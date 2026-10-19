"""A stage whose stream ends without the CLI's `result` event.

MEASURED 2026-10-18 (v1.83.0 dce5aacf, `metascience batch --backend claude
--model sonnet` on statcheck_pvalue_errors/working_set, 20 workers on one
event loop): 7 of 57 stages exited rc=0 with no `result` event. Six had
called StructuredOutput and been told "Structured output provided
successfully"; the tools agent of 10.1007--s40200-021-00832-0 lost its last
100 s, the accepted call included (the CLI's own session log has it). Every
one read `is_error: false`, `cost_usd: 0.0`, and "produced no parseable
findings JSON" or a salvage warning.

The cause is the CLI: `claude -p` (2.1.301) drops whatever it has not yet
written when it exits with its stdout PIPE full, and exits 0. Reproduced with
the real CLI: a reader that slept 75 s got 65,242 bytes (the pipe capacity),
the last line cut mid-JSON, from a CLI that had exited at t+15 s. Twenty
stages sharing one loop is what let the pipe fill. Three fixes, three test
groups below:

1. the child's stdout is a regular file we tail (`runtime._FileLineReader`),
   which a CLI cannot fill or drop;
2. the accepted StructuredOutput call in the transcript is read when no
   `result` event delivered the document (`track_contracts._extract_json`),
   and run_meta says so, with the cost marked unknown;
3. a stage that delivered no document is `is_error: true`.

The fixtures in tests/data/lost_result_event/ are trimmed tails of three of
those transcripts; each records its own provenance.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import time

import pytest

from forensic_metascience_ai_toolkit import agent, runtime
from forensic_metascience_ai_toolkit.llm_backend import CLAUDE, Invocation
from forensic_metascience_ai_toolkit.track_contracts import (
    ACCEPTED_TOOL_CALL_PATH,
    _accepted_structured_output,
    _extract_json,
    mark_no_document,
)
from tests.test_parallel_pipeline import (  # noqa: F401 -- fixtures
    _doc, _row, _stage, fakes, paper, run)

DATA = pathlib.Path(__file__).parent / "data" / "lost_result_event"
SCIENCE_2055 = "10.1177--2055102915615046.science_agent.json"
TOOL_1007 = "10.1007--s40200-021-00832-0.tool_agent.json"
ADJ_586 = "10.1037--0022-3514.87.5.586.adjudicator.json"


def _messages(name):
    return json.loads((DATA / name).read_text())["messages"]


def _lost_stage(name, **kw):
    """The stage payload `_run_stage` returns for such a stream now."""
    st = _stage(None, cost=0.0)
    st.update(messages=_messages(name), result_event=False,
              cost_reported=False, stdout_ended_mid_line=False)
    st.update(kw)
    return st


# --------------------------------------------------------------------------
# 1. The child's stdout is a file: what the CLI wrote is what we read.
# --------------------------------------------------------------------------

#: Behaves like the CLI at exit: stdout non-blocking, write until the kernel
#: refuses, then exit 0 with the rest unwritten. The `result` event is last.
_DROPPING_CHILD = r"""
import fcntl, json, os
fl = fcntl.fcntl(1, fcntl.F_GETFL)
fcntl.fcntl(1, fcntl.F_SETFL, fl | os.O_NONBLOCK)
lines = [json.dumps({"type": "assistant", "message": {"id": "m%d" % i,
         "role": "assistant", "content": [{"type": "text", "text": "x" * 1000}]}})
         for i in range(200)]
lines.append(json.dumps({"type": "result", "subtype": "success",
    "is_error": False, "result": "", "total_cost_usd": 0.42,
    "structured_output": {"schema_version": "2.0", "paper_id": "p",
                          "findings": [{"slug": "kept"}]},
    "usage": {"input_tokens": 1, "output_tokens": 1}}))
view = memoryview(("\n".join(lines) + "\n").encode())
while view:
    try:
        view = view[os.write(1, view):]
    except BlockingIOError:
        break
