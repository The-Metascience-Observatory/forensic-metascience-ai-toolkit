from pathlib import Path
import json
import pytest
from metascience_agent.analysis_runs import Archive


@pytest.mark.usefixtures("image_package")
def test_isolated_workspace_keeps_every_image_source_directory(tmp_path):
    from metascience_agent.analysis_runs import workspace
    paper = tmp_path/'paper'
    paper.mkdir()
    expected = ('pmc_figures', 'publisher_figures', 'paper_figures', 'paper_images',
                'supplementary', 'supplement', 'supplemental', 'supplementary_material', 'si')
    for directory in (*expected, 'panels', 'figures'):
        path = paper/directory
        path.mkdir()
        (path/'source.png').write_bytes(directory.encode())
    with workspace(paper) as (archive, pending, working):
        for directory in expected:
            assert (working/directory/'source.png').read_bytes() == directory.encode()
        assert not (working/'panels').exists()
        assert not (working/'figures').exists()
        archive.seal(pending, status='completed')


def run(a, eid, rid, *, paper="p", at="2026-09-01", state="completed", items=None):
    r = {
        "id": rid,
        "execution_id": eid,
        "component": "image_forensics",
        "paper": paper,
        "started_at": at,
        "provenance": {"version": "1.0"},
    }
    items = items or []
    for i in items:
        i.update(run_id=rid, execution_id=eid, provenance=r["provenance"])
    return a.seal(r, items, status=state, completed_at=at)


def item():
    return {
        "id": "within:p:IMGDUP-1",
        "paper": {"dir": "p"},
        "papers": [{"dir": "p"}],
        "kind": "within",
        "rank": {"score": 1},
        "panels": [],
    }


def execution(a, eid):
    return a.execution(
        "image_forensics",
        execution_id=eid,
        components=["image_forensics"],
        started_at="2026-09-01",
        status="completed",
    )


def test_same_version_distinct_runs_and_scoped_decisions(tmp_path):
    a = Archive(tmp_path)
    execution(a, "e1")
    execution(a, "e2")
    run(a, "e1", "r1", items=[item()])
    run(a, "e2", "r2", at="2026-09-02", items=[item()])
    a.decide("r1", item()["id"], "true_issue", "Reviewer")
    assert len(a.catalog("image_forensics")) == 2
    assert a.feed("e1")["items"][0]["decision"]["decision"] == "true_issue"
    assert a.feed("e2")["items"][0]["decision"] is None
    assert a.feed()["items"][0]["run_id"] == "r2"


def test_failure_does_not_fall_back_or_erase_history(tmp_path):
    a = Archive(tmp_path)
    execution(a, "e1")
    execution(a, "e2")
    run(a, "e1", "r1", items=[item()])
    run(a, "e2", "r2", at="2026-09-02", state="failed")
    assert not a.feed()["items"]
    assert len(a.feed("e1")["items"]) == 1
    assert a.feed()["coverage"]["states"]["failed"] == 1


def test_artifact_is_a_copy_and_owned_by_run(tmp_path):
    a = Archive(tmp_path)
    execution(a, "e1")
    paper = tmp_path / "p"
    paper.mkdir()
    source = paper / "a.png"
    source.write_bytes(b"old pixels")
    r = {
        "id": "r1",
        "execution_id": "e1",
        "paper": "p",
        "component": "image_forensics",
        "provenance": {},
    }
    i = item()
    i["panels"] = [{"paper_dir": "p", "image": "a.png"}]
    frozen, arts = a.freeze_items(r, [i])
    a.seal(r, frozen, artifacts=arts)
    source.write_bytes(b"new pixels")
    aid = next(iter(arts))
    path, _ = a.artifact("r1", aid)
    assert path.read_bytes() == b"old pixels"
    with pytest.raises(ValueError):
        a.artifact("r1", "missing")
    with pytest.raises(ValueError):
        a.artifact("../r1", aid)


