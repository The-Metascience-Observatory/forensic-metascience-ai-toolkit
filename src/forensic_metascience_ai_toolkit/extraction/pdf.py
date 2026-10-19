"""PDF text and table extraction utilities."""

import re
import warnings
from pathlib import Path
from typing import Any


#: A line on at least this fraction of pages is page furniture, not content.
#: Deliberately high: the cost of calling a real line furniture is that it is
#: dropped from a measurement used only to decide readability, while the cost
#: of missing a stamp is a paper reported as readable that nobody read.
_FURNITURE_PAGE_FRACTION = 0.6

#: On a ONE-PAGE document furniture cannot be identified at all, because a
#: stamp is only recognisable by repeating. So the single-page case falls back
#: to raw length, and needs a cutpoint where the multi-page rule needs none.
#:
#: This is the least-supported number here and is flagged as such: no corpus
#: available contains a genuine one-page scan, so the positive case is
#: constructed rather than observed. It is calibrated from the two ends that
#: ARE measured -- a one-page scan carrying only a 124-character JSTOR stamp,
#: and the sparsest genuinely readable single-page document in the three
#: corpora at 571 characters. 150 sits between them with 3.8x headroom below
#: the readable end.
_MIN_SINGLE_PAGE_CHARS = 150

#: What `extract_text_with_tables` appends when it hits `max_chars`. NAMED, not
#: written inline, because a consumer that serves this text onward -- a
#: supplement's running prose, say -- has to be able to take it off again: it is
#: an instruction to a tool caller, and inside a paper's served text it is a
#: sentence the paper never printed, sitting in the numeral floor's own haystack.
TRUNCATION_MARKER = ("\n\n[TEXT TRUNCATED -- call extract_pdf again with first_page/"
                     "last_page to fetch the remaining pages]")


def readable_body_chars(page_texts: list[str]) -> int:
    """How many characters of the DOCUMENT came back, ignoring page furniture.

    THE QUESTION IS NOT WHETHER TEXT CAME BACK. A scanned paper often has a
    text layer holding the publisher's stamp and nothing else, so `len(text)`
    is non-zero and every emptiness test downstream passes. MEASURED on three
    papers drawn from a 300-PDF sweep of a real reference library, every single
    character extracted was furniture of that shape:

      Scheff & Price 1998   918 chars = an OUP download stamp x 8 pages
      Small 2006            950 chars = "Reproduced with permission of the
                                         copyright owner" x 8 pages
      Scheving 1968          98 chars = "(c) 1968 Nature Publishing Group" x 2

    A stamp is identical on every page; a paper's body is not. So the measure
    is what SURVIVES removing lines that repeat across the document, and the
    threshold is ZERO rather than a density cutoff -- a rule that fires only
    when literally nothing but furniture came back cannot reject a short
    letter, a two-page comment, or a paper in any language, which a
    chars-per-page rule does. Digits are normalised so a running page number or
    a per-page date collapses with its siblings instead of surviving as
    content.

    ZERO IS NOT A CONSERVATIVE GUESS, IT IS WHERE THE DATA IS. Measured over
    291 PDFs from `high_value_pdfs_to_run_on`, `eval/ground_truth` and the
    stress sample, all ten known scans come back at EXACTLY 0.0 body
    characters per page and the sparsest genuinely readable document sits at
    163.7 -- so every threshold between 0.001 and 163 scores identically. Given
    that, zero is the better of the equivalent choices: it is the only one with
    no cutpoint to tune, to justify, or to drift.

    (Raw chars-per-page, by contrast, separates those same two groups by only
    1.33x -- 124 against 165.5 -- which is why the furniture subtraction is
    doing the work and not the arithmetic around it.)
    """
    pages = [t for t in page_texts]
    if not pages:
        return 0
    if len(pages) == 1:
        # Nothing to compare against, so no line can be shown to be furniture.
        # Fall back to raw length; see `_MIN_SINGLE_PAGE_CHARS`.
        only = pages[0].strip()
        return len(only) if len(only) >= _MIN_SINGLE_PAGE_CHARS else 0

    def _norm(line: str) -> str:
        return re.sub(r"\d+", "#", line.strip().lower())

    seen: dict[str, int] = {}
    for text in pages:
        for line in {_norm(l) for l in text.splitlines() if l.strip()}:
            seen[line] = seen.get(line, 0) + 1

    threshold = max(2, int(_FURNITURE_PAGE_FRACTION * len(pages)))
    furniture = {line for line, n in seen.items() if n >= threshold}

    return sum(
        len(line.strip())
        for text in pages
        for line in text.splitlines()
        if line.strip() and _norm(line) not in furniture
    )


