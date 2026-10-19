"""
Table ingestion: parse summary-statistics tables into normalized cells so the
agent does not hand-transcribe numbers (transcription/assumption error is a
real failure mode), and reconcile the same table extracted two ways.

`parse_cell`   — one cell → {value, sd, extras, raw} (or a list, for merged blobs)
`parse_table`  — a markdown pipe table, a pdfplumber `data` grid, or raw text
                 → normalized cells + warnings (+ optional cross-check)
`reconcile_tables` — align two extractions of one table, flag disagreements

The `cells` output feeds `detect_duplication` and the reconciliation below --
NOTHING ELSE. These cells are UNTYPED: every `X (Y)` is read as value=X with Y
as its parenthetical companion, so a clinical `142 (71.0)` -- a count and a
PERCENTAGE -- carries sd=71.0 here. Handing that to a granularity or dispersion
check (grimmer, debit, sprite) manufactures an impossibility out of an ordinary
table. Route table cells through `parse_cells_typed` / `check_table` for any
per-cell forensic check; this module exists so two RENDERINGS of a table can be
compared cell-for-cell, where "the value and its companion" is all that is
needed.
"""

from __future__ import annotations

import re
from typing import Any

from . import rounding as _rounding
from .severity import CONSISTENT, INDETERMINATE, SUSPICIOUS

# A numeric token, optionally signed, with optional decimals. No thousands
# separators (those are handled/blocked separately to avoid comma ambiguity).
_NUM = r"[-+]?\d+(?:\.\d+)?"

# mean followed by a dispersion: "5.38 (1.17)", "5.38±1.17", "5.38 +/- 1.17",
# "M=5.38, SD=1.17".
_VALUE_SD_PATTERNS = [
    re.compile(rf"^\s*(?P<v>{_NUM})\s*\(\s*(?P<sd>{_NUM})\s*\)\s*(?P<extra>.*)$"),
    re.compile(rf"^\s*(?P<v>{_NUM})\s*(?:±|\+/-|\+-)\s*(?P<sd>{_NUM})\s*(?P<extra>.*)$"),
    re.compile(
        rf"^\s*(?:M|Mean)\s*[=:]\s*(?P<v>{_NUM})\s*[,;]?\s*"
        rf"(?:SD|S\.D\.|Std)\s*[=:]\s*(?P<sd>{_NUM})\s*(?P<extra>.*)$",
        re.IGNORECASE,
    ),
]

# A bare number (with trailing subscript/marker text).
_BARE = re.compile(rf"^\s*(?P<v>{_NUM})\s*(?P<extra>.*)$")

# Inline "value (sd)" or "value±sd" token, for splitting merged-row blobs.
#
# The lookbehind is load-bearing: without it the value token could start
# MID-NUMBER or mid-fraction, so a merged fraction row like
# "12/30 (40.0) 15/30 (50.0)" matched twice as "30 (40.0)" / "30 (50.0)" and
# fabricated value=30, sd=40.0 -- four numbers welded into readings the paper
# never printed, fed onward to reconciliation and duplication detection as
# data. A value may not be preceded by a digit, a decimal point or a slash.
_INLINE_TOKEN = re.compile(
    rf"(?<![\d/.])(?P<v>{_NUM})\s*(?:\(\s*(?P<sd1>{_NUM})\s*\)|(?:±|\+/-|\+-)\s*(?P<sd2>{_NUM}))"
)

# Signals a thousands-separator / ambiguous-locale number we refuse to guess.
_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")


def _clean_extras(text: str) -> list[str]:
    """Pull subscript/marker tokens (a, b, *, †, ‡, #) out of trailing text."""
    if not text:
        return []
    toks = re.split(r"[\s,]+", text.strip())
    return [t for t in toks if t]


