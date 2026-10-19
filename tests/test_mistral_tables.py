"""
Reading a Mistral OCR extraction, when one exists for a PDF.

Three things matter beyond "it parses":

* the reader must NEVER call the API -- a cheap enumeration that quietly spends
  money and blocks for minutes is the defect `allow_extract=False` exists to
  prevent;
* `None` (no extraction) and `[]` (an extraction showing no tables) are
  different answers, and collapsing them records a paper with tables as having
  none; and
* the output is an EXTRACTION and must say so. Nothing about a paid API makes a
  reading authoritative, and `xml_provenance` already draws this line for XML.
"""

import json

import pytest

from forensic_metascience_ai_toolkit.extraction import mistral_tables as mt

lxml = pytest.importorskip("lxml.html")


def _response(*fragments, model="mistral-ocr-latest", fmt="html"):
    return {
        "model": model,
        "pages": [{"index": 0,
                   "markdown": "body",
                   "tables": [{"id": f"tbl-{i}.html", "content": html,
                               "format": fmt}
                              for i, html in enumerate(fragments)]}],
    }


TWO_ROW = ("<table>"
           "<tr><td rowspan='2'></td><td colspan='2'>Treatment</td></tr>"
           "<tr><td>Drug (n = 78)</td><td>Placebo (n = 68)</td></tr>"
           "<tr><td>Age</td><td>65.1</td><td>66.2</td></tr>"
           "</table>")


def _cache(tmp_path, payload):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\ntrailer\n")
    path = mt.cache_path(pdf)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return pdf


