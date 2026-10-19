"""Model + image table reading, verified by the walker (section 8n).

THE RULING. Greg, 2026-09-06: give the table (text + rendered image) to a
capable model and have it produce its own structured table, rather than
hand-writing rules per markup shape. Validated on twenty JATS tables, ten
composite: 714 of 714 cells with the image, 335 of 335 on the composite ones;
the text alone fails exactly on banners and stacked headers, which is where
the rule-based walker fails too. The image alone determined placement.

WHAT THE WALKER BECOMES. Not the reader: the VERIFIER. A reconstruction is a
reading, and it replaces the walker's cells only when the walker can show it
conserved the table: every numeric token in the walker's cells and labels
appears in the reconstruction's values and labels, no more and no fewer
(Counter equality), every row is as wide as the header, and every value can be
traced to a walker cell. Where the two readings disagree the reconstruction is
REFUSED and recorded, never resolved in favour of either -- that was the
condition stated when this was scoped, and the disagreement rate is the
measurement that decides what happens next.

WHY CONSERVATION IS OVER VALUES AND LABELS TOGETHER. The walker's commonest
error is a banner (`Early Adolescent Group (N=2749)`) read as a data row; the
model reads it as a section label. The numerals are the same, they have moved
between a value slot and a label slot -- and that move is exactly the fix. A
value-only invariant would refuse the correct reading.

RULE 1 (section 8d) APPLIES UNCHANGED. A reconstruction may NARROW what a
check does -- a banner becoming a section takes a false denominator away --
and may not supply a premise: it is a transcription with a confidence, not the
canonical printed table, which is why the walker's own cells are kept on the
record as `walker_cells` beside it.

JATS FIRST (R5). The renderer takes the `<table-wrap>` the walker read, by its
own `id`; CALS (`<tgroup>`) markup is recorded as not attempted, and an
article that exists only as a PDF is still a later step.

A SUPPLEMENT IS NOT A SECOND-CLASS INPUT (Greg, 2026-09-06: "the supplements /
repos aren't 'second-class citizens' in the context of the analysis. They are
as important as the main text, and should be presented to the models in this
fashion"). A Word supplement is drawn from its own markup; a PDF supplement has
no markup to draw, so its PAGE is drawn -- located from the walker's own page
number, or from the page carrying the largest share of the table's cell strings
-- and read through the same call and the same verifier. MEASURED on
jamanetworkopen.2023.37679 before this: nine supplement tables and 592 cells,
every one recorded `supplement format .pdf not rendered yet (docx only)`.

NO NEW DEPENDENCY. The image is drawn by a headless Chromium found on this
machine (`METASCIENCE_CHROME`, a Playwright browser cache, or PATH); with no
browser the table is recorded as not rendered and the walker's cells stand.
"""
from __future__ import annotations

import copy
import glob
import hashlib
import html as _html
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

from ..composite import _COUNT_PCT, _COUNT_SLASH_PCT  # the one definition of `n (pct%)`
from ..extraction import jats as _jats
from . import passes as _passes
from . import reading_store as _store

PROMPT_VERSION = "recon/4-per-cell"
DEFAULT_MODEL = "sonnet"

#: What a single printed number IS. Closed, so two readings of one table cannot
#: drift on the word, and so `bind` can refuse a kind it does not handle.
TIDY_STATISTICS = ("n", "count", "percentage", "mean", "sd", "sem", "median", "iqr",
                   "range", "ci_lower", "ci_upper", "coefficient", "se", "test_statistic",
                   "df", "p", "ratio", "score", "other")

#: Where a statistic's KIND came from. An inference disclosed only in prose
#: notes is not machine-actionable; this field is, and `bind` carries it onto
#: the value so a check can decline `inferred`.
#:
#: `adjudicated` IS A THIRD TIER, and no model writing a table reading may use
#: it: it is stamped by `review.apply_adjudication` when a second reading of the
#: paper, under that function's gates, changed the kind. It sits between the
#: printed bases above and `inferred` -- a model read the paper and says so,
#: which is not the paper saying so. A check may run on it and must ceiling its
#: verdict at `suspicious`; an impossibility claim rests on the premise being the
#: paper's, and an adjudicated premise is ours.
STATISTIC_BASES = ("column_header", "row_label", "footnote", "caption", "citing_text", "cell_form",
                   "inferred", "adjudicated")

#: THE TIDY FORM (Greg, 2026-09-06): "the variable-value relationships that are
#: implicit in the original table can be made explicit in the model's
#: reconstructed version ... performing isomorphic transformations of the data
#: structures will improve more than undermine accuracy and auditability."
#: One entry per printed number, each carrying the cell, row label, column
#: label and section it was printed in -- so the grid is recoverable from the
#: entries (the transformation is invertible) and every entry is auditable
#: back to its cell. Nothing downstream re-matches a label by string.
_NUMBER = {"type": "object", "properties": {
    "statistic": {"type": "string", "enum": list(TIDY_STATISTICS)},
    "statistic_basis": {"type": "string", "enum": list(STATISTIC_BASES),
                        "description": "WHERE the kind was read from; `inferred` when nothing printed or "
                                       "cited states it -- a check may then decline it."},
    "value": {"type": "string", "description": "This ONE number exactly as printed."}},
    "required": ["statistic", "statistic_basis", "value"], "additionalProperties": False}

#: ONE RECORD PER PRINTED CELL, its numbers listed inside (2026-09-06). The
#: first tidy form put one record per NUMBER and repeated the cell's identity
#: and relationships on each; a 189-cell, 756-numeral table then timed out
#: twice at 15 minutes. The cell is the unit of provenance and of the
#: relationships (variable, level, group); only the kind and the value are
#: per number. Same information, about a third of the output.
RECON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "caption": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "column_labels": {"type": "array", "items": {"type": "string"},
                          "description": "Leaf column headers left to right, excluding the stub; "
                                         "stacked levels joined outer to inner with ' | '."},
        "cells": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "row_label": {"type": "string", "description": "The stub text of its row as printed."},
                "section": {"anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "The banner the row sits under, as printed, or null."},
                "column_index": {"type": "integer",
                                 "description": "1-based position among `column_labels`; identical headers "
                                                "are told apart ONLY by this."},
                "column_label": {"type": "string", "description": "Its leaf column header as printed."},
                "cell": {"type": "string", "description": "The whole printed cell, exactly as printed."},
                "variable": {"type": "string",
                             "description": "What is measured, in the paper's own words, with the banner "
                                            "resolved -- never a bare level name."},
                "level": {"anyOf": [{"type": "string"}, {"type": "null"}],
                          "description": "When the row is one value of a categorical variable, that value."},
                "group": {"anyOf": [{"type": "string"}, {"type": "null"}],
                          "description": "The column's arm, model, subgroup or time as printed; null for "
                                         "a whole-sample column."},
                "variable_id": {"anyOf": [{"type": "string"}, {"type": "null"}],
                                "description": "The DECLARED variable's id when one fits exactly; never coined."},
                "level_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "group_id": {"anyOf": [{"type": "string"}, {"type": "null"}],
                             "description": "The declared group's id this column reports on, when certain."},
                # OPTIONAL, added 2026-09-06: a ratio or difference is AGAINST something.
                # The mirrored tables of jamanetworkopen.37679 print two contrast
                # families over the same stubs (veteran vs nonveteran; limitations vs
                # none) and one group id per cell could not say which. Optional so
                # readings already bought stay valid; new readings fill it.
                "reference_group_id": {"anyOf": [{"type": "string"}, {"type": "null"}],
                                       "description": "For a ratio, difference or contrast: the declared group "
                                                      "it is measured AGAINST, when the table or its citing text "
                                                      "states it (a `1 [Reference]` row marks it). Null for a "
                                                      "descriptive cell."},
                "contrast": {"anyOf": [{"type": "string"}, {"type": "null"}],
                             "description": "The comparison in the paper's words, e.g. `veterans vs nonveterans "
                                            "with no limitations`; null for a descriptive cell."},
                "numbers": {"type": "array", "items": _NUMBER,
                            "description": "Every printed number in this cell, in order: `38 (59%)` is two, "
                                           "`3.1 (3.0-3.2)` three, `1 [Reference]` one, `--` none."},
            },
            "required": ["row_label", "section", "column_index", "column_label", "cell", "variable",
                         "level", "group", "variable_id", "level_id", "group_id", "numbers"],
            "additionalProperties": False}},
        "notes": {"anyOf": [{"type": "string"}, {"type": "null"}],
                  "description": "Anything you could not read, or a relationship the table leaves "
                                 "genuinely unstated."},
    },
    "required": ["caption", "column_labels", "cells", "notes"],
    "additionalProperties": False,
}


def _digits(s: Any) -> str:
    """One printed integer's digits, with the separators a paper may put in
    them removed. `84 299`, `84,299` and `84299` are the same number."""
    return re.sub(r"[\s,  ]", "", str(s or ""))


def is_count_of_a_share(cell: Any, printed: Any) -> bool:
    """Is `printed`, in the cell `cell`, the COUNT half of a count/percent pair?

    THE RULE: a percentage printed in a cell is a share OF a base, and the
    integer printed beside it is that share's NUMERATOR. A group's n is the
    BASE of such shares, never a numerator of one -- a group's size relative to
    itself is 100%, and no paper prints its own denominator that way. So an
    integer printed as `38 (59%)` or `587 / 99.5%` is a count of a category,
    whatever the row label spells it.

    WHY THIS IS NOT A LABEL LEXICON, and why a lexicon would not have worked.
    On ajcp.70049 Table 1 the eight such cells sit under four different label
    shapes: `Use at least one evidence-based program (n, %)`, `Pennsylvania
    (n, %)` under a `State` banner, `Externally funded (n, %)`, and -- for
    three of the eight -- the bare level names `None`, `1` and `2 or 3` under a
    `Level of technical assistance received` banner, whose row labels contain
    no `(n, %)` and no `n` at all. A rule spelled as a list of label spellings
    catches five of the eight and leaves the paper's denominator ambiguous.
    This function reads no label. It reads the PRINTED CELL.

    THE CELL SHAPE IS NOT REDEFINED HERE. `_COUNT_PCT` / `_COUNT_SLASH_PCT` are
    this repository's one definition of `n (pct%)`, already imported by
    `bind.cell_components`, where the GRID path types this very cell shape
    `("count", "38"), ("percentage", "59%")` from code. Only the TIDY path can
    produce `n` for it, because only the tidy path lets a model name the kind.
    Two readers of one table disagreed about one cell, and the one that was
    wrong was the one that asked.

    THE PERCENT SIGN IS REQUIRED, unlike in the grid path, and must sit inside
    the count/percent construction itself. `_COUNT_PCT` makes the sign optional
    (`35 (33)` matches it), and this function REMOVES a denominator from the
    pool a check may divide by: it may only ever do that on the paper's own
    positive evidence that the second number is a share, which is the sign.

    ORDER IS NOT PART OF THE RULE, deliberately. `_COUNT_PCT` anchors the count
    first, which is the usual printing; the reversed `88.89%(32)` form recorded
    in CLAUDE.md 8k parses as neither shape and so is simply not retyped, which
    is the refusing direction.
    """
    text = str(cell or "")
    if "%" in str(printed or ""):
        return False                      # this IS the percentage, not its count
    m = _COUNT_PCT.match(text) or _COUNT_SLASH_PCT.match(text)
    if m is None or "%" not in m.group(0):
        return False
    return _digits(m.group(1)) == _digits(printed)


def _retype(e: dict) -> dict:
    """One tidy entry, with an `n` that is the count half of a count/percent
    pair retyped `count`.

    THE MODEL'S OWN WORD IS KEPT (`statistic_as_read`) and the reading on disk
    is untouched: this is a deterministic correction applied on READ, re-derived
    on every load, so no paid reading is discarded to obtain it. That also rules
    out the alternative fix -- editing the reconstruction prompt, which already
    says in as many words that `38 (59%)` is a count -- because the prompt text
    enters every table reading's cache key through `PROMPT_VERSION`.

    AN `adjudicated` KIND IS LEFT ALONE. It is stamped only by
    `review.apply_adjudication`, where a second reading of the WHOLE paper,
    under that function's gates, changed the kind -- which may rest on a
    footnote or a Methods sentence the cell does not carry. Declining to
    overrule it costs a refusal, which is the safe direction; overruling it
    could cost a denominator the paper does state.
    """
    if e.get("statistic") != "n" or e.get("statistic_basis") == "adjudicated":
        return e
    if not is_count_of_a_share(e.get("cell"), e.get("value")):
        return e
    return {**e, "statistic": "count", "statistic_basis": "cell_form",
            "statistic_as_read": e.get("statistic")}


def entries_of(recon: dict) -> list[dict]:
    """The reading as flat entries (one per printed number), whichever form it
    was written in: the per-cell form (`cells[].numbers[]`) or the earlier
    per-number form (`entries[]`, still on disk for readings bought under
    recon/2 and recon/3). Everything downstream reads entries.

    `_retype` runs HERE, on the one funnel every consumer passes through --
    `adapt`, `bind`, the interpretation layer, the coverage counters -- so the
    account cannot hold one typing of a cell and the rebuilt grid another.
    """
    if recon.get("entries") is not None and recon.get("cells") is None:
        return [_retype(e) for e in recon["entries"]]
    out: list[dict] = []
    for c in recon.get("cells") or []:
        base = {k: c.get(k) for k in ("row_label", "section", "column_index", "column_label", "cell",
                                     "variable", "level", "group", "variable_id", "level_id", "group_id",
                                     "reference_group_id", "contrast")}
        for n in c.get("numbers") or []:
            out.append(_retype({**base, "statistic": n.get("statistic"),
                                "statistic_basis": n.get("statistic_basis"),
                                "value": n.get("value")}))
    return out


