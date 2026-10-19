"""Tests for CSF, STALT, and regression checks (previously uncovered)."""

from forensic_metascience_ai_toolkit.tools.csf import csf_test
from forensic_metascience_ai_toolkit.tools.regression import check_regression
from forensic_metascience_ai_toolkit.tools.stalt import stalt_check


class TestCSF:
    """Carlisle-Stouffer-Fisher baseline-similarity test."""

    def test_apple_cider_case_stouffer(self):
        """Gold-standard apple-cider finding: baseline p = 0.93/0.99/0.99 is
        extreme uniformity and MUST be surfaced, never labeled consistent.

        DELIBERATE CHANGE (correlation-aware null). This previously asserted
        `highly_suspicious` and p < 0.001, which held only under an
        INDEPENDENCE assumption (p = 0.0002). At a realistic rho = 0.5 the same
        data give p = 0.0062, and at rho = 0.7, p = 0.0112.

        The downgrade to `suspicious` is the correct reading: THREE baseline
        rows cannot license a fabrication-grade verdict on their own, and with
        k = 3 the correlation assumption dominates the arithmetic entirely
        (the variance doubles, 3 -> 6). The apple-cider paper was established
        by converging evidence, not by this test alone.

        What must NOT regress: the finding is still raised, the direction is
        still `too_similar`, and it is never `consistent` -- that last was the
        original bug, where uniformly HIGH baseline p-values read as
        reassurance rather than as the red flag they are.
        """
        result = csf_test([0.93, 0.99, 0.99], method="stouffer")
        assert result["severity"] in ("suspicious", "highly_suspicious")
        assert result["severity"] != "consistent"
        assert result["direction"] == "too_similar"
        assert result["similarity_p"] < 0.01
        # The independence reading is retained so the downgrade is auditable.
        assert result["similarity_p_under_independence"] < 0.001

    def test_apple_cider_case_fisher(self):
        """Regression: the Fisher branch previously combined raw p-values
        (a test for too-SMALL p) and returned 'consistent' for uniformly
        high baseline p-values."""
        result = csf_test([0.93, 0.99, 0.99], method="fisher")
        assert result["severity"] in ("suspicious", "highly_suspicious")
        assert result["severity"] != "consistent"
        # See the Stouffer test above: p < 0.001 held only under an independence
        # assumption. Brown/Kost-McDermott gives p = 0.0069 at rho = 0.5, still
        # well inside the flagged range. The independence reading is retained so
        # the downgrade stays auditable.
        assert result["similarity_p"] < 0.01
        assert result["similarity_p_under_independence"] < 0.001

    def test_normal_randomization(self):
        result = csf_test([0.23, 0.71, 0.45, 0.09, 0.88], method="stouffer")
        assert result["severity"] == "consistent"
        assert result["direction"] == "normal"

    def test_p_equal_one_does_not_crash(self):
        """p = 1.0 used to produce ±inf z-scores via norm.ppf.

        The regression this guards is numerical: no inf, no NaN. The severity
        assertion moved because an unstated DESIGN now caps the verdict below
        `highly_suspicious` -- stratified, minimised, cluster and matched
        allocation all force baseline balance by construction and would explain
        extreme uniformity innocently. Both branches are asserted so the
        numerical fix and the sensitivity are each pinned.
        """
        result = csf_test([1.0, 1.0, 1.0], method="stouffer")
        assert result["similarity_p"] == result["similarity_p"]  # not NaN
        # Finite and small. The bound loosened from 1e-6 to 1e-3 when the upper
        # clip moved from 1 - 1e-10 to 0.995: a printed "1.00" is the rounding
        # interval [0.995, 1], and the test now reads its LEAST extreme end
        # (z = 2.58, not 6.36) rather than the most extreme representable value.
        # The severities below are what the tool actually reports and they are
        # unchanged -- three 1.00s stay capped without a design and reach
        # `highly_suspicious` with one.
        assert result["similarity_p"] < 1e-3                     # finite, still small
        assert result["severity"] == "suspicious"                # design unknown -> capped

        stated = csf_test([1.0, 1.0, 1.0], method="stouffer", design="parallel_rct")
        assert stated["severity"] == "highly_suspicious"          # sensitivity retained

    def test_rounded_ones_do_not_manufacture_a_fabrication_verdict(self):
        """A printed "1.00" is the interval [0.995, 1], not p = 0.9999999999.

        Clipping it to 1 - 1e-10 fed z = 6.36 into the excess-similarity test, so
        an honest table with a few legitimately balanced categorical rows
        (chi-square has point mass at p = 1 on exact balance) was combined to
        `highly_suspicious` on the strength of the rounding alone. At the
        conservative end of the printed interval (z = 2.58) the same honest table
        is not a finding. A recognised design is supplied so the cap is not what
        clears it -- the clip is.
        """
        honest = [1.00, 1.00, 1.00, 0.55, 0.70, 0.40, 0.85, 0.60]
        for method in ("stouffer", "fisher"):
            r = csf_test(honest, method=method, design="parallel_rct")
            assert r["severity"] != "highly_suspicious", method

    def test_a_genuine_uniformity_signature_still_fires_through_the_clip(self):
        """The clip must remove the rounding artefact, not the real signal: eight
        baseline p-values genuinely at/near 1.00 still combine to fabrication
        grade under a stated design."""
        hard = [1.00, 0.99, 0.98, 0.99, 1.00, 0.98, 0.99, 1.00]
        r = csf_test(hard, method="stouffer", design="parallel_rct")
        assert r["severity"] == "highly_suspicious"

    def test_no_valid_p_values(self):
        result = csf_test([-0.5, 1.5])
        assert "error" in result

    def test_backward_compat_combined_p(self):
        result = csf_test([0.5, 0.5, 0.5])
        assert result["combined_p"] == result["similarity_p"]


