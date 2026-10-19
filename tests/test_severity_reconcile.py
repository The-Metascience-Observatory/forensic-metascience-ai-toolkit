"""Tool severity vs model severity: the comparison nothing was making.

Every tool returns a `severity`. The model then writes its own, and the only
validation in the codebase checked that the string was a member of the enum --
so a tool returning `impossible` against a finding recording `consistent`
passed silently and the tool's answer survived nowhere in the output.
"""
import json

import pytest

from forensic_metascience_ai_toolkit import severity_reconcile as SR
from forensic_metascience_ai_toolkit.bundle import render_viewer


def _finding(model, tool, **kw):
    f = {"id": "f1", "severity": model, **kw}
    if tool is not None:
        f["computed"] = {**f.get("computed", {}), "severity": tool}
    return f


class TestWhenItSpeaks:
    def test_agreement_produces_nothing(self):
        assert SR.reconcile_finding(_finding("impossible", "impossible")) is None

    def test_no_tool_severity_produces_nothing(self):
        """Most tool outputs carry no severity at all. Silence there is not a
        divergence and must not be reported as one."""
        assert SR.reconcile_finding({"id": "f", "severity": "impossible"}) is None
        assert SR.reconcile_finding(_finding("impossible", None,
                                             computed={"consistent": False})) is None

    def test_it_does_not_compare_the_model_field_with_itself(self):
        """The tool's verdict lives in `computed`; the model's at the top
        level. Reading both from the same place would report perfect agreement
        forever and the check would be worthless."""
        f = {"id": "f", "severity": "consistent",
             "computed": {"severity": "impossible", "consistent": False}}
        assert SR.reconcile_finding(f)["tool"] == "impossible"

    def test_legacy_severity_strings_are_normalised_before_comparing(self):
        """`high` and `highly_suspicious` are the same verdict; reporting them
        as a divergence would bury the real ones in noise."""
        assert SR.reconcile_finding(_finding("highly_suspicious", "high")) is None


class TestDirection:
    def test_softening_the_tool_is_a_downgrade(self):
        b = SR.reconcile_finding(_finding("consistent", "impossible"))
        assert b["direction"] == "downgraded"

    def test_hardening_past_the_tool_is_an_upgrade(self):
        b = SR.reconcile_finding(_finding("impossible", "consistent"))
        assert b["direction"] == "upgraded"

    def test_an_unexplained_downgrade_says_so_in_the_note(self):
        b = SR.reconcile_finding(_finding("consistent", "impossible"))
        assert b["explained"] is False
        assert "NO REASON IS STATED" in b["note"]

    def test_a_stated_reason_is_accepted(self):
        b = SR.reconcile_finding(_finding(
            "consistent", "impossible",
            notes="GRIM was applied to a continuous variable, so the result is meaningless."))
        assert b["explained"] is True
        assert "NO REASON" not in b["note"]

    def test_a_token_note_is_not_a_reason(self):
        assert SR.reconcile_finding(_finding("consistent", "impossible",
                                             notes="ok"))["explained"] is False


class TestItDoesNotOverruleTheModel:
    def test_the_recorded_severity_is_left_alone(self):
        """Overwriting the model with the tool would reinstate exactly the
        false positives the applicability guards exist to prevent -- GRIM on a
        continuous variable returns `impossible` on an ordinary number."""
        result = {"findings": {"findings": [_finding("consistent", "impossible")]}}
        SR.annotate(result)
        assert result["findings"]["findings"][0]["severity"] == "consistent"

    def test_the_tools_verdict_survives_in_the_output(self):
        result = {"findings": {"findings": [_finding("consistent", "impossible")]}}
        SR.annotate(result)
        assert result["findings"]["findings"][0]["severity_source"]["tool"] == "impossible"


