"""A file we could not read must not be reported as a paper with nothing in it.

Both extractors here returned a CONFIDENT EMPTY RESULT for a corrupt PDF:

* `extract_figures` gave `success: true, n_figures: 0, warnings: []`, which
  downstream is indistinguishable from a genuinely figureless paper.
* `extract_text_with_tables` gave `num_pages: 0, text: "", truncated: False` --
  and `truncated` is the field a caller checks to ask "is anything missing?".

Neither claim is about the paper. They are about a file that would not open,
and this tool's worst failure is a claim about a paper that came from something
other than the paper.

WHAT CHANGED, 2026-08-17. `extract_text_with_tables` is docling-only and
CACHE-ONLY: it no longer opens the PDF at all. It reads the extraction cache
and, when there is none, refuses and names the command that fills it (Greg,
2026-08-16: pdfplumber "should never run *anywhere* -- you determined it was
inferior to docling in every respect"). Every fixture below is built in a
`tmp_path` and so has no cache, which means the READABLE direction -- "this
document is a paper we read" -- could not be expressed at all: seven tests here
failed because a perfectly good three-page PDF now comes back `unreadable`.
`_extracted` writes the cache entry a completed `metascience extract-tables`
would have left, and its docstring says what that stand-in does and does not
cover.

The refusal is not a hole to patch, it is the shape OUR failure arrives in from
here on, so it is pinned rather than papered over: an unread document yields
`tables: []` WITH `unreadable: True` and an error saying the emptiness is a
fact about the extraction. That is what `TestTableExtractionFailureIsReported`
asserts now, in place of a pdfplumber monkeypatch it can no longer make against
machinery that no longer exists.
"""
import json
import textwrap
from pathlib import Path

import pytest

from metascience_observatory_image_analysis.extraction.figures import extract_figures
from forensic_metascience_ai_toolkit.extraction.pdf import extract_text_with_tables

fitz = pytest.importorskip("fitz")


#: Distinct body text per page. The pages of this fixture used to differ only
#: in a page number, which made it -- correctly -- indistinguishable from a
#: scan carrying a stamp: a document whose every page holds the same one line
#: has no content that varies across pages, and that is exactly what a
#: stamped scan is. Real papers do not look like that (MEASURED: 0 of 212 PDFs
#: across `high_value_pdfs_to_run_on` and `eval/ground_truth` reduce to zero
#: body text, the lowest real document being 163.7 body-chars per page), so
#: the fixture was the unrealistic half and it is the fixture that changed.
_BODY_LINES = [
    "Participants completed the task in a counterbalanced order.",
    "Reaction times were log-transformed before analysis.",
    "The interaction was significant, F(1, 38) = 7.21, p = .011.",
    "Effect sizes are reported as Hedges' g with 95% intervals.",
    "Data and analysis code are available at the project repository.",
]


def _real_pdf(path: Path, pages: int = 3) -> Path:
    """A small but genuinely valid PDF."""
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 100), f"Page {i + 1}. Figure 1. A chart.")
        page.insert_text((72, 130), _BODY_LINES[i % len(_BODY_LINES)])
    doc.save(str(path))
    doc.close()
    return path


def _zero_page_pdf(path: Path) -> Path:
    """A syntactically valid PDF whose page tree is EMPTY.

    Hand-built rather than truncated, because truncation is not deterministic
    across readers: a truncated file may land on an older cross-reference table
    and open with its pages intact. This one opens cleanly in both pdfplumber
    and PyMuPDF and reports zero pages in each -- the exact state a corrupt
    download leaves behind, with none of the flakiness.
    """
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    )
    xref_offset = len(body)
    xref = (b"xref\n0 3\n0000000000 65535 f \n"
            b"0000000009 00000 n \n0000000057 00000 n \n")
    trailer = (b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n"
               + str(xref_offset).encode() + b"\n%%EOF\n")
    path.write_bytes(body + xref + trailer)
    return path