class TestAbsenceIsNotEmptiness:
    def test_no_extraction_is_none_not_an_empty_list(self, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        problems: list[str] = []
        assert mt.pdf_tables(pdf, problems) is None

    def test_an_extraction_with_no_tables_is_an_empty_list(self, tmp_path):
        pdf = _cache(tmp_path, _response())
        problems: list[str] = []
        assert mt.pdf_tables(pdf, problems) == []
        assert problems == []

    def test_a_missing_extraction_is_not_reported_as_a_problem(self, tmp_path):
        # Almost no paper has one. Filing that as a problem would bury the
        # problems that are real.
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        problems: list[str] = []
        mt.pdf_tables(pdf, problems)
        assert problems == []

    def test_a_corrupt_cache_is_a_problem_and_is_named(self, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        path = mt.cache_path(pdf)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        problems: list[str] = []
        assert mt.pdf_tables(pdf, problems) is None
        assert problems and "unreadable" in problems[0]


class TestItSaysWhatProducedIt:
    def test_every_table_is_stamped_an_extraction(self, tmp_path):
        pdf = _cache(tmp_path, _response(TWO_ROW))
        tables = mt.pdf_tables(pdf)
        assert tables and all(t["extractor"] == "mistral" for t in tables)

    def test_the_model_travels_with_the_reading(self, tmp_path):
        pdf = _cache(tmp_path, _response(TWO_ROW, model="mistral-ocr-2505"))
        assert mt.pdf_tables(pdf)[0]["extractor_model"] == "mistral-ocr-2505"


class TestTheSpanWalkIsTheSharedOne:
    def test_a_stacked_header_keeps_each_column_distinct(self):
        tables = mt.tables_from_response(_response(TWO_ROW))
        assert tables[0]["n_header_rows"] == 2
        labels = [c["col_label"] for c in tables[0]["cells"]
                  if c["raw"] in ("65.1", "66.2")]
        assert len(set(labels)) == 2

    def test_the_group_sizes_reach_the_labels(self):
        from forensic_metascience_ai_toolkit.values import design_values_from_cells

        cells = mt.tables_from_response(_response(TWO_ROW))[0]["cells"]
        values = design_values_from_cells(cells, table="t1")
        assert sorted(v["value"] for v in values) == [68, 78]


class TestAFormatChangeIsAnnouncedNotSwallowed:
    def test_a_non_html_table_is_named_rather_than_skipped(self):
        problems: list[str] = []
        tables = mt.tables_from_response(_response("| a | b |", fmt="markdown"),
                                         problems)
        assert tables == []
        assert problems and "not html" in problems[0]

    def test_a_fragment_with_no_table_is_named(self):
        problems: list[str] = []
        assert mt.tables_from_response(_response("<p>nothing</p>"), problems) == []
        assert problems and "held no <table>" in problems[0]

    def test_unparseable_markup_is_not_reported_as_an_absent_table(self):
        # `lint-inert` caught the first version of this: one `return None` for
        # both "there was no table" and "we could not read it" files our failure
        # as a property of the paper. An empty `content` is the case that
        # actually reaches it -- lxml parses almost anything else.
        problems: list[str] = []
        assert mt.tables_from_response(_response(""), problems) == []
        assert problems
        assert "could not be parsed" in problems[0]
        assert "held no <table>" not in problems[0]


class TestItNeverReachesTheNetwork:
    def test_reading_a_cache_makes_no_request(self, tmp_path, monkeypatch):
        import urllib.request

        def explode(*_a, **_k):  # pragma: no cover - the point is it is not hit
            raise AssertionError("the reader tried to call out")

        monkeypatch.setattr(urllib.request, "urlopen", explode)
        pdf = _cache(tmp_path, _response(TWO_ROW))
        assert mt.pdf_tables(pdf)

    def test_the_module_holds_no_api_caller(self):
        import inspect

        source = inspect.getsource(mt)
        for token in ("api.mistral.ai", "requests.post", "urlopen", "httpx"):
            assert token not in source, f"{token} belongs in the extraction step"


class TestThePipelineActuallyUsesIt:
    """A reader nothing calls is a reader that changes nothing. Three modules
    written this month turned out to be built and unconsumed; this is the test
    that would have caught it."""

    def test_prepass_uses_the_extraction_when_the_text_layer_is_damaged(
            self, tmp_path):
        # With no docling cache the text cannot be checked, so this asserts the
        # WIRING, not the preference: see
        # `TestThePixelReadingIsNotAlwaysBetter` for the rule itself.
        from forensic_metascience_ai_toolkit.extraction import docling_tables as dl
        from forensic_metascience_ai_toolkit.prepass import paper_tables

        paper = tmp_path / "10.1234--demo"
        paper.mkdir()
        pdf = paper / "10.1234--demo.pdf"
        pdf.write_bytes(b"%PDF-1.4\ntrailer\n")
        mt.cache_path(pdf).parent.mkdir(parents=True, exist_ok=True)
        mt.cache_path(pdf).write_text(json.dumps(_response(TWO_ROW)),
                                      encoding="utf-8")
        dl._cache_path(pdf).write_text(json.dumps({
            "cache_schema": 6, "error": None, "tables": [],
            "text": "age 65.1 /C6 1.17 and 66.2 /C6 1.32 with p /C6 0.05 /C6 arms",
            "pages": [{"page_num": 1, "text": "x"}],
        }), encoding="utf-8")

        tables = paper_tables(paper)
        assert [t["extractor"] for t in tables] == ["mistral"]
        assert any("n = 78" in (c.get("col_label") or "")
                   for t in tables for c in t["cells"])

    def test_without_one_it_falls_through_to_docling(self, tmp_path):
        from forensic_metascience_ai_toolkit.prepass import paper_tables

        paper = tmp_path / "10.1234--plain"
        paper.mkdir()
        (paper / "10.1234--plain.pdf").write_bytes(b"%PDF-1.4\ntrailer\n")
        tables = paper_tables(paper)
        # No docling cache either, so the answer is a REPORTED failure rather
        # than a silent empty list -- which is what `_walked` carries.
        assert [t["extractor"] for t in tables] != ["mistral"]
        assert getattr(tables, "problems", None)


class TestThePixelReadingIsNotAlwaysBetter:
    """An earlier version preferred a Mistral extraction whenever one existed.
    That rested on a benchmark of 22 papers SELECTED FOR BEING DAMAGED, and
    reading a property of that sample as a property of extractors is a selection
    effect, not a finding.

    MEASURED on the eleven prioritised cerebrolysin papers, nine of them clean:
    Mistral 1,262 cells, docling 1,250 -- a tie, with docling ahead on four
    PDFs. It read 157 cells from CARS against Mistral's 108, and 45 from the
    CASTA data supplement where Mistral read none at all. So the question is
    about THIS pdf's text, not about which reader is better in general.
    """

    def _pdf_with(self, tmp_path, text):
        from forensic_metascience_ai_toolkit.extraction import docling_tables as dl

        paper = tmp_path / "10.1234--demo"
        paper.mkdir()
        pdf = paper / "10.1234--demo.pdf"
        pdf.write_bytes(b"%PDF-1.4\ntrailer\n")
        c = dl._cache_path(pdf)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps({
            "cache_schema": 6, "text": text, "error": None,
            "pages": [{"page_num": 1, "text": text}],
            "tables": [{"label": "Table 1", "n_header_rows": 1,
                        "cells": [{"raw": "42", "row": 1,
                                   "row_label": "Drug", "col_label": "n"}]}],
        }), encoding="utf-8")
        mt.cache_path(pdf).write_text(json.dumps(_response(TWO_ROW)),
                                      encoding="utf-8")
        return paper

    def test_a_clean_text_layer_keeps_docling(self, tmp_path):
        from forensic_metascience_ai_toolkit.prepass import paper_tables

        paper = self._pdf_with(tmp_path, "Mean age was 65.1 (SD 1.17) years.")
        assert [t["extractor"] for t in paper_tables(paper)] == ["docling"]

    def test_a_corrupt_text_layer_switches_to_the_pixels(self, tmp_path):
        from forensic_metascience_ai_toolkit.prepass import paper_tables

        # A PostScript glyph-name leak: the text layer naming glyphs it could
        # not map, which is exactly the damage the pixel reading is for.
        paper = self._pdf_with(tmp_path, "age 65.1 /C6 1.17 and 66.2 /C6 1.32 "
                                         "with p /C6 0.05 across /C6 arms")
        tables = paper_tables(paper)
        assert [t["extractor"] for t in tables] == ["mistral"]

    def test_the_switch_is_announced(self, tmp_path):
        from forensic_metascience_ai_toolkit.prepass import paper_tables

        paper = self._pdf_with(tmp_path, "age 65.1 /C6 1.17 and 66.2 /C6 1.32 "
                                         "with p /C6 0.05 across /C6 arms")
        problems = getattr(paper_tables(paper), "problems", None) or []
        assert any("character corruption" in p for p in problems)

    def test_it_fails_closed_to_the_text_layer(self, tmp_path):
        # No docling cache at all: we do not KNOW the text is damaged, and
        # swapping in the noisier reader on a maybe is not a decision to make
        # silently.
        from forensic_metascience_ai_toolkit.prepass import _text_layer_lies

        pdf = tmp_path / "x.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        assert _text_layer_lies(pdf, []) is False
