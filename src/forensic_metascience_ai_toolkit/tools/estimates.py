"""Effect estimates and confidence intervals: reconciliation and absence-of-evidence.

WHY THIS EXISTS
---------------
Two measured facts about the corpus drove this module:

* **353 estimate-with-95%-CI triples across the corpora, and zero tools accepted
  a CI.** Clinical papers report `OR 1.42 (1.08-1.87)`, not `t(28) = 2.10`. The
  entire toolkit was blind to the modal way clinical results are stated.
* **30.6% of papers assert an absence of effect somewhere.** "No significant
  difference" is routinely written as though it established no difference. A CI
  tells you whether the data could distinguish the two, and usually it could not.

Both checks are DETERMINISTIC arithmetic on numbers the paper published, and
neither accuses anyone of anything. `check_estimate_ci` says the printed numbers
disagree with each other; `absence_of_evidence` says a stated conclusion outruns
the interval beneath it. That register survives scrutiny in a way a trust
verdict does not.

FALSE-POSITIVE DISCIPLINE
-------------------------
* **Ratio measures live on the log scale.** An odds/risk/hazard ratio has a
  symmetric CI in log space, never in linear space. Testing linear symmetry on a
  ratio flags every correctly-reported ratio in the literature.
* **The null is never guessed.** The null is 1 for a ratio and 0 for a
  difference, and an all-positive interval is compatible with both readings.
  When the measure is unstated or unrecognised, every null-dependent
  cross-check either tries BOTH readings or declines with a note -- it never
  silently assumes 0. (Measured before this rule: an unlabelled honest
  `OR 1.10 [0.85, 1.42], p = .72` was accused of a recovered p of 0.0000,
  because the recovery ran against null = 0; ~95% of honest unlabelled narrow
  ratio CIs with an honest p were accused.)
* **Confidence level is inferred, never assumed.** A "95% CI" that looks wrong is
  usually a 90% or 99% CI. We test the plausible levels before reporting a
  discrepancy.
* **Rounding dominates at published precision.** Tolerances derive from the
  printed decimals, not from a fixed epsilon.
* **No SESOI, no equivalence claim.** Without a smallest effect size of interest
  we report the interval and refuse to rule anything in or out.
"""
from __future__ import annotations

import math

from scipy import stats

from . import rounding as _rounding
from ..survey_design import COMPLEX_SURVEY, canonical_sampling

RATIO_MEASURES = {
    "or", "odds_ratio", "rr", "risk_ratio", "relative_risk", "hr", "hazard_ratio",
    "irr", "incidence_rate_ratio", "rate_ratio", "ratio",
    # Common single-token abbreviations of adjusted ratios. Before these (and
    # the prefix stripping below), "aOR" fell through as unrecognised and the
    # null silently defaulted to 0 -- see `_normalise_measure`.
    "aor", "ahr", "airr", "prevalence_ratio",
}
DIFFERENCE_MEASURES = {
    "md", "mean_difference", "mean_diff", "smd", "cohens_d", "hedges_g", "d",
    "beta", "coefficient", "rd", "risk_difference", "difference",
}

#: Leading tokens that modify a measure without changing its scale or null.
#: "adjusted odds ratio" is still an odds ratio. "log" is deliberately NOT
#: here: a log-odds-ratio is a DIFFERENCE (null 0), not a ratio.
_MEASURE_PREFIX_TOKENS = {
    "adjusted", "adj", "unadjusted", "crude", "weighted", "pooled",
    "multivariable", "multivariate",
}

COMMON_LEVELS = (0.95, 0.90, 0.99, 0.80)


def _normalise_measure(measure) -> str:
    text = str(measure or "").strip().lower().replace("-", "_").replace(" ", "_")
    tokens = [t for t in text.split("_") if t]
    while tokens and tokens[0] in _MEASURE_PREFIX_TOKENS:
        tokens = tokens[1:]
    return "_".join(tokens)


def is_ratio_measure(measure: str | None) -> bool:
    return _normalise_measure(measure) in RATIO_MEASURES


def is_difference_measure(measure: str | None) -> bool:
    return _normalise_measure(measure) in DIFFERENCE_MEASURES


def _decimals(value) -> int:
    """Fallback decimals for a parsed float whose source literal is gone.

    Delegates to `rounding.decimals_of_value`, which errs toward the WIDER
    interval: an integral value reads as 0 dp (`5`, `5.0` and `5.00` are
    indistinguishable once parsed, and 0 dp is the only reading that cannot
    be too tight), and trailing zeros are unrecoverable, so `1.40` reads as
    1 dp. Both misreads LOOSEN the test -- a real discrepancy can be waved
    through, but correct rounding is never reported as a problem. (An earlier
    fallback read integers off `str()` as 1 dp -- ten times too TIGHT, the
    accusing direction: honest `OR 4 (1-9)`, the correct 0 dp rounding of
    3.6 (1.4-9.4), was reported suspicious. And `str(1e-08)` has no decimal
    point at all, so a reported p of 1e-8 read as 0 dp and earned a rounding
    slack of 0.5 -- no p could ever be flagged against it.) Callers that still
    have the source literal should pass `decimals` explicitly.
    """
    d = _rounding.decimals_of_value(value)
    return 0 if d is None else d


def _half_width(*values) -> float:
    """Rounding half-width implied by the coarsest printed value."""
    return _rounding.half_width(min(_decimals(v) for v in values))


def _refusal(reason: str) -> dict:
    """A stated refusal: not a finding, and not a statement about the paper."""
    return {
        "severity": "indeterminate",
        "problems": [],
        "explanation": (
            f"Not evaluated: {reason} This is a refusal, not a finding about the paper."
        ),
    }


#: CI methods that are NOT symmetric about the point estimate by construction.
#: The midpoint test assumes a Wald interval -- estimate +/- z*SE -- which is the
#: only method for which symmetry is exact.
#:
#: MEASURED before this: an incremental cost of 420 with a bootstrap CI of
#: [95, 910] returned `suspicious` ("the estimate is not the arithmetic
#: midpoint"), as did a profile-likelihood risk difference of 3.1 in [0.4, 8.9].
#: Neither is an error. Non-parametric bootstrap intervals are MANDATORY
#: practice for skewed cost data in health economics, and exact and
#: profile-likelihood intervals are routine in epidemiology.
#:
#: The registry's integrity card already DISCLOSED this exposure in prose --
#: "Exact, profile and bootstrap CIs are legitimately asymmetric and can fail
#: the midpoint check innocently" -- which is honest disclosure and not a guard.
_ASYMMETRIC_INTERVAL_METHODS = (
    "bootstrap", "bca", "bias_corrected", "bias-corrected", "percentile",
    "exact", "clopper", "pearson_clopper", "profile", "likelihood",
    "fieller", "wilson", "agresti", "jeffreys", "bayesian", "credible",
    "hpd", "posterior", "score",
)


def _interval_is_legitimately_asymmetric(method) -> bool:
    """Whether a declared CI method is asymmetric BY CONSTRUCTION.

    Undeclared returns False, which keeps the existing behaviour: the check
    still runs and still reports, because most papers do not name their method
    and silently dropping the test would lose a real transcription-error
    detector. What changes when it is undeclared is the WORDING -- the problem
    now names the innocent reading instead of asserting an inconsistency.
    """
    if not method:
        return False
    key = str(method).strip().lower().replace("-", "_").replace(" ", "_")
    return any(n.replace("-", "_") in key for n in _ASYMMETRIC_INTERVAL_METHODS)


