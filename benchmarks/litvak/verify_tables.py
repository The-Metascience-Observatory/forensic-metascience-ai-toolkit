#!/usr/bin/env python3
"""Did the tables survive the .docx -> PDF conversion? Measure it, don't assume.

    metascience extract-tables <paper_dir>          # once per paper, expensive
    python benchmarks/litvak/verify_tables.py ~/fmt-litvak/original

WHY THIS EXISTS. The whole argument for not using the benchmark's own
`docx_to_pdf.py` is that it flattens tables and FMA's checks live in tables. That
argument is only worth anything if OUR converter actually preserves them -- and
on the first LibreOffice run it did not. Paper 1's correlation table came back
with `RWA` and `WILL` merged into one column, the row labels displaced to the end
of the row, and the Greek alpha as an unmapped private-use glyph. A shifted
column label hands GRIM/GRIMMER a triple the paper never reported.

So the fidelity claim gets measured per paper and recorded, rather than asserted
once in a README and quietly inherited by every number that follows.

THE .docx IS THE GROUND TRUTH here, not merely another reading: `extract_supplement`
reads OOXML directly, resolves merged cells at their anchor, and needs no layout
model at all.

NOTE ON THE CACHE. `extract_text_with_tables` reads the content-hash extraction
cache and does NOT run docling itself. On a cold cache it returns `unreadable:
true` with an error saying so in as many words -- believe it, and run
`metascience extract-tables` first. Reading that empty result as "this paper has
no tables" is exactly the mistake this file is here to prevent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import BenchmarkNotFound, add_bench_arg, resolve_bench  # noqa: E402

from metascience_agent.extraction.pdf import extract_text_with_tables  # noqa: E402
from metascience_agent.extraction.supplements_read import extract_supplement  # noqa: E402


def _rows(table: dict) -> list[list[str]]:
    return [[str(c or "").strip() for c in row] for row in (table.get("data") or [])]


def _n_cells(table: dict) -> int:
    """Non-empty GRID cells, counted the same way on both sides.

    Always from `data`, never from `cells`. The two paths do not agree on what
    `cells` means: the docx path populates a typed list (`{raw, row, row_label,
    col_label}`) that is legitimately EMPTY when nothing parsed as a scalar,
    while the docling PDF path has no `cells` key at all. Counting `cells`
    reported every converted PDF as holding zero while `metascience
    extract-tables` printed "113 table cell(s) available to the review" for the
    same file -- absence read as evidence, inside the tool written to catch it.
    A fidelity comparison needs one metric measured identically on both sides.
    """
    return sum(1 for row in _rows(table) for c in row if c)


def _header_signature(table: dict) -> tuple[str, ...]:
    rows = _rows(table)
    return tuple(c for c in (rows[0] if rows else []) if c)


def _pua(text: str) -> int:
    """Private-use-area glyphs: a symbol font whose mapping did not survive."""
    return sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)


def compare(docx: Path, pdf: Path) -> dict:
    """Three states per table, and only one of them is damage.

    `intact`         -- the docx header row is reproduced, column breaks and all.
    `damaged`        -- a real header exists in the docx and did not survive.
    `not_comparable` -- the docx table has no header row to compare (layout
                        blocks, borderless grids), so this method says nothing
                        about it either way.

    The third state is load-bearing. An earlier version had only pass/fail and
    folded `not_comparable` into failure, so it reported all ten papers damaged
    including two with no .docx tables at all -- a verifier that cries wolf is a
    verifier nobody reads, and it is the same over-counting this harness exists
    to catch.
    """
    truth = extract_supplement(docx).get("tables") or []
    got = extract_text_with_tables(pdf)
    if got.get("unreadable"):
        return {"error": got.get("error") or "unreadable",
                "hint": "run `metascience extract-tables` on the paper directory first"}
    pdf_tables = got.get("tables") or []
    pdf_sigs = [_header_signature(t) for t in pdf_tables]
    pdf_text = " ".join(" ".join(r) for t in pdf_tables for r in _rows(t))

    matched = []
    for t in truth:
        sig = _header_signature(t)
        if not sig:
            matched.append({"header": [], "state": "not_comparable"})
            continue
        # Header text can survive while the COLUMN BREAK is lost -- the damaging
        # case, because the values then land under the wrong label.
        state = ("intact" if sig in pdf_sigs
                 else "damaged")
        matched.append({"header": list(sig), "state": state,
                        "header_text_present": all(h in pdf_text for h in sig)})

    states = [m["state"] for m in matched]
    return {
        "docx_tables": len(truth),
        "docx_cells": sum(_n_cells(t) for t in truth),
        "pdf_tables": len(pdf_tables),
        "pdf_cells": sum(_n_cells(t) for t in pdf_tables),
        "pdf_spurious_tables": max(0, len(pdf_tables) - len(truth)),
        "pua_glyphs_in_pdf_tables": _pua(pdf_text),
        "tables": matched,
        "n_intact": states.count("intact"),
        "n_damaged": states.count("damaged"),
        "n_not_comparable": states.count("not_comparable"),
        "verdict": ("damaged" if "damaged" in states
                    else "intact" if "intact" in states
                    else "not_comparable"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--which", choices=("modified", "original"), default=None,
                    help="Which source set to compare against "
                         "(default: read it from prepare_meta.json)")
    ap.add_argument("--json", type=Path, default=None)
    add_bench_arg(ap)
    a = ap.parse_args()

    try:
        bench = resolve_bench(a.bench)
    except BenchmarkNotFound as exc:
        print(exc, file=sys.stderr)
        return 1

    meta_path = a.run_dir / "prepare_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    which = a.which or meta.get("which") or "modified"
    src_dir = bench / f"{which} papers"
    print(f"comparing : {a.run_dir}")
    print(f"against   : {src_dir}")
    print(f"converter : {meta.get('converter_description', 'unrecorded')}\n")

    out, damaged, unmeasured, uncomparable = {}, [], [], []
    for pd in sorted((p for p in a.run_dir.iterdir() if p.is_dir()),
                     key=lambda p: p.name):
        pdfs = sorted(pd.glob("*.pdf"))
        if not pdfs:
            continue
        n = int(pd.name.replace("litvak", ""))
        docx = src_dir / f"{n}.docx"
        if not docx.is_file():
            continue
        res = compare(docx, pdfs[0])
        out[pd.name] = res
        if "error" in res:
            print(f"  ????  {pd.name}  NOT EXTRACTED -- {res['hint']}")
            unmeasured.append(pd.name)
            continue
        flag = {"damaged": "LOST", "intact": "ok  ",
                "not_comparable": "  ? "}[res["verdict"]]
        if res["verdict"] == "damaged":
            damaged.append(pd.name)
        elif res["verdict"] == "not_comparable":
            uncomparable.append(pd.name)
        print(f"  {flag}  {pd.name}  docx {res['docx_tables']}t/{res['docx_cells']}c"
              f"  ->  pdf {res['pdf_tables']}t/{res['pdf_cells']}c"
              f"   [{res['n_intact']} intact, {res['n_damaged']} damaged,"
              f" {res['n_not_comparable']} not comparable]"
              f"  (+{res['pdf_spurious_tables']} spurious,"
              f" {res['pua_glyphs_in_pdf_tables']} unmapped glyphs)")
        for m in res["tables"]:
            if m["state"] == "damaged":
                where = "column breaks lost" if m.get("header_text_present") \
                    else "column breaks and header text both lost"
                print(f"          {where}: {m['header'][:6]}")

    if a.json:
        a.json.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print()
    if unmeasured:
        print(f"{len(unmeasured)} paper(s) NOT MEASURED (cold extraction cache): "
              f"{', '.join(unmeasured)}")
        print("  Not the same fact as damaged. Run `metascience extract-tables` "
              "on each, then re-run.")
    if uncomparable:
        print(f"{len(uncomparable)} paper(s) NOT COMPARABLE: "
              f"{', '.join(uncomparable)}")
        print("  Their .docx tables carry no header row, so this method says")
        print("  nothing about them either way -- check those by eye.")
    if damaged:
        print(f"{len(damaged)} paper(s) with DAMAGED tables: {', '.join(damaged)}")
        print("  A shifted column label hands GRIM/GRIMMER a triple the paper")
        print("  never reported. A recall number from these is a number about")
        print("  the converter, not about FMA.")
        return 1
    if not unmeasured and not damaged:
        print("No damaged tables found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
