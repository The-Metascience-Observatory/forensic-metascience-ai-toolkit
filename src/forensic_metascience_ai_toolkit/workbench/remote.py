"""Bounded, reusable Postgres access and a commit-ordered invalidation journal.

Summary expressions deliberately exclude documents and candidate evidence. Detail
reads are separate and never download media. Table/column names below are constants,
not user input. The statement trigger locks BEFORE a writer takes row locks; journal
sequence order therefore agrees with commit order, including multi-table writers.
"""
from __future__ import annotations

import json
from datetime import datetime
from .match_regions import REGION_FIELDS

KEYS = {
    'corpora': ['id'], 'papers': ['id'], 'runs': ['id'], 'executions': ['execution_uid'],
    'findings': ['id'], 'component_items': ['id'], 'users': ['id'], 'reviews': ['id'],
    'run_artifacts': ['run_id', 'artifact_uid'], 'run_channels': ['run_id', 'channel'],
    'component_item_papers': ['item_id', 'paper_id'],
    'image_publication': ['corpus_id', 'paper_id', 'item_uid'],
    'run_review_status':['run_id','reviewer_id'], 'paper_reviews':['paper_id','reviewer_id'],
    # Derived image type per candidate (migration 007). Small rows; the default
    # full-row summary is fine.
    'component_item_derived': ['item_id'],
}
ITEM_FIELDS = ['id', 'run_id', 'execution_id', 'source_id', 'kind', 'detector_kind',
               'coverage_status', 'figure_labels', 'cleared', 'evidence_source', 'evidence_key', 'rank',
               'exhibit', 'video', 'input_file', 'highlight_file', 'publication_status', 'retired', 'replacement_run']


def key_expr(table, prefix='t'):
    return 'jsonb_build_array(' + ','.join(f'{prefix}.{c}' for c in KEYS[table]) + ')::text'


def key_filter(table, *, keys=None, after=''):
    """Keep wire keys as JSON, but compare indexed native primary-key columns.

    Sorting/filtering jsonb_build_array(id)::text rescans the entire table on
    every page and sorts IDs lexically. Large fresh caches never finish bootstrap.
    """
    columns = KEYS[table]
    def decode(key):
        values = json.loads(key)
        if not isinstance(values, list) or len(values) != len(columns) or any(v is None for v in values):
            raise ValueError('Invalid record key')
        return values
    native = '(' + ','.join('t.' + c for c in columns) + ')'
    placeholders = '(' + ','.join(['%s'] * len(columns)) + ')'
    if keys is not None:
        if not keys: return 'false', []
        values = [decode(key) for key in keys]
        return native + ' in (' + ','.join([placeholders] * len(values)) + ')', [v for row in values for v in row]
    if after:
        return native + '>' + placeholders, decode(after)
    return 'true', []


def picked(expr, fields):
    return 'jsonb_build_object(' + ','.join(f"'{f}',{expr}->'{f}'" for f in fields) + ')'


#: What a finding summary carries to say which tool triggered it -- the
#: ingredients, not the verdict: `review_issues.finding_tool` decides, so the
#: file reader, the detail read and this summary cannot disagree. Bounded:
#: one tool name, one stamp and the first 200 characters of the reproduction
#: (the tool name sits in its first 30). The full `tool_verdict` stays out.
TOOL_BASIS = ("jsonb_build_object("
              "'tool_verdict',t.tool_verdict->'tool',"
              "'backing_call',coalesce(t.record->'backing_call'->'tool_short',t.record->'backing_call'->'tool'),"
              "'reproduction_source',t.record->'reproduction_source',"
              "'reproduction',to_jsonb(left(t.record->>'reproduction',200)))")


#: Where a finding sits, in units the findings list can group by
#: (`review_issues.group_issues`): its printed location, the PDF pages its
#: anchors land on, and the tables they name. Bounded: a few short strings
#: and integers, never the anchors themselves.
_ANCHORS = ("(case when jsonb_typeof(t.record->'anchors')='array' "
            "then t.record->'anchors' else '[]'::jsonb end)")
LOCATION_BASIS = ("jsonb_build_object("
                  "'location',to_jsonb(left(t.record->>'location',200)),"
                  "'pages',(select coalesce(jsonb_agg(distinct (a->>'page')::int),'[]'::jsonb) "
                  f"from jsonb_array_elements({_ANCHORS}) a "
                  "where jsonb_typeof(a->'page')='number'),"
                  "'tables',(select coalesce(jsonb_agg(distinct v),'[]'::jsonb) from ("
                  "select coalesce(a->>'table',a->'cell'->>'table',"
                  "case when a->>'table_num' is not null then 'Table '||(a->>'table_num') end,"
                  "a->>'table_key') v "
                  f"from jsonb_array_elements({_ANCHORS}) a) s where v is not null))")


