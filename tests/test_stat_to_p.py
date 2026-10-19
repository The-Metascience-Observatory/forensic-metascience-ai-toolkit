"""One printed statistic, one p-value, in any format.

MEASURED, from the reviews' own words:

  "No tool in this kit converts a chi-squared statistic plus df to a p-value...
   would require dividing the chi-squared by its df by hand."
      -- 10.3389/fnins.2023.1186751, where the missing conversion DOWNGRADED the
         headline finding from `impossible` to `highly_suspicious`

Three archived papers hit this: a chi-squared with df, an r-squared with n, and
a Pearson r with n. statcheck verifies all five of these distributions -- but
only as a TEXT SCANNER over APA grammar, so the same numbers sitting in a table
cell were invisible to the whole kit. `recalc_f_to_p` was the only value-level
sibling, which is why F could be checked and the other four could not.
"""
import math

import pytest
from scipy import stats

from metascience_agent.tools.stat_to_p import CEILING, recalc_stat_to_p


class TestTheArithmeticMatchesScipy:
    """Cross-checked against the distribution functions directly, so a wrong
    tail or a wrong df convention cannot hide behind a plausible number."""

    def test_t(self):
        got = recalc_stat_to_p(2.10, "t", df=28)["computed_p"]
        assert got == pytest.approx(2 * stats.t.sf(2.10, 28))

    def test_chi_squared(self):
        got = recalc_stat_to_p(4.10, "chi2", df=1)["computed_p"]
        assert got == pytest.approx(stats.chi2.sf(4.10, 1))

    def test_z(self):
        got = recalc_stat_to_p(1.96, "z")["computed_p"]
        assert got == pytest.approx(2 * stats.norm.sf(1.96))

    def test_pearson_r_goes_through_its_own_t(self):
        r, n = 0.35, 40
        t = r * math.sqrt((n - 2) / (1 - r * r))
        got = recalc_stat_to_p(r, "r", n=n)["computed_p"]
        assert got == pytest.approx(2 * stats.t.sf(t, n - 2))

    def test_f(self):
        got = recalc_stat_to_p(4.2, "f", df=1, df2=30)["computed_p"]
        assert got == pytest.approx(stats.f.sf(4.2, 1, 30))

    def test_aliases_are_accepted(self):
        for alias in ("chi_squared", "chisq", "x2"):
            assert recalc_stat_to_p(4.10, alias, df=1)["kind"] == "chi2"


class TestAMissingIngredientIsAFactAboutThePaper:
    """A chi-squared with no degrees of freedom cannot be converted by ANY
    implementation. Saying so -- and naming what is missing -- is the useful
    half: it belongs in a review as an incompletely reported test, not as a
    limitation of this toolkit."""

    def test_chi_squared_without_df_is_bounded_and_still_names_it(self):
        """Since 1.88.0 an unprinted df is BOUNDED, not refused (see
        `TestAnUnprintedDfIsBoundedNotRefused`); the omission is still named."""
        r = recalc_stat_to_p(180.74, "chi2")
        assert r["severity"] == "indeterminate"      # no reported p: computes only
        assert r["df_printed"] is False
        assert "property of the publication" in r["df_note"]

    def test_f_without_df_still_refuses_and_says_why_it_cannot_be_bounded(self):
        r = recalc_stat_to_p(4.2, "f", df2=30, reported_p=0.01)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False
        assert "needs df" in r["error"]
        assert "not monotone" in r["explanation"]

    def test_r_without_n_refuses(self):
        assert recalc_stat_to_p(0.35, "r")["severity"] == "indeterminate"

    def test_an_impossible_correlation_is_refused_not_computed(self):
        assert recalc_stat_to_p(1.4, "r", n=40)["severity"] == "indeterminate"

    def test_an_unknown_statistic_says_what_it_does_convert(self):
        r = recalc_stat_to_p(1.0, "kruskal", df=2)
        assert r["severity"] == "indeterminate"
        assert "chi2" in r["error"]