def test_shared_head_freezes_only_once(tmp_path):
    a = Archive(tmp_path)
    (tmp_path / "p").mkdir()
    (tmp_path / "p/a.pdf").write_bytes(b"pdf")
    head = {"dir": "p", "pdf": "a.pdf"}
    i = item()
    i.update(paper=head, papers=[head])
    r = {
        "id": "r1",
        "execution_id": "e1",
        "paper": "p",
        "component": "image_forensics",
        "provenance": {},
    }
    frozen, arts = a.freeze_items(r, [i])
    assert frozen[0]["paper"]["pdf"].startswith("__runs/r1/")


def test_revision_inherits_exact_archived_panel_when_live_path_moved(tmp_path):
    a = Archive(tmp_path)
    execution(a, "e1")
    paper = tmp_path / "p"
    paper.mkdir()
    image = paper / "panel.png"
    image.write_bytes(b"preserved pixels")
    first = {
        "id": "r1", "execution_id": "e1", "paper": "p",
        "component": "image_forensics", "provenance": {},
    }
    original = item()
    original["panels"] = [
        {"paper_dir": "p", "uid": "p.pdf:xref1", "image": "panel.png"}
    ]
    frozen, artifacts = a.freeze_items(first, [original])
    a.seal(first, frozen, artifacts=artifacts)
    image.unlink()

    revision = {
        "id": "r2", "execution_id": "e1", "paper": "p",
        "component": "image_forensics", "provenance": {}, "revision_of": "r1",
    }
    revised = item()
    revised["panels"] = [
        {"paper_dir": "p", "uid": "p.pdf:xref1", "image": "moved/panel.png",
         "image_unavailable_reason": "stale producer path"}
    ]
    refrozen, next_artifacts = a.freeze_items(revision, [revised])
    inherited = refrozen[0]["panels"][0]["image"]

    assert inherited.startswith("__runs/r2/")
    assert "image_unavailable_reason" not in refrozen[0]["panels"][0]
    assert next_artifacts[inherited.rsplit("/", 1)[-1]]["sha256"] \
        == next(iter(artifacts.values()))["sha256"]

def test_feed_projects_exact_ancestor_media_for_an_already_sealed_bad_revision(tmp_path):
    a = Archive(tmp_path)
    execution(a, "e1")
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "panel.png").write_bytes(b"preserved pixels")
    first = {
        "id": "r1", "execution_id": "e1", "paper": "p",
        "component": "image_forensics", "provenance": {},
    }
    original = item()
    original["panels"] = [
        {"paper_dir": "p", "uid": "p.pdf:xref1", "image": "panel.png"}
    ]
    frozen, artifacts = a.freeze_items(first, [original])
    a.seal(first, frozen, artifacts=artifacts, completed_at="2026-09-01")
    bad = item()
    bad["panels"] = [
        {"paper_dir": "p", "uid": "p.pdf:xref1", "image": None,
         "image_unavailable_reason": "No archived image is available for this panel."}
    ]
    revision = {
        "id": "r2", "execution_id": "e1", "paper": "p",
        "component": "image_forensics", "provenance": {}, "revision_of": "r1",
    }
    a.seal(revision, [bad], completed_at="2026-09-02")

    panel = a.feed()["items"][0]["panels"][0]
    assert panel["image"].startswith("__runs/r1/")
    assert panel["image_recovery"] == {
        "method": "exact item id and panel uid in ancestor run", "run_id": "r1"
    }
    assert "image_unavailable_reason" not in panel


def test_sealed_conflict_and_idempotence(tmp_path):
    a = Archive(tmp_path)
    execution(a, "e1")
    r = run(a, "e1", "r1", items=[item()])
    assert run(a, "e1", "r1", items=[item()]) == r
    with pytest.raises(ValueError):
        run(a, "e1", "r1")
    with pytest.raises(ValueError):
        a.decide("r1", "wrong", "true_issue", "R")
    with pytest.raises(ValueError):
        a.decide("latest", item()["id"], "true_issue", "R")


def test_original_candidates_visible_without_screening(tmp_path):
    a = Archive(tmp_path)
    execution(a, "e1")
    run(a, "e1", "r1", items=[item()])
    assert a.feed()["items"][0]["publication_status"] == "unscreened"
    assert not (tmp_path / ".image_track/ai_screening.json").exists()


