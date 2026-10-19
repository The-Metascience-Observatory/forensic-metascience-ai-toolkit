"""Persisted anchors: WHERE each finding sits, written onto the finding.

Contract: docs/specs/anchors.md (approved 2026-08-21). Not `anchoring.py` —
that module records a finding's EVIDENTIARY BASIS; this one records its
locations. An anchor is a claim about a place: a box drawn on the wrong
number is a visual accusation against an innocent cell, so every tier here
may only degrade DOWN (`locators.py` doctrine: none is a successful answer;
never page 1).

The compute engine is `locators` (fold/locate/quote_boxes) and `quotes`
(`fold_with_offsets` for `char_range`). The one NEW mechanism is tier 2 of
the XML→PDF bridge, `word_align_boxes`: per-word folded alignment that may
emit boxes only at >= 90% of the quote's tokens matched AND >= 8 matched.
`annotate_findings` never raises — a paid analysis is never lost to a
highlighting step; failures are named on the record (`anchor_provenance.error`).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import locators
from .extraction.jats import find_pdf, find_xml
from .quotes import fold_with_offsets

_ALIGN_MIN_TOKENS = 8       # spec §4, normative
_ALIGN_MIN_FRAC = 0.9

_STATUS = {"bbox": "anchored", "exact": "anchored", "page": "page_only",
           "section": "section_only", "none": "unanchored"}
_STATUS_RANK = {"anchored": 0, "page_only": 1, "section_only": 2,
                "unanchored": 3}
_JUMPABLE = ("bbox", "exact")


def status_for(confidence: str | None) -> str:
    """Pure function of confidence (spec §3), persisted so nothing re-derives it."""
    return _STATUS.get(confidence or "none", "unanchored")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pipeline() -> str:
    try:
        from .version import pipeline_version
        return pipeline_version()
    except Exception:
        return "unknown"


def _folded_sha1(quote: str) -> str:
    return hashlib.sha1(locators.fold(quote).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Paper context: one PDF open, pages folded once, shared across findings
# ---------------------------------------------------------------------------

def _paper_ctx(paper_dir: Path, doc=None) -> dict:
    ctx: dict[str, Any] = {
        "paper_dir": paper_dir, "pdf": None, "pdf_rel": None,
        "doc": doc, "own_doc": False, "pymupdf": None, "pdf_error": None,
        "pages": [], "words": {}, "sections": [], "sections_kind": None,
        "sections_folded": None,
    }
    try:
        ctx["pdf"] = find_pdf(paper_dir)
    except Exception:
        ctx["pdf"] = None
    if ctx["pdf"] is not None:
        ctx["pdf_rel"] = ctx["pdf"].name
        try:
            import fitz
            ctx["pymupdf"] = getattr(fitz, "version", (None,))[0] \
                or getattr(fitz, "__version__", None)
            if ctx["doc"] is None:
                ctx["doc"] = fitz.open(ctx["pdf"])
                ctx["own_doc"] = True
        except Exception:
            ctx["doc"] = None
            ctx["pdf_error"] = "pymupdf_unavailable"
        if ctx["doc"] is not None:
            try:
                d = ctx["doc"]
                ctx["pages"] = [locators.fold(d[i].get_text())
                                for i in range(d.page_count)]
            except Exception as exc:
                ctx["pdf_error"] = f"page_read_failed: {exc}"
    xml = None
    try:
        xml = find_xml(paper_dir)
    except Exception:
        xml = None
    try:
        if xml is not None:
            from .extraction.jats import extract_xml_text_with_tables
            extracted = extract_xml_text_with_tables(xml, tables="full",
                                                     max_chars=2_000_000)
            ctx["sections_kind"] = "xml"
        else:
            from .extraction.html import (extract_html_text_with_tables,
                                          find_html)
            html_path = find_html(paper_dir)
            extracted = extract_html_text_with_tables(html_path) \
                if html_path is not None else {}
            ctx["sections_kind"] = "html" if html_path is not None else None
        ctx["sections"] = [p for p in (extracted.get("pages") or [])
                           if isinstance(p, dict)]
    except Exception:
        ctx["sections"] = []
    if not ctx["sections"]:
        ctx["sections_kind"] = None
    return ctx


def _folded_sections(ctx: dict) -> list[tuple[str, list[int]]]:
    if ctx["sections_folded"] is None:
        ctx["sections_folded"] = [
            fold_with_offsets(str(sec.get("text") or ""))
            for sec in ctx["sections"]]
    return ctx["sections_folded"]


def _page_words(ctx: dict, page_no: int) -> list[tuple[str, tuple]]:
    """Folded words with their rects for one 1-based page, cached."""
    if page_no not in ctx["words"]:
        try:
            raw = ctx["doc"][page_no - 1].get_text("words")
        except Exception:
            raw = []
        ctx["words"][page_no] = _fold_words(raw)
    return ctx["words"][page_no]


def _fold_words(raw_words: list) -> list[tuple[str, tuple]]:
    out: list[tuple[str, tuple]] = []
    for w in raw_words:
        rect = tuple(float(v) for v in w[:4])
        for part in locators.fold(str(w[4])).split():
            out.append((part, rect))
    return out


# ---------------------------------------------------------------------------
# Tier 2: word alignment
# ---------------------------------------------------------------------------

def _walk(words: list[tuple[str, tuple]], start: int,
          tokens: list[str]) -> tuple[int, list[tuple], int, int]:
    """Greedy contiguous walk from words[start]: (matched, rects, i_end, k_end).

    A token may consume TWO adjacent page words (line-break hyphenation:
    `co-` + `hort`, or a plain split); a mismatch is a substitution — one
    token against one word, counted unmatched — never a promotion.
    """
    matched, rects, i, k = 0, [], 0, start
    while i < len(tokens) and k < len(words):
        w, rect = words[k]
        t = tokens[i]
        if w == t:
            matched += 1
            rects.append(rect)
            i, k = i + 1, k + 1
            continue
        if k + 1 < len(words):
            w2, rect2 = words[k + 1]
            if w + w2 == t or (w.endswith("-") and w[:-1] + w2 == t):
                matched += 1
                rects.extend((rect, rect2))
                i, k = i + 1, k + 2
                continue
        i, k = i + 1, k + 1
    return matched, rects, i, k


def _best_walk(words: list[tuple[str, tuple]],
               tokens: list[str]) -> tuple[int, list[tuple], int, int]:
    best = (0, [], 0, 0)
    for start in range(len(words)):
        got = _walk(words, start, tokens)
        if got[0] > best[0]:
            best = got
    return best


def _meets(matched: int, n_tokens: int) -> bool:
    return (matched >= _ALIGN_MIN_TOKENS
            and n_tokens > 0 and matched / n_tokens >= _ALIGN_MIN_FRAC)


def word_align_boxes(page, folded_tokens: list[str]) -> list[dict]:
    """Tier 2 boxes for one fitz page, or [] (spec §4 thresholds are normative)."""
    words = _fold_words(page.get_text("words"))
    matched, rects, _, _ = _best_walk(words, folded_tokens)
    if not _meets(matched, len(folded_tokens)):
        return []
    return _rect_dicts(rects, page.number + 1)


def _rect_dicts(rects: list[tuple], page_no: int) -> list[dict]:
    return [{"x0": r[0], "y0": r[1], "x1": r[2], "y1": r[3], "page": page_no}
            for r in rects]


def _aligned_spans(ctx: dict, page_no: int,
                   tokens: list[str]) -> list[tuple[int, list[dict]]]:
    """[(page, boxes)] when alignment meets the thresholds, else [].

    A walk that reaches the page's last word with tokens left tries the
    remainder on the NEXT page — a quote split by a page break is one
    passage with two rectangles (spec §2), judged against one threshold.
    """
    words = _page_words(ctx, page_no)
    matched, rects, i_end, k_end = _best_walk(words, tokens)
    spans = [(page_no, _rect_dicts(rects, page_no))]
    total = matched
    if (k_end >= len(words) and i_end < len(tokens)
            and page_no < len(ctx["pages"])):
        m2, rects2, _, _ = _best_walk(_page_words(ctx, page_no + 1),
                                      tokens[i_end:])
        if m2 and rects2:
            spans.append((page_no + 1, _rect_dicts(rects2, page_no + 1)))
            total += m2
    if not _meets(total, len(tokens)):
        return []
    return [s for s in spans if s[1]]


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------

def _base(fid: str, passage_id: str, surface: str, kind: str, *,
          role=None, label: str = "", quote: str | None = None) -> dict:
    rec = {
        "anchor_id": f"{fid}:{passage_id}:{surface}",
        "passage_id": passage_id,
        "passage_key": f"{fid}:{passage_id}",
        "surface": surface,
        "kind": kind,
        "role": role,
        "label": label or "",
        "quote": quote,
    }
    if quote is not None:
        rec["quote_folded_sha1"] = _folded_sha1(quote)
    return rec


def _provenance(pipeline: str, *, pymupdf: str | None = None,
                error: str | None = None) -> dict:
    prov: dict[str, Any] = {"pipeline": pipeline, "at": _now()}
    if pymupdf:
        prov["pymupdf"] = pymupdf
    if error:
        prov["error"] = error
    return prov


def _finish_pdf(rec: dict, ctx: dict, pipeline: str, *, page: int | None,
                boxes: list[dict], confidence: str, method: str,
                error: str | None = None) -> dict:
    rec["file"] = ctx.get("pdf_rel")
    rec["page"] = page
    rec["boxes"] = boxes
    if boxes:
        rec["region"] = {
            "x0": min(b["x0"] for b in boxes),
            "y0": min(b["y0"] for b in boxes),
            "x1": max(b["x1"] for b in boxes),
            "y1": max(b["y1"] for b in boxes),
            "page": page,
        }
    doc = ctx.get("doc")
    if page and doc is not None:
        try:
            if page <= doc.page_count:
                r = doc[page - 1].rect
                rec["media_box"] = {"w": float(r.width), "h": float(r.height)}
        except Exception:
            pass
    rec["confidence"] = confidence
    rec["method"] = method
    rec["status"] = status_for(confidence)
    rec["anchor_provenance"] = _provenance(
        pipeline, pymupdf=ctx.get("pymupdf"), error=error)
    return rec


def _pdf_passage_records(fid: str, passage: dict, ctx: dict,
                         pipeline: str) -> list[dict]:
    """The four-tier bridge (spec §4) for one passage against the paper's PDF."""
    quote = passage["quote"]

    def base() -> dict:
        return _base(fid, passage["id"], "pdf", "pdf_text",
                     role=passage.get("role"), label=passage.get("label") or "",
                     quote=quote)

    if ctx.get("doc") is None:
        return [_finish_pdf(base(), ctx, pipeline, page=None, boxes=[],
                            confidence="none", method="unlocated",
                            error=ctx.get("pdf_error") or "pymupdf_unavailable")]
    tokens = locators.fold(quote).split()
    probe = " ".join(tokens[:8])
    probe_pages = [i + 1 for i, pg in enumerate(ctx["pages"])
                   if probe and probe in pg][:4]
    # Tier 1: full-quote verbatim boxes (the probe fallback would stamp
    # `exact` on the first eight words of a page-spanning quote).
    for page in probe_pages:
        boxes = locators.quote_boxes(ctx["pdf"], page, quote, doc=ctx["doc"],
                                     probe_fallback=False)
        if boxes:
            return [_finish_pdf(base(), ctx, pipeline, page=page, boxes=boxes,
                                confidence="exact", method="quote_verbatim")]
    loc3 = locators.locate(quote, ctx["pages"], "")
    tier3_page = loc3.get("page") if loc3.get("method") == "numeric_tokens" \
        else None
    # Tier 2, only on nominated pages (bounded work).
    for page in dict.fromkeys(probe_pages + ([tier3_page] if tier3_page else [])):
        spans = _aligned_spans(ctx, page, tokens)
        if spans:
            recs = []
            for k, (span_page, boxes) in enumerate(spans):
                rec = _finish_pdf(base(), ctx, pipeline, page=span_page,
                                  boxes=boxes, confidence="exact",
                                  method="quote_word_align")
                if k:  # spec §2: subsequent same-passage pdf anchors suffix
                    rec["anchor_id"] += f":p{span_page}"
                recs.append(rec)
            return recs
    # Tier 3 / probe-page degradation: a page, never a box.
    if probe_pages:
        return [_finish_pdf(base(), ctx, pipeline, page=probe_pages[0],
                            boxes=[], confidence="page",
                            method="quote_verbatim")]
    if tier3_page:
        return [_finish_pdf(base(), ctx, pipeline, page=tier3_page, boxes=[],
                            confidence="page", method="numeric_tokens")]
    # Tier 4: the written statement of absence. Never page 1.
    return [_finish_pdf(base(), ctx, pipeline, page=None, boxes=[],
                        confidence="none", method="unlocated")]


