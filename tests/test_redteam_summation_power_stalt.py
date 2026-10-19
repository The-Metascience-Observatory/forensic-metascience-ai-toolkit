"""Red-team regressions for summation, power_check and stalt (2026-08-09).

House rules enforced here:

* A tool defect, a missing input, or a degenerate input must yield a REFUSAL
  (`indeterminate` with a stated reason), never an accusatory severity.
* Convention ambiguity (one- vs two-tailed alpha, per-group vs total N) must be
  tried both ways or disclosed, never silently assumed and then graded.
* A printed number is an interval; float representation noise must never turn
  an explicit tolerance test accusatory.

Each `test_*_refuses_*` in the Regression classes FAILED against the pre-fix
modules (NaN summation rows came back `suspicious` through the real batch path;
an honest one-tailed power analysis came back `suspicious` under the silent
two-tailed default; a bool p came back `highly_suspicious`). The Pin classes
freeze behaviour that was verified correct, so a later fix cannot silently
weaken a real detection.
"""

import math

import pytest

from metascience_agent.tools.power_check import required_n, verify_power_analysis
from metascience_agent.tools.stalt import stalt_check
from metascience_agent.tools.summation import check_summation, check_summation_batch

NAN = float("nan")
INF = float("inf")

ACCUSATORY = ("impossible", "highly_suspicious", "suspicious")


# ---------------------------------------------------------------------------
# Summation
# ---------------------------------------------------------------------------

class TestSummationRefusesDegenerateInput:
    """A NaN is OUR extraction failing, never the paper's arithmetic."""

    def test_nan_in_values_is_refused_not_judged(self):
        r = check_summation([NAN, 50.0], 100.0, decimals=1, decimals_total=0)
        assert r["severity"] == "indeterminate"
        assert r.get("is_consistent") is None

    def test_nan_expected_sum_is_refused(self):
        r = check_summation([50.0, 50.0], NAN, decimals=1)
        assert r["severity"] == "indeterminate"

    def test_inf_in_values_is_refused(self):
        r = check_summation([INF, 50.0], 100.0, decimals=1, decimals_total=0)
        assert r["severity"] == "indeterminate"

    def test_a_nan_row_does_not_turn_the_whole_batch_accusatory(self):
        """The registry non-finite gate cannot see inside batch row dicts, so
        this is the LIVE path on which a NaN previously became a `suspicious`
        aggregate -- our failure reported in the grammar of a claim about the
        paper."""
        out = check_summation_batch([
            {"values": [33.3, 33.3, 33.3], "expected_sum": 100.0, "decimals": 1,
             "description": "good row"},
            {"values": [NAN, 50.0], "expected_sum": 100.0, "decimals": 1,
             "description": "poison row"},
        ])
        by_row = {r["row"]: r["severity"] for r in out["results"]}
        assert by_row[0] == "consistent"
        assert by_row[1] == "indeterminate"
        assert out["severity"] == "consistent"
        assert out["n_evaluated"] == 1

    def test_string_value_is_refused_not_raised_on_direct_call(self):
        r = check_summation(["n/a", 2.0], 5.0, decimals=1)
        assert r["severity"] == "indeterminate"

    def test_non_list_values_is_refused_not_raised(self):
        r = check_summation(5.0, 5.0, decimals=1)
        assert r["severity"] == "indeterminate"

    def test_negative_decimals_is_refused_not_auto_cleared(self):
        """decimals=-1 gave half_width 5.0 -- a window of +/-10 that clears
        anything: the false all-clear direction."""
        r = check_summation([40.0, 50.0], 100.0, decimals=-1, decimals_total=0)
        assert r["severity"] == "indeterminate"

    @pytest.mark.parametrize("tol", [NAN, INF, -0.5])
    def test_degenerate_tolerance_is_refused(self, tol):
        r = check_summation([40.0, 50.0], 100.0, tolerance=tol)
        assert r["severity"] == "indeterminate"


class TestSummationFloatNoise:
    def test_float_representation_noise_never_beats_an_explicit_tolerance(self):
        """0.1 + 0.2 == 0.30000000000000004; a difference of 5.6e-17 against
        tolerance=0 was reported `suspicious`. A printed number is an interval
        -- the epsilon slack every rounding-basis window already gets applies
        to the explicit path too."""
        r = check_summation([0.1, 0.2], 0.3, tolerance=0)
        assert r["is_consistent"] is True
        assert r["severity"] == "consistent"


