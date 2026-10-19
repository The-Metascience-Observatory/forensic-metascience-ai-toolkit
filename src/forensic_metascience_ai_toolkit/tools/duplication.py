"""
Duplication / copy-paste detector.

Catches summary-statistics that recur where they should not:
  - cross_source_pair : identical (mean, SD) pairs across two+ *independent*
        tables/studies — copy-paste or recycled/fabricated data. (The archetypal
        signature is several affect means matching to two decimals on BOTH the
        mean and the SD across two tables a paper presents as separate samples.)
  - within_table_row / within_table_col : an identical multi-cell line repeated
        inside one table (fill-down copy-paste).
  - near_match : identical after coarser rounding or a digit transposition.

Reference: Heathers (2025) §"Pursuing internal consistency" — two or more
records of the same underlying facts should be identical; identical records of
*different* facts (independent samples) should not.

Severity is keyed on the COUNT of identical pairs (k) and capped at
`highly_suspicious` (duplication is improbable, not mathematically
impossible). A LONE cross-source match is additionally gated on the
span-aware coincidence probability: one collision the tool's own chance
model calls likely is not evidence (see the k=1 gate in
`detect_duplication`). Within-table repeats do not count cells that are
identical BY DESIGN (arm sizes, denominators, zero-event lines) and apply
the same round-value discount the cross-source branch has always had (see
`_within_line_severity`). Whether two blocks truly describe independent
samples is deferred to the editorial stage — the tool reports candidates
and caveats.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import combinations
from typing import Optional

from scipy import stats

from .severity import (
    CONSISTENT,
    HIGHLY_SUSPICIOUS,
    INDETERMINATE,
    SUSPICIOUS,
)

_TIERS = [HIGHLY_SUSPICIOUS, SUSPICIOUS, INDETERMINATE, CONSISTENT]


def _drop_tier(sev: str, steps: int = 1) -> str:
    """Move a severity toward `consistent` by `steps` (never below consistent)."""
    if sev not in _TIERS:
        return sev
    i = min(len(_TIERS) - 1, _TIERS.index(sev) + steps)
    return _TIERS[i]


def _is_round(value: float) -> bool:
    """Values that collide by chance far more often than a uniform grid implies:
    integers, halves, and multiples of 0.05, plus the {0, 0.5, 1} proportions."""
    if value is None:
        return False
    v = abs(value)
    if abs(v - round(v)) < 1e-9:  # integer
        return True
    if abs((v * 20) - round(v * 20)) < 1e-9:  # multiple of 0.05
        return True
    return False


def _is_int(value: float) -> bool:
    """True when a (possibly rounded) cell value is a whole number."""
    return abs(value - round(value)) < 1e-9


#: How much larger the SAMPLE SD (divide by n-1) can be than the population SD
#: (divide by n) for a binary variable: sqrt(n/(n-1)), which is 1.0206 at n=25
#: and falls monotonically. Set to cover every n >= 25, because this function is
#: not given an `n` and a paper reporting proportions on fewer than 25 people is
#: rare enough to argue individually.
_SAMPLE_SD_ALLOWANCE = 1.021


def _is_bernoulli_pair(mean: Optional[float], sd: Optional[float],
                       dm: int, ds: int) -> bool:
    """Is this (mean, SD) a BINARY variable's proportion beside its own SD?

    A binary variable reported as `proportion (SD)` has sd = sqrt(m(1-m)): the
    SD is a DETERMINISTIC FUNCTION of the mean and carries no information of its
    own. The pair holds ONE free parameter, not two, so every calculation in
    this module that prices a pair as two independent draws is wrong for it by
    orders of magnitude.

    MEASURED, and the reason this exists: on
    `10.1001--jamanetworkopen.2023.51752` -- an honest JAMA Network Open cohort
    paper, and one on our own demo shortlist -- `sweep_duplication` returned
    `highly_suspicious` with a coincidence probability of 4.8e-09 over 13
    "identical (mean, SD) pairs". TWELVE of the thirteen are fully explained as
    a proportion beside its own SD once the mean's printed rounding is allowed
    for, and the thirteenth sits exactly on the boundary:

        mean 0.26 -> 0.4386 (printed 0.44)    mean 0.10 -> 0.3000 (printed 0.30)
        mean 0.06 -> 0.2375 (printed 0.24)    mean 0.14 -> 0.3470 (printed 0.35)

    Two tables of one cohort reporting the same proportion of male children is
    expected, not suspicious, and the SD agreeing is arithmetic, not evidence.

    THE BAND COMES FROM THE MEAN'S OWN ROUNDING, not from the printed mean
    alone. `0.07 (0.25)` looks wrong if you compute sqrt(.07 x .93) = 0.2551 and
    demand it round to 0.25 -- but the true proportion is only known to lie in
    [0.065, 0.075], which admits an SD anywhere in [0.246, 0.264], and 0.25 is
    inside it. Ignoring the mean's rounding rejects real Bernoulli pairs and
    leaves the false accusation standing.

    THE SAMPLE-SD CONVENTION IS ALLOWED FOR, and it is not optional. Papers
    divide by n-1 as often as by n, which inflates the SD by sqrt(n/(n-1)) --
    2.1% at n=25, 0.5% at n=100, 0.08% at n=618. Without that allowance the
    band rejected `0.31 (0.47)` by 0.0005, one pair of four, and a single
    rejection kept the whole group accusatory. `_SAMPLE_SD_ALLOWANCE` covers
    every n >= 25; below that the correction is large enough that the pair
    should be argued rather than assumed either way.

    Erring toward calling a pair Bernoulli is the SAFE direction throughout --
    it withholds an accusation rather than making one.
    """
    if mean is None or sd is None:
        return False
    if not 0.0 <= mean <= 1.0:
        return False
    half_m = 0.5 * (10 ** -max(0, int(dm)))
    half_s = 0.5 * (10 ** -max(0, int(ds)))
    lo, hi = max(0.0, mean - half_m), min(1.0, mean + half_m)
    cands = [math.sqrt(p * (1 - p)) for p in (lo, hi)]
    return ((min(cands) - half_s)
            <= sd
            <= (max(cands) * _SAMPLE_SD_ALLOWANCE + half_s))


# ---- k=1 chance-gate constants ----
# The gate consults the multiplicity-corrected coincidence probability the
# tool itself reports (Poisson over ALL cross-source comparisons made).
_CHANCE_CONSISTENT = 0.5     # a lone match MORE LIKELY THAN NOT under chance
_CHANCE_INDETERMINATE = 0.10  # a lone match too likely by chance to accuse
# The span-based chance model is only meaningful when the observed spans cover
# at least this many rounding steps. With fewer, the spans are dominated by
# the duplicated values themselves (two single-cell blocks that match have
# ZERO span), p_pair saturates near 1, and the model would launder every lone
# match to `consistent`.
_SPAN_STEPS_MIN = 5


#: The two occurrences that CONSTITUTE a cross-source match -- one in each
#: block. Held out of the frequency estimate below; see why there.
_MATCH_OCCURRENCES = 2


def _empirical_marginal(pool: list, matched: list, decimals: int) -> float:
    """How common the matched value is in its column FOR OTHER REASONS, 0-1.

    Counted on the REPORTED grid (`round(v, decimals)`), which is the grid
    `_pair_key` matched on -- comparing raw floats against rounded matches
    would find nothing and silently return a floor of zero.

    LEAVE THE MATCH OUT. A duplication necessarily puts its own value in the
    pool twice, once per block, so a naive share is inflated by the very
    collision it is pricing -- and on a small pool that is the whole of it.
    The first draft of this function did exactly that and was caught by four
    existing pins, including the Gino four-pair affect regression: five means
    per block, each matched value appearing exactly twice, share 2/10, and a
    real duplication laundered to `consistent`. Holding out the two
    occurrences leaves that case at zero -- the span model, untouched -- and
    still scores 14/38 on `10.1002--alz.13600`, where the SD 0.01 recurs for
    reasons that have nothing to do with the match.

    Returns the largest leave-out share among the matched values: the most
    conservative reading of what the collision was worth. 0.0 when there is
    nothing left to count, which is the span model unchanged.
    """
    vals = [v for v in pool if v is not None]
    keys = [m for m in matched if m is not None]
    denom = len(vals) - _MATCH_OCCURRENCES
    if denom <= 0 or not keys:
        return 0.0
    counts = Counter(round(float(v), decimals) for v in vals)
    best = max(counts.get(round(float(m), decimals), 0) for m in keys)
    return max(0.0, best - _MATCH_OCCURRENCES) / denom


def _drop_to(current: str, target: str) -> str:
    """`target`, but never LESS severe -> more severe. The gate only clears.

    `_TIERS` runs most-severe first, so a larger index is milder. Written as
    a helper rather than an assignment because the gate now runs over groups
    at every k, and one accidental upgrade there would be an accusation this
    tool manufactured out of its own chance model.
    """
    try:
        return target if _TIERS.index(target) > _TIERS.index(current) else current
    except ValueError:
        return current


def _severity_for_k(k: int, high_precision: bool) -> str:
    if k >= 3:
        return HIGHLY_SUSPICIOUS
    if k == 2:
        return SUSPICIOUS
    if k == 1:
        return SUSPICIOUS if high_precision else INDETERMINATE
    return CONSISTENT


def _pair_key(value: float, sd: Optional[float], dm: int, ds: int) -> tuple:
    v = round(value, dm)
    s = None if sd is None else round(sd, ds)
    return (v, s)


def detect_duplication(
    blocks: list[dict],
    decimals_mean: int = 2,
    decimals_sd: int = 2,
    near_match: bool = True,
    round_value_penalty: float = 8.0,
) -> dict:
    """Detect duplicated summary statistics within and across blocks.

    Args:
        blocks: list of source blocks, each
            {"label": str,
             "sample_id": str | None,   # blocks sharing a sample_id describe the
                                        # SAME participants; matches are expected
             "independent": bool,       # default True
             "cells": [{"label": str, "value": float, "sd": float | None,
                        "decimals_mean": int?, "decimals_sd": int?}]}
        decimals_mean / decimals_sd: default reported precision.
        near_match: also report identical-after-rounding / transposed matches.
        round_value_penalty: multiplier on the coincidence probability for
            round values (they collide more often); also drops their tier.

    Returns:
        dict with severity, duplicate_groups, max_identical_pairs,
        chance_probability, assumptions, caveats, methodology.
    """
    if not blocks or len(blocks) < 1:
        return {"error": "no blocks provided", "severity": INDETERMINATE}

    # Normalize blocks and collect all pair-cells (value + sd both present).
    norm = []
    all_means: list[float] = []
    all_sds: list[float] = []
    for i, blk in enumerate(blocks):
        label = blk.get("label", f"block{i}")
        cells = []
        for c in blk.get("cells", []):
            v = c.get("value")
            if v is None:
                continue
            sd = c.get("sd")
            # `dict.get(k, default)` returns the DEFAULT only when the key is
            # ABSENT. A cell carrying `decimals_sd: None` -- which is what a
            # typed cell looks like when its second number has no determinable
            # printed precision -- came back None and crashed the whole call on
            # `int(None)`, taking a paid run with it. Fall back on the VALUE
            # being None, not merely on the key being missing.
            dm_raw = c.get("decimals_mean")
            ds_raw = c.get("decimals_sd")
            dm = int(decimals_mean if dm_raw is None else dm_raw)
            ds = int(decimals_sd if ds_raw is None else ds_raw)
            cells.append({
                "label": c.get("label", "")
                or f"{c.get('row_label', '')}/{c.get('col_label', '')}".strip("/"),
                "row_label": c.get("row_label"),
                "col_label": c.get("col_label"),
                "value": v, "sd": sd, "dm": dm, "ds": ds,
            })
            all_means.append(v)
            if sd is not None:
                all_sds.append(sd)
        norm.append({
            "label": label,
            "sample_id": blk.get("sample_id"),
            "independent": blk.get("independent", True),
            "cells": cells,
        })

    # Data-driven plausible spans (avoid inventing scale bounds).
    span_mean = max(1e-6, (max(all_means) - min(all_means)) if len(all_means) > 1 else 1.0)
    span_sd = max(1e-6, (max(all_sds) - min(all_sds)) if len(all_sds) > 1 else 1.0)

    duplicate_groups: list[dict] = []

    # ---- Cross-source (mean, SD) pair matches ----
    n_comparisons = 0
    max_k_independent = 0
    bernoulli_at_max = False
    values_at_max: list[tuple] = []
    for a, b in combinations(range(len(norm)), 2):
        ba, bb = norm[a], norm[b]
        pairs_a = {}
        for c in ba["cells"]:
            if c["sd"] is None:
                continue
            pairs_a.setdefault(_pair_key(c["value"], c["sd"], c["dm"], c["ds"]), []).append(c)
        pairs_b = {}
        for c in bb["cells"]:
            if c["sd"] is None:
                continue
            pairs_b.setdefault(_pair_key(c["value"], c["sd"], c["dm"], c["ds"]), []).append(c)

        n_comparisons += len(pairs_a) * len(pairs_b)
        shared = set(pairs_a) & set(pairs_b)
        same_sample = (
            ba["sample_id"] is not None
            and ba["sample_id"] == bb["sample_id"]
        ) or not (ba["independent"] and bb["independent"])

        k = len(shared)
        if k == 0:
            continue

        matched_values = sorted(shared)
        all_round = all(_is_round(v) and (s is None or _is_round(s)) for v, s in matched_values)
        # A BERNOULLI PAIR IS ONE NUMBER WEARING TWO. Judged on the group rather
        # than the pair: one binary row inside a group of continuous ones does
        # not make the group uninformative, but a group that is ALL proportions
        # matched on their means alone, and the SD agreement it is being priced
        # on is arithmetic. Uses the DECLARED precision of the matched pair,
        # which is what `_pair_key` rounded to.
        all_bernoulli = bool(matched_values) and all(
            _is_bernoulli_pair(v, s, decimals_mean, decimals_sd)
            for v, s in matched_values
        )
        high_precision = any(
            (s is not None and s != 0) for _, s in matched_values
        )
        # The SD of a Bernoulli pair is not "precision", it is a restatement of
        # the mean. Treating it as precision is what let k=1 reach `suspicious`.
        grp_sev = _severity_for_k(k, high_precision and not all_bernoulli)
        if same_sample:
            grp_sev = _drop_tier(grp_sev, 2)
        elif all_bernoulli:
            # TWO tiers, one more than the round-value discount. A round value
            # merely collides more often; a Bernoulli SD carries no information
            # AT ALL, so the whole match reduces to "these tables report the
            # same proportion" -- which for subsets of one cohort is expected.
            grp_sev = _drop_tier(grp_sev, 2)
        elif all_round:
            grp_sev = _drop_tier(grp_sev, 1)

        duplicate_groups.append({
            "kind": "cross_source_pair",
            "block_a": ba["label"], "block_b": bb["label"],
            "same_sample_caveat": same_sample,
            "is_round_value": all_round,
            "is_bernoulli_pair": all_bernoulli,
            "k_pairs": k,
            "values": [[v, s] for v, s in matched_values],
            "occurrences": [
                {"block": ba["label"],
                 "cells": [c["label"] for c in pairs_a[key]]}
                for key in matched_values
            ] + [
                {"block": bb["label"],
                 "cells": [c["label"] for c in pairs_b[key]]}
                for key in matched_values
            ],
            "severity": grp_sev,
        })
        if not same_sample:
            if k > max_k_independent:
                max_k_independent = k
                # Carried to the chance model below: whether the STRONGEST
                # group -- the one the reported probability describes -- was
                # Bernoulli. Tracked here rather than recomputed, so the number
                # published always describes the group it was computed from.
                bernoulli_at_max = all_bernoulli
                values_at_max = list(matched_values)

    # ---- Within-table repeated rows / columns ----
    for blk in norm:
        _detect_within_table(blk, duplicate_groups)

    # ---- Near matches (weaker) ----
    if near_match:
        _detect_near_matches(norm, duplicate_groups)

    # ---- Chance probability for the strongest independent cross-source group ----
    p_mean = min(1.0, (10 ** (-decimals_mean)) / span_mean)
    p_sd = min(1.0, (10 ** (-decimals_sd)) / span_sd)
    # ONE FREE PARAMETER, NOT TWO, WHEN THE PAIR IS BERNOULLI. `p_mean * p_sd`
    # is the probability of two INDEPENDENT values colliding; for a proportion
    # beside its own sqrt(m(1-m)) the SD collides with certainty once the mean
    # does, so the joint probability is just `p_mean`. Pricing it as a product
    # is what turned an ordinary cohort table into `highly_suspicious` at
    # 4.8e-09 -- the published number was smaller than the truth by a factor of
    # 1/p_sd, which on that paper was around four orders of magnitude.
    # THE MARGINAL IS FLOORED BY HOW OFTEN THE MATCHED VALUE ACTUALLY OCCURS.
    #
    # `10^-d / span` prices every value in the range as equally likely. A
    # column with low entropy breaks that badly, and it breaks it in the
    # accusing direction: a value that is the MODE of its own column gets
    # priced as if it were rare.
    #
    # MEASURED 2026-08-22, `10.1002--alz.13600`. Table 3's beta-plus-minus-SE
    # column is 20 cells and TEN of them have SE exactly 0.01; Supplementary
    # Table 5 is the same models re-fitted by sex and looks the same. Six
    # (beta, SE) pairs collided -- (-0.01,0.01) (0.00,0.01) (0.01,0.01)
    # (0.02,0.01) (0.03,0.01) (0.05,0.01) -- and the span model called that
    # `highly_suspicious` at a coincidence probability of 2e-39. There is no
    # coincidence: half the SEs in both tables ARE 0.01, so a tie on the beta
    # forces a tie on the pair.
    #
    # This is the Bernoulli defect one level up. `_is_bernoulli_pair` fixes
    # the case where the SD is arithmetic in the mean; this fixes the general
    # case where either column is concentrated, without enumerating a third
    # special case.
    #
    # A FLOOR, DELIBERATELY, so the change is monotone: it can only RAISE
    # `chance_probability` and so only ever LOWER a severity. It cannot invent
    # an accusation, whatever the pool looks like.
    p_mean = max(p_mean, _empirical_marginal(
        all_means, [v for v, _ in values_at_max], decimals_mean))
    p_sd = max(p_sd, _empirical_marginal(
        all_sds, [s_ for _, s_ in values_at_max], decimals_sd))
    p_pair = p_mean if bernoulli_at_max else p_mean * p_sd
    lam = n_comparisons * p_pair
    if max_k_independent >= 1:
        chance_probability = float(stats.poisson.sf(max_k_independent - 1, lam))
    else:
        chance_probability = None

    # ---- chance gate ----
    # AN IDENTICAL PAIR IS ONLY EVIDENCE OF DUPLICATION IF A COINCIDENCE IS
    # UNLIKELY once every comparison actually made is accounted for. That
    # multiplicity-corrected probability is computed right above — but it used
    # to be reported and never consulted: k=1 with a nonzero SD went straight
    # to `suspicious` even when the same result said a chance match was 37%
    # likely. Mirrors grim_test's invented-bound cap and the DEBIT/GRIMMER
    # convention trials: while an innocent reading is live, the severity may
    # not be accusation-grade.
    #   P(>=k chance matches) > 0.5  -> consistent   (expected under innocence)
    #   P(>=k chance matches) > 0.10 -> indeterminate (too likely to accuse)
    #   P(>=k chance matches) <= 0.10 -> the ladder's severity stands
    #
    # EVERY k, NOT ONLY k=1. The old restriction rested on "at k >= 2 the
    # count itself carries the evidence", and that is true only while the
    # matched values are rare. On `10.1002--alz.13600` six matches at k=6 were
    # six restatements of one fact -- half the SEs in both tables are 0.01 --
    # and the count carried nothing. Now that the marginal is floored by the
    # value's actual frequency (see above), the same arithmetic answers the
    # same question at any k, and the special case earns nothing.
    #
    # STILL ONLY EVER DOWNWARD: `_drop_to` never raises a severity, so a real
    # duplication whose values are rare in the pool (tiny p) is untouched.
    # The gate runs only when both observed spans cover >= _SPAN_STEPS_MIN
    # rounding steps; see the constant.
    p_lone = float(stats.poisson.sf(0, lam))
    # Steps covered, with float noise absorbed (0.86 - 0.81 is 0.049999...,
    # which a raw >= would call four steps instead of five).
    spans_informative = (
        round(span_mean / 10 ** (-decimals_mean), 6) >= _SPAN_STEPS_MIN
        and round(span_sd / 10 ** (-decimals_sd), 6) >= _SPAN_STEPS_MIN
    )
    if spans_informative:
        for g in duplicate_groups:
            if (g["kind"] != "cross_source_pair"
                    or g["same_sample_caveat"]
                    or g["severity"] not in (SUSPICIOUS, HIGHLY_SUSPICIOUS)):
                continue
            p_k = float(stats.poisson.sf(max(g["k_pairs"], 1) - 1, lam))
            if p_k <= _CHANCE_INDETERMINATE:
                continue
            g["severity"] = _drop_to(
                g["severity"],
                CONSISTENT if p_k > _CHANCE_CONSISTENT else INDETERMINATE)
            g["chance_gated"] = True
            g["chance_probability"] = p_k

    # ---- Top-level severity = most severe among all groups ----
    top = CONSISTENT
    if duplicate_groups:
        top = min(
            (g["severity"] for g in duplicate_groups),
            key=lambda s: _TIERS.index(s) if s in _TIERS else 99,
        )

    caveats = [
        "Blocks are assumed independent unless they share a sample_id. The "
        "editorial stage must confirm the sources use different participants "
        "before treating a cross-source match as a data-integrity anomaly.",
    ]
    if any(g.get("is_round_value") for g in duplicate_groups):
        caveats.append("Some matched values are round (integers/halves) and "
                       "recur by chance; their severity was reduced.")
    if any(g.get("chance_gated") for g in duplicate_groups):
        caveats.append("A lone cross-source match was de-escalated: after "
                       "correcting for the number of comparisons, at least "
                       f"one coincidental match had probability ≈ {p_lone:.2f}.")

    if max_k_independent >= 1:
        explanation = (
            f"{max_k_independent} identical (mean, SD) pair(s) shared across "
            f"independent blocks (coincidence probability ≈ "
            f"{('%.2g' % chance_probability) if chance_probability is not None else 'n/a'}). "
            "Confirm the sources describe different participants before treating "
            "this as a data-integrity anomaly."
        )
    elif duplicate_groups:
        explanation = (
            f"{len(duplicate_groups)} duplicate pattern(s) found "
            "(within-table repeats, same-sample matches, or near-matches); "
            "no improbable cross-independent-source overlap."
        )
    else:
        explanation = "No duplicated summary statistics detected."

    return {
        "severity": top,
        "explanation": explanation,
        "n_blocks": len(norm),
        "n_cells_total": sum(len(b["cells"]) for b in norm),
        "n_comparisons": n_comparisons,
        "max_identical_pairs": max_k_independent,
        "chance_probability": chance_probability,
        "duplicate_groups": duplicate_groups,
        "assumptions": {
            "span_mean": round(span_mean, 4),
            "span_sd": round(span_sd, 4),
            "decimals": [decimals_mean, decimals_sd],
            "p_pair": p_pair,
            "note": "spans inferred from observed values; assumes independent "
                    "cells and mean⊥SD (slightly conservative).",
        },
        "caveats": caveats,
        "methodology": (
            f"Compared {n_comparisons} cross-source (mean, SD) pairs across "
            f"{len(norm)} blocks plus within-table rows/columns. Strongest "
            f"independent overlap: {max_k_independent} identical pair(s); "
            f"coincidence probability ≈ "
            f"{('%.2g' % chance_probability) if chance_probability is not None else 'n/a'} "
            f"after correcting for the number of comparisons."
        ),
    }


def _cell_grid(blk: dict) -> dict[tuple, tuple]:
    """Map (row_label, col_label) -> (value, sd) for within-table checks."""
    grid = {}
    for c in blk["cells"]:
        # cells from parse_table carry row_label/col_label; detector cells may
        # only carry `label`. Accept either.
        rl = c.get("row_label")
        cl = c.get("col_label")
        if rl is None or cl is None:
            continue
        grid[(rl, cl)] = (round(c["value"], c["dm"]),
                          None if c["sd"] is None else round(c["sd"], c["ds"]))
    return grid


def _within_line_severity(kind: str, sig: tuple) -> tuple[str, int, bool]:
    """Severity for one line (row or column) repeated inside a single table.

    Applies the de-escalations the cross-source branch has always had (the
    same-sample drop, the `all_round` drop) — this branch previously had
    none, so a stratified randomised Table 1 whose three arms legitimately
    share n=20/20/20, 10/10/10 males and a 1-dp baseline age scored
    `highly_suspicious`, the tier reserved for the k>=3 copy-paste signature.

      * COUNT cells — integer value with no SD (or SD exactly 0): arm sizes,
        denominators, zero-event lines. Blocked allocation and zero attrition
        make these identical BY DESIGN, so they never count toward severity.
      * The ladder runs on k_stat, the matched cells that actually carry a
        statistic: >=3 highly_suspicious, 2 suspicious, <=1 indeterminate.
      * Round-value drop, COLUMN matches at k_stat >= 2 only: columns of one
        table are arms/groups drawn from the same recruitment, where
        near-equality is expected under randomisation, and round values
        (integers, halves, 0.05-multiples — every 1-dp value qualifies)
        collide at reporting precision; drop one tier, exactly like the
        cross-source `all_round` drop. ROW matches — DIFFERENT variables
        sharing a whole line of means AND SDs — have no design reason to
        coincide and keep full severity: that is the fill-down signature
        this detector exists to catch.

    Returns (severity, k_stat, round_discount_applied).
    """
    cells = [val for _, val in sig]
    stat = [(v, s) for v, s in cells
            if not (_is_int(v) and (s is None or s == 0))]
    k_stat = len(stat)
    if k_stat >= 3:
        sev = HIGHLY_SUSPICIOUS
    elif k_stat == 2:
        sev = SUSPICIOUS
    else:
        sev = INDETERMINATE
    all_round = bool(stat) and all(
        _is_round(v) and (s is None or _is_round(s)) for v, s in stat
    )
    discounted = kind == "within_table_col" and all_round and k_stat >= 2
    if discounted:
        sev = _drop_tier(sev, 1)
    return sev, k_stat, discounted


def _detect_within_table(blk: dict, groups: list[dict]) -> None:
    """Flag identical multi-cell rows or columns repeated inside one block."""
    grid = _cell_grid(blk)
    if not grid:
        return
    rows: dict[str, dict] = {}
    cols: dict[str, dict] = {}
    for (rl, cl), val in grid.items():
        rows.setdefault(rl, {})[cl] = val
        cols.setdefault(cl, {})[rl] = val

    def _report(kind: str, groups_map: dict):
        seen: dict[tuple, list[str]] = {}
        for label, cells in groups_map.items():
            if len(cells) < 2:
                continue
            sig = tuple(sorted(cells.items()))
            seen.setdefault(sig, []).append(label)
        for sig, labels in seen.items():
            if len(labels) >= 2:
                n_cells = len(sig)
                sev, k_stat, discounted = _within_line_severity(kind, sig)
                grp = {
                    "kind": kind,
                    "block": blk["label"],
                    "labels": labels,
                    "n_identical_cells": n_cells,
                    "n_statistic_cells": k_stat,
                    "severity": sev,
                }
                if discounted:
                    grp["is_round_value"] = True
                groups.append(grp)

    _report("within_table_row", rows)
    _report("within_table_col", cols)


def _detect_near_matches(norm: list[dict], groups: list[dict]) -> None:
    """Report value pairs identical after a digit transposition (weak signal)."""
    def transpositions(value: float, dm: int) -> set[str]:
        s = f"{value:.{dm}f}".replace(".", "")
        out = set()
        for i in range(len(s) - 1):
            if s[i] != s[i + 1]:
                sw = list(s)
                sw[i], sw[i + 1] = sw[i + 1], sw[i]
                out.add("".join(sw))
        return out

    for a, b in combinations(range(len(norm)), 2):
        ba, bb = norm[a], norm[b]
        if (ba["sample_id"] is not None and ba["sample_id"] == bb["sample_id"]):
            continue
        b_digits = {}
        for c in bb["cells"]:
            b_digits.setdefault(f"{round(c['value'], c['dm']):.{c['dm']}f}".replace(".", ""), c)
        for c in ba["cells"]:
            digs = f"{round(c['value'], c['dm']):.{c['dm']}f}".replace(".", "")
            for t in transpositions(c["value"], c["dm"]):
                if t in b_digits and t != digs:
                    groups.append({
                        "kind": "near_match",
                        "block_a": ba["label"], "block_b": bb["label"],
                        "value_a": c["value"], "value_b": b_digits[t]["value"],
                        "relation": "digit_transposition",
                        "severity": INDETERMINATE,
                    })
                    break
