"""A statistic outside its logically necessary range indicts US first.

GREG, 2026-08-11, on a real archived finding that reported "a correlation
coefficient of 11.3":

    "such a finding should trigger an automatic review of the PDF to make sure
     there wasn't an extraction error like misreading 0.113 for 11.3, or
     mistakenly extracting a mean instead of an r value. Gross mistakes like
     that are uncommon even in the most fraudulent papers."

That is a statement about PRIORS and it inverts the obvious design. A
correlation of 11.3 is not a subtle inconsistency that rewards forensic
attention -- it is a number no author, honest or otherwise, would print and
leave in a manuscript through review. Fabricators produce plausible numbers;
that is the entire point of fabricating them. So when we hold a value that
cannot exist, the likeliest author of the error is the party that did the
reading, and the party that did the reading is us.

WHY THIS MATTERS MORE THAN IT LOOKS. An out-of-bounds value is the single most
tempting thing in this toolkit to escalate: it is unambiguous, it needs no
premises, and `impossible` is defensible on the arithmetic alone. It is also
therefore the shortest path to the worst output this toolkit can produce -- a
false accusation, sourced entirely from our own decimal-point slip, stated at
the top of the severity ladder. The cardinal rule is what makes the permissive
reading correct here, not politeness.

WHAT THIS MODULE DOES, THEREFORE:

  * It never returns `impossible` on the strength of the bound alone. The
    verdict is `indeterminate` with `failure_mode: extraction_suspect`, which
    is a visible refusal -- the tolerated outcome -- and not a finding.

  * It names the specific slips that would explain the value, computed rather
    than guessed: which power-of-ten rescaling lands back inside the bound, and
    whether the value looks like a different quantity entirely (a mean, a test
    statistic) read out of the wrong column.

  * It offers ONE escape, and it is evidential rather than discretionary. Pass
    `extraction_verified=True` -- meaning the printed value has been located in
    the paper's own text, by the quote machinery, in a context that names the
    measure -- and the bound becomes what it always was: a logical necessity,
    licensing `impossible`. Verification is the price of the accusation.

This is also the escape hatch the uncomputed-severity clamp needs. A hand-worked
"r = 11.3 is impossible" is clamped to `suspicious` because no tool computed it;
routed through here WITH the extraction verified, it is computed, and the cap
lifts on evidence rather than on assertion.
"""
from __future__ import annotations

from typing import Any

#: Bounds that are LOGICALLY NECESSARY -- true of the measure by definition, not
#: by convention and not by anything the paper chose. Only such bounds belong
#: here: a bound we merely expect is an assumption, and this repo caps verdicts
#: that rest on our assumptions (see `bound_source` in the GRIM family).
#:
#: `None` means unbounded on that side.
MEASURE_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    # Correlation-family: bounded by Cauchy-Schwarz.
    "correlation": (-1.0, 1.0),
    "pearson_r": (-1.0, 1.0),
    "spearman_rho": (-1.0, 1.0),
    "kendall_tau": (-1.0, 1.0),
    "phi": (-1.0, 1.0),
    "partial_r": (-1.0, 1.0),
    # Shares of a whole.
    "p_value": (0.0, 1.0),
    "proportion": (0.0, 1.0),
    "percentage": (0.0, 100.0),
    "r_squared": (0.0, 1.0),
    # ADJUSTED R-squared is a DIFFERENT MEASURE, not an impossible one. It
    # subtracts a penalty for parameters and is negative whenever the model
    # fits worse than the mean -- ordinary in small samples, and printed as-is
    # by every major package. Absent this row it aliased onto `r_squared` and
    # an honest -0.021 returned `impossible`.
    "adjusted_r_squared": (None, 1.0),
    "auc": (0.0, 1.0),
    # Agreement coefficients: -1 by definition at maximal disagreement.
    "kappa": (-1.0, 1.0),
    "icc": (-1.0, 1.0),
    # Cronbach's alpha can go arbitrarily negative; it cannot exceed 1.
    "cronbach_alpha": (None, 1.0),
    # Non-negative by construction.
    "variance": (0.0, None),
    "sd": (0.0, None),
    "se": (0.0, None),
    "count": (0.0, None),
    "n": (0.0, None),
    "chi_squared": (0.0, None),
    "f_statistic": (0.0, None),
}

