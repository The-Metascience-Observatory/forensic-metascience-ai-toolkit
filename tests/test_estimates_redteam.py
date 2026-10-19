"""Red-team regressions for `check_estimate_ci` and `absence_of_evidence`.

Every case here was demonstrated BY EXECUTION against the pre-fix module: an
honest input returning an accusatory severity, a fabricated input returning a
clean bill, or a degenerate input crashing. The house rules these enforce:

* a tool defect, a missing input, an inferred convention or a degenerate input
  must yield a stated `indeterminate`, never an accusation;
* a printed number is an interval, and so is the p recovered from one;
* convention ambiguity (ratio vs difference; where the null is) is tried both
  ways or disclosed, never silently assumed.
"""
import math

import pytest

from metascience_agent.tools.estimates import (
    absence_of_evidence, check_estimate_ci, is_difference_measure,
    is_ratio_measure,
)


class TestTheNullIsNeverGuessed:
    """With `measure` unstated, the old code assumed null = 0 -- and recovered
    z = 7.56 from an honest `OR 1.10 [0.85, 1.42], p = .72`, accusing it of a
    "recovered p of 0.0000". Measured on honest unlabelled narrow ratio CIs
    (SE_log <= 0.2) carrying their own honest p: ~95% were accused."""

    def test_honest_unlabelled_narrow_or_with_honest_p_is_not_accused(self):
        # True p on the log scale for these printed numbers is 0.467.
        r = check_estimate_ci(1.10, 0.85, 1.42, reported_p=0.47, decimals=2)
        assert r["severity"] == "consistent"

    def test_a_p_no_reading_can_reach_is_accused_even_unlabelled(self):
        """WAS `test_..._declined_not_accused`, asserting `consistent`. That
        expectation depended entirely on the 0.005 tolerance FLOOR, as its own
        comment said: "reachable under the difference reading (recovery ~0,
        within the .005 floor)". The floor was removed 2026-08-12 because it
        made every p below 0.005 unfalsifiable against its own interval.

        The new verdict is correct on the arithmetic. `OR 1.10 [0.85, 1.42]`
        SPANS THE NULL, so the result is not significant under any reading --
        the ratio recovery is ~0.47. A reported p of .001 is incompatible with
        an interval containing 1.0, and saying so needs no assumption about
        which measure it is. The decline path still protects the case it was
        built for: readings that genuinely DISAGREE (one reachable, one not).
        """
        r = check_estimate_ci(1.10, 0.85, 1.42, reported_p=0.001, decimals=2)
        assert r["severity"] == "suspicious"

    def test_a_p_wrong_under_both_readings_is_accused_even_unlabelled(self):
        # .72 is unreachable under BOTH readings (difference ~0; ratio ~.47),
        # so the accusation is convention-proof and may fire.
        r = check_estimate_ci(1.10, 0.85, 1.42, reported_p=0.72, decimals=2)
        assert r["severity"] == "suspicious"

    def test_a_p_wrong_under_both_readings_is_still_caught(self):
        # OR 1.10 [0.85, 1.42]: difference reading recovers ~0, ratio reading
        # ~.47. A reported p = .10 is unreachable under either.
        r = check_estimate_ci(1.10, 0.85, 1.42, reported_p=0.10, decimals=2)
        assert r["severity"] == "suspicious"
        assert any("EITHER reading" in p for p in r["problems"])

    def test_unrecognised_label_gets_the_same_protection(self):
        r = check_estimate_ci(1.10, 0.85, 1.42, measure="SMR",
                              reported_p=0.47, decimals=2)
        assert r["severity"] == "consistent"

    def test_null_dependent_payload_is_none_when_the_null_is_unknown(self):
        r = check_estimate_ci(1.10, 0.85, 1.42, decimals=2)
        assert r["severity"] == "consistent"
        assert r["ci_excludes_null"] is None
        assert r["recovered_p"] is None
        assert any("measure" in n for n in r["notes"])

    def test_a_stated_measure_still_gets_the_full_check(self):
        r = check_estimate_ci(1.10, 0.85, 1.42, measure="OR",
                              reported_p=0.72, decimals=2)
        assert r["severity"] == "suspicious"


class TestAdjustedRatioLabelsAreRecognised:
    """"aOR" and "adjusted odds ratio" fell through the exact string set, so
    `absence_of_evidence` assumed null = 0 and reported the textbook null
    result [0.85, 1.42] as "excludes the null", severity `consistent` -- the
    exact inversion the measure gate was built to stop, back in through the
    front door."""

    @pytest.mark.parametrize("label", [
        "aOR", "aHR", "adjusted odds ratio", "Adjusted OR", "adjusted hazard ratio",
        "crude odds ratio", "adjusted rate ratio",
    ])
    def test_adjusted_variants_are_ratios(self, label):
        assert is_ratio_measure(label)

    def test_log_odds_ratio_is_not_a_ratio(self):
        """A log-OR is a DIFFERENCE (null 0); stripping 'log' would invert it."""
        assert not is_ratio_measure("log odds ratio")

    def test_difference_labels_are_recognised(self):
        assert is_difference_measure("mean difference")
        assert is_difference_measure("adjusted mean difference")
        assert not is_difference_measure("OR")

    def test_the_aor_inversion_is_fixed(self):
        r = absence_of_evidence(0.85, 1.42, measure="aOR")
        assert r["includes_null"] is True
        assert r["severity"] == "indeterminate"     # null included, no SESOI

    def test_an_unrecognised_label_is_refused_not_guessed(self):
        r = absence_of_evidence(0.85, 1.42, measure="standardised mortality thing")
        assert r["severity"] == "indeterminate"
        assert r.get("measure_required") is True
        assert "not recognised" in r["explanation"]


