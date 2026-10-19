"""Phase 3b: `metascience tool` and tool-call receipts.

The generic command goes through `ToolSpec.call` (the MCP surface's gates),
serves only what the MCP server would serve under the same environment, prints
the verdict first so a reproduction check can read it, and receipts each call.
Receipts are the tool side's own record; `receipts.join` marks which ledger
calls the tool layer really answered.
"""

import asyncio
import json

import pytest
from typer.testing import CliRunner

from metascience_agent import receipts
from metascience_agent.cli import app
from metascience_agent.evaluation.deterministic import (
    reported_severity,
    reproduction_execution_problem,
    reproducible_tools,
)

runner = CliRunner()
GRIM_OK = {"mean": 3.53, "n": 30, "decimals": 2, "data_type": "likert"}


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv(receipts.ROOT_ENV, str(tmp_path / "receipts"))
    monkeypatch.delenv("METASCIENCE_MCP_STAGE", raising=False)
    monkeypatch.delenv("METASCIENCE_MCP_TOOLS", raising=False)
    monkeypatch.delenv("METASCIENCE_RUN_SLUG", raising=False)


def _fresh_server(monkeypatch):
    """The fence is the server module's own import-time filter; re-import it
    under the test's environment."""
    import importlib
    import sys
    sys.modules.pop("metascience_agent.mcp_server", None)
    return importlib.import_module("metascience_agent.mcp_server")


@pytest.fixture(autouse=True)
def _restore_server():
    """Put the ORIGINAL server module back: other test files hold it and
    `importlib.reload` it, which needs it registered under its name."""
    import sys
    import metascience_agent
    name = "metascience_agent.mcp_server"
    orig = sys.modules.get(name)
    yield
    if orig is not None:
        sys.modules[name] = orig
        metascience_agent.mcp_server = orig
    else:
        sys.modules.pop(name, None)


class TestRun:
    def test_runs_through_the_gates_and_prints_the_verdict_first(self, monkeypatch):
        _fresh_server(monkeypatch)
        res = runner.invoke(app, ["tool", "run", "grim_check", "--json", json.dumps(GRIM_OK)])
        assert res.exit_code == 0, res.output
        assert reported_severity(res.output) == "consistent"
        body = json.loads(res.output.split("\n", 1)[1])
        assert body["severity"] == "consistent"

    def test_a_missing_precision_is_refused_as_on_mcp(self, monkeypatch):
        """`metascience grim` defaults decimals=2; the gates refuse instead."""
        _fresh_server(monkeypatch)
        res = runner.invoke(app, ["tool", "run", "grim_check", "--json",
                                  json.dumps({"mean": 3.53, "n": 30})])
        assert res.exit_code == 0
        assert res.output.startswith("INDETERMINATE:")

    @pytest.mark.parametrize("argv, refusal", [
        (["tool", "run", "nope", "--json", "{}"], "unknown_tool"),
        (["tool", "run", "grim_check", "--json", "{not json"], "bad_arguments"),
        (["tool", "run", "grim_check", "--json", "[1]"], "bad_arguments"),
        (["tool", "run", "grim_check"], "usage"),
    ])
    def test_usage_errors_exit_2_with_a_named_refusal(self, argv, refusal, monkeypatch):
        _fresh_server(monkeypatch)
        res = runner.invoke(app, argv)
        assert res.exit_code == 2
        assert json.loads(res.output)["refusal"] == refusal

    def test_the_role_fence_is_the_servers(self, monkeypatch):
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "science_agent")
        _fresh_server(monkeypatch)
        # check_table is a tool-agent-only tool.
        res = runner.invoke(app, ["tool", "run", "check_table", "--json", "{}"])
        assert res.exit_code == 2
        assert json.loads(res.output)["refusal"] == "off_role_tool"

    def test_a_pipeline_manifest_narrows_it(self, monkeypatch):
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "tool_agent")
        monkeypatch.setenv("METASCIENCE_MCP_TOOLS", "grim_check,check_table")
        _fresh_server(monkeypatch)
        ok = runner.invoke(app, ["tool", "run", "grim_check", "--json", json.dumps(GRIM_OK)])
        assert ok.exit_code == 0
        off = runner.invoke(app, ["tool", "run", "grimmer_check", "--json", "{}"])
        assert off.exit_code == 2 and json.loads(off.output)["refusal"] == "off_role_tool"

    def test_a_bad_manifest_fails_closed(self, monkeypatch):
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "tool_agent")
        monkeypatch.setenv("METASCIENCE_MCP_TOOLS", "no_such_tool")
        import sys
        sys.modules.pop("metascience_agent.mcp_server", None)
        res = runner.invoke(app, ["tool", "run", "grim_check", "--json", json.dumps(GRIM_OK)])
        assert res.exit_code == 2
        assert json.loads(res.output)["refusal"] == "tool_manifest_error"

    def test_a_call_is_receipted(self, monkeypatch):
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "tool_agent")
        monkeypatch.setenv("METASCIENCE_RUN_SLUG", "sonnet-abc")
        _fresh_server(monkeypatch)
        res = runner.invoke(app, ["tool", "run", "grim_check", "--json", json.dumps(GRIM_OK)])
        assert res.exit_code == 0
        [rec] = receipts.load("sonnet-abc", "tool_agent")
        assert rec["tool"] == "grim_check" and rec["via"] == "cli"
        assert rec["args_sha"] == receipts.digest(receipts.canonical(GRIM_OK))
        assert rec["severity"] == "consistent"


