"""
OCR for table images -- the engine seam, the layout reconstruction, and the
provenance decision that keeps a misread digit from becoming an accusation.

WHY THIS EXISTS. 142 of the supplementary files in the working corpus are
`.jpg`/`.png`, and `supplements_read.UNREADABLE` refused every one of them with
"image supplement; there is no OCR in this pipeline". A scanned supplementary
table is not an unusual artefact -- it is how a large share of pre-2010 material
and almost all author-supplied appendices arrive. Refusing them means the
numbers most likely to be unchecked anywhere else are the ones we never look at.

-----------------------------------------------------------------------------
THE PROVENANCE DECISION (the important part of this file)
-----------------------------------------------------------------------------

`figures.py` splits provenance AS-PRINTED vs MEASURED, and the split is not
text-vs-image: a numeral printed inside a figure is `printed_figure` and
licenses the full severity ladder, because the authors ASSERTED it. Only a value
we read off the marks with a ruler is different in kind.

An OCR'd table cell sits in neither box, and putting it in either is a mistake:

  * It is NOT `printed_table`. `printed_table` asserts two things -- that the
    authors printed this number, and that we know WHICH number they printed.
    OCR delivers the first and not the second. Every exact-arithmetic check in
    this repo (GRIM, GRIMMER, SPRITE, DEBIT, GRIM-U) tests whether a value is
    possible to its LAST PRINTED DIGIT. A `3` transcribed from an `8` changes
    that digit, and the check then returns `impossible` against a paper whose
    arithmetic was fine. That is the worst output this toolkit can produce, and
    it is produced by OUR reader rather than by the authors.

  * It is NOT `measured_raster` either, and calling it that would be a false
    statement in the report. Nothing was measured. The stated reason measured
    values are refused -- "a value read off a figure has no last printed digit"
    -- is simply untrue of an OCR'd numeral, which has exactly one. A reader
    who is told the wrong reason cannot audit the refusal, and an operator who
    wants to lift it does the wrong thing (re-measure, rather than re-read).

The two failure shapes are also different in a way that matters for what can be
done about them. A measured value carries a CONTINUOUS error: sigma in data
units, computable from the pixel geometry (`sigma_from_geometry`), and a
tolerance-aware check can still use it. An OCR'd value carries a DISCRETE error:
the mean is 48.90 or it is 43.90, with nothing in between, and no sigma
describes that. So the `uncertainty` machinery -- which stamps a sigma and lets
tolerance-aware checks proceed -- is the wrong instrument for OCR. What OCR
needs is a plain refusal of the exact family plus a promotion path.

Hence a THIRD channel, `ocr_table` / `ocr_text`:

  * reliability tier 2, so every gate that already refuses tier-2 values refuses
    these, with no new gate to remember to add;
  * its own refusal wording, naming transcription rather than measurement;
  * a promotion path: a human (or a second engine) who confirms the cell against
    the image re-stamps it `printed_table`, and the full ladder returns. That is
    the ONLY route from an image to an `impossible` verdict, and it is
    deliberately manual.

What survives OCR without verification is everything that does not turn on the
last digit: reading the table at all, seeing what was reported, duplication
patterns at low severity, order-of-magnitude checks, and telling a human where
to look. That is a large gain over refusing the file.

-----------------------------------------------------------------------------
THE ENGINE SEAM
-----------------------------------------------------------------------------

No OCR engine is installed in this venv (checked: no `pytesseract`, no
`tesseract` binary, no PaddleOCR, no EasyOCR, no `rapidocr-onnxruntime`), and
`fitz.get_tessdata()` raises "No tessdata specified and Tesseract is not
installed". So `engine_status()` reports UNAVAILABLE here and every entry point
refuses with `ocr_unavailable: True`.

That flag exists because of the failure mode this repo keeps finding: a degraded
result reported as success. "We have no OCR engine" and "this image contains no
table" are opposite facts and must never arrive in the same shape -- the first
is a property of this machine, the second a property of the document. A caller
that cannot tell them apart will write "the supplement contains no tables" into
a review, which is a claim about the authors made out of a missing package.

Everything ABOVE the engine is implemented and tested here, because that is
where the interesting errors live: turning word boxes into a grid is what
decides whether a `mean (SD)` pair stays in one cell or is split across two
columns, and a column shift hands GRIM a triple the paper never reported. The
adapters below convert an engine's native output into `OcrWord`s; the layout
code is engine-independent and is exercised by the tests on synthetic boxes.
"""

