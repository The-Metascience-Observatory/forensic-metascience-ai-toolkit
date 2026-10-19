"""
Cheap heuristic flags from Heathers (2025) "More Techniques and Observations".

These are not mathematical impossibility proofs — they're triage signals that
experienced analysts use to direct deeper investigation. Each flag is documented
with its rationale and the section of the intro that motivates it.
"""

from __future__ import annotations

import math
from typing import Optional

from . import anova as _anova
from . import rivets as _rivets
from . import rounding as _rounding
from .severity import refuse_if_nonfinite


def flag_round_n(
    ns: list[int],
    moderate_modulus: int = 50,
    strong_modulus: int = 100,
) -> dict:
    """Flag suspiciously round sample sizes (Heathers §"Big round sample sizes").

    Heathers: "a lot of fabricated papers have sample sizes that are weirdly
    round — n=100, n=300, n=400". The signal is DESCRIPTIVE, not diagnostic,
    and the severity ladder now says so -- `suspicious` is the CEILING.

    - "suspicious": the actual Heathers signature -- three or more reported
      sizes, at least two distinct, all divisible by the modulus. The rulebook
      lists "suspiciously round Ns" as its own example of `suspicious` and
      (rule 8) classes them as individually weak signals that escalate ONLY on
      co-occurrence with stronger findings, so this flag alone never exceeds it.
    - "indeterminate": every size is round but fewer than three, or all one
      repeated value -- indistinguishable from an ordinary designed recruitment
      target. Measured with this repo's own tool: required_n for a two-sample t
      at d=0.4 is EXACTLY 100 per arm, so an honest block-randomised trial
      reports [100, 100] -- which this used to brand `highly_suspicious`.
    - "consistent": at least one n breaks the pattern.

    A flag from this tool is a prompt to LOOK, never a finding on its own.

    Args:
        ns: List of cell / group / total sample sizes claimed in the paper.
        moderate_modulus: Round-number threshold for the pattern.
        strong_modulus: Stricter roundness, recorded in the breakdown; both
            tiers cap at `suspicious`.
    """
    if moderate_modulus < 1 or strong_modulus < 1:
        return {
            "severity": "indeterminate",
            "explanation": (
                f"Not evaluated: moduli must be positive integers (got "
                f"moderate={moderate_modulus}, strong={strong_modulus}). A "
                "configuration error on our side, not a fact about the paper."
            ),
            "methodology": "flag_round_n: modulus guard.",
            "ns": [],
        }

    # A sample size is a positive whole number. Anything else in `ns` is OUR
    # extraction artefact: the old `int(n)` coercion crashed on NaN/inf and --
    # worse -- truncated 100.7 to 100 and then flagged the roundness it had
    # just manufactured, a `suspicious` verdict about values the paper never
    # printed. Integral floats (100.0, as JSON numbers arrive) are fine.
    clean: list[int] = []
    bad: list = []
    for n in ns:
        if n is None:
            continue
        if isinstance(n, bool):
            bad.append(n)
            continue
        if isinstance(n, int):
            v = n
        elif isinstance(n, float):
            if not math.isfinite(n) or not n.is_integer():
                bad.append(n)
                continue
            v = int(n)
        elif isinstance(n, str):
            try:
                v = int(n.strip())
            except ValueError:
                bad.append(n)
                continue
        else:
            # Integer-like objects (e.g. numpy integers) pass; anything whose
            # int() conversion changes its value is refused, not truncated.
            try:
                v = int(n)
            except (TypeError, ValueError, OverflowError):
                bad.append(n)
                continue
            if v != n:
                bad.append(n)
                continue
        if v < 1:
            bad.append(n)
            continue
        clean.append(v)
    if bad:
        return {
            "severity": "indeterminate",
            "explanation": (
                f"Not evaluated: {bad!r} is not a usable sample size (a sample "
                "size is a positive whole number). A fractional, zero, negative "
                "or non-finite n is our extraction artefact, not a fact about "
                "the paper, so no roundness claim is made. Re-read the values "
                "and call again."
            ),
            "methodology": "flag_round_n: input validation, no math.",
            "ns": [],
        }
    ns = clean
    if not ns:
        return {
            "severity": "indeterminate",
            "explanation": "No sample sizes provided.",
            "methodology": "flag_round_n: pure heuristic, no math.",
            "ns": [],
        }

    breakdown = []
    for n in ns:
        breakdown.append({
            "n": n,
            "divisible_by_10": n % 10 == 0,
            "divisible_by_moderate": n % moderate_modulus == 0,
            "divisible_by_strong": n % strong_modulus == 0,
        })

    all_strong = all(b["divisible_by_strong"] for b in breakdown)
    all_moderate = all(b["divisible_by_moderate"] for b in breakdown)
    n_unique = len(set(ns))

    # A descriptive heuristic needs more than a trivial count before it may say
    # anything. Heathers' signature is SEVERAL DISTINCT round sizes; one or two,
    # or one round target repeated per arm, is exactly what an honest a-priori
    # recruitment target looks like (required_n two-sample t at d=0.4 -> 100/arm).
    enough_to_flag = len(ns) >= 3 and n_unique >= 2
    modulus = strong_modulus if all_strong else moderate_modulus

    if all_moderate and enough_to_flag:
        severity = "suspicious"
        explanation = (
            f"All {len(ns)} reported sample sizes are multiples of {modulus} "
            f"({sorted(ns)}). Heathers notes this pattern in fabricated papers, "
            "but it is descriptive, not diagnostic -- a prompt to look closer. "
            "Escalate only if it co-occurs with stronger findings (rule 8)."
        )
    elif all_moderate:
        reason = ("fewer than three sizes were reported" if len(ns) < 3
                  else "they are all the same repeated value")
        severity = "indeterminate"
        explanation = (
            f"The reported sample size(s) ({sorted(ns)}) are all multiples of "
            f"{modulus}, but {reason} -- indistinguishable from an ordinary "
            "designed recruitment target (an a-priori power analysis at d = 0.4 "
            "prescribes exactly 100 per arm). Descriptive note only; no adverse "
            "signal is claimed."
        )
    else:
        severity = "consistent"
        explanation = (
            f"Sample sizes show some non-round variation ({sorted(ns)}); no "
            "round-N flag."
        )

    return {
        "severity": severity,
        "explanation": explanation,
        "ns": ns,
        "n_unique": n_unique,
        "all_divisible_by_moderate": all_moderate,
        "all_divisible_by_strong": all_strong,
        "breakdown": breakdown,
        "moderate_modulus": moderate_modulus,
        "strong_modulus": strong_modulus,
        "methodology": (
            "Heuristic only -- descriptive, not diagnostic, so its ceiling is "
            "`suspicious` (rule 8: round ns are individually weak signals that "
            f"escalate only on co-occurrence). Flags when at least 3 reported "
            f"ns (2+ distinct) are all divisible by {moderate_modulus} (or "
            f"{strong_modulus}); fewer all-round sizes are `indeterminate`, "
            "because an honest designed recruitment target produces the same "
            "pattern. Pattern noted in Heathers (2025) §'Big round sample sizes'."
        ),
    }


