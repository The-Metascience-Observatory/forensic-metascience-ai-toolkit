"""
T-Test Recalculation Tools

Recalculate independent and within-subjects (paired) t-tests
from reported group statistics.
"""

import math
from typing import Optional

from scipy import stats

from . import rounding as _rounding
from .severity import CONSISTENT, HIGHLY_SUSPICIOUS, INDETERMINATE, SUSPICIOUS
from ..survey_design import survey_refusal


def _p_matches(calculated_p: float, reported_p: float,
               decimals_p: Optional[int] = None,
               p_is_threshold: Optional[bool] = None) -> bool:
    """Match allowing for the reported p being rounded (or truncated) in print.

    Shared by the t-test, ANOVA, chi-squared and regression checks, so this one
    function decides how forgiving four tools are.

    `decimals_p` is the precision the p was PRINTED to: a p printed `.03`
    asserts [.025, .035), and one printed `.0312` asserts [.03115, .03125). The
    fallback used when it is absent hard-codes the first of those -- `<= 0.005`,
    i.e. two decimals -- for every p in the literature, and adds a relative
    `0.5 * reported_p` band that at p = .04 accepts a computed .06, a different
    significance decision. That fallback stays, because tightening a shared
    predicate by default would turn correct results into findings across four
    tools at once.

    A DECLARED BOUND IS NOT A ROUNDED VALUE, and until 2026-08-12 it was
    treated as one. `p < .001` asserts an interval whose endpoint is written
    EXACTLY; `.001` there is not a rounded rendering of some unprinted p, so it
    carries no half-width of its own. Applying the rounding allowance to it
    anyway accepted a computed p of .006 against a claimed bound of .001 --
    six times the claim -- and, worse, the tolerance did not shrink when the
    caller supplied the very declaration meant to sharpen it:

        _p_matches(0.004, 0.001)                         -> True   (slab .005)
        _p_matches(0.004, 0.001, p_is_threshold=True)    -> True   (unchanged!)
        _p_matches(0.004, 0.001, decimals_p=3)           -> False

    So declaring "this p is a printed bound" made the check no stricter than
    saying nothing. It now holds the paper to the number it actually printed.
    The protection against INPUT rounding stays where it belongs: the caller
    passes the low end of the achievable p interval (`check_regression` and
    `recalc_f_to_p` both do), so a bound is contradicted only when no reading
    of the rounded inputs can reach it.

    THE TWO DIRECTIONS ARE NOT SYMMETRIC, and treating them as if they were
    made the printed-precision branch a false-accusation machine on the
    commonest convention in the literature. `p < .001` arrives here as
    `reported_p = 0.001` printed to three decimals, and a genuine computed p of
    1e-12 sits far below that interval -- so a strict two-sided interval test
    convicts every correctly reported `p < .001` there is.

    * **Calculated ABOVE the interval** -- the paper reported a SMALLER p than
      its own numbers support. That is overclaiming, and it is the finding.
    * **Calculated BELOW the interval** -- the paper reported a LARGER p than
      its numbers support. Either it printed a threshold, or it understated its
      own result. Neither is misconduct, and the first is everywhere.

    `p_is_threshold` says which case applies. `None` -- the default -- means
    unknown, and the interval is then enforced only in the overclaiming
    direction. Pass `False` only having checked that the paper printed an exact
    value.

    THE ASYMMETRY APPLIES TO THE FALLBACK TOO, and until 2026-08-09 it did not:
    `p_is_threshold` was read only inside the `decimals_p` branch, so a caller
    who explicitly declared "this p is a printed bound" got the symmetric
    fallback anyway and the declaration did nothing.

    MEASURED across every archived run, re-counted 2026-08-12: 745 archived
    calls pass a p to these tools. `decimals_p` is supplied on 554 of them
    (74.4%) -- up from 2 of 186 when the paragraph above was written, so the
    precision-free fallback now governs a minority. `p_is_threshold` is
    supplied on 24 (3.2%), and only three registry tools of the thirteen that
    take a p can be told it at all. `0.001` is the single commonest reported
    value (51 calls), which is the censored shape this now reads correctly.
    Reproduced, before the earlier fix:

        check_regression(b=0.55, se=0.13, reported_p=0.01, df=200)
            -> suspicious            (true p 3e-5; an honest "p < .01" row)
        ... the same call with p_is_threshold=True
            -> suspicious            (the guard was inert)
        ... the same call with decimals_p=2
            -> consistent

    The fix keeps the UPPER bound exactly where it was, so nothing that was
    caught in the overclaiming direction stops being caught; it drops only the
    lower bound, and only when the caller has not confirmed the p is exact.
    """
    if p_is_threshold is True:
        # A bound the paper printed: hold it to that number, not to a rounding
        # interval it never claimed. Whatever precision the caller declared
        # describes the digits of the bound, not slack around it.
        return bool(calculated_p <= reported_p + _rounding.EPSILON)
    if decimals_p is not None:
        half = _rounding.half_width(decimals_p) + _rounding.EPSILON
        if p_is_threshold is False:
            return _rounding.matches_at_precision(calculated_p, reported_p, decimals_p)
        # An unknown that might be a bound: consistent unless the computed p is
        # larger than what was claimed.
        return bool(calculated_p <= reported_p + half)
    tol = max(0.005, 0.5 * reported_p)
    if p_is_threshold is False:
        return bool(abs(calculated_p - reported_p) <= tol)
    return bool(calculated_p <= reported_p + tol)


#: The comparison a paper printed with its p, normalised to one of three
#: relations. `check_estimate_ci` takes the same spellings as
#: `reported_p_operator`; the recalculation tools take them as `p_relation`.
P_RELATIONS = {"=": "=", "==": "=", "<": "<", "<=": "<", "≤": "<",
               ">": ">", ">=": ">", "≥": ">"}


#: The `p_relation` parameter help, shared by every tool that takes one.
P_RELATION_HELP = (
    "What the paper printed between 'p' and the number: '=' for an exact p "
    "('p = .03'), '<' for a bound ('p < .05'), '>' for 'p > .05'. An exact p is "
    "checked in BOTH directions; a bound only against over-claiming. Unset, a "
    "value that is no conventional bound is read as exact and .05/.01/.001 as a "
    "possible bound -- so pass '=' for an exact 'p = .05'.")


def looks_like_printed_bound(p: Optional[float]) -> bool:
    """Could `p` be the endpoint of a printed bound ("p < .05", "p < .001")?

    Bounds are printed at conventional alphas or at powers of ten at or below
    .001 ("p < .0001", "p < 1e-10"). A value like .696 or .26 is not the
    endpoint of any bound a paper writes, so when the relation is not supplied
    it can only have been printed as an exact value.
    """
    if p is None:
        return False
    return bool(is_conventional_alpha(p) or 0.0 <= p <= 0.001 + _rounding.EPSILON)


