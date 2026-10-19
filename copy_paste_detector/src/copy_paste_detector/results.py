"""Aggregate findings, apply context caps, and report coverage."""

from __future__ import annotations

from collections import Counter

from .constants import (
    _DIFFUSE_COLUMN_FRACTION,
    _DIFFUSE_EXEMPT_SCORE,
    _DIFFUSE_MIN_COLUMNS,
    _TIERS,
)
from .screening import (
    _column_name,
    _group_columns,
    _infer_context,
)
from .severity import (
    CONSISTENT,
    INDETERMINATE,
)


def _aggregate(
    *,
    caveats,
    corroborating,
    data_context,
    diversity,
    duplicate_groups,
    excluded,
    implicated_rows,
    n_numeric_total,
    norm,
    p,
    qualifying_pairs,
    seen_pairs,
    segments,
):
    """Apply final caps and sorting in place, then build the existing result dictionary."""
    # ---- aggregate ---------------------------------------------------------
    top = CONSISTENT
    if duplicate_groups:
        top = min((g["severity"] for g in duplicate_groups), key=_TIERS.index)

    # Two reasons to cap at indeterminate, sharing one mechanism: the caller
    # declared pooled data, or the headers say this is not raw data at all.
    inferred = _infer_context(segments)
    cap_reason = ""
    if data_context == "pooled_or_meta_analysis":
        cap_reason = "pooled"
    elif inferred:
        cap_reason = inferred

    # Announce whenever the file is not what the detector is for, even if
    # nothing needed lowering: "we scanned the wrong kind of file" is the
    # useful half of the message, and it does not depend on the verdict.
    context_capped = bool(cap_reason) and (
        cap_reason != "pooled" or _TIERS.index(top) < _TIERS.index(INDETERMINATE)
    )
    if cap_reason and _TIERS.index(top) < _TIERS.index(INDETERMINATE):
        for g in duplicate_groups:
            if _TIERS.index(g["severity"]) < _TIERS.index(INDETERMINATE):
                g["severity"] = INDETERMINATE
                g["context_capped"] = True
        top = INDETERMINATE

    duplicate_groups.sort(
        key=lambda g: (_TIERS.index(g["severity"]), -g.get("adjusted_score", 0.0))
    )

    # ---- diffuse-evidence cap ---------------------------------------------
    # Copy-paste is LOCAL: a few recycled rows, one filled-down block. When
    # findings instead spread across most of a file's columns, the likelier
    # explanation is that the tool has misread the file -- a format it does
    # not understand, an instrument that repeats itself -- than that every
    # variable was independently fabricated. Cap and say so, rather than
    # returning a confident verdict built on a misreading.
    diffuse_capped = False
    n_included = len(diversity)
    # ROW PAIRS ARE EXEMPT FROM THE COLUMN COUNT. A genuinely duplicated
    # participant record matches across MOST of the file by definition -- that
    # is what makes it a duplicate -- so counting its columns as evidence of
    # diffuseness punishes the strongest finding for being strong. The cap is
    # aimed at repeated values and runs smeared over unrelated columns.
    diffuse_groups = [g for g in duplicate_groups if g.get("kind") != "row_pair"]
    if (
        not context_capped
        and n_included >= _DIFFUSE_MIN_COLUMNS
        and diffuse_groups
        and _TIERS.index(top) < _TIERS.index(INDETERMINATE)
    ):
        n_flagged = len(set().union(*(_group_columns(g) for g in diffuse_groups)))
        if n_flagged >= _DIFFUSE_COLUMN_FRACTION * n_included:
            # ...but the cap expresses doubt about DIFFUSE WEAK evidence, and
            # it must not swallow a single overwhelming match. Three
            # participant rows copied into a corpus file scored 13.7 against a
            # background that topped out at 1.37 -- an order of magnitude, and
            # capping it would have hidden the one thing the tool exists to
            # find. Findings far above the ladder keep their severity; the
            # rest are capped, and the caveat still says the file reads oddly.
            survivors = [
                g for g in duplicate_groups if g.get("adjusted_score", 0.0) >= _DIFFUSE_EXEMPT_SCORE
            ]
            diffuse_capped = True
            for g in duplicate_groups:
                if g in survivors:
                    continue
                if _TIERS.index(g["severity"]) < _TIERS.index(INDETERMINATE):
                    g["severity"] = INDETERMINATE
                    g["diffuse_capped"] = True
            top = (
                min((g["severity"] for g in duplicate_groups), key=_TIERS.index)
                if duplicate_groups
                else INDETERMINATE
            )

    caveats.append(
        "Duplication is improbable, not mathematically impossible; identical "
        "records can be legitimate (repeated measures, shared covariates). "
        "The editorial stage must confirm the rows describe supposedly "
        "DIFFERENT observations, and whether the flagged columns feed any "
        "reported result."
    )
    if context_capped and cap_reason == "pooled":
        caveats.append(
            "data_context=pooled_or_meta_analysis: rows compiled from other "
            "sources duplicate BY CONSTRUCTION; severity capped at "
            "indeterminate."
        )
    elif context_capped and cap_reason == "statistical_output":
        caveats.append(
            "Headers (Beta/SE/t/p/R-squared) say this is MODEL OUTPUT, not "
            "participant-level data. An R-squared or a clamped adjusted p "
            "repeats across a model's rows BY CONSTRUCTION, so severity is "
            "capped at indeterminate. Point this tool at the raw data file "
            "instead; pass exclude_columns if the inference is wrong."
        )
    elif context_capped and cap_reason == "aggregate":
        caveats.append(
            "Headers (counts/percentages/means) say this is an AGGREGATE "
            "table, not participant-level data. Binned counts repeat across "
            "bins by nature; severity capped at indeterminate."
        )
    if diffuse_capped:
        caveats.append(
            "Findings are spread across most of this file's columns. "
            "Copy-paste is local; evidence this diffuse more often means the "
            "file's format or instrument was misread than that every variable "
            "was fabricated. Severity capped at indeterminate — read "
            "'by_column' and exclude the columns that are shared by design."
        )
    if data_context == "unknown":
        caveats.append(
            "data_context is unknown. If this file pools data from other "
            "papers (meta-analysis), duplicated rows are expected — re-run "
            "with data_context='pooled_or_meta_analysis'."
        )

    # ---- by-column rollup --------------------------------------------------
    # 6,420 groups is unreadable, and it hides that they come from ~9 columns.
    # A reader who can see "OE_1_Task_0_GROUP: 4,102 groups, 6 distinct values"
    # dismisses the whole block at a glance instead of paging through cell refs.
    by_column: Counter = Counter()
    for g in duplicate_groups:
        for n in _group_columns(g):
            by_column[n] += 1
    column_summary = [{"column": n, "n_groups": k} for n, k in by_column.most_common(30)]

    n_excluded = len(excluded)
    counts = Counter(g["kind"] for g in duplicate_groups)

    # SAY GROUPS WHEN IT IS GROUPS. Each figure below counts a different
    # object, and the old wording ("N duplicated row pair(s)") named the first
    # one after the second.
    n_rowpair_groups = counts.get("row_pair", 0)
    n_rowpairs = len(qualifying_pairs)
    n_rows_impl = len(implicated_rows)
    total_rows = sum(len(s.rows) for s in segments) or 1
    rows_by_sheet: Counter = Counter(segments[s_i].label for (s_i, _r) in implicated_rows)
    groups_by_sheet: Counter = Counter()
    for g in duplicate_groups:
        if g.get("kind") == "row_pair":
            groups_by_sheet[g.get("sheet_a", "?")] += 1

    if duplicate_groups:
        explanation = (
            f"{n_rowpair_groups} row-pair group(s) covering {n_rowpairs} "
            f"row pair(s) and {n_rows_impl} of {total_rows} row(s) "
            f"({100.0 * n_rows_impl / total_rows:.1f}%); "
            f"{counts.get('column_sequence', 0)} repeated column sequence(s); "
            f"{counts.get('repeated_value', 0)} repeated high-precision "
            f"value(s). Across {len(segments)} table(s): "
            + ", ".join(f"{lbl} {k}" for lbl, k in groups_by_sheet.most_common())
            + ". A row-pair GROUP merges every pair sharing one match "
            "signature, so it is a count of phenomena, not of pairs, and "
            "neither is a count of rows."
        )
    else:
        explanation = "No duplicated raw data detected."
    if any(
        "only the first" in c or "not evaluated" in c or "budget" in c and "exhausted" in c
        for c in caveats
    ):
        explanation += " Coverage is PARTIAL; unexamined data may contain additional matches."

    from .storage import digest

    for group in duplicate_groups:
        group["id"] = "CP-" + digest(group)[:24]

    return {
        "severity": top,
        "explanation": explanation,
        "path": str(p),
        "n_tables": len(segments),
        "tables": [s.label for s in segments],
        "n_numeric_cells": n_numeric_total,
        "n_columns_excluded": n_excluded,
        # Named, not hidden: these columns can support a pair but never raise
        # one, and a reader deciding whether to trust a finding needs to know
        # which side of that line each column sat on.
        "corroborating_columns": sorted({_column_name(segments[s], c) for (s, c) in corroborating}),
        "excluded_columns": sorted(
            {f"{_column_name(segments[s], c)} ({reason})" for (s, c), reason in excluded.items()}
        ),
        "duplicate_groups": duplicate_groups,
        "n_duplicate_groups": len(duplicate_groups),
        # The three counts, named. `n_duplicate_groups` above sums all THREE
        # detector kinds, which is why it can exceed the row-pair figure.
        "n_row_pair_groups": n_rowpair_groups,
        "n_row_pairs": n_rowpairs,
        "n_rows_implicated": n_rows_impl,
        "n_rows_total": total_rows,
        "pct_rows_implicated": round(100.0 * n_rows_impl / total_rows, 1),
        "row_pair_groups_by_sheet": dict(groups_by_sheet),
        "rows_implicated_by_sheet": dict(rows_by_sheet),
        "by_column": column_summary,
        "assumptions": {
            "size_normalization": round(norm, 3),
            "matching": "exact equality after float canonicalization; no tolerance matching",
            "data_context": data_context,
        },
        "caveats": caveats,
        "methodology": (
            f"Compared {len(seen_pairs)} candidate row pairs, all vertical "
            f"runs, and value recurrences over {n_numeric_total} numeric cells "
            f"in {len(segments)} table(s); matches weighted by significant-"
            "digit information content with derived-value (fraction/sqrt/log) "
            "and regularity discounts, normalized by "
            f"log10(cells)={round(norm, 2)}. Formula cells are invisible here "
            "(cached values only), so derived columns are handled by the "
            "transform detector and the same-row guard instead."
        ),
    }
