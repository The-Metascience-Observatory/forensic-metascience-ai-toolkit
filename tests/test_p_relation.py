"""An EXACT printed p is checked in both directions; a BOUND only from below.

Every p tool used to tolerate a printed p ABOVE what its statistic allows,
because "p < .05" against a true 2e-5 is a true statement. That is right for a
bound and wrong for an exact value, and it hid documented published errors.
Each `TestPublishedErrors` case is a real one, found by benchmarking the tools
agent on the statcheck_pvalue_errors corpus (2026-10-18); every one came back
`consistent` before 1.86.0. The other classes pin that the protection for
bounds, and for each tool's alternative conventions, still holds.
"""
from __future__ import annotations

import pytest

from metascience_agent import registry as R
from metascience_agent.tools.anova import recalc_f_to_p, recalc_one_way_anova
from metascience_agent.tools.chi_squared import recalc_chi_squared
from metascience_agent.tools.estimates import check_estimate_ci
from metascience_agent.tools.regression import check_regression, check_regression_batch
from metascience_agent.tools.stat_to_p import recalc_stat_to_p
from metascience_agent.tools.ttest import (looks_like_printed_bound,
                                           recalc_independent_t,
                                           resolve_p_relation)

UNDER = "reported_p_above_recomputed"


def _under(r: dict) -> None:
    assert r["severity"] == "suspicious", r
    assert r["failure_mode"] == UNDER, r
    assert r["p_direction"] == "under_claim"


class TestPublishedErrors:
    """Real published p-value errors. None may come back `consistent`."""

    def test_claesen_t_decision_error(self):
        # 10.1037/a0024422 (Claesen et al. 2023 manual coding): t(38) = 3.94
        # printed with p = .696; the true p is .00034.
        for rel in ("=", None):
            r = recalc_stat_to_p(statistic=3.94, kind="t", df=38, reported_p=0.696,
                                 decimals_stat=2, decimals_p=3, p_relation=rel)
            _under(r)
            assert r["decision_error"] is True
        r = recalc_stat_to_p(statistic=3.94, kind="t", df=38, reported_p=0.696,
                             decimals_stat=2, decimals_p=3)
        assert r["p_relation_basis"] == "not_bound_shaped"

    def test_f_decision_error(self):
        # 10.1037/a0028447: F(2, 66) = 11.38 printed with p = .26; true 6e-5.
        _under(recalc_stat_to_p(statistic=11.38, kind="f", df=2, df2=66,
                                reported_p=0.26, decimals_p=2))
        r = recalc_f_to_p(11.38, 2, 66, reported_p=0.26, decimals_p=2)
        _under(r)
        assert r["decision_error"] is True
        # df2 unstated: no denominator df reaches .26 either.
        _under(recalc_f_to_p(11.38, 2, None, reported_p=0.26, decimals_p=2,
                             p_relation="="))

    def test_singh_chi_squared_2x2(self):
        # Singh 1997, 10.1093/gerona/52A.1.M27 (audit ACE2026002): printed .71
        # against Pearson .314, Yates .522, Fisher .467.
        r = recalc_chi_squared(observed=[[5, 12], [7, 8]], reported_p=0.71,
                               decimals_p=2)
        _under(r)
        assert r["largest_convention_p"] == pytest.approx(0.5219, abs=1e-3)

    def test_singh_chi_squared_2x3(self):
        # Same paper: printed .63, Pearson .23, exact Fisher-Freeman-Halton .35.
        r = recalc_chi_squared(observed=[[3, 4, 10], [0, 4, 11]], reported_p=0.63,
                               decimals_p=2, p_relation="=")
        _under(r)
        assert r["calculated_p_freeman_halton"] == pytest.approx(0.3504, abs=1e-3)

    def test_heymsfield_stated_level_not_overridden(self):
        # 10.1001/jamanetworkopen.2020.33457, journal-corrected to P = .10:
        # estimate 1.37, 80% CI 0.31-2.43, printed P = .01.
        r = check_estimate_ci(estimate=1.37, ci_low=0.31, ci_high=2.43,
                              measure="MD", reported_p=0.01, confidence_level=0.8)
        assert r["severity"] == "suspicious", r
        assert r["failure_mode"] == "reconciles_only_at_other_level"
        assert r["level_that_reconciles"] == pytest.approx(0.95)
        assert r["inferred_confidence_level"] is None
        # The corrected value reconciles at the stated level.
        ok = check_estimate_ci(estimate=1.37, ci_low=0.31, ci_high=2.43,
                               measure="MD", reported_p=0.10, confidence_level=0.8)
        assert ok["severity"] == "consistent", ok

    def test_heymsfield_without_measure(self):
        # With the measure unstated BOTH readings must fail before flagging,
        # and at the stated 80% they both do.
        r = check_estimate_ci(estimate=1.37, ci_low=0.31, ci_high=2.43,
                              reported_p=0.01, confidence_level=0.8)
        assert r["severity"] == "suspicious", r

    def test_through_the_registry(self):
        # The MCP path must accept the new parameter.
        r = R.BY_NAME["recalc_stat_to_p"].call(
            {"statistic": 3.94, "kind": "t", "df": 38, "reported_p": 0.696,
             "decimals_stat": 2, "decimals_p": 3, "p_relation": "="})
        _under(r)
        r = R.BY_NAME["recalc_chi_squared"].call(
            {"observed": [[5, 12], [7, 8]], "reported_p": 0.71, "decimals_p": 2,
             "p_relation": "="})
        _under(r)


