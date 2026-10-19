"""run_python_script: the science agent's ONLY route to running code.

The contract under test (docs/specs/pipeline.md section 10): scripts persist
before they run, execution is network-off by construction, no sandbox means
NO EXECUTION (a structured refusal, never a bare shell), and the captured
output is the result -- these are the guardrails, so each one gets a test
that proves it can fire.
"""

import subprocess

import pytest

from metascience_agent import run_script as rs


@pytest.fixture(autouse=True)
def fresh_probe(monkeypatch):
    monkeypatch.setattr(rs, "_SANDBOX", None)


@pytest.fixture()
def paper(tmp_path):
    return str(tmp_path)


def _sandboxed():
    return rs._probe_sandbox() != "none"


class TestRefusals:
    def test_empty_code_refuses(self, paper):
        r = rs.run_python_script("", paper_dir=paper)
        assert r["success"] is False and r["refusal"] == "empty_code"

    def test_no_paper_dir_refuses(self, monkeypatch):
        monkeypatch.delenv(rs.PAPER_DIR_ENV, raising=False)
        r = rs.run_python_script("print(1)")
        assert r["refusal"] == "no_paper_dir"

    def test_no_sandbox_means_no_execution(self, paper, monkeypatch, tmp_path):
        monkeypatch.setattr(rs, "_SANDBOX", "none")
        marker = tmp_path / "must_not_exist"
        r = rs.run_python_script(
            f"open({str(marker)!r}, 'w').write('ran')", paper_dir=paper)
        assert r["refusal"] == "code_disabled"
        assert not marker.exists(), "refused code must never run"

    def test_oversized_code_refuses(self, paper):
        r = rs.run_python_script("#" * (rs._MAX_CODE_CHARS + 1), paper_dir=paper)
        assert r["refusal"] == "code_too_large"


@pytest.mark.skipif(not _sandboxed(), reason="no sandbox on this machine")
class TestExecution:
    def test_stdout_is_the_result(self, paper):
        r = rs.run_python_script("print(240 - 12 - 28)", paper_dir=paper)
        assert r["success"] is True and r["returncode"] == 0
        assert r["stdout"].strip() == "200"
        assert r["sandbox"] in ("bwrap", "unshare")

    def test_the_script_is_persisted_before_it_runs(self, paper, tmp_path):
        r = rs.run_python_script("print('x')", label="sum check", paper_dir=paper)
        script = tmp_path / r["script_path"]
        assert script.exists()
        assert script.read_text() == "print('x')"
        assert r["script_path"].startswith(f"{rs.SCRIPTS_DIRNAME}/001_")

    def test_sequence_numbers_increment(self, paper):
        a = rs.run_python_script("print(1)", label="a", paper_dir=paper)
        b = rs.run_python_script("print(2)", label="b", paper_dir=paper)
        assert (a["seq"], b["seq"]) == (1, 2)

    def test_network_is_off(self, paper):
        r = rs.run_python_script(
            "import socket\n"
            "s = socket.socket(); s.settimeout(3)\n"
            "try:\n"
            "    s.connect(('1.1.1.1', 80))\n"
            "    print('CONNECTED')\n"
            "except OSError as e:\n"
            "    print('BLOCKED', type(e).__name__)\n",
            paper_dir=paper)
        assert r["success"] is True
        assert "CONNECTED" not in r["stdout"]
        assert "BLOCKED" in r["stdout"]

    def test_failure_is_reported_not_hidden(self, paper):
        r = rs.run_python_script("raise ValueError('bad denominator')",
                                 paper_dir=paper)
        assert r["success"] is False and r["returncode"] != 0
        assert "bad denominator" in r["stderr"]

    def test_timeout_kills_and_says_so(self, paper):
        r = rs.run_python_script("import time; time.sleep(60)",
                                 timeout_seconds=1, paper_dir=paper)
        assert r["timed_out"] is True and r["success"] is False

    def test_output_is_capped_with_a_named_truncation(self, paper):
        r = rs.run_python_script("print('y' * 200_000)", paper_dir=paper)
        assert r["stdout_truncated"] is True
        assert "truncated" in r["stdout"]

    def test_paper_dir_env_is_honored(self, paper, monkeypatch):
        monkeypatch.setenv(rs.PAPER_DIR_ENV, paper)
        r = rs.run_python_script("print('ok')")
        assert r["success"] is True


@pytest.mark.skipif(rs._probe_sandbox() != "bwrap",
                    reason="filesystem confinement needs bwrap")