from __future__ import annotations

import os
import shutil
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .figures import OCR_TABLE, OCR_TEXT  # noqa: F401  (re-exported for callers)

# ---------------------------------------------------------------------------
# The word record every engine adapter must produce
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OcrWord:
    """One recognised token and where it sat on the page.

    Coordinates are pixels with a TOP-LEFT origin, which is what every engine
    considered here reports and what PyMuPDF renders to. `conf` is 0-100; an
    engine that reports no confidence passes `None` rather than 100, because a
    fabricated confidence is worse than an absent one -- the whole point of the
    confidence gate is that it fires on values we are unsure of.
    """

    text: str
    x: float
    y: float
    w: float
    h: float
    conf: float | None = None

    @property
    def x1(self) -> float:
        return self.x + self.w

    @property
    def y1(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


# ---------------------------------------------------------------------------
# Engine availability
# ---------------------------------------------------------------------------

#: Engines this module knows how to drive, best first. Each entry is
#: (key, human name, probe, install hint). The probe returns "" when the engine
#: is usable and a REASON when it is not; the reason is what gets reported, so
#: an operator learns which half is missing (the Python package or the binary).
def _probe_pytesseract() -> str:
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return "the `pytesseract` Python package is not installed"
    if not shutil.which("tesseract") and not os.environ.get("TESSERACT_CMD"):
        return ("`pytesseract` is installed but the `tesseract` BINARY is not on "
                "PATH; pytesseract is only a wrapper and cannot read anything "
                "without it")
    return ""


def _probe_rapidocr() -> str:
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except ImportError:
        return "the `rapidocr-onnxruntime` Python package is not installed"
    return ""


def _probe_pymupdf_ocr() -> str:
    try:
        import fitz
    except ImportError:
        return "PyMuPDF is not installed"
    try:
        fitz.get_tessdata()
    except Exception as exc:
        # PyMuPDF's OCR is a Tesseract front-end. Say so: an operator who reads
        # "PyMuPDF is installed" and stops there will not find the real gap.
        return (f"PyMuPDF is present but its OCR is a Tesseract front-end and "
                f"Tesseract is not usable here ({exc})")
    return ""


ENGINES: tuple[tuple[str, str, Any, str], ...] = (
    ("pytesseract", "Tesseract via pytesseract", _probe_pytesseract,
     "apt-get install tesseract-ocr && pip install pytesseract"),
    ("rapidocr", "RapidOCR (ONNX runtime)", _probe_rapidocr,
     "pip install rapidocr-onnxruntime   # no system package needed"),
    ("pymupdf", "Tesseract via PyMuPDF", _probe_pymupdf_ocr,
     "apt-get install tesseract-ocr tesseract-ocr-eng"),
)


def engine_status() -> dict[str, Any]:
    """Which OCR engine, if any, this machine can use -- and why not, per engine.

    Returned rather than raised, and reported verbatim in every refusal, so the
    distinction the module docstring insists on ("no engine here" vs "no table
    there") survives all the way to the reader of a review.
    """
    probed = []
    chosen = None
    for key, name, probe, hint in ENGINES:
        try:
            reason = probe()
        except Exception as exc:                      # a probe must never raise
            reason = f"probe failed: {type(exc).__name__}: {exc}"
        probed.append({"engine": key, "name": name,
                       "available": not reason,
                       "reason": reason, "install": hint})
        if not reason and chosen is None:
            chosen = key
    return {
        "available": chosen is not None,
        "engine": chosen,
        "engines": probed,
        "smallest_install": (
            "" if chosen else
            "rapidocr-onnxruntime is the only one of the three that needs no "
            "root: `pip install rapidocr-onnxruntime` into the project venv "
            "(~80 MB with the bundled models). The others need "
            "`apt-get install tesseract-ocr`, which needs sudo."
        ),
    }


#: The refusal a caller gets when there is no engine. A DISTINCT key, not an
#: empty table -- see the module docstring on why these two must not share a
#: shape.
def unavailable_result(what: str) -> dict[str, Any]:
    st = engine_status()
    missing = "; ".join(f"{e['name']}: {e['reason']}" for e in st["engines"])
    return {
        "error": (
            f"No OCR engine is available on this machine, so {what} was NOT "
            f"read. This is a property of this installation, NOT of the "
            f"document: it says nothing about whether the file contains tables, "
            f"numbers, or anything else. Do not record it as 'no tables found'. "
            f"Probed -- {missing}."
        ),
        "ocr_unavailable": True,
        "ocr_status": st,
        "remedy": st["smallest_install"],
        "tables": [], "text": "", "n_tables": 0,
    }


# ---------------------------------------------------------------------------
# Layout: word boxes -> a grid
# ---------------------------------------------------------------------------

#: A gap between two words on the same line counts as a possible COLUMN BREAK
#: when it exceeds this multiple of the line's own character width. Below it,
#: the gap is word spacing.
#:
#: 1.8 rather than something larger: a numeric table's columns are often only
#: two or three spaces apart, and a threshold that misses the break MERGES two
#: columns into one cell, which reads as `48.90 14.46` -- a single unparseable
#: token, so the cell is dropped rather than misread. A threshold that is too
#: SMALL splits `mean (SD)` into two cells, which is the dangerous direction:
#: the halves then line up under the wrong headings and every value in the row
#: is attributed to the wrong variable. Erring high is erring toward refusal.
_GAP_FACTOR = 1.8

#: A candidate column break is kept only if this share of multi-word lines
#: supports it. A spanning title, a caption or a footnote produces breaks that
#: no other line shares, and without this every one of them would become a
#: column and shred the grid.
_CUT_SUPPORT = 0.6

#: How close two candidate breaks must be, as a multiple of character width, to
#: count as the same break. Typeset columns do not align to the pixel.
_CUT_TOLERANCE = 2.5

#: Two words belong to the same LINE when their vertical centres are within this
#: multiple of the median glyph height. Sub/superscripts and a slightly rotated
#: scan both perturb the centre by well under half a line.
_LINE_TOLERANCE = 0.6

#: Below this median confidence the table is refused whole rather than returned.
#: A table read at 45% confidence is a hypothesis about a table.
_MIN_MEDIAN_CONF = 60.0

#: Individual cells below this are blanked and listed, not silently kept. The
#: blank is honest (we could not read it); keeping a 30%-confidence numeral
#: would put a value nobody printed into a grid a check may later read.
_MIN_CELL_CONF = 40.0


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def group_lines(words: list[OcrWord]) -> list[list[OcrWord]]:
    """Cluster words into text lines by vertical position.

    Sorting by `y` and cutting whenever the centre moves more than a fraction of
    a line is enough here and is stable on a skewed scan; a full baseline fit
    would buy nothing this module's callers can use.
    """
    words = [w for w in words if (w.text or "").strip()]
    if not words:
        return []
    heights = [w.h for w in words if w.h > 0]
    tol = max(1.0, _median(heights) * _LINE_TOLERANCE)
    lines: list[list[OcrWord]] = []
    for w in sorted(words, key=lambda w: (w.cy, w.x)):
        if lines and abs(w.cy - _median([x.cy for x in lines[-1]])) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w.x) for line in lines]


