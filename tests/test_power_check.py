"""Power-analysis verification: recompute what the paper says it did.

~70% of published G*Power calculations do not reproduce. This is deterministic
arithmetic validated against R's `pwr`, so it accuses nobody -- the paper
supplies its own inputs and either they follow or they don't.
"""
import math
import shutil
import subprocess

import pytest

from metascience_agent.tools.power_check import required_n, verify_power_analysis


def _r_available() -> bool:
    if not shutil.which("Rscript"):
        return False
    out = subprocess.run(["Rscript", "-e", 'cat(requireNamespace("pwr", quietly=TRUE))'],
                         capture_output=True, text=True)
    return "TRUE" in out.stdout


@pytest.mark.skipif(not _r_available(), reason="R/pwr not installed")
class TestAgainstRpwr:
    """Ground truth is the pwr package, not our own implementation."""

    @pytest.mark.parametrize("test_type,es,alpha,power,groups,rexpr", [
        ("two_sample_t", 0.5, 0.05, 0.80, 2, "pwr.t.test(d=0.5,sig.level=0.05,power=0.80,type='two.sample')$n"),
        ("two_sample_t", 0.8, 0.05, 0.90, 2, "pwr.t.test(d=0.8,sig.level=0.05,power=0.90,type='two.sample')$n"),
        ("two_sample_t", 0.2, 0.01, 0.80, 2, "pwr.t.test(d=0.2,sig.level=0.01,power=0.80,type='two.sample')$n"),
        ("one_sample_t", 0.5, 0.05, 0.80, 2, "pwr.t.test(d=0.5,sig.level=0.05,power=0.80,type='one.sample')$n"),
        ("paired_t", 0.4, 0.05, 0.80, 2, "pwr.t.test(d=0.4,sig.level=0.05,power=0.80,type='paired')$n"),
        ("correlation", 0.3, 0.05, 0.80, 2, "pwr.r.test(r=0.3,sig.level=0.05,power=0.80)$n"),
        ("correlation", 0.1, 0.05, 0.90, 2, "pwr.r.test(r=0.1,sig.level=0.05,power=0.90)$n"),
        ("anova_oneway", 0.25, 0.05, 0.80, 4, "pwr.anova.test(k=4,f=0.25,sig.level=0.05,power=0.80)$n"),
        ("anova_oneway", 0.40, 0.05, 0.80, 3, "pwr.anova.test(k=3,f=0.40,sig.level=0.05,power=0.80)$n"),
        ("two_proportions", 0.5, 0.05, 0.80, 2, "pwr.2p.test(h=0.5,sig.level=0.05,power=0.80)$n"),
    ])
    def test_matches_pwr(self, test_type, es, alpha, power, groups, rexpr):
        got = required_n(test_type, es, alpha, power, groups=groups)
        n_py = got["n_per_group"] or got["n_total"]
        out = subprocess.run(["Rscript", "-e", f"suppressMessages(library(pwr)); cat({rexpr})"],
                             capture_output=True, text=True, timeout=120).stdout.strip()
        n_r = math.ceil(float(out))
        assert abs(n_py - n_r) <= 1, f"python={n_py} pwr={n_r}"


class TestFalsePositiveGuards:
    """'Your sample size is wrong' is a serious claim. Four guards."""

    @pytest.mark.parametrize("missing", ["effect_size", "alpha", "target_power", "n_reported"])
    def test_underspecification_is_never_a_finding(self, missing):
        kwargs = dict(effect_size=0.5, alpha=0.05, target_power=0.80, n_reported=40)
        kwargs[missing] = None
        r = verify_power_analysis("two_sample_t", **kwargs)
        assert r["severity"] == "indeterminate"
        assert missing in r["missing_inputs"]
        assert r["reproducible"] is False

    def test_over_recruiting_is_correct_practice(self):
        """Inflating N for attrition is good design, not a discrepancy."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80, n_reported=400)
        assert r["severity"] == "consistent"
        assert r["verdict"] == "over_recruited"

    @pytest.mark.parametrize("n", [64, 63, 62])
    def test_software_convention_slack_absorbed(self, n):
        """G*Power / pwr / PASS disagree by a participant or two."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80,
                                  n_reported=n, n_reported_is_per_group=True)
        assert r["severity"] == "consistent"

    def test_genuine_shortfall_is_flagged(self):
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80, n_reported=30)
        assert r["severity"] == "suspicious"
        assert r["achieved_power_at_reported_n"] < 0.5
        assert r["reproducible"] is True

    def test_marginal_shortfall_is_only_indeterminate(self):
        """Small gaps are reported, not escalated."""
        r = verify_power_analysis("two_sample_t", 0.5, 0.05, 0.80, n_reported=120)
        assert r["severity"] == "indeterminate"

    def test_zero_effect_size_refuses(self):
        assert required_n("two_sample_t", 0.0)["severity"] == "indeterminate"

    def test_unsupported_test_refuses(self):
        assert required_n("mixed_model_3way", 0.5)["severity"] == "indeterminate"


