"""highlight_workbook: the artifact never raises and marks the right cells."""

from __future__ import annotations

import csv
import random

import pytest

from copy_paste_detector import detect_raw_duplication, highlight_workbook

openpyxl = pytest.importorskip("openpyxl")


def _planted_xlsx(tmp_path):
    rng = random.Random(7)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["id_code", "weight", "cortisol"])
    kept = []
    for i in range(1, 41):
        row = [f"p{i}", round(rng.uniform(52, 96), 2), round(rng.uniform(180, 620), 3)]
        kept.append(row)
        ws.append(row)
    # duplicate row 5 (sheet row 6) into row 30 (sheet row 31)
    for col, v in ((2, kept[4][1]), (3, kept[4][2])):
        ws.cell(row=31, column=col, value=v)
    p = tmp_path / "planted.xlsx"
    wb.save(p)
    return p


class TestHighlight:
    def test_marks_cells_and_comments_first(self, tmp_path):
        src = _planted_xlsx(tmp_path)
        res = detect_raw_duplication(str(src))
        assert res["duplicate_groups"], "fixture must produce at least one group"
        out = tmp_path / "h.xlsx"
        h = highlight_workbook(src, res["duplicate_groups"], out)
        assert not h.get("error")
        assert h["n_groups_highlighted"] >= 1
        book = openpyxl.load_workbook(str(out))
        ws = book["Data"]
        group = res["duplicate_groups"][0]
        cells = group.get("cells") or group.get("cells_a")
        marked = ws[cells[0]["cell"]]
        assert marked.fill.fgColor.rgb in {
            c
            for c in (
                "FFFFF2AC",
                "FFD3F0D1",
                "FFD6E4FF",
                "FFFFD9D1",
                "FFE8D9FF",
                "FFD1F0EC",
                "FFFFE1F0",
                "FFEDEFC8",
                "FFDCEBDD",
                "FFF0E0C8",
                "FFDDE7F5",
                "FFF5DDDD",
            )
        }
        assert marked.border.left.style == "thin"
        assert any(ws[c["cell"]].comment is not None for c in cells)

    def test_overlapping_groups_are_skipped_not_repainted(self, tmp_path):
        src = _planted_xlsx(tmp_path)
        res = detect_raw_duplication(str(src))
        groups = res["duplicate_groups"]
        doubled = groups + [dict(groups[0])]  # same cells again
        h = highlight_workbook(src, doubled, tmp_path / "h2.xlsx")
        assert not h.get("error")
        assert h["n_groups_skipped"] >= 1

    def test_csv_source_becomes_fresh_workbook(self, tmp_path):
        rng = random.Random(3)
        p = tmp_path / "d.csv"
        with p.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["a", "b"])
            for _ in range(20):
                w.writerow([round(rng.uniform(1, 9), 3), round(rng.uniform(100, 999), 3)])
            w.writerow([517.352, 812.406])
            w.writerow([517.352, 812.406])
        res = detect_raw_duplication(str(p))
        h = highlight_workbook(p, res["duplicate_groups"], tmp_path / "d.xlsx")
        assert not h.get("error")
        assert (tmp_path / "d.xlsx").exists()

    def test_never_raises(self, tmp_path):
        assert "error" in highlight_workbook(
            tmp_path / "missing.xlsx",
            [{"cells": [{"sheet": "S", "cell": "A1"}]}],
            tmp_path / "o.xlsx",
        )
        src = _planted_xlsx(tmp_path)
        assert "error" in highlight_workbook(src, [], tmp_path / "o.xlsx")
        assert "error" in highlight_workbook(
            tmp_path / "t.docx", [{"cells": [{"sheet": "S", "cell": "A1"}]}], tmp_path / "o.xlsx"
        )
