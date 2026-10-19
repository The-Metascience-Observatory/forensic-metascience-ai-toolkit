"""The text track's containment contract, pinned as tests.

Same promise as the image track (whose suite this mirrors): the text track
can NEVER sink or distort the paid text review. That decomposes into:

  * the parent-side client `_run_text_track` never raises -- a crashed,
    hung, missing, or garbage-emitting child becomes a status record;
  * no accusatory severity crosses the child->parent boundary, whatever the
    child claims -- the quarantine is enforced a second time at validation;
  * the child's refusal subtypes stay distinct: fingerprints_missing
    (installation) != no_text_source (directory) != text_unreadable (file),
    because collapsing them writes a claim about the authors out of a
    missing data file;
  * the report's note pair tells the truth in both directions (blanket note
    by default; narrow scope note only when the track RAN).
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from metascience_agent import text_track as TT
from metascience_agent.agent import (
    _run_text_track,
    _validate_text_track_output,
)
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ROW = {
    "id": "TORT-1", "location": "body text",
    "technique": "tortured_phrases", "consistent": False,
    "severity": "indeterminate",
    "reproduction": "metascience tortured-phrases /p",
    "explanation": "QUARANTINED signal",
    "severity_before_quarantine": "suspicious",
    "quarantine_reason": "uncalibrated",
}

VALID_OUTPUT = {
    "schema_version": "1.0", "paper_id": "p",
    "status": {"ran": True, "refusal_subtype": None, "wall_seconds": 0.1,
               "detail": "2 distinct guarded fingerprint(s)"},
    "result": {}, "findings_rows": [VALID_ROW],
}

TORTURED_BODY = (
    "We measured outcomes in adults over twelve weeks of follow-up. "
    "Our counterfeit consciousness pipeline used a flag to clamor filter "
    "and bosom peril screening throughout. "
)


def _fake_child(tmp_path: Path, body: str) -> str:
    """A stand-in for the child interpreter: METASCIENCE_TEXT_PYTHON points
    here and the bash script ignores its `-m ...` arguments."""
    script = tmp_path / "fake_python"
    script.write_text("#!/bin/bash\n" + body + "\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


# ---------------------------------------------------------------------------
# Parent-side validation: the second quarantine
# ---------------------------------------------------------------------------


class TestValidation:
    def test_a_valid_object_passes(self):
        status, rows = _validate_text_track_output(
            json.loads(json.dumps(VALID_OUTPUT)))
        assert status["ran"] is True
        assert rows == [VALID_ROW]

    def test_wrong_schema_version_is_rejected(self):
        bad = {**VALID_OUTPUT, "schema_version": "2.0"}
        with pytest.raises(ValueError):
            _validate_text_track_output(bad)

    def test_an_accusatory_severity_cannot_cross_the_boundary(self):
        row = {**VALID_ROW, "severity": "highly_suspicious"}
        bad = {**VALID_OUTPUT, "findings_rows": [row]}
        with pytest.raises(ValueError, match="accusatory"):
            _validate_text_track_output(bad)

    def test_a_wrong_technique_is_rejected(self):
        """The image validator must not accept text rows and vice versa --
        the hard-coded per-track constants are the point of the wrappers."""
        row = {**VALID_ROW, "technique": "image_duplication"}
        bad = {**VALID_OUTPUT, "findings_rows": [row]}
        with pytest.raises(ValueError):
            _validate_text_track_output(bad)

    def test_a_row_missing_required_keys_is_rejected(self):
        row = {k: v for k, v in VALID_ROW.items() if k != "reproduction"}
        bad = {**VALID_OUTPUT, "findings_rows": [row]}
        with pytest.raises(ValueError):
            _validate_text_track_output(bad)


# ---------------------------------------------------------------------------
# Parent-side client: never raises, one fate per failure mode
# ---------------------------------------------------------------------------


class TestClientContainment:
    # Sync tests driving the async client via asyncio.run -- the house
    # pattern; the suite runs with plugin autoload disabled.
    def _run(self, tmp_path, monkeypatch, child_body, timeout_s=10.0):
        import asyncio
        monkeypatch.setenv("METASCIENCE_TEXT_PYTHON",
                           _fake_child(tmp_path, child_body))
        return asyncio.run(_run_text_track(tmp_path, timeout_s=timeout_s))

    def test_valid_output_injects_rows(self, tmp_path, monkeypatch):
        rec = self._run(tmp_path, monkeypatch,
                        f"echo '{json.dumps(VALID_OUTPUT)}'")
        assert rec["ran"] is True
        assert rec["error_subtype"] == "ran_findings"
        assert rec["is_error"] is False
        assert len(rec["findings_rows"]) == 1

    def test_garbage_output_is_track_output_invalid(self, tmp_path, monkeypatch):
        rec = self._run(tmp_path, monkeypatch, "echo 'not json at all'")
        assert rec["error_subtype"] == "track_output_invalid"
        assert rec["is_error"] is True
        assert rec["findings_rows"] == []
        assert "ZERO findings" in rec["detail"]

    def test_an_accusatory_row_invalidates_the_whole_output(self, tmp_path, monkeypatch):
        smuggle = {**VALID_OUTPUT,
                   "findings_rows": [{**VALID_ROW, "severity": "impossible"}]}
        rec = self._run(tmp_path, monkeypatch,
                        f"echo '{json.dumps(smuggle)}'")
        assert rec["error_subtype"] == "track_output_invalid"
        assert rec["findings_rows"] == []

    def test_a_crashing_child_is_track_crashed(self, tmp_path, monkeypatch):
        rec = self._run(tmp_path, monkeypatch,
                        "echo 'boom' >&2; exit 3")
        assert rec["error_subtype"] == "track_crashed"
        assert rec["is_error"] is True
        assert "boom" in rec["detail"]

    def test_a_hung_child_is_killed_and_recorded_as_timeout(self, tmp_path, monkeypatch):
        rec = self._run(tmp_path, monkeypatch, "sleep 30", timeout_s=0.5)
        assert rec["error_subtype"] == "track_timeout"
        assert rec["is_error"] is True
        assert rec["wall_seconds"] < 10
        assert "UNSCREENED" in rec["detail"]

    def test_a_refusing_child_is_not_an_error(self, tmp_path, monkeypatch):
        refusal = {"schema_version": "1.0", "paper_id": "p",
                   "status": {"ran": False,
                              "refusal_subtype": "fingerprints_missing",
                              "wall_seconds": 0.0,
                              "detail": "dictionary absent"},
                   "result": {}, "findings_rows": []}
        rec = self._run(tmp_path, monkeypatch,
                        f"echo '{json.dumps(refusal)}'")
        assert rec["ran"] is False
        assert rec["error_subtype"] == "fingerprints_missing"
        assert rec["is_error"] is False


# ---------------------------------------------------------------------------
# The child: refusal subtypes are distinct facts; rows aggregate per family
# ---------------------------------------------------------------------------


class TestChild:
    def test_empty_directory_is_no_text_source(self, tmp_path):
        out = TT.run_track(tmp_path)
        assert out["status"]["ran"] is False
        assert out["status"]["refusal_subtype"] == "no_text_source"
        assert out["findings_rows"] == []

    def test_unreadable_sources_are_text_unreadable(self, tmp_path):
        (tmp_path / "paper.pdf").write_bytes(b"not a real pdf")
        out = TT.run_track(tmp_path)
        assert out["status"]["refusal_subtype"] == "text_unreadable"

    def test_missing_dictionary_is_fingerprints_missing(self, tmp_path, monkeypatch):
        from metascience_agent.tools import tortured_phrases as tp
        monkeypatch.setattr(
            tp, "load_phrasebook",
            lambda *a, **k: (_ for _ in ()).throw(
                tp.PhrasebookError("data dir gone; property of the "
                                   "installation")))
        (tmp_path / "body.md").write_text("some text", encoding="utf-8")
        out = TT.run_track(tmp_path)
        assert out["status"]["refusal_subtype"] == "fingerprints_missing"
        assert out["findings_rows"] == []

    def test_clean_paper_ran_with_zero_rows(self, tmp_path):
        (tmp_path / "body.md").write_text(
            "We measured artificial intelligence with a signal to noise "
            "ratio and a random forest model.", encoding="utf-8")
        out = TT.run_track(tmp_path)
        assert out["status"]["ran"] is True
        assert out["status"]["refusal_subtype"] is None
        # No `consistent` row: a finite dictionary cannot certify prose.
        assert out["findings_rows"] == []
        assert out["status"]["text_source"] == "body_md"
        assert out["status"]["dictionary_version"]
        assert out["status"]["n_fingerprints_loaded"] > 0

    def test_fired_paper_builds_one_quarantined_row_per_family(self, tmp_path):
        (tmp_path / "body.md").write_text(
            TORTURED_BODY + "As an AI language model, I cannot verify the "
            "raw data provided by the laboratory.", encoding="utf-8")
        out = TT.run_track(tmp_path)
        rows = out["findings_rows"]
        assert [r["inputs"]["family"] for r in rows] == [
            "tortured_phrase", "llm_boilerplate"]
        assert [r["id"] for r in rows] == ["TORT-1", "TORT-2"]
        phrase_row = rows[0]
        assert phrase_row["technique"] == "tortured_phrases"
        assert phrase_row["severity"] == "indeterminate"
        assert phrase_row["severity_before_quarantine"] == "highly_suspicious"
        assert phrase_row["inputs"]["n_distinct_fingerprints"] == 3
        assert "QUARANTINED" in phrase_row["explanation"]
        assert "headline" in phrase_row["explanation"]
        assert phrase_row["reproduction"].startswith(
            "metascience tool run detect_tortured_phrases --json")
        assert phrase_row["inputs"]["dictionary_version"]
        boiler_row = rows[1]
        assert boiler_row["severity_before_quarantine"] == "highly_suspicious"
        assert out["status"]["families_fired"] == [
            "llm_boilerplate", "tortured_phrase"]
        # The parent-side validator must accept exactly what the child emits.
        _validate_text_track_output(out)

    def test_counts_are_distinct_and_repetition_is_one_event(self, tmp_path):
        (tmp_path / "body.md").write_text(
            "bosom peril and bosom peril and bosom peril in adults.",
            encoding="utf-8")
        out = TT.run_track(tmp_path)
        (row,) = out["findings_rows"]
        assert row["inputs"]["n_distinct_fingerprints"] == 1
        assert row["inputs"]["n_total_occurrences"] == 3
        assert row["severity_before_quarantine"] == "indeterminate"

    def test_itemisation_overflow_is_announced_never_silent(self, tmp_path, monkeypatch):
        distinct = [f"phrase{i} variant" for i in range(14)]
        matches = [{
            "family": "tortured_phrase", "subclass": None,
            "matched_text": p, "fingerprint": p, "expected": "real term",
            "sources": ["cabanac2021"], "start": i * 30, "end": i * 30 + 10,
            "context": f"...{p}...", "section": "body", "variant": None,
            "extraction_risk": False, "in_quotation": False,
            "ambiguity": "low", "acronym_present": None,
            "suppressed_by": None,
        } for i, p in enumerate(distinct)]
        from metascience_agent.tools import tortured_phrases as tp_mod
        stub = {
            "success": True, "severity": "indeterminate",
            "severity_before_quarantine": "highly_suspicious",
            "quarantined": True, "quarantine_reason": "uncalibrated",
            "severity_raw_by_family": {"tortured_phrase": "highly_suspicious",
                                       "llm_boilerplate": "consistent"},
            "matches": matches, "n_matches": 14,
            "n_distinct_fingerprints": 14, "n_words_scanned": 500,
            "text_source": "body_md",
            "dictionary": {"version": "t", "sha256": "s",
                           "n_fingerprints": 51},
        }
        monkeypatch.setattr(TT, "run_track", TT.run_track)  # no-op anchor
        monkeypatch.setattr(
            "metascience_agent.tools.tortured_phrases."
            "detect_tortured_phrases", lambda *a, **k: stub)
        (tmp_path / "body.md").write_text("x", encoding="utf-8")
        out = TT.run_track(tmp_path)
        (row,) = out["findings_rows"]
        assert len(row["inputs"]["matches"]) == TT._MAX_MATCHES_PER_ROW
        assert row["inputs"]["n_not_itemised"] == 4
        assert row["inputs"]["n_distinct_fingerprints"] == 14  # never capped
        assert "not itemised" in row["explanation"]

    def test_suppressed_matches_build_no_row(self, tmp_path):
        # The heading must sit in the final two-thirds for the cut to apply.
        (tmp_path / "body.md").write_text(
            "A longer note about methods and results. " * 20
            + "\n\n# References\n\n1. The counterfeit "
            "consciousness approach. 2. The flag to clamor study. 3. On "
            "bosom peril. 4. More citations follow here at length.",
            encoding="utf-8")
        out = TT.run_track(tmp_path)
        assert out["status"]["ran"] is True
        assert out["findings_rows"] == []


# ---------------------------------------------------------------------------
# Report notes: true in both directions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Agent wiring, end to end and offline: the track runs BY DEFAULT during
# analyze_paper, concurrent with the (stubbed) sweep, and its outputs reach
# every report surface -- the editorial prompt, findings.json, report.md's
# scope note, run_meta, and the text_forensics.json artifact.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Prompt discipline: the sweep must not advertise a tool it cannot call
# ---------------------------------------------------------------------------


