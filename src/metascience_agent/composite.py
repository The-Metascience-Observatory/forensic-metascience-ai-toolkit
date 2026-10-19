"""Split a composite table into its sections, and recover each section's n.

THE PROBLEM, found by Greg 2026-08-10 in a real bundle. Journals routinely print
several logical tables as one physical table, separated by a banner row that
repeats a section name across every column:

    Gender          Gender       Gender      Gender     ...
    Female          1254 (44.31) 646 (49.96) ...        180.74**
    Male            1576 (55.69) 647 (50.04) ...
    Age group       Age group    Age group   Age group  ...
    25 and under    229 (8.09)   90 (6.96)   ...        900.21**

A human reads that as four tables. The pipeline read it as one, and MEASURED on
10.1038/s41537-025-00576-3 Table 2: 73 rows, TWELVE section banners consuming 72
of 389 cells (19%), and `check_table` ran 0 checks and refused all 389 -- 244 of
them with "grim_percentage needs n and this cell carries none".

THE POINT IS NOT TIDINESS. THE SECTION IS WHERE THE DENOMINATOR LIVES.
Within a section the categories are exhaustive, so the counts sum to n -- which
is exactly the number `grim_percentage` was refusing for want of. Verified on
that table: Gender 1254 + 1576 = 2830, Age group 229 + 441 + 736 + 1034 + 390 =
2830, Ethnic group 2646 + 184 = 2830, and every printed percentage matches k/n
to the last digit. Splitting the table turns a wholly unusable 389-cell blob
into sections whose n is recoverable.

WHY THIS DOES NOT MANUFACTURE ACCUSATIONS, which is the only question that
matters when a derived quantity is about to feed a forensic check. The derived n
is CHECKED AGAINST THE PAPER'S OWN PERCENTAGES before it is used: the section's
percentages must sum to ~100, and every printed percentage must match its own
count over the derived n. If either fails, the section is returned with `n=None`
and a stated reason, and no check runs on it. A denominator we inferred and
could not confirm is worth strictly less than no denominator at all, because a
wrong n is the fastest route to a false `impossible` -- see
`docs/GRIM_CONTEXT_DEPENDENCY.md`, mechanism 18.

The self-check has teeth. While developing this I truncated the Marital status
section by one row; the percentages summed to 82.54% and every derived
percentage disagreed with the printed one. The rule caught my own mistake before
it reached a tool, which is the behaviour it exists for.

WHAT THIS DELIBERATELY DOES NOT DO. It does not attribute the section-level test
statistic. In the source, `180.74**` sits on a rowspan covering the whole Gender
block, and the extractor hands it to the FIRST row -- so a naive reader pairs
chi-square 180.74 with "Female" rather than with "Gender". That is a real
misattribution and it is recorded per section as `section_statistic` rather than
left attached to a row, but nothing here decides what it tests.
"""
from __future__ import annotations

import re
from typing import Any

#: A section's percentages must sum to this, within tolerance, for its derived
#: denominator to be trusted. Rounding of k values each to 2 dp can move the sum
#: by a few hundredths; 0.6 accommodates a dozen rows without admitting a table
#: that is genuinely missing one.
_PCT_SUM_TOLERANCE = 0.6

#: Each printed percentage must match k/n to within this, in points. One unit in
#: the last place of a 2-dp percentage is 0.005; doubled for the round-half vs
#: truncation ambiguity the rest of the toolkit already accommodates.
_PCT_CELL_TOLERANCE = 0.011

_COUNT_PCT = re.compile(r"^\s*([\d\s,]+?)\s*\(\s*([\d.]+)\s*%?\s*\)")

#: THE SLASH FORM, which `celltypes` already types `split_n_percent`:
#: `587 / 99.5%`. This module read only `587 (99.5)`, so on a table printed the
#: other way it derived nothing, validated nothing, and its disagreement guard
#: never fired. MEASURED 2026-08-20: two false accusations survived precisely
#: there -- `check_count_percent` used a column-header n that this module would
#: have rejected, had it been able to read the cells at all.
#:
#: A percent SIGN is required, unlike the parenthesised form. `587 / 99.5%` is
#: a count and a percentage; `12 / 30` is a fraction, and reading the 30 as a
#: percentage would invent a denominator. The sign is what distinguishes them.
_COUNT_SLASH_PCT = re.compile(r"^\s*([\d\s,]+?)\s*/\s*([\d.]+)\s*%")


