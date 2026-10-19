"""
A table whose header is two rows deep must be read as two rows.

The reason is not tidiness. A cell with `colspan > 1` spans columns that its own
row cannot tell apart, so the labels those columns actually have live in the row
BELOW it. Reading such a table with a one-row header gives several columns the
same label -- `10.1166--jnn.2011.5114` prints `Control | Heat stress` over
`Saline / Cu / Ag`, and the one-row reading calls three different treatment arms
`Control`. A mean taken from one arm and an `n` taken from another are then
indistinguishable, and GRIM on that pair reports an impossible value against a
paper that printed nothing of the kind.

It also hides the `n`. `values.design_values_from_cells` records that "0 of 20
cells carried a `col`" on `10.1007--s00702-004-0248-2`; the cause is here.
`Placebo (n = 68)` sits in the second header row, so a one-row reading files it
as data and it never becomes a label at all.
"""

import lxml.html
import pytest

from forensic_metascience_ai_toolkit.extraction.html import _rows_of
from forensic_metascience_ai_toolkit.extraction.jats import _Counter, _expand, _header_depth
from forensic_metascience_ai_toolkit.extraction.supplements_read import _finish
from forensic_metascience_ai_toolkit.values import design_values_from_cells

# The shape of the real thing: a spanning group label over the columns that
# carry the group sizes. Taken from `10.1007--s00702-004-0248-2`.
TWO_ROW = """<table>
 <tr><td rowspan="2"></td><td colspan="2">Treatment</td></tr>
 <tr><td>Cerebrolysin (n = 78)</td><td>Placebo (n = 68)</td></tr>
 <tr><td>Age (years)</td><td>65 &#177; 1.17</td><td>65 &#177; 1.32</td></tr>
</table>"""

# No span anywhere: the header is one row and nothing may claim otherwise.
ONE_ROW = """<table>
 <tr><td>Measure</td><td>Drug</td><td>Placebo</td></tr>
 <tr><td>Age</td><td>65</td><td>66</td></tr>
</table>"""

# Row 0 spans, but the row below it is DATA -- its stub is a bare number. The
# walk must stop, or a row of measurements is promoted to a label and the
# register loses the values entirely. From `10.1016--j.yexcr.2014.06.020`.
SPAN_OVER_DATA = """<table>
 <tr><td>DIV</td><td colspan="2">Spinal cord cultures</td></tr>
 <tr><td>0</td><td>-</td><td>+</td></tr>
 <tr><td>7</td><td>+</td><td>+</td></tr>
</table>"""

# Row 0 spans and the row below is a row of numbers. The stub is a word, so only
# the measurement brake can stop this one.
SPAN_OVER_NUMBERS = """<table>
 <tr><td>Group</td><td colspan="2">Outcome</td></tr>
 <tr><td>Drug</td><td>12.5</td><td>13.5</td></tr>
</table>"""


# NO HEADER AT ALL: the first row is data, and no span anywhere licenses
# treating it otherwise. This is a long table continued onto a second element
# without its header repeated -- the shape of PMC5532079 Table 1, where forcing
# row 0 into the header names a column `49` and loses the row's own denominator
# to every value beneath it.
NO_HEADER = """<table>
 <tr><td>No. of patients</td><td>49</td><td>51</td></tr>
 <tr><td>Age (years)</td><td>62.1</td><td>63.4</td></tr>
 <tr><td>Male, n</td><td>21</td><td>26</td></tr>
</table>"""

# THE SAME SHAPE, TOO NARROW TO PROVE ANYTHING. One measurement-shaped cell
# beside a word stub is not evidence by the shared brake -- a genuine header
# `Measure | 2019` reads identically -- so this row still gets depth 1. Recorded
# as a test because the limit is deliberate: refusing to guess costs a column
# label, and guessing wrong deletes a row of measurements.
AMBIGUOUS_FIRST_ROW = """<table>
 <tr><td>No. of patients</td><td>49</td></tr>
 <tr><td>Age (years)</td><td>62.1</td></tr>
</table>"""


def _read(html):
    element = lxml.html.fromstring(html)
    rows = _rows_of(element, _Counter())
    grid, _spans, warnings, _padded = _expand(rows)
    return rows, grid, warnings


def _table(html, header_rows=None):
    rows, grid, warnings = _read(html)
    depth = _header_depth(rows, grid) if header_rows is None else header_rows
    return _finish(grid, 1, "Table 1", "", "", "test",
                   warnings=list(warnings), header_rows=depth)


class TestTheMarkupIsTheProof:
    def test_a_spanning_first_row_proves_a_second_header_row(self):
        rows, grid, _ = _read(TWO_ROW)
        assert _header_depth(rows, grid) == 2

    def test_no_span_means_one_row_and_nothing_deeper(self):
        rows, grid, _ = _read(ONE_ROW)
        assert _header_depth(rows, grid) == 1

    def test_a_real_header_row_is_never_dropped(self):
        # This used to assert that zero was categorically wrong, on the grounds
        # that every caller slices `grid[:depth]`. The reasoning was backwards:
        # where row 0 IS data, a depth of 1 does not save a header, it invents
        # one out of measurements. What must hold is narrower and is what these
        # four fixtures actually show -- each has a genuine header row 0, and
        # none of them may lose it.
        for html in (TWO_ROW, ONE_ROW, SPAN_OVER_DATA, SPAN_OVER_NUMBERS):
            rows, grid, _ = _read(html)
            assert _header_depth(rows, grid) >= 1


