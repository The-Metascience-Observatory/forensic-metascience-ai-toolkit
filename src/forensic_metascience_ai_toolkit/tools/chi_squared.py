"""
Chi-Squared Test Recalculation

Recalculate chi-squared tests from contingency tables.
"""

import math
from typing import Optional

import numpy as np
from scipy import stats

from forensic_metascience_ai_toolkit.tools.severity import (
    CONSISTENT,
    INDETERMINATE,
    SUSPICIOUS,
    refuse_if_nonfinite,
)
from forensic_metascience_ai_toolkit.tools import rounding as _rounding
from forensic_metascience_ai_toolkit.tools.ttest import (
    _p_matches,
    bound_is_stated,
    check_p_adjustment,
    explain_under_claim,
    p_under_claimed,
    resolve_p_relation,
    under_claim_finding,
    under_claim_note,
)
from ..survey_design import survey_refusal


#: Largest number of tables `_freeman_halton_2xc` will enumerate. Beyond it the
#: exact p is not computed and the result says so.
_FFH_MAX_TABLES = 200_000


def _freeman_halton_2xc(table: np.ndarray) -> Optional[float]:
    """Exact Fisher-Freeman-Halton p for a 2xC (or Rx2) table, or None.

    Computed so the UNDER-claim test can try it: a paper that ran the exact
    test on a sparse RxC table prints a p that can sit well above Pearson's,
    and that is a convention, not an error. Enumerates every table with the
    observed margins, summing the probabilities no larger than the observed
    one. None when the table is not 2-by-something or too large to enumerate.
    """
    t = np.asarray(table, dtype=int)
    if t.shape[0] != 2 and t.shape[1] == 2:
        t = t.T
    if t.shape[0] != 2 or t.shape[1] < 2:
        return None
    cols = [int(c) for c in t.sum(axis=0)]
    r1 = int(t[0].sum())
    n = int(t.sum())
    count = 1
    for c in cols[:-1]:
        count *= min(c, r1) + 1
        if count > _FFH_MAX_TABLES:
            return None
    lg = math.lgamma
    log_denom = lg(n + 1) - lg(r1 + 1) - lg(n - r1 + 1)
    col_terms = [[lg(c + 1) - lg(x + 1) - lg(c - x + 1) for x in range(c + 1)]
                 for c in cols]
    obs = sum(col_terms[j][int(x)] for j, x in enumerate(t[0])) - log_denom
    total = 0.0

    def rec(j: int, rem: int, acc: float) -> None:
        nonlocal total
        if j == len(cols) - 1:
            if 0 <= rem <= cols[j]:
                lp = acc + col_terms[j][rem] - log_denom
                if lp <= obs + 1e-7:
                    total += math.exp(lp)
            return
        for x in range(0, min(rem, cols[j]) + 1):
            rec(j + 1, rem - x, acc + col_terms[j][x])

    rec(0, r1, 0.0)
    return float(min(1.0, total))