class TestStatedDifferenceMeasureIsNeverRescaled:
    """measure="MD" with an estimate at the geometric midpoint used to flip to
    the log scale (null 1) and emit a note claiming "measure not stated" --
    a stated measure silently overridden, and the note lied about it."""

    def test_md_stays_linear(self):
        r = check_estimate_ci(2.0, 1.0, 4.0, measure="MD", decimals=1)
        assert r["scale"] == "linear"
        assert not any("measure not stated" in n for n in r["notes"])


class TestSesoiConventions:
    """A ratio SESOI of 0.8 and of 1.25 describe the SAME equivalence band.
    The old code took the band as [1/sesoi, sesoi] literally, so sesoi = 0.8
    gave the unsatisfiable band [1.25, 0.8] and every honest equivalent
    interval was reported `suspicious`; sesoi = 0 divided by zero."""

    def test_sesoi_below_one_is_the_same_band(self):
        lo = absence_of_evidence(0.90, 1.10, measure="OR", sesoi=0.8)
        hi = absence_of_evidence(0.90, 1.10, measure="OR", sesoi=1.25)
        assert hi["severity"] == "consistent"
        assert lo["severity"] == "consistent"
        assert lo["equivalence_supported"] is True

    def test_sesoi_zero_on_a_ratio_refuses_instead_of_crashing(self):
        r = absence_of_evidence(0.90, 1.10, measure="OR", sesoi=0.0)
        assert r["severity"] == "indeterminate"

    def test_sesoi_at_the_null_is_degenerate(self):
        r = absence_of_evidence(0.90, 1.10, measure="OR", sesoi=1.0)
        assert r["severity"] == "indeterminate"

    def test_sesoi_zero_linear_is_degenerate(self):
        r = absence_of_evidence(-0.1, 0.1, measure="MD", sesoi=0.0)
        assert r["severity"] == "indeterminate"

    def test_a_genuinely_violated_sesoi_still_fires(self):
        r = absence_of_evidence(0.72, 1.95, measure="OR", sesoi=1.25)
        assert r["severity"] == "suspicious"


class TestDegenerateInputsRefuse:
    """Crashes and NaN-driven verdicts are our failures; they must surface as
    stated refusals, not accusations or tool errors. (The registry's
    non-finite gate covers the MCP path; the CLI calls the module directly.)"""

    def test_null_value_zero_on_a_ratio_refuses_instead_of_crashing(self):
        # math.log(0) raised ValueError before -- even without a reported p.
        r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR", null_value=0.0)
        assert r["severity"] == "indeterminate"

    def test_confidence_level_one_refuses(self):
        r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR",
                              reported_p=0.012, confidence_level=1.0)
        assert r["severity"] == "indeterminate"

    def test_confidence_level_in_percent_refuses(self):
        r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR",
                              reported_p=0.012, confidence_level=95)
        assert r["severity"] == "indeterminate"
        assert "0.95" in r["explanation"]

    def test_nan_estimate_refuses_not_accuses(self):
        # Was: suspicious, "the estimate nan lies outside its own CI".
        r = check_estimate_ci(float("nan"), 1.08, 1.87, measure="OR")
        assert r["severity"] == "indeterminate"

    def test_infinite_bound_refuses_not_clears(self):
        # Was: consistent, with recovered_se = inf in the payload.
        r = check_estimate_ci(1.42, 1.08, float("inf"), measure="OR")
        assert r["severity"] == "indeterminate"

    def test_string_inputs_refuse_or_coerce_but_never_crash(self):
        r = check_estimate_ci("1.42", "1.08", "1.87", measure="OR")
        assert r["severity"] == "consistent"
        r = check_estimate_ci("not a number", 1.08, 1.87)
        assert r["severity"] == "indeterminate"

    def test_reversed_bounds_refuse_in_both_tools(self):
        assert check_estimate_ci(1.42, 1.87, 1.08)["severity"] == "indeterminate"
        assert absence_of_evidence(1.87, 1.08)["severity"] == "indeterminate"

    def test_absence_zero_width_is_refused_not_cleared(self):
        # [0.85, 0.85] excludes the null, so the old code returned a green
        # "no absence-of-effect claim arises" from what is almost certainly an
        # extraction echo of a single number.
        r = absence_of_evidence(0.85, 0.85, measure="OR")
        assert r["severity"] == "indeterminate"

    def test_absence_nonfinite_refuses(self):
        r = absence_of_evidence(0.85, float("inf"), measure="OR")
        assert r["severity"] == "indeterminate"
        assert "finite" in r["explanation"] or "not finite" in r["explanation"]

    def test_absence_negative_bound_on_a_ratio_refuses(self):
        r = absence_of_evidence(-0.2, 1.42, measure="OR")
        assert r["severity"] == "indeterminate"


