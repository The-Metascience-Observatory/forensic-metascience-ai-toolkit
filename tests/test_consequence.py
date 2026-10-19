"""Consequence: what a finding CHANGES, as distinct from how wrong it is.

The information these tests pin was already being computed and thrown away
twice -- statcheck's `decision_error` and multiplicity's
`n_claims_lost_to_correction` -- so the failure mode this guards against is not
"the arithmetic is wrong" but "the arithmetic never reaches the report".
"""
import hashlib
import json
import re
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import consequence as C
from forensic_metascience_ai_toolkit.bundle import render_viewer
from forensic_metascience_ai_toolkit.report_render import SEVERITY_RANK, markdown_to_html, sort_findings


def _ledger(*results):
    """A minimal tool-call ledger: one validated call per JSON result."""
    return [{"validated": True, "result": json.dumps(r)} for r in results]


class TestFromToolOutput:
    def test_statcheck_decision_error_becomes_a_significance_flip(self):
        out = {"decision_error": True, "reported_p": 0.034}
        b = C.from_tool_output(out, C.corroboration_from_ledger(_ledger(out)))
        assert b["flips_significance"] is True
        assert b["basis"] == "computed"

    def test_the_per_statistic_flag_is_read_where_statcheck_actually_puts_it(self):
        """Both statcheck wrappers nest `decision_error` inside
        `result["statistics"][i]` and expose only the TOTAL at the top level. A
        flat lookup found 0 of the 17 statcheck findings in the committed
        corpus."""
        out = {"statistics": [{"decision_error": False}, {"decision_error": True}]}
        b = C.from_tool_output(out, C.corroboration_from_ledger(_ledger(out)))
        assert b["flips_significance"] is True
        assert b["basis"] == "computed"

    def test_statcheck_no_decision_error_is_a_finding_not_a_gap(self):
        """"checked, and nothing changes" is information. It must not be
        recorded as "unknown", which would let it sort above a real flip."""
        assert C.from_tool_output({"decision_error": False})["flips_significance"] is False

    def test_a_decision_error_total_is_not_a_claim_count(self):
        """`decision_errors` counts STATISTICS. Several can back one claim, one
        claim can rest on none of them, and the total is a whole-paper roll-up
        that lands on whichever finding embedded the statcheck summary."""
        b = C.from_tool_output({"decision_errors": 2, "errors": 5})
        assert b["flips_significance"] is True
        assert b["claims_affected"] is None
        assert "2 statistic(s)" in b["explanation"]

    def test_zero_decision_errors_is_false_not_missing(self):
        assert C.from_tool_output({"decision_errors": 0})["flips_significance"] is False

    def test_multiplicity_claims_lost(self):
        out = {"n_claims_lost_to_correction": 3, "n_significant_uncorrected": 5}
        b = C.from_tool_output(out, C.corroboration_from_ledger(_ledger(out)))
        assert b["claims_affected"] == 3
        assert b["basis"] == "computed"

    def test_multiplicity_is_not_a_significance_flip(self):
        """`flips_significance` means crossing THE ALPHA THE PAPER USED. A
        result lost to Benjamini-Hochberg does not: it fails a correction the
        paper did not apply, over a family `multiplicity_report` explicitly
        declines to assert is the right one. Calling it a flip would import a
        judgement into the basis reserved for what a tool established."""
        b = C.from_tool_output({"n_claims_lost_to_correction": 3})
        assert b["flips_significance"] is None
        assert "the paper did not apply" in b["explanation"]

    def test_multiplicity_losing_nothing_affects_nothing(self):
        b = C.from_tool_output({"n_claims_lost_to_correction": 0})
        assert b["claims_affected"] == 0
        assert b["flips_significance"] is None

    def test_internal_inconsistency_is_not_laundered_into_a_clean_bill(self):
        """`multiplicity_report` surfaces impossible arithmetic rather than
        clamping it away. Deriving a consequence from it would turn the tool's
        own red flag into "changes no significance decision"."""
        b = C.from_tool_output({"n_claims_lost_to_correction": -2,
                                "internal_inconsistency": True})
        assert b["flips_significance"] is None
        assert b["claims_affected"] is None
        assert "internally inconsistent" in b["explanation"]

    def test_output_with_no_consequence_information_yields_none(self):
        """None and "consequence of zero" are different claims. A GRIM result
        says nothing about what depends on it, and must not be recorded as
        saying nothing depends on it."""
        assert C.from_tool_output({"consistent": False, "severity": "impossible"}) is None
        assert C.from_tool_output(None) is None
        assert C.from_tool_output("not a dict") is None

    def test_booleans_are_not_read_as_counts(self):
        """`True` is an int in Python; counting it as one claim would be wrong."""
        b = C.from_tool_output({"n_claims_lost_to_correction": True})
        assert b is None or b["claims_affected"] is None

    def test_fractional_counts_are_refused_not_truncated(self):
        """int(0.9) is 0, which would read as "nothing lost"."""
        b = C.from_tool_output({"n_claims_lost_to_correction": 0.9})
        assert b is None or b["claims_affected"] is None


