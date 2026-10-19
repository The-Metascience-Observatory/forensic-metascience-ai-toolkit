"""A report has to say what produced it, and the number has to mean something.

Before this, `report.md` and `report.pdf` carried NO date and NO version. The
number they would have carried was a hardcoded `0.1.0` declared independently in
`pyproject.toml` and `__init__.py` -- free to disagree -- never bumped, with no
tags and no changelog. Two reports produced a month and forty commits apart were
indistinguishable, which is why the three archived same-paper repeat sets cannot
serve as the run-to-run noise floor the cheaper-model study is gated on: a
difference between two runs cannot be attributed to chance rather than to a
commit landing between them.

Three properties are pinned here:

1. ONE SOURCE OF TRUTH. `version.py` declares the number; `pyproject.toml` reads
   it. A test, not a convention, is what keeps them equal.
2. THE STRING IS THE COMPOSITE. Release number AND git sha AND dirty flag. The
   release number moves monthly and the code moves daily, so the release number
   alone does not identify a run; a sha from a dirty tree identifies code that
   exists on one machine.
3. A MISSING FACT READS AS MISSING. An archived run that recorded no date must
   not borrow today's, and a file mtime offered in place of a run date must say
   on the page that that is what it is.
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from metascience_agent import __version__
from metascience_agent.report_render import resolve_run_stamp
from metascience_agent.version import NOT_RECORDED, git_state, pipeline_version

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
VERSION_PY = (Path(__file__).resolve().parents[1]
              / "src" / "metascience_agent" / "version.py")


def _report():
    return {
        "verdict": "unresolved", "confidence": "low",
        "headline": {"title": "h", "severity": "suspicious", "statement": "s"},
        "findings": [], "not_checked": [], "limitations": [],
        "coverage_summary": {"stats_found": 0, "stats_checked": 0},
    }


class TestOneSourceOfTruth:
    """The number was declared in two files. Two declarations is one drift."""

    def test_pyproject_does_not_declare_its_own_version(self):
        text = PYPROJECT.read_text()
        assert 'dynamic = ["version"]' in text
        assert not re.search(r'^version\s*=\s*"', text, flags=re.MULTILINE), (
            "a literal version in pyproject.toml can drift from version.py; "
            "hatchling must read it from the module instead")

    def test_pyproject_points_at_version_py(self):
        text = PYPROJECT.read_text()
        assert "[tool.hatch.version]" in text
        assert 'path = "src/metascience_agent/version.py"' in text

    def test_version_py_is_the_declaration(self):
        assert re.search(r'^__version__ = "', VERSION_PY.read_text(), flags=re.MULTILINE)

    def test_the_changelog_documents_this_version(self):
        """A number nobody wrote a rule for means nothing. The bump rules live in
        CHANGELOG.md and the current version has to appear there, or the number
        is again a decoration."""
        text = CHANGELOG.read_text()
        assert f"[{__version__}]" in text, (
            f"{__version__} has no CHANGELOG entry -- bump the version and the "
            "changelog in the same commit, or the number is attached to the "
            "wrong runs")
        for rule in ("MAJOR", "MINOR", "PATCH"):
            assert rule in text, "the bump rules must be written down"


class TestTheStringIsTheComposite:
    """A release number alone does not identify a run."""

    CLEAN = {"version": "0.2.0", "git_sha": "1a2b3c4d5e6f", "git_dirty": False}

    def test_a_clean_tree_names_the_release_and_the_commit(self):
        assert pipeline_version(self.CLEAN) == "v0.2.0 (g1a2b3c4d5e6f)"

    def test_a_dirty_tree_says_so(self):
        """A sha from a tree with uncommitted edits identifies code that exists
        nowhere but that machine. Printing it bare would assert reproducibility
        the run does not have."""
        got = pipeline_version({**self.CLEAN, "git_dirty": True})
        assert got == "v0.2.0 (g1a2b3c4d5e6f, uncommitted changes)"

    @pytest.mark.parametrize("dirty", ["unknown", None])
    def test_a_dirty_probe_that_could_not_run_is_not_reported_clean(self, dirty):
        """THE THIRD STATE. Collapsing "the check said clean" into "the check
        failed" publishes our own failure as a fact about the code that ran."""
        got = pipeline_version({**self.CLEAN, "git_dirty": dirty})
        assert "tree state unknown" in got
        assert "uncommitted" not in got

    def test_no_sha_recorded_says_so_once(self):
        assert pipeline_version({"version": "0.2.0"}) == f"v0.2.0 (commit {NOT_RECORDED})"

    def test_a_run_that_recorded_nothing_does_not_borrow_todays_version(self):
        """Re-rendering an archived review must not stamp it with the version of
        the code doing the re-rendering -- that is a fabrication about a document
        produced by different code."""
        got = pipeline_version({})
        assert __version__ not in got
        assert got == f"version {NOT_RECORDED}"

    def test_no_argument_describes_the_running_code(self):
        got = pipeline_version()
        assert got.startswith(f"v{__version__}")

    def test_git_state_reports_sha_and_dirty_together(self):
        """A `git_sha` with no `git_dirty` beside it is a sha whose meaning is
        unknown. They must arrive as a pair or not at all."""
        st = git_state()
        if "git_sha" in st:
            assert len(st["git_sha"]) == 12
            assert "git_dirty" in st, "a sha without a dirty flag says nothing"
            assert st["git_dirty"] in (True, False, "unknown")

    def test_git_state_never_raises_without_a_repo(self):
        """It is bookkeeping. A failure here must not cost a paid analysis."""
        with tempfile.TemporaryDirectory() as d:
            assert git_state(Path(d)) == {} or "git_sha" not in git_state(Path(d))


class TestTheFileDateIsNotPassedOffAsARunDate:
    """The one inference in the whole stamp, and it is labelled on the page.

    A review produced before `_run_stamp` existed has no `analysed_at`, and the
    only date left is the mtime of `run_meta.json`. That is a FILE date: the two
    diverge the moment the directory is copied, and this corpus lives in Dropbox.
    """

    @pytest.fixture
    def legacy(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "run_meta.json"
            p.write_text(json.dumps({"paper_id": "old", "mode": "two_stage"}))
            os.utime(p, (1754708000, 1754708000))
            yield Path(d)

    def test_the_mtime_is_offered(self, legacy):
        stamp = resolve_run_stamp(json.loads((legacy / "run_meta.json").read_text()), legacy)
        assert stamp["analysed_at"].startswith("2025-08-")
        assert stamp["analysed_at_source"] == "file_mtime"

    def test_no_review_dir_means_no_guess(self, legacy):
        """Without a directory there is nothing to stat, and inventing a date
        would be worse than admitting there isn't one."""
        stamp = resolve_run_stamp({"paper_id": "old"}, None)
        assert stamp["analysed_at"] is None
        assert stamp["analysed_at_source"] is None


def test_the_cli_prints_the_composite():
    """`metascience version` is how you check whether a report came from this
    checkout, so it has to print the same string the report stamps."""
    out = subprocess.run(
        [os.environ.get("PYTHON", "python3"), "-m", "metascience_agent.cli", "version"],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(["src", "copy_paste_detector/src"])},
        cwd=Path(__file__).resolve().parents[1], timeout=120,
    )
    assert out.returncode == 0, out.stderr
    assert f"v{__version__}" in out.stdout
