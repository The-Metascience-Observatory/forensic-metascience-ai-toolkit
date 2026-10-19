"""Which characters of a PDF's text layer were drawn from a SYMBOL font.

THE DEFECT THIS FINDS. A text extractor reports the Unicode a font's `ToUnicode`
map assigns to each glyph. Publisher symbol fonts ("Pi", "Ent", "Symbol" fonts)
routinely assign ASCII look-alikes: the glyph DRAWN is `µ`, the character
REPORTED is `m`. The text then reads perfectly -- `30 mg/kg` is a well-formed
dose -- and is wrong by a factor of a thousand. `glyphs.scan` cannot see this:
its patterns key on visibly corrupt output (`GLYPH<n>`, `(cid:n)`, `¼`), and
here nothing is visibly corrupt.

MEASURED on Stern et al. 2014 (Neuropsychopharmacology 39:2179), 2026-09-05,
via PyMuPDF `rawdict` spans:

    AdvPi1        'm' x17   every one is µ   (17 doses, volumes and masses)
    AdvEls-ent4   'o' x11   every one is <   (`*P o 0.05` in every legend)
    AdvEls-ent5   '1' x2    every one is °   (`45 1 or 90 1 angle`)
    AdvP4C4E74    '¼' x20   =  ; '\\x02' x11  x  ; '\\x03' x4  -
    AdvEls-Ent1   'm' x5    a syringe pictogram in the schedule legends
    AdvPi2        'b' x1    β   (GSK3β)

while the ketamine and xylazine doses (`100 mg/kg`, `75 mg/kg`) are drawn in the
body font and are genuinely milligrams. No text-level rule separates those two
populations; the FONT does, exactly.

WHAT THIS MODULE DOES AND DOES NOT DECIDE. It decides, from the PDF alone, WHICH
characters are suspect: any character drawn from a font whose name marks it as a
symbol/pi font, plus any character in a font that is a numeric look-alike. That
is a proven property of the file. It does NOT decide what the glyph is -- that
needs pixels (or a per-font table a human has verified against pixels). So the
audit renders the suspect lines to an image for a person to check, and a repair
is applied only from an explicit `glyph_map` -- `{font: {reported: intended}}`
-- that a human supplies after looking. Each applied repair is logged with the
font, the page and the verification route (`repairs.Repair`), so a value that
depends on one can be judged as such (Greg's repair-with-a-log policy,
2026-08-29).

WHY THE REPAIRS GO INTO THE DOCLING TEXT AND NOT PYMUPDF'S. The pipeline's
canonical text is docling's (`docling_tables.cached_text`); every offset the
scaffold records is into that string. Docling renders the same broken glyphs
differently again -- it writes `m g/kg` with an inserted space, `P o 0.05`, and
turns the `x` of `30.5 x 24.1` into `-`, which INVENTS a minus sign -- so the
repair locates each suspect by its PyMuPDF line context and rewrites the docling
span, restoring the original spacing from the PyMuPDF line. Length is not
preserved; the log carries offsets into the ORIGINAL docling text, which the
caller retains.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..repairs import Repair

#: Font-name fragments that mark a symbol or pi font. Case-insensitive.
#: `P4C4E` is the Advent "Pi 4" family; `Els-ent` the Elsevier entity fonts.
SYMBOL_FONT_MARKERS = ("pi", "symbol", "ent", "p4c4e", "ta42", "dingbat",
                       "wingding", "universal", "mathematical")

#: A body font is one that draws a large share of the document's characters.
#: Anything drawing less than this share AND matching a marker is a symbol font.
_BODY_SHARE = 0.02


def _is_symbol_font(name: str) -> bool:
    """Does this font name mark a symbol / pi / entity font?

    Vendor prefixes glue to the marker (`AdvPi1`, `AdvP4C4E74`, `AdvTA42`), so a
    leading `Adv` is stripped before matching. `pi` is a common substring of
    ordinary names (Capitals, Palatino), so it counts only when followed by a
    digit, a hyphen or the end of the name; `ent` only in the Elsevier
    `Els-ent4` / `Els-Ent1` shape.
    """
    low = re.sub(r"^adv", "", (name or "").lower())
    if re.match(r"^pi\d*(?:-|$)", low):
        return True
    for m in ("symbol", "p4c4e", "ta42", "dingbat", "wingding", "universal",
              "mathematical"):
        if m in low:
            return True
    if re.search(r"(?:^|-)ent\d", low):
        return True
    return False


def audit(pdf_path: str | Path) -> dict[str, Any]:
    """Font census plus every character drawn from a symbol font, with context.

    Returns `{fonts: [{font, n_chars, share, symbol_font}], suspects: [{page,
    font, char, codepoint, line, line_bbox, index_in_line}], n_suspects,
    n_pages, error}`. `error` is set, not raised, when the PDF cannot be opened
    -- and then `suspects` is empty because nothing was read, which the caller
    must not mistake for a clean file.
    """
    p = Path(pdf_path)
    out: dict[str, Any] = {"fonts": [], "suspects": [], "n_suspects": 0,
                           "n_pages": 0, "error": None, "source": p.name}
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - environment
        out["error"] = f"PyMuPDF not installed: {exc}"
        return out
    try:
        doc = fitz.open(str(p))
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        out["error"] = f"could not open {p.name}: {type(exc).__name__}: {exc}"
        return out
    counts: dict[str, int] = {}
    suspects: list[dict] = []
    total = 0
    with doc:
        out["n_pages"] = len(doc)
        for pno, page in enumerate(doc):
            d = page.get_text("rawdict")
            for block in d.get("blocks", []):
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    chars = [(s["font"], ch["c"]) for s in spans for ch in s["chars"]]
                    text = "".join(c for _, c in chars)
                    for font, c in chars:
                        counts[font] = counts.get(font, 0) + 1
                        total += 1
                    for i, (font, c) in enumerate(chars):
                        if not _is_symbol_font(font) or not c.strip():
                            continue
                        suspects.append({
                            "page": pno + 1, "font": font, "char": c,
                            "codepoint": f"U+{ord(c):04X}", "line": text,
                            "index_in_line": i,
                            "line_bbox": [round(x, 1) for x in line["bbox"]],
                        })
    for font, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        out["fonts"].append({"font": font, "n_chars": n,
                             "share": round(n / total, 4) if total else 0.0,
                             "symbol_font": _is_symbol_font(font)})
    out["suspects"] = suspects
    out["n_suspects"] = len(suspects)
    return out


def suspect_summary(audit_result: dict) -> list[dict]:
    """`[{font, char, codepoint, n, example}]` -- one row per (font, reported
    character), which is the unit a human verifies and a `glyph_map` names."""
    rows: dict[tuple[str, str], dict] = {}
    for s in audit_result.get("suspects", []):
        key = (s["font"], s["char"])
        r = rows.setdefault(key, {"font": s["font"], "char": s["char"],
                                  "codepoint": s["codepoint"], "n": 0,
                                  "example": s["line"].strip()[:100],
                                  "pages": []})
        r["n"] += 1
        if s["page"] not in r["pages"]:
            r["pages"].append(s["page"])
    return sorted(rows.values(), key=lambda r: (-r["n"], r["font"]))


def render_suspects(pdf_path: str | Path, audit_result: dict, out_png: str | Path,
                    zoom: float = 4.0, max_lines: int = 60) -> dict:
    """Render each suspect line to one stacked PNG so a person can read the glyphs.

    One line per distinct (page, line) -- a line with three suspects is drawn
    once. Returns `{path, n_lines, error}`; a render failure is reported.
    """
    p = Path(pdf_path)
    seen: set[tuple[int, tuple]] = set()
    lines: list[dict] = []
    for s in audit_result.get("suspects", []):
        key = (s["page"], tuple(s["line_bbox"]))
        if key in seen:
            continue
        seen.add(key)
        lines.append(s)
    lines = lines[:max_lines]
    result: dict[str, Any] = {"path": str(out_png), "n_lines": len(lines), "error": None}
    if not lines:
        return result
    try:
        import fitz
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - environment
        result["error"] = f"rendering needs PyMuPDF and Pillow: {exc}"
        return result
    try:
        doc = fitz.open(str(p))
        pixes = []
        with doc:
            for s in lines:
                x0, y0, x1, y1 = s["line_bbox"]
                rect = fitz.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
                pix = doc[s["page"] - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect)
                pixes.append((Image.frombytes("RGB", (pix.width, pix.height), pix.samples),
                              s["page"]))
        width = max(im.width for im, _ in pixes) + 60
        height = sum(im.height + 8 for im, _ in pixes)
        canvas = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(canvas)
        y = 0
        for im, page in pixes:
            canvas.paste(im, (60, y))
            draw.text((2, y + 8), f"p{page}", fill="red")
            y += im.height + 8
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        canvas.save(str(out_png))
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        result["error"] = f"render failed: {type(exc).__name__}: {exc}"
    return result


# --------------------------------------------------------------------------
# Applying a verified glyph map to the docling text
# --------------------------------------------------------------------------

_CTX = 10          # characters of PyMuPDF line context on each side
_MIN_CTX = 3       # a suspect at a line edge still needs this much on one side


def _flex(fragment: str) -> str:
    """A regex for `fragment` that tolerates how docling re-renders the same
    line: alphanumerics are literal; every other character (punctuation, a dash
    docling may have turned from `–` into `-`, another suspect glyph it may have
    turned into `-` or dropped) becomes "any one non-word character, or none";
    and optional whitespace is allowed between any two characters, because
    docling inserts a space on each side of a symbol-font glyph (`**Po0.05`
    becomes `**P o 0.05`). Ten characters of alphanumeric skeleton on each side
    keep the pattern specific."""
    parts = []
    for c in fragment:
        if c.isspace():
            continue
        parts.append(re.escape(c) if c.isalnum() else r"[^\w\s]?")
    return r"\s*".join(parts)


def apply_glyph_map(text: str, audit_result: dict, glyph_map: dict[str, dict[str, str]],
                    rule: str = "scaffold.fontaudit") -> dict[str, Any]:
    """Rewrite each suspect the map covers, in `text`, and log every edit.

    `glyph_map` is `{font_name: {reported_char: intended_string}}` -- supplied by
    a human who has looked at `render_suspects`' output, never inferred here.
    A suspect whose font or character the map does not cover is left alone and
    listed under `unmapped`; a mapped suspect whose context cannot be found in
    `text` is listed under `unlocated`. Both lists are the caller's to report.

    THE EDIT IS THE SLOT, NOT THE CONTEXT. Each suspect is located by ten
    characters of PyMuPDF line context on either side, but only the glyph's own
    slot -- the reported character plus whatever spacing docling put around it
    -- is rewritten, to the intended character with the spacing the PyMuPDF line
    carries. Adjacent suspects (`*Po0.05, **Po0.01`) therefore do not block each
    other, and the surrounding text is never touched.

    Returns `{text, repairs: [Repair], n_applied, unmapped: [...], unlocated:
    [...]}`. Offsets in the log are into the ORIGINAL `text`, computed against
    the unmodified string before any replacement is made, so they stay readable
    in order (see `repairs.Repair`).
    """
    original = text
    edits: list[tuple[int, int, str, Repair]] = []
    unmapped: list[dict] = []
    unlocated: list[dict] = []
    claimed: list[tuple[int, int]] = []

    for s in audit_result.get("suspects", []):
        font, ch = s["font"], s["char"]
        intended = (glyph_map.get(font) or {}).get(ch)
        if intended is None:
            unmapped.append({"font": font, "char": ch, "page": s["page"],
                             "line": s["line"].strip()[:100]})
            continue
        line, i = s["line"], s["index_in_line"]
        before = line[max(0, i - _CTX):i]
        after = line[i + 1:i + 1 + _CTX]
        if len(before.strip()) + len(after.strip()) < _MIN_CTX:
            unlocated.append({**s, "why": "not enough line context to locate"})
            continue
        slot = rf"(?P<slot>\s*(?:{re.escape(ch)}|[^\w\s])?\s*)"
        pattern = re.compile(_flex(before) + slot + _flex(after))
        hit = None
        for m in pattern.finditer(original):
            span = (m.start("slot"), m.end("slot"))
            if any(a < span[1] and span[0] < b for a, b in claimed):
                continue
            hit = m
            break
        if hit is None:
            unlocated.append({**s, "why": "context not found in the text (figure "
                                         "artwork text is not in the docling body)"})
            continue
        # The PyMuPDF line's own spacing around the glyph comes back with it:
        # `100 mg/kg` has a space before the glyph and none after.
        ws_before = "" if i == 0 or not line[i - 1].isspace() else " "
        ws_after = "" if i + 1 >= len(line) or not line[i + 1].isspace() else " "
        slot_start, slot_end = hit.start("slot"), hit.end("slot")
        replacement = ws_before + intended + ws_after
        # Do not double a space the context already carries on that side.
        if replacement.startswith(" ") and slot_start > 0 and original[slot_start - 1].isspace():
            replacement = replacement[1:]
        if replacement.endswith(" ") and slot_end < len(original) and original[slot_end].isspace():
            replacement = replacement[:-1]
        claimed.append((slot_start, slot_end))
        span_before = original[hit.start():hit.end()]
        span_after = (original[hit.start():slot_start] + replacement
                      + original[slot_end:hit.end()])
        edits.append((slot_start, slot_end, replacement, Repair(
            rule=rule,
            reason=(f"character reported as {ch!r} ({s['codepoint']}) is drawn from "
                    f"symbol font {font} on page {s['page']}; the glyph was verified "
                    f"as {intended!r} by rendering the line. Restores a character the "
                    "font's Unicode map destroyed; invents nothing."),
            before=span_before, after=span_after, offset=hit.start(), target="body",
            narrows_only=False)))

    edits.sort(key=lambda e: e[0])
    out_parts: list[str] = []
    cursor = 0
    for start, end, repl, _ in edits:
        out_parts.append(original[cursor:start])
        out_parts.append(repl)
        cursor = end
    out_parts.append(original[cursor:])
    return {"text": "".join(out_parts), "repairs": [e[3] for e in edits],
            "n_applied": len(edits), "unmapped": unmapped, "unlocated": unlocated}
