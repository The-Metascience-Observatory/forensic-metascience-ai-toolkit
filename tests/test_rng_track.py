"""The seeded-RNG detector's track-only runs (`rng_track`, 1.101.0).

`rngdetect` (metascience-observatory-rng-detector, a separate package) writes
one `forensic_review_rng/findings.v2.json` per screened paper. Every assertion
here is a distinction a simpler wiring loses:

- a component detector's run is not the paper's review: read as `legacy`, a
  newer-dated rngdetect run would replace the full review as the paper's
  latest run, verdict, numeric channel and worst severity;
- its rows are the detector's evidence, never "the analyst's own reading";
- a quarantined row says so where the reviewer reads it.
"""
import json
import os
import time

import jsonschema

from forensic_metascience_ai_toolkit import corpus_stats, review_issues, webapp_index as W
from forensic_metascience_ai_toolkit.core import prompts
from forensic_metascience_ai_toolkit.discovery import (
    COMPONENT_RUN_KINDS, NOT_A_REVIEW_KINDS, review_dirs_reviews_first, run_kind)
from forensic_metascience_ai_toolkit.names import display


def _rng_row(**over):
    row = {
        "finding_id": "f_0123456789abcdef", "finding_id_hasher": "1",
        "slug": "rng_p6_seed42", "producer": "rng_track", "technique": "no_tool_exists",
        "computed_by": "deterministic_track",
        "title": "Page 6: 400 plotted points reproduce np.random.seed(42) output",
        "description": "The x coordinates of 400 plotted points equal, point for point, "
                       "an affine image of draws from a NumPy generator seeded with 42.",
        "location": "page 6, plotted points", "outcome": "problem",
        "provisional_severity": 3, "severity": 3, "severity_is_provisional": True,
        "impossible": False, "quarantined": True,
        "quarantine_reason": "new detector; real-world precision unmeasured",
        "inputs": {"seed": 42, "n_points": 400}, "anchors": [],
        "reproduction_kind": "no_command_applies",
    }
    row.update(over)
    return row


def _rng_doc(rows=None, state="ran"):
    return {"schema_version": "2.0", "paper_id": "10.1234--demo", "run_id": "r_rng_demo",
            "findings": [_rng_row()] if rows is None else rows,
            "channels": {"rng_track": {"state": state, "detail": "screened"}},
            "adjudication": {"ran": False}}


def _full_review(sev=4):
    return {"schema_version": "2.0", "paper_id": "10.1234--demo", "run_id": "r_full",
            "channels": {"tool_expert": {"state": "ran", "detail": ""}},
            "adjudication": {"ran": True, "verdict": "does_not_reconcile"},
            "findings": [{"finding_id": "f_full", "producer": "tool_expert",
                          "technique": "grim", "title": "Table 2: mean impossible",
                          "outcome": "problem", "severity": sev,
                          "adjudication": {"action": "kept"}}]}


def _paper(tmp_path, files):
    d = tmp_path / "10.1234--demo"
    d.mkdir(parents=True, exist_ok=True)
    (d / "10.1234--demo.pdf").write_text("x")
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(content))
    return d


def _newer(path, seconds=10):
    t = time.time() + seconds
    os.utime(path, (t, t))


class TestVocabulary:
    def test_rng_track_is_a_producer_and_a_track(self):
        assert "rng_track" in prompts.PRODUCERS
        assert "rng_track" in prompts.TRACK_PRODUCERS
        assert "rng_track" in COMPONENT_RUN_KINDS <= NOT_A_REVIEW_KINDS
        assert display("rng_track") == "Seeded-RNG detector (rngdetect)"

    def test_a_quarantined_rng_row_validates_against_the_full_schema(self):
        doc = _rng_doc()
        jsonschema.validate(doc, prompts.findings_schema_v2())

    def test_the_rng_producer_subset_keeps_the_quarantine_fields(self):
        """Track producers may write quarantined/quarantine_reason (spec 4);
        before 1.101.0 the subset stripped them from every non-listed producer."""
        props = prompts.producer_findings_schema("rng_track")["properties"]["findings"]["items"]["properties"]
        assert "quarantined" in props and "quarantine_reason" in props


