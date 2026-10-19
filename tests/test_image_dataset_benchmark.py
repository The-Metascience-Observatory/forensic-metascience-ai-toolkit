"""Offline controls for dataset joins, honest denominators, and real detection."""
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from typer.testing import CliRunner

from metascience_observatory_image_analysis.image_forensics import dataset_benchmark as bench
from metascience_observatory_image_analysis.image_forensics.dataset_fetch import safe_extract, write_json


def case(target=True, task="internal_duplication"):
    return bench._case("fixture", "one", task, ["image.png"], target=target, method="IDD")


def result(groups=None, eligible=1):
    return {"success": True, "duplicate_groups": groups or [], "n_eligible": eligible,
            "tiers_not_run": [], "n_panels": eligible}


def test_unknown_datasets_and_missing_archives_are_not_clean(tmp_path):
    m = bench.prepare(tmp_path)
    assert not m["cases"]
    assert all(v["status"] == "unavailable" and v["n_cases"] is None for v in m["inventory"].values())
    with pytest.raises(ValueError, match="no cases available"):
        bench.run_benchmark(tmp_path, tmp_path / "runs")


def test_no_annotation_file_never_becomes_negative(tmp_path):
    (tmp_path / "biofors/annotation_files").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        bench.biofors_cases(tmp_path)


def test_biofors_reverse_pair_and_task_negatives(tmp_path):
    ann = tmp_path / "biofors/annotation_files"
    for name, obj in {
        "classification": {"1": {"a.png": "Blot/Gel", "b.png": "Blot/Gel", "c.png": "Blot/Gel"}},
        "edd_test_pairs": {"1": {"Blot/Gel": ["b.png a.png", "a.png b.png", "b.png c.png"]}},
        "edd_gt": {"1": {"a.png b.png": [[[1, 2, 3, 4]], [[5, 6, 7, 8]]]}},
        "idd_gt": {"1": {"a.png": [[1, 2, 3, 4]]}},
        "cstd_gt": {"1": {"b.png": [[2, 3, 4, 5]]}},
    }.items():
        write_json(ann / f"{name}.json", obj)
    rows = bench.biofors_cases(tmp_path)
    pairs = [r for r in rows if r["method"] == "EDD"]
    assert len(pairs) == 2  # unordered pair counted once
    assert pairs[0]["target"] is True
    assert pairs[0]["boxes"] == [[[5, 6, 7, 8]], [[1, 2, 3, 4]]]
    assert pairs[1]["target"] is False
    singles = [r for r in rows if r["method"] == "IDD"]
    assert len(singles) == 3 and sum(r["target"] for r in singles) == 1


def test_wifs_mask_mapping_and_host_lineage(tmp_path):
    base = tmp_path / "wifs2024/data"
    for folder, name in [("automatically_tampered/tampered", "lf_64x64_google_000001_patch_001.png"),
                         ("tampered_blots/cleanup", "google_000001_patch_002_clipdrop-cleanup.png"),
                         ("tampered_blots/gimp", "google_000001_patch_001_gimp_cg.png"),
                         ("tampered_blots/dall_e", "google_000001_patch_003_generated.png")]:
        p = base / folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("L", (64, 64), 127).save(p)
    rows = bench.wifs_cases(tmp_path)
    assert len(rows) == 4
    assert all(r["group"] == "google_000001" for r in rows)
    assert rows[0]["masks"] == ["wifs2024/data/automatically_tampered/mask/mask_google_000001_patch_001.png"]
    assert bench.validate_case(tmp_path, rows[0])["errors"]  # mask absent, never a clean result


def test_mask_size_and_edge_values(tmp_path):
    Image.new("L", (80, 80), 70).save(tmp_path / "image.png")
    Image.new("RGB", (80, 80), (255, 0, 0)).save(tmp_path / "mask.png")
    c = case()
    c["masks"] = ["mask.png"]
    v = bench.validate_case(tmp_path, c)
    assert not v["errors"] and v["notes"]
    Image.new("L", (81, 80), 255).save(tmp_path / "mask.png")
    assert "dimensions" in bench.validate_case(tmp_path, c)["errors"][0]


def test_task_match_context_and_refusal():
    c = case()
    assert bench.assess(c, result([{"kind": "near_duplicate_phash"}]), True)["predicted"] is False
    assert bench.assess(c, result([{"kind": "intra_panel_clone", "duplication_evidence": False}]), True)["predicted"] is False
    assert bench.assess(c, result([{"kind": "intra_panel_clone", "duplication_evidence": True}]), True)["predicted"] is True
    assert bench.assess(c, result(eligible=0), True)["status"] == "excluded"
    assert bench.assess(c, {"success": False, "error": "unreadable"}, True)["status"] == "refused"
    assert bench.assess(c, result(), False)["status"] == "unsupported"
    assert bench.assess(case(task="synthetic_edit"), result(), True)["predicted"] is None


