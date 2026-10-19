"""Nonrecursive local watches, independent of the network synchronization lane."""
from bisect import bisect_left
from pathlib import Path
import time

from .catalog import project_for_root


def under(paths, changed):
    """The members of sorted `paths` equal to or inside any `changed` path.

    The old pairwise test was files x changes x depth: 9,459 registered files
    against 20 changed paths cost 1.2 s on the live cache (2026-10-01), and a
    synced Dropbox folder delivers a batch every half second. A sorted list
    and a prefix search make it changes x log(files)."""
    found = set()
    for p in changed:
        p = str(p)
        at = bisect_left(paths, p)
        if at < len(paths) and paths[at] == p: found.add(p)
        prefix = p.rstrip('/') + '/'
        at = bisect_left(paths, prefix)
        while at < len(paths) and paths[at].startswith(prefix):
            found.add(paths[at]); at += 1
    return found


class FileMonitor:
    #: How often an armed watch re-checks whether its path set changed.
    RECHECK = 30

    def __init__(self, service):
        self.service = service
        self.catalog = service.catalog
        self.index_stamp = None
        self.last_full = 0

    def prepare(self):
        s, c = self.service, self.catalog
        changed = s.local_wake.is_set()
        s.local_wake.clear()
        # Read first; write only when there is something to consume. This ran
        # a write transaction every half second whether or not anything waited.
        notifications = c.reader.execute('select path from notifications').fetchall()
        if notifications:
            with c.lock, c.db:
                c.db.executemany('delete from notifications where path=?', notifications)
        for (root,) in notifications:
            project = project_for_root(root, c.roots())
            if project and Path(root).is_dir(): c.register_root(project, root)
        if s.index and Path(s.index).is_file():
            st = Path(s.index).stat()
            stamp = (st.st_mtime_ns, st.st_size)
            if stamp != self.index_stamp:
                c.import_index(s.index)
                self.index_stamp = stamp
                changed = True
        if changed or notifications or time.monotonic() - self.last_full > 300:
            s.reconcile_files()
            self.last_full = time.monotonic()

    def signature(self):
        """What `paths()` depends on, cheaply: records/local revisions, roots and files."""
        c = self.catalog
        revisions = c.reader.execute("select scope,revision from cache_revisions where scope in ('records','local') order by scope").fetchall()
        files = c.reader.execute('select count(*),max(rowid) from files').fetchone()
        return (tuple(revisions), tuple(files), tuple((r['project'], r['path']) for r in c.roots()))

    def paths(self):
        c = self.catalog
        roots = c.roots()
        corpora = {p['id']: p['name'] for p in c.records('corpora')}
        wanted = {Path(r['path']) for r in roots}
        wanted.update(Path(path) for _, _, _, path in c.local_papers())
        for paper in c.records('papers'):
            for root in roots:
                if root['project'] == corpora.get(paper['corpus_id']) and paper.get('dir'):
                    base = Path(root['path'])
                    path = (base / paper['dir']).resolve()
                    if path.is_relative_to(base): wanted.add(path)
        wanted.update(Path(row[0]).parent for row in c.reader.execute('select path from files'))
        paths = set()
        for path in wanted:
            # Watch parents too, so removing/recreating a mapped folder is seen.
            while not path.is_dir() and path != path.parent: path = path.parent
            paths.update((str(path), str(path.parent)))
        return sorted(paths)

    def changed(self, changes):
        paths = {Path(path) for _, path in changes}
        self.service.reconcile_files(paths)
        # Verification after modification happens locally, never in the database.
        rows = self.catalog.reader.execute('select sha,path from files').fetchall()
        by_path = {}
        for sha, path in rows: by_path.setdefault(path, []).append(sha)
        for path in sorted(under(sorted(by_path), paths)):
            for sha in by_path[path]: self.catalog.file_for(sha)

    def run(self):
        s = self.service
        while not s.stop.is_set():
            try:
                self.prepare()
                from watchfiles import watch
                signature = self.signature()
                paths = self.paths()
                if not paths:
                    s.stop.wait(0.5)
                    continue
                checked = time.monotonic()
                self.catalog.set_state('file_monitor_error', None)
                for changes in watch(*paths, recursive=False, watch_filter=None,
                                     stop_event=s.stop, rust_timeout=500,
                                     yield_on_timeout=True, debounce=500, debug=False):
                    if changes: self.changed(changes)
                    self.prepare()
                    if s.stop.is_set(): break
                    # Re-arm only when the watched set can have changed. The
                    # watch on ~2,500 folders used to be torn down and rebuilt
                    # every 30 s, recomputing 2.4 s of paths each time.
                    if time.monotonic() - checked > self.RECHECK:
                        checked = time.monotonic()
                        if self.signature() != signature: break
            except Exception as exc:
                self.catalog.set_state('file_monitor_error', f'{type(exc).__name__}: {exc}')
                # Full reconciliation remains available if OS watches fail.
                s.stop.wait(5)
