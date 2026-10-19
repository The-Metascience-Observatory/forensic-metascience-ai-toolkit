"""Estimate/CI reconciliation and absence-of-evidence.

Motivated by two corpus measurements: 353 estimate-with-CI triples that no tool
could read, and 30.6% of papers asserting an absence of effect somewhere.
"""
import math
import shutil
import subprocess

import pytest
from scipy import stats

from forensic_metascience_ai_toolkit.tools.estimates import (
    absence_of_evidence, check_estimate_ci, is_ratio_measure,
)


class TestRatioScale:
    """Ratios are symmetric on the LOG scale. Testing linear symmetry would flag
    every correctly-reported odds ratio in the literature."""

    @pytest.mark.parametrize("measure", ["OR", "odds_ratio", "RR", "hazard_ratio", "HR", "IRR"])
    def test_ratio_measures_recognised(self, measure):
        assert is_ratio_measure(measure)

    @pytest.mark.parametrize("measure", ["mean_difference", "SMD", "cohens_d", "beta"])
    def test_difference_measures_not_treated_as_ratios(self, measure):
        assert not is_ratio_measure(measure)

    def test_correct_ratio_is_consistent(self):
        r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR")
        assert r["severity"] == "consistent"
        assert r["scale"] == "log"
        assert r["implied_centre"] == pytest.approx(math.sqrt(1.08 * 1.87), rel=1e-6)

    @pytest.mark.parametrize("lo,hi", [(0.50, 8.00), (0.20, 20.0), (0.10, 40.0)])
    def test_arithmetic_midpoint_on_a_wide_ratio_ci_is_caught(self, lo, hi):
        """An estimate that is the LINEAR midpoint of a ratio CI is a scale error."""
        r = check_estimate_ci(round((lo + hi) / 2, 3), lo, hi, measure="OR")
        assert r["severity"] == "suspicious"
        assert any("log scale" in p for p in r["problems"])

    @pytest.mark.parametrize("lo,hi", [(1.08, 1.87), (0.90, 1.10)])
    def test_narrow_ratio_ci_does_not_manufacture_a_scale_finding(self, lo, hi):
        """On a narrow CI the two midpoints differ by a few percent -- below the
        rounding and adjusted-vs-unadjusted noise floor. Flagging there would be
        a false positive, so the check deliberately stays silent."""
        r = check_estimate_ci(round((lo + hi) / 2, 3), lo, hi, measure="OR")
        assert r["severity"] == "consistent"

    def test_non_positive_ratio_refuses(self):
        r = check_estimate_ci(0.0, -1.0, 1.87, measure="OR")
        assert r["severity"] == "indeterminate"


class TestUnlabelledScaleInference:
    """When the caller does not NAME the measure, assuming linear flags every
    correctly-reported odds/risk/hazard ratio -- its CI is symmetric in LOG
    space. So an unnamed measure tries both scales and adopts log only when the
    estimate is the geometric midpoint and NOT the arithmetic one.
    """

    def test_unlabelled_odds_ratio_is_not_accused(self):
        # 1.5 IS the geometric midpoint of [0.9, 2.5]; the arithmetic is 1.7.
        # With `measure` omitted this returned `suspicious` before the fix.
        r = check_estimate_ci(1.5, 0.9, 2.5)
        assert r["severity"] == "consistent"
        assert r["scale"] == "log"
        assert any("geometric midpoint" in n.lower() for n in r["notes"])

    def test_unlabelled_hazard_ratio_is_not_accused(self):
        r = check_estimate_ci(2.0, 1.0, 4.0)  # geo mid = 2.0, arith mid = 2.5
        assert r["severity"] == "consistent"

    def test_unrecognised_ratio_label_is_rescued(self):
        # "adjusted odds ratio" is not in the exact ratio set, so it defaulted to
        # linear and false-accused; the data-driven inference rescues it.
        r = check_estimate_ci(1.5, 0.9, 2.5, measure="adjusted odds ratio")
        assert r["severity"] == "consistent"

    def test_a_genuinely_off_estimate_is_still_flagged(self):
        # 1.2 is neither the arithmetic (1.7) nor the geometric (1.5) midpoint,
        # so no scale rescues it -- still suspicious.
        r = check_estimate_ci(1.2, 0.9, 2.5)
        assert r["severity"] == "suspicious"

    def test_a_linear_estimate_stays_linear(self):
        # 5.0 is the arithmetic midpoint of [3, 7]; it fits linear, so no flip.
        r = check_estimate_ci(5.0, 3.0, 7.0)
        assert r["severity"] == "consistent"
        assert r["scale"] == "linear"

    def test_the_flip_never_hides_an_out_of_ci_estimate(self):
        # decimals stated: the integral 3.0 would otherwise drag the fallback
        # to 0 dp, whose wider rounding interval honestly reaches 2.549.
        r = check_estimate_ci(3.0, 0.9, 2.5, decimals=1)
        assert r["severity"] == "suspicious"
        assert any("outside" in p for p in r["problems"])

    def test_a_labelled_ratio_still_catches_the_arithmetic_midpoint(self):
        # The inference only runs for UNNAMED measures; a named ratio keeps the
        # full scale-error detection.
        r = check_estimate_ci(1.7, 0.9, 2.5, measure="odds_ratio")
        assert r["severity"] == "suspicious"


