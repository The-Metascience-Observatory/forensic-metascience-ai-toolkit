"""The magic constants the checks used to compare against.

Rounding was never missing across the board -- the whole GRIM/GRIMMER/SPRITE/
DEBIT family has always been interval-based. It was missing from exactly the
checks that fire most: per the batch docstrings, a real review made 79 of 111
stage-1 calls to `check_regression` and 55 of 124 to `check_summation`, and
both compared against a constant.
"""
import pytest

from metascience_agent.tools import rounding as R
from metascience_agent.tools.anova import recalc_f_to_p
from metascience_agent.tools.regression import check_regression, check_regression_batch
from metascience_agent.tools.sd_checks import check_sd_range
from metascience_agent.tools.summation import check_summation, check_summation_batch
from metascience_agent.tools.ttest import _p_matches


class TestQuotientInterval:
    def test_the_bounds_are_exact_not_merely_the_right_shape(self):
        """Pinned numerically in BOTH directions. A version returning an
        interval twice as wide about the same centre passed the rest of this
        class, and too-wide is the direction that silently clears a
        fabrication."""
        lo, hi = R.quotient_interval(2.0, 1, 0.5, 1)
        assert lo == pytest.approx(1.95 / 0.55, abs=1e-12)
        assert hi == pytest.approx(2.05 / 0.45, abs=1e-12)

    def test_it_never_returns_an_interval_narrower_than_the_truth(self):
        """Brute force over the rectangle. Too narrow is what manufactures
        accusations, so it is the property that has to hold everywhere, not
        just on the cases someone thought of."""
        import itertools
        cases = [(2.0, 1, 0.5, 1), (-2.0, 1, 0.5, 1), (0.12, 2, 0.05, 2),
                 (2.0, 0, 5.0, 0), (-0.5, 2, -0.25, 2), (1e3, 1, 2.5, 1)]
        for num, dpn, den, dpd in cases:
            span = R.quotient_interval(num, dpn, den, dpd)
            assert span is not None
            hn, hd = R.half_width(dpn), R.half_width(dpd)
            worst_lo, worst_hi = span
            for i, j in itertools.product(range(41), repeat=2):
                x = num - hn + 2 * hn * i / 40
                y = den - hd + 2 * hd * j / 40
                if y == 0:
                    continue
                q = x / y
                assert worst_lo - 1e-9 <= q <= worst_hi + 1e-9, (num, den, q, span)

    def test_the_window_depends_on_the_denominators_magnitude(self):
        """This is why a constant cannot work. Identical printed precisions,
        two orders of magnitude between the resulting windows."""
        wide = R.quotient_interval(0.12, 2, 0.05, 2)
        narrow = R.quotient_interval(2.00, 2, 5.00, 2)
        assert (wide[1] - wide[0]) > 100 * (narrow[1] - narrow[0])

    def test_a_denominator_interval_reaching_zero_is_refused(self):
        """SE printed 0.0 to one decimal could be anything in [-0.05, 0.05];
        B/SE is unbounded and no comparison means anything."""
        assert R.quotient_interval(2.0, 1, 0.0, 1) is None

    def test_a_negative_numerator_is_handled(self):
        """Corner evaluation, not a first-order approximation: the quotient is
        not monotone across a sign change."""
        lo, hi = R.quotient_interval(-2.0, 1, 0.5, 1)
        assert lo < hi < 0


class TestDecimalsOfValue:
    def test_an_integral_value_reads_as_zero_decimals(self):
        """`2`, `2.0` and `2.00` are indistinguishable once parsed, and 0 dp is
        the only one of the three whose interval cannot be too tight."""
        assert R.decimals_of_value(2.0) == 0
        assert R.decimals_of_value(2) == 0

    def test_otherwise_it_reads_the_repr(self):
        assert R.decimals_of_value(1.234) == 3

    def test_it_errs_wide_on_trailing_zeros(self):
        """`repr(1.40)` is "1.4", so this reads 1 dp -- ten times too LOOSE,
        which misses findings rather than manufacturing them."""
        assert R.decimals_of_value(1.40) == 1

    @pytest.mark.parametrize("bad", [None, "x", float("nan"), float("inf")])
    def test_it_refuses_what_it_cannot_read(self, bad):
        assert R.decimals_of_value(bad) is None