class TestListAndDescribe:
    def test_list_by_role(self):
        res = runner.invoke(app, ["tool", "list", "--role", "science_agent", "--json"])
        rows = json.loads(res.output)
        assert rows and all("science_agent" in r["roles"] for r in rows)
        assert {"name", "family", "evidence", "roles", "purpose"} <= set(rows[0])

    def test_describe_shows_parameters_and_flags(self):
        res = runner.invoke(app, ["tool", "describe", "grim_check"])
        assert res.exit_code == 0
        assert "decimals (int; guard, precision)" in res.output
        assert "metascience tool run grim_check" in res.output


class TestReplayPolicy:
    def test_only_tool_run_of_a_calculation_executes(self):
        assert reproduction_execution_problem(
            "metascience tool run grim_check --json '{}'") is None
        for cmd in ("metascience tool run extract_pdf --json '{}'",
                    "metascience tool run run_python_script --json '{}'",
                    "metascience tool run grim_check --args-file /etc/passwd",
                    "metascience tool list"):
            assert reproduction_execution_problem(cmd), cmd

    def test_the_replayable_set(self):
        tools = reproducible_tools()
        assert {"grim_check", "grim_percentage", "check_regression"} <= tools
        assert not {"extract_pdf", "check_table", "run_python_script",
                    "r_grim_ground_truth"} & tools


class TestReceipts:
    def _call(self, seq, args, result, truncated=False):
        return {"seq": seq, "tool": "mcp__forensic_metascience__grim_check",
                "tool_short": "grim_check", "surface": "forensic_mcp",
                "input": args, "result": result, "result_truncated": truncated}

    def test_join_marks_calls_and_names_both_kinds_of_gap(self, monkeypatch):
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "tool_agent")
        monkeypatch.setenv("METASCIENCE_RUN_SLUG", "run-1")
        a, b = {"mean": 1.5, "n": 10}, {"mean": 2.5, "n": 10}
        receipts.record("grim_check", a, "R-A")
        receipts.record("grim_check", {"mean": 9.9, "n": 10}, "R-lost")
        ledger = [self._call(1, a, "R-A"), self._call(2, b, "R-B"),
                  {"seq": 3, "tool": "Read", "tool_short": "Read",
                   "surface": "builtin_allowed"}]
        summary = receipts.join(ledger, receipts.load("run-1", "tool_agent"))
        assert ledger[0]["receipt"] and ledger[1]["receipt"] is None
        assert "receipt" not in ledger[2]                     # not a forensic call
        assert summary["n_calls"] == 2 and summary["n_calls_with_receipt"] == 1
        assert summary["calls_without_receipt"] == [2]
        assert len(summary["receipts_without_call"]) == 1

    def test_a_different_result_is_reported_not_unmatched(self, monkeypatch):
        """The transport can change an answer (Claude Code replaced a 93K
        extract_pdf result with a 1.3K notice); the call keeps its receipt and
        the difference is named. A result WE truncated is not a difference."""
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "tool_agent")
        monkeypatch.setenv("METASCIENCE_RUN_SLUG", "run-2")
        a = {"mean": 1.5, "n": 10}
        receipts.record("grim_check", a, "the real answer")
        recs = receipts.load("run-2", "tool_agent")
        changed = [self._call(1, a, "a different answer")]
        s = receipts.join(changed, list(recs))
        assert s["n_calls_with_receipt"] == 1 and s["calls_whose_result_differs"] == [1]
        assert changed[0]["receipt_result_differs"] == {"tool_chars": 15, "model_chars": 18}
        cut = [self._call(1, a, "the real", truncated=True)]
        s = receipts.join(cut, list(recs))
        assert s["n_calls_with_receipt"] == 1 and s["calls_whose_result_differs"] == []

    def test_agent_code_mcp_calls_are_joined_too(self, monkeypatch):
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "science_agent")
        monkeypatch.setenv("METASCIENCE_RUN_SLUG", "run-5")
        receipts.record("run_python_script", {"code": "print(1)"}, "1")
        call = {"seq": 1, "tool": "mcp__forensic_metascience__run_python_script",
                "tool_short": "run_python_script", "surface": "agent_code",
                "input": {"code": "print(1)"}, "result": "1"}
        s = receipts.join([call], receipts.load("run-5", "science_agent"))
        assert s["n_calls_with_receipt"] == 1 and s["receipts_without_call"] == []

    def test_no_run_means_no_receipt_and_collect_empties_the_cache(self, monkeypatch):
        assert receipts.record("grim_check", {}, "x") is None
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "tool_agent")
        monkeypatch.setenv("METASCIENCE_RUN_SLUG", "run-3")
        receipts.record("grim_check", {}, "x")
        text = receipts.collect("run-3", "tool_agent")
        assert text and json.loads(text)["tool"] == "grim_check"
        assert receipts.collect("run-3", "tool_agent") is None

    def test_the_mcp_server_receipts_its_answers(self, monkeypatch):
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "tool_agent")
        monkeypatch.setenv("METASCIENCE_RUN_SLUG", "run-4")
        server = _fresh_server(monkeypatch)
        out = asyncio.run(server._call_tool("grim_check", dict(GRIM_OK)))
        [rec] = receipts.load("run-4", "tool_agent")
        assert rec["via"] == "mcp" and rec["result_sha"] == receipts.digest(out[0].text)