def recalc_chi_squared(
    observed: list[list[int]],
    reported_chi2: Optional[float] = None,
    reported_p: Optional[float] = None,
    use_yates: bool = False,
    decimals_p: Optional[int] = None,
    paired: bool = False,
    sampling: str = "simple_random",
    p_relation: Optional[str] = None,
    p_adjustment: Optional[str] = None,
) -> dict:
    """
    Recalculate chi-squared test from contingency table.

    BOTH-CONVENTIONS RULE (2x2 tables). A 2x2 table has two first-class
    textbook statistics: Pearson's chi-squared and the Yates-continuity-
    corrected chi-squared. R's `chisq.test` applies Yates BY DEFAULT on 2x2
    tables and scipy's `chi2_contingency` defaults to `correction=True`, so a
    paper printing either value is following a mainstream default, not making
    an error. Comparing the reported statistic against only ONE convention
    accuses every paper that used the other -- measured: [[15, 5], [8, 12]]
    has Pearson chi2 = 5.013 and Yates chi2 = 3.683, and a paper correctly
    reporting the Yates value 3.68 (p = .055) sat 1.33 away from the Pearson
    recomputation and was returned `suspicious`. Like DEBIT's sample/
    population-SD dual test (debit.py), reported values are therefore checked
    against BOTH conventions (plus Fisher's exact for the p), and flagged only
    when they match NEITHER. `use_yates` still selects which convention the
    headline `calculated_chi2` / `calculated_p` / `test_type` fields describe;
    it no longer decides which convention the paper is allowed to have used.

    McNEMAR IS A DIFFERENT STATISTIC, AND THE TABLE LOOKS THE SAME. A paired
    2x2 -- the same subjects measured twice -- is tested with McNemar's
    `(b-c)^2 / (b+c)` on the DISCORDANT cells only, not with a Pearson
    chi-squared of independence. Nothing in the counts distinguishes the two
    designs, so handing a McNemar table to this function used to produce a
    confident mismatch against a paper that had done nothing wrong.

    MEASURED 2026-08-22 on 10.1111--j.2044-835x.2011.02046.x: called with
    `observed=[[11, 6], [6, 0]]` and the paper's McNemar chi2 = 9.09, it
    answered "matches NEITHER convention: Pearson gives 2.8651 and
    Yates-corrected gives 1.3270" and returned `suspicious`. It reached no
    report only because that paper's model chose not to file it -- luck, not
    design.

    Rather than depend on the caller remembering (the GRIM-U lesson: model
    memory is not a guard), McNemar is now computed ALONGSIDE on every 2x2 and
    entered into the same both-conventions matching. A reported statistic that
    matches no Pearson convention but DOES match a McNemar one is reported as
    consistent-with-McNemar, because that is what the evidence says the paper
    ran. `paired=True` additionally makes McNemar the headline test.

    Args:
        observed: 2D contingency table. For `paired`, the 2x2 agreement table
            [[a, b], [c, d]] with b and c the discordant cells.
        reported_chi2: Chi-squared statistic reported in paper
        reported_p: P-value reported in paper
        use_yates: Convention shown in the headline calculated_* fields
            (matching always tries both conventions on a 2x2)
        paired: The table is a PAIRED 2x2 (McNemar), not an independence
            table. Makes McNemar the headline test; it is computed and matched
            against either way.
        p_relation: What the paper printed between "p" and the number: '='
            (exact), '<' (a bound), '>'. An exact p LARGER than every
            convention tried (Pearson, Yates, Fisher, McNemar, likelihood
            ratio, Fisher-Freeman-Halton) is an under-claim and flagged
            `suspicious`; a bound never is. Unstated, see
            `ttest.resolve_p_relation`.

    Returns:
        Dictionary with chi-squared, p-value, and Fisher's exact (for 2x2)
    """
    refusal = survey_refusal("recalc_chi_squared", sampling)
    if refusal is not None:
        return refusal
    guard = refuse_if_nonfinite(observed=observed, reported_chi2=reported_chi2,
                                reported_p=reported_p)
    if guard is not None:
        return guard

    observed_arr = np.array(observed, dtype=float)

    if observed_arr.ndim != 2 or observed_arr.size == 0:
        return {
            "error": "observed must be a non-empty 2D contingency table",
            "severity": INDETERMINATE,
        }
    if (observed_arr < 0).any():
        return {
            "error": "contingency table cannot contain negative counts",
            "severity": INDETERMINATE,
        }
    if (observed_arr.sum(axis=0) == 0).any() or (observed_arr.sum(axis=1) == 0).any():
        return {
            "error": (
                "contingency table has an all-zero row or column — "
                "chi-squared is undefined"
            ),
            "severity": INDETERMINATE,
            "inputs": {"observed": observed},
        }

    # Pearson chi-squared, and -- for 2x2 tables -- the Yates-corrected
    # variant as well. scipy applies the correction only at dof == 1, so for
    # larger tables the two conventions coincide and there is nothing to try.
    chi2_pearson, p_pearson, dof, expected = stats.chi2_contingency(
        observed_arr, correction=False
    )
    is_2x2 = observed_arr.shape == (2, 2)
    if is_2x2:
        chi2_yates, p_yates, _, _ = stats.chi2_contingency(
            observed_arr, correction=True
        )
    else:
        chi2_yates = None
        p_yates = None

    # McNEMAR, on the discordant cells only. Both conventions again, for the
    # reason the module already gives for Pearson/Yates: R's `mcnemar.test`
    # applies the continuity correction BY DEFAULT, so a paper printing either
    # value is following a mainstream default.
    chi2_mcnemar = p_mcnemar = chi2_mcnemar_cc = p_mcnemar_cc = None
    if is_2x2:
        b, c = float(observed_arr[0][1]), float(observed_arr[1][0])
        if b + c > 0:
            chi2_mcnemar = (b - c) ** 2 / (b + c)
            p_mcnemar = float(stats.chi2.sf(chi2_mcnemar, 1))
            # `max(..., 0)` because |b-c| < 1 makes the corrected statistic
            # negative, which is not a chi-squared value.
            chi2_mcnemar_cc = max(abs(b - c) - 1.0, 0.0) ** 2 / (b + c)
            p_mcnemar_cc = float(stats.chi2.sf(chi2_mcnemar_cc, 1))

    if paired and chi2_mcnemar is not None:
        chi2, p_primary = ((chi2_mcnemar_cc, p_mcnemar_cc) if use_yates
                           else (chi2_mcnemar, p_mcnemar))
    elif use_yates and is_2x2:
        chi2, p_primary = chi2_yates, p_yates
    else:
        chi2, p_primary = chi2_pearson, p_pearson

    result = {
        "calculated_chi2": float(chi2),
        "calculated_p": float(p_primary),
        "df": dof,
        "test_type": (("McNemar with continuity correction" if use_yates
                       else "McNemar")
                      if paired and chi2_mcnemar is not None
                      else ("Pearson with Yates" if use_yates else "Pearson")),
        "paired": bool(paired),
        "expected": expected.tolist(),
        "inputs": {"observed": observed},
        "calculated_chi2_pearson": float(chi2_pearson),
        "calculated_p_pearson": float(p_pearson),
    }
    if is_2x2:
        result["calculated_chi2_yates"] = float(chi2_yates)
        result["calculated_p_yates"] = float(p_yates)
    if chi2_mcnemar is not None:
        result["calculated_chi2_mcnemar"] = float(chi2_mcnemar)
        result["calculated_p_mcnemar"] = float(p_mcnemar)
        result["calculated_chi2_mcnemar_cc"] = float(chi2_mcnemar_cc)
        result["calculated_p_mcnemar_cc"] = float(p_mcnemar_cc)
    elif is_2x2 and paired:
        # b + c == 0: every pair agreed, and McNemar is undefined. Said out
        # loud rather than silently falling back to a test of independence.
        result["mcnemar_undefined"] = (
            "both discordant cells are zero, so McNemar's (b-c)^2/(b+c) is "
            "undefined; no paired statistic can be checked")

    # For 2x2 tables, also calculate Fisher's exact test
    if is_2x2:
        odds_ratio, p_fisher = stats.fisher_exact(observed_arr)
        result["fisher_p"] = float(p_fisher)
        result["fisher_odds_ratio"] = float(odds_ratio)

    matches: list[bool] = []
    # The reported STATISTIC's own printed precision is only half the story
    # here: the recomputed value also inherits the rounding of every mean and
    # SD it was built from, and propagating that through the test formula is
    # what `rivets_*` exists to do. Deriving a window from the reported
    # statistic alone would be TIGHTER than this constant, which is the
    # dangerous direction. Left as-is deliberately; reach for RIVETS when the
    # question is whether a reported statistic is reachable at all.
    if reported_chi2 is not None:
        result["reported_chi2"] = reported_chi2
        chi2_matches_pearson = bool(abs(chi2_pearson - reported_chi2) < 0.5)
        chi2_matches_yates = (
            bool(abs(chi2_yates - reported_chi2) < 0.5) if is_2x2 else None
        )
        chi2_matches_mcnemar = (
            bool(abs(chi2_mcnemar - reported_chi2) < 0.5)
            if chi2_mcnemar is not None else None)
        chi2_matches_mcnemar_cc = (
            bool(abs(chi2_mcnemar_cc - reported_chi2) < 0.5)
            if chi2_mcnemar_cc is not None else None)
        result["chi2_matches_pearson"] = chi2_matches_pearson
        result["chi2_matches_yates"] = chi2_matches_yates
        result["chi2_matches_mcnemar"] = chi2_matches_mcnemar
        result["chi2_matches_mcnemar_cc"] = chi2_matches_mcnemar_cc
        result["chi2_matches"] = bool(
            chi2_matches_pearson or chi2_matches_yates
            or chi2_matches_mcnemar or chi2_matches_mcnemar_cc)
        # McNEMAR IS TRIED LAST but is not a lesser answer: it is checked only
        # after the independence conventions so that an ordinary 2x2 keeps its
        # ordinary label, and reached only when neither of those explains the
        # printed value.
        if chi2_matches_pearson:
            result["chi2_match_convention"] = "pearson"
        elif chi2_matches_yates:
            result["chi2_match_convention"] = "yates"
        elif chi2_matches_mcnemar:
            result["chi2_match_convention"] = "mcnemar"
        elif chi2_matches_mcnemar_cc:
            result["chi2_match_convention"] = "mcnemar_cc"
        else:
            result["chi2_match_convention"] = None
        matches.append(result["chi2_matches"])
        if is_2x2:
            if result["chi2_match_convention"] == "yates" and not chi2_matches_pearson:
                result["explanation"] = (
                    f"Reported χ² = {reported_chi2} matches the Yates-corrected "
                    f"value ({chi2_yates:.4f}), not the uncorrected Pearson value "
                    f"({chi2_pearson:.4f}). Yates' correction is the default in "
                    "R's chisq.test for 2x2 tables -- a standard reporting "
                    "convention, not an inconsistency."
                )
            elif result["chi2_match_convention"] == "pearson" and not chi2_matches_yates:
                result["explanation"] = (
                    f"Reported χ² = {reported_chi2} matches the uncorrected "
                    f"Pearson value ({chi2_pearson:.4f}); the Yates-corrected "
                    f"value would be {chi2_yates:.4f}."
                )
            elif result["chi2_match_convention"] in ("mcnemar", "mcnemar_cc"):
                which = ("McNemar's" if result["chi2_match_convention"] == "mcnemar"
                         else "the continuity-corrected McNemar")
                result["explanation"] = (
                    f"Reported χ² = {reported_chi2} matches {which} statistic "
                    f"({chi2_mcnemar:.4f} uncorrected, {chi2_mcnemar_cc:.4f} "
                    f"corrected), not a test of independence (Pearson "
                    f"{chi2_pearson:.4f}, Yates {chi2_yates:.4f}). This is a "
                    "PAIRED table -- the same subjects measured twice -- and "
                    "McNemar is the right test for it. Not an inconsistency."
                )
            elif result["chi2_match_convention"] is None:
                mcnemar_note = (
                    f" McNemar's was also tried ({chi2_mcnemar:.4f} "
                    f"uncorrected, {chi2_mcnemar_cc:.4f} corrected), in case "
                    "the table is paired."
                    if chi2_mcnemar is not None else "")
                result["explanation"] = (
                    f"Reported χ² = {reported_chi2} matches NEITHER convention: "
                    f"Pearson gives {chi2_pearson:.4f} and Yates-corrected gives "
                    f"{chi2_yates:.4f} (both tried, window ±0.5). The mismatch is "
                    f"not explained by the continuity-correction convention."
                    f"{mcnemar_note}"
                )

    if reported_p is not None:
        result["reported_p"] = reported_p
        # INFER THE PRINTED PRECISION WHEN IT IS NOT SUPPLIED, rather than
        # falling into `_p_matches`'s precision-free branch. That fallback is
        # SYMMETRIC -- an absolute 0.005 band plus a relative one -- and a
        # symmetric test on a p is the defect this codebase has now named in
        # three other tools: it convicts the commonest convention in the
        # literature. A paper printing "chi2 = 18.00, p < .05" arrives here as
        # reported_p = 0.05 against a true p of 2.2e-05: a TRUE statement, wildly
        # UNDER-claimed, reported `suspicious`. Once the precision is known
        # `_p_matches` takes its DIRECTIONAL branch instead, where a computed p
        # below the claim is an under-claim and passes, and only an over-claim
        # flags.
        #
        # Inferred at this call site rather than by changing the shared default:
        # `_p_matches` backs four tools, and its own docstring says tightening it
        # centrally would turn correct results into findings across all of them
        # at once.
        dp = (decimals_p if decimals_p is not None
              else _rounding.decimals_of_value(reported_p))
        if dp is not None and decimals_p is None:
            result["decimals_p_inferred"] = dp
        resolved = resolve_p_relation(p_relation, reported_p)
        if "error" in resolved:
            return {**result, "severity": INDETERMINATE, "error": resolved["error"]}
        adj = check_p_adjustment(p_adjustment)
        if "error" in adj:
            return {**result, "severity": INDETERMINATE, "error": adj["error"]}
        rel = resolved["relation"]
        result["p_relation"] = rel
        result["p_relation_basis"] = resolved["basis"]
        # A declared bound is held to its exact endpoint (`bound_is_stated`).
        _thr = True if bound_is_stated(resolved) else None
        p_close = _p_matches(p_pearson, reported_p, dp, _thr)
        if is_2x2:
            p_close = p_close or _p_matches(p_yates, reported_p, dp, _thr)
        if "fisher_p" in result:
            p_close = p_close or _p_matches(result["fisher_p"], reported_p, dp, _thr)
        if rel == ">":
            # "p > x" cannot claim too much significance.
            p_close = True

        # THE UNDER-CLAIM TEST USES THE LARGEST p ANY CONVENTION GIVES. An exact
        # printed p above Pearson's may be a legitimate Yates, Fisher, McNemar,
        # likelihood-ratio or Fisher-Freeman-Halton p, so it is flagged only
        # when it sits above ALL of them. MEASURED 2026-10-18 (Singh 1997,
        # 10.1093/gerona/52A.1.M27): [[5,12],[7,8]] printed p = .71 against
        # Pearson .314, Yates .522, Fisher .467 -- `consistent` until 1.86.0.
        p_g = None
        try:
            p_g = float(stats.chi2_contingency(
                observed_arr, correction=False, lambda_="log-likelihood")[1])
        except (ValueError, FloatingPointError):
            p_g = None
        if p_g is not None and math.isfinite(p_g):
            result["calculated_p_likelihood_ratio"] = p_g
        p_ffh = None if is_2x2 else _freeman_halton_2xc(observed_arr)
        if p_ffh is not None:
            result["calculated_p_freeman_halton"] = p_ffh
        candidates = [p for p in (p_pearson, p_yates, result.get("fisher_p"),
                                  p_mcnemar, p_mcnemar_cc,
                                  result.get("calculated_p_likelihood_ratio"),
                                  p_ffh) if p is not None]
        p_hi = float(max(candidates))
        result["largest_convention_p"] = p_hi
        if p_close and p_under_claimed(p_hi, reported_p, dp, rel):
            uc = explain_under_claim(under_claim_finding(
                p_hi, reported_p, dp, resolved,
                "every convention tried on this table (Pearson, Yates, Fisher, "
                "McNemar, likelihood ratio, Fisher-Freeman-Halton where they "
                "apply)"), p_adjustment=adj["adjustment"])
            p_close = bool(uc.get("under_claim_explained"))
            uc.pop("severity")
            uc.pop("consistent")
            result["p_explanation"] = uc.pop("explanation")
            result.update(uc)
        elif p_close and rel is None and p_under_claimed(p_hi, reported_p, dp, "="):
            result["under_claim_if_exact"] = True
            result["p_explanation"] = under_claim_note(p_hi, reported_p)
        result["p_matches"] = bool(p_close)
        matches.append(bool(p_close))

    if not matches:
        result["severity"] = INDETERMINATE
    elif all(matches):
        # An under-claim the paper explains is not a match either: undetermined.
        result["severity"] = (INDETERMINATE if result.get("under_claim_explained")
                              else CONSISTENT)
    else:
        result["severity"] = SUSPICIOUS
    if result.get("p_explanation"):
        result["explanation"] = (
            (result["explanation"] + " " if result.get("explanation") else "")
            + result["p_explanation"])

    both_note = ""
    if is_2x2:
        both_note = (
            f" Both 2x2 conventions tried for the match: Pearson χ² = "
            f"{chi2_pearson:.4f} (p = {p_pearson:.6f}), Yates-corrected χ² = "
            f"{chi2_yates:.4f} (p = {p_yates:.6f}); a reported statistic "
            "matching either convention (or Fisher's exact, for the p) is "
            "consistent."
        )
    result["methodology"] = (
        f"Chi-squared test ({result['test_type']}): χ² = {chi2:.4f}, df = {dof}, "
        f"p = {p_primary:.6f}.{both_note}"
    )

    return result
