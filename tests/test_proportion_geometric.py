"""A geometric mean is not the mean this test needs.

Right-skewed quantities -- biomarkers, titers, concentrations, exposures, costs
-- are conventionally summarised as a GEOMETRIC mean with a geometric SD, and
printed beside the prevalence above a cut-off. Both are called "mean" and "SD"
on the page, and `check_proportion_from_normal` had no way to say which it was
given.
"""

from __future__ import annotations

import pytest

from metascience_agent.tools.continuous_to_categorical import (
    check_proportion_from_normal as check)

# An honest lognormal biomarker: GM 10.0, GSD 3.0. Verified by 200,000 draws,
# the true P(X > 30) is 0.159 -- and exactly, 1 - Phi((ln30 - ln10)/ln3).
GEO = dict(mean=10.0, sd=3.0, n=200, threshold=30.0, direction="above",
           summary="geometric")


class TestADeclaredGeometricSummaryIsReadOnTheLogScale:
    def test_the_honest_paper_is_consistent(self):
        assert check(reported_proportion=0.159, **GEO)["severity"] == "consistent"

    def test_the_theoretical_proportion_is_exact(self):
        """A change of variables, not a new model: a lognormal variable is
        NORMAL IN LOGS, so taking logs of the summary and the threshold puts
        the existing machinery on exactly the right scale."""
        r = check(reported_proportion=0.159, **GEO)
        assert r["theoretical_proportion"] == pytest.approx(0.1587, abs=0.001)

    def test_it_says_what_it_did_and_that_the_model_is_ours(self):
        r = check(reported_proportion=0.159, **GEO)
        assert r["summary_scale"] == "geometric"
        assert "LOG scale" in r["explanation"]
        assert "ours rather than the paper's" in r["explanation"]

    @pytest.mark.parametrize("claimed", [0.60, 0.45, 0.02])
    def test_a_real_inconsistency_is_still_caught(self, claimed):
        """The conversion must not become "stop checking"."""
        assert check(reported_proportion=claimed, **GEO)["severity"] \
            in ("suspicious", "highly_suspicious")

    def test_the_verdict_is_capped_because_the_lognormal_model_is_ours(self):
        r = check(reported_proportion=0.60, **GEO)
        assert r["severity"] != "highly_suspicious"


class TestTheDefectItFixes:
    def test_undeclared_is_unchanged(self):
        """We cannot tell a geometric summary from two numbers, so nothing is
        assumed -- but this is exactly why the parameter has to exist."""
        r = check(reported_proportion=0.159, mean=10.0, sd=3.0, n=200,
                  threshold=30.0, direction="above")
        assert r["severity"] == "highly_suspicious"
        assert r["summary_scale"] == "arithmetic"


class TestItRefusesWhatItCannotPlaceOnALogScale:
    @pytest.mark.parametrize("gm, gsd", [(0.0, 3.0), (-1.0, 3.0), (10.0, 1.0),
                                         (10.0, 0.5)])
    def test_an_invalid_geometric_summary_is_refused(self, gm, gsd):
        """A GSD is a multiplicative factor and cannot be 1 or less."""
        r = check(reported_proportion=0.159, mean=gm, sd=gsd, n=200,
                  threshold=30.0, direction="above", summary="geometric")
        assert r["severity"] == "indeterminate"

    def test_a_non_positive_threshold_is_refused(self):
        r = check(reported_proportion=0.159, mean=10.0, sd=3.0, n=200,
                  threshold=0.0, direction="above", summary="geometric")
        assert r["severity"] == "indeterminate"


class TestArithmeticIsUntouched:
    def test_the_waz_example_from_the_module_docstring(self):
        r = check(reported_proportion=0.355, mean=-1.67, sd=0.89, n=172,
                  threshold=-2.0, direction="below")
        assert r["severity"] == "consistent"
        assert r["summary_scale"] == "arithmetic"