class TestCorroborationIsRequiredForComputed:
    """The first version read the consequence keys straight out of a finding's
    `computed` block -- a field the MODEL writes, declared
    `additionalProperties: true`. That guard closed the front door and left an
    unlocked side door on the same object."""

    FAKE = {"id": "fake", "technique": "manual", "severity": "suspicious",
            "computed": {"n_claims_lost_to_correction": 99, "decision_error": True}}

    def test_numbers_no_tool_produced_are_asserted_not_computed(self):
        result = {"findings": {"findings": [dict(self.FAKE)]}}
        C.annotate(result, ledger=[])          # a ledger containing no such call
        block = result["findings"]["findings"][0]["consequence"]
        assert block["basis"] == "asserted"
        assert "not corroborated" in block["explanation"]

    def test_it_fails_closed_with_no_ledger_at_all(self):
        """No ledger means cannot-corroborate, not nothing-to-corroborate."""
        result = {"findings": {"findings": [dict(self.FAKE)]}}
        C.annotate(result)
        assert result["findings"]["findings"][0]["consequence"]["basis"] == "asserted"

    def test_an_uncorroborated_claim_cannot_be_inherited_as_computed(self):
        result = {"findings": {"findings": [dict(self.FAKE)]},
                  "report_obj": {"findings": [
                      {"rank": 1, "stage1_finding_ids": ["fake"]}]}}
        C.annotate(result, ledger=[])
        # Nothing computed exists to inherit, so the report finding gets either
        # no block or an asserted one -- never a computed one.
        block = result["report_obj"]["findings"][0].get("consequence")
        assert block is None or block["basis"] == "asserted"

    def test_only_validated_calls_corroborate(self):
        """An unvalidated call is the model running its own code, which is
        exactly the provenance this exists to exclude."""
        led = [{"validated": False, "result": json.dumps({"decision_error": True})}]
        assert C.corroboration_from_ledger(led) == set()

    def test_no_ledger_is_distinguishable_from_an_empty_one(self):
        assert C.corroboration_from_ledger(None) is None
        assert C.corroboration_from_ledger([]) == set()

    def test_a_real_tool_result_does_corroborate(self):
        out = {"n_claims_lost_to_correction": 3}
        result = {"findings": {"findings": [
            {"id": "real", "computed": out, "technique": "multiplicity_report"}]}}
        C.annotate(result, ledger=_ledger(out))
        assert result["findings"]["findings"][0]["consequence"]["basis"] == "computed"

    def test_a_different_value_does_not_corroborate(self):
        """Inflating a corroborated number must not inherit its provenance."""
        result = {"findings": {"findings": [
            {"id": "f", "computed": {"n_claims_lost_to_correction": 99}}]}}
        C.annotate(result, ledger=_ledger({"n_claims_lost_to_correction": 3}))
        assert result["findings"]["findings"][0]["consequence"]["basis"] == "asserted"


class TestTheModelCannotLabelItsOwnJudgement:
    def test_a_model_supplied_block_is_always_asserted(self):
        b = C.normalise({"flips_significance": True, "claims_affected": 4,
                         "basis": "computed", "explanation": "trust me"})
        assert b["basis"] == "asserted"

    def test_a_corroborated_block_replaces_the_models_own(self):
        out = {"n_claims_lost_to_correction": 3}
        result = {"findings": {"findings": [{
            "id": "f1", "computed": out,
            "consequence": {"flips_significance": False, "basis": "computed"},
        }]}}
        C.annotate(result, ledger=_ledger(out))
        block = result["findings"]["findings"][0]["consequence"]
        assert block["basis"] == "computed"
        assert block["claims_affected"] == 3      # the tool's answer, not the model's

    def test_an_asserted_block_survives_where_no_tool_spoke(self):
        result = {"findings": {"findings": [{
            "id": "f1", "computed": {"consistent": False},
            "consequence": {"flips_significance": True, "basis": "computed"},
        }]}}
        C.annotate(result)
        block = result["findings"]["findings"][0]["consequence"]
        assert block["basis"] == "asserted"
        assert block["flips_significance"] is True

    def test_a_finding_with_nothing_to_say_carries_no_block(self):
        result = {"findings": {"findings": [{"id": "f1", "computed": {"consistent": True}}]}}
        C.annotate(result)
        assert "consequence" not in result["findings"]["findings"][0]