def extract_text(pdf_path: str | Path) -> str:
    """
    Extract all text from a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Concatenated text from all pages
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # THE SAME UPGRADE `extract_text_with_tables` GOT, and it has to be here
    # too. `paper_text()` -- which feeds the quote verifier and the computation
    # audit's haystack -- calls THIS function, not that one, so upgrading only
    # the other left the two disagreeing: 38,879 characters of docling text
    # from one entry point and 36,016 of pdfplumber from the other, on the same
    # paper, in the same run. Two readers of one document is how a quote
    # verifies against text the checker never saw.
    from . import docling_tables as _dl
    _cached, _why = _dl.cached_text(pdf_path)
    if _cached:
        return _cached
    # No swallowed exception here. `cached_text` already returns a REASON
    # rather than raising -- "not extracted yet", "cache unreadable", "stored
    # by an older version" -- and wrapping it in a bare `except: pass` would
    # discard exactly the diagnosis it exists to provide.
    #
    # ON A CACHE MISS WE EXTRACT WITH DOCLING, AND NEVER WITH PDFPLUMBER.
    #
    # GREG, 2026-08-16: "I never want to use pdfplumber again"; "it should never
    # run *anywhere* -- you determined it was inferior to docling in every
    # respect." The measurements are this project's own, in pyproject: table
    # recall 60.4% -> 95.8%, and pdfplumber renders operators as glyph
    # references, so `t(28) = -3.33` arrives with its `=` and minus sign
    # replaced by `(cid:N)` debris. It also interleaves two-column layouts into
    # single lines, fusing adjacent columns into sentences neither contains.
    #
    # The fallback was not harmless: it made TWO READERS OF ONE DOCUMENT
    # possible -- the model reading docling text while a verifier searched
    # pdfplumber text -- which is how a quote fails to verify against a
    # sentence plainly present in the paper.
    #
    # A live extraction here can be slow, which is exactly why `cached_text`
    # refuses to run the model itself. Running it is still the right trade: the
    # alternative is not "fast", it is "wrong text, silently". On failure we
    # return "" WITH a warning naming the reason, and every consumer already
    # treats "" as UNKNOWN rather than as "this paper says nothing".
    # AND THIS DOES NOT RUN THE MODEL EITHER. The first version of this line
    # did, and it was the wrong place twice over: `paper_text()` calls this
    # function, and `paper_text()` is called by the supplement gate, the quote
    # haystack and the glyph scan, on every paper, throughout the suite. Live
    # extraction here took the suite from 5 minutes to over 30 with every
    # worker pinned, which is the regression `extract_pdf_tables` warns about
    # in its own docstring: enumeration is not the place for extraction.
    #
    # `cached_text` above already returned a REASON. Pass it on rather than
    # guessing, and name the command that fixes it.
    if "has not been extracted" in (_why or ""):
        _why = (f"{pdf_path.name} has not been extracted; run "
                "`metascience extract-tables` on the paper")

    warnings.warn(
        f"no text extracted from {pdf_path.name}: {_why}. Returning empty text; "
        "callers must treat this as UNKNOWN, not as an absence of content.",
        stacklevel=2,
    )
    return ""


def extract_tables(pdf_path: str | Path) -> list[dict[str, Any]]:
    """Tables from a PDF, via docling.

    Kept as a thin wrapper over `extract_text_with_tables` so there is ONE
    extraction path rather than two that can disagree. The previous
    implementation opened the PDF a second time with pdfplumber and ran its own
    ruled/text-alignment passes, which is how a caller could be told a paper has
    no tables by one function and four by another.
    """
    return list(extract_text_with_tables(pdf_path).get("tables") or [])


def extract_text_with_tables(
    pdf_path: str | Path,
    max_chars: int = 50000,
    first_page: int | None = None,
    last_page: int | None = None,
) -> dict[str, Any]:
    """
    Extract both text and tables from a PDF, preserving structure.

    DOCLING ONLY. GREG, 2026-08-16: pdfplumber "should never run *anywhere* --
    you determined it was inferior to docling in every respect." This function
    was the last substantial holdout, and it held out for one reason: it served
    a `pages[]` breakdown with page-range slicing that the docling cache did
    not carry. The cache carries it now (schema 4), so the reason is gone.

    WHAT WENT WITH IT. `page_is_sideways` and `_uprighted` -- detect a
    landscape page, rebuild the PDF with it rotated upright, re-read it, and
    stamp the result `grid_unreliable` -- existed solely because pdfplumber
    cannot read rotated text. Docling can. MEASURED on `10.1002--eat.24415`,
    the paper that motivated that code: pdfplumber calls pages 20-24 of 24
    sideways; against docling's text, 12/12 distinctive words from each of
    those five pages are present, full verbatim lines survive at 12/15 and
    13/16 on the two table-heavy pages, and the Table 1 grid docling returns is
    itself from page 20. So the machinery is deleted rather than ported, and
    no rotate-the-PDF preprocessing step replaces it.

    Args:
        pdf_path: Path to the PDF file
        max_chars: Cap on total returned text (applied to the combined text
            AND to the per-page `pages[].text` entries, so the serialized
            payload stays bounded)
        first_page: 1-based first page to extract (inclusive); None = start
        last_page: 1-based last page to extract (inclusive); None = end

    Returns:
        Dictionary with 'text', 'tables', and 'pages' keys
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    from . import docling_tables as _dl

    # Cache first, then a live run. `cached_text` deliberately never runs the
    # model, so the live call is made here where the caller has asked for a
    # full extraction rather than a cheap text peek.
    doc: dict[str, Any] = {}
    why = ""
    try:
        # CACHE ONLY. EXTRACTION IS AN EXPLICIT STEP, and this function is not
        # it -- the rule `extract_pdf_tables` states in its own docstring, and
        # the one I broke twice measuring the consequences.
        #
        #   attempt 1: invalidated every pre-schema-4 cache entry, so each
        #              cheap read paid for a field it does not use. Suite
        #              5 min -> 27 min.
        #   attempt 2: scoped the re-extraction to this function. Still wrong:
        #              the cache is written BESIDE the PDF, so any caller
        #              handing over a copy in a temp directory misses every
        #              time and re-extracts every time. Suite -> 2h 10m, and an
        #              xdist worker collapsed outright.
        #
        # So: read the cache, and when it is absent SAY SO with the command
        # that fills it. A refusal a reader can act on beats a function that
        # silently blocks for minutes -- and beats pdfplumber, which is the
        # only other way to answer and is not an option any more.
        doc = _dl.extract_pdf_tables(pdf_path, allow_extract=False) or {}
        why = str(doc.get("error") or "")
        if doc and not doc.get("pages") and not why:
            why = (f"{pdf_path.name} was extracted by an older version that "
                   "stored no per-page text; run `metascience extract-tables "
                   "--force` on it")
    except Exception as exc:  # noqa: BLE001
        why = f"{type(exc).__name__}: {exc}"

    dl_pages = list(doc.get("pages") or [])
    total_pages = int(doc.get("num_pages") or len(dl_pages))

    # A ZERO-PAGE DOCUMENT IS A FILE WE COULD NOT READ, NOT A PAPER WITH
    # NOTHING IN IT. Every field of the old empty return was a positive
    # assertion and none of them was true; `truncated: False` in particular
    # answered "is anything missing?" with no while the whole document was.
    if total_pages == 0:
        return {
            "text": "",
            "text_extractor": "docling",
            "text_extractor_note": why or "docling returned no pages",
            "tables": [],
            "pages": [],
            "num_pages": 0,
            "pages_extracted": [],
            "truncated": False,
            "unreadable": True,
            "error": (
                f"{pdf_path.name} could not be read: docling returned no pages"
                + (f" ({why})" if why else "")
                + ". NOTHING was read, so the paper's contents are UNKNOWN -- "
                "an empty `tables` list and a check that finds no statistics "
                "are facts about this extraction, NOT about the paper."
            ),
        }

    lo = max(1, first_page or 1)
    hi = min(total_pages, last_page or total_pages)
    if lo > hi:
        lo, hi = 1, total_pages

    pages: list[dict[str, Any]] = []
    for entry in dl_pages:
        n = int(entry.get("page_num") or 0)
        if not (lo <= n <= hi):
            continue
        pages.append({"page_num": n, "text": entry.get("text") or "", "tables": []})
    by_page = {p["page_num"]: p for p in pages}

    all_tables: list[dict[str, Any]] = []
    for t in (doc.get("tables") or []):
        page_no = t.get("page")
        grid = t.get("data") or []
        if not grid:
            continue
        if page_no is not None and not (lo <= int(page_no) <= hi):
            continue
        table_data = {
            "table_num": t.get("table_num"),
            "data": grid,
            # Docling reads the ruled structure rather than inferring columns
            # from text alignment, which is why the alignment-heuristic
            # rejection counters this function used to publish are gone.
            "strategy": "docling",
        }
        if t.get("label"):
            table_data["label"] = t["label"]
        target = by_page.get(int(page_no)) if page_no is not None else None
        if target is not None:
            target["tables"].append(table_data)
        all_tables.append({"page": page_no, **table_data})

    # The full document's text when the caller wanted all of it; the joined
    # page slice when they asked for a range.
    if lo == 1 and hi == total_pages and (doc.get("text") or "").strip():
        full_text = doc["text"]
    else:
        full_text = "\n\n".join(
            f"--- Page {p['page_num']} ---\n{p['text']}" for p in pages)

    # Measured BEFORE truncation, or a long document opening with a stamped
    # cover page would be judged on the part we kept. A scanned paper opens
    # cleanly and reports its true page count, so page count alone can never
    # detect one -- what detects it is that every character extracted is
    # furniture.
    body_chars = readable_body_chars([p["text"] for p in pages])
    no_readable_body = bool(pages) and body_chars == 0

    # HOW MUCH THERE WAS, BESIDE HOW MUCH CAME BACK. `truncated: True` says
    # something is missing and never how much, so a caller serving this text
    # onward could report neither. MEASURED on jamanetworkopen.2023.51752: its
    # first supplement is 289,222 characters and 50,000 were served, and the
    # only trace was a marker sentence inside the text.
    n_chars_available = len(full_text)
    truncated = False
    if len(full_text) > max_chars:
        truncated = True
        full_text = full_text[:max_chars] + TRUNCATION_MARKER
        budget = max_chars
        for p in pages:
            if budget <= 0:
                p["text"] = "[truncated -- request this page via first_page/last_page]"
                continue
            if len(p["text"]) > budget:
                p["text"] = p["text"][:budget] + " …[truncated]"
            budget -= len(p["text"])

    out = {
        "text": full_text,
        "text_extractor": "docling",
        "text_extractor_note": why,
        "tables": all_tables,
        "pages": pages,
        "num_pages": total_pages,
        "n_chars_available": n_chars_available,
        "pages_extracted": [lo, hi] if pages else [],
        "truncated": truncated,
        "unreadable": no_readable_body,
    }
    if no_readable_body:
        out["error"] = (
            f"{pdf_path.name} has {total_pages} page(s) but NO READABLE TEXT "
            "LAYER: every character extracted is page furniture repeated "
            "across the document (a download stamp, a copyright line, a "
            "running head) or this tool's own page separators. It is a scan "
            "whose OCR produced nothing usable. NOTHING was read, so the "
            "paper's contents are UNKNOWN -- an empty `tables` list and a "
            "check that finds no statistics are facts about this extraction, "
            "NOT about the paper, and must not be reported as though the "
            "paper were clean. To review it at all, the pages have to be read "
            "as images."
        )

    # AN OBSERVED ZERO IS NOT A MISSING ANSWER, and until 2026-08-17 a caller
    # could not tell those apart from this return.
    #
    # MEASURED on the first document of the repaired Zotero stress run (a 2013
    # bench-biology paper, 11 pages, 19,894 body characters, 7 figures): docling
    # parsed it cleanly and detected no table structures, which is almost
    # certainly correct -- its own text never says "Table" followed by a number,
    # and figure-borne data is the house style of that literature. The return
    # nonetheless looked byte-identical to one from a document nothing could be
    # read from: `tables: []` and no word about why.
    #
    # That is the house defect in its quietest form. `tables: []` was carrying
    # two incompatible meanings -- "this paper has none" and "we did not find
    # out" -- and only the first is a fact about the paper. Saying which one
    # this is costs nothing and stops a downstream consumer inferring the wrong
    # one, which is how an absence becomes evidence.
    if not all_tables and not no_readable_body:
        out["tables_note"] = (
            f"docling read {total_pages} page(s) of {pdf_path.name} and "
            "detected NO table structures. This is an OBSERVED zero, not a "
            "failure to look: the pages were parsed and no ruled table was "
            "found in them. Papers whose data lives in figures legitimately "
            "reach this state. It is still worth checking the text for "
            "'Table 1' -- a paper that refers to tables we did not extract is "
            "a recall failure, and that is a different thing entirely."
        )
    return out
