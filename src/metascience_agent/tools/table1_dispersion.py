"""
Bayesian Table 1 dispersion check (Heathers 2025 §"Bayesian Table 1 analysis";
Bolland et al. 2022, F1000Research, "Aushsi baseline").

Idea. Under proper randomization, baseline comparisons across study arms
yield p-values uniformly distributed on [0, 1]. Equivalently, two-sided
z-scores z_i = Φ⁻¹(1 − p_i / 2) satisfy z_i² ~ χ²_1 with E[z²] = 1. Two
deviations are diagnostic:

  - **Under-dispersion** (E[z²] < 1, precision multiplier > 1): groups are
    too similar across rows, the classic signature of fabricated baseline
    data (the original Carlisle/Fujii observation).
  - **Over-dispersion** (E[z²] > 1, precision multiplier < 1): groups
    differ more than chance allows — often a randomization failure.

The precision multiplier τ is estimated as

    τ̂ = √( 1 / mean(z_i²) )

with a percentile bootstrap CI. We additionally report a Kolmogorov-Smirnov
test of the empirical p-values against U(0, 1) as an independent dispersion
diagnostic.

This is a Python port of the *idea* of Bolland et al.'s Shiny tool, not a
faithful reproduction of their Bayesian hierarchical model. The Shiny app
should still be considered authoritative for definitive analysis. The
strength of this implementation is that it accepts mixed continuous /
categorical rows uniformly via the row → p-value → z² pipeline, sidestepping
the assumption-mixing concern that complicates the classical CSF test.

CORRELATION AND DESIGN: PARITY WITH `csf.py`
--------------------------------------------
This tool and `csf_test` answer the SAME forensic question -- is Table 1 too
similar between arms? -- from the SAME evidence, the per-row baseline p-values.
`csf.py` was hardened after measuring a 33.5% false-positive rate at rho = 0.6
and roughly 71% on correctly-randomised cluster trials. This tool was not, so
the two could land on opposite ends of the severity ladder on one table: on 12
under-dispersed rows with the design unstated, this returned
`highly_suspicious` (tau-hat 7.40, CI [7.08, 7.75]) while `csf_test` on the
very same p-values returned `indeterminate`, because the result did not survive
plausible correlation among baseline variables.

Three corrections bring this tool to that standard:

  1. **Design gate** (below): stratified, minimised, cluster and matched
     allocation force baseline balance by construction. Refuse, do not flag.
  2. **Design-unknown cap**: without a stated design those allocations cannot be
     ruled out, so the verdict is capped below `highly_suspicious` -- the same
     rule `csf_test` applies.
  3. **Correlation awareness**: the percentile bootstrap resamples rows i.i.d.,
     so correlated rows NARROW the CI on tau-hat and make the `ci_lo > 2`
     escalation MORE likely -- exactly backwards. The bootstrap now resamples
     the EFFECTIVE number of independent rows under an equicorrelation rho, and
     the verdict is read off the conservative rho that `csf.py` already
     calibrated. Because a wider CI still cannot tell whether the uniformity is
     itself a product of the correlation, escalation is additionally vetoed when
     the correlation-aware combination in `csf_test` -- run on these same
     p-values, reusing that implementation rather than duplicating it -- reports
     the finding as surviving only under an independence assumption.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats

from . import anova as _anova
from . import chi_squared as _chi_squared
from .csf import (
    DEFAULT_RHO_GRID,
    DEPENDENT_DESIGNS,
    VERDICT_RHO,
    _resolve_design,
    csf_test,
)


def _row_to_p_value(row: dict[str, Any]) -> tuple[float, str, dict]:
    """Compute a two-sided p-value from a Table 1 row.

    Each row is either:
      - {"means": [...], "sds": [...], "ns": [...]}  → one-way ANOVA
      - {"counts": [[r1c1, r1c2, ...], [r2c1, r2c2, ...], ...]} → chi-squared

    Returns (p_value, row_kind, raw_stats).
    """
    if "means" in row and "sds" in row and "ns" in row:
        means = list(row["means"])
        sds = list(row["sds"])
        ns = list(row["ns"])
        if len(means) < 2 or len(sds) != len(means) or len(ns) != len(means):
            raise ValueError("Continuous row needs ≥2 groups with matching means/sds/ns lengths.")
        r = _anova.recalc_one_way_anova(means, sds, ns)
        return float(r["calculated_p"]), "continuous", r
    if "counts" in row:
        counts = [list(map(int, r)) for r in row["counts"]]
        if len(counts) < 2 or any(len(r) < 2 for r in counts):
            raise ValueError("Categorical row needs a 2D contingency table with ≥2 rows and ≥2 cols.")
        r = _chi_squared.recalc_chi_squared(counts)
        return float(r["calculated_p"]), "categorical", r
    raise ValueError(
        "Each row must have either ('means','sds','ns') for continuous or "
        "'counts' for categorical."
    )


def _safe_p(p: float) -> float:
    """Clip p-values to (epsilon, 1 - epsilon) so Φ⁻¹ stays finite."""
    eps = 1e-12
    return min(max(p, eps), 1 - eps)


def _z_from_p_two_sided(p: float) -> float:
    """Two-sided z-score: z = Φ⁻¹(1 − p / 2). Always non-negative."""
    return float(stats.norm.ppf(1 - _safe_p(p) / 2))


def _precision_multiplier(z2_values: np.ndarray) -> float:
    """τ̂ = √(1 / mean(z²)). Under H0, mean(z²) ≈ 1 ⇒ τ ≈ 1."""
    m = float(np.mean(z2_values))
    if m <= 0:
        return float("inf")
    return math.sqrt(1.0 / m)


def _effective_rows(k: int, rho: float) -> int:
    """How many INDEPENDENT rows k equicorrelated rows are worth.

    Same identity `csf.py` uses for its Stouffer correction (Strube 1985):
    Var(sum z) = k + k(k-1)rho, i.e. a design effect of 1 + (k-1)rho. Weight,
    height, BMI and waist are four measurements of roughly one thing, so a
    12-row Table 1 at rho = 0.5 carries about two rows' worth of information.
    Floored at 2 because the bootstrap needs at least two draws to vary.
    """
    deff = 1.0 + (k - 1) * max(float(rho), 0.0)
    return max(2, int(k / deff))


def _effective_df(k: int, rho: float) -> float:
    """Effective degrees of freedom for mean(z²) under equicorrelated rows.

    Satterthwaite: T = k·mean(z²) has E[T] = k and, for jointly normal z with
    equicorrelation ρ, Var(T) = 2k(1 + (k−1)ρ²) — because Corr(z_i², z_j²) = ρ²
    for bivariate normal, NOT ρ. Matching a scaled χ² gives ν = k / (1+(k−1)ρ²).

    We deliberately use the LARGER design effect 1 + (k−1)ρ instead. That is the
    Strube identity `_effective_rows` and `csf.py` already apply to the Stouffer
    SUM, where it is exact; for the sum of SQUARES it is conservative, since
    ρ ≥ ρ² on [0, 1]. Fewer effective df means a wider CI means a harder
    accusation, which is the direction this toolkit errs in. Unlike
    `_effective_rows` this is not floored at an integer: χ² takes real df, and
    rounding down to 2 was itself a distortion at small k.
    """
    deff = 1.0 + (k - 1) * max(float(rho), 0.0)
    return max(1.0, k / deff)


def _exact_tau_ci(z2_arr: np.ndarray, df: float, ci_level: float) -> tuple[float, float]:
    """CI for τ by inverting the χ² null. Closed form — no resampling.

    Under H0 each z² ~ χ²_1, and a precision multiplier τ shrinks the z's by τ,
    so z² = χ²_1 / τ². Hence with S = df·mean(z²),

        τ²·S ~ χ²_df    ⇒    τ² ∈ [ χ²_df(α/2) / S , χ²_df(1−α/2) / S ]

    THIS REPLACES A PERCENTILE BOOTSTRAP THAT COULD NOT WORK AT SMALL k. The
    bootstrap resampled k values from k values, so a few similar z² gave a
    spuriously TIGHT CI around a large τ̂ — precisely the `ci_lo > 2`
    fabrication-grade trigger. MEASURED on honest tables (4,000 sims/cell), the
    fraction accused:

        k     bootstrap    exact χ²
        2       35.9%        5.2%
        3       27.6%        5.0%
        12       5.4%        5.1%

    The bootstrap is calibrated only where it was never needed. The exact null
    holds the nominal rate at every k, and costs NO detection: a hard
    under-dispersion signature is caught 100% of the time by both, at every k.

    Concretely, on a real k=2 table from the cerebrolysin corpus (z² = 0.237,
    0.511) the bootstrap returned [1.40, 2.06] and the tool accused
    `suspicious`; the exact CI is [0.26, 3.14] and there is no finding at all.
    """
    m = float(np.mean(z2_arr))
    if m <= 0:
        return float("inf"), float("inf")
    S = df * m
    alpha = 1 - ci_level
    lo2 = float(stats.chi2.ppf(alpha / 2, df)) / S
    hi2 = float(stats.chi2.ppf(1 - alpha / 2, df)) / S
    return math.sqrt(max(lo2, 0.0)), math.sqrt(max(hi2, 0.0))


def _bootstrap_tau_ci(
    z2_arr: np.ndarray,
    n_draw: int,
    num_bootstrap: int,
    ci_level: float,
    rng: np.random.Generator,
) -> tuple[float, float]:
    """SUPERSEDED percentile bootstrap CI — reported for audit, never for a verdict.

    Kept so a reader can see what the verdict USED to be read off; see
    `_exact_tau_ci` for why it was replaced and by how much it was wrong.
    """
    boot = np.empty(num_bootstrap, dtype=float)
    for b in range(num_bootstrap):
        idx = rng.integers(0, len(z2_arr), size=n_draw)
        boot[b] = _precision_multiplier(z2_arr[idx])
    alpha = (1 - ci_level) / 2
    return float(np.quantile(boot, alpha)), float(np.quantile(boot, 1 - alpha))


#: Upper-tail Simes threshold. Deliberately loose (fires on ~10% of honest
#: tables under the null) because the guarded outcome is `indeterminate`
#: with a named next instrument, never an accusation; the measured miss it
#: exists to stop scored 0.057.
_SIMES_UPPER_ALPHA = 0.10


def table1_dispersion(
    rows: list[dict[str, Any]],
    num_bootstrap: int = 1_000,
    ci_level: float = 0.95,
    seed: int = 0,
    design: str | None = None,
    correlation: float | None = None,
    rho_grid: tuple[float, ...] = DEFAULT_RHO_GRID,
) -> dict:
    """Compute the Table 1 dispersion / precision multiplier.

    Args:
        rows: List of row specs (see `_row_to_p_value`).
        num_bootstrap: Resamples for the SUPERSEDED bootstrap CI, which is
            reported for audit only and no longer drives any verdict.
        ci_level: confidence level for the exact χ² CI on τ that the verdict IS
            read off. Default 0.95. Measured on honest tables, raising it from
            0.90 halves the false-accusation rate (5.1% → 2.5%) at no cost in
            detection; 0.99 was rejected because it collapses power at k = 2
            (a hard under-dispersion signature drops from 100% to 35.5%).
        seed: RNG seed for reproducibility.
        design: study design. Cluster-randomised, multi-site, stepped-wedge,
            crossover, matched, stratified and minimised allocation force
            baseline balance BY DESIGN and are refused. Leaving this unset caps
            the verdict below `highly_suspicious`.
        correlation: equicorrelation among the baseline rows, if known or
            estimable. When omitted, a sensitivity analysis is run across
            `rho_grid` and the verdict is read off a conservative rho.
        rho_grid: correlations spanned by the sensitivity analysis.

    Returns:
        dict with per-row p / z, the empirical mean(z²), the precision
        multiplier τ̂, its correlation-adjusted bootstrap CI, the CI
        sensitivity profile across ρ, the K-S test of p vs U(0, 1), and
        a severity verdict.
    """

    # SAME DESIGN GATE AS csf_test, and it was missing here.
    #
    # `csf.py` was rewritten because the uncorrected baseline test flagged a
    # correctly-randomised cluster trial about 71% of the time. This tool takes
    # the same Table 1 rows and asks the same question by a different route --
    # and had no gate at all, while `tool_reference.md` called it the PREFERRED
    # Table 1 omnibus. So the documentation steered the model from the guarded
    # tool to the unguarded one.
    #
    # Stratified and minimised allocation force baseline balance BY
    # CONSTRUCTION: high per-row p, tau-hat > 1, accusation, with no refusal
    # available.
    # RESOLVE the design, do not match the raw string. `design_key in
    # DEPENDENT_DESIGNS` only caught exact American-spelled keys, so free text a
    # model actually produces -- "cluster-randomised trial", "stratified block
    # randomisation" -- escaped the gate. `_resolve_design` substring-matches to
    # a canonical name (and returns None for anything unrecognised), which is the
    # same recognition csf.py was hardened to use. Reused here, both tools now
    # place a given design string identically.
    resolved_design = _resolve_design(design)
    if resolved_design in DEPENDENT_DESIGNS:
        return {
            "severity": "indeterminate",
            "applicable": False,
            "design": design,
            "explanation": (
                f"This is a {design} design, in which baseline observations are correlated "
                "BY DESIGN. Stratified, minimised, cluster and matched allocation force "
                "baseline balance by construction, which this test reads as under-dispersion. "
                "Not evaluated."
            ),
            "methodology": "Table 1 dispersion design-applicability gate.",
        }

    if not rows:
        return {"severity": "indeterminate",
                "explanation": "No rows provided.",
                "methodology": "Bayesian Table 1 dispersion needs ≥2 rows."}
    per_row: list[dict] = []
    p_values: list[float] = []
    z_values: list[float] = []
    z2_values: list[float] = []
    errors: list[str] = []

    for i, row in enumerate(rows):
        label = row.get("label", f"row_{i}")
        try:
            p, kind, raw = _row_to_p_value(row)
            z = _z_from_p_two_sided(p)
            per_row.append({
                "label": label,
                "kind": kind,
                "p_value": p,
                "z_two_sided": z,
                "z_squared": z * z,
            })
            p_values.append(p)
            z_values.append(z)
            z2_values.append(z * z)
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f"{label}: {e}")
            per_row.append({"label": label, "error": str(e)})

    if len(z2_values) < 2:
        return {"severity": "indeterminate",
                "explanation": f"Need ≥2 valid rows; have {len(z2_values)}. "
                              f"Errors: {errors}",
                "per_row": per_row, "errors": errors,
                "methodology": "Bayesian Table 1 dispersion: ≥2 rows required."}

    z2_arr = np.array(z2_values)
    p_arr = np.array(p_values)
    mean_z2 = float(np.mean(z2_arr))
    tau_hat = _precision_multiplier(z2_arr)

    # CI for τ from the EXACT χ² null, across a grid of plausible baseline
    # correlations.
    #
    # Two successive corrections live here. The first made the percentile
    # bootstrap resample the EFFECTIVE row count, because an i.i.d. resample was
    # anti-conservative in the one direction that matters: correlated rows are
    # more alike, so the observed spread of z² shrinks, so the CI narrows, so
    # `ci_lo > 2` fires MORE often on exactly the tables where the assumption
    # has failed.
    #
    # That fixed the ρ dependence but not the underlying problem, which is that
    # a percentile bootstrap CANNOT estimate the sampling distribution of τ̂ from
    # k points when k is small -- it resamples k values from k values. Measured,
    # it accused 35.9% of HONEST k=2 tables and 27.6% at k=3. mean(z²) has a
    # known null, so no resampling is needed at all: see `_exact_tau_ci`.
    rng = np.random.default_rng(seed)
    k = len(z2_arr)
    if correlation is None:
        # ρ = 0 always stays in the grid: the CI it produces is what the old
        # verdict was read off, so reporting it is what makes the correction
        # visible rather than silent.
        grid = tuple(sorted(set(rho_grid) | {VERDICT_RHO, 0.0}))
        rho_used = VERDICT_RHO
        rho_assumed = False
    else:
        grid = (0.0, float(correlation))
        rho_used = float(correlation)
        rho_assumed = True
    ci_profile = {
        round(r, 3): list(_exact_tau_ci(z2_arr, _effective_df(k, r), ci_level))
        for r in grid
    }
    ci_lo, ci_hi = ci_profile[round(rho_used, 3)]
    ci_lo_independent, ci_hi_independent = ci_profile[0.0]
    k_effective = _effective_rows(k, rho_used)
    df_effective = _effective_df(k, rho_used)
    # Reported so the change of method is visible rather than silent -- the same
    # reason ρ = 0 stays in the grid. It drives nothing.
    ci_bootstrap_superseded = list(_bootstrap_tau_ci(
        z2_arr, k_effective, num_bootstrap, ci_level, rng))

    # K-S test of p_values against Uniform(0, 1).
    ks = stats.kstest(p_arr, "uniform")
    ks_p = float(ks.pvalue)
    ks_stat = float(ks.statistic)

    # UPPER-TAIL SIMES on 1 - p: a concentrated cluster of near-1 baseline
    # p-values that the WHOLE-TABLE statistics wash out. Measured on the
    # apple-cider gold paper (2026-08-21): age/weight/height at p = 0.93 /
    # 0.99 / 0.99 beside eight unremarkable biochemical rows gave tau_hat =
    # 1.44 with CI [0.20, 2.82] and an internal csf_test similarity_p of
    # 0.19 -- every whole-table instrument diluted the trio, this tool
    # printed "consistent with random allocation", and the run published
    # the exact reassurance the fixture's gold review exists to catch.
    # Simes over the upper tail is scale-free and standard: with q_i = 1 -
    # p_i sorted ascending, min_i (k/i) * q_(i) is a valid p-value for
    # "SOME subset is too uniform" (0.057 on the measured case).
    q_sorted = sorted(1.0 - pv for pv in p_arr)
    simes_upper_p = float(min(
        (k / (i + 1)) * q for i, q in enumerate(q_sorted))) if k else 1.0

    # Severity.
    # Heuristic thresholds (also used in Bolland-style discussion):
    #   τ > 2 ⇒ strongly under-dispersed (Carlisle-style suspicion)
    #   τ > 1.5 ⇒ moderately under-dispersed
    #   τ < 0.5 ⇒ over-dispersed
    #
    # Escalation to `highly_suspicious` additionally requires the two
    # preconditions `csf_test` already enforces on this same evidence: a stated
    # design, and a result that does not depend on assuming the rows are
    # independent. Without both, the arithmetic may be extreme but the premise
    # is unverified, so the verdict caps at `suspicious` rather than at a
    # fabrication-grade accusation.
    #
    # The correlation-aware null is `csf_test`'s, run on these same p-values --
    # a second implementation of the Strube / Brown corrections here would be
    # one more thing to keep in step, and the point of the exercise is that the
    # two tools stop disagreeing.
    # RECOGNISED, not merely non-empty -- the identical fix csf.py carries. By
    # here the dependent designs are already gated out above, so `resolved_design
    # is not None` means a recognised INDEPENDENT design, and only that lifts the
    # cap. `bool(design_key)` let any string at all -- "quasi-randomised",
    # "observational cohort", a typo -- count as known and escalate an honest
    # under-dispersed table to `highly_suspicious`; the designs that would
    # explain baseline uniformity innocently are exactly the ones an
    # unrecognised string might be naming, so unknown keeps the cap on.
    design_known = resolved_design is not None
    csf = csf_test(p_values, design=design, correlation=correlation)
    csf_severity = str(csf.get("severity", ""))
    # `indeterminate` is CSF's specific verdict for "significant only if you
    # pretend the rows are independent" -- the inference that produced a 33.5%
    # false-positive rate at rho = 0.6. It also covers tables too small to
    # combine. Either way it is not a foundation for a fabrication claim.
    # `consistent` is included, and that used to be the hard call. It is CSF
    # affirmatively finding nothing -- a STRONGER no-finding than
    # `indeterminate` -- so letting it through while vetoing the weaker one was
    # backwards, and it was the mechanism behind every measured k = 3
    # fabrication-grade false accusation. It was not fixed sooner because the
    # obvious fix demoted Fujii 2005 (k = 4, csf `consistent`) from a pinned
    # `highly_suspicious`, i.e. reversed a calibrated true positive.
    #
    # THE EXACT CHI-SQUARE NULL DISSOLVED THAT TRADE-OFF. Fujii's own arithmetic
    # no longer escalates at all -- its honest CI is [0.42, 8.01] -- so the veto
    # has no victim left to claim, and closing it costs nothing.
    correlation_veto = csf_severity in ("indeterminate", "consistent")

    flags: list[str] = []
    if ci_lo > 2.0:
        # One branch, then the two caps applied uniformly below. Splitting this
        # three ways put the design-cap and correlation-veto EXPLANATIONS inside
        # the `ci_lo > 2` arm only, so once the exact null stopped routinely
        # clearing 2 the caveats silently stopped being printed on findings that
        # were still capped by them -- the cap survived, its stated reason did
        # not.
        severity = "suspicious" if (not design_known or correlation_veto) else "highly_suspicious"
        flags.append(
            f"Strong under-dispersion: τ̂ = {tau_hat:.2f} ({int(ci_level*100)}% CI "
            f"[{ci_lo:.2f}, {ci_hi:.2f}]). The lower CI exceeds 2 even after discounting "
            f"the {k} rows to the {df_effective:.2f} effective degrees of freedom they are "
            f"worth at ρ = {rho_used} — baseline values are far more uniform than chance "
            "allows."
        )
    elif tau_hat > 1.5 and ci_lo > 1.0:
        severity = "suspicious"
        flags.append(
            f"Moderate under-dispersion: τ̂ = {tau_hat:.2f} (CI "
            f"[{ci_lo:.2f}, {ci_hi:.2f}]). Baseline values appear more "
            "uniform than expected; warrants closer inspection."
        )
    elif ci_hi < 0.5:
        severity = "suspicious"
        flags.append(
            f"Over-dispersion: τ̂ = {tau_hat:.2f} (CI [{ci_lo:.2f}, "
            f"{ci_hi:.2f}]). Baseline values differ more than randomization "
            "should produce; possible randomization failure."
        )
    elif tau_hat > 1.5:
        # AN APPARENT SIGNAL THE DATA CANNOT SUPPORT. This is the exact
        # complement of the branch above: τ̂ looks under-dispersed but ci_lo ≤ 1,
        # so τ = 1 is not excluded. Calling that `consistent` would be a FALSE
        # ALL-CLEAR -- the second-worst output this toolkit can produce -- and
        # calling it `suspicious` would accuse on evidence that does not reach.
        #
        # Not hypothetical: Fujii 2005, the canonical fabrication case, is
        # k = 4, discounted to df = 1.60 for correlation, CI [0.42, 8.01].
        # Without this branch the tool called the textbook fraud example
        # `consistent`. Refusing is the honest verdict -- four correlated
        # baseline rows carry too little information to convict OR to clear,
        # which is why `csf_test` also finds nothing on the same rows.
        #
        # The guard is deliberately keyed on τ̂ and not on the CI width. Keying
        # it on width made `consistent` almost unreachable: at ρ = 0.5 the
        # effective df is bounded near 2 for ANY k, so honest 15-row tables
        # were refused too. A wide CI around τ̂ ≈ 1 is not a warning, it is just
        # a weak test with nothing to report.
        severity = "indeterminate"
        flags.append(
            f"Apparent under-dispersion this table cannot support: τ̂ = "
            f"{tau_hat:.2f}, but the CI [{ci_lo:.2f}, {ci_hi:.2f}] does not "
            f"exclude τ = 1. The {k} rows are worth {df_effective:.2f} effective "
            f"degrees of freedom at ρ = {rho_used}, too few to decide either "
            "way. NOT a clean bill of health, and NOT a finding."
        )
    else:
        severity = "consistent"
        # "does not distinguish", never "is consistent with random
        # allocation": the second is REASSURANCE, and rulebook rule 1 says
        # high baseline p-values are the red flag, never reassurance. The
        # measured failure above shipped the old sentence into a published
        # pass row on a paper whose gold review calls the baseline rigged.
        flags.append(
            f"τ̂ = {tau_hat:.2f} (CI [{ci_lo:.2f}, {ci_hi:.2f}]) does not "
            "distinguish this table from random allocation."
        )

    if ks_p < 0.001:
        flags.append(
            f"K-S test against U(0,1) rejects uniformity (D = {ks_stat:.3f}, "
            f"p = {ks_p:.4g}); supports dispersion finding."
        )
        if severity == "consistent":
            severity = "suspicious"

    if severity == "consistent" and simes_upper_p < _SIMES_UPPER_ALPHA:
        # NEVER escalates and NEVER accuses -- it withholds the all-clear
        # and names the calibrated instrument. Under the null this fires on
        # ~10% of honest tables, and its cost there is one row saying "run
        # csf_test", which the sweep prompt requires for a multi-arm Table 1
        # anyway.
        severity = "indeterminate"
        extreme = [r for r in per_row
                   if isinstance(r.get("p_value"), float)
                   and r["p_value"] >= 0.9]
        names = ", ".join(str(r.get("label")) for r in extreme) or "(none >= 0.9)"
        flags.append(
            f"NOT a clean bill of health: a subset of rows is more uniform "
            f"than the whole-table statistics reflect (upper-tail Simes p = "
            f"{simes_upper_p:.4f} on 1-p; rows at p >= 0.9: {names}). "
            "Whole-table combination dilutes a concentrated cluster, so run "
            "csf_test on the coherent subgroup the paper's design groups "
            "together (e.g. the anthropometric block) before treating this "
            "table as clear."
        )


    # The two caps, and their reasons, applied to EVERY accusatory path rather
    # than only to `ci_lo > 2`. Each states what would have to be true for the
    # finding to be innocent, which is the whole point of printing it. Placed
    # AFTER the K-S block because that block can escalate on its own, and an
    # escalation that skipped the caps would be an accusation with its own
    # caveats stripped off.
    if severity in ("suspicious", "highly_suspicious"):
        if not design_known:
            flags.append(
                "The study DESIGN was not supplied. Stratified, minimised, cluster "
                "and matched allocation all force baseline balance by construction "
                "and would explain this pattern innocently, so the verdict is "
                "capped below `highly_suspicious` until the design is known."
            )
        if correlation_veto:
            flags.append(
                "The correlation-aware combination of these same baseline p-values "
                f"does not reach a robust finding (csf_test: {csf_severity}). "
                "Baseline rows measure overlapping quantities, so uniformity that "
                "survives only under an independence assumption is not evidence of "
                "fabrication. Capped below `highly_suspicious`."
            )

    explanation = " ".join(flags)

    out = {
        "severity": severity,
        "explanation": explanation,
        "n_rows": len(rows),
        "n_valid": len(z2_values),
        "errors": errors,
        "per_row": per_row,
        "design": design,
        "mean_z_squared": mean_z2,
        "precision_multiplier": tau_hat,
        "precision_multiplier_ci": [ci_lo, ci_hi],
        "precision_multiplier_ci_under_independence": [ci_lo_independent, ci_hi_independent],
        "ci_sensitivity_profile": ci_profile,
        "ci_method": "exact_chi2",
        "precision_multiplier_ci_bootstrap_superseded": ci_bootstrap_superseded,
        "correlation_used": rho_used,
        "correlation_assumed": rho_assumed,
        "effective_rows": k_effective,
        "effective_df": df_effective,
        "csf_cross_check": {
            "severity": csf_severity,
            "similarity_p": csf.get("similarity_p"),
            "similarity_p_under_independence": csf.get("similarity_p_under_independence"),
        },
        "ci_level": ci_level,
        "num_bootstrap": num_bootstrap,
        "ks_p_value": ks_p,
        "ks_statistic": ks_stat,
        "upper_tail_simes_p": simes_upper_p,
        "p_values": p_values,
        "z_values": z_values,
        "methodology": (
            "Bayesian Table 1 dispersion (Heathers/Bolland-style): each row "
            "→ test p-value (one-way ANOVA for continuous, χ² for categorical) "
            "→ two-sided z = Φ⁻¹(1 − p/2). Under proper randomization "
            "E[z²] = 1; precision multiplier τ̂ = √(1 / mean(z²)) > 1 ⇒ "
            "under-dispersion (suspicious uniformity), τ̂ < 1 ⇒ over-"
            "dispersion. The CI on τ̂ inverts the EXACT χ² null — τ²·df·mean(z²) "
            f"~ χ²_df — at df = {df_effective:.2f}, the {k} rows discounted for "
            f"equicorrelation ρ = {rho_used} (design effect 1 + (k−1)ρ, the "
            "Strube 1985 identity csf_test uses, kept here in place of the "
            "exact-for-normal 1 + (k−1)ρ² because it is the wider, "
            "harder-to-accuse choice); the CI across the whole ρ grid is "
            "reported. A percentile bootstrap was used until it was measured to "
            "accuse 35.9% of honest k = 2 tables and 27.6% at k = 3; it is still "
            "reported for audit but drives nothing. Independent K-S test of p-values against "
            "U(0, 1). `highly_suspicious` requires a stated design and a "
            "finding that survives csf_test's correlation-aware null on the "
            "same p-values. Approximate port of Bolland et al. 2022; for "
            "definitive analysis use the Bolland Shiny tool."
        ),
        "caveat": (
            "Baseline rows within one table are usually correlated; assuming otherwise "
            "inflates the false-positive rate to roughly 33% at ρ = 0.6 and ~71% on "
            "cluster-randomised trials. Evaluated at ρ = "
            f"{rho_used}"
            + ("" if rho_assumed else " (a conservative but realistic average for a clinical Table 1)")
            + ". Under-dispersion that appears only under an independence assumption, or "
            "in a trial whose design was never stated, is reported below "
            "`highly_suspicious` rather than as a fabrication-grade finding."
        ),
    }

    # QUARANTINE RELEASED (2026-08-10). Both quarantined paths existed because
    # the percentile bootstrap CI was miscalibrated, and both are fixed at the
    # source by `_exact_tau_ci` rather than suppressed downstream:
    #
    #   1. SMALL k -- the reason the accusation was withheld was that the
    #      bootstrap accused 35.9% of honest k=2 tables and 27.6% at k=3. Under
    #      the exact null those are 2.5% and 2.8% at the default ci_level, and
    #      fabrication-grade lands at 0.6% and 0.25%. The quarantine comment
    #      named this exact redesign ("a real null (chi2_k/k) rather than
    #      bootstrap quantiles") as its release condition.
    #   2. CSF `consistent` NOT VETOING -- now vetoed, see `correlation_veto`.
    #      Its blocker was the Fujii demotion, which the exact null removed.
    #
    # Detection is unaffected: a hard under-dispersion signature is still caught
    # 100% of the time at every k from 2 to 12. `test_table1_dispersion.py`
    # pins these rates so the release cannot silently regress.
    return out
