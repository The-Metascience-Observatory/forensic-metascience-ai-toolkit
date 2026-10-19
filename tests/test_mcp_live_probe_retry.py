"""A failed MCP liveness probe is retried, never cached, and still fails closed.

MEASURED 2026-10-18 (tools_only grok batch, 10 workers, beside a peer's
7-worker grok batch on the same machine): `Backend.assert_mcp_live` cached the
probe's FAILURE per process, so one failed `grok mcp doctor` failed every
remaining paper of the batch instantly with the same MCPUnavailable -- 20 of
20 grok papers, the per-paper retry included. That failure had a real cause
(a mixed-tree import, fixed in 1.85.3), but a handshake that loses a race with
a loaded machine would poison a batch the same way.

Pinned here: a transient failure is retried with a pause and then passes; a
failure is not cached, so the next stage probes again; a server that fails
every attempt still raises (the known positive: the guard has not stopped
guarding); and the blocking probe runs off the event loop, so other papers'
stages keep streaming while it waits.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
import time

import pytest

import metascience_agent.llm_backend as lb
from metascience_agent import runtime
from metascience_agent.llm_backend import (CLAUDE, CODEX, GROK, Invocation,
                                           MCPUnavailable,
                                           reset_mcp_live_cache)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    reset_mcp_live_cache()
    monkeypatch.delenv("METASCIENCE_SKIP_MCP_LIVE", raising=False)
    sleeps: list[float] = []
    monkeypatch.setattr(lb, "_probe_pause", lambda s: sleeps.append(s))
    yield sleeps
    reset_mcp_live_cache()


def _scripted_probe(monkeypatch, outcomes, name="_probe_mcp_doctor"):
    """Patch a probe to fail with each string in `outcomes` (None = pass)."""
    calls = []

    def probe(*a, **k):
        calls.append(1)
        outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if outcome is not None:
            raise MCPUnavailable(outcome)
    monkeypatch.setattr(lb, name, probe)
    return calls


class TestATransientFailureIsRetried:
    def test_fails_once_then_passes(self, monkeypatch, _clean, tmp_path):
        calls = _scripted_probe(monkeypatch, ["handshake failed: connection closed", None])
        GROK.assert_mcp_live(tmp_path)
        assert len(calls) == 2
        assert _clean == [lb.MCP_PROBE_BACKOFF_SECONDS[0]], "it paused before re-probing"

    def test_a_success_is_still_cached(self, monkeypatch, tmp_path):
        calls = _scripted_probe(monkeypatch, [None])
        GROK.assert_mcp_live(tmp_path)
        GROK.assert_mcp_live(tmp_path)
        assert len(calls) == 1, "2-3 stages per paper must still cost one probe"

    def test_the_codex_stdio_probe_gets_the_same_retry(self, monkeypatch):
        calls = _scripted_probe(monkeypatch, ["did not answer", None],
                                name="_probe_mcp_stdio")
        CODEX.assert_mcp_live(None)
        assert len(calls) == 2


class TestAFailureIsNeverCached:
    def test_the_next_stage_probes_again(self, monkeypatch, tmp_path):
        """The 2026-10-18 batch: one failure, then 19 papers failed on the
        cached string without the server ever being asked again."""
        calls = _scripted_probe(monkeypatch, ["boom"] * lb.MCP_PROBE_ATTEMPTS + [None])
        with pytest.raises(MCPUnavailable):
            GROK.assert_mcp_live(tmp_path)
        n_first = len(calls)
        GROK.assert_mcp_live(tmp_path)          # the next paper: server is back
        assert len(calls) == n_first + 1


class TestABrokenServerStillFailsClosed:
    """The known positive: a server that is truly broken must still stop the
    stage before spend, after every attempt has failed."""

    def test_every_attempt_fails_and_it_raises(self, monkeypatch, _clean, tmp_path):
        msg = ("forensic_metascience is configured but not healthy: handshake "
               "failed: connection closed: initialize response")
        calls = _scripted_probe(monkeypatch, [msg])
        with pytest.raises(MCPUnavailable) as exc:
            GROK.assert_mcp_live(tmp_path)
        assert len(calls) == lb.MCP_PROBE_ATTEMPTS
        assert msg in str(exc.value)
        assert f"failed {lb.MCP_PROBE_ATTEMPTS} probe(s) in a row" in str(exc.value)
        assert _clean == list(lb.MCP_PROBE_BACKOFF_SECONDS)

    def test_distinct_errors_are_all_named(self, monkeypatch, tmp_path):
        _scripted_probe(monkeypatch, ["first error", "second error"])
        with pytest.raises(MCPUnavailable) as exc:
            GROK.assert_mcp_live(tmp_path)
        assert "second error" in str(exc.value)
        assert "earlier: first error" in str(exc.value)

    def test_the_real_doctor_parser_still_refuses_an_unhealthy_server(
            self, monkeypatch, tmp_path):
        """End to end through the real `check_doctor_payload`, not a stub."""
        payload = {"servers": [{"name": lb.FORENSIC_SERVER, "healthy": False,
                                "checks": [{"label": "handshake",
                                            "passed": False,
                                            "detail": "connection closed"}]}]}

        class Proc:
            returncode = 1
            stdout = json.dumps(payload)
            stderr = ""
        monkeypatch.setattr(lb.shutil, "which", lambda name: "/usr/bin/grok")
        monkeypatch.setattr(lb.subprocess, "run", lambda *a, **k: Proc())
        with pytest.raises(MCPUnavailable, match="not healthy"):
            GROK.assert_mcp_live(tmp_path)
        assert GROK.name not in lb._MCP_LIVE_CACHE

    def test_claude_is_still_a_no_op(self, monkeypatch):
        calls = _scripted_probe(monkeypatch, ["never"])
        CLAUDE.assert_mcp_live(None)
        assert calls == []


_CHILD = ('import json; print(json.dumps({"type": "result", "subtype": '
          '"success", "is_error": False, "result": "ok", "total_cost_usd": 0.0, '
          '"usage": {"input_tokens": 1, "output_tokens": 1}}))')


async def _no_guard(*a, **k):
    return None


def test_the_probe_does_not_block_the_event_loop(monkeypatch):
    """A batch runs every paper's stages on one loop. The probe is a blocking
    subprocess (90 s timeout, now retried with pauses); called on the loop it
    froze every other in-flight stage for that long."""
    probe_seconds = 0.6
    monkeypatch.setattr(lb, "_probe_mcp_doctor",
                        lambda sandbox: time.sleep(probe_seconds))
    backend = dataclasses.replace(CLAUDE, name="probe-test",
                                  mcp_strategy="cwd_config")
    inv = Invocation(argv=[sys.executable, "-c", _CHILD], prompt_delivery="stdin",
                     workdir=None, env_overlay={}, cleanup=lambda: None,
                     backend=backend, forensic_mcp=False)
    ticks: list[float] = []

    async def ticker(stop):
        while not stop.is_set():
            ticks.append(time.monotonic())
            await asyncio.sleep(0.02)

    async def main():
        stop = asyncio.Event()
        task = asyncio.create_task(ticker(stop))
        await asyncio.sleep(0)
        t0 = time.monotonic()
        stage = await runtime._run_stage(
            inv, "prompt", preflight=lambda b: None, guard=_no_guard,
            check_mcp=True, build_env=lambda: {"PATH": "/usr/bin:/bin"})
        stop.set()
        await task
        return t0, stage

    t0, stage = asyncio.run(main())
    assert stage["return_code"] == 0, stage
    during = [t for t in ticks if t0 < t < t0 + probe_seconds]
    assert len(during) >= 5, (
        f"the loop ticked {len(during)} time(s) during a {probe_seconds}s probe")


def test_a_refused_probe_releases_the_invocation(monkeypatch):
    """A stage stopped before the spawn must still clean up. MEASURED
    2026-10-18: every MCPUnavailable grok paper left its sandbox directory
    (prompt.txt empty) in ~/.cache/metascience/grok-sandbox/."""
    _scripted_probe(monkeypatch, ["server is down"])
    backend = dataclasses.replace(CLAUDE, name="probe-test",
                                  mcp_strategy="cwd_config")
    cleaned = []
    inv = Invocation(argv=[sys.executable, "-c", _CHILD], prompt_delivery="stdin",
                     workdir=None, env_overlay={},
                     cleanup=lambda: cleaned.append(1),
                     backend=backend, forensic_mcp=False)
    with pytest.raises(MCPUnavailable, match="server is down"):
        asyncio.run(runtime._run_stage(
            inv, "prompt", preflight=lambda b: None, guard=_no_guard,
            check_mcp=True, build_env=lambda: {"PATH": "/usr/bin:/bin"}))
    assert cleaned == [1]
