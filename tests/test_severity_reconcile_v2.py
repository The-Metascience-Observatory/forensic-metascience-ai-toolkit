"""Did the adjudicator keep the tool's verdict, and if not, did it say why?

Ported to the parallel pipeline 2026-09-03. Until then `severity_reconcile`
ran only in the legacy writer, so `run_meta.severity_reconciliation` -- whose
`divergences` list is pinned in `VIEWER_MUST_RENDER` and rendered by the
viewer's "Did the write-up keep the tool's verdict?" section -- was satisfied
by archived legacy runs alone, and the section vanished silently on every
current run.

THE V2 QUESTION IS NOT THE V1 QUESTION. In v1 the editorial stage had no
mandate to re-grade, so any departure from the tool's verdict was suspicious.
In v2 an adjudicator exists whose entire job is assigning the final rung, so a
departure is the design working; flagging every one would fire on nearly every
finding and be ignored. The v2 check is a departure the adjudication does not
explain.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from metascience_agent import agent, severity9, severity_reconcile as SR

ARCHIVE = pathlib.Path(__file__).resolve().parents[1] / "benchmarks" / "paper_reviews" / "runs"


def _ledger(tool, args, result):
    msgs = [{"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "c1", "name": agent._mcp(tool),
                 "input": args}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "c1",
                 "content": [{"type": "text", "text": json.dumps(result)}]}]}}]
    return agent._tool_call_ledger(msgs, [])


def _doc(*findings):
    return {"schema_version": "2.0", "findings": list(findings)}


class TestTheLadderMapping:
    def test_only_the_accusatory_values_have_a_rung(self):
        """The trap this module has to avoid: `indeterminate` and `consistent`
        map to non-problem outcomes with a null severity, so comparing them to
        an integer rung is a category error."""
        assert set(severity9.FIVE_TO_NINE) == {
            "suspicious", "highly_suspicious", "impossible"}
        assert "indeterminate" in SR._NOT_ON_THE_LADDER
        assert "consistent" in SR._NOT_ON_THE_LADDER

    def test_a_tool_verdict_off_the_ladder_is_not_a_divergence(self):
        led = _ledger("grim_check", {"mean": 3.5, "n": 30},
                      {"severity": "consistent"})
        f = {"finding_id": "f1", "technique": "grim",
             "inputs": {"mean": 3.5, "n": 30}, "severity": 4}
        assert SR.reconcile_finding_v2(f, SR.severities_from_ledger(led)) is None, (
            "a `consistent` tool verdict has no rung; diffing it against 4 "
            "would manufacture a divergence out of a category error")


class TestWhatCountsAsADivergence:
    def _pair(self, tool_sev, final, **extra):
        led = _ledger("grim_check", {"mean": 3.5, "n": 30},
                      {"severity": tool_sev})
        f = {"finding_id": "f1", "technique": "grim",
             "inputs": {"mean": 3.5, "n": 30}, "severity": final}
        f.update(extra)
        return SR.reconcile_finding_v2(f, SR.severities_from_ledger(led))

    def test_agreement_is_not_reported(self):
        assert self._pair("suspicious", severity9.FIVE_TO_NINE["suspicious"]) is None

    def test_an_unexplained_upgrade_is_flagged(self):
        b = self._pair("suspicious", 7)
        assert b["direction"] == "upgraded" and b["explained"] is False
        assert "STATES NO REASON" in b["note"]

    def test_an_unexplained_downgrade_is_flagged(self):
        b = self._pair("impossible", 1)
        assert b["direction"] == "downgraded" and b["explained"] is False

    def test_an_adjudicated_departure_is_explained_not_alarming(self):
        """The adjudicator's JOB is to set the final rung. A departure it
        reasons about is the design working, not a defect."""
        b = self._pair("suspicious", 7, adjudication={
            "action": "kept",
            "rationale": "the tool checked one row; the pattern spans the table"})
        assert b["explained"] is True
        assert "states a reason" in b["note"]

    def test_a_finding_with_no_final_rung_is_not_a_divergence(self):
        assert self._pair("suspicious", None) is None


class TestEveryFindingLandsInExactlyOneBucket:
    """The conservation property. This module's first version compared NOTHING
    on a run with 22 validated calls and reported that as an absence of
    divergence; the buckets exist so a reader can tell a quiet run from a
    broken join."""

    RUNS = ["apple_cider", "wound_healing", "cerebrolysin_flow", "airforce"]

    @pytest.mark.parametrize("run", RUNS)
    def test_the_buckets_sum_to_the_finding_count(self, run):
        d = ARCHIVE / run / "forensic_review"
        if not (d / "findings.v2.json").is_file():
            pytest.skip(f"{run} is not in this checkout")
        led = []
        for label in ("tool_agent", "science_agent", "adjudicator"):
            p = d / f"toolcalls.{label}.json"
            if p.is_file():
                led += json.loads(p.read_text())
        doc = json.loads((d / "findings.v2.json").read_text())
        n = len(doc.get("findings") or [])
        s = SR.annotate_v2(doc, led)
        total = (s["n_compared"] + s["n_unjoined"] + s["n_manual"]
                 + s["n_not_on_ladder"] + s["n_no_final_severity"])
        assert total == n, (
            f"{run}: {total} bucketed against {n} findings -- a finding in no "
            f"bucket is one the summary cannot account for")

    def test_a_judgement_technique_is_manual_not_a_broken_join(self):
        """`_candidate_tools` falls back to the technique's own name, so
        `not_computational` was filed as a failed join -- overstating our own
        failure, which misleads exactly as much as understating it."""
        assert SR._has_real_tool("not_computational") is False
        assert SR._has_real_tool("internal_contradiction") is False
        assert SR._has_real_tool("grim") is True
        s = SR.annotate_v2(_doc({"finding_id": "f1",
                                 "technique": "not_computational",
                                 "severity": 3}), [])
        assert s["n_manual"] == 1 and s["n_unjoined"] == 0


class TestTheSummaryIsAlwaysRecorded:
    def test_a_run_with_no_ledger_still_reports(self):
        """Writing the summary only when something matched is what hid the
        broken join: the key was simply absent, which reads as 'no
        disagreements' and is indistinguishable from 'this did nothing'."""
        s = SR.annotate_v2(_doc(), [])
        assert s["n_tool_severities_available"] == 0
        assert s["divergences"] == []
        assert "n_unjoined" in s and "n_manual" in s

    def test_every_divergence_is_listed_with_its_marker(self):
        """A list carrying only the unexplained ones beside an `n_diverged`
        that counts all of them makes a reader do subtraction."""
        led = _ledger("grim_check", {"mean": 3.5, "n": 30},
                      {"severity": "suspicious"})
        doc = _doc({"finding_id": "f1", "technique": "grim",
                    "inputs": {"mean": 3.5, "n": 30}, "severity": 7,
                    "adjudication": {"rationale": "x" * 40}})
        s = SR.annotate_v2(doc, led)
        assert s["n_diverged"] == 1
        assert len(s["divergences"]) == 1
        assert "explained" in s["divergences"][0]


