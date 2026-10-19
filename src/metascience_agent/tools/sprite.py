"""
SPRITE (Sample Parameter Reconstruction via Iterative Techniques)

Reconstruct possible sample distributions from mean and SD to reveal
unusual patterns like bimodal distributions.
"""

import math
import random

import numpy as np

from . import rounding


def _decimals_of(value: float | str) -> int:
    """Number of decimals a value was REPORTED to.

    Precision must come from the literal, not a default. A mean printed as
    "1.7" is one decimal, so its rounding interval is +/-0.05; assuming two
    decimals shrinks that tenfold and discards totals the paper genuinely
    permits.
    """
    text = str(value).strip()
    if "." in text:
        return len(text.split(".", 1)[1].rstrip())
    return 0


def _grim_consistent_sums(mean: float, n: int, decimals: int = 2,
                          convention: str = "round_half") -> list[int]:
    """EVERY integer total whose mean rounds back to the reported mean.

    Returns the candidates rather than a bool. The previous version checked the
    neighbours of `round(mean*n)` and then threw the answer away, so the caller
    tested only `round(mean*n)` -- and declared `impossible` whenever that one
    total failed, even when another admissible total worked. That produced
    false accusations on real data (e.g. eight 1s and twenty-two 2s reported as
    M=1.7, SD=0.4: total 52 is admissible at 1 dp, but only 51 was ever tried).
    """
    lo, hi = rounding.window(mean, decimals, convention)
    centre = round(mean * n)
    span = max(2, int(n * (hi - lo)) + 2)
    return [
        s for s in range(centre - span, centre + span + 1)
        if lo - 1e-9 <= s / n < hi - 1e-12
    ]


def _mean_is_grim_consistent(mean: float, n: int, target_sum: int, decimals: int = 2) -> bool:
    """True if some integer total yields a mean that rounds back to `mean`."""
    return bool(_grim_consistent_sums(mean, n, decimals))


def _sd_window_feasible(
    target_sum: int, n: int, sd: float, decimals_sd: int, scale_min: int, scale_max: int,
    apply_bounds: bool = True, ddof: int = 1, convention: str = "round_half",
) -> tuple[bool, str]:
    """Analytically decide whether ANY integer sample can produce the reported SD.

    For integers with a fixed total S, the sum of squares Q is an integer and
        var = (Q - S^2/n) / (n - 1)
    so the reported SD (at its rounding precision) pins Q to a narrow window.
    Two hard constraints then apply:

    1. Q must be an INTEGER in that window.
    2. Q = sum(x_i^2) and S = sum(x_i), and x^2 = x (mod 2), so **Q = S (mod 2)**.
       (This is the same parity constraint GRIMMER uses.)

    If no admissible Q survives, no sample exists -- a *proof*, not a failed
    search. Distinguishing this from search exhaustion is what makes a SPRITE
    "no solution" usable as evidence.

    `apply_bounds=False` keeps ONLY constraints 1 and 2, which hold for any
    integers whatever. The caller reruns the screen that way to find out whether
    an infeasibility is arithmetic (bound-free evidence) or merely a consequence
    of scale limits it supplied itself.
    """
    # THE CONVENTION DECIDES THE WINDOW, and a first version of this function
    # knew only round-half. A truncating reporter prints 2.38 for a true
    # 2.3850589, which sits 0.0000589 ABOVE the round-half ceiling of 2.385 --
    # so the whole admissible Q range shifted out from under it and the sample
    # was proven not to exist. That is a live accusation in this repo's archive
    # against an honest paper (n=30, S=529, Q=9493, printed "17.63 +/- 2.38").
    _lo, _hi = rounding.window(sd, decimals_sd, convention)
    sd_lo = max(0.0, _lo)
    sd_hi = _hi
    base = target_sum**2 / n
    # ddof selects the SD convention: 1 = sample (Bessel, n-1); 0 = population
    # (n), which is numpy's std default and Excel's STDEVP. Only the SD->Q map
    # changes; parity and attainability are convention-independent.
    denom = n - ddof
    q_lo = base + denom * sd_lo**2
    q_hi = base + denom * sd_hi**2

    candidates = [
        q for q in range(math.ceil(q_lo - 1e-9), math.floor(q_hi + 1e-9) + 1)
        if q % 2 == target_sum % 2
    ]
    if not candidates:
        return False, (
            f"No integer sum-of-squares Q with the required parity (Q must be even"
            f"/odd to match the total {target_sum}) falls in the window "
            f"[{q_lo:.2f}, {q_hi:.2f}] implied by SD={sd} at {decimals_sd} dp. "
            "No sample of integers can produce this mean/SD pair."
        )

    if not apply_bounds:
        return True, ""

    # Attainability given the scale bounds.
    base_val, remainder = divmod(target_sum, n)
    if base_val < scale_min or (base_val + (1 if remainder else 0)) > scale_max:
        return False, "The required total is unattainable within the scale bounds."
    q_min = remainder * (base_val + 1) ** 2 + (n - remainder) * base_val**2

    n_high, rest = divmod(target_sum - n * scale_min, scale_max - scale_min) if scale_max > scale_min else (0, 0)
    n_high = min(n_high, n)
    q_max = (
        n_high * scale_max**2
        + (1 if rest and n_high < n else 0) * (scale_min + rest) ** 2
        + max(0, n - n_high - (1 if rest and n_high < n else 0)) * scale_min**2
    )
    if all(q < q_min or q > q_max for q in candidates):
        return False, (
            f"The required sum of squares ({candidates[0]}) lies outside the attainable "
            f"range [{q_min}, {q_max}] for values on [{scale_min}, {scale_max}]."
        )
    return True, ""


