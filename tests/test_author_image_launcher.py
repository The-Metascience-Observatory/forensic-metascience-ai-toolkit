"""The launch boundary must consume the exact screened population."""
from tests.source_paths import IMAGE_ROOT

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from metascience_observatory_image_analysis.image_forensics.complete import snapshot_population

spec = importlib.util.spec_from_file_location(
    "author_image_launcher", IMAGE_ROOT / "examples/run_author_image_corpora.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.fixture
def selection(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "paper").mkdir()
    manifest = corpus / "selection.jsonl"
    manifest.write_text(json.dumps({"rel_dir": "paper", "doi": "10.1000/a"}) + "\n")
    population = tmp_path / "population.json"
    snapshot_population(corpus, [manifest], population, expected_count=1)
    pp = tmp_path / "pubpeer.json"
    pp.write_text(
        json.dumps(
            {
                "10.1000/a": {
                    "status": "no_entry_returned",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        )
    )
    authors = tmp_path / "corpora.json"
    authors.write_text(
        json.dumps(
            [
                {
                    "name": "Author",
                    "analysis_corpus": str(corpus),
                    "population": str(population),
                    "selected": 1,
                    "pubpeer_decisions": str(pp),
                }
            ]
        )
    )
    return authors, manifest, pp


def test_accepted_selection_is_consumed(selection):
    authors, _, _ = selection
    assert len(launcher.validate_populations(authors)) == 1


@pytest.mark.parametrize("status", ["has_comments", "unknown", "failed"])
def test_any_nonnegative_pubpeer_status_refuses_launch(selection, status):
    authors, _, pp = selection
    pp.write_text(json.dumps({"10.1000/a": {"status": status}}))
    with pytest.raises(ValueError, match="PubPeer"):
        launcher.validate_populations(authors)


def test_changed_selection_refuses_launch(selection):
    authors, manifest, _ = selection
    manifest.write_text(json.dumps({"rel_dir": "paper", "doi": "10.1000/another"}))
    with pytest.raises(ValueError, match="Selection changed"):
        launcher.validate_populations(authors)


@pytest.mark.parametrize("days, accepted", [(2, True), (30, True), (-1, False)])
def test_one_pubpeer_check_suffices_but_not_a_future_one(selection, days, accepted):
    """Dan, 2026-09-25: the check is done once, with no freshness window."""
    authors, _, pp = selection
    pp.write_text(
        json.dumps(
            {
                "10.1000/a": {
                    "status": "no_entry_returned",
                    "checked_at": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(),
                }
            }
        )
    )
    if accepted:
        assert launcher.validate_populations(authors)
    else:
        with pytest.raises(ValueError, match="future"):
            launcher.validate_populations(authors)


def test_undated_pubpeer_response_is_not_treated_as_current(selection):
    authors, _, pp = selection
    pp.write_text(json.dumps({"10.1000/a": {"status": "no_entry_returned"}}))
    with pytest.raises(ValueError, match="timestamp"):
        launcher.validate_populations(authors)


def test_duplicate_corpus_cannot_merge_author_runs(selection):
    authors, _, _ = selection
    rows = json.loads(authors.read_text())
    authors.write_text(json.dumps(rows + rows))
    with pytest.raises(ValueError, match="Duplicate author corpus"):
        launcher.validate_populations(authors)


def test_launch_refuses_unfixed_supplement_downloader(monkeypatch):
    from metascience_observatory_image_analysis.image_forensics import complete

    monkeypatch.delattr(complete, "supplement_download_command", raising=False)
    with pytest.raises(ValueError, match="legal-only supplementary"):
        launcher.validate_retrieval_policy()


def test_launch_refuses_ai_retrieval_route(monkeypatch):
    from metascience_observatory_image_analysis.image_forensics import complete

    monkeypatch.setattr(
        complete,
        "supplement_download_command",
        lambda request, corpus: [
            launcher.sys.executable,
            "-m",
            "fetchpdf_grey",
            "--legal-only",
            "--llm-agent-retrieval",
        ],
        raising=False,
    )
    with pytest.raises(ValueError, match="AI routes"):
        launcher.validate_retrieval_policy()


def test_discovered_model_is_explicit_in_child_environment(monkeypatch, tmp_path):
    from metascience_observatory_image_analysis.image_forensics import model_store, panel_detector

    model = tmp_path / 'model.onnx'
    model.write_bytes(b'weights')
    monkeypatch.delenv('METASCIENCE_PANEL_DETECTOR_ONNX', raising=False)
    monkeypatch.setattr(model_store, 'discover_panel_detector_onnx', lambda: (model, 'discovered'))
    monkeypatch.setattr(panel_detector, 'panel_detector_status', lambda path: {'available': True})
    environment, record = launcher.analysis_environment()
    assert environment['METASCIENCE_PANEL_DETECTOR_ONNX'] == str(model.resolve())
    assert record['sha256'] == launcher.hashlib.sha256(b'weights').hexdigest()


def test_ambiguous_panel_model_refuses(monkeypatch):
    from metascience_observatory_image_analysis.image_forensics import model_store

    monkeypatch.setattr(model_store, 'discover_panel_detector_onnx', lambda: (None, 'ambiguous'))
    with pytest.raises(ValueError, match='ambiguous'):
        launcher.analysis_environment()


def test_child_checkpoint_uses_configured_cache(monkeypatch, tmp_path):
    from metascience_observatory_image_analysis.image_forensics import model_store, panel_detector
    from metascience_observatory_image_analysis.image_forensics.search_checkpoint import SearchCheckpoint

    model = tmp_path / 'model.onnx'
    model.write_bytes(b'weights')
    monkeypatch.setattr(model_store, 'discover_panel_detector_onnx', lambda: (model, 'discovered'))
    monkeypatch.setattr(panel_detector, 'panel_detector_status', lambda path: {'available': True})
    root = tmp_path / 'data_drive' / 'cache'
    environment, _ = launcher.analysis_environment(root)
    monkeypatch.setenv('XDG_CACHE_HOME', environment['XDG_CACHE_HOME'])
    checkpoint = SearchCheckpoint('launch_test')
    try:
        database = checkpoint.db.execute('PRAGMA database_list').fetchone()[2]
        assert Path(database) == root / 'metascience/image-search/launch_test.sqlite'
        assert checkpoint.evaluate({'paper': 'test'}, lambda: {'complete': True}) == {'complete': True}
    finally:
        checkpoint.close()



def test_queue_delay_rechecks_at_launch_time(tmp_path, monkeypatch):
    source = IMAGE_ROOT / "examples/run_author_image_corpora.py"
    spec = importlib.util.spec_from_file_location("author_image_launcher", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    initial = datetime(2026, 9, 25, tzinfo=timezone.utc)
    launch = initial + timedelta(days=1, seconds=1)
    clock = iter((initial, launch))

    class Clock:
        @staticmethod
        def now(tz):
            return next(clock)

    checked = []

    def validate(path, *, cohort_time):
        checked.append(cohort_time)
        if cohort_time >= launch:
            raise ValueError("PubPeer check expired while author was queued")
        return [{"name": "fixture"}]

    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(module, "validate_populations", validate)
    monkeypatch.setattr(module, "validate_retrieval_policy", lambda: None)
    monkeypatch.setattr(module, "require_acceptance", lambda *a, **k: {})
    monkeypatch.setattr(module, "analysis_environment", lambda p: ({}, {}))
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: pytest.fail("Expired author launched"))
    monkeypatch.setattr(module.sys, "argv", ["launcher", "--corpora", str(tmp_path / "authors.json"),
                                            "--acceptance", str(tmp_path / "approval.json")])
    with pytest.raises(ValueError, match="expired while author was queued"):
        module.main()
    assert checked == [initial, launch]


def test_redirected_cache_keeps_the_machine_compute_cache(monkeypatch, tmp_path):
    """XDG_CACHE_HOME moves the analysis cache, never the accelerator
    qualification: losing it silently ran CRAFT on CPU for a whole cohort."""
    from metascience_observatory_image_analysis.compute import devices
    monkeypatch.delenv("METASCIENCE_COMPUTE_CACHE", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    expected = str(devices.cache_root())
    monkeypatch.setattr(launcher, "discover_panel_detector_onnx", None, raising=False)
    import metascience_observatory_image_analysis.image_forensics.model_store as store
    import metascience_observatory_image_analysis.image_forensics.panel_detector as pd
    model = tmp_path / "m.onnx"; model.write_bytes(b"x")
    monkeypatch.setattr(store, "discover_panel_detector_onnx", lambda: (model, "fixture"))
    monkeypatch.setattr(pd, "panel_detector_status", lambda m: {"available": True})
    env, _ = launcher.analysis_environment(tmp_path / "analysis_cache")
    assert env["XDG_CACHE_HOME"] == str((tmp_path / "analysis_cache").resolve())
    assert env["METASCIENCE_COMPUTE_CACHE"] == expected


def test_finished_author_notifies_the_review_store(monkeypatch, tmp_path):
    """A cohort's results stayed invisible until its session was notified."""
    from forensic_metascience_ai_toolkit.workbench import notifications
    seen = []
    monkeypatch.setattr(notifications, "published", lambda root: seen.append(root) or {"state": "notified"})
    assert launcher.notify_review(tmp_path) == {"state": "notified"} and seen == [tmp_path]
    monkeypatch.setattr(notifications, "published", lambda root: 1 / 0)
    assert launcher.notify_review(tmp_path)["state"] == "not_notified"


def test_disk_floor_stops_below_and_zero_disables(monkeypatch, tmp_path):
    """2026-09-26: a gate filled /media/dan/data to 0 bytes and crashed 85
    papers; the launcher stops cleanly at a floor instead."""
    monkeypatch.setattr(launcher, "free_gb", lambda path: 12.0)
    assert launcher.below_floor(tmp_path, 20.0) == (True, 12.0)
    assert launcher.below_floor(tmp_path, 10.0) == (False, 12.0)
    assert launcher.below_floor(tmp_path, 0.0) == (False, 12.0)
