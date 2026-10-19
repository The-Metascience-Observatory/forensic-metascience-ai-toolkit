"""
GRIM Test (Granularity-Related Inconsistency of Means)

Checks if reported means are mathematically possible given sample sizes
and integer-valued data (e.g., Likert scales, counts).
"""

from __future__ import annotations

import math
from typing import Optional

from . import rounding as _rounding
from .severity import refuse_if_nonfinite, severity_from_consistency


# Canonical data-type vocabulary shared by GRIM, GRIMMER, SPRITE and DEBIT.
# Every consistency test in this toolkit is defined for exactly one family of
# data, and pointed at any other family it manufactures impossibilities out of
# ordinary numbers (verified: systolic BP 128.43 +/- 15.21 returned `impossible`
# before these guards existed). Normalising here keeps one vocabulary rather
# than four divergent string comparisons.
_DATA_TYPE_ALIASES: dict[str, str] = {
    # integer-valued observations on a bounded scale -> GRIM / GRIMMER / SPRITE
    "integer": "integer", "int": "integer", "whole": "integer",
    "discrete": "integer", "integers": "integer",
    "likert": "likert", "ordinal": "likert", "rating": "likert", "scale": "likert",
    "count": "count", "counts": "count", "frequency": "count", "tally": "count",
    # 0/1-coded -> DEBIT
    "binary": "binary", "dichotomous": "binary", "boolean": "binary",
    "bool": "binary", "indicator": "binary", "0/1": "binary",
    "proportion": "proportion", "percentage": "proportion", "percent": "proportion",
    "fraction": "proportion", "rate": "proportion",
    # an unordered category (sex, diagnosis, site). Its only GRIM-testable
    # number is a share of the sample in one category -- a proportion -- so
    # grim_percentage accepts it; a MEAN of it is not a quantity and every
    # mean-type check refuses it. `nominal_category` is the anatomy family.
    "nominal": "nominal", "categorical": "nominal", "category": "nominal",
    "nominal_category": "nominal",
    # not integer-valued -> every granularity test must refuse
    "continuous": "continuous", "real": "continuous", "float": "continuous",
    "measurement": "continuous", "interval": "continuous", "ratio": "continuous",
    "unknown": "unknown", "": "unknown",
}


def canonical_data_type(data_type: str | None) -> str:
    """Normalise a data-type string to the canonical vocabulary.

    Anything unrecognised becomes `"unknown"`, which every applicability guard
    refuses. That direction is deliberate: an unrecognised label means we do not
    know what the numbers are, and a tool that guesses when it does not know
    produces accusations against honest researchers.
    """
    if data_type is None:
        return "unknown"
    return _DATA_TYPE_ALIASES.get(str(data_type).strip().lower(), "unknown")


#: WHO ESTABLISHED THAT THE OBSERVATIONS ARE INTEGER-VALUED. The exact
#: counterpart of `bound_source`, for the OTHER premise every granularity test
#: rests on -- and the one nothing was checking.
#:
#: GREG'S CALL, 2026-08-10, on the operating philosophy of this whole family:
#:
#:   "GRIM/GRIMMER/SPRITE and that family are very unlikely to be applicable
#:    for most studies. It requires very specific variables, which are discrete,
#:    with known or reported ranges, and with ascertainable granularity. I think
#:    that any such test should be 'guilty until proven innocent' owing to this
#:    low prior probability. These kinds of GRIM-tractable instruments are mainly
#:    in psychology, and we will be using this tool across many fields."
#:
#: He is right, and the asymmetry in the code proved it. `bound_source` has been
#: gated since #87: a range violation against a scale WE invented caps at
#: `suspicious`, because our invention is not the paper's claim. But the
#: GRANULARITY branch -- "no integer sum divided by n rounds to this mean" --
#: reached `impossible` unconditionally, and it depends on a premise of exactly
#: the same kind: that each subject contributed a WHOLE NUMBER. Nothing in the
#: arithmetic establishes that. It arrives as `data_type`, which is the model's
#: own assertion about a variable it read in prose, and `impossible` is the top
#: of the severity ladder -- the claim that no honest sample could have produced
#: this. Resting the strongest verdict we issue on our least-verified input is
#: precisely backwards.
#:
#: The values mirror `bound_source` exactly, so one rule is learned, not two:
#:   stated               the PAPER establishes integer-valued observations --
#:                        a quoted scale definition, an item count with response
#:                        options, "number of falls". Verified, not asserted:
#:                        `Variable.discreteness_source` demands the pipeline's
#:                        own quote verdict, which the model cannot write.
#:   logically_necessary  the quantity cannot be non-integer whatever any paper
#:                        says -- a printed integer COUNT of the n units. Reserved
#:                        for callers who have the numerator on the page.
#:   assumed              everything else, including a model saying `count` with
#:                        high confidence and no verifiable quote. Caps the
#:                        granularity verdict at `suspicious`.
#:
#: WHAT THIS IS NOT. It does not weaken a single true finding: a demoted verdict
#: is still reported, still ranked, still shown to the reader with the same
#: arithmetic. It changes the WORD from "impossible" to "suspicious" wherever we
#: cannot show the paper said its data were whole numbers -- which is the
#: difference between an accusation and a question.
HARD_DISCRETENESS_SOURCES = frozenset({"stated", "logically_necessary"})


#: How far either side of the supplied n to look for a denominator that WOULD
#: fit. Two, because the common causes are small: one or two participants
#: excluded for missing data on this particular outcome, an intention-to-treat
#: total used where a per-protocol total was analysed, a dropout.
DENOMINATOR_WINDOW = 2


def nearby_denominators(mean: float, n: int, decimals: int,
                        window: int = DENOMINATOR_WINDOW) -> list[int]:
    """Which denominators near `n` would make this mean GRIM-consistent?

    A QUESTION FOR THE AUTHORS, NEVER A RESCUE. Read the measurement below
    before changing that.

    The motivating observation is real: 13.04% is impossible at n = 22 and
    exact at n = 23, and 35.3% is impossible at n = 52 and exact at n = 51.
    Both look like a denominator that is off by one, which is the commonest
    thing that can be wrong with a table cell -- the `n` we test against is
    usually read off a COLUMN HEADER, and the analysed n for one outcome is
    routinely smaller than the column's enrolled n.

    THE OBVIOUS FIX IS WRONG, AND THIS IS THE MEASUREMENT THAT SAYS SO.
    De-escalating any granularity failure that fits at a nearby n would not be
    a diagnosis, it would be an off switch. Over 4,000 random 2-dp means per n
    on a 1-7 scale, the share of genuine GRIM failures that fit somewhere in
    n +/- 2:

        n = 10   36.8%
        n = 20   70.6%
        n = 30   79.6%
        n = 50   76.0%

    Three quarters of all detections at typical psychology sample sizes. The
    arithmetic that makes a real fabrication detectable is the same arithmetic
    that makes a neighbouring denominator fit, so "it works at n +/- 1" carries
    almost no evidence at these sizes.

    (n >= 80 returned ZERO failures in the same sweep. At 2 dp every attainable
    mean is within half an ulp of some k/n once n is large, so GRIM has no power
    there at all -- worth knowing before quoting a null result on a big table.)

    So this returns the candidates and changes nothing. Its use is the sentence
    a reader can put to an author: "this value is exact at n = 23; the column
    header says 22 -- which n was analysed for this row?" That is answerable,
    specific, and presupposes no wrongdoing.
    """
    out: list[int] = []
    try:
        for cand in range(max(2, n - window), n + window + 1):
            if cand == n:
                continue
            if _mean_passes_grim(mean, cand, decimals)[0]:
                out.append(cand)
    except (TypeError, ValueError):
        return []
    return out


