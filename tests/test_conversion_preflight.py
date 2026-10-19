"""What the model will actually read, reported before anything is spent.

GREG FITZGERALD, 2026-08-27, naming this the project's top priority:

    "I am quite sure that if I was to inspect much of the input of past runs, it
     would be obvious to me that the run was not going to be successful owing to
     the poor quality/organization of the converted files."

The obstacle was never that the information was hard to get -- it is that
nothing counted it at a moment when knowing was still free. `metascience
preflight <corpus>` costs nothing and runs before any paid stage.

ON ITS FIRST RUN over `high_value_pdfs_to_run_on` this row reported that all
twelve papers had never had their markdown materialised, that five of them walk
to zero tables, and that one paper has 41 tables carrying 4 captions between
them. None of that was hidden; none of it was visible either.
"""
from __future__ import annotations

import json

import pytest

from forensic_metascience_ai_toolkit import preflight


def _paper(tmp_path, name, *, channel=None, chars=0):
    d = tmp_path / name
    (d / "markdown").mkdir(parents=True)
    if channel is not None:
        (d / "markdown" / "source.json").write_text(
            json.dumps({"source_channel": channel, "n_chars": chars}),
            encoding="utf-8")
    return d


class TestItReportsRatherThanJudges:
    """The design rule, inherited from `corpus_state.render_diff`: a count whose
    direction is ambiguous must not be rendered as a verdict. `n_tables: 0` can
    mean the article prints none OR that the extractor could not see them, and
    `prepass` already says so in prose it cannot act on."""

    def test_a_row_is_plain_data_with_no_verdict_field(self, tmp_path):
        _paper(tmp_path, "p1", channel="jats_xml", chars=41085)
        row = preflight.conversion_rows(tmp_path)[0]
        assert row[0] == "p1" and row[1] == "jats_xml" and row[2] == 41085
        assert not any(isinstance(v, bool) for v in row), (
            "a boolean in this row would be a verdict, which this deliberately "
            "does not render")

    def test_zero_tables_is_reported_as_zero_not_as_a_problem(self, tmp_path):
        _paper(tmp_path, "p1", channel="jats_xml", chars=100)
        assert preflight.conversion_rows(tmp_path)[0][3] == 0


class TestTheAbsenceIsStatedNotInferred:
    def test_a_paper_never_run_says_so(self, tmp_path):
        """`markdown/` is written at run start, so its absence means "never
        run" -- which is exactly what an operator about to spend money needs
        stated rather than left to inference. Measured 2026-08-28: all 12 papers
        in the working corpus reported this."""
        _paper(tmp_path, "p1")                       # no source.json
        assert preflight.conversion_rows(tmp_path)[0][1] == "never run"

    def test_an_unreadable_paper_does_not_end_the_sweep(self, tmp_path):
        """The operator wants all twelve rows, not the first error."""
        _paper(tmp_path, "a", channel="jats_xml", chars=10)
        _paper(tmp_path, "b", channel="jats_xml", chars=20)
        rows = preflight.conversion_rows(tmp_path)
        assert len(rows) == 2 and [r[0] for r in rows] == ["a", "b"]

    def test_a_corpus_that_is_not_a_directory_returns_nothing(self, tmp_path):
        assert preflight.conversion_rows(tmp_path / "nope") == []


class TestItActuallyReadsTheCorpus:
    """A test on fixtures alone would pass while the function read the wrong
    keys off a real `source.json`. This one reads the repository's own."""

    def test_it_reads_the_fields_a_real_source_json_writes(self):
        import pathlib
        real = pathlib.Path("benchmarks/paper_reviews/runs/apple_cider/paper/markdown/source.json")
        if not real.is_file():
            pytest.skip("no archived run in this checkout")
        doc = json.loads(real.read_text(encoding="utf-8"))
        assert "source_channel" in doc and "n_chars" in doc, (
            "conversion_rows reads these two keys; if they are renamed every "
            "row silently reports 'never run'")

    def test_the_corpus_sweep_runs_and_returns_one_row_per_paper(self):
        import pathlib
        corpus = pathlib.Path("tests/fixtures/papers/high_value_pdfs_to_run_on")
        if not corpus.is_dir():
            pytest.skip("working corpus not in this checkout")
        rows = preflight.conversion_rows(corpus)
        n_dirs = len([d for d in corpus.iterdir() if d.is_dir()])
        assert len(rows) == n_dirs, "a paper dropped out of the sweep silently"
        assert all(len(r) == 8 for r in rows)
