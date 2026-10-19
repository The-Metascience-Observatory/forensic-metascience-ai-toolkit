"""A band row governs the rows beneath it, and carries their format.

A clinical table is not a flat grid. It prints `Sex, n (%)` or `NIHSS (M, IQR)`
and then the rows that band governs. `celltypes` decides what a cell IS from its
label, so a marker stranded on the band leaves every row under it untyped:

    parse_cell("39 (33.3)", row_label="Male")                    -> ambiguous
    parse_cell("39 (33.3)", row_label="Sex, n (%) | Male")       -> n_percent
    parse_cell("5 (3-11)",  row_label="Day 1")                   -> estimate_ci
    parse_cell("5 (3-11)",  row_label="NIHSS (M, IQR) | Day 1")  -> median_iqr

MEASURED over the eleven-paper run. On `10.1186--s12883-023-03159-w`: 70 rows
parse correctly against 104 marked `ambiguous`, ~250 percentages lost across
five papers. All 74 of that paper's `estimate_ci` groups are really IQRs, so
`check_estimate_ci` was applicable to 74 values it must never run on -- and its
declining to run is also why those 74 are counted `silent`. One defect wearing
three faces: a lost percentage, a mistyped interval, and a silent group.
"""

import pytest

from forensic_metascience_ai_toolkit.extraction.jats import section_bands
from forensic_metascience_ai_toolkit.extraction.supplements_read import _finish
from forensic_metascience_ai_toolkit.tools.celltypes import parse_cell

STRATIFIED = [
    ["Measure", "Drug", "Placebo"],
    ["Sex, n (%)", "", ""],
    ["Male", "39 (33.3)", "41 (35.0)"],
    ["Female", "78 (66.7)", "76 (65.0)"],
    ["NIHSS (M, IQR)", "", ""],
    ["Day 1", "5 (3-11)", "6 (3-11)"],
]

# docling expands a colspan by REPEATING the text; the HTML reader anchor-fills
# it. The same printed band arrives in both shapes and both must be found.
REPEATED = [
    ["Type", "Saline", "Cu"],
    ["A. Control", "A. Control", "A. Control"],
    ["Rect. temp", "36.68", "37.13"],
]


class TestTheBandIsFound:
    def test_a_stub_only_row_that_governs_data(self):
        assert section_bands(STRATIFIED) == {1: "Sex, n (%)", 4: "NIHSS (M, IQR)"}

    def test_a_repeated_span_is_a_band_too(self):
        """BOTH shapes, and the two mechanisms are not in competition.

        This was ceded to `composite.split_sections` for a while, to protect its
        banner detection. MEASURED, and that cut was wrong in both directions:
        on `10.1186--s12883-023-03159-w` composite kept its 14 sections but the
        `(M, IQR)` marker never reached the typer, so all 74 of that paper's
        interquartile ranges stayed typed as confidence intervals. On the Guekht
        paper the fold worked and composite found ZERO sections, because the
        fold had removed the rows before it looked.

        Composite needs the band ROW among the cells; the typer needs the band
        TEXT on the rows beneath. `fold_section_bands` now does both."""
        assert section_bands(REPEATED) == {1: "A. Control"}

    def test_the_band_row_survives_for_composite(self):
        """Removing it deleted composite's input. It is non-numeric, so no check
        consumes it; it is carried for the reader that needs it."""
        from forensic_metascience_ai_toolkit.extraction.jats import fold_section_bands

        body, sections, _kept = fold_section_bands(STRATIFIED, 1)
        assert ["Sex, n (%)", "", ""] in body
        assert sections[0]["label"] == "Sex, n (%)"

    def test_a_list_with_no_data_yields_no_sections(self):
        """An inclusion-criteria table is 23 stub-only rows and no numbers
        anywhere. Without the governs-data brake it reported 23 sections."""
        criteria = [["Criterion"], ["Age 18-85 years"], ["Focal deficit"],
                    ["CT or MRI performed"]]
        assert section_bands(criteria) == {}

    def test_a_row_of_measurements_is_not_a_band(self):
        grid = [["Measure", "A", "B"], ["12.5", "", ""], ["Age", "1", "2"]]
        assert section_bands(grid) == {}

    def test_a_trailing_legend_governs_nothing(self):
        grid = [["Measure", "A"], ["Age", "65"],
                ["+ addition of CL, - without CL", ""]]
        assert section_bands(grid) == {}


class TestTheFormatReachesTheTyper:
    def test_a_percentage_under_a_band_is_recovered(self):
        cells = _finish(STRATIFIED, 1, "T", "", "", "test")["cells"]
        male = next(c for c in cells if c["raw"] == "39 (33.3)")
        assert male["row_label"] == "Sex, n (%) | Male"
        assert parse_cell(male["raw"], row_label=male["row_label"]).percent == 33.3

    def test_an_iqr_is_not_typed_as_a_confidence_interval(self):
        cells = _finish(STRATIFIED, 1, "T", "", "", "test")["cells"]
        day1 = next(c for c in cells if c["raw"] == "5 (3-11)")
        kind = parse_cell(day1["raw"], row_label=day1["row_label"]).kind
        assert kind == "median_iqr", (
            "an interquartile range typed as a confidence interval is a value "
            "check_estimate_ci must never run on")

    def test_without_the_band_both_would_be_wrong(self):
        """Stated as a test so the regression is visible rather than inferred."""
        assert parse_cell("39 (33.3)", row_label="Male").percent is None
        assert parse_cell("5 (3-11)", row_label="Day 1").kind == "estimate_ci"