def percentage_reading_disagrees(mean: float, n: int, decimals: int,
                                 scale_min: float | None = None,
                                 scale_max: float | None = None,
                                 bound_source: str = "assumed") -> dict | None:
    """Would this value be INCONSISTENT if it is a percentage rather than a mean?

    THE FALSE CLEAR THIS CATCHES, found by replaying the archive. The model sent
    the SAME statistic to the same tool in both forms:

        mean = 0.183, n = 12, 3 dp  ->  not consistent
        mean = 18.3,  n = 12, 1 dp  ->  CONSISTENT

    Both describe 18.3% of 12. The second is wrong, and wrong in the dangerous
    direction. A mean of 12 integers moves in steps of 1/12 = 0.083, so 18.3 is
    reachable (220/12 = 18.333). A PERCENTAGE of 12 units moves in steps of
    100/12 = 8.3 POINTS -- the attainable values are 0, 8.3, 16.7, 25.0, and
    18.3 is not among them. Feeding a percentage to a mean-GRIM divides the
    granularity by 100 and clears almost anything.

    Seven archived calls returned `consistent` on values in this shape.

    WHY THIS DOES NOT CHANGE THE VERDICT. 18.3 is a perfectly ordinary mean --
    a FIM score, a blood pressure, a count of days. We cannot tell from the
    number which it is, and refusing every mean above 1 would disable the tool
    on most clinical data. What we CAN say is that the two readings disagree,
    which is a fact rather than an inference, and it is exactly the ambiguity
    that produced the false clear. So it rides along with the `consistent`
    verdict as a caveat and names the tool that answers the other question.
    """
    try:
        if not (n and n > 0) or mean is None or decimals is None:
            return None
        # Only where a percentage reading is even arguable. A value above 100
        # cannot be a percentage of anything; one at or below 1 is already in
        # proportion form and `_proportion_passes_grim` is the right question.
        if not (1.0 < float(mean) <= 100.0):
            return None
        # THE AMBIGUITY IS SETTLED IF THE PAPER SETTLED IT. A value sitting
        # inside a scale the PAPER STATED is a mean on that scale, full stop --
        # and firing there would put this caveat on every ordinary Likert mean
        # (5.0 on a 1-7 scale is not an attainable percentage of 30 either, and
        # saying so is noise). A bound WE assumed cannot rule anything out, so
        # the caveat stands in that case, which is the safe direction.
        if (bound_source in HARD_DISCRETENESS_SOURCES
                and scale_min is not None and scale_max is not None
                and float(scale_min) <= float(mean) <= float(scale_max)):
            return None
        if _proportion_passes_grim(float(mean) / 100.0, n, int(decimals) + 2)[0]:
            return None
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    step = 100.0 / n
    return {
        "reading": "percentage",
        "attainable_step": round(step, 4),
        "note": (
            f"CONSISTENT AS A MEAN OF INTEGERS. If this value is a PERCENTAGE of "
            f"the {n} units instead, it is NOT attainable: a share of {n} moves in "
            f"steps of {step:.2f} percentage points, and {mean} is not one of them. "
            "The two readings disagree, so say which this is -- and use "
            "`grim_percentage` for the percentage reading, which asks the right "
            "question. Passing a percentage here divides the granularity by 100 "
            "and clears almost anything."
        ),
    }


def granularity_ceiling(discreteness_source: str | None) -> str:
    """The strongest verdict a GRANULARITY failure may reach.

    `impossible` only where the discreteness premise is the paper's or is
    logically forced; `suspicious` where it is ours. Shared by GRIM, GRIMMER and
    SPRITE so the three cannot disagree about one cell -- the failure mode this
    repo has already been bitten by twice (`grim_check` said `suspicious` on the
    cell `grimmer_check` called `impossible`, and `composite` certified a
    denominator that `check_count_percent` then convicted).
    """
    return ("impossible" if str(discreteness_source or "").strip().lower()
            in HARD_DISCRETENESS_SOURCES else "suspicious")


#: One sentence, appended verbatim wherever a granularity verdict is demoted, so
#: the reader is told which premise is missing and how to supply it.
DISCRETENESS_CAVEAT = (
    "CAPPED at `suspicious`, not `impossible`: GRIM's arithmetic is airtight only "
    "if each subject really contributed a WHOLE NUMBER, and nothing here "
    "establishes that -- the data type is our reading of the paper, not a claim "
    "the paper is shown to make. A continuous measure, a mean of k items (whose "
    "granularity is 1/(k*n), not 1/n), or a rescaled score all produce this same "
    "arithmetic from honest data. Confirm the instrument is integer-valued and "
    "re-run with discreteness_source='stated' to license `impossible`."
)


def _mean_passes_grim(mean: float, n: int, decimals: int) -> tuple[bool, int]:
    """Return (passes, implied_sum).

    A reported mean (printed to `decimals` dp) is GRIM-consistent iff some
    integer sum S satisfies |S/n − mean| ≤ half the last reported decimal
    place — i.e. S/n rounds back to the reported mean. The nearest candidate
    S = round(mean·n) is sufficient to check.
    """
    if n <= 0:
        return (False, 0)
    s = round(mean * n)
    tol = _rounding.tolerance(decimals)
    return (abs(s / n - mean) <= tol, s)


def _mean_passes_grim_truncation(mean: float, n: int, decimals: int) -> tuple[bool, int]:
    """GRIM under the TRUNCATION convention rather than round-half.

    A reporter that truncates (SPSS's default, some journals', and one of
    `scrutiny::grim`'s rounding options) prints floor(true·10^d)/10^d, so the
    true mean lies in [reported, reported + 10^-d). The question becomes whether
    some integer sum S has S/n in that HALF-OPEN interval -- a different window
    from round-half, not a wider one.

    Reproduced: 16 threes + 14 fours, n=30, exact mean 104/30 = 3.4666..., is
    printed 3.46 by a truncating reporter. Round-half GRIM rejects it (nearest
    is 3.47) and called it `impossible`; under truncation S=104 gives
    3.46667 ∈ [3.46, 3.47), so a real sample exists.
    """
    if n <= 0:
        return (False, 0)
    step = 10.0 ** (-decimals)
    s = math.ceil(mean * n - 1e-9)          # smallest S with S/n >= mean
    return (mean - 1e-12 <= s / n < mean + step - 1e-12, s)


def discriminating_power(n: int, decimals: int) -> dict:
    """How much of the printable grid each convention can REJECT at this (n, d).

    GREG'S RULE, 2026-08-11:

        "I agree to not do the decimal expansion if it ALWAYS rescues an
         otherwise impossible finding."

    A rescue that rescues everything is not a judgement about the paper, it is
    an off switch, and a check that cannot fail must never report `consistent`.
    This function is what makes that testable rather than a matter of opinion.

    EXACT, NOT SAMPLED. The set of attainable means is {S/n : S integer}, and
    S -> S + n shifts the mean by exactly 1, so the accept/reject pattern has
    period 1. Evaluating one period settles it for the whole scale.

    Returns the share of printable values rejected by the round-half convention
    alone, the share rejected by BOTH conventions, and the two facts that follow:

      `check_can_fail`  False when round-half itself rejects nothing. GRIM has no
                        power at all here -- at 1 dp that is EVERY sample size,
                        and at 2 dp it is n >= 100. A `consistent` verdict in
                        this regime is true and tells the reader nothing, so it
                        must say so rather than passing for evidence of order.

      `rescue_is_an_off_switch`  True when round-half CAN reject but nothing
                        survives both conventions. Here the truncation reading
                        is not an explanation of this value -- it is available
                        for every value, so granting it silently converts a real
                        detection into a false all-clear. MEASURED: at 2 dp this
                        is exactly n = 67..99, where round-half still rejects
                        33% down to 10% of the grid and the union rejects none.
    """
    if n <= 0 or decimals is None or decimals < 0 or decimals > 6:
        return {"check_can_fail": True, "rescue_is_an_off_switch": False,
                "round_half_rejects": None, "both_reject": None}
    step = 10.0 ** (-decimals)
    points = int(round(1.0 / step))
    half = both = 0
    for i in range(points):
        m = round(i * step, decimals)
        r = _mean_passes_grim(m, n, decimals)[0]
        if not r:
            half += 1
            if not _mean_passes_grim_truncation(m, n, decimals)[0]:
                both += 1
    return {
        "round_half_rejects": round(half / points, 4),
        "both_reject": round(both / points, 4),
        "check_can_fail": half > 0,
        "rescue_is_an_off_switch": half > 0 and both == 0,
        "n": n,
        "decimals": decimals,
    }


