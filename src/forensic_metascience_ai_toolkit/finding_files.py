"""Portable file identity for a finding.

A finding about a supplement must name a file the workbench can open after
the papers root has moved, and after a Mac path has been opened on Windows.
Absolute paths (`/Users/dan/...`, `C:\\Users\\...`, `/mnt/c/Users/...`)
have already leaked into archived reviews; they are a basename plus noise.

The paper directory is the only root. Stored paths are POSIX and
paper-relative. The model does not author these records — the pipeline
lifts them from tool `inputs.path` / `inputs.sheet` and, on a new run,
from `duplicate_groups[].cells`.

Old reviews with no path in the sweep stay file-less. That is a named
absence, not a guess from the prose `location` string.

This is a different module from `artefacts.py`, which extracts the code,
data and registration URLs a paper *points at*. This one names the file
on disk a finding was *computed from*.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Optional

# A quoted token immediately before the word "sheet" — not a free-text parse.
# Used only when the sweep recorded a file but no worksheet name.

KIND_BY_SUFFIX = {
    ".pdf": "pdf",
    ".xlsx": "xlsx", ".xlsm": "xlsx", ".xls": "xls",
    ".csv": "csv", ".tsv": "tsv",
    ".docx": "docx", ".doc": "doc",
    ".xml": "xml", ".html": "html", ".htm": "html",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".mp4": "video", ".webm": "video",
}

_INPUT_PATH_KEYS = ("path", "pdf_path", "xml_path", "file", "xlsx", "csv")

_MAX_SHEET_ROWS = 500
_MAX_SHEET_COLS = 40
_MAX_CELLS = 200


def kind_of(name: str) -> str:
    suf = Path(str(name or "")).suffix.lower()
    return KIND_BY_SUFFIX.get(suf, "file")


def _posix(p: str) -> str:
    return str(p or "").replace("\\", "/").strip()


def _strip_uri_and_drive(raw: str) -> str:
    s = _posix(raw)
    if s.startswith("file://"):
        s = s[7:]
        if s.startswith("/") and len(s) > 2 and s[2] == ":":
            # file:///C:/Users/...
            s = s[1:]
    # Windows "C:/Users/..." after slash-normalising
    if len(s) >= 3 and s[1] == ":" and s[0].isalpha() and s[2] == "/":
        s = s[2:]
    return s


def relativize(path: str | Path, paper_dir: Path) -> dict:
    """Turn any path the tool wrote into a paper-relative POSIX record.

    Never returns an absolute path. If `path` is not under `paper_dir`,
    only the basename survives.
    """
    paper_dir = Path(paper_dir)
    raw = _strip_uri_and_drive(str(path or ""))
    basename = Path(raw).name or ""
    kind = kind_of(basename or raw)
    empty = {"relpath": basename, "basename": basename, "kind": kind}
    if not basename:
        return {"relpath": "", "basename": "", "kind": "file"}
    if ".." in Path(raw).parts or ".." in Path(raw).as_posix().split("/"):
        return empty
    cand = Path(raw)
    try:
        if cand.is_absolute() or raw.startswith("/"):
            try:
                rel = Path(raw).resolve().relative_to(paper_dir.resolve())
            except (ValueError, OSError):
                return empty
            rel_s = rel.as_posix()
            if ".." in rel_s.split("/"):
                return empty
            return {"relpath": rel_s, "basename": basename, "kind": kind}
    except OSError:
        return empty
    return {"relpath": Path(raw).as_posix(), "basename": basename, "kind": kind}


def _inside(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def resolve(paper_dir: Path, spec: dict) -> tuple[Optional[Path], str]:
    """Locate the file under `paper_dir`. Never walks out.

    Order: relpath, then basename, then one rglob of the basename.
    """
    paper_dir = Path(paper_dir)
    rel = str(spec.get("relpath") or spec.get("basename") or "").strip()
    if not rel:
        return None, "no path recorded"
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        rel = Path(rel).name
    parts = Path(rel).as_posix().split("/")
    if ".." in parts:
        return None, "path escapes the paper directory"
    direct = paper_dir.joinpath(*parts)
    try:
        if direct.is_file() and _inside(paper_dir, direct):
            return direct, "relpath"
    except OSError:
        pass
    base = Path(rel).name
    by_name = paper_dir / base
    try:
        if by_name.is_file() and _inside(paper_dir, by_name):
            return by_name, "basename"
    except OSError:
        pass
    hits: list[Path] = []
    try:
        for h in paper_dir.rglob(base):
            if not h.is_file() or not _inside(paper_dir, h):
                continue
            if "highlighted" in h.parts:
                continue
            hits.append(h)
    except OSError:
        hits = []
    if not hits:
        return None, f"not in this paper directory: {base}"
    prefer = [h for h in hits if "forensic_review" not in h.parts]
    chosen = (prefer[0] if prefer else hits[0])
    how = "glob" if len(hits) == 1 else "glob_ambiguous"
    return chosen, how


def cells_from_groups(groups: list) -> tuple[list[dict], str | None]:
    cells: list[dict] = []
    sheet = None
    seen: set[tuple] = set()
    for g in groups or []:
        if not isinstance(g, dict):
            continue
        if sheet is None:
            sheet = g.get("sheet") or g.get("sheet_a")
        for c in (g.get("cells") or []) + (g.get("cells_a") or []) + (g.get("cells_b") or []):
            if not isinstance(c, dict):
                continue
            key = (c.get("sheet"), c.get("cell") or (c.get("row"), c.get("col")))
            if key in seen:
                continue
            seen.add(key)
            rec = {k: c[k] for k in ("sheet", "cell", "row", "col") if k in c}
            if rec:
                cells.append(rec)
            if len(cells) >= _MAX_CELLS:
                return cells, sheet
    return cells, sheet


def _highlight_relpath(paper_dir: Path, basename: str) -> str | None:
    stem = Path(basename).stem
    try:
        from .webapp_index import review_dirs
        dirs = review_dirs(paper_dir)
    except Exception:
        dirs = [d for d in paper_dir.iterdir()
                if d.is_dir() and d.name.startswith("forensic_review")
                and not d.name.endswith("_bundle")]
    for d in dirs:
        cand = d / "highlighted" / f"{stem}.xlsx"
        if cand.is_file():
            try:
                return cand.relative_to(paper_dir).as_posix()
            except ValueError:
                return None
    return None


def _enrich(spec: dict, paper_dir: Path) -> dict:
    out = dict(spec)
    found, how = resolve(paper_dir, out)
    out["found"] = bool(found)
    out["resolve"] = how
    if found:
        try:
            out["relpath"] = found.relative_to(Path(paper_dir)).as_posix()
        except ValueError:
            pass
        hl = _highlight_relpath(paper_dir, out.get("basename") or found.name)
        if hl:
            out["highlight_relpath"] = hl
    else:
        out["found"] = False
        out["missing_reason"] = how
    if out.get("cells"):
        out["confidence"] = "cells"
    elif out.get("found"):
        out.setdefault("confidence", "file")
    else:
        out["confidence"] = "none"
    return out


def artefacts_from_sweep_finding(finding: dict, paper_dir: Path) -> list[dict]:
    """One finding's files, from a stamp or from `inputs.path`."""
    paper_dir = Path(paper_dir)
    stamped = finding.get("artefacts")
    if isinstance(stamped, list) and stamped:
        return [_enrich(a, paper_dir) for a in stamped if isinstance(a, dict)]
    inputs = finding.get("inputs") if isinstance(finding.get("inputs"), dict) else {}
    path = None
    for key in _INPUT_PATH_KEYS:
        val = inputs.get(key)
        if isinstance(val, str) and val.strip():
            path = val
            break
    if not path:
        return []
    spec = relativize(path, paper_dir)
    spec["role"] = "supplement"
    spec["method"] = "sweep_inputs_path"
    sheet = inputs.get("sheet")
    if isinstance(sheet, str) and sheet.strip():
        spec["sheet"] = sheet.strip()
    cells, sheet_from_groups = cells_from_groups(
        (finding.get("computed") or {}).get("duplicate_groups") or []
        if isinstance(finding.get("computed"), dict) else [])
    if cells:
        spec["cells"] = cells
        spec["sheet"] = spec.get("sheet") or sheet_from_groups
        spec["confidence"] = "cells"
    else:
        spec["confidence"] = "file"
    return [_enrich(spec, paper_dir)]


