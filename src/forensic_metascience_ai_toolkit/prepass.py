"""Checks run on EVERY eligible target, not on the ones a model chose.

WHY THIS EXISTS. The Romano run-to-run study
(`scratchpad/romano_variability_fable_2026-08-11.md`, local scratch, not tracked) compared two runs of one
paper at byte-identical prompt and schema and found one clean split:

    checks with a unique, argument-free target      8 of 8 recurred  (100%)
    checks where the MODEL picks the target
      or supplies an auxiliary assumption           0 of 10 recurred (0%)

Tool determinism does not survive target freedom. The sharpest case: both runs
called `absence_of_evidence` three times, on six different cells, with ZERO
overlap -- and each run had the other's cells inside its own multiplicity
arguments, so each had looked at the other's numbers and stayed silent. And
`detect_duplication` ran in one run (960 comparisons, clean) and not the other,
which merely listed it under `not_checked`.

The fix is not a better prompt. It is to stop asking. Where a target list can be
ENUMERATED from the paper, the harness enumerates it and runs the check on all
of it, and the model's job shrinks to what only it can do: read the paper,
declare what the variables are, and interpret results. That is the same argument
`dispatch.py` makes about tool SELECTION, applied one level out to tool
TARGETING.

WHAT IS AND IS NOT HERE. Two sweeps, both with fully enumerable targets:

  * `sweep_duplication` -- every (mean, SD) pair in every table. Needs no
    declaration from anybody, so it is pure harness work.
  * `sweep_sd_range` -- every `mean_sd` cell whose variable DECLARES bounds.
    Needs the model's anatomy, so it runs after stage 1.

A third, `absence_of_evidence` over every claim of no effect, is NOT here and is
tracked separately: its targets are prose claims ("did not differ"), and finding
them is an extraction problem rather than a wiring one.

THE RULE THIS MODULE MUST NEVER BREAK. A target whose preconditions are absent
is SKIPPED AND COUNTED, never run on invented inputs. `dispatch.py` records what
that costs: SPRITE, handed a "Number of coalition members" cell with no stated
bounds, assumed a 1-7 Likert scale and returned `impossible` on a paper that was
fine. Exhaustive targeting multiplies whatever it does, so it must multiply
refusals rather than assumptions.

THE GRIM SWEEP IS THE EXCEPTION (Dan, 2026-10-18): its failures ARE filed, one
finding per table, by `grim_harness.finding_rows` -- because its premises are
the tools agent's own declarations, read back from the run, and a check that
records 80 failures nobody files is a recall gap, not caution. The rule below
still holds for the duplication and sd_range sweeps.

AND THE RESULTS ARE RECORDED, NOT INJECTED. These sweeps do not append findings
to the report. A deterministic tool result is strong evidence, but a machine
writing accusations into a document nobody read is the C3 shape in reverse (see
`anchoring.py`), and this project's standing rule is that published content is
authored and understood by us. What the sweep produces is COVERAGE: a fixed,
run-invariant statement of what was checked and what it returned, plus a loud
marker when the harness found something at an accusatory tier that the run's
own findings never mention.
"""
from __future__ import annotations

import re

from pathlib import Path
from typing import Any

#: Severities that would accuse if a reader acted on them. A harness sweep that
#: reaches one of these on a cell the run never mentioned is the gap worth
#: shouting about.
from .tools.severity import ACCUSES_AT_ALL as ACCUSATORY  # one definition; see severity.py


#: C0 controls minus ordinary whitespace. A broken font CMap leaks the raw
#: glyph INDEX here; see `glyphs.py`.
_C0_CELL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _repair_proven_glyphs(base: Path, tables: list[dict],
                          problems: list[str]) -> None:
    """Apply to table cells only the character repairs THIS paper proves.

    Table cells carry the same font damage the prose does and nothing repaired
    them. MEASURED over the 211 cached Zotero extractions: 195 of 24,112 cells
    (0.81%) hold a raw control character, 178 of them in `EPIVI7B3` -- which is
    exactly the paper whose own text proves `\x06` is `±` (40 occurrences of
    `mean \x06 SD`, not one literal `±`).

    Applied HERE because `paper_tables` is the single walker every consumer
    shares. Repairing in one caller and not another would put two spellings of
    the same cell into the pipeline -- the two-denominators defect this module's
    own docstring warns about, wearing a different hat.

    STRICTLY GATED by `glyphs.proven_repairs`: a textual anchor in this document
    AND the absence of the real character. EPIVI7B3 also spells MINUS as
    `\x00`, which nothing proves, so a cell reading `\x00 3.5 \x06 7.6`
    becomes `\x00 3.5 ± 7.6` and still will not type -- correctly, because its
    sign is still missing. Only fully proven cells come back.

    Cheap in the normal case: cells are scanned for a control character before
    the paper text is read at all, and 99.2% of papers have none.
    """
    from .glyphs import proven_repairs

    if not any(_C0_CELL.search(str((c or {}).get("raw") or ""))
               for t in tables for c in (t.get("cells") or [])
               if isinstance(c, dict)):
        return
    from .extraction.jats import paper_text

    # NOT WRAPPED IN A BARE `except`. The first cut was, and it unpacked
    # `paper_text` as a 2-tuple when it returns a plain `str` -- so every call
    # raised, the guard swallowed it, and "we crashed" was rendered as "this
    # paper proves nothing". That is this repository's named failure mode
    # committed by the very guard meant to be careful. A read failure is
    # reported below on its own terms.
    try:
        text = paper_text(base)
    except OSError as exc:
        problems.append(f"could not read {base.name} to check its glyph "
                        f"repairs: {type(exc).__name__}: {exc}")
        return
    # `paper_text` returns "" for a paper we COULD NOT READ as well as for one
    # with nothing in it, and the two mean different things here. Unreadable:
    # we cannot prove or disprove anything, and the cells stay damaged for a
    # reason that is OURS. Read-but-unproven: the paper genuinely does not
    # establish the mapping. Both leave the cells alone; only one is our fault,
    # and a reader chasing 145 unusable cells needs to know which.
    if not (text or "").strip():
        problems.append(
            "table cells contain raw font glyph indices, and this paper's text "
            "could not be read at all, so no repair could be proven either way; "
            "the cells are left as-is and will not type")
        return
    repairs = proven_repairs(text if isinstance(text, str) else "")
    if not repairs:
        # NOT SILENT. These cells are about to fail typing, and a reader
        # deserves to know it was the font and not the parser.
        problems.append(
            "table cells contain raw font glyph indices (control characters) "
            "and this paper's own text does not prove what they stand for, so "
            "they are left as-is and will not type; see `glyphs.scan`")
        return
    n = 0
    for t in tables:
        for c in (t.get("cells") or []):
            if not isinstance(c, dict):
                continue
            raw = str(c.get("raw") or "")
            fixed = raw
            for bad, good in repairs.items():
                fixed = fixed.replace(bad, good)
            if fixed != raw:
                c["raw"] = fixed
                n += 1
    if n:
        problems.append(
            f"repaired {n} table cell(s) whose font emitted a raw glyph index, "
            f"using a mapping this paper's own text proves ("
            + ", ".join(f"{k!r}->{v!r}" for k, v in repairs.items()) + ")")