def grim_test(
    mean: float,
    n: int,
    scale_min: int | None = 1,
    scale_max: int | None = 7,
    decimals: int = 2,
    data_type: str = "likert",
    bound_source: str = "assumed",
    discreteness_source: str = "assumed",
) -> dict:
    """
    Test if a mean is mathematically possible given sample size and integer scale.

    GRIM checks if a reported mean could actually arise from integer data.
    For example, with n=30 on a 1-7 scale, a mean of 3.51 is impossible
    because no integer sum divided by 30 rounds to 3.51.

    A BOUND MAY BE ABSENT, AND THAT IS DIFFERENT FROM A BOUND WE INVENTED.
    `scale_min=None` / `scale_max=None` mean "the paper states no bound on this
    side", and the range check is then skipped ON THAT SIDE ONLY. The two
    branches are independent: GRANULARITY (is the mean a multiple of 1/n?) is
    bound-free and unchanged, so an absent bound removes an accusation path and
    adds none -- a narrowing change (CLAUDE.md 8d, Rule 1). A `None` bound can
    never yield `out_of_range`, and a granularity failure still reaches
    `impossible` under a stated discreteness.

    WHY IT WAS NEEDED. The defaults are 1 and 7, i.e. a Likert scale, and they
    are the caller's only way to say nothing. A count with a definitional floor
    of 0 and no ceiling -- "number of coalition members", mean 35.78 at n = 64 --
    was therefore tested against an INVENTED 1-7 scale and came back
    `suspicious` / `out_of_range` on a perfectly ordinary number. The defaults
    are unchanged, so every existing caller behaves exactly as before.

    Args:
        mean: The reported mean value
        n: Sample size
        scale_min: Minimum value on scale (default 1). `None` means the paper
            states no lower bound; the lower range check is then skipped.
        scale_max: Maximum value on scale (default 7). `None` means the paper
            states no upper bound; the upper range check is then skipped.
        decimals: Number of decimal places in reported mean
        data_type: What the observations ARE. GRIM is defined only for
            integer/likert/count data; anything else is refused rather than
            evaluated. Defaults to `likert`, matching the 1-7 default scale.
        bound_source: `stated` if the paper gives the scale bounds, `assumed`
            (the default) if they are ours. A range violation against a bound we
            invented is capped at `suspicious`; only a STATED bound licenses
            `impossible` (rulebook rule 4).
        discreteness_source: `stated` if the PAPER establishes that the
            observations are integer-valued, `logically_necessary` if they
            cannot be otherwise, `assumed` (the default) if that is our reading.
            The same rule as `bound_source`, applied to the other premise -- see
            `HARD_DISCRETENESS_SOURCES`. A GRANULARITY failure resting on an
            assumed discreteness caps at `suspicious`.

    Returns:
        Dictionary with 'consistent', 'severity', 'failure_mode',
        'grim_consistent', 'possible_means_nearby', and 'methodology'.
    """
    guard = refuse_if_nonfinite(mean=mean, n=n, scale_min=scale_min, scale_max=scale_max)
    if guard is not None:
        return guard

    canonical = canonical_data_type(data_type)
    if canonical not in {"integer", "likert", "count"}:
        return {
            "consistent": False,
            "severity": "indeterminate",
            "applicable": False,
            "data_type": data_type,
            "canonical_data_type": canonical,
            "failure_mode": None,
            "error": (
                f"GRIM does not apply to data_type={data_type!r}; it assumes integer "
                "observations on a bounded scale. Pass integer/likert/count only."
            ),
            "explanation": (
                f"GRIM is defined for integer-valued observations. For "
                f"data_type={data_type!r} the mean is not constrained to multiples of "
                "1/n, so no granularity claim can be made. Not evaluated."
            ),
            "methodology": "GRIM applicability guard.",
        }

    if n <= 0:
        return {
            "error": f"n must be a positive integer (got {n})",
            "severity": "indeterminate",
            "applicable": False,
        }

    granularity = 1 / n
    implied_sum = mean * n
    is_consistent, rounded_sum = _mean_passes_grim(mean, n, decimals)

    # Also check if the sum is within the possible range. A `None` bound is an
    # ABSENT bound, not an infinite one: the comparison on that side is not
    # made, so nothing can be out of range because of it.
    min_sum = scale_min * n if scale_min is not None else None
    max_sum = scale_max * n if scale_max is not None else None
    sum_in_range = ((min_sum is None or min_sum <= rounded_sum)
                    and (max_sum is None or rounded_sum <= max_sum))

    # Find nearby possible means
    possible_means = []
    _lo = rounded_sum - 5 if min_sum is None else max(min_sum, rounded_sum - 5)
    _hi = rounded_sum + 6 if max_sum is None else min(max_sum, rounded_sum + 6)
    for test_sum in range(_lo, _hi):
        possible_mean = round(test_sum / n, decimals)
        if possible_mean not in possible_means:
            possible_means.append(possible_mean)

    consistent = is_consistent and sum_in_range

    # Two distinct failure modes with different evidential weight.
    #
    #   granularity  -- the mean is not a multiple of 1/n. Bound-independent:
    #                   true whatever scale the paper used, so it licenses
    #                   `impossible` on its own.
    #   out_of_range -- the implied sum falls outside the scale. This depends
    #                   entirely on WHOSE bounds those are. Against a bound WE
    #                   assumed, it is capped at `suspicious`; a bound the paper
    #                   stated, or one that is logically necessary (a proportion
    #                   cannot exceed 1, a count cannot be negative), is not our
    #                   invention and licenses `impossible`.
    #
    # Granularity is checked first because it is the stronger claim.
    HARD_BOUNDS = {"stated", "logically_necessary"}
    trunc_ok, trunc_sum = _mean_passes_grim_truncation(mean, n, decimals)
    trunc_in_range = ((min_sum is None or min_sum <= trunc_sum)
                      and (max_sum is None or trunc_sum <= max_sum))
    power = discriminating_power(n, decimals)

    #: GREG'S RULE, 2026-08-11, and the two regimes it creates.
    #:
    #:     "we do the test on only those numbers available, flag it, and then
    #:      test truncation etc. That way the reader can see the apparent
    #:      violation (i.e. our toolkit working) but then judge for themselves
    #:      whether the truncation etc is credible. But I agree to not do the
    #:      decimal expansion if it ALWAYS rescues an otherwise impossible
    #:      finding."
    #:
    #: A CHECK THAT CANNOT FAIL MUST NOT REPORT `consistent`. `consistent` reads
    #: as "we looked and the numbers agree". Where no printable value could have
    #: failed, we did not look at anything, and saying otherwise is a false
    #: all-clear -- the second-worst output this toolkit can produce.
    #:
    #: MEASURED over 159 archived GRIM calls: 90 of them (56.6%) were in a
    #: regime with NO power, and every one returned `consistent`. A further 15
    #: (9.4%) sat in the band where the truncation rescue guarantees
    #: `consistent`. Two thirds of this toolkit's GRIM output was uninformative
    #: and presented as a pass.
    #:
    #: At 2 dp the check is dead for n >= 100 and the rescue is an off switch
    #: for n = 67..99. At 1 dp it is dead for every n >= 10 -- which is where
    #: 72 of those 90 calls were. At 0 dp it is dead everywhere.
    # GATED ON `sum_in_range`, because OUT-OF-RANGE IS A DIFFERENT CLAIM and it
    # does not depend on granularity power at all. A mean of 128.43 on a 1-7
    # scale is outside the scale whatever the sample size and precision are, and
    # an unconditional exit here silently deleted that finding -- caught by two
    # existing tests, one of which pins an `impossible` at stated bounds.
    if not power["check_can_fail"] and sum_in_range:
        # THE UNIT-SLIP CAVEAT SURVIVES THIS EXIT, and must.
        #
        # It is a DIFFERENT check with its own power: it asks whether mean/100
        # is attainable at `decimals + 2`, which is a finer grid than the one
        # that just came back dead. At n = 12 the mean-reading at 1 dp cannot
        # fail while the percentage reading at 3 dp rejects 98.8% of the grid.
        # Caught by the archived false clear this caveat exists for (18.3 at
        # n = 12), which sits exactly in the no-power regime -- so a bare early
        # return would have silently deleted the fix that found it.
        out = {
            "consistent": consistent,
            "severity": "indeterminate",
            "applicable": False,
            "mean": mean, "n": n, "decimals": decimals,
            "failure_mode": "no_discriminating_power",
            "discriminating_power": power,
            "error": (
                f"GRIM cannot fail at n = {n} with {decimals} decimal place"
                f"{'' if decimals == 1 else 's'}, so running it decides nothing."
            ),
            "explanation": (
                f"Every value printable to {decimals} dp is attainable as a mean "
                f"of {n} integers, so no reported figure could have failed this "
                "check. That makes a `consistent` verdict here true and empty: it "
                "is not evidence that the numbers are in order, only that GRIM "
                "has no resolution at this sample size and precision. Reported as "
                "indeterminate so it cannot be read as a pass. GRIM needs either "
                "more decimal places or a smaller n."
            ),
            "methodology": (
                "Power computed exactly, not sampled: attainable means are "
                "{S/n}, and S -> S+n shifts the mean by exactly 1, so one period "
                "of the printable grid settles the whole scale."
            ),
        }
        pct = percentage_reading_disagrees(mean, n, decimals,
                                           scale_min, scale_max, bound_source)
        if pct:
            out["percentage_reading"] = pct
        return out

    if consistent:
        failure_mode = None
        severity = "consistent"
    elif (not is_consistent and trunc_ok and power["rescue_is_an_off_switch"]
            and (trunc_in_range or bound_source not in HARD_BOUNDS)):
        # THE RESCUE THAT RESCUES EVERYTHING IS NOT A RESCUE.
        #
        # Here round-half rejects a real share of the grid and NOTHING survives
        # both conventions. So "it works under truncation" is not a fact about
        # this value -- it is available for every value, and granting it turns a
        # detection into a guaranteed all-clear. This is precisely the case Greg
        # carved out, and the honest answer is that we cannot adjudicate.
        failure_mode = "no_discriminating_power"
        severity = "indeterminate"
    elif not is_consistent and trunc_ok and (
            trunc_in_range or bound_source not in HARD_BOUNDS):
        # BEFORE CALLING IT IMPOSSIBLE, TRY THE TRUNCATION CONVENTION. The
        # round-half check failed, but a truncating reporter (SPSS's default,
        # scrutiny::grim's `rounding = "down"`) is consistent -- a real sample
        # exists whose exact mean the paper floored. That is a reporting-
        # convention choice, not fabrication, so it is `suspicious`, never
        # `impossible`; the same de-escalation SPRITE/GRIMMER use for the
        # population-SD convention.
        #
        # The in-range gate on this rescue may only bind when the bounds are
        # the PAPER'S OWN. Gating it on an assumed bound let our invented
        # scale block the rescue and escalate an honest truncating reporter to
        # `impossible`/granularity (repro: 30 obs on a true 1-10 scale summing
        # to 284, printed 9.46 -- trunc-consistent, but 284 lies outside the
        # assumed 1-7 scale's [30, 210]). With a STATED bound the gate stands:
        # both conventions are then dead inside the paper's own scale, and the
        # granularity branch below correctly reaches `impossible`.
        # GREG'S CALL, 2026-08-10 -- a methodological reversal, recorded as his,
        # in the same register as the STALT threshold decision (#84).
        #
        # "An impossible result that is consistent when truncation is assumed
        #  still deserves to be flagged in some way. It is still suspicious,
        #  though I wouldn't want to classify it as suspicious in the findings."
        #
        # So the SEVERITY is `consistent` -- this never enters the findings as
        # an accusation -- while the fact is retained as `rounding_convention`
        # and counted PER PAPER. One truncation rescue is a house style and
        # carries no information; a high RATE across a paper does, and per
        # Heathers this class of anomaly is commoner in papers with more severe
        # errors. The signal lives in the aggregate, so that is where it is
        # reported: grounds to look harder, not a finding on its own. Same
        # shape as `flag_round_n`, which is documented as "a weak signal that
        # escalates only alongside stronger findings".
        failure_mode = "rounding_convention"
        severity = "consistent"
    elif not is_consistent:
        # THE DISCRETENESS GATE. See `HARD_DISCRETENESS_SOURCES` above for the
        # decision and its reasoning: this branch says "no integer sum divided
        # by n rounds to this mean", which is only an accusation if the
        # observations ARE integers, and that premise arrives as `data_type` --
        # the model's reading, not the paper's demonstrated claim.
        failure_mode = "granularity"
        severity = granularity_ceiling(discreteness_source)
    else:
        failure_mode = "out_of_range"
        severity = "impossible" if bound_source in HARD_BOUNDS else "suspicious"

    # THE SENTENCE HAS TO SAY WHICH SIDE WAS NOT CHECKED. With both bounds
    # present it is byte-identical to what it has always been; an absent bound
    # is named as absent rather than printed as `None`.
    if scale_min is not None and scale_max is not None:
        scale_phrase = f"a {scale_min}-{scale_max} scale"
        range_phrase = f" between {min_sum} and {max_sum}"
    elif scale_min is not None:
        scale_phrase = f"a scale from {scale_min} with no stated upper bound"
        range_phrase = f" of at least {min_sum}"
    elif scale_max is not None:
        scale_phrase = f"a scale up to {scale_max} with no stated lower bound"
        range_phrase = f" of at most {max_sum}"
    else:
        scale_phrase = "a scale with no stated bounds"
        range_phrase = ""

    result = {
        "consistent": consistent,
        "severity": severity,
        "applicable": True,
        "failure_mode": failure_mode,
        "grim_consistent": is_consistent,
        "data_type": data_type,
        "canonical_data_type": canonical,
        "bound_source": bound_source,
        "discreteness_source": discreteness_source,
        "reported_mean": mean,
        "n": n,
        "implied_sum": implied_sum,
        "rounded_sum": rounded_sum,
        "sum_in_range": sum_in_range,
        "granularity": granularity,
        "possible_means_nearby": sorted(possible_means),
        "methodology": (
            f"GRIM test: For n={n} with integer responses on {scale_phrase}, "
            f"the mean must be expressible as X/{n} where X is an integer"
            f"{range_phrase}, rounding to {mean} at {decimals} dp. "
            f"Nearest candidate sum {rounded_sum} gives {rounded_sum}/{n} = "
            f"{rounded_sum / n:.6f}, which {'rounds' if is_consistent else 'does NOT round'} "
            f"back to the reported mean."
        ),
    }

    result["discriminating_power"] = power

    # WHAT THE NUMBERS SAY AS PRINTED, SHOWN RATHER THAN SWALLOWED.
    #
    # GREG, 2026-08-11: "we do the test on only those numbers available, flag
    # it, and then test truncation etc. That way the reader can see the apparent
    # violation (i.e. our toolkit working) but then judge for themselves whether
    # the truncation etc is credible."
    #
    # Before this, a value that failed round-half GRIM and passed under
    # truncation returned `severity: consistent` with the fact recorded only as
    # a per-paper counter. The de-escalation was right -- a truncating reporter
    # is a house style, not fabrication, and it must not enter the findings as
    # an accusation -- but it made the detection INVISIBLE. The reader saw a
    # clean result and had nothing to judge.
    #
    # So the severity stays where Greg put it on 2026-08-10 and the arithmetic
    # comes back into view: what failed, what rescued it, and how often that
    # rescue is available at this n, which is the number that tells a reader
    # whether the truncation reading is a specific explanation or a generic one.
    if failure_mode == "rounding_convention":
        rescue_share = (round((power["round_half_rejects"] - power["both_reject"])
                              / power["round_half_rejects"], 3)
                        if power.get("round_half_rejects") else None)
        result["as_reported"] = {
            "verdict": "granularity" if not is_consistent else "out_of_range",
            "severity_if_taken_at_face_value": (
                granularity_ceiling(discreteness_source) if not is_consistent
                else ("impossible" if bound_source in HARD_BOUNDS else "suspicious")),
            "statement": (
                f"As printed, {mean} is not attainable as the mean of {n} integers "
                f"under the usual round-half convention: the nearest sum, "
                f"{rounded_sum}, gives {rounded_sum / n:.6f}."
            ),
            "explained_by": "truncation",
            "explanation": (
                f"It IS attainable if the paper truncated rather than rounded, "
                f"which SPSS does by default: the sum {trunc_sum} gives "
                f"{trunc_sum / n:.6f}, and a reporter who floors to {decimals} dp "
                f"prints exactly {mean}."
            ),
            "how_often_that_excuse_is_available": rescue_share,
            "judge_for_yourself": (
                "This is not counted as a finding, because a truncating reporter "
                "is a reporting convention and not evidence of anything. It is "
                "shown because the arithmetic did fail as printed, and whether "
                "the truncation reading is credible for THIS paper is a "
                "judgement about the paper's own house style -- check whether "
                "its other figures truncate too. A high RATE across one paper is "
                "the thing worth acting on; a single instance is not."
            ),
        }

    if failure_mode == "no_discriminating_power" and severity == "indeterminate":
        result["applicable"] = False
        result["as_reported"] = {
            "verdict": "granularity",
            "statement": (
                f"As printed, {mean} is not attainable as the mean of {n} integers "
                f"under the round-half convention."
            ),
            "why_we_will_not_call_it": (
                f"At n = {n} and {decimals} dp, EVERY printable value that fails "
                "round-half passes under truncation. So 'it works if they "
                "truncated' is not an explanation of this number -- it is "
                "available for every number, and accepting it here would mean "
                "accepting it always. Neither reading can be ruled out, so this "
                "is recorded as undecidable rather than as a pass or a finding."
            ),
        }
        result["explanation"] = result["as_reported"]["why_we_will_not_call_it"]

    # THE UNIT-SLIP CAVEAT, and it rides on a CONSISTENT verdict specifically.
    # A false clear is the second-worst output this toolkit can produce, and
    # `percentage_reading_disagrees` documents seven archived calls that
    # produced one by sending a percentage where a mean was expected.
    if consistent:
        pct = percentage_reading_disagrees(mean, n, decimals,
                                           scale_min, scale_max, bound_source)
        if pct:
            result["percentage_reading"] = pct

    # Say WHY it was demoted, in the result the reader sees. A verdict silently
    # one rung lower than the arithmetic warrants reads as a weaker finding
    # rather than as a missing premise, and the reader cannot then go and supply
    # the premise.
    if failure_mode == "granularity" and severity != "impossible":
        result["discreteness_caveat"] = DISCRETENESS_CAVEAT

    # WHICH DENOMINATOR WOULD HAVE WORKED -- offered as a question, never as a
    # rescue. `nearby_denominators` carries the measurement showing why it must
    # not move the severity: at n = 20-50, three quarters of GENUINE failures
    # also fit at n +/- 2, so this is a lead, not evidence.
    if failure_mode == "granularity":
        near = nearby_denominators(mean, n, decimals)
        if near:
            result["denominator_question"] = {
                "n_tested": n,
                "n_that_would_fit": near,
                "severity_unchanged": True,
                "ask": (
                    f"This value is GRIM-consistent at n = "
                    f"{', '.join(map(str, near))} but not at the n = {n} used here. "
                    "The denominator we tested is usually the column's enrolled "
                    "total, and the n actually analysed for one outcome is often "
                    "smaller. Ask which n this row was analysed at before treating "
                    "the arithmetic as the answer."
                ),
                "not_evidence": (
                    "This does NOT weaken the finding on its own. Measured over "
                    "4,000 random means per n, 70-80% of genuine GRIM failures at "
                    "n = 20-50 also fit somewhere in n +/- 2 -- so 'it works at a "
                    "nearby n' is what almost every failure looks like, honest or "
                    "not. It is a question worth asking, not a reason to withdraw."
                ),
            }

    return result