class TestRegressionUsesAnInterval:
    def test_a_small_se_widens_the_window_enormously(self):
        """B = 0.12, SE = 0.05, both at 2 dp: t is anywhere in roughly
        [2.09, 2.78]. The old flat `|dt| < 0.1` around 2.4 accused every
        reported t outside a window a fifth as wide."""
        r = check_regression(0.12, 0.05, reported_t=2.1,
                             decimals_b=2, decimals_se=2, decimals_t=1)
        assert r["t_matches"] is True
        assert r["severity"] == "consistent"

    def test_a_large_se_narrows_it(self):
        r = check_regression(2.00, 5.00, reported_t=0.9,
                             decimals_b=2, decimals_se=2, decimals_t=1)
        assert r["t_matches"] is False

    def test_a_genuine_discrepancy_is_still_caught(self):
        """The fix must not be "widen until nothing fires"."""
        r = check_regression(1.34, 0.60, reported_t=9.99,
                             decimals_b=2, decimals_se=2, decimals_t=2)
        assert r["t_matches"] is False
        assert r["severity"] == "suspicious"

    def test_an_se_interval_reaching_zero_is_indeterminate_not_a_pass(self):
        r = check_regression(2.0, 0.04, reported_t=50.0,
                             decimals_b=1, decimals_se=1, decimals_t=1)
        assert r["severity"] == "indeterminate"
        assert r["t_matches"] is None

    def test_inferred_precision_is_declared(self):
        r = check_regression(2.0, 0.5, reported_t=4.0)
        assert set(r["precision_inferred"]) == {"b", "se"}

    def test_supplying_precision_actually_narrows_the_window(self):
        """The load-bearing claim. A version accepting the `decimals_*` and
        then discarding them passed every other test in this class."""
        row = {"b": 0.120, "se": 0.050, "reported_t": 2.40}
        loose = check_regression_batch([dict(row)])["results"][0]
        tight = check_regression_batch([dict(row, decimals_b=3, decimals_se=3,
                                             decimals_t=2)])["results"][0]
        lw = loose["t_interval"][1] - loose["t_interval"][0]
        tw = tight["t_interval"][1] - tight["t_interval"][0]
        assert tw < lw / 5, (tw, lw)
        assert "precision_inferred" not in tight

    def test_the_p_branch_uses_the_interval_not_the_point(self):
        """B = 0.11, SE = 0.05 and t = 2.46 all print correctly from
        B = 0.1148, SE = 0.0467. Testing the point p against a window while
        testing the t against an interval cleared the t and convicted the p --
        the same failure the interval work removed, one branch down."""
        r = check_regression(0.11, 0.05, reported_t=2.46, reported_p=0.0199, df=30,
                             decimals_b=2, decimals_se=2, decimals_t=2, decimals_p=4)
        assert r["t_matches"] is True
        assert r["p_matches"] is True
        assert r["severity"] == "consistent"

    def test_the_batch_carries_the_p_precision_too(self):
        out = check_regression_batch([
            {"b": 0.11, "se": 0.05, "reported_t": 2.46, "reported_p": 0.0199,
             "df": 30, "decimals_b": 2, "decimals_se": 2, "decimals_p": 4},
        ])
        assert out["results"][0]["p_matches"] is True

    def test_a_window_wider_than_the_estimate_is_indeterminate_not_consistent(self):
        """B = 0.03, SE = 0.01 at 2 dp admits any t from 1.67 to 7.00. The
        arithmetic is right and the check has no power; reporting `consistent`
        is the false-clear this codebase has had to fix in three batch tools."""
        r = check_regression(0.03, 0.01, reported_t=6.90,
                             decimals_b=2, decimals_se=2, decimals_t=2)
        assert r["severity"] == "indeterminate"
        assert r["low_power"] is True

    def test_unreadable_input_yields_no_verdict(self):
        """A NaN coefficient gave a NaN interval, a False `t_matches` and a
        `suspicious` accusation against a cell nobody could read."""
        r = check_regression(float("nan"), 0.5, reported_t=4.0)
        assert r["severity"] == "indeterminate"
        assert "not a finite number" in r["error"]


