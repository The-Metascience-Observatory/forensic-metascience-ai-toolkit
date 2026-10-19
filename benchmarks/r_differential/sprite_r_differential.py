"""Exhaustive Python-vs-R differential for SPRITE's FEASIBILITY verdict.

The companion to `grim_r_differential.py`, and the reason the R calls cannot be
retired on that one alone: removing `r_grim_ground_truth` while
`r_sprite_ground_truth` is unverified removes half a guarantee.

WHAT IS AND IS NOT COMPARABLE HERE. SPRITE's reconstruction is a stochastic
search, so two implementations will not return the same distributions and there
is nothing to diff. But `sprite_reconstruct` distinguishes four outcomes and
**only `no_solution_proven` is evidence** -- it comes from the analytic
integer/parity constraint, not from a search giving up. That verdict is
deterministic, and it is exactly the one an accusation may rest on. So this
compares FEASIBILITY, which is the whole evidentiary surface, and ignores the
sampling, which is not.

rsprite2 signals infeasibility by RAISING from `set_parameters`, with distinct
messages for the two reasons -- "the standard deviation is outside the possible
range" and "fails GRIMMER test". Both are proofs, so both map to
`no_solution_proven`, and the R side records which so a disagreement can be read
rather than merely counted.

THE PRECISION TRAP, which has produced a false "the repo is broken" finding
before: rsprite2 INFERS decimals from the literal unless told, so `mean = 4.0`
reads as 0 decimals. Every case here pins `m_prec` and `sd_prec` explicitly and
passes Python the same `decimals_mean` / `decimals_sd`, so the two are asked the
same question by construction.

THE RESULT, AFTER TWO WRONG READINGS OF IT. These are the 2026-08-26 figures;
the current ones are in `sprite_r_differential.json`, whose `regions` block now
splits every run the same way. Re-run 2026-10-18 with a two-decimal grid
added: in power 25,015 compared, 0 disagreements; outside it 182 of 53,469,
still every one `python=feasible, r=impossible` -- the gap below is not closed.

    IN THE RANGE WHERE THE TEST HAS POWER:  9,211 compared, 9,211 agree, ZERO
    disagreements. (A separate hand-run sweep, since replaced by the
    `regions.in_power` block of `sprite_r_differential.json`.)

    OUTSIDE IT: 217 disagreements over 59,051 cases, every one
    `python=feasible, r=impossible`.

The second number is not a finding about either implementation. rsprite2 warns
that GRIM and GRIMMER are meaningful only when N < 10^precision -- N < 10 for a
mean at one decimal -- and this file's first sweep used `m_prec=1` with n from 4
to 60, so **217 of 217 disagreements sat outside that range**. Two engines were
being compared on a question neither should answer.

WHAT IT DOES SAY, AND IT IS ABOUT US. `grim_test` already declines where the
test has no discriminating power, returning None and naming the reason;
`sprite_reconstruct` does not, and returns `found` in the same region. That is
the gap worth closing, and closing it would take all 217 to zero by refusal
rather than by agreement -- which is the honest way for them to go.

Greg, 2026-08-26, on the reading this replaces: "it seems impossible that our
tool that used the R package as the canonical implementation of the SPRITE
concept would return inferior results." Right, and the inverse claim was equally
implausible for the same reason. Where the question is meaningful they agree
exactly, which is what two correct implementations of one algorithm should do.

Run:  $(metascience python) benchmarks/r_differential/sprite_r_differential.py [--quick]

A full run rewrites `sprite_r_differential.json`, which records the SHA-256 of every
source file the verdict depends on (`fingerprint.SPRITE_SOURCES`);
`tests/test_r_differential_pin.py` fails when those files change, and this
is the command that clears it. `--quick` writes `sprite_r_differential.quick.json`
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

from metascience_agent.tools.sprite import sprite_reconstruct  # noqa: E402
from fingerprint import SPRITE_SOURCES, code_sha256  # noqa: E402

#: Python outcomes that assert impossibility. `search_exhausted` is NOT one --
#: a search giving up is not a proof, and treating it as one is the single
#: worst error this comparison could bake in.
PROVES_IMPOSSIBLE = {"no_solution_proven", "grim_fail"}

R_SCRIPT = r"""
args <- commandArgs(trailingOnly = TRUE)
suppressMessages(library(rsprite2))
cases <- read.csv(args[1], stringsAsFactors = FALSE)
verdict <- character(nrow(cases)); why <- character(nrow(cases))
for (i in seq_len(nrow(cases))) {
  r <- tryCatch({
    set_parameters(mean = cases$mean[i], sd = cases$sd[i], n_obs = cases$n[i],
                   min_val = cases$lo[i], max_val = cases$hi[i],
                   m_prec = cases$m_prec[i], sd_prec = cases$sd_prec[i])
    c("feasible", "")
  }, error = function(e) {
    m <- conditionMessage(e)
    # "other" is NOT a proof. rsprite2 also raises on its OWN failures --
    # `mean = 5.0, sd = 0.0` at the scale maximum yields "Error in calculating
    # range of possible standard deviations", which is R being unable to
    # answer, not R proving anything. Reading that as impossibility is the same
    # error as reading `search_exhausted` as a proof, one implementation over.
    if (grepl("GRIMMER", m)) c("impossible", "grimmer")
    else if (grepl("outside the possible range", m)) c("impossible", "sd_range")
    else c("undecided", "r_internal_error")
  })
  verdict[i] <- r[1]; why[i] <- r[2]
}
cases$r_verdict <- verdict; cases$r_why <- why
write.csv(cases, args[2], row.names = FALSE)
"""


def enumerate_cases(quick: bool):
    """Integer-scale summaries a paper could plausibly print.

    Scales are the ones that actually appear (1-5, 1-7, 0-10), n is bounded
    where SPRITE still discriminates, and the mean/SD grid is at the precision
    papers report. Combinations far outside the scale are included on purpose:
    the infeasible region is what this is measuring, and a sweep that only
    visits plausible values never exercises the proof.
    """
    scales = [(1, 5), (1, 7)] if quick else [(1, 5), (1, 7), (0, 10)]
    ns = range(5, 26, 5) if quick else range(4, 61, 2)
    for lo, hi in scales:
        span = hi - lo
        for n in ns:
            for mi in range(0, span * 10 + 1, 5 if quick else 2):
                mean = lo + mi / 10
                for si in range(0, int(span * 10 * 0.6) + 1, 5 if quick else 2):
                    sd = si / 10
                    yield {"mean": f"{mean:.1f}", "sd": f"{sd:.1f}", "n": n,
                           "lo": lo, "hi": hi, "m_prec": 1, "sd_prec": 1}

    # TWO-DECIMAL GRID, so the region where the test has power is not three
    # group sizes wide. At one decimal "in power" (n < 10**m_prec) is n in
    # {4, 6, 8}; at two it is every n here. The step is coarse and deliberately
    # not a round number, so the printed values are not all multiples of 0.05.
    ns2 = range(5, 26, 10) if quick else range(4, 61, 4)
    step = 37 if quick else 13               # hundredths
    for lo, hi in scales:
        span = hi - lo
        for n in ns2:
            for mi in range(0, span * 100 + 1, step):
                mean = lo + mi / 100
                for si in range(0, int(span * 100 * 0.6) + 1, step):
                    sd = si / 100
                    yield {"mean": f"{mean:.2f}", "sd": f"{sd:.2f}", "n": n,
                           "lo": lo, "hi": hi, "m_prec": 2, "sd_prec": 2}


def in_power(c: dict) -> bool:
    """rsprite2's own rule: GRIM/GRIMMER discriminate only when
    N < 10**precision. Outside it neither engine's verdict means anything."""
    return int(c["n"]) < 10 ** int(c["m_prec"])


