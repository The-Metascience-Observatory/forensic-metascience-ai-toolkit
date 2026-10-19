"""Score a set of reviews against the GRIM ground truth, cell by cell.

Three numbers per labelled cell, because they come apart in practice:

  checked   some GRIM-family call ran on this value at this n (for grim_sweep:
            an n range containing this n)
  flagged   such a grim_check / grim_percentage call failed on granularity
            (`granularity`, or `rounding_convention` for a truncation rescue;
            grim_percentage before 1.81.0 stated it as an accusing severity
            with no mode)
  reported  a non-discarded GRIM-family finding in findings.v2.json prints
            the value (title, description or notes). Two cells of
            one paper with the same value and n cannot be told apart here.

MEASURED 2026-10-16 (10.1371--journal.pone.0042828, grok-4.6, v1.78.0): 7
cells flagged, 1 reported. A recall that counts only one of these hides the
other's failure.

Recall is reported per `tier` (see verify_labels.py). The headline is
`primary` cells whose value was found in the paper's own text: the cells
the tool is DESIGNED to flag, at an n the paper prints. `rounding_only`
cells are flagged only as `rounding_convention`, by design; `inferred_n`
cells rest on an n the paper never prints. Neither is a miss.

`false_alarm` cells are the reverse: a critic flagged them and the authors
explained them, so `flagged` / `reported` there count the tool's errors.

Cells are not independent: one paper contributes up to 100. So recall is
also given per PAPER (a paper with any headline cell counts as found when
at least one of its headline cells is flagged / reported).

    python benchmarks/grim/score.py --labels SET/labels.jsonl --papers-root DIR \
        --review GLOB [--split dev] [--json OUT]

`DIR/<paper_id>/` (or `DIR/<subfolder>/<paper_id>/`) holds each paper;
GLOB picks its review directory
(e.g. 'forensic_review_sonnet_v1.79.0'); the newest match by run_meta
`analysed_at` wins.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

GRIM_TOOLS = frozenset({"grim_check", "grim_percentage", "grimmer_check"})
#: GRIMMER also tests the SD, so a GRIMMER failure is not by itself a GRIM
#: detection: a mean that passes GRIM fails GRIMMER on its SD alone. It flags
#: only with failure_mode `granularity` (the mean failed); see `_flags`.
FLAGGING_TOOLS = frozenset({"grim_check", "grim_percentage", "grim_sweep"})
GRIM_TECHNIQUES = GRIM_TOOLS | {"grim_sweep", "check_table"}
FLAG_MODES = frozenset({"granularity", "rounding_convention"})
#: Before 1.81.0 grim_percentage stated a detection by severity alone: an
#: inconsistent percentage came back `impossible` with `failure_mode: None`
#: (measured 2026-10-18 on Cureus: 12 of 12 such calls were missed). It now
#: says `granularity`; the severity branch stays for archived reviews.
ACCUSING = frozenset({"suspicious", "highly_suspicious", "impossible"})
DROPPED_ACTIONS = frozenset({"discarded"})


def _short(tool: str) -> str:
    return tool.rsplit("__", 1)[-1]


def _calls(review: Path) -> list[dict]:
    """Every GRIM-family evaluation in the review's tool ledgers, flattened:
    direct calls plus the per-cell rows of `check_table` batches."""
    out = []
    for path in sorted(review.glob("toolcalls.*.json")):
        stage = path.name[len("toolcalls."):-len(".json")]
        try:
            ledger = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for call in ledger if isinstance(ledger, list) else []:
            tool = _short(call.get("tool") or "")
            try:
                result = json.loads(call.get("result") or "{}")
            except (TypeError, ValueError):
                result = {}
            if not isinstance(result, dict):
                result = {}
            if tool in GRIM_TOOLS:
                out.append({"stage": stage, "tool": tool,
                            "inputs": call.get("input") or {},
                            "severity": result.get("severity"),
                            "failure_mode": result.get("failure_mode")})
            elif tool == "grim_sweep":
                # One record per swept value, over the sweep's n range. A sweep
                # of SEVERAL values answers whether they can share one n, not
                # whether each is possible, so only a one-value sweep can flag
                # (measured 2026-10-18: Sonnet swept Shaaban's percentages one
                # at a time, n from 2 to the stated n).
                inp = call.get("input") or {}
                values = inp.get("values") or []
                scale = 100.0 if inp.get("value_type") == "proportion" else 1.0
                for v in values:
                    try:
                        pct = float(v) * scale
                    except (TypeError, ValueError):
                        continue
                    out.append({"stage": stage, "tool": tool,
                                "inputs": {"percentage": pct,
                                           "n_range": (inp.get("n_min", 2), inp.get("n_max"))},
                                "severity": result.get("severity") if len(values) == 1 else None,
                                "failure_mode": result.get("failure_mode")})
            elif tool == "check_table":
                for row in result.get("results") or []:
                    if row.get("tool") in GRIM_TOOLS:
                        res = row.get("result") or {}
                        out.append({"stage": stage, "tool": row["tool"],
                                    "inputs": row.get("inputs") or {},
                                    "severity": row.get("severity"),
                                    "failure_mode": res.get("failure_mode")})
    out += _harness_calls(review)
    return out


def _harness_calls(review: Path) -> list[dict]:
    """The harness GRIM sweep's checks (toolkit 1.82.0+), from
    `run_meta.json` `exhaustive_checks.grim.checked_cells`. Not in any
    ledger: the harness checks every declared cell itself after the run."""
    try:
        meta = json.loads((review / "run_meta.json").read_text())
    except (OSError, ValueError):
        return []
    grim = ((meta.get("exhaustive_checks") or {}).get("grim") or {})
    out = []
    for c in grim.get("checked_cells") or []:
        what = "percentage" if c.get("what") == "percent" else "mean"
        failed = c.get("status") in ("inconsistent", "explained_by_nonresponse")
        out.append({"stage": "harness",
                    "tool": "grim_percentage" if what == "percentage" else "grim_check",
                    "inputs": {what: c.get("value"), "n": c.get("n")},
                    "severity": "suspicious" if failed else "consistent",
                    "failure_mode": "granularity" if failed else None,
                    "harness_status": c.get("status")})
    return out


def _flags(call: dict) -> bool:
    """Did this call detect a GRIM failure of the MEAN (not of an SD, not a
    range)? grimmer_check says so only with failure_mode `granularity` ("mean
    fails GRIM"); its `rounding_convention` can describe the mean/SD pair, so it
    does not count. Measured 2026-10-18: Sonnet tested REST's 5.20 at n = 31
    with grimmer_check alone, which returned `granularity`."""
    if call["tool"] == "grimmer_check":
        return call["failure_mode"] == "granularity"
    return call["tool"] in FLAGGING_TOOLS and (
        call["failure_mode"] in FLAG_MODES
        or (call["failure_mode"] is None and call["severity"] in ACCUSING))


def _matches(call: dict, cell: dict) -> bool:
    inp = call["inputs"]
    if "n_range" in inp:
        if cell.get("kind") != "percentage":
            return False
        lo, hi = inp["n_range"]
        try:
            return (abs(float(inp["percentage"]) - float(cell["value"])) <= 1e-9
                    and int(lo) <= int(cell["n"]) <= int(hi))
        except (TypeError, ValueError):
            return False
    raw = inp.get("percentage") if cell.get("kind") == "percentage" else inp.get("mean")
    try:
        if abs(float(raw) - float(cell["value"])) > 1e-9:
            return False
        n = int(inp.get("n"))
    except (TypeError, ValueError):
        return False
    return n in {int(cell["n"]), int(cell["n"]) * int(cell.get("items_k") or 1)}


def _printed(value: str) -> re.Pattern:
    """The value as printed, not as a fragment of a longer number, nor a side
    of a fraction: "1/10" in a finding's working is not the value 10
    (measured 2026-10-18 on Shaaban)."""
    return re.compile(r"(?<![\d./])" + re.escape(value) + r"(?!\.?\d|/)")


def _reported(findings: list[dict], cell: dict) -> bool:
    pat = _printed(str(cell["value"]))
    for f in findings:
        if f.get("technique") not in GRIM_TECHNIQUES:
            continue
        if f.get("outcome") not in ("problem", "undecided"):
            continue
        if (f.get("adjudication") or {}).get("action") in DROPPED_ACTIONS:
            continue
        if f.get("producer") == "harness":
            # A harness row lists EVERY failing cell in `inputs.cells` and
            # nothing that passed; its prose names only the first twelve.
            if any(pat.search(str(c.get("raw") or "")) and _same_n(c, cell)
                   for c in (f.get("inputs") or {}).get("cells") or []):
                return True
            continue
        # Not `quote` (the source row) nor `inputs` (e.g. `means_tested`):
        # both carry the passing values beside the failing ones.
        text = " ".join(str(f.get(k) or "") for k in
                        ("title", "description", "notes"))
        if pat.search(text):
            return True
    return False


def _same_n(harness_cell: dict, cell: dict) -> bool:
    try:
        n = int(harness_cell.get("n"))
    except (TypeError, ValueError):
        return False
    return n in {int(cell["n"]), int(cell["n"]) * int(cell.get("items_k") or 1)}


def paper_dir(root: Path, paper_id: str) -> Path:
    """`root/<paper_id>`, or `root/<subfolder>/<paper_id>`: a set keeps its
    confirmed papers in `verified/` beside the rest. Two copies is an error,
    not a choice."""
    direct = root / paper_id
    found = [direct] if direct.is_dir() else []
    if root.is_dir():
        found += [sub / paper_id for sub in sorted(root.iterdir())
                  if sub.is_dir() and (sub / paper_id).is_dir()]
    if len(found) > 1:
        raise ValueError(f"{paper_id} is in more than one place: {found}")
    return found[0] if found else direct


def find_review(paper_dir: Path, glob: str) -> Path | None:
    best, best_at = None, ""
    for d in paper_dir.glob(glob):
        meta = d / "run_meta.json"
        if not meta.is_file():
            continue
        try:
            at = json.loads(meta.read_text()).get("analysed_at") or ""
        except ValueError:
            continue
        if best is None or at > best_at:
            best, best_at = d, at
    return best


def score(labels: list[dict], papers_root: Path, glob: str) -> dict:
    rows, missing = [], []
    for paper in labels:
        cells = paper.get("cells") or []
        if not cells:
            continue
        review = find_review(paper_dir(papers_root, paper["paper_id"]), glob)
        if review is None:
            missing.append(paper["paper_id"])
            continue
        calls = _calls(review)
        doc = json.loads((review / "findings.v2.json").read_text())
        findings = [f for f in doc.get("findings") or [] if isinstance(f, dict)]
        for cell in cells:
            hits = [c for c in calls if _matches(c, cell)]
            rows.append({
                "paper_id": paper["paper_id"], "cell": cell["id"],
                "value": cell["value"], "n": cell["n"],
                "arithmetic": (cell.get("arithmetic") or {}).get("verdict"),
                "tier": cell.get("tier") or "unverified",
                "value_verified": bool(cell.get("value_verified")),
                "status": paper.get("status"),
                "checked": bool(hits),
                # By failure MODE, not severity: an `out_of_range` failure
                # against a scale bound the model assumed is not a GRIM
                # detection (measured: Grok's 16.5, which passes GRIM).
                "flagged": any(_flags(c) for c in hits),
                "reported": _reported(findings, cell),
                "review": str(review)})
    def tally(group):
        t = {"cells": len(group)}
        for k in ("checked", "flagged", "reported"):
            t[k] = sum(r[k] for r in group)
        return t

    totals = {}
    for tier in sorted({r["tier"] for r in rows}):
        totals[tier] = tally([r for r in rows if r["tier"] == tier])
    headline = [r for r in rows if r["tier"] == "primary" and r["value_verified"]]
    by_paper: dict[str, list] = {}
    for r in headline:
        by_paper.setdefault(r["paper_id"], []).append(r)
    papers = {k: sum(any(r[k] for r in g) for g in by_paper.values())
              for k in ("checked", "flagged", "reported")}
    papers["papers"] = len(by_paper)
    false_alarms = [r for r in rows if r["tier"] == "false_alarm"]
    return {"headline_cells": tally(headline), "headline_papers": papers,
            "false_alarms": tally(false_alarms),
            "by_tier": totals, "papers_without_review": missing, "cells": rows}


def select_split(labels: list[dict], labels_path: Path, name: str | None) -> list[dict]:
    """Only the papers of split *name*, from the `splits.json` beside the labels.

    Without a split every labelled paper is scored. A named split that the file
    does not have is an error, not an empty score."""
    if not name:
        return labels
    splits = json.loads((labels_path.parent / "splits.json").read_text())
    if name not in splits:
        raise KeyError(f"no split {name!r} in {labels_path.parent / 'splits.json'}")
    keep = set(splits[name])
    return [p for p in labels if p["paper_id"] in keep]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--labels", type=Path, required=True,
                    help="a set's labels.jsonl, e.g. benchmarks/grim/literature_2026-10/")
    ap.add_argument("--papers-root", type=Path, required=True)
    ap.add_argument("--review", required=True,
                    help="glob for the review directory inside each paper dir")
    ap.add_argument("--json", type=Path, help="write the full result here")
    ap.add_argument("--split", help="score only this split (e.g. dev) from the "
                                    "splits.json beside the labels")
    args = ap.parse_args(argv)
    labels = [json.loads(line) for line in args.labels.read_text().splitlines()
              if line.strip()]
    labels = select_split(labels, args.labels, args.split)
    if args.split:
        print(f"split {args.split}: {len(labels)} papers")
    result = score(labels, args.papers_root, args.review)
    def line(name, t, unit="cells"):
        print(f"{name:26s} {unit} {t[unit]:4d}  checked {t['checked']:4d}  "
              f"flagged {t['flagged']:4d}  reported {t['reported']:4d}")
    line("HEADLINE (primary, verified)", result["headline_cells"])
    line("HEADLINE per paper", result["headline_papers"], "papers")
    if result["false_alarms"]["cells"]:
        line("FALSE ALARMS (tool errors)", result["false_alarms"])
    for tier, t in result["by_tier"].items():
        line(f"  tier {tier}", t)
    if result["papers_without_review"]:
        print(f"NO REVIEW for {len(result['papers_without_review'])} labelled "
              "paper(s): " + ", ".join(result["papers_without_review"]))
    if args.json:
        args.json.write_text(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
