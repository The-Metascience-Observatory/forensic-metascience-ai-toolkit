"""Local review must work with no network and no whole-corpus projection."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench import image_review_host
image_review_host.configure_service()  # the host lends its storage first, as at runtime
from metascience_observatory_image_analysis.review_workbench.local_images import ImageCatalog,LocalImages  # noqa: E402
from metascience_observatory_image_analysis.review_workbench.local_image_import import copy_cache,project_run,ingest_run  # noqa: E402
from metascience_observatory_image_analysis.review_workbench.local_image_service import LocalImageService  # noqa: E402
from forensic_metascience_ai_toolkit.workbench.repository import Repository  # noqa: E402
from tests.test_workbench_catalog import seed  # noqa: E402


@pytest.fixture
def local(tmp_path):
    source=Catalog(tmp_path/'shared.sqlite3');seed(source)
    for raw in source.records('component_items'):
        source.save_detail('component_items',json.dumps([raw['id']]),raw,source.record_token('component_items',json.dumps([raw['id']])))
    c=ImageCatalog(tmp_path/'images.sqlite3');copy_cache(c,source.path)
    project_run(c,'project',1)
    LocalImages(c).rebuild_latest('project')
    with c.db:c.db.execute("update image_projects set ready=1 where project='project'")
    # copy_cache deliberately does not make an incomplete import ready.
    with c.db:c.db.execute("insert or ignore into image_projects(project,ready) values('project',1)")
    yield c
    c.close();source.close()


def test_point_read_is_offline_and_does_not_project(local,monkeypatch):
    monkeypatch.setattr(Repository,'_load_projection',lambda *a:pytest.fail('Corpus hydration'))
    s=LocalImageService(local,background=False)
    args=dict(project='project',run='r_old',item='i_0')
    assert s.handle('item_core',args)['id']=='i_0'
    assert s.handle('item_details',args)['sentence']=='Candidate 0'
    with ThreadPoolExecutor(10) as pool:
        assert all(r['id']=='i_0' for r in pool.map(lambda _:s.handle('item_core',args),range(10)))
    with pytest.raises(LookupError,match='absent'):s.handle('item',dict(args,run='latest'))


def test_sql_queue_matches_existing_filters(local):
    old=Repository(local);old.refresh('project','r_old','image_forensics')
    images=LocalImages(local)
    for filters in ({'verdict':'all'},{'verdict':'unexplained','offset':100},{'judgments':[]},{'kind':'absent'},{'sort':'paper','direction':'desc'},{'q':'nested/paper'},{'figure_span':'unknown'},{'figure_span':'different_figures'}):
        args=dict(project='project',run='r_old',**filters)
        expected=old.feed(args);actual=images.feed(args)
        assert [i['id'] for i in actual['items']]==[i['id'] for i in expected['items']]
        for field in ('counts','pagination','judgment_counts','kinds','image_types','lookalike_counts','figure_span_counts','match_region_counts','facet_totals'):
            assert actual[field]==expected[field],field


def test_local_review_survives_restart_and_retains_disagreement(local):
    images=LocalImages(local);args=dict(project='project',run='r_old',item='i_0',reviewer='Dan',decision='false_positive',event_id='first')
    first=images.save_review(args)
    assert first['storage']=='local' and not first['pending']
    assert images.save_review(args)==first
    assert local.pending()==[]
    assert images.item(args)['publication_status']=='cleared'
    with pytest.raises(ValueError,match='identity conflict'):images.save_review(dict(args,item='i_1'))
    images.save_review(dict(args,event_id='second',reviewer='Greg',decision='unsure'))
    reopened=ImageCatalog(local.path)
    try:
        result=LocalImages(reopened).item(args)
        assert result['reviews']['conflict'] and result['decision'] is None
        assert len(result['reviews']['history'])==2
    finally:reopened.close()


def test_decision_sort_groups_decisions_and_keeps_undecided_last(local):
    images=LocalImages(local);base=dict(project='project',run='r_old')
    for n,(item,decision) in enumerate([('i_5','false_positive_chart'),('i_6','false_positive'),('i_7','true_issue'),('i_8','unsure')]):
        images.save_review(dict(base,item=item,reviewer='Dan',decision=decision,event_id=f'e{n}'))
    images.save_review(dict(base,item='i_9',reviewer='Dan',decision='true_issue',event_id='c1'))
    images.save_review(dict(base,item='i_9',reviewer='Greg',decision='false_positive',event_id='c2'))
    def order(direction):
        ids=[i['id'] for i in images.feed(dict(base,verdict='all',judgments=None,sort='decision',direction=direction,limit=100))['items']]
        return ids[:5],ids[5:]
    decided,rest=order('asc')
    assert decided==['i_7','i_8','i_9','i_6','i_5']
    assert rest and not {'i_5','i_6','i_7','i_8','i_9'} & set(rest)
    decided,rest_desc=order('desc')
    assert decided==['i_5','i_6','i_9','i_8','i_7'] and rest_desc==rest
    # The column is rebuilt from the events for a database made before it existed.
    with local.db:local.db.execute('update image_queue set decision=null')
    local.db.execute('alter table image_queue drop column decision');local.db.commit()
    reopened=ImageCatalog(local.path)
    try:
        rows=dict(reopened.reader.execute("select item,decision from image_queue where run in (select run from image_queue where item='i_9') and item in ('i_5','i_9','i_10')").fetchall())
        assert rows=={'i_5':'false_positive_chart','i_9':'conflict','i_10':None}
    finally:reopened.close()


def test_navigation_bounded_and_missing_detail_is_not_empty(local):
    images=LocalImages(local);args=dict(project='project',run='r_old',item='i_100',verdict='all')
    nav=images.navigation(args)
    assert nav['prev']['id']=='i_101' and nav['next']['id']=='i_99'
    assert nav['next_undecided']['id']=='i_99'
    with local.db:local.db.execute("delete from details where entity='component_items' and key='[101]'")
    with pytest.raises(LookupError,match='unavailable locally'):images.item(args)


def test_import_is_idempotent_and_refuses_digest_conflict(local,tmp_path):
    from forensic_metascience_ai_toolkit.analysis_runs import digest
    run=dict(id='fresh',execution_id='fresh_e',component='image_forensics',paper='nested/paper',status='completed',items=[],artifacts={})
    run['sealed_digest']=digest(run)
    execution=dict(id='fresh_e',name='Fresh',requested_components=['image_forensics'],status='completed')
    assert ingest_run(local,'project',tmp_path,run,execution)
    assert not ingest_run(local,'project',tmp_path,run,execution)
    altered=dict(run,status='failed');altered['sealed_digest']=digest({k:v for k,v in altered.items() if k!='sealed_digest'})
    with pytest.raises(ValueError,match='conflict'):ingest_run(local,'project',tmp_path,altered,execution)


def test_latest_item_read_never_loads_even_project_headers(local,monkeypatch):
    local.set_state('image_selection:project',local.rows_for('runs','run_uid',['r_old']))
    monkeypatch.setattr(local,'headers',lambda *a:pytest.fail('Point read loaded project headers'))
    assert LocalImages(local).item(dict(project='project',item='i_3'))['id']=='i_3'


def test_retired_run_cannot_be_opened_or_restored(local,tmp_path):
    images=LocalImages(local)
    r=local.rows_for('runs','run_uid',['r_old'])[0];r['retired_at']='today';r['retirement_reason']='user_requested_rerun'
    with local.db:local.put('runs',r)
    with pytest.raises(LookupError,match='retired'):images.item(dict(project='project',run='r_old',item='i_0'))
    from forensic_metascience_ai_toolkit.analysis_runs import digest
    run=dict(id='r_old',execution_id='e_old',component='image_forensics',paper='nested/paper',status='completed',items=[],artifacts={})
    run['sealed_digest']=digest(run)
    assert not ingest_run(local,'project',tmp_path,run)


def test_unrelated_project_revision_does_not_invalidate(local):
    before=local.revision('project')
    with local.db:local.bump('elsewhere')
    assert local.revision('project')==before


def test_bulk_refuses_changed_selection(local):
    service=LocalImageService(local,background=False)
    with pytest.raises(ValueError,match='selection changed'):
        service.handle('review_filter',dict(project='project',run='r_old',verdict='all',reviewer='Dan',decision='false_positive',expected_total=2))
    assert local.reader.execute('select count(*) from image_events').fetchone()[0]==0


def test_new_tombstone_retires_previously_cached_items(local,tmp_path):
    from metascience_observatory_image_analysis.review_workbench.local_image_import import reconcile
    archive=tmp_path/'.analysis_runs';archive.mkdir()
    (archive/'retired_runs.json').write_text(json.dumps({'r_old':{'retired_at':'today'}}))
    reconcile(local,'project',tmp_path)
    project_run(local,'project',1)  # Rebuilding the queue must keep tombstones.
    with pytest.raises(LookupError,match='retired'):
        LocalImages(local).item(dict(project='project',run='r_old',item='i_0'))
    assert not LocalImages(local).feed(dict(project='project',run='r_old',verdict='all'))['items']


def test_incomplete_import_never_exposes_partial_queue(local):
    with local.db:local.db.execute("insert into image_imports values('project','r_old','abc','indexed',null)")
    images=LocalImages(local)
    assert not images.feed(dict(project='project',run='r_old',verdict='all'))['items']
    with pytest.raises(LookupError,match='being imported'):
        images.item(dict(project='project',run='r_old',item='i_0'))


def test_bad_publication_does_not_block_later_entries(local,tmp_path):
    archive=tmp_path/'.analysis_runs';archive.mkdir()
    (archive/'review_publications.jsonl').write_text('{bad json}\n'+json.dumps({'run':'missing','digest':'x'})+'\n')
    service=LocalImageService(local,background=False)
    service.publications('project',tmp_path)
    assert local.state('image_journal:'+str(tmp_path))==(archive/'review_publications.jsonl').stat().st_size
    assert 'missing' in local.state('image_ingest_error:project')


def test_latest_queue_uses_ingested_headers(local,monkeypatch):
    monkeypatch.setattr(local,'headers',lambda *a:pytest.fail('Queue loaded every run header'))
    images=LocalImages(local)
    monkeypatch.setattr(images.repo,'refresh',lambda *a:pytest.fail('Queue rebuilt repository'))
    assert images.feed(dict(project='project',verdict='all'))['selection']=='latest'


def test_sealed_publication_is_consumed_without_host_or_network(local,tmp_path,monkeypatch):
    from metascience_observatory_image_analysis import integration
    from forensic_metascience_ai_toolkit.analysis_runs import Archive
    from tests.test_analysis_history import execution,run,item
    monkeypatch.setattr(integration,'notify_published',None)
    archive=Archive(tmp_path);execution(archive,'local_execution')
    run(archive,'local_execution','local_run',items=[item()])
    journal=tmp_path/'.analysis_runs/review_publications.jsonl'
    assert json.loads(journal.read_text())['run']=='local_run'
    service=LocalImageService(local,background=False)
    service.publications('project',tmp_path)
    result=service.handle('item_core',dict(project='project',run='local_run',item='within:p:IMGDUP-1'))
    assert result['run_id']=='local_run'
    service.publications('project',tmp_path)
    assert local.reader.execute("select count(*) from image_queue where run='local_run'").fetchone()[0]==1


def test_text_context_filter_affects_rows_and_pagination_without_review_changes(local):
    images=LocalImages(local)
    args=dict(project='project',run='r_old',verdict='all')
    before=images.page(args)[1]['total']
    with local.db:
        local.db.execute("update image_queue set text_label_context=1, publication_status='unscreened', historical_status='unscreened' where project='project' and run='r_old' and item='i_0'")
    rows,page,_=images.page(args)
    assert page['total']==before-1
    assert all(r['id']!='i_0' for r in rows)
    rows,page,_=images.page(dict(args,text_context='only'))
    assert page['total']==1 and rows[0]['id']=='i_0'
    assert rows[0]['decision'] is None
    assert images.page(dict(args,text_context='include'))[1]['total']==before
    # Direct access remains possible, even when context is excluded from queues.
    assert images.item(dict(args,item='i_0'))['id']=='i_0'

    images.save_review(dict(args,item='i_0',reviewer='Dan',decision='true_issue',event_id='overturn-text'))
    assert images.page(args)[1]['total']==before


def test_projection_consumes_only_applied_text_demotion(local):
    images=LocalImages(local)
    raw=next(r for r in local.records('component_items') if r['item_uid']=='i_0')
    raw['record']['detector_kind']='chart_furniture'
    raw['record']['screening']={}
    raw['record']['measurements']={'text_support':{'would_demote':True,'demote':False}}
    with local.db:images.project_item('project',raw,raw)
    args=dict(project='project',run='r_old',verdict='all')
    assert images.page(dict(args,text_context='only'))[1]['total']==0
    raw['record']['measurements']['text_support']['demote']=True
    with local.db:images.project_item('project',raw,raw)
    rows,page,_=images.page(dict(args,text_context='only'))
    assert page['total']==1 and rows[0]['text_label_context'] is True
    assert images.page(args)[1]['total']==122


def test_retained_text_panel_audit_includes_panels_without_findings(local,tmp_path,monkeypatch):
    import hashlib
    from forensic_metascience_ai_toolkit.analysis_runs import digest
    def object_bytes(body,name):
        data=json.dumps(body).encode();sha=hashlib.sha256(data).hexdigest()
        path=tmp_path/'.analysis_runs/objects'/sha[:2]/sha
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        return dict(sha256=sha,name=name,size=len(data),paper='nested/paper',original_path='panels/text_regions/'+name)
    import numpy as np
    from metascience_observatory_image_analysis.image_forensics.text_regions import encode_mask
    from metascience_observatory_image_analysis.image_forensics.search_checkpoint import array_hash
    mask=np.zeros((10,20),bool)
    record=dict(key='fixture',status='measured',reason='no_text_detected',polygons=[],size=[20,10],
                mask_bits=encode_mask(mask),mask_sha256=array_hash(mask),mask_fraction=0.)
    localization=object_bytes(record,'localization.json')
    index=object_bytes(dict(policy='diagnostic',panels=[dict(uid=f'panel-{i:03}',status='measured',localization={'file':'localization.json'}) for i in range(103)]),'index.json')
    run=dict(id='audit_run',execution_id='audit_execution',component='image_forensics',paper='nested/paper',status='completed',items=[],artifacts={'localization':localization,'index':index})
    run['sealed_digest']=digest(run)
    local.register_root('project',tmp_path)
    assert ingest_run(local,'project',tmp_path,run)
    s=LocalImageService(local,background=False)
    args=dict(project='project',run=run['id'])
    page=s.handle('text_regions',dict(args,limit=100))
    assert page['total']==103 and len(page['panels'])==100
    assert page['pagination']['next_offset']==100
    # Listing stays compact: full masks are read only for a selected panel.
    assert 'polygons' not in page['panels'][0]
    assert len(s.handle('text_regions',dict(args,offset=100))['panels'])==3
    detail=s.handle('text_regions',dict(args,paper='nested/paper',uid='panel-000'))
    assert detail['localization']==record
    # A different machine gets shared artifact records but no private audit
    # table. Resolve the exact sealed index through the local file mapping.
    with local.db:
        local.db.execute('DELETE FROM image_text_panels WHERE run=?', [run['id']])
    reimported=s.handle('text_regions',dict(args,limit=100))
    assert reimported == page
    assert s.handle('text_regions',dict(args,paper='nested/paper',uid='panel-000'))['localization']==record
    with pytest.raises(ValueError,match='exact run'):
        s.handle('text_regions',dict(args,run='latest'))
    with pytest.raises(LookupError,match='not recorded'):
        s.handle('text_regions',dict(args,paper='nested/paper',uid='missing'))
    with pytest.raises((ValueError,LookupError)):
        s.handle('text_regions',dict(args,project='other'))
    legacy=s.handle('text_regions',dict(project='project',run='r_old'))
    assert legacy['status']=='not_recorded' and legacy['total']==0
    path=tmp_path/'.analysis_runs/objects'/localization['sha256'][:2]/localization['sha256']
    path.write_text('{}')
    summary=s.handle('text_regions',dict(args,paper='nested/paper',uid='panel-000',summary_only='true'))
    assert summary['panel']['uid']=='panel-000' and 'localization' not in summary
    with pytest.raises((ValueError,FileNotFoundError)):
        s.handle('text_regions',dict(args,paper='nested/paper',uid='panel-000'))


def test_duplicate_alias_unifies_queue_and_links_without_deleting_reviews(local):
    images=LocalImages(local)
    args=dict(project='project',run='r_old',verdict='all')
    before=images.page(args)[1]['total']
    images.save_review(dict(args,item='i_0',reviewer='Dan',decision='true_issue',event_id='duplicate-review'))
    with local.db:
        local.db.execute("insert or replace into image_imports values('project','r_old','sealed','complete',null)")
        local.db.execute("insert into image_equivalences values('project','r_old','i_0','i_1','sealed','{}','today')")
    assert images.page(args)[1]['total']==before-1
    assert images.item(dict(args,item='i_0'))['id']=='i_1'
    assert images.item(dict(args,item='i_0'))['requested_item_id']=='i_0'
    assert local.events('project','r_old','i_0')['history'][0]['event_id']=='duplicate-review'
    # Changed run data invalidates the alias instead of silently hiding evidence.
    with local.db:local.db.execute("update image_imports set digest='changed' where run='r_old'")
    assert images.page(args)[1]['total']==before
    assert images.item(dict(args,item='i_0'))['id']=='i_0'


def test_duplicate_proof_requires_both_physical_pdf_regions():
    from metascience_observatory_image_analysis.review_workbench.image_equivalence import prove_equivalence
    import copy
    a=dict(id='a',run_id='r',panels=[dict(uid='render',paper_dir='p',document=dict(path='pdf'),
        placements=[dict(page=4,bbox_kind='crop_exact',bbox=[382.56,588,450.24,639.36])]),
        dict(uid='other',paper_dir='q',document=dict(path='other-pdf'),
        placements=[dict(page=9,bbox_kind='crop_exact',bbox=[87.52,184.53,154.15,234.56])])])
    b=copy.deepcopy(a);b['id']='b';b['panels'][0]['uid']='xref';b['panels'][0]['placements'][0]['bbox']=[382.5558,588.3811,450.2885,639.4576]
    resolve=lambda d,r:dict(availability='verified',sha256=d*64)
    assert min(prove_equivalence(a,b,resolve)['overlaps'])>.98
    b['panels'][1]['placements'][0]['bbox']=[200,300,260,350]
    with pytest.raises(ValueError,match='same two'):prove_equivalence(a,b,resolve)


def test_explicit_index_scan_registers_archive_for_offline_import(local,tmp_path):
    root=tmp_path/'session'/'corpus'
    (root/'.analysis_runs').mkdir(parents=True)
    (root/'.analysis_runs/index.json').write_text('{"runs":{}}')
    index=tmp_path/'index.json'
    index.write_text(json.dumps({'projects':[{'name':'author__checked','root':str(root),'corpus':{'papers':[]}}]}))
    service=LocalImageService(local,background=False)
    assert service.handle('import_index',{'path':str(index)})['projects']==1
    assert local.roots('author__checked')[0]['path']==str(root)
    assert local.reader.execute('select path from notifications where path=?',[str(root)]).fetchone()
    assert service.local_wake.is_set()


def test_project_count_includes_local_retained_image_runs_but_not_refusals(tmp_path):
    c=Catalog(tmp_path/'counts.sqlite3')
    root=tmp_path/'corpus';root.mkdir()
    index=tmp_path/'index.json'
    index.write_text(json.dumps({'projects':[{'name':'local-author','root':str(root),'corpus':{'papers':[
        {'dir':'ran','channels':{'image_forensics':{'state':'ran'}}},
        {'dir':'refused','channels':{'image_forensics':{'state':'refused'}}},
    ]}}]}))
    c.import_index(index)
    repo=Repository(c);repo.refresh()
    row=repo.projects()['projects'][0]
    assert row['n_papers']==2
    assert row['n_image_run']==1
    c.close()


def test_shared_feed_decision_sort_matches_local_order():
    from forensic_metascience_ai_toolkit.workbench.repository import sort_feed_items
    rows=[dict(id='u',rank={'score':9}),dict(id='fp',decision={'decision':'false_positive'},rank={'score':1}),
          dict(id='c',reviews={'conflict':True},rank={'score':1}),dict(id='ti',decision={'decision':'true_issue'},rank={'score':1}),
          dict(id='chart',decision={'decision':'false_positive_chart'},rank={'score':1})]
    assert [r['id'] for r in sort_feed_items(list(rows),'decision')]==['ti','c','fp','chart','u']
    assert [r['id'] for r in sort_feed_items(list(rows),'decision','desc')]==['chart','fp','c','ti','u']


def test_ingested_items_are_typed_from_the_panel_index(local,tmp_path):
    """Journal-ingested runs had no derived type rows, so every item read
    `untyped` and the type filter offered nothing else (2026-09-26)."""
    from forensic_metascience_ai_toolkit.analysis_runs import digest
    from metascience_observatory_image_analysis.review_workbench.local_image_import import backfill_types
    paper=tmp_path/'typed'/'paper'/'panels';paper.mkdir(parents=True)
    (paper/'panel_index.json').write_text(json.dumps({'panels':[
        {'uid':'typed.pdf:xref1','panel_type':'Microscopy'},{'uid':'typed.pdf:xref2'}]}))
    item=dict(id='within:typed:IMGDUP-1',kind='within',detector_kind='transformed_match',
              paper={'dir':'typed/paper'},papers=[{'dir':'typed/paper'}],
              panels=[{'uid':'typed.pdf:xref1','paper_dir':'typed/paper'},{'uid':'typed.pdf:xref2','paper_dir':'typed/paper'}],
              rank={'score':1,'reasons':[]},cleared=False)
    run=dict(id='typed_run',execution_id='typed_e',component='image_forensics',paper='typed/paper',
             status='completed',items=[item],artifacts={})
    run['sealed_digest']=digest(run)
    local.register_root('project',tmp_path)
    assert ingest_run(local,'project',tmp_path,run)
    row=local.reader.execute("select image_type from image_queue where run='typed_run'").fetchone()
    assert row == ('Microscopy',)
    # A run ingested before typing existed is typed by the backfill.
    with local.db:
        local.db.execute("delete from records where entity='component_item_derived'")
        local.db.execute("update image_queue set image_type='untyped' where run='typed_run'")
    (tmp_path/'.analysis_runs/runs').mkdir(parents=True,exist_ok=True)
    (tmp_path/'.analysis_runs/runs/typed_run.json').write_text(json.dumps(run))
    (tmp_path/'.analysis_runs/index.json').write_text(json.dumps({'runs':{'typed_run':{'component':'image_forensics'}}}))
    assert backfill_types(local,'project',tmp_path)['items'] == 1
    row=local.reader.execute("select image_type from image_queue where run='typed_run'").fetchone()
    assert row == ('Microscopy',)


def test_image_review_counts_reach_the_landing_page(local):
    """Image decisions live only in the local image database, so the landing
    page's shared count showed 0 for a project with 372 reviewed items
    (jun_ren, 2026-09-26). Conflicting reviewers are still one reviewed item;
    a review on a run no longer queued is counted apart, not dropped."""
    service=LocalImageService(local,background=False)
    assert service.handle('image_review_counts',{})['projects']['project']['n_items']==0
    images=LocalImages(local);base=dict(project='project',run='r_old')
    images.save_review(dict(base,item='i_0',reviewer='Dan',decision='false_positive',event_id='a'))
    images.save_review(dict(base,item='i_0',reviewer='Greg',decision='true_issue',event_id='b'))
    images.save_review(dict(base,item='i_1',reviewer='Dan',decision='false_positive',event_id='c'))
    local.event('project',dict(event_id='gone',run_id='r_gone',item='i_x',reviewer='Dan',decision='false_positive',at='2026-09-01'))
    local.db.commit()
    row=service.handle('image_review_counts',{})['projects']['project']
    papers={p for (p,) in local.reader.execute("select paper from image_queue where run='r_old' and item in ('i_0','i_1')")}
    assert {k:row[k] for k in ('n_items','n_papers','n_items_other_runs')}==dict(n_items=2,n_papers=len(papers),n_items_other_runs=1)


def test_views_are_tracked_apart_from_decisions(local):
    """Opening an item is a view, not a decision (Dan, 2026-09-26). A view
    must not mark the item decided or bump the queue revision; the landing
    page counts viewed items against the queue header's own denominator."""
    # The fixture's latest run failed; make the complete r_old the latest view.
    local.set_state('image_selection:project',local.rows_for('runs','run_uid',['r_old']))
    service=LocalImageService(local,background=False);images=LocalImages(local)
    before=local.revision('project')
    total=images.feed(dict(project='project',verdict='all'))['counts']['items']
    assert total>1
    assert service.handle('image_review_counts',{})['projects']['project']['n_viewed']==0
    service.handle('image_viewed',dict(project='project',run='r_old',item='i_0',viewer='Dan'))
    service.handle('image_viewed',dict(project='project',run='r_old',item='i_0',viewer='Dan'))
    service.handle('image_viewed',dict(project='project',run='r_old',item='i_0',viewer='Greg'))
    assert local.revision('project')==before
    assert local.reader.execute("select n_views from image_views where viewer='Dan'").fetchone()==(2,)
    assert images.item(dict(project='project',run='r_old',item='i_0'))['decision'] is None
    row=service.handle('image_review_counts',{})['projects']['project']
    assert row['n_latest_items']==total and row['n_viewed']==1 and row['n_items']==0
    # A decision without opening the item is not a view.
    images.save_review(dict(project='project',run='r_old',item='i_1',reviewer='Dan',decision='false_positive'))
    assert service.handle('image_review_counts',{})['projects']['project']['n_viewed']==1
    with pytest.raises(LookupError):service.handle('image_viewed',dict(project='project',run='r_old',item='nope'))