_CSS = """
body{margin:24px;background:#fff;color:#000;font:15px/1.35 Arial,Helvetica,sans-serif}
.label{font-weight:bold;margin-bottom:4px}.caption{margin-bottom:10px}
table{border-collapse:collapse}th,td{border:1px solid #444;padding:4px 8px;vertical-align:top;text-align:left}
th{background:#eee}.fn{margin-top:10px;font-size:13px;color:#222}
"""



# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def chrome_binary() -> str | None:
    """A headless-capable Chromium: env, Playwright's cache, then PATH."""
    env = os.environ.get("METASCIENCE_CHROME")
    if env and Path(env).exists():
        return env
    hits = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")))
    if hits:
        return hits[-1]
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def table_element(root: ET.Element, wrap_id: str | None, table_num: int | None) -> ET.Element | None:
    """The `<table-wrap>` the walker read: by its own id first, by order second."""
    containers = _jats._table_containers(root)
    if wrap_id:
        for c in containers:
            if c.get("id") == wrap_id:
                return c
    if table_num and 1 <= table_num <= len(containers):
        return containers[table_num - 1]
    return None


_INLINE = {"bold": "b", "italic": "i", "sup": "sup", "sub": "sub", "xref": "sup", "break": "br",
           "underline": "u", "monospace": "code", "sc": "span", "named-content": "span",
           "styled-content": "span", "inline-formula": "span", "ext-link": "span", "uri": "span",
           "p": "div"}
_TABLE_TAGS = {"table", "thead", "tbody", "tfoot", "tr", "td", "th", "colgroup", "col", "caption"}
_KEEP_ATTRS = {"colspan", "rowspan", "align", "valign", "span"}


def _localise(el: ET.Element) -> None:
    for node in el.iter():
        tag = _jats._local(node.tag)
        node.tag = tag if tag in _TABLE_TAGS else _INLINE.get(tag, "span")
        for k in list(node.attrib):
            if k not in _KEEP_ATTRS:
                del node.attrib[k]


