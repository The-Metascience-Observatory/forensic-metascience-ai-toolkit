"""
Summation Check

Verify that values sum to expected totals (e.g., percentages to 100).
"""


def check_summation(
    values: list[float],
    expected_sum: float,
    tolerance: float | None = None,
    description: str = "values",
    decimals: "list[int] | int | None" = None,
    decimals_total: int | None = None,
) -> dict:
    """
    Check if values sum to expected total.

    ROUNDING. Each addend was rounded independently, so each contributes its
    own half-width to the total -- and the total was rounded too. A column of
    twenty values printed to one decimal permits the sum to be off by +/-1.0
    before anything is wrong; two values printed to two decimals permit +/-0.01.
    The old default of a flat 0.5 is wrong in both directions -- twenty times
    too tight for the first column and fifty times too loose for the second --
    and it was a DEFAULT, so it applied wherever a caller did not think about
    it, which per the batch docstring is most of the 55 calls a real review
    makes.

    Args:
        values: List of values that should sum
        expected_sum: Expected total
        tolerance: An EXPLICIT window, overriding the rounding calculation.
            Use it when something other than rounding sets the window -- a
            count column that must hold exactly takes `tolerance=0`.
        description: What the values represent (for reporting)
        decimals: Printed precision of the addends: one int per value, or a
            single int if they share one. Read from the literals.
        decimals_total: Printed precision of `expected_sum`.

    Returns:
        Dictionary with summation check result
    """
    import math

    from . import rounding as _rounding
    from .severity import CONSISTENT, INDETERMINATE, SUSPICIOUS

    def _unusable(v) -> bool:
        # A bool, a string, None, a NaN or an infinity is never a number a
        # paper printed: it is OUR extraction failing (an unparsed cell, an
        # upstream overflow). Judging it manufactures a claim about the paper
        # out of our own defect, so every one of these is refused instead.
        return (isinstance(v, bool) or not isinstance(v, (int, float))
                or not math.isfinite(v))

    if not isinstance(values, (list, tuple)) or not values:
        return {"error": "no values provided", "severity": INDETERMINATE}

    bad = [v for v in values if _unusable(v)]
    if bad or _unusable(expected_sum):
        return {
            "values": values,
            "expected_sum": expected_sum,
            "is_consistent": None,
            "severity": INDETERMINATE,
            "error": (
                "non-numeric or non-finite input "
                f"(offending: {(bad or [expected_sum])!r}). These arise from "
                "OUR extraction failing, never from a printed number, so the "
                "check refuses rather than judges."
            ),
            "methodology": (
                f"Summation refused: {description} contained a value that is "
                "not a finite number, which is an input defect on our side, "
                "not evidence about the paper."
            ),
        }

    actual_sum = sum(values)
    difference = actual_sum - expected_sum

    if isinstance(decimals, int) and not isinstance(decimals, bool):
        dp_each = [decimals] * len(values)
    elif isinstance(decimals, list) and len(decimals) == len(values):
        try:
            dp_each = [int(d) for d in decimals]
        except (TypeError, ValueError):
            dp_each = None    # unreadable precision -> the refusal below
    else:
        dp_each = None
    if dp_each is not None and any(d < 0 for d in dp_each):
        # decimals=-1 means half_width 5.0: a window wide enough to clear
        # anything, i.e. an automatic all-clear from a nonsense input.
        return {
            "values": values,
            "expected_sum": expected_sum,
            "is_consistent": None,
            "severity": INDETERMINATE,
            "error": (
                f"decimals must be >= 0 (got {decimals!r}): a negative printed "
                "precision does not exist, and inventing one widens the window "
                "into an automatic pass."
            ),
        }

    if tolerance is not None:
        if _unusable(tolerance) or tolerance < 0:
            return {
                "values": values,
                "expected_sum": expected_sum,
                "is_consistent": None,
                "severity": INDETERMINATE,
                "error": (
                    f"tolerance must be a finite value >= 0 (got {tolerance!r})."
                ),
            }
        # EPSILON so float representation noise (0.1 + 0.2 != 0.3 by 5.6e-17)
        # can never overrun an explicit window on its own; matches the slack
        # the printed-precision path below already carries.
        window = float(tolerance) + _rounding.EPSILON
        basis = "explicit tolerance"
        dp_total = decimals_total
    elif dp_each is None:
        # REFUSE rather than guess. There is no safe default: inferring from
        # the parsed floats reads a percentage printed "5" as 5.0 and makes the
        # window ten times too tight, while widening every integral value to
        # 0 dp gives a twenty-value column a window of +/-10 percentage points,
        # which clears anything. The old flat 0.5 was the first of those errors
        # -- twenty times too tight for a 1 dp column of twenty values -- and it
        # was a DEFAULT, so it applied wherever nobody thought about it.
        return {
            "values": values,
            "actual_sum": actual_sum,
            "expected_sum": expected_sum,
            "difference": difference,
            "is_consistent": None,
            "severity": INDETERMINATE,
            "tolerance": None,
            "tolerance_basis": "unknown -- no printed precision supplied",
            "error": (
                "Cannot evaluate: the window a sum is allowed depends on how "
                "many addends there are and how precisely each was printed. "
                "Supply `decimals` (one int per value, or a single int if they "
                "share one) and `decimals_total`, or `tolerance` if some "
                "constraint other than rounding sets the window."
            ),
            "methodology": (
                f"Summation refused: {description} sum to {actual_sum} against "
                f"{expected_sum} (difference {difference}), but with no printed "
                "precision there is no defensible window to test that against."
            ),
        }
    else:
        # The total was rounded too, and its precision is NOT the addends'. A
        # percentage column printed to 1 dp is routinely totalled as a bare
        # `100`, which is 0 dp and worth +/-0.5 on its own -- half the window
        # of a twenty-row column, contributed by one number.
        #
        # Read from the value, with the same widest-safe rule used elsewhere:
        # an integral total reads as 0 dp, because `100`, `100.0` and `100.00`
        # are indistinguishable once parsed and only the first cannot be too
        # tight. That is deliberately conservative and it costs power -- a
        # column genuinely totalled `100.00` then gets a window 30x wider than
        # it needs. PASS `decimals_total` and none of this is a guess.
        dp_total = decimals_total
        if dp_total is None:
            dp_total = _rounding.decimals_of_value(expected_sum)
        if dp_total is None:
            dp_total = min(dp_each)
        window = (_rounding.accumulated_half_width(dp_each)
                  + _rounding.half_width(dp_total)
                  + _rounding.EPSILON)
        basis = "printed precision"

    is_consistent = abs(difference) <= window

    return {
        "values": values,
        "actual_sum": actual_sum,
        "expected_sum": expected_sum,
        "difference": difference,
        "tolerance": window,
        "tolerance_basis": basis,
        "is_consistent": is_consistent,
        "severity": CONSISTENT if is_consistent else SUSPICIOUS,
        "methodology": (
            f"Summation check: {description} sum to {actual_sum}, "
            f"expected {expected_sum}, difference = {difference}, "
            f"window = {window:.6g} ({basis}; {len(values)} addend(s) at "
            f"{dp_each} dp, total at {dp_total} dp)"
        ),
    }