class TestInheritance:
    def test_a_report_finding_inherits_the_computed_consequence_it_rests_on(self):
        """Stage 2 rewrites the prose. It must not cost the finding a
        consequence a tool established in stage 1."""
        out = {"n_claims_lost_to_correction": 3}
        result = {
            "findings": {"findings": [{"id": "s1", "computed": out}]},
            "report_obj": {"findings": [
                {"rank": 1, "title": "Multiplicity", "stage1_finding_ids": ["s1"]}]},
        }
        C.annotate(result, ledger=_ledger(out))
        block = result["report_obj"]["findings"][0]["consequence"]
        assert block["basis"] == "computed"
        assert block["claims_affected"] == 3

    def test_the_strongest_cited_consequence_wins(self):
        weak, strong = {"decision_errors": 0}, {"decision_error": True}
        result = {
            "findings": {"findings": [
                {"id": "weak", "computed": weak},
                {"id": "strong", "computed": strong},
            ]},
            "report_obj": {"findings": [
                {"rank": 1, "stage1_finding_ids": ["weak", "strong"]}]},
        }
        C.annotate(result, ledger=_ledger(weak, strong))
        assert result["report_obj"]["findings"][0]["consequence"]["flips_significance"] is True

    def test_the_inherited_block_is_a_copy_not_an_alias(self):
        """The same dict on two findings means a later in-place edit to one
        silently changes the other."""
        out = {"n_claims_lost_to_correction": 3}
        result = {
            "findings": {"findings": [{"id": "s1", "computed": out}]},
            "report_obj": {"findings": [{"rank": 1, "stage1_finding_ids": ["s1"]}]},
        }
        C.annotate(result, ledger=_ledger(out))
        sweep = result["findings"]["findings"][0]["consequence"]
        report = result["report_obj"]["findings"][0]["consequence"]
        assert sweep == report and sweep is not report

    def test_the_models_own_explanation_is_kept(self):
        """The schema asks for "one sentence naming the specific claim
        affected"; the derived string names the arithmetic instead. Replacing
        one with the other discards the more useful half."""
        out = {"n_claims_lost_to_correction": 3}
        result = {
            "findings": {"findings": [{"id": "s1", "computed": out}]},
            "report_obj": {"findings": [{
                "rank": 1, "stage1_finding_ids": ["s1"],
                "consequence": {
                    "basis": "asserted",
                    "explanation": "The abstract's primary outcome no longer survives."}}]},
        }
        C.annotate(result, ledger=_ledger(out))
        text = result["report_obj"]["findings"][0]["consequence"]["explanation"]
        assert "abstract's primary outcome" in text
        assert "do not survive correction" in text

    def test_an_unbacked_report_finding_stays_asserted(self):
        result = {"findings": {"findings": []},
                  "report_obj": {"findings": [
                      {"rank": 1, "stage1_finding_ids": [],
                       "consequence": {"flips_significance": True, "basis": "computed"}}]}}
        C.annotate(result)
        assert result["report_obj"]["findings"][0]["consequence"]["basis"] == "asserted"

    def test_the_summary_separates_sweep_from_report_findings(self):
        """Summing them double-counts the same underlying issue."""
        out = {"decision_error": True}
        result = {"findings": {"findings": [
            {"id": "a", "computed": out},
            {"id": "b", "computed": {"consistent": True}},
        ]}}
        s = C.annotate(result, ledger=_ledger(out))
        assert s == {"n_sweep": 2, "n_report": 0, "n_computed": 1,
                     "n_asserted": 0, "n_absent": 1, "corroborated": True}
        assert result["run_meta"]["consequence"] is s


class TestRank:
    def _r(self, basis="computed", **kw):
        return C.rank({"consequence": {"basis": basis, **kw}})

    def test_a_flip_outranks_a_claim_count(self):
        assert self._r(flips_significance=True) < self._r(claims_affected=9)

    def test_unknown_outranks_explicitly_harmless(self):
        """"we did not determine this" must never present as "nothing depends
        on it" -- that is the one direction of error that misleads a reader."""
        assert self._r(flips_significance=None) < self._r(flips_significance=False)

    def test_computed_outranks_an_identical_assertion(self):
        assert (self._r("computed", flips_significance=True)
                < self._r("asserted", flips_significance=True))

    def test_a_finding_with_no_block_sorts_as_unknown(self):
        assert C.rank({}) == self._r("asserted", flips_significance=None)

    @pytest.mark.parametrize("block", [
        {"claims_affected": "3", "basis": "asserted"},      # a string count
        {"claims_affected": [1], "basis": "asserted"},
        {"flips_significance": "yes", "basis": "asserted"},
        {"basis": None},
        "not a dict",
        None,
    ])
    def test_it_is_total_on_raw_model_output(self, block):
        """`rank` runs from `sort_findings` on RAW model output, before
        `normalise` has coerced anything. A TypeError here does not crash --
        it is caught upstream -- it silently discards the entire rendered
        report and falls back to the raw stage-2 prose."""
        assert isinstance(C.rank({"consequence": block}), tuple)


