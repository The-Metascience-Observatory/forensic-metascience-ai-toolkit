"""Raw-data duplication detector for participant-level supplements.

`detect_duplication` compares SUMMARY statistics ((mean, SD) blocks the model
types in). This tool answers the question that arises one level down: is the
PARTICIPANT-LEVEL data in a supplementary spreadsheet internally duplicated?
It takes a FILE PATH, not cells — a raw grid is thousands of values and the
agent cannot retype it.

Three patterns, each a distinct fabrication/copy-paste signature:
  - row_pair            : two rows share >= 2 identical high-information values
                          in the same columns (a duplicated participant record,
                          possibly with a few digits edited).
  - column_sequence     : a vertical run of >= 3 consecutive values reappears,
                          in order, elsewhere (fill-down / block copy-paste).
  - repeated_value      : one improbably specific number appears more than once
                          (weakest signal; occurrence-weighted).
Row pairs and sequences are also searched ACROSS sheets and segments — recycled
rows between "independent" sheets are the strongest form of the signal.

Evidence is weighted by the INFORMATION CONTENT of the matched numbers, not by
match counts alone: the significant digits of `123.46` matching twice means
something; `100` matching twice means nothing. Values that are secretly derived
(13/3, sqrt(0.30), ln(2), x/8) carry only their source's information and are
discounted, as are whole columns detected as transforms. Sorted/ID/constant
runs are killed by a regularity discount rather than by column classification.

A 33-file corpus sweep flagged 21 of 24 files, none of which survived review,
and the recalibration that followed is worth stating because two of the causes
were the reverse of what they looked like:

  * numbers that never existed. Commas were stripped unconditionally, so the
    survey response "1,2,4,3" (a task ORDER) parsed as the integer 1243 --
    four digits of precision invented from a 4-item permutation.
  * a chance gate that inverted at the far end. `expected_repeats` collapses
    to 0.0 in the tail, so a 4-digit value seen twice was rejected as ordinary
    while the same value seen 2,639 times passed and scored HIGHER. Extreme
    repetition falsifies the uniform-digit model; it does not confirm guilt.
    Columns whose values each recur dozens of times are read as categorical.

The lesson generalises: when a detector fires on most of a corpus it is
usually describing the file FORMAT, not the data. Guards added since (survey
telemetry, text columns with a numeric minority, model-output files, the
same-row guard for repeated values, and a diffuse-evidence cap) all exclude or
cap; none of them accuses, and each names itself in `excluded_columns` or
`caveats` so a reader can see what was dropped and override it.

Idea provenance: the digit-information weighting, derived-value discounts,
regularity discount and occurrence weighting follow the approach published for
inspection in Markus Englund's `copy-paste-detective` (source-available, all
rights reserved); this module is an independent implementation of those IDEAS
in this codebase's idiom, with its own thresholds (pinned by tests) and its own
additions (cross-sheet comparison, in-code misapplication guards).
The underlying principle is Heathers (2025) §"Pursuing internal consistency":
identical records of DIFFERENT facts should not exist.

Severity is capped at `highly_suspicious` — duplication is improbable, never
mathematically impossible (rulebook rules 3, 9, 11). Pooled/meta-analytic data
duplicates rows BY CONSTRUCTION, so `data_context="pooled_or_meta_analysis"`
refuses to accuse (capped at `indeterminate`) — the guard lives in code, like
`grim_test(data_type=...)`, because a tool pointed at the wrong data must
REFUSE, not accuse."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from .constants import (
    _CONTEXTS,
    _MAX_ROW_PAIRS,
)
from .readers import (
    _load_segments,
)
from .repeated_values import (
    _find_repeated_values,
)
from .results import (
    _aggregate,
)
from .row_pairs import (
    _find_row_pairs,
)
from .scoring import (
    _info_digits,
    _size_norm,
)
from .screening import (
    _column_identity,
    _column_name,
    _screen_columns,
)
from .sequences import (
    _find_column_sequences,
)
from .severity import (
    INDETERMINATE,
)


def detect_raw_duplication(
    path: str,
    sheet: Optional[str] = None,
    exclude_columns: Optional[list] = None,
    data_context: str = "unknown",
    max_row_pairs: int = _MAX_ROW_PAIRS,
    *,
    limits=None,
) -> dict:
    """Detect duplicated raw data inside a supplementary data file.

    Args:
        path: the supplement (.xlsx/.xlsm/.csv/.tsv/.docx). The tool loads the
            grid itself — do not retype cells.
        sheet: restrict to one worksheet (default: all, capped and announced).
        exclude_columns: column names that are shared BY DESIGN and must not
            count as evidence: IDs, codes, coordinates, dates-as-numbers,
            site/plot/group-level covariates (weather, species constants).
        data_context: 'raw_participant_level' | 'pooled_or_meta_analysis' |
            'unknown'. Pooled/meta-analytic data duplicates rows by
            construction; findings are then capped at `indeterminate`.
        max_row_pairs: comparison budget (truncation is announced).

    Returns:
        dict with severity (capped at highly_suspicious), duplicate_groups
        (kinds row_pair / column_sequence / repeated_value, each with cell
        references and sheet-wide occurrence counts), caveats, assumptions,
        methodology.
    """
    if data_context not in _CONTEXTS:
        return {
            "error": f"data_context must be one of {list(_CONTEXTS)}, got {data_context!r}",
            "severity": INDETERMINATE,
        }
    if isinstance(exclude_columns, str):
        # A bare string would iterate as characters and the exclusion the
        # caller EXPLICITLY declared would be silently ignored — the tool
        # would then accuse the very column the agent excluded.
        exclude_columns = [exclude_columns]
    p = Path(path)
    if not p.exists():
        return {"error": f"file not found: {path}", "severity": INDETERMINATE}

    if isinstance(max_row_pairs, bool) or not isinstance(max_row_pairs, int) or max_row_pairs < 0:
        return {"error": "max_row_pairs must be a nonnegative integer", "severity": INDETERMINATE}
    caveats: list[str] = []
    coverage = {}
    segments = _load_segments(p, sheet, caveats, limits=limits, coverage=coverage)
    if isinstance(segments, dict):
        return segments
    result = _detect_segments(segments, p, caveats, exclude_columns, data_context, max_row_pairs)
    if any("budget" in c and "exhausted" in c for c in caveats):
        coverage["status"] = "partial"
        coverage["omitted"].append("row-pair budget exhausted")
    if result.get("error"):
        coverage["status"] = "not_evaluable"
    result["coverage"] = coverage
    return result


def _detect_segments(segments, p, caveats, exclude_columns, data_context, max_row_pairs):
    segments = [s for s in segments if s.rows]
    if not segments:
        return {
            "severity": INDETERMINATE,
            "error": "no numeric data rows found in the file",
            "explanation": "Nothing to compare: the file contains no rows with numeric cells.",
        }
    if sum(len(seg.rows) for seg in segments) < 2:
        return {
            "severity": INDETERMINATE,
            "error": "only one numeric data row found; duplication needs at "
            "least two rows to compare",
            "explanation": "Nothing to compare. This is a refusal, not a clean bill.",
        }

    (excluded, capped, notes, diversity, corroborating) = _screen_columns(segments, exclude_columns)
    caveats.extend(notes)
    n_numeric_total = sum(seg.n_numeric for seg in segments)
    norm = _size_norm(n_numeric_total)

    def info(s_idx: int, col: int, v: float) -> int:
        if capped.get((s_idx, col)):
            return min(_info_digits(v), 1)
        return _info_digits(v)

    # ---- occurrence counts (per column-identity and global), and the
    # ---- inverted index that seeds row-pair candidates -------------------
    occurrences: Counter = Counter()  # value -> global count
    col_index: dict[str, dict[float, list[tuple[int, int, int]]]] = defaultdict(
        lambda: defaultdict(list)
    )  # identity -> value -> [(seg, row_no, col)]
    identity_of: dict[tuple[int, int], str] = {}

    for s_idx, seg in enumerate(segments):
        for row_no, numbers in seg.rows:
            for c, v in numbers.items():
                if (s_idx, c) in excluded:
                    continue
                occurrences[v] += 1
                ident = identity_of.setdefault((s_idx, c), _column_identity(seg, s_idx, c))
                col_index[ident][v].append((s_idx, row_no, c))

    if not occurrences:
        return {
            "severity": INDETERMINATE,
            "error": "every numeric column was excluded from comparison "
            "(constant / ID-run / caller-excluded); nothing "
            "comparable remains",
            "excluded_columns": sorted(
                {
                    f"{_column_name(segments[s], c)} ({reason})"
                    for (s, c), reason in excluded.items()
                }
            ),
            "explanation": "No comparable values. This is a refusal, not a clean bill.",
            "caveats": caveats,
        }

    duplicate_groups: list[dict] = []
    reported_cells: set[tuple[int, int, int]] = set()  # (seg, row_no, col)

    def _col_count(ident: str, v: float) -> int:
        """How many cells of this column identity hold this value."""
        return len(col_index[ident].get(v, ()))

    def _discounted(d: int, cnt: int) -> float:
        """A value's information contribution, discounted by how common it is
        in its column. A number 20 rows share is a site-level covariate
        (weather, species constant), not 20 copy-pastes: the more rows carry
        it, the less any one coincidence proves. Count-2 values (a genuine
        pair) keep full weight."""
        excess = math.log2(cnt - 1) if cnt >= 3 else 0.0
        return max(0.0, (d - 1) - excess)

    implicated_rows, qualifying_pairs, seen_pairs = _find_row_pairs(
        _col_count=_col_count,
        _discounted=_discounted,
        caveats=caveats,
        col_index=col_index,
        corroborating=corroborating,
        duplicate_groups=duplicate_groups,
        excluded=excluded,
        identity_of=identity_of,
        info=info,
        max_row_pairs=max_row_pairs,
        norm=norm,
        occurrences=occurrences,
        reported_cells=reported_cells,
        segments=segments,
    )

    _find_column_sequences(
        diversity=diversity,
        duplicate_groups=duplicate_groups,
        excluded=excluded,
        info=info,
        norm=norm,
        reported_cells=reported_cells,
        segments=segments,
    )

    _find_repeated_values(
        col_index=col_index,
        corroborating=corroborating,
        diversity=diversity,
        duplicate_groups=duplicate_groups,
        identity_of=identity_of,
        info=info,
        norm=norm,
        occurrences=occurrences,
        reported_cells=reported_cells,
        segments=segments,
    )

    return _aggregate(
        caveats=caveats,
        corroborating=corroborating,
        data_context=data_context,
        diversity=diversity,
        duplicate_groups=duplicate_groups,
        excluded=excluded,
        implicated_rows=implicated_rows,
        n_numeric_total=n_numeric_total,
        norm=norm,
        p=p,
        qualifying_pairs=qualifying_pairs,
        seen_pairs=seen_pairs,
        segments=segments,
    )
