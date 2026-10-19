"""
Publisher XML full-text extraction (JATS / NLM, PMC article sets, Elsevier CALS).

Why this exists: a PDF extraction of a table collapses rows into blobs
(``'None 226150662 95.5(95.4-95.7) 96.2(95.7-96.7)'``), and a markdown pipe
table cannot express ``colspan``/``rowspan`` or a multi-row header at all. Both
destroy the value-to-column binding that GRIM/GRIMMER and every whole-table
tool depend on. This module goes XML -> dense rectangular cell grid directly,
with no markdown intermediate.

The output mirrors :mod:`forensic_metascience_ai_toolkit.extraction.pdf` key-for-key so the
existing chain is reused unchanged::

    extract_xml -> parse_table(grid) -> parse_cells_typed -> check_table

Every tag is matched by *local* name: namespaces vary by publisher and
hard-coded prefixes break on the next one.
"""

from __future__ import annotations

import json
import re
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Flavours
# ---------------------------------------------------------------------------

JATS = "jats"
PMC_SET = "pmc-set"
ELSEVIER = "elsevier-cals"
UNKNOWN = "unknown"

_TRUNCATION_NOTE = (
    "\n\n[TEXT TRUNCATED — call extract_xml again with first_section/"
    "last_section to fetch the remaining sections]"
)

# Sections that carry no checkable statistics and would swamp the budget.
_SKIP_SECTIONS = {"ref-list"}

# Inline elements whose text is kept verbatim (formatting only).
_TRANSPARENT = {
    "italic", "bold", "sc", "underline", "styled-content", "monospace",
    "roman", "sans-serif", "overline", "strike", "p", "x",
}


def _local(tag: Any) -> str:
    """Local name of an element tag, stripping any ``{namespace}`` prefix."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


#: Heading for prose the publisher gave no heading to. NAMED, not invented:
#: the stage prompts tell the model to write `location` as "Results, para 2",
#: so labelling this run "Methods" or "Results" because that is what it looks
#: like would put a fabricated citation in a forensic finding.
_UNSECTIONED_TITLE = "Body text (no section heading in the XML)"


def xml_flavour(root: ET.Element) -> str:
    """Identify which publisher XML dialect this document uses."""
    name = _local(root.tag)
    if name == "pmc-articleset":
        return PMC_SET
    if name == "article":
        return JATS
    if name == "full-text-retrieval-response":
        return ELSEVIER
    return UNKNOWN


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

# U+2212 MINUS SIGN. `tableparse._NUM` only accepts ASCII [-+], so a cell
# holding "−3.5" is silently unreadable today, and anything that later strips
# non-ASCII would flip the sign of a regression coefficient. En/em dash are
# deliberately NOT touched: "18–65" is a range, and `celltypes._INTERVAL_SEP`
# already reads it as one.
_TRUE_MINUS = "−"

# Space characters used as digit-group separators ("226 150 662"). These are
# unambiguous typographic grouping, unlike a plain ASCII space.
_NARROW_SPACES = "    "
_DIGIT_GROUP = re.compile(rf"(?<=\d)[{_NARROW_SPACES}](?=\d\d\d(?!\d))")
_OTHER_SPACES = re.compile(rf"[{_NARROW_SPACES}       ]")
_ZERO_WIDTH = re.compile("[​‌‍﻿]")


class _Counter(dict):
    """Tally of the character rewrites performed, surfaced in the result."""

    def bump(self, key: str, n: int = 1) -> None:
        if n:
            self[key] = self.get(key, 0) + n


#: DAMAGE THE EXTRACTOR ADDED, not something the paper printed. docling leaves
#: `&lt;` undecoded and older PDFs encode `=` as `¼`, so repairing them RESTORES
#: the paper's text rather than altering it -- which is why this belongs at the
#: reader, above every consumer, rather than inside one of them.
#:
#: MEASURED over the 305-paper cerebrolysin corpus: 265 papers (87%) carry an
#: HTML entity on 3,393 lines, of which 1,901 are `p &lt; <number>`. Every one
#: was a p-value that the model reading this text could not see, that no pattern
#: could match, and that statcheck -- whose entire job is comparing a reported p
#: against a recomputed one -- could not check.
#:
#: THE MARKDOWN PATH BYPASSED `_normalise` ENTIRELY. XML text goes through it
#: and gets its digit-group spaces, true minus and exotic whitespace repaired;
#: `body.md` was read raw. So every docling-extracted paper -- which is most of
#: them -- reached the model with damage the XML papers never had.
_ENTITY_REPAIRS = {"&lt;": "<", "&gt;": ">", "&le;": "\u2264", "&ge;": "\u2265",
                   "&amp;": "&", "&quot;": '"', "&apos;": "'", "&nbsp;": " "}
_ENTITY_RE = re.compile("|".join(re.escape(k) for k in _ENTITY_REPAIRS))

#: `n ¼ 68` is `n = 68`. Repaired only between a word or bracket and a digit,
#: where `¼` cannot mean one quarter.
_MOJIBAKE_EQ = re.compile(r"(?<=[\w\)\]])(\s*)\u00bc(\s*)(?=[-+.\d])")

#: `0 . 28` IS `0.28`. docling splits a decimal point off its digits in some
#: PDFs -- 1,995 occurrences across 80 papers of the heterogeneous Zotero
#: corpus -- and the damage is not merely cosmetic: an index over that text
#: reports TWO numbers where the paper printed one, so the floor's denominator
#: counts a value twice and its own share-judged falls for a reason that has
#: nothing to do with classification.
#:
#: A SPACE BEFORE THE DOT IS REQUIRED, which is what separates this from a
#: numbered list. `1. Text` has no space before the point and is left alone;
#: `1 . 5` cannot be anything but a broken decimal.
_SPLIT_DECIMAL = re.compile(r"(?<=\d)\s+\.\s*(?=\d)")


def repair_extraction_damage(text: str, counts: "_Counter | None" = None) -> str:
    """Undo what the extractor did to the paper's characters.

    Applied at the READER so every consumer sees the same text: the model, the
    quote haystack, the cell typer, statcheck and the enumerator. Repairing it
    in one consumer -- as `completeness` did first -- fixes the floor while
    leaving the FINDER reading mojibake, which is backwards.
    """
    if not text:
        return ""
    counts = counts if counts is not None else _Counter()
    n = len(_ENTITY_RE.findall(text))
    if n:
        text = _ENTITY_RE.sub(lambda m: _ENTITY_REPAIRS[m.group(0)], text)
        counts.bump("html_entity_decoded", n)
    n = len(_MOJIBAKE_EQ.findall(text))
    if n:
        text = _MOJIBAKE_EQ.sub(lambda m: f"{m.group(1)}={m.group(2)}", text)
        counts.bump("mojibake_equals_repaired", n)
    n = len(_SPLIT_DECIMAL.findall(text))
    if n:
        text = _SPLIT_DECIMAL.sub(".", text)
        counts.bump("split_decimal_rejoined", n)
    return text


def _normalise(text: str, counts: _Counter | None = None) -> str:
    """
    Collapse whitespace and repair characters that block numeric parsing.

    Elsevier XML is pretty-printed, so whitespace collapse is mandatory there.
    Every rewrite is counted so the operator can still see what the source
    looked like — nothing is changed silently.
    """
    if not text:
        return ""
    counts = counts if counts is not None else _Counter()

    n = len(_DIGIT_GROUP.findall(text))
    if n:
        text = _DIGIT_GROUP.sub("", text)
        counts.bump("digit_group_space_removed", n)

    if _TRUE_MINUS in text:
        counts.bump("true_minus_to_ascii", text.count(_TRUE_MINUS))
        text = text.replace(_TRUE_MINUS, "-")

    n = len(_ZERO_WIDTH.findall(text))
    if n:
        text = _ZERO_WIDTH.sub("", text)
        counts.bump("zero_width_removed", n)

    n = len(_OTHER_SPACES.findall(text))
    if n:
        text = _OTHER_SPACES.sub(" ", text)
        counts.bump("exotic_space_to_ascii", n)

    return " ".join(text.split())


_NUMERIC_TAIL = re.compile(r"[\d)\]]\s*$")
#: An exponent contains a DIGIT. Without that requirement `[\d.,]+` matches a
#: bare comma, and the separator between two footnote markers became an
#: exponent: `Patel[22]<sup>,</sup><sup>c</sup>` rendered `Patel[22]^,c`.
_NUMERIC_ONLY = re.compile(r"^[-+−]?[\d.,]*\d[\d.,]*$")

#: Unicode superscript forms. Uppercase is deliberately absent: Unicode has no
#: superscript C, F, Q, S, X, Y or Z, so mapping the rest would render `Aᴬ` and
#: `Cᶜ`-less inconsistently. A superscript is converted only when EVERY
#: character in it maps.
_SUPERSCRIPT_PLAIN = "0123456789+-=()abcdefghijklmnoprstuvwxyz"
_SUPERSCRIPT = dict(zip(
    _SUPERSCRIPT_PLAIN,
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ",
))


def _superscripted(inner: str) -> str | None:
    """`inner` as Unicode superscript characters, or None if it will not go.

    A `<sup>` used to be dropped to the baseline unless it followed a digit, so
    `kg/m<sup>2</sup>` came out `kg/m2` and `Serious adverse event<sup>1</sup>`
    came out `Serious adverse event1` -- in both cases a footnote marker or a
    unit exponent silently welded onto the text beside it. Raising it back to
    superscript keeps the distinction a reader (and a parser) needs.

    All-or-nothing: a marker rendered half-raised (`*ᵃ`) is worse than one left
    alone, and Unicode has no superscript `*`, `q`, `C`, `F`, `Q`, `S`, `X`,
    `Y` or `Z` to raise it with.
    """
    if not inner or any(c not in _SUPERSCRIPT for c in inner):
        return None
    return "".join(_SUPERSCRIPT[c] for c in inner)


def _collect(el: ET.Element, buf: list[str], counts: _Counter) -> None:
    """Recursively flatten an element's inline markup into ``buf``."""
    if el.text:
        buf.append(el.text)

    for child in el:
        tag = _local(child.tag)

        if tag in ("break", "br"):
            # 1473 cells contain one. A zero-width join here would glue two
            # separate numbers into a third number the paper never printed.
            buf.append(" ")
            counts.bump("break_to_space")

        elif tag == "xref":
            inner = "".join(child.itertext()).strip()
            if child.get("ref-type") == "bibr" and inner:
                # "...in 2022" + citation "1" would otherwise read as 20221.
                buf.append(f"[{inner}]")
                counts.bump("bibr_xref_bracketed")
            else:
                buf.append(inner)

        elif tag == "sup":
            inner = "".join(child.itertext()).strip()
            prev = "".join(buf)
            raised = _superscripted(inner)
            if inner and _NUMERIC_ONLY.match(inner) and _NUMERIC_TAIL.search(prev):
                # A number raised over a number is an EXPONENT, and `^` is the
                # right rendering precisely because it does not parse: `10^-3`
                # comes back `value: None`, while `10⁻³` comes back `value: 10`
                # -- the cell would yield 10 where the paper printed 0.001.
                # Refusing to parse is the honest answer; inventing 10 is not.
                buf.append("^" + inner)
                counts.bump("superscript_caret")
            elif raised is not None:
                # Everything else raised over a `<sup>` is a UNIT EXPONENT or a
                # FOOTNOTE MARKER, and both were being welded onto the baseline:
                # `kg/m2`, `Serious adverse event1`, `12.3a`. Unicode keeps them
                # legible and keeps `12.3ᵃ` parsing to 12.3 with `ᵃ` as an extra.
                buf.append(raised)
                counts.bump("superscript_unicode")
            else:
                buf.append(inner)

        elif tag == "sub":
            buf.append("".join(child.itertext()).strip())

        elif tag in ("graphic", "inline-graphic"):
            buf.append("[image]")

        elif tag in ("inline-formula", "disp-formula", "math", "formula"):
            buf.append(_formula_text(child))
            counts.bump("formula_flattened")

        elif tag in ("fn", "table-wrap-foot", "alt-text", "table-footnote"):
            # Captured separately (footnotes) or never part of a cell value
            # (Elsevier <ce:alt-text> is an accessibility string).
            pass

        elif tag in ("table-wrap", "table", "tgroup", "fig", "figure",
                     "graphic-alternatives", "alternatives"):
            # Some publishers nest <table-wrap> INSIDE a <p>. Flattening that
            # paragraph would pour the whole table into the prose, and the model
            # could then transcribe numbers from text that has already lost the
            # column alignment -- the exact failure this module exists to
            # remove. The table is emitted once, as a grid, and never here.
            pass

        elif tag in _TRANSPARENT:
            _collect(child, buf, counts)

        else:
            _collect(child, buf, counts)

        if child.tail:
            buf.append(child.tail)


def _formula_text(el: ET.Element) -> str:
    """
    Render a formula without gluing its tokens together.

    MathML ``<mn>0.05</mn><mn>3</mn>`` concatenated yields ``0.053`` — a number
    that appears nowhere in the paper. Prefer the TeX source; otherwise join
    the leaf tokens with spaces.
    """
    for node in el.iter():
        if _local(node.tag) == "tex-math":
            tex = "".join(node.itertext()).strip()
            if tex:
                return tex
    tokens = [
        t.strip()
        for node in el.iter()
        for t in ("".join(node.itertext()).strip(),)
        if not list(node) and t.strip()
    ]
    return " ".join(tokens) if tokens else "[formula]"


def _cell_text(el: ET.Element, counts: _Counter | None = None) -> str:
    """Flatten one table cell to plain text, preserving numeric integrity."""
    counts = counts if counts is not None else _Counter()
    buf: list[str] = []
    _collect(el, buf, counts)
    return _normalise("".join(buf), counts)


# ---------------------------------------------------------------------------
# Span expansion
# ---------------------------------------------------------------------------

_HAS_DIGIT = re.compile(r"\d")


def _expand(
    source_rows: list[list[tuple[str, int, int, bool]]],
) -> tuple[list[list[str]], list[dict], list[str]]:
    """
    Expand ``(text, colspan, rowspan, is_header)`` rows into a dense grid.

    Fill policy is a correctness guard, not a style choice:

    * **header rows and column 0** repeat their text across every covered cell —
      composite column labels and repeated row labels require it, and neither is
      a measurement.
    * **every other body cell is anchor-only**: the value lands in its first
      covered position and the continuations are empty.

    Without the anchor rule a single ``3.7 (0.30)`` with ``colspan=4`` becomes
    four identical (mean, SD) pairs. 355 such cells exist in the working corpus,
    and ``detect_duplication`` escalates at three — a ``highly_suspicious``
    finding manufactured by the parser against a paper that did nothing wrong.

    Returns ``(grid, spans, warnings)``.
    """
    grid: list[list[str]] = []
    spans: list[dict] = []
    warnings: list[str] = []
    carry: dict[int, tuple[str, int]] = {}

    for r_idx, cells in enumerate(source_rows):
        occupied: dict[int, str] = {}

        # Columns still covered by a rowspan from an earlier row.
        for col in sorted(carry):
            text, remaining = carry[col]
            occupied[col] = text
            if remaining <= 1:
                del carry[col]
            else:
                carry[col] = (text, remaining - 1)

        col = 0
        for text, colspan, rowspan, is_header in cells:
            while col in occupied:
                col += 1
            repeat = is_header or col == 0

            for k in range(colspan):
                target = col + k
                if target in occupied:
                    warnings.append(
                        f"row {r_idx}: overlapping span at column {target}"
                    )
                    continue
                occupied[target] = text if (k == 0 or repeat) else ""

            if rowspan > 1:
                for k in range(colspan):
                    carry[col + k] = (
                        text if repeat else "",
                        rowspan - 1,
                    )

            if (colspan > 1 or rowspan > 1) and text:
                spans.append({
                    "row": r_idx,
                    "col": col,
                    "colspan": colspan,
                    "rowspan": rowspan,
                    "text": text,
                    "repeated": repeat,
                })
            col += colspan

        width = max(occupied) + 1 if occupied else 0
        grid.append([occupied.get(i, "") for i in range(width)])

    # Right-pad to a common width. NEVER truncate a long row: dropping a cell
    # loses a reported number, while padding only adds a blank.
    #
    # `padded` records which rows were actually SHORT in the source. That is a
    # different question from "which rows contain blanks" — anchor-only span
    # expansion leaves blanks in perfectly well-formed rows, so testing for
    # blanks would flag a third of all tables and make the signal worthless.
    width = max((len(r) for r in grid), default=0)
    padded = [len(r) < width for r in grid]
    for row in grid:
        row.extend([""] * (width - len(row)))

    return grid, spans, warnings, padded


