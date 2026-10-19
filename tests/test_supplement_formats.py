"""
Every form a supplement arrives in reaches the same `cells` contract -- or
refuses in a way that cannot be mistaken for "there was nothing there".

WHAT PROMPTED THIS. `extract_supplement` read `.docx`, `.xlsx` and `.csv`.
MEASURED over the corpora in this repo, supplementary files are: 357 PDF, 121
JPG, 21 PNG, 15 XML, 7 TXT, 7 HTML, 3 DOCX, 1 XLSX. So the reader covered 4 of
531 files, and the two formats carrying 95% of supplementary material -- PDF and
images -- were the two it could not open. A paper whose eTables live in a
supplementary PDF was reviewed as though it had none, and `.pdf` did not even
reach a named refusal: it fell through to "unsupported supplement format".

The contract each test defends is that the DOWNSTREAM chain does not care where
a table came from: `extract_supplement(...)["tables"][i]["cells"]` goes to
`parse_cells_typed` -> `check_table` whether the file was a spreadsheet, a
publisher HTML page, an EPUB or a scanned image.
"""

import csv
import json
import zipfile

import pytest

from forensic_metascience_ai_toolkit.extraction.supplements_read import (
    IMAGE_SUFFIXES,
    READABLE,
    UNREADABLE,
    extract_supplement,
    extract_supplement_full,
)

fitz = pytest.importorskip("fitz")


#: A one-page document needs at least `_MIN_SINGLE_PAGE_CHARS` (150) of text
#: before `readable_body_chars` will call it readable -- on a single page no line
#: can be shown to be a repeated stamp, so length is the only signal left. A
#: fixture that is only a table is therefore indistinguishable from a scan, and
#: correctly so. Real supplements carry a caption and a footnote; this one does
#: too, for the same reason.
_SI_PROSE = ("eTable 1. Baseline characteristics of the analysed sample. "
             "Values are mean (standard deviation) unless otherwise stated. "
             "Two participants were excluded before analysis for incomplete "
             "baseline measurement.")


#: The grid the fixture below draws, and the grid docling reads back off it.
#: MEASURED 2026-08-17: a live `extract_pdf_tables` on that one-page fixture
#: returns exactly these three rows, cell for cell -- and takes 91.4 s, which is
#: why the cache is written rather than earned.
_RULED_ROWS = [["Variable", "Mean (SD)", "n"],
               ["Age", "48.90 (14.46)", "49"],
               ["BMI", "24.10 (3.20)", "49"]]


def _ruled_table_pdf(path):
    """A ruled-table PDF **and the docling cache for it**, because the PDF
    reader is CACHE-ONLY now.

    WHAT CHANGED (2026-08-16). `extraction.pdf` is docling-only, and neither
    `extract_text` nor `extract_text_with_tables` will run the layout model:
    they read the extraction cache and refuse when it is absent. A fixture
    written into `tmp_path` therefore looks to the reader like an UNEXTRACTED
    paper -- it comes back `unreadable`, and `extract_supplement_full` reroutes
    it to OCR.

    That reroute is why this helper now writes a cache. Without one the tests
    below still PASSED, but they had silently changed subject: from "a
    born-digital supplement is read from its text layer" to "rapidocr can
    transcribe a rendering of it". Different claim, different machine
    dependency, and no longer the thing this class exists to defend. The
    original ruling is kept because the fixture depicts a ruled table; it is the
    missing cache, not missing ruling, that used to route it to OCR.

    Writing the schema-4 entry docling would have written is the pattern
    `tests/test_unreadable_inputs.py` and `tests/test_jats.py` already use, for
    the reason recorded in `docling_tables`: running the real extractor from a
    test is minutes per paper (91.4 s for this single page), and putting it in a
    read path is the regression measured there three times.

    Nothing here is invented for the cache. The grid is the same `_RULED_ROWS`
    the fixture draws and the live run returns; the page text is read back out
    of the file, so editing the fixture cannot leave the cache describing a
    document that no longer exists.
    """
    from forensic_metascience_ai_toolkit.extraction import docling_tables as dl

    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(72, 60, 520, 100), _SI_PROSE, fontsize=9)
    x = [72, 220, 380, 470]
    y = [120, 150, 180, 210]
    for r, row in enumerate(_RULED_ROWS):
        for c, cell in enumerate(row):
            page.insert_text((x[c] + 4, y[r] + 20), cell, fontsize=11)
    for gx in x:
        page.draw_line(fitz.Point(gx, y[0]), fitz.Point(gx, y[-1] + 30))
    for gy in [*y, y[-1] + 30]:
        page.draw_line(fitz.Point(x[0], gy), fitz.Point(x[-1], gy))
    doc.save(str(path))
    doc.close()

    read_back = fitz.open(str(path))
    pages = [{"page_num": i + 1, "text": p.get_text() or ""}
             for i, p in enumerate(read_back)]
    read_back.close()
    text = "\n\n".join(p["text"] for p in pages)

    # Keyed through the reader's own `_cache_path`, so a change to how caches
    # are named breaks this loudly instead of missing every time and quietly
    # sending the whole class back through OCR.
    cache = dl._cache_path(path)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps({
            "text": text,
            "tables": [{"table_num": 1, "page": 1, "data": _RULED_ROWS}],
            "error": None, "n_tables": 1, "n_text_chars": len(text),
            "pages": pages, "num_pages": len(pages),
            "source_format": "pdf", "extractor": "docling", "cache_schema": 4,
        }),
        encoding="utf-8",
    )
    return path


