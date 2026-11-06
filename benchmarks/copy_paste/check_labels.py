#!/usr/bin/env python3
"""Recompute every labelled cell of the copy-paste ground truth from its bytes.

    python benchmarks/copy_paste/check_labels.py --root <GT> [--merge labels.jsonl]

<GT>/<tier>/inputs/<paper_id>/<file> holds each paper's verified bytes, and
<GT>/<tier>/labels.jsonl (or labels_draft/*.jsonl) holds its labels. For each
label this checks: source_sha256 matches the local bytes; every cell exists and
is non-empty; and, for an exact-copy kind with a verified status, each cell's
value equals the value of at least one other labelled cell. A failure is
printed and the exit status is 1. --merge writes all checked labels to one
ledger for copy-paste-benchmark.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from functools import lru_cache
from pathlib import Path

EXACT = {"row_pair", "column_sequence", "repeated_value"}
VERIFIED = {"verified_duplication", "confirmed_error"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(maxsize=None)
def book(path):
    import openpyxl

    return openpyxl.load_workbook(path, data_only=True, read_only=False)


@lru_cache(maxsize=None)
def table(path):
    delimiter = "\t" if path.endswith(".tsv") else ","
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle, delimiter=delimiter))


def value(path, sheet, cell):
    if path.suffix.lower() in {".csv", ".tsv"}:
        letters = "".join(ch for ch in cell if ch.isalpha())
        row = int(cell[len(letters) :])
        col = 0
        for ch in letters:
            col = col * 26 + ord(ch.upper()) - 64
        rows = table(str(path))
        try:
            return rows[row - 1][col - 1]
        except IndexError:
            return None
    wb = book(str(path))
    if sheet not in wb.sheetnames:
        raise KeyError(f"no sheet {sheet!r} in {path.name}")
    return wb[sheet][cell].value


def norm(v):
    if v is None or v == "":
        return None
    try:
        # 15 significant digits: a last-digit edit is not an exact copy.
        return float(f"{float(v):.15g}")
    except (TypeError, ValueError):
        return str(v).strip()


def labels_in(tier):
    merged = tier / "labels.jsonl"
    files = [merged] if merged.exists() else sorted((tier / "labels_draft").glob("*.jsonl"))
    for f in files:
        for line in f.read_text().splitlines():
            if line.strip():
                yield f, json.loads(line)


def check(root):
    problems, rows, cells_checked = [], [], 0
    for tier in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        for source, label in labels_in(tier):
            pid = label["paper_id"]
            folder = tier / "inputs" / pid
            for name, digest in label.get("source_sha256", {}).items():
                path = folder / name
                if not path.exists():
                    problems.append(f"{pid}: missing local file {name}")
                elif sha256(path) != digest:
                    problems.append(f"{pid}: sha256 mismatch for {name}")
            for issue in label.get("issues", []):
                seen = []
                for ref in issue.get("cells", []):
                    path = folder / Path(ref["file"]).name
                    if not path.exists():
                        problems.append(f"{pid}/{issue['id']}: no file {ref['file']}")
                        continue
                    try:
                        v = norm(value(path, ref.get("sheet"), ref["cell"]))
                    except (KeyError, ValueError) as exc:
                        problems.append(f"{pid}/{issue['id']}: {ref} unreadable: {exc}")
                        continue
                    cells_checked += 1
                    if v is None:
                        problems.append(f"{pid}/{issue['id']}: {ref['cell']} is empty")
                    seen.append((ref["cell"], v))
                exact = issue["kind"] in EXACT and issue.get("verification_status") in VERIFIED
                if exact:
                    values = [v for _, v in seen]
                    lonely = [c for c, v in seen if v is not None and values.count(v) < 2]
                    if lonely:
                        problems.append(
                            f"{pid}/{issue['id']}: cells equal to no other labelled cell: {lonely}"
                        )
            rows.append({**label, "tier": tier.name})
    return rows, problems, cells_checked


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--merge", type=Path)
    args = parser.parse_args(argv)
    rows, problems, cells_checked = check(args.root)
    for p in problems:
        print("FAIL", p)
    issues = sum(len(r.get("issues", [])) for r in rows)
    print(
        json.dumps(
            {
                "labels": len(rows),
                "issues": issues,
                "cells_checked": cells_checked,
                "failures": len(problems),
            }
        )
    )
    if args.merge and not problems:
        args.merge.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
