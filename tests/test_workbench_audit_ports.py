"""Synthetic evidence at the audited producer/consumer seams; no shared data."""
import hashlib
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from metascience_agent.workbench.catalog import Catalog
from metascience_agent.workbench.service import Service
from metascience_observatory_image_analysis.image_forensics import retain, sweep, screening_reconcile


def records(c, **entities):
    c.apply_changes([(entity,json.dumps([r.get('id',i)]),r)
                     for entity,rows in entities.items() for i,r in enumerate(rows)], 1)


@pytest.fixture
def service(tmp_path):
    c=Catalog(tmp_path/'cache.sqlite3')
    records(c,corpora=[dict(id=1,name='audit')],
            papers=[dict(id=i,corpus_id=1,dir=f'paper-{i}') for i in (1,2)])
    try: yield Service(c,background=False)
    finally: c.close()


def test_current_sheets_do_not_alias_by_mtime_and_refresh_bytes(service,tmp_path):
    args=dict(project='audit',f='data.csv')
    for i,value in ((1,111),(2,999)):
        p=tmp_path/f'paper-{i}';p.mkdir()
        (p/'data.csv').write_text(f'value\n{value}\n')
        os.utime(p/'data.csv',ns=(1000000000,1000000000))
        service.catalog.map_paper('audit',p.name,p)
    def read(i): return service.handle('sheet',{**args,'dir':f'paper-{i}'})
    with ThreadPoolExecutor(2) as pool:
        a,b=list(pool.map(read,(1,2)))
    assert '111' in json.dumps(a) and '999' in json.dumps(b)
    (tmp_path/'paper-1/data.csv').write_text('value\n777\n')
    os.utime(tmp_path/'paper-1/data.csv',ns=(1000000000,1000000000))
    assert '777' in json.dumps(read(1))


def test_visits_visible_across_refresh_restart_and_second_connection(service):
    other=Catalog(service.catalog.path)
    try:
        second=Service(other,background=False)
        assert not second.handle('papers',{'project':'audit'})['papers'][0].get('viewed')
        for viewer in ('A','B'):
            service.handle('viewed',dict(project='audit',dir='paper-1',viewer=viewer))
        for s in (service,second,Service(other,background=False)):
            row=next(p for p in s.handle('papers',{'project':'audit'})['papers'] if p['dir']=='paper-1')
            assert row['viewed']['n_views']==2
            assert row['viewed']['viewers']==['A','B']
            assert row['viewed']['source']=='recorded'
    finally: other.close()


@pytest.mark.parametrize('decision,validated,eligible,expected',[
    ('unresolved',True,False,'unscreened'),('issue',False,False,'unscreened'),
    ('issue',True,False,'unscreened'),('innocuous',True,False,'cleared'),
    ('issue',True,True,'published')])
def test_ineligibility_is_not_clearance(service,decision,validated,eligible,expected):
    records(service.catalog,runs=[dict(id=1,run_uid='r1',paper_id=1,component='image_forensics',status='complete')],
            component_items=[dict(id=1,run_id=1,owner_paper_id=1,item_uid='i1',record=dict(screening=dict(
                decision=decision,validated=validated,confidence='high',policy='p',inputs_stamp='s')))],
            image_publication=[dict(paper_id=1,item_uid='i1',eligible=eligible,policy='p',source_fingerprint='s')])
    service.repo.refresh()
    assert service.repo.item_view(service.repo.items[1])['publication_status']==expected


@pytest.mark.parametrize('component,status,channel,retired,expected',[
    ('comprehensive','failed',None,False,None),('comprehensive','complete',None,False,None),
    ('comprehensive','complete','ran',False,0),('comprehensive','complete','ran',True,None),
    ('image_forensics','failed',None,False,None),('image_forensics','partial',None,False,None),
    ('image_forensics','complete',None,False,0)])
def test_image_count_requires_completed_image_coverage(service,component,status,channel,retired,expected):
    rows=[dict(id=1,run_uid='r1',paper_id=1,component=component,status=status)]
    if retired: rows.append(dict(id=2,run_uid='retired',paper_id=1,component='image_forensics',status='complete',retired_at='2026-01-01',retirement_reason='user_requested_rerun'))
    records(service.catalog,runs=rows,run_channels=[dict(run_id=1,channel='image_forensics',state=channel)] if channel else [])
    row=next(p for p in service.handle('papers',{'project':'audit'})['papers'] if p['dir']=='paper-1')
    assert row['n_image_findings'] is expected
    if retired: assert row['image_status']=='awaiting a new analysis'


def test_live_non_image_sort_before_pagination(service):
    records(service.catalog,runs=[dict(id=i,run_uid=f'r{i}',paper_id=i,component='comprehensive',status='complete') for i in (1,2)],
        findings=[dict(id=i,run_id=1 if i<10 else 2,paper_id=1 if i<10 else 2,finding_id=f'f{i}',
                       producer='image_track' if i<10 else 'tool_expert',outcome='problem') for i in range(12)])
    page=service.handle('papers',dict(project='audit',sort='findings',direction='desc',limit=1))
    assert page['papers'][0]['n_non_image_findings']==2