#: The percentage GRIM is valid ONLY when the percentage is 100*k/n for an
#: integer count k of the n units -- i.e. a share of the sample. The canonical
#: types that describe such a share are proportion, binary (mean of 0/1) and
#: count. A `continuous` percentage (a mean change "-23.7%", a concentration,
#: a ratio) is NOT k/n and GRIM manufactures an impossibility out of it, so it
#: is refused rather than evaluated -- the same guard grim_test applies to a
#: continuous MEAN. Note the applicable set DIFFERS from grim_test's
#: {integer,likert,count}: a percentage that is a proportion IS testable here,
#: whereas a proportion *mean* is continuous and grim_test refuses it.
#:
#: `nominal` is here because a percentage of an unordered category can only be
#: the share of the sample in that category (Male 27 (45.0%)). It used to be
#: refused: anatomy declares such a variable `nominal`, `dispatch.DISPATCH`
#: routed its n (%) cells here, and every one came back indeterminate.
_PCT_APPLICABLE = {"proportion", "binary", "count", "nominal"}


def grim_test_percentage(
    percentage: float,
    n: int,
    decimals: int | None = None,
    data_type: str = "proportion",
) -> dict:
    """
    Apply GRIM to a percentage (more powerful than means).

    Percentages are fractions of n, so they follow the same logic as GRIM
    but with more decimal places to work with.

    Args:
        percentage: The reported percentage (0-100)
        n: Sample size
        decimals: Decimal places in reported percentage
        data_type: What the percentage IS. GRIM-on-a-percentage is defined only
            when the value is 100*k/n for an integer count k -- a SHARE of the n
            units (proportion / binary / count). A continuous percentage (a mean
            change, a concentration, a ratio) is not k/n, so it is refused rather
            than evaluated. Defaults to `proportion`, the most common share form;
            like grim_test's data_type this is a guard the caller is expected to
            set, not a licence to guess.

    Returns:
        Dictionary with consistency result and possible values
    """
    if decimals is None:
        # NO DEFAULT, AND THE ASYMMETRY IS WHY. Assuming one decimal where the
        # paper printed a whole number shrinks the rounding window tenfold and
        # convicts an honest value; assuming zero where it printed one only
        # widens the window and misses. Those are not symmetric costs, this
        # tool can return `impossible`, and the precision is not ours to guess.
        #
        # MEASURED 2026-08-27 over every deduplicated archived tool call: the
        # model supplied `decimals` on 93 of 93 calls to this tool. The default
        # was never load-bearing -- it was pure downside, and removing it costs
        # nothing measurable. (Contrast `debit_check`, gated identically, whose
        # archived callers omitted it 14 times out of 14: a gate's cost is a
        # property of its callers, not of the gate.)
        # `consistent: None` is the tri-state, not an omission. A consumer
        # reading `result["consistent"]` must get "unknown", not a KeyError and
        # not False -- False would read as "this value is impossible", which is
        # the accusation we are declining to make.
        return {"consistent": None,
                "applicable": False, "severity": "indeterminate",
                "error": ("printed decimals not supplied. Read them off the "
                          "literal the paper printed -- do not infer them from "
                          "a parsed float, which cannot see a trailing zero."),
                "failure_mode": "precondition_absent"}
    guard = refuse_if_nonfinite(percentage=percentage, n=n)
    if guard is not None:
        return guard

    canonical = canonical_data_type(data_type)
    if canonical not in _PCT_APPLICABLE:
        return {
            "consistent": False,
            "severity": "indeterminate",
            "applicable": False,
            "data_type": data_type,
            "canonical_data_type": canonical,
            "reported_percentage": percentage,
            "n": n,
            "error": (
                f"GRIM-on-percentage does not apply to data_type={data_type!r}; "
                "it assumes the percentage is 100*k/n for an integer count k of "
                "the n units. Pass proportion/binary/count (or nominal, for "
                "the share of the sample in a category) only."
            ),
            "explanation": (
                f"A percentage is GRIM-testable only when it is a SHARE of the "
                f"sample (100*k/n). For data_type={data_type!r} -- e.g. a mean "
                "change, a concentration or a ratio -- the value is not "
                "constrained to multiples of 100/n, so no granularity claim can "
                "be made. Not evaluated."
            ),
            "methodology": "GRIM-on-percentage applicability guard.",
        }

    if n <= 0:
        return {
            "error": f"n must be a positive integer (got {n})",
            "severity": "indeterminate",
            "applicable": False,
        }

    # Convert percentage to proportion; a percentage at `decimals` dp has
    # `decimals + 2` dp of precision as a proportion.
    proportion = percentage / 100
    is_consistent, rounded_count = _proportion_passes_grim(
        proportion, n, decimals + 2
    )
    implied_count = proportion * n

    # Check range. On the PROPORTION too: `_proportion_passes_grim` returns a
    # count of 0 for a share outside [0, 1], which passed this test, so 120% at
    # n = 10 went on to the truncation rescue and came back `consistent`.
    in_range = 0.0 <= proportion <= 1.0 and 0 <= rounded_count <= n

    # Find nearby possible percentages
    possible_percentages = []
    for count in range(max(0, rounded_count - 3), min(n, rounded_count + 4)):
        possible_pct = round(100 * count / n, decimals)
        if possible_pct not in possible_percentages:
            possible_percentages.append(possible_pct)

    consistent = is_consistent and in_range

    # TRY THE TRUNCATION CONVENTION BEFORE ACCUSING -- the third and last member
    # of this family to get it. `grim_check` has always tried both; `grim_sweep`
    # got it today; this tool's integrity card said "Only the round-half
    # convention is tried here", which documented the gap without justifying it.
    # There is no reason a PERCENTAGE is less likely to be truncated than a
    # mean; SPSS and several journal styles truncate percentages by default.
    #
    # FOUND BY A REAL RUN: 10.3389/fnins.2023.1186751 reports "9 patients
    # (9.6%)" against its own stated 93 enrolled. 9/93 = 9.6774, which rounds to
    # 9.7 and TRUNCATES to 9.6. We returned `impossible` -- absolute evidence,
    # top of the ladder -- against a paper consistent at its own stated N.
    truncation_ok = False
    if not consistent and in_range:
        truncation_ok = _mean_passes_grim_truncation(proportion, n, decimals + 2)[0]

    # THE SAME POWER ARGUMENT, and the same measurement. A percentage printed
    # to `decimals` dp is a proportion at `decimals + 2`, and the proportion
    # predicate is bit-for-bit the mean predicate (verified), so the identical
    # function settles it. MEASURED: for WHOLE percentages the check is dead at
    # n >= 100 and the truncation rescue is an off switch at n = 78; at 1 dp it
    # survives to n = 200 and dies by n = 1000. Percentages carry two extra
    # digits of resolution, which buys roughly two orders of magnitude in n --
    # and then runs out exactly like the mean check does.
    power = discriminating_power(n, decimals + 2)
    severity = severity_from_consistency(consistent)
    failure_mode = None
    as_reported = None
    if not power["check_can_fail"] and in_range:
        severity = "indeterminate"
        failure_mode = "no_discriminating_power"
        as_reported = {
            "verdict": "granularity",
            "statement": (
                f"Every percentage printable to {decimals} dp is attainable as "
                f"a share of {n}, so no reported figure could have failed."
            ),
            "why_we_will_not_call_it": (
                f"At n = {n} the {decimals}-dp grid is finer than 100/{n}, the "
                "step between attainable percentages. A pass here would be true "
                "and empty -- not evidence the counts are in order, only that "
                "the check has no resolution at this sample size."
            ),
        }
    elif truncation_ok and power["rescue_is_an_off_switch"]:
        # The rescue that rescues everything is not a rescue. Greg's carve-out,
        # applied here for the same reason it is applied to means.
        severity = "indeterminate"
        failure_mode = "no_discriminating_power"
        as_reported = {
            "verdict": "granularity",
            "statement": (
                f"As printed, {percentage}% is not attainable as a share of {n} "
                "under the round-half convention."
            ),
            "why_we_will_not_call_it": (
                f"At n = {n} every percentage that fails round-half passes "
                "under truncation, so 'they truncated' explains this value no "
                "better than it explains any other. Neither reading can be "
                "ruled out, so this is undecidable rather than a pass."
            ),
        }
    elif truncation_ok:
        # Same treatment `grim_check` gives it -- see the decision recorded
        # there. The convention explains the value, so this is not an
        # accusation; it is named rather than escalated, and counted per paper.
        # And, per Greg 2026-08-11, the failed arithmetic is SHOWN rather than
        # swallowed, so the reader has something to judge.
        severity = "consistent"
        failure_mode = "rounding_convention"
        rescue_share = (
            round((power["round_half_rejects"] - power["both_reject"])
                  / power["round_half_rejects"], 3)
            if power.get("round_half_rejects") else None)
        as_reported = {
            "verdict": "granularity",
            "severity_if_taken_at_face_value": "impossible",
            "statement": (
                f"As printed, {percentage}% is not attainable as a share of {n} "
                f"under the round-half convention: the nearest count is "
                f"{rounded_count}, which gives {100 * rounded_count / n:.4f}%."
            ),
            "explained_by": "truncation",
            "explanation": (
                "It IS attainable if the paper truncated rather than rounded, "
                "which SPSS and several journal styles do for percentages by "
                "default."
            ),
            "how_often_that_excuse_is_available": rescue_share,
            "judge_for_yourself": (
                "Not counted as a finding: a truncating reporter is a house "
                "style, not fabrication. It is shown because the arithmetic did "
                "fail as printed. Check whether this paper's other percentages "
                "truncate too -- the RATE is the signal, not one instance."
            ),
        }
    elif not consistent:
        # NAMED, as grim_check names it. This branch used to leave
        # `failure_mode: None` beside `impossible`, so a consumer keying on
        # the mode (benchmarks/grim/score.py) saw no detection: measured
        # 2026-10-18 on Cureus, 12 of 12 such calls were missed. A share
        # outside 0-100% is a range failure, not a granularity one.
        failure_mode = "granularity" if in_range else "out_of_range"

    out = {
        "consistent": consistent,
        "severity": severity,
        "failure_mode": failure_mode,
        "passes_under_truncation": truncation_ok,
        "discriminating_power": power,
        "applicable": bool(power["check_can_fail"]) or not in_range,
        "data_type": data_type,
        "canonical_data_type": canonical,
        "reported_percentage": percentage,
        "n": n,
        "implied_count": implied_count,
        "rounded_count": rounded_count,
        "possible_percentages_nearby": sorted(possible_percentages),
        "methodology": (
            f"GRIM test on percentage (data_type={data_type!r}): for n={n}, a "
            f"percentage that is a share of the sample must be expressible as "
            f"100*X/{n} where X is an integer 0 to {n}. "
            f"Reported {percentage}% implies count = {implied_count:.4f}."
        ),
    }
    if as_reported:
        out["as_reported"] = as_reported
        if "why_we_will_not_call_it" in as_reported:
            out["explanation"] = as_reported["why_we_will_not_call_it"]
    return out


