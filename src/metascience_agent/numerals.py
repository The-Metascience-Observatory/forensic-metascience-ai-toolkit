"""Every number the paper printed, and what each one turned out to be.

Greg, 2026-08-18:

    "instead of looking for these patterns, I think that target of the search
     for values ought to be ALL NUMERIC VALUES. And only after a numeric value
     is indexed, the model looks at the context in order to classify it as,
     e.g., a mean."

WHY THE PATTERN-FIRST APPROACH HAD TO GO. `completeness.BODY_PATTERNS` is an
enumerator built out of shapes -- `4.17 (SD = 1.19)`, `t(38) = 7.21`,
`p = .011`. A shape it has not seen is not merely unclassified, it is INVISIBLE,
and the coverage number it feeds looks fine either way. Two such shapes were
found on one afternoon by checking exhaustiveness against a real paper:

    `M = 4.64, SD = 1.50`   psychology's convention; 37 pairs in the fraud
                            ground-truth paper, and the parenthesised pattern
                            matched ZERO of them
    `65.2 ± 1.17`           the clinical convention; 128 of 305 corpus papers
                            (42%), 5,942 occurrences, none indexed

Finding two in one afternoon is the argument. There is no reason to believe
there is not a third, and no way to know from the inside.

THE SAME FIX AS EVERYWHERE ELSE IN THIS CODEBASE, one layer up: patterns
LOCATE, evidence JUDGES. A scan for `\\d` cannot be silently incomplete -- there
is nothing for a convention to hide behind. So the floor becomes every numeric
token, and what a token IS becomes a separate, visible question.

THE FAILURE MODE INVERTS, which is the point. An unrecognised convention used
to be silence; here it is a row marked `unclassified`, which a reader and a
metric can both see.

ORDER MATTERS, and it is Greg's constraint: indexing needs no anatomy, but
CLASSIFYING does. Asking whether `6.58` is a mean is not answerable until the
paper's variables are declared -- otherwise the model is deriving variable
characteristics in a vacuum. So: index (here, deterministic, no model) ->
statistical anatomy (model) -> classify the residue against it (model).

WHAT THIS DOES NOT DO. It does not decide that a number is a statistic. The
cheap rules below only dispose of the numbers that are demonstrably NOT
statistics -- a citation year, a figure number, a scale anchor -- and every one
of those is a POSITIVE identification with its evidence recorded, never a
guess. Everything else is handed on as `unclassified`, which is the honest
state for a number nobody has looked at yet.
"""

from __future__ import annotations

import re

__all__ = ["NUMERAL", "index", "tally", "CLASSES"]

#: Every numeric literal, as printed. Thousands groups and a leading sign are
#: part of the token; a leading dot is too, because `.52` is how psychology
#: prints a correlation and dropping the dot would change the number.
#:
#: Bounded on both sides against word characters so `p22`, `F1` and `COVID-19`
#: do not yield numbers, and against `.` so `6.58` is one token rather than two.
#: The trailing guard is `(?!\w)(?!\.\d)`, NOT `(?![\w.])`. The stricter form
#: keeps `6.58` from splitting -- but it also drops any number ending a
#: sentence, so `Age was 65.2 ± 1.17.` yielded only `65.2` and the dispersion
#: vanished. Blocking a following digit-after-dot does the first job without
#: the second.
#: A TRAILING LETTER IS A UNIT, NOT A DISQUALIFIER. `(?!\w)` made `542ms`,
#: `24h` and `250mg` invisible -- 293 occurrences in 55 of 305 corpus papers,
#: with no residue row to show for them, which falsified "exhaustive by
#: construction" outright. The LEADING guard is what keeps `p22`, `F1` and
#: `NCT02737566` out, and it does that job on its own.
#:
#: Scientific notation is its own alternative and must come first, or `1.2e-4`
#: tokenises as `1.2` and the exponent is lost.
#: A MIDDLE DOT IS A DECIMAL MARK HERE TOO. This is the FOURTH reader of that
#: convention, and it was the one still getting it wrong after the other three
#: were fixed: `-5·077 (95% CI -7·716 to -2·437)` tokenised as
#: `-5, 077, 95, -7, 716, -2, 437` -- seven tokens where the paper printed
#: three numbers, in the module whose docstring promises "exhaustive by
#: construction".
#:
#: WORSE THAN A LOCAL BUG, because `agreement._numbers` delegates here. Two
#: independent readings of a Lancet-style page shredded IDENTICALLY and the
#: comparison reported perfect agreement on garbage -- the sign-blindness fix
#: had re-created the sign-blindness SHAPE for a different convention. A shared
#: lexer removes divergence between readers and removes their independence with
#: it; that is the trade, and it is only safe if the lexer is right.
#: THE SIGN CLASS INCLUDES U+2212, AND THE THOUSANDS BRANCH MAY NOT SWALLOW A
#: LONGER RUN. Two defects found 2026-08-20 by a design review that RAN this
#: function rather than reading it, both of them recurrences of shapes already
#: fixed elsewhere in the same file:
#:
#:   `tokens("effect was −1.6")`  ->  ['1.6']        the sign, dropped
#:   `tokens("OR 0,5561")`         ->  ['0,556']      a literal nobody printed
#:
#: The first is the sign-blindness this module was fixed for hours earlier, in
#: the ASCII hyphen: `agreement._numbers` delegates here, so two readings that
#: differ only in a U+2212 sign compared as AGREEING. `celltypes` measured 2,850
#: U+2212 cells across the wider corpus, so this is a live shape, not a
#: hypothetical.
#:
#: The second is worse than dropping a number: it INVENTS one. `0,5561` in a
#: decimal-comma document is one number; the thousands branch matched `0,556`
#: and left the `1` behind. We cannot know the document's convention from the
#: token, but we can decline to emit a literal the paper never printed -- so the
#: branch now requires that the last group not be followed by another digit,
#: and `0,5561` falls through to two plain integers instead of one fiction.
NUMERAL = re.compile(
    r"(?<![\w.·])[-+−]?\d+(?:[.·]\d+)?[eE][-+−]?\d+(?![\w.·])"
    r"|(?<![\w.·])[-+−]?\d{1,3}(?:,\d{3})+(?:[.·]\d+)?(?!\d)(?![.·]\d)"
    r"|(?<![\w.·])[-+−]?\d*[.·]\d+(?![.·]\d)"
    r"|(?<![\w.·])[-+−]?\d+(?![.·]\d)"
)

