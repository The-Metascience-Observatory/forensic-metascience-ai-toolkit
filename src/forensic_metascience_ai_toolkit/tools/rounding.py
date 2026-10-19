"""Rounding intervals, in one place.

WHY THIS EXISTS
---------------
A number in a paper is not a number. `71.0` is a claim about an interval --
the true value lies in [70.95, 71.05) -- and every check that compares a
recomputed quantity against a reported one is really asking whether the two
intervals overlap. Get the interval wrong and the check is wrong in a
direction that matters: too tight manufactures impossibilities out of
correctly-reported data, too loose clears results that are genuinely wrong.

Nine separate half-width helpers had accumulated across the tools, each
correct in isolation, none of them checkable against the others. This module
is the single definition. The individual helpers remain as thin wrappers so
no call site had to change.

THE ONE RULE THAT KEEPS BEING BROKEN
------------------------------------
**Printed precision comes from the LITERAL, never from the parsed float.**
`str(71.0)` is `"71.0"`, so a value printed `71` reads as one decimal place
and its interval shrinks tenfold. `str(0.05)` for a p printed `.05000` reads
as two. Use `decimals_of_text` on the source string, and pass `None` rather
than a default when the source string is not available -- "unknown precision"
and "printed to zero decimals" are entirely different claims, and only one of
them licenses a verdict.

`tests/test_printed_precision.py` exists to prevent this specific regression.
"""

from __future__ import annotations

import math
from decimal import Decimal

# Recomputed quantities carry floating-point noise well below any printed
# precision. Without a tolerance a value sitting exactly on an interval
# boundary flips on the last bit of a division.
EPSILON = 1e-12
_EPSILON = EPSILON  # historical name, kept for the wrappers below


#: The reporting conventions this module knows how to build a window for.
#: `round_half` is the default assumption everywhere in the toolkit; a paper
#: that TRUNCATES is equally ordinary (SPSS's default, several journals', and one
#: of `scrutiny::grim`'s options) and produces a DIFFERENT window, not a wider
#: one. Nothing here decides which a paper used -- see `windows`.
CONVENTIONS = ("round_half", "truncation")


def window(value: float, decimals: int,
           convention: str = "round_half") -> tuple[float, float]:
    """The half-open interval of true values that print as `value` at `decimals`.

    THE POINT OF THIS FUNCTION IS THAT THE TWO WINDOWS ARE DIFFERENT AND
    NEITHER CONTAINS THE OTHER, which is why assuming a convention can convict
    an honest paper:

        2.38 at 2 dp, round_half  -> [2.375, 2.385)
        2.38 at 2 dp, truncation  -> [2.380, 2.390)

    They OVERLAP on [2.380, 2.385) -- they are not disjoint, and a first draft of
    this docstring said they were. What matters is the half each does not share:
    round_half admits [2.375, 2.380) which truncation forbids, and truncation
    admits [2.385, 2.390) which round_half forbids. A value in either exclusive
    half is provably impossible under the other convention and perfectly
    ordinary under its own. A reporter that truncates uniformly prints
    2.38 for a true 2.3850589, and a checker that only knows the round-half
    window proves that value impossible. That is not hypothetical: it is a live
    accusation in this repo's own archive against an honest paper
    (n=30, S=529, sum-of-squares 9493, printed "17.63 +/- 2.38").

    Both intervals are returned half-open [lo, hi). For round_half that is the
    conventional round-half-up rule; for truncation it is exact, since a
    truncating reporter prints floor(v*10^d)/10^d.
    """
    if decimals is None:
        raise TypeError(
            "printed decimals is None: there is no window without a precision. "
            "Read it off the literal; do not substitute a default.")
    step = 10.0 ** (-int(decimals))
    if convention == "truncation":
        return (float(value), float(value) + step)
    if convention != "round_half":
        raise ValueError(f"unknown rounding convention {convention!r}; "
                         f"expected one of {CONVENTIONS}")
    return (float(value) - step / 2, float(value) + step / 2)