#: A cell that is only a number, and a cell that is only a mark. Both are
#: measurements, and neither is a column heading -- they are the brake on
#: `_header_depth` walking down into the data.
_ONLY_A_NUMBER = re.compile(r"^[\s(\[]*[-+\u2212]?\d[\d,.]*\s*[%)\]]?\s*$")
_ONLY_A_MARK = re.compile(r"^\s*[-+\u2212\u2013\u2014\u00b1*/\u2713xX]{1,2}\s*$")


def _reads_as_measurements(row: list[str]) -> bool:
    """Is this grid row data rather than a label row?

    THE ONE BRAKE, shared by both readers that decide a header's depth. Whatever
    proposes a deep header -- span structure on the HTML side, docling's
    `column_header` flags on the PDF side -- a row of measurements is not a
    heading, and promoting one out of the body is how a value stops existing for
    every check downstream. An extractor that mislabels a data row must not be
    able to delete it.

    Two tests, because one was not enough. A heading's stub is never a bare
    number, which is what rejects the `0 / - / +` row on
    `10.1016--j.yexcr.2014.06.020`; and two or more cells that are only a number
    or only a mark make the row data whatever its stub says.
    """
    if not row:
        return False
    if _ONLY_A_NUMBER.match(row[0] or ""):
        return True
    return sum(1 for c in row
               if _ONLY_A_NUMBER.match(c or "") or _ONLY_A_MARK.match(c or "")) >= 2


_HAS_A_DIGIT = re.compile(r"\d")


def section_bands(grid: list[list[str]], header_rows: int = 1) -> dict[int, str]:
    """`{row index: band label}` for the full-width heading rows inside a table.

    A clinical table is not a flat grid. It prints a band -- `Sex, n (%)`,
    `NIHSS (M, IQR)`, `A. Control` -- and then the rows it governs. The band
    carries three things the rows below it do not: the experimental arm, the
    variable group, and THE CELL FORMAT.

    THE FORMAT IS WHY THIS MATTERS. `celltypes` decides what a cell is from its
    LABEL, so when `n (%)` sits on a band the rows beneath it are typed with no
    marker at all:

        parse_cell("39 (33.3)", row_label="Male")               -> ambiguous
        parse_cell("39 (33.3)", row_label="Sex, n (%) | Male")  -> n_percent
        parse_cell("5 (3-11)",  row_label="Day 1")              -> estimate_ci
        parse_cell("5 (3-11)",  row_label="NIHSS (M, IQR) | Day 1") -> median_iqr

    MEASURED over the eleven-paper run. On `10.1186--s12883-023-03159-w`, 70
    rows parse correctly (marker on their own label) against 104 marked
    `ambiguous` (marker on a band above) -- about 250 percentages lost across
    five papers. And every one of that paper's 74 `estimate_ci` groups is really
    an interquartile range, so `check_estimate_ci` was applicable to 74 values
    it must never run on. It declined, which is why they also account for 74 of
    the 189 groups the register calls `silent`. One defect, three faces.

    A row qualifies as a band when its only text sits in column 0, or when every
    non-empty cell repeats one string -- docling expands a `colspan` by
    repeating, and the HTML reader anchor-fills it, so the same printed band
    arrives in those two shapes.

    TWO BRAKES, both needed. A band must not read as measurements
    (`_reads_as_measurements`), and it must GOVERN something: at least one row
    before the next band has to carry a number. Without the second, an
    inclusion-criteria table -- 23 stub-only rows and no data anywhere -- reports
    23 sections, and a trailing legend reports one more. Measured: 74 bands
    across 36 tables without it, 37 with, and every one of the 37 governs a
    value.
    """
    if not grid:
        return {}
    candidates: list[int] = []
    for i in range(max(1, header_rows), len(grid)):
        row = grid[i]
        if not row or not str(row[0] or "").strip():
            continue
        # BOTH SHAPES. A band is printed either as a label in column 0 with the
        # rest of the row empty (`Sex, n (%)` over Male / Female) or repeated
        # across every column, which is how docling expands a colspan.
        #
        # An earlier version ceded the repeated shape to
        # `composite.split_sections` to protect its banner detection. MEASURED,
        # and that was the wrong cut: on 10.1186--s12883-023-03159-w composite
        # found its 14 sections but the `(M, IQR)` marker never reached the
        # typer, so all 74 of that paper's interquartile ranges stayed typed as
        # confidence intervals. On the Guekht paper the opposite: the fold
        # worked and composite found ZERO sections, because the fold had removed
        # the rows before it looked.
        #
        # The two are not in competition. Composite needs the band ROW to remain
        # among the cells; the typer needs the band TEXT on the rows beneath.
        # `fold_section_bands` now does both, so this detects both.
        rest = [str(c or "").strip() for c in row[1:]]
        only_stub = not any(rest)
        repeated = bool(rest) and all(r == str(row[0]).strip() for r in rest)
        if not (only_stub or repeated):
            continue
        if _reads_as_measurements(row):
            continue
        candidates.append(i)

    # A PARENT BAND GOVERNS THROUGH ITS CHILD. The brake above asks whether a
    # band has a value under it before the next band, which is right for a
    # trailing legend and wrong for a NESTED heading: `Primary` immediately
    # followed by `HT, n (%)` has nothing between them, so `range(i+1, end)` is
    # empty and the parent was dropped.
    #
    # CORROBORATED AGAINST THE EXTRACTOR, 2026-08-20. docling carries a
    # `row_section` flag on `TableCell` that this walker has never read. Probing
    # it on 10.1186--s12883-023-03159-w: on five of the paper's six banded
    # tables docling's flags and this inference agree EXACTLY, and on the sixth
    # docling additionally marks rows 2 and 8 -- `Primary` and `Secondary` --
    # the two nested parents this brake was rejecting. So the flag is worth
    # nothing here as a source (the shape rule reproduces it) and everything as
    # an independent check on the rule's brakes, which is how it is used.
    #
    # Inheritance is restricted to an IMMEDIATELY adjacent band. A gap with no
    # digits in it is a band governing nothing, which is what the brake is for:
    # the inclusion-criteria table of 23 stub-only rows still reports none,
    # because no band in it governs a value and nothing can inherit from
    # nothing.
    out: dict[int, str] = {}
    direct_at: list[bool] = []
    for k, i in enumerate(candidates):
        end = candidates[k + 1] if k + 1 < len(candidates) else len(grid)
        direct_at.append(any(
            any(_HAS_A_DIGIT.search(str(c or "")) for c in grid[j][1:])
            for j in range(i + 1, end)))
    for k, i in enumerate(candidates):
        # ONE LEVEL OF INHERITANCE, from a band immediately below that governs
        # DIRECTLY. Chaining it instead -- letting an inheriting band confer
        # governance in turn -- admits a whole RUN of stub-only rows sitting
        # above a real band, since each borrows from the next. A title and a
        # note above `Sex, n (%)` would both become bands.
        #
        # The cost is a three-deep nesting losing its outermost heading, which
        # is the conservative direction and is not attested: the observed case
        # is two deep (`Primary` over `HT, n (%)`).
        inherited = (k + 1 < len(candidates)
                     and candidates[k + 1] == i + 1
                     and direct_at[k + 1])
        if direct_at[k] or inherited:
            out[i] = str(grid[i][0]).strip()
    return out


def fold_section_bands(grid: list[list[str]], header_rows: int = 1,
                      indents: list[bool] | None = None):
    """`(body, sections, kept)` -- band rows folded into the labels they govern.

    THREE READERS BUILD CELLS FROM A GRID: this one for JATS, `html._build_table`
    for publisher HTML, and `supplements_read._finish` for everything read from
    a PDF or a spreadsheet. The band logic went into one of them first and the
    corpus measured ZERO bands, because the three papers that carry the defect
    all arrive by XML. Three copies of one act is how they come to disagree, so
    it lives here and all three call it.

    `kept` is the original row index of each body row, because the ragged-row
    check reads `padded` by position and a dropped band would shift it.
    """
    bands = section_bands(grid, header_rows)
    # A BAND ENDS WHERE ITS CHILDREN DO, when the markup says so. Scoping a
    # band to the NEXT band is right for a topic banner and wrong for a
    # variable with levels: measured on `10.1002--ajcp.70049` Table 1, the
    # band `State` governs Pennsylvania and Missouri (both
    # `padding-left:10%`), and the next two rows -- `Communities That Care`
    # and `Externally funded`, unindented -- are separate variables. The
    # default swallowed them and emitted `State | Communities That Care`,
    # the system asserting a coalition model is a US state.
    #
    # AN ALL-FALSE LIST IS NO EVIDENCE, not proof of a flat table: many
    # publishers indent by means this reader cannot see, and every non-XML
    # producer passes None. The next-band default then stands, because a
    # band stopping at its first row is far worse than one running long.
    indents = indents or []
    has_indent_evidence = any(indents)
    body: list[list[str]] = []
    kept: list[int] = []
    sections: list[dict] = []
    current = ""
    for i in range(header_rows, len(grid)):
        if i in bands:
            current = bands[i]
            sections.append({"row": i, "label": current})
            # THE BAND ROW STAYS. `composite.split_sections` reads the CELLS and
            # finds its banners there; removing the row deleted its input, and
            # on the Guekht paper it went from finding sections to finding none.
            # The row is non-numeric, so no check consumes it -- it is carried
            # for the reader that needs it.
            body.append(list(grid[i]))
            kept.append(i)
            continue
        if has_indent_evidence and current and not (
                indents[i] if i < len(indents) else False):
            current = ""
        row = list(grid[i])
        if current and row:
            stub = str(row[0] or "").strip()
            # A blank stub inherits the band ALONE -- otherwise the band's first
            # row lends its name to every blank-stubbed row beneath it.
            row[0] = f"{current} | {stub}" if stub else current
        body.append(row)
        kept.append(i)
    return body, sections, kept


def _header_depth(source_rows: list[list[tuple[str, int, int, bool]]],
                  grid: list[list[str]], cap: int = 4) -> int:
    """How many leading rows the MARKUP proves are header. Zero if row 0 is data.

    A cell with ``colspan > 1`` in row *r* is a proof, not a hint: it spans
    columns that row *r* therefore cannot tell apart, so the columns are
    distinguished by a row BELOW it or not at all. Reading such a table with a
    one-row header does not lose a decoration, it loses the column's identity.

    MEASURED over the 36 tables the Mistral extraction found in the 22
    known-damaged cerebrolysin papers: 20 have a two-row header, and on 15 of
    36 (42%) the one-row reading collapses distinct columns into one label --
    22 distinct column labels gone. On ``10.1166--jnn.2011.5114`` the header is
    ``Control | Heat stress`` over ``Saline / Cu / Ag``, so the one-row reading
    labels the saline, copper and silver columns identically: a mean drawn from
    one and an ``n`` from another are indistinguishable afterwards, and GRIM on
    that pair calls an honest paper impossible. That is the accusation this
    repository exists to avoid making.

    It also loses the ``n``. ``design_values_from_cells`` says of this very
    corpus that "0 of 20 cells carried a `col`" on
    ``10.1007--s00702-004-0248-2``; the cause is here. ``Placebo (n = 68)``
    sits in the second header row, so a one-row reading files it as DATA and no
    cell ever carries it as a label. Measured on that paper: header depth 1
    yields 0 design values, depth 2 yields 2 -- ``n = 78`` and ``n = 68``, the
    numbers that gate GRIM, GRIMMER, SPRITE, `debit_check` and
    `check_count_percent`.

    THE BRAKE MATTERS AS MUCH AS THE PROOF. Walking down while the row above
    spans would, on a table whose body itself merges cells, swallow a row of
    measurements into the header -- and a measurement promoted to a label is
    a value the register then cannot see at all. So a candidate row stops the
    walk when its stub is a bare number (a heading's stub never is) or when two
    or more of its cells read as measurements. Both brakes were needed: on
    ``10.1016--j.yexcr.2014.06.020`` the spanning walk reaches a row of
    ``0 / - / + ...`` that only the stub test rejects.

    AND THE SAME BRAKE ASKED ABOUT ROW 0. The walk used to open at 1 and never
    return lower, so a table with NO header row at all -- most often a long table
    continued onto a second element without repeating its header -- had its first
    DATA row taken as the column labels. On PMC5532079 Table 1 that names a
    column `49` and loses the row's own denominator to every value beneath it.
    Reported by a peer session and independently verified.

    The brake below already answers exactly this question about a LATER row; it
    is now asked about the first one too, rather than a second heuristic being
    invented for the same judgment. This can only ever LOWER a depth -- a row 0
    that does not read as measurements is unchanged, and an AMBIGUOUS row 0
    (one measurement-shaped cell, say) is not evidence and still gets 1. The
    caller then names the columns `(unlabelled column N)` and the row stays in
    the body: a derived boundary may narrow a premise, never supply one.

    Returns a count, not a slice, because the caller owns the grid.
    """
    if grid and _reads_as_measurements(grid[0]):
        return 0
    depth = 1
    while depth < len(grid) and depth < cap:
        above = source_rows[depth - 1] if depth - 1 < len(source_rows) else []
        if not any(c[1] > 1 for c in above):
            break
        candidate = grid[depth]
        if not candidate or _reads_as_measurements(candidate):
            break
        depth += 1
    return depth


