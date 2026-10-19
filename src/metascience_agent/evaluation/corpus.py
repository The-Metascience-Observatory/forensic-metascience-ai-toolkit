"""Score the tool panel against the labelled corpus, exactly as pre-registered.

This module exists so that the analysis has NO free parameters left by the time
a number is produced. `eval/PREREGISTRATION.md` fixes the unit of analysis, the
accusation threshold, the clustering, the exclusions and the interval method;
this file is that document expressed as code, committed before the run.

The one thing it will not do is guess. Every cell the corpus cannot adjudicate
is reported in its own bucket rather than folded into a numerator or a
denominator, because folding `UNDETERMINED` either way is the cheapest available
route to a flattering result.

Inputs
------
`manifest.csv`   -- the corpus, one row per paper. Only the eligibility columns
                    are read here; `label` is used solely to assert that the
                    manifest is internally consistent.
`cells.jsonl`    -- the run output, one JSON object per (paper, tool):

    {"doi": "10.1/x", "tool": "grim", "evaluated": true,
     "max_severity": "consistent", "n_findings": 0}

    `evaluated: false` means the tool refused or could not run -- a visible
    refusal, which the severity ladder tolerates and which E4 measures. It is
    NOT an accusation and NOT a miss.
"""
from __future__ import annotations

import csv
import json
import math
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# The eight tools the manifest adjudicates. Anything outside this set in a
# cells.jsonl is a bug in the runner, not a result, and is rejected loudly.
TOOLS = (
    "grim", "grimmer", "sprite", "debit",
    "statcheck", "baseline_similarity", "digit_preference", "duplication",
)

# Pre-registered accusation threshold (PREREGISTRATION.md section 4). The
# secondary threshold is carried alongside so neither can be quoted alone.
# NOT UNIFIED WITH THE at-all SET, deliberately: these are the PRE-REGISTERED
# thresholds, and moving one silently would move a published rate. Both are
# shared by name from the vocabulary authority so they cannot drift in value,
# while staying two distinct pre-registered quantities here.
from ..tools.severity import ACCUSATION_GRADE as ACCUSATORY
from ..tools.severity import ACCUSES_AT_ALL as ACCUSATORY_SECONDARY

FIRE, NULL, UNDETERMINED, VETOED = "FIRE", "NULL", "UNDETERMINED", "VETOED"


def _toks(s: str) -> set[str]:
    """Split a tool list. The manifest uses `|` in one column and `,` in another."""
    return {t.strip() for t in (s or "").replace("|", ",").split(",")
            if t.strip() and t.strip() != "none"}


def case_of(row: dict) -> str:
    """The misconduct case a paper belongs to -- the CLUSTER, not the paper.

    Eight of the thirty fraud papers are the Sato/Iwamoto case and four are
    Anderson. Papers within a case share authors, methods and often one
    fabricated data-generating process, so treating them as independent
    observations overstates the positive-side sample by roughly a factor of two.
    The manifest records the case as a bracketed prefix on `notes`; controls are
    their own cluster.
    """
    m = re.match(r"\[([^\]]+)\]", (row.get("notes") or "").strip())
    if not m:
        return "doi:" + row["doi"]
    return m.group(1).split("(")[0].strip().split(";")[0].strip()


@dataclass(frozen=True)
class Cell:
    doi: str
    tool: str
    state: str
    case: str
    label: str