class TestATableMayHaveNoHeader:
    """A continued table repeats no header, and its first row is a measurement.

    Naming the columns after it is strictly worse than leaving them unnamed: the
    cells beneath then carry a CONFIDENT wrong name, and the row's own
    denominator (`No. of patients | 49`) becomes a column heading instead.
    """

    def test_a_data_first_row_proves_no_header(self):
        rows, grid, _ = _read(NO_HEADER)
        assert _header_depth(rows, grid) == 0

    def test_the_columns_are_reported_unlabelled(self):
        table = _table(NO_HEADER)
        labels = {cell["col_label"] for cell in table["cells"]}
        assert not any("49" in label for label in labels), labels
        assert all("unlabelled column" in label for label in labels), labels

    def test_the_first_row_stays_in_the_body(self):
        table = _table(NO_HEADER)
        assert table["n_header_rows"] == 0
        assert table["rows"][0][0] == "No. of patients"
        raws = {cell["raw"] for cell in table["cells"]}
        assert {"49", "51"} <= raws

    def test_the_reader_is_told(self):
        table = _table(NO_HEADER)
        assert any("no header in the source" in w for w in table["warnings"])

    def test_an_ambiguous_first_row_is_still_a_header(self):
        # The narrowing rests on the SAME brake the walk already uses, and that
        # brake needs two measurement-shaped cells or a bare-number stub. One
        # number beside a word is not evidence, so nothing changes here.
        rows, grid, _ = _read(AMBIGUOUS_FIRST_ROW)
        assert _header_depth(rows, grid) == 1


class TestTheBrake:
    def test_a_numeric_stub_stops_the_walk(self):
        rows, grid, _ = _read(SPAN_OVER_DATA)
        assert _header_depth(rows, grid) == 1

    def test_a_row_of_measurements_stops_the_walk(self):
        rows, grid, _ = _read(SPAN_OVER_NUMBERS)
        assert _header_depth(rows, grid) == 1

    def test_the_data_row_survives_as_data(self):
        # The point of the brake: those measurements must still be in the body,
        # because a value promoted to a label is a value no check can reach.
        table = _table(SPAN_OVER_NUMBERS)
        assert any(cell["raw"] == "12.5" for cell in table["cells"])


class TestTheColumnKeepsItsIdentity:
    def test_each_column_gets_its_own_label(self):
        table = _table(TWO_ROW)
        labels = [cell["col_label"] for cell in table["cells"]
                  if cell["raw"].startswith("65")]
        assert len(labels) == 2
        assert len(set(labels)) == 2, f"two arms collapsed into one label: {labels}"

    def test_the_group_size_reaches_the_label(self):
        table = _table(TWO_ROW)
        joined = " ".join(cell["col_label"] for cell in table["cells"])
        assert "n = 78" in joined and "n = 68" in joined

    def test_the_one_row_reading_is_what_loses_them(self):
        # Stated as a test so the regression is visible rather than inferred.
        table = _table(TWO_ROW, header_rows=1)
        joined = " ".join(cell["col_label"] for cell in table["cells"])
        assert "n = 78" not in joined


class TestTheRegisterGetsTheN:
    """`n` gates grim, grimmer, sprite, debit and count-percent. Nothing else
    in the pipeline recovers it if the header reading drops it."""

    def test_two_design_values_at_the_proven_depth(self):
        table = _table(TWO_ROW)
        values = design_values_from_cells(table["cells"], table="t1")
        assert sorted(v["value"] for v in values) == [68, 78]

    def test_none_at_a_one_row_reading(self):
        table = _table(TWO_ROW, header_rows=1)
        assert design_values_from_cells(table["cells"], table="t1") == []


class TestFinishDidNotChangeUnderneathItsOtherCallers:
    def test_the_default_is_still_one_row(self):
        grid = [["Measure", "Drug"], ["Age", "65"]]
        table = _finish(grid, 1, "T", "", "", "docx")
        assert table["n_header_rows"] == 1
        assert table["headers"] == ["Measure", "Drug"]

    def test_a_depth_past_the_end_cannot_empty_the_table(self):
        grid = [["Measure", "Drug"], ["Age", "65"]]
        table = _finish(grid, 1, "T", "", "", "docx", header_rows=9)
        assert table["rows"] == [] and table["n_header_rows"] == 2