def _truncated_pdf(path: Path, tmp_path: Path) -> Path:
    """A valid PDF cut short -- PyMuPDF opens it only by REPAIRING it.

    The cut point is SEARCHED FOR rather than fixed at half the bytes. A fixed
    fraction silently changes meaning whenever the fixture it cuts changes
    size: enlarging `_real_pdf` by one line per page moved the half-way point
    from "repairable" to "will not open at all", which is a different refusal
    and quietly stopped testing this one. The helper now asserts it produced
    the state the test is about, so a future fixture edit fails here with a
    clear reason instead of somewhere downstream with a puzzling one.
    """
    whole = _real_pdf(tmp_path / "_whole.pdf").read_bytes()
    for fraction in (0.5, 0.45, 0.4, 0.35, 0.33, 0.3, 0.25, 0.2):
        path.write_bytes(whole[: int(len(whole) * fraction)])
        try:
            doc = fitz.open(str(path))
        except Exception:
            continue          # too short to open at all -- not this test's case
        repaired, pages = doc.is_repaired, doc.page_count
        doc.close()
        if repaired and pages:
            return path
    raise AssertionError(
        "no truncation of this fixture produces a REPAIRED document; the "
        "fixture changed and this helper needs revisiting")


def _scanned_pdf(path: Path, pages: int = 6) -> Path:
    """A SCAN: valid pages, no text layer at all.

    The page bodies are drawings rather than text, which is what a scanned
    paper is -- one raster per page and nothing a text extractor can reach.
    """
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page()
        page.draw_rect(fitz.Rect(60, 60, 540, 780), color=(0, 0, 0), width=0.5)
    doc.save(str(path))
    doc.close()
    return path


def _stamped_scan_pdf(path: Path, pages: int = 8) -> Path:
    """A scan whose ONLY text is the publisher's stamp, repeated per page.

    This is not a hypothetical. MEASURED on three papers from a 300-PDF sweep
    of a real reference library, every character of the extracted text was
    furniture of exactly this shape:

      Scheff & Price 1998    918 chars = an OUP download stamp x 8 pages
      Small 2006             950 chars = "Reproduced with permission of the
                                          copyright owner" x 8 pages
      Scheving 1968           98 chars = "(c) 1968 Nature Publishing Group" x 2

    Not one word of any of the three papers came back, and all three were
    reported as readable. A test that only covers the zero-character case
    misses every one of them, which is why they survived: `len(text) > 0` is
    the wrong question, and the stamp is what makes it the wrong question.
    """
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page()
        page.insert_text(
            (40, 30),
            "Downloaded from https://academic.oup.com/article/57/12/1146 "
            "by guest on 12 March 2021",
            fontsize=6,
        )
        page.draw_rect(fitz.Rect(60, 60, 540, 780), color=(0, 0, 0), width=0.5)
    doc.save(str(path))
    doc.close()
    return path


def _extracted(pdf: Path) -> Path:
    """Stand in for a completed `metascience extract-tables` on `pdf`.

    WHY EVERY READABLE-DIRECTION TEST BELOW NEEDS THIS NOW. Since 2026-08-16
    `extract_text_with_tables` is cache-only: it reads the docling extraction
    cache and refuses when there is none, rather than opening the file. Fixtures
    built in a `tmp_path` have no cache, so without this the three-page fixture
    that stands for "an ordinary paper" is refused exactly like a corrupt
    download, and the false-positive half of every rule here -- the half that
    stops us refusing papers we could have read -- becomes untestable.

    The real extractor cannot be run from a test. One paper is minutes of layout
    model, and putting it in a read path is the regression measured three times
    in `docling_tables`: 260 s to 596 s, then 27 minutes, then 2h10m with a
    worker collapsing. So the schema-4 entry docling would have written is
    written here instead, keyed by the same content hash the reader uses, via
    the reader's own `_cache_path` -- so a change to how caches are named breaks
    this loudly instead of silently missing every time and re-refusing.

    THE PAGE TEXT IS READ OUT OF THE FIXTURE, not hand-written beside it. Each
    fixture above lays down a specific per-page shape -- a stamp on every page,
    a body line that varies, nothing at all -- and that shape is the entire
    input to the rule under test. Deriving it from the file keeps one source of
    truth, so editing a fixture cannot leave the cache describing a document
    that no longer exists.

    WHAT THIS DOES NOT COVER: docling's own fidelity. These tests never checked
    that -- under pdfplumber they were incidentally checking pdfplumber's -- and
    the extractor comparison is measured against publisher JATS XML in
    `docling_tables`' module docstring (recall 60.7% -> 95.9%), not here.
    """
    from forensic_metascience_ai_toolkit.extraction import docling_tables as dl

    doc = fitz.open(str(pdf))
    pages = [{"page_num": i + 1, "text": page.get_text() or ""}
             for i, page in enumerate(doc)]
    doc.close()

    text = "\n\n".join(p["text"] for p in pages)
    cache = dl._cache_path(pdf)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps({
            "text": text, "tables": [], "error": None, "n_tables": 0,
            "n_text_chars": len(text), "pages": pages, "num_pages": len(pages),
            "source_format": "pdf", "extractor": "docling", "cache_schema": 4,
        }),
        encoding="utf-8",
    )
    return pdf


