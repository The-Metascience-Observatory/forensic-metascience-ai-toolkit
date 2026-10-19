"""Real PostgreSQL contract tests in disposable schemas, never production tables.
Run with METASCIENCE_TEST_POSTGRES=1. Credentials use the existing resolver.
"""
import json
import os
import threading
import time
import uuid
from pathlib import Path

import pytest
from metascience_agent.db_push import _connect, resolve_db_url
LIVE_URL=resolve_db_url() if os.environ.get("METASCIENCE_TEST_POSTGRES")=="1" else None
from metascience_agent.workbench.remote import Remote
from metascience_agent.workbench.catalog import Catalog

pytestmark=pytest.mark.skipif(os.environ.get('METASCIENCE_TEST_POSTGRES')!='1',reason='explicit Postgres integration opt-in')


@pytest.fixture
def remote():
    schema='wb_test_'+uuid.uuid4().hex
    conn=_connect(LIVE_URL,connect_timeout=5);conn.autocommit=True
    conn.execute(f'create schema {schema}')
    conn.execute(f'set search_path={schema}')
    try:
        conn.execute(Path('db/schema.sql').read_text())
        r=Remote();r.conn=conn;r.migrate()
        conn.execute("insert into corpora(name) values('test')")
        conn.execute("insert into papers(corpus_id,dir,title) values(1,'paper','Paper')")
        conn.execute("insert into runs(paper_id,run_uid,kind,component,status) values(1,'r1','image_track','image_forensics','complete')")
        conn.execute("insert into component_items(run_id,item_uid,owner_paper_id,record) values(1,'i1',1,%s::jsonb)",[json.dumps({'id':'i1','paper':{'dir':'paper'},'panels':[],'screening':{'validated':True,'decision':'issue','confidence':'high'},'measurements':{'large':'x'*10000}})])
        yield r,schema
    finally:
        conn.execute('set search_path=public')
        conn.execute(f'drop schema {schema} cascade')
        conn.close()


def test_bootstrap_detail_deltas_and_delete(remote,tmp_path):
    r,schema=remote;c=Catalog(tmp_path/'cache.sqlite3')
    try:
        r.sync(c)
        item=c.records('component_items')[0]
        assert 'measurements' not in item['record']
        assert r.detail('component_items','[1]')['record']['measurements']['large']=='x'*10000
        original=c.state('cursor')
        r.conn.execute("update papers set title='Changed' where id=1")
        r.sync(c)
        assert c.records('papers')[0]['title']=='Changed' and c.state('cursor')>original
        r.conn.execute('delete from component_items where id=1');r.sync(c)
        assert c.records('component_items')==[]
    finally:c.close()


def test_journal_cursor_cannot_skip_uncommitted_earlier_writer(remote,tmp_path):
    r,schema=remote;c=Catalog(tmp_path/'cache.sqlite3');r.sync(c)
    a=_connect(LIVE_URL,connect_timeout=5);b=_connect(LIVE_URL,connect_timeout=5)
    for conn in (a,b):
        conn.autocommit=True;conn.execute(f'set search_path={schema}')
    blocked=threading.Event();finished=threading.Event();errors=[]
    try:
        a.execute('begin');a.execute("update papers set title='A' where id=1")
        def write_b():
            try:
                blocked.set();b.execute("insert into corpora(name) values('B')");finished.set()
            except Exception as exc:errors.append(exc)
        t=threading.Thread(target=write_b);t.start();assert blocked.wait(2)
        assert not finished.wait(.2)
        r.sync(c);assert c.records('papers')[0]['title']=='Paper'
        a.execute('commit');t.join(10);assert finished.is_set() and not errors
        r.sync(c);assert c.records('papers')[0]['title']=='A'
        assert any(p['name']=='B' for p in c.records('corpora'))
    finally:a.close();b.close();c.close()


def test_review_retry_identity_and_shared_conflict(remote,tmp_path):
    from metascience_agent.workbench.repository import Repository
    r,schema=remote;c=Catalog(tmp_path/'cache.sqlite3')
    try:
        # A non-UTC session returns timestamptz as '...20:00-04:00'; a retry of
        # the same 'Z' event must still be recognised as the same event.
        r.conn.execute("set timezone='America/New_York'")
        e=dict(event_id='rv_one',run_id='r1',item='i1',decision='true_issue',reviewer='A',note='',at='2026-09-10T00:00:00Z')
        r.send_review(e);r.send_review(e)
        assert r.conn.execute('select count(*) from reviews').fetchone()[0]==1
        with pytest.raises(ValueError,match='conflict'):r.send_review({**e,'decision':'unsure'})
        with pytest.raises(ValueError,match='conflict'):r.send_review({**e,'at':'2026-09-10T00:00:01Z'})
        r.send_review({**e,'event_id':'rv_two','reviewer':'B','decision':'false_positive_other'})
        r.sync(c);repo=Repository(c);repo.refresh()
        assert repo.judgments('r1','i1')['conflict']
    finally:c.close()


