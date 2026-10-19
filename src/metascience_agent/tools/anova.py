"""
ANOVA Recalculation Tools

Recalculate one-way ANOVA from reported group statistics.
"""

from typing import Optional

from scipy import stats

from . import rounding as _rounding
from ..survey_design import survey_refusal
from .severity import CONSISTENT, INDETERMINATE, SUSPICIOUS
from .ttest import (_half_for, p_under_claimed, resolve_p_relation,
                    under_claim_finding, under_claim_note,
                    bound_is_stated, check_p_adjustment, explain_under_claim,
                    ONE_TAILED_UNSTATED_NOTE)


def _apply_p_relation(result: dict, p_hi: float, reported_p: float,
                      decimals_p: Optional[int], p_relation: Optional[str],
                      what: str, p_lo: Optional[float] = None,
                      p_adjustment: Optional[str] = None,
                      test_confirmed: Optional[bool] = None) -> Optional[str]:
    """Fold the printed p relation into `result["p_matches"]`.

    Returns an error string for an unusable `p_relation`, else None. An EXACT
    printed p above the whole achievable interval is an under-claim
    (`ttest.resolve_p_relation`), recorded with its own failure mode and
    `p_explanation`; a "p > x" cannot over-claim, so its directional test is
    replaced by the under-claim test alone.
    """
    chk = check_p_adjustment(p_adjustment)
    if "error" in chk:
        return chk["error"]
    p_adjustment = chk["adjustment"]
    resolved = resolve_p_relation(p_relation, reported_p)
    if "error" in resolved:
        return resolved["error"]
    rel = resolved["relation"]
    result["p_relation"] = rel
    result["p_relation_basis"] = resolved["basis"]
    if p_adjustment is not None:
        result["p_adjustment"] = p_adjustment
    # A DECLARED BOUND IS HELD TO ITS EXACT ENDPOINT (`ttest.bound_is_stated`):
    # the caller's match test gave it the printed precision's slack.
    if bound_is_stated(resolved) and p_lo is not None:
        result["p_matches"] = bool(reported_p >= p_lo - _rounding.EPSILON)
    if rel == ">":
        result["p_matches"] = True
    if result["p_matches"] and p_under_claimed(p_hi, reported_p, decimals_p, rel):
        uc = explain_under_claim(under_claim_finding(p_hi, reported_p, decimals_p,
                                                     resolved, what),
                                 p_adjustment=p_adjustment, test_confirmed=test_confirmed)
        uc.pop("severity")
        uc.pop("consistent")
        result["p_explanation"] = uc.pop("explanation")
        result.update(uc)
        # An under-claim the paper explains (a declared correction, or a test
        # reconstructed from summary statistics) is not a mismatch: it keeps
        # `p_matches` and the caller reports it as indeterminate.
        if not uc.get("under_claim_explained"):
            result["p_matches"] = False
    elif (result["p_matches"] and rel is None
          and p_under_claimed(p_hi, reported_p, decimals_p, "=")):
        result["under_claim_if_exact"] = True
        result["p_explanation"] = under_claim_note(p_hi, reported_p)
    return None