_A1 = __import__("re").compile(r"^\$?([A-Za-z]{1,3})\$?(\d{1,7})$")
# Highlights travel URL-encoded in the /api/sheet query string, and Node refuses
# request headers over 16 KiB (HTTP 431). Anchored ranges are therefore sent as
# one `{row, col, row_end, col_end}` record per A1 range, expanded server-side.
_HIGHLIGHT_URL_BUDGET = 6000
_MAX_EXPANDED_HIGHLIGHTS = 200_000


def _a1_cell(ref: str) -> tuple[int, int] | None:
    """'B12' -> (12, 1): 1-based row, 0-based col (the `_highlight_index` convention)."""
    m = _A1.match(str(ref or "").strip())
    if not m:
        return None
    col = 0
    for ch in m.group(1).upper():
        col = col * 26 + (ord(ch) - 64)
    return int(m.group(2)), col - 1


def _a1_ranges(refs: list) -> list[tuple[int, int, int, int]]:
    """A1 refs and ranges ('B2', 'B2:B40', 'A1:C3') as (row, col, row_end, col_end):
    1-based rows, 0-based cols, inclusive."""
    out = []
    for ref in refs or []:
        if not isinstance(ref, str):
            continue
        a, _, b = ref.partition(":")
        lo, hi = _a1_cell(a), _a1_cell(b or a)
        if lo is None or hi is None:
            continue
        out.append((min(lo[0], hi[0]), min(lo[1], hi[1]), max(lo[0], hi[0]), max(lo[1], hi[1])))
    return out


