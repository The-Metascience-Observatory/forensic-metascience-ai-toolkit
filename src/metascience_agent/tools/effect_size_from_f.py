"""Reconcile a printed effect size against the F (or t) statistic beside it.

WHY THIS EXISTS
---------------
Nothing in the registry converted an F and its degrees of freedom into an
effect size, and partial eta-squared is in almost every psychology ANOVA. Both
halves of that gap showed up in one 9-paper batch (MEASURED 2026-08-22):

  * `10.1007--s10803-013-1829-4` prints "F(2, 54) = 51.81, p < .001,
    eta_p^2 = .83". Partial eta-squared is (F*df1)/(F*df1 + df2) =
    103.62/157.62 = .657, not .83. The finding was filed under technique
    `no_tool_exists` -- the schema's own name for "arithmetic, but nothing in
    the registry covers it", which caps it at `suspicious` and records the gap.
  * `10.1177--0956797615569889` checked four eta-squared values by hand through
    `check_ratio`, using F/(F + df2). That is right there and wrong in general:
    it is the df1 = 1 special case of the formula above. Nothing enforced the
    precondition; the model happened to remember it.

WHAT IT DOES NOT DO
-------------------
It does not decide WHICH effect size the authors reported. Partial eta-squared,
eta-squared and omega-squared are different quantities computed from different
sums of squares, and only partial eta-squared is recoverable from F and df
alone -- the other two need the total sum of squares, which papers almost never
print. So `measure` is REQUIRED and the two unrecoverable ones are refused by
name rather than silently scored against the partial formula. Doing otherwise
would flag every honest paper that reports generalised eta-squared.

FALSE-POSITIVE DISCIPLINE
-------------------------
The rules the rest of the kit already follows:

* **Both numbers are ROUNDED, so the comparison is interval-to-interval.**
  `F = 51.81` asserts F in [51.805, 51.815) and `.83` asserts [.825, .835).
  A flag requires the achievable interval and the reported interval to be
  DISJOINT. Comparing points convicts honest rounding.
* **Capped at `suspicious`.** A mismatch has ordinary explanations this
  arithmetic cannot rule out: a different effect-size family than the label
  suggests, a value carried over from another model, a Greenhouse-Geisser
  correction applied to the df but not the F. `impossible` is for a violation
  of arithmetic, and "the authors reported a different quantity than their
  label says" is not one.
* **Refuses without df1.** The most common misuse is assuming df1 = 1, which
  turns the formula into `F/(F + df2)` and makes every multi-level factor look
  wrong.
"""
from __future__ import annotations

from . import rounding as _rounding
from .severity import (CONSISTENT, INDETERMINATE, SUSPICIOUS,
                       refuse_if_nonfinite)

#: Effect sizes recoverable from F and df alone. Everything else needs a sum of
#: squares the paper did not print.
_RECOVERABLE = {
    "partial_eta_squared": "partial_eta_squared",
    "partial eta squared": "partial_eta_squared",
    "eta_p2": "partial_eta_squared",
    "etap2": "partial_eta_squared",
    "np2": "partial_eta_squared",
    "cohens_f": "cohens_f",
    "cohen's f": "cohens_f",
    "cohens f": "cohens_f",
}

#: Named and refused rather than scored against the partial formula. Each is a
#: real quantity a paper may legitimately report; none follows from F and df.
_NOT_RECOVERABLE = {
    "eta_squared": "eta-squared uses the TOTAL sum of squares, not the error "
                   "term, so it cannot be recovered from F and df alone",
    "eta squared": "eta-squared uses the TOTAL sum of squares, not the error "
                   "term, so it cannot be recovered from F and df alone",
    "generalized_eta_squared": "generalised eta-squared depends on which "
                               "factors are treated as measured vs "
                               "manipulated, which F and df do not carry",
    "omega_squared": "omega-squared subtracts an estimate of error variance "
                     "that needs the total sum of squares",
    "r_squared": "R-squared for a model is SS_model/SS_total, and the total "
                 "sum of squares is not recoverable from an F and its df -- "
                 "what the partial formula gives back is the PARTIAL form",
}