class TestBoundsStayProtected:
    """A printed bound is true of any smaller p. None of these may flag."""

    @pytest.mark.parametrize("rel", ["<", "<=", None])
    def test_p_below_001(self, rel):
        r = recalc_stat_to_p(statistic=12.5, kind="t", df=60, reported_p=0.001,
                             decimals_stat=1, decimals_p=3, p_relation=rel)
        assert r["severity"] == "consistent", r

    def test_unknown_conventional_alpha_keeps_the_bound_reading(self):
        r = recalc_stat_to_p(statistic=3.94, kind="t", df=38, reported_p=0.05,
                             decimals_stat=2, decimals_p=2)
        assert r["severity"] == "consistent"
        assert r["p_relation_basis"] == "unknown"
        # ... and says what the exact reading would conclude.
        assert r["under_claim_if_exact"] is True

    def test_stated_bound_on_any_value(self):
        r = recalc_stat_to_p(statistic=3.94, kind="t", df=38, reported_p=0.696,
                             decimals_stat=2, decimals_p=3, p_relation="<")
        assert r["severity"] == "consistent"

    def test_chi_squared_p_below_05(self):
        # The measured shape the directional rule was built for.
        r = recalc_chi_squared(observed=[[30, 10], [10, 30]], reported_p=0.05)
        assert r["severity"] == "consistent", r

    def test_regression_censored_p(self):
        # check_regression(b=.55, se=.13, p=.01, df=200): an honest "p < .01".
        assert check_regression(b=0.55, se=0.13, reported_p=0.01, df=200,
                                p_is_threshold=True)["severity"] == "consistent"
        assert check_regression(b=0.55, se=0.13, reported_p=0.01, df=200,
                                decimals_p=2)["severity"] == "consistent"

    def test_independent_t_bound(self):
        r = recalc_independent_t(10, 2, 30, 12, 2, 30, reported_p=0.001,
                                 decimals_p=3, p_relation="<")
        assert r["severity"] == "consistent"