# ---------------------------------------------------------------------------
# FIX 18 -- extract_figures
# ---------------------------------------------------------------------------

class TestFiguresRefuseUnreadable:
    def test_zero_page_document_is_refused(self, tmp_path):
        result = extract_figures(_zero_page_pdf(tmp_path / "empty.pdf"),
                                 out_dir=tmp_path / "figs")
        assert result["success"] is False
        assert result["unreadable"] is True

    def test_it_says_figures_are_unknown_not_absent(self, tmp_path):
        """`n_figures: 0` on an unopenable file is not a fact about the paper."""
        result = extract_figures(_zero_page_pdf(tmp_path / "empty.pdf"),
                                 out_dir=tmp_path / "figs")
        assert result["warnings"], "a silent empty result is the bug"
        assert "UNKNOWN" in result["error"]
        assert "not absent" in result["error"]

    def test_a_repaired_document_is_refused_too(self, tmp_path):
        """`is_repaired` means MuPDF rebuilt the file from what it could find.

        Everything downstream -- page count, text blocks, drawing commands --
        would then describe the reconstruction rather than the paper.
        """
        result = extract_figures(_truncated_pdf(tmp_path / "trunc.pdf", tmp_path),
                                 out_dir=tmp_path / "figs")
        assert result["success"] is False
        assert result["is_repaired"] is True

    def test_a_valid_pdf_still_succeeds(self, tmp_path):
        result = extract_figures(_real_pdf(tmp_path / "ok.pdf"),
                                 out_dir=tmp_path / "figs")
        assert result["success"] is True
        assert result.get("unreadable") is not True


# ---------------------------------------------------------------------------
# FIX 34 -- extract_text_with_tables
# ---------------------------------------------------------------------------

class TestPdfRecordSaysUnreadable:
    """The output CONTRACT on a document we did not read, whatever stopped us.

    Cache-only extraction collapsed two roads into one and the collapse is
    deliberate, so it is written down rather than left to be rediscovered: a
    file whose page tree is empty and a file nobody has extracted yet BOTH
    arrive as zero pages, and `extract_text_with_tables` cannot tell them apart
    because it never opens either. Greg's 2026-08-17 design is that `analyze`
    fills the cache up front so the second road is closed before a run reaches
    it (pinned in `tests/test_preextraction.py`).

    What these tests assert is what has to hold on both roads: `unreadable`
    True, `num_pages` 0, `truncated` False -- because "we stopped early to fit
    a budget" is the one thing it does not mean -- and an error saying the
    contents are UNKNOWN. The zero-page fixture is deliberately left without a
    cache, so it exercises the road a live run can actually hit.
    """

    def test_zero_page_document_is_flagged(self, tmp_path):
        out = extract_text_with_tables(_zero_page_pdf(tmp_path / "empty.pdf"))
        assert out["unreadable"] is True
        assert out["num_pages"] == 0

    def test_truncated_is_not_the_signal(self, tmp_path):
        """`truncated: False` was the only "is anything missing?" field, and it
        said no while the entire document was missing. The two facts are
        different and need different fields."""
        out = extract_text_with_tables(_zero_page_pdf(tmp_path / "empty.pdf"))
        assert out["truncated"] is False
        assert out["unreadable"] is True

    def test_it_says_the_contents_are_unknown(self, tmp_path):
        out = extract_text_with_tables(_zero_page_pdf(tmp_path / "empty.pdf"))
        assert "UNKNOWN" in out["error"]

    def test_a_valid_pdf_is_not_flagged(self, tmp_path):
        """The false-positive direction, and the one the cache-only change put
        at risk: this fixture is a perfectly ordinary three-page paper, and
        without an extraction cache it now comes back `unreadable: True,
        num_pages: 0` -- OUR missing step recorded as a fact about the file.
        `_extracted` supplies the step; the assertions are unchanged."""
        out = extract_text_with_tables(_extracted(_real_pdf(tmp_path / "ok.pdf")))
        assert out["unreadable"] is False
        assert out["num_pages"] == 3
        assert "error" not in out

    def test_the_field_is_always_present(self, tmp_path):
        """A consumer must be able to rely on the key, not on its absence.

        One loop over two makers used to say this. The two roads are genuinely
        different now -- one document is read from its cache, the other refused
        for want of one -- so they are spelled out rather than hidden behind a
        tuple that no longer describes what happens to each.
        """
        read = extract_text_with_tables(_extracted(_real_pdf(tmp_path / "ok.pdf")))
        refused = extract_text_with_tables(_zero_page_pdf(tmp_path / "empty.pdf"))
        assert "unreadable" in read
        assert "unreadable" in refused


