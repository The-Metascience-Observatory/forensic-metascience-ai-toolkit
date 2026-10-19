"""Can we find, in the paper, the text a finding says it is quoting?

WHY THIS EXISTS
---------------
`findings[].quote` is described in the schema as "verbatim reported text/values
from the paper", and every finding has one -- 505 of 505 across the corpus. It
was never checked. A field named `quote` that nobody verifies is an invitation
to read composed text as copied text.

MEASURED by THIS module over 499 findings it could build a haystack for (body
text, JATS prose, table grids and their raw header rows, figure captions, the
PyMuPDF text layer, supplements):

    verbatim   186  37%   found as one contiguous span
    elided      63  13%   an explicit ellipsis, every fragment found
    stitched   228  46%   not contiguous, but every number in it is in the paper
    unverified  22   4%   nothing located

A separate pass with a looser rubric for what counts as elided scored the same
corpus 50/19/28/2. The gap is entirely in that rubric, not in the search -- this
one demands a real ellipsis, so a quote joining two sentences with " / " lands
in `stitched` rather than `elided`. That is deliberate: `stitched` under-claims
and `elided` over-claims, and this label is shown to a reader as though it were
a quotation.

The 22 were hand-adjudicated in that pass and found to contain NO FABRICATIONS.
Every one was a limit of the search: a paper printing "Eighty-seven per cent" in
words where the quote gives 87; a quote that is the literal raw header row of a
table; a page reference `p.22` read as the decimal .22 by a naive tokenizer
(fixed here -- see `_NUMBER`). So this module is NOT a fraud detector aimed at
the model. It exists because nearly half of all quotes are STITCHED, and a
stitched quote is the one thing a reader cannot act on: they search the PDF for
it and find nothing.

RE-MEASURED 2026-08-12, over the 637 quotes in the archive that were actually
supplied -- 429 finding quotes and 208 tool-call quotes, across the 18 archived
runs with a findings file. The question asked was whether the ONE-CONTIGUOUS-
SPAN rule is what caps this at half. It is not:

    located (verbatim or elided), before     409 / 637   64.2%
    located (verbatim or elided), after      485 / 637   76.1%

      finding quotes      257 / 429  59.9%  ->  298 / 429  69.5%
      tool-call quotes    152 / 208  73.1%  ->  187 / 208  89.9%

and not one verdict moved DOWN. The whole of that gain is `fold_rendering` --
the model copies from what an extraction tool showed it, and this module
searched a haystack built by DIFFERENT extractors that the model never saw.
`p &lt; 0.05` against `p < 0.05`; `means (cid:2)sem` against `means ± sem`; a
table row drawn with pipes against one drawn with spaces; `fi nal` against
`final`; `α ≤ .05` against `alpha <= .05`. Each of those is one paper seen
twice, and every one of them was being reported to a reader as a quote that is
not in the paper.

WHAT IT IS WORTH, at the place the reader meets it. Of the 162 findings across
the archive that trace back to a producing call's passage, the share whose
passage a reader can open the PDF and find goes 115/162 (71%) -> 149/162 (92%).
Thirty-four accusations shipped saying "this sentence was composed by the
review" over a sentence the authors had written.

WHAT WAS MEASURED AND REJECTED. Allowing a quote to be k disjoint verified
spans -- the obvious relaxation, and the one this rule was suspected of needing
-- recovers 9 of 637 quotes (1.4%), or 15 (2.4%) in the variant that also drops
the same-source and reading-order constraints. That second variant is precisely
the one that lets a model assemble support from opposite ends of a paper. A new
verdict in the vocabulary, in the schema, in two renderers and in the viewer, to
buy 1.4% and re-open the hole the rule exists to close, is not a trade worth
making. The rule stays; the renderer was the bug.

WHAT THE VERDICTS MEAN
----------------------
`verbatim` and `elided` mean a reader can go and look. `stitched` means the
numbers are real but the sentence was assembled by us and does not exist in the
paper -- honest, useful, and it must say so rather than pass as a quotation.
`unverified` means OUR SEARCH failed, and it is phrased that way: on the
evidence above the overwhelmingly likely cause is this module's haystack, not
the authors and not the model. Never report our search failing as a claim about
the paper.

Set by the pipeline, never by the model, exactly as `reproduction_valid` is and
for the same reason: a self-assessment the subject writes is not a check.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

#: Fragments shorter than this are too common to prove anything -- "the" or
#: "0.05" appears in every paper, so requiring them found would pass anything.
_MIN_FRAGMENT = 12

#: An ellipsis, in the several forms a model writes one.
#:
#: ` / ` AND `||` REMOVED 2026-08-18. They are not elision markers, they are
#: separators that occur naturally in scientific text -- `mg / kg`,
#: `male / female`, a table row the model rendered with ` / ` between cells,
#: and any markdown table pipe pair surviving normalise(). Treating them as
#: elisions meant a quote whose two halves sit in different paragraphs and are
#: never printed together came back `elided`, which is one of the two verdicts
#: allowed to make the "As printed" promise.
#:
#: This module's own docstring already said so -- "a quote joining two
#: sentences with ` / ` lands in `stitched` rather than `elided`. That is
#: deliberate" -- and the code did the opposite. The bracketed forms are added
#: because `[...]` is how the convention is actually written in scholarship,
#: and they must be matched WHOLE or the brackets stay glued to the fragments.
_ELLIPSIS = re.compile(r"\[\s*(?:\.\.\.+|…)\s*\]|\.\.\.+|…")

#: A number worth checking. Three alternatives, tried in order:
#:   - a thousands-grouped integer/decimal (12,345 / 12,345.6),
#:   - a leading-dot decimal (.99 -- APA style, dominant in psychology),
#:   - a plain integer or decimal (40.86, 42, -0.21).
#: Each carries an optional leading `-` so a sign-flipped value (a quote of
#: `-0.21` against a paper that prints `0.21`) does not verify. The `(?<![\w.])`
#: lookbehind keeps a page reference safe: in `p.22` the `.` abuts the word
#: char `p`, so no token is emitted -- the same case the old anchored pattern
#: existed to handle, now stated once. The trailing `(?!\d)` stops a match ending
#: mid-number.
_NUMBER = re.compile(
    # `(?<![A-Za-z]\()` keeps the thousands branch off DEGREES OF FREEDOM.
    # `F(2,214)` is not the number 2,214; it is two numbers, and reading it as
    # one made a correctly-copied quote fail to verify.
    r"(?<![\w.])(?<![A-Za-z]\()-?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?!\d)"  # 12,345 / 12,345.6
    r"|(?<![\w.])-?\.\d+(?!\d)"                          # .99 (APA), not p.22
    r"|(?<![\w.])-?\d+(?:\.\d+)?(?!\d)"                  # 40.86, 42, -0.21
)

#: Split a bare integer into thousands groups: 84299 -> 84,299.
_GROUP3 = re.compile(r"(?<=\d)(?=(?:\d{3})+$)")

_DASHES = "−–—‐‑"
_QUOTES = "‘’“”´`"

#: Relational operators, each in the two spellings a paper and a model use.
#: MEASURED: `α ≤ .05` in the paper against `alpha <= .05` in the quote was the
#: single most-repeated unlocatable quote in the archive. NFKC does not touch
#: these -- `≤` has no compatibility decomposition -- so without this fold the
#: two strings can never meet. Folding an operator cannot create or alter a
#: NUMBER, which is the only property the fabrication guarantee rests on.
_OPERATORS = {"≤": "<=", "≥": ">=", "≠": "!=", "≈": "~", "×": "x"}


def _fold_operators(text: str) -> str:
    for glyph, ascii_form in _OPERATORS.items():
        if glyph in text:
            text = text.replace(glyph, ascii_form)
    return text



def normalise(text: str) -> str:
    """Fold away every difference that is typography rather than content.

    A paper prints a minus sign, a model types a hyphen; a PDF emits a
    non-breaking space, a model types a space. Neither difference is a failure
    to quote, and treating them as one is how a verifier manufactures alarm.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _fold_operators(text)
    for ch in _DASHES:
        text = text.replace(ch, "-")
    for ch in _QUOTES:
        text = text.replace(ch, "'")
    text = text.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