def sprite_reconstruct(
    mean: float,
    sd: float,
    n: int,
    scale_min: int = 1,
    scale_max: int = 7,
    num_samples: int = 100,
    max_iterations: int = 10000,
    decimals_sd: int | None = None,
    data_type: str = "integer",
    decimals_mean: int | None = None,
    bound_source: str = "assumed",
    discreteness_source: str = "assumed",
    seed: int = 20260811,
) -> dict:
    """
    Reconstruct possible sample distributions from mean and SD.

    SPRITE iteratively reconstructs samples of integers that match
    the reported mean and SD. This reveals what the underlying data
    distribution must look like.

    Args:
        mean: Reported mean
        sd: Reported standard deviation
        n: Sample size
        scale_min: Minimum value on scale
        scale_max: Maximum value on scale
        num_samples: Number of distributions to generate
        max_iterations: Max iterations per sample
        bound_source: `stated` if the PAPER gives scale_min/scale_max,
            `logically_necessary` if they follow from the quantity itself,
            `assumed` (the default) if WE supplied them. A verdict that rests on
            the scale is capped at `suspicious` unless the bound is hard -- the
            same rule grim_test applies (tools/grim.py:161-170).
        discreteness_source: who established that the observations are
            INTEGER-valued -- `stated`, `logically_necessary`, or `assumed`
            (the default). SPRITE reconstructs samples of integers, so its
            bound-free `grim_fail` verdict rests on that premise exactly as the
            out-of-range verdict rests on the bounds. See
            `grim.HARD_DISCRETENESS_SOURCES`.

    Returns:
        Dictionary with reconstructed distributions and analysis
    """
    # MISAPPLICATION GUARD. SPRITE reconstructs samples of INTEGERS; pointed at
    # a continuous clinical measure it reports ordinary values as impossible
    # (verified: sprite_reconstruct(128.4, 15.2, 200) on systolic BP returned
    # `impossible` before this guard existed).
    from .grim import DISCRETENESS_CAVEAT, canonical_data_type, granularity_ceiling

    if canonical_data_type(data_type) not in {"integer", "likert", "count"}:
        return {
            "success": False,
            "outcome": "not_applicable",
            "applicable": False,
            "severity": "indeterminate",
            "error": f"SPRITE does not apply to data_type={data_type!r}",
            "explanation": (
                "SPRITE reconstructs samples of integers bounded by a known scale. It cannot "
                "be applied to continuous measurements (blood pressure, BMI, concentrations) "
                "or to values whose scale bounds are unknown."
            ),
            "inputs": {"mean": mean, "sd": sd, "n": n},
        }

    # Precision comes from the REPORTED literals, not from a default. A mean
    # printed as "1.7" has a rounding interval of +/-0.05; assuming 2 dp shrinks
    # that tenfold and discards totals the paper genuinely permits.
    if decimals_mean is None:
        decimals_mean = _decimals_of(mean)
    if decimals_sd is None:
        decimals_sd = _decimals_of(sd)
    decimals_mean = max(0, int(decimals_mean))
    decimals_sd = max(0, int(decimals_sd))

    # A finding that rests on the SCALE is only as strong as the scale.
    #
    # Measured on a real paper: "Number of coalition members", mean 35.78,
    # SD 33.74, n=64, declared `count` with NO stated bounds. This function
    # assumed [1, 7], found the implied total 2290 outside its imagined maximum
    # of 448, and returned `impossible`. grim_check got the same cell right
    # (`suspicious`) because it caps out-of-range findings under an assumed
    # bound (tools/grim.py:161-170). 2290/64 = 35.78125 rounds to 35.78; the
    # paper was fine and the 1-7 scale was ours.
    HARD_BOUNDS = {"stated", "logically_necessary"}
    hard_bounds = bound_source in HARD_BOUNDS

    # EVERY total consistent with the reported mean, not just round(mean*n).
    # `grim_sums` is bound-free (pure granularity); `admissible_sums` is that
    # list intersected with the scale. They must stay separate, or a RANGE
    # failure gets reported as a GRIM failure and inherits `impossible`.
    grim_sums = _grim_consistent_sums(mean, n, decimals_mean)
    admissible_sums = [s for s in grim_sums if n * scale_min <= s <= n * scale_max]

    # GRIM pre-check: if the mean itself is not attainable for this n, SPRITE
    # cannot possibly succeed, and saying "could not find valid distributions"
    # would misattribute a granularity failure to a search failure. This is
    # bound-free, so it licenses `impossible` on its own.
    if not grim_sums:
        # TRUNCATION FIRST, for the same reason and with the same policy as
        # `grim_test`, which has carried this rescue since d584401 while this
        # function did not. A truncating reporter's mean lies in
        # [reported, reported + 10^-d), so a total that misses the round-half
        # window can sit squarely inside the truncation one -- and `grim_check`
        # then returns `rounding_convention` on the very cell this branch called
        # a GRIM failure. Three tools, one cell, opposite verdicts: exactly what
        # `granularity_ceiling` was written to prevent.
        trunc_sums = _grim_consistent_sums(mean, n, decimals_mean,
                                           convention="truncation")
        if trunc_sums:
            return {
                "success": False,
                "outcome": "rounding_convention",
                "error": (
                    "No set of integers has a mean that ROUNDS to this value, "
                    "but one has a mean that TRUNCATES to it -- SPSS's default "
                    "and several journals'. A legitimate reporting choice, not "
                    "fabrication. NOT a finding: named and counted per paper, "
                    "because the RATE is where the signal lives."
                ),
                "inputs": {"mean": mean, "sd": sd, "n": n},
                "severity": "consistent",
                "bound_source": bound_source,
                "rounding_convention": "truncation",
                "grim_sums": trunc_sums,
            }
        # Bound-free, but not premise-free: "no set of n INTEGERS" is only an
        # accusation if the observations are integers, which is `data_type` --
        # our reading. Same gate as GRIM's granularity branch, so the two cannot
        # disagree about one cell.
        granularity_max = granularity_ceiling(discreteness_source)
        return {
            "success": False,
            "outcome": "grim_fail",
            "error": "Mean fails the GRIM test; no integer sample can produce it",
            "inputs": {"mean": mean, "sd": sd, "n": n},
            "severity": granularity_max,
            "bound_source": bound_source,
            "discreteness_source": discreteness_source,
            "explanation": (
                f"No set of {n} integers has a mean that rounds to {mean}. This is a GRIM "
                "failure (granularity), established before any SPRITE search was attempted."
                + ("" if granularity_max == "impossible" else " " + DISCRETENESS_CAVEAT)
            ),
        }

    target_sum = round(mean * n)
    if not admissible_sums:
        return {
            "success": False,
            "outcome": "out_of_range",
            "error": "Target sum outside possible range",
            "target_sum": target_sum,
            "valid_range": [n * scale_min, n * scale_max],
            "severity": "impossible" if hard_bounds else "suspicious",
            "bound_source": bound_source,
            "grim_sums": grim_sums,
            "explanation": (
                f"The implied total{'s' if len(grim_sums) > 1 else ''} {grim_sums} "
                f"round to the reported mean but lie outside the attainable range "
                f"[{n * scale_min}, {n * scale_max}] for n={n} on scale "
                f"[{scale_min}, {scale_max}]."
                + ("" if hard_bounds else
                   f" Those bounds are `{bound_source}`, i.e. OURS, not the paper's, so this "
                   "is capped at `suspicious`: pass bound_source='stated' with the scale the "
                   "paper actually reports before treating it as impossible.")
            ),
        }

    # Match the sample SD at its REPORTED PRECISION, which is what rsprite2 does.
    #
    # The previous implementation required an exact variance match (< 1e-4).
    # For integer data with fixed sum S the sum of squares Q is an integer and
    # var = (Q - S^2/n)/(n-1), so an exact match requires (n-1)*sd^2 + S^2/n to
    # land on an integer -- an arithmetic coincidence of the reported figures,
    # not a property of the data. That made "no solution" meaningless as evidence.
    # Analytic feasibility BEFORE searching: separates "provably no sample exists"
    # (evidence) from "our search gave up" (not evidence).
    #
    # Infeasibility must hold for EVERY admissible total. Testing only
    # round(mean*n) declared `impossible` whenever that single total failed,
    # even when another total consistent with the same reported mean worked --
    # a false accusation on genuine data.
    feasibility = [
        (s, *_sd_window_feasible(s, n, sd, decimals_sd, scale_min, scale_max))
        for s in admissible_sums
    ]
    feasible = any(ok for _, ok, _ in feasibility)
    why_not = (
        "; ".join(f"total {s}: {reason}" for s, ok, reason in feasibility if not ok)
        if not feasible else ""
    )
    # Search only from totals that survive the analytic screen.
    admissible_sums = [s for s, ok, _ in feasibility if ok] or admissible_sums
    target_sum = admissible_sums[0]
    if not feasible:
        # The screen mixes bound-FREE constraints (Q integral, Q parity) with
        # bound-DEPENDENT ones (the total attainable within the scale, Q inside
        # [q_min, q_max]). Rerun it bound-free to find out which one did the
        # work: only an arithmetic infeasibility is evidence about the paper.
        bound_free = (
            True if hard_bounds else
            any(_sd_window_feasible(s, n, sd, decimals_sd, scale_min, scale_max,
                                    apply_bounds=False)[0]
                for s in grim_sums)
        )
        rests_on_bounds = (not hard_bounds) and bound_free
        # BEFORE CALLING IT IMPOSSIBLE, TRY THE POPULATION-SD CONVENTION. The
        # window above uses the sample (Bessel, n-1) SD; a paper reporting the
        # population (n) SD -- numpy's std default, Excel's STDEVP -- shifts the
        # implied sum-of-squares out of it. Verified: [1,2,2,3,3,3,4,4,4,4],
        # mean 3.0, population SD exactly 1.0, was proven "impossible" (Q=100 is
        # the real sum of squares, feasible only under ddof=0). GRIMMER and
        # DEBIT treat this as a convention rather than a finding, and SPRITE must
        # not contradict its siblings.
        pop_feasible = (
            (not rests_on_bounds) and
            any(_sd_window_feasible(s, n, sd, decimals_sd, scale_min, scale_max,
                                    ddof=0)[0]
                for s in admissible_sums)
        )
        if pop_feasible:
            return {
                "success": False,
                "outcome": "sd_convention",
                "error": (
                    "No integer sample reproduces this SD under the sample "
                    "(Bessel, n-1) convention, but one does under the POPULATION "
                    "(n) convention -- numpy's std default, Excel's STDEVP. A "
                    "legitimate reporting choice, not fabrication. NOT a finding: "
                    "the convention is named and counted per paper, because the "
                    "RATE is where the signal lives and one such value is a house "
                    "style."
                ),
                "inputs": {"mean": mean, "sd": sd, "n": n},
                # GREG, 2026-08-10, extending his truncation ruling here on his
                # own reasoning -- "it would be inconsistent to do the truncation
                # check but not this." A convention that fully explains the number
                # is not evidence against the paper, which is the argument that
                # moved the truncation rescue to `consistent` in d584401. See
                # `sd_checks.grimmer_test` for the full note; the three tools must
                # not disagree about one cell.
                "severity": "consistent",
                "bound_source": bound_source,
                "sd_convention": "population",
            }
        # The population rescue above is confined to the scale WE supplied, so
        # a population-SD report whose reconstruction needs values beyond that
        # scale still fell through to `no_solution_proven` at `impossible` --
        # an error message claiming "No integer sample can produce this
        # mean/SD pair", which was simply false. Verified: real data
        # [2,2,2,3,4,4,5,5,5,6,6,7,8,8,8,9,9,10,10,10] on a 1-10 scale, mean
        # 6.15, population SD 2.7069 reported 2.71, was branded `impossible`
        # against the assumed 1-7 default. "We could not find a solution in
        # the region we chose to search" is a statement about our search, not
        # the paper, so under ASSUMED bounds the honest verdict is the capped
        # one. Under STATED bounds the search region is the paper's own and
        # `impossible` below remains licensed.
        pop_feasible_unbounded = (
            (not rests_on_bounds) and (not hard_bounds) and
            any(_sd_window_feasible(s, n, sd, decimals_sd, scale_min, scale_max,
                                    apply_bounds=False, ddof=0)[0]
                for s in grim_sums)
        )
        if pop_feasible_unbounded:
            return {
                "success": False,
                "outcome": "sd_convention",
                "error": (
                    "No integer sample reproduces this SD under the sample "
                    "(Bessel, n-1) convention, but one does under the "
                    "POPULATION (n) convention -- numpy's std default, Excel's "
                    "STDEVP -- provided the scale is wider than the ASSUMED "
                    f"{scale_min}-{scale_max}. Consistent if the SD is a "
                    "population SD and the true scale bounds are wider than "
                    "assumed; both the convention and the bounds are ours to "
                    "confirm, not evidence of fabrication. Counted per paper as a "
                    "convention, never filed as a finding."
                ),
                "inputs": {"mean": mean, "sd": sd, "n": n},
                # A fortiori: the branch above is `consistent` on the convention
                # alone, and this one is that convention PLUS a scale we invented.
                # Two of our own assumptions cannot add up to evidence.
                "severity": "consistent",
                "bound_source": bound_source,
                "sd_convention": "population",
                "requires_bounds_beyond_assumed": True,
            }
        # TRUNCATION IS CHECKED LAST, AND THE ORDER IS A LABELLING DECISION
        # RATHER THAN A DISCOVERY. A cell can be explicable by MORE THAN ONE
        # convention -- the archived population case `mean 3.0, sd 1.0, n=10`
        # (real data [1,2,2,3,3,3,4,4,4,4]) is admitted by the population-SD
        # window AND, at 1 dp, by the truncation window. Whichever arm runs
        # first names it, and the name is not cosmetic: `agent.checks_tally`
        # builds the PER-PAPER CONVENTION RATE from this field, and per
        # Heathers the rate is where the signal lives. Population keeps
        # precedence because it held it first and the suite encodes that
        # choice; truncation catches what population cannot explain, which is
        # the whole of the new value. Neither ordering is more true; what
        # would be false is presenting either label as if the other had been
        # ruled out.
        # BEFORE CALLING IT IMPOSSIBLE, TRY THE TRUNCATION CONVENTION.
        #
        # This module CITED Greg's truncation ruling of 2026-08-10 -- "it would
        # be inconsistent to do the truncation check but not this" -- in the
        # comment on the population rescue below, and then never implemented the
        # truncation check it was arguing from. `grim.py` mentions truncation 53
        # times; this file mentioned it only in that comment. The August 27
        # validation sweep then recorded `sprite` as one of the tools that "try
        # truncation before accusing", which was a FALSE CLEARANCE -- worse than
        # an unexamined tool, because it is the reason nobody looked.
        #
        # A truncating reporter prints floor(v*10^d)/10^d, so the admissible
        # window is [reported, reported + 10^-d) -- a DIFFERENT window, not a
        # wider one. Applied to the mean AND the SD together, because a paper
        # that truncates does so uniformly and mixing conventions within one
        # cell would be the guess this rescue exists to avoid.
        #
        # NOT AN OFF SWITCH, and that was measured before this shipped, per
        # Greg's rule of 2026-08-11. Sweeping the printable SD grid at
        # (n, dp) in {20,30,50,100} x {1,2}: truncation rejects 5.1% / 61.4% /
        # 2.6% / 43.1% / 0% / 25.3% / 0% / 12.3% of the grid against round-half's
        # 5.1% / 61.9% / 2.6% / 43.1% / 0% / 25.3% / 0% / 12.5%. It rejects what
        # round-half rejects. In the two cells where it rejects nothing,
        # round-half rejects nothing either -- the check was already powerless
        # there, so the rescue disables nothing that worked.
        trunc_sums = _grim_consistent_sums(mean, n, decimals_mean,
                                           convention="truncation")
        trunc_feasible = any(
            _sd_window_feasible(t, n, sd, decimals_sd, scale_min, scale_max,
                                convention="truncation")[0]
            for t in (trunc_sums or admissible_sums))
        if trunc_feasible:
            return {
                "success": False,
                "outcome": "rounding_convention",
                "error": (
                    "No integer sample reproduces this mean/SD pair under the "
                    "ROUND-HALF convention, but one does under TRUNCATION -- "
                    "SPSS's default, several journals', and one of "
                    "`scrutiny::grim`'s options. A legitimate reporting choice, "
                    "not fabrication. NOT a finding: the convention is named and "
                    "counted per paper, because the RATE is where the signal "
                    "lives and one such value is a house style."
                ),
                "inputs": {"mean": mean, "sd": sd, "n": n},
                # `consistent`, on the same reasoning that moved the GRIM
                # truncation rescue there in d584401 and the population-SD
                # rescue below: a convention that fully explains the number is
                # not evidence against the paper. The three tools must not
                # disagree about one cell, and today they do -- on the archived
                # cell 59.06 +/- 11.15 at n=30, grim_check says
                # `rounding_convention` while grimmer_check and this function
                # both said `impossible`.
                "severity": "consistent",
                "bound_source": bound_source,
                "rounding_convention": "truncation",
                "grim_sums": trunc_sums,
            }
        return {
            "success": False,
            "outcome": "out_of_range" if rests_on_bounds else "no_solution_proven",
            "error": (
                "The reported SD is unattainable on the ASSUMED scale"
                if rests_on_bounds else
                "No integer sample can produce this mean/SD pair"
            ),
            "inputs": {"mean": mean, "sd": sd, "n": n},
            # `no_solution_proven` is the bound-free branch -- "no INTEGER
            # sample can produce this" -- so it carries the discreteness premise
            # and is gated on it, exactly as the sibling branch is gated on the
            # bounds. `out_of_range` is already capped at `suspicious`.
            "severity": ("suspicious" if rests_on_bounds
                         else granularity_ceiling(discreteness_source)),
            "bound_source": bound_source,
            "discreteness_source": discreteness_source,
            "feasible_ignoring_bounds": bound_free if not hard_bounds else None,
            "explanation": (
                why_not + (
                    f" Every one of those reasons depends on the {scale_min}-{scale_max} "
                    f"scale, which is `{bound_source}` -- ours, not the paper's. Ignoring the "
                    "bounds, an integer sample DOES exist, so this is capped at `suspicious`."
                    if rests_on_bounds
                    else ("" if granularity_ceiling(discreteness_source) == "impossible"
                          else " " + DISCRETENESS_CAVEAT)
                )
            ),
        }

    # A SEEDED, LOCAL RNG -- not the module-global one.
    #
    # SPRITE is a Monte Carlo search, and its most consequential output is a
    # NEGATIVE: "no integer sample reproduces this mean and SD", which can reach
    # `impossible`. Drawn from an unseeded global RNG, that claim was not
    # reproducible -- the same paper could yield a finding on one run and not the
    # next, and a reader re-running the tool to check us could fail to see what
    # we saw. For a forensic instrument whose output may be put to an author,
    # that is the wrong kind of surprise.
    #
    # A LOCAL `random.Random` rather than `random.seed()`: seeding the global
    # would silently make every other consumer of `random` in the process
    # deterministic too, which is a side effect no caller asked for.
    #
    # `seed` is a parameter so a caller can deliberately vary it -- the honest
    # way to ask "is this no-solution result robust?" is to re-run under several
    # seeds, not to hope the default was lucky. The analytic screen
    # (`_sd_window_feasible`) is unaffected either way: it PROVES infeasibility
    # from parity and integrality and never searches, which is what makes a
    # SPRITE no-solution usable as evidence at all.
    rng = random.Random(seed)

    successful_samples = []

    for _ in range(num_samples):
        # Initialize with values that sum to target
        sample = _initialize_sprite_sample(n, target_sum, scale_min, scale_max)

        if sample is None:
            continue

        # The initializer is deterministic, so shuffle to give each restart a
        # genuinely different starting point (the sum is permutation-invariant).
        rng.shuffle(sample)

        found = _adjust_toward_sd(
            sample, sd, decimals_sd, scale_min, scale_max, max_iterations, rng
        )
        if found is not None:
            successful_samples.append(found.copy())

    # Analyze the distributions
    if not successful_samples:
        return {
            "success": False,
            "outcome": "search_exhausted",
            "error": (
                "Search exhausted without finding a matching distribution. This is NOT "
                "proof that none exists and must not be reported as an anomaly."
            ),
            "inputs": {"mean": mean, "sd": sd, "n": n},
            "severity": "indeterminate",
            "explanation": (
                f"The stochastic search ran {num_samples} restarts x {max_iterations} iterations "
                "without matching the reported SD. Absence of a solution here is evidence about "
                "the search, not about the data. Cross-check with rsprite2 before drawing any "
                "conclusion."
            ),
        }

    # Count frequency at each value across all samples
    value_counts = {}
    for val in range(scale_min, scale_max + 1):
        counts = [np.sum(s == val) for s in successful_samples]
        value_counts[val] = {
            "mean_count": np.mean(counts),
            "min_count": np.min(counts),
            "max_count": np.max(counts),
        }

    # Check for unusual patterns
    is_bimodal = (
        value_counts[scale_min]["mean_count"] > n * 0.2 and
        value_counts[scale_max]["mean_count"] > n * 0.2
    )

    result = {
        "success": True,
        "outcome": "found",
        "severity": "consistent",
        "num_valid_samples": len(successful_samples),
        "example_distributions": [s.tolist() for s in successful_samples[:5]],
        "value_frequencies": value_counts,
        "is_bimodal": is_bimodal,
        "inputs": {
            "mean": mean,
            "sd": sd,
            "n": n,
            "scale_min": scale_min,
            "scale_max": scale_max,
        },
    }

    if is_bimodal:
        result["warning"] = (
            "Reconstructed distributions are bimodal (heavy at both extremes). "
            "This is unusual for most psychological/survey data."
        )

    result["methodology"] = (
        f"SPRITE reconstruction: Generated {len(successful_samples)} valid distributions "
        f"matching mean={mean}, SD={sd}, n={n} on scale [{scale_min}, {scale_max}]."
    )

    return result


