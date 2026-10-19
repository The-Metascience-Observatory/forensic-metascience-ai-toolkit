"""Does the printed COUNT over the printed denominator give the printed PERCENTAGE?

WHY THIS EXISTS: A FALSE CLEAR, WHICH IS THE SECOND-WORST OUTPUT THIS TOOLKIT
CAN PRODUCE.

A clinical table cell reads `142 (73.0)` at n = 200. `parse_cells` reads both
halves and returns `count: 142, percent: 73.0` -- I checked. The dispatcher then
routes the cell to `grim_percentage` and to nothing else, and
`grim_percentage`'s schema has no `count` parameter, so the count is dropped at
the argument boundary.

GRIM then asks the wrong question. It asks whether 73.0 is ATTAINABLE as
100k/200 for SOME integer k -- and it is, at k = 146 -- so it returns
`consistent`. Reproduced exactly:

    grim_percentage(percentage=73.0, n=200, decimals=1) -> consistent

But the paper did not print k = 146. It printed 142, and 100 * 142 / 200 = 71.0.
The cell is internally inconsistent and every check we ran on it passed.

That is the shape this repo cares about most: not a missing check that refuses
loudly, but a check that answers a nearby question and reports success. GRIM is
the right tool when only a percentage is printed. When the count is printed too,
the exact arithmetic is available and strictly stronger, and it was being thrown
away.

WHY THIS DOES NOT REACH `impossible`, EVER.

The innocent explanation is not exotic, it is the single commonest convention in
clinical tables: THE PERCENTAGE MAY BE OF A DIFFERENT BASE. Row percentages and
column percentages sit in the same table, subgroup percentages are taken over
the subgroup, and "% of those with complete data" is taken over a denominator
that appears nowhere near the cell. A mismatch between `count/n` and the printed
percentage is therefore evidence about WHICH DENOMINATOR WAS USED at least as
often as it is evidence about the arithmetic.

So the result is capped at `suspicious`, and -- more useful than the flag -- it
reports the denominator the percentage actually implies. A human reading
"implied denominator 194.5" resolves the question instantly, and one reading
"implied denominator 1293, which is the column header's n" has learned the cell
is fine and the base is elsewhere.

WHEN THE COUNT EXCEEDS ITS OWN DENOMINATOR the answer is not `suspicious` at
all. A count larger than n with a percentage at or below 100 is a proof that
this n is not the base for this percentage -- which is a fact about our pairing,
not about the paper. It returns `indeterminate` and says so.
"""
from __future__ import annotations

from .severity import CONSISTENT, INDETERMINATE, SUSPICIOUS, refuse_if_nonfinite

#: Nothing here may exceed this. See the module docstring: a different
#: percentage base is an ordinary reporting convention, not a defect, and no
#: amount of arithmetic disagreement rules it out.
CEILING = SUSPICIOUS

METHODOLOGY = (
    "Exact arithmetic on the paper's own printed count and denominator, compared "
    "against its own printed percentage within that percentage's rounding "
    "interval. Strictly stronger than GRIM where the count is printed: GRIM asks "
    "whether the percentage is attainable for SOME integer numerator, this asks "
    "whether it matches THE numerator the paper printed."
)