def _char_width(words: list[OcrWord]) -> float:
    """Median width of one character, used to scale every gap threshold.

    Scaling by the type size rather than by absolute pixels is what makes the
    same thresholds work on a 150 dpi scan and a 600 dpi one.
    """
    per = [w.w / len(w.text) for w in words if w.text and w.w > 0]
    return _median(per) or 1.0


def column_cuts(lines: list[list[OcrWord]]) -> list[float]:
    """The x positions where a column break is supported by most lines.

    A break is a candidate wherever one line has a wide gap; it becomes a CUT
    only when enough other lines have a gap in the same place. This is the whole
    defence against a spanning caption or a footnote destroying the grid: those
    lines contribute candidates nobody else shares, so they are dropped.
    """
    multi = [ln for ln in lines if len(ln) >= 2]
    if len(multi) < 2:
        return []
    cw = _char_width([w for ln in lines for w in ln])
    min_gap = cw * _GAP_FACTOR
    tol = cw * _CUT_TOLERANCE

    candidates: list[float] = []
    for line in multi:
        for a, b in zip(line, line[1:]):
            if b.x - a.x1 >= min_gap:
                candidates.append((a.x1 + b.x) / 2)
    if not candidates:
        return []

    # Cluster the candidates, then keep the clusters most lines agree on. The
    # SUPPORT is counted in distinct lines, not in candidates: one line with
    # three gaps at nearly the same x must not out-vote three lines that agree.
    candidates.sort()
    clusters: list[list[float]] = [[candidates[0]]]
    for c in candidates[1:]:
        if c - clusters[-1][-1] <= tol:
            clusters[-1].append(c)
        else:
            clusters.append([c])

    cuts = []
    need = max(2, round(_CUT_SUPPORT * len(multi)))
    for cluster in clusters:
        centre = _median(cluster)
        supporting = 0
        for line in multi:
            if any(a.x1 - tol <= centre <= b.x + tol and b.x - a.x1 >= min_gap
                   for a, b in zip(line, line[1:])):
                supporting += 1
        if supporting >= need:
            cuts.append(centre)
    return cuts