def test_two_apps_bootstrap_same_private_cache_without_partial_snapshot(remote,tmp_path):
    r,schema=remote
    a=Catalog(tmp_path/'shared.sqlite3');b=Catalog(a.path)
    conn=_connect(LIVE_URL,connect_timeout=5);conn.autocommit=True;conn.execute(f'set search_path={schema}')
    other=Remote();other.conn=conn
    errors=[]
    def sync(peer,cache):
        try:peer.sync(cache)
        except Exception as exc:errors.append(exc)
    threads=[threading.Thread(target=sync,args=(r,a)),threading.Thread(target=sync,args=(other,b))]
    try:
        for thread in threads:thread.start()
        for thread in threads:thread.join(20)
        assert not errors and not any(t.is_alive() for t in threads)
        assert len(a.records('papers'))==len(a.records('runs'))==len(a.records('component_items'))==1
    finally:other.close();a.close();b.close()


def test_retirement_preserves_replacement_and_invalidates_cached_detail(remote,tmp_path):
    from metascience_agent.workbench.retirement import apply,migrate
    r,schema=remote;c=Catalog(tmp_path/'cache.sqlite3')
    try:
        migrate(r.conn)
        r.conn.execute("update runs set sealed_digest='sealed' where run_uid='r1'")
        r.conn.execute("update runs set analysed_at='2026-01-01' where run_uid='r1'")
        r.conn.execute("insert into runs(paper_id,run_uid,kind,component,status,analysed_at) values(1,'r2','image_track','image_forensics','complete','2026-02-01')")
        r.sync(c)
        c.save_detail('component_items','[1]',{'full':'cached'},c.record_token('component_items','[1]'))
        r.conn.execute("update component_items set record=(record::text)::jsonb where id=1")
        with pytest.raises(Exception,match='sealed component evidence'):
            r.conn.execute("update component_items set record='{}'::jsonb where id=1")
        result=apply(r.conn,[{'run_uid':'r1','replacement':'r2'}])
        assert result['runs']==result['items']==1
        assert r.conn.execute("select record->>'retired' from component_items where id=1").fetchone()[0]=='true'
        r.sync(c)
        assert c.detail('component_items','[1]') is None
        assert apply(r.conn,[{'run_uid':'r1','replacement':'r2'}])['runs']==0
        assert apply(r.conn,[{'run_uid':'r2','replacement':'r1'}])['runs']==0
    finally:c.close()


def test_publication_uses_shared_records_with_missing_local_corpus(remote,tmp_path,monkeypatch):
    from metascience_agent import history_publication
    from metascience_observatory_image_analysis.image_forensics.screening import POLICY
    r,_ = remote
    conn = r.connect()
    screen = json.dumps({'policy':POLICY,'decision':'issue','validated':True,
                         'confidence':'high','inputs_stamp':'original-machine-stamp'})
    conn.execute("update component_items set record=jsonb_set(record,'{screening}',%s::jsonb)",[screen])
    monkeypatch.setattr(history_publication,'refresh',lambda *args:pytest.fail('Local scan'))
    absent = tmp_path/'unavailable-mount'/'test'
    result = history_publication.sync(absent,conn)
    assert result['records'] == 1 and result['published_items'] == 1
    revision = conn.execute('select max(revision) from workbench_changes').fetchone()[0]
    # Different machine path and an unchanged sync do not invalidate or journal again.
    history_publication.sync(tmp_path/'second-machine'/'test',conn)
    assert conn.execute('select max(revision) from workbench_changes').fetchone()[0] == revision
    assert conn.execute('select source_fingerprint from image_publication').fetchone()[0] == 'original-machine-stamp'
    conn.execute('update image_publication set eligible=false,updated_at=now()')
    history_publication.sync(absent,conn)
    assert conn.execute('select eligible from image_publication').fetchone()[0] is False
    conn.execute("insert into runs(paper_id,run_uid,kind,component,status,analysed_at) values(1,'new-screen','image_track','image_forensics','complete',clock_timestamp())")
    conn.execute("insert into component_items(run_id,item_uid,owner_paper_id,record) select 2,item_uid,owner_paper_id,record from component_items where run_id=1")
    history_publication.sync(absent,conn)
    assert conn.execute('select eligible from image_publication').fetchone()[0] is True
    # A recorded failed attempt is authoritative; no replacement by the older run.
    conn.execute("insert into runs(paper_id,run_uid,kind,component,status,analysed_at) values(1,'failed','image_track','image_forensics','failed',now())")
    result = history_publication.sync(absent,conn)
    assert result['records'] == 0 and result['published_items'] == 0


