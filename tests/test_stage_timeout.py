"""A stage that hits the wall-clock cap must return what it saw, not vanish.

MEASURED 2026-08-20 on `10.1016--j.neulet.2017.04.022`: grok sat through the
1800 s per-stage timeout, `_run_stage` killed the CLI and re-raised
`TimeoutError`, and the batch wrote `timeout after 1800s` to failed.jsonl
with no forensic_review at all -- so we could not tell whether the CLI hung
on startup, on an MCP tool, or mid-thought. The in-memory stream (messages,
last tool) was in local variables and was thrown away.

Timeout is the same class of stop as the spend cap: work may already have
happened, and discarding it makes a paid (or 30-minute) call un-auditable.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from forensic_metascience_ai_toolkit import agent


class _FakeStdin:
    def write(self, data: bytes) -> None:
        pass

    def close(self) -> None:
        pass

    async def drain(self) -> None:
        pass


class _HangProc:
    """A CLI that emits one tool_use then never EOFs stdout."""

    def __init__(self, payload: bytes = b""):
        self.stdout = asyncio.StreamReader()
        if payload:
            self.stdout.feed_data(payload)
        self.stderr = asyncio.StreamReader()
        self.stdin = _FakeStdin()
        self.pid = None
        self.killed = False
        self.returncode = None

    def kill(self):
        self.killed = True
        self.returncode = -9
        self.stdout.feed_eof()
        self.stderr.feed_eof()

    async def wait(self):
        if not self.killed:
            await asyncio.sleep(3600)
        return self.returncode


@pytest.fixture(autouse=True)
def _no_env_gates(monkeypatch):
    monkeypatch.setattr(agent, "_assert_ready", lambda *a, **k: None)

    async def _no_guard(*a, **k):
        return None

    monkeypatch.setattr(agent, "usage_guard", _no_guard)


def _tool_event(name: str = "extract_pdf") -> bytes:
    return (json.dumps({
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "usage": {"input_tokens": 10, "output_tokens": 4},
            "content": [{"type": "tool_use", "name": name, "id": "t1",
                         "input": {}}],
        },
    }) + "\n").encode()


def _run(monkeypatch, payload: bytes = b"", **kwargs):
    """Build the fake proc INSIDE the running loop.

    `StreamReader` binds to the current event loop at construction. Creating
    it before `asyncio.run` attaches it to a different loop and the hang
    path (readline waiting for EOF) raises RuntimeError instead of timing out.
    """
    holder: dict = {}

    async def fake_exec(*a, **kw):
        assert kw.get("start_new_session") is True
        proc = _HangProc(payload)
        holder["proc"] = proc
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    out = asyncio.run(
        agent._run_stage(["claude", "-p", "x"], "a prompt", **kwargs))
    return out, holder["proc"]


class TestStageTimeoutReturnsWhatItSaw:
    def test_a_hang_returns_error_timeout_instead_of_raising(self, monkeypatch):
        out, proc = _run(monkeypatch, _tool_event("extract_pdf"),
                         timeout=0.15, stage_label="sweep")
        assert proc.killed is True
        assert out["is_error"] is True
        assert out["error_subtype"] == "error_timeout"
        assert out["current_tool"] == "extract_pdf"
        assert out["tool_calls"] == 1
        assert out["messages"], "the in-flight stream must be kept"
        assert agent._stage_hit_timeout(out) is True
        assert agent._stage_hit_budget(out) is False

    def test_a_hang_with_no_events_is_still_a_stage_result(self, monkeypatch):
        """0 messages is a fact, not a reason to raise. The caller (the
        forensic-tools gate) decides whether zero calls is a refuse."""
        out, proc = _run(monkeypatch, timeout=0.15)
        assert proc.killed is True
        assert out["is_error"] is True
        assert out["error_subtype"] == "error_timeout"
        assert out["messages"] == []
        assert out["current_tool"] is None
        assert out["tool_calls"] == 0


def test_editorial_timeout_note_is_distinct_from_the_sweep_note():
    from forensic_metascience_ai_toolkit.agent import (
        PARTIAL_COVERAGE_EDITORIAL_TIMEOUT_NOTE,
        PARTIAL_COVERAGE_TIMEOUT_NOTE,
    )
    assert "editorial pass" in PARTIAL_COVERAGE_EDITORIAL_TIMEOUT_NOTE.lower()
    assert PARTIAL_COVERAGE_EDITORIAL_TIMEOUT_NOTE != PARTIAL_COVERAGE_TIMEOUT_NOTE


def test_a_slow_mcp_tool_returns_indeterminate_not_a_hang(monkeypatch):
    import json
    from types import SimpleNamespace

    from forensic_metascience_ai_toolkit import mcp_server

    async def slow(_args):
        await asyncio.sleep(10)
        return {"content": [{"type": "text", "text": "never"}]}

    monkeypatch.setitem(mcp_server._TOOLS_BY_NAME, "slow",
                        SimpleNamespace(name="slow", handler=slow))
    monkeypatch.setenv("METASCIENCE_MCP_TOOL_TIMEOUT", "0.05")

    async def _go():
        return await mcp_server._call_tool("slow", {})

    out = asyncio.run(_go())
    payload = json.loads(out[0].text)
    assert payload["severity"] == "indeterminate"
    assert "timed out" in payload["error"]


class TestStallIsNotTheSameAsRunningOutOfClock:
    """MEASURED 2026-08-22, `10.1016--j.ynstr.2021.100304`. Its adjudicator
    completed a batch of tool calls at 17:51:33 and its grok session was never
    written to again; the process stayed alive and silent for ~53 more minutes
    until it was killed by hand. Nothing could stop it because `--timeout
    60000` (16.6 h) was the only clock, and that one number has to answer both
    "how long may a legitimate stage take" and "how long before we call it
    dead". Raising it to be safe against the first raises the deadline for a
    DEAD stage by the same amount.

    The recovery path already existed (see the class above); it just could not
    be reached."""

    def test_a_silent_stage_is_cut_off_without_a_duration_cap(self, monkeypatch):
        """No `timeout` at all -- only the stall clock stops this."""
        monkeypatch.setenv("METASCIENCE_STAGE_STALL_SECONDS", "0.3")
        out, proc = _run(monkeypatch, _tool_event("extract_pdf"),
                         stage_label="adjudicator")
        assert proc.killed is True
        assert out["is_error"] is True
        assert out["error_subtype"] == "error_stalled"
        assert out["stalled_seconds"] >= 0.3

    def test_a_stall_keeps_what_ran(self, monkeypatch):
        """Same guarantee the duration path gives: the paper lands PARTIAL
        with the work that happened, not as a bare failure line."""
        monkeypatch.setenv("METASCIENCE_STAGE_STALL_SECONDS", "0.3")
        out, _ = _run(monkeypatch, _tool_event("grim_check"))
        assert out["current_tool"] == "grim_check"
        assert out["tool_calls"] == 1
        assert out["messages"], "the in-flight stream must be kept"
        assert agent._stage_hit_timeout(out) is True

    def test_running_out_of_clock_is_still_reported_as_a_timeout(self, monkeypatch):
        """The two are different facts and get different responses: a budget
        decision versus a backend fault. Fusing them is what made the grok
        stall read as an ordinary slow paper."""
        monkeypatch.setenv("METASCIENCE_STAGE_STALL_SECONDS", "60")
        out, _ = _run(monkeypatch, _tool_event(), timeout=0.15)
        assert out["error_subtype"] == "error_timeout"
        assert out["stalled_seconds"] is None

    def test_the_stall_clock_can_be_turned_off(self, monkeypatch):
        """An operator debugging a genuinely slow backend must be able to
        remove this without also removing the duration cap."""
        monkeypatch.setenv("METASCIENCE_STAGE_STALL_SECONDS", "0")
        out, _ = _run(monkeypatch, _tool_event(), timeout=0.15)
        assert out["error_subtype"] == "error_timeout"

    def test_a_live_stream_is_not_cut_off(self, monkeypatch):
        """The clock measures SILENCE, not elapsed time. A stage emitting
        events must survive well past the stall window."""
        import asyncio as _a, json as _j

        async def feeder(proc):
            for i in range(6):
                await _a.sleep(0.05)
                proc.stdout.feed_data(_tool_event(f"tool_{i}"))
            # EOF cleanly with a zero return code -- this stage SUCCEEDS.
            # `proc.kill()` would set returncode -9 and `_run_stage` would
            # raise StageError, which tests the wrong thing.
            proc.returncode = 0
            proc.killed = True
            proc.stdout.feed_eof()
            proc.stderr.feed_eof()

        holder = {}

        async def fake_exec(*a, **kw):
            proc = _HangProc()
            holder["proc"] = proc
            _a.ensure_future(feeder(proc))
            return proc

        monkeypatch.setenv("METASCIENCE_STAGE_STALL_SECONDS", "0.2")
        monkeypatch.setattr(_a, "create_subprocess_exec", fake_exec)
        out = _a.run(agent._run_stage(["claude", "-p", "x"], "p"))
        assert out["tool_calls"] == 6, "0.05 s gaps are not a stall"
        assert out["error_subtype"] != "error_stalled"
