"""The independent branch must publish evidence, not confuse missing work with clearance."""
from tests.source_paths import IMAGE_ROOT
import asyncio
import inspect
import json
import os
import sys

import pytest

from metascience_agent import agent, parallel
from metascience_observatory_image_analysis.image_forensics import pipeline, screening


import importlib.util
from pathlib import Path

_contract_path = IMAGE_ROOT / "tests/test_pipeline_contracts.py"
_spec = importlib.util.spec_from_file_location("_standalone_pipeline_contracts", _contract_path)
_contracts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_contracts)
detection_record = _contracts.detection_record


def test_default_enabled_and_legacy_detector_aliases():
    from metascience_agent.cli import analyze, batch_cmd
    for fn in (agent.analyze_paper, parallel.analyze_paper_parallel):
        assert inspect.signature(fn).parameters["image_forensics"].default is True
    for fn in (analyze, batch_cmd):
        assert inspect.signature(fn).parameters["image_forensics"].default.default is True
    assert agent._run_image_track is pipeline.run_detection
    assert agent._image_track_command is pipeline.image_track_command


def test_empty_success_is_distinct_from_unresolved_screening(tmp_path, monkeypatch):
    async def detect(*args, **kwargs):
        rec = detection_record()
        rec["output"]["result"] = {"success": True, "duplicate_groups": []}
        return rec
    async def judge(*args, **kwargs):
        pytest.fail("no candidates should spend on screening")
    monkeypatch.setattr(pipeline, "run_detection", detect)
    monkeypatch.setattr(screening, "judge", judge)
    rec = asyncio.run(pipeline.run(tmp_path))
    assert rec["execution_status"] == "completed"
    assert rec["coverage"]["screening"] == {"n_candidates": 0, "n_unresolved": 0}
    assert rec["findings"] == []


@pytest.mark.parametrize("tier,status", [("transformed_match", "incomplete"),
                                         ("intra_panel_clone", "completed")])
def test_unavailable_engine_differs_from_optional_tier(tmp_path, monkeypatch, tier, status):
    async def detect(*args, **kwargs):
        return detection_record(tiers_not_run=[{"tier": tier, "reason": "not run"}])
    async def screen(*args, coverage):
        coverage.update(n_candidates=0, n_unresolved=0)
        return []
    monkeypatch.setattr(pipeline, "run_detection", detect)
    monkeypatch.setattr(screening, "screen_paper_result", screen)
    rec = asyncio.run(pipeline.run(tmp_path))
    assert rec["execution_status"] == status
    assert tier in rec["detail"]


def test_standalone_batch_default_and_opt_out():
    from metascience_agent.batch import build_parser
    parser = build_parser()
    assert parser.parse_args(["papers"]).image_forensics is True
    assert parser.parse_args(["papers", "--no-image-forensics"]).image_forensics is False
    assert parser.parse_args(["papers", "--image-forensics"]).image_forensics is True
