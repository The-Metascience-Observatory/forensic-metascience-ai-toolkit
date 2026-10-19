"""Split a paper's body from its bibliography, once, as a named boundary.

GREG, 2026-08-16: "extract the references separately. That way this kind of
mistake won't happen."

THE MISTAKE. The statistics-register floor enumerated the reference list.
MEASURED over the 16 cached docling extractions: 33 of 439 floor items (7.5%)
sat inside a bibliography, and for `10.1002--eat.24415` it was 20 of 25 -- 80%
of that paper's floor. Three were DOIs read as sample fractions:
`10.1037/0022-3514` enumerates as the "statistic" 1037/0022, a fraction whose
numerator exceeds its own total. The floor is what accuses the register of
being incomplete, so each of those was our artefact charged to the model as a
statistic it failed to list.

WHY A MODULE RATHER THAN A CUTOFF INSIDE THE ENUMERATOR. The first fix put a
heuristic in `_body_items`. That works and is not enough: the next consumer
that reads body text re-derives its own boundary, or forgets to. One boundary,
computed once, carried as data, is what makes the class of mistake go away
instead of this instance of it. `split()` is the only place that decides.

HONEST FAILURE. When no boundary is found the whole text is the body and `how`
says `not_found`. Guessing a cut would silently delete real results, which is
the worse direction: a bibliography enumerated as statistics is noise a reader
can see, while a Results section truncated out of the body is a finding nobody
ever hears about.
"""
from __future__ import annotations

import re