def _achievable_f_interval(
    means: list[float],
    sds: list[float],
    ns: list[int],
    decimals_mean: Optional[int],
    decimals_sd: Optional[int],
) -> tuple[float, Optional[float]]:
    """Outer bound on the F reachable from the printed group means/SDs.

    Rounding of the inputs propagates MULTIPLICATIVELY into F: at F ~ 900 the
    reachable spread from 2 dp inputs is tens of units wide, so a fixed 0.1
    window convicts essentially every honestly reported large F. Each printed
    mean can shift its group's deviation from the grand mean by at most its
    own half-width (scaled by 1 - n_i/N, since moving a mean drags the grand
    mean along) plus the grand mean's worst-case shift from the OTHER groups;
    the SDs bound MS_within monotonically. Combining per-group worst cases
    gives a slightly-too-wide interval by construction, which is the safe
    direction: too wide only misses, too tight accuses. (RIVETS' Monte Carlo
    remains the tool of record for tight reachability.)

    Returns (f_lo, f_hi); f_hi is None when MS_within can reach zero, in which
    case no large reported F can be refuted from these inputs.
    """
    N = sum(ns)
    k = len(means)
    h_ms = [_half_for(m, decimals_mean) for m in means]
    h_ss = [_half_for(s, decimals_sd) for s in sds]
    grand = sum(m * n for m, n in zip(means, ns)) / N
    grand_shift_total = sum(n * h for n, h in zip(ns, h_ms))
    deltas = [
        h * (1 - n / N) + (grand_shift_total - n * h) / N
        for h, n in zip(h_ms, ns)
    ]
    devs = [abs(m - grand) for m in means]
    ssb_hi = sum(n * (d + dl) ** 2 for n, d, dl in zip(ns, devs, deltas))
    ssb_lo = sum(n * max(0.0, d - dl) ** 2 for n, d, dl in zip(ns, devs, deltas))
    ssw_lo = sum((n - 1) * max(0.0, s - h) ** 2 for n, s, h in zip(ns, sds, h_ss))
    ssw_hi = sum((n - 1) * (s + h) ** 2 for n, s, h in zip(ns, sds, h_ss))
    df_between = k - 1
    df_within = N - k
    f_lo = (ssb_lo / df_between) / (ssw_hi / df_within)
    f_hi = (
        (ssb_hi / df_between) / (ssw_lo / df_within) if ssw_lo > 0 else None
    )
    return f_lo, f_hi


