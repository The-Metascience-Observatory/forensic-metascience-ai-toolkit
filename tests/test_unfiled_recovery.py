"""Unfiled tool results are handed back to the analyst once (Grok-side).

MEASURED 2026-10-13: Grok tools agents filed 1 finding after 79-95 forensic
calls in 4 of 11 eval runs. After the report is parsed, code lists the
analyst's own suspicious-or-worse results that no filed finding accounts for
(only calls with a receipt, when receipts exist) and asks once: file each, or
dismiss it with a reason. Claude runs get the pass too since 1.91.0.
"""

import asyncio
import json
from types import SimpleNamespace

from forensic_metascience_ai_toolkit import agent
from forensic_metascience_ai_toolkit.findings_v2 import unaccounted_verdicts
from forensic_metascience_ai_toolkit.modules import _analyst as A
from tests.test_parallel_pipeline import fakes, paper  # noqa: F401


def _call(seq, tool, args, severity, explanation=""):
    return {"seq": seq, "tool": f"mcp__forensic_metascience__{tool}", "tool_short": tool,
            "surface": "forensic_mcp", "validated": True, "input": args,
            "result": json.dumps({"severity": severity, "explanation": explanation}),
            "result_truncated": False}


LEDGER = [
    _call(1, "grim_check", {"mean": 3.53, "n": 30, "decimals": 2}, "impossible", "no sum"),
    _call(2, "grim_check", {"mean": 4.10, "n": 30, "decimals": 2}, "suspicious"),
    _call(3, "grim_check", {"mean": 2.00, "n": 30, "decimals": 2}, "consistent"),
    _call(4, "recalc_independent_t", {"mean1": 1.0, "mean2": 2.0, "sd1": 1, "sd2": 1,
                                      "n1": 10, "n2": 10, "reported_t": 9.9}, "highly_suspicious"),
]


def _finding(technique, inputs, outcome="problem"):
    return {"slug": f"{technique}_{len(json.dumps(inputs))}", "technique": technique,
            "inputs": inputs, "outcome": outcome}


class TestWhatCounts:
    def test_only_suspicious_or_worse_and_only_unfiled(self):
        filed = [_finding("grim_check", {"mean": 3.53, "n": 30})]
        left = unaccounted_verdicts(filed, LEDGER)
        assert [(v["tool"], v["severity"]) for v in left] == [
            ("grim_check", "suspicious"), ("recalc_independent_t", "highly_suspicious")]

    def test_a_pass_row_does_not_account_for_an_accusing_call(self):
        """1.91.0: a pass row says the tool was wrong without saying why."""
        filed = [_finding("grim_check", {"mean": 4.10, "n": 30}, outcome="pass")]
        tools = [v["call"]["seq"] for v in unaccounted_verdicts(filed, LEDGER)]
        assert 2 in tools

    def test_an_undecided_row_accounts_for_its_call(self):
        filed = [_finding("grim_check", {"mean": 4.10, "n": 30}, outcome="undecided")]
        tools = [v["call"]["seq"] for v in unaccounted_verdicts(filed, LEDGER)]
        assert 2 not in tools

    def test_a_bookkeeping_key_does_not_break_the_join(self):
        """A key the tool does not take (`n_checked`) cannot contradict its call."""
        filed = [_finding("grim_check", {"mean": 4.10, "n": 30, "n_checked": 7})]
        tools = [v["call"]["seq"] for v in unaccounted_verdicts(filed, LEDGER)]
        assert 2 not in tools

    def test_a_wrong_value_still_breaks_the_join(self):
        filed = [_finding("grim_check", {"mean": 4.10, "n": 31, "n_checked": 7})]
        tools = [v["call"]["seq"] for v in unaccounted_verdicts(filed, LEDGER)]
        assert 2 in tools

    def test_most_severe_first_and_receipts_filter(self, monkeypatch, tmp_path):
        from forensic_metascience_ai_toolkit import receipts
        items = A.unfiled_results(LEDGER, {"findings": []})
        assert [v["severity"] for v in items] == ["impossible", "highly_suspicious", "suspicious"]
        # Receipts: only calls our tool layer answered are listed.
        monkeypatch.setenv(receipts.ROOT_ENV, str(tmp_path))
        recs = [{"id": "r1", "tool": "grim_check",
                 "args_sha": receipts.digest(receipts.canonical(LEDGER[0]["input"])),
                 "result_sha": receipts.digest(LEDGER[0]["result"])}]
        only = A.unfiled_results(LEDGER, {"findings": []}, recs)
        assert [v["call"]["seq"] for v in only] == [1]