class TestAlternativeConventionsStillRescue:
    """An exact p matching ANY convention the tool tries is not an under-claim."""

    def test_yates_p(self):
        r = recalc_chi_squared(observed=[[5, 12], [7, 8]], reported_p=0.52,
                               decimals_p=2, p_relation="=")
        assert r["severity"] == "consistent", r

    def test_freeman_halton_p(self):
        r = recalc_chi_squared(observed=[[3, 4, 10], [0, 4, 11]], reported_p=0.35,
                               decimals_p=2, p_relation="=")
        assert r["severity"] == "consistent", r

    def test_statistic_rounding_window(self):
        # t printed 2.0 spans [1.95, 2.1) once truncation is allowed, so an
        # exact p anywhere in that window's p range is consistent.
        r = recalc_stat_to_p(statistic=2.0, kind="t", df=20, reported_p=0.062,
                             decimals_stat=1, decimals_p=3, p_relation="=")
        assert r["severity"] == "consistent", r

    def test_independent_t_input_rounding(self):
        # Means printed to 0 dp: the largest reachable p is far above the
        # point recomputation, and the under-claim test uses it.
        r = recalc_independent_t(10, 2, 30, 12, 2, 30, reported_p=0.06,
                                 decimals_p=2, p_relation="=")
        assert r["severity"] == "consistent", r
        assert r["largest_achievable_p"] > 0.06

    def test_independent_t_under_claim(self):
        # Only when the paper says THIS t-test produced its p (1.90.0): a test
        # rebuilt from printed means/SDs is otherwise not the paper's test.
        r = recalc_independent_t(10.0, 2.0, 30, 12.0, 2.0, 30, reported_p=0.43,
                                 decimals_p=2, decimals_mean=1, decimals_sd=1,
                                 p_relation="=", test_confirmed=True)
        _under(r)

    def test_independent_t_under_claim_unconfirmed_is_not_a_finding(self):
        # Default (1.90.0): an ANCOVA, mixed-model or Welch p legitimately exceeds
        # the simple t's, so a printed p above it is indeterminate, not suspicious.
        r = recalc_independent_t(10.0, 2.0, 30, 12.0, 2.0, 30, reported_p=0.43,
                                 decimals_p=2, decimals_mean=1, decimals_sd=1,
                                 p_relation="=")
        assert r["severity"] == "indeterminate", r
        assert r["failure_mode"] == "under_claim_unconfirmed_test", r
        assert r["p_direction"] == "under_claim"


class TestEveryTailReadingIsHeldToTheRelation:
    """An exact p must sit inside SOME reading's interval, from both sides.

    Found by the full suite on 1.86.0's first cut: the one-tailed reading still
    used the bound-only test, so an exact .05 against a two-tailed [.057, .058]
    was 'rescued' by a one-tailed .029 it under-claims -- laxer than the old
    `p_is_threshold=False`, which held both readings two-sided."""

    def test_regression_exact(self):
        # T3 Constant M1 of the round-29 scaffold paper: -13.55 (6.99), p = .05.
        args = dict(b=-13.55, se=6.99, reported_p=0.05, df=57, decimals_b=2,
                    decimals_se=2, decimals_p=2)
        assert check_regression(p_is_threshold=False, **args)["severity"] == "suspicious"
        assert check_regression(p_relation="=", **args)["severity"] == "suspicious"
        # As a BOUND, "p < .05" is true of the one-tailed .029: rescued only
        # when the paper states one-tailed testing (1.93.0).
        assert check_regression(p_relation="<", **args)["severity"] == "suspicious"
        bound = check_regression(p_relation="<", one_tailed_stated=True, **args)
        assert bound["severity"] == "consistent"
        assert bound["p_reconciles_one_sided_only"] is True

    def test_regression_one_tailed_still_rescues_its_own_value(self):
        # A printed p that IS the one-tailed value reconciles, and says so.
        r = check_regression(b=-13.55, se=6.99, reported_p=0.029, df=57,
                             decimals_b=2, decimals_se=2, decimals_p=3,
                             p_relation="=", one_tailed_stated=True)
        assert r["severity"] == "consistent", r
        assert r["p_reconciles_one_sided_only"] is True

    def test_f_one_df(self):
        # F(1, 40) = 4.0 two-tailed p ~ .052; an exact .04 is neither reading.
        r = recalc_f_to_p(4.0, 1, 40, reported_p=0.04, decimals_p=2, decimals_f=1,
                          p_relation="=")
        assert r["severity"] == "suspicious", r
        half = recalc_f_to_p(4.0, 1, 40, reported_p=0.026, decimals_p=3,
                             decimals_f=1, p_relation="=", one_tailed_stated=True)
        assert half["severity"] == "indeterminate", half
        unstated = recalc_f_to_p(4.0, 1, 40, reported_p=0.026, decimals_p=3,
                                 decimals_f=1, p_relation="=")
        assert unstated["severity"] == "suspicious", unstated