def recalc_one_way_anova(
    means: list[float],
    sds: list[float],
    ns: list[int],
    reported_f: Optional[float] = None,
    reported_p: Optional[float] = None,
    decimals_p: Optional[int] = None,
    decimals_mean: Optional[int] = None,
    decimals_sd: Optional[int] = None,
    sampling: str = "simple_random",
    p_relation: Optional[str] = None,
    p_adjustment: Optional[str] = None,
    test_confirmed: bool = False,
) -> dict:
    """
    Recalculate a one-way ANOVA from group statistics.

    Args:
        means: List of group means
        sds: List of group standard deviations
        ns: List of group sample sizes
        reported_f: F-statistic reported in paper
        reported_p: P-value reported in paper
        decimals_p: Printed decimals of reported_p
        decimals_mean, decimals_sd: Printed decimals of the means/SDs; when
            absent they are inferred from the parsed values, erring wide.
        p_relation: '=' (exact), '<' (a bound) or '>' -- what the paper
            printed with the p; see `ttest.resolve_p_relation`.

    Returns:
        Dictionary with calculated F, p, and comparison
    """
    refusal = survey_refusal("recalc_anova", sampling)
    if refusal is not None:
        return refusal
    k = len(means)  # Number of groups
    if k < 2 or len(sds) != k or len(ns) != k:
        return {
            "error": (
                f"Need ≥ 2 groups with equal-length means/sds/ns "
                f"(got {k} means, {len(sds)} sds, {len(ns)} ns)"
            ),
            "severity": INDETERMINATE,
        }
    if any(n < 2 for n in ns):
        return {
            "error": f"All group ns must be ≥ 2 (got {ns})",
            "severity": INDETERMINATE,
        }
    if any(sd < 0 for sd in sds):
        return {
            "error": f"SDs cannot be negative (got {sds})",
            "severity": INDETERMINATE,
        }

    N = sum(ns)  # Total sample size

    # Calculate overall mean
    overall_mean = sum(m * n for m, n in zip(means, ns)) / N

    # Calculate between-group sum of squares
    ss_between = sum(n * (m - overall_mean) ** 2 for m, n in zip(means, ns))

    # Calculate within-group sum of squares
    ss_within = sum((n - 1) * sd ** 2 for n, sd in zip(ns, sds))

    # Degrees of freedom
    df_between = k - 1
    df_within = N - k

    # Mean squares
    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    if ms_within == 0:
        return {
            "error": "All group SDs are zero — F is undefined (MS_within = 0)",
            "severity": INDETERMINATE,
            "ss_between": ss_between,
        }

    # F-statistic
    f_value = ms_between / ms_within

    # P-value
    p_value = stats.f.sf(f_value, df_between, df_within)

    result = {
        "calculated_f": f_value,
        "calculated_p": p_value,
        "df_between": df_between,
        "df_within": df_within,
        "ms_between": ms_between,
        "ms_within": ms_within,
        "overall_mean": overall_mean,
        "inputs": {
            "means": means,
            "sds": sds,
            "ns": ns,
        },
    }

    matches: list[bool] = []
    # The reported F inherits the rounding of every mean and SD it was built
    # from, and that error is MULTIPLICATIVE in F: at F ~ 900 the reachable
    # spread from 2 dp inputs is tens of units wide, so the old fixed
    # |F - reported| < 0.1 window convicted essentially every honestly
    # reported large F. The interval below propagates the printed precision
    # through the F formula (outer bound; see _achievable_f_interval); the
    # historical 0.1 stays as an additive floor so nothing the old window
    # accepted is newly accused. RIVETS remains the tool of record for tight
    # reachability (Monte Carlo) and hand-calculation signatures.
    # The reachable F interval also bounds the reachable p, and BOTH branches must
    # use it. The F branch already did; the p branch compared the reported p only
    # against the POINT p from the rounded means/SDs, so a paper whose F is
    # achievable and whose p is the p OF that achievable F was flagged `suspicious`
    # -- the same asymmetry fixed in check_regression. Compute the interval once
    # whenever either F or p is reported.
    f_lo = f_hi = None
    if reported_f is not None or reported_p is not None:
        f_lo, f_hi = _achievable_f_interval(means, sds, ns, decimals_mean, decimals_sd)

    if reported_f is not None:
        result["reported_f"] = reported_f
        result["achievable_f_interval"] = [f_lo, f_hi]
        result["f_matches"] = bool(
            reported_f >= f_lo - 0.1 - _rounding.EPSILON
            and (f_hi is None or reported_f <= f_hi + 0.1 + _rounding.EPSILON)
        )
        matches.append(result["f_matches"])

    if reported_p is not None:
        # p is monotone DECREASING in F, so the achievable p spans
        # [sf(f_hi), sf(f_lo)] (f_hi=None => p can reach 0). The reported p matches
        # if it lies in that interval or within its own printed precision of an
        # endpoint -- interval-vs-value, not the old point-vs-value.
        p_lo_r = float(stats.f.sf(f_hi, df_between, df_within)) if f_hi is not None else 0.0
        p_hi_r = float(stats.f.sf(f_lo, df_between, df_within))
        h_p = _half_for(reported_p, decimals_p)
        result["reported_p"] = reported_p
        result["achievable_p_interval"] = [p_lo_r, p_hi_r]
        # OVER-CLAIM: a reported p BELOW the achievable interval -- more
        # significance than the printed means/SDs can support -- is suspicious.
        # UNDER-CLAIM: a reported p ABOVE it is a true statement for a bound
        # ("p < .05") and an inconsistency for an exact value; until 1.86.0 it
        # was tolerated in both cases (`_apply_p_relation`).
        result["p_matches"] = bool(reported_p + h_p >= p_lo_r - _rounding.EPSILON)
        err = _apply_p_relation(result, p_hi_r, reported_p, decimals_p, p_relation,
                                "the printed group means and SDs", p_lo=p_lo_r,
                                p_adjustment=p_adjustment,
                                test_confirmed=bool(test_confirmed))
        if err:
            return {**result, "severity": INDETERMINATE, "error": err}
        matches.append(result["p_matches"])

    if not matches:
        result["severity"] = INDETERMINATE
    elif all(matches):
        result["severity"] = (INDETERMINATE if result.get("under_claim_explained")
                              else CONSISTENT)
    else:
        result["severity"] = SUSPICIOUS
    if result.get("p_explanation"):
        result["explanation"] = result["p_explanation"]

    result["methodology"] = (
        f"One-way ANOVA: F = MS_between / MS_within = {ms_between:.4f} / {ms_within:.4f} = {f_value:.4f}. "
        f"df = ({df_between}, {df_within}), p = {p_value:.6f}"
    )

    return result


