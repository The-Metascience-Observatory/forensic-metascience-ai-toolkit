"""The internet seam (docs/specs/pipeline.md section 9).

`internet=True` is the science-error agent's variant: the WEB PAIR moves
from the denied list into the built-in tools, and NOTHING else changes.
These tests pin both halves -- the no-internet argv byte-for-byte (the
production sequence every existing stage runs), and the property that the
internet delta is exactly the web pair. Backend shells stay denied on BOTH
variants: code execution is the run_python_script MCP tool, not a shell.
"""

import pytest

from metascience_agent import llm_backend as lb

ARGS = dict(
    system_prompt="SYSTEM", allowed_tools=["mcp__forensic_metascience__x"],
    model="opus", effort="high", mcp_config_json="{}",
)


def claude_argv(**kw):
    return lb.build_invocation(lb.CLAUDE, **{**ARGS, **kw}).argv


class TestClaudeNoInternetPin:
    def test_the_production_argv_is_byte_pinned(self):
        assert claude_argv() == [
            "claude", "-p",
            "--model", "opus",
            "--effort", "high",
            "--mcp-config", "{}",
            "--strict-mcp-config",
            "--allowedTools", "mcp__forensic_metascience__x",
            "--tools", "Read",
            "--disallowedTools",
            "Bash Edit Write NotebookEdit WebFetch WebSearch Task ToolSearch",
            "--append-system-prompt", "SYSTEM",
            "--permission-mode", "bypassPermissions",
            "--output-format", "stream-json",
            "--verbose",
        ]

    def test_internet_defaults_off(self):
        assert claude_argv() == claude_argv(internet=False)


class TestClaudeInternetDelta:
    def test_the_delta_is_exactly_the_web_pair(self):
        off, on = claude_argv(), claude_argv(internet=True)
        assert len(off) == len(on)
        diffs = [(a, b) for a, b in zip(off, on) if a != b]
        assert diffs == [
            ("Read", "Read,WebSearch,WebFetch"),
            ("Bash Edit Write NotebookEdit WebFetch WebSearch Task ToolSearch",
             "Bash Edit Write NotebookEdit Task ToolSearch"),
        ]

    def test_shells_stay_denied_with_internet_on(self):
        on = claude_argv(internet=True)
        denied = on[on.index("--disallowedTools") + 1]
        for shell in ("Bash", "Write", "Edit"):
            assert shell in denied.split()


class TestGrokInternetDelta:
    @pytest.fixture()
    def grok_argv(self, tmp_path, monkeypatch):
        made = []

        def fake_sandbox(**kw):
            d = tmp_path / f"run-{len(made)}"
            d.mkdir()
            made.append(d)
            return d

        monkeypatch.setattr(lb, "_create_grok_sandbox", fake_sandbox)

        def build(**kw):
            inv = lb.build_invocation(
                lb.GROK, **{**ARGS, "mcp_config_json": None,
                            "paper_dir": str(tmp_path)}, **kw)
            return inv.argv

        return build

    def test_the_delta_is_exactly_the_web_pair(self, grok_argv):
        off, on = grok_argv(), grok_argv(internet=True)

        def flag(argv, name):
            return argv[argv.index(name) + 1]

        assert flag(off, "--tools") == "read_file"
        assert flag(on, "--tools") == "read_file,web_search,web_fetch"
        off_denied = set(flag(off, "--disallowed-tools").split(","))
        on_denied = set(flag(on, "--disallowed-tools").split(","))
        assert off_denied - on_denied == {"web_search", "web_fetch"}
        # nothing else about the argv shape moves (paths differ per sandbox)
        strip = {"--prompt-file", "--cwd", "--tools", "--disallowed-tools"}

        def shape(argv):
            out, skip = [], False
            for i, a in enumerate(argv):
                if skip:
                    skip = False
                    continue
                if a in strip:
                    skip = True
                    continue
                out.append(a)
            return out

        assert shape(off) == shape(on)

    def test_shells_stay_denied_with_internet_on(self, grok_argv):
        on = grok_argv(internet=True)
        denied = on[on.index("--disallowed-tools") + 1].split(",")
        assert "run_terminal_cmd" in denied and "write" in denied


class TestGrokEventNames:
    """Ledgers must read identically whichever backend produced them."""

    @pytest.mark.parametrize("grok_name,claude_name", [
        ("read_file", "Read"),
        ("web_search", "WebSearch"),
        ("web_fetch", "WebFetch"),
        ("run_terminal_cmd", "Bash"),   # always a breach; legible as one
        ("write", "Write"),
    ])
    def test_builtins_are_mapped_with_breadcrumbs(self, grok_name, claude_name):
        block = {"type": "tool_use", "name": grok_name, "input": {"q": "x"},
                 "id": "t1"}
        out = lb._rewrite_tool_use(block)
        assert out["name"] == claude_name
        assert out["grok_meta_tool"] == grok_name
        assert block["name"] == grok_name, "the input block must not mutate"

    def test_unknown_names_pass_through(self):
        block = {"type": "tool_use", "name": "spawn_subagent", "input": {}}
        assert lb._rewrite_tool_use(block) is block