class TestDoclingIsAskedRatherThanGuessedAt:
    """Every docling `TableCell` carries `column_header`. `_grid_of` used to
    keep only `.text`, so the flag existed and no reader ever saw it."""

    @staticmethod
    def _table(rows):
        class Cell:
            def __init__(self, text, header):
                self.text = text
                self.column_header = header

        class Data:
            def __init__(self, grid):
                self.grid = grid

        class Table:
            def __init__(self, grid):
                self.data = Data(grid)

        return Table([[Cell(text, header) for text, header in row] for row in rows])

    def test_two_flagged_rows_are_two_header_rows(self):
        from forensic_metascience_ai_toolkit.extraction.docling_tables import _grid_of

        table = self._table([
            [("", True), ("Treatment", True), ("Treatment", True)],
            [("", True), ("Drug (n = 78)", True), ("Placebo (n = 68)", True)],
            [("Age", False), ("65", False), ("66", False)],
        ])
        grid, route, header_rows = _grid_of(table, None)
        assert route == "data.grid"
        assert header_rows == 2
        assert len(grid) == 3

    def test_one_flagged_row_is_one(self):
        from forensic_metascience_ai_toolkit.extraction.docling_tables import _grid_of

        table = self._table([
            [("Measure", True), ("Drug", True)],
            [("Age", False), ("65", False)],
        ])
        assert _grid_of(table, None)[2] == 1

    def test_nothing_flagged_still_reads_a_header(self):
        # docling flags no header on some tables. Returning 0 would drop the
        # header the PDF path has always assumed; the floor keeps that promise
        # explicit instead of leaving it to a slice that happened to say 1.
        from forensic_metascience_ai_toolkit.extraction.docling_tables import _grid_of

        table = self._table([
            [("Measure", False), ("Drug", False)],
            [("Age", False), ("65", False)],
        ])
        assert _grid_of(table, None)[2] == 1


class TestTheEmptyStubDoesNotDiscardTheAnswer:
    """A stacked header's top-left corner is blank, and docling does not flag a
    blank cell. Requiring EVERY cell to be flagged therefore returned 1 on a
    table docling had marked two rows deep -- verified against real output for
    `10.1166--jnn.2011.5114`, where `n_header_rows` came back 1 for all six
    tables and three treatment arms kept sharing one label."""

    def test_an_unflagged_blank_corner_does_not_cost_the_second_row(self):
        from forensic_metascience_ai_toolkit.extraction.docling_tables import _grid_of

        table = TestDoclingIsAskedRatherThanGuessedAt._table([
            [("", False), ("Control", True), ("Control", True)],
            [("", False), ("Saline", True), ("Cu", True)],
            [("A", False), ("5", False), ("6", False)],
        ])
        assert _grid_of(table, None)[2] == 2

    def test_a_row_of_blanks_is_not_a_header_row(self):
        from forensic_metascience_ai_toolkit.extraction.docling_tables import _grid_of

        table = TestDoclingIsAskedRatherThanGuessedAt._table([
            [("", False), ("", False)],
            [("A", False), ("5", False)],
        ])
        assert _grid_of(table, None)[2] == 1

    def test_a_data_row_still_stops_the_count(self):
        from forensic_metascience_ai_toolkit.extraction.docling_tables import _grid_of

        table = TestDoclingIsAskedRatherThanGuessedAt._table([
            [("", False), ("Control", True), ("Control", True)],
            [("A", False), ("5", False), ("6", False)],
        ])
        assert _grid_of(table, None)[2] == 1


class TestAFlagCannotDeleteAValue:
    """`column_header` is a claim about layout; `_reads_as_measurements` is a
    claim about content. Where they disagree the content wins -- a header row
    leaves the body, and a measurement that leaves the body stops existing for
    every check downstream."""

    def test_a_flagged_row_of_numbers_stays_in_the_body(self):
        from forensic_metascience_ai_toolkit.extraction.docling_tables import _grid_of

        table = TestDoclingIsAskedRatherThanGuessedAt._table([
            [("", False), ("Control", True), ("Control", True)],
            [("Mean", True), ("12.5", True), ("13.5", True)],
            [("A", False), ("5", False), ("6", False)],
        ])
        assert _grid_of(table, None)[2] == 1

    def test_the_first_row_is_never_taken_away_by_the_brake(self):
        # Row 0 is the header by the PDF path's long-standing convention. The
        # brake governs how much FURTHER to go, not whether to have a header.
        from forensic_metascience_ai_toolkit.extraction.docling_tables import _grid_of

        table = TestDoclingIsAskedRatherThanGuessedAt._table([
            [("Mean", True), ("12.5", True), ("13.5", True)],
            [("A", False), ("5", False), ("6", False)],
        ])
        assert _grid_of(table, None)[2] == 1

    def test_a_flagged_row_of_labels_is_still_promoted(self):
        from forensic_metascience_ai_toolkit.extraction.docling_tables import _grid_of

        table = TestDoclingIsAskedRatherThanGuessedAt._table([
            [("", False), ("Control", True), ("Control", True)],
            [("Type", True), ("Saline", True), ("Cu", True)],
            [("A", False), ("5", False), ("6", False)],
        ])
        assert _grid_of(table, None)[2] == 2
