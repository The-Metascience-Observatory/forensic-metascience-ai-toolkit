import pytest
"""An idle service must not spend a core: no writes and no quadratic scans."""
import threading
from pathlib import Path

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.monitor import FileMonitor, under


def test_under_matches_equal_and_contained_paths_only():
    paths = sorted(['/a/b', '/a/b/c.png', '/a/bc/d.png', '/a/b/e/f.png', '/z.png'])
    assert under(paths, {Path('/a/b')}) == {'/a/b', '/a/b/c.png', '/a/b/e/f.png'}
    assert under(paths, {Path('/a/bc/d.png'), Path('/nothing')}) == {'/a/bc/d.png'}
    assert under(paths, set()) == set()


class _Service:
    def __init__(self, catalog):
        self.catalog, self.index, self.local_wake = catalog, None, threading.Event()
        self.reconciled = []
    def reconcile_files(self, paths=None):
        self.reconciled.append(paths)


@pytest.mark.usefixtures("image_package")
def test_idle_prepare_and_video_poll_do_not_write(tmp_path):
    c = Catalog(tmp_path / 'cache.sqlite3')
    try:
        monitor = FileMonitor(_Service(c))
        monitor.prepare()
        writes = c.db.total_changes
        for _ in range(5): monitor.prepare()
        assert c.db.total_changes == writes
        assert not c.db.in_transaction
        from forensic_metascience_ai_toolkit.workbench.service import Service
        s = Service(c, background=False)
        statements = []
        c.db.set_trace_callback(statements.append)
        for _ in range(3): assert s.videos.claim() is None
        assert not any('begin' in q.lower() or 'update' in q.lower() for q in statements), statements
    finally: c.close()


def test_monitor_verifies_only_files_at_or_under_changed_paths(tmp_path):
    c = Catalog(tmp_path / 'cache.sqlite3')
    try:
        (tmp_path / 'p1').mkdir(); (tmp_path / 'p2').mkdir()
        a, b = tmp_path / 'p1' / 'a.png', tmp_path / 'p2' / 'b.png'
        a.write_bytes(b'a'); b.write_bytes(b'b')
        c.register_file(a); c.register_file(b)
        monitor = FileMonitor(_Service(c)); checked = []
        c.file_for = lambda sha: checked.append(sha)
        monitor.changed({(2, str(tmp_path / 'p1'))})
        assert len(checked) == 1
        assert monitor.service.reconciled == [{tmp_path / 'p1'}]
    finally: c.close()


def test_wal_is_checkpointed_and_truncated_only_when_idle(tmp_path):
    import time
    c = Catalog(tmp_path / 'cache.sqlite3')
    try:
        reader = c.reader
        for n in range(200):
            with c.lock, c.db: c.db.execute('insert or replace into state values(?,?)', [f'k{n}', 'x' * 4000])
        wal = Path(f'{c.path}-wal')
        assert wal.stat().st_size > 100_000
        busy = time.monotonic()
        assert c.checkpoint_when_idle(busy, minimum=1) is None  # a request just ran
        result = c.checkpoint_when_idle(busy - 600, minimum=1)
        assert result is not None and result[0] == 0
        assert wal.stat().st_size == 0
        assert c.checkpoint_when_idle(busy - 600, minimum=1) is None  # not again so soon
        assert reader.execute("select count(*) from state").fetchone()[0] == 200
    finally: c.close()