def check_estimate_ci(
    estimate: float,
    ci_low: float,
    ci_high: float,
    measure: str | None = None,
    reported_p: float | None = None,
    reported_p_operator: str = "=",
    confidence_level: float | None = None,
    null_value: float | None = None,
    decimals: int | None = None,
    sampling: str = "simple_random",
    interval_method: str | None = None,
) -> dict:
    """Reconcile a point estimate against its own confidence interval.

    Checks, in order:
      1. the interval is ordered and contains the estimate;
      2. the estimate sits where the CI implies it should (midpoint on the
         correct scale);
      3. the p-value recovered from the CI agrees with the reported p;
      4. significance implied by the CI agrees with the reported p.

    `decimals` is the PRINTED precision of the coarsest of the three numbers,
    and every tolerance here derives from it. Pass it whenever the source
    literals are available: without it the precision is re-derived from the
    parsed floats, which errs toward the WIDER interval -- a bound printed
    `1.40` reads as 1 dp (looser) and one printed `5` reads as 0 dp (exact),
    so a real discrepancy can be waved through, but correctly-rounded values
    are never accused. See `_decimals` for the history: the old fallback read
    integers as 1 dp, ten times too TIGHT, which is the direction that
    manufactures accusations.

    Checks 3 and 4 need to know where the null is (1 for a ratio, 0 for a
    difference). When `measure` is unstated or unrecognised and `null_value`
    is not given, an all-positive interval does not determine it, so those
    checks are only asserted when BOTH readings agree -- or declined with a
    note. Guessing the null inverted honest results (see module docstring).

    `sampling` is the DESIGN the estimate came from. Under `complex_survey`
    this check becomes ONE-SIDED, and only in the p-vs-CI comparison: see
    `survey_design` for the measurement and the monotonicity argument. Briefly:
    the interval and the p come from one fit, the only free parameter is the
    design degrees of freedom, and p is monotone DECREASING in df -- so the
    normal-approximation recovery is the infimum of what p can be. A printed p
    ABOVE it is reachable at some df and says nothing about the paper; a printed
    p BELOW it is reachable at no df and still stands. The ordering, containment
    and midpoint checks are unaffected: they are algebra on the printed numbers
    and no design touches them.

    `reported_p_operator` carries the comparison the paper PRINTED: "=" for an
    exact p, "<"/"<=" for a threshold ("P < .001" -- the modal p format in
    clinical journals), ">"/">=" for the other side ("P > .99"). A threshold is
    an exact printed bound, not a rounded value, so it is tested as an interval
    claim: "p < x" is inconsistent only when NO p below x is reachable from the
    printed CI at the stated level, and unrescuable at any common level.
    Measured need: a paper's abstract-headline "ARR 0.185 (95% CI 0.046-0.748),
    P < .001" (CI-implied p = .018, an 18-fold gap) could not be expressed here
    at all -- the caller either dropped the p (check silently skipped, verdict
    `consistent`) or coerced it to `= .001` (rescued as a mislabelled 99% CI).
    Both defaults recorded the paper's strongest internal inconsistency as
    clean.

    `confidence_level` is the level the PAPER STATES, or None when it states
    none (then 95% is assumed). The distinction decides what a level rescue
    means. With no stated level, a p that reconciles only at another common
    level is read as a mislabelled interval and noted. With a STATED level it
    is not silently overridden: the result is `suspicious` with failure mode
    `reconciles_only_at_other_level`. MEASURED 2026-10-18 (Heymsfield 2021,
    10.1001/jamanetworkopen.2020.33457, later corrected to P = .10): estimate
    1.37, 80% CI 0.31-2.43, printed P = .01. At the stated 80% the interval
    gives p = .098; it came back `consistent` with the note "behaves like a
    95% CI, not the stated 80%" -- the paper's own erratum, cleared.
    """
    survey = canonical_sampling(sampling) == COMPLEX_SURVEY
    level_stated = confidence_level is not None
    failure_mode: str | None = None
    level_that_reconciles: float | None = None
    problems: list[str] = []
    notes: list[str] = []

    # --- input sanity: refusals, never findings ----------------------------
    cleaned: dict[str, float | None] = {}
    for name, value in (("estimate", estimate), ("ci_low", ci_low),
                        ("ci_high", ci_high), ("reported_p", reported_p),
                        ("confidence_level", confidence_level),
                        ("null_value", null_value)):
        if value is None:
            cleaned[name] = None
            continue
        try:
            f = float(value)
        except (TypeError, ValueError):
            return _refusal(f"{name}={value!r} is not a number.")
        if not math.isfinite(f):
            return _refusal(
                f"{name}={value!r} is not finite. NaN and infinity are what an "
                "extraction produces from an empty cell, a dash or a division by "
                "zero, not values a paper printed. Re-read the source value."
            )
        cleaned[name] = f
    estimate = cleaned["estimate"]
    ci_low = cleaned["ci_low"]
    ci_high = cleaned["ci_high"]
    reported_p = cleaned["reported_p"]
    confidence_level = (cleaned["confidence_level"] if level_stated else 0.95)
    null_value = cleaned["null_value"]

    if not 0.0 < confidence_level < 1.0:
        return _refusal(
            f"confidence_level={confidence_level:g} is not a fraction in (0, 1). "
            "Pass e.g. 0.95, not 95."
        )

    # The operator is part of the CLAIM, so an unrecognised one is refused, not
    # defaulted: silently reading "≪" or "~" as "=" would judge a claim the
    # paper never made.
    op = str(reported_p_operator or "=").strip().replace("≤", "<=").replace("≥", ">=")
    if op not in ("=", "<", "<=", ">", ">="):
        return _refusal(
            f"reported_p_operator={reported_p_operator!r} is not one of "
            "'=', '<', '<=', '>', '>='."
        )
    if op != "=" and reported_p is None:
        return _refusal(
            f"reported_p_operator={op!r} was passed without reported_p; a "
            "threshold claim needs its bound. Pass reported_p as the printed "
            "threshold (e.g. reported_p=0.001 for 'P < .001')."
        )
    if op != "=" and reported_p is not None and not 0.0 < reported_p <= 1.0:
        return _refusal(
            f"reported_p={reported_p:g} with operator {op!r} is not a p-value "
            "threshold in (0, 1]."
        )

    if ci_low > ci_high:
        return {
            "severity": "indeterminate",
            "problems": [],
            "explanation": (
                f"CI bounds arrive reversed: [{ci_low}, {ci_high}]. Transposed bounds "
                "are at least as often an extraction error on our side as a defect in "
                "the paper, so nothing is judged. Re-read the source and call again "
                "with the bounds in order."
            ),
        }

    ratio = is_ratio_measure(measure)
    difference = is_difference_measure(measure)
    if ratio and (ci_low <= 0 or estimate <= 0):
        return {
            "severity": "indeterminate",
            "problems": [],
            "explanation": (
                f"Measure '{measure}' is a ratio but the estimate or lower bound is "
                "non-positive, so the log scale is undefined. Cannot evaluate."
            ),
        }
    if ratio and null_value is not None and null_value <= 0:
        return _refusal(
            f"measure '{measure}' is a ratio but null_value={null_value:g} is "
            "non-positive, so the log scale is undefined at the null."
        )
    tol = (_rounding.half_width(decimals) if decimals is not None
           else _half_width(estimate, ci_low, ci_high))

    # SCALE INFERENCE. When the caller does not name the measure, the scale is
    # ambiguous -- and assuming linear flags every correctly-reported odds / risk
    # / hazard ratio, whose CI is symmetric in LOG space, not linear (verified:
    # an unlabelled OR = 1.5, CI [0.9, 2.5] -- 1.5 IS the geometric midpoint --
    # returned `suspicious`, "not the arithmetic midpoint (expected 1.70)"). So
    # when the measure is neither a recognised ratio NOR a recognised difference
    # (a stated MD must never be silently re-scaled), try BOTH scales and adopt
    # log ONLY if the estimate matches the geometric midpoint and NOT the
    # arithmetic one -- the same "try both conventions before accusing" rule
    # SPRITE and GRIM use. A genuine linear estimate fits the arithmetic midpoint
    # and never flips; a mislabelled or unrecognised ratio (SMR, "OR (fully
    # adjusted)") is rescued from a false accusation.
    scale_inferred = False
    if (not ratio and not difference and ci_low > 0 and estimate > 0
            and (null_value is None or null_value > 0)):
        arith_c = (ci_low + ci_high) / 2
        geo_c = math.exp((math.log(ci_low) + math.log(ci_high)) / 2)
        fits_linear = abs(estimate - arith_c) <= max(3 * tol, 0.10 * abs(arith_c))
        fits_log = abs(estimate - geo_c) <= max(3 * tol, 0.10 * abs(geo_c))
        if fits_log and not fits_linear:
            ratio = True
            scale_inferred = True

    # Is the null actually KNOWN, or would it be a guess? Known when the caller
    # passed it, when the measure is recognised on either side, when the data
    # settle it (a negative value cannot belong to a ratio), or when the scale
    # was inferred from the midpoint (disclosed in a note below).
    null_known = (
        null_value is not None or ratio or difference or scale_inferred
        or ci_low < 0 or estimate < 0
    )
    if null_value is None:
        null_value = 1.0 if ratio else 0.0

    if scale_inferred:
        notes.append(
            "measure not stated; the estimate sits at the GEOMETRIC midpoint of its "
            "CI, so it was evaluated as a ratio (log scale). Pass `measure` to remove "
            "the guess."
        )

    # --- containment --------------------------------------------------------
    # The estimate and each bound round INDEPENDENTLY, and their printed
    # precisions can differ, so the honest worst case is one half-width on each
    # side: est printed 2.95 (2 dp) against a bound printed 2.9 (1 dp) is the
    # correct rounding of 2.9451 <= 2.949, and the old single-half-width slack
    # accused it. The cost is that an estimate exactly ONE last-digit step
    # outside its bound is no longer flagged here (the midpoint check below
    # still catches all but the narrowest intervals).
    contain_slack = 2 * tol + _rounding.EPSILON
    if not (ci_low - contain_slack <= estimate <= ci_high + contain_slack):
        problems.append(
            f"the estimate {estimate} lies outside its own CI [{ci_low}, {ci_high}]"
        )

    # --- symmetry on the correct scale -------------------------------------
    #
    # A LOWER BOUND OF ZERO MAKES THE SYMMETRY TEST INAPPLICABLE, NOT FAILED.
    # A ratio's CI is symmetric in LOG space and log(0) does not exist, so a
    # sparse-data interval printed as `OR 0.01 (0.00 to 32.53)` has no geometric
    # centre at all. The code fell through to the ARITHMETIC midpoint -- 16.27 --
    # and reported the paper's 0.01 as grossly asymmetric.
    #
    # Those intervals are ordinary. A zero lower bound is what a zero-cell or
    # quasi-separated contingency table produces, and rounding 0.0001 to `0.00`
    # at two decimals is honest reporting. MEASURED over a harness-fired sweep
    # of 2,113 checks across 87 corpus papers: 13 of the 21 accusatory flags
    # were this exact shape, every one a false positive, all with ci_low == 0.
    #
    # AND THE RESCUE WAS GATED ON THE SAME CONDITION. The scale inference above
    # requires `ci_low > 0`, so a sparse ratio could never be recognised as a
    # ratio -- the one circumstance that makes the log scale untestable also
    # disabled the code that would have chosen it. Hence `not difference`
    # rather than `ratio`: absent a STATED difference, the scale is unknown and
    # the test must not run.
    #
    # CONTAINMENT ABOVE STILL RUNS, and it is the half worth keeping: "the
    # estimate lies outside its own CI" is scale-free and remains checkable.
    if ci_low <= 0 and not difference:
        # A NOTE, not a problem: this is a refusal to test, and the refusal is
        # the correct output. Appending to `problems` would turn our inability
        # to pick a scale into an allegation about the paper.
        notes.append(
            f"the lower bound is {ci_low}, so no scale for this interval can be "
            "established: a ratio's CI has no geometric centre when a bound is "
            "zero (log 0 is undefined), and the measure was not stated to be a "
            "difference. A zero bound is the ordinary output of a sparse or "
            "zero-cell table, not an anomaly. Containment was still checked; "
            "pass `measure` if the symmetry test should run."
        )
        centre = scale_note = None
    elif ratio:
        centre = math.exp((math.log(ci_low) + math.log(ci_high)) / 2)
        scale_note = "geometric midpoint (ratios are symmetric on the log scale)"
    else:
        centre = (ci_low + ci_high) / 2
        scale_note = "arithmetic midpoint"
    asym = None if centre is None else abs(estimate - centre)
    # An unadjusted estimate reported with an adjusted CI (or vice versa) is
    # common and legitimate, so only a gross mismatch is reported.
    if asym is not None and asym > max(3 * tol, 0.10 * abs(centre)):
        # Is the paper simply using the OTHER scale?
        other = ((ci_low + ci_high) / 2) if ratio else None
        if other is not None and abs(estimate - other) <= max(3 * tol, 0.02 * abs(other)):
            problems.append(
                f"the estimate {estimate} is the ARITHMETIC midpoint of [{ci_low}, {ci_high}], "
                f"but '{measure}' is a ratio whose CI should be symmetric on the log scale "
                f"(geometric midpoint {centre:.4f})"
            )
        elif _interval_is_legitimately_asymmetric(interval_method):
            # DECLARED, AND ASYMMETRIC BY CONSTRUCTION. Nothing happened.
            notes.append(
                f"the midpoint test was not run: a {interval_method} interval "
                f"is not symmetric about its estimate by construction, so the "
                f"offset carries no information")
        else:
            problems.append(
                f"the estimate {estimate} is not the {scale_note} of [{ci_low}, {ci_high}] "
                f"(expected about {centre:.4f})"
                + ("" if interval_method else
                   " -- note that bootstrap, exact, profile-likelihood, "
                   "bias-corrected and Fieller intervals are all legitimately "
                   "asymmetric, and this paper does not say which method it "
                   "used, so confirm the method before treating this as a "
                   "finding")
            )

    # --- recover SE and p ---------------------------------------------------
    z_crit = stats.norm.ppf(1 - (1 - confidence_level) / 2)
    if ratio:
        se = (math.log(ci_high) - math.log(ci_low)) / (2 * z_crit)
    else:
        se = (ci_high - ci_low) / (2 * z_crit)
    width_ok = se > 0
    # The recovered p and z depend on WHERE THE NULL IS. With the null unknown
    # they would be guesses, and with a zero-width interval the recovery divides
    # by zero -- either way, publishing a number here publishes our failure as a
    # fact about the paper, so the fields go out as None instead.
    if width_ok and null_known:
        if ratio:
            z_stat = (math.log(estimate) - math.log(null_value)) / se
        else:
            z_stat = (estimate - null_value) / se
        recovered_p = 2 * (1 - stats.norm.cdf(abs(z_stat)))
    else:
        z_stat = None
        recovered_p = None

    inferred_level = None
    p_checked = False
    if reported_p is not None:
        tol_p = _p_tolerance(reported_p)
        if not width_ok:
            # A CI whose printed bounds are EQUAL has no width, so the recovery
            # divides by zero. "RR 1.0 (1.0-1.0), p = .32" is the ordinary
            # large-N table pattern (honest at RR 1.002, 0.998-1.006), and at
            # that printed precision the reachable p is essentially the whole
            # unit interval: the check has no power, so it must say so.
            notes.append(
                f"p not cross-checked: the printed interval [{ci_low}, {ci_high}] has zero "
                "width at this precision, so the recovered p is undefined and any value is "
                "reachable. Report the bounds to more decimals to make this checkable."
            )
        elif not null_known and op != "=":
            # A threshold claim ("p < x") under an UNSTATED measure is declined
            # outright rather than routed through the point logic below: that
            # logic tests reachability of x itself, and a reachable p far BELOW
            # the threshold -- which satisfies "p < x" honestly -- would read
            # as unreachable and accuse. Two unknowns (null and side) stack;
            # refuse and ask for the measure.
            notes.append(
                f"p not cross-checked: the reported p is a threshold claim "
                f"('p {op} {reported_p}') and the measure was not stated, so "
                "the null is unknown. Pass `measure` to pin the reading."
            )
        elif not null_known:
            # THE NULL IS NOT A GUESSABLE INPUT. An all-positive interval is
            # compatible with a ratio (null 1) and a difference (null 0), and
            # the two recoveries differ wildly -- the old code assumed 0 and
            # accused ~95% of honest unlabelled narrow ratio CIs carrying an
            # honest p (measured). So: recover p under BOTH readings, accuse
            # only when the reported p is unreachable under EITHER, and decline
            # with a note when the readings disagree.
            candidates = [("difference reading, null 0", False, 0.0)]
            if ci_low > 0 and estimate > 0:
                candidates.append(("ratio reading, null 1", True, 1.0))
            spans, fails = [], []
            for label, c_ratio, c_null in candidates:
                plo, phi = _recovered_p_interval(
                    estimate, ci_low, ci_high, confidence_level, c_ratio, c_null,
                    decimals)
                spans.append(f"{label}: [{plo:.4f}, {phi:.4f}]")
                # A reading fails only if the reported p is unreachable at
                # EVERY common confidence level under it. The labelled path
                # gets a mislabelled-level rescue below; the unlabelled path
                # must not be harsher than the labelled one (measured: p = .34
                # on an unlabelled OR CI was accused where the labelled call
                # rescued it as a 99% reading).
                # A STATED level is not swapped for a common one that happens
                # to reconcile (see the docstring); an unstated one may be.
                fails.append(all(
                    (reported_p + tol_p < a) or (reported_p - tol_p > b)
                    for a, b in (
                        _recovered_p_interval(estimate, ci_low, ci_high, lv,
                                              c_ratio, c_null, decimals)
                        for lv in ((confidence_level,) if level_stated
                                   else COMMON_LEVELS)
                    )
                ))
            span_text = "; ".join(spans)
            if len(candidates) == 2 and all(fails):
                p_checked = True
                problems.append(
                    f"the reported p = {reported_p} cannot be recovered from the "
                    f"printed estimate and interval under EITHER reading of the "
                    f"unstated measure, at "
                    + (f"the stated {confidence_level:.0%} confidence level"
                       if level_stated else
                       "the assumed 95% or any common confidence level")
                    + f" (at that level: {span_text})"
                )
                if level_stated:
                    failure_mode = "p_unreachable_at_stated_level"
            elif any(fails):
                notes.append(
                    f"p not cross-checked: the measure was not stated, and the two "
                    f"possible readings disagree about the reported p = {reported_p} "
                    f"({span_text}). Pass `measure` to pin the reading."
                )
            else:
                p_checked = True
                notes.append(
                    f"measure not stated; the reported p is reachable under "
                    f"{'both readings' if len(candidates) == 2 else 'the only viable reading'} "
                    f"({span_text}). Pass `measure` to make this exact."
                )
        elif op != "=":
            # A THRESHOLD CLAIM IS AN INTERVAL, NOT A ROUNDED POINT. "p < .001"
            # asserts every p in (0, .001); the printed bound is exact, so the
            # claim gets no rounding slack of its own -- the slack lives in the
            # reachable-p interval, which already spans the printed precision
            # of the estimate and both bounds. Consistent iff the claim
            # interval intersects the reachable interval at the stated level.
            # Otherwise try the ONE common level that could still rescue it --
            # the recovered p falls as the level rises, so a "<" claim is
            # rescuable only at the highest common level and a ">" claim only
            # at the lowest -- before flagging. Measured: "ARR 0.185
            # (0.046-0.748), P < .001" recovers p = .018 at the stated 95% and
            # .0018 at 99% -- below .001 at NO common level -- yet both
            # encodings previously available ("= .001", or dropping the p)
            # recorded the paper's strongest internal inconsistency as clean.
            lt = op in ("<", "<=")
            result_p_lo, result_p_hi = _recovered_p_interval(
                estimate, ci_low, ci_high, confidence_level, ratio, null_value,
                decimals)
            outside = (
                (result_p_lo > reported_p + _rounding.EPSILON) if lt
                else (result_p_hi < reported_p - _rounding.EPSILON)
            )
            rescued = False
            rescue_level = max(COMMON_LEVELS) if lt else min(COMMON_LEVELS)
            stated_level_overridden = False
            if outside and rescue_level != confidence_level:
                b_lo, b_hi = _recovered_p_interval(
                    estimate, ci_low, ci_high, rescue_level, ratio, null_value,
                    decimals)
                rescued = (
                    (b_lo <= reported_p + _rounding.EPSILON) if lt
                    else (b_hi >= reported_p - _rounding.EPSILON)
                )
            p_checked = True
            if rescued and level_stated:
                # A STATED level is not overridden by the one that reconciles.
                stated_level_overridden = True
                failure_mode = "reconciles_only_at_other_level"
                level_that_reconciles = rescue_level
                problems.append(
                    f"the reported 'p {op} {reported_p}' is unreachable at the "
                    f"STATED {confidence_level:.0%} confidence level (recoverable "
                    f"p [{result_p_lo:.4f}, {result_p_hi:.4f}]); it reconciles only "
                    f"if the interval is a {rescue_level:.0%} CI, which is not "
                    "what the paper says. Either the level, the interval or the "
                    "p is misreported"
                )
            elif rescued:
                inferred_level = rescue_level
                notes.append(
                    f"the reported 'p {op} {reported_p}' is unreachable at the "
                    f"assumed {confidence_level:.0%} level but reachable if the "
                    f"interval is a {rescue_level:.0%} CI — check the reported "
                    "level"
                )
            elif outside:
                problems.append(
                    f"the paper reports p {op} {reported_p}, but the p "
                    f"recoverable from the printed interval at the stated "
                    f"{confidence_level:.0%} level is "
                    f"[{result_p_lo:.4f}, {result_p_hi:.4f}], and no common "
                    f"confidence level reaches {'below' if lt else 'above'} "
                    "the claimed bound"
                )
                # The reader-visible reading. A threshold at or beyond alpha
                # pins the claimed side exactly (the bound is printed exact,
                # so no rounding straddle applies), and the same gating as the
                # exact-p path holds: this fires only when the interval test
                # above has already failed, so it is one comparison read two
                # ways, not a second independent finding.
                alpha = 1 - confidence_level
                ci_excludes_null = not (ci_low <= null_value <= ci_high)
                if stated_level_overridden:
                    pass
                elif (lt and reported_p <= alpha + _rounding.EPSILON
                        and not ci_excludes_null):
                    problems.append(
                        f"the CI includes the null ({null_value}), but the "
                        f"reported p {op} {reported_p} says the result is "
                        "significant"
                    )
                elif (not lt and reported_p >= alpha - _rounding.EPSILON
                        and ci_excludes_null):
                    problems.append(
                        f"the CI excludes the null ({null_value}), but the "
                        f"reported p {op} {reported_p} says the result is "
                        "not significant"
                    )
        else:
            # A "wrong" p is usually a different confidence level; test before
            # flagging.
            best = min(
                COMMON_LEVELS,
                key=lambda lv: abs(_p_from_ci(estimate, ci_low, ci_high, lv, ratio,
                                              null_value) - reported_p),
            )
            # THE RECOVERED p IS AN INTERVAL, NOT A POINT. It is computed from
            # three values the paper ROUNDED, and the coarser they are printed
            # the wider the reachable p. A true estimate of 0.54 with SE 0.22
            # gives p = .0141 and a CI of (0.1088, 0.9712); printed at 1 dp that
            # is "0.5 [0.1, 1.0], p = .014", from which the point recovery
            # returns .0294 -- and the honest report was flagged. Across the
            # printed rounding box the reachable p spans roughly [.007, .078],
            # which contains .014. Same interval-vs-interval rule as the rest of
            # the toolkit; `_p_tolerance` is kept as an additive floor so
            # nothing the old window accepted is newly accused.
            result_p_lo, result_p_hi = _recovered_p_interval(
                estimate, ci_low, ci_high, confidence_level, ratio, null_value,
                decimals)
            outside = (reported_p + tol_p < result_p_lo) or (reported_p - tol_p > result_p_hi)
            # The LEVEL inference is judged on the reachable interval AT the
            # candidate level, not on a flat window around its point recovery.
            # The flat +/-0.005 window rescued ANY sufficiently small p: with a
            # CI whose 99%-level recovery is .001, a reported p of 1e-8 -- five
            # orders of magnitude below anything the interval can produce at any
            # level -- was waved through as "behaves like a 99% CI" (measured).
            # The interval test keeps every honest rescue (a mislabelled 90% or
            # Bonferroni-adjusted CI reconciles within rounding of its true
            # level) while the order-of-magnitude guard below refuses to launder
            # a p the interval cannot reach at ANY common level.
            point_off = abs(recovered_p - reported_p) > tol_p
            rescued = False
            if point_off and best != confidence_level:
                b_lo, b_hi = _recovered_p_interval(
                    estimate, ci_low, ci_high, best, ratio, null_value, decimals)
                tol_rescue = max(tol_p, 0.005)
                rescued = (
                    b_lo - tol_rescue - _rounding.EPSILON <= reported_p
                    <= b_hi + tol_rescue + _rounding.EPSILON
                    # Within an order of magnitude of what the level can reach:
                    # additive slack alone is meaningless for p's near zero.
                    and reported_p >= b_lo / 10
                )
            # THE ONE-SIDED GATE. Only the direction a survey design cannot
            # produce survives; see this function's docstring and
            # `survey_design`. Placed here rather than at the top so the
            # ordering, containment and midpoint checks above still run --
            # those are algebra on printed numbers and no design touches them.
            if (survey and recovered_p is not None
                    and reported_p > recovered_p):
                p_checked = False
                notes.append(
                    f"the p recovered from this interval is {recovered_p:.4f} and "
                    f"p = {reported_p} is printed, but the analysis is declared "
                    "COMPLEX SURVEY: a design-based interval uses a t with the "
                    "survey degrees of freedom, and p is monotone decreasing in "
                    "df, so the normal-approximation recovery is a LOWER BOUND. "
                    "A printed p above it is reachable at some df and carries no "
                    "information. Not evaluated. (A printed p BELOW the recovery "
                    "would still be flagged -- no df reaches it.)"
                )
            elif rescued and level_stated:
                # A STATED level is not overridden by the one that reconciles:
                # the paper said which interval it printed, and the p does not
                # fit it. Heymsfield 2021 (see the docstring) was cleared here.
                p_checked = True
                failure_mode = "reconciles_only_at_other_level"
                level_that_reconciles = best
                problems.append(
                    f"the p-value recovered from the STATED {confidence_level:.0%} "
                    f"CI is {recovered_p:.4f} (reachable range [{result_p_lo:.4f}, "
                    f"{result_p_hi:.4f}]), but p = {reported_p} is reported; the "
                    f"two reconcile only if the interval is a {best:.0%} CI, which "
                    "is not what the paper says. Either the level, the interval or "
                    "the p is misreported"
                )
            elif rescued:
                inferred_level = best
                p_checked = True
                notes.append(
                    f"the interval behaves like a {best:.0%} CI, not the assumed "
                    f"{confidence_level:.0%} (no level was stated) — check the "
                    "reported level"
                )
            elif outside and _interval_is_legitimately_asymmetric(interval_method):
                # THE RECOVERY IS A WALD INVERSION, and this interval is not a
                # Wald interval. `se = (ln hi - ln lo) / (2z)` reconstructs the
                # standard error by assuming the bounds sit z errors either side
                # of the estimate on the log scale -- true of a Wald interval
                # and of no other kind. Against a bootstrap, exact,
                # profile-likelihood or Fieller interval the recovered p is a
                # quantity the paper never computed, so a disagreement with the
                # reported p is our arithmetic, not their error.
                #
                # THE MIDPOINT TEST ALREADY RESPECTED `interval_method` AND THIS
                # ONE DID NOT, which is my own omission from the same commit:
                # I guarded the branch the audit pointed at and left its
                # neighbour, which rests on exactly the same assumption.
                p_checked = True
                notes.append(
                    f"the recovered-p check was not run: reconstructing the "
                    f"standard error from the bounds assumes a Wald interval, "
                    f"and a {interval_method} interval is not one")
            elif outside:
                p_checked = True
                problems.append(
                    f"the p-value recovered from the CI is {recovered_p:.4f} (reachable "
                    f"range [{result_p_lo:.4f}, {result_p_hi:.4f}] across the printed "
                    f"precision of the estimate and its bounds), but p = {reported_p} "
                    "is reported"
                    + ("" if interval_method else
                       " -- this recovery inverts a WALD interval, so if the "
                       "paper used a bootstrap, exact, profile-likelihood or "
                       "Fieller interval the two numbers are not comparable; "
                       "confirm the method before treating this as a finding")
                )
            else:
                p_checked = True

            # Significance disagreement is the version a reader would notice.
            #
            # BUT A p PRINTED AT alpha CLASSIFIES NOTHING. "p = .05" asserts the
            # interval [.045, .055], which straddles alpha = .05: at its own
            # printed precision the paper has not said which side of the line it
            # falls on, and neither has a CI whose bound prints as exactly the
            # null. A wholly coherent triple -- log-OR 0.40, SE 0.206, giving
            # p = .0522 and a CI of (0.9962, 2.2339), printed "OR 1.49 [1.00,
            # 2.24], p = .05" -- was reported `suspicious` here. Worse, the
            # branch fired only because `0.05 < (1 - 0.95)` is True by
            # floating-point noise, so the mirror case was passing by luck
            # rather than by reasoning.
            #
            # Decline to classify when the reported p cannot be placed against
            # alpha at its own precision. That is a refusal on ONE branch, not a
            # softening: a p clearly on either side is still cross-checked, and
            # the comparison is epsilon-guarded so it no longer turns on float
            # representation.
            alpha = 1 - confidence_level
            # Inferred from the p LITERAL, never from `decimals`: that argument
            # is the printed precision of the estimate and its interval, and a
            # CI given to 2 dp says nothing about how many digits the p was
            # printed to.
            _dp = _rounding.decimals_of_value(reported_p)
            half_p = _rounding.half_width(0 if _dp is None else _dp)
            ci_excludes_null = not (ci_low <= null_value <= ci_high)
            p_significant = reported_p < alpha - _rounding.EPSILON
            if abs(reported_p - alpha) <= half_p + _rounding.EPSILON:
                notes.append(
                    f"Significance not cross-checked: the reported p = {reported_p} lies "
                    f"within its own printed rounding interval of alpha = {alpha:g}, so it "
                    "does not determine which side of the threshold the result falls on."
                )
            elif (outside and ci_excludes_null != p_significant and inferred_level is None
                  and failure_mode != "reconciles_only_at_other_level"):
                # `outside` gates this too. Null-exclusion and "p < alpha" are
                # two readings of ONE comparison, so once the interval test has
                # found the reported p reachable from the printed interval, a
                # disagreement between the two booleans is a boundary-rounding
                # artefact rather than a second, independent finding.
                problems.append(
                    f"the CI {'excludes' if ci_excludes_null else 'includes'} the null "
                    f"({null_value}), but the reported p = {reported_p} says the result is "
                    f"{'significant' if p_significant else 'not significant'}"
                )

    if not null_known and reported_p is None:
        notes.append(
            "measure not stated and the interval is compatible with both a ratio "
            "(null 1) and a difference (null 0) reading; null-dependent outputs "
            "(recovered p and z, null exclusion) were not evaluated. Pass `measure`."
        )

    severity = "suspicious" if problems else "consistent"
    consistent_text = (
        f"Estimate, CI{' and p' if p_checked else ''} are mutually consistent."
        + ("" if reported_p is None or p_checked
           else " The reported p was not cross-checked; see notes.")
    )
    return {
        "severity": severity,
        "problems": problems,
        "notes": notes,
        "recovered_se": se,
        "recovered_p": float(recovered_p) if recovered_p is not None else None,
        "recovered_z": float(z_stat) if z_stat is not None else None,
        "implied_centre": centre,
        "scale": "log" if ratio else "linear",
        "inferred_confidence_level": inferred_level,
        "confidence_level": confidence_level,
        "confidence_level_stated": level_stated,
        **({"failure_mode": failure_mode,
            "level_that_reconciles": level_that_reconciles}
           if failure_mode else {}),
        "ci_excludes_null": (
            (not (ci_low <= null_value <= ci_high)) if null_known else None
        ),
        "explanation": "; ".join(problems) if problems else consistent_text,
        "methodology": (
            f"SE recovered from the CI width on the {'log' if ratio else 'linear'} scale; "
            "p recovered by a normal approximation. Tolerances derive from the printed "
            "precision. Alternative confidence levels are tested before any discrepancy is "
            "reported. Null-dependent checks run only when the null is known (stated "
            "measure, stated null, or settled by the data); otherwise both readings must "
            "agree before anything is flagged."
        ),
    }