# =============================================================================
# GRIM n-sweep (Heathers §"Reconstructing prevalence")
# =============================================================================

def _proportion_passes_grim(proportion: float, n: int, decimals: int) -> tuple[bool, int]:
    """Return (passes, implied_k) where k is the integer count rounded from
    proportion·n. `decimals` is the precision of the reported proportion."""
    if n <= 0:
        return (False, 0)
    if not (0.0 <= proportion <= 1.0):
        return (False, 0)
    count = proportion * n
    k = round(count)
    if not (0 <= k <= n):
        return (False, k)
    # The proportion `proportion` (as printed to `decimals` dp) must round to
    # the actual fraction k/n. Half-rounding tolerance:
    tol = _rounding.tolerance(decimals)
    return (abs(k / n - proportion) <= tol, k)


def grim_sweep(
    values: list[float],
    n_max: int,
    n_min: int = 2,
    decimals: int | None = None,
    value_type: str = "percentage",
    n_max_source: str = "assumed",
) -> dict:
    """For each reported value, find every n in [n_min, n_max] that passes GRIM,
    then take the intersection across values.

    Use case (Heathers §"Reconstructing prevalence"): a paper reports several
    percentages claimed to come from the same sample, but the cell sizes are
    missing or contested. If the intersection of viable ns is empty, the
    percentages cannot share a single n — so either the n is wrong or the
    percentages refer to different denominators.

    Args:
        values: List of reported percentages (default) or proportions.
        n_max: Largest candidate n (inclusive). Often the claimed total N.
        n_min: Smallest candidate n (inclusive).
        decimals: Decimal places in the reported values. For 49.1% → 1; for
                  0.491 → 3. (For proportions, decimals refers to the
                  proportion's own decimal places.)
        value_type: "percentage" (0–100) or "proportion" (0–1).
        n_max_source: `stated` if n_max is the paper's own total N (or
                  `logically_necessary`), `assumed` (the default) if the range
                  is ours. An empty intersection can only reach `impossible`
                  when the searched range provably brackets the true n — i.e.
                  n_max is the paper's and n_min covers the floor. Against a
                  range WE chose, an empty intersection is a fact about the
                  search, not the paper, and the verdict is `indeterminate`.

    Returns:
        Dict with per-value viable n lists, the joint intersection, and a
        severity verdict if the intersection is empty.
    """
    if decimals is None:
        # NO DEFAULT, AND THE ASYMMETRY IS WHY. Assuming one decimal where the
        # paper printed a whole number shrinks the rounding window tenfold and
        # convicts an honest value; assuming zero where it printed one only
        # widens the window and misses. Those are not symmetric costs, this
        # tool can return `impossible`, and the precision is not ours to guess.
        #
        # MEASURED 2026-08-27 over every deduplicated archived tool call: the
        # model supplied `decimals` on 55 of 55 calls to this tool. The default
        # was never load-bearing -- it was pure downside, and removing it costs
        # nothing measurable. (Contrast `debit_check`, gated identically, whose
        # archived callers omitted it 14 times out of 14: a gate's cost is a
        # property of its callers, not of the gate.)
        # `consistent: None` is the tri-state, not an omission. A consumer
        # reading `result["consistent"]` must get "unknown", not a KeyError and
        # not False -- False would read as "this value is impossible", which is
        # the accusation we are declining to make.
        return {"consistent": None,
                "applicable": False, "severity": "indeterminate",
                "error": ("printed decimals not supplied. Read them off the "
                          "literal the paper printed -- do not infer them from "
                          "a parsed float, which cannot see a trailing zero."),
                "failure_mode": "precondition_absent"}
    if value_type not in ("percentage", "proportion"):
        return {"error": "value_type must be 'percentage' or 'proportion'"}
    if n_max < n_min:
        return {"error": f"n_max ({n_max}) < n_min ({n_min})"}
    if not values:
        return {"error": "no values provided"}

    if value_type == "percentage":
        proportions = [v / 100.0 for v in values]
        # When percentages are reported to `decimals` dp, the corresponding
        # proportion has `decimals + 2` dp of precision.
        proportion_decimals = decimals + 2
    else:
        proportions = list(values)
        proportion_decimals = decimals

    per_value: list[dict] = []
    n_sets: list[set[int]] = []

    for v_orig, p in zip(values, proportions):
        viable: list[dict] = []
        for n in range(n_min, n_max + 1):
            ok, k = _proportion_passes_grim(p, n, proportion_decimals)
            if ok:
                viable.append({"n": n, "k": k, "exact_proportion": k / n})
        per_value.append({
            "value": v_orig,
            "value_as_proportion": p,
            "viable_ns": [v["n"] for v in viable],
            "viable_with_k": viable,
            "n_viable": len(viable),
        })
        n_sets.append({v["n"] for v in viable})

    # Intersection across all values.
    if n_sets:
        joint = set.intersection(*n_sets)
    else:
        joint = set()
    joint_sorted = sorted(joint)

    # An empty intersection is an accusation ONLY if the searched range
    # provably brackets the true n: n_max must be the paper's own stated N
    # (for large enough n every value passes GRIM trivially, so emptiness is
    # ALWAYS range-dependent), and n_min must cover the floor. Against a range
    # we chose, the emptiness is a fact about OUR search -- a true n of 250
    # outside a [20, 200] sweep produces exactly this result from an honest
    # paper -- so the tool refuses rather than accuses.
    HARD_N_SOURCES = {"stated", "logically_necessary"}
    range_provably_brackets_n = n_max_source in HARD_N_SOURCES and n_min <= 2

    # BEFORE ACCUSING, TRY THE OTHER ROUNDING CONVENTION.
    #
    # `grim_test` has done this since the truncation work
    # (`_mean_passes_grim_truncation`, applied with
    # failure_mode="rounding_convention" and capped at `suspicious`).
    # `grim_sweep` never did, and the asymmetry was nobody's decision: the
    # registry documents the choice deliberately for `grim_percentage` and is
    # silent here.
    #
    # MEASURED on the two surviving archived accusations, both from
    # 10.3390--jpm11060545 -- a NON-RETRACTED paper whose finding shipped at
    # `impossible`. The round-half intersection is empty for both; the
    # truncation intersection is not. The Cerebrolysin arm is a genuine rescue:
    # 96.7% and 8.1% share n = 61, which is exactly the arm size implied by the
    # unique split of the paper's stated 119 (59/61 = 96.7213 and 51/58 =
    # 87.9310, summing to 110/119 = 92.4370, all three as printed), and
    # 5/61 = 8.1967 truncates to 8.1. We accused a paper of an impossibility
    # that was an artifact of assuming it rounds.
    truncation_joint: list[int] = []
    if not joint_sorted:
        t_sets = [
            {n for n in range(n_min, n_max + 1)
             if _mean_passes_grim_truncation(p, n, proportion_decimals)[0]}
            for p in proportions
        ]
        truncation_joint = sorted(set.intersection(*t_sets)) if t_sets else []

    if not joint_sorted:
        if truncation_joint:
            # `consistent`, per the decision recorded in `grim_test`: a
            # reporting convention is named and counted, never filed as a
            # suspicious finding.
            severity = "consistent"
            explanation = (
                f"No n in [{n_min}, {n_max}] passes GRIM for all {len(values)} values "
                f"under round-half, but n = "
                f"{', '.join(map(str, truncation_joint[:6]))} does under TRUNCATION, "
                f"which SPSS and several journals use by default. A reporting "
                f"convention explains these values, so they are not impossible "
                f"and this is NOT a finding against the paper. It is recorded as a "
                f"reporting convention and counted per paper, because a high RATE of "
                f"them is what carries information. Read `per_value` before concluding "
                f"anything: a joint solution can be arithmetic coincidence rather "
                f"than the paper's real denominator, and where the per-value sets "
                f"disagree the honest reading is that the values use DIFFERENT "
                f"denominators -- a question for the authors, not a finding."
            )
        elif range_provably_brackets_n:
            severity = "impossible"
            explanation = (
                f"No n in [{n_min}, {n_max}] passes GRIM for ALL {len(values)} "
                "reported values simultaneously under EITHER round-half or "
                "truncation, and n_max is the paper's own "
                "stated N — they cannot share a common denominator at the "
                "stated precision."
            )
        else:
            severity = "indeterminate"
            reason = (
                f"n_max={n_max} is {n_max_source!r}, not the paper's stated N"
                if n_max_source not in HARD_N_SOURCES
                else f"n_min={n_min} > 2 leaves smaller n unchecked"
            )
            explanation = (
                f"No n in [{n_min}, {n_max}] passes GRIM for all {len(values)} "
                f"reported values, but that range is not provably exhaustive "
                f"({reason}): a true n outside it would produce the same empty "
                "intersection from an honest paper. This is a fact about the "
                "searched range, not the paper — not evaluated. Re-run with the "
                "paper's stated total N as n_max and n_max_source='stated' to "
                "license a verdict."
            )
    elif len(joint_sorted) == 1:
        severity = "consistent"
        explanation = (
            f"Unique joint n = {joint_sorted[0]} satisfies GRIM for all "
            "reported values."
        )
    else:
        severity = "consistent"
        explanation = (
            f"{len(joint_sorted)} candidate ns satisfy GRIM for all reported "
            f"values: {joint_sorted}."
        )

    return {
        "severity": severity,
        "explanation": explanation,
        "value_type": value_type,
        "decimals": decimals,
        "n_min": n_min,
        "n_max": n_max,
        "n_max_source": n_max_source,
        "per_value": per_value,
        "joint_viable_ns": joint_sorted,
        "joint_viable_ns_truncation": truncation_joint,
        "failure_mode": "rounding_convention" if truncation_joint else None,
        "methodology": (
            f"GRIM sweep: for each reported {value_type} v, enumerate all n in "
            f"[{n_min}, {n_max}] such that round(v·n) is an integer in [0, n] "
            f"AND round(v·n)/n rounds back to v at {proportion_decimals} dp. "
            "Joint viable n-set is the intersection across all values. When that "
            "intersection is empty the sweep is repeated under the TRUNCATION "
            "convention before any verdict, because a truncating reporter is a "
            "reporting convention and not an impossibility -- `grim_test` has "
            "always done this and this tool did not."
        ),
    }