def cell_states(manifest_rows: list[dict]) -> list[Cell]:
    """Assign every (paper, tool) to exactly one pre-registered state.

    Determined entirely by the manifest -- no run output is consulted, which is
    what makes it safe to compute this before the run and impossible to tune
    afterwards.
    """
    cells: list[Cell] = []
    for r in manifest_rows:
        can, cannot = _toks(r["can_validate_tools"]), _toks(r["cannot_validate_tools"])
        raw_expected = (r["expected_statistical_signature"] or "")
        expected = _toks(raw_expected)
        # `none` is a positive claim -- this paper should produce NOTHING -- and
        # is distinct from an empty cell, which would be an unfilled manifest.
        # Read the `none` token off the RAW string: `_toks` strips it, so testing
        # the stripped set for it can never be true and the contradiction check
        # below would be permanently inert.
        says_none = "none" in {t.strip() for t in raw_expected.replace("|", ",").split(",")}
        expects_none = says_none and not expected
        unknown = (can | cannot | expected) - set(TOOLS)
        if unknown:
            raise ValueError(f"{r['doi']}: unknown tool(s) in manifest: {sorted(unknown)}")
        if says_none and expected:
            raise ValueError(
                f"{r['doi']}: expected signature is both 'none' and {sorted(expected)}"
            )
        if not says_none and not expected:
            raise ValueError(
                f"{r['doi']}: expected_statistical_signature is blank. Write 'none' if the "
                f"claim is that nothing should fire; a blank field is an unfilled manifest, "
                f"and treating it as 'none' would invent 8 negative controls."
            )
        case, label = case_of(r), r["label"]
        for tool in sorted(can | cannot):
            if tool in cannot:
                state = VETOED
            elif tool in expected:
                state = FIRE
            elif expects_none:
                state = NULL
            else:
                state = UNDETERMINED
            cells.append(Cell(r["doi"], tool, state, case, label))
    return cells


