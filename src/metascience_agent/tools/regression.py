"""
Regression Coefficient Checks

Verify consistency between regression coefficients, standard errors,
t-statistics, and p-values.
"""

from typing import Optional

from scipy import stats

from . import rounding as _rounding
from .severity import CONSISTENT, INDETERMINATE, SUSPICIOUS
from .ttest import (_p_matches, bound_is_stated, check_p_adjustment,
                    explain_under_claim, p_under_claimed, resolve_p_relation,
                    under_claim_finding, under_claim_note)


def _abs_interval(lo: float, hi: float) -> tuple[float, float]:
    """Magnitude range of a value known to lie in [lo, hi].

    When the interval straddles zero the magnitude reaches 0; otherwise it is
    the sorted absolute endpoints. Used to compare a reported |t| against the
    recomputed t interval when the paper printed a magnitude, not a signed t.
    """
    if lo <= 0 <= hi:
        return 0.0, max(abs(lo), abs(hi))
    a, b = abs(lo), abs(hi)
    return (a, b) if a <= b else (b, a)


def check_regression(
    b: float,
    se: float,
    reported_t: Optional[float] = None,
    reported_p: Optional[float] = None,
    df: Optional[int] = None,
    decimals_b: Optional[int] = None,
    decimals_se: Optional[int] = None,
    decimals_t: Optional[int] = None,
    decimals_p: Optional[int] = None,
    p_is_threshold: Optional[bool] = None,
    p_relation: Optional[str] = None,
    p_adjustment: Optional[str] = None,
) -> dict:
    """
    Verify regression coefficient consistency.

    t = B / SE should hold, and p should match t with given df.

    ROUNDING. `t` is recomputed from two values the paper ROUNDED, so it is an
    interval and not a point -- and the width of that interval depends on the
    MAGNITUDE of SE, not only on the printed precisions. B = 2.0 with SE = 0.5
    pins t to about +/-0.5; the same precisions with SE = 0.05 leave t anywhere
    within about +/-11. This check previously used a flat `|dt| < 0.1`, which
    is far too tight for the second case -- it accuses correctly-reported
    tables -- and needlessly loose for the first.

    Args:
        b: Unstandardized coefficient
        se: Standard error of coefficient
        reported_t: T-statistic reported in paper
        reported_p: P-value reported in paper
        df: Degrees of freedom (needed for p-value check)
        decimals_b, decimals_se, decimals_t: PRINTED precision of each value.
            Pass them whenever the source literals survive. Omitted, they are
            inferred from the parsed floats towards the WIDER interval (see
            `rounding.decimals_of_value`) and the result says so.
        p_relation: What the paper printed with the p: '=' (exact), '<' (a
            bound), '>'. Supersedes `p_is_threshold` ('<' is True, '=' is
            False); unstated, see `ttest.resolve_p_relation`. An exact p above
            the whole achievable interval is an under-claim, `suspicious`.

    Returns:
        Dictionary with consistency checks
    """
    if se <= 0:
        # A NEGATIVE SE IS OUR ARTEFACT, NOT THEIR CLAIM. No software prints a
        # negative standard error, so a minus sign here came from OUR parse: an
        # en dash or a range separator ("0.4 - 0.9") read as a sign. Reporting
        # it as `impossible` publishes an extraction bug in the grammar of an
        # accusation, which is the failure this codebase keeps finding. The
        # sibling `recalc_independent_t` already refuses a negative SD as
        # `indeterminate` for exactly this reason; match it.
        #
        # It was also a ceiling violation: this tool is `probabilistic`, whose
        # declared ceiling is `highly_suspicious`, and `impossible` sat above it.
        return {
            "error": f"SE must be positive (got {se})",
            "severity": INDETERMINATE,
            "explanation": (
                "Not evaluated. A standard error of zero or below is not something "
                "any analysis produces, so this is almost certainly a value we "
                "mis-read (a dash or a range separator taken for a minus sign). "
                "Re-read the cell and call again."
            ),
        }

    calculated_t = b / se

    dp_b = decimals_b if decimals_b is not None else _rounding.decimals_of_value(b)
    dp_se = decimals_se if decimals_se is not None else _rounding.decimals_of_value(se)
    # `None` here means the value is not a finite number, so nothing about its
    # precision is known -- and `rounding`'s own rule is that unknown precision
    # licenses no verdict. Without this, a NaN coefficient produced a NaN
    # interval, a False `t_matches`, and a `suspicious` accusation against a
    # cell nobody could read.
    if dp_b is None or dp_se is None:
        return {
            "b": b, "se": se,
            "severity": INDETERMINATE,
            "error": (
                "Cannot evaluate: b or se is not a finite number, so neither "
                "its value nor its printed precision is known."
            ),
        }
    inferred = [name for name, given in
                (("b", decimals_b), ("se", decimals_se)) if given is None]

    result = {
        "b": b,
        "se": se,
        "calculated_t": calculated_t,
    }
    if inferred:
        result["precision_inferred"] = inferred

    matches: list[bool] = []
    if reported_t is not None:
        result["reported_t"] = reported_t
        result["t_difference"] = calculated_t - reported_t
        dp_t = decimals_t if decimals_t is not None else _rounding.decimals_of_value(reported_t)
        span = _rounding.quotient_interval(b, dp_b or 0, se, dp_se or 0)
        if span is None:
            # SE's rounding interval reaches zero, so B/SE is unbounded and no
            # comparison against the reported t means anything. Refuse rather
            # than fall back to a constant.
            result["t_matches"] = None
            result["t_interval"] = None
            result["severity"] = INDETERMINATE
            result["methodology"] = (
                f"Regression check refused: SE = {se} printed to {dp_se} decimal(s) "
                "has a rounding interval that includes zero, so B/SE is unbounded."
            )
            return result
        lo, hi = span
        half_t = _rounding.half_width(dp_t or 0)
        result["t_interval"] = [lo, hi]
        # Two intervals, not a point against a window: the recomputed t is a
        # range implied by the rounded inputs, and the reported t is a range
        # implied by ITS own printed precision. They are consistent if they
        # overlap at all.
        signed_ok = (lo - _rounding.EPSILON <= reported_t + half_t
                     and hi + _rounding.EPSILON >= reported_t - half_t)
        # SIGN CONVENTION. Regression tables routinely print |t| (or a |B| whose
        # sign the accompanying t drops), so a negative coefficient recomputes to
        # a NEGATIVE t interval while the table shows the positive t of the same
        # magnitude -- correct arithmetic the signed test alone rejects as
        # `suspicious`. Try the signed overlap first, then the magnitude overlap,
        # and accuse only if BOTH fail: the same try-both-conventions rule the
        # SD, GRIM and chi-square guards use before ever accusing.
        m_lo, m_hi = _abs_interval(lo, hi)
        mag_ok = (m_lo - _rounding.EPSILON <= abs(reported_t) + half_t
                  and m_hi + _rounding.EPSILON >= abs(reported_t) - half_t)
        result["t_matches"] = bool(signed_ok or mag_ok)
        if mag_ok and not signed_ok:
            # The magnitude reconciles but the printed sign disagrees with B/SE.
            # A sign slip is a transcription error, not the significance
            # over-claim this tool hunts, so it does not escalate the severity --
            # but record it so a reader is not left thinking the cell was clean.
            result["sign_mismatch"] = True
        # A window can legitimately be as wide as the estimate. B = 0.03 with
        # SE = 0.01, both at 2 dp, admits any t from 1.67 to 7.00 -- arithmetic
        # that is entirely correct and a check with no power whatever. Calling
        # that `consistent` is the false-clear this codebase has had to fix in
        # three other batch tools: zero inconsistent rows out of zero evaluable
        # rows reads as a clean bill of health. Say `indeterminate` instead.
        width = hi - lo
        result["t_interval_width"] = width
        if width >= abs(calculated_t):
            result["t_matches"] = None
            result["low_power"] = True
            result["severity"] = INDETERMINATE
            result["methodology"] = (
                f"Regression check inconclusive: B = {b} and SE = {se} at {dp_b} and "
                f"{dp_se} printed decimals admit any t in [{lo:.4f}, {hi:.4f}], a window "
                f"at least as wide as the estimate itself ({calculated_t:.4f}). The "
                "arithmetic is right and the check has no power at this precision."
            )
            return result
        matches.append(result["t_matches"])

    if df is not None and reported_p is not None:
        calculated_p = 2 * stats.t.sf(abs(calculated_t), df)
        result["calculated_p"] = calculated_p
        result["reported_p"] = reported_p
        result["df"] = df
        # The p is recomputed from the SAME rounded B and SE as the t, so it is
        # an interval too. Testing the point p against a window while testing
        # the t against an interval convicted honest tables: B = 0.11, SE = 0.05
        # and t = 2.46 all print correctly from B = 0.1148, SE = 0.0467, and the
        # t branch cleared it while the p branch reported it `suspicious`.
        #
        # p is monotone decreasing in |t|, so the p interval is spanned by the
        # t interval's endpoints -- except where the t interval straddles zero,
        # where |t| reaches 0 and p reaches 1.
        span = result.get("t_interval")
        if span is None:
            span = _rounding.quotient_interval(b, dp_b or 0, se, dp_se or 0)
        if span is None:
            result["p_matches"] = None
            result["severity"] = INDETERMINATE
            result["methodology"] = (
                f"Regression check refused: SE = {se} printed to {dp_se} decimal(s) "
                "has a rounding interval that includes zero, so B/SE is unbounded."
            )
            return result
        t_lo, t_hi = span
        t_abs = [abs(t_lo), abs(t_hi)] + ([0.0] if t_lo <= 0 <= t_hi else [])
        sf_lo = float(stats.t.sf(max(t_abs), df))  # smallest one-tailed tail
        sf_hi = float(stats.t.sf(min(t_abs), df))  # largest one-tailed tail
        p_lo, p_hi = 2 * sf_lo, 2 * sf_hi          # two-tailed interval
        result["calculated_p_interval"] = [p_lo, p_hi]

        resolved = resolve_p_relation(p_relation, reported_p, p_is_threshold)
        if "error" in resolved:
            return {**result, "severity": INDETERMINATE, "error": resolved["error"]}
        adj = check_p_adjustment(p_adjustment)
        if "error" in adj:
            return {**result, "severity": INDETERMINATE, "error": adj["error"]}
        rel = resolved["relation"]
        result["p_relation"] = rel
        result["p_relation_basis"] = resolved["basis"]
        # The over-claim test below keeps its historical reading: a declared
        # bound is held to its exact endpoint, anything else gets the printed
        # precision's slack in the over-claiming direction only. An exact p is
        # then ALSO tested from above (the under-claim test after it).
        _thr = True if bound_is_stated(resolved) else None

        def _p_in(a: float, b: float) -> bool:
            # The interval is consistent with the reported p if ANY p it admits
            # is. Checked at the endpoints because `_p_matches` is monotone in
            # the calculated value on each side of the reported one.
            return bool(
                _p_matches(a, reported_p, decimals_p, _thr)
                or _p_matches(b, reported_p, decimals_p, _thr)
                or (a <= reported_p <= b)
            )

        # TAIL CONVENTION. Two-sided is the default reading, but a directional
        # hypothesis reported one-sided prints exactly HALF the p, and B, SE and
        # df cannot tell us which tail the authors used. Reporting the one-tailed
        # p of a legitimate one-sided test is not misconduct, so accept a reported
        # p consistent with EITHER the two-tailed interval or the one-tailed one
        # (its lower half). A genuine over-claim -- a p below even the one-tailed
        # interval -- still fails both and fires. Same try-both-conventions rule
        # as the t sign above, and it only ever loosens in the over-claim
        # direction `_p_matches` already governs.
        # EVERY TAIL READING IS HELD TO THE RELATION. Under an EXACT p a reading
        # matches only if the printed value sits inside its interval from BOTH
        # sides: a printed .05 against a two-tailed [.057, .058] is not rescued
        # by a one-tailed [.029, .029], which it under-claims. (Before 1.86.0
        # `p_is_threshold=False` held both readings two-sided; the directional
        # test alone would have let the one-tailed reading rescue it.)
        two_dir, one_dir = _p_in(p_lo, p_hi), _p_in(sf_lo, sf_hi)
        if rel == ">":
            two_dir = one_dir = True
        two_tailed_ok = two_dir and not p_under_claimed(p_hi, reported_p, decimals_p, rel)
        one_tailed_ok = one_dir and not p_under_claimed(sf_hi, reported_p, decimals_p, rel)
        result["p_matches"] = bool(two_tailed_ok or one_tailed_ok)
        # UNDER-CLAIM: an exact printed p above every two-tailed p the rounded
        # B and SE allow (and so above every one-tailed one). A bound is
        # satisfied by any smaller p.
        if (not result["p_matches"] and two_dir
                and p_under_claimed(p_hi, reported_p, decimals_p, rel)):
            uc = explain_under_claim(under_claim_finding(
                p_hi, reported_p, decimals_p, resolved, f"B/SE = {b}/{se} with df = {df}"),
                p_adjustment=adj["adjustment"])
            uc.pop("severity")
            uc.pop("consistent")
            result["p_explanation"] = uc.pop("explanation")
            result.update(uc)
            result["p_matches"] = bool(uc.get("under_claim_explained"))
            two_tailed_ok = one_tailed_ok = False
        elif (result["p_matches"] and rel is None
              and not (two_dir and not p_under_claimed(p_hi, reported_p, decimals_p, "="))
              and not (one_dir and not p_under_claimed(sf_hi, reported_p, decimals_p, "="))):
            result["under_claim_if_exact"] = True
            result["p_explanation"] = under_claim_note(p_hi, reported_p)
        if one_tailed_ok and not two_tailed_ok:
            # Reconciles only as a one-sided test. Surface it: an unflagged
            # one-sided p on a hypothesis the paper framed as two-sided is worth
            # a human's eye, even though it is not itself an accusation.
            result["p_reconciles_one_sided_only"] = True
        matches.append(result["p_matches"])

        # WHAT WAS FORGIVEN, AND WHICH WAY IT LEANED. The allowances above are
        # what keep this check from convicting honest tables, and they stay. But
        # applying them silently destroyed the one property that separates
        # rounding from anything else: a row rescued by the rounding interval
        # came back indistinguishable from a row that reconciled exactly.
        #
        # Direction only means something across a SET -- fifty rows within
        # tolerance is noise, fifty rows within tolerance of which forty-seven
        # lean the same way is not, and no single row can show that. The residual
        # is signed so the set can be read: NEGATIVE means the paper reported a
        # SMALLER p than its own B and SE support, which is the over-claiming
        # direction.
        #
        # This records; it never accuses. `severity` above is already decided and
        # is not touched here.
        from .. import grace as _grace
        _strict = bool(
            decimals_p is not None
            and _rounding.matches_at_precision(calculated_p, reported_p, decimals_p))
        _kind = None
        if result["p_matches"] and not _strict:
            _kind = ("threshold_bound" if rel == "<"
                     else "one_tailed" if (one_tailed_ok and not two_tailed_ok)
                     else "printed_precision")
        result["grace"] = _grace.record(
            strict_ok=_strict, lenient_ok=bool(result["p_matches"]), grace=_kind,
            reported=reported_p, nearest_consistent=calculated_p,
            note=("reported p against the p implied by B/SE; a negative residual "
                  "is the over-claiming direction"))

    if not matches:
        result["severity"] = INDETERMINATE
    elif all(matches):
        # An under-claim the paper explains is not a match either: undetermined.
        result["severity"] = (INDETERMINATE if result.get("under_claim_explained")
                              else CONSISTENT)
    else:
        result["severity"] = SUSPICIOUS
    if result.get("p_explanation"):
        result["explanation"] = result["p_explanation"]

    result["methodology"] = (
        f"Regression check: t = B/SE = {b}/{se} = {calculated_t:.4f}"
    )

    return result


