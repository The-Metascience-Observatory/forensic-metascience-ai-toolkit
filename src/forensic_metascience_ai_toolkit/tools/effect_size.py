"""Effect sizes, and whether a reported one is plausible for its field.

WHY THIS EXISTS
---------------
`stage2_editorial.md` has always instructed the model to assess "effect-size
plausibility -- compare headline effects to external benchmarks you are
confident of; name the benchmark." Nothing backed that. The model was being
asked for a quantitative judgement from memory, with no tool and no citable
source -- exactly the failure mode the rest of this toolkit exists to remove.

An effect size far outside what is typical for its design is one of the most
informative things you can tell a reader. It is not evidence of misconduct: real
large effects exist, and some fields genuinely produce them. But a d of 3.5 in a
psychotherapy trial, where the field's own meta-analytic distribution centres
near 0.5, is something the reader needs in order to judge the paper at all.

WHY THIS TOOL SURVIVES FIGURE-DERIVED DATA
------------------------------------------
This is the check where digitized numbers earn their keep. Reading a group mean
off a chart carries ~0.44% median error and an error bar ~3.89% (worst case
27.7%, re-measured 2026-08-29 after the benchmark's sweep was re-seeded --
the old 4.15%/37.3% came from a per-process-salted `hash()` seed and did not
reproduce). That is fatal for GRIM, which asks whether a number is possible to its
last printed digit. It is irrelevant here: d = 3.5 is extraordinary whether the
true value is 3.4 or 3.6, and the verdict does not move.

So papers that report an outcome ONLY as a bar chart -- where the means and
SD/SEM exist nowhere in the text -- become checkable for the first time, and
this is the check that works on them.

WHAT IT MUST NOT DO
-------------------
Return `impossible`. An effect size cannot be arithmetically impossible the way
a GRIM-inconsistent mean can; it can only be improbable. The ceiling here is
`suspicious`, and the wording is "unusual for this design, verify the units and
the comparison", never "fabricated".
"""

from __future__ import annotations

import math

from .severity import refuse_if_nonfinite

# ---------------------------------------------------------------------------
# Field benchmarks
# ---------------------------------------------------------------------------
#
# EVERY entry names its source. A benchmark without a citation is an opinion,
# and this tool exists precisely because the model was supplying those from
# memory. Where a field has no benchmark we trust, it is absent, and the tool
# says so rather than substituting a neighbouring field.
#
# These are distributions of OBSERVED effect sizes in the literature, which are
# themselves inflated by publication bias -- so an effect at the 99th percentile
# of published effects is even more unusual relative to reality. Noted in the
# output rather than silently corrected for.

# `provenance` says whether the NUMBERS are traceable to a published table:
#   "cited"            -- median/p75/p95 read directly off a table in the named
#                         source (verifiable, falsifiable).
#   "uncited_estimate" -- the prose claim is real but the percentiles are an
#                         informal estimate not printed in any named source.
#                         Disclosed in the tool output: an unfalsifiable
#                         standard must not pose as a citation.

#: Benchmarks WITHDRAWN, with the reason, so a caller that names one gets a
#: diagnosis instead of "unknown field". A retired standard that vanishes
#: silently is indistinguishable from a typo, and the next person re-adds it.
RETIRED_BENCHMARKS: dict[str, str] = {
    "psychology_general": (
        "WITHDRAWN 2026-08-16: its median of 0.40 was taken from the Open "
        "Science Collaboration (2015) mean original effect of r = .40 -- a "
        "CORRELATION. As a Cohen's d that is d ~ 0.87, so the row compared "
        "reported effect sizes against a threshold less than half of what its "
        "own source implies, and over-flagged ordinary psychology effects as "
        "large. No d percentiles appear anywhere in that paper. Replacing the "
        "numbers would mean inventing percentiles to stand in for a citation, "
        "which is the defect and not the fix. Omit `field` and report the "
        "effect size with its interval, or name a field whose benchmark is "
        "traceable."
    ),
}

