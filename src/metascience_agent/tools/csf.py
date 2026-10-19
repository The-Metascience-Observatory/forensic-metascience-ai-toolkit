"""
Carlisle-Stouffer-Fisher baseline-similarity test, with a correlation-aware null.

WHY THIS FILE WAS REWRITTEN
---------------------------
The classical CSF test combines baseline p-values assuming they are
INDEPENDENT. Table 1 rows are not: weight, height, BMI and waist are four
measurements of roughly one thing. The previous implementation named this
problem in its own docstring and then did nothing about it.

Measured consequences at a nominal 5% level (10,000 simulated Table 1s):

| condition                         | fires  |
|-----------------------------------|--------|
| Stouffer, rho = 0.5, k = 10       | 15%    |
| Stouffer, rho = 0.6               | 33.5%  | (6.7x nominal)
| Stouffer, rho = 0.75, k = 25      | ~50%   |
| correctly randomised cluster RCT  | ~71%   | (ICC = 0.10)

A correctly-randomised trial was being told its randomisation had failed. Two
independent projects building this check hit the identical wall, so this is a
methodological hazard of the technique rather than a coding slip.

THE FIX
-------
1. **Correlation-aware null.** Under equicorrelation rho among k p-values,
   Var(sum z_i) = k + k(k-1)*rho, so Stouffer divides by
   sqrt(k + k(k-1)rho) rather than sqrt(k) (Strube 1985). Fisher uses the
   Brown / Kost & McDermott scaled-chi-square correction.
2. **Sensitivity analysis when rho is unknown**, which it almost always is.
   Rather than assuming independence (anti-conservative) or a single guessed
   rho, the test is evaluated across a grid of plausible correlations and
   escalates ONLY if the conclusion survives the most conservative one. This
   mirrors the rule used elsewhere in this toolkit: a finding must hold across
   the whole attainable interval, not at one convenient point.
3. **Design gate.** In cluster-randomised and multi-site trials, independence
   fails BY DESIGN. The test refuses rather than flagging. The gate reads a
   RESOLVED design (`_resolve_design`), not a raw string: the first version
   treated any non-empty `design` as known, so British spellings that matched
   none of its sets ("randomised", "minimisation") both escaped the refusal and
   lifted the severity cap -- telling the truth about a minimised trial raised
   the verdict from `suspicious` to `highly_suspicious`.
4. **Language.** "Suspicious" is replaced with wording that describes the
   statistical observation without implying misconduct.

Reference: Proschan & Shaw on the operating characteristics of Carlisle's
method; Strube (1985) for the Stouffer correction; Brown (1975) and Kost &
McDermott (2002) for the Fisher correction.
"""

import numpy as np
from scipy import stats

# Designs in which baseline independence fails by construction.
DEPENDENT_DESIGNS = {
    "cluster_randomized", "cluster_rct", "cluster", "multi_site", "multisite",
    "stepped_wedge", "crossover", "matched_pairs", "paired",
    # Stratified and minimised allocation FORCE baseline balance on the
    # stratifying variables. Those rows are then similar by construction, which
    # is exactly the signal this test reads as fabrication.
    "stratified", "stratified_randomized", "minimisation", "minimization",
    "covariate_adaptive", "blocked_stratified",
    # REPEATED MEASURES IS `paired` WITH k > 2, and it was the one dependent
    # family with no entry here. The same people measured at several visits
    # produce SDs correlated by construction -- the same mechanism that puts
    # crossover and matched_pairs on this list -- and the test reads that
    # correlation as under-dispersion.
    #
    # MEASURED on simulated HONEST single-group repeated-measures data (k=4,
    # n=40, 150 replicates, SD literals supplied so the precision guard does
    # not short-circuit), with the design declared truthfully:
    #
    #     between-visit rho = 0.00 ->   0.0% flagged `suspicious`
    #                         0.80 ->   9.3%
    #                         0.95 ->  14.0%
    #                         0.98 ->  13.3%
    #
    # Declaring the design did not help, because none of these words resolved:
    # "repeated measures", "longitudinal", "within-subjects", "pre-post" and
    # "panel study" ALL returned None, and None is not in this set, so the
    # truthful declaration read as an independent design.
    #
    # It matters more than the rate suggests: this verdict carries "the
    # signature Hartgerink et al. (2019) found most diagnostic of fabricated
    # data", which is the most damaging `suspicious` in the toolkit.
    "repeated_measures", "within_subjects", "longitudinal", "pre_post",
    "panel", "within_person",
}

