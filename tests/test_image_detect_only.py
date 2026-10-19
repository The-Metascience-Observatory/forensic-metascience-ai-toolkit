"""Phase 4: image detection without AI review (the `image_detect` pipeline).

The detector runs alone; its candidates are filed UNSCREENED -- quarantined,
`ai_screening.status: not_run`, never the headline (enforced in
`adjudicate.apply`), never published -- and no AI screening is attempted.
With `ai_screening` on (the default), nothing changes (`pipeline.run`).
"""

import asyncio
import json

import pytest

from forensic_metascience_ai_toolkit import adjudicate, agent
from metascience_observatory_image_analysis import discovery
from forensic_metascience_ai_toolkit import pipeline_config as pc
from forensic_metascience_ai_toolkit.modules.image_analysis.module import NOT_SCREENED
from metascience_observatory_image_analysis.image_forensics import pipeline, screening
from tests.test_image_pipeline import detection_record
from tests.test_image_review import _group, _paper
from tests.test_parallel_pipeline import fakes, paper  # noqa: F401


def _run_detect_only(paper, monkeypatch, record_fn=None):
    _paper(paper.parent, paper.name, [_group()])
    detector_result = json.loads((paper / "image_duplication_findings.json").read_text())

    async def detect(*a, **k):
        rec = detection_record()
        rec["output"]["result"] = detector_result
        return record_fn(rec) if record_fn else rec

    async def no_ai(*a, **k):
        raise AssertionError("AI screening ran in a detection-only pipeline")
    monkeypatch.setattr(pipeline, "run_detection", detect)
    monkeypatch.setattr(screening, "judge", no_ai)
    monkeypatch.setattr(screening, "screen_paper_result", no_ai)
    return asyncio.run(agent.analyze_paper(
        str(paper), mode="parallel", pipeline=pc.load("image_detect")))


def test_the_pipeline_is_detection_alone():
    cfg = pc.load("image_detect")
    assert [m.use for m in cfg.modules] == ["image_analysis"]
    assert cfg.option("image_analysis", "ai_screening") is False
    assert not cfg.complete_review


def test_candidates_are_filed_unscreened_and_named(paper, fakes, monkeypatch):
    r = _run_detect_only(paper, monkeypatch)
    rows = r["findings_v2"]["findings"]
    assert rows and all(row["producer"] == "image_track" for row in rows)
    for row in rows:
        assert row["quarantined"] is True
        assert row["inputs"]["ai_screening"] == NOT_SCREENED
    stage = r["run_meta"]["stages"]["image_forensics"]
    assert stage["execution_status"] == "completed"
    assert stage["coverage"]["screening"] == {"not_run": NOT_SCREENED["reason"]}
    assert any("UNSCREENED" in x for x in r["limitations"])
    assert discovery.run_kind(r["findings_v2"]) == "image_track"
    assert fakes["calls"] == []            # no analyst, no adjudicator


def test_a_detector_coverage_gap_makes_it_incomplete(paper, fakes, monkeypatch):
    def gap(rec):
        rec["output"]["status"]["truncated_by_budget"] = True
        return rec
    r = _run_detect_only(paper, monkeypatch, gap)
    assert r["run_meta"]["stages"]["image_forensics"]["execution_status"] == "incomplete"
    assert any("truncated by budget" in x for x in r["limitations"])


def test_with_ai_screening_the_combined_call_still_runs(paper, fakes, monkeypatch):
    called = {}

    async def combined(*a, **k):
        called["run"] = True
        return pipeline.disabled_record() | {"ran": True, "execution_status": "completed"}
    monkeypatch.setattr(pipeline, "run", combined)
    asyncio.run(agent.analyze_paper(str(paper), mode="parallel",
                                    pipeline=pc.load("image_only")))
    assert called == {"run": True}


class TestHeadline:
    def _row(self, fid, severity, unscreened=False):
        row = {"finding_id": fid, "outcome": "problem", "severity": severity,
               "provisional_severity": severity, "producer": "image_track",
               "technique": "image_duplication", "inputs": {}}
        if unscreened:
            row["quarantined"] = True
            row["inputs"]["ai_screening"] = dict(NOT_SCREENED)
        return row

    def _adjudicate(self, rows, headline):
        out = {"verdicts": [{"finding_id": r["finding_id"], "action": "kept",
                             "severity": r["severity"], "category": "none",
                             "rationale": "kept after reading the paper"} for r in rows],
               "paper": {"verdict": "does_not_reconcile", "paper_severity": 5,
                         "confidence": "medium", "summary": "s" * 200,
                         "headline_finding_id": headline}}
        return adjudicate.apply(rows, out)

    def test_an_unscreened_row_is_never_the_headline(self):
        rows = [self._row("f_a", 3, unscreened=True), self._row("f_b", 2)]
        _, summary = self._adjudicate(rows, "f_a")
        assert summary["headline_finding_id"] == "f_b"
        assert summary["n_headline_fallback"] == 1

    def test_only_unscreened_rows_means_no_headline(self):
        rows = [self._row("f_a", 3, unscreened=True)]
        _, summary = self._adjudicate(rows, "f_a")
        assert summary["headline_finding_id"] is None
