"""Push findings-v2 documents into the local findings database (Postgres).

Contract: docs/specs/webapp_db.md sections 0-5. The database is the canonical
QUERYABLE store; files remain the per-run forensic archive and can always
rebuild the DB. Rules enforced here:

- BEST-EFFORT: an unreachable database never fails a paid run. A failed
  push appends to `<corpus>/db_push_pending.jsonl`; `--retry-pending`
  drains it. The auto-push hook swallows everything except KeyboardInterrupt.
- NAMED REFUSAL when the driver is absent (a base dependency since 1.94.0,
  so only a broken install): never a silent skip (the statcheck lesson,
  applied to the DB).
- One transaction PER RUN. Changed reports receive a linked revision ID;
  sealed history is preserved. Identical reports can hydrate missing index
  rows, and no-op replays do not rewrite findings. The legacy replacement
  statements operate only after revision identity has been resolved. Screens
  (`kind='screen'`) are never touched by file pushes.
- Paper identity: match (corpus_id, dir) first, then (corpus_id,
  lower(doi)) over ALL rows; insert only when neither matches (the
  promotion rule -- a DOI-only screen target later fetched keeps its row).
- The orphaned-reviews report: after each push, verdicts whose issue_key
  matches nothing current in that run are PRINTED, never dropped.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_URL_ENV = "METASCIENCE_DB_URL"
PENDING_NAME = "db_push_pending.jsonl"


class DbUnavailable(RuntimeError):
    """Named refusal: driver or URL missing. Message says how to fix it."""


def _dotenv_url(env_file: Path | None = None) -> str | None:
    """The database URL from the repo's gitignored `.env`, if present.

    The CLI and the webapp's spawned Python both run WITHOUT the shell
    profile that would export the variable, so an env-only lookup made the
    auto-push hook permanently silent on this machine -- the URL existed,
    in `.env`, and nothing read it. Repo root only (three levels above this
    file), never the cwd: a paper corpus must not be able to plant a `.env`
    that redirects pushes. (`env_file` is a test seam.)
    """
    if env_file is None:
        env_file = env_file_path()
        if env_file is None:
            return None
    return _dotenv_values(env_file).get(DB_URL_ENV) or None


def env_file_path() -> Path | None:
    """The `.env` every reader here uses: $METASCIENCE_ENV_FILE, else the repo
    root's (None for an install with no repo root)."""
    from .integration import default_env_file
    explicit = os.environ.get("METASCIENCE_ENV_FILE")
    return Path(explicit) if explicit else default_env_file


def _dotenv_values(env_file: Path) -> dict[str, str]:
    try:
        text = env_file.read_text()
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip("'\"")
    return values


#: The off switch, read from the environment OR the `.env`, so the choice
#: `metascience db-setup --no-database` records survives a new shell.
NO_DB_ENV = "METASCIENCE_NO_DB_PUSH"


def database_disabled() -> bool:
    """True when this machine has said it does without the findings database."""
    if os.environ.get(NO_DB_ENV):
        return True
    env_file = env_file_path()
    return bool(env_file and _dotenv_values(env_file).get(NO_DB_ENV))


#: Hosts a database URL may name. The findings database lives on THIS machine;
#: a URL naming any other host is refused rather than connected to, so a stale
#: `.env` cannot quietly send findings or review decisions off the machine.
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", ""})


def is_local_url(url: str) -> bool:
    """True when every host in a libpq URL is this machine (or a unix socket)."""
    from urllib.parse import parse_qs, urlsplit
    parts = urlsplit(url)
    hosts = []
    netloc = parts.netloc.rpartition("@")[2]
    for entry in netloc.split(","):
        entry = entry.strip()
        host = entry[1:entry.index("]")] if entry.startswith("[") else entry.partition(":")[0]
        hosts.append(host)
    hosts += parse_qs(parts.query).get("host", [])
    return all(h.lower() in LOCAL_HOSTS or h.startswith("/") for h in hosts)


