"""Where a reviewable issue sits in the paper.

Extracted from `bundle.py` so the workbench and the HTML bundle share one
locator. The bundle still re-exports these names; tests that import
`bundle._locate` keep working.

A locator is a CLAIM ABOUT A PLACE. A box drawn on the wrong number is a
visual accusation against an innocent cell, so confidence is gated:

  bbox     we have a recorded panel rectangle
  exact    the quote (or its first eight words) is in the PDF text layer
           and we have search boxes; or the quote is a contiguous span
           of a named XML section
  page     numeric-token scoring found a page, but no text boxes
  section  XML numeric-token hit only (no highlight)
  none     we do not know. Never page 1.

`none` is a successful answer, not a failed lookup.

An issue may have several *targets* (two sides of a contradiction, a
sheet's cells, the same quote in XML and in the PDF, each page of an
image match). The model writes verbatim quotes; this module locates
them. It never invents a page.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from .extraction.jats import find_pdf, find_xml

_WS = re.compile(r"\s+")
_NUMTOK = re.compile(r"\d+\.\d+|\b\d{2,}\b")
# Quoted fragments already in `reported` / `quote`. Do not treat the
# apostrophe in "patient's" as a delimiter.
_QUOTED = re.compile(
    r"“([^”]{20,})”"
    r'|"([^"]{20,})"'
    r"|(?<![A-Za-z0-9])'([^']{20,})'(?![A-Za-z])"
)

CONFIDENCES = ("bbox", "exact", "page", "section", "none")
_SHEET_KINDS = frozenset({"xlsx", "xls", "csv", "tsv"})
_JUMPABLE = frozenset({"exact", "bbox"})


def _norm(s: str) -> str:
    return _WS.sub(" ", s or "").strip().lower()


def fold(s: str) -> str:
    """Typography-insensitive form. XML-copied quotes must still hit a PDF."""
    try:
        from .quotes import fold_rendering, normalise
        return fold_rendering(normalise(s or ""))
    except Exception:
        return _norm(s)


def pdf_pages(pdf: Path | None) -> list[str]:
    if not pdf or not pdf.exists():
        return []
    try:
        import fitz
        with fitz.open(pdf) as doc:
            return [fold(doc[i].get_text()) for i in range(doc.page_count)]
    except Exception:
        return []


def locate(quote: str, pages: list[str], body_norm: str) -> dict:
    """Where in the paper is this quote? Returns {page, text_index, method}."""
    q = fold(quote)
    out: dict = {}
    if not q:
        return out

    probe = " ".join(q.split()[:8])
    if probe:
        for i, page in enumerate(pages):
            if probe in page:
                out["page"] = i + 1
                out["method"] = "quote_verbatim"
                break

    if "page" not in out:
        toks = set(_NUMTOK.findall(q))
        if len(toks) >= 2 and pages:
            scores = [sum(1 for tok in toks if tok in page) for page in pages]
            best = max(range(len(pages)), key=lambda i: scores[i])
            # Require a real majority of the tokens: a page sharing one number
            # with a quote is a coincidence, not a location.
            if scores[best] >= max(2, int(len(toks) * 0.6)):
                out["page"] = best + 1
                out["method"] = "numeric_tokens"

    hay_body = body_norm or ""
    if hay_body:
        idx = hay_body.find(probe) if probe else -1
        if idx < 0 and len(q) > 24:
            idx = hay_body.find(q[:40])
        if idx >= 0:
            out["text_index"] = idx
    return out


def _table_rows(sections: list[dict]):
    """Every table row in the document, folded, as (sec, table_num, row, text).

    Table text is NEVER inlined into a section's `text` -- that invariant is
    what stops a grid being poured into prose and re-transcribed with its
    columns lost. The grids live in `sec["tables"][i]["data"]` instead, which
    is why a quote naming a cell used to be unanchorable in XML while
    anchoring fine against the PDF's text layer. MEASURED over 92 papers /
    369 quotes: searching here recovers 54 of the 97 unanchored quotes.

    Rows are joined with a space, not a pipe: `fold` already folds cell edges
    away, so a model's `| Group | F (1.29) = 37.3 |` and the grid's own cells
    reduce to the same string.
    """
    for sec in sections:
        for tab in (sec.get("tables") or []):
            if not isinstance(tab, dict):
                continue
            for row_i, row in enumerate(tab.get("data") or []):
                if not isinstance(row, (list, tuple)):
                    continue
                text = fold(" ".join(str(c or "") for c in row))
                if text:
                    yield sec, tab.get("table_num"), row_i, text


def _locate_in_sections(quote: str, sections: list[dict]) -> dict:
    """XML has no pages. A section hit is a section, never a fabricated page.

    Four passes, strongest evidence first: verbatim in prose, verbatim in a
    table row, token overlap in prose, token overlap in a single table row.
    """
    q = fold(quote)
    if not q:
        return {}
    probe = " ".join(q.split()[:8])

    def _hit(sec, **extra):
        out = {
            "section": sec.get("section") or sec.get("title"),
            "section_index": sec.get("page_num"),
        }
        out.update(extra)
        return out

    for sec in sections:
        text = fold(str(sec.get("text") or ""))
        if probe and probe in text:
            return _hit(sec, method="quote_verbatim")

    if probe:
        for sec, table_num, row_i, text in _table_rows(sections):
            if probe in text:
                return _hit(sec, method="table_verbatim",
                            table_num=table_num, row_index=row_i)

    toks = set(_NUMTOK.findall(q))
    if len(toks) >= 2:
        best_i, best_n = None, 0
        for i, sec in enumerate(sections):
            text = fold(str(sec.get("text") or ""))
            n = sum(1 for tok in toks if tok in text)
            if n > best_n:
                best_i, best_n = i, n
        if best_i is not None and best_n >= max(2, int(len(toks) * 0.6)):
            sec = sections[best_i]
            return _hit(sec, method="numeric_tokens")

        # A grid collides far more readily than prose does -- near-duplicate
        # values are what tables ARE -- so a token hit only counts when it
        # lands on exactly ONE row. Two candidate rows is not a location.
        need = max(2, int(len(toks) * 0.6))
        rows = [
            (sec, table_num, row_i)
            for sec, table_num, row_i, text in _table_rows(sections)
            if sum(1 for tok in toks if tok in text) >= need
        ]
        if len(rows) == 1:
            sec, table_num, row_i = rows[0]
            return _hit(sec, method="table_numeric_tokens",
                        table_num=table_num, row_index=row_i)
    return {}


def anchor_findings(findings: list, pdf: Path | None, body_text: str) -> list:
    """Attach a page number and a text offset to each finding, where locatable."""
    pages = pdf_pages(pdf)
    body_norm = fold(body_text)
    out = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        g = dict(f)
        loc = locate(f.get("quote") or "", pages, body_norm)
        if loc:
            g["_anchor"] = loc
        out.append(g)
    return out


def quote_boxes(pdf: Path, page_no: int, quote: str, *, doc=None,
                probe_fallback: bool = True) -> list[dict]:
    """PDF-point rectangles for `quote` on one page, or empty.

    `search_for` is exact on the text layer. An empty list is not a failure:
    it means we will not draw a box. `probe_fallback=False` demands the FULL
    quote: the anchors bridge needs a probe-only hit to fall through to word
    alignment rather than stamp `exact` on a quote's first eight words.
    """
    q = " ".join((quote or "").split())
    if not q or page_no < 1:
        return []
    own = False
    try:
        import fitz
        if doc is None:
            if not pdf or not Path(pdf).exists():
                return []
            doc = fitz.open(pdf)
            own = True
        if page_no > doc.page_count:
            return []
        page = doc[page_no - 1]
        hits = page.search_for(q[:180])
        if not hits and probe_fallback:
            probe = " ".join(q.split()[:8])
            if probe and probe != q:
                hits = page.search_for(probe)
        return [
            {"x0": float(r.x0), "y0": float(r.y0),
             "x1": float(r.x1), "y1": float(r.y1),
             "page": page_no}
            for r in hits
        ]
    except Exception:
        return []
    finally:
        if own and doc is not None:
            try:
                doc.close()
            except Exception:
                pass


# Deprecated private aliases: `bundle.py` re-exports these and older tests
# import them. New code uses the public names above.
#
# PINNED by `tests/test_function_name_surface.py`. Every entry here is a second
# name for a function that already has one, which is the shape that makes a
# caller guess -- so the set is closed, and adding to it has to be deliberate.
# `_quote_boxes` was removed 2026-08-26 after a census found ZERO references to
# it anywhere in `src/` or `tests/`: a deprecated alias nobody deprecated FROM.
_fold = fold
_pdf_pages = pdf_pages
_locate = locate


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _panel_bboxes(paper_dir: Path) -> dict[str, list[dict]]:
    """uid -> [{page, bbox}] from the harvest, if one exists."""
    idx = _read_json(paper_dir / "panels" / "panel_index.json")
    if not isinstance(idx, dict):
        return {}
    out: dict[str, list[dict]] = {}
    for pan in idx.get("panels") or []:
        if not isinstance(pan, dict):
            continue
        uid = pan.get("uid") or pan.get("id") or pan.get("panel_id")
        if not uid:
            continue
        boxes = []
        for pl in pan.get("placements") or []:
            if not isinstance(pl, dict):
                continue
            bbox = pl.get("bbox")
            page = pl.get("page")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4 and page:
                boxes.append({"page": int(page),
                              "bbox": [float(x) for x in bbox]})
        if boxes:
            out[str(uid)] = boxes
    return out


def _empty(issue_id: str) -> dict:
    return {
        "issue_id": issue_id,
        "page": None,
        "section": None,
        "section_index": None,
        "boxes": [],
        "confidence": "none",
        "method": "unlocated",
        "targets": [],
    }


def quoted_fragments(text: str) -> list[str]:
    """Verbatim spans already marked with quotes in editorial prose.

    A fragment must be long enough that matching it is not a coincidence
    (≥8 words or ≥40 characters). Shorter quoted tokens ('QALY', 'p') are
    ignored.
    """
    out: list[str] = []
    seen: set[str] = set()
    for m in _QUOTED.finditer(text or ""):
        s = _WS.sub(" ", next(g for g in m.groups() if g)).strip()
        if len(s.split()) < 8 and len(s) < 40:
            continue
        key = fold(s)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _dedupe_candidates(cands: list[dict]) -> list[dict]:
    """One quote, one candidate, and no two candidates sharing an id.

    A target's id is `{cand_id}:xml` / `:pdf`, so two candidates with the same
    id mint two targets the viewer cannot tell apart -- `focusTargetId` then
    matches both, and a React key collides. MEASURED 2026-08-22 over the 92
    papers with a PDF, an XML and findings: 101 of 260 issues carried the same
    quote twice under the same id, 544 raw candidates against 369 distinct
    quotes, across 14 papers.

    Dedupe is on the FOLDED quote, so two renderings of one passage collapse;
    the surviving id is the first one, so any anchor already persisted against
    it stays valid.
    """
    out: list[dict] = []
    seen_quotes: set[str] = set()
    for cand in cands:
        key = fold(cand["quote"])
        if not key or key in seen_quotes:
            continue
        seen_quotes.add(key)
        out.append(cand)
    used: set[str] = set()
    for i, cand in enumerate(out):
        if cand["id"] in used:
            cand["id"] = f"{cand['id']}{i}"
        used.add(cand["id"])
    return out


def candidates_for_issue(issue: dict) -> list[dict]:
    """Quotes this issue asks us to locate. Never splits on 'vs' / prose."""
    passages = issue.get("passages")
    if isinstance(passages, list) and passages:
        out = []
        for i, p in enumerate(passages):
            if not isinstance(p, dict):
                continue
            q = str(p.get("quote") or "").strip()
            if not q:
                continue
            out.append({
                "id": str(p.get("id") or chr(97 + i)),
                "role": p.get("role"),
                "label": str(p.get("label") or "").strip(),
                "quote": q,
            })
        if out:
            return _dedupe_candidates(out)
    blob = " ".join(
        str(x) for x in (issue.get("reported"), issue.get("quote")) if x)
    frags = quoted_fragments(blob)
    if frags:
        return _dedupe_candidates([{
            "id": chr(97 + i),
            "label": "",
            "quote": f,
        } for i, f in enumerate(frags)])
    q = str(issue.get("quote") or "").strip()
    if q:
        return [{
            "id": "a",
            "label": str(issue.get("location") or "").strip(),
            "quote": q,
        }]
    return []


def _sheet_targets(issue: dict) -> list[dict]:
    out = []
    for i, art in enumerate(issue.get("artefacts") or []):
        if not isinstance(art, dict):
            continue
        if art.get("kind") not in _SHEET_KINDS or not art.get("found"):
            continue
        cells = art.get("cells") or []
        if not cells:
            continue
        out.append({
            "id": f"sheet-{i}",
            "passage_key": f"sheet-{i}",
            "kind": "sheet_cell",
            "label": art.get("sheet") or art.get("basename") or "sheet",
            "quote": None,
            "file": art.get("relpath") or art.get("basename"),
            "sheet": art.get("sheet"),
            "cells": cells,
            "page": None,
            "boxes": [],
            "section_index": None,
            "confidence": "exact",
            "method": "tool_cells",
        })
    return out


def _pdf_target(cand: dict, pages: list[str], body_norm: str,
                pdf: Path | None, doc, file_rel: str | None) -> dict:
    loc = locate(cand["quote"], pages, body_norm)
    page = loc.get("page")
    method = loc.get("method")
    boxes: list[dict] = []
    conf = "none"
    if page and method == "quote_verbatim" and pdf is not None:
        boxes = quote_boxes(pdf, int(page), cand["quote"], doc=doc)
        conf = "exact" if boxes else "page"
    elif page:
        conf = "page"
    t = {
        "id": f"{cand['id']}:pdf",
        "passage_key": cand["id"],
        "kind": "pdf_text",
        "label": cand.get("label") or "",
        "quote": cand["quote"],
        "file": file_rel,
        "page": int(page) if page else None,
        "boxes": boxes,
        "section_index": None,
        "confidence": conf,
        "method": method or "unlocated",
    }
    if "text_index" in loc:
        t["text_index"] = loc["text_index"]
    return t


#: Methods that place a quote on one contiguous span we can mark, as against
#: token overlap, which only narrows it to a region.
_EXACT_XML_METHODS = ("quote_verbatim", "table_verbatim")


def _xml_target(cand: dict, sections: list[dict]) -> dict:
    loc = _locate_in_sections(cand["quote"], sections)
    method = loc.get("method")
    exact = method in _EXACT_XML_METHODS
    table_num = loc.get("table_num")
    # A float's containing section is often literally named "Floats", which
    # tells a reviewer nothing. Name the table instead.
    label = (f"Table {table_num}" if table_num is not None
             else (cand.get("label") or loc.get("section") or ""))
    return {
        "id": f"{cand['id']}:xml",
        "passage_key": cand["id"],
        "kind": "xml_text",
        "label": label,
        "table_num": table_num,
        "row_index": loc.get("row_index"),
        "quote": cand["quote"],
        "file": None,
        "page": None,
        "boxes": [],
        "section": loc.get("section"),
        "section_index": loc.get("section_index"),
        "confidence": "exact" if exact else ("section" if loc else "none"),
        "method": method or "unlocated",
    }


def _apply_primary(out: dict, targets: list[dict]) -> dict:
    """Old single-place fields = first jumpable target, else first weak hit."""
    jump = next((t for t in targets if t.get("confidence") in _JUMPABLE), None)
    pick = jump or next((t for t in targets if t.get("confidence") not in
                         ("none", None) and t.get("confidence") != "none"), None)
    if not pick:
        return out
    out["confidence"] = pick["confidence"]
    out["method"] = pick.get("method") or out["method"]
    if pick.get("page"):
        out["page"] = pick["page"]
    if pick.get("boxes"):
        out["boxes"] = [b for t in targets
                        if t.get("kind") in ("pdf_text", "pdf_bbox")
                        for b in (t.get("boxes") or [])]
        if not out["boxes"]:
            out["boxes"] = pick["boxes"]
    if pick.get("section_index") is not None:
        out["section"] = pick.get("section")
        out["section_index"] = pick.get("section_index")
    if pick.get("file"):
        out["file"] = pick["file"]
    if pick.get("text_index") is not None:
        out["text_index"] = pick["text_index"]
    return out


def locate_issue(issue: dict, paper_dir: Path, *,
                 pdf: Path | None = None,
                 pages: list[str] | None = None,
                 sections: list[dict] | None = None,
                 body_norm: str = "",
                 panel_boxes: dict[str, list[dict]] | None = None,
                 doc=None,
                 pdf_rel: str | None = None) -> dict:
    """One locator for one workbench issue, with `targets` for each place."""
    iid = str(issue.get("id") or "")
    out = _empty(iid)

    if issue.get("kind") == "image":
        extras = issue.get("extras") or {}
        placements = extras.get("placements") or {}
        panel_boxes = panel_boxes or {}
        uids = [str(u) for u in (extras.get("panels") or [])]
        if isinstance(placements, dict):
            for uid in placements:
                if str(uid) not in uids:
                    uids.append(str(uid))
        recs: list[dict] = []
        seen_box: set[tuple] = set()
        seen_page: set[int] = set()

        def _page_int(raw) -> int | None:
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                return None
            page = int(raw)
            return page if page >= 1 else None

        def _add_box(page: int, bbox: list) -> None:
            key = (page, round(bbox[0], 2), round(bbox[1], 2),
                   round(bbox[2], 2), round(bbox[3], 2))
            if key in seen_box:
                return
            seen_box.add(key)
            recs.append({"page": page, "x0": bbox[0], "y0": bbox[1],
                         "x1": bbox[2], "y1": bbox[3]})

        def _add_placement(pl) -> None:
            if not isinstance(pl, dict):
                return
            page = _page_int(pl.get("page"))
            if page is None:
                return
            bbox = pl.get("bbox")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                _add_box(page, [float(x) for x in bbox])
            elif page not in seen_page:
                seen_page.add(page)
                recs.append({"page": page})

        for uid in uids:
            for rec in panel_boxes.get(uid, []):
                bbox = rec.get("bbox")
                page = _page_int(rec.get("page"))
                if isinstance(bbox, (list, tuple)) and len(bbox) == 4 and page:
                    _add_box(page, [float(x) for x in bbox])
            if isinstance(placements, dict):
                for pl in placements.get(uid) or []:
                    _add_placement(pl)
        if isinstance(placements, list):
            for pl in placements:
                _add_placement(pl)
        by_page: dict[int, list[dict]] = {}
        pages_only: list[int] = []
        for rec in recs:
            page = rec["page"]
            if "x0" in rec:
                by_page.setdefault(page, []).append(
                    {k: rec[k] for k in ("page", "x0", "y0", "x1", "y1")})
            else:
                pages_only.append(page)
        targets: list[dict] = []
        for page in sorted(by_page):
            pb = by_page[page]
            tid = f"{iid}:page:{page}"
            for b in pb:
                b["tid"] = tid
            targets.append({
                "id": tid,
                # One passage per placement PAGE (docs/specs/anchors.md §2):
                # the two placements of a duplicated panel must stay two
                # comparison groups, not collapse into one.
                "passage_key": f"{iid}:pg{page}",
                "kind": "pdf_bbox",
                "label": f"p. {page}",
                "page": page,
                "boxes": pb,
                "confidence": "bbox",
                "method": "placement_bbox",
            })
        for page in sorted(set(pages_only) - set(by_page)):
            targets.append({
                "id": f"{iid}:page:{page}",
                "passage_key": f"{iid}:pg{page}",
                "kind": "pdf_bbox",
                "label": f"p. {page}",
                "page": page,
                "boxes": [],
                "confidence": "page",
                "method": "placement_page",
            })
        out["targets"] = targets
        if targets:
            return _apply_primary(out, targets)
        return out

    targets: list[dict] = []
    cands = candidates_for_issue(issue)
    for cand in cands:
        if pdf is not None and pages is not None:
            targets.append(_pdf_target(
                cand, pages, body_norm, pdf, doc, pdf_rel))
        if sections:
            xt = _xml_target(cand, sections)
            if xt["confidence"] != "none":
                targets.append(xt)
    targets.extend(_sheet_targets(issue))
    out["targets"] = targets
    return _apply_primary(out, targets)


#: Persisted-anchor -> Target field copy (docs/specs/anchors.md §9).
_ANCHOR_TARGET_KEYS = ("passage_key", "quote", "file", "page", "boxes",
                       "section", "section_index", "sheet", "cells",
                       "confidence", "method",
                       # table cells (`xml_cell` / `pdf_cell`, 1.83.0)
                       "table_num", "row_index", "row", "col", "raw")


def _targets_from_anchors(anchors: Any) -> list[dict] | None:
    """Pure anchor→target translation, or None when records are not enriched.

    Minimal producer anchors (no `anchor_id`) mean the annotator has not run:
    fall through to compute. Enriched records translate with no PDF open.
    """
    if not isinstance(anchors, list) or not anchors:
        return None
    out = []
    for a in anchors:
        if not isinstance(a, dict) or not a.get("anchor_id") or not a.get("kind"):
            return None
        t = {"id": a["anchor_id"], "kind": a["kind"],
             "label": a.get("label") or ""}
        for key in _ANCHOR_TARGET_KEYS:
            if a.get(key) is not None:
                t[key] = a[key]
        t.setdefault("boxes", [])
        t.setdefault("confidence", "none")
        t.setdefault("method", "unlocated")
        out.append(t)
    return out


def persisted_locators(issues: list[dict] | None) -> dict:
    """Locators from ENRICHED anchors only, with no file opened.

    For a sealed run, whose source files may since have changed: persisted
    anchors describe the file the run read, so they still hold, while
    computing afresh would locate against a different file. An issue without
    enriched anchors gets no locator, never a computed one."""
    out = []
    for iss in issues or []:
        if not isinstance(iss, dict):
            continue
        translated = _targets_from_anchors(iss.get("anchors"))
        if translated is None:
            continue
        loc = _apply_primary({**_empty(str(iss.get("id") or "")),
                              "targets": translated}, translated)
        loc["located_by"] = "persisted_anchors"
        out.append(loc)
    return {"locators": out}


def locators_for_paper(paper_dir: Path, issues: list[dict] | None = None) -> dict:
    """Every issue's locator, plus how the paper can be shown.

    When `issues` is omitted the caller is expected to have collected them;
    an empty list is a paper with nothing to locate, not a failed lookup.

    Persisted-first: an issue whose `anchors` are already enriched is
    translated purely (`located_by: "persisted_anchors"`); the compute
    context — including the PyMuPDF open — is built only when some issue
    needs the legacy path (`located_by: "computed"`).
    """
    paper_dir = Path(paper_dir)
    pdf = find_pdf(paper_dir)
    xml = find_xml(paper_dir)
    ctx: dict = {}

    def _ctx() -> dict:
        if ctx:
            return ctx
        ctx["pages"] = pdf_pages(pdf) if pdf else []
        sections: list[dict] = []
        body_norm = ""
        if xml is not None:
            try:
                from .extraction.jats import extract_xml_text_with_tables
                extracted = extract_xml_text_with_tables(xml, tables="full",
                                                         max_chars=2_000_000)
                sections = [p for p in (extracted.get("pages") or [])
                            if isinstance(p, dict)]
                if not body_norm:
                    body_norm = fold(extracted.get("text") or "")
            except Exception:
                sections = []
        if ctx["pages"]:
            body_norm = " ".join(ctx["pages"])
        ctx["sections"] = sections
        ctx["body_norm"] = body_norm
        ctx["panel_boxes"] = _panel_bboxes(paper_dir)
        ctx["doc"] = None
        if pdf is not None:
            try:
                import fitz
                ctx["doc"] = fitz.open(pdf)
            except Exception:
                ctx["doc"] = None
        return ctx

    locators = []
    try:
        for iss in (issues or []):
            if not isinstance(iss, dict):
                continue
            translated = _targets_from_anchors(iss.get("anchors"))
            if translated is not None:
                loc = _empty(str(iss.get("id") or ""))
                loc["targets"] = translated
                loc = _apply_primary(loc, translated)
                loc["located_by"] = "persisted_anchors"
                locators.append(loc)
                continue
            c = _ctx()
            issue_pdf, issue_pages = _pdf_for_issue(iss, paper_dir, pdf,
                                                    c["pages"])
            issue_doc = c["doc"]
            pdf_rel = None
            if issue_pdf is not None and issue_pdf != pdf:
                try:
                    pdf_rel = issue_pdf.relative_to(paper_dir).as_posix()
                except ValueError:
                    pdf_rel = issue_pdf.name
                issue_doc = None
            loc = locate_issue(
                iss, paper_dir,
                pdf=issue_pdf,
                pages=(issue_pages if issue_pdf is not None else None),
                sections=c["sections"] or None,
                body_norm=c["body_norm"] if issue_pdf is pdf else (
                    " ".join(issue_pages) if issue_pages else ""),
                panel_boxes=c["panel_boxes"],
                doc=issue_doc,
                pdf_rel=pdf_rel,
            )
            if pdf_rel:
                loc["file"] = pdf_rel
            loc["located_by"] = "computed"
            locators.append(loc)
    finally:
        if ctx.get("doc") is not None:
            try:
                ctx["doc"].close()
            except Exception:
                pass
    return {
        "paper_dir": str(paper_dir),
        "has_pdf": bool(pdf),
        "has_xml": bool(xml),
        "pdf_relpath": pdf.name if pdf else None,
        "xml_relpath": xml.name if xml else None,
        "locators": locators,
    }


def _pdf_for_issue(issue: dict, paper_dir: Path,
                   default_pdf: Path | None,
                   default_pages: list[str]) -> tuple[Optional[Path], list[str]]:
    """A finding about an SI PDF is located in that file, not the article."""
    for art in issue.get("artefacts") or []:
        if not isinstance(art, dict):
            continue
        if art.get("kind") != "pdf" or not art.get("found"):
            continue
        rel = str(art.get("relpath") or art.get("basename") or "")
        if not rel:
            continue
        if default_pdf is not None and Path(rel).name == default_pdf.name:
            continue
        try:
            from .finding_files import resolve
            found, _ = resolve(paper_dir, art)
        except Exception:
            found = None
        if found is not None and found.suffix.lower() == ".pdf":
            return found, pdf_pages(found)
    return default_pdf, default_pages
