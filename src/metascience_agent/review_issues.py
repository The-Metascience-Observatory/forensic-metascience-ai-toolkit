"""The unified issue list the rapid reviewer shows.

Stage 2 already helps prioritize: it writes `consequence` (does this change
a conclusion?) and a proposed `rank`. The renderer, not the model, is the
order a reader sees -- `report_render.sort_findings` re-sorts by severity,
then consequence, then that rank. This module keeps that contract for
numeric findings and extends it across the image and text tracks so one
list can be triaged.

Improvements over severity-then-model-rank alone (the thing that used to
put a typo'd p-value above a result that flips):

  * consequence still outranks the model's `rank` within a severity band
  * a computed flip outranks an asserted one (already in `consequence.rank`)
  * a `field_norm` finding, or one with no sweep ancestor, sorts after a
    finding of the same severity that rests on the paper's own numbers --
    those are the dangerous unbacked accusations
  * an image group that spans figures (the caption contradicts the pixels)
    is treated at least as `highly_suspicious` for ordering
  * an image group the adjudicator already explained sorts last, not as if
    it were still a charge
  * tortured-phrase rows stay visible but cannot outrank arithmetic of the
    same or worse severity (they arrive quarantined)

Each issue carries `priority_reason` so the list can say why it is where it
is. The HTML bundle and `report.md` keep using `sort_findings` unchanged.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import consequence as _consequence
from .finding_files import artefacts_for_editorial, index_sweep
from .report_render import SEVERITY_RANK, sort_findings
from .review_io import load_review
from .webapp_index import review_dirs

_WARRANT_LATE = {"field_norm", "", None}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _v2_numeric_issues(
    paper_dir: Path, d: Path
) -> tuple[list[dict], dict, str] | None:
    """Issue rows from a findings-v2 document (a parallel-pipeline run).

    Without this branch a parallel run was INVISIBLE to the reviewer: the
    loop below reads report.json, which parallel runs do not write, so the
    pane silently fell back to an older legacy run (found while surfacing
    the medicina rematch, 2026-08-21). Only analyst rows map here -- the
    doc's image_track/text_track copies are SKIPPED because the paper-level
    track files already feed `_image_issues`/`_text_issues`, and mapping
    both would show every image finding twice.
    """
    doc = _read_json(d / "findings.v2.json")
    if not isinstance(doc, dict) or not isinstance(doc.get("findings"), list):
        return None
    return _v2_issues_from_doc(doc, d.name)


#: The tool named by a generated reproduction (`agent.py` writes
#: `metascience tool run <tool> --json ...` from the ledger call that
#: `findings_v2.backing_call` picked, and stamps `reproduction_source:
#: generated_from_tool_call`). That stamp IS the backing-call join, made at
#: write time, when the ledger was in hand; the workbench never has it.
_REPRODUCTION_TOOL = re.compile(r"\bmetascience\s+tool\s+run\s+([A-Za-z0-9_]+)")

MODEL_JUDGEMENT = "model judgement"


@lru_cache(maxsize=1)
def _registry_tools() -> frozenset[str]:
    from .registry import SPECS
    return frozenset(s.name for s in SPECS)


def _called_tool(call) -> str | None:
    if isinstance(call, dict):
        name = call.get("tool_short") or call.get("tool")
        return str(name) if name else None
    return str(call) if isinstance(call, str) and call else None


def finding_tool(f: dict) -> dict:
    """Which tool triggered a finding, and how we know: {"tool", "source"}.

    In order of evidence, strongest first:
      * `tool_verdict`  -- the validated registry verdict joined to the row;
      * `tool_call`     -- the one ledger call behind it (`backing_call`,
                           or the reproduction generated from that call);
      * `technique`     -- the row's technique is a registry tool's name, but
                           no recorded call backs it: the analyst LABELLED it
                           with the tool, which is weaker, and the badge says so;
      * `model_judgement` -- none of the above: the analyst's own reading.
    `not_recorded` is the fifth state and is not the fourth: a cached summary
    made before the workbench carried `tool_basis` cannot say, and reading
    that absence as "model judgement" would be LESSONS #1.

    `f` is a full findings-v2 record, or a workbench summary row carrying
    `tool_basis` (the same ingredients, picked by `remote.TOOL_BASIS`).
    """
    if "tool_basis" in f:
        basis = f["tool_basis"]
        if not isinstance(basis, dict):
            return {"tool": None, "source": "not_recorded"}
    else:
        basis = f
    verdict = basis.get("tool_verdict")
    named = _called_tool(verdict)
    if named:
        return {"tool": named, "source": "tool_verdict"}
    named = _called_tool(basis.get("backing_call"))
    if not named and basis.get("reproduction_source") == "generated_from_tool_call":
        m = _REPRODUCTION_TOOL.search(str(basis.get("reproduction") or ""))
        named = m.group(1) if m else None
    if named:
        return {"tool": named, "source": "tool_call"}
    technique = f.get("technique")
    if technique and technique in _registry_tools():
        return {"tool": technique, "source": "technique"}
    return {"tool": MODEL_JUDGEMENT, "source": "model_judgement"}


def _v2_issues_from_doc(doc: dict, run_name: str, *, include_tracks=False) -> tuple[list[dict], dict, str]:
    """Issue rows from an in-memory findings-v2 document. The file branch
    and the database branch (`_db_numeric_issues`) share this one mapping so
    a finding renders identically whichever archive it was read from."""
    adj = doc.get("adjudication") if isinstance(doc.get("adjudication"), dict) \
        else {}
    out: list[dict] = []
    by_id: dict[str, dict] = {}
    for f in doc["findings"]:
        if not isinstance(f, dict):
            continue
        fid = str(f.get("finding_id") or f.get("slug") or "")
        if fid:
            by_id[fid] = f
        if not include_tracks and f.get("producer") in ("image_track", "text_track", "raw_data_track"):
            continue
        if f.get("outcome") != "problem":
            continue
        action = (f.get("adjudication") or {}).get("action")
        if action == "merged":
            continue                      # the surviving parent carries it
        sev9 = f.get("severity")
        tool = finding_tool(f)
        passages = []
        for i, a in enumerate(f.get("anchors") or []):
            if isinstance(a, dict) and a.get("quote"):
                passages.append({
                    "id": a.get("passage_id") or chr(ord("a") + len(passages)),
                    "quote": a["quote"],
                    "role": a.get("role"),
                    "label": a.get("label"),
                })
        out.append({
            "id": fid or f.get("slug") or "",
            "kind": "numeric",
            "source_id": fid,
            "run": run_name,
            "title": f.get("title") or "(untitled)",
            "plain": f.get("description") or "",
            "severity": None,
            "severity_9": sev9 if isinstance(sev9, int) else None,
            "severity_is_provisional": bool(f.get("severity_is_provisional")),
            "impossible": bool(f.get("impossible")),
            "adjudication_action": action,
            "adjudication_rationale": (f.get("adjudication") or {}).get("rationale"),
            "technique": f.get("technique"),
            "producer": f.get("producer"),
            "tool": tool["tool"],
            "tool_source": tool["source"],
            "confidence": None,
            "location": f.get("location"),
            "quote": f.get("quote") or "",
            "quote_verified": f.get("quote_verified"),
            "reported": f.get("reported"),
            "computed": f.get("computed"),
            "consequence": f.get("consequence"),
            "warrant": None,
            "rank": None,
            # The unbacked-accusation lever, v2 flavor: a row with a joined
            # registry-tool verdict sorts with the backed findings; a bare
            # model reading takes the same late-warrant penalty an
            # unbacked editorial row always took.
            "stage1_finding_ids": [fid] if f.get("computed_by") == "registry_tool" else [],
            "passages": passages,
            "artefacts": [],
            "extras": {},
        })
    headline: dict = {}
    hid = adj.get("headline_finding_id")
    if hid and hid in by_id:
        headline = {"statement": by_id[hid].get("title") or ""}
    elif adj.get("summary"):
        headline = {"statement": str(adj["summary"]).split(". ")[0] + "."}
    return out, headline, run_name


def _db_numeric_issues(paper_dir: Path, run: str | None) -> dict:
    """Analyst issues from the findings database, for a paper with no run
    directory on this disk.

    The run happened on another machine and the auto-push carried it to
    Neon; the files never came here. Without this branch the pane said "No
    reviewable issues on disk", which a reader took as "nothing recorded"
    (`10.1002--jfa2.70171`, 2026-09-01: 24 findings in the database).

    Returns the same keys `collect_issues` publishes plus `database`, the
    tri-state from `db_push.fetch_paper_runs` -- `unavailable` and `miss`
    are different facts and both reach the page in words. Run names that
    came back from a DOI match in ANOTHER corpus are prefixed `corpus/`, so
    two corpora's `forensic_review` runs stay distinguishable in the picker.
    """
    from .db_push import fetch_paper_runs
    got = fetch_paper_runs(paper_dir)
    runs = got.get("runs") or []
    corpora = {r.get("corpus") for r in runs}
    labelled = []
    for r in runs:
        label = r.get("name") or r.get("run_uid") or "run"
        if len(corpora) > 1 or r.get("matched_by") == "doi":
            label = f"{r.get('corpus')}/{label}"
        labelled.append((label, r))
    database = {"state": got.get("state"), "detail": got.get("detail"),
                "runs": [{"label": lab, "corpus": r.get("corpus"),
                          "name": r.get("name"), "run_uid": r.get("run_uid"),
                          "matched_by": r.get("matched_by"),
                          "analysed_at": r.get("analysed_at"),
                          "pipeline_version": r.get("pipeline_version"),
                          "verdict": ((r.get("doc") or {}).get("adjudication")
                                      or {}).get("verdict"),
                          "paper_severity": ((r.get("doc") or {}).get(
                              "adjudication") or {}).get("paper_severity"),
                          "n_findings": len((r.get("doc") or {}).get(
                              "findings") or [])}
                         for lab, r in labelled]}
    if not labelled:
        return {"issues": [], "headline": {}, "run": None,
                "available_runs": [], "database": database}
    picked = labelled[0]                       # newest analysed_at first
    if run:
        for lab, r in labelled:
            if run in (lab, r.get("name"), r.get("run_uid")):
                picked = (lab, r)
                break
    label, rec = picked
    issues, headline, _ = _v2_issues_from_doc(rec["doc"], label)
    return {"issues": issues, "headline": headline, "run": label,
            "available_runs": [lab for lab, _ in labelled],
            "database": database}


def _numeric_issues(
    paper_dir: Path, rdirs: list[Path]
) -> tuple[list[dict], dict, str | None]:
    for d in rdirs:
        v2 = _v2_numeric_issues(paper_dir, d)
        if v2 is not None:
            return v2
        report = _read_json(d / "report.json")
        if not isinstance(report, dict):
            continue
        findings = report.get("findings")
        if not isinstance(findings, list):
            continue
        headline = report.get("headline") if isinstance(report.get("headline"), dict) else {}
        sweep = index_sweep(_read_json(d / "findings.json"))
        out = []
        for i, f in enumerate(sort_findings(findings)):
            if not isinstance(f, dict):
                continue
            fid = str(f.get("id") or i + 1)
            out.append({
                "id": f"numeric:{fid}",
                "kind": "numeric",
                "source_id": fid,
                "run": d.name,
                "title": f.get("title") or "(untitled)",
                "plain": f.get("plain") or "",
                "severity": str(f.get("severity") or "").lower() or None,
                "confidence": f.get("confidence"),
                "location": f.get("location"),
                "quote": f.get("quote") or f.get("reported") or "",
                "reported": f.get("reported"),
                "computed": f.get("computed"),
                "consequence": f.get("consequence"),
                "warrant": f.get("warrant"),
                "rank": f.get("rank"),
                "stage1_finding_ids": f.get("stage1_finding_ids") or [],
                "passages": f.get("passages") or [],
                "artefacts": artefacts_for_editorial(f, sweep, paper_dir),
                "extras": {},
            })
        return out, headline, d.name
    return [], {}, None


def _iter_placements(group: dict):
    """Yield placement dicts from either the dict-by-uid or list shape."""
    pl = group.get("placements")
    if isinstance(pl, dict):
        for recs in pl.values():
            for rec in recs or []:
                if isinstance(rec, dict):
                    yield rec
    elif isinstance(pl, list):
        for rec in pl:
            if isinstance(rec, dict):
                yield rec


def _placement_page(rec: dict) -> int | None:
    """1-based PDF page, or None. `bool` is a subclass of `int` — reject it."""
    page = rec.get("page")
    if isinstance(page, bool) or not isinstance(page, (int, float)):
        return None
    page = int(page)
    return page if page >= 1 else None


def _image_where(group: dict) -> tuple[str | None, list[int]]:
    """Human line for where the matched panels sit. Never invents page 1."""
    spots: list[tuple[int, str | None]] = []
    seen: set[tuple[int, str | None]] = set()
    for rec in _iter_placements(group):
        page = _placement_page(rec)
        if page is None:
            continue
        lab = rec.get("figure_label") or None
        if isinstance(lab, str):
            lab = lab.strip() or None
        key = (page, lab)
        if key in seen:
            continue
        seen.add(key)
        spots.append(key)
    spots.sort(key=lambda s: (s[0], s[1] or ""))
    pages = sorted({p for p, _ in spots})
    labels = [lab for _, lab in spots if lab]
    distinct = list(dict.fromkeys(labels))
    if not pages:
        named = [str(x) for x in (group.get("figure_labels") or []) if x]
        return (", ".join(named) or None, [])
    if len(distinct) == 1:
        page_bit = " and p. ".join(str(p) for p in pages)
        return f"{distinct[0]} on p. {page_bit}", pages
    if distinct:
        bits = []
        for page, lab in spots:
            bits.append(f"{lab or 'unlabelled'} p. {page}")
        return " vs ".join(bits), pages
    return "p. " + " and p. ".join(str(p) for p in pages), pages


def _image_issues(paper_dir: Path) -> list[dict]:
    manifest = _read_json(paper_dir / "panels" / "review" / "review_manifest.json")
    groups = []
    if isinstance(manifest, dict):
        groups = list(manifest.get("groups") or [])
    if not groups:
        # Fall back to a retained detector result.
        for cand in (paper_dir / "image_duplication_findings.json",):
            obj = _read_json(cand)
            if isinstance(obj, dict):
                groups = list(obj.get("duplicate_groups") or [])
                break
        for d in review_dirs(paper_dir):
            obj = _read_json(d / "image_analysis.json")
            if isinstance(obj, dict) and obj.get("duplicate_groups"):
                groups = list(obj["duplicate_groups"])
                break
    out = []
    for i, g in enumerate(groups):
        if not isinstance(g, dict):
            continue
        idx = g.get("group_index")
        if not isinstance(idx, int):
            idx = i + 1
        evidence = g.get("duplication_evidence")
        sev = str(g.get("severity_before_quarantine") or g.get("severity")
                  or "").lower() or None
        labels = g.get("figure_labels") or []
        where, pages = _image_where(g)
        title = g.get("sentence") or (
            f"Image match ({g.get('kind') or 'group'}) "
            + (" / ".join(str(x) for x in labels) if labels else f"group {idx}")
        )
        exhibit = g.get("exhibit_png") or g.get("still") or None
        video = g.get("video_mp4") or None
        # Paths in the manifest are sometimes relative to panels/review.
        def _rel(p):
            if not p:
                return None
            p = str(p)
            if p.startswith("panels/"):
                return p
            return f"panels/review/{Path(p).name}"
        out.append({
            "id": f"image:IMGDUP-{idx}",
            "kind": "image",
            "source_id": f"IMGDUP-{idx}",
            "run": None,
            "title": title,
            "plain": title,
            "severity": sev,
            "confidence": None,
            "location": where,
            "quote": "",
            "reported": None,
            "computed": None,
            "consequence": None,
            "warrant": "logical",
            "rank": idx,
            "stage1_finding_ids": [],
            "duplication_evidence": evidence,
            "spans_figures": g.get("spans_figures"),
            "extras": {
                "kind": g.get("kind"),
                "panels": g.get("panels") or [],
                "figure_labels": labels,
                "pages": pages,
                "placements": g.get("placements") or {},
                "measurements": g.get("measurements") or g.get("match_stats") or {},
                "adjudication": g.get("adjudication"),
                "exhibit": _rel(exhibit),
                "video": _rel(video),
                "severity_before_quarantine": g.get("severity_before_quarantine"),
            },
        })
    return out


def _text_issues(paper_dir: Path, rdirs: list[Path]) -> list[dict]:
    obj = None
    run = None
    for d in rdirs:
        cand = _read_json(d / "text_forensics.json")
        if isinstance(cand, dict):
            obj, run = cand, d.name
            break
    if obj is None:
        return []
    rows = obj.get("findings_rows")
    if not isinstance(rows, list):
        # Older files may only have result.matches.
        result = obj.get("result") if isinstance(obj.get("result"), dict) else obj
        matches = result.get("matches") or []
        if not matches:
            return []
        rows = [{
            "id": f"TP-{i+1}",
            "location": m.get("location") or m.get("family"),
            "explanation": m.get("fingerprint") or m.get("phrase") or "",
            "severity": "indeterminate",
            "severity_before_quarantine": m.get("severity"),
        } for i, m in enumerate(matches) if isinstance(m, dict)
          and m.get("suppressed_by") is None]
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or f"TP-{i+1}")
        out.append({
            "id": f"text:{sid}",
            "kind": "text",
            "source_id": sid,
            "run": run,
            "title": row.get("explanation") or row.get("location") or sid,
            "plain": row.get("explanation") or "",
            "severity": str(row.get("severity") or "indeterminate").lower(),
            "confidence": None,
            "location": row.get("location"),
            "quote": (row.get("inputs") or {}).get("quote")
                     if isinstance(row.get("inputs"), dict) else "",
            "reported": None,
            "computed": None,
            "consequence": None,
            "warrant": "field_norm",
            "rank": i + 1,
            "stage1_finding_ids": [],
            "extras": {
                "severity_before_quarantine": row.get("severity_before_quarantine"),
                "quarantine_reason": row.get("quarantine_reason"),
            },
        })
    return out


def _priority_reason(issue: dict) -> str:
    cons = issue.get("consequence") if isinstance(issue.get("consequence"), dict) else {}
    if cons.get("flips_significance") is True:
        basis = cons.get("basis") or "asserted"
        return f"changes a significance decision ({basis})"
    claims = cons.get("claims_affected")
    if isinstance(claims, int) and claims > 0:
        return f"touches {claims} stated claim(s)"
    if issue.get("kind") == "image" and issue.get("spans_figures"):
        return "image match spans figures whose captions disagree"
    if issue.get("kind") == "image" and issue.get("duplication_evidence") is False:
        return "image group already explained; kept so you can disagree"
    if issue.get("kind") == "text":
        return "tortured-phrase / boilerplate screen (quarantined; not a verdict)"
    sev = issue.get("severity")
    if sev == "impossible" or issue.get("impossible"):
        return "impossible arithmetic"
    if issue.get("adjudication_action") == "discarded":
        return "discarded by the adjudicator -- kept so you can disagree"
    if isinstance(issue.get("severity_9"), int):
        prov = " (provisional)" if issue.get("severity_is_provisional") else ""
        return f"severity {issue['severity_9']} of 9{prov}"
    warrant = issue.get("warrant")
    if warrant in _WARRANT_LATE or not issue.get("stage1_finding_ids"):
        if issue.get("kind") == "numeric":
            return "editorial finding with no sweep ancestor, or a reviewer-supplied norm"
    if cons.get("flips_significance") is False:
        return "checked: changes no significance decision"
    return "severity order; consequence not determined"


def issue_sort_key(issue: dict) -> tuple:
    """Lower sorts first. See module docstring for the keys."""
    sev = str(issue.get("severity") or "").lower()
    sev_rank = SEVERITY_RANK.get(sev, 99)
    nine = issue.get("severity_9")
    if isinstance(nine, int):
        # Map the 1-9 ladder onto the 5-enum rank scale so v2 analyst rows
        # interleave honestly with the legacy-ranked image/text tracks
        # (the inverse of severity9.FIVE_TO_NINE's anchor points).
        sev_rank = 0 if nine >= 5 else {4: 1, 3: 2, 2: 3, 1: 4}[nine]
        if issue.get("adjudication_action") == "discarded":
            sev_rank = 8   # visible, after everything still standing
    nine_tb = -(nine if isinstance(nine, int) else 0)

    if issue.get("kind") == "image":
        if issue.get("duplication_evidence") is False:
            sev_rank = 8
        elif issue.get("spans_figures"):
            sev_rank = min(sev_rank, 1)
        else:
            # Unexplained image match: at least suspicious, never "consistent"
            # just because the track is quarantined.
            if sev_rank >= 99:
                sev_rank = 2
            else:
                sev_rank = min(sev_rank, 2)

    if issue.get("kind") == "text":
        # Quarantined: cannot outrank numeric/image of the same severity.
        sev_rank = max(sev_rank if sev_rank < 99 else 3, 3)

    cons = _consequence.rank(issue)
    warrant_late = 1 if (issue.get("kind") == "numeric"
                         and (issue.get("warrant") in _WARRANT_LATE
                              or not issue.get("stage1_finding_ids"))) else 0
    model_rank = issue.get("rank") if isinstance(issue.get("rank"), int) else 0
    return (sev_rank, nine_tb, cons, warrant_late, model_rank,
            issue.get("id") or "")


def sort_issues(issues: list[dict]) -> list[dict]:
    ordered = sorted(issues, key=issue_sort_key)
    out = []
    for i, iss in enumerate(ordered, start=1):
        g = dict(iss)
        g["priority"] = i
        g["priority_reason"] = _priority_reason(g)
        out.append(g)
    return out


def collect_issues(paper_dir: Path, run: str | None = None) -> dict:
    """Everything the rapid reviewer needs for one paper, minus locators.

    `run` pins a specific review directory by name (the GUI's run picker);
    an unknown name falls back to the default newest-usable rule rather
    than erroring -- a stale link must not blank the pane."""
    paper_dir = Path(paper_dir)
    from .analysis_history import report_view
    historical = report_view(paper_dir, run)
    if historical is not None:
        return historical
    requested = run
    all_rdirs = review_dirs(paper_dir)
    rdirs = all_rdirs
    if run:
        picked = [d for d in all_rdirs if d.name == run]
        if picked:
            rdirs = picked
    numeric, headline, served = _numeric_issues(paper_dir, rdirs)
    run = served
    available = [d.name for d in all_rdirs]
    # Where the analyst findings came from. `disk` is the archive of record
    # on this machine; `database` is the fallback for a run pushed from
    # another one; `none` means both were asked and neither had anything --
    # and the `database` sub-record says whether Neon was even reachable.
    source: dict = {"kind": "disk" if served else "none", "database": None}
    if served is None:
        db = _db_numeric_issues(paper_dir, requested)
        source["database"] = db["database"]
        if db["issues"] or db["run"]:
            numeric, headline, run = db["issues"], db["headline"], db["run"]
            available = db["available_runs"]
            source["kind"] = "database"
    image = _image_issues(paper_dir)
    text = _text_issues(paper_dir, rdirs)
    issues = sort_issues(list(numeric) + image + text)
    review = load_review(paper_dir)
    bundle = None
    for d in all_rdirs:
        cand = d.parent / f"{d.name}_bundle"
        if cand.is_dir():
            bundle = cand.name
            break
    return {
        "paper_dir": str(paper_dir),
        "latest_run": run,
        "available_runs": available,
        "n_runs": len(available),
        "headline": headline,
        "issues": issues,
        "review": review,
        "bundle": bundle,
        "source": source,
    }