def _cells_from_grid(
    header: list[str], body: list[list[str]], label_col: int = 0,
    unlabelled_col: str = "col{i}",
) -> list[dict]:
    """
    Build ``{raw, row_label, col_label}`` cells straight from the grid.

    This exists because `parse_table` is a lossy bridge: it runs `parse_cell`
    and drops anything that yields no scalar (`tableparse.py:238`), so an
    ``estimate (CI)`` cell like ``96.2 (95.7-96.7)`` vanishes. On a real
    clinical Table 1 that path keeps 57 of 189 cells, while handing the raw
    strings to `parse_cells_typed` keeps 173 — including 114 `estimate_ci`
    cells with `low`/`high` recovered. Those are the cells the sweep prompt
    calls the highest-yield check on clinical papers, so the main path must not
    route through the filter. `parse_table` remains the right tool for
    reconciling two extractions via `cross_check`.

    An empty label cell inherits the last non-empty one, which is what a reader
    does with a table whose row labels are only printed once.

    ``unlabelled_col`` is the placeholder for a column the source never
    labelled. It stays ``col{i}`` here, where the position IS the identity: a
    JATS grid is rectangular by construction, so column 3 of every row is the
    same column and ``col3`` names it without asserting anything about its
    meaning. Callers whose grid was padded into shape rather than born
    rectangular -- ``supplements_read`` -- pass a placeholder that says the
    column is unlabelled instead, because there the position is exactly what is
    in doubt.
    """
    cells: list[dict] = []
    current = ""
    for r, row in enumerate(body):
        label = row[label_col].strip() if label_col < len(row) else ""
        if label:
            current = label
        for i, raw in enumerate(row):
            if i == label_col:
                continue
            raw = raw.strip()
            if not raw:
                continue
            cells.append({
                "raw": raw,
                # 1-based index into `data`, which is `[header] + body`, so a
                # cell and the grid row it came from share ONE coordinate.
                # Without it the two views could only be windowed on separate
                # cursors, and a caller resuming a large table had no single
                # position to resume from -- `row_label` cannot serve, because
                # a merged label spans its whole block (Romano's 60-row Table 2
                # has 12 distinct labels).
                "row": r + 2,
                # THE PHYSICAL COLUMN, 0-based into the grid row, so that
                # `data[row - 1][col]` is this cell. Emitted because
                # `col_label` is NOT an address: a stacked header can give
                # several columns the same label, and on a table with repeated
                # spans that is the ordinary case, not the exotic one.
                #
                # MEASURED on 10.1002--ajcp.70049 Table 2, whose header is
                # three identical `<th colspan="2">Coefficient</th>` spans over
                # three regression models: 42 cells collapse to 18 distinct
                # `(row_label, col_label)` pairs, and 36 of the 42 sit at an
                # address shared with another cell. The three covariate
                # coefficients `0.31 (0.04)`, `0.35 (0.04)` and `0.36 (0.05)`
                # -- one per model -- are the SAME address.
                #
                # Without this, no model- or term-level anchor can be verified
                # against the register, and a join keyed on anything else
                # assigns all three of that paper's headline coefficients to
                # the first model while reading as proof. It is also the half
                # of extraction verification that conservation cannot supply:
                # checking every value against the printed cells catches
                # invention and omission, and only position catches
                # MISASSIGNMENT.
                "col": i,
                "row_label": current or "(unlabelled row)",
                "col_label": ((header[i].strip() if i < len(header) else "")
                              or unlabelled_col.format(i=i)),
            })
    return cells


def _flatten_header(header_rows: list[list[str]], width: int) -> list[str]:
    """
    Collapse a multi-row header into one composite label per column.

    ``["Stage 1 prediction"(colspan=2)] / ["n1", "d1opt"]`` becomes
    ``["Stage 1 prediction | n1", "Stage 1 prediction | d1opt"]``. Consecutive
    duplicates are dropped so a ``rowspan=2`` label yields ``"Var"`` rather than
    ``"Var | Var"``. A column with no header text stays empty — `parse_table`
    then falls back to ``col{i}``, which is honest; inventing a label is not.
    """
    labels: list[str] = []
    for i in range(width):
        parts: list[str] = []
        for row in header_rows:
            value = row[i].strip() if i < len(row) else ""
            if not value or (parts and parts[-1] == value):
                continue
            parts.append(value)
        labels.append(" | ".join(parts))
    return labels


# ---------------------------------------------------------------------------
# Reading rows out of the two table markups
# ---------------------------------------------------------------------------

def _span(el: ET.Element, attr: str) -> int:
    try:
        return max(1, int(el.get(attr) or 1))
    except (TypeError, ValueError):
        return 1


def _tr_cells(tr: ET.Element, in_thead: bool, counts: _Counter) -> list[tuple]:
    cells: list[tuple] = []
    for cell in tr:
        tag = _local(cell.tag)
        if tag not in ("td", "th"):
            continue
        cells.append((
            _cell_text(cell, counts),
            _span(cell, "colspan"),
            _span(cell, "rowspan"),
            in_thead or tag == "th",
        ))
    return cells


#: Style attributes a publisher uses to indent a stub, marking a row as a CHILD
#: of the band above it rather than a sibling of it. Read as a fact about the
#: printed table, exactly like a colspan.
_INDENT_STYLE = re.compile(r"(?:padding|margin)-left\s*:\s*(\d+(?:\.\d+)?)\s*(%|px|em|pt)",
                           re.I)

#: Leading whitespace a publisher uses instead of a style, including the typographic
#: spaces that survive `_normalise`. Same signal, cheaper markup.
_INDENT_CHARS = "\u00a0\u2000\u2001\u2002\u2003\u2007\u2009\t"


def _row_is_indented(tr: ET.Element) -> bool:
    """Is this row's stub indented under the band above it?

    WHY THIS IS READ AT ALL. `fold_section_bands` scopes a band to the NEXT
    band, which is right for a topic banner and wrong for a variable with
    levels. Measured on `10.1002--ajcp.70049` Table 1: the band `State` governs
    Pennsylvania and Missouri, which carry `padding-left:10%`, and the next two
    rows -- `Communities That Care` and `Externally funded`, with NO indent --
    are separate variables. The next-band default swallowed them, so the walker
    emitted `State | Communities That Care`, asserting that a coalition model is
    a US state.

    The indent is in the publisher's markup and was being discarded by
    `_cell_text`, which flattens a cell to plain text. This reads it before the
    flattening, and returns False when there is no evidence either way -- an
    absent style is not proof of a sibling, so the caller must treat "no indents
    anywhere in this table" as "no evidence" rather than "nothing is indented".
    """
    for cell in tr:
        if _local(cell.tag) not in ("td", "th"):
            continue
        style = cell.get("style") or ""
        m = _INDENT_STYLE.search(style)
        if m and float(m.group(1)) > 0:
            return True
        if (cell.text or "").startswith(tuple(_INDENT_CHARS)):
            return True
        return False        # only the FIRST cell -- the stub -- carries it
    return False


def row_indents(table_el: ET.Element) -> list[bool]:
    """One flag per body row, in the order `_rows_html` returns them."""
    out: list[bool] = []
    for node in table_el:
        tag = _local(node.tag)
        if tag in ("thead", "tbody", "tfoot"):
            for tr in node:
                if _local(tr.tag) == "tr":
                    out.append(_row_is_indented(tr))
        elif tag == "tr":
            out.append(_row_is_indented(node))
    return out


#: `n = 64`, `N = 107`, `n=1,293` -- an assertion about a column, not a
#: measurement of anything.
_ADJUNCT_N = re.compile(r"^\s*[nN]\s*[=:]\s*([\d,]+)\s*$")


def header_adjuncts(grid: list[list[str]], header_rows: int = 1) -> list[dict]:
    """Rows under the header that ASSERT something about a column.

    A table often prints its denominator as the first body row: an empty stub,
    and `n = 64` under the column it describes. It is not a measurement of a
    variable -- there is no variable -- and a reader that treats it as one has
    an unlabelled number in the value stream.

    Greg Fitzgerald, 2026-08-29, reading `10.1002--ajcp.70049` Table 1: "Row 2
    is mostly blank, and contains an n value that I think might confuse the
    model." It does: what `get_table` hands the model is a near-empty row with
    a stray `n = 64` in it, and the fact that it is the COLUMN's denominator
    exists only in the reader's head.

    Returned as structure so the fact is available by name. THE ROW IS NOT
    REMOVED: `data` and `rows` stay the grid the paper printed, on the same
    argument as band rows -- removing them shrank `data` from 61 rows to 49 and
    broke the property `test_table_delivery` exists to hold.

    DELIBERATELY NOT WIRED TO ANY CHECK. This is a denominator with a plausible
    scope, and `values.check_stated_denominators` is one `or` away. A column
    header's n is accepted there only when it is marked `level="column"`; an
    adjunct row's scope is the reader's inference, and the same reasoning that
    bars a footnote's N bars this. Surfacing a fact and licensing arithmetic on
    it are different decisions.
    """
    out: list[dict] = []
    header = grid[header_rows - 1] if 0 < header_rows <= len(grid) else []
    for i in range(header_rows, len(grid)):
        row = grid[i]
        if not row or str(row[0] or "").strip():
            break            # a real stub: the adjunct block is over
        found = False
        for col, cell in enumerate(row):
            m = _ADJUNCT_N.match(str(cell or ""))
            if not m:
                continue
            found = True
            out.append({
                "row": i,
                "column": (str(header[col]).strip()
                           if col < len(header) else None),
                "text": str(cell).strip(),
                "n": int(m.group(1).replace(",", "")),
            })
        if not found:
            break
    return out


def _rows_html(table_el: ET.Element, counts: _Counter) -> list[list[tuple]]:
    """
    Read an XHTML-style ``<table>`` (JATS) into span-annotated rows.

    Walks ``thead``/``tbody``/``tfoot`` explicitly rather than scanning for
    ``<tr>`` anywhere, because header membership decides the repeat-vs-anchor
    fill policy and must not be guessed.
    """
    rows: list[list[tuple]] = []
    for node in table_el:
        tag = _local(node.tag)
        if tag in ("thead", "tbody", "tfoot"):
            in_thead = tag == "thead"
            for tr in node:
                if _local(tr.tag) != "tr":
                    continue
                cells = _tr_cells(tr, in_thead, counts)
                if cells:
                    rows.append(cells)
        elif tag == "tr":
            # Some tables put rows directly under <table>.
            cells = _tr_cells(node, False, counts)
            if cells:
                rows.append(cells)
    return rows


def _rows_cals(tgroup: ET.Element, counts: _Counter) -> list[list[tuple]]:
    """
    Read an Elsevier CALS ``<tgroup>`` into span-annotated rows.

    CALS names its columns: ``<colspec colname="col2"/>`` fixes the order, an
    entry spans via ``namest``/``nameend``, and ``morerows="k"`` means a rowspan
    of ``k+1``. Four files in the working corpus use this and have zero
    ``<table-wrap>`` — two of them are the papers with no PDF at all, so
    skipping CALS would silently review them with no tables.
    """
    order: dict[str, int] = {}
    for spec in tgroup:
        if _local(spec.tag) == "colspec":
            name = spec.get("colname")
            if name:
                order.setdefault(name, len(order))

    rows: list[list[tuple]] = []
    for section in tgroup:
        sec = _local(section.tag)
        if sec not in ("thead", "tbody", "tfoot"):
            continue
        is_header = sec == "thead"
        for tr in section:
            if _local(tr.tag) != "row":
                continue
            cells: list[tuple] = []
            for entry in tr:
                if _local(entry.tag) != "entry":
                    continue
                start, end = entry.get("namest"), entry.get("nameend")
                colspan = 1
                if start and end and start in order and end in order:
                    colspan = max(1, order[end] - order[start] + 1)
                rowspan = _span(entry, "morerows") if entry.get("morerows") else 1
                if entry.get("morerows"):
                    try:
                        rowspan = int(entry.get("morerows")) + 1
                    except (TypeError, ValueError):
                        rowspan = 1
                cells.append((
                    _cell_text(entry, counts), colspan, max(1, rowspan), is_header,
                ))
            if cells:
                rows.append(cells)
    return rows


def _footnotes(container: ET.Element, counts: _Counter) -> list[dict]:
    """
    Collect a table's footnotes.

    These are not decoration: they routinely define what a cell *means*
    ("values are n (%)", "SD in parentheses"), which decides how
    `parse_cells_typed` should type it.
    """
    notes: list[dict] = []
    for node in container.iter():
        tag = _local(node.tag)
        if tag not in ("fn", "table-footnote", "legend"):
            continue
        marker = ""
        body_parts: list[str] = []
        for child in node:
            if _local(child.tag) == "label":
                marker = _normalise("".join(child.itertext()), counts)
            else:
                body_parts.append(_cell_text(child, counts))
        text = _normalise(" ".join(p for p in body_parts if p), counts)
        if not text:
            text = _cell_text(node, counts)
        if text:
            notes.append({"marker": marker, "text": text})
    return notes


def _first(container: ET.Element, names: tuple[str, ...], counts: _Counter) -> str:
    for node in container.iter():
        if _local(node.tag) in names:
            return _cell_text(node, counts)
    return ""


def _build_table(
    container: ET.Element,
    table_el: ET.Element | None,
    table_num: int,
    section: str,
    counts: _Counter,
    cals: bool = False,
) -> dict:
    """Assemble one table dict from its wrapper and (optional) markup."""
    label = _first(container, ("label",), counts)
    caption = ""
    for node in container:
        if _local(node.tag) in ("caption", "simple-para"):
            caption = _cell_text(node, counts)
            break
    if not caption:
        caption = _first(container, ("caption",), counts)

    table: dict[str, Any] = {
        "page": None,          # XML has no pages. Never faked.
        "table_num": table_num,
        "id": container.get("id") or "",
        "label": label,
        "caption": caption,
        "section": section,
        "footnotes": _footnotes(container, counts),
        "source": "xml",
        "warnings": [],
    }

    if table_el is None:
        # A picture of a table. It has NO cells; saying otherwise would let a
        # reader believe it was checked.
        href = ""
        for node in container.iter():
            if _local(node.tag) in ("graphic", "inline-graphic"):
                for key, value in node.attrib.items():
                    if _local(key) == "href":
                        href = value
                        break
        table.update({
            "data": [], "cells": [], "headers": [], "rows": [],
            "header_rows": [], "n_header_rows": 0, "width": 0, "n_rows": 0,
            "spans": [], "alignment_uncertain": False, "image_only": True,
            "graphic_href": href,
        })
        table["warnings"].append(
            "table is an image in the XML and has no cells; extract it from "
            "the PDF or record it as unchecked"
        )
        return table

    source_rows = (
        _rows_cals(table_el, counts) if cals else _rows_html(table_el, counts)
    )
    grid, spans, warnings, padded = _expand(source_rows)
    table["warnings"].extend(warnings)

    n_header = 0
    for cells in source_rows:
        if cells and all(c[3] for c in cells):
            n_header += 1
        else:
            break

    width = len(grid[0]) if grid else 0
    if n_header:
        header = _flatten_header(grid[:n_header], width)
        body = grid[n_header:]
    else:
        # Do not promote a body row into the header — that guess would rename
        # every value's column. Emit an empty header and say so.
        header = [""] * width
        body = grid
        if grid:
            table["warnings"].append(
                "no <thead>; header may be the first body row — pass "
                "header_row=1 to parse_table if so"
            )

    # A row that was SHORT IN THE SOURCE and carries several numbers may have
    # its values sitting under the wrong labels, which would hand GRIM/GRIMMER
    # a (mean, sd, n) triple the paper never reported. A one-cell section-label
    # row is benign and stays silent.
    uncertain = False
    # THE PRINTED TABLE STAYS WHOLE. `data` and `rows` are the grid the paper
    # printed, band rows included -- removing them shrank `data` from 61 rows to
    # 49 and broke the one property `test_table_delivery` exists to hold: every
    # number is in `data` without the caller following a pointer. The fold is a
    # VIEW for typing, not an edit to the table. Same argument as recording a
    # boundary rather than cutting the document.
    _folded, _sections, _kept = fold_section_bands(
        grid, n_header,
        indents=(row_indents(table_el) if (table_el is not None and not cals) else None))
    table["sections"] = _sections
    # See `header_adjuncts`: a fact about a column, surfaced by name so it
    # is not just a near-empty row the model has to interpret.
    table["header_adjuncts"] = header_adjuncts(grid, n_header)
    body_padded = padded[n_header:] if n_header else padded
    for row, was_padded in zip(body, body_padded):
        if not was_padded:
            continue
        numeric = sum(1 for c in row if _HAS_DIGIT.search(c))
        if numeric >= 2:
            uncertain = True
            table["warnings"].append(
                f"ragged row {row[:2]!r}: column labels may be shifted; "
                "reconcile against the PDF before reporting from this table"
            )

    table.update({
        "data": [header] + body,
    # THE FOLD IS OFF. It is detected and REPORTED (`sections`), and it does not
    # touch the cells.
    #
    # WHY, measured 2026-08-20: folding the band into the row label made rows
    # checkable that were not before, and `check_count_percent` then paired
    # them with the COLUMN's n. On two honest papers that produced two false
    # accusations -- `Radiotherapy history | Yes`, count 10, percentage 2.9,
    # against the column header's `n = 352`. 10/352 is 2.84%, so the check
    # fired. But the paper is consistent with its own denominator: any n from
    # 339 to 350 prints 2.9%, and 587/590 prints 99.5% exactly. The rows have a
    # smaller denominator than the column total because some patients' history
    # is unknown -- ordinary, and none of our business to override.
    #
    # `test_and_accuses_nobody` caught it. A false accusation against an honest
    # paper is the worst thing this pipeline can produce, and a typing
    # improvement that buys it is not an improvement.
    #
    # `composite.split_sections` already solves the half that matters: it
    # derives a section's n by summing its exhaustive categories and VALIDATES
    # that n against the paper's own printed percentages before any check may
    # use it. The format-marker inheritance belongs there, behind that
    # validation -- not here, ahead of it.
        "cells": _cells_from_grid(header, _folded),
        "headers": header,
        "rows": body,
        "header_rows": grid[:n_header],
        "n_header_rows": n_header,
        "width": width,
        "n_rows": len(body),
        "spans": spans,
        "alignment_uncertain": uncertain,
        "image_only": False,
        "graphic_href": None,
    })
    return table


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

