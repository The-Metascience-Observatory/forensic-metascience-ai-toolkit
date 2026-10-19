"""Verify a paper's STATED power analysis by recomputing it.

WHY THIS EXISTS
---------------
Published power analyses are largely unverifiable, and where they ARE verifiable
the common failure is not arithmetic. Bakker et al. (2020) found that **~80%
cannot be checked at all** because the inputs are not fully reported; of those
that can be checked **97% reproduce**; and among fully reported analyses **~38%
powered the WRONG hypothesis** — the analysis is arithmetically correct but
answers a different question from the one the paper tests.

(An earlier version of this module cited "~70% of G*Power calculations do not
reproduce." That figure was wrong and is corrected here. The real result is more
interesting: the dominant problem is under-reporting, not miscalculation.)

Two consequences for this tool:

* Its most common honest output will be `indeterminate` — "this power analysis
  cannot be reproduced because the paper did not state X." That is a REPORTING
  finding, and given the 80% figure it is the modal result, not a failure.
* Recomputing N is necessary but not sufficient. A power analysis can reproduce
  perfectly and still be for the wrong hypothesis, which this module does NOT
  detect. See `_METHODOLOGY` and the limitations note below.

Either way the check accuses nobody: the paper states its own inputs, and either
the arithmetic follows or it does not.

This sits in the gap `metacheck` leaves. Its `power` module finds and classifies
power *statements*; recomputing the number is separate work, and it is
deterministic arithmetic rather than text classification, so it can be validated
against `pwr` in R to machine precision.

FALSE-POSITIVE DISCIPLINE
-------------------------
Four guards, because "your sample size is wrong" is a serious claim:

1. **Under-specification is not a finding.** If the paper does not state every
   input (test, effect size, alpha, power, allocation), we return
   `indeterminate`. We never fill in a default and then grade against it.
2. **Over-recruiting is correct practice.** Papers routinely inflate N for
   attrition. Only a reported N *below* the requirement is a discrepancy;
   N above it is expected and is reported as `consistent`.
3. **Software conventions differ.** G*Power, `pwr` and PASS disagree in the last
   participant or two (df handling, noncentrality approximations, rounding up
   per group vs overall). A tolerance band absorbs that.
4. **Rounding up is mandatory and per-group.** A requirement of 63.2 becomes 64,
   and a two-group design rounds each arm.
"""
from __future__ import annotations

import math

from scipy import optimize, stats

SUPPORTED_TESTS = (
    "two_sample_t",      # independent-samples t, effect size d
    "one_sample_t",      # one-sample / single-group t, d
    "paired_t",          # paired t, d (of the differences)
    "anova_oneway",      # one-way ANOVA, Cohen's f
    "correlation",       # Pearson r
    "chi_square",        # chi-squared GOF / independence, Cohen's w
    "two_proportions",   # comparison of two independent proportions, h
)

# Absolute + relative slack absorbing legitimate software disagreement.
_TOL_ABS = 2
_TOL_REL = 0.05


def _z(p: float) -> float:
    return stats.norm.ppf(p)


def _power_two_sample_t(n_per_group: float, d: float, alpha: float, tails: int) -> float:
    """Exact noncentral-t power for a two-sample design."""
    if n_per_group < 2:
        return 0.0
    df = 2 * n_per_group - 2
    ncp = d * math.sqrt(n_per_group / 2)
    crit = stats.t.ppf(1 - alpha / tails, df)
    power = 1 - stats.nct.cdf(crit, df, ncp)
    if tails == 2:
        power += stats.nct.cdf(-crit, df, ncp)
    return power


def _power_one_sample_t(n: float, d: float, alpha: float, tails: int) -> float:
    if n < 2:
        return 0.0
    df = n - 1
    ncp = d * math.sqrt(n)
    crit = stats.t.ppf(1 - alpha / tails, df)
    power = 1 - stats.nct.cdf(crit, df, ncp)
    if tails == 2:
        power += stats.nct.cdf(-crit, df, ncp)
    return power


def _power_anova(n_per_group: float, f: float, alpha: float, groups: int) -> float:
    if n_per_group < 2 or groups < 2:
        return 0.0
    total = n_per_group * groups
    df1, df2 = groups - 1, total - groups
    ncp = f**2 * total
    crit = stats.f.ppf(1 - alpha, df1, df2)
    return 1 - stats.ncf.cdf(crit, df1, df2, ncp)


