"""Score the p tools against the human-labelled cases -- no model, no cost.

Two instruments, each run on every case in cases.jsonl:

  recalc_stat_to_p   called with the case's statistic, df, reported p, relation,
                     printed decimals and tails (and `p_adjustment` when the
                     installed tool takes it). Flagged = an accusing severity.
  statcheck          the toolkit's wrapper (`python_statcheck_text`) on the
                     case rendered as an APA string. Flagged = an `error` that
                     is not cancelled as correct at printed precision.

For each tool the scorecard lists, per source and per stratum, which labelled
errors were caught and which labelled-correct statistics were flagged (by case
id), so a later run can be compared case by case, not just in totals.

    python benchmarks/pvalue_tools/score.py [--cases cases.jsonl] [--out scorecard.json]
"""

from __future__ import annotations

import argparse
import contextlib
import inspect
import io
import json
import re
import warnings
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCUSING = frozenset({"suspicious", "highly_suspicious", "impossible"})


def load_cases(path: Path = HERE / "cases.jsonl") -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ----------------------------------------------------------------- recalc tool
def run_recalc(cases: list[dict]) -> dict[str, bool | None]:
    """case id -> flagged (True/False), or None when the tool refused to evaluate."""
    from metascience_agent.tools.stat_to_p import recalc_stat_to_p
    params = set(inspect.signature(recalc_stat_to_p).parameters)
    out = {}
    for c in cases:
        kw = dict(statistic=c["statistic"], kind=c["kind"], reported_p=c["reported_p"],
                  decimals_stat=c.get("decimals_stat"), decimals_p=c.get("decimals_p"),
                  p_relation=c.get("p_relation"))
        if c["kind"] == "r":
            kw["n"] = c["n"]
        else:
            kw["df"] = c.get("df")
        if c.get("df2") is not None:
            kw["df2"] = c["df2"]
        if c["kind"] in ("t", "r", "z"):
            kw["tails"] = c.get("tails", 2)
        if c.get("p_adjustment") and "p_adjustment" in params:
            kw["p_adjustment"] = c["p_adjustment"]
        try:
            r = recalc_stat_to_p(**kw)
        except Exception:  # noqa: BLE001 -- a crash is a refusal for scoring purposes
            out[c["id"]] = None
            continue
        sev = str(r.get("severity", "")).lower()
        out[c["id"]] = True if sev in ACCUSING else (None if r.get("applicable") is False else False)
    return out


# ------------------------------------------------------------------- statcheck
def _fmt(x: float, d: int | None) -> str:
    if d is None:
        return repr(float(x)).rstrip("0").rstrip(".") if "." in repr(float(x)) else repr(x)
    s = f"{x:.{d}f}"
    return s


def apa(c: dict) -> str | None:
    v = _fmt(c["statistic"], c.get("decimals_stat"))
    p = _fmt(c["reported_p"], c.get("decimals_p"))
    if p.startswith("0."):
        p = p[1:]
    rel = c.get("p_relation") or "="
    if c["kind"] == "t":
        s = f"t({_fmt(c['df'], 0 if float(c['df']).is_integer() else 2)}) = {v}"
    elif c["kind"] == "f":
        d1 = _fmt(c["df"], 0 if float(c["df"]).is_integer() else 2)
        d2 = _fmt(c["df2"], 0 if float(c["df2"]).is_integer() else 2)
        s = f"F({d1}, {d2}) = {v}"
    elif c["kind"] == "chi2":
        s = f"χ2({_fmt(c['df'], 0 if float(c['df']).is_integer() else 2)}) = {v}"
    elif c["kind"] == "r":
        s = f"r({c['n'] - 2}) = {v}"
    elif c["kind"] == "z":
        s = f"z = {v}"
    else:
        return None
    one = " (one-tailed)" if c.get("tails") == 1 else ""
    return f"{s}, p {rel} {p}{one}"


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s.replace("χ²", "χ2").replace("−", "-")).lower()


def run_statcheck(cases: list[dict]) -> dict[str, bool | None]:
    """Each case is its own text: statcheck's per-text heuristics (one-tailed
    wording, corrections) must not leak from one case to the next."""
    from metascience_agent.tools.r_wrappers import python_statcheck_text
    out = {}
    for c in cases:
        s = apa(c)
        if s is None:
            out[c["id"]] = None
            continue
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            warnings.simplefilter("ignore")
            r = python_statcheck_text(f"The result was {s}.")
        rows = r.get("statistics") or []
        if not rows:
            out[c["id"]] = None  # not parsed
            continue
        row = rows[0]
        out[c["id"]] = bool(row.get("error")) and not bool(row.get("correct_at_printed_precision"))
    return out


# ------------------------------------------------------------------- scorecard
def scorecard(cases: list[dict], results: dict[str, dict[str, bool | None]]) -> dict:
    card = {"n_cases": len(cases), "tools": {}}
    for tool, res in results.items():
        groups = defaultdict(lambda: {"errors": 0, "caught": [], "correct": 0,
                                      "false_flags": [], "refused": 0})
        for c in cases:
            keys = ["all", f"source:{c['source']}"] + [f"stratum:{s}" for s in c.get("strata", [])]
            v = res.get(c["id"])
            for k in keys:
                g = groups[k]
                if v is None:
                    g["refused"] += 1
                if c["label"] == "error":
                    g["errors"] += 1
                    if v:
                        g["caught"].append(c["id"])
                else:
                    g["correct"] += 1
                    if v:
                        g["false_flags"].append(c["id"])
        card["tools"][tool] = {k: {**g, "caught": sorted(g["caught"]),
                                   "false_flags": sorted(g["false_flags"])}
                               for k, g in sorted(groups.items())}
    return card


def run(cases: list[dict]) -> dict:
    return scorecard(cases, {"recalc_stat_to_p": run_recalc(cases),
                             "statcheck": run_statcheck(cases)})


def summary_lines(card: dict) -> list[str]:
    lines = []
    for tool, groups in card["tools"].items():
        lines.append(f"== {tool}")
        for k, g in groups.items():
            if k == "all" or k.startswith("source:") or k.startswith("stratum:"):
                rec = f"{len(g['caught'])}/{g['errors']}" if g["errors"] else "-"
                ff = f"{len(g['false_flags'])}/{g['correct']}" if g["correct"] else "-"
                lines.append(f"   {k:34} caught {rec:9} false flags {ff:10} refused {g['refused']}")
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cases", type=Path, default=HERE / "cases.jsonl")
    ap.add_argument("--out", type=Path, default=HERE / "scorecard.json")
    a = ap.parse_args(argv)
    card = run(load_cases(a.cases))
    from metascience_agent.version import __version__
    card["toolkit_version"] = __version__
    a.out.write_text(json.dumps(card, indent=1, sort_keys=True) + "\n")
    print("\n".join(summary_lines(card)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
