"""A declared threshold p was ignored on 98.9% of real calls.

`_p_matches` is shared by the t-test, ANOVA, chi-squared and regression checks,
so this one predicate decides how forgiving four tools are. It reads
`p_is_threshold` -- the caller's declaration that the paper printed a BOUND
(`p < .01`) rather than an exact value -- only inside the `decimals_p` branch.

MEASURED across every archived run in this repository: `decimals_p` is supplied
on 2 of 186 calls that pass a p to those four tools. So the branch that honours
the declaration governed 2 calls, and the symmetric fallback that ignores it
governed 184 -- among them five `reported_p: 0.05` and 179 `check_regression`
rows, which is precisely the shape it misfires on.

REPRODUCED before the fix, by execution:

    check_regression(b=0.55, se=0.13, reported_p=0.01, df=200)   -> suspicious
    ... the same call with p_is_threshold=True                   -> suspicious
    ... the same call with decimals_p=2                          -> consistent

The true p there is 3e-5. The paper reported `p < .01`, which is correct, and
UNDER-claims: it is the direction that helps nobody and is everywhere in the
literature. Flagging it is our failure reported as a fact about the paper.

The fix keeps the UPPER bound exactly where it was, so nothing caught in the
overclaiming direction stops being caught; it drops only the lower bound, and
only when the caller has not confirmed the p was printed exactly.
"""

import pytest

from forensic_metascience_ai_toolkit import registry as R
from forensic_metascience_ai_toolkit.tools.ttest import _p_matches

REG = dict(b=0.55, se=0.13, df=200)          # t = 4.23, true two-tailed p ~ 3e-5
OVER = dict(b=0.15, se=0.13, df=200)         # t = 1.15, true two-tailed p ~ .25


class TestAnHonestThresholdIsNoLongerFlagged:
    @pytest.mark.parametrize("reported_p", [0.05, 0.01, 0.001])
    def test_a_correctly_reported_bound_passes(self, reported_p):
        got = R.BY_NAME["check_regression"].fn(reported_p=reported_p, **REG)
        assert got["severity"] == "consistent", got

    def test_declaring_the_threshold_is_not_inert(self):
        """The whole point of the argument. It used to change nothing at all
        unless `decimals_p` happened to be supplied too."""
        assert R.BY_NAME["check_regression"].fn(
            reported_p=0.01, p_is_threshold=True, **REG)["severity"] == "consistent"

    def test_the_t_test_agrees(self):
        got = R.BY_NAME["recalc_independent_t"].fn(
            mean1=10.0, sd1=3.0, n1=40, mean2=12.2, sd2=3.0, n2=40, reported_p=0.05)
        assert got["severity"] == "consistent", got


class TestTheOverclaimingDirectionStillFires:
    """The fix must not buy specificity with sensitivity. The upper bound is
    unchanged, so every p the paper reported SMALLER than its own numbers
    support is still a finding."""

    @pytest.mark.parametrize("kwargs", [{}, {"p_is_threshold": True},
                                        {"p_is_threshold": False}])
    def test_a_p_smaller_than_the_data_supports_is_still_caught(self, kwargs):
        got = R.BY_NAME["check_regression"].fn(reported_p=0.01, **OVER, **kwargs)
        assert got["severity"] != "consistent", got

    def test_the_t_test_agrees(self):
        got = R.BY_NAME["recalc_independent_t"].fn(
            mean1=10.0, sd1=3.0, n1=40, mean2=10.7, sd2=3.0, n2=40, reported_p=0.01)
        assert got["severity"] != "consistent", got


class TestAConfirmedExactPIsStillCheckedBothWays:
    """`p_is_threshold=False` is the caller saying they looked and the paper
    printed an exact value. Only then is an under-claim evidence of anything,
    and the symmetric test is restored."""

    def test_an_exact_p_far_from_the_computed_one_is_flagged(self):
        got = R.BY_NAME["check_regression"].fn(
            reported_p=0.01, p_is_threshold=False, **REG)
        assert got["severity"] != "consistent", got


class TestThePredicateItself:
    def test_the_acceptance_band_never_narrowed(self):
        """Point-for-point: everything the old symmetric rule accepted, the new
        rule still accepts. Only the region BELOW the band changed."""
        for reported in (0.001, 0.01, 0.04, 0.05, 0.1, 0.5):
            tol = max(0.005, 0.5 * reported)
            for calc in (reported, reported + tol * 0.99, reported - tol * 0.99):
                assert _p_matches(calc, reported), (calc, reported)

    def test_above_the_band_is_still_rejected(self):
        for reported in (0.001, 0.01, 0.05, 0.5):
            tol = max(0.005, 0.5 * reported)
            assert not _p_matches(reported + tol * 1.5, reported), reported

    def test_below_the_band_is_accepted_unless_the_p_is_confirmed_exact(self):
        assert _p_matches(1e-6, 0.05)
        assert _p_matches(1e-6, 0.05, p_is_threshold=True)
        assert not _p_matches(1e-6, 0.05, p_is_threshold=False)
