"""`12/30 (40.0)` -- the one cell where GRIM needs nothing from the model.

MEASURED 2026-08-09 and re-verified against `git show HEAD:...celltypes.py`:
this cell typed `non_numeric` both before and after that day's parse-layer
fixes, so the gap was original rather than introduced, and every downstream
check skipped it.

WHY IT WAS WORTH FIXING even though the direction is safe (coverage lost, never
a false accusation): everywhere else a granularity test runs, the n has to be
INFERRED -- read off a column header, carried down from a row above, or assumed
-- and each of those routes can be wrong in a way that manufactures an
impossibility out of a correctly reported number. Here the paper prints the
denominator. `bound_source` is "stated", so rulebook rule 4's cap on assumed
bounds does not apply, and a finding on this cell can carry full severity.

THE DATE TRAP is the reason the bare form is handled differently, and it is not
hypothetical: `12/30` in a responder column is 12 of 30, and `12/30` in a date
column is the 30th of December. The parenthesised percentage settles it -- dates
do not come with percentages. Without one, a pair that would also make a
calendar date stays `ambiguous` rather than being guessed at, because guessing
here would invent a denominator, and an invented n is exactly how this toolkit
manufactures a false accusation.
"""
import pytest

from metascience_agent.tools.celltypes import CELL_KINDS, parse_cell

KIND = "count_denominator_percent"


class TestTheFormsThatParse:
    @pytest.mark.parametrize("raw", [
        "12/30 (40.0)",
        "12 / 30 (40.0)",     # spaces around the solidus
        "12/30 (40.0%)",      # percent sign inside the parentheses
        "12/30 [40.0]",       # square brackets
    ])
    def test_count_denominator_and_percent_are_all_recovered(self, raw):
        c = parse_cell(raw)
        assert c.kind == KIND, raw
        assert (c.count, c.denominator, c.percent) == (12, 30, 40.0)

    def test_printed_precision_of_the_percentage_is_kept(self):
        """A granularity test sizes its rounding interval from the PRINTED
        precision. Assuming a decimal too many shrinks the interval tenfold and
        manufactures impossibilities."""
        assert parse_cell("12/30 (40.0)").decimals_percent == 1
        assert parse_cell("12/30 (40)").decimals_percent == 0

    def test_a_bare_fraction_parses_when_it_cannot_be_a_date(self):
        c = parse_cell("120/300")
        assert c.kind == KIND
        assert (c.count, c.denominator, c.percent) == (120, 300, None)


class TestTheDateTrap:
    @pytest.mark.parametrize("raw", ["12/30", "3/4", "1/31"])
    def test_a_bare_fraction_that_could_be_a_date_stays_ambiguous(self, raw):
        c = parse_cell(raw)
        assert c.kind == "ambiguous"
        assert "date" in c.candidates

    def test_the_ambiguous_cell_offers_no_arguments_to_any_tool(self):
        """Ambiguity has to be load-bearing. A cell whose meaning is unknown
        must yield nothing, or the guess reaches a forensic check anyway."""
        assert parse_cell("12/30").forensic_kwargs() == {}

    def test_a_percentage_resolves_it(self):
        assert parse_cell("12/30 (40.0)").kind == KIND


class TestImpossibleFractionsAreRefusedRatherThanTyped:
    def test_a_numerator_larger_than_its_denominator_is_not_a_proportion(self):
        """`30/12` cannot be 30 of 12. Typing it would hand GRIM an n smaller
        than its own count."""
        assert parse_cell("30/12").kind != KIND