def table_html(container: ET.Element, keep_rows: set[int] | None = None,
               note: str | None = None) -> str | None:
    """The table as standalone HTML, or None for CALS/graphic-only wraps.

    `keep_rows` is a set of 1-based `<tr>` indices; every other body row is
    dropped and the header rows are kept whatever it says, so one block of a
    long table is drawn as a table in its own right. `note` is printed beside
    the label, naming which rows of how many this is.
    """
    tables = [t for t in _jats._tables_in(container) if _jats._local(t.tag) == "table"]
    if not tables:
        return None
    label = _jats._first(container, ("label",), _jats._Counter())
    caption = ""
    for node in container:
        if _jats._local(node.tag) in ("caption", "simple-para"):
            caption = " ".join("".join(node.itertext()).split())
            break
    fns = [" ".join("".join(n.itertext()).split()) for n in container.iter()
           if _jats._local(n.tag) in ("fn", "table-wrap-foot")]
    parts = [f"<html><head><meta charset='utf-8'><style>{_CSS}</style></head><body>"]
    if label:
        parts.append(f"<div class='label'>{_html.escape(label)}"
                     + (f" &mdash; {_html.escape(note)}" if note else "") + "</div>")
    if caption:
        parts.append(f"<div class='caption'>{_html.escape(caption)}</div>")
    for t in tables:
        t2 = copy.deepcopy(t)
        if keep_rows is not None:
            _keep_rows(t2, keep_rows)
        _localise(t2)
        parts.append(ET.tostring(t2, encoding="unicode", method="html"))
    if fns:
        parts.append("<div class='fn'>" + "<br>".join(_html.escape(f) for f in dict.fromkeys(fns)) + "</div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _keep_rows(table: ET.Element, keep: set[int]) -> None:
    """Drop every `<tr>` whose 1-based document order is not in `keep`.

    The header rows are never dropped: a block without its header is a grid of
    numbers with no columns, and the whole reason the image is served is that it
    is the authority on which value sits under which header.
    """
    rows = [(i, tr) for i, tr in enumerate(
        (n for n in table.iter() if _jats._local(n.tag) == "tr"), start=1)]
    parents = {id(child): parent for parent in table.iter() for child in parent}
    for i, tr in rows:
        in_head = any(_jats._local(p.tag) == "thead" for p in table.iter()
                      for c in p if c is tr)
        if i in keep or in_head:
            continue
        parent = parents.get(id(tr))
        if parent is not None:
            parent.remove(tr)


def docx_table_html(path: Path, table_num: int, label: str | None = None) -> str | None:
    """The `table_num`-th table of a Word supplement as standalone HTML, with
    the merges python-docx exposes drawn as colspan/rowspan.

    MIRRORS `supplements_read.extract_docx_tables`: that reader identifies a
    merged cell by the identity of its `<w:tc>` element repeated across grid
    positions, and blanks the continuations. The same identity test here
    turns the repeats into spans, so the image the model reads shows exactly
    the structure the walker's cells came from -- one rule, drawn twice.
    """
    try:
        from docx import Document
    except ImportError:
        return None
    doc = Document(str(path))
    tables = list(doc.tables)
    if not (1 <= int(table_num) <= len(tables)):
        return None
    table = tables[int(table_num) - 1]
    rows = [list(r.cells) for r in table.rows]
    # Anchor each grid position at the first (row, col) where its <w:tc> appears.
    first: dict[int, tuple[int, int]] = {}
    ident: list[list[Any]] = []
    for r, cells in enumerate(rows):
        ident.append([])
        for c, cell in enumerate(cells):
            tc = cell._tc
            key = next((k for k in first if first[k][2] is tc), None)
            if key is None:
                first[len(first)] = (r, c, tc)
                key = len(first) - 1
            ident[r].append(key)
    span: dict[int, list[int]] = {}
    for r, keys in enumerate(ident):
        for c, k in enumerate(keys):
            sp = span.setdefault(k, [0, 0])
            sp[0] = max(sp[0], c - first[k][1] + 1)
            sp[1] = max(sp[1], r - first[k][0] + 1)
    parts = [f"<html><head><meta charset='utf-8'><style>{_CSS}</style></head><body>"]
    if label:
        parts.append(f"<div class='label'>{_html.escape(label)}</div>")
    parts.append("<table>")
    for r, cells in enumerate(rows):
        parts.append("<tr>")
        for c, cell in enumerate(cells):
            k = ident[r][c]
            if first[k][:2] != (r, c):
                continue
            cs, rs = span[k]
            attrs = (f' colspan="{cs}"' if cs > 1 else "") + (f' rowspan="{rs}"' if rs > 1 else "")
            text = _html.escape(" ".join(cell.text.split())).replace("\n", "<br>")
            parts.append(f"<td{attrs}>{text}</td>")
        parts.append("</tr>")
    parts.append("</table></body></html>")
    return "\n".join(parts)


#: The table's number INSIDE its own file, read off the end of the walker's
#: label. The trailing `(p. 4)` is optional because that is how
#: `supplements_read.extract_pdf_tables` labels a PDF supplement's table
#: (`Table 3 (p. 4)`) -- without it the anchor failed on every PDF supplement,
#: so `context_for` served none of them the passages that cite them.
_SUPP_LABEL_NUM = re.compile(r"Table\s*(\d+)(?:\s*\(p\.\s*\d+\))?\s*$", re.I)


def supplement_path(paper_dir: Path, table: dict) -> tuple[Path | None, str | None]:
    """The file a walked supplement table came from, or why it cannot be found."""
    name = table.get("supplement_file")
    if not name:
        return None, "supplement table with no file recorded"
    path = Path(paper_dir) / str(name)
    if not path.exists():
        hits = list(Path(paper_dir).rglob(str(name)))
        if not hits:
            return None, f"supplement file {name} not found under the paper directory"
        path = hits[0]
    return path, None


def supplement_table_html(paper_dir: Path, table: dict) -> tuple[str | None, str | None]:
    """(html, reason): the HTML render of a walked supplement table, or why not.

    HTML is the right drawing for a format whose table structure survives as
    markup -- today .docx, via `docx_table_html`. A PDF supplement carries no
    such markup: what it has is a PAGE, and `supplement_table_render` -- the
    one entry every format goes through -- draws that instead.
    """
    path, why = supplement_path(paper_dir, table)
    if path is None:
        return None, why
    # THE NUMBER INSIDE THE FILE comes from the walker's label
    # (`<file> :: Table 2`); the document's `table_num` is its position among
    # ALL the paper's tables and named a table the file does not have
    # (measured: "table 5 not found" for the file's Table 1).
    m = _SUPP_LABEL_NUM.search(str(table.get("walker_label") or table.get("label") or ""))
    num = int(m.group(1)) if m else table.get("table_num")
    if not num:
        return None, "supplement table with no table number in its label"
    if path.suffix.lower() == ".docx":
        html = docx_table_html(path, int(num), label=f"{path.name} :: Table {num}")
        return (html, None) if html else (None, f"table {num} not found in {path.name}")
    return None, f"supplement format {path.suffix.lower()} is not rendered as HTML"


# ---------------------------------------------------------------------------
# a PDF supplement's table: find its page, draw the page
# ---------------------------------------------------------------------------

def _squash(s: Any) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def cell_strings(table: dict) -> list[str]:
    """The walker's distinct non-empty cell strings, whitespace removed.

    WHITESPACE IS REMOVED ON BOTH SIDES of the comparison below because the two
    readings are of different renderings of one page: docling wrote the cell
    `23.0 ( ± 0.40)` and PyMuPDF's text layer puts the line break somewhere
    else. Comparing them literally finds nothing, which is the same defect
    `numerals.table_span` fixed for the body text.
    """
    out: list[str] = []
    for c in table.get("cells") or []:
        t = _squash(c.get("raw"))
        if t and t not in out:
            out.append(t)
    return out


#: What `_flatten_header` and `fold_section_bands` join a stacked label with.
#: OURS, not the paper's: the page prints the levels one above the other.
_LABEL_JOIN = " | "

#: The names `_cells_from_grid` gives a column or a row the source never
#: labelled -- `col3` on the JATS path, `(unlabelled column 3)` on the
#: supplement path. OURS TOO, and they carry a digit: counted as printed they
#: would put a `3` in the region that the paper does not contain, and looked for
#: on a page they match nothing.
_PLACEHOLDER_LABEL = re.compile(r"^\(unlabelled\s+(?:column|row)\s*\d*\)$|^col\d+$", re.I)


def region_strings(table: dict) -> list[str]:
    """Every string the walked table REGION prints, as printed: the header grid
    rows, the cell text, the row stubs and the column labels.

    RETURNED AS PRINTED, DEDUPLICATED ON THE WHITESPACE-FREE FORM. Squashing
    before returning looks harmless and is not: `_norm` strips a footnote marker
    only where the letters are glued to the digit, so `3 studies` normalises to
    `3studies` and `_squash`-then-`_norm` gives `3`. The caller squashes when it
    wants a page needle; the token pools normalise the printed string, which is
    what the reading's own strings are normalised from.

    ROLE-FREE ON PURPOSE (the walker-as-witness spec, 2026-09-08). `cell_strings`
    above is what the walker classified as DATA, and that classification IS
    `n_header_rows` -- a guess. The strings this function returns are the same
    whatever the guess was, because a header row that the walker called data is
    in `cells` and one it called header is in `header_rows`, and both are here.

    MEASURED, and it is why this exists. One printed grid walked at depth 0, 1
    and 2 on a supplement page carrying a second table gives three different
    crops, and at depth 2 the table IS NOT DRAWN AT ALL: `_flatten_header`
    joins the two header levels, `N | 620` is a string the page never printed,
    the located share falls to 73% and `_add_band` refuses the page. The
    walker's guess then decides which pixels the model is shown -- the one
    thing this design exists to trust instead of the walker.

    So a label is searched as its PRINTED PARTS. The join is ours; only the
    parts are on the page, and a needle that cannot match can only lower the
    coverage it is measured against.
    """
    out: list[str] = []
    seen: set[str] = set()

    def add(x: Any, split: bool = False) -> None:
        for part in (str(x or "").split(_LABEL_JOIN) if split else [str(x or "")]):
            if _PLACEHOLDER_LABEL.match(part.strip()):
                continue
            t = _squash(part)
            if t and t not in seen:
                seen.add(t)
                out.append(part.strip())

    for row in table.get("header_rows") or []:
        for x in row:
            add(x)
    for c in table.get("cells") or []:
        add(c.get("raw"))
        add(c.get("row_label"), split=True)
        add(c.get("col_label"), split=True)
    for x in list(table.get("row_labels") or []) + list(table.get("col_labels") or []):
        add(x, split=True)
    return out


def _table_needles(table: dict) -> set[str]:
    """The squashed strings this table PRINTS, long enough to look for.

    The whole walked region -- header rows, cell text, row stubs and column
    headers together -- because a table is recognised on a page by its labels as
    much as by its numbers, and because which of those the walker called a
    header must not decide what the model is shown (`region_strings`). The
    walker's own `(unlabelled column N)` placeholder is not printed anywhere,
    so it is dropped rather than searched for.
    """
    return {n for s in region_strings(table) if (n := _squash(s))
            and len(n) >= 3 and "unlabelledcolumn" not in n}


def page_lines(page: Any) -> list[tuple[Any, str]]:
    """`[(rect, squashed_text)]` for one PyMuPDF page, in reading order down."""
    out = []
    for blk in page.get_text("dict").get("blocks") or []:
        for ln in blk.get("lines") or []:
            txt = _squash("".join(s.get("text") or "" for s in ln.get("spans") or []))
            if txt:
                import fitz
                out.append((fitz.Rect(ln["bbox"]), txt))
    return sorted(out, key=lambda x: x[0].y0)


#: A vertical gap larger than this ends the table. A printed table's rows are
#: consecutive lines; a stray match in the prose two paragraphs below is a
#: different cluster, and taking min/max over both is what made one table's
#: band swallow the next one's header on s001 page 21.
_BAND_GAP_PT = 30.0
#: Padding above and below the located rows, so a rule, a footnote marker or a
#: half-line of descender is not shaved off.
_BAND_PAD_PT = 10.0
#: How far above the first located row a caption line may sit and still belong
#: to this table.
_CAPTION_REACH_PT = 45.0
_CAPTION_LINE = re.compile(r"^e?table\s*\d", re.I)
#: A band is only cropped to when this many of the table's own lines were
#: located and this share of its distinctive strings sit inside the band.
_MIN_BAND_LINES = 3
_MIN_BAND_COVERAGE = 0.5
#: How much of a LINE this table's own strings must account for before the line
#: is one of its rows. A share rather than a length, because the two layouts a
#: text layer produces for one printed row -- each cell as its own line, or the
#: whole row as one -- make any absolute rule right for one and wrong for the
#: other. A sentence of prose that happens to contain `0.45` explains four of
#: its ninety characters and is not a row.
_MIN_LINE_EXPLAINED = 0.5


def _explained(text: str, needles: set[str]) -> int:
    """How many of `text`'s characters this table's own strings account for.

    Overlaps are counted once: `620` inside `0.620` is the same characters, and
    summing needle lengths would report more characters than the line has.
    """
    covered = bytearray(len(text))
    for n in needles:
        start = text.find(n)
        while start != -1:
            covered[start:start + len(n)] = b"\x01" * len(n)
            start = text.find(n, start + 1)
    return sum(covered)


def table_band(page: Any, table: dict, siblings: list[dict] | None = None) -> dict:
    """Where on this page THIS table is printed: `{y0, y1, n_lines, coverage}`.

    A page is not a table. Drawing the whole page hands the model a second
    table it was not asked about -- the cross-attribution route -- and on
    jamanetworkopen.2023.51752's first supplement three pages carry two walked
    tables each, drawn as three pairs of identical images.

    TWO RULES DO THE WORK, and both are about telling one table from another:

      * a string this table shares with another table on the same page is not
        evidence for either, so the search uses only the strings that are
        DISTINCTIVE among the tables on the page. `0.45` is printed in both of
        page 21's tables; `African-Americans` is in one.
      * a table is CONTIGUOUS. The located lines are clustered on vertical
        gaps and the heaviest cluster is the table, so a stray match in the
        prose below does not stretch the band over it. Without this, page 21's
        upper table ran from y=49 to y=200 and took the lower table's header
        row with it.

    The caption immediately above is included when there is one: the reader is
    told to use it, and it is the paper's own statement of what the table is.
    """
    lines = page_lines(page)
    mine = _table_needles(table)
    for s in siblings or []:
        mine -= _table_needles(s)
    out: dict[str, Any] = {"y0": None, "y1": None, "n_lines": 0, "coverage": 0.0,
                           "n_distinctive": len(mine)}
    if not mine or not lines:
        return out
    hits = []
    for r, txt in lines:
        covered = _explained(txt, mine)
        if covered / len(txt) >= _MIN_LINE_EXPLAINED:
            hits.append((r, covered))
    if not hits:
        return out
    clusters: list[list] = [[]]
    for r, w in hits:
        if clusters[-1] and r.y0 - clusters[-1][-1][0].y1 > _BAND_GAP_PT:
            clusters.append([])
        clusters[-1].append((r, w))
    best = max(clusters, key=lambda c: sum(w for _, w in c))
    y0 = min(r.y0 for r, _ in best) - _BAND_PAD_PT
    y1 = max(r.y1 for r, _ in best) + _BAND_PAD_PT
    for r, txt in lines:
        if r.y1 <= y0 + _BAND_PAD_PT and y0 - r.y1 < _CAPTION_REACH_PT and _CAPTION_LINE.match(txt):
            y0 = min(y0, r.y0 - _BAND_PAD_PT)
    inside = [txt for r, txt in lines if r.y0 >= y0 and r.y1 <= y1]
    out.update({"y0": round(y0, 1), "y1": round(y1, 1), "n_lines": len(best),
                "coverage": round(sum(1 for n in mine if any(n in t for t in inside)) / len(mine), 3)})
    return out


def pdf_page_texts(path: Path) -> tuple[list[str] | None, str | None]:
    """Every page's text layer, in order; `(None, reason)` when it cannot be read."""
    try:
        import fitz
    except ImportError:                                   # pragma: no cover
        return None, "PyMuPDF is not installed; a PDF supplement page cannot be located or drawn"
    try:
        with fitz.open(str(path)) as doc:
            return [p.get_text() for p in doc], None
    except Exception as exc:                              # noqa: BLE001 - reported, not swallowed
        return None, f"{path.name} could not be opened: {type(exc).__name__}: {exc}"


#: A page must carry at least this share of the table's own cell strings before
#: it is accepted as the page that holds the table. Below it we do not know
#: WHICH page we would be drawing, and a reading of the wrong page is a reading
#: of a table the model was not asked about -- refused by the verifier, after
#: it has been paid for.
_MIN_PAGE_COVERAGE = 0.5

#: How much of what the chosen page LACKS must sit on the page after it before
#: that page is drawn too. A table that runs over a page break leaves most of
#: its remaining cells on the next page; one or two strays are ordinary (a
#: repeated header word, a number that also appears in a footnote), so a
#: handful of spill strings is not evidence of a continuation.
_MIN_SPILL_COVERAGE = 0.5
_MIN_SPILL_STRINGS = 3


def locate_pdf_table(path: Path, table: dict,
                     page_texts: list[str] | None = None,
                     siblings: list[dict] | None = None) -> dict:
    """Which page(s) of a PDF supplement hold this walked table.

    TWO WITNESSES, IN ORDER. The walker's own record carries a page number for
    a PDF supplement table -- docling reads it off the document, and
    `supplements_read.extract_pdf_tables` stamps it -- so that is the answer
    where it exists, and the cell-string coverage is measured beside it as a
    check a reader can see rather than as a veto. Where there is no page
    number, the page carrying the largest share of the table's own cell strings
    is the page; under `_MIN_PAGE_COVERAGE` we say we could not find it rather
    than drawing the likeliest guess.

    THE ASYMMETRY IS THE USUAL ONE. Refusing costs a table that goes unread and
    says so; drawing the wrong page buys a reading of a table nobody asked
    about, and the conservation check would refuse it only after the call is
    paid for.

    MEASURED on jamanetworkopen.2023.37679's nine PDF supplement tables, which
    is why the order is this way round. The walker's page and the best
    text-match page AGREE on all eight tables that have cells -- so the two
    witnesses do not disagree -- but the coverage on that correct page runs
    from 0.00 to 1.00, and the search alone would refuse five of the eight. The
    reason is docling: it FUSES several printed cells into one string
    (`1.00 1.37 (0.91-2.06)`, an entire row of eTable 8), and such a string
    appears nowhere in any page's text layer, on the right page or any other.
    Page 6 was drawn for the table whose coverage is 0.075 and it is the right
    page, checked by eye.
    """
    out: dict[str, Any] = {"pages": None, "basis": None, "coverage": None,
                           "n_cell_strings": 0, "reason": None}
    strings = cell_strings(table)
    out["n_cell_strings"] = len(strings)
    texts, why = (page_texts, None) if page_texts is not None else pdf_page_texts(path)
    if texts is None:
        out["reason"] = why
        return out
    if not texts:
        out["reason"] = f"{path.name} has no pages"
        return out
    if not strings:
        # NOTHING TO CONSERVE. `verify` compares the reading's digits against
        # the walker's; with no walker cells any reading carrying a digit is
        # refused and any empty one is accepted without evidence. Reading such
        # a table cannot tell us anything, so it is not bought.
        out["reason"] = ("the walker read no cells from this table, so a reading of it "
                         "could not be verified against anything")
        return out
    squashed = [_squash(t) for t in texts]
    found = [[s for s in strings if s in hay] for hay in squashed]
    walker_page = table.get("supplement_page") or table.get("page")
    chosen: int | None = None
    if isinstance(walker_page, int) and 1 <= walker_page <= len(texts):
        chosen, out["basis"] = walker_page, "walker_page"
    else:
        best = max(range(len(texts)), key=lambda i: len(found[i]))
        share = len(found[best]) / len(strings)
        if share < _MIN_PAGE_COVERAGE:
            out["coverage"] = round(share, 3)
            out["reason"] = (
                f"the table's cells could not be located in {path.name}: the best page "
                f"({best + 1} of {len(texts)}) carries {len(found[best])} of {len(strings)} "
                f"cell strings ({share:.0%}), under the {_MIN_PAGE_COVERAGE:.0%} needed to "
                "say which page holds it")
            return out
        chosen, out["basis"] = best + 1, "text_match"
    out["coverage"] = round(len(found[chosen - 1]) / len(strings), 3)
    pages = [chosen]
    spill = [s for s in strings if s not in found[chosen - 1]]
    if chosen < len(texts) and len(spill) >= _MIN_SPILL_STRINGS:
        on_next = [s for s in spill if s in squashed[chosen]]
        if len(on_next) / len(spill) >= _MIN_SPILL_COVERAGE:
            pages.append(chosen + 1)
            out["spill_coverage"] = round(len(on_next) / len(spill), 3)
    out["pages"] = pages
    _add_band(path, out, table, siblings, single_page=len(pages) == 1)
    return out


def _add_band(path: Path, out: dict, table: dict, siblings: list[dict] | None,
              single_page: bool) -> None:
    """Attach the crop to a located page, and REFUSE where a page carrying
    another walked table cannot be cut.

    THE ASYMMETRY IS THE SAME ONE `locate_pdf_table` states. Not cropping a
    page that holds one table costs pixels; not cropping a page that holds two
    hands the model a table nobody asked about, and the reading that comes back
    is then about the wrong table -- refused by `verify` after it has been paid
    for, or, worse, conserved because the digits happen to balance.

    So: on a page with siblings a crop is REQUIRED and its absence is a
    refusal; on a page without them a crop is an economy, taken only when the
    band is strongly located and skipped silently when it is not.
    """
    page_no = (out.get("pages") or [None])[0]
    on_page = [s for s in (siblings or [])
               if (s.get("supplement_page") or s.get("page")) == page_no]
    if not single_page:
        if on_page:
            out["pages"] = None
            out["reason"] = (
                f"the table runs over a page break and page {page_no} of "
                f"{path.name} carries {len(on_page) + 1} walked tables; a two-page render cannot "
                "be cropped to one of them, so it is not drawn")
        else:
            out["band"] = {"basis": "not_cropped",
                           "reason": "the table spans two pages; both are drawn whole"}
        return
    try:
        import fitz
    except ImportError:                                   # pragma: no cover
        return
    page_no = out["pages"][0]
    try:
        with fitz.open(str(path)) as doc:
            page = doc[page_no - 1]
            band = table_band(page, table, on_page)
            others = [table_band(page, s, [table] + [o for o in on_page if o is not s])
                      for s in on_page]
            rect = page.rect
    except Exception as exc:                              # noqa: BLE001 - reported, not swallowed
        out["band"] = {"basis": "not_cropped",
                       "reason": f"{type(exc).__name__}: {exc}"}
        return
    strong = (band["y0"] is not None and band["n_lines"] >= _MIN_BAND_LINES
              and band["coverage"] >= _MIN_BAND_COVERAGE)
    clashes = [o for o in others
               if o["y0"] is not None and band["y0"] is not None
               and o["y0"] < band["y1"] and band["y0"] < o["y1"]]
    if strong and not clashes:
        # FULL WIDTH, ALWAYS. The band is a range of ROWS; narrowing the
        # horizontal extent to the columns whose text happened to match would
        # cut off a column whose cells the walker fused.
        out["clip"] = [rect.x0, max(rect.y0, band["y0"]), rect.x1, min(rect.y1, band["y1"])]
        out["band"] = {"basis": "text_band", **band}
        return
    why = ("its printed extent could not be separated from the other table(s) on the page"
           if clashes else
           f"only {band['n_lines']} line(s) of it and {band['coverage']:.0%} of its distinctive "
           "strings could be located on the page")
    if on_page:
        out["pages"] = None
        out["band"] = {"basis": "refused", **band}
        out["reason"] = (
            f"page {page_no} of {path.name} carries {len(on_page) + 1} walked tables and "
            f"{why}; the whole page is not drawn, because it would hand the reader a table "
            "it was not asked about")
        return
    out["band"] = {"basis": "not_cropped", **band,
                   "reason": f"the page is drawn whole: {why}"}


#: 150 dpi, not the 300 the OCR path uses. Nothing here is transcribed by
#: machine: the model reads the page and the walker's own cell strings are
#: served beside it as the characters to copy, so the image has to be legible
#: rather than recognisable to an engine -- and a 300 dpi page image is four
#: times the pixels charged against the model's image budget.
_PAGE_DPI = 150


def render_pdf_pages(path: Path, pages: list[int], out_png: Path,
                     dpi: int = _PAGE_DPI, clip: list[float] | None = None) -> str | None:
    """Draw `pages` of a PDF to one PNG. Returns a reason on failure.

    Two pages are stacked into one image because the reader is served ONE
    image: a table that runs over a page break is one table, and giving the
    model half of it would invite it to reconstruct half.

    `clip` is the located table's own band on a single page (`table_band`), so
    a page carrying two tables is drawn twice, each render holding one table.
    """
    try:
        import fitz
    except ImportError:                                   # pragma: no cover
        return "PyMuPDF is not installed; cannot draw a PDF supplement page"
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    box = fitz.Rect(*clip) if (clip and len(pages) == 1) else None
    try:
        with fitz.open(str(path)) as doc:
            pix = [doc[p - 1].get_pixmap(dpi=dpi, clip=box) for p in pages
                   if 1 <= p <= doc.page_count]
            if not pix:
                return f"none of pages {pages} exists in {path.name}"
            if len(pix) == 1:
                pix[0].save(str(out_png))
            else:
                try:
                    from PIL import Image
                except ImportError:                       # pragma: no cover
                    pix[0].save(str(out_png))
                    return None
                ims = [Image.frombytes("RGB", (p.width, p.height), p.samples) for p in pix]
                w, h = max(i.width for i in ims), sum(i.height for i in ims)
                sheet = Image.new("RGB", (w, h), (255, 255, 255))
                y = 0
                for im in ims:
                    sheet.paste(im, (0, y))
                    y += im.height
                sheet.save(str(out_png))
    except Exception as exc:                              # noqa: BLE001 - reported, not swallowed
        return f"render failed: {type(exc).__name__}: {exc}"
    if not out_png.exists() or out_png.stat().st_size == 0:
        return f"render produced no image for pages {pages} of {path.name}"
    _crop_to_content(out_png)
    return None


def supplement_table_render(paper_dir: Path, table: dict, out_png: Path,
                            siblings: list[dict] | None = None
                            ) -> tuple[str | None, Path | None, dict, str | None]:
    """One entry for every supplement format: `(html, png, meta, reason)`.

    Exactly one of `html` (draw it with `render_png`) and `png` (already drawn)
    is returned, so the model call and the verifier below have ONE code path
    whatever the supplement was. `meta` records what was drawn and how it was
    found, and rides on the reconstruction record.
    """
    path, why = supplement_path(paper_dir, table)
    if path is None:
        return None, None, {}, why
    suffix = path.suffix.lower()
    if suffix != ".pdf":
        html, why = supplement_table_html(paper_dir, table)
        return html, None, ({"render": "html"} if html else {}), why
    same_file = [s for s in (siblings or []) if s.get("supplement_file") == table.get("supplement_file")]
    loc = locate_pdf_table(path, table, siblings=same_file)
    meta = {"render": "pdf_page", "supplement_file": path.name,
            "pages": loc.get("pages"), "page_basis": loc.get("basis"),
            "cell_coverage": loc.get("coverage"),
            "n_cell_strings": loc.get("n_cell_strings"),
            "clip": loc.get("clip"), "band": loc.get("band")}
    if not loc.get("pages"):
        return None, None, meta, loc.get("reason")
    err = render_pdf_pages(path, loc["pages"], out_png, clip=loc.get("clip"))
    if err:
        return None, None, meta, err
    return None, Path(out_png), meta, None


#: Room per printed row, and the fixed cost of the label, caption and footnote
#: block around it. Chromium's `--screenshot` captures the WINDOW, not the
#: document, so the window has to be tall enough before the shot is taken.
#: MEASURED on the meta-analysis (10.1017/s0033291723003501) Table 2, 237 rows:
#: 6,824 px of content, about 28 px a row. 34 leaves room for a row that wraps.
_ROW_PX = 34
_CHROME_PX = 240
#: The tallest window this asks Chromium for. Past it the render is REFUSED
#: rather than silently cut.
_MAX_RENDER_PX = 20000
_DEFAULT_RENDER_PX = 5000


def _estimated_height(html_text: str) -> int:
    """A window tall enough for this table, from its own row count."""
    return max(_DEFAULT_RENDER_PX,
               _CHROME_PX + _ROW_PX * max(1, html_text.count("<tr")))


def png_is_clipped(png: Path) -> bool | None:
    """Does the drawing run off the bottom of the image? None when unknown.

    Ink on the last rows of pixels means the content did not end inside the
    window. It is checked BEFORE `_crop_to_content`, because the crop trims to
    the ink and so leaves a clipped render ending neatly at a row boundary --
    which is exactly what made this look, from outside, like a table that
    simply ended there.
    """
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return None
    with Image.open(png) as im:
        rgb = im.convert("RGB")
        w, h = rgb.size
        # AGAINST WHITE, not against black. `Image.getbbox()` bounds the
        # non-ZERO pixels, so a blank white strip is "non-empty" and every
        # render reads as clipped -- which it did, on the first attempt at this.
        strip = rgb.crop((0, max(0, h - 2), w, h))
        bg = Image.new("RGB", strip.size, (255, 255, 255))
        return ImageChops.difference(strip, bg).getbbox() is not None


def render_png(html_text: str, out_png: Path, chrome: str | None = None,
               width: int = 1400, height: int | None = None,
               meta: dict | None = None) -> str | None:
    """Draw the HTML to `out_png` with headless Chromium. Returns a reason on failure.

    THE WINDOW WAS 5,000 PX AND THE OVERFLOW WAS SILENT. Chromium screenshots
    the window, so a taller table was drawn as its first 5,000 px with no error
    anywhere, and the crop then trimmed to the ink and produced an image ending
    neatly at a row boundary. MEASURED on the meta-analysis Table 2: 237 rows,
    6,824 px, drawn at 1400x4996 with the last ~60 rows absent. A reading of
    that image would have been refused by the verifier for digits it was never
    shown -- after the call was paid for.

    So the window is sized from the table's own row count, the result is CHECKED
    for ink on its bottom edge, and a render still clipped at `_MAX_RENDER_PX`
    is refused by name rather than served short. `meta`, when given, records the
    window, the number of attempts and whether the check could run at all --
    Pillow is optional, and without it clipping cannot be detected, which is a
    state a reader should see rather than a silence.
    """
    chrome = chrome or chrome_binary()
    if not chrome:
        return "no headless Chromium found (set METASCIENCE_CHROME)"
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    src = out_png.with_suffix(".html")
    src.write_text(html_text, encoding="utf-8")
    h = int(height) if height else _estimated_height(html_text)
    attempts = 0
    while True:
        attempts += 1
        h = min(h, _MAX_RENDER_PX)
        cmd = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
               f"--window-size={width},{h}", f"--screenshot={out_png}", src.as_uri()]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return f"render failed: {type(exc).__name__}: {exc}"
        if not out_png.exists() or out_png.stat().st_size == 0:
            return f"render produced no image (exit {proc.returncode}): {proc.stderr[-300:]!r}"
        clipped = png_is_clipped(out_png)
        if meta is not None:
            meta.update({"render_height_px": h, "render_attempts": attempts,
                         "clip_checked": clipped is not None, "clipped": bool(clipped)})
        if not clipped:
            _crop_to_content(out_png)
            return None
        if h >= _MAX_RENDER_PX:
            _crop_to_content(out_png)
            return (f"the table is taller than the {_MAX_RENDER_PX} px render window: ink reaches "
                    "the bottom edge of the image, so the rows below it were never drawn. Refused "
                    "rather than served short")
        h *= 2