def _article_html_tables(base: Path, problems: list[str]) -> list[dict] | None:
    """Walker-shaped tables from fetched publisher HTML, or None if there is none.

    `None` and `[]` are DIFFERENT ANSWERS and the caller depends on it: `None`
    means no usable HTML exists, so fall through to the PDF; `[]` means the HTML
    IS the paper and genuinely has no tables, and falling through would then read
    a different document than the served text.

    Goes through `find_html`, so the decoy gate applies here too -- a Cloudflare
    challenge page cannot supply tables any more than it can supply text.

    `extract_html_text_with_tables` already emits `jats._build_table`'s contract
    (`cells`, `headers`, `header_rows`, `n_header_rows`, spans), so nothing is
    re-derived here. Its `source` field says `"html"`, which is the FORMAT; the
    walker's `source` says `"article"` vs `"supplement"`, which is the ROLE.
    Those are different axes and conflating them is how a supplement table would
    start reporting as the article's.
    """
    from .extraction.html import extract_html_text_with_tables, find_html

    path = find_html(base)
    if path is None:
        return None
    try:
        # A LARGE BUDGET DELIBERATELY. The 50,000-char default is a TEXT budget;
        # a table found past it would be dropped, and a dropped table is
        # indistinguishable downstream from a paper that has none.
        res = extract_html_text_with_tables(path, max_chars=10_000_000)
    except Exception as exc:  # noqa: BLE001 -- named, never silent
        problems.append(f"could not read {path.name}: {type(exc).__name__}: {exc}")
        return None
    if res.get("error"):
        problems.append(f"{path.name}: {res['error']}")
        return None
    out: list[dict] = []
    for t in (res.get("tables") or []):
        num = t.get("table_num")
        out.append({"label": t.get("label") or t.get("caption") or f"Table {num}",
                    "cells": list(t.get("cells") or []),
                    "source": "article",
                    "extractor": "html",
                    "sections": list(t.get("sections") or []),
                    "caption": t.get("caption") or None,
                    "footnotes": list(t.get("footnotes") or []),
                    "section": t.get("section") or None,
                    "table_id": t.get("id") or None,
                    "page": t.get("page"),
                    "header_rows": t.get("header_rows"),
                    "n_header_rows": t.get("n_header_rows"),
                    "header_adjuncts": list(t.get("header_adjuncts") or []),
                    "image_only": bool(t.get("image_only"))})
    return out


def paper_tables(paper_dir, include_supplements: bool = False) -> list[dict]:
    """`[{label, cells, source}]` read from the paper. No model involved.

    Shared with `agent._checkable_coverage`, which needs the identical list --
    two walks of the same tables would be two denominators, and this repo has
    already published one coverage figure computed against a different
    denominator from the one beside it.

    `include_supplements` is OPT-IN, and off by default, because turning it on
    changes what a caller's denominator means. Each call site decides
    deliberately and says why; a silent default would have moved several
    published counts at once. It is the single walker for supplement tables --
    a second one would recreate exactly the two-denominators defect this
    docstring already warns about.

    Pages through large tables: `get_table` windows its output, and stopping at
    the window would silently shrink every enumeration built on this.
    """
    from .extraction.jats import extract_xml_text_with_tables, get_table

    base = Path(paper_dir)
    base = base if base.is_dir() else base.parent
    problems: list[str] = []
    xmls = sorted(base.glob("*.xml"))
    if not xmls:
        # NO XML IS NOT NO TABLES, and returning `[]` said it was. MEASURED
        # 2026-08-13: 308 of 315 paper directories here (97.8%) have no
        # publisher XML, so this branch was the NORMAL case -- and it returned
        # an empty list recording no problem, which made the completeness
        # manifest report `n_table_items: 0` for papers that plainly have
        # tables. `10.1007--s00702-004-0248-2` carries 8 findings located in
        # tables against a manifest saying it has none.
        #
        # The model was finding those tables anyway, by electing to call
        # `extract_pdf` itself -- which is the "delivery, not initiative"
        # failure `_supplement_tables` names one function below: anything left
        # to the model's election inherits its targeting variability.
        #
        # HTML BEFORE THE PDF, because the TEXT ladder already ranks it there
        # and the two must name the same document. `jats._derive_paper_text`
        # returns `html` ahead of `pdf`; if the walker skipped to the PDF a
        # finding could quote a table the served text does not contain, and the
        # coverage denominator would describe a different rendering of the paper
        # than the one the model read.
        #
        # MEASURED 2026-09-05, and this was a real hole rather than a tidiness
        # one: `grep -c -i html prepass.py` returned 0, so an HTML-sourced paper
        # had NO tables at all. On `10.1073--pnas.1211286109` the HTML rung lost
        # 34 numerals including Table 1's entire means-and-SDs block -- so
        # upgrading a paper from PDF to HTML traded a font-corrupted text layer
        # for no tables, and the upgrade was not safe to make until this existed.
        html_out = _article_html_tables(base, problems_out := [])
        problems += problems_out
        if html_out is not None:
            supp_texts: list[dict] = []
            unextracted: list[str] = []
            if include_supplements:
                html_out += _supplement_tables(base, problems, supp_texts, unextracted)
            return _walked(html_out, problems, supp_texts, unextracted)
        return _article_pdf_tables(base, include_supplements)
    src = str(xmls[0])
    # A FAILURE HERE IS OURS AND MUST SAY SO. Returning `[]` on an unreadable
    # file makes "we could not open this paper" indistinguishable from "this
    # paper has no tables", and every count built on the walk then reports our
    # failure as a property of their work. That is the exact defect `paper_text`
    # had -- it swallowed every extraction crash and returned "", and four of
    # its five consumers published a clean result on a paper never opened.
    # `problems` rides along on the list so the caller can tell the two apart;
    # the sweeps still never raise, because no coverage statistic is worth
    # losing a paid analysis over.
    out: list[dict] = []
    try:
        idx = extract_xml_text_with_tables(src, max_chars=2000)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"could not index {Path(src).name}: "
                        f"{type(exc).__name__}: {exc}")
        return _walked(out, problems)
    for num in range(1, (idx.get("n_tables") or 0) + 1):
        try:
            tab = get_table(src, num)
            if not tab.get("found"):
                continue
            got = list(tab.get("cells") or [])
            while tab.get("cells_total") and len(got) < tab["cells_total"]:
                nxt = get_table(src, num, first_row=got[-1]["row"] + 1)
                more = nxt.get("cells") or []
                if not more:
                    break
                got += more
                tab = nxt
        except Exception as exc:  # noqa: BLE001
            problems.append(f"table {num} unreadable: "
                            f"{type(exc).__name__}: {exc}")
            continue
        out.append({"label": tab.get("label") or f"Table {num}", "cells": got,
                    "source": "article",
                    # The XML's own table number: the workbench XML pane names
                    # each grid `table-{n}`, so a cell anchor needs it.
                    "table_num": num,
                    # CARRIED, not recomputed. A band is a fact about the
                    # printed table and a reader has to be able to see which
                    # rows one governed.
                    "sections": list(tab.get("sections") or []),
                    # THE TABLE'S OWN FACTS, CARRIED. This dict used to select
                    # five keys from a record with twenty-two, so a caption, a
                    # section heading and the table's own footnotes were read
                    # out of the source and dropped one function later.
                    #
                    # `values.build_from_paper` calls this walker and says why
                    # ("ONE WALKER, deliberately ... a second walk is two
                    # denominators"), so a field dropped HERE is a field the
                    # register can never carry, whatever its schema says.
                    #
                    # The footnote is not decoration. On `10.1002--eat.24415`
                    # TABLE 1 it reads "Note: N = 107" -- the table's own stated
                    # denominator, which every count/percent check otherwise has
                    # to infer from a column header. And `agent.py` instructs the
                    # MODEL to "Read each table's `footnotes` before typing: they
                    # define whether a cell is `n (%)` or `mean (SD)`". The model
                    # was getting them and the floor was not: two readings of one
                    # paper, one strictly poorer, and nothing comparing them.
                    #
                    # Only the XML path fills these; the PDF extractors return
                    # empty, which is the honest picture rather than a gap.
                    "caption": tab.get("caption") or None,
                    "footnotes": list(tab.get("footnotes") or []),
                    "section": tab.get("section") or None,
                    "table_id": tab.get("id") or None,
                    "page": tab.get("page"),
                    "header_rows": tab.get("header_rows"),
                    # BOTH, BECAUSE THEY ARE DIFFERENT FACTS AND TWO PRODUCERS
                    # EMIT DIFFERENT ONES. `jats.py:1030` emits `header_rows`
                    # as the LIST of header rows; `jats.py:1031` emits
                    # `n_header_rows` as the COUNT; and `jats.get_table`
                    # (:1661) emits only the count. Carrying just the list lost
                    # the header depth on every table that came through
                    # `get_table` -- measured over 26 corpus tables, 18 carry a
                    # list and 8 carry None, and all 8 have the count available
                    # under the other name. A consumer that wants the depth
                    # should not have to know which producer it got.
                    "n_header_rows": tab.get("n_header_rows"),
                    "header_adjuncts": list(tab.get("header_adjuncts") or []),
                    "image_only": bool(tab.get("image_only"))})

    # AN XML WHOSE TABLES ARE ALL PICTURES IS NOT A READING OF THEM. Some
    # publishers -- AHA/Stroke among them -- ship full-text JATS whose
    # `<table-wrap>` holds a `<graphic>` and no `<tr>` at all. This walker
    # returned those as tables with zero cells, and because XML outranks the
    # PDF the paper then had NO table content whatsoever.
    #
    # MEASURED 2026-08-19 over the eleven prioritised cerebrolysin papers: five
    # ship XML, and on two of them (`10.1161--strokeaha.115.009416`,
    # `10.1161--strokeaha.124.049834`) every table is a JPEG. 265 cells that
    # docling had already read from the PDF were being discarded -- on CARS and
    # ESCAS, two of the trials the review is actually about.
    #
    # `get_table` already said so: it sets `image_only`, carries the
    # `graphic_href`, and warns "table is an image in the XML and has no cells;
    # extract it from the PDF or record it as unchecked". This function read
    # that answer and dropped it. So it now does what the warning says.
    #
    # ALL, not ANY. A partial XML -- some tables marked up, one a picture -- is
    # still the better reading and is kept; falling through on one picture
    # would trade good markup for an extraction. The tables that ARE images in
    # that case stay empty and stay reported, which is the honest state.
    if out and not any(t.get("cells") for t in out):
        images = [t["label"] for t in out if t.get("image_only")]
        if images:
            problems.append(
                f"every table in {Path(src).name} is a picture in the XML "
                f"({', '.join(images[:4])}{'...' if len(images) > 4 else ''}), so "
                "the markup carries no cells at all; the PDF was read instead. "
                "The XML remains the authority for everything else in this paper.")
            return _article_pdf_tables(base, include_supplements,
                                       problems=problems)

    supp_texts: list[dict] = []
    unextracted: list[str] = []
    if include_supplements:
        out += _supplement_tables(base, problems, supp_texts, unextracted)
    _repair_proven_glyphs(base, out, problems)
    return _walked(out, problems, supp_texts, unextracted)