FIELD_BENCHMARKS: dict[str, dict] = {
    "social_psychology": {
        "median": 0.36, "p75": 0.65, "p95": 1.30,
        "provenance": "cited",
        "source": "Lovakov & Agadullina (2021), Eur J Soc Psychol, Table 1 -- "
                  "empirical percentiles of 6,447 Cohen's d effect sizes from "
                  "59 social-psychology meta-analyses: 25th 0.15, 50th 0.36, "
                  "75th 0.65, 90th 0.99, 95th 1.30. (Effects were analysed as "
                  "absolute values, matching this tool's use of |d|.)",
    },
    "cognitive_psychology": {
        "median": 0.50, "p75": 0.90, "p95": 1.6,
        "provenance": "uncited_estimate",
        "source": "Open Science Collaboration (2015) -- cognitive-psychology "
                  "originals replicated at higher rates and larger effects than "
                  "social; treat as approximate. These percentiles are not "
                  "printed in the source.",
    },
    "medicine_rct": {
        "median": 0.30, "p75": 0.55, "p95": 1.0,
        "provenance": "uncited_estimate",
        "source": "Standardised mean differences in Cochrane reviews cluster "
                  "well below 0.5; effects above ~1.0 in a clinical trial are "
                  "uncommon outside acute, high-contrast interventions. No "
                  "specific published table backs these percentiles.",
    },
    "education": {
        "median": 0.40, "p75": 0.60, "p95": 1.0,
        "provenance": "uncited_estimate",
        "source": "Hattie's synthesis places the average educational "
                  "intervention near d = 0.40; note Simpson's (2017) critique "
                  "that pooled 'average' effects are not comparable across "
                  "designs, and that well-controlled education RCTs (e.g. EEF "
                  "trials) average far lower. p75/p95 are informal estimates.",
    },
    "psychotherapy": {
        "median": 0.50, "p75": 0.80, "p95": 1.3,
        "provenance": "uncited_estimate",
        "source": "Psychotherapy-vs-control trials typically report d in the "
                  "0.5-0.8 band; larger effects usually indicate a waitlist "
                  "control rather than an active comparator. No specific "
                  "published table backs these percentiles.",
    },
}

#: Above this, an effect is remarkable in ANY field. Not a threshold for
#: suspicion on its own -- a reason to check the units and the comparison first.
UNIVERSALLY_LARGE_D = 2.0


def _hedges_correction(df: float) -> float:
    """Hedges' small-sample correction J. Approaches 1 as df grows."""
    if df <= 1:
        return float("nan")
    return 1.0 - (3.0 / (4.0 * df - 1.0))


