"""Partial eta-squared had no tool, and the hand-rolled substitute was the
df1 = 1 special case.

Both halves showed up in one 9-paper batch (MEASURED 2026-08-22):

  * 10.1007--s10803-013-1829-4 prints "F(2, 54) = 51.81, p < .001,
    eta_p^2 = .83". The correct value is 103.62/157.62 = .657. The finding was
    filed under technique `no_tool_exists` -- the schema's own name for
    "arithmetic, but nothing in the registry covers it".
  * 10.1177--0956797615569889 checked four eta-squared values through
    `check_ratio` using F/(F + df2). Right there (every df1 was 1) and wrong in
    general. Nothing enforced the precondition; the model remembered it.
"""
import pytest

from metascience_agent.tools.effect_size_from_f import effect_size_from_f


class TestTheMeasuredCases:
    def test_the_s10803_mismatch_is_flagged(self):
        r = effect_size_from_f(51.81, 2, 54, 0.83,
                               decimals_f=2, decimals_effect_size=2)
        assert r["severity"] == "suspicious"
        assert r["consistent"] is False
        assert r["computed"] == pytest.approx(0.6574, abs=1e-4)

    @pytest.mark.parametrize("f,df2,reported", [
        (7.556, 30, 0.201),
        (14.231, 30, 0.322),
        (4.573, 30, 0.132),
        (33.548, 15, 0.691),
    ])
    def test_the_0956797615569889_values_still_reconcile(self, f, df2, reported):
        """All four had df1 = 1, so the hand-rolled F/(F + df2) agreed with the
        general formula. They must keep passing through the real tool."""
        r = effect_size_from_f(f, 1, df2, reported,
                               decimals_f=3, decimals_effect_size=3)
        assert r["severity"] == "consistent", r["explanation"]

    def test_the_shortcut_and_the_formula_diverge_when_df1_is_not_one(self):
        """The reason the tool exists rather than a check_ratio convention:
        F/(F + df2) understates partial eta-squared for every multi-level
        factor, so an honest paper looks wrong."""
        f, df1, df2 = 51.81, 2, 54
        shortcut = f / (f + df2)
        real = effect_size_from_f(f, df1, df2)["computed"]
        assert shortcut == pytest.approx(0.4896, abs=1e-3)
        assert real == pytest.approx(0.6574, abs=1e-3)


class TestRoundingDiscipline:
    def test_a_value_consistent_at_its_printed_precision_passes(self):
        """Both numbers are rounded, so the comparison is interval to interval.
        Comparing the two points convicts honest rounding."""
        r = effect_size_from_f(51.81, 2, 54, 0.66,
                               decimals_f=2, decimals_effect_size=2)
        assert r["severity"] == "consistent", r["explanation"]

    def test_a_coarsely_printed_f_widens_the_interval(self):
        """F = 52 asserts [51.5, 52.5), which reaches further than F = 51.81."""
        coarse = effect_size_from_f(52, 2, 54, 0.66, decimals_f=0,
                                    decimals_effect_size=2)
        lo, hi = coarse["achievable_interval"]
        assert hi - lo > 0.001
        assert coarse["severity"] == "consistent"


class TestRefusals:
    @pytest.mark.parametrize("measure", [
        "eta_squared", "generalized_eta_squared", "omega_squared", "r_squared",
    ])
    def test_measures_needing_a_total_sum_of_squares_are_refused_by_name(
            self, measure):
        """Scoring these against the partial formula would flag every paper
        that honestly reports generalised eta-squared."""
        r = effect_size_from_f(51.81, 2, 54, 0.83, measure=measure)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False
        # The reason must name what is MISSING, not just say "refused".
        assert any(w in r["error"].lower()
                   for w in ("sum of squares", "measured vs")), r["error"]

    def test_an_unrecognised_measure_is_refused_not_guessed(self):
        r = effect_size_from_f(51.81, 2, 54, 0.83, measure="hedges_g")
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    @pytest.mark.parametrize("df1,df2", [(None, 54), (0, 54), (2, None), (2, 0)])
    def test_a_missing_or_zero_df_refuses(self, df1, df2):
        r = effect_size_from_f(51.81, df1, df2, 0.83)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_no_reported_value_computes_but_does_not_judge(self):
        r = effect_size_from_f(51.81, 2, 54)
        assert r["severity"] == "indeterminate"
        assert r["consistent"] is None
        assert r["computed"] == pytest.approx(0.6574, abs=1e-4)

    def test_non_finite_input_never_reaches_the_arithmetic(self):
        for bad in (float("nan"), float("inf")):
            r = effect_size_from_f(bad, 2, 54, 0.83)
            assert r["severity"] == "indeterminate"
            assert r["applicable"] is False


class TestTheCap:
    def test_nothing_here_reaches_impossible(self):
        """A mismatch has ordinary explanations this arithmetic cannot rule
        out -- a different effect-size family, a value from another model, an F
        corrected for sphericity against uncorrected df."""
        for f, df1, df2, reported in ((51.81, 2, 54, 0.83), (2.0, 3, 20, 0.99),
                                      (0.01, 1, 10, 0.95)):
            r = effect_size_from_f(f, df1, df2, reported)
            assert r["severity"] != "impossible"

    def test_a_flag_names_the_innocent_readings(self):
        r = effect_size_from_f(51.81, 2, 54, 0.83)
        assert "sphericity" in r["alternative_reading"]


class TestCohensF:
    def test_it_follows_from_partial_eta_squared(self):
        pes = effect_size_from_f(51.81, 2, 54)["computed"]
        cf = effect_size_from_f(51.81, 2, 54, measure="cohens_f")["computed"]
        assert cf == pytest.approx((pes / (1 - pes)) ** 0.5, rel=1e-9)
