"""A censored p is a bound, not a rounded value.

"P < .001" is how the clinical literature reports its smallest p-values, and it
is the single commonest reported p in this project's archive (69 of 1,204 calls
that pass one). It reaches every check as the float `0.001`, indistinguishable
from an exact "P = .001", and until 2026-08-12 the shared predicate applied a
ROUNDING ALLOWANCE to it -- treating the endpoint of an interval claim as
though it were the rounded rendering of some unprinted number.

Two consequences, both pinned below:

1.  The allowance was 0.005 whenever the caller did not declare a precision, so
    a paper claiming "P < .001" was cleared by numbers implying p = .006. Six
    times the claim.
2.  Declaring `p_is_threshold=True` -- the parameter whose entire purpose is to
    say "this is a bound" -- did not shrink the allowance at all. The
    declaration was inert in the direction it was invented for.

The protection against INPUT rounding is unchanged and lives where it belongs:
the caller tests the low end of the achievable p interval, so a bound is
contradicted only when no reading of the rounded b and se can reach it. That is
what keeps this from becoming a false-accusation machine on honest tables, and
it is pinned here too.
"""

import scipy.stats as st

from forensic_metascience_ai_toolkit.registry import BY_NAME
from forensic_metascience_ai_toolkit.tools.regression import check_regression
from forensic_metascience_ai_toolkit.tools.ttest import _p_matches


def _coefficient_for(target_p: float, se: float = 0.0100, df: int = 200):
    """A (b, se) pair whose two-tailed p is `target_p` at four printed decimals."""
    t = float(st.t.isf(target_p / 2, df))
    return round(t * se, 4), se


class TestABoundIsHeldToTheNumberPrinted:
    def test_six_times_the_claim_no_longer_passes(self):
        # The regression. reported_p=0.001 with no declared precision used to
        # carry a +/- 0.005 slab, so anything up to .006 cleared.
        assert not _p_matches(0.004, 0.001, p_is_threshold=True)
        assert not _p_matches(0.006, 0.001, p_is_threshold=True)

    def test_the_declaration_now_changes_the_answer(self):
        # Undeclared, the slab still governs -- that path is deliberately
        # untouched, because most callers cannot yet say which they have.
        # Declared, the same computed p is a finding. If these two ever agree
        # again the parameter has gone inert a second time.
        assert _p_matches(0.004, 0.001)
        assert not _p_matches(0.004, 0.001, p_is_threshold=True)

    def test_a_correctly_reported_bound_still_clears(self):
        # The cardinal rule. Every honest "P < .001" in the literature has a
        # true p far below .001; none of them may become a finding.
        for computed in (1e-12, 1e-6, 5e-4, 9.9e-4, 1.0e-3):
            assert _p_matches(computed, 0.001, p_is_threshold=True), computed

    def test_the_bound_itself_is_not_a_finding(self):
        # Exactly at the claim, within floating-point noise.
        assert _p_matches(0.001, 0.001, p_is_threshold=True)
        assert _p_matches(0.001 + 1e-15, 0.001, p_is_threshold=True)


class TestInputRoundingStillProtects:
    """A bound is contradicted only when NO reading of the rounded inputs
    reaches it. The tool passes both ends of the achievable p interval, so the
    tightened predicate cannot convict a coefficient whose printed precision
    leaves the claim attainable."""

    def test_an_honest_bound_survives_the_tightening(self):
        b, se = _coefficient_for(5e-4)
        r = check_regression(b=b, se=se, df=200, reported_p=0.001,
                             decimals_b=4, decimals_se=4, decimals_p=3,
                             p_is_threshold=True)
        assert r["severity"] == "consistent"

    def test_a_real_overclaim_is_caught(self):
        b, se = _coefficient_for(4e-3)
        r = check_regression(b=b, se=se, df=200, reported_p=0.001,
                             decimals_b=4, decimals_se=4,
                             p_is_threshold=True)
        lo, _hi = r["calculated_p_interval"]
        assert lo > 0.001, "the premise: no reading of the inputs reaches .001"
        assert r["severity"] == "suspicious"

    def test_that_same_overclaim_used_to_be_cleared(self):
        # Same call WITHOUT the declaration: still consistent, because the slab
        # is still what governs an undeclared p. This is the measured gap the
        # registry change exists to close, not a second defect.
        b, se = _coefficient_for(4e-3)
        r = check_regression(b=b, se=se, df=200, reported_p=0.001,
                             decimals_b=4, decimals_se=4)
        assert r["severity"] == "consistent"

    def test_a_coarse_se_still_refuses_to_convict(self):
        # se printed to two decimals admits a 3x range, and the achievable p
        # interval reaches below the claim. No accusation may be issued.
        r = check_regression(b=0.016, se=0.01, df=200, reported_p=0.05,
                             decimals_b=3, decimals_se=2, decimals_p=2,
                             p_is_threshold=True)
        assert r["severity"] == "consistent"