class TestItConsumesTheAnnotatorsJoinRatherThanRederivingOne:
    """The first cut of this port re-derived the tool join with
    `_tool_severity`, which matches on the finding's `inputs` scalars -- and
    **v2 findings do not carry `inputs`**. So it fell through to its weakest
    path while `findings_v2.tool_verdict_for` had already written the answer
    onto the very same findings, 1,300 lines earlier in `parallel.py`.
    Measured on the archive: two findings were filed as "we could not join"
    when a validated verdict was sitting on them.
    """

    def test_tool_verdict_is_preferred_over_the_ledger_join(self):
        f = {"finding_id": "f1", "technique": "grim", "severity": 7,
             "tool_verdict": {"severity": "suspicious", "tool": "grim_check",
                              "validated": True}}
        sev, route = SR._v2_tool_severity(f, [])
        assert (sev, route) == ("suspicious", "tool_verdict")

    def test_a_finding_with_no_inputs_still_joins(self):
        """The whole point: `inputs` is absent on v2 rows, so the ledger route
        cannot fire and the comparison would silently not happen."""
        doc = _doc({"finding_id": "f1", "technique": "grim", "severity": 7,
                    "tool_verdict": {"severity": "suspicious",
                                     "tool": "grim_check", "validated": True},
                    "adjudication": {"rationale": "x" * 40}})
        s = SR.annotate_v2(doc, [])
        assert s["n_compared"] == 1
        assert s["n_joined_by_tool_verdict"] == 1
        assert s["n_unjoined"] == 0

    def test_the_ledger_join_survives_as_a_fallback(self):
        """A superset of the old behaviour, never a replacement: a row the
        annotator could not join but whose `inputs` identify a call is still
        compared."""
        led = _ledger("grim_check", {"mean": 3.5, "n": 30},
                      {"severity": "suspicious"})
        doc = _doc({"finding_id": "f1", "technique": "grim",
                    "inputs": {"mean": 3.5, "n": 30}, "severity": 7,
                    "adjudication": {"rationale": "x" * 40}})
        s = SR.annotate_v2(doc, led)
        assert s["n_compared"] == 1
        assert s["n_joined_by_ledger"] == 1

    def test_a_non_ladder_tool_verdict_is_not_a_failed_join(self):
        """`consistent` is a verdict, not an absence of one. Counting it as
        `n_unjoined` overstates our own failure -- the mirror of understating
        it, and just as misleading."""
        doc = _doc({"finding_id": "f1", "technique": "grim", "severity": 7,
                    "tool_verdict": {"severity": "consistent",
                                     "tool": "grim_check", "validated": True}})
        s = SR.annotate_v2(doc, [])
        assert s["n_not_on_ladder"] == 1
        assert s["n_unjoined"] == 0

    def test_the_route_is_recorded_on_the_block(self):
        doc = _doc({"finding_id": "f1", "technique": "grim", "severity": 7,
                    "tool_verdict": {"severity": "suspicious",
                                     "tool": "grim_check", "validated": True}})
        SR.annotate_v2(doc, [])
        assert doc["findings"][0]["severity_source"]["joined_by"] == "tool_verdict"