def test_reconcile_stops_between_runs_when_the_service_is_stopping(local,tmp_path):
    """Shutdown must not wait for every sealed run to ingest; the cursor is per
    run, so a run skipped at stop time imports on the next start."""
    import threading
    from metascience_observatory_image_analysis.review_workbench.local_image_import import reconcile
    from forensic_metascience_ai_toolkit.analysis_runs import digest
    archive=tmp_path/'.analysis_runs';(archive/'runs').mkdir(parents=True)
    run=dict(id='r_new',execution_id='e_new',component='image_forensics',paper='nested/paper',status='completed',items=[],artifacts={})
    run['sealed_digest']=digest(run)
    (archive/'runs'/'r_new.json').write_text(json.dumps(run))
    (archive/'index.json').write_text(json.dumps({'runs':{'r_new':{'component':'image_forensics','sealed_digest':run['sealed_digest']}}}))
    stop=threading.Event();stop.set()
    assert reconcile(local,'project',tmp_path,stop=stop)['imported']==0
    assert not local.reader.execute("select 1 from image_imports where run='r_new'").fetchall()
    stop.clear()
    reconcile(local,'project',tmp_path,stop=stop)
    assert local.reader.execute("select state from image_imports where run='r_new'").fetchone()==('complete',)


def _sealed_corpus(root, rid='r_fresh'):
    from forensic_metascience_ai_toolkit.analysis_runs import digest
    archive=root/'.analysis_runs';(archive/'runs').mkdir(parents=True)
    run=dict(id=rid,execution_id='e_'+rid,component='image_forensics',paper='paper',status='completed',items=[],artifacts={})
    run['sealed_digest']=digest(run)
    (archive/'runs'/f'{rid}.json').write_text(json.dumps(run))
    (archive/'index.json').write_text(json.dumps({'runs':{rid:{'component':'image_forensics','sealed_digest':run['sealed_digest']}}}))


