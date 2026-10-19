"""Tests for statistical recalculation tools."""

import pytest
import math
from forensic_metascience_ai_toolkit.tools.ttest import recalc_independent_t, recalc_within_subjects_t
from forensic_metascience_ai_toolkit.tools.anova import recalc_one_way_anova, recalc_f_to_p
from forensic_metascience_ai_toolkit.tools.chi_squared import recalc_chi_squared
from forensic_metascience_ai_toolkit.tools.sd_checks import check_sd_range
from forensic_metascience_ai_toolkit.tools.summation import check_summation
from forensic_metascience_ai_toolkit.tools.stalt import stalt_check


class TestIndependentTTest:
    """Tests for independent samples t-test recalculation."""

    def test_basic_calculation(self):
        """Test basic t-test calculation."""
        result = recalc_independent_t(
            mean1=10.0, sd1=2.0, n1=30,
            mean2=12.0, sd2=2.0, n2=30,
        )

        # t should be negative (group 1 mean < group 2 mean)
        assert result["calculated_t"] < 0
        # p should be significant for this effect
        assert result["calculated_p"] < 0.05

    def test_matching_p_value(self):
        """Test that we detect matching p-values."""
        result = recalc_independent_t(
            mean1=10.0, sd1=2.0, n1=30,
            mean2=12.0, sd2=2.0, n2=30,
            reported_p=0.0001,  # approximately correct
        )

        # Should be close to matching
        assert "p_matches" in result

    def test_mismatched_p_value(self):
        """Test that we detect mismatched p-values."""
        result = recalc_independent_t(
            mean1=10.0, sd1=2.0, n1=30,
            mean2=10.5, sd2=2.0, n2=30,  # small difference
            reported_p=0.001,  # way too small
        )

        assert result["p_matches"] == False


class TestANOVA:
    """Tests for one-way ANOVA recalculation."""

    def test_fujii_table1_example(self):
        """
        Test the Fujii Table 1 example from Heathers doc.

        Mean age (SD): 41(12), 41(12), 41(12), 42(12) for n=30 each
        This should return a very small F and very large p.
        """
        result = recalc_one_way_anova(
            means=[41, 41, 41, 42],
            sds=[12, 12, 12, 12],
            ns=[30, 30, 30, 30],
        )

        # Paper reports F=0.0521, p=0.9842
        assert abs(result["calculated_f"] - 0.0521) < 0.01
        assert abs(result["calculated_p"] - 0.9842) < 0.01

    def test_significant_anova(self):
        """Test ANOVA with significant differences."""
        result = recalc_one_way_anova(
            means=[10, 15, 20],
            sds=[2, 2, 2],
            ns=[30, 30, 30],
        )

        assert result["calculated_p"] < 0.001

    def test_p_branch_uses_the_achievable_interval_not_the_point(self):
        """The F branch propagated the mean/SD rounding into an F interval; the p
        branch compared the reported p only to the POINT p, so an honest report
        whose F is achievable and whose p is the p OF that achievable F was
        flagged. Now both branches use the interval."""
        r = recalc_one_way_anova(
            means=[10.06, 10.94, 10.50], sds=[0.96, 0.96, 0.96], ns=[20, 20, 20],
            reported_f=4.2, reported_p=0.020, decimals_mean=1, decimals_sd=1, decimals_p=3,
        )
        assert r["f_matches"] is True and r["p_matches"] is True
        assert r["severity"] == "consistent"

    def test_a_genuinely_wrong_anova_p_is_still_flagged(self):
        r = recalc_one_way_anova(
            means=[10.0, 10.1, 10.2], sds=[1.0, 1.0, 1.0], ns=[20, 20, 20],
            reported_p=0.0001, decimals_mean=1, decimals_sd=1, decimals_p=4,
        )
        assert r["severity"] == "suspicious"


