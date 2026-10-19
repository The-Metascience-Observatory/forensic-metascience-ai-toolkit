"""Integration seams: shared publication, foreground reads and verified sources."""
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.service import Service
from forensic_metascience_ai_toolkit.workbench.monitor import FileMonitor


def test_detail_does_not_wait_for_background_network_lock(tmp_path):
    class Foreground:
        def detail(self, entity, key): return {'record': {'title': 'Saved result'}}
        def close(self): pass

    c = Catalog(tmp_path/'cache.sqlite3')
    try:
        c.apply_changes([('findings','[1]',{'id':1})], 1)
        s = Service(c, background=False, detail_remote=Foreground())
        with ThreadPoolExecutor(max_workers=1) as pool:
            s.network.acquire()
            try:
                result = pool.submit(s.detail, 'findings', '[1]').result(timeout=1)
            finally:
                s.network.release()
        assert result['record']['title'] == 'Saved result'
        assert c.detail('findings','[1]') == result
    finally: c.close()


def source_catalog(tmp_path):
    c = Catalog(tmp_path/'cache.sqlite3')
    xml = tmp_path/'article.xml'
    xml.write_text('<article><front><article-meta><title-group><article-title>Archived title</article-title></title-group></article-meta></front><body><sec><title>Results</title><p>The archived result was 42.</p></sec></body></article>')
    sha = hashlib.sha256(xml.read_bytes()).hexdigest()
    c.register_file(xml, sha)
    c.apply_changes([
        ('corpora','[1]',{'id':1,'name':'project'}),
        ('papers','[1]',{'id':1,'corpus_id':1,'dir':'paper'}),
        ('runs','[1]',{'id':1,'run_uid':'r1','paper_id':1,'component':'comprehensive','sealed_digest':'sealed','status':'complete'}),
        ('run_artifacts','[1, "xml"]',{'run_id':1,'artifact_uid':'xml','role':'source_xml','content_sha256':sha,'record':{'name':'article.xml'}}),
    ],1)
    return c, xml


@pytest.mark.usefixtures("image_package")
def test_archived_xml_renders_actual_text_and_refuses_changed_bytes(tmp_path):
    c, xml = source_catalog(tmp_path)
    try:
        s = Service(c, background=False)
        args = {'project':'project','dir':'paper','run':'r1'}
        result = s.source(args)
        assert result['availability'] == 'verified'
        assert result['article']['mode'] == 'xml'
        assert 'The archived result was 42.' in result['article']['html']
        assert 'Archived title' in result['article']['html']
        assert result['article']['xml_relpath'] == '__runs/r1/xml'
        c.apply_changes([('run_artifacts','[1, "pdf"]',{'run_id':1,'artifact_uid':'pdf',
            'role':'source_pdf','content_sha256':'a'*64,'record':{'name':'article.pdf'}})],2)
        assert s.source(args)['article']['mode'] == 'xml'  # Missing PDF does not hide verified XML.
        xml.write_text('<article><body>Contemporary changed result</body></article>')
        changed = s.source(args)
        assert changed['availability'] == 'unavailable'
        assert changed['article']['mode'] == 'none'
        assert 'html' not in changed['article']  # Never serve cached text after hash failure.
    finally: c.close()


def test_native_file_monitor_updates_without_sync(tmp_path):
    pytest.importorskip('watchfiles')
    c, xml = source_catalog(tmp_path)
    c.map_paper('project','paper',tmp_path)
    s = Service(c,background=False)
    monitor = FileMonitor(s)
    monitor.prepare()
    thread = threading.Thread(target=monitor.run,daemon=True)
    thread.start()
    try:
        # Repeat a harmless creation while the native watcher starts; there is
        # no timing assumption about the OS completing watch registration.
        deadline = time.monotonic()+6
        while time.monotonic()<deadline:
            (tmp_path/'paper.pdf').write_bytes(b'%PDF placeholder')
            if c.local_papers()[0][2]['sources']['pdf']: break
            time.sleep(.1)
        assert c.local_papers()[0][2]['sources']['pdf']
        assert c.state('cursor') == 1  # Local event handling never synchronized Neon.
        assert c.state('file_monitor_error') is None
    finally:
        s.stop.set();thread.join(timeout=5)
        assert not thread.is_alive()
        c.close()


def test_file_events_update_local_availability_without_network(tmp_path):
    c, xml = source_catalog(tmp_path)
    try:
        c.map_paper('project','paper',tmp_path)
        s = Service(c,background=False)
        monitor = FileMonitor(s)
        monitor.prepare()
        assert c.local_papers()[0][2]['sources']['xml']
        xml.unlink()
        monitor.changed({(3,str(xml))})
        assert not c.local_papers()[0][2]['sources']['xml']
        assert c.records('runs')[0]['sealed_digest'] == 'sealed'
        assert str(tmp_path) in monitor.paths()
    finally: c.close()