def _section_record(fid: str, passage: dict, ctx: dict, pipeline: str) -> dict:
    surface = ctx["sections_kind"]
    rec = _base(fid, passage["id"], surface, f"{surface}_text",
                role=passage.get("role"), label=passage.get("label") or "",
                quote=passage["quote"])
    fq, _ = fold_with_offsets(passage["quote"])
    needles = [fq]
    probe = " ".join(fq.split()[:8])
    if probe and probe != fq:
        needles.append(probe)
    for needle in needles:
        if not needle:
            continue
        for sec, (fs, imap) in zip(ctx["sections"], _folded_sections(ctx)):
            idx = fs.find(needle)
            if idx < 0:
                continue
            end_f = idx + len(needle)
            text = str(sec.get("text") or "")
            rec.update({
                "section_index": sec.get("page_num"),
                "section": sec.get("section") or sec.get("title"),
                "char_range": [imap[idx],
                               imap[end_f] if end_f < len(imap) else len(text)],
                "confidence": "exact",
                "method": "quote_verbatim",
                "status": "anchored",
                "anchor_provenance": _provenance(pipeline),
            })
            return rec
    loc = locators._locate_in_sections(passage["quote"], ctx["sections"])
    if loc:
        method = loc.get("method") or "numeric_tokens"
        # A verbatim hit inside a table grid is exact evidence, not a region.
        # It carries no `char_range`: the grid is deliberately absent from the
        # section text, so there is no offset into that text to give. The
        # table and row ARE the location.
        exact = method in locators._EXACT_XML_METHODS
        table_num = loc.get("table_num")
        rec.update({
            "section_index": loc.get("section_index"),
            "section": loc.get("section"),
            "confidence": "exact" if exact else "section",
            "method": method,
            "status": "anchored" if exact else "section_only",
            "anchor_provenance": _provenance(pipeline),
        })
        if table_num is not None:
            rec["table_num"] = table_num
            rec["row_index"] = loc.get("row_index")
            rec["label"] = rec.get("label") or f"Table {table_num}"
        return rec
    rec.update({
        "confidence": "none", "method": "unlocated", "status": "unanchored",
        "anchor_provenance": _provenance(pipeline),
    })
    return rec


