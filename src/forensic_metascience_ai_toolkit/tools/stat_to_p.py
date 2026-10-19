"""Recompute a p-value from ONE printed test statistic, in any format.

WHY THIS EXISTS
---------------
statcheck verifies t, F, r, chi-squared and z -- but only as a TEXT SCANNER over
APA-formatted prose. Hand it a statistic and its df as VALUES and there was
nowhere to put them: `recalc_f_to_p` was the only value-level sibling in the
kit, so F could be checked and the other four could not.

MEASURED, from the reviews' own words:

  "No tool in this kit converts a chi-squared statistic plus df to a p-value...
   would require dividing the chi-squared by its df by hand."
      -- 10.3389/fnins.2023.1186751, where the missing conversion DOWNGRADED the
         headline finding from `impossible` to `highly_suspicious`

Three archived papers hit this: a chi-squared with df, an r-squared with n, and
a Pearson r with n. In each the model correctly refused to do the arithmetic
itself -- that is the rule -- and there was no tool to hand it to.

This is also what makes the statcheck limitation a matter of FORMAT rather than
of capability. Upstream statcheck needs `t(28) = 2.10, p = .04` written in APA
grammar; a statistic sitting in a table cell, or in prose the regex does not
match, is invisible to it. The values are the same values. Now they have a home.

WHAT IT CANNOT DO, and why that is a fact about the paper
--------------------------------------------------------
A chi-squared with no degrees of freedom cannot be converted to ONE p-value by
any implementation, and neither can a correlation with no n. Where the paper
does not print the ingredient, this NAMES the missing one -- a property of the
publication, not a limit of this kit, and it belongs in a review as such.

AN UNPRINTED df CAN STILL BE BOUNDED, for t and chi-squared (since 1.88.0).
For a fixed |t| the p FALLS as df grows (largest at the smallest admissible
df, smallest at df -> infinity, the normal); for a fixed chi-squared the p
RISES with df (smallest at df = 1). Both verified on a dense grid before this
was written, at every statistic from 1e-4 to 40 and every df from 1 to 1e7. So
the printed statistic supports a p INTERVAL over every admissible df, and a
reported p outside it is wrong for EVERY df -- a check that needs no df at all.
MEASURED 2026-10-18 on the statcheck_pvalue_errors working set: two of the
tools agent's five misses were this shape and the tool refused both
(Wansink 2012 `chi2 = 2.355; P = .06`, Etindele Sosso 2020
`t = 9.748, p = .523`). The caller may narrow the range with `df_min`/`df_max`
when the paper states something that bounds it; the result then says whether
the verdict needed those bounds. F has no such bound -- its p is not monotone in
df1 or df2 at every statistic -- so an F without both df still refuses.

FALSE-POSITIVE DISCIPLINE
-------------------------
The same two rules `recalc_f_to_p` already follows, for the same reasons:

* **The statistic is ROUNDED, so it implies a p RANGE.** `chi2 = 4.1` asserts
  chi2 in [4.05, 4.15), and p is monotone in the statistic, so the reported p is
  matched against the whole achievable interval. Comparing it to the point p of
  the printed statistic convicts honestly rounded reports.
* **DIRECTIONAL FOR A BOUND, TWO-SIDED FOR AN EXACT p.** An OVER-claim -- a
  reported p BELOW what the printed statistic can support -- is flagged under
  every relation. An UNDER-claim (reported p above everything the statistic
  allows) is a TRUE statement when the paper printed a bound (`p < .05`), so it
  is flagged only when the p was printed EXACT (`p_relation='='`, or a value
  that is no conventional bound, `ttest.resolve_p_relation`) or as `p > x`.
  Until 1.86.0 it was tolerated outright, and `t(38) = 3.94, p = .696` -- a
  documented decision error, true p .00034 -- came back `consistent`. An
  under-claim is capped at `suspicious` (`ttest.UNDER_CLAIM_SEVERITY`).
"""
from __future__ import annotations

import math

from scipy import stats

from . import rounding as _rounding
from ..survey_design import survey_refusal
from .severity import (CONSISTENT, INDETERMINATE, SUSPICIOUS,
                       refuse_if_nonfinite)