def words_to_grid(words: list[OcrWord]) -> dict[str, Any]:
    """Word boxes -> a rectangular grid of strings, with the doubts recorded.

    Returns `{grid, straddled, n_lines, n_cuts, confidences}`. `straddled` is the
    count of words whose box CROSSES a column cut -- the signal that the cut is
    wrong for that row. It is reported rather than resolved, because a shifted
    column label hands the granularity checks a triple the paper never printed,
    and a grid that quietly guessed is indistinguishable from one that knew.
    """
    lines = group_lines(words)
    if not lines:
        return {"grid": [], "straddled": 0, "n_lines": 0, "n_cuts": 0,
                "confidences": []}
    cuts = column_cuts(lines)
    bounds = [-float("inf"), *cuts, float("inf")]

    grid: list[list[str]] = []
    confidences: list[list[float | None]] = []
    straddled = 0
    for line in lines:
        row = [""] * (len(cuts) + 1)
        conf_row: list[list[float]] = [[] for _ in row]
        for w in line:
            col = 0
            for i in range(len(bounds) - 1):
                if bounds[i] <= w.cx < bounds[i + 1]:
                    col = i
                    break
            # A word whose BOX crosses a cut is evidence against the cut, even
            # though its centre lands cleanly on one side.
            if any(w.x < c < w.x1 for c in cuts):
                straddled += 1
            row[col] = (row[col] + " " + w.text).strip() if row[col] else w.text
            if w.conf is not None:
                conf_row[col].append(w.conf)
        grid.append(row)
        confidences.append([min(c) if c else None for c in conf_row])
    return {"grid": grid, "straddled": straddled, "n_lines": len(lines),
            "n_cuts": len(cuts), "confidences": confidences}


def _gate_confidence(grid: list[list[str]],
                     confidences: list[list[float | None]]) -> tuple[
                         list[list[str]], list[dict], float | None]:
    """Blank the cells we could not read, and report the median confidence.

    A low-confidence cell is REMOVED rather than kept with a warning, because
    the grid is consumed by machinery -- `parse_cells_typed` -> `check_table` --
    that reads cells and not warnings. A warning next to a wrong number does not
    stop the wrong number being checked.
    """
    dropped: list[dict] = []
    kept: list[float] = []
    out: list[list[str]] = []
    for r, (row, crow) in enumerate(zip(grid, confidences)):
        new = []
        for c, (cell, conf) in enumerate(zip(row, crow)):
            if cell and conf is not None and conf < _MIN_CELL_CONF:
                dropped.append({"row": r, "col": c, "text": cell,
                                "confidence": round(conf, 1)})
                new.append("")
                continue
            if cell and conf is not None:
                kept.append(conf)
            new.append(cell)
        out.append(new)
    return out, dropped, (round(_median(kept), 1) if kept else None)