def resolve_p_relation(p_relation: Optional[str], reported_p: Optional[float],
                       p_is_threshold: Optional[bool] = None) -> dict:
    """Which relation did the paper print between its p and the number?

    Returns `{"relation": "=" | "<" | ">" | None, "basis": ...}`, or
    `{"error": ...}` for an unknown spelling or a contradiction.

    THE UNDER-CLAIM DIRECTION WAS NEVER CHECKED, and that hid real errors.
    `_p_matches` (below the printed precision) and every tool's own interval
    test pass a recomputed p BELOW the printed one, because "p < .05" against
    a true 2e-5 is a true statement. That is right for a BOUND and wrong for an
    EXACT value. MEASURED on the statcheck_pvalue_errors corpus, 2026-10-18,
    each a documented published error that came back `consistent`:

        recalc_stat_to_p(t=3.94, df=38, reported_p=.696)    true p .00034
        recalc_stat_to_p(F=11.38, df=2, 66, reported_p=.26)  true p 6e-5
        recalc_chi_squared([[5,12],[7,8]], reported_p=.71)   Pearson .314,
                                                             Yates .522

    Basis, in order:

    * `stated`          -- the caller passed `p_relation`.
    * `p_is_threshold`  -- the legacy flag: True is "<", False is "=".
    * `not_bound_shaped` -- not supplied, and the printed value is not the
      endpoint of any bound papers print (`looks_like_printed_bound`), so it
      can only be exact. This is what catches the three rows above when the
      caller says nothing.
    * `unknown`         -- not supplied and the value IS bound-shaped
      (.05, .001): relation None, and the tool keeps the directional rule.
      Reading "p < .001" as exact would accuse every correctly reported
      highly significant result in the literature.
    """
    if p_relation is not None:
        rel = P_RELATIONS.get(str(p_relation).strip())
        if rel is None:
            return {"error": (f"p_relation must be one of '=', '<', '<=', '>', "
                              f"'>=' (got {p_relation!r})")}
        if p_is_threshold is not None and (rel == "<") != bool(p_is_threshold):
            return {"error": (f"p_relation={p_relation!r} contradicts "
                              f"p_is_threshold={p_is_threshold!r}; pass one")}
        return {"relation": rel, "basis": "stated"}
    if p_is_threshold is True:
        return {"relation": "<", "basis": "p_is_threshold"}
    if p_is_threshold is False:
        return {"relation": "=", "basis": "p_is_threshold"}
    if reported_p is not None and not looks_like_printed_bound(reported_p):
        return {"relation": "=", "basis": "not_bound_shaped"}
    return {"relation": None, "basis": "unknown"}


def p_under_claimed(p_hi: Optional[float], reported_p: Optional[float],
                    decimals_p: Optional[int], relation: Optional[str]) -> bool:
    """Is the printed p LARGER than every p the paper's own numbers allow?

    `p_hi` is the LARGEST achievable recomputed p (the top of the interval the
    rounded inputs span, or the largest across the conventions a tool tries),
    so input rounding never manufactures this. An exact p asserts its rounding
    interval, whose bottom is `printed - half` (a truncated p's interval,
    `[printed, printed + ulp)`, starts higher, so this is the forgiving edge).
    A ">" claim asserts every p above the printed number. A "<" claim, or an
    unknown relation, can never be under-claimed.
    """
    if p_hi is None or reported_p is None:
        return False
    if relation == "=":
        d = decimals_p if decimals_p is not None else _rounding.decimals_of_value(reported_p)
        if d is None:
            return False
        return bool(reported_p - _rounding.half_width(d) - _rounding.EPSILON > p_hi)
    if relation == ">":
        return bool(reported_p - _rounding.EPSILON > p_hi)
    return False


#: Severity of an under-claim. A paper printing LESS significance than its
#: numbers support is a reporting inconsistency -- a typo, a p copied from
#: another row, an adjusted p beside a raw statistic -- and never evidence of
#: fabrication, so this never goes above `suspicious`, even when it flips the
#: significance decision.
UNDER_CLAIM_SEVERITY = SUSPICIOUS


def under_claim_finding(p_hi: float, reported_p: float, decimals_p: Optional[int],
                        resolved: dict, what: str, alpha: float = 0.05) -> dict:
    """The fields an under-claim adds to a tool's result (severity included)."""
    rel = resolved.get("relation")
    d = decimals_p if decimals_p is not None else _rounding.decimals_of_value(reported_p)
    half = _rounding.half_width(0 if d is None else d) if rel == "=" else 0.0
    # A decision error: the printed p says non-significant at alpha and every
    # recomputation says significant. "p > .05" says so at the bound itself.
    claims_ns = (reported_p >= alpha - _rounding.EPSILON if rel == ">"
                 else reported_p - half > alpha + _rounding.EPSILON)
    decision = bool(claims_ns and p_hi < alpha - _rounding.EPSILON)
    printed = f"p {rel} {reported_p}"
    explanation = (
        f"The paper prints {printed}, but recomputed from {what} p is at most "
        f"{p_hi:.4g}, allowing for the rounding of every printed input: the "
        "paper reports LESS "
        "significance than its own numbers show"
        + (f", and on the other side of alpha = {alpha:g} (a decision error)"
           if decision else "")
        + ". This is a reporting inconsistency, not the over-claiming "
        "direction, and not evidence of fabrication.")
    if resolved.get("basis") == "not_bound_shaped":
        explanation += (
            f" The relation was not supplied; {reported_p} is not the endpoint "
            "of a conventional bound, so it was read as an exact value.")
    return {
        "severity": UNDER_CLAIM_SEVERITY,
        "consistent": False,
        "p_direction": "under_claim",
        "failure_mode": "reported_p_above_recomputed",
        "decision_error": decision,
        "p_relation": rel,
        "p_relation_basis": resolved.get("basis"),
        "explanation": explanation,
        "alternative_reading": (
            f"If the paper printed a BOUND ('p < {reported_p}'), re-run with "
            "p_relation='<': a bound is satisfied by any smaller p. A "
            "multiplicity-adjusted p (Bonferroni, Holm) printed beside its raw "
            "statistic is also larger than the statistic implies -- check the "
            "methods for a correction. Otherwise the likeliest causes are a "
            "typo or a p taken from a different row or test."),
    }


def under_claim_note(p_hi: float, reported_p: float) -> str:
    """Said when the relation is unknown and an exact reading would flag."""
    return (
        f"The recomputed p (at most {p_hi:.4g}) is below the printed {reported_p}. "
        "Read as a bound ('p < x') that is consistent; read as an EXACT value it "
        "is an under-claim. The relation was not supplied: if the paper printed "
        "'p = ...', re-run with p_relation='='.")


def bound_is_stated(resolved: dict) -> bool:
    """A "p < x" the caller DECLARED, held to its exact endpoint.

    A printed bound is not a rounded value: "p < .01" asserts p < .01 exactly,
    so it gets no rounding half-width -- only the statistic's own rounding
    (the achievable interval) protects the paper. MEASURED 2026-10-18 on the
    1,120 statistics Wicherts, Bakker & Molenaar (2011) coded by hand
    (benchmarks/pvalue_tools): with the slack, `t(15) = 2.75, p < .01` (true
    p .0149) passed, and the bound misses were most of the 34 labelled errors
    `recalc_stat_to_p` did not catch. An UNKNOWN relation on a conventional
    alpha (basis `unknown`) keeps the slack: it may be an exact .05.
    """
    return resolved.get("relation") == "<" and resolved.get("basis") in ("stated", "p_is_threshold")


