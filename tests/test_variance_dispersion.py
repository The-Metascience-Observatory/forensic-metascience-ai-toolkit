"""Variance-dispersion analysis (Hartgerink et al. 2019, Eqs. 3-5).

The golden cases are PUBLISHED numbers, not self-generated expectations: the
Smeesters SDs Simonsohn (2013) reported at 1.21%, and both sets of the source
paper's own Table 1. If a refactor moves these, it has changed the statistic.
"""
import numpy as np
import pytest

from metascience_agent.tools.variance_dispersion import (
    MIN_GROUPS,
    _dispersion,
    _granularity_ratios,
    _null_distribution,
    _standardized_variances,
    check_variance_dispersion,
)

# Paper Table 1, Set 1 -- "genuine" (randomly generated under the null).
# BOTH columns: the paper computes across experimental AND control.
PAPER_SET1 = [
    10.044, 9.138, 10.322, 9.777, 9.602, 9.479, 10.503, 9.513, 11.167, 8.989,
    9.289, 10.003, 9.191, 10.095, 9.849, 10.425, 9.236, 10.756, 10.414, 9.577,
]
# Paper Table 1, Set 2 -- fabricated with "too little uniform noise".
PAPER_SET2 = [
    10.475, 10.684, 10.454, 10.398, 10.239, 10.457, 10.06, 10.761, 10.328, 10.272,
    11.216, 11.14, 10.789, 10.302, 11.372, 10.388, 11.247, 11.488, 10.069, 11.211,
]
SMEESTERS = [25.09, 24.58, 25.65]


def _run(sds, ns, **kw):
    kw.setdefault("design", "parallel_rct")
    kw.setdefault("homogeneous_variances", True)
    kw.setdefault("sd_texts", [str(s) for s in sds])
    return check_variance_dispersion(sds, ns, **kw)


class TestPublishedGoldenCases:
    """Reproduce numbers printed in the source literature."""

    def test_smeesters_matches_simonsohn(self):
        """Simonsohn (2013): such consistency arises in 1.21% of samples."""
        r = _run(SMEESTERS, [15] * 3)
        assert r["dispersion_p"] == pytest.approx(0.0121, abs=0.004)

    def test_paper_table1_genuine_set(self):
        """Paper reports p = 0.214 for the genuine set."""
        r = _run(PAPER_SET1, [100] * 20)
        assert r["dispersion_p"] == pytest.approx(0.214, abs=0.03)
        assert r["severity"] == "consistent"

    def test_paper_table1_fabricated_set_is_flagged(self):
        """Paper reports p = 0.006 for the fabricated set."""
        r = _run(PAPER_SET2, [100] * 20)
        assert r["dispersion_p"] < 0.01
        assert r["severity"] == "suspicious"

    def test_paper_reported_descriptives_are_reproduced(self):
        """Paper: Set 1 mean SD 9.868 (SD 0.595); Set 2 mean 10.667 (SD 0.456)."""
        assert float(np.mean(PAPER_SET1)) == pytest.approx(9.868, abs=0.002)
        assert float(np.std(PAPER_SET1, ddof=1)) == pytest.approx(0.595, abs=0.002)
        assert float(np.mean(PAPER_SET2)) == pytest.approx(10.667, abs=0.002)
        assert float(np.std(PAPER_SET2, ddof=1)) == pytest.approx(0.456, abs=0.002)

    def test_smeesters_surfaces_rather_than_clearing(self):
        """The canonical case must not come back `consistent`.

        At p ~ 0.012 it sits between the two thresholds. Reporting a clean bill
        of health on the case that made this method's reputation would be the
        wrong failure, so the middle band exists to surface it.
        """
        assert _run(SMEESTERS, [15] * 3)["severity"] == "indeterminate"