#: Debris an extractor leaves where a glyph had no Unicode mapping. `glyphs.py`
#: reports these over 400 papers: `(cid:237)`, `GLYPH<237>`, `/C6`. Whichever
#: extractor the MODEL read may emit them where the one WE search does not, so
#: `means (cid:2)sem` and `means ± sem` are one sentence seen twice.
#: CASE-INSENSITIVE on purpose. `fold_rendering` is normally handed text that
#: `normalise` has already lowercased, but it is a public function and a silent
#: precondition in a public function is a trap: `GLYPH<237>` slipping through
#: unfolded would look exactly like a quote that is not in the paper.
_DEBRIS = re.compile(r"\(cid:\d+\)|glyph<\d+>|/c\d{1,3}\b", re.I)

#: A table cell boundary. Tabs are already single spaces once `normalise` has
#: run; the pipe survives, and it is how BOTH `build_haystack` and the model
#: draw a row -- seldom with the same set of columns.
_CELL_EDGE = re.compile(r"\|+")

#: A word a PDF split at its ligature: `fi nal`, `signi fi cant`, `o ffi ce`.
_LIGATURE_SPLIT = re.compile(r"\b(ffi|ffl|ff|fi|fl)\s+(?=[a-z])")

#: An HTML entity that reached the model still encoded: `p &lt; 0.05`.
_ENTITY = re.compile(r"&(?:[a-z]{2,8}|#x?[0-9a-f]{1,6});")

