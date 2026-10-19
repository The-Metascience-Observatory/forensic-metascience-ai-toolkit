"""The tool sandbox is what makes a finding traceable to a validated tool.

A pre-sandbox run (tests/fixtures/papers/cerebrolysin_papers/done/10.1002--adbi.202300439,
2026-07-17) made 7 `Bash` calls across its two stages, hand-writing scipy in
`python3 -c` for the two-tailed lifespan p-value and the r-squared arithmetic.
Two of that report's three most prominent findings were computed by
model-written code rather than by a validated tool -- and looked identical in
the report to findings that were not.

That is the failure this config prevents, so the config itself is pinned here.
"""
import ast
import pathlib

import pytest

from metascience_agent.agent import BUILTIN_TOOLS, DENIED_TOOLS, _build_claude_cmd

AGENT_SRC = pathlib.Path(__file__).parent.parent / "src" / "metascience_agent" / "agent.py"


class TestDeniedTools:
    @pytest.mark.parametrize("tool", [
        "Bash",        # arbitrary code: the observed breach
        "ToolSearch",  # loads schemas for tools outside the declared surface
        "Edit", "Write", "NotebookEdit",
        "WebFetch", "WebSearch",   # network
        "Task",                    # spawns an unconstrained subagent
    ])
    def test_escape_hatches_are_denied(self, tool):
        assert tool in DENIED_TOOLS

    def test_only_read_is_built_in(self):
        """Every statistical claim must come from an MCP forensic tool.

        `Read` is required (the sweep reads body.md). Anything else added here
        needs to be justified against the traceability requirement.
        """
        assert BUILTIN_TOOLS == ["Read"]

    def test_denied_and_builtin_do_not_overlap(self):
        assert not (set(BUILTIN_TOOLS) & set(DENIED_TOOLS))


class TestInvocation:
    """`--allowedTools` does NOT restrict under `--permission-mode bypassPermissions`.

    Only `--tools` plus `--disallowedTools` constrains the surface. A run that
    silently loses this is indistinguishable from a validated one in its output,
    which is why it is asserted against the built command rather than the docs.
    """

    def _cmd(self):
        from metascience_agent.agent import STAGE1_TOOLS
        return _build_claude_cmd(
            system_prompt="s", allowed_tools=STAGE1_TOOLS, model="sonnet",
        ).argv

    def test_tools_flag_is_present_and_scoped(self):
        cmd = self._cmd()
        assert "--tools" in cmd
        assert cmd[cmd.index("--tools") + 1] == ",".join(BUILTIN_TOOLS)

    def test_disallowed_tools_flag_is_present(self):
        cmd = self._cmd()
        assert "--disallowedTools" in cmd
        passed = cmd[cmd.index("--disallowedTools") + 1]
        for tool in DENIED_TOOLS:
            assert tool in passed, f"{tool} not passed to --disallowedTools"

    def test_allowedtools_never_contradicts_the_denylist(self):
        """`--allowedTools` is how the MCP forensic tools are permitted.

        It does NOT restrict anything under bypassPermissions, so it is not the
        guard -- `--tools` plus `--disallowedTools` is. What must never happen is
        the two lists disagreeing: a denied tool appearing in the allow list is
        a contradiction that reads as permission at a glance.
        """
        cmd = self._cmd()
        assert "--allowedTools" in cmd, "MCP forensic tools must be permitted"
        allowed = cmd[cmd.index("--allowedTools") + 1]
        for tool in DENIED_TOOLS:
            # substring check is deliberate: the MCP names are prefixed, the
            # built-ins are bare, and either form appearing here is wrong.
            assert f"{tool}," not in allowed and not allowed.endswith(tool), (
                f"{tool} is in --allowedTools AND --disallowedTools"
            )


def test_denied_tools_has_a_stated_reason():
    """A future edit must not quietly shorten this list."""
    tree = ast.parse(AGENT_SRC.read_text(encoding="utf-8"))
    src = AGENT_SRC.read_text(encoding="utf-8")
    # Anchor on the ASSIGNMENT, not the first mention: a comment elsewhere that
    # merely references DENIED_TOOLS would otherwise move the window.
    idx = src.index("DENIED_TOOLS = [")
    preamble = src[max(0, idx - 1200):idx]
    assert "Bash" in preamble and "validated" in preamble, (
        "DENIED_TOOLS must keep its explanatory comment: the list looks arbitrary "
        "without the evidence for why each entry is there."
    )
    assert tree is not None


