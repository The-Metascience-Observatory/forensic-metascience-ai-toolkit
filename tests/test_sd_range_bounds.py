"""`check_sd_range` must not accuse on a bound it invented.

Two false accusations at `impossible` grade, both from the branches taken when
the caller does NOT supply the optional arguments -- which is exactly when the
tool knows least and should therefore accuse least.

  * n UNKNOWN used `range / 2`. That is the LARGE-n limit of the true ceiling
    `range/2 * sqrt(n/(n-1))`, which DECREASES in n -- so `range/2` is its
    infimum, the tightest possible ceiling, and the true maximum exceeds it at
    every finite n. Two patients scoring 0 and 10 have an honest sample SD of
    7.07 on a 0-10 range and were told it was impossible.
  * PRECISION UNKNOWN used a flat 1% margin, unrelated to how the value was
    printed, which convicts a coarsely printed SD.

Both fixes only ever WIDEN the admissible set, so neither can turn a real
impossibility into a pass -- the checks below pin that too.
"""

import math

import numpy as np
import pytest

from forensic_metascience_ai_toolkit.tools.sd_checks import check_sd_range


class TestUnknownNUsesTheSupremum:
    def test_the_true_maximum_exceeds_range_over_two_at_every_finite_n(self):
        """Ground truth for the bug: the old ceiling was below the real one for
        every n, so it could only ever over-accuse."""
        lo, hi = 0.0, 10.0
        for n in (2, 3, 5, 10, 100):
            worst = np.array([lo] * (n // 2) + [hi] * (n - n // 2))
            assert worst.std(ddof=1) > (hi - lo) / 2

    def test_two_honest_patients_at_the_extremes_are_not_impossible(self):
        """values 0 and 10 -> sample SD 7.0711, correctly reported as 7.07."""
        assert np.std([0, 10], ddof=1) ==  pytest.approx(7.0710678, abs=1e-6)
        r = check_sd_range(sd=7.07, min_val=0, max_val=10)
        assert r["severity"] == "consistent"

    def test_the_ceiling_is_the_n_equals_two_supremum(self):
        r = check_sd_range(sd=1.0, min_val=0, max_val=10)
        assert r["max_possible_sd"] == pytest.approx(10 / math.sqrt(2), abs=1e-9)

    def test_supplying_n_restores_the_tighter_bound(self):
        """The loosening is only the price of not knowing n; say n and the
        check regains its power."""
        loose = check_sd_range(sd=1.0, min_val=0, max_val=10)["max_possible_sd"]
        tight = check_sd_range(sd=1.0, min_val=0, max_val=10, n=100)["max_possible_sd"]
        assert tight < loose

    def test_a_gross_violation_still_fires_without_n(self):
        """Capped at `highly_suspicious` because the 0-10 range is ASSUMED
        (the default `bound_source`); the same violation against a range the
        paper states is `impossible`. See TestBoundSourceCapsTheVerdict."""
        assert check_sd_range(sd=20, min_val=0, max_val=10)["severity"] == "highly_suspicious"
        assert check_sd_range(sd=20, min_val=0, max_val=10,
                              bound_source="stated")["severity"] == "impossible"


class TestUnknownPrecisionUsesTheLiteral:
    def test_a_zero_dp_sd_is_not_convicted_by_a_flat_one_percent(self):
        """Range 0-9.4 at n=50 gives a ceiling of 4.7477. A true SD of 4.6
        prints as "5" at 0 dp; the old 1% margin (4.7952) called that
        impossible, while the value's own rounding interval reaches 4.5."""
        assert round(4.6) == 5
        r = check_sd_range(sd=5, min_val=0, max_val=9.4, n=50)
        assert r["severity"] == "consistent"

    def test_the_inferred_precision_is_declared_to_the_reader(self):
        r = check_sd_range(sd=5, min_val=0, max_val=9.4, n=50)
        assert "inferred" in r["margin_source"]

    def test_an_explicit_precision_still_wins(self):
        r = check_sd_range(sd=5, min_val=0, max_val=9.4, n=50, decimals_sd=0)
        assert r["severity"] == "consistent"
        assert "printed precision" in r["margin_source"]


class TestRealImpossibilitiesSurvive:
    """The fixes widen the admissible set; they must not empty the check.

    Since the `bound_source` guard landed, a violation against the DEFAULT
    (assumed) bounds fires at `highly_suspicious`; `impossible` needs the
    paper's own range. Both still fire -- the check is capped, not emptied.
    """

    def test_sd_far_above_the_ceiling_still_fires(self):
        assert check_sd_range(9.0, 0, 10, 30)["severity"] == "highly_suspicious"
        assert check_sd_range(9.0, 0, 10, 30,
                              bound_source="stated")["severity"] == "impossible"

    def test_the_narrow_range_case_still_fires(self):
        assert check_sd_range(9.0, 1, 7)["severity"] == "highly_suspicious"
        assert check_sd_range(9.0, 1, 7,
                              bound_source="stated")["severity"] == "impossible"

    def test_a_negative_sd_is_still_impossible(self):
        """Bound-free arithmetic: no assumption is involved, so this one is
        entitled to `impossible` whatever else is unknown."""
        assert check_sd_range(-1, 0, 10)["severity"] == "impossible"


class TestBoundSourceCapsTheVerdict:
    """`check_sd_range` may not reach `impossible` on a range NOBODY stated.

    Everything this check knows -- the ceiling itself -- is derived from
    [min_val, max_val], so a verdict against an assumed range is a statement
    about our assumption wearing the grammar of a claim about the paper.
    Verified before the fix: check_sd_range(sd=4.2, min_val=1, max_val=7,
    n=30) -> severity `impossible` with no way to say whose 1-7 that was.
    """

    def test_the_default_is_assumed_and_capped(self):
        r = check_sd_range(sd=4.2, min_val=1, max_val=7, n=30)
        assert r["bound_source"] == "assumed"
        assert r["is_plausible"] is False
        assert r["severity"] == "highly_suspicious"

    def test_a_stated_range_licenses_impossible(self):
        r = check_sd_range(sd=4.2, min_val=1, max_val=7, n=30,
                           bound_source="stated")
        assert r["severity"] == "impossible"

    def test_a_logically_necessary_range_licenses_impossible(self):
        """A proportion lives in [0, 1] whatever the paper says."""
        r = check_sd_range(sd=0.9, min_val=0, max_val=1, n=100,
                           bound_source="logically_necessary")
        assert r["severity"] == "impossible"

    def test_the_capped_explanation_names_the_bound_as_ours(self):
        r = check_sd_range(sd=4.2, min_val=1, max_val=7, n=30)
        assert "ours" in r["explanation"]
        assert "bound_source" in r["explanation"]

    def test_a_plausible_sd_is_unaffected(self):
        r = check_sd_range(sd=1.5, min_val=1, max_val=7, n=30)
        assert r["severity"] == "consistent"
