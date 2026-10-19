"""Recompute every labelled cell's GRIM arithmetic and stamp it on the label.

A critic's claim is the reason a cell is in this set, not proof that it fails.
Each cell is re-run through the toolkit's own GRIM functions with the premises
the label records (n, k items, printed decimals, integer data), with NO scale
bounds, so only granularity is tested. The result goes in `arithmetic`:

  fails_both          no integer sum works under round-half OR truncation;
                      the tool should flag it (`granularity`)
  fails_rounding_only fails round-half, passes truncation; the tool reports
                      `consistent` / `rounding_convention` BY DESIGN
                      (tools/grim.py, Greg's call 2026-08-10)
  no_power            the check cannot fail at this n and precision
  passes              our arithmetic does not reproduce the critic's claim

A `passes` cell is a label to re-examine (a different n, a typo in
transcription), never a tool miss.

Each cell then gets a `tier`, from the arithmetic and the label's fields:

  false_alarm       `label: false_alarm`: a critic flagged it and the authors
                    explained it; a tool that flags it is wrong
  excluded          premise `not_applicable`, arithmetic passes / no_power, or
                    the value is not printed in the paper (VALUE_CHECK)
  inferred_n        the critic's n is not printed in the paper
  doubtful_premise  the integer premise is the critic's assumption
  rounding_only     fails round-half only (the tool says `rounding_convention`)
  primary           everything else: fails both conventions at a printed n on
                    an integer premise -- what the tool is built to flag

With `--papers-root` (papers at `DIR/<paper_id>/` or `DIR/<subfolder>/<paper_id>/`),
each cell's value is also looked for in its paper's own
text (raw XML text, including tables, and `pdftotext` of the PDF), and
`value_verified` is set when it is found. The headline recall counts only
`primary` cells with `value_verified`: several values were read from a
critic's re-typeset table, not from the paper.

    python benchmarks/grim/verify_labels.py --labels SET/labels.jsonl          # report
    python benchmarks/grim/verify_labels.py --labels SET/labels.jsonl --write  # stamp
    python benchmarks/grim/verify_labels.py --labels SET/labels.jsonl --papers-root DIR --write
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from metascience_agent.tools.grim import (
    _mean_passes_grim,
    _mean_passes_grim_truncation,
    discriminating_power,
)


def classify(cell: dict) -> dict:
    """The two-convention GRIM verdict for one labelled cell."""
    value = float(cell["value"])
    n = int(cell["n"]) * int(cell.get("items_k") or 1)
    decimals = int(cell["decimals"])
    if cell.get("kind", "mean") == "percentage":
        # 100*k/n: test the proportion as a mean of 0/1 data.
        value, decimals = value / 100.0, decimals + 2
    rounds, _ = _mean_passes_grim(value, n, decimals)
    truncates, _ = _mean_passes_grim_truncation(value, n, decimals)
    power = discriminating_power(n, decimals)
    if not power.get("check_can_fail", True):
        verdict = "no_power"
    elif rounds:
        verdict = "passes"
    elif truncates:
        verdict = "fails_rounding_only"
    else:
        verdict = "fails_both"
    return {"verdict": verdict, "n_effective": n, "decimals_tested": decimals,
            # True when truncation would rescue EVERY failing value here; the
            # tool then answers `indeterminate`, not `consistent`.
            "truncation_rescues_everything": bool(
                power.get("rescue_is_an_off_switch"))}


def tier(cell: dict) -> str:
    verdict = (cell.get("arithmetic") or {}).get("verdict")
    if cell.get("label") == "false_alarm":
        # A critic flagged it and the authors' data or answer explained it
        # (e.g. a per-subject average): flagging it is the tool being wrong.
        return "false_alarm"
    if cell.get("premise") == "not_applicable" or verdict in ("passes", "no_power"):
        return "excluded"
    if (cell.get("value_check") or {}).get("outcome") == "not_in_paper":
        return "excluded"
    if cell.get("n_source") != "printed":
        return "inferred_n"
    if cell.get("premise") == "doubtful":
        return "doubtful_premise"
    if verdict == "fails_rounding_only":
        return "rounding_only"
    return "primary"


_MINUS = str.maketrans({"\u2212": "-", "\u2013": "-", "\u2012": "-"})


def paper_text(paper_dir: Path) -> str:
    """All the text the paper's own files carry, tables included."""
    parts = []
    for xml in sorted(paper_dir.glob("*.xml")):
        try:
            parts.append(" ".join(ET.parse(xml).getroot().itertext()))
        except (ET.ParseError, OSError):
            pass
    if shutil.which("pdftotext"):
        for pdf in sorted(paper_dir.glob("*.pdf")):
            try:
                parts.append(subprocess.run(
                    ["pdftotext", "-layout", str(pdf), "-"], capture_output=True,
                    text=True, timeout=120).stdout)
            except (OSError, subprocess.SubprocessError):
                pass
    return " ".join(parts).translate(_MINUS)


