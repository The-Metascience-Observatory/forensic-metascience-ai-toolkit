"""
Variance-dispersion analysis: are these standard deviations too similar?

Hartgerink, Voelkel, Wicherts & van Assen (2019), "Detection of data
fabrication using statistical tools" (Studies 1-2); the statistic is the one
Simonsohn (2013) used in the Smeesters case.

WHY THIS EXISTS
---------------
Sample variances are themselves random. Run the same experiment on several
groups and you do not merely get different MEANS -- you get different SDs, and
those SDs scatter by a knowable amount. Fabricators reliably add noise to the
means, because everyone knows means vary; they forget that the DISPERSION
measures need their own noise. The result is a set of SDs that sit closer
together than sampling error allows.

Hartgerink et al. is the only head-to-head validation of fabrication detectors
against both genuine data and data that real researchers were PAID A BONUS to
fabricate undetectably. Diagnostic performance (AUROC, Study 2, raw data):

| method                              | AUROC |
|-------------------------------------|-------|
| variance analysis (max_z - min_z)   | 1.00  |
| effect size (r)                     | 0.981 |
| multivariate associations           | 0.549-0.833 |
| terminal digits                     | 0.383-0.511  (chance)
| Newcomb-Benford leading digits      | 0.024-0.156  (WORSE than chance)

This module implements the top row. The bottom two rows are why this repository
has no digit-preference or Benford tool, and `evaluation/corpus_run.py` records
that absence as a decision rather than an oversight.

THE STATISTIC (paper Eqs. 3-5)
------------------------------
Under normality, a sample variance is chi-square distributed:

    s_j^2 ~ sigma^2 * chi2_{n_j-1} / (n_j-1)

sigma^2 is unknown, so estimate it with the within mean square and divide it
out; the weighted mean of the standardised variances is then 1 by construction,
the scale cancels, and only the SPREAD is left:

    MS_w  = sum (n_j-1) s_j^2 / sum (n_j-1)
    z_j^2 = s_j^2 / MS_w

Spread is measured as `max_z - min_z`, its null distribution is obtained by
parametric bootstrap from the chi-square above, and the p-value is the fraction
of honest draws at least as tightly clustered as what the paper reported. It is
ONE-SIDED, for excessive consistency.

`max_z - min_z` rather than `SD_z` because the paper measured the range as more
robust to heterogeneity (AUROC 0.827 vs 0.761 in Study 1) and preregistered it
for Study 2. `SD_z` is returned as a secondary diagnostic and drives no verdict.

Reproduces the published worked example: Smeesters' three SDs 25.09, 24.58,
25.65 at n=15 give p ~ 0.012, against the 1.21% printed in Simonsohn (2013) and
quoted by Hartgerink et al.

WHAT THIS TOOL MAY NOT DO
-------------------------
**It never convicts.** The paper's AUROC of 1.00 is a RELATIVE result: in Study
2 every dataset, genuine and fabricated alike, had p < .006 against the
theoretical null, and only comparing the two groups separated them. The authors
say the method "is particularly difficult to apply if no reference distribution
of (arguably) genuine data is available" and that the perfect score "is likely
to be sample specific" -- it was measured on psychology response times with 25
SDs per set. So every result carries `reference_required: True` and severity is
capped at `suspicious`. This tool ranks candidates for a human to look at.

That ceiling is reinforced by the paper's own arithmetic on positive predictive
value, which is the most transferable thing in it: perfect sensitivity with a 5%
false-positive rate, at a 2% base rate of fabrication, yields a PPV of 29% --
roughly one in three accusations wrong. "Hence, we do not recommend attempting
to detect data fabrication on statistical methods alone."

THE THREE GUARDS, AND THE MEASUREMENTS THAT SET THEM
----------------------------------------------------
1. **k >= 3 groups.** Measured false-positive / power at n=25 per group (400
   replicates, honest SDs drawn from the chi-square null vs fabricated SDs
   pinned within +/-2%):

       k:      3      4      5      8     12     20
       FP:   5.8%   6.0%   3.0%   6.0%   4.5%   5.0%
       power: 100%   100%   100%   100%   100%   100%

   Calibrated and fully powered from k=3 up. k=2 calibrates too, but a range
   over two points is just their difference and carries no shape information,
   so it is refused and told why.

2. **`homogeneous_variances` is REQUIRED, and it gates the REASSURING verdict
   too.** The paper's own PREREGISTERED analysis scored AUROC 0.264 -- inverted,
   far worse than chance -- purely from assuming homogeneity where it did not
   hold. Relaxing the assumption moved the identical statistic to 0.761/0.827.

   Measured here, on honest data with genuinely heterogeneous population
   variances, wrongly asserting homogeneity flagged 0.0% as too-consistent,
   against 6.7% when the assumption held. So the failure mode is a FALSE
   NEGATIVE: the test goes blind. That is why an unset guard cannot return
   `consistent` -- a silent all-clear from a blinded test is the exact failure
   the preflight gate exists to prevent elsewhere in this codebase.

3. **Printed precision.** Coarsely printed SDs collide into identical values,
   and identical SDs are this test's fabrication signature. Measured FP by
   rounding step relative to the SD (n=25, k=6, 1500 replicates):

       step/SD:  0.67   0.50   0.33   0.25   0.10   0.05
       FP:       3.7%  60.3%  17.8%   5.3%   4.7%   5.0%

   At SD ~ 2.0 printed to zero decimals, 60.2% of HONEST draws produce six
   identical SDs. The tool would report a fabrication signature manufactured
   entirely by rounding. Refused above `_MAX_GRANULARITY`.

   Precision comes from the printed LITERAL via `rounding.decimals_of_text`,
   never from the parsed float -- `str(3.0)` is "3.0", which reads as one
   decimal and shrinks the step tenfold. That trap is documented at length in
   `tools/rounding.py`.

Severity is additionally capped by the design gate shared with `csf.py`:
cluster, multi-site, stepped-wedge, crossover, matched, stratified and minimised
allocation force balance BY CONSTRUCTION, which this test reads as
under-dispersion. Those refuse outright rather than flag.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import numpy as np

from .csf import DEPENDENT_DESIGNS, _resolve_design
from .rounding import decimals_of_text
from .severity import CONSISTENT, INDETERMINATE, SUSPICIOUS, refuse_if_nonfinite

#: Minimum number of groups. See guard 1 in the module docstring: k=2 is
#: calibrated but its "range" is a single difference, carrying no shape.
MIN_GROUPS = 3

#: Largest tolerated rounding step relative to the SD. Measured: 0.25 holds the
#: nominal rate (5.3%), 0.33 does not (17.8%), 0.50 is catastrophic (60.3%).
_MAX_GRANULARITY = 0.25

#: Bootstrap draws for the null. 100,000 is what the paper used; the Monte Carlo
#: SE on a p near 0.01 is then ~0.0003, well inside the reporting precision.
DEFAULT_ITERATIONS = 100_000

#: Verdict thresholds, two-tier. Measured false-positive rates on honest
#: chi-square SDs (n=25, 1200 replicates per cell):
#:
#:     k:                 3      6     10     20
#:     p < 0.01:       0.7%   1.2%   1.0%   0.7%
#:     p < 0.05:       5.2%   4.6%   5.9%   4.8%
#:
#: Both bands are calibrated. The middle band exists because the canonical
#: published detection -- Smeesters' three SDs, which Simonsohn reported at
#: 1.21% -- lands at p ~ 0.012 and would otherwise be reported as `consistent`,
#: i.e. this tool would return a clean bill of health on the case that made the
#: method's reputation. `indeterminate` says "worth a look" without accusing,
#: which is the role a screening test capped at `suspicious` should play.
_P_SUSPICIOUS = 0.01
_P_INDETERMINATE = 0.05


def _standardized_variances(
    sds: Sequence[float], ns: Sequence[int]
) -> tuple[np.ndarray, float]:
    """Standardised variances z^2 and the within mean square (paper Eqs. 4-5).

    `MS_w` estimates the common population variance; dividing by it makes the
    weighted mean of z^2 equal 1, so absolute scale drops out and only relative
    spread survives. Returns `(z2, MS_w)`.
    """
    s = np.asarray(sds, dtype=float)
    n = np.asarray(ns, dtype=float)
    df = n - 1.0
    ms_w = float(np.sum(df * s**2) / np.sum(df))
    if ms_w <= 0:
        return np.array([]), 0.0
    return (s**2) / ms_w, ms_w


def _dispersion(z2: np.ndarray, measure: str = "range") -> float:
    """Spread of the standardised variances.

    `range` is `max_z - min_z`, the paper's preregistered measure and the one
    the verdict is read off; `sd` is the standard deviation of z^2, reported as
    a secondary diagnostic only.
    """
    if z2.size == 0:
        return float("nan")
    if measure == "sd":
        return float(np.std(z2, ddof=1))
    return float(z2.max() - z2.min())


def _null_distribution(
    ns: Sequence[int],
    iterations: int,
    rng: np.random.Generator,
    measure: str = "range",
) -> np.ndarray:
    """Parametric bootstrap of the dispersion statistic under H0 (paper Eq. 3).

    Draws `s_j^2 ~ chi2_{n_j-1}/(n_j-1)` (sigma^2 = 1 without loss of
    generality: it cancels in the standardisation), standardises each draw the
    same way the observed data are standardised, and returns the dispersion of
    each replicate.
    """
    n = np.asarray(ns, dtype=float)
    df = n - 1.0
    draws = rng.chisquare(df, size=(iterations, len(n))) / df
    ms_w = np.sum(df * draws, axis=1) / np.sum(df)
    z2 = draws / ms_w[:, None]
    if measure == "sd":
        return np.std(z2, axis=1, ddof=1)
    return z2.max(axis=1) - z2.min(axis=1)


def _granularity_ratios(
    sds: Sequence[float], sd_texts: Optional[Sequence[Any]]
) -> tuple[list[Optional[float]], list[Optional[int]]]:
    """Rounding step relative to each SD, from the PRINTED literal.

    Returns `(ratios, decimals)`. An entry is None where the precision could not
    be read -- "unknown precision" and "printed to zero decimals" are different
    claims and only one of them licenses a verdict, which is why
    `decimals_of_text` returns None rather than a default.
    """
    ratios: list[Optional[float]] = []
    decimals: list[Optional[int]] = []
    for i, sd in enumerate(sds):
        text = None
        if sd_texts is not None and i < len(sd_texts):
            text = sd_texts[i]
        dp = decimals_of_text(text) if text is not None else None
        decimals.append(dp)
        if dp is None or sd <= 0:
            ratios.append(None)
            continue
        ratios.append((10.0 ** (-dp)) / float(sd))
    return ratios, decimals


def _refusal(explanation: str, criterion: str, **extra: Any) -> dict:
    """A structured refusal naming the criterion that failed.

    Guards return rather than raise (house rule), and every refusal says WHICH
    criterion tripped so a reader can override it deliberately.
    """
    out = {
        "severity": INDETERMINATE,
        "applicable": False,
        "criterion": criterion,
        "explanation": explanation,
        "reference_required": True,
        "methodology": "Variance-dispersion applicability gate.",
    }
    out.update(extra)
    return out


def _applicability(
    sds: Sequence[float],
    ns: Sequence[int],
    design: Optional[str],
    homogeneous_variances: Optional[bool],
    granularity: Sequence[Optional[float]],
) -> Optional[dict]:
    """Every precondition, in one place. Returns a refusal dict, or None.

    Order matters: the cheapest and most categorical refusals come first, so a
    cluster-randomised trial is never told about its sample sizes.
    """
    # (d) Design gate. RESOLVE the design rather than matching the raw string --
    # free text a model actually produces ("cluster-randomised trial",
    # "stratified block randomisation") escapes exact-key matching, which is the
    # bug csf.py was hardened against and whose fix this reuses.
    resolved = _resolve_design(design)
    if resolved in DEPENDENT_DESIGNS:
        return _refusal(
            f"This is a {design} design, in which group variances are constrained "
            "BY DESIGN. Cluster, multi-site, stepped-wedge, crossover, matched, "
            "stratified and minimised allocation force baseline balance by "
            "construction, which this test reads as under-dispersion. Not evaluated.",
            "design",
            design=design,
        )

    # (a) Enough groups to have a shape.
    if len(sds) < MIN_GROUPS:
        return _refusal(
            f"Needs at least {MIN_GROUPS} groups; {len(sds)} given. With two groups "
            "the range of standardised variances is just their difference and "
            "carries no information about the SHAPE of the dispersion, so no "
            "excessive-consistency verdict is available.",
            "n_groups",
            n_groups=len(sds),
        )

    if len(ns) != len(sds):
        return _refusal(
            f"Got {len(sds)} SDs but {len(ns)} sample sizes; they must correspond "
            "one-to-one.",
            "input_shape",
        )

    # (e) The arithmetic has to be defined.
    if any(float(s) <= 0 for s in sds):
        return _refusal(
            "Every SD must be positive. A zero or negative SD is not a dispersion "
            "estimate, and standardising by it is undefined.",
            "nonpositive_sd",
        )
    if any(int(n) < 2 for n in ns):
        return _refusal(
            "Every group needs n >= 2; a variance from one observation has no "
            "degrees of freedom.",
            "sample_size",
        )

    # (b) The assumption the paper got wrong, which blinds the test when unset.
    if homogeneous_variances is None:
        return _refusal(
            "`homogeneous_variances` was not stated. This test assumes the groups "
            "share a population variance; the source paper's own PREREGISTERED "
            "analysis scored AUROC 0.264 -- inverted, worse than chance -- purely "
            "from asserting that wrongly. Measured here, a violated assumption "
            "makes the test BLIND (0.0% detection) rather than accusatory, so an "
            "unstated assumption cannot return `consistent` either: a silent "
            "all-clear from a blinded test is worse than no answer. State whether "
            "the groups are comparable units measured on one instrument.",
            "homogeneous_variances",
        )
    if homogeneous_variances is False:
        return _refusal(
            "`homogeneous_variances=False`: the groups are not expected to share a "
            "population variance, so the chi-square null this test inverts does not "
            "hold and its verdict would be uninterpretable in either direction.",
            "homogeneous_variances",
        )

    # (c) Printed precision -- the guard only measurement finds.
    known = [g for g in granularity if g is not None]
    if not known:
        return _refusal(
            "Printed precision of the SDs is unknown. Pass the SD literals as "
            "`sd_texts` (e.g. ['2.11', '2.08']). Coarse rounding collapses genuine "
            "variation into identical SDs -- at SD ~ 2.0 printed to zero decimals, "
            "60.2% of honest draws yield six identical SDs -- so without the "
            "printed precision this test cannot tell a fabrication signature from "
            "a rounding artifact.",
            "precision_unknown",
        )
    worst = max(known)
    if worst > _MAX_GRANULARITY:
        return _refusal(
            f"The SDs are printed too coarsely: the rounding step is {worst:.2f} of "
            f"the SD (limit {_MAX_GRANULARITY}). Measured false-positive rate rises "
            "to 17.8% at 0.33 and 60.3% at 0.50, because rounding alone drives "
            "honest SDs onto identical values -- which is precisely this test's "
            "fabrication signature. Refusing rather than reporting an artifact.",
            "granularity",
            granularity_ratios=list(granularity),
        )
    return None


def check_variance_dispersion(
    sds: list[float],
    ns: list[int],
    sd_texts: Optional[list] = None,
    design: Optional[str] = None,
    homogeneous_variances: Optional[bool] = None,
    iterations: int = DEFAULT_ITERATIONS,
    seed: int = 0,
) -> dict:
    """Are these SDs too similar to each other to have arisen by sampling?

    Args:
        sds: reported standard deviations, one per group.
        ns: sample size per group, aligned with `sds`.
        sd_texts: the SDs exactly as PRINTED (e.g. ["2.11", "2.08"]). Required
            in practice: printed precision decides whether identical SDs are a
            signature or a rounding artifact, and it cannot be recovered from a
            float.
        design: study design. Cluster, multi-site, stepped-wedge, crossover,
            matched, stratified and minimised allocation are refused -- they
            constrain variances by construction.
        homogeneous_variances: whether the groups are expected to share a
            population variance. REQUIRED: unset returns `indeterminate` rather
            than a verdict, in either direction.
        iterations: parametric-bootstrap draws for the null.
        seed: RNG seed, for reproducibility.

    Returns:
        dict with `severity`, `dispersion_p`, the statistic and its secondary
        `SD_z`, the standardised variances, and `reference_required: True`.
        Severity is capped at `suspicious`: this ranks candidates for human
        review, it does not convict.
    """
    guard = refuse_if_nonfinite(sds=list(sds), ns=list(ns))
    if guard is not None:
        guard["reference_required"] = True
        return guard

    granularity, decimals = _granularity_ratios(sds, sd_texts)
    refusal = _applicability(sds, ns, design, homogeneous_variances, granularity)
    if refusal is not None:
        refusal.setdefault("n_groups", len(sds))
        return refusal

    z2, ms_w = _standardized_variances(sds, ns)
    if z2.size == 0:
        return _refusal(
            "The within mean square is not positive, so the variances cannot be "
            "standardised.",
            "ms_within",
        )

    observed = _dispersion(z2, "range")
    observed_sd = _dispersion(z2, "sd")

    rng = np.random.default_rng(seed)
    null = _null_distribution(ns, iterations, rng, "range")
    # One-sided, for EXCESSIVE CONSISTENCY: what fraction of honest draws are as
    # tightly clustered as this, or tighter?
    p = float(np.mean(null <= observed))

    if p < _P_SUSPICIOUS:
        severity = SUSPICIOUS
        explanation = (
            f"The {len(sds)} reported SDs are more similar to one another than "
            f"sampling error comfortably allows: only {p:.2%} of honest draws under "
            "the equal-variance null are this tightly clustered or tighter "
            f"(max_z - min_z = {observed:.4f}). Under-dispersed SDs are the "
            "signature Hartgerink et al. (2019) found most diagnostic of "
            "fabricated data (AUROC 1.00 on raw data). This is a RELATIVE "
            "screening signal, not proof: the same analysis flagged genuine "
            "datasets in absolute terms, and it warrants comparison against a "
            "reference distribution of known-genuine data before any conclusion."
        )
    elif p < _P_INDETERMINATE:
        severity = INDETERMINATE
        explanation = (
            f"The {len(sds)} reported SDs are somewhat more similar to one another "
            f"than sampling error predicts: {p:.2%} of honest draws under the "
            "equal-variance null are this tightly clustered or tighter "
            f"(max_z - min_z = {observed:.4f}). Enough to be worth a look, not "
            "enough to report as a finding -- for scale, the canonical published "
            "case of this method (Simonsohn 2013) sits at 1.21%. Compare against a "
            "reference distribution of known-genuine data from the same measure."
        )
    else:
        severity = CONSISTENT
        explanation = (
            f"The {len(sds)} reported SDs scatter about as much as sampling error "
            f"predicts: {p:.2%} of honest draws under the equal-variance null are "
            f"this tightly clustered or tighter (max_z - min_z = {observed:.4f}). "
            "No excessive-consistency signal. Note this is not evidence of "
            "authenticity -- fabricated data may be irregular in one respect and "
            "ordinary in another."
        )

    return {
        "severity": severity,
        "applicable": True,
        "dispersion_p": p,
        "dispersion_statistic": observed,
        "dispersion_measure": "max_z - min_z",
        "sd_z_secondary": observed_sd,
        "z_squared": [float(v) for v in z2],
        "ms_within": ms_w,
        "n_groups": len(sds),
        "sample_sizes": [int(n) for n in ns],
        "granularity_ratios": granularity,
        "printed_decimals": decimals,
        "homogeneous_variances": homogeneous_variances,
        "design": design,
        "iterations": iterations,
        "reference_required": True,
        "explanation": explanation,
        "caveat": (
            "Severity is capped at `suspicious`: over-similar SDs are improbable, "
            "never impossible. The source study's AUROC of 1.00 was a RELATIVE "
            "result -- every dataset it examined, genuine and fabricated alike, "
            "looked significant against the theoretical null, and only comparison "
            "between groups separated them. At a 2% base rate, perfect sensitivity "
            "with 5% false positives still yields a positive predictive value of "
            "29%, i.e. roughly one in three accusations wrong. Confirm the "
            "dispersion values are SDs and not SEs (`check_sd_or_se`) before "
            "reading anything into this."
        ),
        "methodology": (
            "Standardised variances z^2 = s^2 / MS_w with "
            "MS_w = sum (n_j-1) s_j^2 / sum (n_j-1); dispersion measured as "
            "max_z - min_z; null obtained by parametric bootstrap of "
            "s^2 ~ chi2_{n-1}/(n-1) over "
            f"{iterations:,} draws; one-sided p for excessive consistency. "
            "Hartgerink, Voelkel, Wicherts & van Assen (2019), Eqs. 3-5; "
            "statistic as used by Simonsohn (2013)."
        ),
    }