def test_index_rebuild_recovers_manifest(tmp_path):
    a = Archive(tmp_path)
    execution(a, "e1")
    run(a, "e1", "r1", items=[item()])
    (a.base / "index.json").unlink()
    a.rebuild_index()
    assert len(a.feed()["items"]) == 1


def test_portable_copy_import_is_idempotent_and_checks_bytes(tmp_path):
    from copy_paste_detector.portable import save_run
    from metascience_agent.analysis_history import import_copy

    root = tmp_path / "project"
    paper = root / "paper"
    paper.mkdir(parents=True)
    source = tmp_path / "data.csv"
    source.write_text("a,b\n1,2\n1,2\n")
    result = {
        "path": str(source),
        "duplicate_groups": [{"kind": "row_pair", "cells": [{"row": 2, "col": 1}]}],
        "n_row_pairs": 1,
        "n_row_pair_groups": 1,
        "n_rows_implicated": 2,
    }
    portable = save_run(
        tmp_path / "portable", "cp_test", "2026-09-01T00:00:00Z", source, result, {}
    )
    saved = import_copy(root, paper, portable)
    assert saved["id"] == "cp_test"
    assert saved["items"][0]["result_counts"]["n_rows_implicated"] == 2
    assert import_copy(root, paper, portable)["existing"]
    (portable / "input.csv").write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        import_copy(root, paper, portable)


@pytest.mark.usefixtures("image_package")
def test_dry_inventory_never_creates_archive(tmp_path):
    from metascience_agent.analysis_history import import_history

    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "metadata.json").write_text("{}")
    report = import_history(tmp_path, dry_run=True)
    assert report["dry_run"] is True
    assert report["inventory"]["screening_history_documents"] == 0
    assert not (tmp_path / ".analysis_runs").exists()


@pytest.mark.usefixtures("image_package")
def test_interrupted_workspace_preserves_previous_run(tmp_path):
    from metascience_agent.analysis_runs import workspace

    a = Archive(tmp_path)
    execution(a, "e1")
    run(a, "e1", "r1", items=[item()])
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "source.pdf").write_bytes(b"old source")
    with pytest.raises(RuntimeError):
        with workspace(paper, execution_id="e1") as (archive, pending, working):
            (working / "source.pdf").write_bytes(b"new source")
            raise RuntimeError("stopped while extracting")
    assert (paper / "source.pdf").read_bytes() == b"old source"
    assert a.run("r1")["items"][0]["id"] == item()["id"]
    assert a.run(pending["id"])["status"] == "failed"


@pytest.mark.usefixtures("image_package")
def test_a_successful_workspace_reclaims_its_own_tree(tmp_path):
    """The leak this closes: the staging tree used to survive on EVERY path, so
    each re-sweep left a full copy of every paper behind -- 164.7 GB across
    three corpora when it was measured."""
    from metascience_agent.analysis_runs import workspace

    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "source.pdf").write_bytes(b"source")
    with workspace(paper, execution_id=None) as (archive, pending, working):
        assert working.is_dir()
        assert (working / "source.pdf").read_bytes() == b"source"
        tree = archive.base / "work" / pending["id"]
        archive.seal(pending, [], status="completed", completed_at="2026-09-13")
    assert not tree.exists(), "a successful workspace left its staging tree behind"
    assert (paper / "source.pdf").read_bytes() == b"source", "the paper was touched"


@pytest.mark.usefixtures("image_package")
def test_a_failed_workspace_keeps_its_tree(tmp_path):
    """A run that never sealed never froze its output into objects/ nor
    published it, so its tree can be the only copy of that work."""
    from metascience_agent.analysis_runs import workspace

    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "source.pdf").write_bytes(b"source")
    tree = None
    with pytest.raises(RuntimeError):
        with workspace(paper) as (archive, pending, working):
            tree = archive.base / "work" / pending["id"]
            (working / "partial.json").write_text("half-written output")
            raise RuntimeError("stopped mid-run")
    assert tree.exists(), "a failed run's staging tree was deleted"
    assert (tree / "p" / "partial.json").read_text() == "half-written output"


