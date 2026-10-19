"""Contract, call-budget, tool isolation and failure tests without live spend."""

import asyncio
import copy
import json
from pathlib import Path

import pytest

from copy_paste_detector.grok import GrokAdjudicator, packets, parse_response, validate


@pytest.fixture
def packet():
    return {
        "candidates": [
            {
                "candidate_id": "CP-a",
                "source_id": "CP-a",
                "text": "Values 123.4567 are equal",
                "truncated": False,
            }
        ],
        "context": [
            {"source_id": "context:0", "text": "These are independent animals", "truncated": False}
        ],
        "context_available": True,
    }


def verdict():
    return {
        "decisions": [
            {
                "candidate_id": "CP-a",
                "decision": "retain",
                "reason": "Independent animals share a value",
                "citations": [{"source_id": "context:0", "quote": "independent animals"}],
            }
        ]
    }


@pytest.mark.parametrize(
    "change", ["unknown", "duplicate", "missing", "bad_quote", "empty_citations", "extra_severity"]
)
def test_invalid_verdict_never_clears_or_accuses(packet, change):
    output = verdict()
    if change == "unknown":
        output["decisions"][0]["candidate_id"] = "OTHER"
    elif change == "duplicate":
        output["decisions"] *= 2
    elif change == "missing":
        output["decisions"] = []
    elif change == "bad_quote":
        output["decisions"][0]["citations"][0]["quote"] = "fabricated data"
    elif change == "empty_citations":
        output["decisions"][0]["citations"] = []
    else:
        output["decisions"][0]["severity"] = "impossible"
    with pytest.raises(ValueError):
        validate(output, packet)


def test_missing_context_and_truncation_enforced(packet):
    packet["context_available"] = False
    assert validate(verdict(), packet)[0]["decision"] == "uncertain"
    packet["context_available"] = True
    packet["candidates"][0]["truncated"] = True
    assert validate(verdict(), packet)[0]["decision"] == "uncertain"


def test_packet_budget_keeps_every_candidate_and_blinds_labels():
    result = {
        "duplicate_groups": [
            {"id": f"CP-{i}", "kind": "row_pair", "cells": [], "large": "x" * 60000}
            for i in range(105)
        ],
        "gold_labels": "SECRET ANSWER",
        "paper_issue_report": "SECRET ANSWER",
    }
    all_packets = list(packets(result, []))
    assert len(all_packets) == 105
    assert all(p["candidates"][0]["truncated"] for p in all_packets)
    assert all(len(json.dumps(p)) < 48000 for p in all_packets)
    assert "SECRET ANSWER" not in json.dumps(all_packets)


def test_terminal_receipt_and_no_tools_required():
    with pytest.raises(ValueError):
        parse_response(json.dumps(verdict()))
    with pytest.raises(ValueError, match="tool invocation"):
        parse_response(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "tool_use", "name": "web_search"}]},
                }
            )
        )
    with pytest.raises(ValueError, match="error result"):
        parse_response(
            json.dumps({"type": "result", "is_error": True, "structured_output": verdict()})
        )


def test_parallel_limit_unique_cwds_and_global_attempt_budget(tmp_path, monkeypatch, packet):
    import copy_paste_detector.grok as module

    active = peak = calls = 0
    cwds = []

    async def fake(argv, *, cwd, env, timeout):
        nonlocal active, peak, calls
        assert "--disable-web-search" in argv and "--no-subagents" in argv
        assert "metascience_agent" not in str(argv)
        assert not Path(cwd).is_relative_to(tmp_path)
        cwds.append(cwd)
        active += 1
        calls += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return (
            0,
            json.dumps({"type": "result", "subtype": "success", "structured_output": verdict()}),
            "",
        )

    monkeypatch.setattr(module, "subprocess_output", fake)

    async def run():
        agent = GrokAdjudicator(max_calls=3, concurrency=2)
        return await asyncio.gather(
            *(agent.judge(copy.deepcopy(packet), tmp_path / str(i)) for i in range(5))
        )

    results = asyncio.run(run())
    assert peak == 2 and calls == 3
    assert sum(r["status"] == "call_limit" for r in results) == 2
    assert len(set(cwds)) == 3
    assert all(not p.exists() for p in cwds)


def test_retries_count_toward_budget(tmp_path, monkeypatch, packet):
    import copy_paste_detector.grok as module

    async def unavailable(*a, **kw):
        return 1, "", "429 rate limit"

    async def no_delay(*args):
        return None

    monkeypatch.setattr(module, "subprocess_output", unavailable)
    monkeypatch.setattr(module.asyncio, "sleep", no_delay)
    agent = GrokAdjudicator(max_calls=2, retries=2)
    result = asyncio.run(agent.judge(packet, tmp_path))
    assert agent.calls == 2
    assert result["status"] == "call_limit"
    assert not result["decisions"]


def test_malformed_output_not_retried_as_clear(tmp_path, monkeypatch, packet):
    import copy_paste_detector.grok as module

    async def malformed(*a, **kw):
        return 0, "not JSON", ""

    monkeypatch.setattr(module, "subprocess_output", malformed)
    agent = GrokAdjudicator(max_calls=3)
    result = asyncio.run(agent.judge(packet, tmp_path))
    assert result["status"] == "failed" and not result["decisions"]
    assert agent.calls == 1


def test_cancellation_during_process_creation_reaps_child(monkeypatch):
    import sys

    from copy_paste_detector.grok import subprocess_output

    original = asyncio.create_subprocess_exec
    processes = []

    async def run():
        started = asyncio.Event()

        async def delayed_handle(*args, **kwargs):
            proc = await original(*args, **kwargs)
            processes.append(proc)
            started.set()
            await asyncio.sleep(0.05)
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed_handle)
        task = asyncio.create_task(
            subprocess_output([sys.executable, "-c", "import time; time.sleep(30)"])
        )
        await started.wait()
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()  # A surrounding batch can propagate cancellation twice.
        with pytest.raises(asyncio.CancelledError):
            await task
        assert processes[0].returncode is not None

    asyncio.run(run())