class TestItCannotManufactureAnAccusation:
    def test_it_never_exceeds_suspicious(self):
        assert CEILING == "suspicious"
        r = recalc_stat_to_p(0.1, "t", df=200, reported_p=1e-9, decimals_stat=1)
        assert r["severity"] == CEILING

    def test_an_under_claim_is_flagged_only_for_an_exact_p(self):
        """An under-claimed BOUND (`p < .05`) is a true statement, not a defect.
        An under-claimed EXACT p is an inconsistency, capped at `suspicious`.
        This test used to assert that `p = .5` against t(28) = 2.10 (p ~ .045)
        was consistent; 1.86.0 reads .5 -- no conventional bound -- as exact
        (tests/test_p_relation.py has the published errors behind it)."""
        assert recalc_stat_to_p(2.10, "t", df=28, reported_p=0.5, decimals_stat=2,
                                p_relation="<")["severity"] == "consistent"
        assert recalc_stat_to_p(2.10, "t", df=28, reported_p=0.05,
                                decimals_stat=2)["severity"] == "consistent"
        r = recalc_stat_to_p(2.10, "t", df=28, reported_p=0.5, decimals_stat=2)
        assert r["severity"] == "suspicious"
        assert r["failure_mode"] == "reported_p_above_recomputed"

    def test_the_statistic_s_rounding_widens_the_target(self):
        """`t = 2.1` asserts t in [2.05, 2.15), which is a p RANGE. Comparing
        the reported p to the point p of the printed statistic convicts
        honestly rounded reports."""
        r = recalc_stat_to_p(2.10, "t", df=28, reported_p=0.045, decimals_stat=2)
        lo, hi = r["achievable_p_interval"]
        assert lo < r["computed_p"] < hi
        assert r["severity"] == "consistent"

    def test_a_flag_states_the_innocent_reading(self):
        r = recalc_stat_to_p(2.10, "t", df=28, reported_p=0.0001, decimals_stat=2)
        assert r["severity"] == CEILING
        assert "one-tailed" in r["alternative_reading"]

    def test_no_reported_p_asserts_nothing_about_the_paper(self):
        r = recalc_stat_to_p(4.10, "chi2", df=1)
        assert r["severity"] == "indeterminate"
        assert "nothing is asserted" in r["explanation"]


class TestTailsAreNotAMatterOfTaste:
    def test_a_two_tailed_chi_squared_is_corrected_to_the_upper_tail(self):
        """CORRECTED 2026-08-16. This asserted the note say "category error" --
        on a df = 1 chi-squared, which is exactly where that phrasing is FALSE.
        chi2(1) = z^2, so the upper-tail p IS the two-tailed p of the underlying
        z and half of it is the one-tailed p.

        The old note is what the PNAS 0801268105 sweep paraphrased into "F has
        only an upper tail, so no one-tailed convention licenses it here",
        producing that run's headline false accusation. A test pinning the wrong
        sentence is part of how it survived: an assertion has to move with the
        behaviour or it protects the defect.

        The COMPUTATION is unchanged -- p is still the upper tail. Only what the
        tool tells the model about that p has changed.
        """
        r = recalc_stat_to_p(4.1, "chi2", df=1, tails=2)
        assert r["tails"] == 1
        assert r["computed_p"] == pytest.approx(stats.chi2.sf(4.1, 1))
        assert "category error" not in r["tails_note"]
        assert "z^2" in r["tails_note"]

    def test_an_omnibus_chi_squared_keeps_the_original_reasoning(self):
        """Above one df there is genuinely no direction to take, so the sentence
        that was wrong at df = 1 is right here."""
        r = recalc_stat_to_p(9.4, "chi2", df=4, tails=2)
        assert r["tails"] == 1
        assert "omnibus" in r["tails_note"]
        assert r["computed_p"] == pytest.approx(stats.chi2.sf(9.4, 4))

    def test_a_one_tailed_t_halves_its_p(self):
        two = recalc_stat_to_p(2.10, "t", df=28, tails=2)["computed_p"]
        one = recalc_stat_to_p(2.10, "t", df=28, tails=1)["computed_p"]
        assert one == pytest.approx(two / 2)