class TestViewerLadderHasOneSource:
    def _viewer(self, findings=()):
        return render_viewer({"paper_id": "X", "findings": list(findings),
                              "report_html": ""})

    def test_the_placeholder_is_substituted(self):
        assert "__SEVERITY_ORDER__" not in self._viewer()

    def test_the_injected_order_is_the_python_ladder(self):
        from forensic_metascience_ai_toolkit.tools.severity import SEVERITY_LEVELS
        m = re.search(r"const order=(\{.*?\});", self._viewer())
        assert m, "the injected severity order is gone"
        assert json.loads(m.group(1)) == {s: i for i, s in enumerate(SEVERITY_LEVELS)}

    def test_the_consequence_renderer_is_wired_into_the_finding_card(self):
        """`"cHtml" in v` alone passes against the static template even with an
        empty findings list; what matters is that `fHtml` CALLS it."""
        v = self._viewer()
        assert re.search(r"function fHtml\(f\)\{.*?\$\{cHtml\(f\)\}", v, re.DOTALL), (
            "cHtml is defined but never called from the finding card"
        )
        assert re.search(r"function cHtml\(f\)\{(?!\s*return ''\s*\})", v), (
            "cHtml is a stub"
        )

    def test_the_consequence_data_reaches_the_page(self):
        v = self._viewer([
            {"id": "f", "severity": "suspicious", "technique": "multiplicity_report",
             "location": "T", "consequence": {"flips_significance": True,
                                              "claims_affected": 3, "basis": "computed"}},
        ])
        assert '"claims_affected": 3' in v or '"claims_affected":3' in v


class TestAnnotateIsIdempotent:
    """`annotate` runs twice on every real run -- once in `analyze_paper`
    before the report is rendered, once again in `write_review_outputs`. The
    second pass sees the block the first pass wrote, so anything that appends
    rather than replaces will double.

    Observed on the run for `10.1002--eat.24415`: "Computed from 2 result(s)
    significant uncorrected do not survive correction (...). Computed from 2
    result(s) significant uncorrected do not survive correction (...)."
    """

    LEDGER = [{
        "validated": True, "tool_short": "statcheck",
        "input": {"text": "t(28) = 2.1, p = .04"},
        "result": json.dumps({"statistics": [{"decision_error": True}]}),
    }]

    def _run(self, passes):
        f = {"id": "f1", "technique": "statcheck", "severity": "suspicious",
             "computed": {"statistics": [{"decision_error": True}]},
             "consequence": {"flips_significance": True, "claims_affected": 1,
                             "basis": "asserted",
                             "explanation": "The headline effect is not significant."}}
        result = {"findings": {"findings": [f]}}
        for _ in range(passes):
            C.annotate(result, self.LEDGER)
        return f["consequence"]["explanation"]

    def test_a_second_pass_changes_nothing(self):
        assert self._run(1) == self._run(2)

    def test_a_third_pass_changes_nothing_either(self):
        assert self._run(1) == self._run(3)

    def test_the_derived_sentence_appears_exactly_once(self):
        once, twice = self._run(1), self._run(2)
        assert "Computed from" in once
        assert twice.count("Computed from") == once.count("Computed from") == 1

    def test_the_models_own_sentence_is_still_kept(self):
        assert "The headline effect is not significant." in self._run(2)

    def test_an_already_doubled_block_is_repaired(self):
        """Runs completed before the fix carry the duplicate in their saved
        output. Re-annotating should collapse it, not freeze it in."""
        derived = {"flips_significance": True, "claims_affected": 1,
                   "basis": "computed",
                   "explanation": "Computed from 1 result(s) X."}
        doubled = {"explanation": ("The headline effect is not significant. "
                                   "Computed from 1 result(s) X. "
                                   "Computed from 1 result(s) X.")}
        out = C._merge_explanation(derived, doubled)
        assert out["explanation"].count("Computed from") == 1
        assert out["explanation"].startswith("The headline effect is not significant.")