#: A hyphen glued to a word makes what follows part of that word, not a number:
#: `COVID-19` yielded `19` because the lookbehind saw only the hyphen. Checked
#: in `index` rather than in the pattern, because excluding a preceding `-`
#: outright would also lose the upper bound of an interval like `1.08-1.9`.
#: A LETTER before the hyphen, never a digit: `COVID-19` is one word, while
#: `1.08-1.9` is an interval whose upper bound is a number we need.
_WORD_HYPHEN = re.compile(r"[^\W\d]-$")

#: What a number can be found to be. `unclassified` is the DEFAULT and is not a
#: failure -- it is the state of a number nobody has judged yet, and the whole
#: reason for indexing before classifying.
#:
#: EVERY MEMBER IS A CLASSIFICATION AND NONE IS A SUPPRESSION. A classified
#: numeral stays in `n_total` and moves bucket; nothing here removes a row. That
#: is the distinction measured at +206 rows in CLAUDE.md 8f, and it is why a
#: consumer that wants to exclude a class must say which classes it excludes
#: (`coverage.NOT_A_STATISTIC_CLASSES`) rather than shrinking the floor.
CLASSES = ("statistic", "table_cell", "citation_year", "citation_page",
           "citation_marker", "ordinal", "scale_anchor", "placeholder",
           "phase_label", "unclassified")

#: REWRITTEN 2026-08-18 after an adversarial review found every rule below
#: removing REAL reported statistics. On a 12-paper corpus sample, 582 of 689
#: "factorial" classifications (84%) were statistics -- `4.17 (SD = 1.19)` lost
#: its mean, `96 of 104 (92.3%)` lost its denominator, and a stroke trial's
#: primary effect estimate `MW=0.71 (95% CI ...)` was filed as design notation.
#:
#: That is worse than the silence this module was built to replace, because a
#: removed number carries a confident recorded reason and `classify_with`
#: refuses to touch a row that is already classified -- so a matching
#: BODY_PATTERN cannot repair it. The module's own docstring promised these
#: rules "only remove what is demonstrably NOT a statistic" and they did not.
#:
#: THE RULE FOR THE RULES, now enforced by the shapes below: fire only on
#: evidence that admits no other reading. `unclassified` is cheap -- the model
#: looks at it -- and a false removal is permanent, because nobody looks again.