def cohens_d(
    mean1: float, sd1: float, n1: int,
    mean2: float, sd2: float, n2: int,
    correct_small_sample: bool = True,
) -> dict:
    """Standardised mean difference from two independent groups.

    Returns Cohen's d and (by default) Hedges' g, which corrects d's upward bias
    at small n -- the bias is about 4% at n=20 per group and is worth applying
    whenever the tool is used to judge whether an effect is unusually large.
    """
    # A NaN/inf is our extraction artefact, not a reported statistic. Without
    # this, mean1=NaN propagated to d=NaN at severity `consistent`, and an
    # infinite SD collapsed to d = 0.0 `consistent` -- false all-clears stated
    # as verdicts. The registry gate protects the MCP surface only; this is
    # the raw function's own guard (same rationale as refuse_if_nonfinite).
    guard = refuse_if_nonfinite(mean1=mean1, sd1=sd1, n1=n1,
                                mean2=mean2, sd2=sd2, n2=n2)
    if guard is not None:
        return guard

    if n1 < 2 or n2 < 2:
        return {"error": f"need n >= 2 per group (got {n1}, {n2})",
                "severity": "indeterminate"}
    if sd1 < 0 or sd2 < 0:
        return {"error": "standard deviations cannot be negative",
                "severity": "indeterminate"}

    df = n1 + n2 - 2
    pooled_var = (((n1 - 1) * sd1 ** 2) + ((n2 - 1) * sd2 ** 2)) / df
    if pooled_var <= 0:
        return {"error": "pooled variance is zero; both SDs are zero",
                "severity": "indeterminate"}
    pooled_sd = math.sqrt(pooled_var)
    d = (mean1 - mean2) / pooled_sd

    out = {
        "d": d,
        "abs_d": abs(d),
        "pooled_sd": pooled_sd,
        "df": df,
        "n_total": n1 + n2,
        "severity": "consistent",
        "methodology": (
            "Cohen's d = (M1 - M2) / pooled SD, with pooled SD from the "
            "(n-1)-weighted variances."
        ),
    }
    if correct_small_sample:
        j = _hedges_correction(df)
        out["hedges_g"] = d * j
        out["hedges_correction_j"] = j

    # A CONFIDENCE INTERVAL, because a point estimate invites exactly the
    # eyeballing Greg wants to replace: "d = 0.8" and "d = 0.8 [0.1, 1.5]" say
    # very different things about whether an effect is worth attention, and only
    # the second lets a reader see that a study is too small to distinguish a
    # large effect from nothing. Large-sample normal approximation --
    # SE = sqrt((n1+n2)/(n1 n2) + d^2 / (2(n1+n2))) -- which is the standard
    # Hedges & Olkin form and is adequate away from very small n. It is an
    # ESTIMATE and the key says so.
    try:
        _n1, _n2 = int(n1), int(n2)
        _d = out["d"]
        _se = ((_n1 + _n2) / (_n1 * _n2) + (_d * _d) / (2.0 * (_n1 + _n2))) ** 0.5
        out["se_d"] = _se
        out["ci95_d"] = [_d - 1.96 * _se, _d + 1.96 * _se]
        out["ci95_method"] = ("large-sample normal approximation (Hedges & Olkin); "
                              "an estimate, not an exact interval")
    except Exception:  # noqa: BLE001 -- a missing CI is not a reason to lose d
        out["ci95_d"] = None
        out["ci95_method"] = "not computed"
        out["methodology"] += (
            f" Hedges' g applies J = 1 - 3/(4*df - 1) = {j:.4f}, correcting d's "
            "upward small-sample bias."
        )
    return out


def _design_is_paired(design) -> bool:
    """Whether a declared design measures the same units more than once.

    Reuses `csf._resolve_design` rather than restating the vocabulary: this
    codebase has found the same constant hand-copied eleven times with the
    copies disagreeing, and a second design list here would drift from the one
    `check_variance_dispersion` refuses on.
    """
    if not design:
        return False
    # A PLAIN IMPORT, not a guarded one. `csf` imports only numpy and scipy and
    # does not import this module, so there is no cycle to defend against -- and
    # swallowing an ImportError here would make "the design vocabulary is
    # missing" indistinguishable from "this design is not paired", which is the
    # direction that accuses an honest paper.
    from .csf import _resolve_design
    return _resolve_design(design) in {
        "repeated_measures", "within_subjects", "pre_post", "longitudinal",
        "crossover", "paired", "matched_pairs",
    }


