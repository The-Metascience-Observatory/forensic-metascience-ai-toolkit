"""Generate score.py labels for a corpus split from the corpus manifest.

The working-set labels (labels_working_set.jsonl) were written by hand after
reading the papers. The EVALUATION set is held out, so its labels are derived
mechanically from each tier A/B row's documented `erroneous` string, never from
looking at a run's output:

  stat    every "t(df) = x, p REL y" / "F(a, b) = x, p ..." pair -> keys [[x], [y]]
  ci      every "(lo-hi) ... p = y" / "lo to hi" interval        -> keys [[lo], [hi]]
  counts  the printed p plus the first a/b count                 -> keys [[p], [a/b]]
  other   the first two decimals in the string                   -> keys [[d1], [d2]]

    python benchmarks/pvalue/make_labels.py CORPUS_DIR --split evaluation_test_set \
        --out benchmarks/pvalue/labels_evaluation_set.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

STAT = re.compile(
    r"(?P<k>\bt|\bF|\br|χ2|chi2)\s*(?:\(\s*\d+(?:\.\d+)?\s*(?:,\s*\d+(?:\.\d+)?)?\s*\)|\d+,\d+|\d+)?"
    r"\s*=\s*(?P<v>[-−–]?\s*\d*\.?\d+)\s*[,;]?\s*[pP]\s*[<>=]\s*(?P<p>\d*\.\d+)")
CI = re.compile(r"\(\s*(?:95% CI\s*)?(?P<lo>-?\d*\.\d+)\s*(?:-|–|to|,|;)\s*(?P<hi>-?\d*\.\d+)\s*\)")
P = re.compile(r"[pP]\s*[<>=]\s*(\d*\.\d+)")
COUNT = re.compile(r"\b\d+\s*/\s*\d+\b")
DEC = re.compile(r"-?\d*\.\d+")


def folder_names(split_dir: Path) -> dict[str, str]:
    """doi (lowercase, '/' -> '--') -> the folder fetchpdf2 actually made."""
    return {p.name.lower(): p.name for p in split_dir.iterdir() if p.is_dir() and p.name.startswith("10.")}


def labels_for(row: dict, folder: str) -> list[dict]:
    e = row["erroneous"].replace("−", "-").replace("–", "-").replace("χ2", "chi2")
    ct = row["check_type"].split("|")[0]
    base = {"paper_id": folder, "tier": row["tier"], "doi": row["doi"]}
    out = []
    if ct == "test_statistic_to_p":
        for j, m in enumerate(STAT.finditer(e)):
            v = m.group("v").replace(" ", "").lstrip("-")
            out.append({**base, "id": f"{folder}:{j}", "kind": "stat", "raw": m.group(0),
                        "value": v, "keys": [[v], [m.group("p")]]})
    elif ct == "ci_to_p":
        for j, m in enumerate(CI.finditer(e)):
            out.append({**base, "id": f"{folder}:{j}", "kind": "ci", "raw": m.group(0),
                        "value": m.group("hi"), "keys": [[m.group("lo")], [m.group("hi")]]})
    elif ct == "counts_to_p":
        p, c = P.search(e), COUNT.search(e)
        if p and c:
            out.append({**base, "id": f"{folder}:0", "kind": "counts", "raw": e[:80],
                        "value": p.group(1), "keys": [[p.group(1)], [c.group(0).replace(" ", "")]]})
    if not out:  # anything else: the first two decimals the documented string prints
        d = DEC.findall(e)
        if len(d) >= 2:
            out.append({**base, "id": f"{folder}:0", "kind": "other", "raw": e[:80],
                        "value": d[0].lstrip("-"), "keys": [[d[0].lstrip("-")], [d[1].lstrip("-")]]})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--split", default="evaluation_test_set")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    folders = folder_names(a.corpus / a.split)
    rows, missing = [], []
    for r in csv.DictReader((a.corpus / "manifest.csv").open(encoding="utf-8")):
        if r.get("split") != a.split or r["tier"] not in ("A", "B"):
            continue
        key = r["doi"].lower().replace("/", "--")
        if key not in folders:
            missing.append(r["doi"])
            continue
        got = labels_for(r, folders[key])
        if not got:
            missing.append(r["doi"])
        rows.extend(got)
    a.out.write_text("".join(json.dumps(x) + "\n" for x in rows))
    print(f"{len(rows)} labels for {len({x['paper_id'] for x in rows})} papers -> {a.out}")
    if missing:
        print(f"no label derivable for {len(missing)}: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
