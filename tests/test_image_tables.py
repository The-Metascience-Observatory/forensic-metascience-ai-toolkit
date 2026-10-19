"""The image-only-table detector, and the positive control that makes its zero
mean something.

MEASURED 2026-08-11 over 376 corpus PDFs and 452 caption bands: zero image-only
tables. A detector that cannot fire produces that same zero, so the control
below is load-bearing -- it builds the case the module exists to catch and
asserts it is caught.
"""
import re
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")

from metascience_agent.extraction import image_tables as IT  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _pdf_with(tmp_path, caption, *, as_image, extra_text=""):
    """One page: a caption, then either a raster or real text beneath it."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 90), caption, fontsize=10)
    if as_image:
        src = fitz.open()
        sp = src.new_page(width=468, height=330)
        sp.insert_text((20, 40), "Group A 12 (34.0) 5.6 (1.2)", fontsize=11)
        sp.insert_text((20, 70), "Group B 14 (38.9) 5.9 (1.4)", fontsize=11)
        png = sp.get_pixmap(dpi=150).tobytes("png")
        src.close()
        page.insert_image(fitz.Rect(72, 100, 540, 430), stream=png)
    else:
        y = 120
        for row in ("Group A 12 (34.0) 5.6 (1.2)", "Group B 14 (38.9) 5.9 (1.4)",
                    "Total 26 (72.9) 5.7 (1.3)"):
            page.insert_text((72, y), row, fontsize=10)
            y += 18
    if extra_text:
        page.insert_text((72, 700), extra_text, fontsize=9)
    out = tmp_path / f"{'img' if as_image else 'txt'}.pdf"
    doc.save(out)
    doc.close()
    return out


class TestThePositiveControl:
    """Without this, the corpus zero is indistinguishable from a dead check."""

    def test_a_table_pasted_in_as_a_picture_is_detected(self, tmp_path):
        scan = IT.find_image_only_tables(
            _pdf_with(tmp_path, "Table 1. Baseline characteristics", as_image=True))
        assert scan["available"]
        assert len(scan["detections"]) == 1, scan
        d = scan["detections"][0]
        assert d["chars_in_band"] < IT._EMPTY_CHARS
        assert d["raster_share"] >= IT._MIN_RASTER_SHARE
        assert d["caption"].startswith("Table 1")

    def test_the_same_table_set_as_text_is_not_detected(self, tmp_path):
        """The control's control. A detector that fires on ordinary tables would
        put a refusal on every paper in the corpus."""
        scan = IT.find_image_only_tables(
            _pdf_with(tmp_path, "Table 1. Baseline characteristics", as_image=False))
        assert scan["available"]
        assert scan["detections"] == []
        assert scan["bands_examined"] == 1


class TestItDoesNotConfuseABackgroundScanWithATable:
    def test_a_full_page_raster_under_real_text_is_not_a_detection(self, tmp_path):
        """THE BUG THE FIRST MEASUREMENT SHIPPED. Scoring raster coverage of the
        PAGE returned 38 hits over the corpus, every one a scanned page with
        thousands of characters of real text printed on top of the scan."""
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        bg = fitz.open()
        bp = bg.new_page(width=612, height=792)
        png = bp.get_pixmap(dpi=72).tobytes("png")
        bg.close()
        page.insert_image(page.rect, stream=png)          # full-page background
        page.insert_text((72, 90), "Table 1. Characteristics", fontsize=10)
        y = 120
        for i in range(12):
            page.insert_text((72, y), f"Row {i} 12 (34.0) 5.6 (1.2) 0.041", fontsize=10)
            y += 16
        p = tmp_path / "scan.pdf"
        doc.save(p)
        doc.close()
        scan = IT.find_image_only_tables(p)
        assert scan["detections"] == [], "page-level raster coverage is the wrong test"


class TestTheOverleafCaseIsReportedSeparately:
    def test_a_caption_at_the_page_foot_is_not_called_an_image_table(self, tmp_path):
        """5 of 452 corpus bands. The table is overleaf and this pipeline does
        not stitch across pages -- a real limit, and a different one."""
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 300), "Table 1. Characteristics of the cohort", fontsize=10)
        p = tmp_path / "foot.pdf"
        doc.save(p)
        doc.close()
        scan = IT.find_image_only_tables(p)
        assert scan["detections"] == []
        assert len(scan["captions_with_table_overleaf"]) == 1
        reasons = " ".join(r["reason"] for r in IT.refusal_lines(scan))
        assert "page break" in reasons


class TestCaptionsVersusCrossReferences:
    def test_a_mid_sentence_mention_does_not_open_a_band(self, tmp_path):
        """"as shown in Table 3" is a cross-reference. Banding the prose after
        it and finding no text there would manufacture a refusal on a paper
        whose tables we read perfectly well."""
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 300), "The effect was larger, as shown in Table 3.", fontsize=10)
        p = tmp_path / "xref.pdf"
        doc.save(p)
        doc.close()
        scan = IT.find_image_only_tables(p)
        assert scan["bands_examined"] == 0
        assert scan["detections"] == []


class TestFailureIsReportedAsOurs:
    def test_a_missing_pdf_is_unavailable_not_clean(self, tmp_path):
        """"We looked and found none" and "we could not look" are different
        sentences; only the first licenses reading the tables we got as all of
        them."""
        scan = IT.find_image_only_tables(tmp_path / "nope.pdf")
        assert scan["available"] is False
        assert "not found" in scan["reason"]
        rows = IT.refusal_lines(scan)
        assert len(rows) == 1
        assert "could not check" in rows[0]["reason"]

    def test_an_unopenable_file_does_not_raise(self, tmp_path):
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a pdf at all")
        scan = IT.find_image_only_tables(bad)
        assert scan["available"] is False and scan["reason"]


class TestTheRefusalWordingBlamesNobody:
    def test_it_says_the_typesetting_is_not_the_paper_s_fault(self, tmp_path):
        """A table published as a picture is a publisher's decision. Wording it
        as anything else manufactures a criticism out of our own limit -- the
        same error `not_checked` phrasing was corrected for elsewhere."""
        scan = IT.find_image_only_tables(
            _pdf_with(tmp_path, "Table 2. Outcomes", as_image=True))
        row = IT.refusal_lines(scan)[0]
        assert "says nothing about the paper" in row["reason"]
        assert "Table 2" in row["location"]


class TestTheCorpusMeasurementStillHolds:
    """A ratchet, not a gate: if a future corpus DOES contain image tables this
    should surface it rather than fail the build."""

    def test_the_ground_truth_corpus_has_no_image_only_tables(self):
        root = REPO / "eval/ground_truth/papers"
        if not root.exists():
            pytest.skip("ground-truth corpus not present")
        pdfs = [next(iter(d.glob("*.pdf")), None) for d in sorted(root.iterdir())
                if d.is_dir()]
        pdfs = [p for p in pdfs if p][:25]
        if not pdfs:
            pytest.skip("no PDFs in the ground-truth corpus")
        hits, bands = [], 0
        for p in pdfs:
            s = IT.find_image_only_tables(p)
            bands += s["bands_examined"]
            hits.extend((p.name, d["caption"]) for d in s["detections"])
        assert bands > 0, "the scan examined no caption bands at all -- detector is dead"
        assert not hits, (
            f"{len(hits)} image-only table(s) now detected where the 2026-08-11 "
            f"measurement found none over 452 bands: {hits[:3]}. That is new, and "
            "worth an OCR pass if it is not a detector regression.")