def load_manifest(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_cells(path: Path) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            key = (rec["doi"], rec["tool"])
            if key in out:
                raise ValueError(f"{path}:{lineno}: duplicate cell {key}")
            if rec["tool"] not in TOOLS:
                raise ValueError(f"{path}:{lineno}: unknown tool {rec['tool']!r}")
            out[key] = rec
    return out


def accuses(rec: dict | None, threshold: frozenset[str] = ACCUSATORY) -> bool:
    """A missing or unevaluated cell does not accuse.

    A tool that never ran cannot have accused anyone. Scoring absence as an
    accusation would invent false positives; scoring it as a clean pass would
    invent specificity. It is neither -- it is coverage, and E4 measures it.
    """
    if rec is None or not rec.get("evaluated"):
        return False
    return rec.get("max_severity") in threshold


# ---------------------------------------------------------------------------
# Intervals. Both methods here are chosen for the same reason: they behave
# honestly at zero, which is where this study will spend most of its time.
# ---------------------------------------------------------------------------

def clopper_pearson_upper(k: int, n: int, alpha: float = 0.05) -> float:
    """One-sided upper 95% bound on a proportion.

    `0 out of 48` is not "100% specificity"; it is a point estimate of zero with
    an upper bound near 6%, and the bound is the honest thing to quote. Uses the
    beta-quantile form via bisection so there is no scipy dependency.
    """
    if n == 0:
        return 1.0
    if k >= n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        # P(X <= k | n, mid); the bound is the p where this equals alpha.
        tail = sum(math.comb(n, i) * mid**i * (1 - mid) ** (n - i) for i in range(k + 1))
        if tail > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson_lower(k: int, n: int, alpha: float = 0.05) -> float:
    """One-sided lower 95% bound. The mirror of the above, and needed for the
    same reason: `14 out of 14` is not "100% sensitivity". With 14 independent
    cases a perfect score establishes only that the true rate exceeds ~81%.
    """
    if n == 0:
        return 0.0
    if k <= 0:
        return 0.0
    return 1.0 - clopper_pearson_upper(n - k, n, alpha)


def cluster_bootstrap_ci(
    units: list[tuple[str, bool]], n_boot: int = 10_000, seed: int = 20260809
) -> tuple[float, float]:
    """Percentile CI resampling CASES, not papers.

    `units` is (case, accused) per cell. Resampling cells would treat the eight
    Sato papers as eight independent facts about the world; they are one.
    Returns (nan, nan) rather than a fake interval when there is nothing or only
    one cluster to resample.
    """
    if not units:
        return (float("nan"), float("nan"))
    by_case: dict[str, list[bool]] = defaultdict(list)
    for case, hit in units:
        by_case[case].append(hit)
    cases = sorted(by_case)
    if len(cases) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    props: list[float] = []
    for _ in range(n_boot):
        drawn = [by_case[rng.choice(cases)] for _ in cases]
        flat = [h for group in drawn for h in group]
        if flat:
            props.append(sum(flat) / len(flat))
    if not props:
        return (float("nan"), float("nan"))
    props.sort()
    return (props[int(0.025 * len(props))], props[min(int(0.975 * len(props)), len(props) - 1)])


@dataclass
class Endpoint:
    name: str
    k: int
    n: int
    n_cases: int
    ci: tuple[float, float] = (float("nan"), float("nan"))
    upper_bound: float | None = None
    lower_bound: float | None = None
    estimable: bool = True
    note: str = ""

    @property
    def rate(self) -> float | None:
        return (self.k / self.n) if self.n else None


def _endpoint(name: str, units: list[tuple[str, bool]], **kw) -> Endpoint:
    k = sum(1 for _, hit in units if hit)
    n = len(units)
    n_cases = len({c for c, _ in units})
    ep = Endpoint(name=name, k=k, n=n, n_cases=n_cases, **kw)
    if n:
        ep.ci = cluster_bootstrap_ci(units)
        if k == 0:
            # At zero the bootstrap returns (0, 0), which reads as certainty.
            # The Clopper-Pearson bound over CASES is what gets quoted instead.
            ep.upper_bound = clopper_pearson_upper(0, n_cases)
        elif k == n:
            # And a perfect score is not certainty either.
            ep.lower_bound = clopper_pearson_lower(n_cases, n_cases)
    return ep


# Per-tool sensitivity is reported only where the corpus can support it.
# Pre-registered in section 3: below this many positive controls the interval is
# too wide to carry a claim, and reporting a bare fraction invites one.
MIN_FIRE_CELLS_FOR_PER_TOOL = 9


def score(
    manifest_rows: list[dict],
    cells: dict[tuple[str, str], dict],
    threshold: frozenset[str] = ACCUSATORY,
) -> dict:
    """Compute every endpoint in PREREGISTRATION.md section 7."""
    states = cell_states(manifest_rows)
    by_state: dict[str, list[Cell]] = defaultdict(list)
    for c in states:
        by_state[c.state].append(c)

    def units(cs: list[Cell]) -> list[tuple[str, bool]]:
        return [(c.case, accuses(cells.get((c.doi, c.tool)), threshold)) for c in cs]

    e1 = _endpoint("E1 false-accusation rate (PRIMARY)", units(by_state[NULL]))
    e2 = _endpoint("E2 sensitivity (secondary)", units(by_state[FIRE]))
    e5 = _endpoint("E5 undetermined-cell accusation rate (descriptive)",
                   units(by_state[UNDETERMINED]))

    # E3: the canaries. Papers whose expected signature is `none` but whose
    # label is fraud -- Potti x2 (no parseable statistics exist, so any output is
    # hallucinated) and Shu (signatures are all file-level). Correct count: zero.
    canary_dois = {r["doi"] for r in manifest_rows
                   if r["label"] == "fraud"
                   and (r["expected_statistical_signature"] or "").strip() == "none"}
    canary_hits = [
        {"doi": c.doi, "tool": c.tool, "severity": cells[(c.doi, c.tool)].get("max_severity")}
        for c in by_state[NULL]
        if c.doi in canary_dois and accuses(cells.get((c.doi, c.tool)), threshold)
    ]

    # E4: coverage over every cell the corpus can adjudicate at all.
    scoreable = by_state[FIRE] + by_state[NULL] + by_state[UNDETERMINED]
    evaluated = sum(1 for c in scoreable
                    if (cells.get((c.doi, c.tool)) or {}).get("evaluated"))

    per_tool: dict[str, dict] = {}
    for tool in TOOLS:
        fire = [c for c in by_state[FIRE] if c.tool == tool]
        null = [c for c in by_state[NULL] if c.tool == tool]
        entry: dict = {
            "n_fire": len(fire),
            "false_accusation": _endpoint(f"{tool} E1", units(null)),
        }
        if len(fire) >= MIN_FIRE_CELLS_FOR_PER_TOOL:
            entry["sensitivity"] = _endpoint(f"{tool} E2", units(fire))
        else:
            entry["sensitivity"] = Endpoint(
                name=f"{tool} E2", k=0, n=len(fire), n_cases=0, estimable=False,
                note=(f"not estimable: {len(fire)} positive control(s) in this corpus, "
                      f"below the pre-registered minimum of {MIN_FIRE_CELLS_FOR_PER_TOOL}"),
            )
        per_tool[tool] = entry

    return {
        "threshold": sorted(threshold),
        "state_counts": {s: len(by_state[s]) for s in (FIRE, NULL, UNDETERMINED, VETOED)},
        "n_fraud_cases": len({c.case for c in states if c.label == "fraud"}),
        "E1": e1,
        "E2": e2,
        "E3_canary_hits": canary_hits,
        "E3_canary_dois": sorted(canary_dois),
        "E4_coverage": {"evaluated": evaluated, "scoreable": len(scoreable),
                        "rate": evaluated / len(scoreable) if scoreable else None},
        "E5": e5,
        "per_tool": per_tool,
        "missing_cells": sorted(
            (c.doi, c.tool) for c in scoreable if (c.doi, c.tool) not in cells
        ),
    }


def verdict(result: dict) -> list[str]:
    """The pre-registered failure conditions (section 8), evaluated mechanically.

    Written before the run precisely so that a bad result cannot be re-narrated
    as a mixed one afterwards.
    """
    out: list[str] = []
    unmeasured: list[str] = []
    e1: Endpoint = result["E1"]
    e1_upper = e1.upper_bound if e1.upper_bound is not None else e1.ci[1]
    if e1.n and not math.isnan(e1_upper) and e1_upper > 0.20:
        out.append(
            f"NOT DEPLOYABLE as an accusation instrument: the upper 95% bound on the "
            f"false-accusation rate is {e1_upper:.1%}, above the pre-registered 20% "
            f"ceiling. Sensitivity does not rescue this."
        )
    elif e1.n and math.isnan(e1_upper):
        # AN UNEVALUATED CONDITION IS NOT A SATISFIED ONE.
        #
        # MEASURED 2026-08-18. `cluster_bootstrap_ci` returns (nan, nan) when
        # there are fewer than two CASES to resample -- correctly, since one
        # cluster cannot produce an interval. But the guard above then skips the
        # check, nothing else appends anything, and the function falls through
        # to "No pre-registered failure condition triggered."
        #
        # An endpoint with k=3 of n=10 -- a 30% observed false-accusation rate,
        # half again over the pre-registered 20% ceiling -- returned exactly
        # that clean bill of health, because the BOUND was unmeasurable even
        # though the RATE was not.
        #
        # This function exists, in its own words, "so that a bad result cannot
        # be re-narrated as a mixed one afterwards". Silently converting "we
        # could not evaluate the ceiling" into "no condition triggered" is that
        # re-narration, performed by the instrument written to prevent it.
        rate = f"{e1.rate:.1%}" if e1.rate is not None else "unknown"
        unmeasured.append(
            f"E1 NOT EVALUATED: the upper bound on the false-accusation rate "
            f"could not be computed ({e1.n_cases} case(s) -- a cluster "
            f"bootstrap needs at least two). The OBSERVED rate is {rate} "
            f"({e1.k}/{e1.n}). The 20% ceiling was neither met nor breached; it "
            f"was not tested."
        )
    if result["E3_canary_hits"]:
        out.append(
            f"EXTRACTION UNFIT: {len(result['E3_canary_hits'])} accusatory finding(s) on the "
            f"canary papers, where no parseable statistic exists to check. These are our own "
            f"fabrications reported as claims about the paper."
        )
    cov = result["E4_coverage"]["rate"]
    if cov is not None and cov < 0.25:
        out.append(
            f"THIS IS A PARSING RESULT, NOT A FORENSIC ONE: only {cov:.1%} of scoreable cells "
            f"could be evaluated. Report the parsing finding and suppress the forensic endpoints."
        )
    elif cov is None:
        unmeasured.append(
            "E4 NOT EVALUATED: the coverage rate is unavailable, so the 25% "
            "parsing-result threshold was not tested.")

    if not out and not unmeasured:
        out.append("No pre-registered failure condition triggered.")
    elif not out:
        # Never the bare all-clear when a condition went untested. The line
        # below is deliberately not reassuring: it says what was checked, not
        # that everything passed.
        out.append("No pre-registered failure condition triggered AMONG THOSE "
                   "THAT COULD BE EVALUATED -- see the not-evaluated line(s) "
                   "below; this is not a clean result.")
    return out + unmeasured


def format_report(result: dict) -> str:
    """Plain-text report. Every rate carries its interval; zeros carry a bound."""
    def line(ep: Endpoint) -> str:
        if not ep.estimable:
            return f"  {ep.name}: {ep.note}"
        if not ep.n:
            return f"  {ep.name}: no eligible cells"
        body = f"  {ep.name}: {ep.k}/{ep.n} = {ep.rate:.1%}  ({ep.n_cases} cases)"
        if ep.upper_bound is not None:
            body += f"  [0, {ep.upper_bound:.1%}] one-sided Clopper-Pearson over cases"
        elif ep.lower_bound is not None:
            body += f"  [{ep.lower_bound:.1%}, 100%] one-sided Clopper-Pearson over cases"
        elif not math.isnan(ep.ci[0]):
            body += f"  95% CI [{ep.ci[0]:.1%}, {ep.ci[1]:.1%}] cluster bootstrap"
        return body

    L = [
        "FMT panel vs labelled corpus -- scored per eval/PREREGISTRATION.md",
        f"accusation threshold: {', '.join(result['threshold'])}",
        "",
        "cell states: " + "  ".join(f"{k}={v}" for k, v in result["state_counts"].items()),
        f"fraud cases (clustering unit): {result['n_fraud_cases']}",
        "",
        line(result["E1"]),
        line(result["E2"]),
        line(result["E5"]),
    ]
    cov = result["E4_coverage"]
    L.append(f"  E4 coverage: {cov['evaluated']}/{cov['scoreable']}"
             + (f" = {cov['rate']:.1%}" if cov["rate"] is not None else ""))
    L.append(f"  E3 canary hits (correct answer is 0): {len(result['E3_canary_hits'])}")
    for h in result["E3_canary_hits"]:
        L.append(f"      {h['doi']} / {h['tool']} -> {h['severity']}")
    L += ["", "per tool:"]
    for tool, entry in result["per_tool"].items():
        L.append(f"  {tool}")
        L.append("  " + line(entry["sensitivity"]).strip())
        L.append("  " + line(entry["false_accusation"]).strip())
    if result["missing_cells"]:
        L += ["", f"MISSING from cells.jsonl: {len(result['missing_cells'])} scoreable cells "
                  f"produced no record at all (counted as not-evaluated)."]
    L += ["", "pre-registered verdict:"] + [f"  - {v}" for v in verdict(result)]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cells", type=Path, help="path to cells.jsonl from the run")
    ap.add_argument("--manifest", type=Path,
                    default=Path("eval/ground_truth/manifest.csv"))
    ap.add_argument("--secondary", action="store_true",
                    help="also score at the secondary 'suspicious+' threshold")
    ap.add_argument("--json", type=Path, help="write the raw result dict here")
    args = ap.parse_args(argv)

    rows = load_manifest(args.manifest)
    cells = load_cells(args.cells)
    result = score(rows, cells)
    print(format_report(result))
    if args.secondary:
        print("\n" + "=" * 72 + "\nSECONDARY THRESHOLD (suspicious and above)\n")
        print(format_report(score(rows, cells, ACCUSATORY_SECONDARY)))
    if args.json:
        args.json.write_text(json.dumps(result, default=lambda o: o.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