def test_ingest_root_imports_a_finished_corpus_without_the_webapp(local,tmp_path):
    """2026-09-27: a finished author stayed invisible for ten hours because
    only the page-started worker imported anything. `ingest_root` (called by
    the author launcher every two minutes) imports and marks the project
    ready with no service running, and is idempotent."""
    from metascience_observatory_image_analysis.review_workbench.local_image_import import ingest_root
    corpus=tmp_path/'author'/'analysis_sessions'/'s1'/'corpus';corpus.mkdir(parents=True)
    _sealed_corpus(corpus)
    assert ingest_root(local,'author__s1',corpus)['imported']==1
    assert local.reader.execute("select ready from image_projects where project='author__s1'").fetchone()==(1,)
    assert local.reader.execute("select state from image_imports where run='r_fresh'").fetchone()==('complete',)
    assert ingest_root(local,'author__s1',corpus)['imported']==0


def test_watch_imports_every_registered_folder_with_new_runs(local,tmp_path):
    from metascience_observatory_image_analysis.review_workbench.local_image_import import watch
    corpus=tmp_path/'c2';corpus.mkdir();_sealed_corpus(corpus,'r_watch')
    local.register_root('c2',corpus)
    lines=[]
    watch(local,once=True,log=lines.append)
    assert local.reader.execute("select state from image_imports where run='r_watch'").fetchone()==('complete',)
    assert any('"c2"' in line for line in lines)