def python_verdict(c: dict):
    try:
        r = sprite_reconstruct(
            mean=float(c["mean"]), sd=float(c["sd"]), n=int(c["n"]),
            scale_min=int(c["lo"]), scale_max=int(c["hi"]),
            decimals_mean=int(c["m_prec"]), decimals_sd=int(c["sd_prec"]),
            data_type="integer", bound_source="stated",
            discreteness_source="stated", num_samples=1, max_iterations=200,
        )
    except Exception:                                        # noqa: BLE001
        return None, "exception"
    out = str(r.get("outcome") or "")
    if out in PROVES_IMPOSSIBLE:
        return "impossible", out
    if out == "found":
        return "feasible", out
    return None, out            # search_exhausted -- not a verdict either way


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=None,
                    help="default: sprite_r_differential.json beside this script "
                         "(sprite_r_differential.quick.json with --quick)")
    args = ap.parse_args()
    if args.out is None:
        args.out = str(HERE / ("sprite_r_differential.quick.json" if args.quick
                               else "sprite_r_differential.json"))

    cases = list(enumerate_cases(args.quick))
    print(f"cases enumerated: {len(cases):,}")

    with tempfile.TemporaryDirectory() as tmp:
        inp, outp = Path(tmp) / "c.csv", Path(tmp) / "o.csv"
        with inp.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(cases[0]))
            w.writeheader(); w.writerows(cases)
        rs = Path(tmp) / "sprite.R"; rs.write_text(R_SCRIPT, encoding="utf-8")
        print("running rsprite2::set_parameters over the same cases ...")
        proc = subprocess.run(["Rscript", str(rs), str(inp), str(outp)],
                              capture_output=True, text=True, timeout=14400)
        if proc.returncode != 0 or not outp.exists():
            print("R FAILED -- the differential did not run, which is NOT the "
                  "same as the implementations agreeing.", file=sys.stderr)
            print(proc.stderr[-2000:], file=sys.stderr)
            return 2
        with outp.open(encoding="utf-8") as fh:
            r_rows = list(csv.DictReader(fh))

    agree = disagree = undecided = 0
    region = {k: {"n_cases": 0, "n_compared": 0, "n_agree": 0, "n_disagree": 0}
              for k in ("in_power", "out_of_power")}
    by_dir: dict[str, int] = {}
    examples = []
    for c, row in zip(cases, r_rows):
        rv = row.get("r_verdict", "")
        pv, why = python_verdict(c)
        reg = region["in_power" if in_power(c) else "out_of_power"]
        reg["n_cases"] += 1
        if pv is None or rv == "undecided":
            undecided += 1
            continue
        reg["n_compared"] += 1
        if pv == rv:
            agree += 1
            reg["n_agree"] += 1
        else:
            disagree += 1
            reg["n_disagree"] += 1
            k = f"python={pv} r={rv}"
            by_dir[k] = by_dir.get(k, 0) + 1
            if True:   # keep every one: they are the finding
                examples.append({**c, "in_power": in_power(c),
                                 "python": pv, "python_outcome": why,
                                 "r": rv, "r_why": row.get("r_why", "")})

    total = agree + disagree
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quick": bool(args.quick),
        "code_sha256": code_sha256(SPRITE_SOURCES),
        "n_cases": len(cases), "n_compared": total,
        "n_agree": agree, "n_disagree": disagree,
        "n_python_undecided": undecided,
        "regions": region,
        "region_note": ("in_power = n < 10**m_prec, rsprite2's own rule for "
                        "where GRIM/GRIMMER discriminate. Only in_power "
                        "disagreements are evidence against either engine; "
                        "the pin test requires zero of them."),
        "agreement": (agree / total) if total else None,
        "disagreement_directions": by_dir,
        "disagreements": examples,
        "note": ("Compares the FEASIBILITY verdict only. SPRITE's reconstruction "
                 "is a stochastic search and two implementations will not return "
                 "the same distributions; the analytic proof is the whole "
                 "evidentiary surface. `search_exhausted` is counted UNDECIDED, "
                 "never as impossibility -- a search giving up is not a proof."),
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"compared {total:,}: agree {agree:,}  disagree {disagree:,}  "
          f"(python undecided {undecided:,})")
    for k, v in region.items():
        print(f"   {k}: compared {v['n_compared']:,}  agree {v['n_agree']:,}  "
              f"disagree {v['n_disagree']:,}")
    if by_dir:
        print("directions:", by_dir)
        for e in examples[:8]:
            print(f"   mean={e['mean']} sd={e['sd']} n={e['n']} "
                  f"[{e['lo']},{e['hi']}] python={e['python']}({e['python_outcome']}) "
                  f"r={e['r']}({e['r_why']})")
    print(f"\nwrote {args.out}")
    return 1 if region["in_power"]["n_disagree"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
