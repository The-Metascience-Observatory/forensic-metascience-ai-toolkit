"""What the paper claimed, against what its own numbers show.

The risk in this check is not that it misses spin. It is that it invents it.
Most of these tests are refusals, and each one names the false accusation it
prevents.
"""

from __future__ import annotations

import pytest

from forensic_metascience_ai_toolkit.anatomy import anatomy_from_findings
from forensic_metascience_ai_toolkit.tools.claims import (
    CEILING, check_claim_vs_result, claim_consistency_report)

CLAIM = "Training improved fluid intelligence."


def _c(**kw):
    base = dict(claim_quote=CLAIM, asserts="supported", p_value=0.21,
                alpha=0.05, hedged=False)
    base.update(kw)
    return check_claim_vs_result(**base)


class TestTheArithmeticCase:
    def test_an_unhedged_claim_above_alpha_is_suspicious(self):
        r = _c()
        assert r["severity"] == "suspicious"
        assert r["applicable"] is True
        assert "0.21" in r["finding"] and "0.05" in r["finding"]

    def test_it_quotes_both_sides_so_a_reader_adjudicates_the_sentence(self):
        r = _c(p_quote="t(58) = 1.27, p = .21")
        assert r["claim_quote"] == CLAIM
        assert r["p_quote"] == "t(58) = 1.27, p = .21"

    def test_a_claim_at_or_below_alpha_is_consistent(self):
        assert _c(p_value=0.01)["severity"] == "consistent"
        assert _c(p_value=0.05)["severity"] == "consistent"

    def test_it_offers_what_would_resolve_it(self):
        assert "correction" in _c()["what_would_resolve_it"]

    def test_it_never_asserts_impossibility(self):
        """A sentence can always have a reading we did not think of."""
        assert CEILING == "suspicious"
        assert _c()["severity"] != "impossible"


class TestItRefusesRatherThanInvents:
    """Each refusal is a false accusation that would otherwise be shipped."""

    def test_a_hedge_is_never_a_finding(self):
        """A hedge is the authors telling the reader not to over-read it."""
        r = _c(hedged=True)
        assert r["severity"] == "indeterminate"
        assert "hedged" in r["why_not_checked"]

    def test_an_unstated_alpha_is_refused_not_defaulted(self):
        """Assuming .05 accuses every paper that chose another threshold.
        The precedent is 76e9cc3, which deleted four precision defaults."""
        r = _c(alpha=None)
        assert r["severity"] == "indeterminate"
        assert "assuming .05" in r["why_not_checked"]

    def test_a_sentence_covering_several_tests_is_refused(self):
        """A hypothesis supported by three of four tests is legitimately
        described as supported."""
        r = _c(n_tests_claimed=4)
        assert r["severity"] == "indeterminate"
        assert "4 tests" in r["why_not_checked"]

    def test_a_threshold_p_is_refused(self):
        r = _c(p_is_threshold=True, p_value=0.05)
        assert r["severity"] == "indeterminate"
        assert "threshold" in r["why_not_checked"]

    def test_a_correction_changes_the_operative_threshold(self):
        r = _c(correction_applied="bonferroni")
        assert r["severity"] == "indeterminate"
        assert "bonferroni" in r["why_not_checked"]
        assert _c(correction_applied="none")["applicable"] is True

    @pytest.mark.parametrize("asserts", ["not_supported", "mixed", "none"])
    def test_only_a_positive_claim_can_contradict(self, asserts):
        assert _c(asserts=asserts)["severity"] == "indeterminate"

    def test_an_unquotable_claim_is_refused(self):
        assert _c(claim_quote="  ")["severity"] == "indeterminate"

    def test_a_missing_p_is_refused(self):
        assert _c(p_value=None)["severity"] == "indeterminate"

    @pytest.mark.parametrize("p, a", [(1.4, 0.05), (-0.1, 0.05), (0.2, 1.0), (0.2, 0.0)])
    def test_impossible_probabilities_are_refused(self, p, a):
        assert _c(p_value=p, alpha=a)["severity"] == "indeterminate"


def _anatomy(tests, interps):
    return anatomy_from_findings(
        {"paper_id": "p", "anatomy": {"tests": tests, "interpretations": interps}})