def _p_from_ci(estimate, lo, hi, level, ratio, null_value) -> float:
    """Recover a two-sided p from an estimate and its interval, or NaN.

    NaN when the interval has no width: the recovery divides by the SE the width
    implies, and 0/0 yields a NaN whose numpy warning used to escape here, while
    a non-zero numerator yielded an infinity that printed as "recovered p =
    0.0000". Both are OUR arithmetic failing on an unusable input, and the
    caller must be able to tell that apart from a real recovered value.
    """
    z_crit = stats.norm.ppf(1 - (1 - level) / 2)
    try:
        if ratio:
            se = (math.log(hi) - math.log(lo)) / (2 * z_crit)
            if se <= 0:
                return float("nan")
            z = (math.log(estimate) - math.log(null_value)) / se
        else:
            se = (hi - lo) / (2 * z_crit)
            if se <= 0:
                return float("nan")
            z = (estimate - null_value) / se
    except (ValueError, ZeroDivisionError):
        return float("nan")
    return 2 * (1 - stats.norm.cdf(abs(z)))


def _recovered_p_interval(estimate, lo, hi, level, ratio, null_value,
                          decimals=None) -> tuple[float, float]:
    """Range of p recoverable from the PRINTED estimate and interval.

    The recovery divides by the interval's width and measures the estimate's
    distance from the null, so it is sensitive to the rounding of all three
    values -- and most sensitive exactly when they are printed coarsely, which
    is when the point recovery is least trustworthy. A true 0.54 (SE 0.22,
    p = .0141, CI 0.1088-0.9712) printed at 1 dp as "0.5 [0.1, 1.0]" recovers a
    point p of .0294, and the honest report was flagged against it.

    Evaluated at the corners of the joint rounding box, PLUS the null itself as
    a candidate estimate. The corners alone are not enough: p is monotone in the
    interval's width, but it is NOT monotone in the estimate -- it peaks where
    the estimate sits exactly on the null and falls away on either side. So when
    the null lies inside the estimate's rounding interval, p = 1 is reachable
    and no corner ever samples it. Omitting that turned "RR 1.0 (1.0-1.0),
    p = .32" -- the ordinary large-N table pattern, honest at RR 1.002
    (0.998-1.006) -- into an accusation.

    Non-finite corners (a bound rounding through zero on the log scale) are
    dropped; if none survives, fall back to the point recovery so the caller
    still has a usable range.
    """
    h = (_rounding.half_width(decimals) if decimals is not None
         else _half_width(estimate, lo, hi))
    # THE PRINTED VALUES THEMSELVES ARE A CORNER TOO -- and omitting them made
    # this interval exclude its own point recovery.
    #
    # The box was sampled only at `x - h` and `x + h`, never at `x`. But the
    # point recovery every caller compares against uses the PRINTED values, and
    # p is not monotone in the estimate (the docstring below already says so for
    # the null). So the "reachable range" could exclude the very number the same
    # function had just recovered.
    #
    # MEASURED on a real archived call, `OR 0.12 (0.03-0.5)`: the point recovery
    # is p = 0.0031 and the reported reachable range was [0.0000, 0.0003] -- an
    # interval that does not contain its own centre. With `0.5` read as 1 dp,
    # h = 0.05, so the sampled estimates were 0.07 and 0.17 and the lower bound
    # 0.03 became -0.02 (dropped as non-positive) or 0.08; the printed triple
    # was never evaluated. The paper prints p = .003 against a true recovery of
    # 0.0031, and it was about to be accused.
    #
    # Adding the printed values is strictly WIDENING, so it can only withdraw
    # accusations, never create one -- and it makes the invariant hold: the
    # reachable range always contains the point recovery.
    centres = [estimate - h, estimate, estimate + h]
    if abs(estimate - null_value) <= h:
        # The null is inside the printed estimate's interval, so a result
        # exactly at the null -- p = 1 -- is reachable.
        centres.append(null_value)
    ps: list[float] = []
    for e in centres:
        for a in (lo - h, lo, lo + h):
            for b in (hi - h, hi, hi + h):
                if b <= a:
                    continue
                if ratio and (a <= 0 or b <= 0 or e <= 0):
                    continue
                val = _p_from_ci(e, a, b, level, ratio, null_value)
                if math.isfinite(val):
                    ps.append(val)
    if not ps:
        point = _p_from_ci(estimate, lo, hi, level, ratio, null_value)
        point = point if math.isfinite(point) else 0.0
        return point, point
    return min(ps), max(ps)