SUPPLEMENT_HTML = """<html><body>
<h1>Supplementary Tables</h1>
<table><caption>eTable 1. Baseline characteristics</caption>
<thead><tr><th>Variable</th><th>Mean (SD)</th><th>n</th></tr></thead>
<tbody>
<tr><td>Age</td><td>48.90 (14.46)</td><td>49</td></tr>
<tr><td>BMI</td><td>24.10 (3.20)</td><td>49</td></tr>
</tbody></table></body></html>"""


class TestTheFormatCensusIsCovered:
    def test_pdf_is_readable_rather_than_unsupported(self):
        """357 corpus files, and the reader's answer was "unsupported"."""
        assert ".pdf" in READABLE
        assert ".pdf" not in UNREADABLE

    def test_images_are_not_declared_unreadable(self):
        """Whether an image can be read is a property of the MACHINE (is an OCR
        engine installed?), not of the file. Listing them in UNREADABLE stated
        it as a property of the file, permanently."""
        assert not (IMAGE_SUFFIXES & set(UNREADABLE))
        assert IMAGE_SUFFIXES <= READABLE

    def test_what_stays_unreadable_stays_named(self):
        """The refusal IS the result for these, and it names the format so a
        reader knows what to convert."""
        assert set(UNREADABLE) == {".doc", ".xls", ".zip", ".tex"}



def _extract_first(path):
    """Record that we LOOKED, without running the layout model.

    ADDED 2026-08-17, then immediately corrected. Reads are cache-only now, so
    an unextracted PDF reports `unextracted: True` and `no_text_layer: False`
    -- UNKNOWN, deliberately, because "we have not looked" is not "the file has
    no text layer". Reaching the scan branch therefore requires a cache.

    The first version got that cache by calling docling for real. That put LIVE
    EXTRACTION BACK INTO THE SUITE -- the fourth time in this codebase -- and
    under `-n 10` it produced 24 timeouts and took the run from 4:10 to 9:45.
    Extraction is an explicit step; a test asserting a downstream branch does
    not need the model, only the cache entry that branch keys on.

    So write the entry directly. Empty text with real pages is exactly what a
    genuine scan produces, which is the state under test.
    """
    from forensic_metascience_ai_toolkit.extraction.docling_tables import _cache_path
    import json
    c = _cache_path(path)
    c.parent.mkdir(parents=True, exist_ok=True)
    c.write_text(json.dumps({
        "tables": [], "text": "", "error": None,
        "n_tables": 0, "n_text_chars": 0,
        "pages": [{"page_num": 1, "text": ""}, {"page_num": 2, "text": ""}],
        "num_pages": 2, "references": "", "n_reference_chars": 0,
        "references_boundary": None, "references_found_by": "empty",
        "source_format": "pdf", "extractor": "docling",
        "extractor_version": "test-fixture", "cache_schema": 4,
        "notes": ["synthetic cache: the file was looked at and yielded no text"],
    }), encoding="utf-8")
    return path