class TestTheSweepAccusesNobody:
    """An honest paper reports a null result and says so. It must come back
    clean, and it must be visible that the sweep RAN."""

    def test_an_honest_paper_yields_no_contradiction(self):
        a = _anatomy(
            [{"id": "t1", "test_type": "t_test", "p_value": 0.21},
             {"id": "t2", "test_type": "t_test", "p_value": 0.003}],
            [{"id": "i1", "claim": "We found no effect on fluid intelligence.",
              "asserts": "not_supported", "test_ids": ["t1"]},
             {"id": "i2", "claim": "Memory improved.", "asserts": "supported",
              "test_ids": ["t2"]},
             {"id": "i3", "claim": "Mood may have improved.",
              "asserts": "supported", "test_ids": ["t1"], "hedged": True}])
        r = claim_consistency_report(a, alpha=0.05)
        assert r["n_contradictions"] == 0
        assert r["n_interpretations"] == 3

    def test_it_catches_the_one_real_contradiction(self):
        a = _anatomy(
            [{"id": "t1", "test_type": "t_test", "p_value": 0.21}],
            [{"id": "i1", "claim": "Training improved fluid intelligence.",
              "asserts": "supported", "test_ids": ["t1"]}])
        r = claim_consistency_report(a, alpha=0.05)
        assert r["n_contradictions"] == 1
        assert r["worst"] == "suspicious"
        assert r["results"][0]["test_id"] == "t1"

    def test_a_test_we_never_extracted_is_our_gap_not_their_error(self):
        a = _anatomy(
            [], [{"id": "i1", "claim": CLAIM, "asserts": "supported",
                  "test_ids": ["t_missing"]}])
        r = claim_consistency_report(a, alpha=0.05)
        assert r["n_contradictions"] == 0
        assert r["n_refused"] == 1

    def test_no_stated_alpha_checks_nothing_and_says_why(self):
        a = _anatomy(
            [{"id": "t1", "test_type": "t_test", "p_value": 0.21}],
            [{"id": "i1", "claim": CLAIM, "asserts": "supported",
              "test_ids": ["t1"]}])
        r = claim_consistency_report(a, alpha=None)
        assert r["n_contradictions"] == 0
        assert r["n_checked"] == 0
        assert "alpha was not stated" in r["why"]

    def test_silence_is_distinguishable_from_never_having_run(self):
        r = claim_consistency_report(_anatomy([], []), alpha=0.05)
        assert r["n_interpretations"] == 0
        assert r["n_contradictions"] == 0
        assert r["check"] == "claim_vs_printed_p"

    def test_refusals_are_counted_by_reason(self):
        a = _anatomy(
            [{"id": "t1", "test_type": "t_test", "p_value": 0.21}],
            [{"id": f"i{i}", "claim": CLAIM, "asserts": "supported",
              "test_ids": ["t1"], "hedged": True} for i in range(3)])
        r = claim_consistency_report(a, alpha=0.05)
        assert r["n_refused"] == 3
        assert sum(r["refusals"].values()) == 3


class TestDescriptiveFieldsGenerateNoFinding:
    """Causal wording on an observational design is a real criticism and a
    terrible automated accusation. It is recorded, never checked."""

    def test_causal_language_does_not_create_a_contradiction(self):
        a = _anatomy(
            [{"id": "t1", "test_type": "t_test", "p_value": 0.01}],
            [{"id": "i1", "claim": "Coalitions increase EBP uptake.",
              "asserts": "supported", "test_ids": ["t1"],
              "causal_language": True}])
        r = claim_consistency_report(a, alpha=0.05)
        assert r["n_contradictions"] == 0
        assert a.interpretations[0].causal_language is True

    def test_generalization_is_carried_but_unjudged(self):
        a = _anatomy([], [{"id": "i1", "claim": CLAIM, "asserts": "none",
                           "generalization": "all US adolescents"}])
        assert a.interpretations[0].generalization == "all US adolescents"
        assert claim_consistency_report(a, alpha=0.05)["n_contradictions"] == 0


class TestARefusalReasonIsAboutTheRightParty:
    """"No p-value was printed" is a criticism OF THE PAPER. "The sentence
    covers six tests" is a fact about OUR check. Reporting the second as the
    first is the house failure mode -- our own gap rendered as their omission.

    MEASURED on ajcp.70049, whose abstract names six tests in one sentence:
    the sweep blamed the paper for a p-value it prints in Table 2."""

    def test_a_multi_test_sentence_blames_the_sentence_not_the_paper(self):
        r = check_claim_vs_result(
            claim_quote=CLAIM, asserts="supported", p_value=None, alpha=0.05,
            hedged=False, n_tests_claimed=6)
        assert "covers 6 tests" in r["why_not_checked"]
        assert "no p-value" not in r["why_not_checked"]

    def test_a_genuine_missing_p_still_says_so(self):
        r = check_claim_vs_result(
            claim_quote=CLAIM, asserts="supported", p_value=None, alpha=0.05,
            hedged=False, n_tests_claimed=1)
        assert "no p-value was printed" in r["why_not_checked"]


