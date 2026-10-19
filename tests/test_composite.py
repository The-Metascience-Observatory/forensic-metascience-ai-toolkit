"""Composite tables: several logical tables printed as one, and the denominator
that only exists once you split them.

Found by Greg 2026-08-10 in a real bundle. Journals print a banner row repeating
a section name across every column -- Gender, Age group, Ethnic group, Marital
status -- and a human reads four tables where the pipeline read one.
"""
from pathlib import Path

import pytest

from metascience_agent.composite import split_sections

PAPER = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1038--s41537-025-00576-3/"
             "forensic_review_opus_08_09_2026_bundle/paper/"
             "10.1038--s41537-025-00576-3.xml")


def _banner(label, ncols=3, row=0):
    return [{"raw": label, "row": row, "row_label": label, "col_label": f"c{i}"}
            for i in range(ncols)]


def _row(label, vals, row):
    return [{"raw": v, "row": row, "row_label": label, "col_label": f"c{i}"}
            for i, v in enumerate(vals)]


class TestSplitting:
    def test_a_table_with_no_banner_is_one_section(self):
        """Callers must not need a special case for the ordinary table."""
        secs = split_sections(_row("Age", ["1 (50.00)", "1 (50.00)"], 0))
        assert len(secs) == 1 and secs[0]["label"] is None

    def test_a_one_column_table_has_no_banners(self):
        """Every cell trivially equals the row label when there is one column.
        Treating that as a banner would delete the table."""
        cells = [{"raw": "Gender", "row": 0, "row_label": "Gender", "col_label": "c0"}]
        assert len(split_sections(cells)) == 1
        assert split_sections(cells)[0]["cells"], "the row must survive"

    def test_banner_rows_start_sections_and_are_not_data(self):
        cells = (_banner("Gender", 2, 0)
                 + _row("Female", ["1 (50.00)", "1 (50.00)"], 1)
                 + _row("Male", ["1 (50.00)", "1 (50.00)"], 2)
                 + _banner("Age group", 2, 3)
                 + _row("Young", ["2 (100.00)", "2 (100.00)"], 4))
        secs = split_sections(cells)
        assert [s["label"] for s in secs] == ["Gender", "Age group"]
        assert all("Gender" not in [str(c["raw"]) for c in secs[0]["cells"]]
                   for _ in [0]), "the banner is not data"


class TestTheDenominatorIsVerifiedNotGuessed:
    """A denominator we inferred and could not confirm is worth LESS than none:
    a wrong n is the fastest route to a false `impossible`."""

    def test_counts_that_reproduce_the_printed_percentages_are_accepted(self):
        secs = split_sections(_row("Female", ["1254 (44.31)"], 0)
                              + _row("Male", ["1576 (55.69)"], 1))
        info = secs[0]["n_by_column"]["c0"]
        assert info["n"] == 2830
        assert "percentages" in info["n_source"]

    def test_a_missing_row_is_refused_not_averaged(self):
        """Percentages summing to 82.5 mean a row is missing. This exact case
        caught a truncation error during development, before it reached a tool."""
        secs = split_sections(_row("Single", ["848 (29.96)"], 0)
                              + _row("Married", ["1154 (40.78)"], 1)
                              + _row("Divorced", ["334 (11.80)"], 2))
        info = secs[0]["n_by_column"]["c0"]
        assert info["n"] is None
        assert "sum to" in info["why_not"] and "not 100" in info["why_not"]

    def test_a_header_n_that_disagrees_rejects_the_column(self):
        """Two sources for one denominator that differ mean we understand
        neither, so neither is used."""
        cells = ([{"raw": "1254 (44.31)", "row": 0, "row_label": "F",
                   "col_label": "Group (n = 9999)"}]
                 + [{"raw": "1576 (55.69)", "row": 1, "row_label": "M",
                     "col_label": "Group (n = 9999)"}])
        info = split_sections(cells)[0]["n_by_column"]["Group (n = 9999)"]
        assert info["n"] is None and "9999" in info["why_not"]

    def test_a_header_n_that_agrees_is_recorded_as_double_confirmation(self):
        cells = ([{"raw": "1254 (44.31)", "row": 0, "row_label": "F",
                   "col_label": "Group (n = 2830)"}]
                 + [{"raw": "1576 (55.69)", "row": 1, "row_label": "M",
                     "col_label": "Group (n = 2830)"}])
        info = split_sections(cells)[0]["n_by_column"]["Group (n = 2830)"]
        assert info["n"] == 2830 and "header_n" in info["n_source"]

    def test_no_single_n_is_offered_when_columns_disagree(self):
        """Several columns means several populations. Returning one `n` would
        invite the wrong-denominator pairing this module exists to prevent."""
        secs = split_sections(_row("F", ["1254 (44.31)", "646 (49.96)"], 0)
                              + _row("M", ["1576 (55.69)", "647 (50.04)"], 1))
        s = secs[0]
        assert s["n"] is None
        assert len([v for v in s["n_by_column"].values() if v.get("n")]) == 2


