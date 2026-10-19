"""Regressions for the real slow paths and write boundaries, no paid calls."""
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import pytest
from metascience_observatory_image_analysis import image_review as ir
from metascience_agent.review_io import write_review
from tests.test_image_review import _paper, _group


def _review_job(args):
    paper, number = args
    write_review(Path(paper), {"issues": {f"image:IMGDUP-{number}": {"decision": "true_issue", "reviewer": "test"}}})


def test_parallel_review_writes_keep_every_decision(tmp_path):
    with ProcessPoolExecutor(max_workers=4, mp_context=__import__("multiprocessing").get_context("spawn")) as pool:
        list(pool.map(_review_job, [(str(tmp_path), i) for i in range(12)]))
    result = json.loads((tmp_path / "review.json").read_text())
    assert len(result["issues"]) == 12


@pytest.mark.parametrize("rel", ["..", "../outside", "/tmp", "a/../../outside", "a\\..\\outside"])
def test_image_write_refuses_escape_before_writing(tmp_path, rel):
    with pytest.raises(ValueError, match="path"):
        ir.write_decision(tmp_path, f"within:{rel}:IMGDUP-1", "true_issue", "test")
    assert not (tmp_path / "review.json").exists()


def test_image_write_refuses_symlink_and_unknown_item(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        ir.write_decision(root, "within:link:IMGDUP-1", "true_issue", "test")
    _paper(root, "paper", [_group()])
    with pytest.raises(ValueError, match="unknown"):
        ir.write_decision(root, "within:paper:IMGDUP-999", "true_issue", "test")
    assert not (outside / "review.json").exists()


def test_nested_paper_identity(tmp_path):
    root = tmp_path / "corpus"; (root / "done").mkdir(parents=True)
    paper = _paper(root / "done", "paper", [_group()])
    item = ir._within_items(paper, False, [], root)[0]
    assert item["id"] == "within:done/paper:IMGDUP-1"
    assert item["paper"]["dir"] == "done/paper"
    assert all(p["paper_dir"] == "done/paper" for p in item["panels"])
    assert all(p["paper_dir"] == "done/paper" for p in item["targets"])


def test_fast_cache_checks_only_published_papers_and_overlays_decisions(tmp_path, monkeypatch):
    paper = _paper(tmp_path, "paper", [_group()])
    item = ir._within_items(paper, False, [], tmp_path)[0]
    from metascience_observatory_image_analysis.image_forensics.screening import POLICY
    obj = {"cache_version": 3, "screening_code": ir._screening_code(), "screening_policy": POLICY,
           "screening_policies": ir._screening_policies(),
           "screening_stamp": None, "paper_sources": {"paper": ir.paper_source_stamp(paper)},
           "checked_at": __import__('time').time(), "items": [item], "notes": []}
    (tmp_path / ir.CACHE).parent.mkdir(exist_ok=True)
    (tmp_path / ir.CACHE).write_text(json.dumps(obj))
    monkeypatch.setattr(ir, "screening_source_stamp", lambda _: pytest.fail("fast read scanned corpus"))
    assert len(ir.read_fast_cache(tmp_path)["items"]) == 1
    write_review(paper, {"issues": {"image:IMGDUP-1": {"decision": "true_issue", "reviewer": "test"}}})
    assert ir.read_fast_cache(tmp_path)["counts"]["decided"] == 1
    assert ir.read_fast_cache(tmp_path)["refresh_needed"] is False
    write_review(paper, {"issues": {"image:IMGDUP-1": {"decision": "false_positive_other", "reviewer": "test"}}})
    assert ir.read_fast_cache(tmp_path)["items"] == []
    (paper / "metadata.json").write_text('{"title":"changed"}')
    result = ir.read_fast_cache(tmp_path)
    assert not result["items"] and result["refresh_needed"]
    assert "withheld" in result["notes"][-1]


def test_nested_context_and_deleted_ledger_invalidate(tmp_path):
    paper = _paper(tmp_path, "paper", [_group()])
    before = ir.paper_source_stamp(paper)
    (paper / "markdown").mkdir()
    f = paper / "markdown/body.md"; f.write_text("context")
    assert ir.paper_source_stamp(paper) != before
    f.unlink()
    assert ir.paper_source_stamp(paper) == before


def test_unreadable_review_is_not_overwritten(tmp_path):
    review = tmp_path / "review.json"
    review.write_text("broken{")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        write_review(tmp_path, {"issues": {}})
    assert review.read_text() == "broken{"


def test_deleted_screening_ledger_refuses_fast_cache(tmp_path):
    from metascience_observatory_image_analysis.image_forensics.screening import POLICY, LEDGER
    ledger = tmp_path / LEDGER
    ledger.parent.mkdir(parents=True)
    ledger.write_text('{"items":{}}')
    cache = {"cache_version": 3, "screening_policy": POLICY,
             "screening_policies": ir._screening_policies(),
             "screening_code": ir._screening_code(), "screening_stamp": ledger.stat().st_mtime_ns,
             "paper_sources": {}, "items": [], "notes": []}
    (tmp_path / ir.CACHE).write_text(json.dumps(cache))
    assert ir.read_fast_cache(tmp_path) is not None
    ledger.unlink()
    assert ir.read_fast_cache(tmp_path) is None


def test_background_refresh_reuses_unchanged_feed(tmp_path, monkeypatch):
    _paper(tmp_path, "paper", [_group()])
    ir.write_cache(tmp_path, materialise=False)
    monkeypatch.setattr(ir, "build_items", lambda *a, **kw: pytest.fail("unchanged corpus was rebuilt"))
    refreshed = ir.refresh_cache(tmp_path)
    assert refreshed["checked_at"] > 0
    assert ir.read_fast_cache(tmp_path)["refresh_needed"] is False


def test_deleted_screening_ledger_refuses_strict_cache(tmp_path):
    from metascience_observatory_image_analysis.image_forensics.screening import LEDGER
    ledger = tmp_path / LEDGER
    ledger.parent.mkdir(parents=True)
    ledger.write_text('{"items":{}}')
    ir.write_cache(tmp_path, materialise=False)
    assert ir.read_cache(tmp_path) is not None
    ledger.unlink()
    assert ir.read_cache(tmp_path) is None


def test_reaccepting_a_rejected_item_reprojects_only_affected_paper(tmp_path, monkeypatch):
    from metascience_observatory_image_analysis.image_forensics.screening import POLICY, LEDGER, input_stamp
    paper = _paper(tmp_path, "paper", [_group()])
    item = ir._within_items(paper, False, [], tmp_path)[0]
    ledger = tmp_path / LEDGER
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"items": {item["id"]: {
        "policy": POLICY, "decision": "issue", "validated": True, "confidence": "high",
        "inputs_stamp": input_stamp(tmp_path, item), "explanation": "different conditions"}}}))
    assert len(ir.write_cache(tmp_path, materialise=False)["items"]) == 1
    monkeypatch.setattr(ir, "build_items", lambda *a, **kw: pytest.fail("decision rebuilt whole corpus"))
    for decision, count in [("false_positive_other", 0), ("true_issue", 1)]:
        write_review(paper, {"issues": {"image:IMGDUP-1": {"decision": decision, "reviewer": "test"}}})
        assert len(ir.refresh_cache(tmp_path)["items"]) == count
        assert len(ir.read_fast_cache(tmp_path)["items"]) == count