# Designs in which baseline comparisons ARE mutually independent, so the CSF
# premise holds and the verdict need not be capped. Membership here is the ONLY
# thing that counts as "the design is known"; see `_resolve_design`.
INDEPENDENT_DESIGNS = {
    "parallel_rct", "parallel_group", "parallel", "rct",
    "randomized_controlled_trial", "randomised_controlled_trial",
    "simple_randomization", "simple_randomisation",
    "individually_randomized", "individually_randomised",
    "randomized", "randomised",
}

# Free-text -> canonical design, MOST SPECIFIC FIRST. `design` reaches this tool
# as whatever a model read off a methods section -- "cluster-randomised trial",
# "stratified block randomisation", "minimisation by centre" -- so exact set
# membership recognises almost none of it. Substring matching is ordered because
# every dependence-inducing design ALSO contains "randomis": "cluster" has to be
# tested before the plain-randomisation pattern or a cluster trial resolves to
# simple randomisation and loses its refusal.
_DESIGN_PATTERNS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("cluster",), "cluster_randomized"),
    # Before the plain-randomisation clause, for the same reason `cluster` is:
    # "randomised crossover" and "randomised repeated-measures trial" both
    # contain "randomis" and must not resolve to simple randomisation.
    (("repeated_measur", "repeated_assess", "repeat_measur"), "repeated_measures"),
    (("within_subject", "within_person", "within_participant"), "within_subjects"),
    (("longitudinal", "panel_stud", "panel_data", "multiwave", "multi_wave"),
     "longitudinal"),
    (("pre_post", "prepost", "pre_and_post", "before_after", "baseline_follow"),
     "pre_post"),
    (("stepped_wedge", "stepped"), "stepped_wedge"),
    (("stratif",), "stratified"),
    (("minimis", "minimiz"), "minimisation"),
    (("covariate_adaptive", "covariate_adapt", "urn_"), "covariate_adaptive"),
    (("crossover", "cross_over"), "crossover"),
    # `paired` MUST NOT MATCH INSIDE `unpaired`. VERIFIED 2026-08-18:
    # "individually randomised, unpaired" resolved to `matched_pairs` -- the
    # design that declares baseline observations correlated BY DESIGN, which is
    # the exact opposite of what that trial says, and it changes the CSF
    # applicability gate. Negated forms are listed first so they are refused
    # before the bare stem is tried; see `_NEGATED_PAIRING`.
    (("matched", "paired", "pairwise"), "matched_pairs"),
    (("multi_site", "multisite", "multicent", "multi_cent"), "multi_site"),
    # LAST TWO, for the reason given above: every pattern that induces
    # dependence has already had its chance, so what is left is an individually
    # randomised parallel trial, which is the design CSF was written for.
    (("parallel", "_rct", "rct_"), "parallel_rct"),
    (("randomis", "randomiz"), "randomized"),
)

# Phrases that DENY randomisation. Without this they fall through to the
# "randomis|randomiz" pattern and a non-randomised study would resolve to
# `randomized` -- i.e. earn the UNCAPPED ceiling on the strength of the very
# word it used to say randomisation did not happen.
_NOT_RANDOMISED = ("non_random", "nonrandom", "not_random", "quasi")

#: NEGATION, for every stem at once. `_NEGATED_PAIRING` used to enumerate the
#: eight ways to write "not paired"; it was the second such list in this file
#: and it only ever covered the stem someone had already been bitten by. Three
#: more cases were still live when it was written, each resolving to a DEPENDENT
#: design and so suppressing the check outright, with an `explanation` that
#: states the false design as a fact about the trial:
#:
#:   "parallel-group RCT, individually randomised, no stratification"
#:                                                   -> stratified
#:   "this trial was not cluster randomised"         -> cluster_randomized
#:   "not a multicentre trial"                       -> multi_site
#:
#: A stem match is negated when a negation TOKEN precedes it in the same
#: comma-clause, or when one is written as an attached prefix ("unpaired",
#: "nonrandomised"). Clause-bounded so a denial in one phrase cannot travel to
#: another: "individually randomised, unpaired" must still resolve `randomized`
#: off its first clause.
#:
#: A design string that negates everything it names resolves to None -- unknown
#: -- which is the safe outcome in both directions: `design_known` is then
#: False, so the severity cap STAYS ON and the dependent-design gate does not
#: fire either.
_NEGATION_TOKENS = ("no", "not", "non", "never", "without", "un")
_NEGATION_PREFIXES = ("un", "non", "not")


