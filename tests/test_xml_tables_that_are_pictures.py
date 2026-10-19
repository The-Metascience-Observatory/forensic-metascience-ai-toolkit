"""Publisher XML outranks a PDF extraction -- unless its tables are pictures.

AHA/Stroke ships full-text JATS whose `<table-wrap>` holds a `<graphic>` and no
`<tr>`. `paper_tables` returned those as tables with zero cells, and because XML
wins precedence the paper then had NO table content at all.

MEASURED 2026-08-19 over the eleven prioritised cerebrolysin papers: five ship
XML, and on two of them every table is a JPEG. 265 cells docling had already
read from the PDF were being discarded -- on CARS and ESCAS, two of the trials
the review is about.

`get_table` had said so all along: `image_only: True`, a `graphic_href`, and the
warning "table is an image in the XML and has no cells; extract it from the PDF
or record it as unchecked". The walker read that answer and dropped it. This is
the third defect of that exact shape found today -- docling's `column_header`
flag and the fetcher's own filenames were the other two.
"""

from pathlib import Path

import pytest

from metascience_agent.prepass import paper_tables

XML_HEAD = ('<?xml version="1.0"?><article xmlns:xlink="http://www.w3.org/1999/xlink">'
            "<front><article-meta><title-group><article-title>T</article-title>"
            "</title-group></article-meta></front><body>")
XML_TAIL = "</body></article>"

PICTURE = ('<table-wrap id="T{i}"><label>Table {i}.</label>'
           "<caption><p>Baseline</p></caption>"
           '<graphic xlink:href="g00{i}.jpg"/></table-wrap>')

MARKUP = ('<table-wrap id="T{i}"><label>Table {i}.</label>'
          "<caption><p>Baseline</p></caption><table>"
          "<thead><tr><th>Arm</th><th>n</th></tr></thead>"
          "<tbody><tr><td>Drug</td><td>19</td></tr></tbody>"
          "</table></table-wrap>")


def _paper(tmp_path, wraps, with_pdf_cache=True):
    stem = "10.1161--demo"
    d = tmp_path / stem
    d.mkdir()
    (d / f"{stem}.xml").write_text(XML_HEAD + "".join(wraps) + XML_TAIL,
                                   encoding="utf-8")
    pdf = d / f"{stem}.pdf"
    pdf.write_bytes(b"%PDF-1.4\ntrailer\n")
    if with_pdf_cache:
        import json

        from metascience_agent.extraction import docling_tables as dl

        c = dl._cache_path(pdf)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps({
            "cache_schema": 6, "text": "body", "error": None,
            "pages": [{"page_num": 1, "text": "body"}],
            "tables": [{"label": "Table 1", "n_header_rows": 1,
                        "cells": [{"raw": "19", "row": 1,
                                   "row_label": "Drug", "col_label": "n"}]}],
        }), encoding="utf-8")
    return d


class TestAPictureIsNotAReading:
    def test_all_pictures_falls_through_to_the_pdf(self, tmp_path):
        d = _paper(tmp_path, [PICTURE.format(i=1), PICTURE.format(i=2)])
        tables = paper_tables(d)
        assert sum(len(t.get("cells") or []) for t in tables) == 1, (
            "the XML carries no cells and the PDF's were discarded")

    def test_it_says_why_rather_than_switching_silently(self, tmp_path):
        d = _paper(tmp_path, [PICTURE.format(i=1)])
        problems = getattr(paper_tables(d), "problems", None) or []
        assert any("picture in the XML" in p for p in problems)
        assert any("PDF was read instead" in p for p in problems)

    def test_the_xml_is_still_the_authority_for_everything_else(self, tmp_path):
        # Falling through for TABLES must not be read as distrusting the markup.
        d = _paper(tmp_path, [PICTURE.format(i=1)])
        problems = getattr(paper_tables(d), "problems", None) or []
        assert any("remains the authority" in p for p in problems)


class TestGoodMarkupIsNotTradedAway:
    def test_markup_tables_still_win(self, tmp_path):
        d = _paper(tmp_path, [MARKUP.format(i=1)])
        tables = paper_tables(d)
        assert any(c["raw"] == "19" for t in tables for c in t["cells"])
        assert not any("picture in the XML" in p
                       for p in (getattr(tables, "problems", None) or []))

    def test_one_picture_among_real_tables_does_not_trigger_it(self, tmp_path):
        # ALL, not ANY. A partial XML is still the better reading; the picture
        # stays empty and stays reported, which is the honest state.
        d = _paper(tmp_path, [MARKUP.format(i=1), PICTURE.format(i=2)])
        tables = paper_tables(d)
        assert len(tables) == 2
        assert sum(len(t.get("cells") or []) for t in tables) == 1
        assert not any("picture in the XML" in p
                       for p in (getattr(tables, "problems", None) or []))

    def test_the_picture_is_marked_so_a_reader_can_see_it(self, tmp_path):
        d = _paper(tmp_path, [MARKUP.format(i=1), PICTURE.format(i=2)])
        pictures = [t for t in paper_tables(d) if t.get("image_only")]
        assert len(pictures) == 1 and pictures[0]["cells"] == []


class TestNoPdfToFallBackOn:
    def test_it_does_not_pretend_the_pdf_answered(self, tmp_path):
        # No cache, so the PDF cannot be read either. The answer is a REPORTED
        # failure, never a quiet empty list.
        d = _paper(tmp_path, [PICTURE.format(i=1)], with_pdf_cache=False)
        tables = paper_tables(d)
        assert sum(len(t.get("cells") or []) for t in tables) == 0
        problems = getattr(tables, "problems", None) or []
        assert any("picture in the XML" in p for p in problems)
        assert len(problems) >= 2, "the PDF's own failure must be reported too"
