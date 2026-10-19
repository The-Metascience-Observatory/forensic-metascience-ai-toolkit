"""Pins for the complex-survey guard (`survey_design.py`).

MEASURED 2026-08-22 on `10.1186--s12889-025-24026-y` (NHANES) at v1.9.0: six of
the twenty severity-bearing tool-expert findings in a ten-paper grok run were
one error -- p-values and confidence intervals from a design-based analysis
recomputed as though they came from a simple random sample. Two were severity 3.
The paper's Methods named the design AND the software.

Every case below uses the REAL printed numbers from that paper. LESSONS #4: a
guard that cannot fire reads as though it had passed, so each direction has a
known positive and each family has a case that must still be checked.
"""

from __future__ import annotations

import math

import pytest
from scipy import stats

from metascience_agent.registry import BY_NAME
from metascience_agent.survey_design import (COMPLEX_SURVEY, REFUSED_UNDER_SURVEY,
                                             SIMPLE_RANDOM, canonical_sampling,
                                             declares_complex_survey,
                                             survey_refusal)
from metascience_agent.tools.estimates import check_estimate_ci

#: label, OR, ci_low, ci_high, printed p -- read off the paper.
S12889_ROWS = [
    ("Table 2 Model 1", 2.10, 1.40, 3.15, 0.003),
    ("Table 2 Model 2", 2.30, 1.60, 3.30, 0.001),
    ("Table 2 Model 3", 2.50, 1.80, 3.48, 0.001),
    ("Table 5 matched", 1.95, 1.25, 3.04, 0.008),
    ("Abstract PSM", 1.89, 1.18, 3.01, 0.009),
    ("Excluding dual users", 1.98, 1.28, 3.06, 0.003),
]


class TestTheDetectorReadsTheMethods:
    def test_the_real_declaration_fires_with_its_own_quote(self):
        got = declares_complex_survey(
            "BMI was calculated per NHANES protocols. NHANES sampling weights "
            "(WTMEC2YR) were applied to account for complex survey design and "
            "ensure national representativeness. Analyses were performed using "
            "R v4.3.1 with the survey package to incorporate sampling weights.")
        assert got is not None
        assert "complex survey design" in got["quote"], (
            "the paper's OWN sentence is quoted, so the claim is auditable")

    def test_the_mmwr_phrasing_fires_too(self):
        got = declares_complex_survey(
            "Weighted response frequencies were calculated using SAS statistical "
            "software (version 9.4).")
        assert got is not None
        assert "Weighted response frequenc" in got["marker"]

    @pytest.mark.parametrize("software", [
        "Analyses used svyglm in R.",
        "We used PROC SURVEYLOGISTIC.",
        "Estimates used Taylor series linearization.",
        "Variances used balanced repeated replication.",
        "Sampling weights were applied.",
        "Strata and primary sampling units were accounted for.",
    ])
    def test_each_software_and_estimator_marker_fires(self, software):
        assert declares_complex_survey(software) is not None

    @pytest.mark.parametrize("innocent", [
        "Participants were weighed; mean weight was 72.4 kg.",
        "The sample was stratified by age and sex for the subgroup analysis.",
        "We administered a survey to 502 respondents.",
        "Body weight and height were measured by trained staff.",
        "A weighted kappa was used for inter-rater agreement.",
        "",
        None,
    ])
    def test_ordinary_prose_does_not_fire(self, innocent):
        """The measured false-fire rate is 0 of 16 non-survey papers.

        `weight`, `stratified` and `survey` alone are deliberately absent from
        the marker list; each is ordinary in this corpus.
        """
        assert declares_complex_survey(innocent) is None


