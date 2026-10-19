"""A cell we could not parse is not the same fact as a cell holding `NA`.

`n_cells_with_no_value` counted both in one number. MEASURED 2026-08-22 over
the twelve-paper corpus: 1,838 cells produced no value, and **1,182 of them
contain digits** --

    '189153851 28668870 10307907 8421099'          four counts fused
    '81.2 (81.0-81.6) 11.6 (11.3-11.9) 4.0 (3...'  several estimate+CI fused
    '<.001 <.001'                                   two p-values fused

against 656 that are the paper's own missing-data markers (`NA` 104, `X` 126,
`-` 29, `--` 20, and text labels).

The first kind is OUR failure -- docling collapsing several table rows into one
cell -- and each such cell holds four to eight printed numbers, so the real loss
is several thousand values. The second kind is the PAPER saying it has no value
there, which is not a loss at all.

Reporting them as one number states our defect as the paper's property, which
is the confusion this codebase exists to prevent. Splitting them does NOT
recover anything; it makes the size of the loss visible instead of hiding it
inside a count that reads as ordinary.

NOT PARSED, DELIBERATELY. A glued cell cannot say which column each number
belongs to -- that is what makes it glued. Splitting one would attach a number
to a heading it was never printed under, and a mean paired with another
column's `n` is how an honest paper gets accused.
"""
from metascience_agent import values as V


class TestTheTwoReasonsAreSeparated:
    def test_a_marker_is_the_papers_property(self):
        out = V.no_value_reasons(["NA", "X", "-", "--", "n/a"])
        assert out["n_marker"] == 5
        assert out["n_unparsed_with_digits"] == 0

    def test_a_glued_cell_is_our_failure(self):
        out = V.no_value_reasons([
            "189153851 28668870 10307907 8421099",
            "<.001 <.001",
        ])
        assert out["n_unparsed_with_digits"] == 2
        assert out["n_marker"] == 0

    def test_plain_text_is_neither_a_marker_nor_a_loss(self):
        out = V.no_value_reasons(["Mothers of Girls", "Whole"])
        assert out["n_text"] == 2
        assert out["n_unparsed_with_digits"] == 0

    def test_the_total_is_conserved(self):
        cells = ["NA", "X", "1.2 3.4 5.6", "Some label", ""]
        out = V.no_value_reasons(cells)
        assert (out["n_marker"] + out["n_unparsed_with_digits"]
                + out["n_text"] + out["n_blank"]) == out["n_cells"] == 5

    def test_it_says_which_are_ours(self):
        """The whole point is that a reader can see the size of OUR loss."""
        out = V.no_value_reasons(["NA", "1.2 3.4"])
        assert "ours" in out["note"].lower() or "our" in out["note"].lower()

    def test_an_empty_input_reports_zeros_not_omissions(self):
        out = V.no_value_reasons([])
        assert out["n_cells"] == 0 and out["n_unparsed_with_digits"] == 0