#: df2 values swept when the paper does not print one. Dense where the F
#: distribution changes fastest, then representative large values; the
#: df2->infinity chi-square limit is evaluated separately and is the global
#: floor of the achievable p for any F worth checking.
_DF2_GRID = tuple(range(1, 31)) + (40, 60, 120, 1000)


def _f_to_p_df2_unstated(
    f_value: float,
    df1: int,
    reported_p: Optional[float],
    decimals_p: Optional[int],
    decimals_f: Optional[int],
    p_relation: Optional[str] = None,
    p_adjustment: Optional[str] = None,
    one_tailed_stated: bool = False,
) -> dict:
    """The df2-unstated mode: attainability over EVERY df2, never one we chose.

    MEASURED FP, 2026-08-22 (the reason this mode exists): a review flagged
    F(3, df2) = 6.951 against a reported p = 0.0001 using an ASSUMED df2 = 20
    (attainable p there >= ~2.5e-3) -- but at df2 -> infinity the same F gives
    p = 1.14e-4, which PRINTS as 0.0001. The paper never stated df2; the
    contradiction was ours. Rule 4: a df the paper does not print is an
    assumed bound. Here the tool sweeps df2 itself and accuses only when the
    reported p is unattainable at EVERY df2 -- which no assumption can cause.
    """
    h_f = _half_for(f_value, decimals_f)
    f_hi = f_value + h_f
    f_lo = max(0.0, f_value - h_f)
    p_lo = min(float(stats.f.sf(f_hi, df1, d)) for d in _DF2_GRID)
    p_hi = max(float(stats.f.sf(f_lo, df1, d)) for d in _DF2_GRID)
    # df2 -> infinity: F(df1, df2) -> chi2(df1)/df1.
    p_lo = min(p_lo, float(stats.chi2.sf(f_hi * df1, df1)))
    p_hi = max(p_hi, float(stats.chi2.sf(f_lo * df1, df1)))

    result: dict = {
        "f_value": f_value,
        "df1": df1,
        "df2": None,
        "df2_unstated": True,
        "calculated_p_large_df2": float(stats.chi2.sf(f_value * df1, df1)),
        "achievable_p_range_over_df2": [p_lo, p_hi],
        "methodology": (
            f"F-to-p with df2 UNSTATED: F({df1}, ?) = {f_value}; over all "
            f"df2 (1..inf) the achievable p spans [{p_lo:.3g}, {p_hi:.3g}]"),
    }
    if reported_p is None:
        result["severity"] = INDETERMINATE
        result["explanation"] = (
            "No reported p to compare. The paper states no df2, so no single "
            "p can be computed -- only the achievable range above.")
        return result

    h_p = _half_for(reported_p, decimals_p)
    result["reported_p"] = reported_p
    result["p_matches"] = bool(reported_p + h_p >= p_lo - _rounding.EPSILON)
    err = _apply_p_relation(result, p_hi, reported_p, decimals_p, p_relation,
                            f"F({df1}, df2) = {f_value} at any df2", p_lo=p_lo,
                            p_adjustment=p_adjustment)
    if err:
        return {**result, "severity": INDETERMINATE, "error": err}
    if result.get("under_claim_explained"):
        result["severity"] = INDETERMINATE
        result["explanation"] = result["p_explanation"]
        return result
    if result.get("p_direction") == "under_claim":
        result["severity"] = SUSPICIOUS
        result["explanation"] = result["p_explanation"]
        return result
    attainable = result["p_matches"]
    if attainable:
        result["severity"] = CONSISTENT
        result["explanation"] = (
            "The reported p is attainable at SOME df2, so with df2 unstated "
            "there is no contradiction. This is attainability, not "
            "verification: the paper should print its df2, but omitting it "
            "is a reporting note, never a finding."
            + (" " + result["p_explanation"] if result.get("p_explanation") else ""))
        return result
    one_tailed = (df1 == 1 and reported_p + h_p >= p_lo / 2.0 - _rounding.EPSILON
                  and not p_under_claimed(p_hi / 2.0, reported_p, decimals_p,
                                          result.get("p_relation")))
    result["one_tailed_stated"] = bool(one_tailed_stated)
    if one_tailed:
        result["one_tailed_reconciles"] = True
    # Only when the paper SAYS it tested one-tailed (1.93.0, statcheck's rule).
    if one_tailed and one_tailed_stated:
        # Same wrinkle as the exact-df2 path: F(1, df2) = t(df2)^2, so a
        # one-tailed reading halves the p, and the paper says it tested that
        # way. Indeterminate, not consistent: df2 is still unprinted.
        result["severity"] = INDETERMINATE
        result["explanation"] = (
            "The reported p is below the two-tailed floor for every df2 but "
            "inside the ONE-tailed range (df1 = 1, so halving is exactly what "
            "a directional hypothesis produces), and the paper states that it "
            "tested one-tailed. df2 is still unprinted, so this cannot be "
            "determined either way.")
        return result
    result["severity"] = SUSPICIOUS
    result["explanation"] = (
        f"The reported p is smaller than this F can produce at ANY df2 -- "
        f"even the df2 -> infinity floor is {p_lo:.3g} against a reported "
        f"{reported_p} -- so no choice of denominator degrees of freedom "
        "explains it. Capped at suspicious: the F itself is a printed, "
        "rounded value and a transcription slip in F or df1 is the ordinary "
        "explanation; quote the sentence that prints them."
        + (" " + ONE_TAILED_UNSTATED_NOTE if one_tailed else ""))
    if one_tailed:
        result["failure_mode"] = "reconciles_only_one_tailed_unstated"
    return result