# =============================================================================
# 2×2 contingency-table reconstruction (Heathers §"Reconstructing contingency
# tables")
# =============================================================================

def reconstruct_2x2(
    pct_col1: float,
    pct_col2: float,
    n_total: int,
    decimals: int | None = None,
    value_type: str = "percentage",
    reported_chi2: Optional[float] = None,
    chi2_tolerance: float = 0.05,
    balance_ratio_max: float = 4.0,
) -> dict:
    """Reconstruct a 2×2 table from two column-conditional percentages.

    Layout (matching Heathers' SICK/WELL × INTERVENTION/CONTROL example):

        ┌────────────┬───────────────┬──────────┐
        │            │ INTERVENTION  │ CONTROL  │
        ├────────────┼───────────────┼──────────┤
        │ outcome 1  │      A        │    B     │
        │ outcome 2  │      C        │    D     │
        └────────────┴───────────────┴──────────┘

    With A + B + C + D = n_total. The two reported percentages are
    pct_col1 = A / (A + C) and pct_col2 = B / (B + D).

    The trick: enumerate every column-total pair (col1 = A + C,
    col2 = B + D) such that col1 + col2 = n_total. For each, GRIM-check
    whether pct_col1 produces an integer A consistent with col1 (and
    likewise for B). Surface every (A, B, C, D) that survives.

    Args:
        pct_col1: Column-1-conditional percentage (or proportion if
                  value_type='proportion').
        pct_col2: Column-2-conditional percentage.
        n_total: Total N.
        decimals: Decimals in the reported percentages.
        value_type: "percentage" or "proportion".
        reported_chi2: Optional reported χ² to filter solutions by.
        chi2_tolerance: Absolute tolerance on χ² match.
        balance_ratio_max: SORTS the reconstructions -- splits more imbalanced
                           than this (default 4:1) are held back from the primary
                           `candidates` list. It does NOT decide possibility: a
                           valid but imbalanced 2×2 (149 vs 29, ordinary in
                           observational data) is still a reconstruction, never an
                           impossibility. Set large to surface every split first.
    """
    if decimals is None:
        # NO DEFAULT, AND THE ASYMMETRY IS WHY. Assuming one decimal where the
        # paper printed a whole number shrinks the rounding window tenfold and
        # convicts an honest value; assuming zero where it printed one only
        # widens the window and misses. Those are not symmetric costs, this
        # tool can return `impossible`, and the precision is not ours to guess.
        #
        # MEASURED 2026-08-27 over every deduplicated archived tool call: the
        # model supplied `decimals` on 24 of 24 calls to this tool. The default
        # was never load-bearing -- it was pure downside, and removing it costs
        # nothing measurable. (Contrast `debit_check`, gated identically, whose
        # archived callers omitted it 14 times out of 14: a gate's cost is a
        # property of its callers, not of the gate.)
        # `consistent: None` is the tri-state, not an omission. A consumer
        # reading `result["consistent"]` must get "unknown", not a KeyError and
        # not False -- False would read as "this value is impossible", which is
        # the accusation we are declining to make.
        return {"consistent": None,
                "applicable": False, "severity": "indeterminate",
                "error": ("printed decimals not supplied. Read them off the "
                          "literal the paper printed -- do not infer them from "
                          "a parsed float, which cannot see a trailing zero."),
                "failure_mode": "precondition_absent"}
    from .chi_squared import recalc_chi_squared  # local import to avoid cycles

    if value_type == "percentage":
        p1 = pct_col1 / 100.0
        p2 = pct_col2 / 100.0
        prop_dec = decimals + 2
    elif value_type == "proportion":
        p1 = pct_col1
        p2 = pct_col2
        prop_dec = decimals
    else:
        return {"severity": "indeterminate", "applicable": False,
                "error": "value_type must be 'percentage' or 'proportion'"}

    if n_total < 4:
        return {"severity": "indeterminate", "applicable": False,
                "error": "n_total must be ≥ 4 for a 2×2 reconstruction"}

    # The balance filter is a PLAUSIBILITY SORT, never a feasibility test. A valid
    # but imbalanced 2×2 (149 vs 29 -- ordinary in observational designs) is still
    # a reconstruction, so filtering it out BEFORE the possible/impossible decision
    # turned "possible via an imbalanced split" into "impossible", the strongest
    # severity the toolkit has, on OUR heuristic. Segregate the two rather than
    # discard, and decide impossibility over EVERY split.
    candidates: list[dict] = []      # within the balance filter -- surfaced first
    imbalanced: list[dict] = []      # valid, but a more imbalanced split than allowed
    for col1 in range(1, n_total):
        col2 = n_total - col1
        if col1 == 0 or col2 == 0:
            continue

        ok1, A = _proportion_passes_grim(p1, col1, prop_dec)
        ok2, B = _proportion_passes_grim(p2, col2, prop_dec)
        if not (ok1 and ok2):
            continue

        C = col1 - A
        D = col2 - B
        if C < 0 or D < 0:
            continue

        cand = {
            "A": A, "B": B, "C": C, "D": D,
            "col1_total": col1, "col2_total": col2,
            "row1_total": A + B, "row2_total": C + D,
            "implied_pct_col1": (A / col1) * (100.0 if value_type == "percentage" else 1.0),
            "implied_pct_col2": (B / col2) * (100.0 if value_type == "percentage" else 1.0),
        }

        if reported_chi2 is not None:
            chi_result = recalc_chi_squared(
                observed=[[A, B], [C, D]],
                reported_chi2=reported_chi2,
                use_yates=False,
            )
            chi2_calc = chi_result.get("calculated_chi2")
            cand["calculated_chi2"] = float(chi2_calc) if chi2_calc is not None else None
            cand["chi2_match"] = bool(
                cand["calculated_chi2"] is not None
                and abs(cand["calculated_chi2"] - reported_chi2) <= chi2_tolerance
            )

        ratio = max(col1, col2) / min(col1, col2)
        (imbalanced if ratio > balance_ratio_max else candidates).append(cand)

    any_feasible = bool(candidates or imbalanced)

    # Filter by reported χ² if asked -- applied to BOTH lists.
    if reported_chi2 is not None:
        n_pre = len(candidates) + len(imbalanced)
        candidates = [c for c in candidates if c.get("chi2_match")]
        imbalanced = [c for c in imbalanced if c.get("chi2_match")]
        chi2_filter_note = (
            f"{n_pre} reconstruction(s) GRIM-passed; {len(candidates) + len(imbalanced)} "
            f"additionally match reported χ² = {reported_chi2} (tolerance ±{chi2_tolerance})."
        )
    else:
        chi2_filter_note = ""

    n_solutions = len(candidates)
    if not any_feasible:
        # No integer 2×2 reproduces the percentages for ANY column split. This is
        # arithmetic and bound-free -- the genuine GRIM-family impossibility.
        severity = "impossible"
        explanation = (
            f"No 2×2 table with column totals summing to {n_total} can produce both "
            f"reported percentages ({pct_col1}, {pct_col2}) at the stated precision "
            f"(decimals={decimals}) -- every column split was checked, not only the "
            "balanced ones."
        )
    elif reported_chi2 is not None and not candidates and not imbalanced:
        # Reconstructions exist, but none reproduces the reported χ². Decline rather
        # than accuse: the recompute here is Pearson (use_yates=False), so a
        # Yates-corrected or differently-rounded reported χ² mismatches a perfectly
        # valid table. Not an impossibility, and not an accusation.
        severity = "indeterminate"
        explanation = (
            f"Valid 2×2 reconstructions exist, but none reproduces the reported "
            f"χ² = {reported_chi2} (Pearson, tolerance ±{chi2_tolerance}). This may be a "
            "Yates-corrected or rounded χ², so no verdict is drawn on the table."
        )
    elif not candidates and imbalanced:
        # A valid table exists, but only for a split more imbalanced than the
        # plausibility filter. Imbalanced 2×2s are ordinary in observational data,
        # so this is consistent -- NOT the impossibility the filter used to report.
        ex = imbalanced[0]
        severity = "consistent"
        explanation = (
            f"The percentages reconstruct to a valid 2×2, but only for a column split "
            f"more imbalanced than {balance_ratio_max}:1 (e.g. columns "
            f"{ex['col1_total']}/{ex['col2_total']}). An imbalanced split is ordinary "
            "in observational data, so this is consistent, not impossible."
        )
        candidates = imbalanced
        n_solutions = len(candidates)
    elif n_solutions == 1:
        severity = "consistent"
        explanation = "Unique reconstruction found."
    else:
        severity = "consistent"
        explanation = f"{n_solutions} candidate reconstructions found."

    return {
        "severity": severity,
        "explanation": explanation,
        "n_total": n_total,
        "reported_pct_col1": pct_col1,
        "reported_pct_col2": pct_col2,
        "decimals": decimals,
        "value_type": value_type,
        "balance_ratio_max": balance_ratio_max,
        "reported_chi2": reported_chi2,
        "candidates": candidates,
        "n_solutions": n_solutions,
        "n_solutions_outside_balance": len(imbalanced),
        "chi2_filter_note": chi2_filter_note,
        "methodology": (
            "2×2 reconstruction: for EVERY (col1, col2) with col1+col2 = "
            f"{n_total}, test whether both reported column-conditional percentages "
            "GRIM-pass at the chosen precision; each surviving (col1, col2) gives "
            f"one candidate (A, B, C, D). Possibility is decided over all splits; "
            f"the {balance_ratio_max}:1 balance ratio only sorts plausible splits "
            "ahead of imbalanced ones."
            + (" χ² filter applied." if reported_chi2 is not None else "")
        ),
    }