class TestRegressionConventions:
    """Two conventions the signed/two-tailed check rejected as fabrication."""

    def test_a_reported_absolute_t_matches_a_negative_coefficient(self):
        """A regression table printing |t| = 2.20 for B = -0.11, SE = 0.05 is
        correct arithmetic -- |B|/SE = 2.2 -- but the signed interval is
        [-2.56, -1.91] and the old check flagged it `suspicious`. Match on
        magnitude too; record the sign disagreement without escalating."""
        r = check_regression(b=-0.11, se=0.05, reported_t=2.20,
                             decimals_b=2, decimals_se=2, decimals_t=2)
        assert r["t_matches"] is True
        assert r["severity"] == "consistent"
        assert r["sign_mismatch"] is True

    def test_a_wrong_magnitude_is_not_rescued_by_the_sign_guard(self):
        """The magnitude convention must not become "accept any |t|". A reported
        t whose MAGNITUDE is wrong still fails under both signs."""
        r = check_regression(b=-0.11, se=0.05, reported_t=9.99,
                             decimals_b=2, decimals_se=2, decimals_t=2)
        assert r["t_matches"] is False
        assert r["severity"] == "suspicious"

    def test_a_one_sided_p_is_consistent_not_suspicious(self):
        """B = 0.110, SE = 0.050, df = 100 give a two-tailed p ~ 0.028; a
        directional hypothesis reported one-sided prints ~0.014, exactly half.
        The two-tailed-only check flagged every such honest one-sided p."""
        r = check_regression(b=0.110, se=0.050, reported_p=0.014, df=100,
                             decimals_b=3, decimals_se=3, decimals_p=3)
        assert r["p_matches"] is True
        assert r["severity"] == "consistent"
        assert r["p_reconciles_one_sided_only"] is True

    def test_a_p_below_even_the_one_sided_interval_still_fires(self):
        """The one-tailed tolerance only excuses the factor-of-two ambiguity. A
        p claimed far below even the one-sided interval is a real over-claim."""
        r = check_regression(b=0.110, se=0.050, reported_p=0.001, df=100,
                             decimals_b=3, decimals_se=3, decimals_p=3)
        assert r["p_matches"] is False
        assert r["severity"] == "suspicious"

    def test_an_honest_two_sided_p_does_not_trip_the_one_sided_flag(self):
        """When the two-tailed reading already reconciles, the one-sided
        annotation must stay absent -- it marks only the ambiguous case."""
        r = check_regression(b=0.110, se=0.050, reported_p=0.028, df=100,
                             decimals_b=3, decimals_se=3, decimals_p=3)
        assert r["severity"] == "consistent"
        assert "p_reconciles_one_sided_only" not in r

    def test_the_batch_inherits_both_conventions(self):
        """check_regression_batch delegates to check_regression, so a table of
        |t| values against negative coefficients must not read as a wall of
        `suspicious`."""
        out = check_regression_batch([
            {"b": -0.11, "se": 0.05, "reported_t": 2.20,
             "decimals_b": 2, "decimals_se": 2, "decimals_t": 2},
        ])
        assert out["results"][0]["t_matches"] is True
        assert out["severity"] == "consistent"