#: A heading, not a mention. Anchored to a whole line so "we compared our
#: references to theirs" cannot truncate a paper.
_HEADING = re.compile(
    r"^[ \t]*#{0,6}[ \t]*\**[ \t]*"
    r"(?:references?|bibliography|literature\s+cited|works\s+cited|"
    r"references?\s+cited)"
    r"[ \t]*\**[ \t]*:?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

#: One numbered bibliography entry: "18. Badre D, Wagner A-D (2006) ..." or
#: "3. Smith, J. A., & Jones, B. (1998)." Numbered journals (PNAS, Nature) print
#: no heading at all, so this is the only signal those papers give.
#:
#: The surname is matched as ANY letter, not `[A-Z]`. Requiring a capital broke
#: on `5. te Nijenhuis J, van Vianen AEM, ...` in PNAS 0801268105 -- a lowercase
#: Dutch particle -- which punched a hole in the numbering and moved the detected
#: boundary five entries down, leaving part of the bibliography in the body. The
#: year-in-parens lookahead is what makes this specific; the letter class was
#: never carrying the constraint, only an Anglophone assumption.
#:
#: TWO YEAR FORMS. APA/PNAS parenthesise it -- `(2007)` -- and AMA/Vancouver, the
#: house style of most medical journals including JAMA, does not: `Psychol
#: Methods 2002 Mar;7(1):83-104.` Requiring parens would have skipped the entire
#: medical half of the target corpus.
#: A LEADING LIST MARKER AND A LOOSE PERIOD. docling emits some bibliographies
#: as a markdown bullet list -- `- 55 . Niu, Z. et al.` -- with a dash before
#: the number and a space before the point. The anchored form saw neither, so
#: the boundary was never found and the whole reference list was enumerated as
#: the paper's own statistics. 15 of 211 Zotero-corpus papers use this shape;
#: it accounts for 5 of the 35 whose boundary was missed.
_NUMBERED_ENTRY = re.compile(
    r"^[ \t]*(?:[-*\u2022][ \t]*)?(\d{1,3})[ \t]*\.[ \t]+"   # the entry number
    r"(?=[^\n]{0,160}?"                   # ...followed close by, on the line:
    r"(?:\((?:19|20)\d{2}[a-z]?\)"        #   an APA year in parens
    r"|(?:19|20)\d{2}[a-z]?\s*[;:]))"     #   or a Vancouver year before ; or :
    r"[^\W\d_]",                          # entries start with a surname
    re.MULTILINE | re.UNICODE,
)

#: How far the numbering may jump and still count as the same run. Extraction
#: drops an entry now and then -- a reference split across a column break, a line
#: the layout model read as a caption -- and an exact +1 rule turns one dropped
#: entry into a boundary in the wrong place.
_MAX_GAP = 3

#: Below this fraction of the document a match is far likelier to be a table of
#: contents, a running header, or a numbered Methods list than the bibliography.
_EARLIEST = 0.40

#: A lone "12. Smith J (1999)" in the Discussion is not a bibliography. A run of
#: them is.
_MIN_RUN = 4

#: How far apart two numbered runs may sit and still be ONE list. Extraction
#: drops entries, so a single bibliography arrives as several runs; without
#: merging them, "the last run" starts partway into the bibliography. MEASURED
#: over cerebrolysin_papers: the three real within-bibliography gaps are 192,
#: 752 and 1,155 characters. A numbered list in the body is separated from the
#: bibliography by an entire Discussion section, which is far longer.
_SAME_LIST_GAP = 3000


def _numbered_run_start(text: str, floor: int) -> tuple[int | None, int]:
    """Start offset of the longest ascending run of numbered entries, and its length.

    Ascending matters. Numbered lists recur in Methods ("1. participants were
    screened...") and a run there does not climb into the twenties and stay
    monotone the way a reference list does. But the ascent is allowed to SKIP:
    see `_MAX_GAP`. An exact +1 rule read PNAS 0801268105's list as starting at
    entry 6, because entry 5 was `te Nijenhuis` and did not match at all.
    """
    hits = [(m.start(), int(m.group(1))) for m in _NUMBERED_ENTRY.finditer(text)]
    runs: list[list[int]] = []                # [start, length, last entry offset]
    run_start, run_len, prev, last_off = None, 0, None, None
    for off, num in hits:
        if prev is not None and prev < num <= prev + _MAX_GAP:
            run_len += 1
        else:
            if run_start is not None and run_len >= _MIN_RUN and run_start >= floor:
                runs.append([run_start, run_len, last_off])
            run_start, run_len = off, 1
        prev, last_off = num, off
    if run_start is not None and run_len >= _MIN_RUN and run_start >= floor:
        runs.append([run_start, run_len, last_off])
    if not runs:
        return None, run_len

    # MERGE RUNS THAT ARE THE SAME LIST, THEN TAKE THE LAST GROUP.
    #
    # Choosing the LONGEST run cut a systematic review at its Results, because
    # a numbered list of included trials there ("1. Smith J (2011) reported a
    # mean difference of 1.4...") is longer than a short bibliography. The
    # Discussion, the pooled estimate and the whole remainder of the paper were
    # then returned as `references` and never enumerated as reported
    # statistics -- and `how` said `numbered_run` either way, so nothing
    # downstream could tell.
    #
    # But taking the LAST run alone is worse, and MEASURED so: on three
    # cerebrolysin papers it moved the boundary from the true start of the
    # bibliography to entry 37, entry 18 and entry 11 of it, because
    # extraction drops an occasional entry and splits one bibliography into
    # several runs. Half of a real bibliography was reclassified as body.
    #
    # So runs close together are one list. The threshold is set from the data:
    # the three within-bibliography gaps in that corpus are 192, 752 and 1,155
    # characters -- a few reference entries the pattern missed. A body list is
    # separated from the bibliography by an entire Discussion section, which is
    # an order of magnitude further.
    groups = [runs[0]]
    for r in runs[1:]:
        if r[0] - groups[-1][2] <= _SAME_LIST_GAP:
            groups[-1] = [groups[-1][0], groups[-1][1] + r[1], r[2]]
        else:
            groups.append(r)
    return groups[-1][0], groups[-1][1]


def split(text: str) -> dict:
    """`{body, references, boundary, how, n_entries}` for one document's text.

    `how` is part of the contract, not decoration: a caller that needs to know
    whether the bibliography was actually removed -- an audit line, a coverage
    count -- must be able to tell `heading` from `not_found` without re-running
    the detection.
    """
    text = text or ""
    if not text:
        return {"body": "", "references": "", "boundary": None,
                "how": "empty", "n_entries": 0}

    floor = int(len(text) * _EARLIEST)

    # LAST heading, not first: a paper may list "References" in a table of
    # contents, and the real section is the one further down.
    cut, how, n = None, "not_found", 0
    for m in _HEADING.finditer(text):
        if m.start() >= floor:
            cut, how = m.start(), "heading"

    if cut is None:
        start, n = _numbered_run_start(text, floor)
        if start is not None:
            cut, how = start, "numbered_run"

    if cut is None:
        return {"body": text, "references": "", "boundary": None,
                "how": how, "n_entries": n}

    return {"body": text[:cut], "references": text[cut:], "boundary": cut,
            "how": how, "n_entries": n}


def body_of(text: str) -> str:
    """The body alone, for callers that need nothing else."""
    return split(text)["body"]


#: A line in the discarded tail that reads like BODY PROSE rather than a
#: bibliography entry. Deliberately HIGH-PRECISION: it is better to miss
#: stranded prose than to report a reference entry as lost body, because the
#: number this produces is used to qualify a completeness claim and an inflated
#: one would make the qualification meaningless.
_REF_ENTRY_START = re.compile(r"^\s*(?:\d+\.|\[\d+\]|[A-Z][a-z]+,?\s+[A-Z]\.)")
#: `Psychol Rev 97:404-431` -- the volume:page run that only a citation has.
_VOLUME_PAGES = re.compile(r"\b\d+\s*:\s*\d+\s*[-–]\s*\d+")
#: `Carpenter PA, Just MA (1990) ...` -- an author-year citation body.
_AUTHOR_YEAR = re.compile(r"\(\d{4}\)")
#: Short lines are page furniture, running heads and column artefacts.
_MIN_PROSE_CHARS = 60


def stranded_prose(text: str) -> dict:
    """Body prose that fell on the REFERENCES side of the split.

    WHY THIS EXISTS. `numerals.tally` promises that its `n_total` "is the one
    count here that cannot be silently incomplete", and `register_view` prints
    that promise to a reader. The promise rests on the reference cut removing
    only references.

    MEASURED 2026-09-01 over the 12-paper corpus: SIX papers strand real body
    prose after the cut, 27 lines in all. Every two-column PNAS paper does it,
    because the converter interleaves the reference block with the running text
    -- on `pnas.0801268105` the tail contains `mean age, 25.6 years of age; SD,
    3.3` and the whole `Materials. Training task.` section, sitting after a
    `Psychol Rev 51:77-101.` entry with a column separator between them. The cut
    is not wrong about where the references START; the document is not in
    reading order.

    REPORTED, NOT REPAIRED. Moving the boundary would readmit the bibliography,
    which is the single largest source of numerals that are not statistics --
    the reason the cut exists. Recovering only the prose means deciding, line by
    line, which side of an interleaved column each belongs to, and a wrong
    answer puts citation years into the statistics stream. So this says the
    completeness claim does not hold for this document and leaves the fix to a
    caller that knows more.
    """
    text = text or ""
    sp = split(text)
    boundary = sp.get("boundary")
    if not isinstance(boundary, int) or boundary >= len(text):
        return {"n_lines": 0, "n_chars": 0, "lines": [], "how": sp.get("how")}

    out: list[str] = []
    for line in text[boundary:].split("\n"):
        s = line.strip()
        if len(s) < _MIN_PROSE_CHARS:
            continue
        if _REF_ENTRY_START.match(s):
            continue
        if _VOLUME_PAGES.search(s):
            continue
        if s.count(".") >= 2 and _AUTHOR_YEAR.search(s):
            continue
        out.append(s)
    return {"n_lines": len(out), "n_chars": sum(len(s) for s in out),
            "lines": out[:5], "how": sp.get("how")}