def check_count_percent(
    count: int,
    percentage: float,
    n: int,
    decimals: int | None = None,
    source_quote: str | None = None,
    source_locator: str | None = None,
) -> dict:
    """Compare `100 * count / n` against the printed percentage.

    Args:
        count: The numerator the paper printed, e.g. 142 in `142 (73.0)`.
        percentage: The percentage the paper printed, e.g. 73.0.
        n: The denominator this percentage is believed to be over.
        decimals: Printed decimals of `percentage`. REQUIRED for a verdict --
            read it off the literal. Without it the rounding interval is
            unknown, and guessing one is how a correctly-reported cell becomes
            an accusation; the result is `indeterminate` instead.

    Returns a severity, the implied denominator, and the interval it was judged
    against.
    """
    out: dict = {
        "check": "count_vs_percent",
        "reported_count": count,
        "reported_percentage": percentage,
        "n": n,
        "decimals": decimals,
        "methodology": METHODOLOGY,
        "ceiling": CEILING,
        "source_quote": source_quote,
        "source_locator": source_locator,
        "source_quote_supplied": bool(source_quote),
    }

    # NaN and infinity are what an extraction produces from an empty cell or a
    # dash, not values a paper printed. The registry's `ToolSpec.call` guards
    # this, but `cli.py` calls the raw function -- so a NaN count reached the
    # comparison and returned `suspicious` on "nan/100 = nan%".
    bad = refuse_if_nonfinite(count=count, percentage=percentage, n=n)
    if bad:
        return {**out, **bad, "applicable": False}

    if not n or n <= 0:
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": "no positive denominator, so there is nothing to divide by"}
    if count is None or percentage is None:
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": "needs both the printed count and the printed percentage"}

    # THE PRECISION GATE. Same rule as every other check here: a printed number
    # asserts an interval, and inventing its width is the fastest route to a
    # false accusation against a correctly-reported cell.
    if decimals is None:
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": ("printed decimals of the percentage were not supplied, so its "
                          "rounding interval is unknown"),
                "explanation": ("Read the decimals off the literal -- `73.0` is one, `73` "
                                "is zero -- and call again. Assuming a precision would "
                                "decide the verdict on a number nobody supplied.")}

    computed = 100.0 * count / n
    # THE WINDOW MUST ADMIT TRUNCATION, NOT ONLY ROUNDING.
    #
    # VERIFIED FALSE ACCUSATION, found by red-teaming this check on the day it
    # was written. An honest table of 897 people with percentages TRUNCATED at
    # 2 dp -- 311 (34.67), 208 (23.18), 253 (28.20), 125 (13.93) -- had its
    # denominator correctly derived by `composite.split_sections`, and was then
    # convicted by this check on 3 of its 4 cells, publishing `suspicious` for
    # the whole table.
    #
    # The n was never wrong. The two modules disagreed about ROUNDING:
    # `composite._PCT_CELL_TOLERANCE` is 0.011, explicitly "doubled for the
    # round-half vs truncation ambiguity the rest of the toolkit already
    # accommodates", while this used a half-ulp of 0.005. So a truncating table
    # passed section verification and was then accused by the check that runs on
    # the very cells that certified the denominator.
    #
    # A truncated percentage is always <= the true value and never below it by a
    # full ulp, so the window is asymmetric: a full ulp BELOW the printed value
    # and a half ulp above. `debit` accommodates the same convention.
    ulp = 10.0 ** -decimals
    half = 0.5 * ulp
    lo, hi = percentage - half, percentage + ulp
    implied = (100.0 * count / percentage) if percentage else None

    out.update({
        "computed_percentage": round(computed, 6),
        "rounding_interval": [round(lo, 6), round(hi, 6)],
        "implied_denominator": round(implied, 4) if implied else None,
    })

    # `>=`, not `>`. Off-by-one found by the same red team: `count == n` forces
    # 100%, so a printed percentage below 100 proves the pairing is wrong by
    # exactly the argument below -- yet `count == n` was flagged while one
    # person more was excused.
    if count >= n and percentage < 100 - half:
        # NOT an accusation. A count larger than its denominator, with a
        # percentage at or under 100, proves this n is not the base for this
        # percentage -- a fact about OUR pairing, not about the paper.
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "consistent": None,
                "error": f"the count {count} exceeds the denominator {n}",
                "explanation": (
                    f"A count cannot exceed its own denominator, so {n} is not the base "
                    f"for this percentage. The printed percentage implies a denominator "
                    f"of about {implied:.0f}. This says the pairing is wrong, not that "
                    "the paper is." if implied else
                    f"A count cannot exceed its own denominator, so {n} is not the base.")}

    if lo <= computed <= hi:
        # WHICH CONVENTION WAS NEEDED, said out loud. `grim_percentage` already names
        # this when a value fits only under truncation, and two checks on one
        # cell should not disagree about what they accepted. Reported, never
        # escalated: a truncating reporter is a convention, not a defect.
        needed = "truncation" if computed > percentage + half else None
        if needed:
            out["rounding_convention"] = needed
        return {**out, "severity": CONSISTENT, "applicable": True, "consistent": True,
                "explanation": (
                    f"{count}/{n} = {computed:.{max(decimals, 2)}f}%, which matches the "
                    f"printed {percentage}. The count and the percentage agree."
                    + (" This fits only if the reporter TRUNCATES rather than rounds "
                       "-- SPSS's default and several journal styles do. A convention, "
                       "not a defect, but say which one was needed." if needed else ""))}

    return {**out, "severity": CEILING, "applicable": True, "consistent": False,
            "difference": round(computed - percentage, 6),
            "explanation": (
                f"{count}/{n} = {computed:.{max(decimals, 2)}f}%, but the paper prints "
                f"{percentage}, outside the rounding interval "
                f"[{lo:.{max(decimals, 2)}f}, {hi:.{max(decimals, 2)}f}]. "
                f"The printed percentage implies a denominator of about "
                f"{implied:.1f} rather than {n}."
                if implied else ""),
            "alternative_reading": (
                "A percentage taken over a DIFFERENT base is the commonest reason for "
                "this and is not an error: row versus column percentages sit in the same "
                "table, and subgroup percentages are taken over the subgroup. Check the "
                "implied denominator against the other denominators in the table before "
                "treating this as a defect."),
            }
