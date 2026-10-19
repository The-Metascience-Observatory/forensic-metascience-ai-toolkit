"""Phase 3b: `tool_access` -- how an agent module reaches its tools.

`mcp` (default) is today's server and prompt, byte for byte. `mcp_brief`
cuts each MCP description to its first sentence and serves the rest through
`describe_tool`. `skill` drops the MCP server: the agent runs `metascience
tool run` in a shell that Claude's `dontAsk` mode fences to that command, with
the environment that applies the same surface and writes the same receipts.
See docs/specs/tool_access.md.
"""

import asyncio
import json

import pytest

from forensic_metascience_ai_toolkit import agent
from forensic_metascience_ai_toolkit.core import prompts
from forensic_metascience_ai_toolkit import pipeline_config as pc


def _cfg(*mods, **top):
    return pc.parse({"schema_version": 1, "name": top.pop("name", "t"),
                     "modules": list(mods), **top})


class TestConfig:
    def test_default_is_mcp_and_is_not_recorded(self):
        cfg = pc.load("full")
        assert all(m.tool_access == "mcp" for m in cfg.modules)
        assert "tool_access" not in json.dumps(cfg.record())

    def test_a_non_default_is_recorded_and_round_trips(self):
        cfg = _cfg({"use": "tools_agent", "tool_access": "skill"},
                   {"use": "scientific_proofreading_agent", "tool_access": "mcp_brief"})
        rec = cfg.record()
        assert {m["use"]: m.get("tool_access") for m in rec["modules"]} == {
            "tools_agent": "skill", "scientific_proofreading_agent": "mcp_brief"}
        back = pc.from_record(json.loads(json.dumps(rec)))
        assert back.digest == cfg.digest
        assert back.module("tools_agent").tool_access == "skill"
        assert cfg.digest != _cfg("tools_agent", "scientific_proofreading_agent").digest

    @pytest.mark.parametrize("entry, fragment", [
        ({"use": "tools_agent", "tool_access": "smoke_signals"}, "expected one of"),
        ({"use": "adjudicator", "tool_access": "skill"}, "not an agent module"),
        ({"use": "text_forensics", "tool_access": "mcp"}, "not an agent module"),
    ])
    def test_bad_values_are_refused(self, entry, fragment):
        with pytest.raises(pc.PipelineConfigError, match=fragment):
            _cfg(entry)


class TestPrompts:
    def test_mcp_adds_nothing(self):
        cfg = _cfg("tools_agent")
        assert prompts.tool_access_note(cfg, "tools_agent") == ""

    def test_brief_tells_the_agent_to_read_the_manual(self):
        cfg = _cfg({"use": "tools_agent", "tool_access": "mcp_brief"})
        text = prompts.system_prompt_for(cfg, "tools_agent")
        assert "## Tool descriptions in this run" in text and "`describe_tool`" in text

    def test_skill_lists_exactly_the_modules_tools(self):
        cfg = _cfg({"use": "tools_agent", "tool_access": "skill",
                    "tools": ["grim_check"]})
        note = prompts.tool_access_note(cfg, "tools_agent")
        assert "metascience tool run <name> --json" in note
        listed = [l.split("`")[1] for l in note.splitlines() if l.startswith("- `")]
        assert listed == prompts.module_tool_names(cfg, "tools_agent")
        assert "grim_check" in listed and "grimmer_check" not in listed


