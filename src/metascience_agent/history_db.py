"""Idempotent archive mirror. History is copied verbatim, never re-screened."""

from __future__ import annotations
import json
from pathlib import Path
from .analysis_runs import Archive, read




#: Rows per jsonb parameter. Postgres caps a jsonb value at 268,435,455 bytes
#: (256 MB) and rejects the whole statement above it: "total size of jsonb
#: array elements exceeds the maximum". MEASURED 2026-09-14 on
#: the embargoed 2026-09 corpus: 14,451 run manifests, 549 MB on disk, sent as ONE
#: parameter -- so the second full sweep of that corpus could never sync, and
#: nothing said so except .analysis_runs/sync_error.json. 250 runs is ~10 MB
#: even at the largest per-run `meta` seen; the other tables' rows are far
#: smaller, so the same batch size is conservative everywhere. 250 keeps an
#: order of magnitude of headroom at 100 KB per run; test_history_db_encoding pins it.
SYNC_BATCH = 250


def _batched(cur, sql: str, rows: list, *, encode, before=()) -> list:
    """Execute `sql` once per SYNC_BATCH rows, returning every fetched row.

    The statements this serves all take the row list as their LAST parameter
    via `jsonb_array_elements(%s::jsonb)`; `before` supplies any parameters
    that precede it. An empty `rows` still executes once, so a statement's
    side effects (none today) and its shape are the same as before batching,
    and RETURNING rows are concatenated across batches so callers that count
    them keep counting the whole sync.
    """
    out = []
    chunks = [rows[i:i + SYNC_BATCH] for i in range(0, len(rows), SYNC_BATCH)] or [[]]
    for chunk in chunks:
        cur.execute(sql, (*before, encode(chunk)))
        if cur.description is not None:
            out.extend(cur.fetchall())
    return out

def encode_for_postgres(value) -> str:
    """JSON for a Postgres json/jsonb parameter, with U+0000 removed.

    Postgres cannot store a NUL in text or jsonb and rejects the whole
    statement: "unsupported Unicode escape sequence -- \\u0000 cannot be
    converted to text". MEASURED 2026-09-14: three eLife papers in
    the embargoed 2026-09 corpus carried a NUL inside caption text, the sweep's sync is
    one transaction, and so ONE byte rolled back the push of all 3,032 papers.
    The viewer kept showing the previous sweep, the failure was recorded only in
    .analysis_runs/sync_error.json, and nothing said so anywhere a person looks.

    Scrubbed on the ENCODED text rather than by walking the object: json.dumps
    always renders U+0000 as the six characters \\u0000, so a single replace
    covers every nesting depth and every value type with nothing to forget.
    The importer already treats a NUL as a conflict to report
    (workbench/importer.py); here it is dropped, because a caption with a stray
    control byte is still the caption and a corpus that cannot sync is worse.
    """
    return json.dumps(value, default=str).replace("\\u0000", "")

def migration_sql():
    source = Path(__file__).with_name("analysis_history.sql")
    return source.read_text()


def migrate(conn):
    with conn.transaction():
        conn.execute(migration_sql())
    return {"migration": "003_analysis_history", "applied": True}


#: Parent components whose sealed `document` is a findings-v2 report. A
#: partial pipeline (`tools_only`: tools agent, no adjudicator) seals its
#: report under `partial_review` so it never stands as the paper's review --
#: but its findings are still findings. Uploading only `comprehensive` sent a
#: partial run's run row and NONE of its findings, and the importer then
#: skipped the report push for the same run id, so the workbench showed the
#: run and nothing in it (2026-10-18, the GRIM ground-truth tools_only runs).
#: `runs.kind` keeps them apart: `partial_review`, never `full_review`.
REPORT_COMPONENTS = frozenset({"comprehensive", "partial_review"})

#: Archive component -> `runs.kind`. `partial_review` matches what
#: `discovery.run_kind` gives the same document on the report-push path.
RUN_KINDS = {
    "comprehensive": "full_review",
    "partial_review": "partial_review",
    "image_forensics": "image_track",
    "copy_paste": "copy_paste",
}