class TestFtoP:
    def test_a_rounded_F_gives_a_p_interval_not_a_point(self):
        # true F 2.049 prints "F(1,10)=2.0"; the honest p .18 (p of the true F)
        # was flagged against the point p of F=2.0 (~.19). The interval covers it.
        r = recalc_f_to_p(2.0, 1, 10, reported_p=0.18, decimals_p=2, decimals_f=1)
        assert r["p_matches"] is True
        assert r["severity"] == "consistent"

    def test_an_under_claimed_bound_is_tolerated_an_exact_p_is_not(self):
        # p = .33 for F = 2.0 (true p ~ .19) reports LESS significance than the F
        # supports. As a BOUND ("p < .33") that is true and tolerated. As an
        # EXACT value it is a reporting inconsistency -- this test asserted it
        # was tolerated until 1.86.0 -- capped at `suspicious` because
        # fabrication inflates significance, it does not deflate it.
        r = recalc_f_to_p(2.0, 1, 10, reported_p=0.33, decimals_p=2, decimals_f=1,
                          p_relation="<")
        assert r["severity"] == "consistent"
        r = recalc_f_to_p(2.0, 1, 10, reported_p=0.33, decimals_p=2, decimals_f=1)
        assert r["severity"] == "suspicious"
        assert r["failure_mode"] == "reported_p_above_recomputed"

    def test_a_significance_overclaim_is_flagged(self):
        # p = .001 for F = 2.0 claims FAR more significance than achievable.
        r = recalc_f_to_p(2.0, 1, 10, reported_p=0.001, decimals_p=3, decimals_f=1)
        assert r["severity"] == "suspicious"


class TestChiSquared:
    """Tests for chi-squared recalculation."""

    def test_2x2_table(self):
        """Test basic 2x2 contingency table."""
        result = recalc_chi_squared(
            observed=[[10, 20], [30, 40]],
        )

        assert "calculated_chi2" in result
        assert "calculated_p" in result
        assert "fisher_p" in result  # Should have Fisher's for 2x2

    def test_yates_correction(self):
        """Test Yates continuity correction."""
        observed = [[5, 15], [25, 35]]

        result_no_yates = recalc_chi_squared(observed, use_yates=False)
        result_with_yates = recalc_chi_squared(observed, use_yates=True)

        # Yates correction reduces chi-squared
        assert result_with_yates["calculated_chi2"] < result_no_yates["calculated_chi2"]


class TestWithinSubjectsT:
    """Tests for within-subjects t-test analysis."""

    def test_valid_correlation(self):
        """Test case where recovered correlation is valid."""
        result = recalc_within_subjects_t(
            mean_pre=10.0, sd_pre=2.0,
            mean_post=12.0, sd_post=2.5,
            n=30,
            reported_p=0.001,
        )

        # Correlation should be between -1 and 1
        if result["recovered_correlation"] is not None:
            assert result["correlation_valid"] == True

    def test_a_recovered_r_just_over_1_from_rounding_is_not_accused(self):
        """When the SDs differ, r can legitimately approach
        (sd_pre^2+sd_post^2)/(2 sd_pre sd_post) > 1, so a rounded p at the
        boundary recovers r just over 1. p = 0.001 here gives point r = 1.0001,
        but across p's own 3-dp interval a valid r is reachable (r = 0.997 at
        p = 0.0015). The reported numbers are reconcilable at their precision, so
        this must decline, not accuse.

        p is 0.0009 rather than 0.001 so that the rounding-box logic is what is
        under test: a bare 0.001 is now refused earlier as an ambiguous
        threshold reading, which would pass this test for the wrong reason."""
        result = recalc_within_subjects_t(
            mean_pre=50.0, sd_pre=10.0, mean_post=52.0, sd_post=13.0,
            n=30, reported_p=0.0009, p_tail="two",
        )
        assert result["recovered_correlation"] > 1  # the point estimate is invalid
        assert result["severity"] == "indeterminate"
        lo, hi = result["attainable_r_interval"]
        assert lo <= 1.0 <= hi or lo <= 1.0  # the interval reaches the valid range

    def test_an_r_far_outside_even_across_rounding_still_flags(self):
        """r ~ 2.1: the attainable interval over the rounding box stays entirely
        above 1, so the tension between the reported p and the pre/post change is
        robust to rounding -- still highly_suspicious (never impossible)."""
        result = recalc_within_subjects_t(
            mean_pre=50.0, sd_pre=10.0, mean_post=51.0, sd_post=40.0,
            n=50, reported_p=0.0001, p_tail="two",
        )
        assert result["severity"] == "highly_suspicious"
        lo, hi = result["attainable_r_interval"]
        assert lo > 1.0

    def test_a_valid_correlation_stays_consistent(self):
        result = recalc_within_subjects_t(
            mean_pre=50.0, sd_pre=10.0, mean_post=52.0, sd_post=10.0,
            n=30, reported_p=0.007, p_tail="two",
        )
        assert result["severity"] == "consistent"

    def test_a_threshold_p_is_still_indeterminate(self):
        result = recalc_within_subjects_t(
            mean_pre=50.0, sd_pre=10.0, mean_post=52.0, sd_post=13.0,
            n=30, reported_p="<0.05", p_tail="two",
        )
        assert result["severity"] == "indeterminate"