class TestSummationWindowScales:
    def test_the_window_is_the_sum_of_the_addends_slack(self):
        assert check_summation([5.0] * 20, 100.0, decimals=1,
                               decimals_total=1)["tolerance"] == \
            pytest.approx(1.05, abs=1e-6)

    def test_the_total_contributes_its_own_slack(self):
        """A percentage column printed to 1 dp is routinely totalled as a bare
        `100`, which is 0 dp and worth +/-0.5 -- a third of the window of a
        twenty-row column, contributed by one number. Assuming the total was
        printed as finely as the addends understates it and convicts columns
        that add up."""
        loose = check_summation([5.0] * 20, 100.0, decimals=1, decimals_total=0)
        tight = check_summation([5.0] * 20, 100.0, decimals=1, decimals_total=1)
        assert loose["tolerance"] == pytest.approx(1.5, abs=1e-6)
        assert tight["tolerance"] == pytest.approx(1.05, abs=1e-6)

    def test_an_integral_total_defaults_to_the_widest_reading(self):
        """`100`, `100.0` and `100.00` are indistinguishable once parsed, and
        only the first cannot give a window that is too tight. It costs power,
        which is why `decimals_total` should be passed."""
        assert check_summation([5.0] * 20, 100.0, decimals=1)["tolerance"] == \
            pytest.approx(1.5, abs=1e-6)

    def test_a_short_precise_column_gets_a_tight_window(self):
        """The old flat 0.5 was fifty times too loose here."""
        assert check_summation([50.10, 49.60], 100.00, decimals=2,
                               decimals_total=2)["tolerance"] < 0.02

    def test_per_value_precision_is_accepted(self):
        r = check_summation([50.1, 49.60], 100.0, decimals=[1, 2], decimals_total=1)
        assert r["tolerance"] == pytest.approx(0.05 + 0.005 + 0.05, abs=1e-6)

    def test_a_mismatched_decimals_list_falls_through_to_the_refusal(self):
        """Silently reusing the wrong precisions would be worse than refusing."""
        r = check_summation([1.0, 2.0, 3.0], 6.0, decimals=[1, 1])
        assert r["severity"] == "indeterminate"

    def test_the_batch_refuses_rows_with_no_precision(self):
        out = check_summation_batch([{"values": [48.8, 52.2], "expected_sum": 100.0}])
        assert out["results"][0]["severity"] == "indeterminate"

    def test_the_batch_evaluates_rows_that_do_supply_it(self):
        out = check_summation_batch([
            {"values": [48.8, 52.2], "expected_sum": 100.0, "decimals": 1},
        ])
        assert out["results"][0]["severity"] == "suspicious"

    def test_one_poison_cell_does_not_crash_the_whole_batch(self):
        """A non-numeric extraction artefact ('N/A', a dash) in one row's values
        raises inside check_summation; before the per-row guard it propagated out
        and discarded every other row's valid check for that turn."""
        out = check_summation_batch([
            {"values": [1.0, 2.0, 3.0], "expected_sum": 6.0, "decimals": 1},
            {"values": ["n/a", 2.0], "expected_sum": 5.0, "decimals": 1},
            {"values": [48.8, 52.2], "expected_sum": 100.0, "decimals": 1},
        ])
        sev = {r["row"]: r["severity"] for r in out["results"]}
        assert sev[0] == "consistent"          # the good row survived
        assert sev[1] == "indeterminate"        # the poison row declined, not crashed
        assert sev[2] == "suspicious"           # the real discrepancy still caught
        assert out["n_evaluated"] == 2