#: A four-digit year inside a citation. The bracket alone is NOT enough:
#: "(1989 patients)" and "arms of 250, 2013, and 210" are sample sizes. An
#: author-like token must precede, or a bracketed year must be followed by
#: something that ends the citation rather than continuing a sentence.
#: A MULTI-YEAR CITATION IS STILL A CITATION. `(Kawamata, 1997, 1998;
#: Schaebitz, 1999)` classified only its FIRST year: the second sees
#: `Kawamata, 1997, ` behind it, and an author token must sit immediately
#: before, so the chain broke at the comma. The trailing group below walks back
#: over any run of years already listed.
#:
#: Kept narrow on purpose, per this module's rule for its rules. Only a
#: four-digit 19xx/20xx token is eligible at the call site, and the walk-back
#: accepts ONLY complete years (with an optional `1997a` suffix) separated by a
#: comma or semicolon. "arms of 250, 2013, and 210" is still safe -- `of` is not
#: one of the connectives the author alternation allows, so no author token
#: matches and the whole pattern fails, which is the reading that keeps a
#: sample size a sample size.
#: THE COMMA CONNECTIVE NEEDS NO SPACE BEFORE IT, and that is not a detail:
#: it is one house style against another. `Smith et al. [2022]` matched;
#: `Smith et al., [2016]` did NOT, because the alternation required whitespace
#: ahead of every connective and there is none between `al.` and its comma.
#: MEASURED over the 12-paper corpus: 697 numerals sit inside an in-text
#: citation marker and 577 of them (83%) were reaching the floor as
#: `unclassified` -- indistinguishable, to any consumer, from a number the
#: paper reported. On one paper 39 of the first 40 rows the viewer showed under
#: "Not yet judged" were citation years.
#:
#: LOOSENING THIS PATTERN IS THE DANGEROUS DIRECTION, and it is worth saying
#: which way. A numeral wrongly called a citation year LEAVES the checkable
#: floor: a permanent, invisible loss of coverage that no later pass recovers.
#: So the change was tested against a false-removal battery before it shipped
#: -- `(1989 patients)`, `arms of 250, 2013, and 210`, `F (1,78)`, `t (84)`,
#: `we enrolled 2013 participants`, `collected in 2013,` -- all of which must
#: still fail, and do.
_CITATION = re.compile(
    r"[A-Z][A-Za-z'\u2019-]+"
    r"(?:(?:\s+(?:et\s+al\.?|and|&)|\s*,)\s*[A-Z]?[A-Za-z'\u2019-]*)*"
    r"\s*[,(\[]\s*(?:\d{4}[a-z]?\s*[,;]\s*)*$"
)
#: ...and what follows a citation year is a closing bracket or a page/section
#: reference, never a noun. `(1989 patients)` fails this; `(Wood, 1989)` passes.
#: NOT `(Wood 1989)` -- an author with NO comma before the year does not match
#: `_CITATION` at all, which was asserted here and is false on this code. It
#: was checked, 2026-08-29, by running the pattern.
#: A SINGLE disambiguating letter may sit between the year and the delimiter --
#: `(Smith, 1997a, 1997b)`. Exactly one, and it must be followed immediately by
#: the delimiter: `1989 patients` still fails, because `p` is not followed by a
#: closing bracket or comma. Without this the FIRST year of every lettered
#: citation was unclassified.
_CITATION_AFTER = re.compile(
    r"^[a-z]?\s*[)\]\u2019';,]|^\s*(?:p{1,2}\.|:)\s*\d")

#: THE BRACKET-INSIDE-A-BRACKET CITATION, which needs no author at all.
#: A publisher's `<xref ref-type="bibr">` renders as `[2016]`, and the paper's
#: own parenthesis wraps it: `([2016])`, `([2010], [2015])`, `[CADCA], [2018]`,
#: `Kaner's ([2014])`. MEASURED on ajcp.70049: 9 of the 24 sentences H2 could not
#: cover are blocked by exactly this shape, every one of them `unclassified`.
#:
#: A YEAR WRITTEN THIS WAY IS NEVER A MEASUREMENT. The rule requires the token to
#: sit alone inside `[...]` and that bracket to be opened by a `(`, `[`, `,` or
#: `;` -- so `(1989 patients)` (no bracket), `arms of 250, 2013, and 210` (no
#: bracket), and `[95% CI 1990, 2010]` (the `[` does not immediately precede the
#: token) all still fail, as the false-removal battery asserts.
_BRACKETED_YEAR_BEFORE = re.compile(r"[(\[,;]\s*\[\s*$")
_BRACKETED_YEAR_AFTER = re.compile(r"^[a-z]?\s*\]")

#: `Experiment 2`, `Fig. 1`, `Table 3`. The ordinal word must IMMEDIATELY
#: precede the number -- no intervening words -- and the number must be small,
#: because a document has few parts and `Table 4128` is not one of them.
#:
#: `eTable`, `eFigure` and `Supplement` added 2026-09-07: JAMA's supplement
#: cross-references are the largest single blocker of statistic-bearing
#: sentences on jamanetworkopen.2023.37679 -- 24 blocking numerals, and `Results
#: from sensitivity analyses were also significant (eTable 3 in Supplement 1).`
#: holds no other number at all. Same shape as `Table 3`, same guard.
_ORDINAL = re.compile(
    r"\b(?:experiments?|stud(?:y|ies)|e?fig(?:ure)?s?\.?|e?tables?|sections?|"
    r"appendix|appendices|e?supplements?|panels?|steps?|phases?)\s*$", re.I)
_ORDINAL_MAX = 20