class TestSDRangeCheck:
    """Tests for SD range validation."""

    def test_valid_sd(self):
        """Test SD within valid range."""
        result = check_sd_range(sd=2.0, min_val=1, max_val=10)
        assert result["is_plausible"] is True

    def test_impossible_sd(self):
        """Test SD exceeding maximum possible."""
        # For range 1-10 (range=9), max SD ≈ 4.5
        result = check_sd_range(sd=10.0, min_val=1, max_val=10)
        assert result["is_plausible"] is False

    def test_binary_sd_limit(self):
        """
        Test that binary data can't have SD > 0.5.

        For 0/1 data, max SD = 0.5 (when 50% are 0 and 50% are 1)
        """
        result = check_sd_range(sd=0.75, min_val=0, max_val=1)
        assert result["is_plausible"] is False


class TestSummation:
    """Tests for summation checks."""

    def test_percentages_sum_to_100(self):
        """Test that percentages summing to 100 pass."""
        result = check_summation(
            values=[30.0, 45.0, 25.0],
            expected_sum=100.0,
            description="percentages",
            decimals=1,
            decimals_total=1,
        )
        assert result["is_consistent"] is True

    def test_percentages_exceed_100(self):
        """
        Test the example where percentages sum to > 100.

        From Heathers doc: "48.8% + 52.2% = 101%"
        """
        result = check_summation(
            values=[48.8, 52.2],
            expected_sum=100.0,
            description="binary percentages",
            decimals=1,
            decimals_total=1,
        )
        assert result["is_consistent"] is False
        assert result["difference"] == pytest.approx(1.0, abs=0.1)
        # 1.0 is far outside what two 1 dp values and a 1 dp total permit.
        assert result["tolerance"] < 0.2

    def test_no_printed_precision_refuses_rather_than_guessing(self):
        """There is no safe default window. Inferring from the parsed floats
        reads a percentage printed "5" as 5.0 and is ten times too tight;
        widening every integral value to 0 dp gives a twenty-value column
        +/-10 percentage points, which clears anything."""
        result = check_summation(values=[48.8, 52.2], expected_sum=100.0)
        assert result["severity"] == "indeterminate"
        assert result["is_consistent"] is None
        assert "decimals" in result["error"]

    def test_the_window_grows_with_the_number_of_addends(self):
        """Twenty values at 1 dp permit +/-1.0; two permit +/-0.1. A flat 0.5 --
        the old default -- is wrong in both directions."""
        wide = check_summation(values=[5.0] * 20, expected_sum=100.0,
                               decimals=1, decimals_total=1)
        narrow = check_summation(values=[50.0, 50.0], expected_sum=100.0,
                                 decimals=1, decimals_total=1)
        assert wide["tolerance"] == pytest.approx(1.05, abs=1e-6)
        assert narrow["tolerance"] == pytest.approx(0.15, abs=1e-6)

    def test_an_explicit_tolerance_still_wins(self):
        """A count column must hold exactly; rounding is not what sets its
        window."""
        result = check_summation(values=[10.0, 20.0], expected_sum=31.0,
                                 tolerance=0, decimals=0)
        assert result["is_consistent"] is False
        assert result["tolerance_basis"] == "explicit tolerance"