#: Corrections a paper can declare that legitimately print a p LARGER than the
#: raw statistic implies. Huynh-Feldt / Greenhouse-Geisser applied to the p
#: while the uncorrected df are printed, and a Bonferroni / Holm / Tukey /
#: Scheffe adjusted p beside its raw statistic, both look like an under-claim.
#: MEASURED 2026-10-18: all 12 false flags on the 1,071 correct Wicherts
#: statistics were Huynh-Feldt p's, and 95 of 96 statcheck flags Nuijten et al.
#: (2017) found explained by a declared correction were flagged.
P_ADJUSTMENTS = ("none", "sphericity", "multiplicity", "unknown")

P_ADJUSTMENT_HELP = (
    "Whether the paper DECLARES a correction applied to its p: 'sphericity' "
    "(Greenhouse-Geisser / Huynh-Feldt with the uncorrected df printed), "
    "'multiplicity' (Bonferroni, Holm, Tukey, Scheffe or another adjusted p "
    "printed beside the raw statistic), 'none', or 'unknown' (default). A "
    "declared correction explains a printed p LARGER than the statistic "
    "implies, so that direction becomes indeterminate; a printed p SMALLER "
    "than the statistic allows is still a finding. Quote the Methods sentence.")

TEST_CONFIRMED_HELP = (
    "True only when the paper states the printed p comes from THIS test on "
    "these summary statistics (quote it). Otherwise (default) a printed p "
    "LARGER than these means/SDs imply is indeterminate: an ANCOVA, mixed "
    "model, Welch or nonparametric p legitimately exceeds the simple test's. "
    "A printed p SMALLER than the summary statistics allow is still a finding.")


#: statcheck's `OneTailedTxt` rule (1.93.0): a one-tailed reading may explain a
#: mismatch only when the paper SAYS, anywhere, that it tested one-tailed.
ONE_TAILED_STATED_HELP = (
    "True only when the paper says, anywhere, that its tests are one-tailed, "
    "one-sided or directional (quote it) -- statcheck's rule. A 1-df F or "
    "chi-squared whose printed p is only reachable as a one-tailed test is "
    "then indeterminate; otherwise (default) it is a finding, with the "
    "one-tailed reading named beside it.")

#: Why an unstated one-tailed reading no longer rescues a p (1.93.0).
ONE_TAILED_UNSTATED_NOTE = (
    "It would be consistent with a ONE-tailed test, but the paper does not "
    "say it used one, so that reading is not assumed (statcheck's rule: a "
    "one-tailed test explains a mismatch only when the text states one-tailed, "
    "one-sided or directional testing). If the paper does say so anywhere, "
    "call again with one_tailed_stated=True. MEASURED 2026-10-18: the unstated "
    "rescue hid 21 of the 49 errors Wicherts, Bakker & Molenaar (2011) coded "
    "by hand and decided no correct statistic.")


def check_p_adjustment(value: Optional[str]) -> dict:
    """`{"adjustment": ...}` (None when not supplied) or `{"error": ...}`."""
    if value is None:
        return {"adjustment": None}
    v = str(value).strip().lower()
    if v not in P_ADJUSTMENTS:
        return {"error": f"p_adjustment must be one of {', '.join(P_ADJUSTMENTS)} (got {value!r})"}
    return {"adjustment": v}


def explain_under_claim(uc: dict, p_adjustment: Optional[str] = None,
                        test_confirmed: Optional[bool] = None) -> dict:
    """`under_claim_finding`'s fields, demoted to indeterminate when the paper
    itself explains a printed p above the recomputed one.

    `test_confirmed` is None for a tool that recomputes from the paper's own
    printed statistic; False for one that RECONSTRUCTS the test from summary
    statistics without the paper saying that test produced the printed p.
    Only the under-claim direction is ever excused: a p smaller than the
    numbers allow is never explained by either reason.
    """
    reason = None
    if p_adjustment in ("sphericity", "multiplicity"):
        reason = ("under_claim_explained_by_adjustment",
                  f"The paper declares a {p_adjustment} correction, which prints a p "
                  "larger than the raw statistic implies; this under-claim is "
                  "explained, not a finding.")
    elif test_confirmed is False:
        reason = ("under_claim_unconfirmed_test",
                  "The p is recomputed from printed summary statistics with a test "
                  "the paper does not say it used; an adjusted, mixed-model, Welch or "
                  "nonparametric p legitimately exceeds it, so this under-claim is "
                  "not a finding. Pass test_confirmed=True with a quote if the paper "
                  "states the test.")
    if reason is None:
        return uc
    return {**uc, "severity": INDETERMINATE, "consistent": None, "failure_mode": reason[0],
            "under_claim_explained": True,
            "explanation": uc.get("explanation", "") + " " + reason[1]}


def _half_for(value: float, decimals: Optional[int]) -> float:
    """Half-width of a printed input's rounding interval.

    Explicit `decimals` (the precision AS PRINTED) wins; the fallback for a
    bare parsed float is `rounding.decimals_of_value`, which deliberately errs
    towards the WIDER interval (see its docstring) -- too wide only misses,
    too tight accuses.
    """
    d = decimals if decimals is not None else _rounding.decimals_of_value(value)
    return _rounding.half_width(0 if d is None else d)


def _valid_r_within_rounding(mean_pre, sd_pre, mean_post, sd_post, n, p_value,
                             p_tail, df, decimals_mean, decimals_sd, decimals_p,
                             result) -> bool:
    """Is a correlation in [-1, 1] reachable within the inputs' rounding box?

    The paired-r recovery uses point estimates, but every reported statistic is
    rounded and r is sensitive to all of them (r can legitimately approach
    (sd_pre²+sd_post²)/(2·sd_pre·sd_post) > 1 when the SDs differ). Evaluate r at
    the corners of the joint rounding box -- means/SDs at their printed
    half-widths, p across its printed interval -- record the attainable
    [min, max] on `result`, and return True when that interval intersects
    [-1, 1], i.e. a valid correlation is reachable and no inconsistency can be
    established from these rounded numbers.
    """
    h_mpre = _half_for(mean_pre, decimals_mean)
    h_mpost = _half_for(mean_post, decimals_mean)
    h_spre = _half_for(sd_pre, decimals_sd)
    h_spost = _half_for(sd_post, decimals_sd)
    h_p = (_rounding.half_width(decimals_p) if decimals_p is not None
           else _rounding.half_width(_rounding.decimals_of_value(p_value)))
    p_lo = max(1e-9, p_value - h_p)
    p_hi = min(1 - 1e-9, p_value + h_p)

    def _r_at(mp, sp, mq, sq, pp):
        if sp <= 0 or sq <= 0:
            return None
        tail = pp / 2 if p_tail == "two" else pp
        t_ = stats.t.ppf(1 - tail, df)
        den = 2 * t_ ** 2 * sp * sq
        if den == 0:
            return None
        return (t_ ** 2 * (sp ** 2 + sq ** 2) - n * (mq - mp) ** 2) / den

    rs = []
    for mp in (mean_pre - h_mpre, mean_pre + h_mpre):
        for mq in (mean_post - h_mpost, mean_post + h_mpost):
            for sp in (max(1e-9, sd_pre - h_spre), sd_pre + h_spre):
                for sq in (max(1e-9, sd_post - h_spost), sd_post + h_spost):
                    for pp in (p_lo, p_hi):
                        rr = _r_at(mp, sp, mq, sq, pp)
                        if rr is not None:
                            rs.append(rr)
    if not rs:
        return False
    r_min, r_max = float(min(rs)), float(max(rs))
    result["attainable_r_interval"] = [r_min, r_max]
    return (r_min <= 1 + _rounding.EPSILON) and (r_max >= -1 - _rounding.EPSILON)