def _p_tolerance(reported_p: float) -> float:
    """Rounding slack for a p printed at its own precision.

    THE ABSOLUTE FLOOR WAS REMOVED 2026-08-12, AND IT WAS A FALSE-CLEAR ENGINE.

    This used to be `max(precision_slack, 0.005)`. The 0.005 was introduced with
    the original tool family (8b68f5b) to stop a tiny p being unfalsifiable back
    when `str()`-based decimal reading gave 1e-8 a slack of 0.5. `_decimals` now
    reads e-notation correctly -- 1e-8 comes back as 8 dp -- so the floor was
    protecting against a bug that no longer exists.

    What it was doing meanwhile: an ADDITIVE slack of 0.005 applied to a
    quantity that spans orders of magnitude. MEASURED at the precisions clinical
    papers actually print:

        p = .05   -> band [0.0450, 0.0550]     (fine)
        p = .01   -> band [0.0050, 0.0150]     (already a 3x window)
        p = .001  -> band [-0.0040, 0.0060]    (a SIX-fold window, and it
                                                includes zero and negative p)

    So every p below 0.005 was effectively unfalsifiable against its own
    interval. Verified end to end on a real JAMA row: `OR 0.613 (0.440-0.855)`
    with a printed `p = .001` recovers p = 0.0039 -- unreachable at ANY common
    confidence level, 95% giving 0.0039 and 99% giving 0.00015 -- and the check
    returned `consistent`, "Estimate, CI and p are mutually consistent". A CI
    implying p as large as 0.008 still read consistent against a printed .001.

    That is a FALSE CLEAR in exactly the region where clinical papers put their
    headline claims, which under this project's cardinal rule is the
    second-worst output available.

    The printed precision is now the whole story, which is the rule every other
    tolerance in this toolkit follows: `p = .001` printed at 3 dp asserts
    [0.0005, 0.0015], and that is what it is judged against. The recovered-p
    INTERVAL already absorbs the rounding of the estimate and its bounds, so
    this additive term was never the only slack in the comparison.
    """
    return 0.5 * 10 ** (-_decimals(reported_p))


