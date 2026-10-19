"""Layer 0 of the scaffold: what we READ, before anything is interpreted.

Everything a later pass says about the paper points back into this layer: an
offset into `text`, a cell in `tables`, a caption in `figures`. It is built from
the pipeline's own machinery wherever that machinery exists --

  * text        `docling_tables.cached_text` (the canonical body text), then
                the symbol-font repairs from `fontaudit`, every one logged --
                and, appended under a heading naming each file, the running
                prose of every readable SUPPLEMENT, because a supplement is not
                a second-class input (Greg, 2026-09-06) and its paragraphs were
                being served to nobody;
  * sections    `sections.map_sections`, plus a finer `role` (abstract, methods,
                results ...) read from the headings, because numeral accounting
                needs to say WHERE a residual number sits;
  * tables      `prepass.paper_tables` -- the single walker, so the scaffold's
                cells are the same cells the register would see;
  * numerals    `numerals.index` over the repaired text -- the exhaustive floor
                that the completeness measure is computed against;

-- and from two small readers of its own: figure captions (docling drops figure
artwork to `<!-- image -->` and keeps the caption paragraph) and supplement
references (`Supplementary Table S1`), because nothing in the pipeline extracts
either as structure today.

WHAT THIS LAYER REFUSES TO DO: interpret. It records that the paper prints
`Figure 1` with panels a-k; it does not say what panel a shows. That is pass 3's
job, and keeping the two apart is what lets a reader check the reading against
the record.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

from .. import numerals as _numerals
from .. import prepass as _prepass
from .. import sections as _sections
from ..extraction import docling_tables as _dl
from ..extraction import jats as _jats
from ..extraction.jats import paper_text_with_source as _paper_text_with_source
from ..repairs import RepairLog
from . import fontaudit as _fa
from . import reconstruct as _recon

#: Finer-than-`sections.kind` role for a heading, used only for ACCOUNTING --
#: where a residual numeral sits. Unrecognised headings inherit the role of the
#: heading before them (a Methods subsection is Methods); the first heading with
#: no predecessor is `front`.
_ROLE_RULES: tuple[tuple[str, str], ...] = (
    (r"^abstract\b|^summary\b", "abstract"),
    (r"^introduction\b|^background\b", "introduction"),
    (r"^(materials? and )?methods?\b|^experimental procedures|^subjects and methods", "methods"),
    (r"^statistical analys", "methods"),
    (r"^results?\b|^findings\b", "results"),
    (r"^discussion\b|^conclusions?\b|^general discussion", "discussion"),
    (r"^(funding|acknowledge?ments?|references?|bibliography|conflicts?|disclosure|"
     r"author contributions?|supplementary|supporting information|data availability)", "back"),
)

#: A figure caption, in the two shapes the pipeline's own readers write.
#:
#: THE BRACKETED FORM IS THE XML RUNG'S, and it is why four of the six papers
#: prepared on 2026-09-07 reported ZERO figures while their XML declared 3, 7,
#: 7 and 1. `jats._fig_block` writes `[{label}: {caption}]` with the
#: publisher's own `<label>` inside, so the line begins with `[` and the label
#: arrives as `Figure 1.` (Cambridge), `Fig. 1` (Nature), `FIGURE 1`
#: (Frontiers) or `Figure.` (JAMA, for an article with exactly one figure).
#: A rule anchored on a line starting `Figure N` matches none of them, and
#: every figure record the account carried existed only because the PMC image
#: fetch had run -- a caption recovered over the network from a file we hold.
#:
#: THE UNNUMBERED LABEL IS ACCEPTED ONLY INSIDE THE BRACKETS. `Figure.` is a
#: real label and a paper prints it, but so does a sentence beginning
#: `Figure: ...`; the bracket is the renderer's own delimiter and is positive
#: evidence that this line is a caption rather than prose. The plain form
#: below therefore still demands a number, exactly as before.
_FIGURE_CAPTION = re.compile(
    r"(?m)^(?:"
    r"\[(?P<blabel>(?:Figure|FIGURE|Fig\.)\s*(?P<bnum>\d+)?\.?)\s*:\s*(?P<bcap>.+?)\]\s*$"
    r"|(?P<label>Figure|Fig\.)\s+(?P<num>\d+)[.:]?\s+(?P<cap>.+)$"
    r")")
_PANEL_MARKER = re.compile(r"\(([a-z])(?:\s*[-–]\s*([a-z]))?\)")
_TABLE_CAPTION = re.compile(r"(?m)^(Table\s+(\d+))[.:]?\s+(.+)$")


def _sha(data: str | bytes) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def _article_pdf(paper_dir: Path) -> Path | None:
    pdfs = sorted(paper_dir.glob("*.pdf"))
    return pdfs[0] if len(pdfs) == 1 else None


def _roles_for(secs: list[dict]) -> list[dict]:
    """Attach `role` to each section from `sections.map_sections`."""
    out = []
    current = "front"
    for s in secs:
        name = s["name"]
        role = None
        for pat, r in _ROLE_RULES:
            if re.search(pat, name):
                role = r
                break
        if role is None:
            # A Results subsection heading is unrecognisable by name ("IGF-II
            # enhances ..."); it inherits. But the block before Introduction
            # that holds the title, authors and abstract is `front`, and the
            # abstract inside it is recovered by `abstract_span` below.
            role = current
        current = role
        out.append({**s, "role": role})
    return out


def figure_captions(text: str) -> list[dict]:
    """Every `Figure N ...` caption paragraph, with its panel letters.

    Panels are read from `(a)`, `(b–e)` markers in the caption. A caption that
    names none is one panel. Offsets are into `text`.
    """
    figs: list[dict] = []
    for m in _FIGURE_CAPTION.finditer(text):
        bracketed = m.group("bcap") is not None
        raw_num = m.group("bnum") if bracketed else m.group("num")
        num = int(raw_num) if raw_num else None
        # THE CAPTION IS WHAT THE PAPER PRINTED, WITHOUT THE RENDERER'S
        # BRACKETS. They are `_fig_block`'s delimiter, not the publisher's
        # punctuation, and a caption ending `]` reads as a typo to anyone
        # checking a figure record against the article.
        caption = (f"{m.group('blabel')}: {m.group('bcap')}" if bracketed
                   else m.group(0)).strip()
        letters: list[str] = []
        for pm in _PANEL_MARKER.finditer(caption):
            a, b = pm.group(1), pm.group(2)
            if b and ord(b) > ord(a):
                letters += [chr(c) for c in range(ord(a), ord(b) + 1)]
            else:
                letters.append(a)
        seen: list[str] = []
        for l in letters:
            if l not in seen:
                seen.append(l)
        # NO NUMBER IS INVENTED for a paper that printed none. `Figure.` is
        # the label, and it is what the join below and the account both key on.
        label = f"Figure {num}" if num is not None else " ".join(m.group("blabel").split())
        figs.append({"id": f"figure:{num if num is not None else label}", "label": label,
                     "caption": caption, "panels": seen, "n_panels": max(1, len(seen)),
                     "start": m.start(), "end": m.end(),
                     "values_readable_from_text": False})
    return figs


def _figure_key(label: Any) -> Any:
    """What identifies a figure across two readings of one paper: its NUMBER
    when it printed one, and otherwise its label.

    `Fig. 2` in the XML and `Figure 2` in the PMC manifest are one figure and
    the number says so; `Figure.` -- JAMA's label for a single-figure article
    -- carries no digit, and keying on the number alone filed the caption and
    its own fetched image as two figures on a paper that prints one.
    """
    m = re.search(r"(\d+)", str(label or ""))
    return int(m.group(1)) if m else " ".join(str(label or "").lower().split())


def merge_pmc_figures(figs: list[dict], manifest: dict | None) -> list[dict]:
    """The fetched figure images (`pmc_figures/manifest.json`) joined onto the
    caption-derived figure list by figure number; a fetched figure with no
    caption in the text becomes a figure record of its own. Each carries
    `image` (the file name under `pmc_figures/`) and `image_status`, so the
    account can say which figures exist as images and which do not -- the
    first step toward reading values off them (Greg, 2026-09-06), and
    nothing more: no value is read here."""
    if not manifest:
        return figs
    by_key: dict[Any, dict] = {}
    for f in figs:
        by_key.setdefault(_figure_key(f.get("label")), f)
    out = list(figs)
    for mf in manifest.get("figures") or []:
        key = _figure_key(mf.get("figure_label"))
        rec = by_key.get(key) if key != "" else None
        if rec is None:
            rec = {"id": f"figure:{key if key != '' else mf.get('id')}",
                   "label": mf.get("figure_label") or str(mf.get("id")),
                   "caption": mf.get("caption") or "", "panels": [], "n_panels": 1,
                   "start": None, "end": None, "values_readable_from_text": False}
            out.append(rec)
            if key != "":
                by_key[key] = rec
        rec["image"] = mf.get("file")
        rec["image_status"] = mf.get("status")
        rec["image_source"] = manifest.get("source")
    return out


_LABEL_NUMBER = re.compile(r"(?:^|\s|::\s*)(?:e?Table|TABLE)\s*(\d+)\s*$", re.I)
_WRAP_ID_NUMBER = re.compile(r"^(?:tab|table|t)[^0-9]*(\d+)$", re.I)


def printed_table_number(walked: dict) -> int | None:
    """The number the PAPER prints on this table, or None.

    FROM THE LABEL, NEVER FROM THE POSITION. The document layer numbered tables
    by their order in the walk, which is the order the publisher's markup lists
    them in -- and 10.1186/s40337-024-00968-3 lists `Tab5` before `Tab4`. Its
    fourth `<table-wrap>` was therefore recorded as "Table 4", so
    `context_for` served the reading of the paper's Table 5 the sentences that
    cite its Table 4: the caption is the paper's own and was right, and the
    passages explaining what the columns mean were another table's.

    The label is the publisher's own `<label>` text and is tried first; the
    wrap id (`Tab5`) is the fallback, because a publisher who omits the label
    still numbers the anchor. Neither is invented: a table with no number in
    either is reported as unnumbered and the caller falls back to position and
    says so.
    """
    m = _LABEL_NUMBER.search(" ".join(str(walked.get("label") or "").split()))
    if m:
        return int(m.group(1))
    m = _WRAP_ID_NUMBER.match(str(walked.get("table_id") or "").strip())
    return int(m.group(1)) if m else None


def table_captions(text: str) -> dict[int, dict]:
    """`{table_number: {caption, start, end}}` from `Table N ...` lines."""
    out: dict[int, dict] = {}
    for m in _TABLE_CAPTION.finditer(text):
        num = int(m.group(2))
        # The first occurrence that reads like a caption (title case, no verb
        # phrase like "in Table 1") wins; a body reference "as shown in Table 1"
        # never starts a line with the label, so line-anchoring suffices.
        out.setdefault(num, {"caption": m.group(0).strip(), "start": m.start(),
                             "end": m.end()})
    return out


def supplement_references(text: str, paper_dir: str | Path | None = None) -> list[dict]:
    """Every supplementary item the paper depends on, with a context.

    DELEGATES TO `supplements.classify_mentions`. This function used to carry
    its own regex for the single `Supplementary <kind>` style, which was blind
    to the eight others that module already knew -- JAMA `eTable 1`, the bare
    `Table S1` style, BMC `Additional file 1`, `Supporting Information`. MEASURED
    over 105 corpus papers: 71 cite a supplement and the local regex saw none of
    them on 32, so the scaffold reported "no supplements referenced" for a paper
    citing 76. It also lost that module's two hard-won rules -- an appendix
    PRINTED in the paper is not a supplement we lack, and a sentence DENYING a
    supplement ("no supplementary material is provided") is not a citation of
    one. Both are recorded there with the papers that forced them.

    `available` is deliberately THREE-VALUED, and never True. We can prove that
    a directory holds no supplement file at all; we cannot prove that the docx
    on disk is the thing "Table S3" names. So: False when the directory holds
    nothing, None (unknown) when it holds something, and the files we do hold
    are reported once at the document level. Asserting per-label coverage would
    supply a premise from a position rather than from evidence.
    """
    from .. import supplements as _supp
    mm = _supp.classify_mentions(text or "")
    held: list[str] = []
    if paper_dir is not None:
        try:
            inp = _supp.classify_inputs(paper_dir)
            held = list(inp.get("supplements") or []) + list(inp.get("datasets") or [])
        except Exception:
            held = []
    available = None if held else False
    seen: dict[str, dict] = {}
    for m in mm["cited"]:
        label = " ".join(str(m["text"]).split())
        e = seen.setdefault(label.lower(), {
            "label": label, "style": m["style"], "n_references": 0,
            "first_context": m["context"], "available": available,
            "files_held": held, "denied": False})
        e["n_references"] += 1
    for m in mm["denied"]:
        label = " ".join(str(m["text"]).split())
        e = seen.setdefault(label.lower(), {
            "label": label, "style": m["style"], "n_references": 0,
            "first_context": m["context"], "available": available,
            "files_held": held, "denied": True})
        e["denied"] = True
    return list(seen.values())


#: The heading `jats.references_markdown` writes when the reference list is
#: appended to a paper's text. Matched EXACTLY, and only as the last such
#: heading in the document, because it is our own writing and not a guess.
_REFERENCES_MARKER = "\n\n# References\n"


def _split_references(text: str) -> tuple[str, dict]:
    """`(body, {boundary, n_chars, share, how})` -- the served body without the
    bibliography, and what was taken off it.

    WHY THIS IS NOT `references.split`. That function DETECTS a reference list
    in a text layer, and on a two-column PDF it strands real body prose past
    its cut (measured on six PNAS papers, 2026-09-01) -- which is why the
    boundary was never moved there. Here there is nothing to detect: on the XML
    rung `extract_xml_text_with_tables` APPENDS the reference list itself,
    under a heading it writes, so the cut is exact and a text that does not
    carry that heading is not cut at all.

    WHY IT IS CUT. The `<ref-list>` is markup: a list of other papers'
    titles, journals, years, volumes and page ranges. On the meta-analysis
    (10.1017/s0033291723003501) it is 49,093 of 92,333 characters -- 53% of
    everything the passes are served, and, at $0.10 per 1,000 characters, more
    than half the cost of reading the paper. Its numerals were also in the
    floor, where 42% of unclassified numerals were measured to be reference
    debris. The references remain available: they are written beside the body
    as `body.references.md`, and the reference RECORDS are structure the
    extractor already returns.
    """
    out = {"boundary": None, "n_chars": 0, "share": 0.0, "how": "no_reference_block",
           "text": ""}
    cut = (text or "").rfind(_REFERENCES_MARKER)
    if cut == -1:
        return text, out
    out.update({"boundary": cut, "n_chars": len(text) - cut, "how": "appended_heading",
                "share": (len(text) - cut) / len(text) if text else 0.0,
                "text": text[cut:]})
    return text[:cut], out


def supplement_figures(paper_dir: str | Path) -> list[dict]:
    """Every picture embedded in a Word supplement, as an inventory.

    AN INVENTORY, NOT A READING, and it is kept apart from the article's
    figures for that reason: nothing here is served to a pass, no value is read
    from any of these images, and none of them is a figure the ARTICLE
    declares. What it buys is that a file we hold and cannot read stops being
    indistinguishable from a file that is not there --
    10.3389/fnins.2022.843105 puts its supplementary Tables S1 and S2 into the
    .docx as PNGs, so the account said that supplement had three tables when it
    prints five, and two of them are pixels.
    """
    from .. import supplements as _supp
    from ..extraction import supplements_read as _sr
    base = Path(paper_dir)
    out: list[dict] = []
    try:
        names = list(_supp.present_files(base) or [])
    except Exception:                                     # noqa: BLE001
        return out
    for name in names:
        path = base / name if not Path(name).is_absolute() else Path(name)
        if path.suffix.lower() != ".docx":
            continue
        for im in _sr.docx_images(path):
            out.append({"id": f"supplement_figure:{path.name}:{im['index']}",
                        "kind": "supplement_figure",
                        "label": f"{path.name} :: image {im['index']}",
                        "supplement_file": path.name, "index": im["index"],
                        "image": im["name"], "format": im["format"],
                        "n_bytes": im["n_bytes"], "order": im["order"],
                        "image_status": "embedded_in_docx",
                        # A picture may be a figure or a table drawn as one, and
                        # nothing here opens it to find out. Saying which would
                        # be a reading.
                        "is_figure_or_table": "unknown",
                        "values_readable_from_text": False})
    return out


def _table_span(text: str, cells: list[dict]) -> tuple[int, int] | None:
    """One rule for both floors -- see `numerals.table_span`."""
    return _numerals.table_span(text, cells)


def page_anchors(pdf_path: Path, text: str) -> tuple[list[dict], list[str]]:
    """`[{page, offset}]` -- where each PDF page begins in the docling text.

    Docling keeps reading order but drops page boundaries; a reader verifying a
    value needs the PAGE. Each page's own lines (long ones, not page furniture
    that repeats across pages) are tried as anchors until one locates in the
    text at an offset past the previous page's. A page that cannot be anchored
    is reported, and its offsets fall to the page before -- a stated
    imprecision rather than a wrong number.
    """
    problems: list[str] = []
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        return [], [f"page anchors: could not open {pdf_path.name}: {type(exc).__name__}: {exc}"]
    from .bind import locate  # local import: bind imports nothing from here at module load
    pages_lines: list[list[str]] = []
    with doc:
        for page in doc:
            lines = [l.strip() for l in page.get_text("text").splitlines() if len(l.strip()) >= 30]
            pages_lines.append(lines)
    counts: dict[str, int] = {}
    for lines in pages_lines:
        for l in set(re.sub(r"\d+", "#", l) for l in lines):
            counts[l] = counts.get(l, 0) + 1
    anchors: list[dict] = []
    prev = -1
    for pno, lines in enumerate(pages_lines, start=1):
        found = None
        for l in lines:
            if counts.get(re.sub(r"\d+", "#", l), 0) > 1:
                continue          # furniture: repeats on other pages
            probe = l if len(l) <= 60 else l[:60]
            span = locate(probe, text)
            if span and span[0] > prev:
                # Back up to the start of the docling line: PyMuPDF splits
                # `Figure 1` from its caption text, docling joins them, and the
                # page must begin where the joined line begins.
                found = text.rfind("\n", 0, span[0]) + 1
                if found <= prev:
                    found = span[0]
                break
        if found is None:
            problems.append(f"page {pno}: no line of it could be located in the text; its "
                            "offsets are attributed to the previous page")
            continue
        anchors.append({"page": pno, "offset": found})
        prev = found
    return anchors, problems


def section_at(sections: list[dict], offset: int | None) -> str | None:
    """The heading of the section containing `offset`, or None.

    THE LOCATION HANDLE WHEN THERE ARE NO PAGES. A PDF source gives every
    element a page; publisher XML and HTML have no pages at all, so the
    account printed `p.?` on every row of the first JATS run. A section
    heading is what a reader of the web version navigates by.
    """
    if offset is None:
        return None
    for s in sections or []:
        if s.get("start", 0) <= offset < s.get("end", 0):
            name = " ".join(str(s.get("name") or "").split())
            return name or str(s.get("kind") or "") or None
    return None


def page_at(pages: list[dict], offset: int | None) -> int | None:
    """The PDF page an offset falls on, from `page_anchors`; None when unknown."""
    if offset is None or not pages:
        return None
    page = None
    for a in pages:
        if a["offset"] <= offset:
            page = a["page"]
        else:
            break
    return page


#: The line that separates the article from a supplement in the served text.
#: A MARKDOWN HEADING, deliberately: `sections.map_sections` reads headings and
#: nothing else, so a delimiter that is not one leaves the whole supplement
#: inside whatever section the article ended in -- which on an XML paper is the
#: reference list, whose `role` is `back`, and `back` is what `bind` and
#: `linear.chunks` exclude. The delimiter has to be a heading or the text is
#: served and then thrown away by the next stage.
SUPPLEMENT_DELIMITER = "\n\n## SUPPLEMENT: {file}\n\n"


def build(paper_dir: str | Path, glyph_map: dict | None = None,
          render_png: bool = True, reconstruct_model: str | None = None,
          recon_dir: str | Path | None = None,
          serve_supplement_text: bool = True,
          serve_protocol_text: bool = False,
          allow_unextracted_supplements: bool = False) -> dict[str, Any]:
    """The document layer for one paper directory.

    `glyph_map` is the human-verified `{font: {char: intended}}` table for THIS
    paper's symbol fonts (see `fontaudit`). Absent, the audit still runs and
    every suspect is reported as unrepaired -- the text is served as docling
    wrote it, and the report says so.

    `serve_supplement_text` appends each readable supplement's running prose to
    the text the passes read, under a heading naming its file, and indexes it
    into the same numeral floor. Greg, 2026-09-06: "the supplements/repos aren't
    'second-class citizens' in the context of the analysis. They are as
    important as the main text, and should be presented to the models in this
    fashion." It is a parameter (and `--no-supplement-text`) only so the two can
    be measured against each other, not because either is a preference.

    `serve_protocol_text` is the one exception, and it is OFF by default. A
    supplement `supplements.classify_role` calls a `protocol` is a regulatory
    document: its prose is the sponsor's procedures rather than the study's
    results, and on 10.1038/s41392-026-02904-0 it is 194,792 characters against
    the article's 48,743. Its TABLES are walked and counted whatever this says.

    Fails loudly on a missing text: a scaffold built on an empty body would read
    as a paper with nothing in it. It fails the same way, and for the same
    reason, on a supplement nobody has extracted -- see
    `allow_unextracted_supplements`.
    """
    base = Path(paper_dir)
    base = base if base.is_dir() else base.parent
    problems: list[str] = []

    # THE BEST AVAILABLE SOURCE, NOT ALWAYS THE PDF. This function used to
    # demand `docling_tables.cached_text` and raise without it -- so on a paper
    # carrying publisher XML it refused to run at all, while the marked-up truth
    # sat unread in the same directory. MEASURED over 105 corpus paper
    # directories: the ladder in `jats._derive_paper_text` chooses
    # `xml_publisher` for 99 and `pdf` for 6. The scaffold could not read 94% of
    # the corpus, and every conversion defect it did surface came from the
    # remaining 6%.
    #
    # Publisher XML wins because there is no font layer to corrupt: no `x`
    # rendered as a hyphen, no symbol font reporting `mu` as `m`, no lost minus
    # sign. `xml_provenance` already draws the line this relies on -- publisher
    # markup is the marked-up truth, a converter's XML only ever an extraction.
    #
    # THE PDF RUNG DELIBERATELY DOES NOT USE THE LADDER'S OWN PDF READER. That
    # rung is pdfplumber, added so the supplement gate could see a PDF-only
    # paper at all; it inlines no tables and the glyph audit, the repair log and
    # the page anchors below were all built and validated against docling's
    # text. Swapping readers here would trade a known reader for a different one
    # on the exact papers that need the most care. So: ladder for anything
    # better than a PDF, the existing docling path otherwise -- and Mistral
    # belongs on THIS rung, ahead of docling, once an extraction exists for the
    # paper (`mistral_tables.read_cache`), because a pixel reading cannot
    # inherit a font-map defect that the text layer's own characters conceal.
    ladder_text, ladder_source = _paper_text_with_source(base)
    pdf = _article_pdf(base)
    if ladder_source and ladder_source != "pdf" and (ladder_text or "").strip():
        text = ladder_text
        text_channel = ladder_source
    else:
        if pdf is None:
            raise FileNotFoundError(
                f"{base} has no better-than-PDF source and no article PDF")
        text, why = _dl.cached_text(pdf)
        if not text:
            raise RuntimeError(f"no docling text for {pdf.name}: {why}. Run "
                               "`metascience extract-tables` on the directory first.")
        text_channel = "docling cached_text"
    original_text = text
    original_sha = _sha(original_text)

    # ---- symbol-font audit and logged repairs ---------------------------------
    # ONLY FOR TEXT READ OUT OF A PDF. The audit asks which glyphs a PDF's fonts
    # declare without a usable Unicode mapping; markup has no font layer, so on
    # an XML-sourced paper there is nothing for it to be right or wrong about,
    # and running it would report the PDF's fonts as if they had produced the
    # text we are actually serving.
    pdf_is_the_text = text_channel == "docling cached_text"
    audit = _fa.audit(pdf) if (pdf_is_the_text and pdf is not None) else {
        "fonts": [], "suspects": [], "n_suspects": 0, "n_pages": None,
        "skipped": f"text came from {text_channel}, which has no font layer"}
    if audit.get("error"):
        problems.append(audit["error"])
    repair_log = RepairLog(paper_id=base.name, original_sha256=original_sha,
                           original_source=text_channel)
    applied = {"n_applied": 0, "unmapped": [], "unlocated": []}
    if glyph_map:
        applied = _fa.apply_glyph_map(text, audit, glyph_map)
        text = applied["text"]
        for r in applied["repairs"]:
            repair_log.add(r)
    else:
        applied["unmapped"] = [{"font": s["font"], "char": s["char"], "page": s["page"],
                                "line": s["line"].strip()[:100]}
                               for s in audit.get("suspects", [])]
    # ---- the reference list is structure, not body --------------------------
    # It is cut AFTER the repairs and BEFORE anything reads an offset: the
    # block sits at the end of the text, so removing it moves no offset in
    # front of it. `original_text` deliberately keeps it -- `original_sha256`
    # is what `repairs` pins a declaration to, and it must go on naming what
    # the ladder returned.
    text, references = _split_references(text)
    if references["boundary"] is not None:
        problems.append(
            f"references: {references['n_chars']:,} characters of reference list were cut from "
            f"the served body at offset {references['boundary']:,} ({references['share']:.0%} of "
            "the text the ladder returned). They are a bibliography, not the paper's prose, and "
            "the numerals they carry are counted separately below rather than dropped")

    render = {"path": None, "n_lines": 0, "error": None}
    if render_png and audit.get("suspects") and pdf_is_the_text:
        out_png = base / "scaffold" / "font_suspects.png"
        render = _fa.render_suspects(pdf, audit, out_png)
        if render.get("error"):
            problems.append(render["error"])

    # ---- the tables, and the supplements' own prose ----------------------------
    # WALKED BEFORE THE SECTIONS ARE MAPPED, because the walk is also where the
    # supplements are read, and their prose joins the text the sections are
    # mapped over. `paper_tables` needs nothing from the text.
    walked = _prepass.paper_tables(base, include_supplements=True)
    problems += [f"tables: {p}" for p in (getattr(walked, "problems", None) or [])]
    supplement_texts = list(getattr(walked, "supplement_texts", None) or [])
    # A SUPPLEMENT NOBODY HAS EXTRACTED IS A REFUSAL, NOT A ZERO. `extract_pdf`
    # reads the docling cache and deliberately never runs the extractor, so an
    # un-extracted supplement PDF comes back with no text and no tables --
    # shaped exactly like a supplement that has neither, and the account then
    # says the paper has a supplement with nothing in it. That sentence is OUR
    # gap wearing the paper's clothes, and it is the failure this codebase
    # exists to stop.
    #
    # The remedy is one command and it is named. `allow_unextracted_supplements`
    # exists so a caller who has read that sentence can proceed anyway, and the
    # state is then recorded rather than silent.
    unextracted = list(getattr(walked, "unextracted_supplements", None) or [])
    if unextracted and not allow_unextracted_supplements:
        raise RuntimeError(
            f"{len(unextracted)} supplement(s) of {base.name} have not been extracted, so their "
            f"contents are UNKNOWN: {', '.join(unextracted)}. Run "
            f"`metascience extract-tables {base}` first. Building the document anyway would "
            "serve 0 characters and 0 tables for each of them, which is indistinguishable from "
            "a supplement that has neither -- pass allow_unextracted_supplements=True "
            "(--allow-unextracted-supplements) to accept that, knowingly.")
    if unextracted:
        problems.append(
            "supplements: proceeding with " + ", ".join(unextracted) + " UNEXTRACTED "
            "(--allow-unextracted-supplements). Their contents are UNKNOWN: every count on "
            "this paper describes a paper missing those files, and nothing here can tell that "
            f"from a paper that never had them. `metascience extract-tables {base}` fixes it")
    walked = list(walked)

    # A SUPPLEMENT IS NOT A SECOND-CLASS INPUT (Greg, 2026-09-06). Its tables
    # already reached the floor through `index_table_cells`; its RUNNING PROSE
    # reached nothing at all -- it was not served to any pass and was in no
    # denominator, and the build said so in `problems` rather than fixing it.
    # `10.1111--jcpp.13879`'s supplement carries 47 distinct p values and no
    # table; on this paper the second supplement is a Data Sharing Statement
    # with no tables, so under the old build it existed for nobody.
    #
    # APPENDED, NEVER INTERLEAVED. The article's offsets must not move: every
    # value, quote and numeral id already located in it is a byte offset, and
    # inserting anything ahead of them would silently repoint all of them.
    #
    # AND NOT EVERY SUPPLEMENT'S PROSE. `supplements.classify_role` says what
    # kind of document each one is, and exactly one class has a consequence: a
    # trial PROTOCOL is a regulatory document whose prose is the sponsor's
    # procedures rather than the study's results. On
    # 10.1038/s41392-026-02904-0 that is 194,792 characters, four times the
    # article, about $19.50 of the $50.73 the paper's reading was priced at. Its
    # prose is served only on request; its TABLES are walked and counted like
    # any other supplement's, because a statistic is evidence wherever it lives
    # (Greg, 2026-08-27).
    article_text = text
    supplement_spans: list[dict] = []
    supplements_read: list[dict] = []
    from .. import supplements as _supp_mod
    for s in supplement_texts:
        s["role_record"] = _supp_mod.classify_role(s["file"], s["text"])
    if serve_supplement_text:
        for s in supplement_texts:
            role = s["role_record"]["role"]
            if role == "protocol" and not serve_protocol_text:
                supplements_read.append(
                    {"file": s["file"], "role": role, "role_basis": s["role_record"]["basis"],
                     "role_matched": s["role_record"]["matched"], "served": False,
                     "n_chars_available": s.get("n_chars_available") or len(s["text"]),
                     "n_chars_served": 0,
                     "why": ("its prose is a protocol, which is the sponsor's procedures rather "
                             "than the study's results; serve it with "
                             "--serve-protocol-supplements. Its tables are walked and counted "
                             "either way")})
                problems.append(
                    f"supplement {s['file']}: classified `protocol` from the title line "
                    f"{s['role_record']['matched']!r}; its "
                    f"{(s.get('n_chars_available') or len(s['text'])):,} characters of prose were "
                    "NOT served (--serve-protocol-supplements serves them). Its tables are walked "
                    "and counted regardless")
                continue
            head = SUPPLEMENT_DELIMITER.format(file=s["file"])
            heading_start, start = len(text), len(text) + len(head)
            text = text + head + s["text"]
            # `start` IS THE PROSE, NOT THE HEADING. The delimiter names the
            # file, and a supplement file name is full of digits
            # (`...2023.37679_supplementary_info_1_...`); indexing the heading
            # would put numerals in the floor that the paper never printed.
            avail = s.get("n_chars_available")
            avail = len(s["text"]) if avail is None else int(avail)
            supplement_spans.append({"file": s["file"], "heading_start": heading_start,
                                     "start": start, "end": len(text),
                                     "n_chars": len(s["text"]),
                                     # SERVED OF AVAILABLE, AS TWO NUMBERS AND A
                                     # RATIO. The reader's cap used to leave a
                                     # marker sentence inside the served text
                                     # and nothing else; a reader of the account
                                     # could not tell a supplement read whole
                                     # from one read to 12%.
                                     "n_chars_available": avail,
                                     "truncated": bool(s.get("truncated")),
                                     "served_of_available": (round(len(s["text"]) / avail, 4)
                                                             if avail else None),
                                     "role": s["role_record"]["role"],
                                     "role_basis": s["role_record"]["basis"],
                                     "role_matched": s["role_record"]["matched"]})
            supplements_read.append(
                {"file": s["file"], "role": s["role_record"]["role"],
                 "role_basis": s["role_record"]["basis"],
                 "role_matched": s["role_record"]["matched"], "served": True,
                 "n_chars_available": avail, "n_chars_served": len(s["text"]),
                 "why": f"role `{s['role_record']['role']}`; its prose is served"})

    # ---- sections, captions, supplements --------------------------------------
    secs = _roles_for(_sections.map_sections(text))
    # THE SUPPLEMENT'S OWN ROLE, STAMPED BY SPAN. `_ROLE_RULES` reads a heading
    # and a supplement's inner headings ("eTable 1. Respondents' ...") match
    # none of them, so each would INHERIT the role of the heading before it --
    # which, at the join, is the article's reference list, `back`. `back` is
    # what `bind.account_numerals` and `linear.chunks` exclude, so the prose
    # would have been served and then dropped from every count.
    for sec in secs:
        if any(sp["heading_start"] <= sec["start"] < sp["end"] for sp in supplement_spans):
            sec["role"] = "supplement"
    # THESE THREE READ THE ARTICLE, NOT THE WHOLE STRING. A supplement prints
    # its own `Table 1.` and `Figure 2.` lines and cites its own eTables; run
    # over the joined text they would invent article figures, overwrite an
    # article table's caption with a supplement's, and inflate the count of
    # references to a supplement. The article is a prefix of `text`, so every
    # offset they return is unchanged.
    figs = figure_captions(article_text)
    from ..image_plugin import ImagePluginUnavailable, load
    try:
        _read_pmc_manifest = load("image_forensics.pmc_figures").read_manifest
        figs = merge_pmc_figures(figs, _read_pmc_manifest(base))
    except ImagePluginUnavailable:
        problems.append("figures: pmc_figures manifest not read (the image analysis package is not installed)")
    except (OSError, ValueError) as exc:
        problems.append(f"figures: pmc_figures manifest unreadable ({type(exc).__name__}: {exc})")
    supp_figs = supplement_figures(base)
    if supp_figs:
        by_file: dict[str, int] = {}
        for f in supp_figs:
            by_file[f["supplement_file"]] = by_file.get(f["supplement_file"], 0) + 1
        problems.append(
            "supplement figures: "
            + "; ".join(f"{k} carries {v} embedded image(s)" for k, v in by_file.items())
            + " -- inventoried, not read. Some of them are TABLES drawn as pictures, and a "
              "table in an image contributes no cells to any count on this paper")
    tcaps = table_captions(article_text)
    supps = supplement_references(article_text, base)
    # PAGE ANCHORS ARE PDF GEOMETRY. An XML paper has no pages, and inventing
    # one would put a page number on a quote that was never printed on it.
    if pdf_is_the_text and pdf is not None:
        pages, page_problems = page_anchors(pdf, text)
        problems += page_problems
    else:
        pages = []
        problems.append(f"no page anchors: text came from {text_channel}, "
                        "which carries no page geometry")

    # ---- the paper's own identity, from <article-meta> when there is one ----
    # DETERMINISTIC WHERE IT CAN BE. The model was asked to read title, journal,
    # year and DOI off the text and printed `.  . DOI not stated` for a paper
    # whose XML carries all four. `jats.article_metadata` is scoped to
    # `<article-meta>` so a reference-list `<year>` cannot leak in; `bind`
    # prefers these fields and records any disagreement with the model's.
    front = None
    if str(text_channel).startswith("xml"):
        try:
            xp = _jats.find_xml(base)
            if xp is not None:
                meta = _jats.article_metadata(ET.parse(str(xp)).getroot())
                front = {k: meta.get(k) for k in ("title", "journal", "doi", "year", "volume",
                                                  "issue", "pages", "author_list")}
                front["source"] = "<article-meta>"
        except (OSError, ET.ParseError, ValueError) as exc:
            problems.append(f"front matter: <article-meta> could not be read ({type(exc).__name__}: {exc})")

    # ---- tables from the single walker ----------------------------------------
    # MODEL + IMAGE READING ABOVE THE WALKER (section 8n). Each article table
    # of an XML-sourced paper is rendered and read by a model; the walker's
    # cells are replaced ONLY when the walker verifies the reading conserved
    # them (see `reconstruct`). `reconstruct_model=None` reuses a cached
    # reconstruction and never calls a model, which is what `--no-llm` needs.
    if reconstruct_model is not None:
        # CONTEXT-FREE READING, for standalone measurement only. The pipeline
        # reads tables AFTER pass 2, in context (`__main__`), so the reader has
        # the citing passages and the declared vocabulary.
        _recon.reconstruct_tables(
            base, walked, Path(recon_dir) if recon_dir else base / "scaffold" / "tables",
            model=reconstruct_model, problems=problems)
    # THE SPAN IS SEARCHED IN THE ARTICLE ONLY, and a supplement table is
    # enumerated from its CELLS whether or not its own served text inlines it.
    # Two separate reasons, both measured on jamanetworkopen.2023.37679:
    #
    #   * `table_span` matches the first and last cell strings against any pipe
    #     row in the string it is given, and cells like `1.00` and `NA` are not
    #     distinctive. Over the joined text a supplement's table can match the
    #     ARTICLE's pipe rows and be recorded as already-in-the-floor when its
    #     numbers are nowhere in it.
    #   * docling's MARKDOWN of a supplement and docling's STRUCTURED GRID of
    #     the same tables do not agree. Letting the span rule hand those tables
    #     to the text lost 243 numerals the grid has and the markdown does not
    #     (36 `1.00` reference cells, 17 `0`) and gained 144 the markdown has
    #     and the grid does not: the supplement's own bucket 99 smaller and the
    #     whole floor 51 smaller (3,092 -> 3,041) for serving MORE text. The
    #     grid is the richer reading and it is what pass 3 is served, so the
    #     cells own the cells.
    #
    # The pipe rows of a served supplement are therefore set aside below rather
    # than counted: the same physical numbers, counted once, from the reading
    # that has more of them.
    tables: list[dict] = []
    for i, t in enumerate(walked, start=1):
        cells = list(t.get("cells") or [])
        span = (_table_span(article_text, cells)
                if t.get("source") != "supplement" else None)
        # THE NUMBER THE PAPER PRINTS, NOT THE POSITION IN THE WALK. A
        # supplement table keeps the positional number: its identity is its
        # FILE plus its number inside that file (`supplement_file`, and
        # `walker_label`, which is what `context_for` reads), and calling the
        # first supplement table "Table 6" of the article would be a worse
        # claim than calling it the sixth table walked.
        num = printed_table_number(t) if t.get("source") != "supplement" else None
        if num is None and t.get("source") != "supplement":
            problems.append(
                f"tables: {t.get('label') or t.get('table_id') or f'the {i}th table walked'} "
                "prints no number in its label or its id, so it is numbered by its position "
                "in the walk; if this publisher lists tables out of order, its caption and "
                "citing passages belong to another table")
        cap = tcaps.get(num if num is not None else i, {})
        row_labels: list[str] = []
        col_labels: list[str] = []
        for c in cells:
            rl, cl = c.get("row_label"), c.get("col_label")
            if rl and rl not in row_labels:
                row_labels.append(rl)
            if cl and cl not in col_labels:
                col_labels.append(cl)
        tables.append({
            "id": f"table:{i}", "label": f"Table {num if num is not None else i}",
            "walker_label": t.get("label"),
            "wrap_id": t.get("table_id"), "table_num": num or t.get("table_num") or i,
            # WHERE IT SAT IN THE WALK, kept beside the printed number because
            # they are different facts and one consumer needs each: `table:<i>`
            # is an index into this list, and `table_element`'s fallback --
            # "the nth `<table-wrap>`" -- is a position, not a label.
            "position": i,
            "table_number_from": ("label" if num is not None else "position"),
            # THE FILE A SUPPLEMENT TABLE CAME FROM, carried: without it the
            # reader cannot render the table (measured: both ajcp supplement
            # tables "not attempted: no file recorded" on 2026-09-06).
            "supplement_file": t.get("supplement_file"),
            # THE PAGE INSIDE THE SUPPLEMENT'S OWN FILE, which is not the same
            # kind of fact as `page` below: that one is a page of the ARTICLE
            # PDF, read off this text's page anchors, and a supplement's page
            # number printed in that field would be read as an article page by
            # every consumer of it (`bind` gives a table's page to every value
            # bound to the table). Kept under its own name so the reader that
            # draws a PDF supplement's page can find it, and nothing else can
            # mistake it. Measured: docling stamps a page on all nine
            # supplement tables of jamanetworkopen.2023.37679, and the document
            # layer was dropping all nine.
            "supplement_page": t.get("page") if t.get("source") == "supplement" else None,
            "caption": cap.get("caption") or t.get("caption"),
            "source": t.get("source"), "extractor": t.get("extractor"),
            "n_cells": len(cells), "row_labels": row_labels, "col_labels": col_labels,
            "sections": list(t.get("sections") or []),
            "footnotes": list(t.get("footnotes") or []),
            "n_header_rows": t.get("n_header_rows"),
            "header_rows": t.get("header_rows"),
            "text_span": list(span) if span else None,
            # AN ARTICLE PAGE, AND ONLY FROM ARTICLE TEXT. `pages` anchors the
            # ARTICLE PDF's pages in this string; a supplement's inlined table
            # now has a `text_span` too (its prose is served), and reading that
            # span against the article's anchors would return the article's last
            # page for a table printed in a different document. A supplement's
            # own page is `supplement_page` above.
            "page": (page_at(pages, span[0])
                     if (span and t.get("source") != "supplement") else None),
            "cells": cells,
            # THE READING BESIDE THE WALKER'S OWN CELLS, so a reader can see which
            # was used and why; `walker_cells` is the provenance of every
            # reconstructed value.
            "reconstruction": t.get("reconstruction"),
            "walker_cells": t.get("walker_cells") if (t.get("reconstruction") or {}).get("status") == "verified" else None,
            "entries": t.get("entries"),
            "reconstructed_column_labels": t.get("reconstructed_column_labels"),
        })

    # ---- the numeral floor ----------------------------------------------------
    # INDEXED PART BY PART, NOT OVER THE JOINED STRING. Three reasons, and each
    # one is a defect avoided rather than a preference:
    #   * the delimiter is not indexed at all, so a supplement's file name
    #     (`...2023.37679_supplementary_info_1_...`) contributes no numerals;
    #   * a row's `source` is decided by WHICH PART it was found in, which is
    #     evidence, rather than by a span comparison written twice;
    #   * with no supplement served the parts list is [article] and every row is
    #     byte-identical to the single-pass index, so `--no-supplement-text`
    #     restores the previous floor exactly.
    # `index` numbers a row `num:<offset>` and `linear.chunks` slices the served
    # text by that offset, so the offsets are shifted to the joined string and
    # the id rebuilt from the shifted offset -- unique because two parts cannot
    # occupy one offset.
    parts = [{"source": "article", "file": None, "start": 0, "end": len(article_text)}]
    parts += [{"source": "supplement", "file": sp["file"], "start": sp["start"], "end": sp["end"]}
              for sp in supplement_spans]
    rows: list[dict] = []
    n_set_aside = 0
    for part in parts:
        chunk = text[part["start"]:part["end"]]
        got = _numerals.index(chunk, tables_available=bool(tables))
        for r in got:
            r["offset"] += part["start"]
            r["end"] += part["start"]
            r["id"] = f"num:{r['offset']}"
            r["source"] = part["source"]
            if part["file"]:
                r["file"] = part["file"]
            r["role"] = ("supplement" if part["source"] == "supplement"
                         else next((s["role"] for s in secs
                                    if s["start"] <= r["offset"] < s["end"]), "front"))
        if part["source"] == "supplement":
            # THE SAME CELLS, COUNTED ONCE, FROM THE READING THAT HAS MORE OF
            # THEM (see the note above the table loop). A supplement's pipe rows
            # are the converter's markdown of tables that `index_table_cells`
            # enumerates from the structured grid below; counting both would
            # double every supplement cell in the denominator. The count of what
            # is set aside is reported, because a number removed without a
            # number beside it is the suppression this floor exists to prevent.
            aside = [r for r in got if r.get("class") == "table_cell"]
            n_set_aside += len(aside)
            got = [r for r in got if r.get("class") != "table_cell"]
        rows += got

    # THE SUPPLEMENT'S NUMBERS JOIN THE SAME DENOMINATOR. An article's own
    # tables are already in the floor because docling inlines them as pipe rows;
    # a supplement is a separate FILE that never enters `text`, so its numbers
    # were in no denominator at all. On Stern 2014 that was the difference
    # between 144 table cells and 2,638, with `n_total` unmoved at 876 -- a
    # completeness claim measured against a universe excluding the very table
    # the paper's Results section tells the reader to go and read.
    #
    # FROM THE WALKED TABLES, not a second read. `paper_tables` is the single
    # walker and `values.build_from_paper` says why ("a second walk is two
    # denominators"); re-reading the files here to enumerate them would be
    # exactly that.
    #
    # SUPPLEMENT PROSE IS IN, as of 2026-09-06, and it is what makes the span
    # rule below matter for supplements as well. A PDF supplement's text is
    # docling's, which INLINES its tables as pipe rows, so the same cells would
    # be counted twice -- once on a pipe row of the served text and once by
    # `index_table_cells` -- if the rule keyed on the source rather than on
    # whether the served text already holds the table.
    # KEYED ON WHETHER THE BODY ALREADY HOLDS THE TABLE, not on where it came
    # from. A table with a `text_span` is inlined in the text we just indexed --
    # docling's pipe rows -- so its numerals are already rows. A table without
    # one is not in the body at all: every supplement table, and EVERY table of
    # an XML-sourced paper, where the markup keeps tables in their own elements.
    # Measured on `10.1002--ajcp.70049` before this: 143 article table cells
    # contributing 0 to the floor.
    suppressed = _numerals.suppressed(text)
    for t in tables:
        if t.get("text_span"):
            continue
        origin = str(t.get("supplement_file") or t.get("label") or t.get("id"))
        src = "supplement" if t.get("source") == "supplement" else "article"
        cell_rows = _numerals.index_table_cells([t], origin, src)
        for r in cell_rows:
            r["role"] = "supplement" if src == "supplement" else "table"
        rows += cell_rows
        for cell in (t.get("cells") or []):
            suppressed += _numerals.suppressed(str(cell.get("raw") or ""))
    n_offbody = sum(1 for t in tables if not t.get("text_span"))
    if n_offbody:
        problems.append(
            f"numeral floor: {n_offbody} of {len(tables)} table(s) are not "
            "inlined in the article text, so their CELLS were enumerated directly")
    if n_set_aside:
        problems.append(
            f"numeral floor: {n_set_aside} numeral(s) on pipe rows of served supplement "
            "prose were set aside, not dropped -- they are the same cells the table "
            "walker enumerated from the structured grid, and are counted there")
    for sp in supplement_spans:
        if sp["truncated"]:
            # NAMED, WITH BOTH NUMBERS. This used to be a marker sentence inside
            # the served text and nothing else, so every count computed over the
            # supplement -- the floor, the coverage denominators, the cost --
            # described 12% of a file while reading as a fact about the whole.
            problems.append(
                f"supplement {sp['file']}: {sp['n_chars']:,} of {sp['n_chars_available']:,} "
                f"characters served ({sp['served_of_available']:.0%}); the reader's cap took "
                "the rest, so every count over this supplement's PROSE is a count over the "
                "part that was served. Its TABLES are unaffected -- they are enumerated from "
                "the extraction's own grids, not from this text")
    if not serve_supplement_text and supplement_texts:
        # A STATED ABSENCE. With the switch off the prose of these files is in
        # no denominator and served to no pass, which is exactly the state this
        # build had before 2026-09-06 -- said out loud rather than left to be
        # rediscovered.
        problems.append(
            "numeral floor: supplement running prose was NOT served or indexed "
            f"(--no-supplement-text): {', '.join(s['file'] for s in supplement_texts)}")

    # THE REFERENCE NUMERALS ARE COUNTED, NOT DROPPED. `n_total` moving is the
    # one thing this floor exists to make impossible to do quietly, so the
    # block that left the body is enumerated by the same enumerator and its
    # rows are reported beside the total, itemized by class. Body + set-aside
    # is exactly the total the uncut text produced.
    ref_rows = _numerals.index(references["text"], tables_available=bool(tables)) \
        if references["text"] else []
    for r in ref_rows:
        r["source"] = "references"

    floor = _numerals.tally(rows, suppressed)
    # BESIDE `n_total`, NEVER INSIDE IT -- the same treatment `tally` already
    # gives the enumerator's own refusals (`n_suppressed_letter_attached`), and
    # for the same reason: a number removed from a denominator has to be
    # visible as a number.
    floor["n_supplement_pipe_rows_set_aside"] = n_set_aside
    floor["n_reference_numerals_set_aside"] = len(ref_rows)
    # THE SAME RULE FOR A SUPPLEMENT WE CHOSE NOT TO SERVE. A protocol's prose
    # leaves the served text, so it leaves `n_total`; a denominator that moves
    # has to move visibly, and "we decided not to read this" is exactly the kind
    # of decision that must not be invisible in a coverage figure.
    withheld_rows = {
        r["file"]: len(_numerals.index(
            next(s["text"] for s in supplement_texts if s["file"] == r["file"]),
            tables_available=bool(tables)))
        for r in supplements_read if not r.get("served")}
    floor["n_withheld_supplement_numerals"] = sum(withheld_rows.values())
    floor["withheld_supplement_numerals_by_file"] = withheld_rows
    if withheld_rows:
        problems.append(
            "numeral floor: "
            + ", ".join(f"{v:,} numeral(s) of {k}" for k, v in withheld_rows.items())
            + " are counted here rather than in `n_total`, because that supplement's prose was "
              "not served. Its TABLES are in `n_total` as table cells, as they always were")
    floor["reference_numerals_by_class"] = dict(
        sorted(Counter(str(r.get("class") or "unclassified") for r in ref_rows).items()))
    if ref_rows:
        problems.append(
            f"numeral floor: {len(ref_rows):,} numeral(s) of the reference list are counted here "
            "rather than in `n_total` -- "
            + ", ".join(f"{k} {v}" for k, v in floor["reference_numerals_by_class"].items())
            + ". They are years, volumes and page ranges of OTHER papers; the body's total is "
              "the total of what this paper printed")

    doc = {
        "source": {"pdf": pdf.name if pdf else None,
                   "pdf_sha256": _sha(pdf.read_bytes()) if pdf else None,
                   "n_pages": audit.get("n_pages"), "text_channel": text_channel,
                   "original_text_sha256": original_sha, "text_sha256": _sha(text),
                   # `n_chars` IS THE STRING THE PASSES READ, article plus every
                   # supplement served. `n_chars_article` is beside it because
                   # `original_text` (and `body.original.md`) is the ARTICLE's
                   # pre-repair text and nothing else -- the repair log is about
                   # the article's font layer, and `original_text_sha256` is the
                   # article's, which is what `repairs` pins a declaration to.
                   "n_chars": len(text), "n_chars_article": len(article_text),
                   "supplement_text_served": bool(serve_supplement_text and supplement_spans),
                   "n_supplements_served": len(supplement_spans),
                   "n_chars_supplements": sum(sp["n_chars"] for sp in supplement_spans),
                   "n_chars_supplements_available":
                       sum(sp["n_chars_available"] for sp in supplement_spans),
                   "n_supplements_truncated":
                       sum(1 for sp in supplement_spans if sp["truncated"])},
        "supplement_spans": supplement_spans,
        # EVERY READABLE SUPPLEMENT, served or not, with the role that decided
        # it. A file whose prose we chose not to serve must be as visible as
        # one we did, or the choice is indistinguishable from a file we could
        # not open.
        "supplements_read": supplements_read,
        "unextracted_supplements": unextracted,
        "references": {k: v for k, v in references.items() if k != "text"},
        "references_text": references["text"],
        "text": text,
        "original_text": original_text,
        "font_audit": {"fonts": audit.get("fonts", []),
                       "suspects_by_glyph": _fa.suspect_summary(audit),
                       "n_suspects": audit.get("n_suspects", 0),
                       "n_repaired": applied["n_applied"],
                       "unmapped": applied["unmapped"], "unlocated": applied["unlocated"],
                       "render": render},
        "repairs": repair_log.to_dict(),
        "front": front,
        "sections": secs,
        "pages": pages,
        "tables": tables,
        "figures": figs,
        # KEPT APART FROM `figures`, deliberately. These are pictures inside a
        # supplement FILE, not figures the article declares; they are served to
        # no pass and read by nothing, and folding them into the article's
        # figure list would move every figure count in the account.
        "supplement_figures": supp_figs,
        "supplements_referenced": supps,
        "numerals": rows,
        "numeral_floor": floor,
        "problems": problems,
    }
    return doc


def save(doc: dict, out_dir: str | Path) -> dict[str, str]:
    """Write the layer to `out_dir`: the repaired text, the original, the JSON
    without the two texts (they are large and already on disk). Returns paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "body.repaired.md").write_text(doc["text"], encoding="utf-8")
    (out / "body.original.md").write_text(doc["original_text"], encoding="utf-8")
    # BESIDE THE BODY, NOT INSIDE IT. The reference list is cut from the served
    # text; it is not thrown away, and a reader checking a citation year against
    # the bibliography needs the file it was cut into.
    (out / "body.references.md").write_text(doc.get("references_text") or "", encoding="utf-8")
    slim = {k: v for k, v in doc.items()
            if k not in ("text", "original_text", "references_text")}
    (out / "document.json").write_text(json.dumps(slim, indent=1, ensure_ascii=False),
                                       encoding="utf-8")
    return {"text": str(out / "body.repaired.md"),
            "original": str(out / "body.original.md"),
            "references": str(out / "body.references.md"),
            "document": str(out / "document.json")}
