"""The environment gate that runs before anything is spent.

The failure this prevents is not a crash -- it is a paid run that looks
complete and checked nothing. A missing `statcheck` returns `success: false`
and an empty result, which reads as "this paper contains no NHST statistics";
missing `python-docx`/`openpyxl` made 56 supplements read as empty while
preflight still said READY.

So the assertions here are mostly about the DIRECTION of failure: the gate
refuses rather than warns, it refuses BEFORE the subprocess is launched, and it
is overridable only deliberately.
"""

import asyncio
import builtins
import importlib

import pytest

from metascience_agent import preflight
from metascience_agent.preflight import (
    PreflightError,
    assert_ready,
    fatal_checks,
    optional_checks,
)


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch):
    """Each test sees a cold cache and no inherited override."""
    monkeypatch.setattr(preflight, "_CACHE", None)
    monkeypatch.delenv("METASCIENCE_SKIP_PREFLIGHT", raising=False)
    monkeypatch.delenv("METASCIENCE_LLM_CLI", raising=False)
    yield
    preflight._CACHE = None


def _break_module(monkeypatch, missing: str) -> None:
    """Make exactly one module unimportable, leaving the rest alone."""
    real = importlib.import_module

    def fake(name, *a, **kw):
        if name == missing:
            raise ImportError(f"No module named {name!r}")
        return real(name, *a, **kw)

    monkeypatch.setattr(preflight.importlib, "import_module", fake)


class TestFatalChecks:
    def test_all_present_in_this_environment(self):
        """The suite itself runs in an environment that must be READY."""
        failures = [n for n, ok, _ in fatal_checks(refresh=True) if not ok]
        assert not failures, f"fatal dependencies missing here: {failures}"

    @pytest.mark.parametrize("mod", ["statcheck", "claude_agent_sdk", "docx", "openpyxl"])
    def test_a_missing_module_is_reported_not_raised(self, monkeypatch, mod):
        """fatal_checks never raises -- the caller decides what failure means."""
        _break_module(monkeypatch, mod)
        rows = fatal_checks(refresh=True)
        assert any(not ok for _, ok, _ in rows)

    def test_claude_cli_absence_is_fatal(self, monkeypatch):
        monkeypatch.setattr(preflight.shutil, "which", lambda _: None)
        rows = dict((n, ok) for n, ok, _ in fatal_checks(refresh=True))
        assert rows["claude CLI"] is False


class TestAssertReady:
    def test_passes_when_environment_is_complete(self):
        assert_ready()

    @pytest.mark.parametrize("mod", ["statcheck", "docx", "openpyxl"])
    def test_raises_when_a_fatal_dependency_is_missing(self, monkeypatch, mod):
        _break_module(monkeypatch, mod)
        with pytest.raises(PreflightError):
            assert_ready()

    def test_the_message_names_what_is_missing(self, monkeypatch):
        """An operator must not have to guess which library to install."""
        _break_module(monkeypatch, "statcheck")
        with pytest.raises(PreflightError, match="statcheck"):
            assert_ready()

    def test_env_var_overrides(self, monkeypatch):
        """A deliberate partial install stays workable."""
        _break_module(monkeypatch, "statcheck")
        monkeypatch.setenv("METASCIENCE_SKIP_PREFLIGHT", "1")
        assert_ready()

    def test_override_is_exact(self, monkeypatch):
        """Only "1" disables the gate; a stray truthy value must not."""
        _break_module(monkeypatch, "statcheck")
        monkeypatch.setenv("METASCIENCE_SKIP_PREFLIGHT", "0")
        with pytest.raises(PreflightError):
            assert_ready()