def _crop_to_content(png: Path, margin: int = 24) -> bool:
    """Trim the blank canvas below and beside the table.

    Chromium's `--screenshot` captures the whole window, so a one-column table
    arrived as 1400x5000 with the table in the top 700 px -- 86% white, all of
    it charged against the model's image budget. Pillow trims to the ink; with
    no Pillow the image is left whole, and the caller's cache key (the PNG's
    bytes) means a later crop re-reads the table rather than reusing a reading
    of a different image.
    """
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return False
    with Image.open(png) as im:
        rgb = im.convert("RGB")
        bg = Image.new("RGB", rgb.size, (255, 255, 255))
        bbox = ImageChops.difference(rgb, bg).getbbox()
        if not bbox:
            return False
        l, t, r, b = bbox
        box = (max(0, l - margin), max(0, t - margin), min(rgb.width, r + margin), min(rgb.height, b + margin))
        rgb.crop(box).save(png)
    return True


# ---------------------------------------------------------------------------
# the reading
# ---------------------------------------------------------------------------

def lossy_text(cells: list[dict], col_labels: list[str]) -> str:
    """The walker's cells as pipe rows: the characters, not the structure."""
    rows: dict[Any, list[dict]] = {}
    for c in cells:
        rows.setdefault(c.get("row"), []).append(c)
    lines = ["| " + " | ".join(str(l) for l in col_labels) + " |"] if col_labels else []
    for r in sorted(rows, key=lambda x: (x is None, x)):
        cs = sorted(rows[r], key=lambda c: (c.get("col") is None, c.get("col")))
        stub = str(cs[0].get("row_label") or "")
        lines.append("| " + stub + " | " + " | ".join(str(c.get("raw") or "") for c in cs) + " |")
    return "\n".join(lines)


def prompt(png: Path, text: str, label: str, caption: str | None, footnotes: list[str],
           context: dict | None = None, page_image: bool = False) -> str:
    fn = "\n".join(f"- {f}" for f in footnotes) if footnotes else "(none)"
    stats = ", ".join(TIDY_STATISTICS)
    ctx = context or {}
    cites = ctx.get("citing_passages") or "(none found)"
    vocab = ctx.get("vocabulary") or "(no declared variables available for this reading)"
    groups = ctx.get("groups") or "(no declared groups available for this reading)"
    # A PAGE IS NOT A TABLE. Every other render draws the one table and nothing
    # else; a PDF supplement has no markup to draw from, so the image is the
    # whole page and may carry a heading, a footnote block, or a second table.
    # The cells below are what says which table was asked about.
    scope = ("\nThe image is a full supplement page; the table to read is the one whose cells are "
             "listed below.\n" if page_image else "")
    # THE CLOSED VOCABULARY IS ALREADY IN THIS PROMPT, in the `variable_id` line
    # below: "the DECLARED ids below when one fits exactly ... Null when nothing
    # fits exactly; never coin an id." `prompts.CLOSED_VOCABULARY` says the same
    # thing to the passes that had no such sentence, and is deliberately NOT
    # pasted in here: what this prompt serves enters a reading's cache key only
    # through `PROMPT_VERSION`, so changing the text obliges a bump, which
    # discards every cached reading in every corpus. It would buy nothing --
    # the instruction is here already, and `structure.close_vocabulary` enforces
    # it whatever the model writes.
    return f"""\
You are reading ONE printed table from a scientific paper and making its variable-value relationships
EXPLICIT. Nothing is computed, filled, or inferred beyond what the table itself lays out.

First read the rendered image of the table with the Read tool:
{png}
{scope}
The image is the authority on STRUCTURE: which values sit under which header, which rows sit under
which banner, where a header spans several columns. The text below carries the same characters in a
structure-lossy form and is there so you copy them exactly.

Produce, in the schema you are given, one RECORD PER PRINTED CELL, listing every number in the cell
under `numbers` -- `38 (59%)` is two (count, percentage), `3.1 (3.0-3.2)` three (mean or estimate,
ci_lower, ci_upper), `1.01 (0.38)` under a `Coefficient` header two (coefficient, se; or mean, sd --
whichever the header, footnote or citing text says; `other` when nothing says), `1 [Reference]` one,
`--` or `NA` none. A cell with no number is still a record (empty `numbers`). Each record states:
- `variable`: what is measured, in the paper's own words, with the banner resolved. A banner that is
  a variable (`State` over `Pennsylvania`/`Missouri`) makes the stub a `level`; a banner that is a topic
  (`Covariates` over `Communities That Care`) makes the stub the variable and `level` null.
- `group`: the column's arm, model, subgroup or time as printed; null when the column is the whole sample.
- `statistic`: one of {stats}. Read it off the header, footnote, row label, caption or the citing text;
  `cell_form` only for a form that is unambiguous on its own (`59%` is a percentage; `< .001` is a p).
  `statistic_basis` says which. When NOTHING states it and you would be reasoning by analogy with the
  neighbouring rows, say so: `statistic_basis: inferred` with your best reading of the kind. Never
  silently upgrade an inference to a reading.
- `cell`: the whole printed cell; `row_label`, `column_label`, `column_index` (1-based position among
  the column labels -- identical headers are told apart only by this), `section`: where it sat, as
  printed; each entry of `numbers`: one number exactly as printed with its kind and basis.
- `reference_group_id` and `contrast`: for a ratio, difference or other contrast, the declared group it is
  measured AGAINST and the comparison in words -- a `1 [Reference]` row marks the reference; a table with
  two contrast families over the same stubs (veterans vs nonveterans; limitations vs none) needs it on every
  such cell. Null for a descriptive cell.
- `variable_id`, `level_id`, `group_id`: the DECLARED ids below when one fits exactly -- the paper's own
  definition of the variable, its levels, and the arm or model a column reports on. Use the passages that
  cite this table to resolve what the headers leave implicit (which model each `Coefficient` span is;
  whether `(1.13)` is an SD or an SE). Null when nothing fits exactly; never coin an id.
Keep every character of the printed numbers: signs, dashes, spaces, footnote markers. A banner is not
an entry. A column with no header is named `(unlabelled column N)`. Put in `notes` anything the table
leaves genuinely unstated (identical headers with no model labels) rather than resolving it yourself.

TABLE {label}
CAPTION: {caption or "(none)"}
FOOTNOTES:
{fn}

PASSAGES IN THE PAPER THAT CITE THIS TABLE (Methods and Results; the authority on what the headers mean):
{cites}

DECLARED VARIABLES (id, name, kind, units, levels), from the paper's Methods:
{vocab}

DECLARED GROUPS (id, label) per study:
{groups}

STRUCTURE-LOSSY TEXT:
{text}
"""


#: The largest table read in one call. A 189-cell, 756-numeral table timed out
#: twice at 15 minutes before the reading became one record per CELL, and the
#: meta-analysis Table 2 is 1,845 cells: one record per cell is still more
#: output than the cap holds, so the table has no reading path at all. Blocks of
#: about this many cells do, and the conservation check is then over their
#: UNION, which is the only reading of "did this table survive".
_MAX_BLOCK_CELLS = 150


