"""
Standard Deviation Checks

SD range check and GRIMMER test for verifying SD plausibility.
"""

import math
from typing import Optional

from . import rounding as _rounding


def check_sd_range(
    sd: float,
    min_val: float,
    max_val: float,
    n: Optional[int] = None,
    decimals_sd: Optional[int] = None,
    bound_source: str = "assumed",
) -> dict:
    """
    Check if SD is plausible given the data range.

    The maximum possible SD is slightly more than half the range,
    achieved when all values are at the extremes.

    Args:
        sd: Reported standard deviation
        min_val: Minimum possible value
        max_val: Maximum possible value
        n: Sample size (optional, for more precise max SD)
        decimals_sd: Printed precision of `sd`. The ceiling is a HARD bound,
            so the only slack a reported SD legitimately gets is its own
            rounding: an SD printed 3.5 asserts [3.45, 3.55), and only the
            bottom of that interval has to clear the ceiling. Without it the
            check falls back to a flat 1% margin, which is a guess that
            happens to be 0.035 here and 0.35 for an SD of 35.
        bound_source: `stated` if the PAPER gives min_val/max_val,
            `logically_necessary` if they follow from the quantity itself
            (a proportion lies in [0, 1]), `assumed` (the default) if WE
            supplied them. EVERYTHING this check knows flows from the range,
            so a failure against an assumed range is a statement about our
            assumption, not the paper: it is capped at `highly_suspicious`,
            the same rule grim/grimmer/sprite apply to their scale bounds.
            Only a negative SD is bound-free arithmetic and stays
            `impossible` regardless.

    Returns:
        Dictionary with plausibility assessment
    """
    from .severity import refuse_if_nonfinite

    guard = refuse_if_nonfinite(sd=sd, min_val=min_val, max_val=max_val, n=n)
    if guard is not None:
        return guard

    data_range = max_val - min_val
    if data_range < 0:
        return {
            "error": f"max_val ({max_val}) < min_val ({min_val})",
            "severity": "indeterminate",
        }
    if sd < 0:
        return {
            "error": f"SD cannot be negative (got {sd})",
            "severity": "impossible",
        }

    # Maximum SD is achieved with bimodal distribution at extremes
    # For large n, max SD ≈ range/2
    # More precisely: max_sd = range * sqrt(n²/4) / ... for n points
    if n and n > 1:
        # Max sample SD for n points in [min, max]: half at each extreme.
        # ceil/floor split gives range·sqrt(n²/4 - (n mod 2)/4) / sqrt(n(n-1)).
        # The bound below is the even-n exact value and, for odd n, a slight
        # OVER-estimate of the true maximum (n=5: 0.559017 vs 0.547723 per unit
        # range; n=31: 0.508265 vs 0.508001). Over-estimating the ceiling makes
        # the check more permissive, which is the safe direction -- it misses a
        # marginal impossibility rather than inventing one. A previous comment
        # here said "underestimate", which is the opposite claim and would have
        # meant the check accused correctly-reported SDs.
        max_sd = data_range / 2 * math.sqrt(n / (n - 1))
    else:
        # n UNKNOWN -> use the supremum over all n, which is R/sqrt(2) at n = 2,
        # NOT R/2. The bound R/2*sqrt(n/(n-1)) DECREASES in n, so R/2 is its
        # large-n INFIMUM: it is the tightest -- i.e. most accusatory -- ceiling
        # available, and it is exceeded by the true maximum at every finite n
        # (n=2: 0.7071R, n=3: 0.5774R, n=100: 0.5025R). Two patients scoring 0
        # and 10 have an honest sample SD of 7.07 on a 0-10 range, and this
        # branch called that `impossible`. Knowing nothing about n licenses only
        # the weakest bound, so take the supremum; supplying `n` restores the
        # tighter one.
        max_sd = data_range / math.sqrt(2)

    # An SD is only implausible if even the SMALLEST value its printed
    # precision permits exceeds the ceiling. `max_sd` is a hard mathematical
    # bound -- half the range, corrected for n -- so nothing but rounding
    # entitles a reported value to exceed it.
    if decimals_sd is not None:
        slack = _rounding.half_width(decimals_sd)
        is_plausible = (sd - slack) <= max_sd + _rounding.EPSILON
        margin_source = f"printed precision ({decimals_sd} dp)"
    else:
        # A flat 1% is a guess unrelated to how the number was printed: it is
        # 0.035 for an SD of 3.5 and 0.35 for an SD of 35, and it CONVICTS a
        # coarsely printed value. An SD printed "5" (0 dp) asserts [4.5, 5.5),
        # so a true 4.6 under a ceiling of 4.75 is honest -- yet 5 > 4.75*1.01
        # returned `impossible`. Fall back to the precision INFERRED from the
        # literal, the same device `ttest._half_for` uses, which errs towards the
        # wider interval by construction.
        inferred = _rounding.decimals_of_value(sd)
        slack = _rounding.half_width(0 if inferred is None else inferred)
        is_plausible = (sd - slack) <= max_sd + _rounding.EPSILON
        margin_source = (
            f"precision inferred from the value ({inferred} dp); "
            "pass decimals_sd for the exact printed precision"
        )

    # SEVERITY. The entire ceiling is derived from [min_val, max_val], so a
    # violation is only as strong as the claim that the data really live on
    # that range. A range the PAPER states (or logic forces) licenses
    # `impossible`; a range WE assumed cannot -- the finding would be about our
    # assumption, reported in the grammar of a claim about the paper -- so it
    # is capped at `highly_suspicious`. (A negative SD never reaches here; it
    # returned `impossible` above, bound-free.)
    HARD_BOUNDS = {"stated", "logically_necessary"}
    hard_bounds = bound_source in HARD_BOUNDS
    if is_plausible:
        severity = "consistent"
    elif hard_bounds:
        severity = "impossible"
    else:
        severity = "highly_suspicious"

    result = {
        "reported_sd": sd,
        "data_range": data_range,
        "max_possible_sd": max_sd,
        "is_plausible": is_plausible,
        "sd_as_fraction_of_max": sd / max_sd if max_sd > 0 else None,
        "margin_source": margin_source,
        "bound_source": bound_source,
        "severity": severity,
    }

    if not is_plausible:
        result["explanation"] = (
            f"SD of {sd} exceeds maximum possible SD of {max_sd:.4f} "
            f"for data ranging from {min_val} to {max_val}"
            + ("" if hard_bounds else (
                f". That range is `{bound_source}` -- ours, not the paper's -- "
                "so this is capped at `highly_suspicious`: pass "
                "bound_source='stated' with the range the paper actually "
                "reports before treating it as impossible"))
        )
    else:
        result["explanation"] = (
            f"SD of {sd} is {100*sd/max_sd:.1f}% of the maximum possible "
            f"({max_sd:.4f}) for this range"
            if max_sd > 0
            else "Degenerate range (min == max); any nonzero SD is impossible."
        )

    result["methodology"] = (
        f"SD range check: For data in [{min_val}, {max_val}], "
        f"max SD ≈ range/2 = {data_range}/2 = {data_range/2:.4f}. "
        f"Reported SD = {sd}."
    )

    return result


