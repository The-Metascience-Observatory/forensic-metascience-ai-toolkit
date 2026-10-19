"""Portable finding-file paths: never absolute, never outside the paper dir."""
import json
from pathlib import Path

from metascience_agent.finding_files import (
    artefacts_for_editorial, artefacts_from_sweep_finding, relativize,
    resolve, read_sheet,
)
from metascience_agent.review_issues import collect_issues


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


def test_join_editorial_to_sweep_path(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    xlsx = paper / "cars.xlsx"
    xlsx.write_bytes(b"x")
    sweep = {
        "id": "supplement_qaly_raw_duplication",
        "inputs": {"path": "cars.xlsx", "sheet": "QALY"},
        "computed": {},
    }
    editorial = {
        "title": "duplicated rows",
        "stage1_finding_ids": ["supplement_qaly_raw_duplication"],
        "location": "Supplementary data file, 'QALY' sheet",
    }
    arts = artefacts_for_editorial(editorial, {sweep["id"]: sweep}, paper)
    assert len(arts) == 1
    assert arts[0]["found"] is True
    assert arts[0]["kind"] == "xlsx"
    assert arts[0]["relpath"] == "cars.xlsx"
    assert arts[0]["sheet"] == "QALY"
    assert arts[0]["confidence"] == "file"


def test_quoted_sheet_in_location_fills_missing_inputs_sheet(tmp_path):
    """Sweep recorded the file but not the worksheet; location named it in quotes."""
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "cars.xlsx").write_bytes(b"x")
    sweep = {
        "id": "supplement_qaly_raw_duplication",
        "inputs": {"path": "cars.xlsx"},
        "computed": {},
    }
    editorial = {
        "stage1_finding_ids": ["supplement_qaly_raw_duplication"],
        "location": "Supplementary data file, 'QALY' sheet (193 rows)",
    }
    arts = artefacts_for_editorial(editorial, {sweep["id"]: sweep}, paper)
    assert arts[0]["sheet"] == "QALY"


def test_no_path_is_empty_not_a_guess(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    editorial = {
        "stage1_finding_ids": ["something"],
        "location": "Supplementary data file, 'QALY' sheet",
    }
    assert artefacts_for_editorial(editorial, {}, paper) == []


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


def test_collect_issues_attaches_artefacts(tmp_path):
    paper = tmp_path / "p"
    review = paper / "forensic_review"
    review.mkdir(parents=True)
    (paper / "cars.xlsx").write_bytes(b"x")
    (review / "report.json").write_text(json.dumps({
        "findings": [{
            "title": "dup rows", "severity": "highly_suspicious",
            "plain": "rows match", "location": "QALY sheet",
            "stage1_finding_ids": ["supplement_qaly_raw_duplication"],
            "rank": 1, "warrant": "logical",
        }],
    }))
    (review / "findings.json").write_text(json.dumps({
        "findings": [{
            "id": "supplement_qaly_raw_duplication",
            "inputs": {"path": "/old/host/cars.xlsx"},
            "technique": "raw_duplication",
        }],
    }))
    issues = collect_issues(paper)["issues"]
    assert issues
    arts = issues[0].get("artefacts") or []
    assert arts and arts[0]["found"] is True
    assert arts[0]["basename"] == "cars.xlsx"


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