def row_blocks(table: dict, max_cells: int = _MAX_BLOCK_CELLS) -> list[dict]:
    """A long table cut into contiguous bands of rows, each about `max_cells`.

    `[{index, n_blocks, rows, cells}]` in printed order, where `rows` is the
    inclusive 1-based range of `<tr>` indices the block covers and `cells` is
    the walker's own cells for it. The header rows are NOT a block: they are
    repeated into every one (`table_html`), because a band of values with no
    column headers is not a table.

    A row is never split across two blocks. A single row wider than `max_cells`
    is its own block and is over the ceiling -- reporting that honestly beats
    cutting a printed row in half, which would make each half's conservation
    check a comparison against a table that was never printed.

    Returns `[]` when the table fits in one call: blocks exist to make an
    unreadable table readable, and splitting a readable one buys extra calls and
    a merge that can fail.
    """
    cells = list(table.get("cells") or [])
    if len(cells) <= max_cells:
        return []
    header_depth = int(table.get("n_header_rows") or 1)
    by_row: dict[Any, list[dict]] = {}
    for c in cells:
        by_row.setdefault(c.get("row"), []).append(c)
    body = [r for r in sorted(by_row, key=lambda x: (x is None, x))
            if isinstance(r, int) and r > header_depth]
    if not body:
        return []
    groups: list[list[int]] = [[]]
    n = 0
    for r in body:
        if groups[-1] and n + len(by_row[r]) > max_cells:
            groups.append([])
            n = 0
        groups[-1].append(r)
        n += len(by_row[r])
    out = []
    for i, g in enumerate(groups, start=1):
        out.append({"index": i, "n_blocks": len(groups), "rows": [g[0], g[-1]],
                    "row_set": set(g),
                    "cells": [c for r in g for c in by_row[r]]})
    return out


def merge_blocks(recons: list[dict | None]) -> dict:
    """One reading from a table's block readings, in printed order.

    The column labels come from the first block that states any: the header is
    repeated into every block, so the blocks either agree or one of them read
    the same header differently -- and that disagreement is reported by
    `verify_blocks` rather than resolved here.
    """
    cols: list[str] = []
    cells: list[dict] = []
    entries: list[dict] = []
    notes: list[str] = []
    for r in recons:
        if not r:
            continue
        if not cols:
            cols = list(r.get("column_labels") or [])
        if r.get("cells") is not None:
            cells += list(r.get("cells") or [])
        else:
            entries += list(r.get("entries") or [])
        if r.get("notes"):
            notes.append(str(r["notes"]))
    out: dict[str, Any] = {"caption": next((r.get("caption") for r in recons if r), None),
                           "column_labels": cols, "notes": "\n".join(notes) or None}
    if cells or not entries:
        out["cells"] = cells
    else:
        out["entries"] = entries
    return out


def verify_blocks(table: dict, blocks: list[dict],
                  recons: list[dict | None]) -> dict:
    """The union of a table's block readings, against the whole walked region.

    A MISSING BLOCK IS A REFUSAL, NOT A SHORTER TABLE. Verifying only the blocks
    that came back would pass a reading of two thirds of a table, and the digits
    it never saw would look like digits the paper never printed. So the union is
    checked against the WHOLE region -- every string the table prints, header
    rows included -- and an absent block is named.

    A block whose column labels differ from the first block's is also named:
    the header is the same header, drawn into every block, so a difference is
    two readings of one thing.

    THE REGION, NOT THE WALKER'S ROW ROLES: `verify_coarse`, for the reason
    given there. It matters more here than anywhere -- the header is redrawn
    into every block, so a header row the walker misfiled as data is counted
    once per block by one side and once in total by the other.
    """
    reasons: list[str] = []
    for b, r in zip(blocks, recons):
        if not r:
            reasons.append(f"block {b['index']} of {b['n_blocks']} (rows {b['rows'][0]}-"
                           f"{b['rows'][1]}) has no reading")
    first = next((list(r.get("column_labels") or []) for r in recons if r), [])
    for b, r in zip(blocks, recons):
        if r and list(r.get("column_labels") or []) != first:
            reasons.append(f"block {b['index']} read the repeated header differently: "
                           f"{list(r.get('column_labels') or [])[:4]} against {first[:4]}")
    merged = merge_blocks(recons)
    ver = verify_coarse(table, merged) if not reasons else {
        "verified": False, "reasons": [], "n_entries": len(entries_of(merged))}
    ver["reasons"] = reasons + list(ver.get("reasons") or [])
    ver["verified"] = not ver["reasons"]
    ver["n_blocks"] = len(blocks)
    ver["n_blocks_read"] = sum(1 for r in recons if r)
    return ver


def adapt(recon: dict) -> list[dict]:
    """The tidy entries regrouped as printed cells, in the walker's shape, with the
    entries that came from each cell riding on it as `entries`. This is the
    inverse transformation: the grid from the relationships."""
    cols = list(recon.get("column_labels") or [])
    cells: dict[tuple[str, int, str], dict] = {}
    row_index: dict[str, int] = {}
    for e in entries_of(recon):
        stub, sec = str(e.get("row_label") or ""), e.get("section")
        ci = int(e.get("column_index") or 0)
        col = cols[ci - 1] if 1 <= ci <= len(cols) else str(e.get("column_label") or "")
        row_label = f"{sec} | {stub}" if sec else stub
        row_index.setdefault(row_label, len(row_index) + 1)
        # KEYED ON THE COLUMN'S POSITION, not its label: three identical
        # `Coefficient` headers are three columns, and a key on the label folded
        # them into one and lost every value printed in the second and third.
        key = (row_label, ci, str(e.get("cell") or ""))
        c = cells.setdefault(key, {"row": row_index[row_label], "col": ci or len(cols) + 1,
                                   "row_label": row_label, "col_label": col, "raw": str(e.get("cell") or ""),
                                   "section": sec or None, "stub": stub, "entries": []})
        c["entries"].append({k: e.get(k) for k in ("variable", "level", "group", "statistic", "statistic_basis",
                                                    "statistic_as_read",
                                                    "value", "variable_id", "level_id", "group_id",
                                                    "reference_group_id", "contrast")})
    return sorted(cells.values(), key=lambda c: (c["row"], c["col"]))


_NOT_A_NUMBER = re.compile(r"(?:https?://|www\.)\S+|\S+@\S+\.\S+", re.I)


def numeral_tokens(s: Any) -> list[str]:
    """Maximal digit runs after EVERY space is removed. One rule, no grammar:
    `226 150 662` (thin-space thousands) and `226150662` give the same run,
    signs and separators are not digits and so cannot disagree, and an invented
    or dropped number still changes the multiset. URLs and e-mail addresses
    are removed first: the `4` in `cebc4cw.org` is not a printed number, and it
    refused a correct empty reading of a registry table (ajcp Table S1)."""
    text = _NOT_A_NUMBER.sub(" ", str(s or ""))
    return re.findall(r"\d+", re.sub(r"\s", "", text))


def _label_token_set(labels) -> set[str]:
    return {t for lab in labels for t in numeral_tokens(lab)}


def _walker_tokens(cells: list[dict]) -> Counter:
    """Value digits as a multiset plus label digits as a SET. A label's number
    is repeated wherever the label is (the walker folds a banner into every row
    beneath it); a value is printed once. A banner the walker read as a row
    (its text is its own row label) counts through the label set."""
    c: Counter = Counter()
    for cell in cells:
        if _norm(cell.get("raw")) == _norm(cell.get("row_label")):
            continue
        c.update(numeral_tokens(cell.get("raw")))
    labels = {str(x.get("row_label") or "") for x in cells} | {str(x.get("col_label") or "") for x in cells}
    c.update(_label_token_set(labels))
    return c


def walker_stubs(walker_cells: list[dict]) -> set[str]:
    """The normalised row stubs the walker folded into every row of the table.

    The walker's own `row_label` is the authority on what a stub IS -- it is the
    text the extractor lifted out of the grid before any model saw it.
    """
    return {n for c in walker_cells or [] if (n := _norm(c.get("row_label")))}


def walker_printed(walker_cells: list[dict]) -> set[str]:
    """Every normalised string the walker's table prints: cell text, row stubs
    and column headers. What is not in here, the table did not print."""
    out: set[str] = set()
    for c in walker_cells or []:
        for key in ("raw", "row_label", "col_label"):
            if n := _norm(c.get(key)):
                out.add(n)
    return out


def _recon_tokens(recon: dict, stubs: set[str] | None = None,
                  printed: set[str] | None = None) -> Counter:
    """The same count over the reading: each printed CELL once (entries share a
    cell), plus the labels as a set. THE WALKER'S TWO LABEL RULES, APPLIED HERE.

    RULE 1 -- A REPEATED STUB COUNTS ONCE. The walker folds a row stub into
    every row and counts it through the label SET; a reading that reads the same
    stub COLUMN as a column of cells counted it once per row. Measured on ajcp
    table:6, the EBP rating crosswalk: the walker made `Evidence-based (1)` /
    `Not Evidence-based (0)` the stub of seven rows, the reading read them as
    seven cells of a `Rating 1` column, and the reading was refused for six
    digit runs it had not invented. `stubs` is the walker's own row-label set,
    so this can only move a digit the walker already read as a label; a cell
    that is not one of them is a value and is counted as one.

    RULE 2 -- A LABEL THE WALKER'S TABLE DOES NOT PRINT CARRIES NO DIGITS. The
    reading's labels are a BALANCING device: they exist so that a banner or stub
    the walker folded into every row cancels against the one place the reading
    writes it. `(row 1)` .. `(row 7)` -- which the same reading wrote because the
    table has no printed stub, and said so in its notes -- are not that: they are
    the reading's own coordinates, and their digits refused a reading that had
    conserved every printed value. A label whose text occurs nowhere in the
    walker's table is dropped from the token set and named in
    `labels_not_printed`, so the fact that the reading named rows the table does
    not is on the record rather than inside a refusal reason.

    Both rules are OFF when the walker's cells are not supplied (`stubs` and
    `printed` None), so a caller that has only the reading gets the old count.
    """
    c: Counter = Counter()
    seen: set[tuple[str, str, int, str]] = set()
    labels: set[str] = {str(l) for l in recon.get("column_labels") or []}
    for e in entries_of(recon):
        if stubs is not None and _norm(e.get("cell")) in stubs:
            labels.add(str(e.get("cell") or ""))
        else:
            # THE SECTION IS PART OF THE CELL'S IDENTITY. Mirrored panels
            # (Veteran / Nonveteran over the same stubs) print `1 [Reference]`
            # in both; keyed without the section those twins counted once and
            # two correct readings were refused for 24 and 8 "missing" digits
            # (jamanetworkopen.37679).
            key = (str(e.get("section") or ""), str(e.get("row_label") or ""),
                   int(e.get("column_index") or 0), str(e.get("cell") or ""))
            if key not in seen:
                seen.add(key)
                c.update(numeral_tokens(e.get("cell")))
        labels.add(str(e.get("row_label") or ""))
        if e.get("section"):
            labels.add(str(e["section"]))
    c.update(_label_token_set(_printed_labels(labels, printed)))
    return c


def _printed_labels(labels: set[str], printed: set[str] | None) -> set[str]:
    if printed is None:
        return labels
    return {l for l in labels if (n := _norm(l)) and any(n in p for p in printed)}


def _unprinted_labels(labels: set[str], printed: set[str] | None) -> list[str]:
    if printed is None:
        return []
    return sorted(l for l in labels if str(l).strip()
                  and l not in _printed_labels({l}, printed))


_MARKER = re.compile(r"[a-zA-Z*\u2020\u2021\u00a7\u00b6#]+$")


def _strip_marker(s: Any) -> str:
    return _MARKER.sub("", str(s or "").strip())


_GLUED_MARKER = re.compile(r"(?<=\d)[a-zA-Z*\u2020\u2021\u00a7\u00b6#]+(?=\W|$)")


#: Typographic variants of one character, folded to the plain form. The dashes
#: were here first; the quotation marks joined them because a reading types the
#: paper's curly quotes as straight ones. Measured on PMC5557087 Table 2: the
#: walker's banner is `IPSS QOL "If you were to spend the rest of your life ...
#: (n=171)"` with curly quotes, the reading writes the same banner with straight
#: ones, and the containment test then finds no printed string holding it -- so
#: the `171` the paper prints goes missing from the reading's side of a
#: conservation count, on a reading that transcribed every cell correctly.
#: A quotation mark is not a digit and cannot make one, so this can only ever
#: decide whether two strings are the SAME string.
_TYPOGRAPHIC = str.maketrans({"−": "-", "–": "-", "—": "-",
                              "“": '"', "”": '"',
                              "‘": "'", "’": "'"})


def _norm(s: Any) -> str:
    """Whitespace, dash and quotation-mark variants and footnote markers glued
    to a digit (`2.23c`, `0.90*`) removed, so the two containment checks compare
    the printed numbers and their punctuation, not the marker's placement or the
    font the publisher set the quotes in."""
    t = _GLUED_MARKER.sub("", str(s or ""))
    return re.sub(r"\s+", "", t).translate(_TYPOGRAPHIC)


