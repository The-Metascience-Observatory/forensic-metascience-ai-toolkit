"""The public findings site's data: projects, what may be shown, status events, snapshot.

The site ("Scaling Forensic Metascience") is static. It is built from a folder of JSON
files, the snapshot, that `write_snapshot` produces from three tables of the local
findings database (db/migrations/007_publication.sql). Nothing else is ever online.

A paper is shown for a project when `is_public` says so:

- policy `ai_triaged` (the seeded-RNG screens): the tool's exporter marked it eligible,
  unless a person withdrew it;
- policy `human_approved` (everything else): only when a person published it.

A person's `published` always shows a paper and `withdrawn` always hides it.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

POLICIES = ("ai_triaged", "human_approved")
STATES = ("draft", "published", "withdrawn")

#: Status events, in the order a case usually moves. The value is the label the site shows.
KINDS = {
    "ai_reviewed": "Reviewed by AI",
    "human_reviewed": "Reviewed by a human",
    "pubpeer_submitted": "Submitted to PubPeer",
    "plos_comment_submitted": "Submitted to PLOS ONE comments",
    "authors_emailed": "Authors emailed",
    "journal_emailed": "Journal emailed",
    "authors_responded": "Authors responded",
    "journal_responded": "Journal responded",
    "correction": "Correction published",
    "expression_of_concern": "Expression of concern published",
    "retraction": "Retraction published",
}


def norm_doi(doi: str) -> str:
    d = doi.strip().lower()
    d = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", d)
    d = re.sub(r"^doi:\s*", "", d)
    if not re.match(r"^10\.\d{4,9}/\S+$", d):
        raise ValueError(f"not a DOI: {doi!r}")
    return d


def paper_id(doi: str) -> str:
    """The DOI as a file and URL name: 10.1002/ece3.10748 -> 10.1002--ece3.10748."""
    return re.sub(r"[^a-z0-9._()-]", "_", norm_doi(doi).replace("/", "--"))


def is_public(policy: str, state: str, ai_eligible: bool) -> bool:
    if state == "withdrawn":
        return False
    if state == "published":
        return True
    return policy == "ai_triaged" and bool(ai_eligible)


# ---- pure: rows -> snapshot ---------------------------------------------------------------

def build_snapshot(projects: list[dict], publications: list[dict], events: list[dict],
                   generated_at: str | None = None) -> dict[str, object]:
    """{relative file name: JSON-ready object} for the whole site.

    `publications` rows carry `project_slug`; `events` rows carry `project_slug` or None.
    Events of a paper that is not shown anywhere are left out.
    """
    by_slug = {p["slug"]: p for p in projects}
    shown = [r for r in publications
             if is_public(by_slug[r["project_slug"]]["publish_policy"], r["state"], r["ai_eligible"])]
    shown_dois = {r["doi"] for r in shown}
    timeline: dict[str, list[dict]] = {}
    for e in sorted(events, key=lambda e: (str(e["occurred_on"]), list(KINDS).index(e["kind"])
                                           if e["kind"] in KINDS else 99, e.get("id") or 0)):
        if e.get("voided_at") or e["doi"] not in shown_dois:
            continue
        timeline.setdefault(e["doi"], []).append({
            "kind": e["kind"], "label": KINDS.get(e["kind"], e["kind"]),
            "date": str(e["occurred_on"]), "url": e.get("url"), "note": e.get("note"),
            "project": e.get("project_slug")})

    files: dict[str, object] = {}
    papers: dict[str, dict] = {}
    rows_by_project: dict[str, list[dict]] = {s: [] for s in by_slug}
    for r in sorted(shown, key=lambda r: (by_slug[r["project_slug"]]["sort_order"], r["project_slug"])):
        proj = by_slug[r["project_slug"]]
        pid = paper_id(r["doi"])
        cit = r.get("citation") or {}
        kinds = [e["kind"] for e in timeline.get(r["doi"], [])]
        human = r["state"] == "published" or "human_reviewed" in kinds
        rows_by_project[proj["slug"]].append({
            "id": pid, "doi": r["doi"], "title": cit.get("title"), "journal": cit.get("journal"),
            "year": cit.get("year"), "first_author": cit.get("first_author"),
            "one_line": r.get("one_line"), "review": "human" if human else "ai",
            "status": list(dict.fromkeys(kinds))})
        page = papers.setdefault(pid, {"id": pid, "doi": r["doi"], "citation": cit,
                                       "entries": [], "timeline": timeline.get(r["doi"], [])})
        page["entries"].append({
            "project": proj["slug"], "project_title": proj["title"], "tool": proj["tool"],
            "one_line": r.get("one_line"), "summary_md": r.get("summary_md"),
            "findings": r.get("findings") or [], "repo_url": r.get("repo_url"),
            "review": "human" if human else "ai", "ai_review": r.get("ai_review")})

    cards = []
    for p in sorted(projects, key=lambda p: (p["sort_order"], p["slug"])):
        rows = sorted(rows_by_project[p["slug"]],
                      key=lambda x: (-(x["year"] or 0), x["title"] or ""))
        card = {k: p.get(k) for k in ("slug", "title", "tool", "description", "corpus",
                                      "papers_screened", "publish_policy")}
        card["papers_with_findings"] = len(rows)
        cards.append(card)
        files[f"projects/{p['slug']}.json"] = {"project": card, "papers": rows}
    for pid, page in papers.items():
        files[f"papers/{pid}.json"] = page
    files["projects.json"] = {
        "generated_at": generated_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kinds": KINDS, "projects": cards}
    return files


def write_files(files: dict[str, object], out: Path) -> dict[str, int]:
    """Write the snapshot under `out`, removing project and paper files no longer in it.

    Only `projects.json`, `projects/*.json` and `papers/*.json` are ever touched.
    """
    out.mkdir(parents=True, exist_ok=True)
    counts = {"added": 0, "changed": 0, "removed": 0, "unchanged": 0}

    def body(obj) -> str:
        return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n"

    def same_but_time(a: str, b: str) -> bool:
        ja, jb = json.loads(a), json.loads(b)
        return isinstance(ja, dict) and isinstance(jb, dict) and \
            {**ja, "generated_at": 0} == {**jb, "generated_at": 0}

    changed_any = False
    pending_index = None
    for rel, obj in sorted(files.items()):
        path, text = out / rel, body(obj)
        old = path.read_text() if path.exists() else None
        if rel == "projects.json":
            pending_index = (path, text, old)
            continue
        if old == text:
            counts["unchanged"] += 1
            continue
        counts["added" if old is None else "changed"] += 1
        changed_any = True
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    for sub in ("projects", "papers"):
        for path in (out / sub).glob("*.json"):
            if f"{sub}/{path.name}" not in files:
                path.unlink()
                counts["removed"] += 1
                changed_any = True
    if pending_index:
        path, text, old = pending_index
        # A new timestamp alone is not a change: an unchanged site makes no diff.
        if old is None or changed_any or not same_but_time(old, text):
            path.write_text(text)
            counts["added" if old is None else "changed"] += 1
        else:
            counts["unchanged"] += 1
    return counts


# ---- database -----------------------------------------------------------------------------

def _connect(db_url: str | None = None):
    from . import db_push
    return db_push._connect(db_url, connect_timeout=10)


def _project_id(conn, slug: str) -> int:
    row = conn.execute("select id from screening_projects where slug=%s", (slug,)).fetchone()
    if not row:
        raise ValueError(f"no screening project {slug!r}: create it with `publish project`")
    return row[0]


def upsert_project(conn, *, slug: str, title: str, tool: str, policy: str,
                   description: str | None = None, corpus: str | None = None,
                   papers_screened: int | None = None, sort_order: int = 0) -> None:
    if policy not in POLICIES:
        raise ValueError(f"policy must be one of {POLICIES}")
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", slug):
        raise ValueError("slug: lowercase letters, digits and hyphens")
    conn.execute(
        """insert into screening_projects (slug,title,tool,description,corpus,papers_screened,
                                           publish_policy,sort_order)
           values (%s,%s,%s,%s,%s,%s,%s,%s)
           on conflict (slug) do update set title=excluded.title, tool=excluded.tool,
             description=excluded.description, corpus=excluded.corpus,
             papers_screened=excluded.papers_screened, publish_policy=excluded.publish_policy,
             sort_order=excluded.sort_order, updated_at=now()""",
        (slug, title, tool, description, corpus, papers_screened, policy, sort_order))


def import_candidates(conn, project: str, candidates: list[dict]) -> dict[str, int]:
    """Replace a project's exporter-owned content with `candidates` (the full list).

    Each candidate: doi, citation, one_line, summary_md, findings, repo_url, ai_eligible,
    ai_review {category, model, date}. A paper missing from the list stays in the table but
    loses `ai_eligible`. `state` and the decision columns are never touched.
    """
    from psycopg.types.json import Jsonb  # noqa: PLC0415
    pid = _project_id(conn, project)
    seen = []
    for c in candidates:
        doi = norm_doi(c["doi"])
        seen.append(doi)
        review = c.get("ai_review") or None
        conn.execute(
            """insert into publications (project_id,doi,citation,one_line,summary_md,findings,
                                         repo_url,ai_eligible,ai_review)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (project_id,doi) do update set citation=excluded.citation,
                 one_line=excluded.one_line, summary_md=excluded.summary_md,
                 findings=excluded.findings, repo_url=excluded.repo_url,
                 ai_eligible=excluded.ai_eligible, ai_review=excluded.ai_review, updated_at=now()""",
            (pid, doi, Jsonb(c.get("citation") or {}), c.get("one_line"), c.get("summary_md"),
             Jsonb(c.get("findings") or []), c.get("repo_url"), bool(c.get("ai_eligible")),
             Jsonb(review) if review else None))
        if review and review.get("date"):
            add_event(conn, doi, "ai_reviewed", review["date"], project=project,
                      note=review.get("model"), event_uid=f"ai_reviewed:{project}:{doi}")
    dropped = conn.execute(
        "update publications set ai_eligible=false, updated_at=now() "
        "where project_id=%s and ai_eligible and not (doi = any(%s))", (pid, seen)).rowcount
    return {"candidates": len(seen), "eligible": sum(bool(c.get("ai_eligible")) for c in candidates),
            "no_longer_listed": dropped}


def add_event(conn, doi: str, kind: str, occurred_on: str | dt.date, *, project: str | None = None,
              url: str | None = None, note: str | None = None, actor: str | None = None,
              event_uid: str | None = None) -> None:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of: {', '.join(KINDS)}")
    day = occurred_on if isinstance(occurred_on, dt.date) else dt.date.fromisoformat(str(occurred_on)[:10])
    conn.execute(
        """insert into outreach_events (doi,project_id,kind,occurred_on,url,note,actor,event_uid)
           values (%s,%s,%s,%s,%s,%s,%s,%s)
           on conflict (event_uid) do update set occurred_on=excluded.occurred_on,
             note=excluded.note""",
        (norm_doi(doi), _project_id(conn, project) if project else None, kind, day, url, note,
         actor, event_uid))


def void_event(conn, event_id: int) -> bool:
    return conn.execute("update outreach_events set voided_at=now() where id=%s and voided_at is null",
                        (event_id,)).rowcount == 1


def set_state(conn, doi: str, project: str, state: str, *, by: str, note: str | None = None,
              record_event: bool = True) -> None:
    """A person's decision. `published` also records a `human_reviewed` event for today
    (not with `record_event=False`, for decisions made earlier and elsewhere)."""
    if state not in STATES:
        raise ValueError(f"state must be one of {STATES}")
    d = norm_doi(doi)
    n = conn.execute(
        "update publications set state=%s, decided_by=%s, decided_at=now(), decision_note=%s, "
        "updated_at=now() where project_id=%s and doi=%s",
        (state, by, note, _project_id(conn, project), d)).rowcount
    if n != 1:
        raise ValueError(f"{d} is not a candidate of project {project!r}; import it first")
    if state == "published" and record_event:
        add_event(conn, d, "human_reviewed", dt.date.today(), project=project, actor=by,
                  event_uid=f"human_reviewed:{project}:{d}")


def _rows(conn, sql: str) -> list[dict]:
    cur = conn.execute(sql)
    names = [c.name for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def load(conn) -> tuple[list[dict], list[dict], list[dict]]:
    projects = _rows(conn, "select * from screening_projects")
    pubs = _rows(conn, "select p.*, s.slug as project_slug from publications p "
                       "join screening_projects s on s.id=p.project_id")
    events = _rows(conn, "select e.*, s.slug as project_slug from outreach_events e "
                         "left join screening_projects s on s.id=e.project_id")
    return projects, pubs, events


def write_snapshot(out: Path, db_url: str | None = None) -> dict:
    with _connect(db_url) as conn:
        projects, pubs, events = load(conn)
    files = build_snapshot(projects, pubs, events)
    counts = write_files(files, out)
    return {"files": counts,
            "projects": {c["slug"]: c["papers_with_findings"] for c in files["projects.json"]["projects"]},
            "papers": sum(1 for f in files if f.startswith("papers/"))}