def windows(value: float, decimals: int) -> dict[str, tuple[float, float]]:
    """Every convention's window for one printed literal, keyed by convention.

    For a caller that must ask "could ANY ordinary reporting convention have
    produced this?" -- which is the only honest question when the paper does not
    say which it used. A value admissible under any convention the paper could
    plausibly have used is NOT evidence against the paper.

    The caller still owes two things this function will not do for it:
    de-escalate rather than clear (a convention that explains the number is not
    a clean bill of health), and check that the rescue is not an OFF SWITCH --
    a rescue that rescues everything is not a judgement. See
    `grim.discriminating_power`, and Greg's rule of 2026-08-11.
    """
    return {c: window(value, decimals, c) for c in CONVENTIONS}


def half_width(decimals: int) -> float:
    """Half-width of the interval that rounds to a value printed to `decimals` dp.

    A true value `v` printed as `r` to `decimals` decimals satisfies
    `r - 0.5*10**-decimals <= v < r + 0.5*10**-decimals`.
    """
    return 0.5 * (10 ** (-decimals))


def tolerance(decimals: int) -> float:
    """`half_width` plus the floating-point slack, for direct `abs(a - b) <= tol` tests.

    Use this rather than writing `0.5 * 10 ** -d + 1e-12` at the call site;
    that expression appeared in six places and drifted in two of them.
    """
    return half_width(decimals) + EPSILON


def interval(value: float, decimals: int) -> tuple[float, float]:
    """The closed-open interval `[lo, hi)` a printed value asserts.

    Returned as a plain pair rather than a range object because callers do
    arithmetic on the bounds -- accumulating them across a column, widening
    them through a transformation -- more often than they test membership.
    """
    h = half_width(decimals)
    return (value - h, value + h)


def matches_at_precision(computed: float | None, reported: float | None,
                         decimals: int) -> bool:
    """Is `computed` consistent with `reported` at the precision it was printed to?

    False when either side is missing: an absent value is not a match, and
    silently treating it as one is how a check reports `consistent` on data it
    never saw.
    """
    if computed is None or reported is None:
        return False
    # `bool(...)`, not the bare comparison: scipy hands back numpy scalars, and
    # a `numpy.bool_` leaking into a finding is both an `is True` trap and a
    # JSON-serialisation failure at the MCP boundary.
    return bool(abs(computed - reported) <= half_width(decimals) + _EPSILON)


def decimals_of_text(text: str | None) -> int | None:
    """Decimal places as PRINTED in the source text.

    `"71"` -> 0, `"71.0"` -> 1, `"1,234.56"` -> 2. Returns `None` when the text
    is not a parseable number, so callers can distinguish "printed to zero
    decimals" from "unknown" -- the first licenses a granularity verdict, the
    second forbids one.

    Two families of text that `float()` accepts are REFUSED, because counting
    characters after the dot misreads both, and one misreading accuses:

    * **Scientific notation.** `"2.5e3"` counted 3 "decimals" -- an interval of
      +/-0.0005 for a value whose true printed half-width is 50, five orders of
      magnitude too tight, so a computed 2480 was reported inconsistent with a
      printed 2.5e3 (verified by execution). The mantissa's decimals are not
      the value's decimals; without knowing which form the paper printed, the
      precision is unknown, and unknown forbids a verdict.
    * **Non-finite text.** `float("nan")` parses, so `"nan"` returned 0 --
      "printed to zero decimals", which licenses a granularity verdict on a
      value that is not a number.
    """
    if text is None:
        return None
    s = str(text).replace(",", "").strip()
    try:
        f = float(s)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    if "e" in s.lower():
        return None
    _, _, frac = s.partition(".")
    return len(frac.rstrip())