class TestItIsReachable:
    def test_registered_for_both_stages(self):
        from metascience_agent import registry as R
        spec = R.BY_NAME["recalc_stat_to_p"]
        assert len(spec.stages) == 2

    def test_it_is_a_replayable_calculation(self):
        from metascience_agent.evaluation.deterministic import reproducible_tools
        assert "recalc_stat_to_p" in reproducible_tools()


class TestTheRedTeamFindings:
    """Found by adversarially red-teaming this tool on the day it was written."""

    def test_unknown_tails_refuses_rather_than_guessing(self):
        """CONFIRMED FALSE ACCUSATION. `t = 1.75, df = 28, p = 0.046` returns
        `suspicious` under the two-tailed default and `consistent` at tails=1 --
        an honest one-tailed report accused of over-claiming, with "a one-tailed
        test" offered only as an after-the-fact `alternative_reading`.

        The tool already REFUSES when `decimals` is unknown rather than guessing
        a rounding interval. Guessing the tails is the same class of assumption
        deciding the same verdict, so it gets the same gate."""
        honest = dict(statistic=1.75, kind="t", df=28, reported_p=0.046,
                      decimals_stat=2)
        assert recalc_stat_to_p(**honest, tails=1)["severity"] == "consistent"
        assert recalc_stat_to_p(**honest, tails=None)["severity"] == "indeterminate"
        assert recalc_stat_to_p(**honest, tails=2)["severity"] == CEILING

    def test_the_refusal_says_why_it_matters(self):
        r = recalc_stat_to_p(1.75, "t", df=28, reported_p=0.046, tails=None)
        assert "which one the paper ran decides the verdict" in r["explanation"]

    def test_an_upper_tail_statistic_needs_no_tails_at_all(self):
        """chi2 and F have one tail by construction, so `None` is not a gap."""
        r = recalc_stat_to_p(4.1, "chi2", df=1, reported_p=0.04, tails=None)
        assert r["severity"] != "indeterminate" and r["tails"] == 1

    def test_computing_without_a_reported_p_needs_no_tails_decision(self):
        """The gate is on the COMPARISON, not on the arithmetic. With no
        reported p there is no verdict to get wrong, so it computes and says
        plainly that nothing is asserted -- and records which tails it used."""
        r = recalc_stat_to_p(2.10, "t", df=28, tails=None)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is True
        assert r["tails"] == 2 and "computed_p" in r
        assert "nothing is asserted" in r["explanation"]

    def test_a_non_finite_reported_p_is_not_a_clean_bill(self):
        """It returned `consistent` -- a false ALL-CLEAR -- because the
        comparison against NaN is always False. `ToolSpec.call` guarded it;
        `cli.py` calls the raw function."""
        r = recalc_stat_to_p(4.1, "chi2", df=1, reported_p=float("nan"))
        assert r["severity"] == "indeterminate"

    def test_a_non_finite_statistic_refuses(self):
        assert recalc_stat_to_p(float("inf"), "chi2", df=1)["severity"] == "indeterminate"