class TestReconciliation:
    def test_recovered_p_matches_closed_form(self):
        r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR")
        se = (math.log(1.87) - math.log(1.08)) / (2 * stats.norm.ppf(0.975))
        expected = 2 * (1 - stats.norm.cdf(abs(math.log(1.42) / se)))
        assert r["recovered_p"] == pytest.approx(expected, rel=1e-9)

    def test_estimate_outside_own_ci_is_flagged(self):
        r = check_estimate_ci(2.5, 1.08, 1.87, measure="OR")
        assert r["severity"] == "suspicious"
        assert any("outside its own CI" in p for p in r["problems"])

    def test_reversed_bounds_are_refused_not_accused(self):
        """Transposed bounds are the modal EXTRACTION error -- at least as often
        ours as the paper's -- so they are a refusal, not a finding."""
        r = check_estimate_ci(1.42, 1.87, 1.08, measure="OR")
        assert r["severity"] == "indeterminate"
        assert "reversed" in r["explanation"].lower()

    def test_p_disagreeing_with_ci_is_flagged(self):
        r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR", reported_p=0.42)
        assert r["severity"] == "suspicious"

    def test_difference_measure_uses_linear_scale(self):
        r = check_estimate_ci(0.35, 0.10, 0.60, measure="mean_difference", reported_p=0.006)
        assert r["severity"] == "consistent"
        assert r["scale"] == "linear"


class TestConfidenceLevelGuard:
    """A 'wrong' p is usually a different confidence level, not an error."""

    def test_mislabelled_90_percent_ci_is_inferred_not_accused(self):
        se = 0.15
        z90 = stats.norm.ppf(0.95)
        lo, hi = math.exp(math.log(1.30) - z90 * se), math.exp(math.log(1.30) + z90 * se)
        p_true = 2 * (1 - stats.norm.cdf(math.log(1.30) / se))
        r = check_estimate_ci(1.30, round(lo, 2), round(hi, 2), measure="OR",
                              reported_p=round(p_true, 3))
        assert r["severity"] == "consistent"
        assert r["inferred_confidence_level"] == 0.90
        assert r["notes"]