def _article_root(root: ET.Element) -> tuple[ET.Element, list[str]]:
    """Unwrap a ``<pmc-articleset>`` down to the single ``<article>``."""
    warnings: list[str] = []
    if xml_flavour(root) != PMC_SET:
        return root, warnings
    articles = [c for c in root if _local(c.tag) == "article"]
    if not articles:
        return root, ["pmc-articleset contains no <article>"]
    if len(articles) > 1:
        warnings.append(
            f"pmc-articleset holds {len(articles)} articles; used the first"
        )
    return articles[0], warnings


def _table_containers(el: ET.Element) -> list[ET.Element]:
    """Every table wrapper at or below ``el``, in document order."""
    found = []
    for node in el.iter():
        tag = _local(node.tag)
        if tag == "table-wrap":
            found.append(node)
        elif tag == "table" and "elsevier" in str(node.tag):
            found.append(node)          # Elsevier <ce:table> is its own wrapper
    return found


def _tables_in(container: ET.Element) -> list[ET.Element]:
    """The markup table(s) inside a wrapper — there can legitimately be two."""
    out = []
    for node in container.iter():
        tag = _local(node.tag)
        if tag == "table" and node is not container:
            out.append(node)
        elif tag == "tgroup":
            out.append(node)
    return out


def _section_title(sec: ET.Element, counts: _Counter) -> str:
    for child in sec:
        if _local(child.tag) in ("title", "section-title"):
            return _cell_text(child, counts)
    return ""


def _abstract_texts(node: ET.Element, counts: _Counter,
                    seen_figs: "set[int] | None" = None) -> list[str]:
    """An abstract's prose, INCLUDING the structured kind.

    A structured JATS abstract nests its prose in `<sec>` children --
    `<abstract><sec><title>Background</title><p>...` -- and `_paragraphs`
    only reads direct children, so it returned nothing and `add()` dropped
    the whole section. MEASURED 2026-08-22 over 195 papers with an
    `<abstract>`: 114 of them have no direct `<p>` at all. The abstract is
    where a paper's headline claim usually lives, so those were the findings
    least likely to be anchorable.
    """
    out = _paragraphs(node, counts, seen_figs)
    for child in node:
        # `abstract-sec` IS ELSEVIER'S NAME FOR THE SAME THING, and leaving it
        # off cost the whole abstract, not a heading. MEASURED 2026-08-22,
        # `10.1016--j.jpsychires.2018.04.010`: its one `<ce:abstract>` holds
        # four `<ce:abstract-sec>` children and no direct `<ce:simple-para>`,
        # so `_paragraphs` returned nothing, this loop never descended, and
        # `add()` dropped the section. `paper_text` then began at
        # "## Introduction" -- and both of that paper's abstract-vs-Results
        # findings shipped `quote_verified: "unverified"`, because the sentence
        # they quote was not in the text we had loaded. Abstract overstatement
        # is the highest-value class this pipeline produces; it cannot be the
        # one we cannot certify.
        if _local(child.tag) in ("sec", "section", "abstract-sec"):
            title = _section_title(child, counts)
            if title:
                out.append(title)
            out.extend(_abstract_texts(child, counts, seen_figs))
    return out


def _abstract_label(node: ET.Element) -> str:
    """`Abstract`, or `Abstract (key-points)` for a publisher's extra one."""
    for key, val in node.attrib.items():
        if key.endswith("abstract-type") and val:
            return f"Abstract ({val})"
    return "Abstract"


def _fig_block(fig: ET.Element, counts: _Counter) -> str:
    """A figure's label and caption as one block, or "" when it has neither."""
    cap = _first(fig, ("caption", "simple-para"), counts)
    lab = _first(fig, ("label",), counts)
    if not (cap or lab):
        return ""
    return f"[{lab or 'FIGURE'}: {cap}]".strip()


#: Every element name a publisher uses for "this is a figure". `ce:figure` is
#: Elsevier's, and it is the reason this function exists at all -- see
#: `figure_captions`.
_FIGURE_TAGS = ("fig", "figure")


def figure_captions(xml_path: str | Path) -> list[dict]:
    """Every figure element in a publisher XML, with its label and caption.

    `{"id", "raw_label", "label", "caption", "flavour"}` per figure, in
    document order.

    NO `<graphic>` IS REQUIRED, and that is the whole difference from
    `image_forensics.pmc_figures.jats_figures`. That function exists to FETCH
    images from PMC, so a figure with no `<graphic xlink:href>` is nothing it
    can ask for and it drops the element. Elsevier's `full-text-retrieval-
    response` never writes `<graphic>` at all -- it points at artwork with
    `<ce:link locator="gr2"/>` -- so applying the fetcher's rule to an Elsevier
    paper returns ZERO figures and reads as "this paper has no figures".
    Reading a caption needs no image, so this asks for none.

    Raises `OSError` / `ET.ParseError` rather than returning `[]` for a file it
    could not read: an empty list here means "this document names no figure",
    and the caller has to be able to tell those two apart by name.
    """
    root = ET.parse(str(xml_path)).getroot()
    counts = _Counter()
    flavour = xml_flavour(root)
    out: list[dict] = []
    for el in root.iter():
        if _local(el.tag) not in _FIGURE_TAGS:
            continue
        raw_label = _first(el, ("label",), counts)
        caption = _first(el, ("caption", "simple-para"), counts)
        out.append({
            "id": el.get("id") or "",
            "raw_label": raw_label,
            "label": _normalised_figure_label(raw_label, len(out) + 1),
            "caption": caption,
            "flavour": flavour,
        })
    return out


def figure_id_map(xml_path: str | Path) -> dict[str, str]:
    """`element id -> normalised label`, for joining citations to figures.

    A citation names an id (`<xref rid="F2">`, `<ce:cross-ref refid="fig2">`)
    and nothing else, so without this map a reference is unattributable. Ids
    absent from the document are simply not in the map -- the caller reports an
    unresolvable citation, it is not silently dropped here.
    """
    return {f["id"]: f["label"] for f in figure_captions(xml_path)
            if f["id"] and f["label"]}


def _normalised_figure_label(raw_label: str, index: int) -> str:
    """`Fig. 3` -> `Figure 3`, in the spelling the image track's figure-level
    joins are keyed on (`figure_labels` is pinned equal to its normaliser by
    the image package's test suite).
    """
    from .figure_labels import normalise_label
    return normalise_label(raw_label, index) or ""


def _paragraphs(sec: ET.Element, counts: _Counter,
                seen_figs: "set[int] | None" = None) -> list[str]:
    """Prose of a section, excluding nested sections and table/figure markup.

    `seen_figs` records which figures this claimed, so the document-wide sweep
    in `extract_xml_text_with_tables` can pick up the ones no section owns
    without emitting any caption twice.
    """
    return _prose_run(list(sec), counts, seen_figs)


#: Tags `_prose_run` reads. Kept beside it so the walk below can test a child
#: for "is this prose I would collect" without duplicating the list.
_PROSE_TAGS = ("p", "para", "simple-para", "fig", "figure")


def _prose_run(nodes: "list[ET.Element]", counts: _Counter,
               seen_figs: "set[int] | None" = None) -> list[str]:
    """The prose of a RUN of sibling nodes, in document order.

    Split out of `_paragraphs` so the body walk can read paragraphs that are
    not inside any `<sec>` -- see the comment at its call site.
    """
    out: list[str] = []
    for child in nodes:
        tag = _local(child.tag)
        if tag in ("p", "para", "simple-para"):
            text = _cell_text(child, counts)
            if text:
                out.append(text)
        elif tag in ("fig", "figure"):
            block = _fig_block(child, counts)
            if block:
                out.append(block)
                if seen_figs is not None:
                    seen_figs.add(id(child))
    return out


def _find_local(el: ET.Element, name: str) -> ET.Element | None:
    for node in el.iter():
        if _local(node.tag) == name:
            return node
    return None


def _person_name(contrib: ET.Element, counts: _Counter) -> str:
    """"Given Surname" from a JATS name, or the collab/string-name as printed."""
    for node in contrib.iter():
        tag = _local(node.tag)
        if tag in ("name", "string-name"):
            sur = _first(node, ("surname",), counts)
            given = _first(node, ("given-names",), counts)
            full = " ".join(x for x in (given, sur) if x)
            if full:
                return full
        elif tag == "collab":
            text = _cell_text(node, counts)
            if text:
                return text
    return ""


def _authors(article_meta: ET.Element | None, counts: _Counter) -> dict:
    """Author list, and whichever of them the document marks as corresponding.

    None of this was captured before -- `article_metadata` returned title,
    journal, doi and year and nothing else -- so a review could not say who
    wrote the paper, let alone who to write to about it.

    The corresponding author is found two ways because publishers use both:
    `<contrib corresp="yes">` carrying an `<address><email>`, and a separate
    `<corresp>` block in the front matter. Wiley emits both, and either alone
    is enough.
    """
    out = {"authors": "", "author_list": [], "corresponding_author": "",
           "corresponding_email": ""}
    if article_meta is None:
        return out

    names: list[str] = []
    for contrib in article_meta.iter():
        if _local(contrib.tag) != "contrib":
            continue
        if (contrib.get("contrib-type") or "author") != "author":
            continue
        name = _person_name(contrib, counts)
        if not name:
            continue
        names.append(name)
        if contrib.get("corresp") == "yes" and not out["corresponding_author"]:
            out["corresponding_author"] = name
            email = _find_local(contrib, "email")
            if email is not None:
                out["corresponding_email"] = _cell_text(email, counts)

    # The standalone <corresp> block. Used as a fallback for the name and as a
    # first resort for the address, since the contrib element frequently
    # carries the marker without the email.
    for node in article_meta.iter():
        if _local(node.tag) != "corresp":
            continue
        email = _find_local(node, "email")
        if email is not None and not out["corresponding_email"]:
            out["corresponding_email"] = _cell_text(email, counts)
        if not out["corresponding_author"]:
            text = _cell_text(node, counts)
            for candidate in names:
                if candidate and candidate in text:
                    out["corresponding_author"] = candidate
                    break

    # THE PMC PATTERN, which is the commonest one in this corpus and which
    # neither branch above can see.
    #
    # MEASURED on 10.1007--s11064-023-03861-8: the XML carries ZERO <corresp>
    # elements and ZERO <email> elements, so both branches above find nothing
    # and the Questions page renders "No corresponding author was extracted, so
    # these have nowhere to go without looking one up" -- while the answer is
    # sitting in the file. What it actually carries is
    #
    #   <author-notes><fn id="_fncrsp93pmc__"><label>(mark)</label>
    #     <p>Corresponding author.</p></fn>...
    #
    # with the corresponding contrib carrying <xref rid="_fncrsp93pmc__">. The
    # marker is a footnote reference rather than an attribute.
    if not out["corresponding_author"]:
        crsp_ids = {
            fn.get("id") for fn in article_meta.iter()
            if _local(fn.tag) == "fn" and fn.get("id")
            and "correspond" in _cell_text(fn, counts).lower()
        }
        if crsp_ids:
            for contrib in article_meta.iter():
                if _local(contrib.tag) != "contrib":
                    continue
                if (contrib.get("contrib-type") or "author") != "author":
                    continue
                rids = {x.get("rid") for x in contrib.iter()
                        if _local(x.tag) == "xref" and x.get("rid")}
                if rids & crsp_ids:
                    name = _person_name(contrib, counts)
                    if name:
                        out["corresponding_author"] = name
                        out["corresponding_author_source"] = "author_notes_footnote"
                        break

    out["author_list"] = names
    out["authors"] = ", ".join(names)
    # WHERE THE NAME CAME FROM, so the page can say whether to trust it.
    # `corresp="yes"` is the publisher's own structured claim; a footnote match
    # is OUR inference from prose. The Questions page shows this address before
    # someone sends an email about a possible error in a colleague's paper, and
    # getting the recipient wrong there is its own small harm -- the reader is
    # entitled to know which kind of evidence it rests on.
    out.setdefault("corresponding_author_source",
                   "structured" if out["corresponding_author"] else "")
    return out


#: An email as printed in running text. Deliberately NOT used to guess a NAME --
#: only to offer an address once a corresponding author has been identified some
#: other way, and always labelled as read from the body rather than a tagged field.
_EMAIL_IN_TEXT = re.compile(r"[\w.+%-]+@[\w-]+(?:\.[\w-]+)+")


def corresponding_email_from_text(text: str | None,
                                  name: str | None = None) -> tuple[str, str]:
    """An address printed in the paper's own text, and how far to trust it.

    LAST RESORT, and it says so. Publishers routinely print the corresponding
    address in a byline footnote that survives into the text layer while no
    structured `<email>` element exists: the cerebrolysin paper prints
    `Sharma@surgsci.uu.se` and `aruna.sharma@surgsci.uu.se`, neither in a
    tagged field.

    Returns `(email, confidence)` -- `surname_match` when the local part matches
    the corresponding author's surname, `unverified` otherwise. A caller MUST
    show the difference. An address matched to a name is worth offering; one we
    merely found somewhere in the document is worth offering only with a warning
    to check it, because the cost of being wrong is an email about a suspected
    error arriving at the wrong person.
    """
    found = _EMAIL_IN_TEXT.findall(text or "")
    if not found:
        return ("", "")
    if name:
        parts = str(name).split()
        surname = parts[-1].lower() if parts else ""
        if surname:
            for e in found:
                if surname in e.split("@", 1)[0].lower():
                    return (e, "surname_match")
    return (found[0], "unverified")