from .ttest import (ONE_TAILED_UNSTATED_NOTE, bound_is_stated, check_p_adjustment,
                    explain_under_claim, p_under_claimed, resolve_p_relation,
                    under_claim_finding, under_claim_note)

#: Nothing here reaches `impossible`. A p-value recomputed from a rounded
#: statistic is an interval, and a disagreement has ordinary explanations --
#: a one-tailed test, a correction, a different df convention -- that the
#: printed numbers alone cannot rule out.
CEILING = SUSPICIOUS

#: Which extra input each statistic needs before it means anything.
NEEDS = {
    "t": ("df",),
    "chi2": ("df",),
    "z": (),
    "r": ("n",),
    "f": ("df", "df2"),
}

_ALIASES = {
    "chi_squared": "chi2", "chisq": "chi2", "x2": "chi2", "χ2": "chi2",
    "pearson_r": "r", "correlation": "r",
    "t_value": "t", "t_statistic": "t", "z_value": "z", "z_statistic": "z",
    "f_value": "f", "f_statistic": "f",
}

#: Statistics whose p-value is a ONE-SIDED upper tail by construction. A
#: two-tailed reading of a chi-squared or an F is a category error, not an
#: option, so `tails` is ignored for them and the result says so.
_UPPER_TAIL_ONLY = {"chi2", "f"}

#: Statistics whose p is MONOTONE in the df at every fixed statistic, so an
#: unprinted df is bounded rather than refused: -1 = p falls as df grows (t),
#: +1 = p rises (chi2). F is deliberately absent: at df1 = 10, F = 0.7 the p
#: falls from .740 (df2 = 1) to .705 (df2 = 5) and climbs back to .725, so its
#: extremes are not at the ends of a df range and an end-point bound is false.
_DF_MONOTONE = {"t": -1, "chi2": +1}

#: The smallest df a t or chi-squared can have. A Welch df is at least
#: min(n1, n2) - 1, which is 1 for any two groups of two.
_DF_FLOOR = 1.0