class TestSummationHonestPins:
    """Normal rounding must not flag; real discrepancies must keep flagging."""

    def test_three_times_33_3_summing_to_99_9_is_consistent(self):
        r = check_summation([33.3, 33.3, 33.3], 100.0, decimals=1)
        assert r["severity"] == "consistent"

    def test_a_column_rounding_to_100_1_is_consistent(self):
        r = check_summation([24.9, 25.1, 24.8, 25.3], 100.1,
                            decimals=1, decimals_total=1)
        assert r["severity"] == "consistent"

    def test_the_heathers_101_percent_case_still_flags(self):
        r = check_summation([48.8, 52.2], 100.0, decimals=1, decimals_total=1)
        assert r["severity"] == "suspicious"

    def test_an_exact_count_column_that_misses_still_flags(self):
        r = check_summation([10.0, 20.0], 31.0, tolerance=0)
        assert r["is_consistent"] is False
        assert r["severity"] == "suspicious"


# ---------------------------------------------------------------------------
# STALT
# ---------------------------------------------------------------------------

class TestStaltRefusesDegenerateInput:
    def test_a_string_p_is_refused_not_raised(self):
        r = stalt_check("0.03", "<0.05")
        assert r["severity"] == "indeterminate"

    def test_a_bool_p_is_refused_not_accused(self):
        """True coerces to 1.0 and previously came back `highly_suspicious`;
        a boolean is a JSON/parsing artefact, never a recomputed p."""
        r = stalt_check(True, "<0.05")
        assert r["severity"] == "indeterminate"

    def test_none_p_is_refused_not_raised(self):
        r = stalt_check(None, "<0.05")
        assert r["severity"] == "indeterminate"


class TestStaltHonestPins:
    def test_accidental_stalt_is_consistent(self):
        """Heathers' own case: authors unaware their true p is 5e-18. A
        threshold is a style-mandated floor; a tiny hidden p satisfies it."""
        assert stalt_check(5e-18, "<0.05")["severity"] == "consistent"
        assert stalt_check(1.9e-16, "<0.001")["severity"] == "consistent"

    def test_underflow_zero_p_is_consistent_not_judged(self):
        assert stalt_check(0.0, "<0.001")["severity"] == "consistent"

    def test_the_overshoot_ladder_is_pinned(self):
        assert stalt_check(0.04, "<0.001")["severity"] == "highly_suspicious"
        assert stalt_check(0.006, "<0.001")["severity"] == "suspicious"
        assert stalt_check(0.0015, "<0.001")["severity"] == "indeterminate"

    def test_a_one_tailed_overshoot_stays_indeterminate(self):
        """Authors' one-tailed p=.03 printed '<.05'; our two-tailed recompute
        is .06 -- a factor-of-2 artefact, not a contradiction."""
        assert stalt_check(0.06, "<0.05")["severity"] == "indeterminate"

    @pytest.mark.parametrize("threshold", [">0.05", "p>.05", "NS", "n.s."])
    def test_lower_bound_and_ns_forms_are_refused_not_misread(self, threshold):
        """'p > .05' claims the OPPOSITE direction; reading it as an upper
        bound would grade the wrong claim."""
        r = stalt_check(0.03, threshold)
        assert r["severity"] == "indeterminate"


# ---------------------------------------------------------------------------
# Power
# ---------------------------------------------------------------------------