def _power_correlation(n: float, r: float, alpha: float, tails: int) -> float:
    if n < 4 or abs(r) >= 1:
        return 0.0
    z_r = 0.5 * math.log((1 + r) / (1 - r))          # Fisher z
    se = 1 / math.sqrt(n - 3)
    crit = _z(1 - alpha / tails)
    power = 1 - stats.norm.cdf(crit - abs(z_r) / se)
    if tails == 2:
        power += stats.norm.cdf(-crit - abs(z_r) / se)
    return power


def _power_chi_square(n: float, w: float, alpha: float, df: int) -> float:
    if n < 1 or df < 1:
        return 0.0
    crit = stats.chi2.ppf(1 - alpha, df)
    return 1 - stats.ncx2.cdf(crit, df, n * w**2)


def _power_two_proportions(n_per_group: float, h: float, alpha: float, tails: int) -> float:
    if n_per_group < 2:
        return 0.0
    crit = _z(1 - alpha / tails)
    lam = abs(h) * math.sqrt(n_per_group / 2)
    power = 1 - stats.norm.cdf(crit - lam)
    if tails == 2:
        power += stats.norm.cdf(-crit - lam)
    return power


def required_n(
    test_type: str,
    effect_size: float,
    alpha: float = 0.05,
    power: float = 0.80,
    tails: int = 2,
    groups: int = 2,
    df: int | None = None,
    actual_n: int | None = None,
    source_quote: str | None = None,
    source_locator: str | None = None,
) -> dict:
    """Smallest n meeting the target power -- and, given `actual_n`, a verdict.

    GREG, 2026-08-16: "make required_n a proper check so the model can call it."

    IT WAS CLI-ONLY, AND THAT COST A REAL RUN. On PNAS 0801268105 the sweep
    reached for this tool THREE TIMES and was refused, on a paper whose reported
    degrees of freedom imply 68 participants against a stated 34 -- the exact
    question this answers. It was withheld because a model-callable tool must
    return a severity from the ladder and say where its inputs came from, and a
    bare calculator does neither. Both are now true, so the reason is gone.

    WITH `actual_n` IT IS A CHECK, comparing the design a paper HAD against the
    design its own reported effect would need. Without it, it stays the
    calculator it always was.

    THE VERDICT NEVER ACCUSES, and this is deliberate rather than timid. A small
    study is not an erroneous one, and "underpowered" is context a reader weighs,
    not a defect a paper contains. So an under-powered design comes back
    `consistent` with the comparison attached -- the number is the finding, and
    the reader draws the conclusion. Escalating here would manufacture an
    accusation out of every honest pilot study.

    It is also NOT observed power, which is a monotone transformation of the
    p-value (Hoenig & Heisey 2001) and tells a reader nothing the p did not.
    What comes back is a property of the DESIGN.
    """
    if test_type not in SUPPORTED_TESTS:
        return {"error": f"unsupported test_type {test_type!r}", "severity": "indeterminate"}
    if (isinstance(effect_size, bool) or not isinstance(effect_size, (int, float))
            or not math.isfinite(effect_size)):
        # A NaN/inf effect size is an extraction artefact of OURS; it
        # previously crashed brentq mid-solve rather than declining.
        return {"error": f"effect_size must be a finite number (got {effect_size!r})",
                "severity": "indeterminate"}
    if not (0 < alpha < 1) or not (0 < power < 1):
        return {"error": "alpha and power must be in (0, 1)", "severity": "indeterminate"}
    if effect_size == 0:
        return {"error": "effect size of 0 requires infinite n", "severity": "indeterminate"}
    if tails not in (1, 2):
        # tails=0 divided by zero; tails=-1 fed NaN to the solver. Both crashed.
        return {"error": f"tails must be 1 or 2 (got {tails!r})", "severity": "indeterminate"}

    es = abs(effect_size)
    if test_type == "two_sample_t":
        fn, per_group = (lambda n: _power_two_sample_t(n, es, alpha, tails)), True
    elif test_type == "one_sample_t":
        fn, per_group = (lambda n: _power_one_sample_t(n, es, alpha, tails)), False
    elif test_type == "paired_t":
        fn, per_group = (lambda n: _power_one_sample_t(n, es, alpha, tails)), False
    elif test_type == "anova_oneway":
        fn, per_group = (lambda n: _power_anova(n, es, alpha, groups)), True
    elif test_type == "correlation":
        fn, per_group = (lambda n: _power_correlation(n, es, alpha, tails)), False
    elif test_type == "chi_square":
        d = df if df is not None else max(1, groups - 1)
        fn, per_group = (lambda n: _power_chi_square(n, es, alpha, d)), False
    else:  # two_proportions
        fn, per_group = (lambda n: _power_two_proportions(n, es, alpha, tails)), True

    lo, hi = 2, 4
    while fn(hi) < power and hi < 10_000_000:
        lo, hi = hi, hi * 2
    if fn(hi) < power:
        return {"error": "required n exceeds 10,000,000", "severity": "indeterminate"}
    n = int(math.ceil(optimize.brentq(lambda x: fn(x) - power, lo, hi, xtol=1e-4)))
    while fn(n) < power:      # guard the ceiling against float error
        n += 1

    total = n * groups if per_group and test_type in ("anova_oneway",) else (
        n * 2 if per_group else n
    )
    out = {
        "n_per_group": n if per_group else None,
        "n_total": total,
        "achieved_power": round(fn(n), 4),
        "inputs": {"test_type": test_type, "effect_size": effect_size, "alpha": alpha,
                   "power": power, "tails": tails, "groups": groups,
                   "actual_n": actual_n},
        "severity": "consistent",
    }
    # THE COMPARISON THAT MAKES IT A CHECK. Everything above is the calculator;
    # this is what a reader acts on.
    if isinstance(actual_n, (int, float)) and not isinstance(actual_n, bool) and actual_n > 0:
        adequate = actual_n >= total
        out["design_sensitivity"] = {
            "actual_n_total": int(actual_n),
            "required_n_total": total,
            "ratio": round(actual_n / total, 3) if total else None,
            "adequately_powered_for_this_effect": adequate,
        }
        out["explanation"] = (
            f"To detect an effect of {abs(effect_size)} at {int(power*100)}% power and "
            f"alpha {alpha}, this design needs about {total} participants in total; the "
            f"study reports {int(actual_n)}. "
            + ("That is sufficient." if adequate else
               f"That is {round(total/actual_n, 1)}x fewer than required, so the design "
               "could not reliably detect an effect of the size reported. This is "
               "CONTEXT, not an error: small studies are not wrong, and a significant "
               "result from an under-powered design is where selection inflates "
               "estimates rather than where misconduct lives.")
        )
        # `consistent` EITHER WAY. Being small is not a defect, and escalating
        # here would manufacture an accusation out of every honest pilot study.
        out["severity"] = "consistent"
    return out