class TestRelations:

    def test_greater_than_contradicted(self):
        # "p > .05" on a statistic whose p is .0003: a decision error.
        r = recalc_stat_to_p(statistic=3.94, kind="t", df=38, reported_p=0.05,
                             decimals_stat=2, p_relation=">")
        _under(r)
        assert r["decision_error"] is True

    def test_greater_than_never_over_claims(self):
        # "p > .05" on a statistic whose p is .6: true, nothing to flag. The
        # directional over-claim test would have read it as p = .05 claimed.
        for fn, kw in ((recalc_stat_to_p, dict(statistic=0.5, kind="t", df=38)),
                       (recalc_f_to_p, dict(f_value=0.5, df1=2, df2=40))):
            r = fn(reported_p=0.05, p_relation=">", **kw)
            assert r["severity"] == "consistent", (fn.__name__, r)

    def test_unknown_spelling_refuses(self):
        r = recalc_stat_to_p(statistic=3.94, kind="t", df=38, reported_p=0.6,
                             p_relation="~")
        assert r["severity"] == "indeterminate" and "p_relation" in r["error"]

    def test_contradiction_with_p_is_threshold_refuses(self):
        r = check_regression(b=0.55, se=0.13, reported_p=0.31, df=200,
                             p_is_threshold=True, p_relation="=")
        assert r["severity"] == "indeterminate"

    def test_legacy_flag_maps_to_relation(self):
        assert resolve_p_relation(None, 0.05, True)["relation"] == "<"
        assert resolve_p_relation(None, 0.05, False)["relation"] == "="
        assert resolve_p_relation("≤", 0.05)["relation"] == "<"

    @pytest.mark.parametrize("p", [0.1, 0.05, 0.01, 0.005, 0.001, 0.0001, 1e-10, 0.0])
    def test_bound_shapes(self, p):
        assert looks_like_printed_bound(p)

    @pytest.mark.parametrize("p", [0.696, 0.26, 0.71, 0.03, 0.5, 1.0])
    def test_not_bound_shapes(self, p):
        assert not looks_like_printed_bound(p)


class TestSeverityCap:
    """An under-claim is a reporting inconsistency: never above `suspicious`."""

    def test_extreme_under_claim_is_still_suspicious(self):
        r = recalc_stat_to_p(statistic=40.0, kind="t", df=500, reported_p=0.99,
                             decimals_stat=1, decimals_p=2, p_relation="=")
        _under(r)

    def test_every_tool(self):
        rows = [
            # Rebuilt from group means/SDs: an under-claim needs the paper to
            # say this ANOVA produced the p (1.90.0, `test_confirmed`).
            recalc_one_way_anova([1.0, 2.0, 3.0], [1.0, 1.0, 1.0], [10, 10, 10],
                                 reported_p=0.4, decimals_p=1, decimals_mean=1,
                                 decimals_sd=1, p_relation="=", test_confirmed=True),
            check_regression(b=0.55, se=0.13, reported_p=0.31, df=200,
                             decimals_b=2, decimals_se=2, decimals_p=2),
            check_regression_batch([{"b": 0.55, "se": 0.13, "reported_p": 0.31,
                                     "df": 200, "decimals_p": 2,
                                     "p_relation": "="}])["results"][0],
        ]
        for r in rows:
            _under(r)

    def test_anova_rebuilt_from_summaries_unconfirmed_is_not_a_finding(self):
        r = recalc_one_way_anova([1.0, 2.0, 3.0], [1.0, 1.0, 1.0], [10, 10, 10],
                                 reported_p=0.4, decimals_p=1, decimals_mean=1,
                                 decimals_sd=1, p_relation="=")
        assert r["severity"] == "indeterminate", r
        assert r["failure_mode"] == "under_claim_unconfirmed_test", r


class TestDeclaredCorrectionExplainsUnderClaim:
    """A printed p ABOVE the statistic's is explained by a correction the paper
    declares (1.90.0). MEASURED on the Wicherts, Bakker & Molenaar (2011) hand
    coding: all 12 false flags on correct statistics were Huynh-Feldt p's."""

    def test_huynh_feldt_row_is_indeterminate(self):
        # Wicherts 2011: F(9, 504) = 2.25 reported as p = .036 "huyn-feldt" (coded correct).
        r = recalc_stat_to_p(statistic=2.25, kind="f", df=9, df2=504, reported_p=0.036,
                             decimals_stat=2, decimals_p=3, p_relation="=",
                             p_adjustment="sphericity")
        assert r["severity"] == "indeterminate", r
        assert r["failure_mode"] == "under_claim_explained_by_adjustment", r

    def test_without_the_declaration_it_is_still_an_under_claim(self):
        r = recalc_stat_to_p(statistic=2.25, kind="f", df=9, df2=504, reported_p=0.036,
                             decimals_stat=2, decimals_p=3, p_relation="=")
        _under(r)

    def test_a_correction_never_excuses_an_over_claim(self):
        # t(38) = 3.94 printed p = .0001 is BELOW what the statistic allows (.00034).
        r = recalc_stat_to_p(statistic=3.94, kind="t", df=38, reported_p=0.0001,
                             decimals_stat=2, decimals_p=4, p_relation="=",
                             p_adjustment="multiplicity")
        assert r["severity"] == "suspicious", r

    def test_unknown_spelling_refuses(self):
        r = recalc_stat_to_p(statistic=2.25, kind="f", df=9, df2=504, reported_p=0.036,
                             p_adjustment="bonferonni")
        assert r["severity"] == "indeterminate" and "p_adjustment" in r["error"]