def parse_cell(raw: str) -> dict | list[dict]:
    """Parse a single table cell.

    Returns a dict {value, sd, extras, raw} for a normal cell, or a LIST of
    such dicts when the cell is a merged whole-row blob containing several
    value(±sd) tokens (a common docling/pdf extraction artifact, e.g.
    "Age (years) 17.2±5.2 18.1±5.5 19.0±6.1"). A non-numeric cell returns
    {value: None, sd: None, extras, raw}.
    """
    if raw is None:
        return {"value": None, "sd": None, "extras": [], "raw": ""}
    text = str(raw).strip()
    if not text:
        return {"value": None, "sd": None, "extras": [], "raw": text}

    # Merged blob: 2+ value(±sd) tokens in one cell → split into a list.
    inline = list(_INLINE_TOKEN.finditer(text))
    if len(inline) >= 2:
        cells: list[dict] = []
        for m in inline:
            sd = m.group("sd1") or m.group("sd2")
            cells.append({
                "value": float(m.group("v")),
                "sd": float(sd) if sd is not None else None,
                "extras": [],
                "raw": m.group(0),
                "decimals_value": _rounding.decimals_of_text(m.group("v")),
                "decimals_sd": _rounding.decimals_of_text(sd),
            })
        return cells

    if _THOUSANDS.search(text):
        return {
            "value": None, "sd": None, "extras": [],
            "raw": text,
            "warning": "ambiguous thousands/decimal separator; not parsed",
        }

    for pat in _VALUE_SD_PATTERNS:
        m = pat.match(text)
        if m:
            return {
                "value": float(m.group("v")),
                "sd": float(m.group("sd")),
                "extras": _clean_extras(m.group("extra")),
                "raw": text,
                # PRINTED precision, read from the literal while it still
                # exists. Reconciliation compares two renderings at the coarser
                # printed precision, and repr of the parsed float misreads
                # "142" as 1 dp and "1.40" as 1 dp.
                "decimals_value": _rounding.decimals_of_text(m.group("v")),
                "decimals_sd": _rounding.decimals_of_text(m.group("sd")),
            }

    m = _BARE.match(text)
    if m and not re.search(r"\d", m.group("extra") or ""):
        return {
            "value": float(m.group("v")),
            "sd": None,
            "extras": _clean_extras(m.group("extra")),
            "raw": text,
            "decimals_value": _rounding.decimals_of_text(m.group("v")),
        }

    # Non-numeric (a label, footnote, or unparseable content).
    return {"value": None, "sd": None, "extras": [], "raw": text}


def _split_markdown(source: str) -> list[list[str]]:
    """Parse a markdown pipe table into a grid, dropping separator rows."""
    grid: list[list[str]] = []
    for line in source.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        # Drop a GFM separator row like | --- | :--: |.
        if re.fullmatch(r"\|?[\s:|-]+\|?", line) and "-" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        grid.append(cells)
    return grid


def _detect_format(source: Any) -> str:
    if isinstance(source, list):
        return "grid"
    if isinstance(source, str) and "|" in source:
        return "markdown"
    return "text"