def test_denominators_keep_missing_cases_and_unsupported_separate():
    rows = [{"target": True, "status": "completed", "predicted": True},
            {"target": True, "status": "completed", "predicted": False},
            {"target": True, "status": "input_error", "predicted": None},
            {"target": False, "status": "refused", "predicted": None}]
    s = bench.summarize(rows)
    assert s["confusion"] == {"tp": 1, "fp": 0, "tn": 0, "fn": 1}
    assert s["recall_completed"]["value"] == .5
    assert s["recall_all_selected_positives"]["value"] == pytest.approx(1 / 3)
    assert s["false_positive_rate_completed"]["value"] is None
    s = bench.summarize([{"target": True, "status": "unsupported", "predicted": None}])
    assert s["recall_all_selected_positives"] is None


def test_deterministic_stratified_selection():
    cases = [{**case(i % 2 == 0), "id": str(i)} for i in range(40)]
    a = bench.select_cases(cases, 3, 42)
    assert len(a) == 6
    assert a == bench.select_cases(list(reversed(cases)), 3, 42)
    assert len(bench.select_cases(cases, 0, 42)) == 40


def test_archive_traversal_and_symlink_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../outside.txt", "bad")
    with pytest.raises(ValueError, match="unsafe"):
        safe_extract(archive, tmp_path / "dest")
    assert not (tmp_path / "outside.txt").exists()
    with zipfile.ZipFile(archive, "w") as z:
        m = zipfile.ZipInfo("link")
        m.external_attr = 0o120777 << 16
        z.writestr(m, "../outside.txt")
    with pytest.raises(ValueError, match="symlink"):
        safe_extract(archive, tmp_path / "dest")


def test_worker_detects_known_positive_and_retains_real_output(tmp_path):
    pytest.importorskip("fitz")
    # Textured positive avoids a vacuous check through the production tiny gate.
    gray = np.random.default_rng(42).integers(0, 256, (200, 240), dtype=np.uint8)
    p = tmp_path / "source.png"
    Image.fromarray(gray).save(p)
    spec = {"images": [str(p), str(p)], "variant": "original", "copy_move": False, "segment_montages": False}
    out = tmp_path / "run/detector.json"
    bench.detector_worker(spec, out)
    r = json.loads(out.read_text())
    assert r["success"], r
    assert r["n_duplicate_groups"] >= 1, r["explanation"]
    assert any(g["kind"] in ("same_xref_reused", "identical_stream") for g in r["duplicate_groups"])
    assert bench.assess(case(task="external_duplication"), r, False)["predicted"] is True
    assert (out.parent / "input.pdf").is_file()


def test_missing_input_and_cache_invalidation(tmp_path, monkeypatch):
    c = case()
    config = {"copy_move": True, "segment_montages": False, "timeout": 2}
    row = bench.execute_case(tmp_path, c, "original", config, tmp_path / "runs")
    assert row["status"] == "input_error" and row["predicted"] is None
    Image.new("L", (100, 100), 123).save(tmp_path / "image.png")
    calls = []
    def fake_run(args, **kwargs):
        calls.append(args)
        write_json(Path(args[-1]), result())
        return subprocess_result()
    class subprocess_result:
        returncode = 0
    monkeypatch.setattr(bench.subprocess, "run", fake_run)
    row = bench.execute_case(tmp_path, c, "original", config, tmp_path / "runs")
    assert row["status"] == "completed"
    assert bench.execute_case(tmp_path, c, "original", config, tmp_path / "runs")["resumed"]
    assert len(calls) == 1
    Image.new("L", (100, 100), 124).save(tmp_path / "image.png")
    assert not bench.execute_case(tmp_path, c, "original", config, tmp_path / "runs")["resumed"]
    assert len(calls) == 2


def test_cli_commands_are_reachable(tmp_path):
    from metascience_agent.cli import app
    runner = CliRunner()
    for name in ("image-dataset-fetch", "image-dataset-prepare", "image-dataset-run"):
        r = runner.invoke(app, [name, "--help"])
        assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["image-dataset-prepare", "--root", str(tmp_path)])
    assert r.exit_code == 1 and "unavailable" in r.output