def verify(walker_cells: list[dict], recon: dict) -> dict:
    """Did the reading conserve the printed table? A verdict with reasons.

    Three checks and no more: the digits of the walker's table are the digits
    of the reading (values as a multiset, labels as a set); every entry's
    `value` sits inside its own `cell`; every `cell` is a walker cell's text or
    part of one the walker fused. Whether the reading's VARIABLE-VALUE
    relationships are right is not checkable here -- that is what the bench and
    the model's `notes` are for -- and is not pretended to be.
    """
    reasons: list[str] = []
    entries = entries_of(recon)
    stubs, printed = walker_stubs(walker_cells), walker_printed(walker_cells)
    wt, rt = _walker_tokens(walker_cells), _recon_tokens(recon, stubs, printed)
    # A NUMERAL-FREE TABLE (a registry of URLs, a list of instruments) has no
    # entries by right; "empty reading" is a refusal only when the walker's
    # cells carry digits the reading left out.
    if not entries and sum(wt.values()) > 0:
        reasons.append("empty reading")
    missing = sorted((wt - rt).elements())
    extra = sorted((rt - wt).elements())
    if missing:
        reasons.append(f"{len(missing)} digit run(s) in the walker's table absent from the reading: {missing[:8]}")
    if extra:
        reasons.append(f"{len(extra)} digit run(s) in the reading the walker's table does not contain: {extra[:8]}")
    # A FOOTNOTE MARKER IS NOT PART OF THE NUMBER. The reader keeps markers as
    # printed and may attach one to the value and not to the cell text (`2.23c`
    # in a cell written `2.23 (1.62-3.07)`); the digits already balance, so the
    # containment test ignores trailing marker letters and symbols.
    off_cell = [e.get("value") for e in entries
                if _norm(e.get("value")) and _norm(e.get("value")) not in _norm(e.get("cell"))]
    if off_cell:
        reasons.append(f"{len(off_cell)} value(s) not inside their own cell: {off_cell[:6]}")
    # TRACEABLE TO THE WALKER'S TABLE, not only to its CELLS. The same stub rule
    # from the other side: where the walker lifted a column out of the grid as
    # the row stub and the reading kept it as a column, its text is printed in
    # the table and traceable -- it is in `row_labels`, not in `raw`. Refusing it
    # cost ajcp table:6 a reading that had conserved every digit.
    walker_raw = sorted(printed)
    cells = {str(e.get("cell") or "") for e in entries}
    orphans = [c for c in cells if _norm(c) and not any(_norm(c) == w or _norm(c) in w for w in walker_raw)]
    if orphans:
        reasons.append(f"{len(orphans)} cell(s) traceable to no walker cell: {orphans[:6]}")
    unprinted = _unprinted_labels(
        {str(e.get("row_label") or "") for e in entries}
        | {str(e.get("section") or "") for e in entries if e.get("section")}
        | {str(l) for l in recon.get("column_labels") or []}, printed)
    ncol = len(recon.get("column_labels") or [])
    bad_idx = [e.get("column_index") for e in entries
               if not isinstance(e.get("column_index"), int) or not (1 <= e["column_index"] <= max(ncol, 1))]
    if bad_idx:
        reasons.append(f"{len(bad_idx)} entr(ies) with a column_index outside 1..{ncol}: {bad_idx[:6]}")
    bad_stat = sorted({str(e.get("statistic")) for e in entries if e.get("statistic") not in TIDY_STATISTICS})
    if bad_stat:
        reasons.append(f"statistic outside the vocabulary: {bad_stat[:6]}")
    # THE ADJUDICATED TIER IS NOT THE READER'S TO WRITE. `adjudicated` says that a
    # SECOND reading of the paper, under `review.apply_adjudication`'s gates,
    # changed the kind; a reading that stamps it on its own numbers is a model
    # certifying its own premise tier. That is the channel this codebase closes
    # wherever it appears -- `parallel.py:910` pops the model's own
    # `provenance_verdict` and re-derives it rather than believing it (CLAUDE.md
    # 8g) -- and the principle is about WHO may write the tier, not about how
    # strong it is. Refused rather than rewritten, because a reading that claims
    # an authority it cannot have is not a reading we should keep the rest of.
    self_stamped = sum(1 for e in entries if e.get("statistic_basis") == "adjudicated")
    if self_stamped:
        reasons.append(f"{self_stamped} number(s) claim the `adjudicated` basis: a reading may not write the "
                       "adjudicated tier; only apply_adjudication may")
    return {"verified": not reasons, "reasons": reasons,
            # NAMED, NOT SUPPRESSED. A label the table does not print carries no
            # digits (rule 2 above); that it was written at all is a fact about
            # the reading and belongs on the record, not inside a dropped token.
            "labels_not_printed": unprinted[:12],
            "n_labels_not_printed": len(unprinted),
            "n_stub_cells_counted_as_labels": sum(1 for e in entries
                                                  if _norm(e.get("cell")) in stubs),
            "n_walker_cells": len(walker_cells), "n_entries": len(entries), "n_cells_read": len(cells),
            "n_walker_tokens": sum(wt.values()), "n_recon_tokens": sum(rt.values()),
            "n_sections": len({e.get("section") for e in entries if e.get("section")}),
            "n_with_level": sum(1 for e in entries if e.get("level")),
            "n_with_group": sum(1 for e in entries if e.get("group")),
            "n_inferred_statistics": sum(1 for e in entries if e.get("statistic_basis") == "inferred"),
            "by_statistic": dict(Counter(e.get("statistic") for e in entries))}


# ---------------------------------------------------------------------------
# the coarse conservation check: the region, not the roles
# ---------------------------------------------------------------------------

def region_tokens(table: dict, skip: set[str] | None = None) -> Counter:
    """The region's digit inventory: the digit runs of each DISTINCT string the
    walked table prints, counted once per distinct string.

    ONE UNIT, AND IT IS THE PRINTED STRING. `_walker_tokens` has two -- values as
    a multiset, labels as a set -- and which is which is decided by
    `n_header_rows` and by the stub column, so a row the walker misfiles moves
    between them and the counts stop being comparable. Here the walker is asked
    only what the region PRINTS, never what each string is FOR.

    WHY DISTINCT RATHER THAN PER POSITION. The grid the walker returns is not a
    census of printed cells: `jats._expand` repeats a header cell across every
    column its colspan covers and repeats column 0 down every row its rowspan
    covers, and `_cells_from_grid` fills an empty stub down from the last
    non-empty one. Those repeats are fabricated at exactly the positions whose
    role is in doubt, so a per-position multiset would refuse an honest reading
    of every stacked header. Deduplicating on the printed string removes them
    without asking what any row is.

    THE COST, STATED: two body cells printing the SAME string count once, so a
    reading that drops one of them conserves. `over_printed` below bounds the
    other direction (a reading may not claim more copies of a string than the
    region holds anywhere), and `off_cell`/`orphans` still bind every value to a
    string the table printed. What is given up is the multiplicity of a repeated
    printed value -- which the walker's own grid cannot supply honestly.

    `skip` is a set of normalised strings the reading has no field for; see
    `_unreachable_strings`.
    """
    c: Counter = Counter()
    seen: set[str] = set(skip or ())
    for s in region_strings(table):
        n = _norm(s)
        if n and n not in seen:
            seen.add(n)
            c.update(numeral_tokens(s))
    return c


def _unreachable_strings(table: dict, named: set[str]) -> set[str]:
    """The region strings the reading's SCHEMA gives it nowhere to put, so that
    requiring them would refuse a reading for obeying its instructions.

    There is exactly one: the STUB COLUMN'S OWN HEADING. `RECON_SCHEMA` asks for
    "Leaf column headers left to right, EXCLUDING THE STUB", and no other field
    holds it -- a `row_label` is a row's stub, not the heading above the stub
    column. A table headed `Measure (n = 3 studies) | Mean` therefore prints a
    `3` that no correct reading can carry, and a strict region check refuses it.

    NAMED BY THE READING, IT COUNTS AGAIN. When the walker's depth is wrong the
    same cell is a data row's stub, which the reading DOES carry as a
    `row_label`; leaving it out would then put its digits in the reading and not
    in the region, which is the false refusal this whole function exists to stop,
    arriving from the other side. So the exclusion applies only to a string the
    reading names nowhere: it can remove a refusal and can never cause one.
    """
    return {n for row in (table.get("header_rows") or [])
            if row and (n := _norm(row[0])) and n not in named}


def region_printed(table: dict) -> set[str]:
    """Every normalised string the walked region prints. What is not in here,
    the table did not print -- the whole region's answer to `walker_printed`."""
    return {n for s in region_strings(table) if (n := _norm(s))}


def _recon_region_tokens(recon: dict, printed: set[str] | None = None
                         ) -> tuple[Counter, list[str], set[str]]:
    """The same rule on the reading: each DISTINCT string it names -- cell texts,
    row stubs, sections and column labels together -- contributes its digit runs
    once. Returns `(tokens, labels_the_region_does_not_print)`.

    RULE 2 OF `_recon_tokens` IS KEPT and rule 1 is no longer needed. A label the
    region does not print is dropped from the pool and named, because the
    reading's own coordinates (`(row 1)` .. `(row 7)`) are not evidence about the
    paper. The stub rule -- a cell whose text is one of the walker's row labels
    counts as a label -- disappears, because both sides now count a string once
    whether it was read as a stub or as a column of cells.

    A STACKED LABEL IS SPLIT, as it is on the region side. The prompt asks for
    stacked header levels "joined outer to inner with ` | `", so `Model 1 |
    Coefficient` is the reading's own join of two printed cells; counted whole it
    would contribute `1` once per column that carries `Model 1`, and the region
    prints that header once.
    """
    labels: set[str] = {str(l) for l in recon.get("column_labels") or []}
    cells: list[str] = []
    for e in entries_of(recon):
        cells.append(str(e.get("cell") or ""))
        labels.add(str(e.get("row_label") or ""))
        if e.get("section"):
            labels.add(str(e["section"]))
    c: Counter = Counter()
    seen: set[str] = set()
    named: set[str] = set()

    def take(s: str) -> None:
        n = _norm(s)
        if n and n not in seen:
            seen.add(n)
            c.update(numeral_tokens(s))

    for s in cells:
        if n := _norm(s):
            named.add(n)
        take(s)
    unprinted: list[str] = []
    # THE CAPTION IS A LABEL LIKE ANY OTHER, and it has to be, because a Word
    # supplement prints its caption as the table's first ROW: `_finish` keeps
    # that row in `header_rows`, so `eTable 4. Outcomes at 12 months` is in the
    # region and its digits would be missing from a reading that put them where
    # the schema asks -- in `caption`. Where the caption is NOT a grid row (JATS
    # keeps it in its own element) the printed filter drops it, silently: it is
    # not a stray label, it is a field that does not belong to this region.
    for lab in sorted(labels) + [str(recon.get("caption") or "")]:
        stray = False
        for part in str(lab).split(_LABEL_JOIN):
            n = _norm(part)
            if not n:
                continue
            named.add(n)
            if printed is not None and not any(n in q for q in printed):
                stray = True
                continue
            take(part)
        if stray and str(lab).strip() and lab in labels:
            unprinted.append(lab)
    return c, sorted(unprinted), named


def _region_occurrences(table: dict) -> Counter:
    """How many times each normalised string appears anywhere in the walked
    region, repeats and all. A CEILING, deliberately generous: the folded copies
    of a header or a stub are counted, so a reading is only ever caught claiming
    more copies of a string than the region holds under any reading of it."""
    c: Counter = Counter()
    for row in table.get("header_rows") or []:
        for x in row:
            if n := _norm(x):
                c[n] += 1
    for cell in table.get("cells") or []:
        for key in ("raw", "row_label", "col_label"):
            for part in str(cell.get(key) or "").split(_LABEL_JOIN):
                if n := _norm(part):
                    c[n] += 1
    return c


def verify_coarse(table: dict, recon: dict) -> dict:
    """Did the reading conserve the printed table? The same verdict as `verify`,
    computed over the REGION rather than over the walker's row roles.

    THE DEFECT THIS EXISTS FOR (the walker-as-witness spec, 2026-09-08). `verify`
    compares `_walker_tokens(walker_cells)` -- the digits of the cells the walker
    called DATA -- against the reading. A row the walker misfiles as a header
    never becomes a `walker_cells` entry, so its digits reach the comparison only
    through the flattened column labels, where they are counted ONCE however many
    times they were printed. The reading, which read the row correctly from the
    image, counts them per cell. The two are then incomparable, and the reading is
    refused for digits it did not invent -- or, the other way round, a wrong
    reading balances by accident. Five rounds of `_reads_as_measurements` fixes
    were all attempts to stop the walker being wrong; this stops the answer
    depending on whether it was.

    WHAT IS UNCHANGED. Every check that does not rest on row role is carried over
    verbatim: a value must sit inside its own cell, a cell must be traceable to a
    string the table printed, `column_index` must be inside the header,
    `statistic` must be in the closed vocabulary, and a reading may not stamp the
    `adjudicated` tier on its own numbers.

    THIS IS THE VERDICT THE DRIVER KEEPS (2026-09-15). Measured over the 17
    reference accounts, on the readings already bought: `verify` refuses 24 of 72
    tables and 9 of those refusals are FALSE -- proven so cell by cell, since
    each of the nine reproduces every distinct numeral-bearing string its table
    prints, invents none, and reproduces all 355 stratum-M key cells of those
    tables verbatim, the 10 proven-defective ones included. This form refuses 15,
    keeps every refusal `verify` was right about, and turns none of `verify`'s
    48 acceptances into a refusal. `verify` is kept beside it as the control the
    agreement is measured against (`TestConservationOverTheRegion`), not as a
    second gate; nothing calls it on the live path.
    """
    reasons: list[str] = []
    entries = entries_of(recon)
    printed = region_printed(table)
    rt, unprinted, named = _recon_region_tokens(recon, printed)
    unreachable = _unreachable_strings(table, named)
    wt = region_tokens(table, skip=unreachable)
    if not entries and sum(wt.values()) > 0:
        reasons.append("empty reading")
    missing = sorted((wt - rt).elements())
    extra = sorted((rt - wt).elements())
    if missing:
        reasons.append(f"{len(missing)} digit run(s) in the walker's table absent from the reading: {missing[:8]}")
    if extra:
        reasons.append(f"{len(extra)} digit run(s) in the reading the walker's table does not contain: {extra[:8]}")
    off_cell = [e.get("value") for e in entries
                if _norm(e.get("value")) and _norm(e.get("value")) not in _norm(e.get("cell"))]
    if off_cell:
        reasons.append(f"{len(off_cell)} value(s) not inside their own cell: {off_cell[:6]}")
    cells = {str(e.get("cell") or "") for e in entries}
    orphans = [c for c in cells if _norm(c) and not any(_norm(c) == w or _norm(c) in w for w in sorted(printed))]
    if orphans:
        reasons.append(f"{len(orphans)} cell(s) traceable to no walker cell: {orphans[:6]}")
    # THE OTHER HALF OF CONSERVATION, and the only place multiplicity survives.
    # A cell is identified as `_recon_tokens` identifies one -- section, stub,
    # column, text -- so two printed twins are two, and a reading that writes a
    # third has claimed a copy the region does not hold.
    occ = _region_occurrences(table)
    read_occ: Counter = Counter()
    seen_keys: set[tuple[str, str, int, str]] = set()
    for e in entries:
        key = (str(e.get("section") or ""), str(e.get("row_label") or ""),
               int(e.get("column_index") or 0), str(e.get("cell") or ""))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if n := _norm(e.get("cell")):
            read_occ[n] += 1
    over = sorted(s for s, k in read_occ.items() if 0 < occ.get(s, 0) < k)
    if over:
        reasons.append(f"{len(over)} string(s) read more times than the table prints them: {over[:6]}")
    ncol = len(recon.get("column_labels") or [])
    bad_idx = [e.get("column_index") for e in entries
               if not isinstance(e.get("column_index"), int) or not (1 <= e["column_index"] <= max(ncol, 1))]
    if bad_idx:
        reasons.append(f"{len(bad_idx)} entr(ies) with a column_index outside 1..{ncol}: {bad_idx[:6]}")
    bad_stat = sorted({str(e.get("statistic")) for e in entries if e.get("statistic") not in TIDY_STATISTICS})
    if bad_stat:
        reasons.append(f"statistic outside the vocabulary: {bad_stat[:6]}")
    self_stamped = sum(1 for e in entries if e.get("statistic_basis") == "adjudicated")
    if self_stamped:
        reasons.append(f"{self_stamped} number(s) claim the `adjudicated` basis: a reading may not write the "
                       "adjudicated tier; only apply_adjudication may")
    n_cells = len(table.get("cells") or [])
    return {"verified": not reasons, "reasons": reasons,
            "basis": "region",
            "labels_not_printed": unprinted[:12],
            "n_labels_not_printed": len(unprinted),
            # THE STUB COLUMN'S HEADING, which the reading has no field for and
            # was therefore not required to carry. Named rather than silent.
            "stub_headings_not_required": sorted(unreachable)[:6],
            "n_region_strings": len(printed),
            "n_walker_cells": n_cells, "n_entries": len(entries), "n_cells_read": len(cells),
            "n_walker_tokens": sum(wt.values()), "n_recon_tokens": sum(rt.values()),
            "n_over_printed": len(over),
            "n_sections": len({e.get("section") for e in entries if e.get("section")}),
            "n_with_level": sum(1 for e in entries if e.get("level")),
            "n_with_group": sum(1 for e in entries if e.get("group")),
            "n_inferred_statistics": sum(1 for e in entries if e.get("statistic_basis") == "inferred"),
            "by_statistic": dict(Counter(e.get("statistic") for e in entries))}


