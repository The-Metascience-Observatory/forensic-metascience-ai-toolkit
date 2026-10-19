"""
SD ↔ SE confusion check.

A common reporting error (Heathers 2025 §"Confusing SD and SE"; Olsen 2002
in Infect. Immun. found 40% of one journal's papers reported SE instead of SD).
The two are linked by:

    SE = SD / √n           ⟺           SD = √n · SE

If a paper reports a "standard deviation" value `v` from sample size `n` but
actually means standard error, then the true SD is √n · v. Conversely, if
they report "SE" but mean "SD", the true SE is v / √n. Sanity-checking is
done against an external plausibility ceiling (e.g., for human ages with
range 18–80, max sample SD ≈ 31; an SD of 85 is impossible).

This tool computes both interpretations and, given an optional plausibility
ceiling, returns a verdict on which interpretation is consistent with the
data.
"""

from __future__ import annotations

import math
from typing import Optional

from . import rounding as _rounding
from .sd_checks import check_sd_range


def _max_sd_from_range(min_val: float, max_val: float, n: Optional[int]) -> float:
    """Maximum attainable SAMPLE SD for n points confined to [min_val, max_val].

    Half the points at each extreme gives SD = (range/2)·sqrt(n/(n-1)) -- the
    bound used by `sd_checks.check_sd_range` and recorded as an invariant in
    CLAUDE.md.

    This previously returned `range·sqrt((n-1)/(4n))` = (range/2)·sqrt((n-1)/n),
    the RECIPROCAL correction factor. That sits below the true ceiling (0.90x at
    n=10), so genuinely attainable SDs exceeded it and `check_sd_or_se` started
    arguing the paper had mislabelled an SE. The docstring claimed the two
    formulas matched; they did not.
    """
    rng = max_val - min_val
    if n is not None and n > 1:
        return rng / 2.0 * math.sqrt(n / (n - 1))
    return rng / 2.0



def _se_dp_shift(n: int) -> int:
    """Decimals to DROP so a half-width widens by sqrt(n).

    Under the SE reading the implied SD is sqrt(n) x the reported value, so its
    rounding interval is stretched by sqrt(n). `check_sd_range` takes a decimal
    count rather than a width, and each decimal dropped widens by 10x, so this
    is log10(sqrt(n)) rounded down -- a conservative approximation that never
    widens by MORE than the true factor.
    """
    return int(math.log10(math.sqrt(max(n, 1)))) if n > 1 else 0