class TestCanonicalSampling:
    @pytest.mark.parametrize("raw", ["complex_survey", "complex survey",
                                     "COMPLEX_SURVEY", " weighted ", "survey"])
    def test_the_survey_spellings_normalise(self, raw):
        assert canonical_sampling(raw) == COMPLEX_SURVEY

    @pytest.mark.parametrize("raw", [None, "", "simple_random", "srs"])
    def test_the_default_spellings_normalise(self, raw):
        assert canonical_sampling(raw) == SIMPLE_RANDOM

    def test_an_unrecognised_string_falls_back_to_simple_random(self):
        """The OPPOSITE of `canonical_data_type`, on purpose.

        There, an unknown value must not buy a check, so it degrades toward
        refusal. Here refusal is what a typo would buy, and a guard that
        switched itself on for a misspelling would delete real findings on
        ordinary papers.
        """
        assert canonical_sampling("complex-servey") == SIMPLE_RANDOM
        assert canonical_sampling("weighted?") == SIMPLE_RANDOM
        assert canonical_sampling("design_based") == SIMPLE_RANDOM, (
            "trimmed from _ALIASES; the fallback direction is guard-OFF")


class TestTierOneIsOneSidedNotSuppressed:
    """`check_estimate_ci`: the interval and the p come from ONE fit, so the
    survey degrees of freedom are the only free parameter, and p is monotone
    DECREASING in df. The normal-approximation recovery is therefore the
    infimum of p, and only the direction below it survives."""

    def test_p_is_monotone_decreasing_in_df(self):
        """The claim the whole tier rests on, asserted rather than assumed."""
        b = math.log(2.10)
        hw = (math.log(3.15) - math.log(1.40)) / 2
        ps = []
        for df in (2, 4, 8, 20, 100, 1000):
            se = hw / stats.t.isf(0.025, df)
            ps.append(2 * stats.t.sf(b / se, df))
        assert ps == sorted(ps, reverse=True), ps
        z_p = 2 * stats.norm.sf(b / (hw / 1.959964))
        assert min(ps) > z_p, "the z answer is the floor"

    @pytest.mark.parametrize("label,est,lo,hi,p", S12889_ROWS)
    def test_the_six_real_rows_stop_being_findings(self, label, est, lo, hi, p):
        r = check_estimate_ci(est, lo, hi, measure="odds_ratio", reported_p=p,
                              decimals=2, sampling="complex_survey")
        assert r["severity"] == "consistent", label
        assert not r["problems"], label

    def test_the_ninety_percent_ci_claim_is_withdrawn(self):
        """The Models 1-2 finding was a NOTE, not a problem: the tool inferred a
        90% level. Under a survey design the same interval is a 95% t interval
        on ~8 df, so the inference is withdrawn."""
        srs = check_estimate_ci(2.10, 1.40, 3.15, measure="odds_ratio",
                                reported_p=0.003, decimals=2)
        assert srs["inferred_confidence_level"] == 0.9
        svy = check_estimate_ci(2.10, 1.40, 3.15, measure="odds_ratio",
                                reported_p=0.003, decimals=2,
                                sampling="complex_survey")
        assert svy["inferred_confidence_level"] is None
        assert any("COMPLEX SURVEY" in n for n in svy["notes"])

    def test_a_p_BELOW_the_recovery_still_fires(self):
        """THE KNOWN POSITIVE. No degrees of freedom reach a p under the
        normal-approximation floor, so that direction is untouched."""
        r = check_estimate_ci(1.95, 1.25, 3.04, measure="odds_ratio",
                              reported_p=1e-6, decimals=2,
                              sampling="complex_survey")
        assert r["severity"] == "suspicious"
        assert r["problems"]

    def test_ordering_and_containment_are_never_waived(self):
        """Algebra on the printed numbers; no design touches it."""
        r = check_estimate_ci(5.00, 1.25, 3.04, measure="odds_ratio",
                              reported_p=0.5, decimals=2,
                              sampling="complex_survey")
        assert r["severity"] == "suspicious"

    @pytest.mark.parametrize("label,est,lo,hi,p", S12889_ROWS)
    def test_the_default_reproduces_todays_answer(self, label, est, lo, hi, p):
        """No existing caller moves: absent and explicit `simple_random` agree."""
        a = check_estimate_ci(est, lo, hi, measure="odds_ratio", reported_p=p,
                              decimals=2)
        b = check_estimate_ci(est, lo, hi, measure="odds_ratio", reported_p=p,
                              decimals=2, sampling="simple_random")
        assert a == b, label