class TestItReachesGrimWithAStatedN:
    def test_the_arguments_carry_the_denominator(self):
        assert parse_cell("12/30 (40.0)").forensic_kwargs() == {
            "count": 12, "n": 30, "percentage": 40.0}

    def test_a_consistent_percentage_passes_grim(self):
        from metascience_agent.tools.grim import grim_test_percentage
        c = parse_cell("12/30 (40.0)")
        r = grim_test_percentage(percentage=c.percent, n=c.denominator,
                                 decimals=c.decimals_percent)
        assert r["consistent"] is True

    def test_an_unreachable_percentage_is_caught(self):
        """13/30 is 43.333, which prints as 43.3. A reported 43.4 is not a value
        any whole count out of 30 can produce -- and the n came from the cell,
        so nothing about this finding rests on an inference of ours."""
        from metascience_agent.tools.grim import grim_test_percentage
        c = parse_cell("13/30 (43.4)")
        r = grim_test_percentage(percentage=c.percent, n=c.denominator,
                                 decimals=c.decimals_percent)
        assert r["consistent"] is False
        assert r["severity"] == "impossible"


class TestTheKindIsRegistered:
    def test_it_is_in_the_vocabulary(self):
        """A kind absent from CELL_KINDS is a kind no consumer knows to expect."""
        assert KIND in CELL_KINDS


class TestThePrintedDenominatorReachesACheck:
    """`count_denominator_percent` -- `12/30 (40.0)` -- is the one cell form
    where the paper prints its own n. celltypes has typed it since f009ee3;
    DISPATCHABLE_KINDS never gained it and DISPATCH never gained a row, so the
    best-evidenced percentage cell in the corpus was the one cell form nothing
    checked. It fell to "no check defined for a count_denominator_percent cell".
    """

    CELLS = [
        {"raw": "12/30 (40.0)", "row": 1, "col": 1,
         "row_label": "Responders", "col_label": "Treatment"},
        {"raw": "12/30 (44.4)", "row": 2, "col": 1,
         "row_label": "Remission", "col_label": "Treatment"},
    ]

    def test_as_dict_keeps_the_denominator(self):
        """It was parsed, documented at length, and then dropped one method
        later -- `forensic_kwargs` returned it and `as_dict` did not, so the
        per-cell path saw the number and the table path did not."""
        from metascience_agent.tools.celltypes import parse_cell
        assert parse_cell("12/30 (40.0)").as_dict()["denominator"] == 30

    def test_the_cell_reaches_a_check_at_all(self):
        from metascience_agent.dispatch import check_table
        out = check_table(cells=self.CELLS, variables=[], bindings={})
        assert out["n_checks_run"] == 4
        assert out["n_not_run"] == 0

    def test_a_wrong_percentage_is_caught(self):
        """12/30 is 40.0, not 44.4."""
        from metascience_agent.dispatch import check_table
        out = check_table(cells=self.CELLS, variables=[], bindings={})
        caught = [r for r in out["results"]
                  if r["tool"] == "check_count_percent"
                  and r["cell"]["raw"] == "12/30 (44.4)"]
        assert caught and caught[0]["severity"] == "suspicious"

    def test_the_right_percentage_clears(self):
        from metascience_agent.dispatch import check_table
        out = check_table(cells=self.CELLS, variables=[], bindings={})
        assert any(c["tool"] == "check_count_percent"
                   for c in out["consistent_index"])

    def test_the_n_is_the_cell_s_own_and_says_so(self):
        """Not inferred from a column header, not carried down from a row
        above, not reconstructed from a section total -- each of which can
        manufacture an impossibility."""
        from metascience_agent.dispatch import check_table
        out = check_table(cells=self.CELLS, variables=[], bindings={})
        for r in out["results"]:
            assert r["inputs"]["n"] == 30
            assert r["n_provenance"]["how"] == "printed_in_the_cell"
            assert r["n_provenance"]["derived"] is False

    def test_the_common_printed_variants_all_type(self):
        from metascience_agent.tools.celltypes import parse_cell
        for raw in ("12/30 (40.0)", "12/30 (40.0%)", "12/30 (40%)",
                    "12 / 30 (40.0)", "12/30(40.0)", "12/30 [40.0]",
                    "0/30 (0.0)"):
            c = parse_cell(raw)
            assert c.kind == "count_denominator_percent", raw
            assert c.denominator == 30, raw
