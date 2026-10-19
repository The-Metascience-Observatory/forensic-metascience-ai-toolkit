"""The spend ledger is per-run, not per-process.

MEASURED 2026-08-22 (four-paper grok batch, 4 workers): with a module-global
ledger, every `reset_spend()` zeroed every in-flight paper's count and every
`record_spend` landed in whichever papers finished later. The first finisher
reported total_cost_usd $2.11 while its own stages summed to $0.86, and the
four per-paper "totals" ($9.70 in aggregate) each approximated the WHOLE
BATCH's running spend -- a published old-vs-new comparison said 7x when the
truth was ~2x. asyncio tasks copy the ambient context at creation, so a
ContextVar ledger set inside each paper's task is private to that task tree
with no call-site changes.
"""

import asyncio

from metascience_agent import agent


def _stage(cost):
    return {"cost_usd": cost, "wall_seconds": 1.0, "return_code": 0,
            "is_error": False}


class TestConcurrentPapersDoNotShareALedger:
    def test_each_task_sees_only_its_own_spend(self):
        """The batch shape: N papers, each reset-then-record, interleaved."""

        async def paper(cost, ticks):
            agent.reset_spend()
            for c in [cost] * ticks:
                agent.record_spend("stage", _stage(c))
                await asyncio.sleep(0)   # force interleaving
            return agent.spend_so_far()

        async def batch():
            return await asyncio.gather(paper(1.0, 3), paper(10.0, 2))

        a, b = asyncio.run(batch())
        assert a["total_cost_usd"] == 3.0, \
            "paper A must not absorb paper B's concurrent spend"
        assert b["total_cost_usd"] == 20.0
        assert [s["stage"] for s in a["stages"]] == ["stage"] * 3

    def test_a_reset_in_one_task_does_not_zero_another(self):
        """The other half of the contamination: paper B starting mid-run
        used to wipe paper A's ledger, under-counting A."""

        started = asyncio.Event()
        proceed = asyncio.Event()

        async def early():
            agent.reset_spend()
            agent.record_spend("sweep", _stage(5.0))
            started.set()
            await proceed.wait()          # B resets while we sit here
            agent.record_spend("editorial", _stage(2.0))
            return agent.spend_so_far()

        async def late():
            await started.wait()
            agent.reset_spend()           # a NEW paper beginning
            proceed.set()
            return agent.spend_so_far()

        async def batch():
            return await asyncio.gather(early(), late())

        a, b = asyncio.run(batch())
        assert a["total_cost_usd"] == 7.0, \
            "a sibling paper's reset must not zero this paper's ledger"
        assert b["total_cost_usd"] == 0.0

    def test_the_ledger_survives_the_unwinding_exception(self):
        """The original reason the ledger outlives the pipeline: a crash
        record written from an except block must still see the spend."""

        async def crashing_paper():
            agent.reset_spend()
            agent.record_spend("sweep", _stage(4.2))
            try:
                raise RuntimeError("stage 2 died")
            except RuntimeError:
                return agent.spend_so_far()

        out = asyncio.run(crashing_paper())
        assert out["total_cost_usd"] == 4.2

    def test_callers_that_never_reset_still_have_a_ledger(self):
        # The fallback: record before any reset in a bare context must not
        # crash and must be readable -- same lifetime the module global had.
        ctx_before = agent.spend_so_far()
        agent.record_spend("orphan", _stage(0.01))
        after = agent.spend_so_far()
        assert after["total_cost_usd"] >= ctx_before["total_cost_usd"]
        assert any(s["stage"] == "orphan" for s in after["stages"])


class TestTheCrashPathStillSeesTheSpend:
    def test_the_spend_rides_the_exception_across_asyncio_run(self):
        """The cli.analyze crash shape: the pipeline binds its ledger INSIDE
        the task, so the sync-frame crash handler cannot read it through the
        ContextVar -- the number rides the exception instead (attached where
        the context is still visible, read via _metascience_spend outside).
        A clear-in-place reset was tried for this instead and reintroduced
        the batch contamination; see reset_spend's docstring.
        (tests/test_crash_cost_record.py is the end-to-end version through
        the real cli handler.)"""

        async def pipeline():
            agent.reset_spend()
            agent.record_spend("sweep", _stage(4.31))
            raise OSError("Argument list too long")

        async def run_analysis():
            try:
                return await pipeline()
            except BaseException as exc:
                exc._metascience_spend = agent.spend_so_far()
                raise

        try:
            asyncio.run(run_analysis())
        except OSError as exc:
            carried = exc._metascience_spend
        assert carried["total_cost_usd"] == 4.31