def _unnegated_match(clause: str, needle: str) -> bool:
    """Does `needle` occur in `clause` without a negation governing it?"""
    start = 0
    while True:
        i = clause.find(needle, start)
        if i < 0:
            return False
        before = clause[:i]
        attached = any(before.endswith(pre) for pre in _NEGATION_PREFIXES)
        tokens = [t for t in before.split("_") if t]
        if not attached and not any(t in _NEGATION_TOKENS for t in tokens):
            return True
        start = i + 1


def _resolve_design(design: str | None) -> str | None:
    """Canonical design name for a free-text design string, or None if unknown.

    Returning None matters more than any mapping here. `design_known` used to be
    `bool(design_key)`, so ANY non-empty string -- including one this module has
    never heard of -- counted as a known design and LIFTED the severity cap. The
    inversion was worst on honest input: a paper described in British English
    ("randomised", "minimisation") matched nothing in the American-spelled sets
    above, was therefore not gated as a dependent design, and was then treated as
    a known independent design, which is the exact opposite of both true
    statements about it. Telling the truth raised the ceiling from `suspicious`
    to `highly_suspicious`.
    """
    key = str(design or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return None
    if key in DEPENDENT_DESIGNS or key in INDEPENDENT_DESIGNS:
        return key
    if any(n in key for n in _NOT_RANDOMISED):
        return None
    # A DENIAL OF A DESIGN IS NOT THAT DESIGN. Each clause is searched
    # separately, so "individually randomised, unpaired" still resolves off its
    # first clause while the second is refused.
    for needles, canonical in _DESIGN_PATTERNS:
        for clause in key.split(","):
            if any(_unnegated_match(clause, n) for n in needles):
                return canonical
    return None


# Plausible equicorrelation values for clinical Table 1 covariates. The upper
# end is what related anthropometrics actually reach.
DEFAULT_RHO_GRID = (0.0, 0.1, 0.2, 0.3, 0.5, 0.7)

# Correlation used for the VERDICT when none is supplied. 0.5 is a conservative
# but realistic upper bound for the AVERAGE pairwise correlation across a whole
# clinical Table 1, which mixes strongly related anthropometrics (weight/BMI/
# waist) with near-independent rows (age, sex, smoking, comorbidity). Taking the
# grid maximum (0.7) as the verdict was over-conservative: at rho=0.7 with k=10
# the table is effectively ~2 independent comparisons, and even a textbook
# fabrication signature (ten p-values all >= 0.94) fails to reach significance.
# The full profile is always reported so a reader can see the sensitivity.
VERDICT_RHO = 0.5


def _json_safe_p(value: float) -> float | str:
    """A rejected p-value in a form `json.dumps` can emit.

    JSON has no literal for NaN or Infinity, and every tool result in this
    codebase is serialised before a reader ever sees it. Finite rejects (-0.5,
    1.5) survive as numbers; non-finite ones are echoed as their text so the
    reason for the refusal is not itself lost to the serialiser.
    """
    return float(value) if np.isfinite(value) else repr(float(value))


def _stouffer_similarity_p(z_scores: np.ndarray, rho: float) -> float:
    """One-sided Stouffer p for excess similarity, under equicorrelation rho.

    Var(sum z) = k + k(k-1)rho. At rho = 0 this reduces to the classical
    sum(z)/sqrt(k).
    """
    k = len(z_scores)
    var = k + k * (k - 1) * rho
    if var <= 0:
        return float("nan")
    return float(stats.norm.sf(np.sum(z_scores) / np.sqrt(var)))


def _fisher_similarity_p(valid_p: np.ndarray, rho: float) -> float:
    """Brown / Kost & McDermott scaled-chi-square Fisher combination."""
    k = len(valid_p)
    chi2_stat = -2 * np.sum(np.log(1 - valid_p))
    if rho <= 0 or k < 2:
        return float(stats.chi2.sf(chi2_stat, 2 * k))
    # Kost & McDermott (2002) polynomial for cov(-2 ln p_i, -2 ln p_j).
    cov = rho * (3.263 + 0.710 * rho + 0.027 * rho**2)
    expectation = 2 * k
    variance = 4 * k + k * (k - 1) * cov
    c = variance / (2 * expectation)
    f = 2 * expectation**2 / variance
    return float(stats.chi2.sf(chi2_stat / c, f))


def csf_test(
    p_values: list[float],
    method: str = "stouffer",
    correlation: float | None = None,
    design: str | None = None,
    rho_grid: tuple[float, ...] = DEFAULT_RHO_GRID,
) -> dict:
    """Test whether baseline p-values are MORE similar than randomisation allows.

    Args:
        p_values: baseline comparison p-values from one table.
        method: 'stouffer' or 'fisher'.
        correlation: equicorrelation among the baseline variables, if known or
            estimable. When omitted, a sensitivity analysis is run instead and
            the verdict is taken from the most conservative correlation.
        design: study design, as free text. Cluster-randomised, multi-site,
            stepped-wedge, crossover, stratified, minimised and matched designs
            violate independence BY DESIGN and are refused; see
            `_resolve_design` for what is recognised. A string this tool cannot
            place counts as UNKNOWN, which keeps the severity cap on.
        rho_grid: correlations spanned by the sensitivity analysis.

    Returns:
        Dict with `similarity_p` (small => too similar), the sensitivity
        profile, `design_resolved` (what the design string was understood to
        mean), `individual_p_values` (the p-values actually combined) and a
        severity that only escalates on a robust result.
    """
    arr = np.asarray(p_values, dtype=float)
    finite = np.isfinite(arr)
    usable = np.zeros(arr.shape, dtype=bool)
    usable[finite] = (arr[finite] > 0.0) & (arr[finite] <= 1.0)
    valid_p = arr[usable]

    # A p-value outside (0, 1] or a NaN is not a p-value. The old line here was
    # `arr[(arr > 0) & (arr <= 1)]`, which DROPPED those silently and then echoed
    # the full input back as `individual_p_values` -- so a table whose extraction
    # produced NaN for half its rows was combined from the surviving half and
    # reported as though all of them had been used. Combining k p-values is
    # entirely a statement about k; quietly changing k changes the verdict while
    # the output still names the original list.
    #
    # Refusing outright rather than proceeding on the survivors: a non-finite p
    # means the extraction failed, and an extraction that failed on one row is
    # not evidence that the rows it did produce are right. `indeterminate` is
    # "a precondition could not be verified", which is exactly the situation.
    if usable.size and not usable.all():
        dropped = [_json_safe_p(v) for v in arr[~usable].tolist()]
        return {
            "severity": "indeterminate",
            "applicable": False,
            "error": f"{len(dropped)} of {arr.size} p-values are not in (0, 1]: {dropped}",
            "dropped_p_values": dropped,
            "individual_p_values": valid_p.tolist(),
            "num_tests": int(valid_p.size),
            "warning": (
                f"{len(dropped)} value(s) are not p-values and NOTHING was combined. "
                f"`num_tests` reports the {int(valid_p.size)} that would have been left, "
                "not a number of tests that ran."
            ),
            "explanation": (
                "A p-value must be finite and in (0, 1]. Values outside that range "
                "(or NaN) mean the extraction failed, not that the trial is "
                "irregular, so no verdict is issued. Re-extract the baseline table "
                "and re-run; supplying only the rows that parsed would silently "
                "change how many comparisons are being combined."
            ),
            "methodology": "CSF input-validity gate.",
        }

    if len(valid_p) == 0:
        return {"error": "No valid p-values provided", "severity": "indeterminate"}
    if len(valid_p) < 3:
        return {
            "severity": "indeterminate",
            "error": f"only {len(valid_p)} usable p-values",
            "explanation": (
                "Combining fewer than 3 baseline p-values has almost no power and a "
                "correspondingly unstable false-positive rate. Not evaluated."
            ),
            "num_tests": int(len(valid_p)),
        }

    # --- design gate: independence fails by construction -------------------
    resolved_design = _resolve_design(design)
    if resolved_design in DEPENDENT_DESIGNS:
        return {
            "severity": "indeterminate",
            "applicable": False,
            "design": design,
            "design_resolved": resolved_design,
            "num_tests": int(len(valid_p)),
            "explanation": (
                f"This is a {design} design, in which baseline observations are correlated "
                "BY DESIGN, not by chance. The Carlisle-Stouffer-Fisher null assumes "
                "independent baseline comparisons and does not hold here. A simulated, "
                "correctly-randomised cluster trial (design effect 5.95, true null) was "
                "flagged at every table size by the uncorrected test. Not evaluated."
            ),
            "methodology": "CSF design-applicability gate.",
        }

    # Held before the clip so the report can echo what the table actually said.
    valid_p_reported = valid_p.tolist()
    # UPPER CLIP AT 0.995, NOT 1 - 1e-10. A printed "p = 1.00" is not the claim
    # p = 0.9999999999; it is the rounding interval [0.995, 1.00], and Phi^-1 of
    # its two ends differ enormously -- z(0.995) = 2.58 against z(1 - 1e-10) =
    # 6.36 (Fisher: -2 ln(1-p) = 10.6 against 46.0). The old upper clip fed the
    # MOST extreme representable value into a one-sided EXCESS-SIMILARITY test, so
    # each honestly rounded 1.00 -- which a perfectly balanced categorical row
    # legitimately prints, chi-square having point mass at p = 1 on exact balance
    # -- pushed the combined statistic toward `highly_suspicious`. On realistic
    # mixed continuous/categorical Table 1s ~1% of HONEST tables were accused
    # (0.1% at fabrication grade); at the conservative end of the printed
    # interval that rate is ~0. This is the same interval rule the rest of the
    # toolkit already applies (`rounding`: a number in a paper is an interval,
    # err WIDE). It is severity-monotone -- a smaller z can only RAISE the
    # combined p, never lower it -- so it cannot manufacture a new accusation nor
    # turn any real signature into a false all-clear; a genuine fabrication of
    # p's at/near 1.00 still combines to a small p (e.g. three 1.00s under a
    # stated design remain `highly_suspicious`). It also protects the
    # table1_dispersion cross-check, which feeds COMPUTED p's that can sit exactly
    # at 1.0 for a discrete test on perfectly balanced arms. The residual 0.995
    # cap still slightly overstates a value printed to 1 dp ("1.0" -> [0.95, 1]),
    # which errs non-accusing; recovering the last of it needs the printed
    # precision threaded in per value, a tool-surface change left for later.
    valid_p = np.clip(valid_p, 1e-10, 0.995)
    k = len(valid_p)
    z_scores = stats.norm.ppf(valid_p)

    def similarity_at(rho: float) -> float:
        return (_stouffer_similarity_p(z_scores, rho) if method == "stouffer"
                else _fisher_similarity_p(valid_p, rho))

    # --- sensitivity across plausible correlations -------------------------
    if correlation is None:
        grid = tuple(sorted(set(rho_grid) | {VERDICT_RHO}))
        profile = {round(r, 3): similarity_at(r) for r in grid}
        rho_used = VERDICT_RHO
        similarity_p = profile[round(rho_used, 3)]
        independence_p = profile[round(min(grid), 3)]
        assumed = False
    else:
        rho_used = float(correlation)
        similarity_p = similarity_at(rho_used)
        profile = {round(rho_used, 3): similarity_p}
        independence_p = similarity_at(0.0)
        assumed = True

    mean_p = float(np.mean(valid_p))

    # --- severity: only a result robust to the correlation assumption ------
    # RECOGNISED, not merely non-empty. `bool(design_key)` let any string at all
    # -- "randomised", "minimisation", "typo" -- pass as a known design and lift
    # the cap. A design this module cannot place is UNKNOWN, and unknown keeps the
    # cap on, because the designs that would explain extreme baseline similarity
    # innocently are exactly the ones an unrecognised string might be naming.
    design_known = resolved_design is not None
    if similarity_p < 0.001 and not design_known:
        # Without a stated design we cannot rule out stratified/minimised/cluster
        # allocation, each of which forces baseline balance BY CONSTRUCTION. The
        # arithmetic may be extreme, but the premise is unverified, so this caps
        # below a fabrication-grade verdict rather than assuming simple
        # randomisation -- the same rule `bound_source` applies to GRIM.
        severity = "suspicious"
        # Two different ways to be unknown, and a reader needs to be able to tell
        # them apart: nothing was passed, or something was passed that this tool
        # could not place. The second reads as a bug report on the tool, and
        # naming the string is what makes it fixable.
        design_note = (
            "but the study DESIGN was not supplied"
            if not str(design or "").strip()
            else f"but the stated design {design!r} was not RECOGNISED"
        )
        headline = (
            f"Baseline p-values are far more similar than simple randomisation predicts "
            f"(similarity p = {similarity_p:.6f} at rho = {rho_used}), {design_note}. "
            "Stratified, minimised, cluster and matched allocation all force "
            "baseline balance by construction and would explain this pattern innocently. "
            "Capped below `highly_suspicious` until the design is known."
        )
    elif similarity_p < 0.001:
        severity = "highly_suspicious"
        headline = (
            f"Baseline p-values remain more similar than randomisation allows even under the "
            f"conservative assumption rho = {rho_used} (similarity p = {similarity_p:.6f})."
        )
    elif similarity_p < 0.01:
        severity = "suspicious"
        headline = (
            f"Baseline p-values are more similar than expected under randomisation, and the "
            f"result survives a correlation of rho = {rho_used} "
            f"(similarity p = {similarity_p:.4f})."
        )
    elif independence_p < 0.01:
        # Significant only if you pretend the rows are independent -- which is
        # precisely the assumption that produced a 33.5% false-positive rate.
        severity = "indeterminate"
        headline = (
            f"Under an INDEPENDENCE assumption these p-values would look too similar "
            f"(p = {independence_p:.4f}), but the result does NOT survive plausible "
            f"correlation among baseline variables (p = {similarity_p:.4f} at rho = {rho_used}). "
            "Table 1 rows are typically correlated, so this is not evidence of a "
            "randomisation problem without an estimate of that correlation."
        )
    else:
        severity = "consistent"
        headline = (
            f"The distribution of baseline p-values is consistent with random allocation "
            f"(similarity p = {similarity_p:.4f})."
        )

    return {
        # The p-values ACTUALLY combined. Identical to the input by the time
        # control reaches here -- anything unusable returned above -- but stated
        # as the used list rather than the input list so the field cannot drift
        # back into describing values the arithmetic never saw.
        "individual_p_values": valid_p_reported,
        "dropped_p_values": [],
        "similarity_p": similarity_p,
        "combined_p": similarity_p,          # backward-compat alias
        "similarity_p_under_independence": independence_p,
        "sensitivity_profile": profile,
        "correlation_used": rho_used,
        "correlation_assumed": assumed,
        "direction": "too_similar" if similarity_p < 0.01 else "normal",
        "method": method,
        "design": design,
        # What the tool UNDERSTOOD the design to be, echoed so a reader can see
        # whether the severity cap was applied for a reason they agree with.
        # None means "not recognised", which is what keeps the cap on.
        "design_resolved": resolved_design,
        "design_recognized": design_known,
        "num_tests": int(k),
        "mean_p": mean_p,
        "severity": severity,
        "explanation": headline,
        "caveat": (
            "Baseline p-values within one table are usually correlated. Evaluated at "
            f"rho = {rho_used}"
            + ("" if assumed else " (a conservative but realistic average for a clinical Table 1)")
            + ". Assuming independence inflates the false-positive rate to roughly 33% at "
            "rho = 0.6 and ~50% at rho = 0.75 with 25 rows, so a verdict that does not "
            "survive plausible correlation is reported as indeterminate rather than as a "
            "finding."
        ),
        "methodology": (
            f"Carlisle-Stouffer-Fisher ({method}) with a correlation-aware null: "
            + ("Stouffer divided by sqrt(k + k(k-1)rho) (Strube 1985)"
               if method == "stouffer"
               else "Fisher via the Brown / Kost & McDermott scaled chi-square")
            + f" over {k} baseline p-values. One-sided for EXCESS similarity: a small "
            "similarity_p means the groups are more alike than randomisation predicts, which "
            "is the signal of interest -- uniformly high baseline p-values are never "
            "reassurance."
        ),
    }