def anchor_passage(fid: str, passage: dict, ctx: dict,
                   pipeline: str) -> list[dict]:
    """One quote passage → its records across every surface this paper has.

    A surface the paper does not have gets NO record; a surface searched
    without a hit gets an explicit unanchored one (spec §3).
    """
    records: list[dict] = []
    if ctx.get("pdf") is not None:
        records.extend(_pdf_passage_records(fid, passage, ctx, pipeline))
    if ctx.get("sections_kind"):
        records.append(_section_record(fid, passage, ctx, pipeline))
    return records


# ---------------------------------------------------------------------------
# Passage / placement / sheet extraction from a finding
# ---------------------------------------------------------------------------

def _passages_for(finding: dict) -> list[dict]:
    """Quote passages: prior anchors' quotes first (re-annotation recovers
    them), else the producer's `passages[]`/`quote` via the locators rules."""
    out: list[dict] = []
    seen: set[str] = set()
    for a in finding.get("anchors") or []:
        if not isinstance(a, dict):
            continue
        quote = str(a.get("quote") or "").strip()
        if not quote:
            continue
        pid = str(a.get("passage_id") or a.get("id") or chr(97 + len(out)))
        if pid in seen:
            continue
        seen.add(pid)
        out.append({"id": pid, "role": a.get("role"),
                    "label": str(a.get("label") or "").strip(), "quote": quote})
    return out or locators.candidates_for_issue(finding)