def summary_expr(table, base='to_jsonb(t)'):
    if table == 'runs':
        return f"({base}-'meta'-'history_record') || jsonb_build_object('history_record'," + picked(
            't.history_record', ['id', 'paper', 'component', 'scope_key', 'parent_run_id',
             'revision_of', 'execution_id', 'status', 'started_at', 'completed_at',
             'detail', 'latest_eligible', 'selection_family', 'provenance', 'n_items', 'workbench_retired', 'replacement_run']) + ')'
    if table == 'papers':
        return f"({base}-'metadata') || jsonb_build_object('metadata'," + picked(
            't.metadata', ['volume', 'issue', 'pubpeer', 'pubpeer_url']) + ')'
    if table == 'executions':
        return f"({base}-'configuration') || jsonb_build_object('reused_run_ids',t.configuration->'workbench_reused_run_ids')"
    if table == 'run_artifacts':
        return f"({base}-'record') || jsonb_build_object('record'," + picked(
            't.record', ['name', 'role', 'sha256', 'size', 'paper', 'original_path', 'evidence_source']) + ')'
    if table == 'component_items':
        # Paper heads and panels are bounded thumbnail descriptors, not evidence.
        head = picked("t.record->'paper'", ['dir','doi','title','journal','year','pdf'])
        panels = "(select coalesce(jsonb_agg(" + picked('p', ['uid','paper_dir','image','figure_label']) + "),'[]') from jsonb_array_elements(coalesce(t.record->'panels','[]')) p)"
        screen = picked("t.record->'screening'", ['decision','validated','confidence','policy','inputs_stamp'])
        adjudication = picked("t.record->'adjudication'", ['verdict','category','confidence'])
        regions = picked("t.record->'measurements'", REGION_FIELDS)
        return f"({base}-'record') || jsonb_build_object('record'," + picked('t.record', ITEM_FIELDS) + f" || jsonb_build_object('sentence',left(t.record->>'sentence',500),'paper',{head},'panels',{panels},'screening',{screen},'adjudication',{adjudication},'region_measurements',{regions}))"
    if table == 'findings':
        return (f"({base}-'record'-'anchors'-'anchor_summary'-'web_sources'-'tool_verdict'-'adjudication'-'description'-'basis')"
                f" || jsonb_build_object('tool_basis',{TOOL_BASIS},"
                f"'location_basis',{LOCATION_BASIS})")
    return base


SUMMARY_EXCLUDED = {
    'runs': {'meta', 'history_record'}, 'papers': {'metadata'},
    'executions': {'configuration'}, 'run_artifacts': {'record'},
    'component_items': {'record'},
    'findings': {'record', 'anchors', 'anchor_summary', 'web_sources', 'tool_verdict',
                 'adjudication', 'description', 'basis'},
}