class TestThePromptNeverGoesOnArgv:
    """Linux caps a SINGLE argument at MAX_ARG_STRLEN -- 32 pages, 128 KB --
    independently of the 2 MB ARG_MAX for the whole vector.

    A paper carrying a 2.1 MB .docx supplement therefore died with
    `OSError: [Errno 7] Argument list too long` at Popen, AFTER a 22-minute
    stage-1 sweep: the run was paid for and produced nothing, and because the
    crash happened before run_meta.json was written there was no record of what
    it had cost.

    The failure was selective in the worst possible way. It cannot happen on a
    small paper, so it never showed up in testing; it happens on papers with
    large supplements, which are precisely the ones where supplement checking
    matters most. The prompt now goes down stdin.
    """

    MAX_ARG_STRLEN = 32 * 4096  # Linux, 4 KB pages

    def _cmd(self):
        from metascience_agent.agent import STAGE1_TOOLS, _build_claude_cmd
        return _build_claude_cmd(
            system_prompt="s" * 5000, allowed_tools=STAGE1_TOOLS, model="sonnet"
        ).argv

    def test_p_is_a_bare_flag_with_no_prompt_after_it(self):
        cmd = self._cmd()
        assert "-p" in cmd
        assert cmd[cmd.index("-p") + 1].startswith("--"), (
            "the token after -p must be the next FLAG; a prompt there is the "
            "128 KB argv bug"
        )

    def test_no_single_argument_approaches_the_kernel_limit(self):
        for arg in self._cmd():
            assert len(arg.encode()) < self.MAX_ARG_STRLEN, arg[:80]

    def test_the_builder_does_not_accept_a_prompt_at_all(self):
        """Not merely unused -- absent, so it cannot be reintroduced by a caller
        that still passes one positionally."""
        import inspect

        from metascience_agent.agent import _build_claude_cmd
        assert "prompt" not in inspect.signature(_build_claude_cmd).parameters

    def test_run_stage_requires_the_prompt_so_it_cannot_be_dropped(self):
        """If stdin were optional, forgetting it would hang the stage: `claude
        -p` reads until EOF."""
        import inspect

        from metascience_agent.agent import _run_stage
        params = inspect.signature(_run_stage).parameters
        assert "prompt" in params
        assert params["prompt"].default is inspect.Parameter.empty


class TestClaudeArgvStaysByteIdentical:
    def test_starts_with_claude_dash_p(self):
        from metascience_agent.agent import STAGE1_TOOLS, _build_claude_cmd
        argv = _build_claude_cmd(
            system_prompt="s", allowed_tools=STAGE1_TOOLS, model="sonnet",
        ).argv
        assert argv[:2] == ["claude", "-p"]
        assert "--verbose" in argv
        assert "--mcp-config" in argv
        assert "--disallowedTools" in argv
        # The space-joined quirk is left untouched on purpose.
        assert argv[argv.index("--disallowedTools") + 1] == " ".join(
            __import__("metascience_agent.agent", fromlist=["DENIED_TOOLS"]).DENIED_TOOLS
        )


class TestGrokInvocation:
    def _inv(self, tmp_path, monkeypatch, allowed=None):
        monkeypatch.setenv("METASCIENCE_GROK_SANDBOX_ROOT", str(tmp_path / "sb"))
        monkeypatch.setenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", "1")
        from metascience_agent.agent import STAGE1_TOOLS, _build_claude_cmd
        return _build_claude_cmd(
            system_prompt="s",
            allowed_tools=allowed or STAGE1_TOOLS,
            model="grok-4.6",
            backend="grok",
        )

    def test_prompt_file_not_on_argv(self, tmp_path, monkeypatch):
        inv = self._inv(tmp_path, monkeypatch)
        assert "--prompt-file" in inv.argv
        assert "-p" not in inv.argv
        # The user prompt is a file, not an argv token. The system prompt
        # still goes on --append-system-prompt, same as Claude.
        assert inv.prompt_path is not None
        joined = " ".join(inv.argv)
        assert "--mcp-config" not in joined
        assert "--disallowedTools" not in inv.argv
        assert "--allowedTools" not in inv.argv

    def test_kebab_denylist_and_meta_tools_not_denied(self, tmp_path, monkeypatch):
        inv = self._inv(tmp_path, monkeypatch)
        assert "--disallowed-tools" in inv.argv
        denied = inv.argv[inv.argv.index("--disallowed-tools") + 1]
        assert "run_terminal_cmd" in denied
        assert "search_tool" not in denied
        assert "use_tool" not in denied
        assert "search_tool" not in inv.argv
        assert "--deny" in inv.argv

    def test_workdir_is_under_the_trusted_root(self, tmp_path, monkeypatch):
        inv = self._inv(tmp_path, monkeypatch)
        root = tmp_path / "sb"
        assert inv.workdir is not None
        assert str(inv.workdir).startswith(str(root))
        assert (inv.workdir / ".grok" / "config.toml").is_file()
        inv.cleanup()
        assert not inv.workdir.exists()

    def test_compat_skills_are_disabled(self, tmp_path, monkeypatch):
        inv = self._inv(tmp_path, monkeypatch)
        assert inv.env_overlay["GROK_CLAUDE_SKILLS_ENABLED"] == "false"
        assert inv.env_overlay["GROK_CURSOR_SKILLS_ENABLED"] == "false"
        inv.cleanup()