# ---------------------------------------------------------------------------
# Engine adapters
# ---------------------------------------------------------------------------


def _words_pytesseract(image_path: Path, *, config: str = "", timeout: float = 0) -> list[OcrWord]:
    import pytesseract
    from PIL import Image

    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    with Image.open(image_path) as im:
        data = pytesseract.image_to_data(
            im, output_type=pytesseract.Output.DICT, config=config, timeout=timeout)
    words = []
    for i, text in enumerate(data.get("text", [])):
        if not (text or "").strip():
            continue
        try:
            conf = float(data["conf"][i])
        except (KeyError, TypeError, ValueError):
            conf = None
        words.append(OcrWord(
            text=text.strip(), x=float(data["left"][i]), y=float(data["top"][i]),
            w=float(data["width"][i]), h=float(data["height"][i]),
            conf=None if conf is not None and conf < 0 else conf))
    return words


def _words_rapidocr(image_path: Path) -> list[OcrWord]:
    from rapidocr_onnxruntime import RapidOCR

    result, _ = RapidOCR()(str(image_path))
    words = []
    for box, text, score in (result or []):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        # RapidOCR returns LINE boxes, not word boxes. Splitting the line's box
        # evenly across its words is an approximation, and it is the honest one
        # available: the alternative is one cell per line, which loses every
        # column and would silently turn a table into prose.
        parts = (text or "").split()
        if not parts:
            continue
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        span = (x1 - x0) / len(parts)
        for i, part in enumerate(parts):
            words.append(OcrWord(text=part, x=x0 + i * span, y=y0,
                                 w=span, h=y1 - y0,
                                 conf=float(score) * 100 if score else None))
    return words


def _words_pymupdf(image_path: Path) -> list[OcrWord]:
    import fitz

    with fitz.open(image_path) as doc:
        page = doc[0]
        tp = page.get_textpage_ocr(dpi=300, full=True)
        words = []
        for x0, y0, x1, y1, text, *_ in page.get_text("words", textpage=tp):
            if not (text or "").strip():
                continue
            words.append(OcrWord(text=text.strip(), x=x0, y=y0,
                                 w=x1 - x0, h=y1 - y0, conf=None))
    return words


_ADAPTERS = {
    "pytesseract": _words_pytesseract,
    "rapidocr": _words_rapidocr,
    "pymupdf": _words_pymupdf,
}


def ocr_words(image_path: str | Path, engine: str | None = None, *,
              config: str = "", timeout: float = 0) -> dict[str, Any]:
    """Run the best available engine over one image. `{words, engine}` or a refusal."""
    st = engine_status()
    key = engine or st["engine"]
    if key is None:
        return unavailable_result(Path(image_path).name)
    adapter = _ADAPTERS.get(key)
    if adapter is None:
        return {"error": f"unknown OCR engine {key!r}", "ocr_unavailable": True,
                "ocr_status": st, "tables": [], "text": "", "n_tables": 0}
    try:
        words = (adapter(Path(image_path), config=config, timeout=timeout)
                 if key == "pytesseract" else adapter(Path(image_path)))
    except Exception as exc:
        # An engine that CRASHED told us nothing, and must not be reported as an
        # engine that found nothing.
        return {
            "error": (f"the {key} OCR engine raised on "
                      f"{Path(image_path).name}: {type(exc).__name__}: {exc}. "
                      "Nothing was read, so the file's contents are UNKNOWN."),
            "ocr_failed": True, "ocr_status": st,
            "tables": [], "text": "", "n_tables": 0,
        }
    return {"words": words, "engine": key}