def _encoded_len(rec: dict) -> int:
    from urllib.parse import quote_plus
    return len(quote_plus(json.dumps(rec, separators=(",", ":")))) + 3


def artefacts_from_sheet_anchors(anchors: Any, paper_dir: Path) -> list[dict]:
    """A detector's spreadsheet records as artefacts the sheet pane opens.

    A separately run detector (rngdetect's `rng_track`) names the cells of a
    supplementary spreadsheet with the findings-v2 `table_cell` anchor
    `{file: <paper-relative path>, sheet?, cells: ["B2:B41", ...], label?,
    approximate?}`: no `table_num`, a `file` whose suffix is a sheet kind,
    A1 references. One artefact per (file, sheet); each A1 range becomes one
    `{row (1-based), col (0-based), row_end, col_end, sheet}` record that
    `read_sheet` expands, and `n_cells` counts the cells they cover.
    XML table anchors (`table_num`/`row`/`col`) are left to the locator."""
    if not isinstance(anchors, list):
        return []
    recs = [a for a in anchors if isinstance(a, dict) and a.get("kind") == "table_cell"
            and a.get("table_num") is None and isinstance(a.get("file"), str)
            and kind_of(a["file"]) in ("xlsx", "xls", "csv", "tsv")
            and isinstance(a.get("cells"), list)]
    if not recs:
        return []
    groups: dict[tuple, list[dict]] = {}
    for a in recs:
        groups.setdefault((a["file"], a.get("sheet") or None), []).append(a)
    out = []
    for (file, sheet), group in groups.items():
        cells: list[dict] = []
        used = n_cells = 0
        for a in group:
            for r, c, r2, c2 in _a1_ranges(a["cells"]):
                rec = {"row": r, "col": c}
                if (r2, c2) != (r, c):
                    rec.update(row_end=r2, col_end=c2)
                if sheet:
                    rec["sheet"] = sheet
                size = _encoded_len(rec)
                if used + size > _HIGHLIGHT_URL_BUDGET:
                    break
                used += size
                n_cells += (r2 - r + 1) * (c2 - c + 1)
                cells.append(rec)
        spec = relativize(file, paper_dir)
        spec.update({"role": "supplement", "method": "producer_table_cell",
                     "labels": [str(a.get("label")) for a in group if a.get("label")],
                     "approximate": any(bool(a.get("approximate")) for a in group)})
        if sheet:
            spec["sheet"] = sheet
        if cells:
            spec["cells"] = cells
            spec["n_cells"] = n_cells
        out.append(_enrich(spec, paper_dir))
    return out


def stamp_sheet_artefacts(issues: list, paper_dir: Path) -> list:
    """Give each issue without artefacts the spreadsheet its anchors name. In place."""
    for issue in issues or []:
        if isinstance(issue, dict) and not issue.get("artefacts") and issue.get("anchors"):
            arts = artefacts_from_sheet_anchors(issue["anchors"], paper_dir)
            if arts:
                issue["artefacts"] = arts
    return issues


def annotate_sweep_findings(findings_obj: Any, paper_dir: Path) -> Any:
    """Stamp `artefacts` onto sweep findings that name a file. In place."""
    if isinstance(findings_obj, dict):
        rows = findings_obj.get("findings") or []
    elif isinstance(findings_obj, list):
        rows = findings_obj
    else:
        return findings_obj
    for f in rows:
        if not isinstance(f, dict):
            continue
        arts = artefacts_from_sweep_finding(f, paper_dir)
        if arts:
            f["artefacts"] = arts
    return findings_obj


def read_sheet(path: Path, sheet: str | None = None,
               highlights: list | None = None,
               max_rows: int = _MAX_SHEET_ROWS) -> dict:
    """A read-only grid for the workbench. Never raises on a bad file."""
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        if suffix in (".csv", ".tsv"):
            return _read_csv(path, highlights, max_rows,
                             delimiter="\t" if suffix == ".tsv" else ",")
        if suffix in (".xlsx", ".xlsm"):
            return _read_xlsx(path, sheet, highlights, max_rows)
        return {"error": f"cannot display {suffix or 'this file'} as a sheet",
                "sheets": [], "rows": []}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}", "sheets": [], "rows": []}