@pytest.mark.usefixtures("image_package")
def test_keep_workspace_env_var_retains_the_tree_on_success(monkeypatch, tmp_path):
    from metascience_agent.analysis_runs import workspace

    monkeypatch.setenv("METASCIENCE_KEEP_WORKSPACE", "1")
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "source.pdf").write_bytes(b"source")
    with workspace(paper) as (archive, pending, working):
        tree = archive.base / "work" / pending["id"]
        archive.seal(pending, [], status="completed", completed_at="2026-09-13")
    assert tree.exists(), "METASCIENCE_KEEP_WORKSPACE=1 did not retain the tree"


@pytest.mark.usefixtures("image_package")
def test_the_staged_copy_is_independent_of_the_paper(tmp_path):
    """The copy-in uses copy-on-write clones where the filesystem offers them.
    A reflink shares extents but NOT identity, so a producer mutating its
    private copy must not reach the paper directory -- which is the whole
    reason this module forbids hard links into mutable paper directories."""
    from metascience_agent.analysis_runs import workspace

    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "source.pdf").write_bytes(b"original source")
    with workspace(paper) as (archive, pending, working):
        (working / "source.pdf").write_bytes(b"the producer rewrote its copy")
        assert (paper / "source.pdf").read_bytes() == b"original source"
        archive.seal(pending, [], status="completed", completed_at="2026-09-13")
    assert (paper / "source.pdf").read_bytes() == b"original source"


def test_explicit_reuse_does_not_relabel_owner(tmp_path):
    a = Archive(tmp_path)
    execution(a, "e1")
    execution(a, "e2")
    run(a, "e1", "r1", items=[item()])
    a.reuse("e2", "r1")
    assert a.feed("e2")["items"][0]["run_id"] == "r1"
    assert a.feed("e2")["items"][0]["execution_id"] == "e1"


def test_copy_missing_input_keeps_raw_error(tmp_path):
    from metascience_agent.analysis_history import capture_copy

    (tmp_path / "p").mkdir()
    saved = capture_copy(tmp_path, tmp_path / "p", {"error": "unreadable file"}, None)
    assert saved["status"] == "failed"
    assert saved["raw_result"]["error"] == "unreadable file"


def test_tampered_manifest_is_rejected(tmp_path):
    a = Archive(tmp_path)
    execution(a, "e1")
    run(a, "e1", "r1", items=[item()])
    path = a.base / "runs/r1.json"
    obj = json.loads(path.read_text())
    obj["items"] = []
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="digest"):
        a.run("r1")


def test_report_history_never_reads_newer_tracks_or_sources(tmp_path, monkeypatch):
    from metascience_agent.review_issues import collect_issues

    a = Archive(tmp_path)
    paper = tmp_path / "p"
    paper.mkdir()
    e = a.execution("comprehensive", components=["comprehensive"])
    a.seal(
        {
            "id": "report",
            "execution_id": e["id"],
            "component": "comprehensive",
            "paper": "p",
            "provenance": {},
            "document": {"findings": []},
        }
    )
    (paper / "new.pdf").write_bytes(b"new source")
    monkeypatch.setattr(
        "metascience_agent.review_issues._image_issues",
        lambda *args: pytest.fail("current image joined into history"),
    )
    view = collect_issues(paper, "report")
    assert view["latest_run"] == "report"
    assert view["archived_article"]["pdf_relpath"] is None
    assert "unavailable" in view["archived_article"]["warning"]


