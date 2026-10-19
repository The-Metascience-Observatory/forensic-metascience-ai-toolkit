"""
Ratio Check

Verify a reported ratio against the numerator and denominator printed beside
it: cost-effectiveness ratios (ICERs), rates, cost-per-outcome, "X per Y".

WHY THIS EXISTS. The toolkit could recompute sums, t-tests, chi-squareds and
correlations, but nothing verified a DIVISION -- and a health-economics paper's
entire result is one. MEASURED: a cost-utility analysis printed all three
columns of its central table (cost increment, QALY increment, and the
resulting ICER) and the pipeline recorded "Table 2 Deterministic ICER column --
no tool performs ratio/division verification" under `not_checked`. Worked by
hand, the three rows implied three different incremental costs (EUR 270, 263
and 309) where there can only be one, and none matched the EUR 408 the paper
stated in its own methods. That is the paper's headline finding, checkable from
the page alone, and it was skipped for want of an operator.

The load-bearing output is `implied_denominator` / `implied_numerator`: saying
"this row implies a cost of EUR 270 and that one EUR 309" is what makes a
ratio table's inconsistency legible, far more than a pass/fail flag.
"""

import math

from . import rounding as _rounding
from .severity import CONSISTENT, INDETERMINATE, SUSPICIOUS


def _unusable(v) -> bool:
    # A bool, a string, None, a NaN or an infinity is never a number a paper
    # printed: it is OUR extraction failing. Judging it manufactures a claim
    # about the paper out of our own defect.
    return (isinstance(v, bool) or not isinstance(v, (int, float))
            or not math.isfinite(v))