class TestSTALT:
    """Tests for STALT (Smaller Than A Lowest Threshold)."""

    def test_normal_p_value(self):
        """Test p-value that matches threshold."""
        result = stalt_check(calculated_p=0.03, reported_threshold="<0.05")
        assert result["severity"] == "consistent"

    def test_a_tiny_p_that_satisfies_the_bound_is_consistent(self):
        """A p far below a "<" threshold does NOT contradict it.

        This used to assert `highly_suspicious` for p=1e-15 reported as "< .05"
        -- but "p < .05" claims only that p < .05, which 1e-15 satisfies, so the
        printed statement is TRUE. A large test statistic naturally produces a
        tiny p, and style rules (APA: "p < .001" for any p below .001) mandate
        reporting it as a floor. Raising the tool's second-highest severity on a
        true statement is a false accusation; the gap is kept as informational
        detail. Only a p ABOVE the claimed bound contradicts it.
        """
        result = stalt_check(calculated_p=1e-15, reported_threshold="<0.05")
        assert result["severity"] == "consistent"
        assert result["orders_of_magnitude_smaller"] > 10  # kept, informational

    def test_wound_healing_example(self):
        """
        Test recalculated p-values from wound healing paper.

        From Heathers doc:
        - BMI: t=6.5624, p=1.677e-10 (reported as p<0.001)
        """
        result = stalt_check(calculated_p=1.677e-10, reported_threshold="<0.001")
        # This is 7 orders of magnitude smaller than 0.001
        assert result["orders_of_magnitude_smaller"] > 5


class TestStaltStyleFloor:
    """STALT must not accuse a true "p < X" statement.

    A p far below a "<" threshold satisfies it, so the printed claim is true;
    that is style-floor reporting (APA mandates "p < .001" for any p below
    .001), not fraud. Only a p ABOVE the claimed bound contradicts it, graded
    by overshoot: a factor of 2 is the one/two-tailed slack.
    """

    def test_bound_satisfied_however_small_is_consistent(self):
        from forensic_metascience_ai_toolkit.tools.stalt import stalt_check
        assert stalt_check(1e-15, "<0.001")["severity"] == "consistent"
        assert stalt_check(0.0009, "<0.001")["severity"] == "consistent"

    def test_a_real_bound_violation_is_flagged(self):
        from forensic_metascience_ai_toolkit.tools.stalt import stalt_check
        assert stalt_check(0.04, "<0.001")["severity"] == "highly_suspicious"  # 40x
        assert stalt_check(0.006, "<0.001")["severity"] == "suspicious"        # 6x

    def test_within_tail_slack_is_indeterminate_not_accused(self):
        from forensic_metascience_ai_toolkit.tools.stalt import stalt_check
        # 1.5x above the bound: a one-tailed p read as two-tailed explains it.
        assert stalt_check(0.0015, "<0.001")["severity"] == "indeterminate"


class TestChiSquaredYatesOrPearson:
    """recalc_chi_squared compared a 2x2 paper's statistic only to the
    UNcorrected Pearson chi2, so a paper reporting the Yates-corrected value
    (R's chisq.test default) was flagged. It now accepts EITHER convention.
    """

    def test_a_yates_corrected_value_matches(self):
        r = recalc_chi_squared([[15, 5], [8, 12]], reported_chi2=3.68,
                               reported_p=0.055, decimals_p=3)
        assert r["chi2_matches"] is True
        assert r["severity"] == "consistent"

    def test_the_pearson_value_still_matches(self):
        r = recalc_chi_squared([[15, 5], [8, 12]], reported_chi2=5.01,
                               reported_p=0.025, decimals_p=3)
        assert r["chi2_matches"] is True

    def test_a_value_matching_neither_is_flagged(self):
        r = recalc_chi_squared([[15, 5], [8, 12]], reported_chi2=9.9,
                               reported_p=0.002, decimals_p=3)
        assert r["chi2_matches"] is False
        assert r["severity"] in ("suspicious", "highly_suspicious")