def _search_sum_of_squares(
    sums: list[int],
    n: int,
    sd: float,
    ddof: int,
    sd_lo: float,
    sd_hi: float,
    sd_tol: float,
    decimals: int,
    decimals_sd: int,
    scale_min: int,
    scale_max: int,
    apply_bounds: bool,
) -> tuple[bool, list[dict]]:
    """Find integer sums-of-squares Q whose implied SD rounds to the reported SD.

    `apply_bounds=False` drops the scale-attainability window and keeps only the
    constraints that hold for ANY integers -- Q integral, Q ≡ S (mod 2), and
    Q ≥ S²/n (Cauchy-Schwarz). Running the same search both ways is how
    grimmer_test tells "this SD is arithmetically impossible" (bound-free
    evidence) from "this SD is impossible on the scale we assumed" (not).

    `ddof` selects the SD convention: 1 is the sample (Bessel, n-1) SD, 0 is the
    population (n) SD -- numpy's `std` default and Excel's STDEVP, a widespread
    and legitimate reporting choice. Only the map between the reported SD and Q
    changes (Q = (n-ddof)·SD² + S²/n); the parity and attainability constraints
    are convention-independent. Searching both is how the caller avoids calling
    a population-SD report arithmetically impossible.
    """
    denom = n - ddof
    working: list[dict] = []
    found = False

    for s in sums:
        exact_mean = s / n
        # Q = (n-ddof)·SD² + n·mean² = (n-ddof)·SD² + S²/n
        q_lo = denom * sd_lo**2 + s**2 / n
        q_hi = denom * sd_hi**2 + s**2 / n

        # Attainability bounds for Σx² given Σx = S and values in
        # [scale_min, scale_max]: minimum with all values equal, maximum with
        # values at the scale extremes (continuous relaxation — a slightly
        # loose but valid necessary condition).
        q_min_attainable = s**2 / n
        if not apply_bounds:
            q_max_attainable = math.inf
        elif scale_max > scale_min:
            frac_at_max = (s - n * scale_min) / (scale_max - scale_min)
            q_max_attainable = (
                frac_at_max * scale_max**2 + (n - frac_at_max) * scale_min**2
            )
        else:
            q_max_attainable = n * scale_min**2

        for q in range(math.ceil(q_lo - 1e-9), math.floor(q_hi + 1e-9) + 1):
            if q % 2 != s % 2:  # parity: Σx² ≡ Σx (mod 2) for integer data
                continue
            if q < q_min_attainable - 1e-9 or q > q_max_attainable + 1e-9:
                continue
            implied_var = (q - s**2 / n) / denom
            if implied_var < -1e-12:
                continue
            implied_sd = math.sqrt(max(0.0, implied_var))
            # ACCEPT AGAINST THE WINDOW WE WERE GIVEN, not against a symmetric
            # tolerance around the reported value. This function receives
            # `sd_lo`/`sd_hi` and used them to bound the Q search, then threw
            # them away and re-tested `abs(implied_sd - sd) <= sd_tol` -- a
            # ROUND-HALF test, hard-coded, contradicting the window in its own
            # signature. A Q admitted by a truncation window was then rejected
            # here, which is how the archived cell `17.63 +/- 2.38, n=30` was
            # called impossible: S=529, Q=9493, implied SD 2.385059, tolerance
            # 0.005 -- REJECTED BY 0.000059.
            #
            # Equivalent to the old test whenever the caller passes a round-half
            # window, since there sd_lo = sd - sd_tol and sd_hi = sd + sd_tol.
            # Bounds are inclusive at both ends rather than half-open: on a
            # RESCUE window the generous edge is the safe direction, because
            # being generous costs a missed detection and being strict costs a
            # false accusation.
            if sd_lo - 1e-12 <= implied_sd <= sd_hi + 1e-12:
                found = True
                if len(working) < 5:
                    working.append({
                        "sum": s,
                        "sum_squares": q,
                        "exact_mean": round(exact_mean, decimals + 4),
                        "exact_sd": round(implied_sd, decimals_sd + 4),
                    })

    return found, working