def check_sd_or_se(
    reported_value: float,
    n: int,
    reported_as: str = "unknown",
    plausible_sd_max: Optional[float] = None,
    variable_range: Optional[tuple[float, float]] = None,
    decimals: Optional[int] = None,
    bound_source: str = "assumed",
) -> dict:
    """Sanity-check whether a reported dispersion value is more likely SD or SE.

    Args:
        reported_value: The dispersion value as printed in the paper.
        n: Sample size.
        reported_as: One of "SD", "SE", "unknown" — what the paper labels it as.
        plausible_sd_max: Hard upper bound on a plausible SD for this variable.
                          If omitted, derive from `variable_range`.
        variable_range: (min_val, max_val) for the variable; used to derive
                        the SD ceiling via SD ≤ range/2 (cf. SD-range check).
        decimals: PRINTED precision of `reported_value`. A value printed to
                  `d` decimals asserts an interval, and under the SE reading
                  that interval is multiplied by √n — at n = 100 a value
                  printed to one decimal carries ±0.5 of implied SD. Without
                  it the ceiling gets a flat 1% margin, which is a guess and
                  is the wrong size in both directions.
        bound_source: `stated` if the PAPER gives the range/ceiling,
                  `logically_necessary` if it follows from the quantity
                  itself (a proportion lies in [0, 1]), `assumed` (the
                  default) if WE supplied it. The ceiling is the ENTIRE
                  evidential basis of a "neither reading fits" verdict here,
                  so a violation of a ceiling we invented caps at
                  `suspicious`; only a hard bound licenses
                  `highly_suspicious` (rulebook rule 4 — the same rule as
                  grim_test's out_of_range failure mode). Verified: reported
                  SD 12.0 at n = 50 against an assumed 0-10 scale returned
                  `highly_suspicious`, yet fifty real values on the 0-100 mm
                  spelling of the same VAS instrument have sample SD exactly
                  12.0 and are `consistent` against the paper's actual range.

    Returns:
        Dict with both interpretations, their plausibility against the ceiling,
        a "likely_interpretation" string, and a `severity` keyed off the
        reported label.
    """
    if n < 2:
        return {
            "consistent": False,
            "severity": "indeterminate",
            "explanation": "n must be ≥ 2 to relate SD and SE.",
            "methodology": "Trivial precondition.",
            "reported_value": reported_value,
            "n": n,
        }
    if reported_value < 0:
        # OUR artefact, not their claim: no software prints a negative SD or SE,
        # so the minus came from our parse (an en dash, or a range separator).
        # Publishing it as `impossible` reports an extraction bug as an
        # accusation, and it also broke this tool's declared ceiling, which is
        # `highly_suspicious`. `recalc_independent_t` already refuses the same
        # input as `indeterminate`.
        return {
            "consistent": False,
            "severity": "indeterminate",
            "explanation": (
                "Not evaluated. A negative dispersion value is not something any "
                "analysis produces, so this is almost certainly a value we mis-read "
                "(a dash or a range separator taken for a minus sign)."
            ),
            "methodology": "Trivial precondition.",
            "reported_value": reported_value,
            "n": n,
        }

    label = reported_as.strip().upper()
    if label not in ("SD", "SE", "UNKNOWN"):
        label = "UNKNOWN"

    sqrt_n = math.sqrt(n)

    # Interpretation 1: value is an SD. Implied SE = value / √n.
    as_sd = {
        "interpretation": "value is SD",
        "implied_sd": reported_value,
        "implied_se": reported_value / sqrt_n,
    }
    # Interpretation 2: value is an SE. Implied SD = √n · value.
    as_se = {
        "interpretation": "value is SE (mislabeled)",
        "implied_sd": sqrt_n * reported_value,
        "implied_se": reported_value,
    }

    # Resolve plausibility ceiling.
    ceiling = plausible_sd_max
    ceiling_source = "explicit"
    if ceiling is None and variable_range is not None:
        ceiling = _max_sd_from_range(variable_range[0], variable_range[1], n)
        ceiling_source = f"range/2 (from {variable_range})"

    # WHOSE bound is the ceiling? A "neither interpretation fits" verdict
    # below rests ENTIRELY on this ceiling, so it inherits the ceiling's
    # provenance: a bound WE assumed licenses at most `suspicious`, exactly
    # the rule grim_test applies to its out_of_range failure mode
    # (tools/grim.py:183-204; rulebook rule 4). Anything outside HARD_BOUNDS
    # -- including a typo -- fails SAFE, toward the cap.
    HARD_BOUNDS = {"stated", "logically_necessary"}
    hard_bound = bound_source in HARD_BOUNDS
    ceiling_violation_severity = "highly_suspicious" if hard_bound else "suspicious"
    assumed_note = (
        "" if hard_bound else (
            " The ceiling rests on a bound WE supplied (bound_source="
            f"'{bound_source}'), not one the paper states, so this is capped "
            "at `suspicious` (rulebook rule 4); pass bound_source='stated' "
            "with the paper's own range to escalate."
        )
    )

    # How much slack the ceiling gets. A value printed to `decimals` places
    # asserts an interval, and only the SMALLEST implied SD that interval
    # permits can be tested against the ceiling -- otherwise a value implausible
    # solely because of rounding is reported as implausible. Under the SE
    # reading the interval is stretched by √n, so the two readings do not get
    # the same slack. With no printed precision the old flat 1% margin stands,
    # which is a guess: too generous for a coarse value, too mean for a fine one.
    half = _rounding.half_width(decimals) if decimals is not None else None
    margin_source = (f"printed precision ({decimals} dp)" if half is not None
                     else "flat 1% (printed precision not supplied)")

    if ceiling is not None:
        if half is not None:
            as_sd["sd_plausible"] = (as_sd["implied_sd"] - half) <= ceiling
            as_se["sd_plausible"] = (as_se["implied_sd"] - sqrt_n * half) <= ceiling
        else:
            as_sd["sd_plausible"] = as_sd["implied_sd"] <= ceiling * 1.01
            as_se["sd_plausible"] = as_se["implied_sd"] <= ceiling * 1.01
        # If a range was supplied, also run the formal SD-range check on each.
        if variable_range is not None:
            # Thread the precision into the nested check too. Without it the
            # nested result kept the flat 1% margin while the outer verdict used
            # printed precision, so one payload carried both `sd_plausible:
            # True` and a nested `severity: impossible` -- the top of the
            # ladder, sitting inside a `consistent` result the model reads.
            #
            # Under the SE reading the implied SD is sqrt(n) times the reported
            # value, so its rounding interval is stretched by the same factor.
            as_sd["sd_range_check"] = check_sd_range(
                as_sd["implied_sd"], variable_range[0], variable_range[1], n,
                decimals_sd=decimals,
            )
            as_se["sd_range_check"] = check_sd_range(
                as_se["implied_sd"], variable_range[0], variable_range[1], n,
                decimals_sd=None if decimals is None else max(0, decimals - _se_dp_shift(n)),
            )
            # `check_sd_range` has no bound_source parameter, so against a
            # range WE supplied it will still say `impossible` -- the top of
            # the ladder, nested inside a result whose own verdict is capped
            # at `suspicious`. Same payload-contradiction as the precision
            # mismatch above, resolved the same way: the subordinate verdict
            # is downgraded and says why. Its only `impossible` paths here are
            # ceiling failures (a negative SD is returned before this point),
            # so the downgrade can never mask a bound-free impossibility.
            if not hard_bound:
                for chk in (as_sd["sd_range_check"], as_se["sd_range_check"]):
                    if chk.get("severity") == "impossible":
                        chk["severity"] = "suspicious"
                        chk["severity_note"] = (
                            "downgraded from `impossible`: this range verdict "
                            f"rests on bound_source='{bound_source}' bounds "
                            "(ours, not the paper's) -- rulebook rule 4."
                        )
    else:
        as_sd["sd_plausible"] = None
        as_se["sd_plausible"] = None

    # Decide which interpretation is more likely.
    likely = "indeterminate"
    severity = "indeterminate"
    explanation = (
        "No plausibility ceiling provided; cannot adjudicate. "
        "Provide `plausible_sd_max` or `variable_range` for a verdict."
    )

    if ceiling is not None:
        sd_ok = as_sd["sd_plausible"]
        se_ok = as_se["sd_plausible"]
        if sd_ok and not se_ok:
            likely = "SD"
        elif se_ok and not sd_ok:
            likely = "SE"
        elif sd_ok and se_ok:
            # A TIE MUST NOT PRODUCE AN ACCUSATION. This branch means both
            # readings are plausible -- we have established nothing about which
            # the paper used. It hardcoded "SD" and called that "the literal
            # reading", but the literal reading is whatever the paper LABELLED.
            # For an SE-labelled value the default therefore contradicted the
            # page and the tool reported `suspicious` mislabeling on a
            # tie-break, with no evidence behind it.
            #
            # VERIFIED FALSE ACCUSATION, 8 archived calls across 3 papers. In
            # every one the paper's own label was the MORE plausible reading:
            # Ladurner Table 1 CNS, SE = 0.09, n = 78, scale 4.5-8. As SE it
            # implies SD = 0.79, 23% of the scale range -- ordinary. As SD it
            # implies 0.09, 2.6% of the range, an implausibly tight spread for
            # 78 stroke patients. The tool preferred the reading the paper did
            # not use and flagged the paper for not using it.
            #
            # Deferring to the label leaves SD-labelled values exactly as they
            # were (label SD + likely SD was already `consistent`) and turns the
            # SE-labelled tie into `consistent` with its own explanation.
            likely = label if label in ("SD", "SE") else "SD"
        else:
            likely = "neither"

        # Severity based on label vs likelihood. The mislabelling diagnoses
        # stay at `suspicious` regardless of bound_source -- they are already
        # at the assumed-bound cap. Only the ceiling-violation ("neither")
        # verdicts may escalate, and only on a hard bound.
        if label == "SD":
            if likely == "SE":
                severity = "suspicious"
                explanation = (
                    f"Labeled SD = {reported_value} implies SD = {reported_value} "
                    f"(plausible: {sd_ok}). If actually SE, implied SD = "
                    f"√{n} · {reported_value} = {as_se['implied_sd']:.4g} "
                    f"(plausible: {se_ok}). Likely mislabeling: paper says SD, "
                    "but the SE interpretation fits the plausibility ceiling better."
                )
            elif likely == "neither":
                severity = ceiling_violation_severity
                explanation = (
                    f"Both interpretations exceed the plausibility ceiling "
                    f"({ceiling:.4g}). Labeled SD = {reported_value}; implied SD "
                    f"under SE interpretation = {as_se['implied_sd']:.4g}."
                    + assumed_note
                )
            else:
                severity = "consistent"
                explanation = f"Labeled SD = {reported_value} is plausible (≤ {ceiling:.4g})."
        elif label == "SE":
            if likely == "SD":
                severity = "suspicious"
                explanation = (
                    f"Labeled SE = {reported_value} implies SD = "
                    f"√{n} · {reported_value} = {as_se['implied_sd']:.4g} "
                    f"(plausible: {se_ok}). If actually SD, the value is "
                    f"{reported_value} (plausible: {sd_ok}). Likely mislabeling: "
                    "paper says SE, but the SD interpretation fits better — the "
                    "value may be an SD reported as SE."
                    # THE ONE CEILING VERDICT THAT DID NOT SAY WHOSE CEILING IT
                    # WAS. The `neither` branch below appends `assumed_note`,
                    # which reads "The ceiling rests on a bound WE supplied
                    # (bound_source='assumed'), not one the paper states". This
                    # branch reached the same `suspicious` off the same ceiling
                    # and disclosed nothing, so the reader saw a claim about the
                    # PAPER's labelling with no hint that our own assumed range
                    # produced it.
                    #
                    # MEASURED: a 20-item scale scored as a SUM (true range
                    # 20-100) reporting Mean 62.4 (SE 0.6) at n = 100 -- an
                    # ordinary SEM implying SD 6.0. Read against an ASSUMED 1-5
                    # item range it returns "Likely mislabeling". Given the
                    # stated 20-100 range it returns `consistent`. The paper
                    # never changed; our ceiling did.
                    + assumed_note
                )
            elif likely == "neither":
                severity = ceiling_violation_severity
                explanation = (
                    f"Labeled SE = {reported_value} implies SD = "
                    f"{as_se['implied_sd']:.4g}, exceeding plausibility ceiling "
                    f"{ceiling:.4g}. The SD interpretation ({reported_value}) is "
                    "also implausible. Both readings are problematic."
                    + assumed_note
                )
            else:
                severity = "consistent"
                explanation = (
                    f"Labeled SE = {reported_value} implies SD = "
                    f"{as_se['implied_sd']:.4g}, which is plausible (≤ {ceiling:.4g})."
                )
        else:  # UNKNOWN
            if likely in ("SD", "SE"):
                severity = "consistent"
                explanation = (
                    f"Likely reading: {likely}. (SD interpretation plausible: "
                    f"{sd_ok}; SE interpretation plausible: {se_ok}.)"
                )
            else:
                severity = ceiling_violation_severity
                explanation = (
                    f"Neither SD ({reported_value}) nor SE→SD "
                    f"({as_se['implied_sd']:.4g}) is below the plausibility "
                    f"ceiling {ceiling:.4g}."
                    + assumed_note
                )

    return {
        "reported_value": reported_value,
        "n": n,
        "reported_as": label,
        "as_sd": as_sd,
        "as_se": as_se,
        "plausibility_ceiling": ceiling,
        "ceiling_source": ceiling_source if ceiling is not None else None,
        "bound_source": bound_source,
        "likely_interpretation": likely,
        "severity": severity,
        "explanation": explanation,
        "methodology": (
            f"SD/SE confusion check: SE = SD/√n. For n = {n}, √n = {sqrt_n:.4f}. "
            f"As-SD interpretation: SD = {reported_value}, implied SE = "
            f"{as_sd['implied_se']:.4g}. As-SE interpretation: SE = "
            f"{reported_value}, implied SD = {as_se['implied_sd']:.4g}. "
            f"Plausibility ceiling = "
            f"{f'{ceiling:.4g}' if ceiling is not None else 'unspecified'}, "
            f"tested with slack from {margin_source}. Ceiling provenance: "
            f"bound_source='{bound_source}'"
            + (" (hard bound; a both-readings violation may escalate to "
               "highly_suspicious)." if hard_bound else
               " (ours, not the paper's; a ceiling violation caps at "
               "suspicious -- rulebook rule 4).")
        ),
    }