def _text_layer_lies(pdf: Path, problems: list[str]) -> bool:
    """Is THIS PDF's text layer corrupt enough to prefer a pixel reading?

    Asked of the text docling actually produced for this file, not of the paper
    as a whole: a clean article can carry a supplement whose font is broken, and
    the choice of reader is made per file.

    FAILS CLOSED, to the text layer. An unreadable cache or a scanner that
    raises means we do not KNOW the text is damaged, and swapping in a paid
    pixel reading on a maybe is how a clean paper gets read by the noisier of
    two tools. `glyphs.scan` already draws the line: `clean` false means the
    characters carry corruption the patterns recognise.
    """
    from .extraction import docling_tables as _dl
    from . import glyphs as _glyphs

    res = _dl.extract_pdf_tables(pdf, allow_extract=False)
    text = res.get("text") or ""
    if not text:
        return False
    try:
        verdict = _glyphs.scan(text)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"could not check {pdf.name} for glyph corruption "
                        f"({type(exc).__name__}: {exc}); the text layer was used")
        return False
    if verdict.get("clean", True):
        return False
    problems.append(
        f"{pdf.name}: the text layer carries character corruption "
        f"({verdict.get('total_occurrences')} occurrence(s)), so the Mistral "
        "pixel reading was preferred over docling for its tables")
    return True


def _report_stale_caches(base: Path, problems: list[str]) -> None:
    """Name every PDF whose cached extraction predates a fix that changes it.

    `agent.ensure_paper_extracted` already asks `cache_status` and re-extracts
    anything below schema 5 -- that guard is correct and has always been there.
    This walk deliberately does NOT re-extract: it is the cheap cache-only path
    that makes rebuilding a register affordable, and paying docling's 24-140 s
    per file to measure would end the practice of measuring.

    Reading a stale cache is therefore fine. Returning its numbers with nothing
    to say they predate the fix is not.

    MEASURED 2026-08-20, which is why this exists: every register figure
    reported for PDF supplements that day came from caches written at 17:41 on
    2026-08-19, ninety-four minutes BEFORE `cbf197f` taught docling to read its
    own `column_header` flags. The numbers looked current. Re-extracting those
    five supplements moved duplicate-labelled columns from 32.7% to 18.6% and
    stacked headers found from 0 to 15, and the conclusion drawn from the stale
    figures -- that docling mishandles supplement tables and the corpus should
    be re-read by a paid extractor -- did not survive the correction.

    A stale cache is OUR state, not a property of the paper, and this codebase's
    standing rule is that the two must never arrive in the same shape.
    """
    # NEITHER FAILURE IS SWALLOWED. `lint-inert` caught the first draft of this
    # function discarding both, which would have made "the freshness check
    # crashed" indistinguishable from "the cache is fresh" -- the exact
    # confusion the function exists to prevent, committed inside it. A guard
    # that fails silently is worse than no guard, because it reads as an
    # all-clear.
    try:
        from .extraction import docling_tables as _dl
    except Exception as exc:  # noqa: BLE001
        problems.append(
            f"cache freshness unchecked ({type(exc).__name__}: {exc}): docling "
            "could not be imported, so whether these tables came from a "
            "pre-fix extraction is UNKNOWN, not confirmed current.")
        return
    for pdf in sorted(base.glob("*.pdf")):
        try:
            usable, why = _dl.cache_status(pdf)
        except Exception as exc:  # noqa: BLE001
            problems.append(
                f"{pdf.name}: cache freshness unchecked "
                f"({type(exc).__name__}: {exc}). Whether this reading predates "
                "the header-depth fix is UNKNOWN.")
            continue
        # ONLY the staleness case. "not extracted yet" is a different fact with
        # its own reporting, and duplicating it here would double-count it.
        if not usable and "schema" in (why or ""):
            problems.append(
                f"{pdf.name}: {why}. Read from cache anyway -- these numbers "
                "describe the cached extraction, not what this code would "
                "produce now.")