def test_a_folder_with_no_analysis_is_an_empty_queue_not_an_error(local,tmp_path):
    """Dan, 2026-09-27: an author session prepared but never analysed showed
    'Local image records are not imported yet'. It is an empty, watched
    project; one with sealed-but-unimported runs says it is importing."""
    empty=tmp_path/'never_run';empty.mkdir();local.register_root('never_run',empty)
    images=LocalImages(local)
    images.ready('never_run')
    assert local.reader.execute("select ready from image_projects where project='never_run'").fetchone()==(1,)
    pending=tmp_path/'pending';pending.mkdir();_sealed_corpus(pending,'r_pend');local.register_root('pending',pending)
    with pytest.raises(LookupError,match='Importing 1 image run'):images.ready('pending')
    assert local.reader.execute("select 1 from notifications where path=?",[str(pending.resolve())]).fetchone()
    with pytest.raises(LookupError,match='No local folder'):images.ready('nowhere')


def test_never_analysed_project_says_so_not_clean(local,tmp_path):
    empty=tmp_path/'never';empty.mkdir();local.register_root('never',empty)
    images=LocalImages(local);images.ready('never')
    feed=images.feed(dict(project='never',run='latest'))
    assert 'No image analysis has been run' in feed['empty_reason']
    assert 'NOT a clean result' in feed['empty_reason']


