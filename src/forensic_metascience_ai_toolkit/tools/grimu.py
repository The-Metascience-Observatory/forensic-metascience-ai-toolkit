"""
GRIM-U: Granularity-Related Inconsistency of Mann-Whitney U.

Heathers & Grimes (2026), medicalevidenceproject.org/GRIMU.

The Mann-Whitney U (equivalently Wilcoxon rank-sum) statistic takes only
(half-)integer values in [0, n1*n2], so for given group sizes only a FINITE set
of p-values is achievable. A reported MWU p-value can therefore be checked
against that set:

  - below the U=0 floor  -> impossible (a reporting error)
  - between achievable granular values -> granularity inconsistency (often a
    software / continuity-correction / rounding artifact, so treated cautiously)
  - reproduced by some achievable U -> consistent.

Engine (matches the paper's tables byte-exact, and SPSS's default): the NORMAL
APPROXIMATION, not the exact permutation distribution.

    mU  = n1*n2 / 2
    sdU = sqrt(n1*n2*(n1+n2+1) / 12)
    z   = (|U - mU| - cc) / sdU          # cc = 0 or 0.5 (continuity correction)
    p   = 2 * Phi(-z)                     # two-sided

Achievable U runs over {0, 0.5, 1, 1.5, ..., n1*n2}; half-integers arise from
ties and/or the continuity correction. The exact permutation p-value is folded
in only to make the `impossible` verdict robust to software variability — never
to silently rescue a granularity miss.

ONLY apply GRIM-U to p-values a paper attributes to a Mann-Whitney U / Wilcoxon
rank-sum test with known group sizes. It is meaningless for t/F/chi-squared/
regression p-values.

TWO MORE PRECONDITIONS, both enforced here rather than left to the prompt (the
`grim_test`/`debit_test` rule: a tool pointed at data it cannot speak about
must REFUSE, not accuse):

  * `reported_z` -- a p printed beside a normal-approximation Z is a function
    of the ROUNDED Z, whose achievable set is a different, far finer lattice.
    If the supplied Z reproduces the p at its printed precision, this refuses.
  * `ties_possible` -- the tie-corrected variance
    ``n1*n2/12 * ((N+1) - sum(t^3 - t)/(N*(N-1)))`` is strictly smaller than
    the untied term whenever any value repeats, so every achievable p moves.
    Refuses the granularity branch; the below-floor branch still runs, because
    ties cannot push U below 0.

MEASURED 2026-08-22 on 10.1016--j.compedu.2013.12.004 (`Z = 1.219, p = .223`;
`Z = 1.259, p = .208`; n1=21, n2=22, an integer learning score): both scored as
granularity misses and both were published at severity 2 against an honest
paper. A third rank-sum p in the same paper landed on the lattice, which is
what Z-rounding luck looks like from the inside.
"""

from __future__ import annotations

import decimal
from typing import Optional, Union

from scipy import stats

from .rivets import _half_width
from .severity import (
    CONSISTENT,
    IMPOSSIBLE,
    INDETERMINATE,
    SEVERITY_LEVELS,
    SUSPICIOUS,
)

_TOL = 1e-9

#: GRIM-U is defined only for Mann-Whitney U / Wilcoxon rank-sum p-values.
#: Anything else is a misapplication: scoring a t/F/χ² p against the U
#: lattice manufactures an `impossible` from the wrong test. Default
#: `mann_whitney` keeps existing callers working (they already chose this
#: tool); an explicit other type refuses.
_RANK_SUM_ALIASES = {
    "mann_whitney": "mann_whitney",
    "mann-whitney": "mann_whitney",
    "mannwhitney": "mann_whitney",
    "mwu": "mann_whitney",
    "u_test": "mann_whitney",
    "utest": "mann_whitney",
    "wilcoxon": "wilcoxon",
    "wilcoxon_rank_sum": "wilcoxon",
    "wilcoxon-rank-sum": "wilcoxon",
    "rank_sum": "wilcoxon",
    "rank-sum": "wilcoxon",
}


def canonical_test_type(test_type: str | None) -> str:
    """Normalise a test-type string. Unrecognised → `unknown` (refused)."""
    if test_type is None:
        return "unknown"
    key = str(test_type).strip().lower().replace(" ", "_")
    return _RANK_SUM_ALIASES.get(key, "unknown")