class TestAbsenceOfEvidence:
    """'Not significant' is not 'no effect'."""

    def test_wide_null_including_ci_is_not_evidence_of_absence(self):
        r = absence_of_evidence(0.72, 1.95, measure="OR")
        assert r["severity"] == "indeterminate"
        assert r["includes_null"] is True
        assert r["sesoi_provided"] is False
        assert "not 'no effect'" in r["explanation"]

    def test_no_sesoi_means_no_equivalence_claim(self):
        r = absence_of_evidence(0.72, 1.95, measure="OR")
        assert "equivalence" in r["recommendation"].lower()
        assert "equivalence_supported" not in r

    def test_tight_ci_within_sesoi_supports_equivalence(self):
        r = absence_of_evidence(0.95, 1.06, measure="OR", sesoi=1.25)
        assert r["severity"] == "consistent"
        assert r["equivalence_supported"] is True

    def test_wide_ci_outside_sesoi_contradicts_a_no_effect_claim(self):
        r = absence_of_evidence(0.72, 1.95, measure="OR", sesoi=1.25)
        assert r["severity"] == "suspicious"
        assert r["equivalence_supported"] is False

    def test_significant_result_raises_no_absence_claim(self):
        r = absence_of_evidence(1.08, 1.87, measure="OR")
        assert r["severity"] == "consistent"
        assert r["includes_null"] is False

    def test_largest_compatible_effect_is_reported(self):
        r = absence_of_evidence(-0.30, 0.45, measure="mean_difference")
        assert r["largest_compatible_effect"] == pytest.approx(0.45)

    def test_no_claim_means_no_escalation(self):
        """If the paper never asserts absence, we do not manufacture a finding."""
        r = absence_of_evidence(0.72, 1.95, measure="OR", sesoi=1.25,
                                claim_of_no_effect=False)
        assert r["severity"] == "indeterminate"


def _r_available() -> bool:
    return bool(shutil.which("Rscript"))


@pytest.mark.skipif(not _r_available(), reason="R not installed")
def test_se_and_p_match_r():
    # Ask R for full double precision; sprintf("%.10f") truncates below the
    # tolerance we want to assert.
    out = subprocess.run(["Rscript", "-e", (
        'se <- (log(1.87)-log(1.08))/(2*qnorm(0.975)); z <- log(1.42)/se; '
        'cat(format(se, digits=17), format(2*(1-pnorm(abs(z))), digits=17))')],
        capture_output=True, text=True, timeout=180).stdout.split()
    r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR")
    assert r["recovered_se"] == pytest.approx(float(out[0]), rel=1e-12)
    assert r["recovered_p"] == pytest.approx(float(out[1]), rel=1e-12)


class TestTheDecimalsFallbackErrsWideOnly:
    """The parsed-float fallback may only err toward the WIDER interval.

    The two possible misreads are not symmetric. Too LOOSE waves a real
    discrepancy through; too TIGHT reports correct rounding as a problem -- a
    false accusation. The old `str()`-based fallback read an integral value as
    1 dp (ten times too tight: honest "OR 4 (1-9)", the correct 0 dp rounding
    of 3.6 (1.4-9.4), came back `suspicious`), and read `1e-08` as 0 dp (a
    slack of 0.5, which made every tiny reported p unfalsifiable). It now
    delegates to `rounding.decimals_of_value`, which errs wide in both cases.
    """

    def test_trailing_zeros_read_coarser_hence_looser(self):
        from forensic_metascience_ai_toolkit.tools import rounding as R
        from forensic_metascience_ai_toolkit.tools.estimates import _decimals
        assert _decimals(1.40) == 1          # printed to 2 dp, read as 1
        assert R.half_width(1) == pytest.approx(10 * R.half_width(2))

    def test_integral_values_read_at_zero_decimals(self):
        from forensic_metascience_ai_toolkit.tools.estimates import _decimals
        assert _decimals(5.0) == 0           # was 1 -- ten times too tight
        assert _decimals(4) == 0

    def test_the_honest_integer_printed_ratio_is_not_accused(self):
        """"OR 4 (1-9)" is the correct 0 dp rounding of 3.6 (1.4-9.4); with
        `decimals` omitted the old fallback read every value as 1 dp and
        called it suspicious."""
        r = check_estimate_ci(4.0, 1.0, 9.0, measure="OR")
        assert r["severity"] == "consistent"

    def test_a_scientific_notation_p_keeps_its_precision(self):
        """`str(1e-08)` has no decimal point, so the old fallback read it as
        0 dp and granted a rounding slack of 0.5 -- no reported p could ever be
        flagged. This pins the INTENT: a tiny p gets a tiny slack.

        It used to assert the mechanism instead (`== 0.005`, the absolute
        floor). The floor was removed 2026-08-12: applied to a quantity
        spanning orders of magnitude it made every p below 0.005 unfalsifiable
        against its own interval, and accepted a printed `p = .001` against a
        recovered 0.008. Reading the decimal-equivalent precision achieves the
        original intent more exactly than the floor ever did -- 1e-8 now earns
        5e-9 rather than 0.005.
        """
        from forensic_metascience_ai_toolkit.tools.estimates import _p_tolerance
        assert _p_tolerance(1e-8) == pytest.approx(5e-9)
        # The intent, stated as an inequality rather than a magic number.
        assert _p_tolerance(1e-8) < 1e-8, "a tiny p must earn a tiny slack"
        assert _p_tolerance(0.05) == pytest.approx(0.005), "2 dp is unchanged"


