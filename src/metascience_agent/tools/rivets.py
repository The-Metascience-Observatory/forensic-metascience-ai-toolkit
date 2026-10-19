"""
RIVETS — Rounded Input Variables, Exact Test Statistics.

Original observation: Nick Brown (https://osf.io/preprints/psyarxiv/ctu9z),
discussed in Heathers (2025) §"RIVETS, and assessing 'hand curated'
statistical tests".

Setup. A reported descriptive statistic v at d decimals is actually a value
in the half-open interval [v − 0.5·10⁻ᵈ, v + 0.5·10⁻ᵈ). Test statistics
computed from rounded means/SDs are therefore intervals too. RIVETS asks:

(a) What are the analytic min and max of the test statistic given the
    truncation intervals? (Useful for "uninformative statistics" — when the
    range crosses a significance boundary.)
(b) If we evaluate the test at the EXACT rounded values, is the result
    suspiciously close to the reported test statistic? Hand-calculation by
    pen-and-paper or pasting truncated values into a calculator typically
    produces *exactly* this value; software run on the raw data does not.
(c) Across uniform Monte Carlo samples from the joint truncation interval,
    what fraction reproduce the reported t to its reported precision?
    A point match plus a low Monte Carlo match rate is a strong RIVETS hit.

This module implements RIVETS for independent-samples t-tests and one-way
ANOVAs (the two test forms most commonly hand-checked).
"""

from __future__ import annotations

import random
from typing import Optional

from . import anova as _anova
from . import rounding as _rounding
from . import ttest as _ttest
from ..survey_design import survey_refusal
from .severity import (
    CONSISTENT,
    HIGHLY_SUSPICIOUS,
    SEVERITY_LEVELS,
    refuse_if_nonfinite,
)

# Re-exported under the local names these modules (and `grimu`) already import.
_half_width = _rounding.half_width
_matches_at_precision = _rounding.matches_at_precision


# Severity is the WORST of the independent checks a call performs, never the
# last one evaluated. Two flags now fire in the same pass (reported t/F and
# reported p), and plain assignment in evaluation order would let a later
# `consistent` overwrite an earlier `highly_suspicious`.
_SEVERITY_RANK = {name: i for i, name in enumerate(reversed(SEVERITY_LEVELS))}


def _worst(current: str, candidate: str) -> str:
    return candidate if _SEVERITY_RANK[candidate] > _SEVERITY_RANK[current] else current


def _reported_p_outside(
    reported_p: Optional[float],
    is_threshold: bool,
    intervals: list[tuple[float, float]],
    decimals_p: int,
) -> bool:
    """Is a reported p unreachable under EVERY accepted achievable interval?

    Precision-aware in BOTH directions, which is the whole reason RIVETS
    replaces recalc here:

    * Each achievable interval comes from the printed precision of the
      means/SDs -- it is whatever the same machinery already derived, never a
      fixed tolerance around a point estimate.
    * The reported p is itself a printed number, so it stands for the interval
      [p +/- half-ulp at decimals_p]. Comparing the bare printed value against
      the achievable interval would accuse a paper whose true p is 0.0499 of
      misreporting "p = .05".

    `intervals` carries one achievable [p_min, p_max] per accepted READING of
    the report (test flavor x tail convention). The union is deliberately a
    union of intervals, not their convex hull: a p that falls in the gap
    between the two-tailed and one-tailed intervals matches NEITHER convention
    and stays refutable.

    A THRESHOLD ("p < .001") is a one-sided claim, not a value: it is refuted
    only when even the smallest achievable p under any accepted reading
    exceeds the stated bound. Papers report bounds far more often than exact
    p-values, so reading one as exact is a large false-accusation class rather
    than a detection.
    """
    if reported_p is None or not intervals:
        return False
    if is_threshold:
        return min(lo for lo, _ in intervals) > reported_p + 1e-12
    half_p = _half_width(decimals_p)
    return all(
        not (lo - half_p - 1e-12 <= reported_p <= hi + half_p + 1e-12)
        for lo, hi in intervals
    )


# =============================================================================
# Independent-samples t-test
# =============================================================================