class TestPdfSupplements:
    def test_a_pdf_supplement_yields_typed_cells(self, tmp_path):
        """The whole point: the same `cells` a .docx supplement produces, so the
        `parse_cells_typed` -> `check_table` chain is unchanged."""
        got = extract_supplement_full(_ruled_table_pdf(tmp_path / "si.pdf"))
        assert got["source_format"] == "pdf"
        assert got["n_tables"] >= 1
        table = got["tables"][0]
        assert table["cells"], "a supplementary PDF table produced no cells"
        raws = {c["raw"] for c in table["cells"]}
        assert "48.90 (14.46)" in raws
        assert table["page"] == 1

    def test_the_cells_survive_the_typing_chain(self, tmp_path):
        """A cell that cannot be typed is a cell no check can use, so the
        contract has to be verified through the consumer, not at the boundary."""
        from forensic_metascience_ai_toolkit.tools.celltypes import parse_cells

        got = extract_supplement_full(_ruled_table_pdf(tmp_path / "si.pdf"))
        cells = got["tables"][0]["cells"]
        typed = parse_cells(cells)
        kinds = {c["kind"] for c in typed["cells"]}
        assert kinds - {"non_numeric"}, f"nothing typed: {typed['cells']}"

    def test_a_read_grid_says_the_columns_were_read(self, tmp_path):
        """RETARGETED 2026-08-17. Was `test_a_ruled_grid_says_it_was_ruled`,
        asserting `grid_strategy == "ruled"`.

        THE LABEL IS GONE WITH pdfplumber, THE QUESTION IS NOT. `ruled` and
        `text_alignment` named which of pdfplumber's two passes produced the
        grid, and a consumer read them to answer one thing: were these column
        boundaries READ off the document, or invented? Docling reads the
        document's own structure, so there is a single label -- but `check_table`
        still must not treat an inferred grid as a read one, so the disclosure
        still has to arrive, and this asserts all of it: a named extractor,
        `alignment_uncertain` false, no OCR provenance, and no caveat attached.

        Asserting `== "docling"` rather than merely "not text_alignment" on
        purpose. A missing key reads as false in the loose form -- which is
        exactly how this test failed rather than lying when the reroute landed
        (KeyError, not a silent pass) -- and the loose form would have passed on
        the OCR path, whose columns nobody read at all.

        What a grid nobody read looks like is the next test.
        """
        got = extract_supplement_full(_ruled_table_pdf(tmp_path / "si.pdf"))
        table = got["tables"][0]
        assert table["grid_strategy"] == "docling"
        assert table["alignment_uncertain"] is False
        assert table.get("provenance") != "ocr_table"
        assert not table["warnings"]

    def test_a_grid_nobody_read_declares_itself_uncertain(self, tmp_path):
        """RETARGETED 2026-08-17. Was
        `test_an_inferred_grid_declares_itself_uncertain`, asserting
        `grid_strategy == "text_alignment"`.

        THE OLD MECHANISM IS DELETED. pdfplumber's text-alignment fallback
        invented column boundaries from where words happened to line up, and the
        flag existed to stop `check_table` reading an invented grid as a read
        one: a value can land under the wrong heading, and a pair split across a
        boundary nobody drew is a pair the paper never printed.

        THE PROPERTY IS UNCHANGED, and cells whose columns nobody read are still
        reachable -- by a different route. `extraction.pdf` is cache-only, so an
        unextracted PDF is refused (naming `metascience extract-tables`) and
        `extract_supplement_full` reroutes it to OCR, which infers columns from a
        rendering. MEASURED on this fixture: rapidocr returns a grid and reports
        two recognised words straddling a column boundary. Those cells must
        never arrive looking read, and the refusal must never arrive looking
        like an empty supplement.

        The fixture is left unruled so it still depicts a grid no line was drawn
        for, but note what now routes it here is the ABSENT CACHE, not the
        absent ruling -- `_ruled_table_pdf` would land in the same place if its
        cache were not written for it.
        """
        doc = fitz.open()
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(72, 60, 520, 100), _SI_PROSE, fontsize=9)
        for r, row in enumerate([["Age", "48.90", "49"],
                                 ["BMI", "24.10", "49"],
                                 ["Score", "5.51", "30"],
                                 ["Days", "12.30", "44"]]):
            for c, cell in enumerate(row):
                page.insert_text((72 + c * 150, 120 + r * 30), cell, fontsize=11)
        path = tmp_path / "unruled.pdf"
        doc.save(str(path))
        doc.close()

        got = extract_supplement_full(path)
        # The refusal names the command that fixes it. Without this the caller
        # is told only that something went wrong, which is how OUR unextracted
        # PDF becomes a claim about the paper.
        assert "extract-tables" in (got.get("pdf_error") or "")

        # AND IT DOES NOT OCR. Corrected 2026-08-17, hours after the retarget
        # described above: rerouting an UNEXTRACTED PDF to OCR was itself the
        # bug. It stamped `no_text_layer: True` on born-digital files -- a
        # positive, FALSE claim about the publication, with OCR'd numbers
        # carrying `ocr_table` provenance into forensic checks -- and on the
        # JAMA eAppendices it rendered a 1.1 MB, 62-table supplement to PNG
        # page by page, pinning four xdist workers for over an hour each and
        # wedging the suite at 98%.
        #
        # OCR is now reached only when the file WAS extracted and still yielded
        # nothing, which is the real scan signal. "We have not looked" and "the
        # file has no text layer" are opposite facts; the OCR cost is only
        # justified by the second.
        assert got.get("unextracted") is True
        assert got.get("no_text_layer") is False, (
            "an unread PDF must not be reported as having no text layer -- "
            "that is our gap asserted as a property of the file")
        assert got.get("tables") == []
        assert got.get("provenance") != "ocr_table"

    def test_a_scanned_pdf_reports_the_missing_text_layer_not_an_empty_result(
            self, tmp_path):
        """A born-digital PDF with no tables and a scan both return zero tables
        and mean opposite things. `no_text_layer` is the fact that separates
        them, and it is what says OCR is the route in."""
        from forensic_metascience_ai_toolkit.extraction import ocr

        doc = fitz.open()
        for _ in range(2):
            doc.new_page()          # blank pages: no text layer at all
        path = tmp_path / "scan.pdf"
        doc.save(str(path))
        doc.close()
        got = extract_supplement_full(_extract_first(path))
        assert got.get("no_text_layer") is True
        if not ocr.engine_status()["available"]:
            assert got["ocr_unavailable"] is True


