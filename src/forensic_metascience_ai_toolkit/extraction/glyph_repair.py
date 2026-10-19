"""Restore characters a PDF's broken SYMBOL fonts destroyed, by their SHAPE.

THE DEFECT. Some publishers' math fonts (Advent `AdvMPi-One`, `AdvP4C4E74`,
`AdvPi1`; `MathTechnicalP*`; `MathematicalPi-*`) carry wrong Unicode maps. On
schnall2008.pdf (Psych Science) a printed `F(1, 38) = 3.63, p_rep = .90,
η² = .09` reaches every extractor as `F (1, 38) 5 3.63, p rep 5 .90, Z p 2 ¼
: 09`: `=` is `5` (36 times) or `¼`, `η` is `Z`, and a decimal point is `:`.
The embedded CFF glyph NAMES are wrong too (`five`, `onequarter`, `Z`), so no
name-based remap helps, and the codes are reassigned per PDF, so no global
table helps either. statcheck reads none of those statistics.

THE REPAIR, AND WHY IT IS NOT OCR. What the reader SEES is the glyph's outline,
and the outline is in the PDF: the embedded font program. Each distinct (font,
glyph) a symbol font draws is rasterised ONCE from that program -- isolated, so
no neighbouring ink -- and template-matched against reference symbols drawn
from MuPDF's built-in fonts (Nimbus Roman/Sans/Mono, Standard Symbols; shipped
with PyMuPDF, so the references are the same on every machine). Whole-line and
whole-page OCR were measured and rejected (docs/DESIGN_DECISIONS.md): Tesseract
read `p_rep = .95` as `Prep = -95`, inventing a minus sign, and docling's OCR
invented CJK characters in 6 of 22 papers. This module reads no pixels of the
page, generates nothing, and can only choose among a closed set of characters.

THE RULES, each enforced here:

  - Only characters drawn by a SYMBOL font are candidates (`is_symbol_font`).
    A character drawn by any other font is kept exactly as extracted.
  - The extracted character is the default. It is overturned only when the
    shape scores at least `ACCEPT_SCORE` AND beats every other character --
    including the extracted one -- by `ACCEPT_MARGIN`. Otherwise the glyph is
    left as-is and REPORTED as ambiguous.
  - A printable extracted character outside the reference set (`●`, `√`) can
    not be checked, so it is never changed.
  - All glyphs that share a (font, extracted character) must agree, because a
    text string cannot tell them apart. If they do not, none is changed.
  - A docling occurrence is repaired only when its context locates it at
    positions the PDF text layer proves are ALL drawn by that symbol glyph.
    Context that also matches a genuine character is left alone and reported.
  - Every edit is logged as a `repairs.Repair`; the cache on disk is never
    rewritten, so the original extraction is retained.

MEASURED 2026-10-19 over 89 PDFs (the statcheck p-value corpus plus
schnall2008): of 1,378 glyphs whose extracted character is a printable
reference character -- symbol fonts and, as a negative control, whole text
fonts (Minion, Century, Cambria Math) -- 1,310 shape-matched their extracted
character, 56 were refused, and all 12 overturned were in fonts whose maps are
broken (`AdvMPi-One 5->=`, `AdvP4C4E51 :->.`, `AdvPi1 Z->η` and `6->×`,
`MathTechnicalP01 !-><` and `1->>`, `MathTechnicalP03 p->=`,
`MathTechnicalP04 #->×`, `MathTechnicalP12 b->β h->η x->χ`). Zero changes to a
correct character. Each was checked against the rendered page.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import io
import re
import unicodedata
from pathlib import Path
from typing import Any

#: Bumped whenever a rule or threshold changes what is repaired.
REPAIR_VERSION = 1

RULE = "glyph_repair.shape_match"

#: Calibrated on the measurement in the module docstring.
ACCEPT_SCORE = 0.6
ACCEPT_MARGIN = 0.2

#: The closed set a glyph may be identified as. Symbols the statistics depend
#: on, Greek used in effect sizes, and ASCII look-alikes -- the look-alikes are
#: there so a glyph that really IS a `5` can be recognised as one.
REFERENCE_SYMBOLS = "=<>≤≥±×÷−·•°′∼≈≠∗ηχαβγδεθλµπρστφψωΔΣΩ¼½¾€§†‡"
REFERENCE_ASCII = ("0123456789abcdefghijklmnopqrstuvwxyz"
                   "ABCDEFGHIJKLMNOPQRSTUVWXYZ.,:;()[]+-–—/%*'\"!?#&")
REFERENCE_CHARS = REFERENCE_SYMBOLS + REFERENCE_ASCII

#: MuPDF's built-in Base-14 fonts. Each glyph is also drawn slanted, because
#: math fonts set Greek in italic.
_REFERENCE_FONTS = ("tiro", "tiit", "tibo", "helv", "hebo", "cour", "symb")
_SLANT = 0.21

#: Glyph shapes cannot tell these apart, and nothing downstream needs them
#: told apart: a bar is written as ASCII hyphen-minus, which every reader in
#: this pipeline already takes as a minus and as a range dash.
_DASHES = frozenset("-−–—")
_DASH_OUT = "-"

_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}

#: Characters ignored when comparing an extracted string with the layer:
#: docling's markdown table delimiter is not on the page.
_IGNORED = frozenset("|")


# --------------------------------------------------------------------------
# Which fonts are candidates
# --------------------------------------------------------------------------

def is_symbol_font(name: str) -> bool:
    """Does this font name mark a symbol / pi / math font?

    The scaffold's `fontaudit._is_symbol_font` plus the math families it
    missed: `AdvMPi-One` (the font drawing every `=` in schnall2008),
    `MathematicalPi-*`, `MathTechnicalP*`, MathType's `MTSY`/`MTMI`/`MTGU`
    and other `*Math*` fonts. Subset prefixes without a `+` (`CjhwjmAdvP4C4E74`)
    are tolerated by searching rather than anchoring.
    """
    from ..scaffold.fontaudit import _is_symbol_font
    if _is_symbol_font(name):
        return True
    low = (name or "").lower()
    if re.search(r"adv(?:m?pi\d|mpi|p4c4e)", low):
        return True
    if re.search(r"math|mtsy|mtmi|mtgu|mtex|euclidsymbol", low):
        return True
    return False


def _unprintable(ch: str) -> bool:
    """An extracted character that cannot be what the page shows: a control
    code, a private-use code point, or the replacement character."""
    if not ch:
        return True
    cat = unicodedata.category(ch)
    return cat in ("Cc", "Co", "Cn", "Cs") or ch == "�"


def _cls(ch: str) -> str:
    if ch in _DASHES:
        return "-"
    if ch == "μ":  # GREEK MU and MICRO SIGN are one shape
        return "µ"
    return ch


# --------------------------------------------------------------------------
# Rendering an outline from a font program
# --------------------------------------------------------------------------

class _FontProgram:
    """A glyph-id addressable outline source: bare CFF, or TrueType/OpenType."""

    def __init__(self, buf: bytes, ext: str):
        ext = (ext or "").lower()
        if ext == "cff":
            from fontTools.cffLib import CFFFontSet
            cff = CFFFontSet()
            cff.decompile(io.BytesIO(buf), None)
            top = cff[cff.fontNames[0]]
            self._glyphs = top.CharStrings
            self._order = list(top.charset)
            fm = getattr(top, "FontMatrix", None) or [0.001]
            self._scale = fm[0] or 0.001
        elif ext in ("ttf", "otf"):
            from fontTools.ttLib import TTFont
            f = TTFont(io.BytesIO(buf))
            self._glyphs = f.getGlyphSet()
            self._order = f.getGlyphOrder()
            self._scale = 1.0 / f["head"].unitsPerEm
        else:
            raise ValueError(f"font program type {ext!r} is not rendered here")

    def polys(self, gid: int) -> list[list[tuple[float, float]]] | None:
        if gid < 0 or gid >= len(self._order):
            return None
        from fontTools.pens.basePen import BasePen

        class _Pen(BasePen):
            def __init__(pen):
                super().__init__(None)
                pen.out: list[list[tuple[float, float]]] = []
                pen.cur: list[tuple[float, float]] = []

            def _moveTo(pen, p):
                pen._flush()
                pen.cur = [p]

            def _lineTo(pen, p):
                pen.cur.append(p)

            def _curveToOne(pen, p1, p2, p3):
                x0, y0 = pen.cur[-1]
                for i in range(1, 9):
                    t = i / 8
                    m = 1 - t
                    pen.cur.append((m**3 * x0 + 3 * m * m * t * p1[0] + 3 * m * t * t * p2[0] + t**3 * p3[0],
                                    m**3 * y0 + 3 * m * m * t * p1[1] + 3 * m * t * t * p2[1] + t**3 * p3[1]))

            def _qCurveToOne(pen, p1, p2):
                x0, y0 = pen.cur[-1]
                for i in range(1, 9):
                    t = i / 8
                    m = 1 - t
                    pen.cur.append((m * m * x0 + 2 * m * t * p1[0] + t * t * p2[0],
                                    m * m * y0 + 2 * m * t * p1[1] + t * t * p2[1]))

            def _closePath(pen):
                pen._flush()

            _endPath = _closePath

            def _flush(pen):
                if len(pen.cur) > 2:
                    pen.out.append(pen.cur)
                pen.cur = []

        pen = _Pen()
        self._glyphs[self._order[gid]].draw(pen)
        pen._flush()
        s = self._scale
        return [[(x * s, y * s) for x, y in poly] for poly in pen.out]


def _raster(polys, sx, sy, ox, oy, w, h, xmin, ymax):
    import cv2
    import numpy as np
    img = np.zeros((h, w), np.uint8)
    arr = [np.round(np.array([[((x - xmin) * sx + ox) * 16, ((ymax - y) * sy + oy) * 16]
                              for x, y in p])).astype(np.int32) for p in polys]
    cv2.fillPoly(img, arr, 255, lineType=cv2.LINE_AA, shift=4)
    return img.astype(np.float32) / 255


def _features(polys, slant: float = 0.0) -> dict | None:
    """Shape descriptors in EM units: the outline stretched to a square (which
    removes the typeface's proportions), the outline placed on a fixed em grid
    (which keeps its size and height), and its ink extent against the
    baseline -- the only thing separating `.` from `·`, or `η` from `n`."""
    import numpy as np
    if not polys:
        return None
    if slant:
        polys = [[(x + slant * y, y) for x, y in p] for p in polys]
    pts = np.concatenate([np.array(p) for p in polys])
    xmin, ymin = pts.min(0)
    xmax, ymax = pts.max(0)
    w, h = float(xmax - xmin), float(ymax - ymin)
    if w <= 0 and h <= 0:
        return None
    n = 32
    # A thin stroke (a bar) is not stretched into a block.
    sx = (n - 2) / max(w, 0.08)
    sy = (n - 2) / max(h, 0.08)
    sq = _raster(polys, sx, sy, (n - w * sx) / 2, (n - h * sy) / 2, n, n, xmin, ymax)
    e = 40
    se = e / 1.35          # the window runs from 1.0 em above to 0.35 below
    em = _raster(polys, se, se, (e - w * se) / 2, (1.0 - ymax) * se, e, e, xmin, ymax)
    return {"top": float(ymax), "bot": float(ymin), "w": w, "h": h,
            "sq": sq, "em": em}


def _corr(a, b) -> float:
    import numpy as np
    x = a - a.mean()
    y = b - b.mean()
    d = float(np.sqrt((x * x).sum() * (y * y).sum()))
    return float((x * y).sum()) / d if d > 1e-9 else 0.0


def _score(a: dict, b: dict) -> float:
    import math
    corr = (0.3 * _corr(a["sq"], b["sq"]) + 0.3 * _corr(a["em"], b["em"])
            + 0.25 * _corr(a["sq"].sum(1), b["sq"].sum(1))
            + 0.15 * _corr(a["sq"].sum(0), b["sq"].sum(0)))
    geo = abs(a["top"] - b["top"]) + abs(a["bot"] - b["bot"])
    asp = abs(math.log((a["w"] + .02) / (a["h"] + .02))
              - math.log((b["w"] + .02) / (b["h"] + .02)))
    return corr - geo - 0.15 * asp


@functools.lru_cache(maxsize=1)
def _references() -> dict[str, list[dict]]:
    import fitz
    out: dict[str, list[dict]] = {}
    for name in _REFERENCE_FONTS:
        font = fitz.Font(name)
        prog = _FontProgram(font.buffer, "cff")
        for ch in REFERENCE_CHARS:
            gid = font.has_glyph(ord(ch))
            if not gid:
                continue
            polys = prog.polys(gid)
            for slant in (0.0, _SLANT):
                f = _features(polys, slant)
                if f is not None:
                    out.setdefault(ch, []).append(f)
    return out


def identify(polys) -> dict:
    """`{best, score, margin, runner_up, ranked}` for one outline, or
    `{best: None}` when it has no ink. `margin` is measured against the best
    character of a DIFFERENT class (the dashes are one class)."""
    f = _features(polys)
    if f is None:
        return {"best": None, "score": None, "margin": None, "runner_up": None,
                "ranked": []}
    best: dict[str, float] = {}
    for ch, refs in _references().items():
        k = _cls(ch)
        s = max(_score(f, r) for r in refs)
        if k not in best or s > best[k]:
            best[k] = s
    ranked = sorted(best.items(), key=lambda kv: -kv[1])
    top, s1 = ranked[0]
    s2 = ranked[1][1] if len(ranked) > 1 else -1.0
    return {"best": top, "score": round(s1, 3), "margin": round(s1 - s2, 3),
            "runner_up": ranked[1][0] if len(ranked) > 1 else None,
            "ranked": [(c, round(s, 3)) for c, s in ranked[:5]]}


# --------------------------------------------------------------------------
# The per-document glyph map
# --------------------------------------------------------------------------

def _pdf_key(pdf: Path) -> tuple:
    st = pdf.stat()
    return (str(pdf.resolve()), st.st_size, st.st_mtime_ns)


def glyph_map(pdf: str | Path) -> dict:
    """Identify every distinct glyph the PDF's symbol fonts draw.

    Returns `{version, status, error, fonts, glyphs, map, refused}`:

      `status`   `no_symbol_fonts` | `verified` (every symbol glyph matched
                 its extracted character, or was refused) | `repairable` |
                 `error`
      `glyphs`   one row per (font, extracted character): its glyph ids, the
                 occurrence count, `decision` in `kept` / `repair` /
                 `ambiguous` / `unrenderable` / `unverifiable`, and the scores
      `map`      `{font: {extracted: intended}}` for the `repair` rows only
      `refused`  the `ambiguous` and `unrenderable` rows: the characters left
                 as extracted that may nonetheless be wrong

    Memoised per process on the file's identity; never raises.
    """
    p = Path(pdf)
    try:
        key = _pdf_key(p)
    except OSError as exc:
        return _empty("error", f"cannot stat {p.name}: {exc}")
    return copy.deepcopy(_glyph_map_cached(key))


def _empty(status: str, error: str | None = None) -> dict:
    return {"version": REPAIR_VERSION, "status": status, "error": error,
            "fonts": [], "glyphs": [], "map": {}, "refused": []}


@functools.lru_cache(maxsize=256)
def _glyph_map_cached(key: tuple) -> dict:
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - environment
        return _empty("error", f"PyMuPDF not installed: {exc}")
    path = key[0]
    try:
        doc = fitz.open(path)
    except Exception as exc:  # noqa: BLE001
        return _empty("error", f"could not open {Path(path).name}: "
                               f"{type(exc).__name__}: {exc}")
    try:
        return _build_map(doc)
    except Exception as exc:  # noqa: BLE001 -- reported, never raised
        return _empty("error", f"glyph identification failed: "
                               f"{type(exc).__name__}: {exc}")
    finally:
        doc.close()


def _build_map(doc) -> dict:
    # Which programs carry each symbol font name, page by page.
    programs: dict[int, Any] = {}
    groups: dict[tuple[str, str], dict] = {}
    fonts_seen: set[str] = set()
    for pno in range(len(doc)):
        page_fonts: dict[str, list[tuple[int, str]]] = {}
        for xref, ext, _typ, base, *_ in doc.get_page_fonts(pno):
            page_fonts.setdefault(base.split("+", 1)[-1], []).append((xref, ext))

        def _programs(font: str) -> tuple:
            # A span names the font by its INTERNAL name, which need not be
            # the /BaseFont (`AdvMPi-One` vs `AdvMPi-One Regular`).
            if font in page_fonts:
                return tuple(page_fonts[font])
            return tuple(c for b, cs in page_fonts.items()
                         if b.startswith(font) or font.startswith(b) for c in cs)

        # A page whose fonts are all text fonts costs nothing more: tracing
        # glyphs is the expensive step and is skipped.
        if not any(is_symbol_font(b) for b in page_fonts):
            continue
        for span in doc[pno].get_texttrace():
            font = span.get("font") or ""
            if not is_symbol_font(font):
                continue
            cands = _programs(font)
            if not cands:
                continue
            fonts_seen.add(font)
            for ch in span.get("chars", ()):
                cp, gid = ch[0], ch[1]
                if cp is None or cp < 0:
                    c = "\ufffd"
                else:
                    c = chr(cp)
                if c.isspace():
                    continue
                g = groups.setdefault((font, c), {"gids": {}, "n": 0,
                                                   "pages": set()})
                g["n"] += 1
                g["pages"].add(pno + 1)
                g["gids"].setdefault(gid, cands)
    if not fonts_seen:
        return _empty("no_symbol_fonts")

    def _identify_glyph(gid: int, candidates: tuple) -> dict:
        results = []
        for xref, ext in candidates:
            if xref not in programs:
                try:
                    programs[xref] = _FontProgram(doc.extract_font(xref)[3], ext)
                except Exception as exc:  # noqa: BLE001
                    programs[xref] = exc
            prog = programs[xref]
            if isinstance(prog, Exception):
                results.append({"error": str(prog)})
                continue
            polys = prog.polys(gid)
            if polys is None:
                continue
            results.append(identify(polys))
        good = [r for r in results if "error" not in r]
        if not good:
            why = next((r["error"] for r in results if "error" in r),
                       "glyph not found in the embedded program")
            return {"error": why}
        if len({r["best"] for r in good}) > 1:
            # Several embedded subsets share the name, and they disagree.
            return {"error": "several embedded programs share this font name "
                             "and draw different shapes for this glyph"}
        return min(good, key=lambda r: (r["margin"] or 0))

    rows: list[dict] = []
    for (font, c), g in sorted(groups.items()):
        row = {"font": font, "extracted": c, "codepoint": f"U+{ord(c):04X}",
               "n": g["n"], "pages": sorted(g["pages"]), "glyph_ids": sorted(g["gids"]),
               "decision": None, "intended": None, "score": None,
               "margin": None, "runner_up": None, "why": None}
        rows.append(row)
        if not _unprintable(c) and _cls(c) not in {_cls(x) for x in REFERENCE_CHARS}:
            row["decision"] = "unverifiable"
            row["why"] = "the extracted character is outside the reference set, so it cannot be checked; kept"
            continue
        ids = [_identify_glyph(gid, cands) for gid, cands in sorted(g["gids"].items())]
        errs = [r["error"] for r in ids if "error" in r]
        if errs:
            row["decision"] = "unrenderable"
            row["why"] = errs[0]
            continue
        ids = [r for r in ids if r["best"] is not None]
        if not ids:
            row["decision"] = "unverifiable"
            row["why"] = "the glyph has no ink"
            continue
        worst = min(ids, key=lambda r: (r["score"], r["margin"]))
        row.update(score=worst["score"], margin=worst["margin"],
                   runner_up=worst["runner_up"], intended=worst["best"])
        if len({r["best"] for r in ids}) > 1:
            row["decision"] = "ambiguous"
            row["why"] = ("glyphs reported as the same character have different "
                          "shapes, so a text string cannot tell them apart")
            continue
        best = ids[0]["best"]
        if best == _cls(c):
            row["decision"] = "kept"
            continue
        if worst["score"] < ACCEPT_SCORE or worst["margin"] < ACCEPT_MARGIN:
            row["decision"] = "ambiguous"
            row["why"] = (f"best match {best!r} scored {worst['score']} with a margin of "
                          f"{worst['margin']} over {worst['runner_up']!r}; below "
                          f"{ACCEPT_SCORE}/{ACCEPT_MARGIN}, so the character is left as extracted")
            continue
        row["decision"] = "repair"
        row["intended"] = _DASH_OUT if best == "-" else best
    out = _empty("verified")
    out["fonts"] = sorted(fonts_seen)
    out["glyphs"] = rows
    for r in rows:
        if r["decision"] == "repair":
            out["map"].setdefault(r["font"], {})[r["extracted"]] = r["intended"]
        elif r["decision"] in ("ambiguous", "unrenderable"):
            out["refused"].append(r)
    if out["map"]:
        out["status"] = "repairable"
    return out


# --------------------------------------------------------------------------
# The PDF text layer, repaired character by character
# --------------------------------------------------------------------------

def _layer(pdf: Path, gmap: dict) -> dict:
    """The PyMuPDF text layer as a whitespace-free comparison string with,
    per position, the repair it calls for (`None` for a trusted character,
    `"?"` for a symbol-font character that was refused), and per page the
    text with every accepted repair applied."""
    import fitz
    fmap = gmap.get("map") or {}
    refused = {(r["font"], r["extracted"]) for r in gmap.get("refused") or ()}
    cmp: list[str] = []
    target: list[str | None] = []
    pages: list[str] = []
    with fitz.open(str(pdf)) as doc:
        for page in doc:
            parts: list[str] = []
            for block in page.get_text("rawdict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font = span.get("font") or ""
                        repl = fmap.get(font) or {}
                        for ch in span.get("chars", []):
                            c = ch.get("c", "")
                            parts.append(repl.get(c, c))
                            if c.isspace() or c in _IGNORED:
                                continue
                            t = repl.get(c)
                            if t is None and (font, c) in refused:
                                t = "?"
                            for piece in _LIGATURES.get(c, c):
                                cmp.append(_cls(piece))
                                target.append(t)
                    parts.append("\n")
                parts.append("\n")
            pages.append("".join(parts))
    return {"cmp": "".join(cmp), "target": target, "pages": pages}


@functools.lru_cache(maxsize=64)
def _layer_cached(key: tuple, map_sig: str) -> dict:
    return _layer(Path(key[0]), glyph_map(key[0]))


def repaired_text_layer(pdf: str | Path) -> str | None:
    """The PDF text layer with this document's proven repairs applied, or None
    when there is nothing to repair. Quote verification reads this, so a quote
    of the repaired docling text is found in the layer too."""
    p = Path(pdf)
    gmap = glyph_map(p)
    if not gmap.get("map"):
        return None
    try:
        return "\n".join(_layer_cached(_pdf_key(p), _map_sig(gmap))["pages"])
    except Exception as exc:  # noqa: BLE001 -- the caller falls back to the raw layer
        import warnings
        warnings.warn(f"{p.name}: repaired text layer unavailable "
                      f"({type(exc).__name__}: {exc}); the raw layer is used", stacklevel=2)
        return None


def _map_sig(gmap: dict) -> str:
    return repr(sorted((f, sorted(m.items())) for f, m in (gmap.get("map") or {}).items()))


# --------------------------------------------------------------------------
# Repairing an extracted string against the layer
# --------------------------------------------------------------------------

_MIN_CONTEXT = 4
_CONTEXTS = (10, 7, 5, 3, 2)


def repair_string(s: str, layer: dict, raw_chars: frozenset[str],
                  *, target: str = "body") -> tuple[str, list, list[dict]]:
    """`(repaired, [Repair], [unresolved])` for one extracted string.

    Each occurrence of a character the map repairs is located in the PDF text
    layer by its non-whitespace context, longest first. It is repaired only
    when EVERY place that context occurs in the layer is drawn by a glyph the
    map repairs, all to the same character. A context that also occurs at a
    trusted character is left alone (that is how a genuine `5` survives), and
    one that occurs at a refused glyph is left alone and reported.
    """
    from ..repairs import Repair
    if not s or not raw_chars or not any(c in s for c in raw_chars):
        return s, [], []
    # Comparison form of `s`, with an index back into `s`.
    sc: list[str] = []
    idx: list[int] = []
    for i, c in enumerate(s):
        if c.isspace() or c in _IGNORED:
            continue
        for piece in _LIGATURES.get(c, c):
            sc.append(_cls(piece))
            idx.append(i)
    scs = "".join(sc)
    F = layer["cmp"]
    T = layer["target"]
    edits: list[tuple[int, int, str, str]] = []   # (start, end, new, char)
    unresolved: list[dict] = []
    seen_pos: set[int] = set()
    for j, c in enumerate(scs):
        i = idx[j]
        if s[i] not in raw_chars or i in seen_pos:
            continue
        seen_pos.add(i)
        verdict = None
        for k in _CONTEXTS:
            left = scs[max(0, j - k):j]
            right = scs[j + 1:j + 1 + k]
            whole = len(left) + len(right) == len(scs) - 1
            if len(left) + len(right) < _MIN_CONTEXT and not (whole and len(scs) >= 3):
                break
            w = left + c + right
            hits = []
            start = F.find(w)
            while start != -1:
                hits.append(start + len(left))
                start = F.find(w, start + 1)
            if not hits:
                continue
            kinds = {T[h] for h in hits}
            if kinds == {None}:
                verdict = ("trusted", None, None)
            elif len(kinds) == 1 and None not in kinds and "?" not in kinds:
                verdict = ("repair", kinds.pop(), hits[0])
            else:
                verdict = ("mixed", w, None)
            break
        if verdict is None:
            unresolved.append({"target": target, "offset": i, "char": s[i],
                               "why": "not located in the PDF text layer",
                               "context": s[max(0, i - 15):i + 16]})
            continue
        if verdict[0] == "trusted":
            continue
        if verdict[0] == "mixed":
            unresolved.append({"target": target, "offset": i, "char": s[i],
                               "why": "its context occurs both at a symbol-font "
                                      "glyph and at a trusted or refused character",
                               "context": s[max(0, i - 15):i + 16]})
            continue
        _, new, _h = verdict
        a, b = i, i + 1
        # Docling pads a symbol-font glyph with spaces. Elsewhere that padding
        # is kept -- whether `=` had a space beside it is not recoverable, since
        # math fonts build the gap into the glyph's own advance -- but a
        # DECIMAL POINT is never spaced, and `. 09` would split the number.
        if new == ".":
            j2 = b
            while j2 < len(s) and s[j2] in " \t":
                j2 += 1
            if j2 > b and j2 < len(s) and s[j2].isdigit():
                b = j2
            j1 = a
            while j1 > 0 and s[j1 - 1] in " \t":
                j1 -= 1
            if j1 < a and j1 > 0 and s[j1 - 1].isdigit():
                a = j1
        edits.append((a, b, new, s[i]))
    if not edits:
        return s, [], unresolved
    out: list[str] = []
    repairs: list = []
    cur = 0
    for a, b, new, old in sorted(edits):
        if a < cur:            # overlapping padding with the previous edit
            a = cur
        out.append(s[cur:a])
        out.append(new)
        ctx0 = max(0, a - 12)
        ctx1 = min(len(s), b + 12)
        repairs.append(Repair(
            rule=RULE,
            reason=(f"{old!r} (U+{ord(old):04X}) is drawn by a symbol-font glyph "
                    f"whose outline shape-matches {new!r}; the font's Unicode map is "
                    "wrong. Restores what the page shows; invents nothing."),
            before=s[ctx0:ctx1], after=s[ctx0:a] + new + s[b:ctx1],
            offset=a, target=target, narrows_only=False))
        cur = b
    out.append(s[cur:])
    return "".join(out), repairs, unresolved


def _walk(obj: Any, fn, path: str):
    """Apply `fn(string, target)` to every string in a table dict."""
    if isinstance(obj, str):
        return fn(obj, path)
    if isinstance(obj, list):
        return [_walk(v, fn, path) for v in obj]
    if isinstance(obj, dict):
        return {k: (v if k in ("source", "graphic_href") else _walk(v, fn, path))
                for k, v in obj.items()}
    return obj


def summary(gmap: dict) -> dict:
    """The compact record a review carries: what was repaired, what refused."""
    return {
        "version": gmap.get("version", REPAIR_VERSION),
        "status": gmap.get("status"),
        "error": gmap.get("error"),
        "symbol_fonts": gmap.get("fonts", []),
        "repaired_glyphs": [
            {k: r[k] for k in ("font", "extracted", "codepoint", "intended", "n",
                               "score", "margin", "runner_up")}
            for r in gmap.get("glyphs", []) if r["decision"] == "repair"],
        "refused_glyphs": [
            {k: r[k] for k in ("font", "extracted", "codepoint", "n", "decision",
                               "intended", "score", "margin", "why")}
            for r in gmap.get("refused", [])],
    }


def apply_to_extraction(data: dict, pdf: str | Path) -> dict:
    """`data` (a docling cache entry) with this PDF's proven repairs applied
    to `text`, `references`, `pages[].text` and every table string.

    The input is not modified and the cache on disk is not rewritten: the
    original extraction is what is retained. The result carries
    `glyph_repair` (`summary` plus `n_repaired`, `repairs`, `unresolved`).
    A PDF without symbol fonts costs one font listing and is returned with a
    short `glyph_repair` record and otherwise unchanged.
    """
    if not isinstance(data, dict) or data.get("error"):
        return data
    p = Path(pdf)
    try:
        key = _pdf_key(p)
    except OSError:
        return data
    # The WHOLE entry is the key: two entries with the same text and
    # different tables must not share a result.
    import json as _json
    h = hashlib.sha256(_json.dumps(
        {k: data.get(k) for k in ("text", "references", "pages", "tables")},
        sort_keys=True, default=str).encode("utf-8", "replace")).hexdigest()
    out = dict(data)
    out.update(copy.deepcopy(_apply_cached(key, h, _Frozen(data))))
    return out


class _Frozen:
    """Lets the lru_cache key on the content hash while carrying the dict."""

    def __init__(self, data):
        self.data = data

    def __hash__(self):
        return 0

    def __eq__(self, other):
        return isinstance(other, _Frozen)


@functools.lru_cache(maxsize=64)
def _apply_cached(key: tuple, content_hash: str, frozen: _Frozen) -> dict:
    data = frozen.data
    gmap = glyph_map(key[0])
    rec = summary(gmap)
    rec.update(n_repaired=0, repairs=[], unresolved=[],
               original_sha256=hashlib.sha256(
                   (data.get("text") or "").encode("utf-8", "replace")).hexdigest())
    fmap = gmap.get("map") or {}
    if not fmap:
        return {"glyph_repair": rec}
    try:
        layer = _layer_cached(key, _map_sig(gmap))
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"text layer unreadable: {type(exc).__name__}: {exc}"
        return {"glyph_repair": rec}
    raw = frozenset(c for m in fmap.values() for c in m)
    repairs: list = []
    unresolved: list[dict] = []

    def fix(s: str, target: str) -> str:
        new, reps, unres = repair_string(s, layer, raw, target=target)
        repairs.extend(reps)
        unresolved.extend(unres)
        return new

    changed: dict[str, Any] = {}
    if data.get("text"):
        changed["text"] = fix(data["text"], "body")
    if data.get("references"):
        changed["references"] = fix(data["references"], "references")
    if data.get("pages"):
        changed["pages"] = [
            {**pg, "text": fix(pg.get("text") or "", f"page:{pg.get('page_num')}")}
            if isinstance(pg, dict) else pg for pg in data["pages"]]
    if data.get("tables"):
        changed["tables"] = [
            _walk(t, fix, f"table:{t.get('table_num', n + 1) if isinstance(t, dict) else n + 1}")
            for n, t in enumerate(data["tables"])]
    from dataclasses import asdict
    rec["n_repaired"] = len(repairs)
    rec["repairs"] = [asdict(r) for r in repairs]
    # One line per distinct unresolved spot is enough to act on.
    rec["unresolved"] = unresolved[:200]
    rec["n_unresolved"] = len(unresolved)
    changed["glyph_repair"] = rec
    return changed


# --------------------------------------------------------------------------
# Recording the repair, and telling the analysts
# --------------------------------------------------------------------------

def paper_record(paper_dir: str | Path, *, write: bool = False) -> dict | None:
    """The repair record for a paper directory's main PDF, read from its docling
    cache (never extracting), or None when there is no PDF or no cache.
    `write=True` also records the edits in `markdown/repairs.json`."""
    from .docling_tables import extract_pdf_tables
    from .jats import find_pdf
    pdf = find_pdf(Path(paper_dir))
    if pdf is None:
        return None
    res = extract_pdf_tables(pdf, allow_extract=False)
    rec = res.get("glyph_repair")
    if not isinstance(rec, dict):
        return None
    rec = dict(rec)
    rec["pdf"] = Path(pdf).name
    if write:
        try:
            record(paper_dir, rec)
        except Exception as exc:  # noqa: BLE001 -- the repair stands; say the log failed
            import warnings
            warnings.warn(f"{paper_dir}: the glyph repairs were applied but could "
                          f"not be written to markdown/repairs.json "
                          f"({type(exc).__name__}: {exc})", stacklevel=2)
    return rec


def record(paper_dir: str | Path, rec: dict) -> Path | None:
    """Write this repair's edits into `markdown/repairs.json`, the declared
    repair ledger, replacing any earlier entries of this rule and keeping every
    other entry and flag as it was. Returns the path, or None when there was
    nothing to record."""
    from .. import repairs as _rp
    reps = (rec or {}).get("repairs") or []
    log = _rp.load(paper_dir)
    if log is None:
        if not reps:
            return None
        log = _rp.RepairLog(paper_id=Path(paper_dir).name,
                            original_sha256=rec.get("original_sha256") or "",
                            original_source="pdf (docling cache)")
    kept = [r for r in log.repairs if r.rule != RULE]
    if not reps and len(kept) == len(log.repairs):
        return None
    log.repairs = kept + [_rp.Repair(**r) for r in reps]
    return _rp.save(paper_dir, log)


def _fmt_char(c: str) -> str:
    return f"`{c}`" if c and c.isprintable() and not c.isspace() else f"U+{ord(c):04X}"


def analyst_note(paper_dir: str | Path, text: str | None, rec: dict | None = None) -> str:
    """A paragraph appended to both analyst prompts, or "".

    Tells the models what the glyph scan and the font repair found, so they
    neither trust a damaged character nor silently decode it themselves. The
    models decoded `5` as `=` on their own before this existed, which is right
    on schnall2008 and would be a guess on the next paper.
    """
    from ..glyphs import scan
    g = scan(text or "")
    rec = rec or {}
    repaired = rec.get("repaired_glyphs") or []
    refused = rec.get("refused_glyphs") or []
    if not (g.get("quarantine") or repaired or refused or not g.get("clean")):
        return ""
    lines = ["", "", "**THIS PAPER'S TEXT LAYER HAS FONT-ENCODING DAMAGE.**"]
    if repaired:
        lines.append(
            f"The PDF's symbol fonts carry wrong Unicode maps. We identified each "
            "damaged glyph by the SHAPE of its outline in the embedded font and "
            "restored it in the PDF's extracted text -- the paper text, its tables "
            f"and `extract_pdf` ({rec.get('n_repaired', 0)} edits, each logged):")
        for r in repaired:
            lines.append(f"- font {r['font']}: extracted as {_fmt_char(r['extracted'])}, "
                         f"drawn as {_fmt_char(r['intended'])} ({r['n']} glyphs)")
        lines.append(
            "Any other reading of this PDF -- a supplement, a copy, a tool that "
            "reads the raw text layer -- may still show the broken form. Where you see "
            "one of the extracted characters above in a statistic, it is the drawn "
            "character, not the digit or letter.")
    if refused:
        lines.append("These glyphs could NOT be identified and were left as extracted; "
                     "the character you see there may be wrong:")
        for r in refused[:12]:
            lines.append(f"- font {r['font']}: {_fmt_char(r['extracted'])} "
                         f"({r['n']} glyphs; {r['why']})")
    if g.get("patterns"):
        lines.append("Corruption still visible in the text:")
        for h in g["patterns"]:
            ex = (h.get("examples") or [""])[0][:70]
            lines.append(f"- {h['pattern']} x{h['count']}"
                         + (" (affects DIGITS)" if h.get("corrupts_digits") else "")
                         + f": {h['means']}. e.g. `{ex}`")
    lines.append(
        "Treat every damaged character with suspicion: do NOT decode it yourself "
        "and compute on the guess. A finding whose number passes through such a "
        "character must say so in its evidence and be checked against the PDF by "
        "eye; it is a defect of the file's fonts, never of the paper's statistics.")
    return "\n".join(lines)