class TestSummary:
    def test_counts_reach_run_meta(self):
        result = {"findings": {"findings": [
            _finding("consistent", "impossible"),                       # unexplained down
            _finding("impossible", "consistent",
                     notes="The paper states the scale bounds explicitly in Methods."),
            _finding("suspicious", "suspicious"),                       # agrees
            {"id": "x", "severity": "impossible"},                      # no tool severity
        ]}}
        s = SR.annotate(result)
        assert s["n_compared"] == 3
        assert s["n_diverged"] == 2
        assert s["n_downgraded_unexplained"] == 1
        assert s["n_upgraded_unexplained"] == 0
        assert result["run_meta"]["severity_reconciliation"] is s

    def test_a_run_that_compared_nothing_says_so(self):
        """The summary is written even when nothing joined.

        It used to be written only when `n_compared` was non-zero, so a run
        where the join was BROKEN produced no `severity_reconciliation` key at
        all -- which reads as "no disagreements found". That is exactly what
        happened on the first real run: 24 findings, 22 validated tool calls,
        nothing compared, and the output looked clean.
        """
        result = {"findings": {"findings": [{"id": "x", "severity": "impossible",
                                             "technique": "grim"}]}}
        SR.annotate(result)
        summary = result["run_meta"]["severity_reconciliation"]
        assert summary["n_compared"] == 0
        assert summary["n_unjoined"] == 1      # named a tool, matched no call
        assert summary["n_manual"] == 0

    def test_a_hand_computed_finding_is_not_a_failed_join(self):
        """`manual` has no tool verdict by definition -- an honest zero, not a
        broken join. Conflating the two would hide the latter."""
        result = {"findings": {"findings": [{"id": "x", "severity": "impossible",
                                             "technique": "manual"}]}}
        SR.annotate(result)
        summary = result["run_meta"]["severity_reconciliation"]
        assert (summary["n_manual"], summary["n_unjoined"]) == (1, 0)

    def test_a_stale_block_is_cleared_when_it_now_agrees(self):
        f = _finding("impossible", "impossible")
        f["severity_source"] = {"model": "consistent", "tool": "impossible"}
        result = {"findings": {"findings": [f]}}
        SR.annotate(result)
        assert "severity_source" not in f


class TestTheLedgerIsWhereTheVerdictActuallySurvives:
    """`computed.severity` is present in only 3 of the 164 findings in the
    committed corpus -- the model transcribes the numbers it wants to talk
    about, not the whole tool result. The same run's ledger carried 40 tool
    severities. Reading only `computed` made this check nearly inert."""

    LEDGER = [
        {"validated": True, "tool_short": "grim_check",
         "input": {"mean": 5.51, "n": 30, "data_type": "likert"},
         "result": json.dumps({"consistent": False, "severity": "impossible"})},
        {"validated": False, "tool_short": "grim_check",
         "input": {"mean": 1.0, "n": 2},
         "result": json.dumps({"severity": "impossible"})},
    ]

    def test_a_finding_joins_to_the_call_that_produced_it(self):
        f = {"id": "f", "technique": "grim", "severity": "consistent",
             "inputs": {"mean": 5.51, "n": 30}}
        b = SR.reconcile_finding(f, SR.severities_from_ledger(self.LEDGER))
        assert b is not None and b["tool"] == "impossible"
        assert b["direction"] == "downgraded"

    def test_a_technique_names_a_family_not_one_tool(self):
        """The first version mapped each technique to a SINGLE tool name and
        matched nothing at all on a real run. The model labels the FAMILY: it
        called `grim_percentage` and wrote `technique: "grim"`, called
        `check_sd_range` and wrote `check_sd_or_se`. Both labels are legal
        schema values, so a one-to-one table was simply the wrong shape.
        """
        grim = SR._candidate_tools("grim")
        assert "grim_check" in grim and "grim_percentage" in grim
        assert "sprite_reconstruct" in SR._candidate_tools("sprite")
        assert SR._candidate_tools("manual") == ()

    def test_batch_variants_are_candidates_without_being_listed(self):
        """A finding says `check_regression`; the ledger records one
        `check_regression_batch` call carrying 84 rows."""
        assert "check_regression_batch" in SR._candidate_tools("check_regression")

    def test_a_technique_that_is_already_a_tool_name_needs_no_entry(self):
        assert "statcheck" in SR._candidate_tools("statcheck")

    def test_unvalidated_calls_are_not_a_tools_verdict(self):
        got = SR.severities_from_ledger(self.LEDGER)
        assert len(got) == 1

    def test_an_ambiguous_join_is_refused(self):
        """Two calls to the same tool matching the same arguments cannot
        identify which produced the finding, so nothing is claimed."""
        led = self.LEDGER[:1] + [dict(self.LEDGER[0],
                                      result=json.dumps({"severity": "consistent"}))]
        f = {"id": "f", "technique": "grim", "severity": "suspicious",
             "inputs": {"mean": 5.51, "n": 30}}
        assert SR.reconcile_finding(f, SR.severities_from_ledger(led)) is None

    def test_computed_severity_still_wins_when_present(self):
        """It is the more direct route; the ledger join is the fallback."""
        f = {"id": "f", "technique": "grim", "severity": "consistent",
             "inputs": {"mean": 5.51, "n": 30},
             "computed": {"severity": "suspicious"}}
        b = SR.reconcile_finding(f, SR.severities_from_ledger(self.LEDGER))
        assert b["tool"] == "suspicious"

    def test_the_summary_reports_how_much_was_available_to_compare(self):
        result = {"findings": {"findings": [
            {"id": "f", "technique": "grim", "severity": "consistent",
             "inputs": {"mean": 5.51, "n": 30}}]}}
        s = SR.annotate(result, self.LEDGER)
        assert s["n_tool_severities_available"] == 1
        assert s["n_compared"] == 1 and s["n_diverged"] == 1


