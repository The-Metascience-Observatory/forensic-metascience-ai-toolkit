"""Exercise real SQLite output, restart, conflicts, pagination and media boundaries."""
import json
from pathlib import Path

import pytest

from metascience_agent.workbench.catalog import Catalog
from metascience_agent.workbench.repository import Repository, adjudicator_output
from metascience_agent.workbench.service import Service
from metascience_agent.workbench.remote import migration_sql


def seed(c):
    records={
        'corpora':[{'id':1,'name':'project'}],
        'papers':[{'id':1,'corpus_id':1,'dir':'nested/paper','doi':'10.1/x','title':'A paper'},
                  {'id':2,'corpus_id':1,'dir':'other/paper','doi':'10.1/x'}],
        'runs':[{'id':1,'run_uid':'r_old','paper_id':1,'component':'image_forensics','status':'complete','execution_status':'completed','analysed_at':'2026-01-01','execution_uid':'e_old'},
                {'id':2,'run_uid':'r_new','paper_id':1,'component':'image_forensics','status':'failed','execution_status':'failed','analysed_at':'2026-02-01','execution_uid':'e_new'}],
        'executions':[{'execution_uid':'e_old','corpus_id':1,'name':'Old','status':'completed','requested_components':['image_forensics']},
                      {'execution_uid':'e_new','corpus_id':1,'name':'New','status':'failed','requested_components':['image_forensics']}],
        'component_items':[{'id':i+1,'run_id':1,'owner_paper_id':1,'item_uid':f'i_{i}', 'record':{
            'id':f'i_{i}','sentence':f'Candidate {i}','kind':'within','detector_kind':'exact',
            'paper':{'dir':'nested/paper'},'panels':[], 'rank':{'score':i},
            'screening':{'validated':True,'decision':'issue','confidence':'high','policy':'p','inputs_stamp':'s'}}} for i in range(123)],
    }
    changes=[]
    for entity,rows in records.items():
        for r in rows: changes.append((entity,json.dumps([r.get('id') or r.get('execution_uid')]),r))
    c.apply_changes(changes,1)


@pytest.fixture
def catalog(tmp_path):
    c=Catalog(tmp_path/'local/cache.sqlite3'); seed(c)
    yield c
    c.close()


@pytest.mark.usefixtures("image_package")
def test_selected_failed_run_does_not_substitute_older_results(catalog):
    r=Repository(catalog); r.refresh()
    latest=r.feed({'project':'project'})
    assert latest['items']==[]
    assert latest['coverage']['states']=={'failed':1}
    assert r.feed({'project':'project','run':'r_old'})['pagination']['total']==123
    with pytest.raises(ValueError,match='not recorded'):
        r.feed({'project':'project','run':'missing'})


@pytest.mark.usefixtures("image_package")
def test_server_filters_and_pages_before_serialization(catalog):
    r=Repository(catalog); r.refresh()
    first=r.feed({'project':'project','run':'r_old'})
    second=r.feed({'project':'project','run':'r_old','offset':50})
    assert len(first['items'])==len(second['items'])==50
    assert {i['id'] for i in first['items']}.isdisjoint(i['id'] for i in second['items'])
    assert first['items'][0]['id']=='i_122'
    assert first['pagination']=={'offset':0,'limit':50,'total':123,'next_offset':50}
    assert len(json.dumps(first).encode())<250_000
    assert r.feed({'project':'project','run':'r_old','kind':'absent'})['pagination']['total']==0


@pytest.mark.parametrize('item,label', [
    ({'screening': {'decision': None, 'confidence': None}}, 'No saved AI judgment'),
    ({'screening': {}}, 'No saved AI judgment'),
    ({}, 'No saved AI judgment'),
    ({'screening': None, 'adjudication': None}, 'No saved AI judgment'),
    ({'cleared': True}, 'Automatically cleared — AI not needed'),
    ({'cleared': True, 'screening': {}}, 'Automatically cleared — AI not needed'),
    ({'adjudication': {'verdict': 'explained', 'category': 'source_alias'}}, 'explained · source_alias'),
    ({'screening': {'decision': None}, 'adjudication': {'verdict': 'explained'}}, 'explained'),
])
def test_adjudicator_missing_and_legacy_outputs(item, label):
    assert adjudicator_output(item) == label