def _refuse_wrong_test(test_type: str) -> dict:
    canonical = canonical_test_type(test_type)
    return {
        "severity": INDETERMINATE,
        "applicable": False,
        "consistent": None,
        "test_type": test_type,
        "canonical_test_type": canonical,
        "error": (
            f"GRIM-U does not apply to test_type={test_type!r}; it is defined "
            "only for Mann-Whitney U / Wilcoxon rank-sum p-values. Pass "
            "mann_whitney or wilcoxon only."
        ),
        "explanation": (
            f"GRIM-U scores a p against the finite lattice of the U statistic. "
            f"For test_type={test_type!r} that lattice is the wrong object, so "
            "no granularity claim can be made. Not evaluated."
        ),
        "methodology": "GRIM-U applicability guard.",
    }


#: `p_source` spellings that mean "this p came out of a normal-approximation
#: Z, not out of U".
_Z_SOURCES = {"normal_z", "z", "normal_approximation_z", "normal_approx",
              "asymptotic", "asymptotic_z"}


def _z_reproduces_p(z, reported_p, decimals, one_sided: bool) -> bool:
    """Does 2*Phi(-|z|) (or Phi(-|z|) one-sided) render as the reported p at
    its printed precision?

    This is the checkable half of the innocent explanation, so it is CHECKED
    rather than left to the model to remember. If the printed Z accounts for
    the printed p, GRIM-U has nothing left to say about that p: the paper is
    reporting the Z's rounding, not U's granularity.

    Returns False on anything unparseable -- a guard that cannot evaluate its
    own precondition must not fire.
    """
    try:
        zf = abs(float(z))
    except (TypeError, ValueError):
        return False
    p_val, is_threshold, inferred = _parse_reported_p(reported_p)
    if p_val is None or is_threshold:
        return False
    dec = decimals if decimals is not None else inferred
    if dec is None:
        return False
    from_z = stats.norm.sf(zf) if one_sided else 2 * stats.norm.sf(zf)
    return abs(round(from_z, dec) - round(p_val, dec)) < _TOL


def _refuse_p_from_z(reported_p, reported_z, n1, n2, *, matches: bool) -> dict:
    """The p was rendered from a printed normal-approximation Z, so its
    granularity is Z's and not U's.

    MEASURED 2026-08-22 on 10.1016--j.compedu.2013.12.004, which prints
    `Z = 1.219, p = .223` and `Z = 1.259, p = .208`. GRIM-U scored both as
    granularity misses at severity 2 and both were published as findings, while
    the finding's OWN notes recorded that statcheck reproduces each p exactly
    from the printed Z. The third Mann-Whitney in the same paper happened to
    land on the lattice, which makes the difference Z-rounding luck rather than
    signal.

    Two independent reasons the U lattice does not bind here:

      * The p is a deterministic function of a Z printed to 3 dp. Its
        achievable set is the image of that rounding grid under 2*Phi(-|z|) --
        a different lattice from the one GRIM-U enumerates, and a much finer
        one.
      * SPSS reports Mann-Whitney with a TIE CORRECTION: the variance term is
        reduced by the tie sum, so sdU is smaller than sqrt(n1*n2*(n1+n2+1)/12)
        and every achievable p moves. On a small-integer outcome -- which is
        what a rank test is usually reaching for -- ties are near-certain.

    This is the `grim_test`/`debit_test` pattern: a tool pointed at data it
    cannot speak about must REFUSE, not accuse.
    """
    return {
        "severity": INDETERMINATE,
        "applicable": False,
        "consistent": None,
        "n1": n1,
        "n2": n2,
        "reported_p": reported_p,
        "reported_z": reported_z,
        "p_reproduced_by_reported_z": matches,
        "failure_mode": "p_derived_from_normal_z",
        "explanation": (
            f"The paper prints Z = {reported_z} beside p = {reported_p}, and "
            + ("that Z reproduces the p at its printed precision. "
               if matches else
               "the p was attributed to a normal-approximation Z. ")
            + "GRIM-U scores a p against the lattice of the U statistic, but "
            "this p is a function of the ROUNDED Z, whose achievable set is a "
            "different and finer lattice. A tie correction (SPSS's default for "
            "Mann-Whitney) also shrinks sdU, moving every achievable p off the "
            "untied lattice GRIM-U enumerates. Not evaluated."
        ),
        "methodology": (
            "GRIM-U applicability guard: p reported from a normal-approximation "
            "Z rather than from U."
        ),
    }