# ---------------------------------------------------------------------------
# the context: what the paper says about this table
# ---------------------------------------------------------------------------

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\u201c])")


_TABLE_REF = re.compile(r"\b(e)?Tables?\s+(S?\d+[a-z]?(?:\s*(?:,|and|&|\u2013|-|to|through)\s*S?\d+[a-z]?)*)", re.I)


def _tables_named(sent: str) -> set[str]:
    """Every table number a sentence cites: `Table 2`, `Tables 2, 3, 4`,
    `Tables 2 and 3`, `Tables 2-4`. The plural-list form is how a paper explains
    several tables in one sentence (`Results in Tables 2, 3, 4 are shown as
    coefficients`), and a singular-only match missed exactly that sentence."""
    out: set[str] = set()
    for m in _TABLE_REF.finditer(sent):
        # `eTable 2` (JAMA's supplement tables) is its own namespace, `E2`,
        # so it can never be mistaken for the article's Table 2.
        prefix = "E" if m.group(1) else ""
        span = m.group(2)
        for a, b in re.findall(r"(S?\d+)\s*(?:\u2013|-|to|through)\s*(S?\d+)", span, re.I):
            if a[:1].upper() == "S" or b[:1].upper() == "S":
                continue
            lo, hi = int(a), int(b)
            if 0 < hi - lo < 30:
                out.update(prefix + str(i) for i in range(lo, hi + 1))
        out.update(prefix + x.upper() for x in re.findall(r"S?\d+", span))
    return out


def citing_passages(text: str, label: str | None, max_chars: int = 2500) -> str:
    """Every sentence of the body that cites this table, in reading order.

    Greg, 2026-08-29: "any attempt to understand these tables that is not
    informed by the paper/supplement text will fail." The caption does not say
    which model each of ajcp Table 2's three `Coefficient` spans is; the
    Methods paragraph that cites the table does.
    """
    lab = str(label or "").strip()
    m = re.search(r"(S?\d+|[IVX]+)\s*$", lab)
    if not m:
        return ""
    num = m.group(1).upper()
    if re.match(r"eTable\b", lab, re.I):
        num = "E" + num
    out: list[str] = []
    total = 0
    for sent in _SENT.split(text or ""):
        if num in _tables_named(sent):
            s = " ".join(sent.split())
            if total + len(s) > max_chars:
                out.append("[...further citing sentences omitted for length]")
                break
            out.append(s)
            total += len(s)
    return "\n".join(f"- {s}" for s in out)


def vocabulary(p2: dict | None, max_chars: int = 6000) -> str:
    """The declared variables as a compact list the reader can name ids from."""
    lines: list[str] = []
    for v in (p2 or {}).get("variables") or []:
        lv = ", ".join(f"{l.get('label')}{' = ' + str(l['value']) if l.get('value') is not None else ''}"
                       for l in (v.get("levels") or []) if isinstance(l, dict))
        lv_ids = ", ".join(f"{l.get('id')}" for l in (v.get("levels") or []) if isinstance(l, dict) and l.get("id"))
        lines.append(f"- {v.get('id')}: {v.get('name')} [{v.get('kind')}; units {v.get('units') or 'not stated'}]"
                     + (f"; levels: {lv} (ids: {lv_ids})" if lv else ""))
    s = "\n".join(lines)
    return s if len(s) <= max_chars else s[:max_chars] + "\n[...truncated]"


def declared_groups(p1: dict | None, max_chars: int = 3000) -> str:
    lines: list[str] = []
    for st in (p1 or {}).get("studies") or []:
        gs = "; ".join(f"{g.get('id')} = {g.get('label')}" for g in (st.get("groups") or []))
        lines.append(f"- {st.get('id')} ({st.get('label')}): {gs or 'no groups'}")
    s = "\n".join(lines)
    return s if len(s) <= max_chars else s[:max_chars] + "\n[...truncated]"


def context_for(table: dict, text: str | None, p1: dict | None, p2: dict | None) -> dict:
    label = table.get("label") or table.get("walker_label")
    if table.get("source") == "supplement":
        # The body cites a supplement's own "Table 1" as `Table S1` / `eTable 1`;
        # both spellings are tried, and a miss is only a shorter context.
        m = _SUPP_LABEL_NUM.search(str(table.get("walker_label") or label or ""))
        n = m.group(1) if m else None
        cites = "\n".join(x for x in (citing_passages(text or "", f"Table S{n}") if n else "",
                                      citing_passages(text or "", f"eTable {n}") if n else "") if x)
        return {"citing_passages": cites, "vocabulary": vocabulary(p2), "groups": declared_groups(p1)}
    return {"citing_passages": citing_passages(text or "", label),
            "vocabulary": vocabulary(p2), "groups": declared_groups(p1)}


# ---------------------------------------------------------------------------
# the driver
# ---------------------------------------------------------------------------

