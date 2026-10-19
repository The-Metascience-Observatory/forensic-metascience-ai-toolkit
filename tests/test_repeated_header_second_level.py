"""A header row that repeats itself is a SPAN, and the row below names the columns.

MEASURED 2026-08-22 over the twelve-paper corpus, splitting ambiguity by the
table's own source rather than by the paper:

    article      154 of 2,046   7.5%
    pdf-supp     971 of 1,907  50.9%   <- the outlier
    docx-supp     44 of   566   7.8%
    xlsx-supp      0 of 2,983   0.0%

The PDF-supplement path is seven times worse than any other. The cause, on
`...51752` supplementary_info_2 Table 3:

    r0  '' | 'Mothers of Girls' x4 | 'Mothers of Boys' x4     depth reported: 1
    r1  'Baseline' | 'MC' | 'MT' | 'p-v' | 'MHT' | 'MC' ...   read as DATA

Docling propagates a spanning cell across the columns it covers, so the repeat
in r0 IS the span -- and then reports `n_header_rows: 1`, so r1, which holds
the only labels that tell those four columns apart, lands in the body. Four
columns end up named `Mothers of Girls`.

`jats._header_depth` states the cost: a value taken from one of them and an `n`
from another are indistinguishable afterwards, and a check on that pair calls
an honest paper impossible.

FAILS CLOSED, and that brake matters more than the fix. The row below is only
promoted when it does NOT read as measurements -- a header that swallows a data
row deletes a measurement from every check, which is the worse error. It must
also actually help: more distinct labels than the row above, or there is
nothing to gain and we leave the table alone.
"""
from metascience_agent.extraction import supplements_read as S


class TestARepeatedHeaderRowIsASpan:
    def _grid(self):
        return [
            ["", "Mothers of Girls", "Mothers of Girls", "Mothers of Boys",
             "Mothers of Boys"],
            ["Baseline", "MC", "MT", "MC", "MT"],
            ["RP: Race", "0.916", "0.911", "0.928", "0.933"],
            ["RP: Age", "0.249", "0.321", "0.293", "0.301"],
        ]

    def test_the_inner_level_joins_the_label(self):
        t = S._finish([r[:] for r in self._grid()], 1, "T3", "", "x", "pdf")
        assert t["headers"][1] == "Mothers of Girls | MC"
        assert t["headers"][2] == "Mothers of Girls | MT"

    def test_the_columns_become_distinguishable(self):
        t = S._finish([r[:] for r in self._grid()], 1, "T3", "", "x", "pdf")
        named = [h for h in t["headers"] if str(h).strip()]
        assert len(named) == len(set(named)), f"still ambiguous: {named}"

    def test_the_measurement_rows_survive(self):
        t = S._finish([r[:] for r in self._grid()], 1, "T3", "", "x", "pdf")
        assert t["n_rows"] == 2

    def test_a_header_with_no_repeat_is_left_alone(self):
        grid = [["Var", "Mean", "SD"], ["Age", "41.2", "8.1"]]
        t = S._finish([r[:] for r in grid], 1, "T", "", "x", "pdf")
        assert t["headers"][1] == "Mean" and t["n_rows"] == 1

    def test_it_refuses_when_the_row_below_is_measurements(self):
        """A repeated header above NUMBERS is not a stacked header -- promoting
        it would delete a row of data."""
        grid = [["", "Arm A", "Arm A", "Arm B", "Arm B"],
                ["Age", "41.2", "8.1", "40.7", "7.9"],
                ["BMI", "26.1", "3.2", "25.8", "3.4"]]
        t = S._finish([r[:] for r in grid], 1, "T", "", "x", "pdf")
        assert t["n_rows"] == 2, "a measurement row must never be eaten"

    def test_it_refuses_when_the_row_below_does_not_disambiguate(self):
        """If the candidate adds no distinctions there is nothing to gain."""
        grid = [["", "Arm A", "Arm A"], ["", "x", "x"], ["Age", "1", "2"]]
        t = S._finish([r[:] for r in grid], 1, "T", "", "x", "pdf")
        assert t["n_rows"] == 2