#: MEASURES WHOSE ENGLISH LABEL IS ALSO USED FOR A LESS-BOUNDED QUANTITY, with
#: the direction in which the ambiguity lies.
#:
#: `extraction_verified` licenses `impossible`, and its explanation says "the
#: extraction was verified against the paper's own text, so this is not a
#: misreading on our side". That is true of the VALUE and says nothing about the
#: LABEL -- and the label is what supplies the bound. Where a label is genuinely
#: ambiguous, an honest paper is accused:
#:
#:   percentage  -35.2   an ordinary percent DECREASE from baseline
#:   percentage  248.0   an ordinary percent INCREASE
#:   r_squared   -0.021  an ordinary ADJUSTED R-squared (now its own measure)
#:
#: All three returned `impossible` before this. The direction matters: an R^2
#: ABOVE 1 is impossible for adjusted and unadjusted alike and keeps its
#: verdict; only the negative side is ambiguous. A percentage is ambiguous in
#: both directions, because a change can be either sign.
#:
#: This CAPS rather than refuses. A percentage of 150 is still reported, as
#: `suspicious`, naming the reading that would make it innocent -- which is
#: what the toolkit's cardinal rule asks for and what `check_count_percent`
#: already does for the same quantity.
_LABEL_AMBIGUOUS: dict[str, tuple[bool, bool, str]] = {
    # canonical: (below-min is ambiguous, above-max is ambiguous, the reading)
    "percentage": (True, True,
                   "a percent CHANGE, increase or decrease, which is not "
                   "bounded to 0-100 the way a share of a whole is"),
    "r_squared": (True, False,
                  "an ADJUSTED R-squared, which is negative whenever a model "
                  "fits worse than the mean -- ordinary in small samples"),
}

#: Aliases the model actually writes, mapped onto the canonical keys above.
_ALIASES = {
    "r": "correlation", "rho": "spearman_rho", "tau": "kendall_tau",
    "pearson": "pearson_r", "spearman": "spearman_rho", "kendall": "kendall_tau",
    "p": "p_value", "pval": "p_value", "prob": "p_value",
    "pct": "percentage", "percent": "percentage",
    "r2": "r_squared", "rsq": "r_squared", "r_sq": "r_squared",
    "adj_r2": "adjusted_r_squared", "adjusted_r2": "adjusted_r_squared",
    "adj_r_squared": "adjusted_r_squared", "r2_adj": "adjusted_r_squared",
    "alpha": "cronbach_alpha", "coefficient_alpha": "cronbach_alpha",
    "standard_deviation": "sd", "standard_error": "se",
    "chi2": "chi_squared", "chisq": "chi_squared", "f": "f_statistic",
    "sample_size": "n", "auroc": "auc", "c_statistic": "auc",
}


def canonical_measure(measure: Any) -> str:
    s = str(measure or "").strip().lower().replace(" ", "_").replace("-", "_")
    s = s.lstrip("_")
    if s in MEASURE_BOUNDS:
        return s
    return _ALIASES.get(s, s)


def _in_bounds(value: float, lo: float | None, hi: float | None) -> bool:
    if lo is not None and value < lo:
        return False
    return not (hi is not None and value > hi)


def rescalings_that_fit(value: float, lo: float | None,
                        hi: float | None) -> list[dict]:
    """Power-of-ten slips that would put the value back inside its bound.

    COMPUTED, NOT GUESSED. A decimal point read one place wrong is the single
    commonest extraction error on a PDF, and it is worth naming the exact
    alternative reading rather than saying "check the extraction" -- a reader
    handed `0.113` can confirm or refute it in one glance at the page, and a
    reader handed a generic warning cannot.
    """
    out: list[dict] = []
    for power in (1, 2, 3, 4):
        for factor, how in ((10.0 ** -power, "right"), (10.0 ** power, "left")):
            candidate = value * factor
            if _in_bounds(candidate, lo, hi):
                out.append({
                    "reading": round(candidate, 10),
                    "places": power,
                    "slip": (f"decimal point {power} place"
                             f"{'' if power == 1 else 's'} too far {how}"),
                })
    # FEWEST PLACES FIRST, which is likeliest -- not nearest-to-zero. Sorting by
    # magnitude buried the one reading that matters: for r = 11.3 it put
    # 0.00113 ahead of 0.113, and 0.113 is the reading Greg named on sight.
    return sorted(out, key=lambda d: d["places"])[:3]