def check_effect_plausibility(
    d: float | None = None,
    field: str | None = None,
    reported_d: float | None = None,
    mean1: float | None = None, sd1: float | None = None, n1: int | None = None,
    mean2: float | None = None, sd2: float | None = None, n2: int | None = None,
    design: str | None = None,
    provenance: str = "printed_text",
) -> dict:
    """Compute an effect size, report it with a CI, and check it against itself.

    Either pass `d` directly, or the six group statistics and it will be
    computed -- with a 95% CI, because a point estimate invites exactly the
    eyeballing this is meant to replace.

    THREE MODES, and the middle one is the valuable one:

      reported_d + group stats  INTERNAL CONSISTENCY. Does the effect size the
                                paper printed match the one its own means, SDs
                                and ns imply? No benchmark, no comparison class,
                                no opinion about what "large" means.
      group stats alone         Report d and its CI. `severity: consistent`,
                                because stating a value is not an accusation.
      + field (optional)        Additionally place it against field benchmarks.
                                Mostly uncited estimates; the result says so.

    GREG, 2026-08-16: "Having the effect size tools have any a priori
    expectations for what constitutes a large effect size is not especially
    helpful... insofar as they are unrealistically large, that is something that
    the human can judge themselves after seeing all the effect sizes laid out."
    So `field` is optional and omitting it is the ordinary case, not a
    misconfiguration -- this used to end by demanding one.

    `provenance` is carried through. A figure-derived effect is still perfectly
    usable here -- gross implausibility survives digitization error -- but the
    finding says so, because a reader should know the number was read off a
    chart rather than printed.
    """
    computed = None
    if d is None:
        if None in (mean1, sd1, n1, mean2, sd2, n2):
            return {
                "severity": "indeterminate",
                "error": "provide either `d`, or all of mean1/sd1/n1/mean2/sd2/n2",
            }
        computed = cohens_d(mean1, sd1, n1, mean2, sd2, n2)
        if computed.get("error"):
            return computed
        d = computed.get("hedges_g", computed["d"])

    # A non-finite d is our artefact (a failed parse, an upstream overflow),
    # never a paper's reported effect. Judging it produced "|d| = nan is
    # within the usual range" at `consistent` -- a false all-clear -- and
    # "|d| = inf ... at or above the 95th percentile" at `suspicious` -- a
    # claim about the paper manufactured from our own garbage.
    guard = refuse_if_nonfinite(d=d)
    if guard is not None:
        return guard

    abs_d = abs(d)
    result: dict = {
        "d": d,
        "abs_d": abs_d,
        "field": field,
        "design": design,
        "provenance": provenance,
        "computed_from_group_stats": computed,
    }

    if provenance == "figure_pixels":
        result["provenance_note"] = (
            "This effect size was derived from values read off a figure, not from "
            "printed numbers. That is acceptable HERE -- gross implausibility "
            "survives the ~0.4% central / ~4% dispersion digitization error -- but "
            "the same values must not be used for GRIM, GRIMMER, SPRITE or DEBIT, "
            "which require the last printed digit."
        )

    # INTERNAL CONSISTENCY FIRST, because it needs no comparison class at all.
    # GREG, 2026-08-16: "Having the effect size tools have any a priori
    # expectations for what constitutes a large effect size is not especially
    # helpful. What I want ... is for all effect sizes to be calculated (or
    # estimated), and then agent 2 can judge whether the effect sizes are
    # INTERNALLY consistent within the paper."
    #
    # When a paper prints BOTH an effect size and the group statistics it came
    # from, those two numbers are a closed system: recompute and compare. That is
    # an exact check with no benchmark, no field, and no opinion about what large
    # means -- and it is the check that would have caught Mazar 2023, where a
    # printed d of .050 was inconsistent with the means printed beside it.
    if reported_d is not None and computed is not None:
        # WHICH ESTIMATOR DID THE PAPER REPORT? It usually does not say, and the
        # two differ by the Hedges correction j = 1 - 3/(4N-9) -- about 1.3% at
        # N = 60. This block used to recompute HEDGES' G and compare it to a
        # reported value with a tolerance sized for ROUNDING ALONE, so a paper
        # that printed an exactly correct COHEN'S D was accused of internal
        # inconsistency.
        #
        # MEASURED: means 10.0/8.9, SDs 2.0/2.0, n = 30 each. Exact Cohen's d is
        # 0.5500; Hedges' g is 0.5429. A paper printing "d = 0.55" -- correct to
        # every digit it printed -- produced gap 0.0071 against tolerance 0.005
        # and the verdict `suspicious`, under the sentence "One of the two
        # printed values is wrong."
        #
        # A CHECK MAY NOT ACCUSE ON A CONVENTION THE PAPER NEVER STATED. Both
        # estimators are legitimate readings of "d", so the reported value is
        # consistent if it reconciles with EITHER, and the result records which.
        # This is the same rule the rounding work follows: where two conventions
        # are defensible and the paper picks neither, the check reports rather
        # than accuses.
        candidates = {"cohens_d": computed["d"]}
        if "hedges_g" in computed:
            candidates["hedges_g"] = computed["hedges_g"]
        decimals = len(str(reported_d).split(".")[-1]) if "." in str(reported_d) else 0
        tol = max(0.5 * 10 ** (-decimals), 0.005)

        # A MEASURED VALUE HAS NO LAST PRINTED DIGIT, so a rounding half-width is
        # the wrong bound for one. This tool's own docstring is titled "WHY THIS
        # TOOL SURVIVES FIGURE-DERIVED DATA" and cites ~0.44% central and ~3.89%
        # dispersion error -- and the tolerance ignored `provenance` entirely, so
        # a figure-read effect size was held to a rounding bound it cannot meet.
        # The dispersion channel is the one that matters here: d carries the
        # pooled SD in its denominator.
        #
        # THE BUDGET IS SIMULATED, NOT MEASURED -- `make_human_floor(sigma=1.0)`
        # in the figure-extractor benchmark is an uncited default and no human
        # has been measured against it. Widening here is the safe direction
        # regardless (it can only withdraw an accusation), but the multiplier
        # must not be read as an empirical bound.
        from ..registry import MEASURED_PROVENANCE
        if provenance in MEASURED_PROVENANCE:
            from ..extraction.figures import FIGURE_ERROR_BUDGET
            tol = max(tol, abs(reported_d) * FIGURE_ERROR_BUDGET["dispersion"])
            result["tolerance_widened_for"] = provenance

        best = min(candidates, key=lambda k: abs(abs(reported_d) - abs(candidates[k])))
        recomputed = candidates[best]
        gap = abs(abs(reported_d) - abs(recomputed))
        result["reported_d"] = reported_d
        result["recomputed_d"] = recomputed
        result["recomputed_as"] = best
        result["candidates"] = {k: round(v, 4) for k, v in candidates.items()}
        result["abs_difference"] = gap
        result["tolerance"] = tol
        if gap > tol and _design_is_paired(design):
            # A PAIRED DESIGN REPORTS A DIFFERENT QUANTITY, and this comparison
            # cannot be made from what the tool is given.
            #
            # The recomputation above is a BETWEEN-GROUPS d: the mean difference
            # over a pooled SD. A within-subjects study reports `d_z`, the mean
            # change over the SD OF THE DIFFERENCES, and the two are related by
            # d_rm = d_z * sqrt(2 * (1 - r)) -- so they coincide only at r = 0.5
            # and diverge without limit as the pre-post correlation rises. That
            # correlation is not among this function's arguments and cannot be
            # inferred from pre/post means and SDs, so the paper's d_z is not
            # checkable here AT ALL.
            #
            # MEASURED: an honest within-subjects study with pre 50.0 (10.0),
            # post 44.5 (10.0), n = 30, reporting its correct d_z = 0.87,
            # returned `suspicious` -- "One of the two printed values is wrong."
            # Neither was. `design` was accepted, echoed into the result, and
            # consulted nowhere.
            #
            # `paired_d_interval` in this module is the tool that answers this
            # question, by returning a RANGE over plausible r rather than a
            # point. Refusing and naming it is honest; guessing an r is how a
            # correct paper gets accused.
            result["severity"] = "indeterminate"
            result["applicable"] = False
            result["why_not_checked"] = (
                f"this is a {design} design, which reports d_z -- the mean "
                f"change over the SD of the DIFFERENCES -- while the statistics "
                f"printed beside it give a between-groups d. The two are related "
                f"by d_rm = d_z * sqrt(2 * (1 - r)), and the pre-post "
                f"correlation r is neither printed here nor inferable from "
                f"these six numbers, so no disagreement between them is "
                f"evidence about the paper. Use `paired_d_interval`, which "
                f"returns the range of d consistent with a reported d_z over "
                f"plausible r.")
        elif gap > tol:
            result["severity"] = "suspicious"
            result["explanation"] = (
                f"The paper reports d = {reported_d}, but the group statistics printed "
                f"beside it give d = {recomputed:.3f} (|difference| = {gap:.3f}, "
                f"tolerance {tol:g}). One of the two printed values is wrong. This is "
                "internal inconsistency, not a judgement about the size of the effect; "
                "the commonest cause is a transcription or typesetting error, and a "
                "dispersion reported as SEM rather than SD would inflate the "
                "recomputed value by sqrt(n)."
            )
        else:
            result["severity"] = "consistent"
            result["explanation"] = (
                f"The reported d = {reported_d} reconciles with the group statistics "
                f"printed beside it as {best.replace('_', chr(32))} "
                f"(recomputed {recomputed:.3f}, within {tol:g})."
            )
        result["methodology"] = (
            "Internal consistency: the reported effect size recomputed from the "
            "paper's own group statistics. No benchmark and no comparison class.")
        return result

    bench = FIELD_BENCHMARKS.get((field or "").strip().lower()) if field else None
    if bench is None:
        # NO FIELD IS THE DEFAULT AND IS NOT A DEFICIENCY. Reporting the value
        # with its interval is the deliverable; whether an effect is
        # "unrealistically large" is a judgement for the reader with all of the
        # paper's effects laid out in front of them, and for stage 2 looking
        # across them. This branch used to end by demanding a `field`, which
        # made the ordinary case read as a failure to configure the tool.
        # A REQUESTED COMPARISON WE CANNOT MAKE IS NOT A CLEAN RESULT. Omitting
        # `field` is the ordinary case and reports the value; naming a field we
        # have no benchmark for is a request that FAILED, and collapsing the two
        # would let "we could not do what you asked" read as "nothing is wrong".
        if field:
            retired = RETIRED_BENCHMARKS.get((field or "").strip().lower())
            result["severity"] = "indeterminate"
            result["explanation"] = (
                f"Effect size d = {d:.3f}"
                + (f", 95% CI [{(computed or {}).get('ci95_d')[0]:.3f}, "
                   f"{(computed or {}).get('ci95_d')[1]:.3f}]"
                   if (computed or {}).get("ci95_d") else "")
                + (f". The benchmark for {field!r} was withdrawn. {retired}"
                   if retired else
                   f". No benchmark exists for field {field!r}, so the comparison you "
                   "asked for was not made.")
                + " Available: "
                + ", ".join(sorted(FIELD_BENCHMARKS))
                + ". Omit `field` entirely to report the value without any comparison."
            )
            if retired:
                result["benchmark_withdrawn"] = field
            result["methodology"] = "Effect-size report: requested benchmark unavailable."
            return result

        result["severity"] = "consistent"
        ci = (computed or {}).get("ci95_d")
        result["explanation"] = (
            f"Effect size d = {d:.3f}"
            + (f", 95% CI [{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "")
            + ". Reported, not judged: no comparison class was supplied and none is "
              "needed to state the value. Magnitude is for the reader and for the "
              "editorial pass to weigh across the paper's effects as a set."
        )
        if abs_d >= UNIVERSALLY_LARGE_D:
            result["note"] = (
                f"|d| = {abs_d:.2f} is remarkable in any field. Before treating it as a "
                "finding, check that the units are what you think, that the comparison "
                "is the one the paper claims, and that the dispersion is an SD rather "
                "than an SEM -- mistaking SEM for SD inflates d by sqrt(n)."
            )
        result["methodology"] = "Effect-size plausibility: no benchmark applied."
        return result

    result["benchmark"] = bench
    result["benchmark_source"] = bench["source"]
    result["benchmark_provenance"] = bench.get("provenance", "uncited_estimate")
    if result["benchmark_provenance"] != "cited":
        # The caveat must travel with the finding, not sit in a card only a
        # card-reader sees: a percentile that no published table backs is an
        # informal yardstick, and a reader weighing the verdict needs to know.
        result["benchmark_caveat"] = (
            f"The percentile thresholds for {field} are an informal estimate, "
            "not numbers printed in the named source (see benchmark_source). "
            "Treat the band as a yardstick for context, not a citable standard."
        )

    if abs_d >= bench["p95"]:
        result["severity"] = "suspicious"
        band = f"at or above the field's 95th percentile ({bench['p95']})"
    elif abs_d >= bench["p75"]:
        result["severity"] = "indeterminate"
        band = f"above the field's 75th percentile ({bench['p75']})"
    else:
        result["severity"] = "consistent"
        band = f"within the usual range (field median {bench['median']})"

    result["band"] = band
    result["explanation"] = (
        f"|d| = {abs_d:.2f} is {band} for {field}. "
        + (
            "An effect this large is unusual and worth reporting so a reader can judge "
            "it, but it is NOT evidence of misconduct -- real large effects exist. The "
            "three ordinary explanations to rule out first are: dispersion reported as "
            "SEM and read as SD (inflates d by sqrt(n)), a waitlist rather than active "
            "comparator, and a units or scale mismatch between groups."
            if result["severity"] == "suspicious" else
            "Reported for context."
        )
    )
    result["methodology"] = (
        f"Compared |d| against empirical benchmarks for {field}. "
        f"Source: {bench['source']} "
        "These are distributions of PUBLISHED effects, themselves inflated by "
        "publication bias, so an effect at the 95th percentile of the published "
        "literature is more unusual still relative to the underlying truth. Severity "
        "is capped at `suspicious`: an effect size can be improbable but never "
        "arithmetically impossible."
    )
    return result


def available_fields() -> list[str]:
    """Fields with a benchmark, for the caller to choose from."""
    return sorted(FIELD_BENCHMARKS)


#: Correlations a within-subjects design plausibly produces. Not a prior --
#: a RANGE, deliberately wide at both ends, because the whole point is to
#: report what is attainable rather than to pick a value. 0.95 is included
#: because high test-retest correlations are exactly why people run paired
#: designs, and it is the end that moves the answer most.
PAIRED_R_GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)


