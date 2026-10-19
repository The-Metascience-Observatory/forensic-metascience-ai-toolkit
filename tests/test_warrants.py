"""The warrant field: whose standard a finding invokes, and what that licenses.

Each test names the failure it exists to stop. The failure this whole module
guards against is the cardinal one -- criticising a paper for not doing
something its design never required -- which the archive has never committed but
which nothing in the system prevented.
"""
import json
from pathlib import Path

import pytest

from metascience_agent import warrants as W

SCHEMA = (Path(__file__).resolve().parents[1]
          / "src/metascience_agent/schema/report.schema.json")


def _finding_base(**kw):
    f = {"rank": 1, "title": "t", "severity": "suspicious", "confidence": "high",
         "location": "Table 1", "reported": "r", "computed": "c",
         "assumptions": "a", "warrant": "logical", "reproduction": "metascience x",
         "stage1_finding_ids": [], "plain": "p"}
    f.update(kw)
    return f


def _result(*findings):
    return {"report": {"findings": list(findings)}}


class TestTheVocabularyIsClosedAndMatchesTheSchema:
    def test_every_warrant_has_a_meaning_and_a_chip(self):
        """The viewer renders both. A warrant with no lay gloss reaches the
        reader as a bare enum word, which is the failure mode the `plain` field
        exists to prevent everywhere else."""
        for w in W.WARRANTS:
            assert W.WARRANT_MEANING.get(w), w
            assert W.WARRANT_CHIP.get(w), w


class TestResolutionFailsSafe:
    def test_a_stated_warrant_is_returned_as_stated(self):
        r = W.warrant_of({"warrant": "paper_commitment"})
        assert (r["warrant"], r["stated"]) == ("paper_commitment", True)

    @pytest.mark.parametrize("bad", [None, "", "design_validity", "LOGICAL ", 7, []])
    def test_absent_or_unknown_degrades_to_the_supplied_class(self, bad):
        """The unknown case must degrade toward the WEAKER reading. A missing
        field that defaulted to `logical` would buy an unearned uncapped
        severity for every finding that simply forgot to say."""
        r = W.warrant_of({} if bad is None else {"warrant": bad})
        if bad == "LOGICAL ":            # whitespace/case are tolerated
            assert r["warrant"] == "logical" and r["stated"] is True
        else:
            assert r["warrant"] == W.SUPPLIED_WARRANT
            assert r["stated"] is False

    def test_a_non_dict_does_not_raise(self):
        assert W.warrant_of("nonsense")["warrant"] == W.SUPPLIED_WARRANT


class TestTheCap:
    @pytest.mark.parametrize("sev", ["impossible", "highly_suspicious"])
    def test_a_supplied_norm_cannot_reach_the_top_two_rungs(self, sev):
        res = _result(_finding(warrant="field_norm", severity=sev))
        s = W.clamp_supplied_norms(res)
        f = res["report"]["findings"][0]
        assert f["severity"] == W.SUPPLIED_CEILING
        assert s["n_clamped"] == 1

    def test_the_clamp_is_visible_and_names_the_original(self):
        """A severity quietly lowered hides both the correction and a model
        that is systematically over-calling."""
        res = _result(_finding(warrant="field_norm", severity="impossible"))
        W.clamp_supplied_norms(res)
        blk = res["report"]["findings"][0]["severity_source"]
        assert blk["model"] == "impossible"
        assert blk["final"] == W.SUPPLIED_CEILING
        assert blk["direction"] == "clamped"
        assert "reviewer supplied" in blk["reason"]

    def test_an_inferred_warrant_says_it_was_inferred(self):
        """"You named a norm we supplied" and "you named nothing, so we treated
        it as ours" are different statements and only one is the model's."""
        res = _result(_finding(severity="impossible"))
        del res["report"]["findings"][0]["warrant"]
        W.clamp_supplied_norms(res)
        blk = res["report"]["findings"][0]["severity_source"]
        assert "names no warrant" in blk["reason"]

    @pytest.mark.parametrize("w", ["paper_commitment", "named_guideline", "logical"])
    def test_the_other_three_warrants_are_untouched_at_impossible(self, w):
        """The cap must not become a general severity ceiling. Holding a paper
        to its own promise, or to arithmetic, licenses the full ladder."""
        res = _result(_finding(warrant=w, severity="impossible"))
        W.clamp_supplied_norms(res)
        assert res["report"]["findings"][0]["severity"] == "impossible"
        assert "severity_source" not in res["report"]["findings"][0]

    @pytest.mark.parametrize("sev", ["suspicious", "indeterminate", "consistent"])
    def test_nothing_at_or_below_the_ceiling_is_rewritten(self, sev):
        res = _result(_finding(warrant="field_norm", severity=sev))
        W.clamp_supplied_norms(res)
        assert res["report"]["findings"][0]["severity"] == sev

    def test_the_clamp_reaches_a_fixed_point(self):
        res = _result(_finding(warrant="field_norm", severity="impossible"))
        W.clamp_supplied_norms(res)
        assert W.clamp_supplied_norms(res)["n_clamped"] == 0