class TestInputsLessFinding:
    """A finding with no `inputs` accounts only for the calls its prose names.

    MEASURED 2026-10-16 (10.1371--journal.pone.0042828, grok-4.6, v1.78.0):
    grim_check returned `impossible` on seven Table 2 means at n=6 and the
    tools agent filed ONE grim_check finding, `inputs: null`, naming 51.9.
    It used to account for every grim_check call, so the recovery pass never
    asked about the other means.
    """

    MEANS = (51.9, 45.9, 50.9, 18.4, 9.4, 18.4, 51.9)
    LOCATORS = ("CON(6) Locomotor Baseline", "CON(6) Locomotor Day 28",
                "ISCH(6) Locomotor Baseline", "CON(6) Rearing Baseline",
                "MCAO+CMS(6) Rearing Day 28", "MCAO+CMS+D(6) Rearing Baseline",
                "MCAO+CMS+D(6) Locomotor Baseline")
    # The finding exactly as filed (quote/location/title/description).
    FILED = {
        "slug": "grim_51_9", "technique": "grim_check", "inputs": None,
        "outcome": "problem",
        "title": "Table 2: CON locomotor baseline mean 51.9 impossible for n=6",
        "description": (
            "Table 2 reports CON locomotor at baseline as 51.9±2.1 with "
            "n=6. Locomotor counts were tallied as whole numbers. No integer "
            "total of 6 counts has a mean that rounds or truncates to 51.9; "
            "311/6=51.833 rounds to 51.8 and 312/6=52.0. Nearby attainable "
            "means are 51.8 and 52.0."),
        "location": "Table 2, CON(6) Locomotor Baseline",
        "quote": "51.9±2.1",
    }

    def _ledger(self):
        return [_call(i + 1, "grim_check",
                      {"mean": m, "n": 6, "decimals": 1, "data_type": "count",
                       "scale_min": 0, "scale_max": 500 if "Locomotor" in loc else 200,
                       "source_locator": f"Table 2, {loc}"}, "impossible")
                for i, (m, loc) in enumerate(zip(self.MEANS, self.LOCATORS))]

    def test_the_other_means_are_handed_back(self):
        left = unaccounted_verdicts([self.FILED], self._ledger())
        # Both 51.9 calls are named by the finding; the five others are not.
        assert sorted(v["call"]["input"]["mean"] for v in left) == \
            [9.4, 18.4, 18.4, 45.9, 50.9]

    def test_known_positive_it_used_to_hide_all_of_them(self):
        """The guard still has teeth: dropping the finding hands back all 7."""
        assert len(unaccounted_verdicts([], self._ledger())) == 7

    def test_tool_verdict_joins_only_the_named_calls(self):
        from forensic_metascience_ai_toolkit.findings_v2 import backing_call, tool_verdict_for
        ledger = self._ledger()
        # Make an unnamed call disagree: under the old any-call join this
        # broke unanimity and erased the verdict.
        ledger[1]["result"] = json.dumps({"severity": "consistent"})
        tv = tool_verdict_for(self.FILED, ledger)
        assert tv and tv["severity"] == "impossible" and tv["tool"] == "grim_check"
        # Two 51.9 calls with different arguments: no single call to replay.
        assert backing_call(self.FILED, ledger) is None

    def test_a_shared_n_does_not_tie(self):
        """n=6 is printed in every GRIM finding; it names no particular call."""
        filed = dict(self.FILED, title="A mean impossible for n=6",
                     description="n=6", quote="", location="Table 2")
        assert len(unaccounted_verdicts([filed], self._ledger())) == 7

    def test_the_most_specific_match_wins_when_n_differs(self):
        ledger = [
            _call(1, "grim_check", {"mean": 51.9, "n": 6, "decimals": 1}, "impossible"),
            _call(2, "grim_check", {"mean": 45.9, "n": 6, "decimals": 1}, "impossible"),
            _call(3, "grim_check", {"mean": 30.3, "n": 7, "decimals": 1}, "impossible"),
        ]
        left = unaccounted_verdicts([self.FILED], ledger)
        assert [v["call"]["seq"] for v in left] == [2, 3]

    def test_a_single_call_is_still_covered(self):
        """Nothing to tell apart: the one call of the tool is the one meant."""
        ledger = [_call(1, "grim_check", {"mean": 3.53, "n": 30, "decimals": 2},
                        "impossible")]
        filed = dict(self.FILED, title="impossible mean", description="",
                     quote="", location="")
        assert unaccounted_verdicts([filed], ledger) == []