#: `p. 185`, `pp. 12-14` -- the LOCATOR inside a citation. `_CITATION_AFTER`
#: already uses this shape to confirm a year; the page itself was reaching the
#: floor as `unclassified`, indistinguishable from a number the paper reported.
_PAGE_BEFORE = re.compile(r"(?<![A-Za-z])pp?\.\s*(?:\d+\s*[-–]\s*)?$")

#: A JAMA-style superscript reference run: `deaths.18,19,20`. THE DANGEROUS ONE,
#: and it is deliberately the narrowest rule in this module, because a thousands
#: separator has the same shape and `46,000` is a real statistic.
#:
#: THREE OR MORE numbers, so a single comma can never match; NO whitespace, so
#: `250, 2013, and 210` cannot; the run must be glued to the end of a word or a
#: full stop, so a free-standing list cannot; and NO group after the first may be
#: exactly three digits, which is what a thousands group is. `104,105,106` is a
#: real citation run and is refused by that last rule -- the fail-closed
#: direction, on purpose.
_SUPERSCRIPT_RUN = re.compile(r"(?<=[A-Za-z.)])(\d{1,3})((?:,\d{1,3}){2,})(?![\d,])")

#: The placeholder OUR OWN converter writes where a table's grid was lifted out
#: of the running text: `[Table 1: caption -- 75 rows x 5 cols; see tables]`.
#: Those digits are not the paper's, and they were entering the sentence
#: denominator as numerals nobody had covered (6 of them on
#: jamanetworkopen.2023.37679). One definition, imported by `bundle`.
TABLE_PLACEHOLDER = re.compile(
    r"^\[(?P<name>Table[^:\]]*|TABLE[^:\]]*): (?P<caption>.*?) [-—] "
    r"(?P<shape>[^;\]]*); see tables\]$", re.M)

#: `Experiments 1 and 2`. The coordinator must directly follow a NUMBER that an
#: ordinal word introduced -- `[-\d,\s]*` plus a bare comma matched "In Study
#: 1, 45 participants" and removed the sample size.
_COORDINATED = re.compile(
    r"\b(?:experiments?|stud(?:y|ies)|figs?\.?|figures?|tables?|sections?)\s+"
    r"\d{1,2}(?:\s*(?:,|and|&)\s*\d{1,2})*\s*(?:and|&|through|to|-)\s*$", re.I)

#: `2 x 2`, `2(load) x 2(mood)`. The MULTIPLICATION must be present and adjacent
#: to a digit on both sides. The previous form fired on a bare `(` after any
#: number, and on any word ending in x -- "approx 30" lost its 30.
_FACTORIAL_BEFORE = re.compile(r"(?<![A-Za-z])[x\u00d7]\s*$")
_FACTORIAL_AFTER = re.compile(r"^\s*(?:\([^)]{0,40}\)\s*)?[x\u00d7]\s*\d")

#: `1 = sad, 9 = happy` -- a scale's endpoints. The word after `=` must not be a
#: unit or a noun the number quantifies, so a following `patients`/`mg` is not
#: an anchor. Kept narrow: an anchor is a LABEL, and labels are adjectives or
#: short descriptors, not counted things.
_ANCHOR_AFTER = re.compile(r"^\s*=\s*[A-Za-z]")
_ANCHOR_NOT = re.compile(
    r"^\s*=\s*(?:patients?|participants?|subjects?|cases?|controls?|"
    r"m[gl]|kg|ml|mm|cm|s|ms|h|hr|hours?|days?|weeks?|years?|%)\b", re.I)


#: A markdown table row serialised into the body text. docling emits tables as
#: pipe rows inside the prose, so a paper's tabulated results arrive twice: once
#: in `tables` and once as text.
#:
#: MEASURED over the 211-paper Zotero corpus: 26,163 of 98,463 unclassified
#: tokens (27%) sit on such a line, and they are REAL statistics -- confidence
#: intervals, p-values, medians with IQR. They were the single largest
#: identifiable class in the residue.
#:
#: `table_cell` IS NOT A REMOVAL. It does not say "not a statistic"; it says
#: this number belongs to the TABLE pass, which types cells properly and knows
#: their row and column. Calling it prose would have the enumerator competing
#: with the typer over the same value and reporting the loser as missing.
_PIPE_ROW_MIN = 2


def _line_around(text: str, start: int) -> str:
    lo = text.rfind("\n", 0, start) + 1
    hi = text.find("\n", start)
    return text[lo:hi if hi >= 0 else min(len(text), start + 200)]