class TestDeclaredBoundHasNoSlack:
    """"p < .01" is written exactly (1.90.0). MEASURED on the Wicherts hand
    coding: with rounding slack, bound errors like this passed."""

    def test_bound_above_the_statistic_is_caught(self):
        # Wicherts 2011 (labelled error): t(15) = 2.75, p < .01 -- true p .0149.
        r = recalc_stat_to_p(statistic=2.75, kind="t", df=15, reported_p=0.01,
                             decimals_stat=2, decimals_p=2, p_relation="<")
        assert r["severity"] == "suspicious", r

    def test_unknown_relation_on_an_alpha_keeps_the_slack(self):
        # Not declared: .01 might be an exact value, so the old tolerance stays.
        r = recalc_stat_to_p(statistic=2.75, kind="t", df=15, reported_p=0.01,
                             decimals_stat=2, decimals_p=2)
        assert r["severity"] != "suspicious", r


class TestFractionalDfIsRounded:
    """A printed fractional df (Welch, Greenhouse-Geisser) is itself rounded."""

    def test_df_rounding_reconciles(self):
        # t = 2.000 at df exactly 5.5 reaches p <= .09682; a df printed as "5.5"
        # is anywhere in [5.45, 5.55), which reaches .0973 -- so p = .0972 is
        # consistent only once the df's own rounding is counted.
        r = recalc_stat_to_p(statistic=2.0, kind="t", df=5.5, reported_p=0.0972,
                             decimals_stat=3, decimals_p=4, p_relation="=")
        assert r["severity"] == "consistent", r
        assert r["achievable_p_interval"][1] > 0.0972

    def test_integer_df_is_exact(self):
        r = recalc_stat_to_p(statistic=2.0, kind="t", df=5, reported_p=0.0972,
                             decimals_stat=3, decimals_p=4, p_relation="=")
        assert r["achievable_p_interval"][1] == r["achievable_p_interval"][1]  # finite
        assert r["severity"] == "suspicious", r  # t(5) = 2.000 gives p ~ .1019


class TestStatedConfidenceLevel:

    def test_unstated_level_still_rescues(self):
        # No level stated: 95% is assumed and a mislabelled interval is a note.
        r = check_estimate_ci(estimate=1.37, ci_low=0.31, ci_high=2.43,
                              measure="MD", reported_p=0.10)
        assert r["severity"] == "consistent", r
        assert r["inferred_confidence_level"] == pytest.approx(0.8)
        assert r["confidence_level_stated"] is False

    def test_stated_95_not_overridden(self):
        # A STATED 95% whose p reconciles only as an 80% interval.
        r = check_estimate_ci(estimate=1.37, ci_low=0.31, ci_high=2.43,
                              measure="MD", reported_p=0.10, confidence_level=0.95)
        assert r["severity"] == "suspicious", r
        assert r["failure_mode"] == "reconciles_only_at_other_level"

    def test_threshold_claim_at_stated_level(self):
        # "P < .001" from an interval (0.5, 95% CI 0.1-0.9) that reaches it
        # only as a 99% CI: rescued when no level is stated, not when one is.
        args = dict(estimate=0.5, ci_low=0.1, ci_high=0.9, measure="MD",
                    reported_p=0.001, reported_p_operator="<")
        unstated = check_estimate_ci(**args)
        assert unstated["severity"] == "consistent", unstated
        assert unstated["inferred_confidence_level"] == pytest.approx(0.99)
        stated = check_estimate_ci(confidence_level=0.95, **args)
        assert stated["severity"] == "suspicious", stated
        assert stated["failure_mode"] == "reconciles_only_at_other_level"
