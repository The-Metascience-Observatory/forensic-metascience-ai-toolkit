"""Explicit image-result reset. The disk half lives in the image package
(`metascience_observatory_image_analysis.review_workbench.image_cleanup`); the
Neon half -- the migration this repository ships and the database delete --
stays here, with the host's database."""
from pathlib import Path



def __getattr__(name):
    """`clear_disk`, `disk_plan`: the image package's disk half."""
    if name in ("clear_disk", "disk_plan"):
        from ..image_plugin import load
        return getattr(load("review_workbench.image_cleanup"), name)
    raise AttributeError(name)


def migrate(conn):
    path = Path(__file__).resolve().parents[3]/'db/migrations/006_image_reset.sql'
    with conn.transaction(): conn.execute(path.read_text())


def clear_database(conn, project, run_uids):
    """Delete only the named image runs' payloads, retaining identity tombstones."""
    counts = {}
    with conn.transaction():
        conn.execute('select pg_advisory_xact_lock(7168340291)')
        rows = conn.execute("""select r.id from runs r join papers p on p.id=r.paper_id
            join corpora c on c.id=p.corpus_id where c.name=%s and r.run_uid=any(%s)
            and (r.component='image_forensics' or r.kind='image_track') for update of r""",
            [project,run_uids]).fetchall()
        ids = [row[0] for row in rows]
        if len(ids) != len(set(run_uids)): raise ValueError('Image reset scope changed; rebuild the plan')
        conn.execute("""update runs set retired_at=coalesce(retired_at,clock_timestamp()),
            replacement_run_uid=null,retirement_reason='user_requested_rerun',meta='{}'::jsonb
            where id=any(%s)""",[ids])
        counts['runs'] = len(ids)
        for table in ('reviews','run_review_status','run_channels'):
            counts[table] = conn.execute(f'delete from {table} where run_id=any(%s)',[ids]).rowcount
        counts['item_papers'] = conn.execute('delete from component_item_papers where item_id in (select id from component_items where run_id=any(%s))',[ids]).rowcount
        for table in ('component_items','findings','run_artifacts'):
            counts[table] = conn.execute(f'delete from {table} where run_id=any(%s)',[ids]).rowcount
        counts['publication'] = conn.execute('delete from image_publication where corpus_id=(select id from corpora where name=%s)',[project]).rowcount
    return counts