class TestCaching:
    def test_result_is_cached(self, monkeypatch):
        """_run_stage fires 2-3x per paper; imports must not repeat."""
        calls = []
        real = importlib.import_module

        def counting(name, *a, **kw):
            calls.append(name)
            return real(name, *a, **kw)

        monkeypatch.setattr(preflight.importlib, "import_module", counting)
        fatal_checks(refresh=True)
        first = len(calls)
        fatal_checks()
        fatal_checks()
        assert len(calls) == first, "cached call re-imported modules"

    def test_refresh_bypasses_the_cache(self, monkeypatch):
        """`metascience preflight` asks about NOW, not about import time."""
        fatal_checks(refresh=True)
        _break_module(monkeypatch, "statcheck")
        assert all(ok for _, ok, _ in fatal_checks())          # stale, cached
        assert any(not ok for _, ok, _ in fatal_checks(refresh=True))


class TestOptionalChecks:
    def test_never_appear_in_the_fatal_set(self):
        """R, the PDF renderer and PyMuPDF degrade a run; they never block it."""
        fatal_names = {n for n, _, _ in fatal_checks(refresh=True)}
        for name, _, _ in optional_checks():
            assert name not in fatal_names

    def test_absent_optional_tools_do_not_block(self, monkeypatch):
        monkeypatch.setattr(preflight.shutil, "which",
                            lambda n: None if n in ("Rscript", "wkhtmltopdf", "pandoc")
                            else "/usr/bin/claude")
        _break_module(monkeypatch, "fitz")
        assert_ready()   # must not raise


class TestTheRRowDescribesThePackagesNotTheBinary:
    """`which("Rscript")` is not the capability the cross-check needs.

    MEASURED: on a machine with R but without `scrutiny`, this row read
    `R (cross-checks) | OK | present` while every `r_grim_ground_truth` call
    returned an empty error. The prompts require a cross-check before any GRIM
    `impossible` is published, so the gate advertised a confirming engine that
    could not run, and real `impossible` findings were downgraded across a
    corpus. A check that reports a capability the machine lacks is worse than
    no check at all.
    """

    @staticmethod
    def _row():
        return next(r for r in optional_checks() if r[0] == "R (cross-checks)")

    def _fake_probe(self, monkeypatch, *, installed: set[str]):
        monkeypatch.setattr(preflight.shutil, "which",
                            lambda n: "/usr/bin/Rscript" if n == "Rscript"
                            else "/usr/bin/x")

        class _Done:
            def __init__(self, out): self.stdout = out
        def run(cmd, **kw):
            pkg = next(p for p in preflight._R_PACKAGES if p in cmd[-1])
            return _Done("TRUE" if pkg in installed else "FALSE")
        monkeypatch.setattr(preflight.subprocess, "run", run)

    def test_rscript_present_but_package_missing_is_not_ok(self, monkeypatch):
        self._fake_probe(monkeypatch, installed={"rsprite2"})
        name, ok, detail = self._row()
        assert ok is False, "a missing package must not report OK"
        assert detail != "present"
        assert "scrutiny" in detail
        assert "install.packages" in detail

    def test_all_packages_present_is_ok(self, monkeypatch):
        self._fake_probe(monkeypatch, installed={"scrutiny", "rsprite2"})
        _, ok, detail = self._row()
        assert ok is True
        assert "scrutiny" in detail and "rsprite2" in detail

    def test_a_missing_package_still_does_not_block(self, monkeypatch):
        """Non-fatal by design: it degrades a run, it does not make it wrong."""
        self._fake_probe(monkeypatch, installed=set())
        assert_ready()   # must not raise

    def test_missing_package_names_the_tools_it_disables(self, monkeypatch):
        self._fake_probe(monkeypatch, installed=set())
        _, _, detail = self._row()
        assert "r_grim_ground_truth" in detail
        assert "r_sprite_ground_truth" in detail