class TestTheModelCanActuallySayIt:
    """The predicate is only worth having if the declaration reaches it. Of the
    thirteen registry tools that take a p, three could be told it was a bound
    before this change -- and none of the three was `check_regression`, which
    accounts for 696 of the archive's 1,204 p-carrying calls."""

    def test_check_regression_exposes_the_declaration(self):
        names = [p.name for p in BY_NAME["check_regression"].params]
        assert "p_is_threshold" in names
        assert "decimals_p" in names, (
            "179 archived check_regression calls supplied no decimals_p, "
            "because the parameter was not exposed to be supplied"
        )

    def test_both_regression_tools_tell_the_model_why(self):
        for name in ("check_regression", "check_regression_batch"):
            d = BY_NAME[name].description
            assert "p_is_threshold" in d, name
            assert ".006" in d or ".001" in d, (
                f"{name} should show the consequence, not just name the flag"
            )

    def test_the_declaration_survives_a_registry_call(self):
        b, se = _coefficient_for(4e-3)
        spec = BY_NAME["check_regression"]
        base = {"b": b, "se": se, "df": 200, "reported_p": 0.001,
                "decimals_b": 4, "decimals_se": 4}
        declared = spec.call({**base, "p_is_threshold": True})
        undeclared = spec.call(dict(base))
        assert declared["severity"] == "suspicious"
        assert undeclared["severity"] == "consistent"


class TestTheOtherCallersAreUntouched:
    """`_p_matches` backs several tools. Only callers that explicitly declare a
    bound may take the strict branch; a caller that passes a POINT p computed
    from rounded means and SDs must not, or the tightening becomes an
    accusation machine on honest group statistics."""

    def test_recalc_independent_t_threshold_reading_only_clears(self):
        """RE-PINNED 2026-08-22. The old pin asserted the SOURCE contained
        no `p_is_threshold` at all; the conventional-alpha both-readings
        guard (rulebook: a p equal to .05/.01 not declared a threshold must
        fail BOTH readings before it may accuse) legitimately uses it -- in
        the failure branch, and only to DOWNGRADE. What actually matters is
        the direction, so that is what is pinned now: the threshold reading
        may rescue a row to indeterminate, never make one more severe."""
        from forensic_metascience_ai_toolkit.tools.ttest import recalc_independent_t

        # Reported t fits neither flavor, but the data CAN reach the
        # conventional alpha as a bound: ambiguous, not an accusation.
        rescued = recalc_independent_t(10.0, 2.0, 30, 11.3, 2.0, 30,
                                       reported_t=8.00, reported_p=0.05,
                                       decimals_p=2)
        assert rescued["severity"] == "indeterminate"
        assert rescued["failure_mode"] == "p_reading_ambiguous"

        # Same t mismatch, data CANNOT reach the alpha under any flavor or
        # tail: the overclaim stands, the guard must not soften it away...
        accused = recalc_independent_t(10.0, 2.0, 30, 10.3, 2.0, 30,
                                       reported_t=8.00, reported_p=0.05,
                                       decimals_p=2)
        assert accused["severity"] == "suspicious"

        # ...and a NON-conventional p gets no threshold rescue at all: the
        # guard is scoped to the alphas a paper plausibly thresholds on.
        exact = recalc_independent_t(10.0, 2.0, 30, 11.3, 2.0, 30,
                                     reported_t=8.00, reported_p=0.047,
                                     decimals_p=3)
        assert exact["severity"] == "suspicious"

    def test_an_undeclared_p_is_judged_exactly_as_before(self):
        for computed, reported in ((0.004, 0.001), (0.06, 0.05), (0.8, 0.725)):
            assert _p_matches(computed, reported) == (
                computed <= reported + max(0.005, 0.5 * reported)
            )