class TestItIsNotRedundantWithTheEvidenceClamp:
    def test_it_catches_a_tool_computed_finding_the_other_clamp_cannot(self):
        """THE REASON THIS MODULE EXISTS AS A SEPARATE CHECK.
        `clamp_uncomputed` keys on evidence grade, so a finding a tool computed
        is exempt from it. `multiplicity_report` will happily compute how many
        claims fail a correction the paper never undertook -- sound arithmetic
        about an obligation that is ours. Only the warrant sees that."""
        from metascience_agent import severity_reconcile as SR
        f = _finding(warrant="field_norm", severity="impossible",
                     stage1_finding_ids=["s1"])
        res = {"report": {"findings": [f]},
               "findings": {"findings": [{"id": "s1", "technique": "multiplicity_report",
                                          "severity": "impossible"}]}}
        SR.clamp_uncomputed(res)
        assert f["severity"] == "impossible", "evidence clamp should exempt this"
        W.clamp_supplied_norms(res)
        assert f["severity"] == W.SUPPLIED_CEILING


class TestTheSummaryIsAlwaysRecorded:
    def test_run_meta_carries_the_block_even_when_nothing_fired(self):
        """A key that appears only when something fired is indistinguishable
        from a module that never ran -- the house failure pattern."""
        res = _result(_finding(warrant="logical"))
        W.clamp_supplied_norms(res)
        assert "supplied_norm_clamp" in res["run_meta"]

    def test_it_counts_every_warrant_so_drift_is_visible(self):
        res = _result(_finding(warrant="logical"),
                      _finding(warrant="logical"),
                      _finding(warrant="field_norm"))
        s = W.clamp_supplied_norms(res)
        assert s["by_warrant"] == {"logical": 2, "field_norm": 1}
        assert s["n_supplied"] == 1 and s["n_inferred"] == 0

    def test_a_missing_findings_list_returns_an_empty_summary(self):
        assert W.clamp_supplied_norms({})["n_findings"] == 0


def _finding(**kw):
    return _finding_base(**kw)


class TestTheClampsReadTheSHAPEPRODUCTIONPRODUCES:
    """CAUGHT BY THE ROMANO RUN, 2026-08-11, and the most instructive bug of the
    day. Both clamps read `result["report"]`. Production stages the report under
    `report_obj` -- every other annotator uses that key. So both returned at
    their first line on every real run, and `run_meta.json` for the Romano run
    contains no `uncomputed_severity_clamp` and no `supplied_norm_clamp` at all,
    while `severity_reconciliation` sits right beside them because `annotate`
    reads `result["findings"]`.

    `clamp_uncomputed` shipped in e1fa555 as "the enforced severity cap" and
    enforced nothing. Its tests passed the whole time, because they hand-build
    `{"report": ...}` -- a shape production never produces. Tested against the
    wrong shape is indistinguishable from never being called, and neither the
    suite nor `lint-inert` could see it. Only running a paper could.
    """

    def _staged(self, findings):
        return {"report_obj": {"findings": findings},
                "findings": {"findings": []}}

    def test_the_supplied_norm_clamp_fires_on_the_production_shape(self):
        from metascience_agent import warrants as W
        staged = self._staged([_finding(warrant="field_norm",
                                        severity="impossible")])
        s = W.clamp_supplied_norms(staged)
        assert s["n_findings"] == 1, "read `report_obj`, not `report`"
        assert s["n_clamped"] == 1
        assert staged["report_obj"]["findings"][0]["severity"] == "suspicious"

    def test_the_uncomputed_clamp_fires_on_the_production_shape(self):
        from metascience_agent import severity_reconcile as SR
        staged = self._staged([_finding(severity="impossible",
                                        stage1_finding_ids=[])])
        s = SR.clamp_uncomputed(staged)
        assert s["n_findings"] == 1, "read `report_obj`, not `report`"

    def test_both_still_read_the_legacy_key(self):
        """Hand-built fixtures and the archive replay in
        tests/test_corpus_invariants.py pass `{"report": ...}`. The fallback
        keeps them working; it is not the production path."""
        from metascience_agent import severity_reconcile as SR
        from metascience_agent import warrants as W
        legacy = {"report": {"findings": [_finding(warrant="field_norm")]}}
        assert W.clamp_supplied_norms(legacy)["n_findings"] == 1
        assert SR.clamp_uncomputed({"report": {"findings": [_finding()]}})["n_findings"] == 1

    def test_the_summary_reaches_run_meta_on_the_production_shape(self):
        """The symptom that exposed it: an absent key in run_meta.json. A
        module that ran and a module that returned early are indistinguishable
        unless the summary is written unconditionally AND the writer is reached."""
        from metascience_agent import warrants as W
        staged = self._staged([_finding(warrant="logical")])
        W.clamp_supplied_norms(staged)
        assert "supplied_norm_clamp" in staged["run_meta"]
        assert staged["run_meta"]["supplied_norm_clamp"]["n_findings"] == 1