#: The marks a model puts round a quote to show that it IS one.
_WRAPPERS = "\"'`«»[]"


def _unwrap(text: str) -> str:
    """Drop the quotation marks the MODEL added, which the paper never printed.

    MEASURED: a finding whose `quote` was `'The datasets analyzed ... upon
    reasonable request.'` -- the sentence is verbatim in the paper and the pair
    of apostrophes is the model's punctuation, and they alone made an exact
    copy read as unlocatable.
    """
    out = text.strip()
    while len(out) > 2 and out[0] in _WRAPPERS and out[-1] in _WRAPPERS:
        out = out[1:-1].strip()
    return out


def fold_rendering(text: str) -> str:
    """Reduce text to what it SAYS, discarding how one extractor drew it.

    WHY THIS IS NOT A LOOSENING OF THE QUOTE RULE
    ---------------------------------------------
    The rule is that a quote be one contiguous span of the paper. What was
    failing was almost never contiguity. The model copies from what an
    extraction tool showed it; this module searches a haystack built by
    DIFFERENT extractors that the model never saw. MEASURED over the 637
    supplied quotes in the archive (429 finding quotes, 208 tool-call quotes),
    the 228 that failed divide as:

        cell-separator rendering (`|` against a space)           35
        hyphen spacing (`group -based`, `- 0.01`)                27
        undecoded HTML entities (`&lt;` for `<`)                 19
        ligature splits (`fi nal`, `signi fi cant`)               6
        `(cid:2)` / `GLYPH<n>` debris                             4
        the model's own wrapping quote marks                      1

    Those counts OVERLAP -- a table row can need three of them -- and each is
    the number of quotes that stop being locatable if that one substitution is
    removed. Together they recover 76 of the 228; the remaining 152 are
    transliteration (`α` retyped as `alpha`), text whose spaces the extractor
    lost, and our own haystack gaps.

    So this folds the RENDERER, on both sides, and leaves the rule alone. Every
    substitution is many-to-one on typography and the identity on digits: no
    number can enter, leave, or change value under it. That is the whole of the
    fabrication guarantee, and it is untouched.

    DELIBERATELY ABSENT: a fold that strips ALL whitespace. It recovers a
    further 26 quotes, by making `236 551 727` and `236551727` the same string
    -- that is, by guessing where a digit boundary lies. `glyphs.py` records
    this project's standing answer to exactly that temptation: a guess about a
    digit is the one repair never to make.
    """
    if not text:
        return ""
    if "&" in text and _ENTITY.search(text):
        import html
        # Re-fold operators: unescaping `&le;` yields `≤`, which arrives after
        # `normalise` has already had its turn.
        text = _fold_operators(html.unescape(text))
    text = _DEBRIS.sub(" ", text)
    text = _CELL_EDGE.sub(" ", text)
    text = text.replace("­", "")          # soft hyphen
    text = _LIGATURE_SPLIT.sub(r"\1", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def _sub_with_map(pattern: re.Pattern, s: str, imap: list[int],
                  repl) -> tuple[str, list[int]]:
    """`pattern.sub(repl(m), s)` carrying the offset map along.

    Replacement characters inherit their own map entry where they align with
    the match text (a prefix-preserving substitution like `_LIGATURE_SPLIT`),
    else the entry of the match's first character.
    """
    out: list[str] = []
    omap: list[int] = []
    pos = 0
    for m in pattern.finditer(s):
        out.append(s[pos:m.start()])
        omap.extend(imap[pos:m.start()])
        r = repl(m)
        src = m.group(0)
        out.append(r)
        for j, ch in enumerate(r):
            k = m.start() + j if j < len(src) and src[j] == ch else m.start()
            omap.append(imap[k])
        pos = m.end()
    out.append(s[pos:])
    omap.extend(imap[pos:])
    return "".join(out), omap


def fold_with_offsets(text: str) -> tuple[str, list[int]]:
    """Offset-preserving `fold_rendering(normalise(text))` — the anchor fold.

    `index_map[i]` is the index into the ORIGINAL `text` of the character
    that produced folded character `i`; a folded span `[a, b)` maps back to
    `text[index_map[a] : index_map[b]]` (use `len(text)` when `b` is the end).
    Used for `char_range` in persisted anchors (docs/specs/anchors.md §4).
    Same fold tables as `normalise`/`fold_rendering`; the one divergence is
    per-character NFKC (cross-character compositions are not merged), so
    compare only against needles folded by THIS function.
    """
    if not text:
        return "", []
    chars: list[str] = []
    imap: list[int] = []
    for i, ch in enumerate(text):
        for out in unicodedata.normalize("NFKC", ch):
            for op_ch in _OPERATORS.get(out, out):
                if op_ch in _DASHES:
                    op_ch = "-"
                elif op_ch in _QUOTES:
                    op_ch = "'"
                for low in op_ch.lower():
                    chars.append(low)
                    imap.append(i)
    s = "".join(chars)
    ws = re.compile(r"\s+")
    s, imap = _sub_with_map(ws, s, imap, lambda m: " ")
    # normalise's strip; fold_rendering's steps follow in its exact order.
    if s.startswith(" "):
        s, imap = s[1:], imap[1:]
    if s.endswith(" "):
        s, imap = s[:-1], imap[:-1]
    if "&" in s and _ENTITY.search(s):
        import html
        s, imap = _sub_with_map(
            _ENTITY, s, imap, lambda m: _fold_operators(html.unescape(m.group(0))))
    s, imap = _sub_with_map(_DEBRIS, s, imap, lambda m: " ")
    s, imap = _sub_with_map(_CELL_EDGE, s, imap, lambda m: " ")
    if "­" in s:
        kept = [(c, k) for c, k in zip(s, imap) if c != "­"]
        s = "".join(c for c, _ in kept)
        imap = [k for _, k in kept]
    s, imap = _sub_with_map(_LIGATURE_SPLIT, s, imap, lambda m: m.group(1))
    s, imap = _sub_with_map(re.compile(r"\s*-\s*"), s, imap, lambda m: "-")
    s, imap = _sub_with_map(ws, s, imap, lambda m: " ")
    if s.startswith(" "):
        s, imap = s[1:], imap[1:]
    if s.endswith(" "):
        s, imap = s[:-1], imap[:-1]
    return s, imap


def fold_haystack(hay: dict[str, str]) -> dict[str, str]:
    """`fold_rendering` over every source, under the SAME source names.

    The names are kept so that a quote found only in the folded copy still
    tells the reader "the paper's text" -- a label they can act on. It is the
    same passage; only the drawing of it differed.

    Computed once per haystack by the callers that classify in a loop, because
    folding a 200 kB haystack per quote would cost a paid run real time.
    """
    return {name: fold_rendering(text) for name, text in hay.items()}


def _number_forms(token: str) -> set[str]:
    """The equivalent printed forms of ONE number, any of which the paper may use.

    A value has several legitimate spellings -- `.99` and `0.99`; `4.50` and
    `4.5`; `12,345` and `12345` -- and the paper's choice is not a failure to
    quote. These are DISJUNCTIVE: the number is present if ANY form is found.
    (The old `_numbers` flattened a quote's numbers and their variants into one
    list that `classify` required found CONJUNCTIVELY, so `0.99` in a quote
    demanded the paper also print `.99` -- a self-inflicted `unverified`.)

    A leading sign is preserved and re-applied to every form, so `-0.21` never
    collapses onto `0.21`.
    """
    neg = token[:1] in ("-", "−")
    body = token[1:] if neg else token
    variants = {body}
    if body.startswith("0."):
        variants.add(body[1:])            # 0.99 -> .99
    elif body.startswith("."):
        variants.add("0" + body)          # .99 -> 0.99
    if "," in body:
        variants.add(body.replace(",", ""))   # 12,345 -> 12345
    else:
        # ...and the other direction, which was missing. A quote copying `84299`
        # against a paper that prints `84,299` is a correct quote, and reporting
        # it unverified blames the author for our matcher.
        whole, _, frac = body.partition(".")
        if whole.isdigit() and len(whole) > 3:
            grouped = _GROUP3.sub(",", whole)
            variants.add(grouped + ("." + frac if frac else ""))
    for v in list(variants):
        if "." in v:
            stripped = v.rstrip("0").rstrip(".")
            if stripped:
                variants.add(stripped)    # 4.50 -> 4.5
    # THE MIDDLE-DOT SPELLING IS ONE OF A NUMBER'S PRINTED FORMS. Lancet, BMJ
    # and the journals following their style set `5·077` where most set
    # `5.077`, and this function exists precisely because "the paper's choice is
    # not a failure to quote".
    #
    # MEASURED 2026-08-20: `values._appears_in` delegates here, so the per-cell
    # value join was BLIND on such a paper -- 128 of 202 groups on
    # `10.1111--j.1747-4949.2012.00901.x` carry a middle-dot quote, and it holds
    # the corpus's worst join ratio at 26 joined against 45 unmatched. The
    # middle dot had been taught to four other readers that day and not to this
    # one, which is what makes it a class rather than a bug.
    for v in list(variants):
        if "." in v:
            variants.add(v.replace(".", "·"))
    return {("-" + v if neg else v) for v in variants}


def _number_present(token: str, hay: dict[str, str]) -> bool:
    """Is this number, in any of its equivalent forms, somewhere in the paper?"""
    return any(_locate(form, hay) for form in _number_forms(token))


#: Haystack source names that mean we actually read the PAPER (as opposed to a
#: file shipped beside it). If none of these loaded, a "not in the paper"
#: verdict would be a claim about text we never opened -- see `annotate`. Kept in
#: exact sync with the `add(...)` names in `build_haystack`.
_PRIMARY_SOURCES = frozenset({
    "the paper's text", "a table", "the PDF text layer", "a figure caption",
})


def build_haystack(paper_dir: str | Path) -> dict[str, str]:
    """Every place a quote could legitimately have come from, by name.

    Named rather than concatenated so a located quote can tell the reader WHERE
    to look. Each source is independently guarded: one unreadable supplement
    must not cost us the body text, and a haystack that silently shrinks turns
    into a verifier that silently accuses.
    """
    paper_dir = Path(paper_dir)
    hay: dict[str, str] = {}

    def add(name: str, fn) -> None:
        try:
            value = fn()
        except Exception:
            return
        if value and str(value).strip():
            hay[name] = normalise(str(value))

    from .extraction.jats import find_xml, paper_text

    add("the paper's text", lambda: paper_text(paper_dir))

    xml = find_xml(paper_dir)
    if xml is not None:
        # Tables are searched as their RAW rows as well as their flattened
        # form: a quote is often the literal header row, and the flattened
        # "A | B" composite is not a string that appears anywhere else.
        def _tables() -> str:
            from .extraction.jats import extract_xml_tables
            parts = []
            for t in extract_xml_tables(xml) or []:
                for key in ("label", "caption"):
                    if t.get(key):
                        parts.append(str(t[key]))
                for row in (t.get("header_rows") or []):
                    parts.append(" | ".join(str(c) for c in row))
                for row in (t.get("data") or []):
                    parts.append(" | ".join(str(c) for c in row))
                for note in (t.get("footnotes") or []):
                    # A FOOTNOTE IS A DICT, AND `str()` ON ONE IS PYTHON SOURCE.
                    # `jats._footnotes` returns {"marker": "*", "text": "..."},
                    # so this put the literal string
                    #     {'marker': '', 'text': '*P < 0.01; **P < 0.001.'}
                    # into the haystack -- legend reachable only through the
                    # braces and quote characters wrapped around it.
                    #
                    # WHY THE SIGNIFICANCE LEGEND IS WORTH ITS OWN NOTE: one
                    # asterisk means p<0.01 in this paper and p<0.05 in the
                    # next, so a starred cell settles nothing on its own and the
                    # footnote is the passage that makes it mean anything. A
                    # finding that turns on what a marker DENOTES needs to quote
                    # that sentence, and it could not be quoted cleanly.
                    # Marker and text are joined so `*P < 0.01` reads as one
                    # contiguous span, which is what the one-span quote rule
                    # requires.
                    if isinstance(note, dict):
                        text = " ".join(
                            str(note.get(k) or "").strip()
                            for k in ("marker", "text")).strip()
                    else:
                        text = str(note)
                    if text:
                        parts.append(text)
            return "\n".join(parts)

        add("a table", _tables)

    def _pdf_fitz() -> str:
        import fitz
        from .extraction.jats import find_pdf
        pdf = find_pdf(paper_dir)
        if pdf is None:
            return ""
        # The layer with this PDF's broken symbol-font characters restored
        # (`glyph_repair`), so it agrees with the repaired docling text the
        # analysts quote from: a quoted `F(1, 38) = 3.63` is in it, the
        # layer's own `F(1, 38) 5 3.63` is not.
        from .extraction.glyph_repair import repaired_text_layer
        repaired = repaired_text_layer(pdf)
        if repaired is not None:
            return repaired
        # PyMuPDF rather than pdfplumber here: over this corpus it located 423
        # quote-hits against pdfplumber's 247 on the same documents.
        with fitz.open(str(pdf)) as doc:
            return "\n".join(doc[i].get_text() for i in range(doc.page_count))

    add("the PDF text layer", _pdf_fitz)

    if xml is not None:
        def _captions() -> str:
            import xml.etree.ElementTree as ET
            root = ET.parse(str(xml)).getroot()
            return "\n".join(
                " ".join(fig.itertext())
                for fig in root.iter()
                if fig.tag.rsplit("}", 1)[-1] in ("fig", "graphic"))

        add("a figure caption", _captions)

    def _supplements() -> str:
        from .extraction.supplements_read import extract_supplement
        parts = []
        for path in sorted(paper_dir.glob("*")):
            name = path.name.lower()
            # `linked_data` is here because of the one quote in the whole
            # archive whose numbers we could not find ANYWHERE: a row of
            # `..._linked_data_dataverse_..._CEA_CARS.xlsx`, sitting in the
            # paper's own directory, copied correctly by the model and reported
            # `unverified` because this glob would not open a file whose name
            # said "linked_data" rather than "supplement". A deposited dataset
            # is as much the paper's evidence as an appendix is, and refusing
            # to read it turned OUR filename rule into a claim about a quote.
            if not any(k in name for k in ("supplement", "_si", "linked_data")):
                continue
            if path.suffix.lower() not in (".pdf", ".docx", ".xlsx"):
                continue
            try:
                got = extract_supplement(str(path))
            except Exception:
                continue
            if isinstance(got, dict):
                parts.append(str(got.get("text") or ""))
                for t in (got.get("tables") or []):
                    parts.append(json.dumps(t, default=str))
        return "\n".join(parts)

    add("a supplement", _supplements)
    return hay


def _locate(needle: str, hay: dict[str, str]) -> str | None:
    for name, text in hay.items():
        if needle and _contains_bounded(needle, text):
            return name
    return None


def _contains_bounded(needle: str, text: str) -> bool:
    """`needle in text`, except a number may not match INSIDE a longer number.

    Plain containment reports "n = 42" as present in a paper that only ever
    says "n = 428" -- 42 is a substring of 428. Reproduced: a quote of "n = 42"
    verified as verbatim against "the final sample was n = 428", a false
    all-clear about the quote's own accuracy. So when the needle's edge is a
    digit, the character abutting it in the text may not also be a digit (nor a
    decimal point, which would make 428 read as 4.28's tail). Every occurrence
    is checked; one clean placement is enough, because a paper may legitimately
    print both "n = 42" and "n = 428".
    """
    if not needle:
        return False
    start = 0
    # A needle "begins a number" if it starts with a digit OR with a decimal
    # point followed by a digit (".86"). The latter case is why ".86" used to
    # verify INSIDE "40.86": the left-boundary guard was armed only for a
    # digit-first needle, so a dot-led decimal matched the fractional tail of a
    # larger number and was stamped verbatim -- "As printed" -- at 47x the value.
    left_numstart = needle[0].isdigit() or (
        needle[:1] == "." and needle[1:2].isdigit())
    right_digit = needle[-1].isdigit()
    if not (left_numstart or right_digit):
        return needle in text
    n = len(needle)
    while True:
        i = text.find(needle, start)
        if i == -1:
            return False
        before = text[i - 1] if i > 0 else ""
        after = text[i + n] if i + n < len(text) else ""
        # A digit abutting the match extends the number: "42" inside "428".
        # A decimal point only extends it if a DIGIT follows the point -- the
        # `.` in "50." at a sentence end is punctuation, and rejecting it made
        # a number at the end of a sentence unverifiable. Symmetrically, a `.`
        # before the match extends it only if a digit precedes that `.`; and a
        # thousands comma before it does the same, so "345" is not found inside
        # "12,345".
        after2 = text[i + n + 1] if i + n + 1 < len(text) else ""
        before2 = text[i - 2] if i - 2 >= 0 else ""
        bad_right = right_digit and (
            after.isdigit() or (after == "." and after2.isdigit()))
        bad_left = left_numstart and (
            before.isdigit()
            or (before == "." and before2.isdigit())
            or (before == "," and before2.isdigit()))
        if not bad_left and not bad_right:
            return True
        start = i + 1


def classify(quote: str, hay: dict[str, str],
             folded: dict[str, str] | None = None) -> dict[str, Any]:
    """One quote against one haystack. Returns the fields set on the finding.

    `folded` is `fold_haystack(hay)`, which callers that classify many quotes
    against one paper should compute once and pass in; omitted, it is built
    here, correctly but at the cost of re-folding the paper per quote.

    THE SECOND PASS IS NOT A SECOND STANDARD. Both passes ask the same
    question -- is this one contiguous span of the paper? -- of two drawings of
    the same bytes. See `fold_rendering` for what separates a fold from a
    loosening, and for the fold that was measured, and left out, because it
    would have guessed at a digit boundary.
    """
    if not (quote or "").strip():
        return {"quote_verified": "absent"}

    nq = normalise(quote)
    where = _locate(nq, hay)
    if where:
        return {"quote_verified": "verbatim", "quote_source": where}

    if folded is None:
        folded = fold_haystack(hay)
    fq = fold_rendering(_unwrap(nq))
    where = _locate(fq, folded) if fq else None
    if where:
        return {"quote_verified": "verbatim", "quote_source": where}

    # Elided, tried on the raw text first so that today's verdicts are reached
    # by today's path, then on the folded text. Fragments are re-cut from `fq`
    # rather than reused, because the fold can join a fragment that a stray
    # ligature space had split.
    # EVERY NUMBER IN THE QUOTE MUST BE IN THE PAPER BEFORE `elided` IS
    # ALLOWED. Fragments shorter than `_MIN_FRAGMENT` are dropped below as
    # non-probative, which is right -- "0.05" appears in every paper, so
    # requiring it found would pass anything. But they were dropped BEFORE
    # `all(found)` was evaluated, so they were never searched for at all, and
    # the verdict asserted that the whole quoted string is in the paper having
    # checked only the long parts. Numbers are exactly the content that falls
    # under 12 characters, and numbers are the entire point of a forensic
    # quote: a quote of
    #     "The control group showed a marked improvement ... 99.9 ... the
    #      treatment group is mentioned again"
    # against a paper containing no 99.9 anywhere came back `elided`, and the
    # fabricated value was displayed under "As printed" with a link offering to
    # find it in the PDF.
    #
    # The precondition is the same test the `stitched` branch below already
    # applies, hoisted: a number is either present or the quote is not "as
    # printed". Failing it falls through, and `stitched` cannot fire either
    # because it runs the identical check -- so the quote lands in
    # `unverified`, which is the honest verdict.
    _numbers_all_present = all(_number_present(n, hay) for n in _NUMBER.findall(nq))
    for needle, haystack in ((nq, hay), (fq, folded)):
        fragments = [f.strip() for f in _ELLIPSIS.split(needle)
                     if len(f.strip()) >= _MIN_FRAGMENT]
        if len(fragments) > 1 and _numbers_all_present:
            found = [_locate(f, haystack) for f in fragments]
            if all(found):
                return {"quote_verified": "elided",
                        "quote_source": found[0] or "the paper"}

    nums = _NUMBER.findall(nq)
    if nums:
        missing = [n for n in nums if not _number_present(n, hay)]
        if not missing:
            return {
                "quote_verified": "stitched",
                "quote_source": "assembled from values in the paper",
                "quote_problem": (
                    "Every number here appears in the paper, but this exact "
                    "sentence does not -- it was composed by the review, so "
                    "searching the PDF for it will find nothing."
                ),
            }

    return {
        "quote_verified": "unverified",
        "quote_problem": (
            "WE could not locate this text in what we read. That is a "
            "statement about this search, not about the paper: it happens when "
            "the paper spells a number in words, when the value lives in a "
            "figure we can only see as an image, or when the quote is a table "
            "header rendered differently by each extractor. Do not read it as "
            "evidence that the authors did not write this."
        ),
    }


def annotate(findings: list[dict], paper_dir: str | Path) -> list[dict]:
    """Stamp every finding in place. Idempotent, and never raises.

    Idempotent because `write_review_outputs` re-runs the annotators over
    results assembled by paths that never went through the analysis loop, and
    an unannotated findings.json is worse than a redundant pass.
    """
    # STRIP FIRST, UNCONDITIONALLY. The schema must declare these fields (the
    # finding items set additionalProperties:false), so the MODEL can emit
    # them -- and an early return that skips the strip lets a model-written
    # `quote_verified: "verbatim"` survive and render as "As printed ... found
    # in the paper's text" on a paper nobody opened. Verified by attempting
    # exactly that forgery: before this reordering, it worked.
    for finding in findings:
        if isinstance(finding, dict):
            for stale in ("quote_verified", "quote_source", "quote_problem"):
                finding.pop(stale, None)

    try:
        hay = build_haystack(paper_dir)
    except Exception:
        hay = {}
    if not hay:
        # No haystack is not a verdict on any quote. Say nothing rather than
        # stamp 505 findings "unverified" because we could not open the paper.
        return findings

    # Did we actually read the PAPER, or only something beside it? Each source
    # is guarded independently, so a scanned PDF-only paper whose body/XML/PDF
    # text all fail -- but which ships a machine-readable supplement -- yields a
    # haystack of the supplement ALONE. Stamping a finding `unverified` or
    # `stitched` against that says "this is not in the paper / searching the PDF
    # will find nothing" about a paper we never opened: the house failure
    # pattern, our extraction gap in the grammar of a claim about the paper.
    read_the_paper = bool(hay.keys() & _PRIMARY_SOURCES)
    folded = fold_haystack(hay)

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        result = classify(finding.get("quote") or "", hay, folded)
        # A POSITIVE location (verbatim/elided) is honest to report even from a
        # supplement -- it names where we DID find the text. A NEGATIVE verdict
        # when we never read the paper is withheld: the finding stays unstamped
        # and renders as the neutral "Quoted by the review", making no claim.
        if not read_the_paper and result.get("quote_verified") in ("stitched", "unverified"):
            continue
        finding.update(result)
    return findings


def verify_ledger(ledger: list[dict], hay: dict[str, str]) -> dict:
    """Check each tool call's `source_quote` against the paper. In place.

    Greg, 2026-08-09: every tool should "report the exact quote/context of the
    paper from which given values were extracted". The tool surface records the
    claim; THIS decides whether the claim is true, because a self-assessment
    written by the party being checked is not a check -- the same rule that
    governs `quote_verified` on findings and `reproduction_valid` on commands.

    Adds `source_quote_verified` (and `source_quote_source` when located) to
    every entry that carried a quote, and returns a coverage summary.

    THE SUMMARY IS THE POINT, as much as the per-call verdict. "12 of 140 calls
    said where their numbers came from" is a fact about this review that a
    reader needs and that no individual entry reveals. Coverage that is never
    counted is coverage nobody notices is missing.

    Silent on an EMPTY haystack: if the paper could not be read, stamping every
    call `unverified` would report our failure as a fact about their work.

    THE DENOMINATOR IS `eligible`, NOT `calls`. A ledger is mostly extraction --
    `extract_xml`, `get_table`, `Read` -- and those tools have no reported value
    to source, so they were deliberately never given the argument. Scoring them
    as unsourced would report a coverage failure that is really a design
    decision, and would dilute the number that matters until nobody watches it.
    An unrecognised tool that DID supply a quote still counts, so a renamed or
    newly added check cannot quietly fall out of the denominator.
    """
    eligible_tools = _tools_taking_a_source_quote()
    folded = fold_haystack(hay) if hay else {}
    summary = {
        "calls": len(ledger),
        "eligible": 0,
        "with_quote": 0,
        "verbatim": 0,
        "elided": 0,
        "stitched": 0,
        "unverified": 0,
        "checked": bool(hay),
    }
    for entry in ledger:
        if not isinstance(entry, dict):
            continue
        # Strip any verdict the model may have emitted before deciding one.
        entry.pop("source_quote_verified", None)
        quote = (entry.get("input") or {}).get("source_quote")
        has_quote = isinstance(quote, str) and bool(quote.strip())
        if _short_tool_name(entry) in eligible_tools or has_quote:
            summary["eligible"] += 1
        if not has_quote:
            continue
        summary["with_quote"] += 1
        if not hay:
            continue
        verdict = classify(quote, hay, folded)
        entry["source_quote_verified"] = verdict["quote_verified"]
        if verdict.get("quote_source"):
            entry["source_quote_source"] = verdict["quote_source"]
        if verdict["quote_verified"] in summary:
            summary[verdict["quote_verified"]] += 1
    summary["without_quote"] = summary["eligible"] - summary["with_quote"]
    return summary


def _short_tool_name(entry: dict) -> str:
    """The registry's name for the tool this ledger entry called.

    Ledger entries record the MCP name (`mcp__forensic_metascience__grim_check`)
    alongside a pre-stripped `tool_short`; older ledgers and hand-built ones have
    only `tool`. Strip here rather than depend on the richer field existing.
    """
    short = entry.get("tool_short")
    if isinstance(short, str) and short:
        return short
    name = str(entry.get("tool") or "")
    return name.rpartition("__")[2] or name


def _tools_taking_a_source_quote() -> frozenset[str]:
    """Registry names of the tools that accept `source_quote`.

    Read from the registry rather than listed here, so adding a check or
    removing the argument from one cannot leave this counting the wrong
    denominator. Import is local: `registry` is a heavy module and `quotes` is
    imported by the annotation path on every run.
    """
    try:
        from . import registry as _registry
    except Exception:  # noqa: BLE001 -- coverage must never break a paid run
        return frozenset()
    return frozenset(
        spec.name for spec in _registry.SPECS
        if any(p.name == "source_quote" for p in spec.params)
    )