def _sync_report_findings(cur, runs, run_ids, paper_ids):
    """Hydrate the existing report index from the preserved document, once.

    Component candidates never enter this table. A conflicting stored finding
    is an import conflict, not permission to rewrite a historical report.
    """
    rows = [
        {"run": run_ids[r["id"]], "paper": paper_ids[r["paper"]], "record": f}
        for r in runs
        if r["component"] in REPORT_COMPONENTS and isinstance(r.get("document"), dict)
        for f in r["document"].get("findings", [])
    ]
    payload = encode_for_postgres(rows)
    cur.execute(
        """select f.run_id,f.finding_id from findings f
        join jsonb_array_elements(%s::jsonb) e
          on f.run_id=(e->>'run')::bigint and f.finding_id=e->'record'->>'finding_id'
        where f.record is distinct from e->'record'""", (payload,),
    )
    conflicts = cur.fetchall()
    if conflicts:
        raise ValueError(f"stored report findings differ from archive: {conflicts}")
    cur.execute(
        """insert into findings(run_id,paper_id,finding_id,producer,technique,computed_by,
          title,description,outcome,severity,provisional_severity,severity_is_provisional,
          impossible,quarantined,adjudication_action,adjudication,tool_verdict,anchors,
          anchor_summary,web_sources,basis,legacy_original_id,record)
        select (e->>'run')::bigint,(e->>'paper')::bigint,f->>'finding_id',f->>'producer',
          f->>'technique',f->>'computed_by',f->>'title',f->>'description',f->>'outcome',
          (f->>'severity')::smallint,(f->>'provisional_severity')::smallint,
          coalesce((f->>'severity_is_provisional')::boolean,false),
          coalesce((f->>'impossible')::boolean,false),coalesce((f->>'quarantined')::boolean,false),
          f->'adjudication'->>'action',f->'adjudication',f->'tool_verdict',f->'anchors',
          f->'anchor_summary',f->'web_sources',f->>'basis',f->'legacy'->>'original_id',f
        from jsonb_array_elements(%s::jsonb) e
        cross join lateral (select e->'record' as f) d
        on conflict(run_id,finding_id) do nothing""", (payload,),
    )