class TestPMatchesUsesPrintedPrecision:
    def test_the_fallback_band_is_as_loose_as_advertised(self):
        """At p = .04 the relative band accepts a computed .06 -- across the
        alpha the paper used. This is what the constant costs."""
        assert _p_matches(0.06, 0.04) is True

    def test_printed_precision_closes_it(self):
        assert _p_matches(0.06, 0.04, decimals_p=2) is False

    def test_a_value_inside_the_printed_interval_still_matches(self):
        assert _p_matches(0.0348, 0.035, decimals_p=3) is True

    def test_a_finely_printed_p_gets_a_fine_window(self):
        """`.0312` asserts [.03115, .03125). The fallback's 0.005 is four
        hundred times wider."""
        assert _p_matches(0.0316, 0.0312, decimals_p=4) is False
        assert _p_matches(0.0316, 0.0312) is True

    def test_a_threshold_p_is_not_an_accusation(self):
        """`p < .001` reaches here as reported_p = 0.001 printed to three
        decimals, and a genuine computed p of 1e-12 sits far below that
        interval. A strict two-sided test convicts every correctly reported
        `p < .001` in the literature -- which is most of it."""
        assert _p_matches(1e-12, 0.001, decimals_p=3) is True
        assert _p_matches(1e-7, 0.001, decimals_p=3) is True
        assert _p_matches(1e-12, 0.001, decimals_p=3, p_is_threshold=True) is True

    def test_the_overclaiming_direction_still_convicts(self):
        """Below the interval is a threshold or an understatement; ABOVE it the
        paper reported a smaller p than its own numbers support."""
        assert _p_matches(0.06, 0.04, decimals_p=2) is False
        assert _p_matches(0.0316, 0.0312, decimals_p=4) is False

    def test_an_exact_p_can_be_declared_and_is_then_two_sided(self):
        """Only having checked that the paper printed a value, not a bound."""
        assert _p_matches(1e-12, 0.001, decimals_p=3, p_is_threshold=False) is False

    def test_it_reaches_the_tools_that_share_it(self):
        assert recalc_f_to_p(4.82, 1, 45, reported_p=0.033, decimals_p=3)["p_matches"] is True
        # calc 0.0333 is BELOW .040's interval: true of a BOUND ("p < .040")...
        assert recalc_f_to_p(4.82, 1, 45, reported_p=0.040, decimals_p=3,
                             p_relation="<")["p_matches"] is True
        # ...and, since 1.86.0, an under-claim of an EXACT p. .040 is no
        # conventional bound, so unstated it is read as exact.
        assert recalc_f_to_p(4.82, 1, 45, reported_p=0.040, decimals_p=3)["p_matches"] is False
        # calc 0.0333 is ABOVE .020's interval: the paper claimed more than it has.
        assert recalc_f_to_p(4.82, 1, 45, reported_p=0.020, decimals_p=3)["p_matches"] is False


class TestSdOrSePrecisionChangesTheAnswer:
    """The headline item of the dispatch-hole commit had no behavioural test:
    replacing the printed-precision branch with the old flat 1% left the suite
    byte-identical."""

    def test_the_verdict_moves_with_the_precision(self):
        from metascience_agent.tools.se_sd import check_sd_or_se
        guessed = check_sd_or_se(3.1, 30, reported_as="SD", variable_range=(1, 7))
        printed = check_sd_or_se(3.1, 30, reported_as="SD", variable_range=(1, 7),
                                 decimals=1)
        assert guessed["as_sd"]["sd_plausible"] is False    # flat 1% is too mean
        assert printed["as_sd"]["sd_plausible"] is True     # 3.1 asserts [3.05, 3.15)
        assert guessed["severity"] != printed["severity"]

    def test_the_nested_range_check_agrees_with_the_outer_verdict(self):
        """One payload used to carry `sd_plausible: True` beside a nested
        `severity: impossible` -- the top of the ladder, inside a `consistent`
        result the model reads."""
        from metascience_agent.tools.se_sd import check_sd_or_se
        r = check_sd_or_se(3.1, 30, reported_as="SD", variable_range=(1, 7),
                           decimals=1)
        assert r["as_sd"]["sd_plausible"] is True
        assert r["as_sd"]["sd_range_check"]["severity"] != "impossible"