class TestInternalConsistency:
    def test_required_n_actually_achieves_target_power(self):
        for es in (0.2, 0.5, 0.8):
            for power in (0.80, 0.90, 0.95):
                r = required_n("two_sample_t", es, 0.05, power)
                assert r["achieved_power"] >= power

    def test_requirement_is_monotone_in_effect_size(self):
        ns = [required_n("two_sample_t", es, 0.05, 0.80)["n_per_group"]
              for es in (0.2, 0.4, 0.6, 0.8)]
        assert ns == sorted(ns, reverse=True), "smaller effects must need larger n"

    def test_requirement_is_monotone_in_power(self):
        ns = [required_n("two_sample_t", 0.5, 0.05, p)["n_per_group"]
              for p in (0.70, 0.80, 0.90, 0.95)]
        assert ns == sorted(ns), "higher power must need larger n"


class TestTheOneTailedReadingExistsOnlyAtDf1Equals1:
    """GREG, 2026-08-16: "make sure F tests and other tests can accommodate the
    calculations for a 1-tailed version."

    THE SWEEP GOT THIS WRONG ON A REAL PAPER. Reviewing PNAS 0801268105 it
    flagged three p-values as "approximately half" what their F implies and
    reasoned that "the F distribution has no one-tailed form". For an OMNIBUS F
    that is true. For df1 = 1 it is false, and every one of that paper's three
    tests had df1 = 1.

    F(1, k) = t(k)^2 exactly, so the F upper-tail p IS the two-tailed t
    p-value and half of it is the one-tailed one. VERIFIED against the paper's
    own numbers: F(1,19) = 1.93 gives 0.18083 two-tailed and 0.09041
    one-tailed, against a REPORTED 0.09. An exact match on a directional
    hypothesis -- which turns the whole "doubling" pattern from a finding into
    the ordinary signature of planned comparisons.

    Reporting only the two-tailed value would have accused a paper of
    misreporting when it had merely tested directionally, which is the
    false-accusation direction this toolkit exists to avoid.
    """

    def test_a_one_df_F_gets_its_one_tailed_equivalent(self):
        from metascience_agent.tools.anova import recalc_f_to_p
        r = recalc_f_to_p(1.93, 1, 19, reported_p=0.09)
        ot = r["one_tailed_equivalent"]
        assert abs(r["calculated_p"] - 0.18083) < 1e-4
        assert abs(ot["p"] - 0.09041) < 1e-4
        assert abs(ot["t_equivalent"] - 1.3892) < 1e-3

    def test_it_matches_the_paper_that_exposed_it(self):
        """The exact case: a reported 0.09 that the two-tailed recompute calls
        0.181 and the one-tailed calls 0.090."""
        from metascience_agent.tools.anova import recalc_f_to_p
        assert abs(recalc_f_to_p(1.93, 1, 19)["one_tailed_equivalent"]["p"] - 0.09) < 0.001

    def test_an_omnibus_F_has_NO_one_tailed_reading(self):
        """The identity holds only at df1 = 1. Offering a halved p for an
        omnibus F would invent a test that does not exist."""
        from metascience_agent.tools.anova import recalc_f_to_p
        r = recalc_f_to_p(3.4, 3, 40, reported_p=0.03)
        assert r["one_tailed_equivalent"]["p"] is None
        assert "df1 = 3" in r["one_tailed_equivalent"]["why"]

    def test_the_two_tailed_value_stays_the_default(self):
        """Reported, never substituted: a paper that does not SAY it tested
        directionally has not earned the halving."""
        from metascience_agent.tools.anova import recalc_f_to_p
        r = recalc_f_to_p(4.65, 1, 13)
        assert abs(r["calculated_p"] - 0.05037) < 1e-4
        assert "STATES" in r["one_tailed_equivalent"]["caveat"]