class TestInvocations:
    def _build(self, access, backend="claude", **kw):
        return agent._build_claude_cmd(
            system_prompt="sys", allowed_tools=["Read", agent._mcp("grim_check")],
            model="sonnet", backend=backend, mcp_stage="tool_agent",
            run_slug="sonnet-1", paper_dir="/papers/p1", tool_access=access, **kw)

    def test_skill_on_claude_is_fenced_by_dont_ask(self):
        inv = self._build("skill", mcp_tools=["grim_check"])
        argv = inv.argv
        assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
        assert argv[argv.index("--tools") + 1] == "Read,Bash"
        allowed = argv[argv.index("--allowedTools") + 1].split(",")
        assert "Bash(metascience tool run *)" in allowed
        assert not [t for t in allowed if t.startswith("mcp__")]
        assert "Bash" not in argv[argv.index("--disallowedTools") + 1].split()
        assert json.loads(argv[argv.index("--mcp-config") + 1]) == {"mcpServers": {}}
        assert inv.forensic_mcp is False
        env = inv.env_overlay
        assert env["METASCIENCE_MCP_STAGE"] == "tool_agent"
        assert env["METASCIENCE_RUN_SLUG"] == "sonnet-1"
        assert env["METASCIENCE_PAPER_DIR"] == "/papers/p1"
        assert env["METASCIENCE_MCP_TOOLS"] == "grim_check"

    def test_skill_elsewhere_is_refused_by_name(self, monkeypatch, tmp_path):
        monkeypatch.setenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", "1")
        monkeypatch.setenv("METASCIENCE_GROK_SANDBOX_ROOT", str(tmp_path))
        with pytest.raises(ValueError, match="claude backend only"):
            self._build("skill", backend="grok")

    def test_brief_adds_describe_tool_and_the_server_switch(self):
        inv = self._build("mcp_brief")
        argv = inv.argv
        allowed = argv[argv.index("--allowedTools") + 1].split(",")
        assert agent._mcp("describe_tool") in allowed
        cfg = json.loads(argv[argv.index("--mcp-config") + 1])
        env = cfg["mcpServers"]["forensic_metascience"]["env"]
        assert env["METASCIENCE_MCP_BRIEF"] == "1"
        assert argv[argv.index("--permission-mode") + 1] == "bypassPermissions"

    def test_default_has_neither(self):
        argv = self._build("mcp").argv
        cfg = json.loads(argv[argv.index("--mcp-config") + 1])
        assert "METASCIENCE_MCP_BRIEF" not in cfg["mcpServers"]["forensic_metascience"]["env"]
        assert agent._mcp("describe_tool") not in argv[argv.index("--allowedTools") + 1]


class TestBriefServer:
    @pytest.fixture
    def server(self, monkeypatch):
        import importlib
        import sys
        import forensic_metascience_ai_toolkit
        name = "forensic_metascience_ai_toolkit.mcp_server"
        orig = sys.modules.get(name)
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "tool_agent")
        monkeypatch.setenv("METASCIENCE_MCP_BRIEF", "1")
        sys.modules.pop(name, None)
        yield importlib.import_module(name)
        if orig is not None:
            sys.modules[name] = orig
            forensic_metascience_ai_toolkit.mcp_server = orig

    def test_one_line_descriptions_and_describe_tool(self, server):
        from forensic_metascience_ai_toolkit.registry import BY_NAME
        tools = asyncio.run(server._list_tools())
        by = {t.name: t for t in tools}
        assert by["grim_check"].description == BY_NAME["grim_check"].brief
        assert len(by["grim_check"].description) < len(BY_NAME["grim_check"].description)
        assert "describe_tool" in by
        total = sum(len(t.description) for t in tools)
        assert total < sum(len(BY_NAME[t.name].description)
                           for t in tools if t.name in BY_NAME) / 3

    def test_describe_tool_serves_the_full_text_for_this_surface_only(self, server):
        out = asyncio.run(server._call_tool("describe_tool", {"name": "grim_check"}))
        assert "decimals (int; guard, precision)" in out[0].text
        off = asyncio.run(server._call_tool("describe_tool", {"name": "run_python_script"}))
        assert "no tool named" in off[0].text