class TestSTALT:
    """Hidden-p-value threshold check."""

    def test_a_p_far_below_the_bound_is_consistent_not_accused(self):
        """p=1e-18 satisfies "< .05", so the printed claim is true. Flagging a
        true statement highly_suspicious is a false accusation against style-
        floor reporting; only a p ABOVE the bound contradicts it."""
        result = stalt_check(1e-18, "<0.05")
        assert result["severity"] == "consistent"

    def test_reasonable_p(self):
        result = stalt_check(0.03, "<0.05")
        assert result["severity"] == "consistent"

    def test_threshold_parsing_variants(self):
        for threshold in ("<0.05", "p < 0.05", "P<0.05", "≤0.05", "0.05", "= 0.05"):
            result = stalt_check(0.03, threshold)
            assert result.get("threshold_value") == 0.05, threshold

    def test_unparseable_threshold(self):
        result = stalt_check(0.03, "significant")
        assert "error" in result
        assert result["severity"] == "indeterminate"

    def test_p_zero_does_not_crash(self):
        """p = 0 implies infinite orders of magnitude; must not overflow.

        The severity was incidental to this test's real point (no crash). p=0
        satisfies "< .001", so it is consistent, not the old highly_suspicious
        -- that was the same false accusation the two tests above pinned."""
        result = stalt_check(0.0, "<0.001")
        assert result["severity"] == "consistent"

    def test_invalid_p(self):
        assert "error" in stalt_check(1.5, "<0.05")


class TestRegressionCheck:
    """t = B/SE consistency check."""

    def test_matching_t(self):
        result = check_regression(b=2.0, se=0.5, reported_t=4.0)
        assert result["t_matches"] is True
        assert result["severity"] == "consistent"

    def test_mismatching_t(self):
        result = check_regression(b=2.0, se=0.5, reported_t=2.0)
        assert result["t_matches"] is False
        assert result["severity"] == "suspicious"

    def test_p_value_check(self):
        # t = 4.0, df = 100 → p ≈ 0.00012
        result = check_regression(b=2.0, se=0.5, reported_p=0.0001, df=100)
        assert result["p_matches"] is True

    def test_zero_se(self):
        result = check_regression(b=2.0, se=0.0)
        assert "error" in result

    def test_negative_se(self):
        # A negative dispersion is OUR parse artefact (an en dash or a range
        # separator read as a minus), never something an analysis prints, so
        # it is a REFUSAL rather than an accusation -- matching the sibling
        # `recalc_independent_t`, which had it right all along. It was also a
        # ceiling violation: this tool is declared `probabilistic`.
        result = check_regression(b=2.0, se=-0.5)
        assert "error" in result
        assert result["severity"] == "indeterminate"

    def test_no_reported_values(self):
        result = check_regression(b=2.0, se=0.5)
        assert result["severity"] == "indeterminate"