def _placements_for(finding: dict, ctx: dict) -> list[tuple[int, list[dict]]]:
    """Image placements as sorted (page, boxes) — the dict-vs-list
    polymorphism is normalized HERE, once (spec §5), not in three viewers."""
    extras = finding.get("extras") if isinstance(finding.get("extras"), dict) \
        else {}
    pl = finding.get("placements")
    if pl is None:
        pl = extras.get("placements")
    recs: list[dict] = []
    if isinstance(pl, dict):
        for uid_recs in pl.values():
            recs.extend(r for r in (uid_recs or []) if isinstance(r, dict))
    elif isinstance(pl, list):
        recs.extend(r for r in pl if isinstance(r, dict))
    panels = [str(u) for u in (finding.get("panels")
                               or extras.get("panels") or [])]
    if panels:
        panel_boxes = locators._panel_bboxes(ctx["paper_dir"])
        for uid in panels:
            recs.extend(panel_boxes.get(uid, []))
    by_page: dict[int, list[dict]] = {}
    for rec in recs:
        page = rec.get("page")
        if isinstance(page, bool) or not isinstance(page, (int, float)):
            continue
        page = int(page)
        if page < 1:
            continue
        boxes = by_page.setdefault(page, [])
        bbox = rec.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            box = {"x0": float(bbox[0]), "y0": float(bbox[1]),
                   "x1": float(bbox[2]), "y1": float(bbox[3]), "page": page}
            if box not in boxes:
                boxes.append(box)
    return sorted(by_page.items())