def recalc_f_to_p(
    f_value: float,
    df1: int,
    df2: Optional[int] = None,
    reported_p: Optional[float] = None,
    decimals_p: Optional[int] = None,
    decimals_f: Optional[int] = None,
    p_relation: Optional[str] = None,
    p_adjustment: Optional[str] = None,
    one_tailed_stated: bool = False,
) -> dict:
    """
    Verify F statistic to p-value conversion.

    Args:
        f_value: Reported F statistic
        df1: Numerator degrees of freedom
        df2: Denominator degrees of freedom, ONLY if the paper prints it.
            None (the default when the paper is silent) switches to the
            df2-unstated mode: the reported p is checked for attainability
            over EVERY df2, and a finding requires failing all of them.
            Passing a df2 you inferred from the design is an assumed bound
            (rulebook rule 4) and manufactured a measured false positive.
        reported_p: P-value reported in paper
        decimals_p: Printed decimals of reported_p.
        decimals_f: Printed decimals of the reported F. The F is rounded, and p
            is monotone in F, so a printed 'F(1,10) = 2.0' asserts F in
            [1.95, 2.05) and a whole p-range, not a single p. Comparing the
            reported p to the point p of the printed F convicted large fractions
            of honestly rounded reports. Inferred from the F literal when absent.
        p_relation: '=' (exact), '<' (a bound) or '>' -- what the paper
            printed with the p; see `ttest.resolve_p_relation`.
        one_tailed_stated: The paper says, anywhere, that it tested one-tailed
            (statcheck's rule). Only then does the df1 = 1 one-tailed reading
            explain a too-small p; otherwise it is named beside the finding.

    Returns:
        Dictionary with calculated p-value and comparison
    """
    if f_value < 0 or df1 < 1 or (df2 is not None and df2 < 1):
        return {
            "error": f"Invalid inputs (F={f_value}, df1={df1}, df2={df2})",
            "severity": INDETERMINATE,
        }
    if df2 is None:
        return _f_to_p_df2_unstated(f_value, df1, reported_p,
                                    decimals_p, decimals_f, p_relation,
                                    p_adjustment=p_adjustment,
                                    one_tailed_stated=one_tailed_stated)

    calculated_p = stats.f.sf(f_value, df1, df2)

    result = {
        "f_value": f_value,
        "df1": df1,
        "df2": df2,
        "calculated_p": calculated_p,
    }

    # A ONE-TAILED READING EXISTS, AND ONLY WHEN df1 == 1.
    #
    # GREG, 2026-08-16: "make sure F tests and other tests can accommodate the
    # calculations for a 1-tailed version."
    #
    # The F distribution is inherently upper-tailed, so "one-tailed F" is
    # meaningless in general -- and a sweep on PNAS 0801268105 said exactly that
    # while flagging three p-values as "approximately half" what their F
    # implies. For df1 = 1 the statement is WRONG, and that paper is the
    # counter-example: F(1, k) = t(k)^2 exactly, so the F upper-tail p equals
    # the TWO-tailed t p-value, and half of it is the ONE-tailed t p-value.
    #
    # VERIFIED on that paper's own numbers: F(1,19) = 1.93 gives a two-tailed
    # 0.18083 and a one-tailed 0.09041 against a REPORTED 0.09 -- an exact
    # match, on a directional hypothesis. Reporting only the two-tailed value
    # turns an ordinary planned comparison into a finding, which is the
    # false-accusation direction this toolkit exists to avoid.
    #
    # Reported, never substituted: the two-tailed value stays the default,
    # because a paper that does not SAY it tested directionally has not earned
    # the halving. The reader is given both and told which is which.
    if df1 == 1:
        result["one_tailed_equivalent"] = {
            "p": calculated_p / 2.0,
            "t_equivalent": float(f_value) ** 0.5,
            "why": (
                "F(1, df2) = t(df2)^2, so this F's p IS the two-tailed t p-value "
                "and half of it is the one-tailed one. A paper testing a "
                "directional hypothesis may legitimately report the halved "
                "value, and a 'reported p is half the F implies' pattern across "
                "1-df tests is the signature of directional testing rather than "
                "of error."),
            "caveat": (
                "Only defensible if the paper STATES that its tests are "
                "one-tailed. If it does not, the discrepancy is a reporting "
                "omission -- not proof the arithmetic is wrong."),
        }
    elif reported_p is not None:
        result["one_tailed_equivalent"] = {
            "p": None,
            "why": (f"df1 = {df1}, so this F has no one-tailed reading: the "
                    "t-square identity holds only at df1 = 1, and an omnibus F "
                    "over several groups is upper-tailed by construction."),
        }

    if reported_p is not None:
        # The reported F is rounded; propagate its printed interval into a p
        # interval (p decreasing in F) and match the reported p against THAT.
        h_f = _half_for(f_value, decimals_f)
        p_lo_r = float(stats.f.sf(f_value + h_f, df1, df2))
        p_hi_r = float(stats.f.sf(max(0.0, f_value - h_f), df1, df2))
        h_p = _half_for(reported_p, decimals_p)
        result["reported_p"] = reported_p
        result["achievable_p_interval"] = [p_lo_r, p_hi_r]
        # OVER-CLAIM (reported p below the achievable interval) is suspicious;
        # an UNDER-claim above it only when the p was printed exact. See
        # `_apply_p_relation`.
        result["p_matches"] = bool(reported_p + h_p >= p_lo_r - _rounding.EPSILON)
        err = _apply_p_relation(result, p_hi_r, reported_p, decimals_p, p_relation,
                                f"the printed F({df1}, {df2}) = {f_value}", p_lo=p_lo_r,
                                p_adjustment=p_adjustment)
        if err:
            return {**result, "severity": INDETERMINATE, "error": err}
        result["severity"] = (SUSPICIOUS if not result["p_matches"]
                              else INDETERMINATE if result.get("under_claim_explained")
                              else CONSISTENT)
        if result.get("p_explanation"):
            result["explanation"] = result["p_explanation"]

        # THE ONE-TAILED READING HAS TO REACH THE SEVERITY, NOT JUST THE PROSE.
        #
        # Annotating the output was not enough. On PNAS 0801268105 this tool
        # already carried the ceiling note "a one-tailed test ... would explain a
        # disagreement", and the sweep read it, reasoned past it, and wrote that
        # "F has only an upper tail, so no one-tailed convention licenses it
        # here" -- which is false at df1 = 1 and produced a `suspicious` finding
        # against three p-values that reconcile EXACTLY on a directional reading.
        # A possibility the model has to remember is not a guard; an arithmetic
        # result it is handed is.
        #
        # So: at df1 = 1, if the reported p sits inside the HALVED achievable
        # interval, the disagreement has a complete ordinary explanation and this
        # tool does not accuse. It still says so, loudly, and the unstated tail
        # direction remains a legitimate question for the write-up -- but that is
        # a reporting observation, not a forensic signal, and ranking it
        # `suspicious` is how an honest planned comparison becomes a finding.
        if result.get("p_direction") == "under_claim":
            # Halving the p only moves the recomputation further below the
            # printed value, so no tail reading rescues an under-claim.
            pass
        elif df1 == 1 and not result["p_matches"]:
            one_tailed_lo = p_lo_r / 2.0
            # Under an EXACT p the halved reading must contain it from above too.
            reconciles = bool(
                reported_p + h_p >= one_tailed_lo - _rounding.EPSILON
                and not p_under_claimed(p_hi_r / 2.0, reported_p, decimals_p,
                                        result.get("p_relation")))
            result["one_tailed_reconciles"] = reconciles
            result["one_tailed_stated"] = bool(one_tailed_stated)
            if reconciles and not one_tailed_stated:
                # Only when the paper SAYS it tested one-tailed (1.93.0,
                # statcheck's OneTailedTxt rule): the finding stands, with the
                # one-tailed reading named beside it.
                result["failure_mode"] = "reconciles_only_one_tailed_unstated"
                result["explanation"] = (
                    str(result.get("explanation") or "") + " " + ONE_TAILED_UNSTATED_NOTE).strip()
            elif reconciles:
                # INDETERMINATE, not CONSISTENT. An independent adjudication of
                # the PNAS case (2026-08-16) landed on the distinction and it is
                # the right one: a free parameter the paper never states -- the
                # tail direction -- decides whether this p is correct, so we
                # cannot determine that it is. `consistent` would be a false
                # all-clear, which the cardinal ordering ranks second-worst;
                # `suspicious` would be the false accusation, which is worst.
                # `indeterminate` is simply accurate, and it keeps the
                # observation alive for the write-up instead of retiring it.
                result["severity"] = INDETERMINATE
                result["severity_note"] = (
                    f"Downgraded from {SUSPICIOUS}, and NOT to {CONSISTENT}. The "
                    f"reported p disagrees with the two-tailed interval "
                    f"[{p_lo_r:.5f}, {p_hi_r:.5f}] but falls inside the "
                    f"one-tailed interval [{one_tailed_lo:.5f}, "
                    f"{p_hi_r / 2.0:.5f}]. Since F(1, {df2}) = t({df2})^2, "
                    "halving is exactly what a directional hypothesis produces, "
                    "and the paper states that it tested one-tailed, so this is "
                    "NOT a p-value inconsistency. It stays indeterminate because "
                    "a paper-wide statement does not prove THIS test was "
                    "one-tailed: if the paper names it two-tailed, the mismatch "
                    "stands. A one-tailed test at alpha = .05 is a two-tailed "
                    "test at alpha = .10."
                )
        elif df1 > 1 and not result["p_matches"]:
            result["one_tailed_reconciles"] = False
    else:
        result["severity"] = INDETERMINATE

    result["methodology"] = (
        f"F-to-p conversion: F({df1}, {df2}) = {f_value} → p = {calculated_p:.6f}"
    )

    return result