class TestItReachesTheViewer:
    def test_a_divergence_reaches_the_payload(self):
        v = render_viewer({"paper_id": "X", "report_html": "", "findings": [
            {"id": "f", "severity": "S2", "severity_9": 2, "technique": "grim",
             "severity_source": {"model": "consistent", "tool": "impossible",
                                 "direction": "downgraded", "explained": False,
                                 "note": "NO REASON IS STATED."}},
        ]})
        assert "NO REASON IS STATED." in v

    def test_a_divergence_is_rendered_on_the_findings_page(self, tmp_path):
        from tests.test_bundle import section_html
        payload = {"paper_id": "X", "report_html": "", "findings": [
            {"id": "f", "severity": "S2", "severity_9": 2, "technique": "grim",
             "title": "t", "outcome": "problem",
             "severity_source": {"model": "consistent", "tool": "impossible",
                                 "direction": "downgraded", "explained": False,
                                 "note": "NO REASON IS STATED."}}]}
        assert "NO REASON IS STATED." in section_html(payload, "findings", tmp_path)


class TestWhatTheFirstRealRunBroke:
    """Every case here is taken from the run on `10.1002--eat.24415`, where
    this module compared NOTHING against a ledger of 22 validated calls.

    Four independent causes, each alone sufficient to zero the join. They are
    tested separately because fixing any three of them still yields zero.
    """

    def test_a_batch_call_contributes_its_rows_not_its_worst_row(self):
        """`check_regression_batch` carried 84 rows. The call-level severity is
        the WORST of them, so comparing a single-coefficient finding against it
        would call every coefficient in the table indeterminate."""
        ledger = [{
            "validated": True, "tool_short": "check_regression_batch",
            "input": {"rows": [{"b": 0.11, "se": 0.05, "reported_t": 2.46},
                               {"b": 0.30, "se": 0.02, "reported_t": 15.0}]},
            "result": json.dumps({
                "severity": "indeterminate",          # the worst row
                "results": [{"row": 0, "b": 0.11, "se": 0.05,
                             "severity": "consistent"},
                            {"row": 1, "b": 0.30, "se": 0.02,
                             "severity": "indeterminate"}]}),
        }]
        got = SR.severities_from_ledger(ledger)
        assert len(got) == 2, "rows must be expanded"
        assert {s for _, _, s in got} == {"consistent", "indeterminate"}
        assert all(name == "check_regression" for name, _, _ in got), \
            "rows belong to the base tool, which is what a finding names"

    def test_a_batch_row_carries_its_own_input_row(self):
        """A row echoes `b` and `se` but not `reported_t`, while the finding's
        inputs name all three -- so the row's own fields are not enough."""
        ledger = [{
            "validated": True, "tool_short": "check_regression_batch",
            "input": {"rows": [{"b": 0.11, "se": 0.05, "reported_t": 2.46}]},
            "result": json.dumps({"severity": "consistent", "results": [
                {"row": 0, "b": 0.11, "se": 0.05, "severity": "consistent"}]}),
        }]
        f = {"id": "f", "technique": "check_regression", "severity": "suspicious",
             "inputs": {"b": 0.11, "se": 0.05, "reported_t": 2.46}}
        assert SR._tool_severity(f, SR.severities_from_ledger(ledger)) == "consistent"

    def test_a_check_dispatched_inside_check_table_is_recovered(self):
        """`check_sd_or_se` never appears in the ledger under its own name --
        `check_table` dispatches it per cell. Its verdict exists only in the
        enclosing call's `results[]`, which is why the finding never joined."""
        ledger = [{
            "validated": True, "tool_short": "check_table",
            "input": {"cells": [{"raw": "5.5 (1.2)"}]},
            "result": json.dumps({"severity": "indeterminate", "results": [
                {"tool": "check_sd_or_se", "severity": "indeterminate",
                 "inputs": {"sd": 1.2, "n": 30}}]}),
        }]
        got = SR.severities_from_ledger(ledger)
        assert got and got[0][0] == "check_sd_or_se"

    def test_prose_inputs_do_not_defeat_the_join(self):
        """Measured: `inputs` is written for a human. A real finding carried
        `n: "not supplied - the level-1 observation count is never reported"`.
        Requiring that to equal a tool argument is why the join found nothing.
        """
        ledger = [{
            "validated": True, "tool_short": "check_sd_range",
            "input": {"sd": 1.2, "min_val": 1, "max_val": 5, "n": 107},
            "result": json.dumps({"severity": "consistent"}),
        }]
        f = {"id": "f", "technique": "check_sd_range", "severity": "suspicious",
             "inputs": {"min_val": 1, "max_val": 5,
                        "n": "not supplied - never reported"}}
        assert SR._tool_severity(f, SR.severities_from_ledger(ledger)) == "consistent"

    def test_prose_is_dropped_rather_than_fuzzy_matched(self):
        """Dropping a string is safe; guessing at one attributes another
        check's verdict to this finding."""
        assert SR._comparable({("a", "2 (3 for -0.004)"), ("b", 2)}) == {("b", 2)}

    def test_a_finding_naming_nothing_comparable_still_joins_if_all_calls_agree(self):
        ledger = [{"validated": True, "tool_short": "grim_check",
                   "input": {"mean": 5.51, "n": 30},
                   "result": json.dumps({"severity": "impossible"})},
                  {"validated": True, "tool_short": "grim_check",
                   "input": {"mean": 2.20, "n": 40},
                   "result": json.dumps({"severity": "impossible"})}]
        f = {"id": "f", "technique": "grim", "severity": "consistent",
             "inputs": {"note": "both means"}}
        assert SR._tool_severity(f, SR.severities_from_ledger(ledger)) == "impossible"

    def test_but_not_when_they_disagree(self):
        """Nine `check_summation` rows split consistent/suspicious on the real
        run. Picking either would be inventing a verdict."""
        ledger = [{"validated": True, "tool_short": "check_summation",
                   "input": {"expected_sum": 100},
                   "result": json.dumps({"severity": "consistent"})},
                  {"validated": True, "tool_short": "check_summation",
                   "input": {"expected_sum": 112},
                   "result": json.dumps({"severity": "suspicious"})}]
        f = {"id": "f", "technique": "check_summation", "severity": "consistent",
             "inputs": {"note": "eight summation rows"}}
        assert SR._tool_severity(f, SR.severities_from_ledger(ledger)) is None

    def test_a_tool_that_issues_no_verdict_is_not_a_failed_join(self):
        """`multiplicity_report` returns arithmetic and deliberately does not
        decide whether losing two claims is suspicious -- that is stage 2's
        judgement, and inventing a threshold here would prejudge it."""
        ledger = [{"validated": True, "tool_short": "multiplicity_report",
                   "input": {"family_label": "indirect effects"},
                   "result": json.dumps({"n_claims_lost_to_correction": 2,
                                         "bh_threshold": 0.0125})}]
        assert SR.severities_from_ledger(ledger) == []