def _cache_key(table: dict, render_key: str | None, context: dict | None = None) -> str:
    """What a cached reading is a reading OF: the prompt version, the walker's
    cells (the text served) and what was drawn (the image served). The PNG's
    bytes are deliberately NOT in the key -- a change to the renderer's margins
    or crop redraws the same table, and re-buying a reading of it would be
    paying for the same evidence twice.

    `render_key` is the HTML for a table drawn from markup and, for a PDF
    supplement, a description of the pages drawn: the pages are what identifies
    that image, and the PNG's bytes would move with the dpi and the crop."""
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    h.update(json.dumps(table.get("cells") or [], sort_keys=True, ensure_ascii=False).encode())
    h.update((render_key or "").encode("utf-8"))
    h.update(json.dumps(context or {}, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()[:16]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_") or "table"


def _buy_reading(name: str, p: str, out_dir: Path, *, model: str, key: str, n_cells: int,
                 stamp: dict | None, problems: list[str]) -> dict:
    """Pay for one table reading and put it somewhere a wiped run directory
    cannot take it with. Raises `PassFailed` like the call it wraps.

    THE DEPOSIT IS HERE RATHER THAN AT THE CALL SITES so that buying a reading
    and keeping it are one act. Both sites -- a whole table and a block of a
    long one -- used the same call with the same key, and the money was lost
    three times because the only copy was written inside the directory being
    wiped (`reading_store`). A third site added to this module gets the store
    by construction; a third site added around `run_pass` would not.

    A 189-cell table timed out twice at a flat 900 s; the reading is written
    cell by cell, so the budget grows with the table.
    """
    res = _passes.run_pass(name, p, out_dir, model=model, schema=RECON_SCHEMA, tools="Read",
                           timeout_s=900 + 6 * n_cells, retries=1,
                           extra_meta={"cache_key": key, **(stamp or {})})
    _store.bought_here(name, out_dir)
    note = _store.deposit(name, out_dir, key).get("note")
    if note:
        problems.append(note)
    return res


def _refuse(rec: dict, table: dict, recon: dict, ver: dict, kept: Path | list[Path],
            problems: list[str], tid: str) -> None:
    """Record a refusal AS A SUBSTITUTION: the reading was bought and discarded,
    and the walker's grid took its place.

    THE SILENCE THIS REPLACES. A refused table used to leave one sentence in
    `problems` and nothing else, so the account could not say -- and a reader
    could not ask -- which of its cells were typed by a reading of the printed
    table and which by the walker's fallback. That is both a money leak (a paid
    artifact discarded with no trace of what it cost or where it went) and the
    mechanism by which a FALSE refusal degrades correctly-read cells invisibly.
    MEASURED 2026-09-15 on the seventeen reference accounts: withdrawing the nine
    false refusals retypes 260 printed cells that both runs place, and the shape
    of the retyping says which side was right -- 138 cells of PMC4229637 Table 4
    were `dispersion_unstated`/`other` under the fallback and are 127 count and
    127 percentage values under the reading, on a table whose 126 count-percent
    cells the stratum-M key proves reconcilable.

    So the fact is named, docketed and costed here, carried into the account by
    `bind._gaps` as `table_reading_bought_and_discarded`, and printed in section
    7 of `account.md`. The discarded reading is not deleted: `kept` says where it
    still is, so the substitution can be reviewed rather than only regretted.
    """
    rec["status"] = "refused"
    rec["substitution"] = {
        "happened": True,
        "what": ("the model's reading of this table was discarded and the walker's own grid "
                 "was kept in its place"),
        "why": list(ver.get("reasons") or []),
        "basis": ver.get("basis"),
        "reading_model": rec.get("model"),
        "reading_cost_usd": rec.get("cost_usd"),
        "reading_reused": bool(rec.get("reused") or rec.get("reused_from")
                               or any((b.get("status") == "reused") for b in (rec.get("blocks") or []))),
        # RELATIVE TO THE ACCOUNT, so the pointer survives the directory being
        # moved or copied to Drive -- which is what R17 says must happen to
        # anything paid for.
        "reading_kept_at": [f"{Path(k).parent.name}/{Path(k).name}"
                            for k in (kept if isinstance(kept, list) else [kept])],
        "n_entries_discarded": len(entries_of(recon)),
        "n_cells_discarded": len({str(e.get("cell") or "") for e in entries_of(recon)}),
        "n_walker_cells_used_instead": len(table.get("walker_cells") or []),
        "consequence": ("every cell of this table is typed from the walker's grid, not from a "
                        "reading of the printed table; a cell the reading had right is now "
                        "whatever the fallback makes of it"),
    }
    cost = rec.get("cost_usd")
    problems.append(
        f"{tid}: reconstruction refused, walker cells kept"
        + (f" (${float(cost):.2f} of reading discarded)" if cost else "")
        + ": " + "; ".join(ver.get("reasons") or [])[:300])


def reconstruct_table(paper_dir: Path, table: dict, index: int, out_dir: Path, *,
                      model: str | None, root: ET.Element | None, problems: list[str],
                      context: dict | None = None, stamp: dict | None = None,
                      siblings: list[dict] | None = None) -> dict:
    """One table: render, read (or reuse), verify. Returns the reconstruction record and,
    when verified, replaces `table['cells']` (keeping `walker_cells`)."""
    tid = f"table:{index}"
    rec: dict[str, Any] = {"table_id": tid, "status": "not_attempted", "reason": None,
                           "model": None, "cost_usd": None, "png": None, "verification": None}
    walker_cells = list(table.get("cells") or [])
    table["walker_cells"] = walker_cells
    if not walker_cells:
        # NOTHING TO CONSERVE, SO NOTHING TO BUY. `verify` compares the
        # reading's digits against the walker's; with no walker cells any
        # reading carrying a digit is refused and any empty one is accepted
        # without evidence, so the call can only tell us what we already know.
        # `locate_pdf_table` has said exactly this since it was written and the
        # article path did not: 10.1038/s41392-026-02904-0 carries two
        # supplement tables the walker read no cells from, and both would have
        # been rendered and read.
        #
        # A STATE, NOT A FAILURE. The walk of this table produced nothing, which
        # is a fact about our extraction of it and not evidence that the paper
        # printed an empty table.
        rec["status"] = "empty_after_walk"
        rec["reason"] = ("the walker read no cells from this table, so a reading of it could not "
                         "be verified against anything; not rendered and not read")
        problems.append(f"{tid}: {table.get('label') or table.get('walker_label')} came back from "
                        "the walk with no cells; not rendered and not read (empty_after_walk)")
        return rec
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(tid)}"
    png = out_dir / f"{stem}.png"
    html_text: str | None = None
    render_key: str | None = None
    page_image = False
    if table.get("source") == "supplement":
        # A SUPPLEMENT TABLE IS READ THE SAME WAY, from its own file. Greg,
        # 2026-08-27: the main paper, the supplement and a deposit are the same
        # evidence -- and 2026-09-06: a supplement is not a second-class input
        # and is presented to the model as the article is. A Word supplement is
        # drawn from its markup; a PDF supplement has none, so its own page is
        # drawn instead and located first (`locate_pdf_table`).
        html_text, drawn, meta, why = supplement_table_render(paper_dir, table, png,
                                                              siblings=siblings)
        rec.update({k: v for k, v in meta.items() if k != "render"})
        rec["render"] = meta.get("render")
        if html_text is None and drawn is None:
            rec["reason"] = why
            return rec
        if drawn is not None:
            page_image = True
            render_key = f"pdf_page|{meta.get('supplement_file')}|{meta.get('pages')}|dpi{_PAGE_DPI}"
    else:
        if root is None:
            rec["reason"] = "no publisher XML for this paper (PDF tables are a later step)"
            return rec
        # THE FALLBACK IS A POSITION, so it is given one. `table_num` is now
        # the number the paper PRINTS, and on a publisher that lists Tab5
        # before Tab4 the two differ -- passing the printed number as an
        # ordinal would fetch the wrong `<table-wrap>` on exactly the papers
        # this distinction exists for.
        el = table_element(root, table.get("wrap_id") or table.get("table_id"),
                           table.get("position") or index)
        if el is None:
            rec["reason"] = "the walker's <table-wrap> could not be located in the XML"
            return rec
        html_text = table_html(el)
        if html_text is None:
            rec["reason"] = "CALS or graphic-only markup; not rendered"
            return rec
        blocks = row_blocks(table)
        if blocks:
            return _reconstruct_in_blocks(table, tid, stem, out_dir, el, blocks,
                                          model=model, problems=problems, context=context,
                                          stamp=stamp, rec=rec)
    if html_text is not None:
        render_key = html_text
        rmeta: dict[str, Any] = {}
        err = render_png(html_text, png, meta=rmeta)
        rec.update(rmeta)
        if err:
            rec["status"], rec["reason"] = "not_rendered", err
            return rec
    rec["png"] = str(png)
    key = _cache_key(table, render_key, context)
    name = f"{stem}.recon"
    cached, notes = _store.reuse(name, out_dir, key)
    problems += [f"{tid}: {n}" for n in notes]
    recon = None
    if cached is not None:
        recon = cached["data"]
        rec["model"] = (cached.get("meta") or {}).get("model")
        rec["cost_usd"] = (cached.get("meta") or {}).get("cost_usd")
        rec["reused"] = True
        rec["reused_from"] = cached.get("reused_from")
    elif model:
        col_labels = list(dict.fromkeys(str(c.get("col_label") or "") for c in walker_cells))
        text = lossy_text(walker_cells, col_labels)
        p = prompt(png, text, table.get("label") or tid, table.get("caption"),
                   list(table.get("footnotes") or []), context=context,
                   page_image=page_image)
        try:
            res = _buy_reading(name, p, out_dir, model=model, key=key,
                               n_cells=len(walker_cells), stamp=stamp, problems=problems)
        except _passes.PassFailed as exc:
            rec["status"], rec["reason"] = "failed", str(exc)[:400]
            problems.append(f"{tid}: reconstruction failed: {str(exc)[:200]}")
            return rec
        recon = res["data"]
        rec["model"], rec["cost_usd"] = model, res["meta"].get("cost_usd")
        rec["schema_problems"] = res["problems"]
    else:
        rec["reason"] = "no cached reconstruction and the model is off (--no-llm)"
        return rec
    # THE REGION, NOT THE WALKER'S ROW ROLES (`verify_coarse`). `table` still
    # carries the walker's own cells and label lists here -- they are replaced
    # below, and only when the reading is kept.
    ver = verify_coarse(table, recon)
    rec["verification"] = ver
    rec["notes"] = recon.get("notes")
    if ver["verified"]:
        rec["status"] = "verified"
        table["walker_cells"] = walker_cells
        table["cells"] = adapt(recon)
        table["entries"] = entries_of(recon)
        table["reconstructed_column_labels"] = list(recon.get("column_labels") or [])
        _refresh_labels(table)
    else:
        _refuse(rec, table, recon, ver, out_dir / f"{name}.json", problems, tid)
    return rec


def _reconstruct_in_blocks(table: dict, tid: str, stem: str, out_dir: Path,
                           el: ET.Element, blocks: list[dict], *,
                           model: str | None, problems: list[str],
                           context: dict | None, stamp: dict | None,
                           rec: dict) -> dict:
    """A table too long for one call, read as bands of rows and checked as one.

    Each block is a table in its own right -- the header rows are drawn into all
    of them -- so it is rendered, cached and read through exactly the same call
    as any other table. What differs is the CHECK: the conservation test is over
    the UNION of the readings against the whole walker table, so a block that
    never came back is a refusal rather than a shorter table.
    """
    rec["blocks"] = []
    recons: list[dict | None] = []
    total_cost = 0.0
    for b in blocks:
        note = f"rows {b['rows'][0]}-{b['rows'][1]} of this table, block {b['index']} of {b['n_blocks']}"
        html_text = table_html(el, keep_rows=b["row_set"], note=note)
        png = out_dir / f"{stem}.b{b['index']}.png"
        entry: dict[str, Any] = {"index": b["index"], "rows": b["rows"], "n_cells": len(b["cells"]),
                                 "png": str(png), "status": "not_attempted", "cost_usd": None}
        rec["blocks"].append(entry)
        rmeta: dict[str, Any] = {}
        err = render_png(html_text or "", png, meta=rmeta)
        entry.update(rmeta)
        if err:
            entry["status"], entry["reason"] = "not_rendered", err
            recons.append(None)
            continue
        key = _cache_key({"cells": b["cells"]}, html_text, context)
        name = f"{stem}.b{b['index']}.recon"
        cached, notes = _store.reuse(name, out_dir, key)
        problems += [f"{tid} block {b['index']}: {n}" for n in notes]
        if cached is not None:
            recons.append(cached["data"])
            entry.update({"status": "reused", "cost_usd": (cached.get("meta") or {}).get("cost_usd"),
                          "reused_from": cached.get("reused_from")})
        elif model:
            cols = list(dict.fromkeys(str(c.get("col_label") or "") for c in b["cells"]))
            p = prompt(png, lossy_text(b["cells"], cols), f"{table.get('label') or tid} ({note})",
                       table.get("caption"), list(table.get("footnotes") or []), context=context)
            try:
                res = _buy_reading(name, p, out_dir, model=model, key=key,
                                   n_cells=len(b["cells"]), stamp=stamp, problems=problems)
            except _passes.PassFailed as exc:
                entry["status"], entry["reason"] = "failed", str(exc)[:400]
                recons.append(None)
                continue
            recons.append(res["data"])
            entry.update({"status": "read", "cost_usd": res["meta"].get("cost_usd")})
        else:
            entry["reason"] = "no cached reconstruction and the model is off (--no-llm)"
            recons.append(None)
            continue
        total_cost += float(entry.get("cost_usd") or 0.0)
    rec["model"] = model
    rec["cost_usd"] = total_cost or None
    rec["png"] = [b["png"] for b in rec["blocks"]]
    if not any(r for r in recons):
        rec["status"] = "not_attempted"
        rec["reason"] = (f"{len(blocks)} row block(s), none read: "
                         + "; ".join(str(b.get("reason") or b["status"]) for b in rec["blocks"])[:300])
        return rec
    ver = verify_blocks(table, blocks, recons)
    rec["verification"] = ver
    merged = merge_blocks(recons)
    rec["notes"] = merged.get("notes")
    if ver["verified"]:
        rec["status"] = "verified"
        table["cells"] = adapt(merged)
        table["entries"] = entries_of(merged)
        table["reconstructed_column_labels"] = list(merged.get("column_labels") or [])
        _refresh_labels(table)
    else:
        _refuse(rec, table, merged, ver,
                [out_dir / f"{stem}.b{b['index']}.recon.json" for b in blocks], problems, tid)
    return rec


def cell_form(raw: Any) -> str:
    """The printed shape of a cell with its digits erased: `9 (9)`, `9 (9%)`,
    `< .9`, `9 [9, 9]`. Two cells of one form under one header are the same
    kind of thing or the table is lying."""
    t = re.sub(r"\d+", "9", " ".join(str(raw or "").split()))
    t = re.sub(r"9(?:[.,]9)+", "9", t)
    return re.sub(r"\s+", " ", t).strip()


def kind_consistency(tables: list[dict]) -> list[str]:
    """Identical column headers within one paper must carry identical statistic
    kinds; where they do not, every entry under that header is marked
    `statistic_disputed` and the disagreement is returned as a problem line.

    MEASURED on ajcp.70049, 2026-09-06: three structurally identical tables
    (`Coefficient | M (SD)` over `Coefficient | p`, each with the same citing
    sentence in view) were read as coefficient/se, coefficient/sd and mean/sd
    in one run. The numbers were conserved every time; the KIND was not
    stable, and a kind is a check's premise. This is the test-retest
    instrument applied inside one paper, model-free: it decides nothing about
    which reading is right, it only says the readings disagree.
    """
    kinds: dict[str, dict[tuple, list[tuple[str, dict]]]] = {}
    for t in tables:
        for c in t.get("cells") or []:
            es = c.get("entries") or []
            if not es:
                continue
            # HEADER AND PRINTED FORM TOGETHER. A single descriptive column
            # carries `n = 64`, `38 (59%)` and `1.67 (2.15)` in successive rows,
            # and those are three kinds by right; keyed on the header alone the
            # check disputed all 33 entries of ajcp Table 1. `9 (9)` under the
            # same header read as se in one table and sd in the next is the
            # disagreement.
            key = (" ".join(str(c.get("col_label") or "").lower().split()) + " :: " + cell_form(c.get("raw")))
            sig = tuple(e.get("statistic") for e in es)
            kinds.setdefault(key, {}).setdefault(sig, []).append((t.get("id"), c))
    problems: list[str] = []
    for key, by_sig in kinds.items():
        if len(by_sig) < 2:
            continue
        where = {sig: sorted({tid for tid, _ in cells}) for sig, cells in by_sig.items()}
        problems.append(f"column `{key}` read with different kinds across tables: "
                        + "; ".join(f"{'/'.join(map(str, sig))} in {', '.join(tids)}" for sig, tids in where.items())
                        + " -- entries marked statistic_disputed")
        for cells in by_sig.values():
            for _, c in cells:
                for e in c.get("entries") or []:
                    e["statistic_disputed"] = True
    return problems


def _refresh_labels(table: dict) -> None:
    """The document record's derived label lists follow the cells now on it."""
    rl: list[str] = []
    cl: list[str] = []
    for c in table.get("cells") or []:
        if c.get("row_label") and c["row_label"] not in rl:
            rl.append(c["row_label"])
        if c.get("col_label") and c["col_label"] not in cl:
            cl.append(c["col_label"])
    if "row_labels" in table:
        table["row_labels"] = rl
    if "col_labels" in table:
        table["col_labels"] = cl
    if "n_cells" in table:
        table["n_cells"] = len(table.get("cells") or [])


def reconstruct_tables(paper_dir: str | Path, tables: list[dict], out_dir: str | Path, *,
                       model: str | None, problems: list[str], text: str | None = None,
                       p1: dict | None = None, p2: dict | None = None,
                       stamp: dict | None = None) -> list[dict]:
    """Every table through `reconstruct_table`, in order, IN CONTEXT: the
    passages that cite it and the declared variables and groups from passes 1
    and 2 (Greg, 2026-09-06: the caption is not enough; the Methods say what
    the headers leave implicit). Runs AFTER pass 2 for that reason. Mutates the
    records (see `reconstruct_table`) and returns the reconstruction records.

    `stamp` is the structure this reading selected its ids from
    (`structure.stamp`), recorded in each reading's meta so that an account
    assembled from readings of two different vocabularies can be refused."""
    base, out = Path(paper_dir), Path(out_dir)
    # EVERYTHING ALREADY PAID FOR IN THIS DIRECTORY, KEPT SOMEWHERE ELSE, before
    # anything is read: a table that no longer renders never reaches its own
    # cache key, and its reading would otherwise be lost with the directory.
    problems += _store.backfill(out)["notes"]
    root = None
    try:
        xp = _jats.find_xml(base)
        if xp is not None:
            root = ET.parse(str(xp)).getroot()
    except (OSError, ET.ParseError) as exc:
        problems.append(f"table reconstruction: XML unreadable ({type(exc).__name__}: {exc})")
    recs = []
    for i, t in enumerate(tables, start=1):
        ctx = context_for(t, text, p1, p2) if (text or p1 or p2) else None
        # THE OTHER WALKED TABLES, so a PDF supplement's page render can be cut
        # to this table alone: a page carrying two of them is the documented
        # cross-attribution route (`table_band`).
        recs.append(reconstruct_table(base, t, i, out, model=model, root=root, problems=problems,
                                      context=ctx, stamp=stamp,
                                      siblings=[x for x in tables if x is not t]))
        t["reconstruction"] = recs[-1]
    problems += kind_consistency([t for t in tables if (t.get("reconstruction") or {}).get("status") == "verified"])
    return recs
