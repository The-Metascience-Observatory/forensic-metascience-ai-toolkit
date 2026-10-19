"""The register knows a column label is ambiguous and tells nobody.

`col_label_is_unique` is computed correctly for every table cell, and is then
consumed in exactly ONE place -- `group_id`, to decide whether a value's id is
keyed by its label or by its ordinal. That is a good use of the fact. It is not
the only one it is needed for.

WHY IT MATTERS, in `jats._header_depth`'s own words: when two columns carry the
same label, "a mean drawn from one and an `n` from another are
indistinguishable afterwards, and GRIM on that pair calls an honest paper
impossible." The register holds exactly the fact that would warn a reader, and
drops it.

MEASURED 2026-08-21 over the eleven-paper corpus: 971 of 1,907 PDF-supplement
groups (50.9%) sit under a non-unique column label, against 129 of 2,523 (5.1%)
for main-article tables. Per COLUMN the supplement figure is 18.6% -- the
duplicate-labelled columns are the data-dense ones, so the per-cell exposure is
roughly twice the per-column rate, and the per-cell number is the one that
matters because risk scales with values, not headings.

SURFACED, NOT GATED. Suppressing checks on these groups would trade a possible
false accusation for a certain false all-clear, and the cardinal rule ranks
those the other way round only when the suppression is PROVEN unnecessary.
Telling the reader costs nothing and decides nothing.
"""
import pathlib
import pytest

from metascience_agent import values as V

CORPUS = pathlib.Path("tests/fixtures/papers/high_value_pdfs_to_run_on")


class TestAnAmbiguousColumnIsRecorded:
    def _reg(self, groups):
        return {"groups": groups}

    def test_it_counts_groups_under_a_repeated_label(self):
        reg = self._reg([
            {"anchor": {"where": "table", "table": "T1", "col_label": "p",
                        "col_label_is_unique": False}},
            {"anchor": {"where": "table", "table": "T1", "col_label": "p",
                        "col_label_is_unique": False}},
            {"anchor": {"where": "table", "table": "T1", "col_label": "n",
                        "col_label_is_unique": True}},
        ])
        out = V.ambiguous_columns(reg)
        assert out["n_groups"] == 2
        assert out["n_groups_total"] == 3

    def test_it_names_the_tables_so_a_reader_can_look(self):
        reg = self._reg([
            {"anchor": {"where": "table", "table": "Table 4", "col_label": "p",
                        "col_label_is_unique": False}},
        ])
        out = V.ambiguous_columns(reg)
        assert "Table 4" in str(out["tables"])

    def test_a_clean_register_says_zero_not_nothing(self):
        """Zero is an answer. Absence of the key would be the absence-as-
        knowledge failure this function exists to report against."""
        out = V.ambiguous_columns(self._reg([
            {"anchor": {"where": "table", "table": "T", "col_label": "n",
                        "col_label_is_unique": True}}]))
        assert out["n_groups"] == 0 and "share" in out

    def test_an_unknown_flag_is_not_counted_as_clean(self):
        """A missing `col_label_is_unique` means nobody checked, which is not
        the same as checked-and-unique."""
        out = V.ambiguous_columns(self._reg([
            {"anchor": {"where": "table", "table": "T", "col_label": "n"}}]))
        assert out["n_unknown"] == 1

    @pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus not in this checkout")
    def test_the_real_corpus_reports_a_plausible_share(self):
        d = CORPUS / "10.1001--jamanetworkopen.2023.37679"
        if not d.is_dir():
            pytest.skip("paper not present")
        out = V.ambiguous_columns(V.build_from_paper(d))
        assert out["n_groups"] > 0, "this paper's supplements have repeated labels"
        assert 0.0 <= out["share"] <= 1.0
