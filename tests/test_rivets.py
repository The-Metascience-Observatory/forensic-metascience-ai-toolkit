"""Tests for RIVETS (Rounded Input Variables, Exact Test Statistics)."""

import pytest

from metascience_agent.tools.rivets import (
    rivets_independent_t,
    rivets_anova,
    _half_width,
    _matches_at_precision,
)


class TestHelpers:
    def test_half_width(self):
        assert _half_width(2) == pytest.approx(0.005)
        assert _half_width(3) == pytest.approx(0.0005)
        assert _half_width(0) == pytest.approx(0.5)

    def test_matches_at_precision(self):
        assert _matches_at_precision(0.876, 0.876, 3) is True
        assert _matches_at_precision(0.8762, 0.876, 3) is True  # within ±0.0005
        assert _matches_at_precision(0.881, 0.876, 3) is False
        assert _matches_at_precision(0.876, None, 3) is False


class TestHeathersWorkedExample:
    """The intro doc's RIVETS example reproduces analytic extrema:
       t_max ≈ 1.0006 (M1+, M2-, both SDs at low end)
       t_min ≈ 0.7554 (M1-, M2+, both SDs at high end)
       point_t ≈ 0.876 at the truncated inputs.
    """

    def test_analytic_extrema_match_intro(self):
        result = rivets_independent_t(
            mean1=1.71, sd1=0.22, n1=25,
            mean2=1.63, sd2=0.40, n2=25,
            decimals_mean=2, decimals_sd=2,
            num_samples=2000, seed=0,
        )
        # Heathers' values are 1.0006 and 0.7554 (4dp).
        assert result["t_max"] == pytest.approx(1.0006, abs=1e-3)
        assert result["t_min"] == pytest.approx(0.7554, abs=1e-3)

    def test_point_estimate_matches_reported(self):
        result = rivets_independent_t(
            mean1=1.71, sd1=0.22, n1=25,
            mean2=1.63, sd2=0.40, n2=25,
            reported_t=0.876, decimals_t=3,
            num_samples=2000, seed=0,
        )
        # Heathers' point t = 0.876 at the truncated inputs.
        assert result["point_t_at_truncated"] == pytest.approx(0.876, abs=5e-4)
        assert result["point_matches_reported_t"] is True

    def test_rivets_hit_flagged_highly_suspicious(self):
        """When reported t exactly equals point t and MC hit rate is low,
        severity should escalate to highly_suspicious."""
        result = rivets_independent_t(
            mean1=1.71, sd1=0.22, n1=25,
            mean2=1.63, sd2=0.40, n2=25,
            reported_t=0.876, reported_p=0.385,
            decimals_t=3, decimals_p=3,
            num_samples=3000, seed=42,
        )
        assert result["severity"] == "highly_suspicious"
        # MC hit rate should be small (point estimate is one specific value).
        assert result["monte_carlo"]["fraction_match_reported_t"] < 0.10


class TestEdgeCases:
    def test_reported_t_outside_range(self):
        """If reported t is impossible given the truncation precision, flag it."""
        result = rivets_independent_t(
            mean1=1.71, sd1=0.22, n1=25,
            mean2=1.63, sd2=0.40, n2=25,
            reported_t=5.0,  # massively outside [0.75, 1.00]
            num_samples=500,
        )
        assert result["severity"] == "highly_suspicious"
        assert result["reported_t_in_range"] is False
        assert "OUTSIDE" in result["explanation"]

    def test_overlapping_means(self):
        """If means' truncation intervals overlap, t_min should be 0."""
        # Both means rounded to 1.50, so their intervals are [1.495, 1.505).
        result = rivets_independent_t(
            mean1=1.50, sd1=0.30, n1=20,
            mean2=1.50, sd2=0.30, n2=20,
            num_samples=300,
        )
        assert result["t_min"] == 0.0

    def test_negative_sd_rejected(self):
        result = rivets_independent_t(
            mean1=1.0, sd1=-0.1, n1=10,
            mean2=2.0, sd2=0.1, n2=10,
            num_samples=10,
        )
        # REFUSED, not accused. A negative SD is our parse artefact (an en dash
        # or a range separator read as a minus), never something an analysis
        # prints -- and `impossible` also sat above this tool's declared
        # `probabilistic` ceiling. The sibling `recalc_independent_t` had the
        # right behaviour all along.
        assert result["severity"] == "indeterminate"

    def test_n_too_small(self):
        result = rivets_independent_t(
            mean1=1.0, sd1=0.1, n1=1,
            mean2=2.0, sd2=0.1, n2=10,
            num_samples=10,
        )
        assert result["severity"] == "indeterminate"


class TestRivetsAnova:
    def test_anova_runs_and_returns_ranges(self):
        # Three groups close to each other; F should be small but not zero.
        result = rivets_anova(
            means=[5.00, 5.10, 4.90],
            sds=[1.00, 1.10, 0.90],
            ns=[20, 20, 20],
            reported_f=0.20,
            decimals_mean=2, decimals_sd=2,
            num_samples=500,
            seed=0,
        )
        assert result["f_min"] >= 0
        assert result["f_max"] >= result["f_min"]
        assert "monte_carlo" in result

    def test_anova_input_validation(self):
        result = rivets_anova(
            means=[1.0, 2.0],
            sds=[0.1],  # mismatched
            ns=[10, 10],
        )
        assert result["severity"] == "indeterminate"