def grimmer_test(
    mean: float,
    sd: float,
    n: int,
    scale_min: int = 1,
    scale_max: int = 7,
    decimals: Optional[int] = None,
    decimals_sd: Optional[int] = None,
    data_type: str = "integer",
    bound_source: str = "assumed",
    discreteness_source: str = "assumed",
) -> dict:
    """
    Test if a standard deviation is mathematically possible.

    GRIMMER extends GRIM by checking if the SD is consistent with integer data.
    The key insight: for integer data, (n-1)*SD² + n*mean² must be an integer
    (it equals the sum of squared values).

    The reported mean and SD are rounded values, so the test enumerates every
    integer sum S consistent with the rounded mean (GRIM), and for each S asks
    whether any integer sum-of-squares Q exists such that the implied SD
    rounds to the reported SD. Q must also (a) share the parity of S (since
    x² ≡ x mod 2 for integers) and (b) be attainable given the scale bounds.

    Args:
        mean: Reported mean
        sd: Reported standard deviation
        n: Sample size
        scale_min: Minimum value on scale
        scale_max: Maximum value on scale
        decimals: Decimal places in the reported mean
        decimals_sd: Decimal places in the reported SD (defaults to `decimals`)
        bound_source: `stated` if the PAPER gives scale_min/scale_max,
            `logically_necessary` if they follow from the quantity itself,
            `assumed` (the default) if WE supplied them. Only a hard bound
            licenses `impossible` for a failure that depends on the range --
            see the severity block below.
        discreteness_source: the same rule for the OTHER premise -- who
            established that the observations are integer-valued. `stated`,
            `logically_necessary`, or `assumed` (the default). Both GRIMMER
            failure modes that are BOUND-free (`granularity`, `sd_granularity`)
            are DISCRETENESS-dependent, so an assumed discreteness caps them at
            `suspicious`. See `grim.HARD_DISCRETENESS_SOURCES`.

    Returns:
        Dictionary with 'consistent', 'severity', 'failure_mode' and detail
    """
    # MISAPPLICATION GUARD -- GRIMMER, like GRIM, assumes integer observations.
    # On a continuous clinical measure it returns `impossible` for ordinary
    # values (verified: grimmer_test(128.4, 15.2, 200) on systolic BP).
    # Precision must come from the REPORTED literals. Defaulting to 2 dp when a
    # paper printed "1.7" shrinks the rounding interval tenfold and rejects
    # totals the paper genuinely permits -- a false-accusation path measured at
    # 17.1% on genuine 1-dp data.
    from .sprite import _decimals_of
    from .severity import refuse_if_nonfinite

    guard = refuse_if_nonfinite(mean=mean, sd=sd, n=n, scale_min=scale_min, scale_max=scale_max)
    if guard is not None:
        return guard

    if decimals is None:
        decimals = _decimals_of(mean)
    if decimals_sd is None:
        decimals_sd = _decimals_of(sd)

    from .grim import DISCRETENESS_CAVEAT, canonical_data_type, granularity_ceiling

    if canonical_data_type(data_type) not in {"integer", "likert", "count"}:
        return {
            "error": (
                f"GRIMMER does not apply to data_type={data_type!r}; it assumes integer "
                "observations on a bounded scale."
            ),
            "severity": "indeterminate",
            "applicable": False,
            "data_type": data_type,
        }

    if n < 2:
        return {
            "error": f"n must be ≥ 2 for an SD to exist (got {n})",
            "severity": "indeterminate",
        }
    if sd < 0:
        return {
            "error": f"SD cannot be negative (got {sd})",
            "severity": "impossible",
        }
    if decimals_sd is None:
        decimals_sd = decimals

    mean_tol = _rounding.tolerance(decimals)
    sd_tol = _rounding.tolerance(decimals_sd)

    # Step 1 (GRIM): enumerate integer sums S whose exact mean S/n rounds to
    # the reported mean.
    #
    # `grim_sums` is BOUND-FREE -- pure granularity, true whatever scale the
    # paper used. `candidate_sums` is that list intersected with the scale.
    # Keeping them apart is the whole point: `grim_consistent` used to be
    # bool(candidate_sums), i.e. read off a list ALREADY filtered by a range we
    # often invented, so a pure RANGE failure was reported as
    # "mean fails GRIM (no integer sum rounds to it)". That sentence was simply
    # false -- for mean 72.5 at n=100, 72.5 x 100 = 7250 exactly, and the only
    # thing 7250 violated was an assumed 1-7 Likert maximum of 700.
    s_lo = math.ceil((mean - mean_tol) * n)
    s_hi = math.floor((mean + mean_tol) * n)
    min_sum = scale_min * n
    max_sum = scale_max * n
    grim_sums = list(range(s_lo, s_hi + 1))
    candidate_sums = [s for s in grim_sums if min_sum <= s <= max_sum]

    grim_consistent = bool(grim_sums)
    sum_in_range = bool(candidate_sums)

    # Step 2 (GRIMMER): for each S, find integer sums-of-squares Q whose
    # implied SD rounds to the reported SD.
    sd_lo = max(0.0, sd - sd_tol)
    sd_hi = sd + sd_tol
    found_valid, working_combinations = _search_sum_of_squares(
        candidate_sums, n, sd, 1, sd_lo, sd_hi, sd_tol, decimals, decimals_sd,
        scale_min, scale_max, apply_bounds=True,
    )

    consistent = grim_consistent and sum_in_range and found_valid
    sum_squares_point = (n - 1) * sd**2 + n * mean**2

    # SEVERITY. Same rule GRIM already applies (tools/grim.py:161-170), which is
    # why grim_check returned `suspicious` on the cell that made GRIMMER say
    # `impossible`: measured on a real paper, "Number of coalition members"
    # mean 35.78, SD 33.74, n=64, declared `count` with NO stated bounds --
    # grimmer_check -> impossible, grim_check -> suspicious, and with the truthful
    # bounds both -> consistent. 2290/64 = 35.78125, which rounds to 35.78; the
    # only thing violated was our own 1-7 default.
    #
    #   granularity    -- no integer total rounds to the mean. Bound-free, so it
    #                     licenses `impossible` on its own.
    #   out_of_range   -- a total exists but the scale excludes it, OR the SD
    #                     search survives only once the attainability window is
    #                     dropped. Both rest entirely on WHOSE bounds these are.
    #   sd_granularity -- no integer sum-of-squares of the right parity fits the
    #                     SD window even with the bounds removed. Bound-free.
    #
    # The two BOUND-free modes are not premise-free: both say "no integer
    # sample reproduces this", which presupposes the observations are integers.
    # That premise is `data_type`, our reading of the paper, so it is gated on
    # its own source exactly as the bounds are. See grim.HARD_DISCRETENESS_SOURCES.
    HARD_BOUNDS = {"stated", "logically_necessary"}
    hard = bound_source in HARD_BOUNDS
    granularity_max = granularity_ceiling(discreteness_source)
    bound_free_sd_ok = None
    pop_ok = None
    pop_free_ok = None

    if consistent:
        failure_mode, failure_reason = None, None
        severity = "consistent"
    elif not grim_consistent:
        # TRUNCATION FIRST, exactly as `grim_test` does. A mean that no integer
        # total ROUNDS to may still be one an integer total TRUNCATES to, and
        # `grim_test` has returned `rounding_convention` for that case since
        # d584401 while this branch returned `impossible` -- the two tools
        # disagreeing about one cell, which `granularity_ceiling` exists to
        # prevent. Measured on the archived cell `59.06 +/- 11.15, n=30`:
        # grim_check `rounding_convention`, grimmer_check `impossible`.
        _tlo, _thi = _rounding.window(mean, decimals, "truncation")
        _tsums = [x for x in range(math.ceil(_tlo * n - 1e-9),
                                   math.floor(_thi * n + 1e-9) + 1)]
        if _tsums:
            failure_mode = "rounding_convention"
            failure_reason = (
                "no integer total has a mean that ROUNDS to this value, but "
                f"{_tsums} TRUNCATES to it -- SPSS's default and several "
                "journals'. A legitimate reporting choice, NOT evidence of "
                "fabrication, and counted per paper rather than filed."
            )
            severity = "consistent"
        else:
            failure_mode = "granularity"
            failure_reason = "mean fails GRIM (no integer sum rounds to it)"
            severity = granularity_max
    elif not sum_in_range:
        failure_mode = "out_of_range"
        failure_reason = (
            f"the mean is GRIM-consistent (totals {grim_sums} round to it) but every "
            f"such total falls outside [{min_sum}, {max_sum}], the range implied by a "
            f"{scale_min}-{scale_max} scale at n={n}. This is a RANGE failure, not a "
            "granularity failure"
        )
        severity = "impossible" if hard else "suspicious"
    else:
        # The SD search failed. Ask whether it failed because of ARITHMETIC or
        # because of the bounds, by rerunning it with the attainability window
        # removed. Only the arithmetic answer is bound-free evidence.
        bound_free_sd_ok, _ = _search_sum_of_squares(
            grim_sums, n, sd, 1, sd_lo, sd_hi, sd_tol, decimals, decimals_sd,
            scale_min, scale_max, apply_bounds=False,
        )
        if bound_free_sd_ok:
            failure_mode = "out_of_range"
            failure_reason = (
                "a sum-of-squares consistent with the reported SD exists but is "
                f"unattainable on a {scale_min}-{scale_max} scale; the failure rests "
                "on the scale bounds, not on arithmetic"
            )
            severity = "impossible" if hard else "suspicious"
        else:
            # BEFORE CALLING IT IMPOSSIBLE, TRY THE TRUNCATION CONVENTION.
            #
            # This file's own comment below cites Greg's ruling of 2026-08-10 --
            # "it would be inconsistent to do the truncation check but not this"
            # -- to justify the POPULATION rescue, while never doing the
            # truncation check it argues from. `grim_test` has carried that
            # rescue since d584401, so the two tools returned opposite verdicts
            # on one cell: on the archived `59.06 +/- 11.15, n=30`, grim_check
            # said `rounding_convention` and grimmer_check said `impossible`.
            # `granularity_ceiling` exists to stop exactly that.
            #
            # It applies to the mean AND the SD together: a paper that truncates
            # does so uniformly, and mixing conventions within one cell is the
            # guess these rescues exist to avoid.
            #
            # NOT AN OFF SWITCH, measured before shipping per Greg's rule of
            # 2026-08-11: over the printable SD grid at (n, dp) in
            # {20,30,50,100} x {1,2}, truncation rejects 5.1/61.4/2.6/43.1/0/
            # 25.3/0/12.3 per cent against round-half's 5.1/61.9/2.6/43.1/0/
            # 25.3/0/12.5. It rejects what round-half rejects, and in the cells
            # where it rejects nothing, round-half rejected nothing either.
            t_mean_lo, t_mean_hi = _rounding.window(mean, decimals, "truncation")
            t_sd_lo, t_sd_hi = _rounding.window(sd, decimals_sd, "truncation")
            t_sums = list(range(math.ceil(t_mean_lo * n - 1e-9),
                                math.floor(t_mean_hi * n + 1e-9) + 1))
            t_cands = [x for x in t_sums if min_sum <= x <= max_sum]
            trunc_ok, trunc_combos = _search_sum_of_squares(
                t_cands or t_sums, n, sd, 1, max(0.0, t_sd_lo), t_sd_hi, sd_tol,
                decimals, decimals_sd, scale_min, scale_max, apply_bounds=True,
            ) if t_sums else (False, [])

            # BEFORE CALLING IT IMPOSSIBLE, TRY THE POPULATION-SD CONVENTION.
            # The search above uses the sample (Bessel, n-1) SD; a paper that
            # reports the population (n) SD -- numpy's std default, Excel's
            # STDEVP -- shifts the implied sum-of-squares by about one variance
            # unit, out of the Bessel window. Verified: real Likert data
            # [1,2,2,3,3,3,4,4,4,4], mean 3.0, population SD exactly 1.0, was
            # branded `impossible`. This is the exact false accusation DEBIT
            # already guards against, and it caps the population-only case at
            # `suspicious` for the same reason: a reporting-convention choice is
            # not fabrication.
            pop_ok, pop_combos = _search_sum_of_squares(
                candidate_sums, n, sd, 0, sd_lo, sd_hi, sd_tol,
                decimals, decimals_sd, scale_min, scale_max, apply_bounds=True,
            )
            # ... AND TRY IT OUTSIDE THE ASSUMED BOUNDS TOO. The rescue above
            # is confined to the scale WE supplied, so a population-SD report
            # whose reconstruction needs values beyond that scale still fell
            # through to `sd_granularity` at `impossible` -- with a failure
            # reason claiming NO convention admits the SD, which was simply
            # false. Verified: real data [2,2,2,3,4,4,5,5,5,6,6,7,8,8,8,9,9,
            # 10,10,10] on a 1-10 scale, mean 6.15, population SD 2.7069
            # reported 2.71, was branded `impossible` against the assumed 1-7
            # default. "We could not find a solution in the region we chose to
            # search" is a statement about our search, not the paper.
            # `None` = not searched (in-bounds success makes it moot).
            pop_free_ok, pop_free_combos = (
                (None, []) if pop_ok else _search_sum_of_squares(
                    grim_sums, n, sd, 0, sd_lo, sd_hi, sd_tol,
                    decimals, decimals_sd, scale_min, scale_max,
                    apply_bounds=False,
                )
            )
            if pop_ok:
                failure_mode = "sd_convention"
                failure_reason = (
                    "no integer sample reproduces this SD under the sample "
                    "(Bessel, n-1) convention, but one does under the POPULATION "
                    "(n) convention -- numpy's std default and Excel's STDEVP. "
                    "This is a legitimate, common reporting choice, NOT evidence "
                    "of fabrication. It is NOT a finding: the convention is named "
                    "and counted per paper, because the RATE is where the signal "
                    "lives, and one such value is a house style."
                )
                # GREG, 2026-08-10 -- extending his truncation ruling to this
                # convention, on his own reasoning: "it would be inconsistent to
                # do the truncation check but not this."
                #
                # He is right, and the inconsistency was mine. Truncation and
                # population-SD are the same KIND of thing: a reporting
                # convention the paper chose, which fully explains the number. A
                # convention that explains the value is not evidence against the
                # paper, so it must not enter the findings as `suspicious` --
                # exactly the argument that moved the truncation rescue to
                # `consistent` in d584401. Shipping one at `consistent` and the
                # other at `suspicious` would have meant two identical epistemic
                # situations getting different words.
                #
                # The fact is retained (`failure_mode`, `sd_convention`) and
                # counted PER PAPER in `agent.checks_tally`, which is where a
                # rate can be read. Per Heathers, this class of anomaly is
                # commoner in papers with more serious errors -- so a high rate
                # is grounds to look harder, never a finding on its own.
                severity = "consistent"
                working_combinations = pop_combos
            elif pop_free_ok and not hard:
                failure_mode = "sd_convention"
                failure_reason = (
                    "no integer sample reproduces this SD under the sample "
                    "(Bessel, n-1) convention, but one does under the POPULATION "
                    "(n) convention -- numpy's std default and Excel's STDEVP -- "
                    f"provided the scale is wider than the ASSUMED "
                    f"{scale_min}-{scale_max}. Consistent if the SD is a "
                    "population SD and the true scale bounds are wider than "
                    "assumed; both the convention and the bounds are ours to "
                    "confirm, not evidence of fabrication. Counted per paper as a "
                    "convention, never filed as a finding."
                )
                # A FORTIORI. The branch above is `consistent` where the
                # population solution sits inside our assumed scale; this one is
                # the SAME convention plus a second thing that is also ours (the
                # scale we invented). Two of our own assumptions cannot add up to
                # evidence against the paper.
                severity = "consistent"
                working_combinations = pop_free_combos
            elif pop_free_ok:
                # Bounds the paper STATED are hard: a solution that needs
                # values outside them is genuinely unavailable. But the reason
                # must say where the population solution lives, or the verdict
                # overclaims arithmetic impossibility.
                failure_mode = "sd_granularity"
                failure_reason = (
                    "no integer sum-of-squares consistent with the reported SD "
                    "under the sample (n-1) convention (bound-free), and the "
                    "only population-(n)-convention solutions require values "
                    f"outside the STATED {scale_min}-{scale_max} scale"
                )
                severity = granularity_max
            # TRUNCATION IS CHECKED LAST, NOT FIRST, AND THE ORDER IS A
            # LABELLING DECISION RATHER THAN A DISCOVERY. A cell can be
            # explicable by MORE THAN ONE convention -- the archived population
            # case `mean 3.0, sd 1.0, n=10` (real data [1,2,2,3,3,3,4,4,4,4]) is
            # admitted by the population-SD window AND, at 1 dp, by the
            # truncation window. Whichever arm runs first gets to name it, and
            # the name is not cosmetic: `agent.checks_tally` builds the
            # PER-PAPER CONVENTION RATE from exactly this field, and Heathers'
            # argument is that the rate is where the signal lives. Population
            # keeps precedence because it held it first and the suite encodes
            # that choice; truncation catches what population cannot explain,
            # which is the whole of the new value. Neither ordering is more
            # true; what would be false is presenting either label as though
            # the other had been ruled out.
            elif trunc_ok:
                failure_mode = "rounding_convention"
                failure_reason = (
                    "no integer sample reproduces this mean/SD pair under the "
                    "ROUND-HALF convention, but one does under TRUNCATION -- "
                    "SPSS's default, several journals', and one of "
                    "`scrutiny::grim`'s options. A legitimate reporting choice, "
                    "NOT evidence of fabrication. It is NOT a finding: the "
                    "convention is named and counted per paper, because the RATE "
                    "is where the signal lives and one such value is a house "
                    "style."
                )
                # `consistent`, on the identical reasoning the population rescue
                # below already uses and cites. Two conventions, one epistemic
                # situation; shipping them at different severities would give the
                # same fact two different words.
                severity = "consistent"
                working_combinations = trunc_combos
            else:
                failure_mode = "sd_granularity"
                failure_reason = (
                    "no integer sum-of-squares consistent with the reported SD "
                    "under either the sample (n-1) or population (n) convention, "
                    "with or without the scale bounds (after GRIM-consistent "
                    "sums and parity constraint)"
                )
                severity = granularity_max

    result = {
        "consistent": consistent,
        "severity": severity,
        "failure_mode": failure_mode,
        "bound_source": bound_source,
        "discreteness_source": discreteness_source,
        "grim_consistent": grim_consistent,
        "sum_in_range": sum_in_range,
        "found_valid_combination": found_valid,
        "feasible_ignoring_bounds": bound_free_sd_ok,
        "population_feasible_in_bounds": pop_ok,
        "population_feasible_ignoring_bounds": pop_free_ok,
        "reported_mean": mean,
        "reported_sd": sd,
        "n": n,
        "grim_sums": grim_sums,
        "candidate_sums": candidate_sums,
        "implied_sum_squares": sum_squares_point,
        "working_combinations": working_combinations,
        "failure_reason": failure_reason,
        "methodology": (
            f"GRIMMER test: enumerate integer sums S with |S/{n} − {mean}| ≤ "
            f"{mean_tol:.4g} (found {len(candidate_sums)}), then for each S "
            f"search integer sums-of-squares Q with matching parity such that "
            f"sqrt((Q − S²/n)/(n−1)) rounds to {sd} at {decimals_sd} dp. "
            f"{'Found' if found_valid else 'No'} valid (S, Q) combination"
            f"{'s' if found_valid else ''}."
        ),
    }

    if failure_mode in ("granularity", "sd_granularity") and severity != "impossible":
        result["discreteness_caveat"] = DISCRETENESS_CAVEAT

    # WHAT THE NUMBERS SAY AS PRINTED, SHOWN RATHER THAN SWALLOWED.
    #
    # GREG, 2026-08-11: "we do the test on only those numbers available, flag
    # it, and then test truncation etc. That way the reader can see the apparent
    # violation (i.e. our toolkit working) but then judge for themselves whether
    # the truncation etc is credible."
    #
    # The de-escalation is right and stays: a paper reporting the population SD
    # has chosen a convention, not fabricated anything, and Greg's 2026-08-10
    # ruling keeps it out of the findings. What was wrong is that it left the
    # reader NOTHING TO JUDGE -- a clean verdict, with the failed arithmetic
    # nowhere on the page. Same defect, same fix, as the truncation rescue in
    # `grim_test`.
    #
    # MEASURED before keeping it, against Greg's off-switch rule: over 500
    # arbitrary (GRIM-consistent mean, random SD) pairs, the population reading
    # rescued 88 while 299 were still caught at `impossible`. A 22.7% rescue
    # rate is an explanation; it retains three quarters of the check's power and
    # is nothing like the truncation off switch at n = 67..99, which rescued
    # 100%.
    if failure_mode == "sd_convention":
        result["as_reported"] = {
            "verdict": "sd_granularity",
            "severity_if_taken_at_face_value": granularity_max,
            "statement": (
                f"As printed, no integer sample of {n} on a "
                f"{scale_min}-{scale_max} scale reproduces both a mean of "
                f"{mean} and an SD of {sd} under the sample (Bessel, n-1) "
                "convention, which is what most journals mean by SD."
            ),
            "explained_by": "population_sd",
            "explanation": (
                "It IS reproducible if the reported SD is the POPULATION (n) SD "
                "-- numpy's `std` default and Excel's STDEVP. That is a common "
                "and legitimate reporting choice."
                + ("" if pop_ok else
                   " This reading additionally needs the scale to be wider than "
                   f"the {scale_min}-{scale_max} we ASSUMED, which is our "
                   "assumption to confirm, not the paper's to defend.")
            ),
            "how_often_that_excuse_is_available": 0.227,
            "judge_for_yourself": (
                "Not counted as a finding, because a convention that fully "
                "explains a number is not evidence against the paper. It is "
                "shown because the arithmetic did fail as printed. Whether the "
                "population reading is credible here is a question about this "
                "paper's house style -- check whether its other SDs need the "
                "same reading. Measured on arbitrary values this explanation is "
                "available about 23% of the time, so it is a specific claim "
                "rather than a universal escape; the RATE across one paper is "
                "what is worth acting on, not a single instance."
            ),
        }

    return result