def rivets_independent_t(
    mean1: float,
    sd1: float,
    n1: int,
    mean2: float,
    sd2: float,
    n2: int,
    reported_t: Optional[float] = None,
    reported_p: Optional[float] = None,
    decimals_mean: int = 2,
    decimals_sd: int = 2,
    decimals_t: int = 3,
    decimals_p: int = 3,
    use_welch: Optional[bool] = None,
    p_tail: str = "unknown",
    p_is_threshold: Optional[bool] = None,
    num_samples: int = 10_000,
    seed: int = 0,
    sampling: str = "simple_random",
) -> dict:
    """RIVETS analysis for an independent two-sample t-test.

    FALSE-POSITIVE CONTROL (same shape as DEBIT's two SD conventions): a
    reported t/p is judged against every standard READING the paper could
    legitimately have used -- test flavor (Welch's unequal-variance t vs
    Student's pooled t; their statistics differ substantially at unequal n/SD)
    x tail convention for p. A value is HIGHLY suspicious only when NO
    standard reading reaches it. `use_welch=None` / `p_tail="unknown"` (the
    defaults) mean the paper does not say; pinning a convention that the
    numbers then fail -- while the OTHER standard reading explains them -- is
    reported at `suspicious` (a wrong-line copy or unstated convention), never
    at accusation grade.

    Returns:
        dict with point estimates (at truncated inputs), per-flavor analytic
        [t_min, t_max] and achievable [p_min, p_max], optional reported-t/p
        comparisons, Monte Carlo hit rates at the reported precision, and a
        severity verdict.
    """
    refusal = survey_refusal("rivets_independent_t", sampling)
    if refusal is not None:
        return refusal
    if n1 < 2 or n2 < 2:
        return {"severity": "indeterminate",
                "explanation": "Both groups need n ≥ 2.",
                "methodology": "Trivial precondition."}
    if sd1 < 0 or sd2 < 0:
        # OUR artefact, not their claim -- see the identical guard in
        # `recalc_independent_t`, which refuses rather than accuses. A negative
        # SD is a dash we mis-parsed, and `impossible` also sat above this
        # tool's declared ceiling of `highly_suspicious`.
        return {"severity": "indeterminate",
                "explanation": (
                    "Not evaluated. A negative SD is not something any analysis "
                    "produces, so this is almost certainly a value we mis-read."),
                "methodology": "Trivial precondition."}
    if p_tail not in ("two", "one", "unknown"):
        return {"severity": "indeterminate",
                "explanation": f"p_tail must be 'two', 'one' or 'unknown' (got {p_tail!r}).",
                "methodology": "Trivial precondition."}

    flavors_all = ("welch", "student")
    pinned_flavors = (
        ("welch",) if use_welch is True
        else ("student",) if use_welch is False
        else flavors_all
    )
    pinned_tails = ("two", "one") if p_tail == "unknown" else (p_tail,)
    primary = "student" if use_welch is False else "welch"

    # A reported p may arrive as a bound ("p < .001"); see _reported_p_outside.
    p_reported, _parsed_threshold = _ttest._parse_reported_p(reported_p)
    # AN EXPLICIT DECLARATION WINS OVER THE LITERAL, and it has to, because the
    # literal cannot carry the fact. `_parse_reported_p` reads a bound off the
    # STRING "p < .001"; the registry types `reported_p` as a float, so over
    # MCP -- which is every real call -- the string form is UNREACHABLE and a
    # threshold always arrived looking like an exact value. `_reported_p_outside`
    # names that case "a large false-accusation class rather than a detection",
    # and until now it was the only reading a caller could get.
    p_is_threshold = _parsed_threshold if p_is_threshold is None else bool(p_is_threshold)
    if reported_p is None:
        p_reported = None

    half_m = _half_width(decimals_mean)
    half_s = _half_width(decimals_sd)

    # Reverse-engineer the SD interval, clipped to ≥ 0.
    sd1_lo, sd1_hi = max(sd1 - half_s, 0.0), sd1 + half_s
    sd2_lo, sd2_hi = max(sd2 - half_s, 0.0), sd2 + half_s

    # Point estimates at the truncated values, both flavors in one call.
    point = _ttest.recalc_independent_t(
        mean1, sd1, n1, mean2, sd2, n2,
        reported_p=None, reported_t=None, use_welch=None,
    )
    # The underlying t-test can decline (e.g. both SDs zero -- SE is zero and t
    # is undefined). Return its reason rather than raising: this tool has to be
    # answerable on every input recalc_independent_t accepts.
    if "calculated_t" not in point:
        return {"severity": "indeterminate",
                "explanation": point.get("error", "t-test is undefined for these inputs."),
                "methodology": "RIVETS requires a defined test statistic at the truncated inputs."}
    point_t_f = {f: abs(float(point["branches"][f]["t"])) for f in flavors_all}
    point_p_f = {f: float(point["branches"][f]["p_two_tailed"]) for f in flavors_all}
    point_t_abs = point_t_f[primary]
    point_p = point_p_f[primary]

    # Analytic extrema for |t|. Both flavors' t are monotone in |mean diff|
    # and in each SD, so the same corners extremize both; Welch's df moves
    # with the SDs, so p is additionally unioned with the Monte Carlo below.
    if mean1 >= mean2:
        m1_hi, m2_lo = mean1 + half_m, mean2 - half_m
        m1_lo, m2_hi = mean1 - half_m, mean2 + half_m
        # Means' intervals may overlap if mean1 ≈ mean2.
        min_diff = max(0.0, (mean1 - half_m) - (mean2 + half_m))
    else:
        m1_hi, m2_lo = mean1 - half_m, mean2 + half_m
        m1_lo, m2_hi = mean1 + half_m, mean2 - half_m
        min_diff = max(0.0, (mean2 - half_m) - (mean1 + half_m))

    extremum_max = _ttest.recalc_independent_t(
        m1_hi, sd1_lo, n1, m2_lo, sd2_lo, n2, use_welch=None,
    )
    extremum_min = _ttest.recalc_independent_t(
        m1_lo, sd1_hi, n1, m2_hi, sd2_hi, n2, use_welch=None,
    )
    t_min_f: dict[str, float] = {}
    t_max_f: dict[str, float] = {}
    p_min_f: dict[str, float] = {}
    p_max_f: dict[str, float] = {}
    for f in flavors_all:
        t_max_f[f] = abs(float(extremum_max["branches"][f]["t"]))
        p_min_f[f] = float(extremum_max["branches"][f]["p_two_tailed"])
        if min_diff == 0.0:
            # Overlapping mean intervals: |t| can reach 0 and p can reach 1.
            t_min_f[f] = 0.0
            p_max_f[f] = max(float(extremum_min["branches"][f]["p_two_tailed"]),
                             1.0 - 1e-12)
        else:
            t_min_f[f] = abs(float(extremum_min["branches"][f]["t"]))
            p_max_f[f] = float(extremum_min["branches"][f]["p_two_tailed"])

    # Monte Carlo over the joint interval, both flavors per draw.
    rng = random.Random(seed)
    n_match_t = {f: 0 for f in flavors_all}
    n_match_p = {f: 0 for f in flavors_all}
    sampled_ts: dict[str, list[float]] = {f: [] for f in flavors_all}
    sampled_ps: dict[str, list[float]] = {f: [] for f in flavors_all}
    for _ in range(num_samples):
        m1 = rng.uniform(mean1 - half_m, mean1 + half_m)
        m2 = rng.uniform(mean2 - half_m, mean2 + half_m)
        s1 = max(rng.uniform(sd1 - half_s, sd1 + half_s), 1e-12)
        s2 = max(rng.uniform(sd2 - half_s, sd2 + half_s), 1e-12)
        r = _ttest.recalc_independent_t(m1, s1, n1, m2, s2, n2, use_welch=None)
        for f in flavors_all:
            t_sample = abs(float(r["branches"][f]["t"]))
            p_sample = float(r["branches"][f]["p_two_tailed"])
            sampled_ts[f].append(t_sample)
            sampled_ps[f].append(p_sample)
            if reported_t is not None and _matches_at_precision(
                t_sample, abs(reported_t), decimals_t
            ):
                n_match_t[f] += 1
            if p_reported is not None and not p_is_threshold and _matches_at_precision(
                p_sample, p_reported, decimals_p
            ):
                n_match_p[f] += 1

    fraction_match_t_f = {
        f: (n_match_t[f] / num_samples if reported_t is not None else None)
        for f in flavors_all
    }
    fraction_match_p_f = {
        f: (n_match_p[f] / num_samples
            if (p_reported is not None and not p_is_threshold) else None)
        for f in flavors_all
    }

    # Every p we actually sampled IS achievable, so the analytic corners can
    # only be too narrow, never too wide: Welch's df moves with the SDs, so the
    # corner that extremizes |t| need not extremize p exactly. Widening to the
    # union keeps the interval honest and can only remove false accusations.
    for f in flavors_all:
        p_min_f[f] = min([p_min_f[f]] + sampled_ps[f])
        p_max_f[f] = max([p_max_f[f]] + sampled_ps[f])

    # Reported-t comparison: which flavors' achievable intervals contain it?
    t_explained = [
        f for f in flavors_all
        if reported_t is not None
        and t_min_f[f] - 1e-9 <= abs(reported_t) <= t_max_f[f] + 1e-9
    ]
    reported_t_in_range = bool(t_explained)

    # Reported-p comparison: accepted readings are flavor x tail; a one-tailed
    # report prints half the two-tailed p, so its achievable interval is the
    # two-tailed one divided by 2 (kept as SEPARATE intervals, not a hull).
    def _p_interval(f: str, tail: str) -> tuple[float, float]:
        k = 2.0 if tail == "one" else 1.0
        return (p_min_f[f] / k, p_max_f[f] / k)

    tails_all = ("two", "one")
    readings_all = [(f, tail) for f in flavors_all for tail in tails_all]
    readings_pinned = [
        (f, tail) for f in pinned_flavors for tail in pinned_tails
    ]
    outside_all = _reported_p_outside(
        p_reported, p_is_threshold,
        [_p_interval(f, tail) for f, tail in readings_all], decimals_p,
    )
    outside_pinned = _reported_p_outside(
        p_reported, p_is_threshold,
        [_p_interval(f, tail) for f, tail in readings_pinned], decimals_p,
    )

    point_matches_reported_t = any(
        _matches_at_precision(point_t_f[f], reported_t, decimals_t)
        for f in flavors_all
    )

    # Severity logic.
    severity = CONSISTENT
    flags: list[str] = []
    if reported_t is not None and not t_explained:
        severity = _worst(severity, HIGHLY_SUSPICIOUS)
        flags.append(
            f"Reported t = {reported_t} falls OUTSIDE the analytic intervals of "
            f"BOTH standard tests -- Welch [{t_min_f['welch']:.{decimals_t}f}, "
            f"{t_max_f['welch']:.{decimals_t}f}] and Student (pooled) "
            f"[{t_min_f['student']:.{decimals_t}f}, {t_max_f['student']:.{decimals_t}f}]; "
            "neither test can have produced that value from the printed "
            "mean/SD precision."
        )
    elif reported_t is not None and not any(f in t_explained for f in pinned_flavors):
        # The pinned flavor cannot reach it, but the other standard flavor
        # can: the DEBIT treatment for the alternative convention -- flag for
        # review, never at accusation grade.
        severity = _worst(severity, "suspicious")
        other = t_explained[0]
        flags.append(
            f"Reported t = {reported_t} is outside the {'/'.join(pinned_flavors)} "
            f"interval but INSIDE the {other} interval "
            f"[{t_min_f[other]:.{decimals_t}f}, {t_max_f[other]:.{decimals_t}f}]: "
            f"consistent with {other.capitalize()}'s test having been run instead "
            "of the stated one (e.g. the other software output line). A "
            "reporting-convention question, not evidence of fabrication."
        )
    # A paper that prints only a p-value is the case recalc used to cover. Its
    # reported p is unreachable on exactly the same evidence as an unreachable
    # t, so it carries the same severity.
    if outside_all:
        severity = _worst(severity, HIGHLY_SUSPICIOUS)
        bound = "bound" if p_is_threshold else "value"
        flags.append(
            f"Reported p {bound} = {reported_p} is UNREACHABLE given the achievable "
            f"intervals implied by the printed precision of the means/SDs -- "
            f"two-tailed [{min(p_min_f.values()):.3g}, {max(p_max_f.values()):.3g}], "
            f"one-tailed [{min(p_min_f.values()) / 2:.3g}, {max(p_max_f.values()) / 2:.3g}], "
            "under Welch's AND Student's test; no rounding of the printed "
            "descriptives yields it under any standard reading."
        )
    elif p_reported is not None and outside_pinned:
        severity = _worst(severity, "suspicious")
        explaining = [
            f"{f} {tail}-tailed" for f, tail in readings_all
            if not _reported_p_outside(
                p_reported, p_is_threshold, [_p_interval(f, tail)], decimals_p
            )
        ]
        flags.append(
            f"Reported p = {reported_p} is outside the stated reading "
            f"(flavor={'/'.join(pinned_flavors)}, tail={'/'.join(pinned_tails)}) "
            f"but IS reachable under: {', '.join(explaining)}. A reporting-"
            "convention question, not evidence of fabrication."
        )
    for f in flavors_all:
        t_range_f = t_max_f[f] - t_min_f[f]
        if (
            reported_t is not None
            and _matches_at_precision(point_t_f[f], abs(reported_t), decimals_t)
            and fraction_match_t_f[f] is not None
            and t_range_f > 10 ** (-decimals_t)  # wider than 1 reported digit
            and fraction_match_t_f[f] < 0.05
        ):
            severity = _worst(severity, HIGHLY_SUSPICIOUS)
            flags.append(
                f"RIVETS hit: reported t exactly equals the {f.capitalize()} value "
                f"computed from the truncated descriptives (t = "
                f"{point_t_f[f]:.{decimals_t}f}), but only "
                f"{100 * fraction_match_t_f[f]:.1f}% of Monte Carlo samples in the "
                "joint truncation interval reproduce that value. Consistent with "
                "hand-calculation from rounded inputs."
            )
            break

    t_min = min(t_min_f[f] for f in pinned_flavors)
    t_max = max(t_max_f[f] for f in pinned_flavors)
    # Range that judges "uninformative inputs" is the rounding-driven width of
    # a single flavor, not the hull across flavors (whose width reflects the
    # Welch/Student disagreement, not the printed precision).
    t_range = max(t_max_f[f] - t_min_f[f] for f in pinned_flavors)
    p_min = min(p_min_f[f] for f in pinned_flavors)
    p_max = max(p_max_f[f] for f in pinned_flavors)
    p_range = p_max - p_min

    if t_range > 0.5 and severity == CONSISTENT:
        # Big range across reported precision → "uninformative" zone.
        flags.append(
            f"Wide t interval ({t_min:.{decimals_t}f} to {t_max:.{decimals_t}f}; "
            f"range {t_range:.{decimals_t}f}). Reported precision of the inputs "
            "is insufficient to pin down the test statistic."
        )
        severity = "suspicious"

    explanation = (
        " ".join(flags) if flags else
        f"Reported t/p (if any) is consistent with the truncation interval of "
        f"a standard reading ({' / '.join(pinned_flavors)}) and shows no "
        f"RIVETS signature."
    )

    all_samples = [t for f in pinned_flavors for t in sampled_ts[f]]
    fraction_match_t = (
        max(fraction_match_t_f[f] for f in pinned_flavors)
        if reported_t is not None else None
    )
    fraction_match_p = (
        max(fraction_match_p_f[f] for f in pinned_flavors)
        if (p_reported is not None and not p_is_threshold) else None
    )

    return {
        "severity": severity,
        "explanation": explanation,
        "point_t_at_truncated": point_t_abs,
        "point_p_at_truncated": point_p,
        "t_min": t_min,
        "t_max": t_max,
        "t_range": t_range,
        "p_min": p_min,
        "p_max": p_max,
        "p_range": p_range,
        "reported_t": reported_t,
        "reported_t_in_range": reported_t_in_range,
        "reported_t_explained_by": t_explained if reported_t is not None else None,
        "reported_p": reported_p,
        "reported_p_is_threshold": p_is_threshold if reported_p is not None else None,
        "reported_p_in_range": (None if reported_p is None else not outside_all),
        "point_matches_reported_t": point_matches_reported_t,
        "flavors": {
            f: {
                "point_t": point_t_f[f],
                "point_p": point_p_f[f],
                "t_min": t_min_f[f],
                "t_max": t_max_f[f],
                "p_min": p_min_f[f],
                "p_max": p_max_f[f],
            }
            for f in flavors_all
        },
        "monte_carlo": {
            "num_samples": num_samples,
            "fraction_match_reported_t": fraction_match_t,
            "fraction_match_reported_p": fraction_match_p,
            "fraction_match_reported_t_by_flavor": fraction_match_t_f,
            "sampled_t_min": min(all_samples) if all_samples else None,
            "sampled_t_max": max(all_samples) if all_samples else None,
        },
        "inputs": {
            "mean1": mean1, "sd1": sd1, "n1": n1,
            "mean2": mean2, "sd2": sd2, "n2": n2,
            "decimals_mean": decimals_mean, "decimals_sd": decimals_sd,
            "use_welch": use_welch, "p_tail": p_tail,
        },
        "methodology": (
            "RIVETS independent-t: each reported descriptive sits in a "
            f"truncation interval (means ±{half_m}, SDs ±{half_s}). "
            "Analytic [t_min, t_max] computed by extremizing the t-formula at "
            "the appropriate corners, separately for Welch's and Student's "
            "(pooled) test -- both are standard readings of the same summary "
            "row. Monte Carlo samples uniformly from the joint interval and "
            "reports the hit rate at the reported t/p precision. Point match "
            "at the truncated values plus low MC hit rate is the classical "
            "hand-calculation signature. A reported t OR p is flagged at "
            "accusation grade only when it is outside the achievable interval "
            "of EVERY standard reading (flavor x tail); outside only the "
            "caller-pinned reading it is flagged as `suspicious` with the "
            "explaining convention named. A reported p given as a bound "
            "('p < .001') is refuted only if the smallest achievable p under "
            "every accepted reading exceeds that bound."
        ),
    }