@pytest.mark.usefixtures("image_package")
def test_adjudicator_filter_precedes_pagination_and_facets_cover_whole_run(catalog):
    rows = catalog.records('component_items')
    # The lowest ranked item is outside the first two unfiltered pages.
    row = next(row for row in rows if row['item_uid'] == 'i_0')
    row['record']['screening']['decision'] = 'innocuous'
    catalog.apply_changes([('component_items', json.dumps([row['id']]), row)], 2)
    r = Repository(catalog); r.refresh()
    args = {'project': 'project', 'run': 'r_old', 'verdict': 'all'}
    first = r.feed(args)
    expected = [
        {'value': 'Saved AI judgment: innocuous · high', 'count': 1},
        {'value': 'Saved AI judgment: issue · high', 'count': 122},
    ]
    assert first['adjudicator_outputs'] == expected
    filtered = r.feed({**args, 'adjudicator': expected[0]['value']})
    assert [i['id'] for i in filtered['items']] == ['i_0']
    assert filtered['pagination']['total'] == 1
    assert filtered['adjudicator_outputs'] == expected
    selected = r.feed({**args, 'judgments': '["issue", "unresolved"]'})
    assert selected['pagination']['total'] == 122
    assert r.feed({**args, 'judgments': ['issue', 'innocuous']})['pagination']['total'] == 123
    assert r.feed({**args, 'judgments': '[]'})['pagination']['total'] == 0
    assert r.feed({**args, 'adjudicator': 'not adjudicated'})['pagination']['total'] == 0


def test_snapshot_publish_is_atomic_and_cache_invalidation_works(catalog):
    catalog.save_detail('runs','[1]',{'old':True},catalog.record_token('runs','[1]'))
    gen=catalog.begin_snapshot()
    catalog.stage_snapshot(gen,'corpora',[('[2]',{'id':2,'name':'new'})])
    assert catalog.records('corpora')[0]['name']=='project'
    catalog.finish_snapshot(gen,23)
    assert catalog.records('corpora')==[{'id':2,'name':'new'}]
    assert catalog.state('cursor')==23 and catalog.detail('runs','[1]') is None
    old=catalog.record_token('corpora','[2]')
    catalog.apply_changes([('corpora','[2]',None)],24)
    assert catalog.records('corpora')==[]
    assert not catalog.save_detail('corpora','[2]',{},old)


@pytest.mark.usefixtures("image_package")
def test_offline_reviews_survive_restart_and_disagreement_is_not_hidden(catalog):
    r=Repository(catalog); r.refresh()
    a=r.save_review({'project':'project','run':'r_old','item':'i_1','decision':'true_issue','reviewer':'A'})
    r.refresh()
    b=r.save_review({'project':'project','run':'r_old','item':'i_1','decision':'false_positive_other','reviewer':'B'})
    assert a['pending'] and b['pending']
    reopened=Catalog(catalog.path)
    try:
        rr=Repository(reopened);rr.refresh()
        j=rr.judgments('r_old','i_1')
        assert j['conflict'] and j['decision'] is None and len(j['reviewers'])==2
        assert len(j['history'])==2
        item=next(i for i in rr.feed({'project':'project','run':'r_old','offset':100})['items'] if i['id']=='i_1')
        assert item['publication_status']=='published'
    finally: reopened.close()


def test_a_root_is_discovered_from_the_shared_records_papers_root_when_it_exists_here(tmp_path):
    """The sweep records where THIS machine read the corpus (`corpora.papers_root`).
    A viewer that never received the local notification (another process, a
    cache created later) could see rows for archived artifacts and had no
    way to find them: "Missing PDF" and grey panels on every image page (Dan,
    2026-09-14). The hint is used only when the folder exists on this disk;
    another machine's path is ignored, and a symlink is refused."""
    here=tmp_path/'corpus'; (here/'nested'/'paper').mkdir(parents=True)
    c=Catalog(tmp_path/'cache.sqlite3')
    try:
        c.apply_changes([('corpora',json.dumps([i]),r) for i,r in enumerate([
            {'id':1,'name':'project','papers_root':str(here)},
            {'id':2,'name':'elsewhere','papers_root':'/no/such/machine/corpus'},
            {'id':3,'name':'other','papers_root':None}],1)],1)
        assert c.roots('project')==[]
        assert c.paper_path('project','nested/paper')==here/'nested'/'paper'
        assert [r['path'] for r in c.roots('project')]==[str(here)]
        with pytest.raises(FileNotFoundError, match="no local folder is registered for project 'elsewhere'"):
            c.paper_path('elsewhere','nested/paper')
        assert c.discover_root('other') is None
        link=tmp_path/'link'; link.symlink_to(here)
        c.apply_changes([('corpora',json.dumps([4]),{'id':4,'name':'linked','papers_root':str(link)})],2)
        assert c.discover_root('linked') is None
    finally: c.close()