class TestChiSquaredThresholdP:
    """A bare threshold p must not be judged by a SYMMETRIC band.

    Without `decimals_p` the shared `_p_matches` drops into a precision-free
    fallback that treats both directions alike, and a symmetric test on a p is
    the defect already fixed in three other tools: it convicts the commonest
    convention in the literature. The precision is now inferred from the value
    so the DIRECTIONAL branch applies -- under-claims pass, over-claims flag.
    """

    #: chi2 = 18.0, true p = 2.2e-05, so "p < .05" is a TRUE statement.
    STRONG = [[20, 5], [5, 20]]

    def test_an_honest_threshold_claim_is_not_accused(self):
        r = recalc_chi_squared(self.STRONG, reported_chi2=18.0, reported_p=0.05)
        assert r["p_matches"] is True
        assert r["severity"] == "consistent"

    def test_the_inferred_precision_is_reported(self):
        r = recalc_chi_squared(self.STRONG, reported_chi2=18.0, reported_p=0.05)
        assert r["decimals_p_inferred"] == 2

    def test_an_explicit_precision_is_not_overridden(self):
        r = recalc_chi_squared(self.STRONG, reported_chi2=18.0, reported_p=0.05,
                               decimals_p=2)
        assert "decimals_p_inferred" not in r
        assert r["severity"] == "consistent"

    def test_an_over_claim_still_flags(self):
        """Tolerating the under-claim direction must not tolerate the
        fabrication direction: a weak table reported at p = .001 is caught."""
        r = recalc_chi_squared([[13, 12], [8, 17]], reported_p=0.001,
                               decimals_p=3)
        assert r["p_matches"] is False
        assert r["severity"] == "suspicious"


class TestTTestAcceptsBothConventions:
    """The t/F recomputation flagged legitimate reporting choices.

    (A) The achievable interval was Welch-only, so a correct pooled
    (equal-variance) t at unequal n/SD was highly_suspicious. (B) Only the
    two-tailed p was computed, so a legitimate one-tailed report was flagged.
    (C) A fixed 0.1 absolute window ignored that input rounding propagates
    MULTIPLICATIVELY into F/t, convicting honest papers at large F.
    Both readings are now accepted; only a value explained by NEITHER standard
    test/tail, and outside the reachable rounding interval, is flagged.
    """

    def test_a_correct_pooled_t_is_accepted(self):
        from forensic_metascience_ai_toolkit.tools.rivets import rivets_independent_t
        r = rivets_independent_t(105.00, 10.00, 20, 100.00, 20.00, 60,
                                 reported_t=1.07, reported_p=0.287,
                                 decimals_mean=2, decimals_sd=2,
                                 decimals_t=2, decimals_p=3)
        assert r["severity"] == "consistent"

    def test_a_one_tailed_p_is_accepted(self):
        from forensic_metascience_ai_toolkit.tools.rivets import rivets_independent_t
        r = rivets_independent_t(5.30, 1.20, 30, 4.80, 1.20, 30,
                                 reported_t=1.61, reported_p=0.056,
                                 decimals_mean=2, decimals_sd=2,
                                 decimals_t=2, decimals_p=3)
        assert r["severity"] == "consistent"

    def test_a_t_explained_by_no_standard_reading_is_flagged(self):
        from forensic_metascience_ai_toolkit.tools.rivets import rivets_independent_t
        r = rivets_independent_t(105.00, 10.00, 20, 100.00, 20.00, 60,
                                 reported_t=2.5, decimals_mean=2,
                                 decimals_sd=2, decimals_t=2)
        assert r["severity"] == "highly_suspicious"

    def test_a_genuinely_unreachable_F_stays_flagged(self):
        """894.64 for these inputs is genuinely outside the reachable F
        interval [625.58, 643.72] -- the multiplicative-tolerance fix must not
        excuse it."""
        r = recalc_one_way_anova([10.09, 15.01], [0.92, 1.03], [50, 50],
                                 reported_f=894.64)
        assert r["f_matches"] is False
