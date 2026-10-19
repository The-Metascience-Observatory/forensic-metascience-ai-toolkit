"""Tests for GRIM and GRIMMER tests."""

import pytest
from metascience_agent.tools.grim import grim_test, grim_test_percentage
from metascience_agent.tools.sd_checks import grimmer_test



# ---------------------------------------------------------------------------
# `discreteness_source="stated"` APPEARS THROUGHOUT THIS FILE FROM 2026-08-10.
#
# GRIM's GRANULARITY branch used to reach `impossible` unconditionally. It now
# caps at `suspicious` unless someone establishes that the observations are
# INTEGER-valued -- Greg's call, on the grounds that this family is rarely
# applicable outside psychology and should be "guilty until proven innocent".
# See tools/grim.HARD_DISCRETENESS_SOURCES.
#
# Every test below that stipulates Likert/integer data in its own fixture now
# says so with the parameter. The assertions are UNCHANGED: the point of each
# was, and still is, that arithmetic no convention rescues reaches the top of
# the ladder. Only the premise is now explicit rather than assumed.
# ---------------------------------------------------------------------------

class TestGRIM:
    """Tests for GRIM (Granularity-Related Inconsistency of Means)."""

    def test_consistent_mean(self):
        """Test a mean that is mathematically possible."""
        # n=30, mean=5.0 → sum=150, which is divisible by 30
        result = grim_test(mean=5.0, n=30, scale_min=1, scale_max=7)
        assert result["consistent"] is True

    def test_inconsistent_mean(self):
        """Test a mean that is mathematically impossible."""
        # n=30, mean=5.51 → sum=165.3, not an integer
        result = grim_test(mean=5.51, n=30, scale_min=1, scale_max=7)
        assert result["consistent"] is False

    def test_air_force_grim_failures(self):
        """
        Test the Air Force multivitamin paper GRIM failures.

        From the example: 9 of 10 numbers fail GRIM.
        Note: Some percentages may pass due to rounding tolerance.
        The real GRIM test requires exact analysis of reported decimals.
        """
        # 86.1% of n=79 → 68/79 = 86.08% which rounds to 86.1%
        # This actually passes because it's within rounding tolerance
        result = grim_test_percentage(percentage=86.1, n=79, decimals=1)
        # Check that it's at least being analyzed
        assert "consistent" in result

        # The real power of GRIM on this paper is that when you
        # look at the exact decimals reported vs possible values,
        # inconsistencies emerge. This requires more precise analysis.

    def test_possible_mean_calculation(self):
        """Verify that possible means are calculated correctly."""
        result = grim_test(mean=5.0, n=10, scale_min=1, scale_max=7)
        # For n=10, possible means are 0.1 apart: 1.0, 1.1, 1.2, etc.
        assert 5.0 in result["possible_means_nearby"]
        assert 4.9 in result["possible_means_nearby"]
        assert 5.1 in result["possible_means_nearby"]

    def test_achievable_mean_with_nonzero_fraction(self):
        """Regression: the tolerance must scale with n.

        106/30 = 3.5333… which rounds to 3.53 — so mean 3.53 with n=30 is
        achievable. The old implementation used an n-independent tolerance
        and falsely flagged this as impossible.
        """
        result = grim_test(mean=3.53, n=30, scale_min=1, scale_max=7)
        assert result["consistent"] is True
        assert result["severity"] == "consistent"

    def test_self_consistency_with_nearby_means(self):
        """Regression: any mean listed in possible_means_nearby must itself
        pass GRIM (the old implementation contradicted its own list)."""
        for n in (7, 13, 29, 30, 61):
            probe = grim_test(mean=3.5, n=n)
            for m in probe["possible_means_nearby"]:
                r = grim_test(mean=m, n=n)
                assert r["consistent"] is True, f"mean={m}, n={n} should pass"

    def test_severity_field(self):
        assert grim_test(mean=5.51, n=30,
                         discreteness_source="stated")["severity"] == "impossible"
        assert grim_test(mean=5.0, n=30)["severity"] == "consistent"

    def test_invalid_n(self):
        result = grim_test(mean=5.0, n=0)
        assert "error" in result
        assert result["severity"] == "indeterminate"


class TestGRIMPercentage:
    """Tests for GRIM on percentages."""

    def test_consistent_percentage(self):
        """Test a percentage that is possible."""
        # 50% of 100 = 50 people (integer)
        result = grim_test_percentage(percentage=50.0, n=100, decimals=1)
        assert result["consistent"] is True

    def test_inconsistent_percentage(self):
        """Test a percentage that is impossible."""
        # 33.3% of 100 = 33.3 people (not integer)
        result = grim_test_percentage(percentage=33.3, n=100, decimals=1)
        # 33.3% of 100 = 33.3, which rounds to 33
        # But 33/100 = 33.0%, not 33.3%
        assert result["consistent"] is False

    def test_sum_greater_than_100(self):
        """
        Test the example where percentages sum to > 100%.

        From the intro doc: "48.8% + 52.2% = 101%"
        """
        # This is caught by summation check, not GRIM
        # But individual percentages might still fail GRIM
        pass