@pytest.mark.usefixtures("image_package")
def test_shared_projection_preserves_clone_policy_and_review_conflicts():
    from forensic_metascience_ai_toolkit.history_publication import shared_records
    from metascience_observatory_image_analysis.image_forensics.screening import POLICY,CLONE_POLICY

    def screen(policy):
        return {'policy':policy,'decision':'issue','validated':True,'confidence':'high','inputs_stamp':'saved-stamp'}

    class Cursor:
        def execute(self,*args): pass
        def fetchall(self):
            return [
                ('paper','pair','exact',screen(POLICY),None,[],None,None),
                ('paper','clone','intra_panel_clone',screen(CLONE_POLICY),None,[],None,None),
                ('paper','stale','intra_panel_clone',screen(POLICY),None,[],None,None),
                ('paper','rejected','exact',screen(POLICY),None,['false_positive_other'],True,False),
                ('paper','conflict','exact',screen(POLICY),None,['true_issue','false_positive_other'],False,True),
                ('paper','revoked','exact',screen(POLICY),None,[],False,False),
                ('paper','newer','exact',screen(POLICY),None,[],False,True),
                ('paper','cleared','exact',None,'true',[],None,None),
            ]
    records = {r['item_uid']:r for r in shared_records(Cursor(),1)}
    assert records['pair']['eligible'] and records['clone']['eligible']
    assert records['newer']['eligible'] and records['cleared']['eligible']
    assert records['clone']['policy'] == CLONE_POLICY
    assert records['clone']['source_fingerprint'] == 'saved-stamp'
    assert not any(records[k]['eligible'] for k in ('stale','rejected','conflict','revoked'))


@pytest.mark.usefixtures("image_package")
def test_image_run_xml_current_figures_are_explicit_reading_aids(tmp_path):
    import json
    c, xml = source_catalog(tmp_path)
    try:
        xml.write_text('<article><body><fig id="F1"><label>Figure 1</label><caption><p>Full caption</p></caption><graphic href="figure.png"/></fig></body></article>')
        sha = hashlib.sha256(xml.read_bytes()).hexdigest()
        c.register_file(xml, sha)
        c.map_paper('project','paper',tmp_path)
        c.apply_changes([
            ('runs','[1]',{'id':1,'run_uid':'r1','paper_id':1,'component':'image_forensics','sealed_digest':'sealed','status':'complete'}),
            ('run_artifacts','[1, "xml"]',{'run_id':1,'artifact_uid':'xml','role':'source_xml','content_sha256':sha,'record':{'name':'article.xml'}}),
        ],2)
        s = Service(c, background=False)
        args = {'project':'project','dir':'paper','run':'r1','component':'image_forensics'}
        assert '<img ' not in s.source(args)['article']['html']
        (tmp_path/'figure.png').write_bytes(b'local image')
        article = s.source(args)['article']
        assert '<img ' in article['html']
        assert 'Current local image; not archived evidence.' in article['html']
        assert article['figures'][0]['graphics'][0]['status'] == 'local_current'
        assert 'f=figure.png' in article['html']
        # A recorded image becomes verified evidence and uses an archive ref.
        image_sha = hashlib.sha256((tmp_path/'figure.png').read_bytes()).hexdigest()
        c.register_file(tmp_path/'figure.png',image_sha)
        c.apply_changes([('run_artifacts','[1, "image"]',{'run_id':1,'artifact_uid':'image','role':'source',
            'content_sha256':image_sha,'record':{'name':'figure.png'}})],3)
        article=s.source(args)['article']
        assert 'f=__runs%2Fr1%2Fimage' in article['html']
        assert 'Current local image' not in article['html']
        (tmp_path/'figure.png').write_bytes(b'changed image')
        assert '<img ' not in s.source(args)['article']['html']
    finally: c.close()


@pytest.mark.usefixtures("image_package")
def test_cross_paper_xml_uses_only_scoped_sources(tmp_path):
    c, xml = source_catalog(tmp_path)
    try:
        sha=hashlib.sha256(xml.read_bytes()).hexdigest()
        c.apply_changes([
            ('executions','["e1"]',{'execution_uid':'e1','corpus_id':1,'status':'completed'}),
            ('runs','[1]',{'id':1,'run_uid':'r1','execution_uid':'e1','paper_id':None,'component':'image_forensics','sealed_digest':'sealed','status':'complete'}),
            ('papers','[2]',{'id':2,'corpus_id':1,'dir':'other-paper'}),
            ('run_artifacts','[1, "xml"]',{'run_id':1,'artifact_uid':'xml','role':'source_xml','content_sha256':sha,'record':{'name':'article.xml','paper':'paper'}}),
        ],2)
        s=Service(c,background=False)
        args={'project':'project','run':'r1','component':'image_forensics'}
        assert 'Archived title' in s.source({**args,'dir':'paper'})['article']['html']
        other=s.source({**args,'dir':'other-paper'})
        assert other['article']['mode']=='none'
        assert 'html' not in other['article']
    finally:c.close()