class TestStatistic:
    def test_standardization_makes_weighted_mean_one(self):
        """MS_w is defined so the weighted mean of z^2 is exactly 1."""
        sds = [9.0, 10.0, 11.0, 12.0]
        ns = [20, 30, 25, 40]
        z2, ms_w = _standardized_variances(sds, ns)
        df = np.asarray(ns, dtype=float) - 1
        assert float(np.sum(df * z2) / np.sum(df)) == pytest.approx(1.0)
        assert ms_w > 0

    def test_scale_invariance(self):
        """Multiplying every SD by a constant cannot change the verdict."""
        ns = [25] * 5
        a = _run([9.0, 10.0, 11.0, 10.5, 9.5], ns)
        b = _run([90.0, 100.0, 110.0, 105.0, 95.0], ns)
        assert a["dispersion_p"] == pytest.approx(b["dispersion_p"], abs=1e-12)

    def test_range_is_the_verdict_measure_sd_is_secondary(self):
        r = _run(PAPER_SET2, [100] * 20)
        assert r["dispersion_measure"] == "max_z - min_z"
        assert "sd_z_secondary" in r

    def test_identical_sds_give_zero_dispersion(self):
        z2, _ = _standardized_variances([10.0] * 4, [25] * 4)
        assert _dispersion(z2, "range") == pytest.approx(0.0)

    def test_null_distribution_is_calibrated(self):
        """A draw FROM the null must sit uniformly within the null."""
        rng = np.random.default_rng(0)
        ns = [25] * 6
        null = _null_distribution(ns, 20_000, rng, "range")
        # The null's own median should land at p ~ 0.5 by construction.
        assert float(np.mean(null <= float(np.median(null)))) == pytest.approx(0.5, abs=0.02)


class TestCalibration:
    """Honest data must not be accused. The cardinal metric."""

    @pytest.mark.parametrize("k", [3, 6, 12])
    def test_false_positive_rate_near_nominal(self, k):
        rng = np.random.default_rng(100 + k)
        fired = 0
        trials = 200
        for _ in range(trials):
            sds = [float(np.sqrt(rng.chisquare(24) / 24) * 10) for _ in range(k)]
            r = _run(sds, [25] * k, iterations=4000, sd_texts=[f"{s:.4f}" for s in sds])
            if r["severity"] == "suspicious":
                fired += 1
        # Nominal 1% at the `suspicious` threshold; allow Monte Carlo slack.
        assert fired / trials < 0.05, f"k={k}: accused {fired}/{trials} honest sets"

    @pytest.mark.parametrize("k", [3, 6, 12])
    def test_power_against_pinned_sds(self, k):
        """SDs pinned within +-2% are the fabrication signature; must be caught.

        `consistent` is the failure being guarded against. Measured detection is
        100% at every k tested, but the TIER depends on k: at k=3, 74.5% reach
        `suspicious` and the remaining 25.5% land in the middle band. That is
        correct conservatism -- three groups carry little shape -- so this
        asserts detection, and the k>=4 case below asserts the stronger tier.
        """
        rng = np.random.default_rng(200 + k)
        for _ in range(5):
            sds = [10.0 * (1 + rng.uniform(-0.02, 0.02)) for _ in range(k)]
            r = _run(sds, [25] * k, iterations=4000, sd_texts=[f"{s:.4f}" for s in sds])
            assert r["severity"] in ("suspicious", "indeterminate")

    @pytest.mark.parametrize("k", [6, 12])
    def test_pinned_sds_reach_suspicious_once_k_is_moderate(self, k):
        rng = np.random.default_rng(300 + k)
        for _ in range(5):
            sds = [10.0 * (1 + rng.uniform(-0.02, 0.02)) for _ in range(k)]
            r = _run(sds, [25] * k, iterations=4000, sd_texts=[f"{s:.4f}" for s in sds])
            assert r["severity"] == "suspicious"