def check_regression_batch(rows: list[dict]) -> dict:
    """Verify every regression coefficient in one call.

    MEASURED: on a real review, 79 of 111 stage-1 tool calls were
    `check_regression` invoked once per coefficient -- a three-number
    consistency check (t = B/SE) repeated down a regression table. Each call is
    a turn, and turns are essentially the whole cost of a review.

    This is the third instance of the same pattern. `check_table` absorbed the
    per-cell `check_estimate_ci` storm and `check_summation_batch` the per-sum
    one; regression coefficients are neither table cells nor sums, so they
    needed their own batch.

    Each row is `{b, se, reported_t?, reported_p?, df?, decimals_b?,
    decimals_se?, decimals_t?, decimals_p?, p_is_threshold?, p_relation?,
    label?}`. `label`
    is carried through untouched so a finding can name the coefficient rather
    than an index.

    GIVE THE `decimals_*`. Without them every row falls back to the widest
    plausible interval, which is safe but blind: a coefficient printed `0.340`
    is checked as though it read `0.34`. This is the dominant call path -- 79
    of 111 stage-1 calls on one real review -- so a precision the rows never
    carry is a precision the whole review never has.

    The aggregate severity is the WORST row, and a batch in which nothing could
    be evaluated returns `indeterminate` rather than `consistent` -- the
    false-clear that had to be fixed in the DEBIT batch, where zero
    inconsistent rows out of zero evaluated rows read as a clean bill of health.

    Note that a row with neither `reported_t` nor `df` is genuinely
    indeterminate: without df a t cannot be converted to a p, so there is
    nothing to compare the coefficient against. That is the commonest reason a
    row here is not evaluated, and it is a property of what the paper printed.

    A VERDICT THAT ONLY HOLDS AT A DF THE PAPER NEVER PRINTED IS NOT A
    VERDICT. See `_apply_df_sensitivity`: when the caller supplies a df
    without saying the paper reported it, the batch is re-run across a
    probe range, and a verdict that changes across it is reported as
    `indeterminate` rather than as a finding or as a clean result.
    """
    return _apply_df_sensitivity(rows, _batch_core(rows))


