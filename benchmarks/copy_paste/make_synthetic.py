#!/usr/bin/env python3
"""Write the frozen synthetic tier of the copy-paste ground truth.

    python benchmarks/copy_paste/make_synthetic.py --output <GT>/synthetic

Jobs 00-15 are the 2026-09-10 engineering fixtures (seed 20260910) from the
deleted examples/evaluate_copy_paste.py, unchanged, so their bytes and cells
match EVALUATION.md. Jobs 16-21 add one positive control per issue kind the
real-paper tiers contain, including the two kinds exact matching cannot see
(near-duplicate edits, misassigned joins), and a low-precision negative where
chance ties are expected. Labels follow benchmarks/copy_paste/README.md.
Synthetic jobs are development checks; they never count as real-paper families.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from openpyxl import Workbook

SEED = 20260910
HEADER = ["participant_id", "mass_mg", "cortisol_nmol"]
INDEPENDENT = (
    "Each participant_id identifies a different participant. mass_mg and cortisol_nmol "
    "are independently measured continuous outcomes, recorded once per participant "
    "with six decimal places. There are no shared controls or repeated measurements."
)


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".xlsx":
        book = Workbook()
        for row in rows:
            book.active.append(row)
        book.save(path)
    else:
        with path.open("w", newline="") as handle:
            csv.writer(handle).writerows(rows)


def sha256(path):
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def col(index):
    out = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def ref(name, row_index, col_index):
    """Detector convention: the sheet of a CSV is its file name; row 1 is the header."""
    return {"file": name, "sheet": name, "cell": f"{col(col_index)}{row_index + 1}"}


def random_rows(rng, ids):
    return [HEADER] + [
        [j, round(rng.uniform(100, 900), 6), round(rng.uniform(100, 900), 6)] for j in ids
    ]


def engineering_fixtures(root):
    """The sixteen 2026-09-10 fixtures, byte-for-byte the original generator."""
    rng = random.Random(SEED)
    out = []
    for i in range(16):
        paper = root / "inputs" / f"fixture-{i:02}"
        path = paper / ("data.xlsx" if i == 12 else "data.csv")
        rows = random_rows(rng, range(1, 601))
        files, affected = [path], []
        if i < 8 or i in (12, 15):
            rows[500][1:] = rows[5][1:]
            affected = [(path.name, c) for c in ("B6", "C6", "B501", "C501")]
        if i == 12:
            rows = [r[:1] + [1] * 100 + r[1:] for r in rows]
            rows[0] = (
                ["participant_id"]
                + [f"constant_{k}" for k in range(100)]
                + ["mass_mg", "cortisol_nmol"]
            )
            affected = [(path.name, c) for c in ("CX6", "CY6", "CX501", "CY501")]
        if i == 13:
            rows[500:505] = [[j] + rows[5 + j - 500][1:] for j in range(500, 505)]
            affected = [(path.name, c) for c in ("B6", "C6", "B501", "C501")]
        if i == 14:
            other = random_rows(rng, range(1001, 1601))
            other[500][1:] = rows[5][1:]
            files.append(paper / "other.csv")
            write_rows(files[-1], other)
            affected = [
                ("data.csv", "B6"),
                ("data.csv", "C6"),
                ("other.csv", "B501"),
                ("other.csv", "C501"),
            ]
        if i == 15:
            rows[500][0] = rows[5][0]
        write_rows(path, rows)
        context = (
            INDEPENDENT
            if i != 15
            else (
                "This is a longitudinal export. Participant 5 has two visits; the baseline "
                "mass_mg and cortisol_nmol were deliberately copied onto both visit rows. "
                "These are the same baseline observation, not two independently measured "
                "outcomes. All other participants have one visit."
            )
        )
        sheet = {"data.xlsx": "Sheet"}
        cells = [{"file": f, "sheet": sheet.get(f, f), "cell": c} for f, c in affected]
        if i == 15:
            issues = [
                issue(
                    "legitimate-repeat-15",
                    "row_pair",
                    ["row_pair"],
                    "legitimate_repetition",
                    cells,
                    "Baseline visit deliberately copied onto a second visit row (README says so).",
                )
            ]
        elif cells:
            issues = [
                issue(
                    f"planted-{i}",
                    "row_pair",
                    ["row_pair"],
                    "verified_duplication",
                    cells,
                    "Planted exact copy of a participant's two outcome values.",
                )
            ]
        else:
            issues = []
        out.append((f"fixture-{i:02}", files, context, issues))
    return out


def issue(id_, kind, detector_kinds, status, cells, explanation):
    return {
        "id": id_,
        "kind": kind,
        "detector_kinds": detector_kinds,
        "verification_status": status,
        "evidence_url": "synthetic:benchmarks/copy_paste/make_synthetic.py",
        "cells": cells,
        "reviewer": "synthetic",
        "verified_at": "2026-11-06",
        "explanation": explanation,
    }


def kind_fixtures(root):
    """One positive control per issue kind, plus a chance-tie negative."""
    rng = random.Random(SEED + 1)
    out = []

    def job(name):
        return root / "inputs" / name / "data.csv"

    # 16: a run of 6 consecutive mass values pasted lower in the same column.
    path, rows = job("fixture-16"), random_rows(rng, range(1, 401))
    for k in range(6):
        rows[300 + k][1] = rows[40 + k][1]
    cells = [ref(path.name, r, 1) for r in [*range(40, 46), *range(300, 306)]]
    write_rows(path, rows)
    out.append(
        (
            "fixture-16",
            [path],
            INDEPENDENT,
            [
                issue(
                    "planted-sequence-16",
                    "column_sequence",
                    ["column_sequence"],
                    "verified_duplication",
                    cells,
                    "Rows 41-46 of mass_mg pasted, in order, into rows 301-306.",
                )
            ],
        )
    )

    # 17: one high-precision value recurring in four unrelated rows and both columns.
    path, rows = job("fixture-17"), random_rows(rng, range(1, 401))
    value = rows[77][2]
    spots = [(77, 2), (130, 1), (222, 2), (351, 1)]
    for r, c in spots:
        rows[r][c] = value
    write_rows(path, rows)
    out.append(
        (
            "fixture-17",
            [path],
            INDEPENDENT,
            [
                issue(
                    "planted-repeat-17",
                    "repeated_value",
                    ["repeated_value"],
                    "verified_duplication",
                    [ref(path.name, r, c) for r, c in spots],
                    f"The six-decimal value {value} recurs in four unrelated cells.",
                )
            ],
        )
    )

    # 18: rows copied with every value nudged in its last digits (Data Colada style).
    path, rows = job("fixture-18"), random_rows(rng, range(1, 401))
    cells = []
    for k in range(5):
        src, dst = 20 + k, 200 + k
        rows[dst][1:] = [
            round(v + rng.choice([-1, 1]) * rng.randint(1, 9) * 1e-6, 6) for v in rows[src][1:]
        ]
        cells += [ref(path.name, r, c) for r in (src, dst) for c in (1, 2)]
    write_rows(path, rows)
    out.append(
        (
            "fixture-18",
            [path],
            INDEPENDENT,
            [
                issue(
                    "planted-near-duplicate-18",
                    "near_duplicate_edit",
                    [],
                    "verified_duplication",
                    cells,
                    "Rows 21-25 copied to rows 201-205 with each value altered by 1-9e-6.",
                )
            ],
        )
    )

    # 19: a misaligned join, each subject's body length on all four of its trial rows,
    # assigned to the wrong subject (clonal-fish style).
    path = job("fixture-19")
    lengths = [round(rng.uniform(20, 40), 6) for _ in range(100)]
    rows = [["fish_id", "trial", "standard_length_mm", "activity"]]
    for fish in range(100):
        for trial in range(4):
            rows.append(
                [fish + 1, trial + 1, lengths[(fish + 37) % 100], round(rng.uniform(0, 1), 6)]
            )
    write_rows(path, rows)
    out.append(
        (
            "fixture-19",
            [path],
            "Four trials per fish; standard_length_mm was measured once per fish and joined "
            "onto its trial rows. activity is measured per trial.",
            [
                issue(
                    "planted-misassignment-19",
                    "misassignment",
                    [],
                    "verified_duplication",
                    [ref(path.name, r, 2) for r in range(1, 9)],
                    "Lengths were joined with a 37-fish offset: every fish carries another fish's "
                    "length. Repeats within a fish are legitimate; the assignment is wrong. "
                    "Cells list the first two fish only.",
                )
            ],
        )
    )

    # 20: an exact block of 4 whole rows copied (row pairs and runs both apply).
    path, rows = job("fixture-20"), random_rows(rng, range(1, 401))
    for k in range(4):
        rows[350 + k][1:] = rows[100 + k][1:]
    cells = [ref(path.name, r, c) for r in [*range(100, 104), *range(350, 354)] for c in (1, 2)]
    write_rows(path, rows)
    out.append(
        (
            "fixture-20",
            [path],
            INDEPENDENT,
            [
                issue(
                    "planted-block-20",
                    "row_pair",
                    ["row_pair", "column_sequence"],
                    "verified_duplication",
                    cells,
                    "Rows 101-104 copied whole into rows 351-354.",
                )
            ],
        )
    )

    # 21: honest low-precision data; ties are expected by chance and are not issues.
    path = job("fixture-21")
    rows = [["plot", "seedlings", "height_cm", "leaf_count"]]
    rows += [
        [j, rng.randint(0, 20), round(rng.gauss(12, 3), 1), rng.randint(2, 9)]
        for j in range(1, 501)
    ]
    write_rows(path, rows)
    out.append(
        (
            "fixture-21",
            [path],
            "Field plots counted once each. Counts and one-decimal heights; repeated values "
            "are expected by chance.",
            [],
        )
    )
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    root = parser.parse_args(argv).output
    jobs, labels = [], []
    for paper_id, files, context, issues in engineering_fixtures(root) + kind_fixtures(root):
        readme = files[0].parent / "README.txt"
        readme.write_text(context)
        jobs.append(
            {
                "paper_id": paper_id,
                "files": [str(p) for p in files],
                "context_files": [str(readme)],
                "data_context": "raw_participant_level",
            }
        )
        status = (
            "verified_negative"
            if not issues
            or all(i["verification_status"] == "legitimate_repetition" for i in issues)
            else "verified_duplication"
        )
        labels.append(
            {
                "paper_id": paper_id,
                "family_id": paper_id,
                "split": "synthetic_development",
                "source_sha256": {p.name: sha256(p) for p in files},
                "verification_status": status,
                "issues": issues,
            }
        )
    (root / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in jobs))
    (root / "labels.jsonl").write_text("".join(json.dumps(r) + "\n" for r in labels))
    print(json.dumps({"jobs": len(jobs), "issues": sum(len(r["issues"]) for r in labels)}))


if __name__ == "__main__":
    main()