@pytest.mark.skipif(not PAPER.exists(), reason="corpus paper not present")
class TestTheRealTable:
    """MEASURED on 10.1038/s41537-025-00576-3 Table 2 before this module
    existed: 73 rows, 12 banners consuming 72 of 389 cells, and `check_table`
    ran 0 checks while refusing all 389 -- 244 for want of an n that the section
    structure makes recoverable."""

    def _sections(self):
        from metascience_agent.extraction.jats import extract_xml_tables
        return split_sections(extract_xml_tables(PAPER)[1]["cells"])

    def test_it_finds_the_twelve_sections(self):
        secs = self._sections()
        assert len(secs) == 12
        assert [s["label"] for s in secs][:4] == [
            "Gender", "Age group", "Ethnic group", "Marital status"]

    def test_it_recovers_the_denominators_the_dispatcher_was_refusing_for(self):
        secs = self._sections()
        blocks = [v for s in secs for v in s["n_by_column"].values()]
        verified = [v for v in blocks if v.get("n")]
        assert len(verified) >= 40, f"only {len(verified)} of {len(blocks)}"
        overall = secs[0]["n_by_column"]["Overall, n (%)"]
        assert overall["n"] == 2830

    def test_the_column_header_n_confirms_the_derivation_independently(self):
        secs = self._sections()
        col = next(k for k in secs[0]["n_by_column"] if "Low-risk" in k)
        info = secs[0]["n_by_column"][col]
        assert info["n"] == 1293
        assert "header_n" in info["n_source"], "the printed n = 1293 must be checked"


class TestARowOfMissingMarkersIsNotASectionHeading:
    """`_is_banner` fires when every cell of a row carries the same non-numeric
    text. extraction/jats.py drops the label column and skips empty cells, so a
    real data row `Comorbidity | NR | NR | NR` arrives as three identical
    non-numeric cells -- and was classified as a banner. Its data was dropped
    from the section entirely and a section LABELLED "NR" was opened and
    published. Section membership gates denominator recovery, so the loss
    reaches grim_percentage and check_count_percent.
    """

    @staticmethod
    def _row(*vals, r=0):
        return [{"raw": v, "row": r, "col": i} for i, v in enumerate(vals)]

    def test_a_repeated_missing_marker_is_not_a_banner(self):
        from metascience_agent.composite import _is_banner
        for marker in ("NR", "n/a", "Not reported", "None", "--", "—",
                       "ND", "missing", "?"):
            assert not _is_banner(self._row(marker, marker, marker)), marker

    def test_a_real_group_heading_still_is_one(self):
        from metascience_agent.composite import _is_banner
        assert _is_banner(self._row("Demographics", "Demographics"))

    def test_the_data_row_stays_in_its_section(self):
        """The consequence: no section labelled "NR", and the row's cells are
        still counted."""
        from metascience_agent.composite import split_sections
        cells = (self._row("Demographics", "Demographics", r=0)
                 + self._row("NR", "NR", "NR", r=1)
                 + self._row("Age", "41", "39", r=2))
        secs = split_sections(cells)
        assert [s["label"] for s in secs] == ["Demographics"]
        assert len(secs[0]["cells"]) == 6

    def test_the_viewer_uses_the_same_rule(self):
        """bundle.py re-implements the banner test over the RENDERED row, which
        still carries the label column. When the two disagree the viewer
        redraws rows the analysis never saw, so they are kept in step."""
        import inspect
        from metascience_agent import bundle
        src = inspect.getsource(bundle)
        assert "_is_missing_marker" in src
