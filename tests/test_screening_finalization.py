"""Bound finalization work and recover saved decisions without another model call."""
import asyncio
import json

from metascience_observatory_image_analysis.image_forensics import screening, screening_reconcile


def test_empty_sync_does_not_read_archive_or_connect(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit import history_db
    def forbidden(*args, **kwargs):
        raise AssertionError('empty selection must not expand to the corpus')
    monkeypatch.setattr(history_db, 'Archive', forbidden)
    assert history_db.sync(tmp_path, None, []) == {'runs': 0, 'items': 0, 'reviews': 0}


def test_scoped_reconcile_batches_publication_and_never_renders(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit import history_publication, webapp_index
    from metascience_observatory_image_analysis import image_review
    from metascience_observatory_image_analysis.image_forensics import repair_source_identity
    calls = []
    def forbidden(*args, **kwargs):
        raise AssertionError('normal finalization must not scan or rebuild the project index')
    monkeypatch.setattr(webapp_index, 'iter_paper_dirs', forbidden)
    monkeypatch.setattr(repair_source_identity, 'refresh_project_index', forbidden)
    def paper(path, **kwargs):
        assert not kwargs['import_history'] and not kwargs['refresh_publication']
        calls.append(path.name)
        return {'paper': path.name, 'errors': [], 'changed': [], 'pushed': 0}
    monkeypatch.setattr(screening_reconcile, 'reconcile_paper', paper)
    monkeypatch.setattr(history_publication, 'refresh', lambda root, **kw: calls.append(('publication', len(kw['papers']))))
    def cache(root, **kw):
        assert kw == {'materialise': False}
        calls.append('cache')
        return {'counts': {'items': 3}}
    monkeypatch.setattr(image_review, 'write_cache', cache)
    progress = []
    result = screening_reconcile.reconcile_project(tmp_path, push=False,
        papers=[tmp_path/'b', tmp_path/'a', tmp_path/'b'], progress=progress.append)
    assert calls == ['a', 'b', ('publication', 2), 'cache']
    assert result['active_findings'] == 3
    assert progress[-1]['stage'] == 'reconciliation_complete'
    assert [r['completed'] for r in progress if r['stage']=='reconcile'] == [0, 1, 2]


def test_pending_finalization_survives_restart_without_rescreen(tmp_path, monkeypatch):
    from metascience_observatory_image_analysis import image_review
    item = {'id':'cross:one:two:x', 'papers':[{'dir':'one'}, {'dir':'nested/two'}]}
    monkeypatch.setattr(image_review, 'build_items', lambda *a, **kw: {'items':[item]})
    def no_cache(*a, **kw):
        raise AssertionError('no redundant pre-reconciliation feed rebuild')
    monkeypatch.setattr(image_review, 'write_cache', no_cache)
    async def screen(*a, **kw):
        return {'id':item['id'], 'decision':'innocuous'}
    monkeypatch.setattr(screening, 'screen_item', screen)
    def fail(*a, **kw):
        raise RuntimeError('interrupted after saved decisions')
    monkeypatch.setattr(screening_reconcile, 'reconcile_project', fail)
    import pytest
    with pytest.raises(RuntimeError, match='interrupted'):
        asyncio.run(screening._run_screening(tmp_path, force=True))
    pending = tmp_path/'.image_track/reconciliation_pending'
    assert len(list(pending.glob('*.jsonl'))) == 1
    monkeypatch.setattr(image_review, 'build_items', lambda *a, **kw: {'items':[]})
    def finish(root, *, papers, progress):
        assert set(papers) == {tmp_path/'one', tmp_path/'nested/two'}
        return {'papers':[], 'sync_pending':0}
    monkeypatch.setattr(screening_reconcile, 'reconcile_project', finish)
    assert asyncio.run(screening._run_screening(tmp_path)) == []
    assert not list(pending.glob('*.jsonl'))


def test_batch_publication_preserves_unselected_state(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit import history_publication, analysis_runs
    from metascience_observatory_image_analysis import image_review
    base = tmp_path/'.analysis_runs'
    base.mkdir()
    (base/'index.json').write_text('{"runs":{}}')
    preserved = {'paper':'other', 'item_uid':'old', 'eligible':False}
    (base/'publication.json').write_text(json.dumps({'items':[preserved, {'paper':'a','item_uid':'stale'}]}))
    feed_calls = []
    monkeypatch.setattr(analysis_runs.Archive, 'feed', lambda self: feed_calls.append(1) or {'items':[{'id':'new'}]})
    monkeypatch.setattr(image_review, '_within_items', lambda paper,*args: [{'id':'new','paper':{'dir':'a'}}] if paper.name=='a' else [])
    monkeypatch.setattr(image_review, '_cross_items', lambda *args: [])
    monkeypatch.setattr(screening, 'published_items', lambda root, items: items)
    monkeypatch.setattr(screening, 'input_stamp', lambda *args: 'stamp')
    records = history_publication.refresh(tmp_path, papers=[tmp_path/'a', tmp_path/'b'])
    assert feed_calls == [1]
    assert preserved in records
    assert {r['item_uid'] for r in records} == {'old','new'}
    assert next(r for r in records if r['item_uid']=='new')['eligible'] is True


def test_no_changed_papers_means_no_finalization_work(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit import db_push
    from metascience_observatory_image_analysis import image_review
    def forbidden(*args, **kwargs):
        raise AssertionError('nothing changed: no connection or feed rebuild')
    monkeypatch.setattr(db_push, '_connect', forbidden)
    monkeypatch.setattr(image_review, 'write_cache', forbidden)
    assert screening_reconcile.reconcile_project(tmp_path, papers=[]) == {
        'papers': [], 'sync_pending': 0, 'state': 'unchanged'}