# --------------------------------------------------------------------------
# Absence of evidence
# --------------------------------------------------------------------------

def absence_of_evidence(
    ci_low: float | None = None,
    ci_high: float | None = None,
    measure: str | None = None,
    sesoi: float | None = None,
    claim_of_no_effect: bool = True,
    null_value: float | None = None,
    b: float | None = None,
    se: float | None = None,
    df: int | None = None,
    confidence_level: float = 0.95,
) -> dict:
    """Does a stated 'no effect' conclusion survive its own interval?

    "Not significant" is not "no effect". This asks what effects the interval
    still permits, and reports the largest one the data cannot rule out.

    Without a smallest effect size of interest (SESOI) we describe the interval
    and explicitly decline to judge — equivalence cannot be claimed against an
    unstated threshold. A ratio SESOI is a fold-change band: 1.25 and 0.8 both
    describe the band [0.8, 1.25], and either spelling is accepted.

    B AND SE ARE ACCEPTED IN PLACE OF AN INTERVAL, and here is why.

    MEASURED across the archive: 7 papers could not be checked here at all, and
    the reviews said so in their own words -- "The paper's headline null claim
    could not be evaluated with absence_of_evidence because the paper reports NO
    confidence intervals anywhere, and that tool requires ci_low/ci_high.
    Deriving a CI from B and SE would be interval arithmetic performed by hand,
    which is barred." Three of those papers print b AND se, which determines the
    interval completely, and in two of them the null result IS the paper's
    conclusion. The one check that speaks to the headline claim was the one that
    could not run, on the papers where it mattered most.

    The model was right to refuse: doing that arithmetic by hand is precisely
    what it is forbidden to do. The fix is for the TOOL to do it -- the same
    Wald arithmetic `check_regression` has always performed.

    A derived interval is stamped `interval_source: "derived"` and never passes
    itself off as the paper's. `df` selects the t distribution and its absence
    the normal, and the choice is reported rather than assumed in silence. If
    BOTH a printed interval and b/se arrive, the PRINTED one wins -- it is what
    the authors published -- and the derived one is reported beside it, because
    a disagreement between them is itself worth seeing.
    """
    derivation: dict | None = None
    if b is not None and se is not None:
        try:
            b_f, se_f = float(b), float(se)
        except (TypeError, ValueError):
            return {"severity": "indeterminate", "applicable": False,
                    "explanation": f"Not evaluated: b={b!r}, se={se!r} are not numbers."}
        if not (math.isfinite(b_f) and math.isfinite(se_f)) or se_f <= 0:
            return {"severity": "indeterminate", "applicable": False,
                    "explanation": (
                        f"Not evaluated: a standard error of {se!r} cannot bound an "
                        "interval. A non-positive or non-finite SE is what an extraction "
                        "produces from an empty cell, not what a paper printed.")}
        if df:
            crit = float(stats.t.ppf(1 - (1 - confidence_level) / 2, int(df)))
            dist = f"t with {int(df)} df"
        else:
            crit = float(stats.norm.ppf(1 - (1 - confidence_level) / 2))
            dist = "normal (no df supplied)"

        # A RATIO'S INTERVAL IS SYMMETRIC IN LOG SPACE, NEVER IN LINEAR SPACE.
        #
        # VERIFIED FALSE ACCUSATION, found by red-teaming this branch on the day
        # it was written. `measure="OR", b=0.95, se=0.08, sesoi=1.25` returned
        # `suspicious` off a linear interval [0.7932, 1.1068] that pokes outside
        # the [0.8, 1.25] equivalence band. The correct interval is
        # 0.95 * exp(+/-1.96 * 0.08) = [0.8121, 1.1113], wholly INSIDE the band,
        # and the same paper's own printed CI returns `consistent`. Every
        # logistic or Cox table prints an OR or HR whose SE is on the log scale,
        # so this is the ordinary case, not an edge one.
        #
        # This module's docstring already states the rule -- "Ratio measures live
        # on the log scale... Testing linear symmetry on a ratio flags every
        # correctly-reported ratio in the literature" -- and `is_ratio_measure`
        # is defined forty lines above. The new branch simply never asked.
        if is_ratio_measure(measure):
            if b_f <= 0:
                return {"severity": "indeterminate", "applicable": False,
                        "explanation": (
                            f"Not evaluated: measure {measure!r} is a ratio, so its point "
                            f"estimate cannot be {b_f}. A ratio is positive by "
                            "construction; this looks like a labelling or extraction "
                            "error rather than anything about the paper.")}
            lo, hi = b_f * math.exp(-crit * se_f), b_f * math.exp(crit * se_f)
            scale = "log (the SE is assumed to be on the log scale, as every "
            scale += "logistic and Cox table reports it)"
        else:
            lo, hi = b_f - crit * se_f, b_f + crit * se_f
            scale = "linear"
        derivation = {
            "interval_source": "derived",
            "derived_ci": [round(lo, 6), round(hi, 6)],
            "from": {"b": b_f, "se": se_f, "df": df,
                     "confidence_level": confidence_level},
            "distribution": dist,
            "scale": scale,
            "critical_value": round(crit, 6),
            "note": (
                "This interval was NOT printed by the paper. It is "
                + (f"b x exp(+/-{crit:.4f} x se)" if scale.startswith("log")
                   else f"b +/- {crit:.4f} x se")
                + f" on the {dist}, {scale} scale -- the same Wald arithmetic "
                "`check_regression` performs. It "
                "inherits the rounding of the printed b and se, so its bounds are "
                "approximate to that precision."
            ),
        }
        if ci_low is None or ci_high is None:
            ci_low, ci_high = lo, hi
        else:
            # The paper's own interval wins. Ours is reported alongside, because
            # two intervals for one coefficient that DISAGREE is a finding in
            # its own right and silently preferring either would bury it.
            derivation["interval_source"] = "printed (derived interval shown for comparison)"

    if ci_low is None or ci_high is None:
        return {
            "severity": "indeterminate",
            "applicable": False,
            "explanation": (
                "Not evaluated: needs either a printed interval (ci_low, ci_high) or "
                "the coefficient and its standard error (b, se) to derive one. This is "
                "a refusal, not a finding about the paper."
            ),
        }

    out = _absence_of_evidence_from_interval(
        ci_low, ci_high, measure, sesoi, claim_of_no_effect, null_value)
    if derivation:
        # Attached on EVERY return path, including the refusals, because a
        # reader must always be able to see whether the interval judged was
        # the paper's or ours.
        out['derivation'] = derivation
    return out