def _placement_record(fid: str, page: int, boxes: list[dict], ctx: dict,
                      pipeline: str) -> dict:
    rec = _base(fid, f"pg{page}", "pdf", "pdf_bbox")
    if ctx.get("doc") is None and ctx.get("pdf_error"):
        return _finish_pdf(rec, ctx, pipeline, page=None, boxes=[],
                           confidence="none", method="unlocated",
                           error=ctx["pdf_error"])
    return _finish_pdf(rec, ctx, pipeline, page=page, boxes=boxes,
                       confidence="bbox" if boxes else "page",
                       method="placement_bbox" if boxes else "placement_page")


def _sheet_records(fid: str, finding: dict, pipeline: str) -> list[dict]:
    out = []
    for i, st in enumerate(locators._sheet_targets(finding)):
        rec = _base(fid, f"sheet{i}", "sheet", "sheet_cell",
                    label=st.get("label") or "")
        rec.update({
            "file": st.get("file"),
            "sheet": st.get("sheet"),
            "cells": st.get("cells") or [],
            "confidence": "exact",
            "method": "tool_cells",
            "status": "anchored",
            "anchor_provenance": _provenance(pipeline),
        })
        out.append(rec)
    return out


# ---------------------------------------------------------------------------
# Table cells (the harness GRIM sweep's anchors, 1.82.0)
# ---------------------------------------------------------------------------

#: What a cell anchor carries, kept verbatim on every enriched record as
#: `cell` so a re-annotation can rebuild it: the enriched kinds replace the
#: producer's `table_cell` record (anchors are replaced wholesale).
CELL_FIELDS = ("table", "table_key", "table_num", "source", "row_label", "row",
               "col", "raw", "value", "page")