class TestReportedPCheck:
    """A paper that prints only a p-value used to slip past RIVETS entirely.

    The severity logic keyed on reported_t / reported_f alone, so a p-value
    nowhere near the achievable interval returned `consistent` while the
    (precision-blind) recalc tools called it suspicious. RIVETS has to catch
    it too before recalc can be retired -- but WITHOUT recalc's fixed
    tolerance, so a p inside the achievable interval stays consistent.
    """

    # Means/SDs printed to 2 dp with n = 120 pin p down to ~1e-6; a paper
    # claiming p = .30 off these descriptives cannot be believed.
    P_ONLY_CASE = dict(
        mean1=10.00, sd1=2.00, n1=120,
        mean2=11.30, sd2=2.00, n2=120,
        num_samples=500,
    )

    def test_reported_p_outside_achievable_is_flagged(self):
        result = rivets_independent_t(reported_p=0.30, decimals_p=2, **self.P_ONLY_CASE)
        assert result["severity"] == "highly_suspicious"
        assert result["reported_p_in_range"] is False
        assert "UNREACHABLE" in result["explanation"]
        # The interval itself comes from the truncation machinery, not a tolerance.
        assert result["p_max"] < 1e-5

    def test_reported_p_inside_achievable_stays_consistent(self):
        """Precision-awareness is the point -- do not accuse a reachable p."""
        result = rivets_independent_t(
            mean1=1.71, sd1=0.22, n1=25,
            mean2=1.63, sd2=0.40, n2=25,
            reported_p=0.385, decimals_p=3,
            num_samples=2000, seed=0,
        )
        assert result["reported_p_in_range"] is True
        assert result["severity"] == "consistent"

    def test_reported_p_within_its_own_rounding_is_not_flagged(self):
        """p = .32 printed at 2 dp stands for [.315, .325); the achievable
        interval starts at ~.3235, so the two overlap and nothing is wrong."""
        result = rivets_independent_t(
            mean1=1.71, sd1=0.22, n1=25,
            mean2=1.63, sd2=0.40, n2=25,
            reported_p=0.32, decimals_p=2,
            num_samples=2000, seed=0,
        )
        assert result["p_min"] > 0.32  # outside if compared as a bare value
        assert result["reported_p_in_range"] is True
        assert result["severity"] == "consistent"

    def test_absent_reported_p_unchanged(self):
        result = rivets_independent_t(
            mean1=1.71, sd1=0.22, n1=25,
            mean2=1.63, sd2=0.40, n2=25,
            num_samples=2000, seed=0,
        )
        assert result["severity"] == "consistent"
        assert result["reported_p_in_range"] is None
        assert result["monte_carlo"]["fraction_match_reported_p"] is None

    def test_threshold_p_is_a_bound_not_a_value(self):
        """'p < .001' against an achievable p of ~1e-6 is a correct report."""
        result = rivets_independent_t(reported_p="<0.001", **self.P_ONLY_CASE)
        assert result["reported_p_is_threshold"] is True
        assert result["reported_p_in_range"] is True
        assert result["severity"] == "consistent"

    def test_threshold_p_flagged_when_unattainable(self):
        """Same bound, but no rounding of the descriptives gets p below .001."""
        result = rivets_independent_t(
            mean1=1.71, sd1=0.22, n1=25,
            mean2=1.63, sd2=0.40, n2=25,
            reported_p="<0.001",
            num_samples=1000, seed=0,
        )
        assert result["severity"] == "highly_suspicious"
        assert result["reported_p_in_range"] is False

    def test_severity_is_worst_of_not_last_wins(self):
        """The wide-interval note is only `suspicious`; it must not mask an
        unreachable p evaluated earlier in the same pass."""
        result = rivets_independent_t(
            mean1=5.0, sd1=1.0, n1=10,
            mean2=4.0, sd2=1.0, n2=10,
            decimals_mean=1, decimals_sd=1,
            reported_p=0.50, decimals_p=2,
            num_samples=1000, seed=0,
        )
        assert result["t_range"] > 0.5  # the clause that would say `suspicious`
        assert result["severity"] == "highly_suspicious"

    def test_anova_reported_p_outside_achievable_is_flagged(self):
        result = rivets_anova(
            means=[5.00, 5.10, 7.90],
            sds=[1.00, 1.10, 0.90],
            ns=[30, 30, 30],
            reported_p=0.42, decimals_p=2,
            num_samples=500, seed=0,
        )
        assert result["severity"] == "highly_suspicious"
        assert result["reported_p_in_range"] is False
        assert "UNREACHABLE" in result["explanation"]

    def test_anova_reported_p_inside_achievable_stays_consistent(self):
        result = rivets_anova(
            means=[5.00, 5.10, 4.90],
            sds=[1.00, 1.10, 0.90],
            ns=[20, 20, 20],
            reported_p=0.80, decimals_p=2,
            num_samples=500, seed=0,
        )
        assert result["reported_p_in_range"] is True
        assert result["severity"] == "consistent"

    def test_undefined_statistic_declines_instead_of_raising(self):
        """recalc answers `indeterminate` on zero SDs; RIVETS used to raise,
        which is not a verdict a caller can act on."""
        t_result = rivets_independent_t(
            mean1=1.0, sd1=0.0, n1=10,
            mean2=2.0, sd2=0.0, n2=10,
            reported_p=0.5, num_samples=50,
        )
        assert t_result["severity"] == "indeterminate"
        anova_result = rivets_anova(
            means=[1.0, 2.0], sds=[0.0, 0.0], ns=[10, 10],
            reported_p=0.5, num_samples=50,
        )
        assert anova_result["severity"] == "indeterminate"

    def test_anova_absent_reported_p_unchanged(self):
        result = rivets_anova(
            means=[5.00, 5.10, 4.90],
            sds=[1.00, 1.10, 0.90],
            ns=[20, 20, 20],
            num_samples=500, seed=0,
        )
        assert result["severity"] == "consistent"
        assert result["reported_p_in_range"] is None