class TestAlphaStraddleIsNotClassified:
    """A p printed AT alpha does not say which side of alpha it is on.

    "p = .05" asserts [.045, .055], which straddles alpha = .05, and a CI whose
    bound prints as exactly the null says no more. Yet the significance
    cross-check classified it and reported the disagreement as a problem.

    The failing case is an entirely coherent triple: log-OR 0.40 with SE 0.206
    gives p = .0522 and a 95% CI of (0.9962, 2.2339) -- which print as
    "OR 1.49 [1.00, 2.24], p = .05". Every number is the correct rounding of one
    self-consistent result, and it was reported `suspicious`.

    The branch also fired only because `0.05 < (1 - 0.95)` is True by floating
    point, so its mirror case was passing by luck rather than by reasoning.
    """

    COHERENT = dict(estimate=1.49, ci_low=1.00, ci_high=2.24,
                    measure="OR", decimals=2)

    def test_the_coherent_triple_is_not_a_problem(self):
        r = check_estimate_ci(reported_p=0.05, **self.COHERENT)
        assert r["severity"] == "consistent"
        assert r["problems"] == []

    def test_the_refusal_is_explained_rather_than_silent(self):
        r = check_estimate_ci(reported_p=0.05, **self.COHERENT)
        assert any("not cross-checked" in n for n in r["notes"])

    def test_a_p_clearly_below_alpha_is_still_checked(self):
        """Declining at the boundary must not disable the check."""
        r = check_estimate_ci(reported_p=0.004, **self.COHERENT)
        assert r["severity"] == "suspicious"
        assert any("includes the null" in p for p in r["problems"])

    def test_a_p_clearly_above_alpha_is_still_checked(self):
        r = check_estimate_ci(estimate=1.60, ci_low=1.20, ci_high=2.10,
                              measure="OR", reported_p=0.65, decimals=2)
        assert r["severity"] == "suspicious"
        assert any("excludes the null" in p for p in r["problems"])

    def test_the_p_precision_comes_from_the_p_not_from_decimals(self):
        """`decimals` is the precision of the ESTIMATE and its interval; a CI
        given to 2 dp says nothing about how many digits the p carries. A p
        printed to 3 dp asserts a tenth of the interval and IS placeable."""
        r = check_estimate_ci(reported_p=0.047, **self.COHERENT)
        assert not any("not cross-checked" in n for n in r["notes"])