def _class_of(text: str, start: int, end: int) -> tuple[str, str | None]:
    """What this token is, from the characters around it. `(class, evidence)`.

    Every non-`unclassified` answer carries the evidence that produced it, so a
    reader can see WHY a number was set aside rather than being told that it
    was. A rule that cannot show its reason is a rule nobody can audit.
    """
    before = text[max(0, start - 60):start]
    after = text[end:end + 30]
    token = text[start:end]

    def _small_int() -> bool:
        try:
            return float(token) <= _ORDINAL_MAX and float(token) == int(float(token))
        except ValueError:
            return False

    line = _line_around(text, start)
    # OUR OWN TEXT, FIRST. The placeholder line is written by the converter where
    # a table's grid was lifted out of the running text, so its digits were never
    # the paper's; every rule below would be judging our sentence, not theirs.
    if TABLE_PLACEHOLDER.search(line.strip()):
        return "placeholder", "inside the converter's own table placeholder line"
    if line.count("|") >= _PIPE_ROW_MIN:
        return "table_cell", "on a serialised table row; the table pass owns it"
    if _PAGE_BEFORE.search(before):
        return "citation_page", "a page number inside a citation"
    if _superscript_run_span(text, start, end):
        return "citation_marker", "one of a run of superscript reference markers"
    if _ANCHOR_AFTER.match(after) and not _ANCHOR_NOT.match(after):
        return "scale_anchor", f"followed by '{after.strip()[:18]}'"
    if _ORDINAL.search(before) and _small_int():
        return "ordinal", f"follows '{before.strip().split()[-1][:18]}'"
    if _COORDINATED.search(before) and _small_int():
        return "ordinal", "a further item in a list of document ordinals"
    if _FACTORIAL_BEFORE.search(before) or _FACTORIAL_AFTER.match(after):
        return "ordinal", "factorial design notation, not a measurement"
    if (len(token) == 4 and token[:2] in ("19", "20")
            and _CITATION.search(before) and _CITATION_AFTER.match(after)):
        return "citation_year", "a year inside a citation"
    if (len(token) == 4 and token[:2] in ("19", "20")
            and _BRACKETED_YEAR_BEFORE.search(before)
            and _BRACKETED_YEAR_AFTER.match(after)):
        return "citation_year", "a year alone inside a citation's own brackets"
    return "unclassified", None


def _superscript_run_span(text: str, start: int, end: int) -> bool:
    """Does the token at [start, end) sit inside a superscript reference run?

    The run is found in the surrounding line and its own span is checked, so a
    token that merely LOOKS like part of one (`46,000` beside a run) is not
    swept in. A leading-dot decimal (`deaths.18,19` tokenises `.18`) is handled
    by testing the digit position as well as the token's own start.
    """
    lo = text.rfind("\n", 0, start) + 1
    window = text[lo:end + 24]
    for m in _SUPERSCRIPT_RUN.finditer(window):
        # No group after the first may be exactly three digits: that is what a
        # thousands separator looks like, and `46,000,000` is a real number.
        if any(len(g) == 3 for g in m.group(2).lstrip(",").split(",")):
            continue
        a, b = lo + m.start(), lo + m.end()
        if a <= start < b or a <= start + 1 < b:
            return True
    return False


def tokens(text: str, upto: int | None = None):
    """Every numeric token in `text`, with the word-hyphen guard applied.

    ONE READER, because the pattern and the guard belong together. `NUMERAL`
    deliberately allows a leading `-`, so that an interval's lower bound and a
    genuinely negative value both survive; `_WORD_HYPHEN` is what stops
    `COVID-19` from yielding -19. A caller that takes the pattern and forgets
    the guard gets a negative number out of a disease name, and a caller that
    writes its own pattern gets something subtly different -- which is how
    `agreement` came to compare two readings of a page using a regex with NO
    sign at all, and so reported `-1.6` and `1.6` as agreeing.
    """
    limit = len(text or "") if upto is None else upto
    for m in NUMERAL.finditer(text or ""):
        if m.start() >= limit:
            break
        if _WORD_HYPHEN.search((text or "")[max(0, m.start() - 2):m.start()]):
            continue          # `COVID-19`: part of a word, not a number
        yield m


#: A digit run directly preceded by a LETTER, which `NUMERAL`'s `(?<![\w.·])`
#: lookbehind refuses. That lookbehind is right and must stay: without it `p53`,
#: `IL6`, `COVID19` and `Study2` all become numbers. But it is a SHAPE RULE
#: applied silently, in the one module whose contract is that its count "cannot
#: be silently incomplete" -- so what it removes is counted here rather than
#: vanishing.
_LETTER_ATTACHED = re.compile(r"(?<=[^\W\d])[-+−]?\d+(?:[.·]\d+)?")