def migration_sql():
    statements = ["""
create table if not exists workbench_changes (
 revision bigint generated always as identity primary key,
 entity text not null, key text not null, deleted boolean not null,
 changed_at timestamptz not null default now(),
 unique(entity,key)
);
create or replace function workbench_serialize() returns trigger language plpgsql as $$
begin
 perform pg_advisory_xact_lock(7168340291);
 return null;
end $$;
create or replace function workbench_journal() returns trigger language plpgsql as $$
declare obj jsonb; k jsonb := '[]'::jsonb; col text;
begin
 if TG_OP='UPDATE' and NEW is not distinct from OLD then return NEW; end if;
 if TG_OP='DELETE' then obj:=to_jsonb(OLD); else obj:=to_jsonb(NEW); end if;
 foreach col in array TG_ARGV loop k:=k || jsonb_build_array(obj->col); end loop;
 insert into workbench_changes(entity,key,deleted) values(TG_TABLE_NAME,k::text,TG_OP='DELETE')
 on conflict(entity,key) do update set revision=DEFAULT,deleted=excluded.deleted,changed_at=excluded.changed_at;
 if TG_OP='DELETE' then return OLD; else return NEW; end if;
end $$;
"""]
    # The image TYPE of a candidate, as derived metadata beside the evidence.
    # The learned panel typer writes its class per panel into each paper's
    # panels/panel_index.json (Blots, Graphs, Microscopy, Body Imaging, Flow
    # Cytometry); nothing carried it into the review queue, so a reviewer could
    # not ask for "just the blots". It lives in its OWN table, not in
    # component_items.record, because migration 006 makes a sealed run's item
    # record accept no update except the retirement marker -- it is evidence.
    # A model's classification is not evidence about the paper: the typer can
    # be wrong and can be replaced, so it is derived, re-computable, and keyed
    # to the item it describes. Created HERE, before the loop below attaches
    # its change-journal triggers, because that loop covers every KEYS table.
    statements.append("""
create table if not exists component_item_derived (
 item_id bigint primary key references component_items(id) on delete cascade,
 image_type text not null,
 panel_types jsonb not null default '{}'::jsonb,
 typer text,
 derived_at timestamptz not null default now()
);
create index if not exists component_item_derived_type on component_item_derived(image_type);
""")
    for table, keys in KEYS.items():
        args = ','.join(f"'{k}'" for k in keys)
        statements.append(f"""
drop trigger if exists workbench_serialize on {table};
create trigger workbench_serialize before insert or update or delete on {table}
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on {table};
create trigger workbench_journal after insert or update or delete on {table}
 for each row execute function workbench_journal({args});
""")
    return '\n'.join(statements)


def describe_error(exc):
    """A sync failure, leading with its most informative cause.

    libpq tries every address of the host and reports the LAST failure first:
    on 2026-10-01 the status read "Cannot assign requested address" (this
    machine has no IPv6 route) while every IPv4 address had answered "Your
    account or project has exceeded the quota". A refusal the server SAID
    outranks a network failure on the way to it; the full text follows.
    """
    import re
    from collections import Counter
    text = str(exc)
    attempts = re.findall(r"hostaddr: '([^']*)': [^:]+: (.*?)(?=\n- host:|\Z)", text, re.S)
    if len(attempts) < 2:
        return f'{type(exc).__name__}: {text}'
    server, network = [], []
    for _address, detail in attempts:
        said = re.search(r'(?:ERROR|FATAL):\s*([^\n]+)', detail)
        if said: server.append(said.group(1).strip())
        else: network.append(detail.rsplit('failed:', 1)[-1].strip().splitlines()[0])
    if server:
        cause, n = Counter(server).most_common(1)[0]
        lead = f'the database server refused the connection: {cause} ({n} of {len(attempts)} addresses'
        lead += f'; {len(network)} other(s) unreachable: {Counter(network).most_common(1)[0][0]})' if network else ')'
    else:
        cause, n = Counter(network).most_common(1)[0]
        lead = f'no address of the database server was reachable: {cause} ({n} of {len(attempts)} addresses)'
    return f'{type(exc).__name__}: {lead}. Details: {text}'


