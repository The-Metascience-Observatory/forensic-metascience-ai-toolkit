#!/usr/bin/env python3
"""Litvak's stored per-system findings, in the shape our verifier reads.

His repo keeps the RAW output of every system it tested:
`benchmark/results/<condition>/paper_N_review.json`, each holding an `issues`
list with `category`, `subcategory`, `description`, `quote`, `location` and
`severity`. Measured 2026-08-24: 54 conditions, 8,929 findings, and **zero**
with an empty description -- so re-scoring his systems needs no new collection,
only a field map.

WHY THIS EXISTS. Every comparison in this repo has been asymmetric: only FMA's
findings have been through the grounded verifier, while his published figures
come from one haiku call per finding with no evidence requirement. Putting our
verified number beside his unverified one is not a comparison. This module is
the first half of removing that asymmetry.

His `paper_N_matched.json` is the other half -- it records which planted error
each finding was credited with under HIS protocol, which is what lets a
re-scored row carry both a protocol and a verified column.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

#: His condition suffixes that are not a headline detection run.
NON_HEADLINE = ("_open", "_run2", "_run3")


class ConditionNotFound(RuntimeError):
    """Named condition has no stored findings, with the directory named."""


def results_root(bench: Path) -> Path:
    return Path(bench) / "benchmark" / "results"


def available(bench: Path, include_originals: bool = True) -> list[str]:
    root = results_root(bench)
    if not root.is_dir():
        return []
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if any(d.name.endswith(s) for s in NON_HEADLINE):
            continue
        if not include_originals and d.name.endswith("_originals"):
            continue
        if list(d.glob("paper_*_review.json")):
            out.append(d.name)
    return out


def load_condition(bench: Path, condition: str) -> dict[int, list[dict]]:
    """{paper number: [finding, ...]} for one of his runs.

    Mapped onto the field names our verifier already understands rather than
    teaching the verifier a second vocabulary: `category` -> `technique`,
    `subcategory` -> `slug`. Everything else passes through under its own name.

    NO `title` IS SYNTHESISED. FMA findings carry a crafted one-clause title and
    his do not, and inventing one here -- from the subcategory slug, say --
    would put words in his systems' mouths that they never wrote. The verifier
    is normalised to ignore titles instead (see `score.render_for_verify`), so
    the asymmetry is removed by showing LESS of ours, not more of his.
    """
    d = results_root(bench) / condition
    files = sorted(d.glob("paper_*_review.json"))
    if not files:
        raise ConditionNotFound(
            f"no paper_*_review.json under {d}. Available conditions: "
            + ", ".join(available(Path(bench))[:8]) + " ...")
    out: dict[int, list[dict]] = {}
    for fp in files:
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as exc:                               # noqa: BLE001
            raise ConditionNotFound(f"{fp} is unreadable: {exc}") from exc
        try:
            paper = int("".join(c for c in fp.stem.split("_")[1] if c.isdigit()))
        except (IndexError, ValueError) as exc:
            raise ConditionNotFound(f"no paper number in {fp.name}") from exc
        rows = []
        for i, issue in enumerate(doc.get("issues") or []):
            if not isinstance(issue, dict):
                continue
            rows.append({
                "finding_id": f"{condition}|p{paper}|{i}",
                "technique": issue.get("category"),
                "slug": issue.get("subcategory"),
                "description": issue.get("description") or "",
                "quote": issue.get("quote") or "",
                "location": issue.get("location") or "",
                "severity": issue.get("severity"),
                "outcome": "problem",       # his schema records issues only
            })
        out[paper] = rows
    return out


def load_protocol_matches(bench: Path, condition: str
                          ) -> dict[tuple[int, str], bool]:
    """{(paper, subcategory): matched} under HIS haiku protocol.

    Read from `paper_N_matched.json` so a re-scored row can carry his published
    verdict beside ours, rather than replacing it. The two are different
    claims: his is what the benchmark reports, ours is what survives a grounded
    check.
    """
    d = results_root(bench) / condition
    got: dict[tuple[int, str], bool] = {}
    for fp in sorted(d.glob("paper_*_matched.json")):
        try:
            rows = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:                                      # noqa: BLE001
            continue
        for r in rows:
            gt = r.get("ground_truth") or {}
            if "paper" in gt and "subcategory" in gt:
                got[(int(gt["paper"]), gt["subcategory"])] = bool(r.get("matched"))
    return got


def model_id(bench: Path, condition: str) -> Optional[str]:
    """The model behind a condition, from the run's own metadata.

    His directory names omit versions and two collide on "opus":
    `claude_opus_*` is claude-opus-4-6 and `claude_opus48_*` is claude-opus-4-8.
    Reading `model_id` is how a table avoids mislabelling them.
    """
    for fp in sorted((results_root(bench) / condition).glob("paper_*_review.json")):
        try:
            return json.loads(fp.read_text(encoding="utf-8")).get("model_id")
        except Exception:                                      # noqa: BLE001
            continue
    return None