def test_tool_capture_precedes_truncation_and_uses_frozen_input(tmp_path, monkeypatch):
    from metascience_agent.history_runtime import record_tool_copy

    a = Archive(tmp_path)
    e = a.execution("comprehensive", components=["comprehensive", "copy_paste"])
    paper = tmp_path / "p"
    paper.mkdir()
    source = paper / "data.csv"
    source.write_text("before")
    monkeypatch.setenv("METASCIENCE_PAPER_DIR", str(paper))
    monkeypatch.setenv("METASCIENCE_HISTORY_ROOT", str(tmp_path))
    monkeypatch.setenv("METASCIENCE_EXECUTION_ID", e["id"])

    def detector(path):
        source.write_text("after")
        assert Path(path).read_text() == "before"
        return {"path": path, "duplicate_groups": [], "full_explanation": "x" * 12000}

    returned = record_tool_copy(detector, {"path": str(source)})
    saved = a.run(returned["history_run_id"])
    assert len(saved["raw_result"]["full_explanation"]) == 12000
    assert saved["provenance"]["input_hashes"][str(source)] == saved["artifacts"]["input"]["sha256"]
    assert a.artifact(saved["id"], "input")[0].read_text() == "before"
    assert returned["path"] == str(source)


def test_portable_failed_attempt_keeps_its_error_without_input(tmp_path):
    from copy_paste_detector.portable import save_run
    from metascience_agent.analysis_history import import_copy

    paper = tmp_path / "project/p"
    paper.mkdir(parents=True)
    portable = save_run(
        tmp_path / "portable",
        "failed_copy",
        "2026-09-09T00:00:00Z",
        tmp_path / "missing.csv",
        {"error": "input missing"},
        {},
    )
    saved = import_copy(paper.parent, paper, portable)
    assert saved["status"] == "failed"
    assert saved["raw_result"]["error"] == "input missing"


@pytest.mark.usefixtures("image_package")
def test_cancellation_records_the_screening_attempt(tmp_path, monkeypatch):
    import asyncio
    from tests.test_image_review import _paper, _group
    from metascience_observatory_image_analysis.image_forensics import screening

    (tmp_path / ".image_track").mkdir()
    paper = _paper(tmp_path, "10.1--images", [_group()])
    original = json.loads((paper / "image_duplication_findings.json").read_text())

    async def exercise():
        began = asyncio.Event()

        async def judge(*args, **kwargs):
            began.set()
            await asyncio.Future()

        monkeypatch.setattr(screening, "judge", judge)
        pending = asyncio.create_task(screening.screen_paper_result(paper, original))
        await asyncio.wait_for(began.wait(), 5)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending

    asyncio.run(exercise())
    archive = Archive(tmp_path)
    saved = [archive.run(p.stem) for p in (archive.base / "runs").glob("*.json")]
    assert any(r["status"] == "cancelled" and r["items"] for r in saved)
    assert not screening.read_ledger(tmp_path)["claims"]


@pytest.mark.usefixtures("image_package")
def test_image_publication_uses_item_policy_and_incremental_sync(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from metascience_agent import history_publication
    from metascience_observatory_image_analysis.image_forensics import screening

    records = [
        {"item_uid": "pair", "paper": "p", "policy": screening.POLICY,
         "eligible": False, "source_fingerprint": "pair-stamp"},
        {"item_uid": "clone", "paper": "p", "policy": screening.CLONE_POLICY,
         "eligible": False, "source_fingerprint": "clone-stamp"},
    ]
    monkeypatch.setattr(history_publication, "shared_records", lambda cur, corpus: records)
    monkeypatch.setattr(history_publication, "refresh", lambda root: pytest.fail("Shared publication must not scan local files"))

    class Cursor:
        def __init__(self):
            self.queries = []
            self.last = ""
        def execute(self, query, args=()):
            self.last = " ".join(query.split()).lower()
            self.queries.append((self.last, args))
        def fetchone(self):
            return (1,) if "select id from corpora" in self.last else (0,)

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()
        def transaction(self):
            return nullcontext()
        def cursor(self):
            return self.cursor_instance

    conn = Connection()
    history_publication.sync(tmp_path, conn)
    queries = [q for q, _ in conn.cursor_instance.queries]
    assert any("insert into image_publication as current" in q for q in queries)
    assert any("delete from image_publication current" in q and "not exists" in q
               for q in queries)
    assert not any(q == "delete from image_publication where corpus_id=%s" for q in queries)
    payload = next(args[1] for q, args in conn.cursor_instance.queries
                   if "insert into image_publication as current" in q)
    assert {r["policy"] for r in json.loads(payload)} == {
        screening.POLICY, screening.CLONE_POLICY}


@pytest.mark.usefixtures("image_package")
def test_inventory_discovers_copy_results_and_preserves_recorded_id(tmp_path):
    from metascience_agent.analysis_history import import_history

    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "metadata.json").write_text("{}")
    source = paper / "source.csv"
    source.write_text("a,b\n1,2\n1,2\n")
    (paper / "saved.json").write_text(
        json.dumps(
            {
                "run_id": "recorded_copy",
                "result": {
                    "path": str(source),
                    "n_row_pairs": 1,
                    "duplicate_groups": [{"kind": "row_pair"}],
                },
            }
        )
    )
    dry = import_history(tmp_path, dry_run=True)
    assert dry["copy_outputs_found"] == 1
    assert not (tmp_path / ".analysis_runs").exists()
    report = import_history(tmp_path)
    assert not report["errors"]
    assert Archive(tmp_path).run("recorded_copy")["items"]