def article_metadata(root: ET.Element, counts: _Counter | None = None) -> dict:
    """What the document states about itself: who, where, when, and which issue.

    SCOPED TO `<article-meta>` wherever it exists. The previous implementation
    walked the whole tree taking the first match for each field, which is safe
    for the title but wrong for `year`: a paper with a reference list contains
    dozens of `<year>` elements, and the first one outside the front matter
    belongs to somebody else's paper. It happened to work only because front
    matter precedes the bibliography.
    """
    counts = counts if counts is not None else _Counter()
    meta: dict[str, Any] = {
        "title": "", "journal": "", "doi": "", "year": "",
        "volume": "", "issue": "", "pages": "",
        "authors": "", "author_list": [],
        "corresponding_author": "", "corresponding_email": "",
    }

    scope = _find_local(root, "article-meta") or root
    journal_scope = _find_local(root, "journal-meta") or root

    for node in scope.iter():
        tag = _local(node.tag)
        if tag == "article-title" and not meta["title"]:
            meta["title"] = _cell_text(node, counts)
        elif tag == "article-id" and node.get("pub-id-type") == "doi" and not meta["doi"]:
            meta["doi"] = _cell_text(node, counts)
        elif tag in ("doi", "pii") and not meta["doi"]:
            meta["doi"] = _cell_text(node, counts)
        elif tag == "volume" and not meta["volume"]:
            meta["volume"] = _cell_text(node, counts)
        elif tag == "issue" and not meta["issue"]:
            meta["issue"] = _cell_text(node, counts)
        elif tag == "year" and not meta["year"]:
            meta["year"] = _cell_text(node, counts)

    fpage = _find_local(scope, "fpage")
    lpage = _find_local(scope, "lpage")
    if fpage is not None:
        first = _cell_text(fpage, counts)
        last = _cell_text(lpage, counts) if lpage is not None else ""
        meta["pages"] = f"{first}-{last}" if last else first

    journal = _find_local(journal_scope, "journal-title")
    if journal is not None:
        meta["journal"] = _cell_text(journal, counts)

    meta.update(_authors(scope if scope is not root else root, counts))
    return meta


def _ref_field(ref: ET.Element, names: tuple[str, ...], counts: _Counter) -> str:
    for node in ref.iter():
        if _local(node.tag) in names:
            text = _cell_text(node, counts)
            if text:
                return text
    return ""


def extract_references(root: ET.Element, counts: _Counter | None = None) -> list[dict]:
    """The reference list, structured.

    `<ref-list>` is skipped by the section walker on purpose -- it carries no
    checkable statistics and would swamp the stage-1 budget -- but skipping it
    for the STATISTICS text is not a reason to discard it entirely. Checking a
    paper's citations for fabrication needs the bibliography, and no path in
    this codebase produced one for an XML-fetched paper.

    The shape matches the `references.json` already written by the older
    PDF-fetch pipeline, so the existing consumers keep working.

    Both citation styles are handled: `<element-citation>` tags every field,
    while `<mixed-citation>` marks them up inside running prose. Wiley emits
    the latter, and it is just as fully tagged -- authors, year, title, source,
    volume, issue, pages, DOI and PMID are all individually addressable.
    """
    counts = counts if counts is not None else _Counter()
    out: list[dict] = []

    for ref in root.iter():
        if _local(ref.tag) != "ref":
            continue
        authors: list[str] = []
        for node in ref.iter():
            if _local(node.tag) in ("name", "string-name"):
                sur = _first(node, ("surname",), counts)
                given = _first(node, ("given-names",), counts)
                full = " ".join(x for x in (sur, given) if x)
                if full:
                    authors.append(full)
            elif _local(node.tag) == "collab":
                text = _cell_text(node, counts)
                if text:
                    authors.append(text)

        ids = {}
        for node in ref.iter():
            if _local(node.tag) == "pub-id":
                kind = node.get("pub-id-type") or "other"
                ids.setdefault(kind, _cell_text(node, counts))

        fpage = _ref_field(ref, ("fpage",), counts)
        lpage = _ref_field(ref, ("lpage",), counts)
        year = _ref_field(ref, ("year",), counts)

        out.append({
            "id": len(out) + 1,
            "ref_id": ref.get("id") or "",
            "authors": authors,
            "title": _ref_field(ref, ("article-title", "chapter-title"), counts),
            "journal": _ref_field(ref, ("source",), counts),
            "volume": _ref_field(ref, ("volume",), counts) or None,
            "issue": _ref_field(ref, ("issue",), counts) or None,
            "pages": (f"{fpage}-{lpage}" if fpage and lpage else fpage or None),
            "year": int(year) if year.isdigit() else (year or None),
            "doi": ids.get("doi") or None,
            "pmid": ids.get("pmid") or None,
            # The citation exactly as printed. A fabrication check needs to
            # compare against what the authors actually wrote, not against our
            # reassembly of it from tags.
            "raw": _ref_field(ref, ("mixed-citation", "element-citation"), counts),
        })
    return out


def references_markdown(refs: list[dict]) -> str:
    """The reference list as text, for `paper_text` and for reading."""
    lines = ["# References", ""]
    for r in refs:
        bits = [", ".join(r.get("authors") or []) or "[no author]"]
        if r.get("year"):
            bits.append(f"({r['year']})")
        if r.get("title"):
            bits.append(r["title"] + ".")
        if r.get("journal"):
            bits.append(r["journal"] + ("," if r.get("volume") else "."))
        if r.get("volume"):
            bits.append(str(r["volume"]) + (f"({r['issue']})" if r.get("issue") else "")
                        + ("," if r.get("pages") else "."))
        if r.get("pages"):
            bits.append(str(r["pages"]) + ".")
        if r.get("doi"):
            bits.append(f"doi:{r['doi']}")
        lines.append(f"{r['id']}. " + " ".join(bits))
    return "\n".join(lines) + "\n"


def _sections(root: ET.Element, counts: _Counter) -> list[dict]:
    """
    Split the document into ordered sections, each with its text and tables.

    Sections stand in for the pages a PDF would have. Tables are collected from
    ``<body>``, ``<floats-group>`` and ``<app>`` alike — 55 tables in the working
    corpus live outside ``<body>`` and would otherwise be invisible.
    """
    sections: list[dict] = []
    seen_tables: set[int] = set()
    table_num = 0

    def add(title: str, texts: list[str], containers: list[ET.Element],
            cals: bool, keep_empty: bool = False):
        nonlocal table_num
        tables = []
        for container in containers:
            if id(container) in seen_tables:
                continue
            seen_tables.add(id(container))
            markup = _tables_in(container)
            if not markup:
                table_num += 1
                tables.append(_build_table(
                    container, None, table_num, title, counts, cals
                ))
                continue
            for el in markup:
                table_num += 1
                tables.append(_build_table(
                    container, el, table_num, title, counts,
                    cals or _local(el.tag) == "tgroup",
                ))
        # A HEADING WITH NO PROSE OF ITS OWN IS STILL THE PAPER'S STRUCTURE.
        #
        # MEASURED 2026-08-11 over 71 XML papers: 293 of 1,209 distinct section
        # titles (24%) never reached the extracted text, and they were
        # systematically the ones that matter -- `Methods`, `Results`,
        # `Discussion`, `Materials and Methods`, `Conclusions`. JATS puts a
        # top-level section's prose inside its CHILD `<sec>` elements, so
        # `_paragraphs()` on the container returns nothing, and `if texts or
        # tables` then dropped the container entirely, heading and all. The
        # children survived as `##` headings with no parent above them.
        #
        # Reported by Greg from the viewer: the Romano PDF reads `Method` /
        # `Participants and Procedures`, and the extracted text began at
        # `## Participants and Procedures` with no `Method` anywhere. A model
        # that cannot see where the Methods section starts cannot tell a number
        # reported in Methods from the same number reported in Results, which
        # is the distinction half the internal-consistency reasoning rests on.
        #
        # `keep_empty` is passed only for a section that HAS child sections, so
        # a genuinely empty `<sec>` is still dropped rather than emitting a
        # heading over nothing.
        if texts or tables or keep_empty:
            sections.append({"title": title, "texts": texts, "tables": tables})

    meta = article_metadata(root, counts)
    #: Figures already emitted by a section, so the sweep below cannot repeat one.
    seen_figs: set[int] = set()
    # Every abstract, not just the first: a JAMA Network Open article carries
    # `key-points`, `teaser` and the abstract proper as three siblings, and
    # taking `[0]` published whichever happened to come first.
    abstract_nodes = [n for n in root.iter() if _local(n.tag) == "abstract"]
    for node in abstract_nodes:
        add(_abstract_label(node), _abstract_texts(node, counts, seen_figs),
            [], False)

    is_elsevier = xml_flavour(root) == ELSEVIER

    # A PARAGRAPH OUTSIDE EVERY `<sec>` IS STILL THE PAPER.
    #
    # `walk` recognised only sections and containers, so prose sitting as a
    # DIRECT child of `<body>` was never read. MEASURED 2026-08-22,
    # `10.15585--mmwr.mm6923e2`: 34 KB of XML yielded 6,891 characters of
    # text, because that report's entire Methods and Results -- eleven `<p>`
    # children of `<body>`, about 7 KB -- sit outside any `<sec>`, and only
    # the Discussion onward is sectioned. The tool agent had to recover them
    # from PDF page images instead, which is why that paper's ledger is the
    # smallest in its batch (32 calls against 64-118 for its siblings). A
    # loader that silently returns a fifth of the paper is the same defect as
    # a channel that did not run: absence read as content.
    #
    # `collect_prose` is FALSE inside a `<sec>` -- `add()` above already ran
    # `_paragraphs` on it, and collecting again would emit every sectioned
    # paragraph twice. Runs are flushed at each section/container boundary so
    # document order survives a body that interleaves the two.
    def walk(el: ET.Element, depth: int = 0, collect_prose: bool = False):
        pending: list[ET.Element] = []

        def flush() -> None:
            if not pending:
                return
            texts = _prose_run(pending, counts, seen_figs)
            pending.clear()
            if texts:
                add(_UNSECTIONED_TITLE, texts, [], is_elsevier)

        for child in el:
            tag = _local(child.tag)
            if collect_prose and tag in _PROSE_TAGS:
                pending.append(child)
                continue
            if tag in ("sec", "section"):
                flush()
                title = _section_title(child, counts) or f"Section {len(sections) + 1}"
                if title.lower() in _SKIP_SECTIONS:
                    continue
                has_child_sections = any(
                    _local(g.tag) in ("sec", "section") for g in child)
                add(title, _paragraphs(child, counts, seen_figs),
                    _table_containers(child), is_elsevier,
                    keep_empty=has_child_sections)
                walk(child, depth + 1)
            elif tag == "ref-list":
                continue
            elif tag in ("body", "sections", "app-group", "app", "floats-group",
                         "back", "ack", "fn-group", "notes", "article",
                         "originalText", "doc", "serial-item"):
                flush()
                label = {"floats-group": "Floats", "app": "Appendix",
                         "app-group": "Appendix"}.get(tag)
                if label:
                    add(label, [], _table_containers(child), is_elsevier)
                walk(child, depth + 1, collect_prose=True)
        flush()

    walk(root)

    # Anything still unclaimed (tables outside every recognised container).
    leftovers = [c for c in _table_containers(root) if id(c) not in seen_tables]
    if leftovers:
        add("Unplaced tables", [], leftovers, is_elsevier)

    # FIGURES GET THE DOCUMENT-WIDE SWEEP TABLES ALREADY HAD.
    #
    # `_paragraphs` only ever saw a figure that was a DIRECT CHILD of a section
    # it was called on, and publishers overwhelmingly park floats elsewhere.
    # MEASURED 2026-08-22 over 120 papers with XML: of 550 <fig> elements only
    # 234 have a <sec> parent -- 219 sit under <floats>, 71 under
    # <floats-group>, the rest under <p>, <fig-group>, <body> or <app>. So the
    # majority of captions never reached the text at all, and a finding
    # quoting one could not be anchored or highlighted.
    #
    # Captions are prose and carry no grid, so unlike a table there is nothing
    # here that could pour columns into the text -- the reason `_collect`
    # skips <fig> beside <table-wrap> does not apply to the caption itself.
    unclaimed = [
        block for block in (
            _fig_block(f, counts) for f in root.iter()
            if _local(f.tag) in ("fig", "figure") and id(f) not in seen_figs
        ) if block
    ]
    if unclaimed:
        add("Figures", unclaimed, [], is_elsevier)

    if meta["title"]:
        sections.insert(0, {"title": meta["title"], "texts": [], "tables": []})
    return sections


def table_index_entry(t: dict) -> dict:
    """One table's IDENTITY, without its cells.

    Everything a reader needs to decide whether they want the grid: which table
    it is, what it is called, how big it is, and whether it is usable at all.
    """
    return {
        "table_num": t.get("table_num"),
        "id": t.get("id") or "",
        "label": t.get("label") or "",
        "caption": t.get("caption") or "",
        "section": t.get("section") or "",
        "n_rows": t.get("n_rows"),
        "width": t.get("width"),
        "n_header_rows": t.get("n_header_rows"),
        "n_footnotes": len(t.get("footnotes") or []),
        # See `header_adjuncts`. Emitted to the MODEL and carried to the floor
        # by `prepass`, because a field that reaches only one of them is the
        # asymmetry that produced the footnote defect.
        "header_adjuncts": t.get("header_adjuncts") or [],
        "image_only": bool(t.get("image_only")),
        "alignment_uncertain": bool(t.get("alignment_uncertain")),
    }


#: Character budget for the `cells` view. A paid validation run on
#: `10.1002--eat.24415` caught `get_table` -- the tool built to STOP results
#: spilling -- spilling on that paper's 60x7 Table 2 at 69,971 characters.
#:
#: Budgeted by SIZE rather than by row count, for two reasons. Cell labels vary
#: enormously in length (Romano's average 153 characters per cell against
#: Table 1's 85), so a fixed row count bounds nothing. And `cells` does not
#: partition by row label: Romano's Table 2 has 60 rows and only 12 DISTINCT
#: row labels, because a merged label spans its whole block -- so windowing by
#: label returned the entire table and looked like it had worked.
#:
#: 10 kB, not 24 kB. The observed spill was at 69,971 characters and the wave-3
#: one at 160,395, so the true cap sits somewhere below 70 kB and is measured in
#: TOKENS -- which for a table of numbers and unicode arrows is a far worse
#: ratio than for prose. A budget that leaves the total payload around 25 kB is
#: the only one that makes "this tool cannot spill" a property rather than a
#: hope. `data` carries the whole grid regardless, so the cost of a tight
#: budget is extra calls only when feeding `check_table`, never lost content.
_CELLS_CHAR_BUDGET = 10000

#: TOTAL payload ceiling. Below the 69,971 that the harness refused, with room
#: for the token/character ratio of a table of numbers being worse than prose.
_TABLE_CHAR_BUDGET = 36000

#: `data` gets first claim on the budget, and it is enough for every table in
#: the corpus: the largest full grid is 30,393 characters
#: (`10.1017--s0033291723003501` Table 2, 236x13) against a median of 2,018.
#: THE GRID IS THE VIEW THAT MUST NOT LOSE A NUMBER, so when a table is big
#: enough that grid and cells cannot both fit, `cells` yields -- a caller can
#: page `cells` back, but a number missing from the grid is a number the caller
#: does not know exists. The grid's share is the total MINUS the measured cost
#: of the fixed fields, computed per table rather than reserved as a flat
#: allowance -- a flat 9,000 left the one 236x13 table 3,393 characters short
#: of its own grid, which is the whole difference between complete and not.


#: How many worked examples to keep when the same warning fires many times.
_WARNING_EXAMPLES = 3