def _norm_kind(kind: str) -> str:
    k = str(kind or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(k, k)


def _p_from(kind: str, stat: float, df, df2, n, tails: int) -> float | None:
    """The upper-tail (or two-tailed) p for one statistic value."""
    s = abs(stat) if kind in ("t", "z", "r") else stat
    if kind == "t":
        # df = infinity is the limit the df-free bound uses: the normal.
        p = float(stats.norm.sf(s) if math.isinf(df) else stats.t.sf(s, df))
    elif kind == "z":
        p = float(stats.norm.sf(s))
    elif kind == "chi2":
        if math.isinf(df):
            return 1.0
        return float(stats.chi2.sf(max(0.0, stat), df))
    elif kind == "f":
        return float(stats.f.sf(max(0.0, stat), df, df2))
    elif kind == "r":
        if s >= 1.0:
            return None
        t = s * math.sqrt((n - 2) / (1 - s * s))
        p = float(stats.t.sf(t, n - 2))
    else:
        return None
    return p * 2 if tails == 2 else p


def _df_range(d):
    """(low, high) a printed FRACTIONAL df's rounding allows, or None for an
    integer (or absent) df, which is exact."""
    if d is None:
        return None
    try:
        v = float(d)
    except (TypeError, ValueError):
        return None
    if v.is_integer():
        return None
    dec = _rounding.decimals_of_value(v) or 1
    h = _rounding.half_width(dec)
    return (max(v - h, 1e-9), v + h)


def recalc_stat_to_p(
    statistic: float,
    kind: str,
    df: int | None = None,
    df2: int | None = None,
    n: int | None = None,
    reported_p: float | None = None,
    decimals_stat: int | None = None,
    decimals_p: int | None = None,
    tails: int | None = 2,
    p_relation: str | None = None,
    source_quote: str | None = None,
    source_locator: str | None = None,
    sampling: str = "simple_random",
    df_min: float | None = None,
    df_max: float | None = None,
    p_adjustment: str | None = None,
    one_tailed_stated: bool = False,
) -> dict:
    """Recompute p from a single printed statistic and compare it to the paper's.

    Args:
        statistic: The printed value.
        kind: One of `t`, `chi2`, `z`, `r`, `f` (aliases accepted).
        df: Degrees of freedom -- required for `t` and `chi2`, numerator df for `f`.
        df2: Denominator df, `f` only.
        n: Sample size, `r` only (df = n - 2).
        reported_p: The p the paper printed. Without it this only computes.
        decimals_stat: Printed decimals of `statistic`. The statistic is
            rounded, so it implies a p RANGE; inferred from the literal when
            absent, which errs wide.
        decimals_p: Printed decimals of `reported_p`.
        tails: 2 (default) or 1. Ignored for `chi2` and `f`, whose p is an
            upper tail by construction.
        p_relation: What the paper printed between "p" and the number: '='
            (exact), '<' / '<=' (a bound), '>' / '>='. Unstated, a value that
            is no conventional bound is read as exact and one that is (.05,
            .001) keeps the directional rule; see `ttest.resolve_p_relation`.
        df_min, df_max: ONLY when `df` is not printed (`t`, `chi2`). The p is
            then bounded over every df in [df_min, df_max] -- default
            [1, infinity) -- and a reported p outside that interval is wrong
            for every df in it. Supply a bound only when the paper states
            something that forces it (e.g. a stated N caps a t's df at N - 1);
            the result reports whether the verdict needed it.
        p_adjustment: A correction the paper DECLARES for its p ('sphericity',
            'multiplicity', 'none', 'unknown'). A declared correction explains
            a printed p ABOVE the recomputed one (an adjusted p beside its raw
            statistic), so that direction becomes indeterminate; a p BELOW
            what the statistic allows is still a finding.
        one_tailed_stated: The paper says, anywhere, that it tested one-tailed
            (statcheck's `OneTailedTxt` rule). Only then may the 1-df one-tailed
            reading of an F or chi-squared explain a too-small p; otherwise the
            mismatch is a finding with that reading named beside it.
    """
    refusal = survey_refusal("recalc_stat_to_p", sampling)
    if refusal is not None:
        return refusal
    adj = check_p_adjustment(p_adjustment)
    if "error" in adj:
        return {"check": "stat_to_p", "severity": INDETERMINATE, "applicable": False,
                "error": adj["error"]}
    k = _norm_kind(kind)
    out: dict = {
        "check": "stat_to_p",
        "kind": k,
        "statistic": statistic,
        "df": df, "df2": df2, "n": n,
        "tails": tails,
        "ceiling": CEILING,
        "source_quote": source_quote,
        "source_locator": source_locator,
        "source_quote_supplied": bool(source_quote),
        "one_tailed_stated": bool(one_tailed_stated),
    }

    # NaN and infinity are what an extraction produces from an empty cell or a
    # dash. The registry's `ToolSpec.call` guards this; `cli.py` calls the raw
    # function, and a NaN `reported_p` returned `consistent` -- a false ALL-CLEAR.
    bad = refuse_if_nonfinite(statistic=statistic, reported_p=reported_p)
    if bad:
        return {**out, **bad, "applicable": False}

    if k not in NEEDS:
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": (f"unknown statistic {kind!r}; this converts "
                          f"{', '.join(sorted(NEEDS))}")}

    # THE MISSING INGREDIENT IS A FACT ABOUT THE PAPER, and saying which one is
    # missing is the useful half. A chi-squared printed without its degrees of
    # freedom cannot be converted by ANY implementation -- that is not a limit
    # of this kit, and a review should say so in those words.
    have = {"df": df, "df2": df2, "n": n}
    missing = [name for name in NEEDS[k] if not have.get(name)]
    # AN UNPRINTED df IS BOUNDED, NOT REFUSED, where the p is monotone in it.
    df_free = k in _DF_MONOTONE and missing == ["df"]
    if df_free:
        lo_df = _DF_FLOOR if df_min is None else float(df_min)
        hi_df = math.inf if df_max is None else float(df_max)
        if not (math.isfinite(lo_df) and lo_df >= _DF_FLOOR and hi_df >= lo_df):
            return {**out, "severity": INDETERMINATE, "applicable": False,
                    "error": (f"df bounds [{df_min}, {df_max}] are not a range of "
                              f"degrees of freedom (need {_DF_FLOOR:g} <= df_min "
                              "<= df_max)")}
        # The paper still omitted the df: that stays a reportable fact even
        # when the bound below settles the arithmetic.
        out.update({"df_printed": False,
                    "df_range": [lo_df, None if math.isinf(hi_df) else hi_df],
                    "df_bounds_supplied": df_min is not None or df_max is not None,
                    "df_note": (
                        f"No df was supplied, so p is bounded over EVERY df in "
                        f"[{lo_df:g}, {'infinity' if math.isinf(hi_df) else f'{hi_df:g}'}"
                        f"{')' if math.isinf(hi_df) else ']'}: for a fixed statistic "
                        + ("a t's p falls as df grows" if k == "t"
                           else "a chi-squared's p rises with df")
                        + ". A verdict below holds for every df in that range. The "
                        "unprinted df is itself an incompletely reported test -- a "
                        "property of the publication.")})
        missing = []
    elif df is not None and (df_min is not None or df_max is not None):
        out["df_note"] = (f"df = {df} was supplied, so df_min/df_max were ignored: "
                          "they bound an UNPRINTED df only.")
    if missing:
        unbounded = ("" if k != "f" else
                     " An F's p is not monotone in its degrees of freedom -- at "
                     "df1 = 10 and F = 0.7 it falls and then rises as df2 grows -- "
                     "so, unlike a t or a chi-squared, it cannot be bounded over an "
                     "unknown df either.")
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": f"{k} needs {', '.join(missing)} and none was supplied",
                "explanation": (
                    f"A {k} statistic cannot be converted to a p-value without "
                    f"{' and '.join(missing)}. If the paper does not print it, that is a "
                    "property of the publication -- no implementation can recover it -- "
                    "and belongs in the review as an incompletely reported test rather "
                    "than as a limitation of this toolkit." + unbounded)}

    if k == "r" and abs(statistic) >= 1:
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": f"|r| = {abs(statistic)} is not below 1, so it is not a correlation"}
    if k == "r" and n is not None and n <= 2:
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": f"n = {n} leaves no degrees of freedom for a correlation"}
    # TAILS ARE NOT A DEFAULT, THEY ARE AN INPUT.
    #
    # VERIFIED FALSE ACCUSATION, from red-teaming this tool the day it was
    # written: `t = 1.75, df = 28, reported_p = 0.046` returns `suspicious`
    # under the two-tailed default and `consistent` at `tails=1`. That is an
    # honest one-tailed report accused of over-claiming, and the tool listed
    # "a one-tailed test" only as an after-the-fact `alternative_reading`.
    #
    # It already REFUSES when `decimals` is unknown rather than guessing a
    # rounding interval. Guessing the tails is the same class of assumption
    # deciding the same verdict, so it gets the same gate. Two-tailed remains
    # the default for the CONVENIENCE of a caller who says so; passing None
    # means "I do not know", and that is a refusal.
    if tails is None and k not in _UPPER_TAIL_ONLY and reported_p is not None:
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": "the number of tails was not supplied",
                "explanation": (
                    f"A {k} statistic gives a different p one-tailed than two-tailed, and "
                    "which one the paper ran decides the verdict. Read it off the "
                    "methods and call again with `tails=1` or `tails=2`. Assuming would "
                    "settle the question on a fact nobody supplied -- the same reason "
                    "`decimals` is required.")}
    if tails is None:
        tails = 1 if k in _UPPER_TAIL_ONLY else 2
        out["tails"] = tails

    # THE ONE-DF CASE IS NOT A CATEGORY ERROR, AND SAYING IT WAS CAUSED ONE.
    #
    # This note used to read "a two-tailed reading of it is a category error"
    # for every chi2 and F. On PNAS 0801268105 the sweep paraphrased it almost
    # verbatim -- "F has only an upper tail, so no one-tailed convention
    # licenses it here" -- and made that the run's headline SUSPICIOUS finding
    # against three p-values that reconcile exactly on a directional reading.
    # The tool handed the model the false sentence; the model did not invent it.
    #
    # At one numerator degree of freedom the identities F(1,k) = t(k)^2 and
    # chi2(1) = z^2 hold exactly, so the upper-tail p IS the two-tailed p of the
    # underlying t or z, and half of it is the one-tailed p. The tail direction
    # lives in the sign of the underlying contrast, not in the shape of the F or
    # chi-squared distribution. Above one df there is genuinely no direction to
    # take, and the original note is correct there.
    # With the df unprinted, df = 1 is admissible whenever the range starts
    # there, and the 1-df one-tailed reading comes with it.
    _one_df = ((k == "f" and df == 1) or (k == "chi2" and df == 1)
               or (k == "chi2" and df_free and lo_df < 2))
    # A paper that STATES one-tailed testing earns the halved reading for a
    # two-tailed t, z or r as well -- statcheck applies its rule to every test.
    _one_tailed_reading = _one_df or (bool(one_tailed_stated)
                                      and k in ("t", "z", "r") and tails == 2)
    if k in _UPPER_TAIL_ONLY and tails != 1:
        out["tails"] = 1
        if _one_df:
            out["tails_note"] = (
                f"The p returned for this {k} is the upper-tail value. At df = 1 "
                f"that is NOT the whole story: {'F(1, k) = t(k)^2' if k == 'f' else 'chi2(1) = z^2'}"
                " exactly, so this upper-tail p is the TWO-tailed p of the "
                "underlying statistic and half of it is the one-tailed p. A paper "
                "testing a directional hypothesis may legitimately report the "
                "halved value. Do NOT write that a one-tailed reading is "
                "impossible here -- it is not.")
        else:
            out["tails_note"] = (
                f"`tails` is ignored for this {k}: with df "
                f"{'>= ' + format(lo_df, 'g') if df_free else '= ' + str(df)} > 1 it is an "
                "omnibus test whose p is an upper tail by construction, and there "
                "is no single contrast whose sign could give it a direction.")
        tails = 1

    def _span(value: float, lo: float | None = None, hi: float | None = None):
        """(lowest, highest) p one statistic value reaches over the df in play.

        A printed df gives one point. An unprinted one gives the two ends of
        the admissible range, which ARE the extremes because the p is monotone
        in the df (`_DF_MONOTONE`)."""
        if not df_free:
            # A FRACTIONAL df is a printed, rounded value (Welch's t, a
            # Greenhouse-Geisser F): "df = 6.8" is anywhere in [6.75, 6.85).
            # p is monotone in each df, so the extremes are at the corners.
            # MEASURED 2026-10-18 (Garcia-Berthou & Alcaraz 2004, Nature):
            # t(6.8) = 0.837, p = .432 was flagged while a df of 6.75 gives .4316.
            corners = [(df, df2)]
            dfs = [_df_range(df), _df_range(df2)]
            if dfs[0] or dfs[1]:
                corners = [(a, b) for a in (dfs[0] or (df,)) for b in (dfs[1] or (df2,))]
            ps = [_p_from(k, value, a, b, n, tails) for a, b in corners]
            ps = [x for x in ps if x is not None]
            if not ps:
                return (None, None)
            return (min(ps), max(ps))
        a = _p_from(k, value, lo_df if lo is None else lo, None, None, tails)
        b = _p_from(k, value, hi_df if hi is None else hi, None, None, tails)
        return (min(a, b), max(a, b))

    span = _span(float(statistic))
    # The POINT p at the printed df(s); `span` also covers a fractional df's rounding.
    computed = span[0] if df_free else _p_from(k, float(statistic), df, df2, n, tails)
    if computed is None or not all(math.isfinite(x) for x in span):
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": "the conversion did not produce a finite p-value"}
    if df_free:
        # There is no single p to report: one per admissible df.
        out["computed_p"] = None
        out["computed_p_range_over_df"] = list(span)
        hi_txt = "inf)" if math.isinf(hi_df) else f"{hi_df:g}]"
        out["methodology"] = (
            f"{k} = {statistic}, df unprinted, bounded over df in "
            f"[{lo_df:g}, {hi_txt} -> p in [{span[0]:.6g}, {span[1]:.6g}] "
            f"({tails}-tailed)")
        scope = (" at every df in [" + f"{lo_df:g}, "
                 + ("infinity)" if math.isinf(hi_df) else f"{hi_df:g}]"))
    else:
        out["computed_p"] = computed
        out["methodology"] = (
            f"{k} = {statistic}"
            + (f", df = {df}" if df else "") + (f", df2 = {df2}" if df2 else "")
            + (f", n = {n}" if n else "")
            + f" -> p = {computed:.6g} ({tails}-tailed)")
        scope = ""

    if reported_p is None:
        return {**out, "severity": INDETERMINATE, "applicable": True,
                "explanation": ("Computed only: no reported p was supplied to compare "
                                "against, so nothing is asserted about the paper.")}

    # THE STATISTIC IS ROUNDED, so it implies a p INTERVAL. p is monotone in the
    # statistic's magnitude, so the printed value's rounding interval maps to a
    # p range and the reported p is judged against THAT. Comparing to the point
    # p of the printed statistic convicts honestly rounded reports.
    # AND THE WINDOW MUST ADMIT TRUNCATION, not only round-half.
    #
    # VERIFIED FALSE ACCUSATION in this very function. A truncating reporter
    # printing `chi2 = 4.1` may hold a true value up to 4.199..., whose p is
    # 0.0407 -- but a symmetric +/-0.05 window bottoms out at 0.0416, so an
    # honest `p = .041` was flagged as over-claiming. SPSS truncates by default
    # and several journal styles follow it; `grim.py`, `debit.py` and `rivets.py`
    # all already accommodate this convention, and this new tool did not.
    #
    # Truncation puts the true value in [printed, printed + ulp); round-half
    # puts it in [printed - half, printed + half). The union is
    # [printed - half, printed + ulp), and p decreases in the statistic, so the
    # SMALLEST achievable p comes from the top of that range.
    d_s = (decimals_stat if decimals_stat is not None
           else (_rounding.decimals_of_value(statistic) or 0))
    h_s = _rounding.half_width(d_s)
    ulp_s = 10.0 ** -d_s
    top = abs(float(statistic)) + ulp_s
    bottom = max(0.0, abs(float(statistic)) - h_s)
    big, small = _span(top), _span(bottom)
    ends = [x for x in (*big, *small) if x is not None]
    p_lo, p_hi = (min(ends), max(ends)) if len(ends) == 4 else (computed, computed)
    h_p = _rounding.half_width(
        decimals_p if decimals_p is not None
        else (_rounding.decimals_of_value(reported_p) or 0))

    resolved = resolve_p_relation(p_relation, reported_p)
    if "error" in resolved:
        return {**out, "severity": INDETERMINATE, "applicable": False,
                "error": resolved["error"]}
    rel = resolved["relation"]
    out.update({"reported_p": reported_p,
                "achievable_p_interval": [p_lo, p_hi],
                "statistic_rounding_half_width": h_s,
                "p_relation": rel,
                "p_relation_basis": resolved["basis"]})

    # OVER-CLAIM: a reported p BELOW what the printed statistic can support is
    # more significance than the number earns. A "p > x" claim cannot over-claim.
    slack = 0.0 if bound_is_stated(resolved) else h_p
    over_claimed = rel != ">" and reported_p + slack < p_lo - _rounding.EPSILON
    if not over_claimed:
        # UNDER-CLAIM: only an exact p (or a "p > x") can be contradicted from
        # above; a bound ("p < .05") is satisfied by any smaller p.
        if p_under_claimed(p_hi, reported_p, decimals_p, rel):
            return {**out, "applicable": True, "p_adjustment": adj["adjustment"],
                    **explain_under_claim(under_claim_finding(
                        p_hi, reported_p, decimals_p, resolved,
                        f"the printed {k} = {statistic}"),
                        p_adjustment=adj["adjustment"])}
        res = {**out, "severity": CONSISTENT, "consistent": True, "applicable": True,
               "explanation": (
                   f"The printed {k} supports p in [{p_lo:.6g}, {p_hi:.6g}], and the "
                   f"reported p = {reported_p} is consistent with it.")}
        if rel is None and p_under_claimed(p_hi, reported_p, decimals_p, "="):
            res["under_claim_if_exact"] = True
            res["explanation"] += " " + under_claim_note(p_hi, reported_p)
        return res
    # THE ONE-TAILED READING REACHES THE SEVERITY, not just the prose below it.
    # `alternative_reading` already named a one-tailed test as an explanation and
    # the sweep read it, reasoned past it, and accused anyway. A possibility the
    # model has to remember is not a guard; an arithmetic result it is handed is.
    # Mirrors `recalc_f_to_p`, and lands on INDETERMINATE for the same reason:
    # the tail direction is a free parameter the paper never stated, so we cannot
    # determine the p is right. `consistent` would be a false all-clear.
    # A VERDICT THAT NEEDED THE CALLER'S df BOUNDS SAYS SO. Bounds come from
    # the caller's reading of the paper (rulebook rule 4: a bound you derived is
    # an assumed bound), so the result states whether the full range [1, inf)
    # would have flagged too.
    if df_free and out["df_bounds_supplied"]:
        # Over [1, inf) a chi2 also admits the 1-df one-tailed reading, so a
        # bound that only removed df = 1 was needed too.
        wide_lo = min(_span(top, _DF_FLOOR, math.inf)) / (2.0 if k == "chi2" else 1.0)
        out["verdict_needs_df_bounds"] = bool(
            reported_p + slack >= wide_lo - _rounding.EPSILON)
    if _one_tailed_reading:
        # Under an EXACT p the one-tailed reading must also not be exceeded:
        # it rescues a p that sits inside its interval, not one above it.
        # A declared bound gets no rounding slack here either (`bound_is_stated`).
        reconciles = bool(reported_p + slack >= (p_lo / 2.0) - _rounding.EPSILON
                          and not p_under_claimed(p_hi / 2.0, reported_p, decimals_p, rel))
        out["one_tailed_reconciles"] = reconciles
        # ONLY WHEN THE PAPER SAYS SO (1.93.0, statcheck's OneTailedTxt rule).
        # This rescue used to fire on every 1-df F and chi-squared. MEASURED
        # 2026-10-18 on the p-tool benchmark: it decided 23 cases, all 23
        # labelled errors -- 21 of the 49 in Wicherts et al.'s hand coding --
        # and not one correct statistic.
        if reconciles and one_tailed_stated:
            return {**out, "severity": INDETERMINATE, "consistent": None,
                    "applicable": True, "one_tailed_reconciles": True,
                    "explanation": (
                        f"The printed {k} = {statistic} supports p no smaller than "
                        f"{p_lo:.6g} two-tailed{scope}, and the paper reports "
                        f"{reported_p} -- but the one-tailed reading supports p no "
                        f"smaller than {p_lo / 2.0:.6g}, which the reported value "
                        "clears, and the paper states that it tested one-tailed. "
                        "So this is not a p-value inconsistency. It stays "
                        "indeterminate rather than consistent because a paper-wide "
                        "statement does not prove THIS test was one-tailed: if the "
                        "paper names this test as two-tailed, the mismatch stands. "
                        "A one-tailed test at alpha = .05 is two-tailed at .10.")}
        if reconciles:
            out["failure_mode"] = "reconciles_only_one_tailed_unstated"
    if df_free:
        needs = out.get("verdict_needs_df_bounds")
        return {**out, "severity": CEILING, "consistent": False, "applicable": True,
                "holds_for_every_df": True,
                "explanation": (
                    f"The printed {k} = {statistic} supports p no smaller than "
                    f"{p_lo:.6g}{scope}, but the paper reports p = {reported_p} -- more "
                    "significance than the statistic earns at ANY of those degrees of "
                    "freedom, so the paper's unprinted df cannot reconcile it."
                    + (" This rests on the df bounds supplied: over [1, infinity) "
                       "it would not be flagged ("
                       + ("some df, or the 1-df one-tailed reading, reconciles it"
                          if k == "chi2" else "some df reconciles it")
                       + "), so quote the sentence that prints the numerals "
                       "fixing the bound." if needs else "")
                + (" " + ONE_TAILED_UNSTATED_NOTE if out.get("one_tailed_reconciles")
                   else "")),
                "alternative_reading": (
                    ("A one-tailed test, a" if k == "t" and tails == 2 else "A")
                    + " correction applied to the p but not shown, or a statistic "
                    "from a different test than the one named would explain this. "
                    "Check the reported test before treating it as an error.")}
    return {**out, "severity": CEILING, "consistent": False, "applicable": True,
            "explanation": (
                f"The printed {k} = {statistic} supports p no smaller than {p_lo:.6g}, "
                f"but the paper reports p = {reported_p} -- more significance than the "
                "statistic earns at its printed precision."
                + (" " + ONE_TAILED_UNSTATED_NOTE if out.get("one_tailed_reconciles")
                   else "")),
            "alternative_reading": (
                "A one-tailed test, a different df convention, or a correction applied to "
                "the p but not shown would each explain this. Check the reported test "
                "before treating it as an error.")}