def _independent_t_branches(
    mean1: float, sd1: float, n1: int, mean2: float, sd2: float, n2: int,
) -> Optional[dict]:
    """t, df and p under BOTH standard flavors of the independent t-test.

    `welch` (unequal variances) and `student` (pooled variance) are both
    routine, defensible analyses of the same two-group summary, and with
    unequal n/SD their t statistics differ substantially because the pooled SE
    is not the Welch SE. A check that recomputes only one flavor convicts
    every paper that ran the other. NOTE the Student branch pools the
    variances: the previous code reused the Welch SE and only swapped the df,
    which is not Student's test and made a correctly computed pooled t
    unreachable even when explicitly requested.

    Returns None when both SDs are zero (t undefined under either flavor).
    """
    se1_sq = sd1**2 / n1
    se2_sq = sd2**2 / n2
    se_welch = math.sqrt(se1_sq + se2_sq)
    if se_welch == 0:
        return None
    df_welch = (se1_sq + se2_sq) ** 2 / (
        se1_sq**2 / (n1 - 1) + se2_sq**2 / (n2 - 1)
    )
    sp_sq = ((n1 - 1) * sd1**2 + (n2 - 1) * sd2**2) / (n1 + n2 - 2)
    se_student = math.sqrt(sp_sq * (1 / n1 + 1 / n2))
    df_student = n1 + n2 - 2
    diff = mean1 - mean2
    out: dict = {}
    for name, se, df in (
        ("welch", se_welch, df_welch),
        ("student", se_student, df_student),
    ):
        t = diff / se
        p_two = float(2 * stats.t.sf(abs(t), df))
        out[name] = {
            "t": t,
            "df": df,
            "se": se,
            "p_two_tailed": p_two,
            # The favourable-direction one-tailed reading, the convention a
            # one-tailed report actually prints.
            "p_one_tailed": p_two / 2.0,
        }
    return out


def _branch_t_interval(
    flavor: str,
    mean1: float, sd1: float, n1: int, mean2: float, sd2: float, n2: int,
    h_m1: float, h_s1: float, h_m2: float, h_s2: float,
) -> tuple[float, Optional[float]]:
    """The |t| interval reachable from the printed means/SDs under one flavor.

    Rounding of the inputs propagates MULTIPLICATIVELY into t, so the
    reachable spread grows with the statistic; a fixed absolute window that is
    generous at t = 1.5 convicts honestly reported values at t = 30. The
    numerator (|mean difference|) and denominator (SE) are each monotone in
    their inputs, so the extremes sit at the interval corners exactly.

    Returns (t_lo, t_hi); t_hi is None when the SE can reach zero, in which
    case no finite reported t can be refuted from these inputs.
    """
    d = abs(mean1 - mean2)
    d_hi = d + h_m1 + h_m2
    d_lo = max(0.0, d - h_m1 - h_m2)
    s1_lo, s1_hi = max(0.0, sd1 - h_s1), sd1 + h_s1
    s2_lo, s2_hi = max(0.0, sd2 - h_s2), sd2 + h_s2
    if flavor == "welch":
        se_lo = math.sqrt(s1_lo**2 / n1 + s2_lo**2 / n2)
        se_hi = math.sqrt(s1_hi**2 / n1 + s2_hi**2 / n2)
    else:
        factor = (1 / n1 + 1 / n2) / (n1 + n2 - 2)
        se_lo = math.sqrt(((n1 - 1) * s1_lo**2 + (n2 - 1) * s2_lo**2) * factor)
        se_hi = math.sqrt(((n1 - 1) * s1_hi**2 + (n2 - 1) * s2_hi**2) * factor)
    t_lo = d_lo / se_hi  # se_hi > 0: the both-SDs-zero case was rejected earlier
    t_hi = (d_hi / se_lo) if se_lo > 0 else None
    return t_lo, t_hi


