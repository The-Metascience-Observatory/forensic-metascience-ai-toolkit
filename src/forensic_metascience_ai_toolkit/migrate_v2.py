"""One-way legacy converter: v1 findings -> findings.v2.json, beside the old.

Contract: docs/specs/findings_v2.md sections 1.7 and 12. Three input classes
per paper: per-run `findings.json` (schema 1.x), orphan
`image_duplication_findings.json` (masliah holds 544), and standalone
`text_forensics.json`. Rules that are locked decisions:

- NEVER overwrite a v1 file and NEVER rewrite review.json (the two-person
  Dropbox sync unit); output is `findings.v2.json` beside the source.
- `pipeline_version` defaults to "0.0.1" when the run recorded none;
  `analysed_at` falls back to file mtime WITH `analysed_at_source:
  "file_mtime"` -- a file date presented as a run date is the substitution
  this toolkit exists to catch.
- Unconvertible runs get `findings.v2.skipped.json {reason}` -- a named
  skip, never a silent one -- and the corpus roll-up counts them.
- Reviewer verdicts survive BY REFERENCE: `legacy.original_id` carries the
  PREFIXED review.json key; the post-check reports orphaned decisions.
- Synthesized titles/descriptions are deterministic templates flagged
  `legacy` -- adequate, never fabricated fluency.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import findings_v2 as fv2
from .registry import BY_NAME, EVIDENCE_ABSOLUTE
from .severity9 import FIVE_TO_NINE, OUTCOME_FROM_FIVE
from .severity_reconcile import _TECHNIQUE_TOOLS

FROM_SCHEMA = "findings-1.x"
_PASSTHROUGH = {"not_computational", "no_tool_exists", "tool_existed_unused"}


def _map_technique(old: str | None) -> str:
    t = str(old or "")
    if t in _TECHNIQUE_TOOLS:
        return _TECHNIQUE_TOOLS[t][0]
    if t == "image_duplication":
        return "analyze_paper_images"
    if t == "tortured_phrases":
        return "detect_tortured_phrases"
    if t in _PASSTHROUGH:
        return t
    if t in BY_NAME:
        return t
    return "legacy_unattributed"


def _producer_for(row: dict) -> str:
    rid = str(row.get("id") or "")
    if rid.startswith("IMGDUP"):
        return "image_track"
    if rid.startswith(("TORT", "TP-")):
        return "text_track"
    return "legacy_sweep"


def _review_key(row: dict) -> str:
    rid = str(row.get("id") or "")
    if rid.startswith("IMGDUP"):
        return f"image:{rid}"
    if rid.startswith(("TORT", "TP-")):
        return f"text:{rid}"
    return f"numeric:{rid}"


def _title_from(row: dict) -> str:
    rid = str(row.get("id") or "finding").replace("_", " ").replace("-", " ")
    title = rid[:1].upper() + rid[1:]
    loc = str(row.get("location") or "").strip()
    if loc and len(title) + len(loc) + 4 <= 90:
        title = f"{title} ({loc})"
    title = title[:90]
    return title if len(title) >= 8 else (title + " (legacy)")[:90]


def _description_from(row: dict) -> str:
    for key in ("explanation", "notes"):
        text = str(row.get(key) or "").strip()
        if len(text) >= 20:
            return text[:700]
    bits = [f"Legacy {row.get('technique')} check at "
            f"{row.get('location') or 'an unrecorded location'}."]
    if row.get("reported"):
        bits.append(f"Reported: {json.dumps(row['reported'], default=str)[:200]}.")
    if row.get("computed"):
        bits.append(f"Computed: {json.dumps(row['computed'], default=str)[:200]}.")
    return " ".join(bits)[:700].ljust(20, ".")


def convert_row(row: dict) -> dict:
    """One v1 finding row -> one findings-v2 row (spec section 1.7 mapping)."""
    sev5 = str(row.get("severity") or "indeterminate")
    technique = _map_technique(row.get("technique"))
    outcome = OUTCOME_FROM_FIVE.get(sev5, "undecided")
    prov = FIVE_TO_NINE.get(sev5)
    spec = BY_NAME.get(technique)
    impossible = bool(sev5 == "impossible" and spec is not None
                      and spec.evidence == EVIDENCE_ABSOLUTE)
    quarantined = bool(row.get("severity_before_quarantine")
                       or row.get("quarantine_reason"))
    src = row.get("severity_source") or {}
    tool_verdict = None
    if isinstance(src, dict) and src.get("tool"):
        tool_verdict = {"severity": src.get("tool"),
                        "tool": technique, "validated": True}
    elif quarantined:
        tool_verdict = {"severity": sev5, "tool": technique, "validated": True,
                        "quarantined_raw": row.get("severity_before_quarantine")}
    anchors: list[dict] = []
    quote = str(row.get("quote") or "").strip()
    if quote:
        anchors.append({"kind": "quote", "quote": quote})
    out = {
        "slug": str(row.get("id") or "finding"),
        "producer": _producer_for(row),
        "technique": technique,
        "title": _title_from(row),
        "description": _description_from(row),
        "location": str(row.get("location") or "unrecorded"),
        "outcome": outcome,
        "provisional_severity": prov if outcome == "problem" else None,
        "severity": prov if outcome == "problem" else None,
        "severity_is_provisional": True,
        "impossible": impossible,
        "tool_verdict": tool_verdict,
        # A v1 sweep row names the tool it used in `technique` and seldom
        # carries `severity_source`; the v1 viewer graded a registered
        # technique as computed (`viewer_facts._tool_produced`'s fallback), so
        # the conversion keeps that reading instead of filing every such row
        # as the model's own.
        "computed_by": ("deterministic_track"
                        if _producer_for(row) != "legacy_sweep"
                        else "registry_tool" if (tool_verdict or spec is not None)
                        else "model_reading"),
        "quarantined": quarantined,
        "anchors": anchors,
        "legacy": {"from_schema": FROM_SCHEMA,
                   "original_id": _review_key(row),
                   "original_severity": sev5,
                   "migrated_at": _now()},
    }
    if not anchors:
        out["anchor_problem"] = ("legacy row carried no verbatim quote; "
                                 "located via its recorded location only")
    if quarantined:
        out["quarantine_reason"] = row.get("quarantine_reason") \
            or "quarantined by the originating track"
    for key in ("quote", "inputs", "reported", "computed", "consequence",
                "notes", "artefacts", "reproduction", "reproduction_kind",
                "reproduction_valid", "reproduction_problem",
                "quote_verified", "quote_source", "quote_problem", "source"):
        if row.get(key) is not None:
            out[key] = row[key]
    return out


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_identity(source: Path, run_meta: dict | None) -> dict:
    rm = run_meta or {}
    analysed = rm.get("analysed_at")
    ident = {
        "pipeline_version": rm.get("version") or "0.0.1",
        "analysed_at": analysed or datetime.fromtimestamp(
            source.stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "analysed_at_source": "recorded" if analysed else "file_mtime",
    }
    return ident


def _doc_for(paper_id: str, rows: list[dict], source: Path,
             run_meta: dict | None, channels: dict) -> dict:
    ident = _run_identity(source, run_meta)
    seed = f"{paper_id}\x1f{ident['analysed_at']}\x1f{_sha(source)}"
    fv2.assign_finding_ids(rows, paper_id)
    # Project the paper's metadata.json so every consumer (stats, queries,
    # the DB) reads bibliography from the document, not from a second file.
    meta = None
    meta_path = source.parent.parent / "metadata.json" \
        if source.parent.name.startswith("forensic_review") \
        else source.parent / "metadata.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:  # noqa: BLE001
            meta = None
    return {
        "schema_version": "2.0",
        "paper_id": paper_id,
        **({"paper_metadata": fv2.paper_metadata_projection(meta)}
           if meta else {}),
        "run_id": f"r_{hashlib.sha256(seed.encode()).hexdigest()[:16]}",
        "findings": rows,
        "channels": fv2.channels_block(**channels),
        "adjudication": {"ran": False,
                         "skipped_reason": "migrated legacy run; the "
                         "adjudicator never existed for it"},
        "legacy": {"from_schema": FROM_SCHEMA, "source_file": source.name,
                   "source_sha256": _sha(source), "migrated_at": _now(),
                   **ident},
    }


def _write(out_path: Path, doc: dict, dry_run: bool) -> None:
    if not dry_run:
        tmp = out_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=2, default=str),
                       encoding="utf-8")
        tmp.replace(out_path)


def _skip(out_dir: Path, source: Path, reason: str, dry_run: bool) -> dict:
    rec = {"reason": reason, "source_file": source.name,
           "attempted_at": _now()}
    if not dry_run:
        (out_dir / "findings.v2.skipped.json").write_text(
            json.dumps(rec, indent=2), encoding="utf-8")
    return {"skipped": True, "reason": reason, "source": str(source)}


def _already(out_path: Path, source: Path) -> bool:
    if not out_path.exists():
        return False
    try:
        prior = json.loads(out_path.read_text())
        return prior.get("legacy", {}).get("source_sha256") == _sha(source)
    except Exception:  # noqa: BLE001
        return False


def convert_run(review_dir: Path, paper_id: str, *, force: bool = False,
                dry_run: bool = False) -> dict:
    source = review_dir / "findings.json"
    out_path = review_dir / "findings.v2.json"
    if not source.exists():
        return _skip(review_dir, source, "no findings.json in this run",
                     dry_run)
    if not force and _already(out_path, source):
        return {"skipped": True, "reason": "already converted (source "
                "unchanged)", "source": str(source)}
    try:
        v1 = json.loads(source.read_text())
        raw_rows = v1.get("findings")
        if not isinstance(raw_rows, list):
            return _skip(review_dir, source,
                         "v1 document carries no findings array", dry_run)
    except Exception as exc:  # noqa: BLE001
        return _skip(review_dir, source, f"unparseable v1 JSON: {exc}",
                     dry_run)
    run_meta = None
    rm_path = review_dir / "run_meta.json"
    if rm_path.exists():
        try:
            run_meta = json.loads(rm_path.read_text())
        except Exception:  # noqa: BLE001
            run_meta = None
    rows = [convert_row(r) for r in raw_rows if isinstance(r, dict)]
    stages = (run_meta or {}).get("stages") or {}

    def _track_state(name: str) -> tuple[str, str]:
        st = stages.get(name)
        if not isinstance(st, dict):
            return "did_not_run", "no stage record in run_meta"
        if st.get("is_error"):
            return "refused", str(st.get("error_subtype") or "stage error")
        return "ran", ""

    channels = {
        "tool_expert": ("ran", "migrated: the v1 numeric sweep"),
        "science_error": ("did_not_run",
                          "the science agent did not exist for this run"),
        "image_forensics": _track_state("image_forensics"),
        "tortured_phrases": _track_state("text_forensics"),
    }
    doc = _doc_for(paper_id, rows, source, run_meta, channels)
    _write(out_path, doc, dry_run)
    return {"converted": True, "n_findings": len(rows),
            "out": str(out_path), "source": str(source)}


def _issue_to_row(issue: dict) -> dict:
    """A workbench issue -> the pseudo-v1 row `convert_row` consumes. The
    issue space is the AUTHORITATIVE id space for review joins: reviewers
    judged what the workbench displayed (`review_issues.collect_issues`,
    manifest-fallback numbering and all), not the capped injection rows."""
    extras = issue.get("extras") if isinstance(issue.get("extras"), dict) \
        else {}
    technique = {"image": "image_duplication",
                 "text": "tortured_phrases"}.get(issue.get("kind"),
                                                 "reconcile")
    return {
        "id": issue.get("source_id") or issue.get("id"),
        "technique": technique,
        "severity": issue.get("severity") or "indeterminate",
        "severity_before_quarantine": extras.get("severity_before_quarantine"),
        "quarantine_reason": extras.get("quarantine_reason"),
        "explanation": issue.get("plain") or issue.get("title"),
        "location": issue.get("location"),
        "quote": issue.get("quote"),
        "reported": issue.get("reported"),
        "computed": issue.get("computed"),
    }


def convert_orphan_tracks(paper_dir: Path, paper_id: str, *,
                          force: bool = False, dry_run: bool = False) -> dict | None:
    """Track outputs with no enclosing run (masliah's 544), converted in the
    WORKBENCH'S issue space so review.json keys keep joining. Verdicts on
    findings the current artifacts no longer produce stay orphaned -- and
    reported: regenerated detector files are a fact the record must show,
    never paper over."""
    img = paper_dir / "image_duplication_findings.json"
    manifest = paper_dir / "panels" / "review" / "review_manifest.json"
    txt = paper_dir / "text_forensics.json"
    if not img.exists() and not manifest.exists() and not txt.exists():
        return None
    source = img if img.exists() else (manifest if manifest.exists() else txt)
    out_path = paper_dir / "findings.v2.json"
    if not force and _already(out_path, source):
        return {"skipped": True, "reason": "already converted (source "
                "unchanged)", "source": str(source)}
    try:
        from .review_issues import collect_issues
        issues = [i for i in collect_issues(paper_dir).get("issues", [])
                  if i.get("kind") in ("image", "text")]
    except Exception as exc:  # noqa: BLE001
        return _skip(paper_dir, source,
                     f"workbench issue collection failed: {exc}", dry_run)
    rows = [convert_row(_issue_to_row(i)) for i in issues]
    n_img = sum(1 for i in issues if i.get("kind") == "image")
    n_txt = sum(1 for i in issues if i.get("kind") == "text")
    channels: dict[str, tuple[str, str]] = {
        "tool_expert": ("did_not_run", "no numeric run for this paper"),
        "science_error": ("did_not_run", "no science run for this paper"),
        "image_forensics": (("ran", f"migrated: {n_img} workbench issue(s)")
                            if (img.exists() or manifest.exists())
                            else ("did_not_run", "no retained detector file")),
        "tortured_phrases": (("ran", f"migrated: {n_txt} row(s)")
                             if txt.exists() else ("did_not_run", "")),
    }
    doc = _doc_for(paper_id, rows, source, None, channels)
    _write(out_path, doc, dry_run)
    return {"converted": True, "n_findings": len(rows), "out": str(out_path),
            "source": str(source)}


def _review_orphans(paper_dir: Path, converted_ids: set[str]) -> list[str]:
    review = paper_dir / "review.json"
    if not review.exists():
        return []
    try:
        data = json.loads(review.read_text())
    except Exception:  # noqa: BLE001
        return ["review.json unreadable"]
    keys = set((data.get("issues") or {}).keys()) \
        | set((data.get("findings") or {}).keys())
    normalized = {k if ":" in k else f"image:{k}" if k.startswith("IMGDUP")
                  else f"numeric:{k}" for k in keys}
    return sorted(normalized - converted_ids)


def convert_paper(paper_dir: Path, *, force: bool = False,
                  dry_run: bool = False) -> dict:
    from .webapp_index import review_dirs
    paper_id = paper_dir.name
    records: list[dict] = []
    for rd in review_dirs(paper_dir):
        records.append({"run": rd.name,
                        **convert_run(rd, paper_id, force=force,
                                      dry_run=dry_run)})
    orphan = None
    if not records:
        orphan = convert_orphan_tracks(paper_dir, paper_id, force=force,
                                       dry_run=dry_run)
        if orphan:
            records.append({"run": None, **orphan})
    converted_ids: set[str] = set()
    for rec in records:
        if rec.get("converted"):
            try:
                doc = json.loads(Path(rec["out"]).read_text()) \
                    if not dry_run else None
            except Exception:  # noqa: BLE001
                doc = None
            for row in (doc or {}).get("findings", []):
                oid = (row.get("legacy") or {}).get("original_id")
                if oid:
                    converted_ids.add(oid)
    orphans = _review_orphans(paper_dir, converted_ids) \
        if not dry_run and converted_ids else []
    return {"paper": paper_dir.name, "records": records,
            "review_orphans": orphans}


def convert_tree(root: Path, *, force: bool = False,
                 dry_run: bool = False) -> dict:
    """Every paper under a corpus root; writes migration_report.json at the
    root (unless dry-run, which only returns it)."""
    report = {"root": str(root), "generated_at": _now(), "dry_run": dry_run,
              "n_converted": 0, "n_skipped": 0, "n_review_orphans": 0,
              "by_reason": {}, "papers": []}
    from .webapp_index import iter_paper_dirs
    # done/<slug> and batch folders hold papers too -- the flat scan left
    # every archived paper unconverted (cerebrolysin's done/ papers had no
    # v2 docs at all until the corpus-stats --verify drift check exposed
    # the shared hole, 2026-08-21).
    for paper_dir in iter_paper_dirs(root):
        rec = convert_paper(paper_dir, force=force, dry_run=dry_run)
        if not rec["records"]:
            continue
        for r in rec["records"]:
            if r.get("converted"):
                report["n_converted"] += 1
            else:
                report["n_skipped"] += 1
                reason = r.get("reason", "?")
                report["by_reason"][reason] = \
                    report["by_reason"].get(reason, 0) + 1
        report["n_review_orphans"] += len(rec["review_orphans"])
        report["papers"].append(rec)
    if not dry_run:
        (root / "migration_report.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report