class TestTruncationIsAConventionNotADefect:
    """VERIFIED FALSE ACCUSATION in this function, found when Greg asked whether
    the truncation allowance is applied everywhere it could be. It was not: six
    modules handle it (`grim`, `debit`, `rivets`, `heuristics`, `count_percent`,
    `raw_duplication`) and eight use a symmetric window without it -- including
    this one, written the same day.

    A truncating reporter printing `chi2 = 4.1` may hold a true value up to
    4.199..., whose p is 0.0407. The symmetric +/-0.05 window bottomed out at
    0.0416, so an honest `p = .041` was flagged as over-claiming. SPSS truncates
    by default and several journal styles follow it."""

    def test_a_truncated_statistic_is_not_an_over_claim(self):
        r = recalc_stat_to_p(4.1, "chi2", df=1, reported_p=0.0407, decimals_stat=1)
        assert r["severity"] == "consistent"
        assert r["achievable_p_interval"][0] < 0.0407

    def test_the_window_is_asymmetric_the_way_truncation_implies(self):
        """Truncation puts the true value in [printed, printed + ulp); rounding
        in [printed - half, printed + half). The union is what a check may
        assume, and p decreases in the statistic."""
        from scipy import stats
        r = recalc_stat_to_p(4.1, "chi2", df=1, reported_p=0.5, decimals_stat=1)
        lo, hi = r["achievable_p_interval"]
        assert lo == pytest.approx(float(stats.chi2.sf(4.2, 1)), rel=1e-6)
        assert hi == pytest.approx(float(stats.chi2.sf(4.05, 1)), rel=1e-6)

    def test_a_real_over_claim_still_fails(self):
        """The window admits truncation; it must not admit everything."""
        assert recalc_stat_to_p(4.1, "chi2", df=1, reported_p=0.0001,
                                decimals_stat=1)["severity"] == CEILING


