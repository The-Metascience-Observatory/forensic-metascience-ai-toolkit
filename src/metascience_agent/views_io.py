"""Who has OPENED a paper's results page, written beside the paper.

`views.json` is a sibling of `review.json` and deliberately not part of it. A
view is not a decision:

  - `review_io._paper_fields` whitelists the keys it will store and drops the
    rest, so a `views` block there is silently discarded until the whitelist is
    widened;
  - `webapp_index.review_state` answers `reviewed: True` because the FILE
    EXISTS, so a view written into `review.json` would report every paper
    somebody merely opened as a paper somebody had judged;
  - `/api/review` stamps `reviewed_by`/`reviewed_at` onto any patch carrying
    `paper`, which would file a passer-by as the reviewer.

Same sync unit as `review.json` otherwise: the corpora live on Dropbox, two
people run the workbench locally, so the record is per-paper and merged on
read rather than overwritten. `atomicio.atomic_write_text` publishes it, so a
crash cannot leave a half-file that the scanner reads back as "never opened".

WHAT A MISSING RECORD MEANS. Not "nobody has read this paper". Nothing was
tracking before this module existed, and a `viewer.html` bundle opened from
`file://`, a PDF opened in Preview, or a colleague reading over a shoulder
cannot report back by construction. The absence of a record is the absence of
a record; `webapp_index.viewed_state` is where that distinction is rendered.

THE LOST UPDATE IS REAL AND BOUNDED. Two viewers on two machines can each read
this file and publish their own edit, and one of the two viewer rows is lost --
`atomicio`'s docstring says an atomic publish does not serialise a
read-modify-write. What survives either way is the fact the column shows: both
writers set the same `viewed: yes`. The per-viewer roll-up is best-effort and
says so.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"

VIEWS_NAME = "views.json"

#: A name longer than this is not a name. The reviewer chip is free text and
#: the value arrives over HTTP, so it is bounded before it is stored.
MAX_NAME_LEN = 120


def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_name(viewer) -> str | None:
    """The viewer's name, or None for an anonymous one.

    None rather than the string "anonymous": the reviewer chip is a free-text
    box, so "anonymous" is a name a person could actually type, and a sentinel
    that collides with real data is not a sentinel.
    """
    if not isinstance(viewer, str):
        return None
    name = "".join(c for c in viewer if c.isprintable()).strip()
    return name[:MAX_NAME_LEN] or None


def empty_views() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "n_views": 0,
        "first_at": None,
        "last_at": None,
        "viewers": [],
    }


def _normalise(obj: dict) -> dict:
    """Whatever is on disk, in the shape every caller expects.

    Unknown top-level keys survive -- a future field written by a newer
    workbench must not be deleted by an older one round-tripping the file.
    """
    out = dict(obj)
    viewers = []
    for rec in out.get("viewers") or []:
        if not isinstance(rec, dict):
            continue
        viewers.append({
            "name": _clean_name(rec.get("name")),
            "first_at": rec.get("first_at") or rec.get("at"),
            "last_at": rec.get("last_at") or rec.get("at"),
            "n": int(rec["n"]) if isinstance(rec.get("n"), int) else 1,
        })
    out["viewers"] = viewers
    n = out.get("n_views")
    out["n_views"] = n if isinstance(n, int) and n >= 0 else sum(
        v["n"] for v in viewers)
    out["first_at"] = out.get("first_at") or (
        min((v["first_at"] for v in viewers if v["first_at"]), default=None))
    out["last_at"] = out.get("last_at") or (
        max((v["last_at"] for v in viewers if v["last_at"]), default=None))
    out["schema_version"] = SCHEMA_VERSION
    return out


def load_views(paper_dir) -> dict:
    """The file on disk, or an empty document. Never raises on absence.

    An UNREADABLE file is not an unviewed paper, so it comes back flagged
    rather than empty -- the same distinction `review_io.load_review` draws.
    A caller that overwrites it would destroy whatever the truncated file
    still held.
    """
    path = Path(paper_dir) / VIEWS_NAME
    if not path.is_file():
        return empty_views()
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        out = empty_views()
        out["unreadable"] = True
        return out
    if not isinstance(obj, dict):
        out = empty_views()
        out["unreadable"] = True
        return out
    return _normalise(obj)


def merge_view(current: dict, *, viewer=None, at: str | None = None) -> dict:
    """Add one view to the document. Pure -- no disk, no clock of its own."""
    base = _normalise(current if isinstance(current, dict) else {})
    when = at or _now()
    name = _clean_name(viewer)

    viewers = [dict(v) for v in base.get("viewers") or []]
    for rec in viewers:
        if rec.get("name") == name:
            if rec.get("last_at") == when:
                # The SAME open, recorded twice -- a defeated latch in the
                # browser, a retried POST. One person opening one paper once
                # must not become two views.
                return base
            rec["n"] = int(rec.get("n") or 0) + 1
            rec["last_at"] = when
            rec["first_at"] = rec.get("first_at") or when
            break
    else:
        viewers.append({"name": name, "first_at": when, "last_at": when,
                        "n": 1})

    merged = dict(base)
    merged["viewers"] = viewers
    merged["n_views"] = int(base.get("n_views") or 0) + 1
    # `first_at` is written once and never moved: it is when this paper was
    # FIRST opened, which is the fact a reader wants when the last view was
    # five minutes ago.
    merged["first_at"] = base.get("first_at") or when
    merged["last_at"] = when
    merged["schema_version"] = SCHEMA_VERSION
    return merged


def record_view(paper_dir, *, viewer=None, at: str | None = None) -> dict:
    """Load, merge, atomic write. Returns the merged document.

    Unlike review decisions this does not rewrite the global index on each
    visit. The project table is an explicit snapshot; Refresh counts includes
    new visits. A separate lock protects concurrent view increments.
    """
    paper_dir = Path(paper_dir)
    if not paper_dir.is_dir():
        # Never conjure the directory. `webapp_index.looks_like_paper` calls
        # any non-empty directory a paper, so a stray click against a bad slug
        # would invent one -- a paper in the corpus that nobody ever fetched
        # and no publisher ever published.
        out = empty_views()
        out["recorded"] = False
        out["reason"] = "no such paper directory"
        return out
    from .atomicio import file_lock
    with file_lock(paper_dir / ".views.lock"):
        current = load_views(paper_dir)
        if current.get("unreadable"):
            # Refuse to overwrite a file we could not read. The view is lost; the
            # record is not.
            return current
        merged = merge_view(current, viewer=viewer, at=at)
        from .atomicio import atomic_write_text
        atomic_write_text(paper_dir / VIEWS_NAME,
                          json.dumps(merged, indent=2) + "\n")
        return merged


def main(argv=None) -> int:
    """`python -m metascience_agent.views_io <paper_dir> [--viewer NAME]`.

    A SECOND ENTRY POINT, and the reason is measured: the workbench records a
    view on every page open through an asynchronous module bridge. Importing `cli.py` (Typer, rich,
    the whole tool registry) costs 407 ms on this machine; importing this
    module costs 22 ms. The `metascience view-record` command still exists for
    humans and for a reproducible one-liner -- it is the hot path that must
    not pay for the CLI.
    """
    import argparse

    ap = argparse.ArgumentParser(prog="metascience_agent.views_io")
    ap.add_argument("paper_dir")
    ap.add_argument("--viewer", default=None)
    ap.add_argument("--at", default=None)
    args = ap.parse_args(argv)
    print(json.dumps(record_view(args.paper_dir, viewer=args.viewer,
                                 at=args.at), default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover -- exercised as a subprocess
    raise SystemExit(main())