def _article_pdf_tables(base: Path, include_supplements: bool = False,
                        problems: list[str] | None = None) -> list[dict]:
    """The article's tables when the publisher gave us only a PDF.

    Which is almost always: 97.8% of the paper directories here have no XML.

    MEASURED 2026-08-13 against the seven papers that ship BOTH formats, so the
    XML is a ground truth for what the PDF ought to yield:

        pdfplumber   precision 88.3%   recall 60.7%
        docling      precision 92.0%   recall 95.9%

    Docling is used because it wins on both axes; see
    `extraction/docling_tables.py` for why routing and ensembles were measured
    and rejected. THE XML IS STILL PREFERRED WHENEVER IT EXISTS -- it is not an
    extraction at all, it is the marked-up truth, and no model beats reading the
    answer.

    A failure is reported, never returned as an empty list. "We could not read
    this PDF" and "this paper has no tables" are opposite facts and this
    function's whole reason for existing is that they were the same value.
    """
    from . import supplements as _supp

    # Inherited when the XML walker handed over, so the reason it did is not
    # lost on the way -- a caller must still be able to see that this paper HAS
    # publisher markup and why it was not used for the tables.
    problems = problems if problems is not None else []
    # SAY SO BEFORE READING IT. See `_report_stale_caches`: this path serves a
    # pre-fix cache by design, and the numbers built on one must not look
    # current.
    _report_stale_caches(base, problems)
    out: list[dict] = []

    # THE ARTICLE, BY DECLARATION, not by guessing at filenames. `classify_inputs`
    # already knows which file is the article -- from the operator's
    # `inputs.json`, the fetch record, or the DOI stem -- and duplicating that
    # judgement here is how two parts of one pipeline come to disagree about
    # what they are reading.
    try:
        rows = (_supp.classify_inputs(base).get("files") or [])
    except Exception as exc:  # noqa: BLE001
        problems.append(f"could not classify the files in {base.name}: "
                        f"{type(exc).__name__}: {exc}")
        rows = []
    articles = [base / r["name"] for r in rows
                if r.get("role") == "article" and str(r.get("name", "")).lower().endswith(".pdf")]
    if not articles:
        pdfs = sorted(base.glob("*.pdf"))
        # ONLY WHEN THERE IS EXACTLY ONE. `pdfs[:1]` took whichever sorted
        # first, so a directory holding the paper and a supplement could have
        # had the SUPPLEMENT's tables read as the article's. Measured, every
        # corpus directory here holds 0 or 1 PDF, so this costs nothing today
        # and removes the hazard for the day one holds two. Matches
        # `completeness._article_pdf`, which refuses on ambiguity for the same
        # reason.
        if len(pdfs) == 1:
            articles = pdfs[:1]
            problems.append(
                f"no file is declared the article, so {pdfs[0].name} was read as "
                "one -- it is the only PDF here. Declare it with `metascience "
                "inputs` to be sure.")
        elif pdfs:
            problems.append(
                f"{len(pdfs)} PDFs here and none is declared the article, so no "
                "tables were read from any of them; picking by filename risks "
                "reading a supplement as the paper. Declare it with "
                "`metascience inputs`.")

    from .extraction import docling_tables as _dl
    from .extraction import mistral_tables as _mistral
    for pdf in articles:
        # THE PIXEL READING WINS ONLY WHERE THE TEXT LAYER LIES. An earlier
        # version preferred a Mistral extraction whenever one existed, on the
        # strength of a benchmark that measured 1,378 statistics against
        # docling's 1,208 with 0 hallucination markers against 47. That
        # benchmark ran on 22 papers SELECTED FOR BEING DAMAGED, and reading a
        # property of that sample as a property of extractors was a selection
        # effect, not a finding.
        #
        # MEASURED 2026-08-19 on the eleven prioritised cerebrolysin papers, of
        # which `glyphs.scan_paper` calls nine clean: Mistral 1,262 cells,
        # docling 1,250 -- a tie, and docling ahead on four PDFs. It read 157
        # cells from CARS where Mistral read 108, and 45 from the CASTA data
        # supplement where Mistral read none at all. On the two papers that DO
        # carry glyph damage the order reverses, which is the benchmark's real
        # result: pixels beat a text layer that lies, and lose to one that does
        # not, because docling detects more tables when it can read the text.
        #
        # So the question asked here is about THIS pdf's text, not about which
        # reader is better in general.
        mistral_problems: list[str] = []
        mistral_tables = _mistral.pdf_tables(pdf, mistral_problems)
        problems.extend(mistral_problems)
        if mistral_tables is not None and _text_layer_lies(pdf, problems):
            for t in mistral_tables:
                out.append({"label": t.get("label") or "Table",
                            "cells": list(t.get("cells") or []),
                            "source": "article",
                            "sections": list(t.get("sections") or []),
                            # THE TABLE'S OWN FACTS, CARRIED. This dict used to select
                            # five keys from a record with twenty-two, so a caption, a
                            # section heading and the table's own footnotes were read
                            # out of the source and dropped one function later.
                            #
                            # `values.build_from_paper` calls this walker and says why
                            # ("ONE WALKER, deliberately ... a second walk is two
                            # denominators"), so a field dropped HERE is a field the
                            # register can never carry, whatever its schema says.
                            #
                            # The footnote is not decoration. On `10.1002--eat.24415`
                            # TABLE 1 it reads "Note: N = 107" -- the table's own stated
                            # denominator, which every count/percent check otherwise has
                            # to infer from a column header. And `agent.py` instructs the
                            # MODEL to "Read each table's `footnotes` before typing: they
                            # define whether a cell is `n (%)` or `mean (SD)`". The model
                            # was getting them and the floor was not: two readings of one
                            # paper, one strictly poorer, and nothing comparing them.
                            #
                            # Only the XML path fills these; the PDF extractors return
                            # empty, which is the honest picture rather than a gap.
                            "caption": t.get("caption") or None,
                            "footnotes": list(t.get("footnotes") or []),
                            "section": t.get("section") or None,
                            "table_id": t.get("id") or None,
                            "page": t.get("page"),
                            "header_rows": t.get("header_rows"),
                    "n_header_rows": t.get("n_header_rows"),
                    "header_adjuncts": list(t.get("header_adjuncts") or []),
                            "extractor": "mistral",
                            "extracted_from": pdf.name})
            continue
        # CACHE ONLY. `paper_tables` is a cheap enumeration that many callers
        # make; running a layout model inside it took the suite from 260 s to
        # 596 s and raced two xdist workers into one cache file. Extraction is
        # an explicit step -- `metascience extract-tables` -- and a cold cache
        # is REPORTED here, not silently treated as a paper without tables.
        res = _dl.extract_pdf_tables(pdf, allow_extract=False)
        if res.get("error"):
            problems.append(f"{pdf.name}: {res['error']}")
            continue
        for t in (res.get("tables") or []):
            out.append({"label": t.get("label") or "Table",
                        "cells": list(t.get("cells") or []),
                        "source": "article",
                        "sections": list(t.get("sections") or []),
                        # THE TABLE'S OWN FACTS, CARRIED. This dict used to select
                        # five keys from a record with twenty-two, so a caption, a
                        # section heading and the table's own footnotes were read
                        # out of the source and dropped one function later.
                        #
                        # `values.build_from_paper` calls this walker and says why
                        # ("ONE WALKER, deliberately ... a second walk is two
                        # denominators"), so a field dropped HERE is a field the
                        # register can never carry, whatever its schema says.
                        #
                        # The footnote is not decoration. On `10.1002--eat.24415`
                        # TABLE 1 it reads "Note: N = 107" -- the table's own stated
                        # denominator, which every count/percent check otherwise has
                        # to infer from a column header. And `agent.py` instructs the
                        # MODEL to "Read each table's `footnotes` before typing: they
                        # define whether a cell is `n (%)` or `mean (SD)`". The model
                        # was getting them and the floor was not: two readings of one
                        # paper, one strictly poorer, and nothing comparing them.
                        #
                        # Only the XML path fills these; the PDF extractors return
                        # empty, which is the honest picture rather than a gap.
                        "caption": t.get("caption") or None,
                        "footnotes": list(t.get("footnotes") or []),
                        "section": t.get("section") or None,
                        "table_id": t.get("id") or None,
                        "page": t.get("page"),
                        "header_rows": t.get("header_rows"),
                    "n_header_rows": t.get("n_header_rows"),
                    "header_adjuncts": list(t.get("header_adjuncts") or []),
                        "extractor": "docling",
                        "extracted_from": pdf.name})
    if not out and not problems:
        problems.append(
            f"no tables were found in {base.name} and nothing failed, so either "
            "the article genuinely prints none or the extractor could not see "
            "them. This is stated because a silent empty list is what made 0 "
            "table items indistinguishable from 0 tables.")
    supp_texts: list[dict] = []
    unextracted: list[str] = []
    if include_supplements:
        out += _supplement_tables(base, problems, supp_texts, unextracted)
    _repair_proven_glyphs(base, out, problems)
    return _walked(out, problems, supp_texts, unextracted)