# =============================================================================
# One-way ANOVA
# =============================================================================

#: Above this many groups the vertex enumeration is skipped. 2^12 = 4096 ANOVA
#: evaluations is already more than the Monte Carlo pass; beyond it the cost
#: doubles per group for a correction that shrinks as k grows (more groups means
#: more interior averaging, so the sampler gets closer to the corner on its own).
_MAX_CORNER_GROUPS = 12


def _anova_corner_extremes(means: list[float], sds: list[float], ns: list[int],
                           half_m: float, half_s: float) -> tuple[list[float], list[float]]:
    """F and p at the corners of the rounding box, where the extremes actually live.

    Monte Carlo samples the box's interior and reaches a vertex with probability
    zero, so the achievable interval it reports is too NARROW -- and a too-narrow
    interval is what turns a reachable p into "UNREACHABLE". Returns whatever the
    corners add; the caller unions it with the sampled range, so this can only
    ever WIDEN the interval and therefore only ever remove an accusation.

    Only the F-maximising side needs enumerating. F is maximal at a vertex of the
    means box with every SD at its floor (between-group SS is convex in the
    means; within-group SS is minimal at the SD lower bounds), and that is the
    p-minimising side -- the accusing one. The opposite extreme is p = 1,
    attained wherever the mean intervals admit a common value, which the sampler
    finds without help.
    """
    k = len(means)
    if k < 2 or k > _MAX_CORNER_GROUPS or k != len(sds) or k != len(ns):
        return [], []
    lo_sds = [max(s - half_s, 1e-12) for s in sds]
    fs: list[float] = []
    ps: list[float] = []
    for bits in range(1 << k):
        corner = [m + (half_m if (bits >> i) & 1 else -half_m)
                  for i, m in enumerate(means)]
        try:
            r = _anova.recalc_one_way_anova(corner, lo_sds, ns)
            fs.append(float(r["calculated_f"]))
            ps.append(float(r["calculated_p"]))
        except Exception:  # noqa: BLE001 -- a corner we cannot evaluate is simply not offered
            continue
    return fs, ps


