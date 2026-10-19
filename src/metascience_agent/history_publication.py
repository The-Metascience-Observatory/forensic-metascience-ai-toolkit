"""Current publication eligibility, separate from immutable saved judgments."""

import json
from pathlib import Path
from .analysis_runs import Archive, now, read
from .atomicio import atomic_write_text

#: Corpora under a selection embargo carry an EMBARGO.json marker at their
#: root.  Publication is refused for those, because publishing our own findings
#: before the embargo lifts can spoil the purpose the corpus was assembled
#: for.  The marker is a file rather than a
#: database flag so the refusal survives any database state and any code path
#: that reaches publication.
EMBARGO_MARKER = "EMBARGO.json"


class EmbargoViolation(RuntimeError):
    """Publication was attempted for a corpus under a selection embargo."""


def embargo_of(root):
    """The embargo record for a corpus root, or None."""
    try:
        marker = Path(root) / EMBARGO_MARKER
        if marker.is_file():
            return json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # An unreadable marker is treated as present-and-unparseable below; it
        # must never read as "not embargoed".
        return {"track": "unknown", "reason": f"unreadable {EMBARGO_MARKER}"}
    return None


def assert_not_embargoed(root, *, action="publish"):
    """Raise if this corpus may not be published from.

    Deliberately a hard raise and not a silent filter: a guard that quietly
    drops embargoed rows looks identical, from the outside, to a guard that is
    not running at all.
    """
    rec = embargo_of(root)
    if rec:
        raise EmbargoViolation(
            f"refusing to {action} from {Path(root).name}: this corpus is under a "
            f"selection embargo (track={rec.get('track')!r}). {rec.get('reason', '')} "
            f"Remove {EMBARGO_MARKER} only with the corpus owner's explicit decision."
        )


def human_rejected(root, item_id, inputs_stamp):
    a = Archive(root)
    decisions = a.reviews()
    if not decisions:
        return False
    metadata = list(read(a.base / "index.json", {"runs": {}})["runs"].values())
    for (rid, iid), rec in decisions.items():
        if iid != item_id or not rec["decision"].startswith("false_positive"):
            continue
        run = a.run(rid)
        candidates = [
            r
            for r in metadata
            if r["component"] == "image_forensics"
            and r.get("paper") == run.get("paper")
            and r.get("latest_eligible", True)
        ]
        candidates.sort(key=lambda r: (r.get("completed_at") or r.get("started_at") or "", r["id"]))
        if candidates and candidates[-1]["id"] != rid:
            continue  # Another run's decision is context, never inherited.
        for item in run["items"]:
            if (
                item["id"] == iid
                and (item.get("screening") or {}).get("inputs_stamp") == inputs_stamp
            ):
                return True
    return False


def refresh(root, paper=None, *, papers=None):
    assert_not_embargoed(root, action="refresh publication state")
    from .image_plugin import load as _image_load
    _m = _image_load("image_review")
    _within_items, _cross_items, read_ledger = _m._within_items, _m._cross_items, _m.read_ledger
    from .discovery import iter_paper_dirs
    from .image_plugin import load as _image_load
    _m = _image_load("image_forensics.screening")
    published_items, input_stamp, policy_for = _m.published_items, _m.input_stamp, _m.policy_for

    a = Archive(root)
    dirs = list(papers) if papers is not None else ([Path(paper)] if paper else iter_paper_dirs(a.root))
    candidates = []
    for d in dirs:
        candidates.extend(_within_items(d, False, [], a.root))
    candidates.extend(_cross_items(dirs, False, read_ledger(a.root), [], a.root))
    published = {i["id"] for i in published_items(a.root, candidates)}
    if (a.base / "index.json").exists():
        saved = {i["id"] for i in a.feed()["items"]}
        published.intersection_update(saved)
    records = [
        {
            "item_uid": i["id"],
            "paper": i["paper"]["dir"],
            "policy": policy_for(i),
            "eligible": i["id"] in published,
            "source_fingerprint": input_stamp(a.root, i),
        }
        for i in candidates
    ]
    path = a.base / "publication.json"
    if paper or papers is not None:
        selected = {Path(d).resolve().relative_to(a.root).as_posix() for d in dirs}
        previous = read(path, {"items": []})["items"]
        records = [r for r in previous if r["paper"] not in selected] + records
    a.base.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps({"at": now(), "items": records}))
    return records


