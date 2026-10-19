"""The index counted 13 papers in a 12-paper corpus, and lost a real one.

`_should_descend` treats a directory with "paper-like children" as a folder OF
papers. `_looks_like_paper_leaf` excludes anything `_is_paper_internal`, which
caught `forensic_review*` and a fixed list of names -- but NOT
`bundle_HEAD_<date>`, the second shape a viewer bundle is written as.

MEASURED on the working corpus: that one directory made its PARENT look like a
nest, so `10.1002--eat.24415` -- a paper with EIGHT review runs -- vanished from
the index, `bundle_HEAD_2026-08-12` and `markdown` appeared in its place, and
`corpus-stats` reported "1/13 papers" for a corpus of twelve. Every fire-rate
denominator, `by_journal` and `by_year` count on the page was computed over 13.
"""

from __future__ import annotations

import pathlib

import pytest

from forensic_metascience_ai_toolkit import webapp_index as W
from forensic_metascience_ai_toolkit.report_render import severity_rank

CORPUS = pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/papers/high_value_pdfs_to_run_on"


class TestPaperInternalsAreNotPapers:
    @pytest.mark.parametrize("name", [
        "bundle_HEAD_2026-08-12", "bundle_HEAD_2026-01-01",
        "forensic_review_bundle", "forensic_review_2026-08-13_supp_bundle",
        "markdown", "figures", "panels", "supplementary",
    ])
    def test_it_is_internal(self, name):
        assert W._is_paper_internal(name)

    @pytest.mark.parametrize("name", [
        "10.1002--eat.24415", "10.1073--pnas.0801268105", "some_paper_slug",
    ])
    def test_a_real_slug_is_not_internal(self, name):
        assert not W._is_paper_internal(name)


@pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus not present")
class TestTheCorpusEnumeratesTwelve:
    def test_the_count_is_right(self):
        assert len(list(W.iter_paper_dirs(CORPUS))) == 12

    def test_the_lost_paper_is_back(self):
        names = {d.name for d in W.iter_paper_dirs(CORPUS)}
        assert "10.1002--eat.24415" in names

    def test_no_internal_directory_is_listed_as_a_paper(self):
        names = {d.name for d in W.iter_paper_dirs(CORPUS)}
        assert "bundle_HEAD_2026-08-12" not in names
        assert "markdown" not in names

    def test_a_paper_with_review_runs_is_not_treated_as_a_nest(self):
        paper = CORPUS / "10.1002--eat.24415"
        assert W.looks_like_paper(paper)
        assert not W._should_descend(paper)


class TestSeverityRankUnderstandsBothLadders:
    """v2 severities are INTEGERS, and `SEVERITY_RANK` holds v1 strings, so
    every current-pipeline finding ranked None. `sort_papers` is documented as
    "Worst first... the paper that most needs a human" and was putting papers
    whose only runs are RETIRED at the top of the queue."""

    @pytest.mark.parametrize("s, expected", [
        ("impossible", 0), ("highly_suspicious", 1), ("suspicious", 2),
        ("indeterminate", 3), ("consistent", 4),
    ])
    def test_the_string_ladder_is_unchanged(self, s, expected):
        assert severity_rank(s) == expected

    @pytest.mark.parametrize("n, expected", [
        (9, 0), (8, 0), (7, 1), (5, 1), (4, 2), (3, 2), (2, 3), (1, 4),
    ])
    def test_the_numeric_ladder_maps_onto_it(self, n, expected):
        assert severity_rank(n) == expected

    def test_the_accusatory_boundary_is_preserved(self):
        """`severity9.ACCUSATORY_MIN` is 3, which is where `suspicious`
        begins."""
        from forensic_metascience_ai_toolkit.severity9 import ACCUSATORY_MIN
        assert severity_rank(ACCUSATORY_MIN) == severity_rank("suspicious")
        assert severity_rank(ACCUSATORY_MIN - 1) > severity_rank("suspicious")

    def test_a_numeric_string_from_a_json_round_trip_works(self):
        assert severity_rank("4") == severity_rank(4)

    @pytest.mark.parametrize("bad", [None, "", True, False, 0, "not-a-severity"])
    def test_a_non_severity_still_ranks_none(self, bad):
        """`normalize_severity` maps every unrecognised string onto
        `indeterminate`; ranking a typo as a real verdict is what this
        function's docstring exists to prevent."""
        assert severity_rank(bad) is None
