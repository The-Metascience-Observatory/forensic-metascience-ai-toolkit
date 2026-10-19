"""Regression checks for live-cache contention, not just single-process speed."""
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.repository import Repository
from forensic_metascience_ai_toolkit.workbench.service import Service
from tests.test_workbench_catalog import seed


@pytest.fixture
def caches(tmp_path):
    a=Catalog(tmp_path/'cache.sqlite3');seed(a)
    b=Catalog(a.path)
    yield a,b
    b.close();a.close()


def test_unrelated_writes_do_not_invalidate_projection(caches,tmp_path,monkeypatch):
    a,b=caches
    r=Repository(a);r.refresh('project','r_old','image_forensics')
    original=r.items
    b.set_state('synced_at','later')
    b.set_state('file_monitor_error',None)
    b.save_detail('runs','[1]',{'cached':True},b.record_token('runs','[1]'))
    media=tmp_path/'file';media.write_bytes(b'content');b.register_file(media)
    monkeypatch.setattr(a,'headers',lambda *a:pytest.fail('Unrelated write rebuilt queue'))
    r.refresh('project','r_old','image_forensics')
    assert r.items is original


@pytest.mark.usefixtures("image_package")
def test_two_process_revisions_and_selected_scope(caches):
    a,b=caches
    r=Repository(a);r.refresh('project','r_old','image_forensics')
    assert len(r.items)==123
    row=b.records('component_items')[0];row['record']['rank']['score']=1000
    b.apply_changes([('component_items',json.dumps([row['id']]),row)],2)
    r.refresh('project','r_old','image_forensics')
    assert r.feed({'project':'project','run':'r_old'})['items'][0]['id']==row['item_uid']
    r.refresh('project','latest','image_forensics')
    assert r.items=={} # latest failed run cannot expose old candidates


def test_readers_and_snapshot_do_not_block_writes(caches):
    a,b=caches
    with a.snapshot():
        before=a.version
        with ThreadPoolExecutor(1) as pool:
            other_reader=pool.submit(lambda:id(a.reader)).result()
            pool.submit(b.set_state,'status','ok').result(timeout=2)
        assert other_reader!=id(a.reader)
        b.enqueue({'event_id':'e'})
        assert a.version==before
    assert a.version!=before


@pytest.mark.usefixtures("image_package")
def test_thumbnail_preserves_source_validation_and_deduplicates(caches,tmp_path,monkeypatch):
    a,b=caches
    image=tmp_path/'source.png';Image.new('RGB',(1300,600),'teal').save(image)
    sha=hashlib.sha256(image.read_bytes()).hexdigest();a.register_file(image,sha)
    a.apply_changes([('run_artifacts',json.dumps([1,'a']),dict(run_id=1,artifact_uid='a',content_sha256=sha,record={'name':'source.png'}))],2)
    s=Service(a,background=False)
    monkeypatch.setattr(a,'headers',lambda *a:pytest.fail('Media hydrated a repository'))
    args=dict(project='project',dir='nested/paper',f='__runs/r_old/a',variant='thumbnail')
    assert not s.handle('artifact',args)['thumbnail_ready']
    peer=Service(b,background=False)
    decodes=[];original_thumbnail=Image.Image.thumbnail
    def decoded(image,*args,**kwargs):
        decodes.append(1)
        return original_thumbnail(image,*args,**kwargs)
    monkeypatch.setattr(Image.Image,'thumbnail',decoded)
    with ThreadPoolExecutor(4) as pool:
        results=list(pool.map(lambda n:(s if n%2 else peer).handle('thumbnail',args),range(4)))
    assert len(decodes)==1
    assert len({r['path'] for r in results})==1
    assert Image.open(results[0]['path']).size==(260,120)
    assert Image.open(image).size==(1300,600)
    assert s.handle('artifact',args)['thumbnail_ready']
    Image.new('RGB',(1300,600),'red').save(image)
    with pytest.raises(FileNotFoundError):s.handle('artifact',args)
    image.unlink()
    with pytest.raises(FileNotFoundError):s.handle('artifact',args)


def test_foreign_project_artifact_is_refused(caches):
    a,_=caches
    with pytest.raises(ValueError,match='project'):
        a.artifact_record('elsewhere','r_old','anything')