def suppressed(text: str, upto: int | None = None) -> list[dict]:
    """Digit runs the enumerator refuses because a letter directly precedes them.

    NOT ADDED TO `n_total`, and that is the point. Some of these are genuinely
    parts of names -- `p53` is a gene, not a 53 -- so promoting them would put
    invented numbers in the denominator, which is worse than omitting real ones.
    Counting them instead converts a silent incompleteness into a stated one,
    which is the same move `unclassified` makes for numbers nobody has judged.

    MEASURED on Stern 2014's tables (2,649 cells): 654 occurrences, of which
    470 are a test statistic's degrees of freedom -- `F6,51=6.819` yields `51`
    and `6.819` but not the `6`, and `t15 = 2.3` yields only `2.3`, losing the
    df entirely. For a toolkit whose checks turn on df that is the most costly
    place for the enumeration to be quietly short.
    """
    out: list[dict] = []
    limit = len(text or "") if upto is None else upto
    for m in _LETTER_ATTACHED.finditer(text or ""):
        if m.start() >= limit:
            break
        out.append({
            "printed": m.group(0),
            "offset": m.start(),
            "preceded_by": (text or "")[max(0, m.start() - 1):m.start()],
            "context": " ".join(
                (text or "")[max(0, m.start() - 30):m.end() + 20].split()),
        })
    return out


def index(text: str, upto: int | None = None,
          tables_available: bool = True) -> list[dict]:
    """Every numeric token in `text`, in order, one row each.

    EXHAUSTIVE BY CONSTRUCTION, which is the entire point: nothing is filtered
    out here, so nothing can be silently absent. `upto` bounds the scan at the
    reference boundary, because a bibliography's numbers are not the paper's.

    `tables_available` must be False when the extractor produced no tables:
    `table_cell` asserts that another pass owns the number, and that assertion
    is false if there is no such pass.
    """
    out: list[dict] = []
    for m in tokens(text, upto):
        kind, why = _class_of(text, m.start(), m.end())
        if kind == "table_cell" and not tables_available:
            # ROUTING INTO A VOID IS A SILENT LOSS. `table_cell` means "the
            # table pass owns this" -- and if the extractor produced no tables,
            # no pass owns it. MEASURED on the Zotero corpus this is 5 papers
            # and 84 tokens, small enough to be tempting to ignore and exactly
            # the shape of defect this repository keeps finding: a number
            # handed to a consumer that does not exist.
            kind, why = "unclassified", None
        out.append({
            "id": f"num:{m.start()}",
            "printed": m.group(0),
            "offset": m.start(),
            "end": m.end(),
            "class": kind,
            "why": why,
            "context": " ".join(
                text[max(0, m.start() - 50):m.end() + 30].split()),
        })
    return out


def channel(row: dict) -> str:
    """`table` when the table pass owns this numeral, `prose` otherwise.

    ONE RULE FOR EVERY PRINTER. A body token inside a docling pipe row is
    classed `table_cell` by `index`; a cell enumerated by `index_table_cells`
    is classed `table_cell` too. Both are the table channel. Keying on the
    class rather than on `offset is None` means a converter that inlines its
    tables and one that does not report the same split for the same paper.
    """
    return "table" if (row.get("class") or "") == "table_cell" else "prose"


def source_key(row: dict) -> str:
    """`<source>_<channel>`: `article_prose`, `article_table`, `supplement_table`.

    This is the key `tally.by_source` reports under, and the split every
    printer of a floor total must show beside it (Greg, 2026-09-06: "table
    values and prose values should be combined floors, but whenever you give
    the total give the breakdown by source").
    """
    return f"{row.get('source') or 'article'}_{channel(row)}"


def table_span(text: str, cells: list[dict]) -> tuple[int, int] | None:
    """Where an inlined pipe table sits in `text`, by its first and last cell
    strings; None when the table is not inlined.

    THE ONE RULE THAT DECIDES WHETHER A TABLE'S CELLS ARE ALREADY IN THE FLOOR.
    Both floors -- the scaffold's (`scaffold.document.build`) and the
    register's (`values.build_from_paper`) -- ask this before enumerating a
    table's cells directly, so a converter that inlines tables (docling's pipe
    rows) cannot count a cell twice and one that keeps tables in their own
    elements (publisher XML, HTML) cannot leave them out. Moved here from the
    scaffold so there is one definition, not two that drift.

    WHITESPACE-INSENSITIVE, because the text has been repaired since the cells
    were read: the walker's cell says `23.0 ( ± 0.40)` and the repaired body
    says `23.0 (±0.40)`. Comparing them literally found no table at all, so
    every table numeral fell out of the accounting and the table had no page.
    """
    rows = [c.get("raw") for c in cells if str(c.get("raw") or "").strip()]
    if not rows:
        return None

    def _squash(t: str) -> str:
        return re.sub(r"\s+", "", t)
    first, last = _squash(str(rows[0])), _squash(str(rows[-1]))
    pipe_rows = [(m.start(), m.end()) for m in re.finditer(r"(?m)^\|.*\|\s*$", text)]
    starts = [s for s, e in pipe_rows if first in _squash(text[s:e])]
    ends = [e for s, e in pipe_rows if last in _squash(text[s:e])]
    if not starts or not ends:
        return None
    s0 = min(starts)
    e0 = max(e for e in ends if e >= s0) if any(e >= s0 for e in ends) else None
    if e0 is None:
        return None
    above = [(s, e) for s, e in pipe_rows if e <= s0]
    while above and text[above[-1][1]:s0].strip() == "":
        s0 = above[-1][0]
        above.pop()
    return (s0, e0)