def _cells_for(finding: dict) -> list[dict]:
    """The table cells a finding names: producer `table_cell` anchors, or the
    `cell` kept on enriched `xml_cell` / `pdf_cell` records."""
    out: list[dict] = []
    seen: set[tuple] = set()
    for a in finding.get("anchors") or []:
        if not isinstance(a, dict):
            continue
        if a.get("kind") == "table_cell":
            cell = a
        elif a.get("kind") in ("xml_cell", "pdf_cell") and isinstance(a.get("cell"), dict):
            cell = a["cell"]
        else:
            continue
        try:
            key = (str(cell.get("table_key") or cell.get("table") or ""),
                   int(cell["row"]), int(cell["col"]))
        except (KeyError, TypeError, ValueError):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append({k: cell.get(k) for k in CELL_FIELDS if cell.get(k) is not None})
    return out


def _cell_id(cell: dict) -> str:
    table = "".join(ch if ch.isalnum() else "-"
                    for ch in str(cell.get("table_key") or cell.get("table") or "t"))
    return f"cell-{table}-r{cell['row']}c{cell['col']}"


def _row_cells(ctx: dict, cell: dict) -> list[dict] | None:
    """The cells of this cell's row, from the same walk the harness swept."""
    if "tables" not in ctx:
        try:
            from .prepass import paper_tables
            ctx["tables"] = paper_tables(ctx["paper_dir"], include_supplements=True)
        except Exception:  # noqa: BLE001
            ctx["tables"] = []
    key = str(cell.get("table_key") or "")
    if not (key.startswith("T") and key[1:].isdigit()):
        return None
    i = int(key[1:]) - 1
    if not 0 <= i < len(ctx["tables"]):
        return None
    return [c for c in ctx["tables"][i].get("cells") or []
            if c.get("row") == cell.get("row")]


def _label_tokens(label: Any) -> list[str]:
    last = str(label or "").split(" | ")[-1]
    if not last or last.startswith("(unlabelled"):
        return []
    return locators.fold(last).split()[:4]


def _cell_box_on_page(ctx: dict, page: int, cell: dict,
                      row_cells: list[dict]) -> list[dict] | None:
    """The cell's box on `page`, or None. NEVER A GUESSED BOX.

    The row is found by its label, which must occur exactly once on the page;
    the cell's printed text is then searched in that label's line band, right
    of the label, and taken only if it occurs there exactly as often as the
    table row prints it -- the k-th occurrence for the k-th equal cell."""
    label = _label_tokens(cell.get("row_label"))
    want = locators.fold(str(cell.get("raw") or "")).split()
    if not label or not want:
        return None
    words = _page_words(ctx, page)
    starts = [k for k in range(len(words) - len(label) + 1)
              if [w for w, _ in words[k:k + len(label)]] == label]
    if len(starts) != 1:
        return None
    first = words[starts[0]][1]
    last = words[starts[0] + len(label) - 1][1]
    height = max(1.0, first[3] - first[1])
    lo, hi = first[1] - 0.35 * height, first[3] + 0.35 * height
    band = [(w, r) for w, r in words
            if lo <= (r[1] + r[3]) / 2 <= hi and r[0] >= last[2] - 0.5]
    band.sort(key=lambda wr: wr[1][0])
    hits = [band[k:k + len(want)] for k in range(len(band) - len(want) + 1)
            if [w for w, _ in band[k:k + len(want)]] == want]
    same = [c for c in row_cells
            if locators.fold(str(c.get("raw") or "")).split() == want]
    same.sort(key=lambda c: int(c.get("col") or 0))
    if not hits or len(hits) != len(same):
        return None
    ordinal = next((k for k, c in enumerate(same)
                    if c.get("col") == cell.get("col")), None)
    if ordinal is None:
        return None
    return _rect_dicts([r for _, r in hits[ordinal]], page)


