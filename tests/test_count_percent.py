"""The printed count, checked against the printed percentage.

THE FALSE CLEAR THIS CLOSES, reproduced before the tool existed:

    grim_percentage(percentage=73.0, n=200, decimals=1) -> consistent

because 73.0 is reachable as 100k/200 at k = 146. But a cell reading
`142 (73.0)` printed k = 142, and 100 x 142 / 200 = 71.0. `parse_cells` returned
`count: 142` the whole time; `_build_args` dropped it, because
`grim_percentage`'s schema has no `count`.

A false clear is the second-worst output this toolkit can produce, and it is
worse than the missing-check case it looks like: a check that refuses says so,
while this one answered a nearby question and reported success.
"""
import pytest

from forensic_metascience_ai_toolkit import registry as R
from forensic_metascience_ai_toolkit.dispatch import check_table
from forensic_metascience_ai_toolkit.tools.count_percent import CEILING, check_count_percent

PROP = {"id": "g", "family": "proportion", "confidence": "high"}


class TestTheArithmetic:
    def test_a_matching_cell_is_consistent(self):
        r = check_count_percent(count=142, percentage=71.0, n=200, decimals=1)
        assert r["severity"] == "consistent" and r["consistent"] is True

    def test_the_measured_false_clear_is_now_caught(self):
        r = check_count_percent(count=142, percentage=73.0, n=200, decimals=1)
        assert r["severity"] == CEILING
        assert r["computed_percentage"] == 71.0

    def test_grim_still_calls_that_same_cell_consistent(self):
        """Not a criticism of GRIM -- it answers a different question, and is
        the right tool when only a percentage is printed. Pinned so the reason
        both checks run is visible."""
        out = R.BY_NAME["grim_percentage"].call(
            {"percentage": 73.0, "n": 200, "decimals": 1, "data_type": "proportion"})
        assert out["severity"] == "consistent"

    def test_rounding_is_respected(self):
        """`71` printed to 0 dp asserts [70.5, 71.5]; 100*142/200 = 71.0 sits
        inside it. Judging a printed number against more precision than it
        claims is how a correct cell becomes an accusation."""
        assert check_count_percent(count=142, percentage=71, n=200,
                                   decimals=0)["severity"] == "consistent"
        assert check_count_percent(count=141, percentage=71, n=200,
                                   decimals=0)["severity"] == "consistent"  # 70.5
        assert check_count_percent(count=139, percentage=71, n=200,
                                   decimals=0)["severity"] == CEILING       # 69.5


class TestItCannotBecomeAnAccusation:
    def test_it_never_exceeds_suspicious(self):
        """A percentage over a DIFFERENT base is the commonest convention in
        clinical tables, and no arithmetic disagreement rules it out."""
        assert CEILING == "suspicious"
        for count, pct in [(1, 99.0), (999, 0.1), (5, 50.0)]:
            r = check_count_percent(count=count, percentage=pct, n=1000, decimals=1)
            assert r["severity"] in ("consistent", "suspicious")

    def test_a_mismatch_reports_the_denominator_it_implies(self):
        """More useful than the flag. A reader who sees `implied 1293` and
        recognises the column header's n has resolved it at a glance."""
        r = check_count_percent(count=646, percentage=49.96, n=2830, decimals=2)
        assert r["severity"] == CEILING
        assert 1290 < r["implied_denominator"] < 1296

    def test_the_innocent_reading_is_stated_beside_the_flag(self):
        r = check_count_percent(count=142, percentage=73.0, n=200, decimals=1)
        assert "different base" in r["alternative_reading"].lower()

    def test_a_count_larger_than_n_is_a_wrong_pairing_not_a_defect(self):
        """It PROVES this n is not the base for this percentage -- a fact about
        our pairing. Flagging the paper for it would be an accusation built out
        of our own mistake."""
        r = check_count_percent(count=300, percentage=15.0, n=200, decimals=1)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False
        assert "not the base" in r["explanation"]

    def test_missing_decimals_refuses_rather_than_guessing(self):
        r = check_count_percent(count=142, percentage=73.0, n=200)
        assert r["severity"] == "indeterminate"
        assert "rounding interval is unknown" in r["error"]

    def test_no_denominator_is_a_refusal(self):
        assert check_count_percent(count=1, percentage=1.0, n=0,
                                   decimals=1)["severity"] == "indeterminate"


