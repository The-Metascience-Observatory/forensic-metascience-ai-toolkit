"""Indexed local reads and durable invalidation, shared by every app process."""
from .timing import timed
from contextlib import contextmanager
import json
from collections import OrderedDict
import sqlite3
import threading


def migrate_reads(db):
    # Triggers also cover an older app process writing to the same cache.
    db.execute('create table if not exists cache_revisions(scope text primary key, revision integer not null)')
    for table, scope, columns in [('records','records',['body']), ('outbox','reviews',['body']),
                                   ('papers_local','local',['body','path']), ('roots','local',['path']),
                                   ('visits','local',['body']), ('project_flags','local',['body'])]:
        for operation in ('insert','update','delete'):
            changed = ' or '.join(f'new.{c} is not old.{c}' for c in columns)
            when = f' when {changed}' if operation == 'update' else ''
            db.execute(f'''create trigger if not exists cache_revision_{table}_{operation}
                after {operation} on {table}{when} begin
                insert into cache_revisions values('{scope}',1)
                on conflict(scope) do update set revision=revision+1; end''')
    for field in ('id','corpus_id','paper_id','run_id','execution_uid','run_uid','item_id'):
        db.execute(f"create index if not exists records_{field} on records(entity,json_extract(body,'$.{field}'))")
    db.execute("create index if not exists records_artifact on records(entity,json_extract(body,'$.run_id'),json_extract(body,'$.artifact_uid'))")
    db.commit()


class CatalogReads:
    def _init_readers(self):
        self._readers = threading.local()
        self._reader_connections = []
        self._reader_lock = threading.Lock()
        self._artifact_cache = OrderedDict()
        self._artifact_cache_lock = threading.Lock()

    @property
    def reader(self):
        if not hasattr(self._readers, 'db'):
            db = sqlite3.connect(f'file:{self.path}?mode=ro', uri=True, check_same_thread=False)
            db.execute('pragma busy_timeout=5000')
            self._readers.db = db
            with self._reader_lock: self._reader_connections.append(db)
        return self._readers.db

    @contextmanager
    def snapshot(self):
        db = self.reader
        db.execute('begin')
        try: yield
        finally: db.rollback()

    @property
    def version(self):
        return tuple(self.reader.execute('select scope,revision from cache_revisions order by scope').fetchall())

    @timed("database")
    def rows_for(self, entity, field=None, values=None):
        if field is None:
            rows = self.reader.execute('select body from records where entity=?',[entity]).fetchall()
        else:
            # item_id: component_item_derived is keyed by the item it describes.
            if field not in ('id','corpus_id','paper_id','run_id','execution_uid','run_uid','item_id'):
                raise ValueError('Unsupported indexed field')
            values = list(set(values or []))
            rows = []
            for start in range(0,len(values),500):
                batch = values[start:start+500]
                rows.extend(self.reader.execute(f"select body from records where entity=? and json_extract(body,'$.{field}') in ({','.join('?' for _ in batch)})",[entity,*batch]).fetchall())
        return [json.loads(body) for body, in rows]

    def record(self, entity, key):
        row=self.reader.execute('select body from records where entity=? and key=?',[entity,key]).fetchone()
        return json.loads(row[0]) if row else None

    def headers(self, project=None):
        corpora=self.rows_for('corpora')
        ids=[c['id'] for c in corpora if project in (None,'') or c['name']==project]
        papers=self.rows_for('papers','corpus_id',ids)
        executions=self.rows_for('executions','corpus_id',ids)
        if project in (None,''):
            runs=self.rows_for('runs')
        else:
            candidates=self.rows_for('runs','paper_id',[p['id'] for p in papers])+self.rows_for('runs','execution_uid',[e['execution_uid'] for e in executions])
            runs=list({r['id']:r for r in candidates}.values())
        return dict(corpora=corpora,papers=papers,executions=executions,runs=runs,users=self.rows_for('users'))

    @timed("database")
    def artifact_record(self, project, run_uid, artifact_uid):
        with self.snapshot():
            revision=self.reader.execute("select revision from cache_revisions where scope='records'").fetchone()
            cache_key=(revision,project,run_uid,artifact_uid)
            with self._artifact_cache_lock:
                cached=self._artifact_cache.get(cache_key)
                if cached is not None:
                    self._artifact_cache.move_to_end(cache_key)
                    return cached
            runs=self.rows_for('runs','run_uid',[run_uid])
            if len(runs)!=1: raise ValueError('Artifact run is not recorded')
            run=runs[0]
            papers=self.rows_for('papers','id',[run.get('paper_id')])
            executions=self.rows_for('executions','execution_uid',[run.get('execution_uid')])
            corpus_id=(papers[0] if papers else executions[0] if executions else {}).get('corpus_id')
            corpora=self.rows_for('corpora','id',[corpus_id])
            if not corpora or corpora[0]['name']!=project: raise ValueError('Artifact run is not in this project')
            # Exact composite primary key; never hydrate an entire repository.
            row=self.reader.execute("select body from records where entity='run_artifacts' and json_extract(body,'$.run_id')=? and json_extract(body,'$.artifact_uid')=?",[run['id'],artifact_uid]).fetchone()
            rec=json.loads(row[0]) if row else None
            if not rec: raise FileNotFoundError('Artifact is not recorded in this run')
            with self._artifact_cache_lock:
                self._artifact_cache[cache_key]=rec
                while len(self._artifact_cache)>512: self._artifact_cache.popitem(last=False)
            return rec
