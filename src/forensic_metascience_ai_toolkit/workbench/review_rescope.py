"""Recover human review decisions stranded in the legacy `(unscoped)` bucket.

WHY THIS EXISTS. A decision made in the webapp is written to the paper's
`review.json` under the run it was about. When the webapp could not name that
run it wrote the decision to the `(unscoped)` bucket instead, and
`db_push.push_reviews` reports those as `unmatched` and imports nothing --
correctly, because inventing a target is worse than losing one.

Three things then made runs unnameable at once on 2026-09-10: the discovery
corpora moved out of Dropbox (so `roots` still pointed at vanished paths), the
image retirement retired 5,563 runs and 28,827 candidates, and two runs failed
import with `U+0000, which PostgreSQL JSONB cannot preserve`. MEASURED
afterwards: 19 review rows in the database against 55 distinct decisions
recoverable from disk.

WHAT MAKES A REBINDING SAFE. `IMGDUP-N` is POSITIONAL -- it is an index into
one run's findings list (`image_track._findings_rows`). Rebinding a decision to
a different run can therefore attach "false positive" to a different finding,
which is worse than losing the decision. So this module never picks a run by
recency, liveness or count. It matches on the issue key itself:
`component_items.item_uid` ends with the same `IMGDUP-N`, and the rebinding is
performed ONLY when exactly one live item in that paper owns that key. Anything
else is reported and left alone:

  `unowned`    -- no live item owns the key: the run was retired and nothing
                  replaced it. The decision is not recoverable, and saying so
                  is the honest outcome. Not an error.
  `ambiguous`  -- several live items own the key, so the key does not identify
                  a finding any more. Needs a human.

Idempotent: `push_reviews` already declines to insert a verdict identical to
the latest stored row for its (run, issue, reviewer), so re-running adds
nothing. Dry run is the default; `--apply` writes.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UNOWNED = "unowned"
AMBIGUOUS = "ambiguous"
RESCOPED = "rescoped"
ALREADY = "already_scoped"


def _live_owners(cur, corpus: str, paper_dir: str, issue_key: str) -> list[dict]:
    """Live component items in this paper whose uid ends with the issue key.

    Retired runs are excluded in SQL and retired item records are excluded in
    Python -- a record carrying `retired` is a tombstone, not a candidate.
    """
    short = issue_key.split(":")[-1]
    cur.execute(
        "select ci.run_id, r.run_uid, ci.item_uid, ci.record "
        "from component_items ci join runs r on r.id = ci.run_id "
        "join papers p on p.id = ci.owner_paper_id "
        "join corpora co on co.id = p.corpus_id "
        "where co.name = %s and p.dir = %s and ci.item_uid like %s "
        "and r.retired_at is null",
        (corpus, paper_dir, f"%:{short}"))
    out = []
    for run_id, run_uid, item_uid, record in cur.fetchall():
        rec = record if isinstance(record, dict) else {}
        if rec.get("retired"):
            continue
        out.append({"run_id": run_id, "run_uid": run_uid, "item_uid": item_uid,
                    "detector_kind": rec.get("detector_kind") or rec.get("kind")})
    return out


def plan(root: Path, corpus: str, conn) -> dict[str, Any]:
    """What a rescope would do, decided but not written."""
    from forensic_metascience_ai_toolkit.review_io import (
        UNSCOPED_RUN, load_review)
    cur = conn.cursor()
    actions: list[dict] = []
    for review in sorted(Path(root).glob("*/review.json")):
        paper_dir = review.parent.name
        try:
            data = load_review(review.parent)
        except (OSError, ValueError) as exc:
            actions.append({"paper": paper_dir, "outcome": "unreadable",
                            "detail": f"{type(exc).__name__}: {exc}"})
            continue
        for run_name, block in (data.get("runs") or {}).items():
            issues = (block.get("issues") or {}) if isinstance(block, dict) else {}
            for key, entry in issues.items():
                if not isinstance(entry, dict) or not entry.get("decision"):
                    continue
                base = {"paper": paper_dir, "issue_key": key,
                        "decision": entry.get("decision"),
                        "reviewer": entry.get("reviewer"), "at": entry.get("at")}
                if run_name != UNSCOPED_RUN:
                    actions.append({**base, "outcome": ALREADY, "run": run_name})
                    continue
                owners = _live_owners(cur, corpus, paper_dir, key)
                if len(owners) == 1:
                    actions.append({**base, "outcome": RESCOPED, **owners[0]})
                elif not owners:
                    actions.append({**base, "outcome": UNOWNED})
                else:
                    actions.append({**base, "outcome": AMBIGUOUS,
                                    "candidates": [o["run_uid"] for o in owners]})
    counts: dict[str, int] = {}
    for a in actions:
        counts[a["outcome"]] = counts.get(a["outcome"], 0) + 1
    return {"corpus": corpus, "root": str(root), "actions": actions,
            "counts": counts,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def apply(pl: dict, conn) -> dict[str, Any]:
    """Write the `rescoped` actions. Unowned and ambiguous are left alone."""
    from forensic_metascience_ai_toolkit.db_push import _user_for
    cur = conn.cursor()
    written = skipped = 0
    errors: list[str] = []
    for a in pl["actions"]:
        if a.get("outcome") != RESCOPED:
            continue
        try:
            cur.execute(
                "select p.id from papers p join corpora c on c.id = p.corpus_id "
                "where c.name = %s and p.dir = %s", (pl["corpus"], a["paper"]))
            row = cur.fetchone()
            if not row:
                errors.append(f"{a['paper']}: no such paper in {pl['corpus']}")
                continue
            paper_pk = row[0]
            uid = _user_for(cur, str(a.get("reviewer") or "").strip() or "(unrecorded)")
            # Change detection, exactly as push_reviews does it: an identical
            # verdict for this (run, issue, reviewer) inserts nothing, so a
            # repeated run manufactures no history.
            cur.execute(
                "select decision from reviews where run_id=%s and issue_key=%s "
                "and reviewer_id=%s order by decided_at desc, id desc limit 1",
                (a["run_id"], a["issue_key"], uid))
            last = cur.fetchone()
            if last is not None and last[0] == a["decision"]:
                skipped += 1
                continue
            cur.execute(
                "select id from findings where run_id=%s and "
                "(finding_id=%s or legacy_original_id=%s)",
                (a["run_id"], a["issue_key"], a["issue_key"]))
            f = cur.fetchone()
            cur.execute(
                "insert into reviews (run_id, paper_id, finding_pk, issue_key, "
                "reviewer_id, decision, extra, decided_at) "
                "values (%s,%s,%s,%s,%s,%s,%s,coalesce(%s::timestamptz, now()))",
                (a["run_id"], paper_pk, f[0] if f else None, a["issue_key"], uid,
                 a["decision"],
                 # PROVENANCE, so a later reader can tell a recovered decision
                 # from one made against a run the reviewer actually saw.
                 json.dumps({"rescoped_from": "(unscoped)",
                             "rescoped_by": "workbench.review_rescope",
                             "matched_item_uid": a["item_uid"]}),
                 a.get("at")))
            written += 1
        except Exception as exc:  # noqa: BLE001 -- one bad row must not sink the rest
            errors.append(f"{a['paper']} {a['issue_key']}: {type(exc).__name__}: {exc}")
    return {"written": written, "unchanged": skipped, "errors": errors}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path, help="corpus root holding the paper dirs")
    ap.add_argument("--corpus", required=True, help="corpus name in the database")
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    ap.add_argument("--out", type=Path, help="write the plan/result JSON here")
    args = ap.parse_args()

    from forensic_metascience_ai_toolkit.db_push import _connect
    with _connect(None) as conn:
        pl = plan(args.root, args.corpus, conn)
        if args.apply:
            with conn.transaction():
                pl["result"] = apply(pl, conn)
    print(json.dumps(pl["counts"], indent=1))
    if pl.get("result"):
        print(json.dumps(pl["result"], indent=1))
    if args.out:
        args.out.write_text(json.dumps(pl, indent=1, default=str))
        print(f"plan written to {args.out}")


if __name__ == "__main__":
    main()