def _refuse_ties(reported_p, n1, n2) -> dict:
    """Ranks with ties do not live on the untied U lattice.

    The tie-corrected variance is
    ``sdU^2 = n1*n2/12 * ((N+1) - sum(t^3 - t)/(N*(N-1)))``, strictly smaller
    than the untied term whenever any value repeats. A granularity miss against
    the untied lattice is then a statement about our model, not the paper.

    The BELOW-FLOOR verdict is unaffected and is still reported: ties cannot
    push U below 0, so a p smaller than the U=0 p remains impossible.
    """
    return {
        "severity": INDETERMINATE,
        "applicable": False,
        "consistent": None,
        "n1": n1,
        "n2": n2,
        "reported_p": reported_p,
        "failure_mode": "ties_break_the_lattice",
        "explanation": (
            "The outcome was declared tie-prone (a small-integer or ordinal "
            "scale), so the rank sum carries a tie correction: sdU is smaller "
            "than the untied sqrt(n1*n2*(n1+n2+1)/12) and every achievable p "
            "moves. A miss against the untied lattice would be a fact about "
            "this model, not about the paper. Not evaluated. (A below-floor p "
            "would still be impossible -- ties cannot push U below 0 -- so "
            "re-run with ties_possible=False if you have a floor question.)"
        ),
        "methodology": "GRIM-U applicability guard: ties break the U lattice.",
    }


# ---------------------------------------------------------------------------
# reported-p parsing
# ---------------------------------------------------------------------------

# A paper's printed p-value carries at most a handful of decimals. A float
# whose shortest round-tripping decimal form needs more than this many (e.g.
# 0.1 + 0.2 -> 0.30000000000000004, 17 decimals) matches no cleanly printed
# number, so no precision is inferred from it and the check refuses.
_MAX_INFERRED_DECIMALS = 6


def _parse_reported_p(reported_p: Union[float, str]) -> tuple[Optional[float], bool, Optional[int]]:
    """Return (value, is_threshold, decimals_inferred).

    Accepts 0.171, "0.171", "<0.001", "p < 0.001", "≤ .05". For a threshold
    form the value is the threshold X and is_threshold=True.

    The decimals a paper printed are a fact about the PAPER; a bare float does
    not carry them. For numeric input the inferred precision is the shortest
    decimal form that round-trips the float (repr) — a LOWER bound on whatever
    the paper printed, so using it can only WIDEN the rounding interval, the
    lenient direction. (The old behaviour, a silent 3-decimal default, scored
    0.02 as "0.020" and manufactured a below-floor `impossible` the string
    spelling "0.02" did not.) Float-noise reprs longer than
    _MAX_INFERRED_DECIMALS yield decimals_inferred=None, which grimu_check
    refuses rather than scores.
    """
    if isinstance(reported_p, (int, float)):
        value = float(reported_p)
        exponent = decimal.Decimal(repr(value)).as_tuple().exponent
        if not isinstance(exponent, int):        # non-finite float: 'n'/'N'/'F'
            return value, False, None
        inferred = max(0, -exponent)
        if inferred > _MAX_INFERRED_DECIMALS:
            inferred = None
        return value, False, inferred
    s = str(reported_p).strip().lower().lstrip("p").strip()
    is_threshold = s.startswith("<") or s.startswith("≤")
    cleaned = s.lstrip("<≤=").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return None, is_threshold, None
    # infer decimals from the literal (".171" -> 3, "0.001" -> 3)
    decimals = len(cleaned.split(".")[1]) if "." in cleaned else 0
    return value, is_threshold, decimals


# ---------------------------------------------------------------------------
# p-value engines
# ---------------------------------------------------------------------------

def _mu_sigma(n1: int, n2: int) -> tuple[float, float]:
    mU = n1 * n2 / 2.0
    sdU = (n1 * n2 * (n1 + n2 + 1) / 12.0) ** 0.5
    return mU, sdU


def _p_normal(U: float, mU: float, sdU: float, cc: float, one_sided: bool) -> float:
    if sdU == 0:
        return 1.0
    z = (abs(U - mU) - cc) / sdU
    if z < 0:
        z = 0.0
    tail = float(stats.norm.sf(z))
    return min(1.0, tail if one_sided else 2 * tail)


# Above this product the exact permutation distribution is skipped (granularity
# is negligible for large samples anyway; the normal approximation is used).
_EXACT_MAX_PRODUCT = 5000