class TestTheOneTailedReadingReachesTheSeverity:
    """Annotating the output was not enough, and this is the evidence.

    On PNAS 0801268105 this tool ALREADY carried the ceiling note "a one-tailed
    test ... would explain a disagreement". The sweep read it, reasoned past it,
    and asserted "F has only an upper tail, so no one-tailed convention licenses
    it here" -- false at df1 = 1 -- and the run's headline finding was a
    `suspicious` flag against three p-values that reconcile EXACTLY on a
    directional reading.

    A possibility the model has to remember is not a guard. So at df1 = 1, a
    reported p inside the HALVED achievable interval no longer draws an
    accusation from this tool. The unstated tail direction is still worth
    asking the authors about; it is a reporting observation, not a forensic
    signal, and the difference is the whole cardinal rule.
    """

    def test_the_real_case_is_flagged_with_the_reading_named(self):
        """1.93.0, statcheck's rule: the paper (checked 2026-10-18) never says
        it tested one-tailed, so the halved reading does not rescue it. The
        result names that reading, so the model cannot write that none exists."""
        from metascience_agent.tools.anova import recalc_f_to_p
        r = recalc_f_to_p(1.93, 1, 19, reported_p=0.09, decimals_f=2, decimals_p=2)
        assert r["p_matches"] is False
        assert r["one_tailed_reconciles"] is True
        assert r["severity"] == "suspicious"
        assert r["failure_mode"] == "reconciles_only_one_tailed_unstated"
        assert "ONE-tailed" in r["explanation"]

    def test_a_stated_one_tailed_test_no_longer_accuses(self):
        from metascience_agent.tools.anova import recalc_f_to_p
        r = recalc_f_to_p(1.93, 1, 19, reported_p=0.09, decimals_f=2, decimals_p=2,
                          one_tailed_stated=True)
        assert r["p_matches"] is False, "still disagrees with the two-tailed interval"
        assert r["one_tailed_reconciles"] is True
        assert r["severity"] == "indeterminate", (
            "NOT consistent. The tail direction is a free parameter the paper "
            "never states, so we cannot determine the p is right -- calling it "
            "consistent is a false all-clear, which the cardinal ordering ranks "
            "second-worst behind the false accusation we just removed."
        )
        assert "Downgraded from suspicious" in r["severity_note"]
        assert "NOT to consistent" in r["severity_note"]

    def test_it_does_not_forgive_a_p_too_small_even_for_one_tailed(self):
        """The escape hatch is arithmetic, not a blanket excuse. Halving 0.181
        gives 0.090; a reported 0.01 is not explained by directional testing."""
        from metascience_agent.tools.anova import recalc_f_to_p
        r = recalc_f_to_p(1.93, 1, 19, reported_p=0.01, decimals_f=2, decimals_p=2)
        assert r["one_tailed_reconciles"] is False
        assert r["severity"] == "suspicious"

    def test_the_hatch_stays_shut_for_an_omnibus_F(self):
        """df1 > 1 has no one-tailed reading, so the downgrade must not apply --
        otherwise the fix for one false accusation opens a false all-clear."""
        from metascience_agent.tools.anova import recalc_f_to_p
        r = recalc_f_to_p(1.9, 3, 40, reported_p=0.03, decimals_f=1, decimals_p=2)
        assert r["one_tailed_reconciles"] is False
        assert r["severity"] == "suspicious"
        assert "severity_note" not in r

    def test_an_honest_two_tailed_report_is_untouched(self):
        from metascience_agent.tools.anova import recalc_f_to_p
        r = recalc_f_to_p(1.93, 1, 19, reported_p=0.18, decimals_f=2, decimals_p=2)
        assert r["p_matches"] is True
        assert r["severity"] == "consistent"
        assert "severity_note" not in r


class TestRequiredNIsAProperCheck:
    """It was CLI-only for one day. The sweep on PNAS 0801268105 reached for it
    three times and was refused, on a paper whose degrees of freedom imply 68
    participants against a stated 34 -- exactly what it answers."""

    def test_with_actual_n_it_compares_designs(self):
        from metascience_agent.tools.power_check import required_n
        r = required_n("two_sample_t", 0.5, actual_n=34)
        ds = r["design_sensitivity"]
        assert ds["required_n_total"] > ds["actual_n_total"]
        assert ds["adequately_powered_for_this_effect"] is False

    def test_being_underpowered_is_never_an_accusation(self):
        """A small study is not an erroneous one. Escalating here would
        manufacture a finding out of every honest pilot."""
        from metascience_agent.tools.power_check import required_n
        assert required_n("two_sample_t", 0.5, actual_n=8)["severity"] == "consistent"
        assert required_n("two_sample_t", 0.5, actual_n=5000)["severity"] == "consistent"

    def test_without_actual_n_it_is_still_the_calculator(self):
        from metascience_agent.tools.power_check import required_n
        assert "design_sensitivity" not in required_n("two_sample_t", 0.5)

    def test_the_explanation_names_the_selection_problem_not_misconduct(self):
        from metascience_agent.tools.power_check import required_n
        e = required_n("two_sample_t", 0.5, actual_n=34)["explanation"]
        assert "selection inflates" in e and "CONTEXT, not an error" in e