class TestTheFieldItWritesIsLegalAndPipelineOnly:
    """`findings/items` is `additionalProperties: false`, so a field the
    pipeline writes and the schema does not declare is illegal by contract --
    and nothing validates the WRITTEN document, so only the absence of a
    validator kept it green. v1.24.0 shipped exactly that."""

    def test_severity_source_is_declared_in_the_v2_schema(self):
        from metascience_agent.core import prompts
        props = (prompts.findings_schema_v2()
                 ["properties"]["findings"]["items"]["properties"])
        assert "severity_source" in props, (
            "annotate_v2 writes this field into a closed schema")

    def test_no_producer_is_offered_the_slot(self):
        """A producer able to write its own `severity_source` could assert
        agreement with a tool that never ran."""
        from metascience_agent.core import prompts
        for p in prompts.PRODUCERS:
            try:
                sub = prompts.producer_findings_schema(p)
            except ValueError:
                continue          # converter-written producers have no subset
            props = sub["properties"]["findings"]["items"]["properties"]
            assert "severity_source" not in props, p

    def test_an_annotated_finding_satisfies_the_items_schema(self):
        import jsonschema
        from metascience_agent.core import prompts
        items = (prompts.findings_schema_v2()
                 ["properties"]["findings"]["items"])
        doc = _doc({"finding_id": "f1", "technique": "grim", "severity": 7,
                    "title": "t", "detail": "d",
                    "tool_verdict": {"severity": "suspicious",
                                     "tool": "grim_check", "validated": True}})
        SR.annotate_v2(doc, [])
        block = doc["findings"][0]["severity_source"]
        assert block is not None
        jsonschema.Draft202012Validator(
            items["properties"]["severity_source"]).validate(block)