def _exact_u_counts(n1: int, n2: int) -> list[int]:
    """Exact null counts of U over 0..n1*n2, as coefficients of the Gaussian
    binomial [n1+n2, n1]_q = prod_{k=1..n1} (1 - q^(n2+k)) / (1 - q^k).

    Computed iteratively (no recursion): multiply by each 1/(1 - q^k) geometric
    series, then by each numerator factor (1 - q^(n2+k)). Sums to C(n1+n2, n1).
    """
    N = n1 * n2
    coeffs = [0] * (N + 1)
    coeffs[0] = 1
    for k in range(1, n1 + 1):                       # multiply by 1/(1 - q^k)
        for i in range(k, N + 1):
            coeffs[i] += coeffs[i - k]
    for k in range(1, n1 + 1):                       # multiply by (1 - q^(n2+k))
        shift = n2 + k
        for i in range(N, shift - 1, -1):
            coeffs[i] -= coeffs[i - shift]
    return coeffs


def _exact_u_pmf(n1: int, n2: int) -> Optional[list[float]]:
    """Exact null pmf of U, or None if the sample is too large to enumerate."""
    if n1 * n2 > _EXACT_MAX_PRODUCT:
        return None
    counts = _exact_u_counts(n1, n2)
    total = sum(counts)
    return [c / total for c in counts]


def _p_exact(U: float, pmf: list[float], one_sided: bool) -> Optional[float]:
    """Exact two-sided p for an (integer) U from the null pmf. Half-integer U
    (ties) has no exact-permutation analogue, so returns None."""
    if abs(U - round(U)) > _TOL:
        return None
    u = int(round(U))
    if u < 0 or u >= len(pmf):
        return None
    import itertools
    cum = list(itertools.accumulate(pmf))
    lower = cum[u]
    upper = 1.0 - (cum[u - 1] if u > 0 else 0.0)
    tail = min(lower, upper)
    return min(1.0, tail if one_sided else 2 * tail)


# ---------------------------------------------------------------------------
# achievable set
# ---------------------------------------------------------------------------

def _achievable(
    n1: int, n2: int, ccs: list[float], methods: list[str], one_sided: bool
) -> list[dict]:
    """Every achievable (U, cc, method, p) over the lower half U in [0, mU].

    (p is symmetric about mU, so the lower half enumerates all distinct p.)
    """
    mU, sdU = _mu_sigma(n1, n2)
    pmf = _exact_u_pmf(n1, n2) if "exact" in methods else None

    out: list[dict] = []
    # half-integer grid from 0 to mU inclusive
    steps = int(round(mU * 2))
    for i in range(steps + 1):
        U = i / 2.0
        for cc in ccs:
            if "normal" in methods:
                out.append({
                    "U": U, "cc": cc, "method": "normal",
                    "p": _p_normal(U, mU, sdU, cc, one_sided),
                })
        if pmf is not None:
            pe = _p_exact(U, pmf, one_sided)
            if pe is not None:
                out.append({"U": U, "cc": 0.0, "method": "exact", "p": pe})
    return out


