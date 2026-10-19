"""The tables a paper printed, plus a DERIVED split, with the printed one canonical.

WHY A DERIVED SPLIT AND NOT A CUT. Journals print several logical tables as one
physical table, separated by a banner row repeating a section name across every
column. `composite.split_sections` already recovers those sections, and the
section is where the denominator lives -- within a section the categories are
exhaustive, so the counts sum to n, which is the number `grim_percentage` keeps
refusing for want of.

The standing decision (CLAUDE.md) is:

    Record the boundary; do NOT cut the table into synthetic sub-tables -- the
    precedent is `references_boundary`, where the text stays whole.

with three reasons: a finding in "Table 1b" points at a table the paper never
printed, so provenance breaks; `n_table_items` and every coverage figure move;
and two walkers can end up disagreeing about how many tables exist.

GREG, 2026-08-27, RESOLVING IT: "go ahead with the derived split, keep the
register anchored." That distinction is what makes both true at once. The
decision above is about the WALKER cutting the source. This writes a DERIVED
artifact beside the paper: the printed table stays whole and canonical, every
block carries provenance back to it, and nothing here is an input to the value
register or to any check. So none of the three reasons is triggered --
`n_table_items` is untouched because the walker is unchanged, and a finding can
only ever cite the printed table because that is the only thing anchored.

THE INVARIANT THIS FILE EXISTS TO HOLD, and the one a test pins:

    A block id NEVER appears in a value anchor, a finding, or a check.

A block is a reading aid for an agent that has to navigate a 389-cell blob. It
is not evidence, and the moment it becomes evidence the provenance argument
above is lost.

NAMING. Blocks are keyed by the printed table's own label plus an ordinal and
the section's own printed text -- never "Table 1b", which is a label the paper
does not have and which a reader would reasonably believe was printed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: The directory written beside a paper. Derived, disposable, rebuildable.
PACKAGE_DIR = "tables"

#: Written into every block file and index entry. A consumer that finds this key
#: knows the content was assembled by us and is not the paper's own layout.
DERIVED_NOTE = (
    "DERIVED. The paper printed one physical table; this block is one section of "
    "it, split by a banner row. The printed table is canonical and is in "
    "`printed/`. Cite the printed table, never this block."
)


def _slug(text: str, limit: int = 48) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in (text or "")]
    s = "".join(keep)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")[:limit] or "unlabelled"


def _col_key(c: dict):
    """The column a cell sits in: its `col` index when it has one, else its label.

    TWO COLUMNS CAN SHARE A LABEL. PLOS ONE 10.1371/journal.pone.0042828 Table 2
    prints "Locomotor Activity" and "Rearing Activity" as spanners, but its XML
    splits each into two `colspan="1"` cells ("Locomotor", "Activity"), so the
    stacked-header fold gives column 2 and column 4 the same label, "Activity |
    Day28 ISCH". Keyed by label, the second overwrote the first: the 7-column
    table was written with 6, the locomotor Day-28 values were gone, and the
    rearing Day-28 values sat under the locomotor heading. Docling tables repeat
    labels the same way (an `n` and a `%` under every arm when the spanner is
    lost). A label is not an identity; the index is.
    """
    col = c.get("col")
    if isinstance(col, int) and not isinstance(col, bool):
        return (0, col)
    return (1, c.get("col_label"))


def _grid(cells: list[dict]) -> tuple[list, list, dict]:
    """Rows, column keys, and a (row, column key) -> raw map.

    Columns are keyed by the cell's `col` index when it carries one (every
    extractor's cells do) and by `col_label` only when it does not: a walked cell
    may carry `raw`, `row`, `row_label`, `col_label` and NO `col`, and reading
    `c["col"]` there yields a one-column table on every paper while looking
    correct. Indexed columns are ordered by index, so a column whose first rows
    are blank is not moved to the end; label-keyed ones keep first appearance.
    The header label of a column is the first non-empty `col_label` it holds
    (`idx["col_labels"]`).
    """
    cols: list = []
    for c in cells:
        k = _col_key(c)
        if k not in cols:
            cols.append(k)
    indexed = sorted(k for k in cols if k[0] == 0)
    if indexed:
        it = iter(indexed)
        cols = [next(it) if k[0] == 0 else k for k in cols]
    col_labels: dict = {}
    for c in cells:
        k = _col_key(c)
        if not col_labels.get(k):
            col_labels[k] = c.get("col_label") or ""
    rows: list = []
    for c in cells:
        if c.get("row") not in rows:
            rows.append(c.get("row"))
    rows.sort(key=lambda x: (x is None, x))
    by = {(c.get("row"), _col_key(c)): (c.get("raw") or "") for c in cells}
    labels = {}
    for c in cells:
        labels.setdefault(c.get("row"), c.get("row_label") or "")
    return rows, cols, {"by": by, "row_labels": labels, "col_labels": col_labels}


def _cell(text: Any) -> str:
    """One cell, safe to place between pipes.

    A WALKED LABEL CAN CONTAIN A PIPE. The stacked-header fold joins a spanning
    header to its sub-header with " | ", so `col_label` arrives as
    `"Comorbidity patterns, n (%) | Low-risk CVDs (n = 1293)"` and `row_label`
    as `"Typical antipsychotics | No"`. Written raw between pipes those split
    the row, and markdown silently renders a table with the wrong number of
    columns and the values shifted -- a corruption that looks like a table.
    Found 2026-08-27 by counting the header cells against the separator.

    Newlines go too: a cell holding one would end the row mid-table.
    """
    return (str(text if text is not None else "")
            .replace("|", "\\|").replace("\n", " ").strip())


def _markdown(cells: list[dict], title: str, note: str = "") -> str:
    rows, cols, idx = _grid(cells)
    if not rows or not cols:
        return f"# {title}\n\n_No cells._\n"
    out = [f"# {title}", ""]
    if note:
        out += [f"> {note}", ""]
    out.append("| " + " | ".join(
        [""] + [_cell(idx["col_labels"].get(c)) for c in cols]) + " |")
    out.append("|" + "---|" * (len(cols) + 1))
    for r in rows:
        cellvals = [_cell(idx["by"].get((r, c), "")) for c in cols]
        out.append("| " + " | ".join([_cell(idx["row_labels"].get(r, ""))]
                                     + cellvals) + " |")
    return "\n".join(out) + "\n"


def _sections_from_record(table: dict, cells: list[dict]) -> list[dict]:
    """Sections from the table's own `sections` list, as blocks of cells.

    Each entry is `{"row": i, "label": str}` naming the row a band STARTS at, so
    a block runs from its own band row to the next one. Rows before the first
    band (a table that opens with unbanded rows) become a leading unlabelled
    block, which is what the printed table shows.

    Returns [] when the record carries no sections, so the caller can fall back
    rather than treat "no record" as "no sections".
    """
    marks = [m for m in (table.get("sections") or [])
             if isinstance(m, dict) and m.get("row") is not None]
    if not marks:
        return []
    marks = sorted(marks, key=lambda m: m["row"])
    bounds = [(int(m["row"]), str(m.get("label") or "").strip()) for m in marks]

    out: list[dict] = []
    lead = [c for c in cells if (c.get("row") or 0) < bounds[0][0]]
    if lead:
        out.append({"label": None, "cells": lead, "n": None,
                    "n_source": None, "why_not": None})
    for i, (start, label) in enumerate(bounds):
        end = bounds[i + 1][0] if i + 1 < len(bounds) else None
        block = [c for c in cells
                 if (c.get("row") or 0) >= start
                 and (end is None or (c.get("row") or 0) < end)]
        if block:
            out.append({"label": label, "cells": block, "n": None,
                        "n_source": None, "why_not": None})
    return out


def build(paper_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    """Write `tables/` beside the paper. Returns the index it wrote.

    Best-effort by contract, like `report_render` and `copy_paste_detector.highlight`: a
    missing dependency or an unwritable path returns a structured `error` and
    never raises. This is a navigation aid layered on top of the analysis, not
    a step the pipeline may fail on.
    """
    from . import composite, prepass

    paper_dir = Path(paper_dir)
    out = Path(out_dir) if out_dir else paper_dir / PACKAGE_DIR
    index: dict[str, Any] = {
        "paper_dir": str(paper_dir),
        "derived": True,
        "note": DERIVED_NOTE,
        "printed": [],
        "blocks": [],
    }
    try:
        tables = list(prepass.paper_tables(paper_dir, include_supplements=True))
    except Exception as exc:                              # noqa: BLE001
        index["error"] = f"{type(exc).__name__}: {exc}"
        return index

    try:
        (out / "printed").mkdir(parents=True, exist_ok=True)
        (out / "blocks").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        index["error"] = f"could not create {out}: {exc}"
        return index

    captions = ["# Table captions", ""]
    for i, t in enumerate(tables):
        label = str(t.get("label") or f"(unlabelled table {i})")
        cells = t.get("cells") or []
        printed_name = f"printed/{i:02d}_{_slug(label)}.md"
        try:
            (out / printed_name).write_text(
                _markdown(cells, label), encoding="utf-8")
        except OSError:
            continue
        index["printed"].append({
            "ordinal": i, "label": label, "file": printed_name,
            "n_cells": len(cells),
            "extractor": t.get("extractor") or t.get("source"),
        })
        captions += [f"## {label}", "", f"- file: `{printed_name}`",
                     f"- cells: {len(cells)}", ""]

        # THE TABLE ALREADY KNOWS ITS SECTIONS. `fold_section_bands` records
        # them as `[{"row": i, "label": ...}]` and `prepass` carries the list,
        # so re-deriving them from banner ROWS asks a question the record has
        # already answered -- and answers it wrong here, because the band rows
        # are dropped before cells are built.
        #
        # MEASURED 2026-08-29 on `10.1002--ajcp.70049` Table 2, a table Greg
        # identified by eye as composite: the record carries sections at rows 2
        # and 6 ("Measures of inclusive leadership", "Covariates"), the cells
        # begin at row 3 and skip 6, `split_sections` therefore finds ONE
        # section, and the package wrote ZERO blocks on a paper with two
        # obviously composite tables. The comment at `jats.fold_section_bands`
        # asserting "THE BAND ROW STAYS" does not hold on this path.
        #
        # Prefer the record; fall back to the scan for producers that do not
        # emit one.
        sections = _sections_from_record(t, cells)
        if not sections:
            try:
                sections = composite.split_sections(cells)
            except Exception:                              # noqa: BLE001
                sections = []
        # ONE SECTION IS NOT A COMPOSITE. Writing a block for a table that has
        # no banner row would double every table on disk and invite a reader to
        # cite the copy.
        if len(sections) < 2:
            continue
        for k, s in enumerate(sections):
            sec_cells = s.get("cells") or []
            if not sec_cells:
                continue
            block_id = f"{label} :: block {k}"
            name = f"blocks/{i:02d}_{k:02d}_{_slug(s.get('label') or 'section')}.md"
            try:
                (out / name).write_text(
                    _markdown(sec_cells, block_id, DERIVED_NOTE), encoding="utf-8")
            except OSError:
                continue
            index["blocks"].append({
                "block_id": block_id,
                "file": name,
                # PROVENANCE, and the reason this is safe: every block says which
                # printed table it came from and which of ITS rows it holds.
                "printed_table_label": label,
                "printed_table_file": printed_name,
                "printed_row_indices": sorted(
                    {c.get("row") for c in sec_cells if c.get("row") is not None}),
                "section_label": s.get("label"),
                # The section's recovered n, and `why_not` when it could not be
                # verified against the paper's own percentages. Carried, not
                # relied on: nothing here feeds a check.
                "n": s.get("n"),
                "n_source": s.get("n_source"),
                "why_not": s.get("why_not"),
                "is_evidence": False,
            })

    try:
        (out / "captions.md").write_text("\n".join(captions), encoding="utf-8")
        (out / "index.json").write_text(
            json.dumps(index, indent=1) + "\n", encoding="utf-8")
    except OSError as exc:
        index["error"] = f"could not write index: {exc}"
    return index


def block_ids(index: dict) -> set[str]:
    """Every derived block id, for the test that pins they never become evidence."""
    return {b.get("block_id") for b in (index or {}).get("blocks") or []
            if b.get("block_id")}