def test_paper_heads_take_missing_citation_fields_from_metadata(tmp_path):
    """A cross-paper finding recorded before metadata was fetched still names
    both papers; recorded values win, and a missing file changes nothing."""
    import json as _json
    from metascience_observatory_image_analysis.review_workbench.local_images import with_citations
    paper = tmp_path / "10.1--a"
    paper.mkdir()
    (paper / "metadata.json").write_text(_json.dumps({
        "title": "A title", "authors": "X; Y", "journal": "J Biol",
        "volume": "3", "issue": "1-2", "pages": "1-9", "year": 1999}))
    heads = with_citations([
        {"dir": "10.1--a", "path": str(paper), "title": None, "journal": "Recorded"},
        {"dir": "10.1--b", "path": str(tmp_path / "absent"), "title": None},
    ])
    assert heads[0]["title"] == "A title" and heads[0]["journal"] == "Recorded"
    assert heads[0]["pages"] == "1-9" and heads[0]["authors"] == "X; Y"
    assert heads[1] == {"dir": "10.1--b", "path": str(tmp_path / "absent"), "title": None}


def test_year_sort_puts_unknown_years_last_and_reports_the_year(local):
    """Dan, 2026-09-29: a sortable paper-year column. The queue column is
    indexed data (not the item snapshot, which often lacks the year)."""
    images=LocalImages(local);base=dict(project='project',run='r_old')
    rows=local.db.execute("select rowid,item from image_queue where project='project' and run='r_old' order by item").fetchall()
    years=[2019,None,2024,2021]+[None]*(len(rows)-4)
    with local.db:
        for (rowid,_),y in zip(rows,years):local.db.execute('update image_queue set year=? where rowid=?',[y,rowid])
    def feed(direction):
        return images.feed(dict(base,verdict='all',judgments=None,sort='year',direction=direction,limit=100))['items']
    desc=[i['year'] for i in feed('desc')]
    assert desc[:3]==[2024,2021,2019] and all(y is None for y in desc[3:])
    asc=[i['year'] for i in feed('asc')]
    assert asc[:3]==[2019,2021,2024] and all(y is None for y in asc[3:])


def test_year_backfill_reads_the_paper_record(local):
    from metascience_observatory_image_analysis.review_workbench.local_images import paper_year
    assert paper_year(None,'2022-05-01')==2022 and paper_year('n.d.',1850)==1850 and paper_year('x',None) is None
    local.db.execute('alter table image_queue drop column year');local.db.commit()
    reopened=ImageCatalog(local.path)
    assert {r[1] for r in reopened.db.execute('pragma table_info(image_queue)')} >= {'year'}
    reopened.close()


def test_author_corpus_year_comes_from_the_selection_list(tmp_path):
    """Author-corpus metadata.json holds only the DOI; eligible_dois.csv two
    levels above the session corpus has the year."""
    from metascience_observatory_image_analysis.review_workbench.local_images import _selection_year
    author=tmp_path/'author';corpus=author/'analysis_sessions'/'s1'/'corpus';corpus.mkdir(parents=True)
    (author/'eligible_dois.csv').write_text('DOI,title,year,pmid\n10.1/ABC,t,2011,1\n10.1/xyz,t,,2\n')
    assert _selection_year([{'doi':'10.1/abc'}],[str(corpus)])==2011
    assert _selection_year([{'doi':'10.1/xyz'}],[str(corpus)]) is None
    assert _selection_year([{'doi':'10.1/nope'}],[str(tmp_path/'elsewhere')]) is None