def _ccs_for(continuity_correction: str) -> list[float]:
    return {
        "none": [0.0],
        "cc": [0.5],
        "both": [0.0, 0.5],
    }.get(continuity_correction, [0.0, 0.5])


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def grimu_check(
    n1: int,
    n2: int,
    reported_p: Union[float, str],
    decimals: Optional[int] = None,
    continuity_correction: str = "both",
    method: str = "normal",
    include_exact_union: bool = True,
    one_sided: bool = False,
    test_type: str = "mann_whitney",
    reported_z: Optional[float] = None,
    p_source: str = "unspecified",
    ties_possible: Optional[bool] = None,
) -> dict:
    """Check a Mann-Whitney U / Wilcoxon rank-sum p-value against the achievable
    granular set for group sizes n1, n2.

    Args:
        n1, n2: the two group sizes.
        reported_p: the reported p (float, "0.171", or a threshold "<0.001").
            Prefer the STRING spelling: it carries the paper's printed
            precision ("0.020" vs "0.02"), which a float cannot.
        decimals: reported precision. If None it is inferred -- from the
            string literal, or for a bare float from its shortest
            round-tripping decimal form (a lower bound on the printed
            precision, so the interval can only widen). A float whose
            shortest form exceeds 6 decimals (float noise) is refused.
        continuity_correction: "none" | "cc" | "both" (default: consider both,
            since a paper rarely states whether CC was applied).
        method: "normal" | "exact" | "both" (the reference engine).
        include_exact_union: fold exact-permutation p's into the achievable set
            so the `impossible` verdict is robust to software conventions.
        one_sided: the reported p is one-sided.
        test_type: what test the paper attributed this p to. Only
            Mann-Whitney / Wilcoxon rank-sum are in scope; anything else
            (t, F, chi-squared, ANOVA, unspecified-as-other) is refused.
        reported_z: the normal-approximation Z the paper printed beside the p,
            if it printed one. PASS IT WHENEVER THE PAPER SHOWS ONE. If that Z
            reproduces the p at its printed precision, the p is a function of
            the rounded Z rather than of U and the check REFUSES -- see
            `_refuse_p_from_z` for the measured false positives it prevents.
        p_source: "u_statistic" | "normal_z" | "unspecified" (default). An
            explicit "normal_z" refuses without needing the Z itself.
        ties_possible: True when the outcome is a small-integer or ordinal
            scale, so ranks tie and the tie-corrected sdU moves every
            achievable p off the untied lattice. Refuses the granularity
            branch only; the below-floor branch is unaffected and still runs.

    Returns a dict with severity + supporting detail (see module docstring).
    """
    # -- guards --
    if canonical_test_type(test_type) not in {"mann_whitney", "wilcoxon"}:
        return _refuse_wrong_test(test_type)
    if str(p_source or "").strip().lower() in _Z_SOURCES:
        return _refuse_p_from_z(reported_p, reported_z, n1, n2, matches=False)
    if reported_z is not None and _z_reproduces_p(reported_z, reported_p,
                                                  decimals, one_sided):
        return _refuse_p_from_z(reported_p, reported_z, n1, n2, matches=True)
    if n1 < 1 or n2 < 1:
        return {"error": f"group sizes must be >= 1 (got n1={n1}, n2={n2})",
                "severity": INDETERMINATE}
    p_val, is_threshold, inferred = _parse_reported_p(reported_p)
    if p_val is None:
        return {"error": f"could not parse reported_p: {reported_p!r}",
                "severity": INDETERMINATE}
    if not (0 < p_val <= 1):
        return {"error": f"reported_p must be in (0, 1] (got {p_val})",
                "severity": INDETERMINATE}
    if decimals is not None:
        decimals_source = "caller"
    elif inferred is None:
        # A float whose shortest decimal form is float noise (0.1 + 0.2 ->
        # 0.30000000000000004) matches no cleanly printed p-value, and there
        # is no defensible precision to score it at. Refuse visibly rather
        # than assume one: the assumed-3-decimals default this replaces turned
        # honest reports into below-floor impossibilities.
        return {
            "error": (
                f"cannot infer the printed precision (decimals) of "
                f"reported_p={reported_p!r}: its shortest decimal form needs "
                f"more than {_MAX_INFERRED_DECIMALS} decimals, which matches "
                "no cleanly printed p-value. Pass the p-value as the printed "
                "string (e.g. '0.3') or supply decimals= explicitly."
            ),
            "severity": INDETERMINATE,
            "reported_p": reported_p,
        }
    else:
        decimals = inferred
        decimals_source = (
            "printed_literal" if isinstance(reported_p, str)
            # repr round-trip = MINIMUM decimals the paper could have printed;
            # never narrower than the true printed form, so never accusatory.
            else "float_repr_minimum"
        )

    methods = ["normal"]
    if method in ("exact", "both") or include_exact_union:
        methods.append("exact")
    ccs = _ccs_for(continuity_correction)

    mU, sdU = _mu_sigma(n1, n2)
    achievable = _achievable(n1, n2, ccs, methods, one_sided)

    # floor = smallest achievable p (at U=0), per convention and overall
    floor_by_conv: dict[str, float] = {}
    for a in achievable:
        if abs(a["U"]) <= _TOL:
            key = f"{a['method']}{'+cc' if a['cc'] else ''}"
            floor_by_conv[key] = a["p"]
    floor_p = min(floor_by_conv.values()) if floor_by_conv else None
    min_possible_p = floor_p

    half = _half_width(decimals)
    lo, hi = p_val - half, p_val + half

    # -- threshold "<X" branch: is the floor legitimately below X? --
    if is_threshold:
        if floor_p is not None and floor_p >= p_val - _TOL:
            # even the smallest achievable p is >= the claimed threshold:
            # "<X" cannot be reached -> impossible reporting error
            return _result(
                IMPOSSIBLE, False, n1, n2, mU, sdU, p_val, [lo, hi], decimals,
                floor_p, floor_by_conv, min_possible_p, achievable, [],
                below_floor=True, is_threshold=True,
                decimals_source=decimals_source,
                explanation=(
                    f"Reported p < {p_val} is impossible: the minimum achievable "
                    f"Mann-Whitney p for {n1}v{n2} (at U=0) is {floor_p:.6g}, which "
                    f"is already >= {p_val}. No rank configuration can produce a "
                    f"value this small."
                ),
            )
        return _result(
            CONSISTENT, True, n1, n2, mU, sdU, p_val, [lo, hi], decimals,
            floor_p, floor_by_conv, min_possible_p, achievable, [],
            below_floor=False, is_threshold=True,
            decimals_source=decimals_source,
            explanation=(
                f"Reported p < {p_val} is reachable: the minimum achievable p "
                f"(U=0) is {floor_p:.6g} < {p_val}. Consistent with a genuine "
                f"low p (e.g. non-overlapping groups). For whether the hidden "
                f"exact value is suspiciously small, see stalt_check."
            ),
        )

    def _exact_result(*args, **kwargs):
        """Exact-p scoring, dual-read when the p is a conventional alpha.

        A model that stripped '<' from 'p<0.05' used to turn a reachable
        threshold into a granularity miss. If the bound reading does not
        accuse, neither do we.
        """
        res = _result(*args, **kwargs)
        if res["severity"] not in {IMPOSSIBLE, SUSPICIOUS}:
            return res
        from .ttest import is_conventional_alpha
        if not is_conventional_alpha(p_val):
            return res
        as_bound = grimu_check(
            n1, n2, f"<{p_val}", decimals=decimals,
            continuity_correction=continuity_correction, method=method,
            include_exact_union=include_exact_union, one_sided=one_sided,
            test_type=test_type,
        )
        if as_bound.get("severity") in {CONSISTENT, INDETERMINATE}:
            out = dict(res)
            out["severity"] = INDETERMINATE
            out["failure_mode"] = "p_reading_ambiguous"
            out["explanation"] = (
                "Reported p equals a conventional alpha and was scored as an "
                "exact value; reading it as a threshold bound does not accuse. "
                "The two readings disagree, so this is not reported as a finding."
            )
            return out
        return res

    # -- below-floor impossibility: entire interval below the floor everywhere --
    if floor_p is not None and hi < floor_p - _TOL:
        return _exact_result(
            IMPOSSIBLE, False, n1, n2, mU, sdU, p_val, [lo, hi], decimals,
            floor_p, floor_by_conv, min_possible_p, achievable, [],
            below_floor=True,
            decimals_source=decimals_source,
            explanation=(
                f"Reported p = {p_val} lies entirely below the minimum achievable "
                f"Mann-Whitney p for {n1}v{n2} (floor at U=0 is {floor_p:.6g}, across "
                f"all conventions). No rank sum can produce a p this small — a "
                f"likely reporting error."
            ),
        )

    # -- matching: any achievable U whose p is in the reported interval --
    matched = [a for a in achievable if lo - _TOL <= a["p"] <= hi + _TOL]
    # de-dup identical (U, cc, method) already unique; sort by closeness
    matched.sort(key=lambda a: abs(a["p"] - p_val))

    if matched:
        conv = _describe_convention(matched[0])
        return _exact_result(
            CONSISTENT, True, n1, n2, mU, sdU, p_val, [lo, hi], decimals,
            floor_p, floor_by_conv, min_possible_p, achievable, matched,
            decimals_source=decimals_source,
            explanation=(
                f"Reported p = {p_val} is reproduced by U = {matched[0]['U']:g} "
                f"({conv}); consistent with a Mann-Whitney/Wilcoxon test on "
                f"{n1}v{n2}."
            ),
        )

    # -- bracket the reported value with the nearest achievable p's --
    below = [a for a in achievable if a["p"] < p_val]
    above = [a for a in achievable if a["p"] > p_val]
    nearest_below = max(below, key=lambda a: a["p"]) if below else None
    nearest_above = min(above, key=lambda a: a["p"]) if above else None

    # -- granularity-vanished gate: the LOCAL bracket around the reported value
    # is narrower than one rounding unit, so a "miss" is not discriminating. --
    if (nearest_below is not None and nearest_above is not None
            and (nearest_above["p"] - nearest_below["p"]) < 2 * half - _TOL):
        return _exact_result(
            CONSISTENT, True, n1, n2, mU, sdU, p_val, [lo, hi], decimals,
            floor_p, floor_by_conv, min_possible_p, achievable, [],
            nearest_below=nearest_below, nearest_above=nearest_above,
            note="granularity_insufficient", decimals_source=decimals_source,
            explanation=(
                f"At {n1}v{n2} the achievable p-values bracketing {p_val} "
                f"(U={nearest_below['U']:g}→{nearest_below['p']:.4g}, "
                f"U={nearest_above['U']:g}→{nearest_above['p']:.4g}) are spaced "
                f"more finely than the reported precision ({decimals} dp), so "
                f"GRIM-U has no discriminating power here — not flagged."
            ),
        )

    # -- granularity inconsistency: reachable-in-range but no U matches --
    if ties_possible:
        return _refuse_ties(reported_p, n1, n2)
    return _exact_result(
        SUSPICIOUS, False, n1, n2, mU, sdU, p_val, [lo, hi], decimals,
        floor_p, floor_by_conv, min_possible_p, achievable, [],
        nearest_below=nearest_below, nearest_above=nearest_above,
        decimals_source=decimals_source,
        explanation=(
            f"Reported p = {p_val} falls between achievable Mann-Whitney p-values "
            f"for {n1}v{n2} and is reproduced by no permissible rank sum "
            f"(nearest: "
            f"{_fmt_neighbor(nearest_below)} below, {_fmt_neighbor(nearest_above)} "
            f"above). A granularity inconsistency — often a software / continuity-"
            f"correction / rounding artifact, so treated cautiously, not as "
            f"impossible."
        ),
    )