def _supplement_tables(base: Path, problems: list[str],
                       texts: list[dict] | None = None,
                       unextracted: list[str] | None = None) -> list[dict]:
    """Supplement tables, walked the same way and labelled by their file.

    `texts`, when given, collects each readable supplement's RUNNING PROSE
    (`{file, text}`) from the same read. It is not a second product bolted on:
    every reader in `supplements_read` already returns `text` beside `tables`
    and this function was dropping it, so a supplement's paragraphs -- where a
    paper such as `10.1111--jcpp.13879` puts 47 p values and no table at all --
    were extracted and discarded in the one place that had them.

    DELIVERY, NOT INITIATIVE. Article tables are enumerated deterministically by
    the walk above; supplement tables were reachable only if the model elected to
    call `extract_supplement`. MEASURED over the whole archive on 2026-08-13:
    TWELVE such calls exist, and the two papers holding 13,064 of the 26,592
    supplement items received NONE. Meanwhile 90.4% of the checkable items in
    supplement-carrying papers live in those files.

    The capability was never the problem -- 11 of those 12 calls returned
    content, and the extractor reads a 1.1 MB eAppendix into 62 tables and
    12,052 cells without complaint. What failed is that anything left to the
    model's election inherits its targeting variability, which is measured at a
    Jaccard of 0.45 between runs and here lands at approximately zero.

    An unreadable supplement appends to `problems` and yields nothing, so a
    document we could not open never masquerades as a document with no tables.
    """
    out: list[dict] = []
    try:
        from . import supplements as _supp
        names = list(_supp.present_files(base) or [])
    except Exception as exc:  # noqa: BLE001
        problems.append(f"supplementary files could not be enumerated: "
                        f"{type(exc).__name__}: {exc}")
        return out
    for name in names:
        path = base / name if not Path(name).is_absolute() else Path(name)
        try:
            from .extraction.supplements_read import extract_supplement_full
            doc = extract_supplement_full(path)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"supplement {Path(name).name!r} unreadable: "
                            f"{type(exc).__name__}: {exc}")
            continue
        if not isinstance(doc, dict) or doc.get("error"):
            why = (doc or {}).get("error") if isinstance(doc, dict) else "no result"
            problems.append(f"supplement {Path(name).name!r} unreadable: {why}")
            continue
        short = Path(name).name
        if doc.get("unextracted"):
            # NOT LOOKED AT, WHICH IS NOT THE SAME AS EMPTY. `extract_pdf_tables`
            # reads the docling cache and never runs the extractor, so a
            # supplement nobody has extracted comes back with no text and no
            # tables -- shaped exactly like a supplement that has neither. That
            # was silent here: the file reached no `problems` entry, no text and
            # no denominator, and the account then reported the paper as having
            # a supplement with nothing in it.
            if unextracted is not None:
                unextracted.append(short)
            problems.append(
                f"supplement {short!r} has NOT been extracted, so its contents are UNKNOWN. "
                "This is our gap and not a property of the file: it is not evidence that the "
                "supplement has no tables and not evidence that it is a scan. Run "
                f"`metascience extract-tables {base}`")
            continue
        if texts is not None and str(doc.get("text") or "").strip():
            # HOW MUCH OF THE FILE THIS IS. A reader that caps its output says
            # so (`extract_pdf_tables` does, and its cap took 239,222 of
            # jamanetworkopen.2023.51752's 289,222 supplement characters); a
            # reader that takes the file whole says nothing, and then the served
            # length IS the available length. A reader that truncated WITHOUT
            # recording it would be mis-reported here, and that is a defect in
            # that reader: this layer cannot detect a loss nobody wrote down.
            served = str(doc["text"])
            texts.append({"file": short, "text": served,
                          "n_tables": len(doc.get("tables") or []),
                          "n_chars_available": (doc["n_chars_available"]
                                                if doc.get("n_chars_available") is not None
                                                else len(served)),
                          "truncated": bool(doc.get("text_truncated"))})
        for t in (doc.get("tables") or []):
            out.append({
                # The label carries the file, because "Table 1" of an eAppendix
                # and "Table 1" of the article are different tables and every
                # downstream key is built from this string.
                "label": f"{short} :: {t.get('label') or 'Table'}",
                "cells": list(t.get("cells") or []),
                "source": "supplement",
                # `sections` was dropped on THIS path alone, and 67% of the
                # corpus's groups are supplement-anchored -- so the band a row
                # belongs to was unavailable for two thirds of the register.
                "sections": list(t.get("sections") or []),
                # THE TABLE'S OWN FACTS, CARRIED. This dict used to select
                # five keys from a record with twenty-two, so a caption, a
                # section heading and the table's own footnotes were read
                # out of the source and dropped one function later.
                #
                # `values.build_from_paper` calls this walker and says why
                # ("ONE WALKER, deliberately ... a second walk is two
                # denominators"), so a field dropped HERE is a field the
                # register can never carry, whatever its schema says.
                #
                # The footnote is not decoration. On `10.1002--eat.24415`
                # TABLE 1 it reads "Note: N = 107" -- the table's own stated
                # denominator, which every count/percent check otherwise has
                # to infer from a column header. And `agent.py` instructs the
                # MODEL to "Read each table's `footnotes` before typing: they
                # define whether a cell is `n (%)` or `mean (SD)`". The model
                # was getting them and the floor was not: two readings of one
                # paper, one strictly poorer, and nothing comparing them.
                #
                # Only the XML path fills these; the PDF extractors return
                # empty, which is the honest picture rather than a gap.
                "caption": t.get("caption") or None,
                "footnotes": list(t.get("footnotes") or []),
                "section": t.get("section") or None,
                "table_id": t.get("id") or None,
                "page": t.get("page"),
                "header_rows": t.get("header_rows"),
                    "n_header_rows": t.get("n_header_rows"),
                    "header_adjuncts": list(t.get("header_adjuncts") or []),
                "supplement_file": short,
            })
    return out


class _walked(list):
    """The tables, carrying any failure that happened while reading them.

    A plain `list` subclass so every existing caller keeps iterating it
    unchanged, while a caller that cares can read `.problems` and refuse to
    report coverage computed over a walk that partly failed.

    `supplement_texts` rides here for the same reason `problems` does: the
    reader that produced a supplement's TABLES produced its RUNNING TEXT in the
    same call and this walker was discarding it, so a caller wanting the prose
    had to open every supplement a second time. `[{file, text}]` in walk order;
    empty when the walk did not include supplements.

    `unextracted_supplements` rides here for a third reason of the same shape: a
    supplement PDF nobody has run the extractor on comes back with no text and
    no tables, which is indistinguishable from a supplement that has neither.
    The caller has to be able to tell "we did not look" from "there is nothing
    there", and only this function knows which happened."""

    def __init__(self, tables, problems, supplement_texts=None,
                 unextracted_supplements=None):
        super().__init__(tables)
        self.problems = list(problems)
        self.supplement_texts = list(supplement_texts or [])
        self.unextracted_supplements = list(unextracted_supplements or [])