def test_ingest_root_registers_the_project_with_the_shared_workbench(local,tmp_path,monkeypatch):
    """2026-09-30: Yadong Huang's results were imported into the local review
    store but the landing page (the SHARED workbench's list) never heard of
    the project. Importing must register it there too."""
    import sqlite3
    from forensic_metascience_ai_toolkit.workbench import notifications
    from metascience_observatory_image_analysis.review_workbench.local_image_import import ingest_root
    shared=tmp_path/'workbench_shared.sqlite3'
    with sqlite3.connect(shared) as conn:conn.execute('create table notifications(path text primary key)')
    monkeypatch.setattr(notifications,'cache_path',lambda:shared)
    corpus=tmp_path/'author'/'analysis_sessions'/'s1'/'corpus';corpus.mkdir(parents=True)
    _sealed_corpus(corpus,'r_shared')
    result=ingest_root(local,'author__s1',corpus)
    assert result['shared']=={'state':'notified'}
    with sqlite3.connect(shared) as conn:
        assert conn.execute('select path from notifications').fetchall()==[(str(corpus.resolve()),)]


def test_latest_selection_has_one_authority_and_a_revision(local):
    """The queue, the point read and every revision-keyed cache agree on the
    latest run. An ingest bumps the header revision BEFORE its deferred
    selection write; a request in that gap used to cache the old selection
    under the new revision for good, and `find` read a different table."""
    images=LocalImages(local);args=dict(project='project',item='i_0')
    assert [r['run_uid'] for r in images.selected(dict(project='project'))]==['r_new']
    with pytest.raises(LookupError):images.find(args)
    # A newer run supersedes r_new as the latest (here: r_new stops being eligible).
    r=local.rows_for('runs','run_uid',['r_new'])[0]
    r['history_record']={'latest_eligible':False}
    with local.lock,local.db:local.put('runs',r);local.bump('project',headers=True)
    # The gap: the revision moved, the stored selection has not.
    assert [r['run_uid'] for r in images.selected(dict(project='project'))]==['r_new']
    before=local.header_revision('project')
    images.rebuild_latest('project')
    assert local.header_revision('project')>before
    assert [r['run_uid'] for r in images.selected(dict(project='project'))]==['r_old']
    assert images.find(args)[0]=='r_old'
    assert images.feed(dict(project='project',verdict='all'))['counts']['items']==123


def test_bulk_saves_in_chunked_transactions_and_reports_progress(local,monkeypatch):
    """A 5,000-item bulk save was one transaction and fsync per item and
    outlived the bridge timer; it is now chunked, and the background job
    reports how much is durable while it runs."""
    import time
    service=LocalImageService(local,background=False)
    monkeypatch.setattr(LocalImages,'BULK_CHUNK',10)
    commits=[]
    real=local.bump
    monkeypatch.setattr(local,'bump',lambda project,**k:(commits.append(project),real(project,**k)))
    items=[dict(run='r_old',id=f'i_{n}') for n in range(25)]+[dict(run='r_old',id='nope')]
    job=service.handle('review_filter_start',dict(project='project',reviewer='Dan',decision='false_positive',items=items,component='image_forensics'))
    deadline=time.monotonic()+10
    while (status:=service.handle('job_status',{'job':job['id']}))['state']=='running' and time.monotonic()<deadline:time.sleep(0.05)
    assert status['state']=='done',status
    result=status['result']
    assert result['saved']==25 and [f['id'] for f in result['failed']]==['nope']
    assert status['progress']=={'matched':26,'to_save':26,'skipped_already_decided':0,'processed':26,'saved':25,'failed':1}
    assert len(commits)==3  # one revision bump per chunk, not per item
    assert local.reader.execute("select count(*) from image_queue where run='r_old' and decided=1 and publication_status='cleared'").fetchone()[0]==25
    # A refused row left nothing half-written.
    assert local.reader.execute("select count(*) from image_events where item='nope'").fetchone()[0]==0
    with pytest.raises(LookupError,match='outcome is unknown'):service.handle('job_status',{'job':'job_gone'})


def test_bulk_job_failure_says_how_much_was_saved(local):
    import time
    service=LocalImageService(local,background=False)
    job=service.handle('review_filter_start',dict(project='project',run='r_old',verdict='all',reviewer='Dan',decision='false_positive',expected_total=2))
    deadline=time.monotonic()+10
    while (status:=service.handle('job_status',{'job':job['id']}))['state']=='running' and time.monotonic()<deadline:time.sleep(0.05)
    assert status['state']=='failed' and 'selection changed' in status['error']
    assert status['progress'].get('saved',0)==0


def test_conflicting_reviews_can_be_resolved_without_losing_either(local):
    images=LocalImages(local);base=dict(project='project',run='r_old',item='i_4')
    with pytest.raises(ValueError,match='no conflicting'):
        images.save_review(dict(base,reviewer='Dan',decision='true_issue',resolve=True))
    images.save_review(dict(base,reviewer='Dan',decision='true_issue',event_id='a'))
    images.save_review(dict(base,reviewer='Greg',decision='false_positive',event_id='b'))
    # An imported second version of one event id is a conflict too.
    with local.db:local.db.execute('insert into image_review_conflicts values(?,?,?,?,?)',['a','project','r_old','i_4',json.dumps(dict(event_id='a',run_id='r_old',item='i_4',decision='unsure',reviewer='Dan'))])
    item=images.item(base)
    assert item['review_conflict'] and item['decision'] is None
    row=lambda:local.reader.execute("select decided,decision,publication_status from image_queue where run='r_old' and item='i_4'").fetchone()
    assert row()[:2]==(0,'conflict')
    resolved=images.save_review(dict(base,reviewer='Ana',decision='true_issue',resolve=True,event_id='r'))
    assert resolved['extra']['resolution']['resolves']==['a','b','a']
    assert images.save_review(dict(base,reviewer='Ana',decision='true_issue',resolve=True,event_id='r'))==resolved  # retry
    item=images.item(base)
    assert not item['review_conflict'] and item['decision']['event_id']=='r'
    assert len(item['reviews']['history'])==4  # both originals and the imported version kept
    assert row()==(1,'true_issue',row()[2])
    # Agreement after the resolution keeps it settled; new disagreement reopens it.
    images.save_review(dict(base,reviewer='Dan',decision='true_issue'))
    assert images.item(base)['decision']['decision']=='true_issue'
    images.save_review(dict(base,reviewer='Greg',decision='false_positive'))
    assert images.item(base)['review_conflict'] and row()[:2]==(0,'conflict')