def resolve_db_url(db_url: str | None = None) -> str | None:
    """Explicit arg > $METASCIENCE_DB_URL > repo .env. Local hosts only.

    Raises DbUnavailable for a URL naming another machine: the remote (Neon)
    database was retired 2026-10-16 and every store is local now.
    """
    url = db_url or os.environ.get(DB_URL_ENV) or _dotenv_url()
    if url and not is_local_url(url):
        raise DbUnavailable(
            f"{DB_URL_ENV} names a remote host; only a database on this machine "
            "(localhost, 127.0.0.1, ::1 or a unix socket) is supported")
    return url


def _connect(db_url: str | None, *, connect_timeout: int | None = None):
    url = resolve_db_url(db_url)
    if not url:
        raise DbUnavailable(
            f"no database URL: set {DB_URL_ENV} (a local Postgres connection "
            "string), put it in the repo .env, or pass --db-url")
    try:
        import psycopg  # noqa: PLC0415 -- deliberately lazy
    except ImportError as exc:
        raise DbUnavailable(
            "the psycopg driver is not installed -- it is a base dependency: "
            "reinstall with `pip install -e .`") from exc
    # AUTOCOMMIT, so every `with conn.transaction()` below is a real, committed
    # transaction. Without it the first statement opens an implicit
    # transaction, each later `transaction()` block is only a SAVEPOINT inside
    # it, and `close()` rolls the lot back: `metascience db-push` printed
    # "pushed 1 run(s)" and stored nothing (measured 2026-10-01).
    if connect_timeout is not None:
        return psycopg.connect(url, connect_timeout=connect_timeout,
                               autocommit=True)
    return psycopg.connect(url, autocommit=True)


def _doc_and_meta(review_dir: Path) -> tuple[dict, dict] | None:
    fp = review_dir / "findings.v2.json"
    if not fp.exists():
        return None
    try:
        doc = json.loads(fp.read_text())
    except Exception:  # noqa: BLE001
        return None
    meta = {}
    rm = review_dir / "run_meta.json"
    if rm.exists():
        try:
            meta = json.loads(rm.read_text())
        except Exception:  # noqa: BLE001
            meta = {}
    return doc, meta


