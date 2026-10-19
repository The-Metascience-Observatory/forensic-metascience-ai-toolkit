"""Synthetic papers with KNOWN ground truth, for measuring the two error rates.

Why this exists
---------------
Every eval fixture in `benchmarks/paper_reviews/fixtures/` expects `verdict: untrustworthy`. That
measures sensitivity only. It cannot tell you how often the pipeline accuses an
HONEST paper -- which is the error that actually matters, because a false
accusation of misconduct is costly and hard to retract.

This module generates:

* **negative controls** -- tables whose summary statistics are computed from
  real integer samples, so they are correct *by construction*. Any
  `impossible` finding on these is a FALSE POSITIVE, full stop.
* **positive controls** -- the same tables with a single, known, surgical flaw
  injected. A missed flaw is a false negative.

Both are deterministic given a seed, cost nothing to run, and need no API call,
so they can gate every change to a tool.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass
class Row:
    """One reported summary-statistics row, plus the truth behind it."""

    label: str
    values: list[int]
    scale_min: int
    scale_max: int
    data_type: str = "likert"
    decimals: int = 2
    # What the "paper" reports. Equals the truth unless a flaw was injected.
    reported_mean: float = 0.0
    reported_sd: float = 0.0
    reported_n: int = 0
    flaw: str | None = None

    @property
    def true_mean(self) -> float:
        return sum(self.values) / len(self.values)

    @property
    def true_sd(self) -> float:
        n = len(self.values)
        if n < 2:
            return 0.0
        m = self.true_mean
        return math.sqrt(sum((v - m) ** 2 for v in self.values) / (n - 1))

    def report_truthfully(self) -> "Row":
        self.reported_mean = round(self.true_mean, self.decimals)
        self.reported_sd = round(self.true_sd, self.decimals)
        self.reported_n = len(self.values)
        self.flaw = None
        return self


@dataclass
class SyntheticPaper:
    paper_id: str
    rows: list[Row] = field(default_factory=list)
    injected_flaws: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.injected_flaws


def _sample_rows(rng: random.Random, n_rows: int, scale_min: int, scale_max: int) -> list[Row]:
    rows: list[Row] = []
    for i in range(n_rows):
        n = rng.choice([18, 24, 30, 42, 55, 64, 80, 117])
        values = [rng.randint(scale_min, scale_max) for _ in range(n)]
        rows.append(
            Row(
                label=f"item_{i + 1}",
                values=values,
                scale_min=scale_min,
                scale_max=scale_max,
            ).report_truthfully()
        )
    return rows


def generate_clean_paper(
    seed: int, n_rows: int = 6, scale_min: int = 1, scale_max: int = 7
) -> SyntheticPaper:
    """A paper whose statistics are correct BY CONSTRUCTION.

    Every reported mean/SD is computed from an actual integer sample, so there
    is no anomaly to find. Any `impossible` verdict here is a false positive.
    """
    rng = random.Random(seed)
    return SyntheticPaper(
        paper_id=f"clean_{seed}",
        rows=_sample_rows(rng, n_rows, scale_min, scale_max),
    )


# Flaw kinds a forensic pass SHOULD catch, each surgical and independently
# verifiable. `population_sd` is deliberately NOT here -- it is a legitimate
# reporting convention and belongs in the negative controls.
FLAW_KINDS = ("grim_violation", "impossible_sd", "transposed_digits")


def inject_flaw(row: Row, kind: str, rng: random.Random) -> Row:
    """Perturb a truthful row in one known way. Returns the same Row, mutated.

    A FLAW THAT CHANGES NO PRINTED NUMBER IS NOT A FLAW, and counting a tool as
    having "missed" one measures the generator, not the tool. Both mean-perturbing
    kinds used to produce them:

      * `grim_violation` nudged by 1/(3n) and re-rounded. At n = 80 or 117 --
        both on `_sample_rows`' menu -- that increment is below the rounding
        resolution, so `round(4.00 + 0.0028, 2)` is 4.00 forever. MEASURED over
        seeds 3000-3099: **23 of 100** "flawed" papers were numerically
        IDENTICAL to their clean twin. The benchmark's reported grim_violation
        sensitivity of 75% was close to 1 minus that rate -- a generator defect
        published as a property of GRIM.
      * `transposed_digits` was not a transposition. It replaced the last digit
        with the second-last, so 4.61 became 4.66, not 4.16. 11 of 100 were
        unchanged.

    Both now VERIFY the perturbation landed, and `row.flaw` is set to None when
    it could not -- at n >= 100 every two-decimal mean is GRIM-attainable, so no
    detectable violation exists to inject and the honest thing is to say so.
    `benchmark` then excludes those papers from the denominator instead of
    scoring them as misses.
    """
    before = (row.reported_mean, row.reported_sd)
    if kind == "grim_violation":
        # Walk in steps of the printed resolution, not of 1/(3n): the increment
        # has to be visible in the printed number to change what a reader sees.
        n = row.reported_n
        ulp = 1.0 / (10 ** row.decimals)
        candidate = row.reported_mean
        found = False
        for i in range(1, 201):
            candidate = round(row.reported_mean + i * ulp, row.decimals)
            if (candidate != row.reported_mean
                    and not _mean_is_attainable(candidate, n, row.decimals)
                    and row.scale_min <= candidate <= row.scale_max):
                found = True
                break
        if found:
            row.reported_mean = candidate
    elif kind == "impossible_sd":
        # An SD larger than the scale range can possibly support.
        span = row.scale_max - row.scale_min
        row.reported_sd = round(span * 0.75 + 1.0, row.decimals)
    elif kind == "transposed_digits":
        # A REAL transposition of the last two digits: 4.61 -> 4.16.
        s = f"{row.reported_mean:.{row.decimals}f}"
        chars = list(s)
        pos = [i for i, c in enumerate(chars) if c.isdigit()]
        if len(pos) >= 2 and chars[pos[-1]] != chars[pos[-2]]:
            chars[pos[-1]], chars[pos[-2]] = chars[pos[-2]], chars[pos[-1]]
            try:
                row.reported_mean = float("".join(chars))
            except ValueError:
                pass
    else:
        raise ValueError(f"unknown flaw kind: {kind}")
    # The honest record of whether a flaw was actually injected.
    row.flaw = kind if (row.reported_mean, row.reported_sd) != before else None
    return row


def _mean_is_attainable(mean: float, n: int, decimals: int) -> bool:
    tol = 0.5 / (10**decimals) + 1e-12
    target = round(mean * n)
    return any(abs(k / n - mean) <= tol for k in (target - 1, target, target + 1))


def generate_flawed_paper(
    seed: int, kind: str = "grim_violation", n_rows: int = 6,
    scale_min: int = 1, scale_max: int = 7,
) -> SyntheticPaper:
    """A clean paper with exactly ONE flawed row, of a known kind."""
    rng = random.Random(seed)
    paper = generate_clean_paper(seed, n_rows, scale_min, scale_max)
    paper.paper_id = f"flawed_{kind}_{seed}"
    target = rng.randrange(len(paper.rows))
    inject_flaw(paper.rows[target], kind, rng)
    paper.injected_flaws = [f"{paper.rows[target].label}:{kind}"]
    return paper


# THE HIGHER BAR, DELIBERATELY. This harness measures whether the panel catches
# an INJECTED flaw at accusation grade; the comments below reason explicitly
# about flaws "capped at `suspicious` -- below ACCUSATORY", so `suspicious` is
# meant to sit under this line. Shared by name so it cannot drift into the
# accuses-at-all set.
from .tools.severity import ACCUSATION_GRADE as ACCUSATORY


def screen_row(row: Row) -> dict:
    """Run the applicable tool panel on one row, honestly parameterised.

    Tools are told what the data actually are (`data_type`), that the scale
    bounds are stated, and that the observations are integers, which is the
    correct usage -- the point is to measure the false-positive rate under
    CORRECT use, not under misapplication.
    """
    from .tools import grim_test, grimmer_test

    # `discreteness_source` is the THIRD construction fact, and omitting it
    # reproduced the `bound_source` failure below EXACTLY: `_sample_rows` draws
    # every observation from `randint`, so integer-valuedness is how the data
    # were made, not something we are assuming about a paper we read. Left
    # defaulted, the injected `grim_violation` and `transposed_digits` flaws
    # capped at `suspicious` -- below ACCUSATORY -- and the panel caught 0 of
    # 15. A guard that is right for real papers is wrong for a fixture whose
    # premises are stipulated, and a sensitivity harness that quietly stops
    # detecting is the worst way to find that out.
    results = {}
    results["grim"] = grim_test(
        row.reported_mean, row.reported_n,
        scale_min=row.scale_min, scale_max=row.scale_max,
        decimals=row.decimals, data_type=row.data_type, bound_source="stated",
        discreteness_source="stated",
    )
    # Same two arguments the `grim_test` call above passes, and for the same
    # reason. `grimmer_test` gained `bound_source` when its severity was split by
    # failure mode: an `out_of_range` SD depends entirely on WHOSE bounds these
    # are, so it caps at `suspicious` unless the bound is hard. These bounds are
    # hard -- `_sample_rows` draws every value from `randint(scale_min,
    # scale_max)`, so the range is a construction fact, not our assumption.
    # Leaving it defaulted capped the injected `impossible_sd` flaw (sd 5.5 on a
    # 1-7 scale) at `suspicious`, which is below `ACCUSATORY`, so the panel
    # caught 0 of 15 -- a false all-clear on the one flaw that is unambiguous.
    results["grimmer"] = grimmer_test(
        row.reported_mean, row.reported_sd, row.reported_n,
        scale_min=row.scale_min, scale_max=row.scale_max, decimals=row.decimals,
        data_type=row.data_type, bound_source="stated",
        discreteness_source="stated",
    )
    return results


def screen_paper(paper: SyntheticPaper) -> dict:
    """Screen every row; return per-row severities and whether we accused."""
    per_row = {}
    accused_rows = []
    for row in paper.rows:
        res = screen_row(row)
        sevs = {k: v.get("severity") for k, v in res.items()}
        per_row[row.label] = sevs
        if any(s in ACCUSATORY for s in sevs.values()):
            accused_rows.append(row.label)
    return {
        "paper_id": paper.paper_id,
        "is_clean": paper.is_clean,
        "injected_flaws": paper.injected_flaws,
        "per_row": per_row,
        "accused_rows": accused_rows,
        "accused": bool(accused_rows),
    }


def benchmark(n_clean: int = 40, n_flawed_per_kind: int = 12, seed0: int = 1000) -> dict:
    """Measure specificity (1 - FP rate) and per-flaw sensitivity.

    Free, deterministic, offline. Run it after ANY change to a tool.
    """
    clean_results = [screen_paper(generate_clean_paper(seed0 + i)) for i in range(n_clean)]
    false_positives = [r for r in clean_results if r["accused"]]

    sensitivity = {}
    for kind in FLAW_KINDS:
        papers = [generate_flawed_paper(seed0 + 500 + j, kind=kind)
                  for j in range(n_flawed_per_kind)]
        runs = [screen_paper(p) for p in papers]
        # TWO CORRECTIONS, both of which used to inflate or deflate this number
        # with facts about the GENERATOR rather than about the tools.
        #
        # 1. A PAPER WITH NO INJECTED FLAW IS NOT A MISS. `inject_flaw` records
        #    `row.flaw = None` when the perturbation could not change any
        #    printed number -- at n >= 100 every two-decimal mean is
        #    GRIM-attainable, so no detectable violation exists to inject.
        #    MEASURED over seeds 3000-3099 before this was excluded: 23 of 100
        #    `grim_violation` papers were numerically IDENTICAL to their clean
        #    twin, and the reported sensitivity of ~75% was close to 1 minus
        #    that rate. `undetectable` is reported so the exclusion is visible.
        # 2. THE ACCUSED ROW MUST BE THE INJECTED ROW. Crediting a hit when any
        #    row was accused lets a false positive on a CLEAN row of a flawed
        #    paper score as a detection -- the one arrangement that makes a
        #    tool look better the worse it behaves.
        scored, caught = 0, 0
        for paper, run in zip(papers, runs):
            flawed_rows = {r.label for r in paper.rows if r.flaw}
            if not flawed_rows:
                continue
            scored += 1
            caught += bool(flawed_rows & set(run["accused_rows"]))
        sensitivity[kind] = {"caught": caught, "total": scored,
                             "undetectable": len(runs) - scored,
                             "rate": caught / scored if scored else None}

    return {
        "clean_papers": len(clean_results),
        "false_positive_papers": len(false_positives),
        "specificity": 1.0 - (len(false_positives) / len(clean_results)) if clean_results else 0.0,
        "false_positive_detail": [
            {"paper_id": r["paper_id"], "rows": r["accused_rows"]} for r in false_positives
        ],
        "sensitivity": sensitivity,
    }


# ---------------------------------------------------------------------------
# Negative controls for the rest of the panel
# ---------------------------------------------------------------------------
#
# `screen_row` above exercises `grim_test` and `grimmer_test`. The toolkit has
# a dozen more checks and NONE of them had a negative control, so their
# false-positive rate was not measured -- on a toolkit whose cardinal rule is
# that a false accusation is its worst output.
#
# The 2026-09-01 audits found honest-paper accusations in five of these tools
# (a percent CHANGE read as a share, a cluster trial read as one unit, a
# geometric mean read as arithmetic, a bootstrap CI read as Wald, a
# within-subjects d read as between-groups). Each is now guarded, and each is
# the kind of thing a generator like this catches by construction rather than
# by somebody thinking of it.
#
# WHAT MAKES THESE CONTROLS RATHER THAN FIXTURES: every quantity is COMPUTED
# from generated data, not typed out. A percentage is `100 * k / n` at the
# printed precision; a CI is the actual Wald interval of the generated
# estimate; a flow's arms sum to its stage. An accusatory verdict on any of
# them is a false positive by definition, with no adjudication needed.


def clean_count_percent(rng: random.Random) -> dict:
    """A count, its denominator, and the percentage they actually give."""
    n = rng.randint(30, 900)
    count = rng.randint(0, n)
    decimals = rng.choice([0, 1, 2])
    pct = round(100.0 * count / n, decimals)
    return {"count": count, "n": n, "percentage": pct, "decimals": decimals}


def clean_summation(rng: random.Random) -> dict:
    """Parts that really do add up to their total."""
    decimals = rng.choice([0, 1, 2])
    parts = [round(rng.uniform(0.5, 40.0), decimals) for _ in range(rng.randint(3, 6))]
    return {"values": parts, "expected_sum": round(sum(parts), decimals),
            "decimals": decimals}


def clean_estimate_ci(rng: random.Random) -> dict:
    """An estimate with its own WALD interval and the p that interval implies.

    Built on the log scale for a ratio measure, which is where the tool works,
    so the interval is symmetric in logs exactly as a Wald interval is.
    """
    import math

    log_est = rng.uniform(-1.2, 1.2)
    se = rng.uniform(0.05, 0.45)
    z = 1.959963984540054                      # two-sided 95%
    est = math.exp(log_est)
    lo, hi = math.exp(log_est - z * se), math.exp(log_est + z * se)
    # The p this interval implies, which is what the paper would print.
    from scipy import stats
    p = 2 * (1 - stats.norm.cdf(abs(log_est) / se))
    return {"estimate": round(est, 3), "ci_low": round(lo, 3),
            "ci_high": round(hi, 3), "measure": "OR",
            "reported_p": float(f"{p:.3g}"), "interval_method": "wald"}


def clean_flow(rng: random.Random) -> dict:
    """A CONSORT flow that reconciles, in ONE unit, with every loss accounted."""
    assessed = rng.randint(200, 900)
    excluded = rng.randint(10, assessed // 4)
    randomized = assessed - excluded
    lost = rng.randint(0, randomized // 6)
    analyzed = randomized - lost
    arm_a = analyzed // 2
    # `excluded` entries are OBJECTS, not pairs. My first version used
    # `[["ineligible", 22]]` and the tool refused the whole flow with "stage
    # ... excluded[0] is not an object" -- so all 60 controls returned
    # `indeterminate` and measured NOTHING while looking like a clean sweep.
    # A negative control that never reaches its check is worse than no control:
    # it reports specificity it did not test.
    return {"stages": [
        {"label": "Participants assessed", "n": assessed, "unit": "participants",
         "excluded": [{"label": "ineligible", "n": excluded}]},
        {"label": "Participants randomized", "n": randomized, "unit": "participants",
         "excluded": [{"label": "withdrew", "n": lost}]},
        {"label": "Participants analyzed", "n": analyzed, "unit": "participants",
         "arms": [{"label": "treatment", "n": arm_a},
                  {"label": "control", "n": analyzed - arm_a}]},
    ]}


def clean_effect_size(rng: random.Random) -> dict:
    """Two groups and the between-groups d their own statistics give."""
    import math

    n1 = n2 = rng.randint(20, 120)
    sd1 = round(rng.uniform(0.8, 12.0), 2)
    sd2 = round(sd1 * rng.uniform(0.85, 1.15), 2)
    m1 = round(rng.uniform(10.0, 60.0), 2)
    m2 = round(m1 - rng.uniform(-6.0, 6.0), 2)
    pooled = math.sqrt(((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / (n1 + n2 - 2))
    d = (m1 - m2) / pooled
    return {"mean1": m1, "sd1": sd1, "n1": n1, "mean2": m2, "sd2": sd2, "n2": n2,
            "reported_d": round(d, 2), "design": "parallel-group RCT"}


#: name -> (generator, tool import path, callable name). Each generator returns
#: kwargs the tool accepts directly, so a mismatch surfaces as a TypeError
#: rather than as a silently defaulted premise.
CLEAN_GENERATORS = {
    "check_count_percent": (clean_count_percent, "count_percent"),
    "check_summation": (clean_summation, "summation"),
    "check_estimate_ci": (clean_estimate_ci, "estimates"),
    "check_flow_arithmetic": (clean_flow, "flow"),
    "check_effect_plausibility": (clean_effect_size, "effect_size"),
}


def screen_clean(tool: str, seed: int) -> dict:
    """Generate one correct-by-construction case and run its tool on it."""
    import importlib

    generator, module = CLEAN_GENERATORS[tool]
    kwargs = generator(random.Random(seed))
    fn = getattr(importlib.import_module(
        f"forensic_metascience_ai_toolkit.tools.{module}"), tool)
    result = fn(**kwargs) or {}
    return {"tool": tool, "seed": seed, "inputs": kwargs,
            "severity": result.get("severity"),
            "explanation": str(result.get("explanation")
                               or result.get("finding") or "")[:300]}


#: name -> a function that takes clean kwargs and returns them with ONE known
#: defect. These exist so the negative controls above cannot pass vacuously: a
#: generator whose output no longer reaches its check reports specificity it
#: did not test, which is exactly what happened to `clean_flow` on its first
#: version (its `excluded` entries were pairs rather than objects, the tool
#: refused every case, and 60 `indeterminate` verdicts looked like a clean
#: sweep).
def _break_count_percent(kw: dict) -> dict:
    # A percentage that no count over this n can produce.
    bad = round(100.0 * kw["count"] / kw["n"] + 9.0, kw["decimals"])
    return {**kw, "percentage": min(bad, 99.9)}


def _break_summation(kw: dict) -> dict:
    return {**kw, "expected_sum": round(kw["expected_sum"] + 7.5, kw["decimals"])}


def _break_estimate_ci(kw: dict) -> dict:
    # The interval's own p, moved somewhere the interval cannot reach.
    return {**kw, "reported_p": 0.5 if kw["reported_p"] < 0.1 else 0.0001}


def _break_flow(kw: dict) -> dict:
    stages = [dict(s) for s in kw["stages"]]
    stages[-1] = {**stages[-1], "n": stages[1]["n"] + 40}   # analysed > randomised
    stages[-1].pop("arms", None)
    return {"stages": stages}


def _break_effect_size(kw: dict) -> dict:
    return {**kw, "reported_d": round(kw["reported_d"] + 0.9, 2)}


BREAKERS = {
    "check_count_percent": _break_count_percent,
    "check_summation": _break_summation,
    "check_estimate_ci": _break_estimate_ci,
    "check_flow_arithmetic": _break_flow,
    "check_effect_plausibility": _break_effect_size,
}


def screen_broken(tool: str, seed: int) -> dict:
    """The same generated case with one known defect, run through its tool."""
    import importlib

    generator, module = CLEAN_GENERATORS[tool]
    kwargs = BREAKERS[tool](generator(random.Random(seed)))
    fn = getattr(importlib.import_module(
        f"forensic_metascience_ai_toolkit.tools.{module}"), tool)
    result = fn(**kwargs) or {}
    return {"tool": tool, "seed": seed, "inputs": kwargs,
            "severity": result.get("severity"),
            "explanation": str(result.get("explanation")
                               or result.get("finding") or "")[:300]}