_TAILED_TESTS = ("two_sample_t", "one_sample_t", "paired_t",
                 "correlation", "two_proportions")


def verify_power_analysis(
    test_type: str,
    effect_size: float | None = None,
    alpha: float | None = None,
    target_power: float | None = None,
    n_reported: int | None = None,
    n_reported_is_per_group: bool = False,
    tails: int | None = None,
    groups: int = 2,
    df: int | None = None,
    allows_attrition_inflation: bool = True,
    allocation_ratio: float = 1.0,
) -> dict:
    """Recompute a stated power analysis and compare it to the reported N.

    Returns `indeterminate` unless every input needed to reproduce the
    calculation was actually stated by the paper.

    CONVENTIONS ARE NEVER SILENTLY GRADED AGAINST. `tails=None` means the
    paper did not state its tail convention: the two-tailed reading is then
    primary, but a shortfall that reconciles under the one-tailed reading is
    reported as `indeterminate` with the ambiguity named — a convention we
    assumed is not the paper's arithmetic. (An honestly one-tailed paper
    reporting N=102 at d=0.5 was previously graded `suspicious` against the
    silently-assumed two-tailed 128.) Pass `tails` explicitly when the paper
    states it; that restores full sensitivity. Likewise a reported N that IS
    the per-group requirement is treated as a probable units confusion, not
    underpowering, and `allocation_ratio != 1` is refused rather than
    approximated by 1:1 arithmetic.
    """
    missing = [
        name for name, val in (
            ("effect_size", effect_size), ("alpha", alpha),
            ("target_power", target_power), ("n_reported", n_reported),
        ) if val is None
    ]
    if missing:
        return {            "severity": "indeterminate",
            "reproducible": False,
            "missing_inputs": missing,
            "explanation": (
                "The paper did not state " + ", ".join(missing) + ", so its power analysis "
                "cannot be reproduced. This is a REPORTING gap, not evidence that the "
                "calculation is wrong."
            ),
        }

    if (isinstance(n_reported, bool) or not isinstance(n_reported, (int, float))
            or not math.isfinite(n_reported) or n_reported < 1):
        # N=0, a negative N or a NaN is never a recruited sample: it is OUR
        # extraction failing. It previously graded as a shortfall ("suspicious,
        # underpowered_vs_stated_parameters" at N=0).
        return {            "severity": "indeterminate", "reproducible": False,
            "verdict": "unusable_n_reported",
            "explanation": (
                f"n_reported={n_reported!r} is not a usable sample size. This is "
                "an input or extraction failure on OUR side, not a finding "
                "about the paper."
            ),
        }

    if allocation_ratio != 1.0:
        return {            "severity": "indeterminate", "reproducible": False,
            "verdict": "unsupported_design",
            "explanation": (
                f"allocation_ratio={allocation_ratio!r} is not supported: this "
                "check recomputes a 1:1 design, and an unequal allocation needs "
                "MORE total N than the 1:1 arithmetic, so grading a k:1 design "
                "against it can accuse a correct calculation. Refusing instead."
            ),
        }

    tails_stated = tails is not None
    primary_tails = tails if tails_stated else 2

    req = required_n(test_type, effect_size, alpha, target_power, primary_tails,
                     groups, df)
    if req.get("error"):
        return {"severity": "indeterminate", "reproducible": False, **req}

    needed = req["n_per_group"] if (n_reported_is_per_group and req["n_per_group"]) else req["n_total"]
    tolerance = max(_TOL_ABS, math.ceil(_TOL_REL * needed))
    shortfall = needed - n_reported

    if shortfall <= tolerance:
        if n_reported > needed + tolerance:
            severity, verdict = "consistent", "over_recruited"
            if allows_attrition_inflation:
                expl = (
                    f"Reported N={n_reported} exceeds the {needed} required. Recruiting above the "
                    "minimum is normal practice (attrition allowance) and is not a discrepancy."
                )
            else:
                expl = (
                    f"Reported N={n_reported} exceeds the {needed} required. "
                    "`allows_attrition_inflation` is off, but an N above the "
                    "requirement is still never graded as a discrepancy; it is "
                    "only labelled."
                )
        else:
            severity, verdict = "consistent", "reproduces"
            expl = f"Reported N={n_reported} matches the recomputed requirement of {needed}."
    else:
        # A shortfall exists against the PRIMARY reading. Before grading it,
        # try the readings we would otherwise be silently assuming: an
        # accusation may not rest on an assumed convention.
        if not tails_stated and test_type in _TAILED_TESTS:
            alt = required_n(test_type, effect_size, alpha, target_power, 1,
                             groups, df)
            if not alt.get("error"):
                needed_alt = (alt["n_per_group"]
                              if (n_reported_is_per_group and alt["n_per_group"])
                              else alt["n_total"])
                tol_alt = max(_TOL_ABS, math.ceil(_TOL_REL * needed_alt))
                if needed_alt - n_reported <= tol_alt:
                    return {                        "severity": "indeterminate", "reproducible": True,
                        "verdict": "reconciles_under_one_tailed_reading",
                        "required_n": needed,
                        "required_n_one_tailed": needed_alt,
                        "reported_n": n_reported, "tolerance": tolerance,
                        "target_power": target_power,
                        "explanation": (
                            f"N={n_reported} falls short of the two-tailed "
                            f"requirement ({needed}) but satisfies the "
                            f"one-tailed one ({needed_alt}). The paper's tail "
                            "convention was not stated, and a shortfall "
                            "explained by an assumed convention is not a "
                            "discrepancy. Confirm the tail convention from the "
                            "paper and re-run with `tails` set."
                        ),
                        "recomputation": req, "methodology": _METHODOLOGY,
                    }
        if not n_reported_is_per_group and req.get("n_per_group"):
            n_pg = req["n_per_group"]
            tol_pg = max(_TOL_ABS, math.ceil(_TOL_REL * n_pg))
            if abs(n_pg - n_reported) <= tol_pg:
                return {                    "severity": "indeterminate", "reproducible": True,
                    "verdict": "reconciles_if_n_reported_is_per_group",
                    "required_n": needed, "required_n_per_group": n_pg,
                    "reported_n": n_reported, "tolerance": tolerance,
                    "target_power": target_power,
                    "explanation": (
                        f"N={n_reported} was read as a TOTAL and falls short of "
                        f"the {needed} required — but it matches the PER-GROUP "
                        f"requirement of {n_pg}, the signature of a per-group "
                        "figure passed as a total. Confirm which the paper "
                        "reports and re-run with `n_reported_is_per_group` set."
                    ),
                    "recomputation": req, "methodology": _METHODOLOGY,
                }

        # Under-powered relative to the paper's OWN stated parameters, under
        # every reading tried above.
        achieved = _achieved_power(test_type, effect_size, alpha, n_reported,
                                   n_reported_is_per_group, primary_tails, groups, df)
        severity = "suspicious" if shortfall > 2 * tolerance else "indeterminate"
        verdict = "underpowered_vs_stated_parameters"
        assumed = []
        if not tails_stated and test_type in _TAILED_TESTS:
            assumed.append("two-tailed alpha (tails unstated; the one-tailed "
                           "requirement does not reconcile either)")
        if not n_reported_is_per_group and req.get("n_per_group"):
            assumed.append(f"n_reported read as a TOTAL (the per-group "
                           f"requirement is {req['n_per_group']}, which it does "
                           "not match either)")
        expl = (
            f"The paper's own stated parameters (d={effect_size}, alpha={alpha}, "
            f"power={target_power}) require N={needed}, but N={n_reported} is reported — "
            f"a shortfall of {shortfall}. At the reported N the actual power is "
            f"{achieved:.2f}, not {target_power}. This is an arithmetic discrepancy in the "
            "paper's own calculation, not a judgement about the design."
        )
        if assumed:
            expl += " Readings assumed: " + "; ".join(assumed) + "."
        return {            "severity": severity, "reproducible": True, "verdict": verdict,
            "required_n": needed, "reported_n": n_reported, "shortfall": shortfall,
            "achieved_power_at_reported_n": round(achieved, 4),
            "target_power": target_power, "tolerance": tolerance,
            "assumed_conventions": assumed,
            "explanation": expl, "recomputation": req,
            "methodology": _METHODOLOGY,
        }

    return {        "severity": severity, "reproducible": True, "verdict": verdict,
        "required_n": needed, "reported_n": n_reported, "shortfall": shortfall,
        "target_power": target_power, "tolerance": tolerance,
        "explanation": expl, "recomputation": req,
        "methodology": _METHODOLOGY,
    }


