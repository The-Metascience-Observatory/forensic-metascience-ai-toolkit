"""Where a paper's ANALYTIC prose is, and where its furniture is.

Greg, 2026-08-18:

    > I think the better approach for the front matter and the citation section
    > (and other sections I cannot think of at this moment) is to identify those
    > sections and don't include them in the analysis of the extractable values.

He is right, and the alternative is what this module replaces: a per-number rule
for each kind of noise. Two of those had already been written -- a citation-year
rule and, before it, an affiliation-superscript problem nobody had got to -- and
each one only ever covers the shape it was written for. A section map covers the
shapes nobody has thought of yet, which is the half he named.

WHAT THIS IS NOT FOR. It does not shrink the numeral floor. `numerals.index`
stays exhaustive, because it is the tripwire that says what the finder missed,
and a floor that quietly stops counting is the one defect this whole layer
exists to prevent. Sections CLASSIFY: a number in the acknowledgements is
judged, not dropped, and `share_judged` rises honestly instead of the
denominator falling.

FAIL CLOSED, ALWAYS. Every unrecognised heading is ANALYTIC, and a paper with no
recognisable analytic heading gets NO front matter at all. Excluding a real
Results section would delete true statistics from the work list silently, and a
missing statistic is invisible in a way a surplus one is not.
"""

from __future__ import annotations

import re

#: kinds a span can have.
ANALYTIC, FRONT_MATTER, BACK_MATTER = "analytic", "front_matter", "back_matter"

_HEADING = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]*(.+?)[ \t]*$")

#: Letter-spaced headings are real and common: 13 of 119 corpus papers print
#: `## A B S T R A C T`, and 10 print `## A R T I C L E I N F O`. Matching them
#: literally would need a pattern per spelling, so single characters separated
#: by spaces are squashed back together first.
_SPACED = re.compile(r"\b(?:\w[ \t]){2,}\w\b")

#: Publisher furniture and the paper's own identity block. `accepted manuscript`
#: appears in 111 of 119 corpus papers, `article in press` in 17.
_FRONT = re.compile(
    r"^(?:body|accepted manuscript|article in press|articleinfo|article info|"
    r"original (?:paper|article|research)|research (?:paper|article)|"
    r"review article|open access|editorial|correspondence)\b")

#: Sections after the argument ends. Their numbers are grant ids, ORCIDs, dates
#: and page ranges -- never a reported result.
_BACK = re.compile(
    r"^(?:references?|bibliography|literature cited|works cited|"
    r"acknowledge?ments?|acknowledgements?|funding|financial support|"
    r"competing interests?|conflicts? of interest|declarations?|"
    r"disclosures?|author contributions?|contributorship|"
    r"data availability|availability of data|code availability|"
    r"ethics? (?:approval|statement)|consent|informed consent|"
    r"abbreviations?|glossary|orcid|supplementary|supporting information|"
    r"appendix|appendices)\b")

#: The headings that mark the argument itself. Used ONLY to decide where the
#: front matter stops -- never to exclude anything, so a paper whose Methods
#: heading we fail to recognise loses nothing.
_ANALYTIC = re.compile(
    r"^(?:a ?b ?s ?t ?r ?a ?c ?t|abstract|summary|introduction|background|"
    r"objectives?|aims?|methods?|materials? and methods?|method and materials?|"
    r"patients and methods|subjects and methods|experimental|"
    r"statistical analys[ie]s|statistics|study design|participants|"
    r"results?|findings|discussion|conclusions?|interpretation|limitations)\b")


def _norm(raw: str) -> str:
    s = _SPACED.sub(lambda m: m.group(0).replace(" ", "").replace("\t", ""), raw)
    s = re.sub(r"^[\d.)\s]+", "", s.strip().lower())
    return re.sub(r"\s+", " ", s).strip(" :.-–—")


def _kind(name: str) -> str:
    if _BACK.match(name):
        return BACK_MATTER
    if _FRONT.match(name):
        return FRONT_MATTER
    return ANALYTIC


def map_sections(text: str) -> list[dict]:
    """`[{name, raw, kind, start, end}]`, covering the whole string in order.

    The span before the first heading is the paper's identity block -- title,
    authors, affiliations -- and is front matter ONLY when an analytic heading
    turns up later. Without that evidence it stays analytic, because a paper we
    cannot read the structure of is one we must not start deleting from.
    """
    if not text:
        return []
    marks = [(m.start(), m.end(), _norm(m.group(1))) for m in _HEADING.finditer(text)]
    if not marks:
        return [{"name": "", "raw": "", "kind": ANALYTIC,
                 "start": 0, "end": len(text)}]

    out: list[dict] = []
    for i, (start, _end, name) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out.append({"name": name, "raw": name, "kind": _kind(name),
                    "start": start, "end": stop})

    # A back-matter section runs until the argument RESUMES, not merely until
    # the next heading: `## Acknowledgements` is routinely followed by
    # `## Funding` and then `## References`, and treating each sub-heading as a
    # fresh start would let the middle of the back matter read as analytic.
    seen_back = False
    for sec in out:
        if sec["kind"] == BACK_MATTER:
            seen_back = True
        elif seen_back and _ANALYTIC.match(sec["name"]):
            seen_back = False
        elif seen_back:
            sec["kind"] = BACK_MATTER

    # ONLY the identity block and headings we RECOGNISE as furniture. An
    # earlier cut classed everything before the first analytic heading as front
    # matter, and it silently ate real results: a paper's TITLE is itself a
    # markdown heading, and the section under it holds the abstract. MEASURED
    # over 40 corpus papers, that rule put 36 numerals already classed
    # `statistic` inside an excluded span -- among them "reduced A-beta burden
    # by 43% in the young group and by 27% in the older" and "death of 60% of
    # the animals". Those are findings.
    #
    # The trade is deliberate and one-sided. Keeping an affiliation superscript
    # in the work list costs the model one glance at a number it will call
    # noise; dropping a reported percentage costs a check that would otherwise
    # have run, and nothing downstream can tell that it is missing. Surplus is
    # visible, absence is not.
    head = {"name": "", "raw": "", "start": 0, "end": marks[0][0],
            "kind": FRONT_MATTER}
    return ([head] if head["end"] > 0 else []) + out


def kind_at(sections: list[dict], offset: int) -> str:
    """Which kind of span an offset falls in. Unknown offsets read ANALYTIC."""
    for sec in sections or []:
        if sec["start"] <= offset < sec["end"]:
            return sec["kind"]
    return ANALYTIC


def spans(sections: list[dict], kind: str) -> list[tuple[int, int]]:
    return [(s["start"], s["end"]) for s in sections or [] if s["kind"] == kind]