class TestLedger:
    def _messages(self, command, result):
        return [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "u1", "name": "Bash",
                 "input": {"command": command}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "u1", "content": result}]}}]

    def test_a_skill_call_is_a_forensic_call(self):
        cmd = """metascience tool run grim_check --json '{"mean": 3.53, "n": 30}'"""
        led = agent._tool_call_ledger(
            self._messages(cmd, 'CONSISTENT: ok\n{"severity": "consistent"}'),
            ["Read", agent._mcp("grim_check")])
        [row] = led
        assert row["tool_short"] == "grim_check" and row["surface"] == "forensic_mcp"
        assert row["validated"] is True and row["via"] == "cli"
        assert row["input"] == {"mean": 3.53, "n": 30}
        assert json.loads(row["result"]) == {"severity": "consistent"}

    def test_anything_more_on_the_line_is_not(self):
        cmd = """metascience tool run grim_check --json '{"mean": 1}' && cat /etc/passwd"""
        [row] = agent._tool_call_ledger(self._messages(cmd, "x"), ["Read"])
        assert row["tool_short"] == "Bash" and row["validated"] is False

    def test_reading_the_manual_is_harness(self):
        [row] = agent._tool_call_ledger(
            self._messages("metascience tool describe grim_check", "..."), ["Read"])
        assert row["surface"] == "harness"


class TestSkillGuard:
    """The real shell fence (skill_guard.py). Measured 2026-10-13: Claude's
    `Bash(metascience tool run *)` pattern let `... && echo PWNED` run."""

    @pytest.mark.parametrize("cmd", [
        "metascience tool run grim_check --json '{\"mean\": 3.53, \"n\": 30}'",
        "metascience tool describe grim_check",
        "metascience tool list",
        "metascience tool list --role tool_agent --json",
    ])
    def test_the_three_shapes_pass(self, cmd):
        from forensic_metascience_ai_toolkit.skill_guard import allowed
        assert allowed(cmd)

    @pytest.mark.parametrize("cmd", [
        "cat /etc/hostname",
        "metascience tool run grim_check --json '{\"mean\": 1}' && echo PWNED",
        "metascience tool run grim_check --json '{}'; rm -rf ~",
        "metascience tool run grim_check --json '{}' | sh",
        "metascience tool run grim_check --json \"{\\\"m\\\": \\\"$(id)\\\"}\"",
        "metascience tool run grim_check --json '{}' > /tmp/x",
        "metascience tool run grim_check --json '[1]'",
        "metascience tool run grim_check --json '{bad'",
        "metascience tool run grim_check --args-file /etc/passwd",
        "metascience tool describe grim_check; id",
        "metascience analyze paper.pdf",
        "metascience tool run grim_check --json '{}'\nid",
    ])
    def test_everything_else_is_refused(self, cmd):
        from forensic_metascience_ai_toolkit.skill_guard import allowed
        assert not allowed(cmd)

    def test_the_hook_blocks_with_exit_2_and_fails_closed(self):
        import subprocess
        import sys
        from forensic_metascience_ai_toolkit import skill_guard
        path = skill_guard.__file__

        def run(stdin):
            return subprocess.run([sys.executable, "-I", path], input=stdin,
                                  capture_output=True, text=True).returncode
        ok = json.dumps({"tool_name": "Bash", "tool_input": {
            "command": "metascience tool describe grim_check"}})
        bad = json.dumps({"tool_name": "Bash", "tool_input": {"command": "id"}})
        assert run(ok) == 0 and run(bad) == 2 and run("not json") == 2
        assert run(json.dumps({"tool_name": "Read", "tool_input": {}})) == 0

    def test_the_skill_launch_carries_the_hook(self):
        inv = agent._build_claude_cmd(
            system_prompt="s", allowed_tools=["Read"], model="sonnet",
            backend="claude", mcp_stage="tool_agent", tool_access="skill")
        settings = json.loads(inv.argv[inv.argv.index("--settings") + 1])
        [entry] = settings["hooks"]["PreToolUse"]
        assert entry["matcher"] == "Bash"
        command = entry["hooks"][0]["command"]
        assert "skill_guard.py" in command and " -I " in command
        assert command.endswith("|| exit 2")