@pytest.mark.usefixtures("image_package")
def test_filtered_empty_is_not_reported_as_absent_evidence(caches):
    a,_=caches
    r=Repository(a);r.refresh('project','r_old','image_forensics')
    result=r.feed({'project':'project','run':'r_old','verdict':'all','judgments':[]})
    assert result['items']==[] and result['counts']['items']==123
    assert result['pagination']['total']==0
    assert result['empty_reason'].startswith('123 saved results exist in this run selection, but none match the current filters.')
    assert 'Adjust the filters' in result['empty_reason']


def test_image_type_lookup_uses_item_index(caches):
    """A large queue reads types in batches; none may scan every derived row."""
    a, _ = caches
    a.apply_changes([('component_item_derived', '[1]',
                      {'item_id': 1, 'image_type': 'Microscopy'})], 2)
    plan = a.reader.execute(
        "explain query plan select body from records where entity=? and json_extract(body,'$.item_id') in (?,?)",
        ['component_item_derived', 1, 2]).fetchall()
    assert any('records_item_id' in row[-1] for row in plan), plan
    assert a.rows_for('component_item_derived', 'item_id', [1, 2]) == [
        {'item_id': 1, 'image_type': 'Microscopy'}]


@pytest.mark.usefixtures("image_package")
def test_scoped_read_preserves_global_projection_order_and_filters(caches):
    a,_=caches
    global_repo=Repository(a);global_repo.refresh()
    scoped=Repository(a);scoped.refresh('project','r_old','image_forensics')
    for filters in ({'verdict':'all'}, {'verdict':'unexplained'}, {'verdict':'all','offset':50},
                    {'verdict':'all','undecided':True}, {'verdict':'all','kind':'not-recorded'}):
        args={'project':'project','run':'r_old',**filters}
        before=global_repo.feed(args);after=scoped.feed(args)
        for key in ('items','counts','pagination','judgment_counts','coverage','empty_reason'):
            assert after[key]==before[key], key


def test_artifact_metadata_cache_revalidates_shared_revision(caches,monkeypatch):
    a,b=caches
    key=json.dumps([1,'ref'])
    first=dict(run_id=1,artifact_uid='ref',content_sha256='a'*64,record={'name':'source.png'})
    b.apply_changes([('run_artifacts',key,first)],2)
    assert a.artifact_record('project','r_old','ref')==first
    original=a.rows_for
    monkeypatch.setattr(a,'rows_for',lambda *args:pytest.fail('Cached metadata repeated indexed reads'))
    b.set_state('sync_error',None)
    assert a.artifact_record('project','r_old','ref')==first
    monkeypatch.setattr(a,'rows_for',original)
    updated={**first,'content_sha256':'b'*64}
    b.apply_changes([('run_artifacts',key,updated)],3)
    assert a.artifact_record('project','r_old','ref')==updated
    b.apply_changes([('run_artifacts',key,None)],4)
    with pytest.raises(FileNotFoundError):a.artifact_record('project','r_old','ref')


@pytest.mark.usefixtures("image_package")
def test_thumbnail_cache_evicts_derivatives_only(caches,tmp_path,monkeypatch):
    from metascience_observatory_image_analysis.review_workbench import thumbnails
    a,_=caches
    cache=thumbnails.Thumbnails(a)
    sources=[]
    for color in ('teal','green','yellow'):
        source=tmp_path/f'{color}.png';Image.new('RGB',(800,400),color).save(source)
        sha=hashlib.sha256(source.read_bytes()).hexdigest();a.register_file(source,sha)
        sources.append(dict(path=str(source),sha256=sha))
    first=cache.generate(sources[0])
    from pathlib import Path
    monkeypatch.setattr(thumbnails,'MAX_BYTES',Path(first['path']).stat().st_size*2+10)
    for source in sources[1:]:cache.generate(source)
    assert sum(p.stat().st_size for p in cache.folder.glob('*.png'))<=thumbnails.MAX_BYTES
    for source in sources:assert a.file_for(source['sha256'])==source['path']