@pytest.mark.parametrize('sort,direction',[('triage',None),('triage','desc'),('score',None),('score','asc'),('paper','desc'),('decision','asc'),('decision','desc'),('year','asc'),('year','desc')])
def test_keyset_navigation_matches_the_queue_order(local,sort,direction):
    images=LocalImages(local);base=dict(project='project',run='r_old',verdict='all')
    for n,(item,decision) in enumerate([('i_5','true_issue'),('i_50','false_positive'),('i_51','unsure'),('i_7','true_issue')]):
        images.save_review(dict(base,item=item,reviewer='Dan',decision=decision,event_id=f'k{n}'))
    with local.db:local.db.execute("update image_queue set year=case when cast(substr(item,3) as int)%3=0 then null else 2000+cast(substr(item,3) as int)%5 end")
    args=dict(base,sort=sort,**({'direction':direction} if direction else {}))
    rows=[]
    while True:
        page=images.feed(dict(args,offset=len(rows),limit=100))
        rows+=page['items']
        if page['pagination']['next_offset'] is None:break
    ids=[i['id'] for i in rows]
    for at in (0,1,4,50,len(ids)-2,len(ids)-1):
        nav=images.navigation(dict(args,item=ids[at],owner='r_old'))
        assert nav['position']==at+1 and nav['total']==len(ids)
        assert (nav['prev'] or {}).get('id')==(ids[at-1] if at else None)
        assert (nav['next'] or {}).get('id')==(ids[at+1] if at+1<len(ids) else None)
        undecided=[i['id'] for i in rows[at+1:] if not i.get('decision')]
        assert [u['id'] for u in nav['upcoming']]==undecided[:LocalImages.UPCOMING]
        assert (nav['next_undecided'] or {}).get('id')==(undecided[0] if undecided else None)


def test_queue_rows_facets_and_run_options_are_separate_requests(local):
    images=LocalImages(local);service=LocalImageService(local,background=False)
    base=dict(project='project',run='r_old',verdict='all')
    images.save_review(dict(base,item='i_3',reviewer='Dan',decision='true_issue'))
    images.save_review(dict(base,item='i_3',reviewer='Greg',decision='unsure'))
    full=images.feed(base);rows=images.feed(dict(base,facets='none'))
    assert [i['id'] for i in rows['items']]==[i['id'] for i in full['items']]
    assert rows['pagination']==full['pagination'] and rows['revision']==full['revision']
    assert not {'counts','kinds','runs','sync','judgment_counts'} & set(rows)
    facets=service.handle('feed_facets',base)
    for field in ('counts','kinds','image_types','judgment_counts','match_region_counts','facet_totals','notes','latest_info','coverage'):
        assert facets[field]==full[field],field
    assert service.handle('image_run_options',dict(project='project'))['runs']==full['runs']
    # Review state per row comes from one batched read, identical to the point read.
    for item in full['items']:
        assert item['reviews']==local.events('project',item['run_id'],item['id'])
    empty=images.feed(dict(base,facets='none',q='no such folder'))
    assert empty['items']==[] and 'none match the current filters' in empty['empty_reason']



def test_default_order_is_the_triage_rule_not_the_bare_score(local):
    """Cleared groups, then measured lookalikes, sort after everything else of
    any score (`triage_rank.sort_key`); score order stays available."""
    def rerank(item,**rank):
        row=local.reader.execute("select summary from image_queue where run='r_old' and item=?",[item]).fetchone()
        summary=json.loads(row[0]);summary['rank']={**summary['rank'],**rank}
        from metascience_observatory_image_analysis.image_forensics.triage_rank import sort_value
        with local.db:local.db.execute("update image_queue set summary=?,triage=? where run='r_old' and item=?",[json.dumps(summary),sort_value(summary['rank']),item])
    rerank('i_122',cleared=True);rerank('i_121',lookalike=True);rerank('i_3',verdict_tier=0)
    images=LocalImages(local);base=dict(project='project',run='r_old',verdict='all',limit=100)
    def ids(**k):
        rows=[];args=dict(base,**k)
        while True:
            page=images.feed(dict(args,offset=len(rows)))
            rows+=[i['id'] for i in page['items']]
            if page['pagination']['next_offset'] is None:return rows
    order=ids()
    assert order[0]=='i_3' and order[-2:]==['i_121','i_122'] and order[1]=='i_120'
    assert ids(sort='score')[:3]==['i_122','i_121','i_120']
    # The column is rebuilt from the stored ranks for a database made before it.
    local.db.execute('drop index image_queue_triage');local.db.execute('alter table image_queue drop column triage');local.db.commit()
    reopened=ImageCatalog(local.path)
    try:
        assert reopened.reader.execute("select count(*) from image_queue where triage is null").fetchone()[0]==0
        assert LocalImages(reopened).feed(dict(base))['items'][0]['id']=='i_3'
    finally:reopened.close()


def test_missed_duplications_are_immutable_recall_labels(local):
    images=LocalImages(local);service=LocalImageService(local,background=False)
    region=lambda page,box,**k:dict(paper_dir='nested/paper',document='paper.pdf',page=page,bbox_pt=box,**k)
    args=dict(project='project',reviewer='Dan',manipulation='partial_overlap',note='lane 3 reused',event_id='m1',
              regions=[region(4,[10,20,110,90],panel_uid='paper.pdf:xref7-seg2',figure='Figure 2'),region(6,[50,60,150,160])],run='r_old',item='i_1')
    before=local.revision('project')
    saved=service.handle('image_missed_record',args)
    assert saved['regions'][0]['panel_uid']=='paper.pdf:xref7-seg2' and saved['context']=={'run':'r_old','item':'i_1'}
    assert service.handle('image_missed_record',dict(args))['at']==saved['at']  # a retry is the same event
    with pytest.raises(ValueError,match='identity conflict'):service.handle('image_missed_record',dict(args,note='changed'))
    assert local.revision('project')==before  # a recall label is not a queue decision
    for bad,match in [(dict(manipulation='guess'),'manipulation'),(dict(regions=[region(1,[0,0,1,1])]),'Exactly two'),
                      (dict(regions=[region(1,[5,5,1,1]),region(1,[0,0,1,1])]),'not a box'),(dict(reviewer=''),'Reviewer')]:
        with pytest.raises(ValueError,match=match):service.handle('image_missed_record',dict(args,event_id='bad',**bad))
    assert [m['event_id'] for m in service.handle('image_missed',dict(project='project',paper='nested/paper'))['missed']]==['m1']