def parse_table(
    source: Any,
    source_format: str = "auto",
    source_label: str = "table",
    header_row: int = 0,
    label_col: int = 0,
    cross_check: Any = None,
    cross_check_format: str = "auto",
) -> dict:
    """Parse a table into normalized cells.

    Args:
        source: markdown pipe-table string, a pdfplumber `data` grid
            (list[list[str]] — the `data` field from extract_text_with_tables),
            or raw whitespace/newline text.
        source_format: "auto" | "markdown" | "grid" | "text".
        source_label: name used in the output and downstream findings.
        header_row: index of the header row within the grid (column labels).
        label_col: index of the column holding row labels.
        cross_check: an optional second source (same table, other extraction)
            to reconcile against.

    Returns:
        {severity, source_label, shape, row_labels, col_labels, cells, warnings,
         [reconciliation], methodology}
        where cells = [{row_label, col_label, value, sd, extras, raw}].
    """
    if source_format == "auto":
        source_format = _detect_format(source)

    if source_format == "markdown":
        grid = _split_markdown(source)
    elif source_format == "grid":
        grid = [[("" if c is None else str(c)) for c in row] for row in (source or [])]
    else:  # whitespace/newline text
        grid = [re.split(r"\s{2,}|\t", ln.strip())
                for ln in str(source).splitlines() if ln.strip()]

    if not grid:
        return {
            "severity": INDETERMINATE,
            "error": "no rows parsed from source",
            "source_label": source_label,
            "cells": [],
            "warnings": ["empty table"],
        }

    warnings: list[str] = []
    col_labels: list[str] = []
    if 0 <= header_row < len(grid):
        col_labels = grid[header_row]
    body = [row for i, row in enumerate(grid) if i != header_row]

    cells: list[dict] = []
    row_labels: list[str] = []
    for r_idx, row in enumerate(body):
        raw_label = row[label_col].strip() if label_col < len(row) else f"row{r_idx}"
        label = raw_label
        parsed_row: list[tuple[int, dict]] = []
        for c_idx, cell in enumerate(row):
            parsed = parse_cell(cell)
            if c_idx == label_col:
                if isinstance(parsed, list):
                    # The label column itself is a merged blob: leading text is
                    # the row label, the value tokens are this row's data.
                    label = _INLINE_TOKEN.sub("", str(cell)).strip() or f"row{r_idx}"
                    warnings.append(
                        f"{source_label}: merged blob in label column of row "
                        f"'{label}' split into {len(parsed)} cells"
                    )
                    for sub in parsed:
                        parsed_row.append((c_idx, sub))
                # otherwise: plain label cell, contributes no data
                continue
            if isinstance(parsed, list):
                warnings.append(
                    f"{source_label}: merged blob at row '{label or r_idx}' "
                    f"col {c_idx} split into {len(parsed)} cells"
                )
                for sub in parsed:
                    parsed_row.append((c_idx, sub))
            else:
                if parsed.get("warning"):
                    warnings.append(f"{source_label}: {parsed['warning']} ({parsed['raw']!r})")
                parsed_row.append((c_idx, parsed))

        # If the row label itself was empty but the blob carried a label, the
        # merged-blob branch already dropped it; keep the given label.
        if not any(p.get("value") is not None for _, p in parsed_row):
            # A pure label / section row — skip but remember the label.
            if label:
                row_labels.append(label)
            continue

        row_labels.append(label or f"row{r_idx}")
        # Assign column labels positionally over the numeric cells.
        numeric_idx = 0
        for c_idx, parsed in parsed_row:
            if parsed.get("value") is None and parsed.get("sd") is None:
                continue
            col_label = ""
            if col_labels:
                # header column index aligns to c_idx when no blob-splitting;
                # fall back to positional numeric index otherwise.
                if c_idx < len(col_labels):
                    col_label = col_labels[c_idx]
                else:
                    non_label_cols = [c for i, c in enumerate(col_labels) if i != label_col]
                    if numeric_idx < len(non_label_cols):
                        col_label = non_label_cols[numeric_idx]
            out_cell = {
                "row_label": label or f"row{r_idx}",
                "col_label": col_label or f"col{numeric_idx}",
                "value": parsed.get("value"),
                "sd": parsed.get("sd"),
                "extras": parsed.get("extras", []),
                "raw": parsed.get("raw", ""),
            }
            # Printed precision, present ONLY when the literal was seen.
            # `detect_duplication` reads `decimals_sd` with a `.get` default,
            # and a key stored as None defeats the default (`int(None)`); an
            # absent key is the honest encoding of "literal not available".
            for dk in ("decimals_value", "decimals_sd"):
                if parsed.get(dk) is not None:
                    out_cell[dk] = parsed[dk]
            cells.append(out_cell)
            numeric_idx += 1

    result = {
        # A parser is not a check: reading a grid says nothing about whether the
        # paper is right, so parse_table renders NO verdict of its own (like
        # parse_cells_typed). Its old top-level severity was `consistent` on
        # EVERY call -- the `if warnings` branch below overrode SUSPICIOUS back to
        # CONSISTENT -- so a table where nothing parsed read as a clean bill of
        # health, and, because severity_reconcile maps technique="reconcile" to
        # this tool and reads only the TOP-LEVEL severity, a correct text-vs-table
        # mismatch finding was publicly stamped "upgraded past a tool that said
        # consistent". The verdict, when there is one, is the reconciliation below.
        "severity": INDETERMINATE,
        "source_label": source_label,
        "shape": [len(body), max((len(r) for r in grid), default=0)],
        "row_labels": row_labels,
        "col_labels": [c for i, c in enumerate(col_labels) if i != label_col],
        "cells": cells,
        "n_numeric_cells": len(cells),
        "warnings": warnings,
        "methodology": (
            f"Parsed {len(cells)} numeric cells from a {source_format} table "
            f"'{source_label}'. Each cell normalized to value/SD/extras."
        ),
    }
    if cross_check is not None:
        other = parse_table(
            cross_check,
            source_format=cross_check_format,
            source_label=f"{source_label}__crosscheck",
            header_row=header_row,
            label_col=label_col,
        )
        result["reconciliation"] = reconcile_tables(result, other)
        # A cross-check IS a verdict -- two extractions agreeing or disagreeing is
        # exactly what `reconcile` findings assert -- so lift it to the top level
        # where consumers and severity_reconcile read `severity`. Without this the
        # disagreement stayed nested and the top level read `consistent`.
        result["severity"] = result["reconciliation"].get("severity", INDETERMINATE)

    return result