class TestGRIMPercentageDataType:
    """The percentage GRIM is valid only when the value is a SHARE of the
    sample (100*k/n). A continuous percentage -- a mean change, a
    concentration, a ratio -- is not k/n, and running GRIM on it manufactures
    a false `impossible`. The data_type guard refuses those, mirroring the
    guard grim_test applies to a continuous MEAN.
    """

    def test_continuous_percentage_is_refused_not_accused(self):
        # "Blood glucose fell 23.7%" at n=40: 100*k/40 = 23.7 has no integer k
        # (nearest are 22.5 and 25.0), so the old ungated tool called this
        # `impossible`. But a mean change is not a share of the sample.
        r = grim_test_percentage(23.7, 40, decimals=1, data_type="continuous")
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False
        assert r["canonical_data_type"] == "continuous"

    def test_a_genuine_share_impossibility_is_still_flagged(self):
        # 33.4% of n=7 cannot be a count/7 (3/7 = 42.9, 2/7 = 28.6), so a real
        # count-proportion reported as 33.4% is impossible -- the guard must not
        # blunt this.
        r = grim_test_percentage(33.4, 7, decimals=1, data_type="proportion")
        assert r["severity"] == "impossible"
        assert r["applicable"] is True

    def test_binary_share_is_applicable(self):
        # 42.9% of n=7 = 3/7 (42.857 rounds to 42.9): a binary 0/1 variable's
        # mean-as-percentage is a share and passes.
        r = grim_test_percentage(42.9, 7, decimals=1, data_type="binary")
        assert r["applicable"] is True
        assert r["consistent"] is True

    def test_unknown_data_type_is_refused(self):
        # An unrecognised or missing label means we do not know the value is a
        # share; the safe direction is to decline, not to accuse.
        r = grim_test_percentage(23.7, 40, decimals=1, data_type="ratio")
        assert r["applicable"] is False
        assert r["severity"] == "indeterminate"

    def test_default_data_type_still_evaluates_a_share(self):
        # The default is `proportion`, so callers testing genuine shares (the
        # existing behaviour) keep a verdict.
        r = grim_test_percentage(50.0, 100, decimals=1)
        assert r["applicable"] is True
        assert r["consistent"] is True


class TestGRIMMER:
    """Tests for GRIMMER (GRIM for standard deviations)."""

    def test_consistent_sd(self):
        """An SD that is genuinely achievable with integer data.

        Data [3,3,3,4,4,4,4,5,5,5]: mean = 4.0, sample SD = 0.8165 → 0.82.
        """
        result = grimmer_test(mean=4.0, sd=0.82, n=10, scale_min=1, scale_max=7)
        assert result["consistent"] is True
        assert result["found_valid_combination"] is True
        assert result["severity"] == "consistent"

    def test_impossible_sd_parity(self):
        """A genuine both-convention impossibility stays impossible.

        (mean=4.00, SD=1.40, n=10) is unreachable under BOTH the sample and the
        population SD convention -- verified by exhaustive enumeration of every
        multiset of 10 values in [1,7] summing to 40: 1.40 is in neither
        convention's achievable-SD set.

        This used to assert (4.00, SD=1.00, n=10) impossible, on a brute force
        that checked only the SAMPLE SD. That case IS reachable under the
        population convention -- [2,3,3,4,4,4,5,5,5,5] has population SD exactly
        1.00 -- so the old expectation was a false accusation against numpy's
        std default. It now lives in TestGrimmerPopulationSdConvention
        (test_false_positive_guards.py) as a suspicious/sd_convention case.
        """
        result = grimmer_test(mean=4.0, sd=1.4, n=10, scale_min=1, scale_max=7,
                              decimals=2, decimals_sd=2,
                              discreteness_source="stated")
        assert result["consistent"] is False
        assert result["severity"] == "impossible"

    def test_impossible_tiny_sd(self):
        """SD 0.01 with mean 2.0, n=5: only achievable SD near 0 is exactly 0."""
        result = grimmer_test(mean=2.0, sd=0.01, n=5)
        assert result["consistent"] is False

    def test_neighbouring_achievable_sds_pass(self):
        """The two brute-force-verified achievable SDs adjacent to 1.0 pass."""
        for sd in (0.94, 1.05):
            result = grimmer_test(mean=4.0, sd=sd, n=10, scale_min=1, scale_max=7)
            assert result["consistent"] is True, f"sd={sd} should be achievable"

    def test_sum_of_squares_formula(self):
        """Verify the sum of squares formula is applied correctly."""
        # Σx² = (n-1)*σ² + n*μ²
        mean, sd, n = 3.0, 1.0, 10
        result = grimmer_test(mean=mean, sd=sd, n=n)

        expected_sum_sq = (n - 1) * sd**2 + n * mean**2
        assert abs(result["implied_sum_squares"] - expected_sum_sq) < 0.001

    def test_invalid_inputs(self):
        assert "error" in grimmer_test(mean=4.0, sd=1.0, n=1)
        assert "error" in grimmer_test(mean=4.0, sd=-0.5, n=10)


