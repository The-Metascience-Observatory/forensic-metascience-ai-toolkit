"""Find repeated vertical runs after row-pair detection."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from .constants import (
    _CATEGORICAL_COUNT_RATIO,
    _CATEGORICAL_MAX_DISTINCT,
    _MIN_RUN,
    _TIERS,
)
from .readers import (
    _cell_ref,
)
from .scoring import (
    _line_severity,
    _regularity,
)
from .screening import (
    _column_identity,
    _column_name,
)
from .severity import (
    CONSISTENT,
    INDETERMINATE,
)


def _find_column_sequences(
    *, diversity, duplicate_groups, excluded, info, norm, reported_cells, segments
):
    """Append sequence groups and reserve their cells after the row-pair stage."""
    # ---- 2. repeated column sequences -------------------------------------
    # A vertical run of >= _MIN_RUN consecutive values reappearing (same
    # column, another column, or another sheet). Same-row matches across two
    # columns never seed: two columns holding one measurement's raw and
    # derived form legitimately co-vary row-by-row.
    # A column cycling through a handful of codes reproduces its own runs by
    # combinatorial necessity -- with 6 values, some 3-long run repeats within
    # a few hundred rows no matter who typed it. `_regularity` cannot see this
    # (the diffs are irregular), so such columns do not seed runs at all.
    col_series: dict[tuple[int, int], list[tuple[int, float]]] = defaultdict(list)
    for s_idx, seg in enumerate(segments):
        for row_no, numbers in seg.rows:
            for c, v in numbers.items():
                key = (s_idx, c)
                if key in excluded:
                    continue
                div = diversity.get(key, 10**9)
                if (
                    div <= _CATEGORICAL_MAX_DISTINCT
                    and len(seg.rows) >= _CATEGORICAL_COUNT_RATIO * div
                ):
                    continue
                col_series[key].append((row_no, v))
    # Exact tuples are the index keys: no approximate/hash-only match can
    # become evidence. Missing cells break physical adjacency.
    index = defaultdict(list)
    for key, series in sorted(col_series.items()):
        for i in range(len(series) - _MIN_RUN + 1):
            window = series[i : i + _MIN_RUN]
            if any(b[0] != a[0] + 1 for a, b in zip(window, window[1:])):
                continue
            if window[0][1] == 0 or info(key[0], key[1], window[0][1]) < 1:
                continue
            index[tuple(v for _, v in window)].append((key, i))
    seeds = defaultdict(lambda: defaultdict(set))
    for occurrences in index.values():
        for (ka, i), (kb, j) in combinations(occurrences, 2):
            source_a, source_b = segments[ka[0]].source, segments[kb[0]].source
            if (
                source_a
                and source_b
                and source_a["file"] != source_b["file"]
                and _column_identity(segments[ka[0]], ka[0], ka[1])
                != _column_identity(segments[kb[0]], kb[0], kb[1])
            ):
                continue
            if ka == kb and j < i + _MIN_RUN:
                continue
            if ka != kb and ka[0] == kb[0] and col_series[ka][i][0] == col_series[kb][j][0]:
                continue
            seeds[(ka, kb)][i].add(j)
    seen_runs: set[tuple] = set()

    def _runs_between(ka: tuple[int, int], kb: tuple[int, int], starts) -> None:
        sa, sb = col_series[ka], col_series[kb]
        # Chance null for runs (the sequence-side mirror of the repeated-value
        # Poisson gate): with per-cell collision probability q between these
        # two columns' empirical value distributions, ~len(sa)*len(sb)*q^L
        # alignments of length L arise by chance. Low-cardinality columns
        # (Likert scores, 1-dp temperatures, heaped integers) produce short
        # matching runs by pigeonhole; those are not evidence. For a column
        # against itself this overcounts alignments by <= 2x, which only
        # REFUSES more.
        count_a = Counter(v for _, v in sa)
        count_b = Counter(v for _, v in sb)
        n_ab = len(sa) * len(sb)
        collide = sum(count_a[v] * count_b.get(v, 0) for v in count_a) / n_ab if n_ab else 0.0
        next_i = 0
        for i in sorted(starts):
            if i < next_i:
                continue
            v = sa[i][1]
            if v == 0 or info(ka[0], ka[1], v) < 1:
                i += 1
                continue
            best_len = 0
            best_j = -1
            for j in sorted(starts[i]):
                if ka == kb and i == j:
                    continue
                # same-row guard for distinct columns of one segment
                if ka != kb and ka[0] == kb[0] and sa[i][0] == sb[j][0]:
                    continue
                if ka == kb and j < i:
                    continue
                length = 0
                while (
                    i + length < len(sa)
                    and j + length < len(sb)
                    and not (ka == kb and i + length == j)
                    and sa[i + length][1] == sb[j + length][1]
                    and sa[i + length][0] == sa[i][0] + length
                    and sb[j + length][0] == sb[j][0] + length
                ):
                    length += 1
                if length > best_len:
                    best_len, best_j = length, j
            if best_len >= _MIN_RUN:
                run_key = (ka, i, kb, best_j, best_len)
                mirror = (kb, best_j, ka, i, best_len)
                if run_key not in seen_runs and mirror not in seen_runs:
                    seen_runs.add(run_key)
                    values = [sa[i + t][1] for t in range(best_len)]
                    raw = sum(max(0, info(ka[0], ka[1], u) - 1) for u in set(values))
                    reg = _regularity(values)
                    adjusted = raw * (1.0 - reg) / norm
                    sev = _line_severity(adjusted)
                    expected_runs = n_ab * collide**best_len
                    if expected_runs > 0.5:
                        sev = CONSISTENT  # a run this likely is chance
                    elif expected_runs > 0.05 and _TIERS.index(sev) < _TIERS.index(INDETERMINATE):
                        sev = INDETERMINATE
                    if sev != CONSISTENT:
                        seg_a, seg_b = segments[ka[0]], segments[kb[0]]
                        for t in range(best_len):
                            reported_cells.add((ka[0], sa[i + t][0], ka[1]))
                            reported_cells.add((kb[0], sb[best_j + t][0], kb[1]))
                        duplicate_groups.append(
                            {
                                "kind": "column_sequence",
                                "cross_sheet": ka[0] != kb[0],
                                "column_a": _column_name(seg_a, ka[1]),
                                "column_b": _column_name(seg_b, kb[1]),
                                "sheet_a": seg_a.label,
                                "sheet_b": seg_b.label,
                                "start_a": _cell_ref(seg_a, sa[i][0], ka[1]),
                                "start_b": _cell_ref(seg_b, sb[best_j][0], kb[1]),
                                "cells_a": [
                                    _cell_ref(seg_a, sa[i + t][0], ka[1]) for t in range(best_len)
                                ],
                                "cells_b": [
                                    _cell_ref(seg_b, sb[best_j + t][0], kb[1])
                                    for t in range(best_len)
                                ],
                                "length": best_len,
                                "values": values,
                                "regularity": round(reg, 3),
                                "chance_expected_runs": round(expected_runs, 4),
                                "information_score": round(raw, 2),
                                "adjusted_score": round(adjusted, 2),
                                "severity": sev,
                            }
                        )
                next_i = i + max(best_len, 1)
            else:
                i += 1

    for (ka, kb), starts in sorted(seeds.items()):
        _runs_between(ka, kb, starts)
