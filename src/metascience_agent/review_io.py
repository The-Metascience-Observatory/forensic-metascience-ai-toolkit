"""Human review labels, written beside the paper.

`review.json` is the sync unit: two people run the workbench locally and the
papers directory lives on Dropbox. Merge by issue id, never overwrite the
file wholesale. Write via temp + rename so a crash cannot look like
"unreviewed" -- a half-JSON that the scanner then reads as silence is the
same substitution this toolkit exists to catch.

Schema 1.1 is the contract the workbench writes. Schema 1.0
(publication/reporting gates + `findings`) is still readable. New writes
keep any 1.0 keys they find; they do not delete them. Numeric `correct`
was split into `correct_minor` and `correct_significant`; a stored
`correct` is still a valid decision, not rewritten.

A PubPeer comment is usually one post for the paper, not one checkbox
per finding. `paper.submitted_to_pubpeer` / `paper.pubpeer_url` /
`paper.pubpeer_note` are the paper-level record. Per-issue
`submitted_to_pubpeer` still exists for a finding that was posted on
its own. Absence of the paper-level flag is not "not submitted" — it
is that nobody recorded a submission.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0"

#: Legacy (1.x) verdicts land here: we cannot reliably recover WHICH run the
#: workbench displayed when they were made, and guessing would file a human
#: decision under a run the human never saw. Unscoped verdicts render on
#: whatever run is displayed, marked as unscoped.
UNSCOPED_RUN = "(unscoped)"


def image_issue_decisions(paper_dir: Path) -> dict[str, str]:
    """`IMGDUP-N` -> decision, from a 1.0 or 1.1 `review.json`.

    Empty dict if the paper has not been labelled. Keys are the group id
    without the `image:` prefix so a scorer can join them to a sweep row.
    """
    obj = load_review(paper_dir)
    out: dict[str, str] = {}
    for key, rec in (obj.get("issues") or {}).items():
        if not isinstance(rec, dict) or not rec.get("decision"):
            continue
        kid = str(key)
        if kid.startswith("image:"):
            kid = kid.split(":", 1)[1]
        if kid.upper().startswith("IMGDUP"):
            out[kid] = str(rec["decision"])
    return out

PAPER_STATUSES = ("unreviewed", "in_progress", "complete")

NUMERIC_DECISIONS = (
    "correct_minor",
    "correct_significant",
    "false_positive",
)
# Pre-split `correct` stays readable. The workbench no longer offers it.
LEGACY_DECISIONS = ("correct",)
# Reason-specific false positives (2026-09-14): one extra click that turns
# "355 labelled pairs still fire" into a count per CLASS, so each detector
# rule's remaining miss is measured directly instead of by a hand audit. Every
# `false_positive*` decision is a rejection to every reader; the reason is for
# the benchmark's split, never for publication.
IMAGE_DECISIONS = (
    "false_positive",
    "false_positive_other",
    "false_positive_same_condition",
    "false_positive_chart",          # a plot template, legend, axis or label
    "false_positive_overlay",        # a channel beside / inside its own merge
    "false_positive_supplement",     # a figure re-shown in its own supplement
    "false_positive_magnification",  # an overview and its own detail
    "false_positive_scale_bar",      # matching scale bars rather than image content
    "false_positive_channels",       # different channels of the same field (Dan, 2026-09-26)
    "false_positive_logo",           # a logo / journal mark, not a result (Dan, 2026-09-26)
    "true_issue",
    "unsure",
)
TEXT_DECISIONS = NUMERIC_DECISIONS
ALL_DECISIONS = frozenset(NUMERIC_DECISIONS + IMAGE_DECISIONS + LEGACY_DECISIONS)

# Per-issue fields the API shortcut may set. A PubPeer comment is often
# one post covering several findings, so the same keys also live on
# `paper` — see `_paper_fields`. Extra keys already on an issue survive.
ISSUE_PATCH_KEYS = (
    "decision", "submitted_to_pubpeer", "submitted_to_editor",
    "pubpeer_url", "note", "reviewer", "at",
)


def empty_review() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "paper": {
            "status": "unreviewed",
            "reviewed_by": None,
            "reviewed_at": None,
        },
        "runs": {},
        "issues": {},
    }


def _issues_view(runs: dict) -> dict:
    """The flattened compatibility view every 1.x consumer reads: the union
    of all runs' issues, unscoped first so a RUN-SCOPED verdict on the same
    key wins. Regenerated on every load/merge -- a VIEW, never the record."""
    out: dict[str, Any] = {}
    for run_name in sorted(runs, key=lambda r: (r != UNSCOPED_RUN, r)):
        bucket = runs.get(run_name) or {}
        for key, rec in (bucket.get("issues") or {}).items():
            if isinstance(rec, dict):
                out[str(key)] = rec
    return out


def pubpeer_url(value) -> str | None:
    """Only a PubPeer https URL is stored. Anything else is absence.

    The workbench renders this as an href. An unchecked string is not
    "we have no link" — it is not a PubPeer URL, so it is not recorded.
    """
    if not isinstance(value, str):
        return None
    url = value.strip()
    if url.startswith("https://pubpeer.com/"):
        return url
    return None


def _paper_fields(paper: dict, status: str) -> dict:
    """The 1.1 paper object. Unknown keys are dropped on purpose so a
    typo cannot become a second source of truth beside the named fields.
    """
    out = {
        "status": status,
        "reviewed_by": paper.get("reviewed_by") or paper.get("reviewer"),
        "reviewed_at": paper.get("reviewed_at") or paper.get("at"),
    }
    if "submitted_to_pubpeer" in paper:
        out["submitted_to_pubpeer"] = bool(paper.get("submitted_to_pubpeer"))
    if "pubpeer_url" in paper:
        out["pubpeer_url"] = pubpeer_url(paper.get("pubpeer_url"))
    if "pubpeer_note" in paper:
        note = paper.get("pubpeer_note")
        out["pubpeer_note"] = note.strip() if isinstance(note, str) and note.strip() else None
    return out


def load_review(paper_dir: Path) -> dict:
    """The file on disk, or an empty 1.1 document. Never raises on absence."""
    path = Path(paper_dir) / "review.json"
    if not path.is_file():
        return empty_review()
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Unreadable is not unreviewed. Callers that care check `unreadable`.
        out = empty_review()
        out["unreadable"] = True
        return out
    if not isinstance(obj, dict):
        out = empty_review()
        out["unreadable"] = True
        return out
    return _normalise(obj)


def _normalise(obj: dict) -> dict:
    """Promote 1.0 into 1.1 without dropping the old keys."""
    out = dict(obj)
    paper = out.get("paper") if isinstance(out.get("paper"), dict) else {}
    status = paper.get("status")
    if status not in PAPER_STATUSES:
        if out.get("issues") or out.get("findings"):
            status = "in_progress"
        else:
            status = "unreviewed"
    out["paper"] = _paper_fields(paper, status)
    issues = out.get("issues")
    if not isinstance(issues, dict):
        issues = {}
        # 1.0 stored per-finding decisions under `findings`.
        old = out.get("findings")
        if isinstance(old, dict):
            for key, rec in old.items():
                if not isinstance(rec, dict):
                    continue
                # 1.0 stored every decision under `findings` with no kind.
                # IMGDUP-* is an image group; everything else is numeric.
                # Writing them all as `numeric:` made the workbench show
                # arithmetic buttons on image matches, so 113 Masliah image
                # labels landed as generic `false_positive` rather than the
                # image taxonomy (MEASURED 2026-08-19, 31 review.json files).
                prefix = "image" if str(key).upper().startswith("IMGDUP") \
                    else "numeric"
                rec = dict(rec)
                if prefix == "image" and rec.get("decision") == "false_positive":
                    rec["decision"] = "false_positive_other"
                issues[f"{prefix}:{key}"] = rec
    # 2.0: verdicts live under runs[<run>]["issues"]; a 1.x flat `issues`
    # dict becomes the UNSCOPED bucket (see UNSCOPED_RUN). The flat key
    # stays as a regenerated compatibility VIEW for 1.x consumers.
    runs = out.get("runs") if isinstance(out.get("runs"), dict) else {}
    runs = {str(k): (v if isinstance(v, dict) else {}) for k, v in runs.items()}
    if issues and not runs.get(UNSCOPED_RUN, {}).get("issues"):
        already = set()
        for bucket in runs.values():
            already.update((bucket.get("issues") or {}).keys())
        orphan = {k: v for k, v in issues.items() if k not in already}
        if orphan:
            runs.setdefault(UNSCOPED_RUN, {}).setdefault(
                "issues", {}).update(orphan)
    out["runs"] = runs
    out["issues"] = _issues_view(runs)
    out["schema_version"] = SCHEMA_VERSION
    return out


def merge_review(current: dict, patch: dict) -> dict:
    """Merge a patch into the current document.

    `issues` are merged by id. A patch that names `paper` replaces those
    fields only. Unknown top-level keys in `current` survive.
    """
    base = _normalise(current if isinstance(current, dict) else {})
    patch = patch if isinstance(patch, dict) else {}
    merged = dict(base)

    if isinstance(patch.get("paper"), dict):
        paper = dict(merged.get("paper") or {})
        incoming = patch["paper"]
        if incoming.get("status") in PAPER_STATUSES:
            paper["status"] = incoming["status"]
        if "reviewed_by" in incoming:
            paper["reviewed_by"] = incoming.get("reviewed_by")
        if "reviewed_at" in incoming:
            paper["reviewed_at"] = incoming.get("reviewed_at")
        if "submitted_to_pubpeer" in incoming:
            paper["submitted_to_pubpeer"] = bool(incoming.get("submitted_to_pubpeer"))
        if "pubpeer_url" in incoming:
            paper["pubpeer_url"] = pubpeer_url(incoming.get("pubpeer_url"))
        if "pubpeer_note" in incoming:
            note = incoming.get("pubpeer_note")
            paper["pubpeer_note"] = (
                note.strip() if isinstance(note, str) and note.strip() else None
            )
        merged["paper"] = _paper_fields(paper, paper.get("status") or "unreviewed")

    target_run = str(patch.get("run") or UNSCOPED_RUN)

    def _run_bucket() -> dict:
        runs = merged.setdefault("runs", {})
        return runs.setdefault(target_run, {}).setdefault("issues", {})

    if patch.get("run_status") in PAPER_STATUSES:
        merged.setdefault("runs", {}).setdefault(target_run, {})["status"] = \
            patch["run_status"]

    if isinstance(patch.get("issues"), dict):
        issues = _run_bucket()
        for key, rec in patch["issues"].items():
            if not isinstance(rec, dict):
                continue
            prev = issues.get(str(key)) if isinstance(issues.get(str(key)), dict) else {}
            next_rec = dict(prev)
            next_rec.update(rec)
            if "pubpeer_url" in next_rec:
                next_rec["pubpeer_url"] = pubpeer_url(next_rec.get("pubpeer_url"))
            if next_rec.get("decision") is not None \
                    and next_rec.get("decision") not in ALL_DECISIONS:
                next_rec["decision"] = prev.get("decision")
            issues[str(key)] = next_rec

    # A single-issue shortcut used by the API: {issue_id, ...fields}
    if patch.get("issue_id"):
        iid = str(patch["issue_id"])
        rec = {k: patch[k] for k in ISSUE_PATCH_KEYS if k in patch}
        if "pubpeer_url" in rec:
            rec["pubpeer_url"] = pubpeer_url(rec.get("pubpeer_url"))
        issues = _run_bucket()
        prev = issues.get(iid) if isinstance(issues.get(iid), dict) else {}
        next_rec = dict(prev)
        next_rec.update(rec)
        if next_rec.get("decision") is not None \
                and next_rec.get("decision") not in ALL_DECISIONS:
            next_rec["decision"] = prev.get("decision")
        issues[iid] = next_rec
        if merged["paper"]["status"] == "unreviewed":
            merged["paper"]["status"] = "in_progress"

    merged["issues"] = _issues_view(merged.get("runs") or {})
    merged["schema_version"] = SCHEMA_VERSION
    return merged


def write_review(paper_dir: Path, patch: dict) -> dict:
    """Load, merge, atomic write. Returns the merged document."""
    paper_dir = Path(paper_dir)
    path = paper_dir / "review.json"
    from .atomicio import file_lock
    with file_lock(paper_dir / ".review.lock"):
        current = {}
        if path.is_file():
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ValueError(f"review file is unreadable; refusing to overwrite {path}") from exc
        merged = merge_review(current, patch)
        from .atomicio import atomic_write_text
        atomic_write_text(path, json.dumps(merged, indent=2) + "\n")
    try:
        # `webapp_index`, not `discovery`: the extracted copy named the wrong
        # module, and the bare except below hid it (2026-09-11 to 2026-10-16).
        from .webapp_index import refresh_index_paper
        refresh_index_paper(paper_dir)
    except Exception:  # noqa: BLE001 — a table snapshot must not fail a save
        pass
    return merged