class Remote:
    """Used only by the single network worker; no interactive SQLite lock is held."""
    def __init__(self, url=None):
        self.url, self.conn = url, None
        self.bytes = 0
        self._summaries = {}

    def connect(self):
        if self.conn is None or self.conn.closed:
            from ..db_push import _connect
            self.conn = _connect(self.url, connect_timeout=5)
            self.conn.autocommit = True
            self.conn.execute("set statement_timeout='15s'")
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
        self.conn = None
        self._summaries.clear()

    def summary(self, table):
        if table not in self._summaries:
            # Exclude large evidence columns BEFORE JSON conversion. Subtracting
            # them from to_jsonb(t) still detoasts/serializes every full payload.
            columns = self.connect().execute(
                'select attname from pg_attribute where attrelid=%s::regclass '
                'and attnum>0 and not attisdropped order by attnum', [table]).fetchall()
            keep = [name for (name,) in columns if name not in SUMMARY_EXCLUDED.get(table, set())]
            selected = ','.join('t."' + name.replace('"', '""') + '"' for name in keep)
            base = f'(select to_jsonb(s) from (select {selected}) s)'
            self._summaries[table] = summary_expr(table, base)
        return self._summaries[table]

    def migrate(self):
        c = self.connect()
        with c.transaction():
            c.execute("set local lock_timeout='5s'")
            c.execute(migration_sql())

    def rows(self, table, keys=None, after='', limit=500):
        c = self.connect()
        key = key_expr(table)
        where, args = key_filter(table, keys=keys, after=after)
        order = ','.join('t.' + col for col in KEYS[table])
        rows = c.execute(f'select {key},{self.summary(table)} from {table} t where {where} order by {order} limit %s', [*args, limit]).fetchall()
        self.bytes += len(json.dumps(rows, default=str).encode())
        return rows

    def detail(self, table, key):
        if table not in ('findings','component_items','runs','executions'):
            raise ValueError('unsupported detail')
        where, args = key_filter(table, keys=[key])
        row = self.connect().execute(f'select to_jsonb(t) from {table} t where {where}', args).fetchone()
        if not row:
            raise LookupError('Shared record no longer exists')
        self.bytes += len(json.dumps(row[0], default=str).encode())
        return row[0]

    def bootstrap(self, catalog):
        c = self.connect()
        # A repeatable snapshot pairs the summary pages with their exact watermark.
        with c.transaction():
            c.execute('set transaction isolation level repeatable read, read only')
            cursor = c.execute('select coalesce(max(revision),0) from workbench_changes').fetchone()[0]
            generation = catalog.begin_snapshot()
            for table in KEYS:
                after = ''
                while True:
                    rows = self.rows(table, after=after)
                    if not rows:
                        break
                    catalog.stage_snapshot(generation, table, rows)
                    after = rows[-1][0]
            catalog.finish_snapshot(generation, cursor)

    def sync(self, catalog):
        from ..atomicio import file_lock
        # Multiple app instances and the explicit sync CLI share one private DB.
        with file_lock(catalog.path.with_suffix('.sync.lock')):
            return self._sync_locked(catalog)

    def identity(self):
        """A stable name for the database on the other end of this connection.

        `system_identifier` is unique per PostgreSQL cluster and survives
        restarts, so cluster+database distinguishes two servers that happen to
        hold the same schema -- which is exactly the case a database switcher
        creates.
        """
        row = self.connect().execute(
            "select system_identifier::text || '/' || current_database() "
            "from pg_control_system()").fetchone()
        return row[0] if row else None

    def _sync_locked(self, catalog):
        c = self.connect()
        # The cache is a projection of ONE database, and `cursor` is a watermark
        # into that database's workbench_changes.revision sequence. Pointed at a
        # different database the watermark is meaningless: a higher max revision
        # there would replay unrelated changes, a lower one would skip every
        # change silently, and either way the pages would keep serving rows from
        # the database we just left. So a change of identity discards the cache
        # and re-snapshots rather than syncing incrementally.
        seen, now = catalog.state('db_identity'), self.identity()
        if now and seen != now:
            if seen is not None:
                catalog.reset_for_new_database(now)
            catalog.set_state('db_identity', now)
        if catalog.state('cursor') is None:
            self.bootstrap(catalog)
        while True:
            cursor = int(catalog.state('cursor') or 0)
            with c.transaction():
                c.execute('set transaction isolation level repeatable read, read only')
                changes = c.execute('select revision,entity,key,deleted from workbench_changes where revision>%s order by revision limit 500', [cursor]).fetchall()
                if not changes:
                    break
                grouped = {}
                for rev, table, key, deleted in changes:
                    grouped.setdefault(table, {})[key] = deleted
                updates = []
                for table, keys in grouped.items():
                    current = dict(self.rows(table, keys=list(keys)))
                    updates.extend((table,key,current.get(key)) for key in keys)
                catalog.apply_changes(updates, changes[-1][0])
        self.refresh_region_summaries(catalog)
        self.refresh_tool_summaries(catalog)
        catalog.set_state('synced_at', __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())

    def refresh_region_summaries(self, catalog):
        """Add bounded geometry to pre-feature caches in the background sync.

        No evidence/run writes, no media or full-detail downloads, and no
        journal-watermark movement. Presence marks completion even when the
        saved item has no measurement. New/changed rows get it in summary().
        """
        stamp = [2, catalog.state('db_identity')]
        if catalog.state('region_summary_schema') == stamp:
            return
        after = ''
        while True:
            keys = [key for (key,) in catalog.reader.execute(
                "select key from records where entity='component_items' "
                "and key>? "
                "order by key limit 500", [after])]
            if not keys:
                catalog.set_state('region_summary_schema', stamp)
                return
            ids = [json.loads(key)[0] for key in keys]
            expr = picked("t.record->'measurements'", REGION_FIELDS)
            rows = self.connect().execute(
                f'select t.id,{expr} from component_items t where t.id=any(%s)', [ids]).fetchall()
            self.bytes += len(json.dumps(rows, default=str).encode())
            found = dict(rows)
            # The normal sync lock serializes journal pulls with this patch.
            # Keep all other summary fields and any already cached full detail.
            with catalog.lock, catalog.db:
                catalog.db.executemany(
                    "update records set body=json_set(body,'$.record.region_measurements',json(?)) "
                    "where entity='component_items' and key=?",
                    [(json.dumps(found.get(i)), key) for i, key in zip(ids, keys)])
            after = keys[-1]

    def refresh_tool_summaries(self, catalog):
        """Add `tool_basis` to finding summaries cached before it existed.

        Modelled on `refresh_region_summaries`: bounded columns only, no
        detail download, no journal-watermark movement, and presence marks
        completion. Until it has run, such a row reads `not_recorded` -- never
        "model judgement", which would be a claim the cache cannot make.
        """
        # 2: `location_basis` joined `tool_basis` (1.83.0); one pass fills both.
        stamp = [2, catalog.state('db_identity')]
        if catalog.state('tool_summary_schema') == stamp:
            return
        after = ''
        while True:
            keys = [key for (key,) in catalog.reader.execute(
                "select key from records where entity='findings' "
                "and key>? order by key limit 500", [after])]
            if not keys:
                catalog.set_state('tool_summary_schema', stamp)
                return
            ids = [json.loads(key)[0] for key in keys]
            rows = self.connect().execute(
                f'select t.id,{TOOL_BASIS},{LOCATION_BASIS} from findings t '
                'where t.id=any(%s)', [ids]).fetchall()
            self.bytes += len(json.dumps(rows, default=str).encode())
            found = {row[0]: row[1:] for row in rows}
            with catalog.lock, catalog.db:
                catalog.db.executemany(
                    "update records set body=json_set(body,'$.tool_basis',json(?),"
                    "'$.location_basis',json(?)) where entity='findings' and key=?",
                    [(json.dumps((found.get(i) or (None, None))[0]),
                      json.dumps((found.get(i) or (None, None))[1]), key)
                     for i, key in zip(ids, keys)])
            after = keys[-1]

    def send_review(self, event):
        c = self.connect()
        with c.transaction():
            # Lock before user upsert too, maintaining the writer lock order.
            c.execute('select pg_advisory_xact_lock(7168340291)')
            row = c.execute('select id,paper_id from runs where run_uid=%s', [event['run_id']]).fetchone()
            if not row:
                raise ValueError('Run not yet in the database; decision remains pending')
            run, paper = row
            item = c.execute('select id,owner_paper_id from component_items where run_id=%s and item_uid=%s', [run,event['item']]).fetchone()
            finding = c.execute('select id,paper_id from findings where run_id=%s and (finding_id=%s or legacy_original_id=%s)', [run,event['item'],event['item']]).fetchone()
            if not item and not finding and event['item'] != '__paper__':
                raise ValueError('Decision target not recorded in this run')
            paper = (item or finding or [None,paper])[1]
            c.execute('insert into users(name,legacy_name) values(%s,%s) on conflict(legacy_name) do nothing', [event['reviewer']]*2)
            user = c.execute('select id from users where legacy_name=%s', [event['reviewer']]).fetchone()[0]
            existing = c.execute('select run_id,issue_key,decision,note,reviewer_id,extra,decided_at from reviews where event_uid=%s', [event['event_id']]).fetchone()
            if existing:
                # Compare INSTANTS, not ISO strings: timestamptz comes back in
                # the session's TimeZone, so on a non-UTC server an identical
                # retry read '20:00-04:00' against '00:00+00:00' and every
                # outbox retry was refused as a conflict.
                at = datetime.fromisoformat(event['at'].replace('Z', '+00:00'))
                stored = existing[6] if at.tzinfo else existing[6].replace(tzinfo=None)
                if tuple(existing[:6]) != (run,event['item'],event['decision'],event.get('note',''),user,event.get('extra',{})) or stored != at:
                    raise ValueError('Review event ID conflicts with an existing event')
                return
            c.execute('''insert into reviews(run_id,paper_id,component_item_pk,finding_pk,issue_key,
 reviewer_id,decision,note,decided_at,event_uid,extra) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)''',
                [run,paper,item[0] if item else None,finding[0] if finding and not item else None,
                 event['item'],user,event['decision'],event.get('note',''),event['at'],event['event_id'],json.dumps(event.get('extra',{}))])
