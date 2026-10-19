"""Which passage was this finding's numbers read from? (parallel pipeline)

`source` was a CONTRACT WITH NO PRODUCER until 2026-09-04: declared in
`findings.v2.schema.json` ("Set by the pipeline, not the model", five
subfields) AND listed in `prompts._NOT_PRODUCER_WRITTEN`, so the design
already said the pipeline writes it -- and nothing on the parallel path did.
Measured before the port: 0 of 80 findings across the four archived parallel
runs carried it, against every legacy run that did. The legacy deletion would
have taken the capability silently, because `annotate` lives in
`write_review_outputs`.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from forensic_metascience_ai_toolkit import sourcing


def _ledger(tool, args, **entry):
    return [{"tool_short": tool, "input": args, "validated": True, **entry}]


def _doc(*findings):
    return {"schema_version": "2.0", "paper_id": "p", "findings": list(findings)}


class TestTheJoin:
    def test_a_finding_gets_the_quote_of_its_producing_call(self):
        led = _ledger("grim_check", {"mean": 3.5, "n": 30,
                                     "source_quote": "Age 3.5 (n=30)",
                                     "source_locator": "Table 1"})
        doc = _doc({"finding_id": "f1", "technique": "grim"})
        s = sourcing.annotate_v2(doc, led)
        src = doc["findings"][0]["source"]
        assert src["source_quote"] == "Age 3.5 (n=30)"
        assert src["source_locator"] == "Table 1"
        assert s["traced_to_a_passage"] == 1

    def test_disagreeing_quotes_refuse_rather_than_guess(self):
        """Attaching one row's evidence to another row's accusation is the
        false attribution this module exists to prevent."""
        led = (_ledger("grim_check", {"n": 30, "source_quote": "row A"})
               + _ledger("grim_check", {"n": 40, "source_quote": "row B"}))
        doc = _doc({"finding_id": "f1", "technique": "grim"})
        sourcing.annotate_v2(doc, led)
        assert "source" not in doc["findings"][0]

    def test_an_unvalidated_call_contributes_nothing(self):
        led = _ledger("grim_check", {"source_quote": "q"})
        led[0]["validated"] = False
        doc = _doc({"finding_id": "f1", "technique": "grim"})
        s = sourcing.annotate_v2(doc, led)
        assert "source" not in doc["findings"][0]
        assert s["quotes_available"] == 0

    def test_a_model_written_source_is_stripped_before_deciding(self):
        """The party being checked does not get to certify itself."""
        doc = _doc({"finding_id": "f1", "technique": "grim",
                    "source": {"source_quote": "I made this up"}})
        sourcing.annotate_v2(doc, [])
        assert "source" not in doc["findings"][0]


class TestManualIsNotAFailedJoin:
    """v2 techniques include judgement calls with no producing call BY
    DEFINITION. `_candidate_tools` falls back to the technique's own name, so
    the v1 test files those as joinable and then as untraced -- reporting a
    design fact as a coverage failure."""

    @pytest.mark.parametrize("technique",
                             ["not_computational", "internal_contradiction",
                              "factual_claim"])
    def test_a_judgement_technique_lands_in_manual(self, technique):
        s = sourcing.annotate_v2(_doc({"finding_id": "f1",
                                       "technique": technique}), [])
        assert s["manual"] == 1 and s["joinable"] == 0

    def test_the_buckets_sum_to_the_finding_count(self):
        doc = _doc({"finding_id": "a", "technique": "grim"},
                   {"finding_id": "b", "technique": "not_computational"},
                   {"finding_id": "c", "technique": "check_table"})
        s = sourcing.annotate_v2(doc, [])
        assert s["joinable"] + s["manual"] == s["findings"] == 3


class TestAgainstTheArchive:
    """The port must actually fire on real documents, not just fixtures."""

    @pytest.mark.parametrize("run,min_traced",
                             [("apple_cider", 10), ("cerebrolysin_flow", 5)])
    def test_archived_parallel_runs_now_trace_findings(self, run, min_traced):
        base = pathlib.Path(__file__).parent.parent / "benchmarks/paper_reviews/runs" / run / "forensic_review"
        doc_path = base / "findings.v2.json"
        if not doc_path.exists():
            pytest.skip(f"{run} not on this disk")
        doc = json.loads(doc_path.read_text())
        led = []
        for f in sorted(base.glob("toolcalls.*.json")):
            v = json.loads(f.read_text())
            led += v if isinstance(v, list) else (v.get("calls") or [])
        s = sourcing.annotate_v2(doc, led)
        assert s["traced_to_a_passage"] >= min_traced
        assert s["joinable"] + s["manual"] == s["findings"]