def _collapse_warnings(warnings: list) -> list[str]:
    """One line per KIND of warning, with a count and a few examples.

    A per-row warning that quotes the row is the duplication problem again in
    another field: `10.1017--s0033291723003501` Table 2 emitted 235 separate
    "ragged row [...]" warnings totalling 36,445 characters -- three times the
    size of the grid they describe, and larger than every other part of the
    payload combined. Two hundred and thirty-five copies of one fact is not
    two hundred and thirty-five facts.

    Nothing is lost that a reader can act on: the kind, the exact count, and
    enough examples to see the shape.
    """
    groups: dict[str, list[str]] = {}
    for w in warnings or []:
        text = str(w)
        # Strip the quoted row content, which is what varies between copies.
        key = re.sub(r"\[.*?\]", "[...]", text)
        key = re.sub(r"\d+", "N", key)
        groups.setdefault(key, []).append(text)
    out: list[str] = []
    for key, members in groups.items():
        if len(members) == 1:
            out.append(members[0])
            continue
        examples = "; ".join(members[:_WARNING_EXAMPLES])
        out.append(f"{len(members)}x {key} -- e.g. {examples}")
    return out


def _window(items: list, lo: int, last: int | None, budget: int) -> tuple[list, int]:
    """`items[lo-1:hi]` where `hi` is as far as `budget` characters reach.

    Returns `(slice, hi)`. Always yields at least one item, so a single
    oversized row still comes back rather than silently vanishing.
    """
    if last:
        hi = min(len(items), last)
    else:
        hi, spent = lo - 1, 0
        for i in range(lo - 1, len(items)):
            spent += len(json.dumps(items[i], ensure_ascii=False))
            if spent > budget and hi >= lo:
                break
            hi = i + 1
    return items[lo - 1:hi], hi


def get_table(xml_path: str | Path, table_num: int,
              first_row: int | None = None,
              last_row: int | None = None) -> dict[str, Any]:
    """ONE table, in full, with the identity the checking tools need.

    WHY THIS EXISTS. `extract_xml_text_with_tables` returns every grid at once.
    On a real clinical paper that is a 184 kB payload of which 75 kB is tables,
    and the harness caps tool results -- so it spilled to a file and the model
    recovered roughly 40% of it with six blind `Read` calls at guessed line
    offsets. Nine of twenty-eight run logs in the working corpus contain such a
    spill. The tables were extracted perfectly and delivered by luck.

    Fetching one table at a time cannot spill, and it carries the two things
    that were being lost at the boundary into the checking tools: the LABEL, so
    a finding can say which table it is about, and the FOOTNOTES, which are what
    decide whether `142 (71.0)` is `n (%)` or `mean (SD)`.

    EXCEPT THAT IT DID SPILL, and only a paid run found it. On Romano's 60x7
    Table 2 this returned 58,217 characters and the harness refused it. The
    earlier claim that `data` and `cells` are "genuinely different views" was
    wrong in the way that mattered: of the 43,960 characters in `cells`, 25,302
    (58%) were `row_label` repeated once per column and `col_label` repeated
    once per row -- both of which are already in `data`, once each. `raw` was
    6,850 characters, under 12% of it.

    So `cells` is now WINDOWED to a `_CELLS_CHAR_BUDGET` character budget, with
    `data` -- the compact grid, and the whole table -- always returned in full
    beside it. The window is stated in the result, never silently applied:
    `cells_row_window`, `cells_total` and a `how_to_get_more` string naming the
    exact next call.

    NAMES CORRECTED 2026-08-12. This paragraph previously described a
    `_CELL_ROWS_PER_CALL` row budget and keys `cells_window` / `cells_rows_total`,
    none of which exist. A docstring naming fields a caller cannot find is worse
    than none: it invites the reader to conclude the paging contract is
    imaginary, which is close to what the archive shows actually happened.

    AND THE STATED CONTRACT IS NOT ENOUGH ON ITS OWN. Measured over 51 archived
    calls, `cells` delivered 2,269 of 3,714 cells (61%); 10 of 33 tables came
    back short, and in 9 of those 10 the model made exactly ONE call, received
    `how_to_get_more` naming the next one, and stopped. `data_is_complete` is
    keyed on the GRID and was true on all 51, which is honest about `data` and
    reads as an all-clear about `cells`. Stating a window is necessary; saying
    what SKIPPING it costs is what makes it act on.
    """
    counts = _Counter()
    try:
        root = ET.parse(str(xml_path)).getroot()
    except (ET.ParseError, OSError) as exc:
        return {"error": f"could not parse {xml_path}: {exc}",
                "table_num": table_num, "found": False}

    root, _warnings = _article_root(root)
    tables = [t for sec in _sections(root, counts) for t in sec["tables"]]
    for t in tables:
        if t.get("table_num") != table_num:
            continue

        # THE GRID IS COMPLETE. Every number the paper printed is in `data` on
        # the first call, so no reader and no model can end up with a partial
        # table by failing to follow a pointer. That is affordable because the
        # grid is SMALL: measured over all 475 corpus tables, the full `data`
        # is a median of 2,018 characters, p95 6,327, and exactly ONE table of
        # 475 exceeds 20,000. It was never `data` that blew the limit.
        #
        # `cells` is what blows it -- the {raw, row_label, col_label} form
        # `check_table` consumes, roughly four times the size for the same
        # content because both labels repeat on every cell. That one is
        # windowed, and it is the only thing pagination affects.
        cells = list(t.get("cells") or [])
        grid = list(t.get("data") or [])
        lo = max(1, first_row or 1)

        # The single outlier -- `10.1017--s0033291723003501` Table 2, 236x13,
        # 30,393 characters of grid -- still has to be cut, or the payload
        # exceeds the limit whatever else is dropped. It is cut LAST and said
        # loudest, because a truncated grid is the one case where a caller can
        # be missing a printed number.
        # The overhead is MEASURED, not reserved. A flat allowance left the one
        # 236x13 table 3,393 characters short of its own grid, which is the
        # difference between "every table complete" and "all but one".
        # WHAT GETS SHED, IN ORDER. The grid is the only view that carries a
        # number the caller cannot get any other way, so everything else yields
        # to it: `spans` (a merge diagnostic) goes first, then `cells` (a
        # reformatting of the grid, pageable), and the grid itself is cut only
        # if the two together still are not enough. Shedding spans is what
        # takes the corpus from 474 of 475 complete grids to 475 of 475 -- the
        # last table spends 6,000 characters on span records.
        essential = {
            **table_index_entry(t),
            "headers": t.get("headers"),
            "footnotes": t.get("footnotes") or [],
            "warnings": _collapse_warnings(t.get("warnings") or []),
            "normalizations": dict(counts),
        }
        grid_budget = _TABLE_CHAR_BUDGET - len(json.dumps(essential, ensure_ascii=False))
        grid_cost = len(json.dumps(grid, ensure_ascii=False))

        # A CONTINUATION call does not re-send the whole grid. The caller got it
        # complete on call one, and re-sending it left nothing for `cells`: on
        # the 236-row table the cell budget collapsed to about zero and the walk
        # returned ONE ROW per call, so 1,845 cells would have taken 237 calls
        # and the loop looked like it had stalled. On a continuation the grid
        # slice is just context for the cells being returned.
        resuming = bool(first_row) and first_row > 1
        if resuming:
            rows, row_hi = _window(grid, lo, last_row, 4000)
            grid_full = True          # it was complete on the first call
        elif grid_cost <= grid_budget:
            rows, row_hi, grid_full = grid, len(grid), True
        else:
            rows, row_hi = _window(grid, lo, last_row, grid_budget)
            grid_full = False
        spare = grid_budget - len(json.dumps(rows, ensure_ascii=False))
        spans = _window(list(t.get("spans") or []), lo, None, min(6000, max(0, spare)))[0]
        grid_budget -= len(json.dumps(spans, ensure_ascii=False))

        # `cells` gets whatever the grid left. On a big table that is little or
        # nothing, and that is the correct trade: the grid carries every number.
        # Capped as well as bounded: letting `cells` expand into every spare
        # byte pushed the corpus p95 from 19,687 to 30,380 characters for no
        # gain, since a caller feeding `check_table` pages it anyway.
        cell_budget = max(1200, min(
            _CELLS_CHAR_BUDGET,
            grid_budget - len(json.dumps(rows, ensure_ascii=False)),
        ))
        by_row: dict[int, list[dict]] = {}
        for c in cells:
            by_row.setdefault(int(c.get("row") or 0), []).append(c)
        cell_hi, spent = lo - 1, 0
        for r in range(lo, row_hi + 1):
            spent += sum(len(json.dumps(c, ensure_ascii=False))
                         for c in by_row.get(r, []))
            if spent > cell_budget and cell_hi >= lo:
                break
            cell_hi = r
        cell_hi = max(lo, cell_hi)
        window = [c for c in cells if lo <= int(c.get("row") or 0) <= cell_hi]

        out = {
            "found": True,
            **table_index_entry(t),
            # NEVER WINDOWED. A section band is a fact about the whole printed
            # table, and a caller paging through rows still needs to know which
            # band governs the ones it is looking at.
            "sections": list(t.get("sections") or []),
            "headers": t.get("headers"),
            "data": rows,
            "data_is_complete": grid_full,
            "rows_total": len(grid),
            "cells": window,
            "cells_total": len(cells),
            "cells_row_window": [lo, cell_hi],
            "footnotes": t.get("footnotes") or [],
            "spans": spans,
            "spans_total": len(t.get("spans") or []),
            "graphic_href": t.get("graphic_href"),
            "warnings": _collapse_warnings(t.get("warnings") or []),
            "normalizations": dict(counts),
        }
        # Stated, never silent -- and the two cases are stated DIFFERENTLY,
        # because only one of them means a number is missing.
        notes = []
        if not grid_full:
            notes.append(
                f"THE GRID IS TRUNCATED: `data` holds rows {lo}-{row_hi} of "
                f"{len(grid)}. Numbers outside that range are NOT in this "
                f"result. This happens on roughly one table in 475."
            )
        if cell_hi < len(grid):
            # WORDED AS A COST, NOT AS REASSURANCE. This note used to end
            # "so nothing is missing; page `cells` only if you are feeding
            # check_table" -- both clauses true, and together the reason the
            # paging never happened. MEASURED over 51 archived get_table calls:
            # 2,269 of 3,714 cells delivered (61%), 10 of 33 tables short, and
            # in 9 of those 10 the model made exactly ONE call, was handed this
            # string naming the exact next call, and never made it. Feeding
            # check_table is not a special case -- it is the only thing `cells`
            # is for -- so a sentence framing it as conditional reads as
            # permission to stop, and "nothing is missing" reads as an all-clear
            # about a cell list that was in fact truncated.
            missing = len(grid) - cell_hi
            notes.append(
                f"`cells` HOLDS ONLY ROWS {lo}-{cell_hi} OF {len(grid)}: "
                f"{missing} row(s) of this table are absent from `cells`, and "
                f"any check you run on them will silently skip those rows."
                + (" The compact grid in `data` IS complete, so no printed "
                   "number is hidden from you -- but `data` is not the input "
                   "check_table takes. Page `cells` to the end before checking."
                   if grid_full else "")
            )
        if notes:
            out["how_to_get_more"] = " ".join(notes) + (
                f" Continue with get_table(xml_path, {table_num}, "
                f"first_row={min(row_hi, cell_hi) + 1})."
            )
        return out
    return {
        "found": False,
        "table_num": table_num,
        "error": (f"no table {table_num} in this document; it has "
                  f"{len(tables)} table(s), numbered "
                  f"{[t.get('table_num') for t in tables]}"),
        "available": [table_index_entry(t) for t in tables],
    }


def extract_xml_text_with_tables(
    xml_path: str | Path,
    max_chars: int = 50000,
    first_section: int | None = None,
    last_section: int | None = None,
    tables: str = "index",
) -> dict[str, Any]:
    """
    Extract body text and tables from a publisher XML full text.

    Mirrors :func:`forensic_metascience_ai_toolkit.extraction.pdf.extract_text_with_tables`
    key-for-key so callers and prompts can treat the two interchangeably.
    Sections stand in for pages; ``page`` is always ``None`` because XML has
    none, and inventing one would put a fabricated citation in a finding.

    Table content is deliberately NOT inlined into ``text`` — only a
    placeholder. If the prose carried the numbers, the model could transcribe
    from text that has already lost the column alignment, which is the exact
    failure this module exists to remove. There is one representation of a
    table, and it is the grid.

    Args:
        xml_path: Path to the XML file
        max_chars: Cap on returned text (tables are never truncated)
        first_section: 1-based first section to include (inclusive)
        last_section: 1-based last section to include (inclusive)

    Returns:
        Dict with 'text', 'tables', 'pages', 'num_pages', 'truncated' plus
        XML-only keys ('source_format', 'unit', 'article_meta', 'n_tables',
        'n_tables_image_only', 'warnings', 'normalizations').
    """
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"XML not found: {xml_path}")

    counts = _Counter()
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as exc:
        # Returned, not raised: a malformed publisher file must not burn a
        # billed stage. Publisher XML is not under our control.
        return {
            "error": f"XML parse failed: {exc}",
            "text": "", "tables": [], "pages": [], "num_pages": 0,
            "pages_extracted": [], "truncated": False,
            "source_format": UNKNOWN, "unit": "section",
            "article_meta": {}, "n_tables": 0, "n_tables_image_only": 0,
            "warnings": [f"unparseable XML: {exc}"], "normalizations": {},
        }

    # Record the dialect of the file AS IT ARRIVED. Reading it after the
    # unwrap would report a PMC article set as plain JATS and lose the
    # provenance that explains where the tables came from.
    flavour = xml_flavour(root)
    root, warnings = _article_root(root)
    meta = article_metadata(root, counts)
    sections = _sections(root, counts)

    total = len(sections)
    lo = max(1, first_section or 1)
    hi = min(total, last_section or total)
    selected = sections[lo - 1:hi] if total else []

    pages = []
    all_tables = []
    for i, sec in enumerate(selected, start=lo):
        body = "\n\n".join(sec["texts"])
        refs = []
        for t in sec["tables"]:
            all_tables.append(t)
            name = t["label"] or f"Table {t['table_num']}"
            shape = (
                "image only, no cells" if t["image_only"]
                else f"{t['n_rows']} rows x {t['width']} cols"
            )
            refs.append(f"[{name}: {t['caption']} — {shape}; see tables]")
        if refs:
            body = (body + "\n\n" + "\n".join(refs)).strip()
        pages.append({
            "page_num": i,
            "unit": "section",
            "section": sec["title"],
            "text": body,
            "tables": [
                {"table_num": t["table_num"], "data": t["data"]}
                for t in sec["tables"]
            ],
        })

    full_text = "\n\n".join(
        f"## {p['section']}\n{p['text']}".rstrip() for p in pages
    )

    # THE REFERENCES ARE PART OF THE PAPER, and until now the checks never saw
    # them. Reported by Greg from the viewer, 2026-08-11: "why aren't the
    # references also extracted into the 'what the checks read' pane? They
    # absolutely should be -- they are part of the paper."
    #
    # `extract_references` has worked since Wave 2a and its 48 records reach the
    # bundle payload, so the VIEWER could list them. `references_markdown` was
    # written to render them into text and was called by NOTHING -- flagged by
    # `lint-inert` the same morning as an unconsumed definition, hours before
    # Greg hit the symptom from the other end. Built, tested, never consumed.
    #
    # Appended at the END on purpose: the click-to-source sync and every quote
    # search index `body_text` by character offset, so anything inserted ahead
    # of the body would shift every existing anchor.
    #
    # What it buys beyond the pane: a citation year that contradicts the text,
    # a reference to a retracted paper, a "(2020)" in the prose with no 2020
    # entry in the list -- none of which is checkable against a document whose
    # reference list was deleted before the model read it.
    try:
        _refs = extract_references(root, counts)
        if _refs:
            full_text = full_text.rstrip() + "\n\n" + references_markdown(_refs)
    except Exception:  # noqa: BLE001
        # Recorded rather than silent: a paper whose references we could not
        # parse must not look like a paper with none.
        full_text = full_text.rstrip() + (
            "\n\n# References\n\n[The reference list could not be parsed from "
            "this document. It is not absent from the paper.]\n")

    truncated = False
    if len(full_text) > max_chars:
        truncated = True
        full_text = full_text[:max_chars] + _TRUNCATION_NOTE
        budget = max_chars
        for p in pages:
            if budget <= 0:
                p["text"] = (
                    "[truncated — request this section via first_section/"
                    "last_section]"
                )
                continue
            if len(p["text"]) > budget:
                p["text"] = p["text"][:budget] + " …[truncated]"
            budget -= len(p["text"])

    image_only = sum(1 for t in all_tables if t["image_only"])
    if image_only:
        warnings.append(
            f"{image_only} table(s) are images in the XML and have no cells; "
            "get them from the PDF or record them as unchecked"
        )
    uncertain = sum(1 for t in all_tables if t["alignment_uncertain"])
    if uncertain:
        warnings.append(
            f"{uncertain} table(s) had ragged rows (alignment_uncertain); "
            "reconcile against the PDF before reporting from them"
        )
    if flavour == UNKNOWN:
        warnings.append(
            f"unrecognised XML root <{_local(root.tag)}>; tables may be missed"
        )

    # INDEX by default, grids on request.
    #
    # Returning every grid produced a 184 kB payload on a real paper, which the
    # harness cannot deliver: it spilled to a file and the model recovered
    # about 40% of it by guessing line offsets. An index of the same document is
    # a couple of kB, and `get_table` fetches the ones that matter -- so the
    # model chooses what to read instead of sampling what it was handed.
    #
    # `tables="full"` restores the old behaviour for callers that genuinely
    # want everything (the CLI, tests, anything not going through a model).
    if tables == "full":
        table_payload = all_tables
        page_tables = True
    else:
        table_payload = [table_index_entry(t) for t in all_tables]
        page_tables = False

    if not page_tables:
        for p in pages:
            p["tables"] = [{"table_num": t["table_num"]} for t in p["tables"]]
            # `full_text` is literally the join of these, section headers and
            # all, so carrying them again doubles the payload for nothing. On
            # Romano that duplication was 45 kB -- more than the tables. The
            # section list stays, because knowing what sections exist is how a
            # caller decides what to request.
            p.pop("text", None)

    return {
        "text": full_text,
        "tables": table_payload,
        "tables_mode": "full" if page_tables else "index",
        "how_to_get_a_table": (
            None if page_tables else
            "Cells are not included here. Call get_table(xml_path, table_num) "
            "for the full grid of any table listed above, with its footnotes."
        ),
        "pages": pages,
        "num_pages": total,
        "pages_extracted": [lo, hi] if pages else [],
        "truncated": truncated,
        "source_format": flavour,
        "unit": "section",
        "article_meta": meta,
        "n_tables": len(all_tables),
        "n_tables_image_only": image_only,
        "warnings": warnings,
        "normalizations": dict(counts),
    }