# ---------------------------------------------------------------------------
# A SCAN OPENS FINE. That is the whole problem.
# ---------------------------------------------------------------------------

class TestOurFailureIsNotAttributedToThePaper:
    """`_page_ink` swallowed a decoder error and called it "no artwork".

    MuPDF raises out of `get_image_rects` on a damaged embedded raster -- the
    "cmsOpenProfileFromMem failed" class, which appeared in a 300-document
    sweep. The handler was `except Exception: continue`, so the rectangle was
    dropped and the crop then reported `NO CROP: no artwork found on the page`.

    That sentence is a claim about the PAPER. The true statement is a claim
    about THIS TOOL. Reported in the paper's words, it invites a reader to
    conclude a figure is absent when what actually happened is that we could
    not read it. Injection below rather than a fixture PDF, because a raster
    that breaks MuPDF's colour management is not something to check into a
    repository.
    """

    def _inject(self, monkeypatch):
        def boom(self, *a, **k):
            raise RuntimeError("MuPDF: cmsOpenProfileFromMem failed")
        monkeypatch.setattr(fitz.Page, "get_image_rects", boom)

    def test_a_decode_failure_does_not_claim_the_page_is_empty(
            self, tmp_path, monkeypatch):
        from metascience_observatory_image_analysis.extraction.figures import extract_figures
        pdf = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--hbm.26595/"
                   "10.1002--hbm.26595.pdf")
        if not pdf.exists():
            pytest.skip("corpus not present")
        self._inject(monkeypatch)
        r = extract_figures(pdf, out_dir=tmp_path / "f", render_pages=False)
        warnings = r.get("warnings") or []
        assert warnings, "the drop has to be reported at all"
        assert not [w for w in warnings if "no artwork found on the page" in w]
        assert [w for w in warnings if "NOT BE DECODED" in w]

    def test_it_names_whose_failure_it_was(self, tmp_path, monkeypatch):
        from metascience_observatory_image_analysis.extraction.figures import extract_figures
        pdf = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--hbm.26595/"
                   "10.1002--hbm.26595.pdf")
        if not pdf.exists():
            pytest.skip("corpus not present")
        self._inject(monkeypatch)
        r = extract_figures(pdf, out_dir=tmp_path / "f", render_pages=False)
        said = " ".join(r.get("warnings") or [])
        assert "this tool, not a fact about the paper" in said

    def test_a_healthy_document_gains_no_such_warning(self, tmp_path):
        from metascience_observatory_image_analysis.extraction.figures import extract_figures
        pdf = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--hbm.26595/"
                   "10.1002--hbm.26595.pdf")
        if not pdf.exists():
            pytest.skip("corpus not present")
        r = extract_figures(pdf, out_dir=tmp_path / "f", render_pages=False)
        assert r["n_cropped"] == r["n_figures"], "all five crop normally"
        assert not [w for w in (r.get("warnings") or []) if "DECODED" in w]