class TestZeroWidthPayloadHygiene:
    """se = 0 made the inline recovery emit recovered_p = 0.0 and
    recovered_z = inf even when no p was supplied -- Infinity is not valid
    strict JSON, and a recovered p of 0.0 reads as a real recovery."""

    def test_recovered_fields_are_none_not_zero_and_inf(self):
        r = check_estimate_ci(1.0, 1.0, 1.0, measure="RR", decimals=1)
        assert r["severity"] == "consistent"
        assert r["recovered_p"] is None
        assert r["recovered_z"] is None

    def test_payload_is_strict_json_serialisable(self):
        import json
        r = check_estimate_ci(1.0, 1.0, 1.0, measure="RR", decimals=1)
        json.dumps(r, allow_nan=False)

    def test_absence_unbounded_largest_effect_is_none_not_inf(self):
        r = absence_of_evidence(0.0, 2.0, measure="OR")
        assert r["largest_compatible_effect"] is None
        assert "unbounded" in r["explanation"]


class TestMixedPrecisionContainment:
    """est printed 2.95 (2 dp) with an upper bound printed 2.9 (1 dp) is the
    correct rounding of 2.9451 <= 2.949: the estimate and each bound round
    INDEPENDENTLY, so the honest worst case is one half-width on each side.
    The old single-half-width slack (with no epsilon) accused it."""

    def test_the_honest_mixed_precision_triple_is_not_accused(self):
        r = check_estimate_ci(2.95, 2.8, 2.9, measure="OR", decimals=1)
        assert r["severity"] == "consistent"

    def test_a_clear_containment_violation_is_still_caught(self):
        # decimals stated: at 1 dp the doubled slack is 0.1 and 3.0 is far
        # outside [0.9, 2.5]. (Without `decimals` the integral 3.0 drags the
        # fallback to 0 dp, whose wider interval honestly reaches 2.549 -- the
        # deliberate errs-wide direction of the fallback.)
        r = check_estimate_ci(3.0, 0.9, 2.5, decimals=1)
        assert r["severity"] == "suspicious"
        assert any("outside" in p for p in r["problems"])


class TestTinyReportedPIsFalsifiable:
    """Two stacked defects made any sufficiently small reported p pass:

    * `str(1e-08)` has no decimal point, so `_p_tolerance` granted it a
      rounding slack of 0.5 -- `OR 1.42 [1.08, 1.87], p = 1e-8` (recovered
      p = .0123 at EVERY common level >= .0008) returned `consistent` with no
      notes at all;
    * the level-inference rescue used a flat +/-.005 window around the point
      recovery at the best alternative level, so p = .00001 was waved through
      as "behaves like a 99% CI" territory even though the 99% recovery is
      ~.001, two orders of magnitude away.
    """

    def test_p_1e8_is_flagged(self):
        r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR",
                              reported_p=1e-8, decimals=2)
        assert r["severity"] == "suspicious"

    def test_p_00001_is_flagged(self):
        r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR",
                              reported_p=0.00001, decimals=2)
        assert r["severity"] == "suspicious"

    def test_the_coherent_99_percent_reading_is_still_rescued(self):
        # p = .001 IS what this interval produces as a 99% CI (recovered
        # .000998), so the mislabelled-level rescue must survive the fix.
        r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR",
                              reported_p=0.001, decimals=2)
        assert r["severity"] == "consistent"
        assert r["inferred_confidence_level"] == 0.99

    def test_a_bonferroni_style_level_is_not_newly_accused(self):
        # A 99.17% (six-way Bonferroni) CI with its honest unadjusted p: the
        # nearest common level is 99% and the reachable-interval rescue must
        # absorb the .9917-vs-.99 difference. This pins the rescue against
        # over-tightening.
        r = check_estimate_ci(1.42, 0.98, 2.06, measure="OR",
                              reported_p=0.012, decimals=2)
        assert r["severity"] == "consistent"
        assert r["inferred_confidence_level"] == 0.99

    def test_an_honest_tiny_p_with_a_tiny_recovery_stays_clean(self):
        # logOR 0.9163 (OR 2.5), SE_log 0.18 -> z = 5.09, p = 3.6e-7,
        # 95% CI [1.76, 3.56]. Printed "p < .001" and extracted as .001.
        r = check_estimate_ci(2.5, 1.76, 3.56, measure="OR",
                              reported_p=0.001, decimals=2)
        assert r["severity"] == "consistent"


class TestHonest90PercentCI:
    def test_stated_90_percent_level_is_used_throughout(self):
        # se_log = .1252: 90% CI [1.06, 1.60] around 1.30, p = .036.
        r = check_estimate_ci(1.30, 1.06, 1.60, measure="OR",
                              reported_p=0.036, confidence_level=0.90,
                              decimals=2)
        assert r["severity"] == "consistent"
        assert r["problems"] == []
        assert r["inferred_confidence_level"] is None