class TestRecoveredPIsAnInterval:
    """The recovered p is computed from three ROUNDED values, so it is a range.

    The recovery divides by the width the interval implies and measures the
    estimate's distance from the null, so it is most sensitive exactly when the
    values are printed coarsely -- which is when the point recovery deserves
    least trust. A true estimate of 0.54 with SE 0.22 gives p = .0141 and a CI
    of (0.1088, 0.9712); printed at 1 dp that reads "0.5 [0.1, 1.0], p = .014",
    the point recovery returns .0294, and the honest report was flagged.
    """

    def test_a_coarsely_printed_ci_is_not_accused(self):
        r = check_estimate_ci(0.5, 0.1, 1.0, measure="MD", reported_p=0.014,
                              decimals=1)
        assert r["severity"] == "consistent"

    def test_the_reachable_range_is_reported_when_it_does_fire(self):
        r = check_estimate_ci(1.42, 1.08, 1.87, measure="OR", reported_p=0.42,
                              decimals=2)
        assert r["severity"] == "suspicious"
        assert any("reachable range" in p for p in r["problems"])

    def test_the_null_is_reachable_when_it_sits_inside_the_estimates_interval(self):
        """p is NOT monotone in the estimate -- it peaks at the null and falls
        away either side -- so the box corners never sample p = 1. Omitting the
        null as a candidate is what convicted the large-N table pattern."""
        from forensic_metascience_ai_toolkit.tools.estimates import _recovered_p_interval
        lo, hi = _recovered_p_interval(1.02, 0.9, 1.2, 0.95, True, 1.0, 1)
        assert hi == pytest.approx(1.0, abs=1e-9)


class TestZeroWidthIntervalIsRefusedNotAccused:
    """"RR 1.0 (1.0-1.0), p = .32" is the ordinary large-N table pattern.

    Honest at RR 1.002 (0.998-1.006). At the printed precision the interval has
    no width, so the recovery divides by zero: 0/0 gave a NaN whose numpy
    warning escaped, and a non-zero numerator gave an infinity that printed as
    "the p recovered from the CI is 0.0000". Both are OUR arithmetic failing on
    an unusable input, and both were reported as claims about the paper.
    """

    def test_the_large_n_pattern_is_not_accused(self):
        r = check_estimate_ci(1.0, 1.0, 1.0, measure="RR", reported_p=0.32,
                              decimals=1)
        assert r["severity"] == "consistent"

    def test_the_refusal_names_the_reason_and_the_remedy(self):
        r = check_estimate_ci(1.0, 1.0, 1.0, measure="RR", reported_p=0.32,
                              decimals=1)
        note = next(n for n in r["notes"] if "not cross-checked" in n)
        assert "zero width" in note
        assert "more decimals" in note

    def test_the_recovery_returns_nan_rather_than_a_number(self):
        """A caller must be able to tell a failed recovery from a real value."""
        import math

        from forensic_metascience_ai_toolkit.tools.estimates import _p_from_ci
        assert math.isnan(_p_from_ci(1.0, 1.0, 1.0, 0.95, True, 1.0))
        assert math.isnan(_p_from_ci(0.5, 0.5, 0.5, 0.95, False, 0.0))


