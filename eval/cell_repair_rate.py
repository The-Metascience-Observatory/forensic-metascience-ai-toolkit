#!/usr/bin/env python3
"""How often does extraction damage a table CELL? (#152)

WHY THIS EXISTS. The benchmark that chose the extractor is blind to this. It
scores recall over DISTINCT NUMERIC LITERALS, so a cell reading "100 100" scores
a perfect hit because "100" is present -- and 10.3390--healthcare11101497 scores
100% recall while its Table 2 is visibly mangled. Every metric in the acquisition
spec's section 2 has the same blind spot: duplication, cross-column merges and
values landing in the wrong row are all invisible to it.

Before building a Stage 0 repair agent, #152 says to measure how much there is
to repair, and specifically whether it is one publisher's PDFs.

TWO DEFECTS, DELIBERATELY COUNTED SEPARATELY, because they call for different
repairs and merging them would justify the wrong build:

  duplicated   the SAME content repeated -- "Sample size Sample size", "100 100",
               "1050 EUR 93 1050 EUR" (a doubling with a neighbour's 93 caught
               in the middle). Repair: de-duplicate.
  merged       DISTINCT content from adjacent columns run together --
               "Upper threshold (95%) Lower threshold (95%)". Repair: split.
               This is NOT duplication, and an early version of this script
               scored it as such because a repeated token run matched.

MEASURED 2026-08-18 over the 23 cached extractions in this repository:
  9,381 cells, 19 exactly doubled (0.20%), concentrated in ONE MDPI paper at
  12.2% of its 41 cells; 9 of 13 papers with cells had none at all.

READ THE NUMBER AS AN UPPER BOUND, NOT A RATE, and this is the substantive
finding rather than a caveat. Three separate attempts to detect the defect
automatically each produced false positives that had to be caught by eye:

  `14 : 14`                       a RATIO, not a doubled 14
  `<.001 <.001`                   genuinely ambiguous -- one cell doubled, or
                                  two adjacent cells that both really say <.001
                                  and were merged? The cell cannot say.
  `Upper threshold (95%) Lower    two DISTINCT headers run together. A repeated
   threshold (95%)`               token run matches it; it is not duplication
                                  and its repair is a split, not a de-dup.

AND THE ONE MECHANICAL DISCRIMINATOR IS UNAVAILABLE. If a row held fewer cells
than its header declares, a merge would be visible from the grid's shape alone.
Measured across all 17 table sets in the cache: ZERO ragged rows. Docling emits
perfectly rectangular grids, so a merged cell leaves no structural trace, and
whether `100 100` is one damaged cell or two intact ones cannot be decided from
the extraction at all -- only from the page.

That is the argument #152 makes, arriving as a measurement: the discrimination
needs judgement because no rule in the data can make it. It is also the argument
for deliverable 1b (cell-level ground truth) BEFORE any further claim about
extraction QUALITY as opposed to coverage -- including any claim built on the
number at the top of this docstring.

Point it at the Zotero stress corpus (~/fmt-zotero-stress) for a sample chosen
for format diversity rather than convenience; 13 papers is far too few either
way.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def tokens(cell: str) -> list[str]:
    return " ".join((cell or "").split()).split(" ") if (cell or "").strip() else []


def is_duplicated(toks: list[str]) -> str | None:
    """The same content twice. Returns the repeated unit, or None.

    Covers the clean form (`X X`) and the interrupted form (`X 93 X`), which is
    what a doubling merged with a neighbouring column looks like. Requires the
    repeated unit to be IDENTICAL, which is what separates this from `merged`.
    """
    n = len(toks)
    if n < 2:
        return None
    if n % 2 == 0 and toks[:n // 2] == toks[n // 2:]:
        return " ".join(toks[:n // 2])
    # interrupted: a leading run that reappears later, covering most of the cell
    for L in range(n // 2, 0, -1):
        run = toks[:L]
        for j in range(L, n - L + 1):
            if toks[j:j + L] == run and 2 * L >= 0.6 * n:
                return " ".join(run)
    return None


def scan(paths: list[Path]) -> dict:
    per: dict[str, dict] = {}
    examples: list[tuple[str, str, str]] = []
    for c in paths:
        try:
            d = json.loads(c.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        name = c.parent.parent.name
        row = per.setdefault(name, {"cells": 0, "duplicated": 0})
        for t in (d.get("tables") or []):
            for r in (t.get("data") or []):
                for cell in (r or []):
                    if not isinstance(cell, str):
                        continue
                    tk = tokens(cell)
                    if not tk:
                        continue
                    row["cells"] += 1
                    unit = is_duplicated(tk)
                    if unit:
                        row["duplicated"] += 1
                        if len(examples) < 25:
                            examples.append((name, cell[:70], unit[:40]))
    cells = sum(v["cells"] for v in per.values())
    dup = sum(v["duplicated"] for v in per.values())
    return {"papers": per, "n_cells": cells, "n_duplicated": dup,
            "rate": (dup / cells) if cells else None, "examples": examples}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", nargs="*", default=["."],
                    help="directories to scan for *.tables.json")
    ap.add_argument("--json", type=Path, help="write the full result")
    a = ap.parse_args(argv)

    paths: list[Path] = []
    for r in a.root:
        # `find`-style walk that skips .git: rglob into a git-lfs object store
        # exhausted memory on this machine while docling was running.
        for p in Path(r).rglob("*.tables.json"):
            if ".git" not in p.parts:
                paths.append(p)
    if not paths:
        print("no extraction caches found", file=sys.stderr)
        return 1

    res = scan(paths)
    print(f"caches {len(paths)}  papers {len(res['papers'])}  "
          f"cells {res['n_cells']}")
    print(f"DUPLICATED {res['n_duplicated']} "
          f"({100 * (res['rate'] or 0):.2f}% of cells)")
    print("\nper paper, worst first:")
    for name, v in sorted(res["papers"].items(),
                          key=lambda kv: -kv[1]["duplicated"])[:15]:
        if v["cells"]:
            print(f"  {v['duplicated']:4d}/{v['cells']:6d} "
                  f"({100 * v['duplicated'] / v['cells']:5.1f}%)  {name[:52]}")
    if res["examples"]:
        print("\nexamples:")
        for name, cell, unit in res["examples"][:12]:
            print(f"  {name[:28]:30} {cell!r}")
    if a.json:
        a.json.write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