def sync(root, conn, selected_runs=None):
    if selected_runs is not None and not selected_runs:
        return {"runs": 0, "items": 0, "reviews": 0}
    archive = Archive(root)
    if selected_runs:
        loaded = {}
        wanted = set(selected_runs)
        while wanted:
            uid = wanted.pop()
            if uid in loaded: continue
            r = archive.run(uid)
            loaded[uid] = r
            wanted.update(x for x in (r.get("parent_run_id"), r.get("revision_of")) if x and x not in loaded)
        runs = [loaded[uid] for uid in sorted(loaded)]
    else:
        runs = [archive.run(p.stem) for p in sorted((archive.base / "runs").glob("*.json"))]
    known = {r["id"] for r in runs}
    executions = [read(p) for p in sorted((archive.base / "executions").glob("*.json"))]
    if selected_runs:
        owners = {r["execution_id"] for r in runs}
        executions = [e for e in executions if e["id"] in owners or known.intersection(e.get("reused_run_ids", []))]
    executions = [{**e,'configuration':{**(e.get('configuration') or {}),'workbench_reused_run_ids':e.get('reused_run_ids',[])}} for e in executions]
    papers = sorted(
        {p["dir"] for r in runs for i in r["items"] for p in i["papers"]}
        | {r["paper"] for r in runs if r.get("paper")}
    )
    counts = {"runs": 0, "items": 0, "reviews": 0}
    encode = encode_for_postgres
    with conn.transaction():
        cur = conn.cursor()
        # `papers_root` is WHERE THIS MACHINE READ THE CORPUS. It is a hint
        # for the workbench, never an identity: a viewer uses it only after
        # checking the directory exists on its own disk, so another
        # machine's path is simply ignored there. Without it the workbench
        # had exactly one way to learn a corpus's folder (a local
        # notification at sweep time) and, that missed, every archived PDF
        # and panel image of the run was "Missing" (Dan, 2026-09-14).
        cur.execute(
            "insert into corpora(name, papers_root) values(%s, %s) "
            "on conflict(name) do update set papers_root=excluded.papers_root",
            (archive.root.name, str(Path(archive.root).resolve())),
        )
        cur.execute("select id from corpora where name=%s", (archive.root.name,))
        corpus = cur.fetchone()[0]
        cur.execute(
            "insert into papers(corpus_id,dir) select %s,value from jsonb_array_elements_text(%s::jsonb) on conflict(corpus_id,dir) where dir is not null do nothing",
            (corpus, encode(papers)),
        )
        cur.execute("select dir,id from papers where corpus_id=%s", (corpus,))
        paper_ids = dict(cur.fetchall())
        cur.execute(
            """insert into executions(execution_uid,corpus_id,mode,name,requested_components,configuration,provenance,started_at,finished_at,status)
            select e->>'id',%s,e->>'mode',e->>'name',e->'requested_components',e->'configuration',e->'provenance',(e->>'started_at')::timestamptz,(e->>'finished_at')::timestamptz,e->>'status'
            from jsonb_array_elements(%s::jsonb) e on conflict(execution_uid) do update set status=excluded.status,finished_at=excluded.finished_at,configuration=excluded.configuration""",
            (corpus, encode(executions)),
        )
        payload = []
        for r in runs:
            owner = r.get("paper") or min(
                (p["dir"] for i in r["items"] for p in i["papers"]), default=None
            )
            kind = RUN_KINDS.get(r["component"], "component")
            payload.append(
                {
                    "uid": r["id"],
                    "paper": paper_ids.get(owner),
                    "kind": kind,
                    "component": r["component"],
                    "status": {
                        "completed": "complete",
                        "unavailable": "incomplete",
                        "not_requested": "incomplete",
                        "refused": "failed",
                        "cancelled": "failed",
                    }.get(r["status"], r["status"]),
                    "execution": r["execution_id"],
                    "parent": r.get("parent_run_id") if r.get("parent_run_id") in known else None,
                    "revision": r.get("revision_of") if r.get("revision_of") in known else None,
                    "digest": r["sealed_digest"],
                    "state": r["status"],
                    "version": r.get("provenance", {}).get("version"),
                    "at": r.get("completed_at") or r.get("started_at"),
                    "meta": {k: v for k, v in r.items() if k not in {"items", "artifacts"}},
                }
            )
        conflicts = _batched(
            cur,
            "select r.run_uid from runs r join jsonb_array_elements(%s::jsonb) e on r.run_uid=e->>'uid' where r.sealed_digest is not null and r.sealed_digest<>e->>'digest'",
            payload, encode=encode,
        )
        if conflicts:
            raise ValueError(f"sealed database runs differ: {conflicts}")
        counts["runs"] = len(_batched(
            cur,
            """insert into runs(paper_id,run_uid,kind,component,status,execution_uid,parent_run_uid,revision_of,sealed_digest,execution_status,pipeline_version,analysed_at,history_record)
            select (e->>'paper')::bigint,e->>'uid',e->>'kind',e->>'component',e->>'status',e->>'execution',e->>'parent',e->>'revision',e->>'digest',e->>'state',e->>'version',(e->>'at')::timestamptz,e->'meta'
            from jsonb_array_elements(%s::jsonb) e on conflict(run_uid) do update set execution_uid=excluded.execution_uid,component=excluded.component,parent_run_uid=excluded.parent_run_uid,revision_of=excluded.revision_of,execution_status=excluded.execution_status,sealed_digest=excluded.sealed_digest,history_record=excluded.history_record where runs.sealed_digest is null returning id""",
            payload, encode=encode,
        ))
        cur.execute(
            "select run_uid,id from runs where run_uid=any(%s)", ([r["uid"] for r in payload],)
        )
        run_ids = dict(cur.fetchall())
        _sync_report_findings(cur, runs, run_ids, paper_ids)
        cur.execute("select run_id,item_uid,id from component_items where run_id=any(%s)",(list(run_ids.values()),))
        existing_items={(rid,uid):pk for rid,uid,pk in cur.fetchall()}
        items = [
            {
                "run": run_ids[r["id"]],
                "uid": i["id"],
                "owner": paper_ids[i["paper"]["dir"]],
                "record": i,
            }
            for r in runs
            if r["id"] in run_ids
            for i in r["items"]
            if (run_ids[r["id"]],i["id"]) not in existing_items
        ]
        counts["items"] = len(_batched(
            cur,
            """insert into component_items(run_id,item_uid,owner_paper_id,record) select (e->>'run')::bigint,e->>'uid',(e->>'owner')::bigint,e->'record' from jsonb_array_elements(%s::jsonb) e on conflict(run_id,item_uid) do nothing returning id""",
            items, encode=encode,
        ))
        cur.execute(
            "select run_id,item_uid,id from component_items where run_id=any(%s)",
            (list(run_ids.values()),),
        )
        item_ids = {(r, i): pk for r, i, pk in cur.fetchall()}
        associations = [
            {"item": item_ids[(run_ids[r["id"]], i["id"])], "paper": paper_ids[p["dir"]]}
            for r in runs
            if r["id"] in run_ids
            for i in r["items"]
            for p in i["papers"]
        ]
        _batched(
            cur,
            "insert into component_item_papers(item_id,paper_id) select (e->>'item')::bigint,(e->>'paper')::bigint from jsonb_array_elements(%s::jsonb) e on conflict do nothing",
            associations, encode=encode,
        )
        artifacts = [
            {"run": run_ids[r["id"]], "uid": aid, "record": a, "ref": f"__runs/{r['id']}/{aid}"}
            for r in runs
            if r["id"] in run_ids
            for aid, a in r["artifacts"].items()
        ]
        _batched(
            cur,
            """insert into run_artifacts(run_id,artifact_uid,role,content_sha256,size_bytes,local_reference,record) select (e->>'run')::bigint,e->>'uid',coalesce(e->'record'->>'role','source'),e->'record'->>'sha256',(e->'record'->>'size')::bigint,e->>'ref',e->'record' from jsonb_array_elements(%s::jsonb) e on conflict do nothing""",
            artifacts, encode=encode,
        )
        events = archive.base / "reviews.jsonl"
        events = (
            [json.loads(line) for line in events.read_text().splitlines()]
            if events.exists()
            else []
        )
        events = [e for e in events if e["run_id"] in run_ids]
        names = sorted({e["reviewer"] for e in events})
        cur.execute(
            "insert into users(name,legacy_name) select value,value from jsonb_array_elements_text(%s::jsonb) on conflict(legacy_name) do nothing",
            (encode(names),),
        )
        cur.execute("select legacy_name,id from users where legacy_name=any(%s)", (names,))
        users = dict(cur.fetchall())
        owners = {
            (r["id"], i["id"]): paper_ids[i["paper"]["dir"]] for r in runs for i in r["items"]
        }
        rows = [
            {
                **e,
                "run": run_ids[e["run_id"]],
                "target": item_ids[(run_ids[e["run_id"]], e["item"])],
                "paper": owners[(e["run_id"], e["item"])],
                "user": users[e["reviewer"]],
            }
            for e in events
        ]
        counts["reviews"] = len(_batched(
            cur,
            """insert into reviews(run_id,paper_id,component_item_pk,issue_key,reviewer_id,decision,note,decided_at,event_uid) select (e->>'run')::bigint,(e->>'paper')::bigint,(e->>'target')::bigint,e->>'item',(e->>'user')::bigint,e->>'decision',e->>'note',(e->>'at')::timestamptz,e->>'event_id' from jsonb_array_elements(%s::jsonb) e on conflict(event_uid) where event_uid is not null do nothing returning id""",
            rows, encode=encode,
        ))
    return counts



