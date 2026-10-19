"""Information-content scoring and severity ladders."""

from __future__ import annotations

import math
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from typing import Optional

from .constants import (
    _DERIVED_MIN_DECIMALS,
    _FRACTION_DENOMS,
    _LINE_HS,
    _LINE_IND,
    _LINE_S,
    _RATIONAL_MAX_DENOM,
    _TERMINATING_DENOMS,
    _VALUE_HS,
    _VALUE_IND,
    _VALUE_S,
    _YEAR_RANGE,
)
from .severity import (
    CONSISTENT,
    HIGHLY_SUSPICIOUS,
    INDETERMINATE,
    SUSPICIOUS,
)


def _canon(x: float) -> float:
    """Collapse binary float noise to the shortest equivalent decimal.

    0.1 + 0.2 arrives as 0.30000000000000004; two copy-pasted cells must
    compare EQUAL, and all matching downstream is exact equality — there is no
    tolerance matching anywhere in this module (a tolerance would manufacture
    matches between genuinely different measurements).
    """
    if x == int(x):
        return float(x)
    for k in range(0, 12):
        c = round(x, k)
        if abs(x - c) < 1e-12 * max(1.0, abs(x)):
            return c
    return x


def _sig_digits(x: float) -> int:
    """Significant decimal digits of x (sign, point, leading/trailing zeros
    stripped). `123.46` -> 5, `100` -> 1, `0.030` -> 1, `0` -> 0."""
    if x == 0:
        return 0
    s = repr(abs(_canon(x)))
    if "e" in s or "E" in s:  # scientific notation: mantissa digits only
        s = s.split("e")[0].split("E")[0]
    digits = s.replace(".", "").strip("0")
    return len(digits)


def _num_decimals(x: float) -> int:
    s = repr(abs(_canon(x)))
    if "e" in s or "E" in s:
        return 0
    return len(s.split(".")[1]) if "." in s else 0


@lru_cache(maxsize=65536)
def _derived_source_digits(x: float) -> Optional[int]:
    """If x is (within a printed-precision-scaled tolerance) a repeating
    fraction, a square root of a short decimal, or a natural log of a short
    decimal — or (at machine precision) an exact small-denominator rational —
    return the SOURCE value's digit count. Long decimals that are secretly
    13/3, sqrt(0.30) or 700/29 carry only their source's information.
    """
    nd = _num_decimals(x)
    if nd < _DERIVED_MIN_DECIMALS:
        return None
    v = abs(x)

    # Repeating fraction: v * d is (nearly) an integer for a small odd d.
    for d in _FRACTION_DENOMS:
        n = v * d
        if abs(n - round(n)) < 10.0 ** (-(nd - 2)) and round(n) != 0:
            return _sig_digits(round(n))
    # Square root of a <=2-decimal measurement.
    if v >= 0.1:
        sq = v * v
        if abs(sq - round(sq, 2)) < 1e-5 and round(sq, 2) != 0:
            return _sig_digits(round(sq, 2))
    # Natural log of a <=2-decimal value (only plausible for small logs).
    if v <= 12:
        try:
            e = math.exp(x)
        except OverflowError:  # pragma: no cover - bounded by v <= 12
            e = float("inf")
        if math.isfinite(e) and abs(e - round(e, 2)) < 1e-5 * max(1.0, e):
            if round(e, 2) != 0:
                return _sig_digits(round(e, 2))
    # Exact rational with a small denominator (k/29 as a percentage, a ratio
    # of two counts): matched at the float noise floor — far below any printed
    # precision — so only machine-computed rationals qualify. The numerator's
    # digits are the information; for a non-derived value the best q<=999
    # approximation has a numerator as long as the value itself, so this
    # branch never discounts honest measurements below their true content.
    frac = Fraction(v).limit_denominator(_RATIONAL_MAX_DENOM)
    if (
        frac.denominator >= 2
        and frac.numerator != 0
        and abs(v - frac.numerator / frac.denominator) <= 1e-11 * max(1.0, v)
    ):
        return _sig_digits(float(frac.numerator))
    return None


def _info_digits(x: float) -> int:
    """Information content of one value, in significant digits, after guards.

    Years -> 1 (a year is a label, not a measurement). Halves/quarters/eighths
    are re-expressed over their denominator when that shortens them by >= 2
    digits. Derived forms (fraction / sqrt / ln) are scored as their source.
    """
    if x == 0:
        return 0
    if float(x).is_integer() and _YEAR_RANGE[0] <= abs(x) <= _YEAR_RANGE[1]:
        return 1
    d = _sig_digits(x)
    derived = _derived_source_digits(x)
    if derived is not None and derived < d:
        d = derived
    for den in _TERMINATING_DENOMS:
        alt = _canon(x * den)
        if alt == int(alt):
            d_alt = _sig_digits(alt)
            if d_alt + 2 <= d:
                d = min(d, d_alt)
            break
    return d


def _size_norm(n_numeric_cells: int) -> float:
    """Multiple-comparisons normalization: expected coincidences grow with the
    number of numeric cells, roughly logarithmically. Floor of 3 so small
    sheets get no free severity."""
    return max(math.log10(max(n_numeric_cells, 1)), 3.0)


def _line_severity(adjusted: float) -> str:
    if adjusted >= _LINE_HS:
        return HIGHLY_SUSPICIOUS
    if adjusted >= _LINE_S:
        return SUSPICIOUS
    if adjusted >= _LINE_IND:
        return INDETERMINATE
    return CONSISTENT


def _value_severity(adjusted: float) -> str:
    if adjusted >= _VALUE_HS:
        return HIGHLY_SUSPICIOUS
    if adjusted >= _VALUE_S:
        return SUSPICIOUS
    if adjusted >= _VALUE_IND:
        return INDETERMINATE
    return CONSISTENT


def _regularity(values: list[float]) -> float:
    """Fraction of consecutive differences sharing the most common value.
    An arithmetic or constant run scores ~1 and is discounted to nothing;
    genuinely irregular measurements score ~0."""
    if len(values) < 2:
        return 0.0
    diffs = [_canon(b - a) for a, b in zip(values, values[1:])]
    if len(set(values)) == 1:
        return (len(values) - 1) / len(values)
    top_n = Counter(diffs).most_common(1)[0][1]
    return (top_n - 1) / len(diffs) if len(diffs) > 1 else 0.0