class TestItIsActuallyReached:
    """Built-and-never-called is this repo's signature defect, and this tool
    exists precisely because a value was computed and then dropped at an
    argument boundary."""

    def test_the_dispatcher_runs_it_on_an_n_percent_cell(self):
        """CHANGED 2026-08-20. The old case was `142 (73.0)` against n=200,
        which implies 195 -- a 2.5% gap, and `_clamp_shared_denominator` now
        caps a lone row that near the header to `indeterminate`. The tool is
        still REACHED and still flags; what changed is how loudly a near-miss
        speaks. So the accusing case here is widened past the clamp, and the
        near-miss keeps its own test below."""
        r = check_table([{"raw": "142 (90.0)", "row_label": "F", "n": 200}],
                        [PROP], {"F": "g"})           # implies 158, a 21% gap
        assert "check_count_percent" in r["tools_run"]
        assert r["severity"] == "suspicious"

    def test_a_lone_near_miss_is_reached_but_only_capped(self):
        """The tool runs -- that is what this class exists to prove -- and the
        verdict is `indeterminate` rather than an accusation, because one row
        five below its header is the shape of item non-response and from a
        single row that cannot be told from a slip in the percentage."""
        r = check_table([{"raw": "142 (73.0)", "row_label": "F", "n": 200}],
                        [PROP], {"F": "g"})           # implies 195, a 2.5% gap
        assert "check_count_percent" in r["tools_run"]
        assert r["severity"] == "indeterminate"

    def test_it_runs_alongside_grim_not_instead_of_it(self):
        r = check_table([{"raw": "142 (71.0)", "row_label": "F", "n": 200}],
                        [PROP], {"F": "g"})
        assert {"grim_percentage", "check_count_percent"} <= set(r["tools_run"])
        assert r["severity"] == "consistent"

    def test_the_count_survives_the_argument_boundary(self):
        """The actual bug: `parse_cells` returned `count` and `_build_args`
        never passed it on."""
        r = check_table([{"raw": "142 (73.0)", "row_label": "F", "n": 200}],
                        [PROP], {"F": "g"})
        rec = [x for x in r["results"] if x["tool"] == "check_count_percent"][0]
        assert rec["inputs"]["count"] == 142

    def test_every_n_percent_dispatch_row_includes_it(self):
        from forensic_metascience_ai_toolkit.dispatch import DISPATCH
        rows = {k: v for k, v in DISPATCH.items() if k[0] == "n_percent"}
        assert rows
        for key, tools in rows.items():
            assert "check_count_percent" in tools, key


class TestTheRedTeamFindings:
    """Found by adversarially red-teaming this check on the day it was written.
    Two of the three were CONFIRMED false accusations against honest input --
    the worst category this project recognises."""

    def test_a_truncating_table_is_not_convicted(self):
        """CONFIRMED FALSE ACCUSATION. An honest table of 897 people with
        percentages TRUNCATED at 2 dp had its denominator correctly derived by
        `composite.split_sections` and was then convicted on 3 of its 4 cells,
        publishing `suspicious` for the whole table.

        The n was never wrong. The two modules disagreed about ROUNDING:
        `composite._PCT_CELL_TOLERANCE` is 0.011, explicitly doubled for the
        truncation ambiguity, while this used a half-ulp of 0.005. A truncating
        table passed section verification and was then accused by the check
        running on the very cells that certified the denominator."""
        from forensic_metascience_ai_toolkit.dispatch import check_table
        rows = [("Married", 311, 34.67), ("Single", 208, 23.18),
                ("Divorced", 253, 28.20), ("Widowed", 125, 13.93)]
        cells = [{"raw": f"{c} ({p})", "row": i, "row_label": lab,
                  "col_label": "Overall"} for i, (lab, c, p) in enumerate(rows, 1)]
        r = check_table(cells, [PROP], {lab: "g" for lab, _, _ in rows})
        flagged = [x for x in r["results"] if x["tool"] == "check_count_percent"]
        assert not flagged, [x["cell"]["raw"] for x in flagged]

    def test_a_truncation_only_fit_says_which_convention_it_needed(self):
        """`grim_percentage` already names this when a value fits only under
        truncation. Two checks on one cell must not disagree about what they
        accepted -- but naming it is not escalating it."""
        r = check_count_percent(count=208, percentage=23.18, n=897, decimals=2)
        assert r["severity"] == "consistent"
        assert r["rounding_convention"] == "truncation"
        assert "TRUNCATES rather than rounds" in r["explanation"]

    def test_a_rounding_fit_claims_no_convention(self):
        r = check_count_percent(count=311, percentage=34.67, n=897, decimals=2)
        assert r["severity"] == "consistent"
        assert "rounding_convention" not in r

    def test_a_real_error_still_fails_after_the_window_widened(self):
        """The window admits truncation; it must not admit everything."""
        assert check_count_percent(count=142, percentage=73.0, n=200,
                                   decimals=1)["severity"] == CEILING

    def test_count_equal_to_n_is_the_same_wrong_pairing_as_count_above_it(self):
        """OFF BY ONE. `count == n` forces 100%, so a printed percentage below
        100 proves the pairing is wrong by exactly the tool's own argument --
        yet it was flagged, while one person more was excused."""
        assert check_count_percent(count=132, percentage=41.5, n=132,
                                   decimals=1)["severity"] == "indeterminate"
        assert check_count_percent(count=133, percentage=41.5, n=132,
                                   decimals=1)["severity"] == "indeterminate"

    def test_a_genuine_hundred_percent_still_passes(self):
        assert check_count_percent(count=132, percentage=100.0, n=132,
                                   decimals=1)["severity"] == "consistent"

    def test_a_non_finite_input_refuses_on_the_raw_function(self):
        """The registry's `ToolSpec.call` guarded this, but `cli.py` calls the
        raw function -- so a NaN count reached the comparison and returned
        `suspicious` on "nan/100 = nan%"."""
        for bad in (float("nan"), float("inf")):
            assert check_count_percent(count=bad, percentage=50.0, n=100,
                                       decimals=1)["severity"] == "indeterminate"