class TestImageSupplements:
    def test_an_image_refusal_is_about_this_machine_not_the_file(self, tmp_path):
        """THE DISTINCTION THIS REPO KEEPS PAYING FOR. `no OCR engine here` and
        `this file has no tables` must never arrive in the same shape: the
        second is a claim about the authors, and it would be written out of a
        missing package."""
        from forensic_metascience_ai_toolkit.extraction import ocr

        path = tmp_path / "etable1.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        got = extract_supplement(path)
        if ocr.engine_status()["available"]:
            pytest.skip("an OCR engine is installed; this is the no-engine case")
        assert got["ocr_unavailable"] is True
        assert got["tables"] == []
        assert "NOT of the document" in got["error"]
        assert got["remedy"]

    def test_an_image_is_not_refused_by_extension(self, tmp_path):
        """It used to be refused before anything looked at it, permanently and
        regardless of what was installed."""
        path = tmp_path / "etable1.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        got = extract_supplement(path)
        assert got.get("unreadable_format") != ".png"


class TestHtmlSupplements:
    def test_an_html_supplement_yields_cells(self, tmp_path):
        path = tmp_path / "si.html"
        path.write_text(SUPPLEMENT_HTML, encoding="utf-8")
        got = extract_supplement_full(path)
        assert got["n_tables"] == 1
        raws = {c["raw"] for c in got["tables"][0]["cells"]}
        assert "48.90 (14.46)" in raws

    def test_a_supplement_is_not_refused_for_failing_to_be_the_article(
            self, tmp_path):
        """`validate_t2` asks "is this the article?" -- title, abstract, DOI,
        body length. A supplementary tables page is legitimately none of those,
        so running that check here would refuse real supplements for the wrong
        question. The blatant cookie-wall check still applies."""
        path = tmp_path / "si.html"
        path.write_text(SUPPLEMENT_HTML, encoding="utf-8")
        assert not extract_supplement_full(path).get("error")

    def test_a_paywall_page_saved_as_a_supplement_is_still_refused(self, tmp_path):
        """Relaxing the article check must not relax the decoy check: a cookie
        wall saved under a supplement's name is exactly as useless."""
        path = tmp_path / "si.html"
        wall = ("<html><body>" + "<p>Just a moment... Checking your browser. "
                "Please enable cookies. Access denied.</p>" * 12 + "</body></html>")
        path.write_text(wall, encoding="utf-8")
        got = extract_supplement_full(path)
        assert got.get("error")