def _count_and_pct(raw: Any) -> tuple[int, float] | None:
    text = str(raw or "")
    m = _COUNT_PCT.match(text) or _COUNT_SLASH_PCT.match(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", "").replace("", "")), float(m.group(2))
    except ValueError:
        return None


#: Typographic conventions for "no value here". A row of these is DATA THAT IS
#: MISSING, not a heading -- and the two are indistinguishable to the
#: all-cells-identical rule, because extraction/jats.py drops the label column
#: and skips empty cells, so `Comorbidity | NR | NR | NR` arrives as three
#: identical non-numeric cells. It was then classified as a banner: the row's
#: data was dropped from the section entirely, and a section LABELLED "NR" was
#: opened and published. Section membership gates denominator recovery, so the
#: loss reaches grim_percentage and check_count_percent.
#:
#: A closed list is the right instrument here, unlike the negation lists this
#: codebase has had to abandon elsewhere: these are a small, standard set of
#: printing conventions rather than an open class of English phrasings, and an
#: unrecognised marker simply leaves the previous behaviour in place.
_MISSING_MARKERS = frozenset({
    "nr", "n/r", "na", "n/a", "n.a.", "nd", "n/d", "ns", "n/s",
    "not reported", "not available", "not applicable", "not done",
    "not assessed", "not tested", "not measured", "none", "missing",
    "unknown", "-", "--", "---", "\u2013", "\u2014", ".", "..", "?", "*",
})


def _is_missing_marker(text: str) -> bool:
    """Is this cell a "no value here" placeholder rather than a label?"""
    return str(text or "").strip().strip("*\u2020\u2021\u00a7\u00b6").lower() in _MISSING_MARKERS


def _is_stub_band(row_cells: list[dict], table_width: int) -> bool:
    """A band printed as a label in column 0 with the rest of the row empty.

    THE OTHER HALF OF THE SAME THING. `_is_banner` finds the shape where the
    section name is repeated across every column. Clinical tables far more often
    print it once, with the row otherwise blank -- `Sex, n (%)`,
    `Radiotherapy history`, `NIHSS (M, IQR)` -- and `extraction/jats.py` skips
    empty cells, so such a row ARRIVES AS ONE CELL in a table that is several
    columns wide.

    Without this, a table of stub-banded sub-questions is one section: every
    sub-question's percentages are summed together, the total lands far from
    100, and `_derive_n` rejects the column for "categories not exhaustive".
    Nothing is derived, so nothing disagrees, so the guard against a wrong
    header n never fires. MEASURED 2026-08-20: that is exactly how two false
    accusations survived on honest papers.

    `table_width` is required, and the one-cell rule applies only where the
    table is wider than one column -- the same reason `_is_banner` demands two
    cells. In a genuinely one-column table every row is a lone label and
    treating them as bands would delete the table.
    """
    if table_width < 2 or len(row_cells) != 1:
        return False
    only = str(row_cells[0].get("raw") or "").strip()
    if not only or _is_missing_marker(only):
        return False
    return _count_and_pct(only) is None and not _numeric(only)


def _is_banner(row_cells: list[dict]) -> bool:
    """A row whose every cell carries the same non-numeric text is a section
    banner, not data. Requires >=2 cells: a one-column table has no banners, and
    treating its single label column as one would delete the table.

    Except when that text is a MISSING-DATA MARKER -- see `_MISSING_MARKERS`.
    A repeated "NR" says the row's values were not reported; it does not say
    the row is a heading.
    """
    if len(row_cells) < 2:
        return False
    vals = {str(c.get("raw") or "").strip() for c in row_cells}
    if len(vals) != 1:
        return False
    only = next(iter(vals))
    if _is_missing_marker(only):
        return False
    return bool(only) and _count_and_pct(only) is None and not _numeric(only)


def _numeric(s: str) -> bool:
    try:
        float(str(s).replace(",", "").rstrip("*†‡§¶"))
        return True
    except ValueError:
        return False


def split_sections(cells: list[dict]) -> list[dict]:
    """Split a table's cells into sections at each banner row.

    Returns one dict per section: `label`, `cells` (banner excluded), `n`, the
    `n_source`, and `why_not` when a denominator could not be verified. A table
    with no banners comes back as a single section labelled `None`, so callers
    need no special case.
    """
    by_row: dict[Any, list[dict]] = {}
    for c in cells or []:
        by_row.setdefault(c.get("row"), []).append(c)

    # The widest row is the table's width. A stub band is a ONE-cell row in a
    # table wider than that, which cannot be judged from the row alone.
    table_width = max((len(v) for v in by_row.values()), default=0)

    sections: list[dict] = []
    current = {"label": None, "cells": [], "section_statistic": None}
    for ri in sorted(by_row, key=lambda r: (r is None, r)):
        row = sorted(by_row[ri], key=lambda c: c.get("col") or 0)
        if _is_banner(row) or _is_stub_band(row, table_width):
            if current["cells"]:
                sections.append(current)
            current = {"label": str(row[0].get("raw") or "").strip(),
                       "cells": [], "section_statistic": None}
            continue
        current["cells"].extend(row)
    if current["cells"] or not sections:
        sections.append(current)

    for s in sections:
        s.update(_derive_n(s["cells"]))
    return sections


#: See `dispatch._EQ`: older Springer PDFs encode `=` as `¼`, so `n = 68`
#: arrives as `n ¼ 68`. Repaired only between an `n` and a digit, where the
#: character can mean nothing else.
_HEADER_N = re.compile(r"\bn\s*[=\u00bc]\s*([\d,]+)")


def _derive_n(cells: list[dict]) -> dict:
    """Recover a denominator PER COLUMN, and verify each one.

    ONE DENOMINATOR PER COLUMN, not one per section. Every column of a
    cross-tabulated table is its own population -- "Overall", then one per
    subgroup -- so a section has as many denominators as it has columns.
    Summing across them produces a number belonging to nothing: measured on
    10.1038/s41537-025-00576-3 Table 2, doing so made every section's
    percentages sum to ~500 rather than 100, because there were five data
    columns. The 500 was the guard catching my own error before it reached a
    tool, which is what it is for.

    Columns are identified by `col_label`, because the JATS extractor emits
    cells keyed `raw/row/row_label/col_label` with NO column index. Assuming an
    index that is not there is how the first version summed everything.

    Where the column header states its own n -- "Low-risk CVDs (n = 1293)" is
    the common form -- the derived value is checked against it. Agreement is a
    second, independent confirmation; disagreement rejects the column outright,
    because two sources for one number that differ mean we understand neither.
    """
    if not cells:
        return {"n_by_column": {}, "n": None, "why_not": "no data cells"}

    by_col: dict[str, list[dict]] = {}
    for c in cells:
        by_col.setdefault(str(c.get("col_label") or ""), []).append(c)

    out: dict[str, dict] = {}
    for label, col_cells in by_col.items():
        # The CONTRIBUTING cells are kept, not just their numbers. A denominator
        # is only known to belong to the cells that were summed to make it: a
        # `mean (SD)` row printed inside an otherwise categorical section did
        # not contribute a count, and its own n may be smaller for missing data.
        # Handing it the section total is a false `impossible` waiting to
        # happen, so a caller needs to know which cells the n actually covers.
        pairs = [(c, kp) for c, kp in
                 ((c, _count_and_pct(c.get("raw"))) for c in col_cells) if kp]
        usable = [kp for _, kp in pairs]
        if len(usable) < 2:
            out[label] = {"n": None, "contributing": [],
                          "why_not": "fewer than two `count (percent)` cells"}
            continue

        n = sum(k for k, _ in usable)
        pct_sum = sum(p for _, p in usable)
        if abs(pct_sum - 100.0) > _PCT_SUM_TOLERANCE:
            out[label] = {"n": None, "contributing": [], "why_not": (
                f"percentages sum to {pct_sum:.2f}, not 100 -- rows are missing or the "
                "categories are not exhaustive, so the counts do not sum to a denominator")}
            continue

        bad = [f"{k}/{n} = {100 * k / n:.2f} but the paper prints {p:.2f}"
               for k, p in usable if abs(100 * k / n - p) > _PCT_CELL_TOLERANCE]
        if bad:
            out[label] = {"n": None, "contributing": [], "why_not": (
                "the derived denominator does not reproduce the paper's own percentages "
                f"({len(bad)} of {len(usable)} disagree; first: {bad[0]})")}
            continue

        stated = _HEADER_N.search(label)
        if stated:
            want = int(stated.group(1).replace(",", ""))
            if want != n:
                out[label] = {"n": None, "contributing": [], "why_not": (
                    f"the counts sum to {n} but the column header states n = {want}; "
                    "two sources for one denominator disagree, so neither is used"),
                    # THE CELLS THE DISAGREEMENT COVERS. "Neither is used" was
                    # true only of the DERIVED n: dispatch drops that and then
                    # takes the header n from `raw_cell["n"]` unchallenged, so
                    # the column this rejected still got checked against the
                    # number this rejected. Naming the cells lets the caller
                    # refuse them. See `_section_denominators`.
                    "disputed": list(col_cells),
                    "stated": want, "derived": n}
                continue
            out[label] = {"n": n, "contributing": [c for c, _ in pairs], "n_source":
                          "section_counts_verified_against_percentages_AND_header_n"}
            continue

        out[label] = {"n": n, "contributing": [c for c, _ in pairs], "n_source":
                      "section_counts_verified_against_printed_percentages"}

    verified = {k: v["n"] for k, v in out.items() if v.get("n")}
    return {
        "n_by_column": out,
        # Convenience for the common single-population case only. With several
        # columns there is no one `n`, and returning one would invite exactly
        # the wrong-denominator pairing this module exists to prevent.
        "n": next(iter(verified.values())) if len(verified) == 1 else None,
        "why_not": None if verified else "no column yielded a verified denominator",
    }
