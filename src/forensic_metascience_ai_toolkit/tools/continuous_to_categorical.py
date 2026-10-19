"""
Continuous → categorical proportion plausibility.

Heathers (2025) §"Within papers — continuous to categorical transforms":
when a paper reports a categorical summary (e.g., "35.5% of children were
underweight, defined as WAZ < -2") alongside the continuous distribution
(mean WAZ = -1.67, SD = 0.89, n = 172), the categorical figure must be
consistent with what the continuous distribution would produce.

Implementation. Two complementary checks:

(A) **Analytic (binomial)**. Under the assumption that the underlying
    variable is normal with the reported (μ, σ), the theoretical
    population proportion meeting the threshold is

        p_thresh = Φ((threshold - μ) / σ)            if direction == "below"
                 = 1 − Φ((threshold - μ) / σ)        if direction == "above"

    The reported sample proportion is observed_count / n where
    observed_count = round(reported_proportion · n). A two-sided
    binomial test (n, p_thresh) on observed_count gives a tight,
    parametric p-value.

(B) **Monte Carlo confirmation**. Draw B replicates of n samples from
    N(μ, σ), compute the sample proportion in each, and report the
    empirical distribution and a two-sided empirical p-value.

Both are returned. (A) is the headline test; (B) is a sanity check
that exposes any binomial-approximation issues at small n.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
from scipy import stats



def check_proportion_from_normal(
    reported_proportion: float,
    mean: float,
    sd: float,
    n: int,
    threshold: float,
    direction: Literal["below", "above"] = "below",
    num_simulations: int = 10_000,
    summary: str = "arithmetic",
    seed: int = 0,
) -> dict:
    """Test whether a reported proportion at a threshold is consistent with
    an assumed-normal continuous distribution.

    Args:
        reported_proportion: The reported proportion (0..1) above/below threshold.
        mean: Reported sample mean of the continuous variable.
        sd: Reported sample SD.
        n: Sample size.
        threshold: Cut-off value defining the categorical bin.
        direction: "below" if the proportion counts values < threshold,
                   "above" if it counts values > threshold.
        num_simulations: MC replicate count.
        seed: RNG seed.

    Returns:
        dict with the analytic binomial result, MC result, and severity.
    """
    # A GEOMETRIC MEAN IS NOT THE MEAN THIS TEST NEEDS.
    #
    # Right-skewed quantities -- biomarkers, titers, concentrations, exposures,
    # costs -- are conventionally summarised as a GEOMETRIC mean with a
    # geometric SD, and printed beside the prevalence above a cut-off. Both are
    # called "mean" and "SD" on the page, and the function had no way to say
    # which it was given.
    #
    # MEASURED, on an honest paper: GM 10.0 (GSD 3.0) with a true P(X > 30) of
    # 0.159, verified by 200,000 draws. Fed as `mean`/`sd` it returns
    # `highly_suspicious` -- the branch reserved for a proportion outside the
    # DISTRIBUTION-FREE bound, whose explanation says "with no distributional
    # assumption at all". There was an assumption: that the two numbers handed
    # over were arithmetic.
    #
    # Converted rather than refused, because the conversion is EXACT under
    # lognormality and the resulting bound is then the one the paper's own
    # numbers imply. The severity is capped afterwards, because the lognormal
    # model is OURS -- the same rule `bound_source` encodes elsewhere.
    _geometric = str(summary or "").strip().lower().startswith("geom")
    _summary_note = ""
    if _geometric:
        if not (mean > 0 and sd > 1):
            return {
                "severity": "indeterminate", "applicable": False,
                "check": "proportion_from_continuous",
                "explanation": (
                    "a geometric summary needs GM > 0 and GSD > 1; a GSD is a "
                    "multiplicative factor and cannot be 1 or less."),
            }
        if not threshold > 0:
            return {
                "severity": "indeterminate", "applicable": False,
                "check": "proportion_from_continuous",
                "explanation": (
                    "a geometric summary describes a strictly positive "
                    "variable, so a threshold of "
                    f"{threshold} cannot be placed on its scale."),
            }
        # A CHANGE OF VARIABLES, NOT A NEW MODEL. A lognormal variable is
        # NORMAL IN LOGS, so taking logs of the geometric summary and of the
        # threshold puts the existing machinery on exactly the right scale:
        #
        #     P(X > t) = 1 - Phi( (ln t - ln GM) / ln GSD )
        #
        # Converting GM/GSD to an ARITHMETIC mean and SD and then applying a
        # NORMAL model is the wrong move and was my first attempt: it predicted
        # 33.8% where the paper's own numbers give 15.9%, turning an exactly
        # correct paper into `suspicious` -- and it let a genuinely wrong 60%
        # pass as `consistent`. In log space both come out right.
        _gm, _gsd, _t = mean, sd, threshold
        mean, sd = math.log(_gm), math.log(_gsd)
        threshold = math.log(_t)
        _summary_note = (
            f" The paper reports a GEOMETRIC summary (GM {_gm:g}, GSD {_gsd:g}), "
            f"so the test was run on the LOG scale, where a lognormal variable "
            f"is normal: ln GM = {mean:.4g}, ln GSD = {sd:.4g}, ln threshold = "
            f"{threshold:.4g}. That lognormal model is ours rather than the "
            f"paper's, so the verdict is capped.")

    # PRECONDITION FAILURES ARE REFUSALS, NOT VERDICTS.
    #
    # Both branches below used to return `impossible` -- the strongest claim the
    # system makes -- while `n < 1` ten lines down correctly returned
    # `indeterminate` for exactly the same kind of problem, and debit.py:124-144
    # already handles the identical situation ("a mean outside [0,1] means DEBIT
    # was pointed at non-binary data -- a MISAPPLICATION -- not that the paper is
    # impossible") as `indeterminate`.
    #
    # A proportion outside [0, 1] is almost always a CALLING error: the paper
    # printed "35.5%" and it was handed over as 35.5 instead of 0.355. Verified:
    # check_proportion_from_normal(35.5, mean=1.0, sd=1.0, n=100, threshold=0.5)
    # returned `impossible`, an accusation manufactured entirely by a unit
    # mismatch on our side. sd <= 0 is the same shape of problem -- an SD of 0
    # means the value was not extracted, or the variable is degenerate, so the
    # normal model this check rests on does not exist and cannot be evaluated.
    if not (0.0 <= reported_proportion <= 1.0):
        return {"severity": "indeterminate",
                "explanation": (
                    f"reported_proportion {reported_proportion} is outside [0, 1], so it is "
                    "not a proportion. It was most likely passed as a PERCENTAGE -- divide "
                    "by 100. Not evaluated; this says nothing about the paper."
                ),
                "methodology": "Precondition guard: the input is not a proportion."}
    if sd <= 0:
        return {"severity": "indeterminate",
                "explanation": (
                    f"SD must be positive (got {sd}); with no dispersion there is no normal "
                    "distribution to compare the categorical summary against. Not evaluated."
                ),
                "methodology": "Precondition guard: no distribution to test."}
    if n < 1:
        return {"severity": "indeterminate",
                "explanation": "n must be ≥ 1.",
                "methodology": "Trivial precondition."}
    if direction not in ("below", "above"):
        return {"severity": "indeterminate",
                "explanation": "direction must be 'below' or 'above'.",
                "methodology": ""}

    # Theoretical proportion under N(mean, sd).
    z = (threshold - mean) / sd
    cdf_below = stats.norm.cdf(z)
    p_thresh = float(cdf_below) if direction == "below" else float(1.0 - cdf_below)

    observed_count = round(reported_proportion * n)
    observed_count = max(0, min(n, observed_count))

    # Analytic two-sided binomial test.
    binom = stats.binomtest(observed_count, n, p=p_thresh, alternative="two-sided")
    binom_p = float(binom.pvalue)

    # 95% CI for the binomial proportion.
    ci = binom.proportion_ci(confidence_level=0.95, method="exact")
    binom_ci_lo = float(ci.low)
    binom_ci_hi = float(ci.high)

    # Monte Carlo confirmation.
    rng = np.random.default_rng(seed)
    samples = rng.normal(loc=mean, scale=sd, size=(num_simulations, n))
    if direction == "below":
        counts = (samples < threshold).sum(axis=1)
    else:
        counts = (samples > threshold).sum(axis=1)
    sim_props = counts / n
    sim_mean = float(sim_props.mean())
    sim_lo = float(np.quantile(sim_props, 0.025))
    sim_hi = float(np.quantile(sim_props, 0.975))

    # Empirical two-sided p-value.
    extreme_low = float((sim_props <= reported_proportion + 1e-12).mean())
    extreme_high = float((sim_props >= reported_proportion - 1e-12).mean())
    empirical_p = min(1.0, 2 * min(extreme_low, extreme_high))

    # DISTRIBUTION-FREE envelope (Cantelli's inequality). The normal model above
    # is only OURS: predicting a proportion of RAW observations past a threshold
    # needs raw-data normality, and a parametric test in the paper does not supply
    # it -- a t-test/ANOVA warrants normality of the sampling distribution of the
    # MEANS (CLT), while the raw values stay as skewed as they are. Skewness is
    # therefore a fully innocent explanation for a mismatch with the normal
    # prediction, and (verified: an ordinary lognormal with mean 50, SD 40 has a
    # legitimate 2.8% above 150 that the normal model flagged at p = 1e-8) a
    # normal-only mismatch may NOT be accusation-grade. What needs no assumption
    # is Cantelli's bound: no distribution with this mean and SD places more than
    # 1/(1+d^2) of its mass d SDs into the tail. Only a reported proportion that
    # violates THAT -- inconsistent with the reported mean/SD under EVERY
    # distribution, even allowing for binomial sampling -- earns highly_suspicious.
    d = (threshold - mean) / sd
    cantelli = 1.0 / (1.0 + d * d)
    if direction == "above":
        df_max = cantelli if d >= 0 else 1.0
        df_min = (1.0 - cantelli) if d < 0 else 0.0
    else:  # below
        df_max = cantelli if d <= 0 else 1.0
        df_min = (1.0 - cantelli) if d > 0 else 0.0
    df_violation = (binom_ci_lo > df_max + 1e-9) or (binom_ci_hi < df_min - 1e-9)
    inconsistent_with_normal = binom_p < 0.01

    if df_violation:
        severity = "highly_suspicious"
        explanation = (
            f"Reported proportion {reported_proportion:.4f} ({observed_count}/{n}) is "
            f"outside what ANY distribution with mean {mean} and SD {sd} can produce: "
            f"Cantelli's inequality bounds the proportion {direction} {threshold} to "
            f"[{df_min:.4f}, {df_max:.4f}], and even the reported proportion's 95% CI "
            f"[{binom_ci_lo:.4f}, {binom_ci_hi:.4f}] falls outside it. The categorical and "
            "continuous summaries are mutually inconsistent, with no distributional "
            "assumption at all."
        )
    elif inconsistent_with_normal:
        severity = "suspicious"
        explanation = (
            f"Reported proportion {reported_proportion:.4f} ({observed_count}/{n}) differs "
            f"from a NORMAL model's prediction ({p_thresh:.4f}; binomial p = {binom_p:.4g}), "
            f"but it lies within the distribution-free bound [{df_min:.4f}, {df_max:.4f}], so "
            "a skewed underlying distribution fully explains it. A parametric test in the "
            "paper would warrant normality of the sampling distribution of the MEANS (CLT), "
            "not of the raw values this proportion counts -- so skew here is not a reporting "
            "error. A question, not an accusation."
        )
    else:
        severity = "consistent"
        explanation = (
            f"Reported proportion {reported_proportion:.4f} ({observed_count}/"
            f"{n}) is consistent with a normal model: theoretical proportion "
            f"{direction} {threshold} = Φ-based {p_thresh:.4f} (binomial p = "
            f"{binom_p:.4g}, 95% CI {binom_ci_lo:.4f}–{binom_ci_hi:.4f})."
        )

    if _geometric:
        # OUR distributional model may not license the strongest verdict.
        if severity == "highly_suspicious":
            severity = "suspicious"
        explanation = explanation + _summary_note

    return {
        "severity": severity,
        "explanation": explanation,
        "summary_scale": "geometric" if _geometric else "arithmetic",
        "reported_proportion": reported_proportion,
        "observed_count": observed_count,
        "n": n,
        "threshold": threshold,
        "direction": direction,
        "theoretical_proportion": p_thresh,
        "distribution_free_bound_95": [df_min, df_max],
        "distribution_free_violation": df_violation,
        "binomial_p_two_sided": binom_p,
        "binomial_ci_95": [binom_ci_lo, binom_ci_hi],
        "mc_mean_proportion": sim_mean,
        "mc_ci_95": [sim_lo, sim_hi],
        "mc_empirical_p_two_sided": empirical_p,
        "mc_num_simulations": num_simulations,
        "z_score": float(z),
        "methodology": (
            "Continuous→categorical plausibility: under the assumed normal "
            f"N({mean}, {sd}²), theoretical P(X {direction} {threshold}) = "
            f"{p_thresh:.4f}. Reported proportion = {observed_count}/{n} = "
            f"{reported_proportion:.4f}. Two-sided binomial test gives p = "
            f"{binom_p:.4g}; Monte Carlo with {num_simulations} replicates "
            f"of n = {n} gives 95% CI [{sim_lo:.4f}, {sim_hi:.4f}]."
        ),
    }
