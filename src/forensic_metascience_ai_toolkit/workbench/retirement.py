"""Explicit retirement of superseded image payloads; local archives are untouched."""
import json
from pathlib import Path


def migrate(conn):
    sql=Path(__file__).resolve().parents[3]/'db/migrations/005_image_retirement.sql'
    with conn.transaction():
        conn.execute(sql.read_text())


def apply(conn, entries):
    """Apply a reviewed plan, rechecking replacement ownership and human reviews."""
    counts={'runs':0,'items':0,'artifacts':0}
    with conn.transaction():
        conn.execute('select pg_advisory_xact_lock(7168340291)')
        rows=conn.execute("""select old.id,newer.run_uid from
            jsonb_to_recordset(%s::jsonb) as requested(run_uid text,replacement text)
            join runs old on old.run_uid=requested.run_uid
            join runs newer on newer.run_uid=requested.replacement
            where old.component='image_forensics' and newer.component='image_forensics'
            and old.paper_id=newer.paper_id
            and old.history_record->>'scope_key' is not distinct from newer.history_record->>'scope_key'
            and coalesce(newer.execution_status,newer.status) in ('complete','completed')
            and coalesce(newer.history_record->>'latest_eligible','true')!='false' and newer.retired_at is null
            and (old.analysed_at<newer.analysed_at or old.history_record->>'latest_eligible'='false')
            and old.retired_at is null
            and not exists(select 1 from reviews where run_id=old.id)
            order by old.id for update of old,newer""",[json.dumps(entries)]).fetchall()
        if not rows:
            return counts
        mapping=json.dumps([{'id':rid,'replacement':uid} for rid,uid in rows])
        ids=[rid for rid,uid in rows]
        counts['runs']=conn.execute("""update runs r set retired_at=clock_timestamp(),replacement_run_uid=m.replacement
            from jsonb_to_recordset(%s::jsonb) as m(id bigint,replacement text)
            where r.id=m.id""",[mapping]).rowcount
        counts['items']=conn.execute("""update component_items i set record=jsonb_build_object(
            'id',i.item_uid,'retired',true,'replacement_run',m.replacement)
            from jsonb_to_recordset(%s::jsonb) as m(id bigint,replacement text)
            where i.run_id=m.id and not coalesce((i.record->>'retired')::boolean,false)""",
            [mapping]).rowcount
        counts['artifacts']=conn.execute("""update run_artifacts set record=jsonb_build_object(
            'name',record->>'name','retired',true) where run_id=any(%s)""",[ids]).rowcount
    return counts