def flag_uninformative_stat(
    means: list[float],
    sds: list[float],
    ns: list[int],
    reported_p: Optional[float] = None,
    decimals_mean: int = 2,
    decimals_sd: int = 2,
    decimals_p: int = 3,
    significance_threshold: float = 0.05,
    p_range_warn: float = 0.5,
    num_samples: int = 3_000,
    seed: int = 0,
) -> dict:
    """Flag NHST comparisons where reported precision is too coarse to pin
    down the result (Heathers §"Uninformative statistics", Cheng 2009 example).

    The classic case: three groups all reported as "1.60 (0.07)" with an
    accompanying p-value. At the literal point estimate, F = 0 and p = 1, so
    the reported p must come from somewhere in the truncation interval. If
    the interval-implied p-range crosses the significance threshold, the
    "comparison" is uninformative — it could fairly be reported anywhere
    from "no difference" to "statistically significant".

    This wraps rivets_anova and adds:
    - whether the p-range straddles `significance_threshold`
    - whether the reported p falls inside the implied range
    - a flag if the precision-implied p-range is wider than `p_range_warn`.
    """
    # `reported_p` is judged HERE, directionally, and only here. It must be a
    # real p-value: a NaN, an infinity, or a value outside [0, 1] is our
    # mis-parse (a percentage, a test statistic, a footnote marker), and
    # comparing it would state our artefact as a note about the paper.
    if reported_p is not None:
        if isinstance(reported_p, bool) or not isinstance(reported_p, (int, float)):
            return {
                "severity": "indeterminate",
                "is_uninformative": None,
                "explanation": (
                    f"Not evaluated: reported_p={reported_p!r} is not a number. "
                    "Pass the numeric bound of a threshold report ('p < .001' "
                    "-> 0.001) rather than a string."
                ),
                "methodology": "flag_uninformative_stat: input validation.",
            }
        guard = refuse_if_nonfinite(reported_p=reported_p)
        if guard is not None:
            return {**guard, "is_uninformative": None}
        if not (0.0 <= reported_p <= 1.0):
            return {
                "severity": "indeterminate",
                "is_uninformative": None,
                "explanation": (
                    f"Not evaluated: reported_p={reported_p} is outside [0, 1], "
                    "so it is not a p-value -- almost certainly a value we "
                    "mis-read (a percentage? a test statistic?). No claim about "
                    "the paper is made from it."
                ),
                "methodology": "flag_uninformative_stat: input validation.",
            }

    # reported_p is deliberately NOT forwarded to rivets_anova. Its two-sided
    # range check escalates an UNDER-claimed p (the honest "p < .001"-as-bound
    # case) to `highly_suspicious`, and that verdict rode along inside
    # `underlying_rivets` -- an accusation shipped in the same payload whose
    # top line said `consistent`. The directional judgement below is the only
    # reported-p verdict this result carries.
    riv = _rivets.rivets_anova(
        means=means, sds=sds, ns=ns,
        reported_p=None, reported_f=None,
        decimals_mean=decimals_mean, decimals_sd=decimals_sd,
        decimals_p=decimals_p,
        num_samples=num_samples, seed=seed,
    )

    if riv.get("severity") == "indeterminate":
        return {**riv, "is_uninformative": None}

    p_min = riv["p_min"]
    p_max = riv["p_max"]
    f_min = riv["f_min"]
    f_max = riv["f_max"]

    # EXACT corner search. rivets_anova bounds p by Monte Carlo, and random
    # draws never visit the corner of the truncation box, so its p_min
    # overstates the true achievable minimum -- measured on [1.60]x3 (0.07),
    # n=150x3: MC minimum 0.366 vs corner 0.307. Any reported p in that gap
    # was branded "SMALLER than any p the printed values can produce": our
    # sampling shortfall in the grammar of a claim about the paper. The
    # between-group sum of squares is a convex quadratic in the means, so F is
    # maximised at a VERTEX of the means box, with every SD at its lower
    # bound; enumerating the vertices makes the minimum exact.
    half_m = _rounding.half_width(decimals_mean)
    half_s = _rounding.half_width(decimals_sd)
    k = len(means)
    corner_searched = k <= 12                     # 2^k evaluations
    if corner_searched:
        lo_sds = [max(s - half_s, 1e-12) for s in sds]
        for bits in range(2 ** k):
            m_corner = [m + half_m if (bits >> i) & 1 else m - half_m
                        for i, m in enumerate(means)]
            rr = _anova.recalc_one_way_anova(m_corner, lo_sds, ns)
            if "calculated_p" in rr:
                p_min = min(p_min, float(rr["calculated_p"]))
                f_max = max(f_max, float(rr["calculated_f"]))
    if max(m - half_m for m in means) <= min(m + half_m for m in means):
        # Every mean interval shares a common point, so all true means can
        # coincide: F = 0 and p = 1 are exactly achievable.
        p_max = 1.0
        f_min = 0.0
    p_range = p_max - p_min

    straddles_threshold = (p_min <= significance_threshold <= p_max)
    # Interval-vs-interval, and DIRECTIONAL. The reported p asserts its own
    # rounding interval [reported_p ± half], and the achievable p over the mean/SD
    # rounding box is [p_min, p_max]. Only an OVER-claim -- a reported p smaller
    # than anything the printed statistics can produce -- is flagged. An
    # UNDER-claim (a reported p LARGER than the achievable maximum) is the
    # conservative direction, dominated by threshold reporting ("p < .001" passed
    # as its bound) and corrected/different tests, NOT fabrication, so it never
    # escalates. And an over-claim is only ASSERTED when the corner search ran:
    # a Monte-Carlo-only minimum is an overestimate, and calling a p below it
    # "unreachable" states our sampling shortfall as the paper's fabrication.
    _half_p = _rounding.half_width(decimals_p)
    overclaims = (reported_p is not None and corner_searched
                  and (reported_p + _half_p < p_min))
    underclaims = reported_p is not None and (reported_p - _half_p > p_max)
    reported_in_range = reported_p is not None and not overclaims and not underclaims
    is_uninformative = straddles_threshold or p_range > p_range_warn

    flags: list[str] = []
    severity = "consistent"
    if straddles_threshold:
        severity = "suspicious"
        flags.append(
            f"P-range [{p_min:.{decimals_p}f}, {p_max:.{decimals_p}f}] straddles "
            f"the significance threshold {significance_threshold}. The reported "
            "precision of the inputs is insufficient to determine whether the "
            "comparison is significant."
        )
    if p_range > p_range_warn:
        if severity == "consistent":
            severity = "suspicious"
        flags.append(
            f"Wide p-range ({p_range:.{decimals_p}f}). Effectively any p in "
            f"[{p_min:.{decimals_p}f}, {p_max:.{decimals_p}f}] is consistent "
            "with the printed mean/SD precision."
        )
    if overclaims:
        # A FLAG, never a finding: `suspicious` is this tool's ceiling.
        # Heathers' verdict on this whole category is "not necessarily an
        # error" / "not an error in its own right ... it can be regarded as a
        # flag", and the comparison rests on an assumption this tool cannot
        # verify -- that the p belongs to a plain one-way ANOVA on exactly
        # these groups. The old `highly_suspicious` branch also announced
        # "the reported significance exceeds what the statistics support"
        # even when the reported p was nowhere near significant.
        severity = "suspicious"
        flags.append(
            f"Reported p = {reported_p} is below the smallest p "
            f"({p_min:.{decimals_p}f}) that a PLAIN ONE-WAY ANOVA on these "
            "printed means/SDs can produce at their stated precision (exact "
            "corner search included). This is a flag to look closer, not a "
            "finding: the ordinary explanations are that the p belongs to a "
            "different or adjusted test (Welch, Kruskal-Wallis, ANCOVA, "
            "repeated measures, a covaried model) or that a value was "
            "transcribed wrongly -- this tool assumes a plain one-way ANOVA "
            "and cannot tell those apart. For the accusation-grade treatment "
            "of an unreachable reported p, run rivets_anova with the reported "
            "p and the test identity established."
        )
    elif underclaims:
        # Noted, not flagged: the reported p is LESS significant than achievable,
        # the conservative direction. A threshold p reported as its bound, or a
        # corrected/different test, explains it; it is not evidence of fabrication.
        flags.append(
            f"Reported p = {reported_p} is larger than the achievable maximum "
            f"{p_max:.{decimals_p}f}; the likeliest cause is a threshold p reported as "
            "its bound (e.g. 'p < .001') or a corrected/different test, so it is noted "
            "rather than flagged."
        )
    elif (reported_p is not None and not corner_searched
          and (reported_p + _half_p < p_min)):
        # Too many groups to enumerate corners: the Monte Carlo minimum is not
        # a bound, so no over-claim is asserted -- disclosed instead.
        flags.append(
            f"Reported p = {reported_p} is below the MONTE CARLO minimum "
            f"({p_min:.{decimals_p}f}), but with {k} groups the exact corner "
            "search was skipped and the sampled minimum overstates the true "
            "one, so no over-claim is asserted."
        )

    explanation = " ".join(flags) if flags else (
        "Reported precision is sufficient to pin down the test outcome."
    )

    return {
        "severity": severity,
        "explanation": explanation,
        "is_uninformative": is_uninformative,
        "p_min": p_min, "p_max": p_max, "p_range": p_range,
        "f_min": f_min, "f_max": f_max,
        "corner_search_performed": corner_searched,
        "straddles_significance_threshold": straddles_threshold,
        "significance_threshold": significance_threshold,
        "reported_p": reported_p,
        "reported_p_in_range": reported_in_range,
        "reported_p_overclaims": overclaims,
        "reported_p_underclaims": underclaims,
        "underlying_rivets": riv,
        "methodology": (
            "flag_uninformative_stat: runs rivets_anova on the reported "
            "means/SDs/ns for a Monte Carlo p-range implied by the input "
            f"precision (means ±{0.5 * 10 ** -decimals_mean}, SDs ±"
            f"{0.5 * 10 ** -decimals_sd}), then makes the achievable minimum "
            "EXACT by corner search (the between-group sum of squares is "
            "convex in the means, so F is maximal at a vertex of the means "
            "box with all SDs at their lower bound; sampling alone never "
            "visits the corner and overstated the minimum). Flags when the "
            f"p-range straddles the significance threshold "
            f"{significance_threshold}, exceeds width {p_range_warn}, or the "
            "reported p is below the exact achievable minimum. ASSUMES a "
            "plain one-way ANOVA on exactly these groups; a different or "
            "adjusted test voids the comparison, which is why the ceiling is "
            "`suspicious` -- per Heathers §'Uninformative statistics', this "
            "category is a flag, 'not an error in its own right', never a "
            "finding. The accusation-grade reported-p check is rivets_anova."
        ),
    }