class TestTheFamilyRoutesThatWereMissing:
    """Four registered tools had no technique route, and half of `reconcile`
    pointed at the wrong family.

    Both are join failures, and a join failure here is silent by construction:
    the tool's verdict is simply discarded and the model's stands unchallenged.
    That is the failure mode this whole module exists to prevent.
    """

    CI_LEDGER = [
        {"validated": True, "tool_short": "check_estimate_ci",
         "input": {"estimate": 1.42, "ci_low": 1.08, "ci_high": 1.87,
                   "reported_p": 0.51},
         "result": json.dumps({"severity": "suspicious"})},
    ]

    def test_reconcile_reaches_check_estimate_ci(self):
        """Measured: 32 of the 68 `reconcile` findings in the corpus reproduce
        with `check-ci`. About half of that family is not an argument about a
        parsed table at all -- it is a point estimate disagreeing with its own
        confidence interval -- and every one of those joined to nothing."""
        assert "check_estimate_ci" in SR._candidate_tools("reconcile")

    def test_a_reconcile_finding_now_joins_to_the_ci_call(self):
        f = {"id": "f", "technique": "reconcile", "severity": "consistent",
             "inputs": {"estimate": 1.42, "ci_low": 1.08, "ci_high": 1.87}}
        b = SR.reconcile_finding(f, SR.severities_from_ledger(self.CI_LEDGER))
        assert b is not None and b["tool"] == "suspicious"
        assert b["direction"] == "downgraded"

    def test_the_table_routes_are_not_displaced_by_it(self):
        """`reconcile` is still, mostly, an argument about a parsed table."""
        c = SR._candidate_tools("reconcile")
        for name in ("parse_table", "parse_cells_typed", "check_table"):
            assert name in c

    #: These four have a ToolSpec but no entry in the findings schema's
    #: `technique` enum, so nothing routed a finding back to them.
    UNROUTED = ("absence_of_evidence", "check_effect_plausibility",
                "check_estimate_ci", "verify_power_analysis")

    @pytest.mark.parametrize("technique", UNROUTED)
    def test_the_route_is_declared_rather_than_left_to_the_fallback(self, technique):
        """`_candidate_tools` falls through to the technique's own name, so
        these resolved correctly by COINCIDENCE -- the technique string happens
        to equal the tool name. A coincidence is not a route: it records no
        decision, breaks silently if the fallback ever changes, and leaves the
        table looking like these four tools were considered and excluded.

        Consequence while they were absent: 12 of 15 stage-1 runs showed these
        findings under `hand-computed` in the bundle check table AND showed the
        tool itself flowing to `no finding` in the Sankey -- the same work
        counted twice, once as unattributed and once as unproductive.
        """
        assert technique in SR._TECHNIQUE_TOOLS
        assert technique in SR._candidate_tools(technique)

    @pytest.mark.parametrize("technique", UNROUTED)
    def test_a_finding_from_one_of_them_joins_to_its_call(self, technique):
        ledger = [{"validated": True, "tool_short": technique,
                   "input": {"n": 40},
                   "result": json.dumps({"severity": "indeterminate"})}]
        f = {"id": "f", "technique": technique, "severity": "suspicious",
             "inputs": {"n": 40}}
        b = SR.reconcile_finding(f, SR.severities_from_ledger(ledger))
        assert b is not None and b["tool"] == "indeterminate"
