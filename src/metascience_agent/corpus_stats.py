"""Per-corpus fire-rate statistics from findings-v2 documents.

Contract: docs/specs/webapp_db.md section 14. Denominator discipline is
CONTRACTUAL (LESSONS #2): every rate names its denominator; "ran" for
denominator purposes means channel state in {ran, ran_result_discarded} --
a channel that demonstrably ran and retained nothing STILL RAN (the
370-of-370-minus-one image corpus would otherwise lose ~369 papers from its
denominator); refused/did_not_run/unknown are counted and printed
separately, never folded into "did not fire"; adjudicator-discarded rows
are n_discarded_by_adjudicator, never fires; fast_screen rows are a FUNNEL
and are excluded from accusation-grade fires. Everything except the
optional tool_calls section is SQL-derivable from the Phase-5N tables --
the proof queries in the spec are the reference implementations this file
must agree with.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

#: Channel states that count as "the check ran" for denominators.
RAN_STATES = ("ran", "ran_result_discarded")

#: Which channel a technique's findings ride in (for n_papers_ran).
_TECHNIQUE_CHANNEL = {
    "analyze_paper_images": "image_forensics",
    "detect_tortured_phrases": "tortured_phrases",
}


def _v2_docs(paper_dir: Path):
    seen = set()
    # NO RUN-HORIZON FILTER HERE, DELIBERATELY. This function computes
    # statistics over whatever it is handed, including a deliberate historical
    # archive, and it has no channel to report an exclusion -- so filtering
    # inside it would be exactly the silent drop `runs.partition` exists to
    # prevent. The horizon belongs where a question is INTERPRETED (the `runs`
    # verb, `register_view`, and the rule in CLAUDE.md), not where arithmetic
    # is done. See tests/test_run_horizon.py.
    for path in sorted(paper_dir.glob("forensic_review*/findings.v2.json")) \
            + sorted(paper_dir.glob("findings.v2.json")):
        try:
            doc = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            continue
        rid = doc.get("run_id") or str(path)
        if rid in seen:
            continue
        seen.add(rid)
        yield path, doc


def _current_doc(paper_dir: Path) -> dict | None:
    """The paper's CURRENT v2 document: newest by analysed_at (nulls last),
    mirroring the current_runs view's ordering rule.

    The date comes from the doc's own fields OR the sibling run_meta.json:
    a fresh parallel doc carries no analysed_at at all, so on the doc
    fields alone it sorted as "" -- LAST -- and a paper's brand-new run
    lost to its own migrated legacy doc (caught live by the first
    --verify run, 2026-08-21: file mode and the DB picked different runs
    for the same paper)."""
    from .webapp_index import run_kind
    # An image-only sweep run (kind `image_track`) is never the paper's
    # current REVIEW while a full review exists, however new it is; it only
    # stands in when there is nothing else.
    best: dict[str, tuple[str, dict]] = {}
    for path, doc in _v2_docs(paper_dir):
        when = (doc.get("legacy") or {}).get("analysed_at") \
            or doc.get("analysed_at") or ""
        if not when:
            rm = path.parent / "run_meta.json"
            try:
                when = str(json.loads(rm.read_text()).get("analysed_at")
                           or "")
            except Exception:  # noqa: BLE001
                when = ""
        kind = run_kind(doc)
        if kind == "partial_review":
            # A partial pipeline (one tool, no adjudicator, ...) is an
            # experiment, never the paper's review: corpus statistics drawn
            # from it would mix a one-tool fire rate into the review's.
            continue
        tier = "image" if kind == "image_track" else "review"
        cur = best.get(tier)
        if cur is None or when > cur[0]:     # empty string sorts last, as
            best[tier] = (when, doc)         # the current_runs view orders
    pick = best.get("review") or best.get("image")
    return pick[1] if pick else None


def _metadata(paper_dir: Path, doc: dict) -> dict:
    pm = doc.get("paper_metadata") or {}
    if pm.get("journal_normalized") or pm.get("year"):
        return pm
    meta_path = paper_dir / "metadata.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text())
        except Exception:  # noqa: BLE001
            pass
    return pm


def compute(root: Path) -> dict:
    """File mode: scan the corpus directory tree."""
    from .webapp_index import iter_paper_dirs
    root = Path(root)
    # The CANONICAL enumeration (webapp_index owns it): `done/<slug>` and
    # batch folders hold papers too. The flat top-level scan this used
    # silently dropped every archived paper -- the first live --verify run
    # (2026-08-21, cerebrolysin) caught file and DB disagreeing because
    # BOTH had inherited the same hole from different code paths.
    papers = iter_paper_dirs(root)

    def entries():
        for paper_dir in papers:
            doc = _current_doc(paper_dir)
            if doc is None:
                yield paper_dir.name, None, {}
            else:
                yield paper_dir.name, doc, _metadata(paper_dir, doc)

    return _aggregate(entries(), corpus=root.name)


def compute_from_db(corpus: str, *, db_url: str | None = None,
                    conn=None) -> dict:
    """DB mode: the SAME aggregation over rows fetched from the findings database.

    Deliberately NOT a second implementation of the denominator rules in
    SQL -- that would be the two-implementations drift this module's
    contract warns about. The SQL selects each paper's CURRENT run (newest
    analysed_at, nulls last -- the current_runs ordering, and the same rule
    `_current_doc` applies to files) and reconstructs the same
    (name, doc, meta) triples `compute` yields; every counting rule then
    runs once, in `_aggregate`. One honest difference: `n_papers` here is
    papers KNOWN TO THE DATABASE for this corpus -- a paper directory that
    never produced a findings doc was never pushed, so file mode's
    n_papers can exceed it; every other key is asserted equal by
    `--from-db --verify` and tests/test_corpus_stats.py.
    """
    from . import db_push as _db
    owned = conn is None
    if owned:
        conn = _db._connect(db_url)
    try:
        cur = conn.cursor()
        cur.execute(
            "select p.id, p.dir, p.metadata, r.id as run_pk "
            "from papers p "
            "join corpora c on c.id = p.corpus_id "
            "join lateral ("
            "  select id from runs r2 where r2.paper_id = p.id and r2.kind in ('full_review','legacy') and (r2.component is null or r2.component = 'comprehensive') "
            "  order by (r2.kind in ('full_review','legacy')) desc, r2.analysed_at desc nulls last, r2.id desc limit 1"
            ") r on true "
            "where c.name = %s order by p.dir", (corpus,))
        papers = cur.fetchall()
        run_pks = [row[3] for row in papers]
        channels: dict[int, dict] = {}
        findings: dict[int, list] = {}
        if run_pks:
            cur.execute(
                "select run_id, channel, state from run_channels "
                "where run_id = any(%s)", (run_pks,))
            for run_id, channel, state in cur.fetchall():
                channels.setdefault(run_id, {})[channel] = {"state": state}
            cur.execute(
                "select run_id, record from findings "
                "where run_id = any(%s) order by run_id, id", (run_pks,))
            for run_id, record in cur.fetchall():
                if isinstance(record, str):
                    record = json.loads(record)
                findings.setdefault(run_id, []).append(record)
    finally:
        if owned:
            conn.close()

    def entries():
        for _pid, d, metadata, run_pk in papers:
            if isinstance(metadata, str):
                metadata = json.loads(metadata) if metadata else {}
            doc = {"channels": channels.get(run_pk, {}),
                   "findings": findings.get(run_pk, [])}
            yield d, doc, (metadata or {})

    out = _aggregate(entries(), corpus=corpus)
    out["source"] = "db"
    return out


def _aggregate(entries, *, corpus: str) -> dict:
    """One implementation of every counting rule, whatever fed it.

    `entries` yields (paper_name, doc_or_None, meta) -- doc None means a
    paper with no findings document (counted in n_papers only)."""
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus": corpus,
        "n_papers": 0,
        "n_papers_with_v2": 0,
        "channel_status": {},
        "per_technique": [],
        "by_journal": [],
        "by_year": [],
    }
    chan: dict[str, dict[str, int]] = {}
    ran_papers: dict[str, set] = {}
    tech: dict[tuple[str, str], dict[str, Any]] = {}
    by_journal: dict[str, dict[str, Any]] = {}
    by_year: dict[Any, dict[str, Any]] = {}

    for paper_name, doc, meta in entries:
        out["n_papers"] += 1
        if doc is None:
            continue
        out["n_papers_with_v2"] += 1
        channels = doc.get("channels") or {}
        for name, ch in channels.items():
            state = ch.get("state") if isinstance(ch, dict) else str(ch)
            bucket = chan.setdefault(name, {})
            bucket[state] = bucket.get(state, 0) + 1
            if state in RAN_STATES:
                # The DENOMINATOR: counted from channel state alone, so a
                # paper whose check ran and retained nothing still counts
                # (the LESSONS #2 rule -- this loop, not the findings loop,
                # owns the denominator).
                ran_papers.setdefault(name, set()).add(paper_name)

        journal = meta.get("journal_normalized") or meta.get("journal") \
            or "(no journal recorded)"
        year = meta.get("year") or "(no year)"
        j = by_journal.setdefault(journal, {"journal_normalized": journal,
                                            "n_papers": 0, "fired": set(),
                                            "n_findings_problem": 0,
                                            "n_impossible": 0,
                                            "worst_severity": None})
        y = by_year.setdefault(year, {"year": year, "n_papers": 0,
                                      "fired": set(),
                                      "n_findings_problem": 0,
                                      "n_impossible": 0})
        j["n_papers"] += 1
        y["n_papers"] += 1

        for f in doc.get("findings") or []:
            if not isinstance(f, dict):
                continue
            producer = f.get("producer")
            t = str(f.get("technique"))
            key = (t, str(f.get("computed_by") or "unknown"))
            row = tech.setdefault(key, {
                "technique": t, "computed_by": key[1],
                "papers_ran": set(), "papers_fired": set(),
                "n_findings": {"problem": 0, "pass": 0, "undecided": 0},
                "n_impossible": 0, "by_severity": {},
                "n_discarded_by_adjudicator": 0, "n_screen_flags": 0,
            })
            outcome = f.get("outcome")
            if outcome in row["n_findings"]:
                row["n_findings"][outcome] += 1
            action = (f.get("adjudication") or {}).get("action")
            is_fire = (outcome == "problem" and action != "discarded"
                       and producer != "fast_screen")
            if action == "discarded":
                row["n_discarded_by_adjudicator"] += 1
            if producer == "fast_screen" and outcome == "problem":
                row["n_screen_flags"] += 1
            if f.get("impossible"):
                row["n_impossible"] += 1
                j["n_impossible"] += 1
                y["n_impossible"] += 1
            sev = f.get("severity")
            if is_fire:
                row["papers_fired"].add(paper_name)
                j["fired"].add(paper_name)
                y["fired"].add(paper_name)
                j["n_findings_problem"] += 1
                y["n_findings_problem"] += 1
                if isinstance(sev, int):
                    row["by_severity"][str(sev)] = \
                        row["by_severity"].get(str(sev), 0) + 1
                    if j["worst_severity"] is None or sev > j["worst_severity"]:
                        j["worst_severity"] = sev


    out["channel_status"] = {
        name: {**{s: 0 for s in ("ran", "ran_result_discarded", "refused",
                                 "did_not_run", "unknown")}, **states}
        for name, states in sorted(chan.items())
    }
    for (t, cb), row in sorted(tech.items()):
        row.pop("papers_ran", None)
        n_ran = len(ran_papers.get(_TECHNIQUE_CHANNEL.get(t, "tool_expert"),
                                   set()))
        n_fired = len(row.pop("papers_fired"))
        out["per_technique"].append({
            **row,
            "n_papers_ran": n_ran,
            "n_papers_fired": n_fired,
            "fire_rate": round(n_fired / n_ran, 4) if n_ran else None,
        })
    for j in by_journal.values():
        j["n_papers_fired"] = len(j.pop("fired"))
        out["by_journal"].append(j)
    for y in by_year.values():
        y["n_papers_fired"] = len(y.pop("fired"))
        out["by_year"].append(y)
    out["by_journal"].sort(key=lambda r: -r["n_papers"])
    out["by_year"].sort(key=lambda r: str(r["year"]))
    return out


def diff_stats(file_stats: dict, db_stats: dict) -> list[str]:
    """Every disagreement between the two modes, excluding the documented
    ones (generated_at; n_papers -- papers that never produced a doc were
    never pushed; the db `source` marker)."""
    diffs: list[str] = []
    skip = {"generated_at", "n_papers", "source"}

    def norm(v):
        if isinstance(v, list):
            # order-insensitive on the list sections: file mode orders by
            # directory scan, db mode by SQL sort
            return sorted((json.dumps(x, sort_keys=True, default=str)
                           for x in v))
        return v

    for key in sorted(set(file_stats) | set(db_stats) - skip):
        if key in skip:
            continue
        a, b = norm(file_stats.get(key)), norm(db_stats.get(key))
        if a != b:
            if isinstance(a, list) and isinstance(b, list):
                only_a = [x for x in a if x not in b]
                only_b = [x for x in b if x not in a]
                for x in only_a[:5]:
                    diffs.append(f"{key}: file-only {x[:160]}")
                for x in only_b[:5]:
                    diffs.append(f"{key}: db-only   {x[:160]}")
            else:
                diffs.append(f"{key}: file={str(a)[:120]} db={str(b)[:120]}")
    return diffs