def _initialize_sprite_sample(n: int, target_sum: int, scale_min: int, scale_max: int):
    """Initialize a sample that sums to target."""
    # Start with all middle values
    mid_val = (scale_min + scale_max) // 2
    sample = np.full(n, mid_val)

    current_sum = np.sum(sample)
    diff = target_sum - current_sum

    # Adjust to reach target sum
    if diff > 0:
        # Need to increase sum
        for i in range(n):
            if diff <= 0:
                break
            increase = min(diff, scale_max - sample[i])
            sample[i] += increase
            diff -= increase
    else:
        # Need to decrease sum
        diff = -diff
        for i in range(n):
            if diff <= 0:
                break
            decrease = min(diff, sample[i] - scale_min)
            sample[i] -= decrease
            diff -= decrease

    if np.sum(sample) != target_sum:
        return None

    return sample


def _adjust_toward_sd(
    sample: np.ndarray,
    target_sd: float,
    decimals_sd: int,
    scale_min: int,
    scale_max: int,
    max_iterations: int,
    rng: random.Random,
) -> np.ndarray | None:
    """Hill-climb a sample toward the target SD, preserving its sum exactly.

    Each move increments one element and decrements another (so the total, and
    therefore the mean, is invariant) and is ACCEPTED only if it reduces the
    distance to the target SD; otherwise it is reverted. The previous
    implementation applied moves unconditionally and could pick an index pair
    that moved variance the wrong way, so it random-walked instead of
    converging.

    Returns the sample once its SD rounds to the target at the reported
    precision, or None if the search stalls.
    """
    target_round = round(target_sd, decimals_sd)
    current_sd = float(np.std(sample, ddof=1))
    if round(current_sd, decimals_sd) == target_round:
        return sample

    stalled = 0
    for _ in range(max_iterations):
        up_candidates = np.where(sample < scale_max)[0]
        down_candidates = np.where(sample > scale_min)[0]
        if len(up_candidates) == 0 or len(down_candidates) == 0:
            return None

        i = int(rng.choice(up_candidates))
        j = int(rng.choice(down_candidates))
        if i == j:
            continue

        sample[i] += 1
        sample[j] -= 1
        new_sd = float(np.std(sample, ddof=1))

        if round(new_sd, decimals_sd) == target_round:
            return sample

        if abs(new_sd - target_sd) < abs(current_sd - target_sd):
            current_sd = new_sd
            stalled = 0
        else:
            # revert
            sample[i] -= 1
            sample[j] += 1
            stalled += 1
            if stalled > 400:  # local optimum: let the caller restart
                return None

    return None
