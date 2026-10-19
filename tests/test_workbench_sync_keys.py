"""Regression checks for fresh-cache paging and moved report identities."""
import json

import pytest

from metascience_agent.workbench.remote import Remote, key_filter
from metascience_agent.workbench.catalog import Catalog
from metascience_agent.workbench.repository import Repository
from metascience_agent.workbench.service import Service


def test_native_key_predicates_cover_scalar_composite_and_deleted_batches():
    assert key_filter('runs', after='[9]') == ('(t.id)>(%s)', [9])
    assert key_filter('run_artifacts', after='[9,"asset"]') == ('(t.run_id,t.artifact_uid)>(%s,%s)', [9, 'asset'])
    assert key_filter('runs', keys=['[2]', '[10]']) == ('(t.id) in ((%s),(%s))', [2, 10])
    assert key_filter('runs', keys=[]) == ('false', [])
    with pytest.raises(ValueError): key_filter('run_artifacts', after='[9]')
    with pytest.raises(KeyError): key_filter('untrusted_table')


def test_row_query_uses_index_order_and_never_serializes_discarded_payloads():
    class Result:
        def __init__(self, rows): self.rows = rows
        def fetchall(self): return self.rows
    class Connection:
        closed = False
        def __init__(self): self.calls = []
        def execute(self, sql, args):
            self.calls.append((sql, args))
            if 'pg_attribute' in sql:
                return Result([(x,) for x in ['id', 'paper_id', 'meta', 'history_record']])
            return Result([('[10]', {'id':10})])
    r = Remote(); r.conn = Connection()
    assert r.rows('runs', after='[9]') == [('[10]', {'id':10})]
    sql, args = r.conn.calls[-1]
    assert 'where (t.id)>(%s) order by t.id limit %s' in sql
    assert args == [9, 500]
    assert 'to_jsonb(t)' not in sql
    assert 'select t."id",t."paper_id"' in sql
    assert 't."meta"' not in sql
    assert 't.history_record' in sql  # compact provenance is retained


def test_moved_report_uses_run_identity_not_doi_and_serves_findings(tmp_path):
    c = Catalog(tmp_path/'cache.sqlite3')
    try:
        c.apply_changes([
            ('corpora','[1]',{'id':1,'name':'project'}),
            ('papers','[1]',{'id':1,'corpus_id':1,'dir':'paper','doi':'10.same/doi'}),
            ('papers','[2]',{'id':2,'corpus_id':1,'dir':'other','doi':'10.same/doi'}),
            ('runs','[1]',{'id':1,'run_uid':'saved-run','paper_id':1,'component':'comprehensive','status':'partial'}),
            ('runs','[2]',{'id':2,'run_uid':'other-run','paper_id':2,'component':'comprehensive','status':'complete'}),
            ('findings','[1]',{'id':1,'run_id':1,'paper_id':1,'finding_id':'F1','title':'Saved finding','outcome':'problem','severity':3}),
        ], 1)
        body = {'runs':[{'run_id':'saved-run'}], 'doi':'10.same/doi'}
        with c.lock, c.db:
            c.db.execute('insert into papers_local values(?,?,?,?)', ['project','nested/paper',json.dumps(body),str(tmp_path)])
            c.db.execute('insert into papers_local values(?,?,?,?)', ['project','unlinked',json.dumps({'doi':'10.same/doi'}),str(tmp_path)])
        s = Service(c, background=False)
        result = s.handle('paper', {'project':'project','dir':'nested/paper'})
        assert result['paper']['shared_id'] == 1
        assert result['paper']['dir'] == 'nested/paper'
        assert result['issues']['latest_run'] == 'saved-run'
        assert result['issues']['pagination']['total'] == 1
        assert result['issues']['issues'][0]['title'] == 'Saved finding'
        repo = Repository(c); repo.refresh()
        assert repo.resolve_paper('project',directory='unlinked')['id'].startswith('local:')
        rows = repo.papers_page({'project':'project'})['papers']
        assert next(p for p in rows if p['dir']=='nested/paper')['n_findings'] == 1
        with c.lock, c.db:
            body['runs'].append({'run_id':'other-run'})
            c.db.execute('update papers_local set body=? where dir=?',[json.dumps(body),'nested/paper'])
            c.generation += 1
        repo.refresh()
        with pytest.raises(ValueError, match='multiple shared papers'):
            repo.resolve_paper('project',directory='nested/paper')
    finally:
        c.close()


