import json
"""Portable finding-file paths: never absolute, never outside the paper dir."""
from pathlib import Path

from forensic_metascience_ai_toolkit.finding_files import (
    artefacts_from_sweep_finding, relativize,
    resolve, read_sheet,
)


def test_relativize_unix_absolute_becomes_basename(tmp_path):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    spec = relativize("/Users/dan/Dropbox/foo/bar.xlsx", paper)
    assert spec["basename"] == "bar.xlsx"
    assert spec["relpath"] == "bar.xlsx"
    assert not spec["relpath"].startswith("/")
    assert spec["kind"] == "xlsx"


def test_relativize_windows_and_wsl_paths(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    for raw in (
        r"C:\Users\dan\Dropbox\foo.xlsx",
        "C:/Users/dan/Dropbox/foo.xlsx",
        "/mnt/c/Users/dan/Dropbox/foo.xlsx",
        "file:///C:/Users/dan/foo.xlsx",
    ):
        spec = relativize(raw, paper)
        assert spec["basename"] == "foo.xlsx", raw
        assert spec["relpath"] == "foo.xlsx", raw


def test_relativize_under_paper_dir_keeps_relative(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    src = paper / "data.xlsx"
    src.write_bytes(b"x")
    spec = relativize(str(src), paper)
    assert spec["relpath"] == "data.xlsx"


def test_relativize_nested_file_keeps_subpath(tmp_path):
    paper = tmp_path / "p"
    nested = paper / "si" / "tables.xlsx"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"x")
    spec = relativize(str(nested), paper)
    assert spec["relpath"] == "si/tables.xlsx"
    assert spec["basename"] == "tables.xlsx"


def test_resolve_refuses_dotdot(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    secret = tmp_path / "secret.xlsx"
    secret.write_bytes(b"x")
    found, reason = resolve(paper, {"relpath": "../secret.xlsx",
                                    "basename": "secret.xlsx"})
    assert found is None
    assert found is None or not _is_outside(paper, found)
    assert "escape" in reason or "not in this paper" in reason


def test_resolve_never_returns_a_path_outside_the_paper(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    (tmp_path / "cars.xlsx").write_bytes(b"x")
    for spec in (
        {"relpath": "../cars.xlsx", "basename": "cars.xlsx"},
        {"relpath": r"..\cars.xlsx", "basename": "cars.xlsx"},
        {"relpath": "/etc/passwd", "basename": "passwd"},
        {"relpath": "si/../../cars.xlsx", "basename": "cars.xlsx"},
    ):
        found, _ = resolve(paper, spec)
        assert found is None or _is_inside(paper, found), spec


def test_resolve_finds_basename_when_absolute_moved(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "qaly.xlsx").write_bytes(b"x")
    spec = relativize("/old/machine/run_with_sonnet/qaly.xlsx", paper)
    found, how = resolve(paper, spec)
    assert found == paper / "qaly.xlsx"
    assert how in ("basename", "relpath")


def test_resolve_finds_file_after_root_moves(tmp_path):
    """A stored basename still works when the papers root is a different OS path."""
    old = tmp_path / "mac" / "Dropbox" / "p"
    new = tmp_path / "linux" / "papers" / "p"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (new / "QALY.xlsx").write_bytes(b"x")
    spec = relativize(str(old / "QALY.xlsx"), old)
    found, _ = resolve(new, spec)
    assert found == new / "QALY.xlsx"


def test_cells_from_duplicate_groups_raise_confidence(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "cars.xlsx").write_bytes(b"x")
    sweep = {
        "id": "dup",
        "inputs": {"path": "cars.xlsx", "sheet": "QALY"},
        "computed": {
            "duplicate_groups": [{
                "sheet": "QALY",
                "cells": [
                    {"sheet": "QALY", "cell": "B2", "row": 2, "col": 1},
                    {"sheet": "QALY", "cell": "B9", "row": 9, "col": 1},
                ],
            }],
        },
    }
    arts = artefacts_from_sweep_finding(sweep, paper)
    assert arts[0]["confidence"] == "cells"
    assert len(arts[0]["cells"]) == 2


def test_read_sheet_highlights_1based_rows(tmp_path):
    import openpyxl
    src = tmp_path / "t.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "QALY"
    ws.append(["id", "q"])
    ws.append(["a", 1])
    ws.append(["b", 2])
    wb.save(src)
    grid = read_sheet(src, "QALY",
                      highlights=[{"sheet": "QALY", "cell": "B2", "row": 2, "col": 1}])
    assert grid["sheet"] == "QALY"
    assert grid["rows"][0][0] == "id"
    assert {"r": 1, "c": 1} in [{k: h[k] for k in ("r", "c")}
                                for h in grid["highlights"]]


def _is_inside(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _is_outside(root: Path, target: Path) -> bool:
    return not _is_inside(root, target)


# --- detector spreadsheet anchors (rng_track `table_cell` with a sheet file) ---------

def _rng_sheet_paper(tmp_path):
    import openpyxl
    paper = tmp_path / "10.1--rng"
    (paper / "supplementary").mkdir(parents=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Figure 3e"
    ws.append(["X", "Y"])
    for i in range(40):
        ws.append([i * 0.1, i * 0.2])
    wb.save(paper / "supplementary" / "S4.xlsx")
    return paper


def test_sheet_anchors_become_an_openable_artefact(tmp_path):
    from forensic_metascience_ai_toolkit.finding_files import artefacts_from_sheet_anchors
    paper = _rng_sheet_paper(tmp_path)
    anchors = [
        {"kind": "table_cell", "file": "supplementary/S4.xlsx", "sheet": "Figure 3e",
         "cells": ["A2:A31"], "label": "X", "approximate": False},
        {"kind": "table_cell", "file": "supplementary/S4.xlsx", "sheet": "Figure 3e",
         "cells": ["B2:B31"], "label": "Y", "approximate": False},
        {"kind": "table_cell", "table_num": 2, "row": 3, "col": 1},      # an XML cell: not ours
    ]
    (art,) = artefacts_from_sheet_anchors(anchors, paper)
    assert art["found"] and art["relpath"] == "supplementary/S4.xlsx" and art["kind"] == "xlsx"
    assert art["sheet"] == "Figure 3e" and art["confidence"] == "cells"
    assert art["n_cells"] == 60
    assert art["cells"] == [
        {"row": 2, "col": 0, "row_end": 31, "col_end": 0, "sheet": "Figure 3e"},
        {"row": 2, "col": 1, "row_end": 31, "col_end": 1, "sheet": "Figure 3e"}]
    grid = read_sheet(paper / art["relpath"], art["sheet"], art["cells"])
    marks = {(h["r"], h["c"]) for h in grid["highlights"]}
    assert (1, 0) in marks and (30, 1) in marks and (0, 0) not in marks      # header unmarked
    assert grid["rows"][1][0] == "0" or grid["rows"][1][0].startswith("0")


def test_sheet_anchor_ranges_highlight_every_cell_in_a_short_url(tmp_path):
    from urllib.parse import urlencode
    from forensic_metascience_ai_toolkit.finding_files import artefacts_from_sheet_anchors
    paper = _rng_sheet_paper(tmp_path)
    anchors = [{"kind": "table_cell", "file": "supplementary/S4.xlsx", "sheet": "Figure 3e",
                "cells": [f"{c}2:{c}41"]} for c in "ABC"]
    (art,) = artefacts_from_sheet_anchors(anchors, paper)
    assert art["n_cells"] == 120 and len(art["cells"]) == 3
    # the pane sends them URL-encoded; Node rejects headers over 16 KiB (HTTP 431)
    assert len(urlencode({"highlights": json.dumps(art["cells"], separators=(",", ":"))})) < 8000
    grid = read_sheet(paper / art["relpath"], art["sheet"], art["cells"])
    marks = {(h["r"], h["c"]) for h in grid["highlights"]}
    assert {(r, c) for r in range(1, 41) for c in range(3)} <= marks and (0, 0) not in marks


def test_many_disjoint_ranges_stay_within_the_url_budget(tmp_path):
    from urllib.parse import urlencode
    from forensic_metascience_ai_toolkit.finding_files import artefacts_from_sheet_anchors
    paper = _rng_sheet_paper(tmp_path)
    anchors = [{"kind": "table_cell", "file": "supplementary/S4.xlsx", "sheet": "Figure 3e",
                "cells": [f"A{r}" for r in range(2, 2000, 2)]}]
    (art,) = artefacts_from_sheet_anchors(anchors, paper)
    assert 20 < len(art["cells"]) < 999 and art["n_cells"] == len(art["cells"])
    assert len(urlencode({"highlights": json.dumps(art["cells"], separators=(",", ":"))})) < 8000

def test_sheet_anchor_for_a_missing_file_is_not_found(tmp_path):
    from forensic_metascience_ai_toolkit.finding_files import (
        artefacts_from_sheet_anchors, stamp_sheet_artefacts)
    paper = tmp_path / "p"
    paper.mkdir()
    (art,) = artefacts_from_sheet_anchors(
        [{"kind": "table_cell", "file": "supplementary/gone.csv", "cells": ["B2:B9"]}], paper)
    assert art["found"] is False and art["kind"] == "csv"
    issues = [{"anchors": [{"kind": "page_bbox", "page": 1}], "artefacts": []},
              {"anchors": [{"kind": "table_cell", "file": "x.csv", "cells": ["A1"]}], "artefacts": []}]
    stamp_sheet_artefacts(issues, paper)
    assert issues[0]["artefacts"] == [] and issues[1]["artefacts"][0]["basename"] == "x.csv"


def test_sheet_preview_refuses_a_zip_bomb_and_bounds_a_giant_csv_line(tmp_path):
    """The sheet pane parses an author's supplementary file inside the service
    every reviewer shares (security review, 2026-11-10). A workbook whose
    shared strings inflate far beyond their packed size is refused before
    openpyxl loads them; a CSV line of any length is read in bounded pieces."""
    import zipfile
    import openpyxl
    from forensic_metascience_ai_toolkit import finding_files as ff
    good = tmp_path / "good.xlsx"
    wb = openpyxl.Workbook(); wb.active.append(["a", 1]); wb.save(good)
    assert ff.read_sheet(good)["rows"] == [["a", "1"]]
    bomb = tmp_path / "bomb.xlsx"
    with zipfile.ZipFile(good) as src, zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            out.writestr(item, src.read(item.filename))
        out.writestr("xl/sharedStrings.xml", b"<sst>" + b"A" * (30 * 1024 * 1024) + b"</sst>")
    assert bomb.stat().st_size < 1024 * 1024
    got = ff.read_sheet(bomb)
    assert got["rows"] == [] and "too large to preview" in got["error"]
    long = tmp_path / "long.csv"
    long.write_text("x,y\n" + "9" * (ff._MAX_CSV_LINE * 2 + 10) + ",1\nlast,2\n")
    seen = []
    real = ff._bounded_lines
    def spy(fh):
        for line in real(fh):
            seen.append(len(line)); yield line
    ff._bounded_lines = spy
    try: ff.read_sheet(long)
    finally: ff._bounded_lines = real
    assert seen and max(seen) <= ff._MAX_CSV_LINE