class TestScannedDocumentIsUnreadable:
    """`unreadable` fired only at `total_pages == 0`, which a scan never meets.

    A scanned paper opens cleanly, reports its true page count, and returns ""
    for every page. It failed every test above by passing them.

    MEASURED over 300 PDFs sampled from a 7,046-item reference library: 9 came
    back at 16-120 characters per page against a corpus median of 1,827, and
    all 9 were reported as successful extractions. Every one of them is
    pre-2000 or of unknown year; the 2010s and 2020s strata are completely
    clean, which is why a corpus of modern publisher PDFs never surfaced this.

    What makes it the worst case rather than merely a missing feature: on a
    paper with no readable text there is nothing for any check to fire on, so
    the sweep completes with no findings, and stage 2's three conditions for a
    `trustworthy` verdict -- no surviving finding, headline severity none,
    nothing lost to correction -- are all satisfied VACUOUSLY. A verdict of
    `trustworthy` is a positive claim that can be quoted as an exoneration, so
    the failure is not a missed accusation but a manufactured clearance.
    """

    def test_a_scan_with_no_text_layer_is_flagged(self, tmp_path):
        """Extraction SUCCEEDED here and still read nothing -- that is the case.

        The assert message used to read "it opens fine", which described
        pdfplumber opening the file. Nothing opens it now; the document is read
        from its extraction cache, which reports all six pages and empty text
        for each. The point survives the rewording and is the same one: a scan
        is not a short document and not a missing document, so page count can
        never detect one.
        """
        out = extract_text_with_tables(_extracted(_scanned_pdf(tmp_path / "scan.pdf")))
        assert out["num_pages"] == 6, "all six pages came back -- that is the point"
        assert out["unreadable"] is True

    def test_a_stamp_on_every_page_is_not_a_readable_paper(self, tmp_path):
        """The measured case. Text is present, and none of it is the paper."""
        out = extract_text_with_tables(
            _extracted(_stamped_scan_pdf(tmp_path / "stamp.pdf")))
        assert out["text"].strip(), "the stamp really is extractable text"
        assert out["unreadable"] is True

    def test_it_says_the_contents_are_unknown(self, tmp_path):
        """Same contract as the zero-page case: a caller must be told that
        nothing came back, in the same field, with the same words."""
        out = extract_text_with_tables(_extracted(_scanned_pdf(tmp_path / "scan.pdf")))
        assert "UNKNOWN" in out["error"]

    def test_page_separators_do_not_count_as_content(self, tmp_path):
        """`text` was 100 chars on a 6-page scan and every character was the
        extractor's own `--- Page N ---` scaffolding: 8 x 15 + 7 x 2 = 134 on
        the 8-page case. Any downstream non-empty test was satisfied by our
        furniture, so the emptiness check could never fire.

        Still reachable under docling: the cached body text of a scan is empty,
        so `text` is assembled from the per-page slice, and the separators are
        again the only characters in it."""
        out = extract_text_with_tables(_extracted(_scanned_pdf(tmp_path / "scan.pdf")))
        residue = out["text"].replace("-", "").replace("Page", "")
        assert not "".join(residue.split()).strip("0123456789"), (
            "nothing but separators came back")
        assert out["unreadable"] is True

    def test_a_real_paper_is_still_readable(self, tmp_path):
        """The false-positive direction, which matters as much: refusing a
        paper we could have read is a real cost, so the rule must not fire on
        an ordinary document."""
        out = extract_text_with_tables(_extracted(_real_pdf(tmp_path / "ok.pdf")))
        assert out["unreadable"] is False
        assert "error" not in out

    def test_a_short_paper_is_not_mistaken_for_a_scan(self, tmp_path):
        """A two-page letter or comment is a legitimate document type, and a
        density rule applied naively rejects one. Length is not the signal."""
        doc = fitz.open()
        for i in range(2):
            page = doc.new_page()
            page.insert_text((72, 100), f"Page {i + 1} of 2.")
            page.insert_text((72, 130), _BODY_LINES[i])
        doc.save(str(tmp_path / "letter.pdf"))
        doc.close()
        out = extract_text_with_tables(_extracted(tmp_path / "letter.pdf"))
        assert out["unreadable"] is False, (
            "two pages of real prose, under a running head that repeats -- the "
            "head is furniture and the prose is not")

    def test_the_measure_is_content_that_varies_not_length(self, tmp_path):
        """The rule that was NOT chosen, and why.

        A chars-per-page threshold would have to sit above 120 to catch the
        measured scans, and a genuine two-page Nature report from 1968 sits at
        49. Any cutpoint that separates them on length alone also rejects
        short letters, comments and errata -- and rejects papers in languages
        whose typography packs fewer characters per page, which is a fairness
        problem on top of an accuracy one. Requiring only that SOMETHING vary
        across the pages needs no cutpoint at all.
        """
        doc = fitz.open()
        for i in range(9):
            page = doc.new_page()
            page.insert_text((40, 30), "Downloaded from example.org by guest",
                             fontsize=6)
            if i == 4:
                page.insert_text((72, 130), "n = 40 participants were enrolled.")
        doc.save(str(tmp_path / "one_real_page.pdf"))
        doc.close()
        out = extract_text_with_tables(_extracted(tmp_path / "one_real_page.pdf"))
        assert out["unreadable"] is False, (
            "one page of real content in nine is still a paper we read")