def _absence_of_evidence_from_interval(
    ci_low: float,
    ci_high: float,
    measure: str | None = None,
    sesoi: float | None = None,
    claim_of_no_effect: bool = True,
    null_value: float | None = None,
) -> dict:
    """The judgement half: given an interval, what does it permit?

    Split out from `absence_of_evidence` so the b/se derivation could be
    added in front of it without touching a single line of the reasoning
    this tool has always done. The derivation decides WHICH interval; this
    decides what the interval means.
    """
    cleaned: dict[str, float | None] = {}
    for name, value in (("ci_low", ci_low), ("ci_high", ci_high),
                        ("sesoi", sesoi), ("null_value", null_value)):
        if value is None:
            cleaned[name] = None
            continue
        try:
            f = float(value)
        except (TypeError, ValueError):
            return {
                "severity": "indeterminate",
                "explanation": (
                    f"Not evaluated: {name}={value!r} is not a number. This is a "
                    "refusal, not a finding about the paper."
                ),
            }
        if not math.isfinite(f):
            return {
                "severity": "indeterminate",
                "explanation": (
                    f"Not evaluated: {name}={value!r} is not finite. NaN and infinity "
                    "are what an extraction produces from an empty cell, a dash or a "
                    "division by zero, not values a paper printed. Re-read the source."
                ),
            }
        cleaned[name] = f
    ci_low = cleaned["ci_low"]
    ci_high = cleaned["ci_high"]
    sesoi = cleaned["sesoi"]
    null_value = cleaned["null_value"]

    ratio = is_ratio_measure(measure)
    difference = is_difference_measure(measure)

    if ci_low > ci_high:
        return {"severity": "indeterminate", "explanation": "CI bounds are reversed."}
    if ci_high - ci_low <= _rounding.EPSILON:
        # A zero-width interval is the signature of an extraction echo (the
        # same number read twice), and judging it produced a green "excludes
        # the null" from our own artefact.
        return {
            "severity": "indeterminate",
            "explanation": (
                f"The interval [{ci_low}, {ci_high}] has zero width, which is the "
                "signature of an extraction echo (the same number read twice) rather "
                "than a printed interval. Not evaluated; re-read the bounds."
            ),
        }
    if ratio and ci_low < 0:
        return {
            "severity": "indeterminate",
            "explanation": (
                f"Measure '{measure}' is a ratio, but the lower bound {ci_low} is "
                "negative -- a ratio's bounds cannot be. Likely an extraction or "
                "labelling error; not evaluated."
            ),
        }

    if null_value is None and not ratio and not difference:
        # We do not know where the null is, and guessing INVERTS the result.
        # `is_ratio_measure(None)` is False, so this used to assume 0.0: the
        # odds-ratio interval [0.85, 1.42] -- a textbook null result -- came
        # back "excludes the null", severity `consistent`. Every ratio CI has
        # positive bounds, so that green verdict was returned for effectively
        # every OR/RR/HR/IRR result, and those dominate this corpus. The same
        # inversion re-entered through the front door for any label the exact
        # set missed ("aOR", "adjusted odds ratio"), so the gate is now
        # "recognised", not "present".
        #
        # A negative bound is the one case that settles it: ratio measures are
        # strictly positive, so the measure cannot be a ratio and 0.0 is safe.
        if ci_low < 0 or ci_high < 0:
            null_value = 0.0
        elif measure is None:
            return {
                "severity": "indeterminate",
                "explanation": (
                    f"Cannot judge the interval [{ci_low}, {ci_high}] without knowing the "
                    "measure. The null is 1 for a ratio measure (OR/RR/HR/IRR) and 0 for a "
                    "difference. This interval is compatible with either reading, and they "
                    "give opposite answers, so pass `measure` (or `null_value`)."
                ),
                "measure_required": True,
            }
        else:
            return {
                "severity": "indeterminate",
                "explanation": (
                    f"Measure label '{measure}' is not recognised as a ratio "
                    "(OR/RR/HR/IRR, null 1) or a difference (MD/SMD/RD, null 0), and "
                    f"the interval [{ci_low}, {ci_high}] is compatible with either "
                    "reading, which give opposite answers. Pass a recognised `measure` "
                    "or `null_value`."
                ),
                "measure_required": True,
            }

    if null_value is None:
        null_value = 1.0 if ratio else 0.0

    includes_null = ci_low <= null_value <= ci_high
    if not includes_null:
        caveat = ""
        if claim_of_no_effect:
            caveat = (
                " If the paper nonetheless claims no effect, that claim contradicts "
                "this interval -- or refers to practical rather than statistical "
                "significance, which can only be assessed against a stated SESOI."
            )
        return {
            "severity": "consistent",
            "includes_null": False,
            "explanation": (
                f"The interval [{ci_low}, {ci_high}] excludes the null ({null_value}), so no "
                "absence-of-effect claim arises here." + caveat
            ),
        }

    # Largest effect still compatible with the data, on the measure's own scale.
    if ratio:
        if ci_low > 0:
            largest = max(ci_high / null_value, null_value / ci_low)
            desc = f"a {largest:.2f}-fold effect in either direction"
        else:
            # A lower bound of 0 (zero events) makes the protective direction
            # unbounded; publishing float('inf') breaks strict JSON downstream.
            largest = None
            desc = ("an unbounded effect in the protective direction "
                    "(the interval's lower bound reaches 0)")
    else:
        largest = max(abs(ci_high - null_value), abs(null_value - ci_low))
        desc = f"an effect of {largest:.3f}"

    if sesoi is None:
        return {
            "severity": "indeterminate" if claim_of_no_effect else "consistent",
            "includes_null": True,
            "largest_compatible_effect": largest,
            "sesoi_provided": False,
            "explanation": (
                f"The interval [{ci_low}, {ci_high}] includes the null, so the result is not "
                f"statistically significant — but it remains compatible with {desc}. "
                "'Not significant' is not 'no effect'. Because the paper states no smallest "
                "effect size of interest, equivalence cannot be assessed and no conclusion of "
                "'no effect' is licensed by these numbers alone."
            ),
            "recommendation": (
                "An equivalence test (TOST) against a pre-specified SESOI is required to "
                "support a claim of no effect."
            ),
            "methodology": _AOE_METHODOLOGY,
        }

    # With a SESOI we can say something definite -- once the SESOI itself is
    # usable. A degenerate SESOI (zero, or exactly the null) defines a
    # zero-width equivalence band that EVERY real interval fails, which turns
    # this check into an accusation machine; and a ratio SESOI below 1 is the
    # same band stated from the other end, not a different threshold.
    if ratio:
        if sesoi <= 0:
            return {
                "severity": "indeterminate",
                "explanation": (
                    f"SESOI={sesoi:g} is not usable for a ratio measure: equivalence "
                    "bounds are a positive fold-change (e.g. 1.25, or equivalently "
                    "0.8). Not evaluated."
                ),
            }
        band_hi = max(sesoi, 1.0 / sesoi)
        if band_hi - 1.0 <= _rounding.EPSILON:
            return {
                "severity": "indeterminate",
                "explanation": (
                    f"SESOI={sesoi:g} equals the null (1), so the equivalence band has "
                    "zero width and every real interval would fail it. Not evaluated."
                ),
            }
        within = (ci_low >= 1.0 / band_hi) and (ci_high <= band_hi)
    else:
        if abs(sesoi) <= _rounding.EPSILON:
            return {
                "severity": "indeterminate",
                "explanation": (
                    "SESOI=0 defines a zero-width equivalence band that every real "
                    "interval fails. Pass the smallest effect size that would MATTER. "
                    "Not evaluated."
                ),
            }
        within = (ci_low >= -abs(sesoi)) and (ci_high <= abs(sesoi))

    if within:
        return {
            "severity": "consistent",
            "includes_null": True,
            "equivalence_supported": True,
            "largest_compatible_effect": largest,
            "sesoi_provided": True,
            "explanation": (
                f"The whole interval [{ci_low}, {ci_high}] falls inside the equivalence bounds "
                f"implied by the SESOI ({sesoi}), so a claim of practical equivalence IS "
                "supported by these numbers."
            ),
            "methodology": _AOE_METHODOLOGY,
        }
    return {
        "severity": "suspicious" if claim_of_no_effect else "indeterminate",
        "includes_null": True,
        "equivalence_supported": False,
        "largest_compatible_effect": largest,
        "sesoi_provided": True,
        "explanation": (
            f"The paper's interval [{ci_low}, {ci_high}] extends beyond the SESOI ({sesoi}) and "
            f"remains compatible with {desc}. A conclusion of 'no effect' therefore outruns the "
            "evidence: the study could not distinguish no effect from a meaningful one."
        ),
        "methodology": _AOE_METHODOLOGY,
    }


_AOE_METHODOLOGY = (
    "Absence-of-evidence check: a CI containing the null shows only that the data are "
    "compatible with the null, not that the null is true. The largest compatible effect is read "
    "off the interval bound furthest from the null. Equivalence is assessed only against a "
    "stated SESOI; with none, the check reports the interval and declines to conclude."
)
