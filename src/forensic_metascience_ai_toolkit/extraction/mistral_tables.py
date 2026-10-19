"""Tables from a Mistral OCR extraction, when one has been produced for a PDF.

WHY A SECOND PDF READER EXISTS. Docling is the pipeline's reader and stays that.
But 7.2% of the 305-paper cerebrolysin corpus carries font-encoding corruption
that touches a number -- a PDF that declares a glyph with no Unicode mapping,
which every text-layer extractor inherits and each spells differently. On the 22
papers where that damage was measured, reading the PAGE IMAGE instead recovers
what the text layer lost:

    body.md (pdf2mdjson)   1,064 statistics   988 corruption artefacts
    docling full-page OCR  1,208 statistics     0   but 47 hallucination
                                                    markers, in 27% of papers
    Mathpix                1,272 statistics     0   4 hallucination markers
    Mistral OCR            1,378 statistics     0   0 hallucination markers

So this module exists for the papers docling cannot read cleanly, not as a
replacement for it.

IT IS AN EXTRACTION AND SAYS SO. `xml_provenance` already draws this line for
XML -- publisher markup is the marked-up truth, a converter's output only ever
an extraction -- and the same rule applies here. Every table this module returns
is stamped `extractor: "mistral"`, and nothing about a paid API makes its
reading authoritative.

READS ONLY. There is no API call here and there must not be one: a cheap
enumeration that silently spends money and blocks for minutes is the defect
`docling_tables.extract_pdf_tables(allow_extract=False)` was written to prevent.
Producing the extraction is an explicit, out-of-band step; a cold cache is
REPORTED, never treated as a paper without tables.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .docling_tables import CACHE_DIRNAME, _digest
from .jats import _Counter, _expand, _header_depth
from .supplements_read import _finish

def cache_path(pdf: str | Path) -> Path:
    """Where a Mistral extraction of this PDF lives.

    Keyed on the file's CONTENT hash, beside it, exactly as the docling cache
    is -- so the two sit in one directory, a PDF edited in place invalidates
    both, and an extraction produced on another machine transfers.
    """
    p = Path(pdf)
    return p.parent / CACHE_DIRNAME / f"{p.stem}.{_digest(p)}.mistral.json"


def read_cache(pdf: str | Path) -> tuple[dict[str, Any] | None, str]:
    """`(payload, why_not)` -- the stored API response, or a reason there is none."""
    p = Path(pdf)
    if not p.is_file():
        return None, f"no such file: {p}"
    c = cache_path(p)
    if not c.is_file():
        return None, f"{p.name} has no Mistral extraction"
    try:
        return json.loads(c.read_text(encoding="utf-8")), ""
    except Exception as exc:  # noqa: BLE001
        # NOT silently re-read as absent. "We could not parse what we stored"
        # and "nothing was ever stored" send an operator to different places.
        return None, f"Mistral cache unreadable ({type(exc).__name__}: {exc})"


def _table_element(html: str) -> tuple[Any | None, str]:
    """`(element, why_not)` -- the `<table>` inside a fragment. lxml wraps loose markup.

    The reason travels because a fragment that HELD no table and a fragment we
    could not PARSE are different facts, and returning None for both files our
    failure as a property of the paper. `paper_text` had exactly this defect and
    four of its five callers published a clean result on a paper never opened.
    """
    import lxml.html

    try:
        el = lxml.html.fromstring(html)
    except Exception as exc:  # noqa: BLE001
        return None, f"could not be parsed as HTML ({type(exc).__name__}: {exc})"
    if el.tag == "table":
        return el, ""
    found = el.find(".//table")
    return (found, "") if found is not None else (None, "held no <table>")


def tables_from_response(payload: dict[str, Any],
                         problems: list[str] | None = None) -> list[dict]:
    """The response's tables, walked into the one cell shape every reader uses.

    Mistral returns each table as an HTML fragment with real `rowspan` and
    `colspan`, so it goes through `_rows_of`/`_expand` -- the SAME span walker
    the JATS and publisher-HTML readers use. A second span implementation here
    would be a second way to get a merged cell wrong, and merged cells are where
    a column silently becomes another column's.

    Header depth comes from `_header_depth`, because Mistral emits `<td>` with
    no `<thead>`: the `<th>` test every publisher-HTML table relies on returns
    nothing here, and the span structure is the only proof available. MEASURED
    over the 36 tables it found in those 22 papers: 20 have a two-row header,
    and reading them with one row collapses distinct columns on 15 of 36 (42%).
    """
    from .html import _rows_of

    problems = problems if problems is not None else []
    out: list[dict] = []
    n = 0
    for page in (payload.get("pages") or []):
        for table in (page.get("tables") or []):
            n += 1
            content = table.get("content") or ""
            if (table.get("format") or "").lower() != "html":
                # NAMED, not skipped quietly. A response that stopped being HTML
                # is a change in what we are reading, and a shorter list of
                # tables is not the way to find that out.
                problems.append(
                    f"table {table.get('id') or n} is "
                    f"{table.get('format') or 'an unstated format'}, not html; "
                    "it was not read")
                continue
            el, why = _table_element(content)
            if el is None:
                problems.append(f"table {table.get('id') or n} {why}; "
                                "it was not read")
                continue
            source_rows = _rows_of(el, _Counter())
            grid, _spans, warnings, _padded = _expand(source_rows)
            if not grid:
                problems.append(f"table {table.get('id') or n} resolved to zero "
                                "rows; it was not read")
                continue
            out.append(_finish(
                grid, n, f"Table {n}", "", "",
                f"page {page.get('index')}" if page.get("index") is not None else "",
                warnings=list(warnings),
                header_rows=_header_depth(source_rows, grid),
            ))
    return out


def pdf_tables(pdf: str | Path,
               problems: list[str] | None = None) -> list[dict] | None:
    """This PDF's tables from its Mistral extraction, or None if there is none.

    None and `[]` are DIFFERENT ANSWERS and the caller must be able to tell them
    apart: None is "no extraction exists, use another reader", `[]` is "the
    extraction exists and this paper prints no tables". Collapsing the two is
    how a paper with tables comes to be recorded as having none.
    """
    problems = problems if problems is not None else []
    payload, why = read_cache(pdf)
    if payload is None:
        if why and "has no Mistral extraction" not in why:
            problems.append(why)
        return None
    tables = tables_from_response(payload, problems)
    for t in tables:
        t["extractor"] = "mistral"
        t["extractor_model"] = payload.get("model") or "unknown"
    return tables