class TestOnePageDocuments:
    """A single page cannot have its furniture identified.

    Everywhere else the measure is "what text does NOT repeat across pages",
    which needs no threshold: measured over 291 PDFs, every known scan comes
    back at exactly 0.0 body-chars per page and the sparsest readable document
    at 163.7, so any cutpoint between them behaves the same and zero is chosen
    for having none.

    One page breaks that, because a stamp is only recognisable by repeating.
    So this case alone falls back to raw length, and alone needs a number. It
    is the weakest-supported part of the rule and is flagged as such in the
    source: no corpus available holds a genuine one-page scan, so the positive
    example is constructed. The two ends that ARE measured are a one-page scan
    carrying only a 124-character JSTOR stamp and the sparsest genuinely
    readable single-page document at 571 characters.
    """

    def _one_page(self, path, text):
        """One page, SET IN LINES rather than one string running off the paper.

        This used to be a single `insert_text` of the whole abstract. pdfplumber
        handed back every character regardless of where the glyphs landed, so
        nobody noticed that the line was 947 points wide on a 595-point page.
        The cache is now built from what is actually ON the page, and MEASURED
        the abstract below came back CLIPPED at the right edge: 180 characters
        of 303, leaving only 1.2x headroom over the 150-character cutpoint this
        whole class exists to calibrate -- close enough that rewording one
        sentence could flip the result and look like a rule change.

        Wrapping at 90 columns restores the full 303 characters (2.0x the
        cutpoint) and makes the fixture look like the thing it stands for, since
        a real one-page abstract is set in lines. The stamp case is unaffected
        either way: 86 characters fit on one line and sit below the cutpoint
        before and after.
        """
        doc = fitz.open()
        page = doc.new_page()
        for i, line in enumerate(textwrap.wrap(text, 90)):
            page.insert_text((40, 40 + 10 * i), line, fontsize=7)
        doc.save(str(path))
        doc.close()
        return path

    def test_a_one_page_scan_carrying_only_a_stamp_is_refused(self, tmp_path):
        pdf = self._one_page(tmp_path / "stamp.pdf",
                             "Downloaded from JSTOR by an anonymous user on "
                             "12 March 2021. All use subject to terms.")
        assert extract_text_with_tables(_extracted(pdf))["unreadable"] is True

    def test_a_one_page_paper_is_not_refused(self, tmp_path):
        pdf = self._one_page(
            tmp_path / "abstract.pdf",
            "We report a direct replication of Smith (2019) in a new sample "
            "of n = 212 undergraduates. The original effect was d = 0.62; we "
            "observed d = 0.11, 95% CI [-0.06, 0.28]. The difference between "
            "estimates was reliable, p = .004. Materials, data and analysis "
            "code are available on the Open Science Framework.")
        assert extract_text_with_tables(_extracted(pdf))["unreadable"] is False