def _achieved_power(test_type, es, alpha, n, per_group, tails, groups, df) -> float:
    n_eff = n if per_group else (n / groups if test_type in ("two_sample_t", "anova_oneway",
                                                             "two_proportions") else n)
    es = abs(es)
    if test_type == "two_sample_t":
        return _power_two_sample_t(n_eff, es, alpha, tails)
    if test_type in ("one_sample_t", "paired_t"):
        return _power_one_sample_t(n_eff, es, alpha, tails)
    if test_type == "anova_oneway":
        return _power_anova(n_eff, es, alpha, groups)
    if test_type == "correlation":
        return _power_correlation(n_eff, es, alpha, tails)
    if test_type == "chi_square":
        return _power_chi_square(n_eff, es, alpha, df if df is not None else max(1, groups - 1))
    return _power_two_proportions(n_eff, es, alpha, tails)


_METHODOLOGY = (
    "Power recomputed from the paper's own stated inputs using exact noncentral "
    "distributions (noncentral t / F / chi-squared; Fisher z for correlations). The "
    "requirement is rounded UP, per group where the design is grouped, and compared with a "
    "tolerance of max(2, 5%) to absorb documented disagreement between G*Power, pwr and PASS. "
    "Reporting an N ABOVE the requirement is treated as correct practice (attrition "
    "allowance), never as a discrepancy."
)