@pytest.mark.usefixtures("image_package")
def test_two_computers_same_findings_independent_file_availability(catalog,tmp_path):
    other=Catalog(tmp_path/'second/cache.sqlite3');seed(other)
    try:
        a=Repository(catalog);a.refresh();b=Repository(other);b.refresh()
        assert a.feed({'project':'project','run':'r_old'})['items']==b.feed({'project':'project','run':'r_old'})['items']
        folder=tmp_path/'outside-dropbox';folder.mkdir()
        catalog.map_paper('project','nested/paper',folder)
        assert catalog.paper_path('project','nested/paper')==folder
        # The message names the missing ROOT and its project: beside "no DOI
        # on disk" it used to read as though the paper had no PDF.
        with pytest.raises(FileNotFoundError, match=r"no local folder is registered for project 'project'"):
            other.paper_path('project','nested/paper')
        assert a.resolve_paper('project',directory='other/paper')['id']==2
        with pytest.raises(ValueError,match='Ambiguous'):a.resolve_paper('project',slug='paper')
    finally:other.close()


@pytest.mark.usefixtures("image_package")
def test_hash_validation_changed_files_and_traversal(catalog,tmp_path):
    media=tmp_path/'image.png';media.write_bytes(b'original')
    import hashlib
    sha=hashlib.sha256(b'original').hexdigest()
    catalog.register_file(media,sha)
    assert catalog.file_for(sha)==str(media)
    media.write_bytes(b'modified')
    assert catalog.file_for(sha) is None
    with pytest.raises(ValueError,match='hash'):catalog.register_file(media,sha)
    catalog.map_paper('project','nested/paper',tmp_path)
    service=Service(catalog,background=False)
    with pytest.raises(ValueError):service.artifact({'project':'project','dir':'nested/paper','f':'../outside'})


@pytest.mark.usefixtures("image_package")
def test_no_network_or_python_process_on_summary_reads(catalog,monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('spawned a child'))
    class Offline:
        def connect(self):pytest.fail('connected to Neon')
    s=Service(catalog,Offline(),background=False)
    assert s.handle('projects',{})['n_papers']==2
    assert len(s.handle('feed',{'project':'project','run':'r_old'})['items'])==50
    assert len(s.handle('papers',{'project':'project'})['papers'])==2


def test_a_failed_landing_page_warmup_is_named_not_discarded(catalog):
    """The background loop warms the landing-page summary after each sync. A
    warm-up that raised used to vanish (`except Exception: pass`), so a slow
    landing page read as merely cold. It is now in `status()`, and cleared by
    the next warm-up that works."""
    class Quiet:
        bytes=0
        def sync(self,catalog):pass
        def close(self):pass
    s=Service(catalog,Quiet(),background=False)
    def once(interval):s.stop.set();return True
    s.wake.wait=once
    def broken():raise RuntimeError('projection unavailable')
    s.projects=broken
    s.background()
    assert catalog.status()['warmup_error']=='RuntimeError: projection unavailable'
    s.stop.clear();s.projects=lambda:{}
    s.background()
    assert catalog.status()['warmup_error'] is None


def test_migration_artifact_matches_generator():
    text=Path('db/migrations/004_workbench.sql').read_text()
    assert text.split('\n',1)[1]==migration_sql()


def test_second_app_observes_external_sqlite_changes(catalog):
    other=Catalog(catalog.path)
    try:
        r=Repository(catalog);r.refresh()
        other.apply_changes([('corpora','[1]',{'id':1,'name':'renamed'})],2)
        r.refresh()
        assert r.project_ids=={'renamed':1}
    finally:other.close()