def test_spot_check_samples_automatic_demotions_by_kind_with_a_seed(local):
    """Context-demoted rows are never candidates; a seeded stratified sample
    per demotion kind lets a reviewer say whether the rule was right."""
    with local.db:
        local.db.execute("update image_queue set base_status='cleared',publication_status='cleared',historical_base='cleared',historical_status='cleared',detector_kind=case when cast(substr(item,3) as int)%2=0 then 'chart_furniture' else 'channel_overlay_reshow' end where run='r_old' and cast(substr(item,3) as int)<60")
    images=LocalImages(local);service=LocalImageService(local,background=False)
    base=dict(project='project',run='r_old',spot_check='7',spot_n=5)
    rows=images.feed(dict(base,limit=100))['items']
    kind_of=dict(local.reader.execute("select item,detector_kind from image_queue where run='r_old'").fetchall())
    assert len(rows)==10 and sorted(kind_of[r['id']] for r in rows)==['channel_overlay_reshow']*5+['chart_furniture']*5
    again=[r['id'] for r in images.feed(dict(base,limit=100,sort='paper'))['items']]
    assert sorted(again)==sorted(r['id'] for r in rows)  # the seed, not the order, decides the sample
    other=[r['id'] for r in images.feed(dict(base,spot_check='8',limit=100))['items']]
    assert sorted(other)!=sorted(again)
    target=rows[0]
    images.save_review(dict(project='project',run=target['run_id'],item=target['id'],reviewer='Dan',decision='unsure',
                            extra={'demotion_check':{'verdict':'wrong','kind':kind_of[target['id']],'seed':'7'}}))
    progress=service.handle('feed_facets',base)['spot_check']
    assert progress['strata'][kind_of[target['id']]]=={'population':30,'sampled':5,'right':0,'wrong':1}
    with pytest.raises(ValueError,match='demotion_check'):
        images.save_review(dict(project='project',run=target['run_id'],item=target['id'],reviewer='Dan',decision='unsure',extra={'demotion_check':{'verdict':'maybe'}}))
    # A later decision by the same reviewer keeps the spot-check verdict.
    later=images.save_review(dict(project='project',run=target['run_id'],item=target['id'],reviewer='Dan',decision='true_issue'))
    assert later['extra']['demotion_check']['verdict']=='wrong'


def test_a_decision_on_an_earlier_run_is_offered_only_for_provably_same_evidence(local,tmp_path):
    from forensic_metascience_ai_toolkit.analysis_runs import digest
    def run(rid,when,sha,uid='p.pdf:xref1'):
        item=dict(id='within:nested/paper:IMGDUP-1',kind='within',detector_kind='transformed_match',paper={'dir':'nested/paper'},
                  panels=[dict(uid=uid,paper_dir='nested/paper',image=f'__runs/{rid}/a_p1',crop_box=[0,0,10,10])],rank={'score':1})
        r=dict(id=rid,execution_id=rid+'_e',component='image_forensics',paper='nested/paper',status='completed',completed_at=when,
               items=[item],artifacts={'a_p1':dict(sha256=sha,role='panel')})
        r['sealed_digest']=digest(r)
        assert ingest_run(local,'project',tmp_path,r,dict(id=rid+'_e',name=rid,requested_components=['image_forensics'],status='completed'))
    run('ar_old','2026-03-01','a'*64);run('ar_same','2026-04-01','a'*64)
    images=LocalImages(local);service=LocalImageService(local,background=False)
    item='within:nested/paper:IMGDUP-1'
    images.save_review(dict(project='project',run='ar_old',item=item,reviewer='Dan',decision='true_issue',event_id='old'))
    offers=service.handle('image_carried',dict(project='project',run='ar_same',item=item))
    assert [(o['run'],o['decision'],o['event_id']) for o in offers['offers']]==[('ar_old','true_issue','old')]
    assert images.item(dict(project='project',run='ar_same',item=item))['decision'] is None  # never applied silently
    saved=images.save_review(dict(project='project',run='ar_same',item=item,reviewer='Ana',carry_from='ar_old',event_id='c1'))
    assert saved['decision']=='true_issue' and saved['extra']['carried_from']['event_id']=='old'
    assert service.handle('image_carried',dict(project='project',run='ar_same',item=item))['offers']==[]
    # Same item id, different pixels: shown as not provable, and refused.
    run('ar_new','2026-05-01','b'*64)
    offers=service.handle('image_carried',dict(project='project',run='ar_new',item=item))
    assert offers['offers']==[] and {o['run'] for o in offers['not_provable']}=={'ar_old','ar_same'}
    with pytest.raises(ValueError,match='not provably'):
        images.save_review(dict(project='project',run='ar_new',item=item,reviewer='Ana',carry_from='ar_old'))
    # A later ordinary decision does not inherit the provenance.
    later=images.save_review(dict(project='project',run='ar_same',item=item,reviewer='Ana',decision='unsure'))
    assert 'carried_from' not in later['extra']


def test_queue_knows_which_items_have_their_evidence_on_this_computer(local,tmp_path):
    from forensic_metascience_ai_toolkit.analysis_runs import digest
    import hashlib
    blob=b'panel pixels';sha=hashlib.sha256(blob).hexdigest()
    objects=tmp_path/'.analysis_runs/objects'/sha[:2];objects.mkdir(parents=True);(objects/sha).write_bytes(blob)
    local.register_root('project',tmp_path)
    def run(rid,when,digest_of):
        item=dict(id=f'within:nested/paper:IMGDUP-{rid}',kind='within',detector_kind='transformed_match',paper={'dir':'nested/paper'},
                  panels=[dict(uid='p.pdf:xref1',paper_dir='nested/paper',image=f'__runs/{rid}/a_p1')],rank={'score':1})
        r=dict(id=rid,execution_id=rid+'_e',component='image_forensics',paper='nested/paper',status='completed',completed_at=when,
               items=[item],artifacts={'a_p1':dict(sha256=digest_of,role='panel')})
        r['sealed_digest']=digest(r)
        ingest_run(local,'project',tmp_path,r,dict(id=rid+'_e',name=rid,requested_components=['image_forensics'],status='completed'))
    run('ar_here','2026-03-01',sha);run('ar_gone','2026-04-01','0'*64)
    images=LocalImages(local)
    before=local.revision('project')
    assert images.refresh_availability()>=2
    state=dict(local.reader.execute("select run,evidence from image_queue where run in ('ar_here','ar_gone')").fetchall())
    assert state=={'ar_here':'available','ar_gone':'missing'}
    assert local.revision('project')>before
    assert images.refresh_availability()==0  # nothing re-read until a recheck is due
    rows=images.feed(dict(project='project',run='ar_gone',verdict='all',evidence='missing'))
    assert [i['id'] for i in rows['items']]==['within:nested/paper:IMGDUP-ar_gone']
    assert {o['value']:o['count'] for o in rows['evidence_counts']}=={'missing':1}
    # The object appears (a root registered later): rechecked once due.
    gone=tmp_path/'.analysis_runs/objects/00';gone.mkdir();(gone/('0'*64)).write_bytes(b'x')
    with local.db:local.db.execute("update image_queue set evidence_checked='2000-01-01' where run='ar_gone'")
    images.refresh_availability()
    assert local.reader.execute("select evidence from image_queue where run='ar_gone'").fetchone()[0]=='available'