def _highlight_index(highlights: list | None, sheet: str | None) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for h in highlights or []:
        if not isinstance(h, dict):
            continue
        if h.get("sheet") and sheet and str(h["sheet"]) != str(sheet):
            continue
        r, c = h.get("row"), h.get("col")
        r2, c2 = h.get("row_end"), h.get("col_end")
        if (isinstance(r, int) and isinstance(c, int) and isinstance(r2, int)
                and isinstance(c2, int)):
            # an inclusive range, same conventions as a single cell
            for rr in range(r, max(r, r2) + 1):
                for cc in range(c, max(c, c2) + 1):
                    if len(out) >= _MAX_EXPANDED_HIGHLIGHTS:
                        return out
                    out.add((rr - 1 if rr >= 1 else rr, cc))
            continue
        if isinstance(r, int) and isinstance(c, int):
            # tool cells are 1-based rows (Excel); col may be 0- or 1-based.
            # raw_duplication `_cell_ref` uses 1-based row and 0-based col
            # via _col_letter(col). Treat row as 1-based, col as 0-based.
            out.add((r - 1 if r >= 1 else r, c))
    return out


# A supplementary file is the author's, and the pane that shows it runs in the
# one service every reviewer shares. These bound what opening a hostile file
# can cost: a CSV with one multi-gigabyte line, and an .xlsx whose few
# kilobytes inflate to gigabytes (openpyxl loads the shared-strings table
# whole, and a zip member has no ratio limit of its own).
_MAX_CSV_LINE = 1_000_000
_MAX_XLSX_STRINGS = 200 * 1024 * 1024
_MAX_XLSX_MEMBER = 2 * 1024 * 1024 * 1024
_MAX_XLSX_RATIO = 200          # deflate on real sheet XML measures 10-40


def _bounded_lines(fh):
    """Lines of `fh`, each read with a size limit: a longer line is delivered
    in pieces instead of being held in memory whole."""
    while True:
        line = fh.readline(_MAX_CSV_LINE)
        if not line:
            return
        yield line


def _check_xlsx_archive(path: Path) -> None:
    import zipfile
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            size, packed = info.file_size, max(info.compress_size, 1)
            name = info.filename.lower()
            if (size > _MAX_XLSX_MEMBER
                    or (name.endswith("sharedstrings.xml") and size > _MAX_XLSX_STRINGS)
                    or (size > 20 * 1024 * 1024 and size / packed > _MAX_XLSX_RATIO)):
                raise ValueError(
                    f"workbook is too large to preview safely ({info.filename}: "
                    f"{size // (1024 * 1024)} MB uncompressed); open the file itself")


def _read_csv(path: Path, highlights: list | None, max_rows: int,
              delimiter: str) -> dict:
    rows: list[list[str]] = []
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        for i, row in enumerate(csv.reader(_bounded_lines(fh), delimiter=delimiter)):
            if i >= max_rows:
                break
            rows.append([str(c) for c in row[:_MAX_SHEET_COLS]])
    n = len(rows)
    marks = _highlight_index(highlights, None)
    return {
        "sheets": [path.stem],
        "sheet": path.stem,
        "rows": rows,
        "n_rows": n,
        "n_cols": max((len(r) for r in rows), default=0),
        "truncated": False,
        "highlights": [{"r": r, "c": c} for (r, c) in sorted(marks)
                       if 0 <= r < n],
        "error": None,
    }


def _read_xlsx(path: Path, sheet: str | None, highlights: list | None,
               max_rows: int) -> dict:
    import openpyxl
    _check_xlsx_archive(path)
    book = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    names = list(book.sheetnames)
    active = sheet if sheet in names else (names[0] if names else None)
    if active is None:
        return {"error": "workbook has no sheets", "sheets": [], "rows": []}
    ws = book[active]
    rows: list[list[str]] = []
    truncated = False
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i >= max_rows:
            truncated = True
            break
        cells = list(row[:_MAX_SHEET_COLS])
        rows.append(["" if c is None else str(c) for c in cells])
    book.close()
    marks = _highlight_index(highlights, active)
    return {
        "sheets": names,
        "sheet": active,
        "rows": rows,
        "n_rows": len(rows),
        "n_cols": max((len(r) for r in rows), default=0),
        "truncated": truncated,
        "highlights": [{"r": r, "c": c} for (r, c) in sorted(marks)
                       if 0 <= r < len(rows)],
        "error": None,
    }