def _pair_agrees(ca: dict, cb: dict, val_key: str, dec_key: str) -> bool:
    """Do two renderings of the same printed cell agree at the coarser precision?

    A printed number is an interval, so the test is interval overlap --
    `|a - b| <= half_width(coarser) + epsilon` -- not equality of the two
    values re-rounded. `round(a, d) == round(b, d)` put the boundary case on
    the wrong side: the paper's text saying 5.35 and its table saying 5.4 are
    the SAME claim at 1 dp, but banker's rounding sends 5.35 to 5.3 and the
    honest pair was stamped a disagreement.

    Precision comes from the recorded literal (`decimals_value`/`decimals_sd`)
    when the parser saw one; the repr fallback exists for cells built by other
    code and errs coarse (`repr(142.0)` reads as 1 dp where the paper printed
    0), which widens the interval -- the direction that misses, never the one
    that accuses.
    """
    def dec(cell: dict) -> int:
        d = cell.get(dec_key)
        if d is not None:
            return d
        s = repr(cell[val_key])
        return len(s.split(".")[1]) if "." in s else 0

    d = min(dec(ca), dec(cb))
    return abs(ca[val_key] - cb[val_key]) <= _rounding.tolerance(d)


def reconcile_tables(table_a: dict, table_b: dict) -> dict:
    """Align two parsed tables by (row_label, col_label) and flag disagreements.

    A disagreement is either an extraction error OR a genuine text-vs-table
    mismatch in the paper — both worth surfacing. Matching is exact on
    normalized labels first, then case/space-insensitive.
    """
    def key(cell: dict, fuzzy: bool) -> tuple[str, str]:
        r, c = cell.get("row_label", ""), cell.get("col_label", "")
        if fuzzy:
            r = re.sub(r"\s+", " ", r.strip().lower())
            c = re.sub(r"\s+", " ", c.strip().lower())
        return (r, c)

    a_cells = table_a.get("cells", [])
    b_cells = table_b.get("cells", [])
    b_index = {key(c, False): c for c in b_cells}
    b_index_fuzzy = {key(c, True): c for c in b_cells}

    disagreements: list[dict] = []
    n_compared = 0
    n_agree = 0
    for ca in a_cells:
        cb = b_index.get(key(ca, False)) or b_index_fuzzy.get(key(ca, True))
        if cb is None:
            continue
        n_compared += 1
        kinds = []
        if ca.get("value") is not None and cb.get("value") is not None:
            if not _pair_agrees(ca, cb, "value", "decimals_value"):
                kinds.append("value")
        if ca.get("sd") is not None and cb.get("sd") is not None:
            if not _pair_agrees(ca, cb, "sd", "decimals_sd"):
                kinds.append("sd")
        if kinds:
            disagreements.append({
                "row_label": ca.get("row_label"),
                "col_label": ca.get("col_label"),
                "value_a": ca.get("value"), "value_b": cb.get("value"),
                "sd_a": ca.get("sd"), "sd_b": cb.get("sd"),
                "kind": "+".join(kinds),
            })
        else:
            n_agree += 1

    severity = SUSPICIOUS if disagreements else CONSISTENT
    return {
        "severity": severity,
        "n_compared": n_compared,
        "n_agree": n_agree,
        "n_disagree": len(disagreements),
        "disagreements": disagreements,
        "explanation": (
            f"{n_agree}/{n_compared} aligned cells agree between "
            f"'{table_a.get('source_label')}' and '{table_b.get('source_label')}'."
            + (f" {len(disagreements)} disagree — check for extraction error or a "
               "genuine text-vs-table mismatch." if disagreements else "")
        ),
        "methodology": (
            "Reconciliation: aligned cells by (row, col) label and compared "
            "values/SDs at the coarser reported precision."
        ),
    }