def test_sweep_preserves_nested_identity_and_cumulative_child_furniture(tmp_path,monkeypatch):
    dirs=[tmp_path/d/'paper' for d in ('a','b')]
    for d in dirs:d.mkdir(parents=True)
    sweep.save_corpus_furniture(tmp_path,{'old'},{},'before')
    monkeypatch.setattr(sweep,'corpus_papers',lambda c:dirs)
    screens=iter([dict(sha256=[],min_papers=2),dict(sha256=['new'],min_papers=2)])
    monkeypatch.setattr(sweep,'corpus_furniture',lambda ds:next(screens))
    monkeypatch.setattr(retain,'panel_shas',lambda d:{'old','new'})
    seen=[]
    async def run(jobs_,*,jobs,timeout_s,on_done):
        for d,args in jobs_:
            seen.append((d.relative_to(tmp_path).as_posix(),json.loads(Path(args[args.index('--furniture-from')+1]).read_text())['sha256']))
            on_done(d,dict(output=dict(status=dict(ran=True),result=dict(n_duplicate_groups=0))))
    monkeypatch.setattr(sweep,'_run_papers',run)
    result=sweep.run_sweep(tmp_path,sweep_id='audit',force=True,progress=False,panel_detector='gutter',log=lambda s:None)
    assert [x[1] for x in seen]==[['old'],['old'],['new','old'],['new','old']]
    assert result['n_rows']==2
    assert {x[0] for x in seen}=={'a/paper','b/paper'}
    with pytest.raises(ValueError,match='Ambiguous'):
        sweep.run_sweep(tmp_path,sweep_id='ambiguous',papers=['paper'],progress=False,panel_detector='gutter',log=lambda s:None)


def test_nested_cross_survivor_has_exactly_one_owner(tmp_path,monkeypatch):
    (tmp_path/'.image_track').mkdir()
    owners=[tmp_path/d/'paper' for d in ('nested','other')]
    for p in owners:p.mkdir(parents=True)
    item=dict(kind='cross',source_id='cross1',papers=[dict(dir='nested/paper'),dict(dir='other/paper')],
        panels=[dict(uid='a',placements=[]),dict(uid='b',placements=[])],figure_labels=['Figure 1'],
        screening=dict(explanation='Measured reuse',fingerprint='fp',decision='issue',confidence='high'))
    from metascience_observatory_image_analysis import image_review
    monkeypatch.setattr(image_review,'_within_items',lambda *a:[])
    results=[screening_reconcile.image_document({'findings':[]},p,[item]) for p in owners]
    assert [len(r['findings']) for r in results]==[1,0]
    assert results[0]['findings'][0]['inputs']['image_scope']=='cross'






def test_archived_xml_preferred_with_verified_pdf_toggle(tmp_path):
    from tests.test_workbench_integration import source_catalog
    c,xml=source_catalog(tmp_path)
    try:
        pdf=tmp_path/'article.pdf';pdf.write_bytes(b'%PDF-1.4 fixture')
        sha=hashlib.sha256(pdf.read_bytes()).hexdigest();c.register_file(pdf,sha)
        c.apply_changes([('run_artifacts','[1, "pdf"]',dict(run_id=1,artifact_uid='pdf',role='source_pdf',
            content_sha256=sha,record=dict(name='article.pdf')))],2)
        s=Service(c,background=False);args=dict(project='project',dir='paper',run='r1')
        article=s.source(args)['article']
        assert article['mode']=='xml' and article['has_pdf'] and article['has_xml']
        assert article['pdf_relpath']=='__runs/r1/pdf'
        assert 'archived result was 42' in article['html']
        pdf.write_bytes(b'changed')
        article=s.source(args)['article']
        assert article['mode']=='xml' and not article['has_pdf']
        assert 'pdf_relpath' not in article
        xml.write_text('changed')
        assert s.source(args)['availability']=='unavailable'
    finally:c.close()




def test_reconcile_files_stops_when_the_service_is_stopping(tmp_path):
    """Shutdown joins the file monitor; a full reconciliation pass over a large
    catalog must return once `stop` is set rather than finish every paper."""
    c=Catalog(tmp_path/'cache.sqlite3')
    root=tmp_path/'corpus'; root.mkdir()
    records(c,corpora=[dict(id=1,name='audit')],
            papers=[dict(id=i,corpus_id=1,dir=f'paper-{i}') for i in range(50)])
    c.register_root('audit',str(root))
    for i in range(50): (root/f'paper-{i}').mkdir()
    try:
        s=Service(c,background=False)
        s.reconcile_files()
        assert len(c.local_papers())==50
        for i in range(50): (root/f'paper-{i}'/'x.pdf').write_bytes(b'%PDF')
        s.stop.set()
        s.reconcile_files()
        # Nothing was rewritten after the stop: the pass broke out at once.
        assert all(not json.loads(row[2]).get('sources',{}).get('pdf') for row in
                   c.db.execute('select project,dir,body from papers_local').fetchall())
    finally: c.close()