class TestSupplementIntegrityRow:
    """The auditor exists because a corpus held 30 git-lfs pointer stubs where
    its supplements should have been, every oid matching the manifest, and
    nothing noticed -- integrity metadata was written, never read back. The
    row must be honest in BOTH import states: present says where the audit
    runs, absent NAMES the standalone command. A silent absence here is the
    original defect wearing preflight's clothes.
    """

    NAME = "fetchpdf-verify (supplement integrity)"

    def _row(self):
        return next(r for r in optional_checks() if r[0] == self.NAME)

    def test_absent_names_the_standalone_command(self, monkeypatch):
        _break_module(monkeypatch, "fetchpdf.retrieval.verify")
        _, ok, detail = self._row()
        assert ok is False
        assert "fetchpdf-verify" in detail, "a named absence, never silence"

    def test_present_says_where_the_audit_runs(self, monkeypatch):
        real = importlib.import_module

        def fake(name, *a, **kw):
            if name == "fetchpdf.retrieval.verify":
                return object()
            return real(name, *a, **kw)

        monkeypatch.setattr(preflight.importlib, "import_module", fake)
        _, ok, detail = self._row()
        assert ok is True
        assert "batch" in detail, "the operator must learn what consumes it"

    def test_absence_never_blocks(self, monkeypatch):
        """Best-effort by contract: verify informs a run, it never blocks one."""
        _break_module(monkeypatch, "fetchpdf.retrieval.verify")
        assert_ready()   # must not raise


class TestTheGateRunsBeforeTheSpend:
    """The whole point: refuse BEFORE `claude` is launched, not after."""

    def test_run_stage_aborts_without_launching_a_subprocess(self, monkeypatch):
        from metascience_agent import agent

        launched = []

        async def fake_exec(*a, **kw):
            launched.append(a)
            raise AssertionError("subprocess launched despite failed preflight")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        monkeypatch.setattr(agent, "_assert_ready",
                            lambda *a, **k: (_ for _ in ()).throw(PreflightError("boom")))

        with pytest.raises(PreflightError):
            asyncio.run(agent._run_stage(["claude", "-p", "x"], "a prompt"))
        assert not launched

    def test_it_precedes_the_usage_guard(self, monkeypatch):
        """The free local check runs before the network probe."""
        from metascience_agent import agent

        order = []

        async def fake_guard(*a, **k):
            order.append("usage")

        monkeypatch.setattr(agent, "usage_guard", fake_guard)
        monkeypatch.setattr(agent, "_assert_ready",
                            lambda *a, **k: order.append("preflight"))

        async def fake_exec(*a, **kw):
            raise RuntimeError("stop here")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        with pytest.raises(RuntimeError):
            asyncio.run(agent._run_stage(["claude", "-p", "x"], "a prompt"))
        assert order == ["preflight", "usage"]


class TestBatchRunnerTreatsItAsEnvironmentFault:
    def test_preflight_error_is_not_a_retryable_paper(self):
        """It must not land in failed.jsonl: retrying cannot install a library.

        Checked by reading the source, as the batch runner is a script with a
        heavy import surface -- the same approach `test_tool_exposure.py` takes
        for the MCP layer.
        """
        from pathlib import Path

        import re

        src = (Path(__file__).resolve().parents[1]
               / "src" / "metascience_agent" / "batch.py").read_text()
        # Matched by SHAPE, not by the tuple's exact text: the tuple grows as
        # new environment faults are found (BackendUnavailable joined it
        # 2026-08-23 after an exhausted API balance filled failed.jsonl with
        # ten papers that were never analysed). Pinning the literal made this
        # test fail on the addition rather than on a regression.
        m = re.search(r"except \(PreflightError[^)]*\)", src)
        assert m, "the environment-fault handler is gone"
        members = m.group(0)
        assert "BudgetUnsupported" in members
        assert "BackendUnavailable" in members, (
            "an exhausted API balance would be recorded as a per-paper failure"
        )
        handler = src[m.end():].split("except WeeklyLimitReached")[0]
        assert "_append_jsonl" not in handler, (
            "an environment fault is being recorded as a per-paper failure"
        )
        assert "raise" in handler, "PreflightError must stop the batch"