class TestOnARealHonestPaper:
    """ajcp.70049 reports its null explicitly -- "but not with evidence-based
    practice fidelity" -- with three fidelity tests at p = .38, .96 and .89.
    A paper that reports its own null must never be accused."""

    def test_it_accuses_nobody(self):
        a = anatomy_from_findings({"paper_id": "ajcp", "anatomy": {
            "tests": [
                {"id": "t2_comm", "test_type": "other", "p_value": 0.01},
                {"id": "t3_comm", "test_type": "other", "p_value": 0.03},
                {"id": "t4_comm", "test_type": "mixed_model", "p_value": 0.38},
                {"id": "t4_idm", "test_type": "mixed_model", "p_value": 0.96},
                {"id": "t4_icr", "test_type": "mixed_model", "p_value": 0.89}],
            "interpretations": [
                {"id": "i1", "location": "abstract", "asserts": "supported",
                 "claim": ("Inclusive leadership was positively associated with "
                           "the number of evidence-based practices used and how "
                           "many parents and youth those programs reached"),
                 "test_ids": ["t2_comm", "t3_comm"]},
                {"id": "i2", "location": "abstract", "asserts": "not_supported",
                 "claim": "but not with evidence-based practice fidelity",
                 "test_ids": ["t4_comm", "t4_idm", "t4_icr"]},
                {"id": "i3", "location": "conclusion", "asserts": "supported",
                 "hedged": True, "test_ids": [],
                 "claim": ("Findings indicate that inclusive coalition leadership "
                           "warrants the time and skills entailed.")}]}})
        r = claim_consistency_report(a, alpha=0.05)
        assert r["n_contradictions"] == 0, r["results"]
        assert r["n_interpretations"] == 3


class TestTheSweepIsActuallyWired:
    """A capability that exists and is never invoked is this codebase's most
    frequently rediscovered defect. These tests assert the sweep RUNS, not
    merely that it could."""

    DOC = {"paper_id": "p", "anatomy": {
        "studies": [{"id": "s1", "label": "study", "alpha": 0.05}],
        "tests": [{"id": "t1", "test_type": "t_test", "p_value": 0.21},
                  {"id": "t2", "test_type": "t_test", "p_value": 0.01}],
        "interpretations": [
            {"id": "i1", "claim": "Training improved fluid intelligence.",
             "asserts": "supported", "test_ids": ["t1"], "location": "abstract"},
            {"id": "i2", "claim": "Memory improved.", "asserts": "supported",
             "test_ids": ["t2"]}]}}

    def test_alpha_is_read_off_the_study(self):
        a = anatomy_from_findings(self.DOC)
        assert a.studies[0].alpha == 0.05

    def test_the_prepass_sweep_uses_the_papers_own_alpha(self):
        from forensic_metascience_ai_toolkit import prepass
        r = prepass._sweep_claims(self.DOC)
        assert r["alpha"] == 0.05
        assert r["n_checked"] == 2
        assert r["n_contradictions"] == 1

    def test_an_undeclared_alpha_checks_nothing_and_records_why(self):
        """Assuming .05 would accuse every paper that committed to another
        threshold. Refusing loudly keeps 'we looked and found nothing'
        distinguishable from 'we never looked'."""
        from forensic_metascience_ai_toolkit import prepass
        doc = {**self.DOC, "anatomy": {**self.DOC["anatomy"],
                                       "studies": [{"id": "s1", "label": "s"}]}}
        r = prepass._sweep_claims(doc)
        assert r["alpha"] is None
        assert r["n_checked"] == 0 and r["n_contradictions"] == 0
        assert "alpha was not stated" in r["why"]

    def test_a_table_less_paper_still_gets_the_claim_sweep(self, tmp_path):
        """The sweep reads the anatomy, not the tables, so gating it on the
        tables check would silently disable it for prose- and figure-only
        papers -- whose claims are hardest to check by other means."""
        from forensic_metascience_ai_toolkit import prepass
        r = prepass.run_exhaustive(tmp_path, self.DOC)
        assert r is not None, "the claim sweep was hidden by the tables gate"
        assert r["n_tables"] == 0
        assert r["n_accusatory"] == 1
        assert r["claims"]["n_contradictions"] == 1

    def test_a_table_less_paper_with_no_claims_is_still_silent(self):
        """Silence about tables remains the right answer when there is nothing
        else to report -- a '0 of 0' line reads as a failed review."""
        from forensic_metascience_ai_toolkit import prepass
        import tempfile, pathlib
        r = prepass.run_exhaustive(pathlib.Path(tempfile.mkdtemp()),
                                   {"paper_id": "p", "anatomy": {"studies": []}})
        assert r is None

    def test_a_sweep_that_crashed_says_so_rather_than_reporting_zero(self):
        from forensic_metascience_ai_toolkit import prepass
        r = prepass._sweep_claims({"paper_id": "p", "anatomy": {
            "interpretations": [{"id": "i1", "claim": "x", "asserts": "supported"}],
            "tests": "not a list"}})
        assert r is None or "error" in r or r["n_contradictions"] == 0