class TestGRIMMERBoundSource:
    """GRIMMER may not say `impossible` against a scale it invented.

    Measured on a real paper: "Number of coalition members", mean 35.78,
    SD 33.74, n=64, declared `count` with NO stated bounds. grimmer_check
    returned `impossible` against its default 1-7 Likert scale, while grim_check
    on the same input returned `suspicious` -- because GRIM caps out-of-range
    findings when `bound_source` is assumed (tools/grim.py:161-170) and GRIMMER
    had no such parameter. 2290/64 = 35.78125, which rounds to 35.78; the paper
    was fine.
    """

    ARGS = dict(mean=35.78, sd=33.74, n=64, data_type="count",
                decimals=2, decimals_sd=2)

    def test_the_reported_false_accusation(self):
        r = grimmer_test(**self.ARGS)
        assert r["severity"] == "suspicious"
        assert r["failure_mode"] == "out_of_range"

    def test_grim_and_grimmer_now_agree_on_the_same_cell(self):
        g = grim_test(35.78, 64, data_type="count", decimals=2)
        assert grimmer_test(**self.ARGS)["severity"] == g["severity"] == "suspicious"

    def test_a_stated_bound_still_licenses_impossible(self):
        """The fix is "stop inventing bounds", not "stop checking"."""
        r = grimmer_test(**self.ARGS, bound_source="stated")
        assert r["severity"] == "impossible"

    def test_the_truthful_bounds_make_it_consistent(self):
        r = grimmer_test(**self.ARGS, scale_min=0, scale_max=500,
                         bound_source="stated")
        assert r["severity"] == "consistent" and r["consistent"] is True

    def test_a_range_failure_is_not_called_a_granularity_failure(self):
        """72.5 x 100 = 7250 EXACTLY, so "no integer sum rounds to it" was false.

        `grim_consistent` was read off a candidate list already filtered by the
        assumed range, so every range failure was reported as a GRIM failure.
        """
        r = grimmer_test(mean=72.5, sd=10.0, n=100, data_type="count",
                         decimals=1, decimals_sd=1)
        assert r["grim_consistent"] is True
        assert r["sum_in_range"] is False
        assert 7250 in r["grim_sums"]
        assert "no integer sum rounds to it" not in r["failure_reason"]
        assert "RANGE failure" in r["failure_reason"]

    def test_an_arithmetic_impossibility_is_still_impossible(self):
        """Bound-free evidence: no sum-of-squares of the right parity fits the
        SD window under EITHER convention, with or without the scale.
        (mean 4.00, SD 1.40, n=10 -- see test_impossible_sd_parity for why the
        old SD=1.00 case is population-feasible and no longer belongs here.)
        """
        r = grimmer_test(mean=4.0, sd=1.4, n=10, scale_min=1, scale_max=7,
                         decimals=2, decimals_sd=2, discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "sd_granularity"
        assert r["feasible_ignoring_bounds"] is False

    def test_a_granularity_failure_is_still_impossible(self):
        r = grimmer_test(mean=5.51, sd=1.0, n=30, data_type="likert",
                         discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "granularity"


class TestGRIMSweep:
    """Heathers §"Reconstructing prevalence" — Ballot 1989 example."""

    def test_ballot_1989_first_value(self):
        """grim('0.491', n) should be TRUE for n in
        {53, 55, 57, 106, 108, 110, 112, 114, 116, 159, 161} (per intro doc)."""
        from metascience_agent.tools.grim import grim_sweep

        # Test as proportion 0.491 reported to 3dp.
        result = grim_sweep([0.491], n_max=161, decimals=3, value_type="proportion")
        viable = result["per_value"][0]["viable_ns"]
        expected = [53, 55, 57, 106, 108, 110, 112, 114, 116, 159, 161]
        assert viable == expected

    def test_ballot_1989_intersection_empty(self):
        """The three percentages 49.1, 16.2, 17.4 cannot share a common n
        in [2, 161]; their joint viable set is empty (Heathers' diagnosis)."""
        from metascience_agent.tools.grim import grim_sweep

        # n_max=161 is Ballot's own reported N, so the range is stated, not
        # ours -- which is what licenses the `impossible` verdict.
        result = grim_sweep([49.1, 16.2, 17.4], n_max=161, decimals=1,
                            n_max_source="stated")
        assert result["joint_viable_ns"] == []
        assert result["severity"] == "impossible"

    def test_unique_intersection(self):
        """Two percentages that DO share a unique n."""
        from metascience_agent.tools.grim import grim_sweep

        # 50.0% and 25.0% both pass GRIM at n=4 (k=2, k=1) and many others;
        # use a tight range to force uniqueness.
        result = grim_sweep([50.0, 25.0], n_max=4, n_min=4, decimals=1)
        assert result["joint_viable_ns"] == [4]


class TestGRIMTruncationBoundGate:
    """The truncation rescue may not be blocked by a bound WE assumed.

    A truncating reporter (SPSS default) on a 1-10 scale: 30 obs summing to
    284, exact mean 284/30 = 9.4667, printed 9.46. Round-half GRIM fails
    (nearest is 9.47), truncation GRIM passes -- but the truncation-consistent
    sum 284 lies outside the DEFAULT ASSUMED 1-7 scale's [30, 210], so the
    rescue was gated off and the verdict escalated to `impossible` with
    failure_mode `granularity` ("bound-independent") -- on a path that ran
    straight through our invented bound. An honest truncating paper, called
    mathematically impossible.
    """

    def test_truncation_rescue_not_blocked_by_assumed_bounds(self):
        r = grim_test(mean=9.46, n=30)  # bounds default 1-7, bound_source assumed
        # RECALIBRATED 2026-08-10 (Greg): a value rescued by the truncation
        # convention is `consistent`, not `suspicious` -- it must not enter the
        # findings as an accusation. The convention is still NAMED
        # (`failure_mode == "rounding_convention"`) and counted per paper, which
        # is where the signal actually lives. See `grim.grim_test`.
        assert r["severity"] == "consistent"
        assert r["failure_mode"] == "rounding_convention"
        assert r["failure_mode"] == "rounding_convention"
        assert r["severity"] != "impossible"

    def test_stated_bounds_still_license_impossible(self):
        # With the paper's OWN 1-7 bound, both conventions are dead: round-half
        # fails everywhere, truncation's only sum (284) violates the stated
        # scale. The fix must not blunt this.
        r = grim_test(mean=9.46, n=30, scale_min=1, scale_max=7,
                      bound_source="stated", discreteness_source="stated")
        assert r["severity"] == "impossible"

    def test_true_stated_bounds_give_rounding_convention(self):
        # The ground truth: on the paper's actual 1-10 scale this is a
        # truncation-convention finding, nothing stronger.
        r = grim_test(mean=9.46, n=30, scale_min=1, scale_max=10,
                      bound_source="stated")
        # RECALIBRATED 2026-08-10 (Greg): a value rescued by the truncation
        # convention is `consistent`, not `suspicious` -- it must not enter the
        # findings as an accusation. The convention is still NAMED
        # (`failure_mode == "rounding_convention"`) and counted per paper, which
        # is where the signal actually lives. See `grim.grim_test`.
        assert r["severity"] == "consistent"
        assert r["failure_mode"] == "rounding_convention"
        assert r["failure_mode"] == "rounding_convention"

    def test_both_convention_impossibility_still_impossible(self):
        # 5.51 at n=30 fails round-half AND truncation: bound-free arithmetic,
        # stays `impossible` under assumed bounds.
        r = grim_test(mean=5.51, n=30, discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "granularity"


class TestGRIMSweepRangeGuard:
    """An empty intersection is a fact about OUR searched n-range unless that
    range provably brackets the true n. True sample: counts 85, 245, 41 of
    n=250 -> 34.0%, 98.0%, 16.4% at 1 dp. Sweeping [20, 200] (or [2, 200])
    finds no joint n and used to return `impossible` -- but n=250 is simply
    outside the range we chose. Only a STATED total N licenses the accusation.
    """

    VALS = [34.0, 98.0, 16.4]

    def test_empty_intersection_with_assumed_range_refuses(self):
        from metascience_agent.tools.grim import grim_sweep

        r = grim_sweep(self.VALS, n_max=200, n_min=20, decimals=1)
        assert r["joint_viable_ns"] == []
        assert r["severity"] == "indeterminate"
        assert "range" in r["explanation"].lower()

    def test_empty_intersection_with_stated_n_is_impossible(self):
        from metascience_agent.tools.grim import grim_sweep

        # Same values, but the paper itself claims N <= 200: the range is the
        # paper's own, so the empty intersection is about the paper.
        r = grim_sweep(self.VALS, n_max=200, n_min=2, decimals=1,
                       n_max_source="stated")
        assert r["joint_viable_ns"] == []
        assert r["severity"] == "impossible"

    def test_stated_n_but_raised_n_min_still_refuses(self):
        from metascience_agent.tools.grim import grim_sweep

        # n_max is the paper's, but n_min=20 is OURS: a true n in [2, 19]
        # was never checked, so the range is not provably exhaustive.
        r = grim_sweep(self.VALS, n_max=200, n_min=20, decimals=1,
                       n_max_source="stated")
        assert r["severity"] == "indeterminate"

    def test_range_that_brackets_the_truth_finds_it(self):
        from metascience_agent.tools.grim import grim_sweep

        r = grim_sweep(self.VALS, n_max=300, n_min=20, decimals=1)
        assert 250 in r["joint_viable_ns"]
        assert r["severity"] == "consistent"


class TestReconstruct2x2:
    """Heathers' INTERVENTION/CONTROL example: 63.7%/44.9%, n=180, χ²=6.407."""

    def test_unique_with_chi2_filter(self):
        from metascience_agent.tools.grim import reconstruct_2x2

        # With tight χ² tolerance, the canonical (58,40,33,49) solution is unique.
        result = reconstruct_2x2(
            pct_col1=63.7, pct_col2=44.9, n_total=180, decimals=1,
            reported_chi2=6.407, chi2_tolerance=0.01,
        )
        assert result["n_solutions"] == 1
        cand = result["candidates"][0]
        assert (cand["A"], cand["B"], cand["C"], cand["D"]) == (58, 40, 33, 49)
        assert cand["col1_total"] == 91
        assert cand["col2_total"] == 89
        assert cand["chi2_match"] is True

    def test_multiple_solutions_without_filter(self):
        from metascience_agent.tools.grim import reconstruct_2x2

        result = reconstruct_2x2(
            pct_col1=63.7, pct_col2=44.9, n_total=180, decimals=1,
        )
        # Without filtering, both math-valid solutions appear (Heathers
        # eliminates the second on randomization grounds, not math).
        assert result["n_solutions"] >= 2
        # Canonical solution must be present.
        canonical = next(
            (c for c in result["candidates"]
             if (c["A"], c["B"], c["C"], c["D"]) == (58, 40, 33, 49)),
            None,
        )
        assert canonical is not None

    def test_impossible_when_total_too_small(self):
        from metascience_agent.tools.grim import reconstruct_2x2

        # No 2x2 with n_total=4 can produce 63.7% and 44.9% at 1dp precision.
        result = reconstruct_2x2(63.7, 44.9, n_total=4, decimals=1)
        assert result["severity"] == "impossible"
        assert result["n_solutions"] == 0

    def test_an_imbalanced_table_is_not_impossible(self):
        """The balance filter must SORT, not gate feasibility. An ordinary
        observational split (149 vs 29) reconstructs perfectly; declaring it
        `impossible` was OUR heuristic exclusion published as a claim about the
        paper, at the strongest severity the toolkit has."""
        from metascience_agent.tools.grim import reconstruct_2x2

        result = reconstruct_2x2(pct_col1=36.91, pct_col2=37.93, n_total=178, decimals=2)
        assert result["severity"] == "consistent"
        assert result["n_solutions"] == 1
        assert result["n_solutions_outside_balance"] == 1
        c = result["candidates"][0]
        # The true table: columns 149 / 29.
        assert {c["col1_total"], c["col2_total"]} == {149, 29}
        assert "imbalanced" in result["explanation"]

    def test_genuinely_unreconstructable_is_still_impossible(self):
        from metascience_agent.tools.grim import reconstruct_2x2
        # Checked over EVERY split, not only balanced ones.
        result = reconstruct_2x2(33.33, 66.67, n_total=7, decimals=2)
        assert result["severity"] == "impossible"
        assert "every column split was checked" in result["explanation"]

    def test_reconstructions_exist_but_chi2_matches_none_declines(self):
        """A reported chi-squared that matches no reconstruction is not proof the
        table is impossible -- the recompute is Pearson, so a Yates or rounded
        chi-squared mismatches a valid table. Decline, do not accuse."""
        from metascience_agent.tools.grim import reconstruct_2x2
        result = reconstruct_2x2(63.7, 44.9, n_total=180, decimals=1,
                                 reported_chi2=999.0, chi2_tolerance=0.01)
        assert result["severity"] == "indeterminate"
        assert result["n_solutions"] == 0

    def test_precondition_errors_carry_a_severity(self):
        from metascience_agent.tools.grim import reconstruct_2x2
        assert reconstruct_2x2(50.0, 50.0, n_total=2)["severity"] == "indeterminate"
        assert reconstruct_2x2(50.0, 50.0, n_total=100,
                               value_type="nonsense")["severity"] == "indeterminate"


class TestRealWorldExamples:
    """Tests based on real-world examples from the Heathers document."""

    def test_apple_cider_vinegar_bmi(self):
        """
        Test BMI values from the apple cider vinegar paper.

        BMI: range 27-34, mean=30.6, SD=3.1, n=30
        SPRITE shows bimodal distribution (many 27s and 34s)
        """
        from metascience_agent.tools.sprite import sprite_reconstruct

        result = sprite_reconstruct(
            mean=30.6,
            sd=3.1,
            n=30,
            scale_min=27,
            scale_max=34,
            num_samples=10,
        )

        # Should either succeed or fail with error message
        # (SPRITE is probabilistic and may not always find solutions)
        assert "success" in result or "error" in result

        # If successful, may show bimodal pattern
        # The paper notes "curiously strong preponderance of low values (BMI = 27)
        # and high values (BMI = 34)"


class TestGrimSweepTriesTruncationBeforeAccusing:
    """`grim_test` has always tried the truncation convention before calling a
    mean impossible. `grim_sweep` never did, and nobody decided that -- the
    registry documents the choice deliberately for `grim_percentage` and is
    silent here.

    The asymmetry produced a published `impossible` against a NON-RETRACTED
    paper. On 10.3390/jpm11060545 the sweep was given the Cerebrolysin arm's
    96.7% infusion rate and 8.1% adverse-event rate with the paper's stated
    N=119, found no shared denominator under round-half, and accused.

    It is consistent. The unique split of 119 fitting the three printed
    percentages is 61/58: 59/61 = 96.7213 -> 96.7, 51/58 = 87.9310 -> 87.9, and
    110/119 = 92.4370 -> 92.4. At n=61 the stated 5 adverse events give
    5/61 = 8.1967, which TRUNCATES to 8.1 and rounds to 8.2. The paper truncates.
    """

    @staticmethod
    def _sweep(values, n_max=119, source="stated"):
        from metascience_agent.registry import BY_NAME
        return BY_NAME["grim_sweep"].call({
            "values": values, "n_max": n_max, "n_min": 2, "decimals": 1,
            "value_type": "percentage", "n_max_source": source})

    def test_the_published_false_accusation_is_retired(self):
        r = self._sweep([96.7, 8.1])
        assert r["severity"] != "impossible"
        # RECALIBRATED 2026-08-10 (Greg): a value rescued by the truncation
        # convention is `consistent`, not `suspicious` -- it must not enter the
        # findings as an accusation. The convention is still NAMED
        # (`failure_mode == "rounding_convention"`) and counted per paper, which
        # is where the signal actually lives. See `grim.grim_test`.
        assert r["severity"] == "consistent"
        assert r["failure_mode"] == "rounding_convention"

    def test_it_names_the_denominator_that_rescues_it(self):
        r = self._sweep([96.7, 8.1])
        assert r["joint_viable_ns"] == []
        assert 61 in r["joint_viable_ns_truncation"]
        assert r["failure_mode"] == "rounding_convention"
        assert "TRUNCATION" in r["explanation"]

    def test_the_other_arm_is_also_no_longer_impossible(self):
        # RECALIBRATED 2026-08-10 (Greg): a value rescued by the truncation
        # convention is `consistent`, not `suspicious` -- it must not enter the
        # findings as an accusation. The convention is still NAMED
        # (`failure_mode == "rounding_convention"`) and counted per paper, which
        # is where the signal actually lives. See `grim.grim_test`.
        assert self._sweep([87.9, 8.3])["severity"] == "consistent"
        assert self._sweep([87.9, 8.3])["failure_mode"] == "rounding_convention"

    def test_a_truncation_rescue_warns_that_it_may_be_coincidence(self):
        """The placebo arm's joint solution is n=108, which is NOT its arm size
        (58) -- 87.9% fits 58 and 8.3% fits 60, so those two percentages really
        do use different denominators. A joint solution can be arithmetic
        coincidence, and the explanation has to say so or the cap becomes a
        false all-clear."""
        r = self._sweep([87.9, 8.3])
        assert "coincidence" in r["explanation"]
        assert "per_value" in r["explanation"]

    def test_a_genuinely_impossible_sweep_still_accuses(self):
        """The fix must not blunt the check -- only rescue what a convention
        explains."""
        r = self._sweep([33.3, 66.6, 50.1], n_max=40)
        assert r["joint_viable_ns_truncation"] == []
        assert r["severity"] == "impossible"

    def test_a_consistent_sweep_is_untouched(self):
        r = self._sweep([50.0, 25.0], n_max=40)
        assert r["severity"] == "consistent"
        assert r["failure_mode"] is None

    def test_the_range_guard_still_takes_precedence(self):
        """An assumed range cannot license any verdict, truncation or not."""
        r = self._sweep([33.3, 66.6, 50.1], n_max=40, source="assumed")
        assert r["severity"] == "indeterminate"

    def test_the_two_grim_tools_now_agree_about_truncation(self):
        """The asymmetry itself, stated as a property: a value a truncating
        reporter would print must not be `impossible` in either tool."""
        from metascience_agent.registry import BY_NAME
        single = BY_NAME["grim_check"].call(
            {"mean": 3.46, "n": 30, "decimals": 2, "data_type": "likert"})
        assert single["severity"] != "impossible"
        assert self._sweep([96.7, 8.1])["severity"] != "impossible"


class TestGrimPercentageTriesTruncationToo:
    """The last of the three GRIM tools to get the truncation branch.

    `grim_check` has always tried both conventions. `grim_sweep` got it in
    bd240cf. This one's integrity card said "Only the round-half convention is
    tried here" -- documenting the gap without justifying it. There is no reason
    a percentage is less likely to be truncated than a mean; SPSS and several
    journal styles truncate percentages by default.

    FOUND BY A REAL RUN, not by inspection: 10.3389/fnins.2023.1186751 reports
    "Premature discontinuations were reported in 9 patients due to loss to
    follow-up (9.6%)" against its own stated 93 enrolled. 9/93 = 9.6774, which
    rounds to 9.7 and TRUNCATES to 9.6. The run returned `impossible`.
    """

    @staticmethod
    def _pct(percentage, n, decimals=1):
        from metascience_agent.registry import BY_NAME
        return BY_NAME["grim_percentage"].call(
            {"percentage": percentage, "n": n, "decimals": decimals,
             "data_type": "proportion"})

    def test_the_run_finding_is_no_longer_impossible(self):
        r = self._pct(9.6, 93)
        # RECALIBRATED 2026-08-10 (Greg): a value rescued by the truncation
        # convention is `consistent`, not `suspicious` -- it must not enter the
        # findings as an accusation. The convention is still NAMED
        # (`failure_mode == "rounding_convention"`) and counted per paper, which
        # is where the signal actually lives. See `grim.grim_test`.
        assert r["severity"] == "consistent"
        assert r["failure_mode"] == "rounding_convention"
        assert r["passes_under_truncation"] is True
        assert r["failure_mode"] == "rounding_convention"

    def test_it_is_not_silently_cleared_either(self):
        """A convention explains it, so it is not impossible -- but the reader
        is told which convention was needed.

        RECALIBRATED 2026-08-10 (Greg): that "told" is no longer carried by the
        SEVERITY, which is now `consistent` so it cannot enter the findings as
        an accusation. It is carried by `failure_mode` and by the per-paper
        count. The intent of this test is unchanged; only the field that holds
        the signal has moved."""
        r = self._pct(9.6, 93)
        assert r["severity"] == "consistent"
        assert r["failure_mode"] == "rounding_convention"
        assert r["passes_under_truncation"] is True

    def test_a_value_that_rounds_cleanly_is_consistent(self):
        r = self._pct(9.6, 94)
        assert r["severity"] == "consistent" and r["failure_mode"] is None

    def test_a_genuinely_unreachable_percentage_still_accuses(self):
        r = self._pct(33.3, 7)
        assert r["severity"] == "impossible"
        assert r["passes_under_truncation"] is False

    def test_all_three_grim_tools_now_agree_about_truncation(self):
        """State the family property, since the asymmetry was the actual bug in
        two of the three."""
        from metascience_agent.registry import BY_NAME
        assert BY_NAME["grim_check"].call(
            {"mean": 3.46, "n": 30, "decimals": 2,
             "data_type": "likert"})["severity"] != "impossible"
        assert BY_NAME["grim_sweep"].call(
            {"values": [96.7, 8.1], "n_max": 119, "n_min": 2, "decimals": 1,
             "value_type": "percentage",
             "n_max_source": "stated"})["severity"] != "impossible"
        assert self._pct(9.6, 93)["severity"] != "impossible"

    def test_the_integrity_card_no_longer_claims_round_half_only(self):
        from metascience_agent.registry import BY_NAME
        card = BY_NAME["grim_percentage"].integrity_card()
        assumptions = " ".join(card["assumptions"])
        assert "truncation" in assumptions.lower()
        assert "Only the round-half convention" not in assumptions


class TestTruncationIsCountedNotAccused:
    """GREG'S CALL, 2026-08-10, recorded as a methodological reversal in the
    same register as the STALT threshold decision (#84):

      "An impossible result that is consistent when truncation is assumed still
       deserves to be flagged in some way. It is still suspicious, though I
       wouldn't want to classify it as suspicious in the findings."

    So the severity is `consistent` -- it can never enter the findings as an
    accusation -- and the fact is carried by `failure_mode` per cell and by a
    RATE per paper. One rescue is a house style and carries no information; a
    high proportion does, because per Heathers this class of anomaly is
    commoner in papers with more serious problems. Grounds to look harder, not
    evidence in itself. Same shape as `flag_round_n`."""

    def test_the_severity_never_reaches_the_findings_as_suspicious(self):
        from metascience_agent.tools.grim import grim_test_percentage
        r = grim_test_percentage(percentage=9.6, n=93, decimals=1,
                                 data_type="proportion")
        assert r["severity"] == "consistent"

    def test_but_the_convention_is_still_named(self):
        from metascience_agent.tools.grim import grim_test_percentage
        r = grim_test_percentage(percentage=9.6, n=93, decimals=1,
                                 data_type="proportion")
        assert r["failure_mode"] == "rounding_convention"
        assert r["passes_under_truncation"] is True

    def test_a_genuine_granularity_failure_is_still_impossible(self):
        """The de-escalation is for the CONVENTION, not for arithmetic that no
        convention rescues."""
        from metascience_agent.tools.grim import grim_test
        r = grim_test(mean=5.19, n=10, decimals=2, data_type="likert",
                      scale_min=1, scale_max=7, bound_source="stated",
                      discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "granularity"

    def test_the_population_sd_convention_now_gets_the_same_treatment(self):
        """REVERSED 2026-08-10. This test previously asserted the OPPOSITE --
        that the population-SD convention was "deliberately not extended"
        because Greg had ruled on truncation only, and extending his decision
        would have been me deciding rather than him.

        He then ruled: "regarding the Population-SD convention, I changed my
        mind and want it applied as well -- it would be inconsistent to do the
        truncation check but not this." He is right: both are reporting
        conventions the paper chose that fully explain the number, and one
        epistemic situation was getting two different words depending on which
        convention happened to carry the value.

        The old version also asserted this by grepping the module source for
        `severity = "suspicious"`, which passed against the UNRELATED
        `overall_severity` line in the batch aggregate. A source-string test
        that survives the behaviour it pins is not a test. This one calls the
        tools."""
        from metascience_agent.tools.debit import debit_test
        from metascience_agent.tools.sd_checks import grimmer_test
        from metascience_agent.tools.sprite import sprite_reconstruct

        d = debit_test(0.20, 0.40, 30)
        assert d["severity"] == "consistent"
        assert d["sd_convention"] == "population"
        assert d["consistent_under_population_convention"] is True

        cell = dict(mean=3.0, sd=1.0, n=10, scale_min=1, scale_max=7,
                    data_type="likert", bound_source="stated")
        g, sp = grimmer_test(**cell), sprite_reconstruct(**cell)
        assert g["severity"] == sp["severity"] == "consistent"
        # NAMED, not erased. `consistent` must not mean the convention went
        # unrecorded -- the per-paper rate is built from exactly these fields.
        assert g["failure_mode"] == sp["outcome"] == "sd_convention"

    def test_both_rates_are_counted_per_paper(self):
        """A convention that stops being a finding and is counted nowhere has
        simply been deleted, and the whole argument for de-escalating it was
        that the AGGREGATE is where it means something."""
        from metascience_agent.agent import checks_tally
        out = checks_tally(None, {"findings": []})
        rc = out["rounding_convention"]
        assert set(rc) >= {"n_fit_only_under_truncation", "n_granularity_checks"}
        assert "NOT a finding" in rc["note"]
        assert "RATE is the signal" in rc["note"]

        sc = out["sd_convention"]
        assert set(sc) >= {"n_fit_only_under_population_sd", "n_granularity_checks"}
        assert "NOT a finding" in sc["note"]
        # KEPT SEPARATE from the rounding convention on purpose: they have
        # different innocent explanations, and "this lab reports numpy's std"
        # and "this journal truncates" lead to different follow-up questions.
        assert "population" in sc["note"].lower()

    def test_the_population_sd_counter_actually_counts(self):
        """The truncation counter was written before its tools emitted the
        field it reads, and nothing caught it because a zero counter looks
        exactly like a clean paper. Drive this one with a real tool result."""
        import json
        from metascience_agent.agent import checks_tally
        from metascience_agent.tools.sd_checks import grimmer_test

        r = grimmer_test(mean=3.0, sd=1.0, n=10, scale_min=1, scale_max=7,
                         data_type="likert", bound_source="stated")
        assert r["failure_mode"] == "sd_convention", "fixture must be the pop-SD case"
        messages = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t1", "name": "grimmer_check", "input": {}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t1",
                 "content": json.dumps(r)}]}},
        ]
        out = checks_tally(messages, {"findings": []})
        assert out["sd_convention"]["n_fit_only_under_population_sd"] == 1
        assert out["sd_convention"]["n_granularity_checks"] == 1