def test_run_history_never_loads_candidates(caches, monkeypatch):
    a, _ = caches
    original = a.rows_for
    def headers_only(entity, *args):
        assert entity not in ('component_items', 'findings', 'reviews', 'component_item_derived')
        return original(entity, *args)
    monkeypatch.setattr(a, 'rows_for', headers_only)
    monkeypatch.setattr(Repository, 'refresh', lambda *a, **k: pytest.fail('Run history loaded a projection'))
    result = Service(a, background=False).handle('runs', {'project': 'project', 'component': 'image_forensics'})
    assert result['runs']
    assert all('run_ids' not in r for r in result['runs'])


def test_cold_scope_does_not_block_cached_scope(caches, monkeypatch):
    import threading
    a, _ = caches
    warm = Repository(a)
    warm.refresh('project', 'r_old', 'image_forensics')
    entered, release = threading.Event(), threading.Event()
    original = Repository._load_projection
    def load(self, project, selection, kind):
        if selection == 'latest':
            entered.set()
            assert release.wait(5)
        return original(self, project, selection, kind)
    monkeypatch.setattr(Repository, '_load_projection', load)
    with ThreadPoolExecutor(2) as pool:
        cold = pool.submit(Repository(a).refresh, 'project', 'latest', 'image_forensics')
        try:
            assert entered.wait(2)
            # A different worker must acquire the shared payload without waiting
            # for the unrelated cold scope (not just reuse its own local cache).
            other = Repository(a)
            pool.submit(other.refresh, 'project', 'r_old', 'image_forensics').result(timeout=1)
            assert other.items is warm.items
        finally:
            release.set()
        cold.result(timeout=3)


def test_same_scope_loads_once(caches, monkeypatch):
    import threading
    a, _ = caches
    original = Repository._load_projection
    entered, release = threading.Event(), threading.Event()
    calls = []
    def load(self, *args):
        calls.append(args)
        entered.set()
        assert release.wait(5)
        return original(self, *args)
    monkeypatch.setattr(Repository, '_load_projection', load)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(Repository(a).refresh, 'project', 'r_old', 'image_forensics')
        assert entered.wait(2)
        second = pool.submit(Repository(a).refresh, 'project', 'r_old', 'image_forensics')
        release.set()
        first.result(timeout=3); second.result(timeout=3)
    assert len(calls) == 1


@pytest.mark.usefixtures("image_package")
def test_thumbnail_cache_scans_rarely_uses_striped_locks_and_evicts_least_recently_used(caches,tmp_path,monkeypatch):
    import os, time
    from pathlib import Path
    from metascience_observatory_image_analysis.review_workbench import thumbnails
    a,_=caches
    cache=thumbnails.Thumbnails(a)
    sources=[]
    for color in ('teal','green','yellow','red'):
        source=tmp_path/f'{color}.png';Image.new('RGB',(800,400),color).save(source)
        sha=hashlib.sha256(source.read_bytes()).hexdigest();a.register_file(source,sha)
        sources.append(dict(path=str(source),sha256=sha))
    legacy=cache.folder/'0123.lock';legacy.write_text('');os.utime(legacy,(time.time()-7200,)*2)
    scans=[];real=os.scandir
    monkeypatch.setattr(thumbnails.os,'scandir',lambda p:(scans.append(p),real(p))[1])
    first=cache.generate(sources[0])
    for source in sources[1:3]:cache.generate(source)
    assert len(scans)==1  # the first call measures; later ones add to the estimate
    assert not legacy.exists()  # a stale per-thumbnail lock from the old scheme is removed
    assert [p.name for p in cache.folder.glob('*.lock')]==['.eviction.lock'] and len(list((cache.folder/'.locks').glob('*.lock')))<=3
    # Least recently USED goes first: touch the oldest-created one by using it.
    paths=[Path(cache.generate(s)['path']) for s in sources[:3]]
    for n,p in enumerate(paths):os.utime(p,(time.time()-10000+n,)*2)
    cache.lookup(sources[0])  # used now
    monkeypatch.setattr(thumbnails,'MAX_BYTES',sum(p.stat().st_size for p in paths)-1)
    cache.generate(sources[3])
    assert paths[0].exists() and not paths[1].exists()