def recalc_independent_t(
    mean1: float,
    sd1: float,
    n1: int,
    mean2: float,
    sd2: float,
    n2: int,
    reported_p: Optional[float] = None,
    reported_t: Optional[float] = None,
    use_welch: Optional[bool] = None,
    decimals_p: Optional[int] = None,
    p_tail: str = "unknown",
    decimals_mean: Optional[int] = None,
    decimals_sd: Optional[int] = None,
    sampling: str = "simple_random",
    p_relation: Optional[str] = None,
    p_adjustment: Optional[str] = None,
    test_confirmed: bool = False,
) -> dict:
    """
    Recalculate an independent samples t-test from group statistics.

    FALSE-POSITIVE CONTROL (same shape as DEBIT's two SD conventions and
    `recalc_within_subjects_t`'s `p_tail`): a reported t/p is judged against
    every standard reading the paper could legitimately have used, and a
    mismatch is a finding only when NO standard reading explains it.

    * Test flavor: Welch's (unequal variances) and Student's (pooled) t are
      both routine. `use_welch=None` (default, "the paper does not say") accepts
      either; True/False pins the flavor the paper states, and a value that
      then fits only the OTHER flavor is reported as suspicious with the
      convention named -- a wrong-line copy, not fabrication.
    * Tail: `p_tail="unknown"` (default) accepts a two- or one-tailed reported
      p; "two"/"one" pins it, with the same capped treatment for the
      alternative.
    * Input rounding: the reported t is compared against the t interval
      reachable from the printed means/SDs (precision from
      decimals_mean/decimals_sd when given, else inferred wide), plus the
      historical 0.1 absolute floor -- never against the point estimate alone,
      whose distance from a correctly reported t grows with the statistic.

    Args:
        mean1, sd1, n1: Group 1 statistics
        mean2, sd2, n2: Group 2 statistics
        reported_p: P-value reported in paper (for comparison)
        reported_t: T-statistic reported in paper (for comparison)
        use_welch: True = Welch, False = Student, None = unstated (accept both)
        decimals_p: Printed decimals of reported_p
        p_tail: "two" | "one" | "unknown" -- tail convention of reported_p
        decimals_mean, decimals_sd: Printed decimals of the means/SDs
        p_relation: '=' (exact), '<' (a bound) or '>' -- what the paper
            printed with the p; see `resolve_p_relation`. An exact p above
            every p the rounded inputs reach is an under-claim, `suspicious`.

    Returns:
        Dictionary with calculated values and comparison to reported
    """
    refusal = survey_refusal("recalc_independent_t", sampling)
    if refusal is not None:
        return refusal
    if n1 < 2 or n2 < 2:
        return {
            "error": f"Both groups need n ≥ 2 (got n1={n1}, n2={n2})",
            "severity": INDETERMINATE,
        }
    if sd1 < 0 or sd2 < 0:
        return {
            "error": f"SDs cannot be negative (got sd1={sd1}, sd2={sd2})",
            "severity": INDETERMINATE,
        }
    if p_tail not in ("two", "one", "unknown"):
        return {
            "error": f"p_tail must be 'two', 'one' or 'unknown' (got {p_tail!r})",
            "severity": INDETERMINATE,
        }

    branches = _independent_t_branches(mean1, sd1, n1, mean2, sd2, n2)
    if branches is None:
        return {
            "error": "Both SDs are zero — t-statistic is undefined",
            "severity": INDETERMINATE,
        }

    flavors_all = ("welch", "student")
    pinned_flavors = (
        ("welch",) if use_welch is True
        else ("student",) if use_welch is False
        else flavors_all
    )
    tails_all = ("two", "one")
    pinned_tails = tails_all if p_tail == "unknown" else (p_tail,)

    primary = "student" if use_welch is False else "welch"
    t_stat = branches[primary]["t"]
    df = branches[primary]["df"]
    p_value = branches[primary]["p_two_tailed"]

    result = {
        "calculated_t": t_stat,
        "calculated_df": df,
        "calculated_p": p_value,
        "test_type": (
            "Welch" if use_welch is True
            else "Student" if use_welch is False
            else "Welch|Student (unstated; both checked)"
        ),
        "p_tail": p_tail,
        "branches": {
            name: {k: b[k] for k in ("t", "df", "p_two_tailed", "p_one_tailed")}
            for name, b in branches.items()
        },
        "inputs": {
            "group1": {"mean": mean1, "sd": sd1, "n": n1},
            "group2": {"mean": mean2, "sd": sd2, "n": n2},
            "use_welch": use_welch,
            "p_tail": p_tail,
        },
    }

    # Per-flavor verdicts on each reported statistic.
    p_ok: dict[str, bool] = {}
    p_ok_any_tail: dict[str, bool] = {}
    t_ok: dict[str, bool] = {}
    resolved = resolve_p_relation(p_relation, reported_p)
    if "error" in resolved:
        return {"error": resolved["error"], "severity": INDETERMINATE}
    adj = check_p_adjustment(p_adjustment)
    if "error" in adj:
        return {"error": adj["error"], "severity": INDETERMINATE}
    rel = resolved["relation"]
    # A declared bound is held to its exact endpoint (`bound_is_stated`).
    _thr = True if bound_is_stated(resolved) else None
    # The LARGEST p each flavor's printed inputs reach, per tail: the smallest
    # |t| their rounding allows, at the most conservative df (Welch's df is
    # never below min(n) - 1). Under an exact relation a tail reading matches
    # only if the printed p is not above it.
    h_in = (_half_for(mean1, decimals_mean), _half_for(sd1, decimals_sd),
            _half_for(mean2, decimals_mean), _half_for(sd2, decimals_sd))
    p_hi_tail: dict[str, dict[str, float]] = {}
    for f, df_c in (("welch", min(n1, n2) - 1), ("student", n1 + n2 - 2)):
        t_lo_f = _branch_t_interval(f, mean1, sd1, n1, mean2, sd2, n2, *h_in)[0]
        one = float(stats.t.sf(t_lo_f, df_c))
        p_hi_tail[f] = {"two": 2 * one, "one": one}
    if reported_p is not None:
        result["p_relation"] = rel
        result["p_relation_basis"] = resolved["basis"]
        for f in flavors_all:
            by_tail = {
                "two": _p_matches(branches[f]["p_two_tailed"], reported_p, decimals_p, _thr),
                "one": _p_matches(branches[f]["p_one_tailed"], reported_p, decimals_p, _thr),
            }
            if rel == ">":
                # "p > x" cannot claim too much significance; only the
                # under-claim test below can contradict it.
                by_tail = {"two": True, "one": True}
            by_tail = {tail: ok and not p_under_claimed(
                           p_hi_tail[f][tail], reported_p, decimals_p, rel)
                       for tail, ok in by_tail.items()}
            p_ok[f] = any(by_tail[tail] for tail in pinned_tails)
            p_ok_any_tail[f] = any(by_tail.values())
        result["reported_p"] = reported_p
        result["p_matches"] = any(p_ok[f] for f in pinned_flavors)
        result["p_difference"] = abs(p_value - reported_p)

    # The reported t inherits the rounding of every mean and SD it was built
    # from, and that error is MULTIPLICATIVE: at t ~ 30 the reachable spread
    # from 2 dp inputs exceeds the old fixed 0.1 window several times over.
    # The interval below propagates the printed precision through the formula
    # exactly (corner evaluation; see rounding.quotient_interval for the same
    # move on regression t = B/SE); the historical 0.1 stays as an additive
    # floor so nothing the old window accepted is newly accused. RIVETS remains
    # the tool of record for reachability with Monte Carlo + hand-calc
    # signatures.
    if reported_t is not None:
        h_m1 = _half_for(mean1, decimals_mean)
        h_m2 = _half_for(mean2, decimals_mean)
        h_s1 = _half_for(sd1, decimals_sd)
        h_s2 = _half_for(sd2, decimals_sd)
        intervals: dict[str, tuple[float, Optional[float]]] = {}
        for f in flavors_all:
            t_lo, t_hi = _branch_t_interval(
                f, mean1, sd1, n1, mean2, sd2, n2, h_m1, h_s1, h_m2, h_s2
            )
            intervals[f] = (t_lo, t_hi)
            t_ok[f] = bool(
                abs(reported_t) >= t_lo - 0.1 - _rounding.EPSILON
                and (t_hi is None or abs(reported_t) <= t_hi + 0.1 + _rounding.EPSILON)
            )
            result["branches"][f]["achievable_t_interval"] = [t_lo, t_hi]
        result["reported_t"] = reported_t
        result["t_matches"] = any(t_ok[f] for f in pinned_flavors)

    # A legitimate paper ran ONE test: consistency means a single flavor
    # explains every reported statistic simultaneously (its p under some
    # accepted tail), not p under one flavor and t under another.
    def _flavor_explains(f: str, tails_ok: dict[str, bool]) -> bool:
        if reported_p is not None and not tails_ok.get(f, False):
            return False
        if reported_t is not None and not t_ok.get(f, False):
            return False
        return True

    if reported_p is None and reported_t is None:
        result["severity"] = INDETERMINATE
        result["explanation"] = "No reported t or p was given to compare against."
    else:
        explained_pinned = [f for f in pinned_flavors if _flavor_explains(f, p_ok)]
        explained_any = [f for f in flavors_all if _flavor_explains(f, p_ok_any_tail)]
        result["explained_by"] = explained_pinned or explained_any
        if explained_pinned:
            result["severity"] = CONSISTENT
            result["explanation"] = (
                "Reported statistics are consistent with "
                + " / ".join(f"{f.capitalize()}'s t-test" for f in explained_pinned)
                + " on these group statistics."
            )
        elif explained_any:
            # DEBIT's pattern for the alternative convention: a standard
            # reading the caller did not pin explains the numbers -- a
            # reporting-convention question, never accusation-grade.
            result["severity"] = SUSPICIOUS
            result["explanation"] = (
                "The reported statistics do not fit the stated convention "
                f"(flavor={'/'.join(pinned_flavors)}, tail={'/'.join(pinned_tails)}) "
                "but ARE internally consistent under "
                + " / ".join(f"{f.capitalize()}'s t-test" for f in explained_any)
                + (" with a one-tailed p" if (reported_p is not None
                   and not any(p_ok.get(f, False) for f in explained_any)) else "")
                + ". That is a reporting-convention difference (e.g. the other "
                "software output line, or an unstated one-tailed test), not "
                "evidence of fabrication."
            )
        else:
            result["severity"] = SUSPICIOUS
            result["explanation"] = (
                "The reported statistics fit NEITHER Welch's nor Student's "
                "t-test on these group statistics, under either tail "
                "convention, allowing for rounding of the printed inputs."
            )
            if (reported_p is not None and rel is None
                    and is_conventional_alpha(reported_p)):
                bound_ok = False
                for f in flavors_all:
                    for key in ("p_two_tailed", "p_one_tailed"):
                        p_calc = branches[f].get(key)
                        if p_calc is not None and _p_matches(
                                p_calc, reported_p, decimals_p,
                                p_is_threshold=True):
                            bound_ok = True
                            break
                    if bound_ok:
                        break
                if bound_ok:
                    result["severity"] = INDETERMINATE
                    result["failure_mode"] = "p_reading_ambiguous"
                    result["explanation"] = (
                        "Reported p equals a conventional alpha. Read as an "
                        "exact value it mismatches; read as a threshold bound "
                        "it does not accuse. The two readings disagree, so "
                        "this is not reported as a finding."
                    )

        # UNDER-CLAIM: an exact printed p ABOVE every p the printed means and
        # SDs can reach -- under either flavor, two-tailed, at the smallest |t|
        # their rounding allows and the most conservative df (Welch's df is
        # never below min(n) - 1). A bound is satisfied by any smaller p.
        if reported_p is not None and rel in ("=", ">"):
            p_hi = max(v["two"] for v in p_hi_tail.values())
            result["largest_achievable_p"] = p_hi
            if p_under_claimed(p_hi, reported_p, decimals_p, rel):
                # RECONSTRUCTED from printed means/SDs: unless the paper says this
                # t-test produced its p (`test_confirmed`), an under-claim is not
                # a finding -- an ANCOVA, mixed-model or nonparametric p exceeds it.
                uc = explain_under_claim(
                    under_claim_finding(p_hi, reported_p, decimals_p, resolved,
                                        "the printed group means and SDs"),
                    p_adjustment=adj["adjustment"], test_confirmed=bool(test_confirmed))
                prior = (result.get("explanation")
                         if result.get("severity") == SUSPICIOUS else None)
                if uc.get("under_claim_explained") and result.get("t_matches") is False:
                    # The printed t ALREADY contradicts the means/SDs, which does
                    # not depend on the p: keep that finding; only the p's
                    # under-claim is excused.
                    result["under_claim_explained"] = True
                    result["p_explanation"] = uc["explanation"]
                else:
                    result.update(uc)
                    result.pop("consistent", None)
                    result["p_matches"] = None if uc.get("under_claim_explained") else False
                if prior and result.get("t_matches") is False:
                    result["explanation"] = prior + " " + uc["explanation"]
        elif (reported_p is not None and rel is None
              and result.get("severity") == CONSISTENT):
            p_hi = max(v["two"] for v in p_hi_tail.values())
            if p_under_claimed(p_hi, reported_p, decimals_p, "="):
                result["under_claim_if_exact"] = True
                result["explanation"] += " " + under_claim_note(p_hi, reported_p)

    result["methodology"] = (
        "Independent samples t-test, both flavors: "
        f"Welch t = {branches['welch']['t']:.4f} (df = {branches['welch']['df']:.2f}, "
        f"two-tailed p = {branches['welch']['p_two_tailed']:.6f}); "
        f"Student t = {branches['student']['t']:.4f} (df = {branches['student']['df']:.0f}, "
        f"two-tailed p = {branches['student']['p_two_tailed']:.6f}). "
        "A reported value counts as matching if any accepted flavor/tail "
        "reading reaches it within the rounding interval of the printed "
        "means/SDs (plus the historical 0.1 floor on t)."
    )

    return result