def test_finding_summary_carries_the_tool_basis_and_old_caches_are_backfilled(tmp_path):
    """Which tool triggered a finding reaches the cached summary (bounded:
    names and a reproduction prefix, never the full tool_verdict), and a cache
    made before the field existed reads `not_recorded` until backfilled."""
    from metascience_agent.workbench.remote import TOOL_BASIS, summary_expr
    sql = summary_expr('findings')
    assert "'tool_basis'" in sql and TOOL_BASIS in sql
    assert "t.tool_verdict->'tool'" in sql
    assert "left(t.record->>'reproduction',200)" in sql
    c = Catalog(tmp_path/'cache.sqlite3')
    try:
        c.apply_changes([
            ('corpora','[1]',{'id':1,'name':'project'}),
            ('papers','[1]',{'id':1,'corpus_id':1,'dir':'paper'}),
            ('runs','[1]',{'id':1,'run_uid':'r1','paper_id':1,'component':'comprehensive','status':'complete'}),
            ('findings','[1]',{'id':1,'run_id':1,'paper_id':1,'finding_id':'F1','title':'Old row',
                               'technique':'grim_check','outcome':'problem','severity':3}),
        ], 1)
        s = Service(c, background=False)
        def issue():
            return s.handle('paper', {'project':'project','dir':'paper'})['issues']['issues'][0]
        # Absence is not "model judgement", and not grim_check either.
        assert (issue()['tool'], issue()['tool_source']) == (None, 'not_recorded')
        class Connection:
            calls = 0
            def execute(self, sql, values):
                self.calls += 1
                assert TOOL_BASIS in sql and 'to_jsonb(t)' not in sql
                return self
            def fetchall(self):
                return [(1, {'tool_verdict': None, 'backing_call': None,
                             'reproduction_source': 'generated_from_tool_call',
                             'reproduction': "metascience tool run grimmer_check --json '{}'"},
                         {'location': 'Table 2, row 3', 'pages': [4], 'tables': ['Table 2']})]
        remote = Remote(); connection = Connection()
        remote.connect = lambda: connection
        remote.refresh_tool_summaries(c)
        assert c.state('cursor') == 1           # no journal movement
        assert (issue()['tool'], issue()['tool_source']) == ('grimmer_check', 'tool_call')
        # The same pass fills where the finding sits (grouping, 1.83.0).
        assert issue()['location_basis'] == {'location': 'Table 2, row 3',
                                             'pages': [4], 'tables': ['Table 2']}
        assert issue()['location'] == 'Table 2, row 3'
        remote.refresh_tool_summaries(c)
        assert connection.calls == 1            # done once, then marked complete
    finally:
        c.close()


def test_finding_tool_order_of_evidence():
    from metascience_agent.review_issues import finding_tool
    base = {'technique': 'grim_check'}
    assert finding_tool({**base, 'tool_verdict': {'tool': 'grimmer_check'}}) == {'tool': 'grimmer_check', 'source': 'tool_verdict'}
    assert finding_tool({**base, 'backing_call': {'tool_short': 'debit_check'}}) == {'tool': 'debit_check', 'source': 'tool_call'}
    # A model-written command is not a ledger call.
    assert finding_tool({**base, 'reproduction_source': 'model_written',
                         'reproduction': 'metascience tool run debit_check'})['source'] == 'technique'
    assert finding_tool(base) == {'tool': 'grim_check', 'source': 'technique'}
    assert finding_tool({'technique': 'internal_contradiction'}) == {'tool': 'model judgement', 'source': 'model_judgement'}
    assert finding_tool({**base, 'tool_basis': None}) == {'tool': None, 'source': 'not_recorded'}