# ---------------------------------------------------------------------------
# Image type, derived per candidate from the typer's per-panel classes.
# ---------------------------------------------------------------------------

#: What the review queue can filter on. The five are the typer's classes as
#: written in panel_index.json; the two extras are the honest states an ITEM
#: can be in that a panel cannot.
IMAGE_TYPE_MIXED = "mixed"
IMAGE_TYPE_UNTYPED = "untyped"


def image_type_for(panel_types) -> str:
    """One image type for an item from its panels' classes.

    A single class when every TYPED panel agrees; `mixed` the moment a second
    class appears (no share threshold -- a chart beside a micrograph is a mixed
    item, whatever the proportions); `untyped` when no panel carries a class.
    Untyped panels do not vote: an item whose one typed panel is a blot beside
    two untyped crops is a blot item, not a mixed one, because "untyped" is
    absence of the typer, never a class.
    """
    classes = {t for t in (panel_types or {}).values() if t}
    if not classes:
        return IMAGE_TYPE_UNTYPED
    if len(classes) > 1:
        return IMAGE_TYPE_MIXED
    return next(iter(classes))


def _panel_index_types(root: Path, paper_dir: str, cache: dict) -> dict:
    """uid -> class for one paper, read once from panels/panel_index.json."""
    if paper_dir in cache:
        return cache[paper_dir]
    index = root / paper_dir / "panels" / "panel_index.json"
    types: dict = {}
    if index.is_file():
        try:
            for panel in (json.loads(index.read_text()).get("panels") or []):
                if panel.get("uid") and panel.get("panel_type"):
                    types[panel["uid"]] = panel["panel_type"]
        except (OSError, ValueError):
            types = {}
    cache[paper_dir] = types
    return types


def derive_image_types(root, runs) -> list[dict]:
    """Rows for component_item_derived, from the corpus's panel indexes.

    The index on disk is the paper's CURRENT one, so an older run's items are
    typed by the newest typing of the same panels. That is the intent: the type
    is a property of the panel image, not of the run that found the match, and
    a re-typed corpus should re-type its history. The uid namespace
    (`<doc>:xref<N>-seg<M>`) is stable across runs for the same crop.
    """
    root = Path(root)
    cache: dict = {}
    rows = []
    for r in runs:
        if r.get("component") != "image_forensics":
            continue
        typer = ((r.get("provenance") or {}).get("parameters") or {}).get("panel_detector")
        for item in r.get("items") or []:
            panel_types = {}
            for p in item.get("panels") or []:
                if not isinstance(p, dict) or not p.get("uid"):
                    continue
                paper_dir = p.get("paper_dir") or (item.get("paper") or {}).get("dir") or r.get("paper")
                if not paper_dir:
                    continue
                t = _panel_index_types(root, str(paper_dir), cache).get(p["uid"])
                if t:
                    panel_types[p["uid"]] = t
            rows.append({"run": r["id"], "item": item["id"],
                         "image_type": image_type_for(panel_types),
                         "panel_types": panel_types, "typer": typer})
    return rows