@pytest.mark.usefixtures("image_package")
def test_historical_xml_conversion_reused_but_hash_still_checked(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit.extraction import xml_html
    c, xml = source_catalog(tmp_path)
    original = xml_html._xml_article_html
    calls = []
    def convert(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)
    monkeypatch.setattr(xml_html, '_xml_article_html', convert)
    try:
        service = Service(c, background=False)
        args = {'project': 'project', 'dir': 'paper', 'run': 'r1'}
        first = service.source(args)
        assert service.source(args) == first
        assert len(calls) == 1
        xml.write_text('<article><body>Replaced</body></article>')
        assert service.source(args)['availability'] == 'unavailable'
        assert len(calls) == 1
    finally:
        c.close()


def test_source_conversions_coalesce_per_key_and_do_not_block_other_keys(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    c, _ = source_catalog(tmp_path)
    entered, release = Event(), Event()
    calls = []
    def slow():
        calls.append('slow')
        entered.set()
        assert release.wait(5)
        return {'html': 'slow source'}
    try:
        service = Service(c, background=False)
        with ThreadPoolExecutor(max_workers=3) as pool:
            first = pool.submit(service.cached_source, ('source-a',), slow)
            assert entered.wait(2)
            same = pool.submit(service.cached_source, ('source-a',), slow)
            other = pool.submit(service.cached_source, ('source-b',), lambda: {'html': 'other source'})
            try:
                assert other.result(timeout=2) == {'html': 'other source'}
                assert not first.done()
            finally:
                release.set()
            assert first.result() == same.result() == {'html': 'slow source'}
        assert calls == ['slow']
        assert not service.source_locks
        for i in range(25):
            service.cached_source(('extra', i), lambda: {})
        assert len(service.source_cache) == 20
    finally:
        release.set()
        c.close()


def test_failed_source_conversion_can_retry(tmp_path):
    import pytest
    c, _ = source_catalog(tmp_path)
    try:
        service = Service(c, background=False)
        def fail():
            raise ValueError('conversion failed')
        with pytest.raises(ValueError, match='conversion failed'):
            service.cached_source('source', fail)
        assert 'source' not in service.source_cache
        assert service.cached_source('source', lambda: {'html': 'recovered'}) == {'html': 'recovered'}
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_source_route_converts_other_document_while_one_is_busy(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from forensic_metascience_ai_toolkit.extraction import xml_html
    c, xml = source_catalog(tmp_path)
    other = tmp_path / 'other.xml'
    other.write_text(xml.read_text().replace('Archived title', 'Other title'))
    sha = hashlib.sha256(other.read_bytes()).hexdigest()
    c.register_file(other, sha)
    c.apply_changes([
        ('papers', '[2]', {'id': 2, 'corpus_id': 1, 'dir': 'other'}),
        ('runs', '[2]', {'id': 2, 'run_uid': 'r2', 'paper_id': 2,
                        'component': 'comprehensive', 'sealed_digest': 'sealed', 'status': 'complete'}),
        ('run_artifacts', '[2, "xml"]', {'run_id': 2, 'artifact_uid': 'xml',
            'role': 'source_xml', 'content_sha256': sha, 'record': {'name': 'other.xml'}}),
    ], 2)
    entered, release = Event(), Event()
    calls = []
    original = xml_html._xml_article_html
    def convert(path, **kwargs):
        calls.append(path.name)
        if path.name == 'article.xml':
            entered.set()
            assert release.wait(5)
        return original(path, **kwargs)
    monkeypatch.setattr(xml_html, '_xml_article_html', convert)
    try:
        service = Service(c, background=False)
        args = {'project': 'project', 'dir': 'paper', 'run': 'r1'}
        with ThreadPoolExecutor(max_workers=3) as pool:
            first = pool.submit(service.source, args)
            assert entered.wait(2)
            same = pool.submit(service.source, args)
            second = pool.submit(service.source, {**args, 'dir': 'other', 'run': 'r2'})
            try:
                assert 'Other title' in second.result(timeout=3)['article']['html']
                assert not first.done()
            finally:
                release.set()
            assert first.result() == same.result()
        assert calls.count('article.xml') == calls.count('other.xml') == 1
    finally:
        release.set()
        c.close()