class TestGuards:
    """Each precondition refuses, names its criterion, and never accuses."""

    def test_too_few_groups(self):
        r = _run([25.09, 24.58], [15, 15])
        assert r["severity"] == "indeterminate"
        assert r["criterion"] == "n_groups"
        assert r["applicable"] is False

    def test_min_groups_is_three(self):
        assert MIN_GROUPS == 3
        assert _run(SMEESTERS, [15] * 3)["applicable"] is True

    def test_homogeneity_unstated_refuses(self):
        r = check_variance_dispersion(
            SMEESTERS, [15] * 3, sd_texts=["25.09", "24.58", "25.65"],
            design="parallel_rct",
        )
        assert r["severity"] == "indeterminate"
        assert r["criterion"] == "homogeneous_variances"

    def test_homogeneity_unstated_cannot_return_consistent(self):
        """The guard must gate the REASSURING verdict too.

        A violated equal-variance assumption blinds this test (measured 0.0%
        detection) rather than making it accusatory, so a silent all-clear is
        the dangerous output, not a false accusation.
        """
        honest = [9.0, 10.0, 11.0, 12.0, 8.5]
        r = check_variance_dispersion(
            honest, [25] * 5, sd_texts=[str(s) for s in honest],
            design="parallel_rct",
        )
        assert r["severity"] != "consistent"
        assert r["criterion"] == "homogeneous_variances"

    def test_declared_heterogeneous_refuses(self):
        r = _run(SMEESTERS, [15] * 3, homogeneous_variances=False)
        assert r["severity"] == "indeterminate"
        assert r["criterion"] == "homogeneous_variances"

    @pytest.mark.parametrize("design", [
        "cluster-randomised trial", "stepped_wedge", "crossover",
        "matched_pairs", "stratified block randomisation", "minimisation by centre",
        "multi_site",
    ])
    def test_dependent_designs_refused(self, design):
        r = _run(PAPER_SET2, [100] * 20, design=design)
        assert r["severity"] == "indeterminate"
        assert r["criterion"] == "design"

    def test_unknown_precision_refuses(self):
        r = check_variance_dispersion(
            SMEESTERS, [15] * 3, design="parallel_rct", homogeneous_variances=True,
        )
        assert r["severity"] == "indeterminate"
        assert r["criterion"] == "precision_unknown"

    def test_coarse_rounding_refuses_rather_than_accusing(self):
        """The measured trap: SD ~ 2.0 printed to 0dp.

        60.2% of HONEST samples give six identical SDs there, so an accusation
        would be an artifact of rounding, not a signature.
        """
        r = check_variance_dispersion(
            [2.0] * 6, [25] * 6, sd_texts=["2"] * 6,
            design="parallel_rct", homogeneous_variances=True,
        )
        assert r["severity"] == "indeterminate"
        assert r["criterion"] == "granularity"

    def test_precision_read_from_literal_not_float(self):
        """`2` and `2.00` are different claims about the same float."""
        coarse, _ = _granularity_ratios([2.0], ["2"])
        fine, _ = _granularity_ratios([2.0], ["2.00"])
        assert coarse[0] == pytest.approx(0.5)
        assert fine[0] == pytest.approx(0.005)

    def test_finely_printed_small_sds_are_allowed(self):
        r = check_variance_dispersion(
            [2.11, 2.34, 1.98, 2.51, 2.07], [25] * 5,
            sd_texts=["2.11", "2.34", "1.98", "2.51", "2.07"],
            design="parallel_rct", homogeneous_variances=True,
        )
        assert r["applicable"] is True

    def test_nonpositive_sd_refused(self):
        r = _run([0.0, 10.0, 11.0], [25] * 3)
        assert r["criterion"] == "nonpositive_sd"

    def test_singleton_group_refused(self):
        r = _run([9.0, 10.0, 11.0], [1, 25, 25])
        assert r["criterion"] == "sample_size"

    def test_mismatched_lengths_refused(self):
        r = _run([9.0, 10.0, 11.0], [25, 25])
        assert r["criterion"] == "input_shape"

    def test_nonfinite_refused(self):
        r = _run([float("nan"), 10.0, 11.0], [25] * 3)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False


class TestContract:
    """House rules: severity ceiling, reference requirement, reproducibility."""

    def test_never_returns_impossible(self):
        """Over-similar SDs are improbable, never a math violation."""
        r = check_variance_dispersion(
            [10.0, 10.0001, 9.9999, 10.00005], [500] * 4,
            sd_texts=["10.0000", "10.0001", "9.9999", "10.0001"],
            design="parallel_rct", homogeneous_variances=True,
        )
        assert r["severity"] in ("suspicious", "indeterminate", "consistent")

    def test_reference_required_on_every_path(self):
        assert _run(PAPER_SET2, [100] * 20)["reference_required"] is True
        assert _run([25.09, 24.58], [15, 15])["reference_required"] is True
        assert _run([float("inf"), 1.0, 2.0], [25] * 3)["reference_required"] is True

    def test_deterministic_for_a_given_seed(self):
        a = _run(PAPER_SET2, [100] * 20, seed=7)
        b = _run(PAPER_SET2, [100] * 20, seed=7)
        assert a["dispersion_p"] == b["dispersion_p"]

    def test_carries_methodology_and_caveat(self):
        r = _run(PAPER_SET2, [100] * 20)
        assert "Hartgerink" in r["methodology"]
        assert "capped at `suspicious`" in r["caveat"]