def _bounds_are_stated(var: dict) -> bool:
    """`Variable.bounds_are_stated`, read off a record the PIPELINE has stamped.

    WHY NOT `dispatch._variable_kwargs`, WHICH IS THE LIVE DERIVATION. Because
    it cannot work here, and finding that out cost a wrong measurement that was
    reported as a finding. `_as_variable` strips `provenance_verdict` from the
    input (so a model cannot certify its own quote) and re-derives it from
    `dispatch._haystack()`, which is built from `METASCIENCE_PAPER_DIR` -- an
    environment variable set only for the MCP subprocess. In any other process
    the haystack is empty, `_verify_variable_quote` correctly returns None, and
    EVERY variable reads as `assumed`. Measured through that path, 501 of 501
    archived cells looked unbounded and I reported that the gate had never once
    opened. It has: 50 of 199 archived variables satisfy it.

    So this reads the verdict `agent._annotate_quotes` already wrote onto the
    record. That is not the model's claim: that pass pops any model-supplied
    `provenance_verdict` UNCONDITIONALLY before adjudicating the quote against
    the paper itself, and writes its own only when the paper could be read.

    THE ORDERING THIS DEPENDS ON is enforced by the annotator chain in
    `agent.py`, where the exhaustive sweep runs AFTER `quotes`, and by
    `tests/test_prepass.py::TestItRunsAfterTheQuoteAdjudicator`. Run it before,
    and the field is absent, and every bound silently reads as assumed again.
    """
    if str(var.get("confidence") or "") != "high":
        return False
    return str(var.get("provenance_verdict") or "") in ("verbatim", "elided")


#: A column band naming a MODEL OUTPUT. A regression coefficient beside its
#: standard error is typographically identical to a mean beside its SD --
#: `8.57 (3.03)` reads both ways -- and only the column header distinguishes
#: them.
#:
#: MEASURED on 10.1002--ajcp.70049, which is why this exists: 69 cells type as
#: `mean_sd`, and 63 of them are regression coefficients from three tables
#: captioned "Associations between ...". Their column band reads
#: `Coefficient | M (SD)` -- the paper puts `M (SD)` UNDER a `Coefficient`
#: band, so the sub-label is convention (or the paper's own slip) and the band
#: is what the column actually holds.
#:
#: Binding one of those rows to the variable its label names and running
#: `check_sd_range` returns `impossible` on an honest paper: SD 3.03 against a
#: 1-5 scale, whose largest possible SD is 2.0. The verdict is arithmetically
#: correct and completely wrong, because 3.03 is a standard error, not an SD.
#: Measured directly: 19 checks, 18 consistent, ONE false `impossible`.
#:
#: THIS ONLY EVER REMOVES CHECKS, which is what makes it safe to be generous:
#: a false positive here costs coverage, never correctness (invariant 1 -- a
#: derived boundary may narrow a premise, never supply one). What is skipped is
#: counted and named so the loss cannot be silent.
_MODEL_OUTPUT_COL = re.compile(
    r"\b(coefficients?|coef|estimates?|beta|slopes?|loadings?|"
    r"odds[\s_-]*ratios?|a?ors?|risk[\s_-]*ratios?|hazard[\s_-]*ratios?|"
    r"rate[\s_-]*ratios?|a?[ir]rrs?|marginal[\s_-]*effects?)\b", re.I)

#: A COEFFICIENT SYMBOL beside a standard error: `b (SE)`, `B (SE)`,
#: `Beta (SE)`, `Est (SE)`. This is a model-output column, and the SYMBOL is
#: what says so -- not the SE.
#:
#: THIS WAS ONCE A BARE `(SE)` TEST, AND THAT WAS WRONG. Measured over the
#: 12-paper corpus, the bare rule blocked 168 cells and every one of them typed
#: `mean_se` -- meaning the cell typer had ALREADY recognised the parenthetical
#: as a standard error and was routing them to `check_sd_or_se`, the tool whose
#: entire job is adjudicating SE-versus-SD columns. `Mean (SE)` is an ordinary
#: descriptive column, and blocking it removed real coverage while preventing
#: nothing: `b (SE)` also types as `mean_se`, so the typer was never confused
#: about it either.
#:
#: What remains true is narrower and still worth guarding: a REGRESSION
#: coefficient's standard error is not a sample SD of any variable, so a
#: plausibility ceiling derived from that variable's range does not apply to
#: it. The coefficient symbol is the evidence for that, and a bare `b` alone is
#: too short a token to match safely -- paired with `(SE)` it is not.
_SE_COLUMN = re.compile(
    r"(?:^|\|)\s*(?:b|B|beta|\u03b2|est|estimate|coef|coeff)\s*"
    r"\(\s*(?:se|s\.e\.|standard\s+error)\s*\)", re.I)

#: A caption describing a MODELLING result rather than a description of the
#: sample. Secondary to the column band, which is the paper's own markup; used
#: when the band is absent or unlabelled.
_MODEL_OUTPUT_CAPTION = re.compile(
    r"\b(associations?[\s_-]+(between|of|with)|regress\w*|predictors?[\s_-]+of|"
    r"predicting|adjusted[\s_-]+(model|analys|odds|estimate))", re.I)


def reports_model_output(col_label=None, caption=None) -> str | None:
    """The reason this cell is a model output, or None.

    MEASURED 2026-08-31 over the 12-paper working corpus, 2,505 cells of
    descriptive kind (`mean_sd`, `mean_se`, `n_percent`):

      231 guarded, and every one audited by eye as a genuine model output --
          63 `Coefficient | M (SD)` on ajcp.70049, 168 `b (SE)` on eat.24415.
          ZERO false positives, so no descriptive coverage was lost.
      168 of those 231 are caught ONLY by the standard-error rule, because `b`
          is too short a token for the model-output pattern to match safely.
          That rule is not a refinement; it is most of the coverage.
        0 cells where the CAPTION says model-output and the column band misses.
          The band is sufficient on this corpus -- which is why `check_table`,
          which never receives a caption, loses nothing measurable by having
          only the band. Twelve papers is not proof of no blind spot; it is the
          reason the caption fallback is kept rather than deleted.

    Returns the matched phrase rather than a boolean so a skipped cell can say
    WHY it was skipped -- a count of silent skips is the coverage claim this
    codebase keeps having to un-inflate.
    """
    for text, where in ((col_label, "column"), (caption, "caption")):
        s = str(text or "")
        if not s:
            continue
        m = _SE_COLUMN.search(s)
        if m:
            return (f"{where} says {m.group(0).strip()!r} -- a regression "
                    f"coefficient beside its standard error, not a "
                    f"descriptive statistic of a measured variable")
        rx = _MODEL_OUTPUT_COL if where == "column" else _MODEL_OUTPUT_CAPTION
        m = rx.search(s)
        if m:
            return f"{where} says {m.group(0)!r}"
        # The column band is checked against the caption pattern too: a band
        # reading "Adjusted model 1" names a model as surely as a caption does.
        if where == "column" and _MODEL_OUTPUT_CAPTION.search(s):
            return f"column says {_MODEL_OUTPUT_CAPTION.search(s).group(0)!r}"
    return None


def _norm_label(s) -> str:
    """Row labels and variable names differ in punctuation and case, never in
    words. Deliberately NOT a fuzzy match: the 89%-failure location join in
    `anatomy.weight_finding_severity` is what free-text similarity buys."""
    import re
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def _typed(cells: list[dict]) -> list[dict]:
    """Typed cells, or nothing plus a warning that says so.

    Warns rather than returning a bare `[]`: a table whose cells could not be
    typed contributes zero targets, and a zero nobody logged is a coverage
    figure that quietly shrank."""
    import warnings

    from . import census as _census
    try:
        return (_census.parse_cells(cells) or {}).get("cells") or []
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"prepass: {len(cells)} cells could not be typed and are "
                      f"absent from every sweep total: "
                      f"{type(exc).__name__}: {exc}", stacklevel=2)
        return []