def _cell_pdf(ctx: dict, cell: dict) -> tuple[int | None, list[dict], str]:
    """`(page, boxes, method)` for a cell in the paper's main PDF."""
    if ctx.get("doc") is None or str(cell.get("source") or "article") != "article":
        return None, [], "unlocated"
    row_cells = _row_cells(ctx, cell)
    if row_cells is None:
        return None, [], "unlocated"
    page = cell.get("page") if isinstance(cell.get("page"), int) else None
    label = " ".join(_label_tokens(cell.get("row_label")))
    raw = locators.fold(str(cell.get("raw") or ""))
    candidates = [page] if page else [
        i + 1 for i, text in enumerate(ctx["pages"])
        if label and label in text and raw and raw in text]
    found = [(pg, boxes) for pg in candidates
             if (boxes := _cell_box_on_page(ctx, pg, cell, row_cells))]
    if len(found) == 1:
        return found[0][0], found[0][1], "cell_row_band"
    if page:
        return page, [], "cell_page"
    if len(candidates) == 1:
        return candidates[0], [], "cell_page"
    return None, [], "unlocated"


def _cell_records(fid: str, cell: dict, ctx: dict, pipeline: str) -> list[dict]:
    pid = _cell_id(cell)
    table = str(cell.get("table") or cell.get("table_key") or "")
    if table.startswith("cref"):
        # An older docling cache labels a table by its caption reference.
        table = f"table on p. {cell['page']}" if cell.get("page") else str(cell.get("table_key"))
    label = f"{table}, {cell.get('row_label') or 'row ' + str(cell['row'])}: {cell.get('raw')}"
    out: list[dict] = []
    if (ctx.get("sections_kind") == "xml" and cell.get("table_num") is not None
            and str(cell.get("source") or "article") == "article"):
        rec = _base(fid, pid, "xml", "xml_cell", role="said", label=label)
        rec.update({"table_num": cell["table_num"], "row": cell["row"],
                    "col": cell["col"], "raw": cell.get("raw"), "cell": cell,
                    "confidence": "exact", "method": "table_cell",
                    "status": "anchored",
                    "anchor_provenance": _provenance(pipeline)})
        out.append(rec)
    if ctx.get("pdf") is not None:
        page, boxes, method = _cell_pdf(ctx, cell)
        rec = _base(fid, pid, "pdf", "pdf_cell", role="said", label=label)
        rec.update({"row": cell["row"], "col": cell["col"],
                    "raw": cell.get("raw"), "cell": cell})
        out.append(_finish_pdf(rec, ctx, pipeline, page=page, boxes=boxes,
                               confidence=("exact" if boxes else
                                           "page" if page else "none"),
                               method=method))
    return out


# ---------------------------------------------------------------------------
# The annotator
# ---------------------------------------------------------------------------

def summarize(finding: dict) -> dict:
    """`anchor_summary` (spec §8): best status per surface, primary anchor."""
    recs = [a for a in finding.get("anchors") or [] if isinstance(a, dict)]
    out: dict[str, Any] = {}
    for a in recs:
        surface = a.get("surface")
        if not surface:
            continue
        status = a.get("status") or "unanchored"
        cur = out.get(surface)
        if cur is None or _STATUS_RANK.get(status, 3) < _STATUS_RANK.get(cur, 3):
            out[surface] = status
    primary = next((a for a in recs if a.get("confidence") in _JUMPABLE), None) \
        or next((a for a in recs
                 if a.get("confidence") not in (None, "none")), None)
    out["primary_anchor_id"] = primary.get("anchor_id") if primary else None
    out["page"] = primary.get("page") \
        if primary and primary.get("surface") == "pdf" else None
    return out


def _finding_id(finding: dict) -> str:
    return str(finding.get("finding_id") or finding.get("id") or "")


def _already_annotated(finding: dict, pipeline: str) -> bool:
    """Idempotence key (spec §6): every record enriched by THIS pipeline with
    an unchanged quote. True means skip, preserving `at`."""
    anchors = finding.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        return False
    for a in anchors:
        if not isinstance(a, dict) or not a.get("anchor_id"):
            return False
        prov = a.get("anchor_provenance")
        if not isinstance(prov, dict) or prov.get("pipeline") != pipeline:
            return False
        quote = a.get("quote")
        if quote is not None and a.get("quote_folded_sha1") != _folded_sha1(quote):
            return False
    return True