def test_explicit_image_reset_cannot_touch_other_analysis_or_reimport(remote,tmp_path):
    from metascience_agent.workbench.image_cleanup import migrate,clear_database
    from metascience_agent.workbench.repository import Repository
    r,_=remote;conn=r.connect();migrate(conn)
    conn.execute('insert into component_item_papers(item_id,paper_id) values(1,1)')
    conn.execute("update runs set sealed_digest='sealed',history_record='{}'::jsonb where id=1")
    conn.execute("insert into runs(paper_id,run_uid,kind,component,status) values(1,'numeric','full_review','comprehensive','complete')")
    c=Catalog(tmp_path/'cache.sqlite3')
    try:
        r.sync(c)
        key='[1]';c.save_detail('component_items',key,r.detail('component_items',key),c.record_token('component_items',key))
        with pytest.raises(ValueError,match='scope changed'):
            clear_database(conn,'test',['numeric'])
        outcome=clear_database(conn,'test',['r1'])
        assert outcome['component_items']==1
        assert outcome['item_papers']==1
        assert conn.execute("select retired_at from runs where run_uid='numeric'").fetchone()[0] is None
        with pytest.raises(Exception,match='explicitly cleared'):
            with conn.transaction():
                conn.execute("insert into component_items(run_id,item_uid,owner_paper_id,record) values(1,'i1',1,'{}')")
        r.sync(c)
        assert c.detail('component_items',key) is None
        repo=Repository(c);repo.refresh()
        feed=repo.feed({'project':'test','component':'image_forensics'})
        assert feed['items']==[] and 'awaiting a new analysis' in feed['empty_reason']
        assert repo.feed({'project':'test','component':'image_forensics','run':'r1'})['items']==[]
    finally:c.close()


def test_finding_summaries_say_which_tool_triggered_them(remote,tmp_path):
    """The cached summary carries `tool_basis`, and a pre-feature cache is
    backfilled -- with the state between the two reading `not_recorded`."""
    from metascience_agent.review_issues import finding_tool
    r,schema=remote
    r.conn.execute("insert into runs(paper_id,run_uid,kind,component,status) values(1,'r_part','partial_review','partial_review','complete')")
    records={
        'f_verdict':{'technique':'grim_check','tool_verdict':{'tool':'grim_check','severity':'impossible'}},
        'f_call':{'technique':'baseline_uniformity','reproduction_source':'generated_from_tool_call',
                  'reproduction':"metascience tool run carlisle_test --json '{\"p\": [0.9]}'"},
        'f_label':{'technique':'grim_percentage','computed_by':'model_reading'},
        'f_model':{'technique':'internal_contradiction','computed_by':'model_reading'},
    }
    for fid,rec in records.items():
        rec={'finding_id':fid,'producer':'tool_expert','outcome':'problem',**rec}
        r.conn.execute("""insert into findings(run_id,paper_id,finding_id,producer,technique,outcome,
            severity,severity_is_provisional,tool_verdict,record) values(2,1,%s,'tool_expert',%s,'problem',4,true,%s::jsonb,%s::jsonb)""",
            [fid,rec['technique'],json.dumps(rec.get('tool_verdict')),json.dumps(rec)])
    expected={'f_verdict':('grim_check','tool_verdict'),'f_call':('carlisle_test','tool_call'),
              'f_label':('grim_percentage','technique'),'f_model':('model judgement','model_judgement')}
    c=Catalog(tmp_path/'cache.sqlite3')
    try:
        r.sync(c)
        def tags():
            return {f['finding_id']:tuple(finding_tool(f).values()) for f in c.records('findings')}
        assert tags()==expected
        summary=next(f for f in c.records('findings') if f['finding_id']=='f_verdict')
        assert 'tool_verdict' not in summary and 'record' not in summary
        # A cache made before the field existed: honest absence, then backfill.
        with c.lock,c.db:
            c.db.execute("update records set body=json_remove(body,'$.tool_basis') where entity='findings'")
        c.set_state('tool_summary_schema',None)
        stale={f['finding_id']:finding_tool({**f,'tool_basis':f.get('tool_basis')}) for f in c.records('findings')}
        assert {t['source'] for t in stale.values()}=={'not_recorded'}
        r.refresh_tool_summaries(c)
        assert tags()==expected
        assert c.state('tool_summary_schema')==[2,c.state('db_identity')]
    finally:c.close()