def _parse_reported_p(reported_p) -> tuple[float | None, bool]:
    """Parse a reported p-value that may be a threshold string ("p<0.05", "≤.01").

    Returns (value, is_threshold). A value carrying `<`/`≤` is a BOUND, not an
    exact p: treating it as exact understates t and drives the recovered
    correlation far negative, which previously produced spurious `impossible`
    findings. We therefore auto-detect it rather than trusting the caller.
    """
    if isinstance(reported_p, str):
        s = reported_p.strip().lstrip("pP=").strip()
        is_threshold = any(ch in s for ch in ("<", "≤"))
        s = s.replace("<", "").replace("≤", "").replace("=", "").strip()
        try:
            return float(s), is_threshold
        except ValueError:
            return None, is_threshold
    try:
        return float(reported_p), False
    except (TypeError, ValueError):
        return None, False


#: p-values papers print as a BOUND far more often than as an exact result.
#: A bare float equal to one of these is ambiguous, and the guard inside
#: `recalc_within_subjects_t` refuses when the two readings disagree.
_CONVENTIONAL_ALPHAS = (0.1, 0.05, 0.025, 0.01, 0.005, 0.001)


def is_conventional_alpha(p: float | None) -> bool:
    """True if `p` is exactly a conventional alpha (0.05, 0.01, ...)."""
    if p is None:
        return False
    try:
        val = float(p)
    except (TypeError, ValueError):
        return False
    return any(math.isclose(val, a, rel_tol=0.0, abs_tol=1e-12)
               for a in _CONVENTIONAL_ALPHAS)