def _canonical_measure(measure: str | None) -> tuple[str | None, str | None]:
    """(canonical name, refusal reason). Exactly one is non-None."""
    key = str(measure or "").strip().lower().replace("-", "_")
    key_spaced = key.replace("_", " ")
    if key in _RECOVERABLE or key_spaced in _RECOVERABLE:
        return _RECOVERABLE.get(key) or _RECOVERABLE[key_spaced], None
    if key in _NOT_RECOVERABLE or key_spaced in _NOT_RECOVERABLE:
        return None, _NOT_RECOVERABLE.get(key) or _NOT_RECOVERABLE[key_spaced]
    return None, (
        f"unrecognised effect-size measure {measure!r}. Recoverable from F and "
        f"df: {', '.join(sorted(set(_RECOVERABLE.values())))}. Anything else "
        "needs a sum of squares the paper did not print."
    )


def _partial_eta_squared(f_value: float, df1: int, df2: int) -> float:
    return (f_value * df1) / (f_value * df1 + df2)


def effect_size_from_f(
    f_value: float,
    df1: int,
    df2: int,
    reported_effect_size: float | None = None,
    measure: str = "partial_eta_squared",
    decimals_f: int | None = None,
    decimals_effect_size: int | None = None,
    source_quote: str | None = None,
    source_locator: str | None = None,
) -> dict:
    """Recompute an effect size from a printed F and compare it to the paper's.

    Args:
        f_value: The printed F.
        df1: Numerator degrees of freedom. REQUIRED -- assuming 1 collapses the
            formula to `F/(F + df2)` and makes every multi-level factor look
            wrong.
        df2: Denominator (error) degrees of freedom.
        reported_effect_size: The value the paper printed. Without it this only
            computes, and returns `indeterminate`.
        measure: What the paper called it. `partial_eta_squared` or `cohens_f`
            are recoverable; `eta_squared`, `generalized_eta_squared`,
            `omega_squared` and model `r_squared` are REFUSED by name.
        decimals_f: Printed decimals of `f_value`; inferred from the value when
            absent.
        decimals_effect_size: Printed decimals of `reported_effect_size`;
            inferred when absent.
        source_quote / source_locator: provenance, carried through unchanged.

    Returns a dict with `severity` (never above `suspicious`) and the interval
    arithmetic behind it.
    """
    out: dict = {
        "tool": "effect_size_from_f",
        "f_value": f_value, "df1": df1, "df2": df2,
        "measure": measure,
        "source_quote": source_quote,
        "source_locator": source_locator,
        "source_quote_supplied": source_quote is not None,
    }

    bad = refuse_if_nonfinite(f_value=f_value,
                              **({"reported_effect_size": reported_effect_size}
                                 if reported_effect_size is not None else {}))
    if bad is not None:
        return {**out, **bad, "applicable": False}

    canonical, refusal = _canonical_measure(measure)
    if canonical is None:
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": refusal,
                "explanation": (
                    f"Not evaluated: {refusal}. Reporting a mismatch here would "
                    "be scoring the paper against a formula for a quantity it "
                    "did not claim to report.")}
    out["canonical_measure"] = canonical

    for name, value in (("df1", df1), ("df2", df2)):
        if value is None or value < 1:
            return {**out, "severity": INDETERMINATE, "applicable": False,
                    "error": f"{name} must be a positive integer (got {value})",
                    "explanation": (
                        "Partial eta-squared needs BOTH degrees of freedom. "
                        "Assuming df1 = 1 collapses the formula to F/(F + df2), "
                        "which is the one-numerator-df special case and is wrong "
                        "for every multi-level factor.")}
    if f_value < 0:
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": f"F must be non-negative (got {f_value})"}

    # THE F IS ROUNDED, SO THE EFFECT SIZE IS AN INTERVAL. Partial eta-squared
    # is monotone increasing in F, so the endpoints map straight through.
    d_f = (decimals_f if decimals_f is not None
           else (_rounding.decimals_of_value(f_value) or 0))
    h_f = _rounding.half_width(d_f)
    f_lo, f_hi = max(0.0, f_value - h_f), f_value + h_f

    pes_lo = _partial_eta_squared(f_lo, df1, df2)
    pes_hi = _partial_eta_squared(f_hi, df1, df2)
    point = _partial_eta_squared(f_value, df1, df2)

    if canonical == "cohens_f":
        # f = sqrt(pes / (1 - pes)), monotone in pes.
        def _to_cohens_f(v: float) -> float:
            return (v / (1 - v)) ** 0.5 if v < 1 else float("inf")
        lo, hi, point = (_to_cohens_f(pes_lo), _to_cohens_f(pes_hi),
                         _to_cohens_f(point))
    else:
        lo, hi = pes_lo, pes_hi

    out.update({
        "computed": point,
        "achievable_interval": [lo, hi],
        "formula": ("(F*df1)/(F*df1 + df2)" if canonical == "partial_eta_squared"
                    else "sqrt(pes/(1-pes)) with pes = (F*df1)/(F*df1 + df2)"),
        "f_rounding_half_width": h_f,
    })

    if reported_effect_size is None:
        return {**out, "severity": INDETERMINATE, "applicable": True,
                "consistent": None,
                "explanation": (
                    f"The printed F(({df1}, {df2})) = {f_value} implies "
                    f"{canonical} in [{lo:.4g}, {hi:.4g}]. No reported value was "
                    "supplied, so there is nothing to compare it against.")}

    d_e = (decimals_effect_size if decimals_effect_size is not None
           else (_rounding.decimals_of_value(reported_effect_size) or 0))
    h_e = _rounding.half_width(d_e)
    r_lo, r_hi = reported_effect_size - h_e, reported_effect_size + h_e
    out.update({"reported_effect_size": reported_effect_size,
                "reported_interval": [r_lo, r_hi],
                "effect_size_rounding_half_width": h_e})

    # INTERVAL AGAINST INTERVAL. Overlap anywhere is consistent; comparing the
    # two POINTS would convict honest rounding at either end.
    overlap = (r_lo <= hi + _rounding.EPSILON
               and r_hi >= lo - _rounding.EPSILON)
    if overlap:
        return {**out, "severity": CONSISTENT, "consistent": True,
                "applicable": True,
                "explanation": (
                    f"F({df1}, {df2}) = {f_value} implies {canonical} in "
                    f"[{lo:.4g}, {hi:.4g}], which meets the reported "
                    f"{reported_effect_size} at its printed precision.")}

    # CAPPED AT SUSPICIOUS. A label naming a different effect-size family, a
    # value carried over from another model, or a Greenhouse-Geisser correction
    # applied to the df but not the F all produce this and are not arithmetic
    # violations.
    return {**out, "severity": SUSPICIOUS, "consistent": False,
            "applicable": True,
            "explanation": (
                f"F({df1}, {df2}) = {f_value} implies {canonical} in "
                f"[{lo:.4g}, {hi:.4g}], and the paper reports "
                f"{reported_effect_size} (interval [{r_lo:.4g}, {r_hi:.4g}]). "
                "The two do not meet."),
            "alternative_reading": (
                "The paper may be reporting a different effect-size family than "
                "the label suggests (eta-squared and generalised eta-squared are "
                "both smaller than partial eta-squared for the same model), or a "
                "value from a model other than the one this F came from, or an "
                "F corrected for sphericity against uncorrected df. Check what "
                "the Methods say the measure is before treating this as an "
                "error.")}