def extract_xml_text(xml_path: str | Path, max_chars: int = 2_000_000) -> str:
    """Body text only — mirrors :func:`extraction.pdf.extract_text`."""
    return extract_xml_text_with_tables(xml_path, max_chars=max_chars)["text"]


def extract_xml_tables(xml_path: str | Path) -> list[dict[str, Any]]:
    """Tables only — mirrors :func:`extraction.pdf.extract_tables`.

    Full grids, not the index: this is a Python API for callers that asked for
    tables and want tables. The index exists for the MCP surface, where the
    payload has to cross a size cap.
    """
    return extract_xml_text_with_tables(xml_path, tables="full")["tables"]


def find_body_md(paper_dir: str | Path) -> Path | None:
    """The paper's body markdown, preferring ``body.md``.

    The harvest writes ``<dirname>_from_pdf_body.md`` and never ``body.md``.
    A resolver that only looks for the literal name treats a paper with tens
    of kilobytes of extracted body as having no text -- measured 2026-08-20
    on `nina_mazar/grok_test`, where five PDF-only folders each held a
    harvest body (11-70 KB) and `metascience batch` skipped them as
    "scanned or corrupt".
    """
    paper_dir = Path(paper_dir)
    if not paper_dir.is_dir():
        return None
    from .markdown_out import body_path
    canonical = body_path(paper_dir)
    if canonical.exists():
        return canonical
    literal = paper_dir / "body.md"
    if literal.exists():
        return literal
    harvest = paper_dir / f"{paper_dir.name}_from_pdf_body.md"
    if harvest.exists():
        return harvest
    # `<stem>_from_xml.md` / `<stem>_from_html.md` are DELIBERATELY NOT HERE.
    # See `_FETCHPDF_MARKDOWN_IS_NOT_A_SOURCE`.
    return None


#: WHY `<stem>_from_xml.md` AND `<stem>_from_html.md` ARE NEVER READ, even
#: though 418 and 37 of them sit in the corpora and this repo otherwise finds
#: only 313 body markdowns across 1,293 papers.
#:
#: `fetchpdf --to-markdown` writes them, and its own help text promises
#: "tables stay canonical HTML so colspan/rowspan survive, which Markdown
#: cannot express". MEASURED 2026-08-22 across all 418 papers holding both an
#: XML and a `_from_xml.md`: **152 (36%) declare fewer tables in their front
#: matter than the XML actually contains**, nearly all `tables: 0`, one Lancet
#: paper with 7. The content is not dropped -- it is dissolved into the prose
#: with no delimiters:
#:
#:     2-AG at post-injury5.111.870.232.730.007**AEA at post-injury0.21...
#:
#: which is B=5.11, SE=1.87, beta=0.23, t=2.73, p=0.007. And the header says
#: `tables_not_machine_readable: 0` -- it certifies that nothing was lost,
#: which is what makes it dangerous rather than merely lossy.
#:
#: The cause is the one this module already guards against: some publishers
#: nest `<table-wrap>` INSIDE a `<p>`, so paragraph flattening must skip table
#: markup. `extract_xml_text_with_tables` gets those same papers right (the
#: measured example: 3 tables, 3 `[Table N: ...]` placeholders, 0 inlined
#: rows), which is why `markdown_out` builds `markdown/body.md` from THIS
#: chain and never from fetchpdf's output.
#:
#: A fixed fetchpdf does not retire this: 418 files are already on disk and a
#: corpus can be fetched with any version.
_FETCHPDF_MARKDOWN_IS_NOT_A_SOURCE = ("_from_xml.md", "_from_html.md")


def find_xml(paper_dir: str | Path) -> Path | None:
    """The paper's XML full text, preferring ``<dirname>.xml``."""
    paper_dir = Path(paper_dir)
    if not paper_dir.is_dir():
        return None
    preferred = paper_dir / f"{paper_dir.name}.xml"
    if preferred.exists():
        return preferred
    candidates = [
        x for x in sorted(paper_dir.glob("*.xml"))
        if "supplementary" not in x.stem.lower()
    ]
    return candidates[0] if candidates else None


def find_pdf(paper_dir: str | Path) -> Path | None:
    """The paper's MAIN PDF, preferring ``<dirname>.pdf``.

    Supplement-looking filenames are excluded: reading an appendix as though it
    were the paper would let the supplement gate find its own citations in it.
    The hint list is `supplements._SI_HINTS` itself rather than a copy, so the
    two cannot drift apart -- a file this function skipped and `present_files`
    did not count would be invisible to both halves of the gate.
    """
    from ..supplements import _SI_HINTS

    paper_dir = Path(paper_dir)
    if not paper_dir.is_dir():
        return None
    preferred = paper_dir / f"{paper_dir.name}.pdf"
    if preferred.exists():
        return preferred
    candidates = [
        p for p in sorted(paper_dir.glob("*.pdf"))
        if not any(h in p.name.lower() for h in _SI_HINTS)
    ]
    return candidates[0] if candidates else None


#: Markers that identify a JATS/NLM article as the PUBLISHER'S OWN markup.
#:
#: CHOSEN BY COMPARING REAL FILES, after the first cut of this list failed on
#: the very thing it was written to catch. That cut included `<article-meta>`,
#: and ScienceBeam's JATS output emits `<article-meta>` -- so a synthesised file
#: was classified `publisher`, which is precisely the laundering this function
#: exists to prevent. MEASURED on one paper converted both ways:
#:
#:     marker                    publisher   sciencebeam
#:     DOCTYPE / JATS DTD                3             0
#:     <journal-meta>                    1             0
#:     <issn>                            2             0
#:     <publisher-name>                  5             0
#:     article-id pub-id-type            7             0
#:     <pub-date>                        2             0
#:     <article-meta>                    1             1   <- the one I used
#:
#: What survives is JOURNAL AND PUBLISHER IDENTITY. A converter reading a PDF
#: cannot invent an ISSN, a publisher's name, a DOCTYPE declaration or a
#: pub-id-type registry; those exist because a production system wrote them.
#: Article-level structure proves nothing, because reconstructing article-level
#: structure is exactly what a converter does.
_PUBLISHER_XML = re.compile(
    r"<!DOCTYPE\s+article|JATS-|//NLM//DTD|dtd-version\s*="
    r"|<journal-meta|<issn|<publisher-name"
    r"|<article-id[^>]*pub-id-type"
    # Elsevier's full-text API root, and the namespace it is served under.
    # It is publisher markup by definition -- there is no converter that
    # emits it -- but it carries none of the JATS markers above: its ISSN is
    # `<prism:issn>`, which `<issn` does not match. So it scored `unknown`,
    # every caller reads `unknown` as `derived`, and Elsevier full texts were
    # being stripped of an authority they had earned. MEASURED 2026-08-22 on
    # `10.1016--j.jpsychires.2018.04.010`, whose tables CLAUDE.md already
    # treats as first-class; the text provenance disagreed with them.
    r"|<full-text-retrieval-response"
    r"|elsevier\.com/xml/svapi/article",
    re.I)

#: Markers that identify XML as something WE (or a tool) derived from a PDF.
#: GROBID and ScienceBeam both emit TEI and both stamp an `<application>` in
#: the encoding description; `pdfalto` may appear in the same block.
_DERIVED_XML = re.compile(
    r"GROBID|sciencebeam|pdfalto|<TEI[ >]|xmlns=\"http://www\.tei-c\.org",
    re.I)


def xml_provenance(path: "Path | str") -> str:
    """`"publisher"`, `"derived"`, or `"unknown"` for an XML file.

    WHY THIS DISTINCTION IS LOAD-BEARING. Throughout this codebase, XML means
    the marked-up truth -- `prepass.paper_tables` says so in as many words:
    "it is not an extraction at all, it is the marked-up truth, and no model
    beats reading the answer." MEASURED over the 61 evaluation papers that ship
    publisher XML, glyph debris is ZERO in 61 of 61, which is why that privilege
    is deserved: there is no font layer to corrupt.

    A JATS file SYNTHESISED from a PDF earns none of it. ScienceBeam and GROBID
    parse the PDF with `pdfalto`, which reads the same text layer that gives us
    `65 /C6 1.17` -- so a derived JATS carries the identical corruption inside
    much better structure. Letting it answer to the same label would launder an
    extraction into an authority, which is the failure this repository keeps
    finding in new clothes.

    UNKNOWN IS TREATED AS DERIVED BY EVERY CALLER, and that direction is the
    whole point: an XML whose origin we cannot establish must not inherit a
    privilege granted to files we can. Being unable to tell is not evidence that
    it is publisher markup.
    """
    try:
        head = Path(path).read_text(encoding="utf-8", errors="replace")[:20_000]
    except OSError:
        return "unknown"
    derived = bool(_DERIVED_XML.search(head))
    publisher = bool(_PUBLISHER_XML.search(head))
    # Derived wins a tie: a converter that emits JATS-shaped elements while
    # stamping its own name is still a converter.
    if derived:
        return "derived"
    if publisher:
        return "publisher"
    return "unknown"


#: Phrases that only appear on a publisher ACCESS WALL -- the landing page a
#: fetcher gets when the article itself is behind a paywall. Deliberately
#: purchase-flow specific: "sign in" and "subscribe" alone sit in the chrome of
#: plenty of genuine full-text pages, so they are not on this list.
_ACCESS_WALL_MARKERS = (
    "purchase 24 hour online access",
    "purchase access",
    "add to cart",
    "get access to the full version of this article",
    "rent this article",
    "buy this article",
    "restricted access",
    "checkout",
    "start 2 week free trial",
    "click the button below for the full-text content",
)

#: How much longer the PDF must be before an access wall is displaced. A
#: landing page is title + abstract + references; the article is several times
#: that. Requiring a clear margin rather than a single character keeps the
#: chosen source stable when the two are of a size.
_ACCESS_WALL_PDF_MARGIN = 1.5


def looks_like_access_wall(text: str) -> tuple[bool, list[str]]:
    """Is this HTML the article, or the shop front in front of it?

    MEASURED 2026-08-22 on 10.1177--0093854811403123: the fetched
    `.fulltext.html` is the SAGE landing page -- title, abstract, references,
    and "Purchase 24 hour online access ... Article - $37.50 ... Add to cart".
    13,838 characters, ZERO statcheck-eligible statistics, no tables. The PDF
    beside it yields 41,510 characters and 13 statistics.

    `paper_text_with_source` ranks HTML above the PDF because HTML preserves
    table structure a text layer cannot -- true of a real full text, and
    exactly backwards for a shop front. Everything reading `paper_text` on that
    paper (the value register, the text-forensics word count, the supplement
    gate) was reading the purchase page.

    TWO CONDITIONS, because either alone is wrong -- and the second one lives
    in the CALLER. Purchase chrome appears in the sidebar of plenty of genuine
    full-text pages, so markers alone must not demote anything; the caller
    additionally requires the PDF to be substantially longer before it
    displaces this text. That makes a false positive here cost nothing.

    A section-word test was tried as the second condition and DOES NOT WORK:
    "method" and "discussion" both appear in this very landing page, inside its
    reference-list titles. Substring matching over a page that carries its own
    bibliography cannot tell a body from a citation.

    WHY NOT IN `find_html`'s VALIDATOR. `html.find_html` already refuses
    landing pages, and this page went through it: `validate_t2` was installed
    on the measuring machine and passed 13,838 characters of abstract plus
    purchase chrome (its floors are 5,000 characters and "not an abstract-length
    stub"), while the dependency-free fallback needs an interstitial phrase to
    DOMINATE the page. Tightening either would make the HTML absent EVERYWHERE
    -- including `extract_html`'s tables -- for any full text that happens to
    carry purchase chrome in a sidebar. This check is narrower on purpose: it
    only reorders `paper_text`'s fallback chain, and only when a longer PDF is
    actually sitting there.

    Returns the markers found, so a caller can say WHY.
    """
    low = (text or "").lower()
    found = [m for m in _ACCESS_WALL_MARKERS if m in low]
    return len(found) >= 2, found


def paper_text(paper_dir: str | Path) -> str:
    """
    The paper's text, whatever form it arrived in.

    Thin wrapper over `paper_text_with_source`, which additionally reports
    WHICH source in the fallback chain supplied the text -- see its docstring
    for the chain, the measurements behind it, and the ""-means-UNKNOWN rule.
    """
    return paper_text_with_source(paper_dir)[0]