def check_ratio(
    numerator: float,
    denominator: float,
    reported_ratio: float,
    decimals_numerator: int | None = None,
    decimals_denominator: int | None = None,
    decimals_ratio: int | None = None,
    description: str = "ratio",
) -> dict:
    """Does a printed ratio follow from the numerator and denominator printed with it?

    Every input is rounded, and a quotient's slack depends on BOTH printed
    precisions and on the magnitude of the denominator -- B/SE with SE = 0.5
    tolerates about +/-0.5, the same precisions with SE = 0.05 about +/-11. So
    the attainable interval is computed at the corners of the rounding
    rectangle via `rounding.quotient_interval` rather than against any fixed
    tolerance, and the reported value is judged against its own printed
    precision.

    Args:
        numerator: The printed numerator (e.g. an incremental cost).
        denominator: The printed denominator (e.g. an incremental QALY).
        reported_ratio: The ratio as printed (e.g. the ICER).
        decimals_numerator / decimals_denominator / decimals_ratio: Printed
            decimals of each, read from the literals. Required: there is no
            safe default, since guessing sets a window that either clears
            everything or accuses on rounding alone.
        description: What the ratio represents, for the report.

    Returns:
        Dict with `consistent`, `severity`, the attainable interval, and the
        numerator/denominator each implied by the other two printed values.
    """
    for label, v in (("numerator", numerator), ("denominator", denominator),
                     ("reported_ratio", reported_ratio)):
        if _unusable(v):
            return {
                "consistent": None,
                "severity": INDETERMINATE,
                "error": (
                    f"{label} is not a finite number ({v!r}). That is an input "
                    "defect on our side, not evidence about the paper, so the "
                    "check refuses rather than judges."
                ),
            }

    dps = {"numerator": decimals_numerator,
           "denominator": decimals_denominator,
           "ratio": decimals_ratio}
    missing = [k for k, d in dps.items() if d is None]
    if missing:
        return {
            "consistent": None,
            "severity": INDETERMINATE,
            "error": (
                f"printed precision not supplied for: {', '.join(missing)}. "
                "A quotient's tolerance depends on both inputs' precision and "
                "on the denominator's magnitude, so there is no safe default: "
                "guessing either clears every ratio or accuses on rounding "
                "alone. Read the decimals off the literals as printed."
            ),
        }
    if any(d < 0 for d in dps.values()):
        return {
            "consistent": None,
            "severity": INDETERMINATE,
            "error": (f"decimals must be >= 0 (got {dps!r}); a negative "
                      "printed precision does not exist."),
        }

    if denominator == 0:
        return {
            "consistent": None,
            "severity": INDETERMINATE,
            "error": "denominator is zero; the ratio is undefined.",
        }

    computed = numerator / denominator
    attainable = _rounding.quotient_interval(
        numerator, int(decimals_numerator),
        denominator, int(decimals_denominator))
    if attainable is None:
        # The denominator's own rounding interval straddles zero, so the
        # quotient is unbounded. A tiny printed denominator (an ICER's QALY
        # increment at 3 dp is the live case) makes this common, and it is a
        # REFUSAL, not a pass.
        return {
            "consistent": None,
            "severity": INDETERMINATE,
            "computed_ratio": computed,
            "reported_ratio": reported_ratio,
            "error": (
                f"the denominator {denominator} printed to "
                f"{decimals_denominator} dp could be zero within its own "
                "rounding interval, so the attainable ratio is unbounded and "
                "no comparison is meaningful."
            ),
            "methodology": (
                f"{description}: refused. Rounding interval of the denominator "
                "includes zero."
            ),
        }

    lo, hi = attainable
    r_lo, r_hi = _rounding.interval(reported_ratio, int(decimals_ratio))
    consistent = not (hi < r_lo or lo > r_hi)

    # What the OTHER two printed values imply about each input. This is the
    # number that makes a table legible: three ICER rows implying three
    # different incremental costs is a contradiction a reader can see, where
    # three failed comparisons are just three failures.
    implied_denominator = (numerator / reported_ratio
                           if reported_ratio != 0 else None)
    implied_numerator = reported_ratio * denominator

    result = {
        "consistent": consistent,
        "computed_ratio": computed,
        "reported_ratio": reported_ratio,
        "attainable_ratio_interval": [lo, hi],
        "reported_ratio_interval": [r_lo, r_hi],
        "implied_denominator": implied_denominator,
        "implied_numerator": implied_numerator,
        "inputs": {
            "numerator": numerator, "denominator": denominator,
            "reported_ratio": reported_ratio,
            "decimals_numerator": decimals_numerator,
            "decimals_denominator": decimals_denominator,
            "decimals_ratio": decimals_ratio,
        },
    }

    if consistent:
        result["severity"] = CONSISTENT
        result["explanation"] = (
            f"{description}: the printed {reported_ratio:g} follows from "
            f"{numerator} / {denominator} at the stated precision."
        )
        result["methodology"] = (
            f"{description}: {numerator} / {denominator} = {computed:.6g}, "
            f"attainable over the printed rounding box as "
            f"[{lo:.6g}, {hi:.6g}], which meets the reported {reported_ratio:g} "
            f"read at {decimals_ratio} dp."
        )
        return result

    # CAPPED AT `suspicious`, DELIBERATELY. The arithmetic is exact, but a
    # printed ratio has more innocent explanations than a printed sum: it may
    # be computed from unrounded values the paper never shows, from a
    # discounted or half-cycle-corrected quantity, or from a subgroup. Naming
    # the implied denominator lets a reader judge which, and that is worth more
    # than a stronger label this check cannot actually support.
    result["severity"] = SUSPICIOUS
    result["failure_mode"] = "ratio_not_reproducible"
    result["explanation"] = (
        f"{description}: {numerator} / {denominator} gives {computed:.6g}, not "
        f"the printed {reported_ratio:g}. For the printed value to hold the "
        f"denominator would have to be {implied_denominator:.6g}, not "
        f"{denominator}."
    )
    result["methodology"] = (
        f"{description}: {numerator} / {denominator} = {computed:.6g}, "
        f"attainable over the printed rounding box as [{lo:.6g}, {hi:.6g}], "
        f"which does not meet the reported {reported_ratio:g} read at "
        f"{decimals_ratio} dp (interval [{r_lo:.6g}, {r_hi:.6g}]). For the "
        f"reported value to hold, the denominator would have to be "
        f"{implied_denominator:.6g} rather than the printed {denominator}, or "
        f"the numerator {implied_numerator:.6g} rather than {numerator}. "
        "Ratios are often computed from unrounded intermediates, so treat a "
        "single mismatch as a question; several rows of one table implying "
        "DIFFERENT values for a quantity that can only have one is the "
        "stronger signal."
    )
    return result