class TestAnUnprintedDfIsBoundedNotRefused:
    """For a fixed |t| the two-sided p FALLS as df grows; for a fixed chi2 the p
    RISES. So the printed statistic supports a p interval over EVERY admissible
    df, and a reported p outside it is wrong for every df the paper could have
    used -- no df needed.

    MEASURED 2026-10-18, statcheck_pvalue_errors working set (tools_only,
    Sonnet): two of five misses were statistics printed without df that this
    tool refused:

      Wansink et al. 2012, 10.1001/archpediatrics.2012.999 (retracted):
          `chi2 = 2.355; P = .06`
      Etindele Sosso et al. 2020, 10.1038/s41598-020-58462-0 (retracted):
          Table 3 `t = 9.748, p = .523`
    """

    # -- the premise, so a new entry in _DF_MONOTONE has to earn it ----------
    def test_the_monotonicity_the_bound_rests_on_holds(self):
        from metascience_agent.tools.stat_to_p import _DF_MONOTONE
        dfs = [1, 1.5, 2, 3, 5, 8, 13, 30, 100, 1000, 1e5]
        for x in (0.01, 0.3, 1.0, 1.96, 2.355, 4.0, 9.748, 25.0):
            t = [2 * stats.t.sf(x, d) for d in dfs]
            c = [stats.chi2.sf(x, d) for d in dfs]
            assert all(b <= a + 1e-15 for a, b in zip(t, t[1:])), x
            assert all(b >= a - 1e-15 for a, b in zip(c, c[1:])), x
        assert set(_DF_MONOTONE) == {"t", "chi2"}

    def test_f_is_excluded_because_its_p_is_not_monotone_in_df2(self):
        """The reason F still refuses: at df1 = 10, F = 0.7 the p falls and then
        rises as df2 grows, so the ends of a df range are not its extremes."""
        p = [stats.f.sf(0.7, 10, d) for d in (1, 3, 5, 100, 1e5)]
        rises = any(b > a for a, b in zip(p, p[1:]))
        falls = any(b < a for a, b in zip(p, p[1:]))
        assert rises and falls

    # -- the two measured misses ----------------------------------------------
    def test_wansink_two_tailed_fails_at_every_df(self):
        """chi2(1) = 2.355 gives p = .125, and p only grows with df, so .06 is
        unreachable two-tailed at ANY df. But chi2(1) = z^2, and the one-tailed
        1-df reading gives .062 -- which prints as .06. The tool's existing
        1-df rule then lands on INDETERMINATE with `one_tailed_reconciles`,
        exactly as it would with `df = 1` printed. (The same paper's
        `t(78) = 1.65, P = .05` is also one-tailed-exact: two-tailed .103.)"""
        r = recalc_stat_to_p(2.355, "chi2", reported_p=0.06,
                             decimals_stat=3, decimals_p=2)
        assert r["applicable"] is True
        assert r["df_printed"] is False
        assert r["df_range"] == [1.0, None]
        lo, hi = r["achievable_p_interval"]
        assert lo == pytest.approx(stats.chi2.sf(2.356, 1), rel=1e-9)
        assert lo > 0.06 + 0.005          # two-tailed: no df reaches it
        assert hi == 1.0                  # p -> 1 as df -> infinity
        assert r["one_tailed_reconciles"] is True
        # 1.93.0, statcheck's rule: the one-tailed reading rescues only a
        # paper that states it; unstated, the finding stands with it named.
        assert r["severity"] == "suspicious"
        assert r["failure_mode"] == "reconciles_only_one_tailed_unstated"
        stated = recalc_stat_to_p(2.355, "chi2", reported_p=0.06, decimals_stat=3,
                                  decimals_p=2, one_tailed_stated=True)
        assert stated["severity"] == "indeterminate"
        assert "every df" in stated["explanation"]

    def test_wansink_is_a_finding_once_the_paper_rules_out_one_df(self):
        """With df >= 2 stated, there is no one-tailed reading left and the p is
        wrong at every remaining df -- and the result says the verdict rested on
        the supplied bound."""
        r = recalc_stat_to_p(2.355, "chi2", reported_p=0.06, decimals_stat=3,
                             decimals_p=2, df_min=2)
        assert r["severity"] == CEILING
        assert r["holds_for_every_df"] is True
        assert r["verdict_needs_df_bounds"] is True
        assert "rests on the df bounds" in r["explanation"]

    def test_etindele_no_df_reaches_the_printed_p(self):
        """t = 9.748: at df = 1 two-sided p = .065, the LARGEST any df gives, so
        .523 is out of reach for every df. That is an UNDER-claim (the p is too
        large); the bound is this tool's job, the verdict on an exact p that is
        too large is the under-claim rule's."""
        r = recalc_stat_to_p(9.748, "t", reported_p=0.523,
                             decimals_stat=3, decimals_p=3)
        lo, hi = r["achievable_p_interval"]
        assert hi == pytest.approx(2 * stats.t.sf(9.7475, 1), rel=1e-9)
        assert hi < 0.065 + 1e-3 < 0.523
        assert lo < 1e-20                 # normal limit
        assert r["computed_p"] is None
        assert r["computed_p_range_over_df"][1] == pytest.approx(0.06508, abs=1e-5)

    @pytest.mark.skipif(
        "p_relation" not in __import__("inspect").signature(recalc_stat_to_p).parameters,
        reason="the exact-p under-claim rule (p_relation) is on another branch")
    def test_etindele_is_flagged_when_the_p_is_printed_exact(self):
        r = recalc_stat_to_p(9.748, "t", reported_p=0.523, decimals_stat=3,
                             decimals_p=3, p_relation="=")
        assert r["severity"] == CEILING

    # -- no false positives ----------------------------------------------------
    def test_a_p_some_df_reconciles_stays_clean(self):
        """t = 2.0, p = .06: at df = 1 p is .295, at df -> inf .046; .06 is
        inside, so SOME df reconciles it and nothing may be flagged."""
        r = recalc_stat_to_p(2.0, "t", reported_p=0.06, decimals_stat=1,
                             decimals_p=2)
        assert r["severity"] in ("consistent", "indeterminate")
        assert r["severity"] != CEILING
        lo, hi = r["achievable_p_interval"]
        assert lo < 0.06 < hi

    def test_a_large_sample_t_at_its_normal_limit_is_not_an_over_claim(self):
        """t = 1.96, p = .05 is exactly right at df -> infinity."""
        r = recalc_stat_to_p(1.96, "t", reported_p=0.05, decimals_stat=2,
                             decimals_p=2)
        assert r["severity"] == "consistent"

    def test_a_threshold_p_below_every_df_is_still_clean(self):
        """`t = 9.748, p < .05` is true at every df; a bound is never an
        over-claim."""
        r = recalc_stat_to_p(9.748, "t", reported_p=0.05, decimals_stat=3,
                             decimals_p=2)
        assert r["severity"] == "consistent"

    def test_tails_still_have_to_be_stated_for_a_t(self):
        r = recalc_stat_to_p(2.0, "t", reported_p=0.01, tails=None)
        assert r["severity"] == "indeterminate"
        assert "tails" in r["error"]

    # -- real over-claims, at every df ------------------------------------------
    def test_a_t_whose_p_no_df_supports_is_a_finding(self):
        """t = 2.00: even at df -> infinity p >= .044 (with rounding), so .01 is
        more significance than any df earns."""
        r = recalc_stat_to_p(2.0, "t", reported_p=0.01, decimals_stat=2,
                             decimals_p=2)
        assert r["severity"] == CEILING
        assert r["holds_for_every_df"] is True
        assert "ANY of those degrees of freedom" in r["explanation"]
        assert "verdict_needs_df_bounds" not in r

    def test_an_omnibus_chi2_over_claim_is_a_finding(self):
        r = recalc_stat_to_p(6.0, "chi2", reported_p=0.001, decimals_stat=1,
                             decimals_p=3)
        assert r["severity"] == CEILING
        assert r["one_tailed_reconciles"] is False
        assert r["achievable_p_interval"][0] == pytest.approx(
            stats.chi2.sf(6.1, 1), rel=1e-9)

    def test_it_never_exceeds_the_ceiling(self):
        r = recalc_stat_to_p(0.5, "t", reported_p=1e-10, decimals_stat=1,
                             decimals_p=10)
        assert r["severity"] == CEILING == "suspicious"

    # -- bounds ------------------------------------------------------------------
    def test_a_supplied_upper_bound_narrows_and_is_named(self):
        """t = 2.0, p = .04: some large df reconciles it, but df <= 10 does not.
        The flag must say it rested on that bound."""
        r = recalc_stat_to_p(2.0, "t", reported_p=0.04, decimals_stat=2,
                             decimals_p=2, df_max=10)
        assert r["severity"] == CEILING
        assert r["df_range"] == [1.0, 10.0]
        assert r["verdict_needs_df_bounds"] is True
        unbounded = recalc_stat_to_p(2.0, "t", reported_p=0.04, decimals_stat=2,
                                     decimals_p=2)
        assert unbounded["severity"] == "consistent"

    def test_a_bound_that_was_not_needed_says_so(self):
        r = recalc_stat_to_p(2.0, "t", reported_p=0.01, decimals_stat=2,
                             decimals_p=2, df_max=50)
        assert r["severity"] == CEILING
        assert r["verdict_needs_df_bounds"] is False

    @pytest.mark.parametrize("lo,hi", [(0.5, None), (10, 5), (float("inf"), None)])
    def test_an_impossible_df_range_refuses(self, lo, hi):
        r = recalc_stat_to_p(2.0, "t", reported_p=0.01, df_min=lo, df_max=hi)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_bounds_are_ignored_when_the_df_is_printed(self):
        r = recalc_stat_to_p(2.0, "t", df=28, reported_p=0.06, df_max=5)
        assert r["computed_p"] == pytest.approx(2 * stats.t.sf(2.0, 28))
        assert "ignored" in r["df_note"]

    def test_the_registry_path_carries_the_bounds(self):
        from metascience_agent.registry import SPECS
        spec = next(s for s in SPECS if s.name == "recalc_stat_to_p")
        r = spec.call({"statistic": 2.0, "kind": "t", "reported_p": 0.04,
                       "decimals_stat": 2, "decimals_p": 2, "df_max": 10})
        assert r["severity"] == CEILING
        assert r["df_range"] == [1.0, 10.0]