def _annotate_one(finding: dict, ctx: dict, pipeline: str) -> None:
    fid = _finding_id(finding)
    records: list[dict] = []
    for passage in _passages_for(finding):
        records.extend(anchor_passage(fid, passage, ctx, pipeline))
    if ctx.get("pdf") is not None:
        for page, boxes in _placements_for(finding, ctx):
            records.append(_placement_record(fid, page, boxes, ctx, pipeline))
    records.extend(_sheet_records(fid, finding, pipeline))
    for cell in _cells_for(finding):
        records.extend(_cell_records(fid, cell, ctx, pipeline))
    finding["anchors"] = records          # replaced wholesale, never appended
    finding["anchor_summary"] = summarize(finding)


def _annotate_degraded(finding: dict, ctx: dict, pipeline: str,
                       error: str) -> None:
    """The named-failure shape: unanchored records, never a silent absence."""
    fid = _finding_id(finding)
    records: list[dict] = []
    for passage in _passages_for(finding):
        if ctx.get("pdf") is not None:
            records.append(_finish_pdf(
                _base(fid, passage["id"], "pdf", "pdf_text",
                      role=passage.get("role"),
                      label=passage.get("label") or "",
                      quote=passage["quote"]),
                ctx, pipeline, page=None, boxes=[], confidence="none",
                method="unlocated", error=error))
        if ctx.get("sections_kind"):
            surface = ctx["sections_kind"]
            rec = _base(fid, passage["id"], surface, f"{surface}_text",
                        role=passage.get("role"),
                        label=passage.get("label") or "",
                        quote=passage["quote"])
            rec.update({"confidence": "none", "method": "unlocated",
                        "status": "unanchored",
                        "anchor_provenance": _provenance(pipeline, error=error)})
            records.append(rec)
    for cell in _cells_for(finding):
        # Kept, unanchored: the producer's cell must survive a failed pass.
        rec = _base(fid, _cell_id(cell), "xml", "xml_cell", role="said",
                    label=f"{cell.get('table')}: {cell.get('raw')}")
        rec.update({"cell": cell, "confidence": "none", "method": "unlocated",
                    "status": "unanchored",
                    "anchor_provenance": _provenance(pipeline, error=error)})
        records.append(rec)
    finding["anchors"] = records
    finding["anchor_summary"] = summarize(finding)


def annotate_findings(paper_dir: str | Path, findings: list,
                      doc=None, force: bool = False) -> list:
    """Enrich every finding's `anchors[]` in place (spec §6). Never raises.

    One PDF open and one page-fold pass serve all findings; `doc` is an
    already-open fitz document to reuse (not closed here). Idempotent —
    re-running over an annotated document is a byte-level no-op unless
    `force` — and re-annotation replaces `anchors[]` wholesale.
    """
    pipeline = _pipeline()
    try:
        ctx = _paper_ctx(Path(paper_dir), doc=doc)
    except Exception as exc:  # noqa: BLE001 — the never-raises contract
        ctx = {"paper_dir": Path(paper_dir), "pdf": None, "sections": [],
               "sections_kind": None, "doc": None, "own_doc": False,
               "pdf_error": f"context_failed: {exc}"}
    try:
        for finding in findings or []:
            if not isinstance(finding, dict):
                continue
            try:
                if not force and _already_annotated(finding, pipeline):
                    finding.setdefault("anchor_summary", summarize(finding))
                    continue
                _annotate_one(finding, ctx, pipeline)
            except Exception as exc:  # noqa: BLE001
                try:
                    _annotate_degraded(finding, ctx, pipeline,
                                       f"{type(exc).__name__}: {exc}")
                except Exception:
                    finding["anchor_summary"] = \
                        finding.get("anchor_summary") or {}
    finally:
        if ctx.get("own_doc") and ctx.get("doc") is not None:
            try:
                ctx["doc"].close()
            except Exception:
                pass
    return findings