def test_report_source_cannot_be_the_generated_report_pdf(tmp_path):
    from metascience_agent.analysis_history import report_view
    archive = Archive(tmp_path); paper = tmp_path / 'p'; paper.mkdir()
    execution_record = archive.execution('comprehensive', components=['comprehensive'])
    source = paper / 'z_source.pdf'; source.write_bytes(b'source document')
    rendered = paper / 'report.pdf'; rendered.write_bytes(b'generated report')
    archive.seal({'id': 'report_run', 'execution_id': execution_record['id'], 'component': 'comprehensive',
                  'paper': 'p', 'provenance': {}, 'document': {'findings': []}}, artifacts={
                  'output': {**archive.object(rendered), 'role': 'report_output'},
                  'source': {**archive.object(source), 'role': 'source'}})
    assert report_view(paper, 'report_run')['archived_article']['pdf_relpath'] == '__runs/report_run/source'


def test_panel_source_pdf_is_frozen_with_its_pixels(tmp_path):
    a = Archive(tmp_path)
    paper = tmp_path / 'p'
    paper.mkdir()
    (paper/'a.pdf').write_bytes(b'pdf source')
    r = {'id': 'r1', 'execution_id': 'e1', 'paper': 'p',
         'component': 'image_forensics', 'provenance': {}}
    i = item()
    i['panels'] = [{'paper_dir': 'p', 'image': None,
                    'document': {'path': 'a.pdf', 'role': 'main'}}]
    frozen, artifacts = a.freeze_items(r, [i])
    ref = frozen[0]['panels'][0]['document']['path']
    assert ref.startswith('__runs/r1/')
    assert artifacts[ref.split('/')[-1]]['role'] == 'source_pdf'


def test_streamed_evidence_digest_preserves_historical_bytes():
    import hashlib
    import json
    from metascience_agent.analysis_runs import digest
    value = {'unicode': 'μ核', 'nested': [{'float': 1.5, 'none': None, 'bool': True}] * 1000}
    assert digest(value) == hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def test_capture_transfer_and_public_copy_have_identical_evidence(tmp_path):
    import copy
    a = Archive(tmp_path)
    (tmp_path / 'p').mkdir()
    (tmp_path / 'p/a.png').write_bytes(b'pixels')
    original = item()
    original['panels'] = [{'paper_dir': 'p', 'image': 'a.png'}]
    pristine = copy.deepcopy(original)
    r = {'id': 'r1', 'execution_id': 'e1', 'paper': 'p',
         'component': 'image_forensics', 'provenance': {}}
    isolated, artifacts = a.freeze_items(r, [original])
    assert original == pristine
    owned = [copy.deepcopy(original)]
    events = []
    transferred, next_artifacts = a.freeze_items(r, owned, copy_items=False,
        progress=lambda stage, **counts: events.append((stage, counts)))
    assert transferred is owned
    assert transferred == isolated and artifacts == next_artifacts
    assert {'freezing_items', 'freezing_sources', 'evidence_keys'} <= {e[0] for e in events}