def check_statistic_bounds(
    value: float,
    measure: str,
    extraction_verified: bool = False,
    source_quote: str | None = None,
) -> dict:
    """Is this value inside the range its measure logically permits?

    Returns `consistent` when it is. When it is NOT, returns a REFUSAL rather
    than an accusation -- see the module docstring for why -- unless the
    extraction has been verified against the paper's own text, in which case the
    logical necessity licenses `impossible`.
    """
    canon = canonical_measure(measure)
    if canon not in MEASURE_BOUNDS:
        return {
            "severity": "indeterminate",
            "applicable": False,
            "measure": measure,
            "canonical_measure": canon,
            "error": f"No logically necessary bound is defined for {measure!r}.",
            "explanation": (
                "This check only knows bounds that follow from a measure's "
                "definition. An expectation about a plausible range is an "
                "assumption, not a necessity, and this tool will not accuse a "
                "paper of violating our expectations. Not a statement about "
                "the paper."
            ),
            "methodology": "Logical-bounds lookup; unknown measure.",
        }

    try:
        v = float(value)
    except (TypeError, ValueError):
        return {"severity": "indeterminate", "applicable": False,
                "error": f"value must be numeric (got {value!r})",
                "explanation": "Not a statement about the paper."}
    if v != v or v in (float("inf"), float("-inf")):
        return {"severity": "indeterminate", "applicable": False,
                "error": "value is not finite",
                "explanation": "Not a statement about the paper."}

    lo, hi = MEASURE_BOUNDS[canon]
    span = (f"[{'-inf' if lo is None else lo}, {'inf' if hi is None else hi}]")
    base = {
        "measure": measure,
        "canonical_measure": canon,
        "value": v,
        "bound": {"low": lo, "high": hi},
        "applicable": True,
        "methodology": (
            f"A {canon.replace('_', ' ')} lies in {span} by definition. "
            "The bound is logically necessary, not a convention and not an "
            "assumption of this review."
        ),
    }

    if _in_bounds(v, lo, hi):
        return {**base, "consistent": True, "severity": "consistent",
                "failure_mode": None,
                "explanation": f"{v} lies within {span}, as it must."}

    fits = rescalings_that_fit(v, lo, hi)

    _amb = _LABEL_AMBIGUOUS.get(canon)
    if _amb and extraction_verified:
        below_amb, above_amb, reading = _amb
        out_below = lo is not None and v < lo
        out_above = hi is not None and v > hi
        if (out_below and below_amb) or (out_above and above_amb):
            return {
                **base,
                "consistent": False,
                "severity": "suspicious",
                "failure_mode": "outside_logical_bound_or_mislabelled",
                "extraction_verified": True,
                "source_quote": source_quote,
                "label_is_ambiguous": True,
                "innocent_reading": reading,
                "explanation": (
                    f"{v} lies outside {span}, which a "
                    f"{canon.replace('_', ' ')} cannot do -- but the bound "
                    f"comes from the LABEL, and `extraction_verified` confirms "
                    f"we read the VALUE correctly, not that the label names "
                    f"what we assumed. This label is also used for {reading}. "
                    f"Reported, not alleged: confirm which quantity this is "
                    f"before treating it as a finding."),
                "rescalings_that_would_fit": fits,
            }

    if extraction_verified:
        return {
            **base,
            "consistent": False,
            "severity": "impossible",
            "failure_mode": "outside_logical_bound",
            "extraction_verified": True,
            "source_quote": source_quote,
            "explanation": (
                f"{v} lies outside {span}, which a {canon.replace('_', ' ')} "
                "cannot do. The extraction was verified against the paper's own "
                "text, so this is not a misreading on our side: the value as "
                "printed cannot be what the label says it is. The likeliest "
                "innocent explanations are a typesetting error or a mislabelled "
                "row -- both worth asking the authors about, and neither "
                "something this review can settle."
            ),
            "rescalings_that_would_fit": fits,
        }

    return {
        **base,
        "consistent": False,
        "severity": "indeterminate",
        "failure_mode": "extraction_suspect",
        "extraction_verified": False,
        "explanation": (
            f"{v} lies outside {span}, which a {canon.replace('_', ' ')} cannot "
            "do -- and that is the reason to doubt OUR reading before doubting "
            "the paper. A value this far outside its definition is not the kind "
            "of error that survives to publication, in an honest paper or a "
            "fabricated one: fabricators produce plausible numbers. The "
            "likeliest author of this error is whoever read the page, which was "
            "us. Re-read the value in the source before treating it as a "
            "finding; if it is confirmed there, call this again with "
            "extraction_verified=true and it will be reported as impossible."
        ),
        "verify_first": [
            "Locate the value in the paper itself, not in our extraction.",
            "Check the decimal point against the printed figure.",
            "Check the column: a mean, a test statistic or a percentage read "
            "out of the wrong column is the other common source of this.",
            "Check whether the row label names the measure this value was "
            "filed under.",
        ],
        "rescalings_that_would_fit": fits,
        "not_evidence": (
            "This is NOT a finding and must not be reported as one. It is a "
            "flag on our own extraction."
        ),
    }