def shared_records(cur, corpus):
    """Project saved judgments, never this machine's directory inventory.

    File-stat screening stamps are opaque saved identities here: recomputing
    them on another machine would turn an unavailable file into a revocation.
    The producer archives revised judgments; current policy remains a separate
    eligibility check. Empty/failed latest attempts do not resurrect older runs.
    """
    from .image_plugin import load as _image_load
    _m = _image_load("image_forensics.screening")
    policy_for, survives = _m.policy_for, _m.survives

    cur.execute("""with ranked as (
        select r.*,row_number() over (
          partition by coalesce(r.history_record->>'scope_key',r.paper_id::text,'cross')
          order by r.analysed_at desc nulls last,r.id desc) as position
        from runs r join papers p on p.id=r.paper_id
        where p.corpus_id=%s and r.component='image_forensics'
          and r.retired_at is null
          and coalesce(r.history_record->>'latest_eligible','true')<>'false'
    )
    select p.dir,i.item_uid,i.record->>'detector_kind',i.record->'screening',
           i.record->>'cleared',
           array(select decision from (
             select distinct on (reviewer_id) reviewer_id,decision
             from reviews where run_id=r.id and issue_key=i.item_uid
             order by reviewer_id,decided_at desc,id desc
           ) judgments),publication.eligible,r.analysed_at>publication.updated_at
    from ranked r join component_items i on i.run_id=r.id
    join papers p on p.id=i.owner_paper_id
    left join image_publication publication on publication.corpus_id=%s
      and publication.paper_id=p.id and publication.item_uid=i.item_uid
    where r.position=1 and coalesce(i.record->>'retired','false')<>'true'
    order by p.dir,i.item_uid,r.analysed_at nulls first,r.id""", (corpus, corpus))
    records = {}
    for paper, uid, detector, screen, cleared, decisions, previous, newer in cur.fetchall():
        screen = screen or {}
        policy = policy_for({'detector_kind': detector})
        eligible = cleared == 'true' or (bool(screen.get('inputs_stamp')) and survives(screen, policy=policy))
        if previous is False and newer is not True:
            eligible = False  # Importing an old judgment cannot undo a revocation.
        if decisions and all(str(d).startswith('false_positive') for d in decisions):
            eligible = False
        if len(set(decisions)) > 1 and previous is False:
            eligible = False  # Disagreement does not undo an existing revocation.
        if cleared == 'true':
            eligible = True  # Retain deterministic clearances in the explicit audit view.
        records[(paper, uid)] = {
            'paper': paper, 'item_uid': uid, 'policy': policy,
            'eligible': eligible,
            'source_fingerprint': screen.get('inputs_stamp'),
        }
    return list(records.values())


def sync(root, conn):
    assert_not_embargoed(root, action="sync publication state")
    with conn.transaction():
        cur = conn.cursor()
        # Serialize the projection snapshot with authoritative writers, so an
        # older concurrent refresh cannot overwrite a newer publication state.
        cur.execute('select pg_advisory_xact_lock(7168340291)')
        cur.execute("select id from corpora where name=%s", (Path(root).name,))
        row = cur.fetchone()
        if not row:
            return {"records": 0}
        corpus = row[0]
        records = shared_records(cur, corpus)
        cur.execute(
            """insert into image_publication as current
           (corpus_id,paper_id,item_uid,policy,eligible,source_fingerprint)
           select %s,p.id,e->>'item_uid',e->>'policy',(e->>'eligible')::boolean,e->>'source_fingerprint'
           from jsonb_array_elements(%s::jsonb) e join papers p on p.corpus_id=%s and p.dir=e->>'paper'
           on conflict(corpus_id,paper_id,item_uid) do update set
             eligible=excluded.eligible,policy=excluded.policy,
             source_fingerprint=excluded.source_fingerprint,updated_at=now()
           where (current.policy,current.eligible,current.source_fingerprint)
             is distinct from (excluded.policy,excluded.eligible,excluded.source_fingerprint)""",
            (corpus, json.dumps(records), corpus),
        )
        cur.execute(
            """delete from image_publication current where current.corpus_id=%s
           and not exists (
             select 1 from jsonb_array_elements(%s::jsonb) e
             join papers p on p.corpus_id=%s and p.dir=e->>'paper'
             where p.id=current.paper_id and e->>'item_uid'=current.item_uid
           )""",
            (corpus, json.dumps(records), corpus),
        )
    cur.execute(
        "select count(*) from published_component_items i join papers p on p.id=i.owner_paper_id where p.corpus_id=%s",
        (corpus,),
    )
    return {"records": len(records), "published_items": cur.fetchone()[0]}