#: A markdown pipe row whose cells are empty except the first -- the shape a
#: converter writes when it wrapped a FLATTENED prose line in pipes instead of
#: recovering columns. It looks like a table to a reader and to a model, and it
#: carries no column association at all.
_DEGENERATE_ROW = re.compile(r"^\s*\|[^|]+\|(?:\s*\|)+\s*$", re.MULTILINE)

#: Three or more numbers on one line: a data row rather than prose.
_DATA_ROW_NUMS = re.compile(r"-?\d+\.?\d*")


def ingested_markdown_degeneracy(text: str) -> dict:
    """How badly does a `body.md` WE DID NOT WRITE repeat or fake its tables?

    The source chain ranks `body.md` first on the reasoning that pre-extracted
    markdown is "cheapest and most faithful". That is true of markdown WE wrote,
    where `jats.py` emitted a `[Table N: ...]` placeholder and the columns
    survive in the table objects. It is not true of a `body.md` already on disk
    from an older pipeline or a converter that is not ours, and the rank was
    inherited without the assumption being rechecked.

    MEASURED 2026-08-26 on `benchmarks/paper_reviews/runs/apple_cider`, whose `source.json` records
    `source_channel: body_md` with `source_file: null`:

        ingested body.md         41,085 chars   62 duplicated data rows
        our docling extraction   37,857 chars    2 duplicated data rows, 3 tables

    Every table appears TWICE -- once as column-collapsed page prose and again
    as pipe rows -- and the pipe rows are degenerate: `| Male 40.0 (n=12) 33.3
    (n=10) ... |  |  |  |  |` is the same flattened line with four empty cells
    after it. So the model reads each number twice and the second copy wears a
    table's clothes without carrying a column association.

    Reports; it does not judge. The caller decides what a score is worth.
    """
    text = text or ""
    counts: dict[tuple, int] = {}
    for line in text.split("\n"):
        nums = _DATA_ROW_NUMS.findall(line.strip())
        if len(nums) >= 3:
            k = tuple(nums)
            counts[k] = counts.get(k, 0) + 1
    dup_rows = sum(v - 1 for v in counts.values() if v > 1)
    return {
        "n_duplicated_data_rows": dup_rows,
        "n_degenerate_pipe_rows": len(_DEGENERATE_ROW.findall(text)),
        "n_table_placeholders": len(re.findall(r"\[Table \d+:", text)),
    }


def _ingested_markdown_is_degraded(scores: dict) -> bool:
    """Is this ingested markdown bad enough to lose its first-place rank?

    Deliberately conservative. A handful of repeated data rows is ordinary --
    a summary line restating a table row is normal scientific writing, and our
    own docling output scores 2 on the paper above. The bar is set so that
    ordinary repetition does NOT demote a file and the apple_cider shape does:
    many duplicated rows AND no placeholder discipline, or outright degenerate
    pipe rows.
    """
    if scores.get("n_table_placeholders"):
        return False        # it observes our placeholder contract; it is ours
    return (scores.get("n_duplicated_data_rows", 0) >= 10
            or scores.get("n_degenerate_pipe_rows", 0) >= 5)


def _derive_paper_text(paper_dir: str | Path) -> tuple[str, str | None]:
    """
    The paper's text plus which source supplied it
    (``"body_md" | "body_md_degraded" | "xml_publisher" | "xml_derived" |
    "html" | "pdf" | None``).

    `xml_derived` is XML we or a converter built FROM a PDF -- it carries the
    text layer's corruption inside better structure, and must not be read as
    the marked-up truth. See `xml_provenance`.

    ``None`` accompanies an empty text: no source could be read, which is
    UNKNOWN, never "the paper says nothing". Consumers that record provenance
    (the text-forensics track) need the source label; everything else keeps
    calling `paper_text`.

    Shared by every consumer that used to hardcode ``body.md``/``abstract.md``.
    Those files no longer exist for XML-fetched papers, so each of those call
    sites was silently reading ``""`` — which, in ``supplements.audit``, made
    the supplement gate pass unconditionally. HTML-only and PDF-only papers
    are the same bug in two more shapes, so the fallback chain covers both.

    THE PDF FALLBACK IS NOT AN EXTRA -- it is what makes the supplement gate
    able to see a PDF-only paper at all. MEASURED with only the main PDF in the
    directory: 0 characters returned for 7 of 7 PDF-only ground-truth papers,
    and `supplements.gate` PROCEEDED on all 7. Corpus-wide the same run passed
    97 of 97 papers with 0 detected as citing a supplement; with this fallback
    it is 70 of 97 detected and 26 passing. A gate that cannot read the paper
    is not a gate, and `OVERRIDE_WARNING` never printed, so nothing in any
    report said the SI had been absent.

    Order is deliberate: the pre-extracted markdown is cheapest and most
    faithful, then the publisher XML, then fetched HTML (both preserve table
    structure the way a raw text layer cannot -- HTML ranks above the PDF
    fallback for the same reason it ranks above PDF in the main sweep's own
    source-priority chain), then the PDF text layer last -- which costs a
    full pdfplumber pass (MEASURED at a median 6.6 s per paper over 12 corpus
    PDFs) and is the only form that can be absent-by-typography, since a
    scanned paper has no text layer at all. ``""`` still comes back when every
    source fails, and callers must treat that as UNKNOWN rather than as "this
    paper says nothing".

    Not switched to PyMuPDF, but it is the obvious next question and the
    numbers are here for whoever asks: over the same 12 PDFs `fitz` is 5.6x
    faster (14.4 s against 81.4 s in total) and finds STRICTLY MORE supplement
    citations -- on 3 of the 12 it sees a `Supplement 1` or `Supporting
    Information` reference that pdfplumber's text layer does not, and on none
    of them the reverse. That is a recall gap in the gate, not just a speed
    one, and it belongs to whoever owns the extractor choice.
    """
    paper_dir = Path(paper_dir)
    if not paper_dir.is_dir():
        return "", None

    # `markdown/body.md` IS DELIBERATELY NOT READ HERE, and the next person to
    # look will want to add it. Don't.
    #
    # `markdown_out` writes that file FROM this function, for the agents to
    # `read_file`. Reading it back would make the folder its own input and
    # reintroduce a staleness class we cannot close: it invalidates on the
    # source FILES changing, and not on this extractor changing. MEASURED
    # 2026-08-22 -- the extractor moved twice in two days (dc4306f captions and
    # abstracts, d5d8604 Elsevier abstracts, the second adding thousands of
    # characters per paper on the live corpus), and the XML was untouched
    # both times, so every cached body.md would have gone on serving pre-fix
    # text with nothing able to notice.
    #
    # There is no speed argument to weigh against that: a fresh resolve costs
    # 4.4 ms/paper, measured over 40 papers.

    def _read_md(path: Path) -> str | None:
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    #: Set when an ingested body.md was demoted, so the last resort can use
    #: it rather than returning "" -- which every consumer reads as UNKNOWN.
    _degraded_fallback: str | None = None

    parts: list[str] = []
    for name in ("body.md", "abstract.md", "references.md"):
        text = _read_md(paper_dir / name)
        if text:
            parts.append(text)
    if parts:
        ingested = repair_extraction_damage("\n\n".join(parts))
        # AN INGESTED body.md MUST EARN ITS RANK. It is first in this chain
        # because pre-extracted markdown is cheapest and most faithful -- true
        # of markdown we wrote, and an assumption nobody rechecked for a file
        # that was simply on disk. When it is degraded and another source
        # exists, fall through; the demotion is RECORDED by the caller through
        # the returned label, never silent.
        scores = ingested_markdown_degeneracy(ingested)
        if not _ingested_markdown_is_degraded(scores):
            return ingested, "body_md"
        warnings.warn(
            f"{paper_dir}: the body.md on disk repeats its tables "
            f"({scores['n_duplicated_data_rows']} duplicated data rows, "
            f"{scores['n_degenerate_pipe_rows']} degenerate pipe rows, no "
            f"placeholders); falling through to a source we extract ourselves. "
            f"If nothing else is readable this file is used anyway and the "
            f"label says so.", stacklevel=2)
        _degraded_fallback = ingested

    xml = find_xml(paper_dir)
    if xml is not None:
        try:
            text = extract_xml_text(xml)
        except (OSError, ET.ParseError):
            text = ""
        if text.strip():
            # THE LABEL CARRIES THE PROVENANCE. `xml_publisher` is the
            # marked-up truth; `xml_derived` is a PDF extraction wearing XML's
            # clothes and inherits none of that authority. Unknown origin is
            # reported as derived, because being unable to tell is not evidence
            # of publisher markup.
            prov = xml_provenance(xml)
            return text, ("xml_publisher" if prov == "publisher" else "xml_derived")

    # Deferred import: extraction.html imports jats's cell/span helpers, so a
    # module-level import here would be circular.
    from .html import extract_html_text_with_tables, find_html

    html = find_html(paper_dir)
    if html is not None:
        try:
            html_result = extract_html_text_with_tables(html)
        except (OSError, ValueError):
            html_result = {"error": "extraction failed"}
        text = html_result.get("text", "") if not html_result.get("error") else ""
        if text.strip():
            # TOO SHORT TO BE THE PAPER is treated as a wall, and routed through
            # the same fall-through rather than a parallel one. A Cloudflare
            # "Client Challenge" carries none of the access-wall markers -- it
            # is not selling anything -- so `looks_like_access_wall` passes it,
            # and 13 paper directories were serving its 228 characters as the
            # article. See `html.article_text_too_short` for the measurement.
            # The length floor is applied by `find_html`'s own gate, so a decoy
            # never reaches here. `short` stays as a belt-and-braces read for a
            # caller that supplied an HTML by another route.
            from .html import article_text_too_short as _too_short
            short = _too_short(text)
            walled, _markers = looks_like_access_wall(text)
            if not walled and not short:
                return text, "html"
            # A SHOP FRONT MUST NOT OUTRANK THE ARTICLE. Falling through is
            # gated on the PDF actually being richer, so a false positive here
            # costs nothing: if this HTML really is the full text, it is longer
            # than the text layer and it is what comes back.
            pdf_text, pdf_source = _pdf_text_with_source(paper_dir)
            if (len(pdf_text.strip())
                    > _ACCESS_WALL_PDF_MARGIN * len(text.strip())):
                return pdf_text, pdf_source
            if short:
                # NOTHING BETTER EXISTS, and the HTML is not the paper. "" is
                # UNKNOWN, which every consumer already reads correctly; the
                # alternative is handing 228 characters of browser interstitial
                # to a pipeline that reports missing data as a finding.
                warnings.warn(
                    f"{paper_dir}: the fetched HTML is not the article ({short}). "
                    "Serving NO text rather than the interstitial. Run "
                    "`metascience needs-fetch` for the URL to fetch by hand.",
                    stacklevel=2)
                return "", None
            return text, "html"

    # Harvest layout: `{stem}_from_pdf_body.md`, never `body.md`. After XML
    # and HTML (those preserve table structure) and before the PDF cache, so
    # a paper the fetcher already transcribed is not treated as unread just
    # because docling has not run.
    harvest_parts: list[str] = []
    for kind in ("body", "abstract", "references"):
        text = _read_md(paper_dir / f"{paper_dir.name}_from_pdf_{kind}.md")
        if text:
            harvest_parts.append(text)
    if harvest_parts:
        return "\n\n".join(harvest_parts), "body_md"

    text, source = _pdf_text_with_source(paper_dir)
    if text.strip():
        return text, source

    # THE DEMOTED FILE IS STILL BETTER THAN NOTHING, and returning "" here would
    # be the worse bug: an empty read means UNKNOWN to every consumer, and a
    # paper we can partly read would be recorded as a paper that says nothing.
    # The label carries the demotion so the record shows what was used.
    if _degraded_fallback is not None:
        warnings.warn(
            f"{paper_dir}: no source could be extracted, so the degraded "
            f"body.md is used after all. Its tables are repeated and its pipe "
            f"rows carry no column association; treat table-derived values "
            f"from this paper with corresponding caution.", stacklevel=2)
        return _degraded_fallback, "body_md_degraded"
    return text, source


def paper_text_with_source(paper_dir: str | Path) -> tuple[str, str | None]:
    """`_derive_paper_text`, plus a DECLARED repair overlay.

    THIS IS NOT THE REJECTED IDEA. `_derive_paper_text` carries a long comment
    forbidding `markdown/body.md` from being read back, and it is right: that
    file is written FROM this function, so reading it as a cache "invalidates
    on the source FILES changing, and not on this extractor changing" -- and
    the extractor moved twice in two days while the XML sat still.

    That argument is about a CACHE. It does not reach a repair a human made on
    purpose and declared, and the staleness hole it names is exactly what the
    declaration closes: `repairs.RepairLog` pins `original_sha256`, the hash of
    the text this repair was made against. So the order here is derive FIRST,
    then overlay -- which makes the check possible at all. If the extractor
    moves, the derived text changes, the hash stops matching, and the
    declaration is REFUSED rather than silently serving pre-fix text. The
    failure mode the comment warns about cannot occur through this path.

    WHY IT IS NEEDED. `markdown/body.md` is where a person would put a repaired
    body -- it is the file we tell them to inspect. MEASURED 2026-08-31 across
    the 12-paper working corpus: 12 of 12 carry `markdown/body.md`, 0 carry a
    top-level `body.md`, and the resolver reads only the top-level name, so an
    edit to the canonical file changed nothing on either an XML-sourced or a
    PDF-sourced paper. Without this overlay the repair-with-a-log policy has
    nowhere to write.

    STRICTLY OPT-IN. With no log -- every paper today -- this returns exactly
    what `_derive_paper_text` returned. An UNDECLARED divergence is deliberately
    NOT read: see `repairs.divergence`.
    """
    text, source = _derive_paper_text(paper_dir)
    try:
        from ..repairs import authorises_body_md, sha256
        log = authorises_body_md(paper_dir)
        if log is None:
            return text, source
        # The staleness guard. A declaration is valid only against the text it
        # was made against; anything else and we do not know what the repairs
        # were repairing.
        if not log.original_sha256 or log.original_sha256 != sha256(text):
            warnings.warn(
                f"{paper_dir}: a repair log declares markdown/body.md, but it "
                f"was made against different derived text (the extractor or the "
                f"source has changed since). Refusing the declaration and using "
                f"the derived text. Re-make the repairs against the current "
                f"text to restore it.", stacklevel=2)
            return text, source
        repaired = find_body_md(paper_dir)
        if repaired is None:
            return text, source
        body = repaired.read_text(encoding="utf-8", errors="replace")
        if not body.strip():
            return text, source
        return body, "body_md_repaired"
    except Exception:  # noqa: BLE001 -- an overlay must never cost the paper
        return text, source


def _pdf_text_with_source(paper_dir: Path) -> tuple[str, str | None]:
    """The PDF text-layer branch of the fallback chain, on its own so the
    access-wall check can reach it without duplicating the cache handling."""
    pdf = find_pdf(paper_dir)
    if pdf is None:
        return "", None
    try:
        from .pdf import extract_text
        from . import docling_tables as _dl
        text = extract_text(pdf)
    except Exception:
        # A corrupt or scanned PDF yields nothing readable. Returning "" is
        # correct and is NOT the same as "no supplement is referenced" --
        # `supplements.audit` fails closed on an empty text for exactly this
        # reason.
        return "", None
    if text.strip():
        return text, "pdf"
    # Cache miss is UNKNOWN-because-we-have-not-looked, not a scan.
    # `audit` branches on this source so a batch plan cannot print
    # "scanned or corrupt" for a PDF nobody has extracted yet.
    _usable, why = _dl.cache_status(pdf)
    if not _usable and "not extracted yet" in why:
        return "", "pdf_not_extracted"
    return "", None