def sweep_duplication(tables: list[dict]) -> dict:
    """`detect_duplication` over every (mean, SD) pair the paper prints.

    ALWAYS RUN, and that is the entire point. It is one call over the whole
    paper, it needs no declaration from the model, and in the two archived runs
    of the same paper it fired in one and not the other -- the run that skipped
    it wrote "Whole paper, detect_duplication" into `not_checked`, so the system
    knew what it was skipping and skipped it anyway. A check whose target is the
    whole paper has nothing to choose, and should never have been optional.

    One block per table, because `detect_duplication` treats blocks as
    potentially independent samples: collapsing every table into one block would
    call two tables reporting the same cohort a duplication.
    """
    from .tools.duplication import detect_duplication

    blocks, n_pairs = [], 0
    for tab in tables:
        cells = []
        for c in _typed(tab.get("cells") or []):
            if c.get("kind") != "mean_sd":
                continue
            if c.get("value") is None or c.get("sd") is None:
                continue
            cells.append({
                "label": c.get("row_label") or c.get("raw") or "",
                "value": c["value"], "sd": c["sd"],
                "decimals_mean": c.get("decimals_value"),
                "decimals_sd": c.get("decimals_sd"),
            })
        if cells:
            n_pairs += len(cells)
            blocks.append({"label": tab.get("label"), "cells": cells})

    out: dict[str, Any] = {
        "tool": "detect_duplication",
        "targets_enumerated": n_pairs,
        "n_blocks": len(blocks),
    }
    if not blocks:
        # NOT a clean result. A paper printing no (mean, SD) pair gives this
        # check nothing to work on, and "no duplication found" would be a
        # statement about a search that never happened.
        out["ran"] = False
        out["severity"] = "indeterminate"
        out["why_not"] = (
            "The paper prints no (mean, SD) pair in any table, so there was "
            "nothing to compare. This is a refusal, not a clean result.")
        return out
    try:
        res = detect_duplication(blocks)
    except Exception as exc:  # noqa: BLE001
        out["ran"] = False
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["severity"] = "indeterminate"
        return out
    out["ran"] = True
    out["severity"] = res.get("severity")
    out["max_identical_pairs"] = res.get("max_identical_pairs")
    out["n_duplicate_groups"] = len(res.get("duplicate_groups") or [])
    out["result"] = res
    return out


def sweep_sd_range(tables: list[dict], variables: list[dict] | None,
                   bindings: dict | None) -> dict:
    """`check_sd_range` on every `mean_sd` cell whose variable declares bounds.

    RUNS AFTER STAGE 1 BECAUSE IT HAS TO. Measured on the Romano XML: 6 of 314
    cells are `mean_sd`, and **0 of the 6 are runnable** without a variable
    declaration -- the census says so in as many words ("a variable
    declaration: this kind is checkable but nothing routes it at
    data_type='unknown'"). The bounds are the whole check: everything
    `check_sd_range` knows flows from the range, so a harness that supplied its
    own range would be checking its own assumption and reporting the result as
    a fact about the paper.

    So a cell whose variable is undeclared, or declared without stated bounds,
    is SKIPPED AND COUNTED. `bound_source` comes from `dispatch._variable_kwargs`
    -- the same derivation the live path uses -- rather than from a rule
    restated here, because a second copy of that judgement would eventually be
    the more permissive one.

    WHAT IT ACTUALLY RETURNS TODAY, AND THIS IS THE POINT OF BUILDING IT.
    Replayed over 11 archived runs:

        mean_sd cells enumerated        501
          bound by name recovery         19
          CHECKED                         0
          refused, no declaration       482
          refused, bounds not stated     19

    ZERO. Not one cell in the archive reaches a determination, and the sweep is
    behaving correctly in every one of those 501 refusals. The blocker is
    upstream of targeting: `Variable.bounds_are_stated()` requires
    `confidence == "high"` AND a provenance quote verified `verbatim`/`elided`,
    and across 199 archived variable declarations that combination has never
    once been produced. The whole `mean_sd` family -- this check, and by the
    same gate SPRITE and GRIMMER -- has therefore never been reachable on a real
    paper, for a reason no coverage number previously stated.

    That finding is the deliverable here, not the checks. Exhaustive targeting
    turned an invisible gap into a counted one: the earlier `check_table`-based
    coverage figure reported cells "not checked" without distinguishing a cell
    nobody aimed at from a cell that could not be checked by anyone. Do NOT read
    the zero as this sweep failing. Read it as the sweep reporting, for the
    first time, that the bounds premise the family depends on is never
    established.
    """
    from .tools.sd_checks import check_sd_range

    by_id = {v.get("id"): v for v in (variables or []) if isinstance(v, dict)}
    bind = dict(bindings or {})
    # NO BINDINGS AT ALL IS THE NORMAL CASE. `bindings` is an argument the model
    # passes to `parse_cells_typed` per call; the anatomy block it writes to
    # `findings.json` carries variables and no row-label map, so a harness
    # reading the archive has 21 declared variables and no way to reach any of
    # them. Recovered here by EXACT normalised name match, which is precise and
    # thin: measured over 11 archived runs and 501 `mean_sd` cells, 19 (4%)
    # match exactly one variable and ZERO match more than one. Low recall, no
    # mis-binding -- and a cell matching several variables is skipped rather
    # than assigned to the first, because binding a row to the wrong variable
    # re-reads the cell against bounds that were never its own.
    if not bind and by_id:
        buckets: dict[str, list] = {}
        for v in by_id.values():
            buckets.setdefault(_norm_label(v.get("name")), []).append(v)
        derived = {k: hits[0].get("id") for k, hits in buckets.items()
                   if len(hits) == 1 and k}
        out_derived = derived
    else:
        out_derived = {}
    out: dict[str, Any] = {
        "tool": "check_sd_range",
        "targets_enumerated": 0, "n_checked": 0,
        "n_skipped_undeclared": 0, "n_skipped_unstated_bounds": 0,
        "n_skipped_model_output": 0, "skipped_model_output_why": {},
        "results": [], "worst": None,
    }
    worst_rank, order = 9, {"impossible": 0, "highly_suspicious": 1,
                            "suspicious": 2, "indeterminate": 3, "consistent": 4}
    for tab in tables:
        for c in _typed(tab.get("cells") or []):
            if c.get("kind") != "mean_sd" or c.get("sd") is None:
                continue
            out["targets_enumerated"] += 1

            # A COEFFICIENT IS NOT A MEAN, AND THE CELL CANNOT TELL YOU WHICH.
            # `8.57 (3.03)` types as mean_sd whether it is a mean beside its SD
            # or a coefficient beside its standard error; only the column band
            # says. Skipped BEFORE binding, because the danger is precisely
            # that the row label names a real variable -- bind it and
            # `check_sd_range` reads a standard error against that variable's
            # scale and returns `impossible` on an honest paper. Measured on
            # ajcp.70049: 63 of 69 targets are coefficients, and binding them
            # produced exactly one such false accusation.
            why = reports_model_output(c.get("col_label"), tab.get("caption"))
            if why:
                out["n_skipped_model_output"] += 1
                out["skipped_model_output_why"][why] = (
                    out["skipped_model_output_why"].get(why, 0) + 1)
                continue

            label = c.get("row_label")
            vid = bind.get(label)
            if vid is None and out_derived:
                vid = out_derived.get(_norm_label(label))
                if vid is not None:
                    out["n_bound_by_name"] = out.get("n_bound_by_name", 0) + 1
            var = by_id.get(vid)
            if not var:
                out["n_skipped_undeclared"] += 1
                continue
            lo, hi = var.get("lower_bound"), var.get("upper_bound")
            if lo is None or hi is None or not _bounds_are_stated(var):
                # THE LINE THAT MUST NOT MOVE. Running here with an invented
                # range is how SPRITE returned `impossible` on an honest
                # count variable by assuming a 1-7 Likert scale.
                out["n_skipped_unstated_bounds"] += 1
                continue
            try:
                res = check_sd_range(
                    sd=float(c["sd"]), min_val=float(lo), max_val=float(hi),
                    decimals_sd=c.get("decimals_sd"), bound_source="stated")
            except Exception as exc:  # noqa: BLE001
                res = {"severity": "indeterminate", "error": str(exc)}
            out["n_checked"] += 1
            sev = res.get("severity")
            out["results"].append({
                "table": tab.get("label"), "row_label": c.get("row_label"),
                "raw": c.get("raw"), "sd": c.get("sd"),
                "bounds": [lo, hi], "severity": sev,
            })
            if order.get(str(sev), 9) < worst_rank:
                worst_rank, out["worst"] = order.get(str(sev), 9), sev
    return out



