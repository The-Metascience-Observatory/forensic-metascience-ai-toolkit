"""`metascience agreement` published a reproducibility figure from retired runs.

`find_runs` looked only for `findings.json`. The current pipeline writes
`findings.v2.json`. So on a paper carrying runs of both kinds this verb selected
EXCLUSIVELY the retired-schema ones and published a pass@1 bracket about a
pipeline that no longer exists -- CLAUDE.md section 0b implemented as a command.

MEASURED on 10.1002--ajcp.70049 before the fix: three runs used, all schema 1.0,
reported as "ONE RUN SURFACES BETWEEN 37% AND 68% of what the pipeline is
capable of finding on this paper", while `metascience runs` reports 3 current
and 3 stale and the two sets are disjoint.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from forensic_metascience_ai_toolkit.evaluation.agreement import find_runs, from_review_dirs

ROW = {"slug": "s", "title": "t" * 10, "description": "d" * 30,
       "location": "Table 1", "severity": "suspicious"}


def _run(root: pathlib.Path, name: str, filename: str) -> pathlib.Path:
    d = root / name
    d.mkdir(parents=True)
    (d / filename).write_text(json.dumps({"paper_id": "p", "findings": [ROW]}))
    return d


class TestItSeesTheCurrentSchema:
    def test_a_v2_run_is_found(self, tmp_path):
        _run(tmp_path, "review_a", "findings.v2.json")
        assert [d.name for d in find_runs(tmp_path)] == ["review_a"]

    def test_a_v1_only_paper_still_works(self, tmp_path):
        """Archaeology stays possible; it just stops being the default."""
        _run(tmp_path, "old_a", "findings.json")
        _run(tmp_path, "old_b", "findings.json")
        assert len(find_runs(tmp_path)) == 2

    def test_current_runs_are_preferred_outright(self, tmp_path):
        """When both exist the useful answer is about the pipeline in use, and
        the two cannot be compared anyway."""
        _run(tmp_path, "old_a", "findings.json")
        _run(tmp_path, "old_b", "findings.json")
        _run(tmp_path, "new_a", "findings.v2.json")
        assert [d.name for d in find_runs(tmp_path)] == ["new_a"]


class TestItRefusesToCompareAcrossSchemas:
    def test_mixing_is_an_error_not_a_percentage(self, tmp_path):
        a = _run(tmp_path, "v1_run", "findings.json")
        b = _run(tmp_path, "v2_run", "findings.v2.json")
        out = from_review_dirs([a, b])
        assert out["error"] == "mixed_schemas"
        assert "pass_at_1_bracket" not in out

    def test_it_names_which_runs_are_which(self, tmp_path):
        a = _run(tmp_path, "v1_run", "findings.json")
        b = _run(tmp_path, "v2_run", "findings.v2.json")
        out = from_review_dirs([a, b])
        assert out["schemas"] == {"v1_run": "v1", "v2_run": "v2"}
        assert "v1_run" in out["note"] and "v2_run" in out["note"]

    def test_the_note_says_why_rather_than_just_refusing(self):
        """A refusal a reader cannot act on is a dead end."""
        import tempfile
        root = pathlib.Path(tempfile.mkdtemp())
        a = _run(root, "v1_run", "findings.json")
        b = _run(root, "v2_run", "findings.v2.json")
        note = from_review_dirs([a, b])["note"]
        assert "id derivation" in note
        assert "metascience runs" in note

    def test_one_schema_is_compared_normally(self, tmp_path):
        a = _run(tmp_path, "v2_a", "findings.v2.json")
        b = _run(tmp_path, "v2_b", "findings.v2.json")
        out = from_review_dirs([a, b])
        assert out.get("error") is None
        assert "pass_at_1_bracket" in out


CORPUS = (pathlib.Path(__file__).resolve().parents[1]
          / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "10.1002--ajcp.70049")

#: BOTH tests below assert that `find_runs` picks the `gatetest*` runs over the
#: three retired ones beside them -- so the fixture they need is not the paper
#: directory, it is those run directories, and they were NEVER COMMITTED (no
#: `*gatetest*` path exists anywhere in this repository's history). Guarding on
#: `CORPUS.is_dir()` alone made the absence read as an assertion failure
#: claiming `find_runs` is broken, which is our missing fixture reported as the
#: code's defect. Name the real precondition instead.
_GATETEST_RUNS = sorted(CORPUS.glob("forensic_review_gatetest*")) if CORPUS.is_dir() else []


@pytest.mark.skipif(
    not _GATETEST_RUNS,
    reason="the gatetest* reference runs are not in this checkout "
           "(never committed); this asserts which runs are CURRENT and "
           "cannot be answered without them")
class TestOnTheRealPaper:
    def test_it_no_longer_selects_only_retired_runs(self):
        names = [d.name for d in find_runs(CORPUS)]
        assert names, "no runs selected at all"
        assert all("gatetest" in n for n in names), names

    def test_one_current_run_refuses_rather_than_reporting_agreement(self):
        """The honest answer when there is one run, instead of a bracket
        computed from three dead ones."""
        out = from_review_dirs(find_runs(CORPUS))
        assert "NOT an agreement of 100%" in out["note"]