class TestAbsenceOfEvidenceCanDeriveItsOwnInterval:
    """MEASURED across the archive: 7 papers could not be checked here at all,
    and the reviews said so in their own words --

        "The paper's headline null claim could not be evaluated with
         absence_of_evidence because the paper reports NO confidence intervals
         anywhere, and that tool requires ci_low/ci_high. Deriving a CI from B
         and SE would be interval arithmetic performed by hand, which is barred."

    Three of those papers print b AND se, which determines the interval
    completely, and in two of them the null result IS the paper's conclusion.
    The one check that spoke to the headline claim was the one that could not
    run, on the papers where it mattered most.

    The model was RIGHT to refuse -- doing that arithmetic by hand is exactly
    what it is forbidden to do. The fix belongs in the tool."""

    def test_b_and_se_are_enough(self):
        from forensic_metascience_ai_toolkit.tools.estimates import absence_of_evidence
        r = absence_of_evidence(b=0.12, se=0.31, measure="b",
                                sesoi=0.5, null_value=0.0)
        assert r["severity"] != "indeterminate"
        assert r["derivation"]["interval_source"] == "derived"

    def test_the_arithmetic_is_the_ordinary_wald_interval(self):
        from forensic_metascience_ai_toolkit.tools.estimates import absence_of_evidence
        d = absence_of_evidence(b=0.12, se=0.31, measure="b",
                                sesoi=0.5, null_value=0.0)["derivation"]
        lo, hi = d["derived_ci"]
        assert lo == pytest.approx(0.12 - 1.959964 * 0.31, abs=1e-4)
        assert hi == pytest.approx(0.12 + 1.959964 * 0.31, abs=1e-4)

    def test_df_selects_the_t_distribution_and_says_so(self):
        """Silently choosing a distribution is how a bound becomes wrong
        without anyone being able to see why."""
        from forensic_metascience_ai_toolkit.tools.estimates import absence_of_evidence
        d = absence_of_evidence(b=0.12, se=0.31, df=12, measure="b",
                                sesoi=0.5, null_value=0.0)["derivation"]
        assert "t with 12 df" in d["distribution"]
        assert d["critical_value"] > 1.959964      # t is wider than z
        z = absence_of_evidence(b=0.12, se=0.31, measure="b", sesoi=0.5,
                                null_value=0.0)["derivation"]
        assert "normal" in z["distribution"]

    def test_a_derived_interval_never_passes_as_the_paper_s(self):
        from forensic_metascience_ai_toolkit.tools.estimates import absence_of_evidence
        d = absence_of_evidence(b=0.12, se=0.31, measure="b",
                                sesoi=0.5, null_value=0.0)["derivation"]
        assert "NOT printed by the paper" in d["note"]
        assert "inherits the rounding" in d["note"]

    def test_a_printed_interval_wins_and_ours_is_shown_beside_it(self):
        """Two intervals for one coefficient that DISAGREE is a finding in its
        own right; silently preferring either would bury it."""
        from forensic_metascience_ai_toolkit.tools.estimates import absence_of_evidence
        r = absence_of_evidence(ci_low=-0.20, ci_high=0.44, b=0.12, se=0.31,
                                measure="b", sesoi=0.5, null_value=0.0)
        assert "printed" in r["derivation"]["interval_source"]
        assert r["derivation"]["derived_ci"][0] == pytest.approx(-0.4876, abs=1e-3)

    def test_neither_input_is_still_a_clean_refusal(self):
        from forensic_metascience_ai_toolkit.tools.estimates import absence_of_evidence
        r = absence_of_evidence(measure="b")
        assert r["severity"] == "indeterminate"
        assert "refusal, not a finding" in r["explanation"]

    def test_a_nonpositive_se_refuses_rather_than_inventing_a_bound(self):
        from forensic_metascience_ai_toolkit.tools.estimates import absence_of_evidence
        for bad in (0, -0.3, float("nan")):
            r = absence_of_evidence(b=0.12, se=bad, measure="b")
            assert r["severity"] == "indeterminate"

    def test_the_printed_path_is_completely_unchanged(self):
        """The derivation was added IN FRONT of the judgement, not inside it.
        A caller passing an interval must get exactly what it always got."""
        from forensic_metascience_ai_toolkit.tools.estimates import absence_of_evidence
        r = absence_of_evidence(ci_low=-0.49, ci_high=0.73, measure="b",
                                sesoi=0.5, null_value=0.0)
        assert "derivation" not in r
        assert r["severity"] != "indeterminate"