def _sweep_claims(findings: dict | None) -> dict | None:
    """The claim-vs-printed-p sweep, driven off the anatomy.

    `alpha` is taken ONLY from the paper's own declaration. There is no default:
    assuming .05 would accuse every paper that pre-registered a different
    threshold, and the precedent for deleting rather than defaulting such a
    value is `76e9cc3`. With no stated alpha the sweep runs, checks nothing, and
    records why -- which keeps "we looked and found nothing" distinguishable
    from "we never looked".
    """
    from .anatomy import anatomy_from_findings
    from .tools.claims import claim_consistency_report
    try:
        anatomy = anatomy_from_findings(findings or {})
        if anatomy is None:
            return None
        studies = getattr(anatomy, "studies", None) or []
        alpha = next((a for a in (getattr(s, "alpha", None) for s in studies)
                      if isinstance(a, (int, float))), None)
        return claim_consistency_report(anatomy, alpha=alpha)
    except Exception as exc:  # noqa: BLE001
        # Recorded, never swallowed: a caller must be able to tell a sweep that
        # found nothing from one that never completed.
        return {"check": "claim_vs_printed_p", "error": f"{type(exc).__name__}: {exc}",
                "n_interpretations": 0, "n_contradictions": 0, "results": []}


NOT_ENABLED = "tool not enabled in this pipeline"


def _not_enabled(tool: str) -> dict:
    """A harness sweep the pipeline's toolset excludes: named, never a pass."""
    return {"tool": tool, "severity": None, "results": [], "not_run": NOT_ENABLED}


def run_exhaustive(paper_dir, findings: dict | None,
                   enabled: "frozenset[str] | None" = None,
                   ledger: list[dict] | None = None) -> dict | None:
    """Both sweeps, plus the statement a reader needs about what they cover.

    Returns None when the paper has no XML tables to enumerate -- silence rather
    than a zero, for the same reason `_checkable_coverage` returns None: a "0 of
    0 checked" line reads as a failure of the review rather than as the absence
    of a surface to review.

    SUPPLEMENTS INCLUDED. A duplicated pair of values is evidence wherever it
    sits, and eTables are exactly where a large results grid usually lives -- so
    excluding them narrowed the strongest deterministic check in the toolkit to
    the smaller half of the paper.

    Checked before enabling, because more tables means more pairwise comparisons
    and multiplicity is how a duplication sweep manufactures accusations: on the
    three supplement-carrying papers here, including 51752 at 84 tables, the
    worst severity is `none` both with and without them. `duplication.py` already
    corrects the coincidence probability by `n_comparisons`, and that correction
    absorbs the extra pairs rather than letting them accumulate.
    """
    anatomy = ((findings or {}).get("anatomy") or {})
    variables = anatomy.get("variables") if isinstance(anatomy, dict) else None
    bindings = anatomy.get("bindings") if isinstance(anatomy, dict) else None

    # THE CLAIM SWEEP RUNS BEFORE THE TABLES GATE, DELIBERATELY. It reads the
    # anatomy, not the tables, so gating it on `if not tables` would silently
    # disable it for a paper that reports everything in prose or figures --
    # exactly the class of paper whose claims are hardest to check by other
    # means, and exactly the "capability present, never invoked" failure this
    # codebase keeps rediscovering.
    # A PIPELINE TOOLSET SCOPES THE HARNESS TOO (`enabled`, None = every
    # sweep). A one-tool experiment that still ran the duplication and
    # sd_range sweeps would hand the adjudicator checks the run was configured
    # without. The claim sweep has no registry tool of its own, so a restricted
    # toolset leaves it off; each skipped sweep says so by name.
    def _on(tool: str) -> bool:
        return enabled is None or tool in enabled

    claims = _sweep_claims(findings) if enabled is None else None

    tables = paper_tables(paper_dir, include_supplements=True)
    if not tables:
        # Silence about TABLES is still the right answer -- see the docstring --
        # but not about claims, when there were claims to judge.
        if claims and claims.get("n_interpretations"):
            return {"n_tables": 0, "claims": claims,
                    "n_accusatory": claims.get("n_contradictions", 0),
                    "accusatory": [r for r in claims.get("results", [])
                                   if r.get("severity") == "suspicious"],
                    "why": ("This paper has no enumerable tables, so the "
                            "harness table sweeps did not run. The claim sweep "
                            "reads the anatomy and did.")}
        return None

    dup = (sweep_duplication(tables) if _on("detect_duplication")
           else _not_enabled("detect_duplication"))
    sdr = (sweep_sd_range(tables, variables, bindings) if _on("check_sd_range")
           else _not_enabled("check_sd_range"))
    # THE GRIM SWEEP, the one sweep whose failures ARE filed (see the module
    # docstring and `grim_harness.finding_rows`). Its premises come from the
    # tools agent's `declare_table` calls, read back from the ledger; without
    # any, it still checks what needs no declaration (printed n (%) cells).
    grim = None
    if _on("grim_check") or _on("grim_percentage"):
        from . import grim_harness as _gh
        decls, declared_vars = _gh.declarations_from_ledger(ledger)
        try:
            from .extraction.jats import paper_text as _paper_text
            text = _paper_text(paper_dir)
        except Exception:  # noqa: BLE001
            text = None
        grim = _gh.sweep_grim(tables, decls,
                              _gh.merge_variables(declared_vars, variables),
                              paper_text=text)
        grim["n_declarations"] = len(decls)
    else:
        grim = _not_enabled("grim_check")
    out = {
        "n_tables": len(tables),
        "duplication": dup,
        "sd_range": sdr,
        "grim": grim,
        "claims": claims,
        "why": (
            "These checks were aimed by the harness, not by the model: every "
            "eligible target in the paper's tables was enumerated and checked. "
            "That makes their coverage identical from run to run, which the "
            "model-aimed checks are not -- two runs of this pipeline on one "
            "paper overlapped on 0 of 10 model-aimed targets."),
    }
    if enabled is not None:
        # SAY WHAT DID NOT RUN, in the sentence the adjudicator reads. "Every
        # eligible target was checked" over two disabled sweeps is a coverage
        # claim this run cannot make.
        skipped = [name for name, ran in (
            ("detect_duplication", _on("detect_duplication")),
            ("check_sd_range", _on("check_sd_range")),
            ("grim sweep", _on("grim_check") or _on("grim_percentage")),
            ("claim sweep", False)) if not ran]
        out["not_run"] = skipped
        ran = [n for n in ("detect_duplication", "check_sd_range", "grim sweep")
               if n not in skipped]
        out["why"] = (
            "This run's pipeline restricts the toolset. Harness sweeps run: "
            + (", ".join(ran) or "none")
            + ". NOT run (tool not enabled in this pipeline): "
            + ", ".join(skipped)
            + ". Their absence is not a pass.")
    flagged = [r for r in sdr["results"] if str(r.get("severity")) in ACCUSATORY]
    if str(dup.get("severity")) in ACCUSATORY:
        flagged.append({"tool": "detect_duplication",
                        "severity": dup.get("severity")})
    flagged += [r for r in (claims or {}).get("results", [])
                if r.get("severity") == "suspicious"]
    out["n_accusatory"] = len(flagged)
    out["accusatory"] = flagged
    return out