def check_summation_batch(rows: list[dict], tolerance: float | None = None) -> dict:
    """Run every summation check in one call.

    MEASURED: on a real review, 55 of 124 stage-1 tool calls were
    `check_summation` invoked once per sum -- flow-diagram arms, table column
    totals, percentage columns. Each is a genuinely distinct check (unlike the
    per-cell storm `check_table` absorbs), but each also costs a turn, and turns
    are essentially the entire cost of a review.

    Each row is `{values, expected_sum, description?, tolerance?, decimals?,
    decimals_total?}`. Give `decimals` per row: the window a sum is allowed
    depends on how many addends there are and how precisely each was printed,
    so one window across a whole batch is wrong for most of it. A per-row
    explicit `tolerance` still wins where something other than rounding sets
    the window -- a count column that must hold exactly takes `tolerance=0`.

    The aggregate severity is the WORST row, and an all-indeterminate batch
    reports `indeterminate` rather than `consistent` -- the same false-clear
    that had to be fixed in the DEBIT batch, where reporting zero impossible
    rows out of zero evaluated rows looked like a clean bill of health.
    """
    from .severity import CONSISTENT, INDETERMINATE, SUSPICIOUS

    if not rows:
        return {
            "severity": INDETERMINATE, "applicable": False,
            "n_rows": 0, "n_evaluated": 0,
            "explanation": "No rows supplied; nothing was evaluated.",
        }

    results, n_bad, n_indet = [], 0, 0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            results.append({"row": i, "severity": INDETERMINATE,
                            "error": "row is not an object"})
            n_indet += 1
            continue
        try:
            out = check_summation(
                values=row.get("values") or [],
                expected_sum=row.get("expected_sum"),
                tolerance=row.get("tolerance", tolerance),
                description=row.get("description", "values"),
                decimals=row.get("decimals"),
                decimals_total=row.get("decimals_total"),
            ) if row.get("expected_sum") is not None else {
                "severity": INDETERMINATE, "error": "expected_sum missing"}
        except Exception as exc:  # noqa: BLE001
            # One poison cell -- a non-numeric extraction artefact ("N/A", a dash,
            # a footnote marker) in a row's `values` -- raises inside
            # check_summation. Without this it propagated out and crashed the
            # WHOLE batch, discarding every other row's valid summation check for
            # that turn. A poison row becomes `indeterminate`; the rest proceed.
            out = {"severity": INDETERMINATE,
                   "error": f"row could not be evaluated: {exc}"}
        out["row"] = i
        if row.get("description"):
            out["description"] = row["description"]
        sev = out.get("severity")
        if sev == INDETERMINATE:
            n_indet += 1
        elif sev != CONSISTENT:
            n_bad += 1
        results.append(out)

    n_evaluated = len(rows) - n_indet
    if n_evaluated == 0:
        severity, explanation = INDETERMINATE, (
            f"None of the {len(rows)} rows could be evaluated. This is a refusal, "
            "not a finding: nothing was checked, so nothing is confirmed.")
    elif n_bad:
        severity, explanation = SUSPICIOUS, (
            f"{n_bad} of {n_evaluated} evaluated sums do not reconcile.")
    else:
        severity, explanation = CONSISTENT, (
            f"All {n_evaluated} evaluated sums reconcile within tolerance"
            + (f"; {n_indet} row(s) could not be evaluated." if n_indet else "."))

    return {
        "severity": severity,
        "n_rows": len(rows),
        "n_evaluated": n_evaluated,
        "n_indeterminate": n_indet,
        "n_inconsistent": n_bad,
        "results": results,
        "explanation": explanation,
        "methodology": (
            "Batched summation. Each row is checked independently by "
            "check_summation; the aggregate severity is the worst row, and a "
            "batch in which nothing could be evaluated reports `indeterminate` "
            "rather than `consistent`."
        ),
    }
