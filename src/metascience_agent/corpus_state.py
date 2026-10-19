"""A comparable snapshot of what the register currently says about a corpus.

WHY THIS EXISTS. Greg, 2026-08-21: Dan is landing his own changes to this
codebase, and "the version he created will not have the kind of coverage as
ours... we will need to use our framework for sanity-checking the results."

Merging someone else's work is, in this repository's own terms, A FIX
ELSEWHERE. 2026-08-20 produced three separate cases of a measured claim being
falsified by one -- an "absence of negative examples" that a header fix
disproved, an unlabelled-column count that conflated our defect with the
file's, and a note recommending a change that would have deleted data. In every
case the number had been true when written.

After a merge, every figure we hold is a claim about the code that produced it,
not about the corpus. The only honest way to tell an improvement from a
regression is to have written the BEFORE down first, in a form that can be
compared mechanically rather than from memory.

WHAT THIS DELIBERATELY DOES NOT DO IS JUDGE. It reports numbers and the
difference between two sets of them; a human decides which direction is good.
`n_ambiguous_columns` rising after a merge could mean the reader got worse, or
that it began reading tables it used to skip entirely -- opposite conclusions
from the same delta, and nothing here can distinguish them. A tool that
returned a verdict would invite tuning until the verdict was green, which is
the failure this repository's residual-publishing rule exists to prevent.

IT LIVES IN ITS OWN MODULE ON PURPOSE. A new file is the least likely thing a
merge mangles, and the instrument used to check a merge should not be one of
the things the merge can quietly break.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

#: A problem string from `prepass` that means the reading predates a fix.
#: Matched on the word the guard itself uses; see
#: `prepass._report_stale_caches`.
_STALE = "schema"


def snapshot_register(register: dict) -> dict:
    """The measures we actually argue from, pulled out of one register.

    Every key is present unconditionally, including as a zero. An omitted key
    reads as "not measured", and the difference between "measured zero" and
    "never looked" is the one this codebase spends most of its guards on.
    """
    from . import values as V

    groups = register.get("groups") or []
    problems = list(register.get("problems") or [])

    roles: dict[str, int] = {}
    n_values = 0
    for g in groups:
        for v in (g.get("values") or []):
            n_values += 1
            r = str(v.get("role") or "unknown")
            roles[r] = roles.get(r, 0) + 1

    amb = register.get("ambiguous_columns")
    if not isinstance(amb, dict):
        amb = V.ambiguous_columns({"groups": groups})

    # THE NUMERAL FLOOR, so the merge-diff can see it shrink.
    #
    # This snapshot tracked groups, values, roles and ambiguity, and NO numeral
    # fields at all -- while `register["numerals"]` sat in the very register it
    # was snapshotting. So the section-8b instrument, which exists to catch a
    # capability quietly disappearing across a merge, was BLIND to the one
    # measure most easily reduced by accident.
    #
    # THE DISTINCTION IT HAS TO ENCODE. There are two ways to make the "not yet
    # judged" panel smaller and they look identical to a reader:
    #   CLASSIFICATION moves rows between buckets and leaves `n_total` alone.
    #     Today's `_CITATION` fix did exactly this: citation_year +206 corpus
    #     wide, n_total invariant at 3,371.
    #   SUPPRESSION shrinks `n_total` -- the denominator of every "numbers we
    #     did not check" claim. `numerals.tally` promises that denominator
    #     "cannot quietly shrink", but a repackaging rewrite runs UPSTREAM of
    #     indexing, which is exactly the mechanism by which it can.
    # Recording `n_total` beside the histogram is what tells them apart.
    #
    # ZERO-FILLED FROM `numerals.CLASSES`, deliberately. Without it a class that
    # measures zero vanishes from the histogram, and "measured zero" collapses
    # into "never looked" -- the same absence-as-knowledge error this codebase
    # keeps repairing. A class REMOVED from CLASSES then shows as GONE in the
    # diff, which is the line section 8b says matters.
    from . import numerals as _numerals
    nu = register.get("numerals") or {}
    by = dict(nu.get("by_class") or {})

    return {
        "has_numeral_floor": 1 if nu else 0,
        "n_numerals_total": int(nu.get("n_total") or 0),
        "n_numerals_judged": int(nu.get("n_judged") or 0),
        "numeral_classes": {c: int(by.get(c, 0)) for c in _numerals.CLASSES},
        # THE SPLIT BESIDE THE TOTAL, always (Greg, 2026-09-06). A total that
        # rises because table cells joined the floor and one that rises
        # because a reader improved are the same number without this.
        "numerals_by_source": {k: int((v or {}).get("n_total") or 0)
                               for k, v in sorted((nu.get("by_source") or {}).items())},
        "n_groups": len(groups),
        "n_values": n_values,
        "n_table_groups": amb.get("n_groups_total", 0),
        "n_ambiguous_columns": amb.get("n_groups", 0),
        "n_ambiguous_unknown": amb.get("n_unknown", 0),
        "n_untyped_groups": register.get("n_untyped_groups") or 0,
        "n_cells_with_no_value": register.get("n_cells_with_no_value") or 0,
        "n_problems": len(problems),
        "n_stale_cache_warnings": sum(1 for p in problems if _STALE in str(p)),
        "roles": dict(sorted(roles.items())),
    }


def snapshot_paper(paper_dir: Any) -> dict:
    """Snapshot one paper, building its register from what is on disk."""
    from . import values as V

    d = Path(paper_dir)
    reg = V.build_from_paper(d)
    out = snapshot_register(reg)
    out["paper"] = d.name
    return out


def snapshot_corpus(corpus_dir: Any) -> dict:
    """Snapshot every paper directory under `corpus_dir`, plus totals.

    A paper that raises is RECORDED, not skipped: a corpus that silently
    shrinks between two runs would make the diff meaningless in exactly the
    direction that flatters the newer code.
    """
    base = Path(corpus_dir)
    papers: list[dict] = []
    failed: list[dict] = []
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        try:
            papers.append(snapshot_paper(d))
        except Exception as exc:  # noqa: BLE001
            failed.append({"paper": d.name,
                           "error": f"{type(exc).__name__}: {exc}"})

    totals: dict[str, Any] = {"n_papers": len(papers),
                              "n_papers_failed": len(failed)}
    roles: dict[str, int] = {}
    numeral_classes: dict[str, int] = {}
    numerals_by_source: dict[str, int] = {}
    for p in papers:
        for k, v in p.items():
            if k in ("paper", "roles", "numeral_classes", "numerals_by_source"):
                continue
            totals[k] = totals.get(k, 0) + v
        for k, v in (p.get("roles") or {}).items():
            roles[k] = roles.get(k, 0) + v
        for k, v in (p.get("numeral_classes") or {}).items():
            numeral_classes[k] = numeral_classes.get(k, 0) + v
        for k, v in (p.get("numerals_by_source") or {}).items():
            numerals_by_source[k] = numerals_by_source.get(k, 0) + v
    totals["roles"] = dict(sorted(roles.items()))
    totals["numeral_classes"] = dict(sorted(numeral_classes.items()))
    totals["numerals_by_source"] = dict(sorted(numerals_by_source.items()))

    return {"corpus": str(base), "totals": totals,
            "papers": papers, "failed": failed}


def _flat(totals: dict) -> dict:
    """Totals with the role histogram flattened to `role:<name>` keys."""
    out = {}
    for k, v in (totals or {}).items():
        if k == "roles" and isinstance(v, dict):
            for rk, rv in v.items():
                out[f"role:{rk}"] = rv
        elif k == "numeral_classes" and isinstance(v, dict):
            for rk, rv in v.items():
                out[f"numclass:{rk}"] = rv
        elif k == "numerals_by_source" and isinstance(v, dict):
            for rk, rv in v.items():
                out[f"numsrc:{rk}"] = rv
        elif isinstance(v, (int, float)):
            out[k] = v
    return out


def diff(before: dict, after: dict) -> dict:
    """Every measure, its two values, and the change. NO verdict.

    A key present on only one side is NAMED with `None` on the other rather
    than dropped -- a measure that stopped being computed is the single most
    important thing a merge can do to this framework, and dropping it from the
    diff would hide exactly that.
    """
    b = _flat(before.get("totals") if "totals" in before else before)
    a = _flat(after.get("totals") if "totals" in after else after)
    out: dict[str, dict] = {}
    for key in sorted(set(b) | set(a)):
        bv, av = b.get(key), a.get(key)
        out[key] = {
            "before": bv,
            "after": av,
            "change": (av - bv) if (bv is not None and av is not None) else None,
        }
    return out


def render_diff(d: dict) -> str:
    """The diff as text, changed measures first, unchanged still listed."""
    rows = sorted(d.items(),
                  key=lambda kv: (kv[1]["change"] == 0, -abs(kv[1]["change"] or 0)))
    width = max((len(k) for k in d), default=8)
    lines = [f"{'measure'.ljust(width)}  {'before':>10}  {'after':>10}  {'change':>10}"]
    for k, v in rows:
        ch = v["change"]
        mark = "" if ch in (0, None) else ("  +" if ch > 0 else "  -")
        lines.append(
            f"{k.ljust(width)}  {str(v['before']):>10}  {str(v['after']):>10}  "
            f"{('GONE' if v['after'] is None else 'NEW' if v['before'] is None else ch):>10}{mark}")
    lines.append("")
    lines.append("Direction is NOT a verdict. More ambiguous columns may mean a "
                 "worse reader OR a reader that stopped skipping tables.")
    return "\n".join(lines)