class TestRunKind:
    def test_an_rng_document_is_its_own_kind_whatever_its_state(self):
        for state in ("ran", "refused", "did_not_run", "unknown"):
            assert run_kind(_rng_doc(state=state)) == "rng_track"

    def test_an_empty_document_is_still_legacy(self):
        assert run_kind({}) == "legacy"

    def test_a_full_review_is_never_reclassified_by_an_rng_channel(self):
        doc = _full_review()
        doc["channels"]["rng_track"] = {"state": "ran", "detail": ""}
        assert run_kind(doc) == "full_review"


class TestNotTheReview:
    def test_a_newer_rng_run_does_not_become_the_latest_review(self, tmp_path):
        d = _paper(tmp_path, {"forensic_review/findings.v2.json": _full_review(4),
                              "forensic_review_rng/findings.v2.json": _rng_doc()})
        _newer(d / "forensic_review_rng")
        rec = W.scan_paper(d)
        assert rec["n_runs"] == 2                       # still listed
        assert rec["latest_run"] == "forensic_review"
        assert rec["verdict"] == "does_not_reconcile"
        assert rec["worst_severity_9"] == 4

    def test_the_rng_run_listed_with_its_kind(self, tmp_path):
        d = _paper(tmp_path, {"forensic_review_rng/findings.v2.json": _rng_doc()})
        rec = W.scan_paper(d)
        assert [r["kind"] for r in rec["runs"]] == ["rng_track"]

    def test_an_rng_run_alone_is_not_a_numeric_review(self, tmp_path):
        d = _paper(tmp_path, {"forensic_review_rng/findings.v2.json": _rng_doc()})
        rec = W.scan_paper(d)
        assert rec["latest_run"] is None
        assert rec["channels"]["numeric"]["state"] == "did_not_run"

    def test_corpus_stats_current_doc_is_the_review(self, tmp_path):
        d = _paper(tmp_path, {"forensic_review/findings.v2.json": _full_review(),
                              "forensic_review_rng/findings.v2.json": _rng_doc()})
        _newer(d / "forensic_review_rng")
        assert corpus_stats._current_doc(d)["run_id"] == "r_full"

    def test_default_issue_pick_serves_the_review_not_the_newer_rng_run(self, tmp_path):
        d = _paper(tmp_path, {"forensic_review/findings.v2.json": _full_review(),
                              "forensic_review_rng/findings.v2.json": _rng_doc()})
        _newer(d / "forensic_review_rng")
        assert [p.name for p in review_dirs_reviews_first(d)] == [
            "forensic_review", "forensic_review_rng"]
        assert review_issues.collect_issues(d)["latest_run"] == "forensic_review"

    def test_the_rng_run_is_served_when_picked(self, tmp_path):
        d = _paper(tmp_path, {"forensic_review/findings.v2.json": _full_review(),
                              "forensic_review_rng/findings.v2.json": _rng_doc()})
        out = review_issues.collect_issues(d, run="forensic_review_rng")
        assert out["latest_run"] == "forensic_review_rng"
        assert [i["producer"] for i in out["issues"] if i["kind"] == "numeric"] == ["rng_track"]


class TestHowTheRowReads:
    def test_the_detector_is_the_tool_not_the_analyst(self):
        assert review_issues.finding_tool(_rng_row()) == {"tool": "rng_track", "source": "component"}

    def test_a_model_row_without_a_tool_is_still_model_judgement(self):
        row = _rng_row(producer="science_error", computed_by="model_reading")
        assert review_issues.finding_tool(row)["source"] == "model_judgement"

    def test_a_quarantined_row_carries_its_flag_and_reason_to_the_issue(self):
        issues, _, _ = review_issues._v2_issues_from_doc(_rng_doc(), "forensic_review_rng",
                                                         include_tracks=True)
        assert issues[0]["quarantined"] is True
        assert issues[0]["quarantine_reason"] == "new detector; real-world precision unmeasured"
        assert issues[0]["tool_source"] == "component"

    def test_an_unquarantined_row_has_no_reason(self):
        doc = _rng_doc([_rng_row(quarantined=False, quarantine_reason=None)])
        issues, _, _ = review_issues._v2_issues_from_doc(doc, "r", include_tracks=True)
        assert issues[0]["quarantined"] is False and issues[0]["quarantine_reason"] is None

    def test_track_rows_are_hidden_from_the_default_issue_list(self):
        """Same rule as the other tracks: hidden unless include_tracks."""
        issues, _, _ = review_issues._v2_issues_from_doc(_rng_doc(), "r")
        assert issues == []
