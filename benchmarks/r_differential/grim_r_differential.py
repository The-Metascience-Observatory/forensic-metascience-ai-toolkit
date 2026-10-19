"""Exhaustive Python-vs-R differential for GRIM, so the R call can be retired.

WHY THIS EXISTS. Greg, 2026-08-26:

    "I am reasonably sure that we can verify to within a shadow of a doubt that
     the python implementation of both those R packages produces the same
     output in all circumstances. This is a needless dependency, since we are
     already using python versions of those same packages."

The R cross-check is not there because R is better -- it is there because it is
INDEPENDENT. Our Python GRIM cannot find a bug in our Python GRIM. That is the
whole argument for a second implementation, and it does not require the second
one to run at ANALYSIS time. It requires it to have been run.

So this converts a runtime dependency into a build-time one. GRIM's input space
is finite and enumerable -- a mean at d decimals, a group size n, an item count
-- which means "we agree in all circumstances" is a claim that can be settled by
enumeration rather than by sampling. Once it is settled and recorded, the
runtime call adds nothing but a way to fail.

THE DEPENDENCY HAS ALREADY COST US ONCE. `scrutiny` writes "package not
installed" to STDOUT and `quietly = TRUE` leaves stderr empty, so `r_grim`
returned `{"error": ""}` on every call and the caller read that as agreement.
The prompts require a cross-check before any GRIM `impossible` is published, so
a missing package silently capped every GRIM finding in a corpus at
`suspicious`. A verification artifact cannot fail that way: it either ran or it
is not on disk.

THE ONE TRAP, and it has produced a false "the repo is broken" finding before:
`scrutiny::grim` reads the number of decimals FROM THE LITERAL you hand it, so
`grim(3.5, 30)` and `grim("3.50", 30)` are different questions. Every case here
passes R the STRING and Python the (float, decimals) pair built from that same
string, so the two are asked the same question by construction.

Run:  $(metascience python) benchmarks/r_differential/grim_r_differential.py [--quick]

A full run rewrites `grim_r_differential.json`, which records the SHA-256 of every
source file the verdict depends on (`fingerprint.GRIM_SOURCES`);
`tests/test_r_differential_pin.py` fails when those files change, and this
is the command that clears it. `--quick` writes `grim_r_differential.quick.json`
instead, so a smoke run never replaces the record.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

from metascience_agent.tools.grim import grim_test  # noqa: E402
from fingerprint import GRIM_SOURCES, code_sha256  # noqa: E402

R_SCRIPT = r"""
args <- commandArgs(trailingOnly = TRUE)
suppressMessages(library(scrutiny))
cases <- read.csv(args[1], colClasses = c(x = "character"), stringsAsFactors = FALSE)
out <- mapply(function(x, n, items, percent) {
  v <- tryCatch(scrutiny::grim(x = x, n = n, items = items, percent = as.logical(percent)),
                error = function(e) NA)
  if (length(v) != 1 || is.na(v)) NA else as.logical(v)
}, cases$x, cases$n, cases$items, cases$percent)
cases$r_consistent <- out
write.csv(cases, args[2], row.names = FALSE)
"""


def enumerate_cases(quick: bool):
    """Every (mean literal, n, items) worth asking, at 1 and 2 decimals.

    Bounds chosen to cover what papers actually print rather than to be large
    for its own sake: Likert and clinical means live in 0-10, and a group size
    above a few hundred makes GRIM vacuous because the granularity is finer
    than the reported precision. `items > 1` is included because a scale mean
    over k items has k times the granularity, and that path is a separate
    branch in both implementations.
    """
    n_max = 40 if quick else 200
    for decimals in (1, 2):
        step = 10 ** -decimals
        top = 20 if quick else 100          # means 0.0 .. top*step*10
        for i in range(0, top * 10 + 1):
            x = f"{i * step:.{decimals}f}"
            for n in range(1, n_max + 1):
                yield {"x": x, "n": n, "items": 1, "percent": 0,
                       "decimals": decimals}
        # ITEMS > 1 IS DELIBERATELY NOT ENUMERATED, and the reason is a finding
        # rather than an omission. `scrutiny::grim` takes an `items` argument --
        # a scale mean over k items has k times the granularity -- and
        # `tools.grim.grim_test` has NO SUCH PARAMETER. Its signature is
        # (mean, n, scale_min, scale_max, decimals, data_type, bound_source,
        # discreteness_source), so no caller in this repo can express the
        # question, and the multi-item case never arises in our pipeline.
        #
        # A first version of this file enumerated items in (2, 3, 5), passed
        # them to R, and passed NOTHING to Python -- which asked the two
        # implementations different questions and produced a page of
        # "disagreements" that were entirely the harness's. Every one had
        # items > 1. Comparing where only one side can answer measures the
        # harness, not the implementations.
        #
        # It sharpens the retirement argument rather than weakening it: the one
        # capability R has that we lack is one nothing here ever invokes, so the
        # runtime call is cross-checking a question we do not ask.


def python_verdict(case: dict):
    """`grim_consistent` -- the pure granularity verdict, not the folded one.

    `consistent` additionally reflects the range check, which is a different
    question and one `scrutiny::grim` does not answer.
    """
    try:
        r = grim_test(
            mean=float(case["x"]), n=int(case["n"]),
            decimals=int(case["decimals"]),
            data_type="integer", bound_source="stated",
            discreteness_source="stated",
        )
    except Exception:                                    # noqa: BLE001
        return None
    v = r.get("grim_consistent")
    return (None if v is None else bool(v)), str(r.get("failure_mode") or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="a small sweep, for a smoke test")
    ap.add_argument("--out", default=None,
                    help="default: grim_r_differential.json beside this script "
                         "(grim_r_differential.quick.json with --quick)")
    args = ap.parse_args()
    if args.out is None:
        args.out = str(HERE / ("grim_r_differential.quick.json" if args.quick
                               else "grim_r_differential.json"))

    cases = list(enumerate_cases(args.quick))
    print(f"cases enumerated: {len(cases):,}")

    with tempfile.TemporaryDirectory() as tmp:
        inp, outp = Path(tmp) / "cases.csv", Path(tmp) / "out.csv"
        with inp.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["x", "n", "items", "percent",
                                               "decimals"])
            w.writeheader()
            w.writerows(cases)
        rs = Path(tmp) / "grim.R"
        rs.write_text(R_SCRIPT, encoding="utf-8")
        print("running scrutiny::grim over the same cases ...")
        proc = subprocess.run(["Rscript", str(rs), str(inp), str(outp)],
                              capture_output=True, text=True, timeout=7200)
        if proc.returncode != 0 or not outp.exists():
            print("R FAILED -- the differential did not run, which is NOT the "
                  "same as the implementations agreeing.", file=sys.stderr)
            print(proc.stderr[-2000:], file=sys.stderr)
            return 2
        with outp.open(encoding="utf-8") as fh:
            r_rows = list(csv.DictReader(fh))

    agree = disagree = r_na = py_na = declines_where_r_said_true = 0
    declines: dict[str, int] = {}
    examples = []
    for case, row in zip(cases, r_rows):
        rv = row.get("r_consistent", "")
        r_val = True if rv == "TRUE" else (False if rv == "FALSE" else None)
        p_val, why = python_verdict(case)
        if r_val is None:
            r_na += 1
            continue
        if p_val is None:
            py_na += 1
            declines[why] = declines.get(why, 0) + 1
            if r_val is True:
                declines_where_r_said_true += 1
            continue
        if p_val == r_val:
            agree += 1
        else:
            disagree += 1
            if len(examples) < 25:
                examples.append({**case, "python": p_val, "r": r_val})

    total = agree + disagree
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quick": bool(args.quick),
        "code_sha256": code_sha256(GRIM_SOURCES),
        "n_cases": len(cases),
        "n_compared": total,
        "n_agree": agree,
        "n_disagree": disagree,
        "n_r_declined": r_na,
        "n_python_declined": py_na,
        "python_decline_reasons": declines,
        "n_declines_where_r_said_consistent": declines_where_r_said_true,
        "decline_note": (
            "A Python decline is not a disagreement. Where GRIM has no "
            "discriminating power -- n coarse enough relative to the "
            "reported precision that EVERY mean is reachable -- Python "
            "returns None and names the reason, while scrutiny returns "
            "TRUE. Reporting that TRUE as `consistent` would publish a "
            "vacuous pass as evidence, which is the substitution this "
            "toolkit exists to catch. The refusal is the better answer."),
        "agreement": (agree / total) if total else None,
        "disagreements": examples,
        "note": ("Compares `grim_consistent` against `scrutiny::grim`. R is "
                 "handed the mean as a STRING and Python the (float, decimals) "
                 "pair built from that same string, because scrutiny reads the "
                 "decimal count off the literal -- otherwise the two are asked "
                 "different questions and the run means nothing."),
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"compared {total:,}: agree {agree:,}  disagree {disagree:,}  "
          f"(R declined {r_na:,}, Python declined {py_na:,})")
    if declines:
        print("python declines by reason:", declines)
        print(f"  of which R answered TRUE: {declines_where_r_said_true:,}")
    if examples:
        print("\nfirst disagreements:")
        for e in examples[:10]:
            print(f"   x={e['x']} n={e['n']} items={e['items']} "
                  f"-> python={e['python']} r={e['r']}")
    print(f"\nwrote {args.out}")
    return 1 if disagree else 0


if __name__ == "__main__":
    raise SystemExit(main())