class TestThePass:
    def _ctx(self, tmp_path):
        return SimpleNamespace(run_slug=None, verbose=False, timeout=60, on_progress=None)

    def _stage(self):
        msgs = []
        for c in LEDGER:
            msgs.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": f"u{c['seq']}", "name": c["tool"], "input": c["input"]}]}})
            msgs.append({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"u{c['seq']}", "content": c["result"]}]}})
        return {"messages": msgs}

    def test_grok_is_asked_once_and_the_answer_is_merged(self, monkeypatch, tmp_path):
        sent = {}

        async def fake_run(cmd, prompt, *a, **k):
            sent["prompt"], sent["label"] = prompt, k.get("stage_label")
            filed = _finding("grim_check", {"mean": 3.53, "n": 30})
            filed["description"] = "result #1: the mean is not reachable"
            return {"structured_output": {
                "findings": [filed],
                "unchecked": [{"location": "result #3: grim_check mean 4.10 n 30",
                               "reason": "the paper prints 4.1, one decimal"}]},
                "cost_usd": 0.01, "messages": [{"type": "result"}]}
        monkeypatch.setattr(agent, "_run_stage", fake_run)
        monkeypatch.setattr(agent, "record_spend", lambda *a, **k: None)
        doc = {"findings": [], "unchecked": []}
        lim = []
        out, extra = asyncio.run(A.recover_unfiled(
            self._ctx(tmp_path), SimpleNamespace(name="grok"), self._stage(), doc,
            "tool_agent", "tool_expert", "tool_agent", lambda: "CMD", lim))
        assert extra["messages"] == [{"type": "result"}]
        assert sent["label"] == "tool_agent_unfiled"
        assert "1. `grim_check` returned **impossible**" in sent["prompt"]
        assert "BEGINS with `result #N:`" in sent["prompt"]
        assert "the tool said: no sum" in sent["prompt"]
        assert len(out["findings"]) == 1 and len(out["unchecked"]) == 1
        # Exact by number: #1 filed, #3 dismissed, #2 still open.
        assert lim == ["the tool_agent report did not account for 3 of its own "
                       "suspicious-or-worse tool results; asked once to account for "
                       "them: 1 filed, 1 dismissed with a reason, 1 still unaccounted"]
        # The dismissed call, by tool and arguments, for the run's final record.
        assert extra["dismissed_calls"] == [{"tool": "grim_check", "input": LEDGER[1]["input"]}]

    def test_an_unlisted_backend_is_not_asked(self, monkeypatch, tmp_path):
        async def boom(*a, **k):
            raise AssertionError("an unlisted backend got the unfiled pass")
        monkeypatch.setattr(agent, "_run_stage", boom)
        doc = {"findings": []}
        out, extra = asyncio.run(A.recover_unfiled(
            self._ctx(tmp_path), SimpleNamespace(name="not_a_backend"), self._stage(), doc,
            "tool_agent", "tool_expert", "tool_agent", lambda: "CMD", []))
        assert out is doc and out["findings"] == [] and extra is None

    def test_claude_is_asked_but_keeps_one_zero_call_retry(self):
        """1.91.0: Claude left 56 results unaccounted on the p-value working
        set; it joins the unfiled pass, not the zero-call second retry."""
        assert "claude" in A.UNFILED_RECOVERY_BACKENDS
        assert "claude" not in A.ZERO_CALL_RETRY_BACKENDS
        assert A.ZERO_CALL_RETRY_BACKENDS == {"grok", "openrouter", "codex", "antigravity"}

    def test_nothing_unfiled_means_no_call(self, monkeypatch, tmp_path):
        async def boom(*a, **k):
            raise AssertionError("asked with nothing to account for")
        monkeypatch.setattr(agent, "_run_stage", boom)
        filed = [_finding("grim_check", {"mean": m, "n": 30}) for m in (3.53, 4.10)]
        filed.append(_finding("recalc_independent_t", {"mean1": 1.0, "mean2": 2.0}))
        asyncio.run(A.recover_unfiled(
            self._ctx(tmp_path), SimpleNamespace(name="grok"), self._stage(),
            {"findings": filed}, "tool_agent", "tool_expert", "tool_agent",
            lambda: "CMD", []))


