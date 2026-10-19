"""Say so when a table is a picture, instead of silently reading no table.

WHAT WAS MEASURED, AND WHY THERE IS NO OCR PASS HERE. Task #143 assumed
main-paper tables stored as images were a live gap. Measured 2026-08-11 over
376 PDFs (68 eval/ground_truth + 308 cerebrolysin) and 452 table-caption bands:
ZERO are image-only. Building an OCR pipeline for the main paper would be
building for a case that does not occur in either corpus, so this module
detects and reports, and nothing more. `extraction/ocr.py` already handles the
case that DOES occur -- 142 image supplements -- and its provenance reasoning
(an OCR'd numeral is neither `printed_table` nor `measured_raster`) is why
routing main-paper tables through it silently would be worse than refusing.

THE FIRST VERSION OF THIS MEASUREMENT WAS WRONG, in the dangerous direction,
and the correction is the whole design. It scored raster coverage of the PAGE
and returned 38 "hits" -- every one a full-page scan background with thousands
of characters of real text printed on top. Coverage of the page answers nothing.
The question is whether the BAND UNDER THE CAPTION holds any text: a table set
as text puts hundreds of characters there, a table set as a picture puts none.

POSITIVE CONTROL, because a detector that can never fire reports zero exactly as
convincingly as a corpus that has none. `tests/test_image_tables.py` builds the
case this is meant to catch -- a rasterised table pasted under a caption -- and
asserts it fires. Do not delete that test to make this file smaller.

WHAT A DETECTION IS FOR. It is a REFUSAL, in the house sense: this analysis did
not read Table 3, and the reader is told which one and why. It is never a
finding about the paper. Publishing a table as an image is a typesetting
decision, not an anomaly, and nothing here may be routed into `findings`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

#: Caption at the start of a line. Anchored deliberately: an unanchored pattern
#: matches "as shown in Table 3" mid-sentence and bands the body prose that
#: follows it, which is the difference between a caption and a cross-reference.
_CAPTION = re.compile(r"^\s*(?:TABLE|Table)\s+(\d+)[.:\s]", re.M)

#: How far below a caption the table may extend before we stop looking. Bands
#: are also cut at the next caption, so this only bounds the last one on a page.
_BAND_POINTS = 420.0

#: A band shorter than this is a caption pinned to the page foot with its table
#: overleaf -- 5 of 452 in the corpus. Real, and a DIFFERENT problem (no
#: multi-page stitching exists); reporting it as an image-only table would be a
#: false statement about what we saw.
_MIN_BAND_POINTS = 40.0

#: Characters in the band below which we call it empty. Not zero: a stray
#: footnote marker or a units row bleeding in from the caption is common.
_EMPTY_CHARS = 40

#: Share of the band a raster must cover to be the reason the band is empty.
_MIN_RASTER_SHARE = 0.20


def _bands(page) -> list[tuple[str, Any]]:
    """(caption label, rect) for every table caption on a PyMuPDF page."""
    import fitz

    caps: list[tuple[str, Any]] = []
    for m in _CAPTION.finditer(page.get_text()):
        label = m.group(0).strip()
        hits = page.search_for(label, quads=False) or []
        if hits:
            caps.append((label, hits[0]))
    caps.sort(key=lambda t: t[1].y0)

    out: list[tuple[str, Any]] = []
    for i, (label, r) in enumerate(caps):
        top = r.y1
        bot = caps[i + 1][1].y0 if i + 1 < len(caps) else page.rect.y1
        bot = min(bot, top + _BAND_POINTS)
        if bot - top > _MIN_BAND_POINTS:
            out.append((label, fitz.Rect(page.rect.x0, top, page.rect.x1, bot)))
    return out


def find_image_only_tables(pdf_path: str | Path) -> dict[str, Any]:
    """Bands that carry a table caption, no text, and a raster where the table
    should be.

    Returns `{"available": bool, "reason": str, "bands_examined": int,
    "detections": [...]}`. `available` False means we could not look -- an
    unreadable PDF or a missing PyMuPDF -- and that is reported as OUR limit,
    never as a clean result. The distinction matters: "we looked and every table
    is text" and "we could not look" are different sentences and only one of
    them licenses reading the tables we did get as the whole set.
    """
    out: dict[str, Any] = {"available": False, "reason": "", "pdf": str(pdf_path),
                           "bands_examined": 0, "detections": [],
                           "captions_with_table_overleaf": []}
    try:
        import fitz
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"PyMuPDF unavailable: {exc}"
        return out

    p = Path(pdf_path)
    if not p.exists():
        out["reason"] = f"PDF not found: {p}"
        return out
    try:
        doc = fitz.open(p)
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"PDF could not be opened: {str(exc)[:120]}"
        return out

    out["available"] = True
    try:
        for pno, page in enumerate(doc, 1):
            try:
                bands = _bands(page)
            except Exception:  # noqa: BLE001, PERF203 -- one bad page is not a bad PDF
                continue
            for label, band in bands:
                out["bands_examined"] += 1
                try:
                    n_chars = len(page.get_textbox(band).strip())
                except Exception:  # noqa: BLE001
                    continue
                if n_chars >= _EMPTY_CHARS:
                    continue
                area = band.get_area() or 1.0
                share = 0.0
                try:
                    infos = page.get_image_info()
                except Exception:  # noqa: BLE001
                    infos = []
                for d in infos:
                    hit = fitz.Rect(d["bbox"]) & band
                    if not hit.is_empty:
                        share = max(share, hit.get_area() / area)
                row = {"page": pno, "caption": label,
                       "bbox": [round(v, 1) for v in band],
                       "chars_in_band": n_chars,
                       "raster_share": round(share, 3)}
                if share >= _MIN_RASTER_SHARE:
                    out["detections"].append(row)
                else:
                    # Empty band, no picture: the caption sits at the foot of the
                    # page and the table itself is overleaf. NOT an image table.
                    out["captions_with_table_overleaf"].append(row)
    finally:
        doc.close()
    return out


def refusal_lines(scan: dict[str, Any]) -> list[dict[str, str]]:
    """`{location, reason}` rows for the report's `not_checked` list.

    Phrased as OUR limit throughout. A table set as a picture is a typesetting
    choice; the only fact here is that this analysis did not read it.
    """
    if not scan.get("available"):
        return [{"location": "tables (image check)",
                 "reason": ("We could not check whether any table is stored as a "
                            f"picture: {scan.get('reason') or 'unknown'}. The "
                            "tables reported below may not be all of them.")}]
    rows = []
    for d in scan.get("detections") or []:
        rows.append({
            "location": f"{d['caption']} (page {d['page']})",
            "reason": ("This table is stored in the PDF as a picture rather than "
                       "as text, so no numbers were read from it and no check "
                       "ran against it. That is a typesetting choice by the "
                       "publisher and says nothing about the paper -- but it "
                       "means this table is outside everything reported here."),
        })
    for d in scan.get("captions_with_table_overleaf") or []:
        rows.append({
            "location": f"{d['caption']} (page {d['page']})",
            "reason": ("The caption sits at the foot of the page and the table "
                       "body continues on the next one. This pipeline reads "
                       "tables one page at a time and does not join a table "
                       "across a page break, so it may have been read in "
                       "fragments or missed."),
        })
    return rows
