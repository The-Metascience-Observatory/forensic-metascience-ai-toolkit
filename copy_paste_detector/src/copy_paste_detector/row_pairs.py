"""Find matching participant rows, including cross-sheet matches."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Optional

from .constants import (
    _MAX_SEED_OCCURRENCES,
    _MIN_SHARED_COLS,
    _SEED_MIN_DIGITS,
    _TELEMETRY_SEED_DIGITS,
    _TIERS,
)
from .readers import (
    _cell_ref,
)
from .scoring import (
    _line_severity,
)
from .severity import (
    CONSISTENT,
    INDETERMINATE,
    SUSPICIOUS,
)


def _find_row_pairs(
    *,
    _col_count,
    _discounted,
    caveats,
    col_index,
    corroborating,
    duplicate_groups,
    excluded,
    identity_of,
    info,
    max_row_pairs,
    norm,
    occurrences,
    reported_cells,
    segments,
):
    """Append row-pair groups, update reported cells/caveats, and return row counts as sets."""
    # ---- 1. row pairs ----------------------------------------------------
    # Candidate pairs are seeded by informative values sharing a column
    # identity; each candidate pair is then compared across ALL column
    # identities the two rows share.
    row_cells: dict[tuple[int, int], dict[str, tuple[int, float]]] = {}
    for s_idx, seg in enumerate(segments):
        for row_no, numbers in seg.rows:
            per_ident: dict[str, tuple[int, float]] = {}
            for c, v in numbers.items():
                if (s_idx, c) in excluded:
                    continue
                per_ident[identity_of[(s_idx, c)]] = (c, v)
            row_cells[(s_idx, row_no)] = per_ident

    seen_pairs: set[tuple] = set()
    pair_groups: dict[frozenset, dict] = {}  # match signature -> merged group
    pair_rows: dict[frozenset, set] = {}  # match signature -> rows involved
    # GROUPS AND PAIRS ARE DIFFERENT NUMBERS AND USED TO SHARE A NOUN.
    # `pair_groups` merges every pair sharing a match signature, so its length
    # is a count of PHENOMENA. The report called that "N duplicated row
    # pair(s)". MEASURED: on a 193-row workbook the tool said "75 duplicated
    # row pairs" and a reader divided 75 by 193 to get "roughly 39% of rows
    # implicated" -- a group count over a row count. The true figures were 22
    # qualifying pairs across 24 rows, i.e. 12.4%. Track all three separately
    # so no caller has to infer one from another.
    qualifying_pairs: set[tuple] = set()  # (row_a, row_b) that actually matched
    implicated_rows: set[tuple] = set()  # (segment_idx, row_no)
    truncated = False
    for ident, by_value in col_index.items():
        for v, locs in by_value.items():
            if info(locs[0][0], locs[0][2], v) < _SEED_MIN_DIGITS:
                continue
            # Telemetry may seed only at HIGH precision. A shared click count
            # (1.0) or browser build would otherwise nominate half the file;
            # a page-submit time of 226.971s is nobody else's, and in a survey
            # export whose substantive answers are all 1-2 digit Likert codes
            # the timers are the ONLY columns precise enough to identify a
            # recycled record -- refusing to seed on them at any precision
            # made three rows copied into a corpus file undetectable.
            if (
                corroborating.get((locs[0][0], locs[0][2]))
                and info(locs[0][0], locs[0][2], v) < _TELEMETRY_SEED_DIGITS
            ):
                continue
            rows_here = {(s, r) for s, r, _ in locs}
            if not (1 < len(rows_here) <= _MAX_SEED_OCCURRENCES):
                continue
            for ra, rb in combinations(sorted(rows_here), 2):
                key = (ra, rb)
                if key in seen_pairs:
                    continue
                if max_row_pairs and len(seen_pairs) >= max_row_pairs:
                    truncated = True
                    break
                seen_pairs.add(key)
                cells_a, cells_b = row_cells[ra], row_cells[rb]
                shared: dict[float, list[str]] = {}
                shared_cols: list[tuple[str, float]] = []
                n_substantive = 0
                for ident2 in sorted(cells_a.keys() & cells_b.keys()):
                    ca, va = cells_a[ident2]
                    _, vb = cells_b[ident2]
                    if va == vb and va != 0:
                        shared_cols.append((ident2, va))
                        shared.setdefault(va, []).append(ident2)
                        if (
                            not corroborating.get((ra[0], ca))
                            or info(ra[0], ca, va) >= _TELEMETRY_SEED_DIGITS
                        ):
                            n_substantive += 1
                if len(shared_cols) < _MIN_SHARED_COLS:
                    continue
                # A pair carried entirely by LOW-precision telemetry is the
                # instrument agreeing with itself. High-precision timers are
                # different: matching to the millisecond is the signature, not
                # the noise.
                if not n_substantive:
                    continue
                # Distinct values only (one number repeated across five
                # columns is one fact, not five), each discounted by how
                # common it is in its column.
                score = 0.0
                pair_min_cnt: Optional[int] = None
                for val, ids in shared.items():
                    cnt = min(_col_count(i2, val) for i2 in ids)
                    pair_min_cnt = cnt if pair_min_cnt is None else min(pair_min_cnt, cnt)
                    score += _discounted(info(ra[0], cells_a[ids[0]][0], val), cnt)
                adjusted = score / norm
                sev = _line_severity(adjusted)
                # Block-structure cap: when even the RAREST matched value is
                # carried by >= 4 rows of its column, this pair sits inside
                # value BLOCKS — the shape site/plot-level covariates produce
                # BY DESIGN (several high-precision numbers shared by every
                # row of a site). Mirrors the repeated_value single-column
                # ladder (>=4 caps at suspicious, >=8 at indeterminate). A
                # genuinely copied pair keeps count-2 values and is untouched.
                block_capped = False
                if pair_min_cnt is not None and pair_min_cnt >= 4:
                    cap = INDETERMINATE if pair_min_cnt >= 8 else SUSPICIOUS
                    if _TIERS.index(sev) < _TIERS.index(cap):
                        sev = cap
                        block_capped = True
                # Chance gate (CLEARING only). Independence underestimates
                # joint match probability when columns correlate, so a large
                # expected count is still a reason to drop; a small one is
                # not a reason to escalate. Unique-to-the-pair values
                # (rarest matched value on exactly 2 rows) are skipped:
                # expected coincidences are ~0 by construction.
                chance_expected = None
                if sev != CONSISTENT and pair_min_cnt is not None and pair_min_cnt > 2:
                    n_sheet = max(len(segments[ra[0]].rows), len(segments[rb[0]].rows))
                    expected = n_sheet * (n_sheet - 1) / 2.0
                    for ident2, val in shared_cols:
                        n_col = n_sheet
                        cnt = _col_count(ident2, val)
                        expected *= (cnt / n_col) if n_col else 1.0
                    chance_expected = expected
                    if expected > 0.5:
                        sev = CONSISTENT
                    elif expected > 0.05 and _TIERS.index(sev) < _TIERS.index(INDETERMINATE):
                        sev = INDETERMINATE
                if sev == CONSISTENT:
                    continue
                seg_a, seg_b = segments[ra[0]], segments[rb[0]]
                for ident2, val in shared_cols:
                    reported_cells.add((ra[0], ra[1], cells_a[ident2][0]))
                    reported_cells.add((rb[0], rb[1], cells_b[ident2][0]))
                # Merge pairs with the SAME matched (column, value) set: k rows
                # sharing one block of values is one phenomenon, not C(k,2).
                sig = frozenset(shared_cols)
                grp = pair_groups.get(sig)
                if grp is None:
                    grp = pair_groups[sig] = {
                        "kind": "row_pair",
                        "cross_sheet": ra[0] != rb[0],
                        "sheet_a": seg_a.label,
                        "sheet_b": seg_b.label,
                        "rows": [],
                        "cells": [],
                        "n_shared_columns": len(shared_cols),
                        "n_distinct_values": len(shared),
                        "shared": [
                            {
                                "column": ident2,
                                "value": val,
                                "occurrences_in_file": occurrences[val],
                                "occurrences_in_column": _col_count(ident2, val),
                            }
                            for ident2, val in sorted(shared_cols)
                        ],
                        "information_score": round(score, 2),
                        "adjusted_score": round(adjusted, 2),
                        "severity": sev,
                        "column_mass_capped": block_capped,
                        "chance_expected_pairs": (
                            None if chance_expected is None else round(chance_expected, 4)
                        ),
                    }
                grp["cross_sheet"] = grp["cross_sheet"] or ra[0] != rb[0]
                pair_rows.setdefault(sig, set()).update((ra, rb))
                qualifying_pairs.add((ra, rb))
                implicated_rows.update((ra, rb))
                for s_i, r_no in (ra, rb):
                    row_map = cells_a if (s_i, r_no) == ra else cells_b
                    ref = _cell_ref(segments[s_i], r_no, row_map[shared_cols[0][0]][0])
                    if ref not in grp["rows"]:
                        grp["rows"].append(ref)
                        for ident2, _val in shared_cols:
                            cref = _cell_ref(segments[s_i], r_no, row_map[ident2][0])
                            grp["cells"].append(cref)
            if truncated:
                break
        if truncated:
            break
    # Matched-design cap: MANY row pairs (>= 5) matching on the SAME column
    # set and covering most (>= 50%) of the involved tables' rows is the
    # shape of a matched/stratified/dyadic design, long-format repeat visits,
    # or a table present twice — as much as of copy-paste. Refuse to accuse;
    # name the structure so the editorial stage can judge the study design.
    fam: dict[frozenset, list] = defaultdict(list)
    for sig in pair_groups:
        fam[frozenset(ident for ident, _ in sig)].append(sig)
    for col_set, sigs in fam.items():
        if len(sigs) < 5:
            continue
        involved: set = set().union(*(pair_rows[s] for s in sigs))
        seg_ids = {s for s, _ in involved}
        seg_rows = sum(len(segments[s].rows) for s in seg_ids)
        if seg_rows and len(involved) >= 0.5 * seg_rows:
            capped_here = False
            for s in sigs:
                grp = pair_groups[s]
                if _TIERS.index(grp["severity"]) < _TIERS.index(INDETERMINATE):
                    grp["severity"] = INDETERMINATE
                    grp["design_structure_capped"] = True
                    capped_here = True
            if capped_here:
                caveats.append(
                    f"{len(sigs)} row pairs match on the same column set "
                    f"({sorted(col_set)}) and cover {len(involved)} of "
                    f"{seg_rows} rows in the involved table(s): that is the "
                    "shape of a matched/paired design, long-format repeated "
                    "measures, or one table present twice, as much as of "
                    "copy-paste; severity capped at indeterminate — confirm "
                    "the study design before treating this as evidence"
                )
    duplicate_groups.extend(pair_groups.values())
    if truncated:
        # SAY WHICH WAY IT IS WRONG. "Coverage is PARTIAL" was read as "the
        # number could be anything", and a reader combined it with a group
        # count to argue the true figure was higher still. Truncation halts the
        # search, so it can only ever MISS pairs: the reported count is a floor
        # on this tool's own loose criterion, and says nothing about rows.
        caveats.append(
            f"row-pair comparison budget ({max_row_pairs}) exhausted; coverage "
            "is PARTIAL and the row-pair counts are an UNDER-count (the search "
            "stopped early, so it can only have missed pairs, never invented "
            "them). Raise max_row_pairs for a complete sweep."
        )

    return implicated_rows, qualifying_pairs, seen_pairs