class TestZeroCallRetry:
    """MEASURED 2026-10-14: a grok science agent's whole session was one turn,
    an empty placeholder document taken as the answer (3 of 20 runs)."""

    def test_the_correction_names_the_first_call(self):
        src = SimpleNamespace(xml=None, main_pdf="/p/paper.pdf", body_md=None)
        text = A._producer_retry_correction(None, {"findings": []}, 0, False, False,
                                            first_call=A._first_call(src))
        assert "`extract_pdf` with pdf_path `/p/paper.pdf`" in text
        assert "only JSON, with no tool call beside it" in text
        assert "highlights document" not in text

    def test_a_second_zero_call_dump_gets_one_more_attempt(self, monkeypatch):
        calls = []

        async def empty(cmd, prompt, *a, **k):
            calls.append(k.get("stage_label"))
            return {"structured_output": {"findings": [], "unchecked": []},
                    "messages": [], "cost_usd": 0.0}
        monkeypatch.setattr(agent, "_run_stage", empty)
        monkeypatch.setattr(agent, "record_spend", lambda *a, **k: None)
        ctx = SimpleNamespace(verbose=False, timeout=60, on_progress=None,
                              src=SimpleNamespace(xml="/p/a.xml", main_pdf=None, body_md=None))
        lim = []
        stage = {"messages": [], "structured_output": {"findings": []}}
        asyncio.run(A.retry_if_empty(ctx, SimpleNamespace(name="grok"), stage,
                                     {"findings": [], "unchecked": []}, "science_agent",
                                     "science_error", lambda: "CMD", "PROMPT", lim))
        assert calls == ["science_agent_retry", "science_agent_retry2"]
        assert any("retried a second time" in l for l in lim)


def test_the_unfiled_transcript_is_archived(paper, fakes):  # noqa: F811
    from forensic_metascience_ai_toolkit import parallel
    r = asyncio.run(agent.analyze_paper(str(paper), mode="parallel"))
    r["unfiled_stages"] = {"tool_agent": {"messages": [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "x"}]}}]}}
    out = paper / "review-unfiled"
    parallel.write_parallel_outputs(r, out, render_pdf=False)
    assert (out / "messages.tool_agent_unfiled.json").is_file()
