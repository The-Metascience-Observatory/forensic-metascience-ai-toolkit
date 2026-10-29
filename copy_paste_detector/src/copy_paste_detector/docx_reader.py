"""Focused Word-table reader preserving the detector's historical input grid.

The normalization helpers originate in the toolkit's JATS and
supplement readers. Parity tests cover this intentionally independent subset.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_ONLY_A_NUMBER = re.compile(r"^[\s(\[]*[-+\u2212]?\d[\d,.]*\s*[%)\]]?\s*$")


_ONLY_A_MARK = re.compile(r"^\s*[-+\u2212\u2013\u2014\u00b1*/\u2713xX]{1,2}\s*$")


def _reads_as_measurements(row: list[str]) -> bool:
    """Is this grid row data rather than a label row?

    THE ONE BRAKE, shared by both readers that decide a header's depth. Whatever
    proposes a deep header -- span structure on the HTML side, docling's
    `column_header` flags on the PDF side -- a row of measurements is not a
    heading, and promoting one out of the body is how a value stops existing for
    every check downstream. An extractor that mislabels a data row must not be
    able to delete it.

    Two tests, because one was not enough. A heading's stub is never a bare
    number, which is what rejects the `0 / - / +` row on
    `10.1016--j.yexcr.2014.06.020`; and two or more cells that are only a number
    or only a mark make the row data whatever its stub says.
    """
    if not row:
        return False
    if _ONLY_A_NUMBER.match(row[0] or ""):
        return True
    return sum(1 for c in row if _ONLY_A_NUMBER.match(c or "") or _ONLY_A_MARK.match(c or "")) >= 2


def _header_depth(
    source_rows: list[list[tuple[str, int, int, bool]]], grid: list[list[str]], cap: int = 4
) -> int:
    """How many leading rows the MARKUP proves are header. Zero if row 0 is data.

    A cell with ``colspan > 1`` in row *r* is a proof, not a hint: it spans
    columns that row *r* therefore cannot tell apart, so the columns are
    distinguished by a row BELOW it or not at all. Reading such a table with a
    one-row header does not lose a decoration, it loses the column's identity.

    MEASURED over the 36 tables the Mistral extraction found in the 22
    known-damaged cerebrolysin papers: 20 have a two-row header, and on 15 of
    36 (42%) the one-row reading collapses distinct columns into one label --
    22 distinct column labels gone. On ``10.1166--jnn.2011.5114`` the header is
    ``Control | Heat stress`` over ``Saline / Cu / Ag``, so the one-row reading
    labels the saline, copper and silver columns identically: a mean drawn from
    one and an ``n`` from another are indistinguishable afterwards, and GRIM on
    that pair calls an honest paper impossible. That is the accusation this
    repository exists to avoid making.

    It also loses the ``n``. ``design_values_from_cells`` says of this very
    corpus that "0 of 20 cells carried a `col`" on
    ``10.1007--s00702-004-0248-2``; the cause is here. ``Placebo (n = 68)``
    sits in the second header row, so a one-row reading files it as DATA and no
    cell ever carries it as a label. Measured on that paper: header depth 1
    yields 0 design values, depth 2 yields 2 -- ``n = 78`` and ``n = 68``, the
    numbers that gate GRIM, GRIMMER, SPRITE, `debit_check` and
    `check_count_percent`.

    THE BRAKE MATTERS AS MUCH AS THE PROOF. Walking down while the row above
    spans would, on a table whose body itself merges cells, swallow a row of
    measurements into the header -- and a measurement promoted to a label is
    a value the register then cannot see at all. So a candidate row stops the
    walk when its stub is a bare number (a heading's stub never is) or when two
    or more of its cells read as measurements. Both brakes were needed: on
    ``10.1016--j.yexcr.2014.06.020`` the spanning walk reaches a row of
    ``0 / - / + ...`` that only the stub test rejects.

    The same brake is asked about row 0 (mirrors the agent reader, v1.72.0): a
    table whose first row reads as measurements has no header, and its first
    row stays data. Without it, a blank source row 0 flattened to an empty
    header, the post-flatten guard never fired, and the first data row was
    dropped from the body.

    Returns a count, not a slice, because the caller owns the grid.
    """
    if grid and _reads_as_measurements(grid[0]):
        return 0
    depth = 1
    while depth < len(grid) and depth < cap:
        above = source_rows[depth - 1] if depth - 1 < len(source_rows) else []
        if not any(c[1] > 1 for c in above):
            break
        candidate = grid[depth]
        if not candidate or _reads_as_measurements(candidate):
            break
        depth += 1
    return depth


def _flatten_header(header_rows: list[list[str]], width: int) -> list[str]:
    """
    Collapse a multi-row header into one composite label per column.

    ``["Stage 1 prediction"(colspan=2)] / ["n1", "d1opt"]`` becomes
    ``["Stage 1 prediction | n1", "Stage 1 prediction | d1opt"]``. Consecutive
    duplicates are dropped so a ``rowspan=2`` label yields ``"Var"`` rather than
    ``"Var | Var"``. A column with no header text stays empty — `parse_table`
    then falls back to ``col{i}``, which is honest; inventing a label is not.
    """
    labels: list[str] = []
    for i in range(width):
        parts: list[str] = []
        for row in header_rows:
            value = row[i].strip() if i < len(row) else ""
            if not value or (parts and parts[-1] == value):
                continue
            parts.append(value)
        labels.append(" | ".join(parts))
    return labels


def _propagated_header(
    source_rows: list[list[tuple[str, int, int, bool]]], upto: int, width: int
) -> list[list[str]]:
    """Header rows repeat a spanning label across every column it covers.

    `jats._expand` states the policy and calls it a correctness guard: header
    rows and column 0 repeat their text across every covered cell, and every
    other body cell is anchor-only. The .docx reader implemented only the body
    half -- it blanks a merge's continuations so one measurement is not counted
    several times, which is right, and then flattened the header from those
    same blanked rows, which is not.

    What that cost on `EAT-58-1072-s001.docx` Table S.4:

        row 1  '' | Within-Person |  |  | Between-Person |  |
        row 2  '' | b (SE) | p | beta | b (SE) | p | beta

    Only the columns holding a span's ANCHOR kept the group, so the labels came
    out `Within-Person | b (SE)`, `p`, `beta`, `Between-Person | b (SE)`, `p`,
    `beta` -- two columns named `p`, two named `beta`, and nothing to tell them
    apart. `_header_depth` describes exactly this as the accusation risk: a
    value taken from one and an n from another are indistinguishable
    afterwards, and a check on that pair calls an honest paper impossible.

    Body rows are NOT passed here and must never be: repeating a spanned value
    is how one `3.7 (0.30)` becomes four identical pairs and
    `detect_duplication` manufactures a finding.
    """
    out: list[list[str]] = []
    for row in source_rows[:upto]:
        cells: list[str] = []
        for cell in row:
            text, colspan = cell[0], max(1, cell[1])
            cells.extend([text] * colspan)
        cells = cells[:width]
        cells.extend([""] * (width - len(cells)))
        out.append([" ".join(("" if c is None else str(c)).split()) for c in cells])
    return out


def _normalise_table(grid, table_num, source_rows):
    """The rows/data subset of the agent reader's normalization contract.

    Detection historically consumes body rows (falling back to data when the
    body is empty). Keep that behavior, even where it discards header labels.
    Agent provenance, typed cells and section annotations are not needed here.
    """
    grid = [[" ".join(("" if c is None else str(c)).split()) for c in row] for row in grid]
    grid = [row for row in grid if any(row)]
    width = max((len(row) for row in grid), default=0)
    for row in grid:
        row.extend([""] * (width - len(row)))
    depth = _header_depth(source_rows, grid) if source_rows and grid else 1
    depth = max(0, min(int(depth), len(grid))) if grid else 1
    label_start = 0
    if source_rows and grid:
        while (
            label_start < depth - 1
            and label_start < len(source_rows)
            and len(source_rows[label_start]) == 1
            and source_rows[label_start][0][1] >= width > 1
        ):
            label_start += 1
    header_source = (
        _propagated_header(source_rows, depth, width) if source_rows and grid else grid[:depth]
    )
    header = _flatten_header(header_source[label_start:], width) if grid else []
    # A continuation table may begin directly with measurements. Keep that
    # first row as data, matching the agent reader's header-restoration guard.
    if grid and header and any(str(h).strip() for h in header):
        if _reads_as_measurements([str(h or "").strip() for h in header]):
            depth = 0
            header = [""] * width
    body = grid[depth:] if grid else []
    return {"label": f"Table {table_num}", "rows": body, "data": [header] + body if grid else []}


def extract_docx_tables(path: str | Path) -> dict[str, Any]:
    """Tables and paragraph text from a Word (.docx) supplement."""
    path = Path(path)
    try:
        from docx import Document
    except ImportError:
        return {
            "error": "python-docx is not installed; cannot read .docx",
            "tables": [],
            "text": "",
            "n_tables": 0,
        }

    document = Document(str(path))
    tables = []
    for i, table in enumerate(document.tables, 1):
        grid: list[list[str]] = []
        # The SPAN WIDTHS, kept rather than discarded. The duplicate test below
        # already establishes which grid positions one <w:tc> covers; counting
        # them is the colspan, and `_finish` needs it to know how many leading
        # rows are header. Shape matches `jats._header_depth`'s input:
        # (text, colspan, rowspan, is_header).
        source_rows: list[list[tuple[str, int, int, bool]]] = []
        for row in table.rows:
            cells: list[str] = []
            seen: list[Any] = []
            anchors: list[list[Any]] = []
            for cell in row.cells:
                # python-docx REPEATS a merged cell once per grid position it
                # covers. Keeping those copies would turn one measurement into
                # several identical (mean, SD) pairs and trip
                # `detect_duplication` -- a finding invented by the reader. Keep
                # the anchor, blank the continuations, exactly as jats.py does.
                #
                # Compare the underlying <w:tc> elements by identity. `id()` is
                # NOT safe here: `cell._tc` hands back a transient proxy, and a
                # freed one's id can be reused by an unrelated cell.
                element = cell._tc
                duplicate = any(element is s for s in seen)
                cells.append("" if duplicate else cell.text)
                seen.append(element)
                if duplicate and anchors and anchors[-1][0] is element:
                    anchors[-1][2] += 1
                elif duplicate:
                    for a in anchors:
                        if a[0] is element:
                            a[2] += 1
                            break
                else:
                    anchors.append([element, cell.text, 1])
            grid.append(cells)
            source_rows.append([(txt, span, 1, False) for _el, txt, span in anchors])
        tables.append(_normalise_table(grid, i, source_rows))

    text = "\n\n".join(p.text for p in document.paragraphs if p.text.strip())
    return {
        "text": text,
        "tables": tables,
        "n_tables": len(tables),
        "source_format": "docx",
    }
