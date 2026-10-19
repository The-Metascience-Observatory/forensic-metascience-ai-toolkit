"""Shape-matched repair of broken symbol-font characters (`extraction.glyph_repair`).

The synthetic PDF reproduces the schnall2008 defect exactly: an embedded CFF
font named `AdvMPi-One` whose glyph for the code `5` DRAWS `=`, so every
extractor reports `5`. Beside it, body-font digits `15` and `25` that are
genuinely fives, a `<` the symbol font draws correctly, and an irregular glyph
that matches no reference character.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
pytest.importorskip("fontTools")
pytest.importorskip("cv2")

from forensic_metascience_ai_toolkit.extraction import glyph_repair as gr  # noqa: E402


def _rect(pen, x0, y0, x1, y1):
    pen.moveTo((x0, y0))
    pen.lineTo((x1, y0))
    pen.lineTo((x1, y1))
    pen.lineTo((x0, y1))
    pen.closePath()


def _broken_font() -> bytes:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    order = [".notdef", "five", "less", "r"]
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({ord("5"): "five", ord("<"): "less", ord("r"): "r"})
    cs = {}
    p = T2CharStringPen(600, None)
    _rect(p, 0, 0, 500, 700)
    cs[".notdef"] = p.getCharString()
    p = T2CharStringPen(667, None)          # code `5`, drawn as `=`
    _rect(p, 60, 120, 600, 170)
    _rect(p, 60, 330, 600, 380)
    cs["five"] = p.getCharString()
    p = T2CharStringPen(667, None)          # code `<`, drawn as `<`
    for pt in ((600, 520), (70, 270), (600, 20), (600, 70), (170, 270), (600, 470)):
        (p.lineTo if pt != (600, 520) else p.moveTo)(pt)
    p.closePath()
    cs["less"] = p.getCharString()
    p = T2CharStringPen(600, None)          # code `r`, drawn as nothing we know
    for pt in ((50, 0), (550, 90), (300, 650), (420, 200), (90, 420)):
        (p.lineTo if pt != (50, 0) else p.moveTo)(pt)
    p.closePath()
    cs["r"] = p.getCharString()
    fb.setupCFF("AdvMPi-One", {"FullName": "AdvMPi-One"}, cs, {})
    fb.setupHorizontalMetrics({".notdef": (600, 0), "five": (667, 0),
                               "less": (667, 0), "r": (600, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "AdvMPi-One", "styleName": "Regular",
                       "psName": "AdvMPi-One"})
    fb.setupOS2()
    fb.setupPost()
    b = io.BytesIO()
    fb.save(b)
    return b.getvalue()


LINES = [
    [("t(28) ", "b"), ("5", "s"), (" 2.20, p ", "b"), ("5", "s"),
     (" .04, with 15 participants", "b")],
    [("and M ", "b"), ("<", "s"), (" 3.50 for 25 people", "b")],
    [("odd mark ", "b"), ("r", "s"), (" here", "b")],
]
#: What docling makes of that page: the broken font's codes, verbatim.
DOCLING_TEXT = ("t(28) 5 2.20, p 5 .04, with 15 participants\n"
                "and M < 3.50 for 25 people\nodd mark r here")


@pytest.fixture(scope="module")
def broken_pdf(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("glyphs") / "paper.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_font(fontname="AdvMPi-One", fontbuffer=_broken_font())
    y = 100
    for line in LINES:
        x = 72
        for txt, kind in line:
            page.insert_text((x, y), txt, fontsize=11,
                             fontname="AdvMPi-One" if kind == "s" else "helv")
            x += (11 * 0.667 * len(txt) if kind == "s"
                  else fitz.get_text_length(txt, fontname="helv", fontsize=11))
        y += 20
    doc.save(str(path))
    return path


def test_the_synthetic_pdf_reproduces_the_defect(broken_pdf):
    with fitz.open(str(broken_pdf)) as doc:
        raw = doc[0].get_text()
    assert "t(28) 5 2.20, p 5 .04" in raw


class TestIdentification:
    def test_symbol_fonts_include_the_math_pi_families(self):
        for name in ("AdvMPi-One", "AdvPi1", "AdvP4C4E74", "CjhwjmAdvP4C4E74",
                     "MathematicalPi-One", "MathTechnicalP03", "MTSY",
                     "Universal-GreekwithMathPi"):
            assert gr.is_symbol_font(name), name
        for name in ("Helvetica", "MinionPro-Regular", "AdvBdw", "TimesNewRomanPSMT"):
            assert not gr.is_symbol_font(name), name

    def test_fontaudit_no_longer_misses_advmpi(self):
        from forensic_metascience_ai_toolkit.scaffold.fontaudit import _is_symbol_font
        assert _is_symbol_font("AdvMPi-One")
        assert not _is_symbol_font("Capitals")

    def test_each_glyph_is_identified_by_its_shape(self, broken_pdf):
        g = gr.glyph_map(broken_pdf)
        assert g["status"] == "repairable"
        rows = {r["extracted"]: r for r in g["glyphs"]}
        assert rows["5"]["decision"] == "repair" and rows["5"]["intended"] == "="
        assert rows["5"]["n"] == 2          # identified once, applied to both
        assert rows["<"]["decision"] == "kept"
        assert g["map"] == {"AdvMPi-One": {"5": "="}}

    def test_an_unidentifiable_glyph_is_left_as_is_and_reported(self, broken_pdf):
        g = gr.glyph_map(broken_pdf)
        refused = {r["extracted"]: r for r in g["refused"]}
        assert refused["r"]["decision"] == "ambiguous"
        assert "left as extracted" in refused["r"]["why"]
        assert "r" not in g["map"].get("AdvMPi-One", {})

    def test_text_fonts_are_never_candidates(self, broken_pdf):
        g = gr.glyph_map(broken_pdf)
        assert {r["font"] for r in g["glyphs"]} == {"AdvMPi-One"}

    def test_a_pdf_without_symbol_fonts_is_untouched(self, tmp_path):
        p = tmp_path / "plain.pdf"
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "t(28) = 2.20, p = .04", fontname="helv")
        doc.save(str(p))
        assert gr.glyph_map(p)["status"] == "no_symbol_fonts"
        data = {"text": "t(28) = 2.20, p = .04"}
        out = gr.apply_to_extraction(data, p)
        assert out["text"] == data["text"]
        assert out["glyph_repair"]["n_repaired"] == 0

    def test_an_unreadable_pdf_is_an_error_not_a_clean_result(self, tmp_path):
        p = tmp_path / "stub.pdf"
        p.write_text("version https://git-lfs.github.com/spec/v1\n")
        g = gr.glyph_map(p)
        assert g["status"] == "error" and g["error"]


class TestRepair:
    def test_docling_text_is_repaired_and_genuine_fives_survive(self, broken_pdf):
        data = {"text": DOCLING_TEXT}
        out = gr.apply_to_extraction(data, broken_pdf)
        assert out["text"].startswith("t(28) = 2.20, p = .04, with 15 participants")
        assert "for 25 people" in out["text"]
        assert "odd mark r here" in out["text"]       # refused: left as-is
        assert data["text"] == DOCLING_TEXT            # input not modified

    def test_every_edit_is_logged_as_a_repair(self, broken_pdf):
        out = gr.apply_to_extraction({"text": DOCLING_TEXT}, broken_pdf)
        rec = out["glyph_repair"]
        assert rec["n_repaired"] == 2 == len(rec["repairs"])
        for r in rec["repairs"]:
            assert r["rule"] == gr.RULE and r["target"] == "body"
            assert "5" in r["before"] and "=" in r["after"]
            assert DOCLING_TEXT[r["offset"]] == "5"   # offsets into the ORIGINAL
        assert rec["refused_glyphs"][0]["extracted"] == "r"

    def test_table_cells_and_pages_are_repaired_too(self, broken_pdf):
        data = {"text": DOCLING_TEXT,
                "pages": [{"page_num": 1, "text": DOCLING_TEXT}],
                "tables": [{"table_num": 1, "source": "paper.pdf",
                            "cells": [{"raw": "p 5 .04", "row": 1}],
                            "data": [["t(28) 5 2.20", "15"]]}]}
        out = gr.apply_to_extraction(data, broken_pdf)
        assert out["pages"][0]["text"].startswith("t(28) = 2.20")
        assert out["tables"][0]["cells"][0]["raw"] == "p = .04"
        assert out["tables"][0]["data"][0] == ["t(28) = 2.20", "15"]
        assert {r["target"] for r in out["glyph_repair"]["repairs"]} == {
            "body", "page:1", "table:1"}

    def test_a_context_that_also_matches_a_trusted_character_is_not_touched(
            self, broken_pdf):
        layer = {"cmp": "a5bxa5b", "target": [None, "=", None, None, None, None, None],
                 "pages": []}
        new, reps, unres = gr.repair_string("a 5 b", layer, frozenset("5"))
        assert new == "a 5 b" and not reps
        assert unres and "both" in unres[0]["why"]

    def test_the_pdf_text_layer_is_repaired_for_quote_verification(self, broken_pdf):
        layer = gr.repaired_text_layer(broken_pdf)
        assert "t(28) = 2.20, p = .04" in layer
        assert "15 participants" in layer

    def test_statcheck_reads_the_repaired_text(self, broken_pdf):
        from forensic_metascience_ai_toolkit.tools.r_wrappers import python_statcheck_text
        before = python_statcheck_text(DOCLING_TEXT)
        if not before.get("success"):
            pytest.skip("statcheck unavailable")
        after = python_statcheck_text(
            gr.apply_to_extraction({"text": DOCLING_TEXT}, broken_pdf)["text"])
        assert before.get("stats_found", 0) == 0
        assert after.get("stats_found", 0) == 1


class TestDoclingCache:
    def test_cache_readers_serve_the_repair_and_the_cache_keeps_the_original(
            self, broken_pdf, tmp_path):
        import shutil
        from forensic_metascience_ai_toolkit.extraction import docling_tables as dl
        pdf = tmp_path / "paper.pdf"
        shutil.copy(broken_pdf, pdf)
        cache = dl._cache_path(pdf)
        cache.parent.mkdir(parents=True)
        entry = {"text": DOCLING_TEXT, "tables": [], "error": None,
                 "pages": [{"page_num": 1, "text": DOCLING_TEXT}],
                 "cache_schema": dl.CACHE_SCHEMA}
        cache.write_text(json.dumps(entry))
        res = dl.extract_pdf_tables(pdf, allow_extract=False)
        assert res["text"].startswith("t(28) = 2.20")
        text, why = dl.cached_text(pdf)
        assert not why and text == res["text"]
        assert json.loads(cache.read_text())["text"] == DOCLING_TEXT

    def test_record_writes_the_ledger_and_replaces_its_own_entries(
            self, broken_pdf, tmp_path):
        from forensic_metascience_ai_toolkit import repairs
        rec = gr.apply_to_extraction({"text": DOCLING_TEXT}, broken_pdf)["glyph_repair"]
        gr.record(tmp_path, rec)
        gr.record(tmp_path, rec)
        log = repairs.load(tmp_path)
        assert log is not None and len(log.repairs) == 2
        assert all(r.rule == gr.RULE for r in log.repairs)
        assert not log.declares_body_md       # recording never redirects the reader


class TestAnalystNote:
    def test_note_names_the_font_and_the_substitution(self, broken_pdf):
        out = gr.apply_to_extraction({"text": DOCLING_TEXT}, broken_pdf)
        note = gr.analyst_note(".", out["text"], out["glyph_repair"])
        assert "AdvMPi-One" in note and "extracted as `5`, drawn as `=`" in note
        assert "could NOT be identified" in note and "`r`" in note
        assert "do NOT decode it yourself" in note

    def test_note_reports_unrepaired_corruption_from_the_glyph_scan(self):
        text = "t (10) 5 1.84, p 5 .09; t (11) 5 2.10, p 5 .05; F (1, 9) 5 3.2, p 5 .1"
        note = gr.analyst_note(".", text, None)
        assert "equals as digit 5" in note and "affects DIGITS" in note

    def test_clean_paper_gets_no_note(self):
        assert gr.analyst_note(".", "t(28) = 2.20, p = .04", None) == ""


#: A real Springer PDF in the repo whose Advent pi fonts draw `=` under the
#: code `¼` (cerebrolysin corpus). Pinned so a change to the matcher that loses
#: it, or starts changing a glyph it should not, is seen.
_S00702 = (Path(__file__).parent / "fixtures" / "papers" / "cerebrolysin_papers"
           / "10.1007--s00702-004-0248-2" / "10.1007--s00702-004-0248-2.pdf")


def test_real_advent_font_pdf(tmp_path):
    if not _S00702.is_file() or _S00702.stat().st_size < 10_000:
        pytest.skip("fixture PDF not checked out from LFS")
    g = gr.glyph_map(_S00702)
    assert g["map"].get("AdvP4C4E74", {}).get("¼") == "="
    # Every overturned label is in an Advent pi font, never a text font.
    assert all(gr.is_symbol_font(f) for f in g["map"])