def quotient_interval(num: float, num_decimals: int,
                      den: float, den_decimals: int) -> tuple[float, float] | None:
    """The interval a QUOTIENT of two printed values can occupy.

    `t = B/SE` is the commonest recomputation in the toolkit and its slack is
    not a constant: it depends on both printed precisions AND on the magnitude
    of the denominator. B = 2.0, SE = 0.5 gives t within about +/-0.5; the same
    precisions with SE = 0.05 give t within about +/-11. A fixed tolerance of
    0.1 -- what `check_regression` used -- is far too tight in the second case
    and needlessly loose in the first.

    Computed at the four corners of the rectangle rather than by propagating
    derivatives, because the function is not monotone across a sign change and
    the corner evaluation is exact where a first-order approximation is not.

    Returns None when the denominator's interval straddles zero: the quotient
    is then unbounded and no comparison is meaningful. That is a refusal, not
    a pass -- callers must report `indeterminate`.
    """
    hn, hd = half_width(num_decimals), half_width(den_decimals)
    d_lo, d_hi = den - hd, den + hd
    if d_lo <= 0 <= d_hi:
        return None
    values = [(num + sn * hn) / d
              for sn in (-1, 1)
              for d in (d_lo, d_hi)]
    return (min(values), max(values))


def coarsest_decimals(*texts: str | None) -> int | None:
    """The fewest decimals among several printed values, or `None` if any is unknown.

    The binding constraint on a comparison involving several reported numbers
    is the coarsest of them: an estimate printed to 2 dp compared against a
    bound printed to 1 dp is only known to 1 dp. `None` propagates rather than
    being skipped, because a single unknown makes the whole comparison's
    precision unknown.
    """
    if not texts:
        return None
    seen = [decimals_of_text(t) for t in texts]
    if any(d is None for d in seen):
        return None
    return min(seen)  # type: ignore[type-var]


def decimals_of_value(value: float | int | None) -> int | None:
    """FALLBACK precision for a value whose source literal is gone.

    Use `decimals_of_text` wherever the literal survives. This exists for the
    call sites that receive a parsed float and nothing else, and it errs
    deliberately towards the WIDER interval:

    * An integral value returns 0, not the 1 that `repr(2.0)` implies. `2`,
      `2.0` and `2.00` are indistinguishable once parsed, and 0 dp is the only
      one of the three that cannot be too tight. Too tight manufactures
      impossibilities; too loose only misses things, and a missed finding is
      recoverable while a false accusation is not.
    * Otherwise it reads `repr` after stripping floating-point noise, which
      also drops trailing zeros -- so `1.40` reads as 1 dp. That is again the
      wider interval, and again the safe direction.

    The noise-stripping is load-bearing, not tidiness. `repr(0.1 + 0.2)` is
    `'0.30000000000000004'`, which reads as SEVENTEEN decimals and an interval
    fourteen orders of magnitude too narrow -- the direction that manufactures
    accusations, and reachable from any value a caller computed rather than
    parsed. `0.3` and `0.1 + 0.2` gave opposite verdicts on the same
    coefficient before this. `%.12g` keeps every digit a paper could plausibly
    have printed and discards the rest.

    Returns None for a value that is not a finite number. Callers must treat
    that as "no verdict", not as zero decimals.

    A float small enough that its repr is E-NOTATION (below 1e-4) cannot go
    through `decimals_of_text`, which refuses e-notation as unknowable printed
    precision. Here the literal never existed, so the DECIMAL-EQUIVALENT
    precision is derived from the exponent instead: 1.5e-05 is `0.000015`, six
    decimals, half-width 5e-7 -- the interval either plausible printed form
    (`0.000015` or `1.5x10^-5`) asserts. Returning None instead would crash the
    call sites that wrap this in `half_width` with a parsed p-value.
    """
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    if f.is_integer():
        return 0
    s = f"{f:.12g}"
    if "e" in s.lower():
        return max(-Decimal(s).as_tuple().exponent, 0)
    return decimals_of_text(repr(float(s)))


def accumulated_half_width(decimals_each: list[int]) -> float:
    """Half-width of a SUM of independently-rounded values.

    Each addend contributes its own half-width, so a column of twenty values
    printed to one decimal permits the total to be off by +/-1.0 -- not the
    +/-0.05 of a single cell, and not a fixed tolerance chosen in advance.
    Both errors were live: a constant tolerance of 0.5 is simultaneously ten
    times too loose for a two-value 2 dp sum and half as loose as it must be
    for that twenty-value column.

    This is the WORST case (every value rounding the same way), which is the
    right bound for a forensic check: a total inside it is not evidence of
    anything.
    """
    return sum(half_width(d) for d in decimals_each)