def paired_d_interval(dz: float | None = None,
                      t: float | None = None,
                      n: int | None = None,
                      r: float | None = None,
                      r_grid: tuple[float, ...] = PAIRED_R_GRID) -> dict:
    """What a within-subjects d could be, when the correlation is unreported.

    WHAT IT COMPUTES, and the label was wrong for one day. A paired design
    reports `d_z` -- the difference over the SD OF THE DIFFERENCES -- and a
    reader comparing it against a between-subjects literature wants a raw-SD
    effect size. The closed form is

        d_rm = d_z * sqrt(2 * (1 - r))                    [Lakens 2013 eq. 8]

    and that is **d_rm**, not d_av. The two coincide only when the pre and post
    SDs are equal. `d_av = M_diff / ((SD1 + SD2) / 2)` additionally needs the SD
    RATIO, which this tool neither takes nor can infer from d_z and r.

    MEASURED 2026-08-27, 300,000 pairs per cell, against empirical d_av and
    d_rm computed from the data:

        sd2/sd1   r=0.3 err vs d_av   r=0.8 err vs d_av
          1.0            0.2%               0.1%
          2.0            9.0%              29.3%
          3.0           17.3%              44.5%

    It tracks d_rm to Monte-Carlo noise at every ratio. This function shipped on
    2026-08-26 naming its outputs `d_av`, with an assumptions card asserting the
    exact inverse ("Unequal SDs make d_av the quantity this returns and d_rm
    slightly different") and a regression test that fixed sd1 == sd2 -- the one
    condition under which the two are the same number. The test could not have
    caught it.

    and papers reporting `d_z` almost never report `r`. `recalc_within_subjects_t`
    RECOVERS r when the pre and post SDs are both printed, and that is strictly
    better; this is for the case where they are not, and the honest answer is an
    interval rather than a number.

    The discipline is the one `recalc_within_subjects_t` already applies to a
    thresholded p-value: when an input is a bound rather than a value, report
    the whole attainable range and refuse to pick a point inside it. Choosing
    r = 0.5 silently -- which is what an unstated assumption amounts to -- is
    the "within 15 per cent" tolerance that appeared in this project's own
    reasoning with no author and no trace.

    DIRECTION, because it is easy to invert and a published R package has:
    d_av SHRINKS as r rises. A high correlation makes the paired test efficient,
    so `d_z` is large while the raw-SD effect is not. At r = 0.9 the factor is
    sqrt(0.2) = 0.447. VERIFIED against a 200,000-pair simulation with known r
    while assessing `effectcheck` 0.7.7, whose `dav_from_dz` divides where it
    should multiply and so reports d_av = 2.82 where the truth is 0.28.

    DESCRIPTIVE BY EVIDENCE CLASS. It reports a property of what was printed and
    can never accuse: a wide interval means the paper did not say enough, which
    is a fact about the reporting and not about the work.
    """
    if dz is None:
        if t is None or not n:
            return {"error": "supply either dz, or t together with n",
                    "severity": "indeterminate"}
        if n < 2:
            return {"error": "n must be at least 2", "severity": "indeterminate"}
        dz = float(t) / math.sqrt(float(n))
    dz = float(dz)
    if not math.isfinite(dz):
        return {"error": "dz is not finite", "severity": "indeterminate"}

    def d_rm(rho: float) -> float:
        return dz * math.sqrt(2.0 * (1.0 - rho))

    if r is not None:
        rho = float(r)
        if not (-1.0 < rho < 1.0):
            return {"error": "r must lie strictly between -1 and 1",
                    "severity": "indeterminate"}
        value = d_rm(rho)
        return {
            "dz": dz, "r": rho, "d_rm": value,
            "d_rm_low": value, "d_rm_high": value,
            "r_is_reported": True,
            "interval_width": 0.0,
            "severity": "indeterminate",
            "note": ("r was supplied, so d_rm is determined. d_av is NOT: it also "
                     "needs the SD ratio, which this tool does not take."),
        }

    grid = tuple(sorted(float(x) for x in r_grid if -1.0 < float(x) < 1.0))
    if not grid:
        return {"error": "r_grid contains no correlation in (-1, 1)",
                "severity": "indeterminate"}
    values = [d_rm(rho) for rho in grid]
    low, high = min(values), max(values)
    return {
        "dz": dz,
        "r_is_reported": False,
        "r_grid": list(grid),
        "d_rm_low": low,
        "d_rm_high": high,
        "d_rm_at_r": {f"{rho:g}": d_rm(rho) for rho in grid},
        "interval_width": high - low,
        "ratio_high_to_low": (high / low) if low > 0 else None,
        "severity": "indeterminate",
        "note": (
            f"The paper reports d_z = {dz:.4g} and no pre-post correlation, so "
            f"d_rm is not determined: across r in [{grid[0]:g}, {grid[-1]:g}] it "
            f"ranges from {low:.4g} to {high:.4g}. Quote the interval, not a "
            "point. This is d_rm, NOT d_av -- d_av also needs the SD ratio, "
            "which this tool does not take. If the pre and post SDs are both printed, "
            "`recalc_within_subjects_t` recovers r and this refusal is "
            "unnecessary."
        ),
    }
