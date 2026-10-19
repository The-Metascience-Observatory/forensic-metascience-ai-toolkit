"""Tests for continuous→categorical proportion plausibility."""

import pytest

from metascience_agent.tools.continuous_to_categorical import (
    check_proportion_from_normal,
)


class TestKhadilkar2010:
    """Heathers' worked example: WAZ mean=-1.67, SD=0.89, n=172, 35.5% < -2.

    Theoretical Φ((-2 - -1.67)/0.89) = Φ(-0.371) ≈ 0.355 — matches reported.
    """

    def test_consistent(self):
        result = check_proportion_from_normal(
            reported_proportion=0.355, mean=-1.67, sd=0.89, n=172,
            threshold=-2.0, direction="below", num_simulations=2000, seed=0,
        )
        assert result["severity"] == "consistent"
        assert result["theoretical_proportion"] == pytest.approx(0.355, abs=0.005)
        # The reported is essentially the theoretical; binomial p should be ~1.
        assert result["binomial_p_two_sided"] > 0.5

    def test_above_direction(self):
        # 64.5% above -2 should also be consistent.
        result = check_proportion_from_normal(
            reported_proportion=0.645, mean=-1.67, sd=0.89, n=172,
            threshold=-2.0, direction="above", num_simulations=2000, seed=0,
        )
        assert result["severity"] == "consistent"


class TestImplausibleCases:
    def test_far_outside_normal_is_a_distribution_free_violation(self):
        """80% at least 2 SDs below the mean is impossible for ANY distribution:
        Cantelli caps the mass 2 SDs into a tail at 1/(1+4) = 20%. So this earns
        `highly_suspicious` with no distributional assumption."""
        result = check_proportion_from_normal(
            reported_proportion=0.80, mean=0.0, sd=1.0, n=100,
            threshold=-2.0, direction="below", num_simulations=2000, seed=0,
        )
        assert result["severity"] == "highly_suspicious"
        assert result["distribution_free_violation"] is True

    def test_zero_below_the_mean_is_only_suspicious_not_accused(self):
        """0% below the mean contradicts a NORMAL model (which is symmetric, 50%),
        but not every distribution: a left-skewed variable with mean 0, SD 1 can
        put ~1% of its mass below the mean (e.g. 0.01 at -9.95, 0.99 at +0.1), so
        0/100 is achievable. The old code called this `highly_suspicious` -- a
        false accusation that assumed symmetry. It is a question, not a verdict."""
        result = check_proportion_from_normal(
            reported_proportion=0.0, mean=0.0, sd=1.0, n=100,
            threshold=0.0, direction="below", num_simulations=500, seed=0,
        )
        assert result["severity"] == "suspicious"
        assert result["distribution_free_violation"] is False

    def test_a_skewed_variables_tail_is_not_an_accusation(self):
        """A legitimate proportion for a right-skewed variable (an ordinary
        lognormal with mean 50, SD 40 has 2.8% above 150) was flagged
        `highly_suspicious` by the normal model (p ~ 1e-8). It is within the
        distribution-free bound, so a skewed distribution explains it: cap at
        `suspicious`, never accuse."""
        result = check_proportion_from_normal(
            reported_proportion=0.028, mean=50.0, sd=40.0, n=800,
            threshold=150.0, direction="above", num_simulations=2000, seed=0,
        )
        assert result["severity"] == "suspicious"
        assert result["distribution_free_violation"] is False

    def test_a_proportion_no_distribution_can_produce_is_flagged(self):
        """30% of the mass 3 SDs above the mean is impossible for any
        distribution (Cantelli max = 1/(1+9) = 10%), so it stays accusation-grade
        even without assuming normality."""
        result = check_proportion_from_normal(
            reported_proportion=0.30, mean=50.0, sd=10.0, n=500,
            threshold=80.0, direction="above", num_simulations=2000, seed=0,
        )
        assert result["severity"] == "highly_suspicious"
        assert result["distribution_free_violation"] is True


class TestPreconditionFailuresAreRefusals:
    """A precondition we could not verify is `indeterminate`, never a verdict.

    Both branches here returned `impossible` -- the strongest claim the system
    can make -- for problems that live entirely on OUR side of the call. `n < 1`
    in the same function, and debit.py:124-144 for the identical situation,
    already answered `indeterminate`.
    """

    def test_proportion_outside_unit_interval(self):
        result = check_proportion_from_normal(
            reported_proportion=1.5, mean=0.0, sd=1.0, n=10, threshold=0,
        )
        assert result["severity"] == "indeterminate"

    def test_a_percentage_passed_as_a_proportion_is_not_an_accusation(self):
        """The realistic version: the paper printed 35.5%, and 35.5 was passed."""
        result = check_proportion_from_normal(
            reported_proportion=35.5, mean=1.0, sd=1.0, n=100, threshold=0.5,
        )
        assert result["severity"] == "indeterminate"
        assert "percentage" in result["explanation"].lower()

    def test_negative_sd(self):
        result = check_proportion_from_normal(
            reported_proportion=0.5, mean=0.0, sd=-1.0, n=10, threshold=0,
        )
        assert result["severity"] == "indeterminate"

    def test_zero_sd(self):
        result = check_proportion_from_normal(
            reported_proportion=0.5, mean=0.0, sd=0.0, n=10, threshold=0,
        )
        assert result["severity"] == "indeterminate"


class TestEdgeCases:
    def test_invalid_direction(self):
        result = check_proportion_from_normal(
            reported_proportion=0.5, mean=0.0, sd=1.0, n=10, threshold=0,
            direction="sideways",
        )
        assert result["severity"] == "indeterminate"

    def test_seed_reproducibility(self):
        a = check_proportion_from_normal(
            0.355, -1.67, 0.89, 172, -2.0, "below", num_simulations=500, seed=42,
        )
        b = check_proportion_from_normal(
            0.355, -1.67, 0.89, 172, -2.0, "below", num_simulations=500, seed=42,
        )
        assert a["mc_mean_proportion"] == b["mc_mean_proportion"]
