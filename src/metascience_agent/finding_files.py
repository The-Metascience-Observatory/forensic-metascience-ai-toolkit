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
import re
from pathlib import Path
from typing import Any, Optional

# A quoted token immediately before the word "sheet" — not a free-text parse.
# Used only when the sweep recorded a file but no worksheet name.
_SHEET_IN_LOCATION = re.compile(r"['\"]([^'\"]{1,80})['\"]\s+sheet", re.I)

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


def artefacts_for_editorial(finding: dict, sweep_by_id: dict[str, dict],
                            paper_dir: Path) -> list[dict]:
    """Join an editorial finding to sweep ancestors' files.

    No ancestor, or an ancestor with no path, yields []. We do not parse
    English `location` strings.
    """
    if isinstance(finding.get("artefacts"), list) and finding["artefacts"]:
        return [_enrich(a, paper_dir) for a in finding["artefacts"]
                if isinstance(a, dict)]
    hinted_sheet = None
    loc = finding.get("location")
    if isinstance(loc, str):
        m = _SHEET_IN_LOCATION.search(loc)
        if m:
            hinted_sheet = m.group(1).strip()
    ids = finding.get("stage1_finding_ids") or []
    out: list[dict] = []
    seen: set[str] = set()
    for fid in ids:
        anc = sweep_by_id.get(str(fid))
        if not isinstance(anc, dict):
            continue
        for art in artefacts_from_sweep_finding(anc, paper_dir):
            if hinted_sheet and not art.get("sheet"):
                art["sheet"] = hinted_sheet
            key = art.get("relpath") or art.get("basename") or ""
            if key in seen:
                continue
            seen.add(key)
            out.append(art)
    return out


def index_sweep(findings_obj: Any) -> dict[str, dict]:
    findings = findings_obj
    if isinstance(findings_obj, dict):
        findings = findings_obj.get("findings")
    out: dict[str, dict] = {}
    for f in findings or []:
        if isinstance(f, dict) and f.get("id"):
            out[str(f["id"])] = f
    return out


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
        if isinstance(r, int) and isinstance(c, int):
            # tool cells are 1-based rows (Excel); col may be 0- or 1-based.
            # raw_duplication `_cell_ref` uses 1-based row and 0-based col
            # via _col_letter(col). Treat row as 1-based, col as 0-based.
            out.add((r - 1 if r >= 1 else r, c))
    return out


def _read_csv(path: Path, highlights: list | None, max_rows: int,
              delimiter: str) -> dict:
    rows: list[list[str]] = []
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        for i, row in enumerate(csv.reader(fh, delimiter=delimiter)):
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
