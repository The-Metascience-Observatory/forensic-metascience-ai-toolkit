"""The per-role MCP fence: off-role tools are not served, and a call for
one is a NAMED refusal.

MEASURED FAILURE, 2026-08-21 apple_cider eval: the TOOL EXPERT called
`run_python_script` -- a SCIENCE_AGENT-only tool -- three times, and every
call EXECUTED with `validated=True` (surface `forensic_mcp_offlist`). The
per-role allowlists lived in `--allowedTools`, which under
bypassPermissions is an auto-approve list rather than a fence, while the
stdio MCP server registered every tool for every caller. The "tool agent
writes no code" decision was prompt-deep.

The fence: `agent._build_mcp_config` stamps the stage into the server's
environment (the process-boundary channel the model cannot write), and
`mcp_server` registers only that role's tools -- absence, the same
mechanism that already keeps the two CLI-only tools off the server.
"""

import importlib
import json

import pytest

from metascience_agent import agent as A
from metascience_agent import mcp_server as M
from metascience_agent.registry import (
    ADJUDICATOR, SCIENCE_AGENT, TOOL_AGENT, stage_tools,
)


def _reload_server(monkeypatch, stage):
    if stage is None:
        monkeypatch.delenv(M.MCP_STAGE_ENV, raising=False)
    else:
        monkeypatch.setenv(M.MCP_STAGE_ENV, stage)
    return importlib.reload(M)


@pytest.fixture(autouse=True)
def _restore_server():
    """Whatever a test does to the module, later tests (and later suites in
    this process) see the unfiltered server again."""
    yield
    import os
    os.environ.pop(M.MCP_STAGE_ENV, None)
    importlib.reload(M)


class TestServedSurface:
    def test_tool_agent_server_has_no_code_tool(self, monkeypatch):
        m = _reload_server(monkeypatch, TOOL_AGENT)
        names = {t.name for t in m._SERVED_TOOLS}
        assert names == set(stage_tools(TOOL_AGENT))
        assert "run_python_script" not in names

    def test_science_agent_server_does_have_it(self, monkeypatch):
        m = _reload_server(monkeypatch, SCIENCE_AGENT)
        names = {t.name for t in m._SERVED_TOOLS}
        assert "run_python_script" in names
        assert names == set(stage_tools(SCIENCE_AGENT))

    def test_no_stage_serves_the_full_surface(self, monkeypatch):
        m = _reload_server(monkeypatch, None)
        assert {t.name for t in m._SERVED_TOOLS} \
            == {t.name for t in m.ALL_TOOLS}

    def test_an_unknown_stage_fails_open_to_the_full_surface(self, monkeypatch):
        """A typo in the env must not brick the server -- the ledger's
        off-list labeling remains the second layer."""
        m = _reload_server(monkeypatch, "not_a_role")
        assert {t.name for t in m._SERVED_TOOLS} \
            == {t.name for t in m.ALL_TOOLS}


class TestOffRoleCallRefuses:
    def test_the_measured_breach_is_now_a_named_refusal(self, monkeypatch):
        import asyncio
        m = _reload_server(monkeypatch, TOOL_AGENT)
        out = asyncio.run(m._call_tool.__wrapped__(
            "run_python_script", {"code": "print(1)", "label": "x"})
            if hasattr(m._call_tool, "__wrapped__")
            else m._call_tool("run_python_script",
                              {"code": "print(1)", "label": "x"}))
        payload = json.loads(out[0].text)
        assert payload.get("refusal") == "off_role_tool"
        assert "tool_agent" in payload["error"]
        assert payload.get("severity") == "indeterminate"


class TestConfigThreading:
    def test_build_mcp_config_stamps_the_stage(self):
        cfg = json.loads(A._build_mcp_config("/tmp/p", mcp_stage=TOOL_AGENT))
        env = cfg["mcpServers"][A.MCP_SERVER_NAME]["env"]
        assert env[M.MCP_STAGE_ENV] == TOOL_AGENT

    def test_no_stage_means_no_env_key(self):
        cfg = json.loads(A._build_mcp_config("/tmp/p"))
        env = cfg["mcpServers"][A.MCP_SERVER_NAME]["env"]
        assert M.MCP_STAGE_ENV not in env

    def test_every_parallel_agent_names_its_stage(self):
        """Pin (the caller-registry pattern): every agent's command passes
        its `mcp_stage`, so a refactor cannot silently revert one agent to
        the unfiltered server. Since Phase 2 the commands are built by the
        modules (`modules/`), not by parallel.py; the parity oracle
        (`tests/test_pipeline_parity.py`) also pins the stage each of the
        three default invocations actually carries."""
        import inspect

        from metascience_agent import modules
        from metascience_agent.modules import _analyst
        from metascience_agent.registry import SCIENCE_AGENT, TOOL_AGENT
        assert modules.load("tools_agent").mcp_stage == TOOL_AGENT
        assert modules.load("scientific_proofreading_agent").mcp_stage == SCIENCE_AGENT
        build = inspect.getsource(_analyst.AnalystModule.build_cmd)
        assert build.count("mcp_stage=self.mcp_stage") == 2, (
            "an analyst command (main or recovery) no longer stamps its stage")
        adj = inspect.getsource(type(modules.load("adjudicator")))
        assert adj.count("mcp_stage=ADJUDICATOR") == 2, (
            "an adjudicator command (main or retry) no longer stamps its stage")


class TestGrokRouteIsFencedToo:
    def test_the_grok_sandbox_config_carries_the_stage(self, tmp_path,
                                                       monkeypatch):
        """MEASURED 2026-08-21, first live Grok parallel run: the claude
        path's stage-filtered server held (0 off-list calls in 39) while
        the grok TOML omitted the stage env and the science agent executed
        check_estimate_ci and grim_check off-role through use_tool."""
        monkeypatch.setenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", "1")
        monkeypatch.setenv("METASCIENCE_GROK_SANDBOX_ROOT", str(tmp_path))
        from metascience_agent.llm_backend import GROK, build_invocation
        inv = build_invocation(
            GROK, system_prompt="x", allowed_tools=["read_file"],
            model="grok-4.6", effort="high", paper_dir=str(tmp_path),
            mcp_stage=SCIENCE_AGENT, python_executable="python3")
        cfgs = list(tmp_path.rglob("config.toml"))
        assert cfgs, "the grok sandbox writes a config.toml"
        body = cfgs[0].read_text()
        assert 'METASCIENCE_MCP_STAGE = "science_agent"' in body