def test_metadata_patch_keeps_same_reviewer_judgment_and_other_fields(catalog):
    r=Repository(catalog);r.refresh()
    r.save_review(dict(project='project',run='r_old',item='i_0',reviewer='A',decision='true_issue',note='Confirmed',extra={'pubpeer_url':'https://example.org'}))
    r.refresh()
    r.save_review(dict(project='project',run='r_old',item='i_0',reviewer='A',extra={'submitted_to_pubpeer':True}))
    r.refresh()
    decision=r.judgments('r_old','i_0')['decision']
    assert decision['decision']=='true_issue' and decision['note']=='Confirmed'
    assert decision['extra']=={'pubpeer_url':'https://example.org','submitted_to_pubpeer':True}


def test_unrelated_sync_state_does_not_discard_fetched_detail(catalog):
    token=catalog.record_token('runs','[1]')
    catalog.set_state('bytes_received',123)
    assert catalog.save_detail('runs','[1]',{'content':'preserved'},token)


def test_parent_link_alone_does_not_hide_component_candidate(catalog):
    catalog.apply_changes([
        ('runs','[3]',{'id':3,'run_uid':'report','paper_id':1,'component':'comprehensive','status':'complete','analysed_at':'2026-01-01'}),
        ('findings','[1]',{'id':1,'run_id':3,'paper_id':1,'finding_id':'F1','legacy_original_id':'different','outcome':'problem','severity':4}),
    ],2)
    r=Repository(catalog);r.refresh()
    candidate=r.items[1]
    r.runs[1]['parent_run_uid']='report'
    assert not r.represented(candidate,[r.runs[3]])
    r.findings[1]['legacy_original_id']='i_0'
    assert r.represented(candidate,[r.runs[3]])


def test_offline_duplicate_retry_retains_event_timestamp(catalog):
    r=Repository(catalog);r.refresh()
    args=dict(project='project',run='r_old',item='i_0',reviewer='A',decision='true_issue',event_id='rv_retry')
    first=r.save_review(args);r.refresh()
    second=r.save_review(args)
    assert first['at']==second['at'] and len(catalog.pending())==1
    with pytest.raises(ValueError,match='conflict'):
        r.save_review({**args,'decision':'unsure'})


@pytest.mark.usefixtures("image_package")
def test_conflict_does_not_republish_revoked_finding(catalog):
    r=Repository(catalog);r.refresh()
    for reviewer,decision in [('A','true_issue'),('B','false_positive_other')]:
        r.save_review(dict(project='project',run='r_old',item='i_0',reviewer=reviewer,decision=decision));r.refresh()
    r.publication[(1,'i_0')]={'eligible':False,'policy':'p','source_fingerprint':'s'}
    view=r.item_view(r.items[1])
    assert view['reviews']['conflict'] and view['publication_status']=='unscreened'
    assert 'not a scientific clearance' in view['eligibility_detail']


def test_importer_reports_unrepresentable_records_without_altering_archives(tmp_path,monkeypatch):
    from metascience_agent.workbench import importer
    from metascience_agent import history_db,history_publication
    class Connection:
        def execute(self,*args):
            if 'pg_size_bytes' in args[0]:
                class Cursor:
                    def fetchone(self): return (None,0)
                return Cursor()
            return []
    class Remote:
        def connect(self): return Connection()
        def close(self): pass
    monkeypatch.setattr(importer,'Remote',Remote)
    monkeypatch.setattr(history_publication,'sync',lambda *a:{})
    uploaded=[]
    monkeypatch.setattr(history_db,'sync',lambda root,conn,runs: uploaded.extend(runs) or {'runs':len(runs),'items':0,'reviews':0})
    root=tmp_path/'corpus';folder=root/'.analysis_runs/runs';folder.mkdir(parents=True)
    rows=[{'id':'good','sealed_digest':'g'},{'id':'bad','sealed_digest':'b','caption':'bad\x00text'},
          {'id':'child','sealed_digest':'c','parent_run_id':'bad'}]
    for row in rows:(folder/(row['id']+'.json')).write_text(json.dumps(row))
    before=(folder/'bad.json').read_bytes()
    result=importer.migrate(root)
    assert uploaded==['good']
    assert {e['run'] for e in result['errors']}=={'bad','child'}
    assert (folder/'bad.json').read_bytes()==before