class TestThresholdPClaims:
    """`reported_p_operator` makes 'P < .001' -- the modal p format in clinical
    journals -- expressible.

    Measured on 10.1001/jamanetworkopen.2023.51752 (forensic_review, 2026-08-09):
    the paper's two abstract-headline rows print 'P < .001' against 95% CIs whose
    implied p is .018 and .0024. The sweep had no way to pass the threshold, so
    stage 1 dropped the p (check silently skipped, verdict `consistent`) and
    stage 2 coerced it to `= .001` (rescued as a mislabelled 99% CI, verdict
    `consistent`). Both encodings recorded the paper's strongest internal
    inconsistency as clean. A threshold is an interval claim: "p < x" is
    consistent iff some p below x is reachable from the printed CI."""

    def test_the_headline_case_is_flagged_at_every_common_level(self):
        """ARR 0.185 (0.046-0.748): implied p is .018 at 95% and .0018 at 99%,
        so 'P < .001' is unreachable at ANY common level -- flagged."""
        r = check_estimate_ci(0.185, 0.046, 0.748, measure="RR",
                              reported_p=0.001, reported_p_operator="<")
        assert r["severity"] == "suspicious"
        assert any("p < 0.001" in p for p in r["problems"])

    def test_a_threshold_reachable_at_99_is_rescued_with_a_note(self):
        """ARR 0.217 (0.081-0.582): implied p .0024 at 95% but 6.6e-5 at 99%.
        A mislabelled level explains it, so the claim is rescued -- same
        policy as the exact-p path, disclosed in a note."""
        r = check_estimate_ci(0.217, 0.081, 0.582, measure="RR",
                              reported_p=0.001, reported_p_operator="<")
        assert r["severity"] == "consistent"
        assert r["inferred_confidence_level"] == 0.99
        assert any("99%" in n for n in r["notes"])

    def test_an_honest_threshold_is_consistent(self):
        """Implied p ~.03 satisfies 'P < .05' outright: no note, no problem."""
        r = check_estimate_ci(0.7, 0.51, 0.96, measure="RR",
                              reported_p=0.05, reported_p_operator="<")
        assert r["severity"] == "consistent"
        assert not r["problems"]

    def test_a_gt_claim_is_the_mirror(self):
        """'P > .99' against a near-null RR whose implied p is ~.97: reachable
        within the printed rounding of the bounds, or at the LOWEST common
        level (recovered p rises as the level falls) -- never accused."""
        r = check_estimate_ci(1.0, 0.828, 1.207, measure="RR",
                              reported_p=0.99, reported_p_operator=">")
        assert r["severity"] == "consistent"

    def test_a_significant_threshold_against_a_null_including_ci_reads_both_ways(self):
        """'P < .001' printed beside a CI that CONTAINS the null is one
        comparison read two ways: unreachable p, and a significance claim the
        interval contradicts. Both are stated; still one finding, gated on the
        reachability failure (same policy as the exact-p path)."""
        r = check_estimate_ci(0.9, 0.6, 1.35, measure="RR",
                              reported_p=0.001, reported_p_operator="<")
        assert r["severity"] == "suspicious"
        assert len(r["problems"]) == 2
        assert any("includes the null" in p for p in r["problems"])

    def test_an_operator_without_a_p_is_a_refusal(self):
        r = check_estimate_ci(0.185, 0.046, 0.748, measure="RR",
                              reported_p_operator="<")
        assert r["severity"] == "indeterminate"
        assert "refusal" in r["explanation"]

    def test_an_unrecognised_operator_is_a_refusal_not_a_default(self):
        """Silently reading '~' as '=' would judge a claim the paper never
        made."""
        r = check_estimate_ci(0.185, 0.046, 0.748, measure="RR",
                              reported_p=0.001, reported_p_operator="~")
        assert r["severity"] == "indeterminate"

    def test_a_threshold_with_no_scale_at_all_is_declined(self):
        """Unstated measure AND an estimate that fits both midpoints: the null
        is unknowable, and the point logic would misread 'p < x' with a
        reachable p far BELOW x as a failure. Declined with a note instead."""
        r = check_estimate_ci(5.0, 1.0, 9.0,
                              reported_p=0.001, reported_p_operator="<")
        assert r["severity"] == "consistent"
        assert not r["problems"]
        assert any("threshold claim" in n for n in r["notes"])

    def test_the_default_operator_leaves_the_exact_p_path_byte_identical(self):
        """Regression pin: every archived call carries no operator, and replay
        across the 11-run corpus moved ZERO verdicts on this change."""
        for kw in (dict(reported_p=0.001),
                   dict(reported_p=0.05),
                   dict()):
            old_style = check_estimate_ci(0.185, 0.046, 0.748, measure="RR", **kw)
            explicit = check_estimate_ci(0.185, 0.046, 0.748, measure="RR",
                                         reported_p_operator="=", **kw)
            assert old_style == explicit