class TestAnAbsentBoundIsNotAnInventedOne:
    """D1-A (2026-09-08). `scale_min=None` / `scale_max=None` mean the paper
    states no bound on that side, and the range check is skipped ON THAT SIDE
    ONLY.

    WHY IT WAS NEEDED. The defaults are 1 and 7 -- a Likert scale -- and they
    were the caller's only way to say nothing. A count with no ceiling
    ("number of coalition members", mean 35.78 at n = 64) was therefore tested
    against an INVENTED 1-7 scale and came back `suspicious` / `out_of_range`
    on an ordinary number.

    THIS IS A NARROWING CHANGE (CLAUDE.md 8d, Rule 1): it removes an accusation
    path and adds none. The granularity branch is bound-free and untouched, so
    a real granularity failure still reaches `impossible` under a stated
    discreteness with no bounds at all.
    """

    def test_the_invented_scale_is_what_produced_the_accusation(self):
        assert grim_test(35.78, 64, decimals=2, data_type="count")["severity"] == "suspicious"
        assert grim_test(35.78, 64, decimals=2,
                         data_type="count")["failure_mode"] == "out_of_range"

    def test_an_absent_bound_clears_it(self):
        r = grim_test(35.78, 64, decimals=2, data_type="count",
                      scale_min=None, scale_max=None)
        assert r["severity"] == "consistent"
        assert r["failure_mode"] is None
        assert r["sum_in_range"] is True

    def test_a_none_bound_can_never_yield_out_of_range(self):
        for mean in (-500.0, 0.0, 3.5, 12.4, 4000.0):
            for lo, hi in ((None, None), (0, None), (None, 7)):
                r = grim_test(mean, 30, scale_min=lo, scale_max=hi, decimals=1,
                              data_type="count", bound_source="stated")
                if r.get("failure_mode") == "out_of_range":
                    # Only reachable when the STATED side is the one violated.
                    assert (lo is not None and mean < lo) or (hi is not None and mean > hi)

    def test_one_sided_bounds_still_bind_on_the_side_they_have(self):
        low = grim_test(-3.0, 30, scale_min=0, scale_max=None, decimals=1,
                        data_type="count", bound_source="stated")
        assert low["sum_in_range"] is False
        high = grim_test(500.0, 30, scale_min=None, scale_max=7, decimals=1,
                         data_type="likert", bound_source="stated")
        assert high["sum_in_range"] is False
        # 2 dp, so GRIM has resolution here and the full record is returned;
        # at 1 dp and n = 30 the no-power branch exits before `sum_in_range`.
        assert grim_test(3.0, 30, scale_min=0, scale_max=None, decimals=2,
                         data_type="count")["sum_in_range"] is True

    def test_granularity_still_reaches_impossible_with_no_bounds(self):
        r = grim_test(5.51, 30, scale_min=None, scale_max=None, decimals=2,
                      data_type="likert", discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "granularity"

    def test_the_defaults_are_untouched(self):
        import inspect
        sig = inspect.signature(grim_test)
        assert sig.parameters["scale_min"].default == 1
        assert sig.parameters["scale_max"].default == 7

    def test_the_methodology_names_the_side_it_did_not_check(self):
        both = grim_test(5.0, 30, scale_min=1, scale_max=7, decimals=2)
        assert "on a 1-7 scale" in both["methodology"]
        assert "between 30 and 210" in both["methodology"]
        one = grim_test(5.0, 30, scale_min=0, scale_max=None, decimals=2,
                        data_type="count")
        assert "no stated upper bound" in one["methodology"]
        none = grim_test(5.0, 30, scale_min=None, scale_max=None, decimals=2,
                         data_type="count")
        assert "no stated bounds" in none["methodology"]

    def test_the_registry_passes_a_none_bound_through(self):
        from metascience_agent import registry
        r = registry.BY_NAME["grim_check"].call(
            {"mean": 35.78, "n": 64, "decimals": 2, "data_type": "count",
             "scale_min": None, "scale_max": None})
        assert r["severity"] == "consistent"


class TestPercentageFailureMode:
    """grim_percentage names its failure the way grim_check does.

    An inconsistent percentage came back `impossible` with `failure_mode:
    None`, so anything keying on the mode missed it (benchmarks/grim/score.py:
    12 of 12 such calls on Cureus, 2026-10-18).
    """

    def test_a_granularity_failure_says_so(self):
        r = grim_test_percentage(46.8, 30, 1, data_type="proportion")
        assert (r["severity"], r["failure_mode"]) == ("impossible", "granularity")
        assert grim_test(5.51, 30, data_type="likert",
                         discreteness_source="stated")["failure_mode"] == "granularity"

    def test_a_pass_has_no_failure_mode(self):
        r = grim_test_percentage(46.7, 30, 1, data_type="proportion")
        assert (r["severity"], r["failure_mode"]) == ("consistent", None)

    def test_the_truncation_rescue_is_unchanged(self):
        r = grim_test_percentage(9.6, 93, 1, data_type="proportion")
        assert (r["severity"], r["failure_mode"]) == ("consistent",
                                                      "rounding_convention")

    @pytest.mark.parametrize("pct", [120.0, -5.5])
    def test_a_share_outside_0_100_is_out_of_range_not_rescued(self, pct):
        """120% at n = 10 used to pass the range test (the helper returns a
        count of 0 off the unit interval) and was then `consistent` under
        truncation."""
        r = grim_test_percentage(pct, 10, 1, data_type="proportion")
        assert (r["severity"], r["failure_mode"]) == ("impossible", "out_of_range")
        assert r["passes_under_truncation"] is False