def _paper_identity(doc: dict, paper_dir: Path, corpus: str) -> dict:
    pm = dict(doc.get("paper_metadata") or {})
    if not (pm.get("journal_normalized") or pm.get("year")):
        # The SAME fallback corpus_stats._metadata applies on the file side:
        # a doc whose projection lacks journal/year reads the paper's
        # metadata.json. Without this the DB stored the bare projection and
        # the --verify drift check flagged one 1999 paper as
        # "(no journal recorded)" in DB mode only.
        mp = Path(paper_dir) / "metadata.json"
        try:
            pm = {**json.loads(mp.read_text()), **{k: v for k, v in
                                                   pm.items() if v}}
        except Exception:  # noqa: BLE001
            pass
    doi = str(pm.get("doi") or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    from .analysis_runs import project_root
    root = project_root(paper_dir)
    relative = Path(paper_dir).resolve().relative_to(root).as_posix() if root.name == corpus else paper_dir.name
    return {"corpus": corpus, "dir": relative, "doi": doi or None,
            "title": pm.get("title"), "journal": pm.get("journal"),
            "journal_full": pm.get("journal_normalized"),
            "year": pm.get("year") if isinstance(pm.get("year"), int) else None,
            "first_author": pm.get("first_author"),
            "authors": json.dumps(pm.get("authors_list") or [], default=str),
            "metadata": json.dumps(pm, default=str)}


def _previous_state(previous) -> tuple[dict, dict]:
    """`(meta, history_record)` of an existing run row, as dicts.

    A NULL column reads as None, not as an empty object, and `_jsonb` passes
    None straight through. MEASURED 2026-09-12 on the local shared database:
    3,685 of 24,473 `runs` rows carry no `history_record` and 16,908 no
    `meta`, and `.get` on one of those aborted `push_run` for ALL 114 papers
    of the embargoed 2026-09 corpus -- so a whole corpus of screening judgments never
    reached the shared database, recorded only as an
    `AttributeError: 'NoneType' object has no attribute 'get'` in a
    per-paper pending reason nobody reads.
    """
    if not previous:
        return {}, {}
    return (_jsonb(previous[0]) or {}), (_jsonb(previous[1]) or {})


def push_run(conn, doc: dict, meta: dict, paper_dir: Path,
             corpus: str, run_name: str | None = None) -> dict:
    """Preserve report identity on replay; changed content creates a revision.

    Returns counts and orphaned-review keys for the caller to print.
    """
    ident = _paper_identity(doc, paper_dir, corpus)
    run_uid = doc.get("run_id")
    # A re-projected report is a revision, not permission to erase the prior run.
    from .analysis_runs import digest as history_digest
    content_digest = history_digest(doc)
    history_cur = conn.cursor()
    history_cur.execute("select meta, history_record from runs where run_uid=%s", (run_uid,))
    previous = history_cur.fetchone()
    old_meta, saved_history = _previous_state(previous)
    saved_document = saved_history.get("document")
    old_digest = (history_digest(saved_document) if isinstance(saved_document, dict)
                  else old_meta.get("content_digest"))
    if previous and old_digest != content_digest:
        original_uid = run_uid
        run_uid = f"{run_uid}_rev_{content_digest[:16]}"
        meta = {**meta, "revision_of": original_uid}
        doc = {**doc, "run_id": run_uid}
    meta = {**meta, "content_digest": content_digest}
    findings = [f for f in doc.get("findings") or [] if isinstance(f, dict)]
    legacy = doc.get("legacy") or {}
    adj = doc.get("adjudication") or {}
    with conn.transaction():
        cur = conn.cursor()
        cur.execute("insert into corpora (name) values (%s) "
                    "on conflict (name) do nothing", (corpus,))
        cur.execute("select id from corpora where name = %s", (corpus,))
        corpus_id = cur.fetchone()[0]
        # identity: dir first, then lower(doi) over ALL rows, insert last
        cur.execute("select id from papers where corpus_id=%s and dir=%s",
                    (corpus_id, ident["dir"]))
        row = cur.fetchone()
        if row is None and ident["doi"]:
            cur.execute("select id from papers where corpus_id=%s "
                        "and lower(doi)=%s", (corpus_id, ident["doi"]))
            row = cur.fetchone()
            if row is not None:   # promotion: the screen target gains a dir
                cur.execute("update papers set dir=%s where id=%s",
                            (ident["dir"], row[0]))
        if row is None:
            cur.execute(
                "insert into papers (corpus_id, dir, doi, title, journal, "
                "journal_full, year, first_author, authors, metadata) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id",
                (corpus_id, ident["dir"], ident["doi"], ident["title"],
                 ident["journal"], ident["journal_full"], ident["year"],
                 ident["first_author"], ident["authors"], ident["metadata"]))
            row = cur.fetchone()
        paper_id = row[0]
        # Fill-only-if-null metadata backfill: a paper first pushed from a
        # doc with no projection keeps its columns forever otherwise --
        # re-pushing after a metadata fetch must heal it, and never clobber
        # a value already present.
        cur.execute(
            "update papers set title=coalesce(title,%s), "
            "journal=coalesce(journal,%s), journal_full=coalesce(journal_full,%s), "
            "year=coalesce(year,%s), first_author=coalesce(first_author,%s), "
            "doi=coalesce(doi,%s), "
            # per-KEY fill-only on the jsonb too: existing keys win, new
            # keys land -- the stats reader takes journal/year from here
            "metadata=(%s::jsonb || coalesce(metadata,'{}'::jsonb)) "
            "where id=%s",
            (ident["title"], ident["journal"], ident["journal_full"],
             ident["year"], ident["first_author"], ident["doi"],
             ident["metadata"], paper_id))
        from .discovery import run_kind
        kind = run_kind(doc)
        cur.execute(
            "insert into runs (paper_id, run_uid, kind, name, status, "
            "verdict, paper_severity, pipeline_version, analysed_at, "
            "analysed_at_source, cost_usd, pushed_at, meta) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s) "
            "on conflict (run_uid) do update set status=excluded.status, "
            "name=coalesce(excluded.name, runs.name), "
            "verdict=excluded.verdict, paper_severity=excluded.paper_severity, "
            "pushed_at=now(), meta=excluded.meta returning id",
            (paper_id, run_uid, kind, run_name,
             "partial" if not adj.get("ran") else "complete",
             adj.get("verdict"), adj.get("paper_severity"),
             legacy.get("pipeline_version") or meta.get("version"),
             legacy.get("analysed_at") or meta.get("analysed_at"),
             legacy.get("analysed_at_source") or "recorded",
             meta.get("total_cost_usd"),
             json.dumps(meta, default=str)))
        run_pk = cur.fetchone()[0]
        cur.execute("delete from run_channels where run_id=%s", (run_pk,))
        for name, ch in (doc.get("channels") or {}).items():
            state = ch.get("state") if isinstance(ch, dict) else str(ch)
            detail = ch.get("detail") if isinstance(ch, dict) else None
            cur.execute("insert into run_channels (run_id, channel, state, "
                        "detail) values (%s,%s,%s,%s)",
                        (run_pk, name, state, detail))
        pushed_ids = [str(f.get("finding_id")) for f in findings]
        if pushed_ids:
            cur.execute(
                "delete from findings where run_id=%s and "
                "finding_id != all(%s)", (run_pk, pushed_ids))
        else:
            cur.execute("delete from findings where run_id=%s", (run_pk,))
        for f in findings:
            cur.execute(
                "insert into findings (run_id, paper_id, finding_id, "
                "producer, technique, computed_by, title, description, "
                "outcome, severity, provisional_severity, "
                "severity_is_provisional, impossible, quarantined, "
                "adjudication_action, adjudication, tool_verdict, anchors, "
                "anchor_summary, web_sources, basis, legacy_original_id, "
                "record) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                "%s,%s,%s,%s,%s,%s,%s) "
                "on conflict (run_id, finding_id) do update set "
                "title=excluded.title, description=excluded.description, "
                "outcome=excluded.outcome, producer=excluded.producer, "
                "technique=excluded.technique, computed_by=excluded.computed_by, "
                "provisional_severity=excluded.provisional_severity, "
                "severity_is_provisional=excluded.severity_is_provisional, "
                "impossible=excluded.impossible, quarantined=excluded.quarantined, "
                "tool_verdict=excluded.tool_verdict, web_sources=excluded.web_sources, "
                "basis=excluded.basis, legacy_original_id=excluded.legacy_original_id, "
                "severity=excluded.severity, "
                "adjudication_action=excluded.adjudication_action, "
                "adjudication=excluded.adjudication, "
                "anchors=excluded.anchors, "
                "anchor_summary=excluded.anchor_summary, "
                "record=excluded.record "
                "where findings.record is distinct from excluded.record",
                (run_pk, paper_id, f.get("finding_id"), f.get("producer"),
                 f.get("technique"), f.get("computed_by"), f.get("title"),
                 f.get("description"), f.get("outcome"), f.get("severity"),
                 f.get("provisional_severity"),
                 bool(f.get("severity_is_provisional")),
                 bool(f.get("impossible")), bool(f.get("quarantined")),
                 (f.get("adjudication") or {}).get("action"),
                 json.dumps(f.get("adjudication"), default=str),
                 json.dumps(f.get("tool_verdict"), default=str),
                 json.dumps(f.get("anchors"), default=str),
                 json.dumps(f.get("anchor_summary"), default=str),
                 json.dumps(f.get("web_sources"), default=str),
                 f.get("basis"),
                 (f.get("legacy") or {}).get("original_id"),
                 json.dumps(f, default=str)))
        cur.execute(
            "insert into sync_state (paper_id, scope, last_push_at, "
            "source_sha256) values (%s,%s,now(),%s) "
            "on conflict (paper_id, scope) do update set "
            "last_push_at=now(), source_sha256=excluded.source_sha256",
            (paper_id, "findings", legacy.get("source_sha256")))
    # Orphaned reviews: verdicts whose keys join nothing in this run.
    orphans: list[str] = []
    review = paper_dir / "review.json"
    if review.exists():
        try:
            data = json.loads(review.read_text())
            keys = set((data.get("issues") or {}).keys())
            known = {(f.get("legacy") or {}).get("original_id")
                     for f in findings} | {f.get("finding_id")
                                           for f in findings}
            orphans = sorted(k for k in keys if k not in known)
        except Exception:  # noqa: BLE001
            orphans = ["review.json unreadable"]
    return {"run_uid": run_uid, "paper": paper_dir.name,
            "paper_pk": paper_id,
            "n_findings": len(findings), "review_orphans": orphans}