class TestTheBandLeavesTheBody:
    def test_the_band_row_is_not_a_data_row(self):
        t = _finish(STRATIFIED, 1, "T", "", "", "test")
        assert not any(c["raw"] in ("Sex, n (%)", "NIHSS (M, IQR)")
                       for c in t["cells"])

    def test_the_bands_are_recorded_with_their_printed_row(self):
        """The printed table is not rewritten -- the boundary is recorded, so a
        finding can still be traced to the row the paper printed."""
        t = _finish(STRATIFIED, 1, "T", "", "", "test")
        assert t["sections"] == [{"row": 1, "label": "Sex, n (%)"},
                                 {"row": 4, "label": "NIHSS (M, IQR)"}]

    def test_no_value_is_lost_to_the_band(self):
        t = _finish(STRATIFIED, 1, "T", "", "", "test")
        assert {c["raw"] for c in t["cells"]} == {
            "39 (33.3)", "41 (35.0)", "78 (66.7)", "76 (65.0)",
            "5 (3-11)", "6 (3-11)"}


class TestATableWithNoBandsIsUnchanged:
    def test_plain_table_keeps_its_labels(self):
        grid = [["Measure", "Drug"], ["Age", "65.1"], ["Weight", "70.2"]]
        t = _finish(grid, 1, "T", "", "", "test")
        assert t["sections"] == []
        assert {c["row_label"] for c in t["cells"]} == {"Age", "Weight"}


class TestThePrintedTableStaysWhole:
    """The fold is a VIEW for typing, not an edit to the table.

    A first version dropped band rows from the body, and `get_table`'s `data`
    went from 61 rows to 49 -- breaking the one property `test_table_delivery`
    exists to hold: every number the paper printed is in `data` without the
    caller following a pointer. Same argument as recording a boundary rather
    than cutting the document: a finding has to be traceable to real ink.
    """

    def test_data_keeps_every_printed_row(self):
        t = _finish(STRATIFIED, 1, "T", "", "", "test")
        assert len(t["data"]) == len(STRATIFIED)
        assert ["Sex, n (%)", "", ""] in t["data"]

    def test_rows_keeps_the_band(self):
        t = _finish(STRATIFIED, 1, "T", "", "", "test")
        assert any(r[0] == "NIHSS (M, IQR)" for r in t["rows"])

    def test_the_cells_still_see_the_band(self):
        """Both at once: the table is whole AND the typing is right."""
        t = _finish(STRATIFIED, 1, "T", "", "", "test")
        male = next(c for c in t["cells"] if c["raw"] == "39 (33.3)")
        assert male["row_label"] == "Sex, n (%) | Male"


NESTED = [
    ["Outcome", "CblG (n = 50)", "Ctrl (n = 50)"],
    ["Primary", "", ""],
    ["HT, n (%)", "", ""],
    ["Any", "12 (24)", "9 (18)"],
    ["Secondary", "", ""],
    ["NIHSS (M, IQR)", "", ""],
    ["Day 1", "5 (3-11)", "6 (4-12)"],
]


class TestAParentBandGovernsThroughItsChild:
    """The `governs` brake asks whether a band has a value under it before the
    next band. Right for a trailing legend; wrong for a NESTED heading.
    `Primary` immediately followed by `HT, n (%)` has nothing between them, so
    the range is empty and the parent was dropped.

    CORROBORATED AGAINST THE EXTRACTOR, 2026-08-20. docling carries a
    `row_section` flag on `TableCell` that this walker has never read. Probed on
    `10.1186--s12883-023-03159-w`: on five of that paper's six banded tables
    docling's flags and this inference agree EXACTLY, and on the sixth docling
    additionally marks `Primary` and `Secondary` -- precisely the two nested
    parents this brake rejected. The flag is worth nothing as a SOURCE, since
    the shape rule reproduces it, and a great deal as an independent check on
    the rule's brakes.
    """

    def test_a_nested_parent_is_found(self):
        assert section_bands(NESTED) == {
            1: "Primary", 2: "HT, n (%)", 4: "Secondary", 5: "NIHSS (M, IQR)"}

    def test_the_brake_still_rejects_bands_governing_nothing(self):
        """The case it was built for: an inclusion-criteria table of stub-only
        rows with no data anywhere reported 23 sections without it. Nothing can
        inherit from nothing."""
        assert section_bands([["Var", "A"], ["Note", ""], ["Legend", ""]]) == {}

    def test_inheritance_does_not_CHAIN(self):
        """One level only, and the row two above is excluded.

        The guarantee is NOT "only real bands are admitted" -- a stub row
        immediately above a governing band is indistinguishable from `Primary`
        above `HT, n (%)`, which is the shape this exists to admit. What it
        rules out is a RUN: chaining would let each stub borrow from the next,
        so a title and a note stacked above `Sex, n (%)` would all become bands.
        """
        grid = [["Var", "A"],
                ["two above", ""],
                ["one above", ""],
                ["Sex, n (%)", ""],
                ["Male", "12 (24)"]]
        got = section_bands(grid)
        assert 1 not in got, "the row two above inherits from nothing"
        assert set(got) == {2, 3}

    def test_an_ordinary_single_band_is_unchanged(self):
        assert section_bands([["Var", "A"], ["Sex, n (%)", ""],
                              ["Male", "12 (24)"]]) == {1: "Sex, n (%)"}
