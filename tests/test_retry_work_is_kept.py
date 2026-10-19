"""A retry that did the work is the attempt the run keeps.

MEASURED 2026-10-18, 10.1001--archpediatrics.2012.999, tools_only on grok-4.6:
the tools agent's first attempt took one turn and made no tool call; the full
re-run made 25 forensic calls in 7.5 minutes (its MCP receipts, run slug
grok-4-6-8757eabf, hold two `suspicious` recalc_stat_to_p results) and filed no
usable document. `retry_if_empty` returned the ORIGINAL zero-call attempt, so
the forensic-tools gate refused the paper for making "no call on its forensic
tool list (not even a reader)" -- false -- and the 25 results were discarded.

Pinned here, end to end through the real module, docket and writer path:
  - the re-run's ledger is handed to the document-only recovery, as a first
    attempt's ledger already was;
  - the recovered rows join their tool verdicts, which needs the recovery
    stage to CARRY the tool-running transcript (it has no tool calls of its
    own) -- true of the first-attempt recovery too, which returned the bare
    recovery stage;
  - when the recovery fails as well, the paper is not refused with a false
    "no call" sentence: the stage that is kept is the one with the calls.
"""
from __future__ import annotations

import json

from forensic_metascience_ai_toolkit import agent
from tests.test_parallel_pipeline import (_doc, _stage, fakes, paper,  # noqa: F401
                                          run)

CALL_INPUT = {"stat_type": "t", "value": 2.1, "df1": 58, "reported_p": 0.002}


def _calls(n: int, severity: str = "consistent") -> list[dict]:
    out = []
    for i in range(n):
        tid = f"call{i}"
        sev = "suspicious" if i == 0 else severity
        inp = CALL_INPUT if i == 0 else {**CALL_INPUT, "value": 1.0 + i}
        out.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": tid,
             "name": agent._mcp("recalc_stat_to_p"), "input": inp}]}})
        out.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid,
             "content": [{"type": "text", "text": json.dumps(
                 {"severity": sev, "explanation": "recomputed"})}]}]}})
    return out


def _empty():
    return _doc([], coverage={"stats_found": 0, "tools_run": []})


def _recovered_row():
    return {"slug": "t2-p", "technique": "recalc_stat_to_p",
            "title": "Table 2: t(58)=2.10 gives p=.04, not the printed p=.002",
            "description": "The printed p does not match the p recomputed from "
                           "the reported t and df.",
            "location": "Table 2", "outcome": "problem",
            "provisional_severity": 3, "inputs": CALL_INPUT,
            "quote": "81.3% of participants reported full compliance"}


def _install(monkeypatch, recovery_doc):
    """First attempt: zero calls, empty doc. Full re-run: 25 calls, empty doc.
    Document-only recovery: `recovery_doc`, no tool calls of its own."""
    labels: list[str] = []

    async def fake_requiring(*, build_cmd, prompt, stage_label, **kw):
        build_cmd()
        labels.append(stage_label)
        res = _stage(_empty())
        agent.record_spend(stage_label, res)
        return res

    inner = agent._run_stage

    async def fake_run_stage(cmd, prompt, *a, **kw):
        label = kw.get("stage_label") or ""
        if label == "tool_agent_retry":
            labels.append(label)
            res = _stage(_empty())
            res["messages"] = _calls(25)
            return res
        if label == "tool_agent_retry_recover":
            labels.append(label)
            assert "YOUR TOOL LEDGER" in prompt and "recalc_stat_to_p" in prompt, (
                "the recovery must be handed the RE-RUN's ledger")
            return _stage(recovery_doc)
        return await inner(cmd, prompt, *a, **kw)

    monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools", fake_requiring)
    monkeypatch.setattr(agent, "_run_stage", fake_run_stage)
    return labels


def test_the_reruns_work_is_recovered_and_its_verdicts_join(paper, monkeypatch, fakes):
    labels = _install(monkeypatch, _doc([_recovered_row()]))
    res = run(paper)
    assert labels == ["tool_agent", "tool_agent_retry", "tool_agent_retry_recover"]
    lim = res["limitations"]
    assert any("retry made 25 forensic calls but filed no usable report" in l
               for l in lim), lim
    assert not any("not even a reader" in l for l in lim), lim
    rows = [f for f in res["findings_v2"]["findings"]
            if f.get("producer") == "tool_expert"]
    assert [r["slug"] for r in rows] == ["t2-p"]
    tv = rows[0].get("tool_verdict")
    assert tv and tv["severity"] == "suspicious" and tv["tool"] == "recalc_stat_to_p", (
        "the verdict joins from the ledger only if the kept stage carries it")
    assert len([m for m in res["tool_agent"]["messages"]
                if m.get("type") == "assistant"]) == 25


def test_a_failed_recovery_is_not_refused_as_a_stage_that_never_ran(
        paper, monkeypatch, fakes):
    # About the retry, not the unfiled-results pass Claude gets since 1.91.0
    # (its 25 accusing calls would otherwise be sent back once more).
    from forensic_metascience_ai_toolkit.modules import _analyst
    monkeypatch.setattr(_analyst, "UNFILED_RECOVERY_BACKENDS",
                        _analyst.UNFILED_RECOVERY_BACKENDS - {"claude"})
    labels = _install(monkeypatch, _empty())
    res = run(paper)
    assert labels[-1] == "tool_agent_retry_recover"
    lim = res["limitations"]
    assert not any("not even a reader" in l for l in lim), (
        "the re-run made 25 calls; saying it made none is false", lim)
    assert any("retry was empty too" in l for l in lim), lim
    kept = res["tool_agent"]
    assert sum(1 for m in kept["messages"] if m.get("type") == "assistant") == 25


def test_a_first_attempts_recovered_docket_keeps_its_ledger(paper, monkeypatch, fakes):
    """The older path: the first attempt did the work, the recovery composed
    the document. Its rows must join their verdicts too."""
    async def fake_requiring(*, build_cmd, prompt, stage_label, **kw):
        build_cmd()
        res = _stage(_empty())
        res["messages"] = _calls(10)
        agent.record_spend(stage_label, res)
        return res

    inner = agent._run_stage

    async def fake_run_stage(cmd, prompt, *a, **kw):
        if (kw.get("stage_label") or "") == "tool_agent_retry":
            assert "YOUR TOOL LEDGER" in prompt
            return _stage(_doc([_recovered_row()]))      # no calls of its own
        return await inner(cmd, prompt, *a, **kw)

    monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools", fake_requiring)
    monkeypatch.setattr(agent, "_run_stage", fake_run_stage)
    res = run(paper)
    rows = [f for f in res["findings_v2"]["findings"]
            if f.get("producer") == "tool_expert"]
    assert rows and (rows[0].get("tool_verdict") or {}).get("severity") == "suspicious"


def test_carrying_work_puts_the_tool_transcript_first():
    from forensic_metascience_ai_toolkit.modules._analyst import _carrying_work
    rec = {"messages": [{"type": "result"}]}
    out = _carrying_work(rec, {"messages": [{"type": "assistant"}]}, None)
    assert out is rec
    assert [m["type"] for m in out["messages"]] == ["assistant", "result"]