def _describe_convention(a: dict) -> str:
    if a["method"] == "exact":
        return "exact permutation"
    return "normal approx, continuity correction" if a["cc"] else "normal approx, no continuity correction"


def _fmt_neighbor(a: Optional[dict]) -> str:
    if a is None:
        return "none"
    return f"U={a['U']:g}→p={a['p']:.4g}"


def _result(severity, consistent, n1, n2, mU, sdU, reported_p, interval,
            decimals, floor_p, floor_by_conv, min_possible_p, achievable,
            matched, *, below_floor=False, is_threshold=False, note=None,
            nearest_below=None, nearest_above=None, decimals_source=None,
            explanation="") -> dict:
    n_distinct = len({round(a["p"], decimals) for a in achievable})
    return {
        "severity": severity,
        "consistent": consistent,
        "reported_p": reported_p,
        "reported_p_interval": interval,
        "decimals": decimals,
        # where `decimals` came from: "caller" (explicit argument),
        # "printed_literal" (counted off the string spelling), or
        # "float_repr_minimum" (shortest round-tripping decimal form of a bare
        # float -- a lower bound on the printed precision, disclosed because
        # it is OUR inference, not the paper's statement).
        "decimals_source": decimals_source,
        "n1": n1, "n2": n2,
        "mU": mU, "sdU": sdU,
        "floor_p": floor_p,
        "floor_p_by_convention": floor_by_conv,
        "min_possible_p": min_possible_p,
        "n_achievable_p": n_distinct,
        "below_floor": below_floor,
        "is_threshold": is_threshold,
        "matched": [
            {"U": a["U"], "cc": a["cc"], "p": a["p"], "method": a["method"]}
            for a in matched[:6]
        ],
        "matched_convention": _describe_convention(matched[0]) if matched else None,
        "nearest_below": (
            {"U": nearest_below["U"], "p": nearest_below["p"]} if nearest_below else None
        ),
        "nearest_above": (
            {"U": nearest_above["U"], "p": nearest_above["p"]} if nearest_above else None
        ),
        "note": note,
        "explanation": explanation,
        "methodology": (
            f"GRIM-U: Mann-Whitney U for {n1}v{n2} has mU={mU:g}, "
            f"sdU={sdU:.4f}; achievable U are {{0, 0.5, ..., {n1*n2}}} giving "
            f"{n_distinct} distinct p at {decimals} dp (normal approximation, "
            f"±continuity correction, exact-permutation union). Reported "
            f"p={reported_p} checked against interval "
            f"[{interval[0]:.6g}, {interval[1]:.6g})."
        ),
    }