class TestEpubSupplements:
    def test_an_epub_is_read_without_a_new_dependency(self, tmp_path):
        """An EPUB is a zip of XHTML and the HTML table builder already exists.
        `ebooklib` is not installed and is not needed."""
        path = tmp_path / "si.epub"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
            z.writestr("OEBPS/ch1.xhtml", SUPPLEMENT_HTML)
        got = extract_supplement_full(path)
        assert got["source_format"] == "epub"
        assert got["n_tables"] == 1
        raws = {c["raw"] for c in got["tables"][0]["cells"]}
        assert "48.90 (14.46)" in raws

    def test_a_corrupt_epub_refuses_rather_than_returning_nothing(self, tmp_path):
        path = tmp_path / "si.epub"
        path.write_bytes(b"not a zip")
        assert extract_supplement_full(path)["error"]


class TestTextSupplements:
    def test_plain_text_returns_its_text_and_guesses_no_columns(self, tmp_path):
        """A whitespace-column guess over a readme produces a grid nobody
        printed -- the same invention the PDF path needed `_looks_tabular` to
        gate, back when a text-alignment fallback could make one. That gate went
        with pdfplumber on 2026-08-16 because docling reads structure instead of
        guessing at it; this reader has no layout model, so the policy is all it
        has and the policy stays. The empty `tables` list is stated as OUR
        policy, not as a fact about the file."""
        path = tmp_path / "readme.txt"
        path.write_text("Age  48.90 (14.46)  49\nBMI  24.10 (3.20)  49\n")
        got = extract_supplement_full(path)
        assert "48.90" in got["text"]
        assert got["tables"] == []
        assert any("does not infer columns" in w for w in got["warnings"])


class TestXmlSupplements:
    def test_a_jats_supplement_routes_to_the_xml_reader(self, tmp_path):
        path = tmp_path / "si.xml"
        path.write_text(
            "<article><body><sec><table-wrap id='t1'><label>eTable 1</label>"
            "<table><thead><tr><th>Variable</th><th>Mean (SD)</th></tr></thead>"
            "<tbody><tr><td>Age</td><td>48.90 (14.46)</td></tr></tbody>"
            "</table></table-wrap></sec></body></article>", encoding="utf-8")
        got = extract_supplement_full(path)
        assert got["source_format"] == "xml"
        assert got["n_tables"] == 1
        raws = {c["raw"] for c in got["tables"][0]["cells"]}
        assert "48.90 (14.46)" in raws


class TestTheOldBehaviourIsPreserved:
    def test_csv_still_works(self, tmp_path):
        path = tmp_path / "si.csv"
        with path.open("w", newline="") as handle:
            csv.writer(handle).writerows([["Var", "V"], ["Age", "12.3"]])
        assert extract_supplement(path)["tables"][0]["rows"] == [["Age", "12.3"]]

    def test_a_corrupt_file_still_returns_an_error_rather_than_raising(
            self, tmp_path):
        path = tmp_path / "si.docx"
        path.write_bytes(b"not really a docx")
        got = extract_supplement(path)
        assert got["error"] and got["tables"] == []

    def test_a_missing_file_still_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            extract_supplement(tmp_path / "nope.pdf")