_REVIEW_ENTRY_KEYS = ("decision", "note", "submitted_to_pubpeer",
                      "submitted_to_editor", "pubpeer_url", "reviewer", "at")


def _user_for(cur, legacy_name: str) -> int:
    cur.execute("select id from users where legacy_name = %s", (legacy_name,))
    row = cur.fetchone()
    if row is not None:
        return row[0]
    cur.execute("insert into users (legacy_name, name) values (%s, %s) "
                "returning id", (legacy_name, legacy_name))
    return cur.fetchone()[0]


def push_reviews(conn, paper_id: int, paper_dir: Path) -> dict:
    """Mirror review.json's verdicts into the append-only `reviews` table.

    Append-only with CHANGE DETECTION: a verdict identical to the latest
    stored row for its (run, issue, reviewer) inserts nothing, so bulk
    re-pushes do not manufacture history. Verdicts scoped to a run the
    database does not know (or sitting in the legacy "(unscoped)" bucket)
    are returned as `unmatched`, never silently dropped -- db-push's
    printed report carries them.

    Until 2026-08-21 nothing wrote this table at all; the orphan REPORT
    existed and read as though the verdicts were being mirrored.
    """
    from .review_io import UNSCOPED_RUN, load_review
    data = load_review(paper_dir)
    runs = data.get("runs") or {}
    pushed = unchanged = 0
    unmatched: list[str] = []
    cur = conn.cursor()
    for run_name, block in runs.items():
        issues = (block.get("issues") or {}) if isinstance(block, dict) else {}
        if not issues:
            continue
        run_pk = None
        if run_name != UNSCOPED_RUN:
            cur.execute("select id from runs where paper_id = %s and (run_uid = %s or name = %s)",
                        (paper_id, run_name, run_name))
            row = cur.fetchone()
            run_pk = row[0] if row else None
        if run_pk is None:
            unmatched.extend(f"{run_name}:{k}" for k in issues)
            continue
        for key, entry in issues.items():
            if not isinstance(entry, dict):
                continue
            reviewer = str(entry.get("reviewer") or "").strip() or "(unrecorded)"
            uid = _user_for(cur, reviewer)
            new = (entry.get("decision"),
                   bool(entry.get("submitted_to_pubpeer")),
                   bool(entry.get("submitted_to_editor")),
                   entry.get("pubpeer_url"), entry.get("note"))
            cur.execute(
                "select decision, submitted_to_pubpeer, submitted_to_editor, "
                "pubpeer_url, note from reviews where run_id=%s and "
                "issue_key=%s and reviewer_id=%s "
                "order by decided_at desc, id desc limit 1",
                (run_pk, key, uid))
            last = cur.fetchone()
            if last is not None and tuple(last) == new:
                unchanged += 1
                continue
            cur.execute(
                "select id from findings where run_id=%s and "
                "(finding_id=%s or legacy_original_id=%s)", (run_pk, key, key))
            f = cur.fetchone()
            extra = {k: v for k, v in entry.items()
                     if k not in _REVIEW_ENTRY_KEYS}
            cur.execute(
                "insert into reviews (run_id, paper_id, finding_pk, "
                "issue_key, reviewer_id, decision, note, "
                "submitted_to_pubpeer, submitted_to_editor, pubpeer_url, "
                "extra, decided_at) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                "coalesce(%s::timestamptz, now()))",
                (run_pk, paper_id, f[0] if f else None, key, uid,
                 new[0], new[4], new[1], new[2], new[3],
                 json.dumps(extra, default=str) if extra else None,
                 entry.get("at")))
            pushed += 1
    return {"pushed": pushed, "unchanged": unchanged, "unmatched": unmatched}