def test_fetch_receipt_records_failure_and_checksum(tmp_path, monkeypatch):
    from metascience_observatory_image_analysis.image_forensics import dataset_fetch as fetch
    source = tmp_path / "downloads/test.zip"
    source.parent.mkdir()
    with zipfile.ZipFile(source, "w") as z:
        z.writestr("upstream/image.txt", "pixels")
    monkeypatch.setattr(fetch, "SOURCES", {"fixture": [{"name": "test.zip", "url": "https://example.invalid/test.zip",
                                                      "unpack": "fixture", "strip_root": True, "budget_bytes": 1}]})
    r = fetch.fetch_datasets(tmp_path, "fixture")
    row = r["files"]["fixture/test.zip"]
    assert row["status"] == "extracted" and len(row["sha256"]) == 64
    assert (tmp_path / "fixture/image.txt").read_text() == "pixels"
    source.write_bytes(b"changed")
    r = fetch.fetch_datasets(tmp_path, "fixture")
    assert r["files"]["fixture/test.zip"]["status"] == "unavailable"
    assert "changed" in r["files"]["fixture/test.zip"]["detail"]


def test_edd_cannot_match_only_within_one_input():
    c = case(task="external_duplication")
    r = result([{"kind": "near_duplicate_phash", "spans_figures": False}], eligible=2)
    assert bench.assess(c, r, True)["predicted"] is False
    r["duplicate_groups"][0]["spans_figures"] = True
    assert bench.assess(c, r, True)["predicted"] is True


def test_development_selection_excludes_unsupported_before_sampling():
    rows = [{**case(i % 2 == 0, task='external_duplication'), 'id': f'external-{i}'} for i in range(12)]
    rows += [{**case(True), 'id': 'clone'}, {**case(True, task='synthetic_edit'), 'id': 'unsupported'}]
    rows += [{**rows[0], 'id': 'bad-adapter', 'adapter_status': 'unrecognised'}]
    selected = bench.select_cases(bench.enabled_cases(rows, False), 2, 0)
    assert len(selected) == 4 and sum(c['target'] for c in selected) == 2
    assert selected == bench.select_cases(bench.enabled_cases(rows[::-1], False), 2, 0)
    assert {c['task'] for c in selected} == {'external_duplication'}
    assert len(bench.enabled_cases(rows, True)) == 13


def test_required_text_incomplete_is_not_a_completed_negative():
    c = case(task='external_duplication')
    r = result(eligible=2)
    r['text_exclusion_coverage'] = {'transformed': {'status': 'incomplete', 'policy': 'enforce'}}
    assessed = bench.assess(c, r, False)
    assert assessed['status'] == 'incomplete' and assessed['predicted'] is None
    assert assessed['coverage']['text_exclusion_coverage'] == r['text_exclusion_coverage']
    # Independent completed identity evidence remains usable.
    r['duplicate_groups'] = [{'kind': 'identical_stream', 'spans_figures': True}]
    assert bench.assess(c, r, False)['predicted'] is True


def test_policy_changes_benchmark_execution_identity(monkeypatch):
    monkeypatch.setenv('METASCIENCE_TEXT_EXCLUSION', 'off')
    off = bench.execution_settings()
    monkeypatch.setenv('METASCIENCE_TEXT_EXCLUSION', 'enforce')
    assert bench.execution_settings() != off


# --------------------------------------------------------------------------
# default_runs_dir: run outputs are measurements, not ground truth, so a
# configured machine writes them outside the dataset root.
# --------------------------------------------------------------------------

def test_default_runs_dir_env_wins(tmp_path, monkeypatch):
    from metascience_observatory_image_analysis.image_forensics.dataset_benchmark import default_runs_dir
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".image_runs").mkdir()
    monkeypatch.setenv("METASCIENCE_IMAGE_RUNS", str(tmp_path / "perf"))
    assert default_runs_dir(tmp_path / "data", "panel_box") == tmp_path / "perf" / "panel_box"


def test_default_runs_dir_image_runs_link(tmp_path, monkeypatch):
    from metascience_observatory_image_analysis.image_forensics.dataset_benchmark import default_runs_dir
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("METASCIENCE_IMAGE_RUNS", raising=False)
    (tmp_path / ".image_runs").mkdir()
    assert default_runs_dir(tmp_path / "data", "dataset_benchmarks") == Path(".image_runs") / "dataset_benchmarks"


def test_default_runs_dir_unconfigured_keeps_historical_layout(tmp_path, monkeypatch):
    from metascience_observatory_image_analysis.image_forensics.dataset_benchmark import default_runs_dir
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("METASCIENCE_IMAGE_RUNS", raising=False)
    root = tmp_path / "data"
    assert default_runs_dir(root, "dataset_benchmarks") == root / "runs"
    assert default_runs_dir(root, "panel_box") == root / "runs" / "panel_box"
    assert default_runs_dir(root, "overlap_bench") == root / "runs" / "overlap_bench"