def index_table_cells(tables: list[dict], origin: str,
                      source: str = "supplement") -> list[dict]:
    """Every numeric token in the CELLS of walked tables that the body text
    does not already contain.

    WHY THIS EXISTS, AND WHY IT IS NOT SUPPLEMENT-SPECIFIC. `index` enumerates a
    body text. Whether a table's numbers are in that count is an ACCIDENT OF THE
    CONVERTER: docling inlines tables as pipe rows, so 174 of Stern 2014's 876
    floor rows are `table_cell` for that reason alone -- while publisher XML
    keeps tables in their own elements, so on the 99 corpus papers the source
    ladder reads as `xml_publisher` the article's own table cells appear in the
    body text NOT AT ALL. Measured on `10.1002--ajcp.70049`: 143 article table
    cells, contributing 0 to the floor.

    So the caller passes the tables the body does NOT already contain -- in
    practice, those with no `text_span` -- and their cells are enumerated here.
    Keying on the span rather than on the source is what stops the same numbers
    being counted twice on a converter that does inline them.

    A supplement is the other half of the same fact: a separate FILE that never
    enters the body text under any converter. MEASURED on Stern: fetching the
    supplement took the scaffold from 144 table cells to 2,638 and left
    `n_total` at 876, so every placed/ambiguous/unplaced ratio was computed
    against a universe that excluded the paper's own statistics table -- the one
    its Results section points the reader to.

    THE POINT IS THAT THIS WILL MAKE COVERAGE LOOK WORSE, and that is the floor
    working. `tally`'s own note says an under-classifying pass must show up as a
    falling `share_judged` rather than an unchanged score. Nothing currently
    serves supplement text to the extraction, so these rows arrive
    `unclassified` and say so, instead of being absent and silent.

    IDS ARE NAMESPACED AND `offset` IS NONE, deliberately. A body row's id is
    its offset into the body text and consumers slice that text with it --
    `linear.chunks` selects a chunk's numerals by `chunk.start <= offset <
    chunk.end`. A supplement offset is into a DIFFERENT string, so reusing the
    field would silently file supplement numbers into whichever body chunk
    happens to span the same integer, and hand the model a number with the wrong
    surrounding text. `None` makes that a loud failure instead of a quiet
    mis-assignment; callers select on `source` first.

    Cells are classed `table_cell` because that assertion is TRUE here -- the
    table pass really does own them, and `paper_tables(include_supplements=True)`
    is that pass. Prose gets the ordinary `_class_of` treatment.
    """
    rows: list[dict] = []
    for t_i, table in enumerate(tables or [], start=1):
        for c_i, cell in enumerate(table.get("cells") or []):
            raw = str(cell.get("raw") or "")
            if not raw.strip():
                continue
            where = " | ".join(
                str(x) for x in (cell.get("row_label"), cell.get("col_label")) if x)
            for m in tokens(raw):
                rows.append({
                    "id": f"num:cell:{source}:{origin}:t{t_i}:c{c_i}:{m.start()}",
                    "printed": m.group(0),
                    "offset": None,
                    "end": None,
                    "class": "table_cell",
                    "why": (f"printed in a cell of {origin} table {t_i}, which the "
                            "body text does not contain; the table pass owns "
                            "this number"),
                    "context": f"{where}: {raw}".strip(": "),
                    "source": source,
                    "file": origin,
                    "table_index": t_i,
                    "cell_index": c_i,
                })
    return rows


def classify_with(rows: list[dict], spans: list[tuple[int, int]],
                  label: str = "statistic", evidence: str = "") -> int:
    """Mark every token falling inside one of `spans`. Returns how many.

    This is how `completeness.BODY_PATTERNS` earns its keep after ceasing to be
    the enumerator: it is good at what it DOES match, so its matches become
    positive classifications over the index rather than the index itself. What
    it misses is now visible as `unclassified` instead of absent.
    """
    n = 0
    for r in rows:
        if r["class"] != "unclassified":
            continue
        if any(a <= r["offset"] < b for a, b in spans):
            r["class"] = label
            r["why"] = evidence or "matched a reported-statistic pattern"
            n += 1
    return n


def _spread(rows: list[dict], k: int) -> list[dict]:
    """Up to `k` rows, preferring one per distinct preceding letter."""
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        key = str(r.get("preceded_by") or "").lower()
        if key not in seen:
            seen.add(key)
            out.append(r)
            if len(out) >= k:
                return out
    for r in rows:
        if r not in out:
            out.append(r)
            if len(out) >= k:
                break
    return out


