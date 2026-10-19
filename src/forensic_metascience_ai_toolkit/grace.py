"""A discrepancy that was forgiven is still a discrepancy, and it is recorded.

WHY THIS EXISTS. Every check in this toolkit applies allowances before it
returns: a printed-precision interval, a one-tailed reading, a population-versus
-sample SD, a truncated mean. Those allowances are what keep the tools from
convicting honest papers, and removing them is not an option -- the cardinal
rule says a false accusation is the worst output there is.

But they were applied INSIDE the check, so an item they rescued came back
`consistent` and its raw residual was destroyed at source. That threw away the
only signal that distinguishes rounding noise from something else: DIRECTION.

Fifty cells each within rounding tolerance is noise. Fifty cells each within
tolerance of which forty-seven lean the SAME WAY is not, and no individual cell
can tell you that -- it is a property of the set. This is the reasoning behind
terminal-digit and Carlisle-family analyses, and the old architecture made it
uncomputable, because by the time anything could aggregate, every rescued item
looked identical to an item that reconciled exactly.

WHAT THIS MODULE DOES NOT DO. It does not change a single verdict. A rescued
item is still `consistent` and still not an accusation; that is deliberate and
must stay that way. It records what the check already knew and was throwing
away, so a reader can be shown "these 37 rows reconcile only once rounding is
allowed for, and 34 of the 37 err in the direction that favours the reported
result" -- a sentence the pipeline could not previously form about itself.

THE VOCABULARY IS CLOSED. A free-text reason is how a closed vocabulary stops
being closed, and the point of naming each allowance is that a reader can ask
how often each one is doing the rescuing.
"""

from __future__ import annotations

import math
from typing import Any

#: Why an item that did NOT reconcile on its printed values reconciles anyway.
#: Each is a real reporting convention, not a fudge factor -- and each is a
#: hypothesis about the paper that a reader is entitled to see us relying on.
GRACE_KINDS: dict[str, str] = {
    "printed_precision":
        "the values agree once each is read as the interval its printed "
        "precision asserts, rather than as an exact number",
    "one_tailed":
        "the reported p is half the two-tailed p, consistent with a directional "
        "test the paper may legitimately have run",
    "population_sd":
        "the dispersion reconciles under the population (n) convention rather "
        "than the sample (n-1) one",
    "truncation":
        "the value reconciles if it was truncated rather than rounded",
    "threshold_bound":
        "the reported value is a bound ('p < .001'), not an exact quantity",
    "alternative_test":
        "a different but defensible variant of the same test reconciles it "
        "(Welch against Student, Yates against Pearson)",
    "shared_denominator":
        "the row reconciles under a denominator the paper does not print",
}

#: A rescued item is CONSISTENT. This module never raises a severity, and the
#: constant exists so that intent is greppable rather than implied.
RESCUE_NEVER_ACCUSES = True


def record(*, strict_ok: bool, lenient_ok: bool, grace: str | None = None,
           reported: float | None = None, nearest_consistent: float | None = None,
           note: str = "") -> dict[str, Any]:
    """One item's grace record, in the shape the aggregate consumes.

    `strict_ok`  -- did it reconcile on the printed values alone?
    `lenient_ok` -- did it reconcile once the allowance was applied?
    `grace`      -- which allowance, from GRACE_KINDS, did the rescuing.

    `residual` is signed: POSITIVE when the reported value is larger than the
    nearest value that would have reconciled strictly. The sign is the entire
    point -- an unsigned magnitude cannot show a lean, and a lean is what
    separates rounding from everything else.
    """
    if grace is not None and grace not in GRACE_KINDS:
        raise ValueError(
            f"grace={grace!r} is not in the closed vocabulary; add it to "
            f"GRACE_KINDS with a sentence a reader can evaluate, or use one of "
            f"{sorted(GRACE_KINDS)}")

    residual = None
    if (reported is not None and nearest_consistent is not None
            and math.isfinite(reported) and math.isfinite(nearest_consistent)):
        residual = float(reported) - float(nearest_consistent)

    return {
        "strict": "reconciles" if strict_ok else "does_not_reconcile",
        "rescued": bool(lenient_ok and not strict_ok),
        "grace": grace if (lenient_ok and not strict_ok) else None,
        "residual": residual,
        "direction": (0 if not residual else (1 if residual > 0 else -1)),
        "note": note,
    }


def summarise(records: list[dict]) -> dict[str, Any]:
    """The set-level reading, which is the only level where a lean is visible.

    Reports the counts, the split by allowance, and -- where residual signs are
    available -- how lopsided they are, with an exact two-sided sign test. No
    verdict is issued here: a lean is evidence for a reader, not an accusation,
    and the toolkit has no calibrated threshold for one.
    """
    recs = [r for r in (records or []) if isinstance(r, dict)]
    rescued = [r for r in recs if r.get("rescued")]
    by_kind: dict[str, int] = {}
    for r in rescued:
        k = r.get("grace") or "unnamed"
        by_kind[k] = by_kind.get(k, 0) + 1

    signs = [r["direction"] for r in rescued if r.get("direction")]
    pos = sum(1 for s in signs if s > 0)
    n = len(signs)
    p_lean = _sign_test(pos, n) if n else None

    return {
        "n_items": len(recs),
        "n_reconciled_strictly": sum(1 for r in recs if r.get("strict") == "reconciles"),
        "n_rescued": len(rescued),
        "by_grace": by_kind,
        "n_with_direction": n,
        "n_leaning_high": pos,
        "n_leaning_low": n - pos,
        "sign_test_p": p_lean,
        "reading": _reading(len(rescued), pos, n, p_lean),
    }


def _sign_test(pos: int, n: int) -> float:
    """Exact two-sided binomial test against p = 0.5. No scipy dependency: the
    counts here are small and an exact sum is both cheap and auditable."""
    if n <= 0:
        return 1.0
    def _pmf(k: int) -> float:
        return math.comb(n, k) * 0.5 ** n
    obs = _pmf(pos)
    # Two-sided by the method of small probabilities: everything at least as
    # unlikely as what was observed.
    return min(1.0, sum(_pmf(k) for k in range(n + 1) if _pmf(k) <= obs + 1e-15))


def _reading(n_rescued: int, pos: int, n: int, p: float | None) -> str:
    """The set-level sentence.

    REPORTS THE MAJORITY, NOT `pos`. Written first as "{pos} of {n} lean the
    same way", which reads "0 of 24 lean the same way" when all 24 lean LOW --
    the strongest possible signal, printed as though it were the absence of one.
    Caught by reading the output rather than the code.
    """
    if not n_rescued:
        return "Nothing needed an allowance; every item reconciled on its printed values."
    base = (f"{n_rescued} item(s) reconcile only once an allowance is applied. "
            "Each is individually explainable and none is an accusation.")
    if not n or p is None:
        return base + " No signed residuals were available, so no lean can be assessed."
    same = max(pos, n - pos)
    way = "high" if pos >= n - pos else "low"
    if p < 0.01:
        return (base + f" Their residuals are lopsided -- {same} of {n} lean {way} "
                f"(sign test p = {p:.4f}). A set of individually forgivable "
                "discrepancies that nearly all point one way is worth a human's "
                "eye, because rounding has no reason to prefer a direction.")
    if p < 0.05:
        return (base + f" {same} of {n} lean {way} (sign test p = {p:.3f}), "
                "which is suggestive rather than conclusive.")
    return (base + f" Their residuals are close to evenly split ({pos} of {n} high, "
            f"sign test p = {p:.2f}), which is what rounding alone looks like.")