os._exit(0)
"""

#: How long the event loop is blocked after the spawn: what a busy batch does.
LOOP_BLOCK = 1.0


def _invocation(script):
    return Invocation(argv=[sys.executable, "-c", script],
                      prompt_delivery="stdin", workdir=None, env_overlay={},
                      cleanup=lambda: None, backend=CLAUDE, forensic_mcp=False)


async def _no_guard(*a, **k):
    return None


def _run_stage(inv):
    return asyncio.run(runtime._run_stage(
        inv, "prompt", preflight=lambda backend: None, guard=_no_guard,
        build_env=lambda: {"PATH": "/usr/bin:/bin"}))


@pytest.fixture()
def blocked_loop(monkeypatch):
    real_exec = asyncio.create_subprocess_exec

    async def spawn_then_block(*a, **kw):
        proc = await real_exec(*a, **kw)
        time.sleep(LOOP_BLOCK)  # another coroutine doing synchronous work
        return proc

    monkeypatch.setattr(runtime.asyncio, "create_subprocess_exec",
                        spawn_then_block)


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl")
class TestTheStreamSurvivesABusyLoop:
    def test_the_double_reproduces_the_loss_on_a_pipe(self):
        """KNOWN POSITIVE for the double (LESSONS #4): on a pipe nobody is
        reading, it loses its `result` event exactly as the CLI did."""
        # Synchronous on purpose: an asyncio pipe transport drains the pipe
        # whenever the loop runs, so "nobody is reading" must be enforced.
        import subprocess
        proc = subprocess.Popen([sys.executable, "-c", _DROPPING_CHILD],
                                stdout=subprocess.PIPE)
        rc = proc.wait(timeout=60)      # exits before anything is read
        out = proc.stdout.read()
        proc.stdout.close()
        assert rc == 0
        assert b'"type": "result"' not in out
        assert len(out) < 200 * 1000

    def test_run_stage_gets_the_result_event(self, blocked_loop):
        stage = _run_stage(_invocation(_DROPPING_CHILD))
        assert stage["return_code"] == 0
        assert stage["result_event"] is True
        assert stage["structured_output"]["findings"] == [{"slug": "kept"}]
        assert stage["cost_usd"] == pytest.approx(0.42)
        assert stage["stdout_unparsed_lines"] == 0
        assert len(stage["messages"]) == 201

    def test_the_child_is_handed_a_file_not_a_pipe(self, monkeypatch):
        seen = {}

        class _Done(Exception):
            pass

        async def capture(*a, **kw):
            seen["stdout"] = kw["stdout"]
            raise _Done

        monkeypatch.setattr(runtime.asyncio, "create_subprocess_exec", capture)
        with pytest.raises(_Done):
            _run_stage(_invocation("pass"))
        assert seen["stdout"] is not asyncio.subprocess.PIPE
        assert hasattr(seen["stdout"], "fileno")
        # ...and the file is gone afterwards.
        assert not pathlib.Path(seen["stdout"].name).exists()

    def test_a_stream_cut_mid_line_says_so(self):
        """What 10.1007's tools agent most likely received: whole events, then
        a line the CLI never finished. No `result` event, and the record names
        the cut instead of skipping it silently."""
        script = (
            "import sys\n"
            "sys.stdout.write('{\"type\": \"system\", \"subtype\": \"x\"}\\n')\n"
            "sys.stdout.write('{\"type\": \"assistant\", \"message\": {\"content\": [')\n"
            "sys.stdout.flush()\n")
        stage = _run_stage(_invocation(script))
        assert stage["return_code"] == 0
        assert stage["result_event"] is False
        assert stage["stdout_unparsed_lines"] == 1
        assert stage["stdout_ended_mid_line"] is True
        assert stage["cost_reported"] is False

    def test_a_complete_stream_reports_a_result_event(self):
        script = ("print('{\"type\": \"result\", \"subtype\": \"success\", "
                  "\"is_error\": false, \"result\": \"ok\", "
                  "\"total_cost_usd\": 0.1}')")
        stage = _run_stage(_invocation(script))
        assert stage["result_event"] is True
        assert stage["stdout_ended_mid_line"] is False
        assert stage["result"] == "ok"


class TestFileLineReader:
    def test_lines_written_after_the_first_read_and_before_exit(self, tmp_path):
        path = tmp_path / "out.jsonl"
        path.write_bytes(b"")

        async def go():
            loop = asyncio.get_running_loop()
            exited = loop.create_future()
            reader = runtime._FileLineReader(open(path, "rb"), exited, poll=0.01)
            got = []

            async def writer():
                with open(path, "ab") as fh:
                    for chunk in (b'{"a": 1}\n{"b"', b': 2}\n', b'{"tail": 3}'):
                        await asyncio.sleep(0.03)
                        fh.write(chunk)
                        fh.flush()
                exited.set_result(0)

            task = asyncio.ensure_future(writer())
            while line := await reader.readline():
                got.append(line)
            await task
            return got

        assert asyncio.run(go()) == [b'{"a": 1}\n', b'{"b": 2}\n', b'{"tail": 3}']


# --------------------------------------------------------------------------
# 2. The accepted StructuredOutput call is the document.
# --------------------------------------------------------------------------

class TestTheAcceptedCallIsRead:
    def test_science_agent_2055_yields_its_nine_findings(self):
        msgs = _messages(SCIENCE_2055)
        doc, path = _extract_json({"messages": msgs, "text": ""})
        assert path == ACCEPTED_TOOL_CALL_PATH
        assert doc["paper_id"] == "10.1177--2055102915615046"
        assert len(doc["findings"]) == 9
        # The REJECTED first attempt (two titles over 90 characters) is not it.
        assert all(len(f["title"]) <= 90 for f in doc["findings"])

    def test_adjudicator_586_yields_its_seventeen_verdicts(self):
        doc, path = _extract_json({"messages": _messages(ADJ_586), "text": ""})
        assert path == ACCEPTED_TOOL_CALL_PATH
        assert len(doc["verdicts"]) == 17
        assert doc["paper"]["verdict"]

    def test_a_rejected_call_is_never_used(self):
        """10.1007's tools agent: its only StructuredOutput in our stream was
        rejected by the schema gate; the accepted one never reached us."""
        msgs = _messages(TOOL_1007)
        assert any(b.get("name") == "StructuredOutput"
                   for e in msgs if e.get("type") == "assistant"
                   for b in e["message"]["content"])
        assert _accepted_structured_output(msgs) is None
        assert _extract_json({"messages": msgs, "text": ""}) == (None, "failed")

    def test_a_call_without_a_tool_result_is_not_trusted(self):
        msgs = [m for m in _messages(SCIENCE_2055) if m.get("type") != "user"]
        assert _accepted_structured_output(msgs) is None

    def test_a_result_event_still_wins(self):
        st = {"messages": _messages(SCIENCE_2055),
              "structured_output": {"paper_id": "from_result", "findings": []}}
        assert _extract_json(st) == (st["structured_output"], "json_schema")

    def test_it_precedes_the_prose_salvage(self):
        """10.1097--md.0000000000015344's science agent took this route as
        `salvaged_object` and was reported as a DEGENERATED stream."""
        text = json.dumps({"schema_version": "2.0", "paper_id": "prose",
                           "findings": []})
        doc, path = _extract_json({"messages": _messages(SCIENCE_2055),
                                   "text": text})
        assert path == ACCEPTED_TOOL_CALL_PATH and doc["paper_id"] != "prose"


# --------------------------------------------------------------------------
# 3. End to end: findings reach the report; a lost stage reads as errored.
# --------------------------------------------------------------------------

class TestThroughThePipeline:
    def test_recovered_science_findings_reach_the_report(self, paper, fakes):
        fakes["science"] = _lost_stage(SCIENCE_2055)
        res = run(paper)
        meta = res["run_meta"]["stages"]["science_agent"]
        assert meta["output_parse_path"] == ACCEPTED_TOOL_CALL_PATH
        assert meta["result_event"] is False
        assert meta["cost_reported"] is False
        assert meta["is_error"] is False
        assert "science_agent" in res["run_meta"]["cost_unreported_stages"]
        lims = res["limitations"]
        assert any("accepted StructuredOutput call" in l and "UNKNOWN" in l
                   for l in lims), lims
        assert not any("no parseable findings JSON" in l for l in lims)
        rows = res["findings_v2"]["findings"]
        science_rows = [f for f in rows if f.get("producer") == "science_error"]
        assert len(science_rows) == 9, [f.get("producer") for f in rows]

    def test_a_lost_tools_stage_is_an_error(self, paper, fakes, monkeypatch):
        repaired = []

        async def no_repair(raw, *a, **k):
            repaired.append(raw)
            return None

        monkeypatch.setattr(agent, "_repair_json", no_repair)
        fakes["tool"] = _lost_stage(TOOL_1007, stdout_ended_mid_line=True)
        res = run(paper)
        meta = res["run_meta"]["stages"]["tool_agent"]
        assert meta["is_error"] is True
        assert meta["error_subtype"] == "no_result_event"
        assert meta["result_event"] is False
        assert meta["stdout_ended_mid_line"] is True
        lims = res["limitations"]
        assert any("tool_agent" in l and "LOST, not absent" in l
                   and "cut mid-line" in l for l in lims), lims

    def test_a_lost_adjudicator_is_an_error(self, paper, fakes):
        fakes["adjudicator"] = _lost_stage(TOOL_1007)   # no accepted document
        res = run(paper)
        meta = res["run_meta"]["stages"]["adjudicator"]
        assert meta["is_error"] is True
        assert meta["error_subtype"] == "no_result_event"
        assert any("adjudicator" in l and "`result`" in l
                   for l in res["limitations"]), res["limitations"]


class TestMarkNoDocument:
    def test_a_specific_subtype_is_kept(self):
        st = {"is_error": True, "error_subtype": "error_timeout"}
        mark_no_document(st)
        assert st == {"is_error": True, "error_subtype": "error_timeout"}

    def test_a_complete_stream_with_nothing_parseable(self):
        st = {"is_error": False, "result_event": True}
        mark_no_document(st)
        assert st["is_error"] is True
        assert st["error_subtype"] == "no_parseable_output"