class TestRecalcStatToPHasTheSameOneDfReading:
    """The false sentence originated HERE, not in the model.

    Reviewing PNAS 0801268105 the sweep wrote "F has only an upper tail, so no
    one-tailed convention licenses it here" and made it the run's headline. That
    is a near-verbatim paraphrase of what this tool told it in the same context:
    its `tails_note` said "a two-tailed reading of it is a category error", and
    its registry description said "`tails` is ignored for chi2 and F".

    Both are true above one numerator df and false at df = 1, where
    F(1,k) = t(k)^2 and chi2(1) = z^2 hold exactly. `34e05a5` fixed
    `recalc_f_to_p` and left this tool untouched, so the source of the error
    outlived the fix for it.
    """

    def test_the_one_df_note_no_longer_says_category_error(self):
        from metascience_agent.tools.stat_to_p import recalc_stat_to_p
        r = recalc_stat_to_p(statistic=1.93, kind="f", df=1, df2=19,
                             reported_p=0.09, decimals_stat=2, decimals_p=2, tails=2)
        assert "category error" not in (r.get("tails_note") or "")
        assert "t(k)^2" in r["tails_note"]

    def test_an_omnibus_F_still_gets_the_original_note(self):
        from metascience_agent.tools.stat_to_p import recalc_stat_to_p
        r = recalc_stat_to_p(statistic=1.9, kind="f", df=3, df2=40,
                             reported_p=0.03, decimals_stat=1, decimals_p=2, tails=2)
        assert "omnibus" in r["tails_note"]

    def test_the_real_case_is_flagged_unless_one_tailed_is_stated(self):
        from metascience_agent.tools.stat_to_p import recalc_stat_to_p
        kw = dict(statistic=1.93, kind="f", df=1, df2=19,
                  reported_p=0.09, decimals_stat=2, decimals_p=2)
        r = recalc_stat_to_p(**kw)
        assert r["one_tailed_reconciles"] is True
        assert r["severity"] == "suspicious"
        assert r["failure_mode"] == "reconciles_only_one_tailed_unstated"
        r = recalc_stat_to_p(**kw, one_tailed_stated=True)
        assert r["severity"] == "indeterminate"

    def test_a_one_df_chi_squared_gets_the_same_treatment(self):
        """chi2(1) = z^2 has exactly the structure of F(1,k) = t(k)^2. Fixing
        one and not the other would leave the same false accusation available."""
        from metascience_agent.tools.stat_to_p import recalc_stat_to_p
        r = recalc_stat_to_p(statistic=3.5, kind="chi2", df=1,
                             reported_p=0.031, decimals_stat=1, decimals_p=3,
                             one_tailed_stated=True)
        assert r["one_tailed_reconciles"] is True
        assert r["severity"] == "indeterminate"
        r = recalc_stat_to_p(statistic=3.5, kind="chi2", df=1,
                             reported_p=0.031, decimals_stat=1, decimals_p=3)
        assert r["severity"] == "suspicious"

    def test_a_p_too_small_even_for_one_tailed_is_still_flagged(self):
        from metascience_agent.tools.stat_to_p import recalc_stat_to_p
        r = recalc_stat_to_p(statistic=1.93, kind="f", df=1, df2=19,
                             reported_p=0.01, decimals_stat=2, decimals_p=2)
        assert r["one_tailed_reconciles"] is False
        assert r["severity"] == "suspicious"

    def test_an_omnibus_over_claim_is_still_flagged(self):
        """The escape hatch must not open above one df, or the fix for a false
        accusation becomes a false all-clear."""
        from metascience_agent.tools.stat_to_p import recalc_stat_to_p
        r = recalc_stat_to_p(statistic=1.9, kind="f", df=3, df2=40,
                             reported_p=0.03, decimals_stat=1, decimals_p=2)
        assert r["severity"] == "suspicious"
        assert "one_tailed_reconciles" not in r