def _batch_core(rows: list[dict]) -> dict:
    """The batch itself, with no df-sensitivity pass.

    Separated so `_apply_df_sensitivity` can re-run it at each probe df
    without recursing back into its own guard."""
    from .severity import CONSISTENT, INDETERMINATE

    if not rows:
        return {
            "severity": INDETERMINATE, "applicable": False,
            "n_rows": 0, "n_evaluated": 0, "n_indeterminate": 0,
            "n_inconsistent": 0, "results": [],
            "explanation": "No rows supplied; nothing was evaluated.",
        }

    order = {"impossible": 0, "highly_suspicious": 1, "suspicious": 2,
             "indeterminate": 3, "consistent": 4}
    results, n_indet, n_bad = [], 0, 0
    worst = CONSISTENT

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            results.append({"row": i, "severity": INDETERMINATE,
                            "error": "row is not an object"})
            n_indet += 1
            continue
        try:
            out = check_regression(
                b=float(row["b"]), se=float(row["se"]),
                reported_t=row.get("reported_t"),
                reported_p=row.get("reported_p"),
                df=row.get("df"),
                # Per-row printed precision. Without it every row falls back to
                # the widest plausible interval, and a table printed to three
                # decimals is checked as though it were printed to zero.
                decimals_b=row.get("decimals_b"),
                decimals_se=row.get("decimals_se"),
                decimals_t=row.get("decimals_t"),
                decimals_p=row.get("decimals_p"),
                p_is_threshold=row.get("p_is_threshold"),
                p_relation=row.get("p_relation"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            out = {"severity": INDETERMINATE, "error": f"unusable row: {exc}"}
        out["row"] = i
        if row.get("label"):
            out["label"] = row["label"]
        sev = out.get("severity", INDETERMINATE)
        if sev == INDETERMINATE:
            n_indet += 1
        elif sev != CONSISTENT:
            n_bad += 1
        if order.get(sev, 9) < order.get(worst, 9):
            worst = sev
        results.append(out)

    n_evaluated = len(rows) - n_indet
    if n_evaluated == 0:
        severity = INDETERMINATE
        explanation = (
            f"None of the {len(rows)} coefficients could be evaluated -- most "
            "commonly because no df was given, without which t cannot be "
            "converted to p. This is a refusal, not a finding: nothing was "
            "checked, so nothing is confirmed.")
    else:
        severity = worst
        explanation = (
            f"{n_bad} of {n_evaluated} evaluated coefficients disagree with "
            f"their reported statistic."
            + (f" {n_indet} row(s) could not be evaluated." if n_indet else ""))

    return {
        "severity": severity,
        "n_rows": len(rows),
        "n_evaluated": n_evaluated,
        "n_indeterminate": n_indet,
        "n_inconsistent": n_bad,
        "results": results,
        "explanation": explanation,
        "methodology": (
            "Batched regression consistency (t = B/SE). Each row is checked "
            "independently by check_regression; the aggregate severity is the "
            "worst row, and a batch in which nothing could be evaluated reports "
            "`indeterminate` rather than `consistent`."
        ),
    }


#: Degrees of freedom probed when the caller supplied a df the paper did not
#: print. Chosen to bracket where the t distribution actually moves: p changes
#: sharply between df 10 and 30 and is nearly flat above ~100, so these four
#: separate "the answer depends on df" from "it does not" without pretending to
#: know the study's real residual df.
DF_PROBES = (10, 30, 100, 100_000)

#: What a row must say for its df to count as evidence rather than a guess.
#: ABSENT MEANS ASSUMED, deliberately. A df whose provenance nobody stated
#: cannot license a determination, and the fail-safe direction in this toolkit
#: is always toward the weaker reading.
DF_REPORTED = "reported"


def _apply_df_sensitivity(rows: list[dict], out: dict) -> dict:
    """Refuse a verdict that only holds at a df the paper never printed.

    MEASURED ON A REAL RUN, and it is the sharpest instance of model-supplied
    assumption risk in the archive. Romano et al., Table 2, the SAME 68
    coefficients in two runs at byte-identical prompt and schema:

        df supplied      verdict          inconsistent rows
        (none)           indeterminate    0 of 0 evaluated
        10               SUSPICIOUS       5
        30 .. 100000     consistent       0

    One run declined to supply a df and reported "the single largest
    verification gap in the paper". The other supplied `df=100000` -- a number
    appearing nowhere in the paper -- got 68 of 68 consistent, and filed it
    under `not_checked`. The accusation and the all-clear were both
    manufactured by a choice the model made, and BOTH directions are failures
    this toolkit exists to prevent.

    So when the df is not `reported`, the batch is re-run across `DF_PROBES`. If
    the verdict is identical at every probe it is a property of the numbers and
    stands. If it changes, the answer is `indeterminate`: not "the paper is
    fine", not "these coefficients disagree", but "this cannot be settled
    without a df the paper did not print". Row-level results are left intact so
    a reader can see what each convention gives.

    A `reported` df is evidence and is never second-guessed here.
    """
    from .severity import INDETERMINATE

    supplied = [r for r in rows
                if isinstance(r, dict) and r.get("df") is not None]
    if not supplied or out.get("n_evaluated", 0) == 0:
        return out
    assumed = [r for r in supplied
               if str(r.get("df_source") or "") != DF_REPORTED]
    if not assumed:
        out["df_provenance"] = "reported"
        return out

    seen: dict[int, str] = {}
    for probe in DF_PROBES:
        probed = []
        for r in rows:
            if not isinstance(r, dict):
                probed.append(r)
                continue
            r2 = dict(r)
            if (r2.get("df") is not None
                    and str(r2.get("df_source") or "") != DF_REPORTED):
                r2["df"] = probe
            probed.append(r2)
        seen[probe] = _batch_core(probed).get("severity", INDETERMINATE)

    out["df_provenance"] = "assumed"
    out["df_sensitivity"] = {
        "probes": {str(k): v for k, v in seen.items()},
        "stable": len(set(seen.values())) == 1,
        "n_rows_with_assumed_df": len(assumed),
    }
    if len(set(seen.values())) == 1:
        out["explanation"] += (
            f" The df was assumed rather than read from the paper, but the "
            f"verdict is the same at df {DF_PROBES[0]} through {DF_PROBES[-1]}, "
            "so it does not rest on that assumption.")
        return out

    original = out["severity"]
    spread = ", ".join(f"df {k} -> {v}" for k, v in seen.items())
    out["severity"] = INDETERMINATE
    out["severity_source"] = {
        "original": original,
        "final": INDETERMINATE,
        "clamped_by": "assumed_df_changes_the_verdict",
        "why": (
            "The degrees of freedom used here were supplied by this review, not "
            f"printed by the paper, and the verdict changes across plausible "
            f"values ({spread}). Neither the finding nor the clean result can be "
            "attributed to the authors, so it is reported as unsettled."),
    }
    out["explanation"] = (
        f"Not settled: the verdict depends on a degrees-of-freedom value the "
        f"paper did not print ({spread}). {out['n_inconsistent']} of "
        f"{out['n_evaluated']} rows disagree at the df supplied, but that df is "
        "an assumption of this review, not a number the authors reported. Ask "
        "the authors for the df, or read it from a reported test statistic.")
    return out
