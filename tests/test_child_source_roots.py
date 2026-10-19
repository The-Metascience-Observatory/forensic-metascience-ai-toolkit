"""Every child that imports the toolkit gets BOTH source roots of THIS tree.

MEASURED FAILURE, 2026-10-18: a pinned worktree run (1.83.0) set
PYTHONPATH=<wt>/src:<wt>/copy_paste_detector/src, but the forensic MCP
server's env carried only `<wt>/src`, so the server resolved
`copy_paste_detector` through the editable install's `.pth` -- the shared
Dropbox checkout. A peer change there (`_compat`) killed every tools agent on
grok and claude with `MCPUnavailable` mid-batch. The fix is one helper,
`llm_backend.forensic_pythonpath`; these tests pin that each launch path
(claude MCP config, grok config.toml, codex `-c` env, the codex stdio probe,
the skill launch's `metascience tool run`, the OpenRouter loop, the
deterministic tracks) carries it.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import agent as A
from forensic_metascience_ai_toolkit import llm_backend as lb
from forensic_metascience_ai_toolkit.llm_backend import (
    CLAUDE, CODEX, OPENROUTER, build_invocation, forensic_pythonpath,
)

ROOT = Path(lb.__file__).resolve().parents[2]
SRC = ROOT / "src"
DETECTOR = ROOT / "copy_paste_detector" / "src"
FORENSIC = "mcp__forensic_metascience__grim_check"


def _entries(pythonpath: str) -> list[Path]:
    return [Path(p).resolve() for p in pythonpath.split(os.pathsep) if p]


def _assert_both_roots_first(pythonpath: str) -> None:
    got = _entries(pythonpath)
    assert got[:2] == [SRC.resolve(), DETECTOR.resolve()], pythonpath


class TestHelper:
    def test_this_tree_has_the_detector_beside_it(self):
        # The premise of every other test here: a source checkout (editable
        # or worktree) carries copy_paste_detector/src beside src/.
        assert (DETECTOR / "copy_paste_detector" / "__init__.py").is_file()

    def test_both_roots_of_this_tree_lead(self, monkeypatch):
        monkeypatch.delenv("PYTHONPATH", raising=False)
        _assert_both_roots_first(forensic_pythonpath())
        assert len(_entries(forensic_pythonpath())) == 2

    def test_caller_entries_are_kept_after_ours_without_duplicates(self, tmp_path):
        extra = tmp_path / "image_src"
        inherited = os.pathsep.join([str(DETECTOR), "", str(extra), str(SRC)])
        got = _entries(forensic_pythonpath(inherited))
        assert got == [SRC.resolve(), DETECTOR.resolve(), extra.resolve()]

    def test_an_empty_entry_is_not_inherited(self):
        # "" on PYTHONPATH is the cwd; a paper directory must not become
        # importable through it.
        assert "" not in forensic_pythonpath(os.pathsep).split(os.pathsep)

    def test_known_positive_the_child_imports_this_trees_detector(self, monkeypatch):
        """The real proof, not the string: a child given this env imports
        copy_paste_detector from THIS tree. In a worktree whose editable
        install points at another checkout, `<src>` alone resolves elsewhere
        -- the 2026-10-18 crash."""
        monkeypatch.delenv("PYTHONPATH", raising=False)
        out = subprocess.run(
            [sys.executable, "-c",
             "import copy_paste_detector, forensic_metascience_ai_toolkit;"
             "print(copy_paste_detector.__file__);print(forensic_metascience_ai_toolkit.__file__)"],
            env={**os.environ, "PYTHONPATH": forensic_pythonpath()},
            capture_output=True, text=True, timeout=60, cwd=str(Path("/")),
        )
        assert out.returncode == 0, out.stderr
        detector_file, agent_file = (Path(p).resolve()
                                     for p in out.stdout.split())
        assert DETECTOR.resolve() in detector_file.parents
        assert SRC.resolve() in agent_file.parents


class TestEveryLaunchPath:
    def test_claude_mcp_config(self):
        cfg = json.loads(A._build_mcp_config(paper_dir="/tmp/p", mcp_stage="tool_agent"))
        server = next(iter(cfg["mcpServers"].values()))
        _assert_both_roots_first(server["env"]["PYTHONPATH"])

    def test_grok_config_toml(self, tmp_path, monkeypatch):
        monkeypatch.setenv("METASCIENCE_GROK_SANDBOX_ROOT", str(tmp_path / "gsb"))
        monkeypatch.setenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", "1")
        monkeypatch.delenv("PYTHONPATH", raising=False)
        run_dir = lb._create_grok_sandbox(
            python_executable=sys.executable, paper_dir=tmp_path,
            mcp_stage="tool_agent")
        text = (run_dir / ".grok" / "config.toml").read_text()
        assert f"PYTHONPATH = {lb._toml_str(forensic_pythonpath())}" in text
        _assert_both_roots_first(forensic_pythonpath())

    def test_codex_server_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("METASCIENCE_CODEX_SANDBOX_ROOT", str(tmp_path / "csb"))
        monkeypatch.delenv("PYTHONPATH", raising=False)
        inv = build_invocation(CODEX, system_prompt="s", allowed_tools=[FORENSIC],
                               model="m", effort="high", paper_dir=tmp_path,
                               mcp_stage="tool_agent")
        try:
            env_arg = next(a for a in inv.argv
                           if a.startswith("mcp_servers.forensic_metascience.env="))
            assert f"PYTHONPATH = {lb._toml_str(forensic_pythonpath())}" in env_arg
        finally:
            inv.cleanup()

    def test_codex_stdio_probe(self, monkeypatch):
        seen = {}

        def fake_run(argv, **kw):
            seen.update(kw["env"])
            raise subprocess.SubprocessError("stop here")

        monkeypatch.setattr(lb.subprocess, "run", fake_run)
        with pytest.raises(lb.MCPUnavailable):
            lb._probe_mcp_stdio(sys.executable)
        _assert_both_roots_first(seen["PYTHONPATH"])

    def test_skill_launch_metascience_tool_run(self):
        inv = A._build_skill_cmd(
            CLAUDE, system_prompt="s", allowed_tools=[FORENSIC], model="m",
            json_schema=None, budget_usd=None, effort="high", paper_dir="/tmp/p",
            max_turns=None, internet=False, mcp_stage="tool_agent",
            run_slug=None, mcp_tools=None)
        try:
            _assert_both_roots_first(inv.env_overlay["PYTHONPATH"])
        finally:
            inv.cleanup()

    def test_openrouter_loop_process(self):
        inv = build_invocation(OPENROUTER, system_prompt="s", allowed_tools=[FORENSIC],
                               model="m", effort="high",
                               mcp_config_json=A._build_mcp_config())
        try:
            _assert_both_roots_first(inv.env_overlay["PYTHONPATH"])
            # ...and the server it starts gets the same, via the claude config.
            cfg = json.loads(inv.argv[inv.argv.index("--mcp-config") + 1])
            server = next(iter(cfg["mcpServers"].values()))
            _assert_both_roots_first(server["env"]["PYTHONPATH"])
        finally:
            inv.cleanup()

    def test_deterministic_tracks(self):
        _assert_both_roots_first(A._build_track_env()["PYTHONPATH"])

    def test_raw_track_child(self, monkeypatch, tmp_path):
        import asyncio
        from forensic_metascience_ai_toolkit.modules.raw_data import module as raw
        seen = {}

        async def fake_exec(*argv, **kw):
            seen.update(kw.get("env") or {})
            raise RuntimeError("stop here")

        monkeypatch.setattr(raw.asyncio, "create_subprocess_exec", fake_exec)
        with pytest.raises(RuntimeError, match="stop here"):
            asyncio.run(raw.run_raw_track(tmp_path, timeout_s=5))
        _assert_both_roots_first(seen["PYTHONPATH"])