@pytest.mark.usefixtures("image_package")
def test_judgment_counts_are_faceted_not_whole_run(catalog):
    """Judgment counts answer "how many would I get if I picked this", given
    the OTHER filters.

    They used to describe the whole selection regardless of every other
    filter, which made them useless as soon as one was set -- Dan asked for
    dynamic counts on 2026-09-15 and this test now pins that. Two things must
    NOT move them: pagination (a page is not a filter) and the judgments
    filter itself (a facet that counted its own selection would report zero
    for every option the user had not picked).
    """
    rows = catalog.records('component_items')
    for uid, screen in [('i_0', {'decision': 'unresolved'}),
                        ('i_1', {'decision': 'innocuous'}), ('i_2', {}), ('i_3', None)]:
        row = next(r for r in rows if r['item_uid'] == uid)
        row['record']['screening'] = screen
        if uid == 'i_3':
            row['record']['adjudication'] = {'verdict': 'explained'}
        catalog.apply_changes([('component_items', json.dumps([row['id']]), row)], 2)
    repo = Repository(catalog); repo.refresh()
    args = {'project': 'project', 'run': 'r_old', 'verdict': 'all'}
    expected = {'issue': 119, 'unresolved': 1, 'innocuous': 1, 'missing': 1, 'legacy': 1}
    for filters in ({}, {'offset': 50}, {'judgments': ['issue']}):
        assert repo.feed({**args, **filters})['judgment_counts'] == expected
    # ...but another facet DOES narrow them: nothing has this kind, so there
    # is nothing left to count.
    assert repo.feed({**args, 'kind': 'absent'})['judgment_counts'] == {}
    assert repo.feed({'project': 'project'})['judgment_counts'] == {}


@pytest.mark.usefixtures("image_package")
def test_automatic_clearance_has_its_own_filter_and_count(catalog):
    rows = catalog.records('component_items')
    for uid, cleared in [('i_0', True), ('i_1', False)]:
        row = next(r for r in rows if r['item_uid'] == uid)
        row['record'].update(screening={}, cleared=cleared)
        catalog.apply_changes([('component_items', json.dumps([row['id']]), row)], 2)
    repo = Repository(catalog); repo.refresh()
    args = {'project': 'project', 'run': 'r_old', 'verdict': 'all'}
    result = repo.feed({**args, 'judgments': ['automatic_clearance']})
    assert [i['id'] for i in result['items']] == ['i_0']
    assert result['judgment_counts']['automatic_clearance'] == 1
    assert result['judgment_counts']['missing'] == 1
    assert [i['id'] for i in repo.feed({**args, 'judgments': ['missing']})['items']] == ['i_1']
    assert adjudicator_output({'cleared': True, 'screening': {'decision': 'innocuous'}}).startswith('Saved AI judgment: innocuous')


def test_latest_cross_execution_keeps_its_batches_without_old_tail(catalog):
    rows=[]
    for i,(execution,ordinal,date) in enumerate((('e_old',0,'2026-01-01'),
                                                ('e_old',1,'2026-01-01'),
                                                ('e_new',0,'2026-02-01')),10):
        row={'id':i,'run_uid':f'cross_{i}','paper_id':None,'component':'image_forensics',
             'status':'complete','execution_status':'completed','analysed_at':date,'execution_uid':execution,
             'history_record':{'scope_key':f'cross:complete:{ordinal}','selection_family':'cross:complete'}}
        rows.append(('runs',json.dumps([i]),row))
    catalog.apply_changes(rows,2)
    repository=Repository(catalog);repository.refresh()
    latest=repository.selected_runs('project',kind='image_forensics')
    assert {r['run_uid'] for r in latest if r['paper_id'] is None}=={'cross_12'}
    old=repository.selected_runs('project',selection='e_old',kind='image_forensics')
    assert {r['run_uid'] for r in old if r['paper_id'] is None}=={'cross_10','cross_11'}


def test_projects_summary_is_cached_per_catalog_version(catalog,monkeypatch):
    """The landing page recomputed a full-catalog projection per load
    (~12 s measured 2026-09-26). Same version: no reload. New version: fresh."""
    s=Service(catalog,background=False)
    first=s.handle('projects',{})
    monkeypatch.setattr(Repository,'projects',lambda self:pytest.fail('recomputed at the same version'))
    assert s.handle('projects',{})['projects']==first['projects']
    monkeypatch.undo()
    with catalog.db:catalog.db.execute("update cache_revisions set revision=revision+1 where scope='local'")
    catalog.map_paper('project','extra/paper',catalog.path.parent)
    assert s.handle('projects',{})['n_papers']==first['n_papers']+1
