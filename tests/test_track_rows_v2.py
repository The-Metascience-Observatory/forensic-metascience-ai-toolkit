"""Dual emission from the deterministic tracks: v2 rows beside untouched v1.

Phase 1 of the findings_v2 overhaul (docs/specs/findings_v2.md). The live
injection path is the money path -- its rows reach the PAID editorial stage --
so the contract under test decomposes as:

  * the v1 builders are BYTE-IDENTICAL to their pre-change output, pinned
    against literal goldens generated from the builders before this change
    (not recomputed through any shared helper, which would be vacuous);
  * the track envelope gains `findings_rows_v2` ONLY when `emit_v2=True` is
    passed -- the default envelope, which the subprocess `__main__` path and
    `agent.py` consume, has no such key at all;
  * every v2 row validates against the FULL `prompts.findings_schema_v2()`
    finding-item schema (`additionalProperties: false` does the policing);
  * the quarantine cap is really applied (`severity9.FIVE_TO_NINE` maps
    `highly_suspicious` ABOVE `QUARANTINE_CAP`, so the test cannot pass
    vacuously);
  * `inputs.group_index` -- the defended join key that addresses the
    detector's OWN list, context groups included -- survives into v2, and
    the overflow remainder row still deliberately lacks it;
  * both placement shapes (tier 1's list, tiers 2-4's dict-by-uid) become
    `page_bbox` anchors, page and bbox verbatim from the placements.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import jsonschema

from metascience_observatory_image_analysis.image_forensics import image_track as IT
from metascience_agent import severity9
from metascience_agent.core import prompts
from metascience_agent import text_track as TT
from metascience_agent.findings_v2 import validate_producer_constraints

FINDING = prompts.findings_schema_v2()["properties"]["findings"]["items"]

PDF = Path("/paper/10.1--x/10.1--x.pdf")
PAPER = Path("/paper/10.1--x")

# ---------------------------------------------------------------------------
# Fixtures: canned track results in the REAL shapes (pinned in
# tests/test_image_track.py / test_text_track.py against the detectors'
# own records -- `panels` is uid strings, `placements` a dict keyed by uid
# for tiers 2-4 and the one panel's LIST for tier 1).
# ---------------------------------------------------------------------------

IMAGE_RESULT = {
    "success": True, "n_panels": 5, "n_eligible": 4,
    "n_duplicate_groups": 2,
    "severity": "indeterminate",
    "severity_before_quarantine": "suspicious",
    "quarantined": True,
    "quarantine_reason": "unvalidated on ground truth",
    "duplicate_groups": [
        # Index 0: CONTEXT (duplication_evidence False) -- both builders must
        # set it aside, and its index must still count in group_index.
        {"kind": "chart_furniture", "duplication_evidence": False,
         "sentence": "shared axis furniture",
         "panels": ["10.1--x.pdf:xref2"],
         "figure_labels": ["Figure 2"],
         "placements": {"10.1--x.pdf:xref2": [
             {"page": 1, "bbox": [1.0, 2.0, 3.0, 4.0]}]}},
        # Index 1: dict-by-uid placements (tiers 2-4); one placement has no
        # bbox, so the anchor for it must omit the key rather than invent one.
        {"kind": "identical_stream", "tier": 2,
         "duplication_evidence": True,
         "sentence": "two panels share identical stream bytes",
         "severity_before_quarantine": "highly_suspicious",
         "panels": ["10.1--x.pdf:xref5", "si.pdf:xref9"],
         "figure_labels": ["Figure 1", "Figure 3"],
         "placements": {
             "10.1--x.pdf:xref5": [{"page": 2,
                                    "bbox": [10.0, 20.0, 110.0, 220.0],
                                    "figure_label": "Figure 1"}],
             "si.pdf:xref9": [{"page": 4, "figure_label": "Figure 3"}],
         }},
        # Index 2: LIST placements (tier 1, the one panel's own list).
        {"kind": "same_xref_reused", "tier": 1,
         "sentence": "one stream placed twice under two captions",
         "severity_before_quarantine": "suspicious",
         "panels": ["10.1--x.pdf:xref7"],
         "figure_labels": ["Figure 4"],
         "placements": [{"page": 5, "bbox": [1.0, 1.0, 2.0, 2.0]},
                        {"page": 6, "bbox": [3.0, 3.0, 4.0, 4.0]}]},
    ],
}


def _match(family, fp, text=None, suppressed=None):
    return {"family": family, "subclass": None,
            "matched_text": text or fp, "fingerprint": fp,
            "expected": "real term", "sources": ["cabanac2021"],
            "start": 0, "end": 10, "context": f"...{text or fp}...",
            "section": "body", "variant": None,
            "extraction_risk": False, "in_quotation": False,
            "ambiguity": "low", "acronym_present": None,
            "suppressed_by": suppressed}


TEXT_RESULT = {
    "success": True, "severity": "indeterminate",
    "severity_before_quarantine": "highly_suspicious",
    "quarantined": True, "quarantine_reason": "seed dictionary",
    "severity_raw_by_family": {"tortured_phrase": "highly_suspicious",
                               "llm_boilerplate": "suspicious"},
    "matches": [
        # The matched TEXT differs from the fingerprint in case: the anchor
        # must quote the paper, not the dictionary.
        _match("tortured_phrase", "counterfeit consciousness",
               text="Counterfeit Consciousness"),
        _match("tortured_phrase", "counterfeit consciousness",
               text="counterfeit consciousness"),
        _match("tortured_phrase", "bosom peril"),
        _match("llm_boilerplate", "as an ai language model",
               text="As an AI language model"),
        # Suppressed: indicts the cited paper, must reach no row and no anchor.
        _match("tortured_phrase", "flag to clamor",
               suppressed="references_section"),
    ],
    "n_matches": 4, "n_distinct_fingerprints": 3, "n_words_scanned": 500,
    "text_source": "body_md",
    "dictionary": {"version": "2026-08-17", "sha256": "abc123",
                   "n_fingerprints": 51},
}

# ---------------------------------------------------------------------------
# Pre-change goldens: the LITERAL output of the v1 builders on the fixtures
# above, captured before `_findings_rows_v2` / `_family_rows_v2` existed.
# Byte-for-byte, not recomputed -- a golden that shares code with the thing
# it pins would pass whatever both did.
# ---------------------------------------------------------------------------

IMAGE_GOLDEN_V1 = [
    {
        "id": "IMGDUP-1",
        "location": "Figure 1 / Figure 3 (page 2, 4)",
        "technique": "image_duplication",
        "consistent": False,
        "severity": "indeterminate",
        "reproduction": "metascience image-analysis /paper/10.1--x/10.1--x.pdf --paper-dir /paper/10.1--x",
        "inputs": {
            "pdf_path": "/paper/10.1--x/10.1--x.pdf",
            "kind": "identical_stream",
            "panel_ids": ["10.1--x.pdf:xref5", "si.pdf:xref9"],
            "group_index": 1,
        },
        "explanation": "two panels share identical stream bytes QUARANTINED: this image check is not yet calibrated against ground truth, so it may not accuse -- the uncalibrated signal was 'highly_suspicious'. unvalidated on ground truth Report this as an unvalidated signal for human side-by-side review of the named panels, never as a finding of record, and never in the headline.",
        "severity_before_quarantine": "highly_suspicious",
        "quarantine_reason": "unvalidated on ground truth",
    },
    {
        "id": "IMGDUP-2",
        "location": "Figure 4 (page 5, 6)",
        "technique": "image_duplication",
        "consistent": False,
        "severity": "indeterminate",
        "reproduction": "metascience image-analysis /paper/10.1--x/10.1--x.pdf --paper-dir /paper/10.1--x",
        "inputs": {
            "pdf_path": "/paper/10.1--x/10.1--x.pdf",
            "kind": "same_xref_reused",
            "panel_ids": ["10.1--x.pdf:xref7"],
            "group_index": 2,
        },
        "explanation": "one stream placed twice under two captions QUARANTINED: this image check is not yet calibrated against ground truth, so it may not accuse -- the uncalibrated signal was 'suspicious'. unvalidated on ground truth Report this as an unvalidated signal for human side-by-side review of the named panels, never as a finding of record, and never in the headline.",
        "severity_before_quarantine": "suspicious",
        "quarantine_reason": "unvalidated on ground truth",
    },
]

TEXT_GOLDEN_V1 = [
    {
        "id": "TORT-1",
        "location": "body text (offsets in text_forensics.json)",
        "technique": "tortured_phrases",
        "consistent": False,
        "severity": "indeterminate",
        "reproduction": "metascience tortured-phrases /paper/10.1--x",
        "inputs": {
            "family": "tortured_phrase",
            "n_distinct_fingerprints": 2,
            "n_total_occurrences": 3,
            "n_not_itemised": 0,
            "dictionary_version": "2026-08-17",
            "dictionary_sha256": "abc123",
            "matches": [
                {"matched": "counterfeit consciousness",
                 "expected": "real term", "count": 2,
                 "example_context": "...Counterfeit Consciousness...",
                 "in_quotation": False, "extraction_risk": False},
                {"matched": "bosom peril",
                 "expected": "real term", "count": 1,
                 "example_context": "...bosom peril...",
                 "in_quotation": False, "extraction_risk": False},
            ],
        },
        "explanation": "2 distinct tortured phrase(s) (3 occurrence(s)) survived the guards, e.g. 'counterfeit consciousness' for 'real term'; 'bosom peril' for 'real term'. QUARANTINED: this screen's false-positive classes are not yet measured on this pipeline, so it may not accuse -- the pre-registered grade was 'highly_suspicious'. seed dictionary Report as an unvalidated signal for human review of the quoted spans, never as a finding of record, and never in the headline.",
        "severity_before_quarantine": "highly_suspicious",
        "quarantine_reason": "seed dictionary",
    },
    {
        "id": "TORT-2",
        "location": "body text (offsets in text_forensics.json)",
        "technique": "tortured_phrases",
        "consistent": False,
        "severity": "indeterminate",
        "reproduction": "metascience tortured-phrases /paper/10.1--x",
        "inputs": {
            "family": "llm_boilerplate",
            "n_distinct_fingerprints": 1,
            "n_total_occurrences": 1,
            "n_not_itemised": 0,
            "dictionary_version": "2026-08-17",
            "dictionary_sha256": "abc123",
            "matches": [
                {"matched": "as an ai language model",
                 "expected": "real term", "count": 1,
                 "example_context": "...As an AI language model...",
                 "in_quotation": False, "extraction_risk": False},
            ],
        },
        "explanation": "1 distinct LLM-boilerplate string(s) (1 occurrence(s)) survived the guards, e.g. 'as an ai language model' for 'real term'. QUARANTINED: this screen's false-positive classes are not yet measured on this pipeline, so it may not accuse -- the pre-registered grade was 'suspicious'. seed dictionary Report as an unvalidated signal for human review of the quoted spans, never as a finding of record, and never in the headline.",
        "severity_before_quarantine": "suspicious",
        "quarantine_reason": "seed dictionary",
    },
]


def _validate_all(rows):
    for row in rows:
        jsonschema.validate(row, FINDING)


# ---------------------------------------------------------------------------
# v1 stays byte-identical
# ---------------------------------------------------------------------------


class TestV1Unchanged:
    def test_image_v1_rows_match_the_pre_change_golden(self):
        assert IT._findings_rows(copy.deepcopy(IMAGE_RESULT), PDF, PAPER) \
            == IMAGE_GOLDEN_V1

    def test_text_v1_rows_match_the_pre_change_golden(self):
        assert TT._family_rows(copy.deepcopy(TEXT_RESULT), PAPER) \
            == TEXT_GOLDEN_V1

    def test_the_v2_builders_do_not_mutate_the_result(self):
        """The v1 rows are built from the same result object; a v2 builder
        that edits it in passing would change v1 output without any v1 code
        changing -- drift with no fingerprints."""
        img = copy.deepcopy(IMAGE_RESULT)
        IT._findings_rows_v2(img, PDF, PAPER)
        assert img == IMAGE_RESULT
        txt = copy.deepcopy(TEXT_RESULT)
        TT._family_rows_v2(txt, PAPER)
        assert txt == TEXT_RESULT

    def test_v2_rows_do_not_share_the_inputs_dict_with_v1(self):
        """Both row sets ride one envelope; a shared inner dict would let a
        later v2 annotation silently rewrite the v1 row stage 2 reads."""
        result = copy.deepcopy(IMAGE_RESULT)
        v1 = IT._findings_rows(result, PDF, PAPER)
        v2 = IT._findings_rows_v2(result, PDF, PAPER)
        v2[0]["inputs"]["group_index"] = 999
        assert v1[0]["inputs"]["group_index"] == 1


# ---------------------------------------------------------------------------
# Image track v2 rows
# ---------------------------------------------------------------------------


class TestImageRowsV2:
    def rows(self, result=None):
        return IT._findings_rows_v2(
            copy.deepcopy(result or IMAGE_RESULT), PDF, PAPER)

    def test_every_row_validates_against_the_full_v2_schema(self):
        _validate_all(self.rows())

    def test_identity_producer_technique_slug(self):
        rows = self.rows()
        assert [r["slug"] for r in rows] == ["IMGDUP-1", "IMGDUP-2"]
        assert all(r["producer"] == "image_track" for r in rows)
        # Registry-exact name (spec 1.2), not v1's `image_duplication` label.
        assert all(r["technique"] == "analyze_paper_images" for r in rows)
        assert all(r["computed_by"] == "deterministic_track" for r in rows)
        assert all(r["outcome"] == "problem" for r in rows)

    def test_group_index_is_the_detectors_own_index(self):
        """Context group 0 is filtered but still COUNTED: the join key
        addresses `duplicate_groups` as the detector wrote it."""
        rows = self.rows()
        assert [r["inputs"]["group_index"] for r in rows] == [1, 2]

    def test_finding_ids_are_assigned_distinct_and_deterministic(self):
        rows = self.rows()
        ids = [r["finding_id"] for r in rows]
        assert all(re.fullmatch(r"f_[0-9a-f]{16}", i) for i in ids)
        assert len(set(ids)) == len(ids)
        assert all(r["finding_id_hasher"] for r in rows)
        assert [r["finding_id"] for r in self.rows()] == ids  # stable re-run

    def test_quarantine_cap_is_applied_and_not_vacuously(self):
        rows = self.rows()
        # The raw signal maps ABOVE the cap, so a pass here proves the clamp.
        assert severity9.FIVE_TO_NINE["highly_suspicious"] \
            > severity9.QUARANTINE_CAP
        assert rows[0]["provisional_severity"] == severity9.QUARANTINE_CAP
        assert rows[1]["provisional_severity"] == \
            severity9.FIVE_TO_NINE["suspicious"]
        assert all(r["quarantined"] is True for r in rows)
        assert all(r["quarantine_reason"] for r in rows)
        assert all(r["severity_is_provisional"] is True for r in rows)
        assert all(r["impossible"] is False for r in rows)

    def test_tool_verdict_carries_the_raw_signal(self):
        rows = self.rows()
        assert rows[0]["tool_verdict"] == {
            "severity": "indeterminate", "tool": "analyze_paper_images",
            "validated": True, "quarantined_raw": "highly_suspicious"}
        assert rows[1]["tool_verdict"]["quarantined_raw"] == "suspicious"

    def test_dict_shaped_placements_become_per_uid_anchors(self):
        row = self.rows()[0]
        assert row["anchors"] == [
            {"kind": "page_bbox", "file": "10.1--x.pdf", "doc": "10.1--x.pdf",
             "page": 2, "bbox": [10.0, 20.0, 110.0, 220.0],
             "panel_id": "10.1--x.pdf:xref5"},
            # No bbox in the placement -> no bbox key, never an invented one.
            {"kind": "page_bbox", "file": "si.pdf", "doc": "si.pdf",
             "page": 4, "panel_id": "si.pdf:xref9"},
        ]

    def test_list_shaped_placements_attribute_to_the_one_panel(self):
        row = self.rows()[1]
        assert [a["page"] for a in row["anchors"]] == [5, 6]
        assert all(a["panel_id"] == "10.1--x.pdf:xref7"
                   for a in row["anchors"])
        assert all(a["file"] == "10.1--x.pdf" for a in row["anchors"])

    def test_titles_and_descriptions_respect_the_hard_bounds(self):
        for row in self.rows():
            assert 8 <= len(row["title"]) <= 90
            assert 20 <= len(row["description"]) <= 700
            # The description is the v1 explanation prose, not new writing.
            assert "QUARANTINED" in row["description"]

    def test_structural_invariants_hold(self):
        assert validate_producer_constraints(self.rows()) == []

    def test_overflow_keeps_the_remainder_row_without_a_join_key(self):
        context = {"kind": "chart_furniture", "duplication_evidence": False,
                   "sentence": "context", "panels": []}
        groups = [context] + [
            {"kind": "identical_stream", "sentence": f"group {i}",
             "severity_before_quarantine": "suspicious", "panels": []}
            for i in range(15)]
        result = {"success": True, "n_panels": 40, "n_eligible": 40,
                  "n_duplicate_groups": 15, "duplicate_groups": groups,
                  "quarantine_reason": "unvalidated"}
        rows = IT._findings_rows_v2(result, PDF, PAPER)
        assert len(rows) == IT._MAX_FINDINGS_ROWS
        # Itemised rows address the detector's list, context offset included.
        assert rows[0]["inputs"]["group_index"] == 1
        remainder = rows[-1]
        assert remainder["slug"] == f"IMGDUP-{IT._MAX_FINDINGS_ROWS}"
        assert "group_index" not in remainder["inputs"]
        assert remainder["inputs"]["remainder"] is True
        assert remainder["anchors"] == []
        assert remainder["anchor_problem"]  # named absence, never silent
        _validate_all(rows)

    def test_context_only_groups_build_no_rows(self):
        result = {"success": True,
                  "duplicate_groups": [{"kind": "chart_furniture",
                                        "duplication_evidence": False,
                                        "sentence": "context", "panels": []}],
                  "quarantine_reason": "unvalidated"}
        assert IT._findings_rows_v2(result, PDF, PAPER) == []

    def test_non_accusatory_raw_is_record_keeping_with_a_named_reason(self):
        """Nothing withheld: no FIVE_TO_NINE mapping exists, so the row is
        pinned below ACCUSATORY_MIN, and the empty detector reason is
        replaced -- a bare cap with no reason is forbidden."""
        result = {"success": True, "quarantine_reason": "",
                  "duplicate_groups": [
                      {"kind": "layout_ghost",
                       "sentence": "one panel is placed off-page",
                       "panels": ["10.1--x.pdf:xref3"], "placements": []}]}
        (row,) = IT._findings_rows_v2(result, PDF, PAPER)
        assert row["provisional_severity"] == 2 < severity9.ACCUSATORY_MIN
        assert row["tool_verdict"]["quarantined_raw"] is None
        assert row["quarantine_reason"] == IT._V2_IMAGE_QUARANTINE_REASON
        assert "nothing was withheld" in row["description"]
        jsonschema.validate(row, FINDING)


# ---------------------------------------------------------------------------
# Text track v2 rows
# ---------------------------------------------------------------------------


class TestTextRowsV2:
    def rows(self, result=None):
        return TT._family_rows_v2(copy.deepcopy(result or TEXT_RESULT), PAPER)

    def test_every_row_validates_against_the_full_v2_schema(self):
        _validate_all(self.rows())

    def test_identity_producer_technique_slug(self):
        rows = self.rows()
        assert [r["slug"] for r in rows] == ["TORT-1", "TORT-2"]
        assert all(r["producer"] == "text_track" for r in rows)
        # Registry-exact name (spec 1.2), not v1's `tortured_phrases` label.
        assert all(r["technique"] == "detect_tortured_phrases" for r in rows)
        assert all(r["computed_by"] == "deterministic_track" for r in rows)
        assert all(r["outcome"] == "problem" for r in rows)
        assert [r["inputs"]["family"] for r in rows] == [
            "tortured_phrase", "llm_boilerplate"]

    def test_anchors_quote_the_matched_text_per_itemised_fingerprint(self):
        """One quote anchor per itemised distinct fingerprint, carrying the
        span AS MATCHED in the paper (case and all), not the dictionary
        entry -- an anchor quoting the dictionary may fail to locate."""
        rows = self.rows()
        assert rows[0]["anchors"] == [
            {"kind": "quote", "quote": "Counterfeit Consciousness"},
            {"kind": "quote", "quote": "bosom peril"},
        ]
        assert rows[1]["anchors"] == [
            {"kind": "quote", "quote": "As an AI language model"},
        ]

    def test_suppressed_matches_anchor_nothing(self):
        for row in self.rows():
            assert all("flag to clamor" not in a["quote"]
                       for a in row["anchors"])

    def test_quarantine_cap_is_applied_and_not_vacuously(self):
        rows = self.rows()
        assert severity9.FIVE_TO_NINE["highly_suspicious"] \
            > severity9.QUARANTINE_CAP
        assert rows[0]["provisional_severity"] == severity9.QUARANTINE_CAP
        assert rows[1]["provisional_severity"] == \
            severity9.FIVE_TO_NINE["suspicious"]
        assert all(r["quarantined"] is True for r in rows)
        assert all(r["quarantine_reason"] == "seed dictionary" for r in rows)

    def test_tool_verdict_carries_the_pre_registered_grade(self):
        rows = self.rows()
        assert rows[0]["tool_verdict"] == {
            "severity": "indeterminate", "tool": "detect_tortured_phrases",
            "validated": True, "quarantined_raw": "highly_suspicious"}
        assert rows[1]["tool_verdict"]["quarantined_raw"] == "suspicious"

    def test_finding_ids_are_assigned_distinct_and_deterministic(self):
        rows = self.rows()
        ids = [r["finding_id"] for r in rows]
        assert all(re.fullmatch(r"f_[0-9a-f]{16}", i) for i in ids)
        assert len(set(ids)) == len(ids)
        assert [r["finding_id"] for r in self.rows()] == ids

    def test_titles_and_descriptions_respect_the_hard_bounds(self):
        for row in self.rows():
            assert 8 <= len(row["title"]) <= 90
            assert 20 <= len(row["description"]) <= 700
            assert "QUARANTINED" in row["description"]

    def test_structural_invariants_hold(self):
        assert validate_producer_constraints(self.rows()) == []

    def test_non_accusatory_grade_is_record_keeping(self):
        result = copy.deepcopy(TEXT_RESULT)
        result["severity_raw_by_family"] = {
            "tortured_phrase": "indeterminate",
            "llm_boilerplate": "indeterminate"}
        rows = TT._family_rows_v2(result, PAPER)
        assert all(r["provisional_severity"] == 2 for r in rows)
        # `indeterminate` IS a 5-enum value, so it survives as the raw grade.
        assert all(r["tool_verdict"]["quarantined_raw"] == "indeterminate"
                   for r in rows)
        _validate_all(rows)


# ---------------------------------------------------------------------------
# Envelope discipline: the key exists ONLY under emit_v2
# ---------------------------------------------------------------------------


class TestImageEnvelope:
    def _run(self, tmp_path, monkeypatch, **kwargs):
        paper = tmp_path / "10.1--x"
        paper.mkdir(exist_ok=True)
        (paper / "10.1--x.pdf").write_bytes(b"%PDF-1.4 stub")
        from metascience_observatory_image_analysis.image_forensics import panels
        from metascience_observatory_image_analysis.image_forensics import image_analysis as IA
        monkeypatch.setattr(panels, "panel_engine_status",
                            lambda *a, **k: {"available": True,
                                     "transformed_tier_available": True,
                                     "engines": ["stub"]})
        monkeypatch.setattr(IA, "analyze_paper_images",
                            lambda *a, **k: copy.deepcopy(IMAGE_RESULT))
        monkeypatch.setattr(IT, "_write_figure_captions",
                            lambda *a, **k: None)
        return IT.run_track(paper, **kwargs)

    def test_default_envelope_has_no_v2_key(self, tmp_path, monkeypatch):
        out = self._run(tmp_path, monkeypatch)
        assert "findings_rows_v2" not in out
        assert len(out["findings_rows"]) == 2

    def test_emit_v2_false_is_byte_identical_to_the_default(
            self, tmp_path, monkeypatch):
        default = self._run(tmp_path, monkeypatch)
        explicit = self._run(tmp_path, monkeypatch, emit_v2=False)
        default["status"].pop("wall_seconds")
        explicit["status"].pop("wall_seconds")
        assert default == explicit

    def test_emit_v2_adds_rows_beside_untouched_v1(self, tmp_path, monkeypatch):
        default = self._run(tmp_path, monkeypatch)
        out = self._run(tmp_path, monkeypatch, emit_v2=True)
        assert out["findings_rows"] == default["findings_rows"]  # dual, not instead
        rows = out["findings_rows_v2"]
        assert len(rows) == 2
        _validate_all(rows)
        # JSON-serializable end to end: this envelope crosses a pipe.
        json.dumps(out)

    def test_a_refusal_under_emit_v2_carries_an_empty_list(
            self, tmp_path, monkeypatch):
        from metascience_observatory_image_analysis.image_forensics import panels
        monkeypatch.setattr(panels, "panel_engine_status",
                            lambda *a, **k: {"available": True,
                                     "transformed_tier_available": True,
                                     "engines": ["stub"]})
        paper = tmp_path / "10.1--empty"
        paper.mkdir()
        out = IT.run_track(paper, emit_v2=True)  # no PDF -> refusal
        assert out["status"]["ran"] is False
        assert out["findings_rows_v2"] == []
        # And WITHOUT emit_v2 the refusal envelope has no such key.
        assert "findings_rows_v2" not in IT.run_track(paper)


class TestTextEnvelope:
    def _run(self, tmp_path, monkeypatch, result=None, **kwargs):
        paper = tmp_path / "10.1--x"
        paper.mkdir(exist_ok=True)
        monkeypatch.setattr(
            "metascience_agent.tools.tortured_phrases."
            "detect_tortured_phrases",
            lambda *a, **k: copy.deepcopy(result or TEXT_RESULT))
        return TT.run_track(paper, **kwargs)

    def test_default_envelope_has_no_v2_key(self, tmp_path, monkeypatch):
        out = self._run(tmp_path, monkeypatch)
        assert "findings_rows_v2" not in out
        assert len(out["findings_rows"]) == 2

    def test_emit_v2_false_is_byte_identical_to_the_default(
            self, tmp_path, monkeypatch):
        default = self._run(tmp_path, monkeypatch)
        explicit = self._run(tmp_path, monkeypatch, emit_v2=False)
        default["status"].pop("wall_seconds")
        explicit["status"].pop("wall_seconds")
        assert default == explicit

    def test_emit_v2_adds_rows_beside_untouched_v1(self, tmp_path, monkeypatch):
        default = self._run(tmp_path, monkeypatch)
        out = self._run(tmp_path, monkeypatch, emit_v2=True)
        assert out["findings_rows"] == default["findings_rows"]
        rows = out["findings_rows_v2"]
        assert len(rows) == 2
        _validate_all(rows)
        json.dumps(out)

    def test_a_refusal_under_emit_v2_carries_an_empty_list(
            self, tmp_path, monkeypatch):
        refusal = {"success": False, "refusal": "no_text_source",
                   "error": "no text-bearing file", "dictionary": {}}
        out = self._run(tmp_path, monkeypatch, result=refusal, emit_v2=True)
        assert out["status"]["ran"] is False
        assert out["findings_rows_v2"] == []
        out2 = self._run(tmp_path, monkeypatch, result=refusal)
        assert "findings_rows_v2" not in out2