def _letter_counts(rows: list[dict]) -> dict:
    """How many refusals sat behind each letter, commonest first. `F` and `t`
    dominating is the signal that degrees of freedom are what is being lost."""
    counts: dict[str, int] = {}
    for r in rows:
        key = str(r.get("preceded_by") or "?")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:10])


def tally(rows: list[dict], suppressed_rows: list[dict] | None = None) -> dict:
    """The three quantities a coverage claim needs, kept apart.

    `register.py` sets the rule this exists to satisfy: THE DENOMINATOR MUST BE
    INDEPENDENT OF THE FINDER. A model that both enumerates and judges
    checkability reports full coverage of whatever it happened to notice, and
    the metric IMPROVES as the enumeration degrades.

    `n_total` is model-free and near-complete, so it is the one denominator
    here that cannot quietly shrink. Publishing `n_statistic / n_total` beside
    the coverage number is what makes an under-classifying model visible: a
    classifier that gives up shows a falling ratio instead of a rising score.
    """
    by = {c: 0 for c in CLASSES}
    # STRATIFIED BY SOURCE, because "we checked X% of this paper's numbers" is a
    # different claim depending on whether the supplement is in the denominator.
    # One `n_total` spanning both, so there is still exactly ONE denominator --
    # a second tally would be a second denominator, which is the failure this
    # module exists to prevent -- plus the split, so a reader can see that (say)
    # every unread number is in a file nothing serves to the extraction.
    #
    # AND BY CHANNEL (Greg, 2026-09-06): table values and prose values are ONE
    # floor, and whenever the total is given the split is given beside it. The
    # key is `<source>_<prose|table>` from `source_key`, so `article_table` and
    # `article_prose` are separately visible under the one `n_total`.
    by_source: dict[str, dict] = {}
    for r in rows:
        b = by_source.setdefault(source_key(r), {"n_total": 0, "n_judged": 0})
        b["n_total"] += 1
        if (r.get("class") or "unclassified") != "unclassified":
            b["n_judged"] += 1
    # PER-SOURCE SHARE, because the top-line one stops being informative the
    # moment a large auto-classified block joins. `table_cell` counts as judged
    # -- it means another pass owns the number -- so adding a supplement's 2,832
    # table numerals to Stern took `share_judged` from 0.371 to 0.851 while
    # nothing new had been read. The headline is not wrong, it is dominated; the
    # split is what lets a reader see that the article half is still at 0.371.
    for b in by_source.values():
        b["share_judged"] = (b["n_judged"] / b["n_total"]) if b["n_total"] else None
    for r in rows:
        # ONE KEY, READ AND WRITTEN. The write defaulted a missing `class` to
        # "unclassified" while the read looked up the raw `None`, so such a row
        # RESET its bucket to 1 instead of incrementing -- silently deflating
        # every count above it and inflating `share_judged`, in the function
        # whose whole purpose is an honest denominator.
        kind = r.get("class") or "unclassified"
        by[kind] = by.get(kind, 0) + 1
    total = len(rows)
    judged = total - by["unclassified"]
    # WHAT THE ENUMERATOR REFUSED, reported beside the count and never inside
    # it. `n_total` keeps its exact meaning -- every token the model-free reader
    # yielded -- and a reader can now see how many digit runs it declined, and
    # on what evidence, instead of the omission being invisible.
    supp = list(suppressed_rows or [])
    return {
        "n_total": total,
        "by_class": by,
        "by_source": by_source,
        "n_suppressed_letter_attached": len(supp),
        # SAMPLED ACROSS DISTINCT PRECEDING LETTERS, not the first five. The
        # first five of Stern's 730 were all an email address and a mouse strain
        # (`ca60@nyu.edu`, `C57BL/6J`) -- genuinely not numbers, and so a sample
        # that made the refusals look entirely benign while 470 of them were a
        # test statistic's degrees of freedom.
        "suppressed_examples": [r.get("context") for r in _spread(supp, 6)],
        "n_suppressed_by_letter": _letter_counts(supp),
        "n_judged": judged,
        "share_judged": (judged / total) if total else None,
        "note": (
            "`n_total` is every numeric token, found without a model and "
            "without a shape rule, so it is the one count here that cannot be "
            "silently incomplete. `unclassified` is not a failure -- it is a "
            "number nobody has judged yet, and it is reported rather than "
            "dropped so that an under-classifying pass is visible as a falling "
            "`share_judged` instead of an unchanged coverage score. Read "
            "`by_source` (keyed `<source>_<prose|table>`) before the top-line "
            "share: prose and table cells are ONE floor, and a `_table` bucket "
            "counts as judged because another pass owns the number, so a "
            "source whose numbers are all in tables reads as fully judged "
            "whether or not anything has read them."
        ),
    }