class TestPowerConventionAmbiguity:
    """Rule: a convention must be tried both ways or disclosed, never silently
    assumed and then graded against."""

    def test_an_honest_one_tailed_paper_is_not_accused_under_the_default(self):
        """Paper powered one-tailed (needs 102 total at d=0.5); caller left the
        tail convention unstated. Grading against the silently-assumed
        two-tailed 128 gave `suspicious` -- a false accusation about correct
        arithmetic."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=102)
        assert r["severity"] not in ACCUSATORY
        assert r["severity"] == "indeterminate"
        assert "tail" in r["explanation"].lower()

    def test_an_explicitly_two_tailed_paper_keeps_full_sensitivity(self):
        """When the caller states tails=2 (the paper said so), N=102 against a
        requirement of 128 is a real shortfall and must still flag."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=102, tails=2)
        assert r["severity"] == "suspicious"

    def test_per_group_n_passed_without_the_flag_is_not_accused(self):
        """Paper: '64 per group required'; caller passes 64 with the default
        total-N reading. 64 IS the per-group requirement -- the units-confusion
        signature -- and previously came back `suspicious`."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=64, tails=2)
        assert r["severity"] not in ACCUSATORY
        assert r["severity"] == "indeterminate"
        assert "per" in r["explanation"].lower()

    def test_a_gross_shortfall_still_flags_even_with_tails_unstated(self):
        """N=30 reconciles under NO reading (one-tailed needs 102, per-group
        needs 64): sensitivity to real underpowering is preserved."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=30)
        assert r["severity"] == "suspicious"

    def test_an_intermediate_shortfall_with_stated_tails_still_flags(self):
        """N=100 with tails=2 stated: not the per-group signature (64), short
        of the requirement (128) -- stays suspicious. Pinned so the rescue
        cannot silently widen."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=100, tails=2)
        assert r["severity"] == "suspicious"


class TestPowerRefusesDegenerateInput:
    @pytest.mark.parametrize("n", [0, -5])
    def test_nonpositive_n_reported_is_refused_not_accused(self, n):
        """N=0 is an extraction failure, not a recruited sample; it previously
        came back `suspicious underpowered_vs_stated_parameters`."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80, n_reported=n)
        assert r["severity"] == "indeterminate"
        assert r.get("verdict") != "underpowered_vs_stated_parameters"

    def test_nan_n_reported_is_refused_without_accusatory_grammar(self):
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=NAN)
        assert r["severity"] == "indeterminate"
        assert r.get("verdict") != "underpowered_vs_stated_parameters"
        assert "shortfall of nan" not in r.get("explanation", "")

    @pytest.mark.parametrize("es", [NAN, INF])
    def test_nonfinite_effect_size_is_refused_not_raised(self, es):
        r = verify_power_analysis("two_sample_t", es, 0.05, 0.80, n_reported=128)
        assert r["severity"] == "indeterminate"

    @pytest.mark.parametrize("tails", [0, -1, 3])
    def test_invalid_tails_is_refused_not_raised(self, tails):
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=128, tails=tails)
        assert r["severity"] == "indeterminate"

    @pytest.mark.parametrize("tails", [0, -1, 3])
    def test_required_n_invalid_tails_is_refused_not_raised(self, tails):
        r = required_n("two_sample_t", 0.5, tails=tails)
        assert r["severity"] == "indeterminate"

    @pytest.mark.parametrize("es", [NAN, INF])
    def test_required_n_nonfinite_effect_is_refused_not_raised(self, es):
        r = required_n("two_sample_t", es)
        assert r["severity"] == "indeterminate"


class TestPowerHonestPins:
    def test_over_recruiting_for_dropout_never_flags(self):
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=142, tails=2)
        assert r["severity"] == "consistent"
        assert r["verdict"] == "over_recruited"

    def test_over_recruit_with_inflation_flag_off_is_labelled_truthfully(self):
        """142 does not 'match' 128; with the flag off it was labelled
        `reproduces` with an explanation asserting a match that is false."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=142, tails=2,
                                  allows_attrition_inflation=False)
        assert r["severity"] == "consistent"
        assert r["verdict"] == "over_recruited"
        assert "matches" not in r["explanation"]

    def test_missing_inputs_stay_a_reporting_finding(self):
        r = verify_power_analysis("two_sample_t", 0.5, None, 0.80,
                                  n_reported=128)
        assert r["severity"] == "indeterminate"
        assert r["missing_inputs"] == ["alpha"]

    def test_exact_reproduction_is_consistent(self):
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=128, tails=2)
        assert r["severity"] == "consistent"
        assert r["verdict"] == "reproduces"

    def test_required_n_two_tailed_benchmark_is_stable(self):
        assert required_n("two_sample_t", 0.5, 0.05, 0.80)["n_per_group"] == 64

    def test_required_n_one_tailed_benchmark_is_stable(self):
        assert required_n("two_sample_t", 0.5, 0.05, 0.80,
                          tails=1)["n_per_group"] == 51


class TestPowerUnequalAllocation:
    def test_a_non_unit_allocation_ratio_is_refused_not_graded_at_1_to_1(self):
        """A 2:1 design powered correctly in G*Power needs MORE total N than
        our 1:1 arithmetic; grading its per-arm numbers against a 1:1
        recomputation can accuse correct work. Unsupported designs are
        refused, not approximated."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=150, tails=2,
                                  allocation_ratio=2.0)
        assert r["severity"] == "indeterminate"