def rivets_anova(
    means: list[float],
    sds: list[float],
    ns: list[int],
    reported_f: Optional[float] = None,
    reported_p: Optional[float] = None,
    decimals_mean: int = 2,
    decimals_sd: int = 2,
    decimals_f: int = 3,
    decimals_p: int = 3,
    p_is_threshold: Optional[bool] = None,
    num_samples: int = 5_000,
    seed: int = 0,
    sampling: str = "simple_random",
) -> dict:
    """RIVETS for one-way ANOVA. Same logic as the t variant; F is bounded
    via Monte Carlo since analytic extrema for k > 2 groups are messy."""
    refusal = survey_refusal("rivets_anova", sampling)
    if refusal is not None:
        return refusal
    k = len(means)
    if not (k == len(sds) == len(ns)):
        return {"severity": "indeterminate",
                "explanation": "means/sds/ns must have the same length."}
    if k < 2:
        return {"severity": "indeterminate",
                "explanation": "Need at least 2 groups."}
    if any(n < 2 for n in ns):
        return {"severity": "indeterminate",
                "explanation": "All groups need n ≥ 2."}

    guard = refuse_if_nonfinite(means=means, sds=sds, ns=ns,
                                reported_f=reported_f, reported_p=reported_p)
    if guard is not None:
        return guard

    # A reported p may arrive as a bound ("p < .001"); see _reported_p_outside.
    p_reported, _parsed_threshold = _ttest._parse_reported_p(reported_p)
    # AN EXPLICIT DECLARATION WINS OVER THE LITERAL, and it has to, because the
    # literal cannot carry the fact. `_parse_reported_p` reads a bound off the
    # STRING "p < .001"; the registry types `reported_p` as a float, so over
    # MCP -- which is every real call -- the string form is UNREACHABLE and a
    # threshold always arrived looking like an exact value. `_reported_p_outside`
    # names that case "a large false-accusation class rather than a detection",
    # and until now it was the only reading a caller could get.
    p_is_threshold = _parsed_threshold if p_is_threshold is None else bool(p_is_threshold)
    if reported_p is None:
        p_reported = None

    half_m = _half_width(decimals_mean)
    half_s = _half_width(decimals_sd)

    # Point estimate.
    point = _anova.recalc_one_way_anova(means, sds, ns)
    # Same as the t variant: MS_within of zero leaves F undefined, and a
    # declined answer beats a traceback.
    if "calculated_f" not in point:
        return {"severity": "indeterminate",
                "explanation": point.get("error", "ANOVA is undefined for these inputs."),
                "methodology": "RIVETS requires a defined test statistic at the truncated inputs."}
    point_f = float(point["calculated_f"])
    point_p = float(point["calculated_p"])

    rng = random.Random(seed)
    sampled_fs: list[float] = []
    sampled_ps: list[float] = []
    n_match_f = 0
    n_match_p = 0
    for _ in range(num_samples):
        m_samp = [rng.uniform(m - half_m, m + half_m) for m in means]
        s_samp = [max(rng.uniform(s - half_s, s + half_s), 1e-12) for s in sds]
        r = _anova.recalc_one_way_anova(m_samp, s_samp, ns)
        f_val = float(r["calculated_f"])
        p_val = float(r["calculated_p"])
        sampled_fs.append(f_val)
        sampled_ps.append(p_val)
        if reported_f is not None and _matches_at_precision(f_val, reported_f, decimals_f):
            n_match_f += 1
        if p_reported is not None and not p_is_threshold and _matches_at_precision(
            p_val, p_reported, decimals_p
        ):
            n_match_p += 1

    # The point estimate at the truncated values is achievable by construction,
    # so it belongs in the range even if no MC draw landed there. Including it
    # can only widen the interval, i.e. only ever removes an accusation.
    # THE CORNER THE SAMPLER NEVER VISITS. Monte Carlo draws uniformly from the
    # interior of the rounding box, and the extreme of F lies on a VERTEX, which
    # a finite sample reaches with probability zero. The gap is not academic:
    #
    #   rivets_anova(means=[1.60]*3, sds=[0.07]*3, ns=[150]*3, reported_p=0.35)
    #     -> highly_suspicious, "Reported p = 0.35 is UNREACHABLE given the
    #        achievable interval [0.366, 1]"
    #
    # while the exact corner gives p = 0.307, so 0.35 is achievable and the
    # accusation is OUR sampling shortfall stated as a fact about the paper.
    # Measured MC-vs-corner gap over the configurations tested: 0.059 at n=150,
    # 0.028 at n=30, and in one case the corner crosses 0.05 where MC did not.
    #
    # Why a vertex: between-group SS is a positive semidefinite quadratic form
    # in the means, hence CONVEX, and a convex function over a box attains its
    # maximum at a corner. Within-group SS depends only on the SDs and is
    # minimised at their lower bounds. F is maximal, and therefore p minimal,
    # at a means-vertex with every SD at its floor. 2^k evaluations.
    corner_fs, corner_ps = _anova_corner_extremes(means, sds, ns, half_m, half_s)
    f_min = min(sampled_fs + [point_f] + corner_fs)
    f_max = max(sampled_fs + [point_f] + corner_fs)
    p_min = min(sampled_ps + [point_p] + corner_ps)
    p_max = max(sampled_ps + [point_p] + corner_ps)
    f_range = f_max - f_min
    p_range = p_max - p_min

    fraction_match_f = (n_match_f / num_samples) if reported_f is not None else None
    fraction_match_p = (
        (n_match_p / num_samples) if (p_reported is not None and not p_is_threshold) else None
    )
    point_matches_reported_f = _matches_at_precision(point_f, reported_f, decimals_f)
    reported_f_in_range = (
        reported_f is not None and (f_min - 1e-9 <= reported_f <= f_max + 1e-9)
    )
    reported_p_outside = _reported_p_outside(
        p_reported, p_is_threshold, [(p_min, p_max)], decimals_p
    )

    severity = CONSISTENT
    flags: list[str] = []
    if reported_f is not None and not reported_f_in_range:
        severity = _worst(severity, HIGHLY_SUSPICIOUS)
        flags.append(
            f"Reported F = {reported_f} falls OUTSIDE the Monte Carlo F range "
            f"[{f_min:.{decimals_f}f}, {f_max:.{decimals_f}f}]."
        )
    # An ANOVA reported as "F(2, 87) = ..., p = ..." is often quoted p-only in
    # a results sentence. That p gets the same treatment as an out-of-range F.
    if reported_p_outside:
        severity = _worst(severity, HIGHLY_SUSPICIOUS)
        bound = "bound" if p_is_threshold else "value"
        flags.append(
            f"Reported p {bound} = {reported_p} is UNREACHABLE given the achievable "
            f"interval [{p_min:.3g}, {p_max:.3g}] implied by the printed precision of "
            "the group means/SDs."
        )
    if (
        point_matches_reported_f
        and fraction_match_f is not None
        and f_range > 10 ** (-decimals_f)
        and fraction_match_f < 0.05
    ):
        severity = _worst(severity, HIGHLY_SUSPICIOUS)
        flags.append(
            f"RIVETS hit: reported F exactly equals point estimate "
            f"({point_f:.{decimals_f}f}) but only "
            f"{100 * fraction_match_f:.1f}% of MC samples reproduce it. "
            "Hand-calculation signature."
        )

    explanation = " ".join(flags) if flags else "No RIVETS signature."

    return {
        "severity": severity,
        "explanation": explanation,
        "point_f_at_truncated": point_f,
        "point_p_at_truncated": point_p,
        "f_min": f_min, "f_max": f_max, "f_range": f_range,
        "p_min": p_min, "p_max": p_max, "p_range": p_range,
        "reported_f": reported_f,
        "reported_f_in_range": reported_f_in_range,
        "reported_p": reported_p,
        "reported_p_is_threshold": p_is_threshold if reported_p is not None else None,
        "reported_p_in_range": (None if reported_p is None else not reported_p_outside),
        "point_matches_reported_f": point_matches_reported_f,
        "monte_carlo": {
            "num_samples": num_samples,
            "fraction_match_reported_f": fraction_match_f,
            "fraction_match_reported_p": fraction_match_p,
        },
        "inputs": {
            "means": means, "sds": sds, "ns": ns,
            "decimals_mean": decimals_mean, "decimals_sd": decimals_sd,
        },
        "methodology": (
            "RIVETS one-way ANOVA: Monte Carlo samples uniformly from the "
            "joint truncation interval (means ±half-rounding, SDs ±half-"
            "rounding) and reports F-range, p-range, and exact-match hit "
            "rates at the reported F/p precision. Hand-calculation from "
            "truncated inputs typically lands at the point estimate; software "
            "on raw data does not. A reported F OR a reported p outside its "
            "achievable range is flagged at the same severity; a reported p "
            "given as a bound ('p < .001') is refuted only if the smallest "
            "achievable p exceeds that bound."
        ),
    }