def mirror_review(paper_dir: Path, *, db_url: str | None = None) -> dict:
    """Click-time best-effort mirror for one paper's review.json. Returns a
    status record, never raises; the file stays master either way."""
    paper_dir = Path(paper_dir)
    try:
        if not resolve_db_url(db_url):
            return {"skipped": "no database URL"}
        conn = _connect(db_url, connect_timeout=10)
        try:
            corpus = _corpus_of(paper_dir)
            cur = conn.cursor()
            cur.execute(
                "select p.id from papers p join corpora c on c.id=p.corpus_id "
                "where c.name=%s and p.dir=%s", (corpus, paper_dir.name))
            row = cur.fetchone()
            if row is None:
                return {"skipped": "paper not in the database yet "
                                   "(db-push the corpus first)"}
            with conn.transaction():
                rec = push_reviews(conn, row[0], paper_dir)
            return rec
        finally:
            conn.close()
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 -- best-effort by contract
        return {"error": f"{type(exc).__name__}: {exc}"}


def _pending_path(root: Path) -> Path:
    return root / PENDING_NAME


def record_pending(root: Path, paper_dir: Path, reason: str) -> None:
    rec = {"paper": str(paper_dir), "reason": reason,
           "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    with _pending_path(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def _corpus_of(paper_dir: Path) -> str:
    """The corpus a paper belongs to: the first ancestor that is not a
    scaffolding directory.

    `paper_dir.parent.name` minted PHANTOM CORPORA (caught live by the
    first `corpus-stats --verify`, 2026-08-21): a paper archived at
    `<corpus>/done/<slug>` pushed under a corpus literally named "done",
    splitting the corpus's statistics across two rows keyed by an
    implementation detail of the batch runner. The scaffolding names are
    webapp_index's -- one register. Batch-dump folders NOT in that static
    set (a `grok_run/` some script created) still mislabel a single-paper
    auto-push; the bulk CLI push avoids that entirely by passing
    `corpus=<root>.name` explicitly.
    """
    from .discovery import _NOT_A_PAPER
    parent = Path(paper_dir).parent
    while parent.name in _NOT_A_PAPER and parent.parent != parent:
        parent = parent.parent
    return parent.name


def push_paper(paper_dir: Path, *, corpus: str | None = None,
               db_url: str | None = None, conn=None) -> list[dict]:
    """Every v2 document under one paper. Raises DbUnavailable (named) when
    there is nothing to connect with; other DB errors propagate to the
    caller, who decides between pending-journal and loud failure."""
    paper_dir = Path(paper_dir)
    corpus = corpus or _corpus_of(paper_dir)
    own = conn is None
    if own:
        conn = _connect(db_url)
    try:
        out = []
        docs = []
        for rd in sorted(paper_dir.glob("forensic_review*")):
            pair = _doc_and_meta(rd)
            if pair:
                docs.append((*pair, rd.name))
        pair = _doc_and_meta(paper_dir)
        if pair:
            docs.append((*pair, None))
        paper_pk = None
        for doc, meta, run_name in docs:
            rec = push_run(conn, doc, meta, paper_dir, corpus,
                           run_name=run_name)
            paper_pk = rec.get("paper_pk") or paper_pk
            out.append(rec)
        if paper_pk is not None:
            rec = push_reviews(conn, paper_pk, paper_dir)
            if rec.get("pushed") or rec.get("unmatched"):
                out.append({"paper": paper_dir.name, "reviews": rec})
        return out
    finally:
        if own:
            conn.close()


def auto_push(paper_dir: Path, review_dir: Path) -> dict | None:
    """The run-completion hook: fire-and-forget when a database URL
    resolves (env or repo .env). NEVER raises -- an unreachable database must
    not fail a paid run; the failure lands in the pending journal instead."""
    if database_disabled():
        # AN EXPLICIT OFF SWITCH, because the default is ON and the default is
        # the real database. `resolve_db_url` falls back to the repo's .env so
        # the CLI works without an exported variable, which means any script
        # that reaches `write_parallel_outputs` -- an experiment, an agent
        # driving the writer on synthetic findings to see what it emits --
        # pushes those findings to production unless it knows to monkeypatch
        # an internal. The suite is already covered by an autouse fixture in
        # tests/conftest.py; this is the equivalent for everything that is not
        # the suite, and it is reported rather than silent so a caller can tell
        # "did not push" from "pushed nothing".
        return {"pushed": 0, "skipped": f"{NO_DB_ENV} is set"}
    try:
        if not resolve_db_url():
            return None
    except DbUnavailable as exc:  # a remote URL: refused, reported, never fatal
        return {"pushed": 0, "skipped": str(exc)}
    paper_dir = Path(paper_dir)
    try:
        records = push_paper(paper_dir)
        return {"pushed": len(records)}
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 -- best-effort by contract
        try:
            record_pending(paper_dir.parent, paper_dir,
                           f"{type(exc).__name__}: {exc}")
        except Exception:  # noqa: BLE001
            pass
        return {"pushed": 0, "pending": True, "reason": str(exc)}


def query_findings(corpus: str, *, technique: str | None = None,
                   min_severity: int | None = None,
                   producer: str | None = None, journal: str | None = None,
                   year: int | None = None, impossible_only: bool = False,
                   db_url: str | None = None, conn=None) -> list[dict]:
    """The SQL twin of the CLI's file-scan findings query.

    Same semantics on purpose -- every run of every paper in the corpus
    (the file scan reads every findings.v2.json, so a "current runs only"
    DB answer would silently disagree with offline mode), problem rows
    only, adjudicator-discarded rows excluded. Output rows carry the same
    keys as the file scan so the two modes are byte-comparable after
    ordering; `tests` and the live drift check compare them as sets keyed
    on (run_id, finding_id).
    """
    sql = (
        "select f.finding_id, p.dir, r.run_uid, f.technique, f.producer, "
        "f.severity, f.severity_is_provisional, f.impossible, f.title, "
        "coalesce(p.journal_full, p.journal, '') as journal, p.year "
        "from findings f "
        "join runs r on r.id = f.run_id "
        "join papers p on p.id = f.paper_id "
        "join corpora c on c.id = p.corpus_id "
        "where c.name = %s and f.outcome = 'problem' "
        "and coalesce(f.adjudication_action, 'kept') <> 'discarded'")
    params: list = [corpus]
    if technique:
        sql += " and f.technique = %s"
        params.append(technique)
    if producer:
        sql += " and f.producer = %s"
        params.append(producer)
    if min_severity:
        sql += " and f.severity >= %s"
        params.append(min_severity)
    if journal:
        sql += " and coalesce(p.journal_full, p.journal, '') ilike %s"
        params.append(f"%{journal}%")
    if year:
        sql += " and p.year = %s"
        params.append(year)
    if impossible_only:
        sql += " and f.impossible"
    sql += " order by p.dir, r.run_uid, f.id"
    owned = conn is None
    if owned:
        conn = _connect(db_url)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = ("finding_id", "paper_id", "run_id", "technique", "producer",
                "severity", "severity_is_provisional", "impossible", "title",
                "journal", "year")
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        if owned:
            conn.close()


def _jsonb(value: Any) -> Any:
    """psycopg returns jsonb as Python objects; a fake or a text column
    returns a string. Accept both, and never let a bad row raise."""
    if isinstance(value, (dict, list)) or value is None:
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def fetch_paper_runs(paper_dir: Path, *, corpus: str | None = None,
                     db_url: str | None = None, conn=None,
                     connect_timeout: int = 10) -> dict:
    """Every run the findings database holds for one paper, as v2-shaped docs.

    The READ twin of `push_run`, for the workbench. A paper analysed on
    another machine has no `forensic_review*/` on this disk but does have
    its rows in the findings database (the auto-push), and the review pane used to say "No
    reviewable issues on disk" about it -- true, and read as nothing having
    been recorded anywhere (`10.1002--jfa2.70171`, 2026-09-01: 24 findings
    in the database, none on this disk).

    Identity is the push rule read backwards: (corpus, dir) first, then
    lower(doi) over ALL corpora. 30 of 646 papers in the database share a
    DOI with a paper in another corpus, so a DOI hit names its corpus on
    every run and the caller labels the runs accordingly.

    Returns a TRI-STATE, never raises: `state` is `hit` (runs returned),
    `miss` (reachable, nothing for this paper) or `unavailable` (no URL, no
    driver, or the connection failed -- `detail` says which). A caller that
    collapsed `unavailable` into `miss` would render a network fault as a
    clean paper, which is the error this toolkit exists to catch.
    """
    paper_dir = Path(paper_dir)
    corpus = corpus or _corpus_of(paper_dir)
    ident = _paper_identity({}, paper_dir, corpus)
    doi = ident["doi"]
    owned = conn is None
    try:
        if owned:
            conn = _connect(db_url, connect_timeout=connect_timeout)
    except DbUnavailable as exc:
        return {"state": "unavailable", "detail": str(exc), "runs": []}
    except Exception as exc:  # noqa: BLE001 -- best-effort by contract
        return {"state": "unavailable",
                "detail": f"{type(exc).__name__}: {exc}", "runs": []}
    try:
        cur = conn.cursor()
        cur.execute(
            "select c.name, p.dir, r.id, r.run_uid, r.name, r.kind, r.status, "
            "r.verdict, r.paper_severity, r.pipeline_version, r.analysed_at, "
            "r.analysed_at_source, r.cost_usd, r.meta "
            "from runs r join papers p on p.id = r.paper_id "
            "join corpora c on c.id = p.corpus_id "
            "where ((c.name = %s and p.dir = %s) "
            "or (%s::text is not null and lower(p.doi) = %s)) "
            "and r.kind in ('full_review','legacy') and (r.component is null or r.component='comprehensive') "
            "order by r.analysed_at desc nulls last, r.id desc",
            (corpus, ident["dir"], doi, doi))
        rows = list(cur.fetchall() or [])
        exact = [r for r in rows if r[0] == corpus and r[1] == ident["dir"]]
        if exact:
            rows = exact
        if not rows:
            return {"state": "miss", "runs": [],
                    "detail": f"no run for corpus {corpus!r} dir "
                              f"{paper_dir.name!r}"
                              + (f" or doi {doi!r}" if doi else
                                 " (no DOI in metadata.json to match on)")}
        by_pk: dict[int, list] = {r[2]: [] for r in rows}
        cur.execute(
            "select run_id, record from findings where run_id = any(%s) "
            "order by run_id, id", (list(by_pk),))
        for run_pk, record in cur.fetchall() or []:
            rec = _jsonb(record)
            if isinstance(rec, dict) and run_pk in by_pk:
                by_pk[run_pk].append(rec)
        runs = []
        for (cname, pdir, run_pk, run_uid, name, kind, status, verdict,
             sev, version, analysed_at, at_source, cost, meta) in rows:
            runs.append({
                "corpus": cname, "dir": pdir, "name": name,
                "run_uid": run_uid, "kind": kind, "status": status,
                "matched_by": "dir" if (cname == corpus
                                        and pdir == ident["dir"]) else "doi",
                "analysed_at": (analysed_at.isoformat()
                                if hasattr(analysed_at, "isoformat")
                                else analysed_at),
                "analysed_at_source": at_source,
                "pipeline_version": version, "cost_usd": cost,
                "doc": {
                    "schema_version": "2.0", "run_id": run_uid,
                    "findings": by_pk[run_pk],
                    "adjudication": {"ran": status == "complete",
                                     "verdict": verdict,
                                     "paper_severity": sev},
                    "legacy": {"pipeline_version": version,
                               "analysed_at": (analysed_at.isoformat()
                                               if hasattr(analysed_at,
                                                          "isoformat")
                                               else analysed_at)},
                    "run_meta": _jsonb(meta) or {},
                },
            })
        return {"state": "hit", "detail": f"{len(runs)} run(s)", "runs": runs}
    except Exception as exc:  # noqa: BLE001 -- best-effort by contract
        return {"state": "unavailable",
                "detail": f"{type(exc).__name__}: {exc}", "runs": []}
    finally:
        # No try/except here: a close that fails should be SEEN (the
        # inertness ratchet counts a silent one), and psycopg's close is
        # already safe on a broken or already-closed connection.
        if owned and conn is not None:
            conn.close()


def retry_pending(root: Path, *, db_url: str | None = None) -> dict:
    path = _pending_path(Path(root))
    if not path.exists():
        return {"retried": 0, "remaining": 0}
    entries = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    conn = _connect(db_url)
    ok, still = 0, []
    try:
        for rec in entries:
            try:
                push_paper(Path(rec["paper"]), conn=conn)
                ok += 1
            except Exception as exc:  # noqa: BLE001
                still.append({**rec, "reason": f"{type(exc).__name__}: {exc}"})
    finally:
        conn.close()
    if still:
        path.write_text("\n".join(json.dumps(r) for r in still) + "\n")
    else:
        path.unlink()
    return {"retried": ok, "remaining": len(still)}
