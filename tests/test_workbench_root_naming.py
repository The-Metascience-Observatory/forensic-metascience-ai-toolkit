"""A notified folder is registered under its project's name, never its basename.

Measured 2026-09-26 in the operator's cache: 1,870 `roots` rows under the
project `corpus` (every author session's `analysis_sessions/*/corpus` and
every run workspace's `.analysis_runs/work/ar_*/corpus`), and ~2,300 rows
named after pytest tmp folders.
"""
import os
import threading
from pathlib import Path

from forensic_metascience_ai_toolkit.workbench import catalog as catalog_module
from forensic_metascience_ai_toolkit.workbench.catalog import Catalog, project_for_root
from metascience_observatory_image_analysis.review_workbench.local_images import image_path
from forensic_metascience_ai_toolkit.workbench.monitor import FileMonitor
from forensic_metascience_ai_toolkit.workbench import notifications


def test_session_corpus_is_named_author_and_session():
    root = Path('/data/jun_ren_rw20260922/analysis_sessions/pubpeer_checked_20260925T010252Z/corpus')
    assert project_for_root(root) == 'jun_ren_rw20260922__pubpeer_checked_20260925T010252Z'


def test_run_workspace_is_not_a_project():
    root = Path('/data/masliah_papers/.analysis_runs/work/ar_5a52d8/corpus')
    assert project_for_root(root) is None


def test_existing_registration_keeps_its_name_and_basename_is_the_fallback(tmp_path):
    rows = [{'project': 'my_name', 'path': str(tmp_path)}]
    assert project_for_root(tmp_path, rows) == 'my_name'
    assert project_for_root(tmp_path / 'other') == 'other'


class _Service:
    def __init__(self, catalog):
        self.catalog, self.index, self.local_wake = catalog, None, threading.Event()
    def reconcile_files(self, paths=None):
        pass


def test_monitor_registers_notified_roots_under_their_project(tmp_path):
    session = tmp_path / 'author_x' / 'analysis_sessions' / 's1' / 'corpus'
    workspace = tmp_path / 'author_x' / '.analysis_runs' / 'work' / 'ar_1' / 'corpus'
    session.mkdir(parents=True); workspace.mkdir(parents=True)
    c = Catalog(tmp_path / 'cache.sqlite3')
    with c.db:
        c.db.executemany('insert into notifications values(?)', [[str(session)], [str(workspace)]])
    FileMonitor(_Service(c)).prepare()
    assert [(r['project'], r['path']) for r in c.roots()] == [('author_x__s1', str(session.resolve()))]
    assert c.db.execute('select count(*) from notifications').fetchone()[0] == 0


def test_producer_notification_ignores_run_workspaces(tmp_path, monkeypatch):
    cache = tmp_path / 'cache.sqlite3'
    Catalog(cache)
    monkeypatch.setenv('METASCIENCE_WORKBENCH_DB', str(cache))
    result = notifications.published(tmp_path / 'c' / '.analysis_runs' / 'work' / 'ar_1' / 'corpus')
    assert result == {'state': 'run_workspace_ignored'}
    assert Catalog(cache).db.execute('select count(*) from notifications').fetchone()[0] == 0


def test_tests_never_reach_the_operator_caches():
    """The conftest guard: both caches resolve under pytest's tmp, and do not exist."""
    home_default = Path.home() / '.local/share/metascience'
    for path in (catalog_module.cache_path(), image_path()):
        assert not path.is_relative_to(home_default), path
        assert not path.exists(), path


def test_cleanup_is_a_dry_run_until_applied_and_touches_only_roots(tmp_path):
    import tempfile
    from forensic_metascience_ai_toolkit.workbench import root_cleanup
    cache = tmp_path / 'cache.sqlite3'
    c = Catalog(cache)
    pytest_root = str(Path(tempfile.gettempdir()) / 'pytest-of-x' / 'pytest-1' / 'test_a0')
    session = '/data/author_x/analysis_sessions/s1/corpus'
    rows = [('test_a0', pytest_root), ('corpus', session),
            ('corpus', '/data/author_x/.analysis_runs/work/ar_1/corpus'),
            ('author_y__s2', '/data/author_y/analysis_sessions/s2/corpus'),
            ('corpus', '/data/author_y/analysis_sessions/s2/corpus'),
            ('masliah_papers', '/data/masliah_papers')]
    with c.db:
        c.db.executemany('insert into roots values(?,?)', rows)
        c.db.execute("insert into papers_local values('test_a0','p','{}',?)", [pytest_root])
    dry = root_cleanup.run(cache)
    assert dry['remove'] == {'pytest': 1, 'collision': 3} and not dry['applied']
    assert c.db.execute('select count(*) from roots').fetchone()[0] == 6
    done = root_cleanup.run(cache, apply=True)
    assert done['roots_after'] == 3
    assert sorted(c.db.execute('select project from roots')) == [
        ('author_x__s1',), ('author_y__s2',), ('masliah_papers',)]
    assert c.db.execute('select count(*) from papers_local').fetchone()[0] == 1