class TestBwrapConfinement:
    def test_the_real_filesystem_is_read_only_inside(self, paper):
        # NOT under /tmp: bwrap gives the sandbox a private throwaway tmpfs
        # there (see the next test), so the escape probe must target a path
        # that exists on the REAL filesystem.
        import os
        from pathlib import Path
        victim = Path.home() / f".rs_escape_probe_{os.getpid()}.txt"
        try:
            r = rs.run_python_script(
                f"open({str(victim)!r}, 'w').write('escaped')", paper_dir=paper)
            assert r["success"] is False
            assert not victim.exists(), "writes outside the scripts dir must fail"
        finally:
            victim.unlink(missing_ok=True)

    def test_tmp_is_a_private_tmpfs_not_the_real_one(self, paper):
        # Probe the sandbox's explicit /tmp mount, even when pytest uses a
        # different disk through TMPDIR or --basetemp.
        from pathlib import Path
        from uuid import uuid4

        victim = Path("/tmp") / f"metascience-tmpfs-probe-{uuid4().hex}.txt"
        try:
            r = rs.run_python_script(
                f"open({str(victim)!r}, 'w').write('private'); print('WROTE')",
                paper_dir=paper)
            assert r["success"] is True and "WROTE" in r["stdout"]
            assert not victim.exists(), "the write must not reach the real /tmp"
        finally:
            victim.unlink(missing_ok=True)

    def test_the_workdir_is_writable(self, paper):
        r = rs.run_python_script(
            "open('scratch.txt', 'w').write('fine'); print(open('scratch.txt').read())",
            paper_dir=paper)
        assert r["success"] is True and "fine" in r["stdout"]


class TestProbe:
    def test_probe_is_cached(self, monkeypatch):
        calls = []
        real = subprocess.run

        def counting(argv, **kw):
            calls.append(argv[0])
            return real(argv, **kw)

        monkeypatch.setattr(rs.subprocess, "run", counting)
        rs._probe_sandbox()
        first = list(calls)
        rs._probe_sandbox()
        assert calls == first, "second probe must hit the cache"


class TestRunScopedScriptsDirectory:
    """`METASCIENCE_RUN_SLUG` keeps two runs on one paper directory apart.

    The sequence number is chosen by COUNTING the scripts already on disk, so
    without scoping two concurrent runs both wrote `001_<label>.py` and the
    second silently replaced the first's code -- under a `.d` workdir both
    sandboxes then executed in. The persisted script is the audit artefact
    behind every `reproduction_kind: "script"` finding.
    """

    def _run(self, monkeypatch, base, slug, code, label):
        monkeypatch.setenv(rs.PAPER_DIR_ENV, str(base))
        if slug is None:
            monkeypatch.delenv(rs.RUN_SLUG_ENV, raising=False)
        else:
            monkeypatch.setenv(rs.RUN_SLUG_ENV, slug)
        return rs.run_python_script(code, label=label)

    def test_unset_keeps_the_flat_layout(self, monkeypatch, tmp_path):
        res = self._run(monkeypatch, tmp_path, None, "print(1)", "demo")
        assert (tmp_path / "analysis_code" / "001_demo.py").exists()
        assert res["script_path"] == "analysis_code/001_demo.py"

    def test_an_empty_slug_does_not_become_a_directory_called_script(
            self, monkeypatch, tmp_path):
        """`_slug("")` returns "script", so the emptiness test must come first
        -- routed through it, an unset variable would put every single-run
        analysis under `analysis_code/script/`."""
        self._run(monkeypatch, tmp_path, "   ", "print(1)", "demo")
        assert (tmp_path / "analysis_code" / "001_demo.py").exists()
        assert not (tmp_path / "analysis_code" / "script").exists()

    def test_two_runs_do_not_overwrite_each_other(self, monkeypatch, tmp_path):
        a = self._run(monkeypatch, tmp_path, "opus-aaaaaaaa", "print('a')", "x")
        b = self._run(monkeypatch, tmp_path, "grok-bbbbbbbb", "print('b')", "x")
        root = tmp_path / "analysis_code"
        assert (root / "opus-aaaaaaaa" / "001_x.py").read_text() == "print('a')"
        assert (root / "grok-bbbbbbbb" / "001_x.py").read_text() == "print('b')"
        # Each counter restarts inside its own directory: both are 001, and
        # that is the point -- the archive flattens the slug away.
        assert a["seq"] == b["seq"] == 1

    def test_script_path_names_the_ARCHIVE_location(self, monkeypatch,
                                                    tmp_path):
        """`write_parallel_outputs` flattens the slug, so the reproduction
        string must not carry it -- it would name a directory that no longer
        exists by the time anyone reads the review."""
        res = self._run(monkeypatch, tmp_path, "opus-aaaaaaaa", "print(1)", "d")
        assert res["script_path"] == "analysis_code/001_d.py"
        assert "opus-aaaaaaaa" not in res["script_path"]

    def test_the_sandbox_workdir_is_scoped_too(self, monkeypatch, tmp_path):
        self._run(monkeypatch, tmp_path, "opus-aaaaaaaa", "print(1)", "x")
        self._run(monkeypatch, tmp_path, "grok-bbbbbbbb", "print(1)", "x")
        root = tmp_path / "analysis_code"
        assert (root / "opus-aaaaaaaa" / "001_x.d").is_dir()
        assert (root / "grok-bbbbbbbb" / "001_x.d").is_dir()
