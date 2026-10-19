"""An ingested `body.md` must earn its first place in the source chain.

The chain ranks `body.md` first because pre-extracted markdown is "cheapest and
most faithful". That is true of markdown WE wrote, where `jats.py` emitted a
`[Table N: ...]` placeholder and the columns survive in the table objects. It
was inherited, unchecked, by any `body.md` that happened to be on disk.

MEASURED on `benchmarks/paper_reviews/runs/apple_cider`, whose `source.json` records
`source_channel: body_md` with `source_file: null`:

    ingested body.md         41,085 chars   62 duplicated data rows
    our docling extraction   37,857 chars    2 duplicated data rows, 3 tables
"""
from __future__ import annotations

import warnings

import pytest

from forensic_metascience_ai_toolkit.extraction.jats import (
    _ingested_markdown_is_degraded,
    ingested_markdown_degeneracy,
)

# The real shape, from apple_cider: a flattened prose row, then the SAME row
# wrapped in pipes with empty trailing cells.
_REAL_SHAPE = """
Male 40.0 (n=12) 33.3 (n=10) 36.6 (n=11) 43.3 (n=13)
Female 60.0 (n=18) 66.7 (n=20) 63.4 (n=19) 56.7 (n=17)

| Male 40.0 (n=12) 33.3 (n=10) 36.6 (n=11) 43.3 (n=13) |  |  |  |  |
| Female 60.0 (n=18) 66.7 (n=20) 63.4 (n=19) 56.7 (n=17) |  |  |  |  |
"""


class TestTheMeasure:
    def test_it_counts_the_repeated_data_rows(self):
        s = ingested_markdown_degeneracy(_REAL_SHAPE)
        assert s["n_duplicated_data_rows"] == 2

    def test_it_counts_degenerate_pipe_rows(self):
        """`| everything |  |  |  |` is a flattened line wearing a table's
        clothes: it carries no column association at all."""
        assert ingested_markdown_degeneracy(_REAL_SHAPE)["n_degenerate_pipe_rows"] == 2

    def test_a_real_pipe_table_is_not_degenerate(self):
        good = "| Variable | Arm A | Arm B |\n| Male | 40.0 | 33.3 |\n"
        assert ingested_markdown_degeneracy(good)["n_degenerate_pipe_rows"] == 0

    def test_prose_with_few_numbers_is_not_a_data_row(self):
        s = ingested_markdown_degeneracy("We recruited 30 adults.\nWe recruited 30 adults.\n")
        assert s["n_duplicated_data_rows"] == 0

    def test_empty_input_is_all_zeroes_not_an_exception(self):
        for t in ("", None):
            s = ingested_markdown_degeneracy(t)
            assert s["n_duplicated_data_rows"] == 0


class TestTheBarIsDeliberatelyHigh:
    """A linter that fires on ordinary papers gets switched off."""

    def test_our_own_output_is_not_demoted(self):
        """Our docling extraction of the same paper scores 2. The bar must sit
        well above ordinary repetition -- a summary line restating a table row
        is normal scientific writing."""
        assert not _ingested_markdown_is_degraded(
            {"n_duplicated_data_rows": 2, "n_degenerate_pipe_rows": 0,
             "n_table_placeholders": 0})

    def test_the_apple_cider_shape_is_demoted(self):
        assert _ingested_markdown_is_degraded(
            {"n_duplicated_data_rows": 62, "n_degenerate_pipe_rows": 59,
             "n_table_placeholders": 0})

    def test_a_file_observing_our_placeholder_contract_is_never_demoted(self):
        """A placeholder means `jats.py` wrote it and the columns live in the
        table objects. Whatever else it scores, it is ours."""
        assert not _ingested_markdown_is_degraded(
            {"n_duplicated_data_rows": 500, "n_degenerate_pipe_rows": 500,
             "n_table_placeholders": 3})

    @pytest.mark.parametrize("dup,pipes,demote", [
        (9, 0, False), (10, 0, True),        # the duplicated-row bar
        (0, 4, False), (0, 5, True),         # the degenerate-pipe bar
    ])
    def test_the_thresholds_are_where_the_docstring_says(self, dup, pipes, demote):
        assert _ingested_markdown_is_degraded(
            {"n_duplicated_data_rows": dup, "n_degenerate_pipe_rows": pipes,
             "n_table_placeholders": 0}) is demote


class TestTheDemotionIsAnnouncedNotSilent:
    def test_a_demoted_paper_warns(self, tmp_path):
        (tmp_path / "body.md").write_text(_REAL_SHAPE * 40, encoding="utf-8")
        from forensic_metascience_ai_toolkit.extraction import jats
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            jats.paper_text_with_source(tmp_path)
        assert any("repeats its tables" in str(x.message) for x in w)

    def test_with_no_other_source_the_demoted_file_is_used_anyway(self, tmp_path):
        """Returning "" would be the worse bug: every consumer reads an empty
        text as UNKNOWN, so a partly-readable paper would be recorded as one
        that says nothing."""
        (tmp_path / "body.md").write_text(_REAL_SHAPE * 40, encoding="utf-8")
        from forensic_metascience_ai_toolkit.extraction import jats
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            text, source = jats.paper_text_with_source(tmp_path)
        assert text.strip()
        assert source == "body_md_degraded", (
            "the label must carry the demotion into the record")

    def test_a_healthy_body_md_keeps_its_rank_silently(self, tmp_path):
        (tmp_path / "body.md").write_text(
            "Ordinary prose about 3 groups of 30 adults.\n", encoding="utf-8")
        from forensic_metascience_ai_toolkit.extraction import jats
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            text, source = jats.paper_text_with_source(tmp_path)
        assert source == "body_md" and not w