def test_rebuild_serializes_concurrent_screening_commit(tmp_path, monkeypatch):
    import threading
    from metascience_observatory_image_analysis.image_forensics.screening import LEDGER, ledger_lock
    _paper(tmp_path, "paper", [_group()])
    started, committed = threading.Event(), threading.Event()
    threads = []
    original = ir.build_items

    def commit():
        started.set()
        with ledger_lock(tmp_path):
            (tmp_path / LEDGER).write_text('{"items":{}}')
            committed.set()

    def build(*args, **kwargs):
        thread = threading.Thread(target=commit)
        threads.append(thread)
        thread.start()
        assert started.wait(2)
        assert not committed.wait(.1), "screening changed during the rebuild"
        return original(*args, **kwargs)

    monkeypatch.setattr(ir, "build_items", build)
    result = ir.write_cache(tmp_path, materialise=False)
    for thread in threads:
        thread.join(2)
    assert committed.is_set()
    assert result["counts"]["items"] == 0


def test_live_screening_revalidates_cache_without_full_rebuild(tmp_path, monkeypatch):
    from metascience_observatory_image_analysis.image_forensics.screening import POLICY, LEDGER, input_stamp
    paper = _paper(tmp_path, "paper", [_group()])
    item = ir._within_items(paper, False, [], tmp_path)[0]
    ledger = tmp_path / LEDGER
    ledger.parent.mkdir(parents=True)
    record = {"policy": POLICY, "decision": "issue", "validated": True,
              "confidence": "high", "inputs_stamp": input_stamp(tmp_path, item),
              "explanation": "different conditions"}
    ledger.write_text(json.dumps({"items": {item["id"]: record}}))
    assert len(ir.write_cache(tmp_path, materialise=False)["items"]) == 1
    record["decision"] = "innocuous"
    ledger.write_text(json.dumps({"items": {item["id"]: record}}))
    monkeypatch.setattr(ir, "source_snapshot", lambda _: pytest.fail("scanned the corpus"))
    result = ir.read_fast_cache(tmp_path)
    assert result["items"] == []
    assert result["refresh_needed"] is True
