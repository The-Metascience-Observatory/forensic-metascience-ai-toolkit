"""Private, transactional local cache, durable outbox and verified file catalog."""
from __future__ import annotations

from .timing import timed

from .catalog_reads import CatalogReads, migrate_reads

import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import uuid


from metascience_agent.workbench.common import (  # noqa: F401 -- re-exported
    WAL_LIMIT, cache_path, encode, is_run_workspace, now, project_for_root)


class Catalog(CatalogReads):
    def __init__(self, path=None):
        self.path = Path(path or cache_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute('pragma journal_mode=WAL')
        self.db.execute('pragma busy_timeout=5000')
        self.db.execute(f'pragma journal_size_limit={WAL_LIMIT}')
        self.db.executescript('''
create table if not exists records(entity text,key text,body text not null,primary key(entity,key));
create table if not exists staging(generation text,entity text,key text,body text,primary key(generation,entity,key));
create table if not exists state(key text primary key,value text);
create table if not exists record_tokens(entity text,key text,token text,primary key(entity,key));
create table if not exists details(entity text,key text,body text,primary key(entity,key));
create table if not exists outbox(event_id text primary key,body text not null,error text);
create table if not exists roots(project text,path text,primary key(project,path));
create table if not exists papers_local(project text,dir text,body text,path text,primary key(project,dir));
create table if not exists files(sha text,path text primary key,size integer,mtime integer,ctime integer,verified_at text);
create index if not exists files_sha on files(sha);
create table if not exists notifications(path text primary key);
create table if not exists visits(project text,dir text,body text,primary key(project,dir));
create table if not exists project_flags(project text primary key,body text not null);
''')
        self.db.commit()
        migrate_reads(self.db)
        self._init_readers()
        self.generation = 0

    def close(self):
        for db in self._reader_connections: db.close()
        self.db.close()

    _last_checkpoint = 0.0

    def checkpoint_when_idle(self, last_active, idle=120, every=900, minimum=WAL_LIMIT):
        """Fold the WAL back into the database while nobody is using it.

        Nothing ever did: SQLite's automatic checkpoint is PASSIVE, cannot
        finish past a reader's open snapshot, and never shrinks the file. On
        2026-10-01 the image-review database carried a 1.06 GB WAL and the
        shared cache 1.6 GB. TRUNCATE briefly blocks writers, so it runs only
        after `idle` seconds without a request, at most every `every` seconds,
        and only when the WAL has outgrown `minimum`. Returns SQLite's
        (busy, wal_frames, checkpointed_frames), or None when it did not run.
        """
        import time
        try: size = Path(f'{self.path}-wal').stat().st_size
        except OSError: return None
        clock = time.monotonic()
        if size < minimum or clock - last_active < idle or clock - self._last_checkpoint < every:
            return None
        self._last_checkpoint = clock
        with self.lock:
            return tuple(self.db.execute('pragma wal_checkpoint(TRUNCATE)').fetchone())

    def state(self, key):
        r = self.reader.execute('select value from state where key=?',[key]).fetchone()
        return json.loads(r[0]) if r else None

    def set_state(self, key, value):
        with self.lock, self.db:
            self.db.execute('insert or replace into state values(?,?)',[key,encode(value)])

    def status(self):
        pending = self.reader.execute('select count(*) from outbox').fetchone()[0]
        failures = [r[0] for r in self.reader.execute('select distinct error from outbox where error is not null limit 5')]
        return dict(synced_at=self.state('synced_at'), error=self.state('sync_error'),
                    file_monitor_error=self.state('file_monitor_error'),
                    warmup_error=self.state('warmup_error'),
                    ready=self.state('cursor') is not None, pending_writes=pending,
                    pending_errors=failures, source='database cache', bytes_received=self.state('bytes_received') or 0)

    def reset_for_new_database(self, identity):
        """Discard the projection so the next sync rebuilds it from scratch.

        Called when the remote's identity changes. Everything derived from the
        old database goes: the staged and committed records, the revision
        watermark and the byte counter. The review OUTBOX is deliberately left
        alone -- those are decisions a human made that have not reached any
        database yet, and dropping them would destroy work. The switcher refuses
        to run while the outbox is non-empty for that reason.
        """
        with self.lock, self.db:
            self.db.execute('delete from staging')
            self.db.execute('delete from records')
            self.db.execute("delete from state where key in ('cursor','bytes_received')")
        return {'reset_for': identity}

    def begin_snapshot(self):
        generation = uuid.uuid4().hex
        with self.lock, self.db:
            self.db.execute('delete from staging')
        return generation

    def stage_snapshot(self, generation, entity, rows):
        with self.lock, self.db:
            self.db.executemany('insert into staging values(?,?,?,?)',
                                [(generation,entity,k,encode(v)) for k,v in rows])

    def finish_snapshot(self, generation, cursor):
        with self.lock, self.db:
            self.db.execute('delete from records')
            self.db.execute('insert into records select entity,key,body from staging where generation=?',[generation])
            self.db.execute('delete from staging')
            self.db.execute('delete from details')
            self.db.execute('delete from record_tokens')
            self.db.execute('insert into record_tokens select entity,key,? from records',[generation])
            self.db.execute('insert or replace into state values(?,?)',['cursor',encode(cursor)])
            self.generation += 1

    def apply_changes(self, changes, cursor):
        with self.lock, self.db:
            for entity,key,body in changes:
                if body is None:
                    self.db.execute('delete from records where entity=? and key=?',[entity,key])
                else:
                    self.db.execute('insert or replace into records values(?,?,?)',[entity,key,encode(body)])
                self.db.execute('delete from details where entity=? and key=?',[entity,key])
                self.db.execute('insert or replace into record_tokens values(?,?,?)',[entity,key,uuid.uuid4().hex])
            self.db.execute('insert or replace into state values(?,?)',['cursor',encode(cursor)])
            self.generation += 1

    def records(self, entity):
        return self.rows_for(entity)

    def all_records(self):
        rows=self.reader.execute('select entity,body from records').fetchall()
        out={}
        for entity,body in rows: out.setdefault(entity,[]).append(json.loads(body))
        return out

    def detail(self, entity, key):
        row = self.reader.execute('select body from details where entity=? and key=?',[entity,key]).fetchone()
        return json.loads(row[0]) if row else None

    def record_token(self,entity,key):
        row=self.reader.execute("select token from record_tokens where entity=? and key=?",[entity,key]).fetchone()
        return row[0] if row else None

    def save_detail(self, entity, key, body, generation):
        with self.lock, self.db:
            row = self.db.execute("select token from record_tokens where entity=? and key=?",[entity,key]).fetchone()
            if generation != (row[0] if row else None):
                return False  # A journal update arrived while the network read was in flight.
            self.db.execute('insert or replace into details values(?,?,?)',[entity,key,encode(body)])
            return True

    def enqueue(self, event):
        with self.lock, self.db:
            existing = self.db.execute('select body from outbox where event_id=?',[event['event_id']]).fetchone()
            if existing and json.loads(existing[0]) != event:
                raise ValueError('Review event identity conflict')
            self.db.execute('insert or ignore into outbox values(?,?,null)',[event['event_id'],encode(event)])
            self.generation += 1
        return {**event,'pending':True}

    def pending(self):
        rows=self.reader.execute('select body from outbox order by rowid').fetchall()
        return [json.loads(r[0]) for r in rows]

    def acknowledge(self, event_id):
        with self.lock, self.db:
            self.db.execute('delete from outbox where event_id=?',[event_id])
            self.generation += 1

    def register_root(self, project, path):
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            raise ValueError('Local root is not an available directory')
        with self.lock, self.db:
            self.db.execute('insert or ignore into roots values(?,?)',[project,str(root)])
        return {'project':project,'path':str(root)}

    def discover_root(self, project):
        """The folder the shared corpus record says the corpus was synced from,
        IF that folder exists on this machine -- registered and returned, else
        None. The second, independent way a root becomes known: the first is
        the producer's local notification at sweep time, and a viewer that
        never received one (another process, a cache created later) had no
        way to find archived artifacts it could see rows for. A path from
        another machine fails `is_dir()` here and is ignored; a symlink is
        refused for the same reason `paper_path` refuses one."""
        for rec in self.records('corpora'):
            hint = rec.get('papers_root') if rec.get('name') == project else None
            if not hint:
                continue
            root = Path(hint)
            try:
                if root.is_dir() and str(root.resolve()) == str(root):
                    self.register_root(project, root)
                    return root
            except OSError:
                continue
        return None

    def roots(self, project=None):
        rows = self.reader.execute('select project,path from roots' + (' where project=?' if project else ''), [project] if project else []).fetchall()
        return [dict(project=p,path=r,available=Path(r).is_dir()) for p,r in rows]

    def import_index(self, path):
        obj = json.loads(Path(path).read_text())
        with self.lock, self.db:
            for project in obj['projects']:
                root = Path(project['root']).resolve()
                self.db.execute('insert or ignore into roots values(?,?)',[project['name'],str(root)])
                for p in project['corpus']['papers']:
                    absolute = (root / p['dir']).resolve()
                    if not absolute.is_relative_to(root):
                        raise ValueError('Index paper escapes its root')
                    self.db.execute('insert into papers_local values(?,?,?,?) on conflict(project,dir) do update set body=excluded.body',
                                    [project['name'],p['dir'],encode(p),str(absolute)])
            self.generation += 1
        return {'projects':len(obj['projects']),'papers':sum(len(p['corpus']['papers']) for p in obj['projects'])}

    def local_papers(self, project=None):
        rows=self.reader.execute('select * from papers_local'+(' where project=?' if project else ''),[project] if project else []).fetchall()
        return [(p,d,json.loads(b),path) for p,d,b,path in rows]

    def map_paper(self, project, directory, path):
        target = Path(path).expanduser().resolve()
        if not target.is_dir():
            raise ValueError('Paper folder is not available')
        with self.lock, self.db:
            self.db.execute('insert into papers_local values(?,?,?,?) on conflict(project,dir) do update set path=excluded.path',
                            [project,directory,'{}',str(target)])
            self.generation += 1
        return {'path':str(target)}

    def paper_path(self, project, directory):
        row = self.reader.execute('select path from papers_local where project=? and dir=?',[project,directory]).fetchone()
        if row and Path(row[0]).is_dir():
            if str(Path(row[0]).resolve()) != row[0]:
                raise ValueError('Mapped paper folder was replaced by a symlink')
            return Path(row[0])
        # Exact explicit corpus-relative mapping only; never search by DOI or basename.
        if Path(directory).is_absolute() or '..' in directory.replace('\\','/').split('/'):
            raise ValueError('Invalid paper directory')
        roots = self.roots(project)
        if not any(r['available'] for r in roots) and self.discover_root(project):
            roots = self.roots(project)
        for root in roots:
            base = Path(root['path']).resolve()
            path = (base / directory).resolve()
            if path.is_relative_to(base) and path.is_dir():
                return path
        # Name the project and the remedy: this is a missing ROOT, not a
        # missing file, and the reviewer used to read it beside "no DOI on
        # disk to build a download link from" as though the paper had no PDF.
        raise FileNotFoundError(
            f"Paper files unavailable on this computer: no local folder is registered "
            f"for project {project!r} (paper directory {directory!r}). Register the "
            "corpus root on the Files page, or re-run the sweep from this machine, "
            "which registers it.")

    @timed("file_validation")
    def register_file(self, path, expected=None, allowed_root=None):
        path = Path(path).expanduser().resolve()
        if allowed_root and not path.is_relative_to(Path(allowed_root).resolve()):
            raise ValueError('Artifact escapes registered root')
        before = path.stat()
        sha = None
        if hasattr(hashlib,'file_digest'):
            with path.open('rb') as stream:
                sha = hashlib.file_digest(stream,'sha256').hexdigest()
        if sha is None:
            h = hashlib.sha256()
            with path.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
            sha = h.hexdigest()
        after = path.stat()
        if (before.st_size,before.st_mtime_ns,before.st_ctime_ns) != (after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise ValueError('File changed during validation; retry indexing')
        if expected and sha != expected:
            raise ValueError('File hash does not match historical evidence')
        with self.lock, self.db:
            self.db.execute('insert or replace into files values(?,?,?,?,?,?)',
                            [sha,str(path),after.st_size,after.st_mtime_ns,after.st_ctime_ns,now()])
        return str(path)

    @timed("file_validation")
    def file_for(self, sha):
        rows = self.reader.execute('select path,size,mtime,ctime from files where sha=?',[sha]).fetchall()
        for path,size,mtime,ctime in rows:
            try:
                p = Path(path)
                # A replaced symlink must not silently grant access elsewhere.
                if str(p.resolve()) != path:
                    continue
                st = p.stat()
                if (st.st_size,st.st_mtime_ns,st.st_ctime_ns) == (size,mtime,ctime):
                    return path
                return self.register_file(path,expected=sha)
            except (OSError,ValueError):
                continue
        return None