class TestOneBadPageDoesNotCostTheDocument:
    """`render_pdf_pages` wrapped its whole loop in `except Exception: return []`.

    `get_pixmap` raises on a damaged image stream or a broken colour profile,
    so a single unrenderable page discarded every page already written. The
    caller then computed the total from a second open and produced
    `pages: 0, total_pages: 40, truncated: True` -- which reads as "we stopped
    early to fit a budget", the one thing it does not mean. The comment
    directly beneath that line insists a reader "who sees 12 of 40 pages must
    know the other 28 exist", which is exactly the distinction being lost.

    No new plumbing was needed to tell the two apart: the caller already knows
    how many pages it ASKED for, so anything short of that failed rather than
    being trimmed.
    """

    PDF = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--hbm.26595/"
               "10.1002--hbm.26595.pdf")

    def _flaky(self, monkeypatch, bad_page=3):
        orig = fitz.Page.get_pixmap
        seen = {"n": 0}

        def flaky(self, *a, **k):
            seen["n"] += 1
            if seen["n"] == bad_page:
                raise RuntimeError("MuPDF: cannot render page")
            return orig(self, *a, **k)

        monkeypatch.setattr(fitz.Page, "get_pixmap", flaky)

    def _render(self, tmp_path):
        from forensic_metascience_ai_toolkit.bundle import render_all_pdfs
        return render_all_pdfs([self.PDF], tmp_path)

    def test_the_other_pages_survive(self, tmp_path, monkeypatch):
        if not self.PDF.exists():
            pytest.skip("corpus not present")
        self._flaky(monkeypatch)
        _, docs = self._render(tmp_path)
        assert docs[0]["pages"] == docs[0]["total_pages"] - 1

    def test_a_failed_render_is_not_reported_as_truncation(self, tmp_path, monkeypatch):
        if not self.PDF.exists():
            pytest.skip("corpus not present")
        self._flaky(monkeypatch)
        _, docs = self._render(tmp_path)
        assert docs[0]["pages_failed_to_render"] == 1
        assert "OUR renderer failed" in docs[0]["render_note"]

    def test_a_healthy_document_carries_no_such_note(self, tmp_path):
        if not self.PDF.exists():
            pytest.skip("corpus not present")
        _, docs = self._render(tmp_path)
        assert docs[0]["pages"] == docs[0]["total_pages"]
        assert docs[0]["truncated"] is False
        assert "pages_failed_to_render" not in docs[0]


class TestTableExtractionFailureIsReported:
    """"No tables in this paper" and "our table reader never ran" are different.

    WHAT THIS USED TO TEST, and why it is retargeted rather than deleted.
    `_tables_with_fallback` ran pdfplumber's ruled pass UNPROTECTED, so one page
    it could not rule took the whole document down; and the text-alignment
    fallback returned `[], []`, which a caller cannot distinguish from a page
    that genuinely has no table. Two of the three tests below monkeypatched
    `pdfplumber.page.Page.extract_tables` to force that raise.

    THE MECHANISM IS GONE -- the fallback, the per-page `tables_error_pages`
    counter, and pdfplumber itself (Greg, 2026-08-16: it "should never run
    *anywhere*"). Extraction is now a separate cached step, so there is no
    per-page table reader inside this call to break, and the monkeypatch would
    be inert: the assertions named fields that are no longer emitted, and the
    only reason the file was green was that the corpus PDF happens to be absent
    from this checkout. A test that can only pass by being skipped is a test
    waiting to fire on whoever restores the corpus.

    THE PROPERTY SURVIVES THE MECHANISM, and it is the one that matters for a
    tool whose output is an accusation: an empty `tables` list must never arrive
    in the same shape as an answer. It now takes exactly one form -- cache-only
    extraction means the failure is "nobody ran the reader", and it is reported
    at the TOP level, because a model that reads `tables: []` and moves on never
    looks any deeper.

    The corpus gate goes with the monkeypatch: the fixtures state the property
    directly and run everywhere, which is worth more than fidelity to a document
    this checkout does not have.
    """

    def test_an_unread_document_does_not_return_a_bare_empty_list(self, tmp_path):
        """The whole point, in one place: `tables: []` never travels alone."""
        out = extract_text_with_tables(_real_pdf(tmp_path / "unread.pdf"))
        assert out["tables"] == []
        assert out["unreadable"] is True
        assert "empty `tables` list" in out["error"]
        assert "NOT about the paper" in out["error"]

    def test_the_reason_names_the_step_that_would_fix_it(self, tmp_path):
        """A refusal a reader cannot act on is only marginally better than a
        wrong answer. The one thing standing between this document and a real
        table list is a command, so the record says which."""
        out = extract_text_with_tables(_real_pdf(tmp_path / "unread.pdf"))
        assert "metascience extract-tables" in out["error"]
        assert "metascience extract-tables" in (out["text_extractor_note"] or "")

    def test_a_read_document_answers_about_the_paper(self, tmp_path):
        """The other half, and the reason the first is not merely a tautology:
        this fixture has no tables either, so both calls return `tables: []`.
        What separates them is `unreadable` and the presence of an error, which
        is exactly the distinction the old fallback could not express."""
        out = extract_text_with_tables(_extracted(_real_pdf(tmp_path / "read.pdf")))
        assert out["tables"] == []
        assert out["unreadable"] is False
        assert "error" not in out