def recalc_within_subjects_t(
    mean_pre: float,
    sd_pre: float,
    mean_post: float,
    sd_post: float,
    n: int,
    reported_p,
    p_is_threshold: bool = False,
    p_tail: str = "two",
    decimals_mean: Optional[int] = None,
    decimals_sd: Optional[int] = None,
    decimals_p: Optional[int] = None,
    sampling: str = "simple_random",
) -> dict:
    """
    Analyze within-subjects (paired) t-test and recover hidden correlation.

    For paired t-tests, we can recover the correlation between measurements
    from the reported statistics. If the implied correlation is impossible
    (|r| > 1), this is a flag.

    Based on Jané et al. (2024) methodology from Heathers (2025).

    IMPORTANT (false-positive control): the recovered r is monotonically
    INCREASING in t, and t is determined by the p-value. Papers overwhelmingly
    report thresholds ("p < .05") rather than exact p-values. Passing a
    threshold as if it were exact understates t and drags r far below -1,
    which reads as fabrication-grade evidence when it is only a reporting
    convention. When the p is a bound, the recovered r is likewise only a
    LOWER bound, so we report the attainable interval and return
    `indeterminate` unless the *entire* interval lies outside [-1, 1].

    Args:
        mean_pre: Pre-test mean
        sd_pre: Pre-test SD
        mean_post: Post-test mean
        sd_post: Post-test SD
        n: Sample size
        reported_p: Reported p-value. May be a float, or a string such as
            "<0.05" / "≤.01" — a threshold string is auto-detected.
        p_is_threshold: True if reported_p is an upper bound ("p < x") rather
            than an exact value. Auto-set when reported_p is a threshold string.
        p_tail: "two" (default) or "one" — the tail convention of the reported p.
        decimals_mean, decimals_sd, decimals_p: Printed decimals of the
            means / SDs / p. Every input is rounded, and the recovered r is
            sensitive to all of them (r can legitimately approach
            (sd_pre²+sd_post²)/(2·sd_pre·sd_post) > 1 when the SDs differ), so an
            exact-p r just outside [-1, 1] may be nothing but rounding. When the
            recovered r is invalid, the attainable r is computed over the joint
            rounding box and the inconsistency is only reported if the WHOLE
            interval lies outside [-1, 1]. Absent, the precision is inferred from
            the printed floats (erring wide).

    Returns:
        Dictionary with recovered correlation and validity check
    """
    refusal = survey_refusal("recalc_within_subjects_t", sampling)
    if refusal is not None:
        return refusal
    p_value, detected_threshold = _parse_reported_p(reported_p)
    p_is_threshold = bool(p_is_threshold or detected_threshold)

    if n < 2:
        return {
            "error": f"n must be ≥ 2 (got {n})",
            "severity": INDETERMINATE,
        }
    if p_value is None:
        return {
            "error": f"reported_p could not be parsed (got {reported_p!r})",
            "severity": INDETERMINATE,
        }
    if not (0 < p_value < 1):
        return {
            "error": f"reported_p must be in (0, 1) (got {p_value})",
            "severity": INDETERMINATE,
        }
    if p_tail not in ("two", "one"):
        return {
            "error": f"p_tail must be 'two' or 'one' (got {p_tail!r})",
            "severity": INDETERMINATE,
        }
    if sd_pre <= 0 or sd_post <= 0:
        return {
            "error": f"SDs must be positive (got sd_pre={sd_pre}, sd_post={sd_post})",
            "severity": INDETERMINATE,
        }

    # A THRESHOLD P, PASSED AS AN EXACT ONE, IS THE INPUT ERROR THIS TOOL
    # CANNOT SURVIVE -- AND IT HAS ALREADY HAPPENED.
    #
    # The docstring above explains why a bound must not be read as a value.
    # The guard fires correctly when it is TOLD: `reported_p="<0.05"` returns
    # `indeterminate`. But the caller strips the "<" and the same paper's row
    # becomes `highly_suspicious`:
    #
    #   reported_p="<0.05"  -> indeterminate,      r interval [-80.22, 1.013]
    #   reported_p="0.05"   -> highly_suspicious,  r interval [-90.59, -70.90]
    #
    # MEASURED: a stage-1 sweep recorded the second interval for seven paired
    # rows of `10.17116--jnevro20181185139`, six of which the paper printed as
    # "p<0.05". That produced the review's `highly_suspicious` headline against
    # a real paper, and it had to be retracted -- recomputing the attainable p
    # over every r in [-1, 1] gives, for the MMSE row, [2.1e-31, 4.5e-11]:
    # every attainable value already satisfies p<0.05, so nothing was
    # established at all.
    #
    # A tool cannot see the "<" that was stripped upstream. What it CAN do is
    # notice that the p it was handed is exactly a conventional alpha -- a
    # value papers print as a bound far more often than as an exact result --
    # and check whether the finding survives the other reading. If reading the
    # same p as a bound dissolves the finding, then the two readings disagree,
    # we cannot tell which we were given, and the house rule applies: refuse
    # rather than accuse. If the finding survives BOTH readings it is robust to
    # the ambiguity and proceeds untouched, so a genuinely extreme exact-p case
    # is not lost.
    if not p_is_threshold and any(
            math.isclose(p_value, a, rel_tol=0.0, abs_tol=1e-12)
            for a in _CONVENTIONAL_ALPHAS):
        as_bound = recalc_within_subjects_t(
            mean_pre, sd_pre, mean_post, sd_post, n, p_value,
            p_is_threshold=True, p_tail=p_tail,
            decimals_mean=decimals_mean, decimals_sd=decimals_sd,
            decimals_p=decimals_p,
        )
        if as_bound.get("severity") == INDETERMINATE:
            return {
                "severity": INDETERMINATE,
                "failure_mode": "p_reading_ambiguous",
                "recovered_correlation": None,
                "correlation_valid": None,
                "p_is_threshold": False,
                "p_tail": p_tail,
                "attainable_r_interval_as_bound":
                    as_bound.get("attainable_r_interval"),
                "explanation": (
                    f"The reported p was given as exactly {p_value:g}, which is a "
                    "conventional significance threshold. Papers print that value "
                    "as a BOUND ('p < " f"{p_value:g}') far more often than as an "
                    "exact result, and the two readings disagree here: read as an "
                    "exact value this would be a finding, but read as a bound it "
                    "establishes nothing, because the attainable correlation "
                    "interval reaches the valid range. Since we cannot tell which "
                    "was meant, nothing is reported. To settle it, supply the exact "
                    "p to more decimal places, or the paired t statistic -- or pass "
                    "p_is_threshold=True if the paper printed an inequality."
                ),
                "inputs": {
                    "mean_pre": mean_pre, "sd_pre": sd_pre,
                    "mean_post": mean_post, "sd_post": sd_post,
                    "n": n, "reported_p": reported_p,
                    "p_is_threshold": False, "p_tail": p_tail,
                },
            }

    # Get paired t from p-value.
    # Two-tailed: p = 2*P(T > |t|)  ->  |t| = qt(1 - p/2, df)
    # One-tailed: p =   P(T > |t|)  ->  |t| = qt(1 - p,   df)
    df = n - 1
    reported_p = p_value
    tail_prob = reported_p / 2 if p_tail == "two" else reported_p
    paired_t = stats.t.ppf(1 - tail_prob, df)

    # Mean difference
    mean_diff = mean_post - mean_pre

    # Recover correlation using the formula from Jané et al.
    # r = (t²*(sd_pre² + sd_post²) - n*(mean_diff)²) / (2*t²*sd_pre*sd_post)
    numerator = paired_t**2 * (sd_pre**2 + sd_post**2) - n * mean_diff**2
    denominator = 2 * paired_t**2 * sd_pre * sd_post

    if denominator == 0:
        recovered_r = None
        r_valid = False
    else:
        recovered_r = numerator / denominator
        r_valid = -1 <= recovered_r <= 1

    # Calculate SD of change scores
    if recovered_r is not None and r_valid:
        sd_change = math.sqrt(sd_pre**2 + sd_post**2 - 2 * sd_pre * sd_post * recovered_r)
    else:
        sd_change = None

    # Calculate t-test denominator
    t_denom = mean_diff / paired_t if paired_t != 0 else None

    # Supremum of the recoverable r as t -> infinity (i.e. as the true p -> 0).
    # By AM-GM this is always >= 1, so a thresholded p can essentially never
    # prove impossibility from below.
    r_supremum = (sd_pre**2 + sd_post**2) / (2 * sd_pre * sd_post)

    result = {
        "recovered_correlation": recovered_r,
        "correlation_valid": r_valid,
        "recovered_paired_t": paired_t,
        "mean_difference": mean_diff,
        "sd_change": sd_change,
        "t_denominator": t_denom,
        "p_is_threshold": p_is_threshold,
        "p_tail": p_tail,
        "inputs": {
            "mean_pre": mean_pre,
            "sd_pre": sd_pre,
            "mean_post": mean_post,
            "sd_post": sd_post,
            "n": n,
            "reported_p": reported_p,
            "p_is_threshold": p_is_threshold,
            "p_tail": p_tail,
        },
    }

    if recovered_r is None:
        result["severity"] = INDETERMINATE
        result["explanation"] = (
            "Correlation could not be recovered (degenerate denominator: "
            "recovered t = 0 or an SD is zero)."
        )
    elif p_is_threshold:
        # The reported p is an upper bound, so t is a lower bound, so the
        # recovered r is a LOWER bound. The attainable set is [recovered_r, r_supremum].
        result["recovered_correlation_is_lower_bound"] = True
        result["attainable_r_interval"] = [recovered_r, r_supremum]
        if recovered_r > 1 and not _valid_r_within_rounding(
                mean_pre, sd_pre, mean_post, sd_post, n, reported_p, p_tail, df,
                decimals_mean, decimals_sd, decimals_p, result):
            # CAPPED AT `highly_suspicious`, AND THE ROUNDING BOX IS CHECKED
            # FIRST. Both were missing, and together they made this the harshest
            # branch in the function on the WEAKEST evidence:
            #
            #   mean_pre 10.0 / sd_pre 2.0 / mean_post 10.2 / sd_post 4.0, n=20
            #     reported "p < 0.001" (a BOUND)      -> `impossible`
            #     reported "p = 0.0005" (an EXACT p)  -> `highly_suspicious`
            #
            # The exact p is the stronger claim and the threshold only bounds t,
            # so the ladder was inverted. The exact branch below already routes
            # through `_valid_r_within_rounding` -- every input is printed and
            # rounded, and r is sensitive to all of them -- and already caps,
            # because the recovery assumes a standard paired t-test and a tail
            # convention. Those are ASSUMPTIONS, and an assumed model may not
            # reach `impossible`, whichever branch reads it.
            result["severity"] = HIGHLY_SUSPICIOUS
            result["explanation"] = (
                f"Even at the reported bound, and across the rounding interval of every "
                f"input, the attainable correlation lies above 1 (from "
                f"[{recovered_r:.4f}, {r_supremum:.4f}] at the printed values). No "
                "correlation can satisfy these statistics AS A PAIRED T-TEST read at "
                "this tail convention -- which is the likeliest thing to be wrong here, "
                "so this is reported below fabrication grade."
            )
        else:
            result["severity"] = INDETERMINATE
            result["explanation"] = (
                f"The reported p is a threshold, so the recovered r = {recovered_r:.4f} is only a "
                f"LOWER bound; the attainable interval is [{recovered_r:.4f}, {r_supremum:.4f}], "
                "which intersects the valid range [-1, 1]. No inconsistency can be established "
                "from a thresholded p-value. Obtain the exact p (or t) to test this properly."
            )
    elif not r_valid and _valid_r_within_rounding(
            mean_pre, sd_pre, mean_post, sd_post, n, reported_p, p_tail, df,
            decimals_mean, decimals_sd, decimals_p, result):
        # The point estimate recovered r outside [-1, 1], but every input is
        # rounded and r is sensitive to all of them: across the printed rounding
        # box a valid correlation is reachable, so the reported numbers are
        # reconcilable at their own precision and NOTHING is established.
        # Verified: p = 0.001 with sd_pre=10, sd_post=13 recovers r = 1.0001 at
        # the point but r = 0.9971 at the upper edge of p's 3-dp interval.
        r_lo, r_hi = result["attainable_r_interval"]
        result["severity"] = INDETERMINATE
        result["explanation"] = (
            f"The point estimate recovers r = {recovered_r:.4f} (outside [-1, 1]), but across "
            f"the rounding intervals of the reported statistics the attainable r spans "
            f"[{r_lo:.4f}, {r_hi:.4f}], which reaches the valid range. At their printed "
            "precision the reported numbers are reconcilable with a real correlation, so no "
            "inconsistency is established. (Also rule out an undeclared threshold p, or a "
            "one-tailed p read as two-tailed.)"
        )
    elif not r_valid:
        # Exact-p reading, |r| > 1 even across the rounding box. This is a real
        # tension between the reported p and the reported means/SDs -- but the
        # overwhelmingly common causes are benign reporting conventions (an
        # undetected threshold, or a one-tailed p read as two-tailed), NOT
        # fabrication. Never escalate to `impossible`.
        if recovered_r < -1:
            cause = (
                "the reported p-value is too LARGE for the reported pre/post change "
                "(a smaller p / larger t would be required)"
            )
        else:
            cause = (
                "the reported p-value is too SMALL for the reported pre/post change "
                "(a larger p / smaller t would be required)"
            )
        result["severity"] = "highly_suspicious"
        result["explanation"] = (
            f"Recovered correlation r = {recovered_r:.4f} lies outside [-1, 1], meaning {cause}. "
            "Before treating this as evidence, rule out the benign explanations: an undeclared "
            "threshold p (re-run with p_is_threshold=True) or a one-tailed p read as two-tailed "
            "(re-run with p_tail='one'). Reported as highly_suspicious, not impossible, because "
            "reporting convention -- not data fabrication -- is the most common cause."
        )
    else:
        result["severity"] = CONSISTENT
        result["explanation"] = (
            f"Recovered correlation r = {recovered_r:.4f} is valid. "
            f"SD of change scores = {sd_change:.4f}."
        )

    result["methodology"] = (
        f"Within-subjects t-test analysis: From p = {reported_p}, recovered t = {paired_t:.4f}. "
        f"Using Jané et al. (2024) formula to recover correlation: "
        f"r = (t²(SD₁² + SD₂²) - n*d²) / (2t²*SD₁*SD₂) = "
        + (f"{recovered_r:.4f}." if recovered_r is not None else "undefined.")
    )

    return result
