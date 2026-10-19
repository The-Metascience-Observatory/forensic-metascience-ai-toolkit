"""`metascience image-rebuild-exhibits`: the backfill for the unaligned
control. Free, idempotent, and it must leave the sweep stamp alone."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("cv2")
pytest.importorskip("scipy")

from metascience_observatory_image_analysis.image_forensics import review_media as RM  # noqa: E402
from tests.image_fixtures import save_png, shifted_crop_pair  # noqa: E402


def _corpus(tmp_path):
    root = tmp_path / "corpus"
    d = root / "10.1--p"
    a, b, M = shifted_crop_pair()
    save_png(d / "panels" / "xrefA.png", a)
    save_png(d / "panels" / "xrefB.png", b)
    (d / "image_duplication_findings.json").write_text(json.dumps({
        "paper_id": "10.1--p", "duplicate_groups": [
            {"kind": "transformed_match", "duplication_evidence": True,
             "panels": ["d:xrefA", "d:xrefB"], "sentence": "s",
             "match_stats": {"rotation_deg": 0.0, "scale": 1.0, "n_inliers": 80,
                             "inlier_ratio": 0.8, "affine": M,
                             "inlier_box_a": [10, 10, 150, 100], "inlier_box_b": [10, 10, 150, 100]}}],
        "n_duplicate_groups": 1}))
    status = d / "panels" / "image_track_status.json"
    status.write_text(json.dumps({"sweep": {"outcome": "ran", "detector": {"fingerprint": "abc"}}}))
    (root / "10.1--empty").mkdir()
    (root / "10.1--empty" / "image_duplication_findings.json").write_text(json.dumps({"duplicate_groups": []}))
    return root, d, status


def test_it_measures_the_control_and_leaves_the_stamp_alone(tmp_path):
    root, d, status = _corpus(tmp_path)
    before = status.read_bytes()
    out = RM.rebuild_exhibits(root)
    assert out["rebuilt"] == 1 and out["skipped"] == 1 and out["errors"] == 0
    assert out["gates"].get("passed") == 1
    man = json.loads((d / "panels" / "review" / RM.MANIFEST_NAME).read_text())
    assert man["groups"][0]["measurements"]["control"]["note"] == ""
    assert status.read_bytes() == before


def test_it_is_idempotent_and_carries_the_block(tmp_path):
    root, d, _ = _corpus(tmp_path)
    RM.rebuild_exhibits(root)
    first = json.loads((d / "panels" / "review" / RM.MANIFEST_NAME).read_text())
    RM.rebuild_exhibits(root)
    second = json.loads((d / "panels" / "review" / RM.MANIFEST_NAME).read_text())
    assert first["groups"][0]["measurements"]["control"] == second["groups"][0]["measurements"]["control"]


def test_the_cli_verb_exists():
    from typer.testing import CliRunner
    from metascience_agent.cli import app
    r = CliRunner().invoke(app, ["image-rebuild-exhibits", "--help"])
    assert r.exit_code == 0 and "backfill" in r.output