def sync_image_types(root, conn, selected_runs=None) -> dict:
    """Upsert derived image types for every image run in the archive.

    Its own transaction, separate from `sync()`: a typing problem must not roll
    back the evidence push, and the evidence push must not be held for typing.
    Only rows whose type actually changed are rewritten, so the change journal
    (and therefore every viewer's cache refresh) sees a re-sync as a no-op.
    """
    archive = Archive(root)
    runs = [archive.run(rid) for rid in read(archive.base / "index.json", {"runs": {}})["runs"]]
    if selected_runs is not None:
        runs = [r for r in runs if r["id"] in set(selected_runs)]
    rows = derive_image_types(root, runs)
    counts = {"items": len(rows), "typed": sum(r["image_type"] != IMAGE_TYPE_UNTYPED for r in rows)}
    with conn.transaction():
        cur = conn.cursor()
        written = _batched(
            cur,
            """insert into component_item_derived(item_id,image_type,panel_types,typer,derived_at)
            select ci.id,e->>'image_type',e->'panel_types',e->>'typer',now()
            from jsonb_array_elements(%s::jsonb) e
            join runs r on r.run_uid=e->>'run'
            join component_items ci on ci.run_id=r.id and ci.item_uid=e->>'item'
            on conflict(item_id) do update set image_type=excluded.image_type,
              panel_types=excluded.panel_types,typer=excluded.typer,derived_at=excluded.derived_at
            where component_item_derived.image_type is distinct from excluded.image_type
               or component_item_derived.panel_types is distinct from excluded.panel_types
            returning item_id""",
            rows, encode=encode_for_postgres,
        )
    counts["written"] = len(written)
    return counts

def try_sync(root, selected_runs=None):
    from . import db_push
    import os

    if os.environ.get("METASCIENCE_NO_DB_PUSH"):
        return {"state": "disabled", "detail": "METASCIENCE_NO_DB_PUSH is set"}
    try:
        configured = db_push.resolve_db_url()
    except db_push.DbUnavailable as exc:
        return {"state": "not_configured", "detail": str(exc)}
    if not configured:
        return {"state": "not_configured"}
    error_path = Archive(root).base / "sync_error.json"

    def _record(state: str, **fields):
        from .atomicio import atomic_write_text
        error_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(error_path, json.dumps({"state": state, **fields}, default=str))
        return {"state": state, **fields}

    try:
        with db_push._connect(None, connect_timeout=10) as conn:
            result = sync(root, conn, selected_runs)
    except Exception as exc:
        # The RUN sync failed: nothing landed (its transaction rolled back).
        # This is the state the viewer keeps showing a previous run in.
        return _record("pending", error=str(exc))

    # The run sync has COMMITTED -- `sync()` owns the outermost transaction on a
    # non-autocommit connection, so it is durable before anything below runs.
    # Derived image types ride along in their own transaction; a failure here
    # is named in the result and never undoes the evidence push.
    try:
        with db_push._connect(None, connect_timeout=10) as conn:
            result["image_types"] = sync_image_types(root, conn, selected_runs)
    except Exception as exc:
        result["image_types"] = {"state": "failed", "error": str(exc)}
    # Publication state is a SEPARATE step with its own refusals, and the
    # embargo is the routine one: `history_publication.sync` raises on a corpus
    # carrying EMBARGO.json, by design. Reporting that raise as
    # {"state": "pending"} said the whole sync had failed when the runs were in
    # fact in the database, and left a sync_error.json that read like a push
    # failure. A refused publication step is named as exactly that.
    from .history_publication import EmbargoViolation, sync as sync_publication
    try:
        with db_push._connect(None, connect_timeout=10) as conn:
            publication = sync_publication(root, conn)
    except EmbargoViolation as exc:
        return _record("synced", **result, publication={"state": "refused",
                                                          "reason": "embargo",
                                                          "detail": str(exc)})
    except Exception as exc:
        return _record("synced", **result, publication={"state": "failed",
                                                          "error": str(exc)})
    error_path.unlink(missing_ok=True)
    return {"state": "synced", **result, "publication": publication}