def _severity_rank(severity: Optional[str]) -> int:
    """Position in SEVERITY_LEVELS (0 = most severe, i.e. `impossible`).

    Unknown/missing severities sort as LEAST severe so a malformed per-value
    result can never masquerade as the worst finding.
    """
    try:
        return SEVERITY_LEVELS.index(severity)
    except ValueError:
        return len(SEVERITY_LEVELS)


def grimu_coexistence(
    n1: int,
    n2: int,
    p_values: list[Union[float, str]],
    decimals: Optional[int] = None,
    continuity_correction: str = "both",
    method: str = "normal",
    one_sided: bool = False,
    test_type: str = "mann_whitney",
    p_source: str = "unspecified",
    ties_possible: Optional[bool] = None,
) -> dict:
    """Flag minimally-differing p-values from the same n1, n2 that cannot both
    be reproduced by achievable U's (Heathers & Grimes' co-existence heuristic).

    e.g. Brouwers 0.171 vs 0.172 (n=8v8): 0.172 → U=19, but 0.171 is reproduced
    by no U and is bracketed by U=18.5 (0.156) and U=19 (0.172).

    `one_sided` marks the reported p's as one-sided and is passed through to
    every per-value check: a one-sided table scored against the two-sided
    achievable set is a false accusation (8v8 p=0.086 is suspicious two-sided
    but consistent one-sided).
    """
    if canonical_test_type(test_type) not in {"mann_whitney", "wilcoxon"}:
        return _refuse_wrong_test(test_type)
    # The co-existence heuristic reads the SAME untied lattice, so the same two
    # preconditions void it. Refusing here rather than only per-value keeps the
    # aggregate from reporting a violation built out of refusals.
    if str(p_source or "").strip().lower() in _Z_SOURCES:
        return _refuse_p_from_z(p_values, None, n1, n2, matches=False)
    if ties_possible:
        return _refuse_ties(p_values, n1, n2)
    if n1 < 1 or n2 < 1:
        return {"error": f"group sizes must be >= 1 (got n1={n1}, n2={n2})",
                "severity": INDETERMINATE}
    if not p_values or len(p_values) < 2:
        return {"error": "need at least two p-values", "severity": INDETERMINATE}

    per_value = []
    for p in p_values:
        r = grimu_check(n1, n2, p, decimals=decimals,
                        continuity_correction=continuity_correction, method=method,
                        one_sided=one_sided, test_type=test_type)
        per_value.append({
            "reported_p": r.get("reported_p"),
            "severity": r.get("severity"),
            "consistent": r.get("consistent"),
            "matched": r.get("matched"),
            "nearest_below": r.get("nearest_below"),
            "nearest_above": r.get("nearest_above"),
        })

    # a violation: a granularity-inconsistent value that differs minimally from
    # another (consistent) value from the same sample
    violations = []
    vals = [(pv, _parse_reported_p(pv["reported_p"])[0]) for pv in per_value]
    for i, (pa, va) in enumerate(vals):
        if pa["severity"] != SUSPICIOUS or va is None:
            continue
        for j, (pb, vb) in enumerate(vals):
            if i == j or vb is None:
                continue
            d = max(decimals or 3, 1)
            if abs(va - vb) <= _half_width(d) * 2 + _TOL and pb["consistent"]:
                violations.append({
                    "p_inconsistent": va,
                    "p_consistent": vb,
                    "reason": (
                        f"p={va} is reproduced by no achievable U while the "
                        f"minimally-different p={vb} is (U="
                        f"{pb['matched'][0]['U']:g}); they cannot co-exist for "
                        f"a Mann-Whitney test on {n1}v{n2}."
                    ),
                })

    # Top-level severity = the WORST per-value severity, which the pairwise
    # co-existence verdict can only RAISE, never lower. A consumer that reads
    # only this field must not be told a set is clean because the pairwise rule
    # did not fire: two below-floor p-values are individually `impossible` yet
    # trigger no co-existence violation, and reporting that as `consistent`
    # turns a detected impossibility into a missed one.
    severities = [pv["severity"] for pv in per_value]
    if violations:
        severities.append(SUSPICIOUS)
    severity = min(severities, key=_severity_rank)
    flagged = [s for s in severities[:len(per_value)] if s != CONSISTENT]
    return {
        "severity": severity,
        "n1": n1, "n2": n2,
        "per_value": per_value,
        "coexistence_violations": violations,
        "explanation": (
            f"{len(violations)} co-existence violation(s): minimally-differing "
            f"p-values from the same {n1}v{n2} sample that cannot both arise from "
            f"achievable rank sums."
            if violations else
            (
                f"No co-existence violations among the supplied p-values, but "
                f"{len(flagged)} of {len(per_value)} p-value(s) are individually "
                f"flagged (worst: {severity}); see per_value."
                if flagged else
                "No co-existence violations among the supplied p-values."
            )
        ),
        "methodology": (
            "GRIM-U co-existence: build the achievable p-set for the shared "
            "group sizes, then flag any granularity-inconsistent p that differs "
            "minimally from a reproducible p (they cannot both be real)."
        ),
    }