class TestTierTwoRefuses:
    """Recompute-from-printed-means: the direction argument does NOT transfer,
    so these refuse in both directions."""

    CASES = {
        # Table 1 BMI: 28.9+-6.5 (n=684) vs 27.1+-5.8 (n=188), printed P=0.004.
        "rivets_independent_t": {
            "mean1": 28.9, "sd1": 6.5, "n1": 684,
            "mean2": 27.1, "sd2": 5.8, "n2": 188, "reported_p": 0.004},
        "recalc_independent_t": {
            "mean1": 28.9, "sd1": 6.5, "n1": 684,
            "mean2": 27.1, "sd2": 5.8, "n2": 188, "reported_p": 0.004},
        # Table 1 race, back-derived counts, printed P=0.003.
        "recalc_chi_squared": {
            "observed": [[83, 43, 312, 138, 108], [16, 9, 106, 30, 27]],
            "reported_p": 0.003},
    }

    @pytest.mark.parametrize("tool", sorted(CASES))
    def test_the_real_inputs_are_refused(self, tool):
        r = BY_NAME[tool].call(dict(self.CASES[tool], sampling="complex_survey"))
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False
        assert "COMPLEX SURVEY" in r["error"]

    @pytest.mark.parametrize("tool", sorted(CASES))
    def test_the_same_inputs_still_run_by_default(self, tool):
        """THE KNOWN POSITIVE for the family: the guard is off unless asked."""
        r = BY_NAME[tool].call(dict(self.CASES[tool]))
        assert r.get("applicable") is not False
        assert r["severity"] != "indeterminate" or "error" not in r

    def test_the_race_row_shows_why_direction_cannot_rescue_this_family(self):
        """Printed p=0.003 against an unweighted chi-square of 0.117 is the
        'anomalous' direction -- p BELOW the recomputation -- and is STILL a
        false positive, because NHANES oversamples minorities and weighting
        moves the racial composition itself. Hence: refuse, not narrow."""
        srs = BY_NAME["recalc_chi_squared"].call(dict(self.CASES["recalc_chi_squared"]))
        assert srs["calculated_p"] > 0.05 > 0.003, (
            "the unweighted recomputation really is on the other side of alpha")
        svy = BY_NAME["recalc_chi_squared"].call(
            dict(self.CASES["recalc_chi_squared"], sampling="complex_survey"))
        assert svy["severity"] == "indeterminate"

    def test_every_refused_tool_is_reachable_and_guarded(self):
        """The set and the wiring cannot drift apart silently."""
        for name in REFUSED_UNDER_SURVEY:
            spec = BY_NAME[name]
            assert "sampling" in {p.name for p in spec.params}, name
            assert "sampling" in spec.guards(), name
            assert survey_refusal(name, "complex_survey") is not None, name

    def test_counting_checks_are_deliberately_untouched(self):
        """Integer arithmetic on printed counts is valid under any design."""
        for name in ("check_count_percent", "check_summation",
                     "check_flow_arithmetic", "grim_check"):
            assert name not in REFUSED_UNDER_SURVEY
            assert survey_refusal(name, "complex_survey") is None

    def test_check_estimate_ci_is_not_in_the_refused_set(self):
        """It guards itself, one-sidedly; refusing it outright would throw away
        the direction that still carries information."""
        assert "check_estimate_ci" not in REFUSED_UNDER_SURVEY
        assert survey_refusal("check_estimate_ci", "complex_survey") is None


class TestThePromptCarriesTheDeclaration:
    def test_the_note_quotes_the_paper_and_names_the_argument(self):
        from metascience_agent.parallel import _survey_design_note
        note = _survey_design_note(
            "NHANES sampling weights (WTMEC2YR) were applied to account for "
            "complex survey design.")
        assert "complex survey design" in note, "the paper's own words"
        assert 'sampling="complex_survey"' in note
        assert "LARGER" in note and "SMALLER" in note, "the one-sided rule"

    def test_an_ordinary_paper_gets_nothing_appended(self):
        from metascience_agent.parallel import _survey_design_note
        assert _survey_design_note("A randomised trial of 240 participants.") == ""
