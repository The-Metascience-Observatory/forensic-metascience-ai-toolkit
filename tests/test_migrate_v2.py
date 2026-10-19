"""The legacy converter: mapping, backdating, idempotency, review joins."""

import json
import time
from pathlib import Path

import jsonschema
import pytest

from forensic_metascience_ai_toolkit import migrate_v2 as M
from forensic_metascience_ai_toolkit.core import prompts


class TestRowMapping:
    def test_severity_map_outcome_and_the_impossible_gate(self):
        row = {"id": "t1_grim", "technique": "grim",
               "severity": "impossible", "location": "Table 1",
               "quote": "mean 3.53 (n=30)", "consistent": False}
        out = M.convert_row(row)
        assert out["technique"] == "grim_check"
        assert out["outcome"] == "problem"
        assert out["provisional_severity"] == out["severity"] == 5
        assert out["severity_is_provisional"] is True
        assert out["impossible"] is True          # absolute-evidence tool
        assert out["legacy"]["original_id"] == "numeric:t1_grim"
        assert out["anchors"] == [{"kind": "quote",
                                   "quote": "mean 3.53 (n=30)"}]

    def test_impossible_never_from_a_non_absolute_tool(self):
        row = {"id": "d1", "technique": "duplication",
               "severity": "impossible", "location": "Tables 1-3"}
        out = M.convert_row(row)
        assert out["impossible"] is False, \
            "duplication is probabilistic; v1 mislabels do not mint the flag"

    def test_consistent_and_indeterminate_carry_no_severity(self):
        for sev5, outcome in (("consistent", "pass"),
                              ("indeterminate", "undecided")):
            out = M.convert_row({"id": "x", "technique": "grim",
                                 "severity": sev5, "location": "T1"})
            assert out["outcome"] == outcome
            assert out["severity"] is None
            assert out["provisional_severity"] is None

    def test_quarantined_track_rows_keep_their_raw_grade(self):
        row = {"id": "IMGDUP-2", "technique": "image_duplication",
               "severity": "indeterminate",
               "severity_before_quarantine": "highly_suspicious",
               "quarantine_reason": "uncalibrated", "location": "Fig 3"}
        out = M.convert_row(row)
        assert out["producer"] == "image_track"
        assert out["quarantined"] is True
        assert out["tool_verdict"]["quarantined_raw"] == "highly_suspicious"
        assert out["legacy"]["original_id"] == "image:IMGDUP-2"

    def test_unknown_technique_is_named_not_guessed(self):
        out = M.convert_row({"id": "m1", "technique": "manual",
                             "severity": "suspicious", "location": "p2"})
        assert out["technique"] == "legacy_unattributed"


@pytest.fixture()
def legacy_paper(tmp_path):
    paper = tmp_path / "10.1234--x"
    run = paper / "forensic_review"
    run.mkdir(parents=True)
    (run / "findings.json").write_text(json.dumps({
        "schema_version": "1.0", "paper_id": "10.1234--x",
        "findings": [
            {"id": "t1_grim", "technique": "grim", "severity": "impossible",
             "location": "Table 1", "quote": "mean 3.53", "consistent": False},
            {"id": "ok1", "technique": "statcheck", "severity": "consistent",
             "location": "Results", "consistent": True},
        ],
        "coverage": {"stats_found": 2, "tools_run": ["grim_check"]}}))
    (run / "report.json").write_text("{}")
    return paper


class TestRunConversion:
    def test_backdating_and_version_default(self, legacy_paper):
        rec = M.convert_run(legacy_paper / "forensic_review", "10.1234--x")
        doc = json.loads((legacy_paper / "forensic_review" /
                          "findings.v2.json").read_text())
        assert rec["converted"] and rec["n_findings"] == 2
        assert doc["legacy"]["pipeline_version"] == "0.0.1"
        assert doc["legacy"]["analysed_at_source"] == "file_mtime"
        assert doc["channels"]["science_error"]["state"] == "did_not_run"
        jsonschema.validate(doc, prompts.findings_schema_v2())

    def test_recorded_dates_are_preferred(self, legacy_paper):
        (legacy_paper / "forensic_review" / "run_meta.json").write_text(
            json.dumps({"analysed_at": "2026-07-01T00:00:00Z",
                        "version": "0.7.0"}))
        M.convert_run(legacy_paper / "forensic_review", "10.1234--x",
                      force=True)
        doc = json.loads((legacy_paper / "forensic_review" /
                          "findings.v2.json").read_text())
        assert doc["legacy"]["pipeline_version"] == "0.7.0"
        assert doc["legacy"]["analysed_at_source"] == "recorded"

    def test_idempotent_via_source_hash(self, legacy_paper):
        run = legacy_paper / "forensic_review"
        assert M.convert_run(run, "10.1234--x")["converted"]
        second = M.convert_run(run, "10.1234--x")
        assert second["skipped"] and "unchanged" in second["reason"]
        # touching the source re-converts
        time.sleep(0.01)
        src = run / "findings.json"
        src.write_text(src.read_text() + " ")
        assert M.convert_run(run, "10.1234--x")["converted"]

    def test_v1_files_are_never_touched(self, legacy_paper):
        src = legacy_paper / "forensic_review" / "findings.json"
        before = src.read_bytes()
        M.convert_run(legacy_paper / "forensic_review", "10.1234--x")
        assert src.read_bytes() == before

    def test_unparseable_source_writes_a_named_skip(self, tmp_path):
        run = tmp_path / "forensic_review"
        run.mkdir()
        (run / "findings.json").write_text("{not json")
        rec = M.convert_run(run, "p")
        assert rec["skipped"]
        skip = json.loads((run / "findings.v2.skipped.json").read_text())
        assert "unparseable" in skip["reason"]


class TestReviewJoins:
    def test_orphaned_verdicts_are_reported_never_silent(self, legacy_paper):
        (legacy_paper / "review.json").write_text(json.dumps({
            "schema_version": "1.1",
            "issues": {"numeric:t1_grim": {"decision": "false_positive"},
                       "numeric:ghost_row": {"decision": "correct_minor"}}}))
        rec = M.convert_paper(legacy_paper)
        assert rec["review_orphans"] == ["numeric:ghost_row"]