class TestSdRangeCeiling:
    def test_only_the_bottom_of_the_rounding_interval_must_clear_the_ceiling(self):
        """`max_sd` is a hard mathematical bound -- half the range, corrected
        for n -- so nothing but the value's own rounding entitles it to
        exceed."""
        r = check_sd_range(3.1, 1, 7, n=30, decimals_sd=1)
        assert r["max_possible_sd"] < 3.1           # nominally over the bound
        assert r["is_plausible"] is True            # but within its printed precision
        assert "printed precision" in r["margin_source"]

    def test_a_real_impossibility_is_still_caught(self):
        # bound_source="stated": this test pins the rounding margin, not the
        # bound-provenance cap (which caps the same call at the default
        # `assumed` to `highly_suspicious` -- see test_sd_range_bounds.py).
        r = check_sd_range(3.5, 1, 7, n=30, decimals_sd=1, bound_source="stated")
        assert r["is_plausible"] is False
        assert r["severity"] == "impossible"

    def test_the_inferred_margin_is_named_when_precision_was_not_supplied(self):
        """The fallback used to be a flat 1% -- a margin unrelated to how the
        number was printed, which is 0.035 for an SD of 3.5 and 0.35 for 35, and
        which convicted a coarsely printed SD (a true 4.6 printed "5" under a
        4.75 ceiling). It now infers the precision from the literal, the same
        device the rest of the toolkit uses, and says so."""
        src = check_sd_range(3.0, 1, 7, n=30)["margin_source"]
        assert "inferred" in src
        assert "decimals_sd" in src        # tells the caller how to do better


class TestFToPDf2Unstated:
    """MEASURED FP, 2026-08-22: F(3, df2)=6.951 was flagged against a
    reported p=0.0001 using an ASSUMED df2=20 -- but at df2->inf the same F
    gives p=1.14e-4, which PRINTS as 0.0001. The paper never stated df2.
    With df2 omitted the tool sweeps every df2 and accuses only when none
    explains the reported p (rule 4: an inferred df is an assumed bound)."""

    def test_the_measured_sholl_case_is_consistent_without_df2(self):
        r = recalc_f_to_p(6.951, 3, reported_p=0.0001, decimals_p=4)
        assert r["severity"] == "consistent"
        assert r["df2_unstated"] is True
        assert r["p_matches"] is True

    def test_the_same_case_with_the_assumed_df2_still_mismatches(self):
        # Passing the df the model invented reproduces the FP shape -- the
        # fix is refusing to invent it, not softening the exact-df2 math.
        r = recalc_f_to_p(6.951, 3, 20, reported_p=0.0001, decimals_p=4)
        assert r["p_matches"] is False

    def test_a_p_below_the_infinite_df_floor_is_still_caught(self):
        # F(3,?)=6.951's floor is ~1.1e-4; p=0.00001 is unattainable at ANY
        # df2 -- that accusation needs no assumption, and caps at suspicious.
        r = recalc_f_to_p(6.951, 3, reported_p=0.00001, decimals_p=5)
        assert r["severity"] == "suspicious"
        assert r["p_matches"] is False

    def test_df1_one_falls_back_to_the_tail_wrinkle(self):
        # F(1,?) = t^2: below the two-tailed floor but inside one-tailed ->
        # indeterminate, same as the exact-df2 path's PNAS lesson.
        floor2t = recalc_f_to_p(6.951, 1)["achievable_p_range_over_df2"][0]
        p_between = floor2t * 0.7   # below two-tailed floor, above half of it
        r = recalc_f_to_p(6.951, 1, reported_p=p_between, decimals_p=6)
        assert r["severity"] == "indeterminate"
        assert r["one_tailed_reconciles"] is True

    def test_no_reported_p_is_indeterminate_with_the_range(self):
        r = recalc_f_to_p(6.951, 3)
        assert r["severity"] == "indeterminate"
        lo, hi = r["achievable_p_range_over_df2"]
        assert lo < 1.2e-4 < hi