def printed(text: str, value: str) -> bool:
    """`value` appears as a number in its own right, not inside a longer one.
    A leading-dot value (".62") also matches "0.62", and vice versa."""
    v = value.translate(_MINUS)
    text = text.translate(_MINUS)
    forms = {v}
    body = v.lstrip("-")
    sign = "-" if v.startswith("-") else ""
    if body.startswith("0."):
        forms.add(sign + body[1:])
    elif body.startswith("."):
        forms.add(sign + "0" + body)
    return any(re.search(r"(?<![\d.])" + re.escape(f) + r"(?!\.?\d)", text)
               for f in forms)


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


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--labels", type=Path, required=True,
                    help="a set's labels.jsonl, e.g. benchmarks/grim/literature_2026-10/")
    ap.add_argument("--write", action="store_true",
                    help="stamp `arithmetic`, `tier` (and `value_verified`) in place")
    ap.add_argument("--papers-root", type=Path,
                    help="DIR/<paper_id>/ holds each paper's PDF/XML")
    args = ap.parse_args(argv)
    papers = load(args.labels)
    counts: dict[str, int] = {}
    verified = {"found": 0, "by_eye": 0, "not_found": 0, "no_paper": 0}
    for paper in papers:
        text = None
        if args.papers_root is not None:
            pdir = paper_dir(args.papers_root, paper["paper_id"])
            text = paper_text(pdir) if pdir.is_dir() else ""
        for cell in paper.get("cells") or []:
            cell["arithmetic"] = classify(cell)
            cell["tier"] = tier(cell)
            counts[cell["tier"]] = counts.get(cell["tier"], 0) + 1
            if cell["arithmetic"]["verdict"] == "passes":
                print(f"RE-EXAMINE {paper['paper_id']} {cell['id']}: "
                      f"{cell['value']} at n={cell['n']} k={cell.get('items_k', 1)} "
                      "passes GRIM as labelled", file=sys.stderr)
            if text is None:
                continue
            if not text:
                verified["no_paper"] += 1
            elif printed(text, str(cell["value"])):
                cell["value_verified"] = True
                cell["value_verified_by"] = "text"
                verified["found"] += 1
            elif (cell.get("value_check") or {}).get("outcome") == "eye":
                # Recorded in build_labels.VALUE_CHECK: present, but the text
                # layer garbles it.
                cell["value_verified"] = True
                cell["value_verified_by"] = "eye"
                verified["by_eye"] += 1
            else:
                cell["value_verified"] = False
                verified["not_found"] += 1
                print(f"NOT IN TEXT {paper['paper_id']} {cell['id']}: "
                      f"{cell['value']} ({cell.get('location')})", file=sys.stderr)
    print(json.dumps(counts, sort_keys=True))
    if args.papers_root is not None:
        print("value check:", json.dumps(verified))
    if args.write:
        args.labels.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n"
                                       for p in papers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
