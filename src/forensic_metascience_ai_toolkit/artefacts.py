"""Find the code, data and registrations a paper points at.

MEASURED on the 95-paper high-value corpus: 18.9% name a code or data
repository, 29.5% carry a trial registration, and 77.9% have a
data-availability statement. On the older cerebrolysin corpus it is 1.0% and
5.6% -- this is a property of modern reporting standards, not of papers in
general.

Two uses, and only the first is automatic.

1. REPORTING. A paper that says "data are available at github.com/x/y" has made
   a checkable promise, and a reader assessing it wants to know the promise was
   made and where it points. A registration number is the strongest single
   handle on outcome switching that a text-only pass can offer.

2. INTAKE. `--artefact` lets an operator supply what those links point to -- a
   cloned repo, a downloaded OSF archive -- so the analysis can see it. Nothing
   here fetches anything: this module reads text and reports URLs. Downloading
   what a paper links to is a decision with its own consequences and is the
   operator's to make.
"""

from __future__ import annotations

import re
from pathlib import Path

#: (kind, pattern). Ordered most- to least- specific.
_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("github", re.compile(r"https?://(?:www\.)?github\.com/[\w.\-]+/[\w.\-]+", re.I)),
    ("gitlab", re.compile(r"https?://(?:www\.)?gitlab\.com/[\w.\-/]+", re.I)),
    ("osf", re.compile(r"https?://osf\.io/[\w]+", re.I)),
    # The URL prefix is OPTIONAL on the DOI-based deposits: papers routinely
    # cite a bare `10.5281/zenodo.1234567`, and requiring `https://` missed them.
    ("zenodo", re.compile(r"(?:https?://(?:doi\.org/)?)?10\.5281/zenodo\.\d+", re.I)),
    ("dryad", re.compile(
        r"https?://datadryad\.org/[\w./\-]+|(?:https?://doi\.org/)?10\.5061/[\w./\-]+", re.I)),
    ("figshare", re.compile(r"https?://(?:\w+\.)?figshare\.com/[\w./\-]+", re.I)),
    ("dataverse", re.compile(r"(?:https?://(?:doi\.org/)?)?10\.7910/DVN/[\w]+", re.I)),
    ("clinicaltrials", re.compile(r"\bNCT\d{8}\b")),
    ("isrctn", re.compile(r"\bISRCTN\d{8}\b", re.I)),
    ("prospero", re.compile(r"\bCRD4\d{10,}\b", re.I)),
    ("drks", re.compile(r"\bDRKS\d{8}\b", re.I)),
)

#: Kinds that are a REGISTRATION rather than a code/data deposit. Worth
#: separating: a registration supports checking outcome switching, a repository
#: supports checking the analysis.
_REGISTRIES = frozenset({"clinicaltrials", "isrctn", "prospero", "drks"})

#: A NAMED SECTION heading. "Data availability", "Code and materials sharing".
#: Precise on its own: the words only co-occur in that order when the paper is
#: making the statement.
_AVAILABILITY_HEADING = re.compile(
    r"\b(?:data|code|materials?)\s+(?:and\s+\w+\s+)?"
    r"(?:availability|accessibility|sharing)\b", re.I)

#: A LOCATOR for the prose form ("Data are available from the corresponding
#: author"). On its own it says nothing about WHAT is available, and the
#: subject is the whole claim -- so it is judged by `_AVAILABILITY_SUBJECT`.
#: Unjudged it read a drug-supply sentence as a data-sharing commitment:
#:   "Cerebrolysin was available from EVER Pharma (Unterach, Austria)."
#: which is ubiquitous in this repo's own corpus, and
#:   "Recruitment flyers are available upon request from the first author."
_AVAILABILITY_PROSE = re.compile(r"\bavailab\w+\s+(?:from|at|on|upon|via)\b", re.I)

#: What has to be the thing being made available. `materials` is deliberately
#: ABSENT here while present in the heading pattern above: "materials were
#: available from Sigma-Aldrich" is a reagent-supply sentence, and the cost of
#: the two errors is not symmetric. A miss adds the caveat "the links may be
#: incidental rather than a sharing commitment", which is conservative; a false
#: positive makes bundle.py assert "A data-availability statement is present
#: but names no repository", a claim about the authors' reporting conduct.
_AVAILABILITY_SUBJECT = re.compile(
    r"\b(?:data|datasets?|code|scripts?|software|syntax|"
    r"analys[ei]s\s+files?)\b", re.I)


def has_availability_statement(text: str) -> bool:
    """Does this paper state that its data or code can be obtained?

    The heading form settles it. The prose form only LOCATES a candidate; the
    clause must then name data or code as the thing available, because
    "available from" is how a paper says where it bought its reagents.
    """
    text = text or ""
    if _AVAILABILITY_HEADING.search(text):
        return True
    return any(
        _AVAILABILITY_SUBJECT.search(_clause_around(text, m.start(), m.end()))
        for m in _AVAILABILITY_PROSE.finditer(text)
    )


def find(text: str) -> dict:
    """Extract every artefact reference from a paper's text."""
    text = text or ""
    found: dict[str, list[str]] = {}
    for kind, pattern in _PATTERNS:
        hits = []
        for m in pattern.findall(text):
            v = m.rstrip(".,;)")
            if v not in hits:
                hits.append(v)
        if hits:
            found[kind] = hits

    repos = {k: v for k, v in found.items() if k not in _REGISTRIES}
    regs = {k: v for k, v in found.items() if k in _REGISTRIES}
    statement = has_availability_statement(text)

    return {
        "repositories": repos,
        "registrations": regs,
        "has_availability_statement": statement,
        "n_repositories": sum(len(v) for v in repos.values()),
        "n_registrations": sum(len(v) for v in regs.values()),
        "all": sorted({v for vs in found.values() for v in vs}),
    }


def find_in_paper(paper_dir: str | Path) -> dict:
    """Scan a paper directory's extracted text."""
    from .extraction.jats import paper_text

    paper_dir = Path(paper_dir)
    # Falls back to the XML full text when body.md is absent. Reading body.md
    # directly returned "" for every XML-fetched paper, so this scan silently
    # found nothing at all.
    text = paper_text(paper_dir)
    out = find(text)
    # An empty text is not a paper that shares nothing. `summarise` already
    # hedges ("absence here is weak evidence"), but that hedge is about
    # extraction dropping a data-availability statement -- a different and much
    # weaker claim than "we could not read one word of this paper". Saying "no
    # links found" about a document we never read invites the reader to hold it
    # against the authors for our failure.
    out["text_available"] = bool(text.strip())
    if not out["text_available"]:
        out["note"] = (
            "NO TEXT COULD BE READ from this paper, so whether it links to "
            "code, data or a registration is UNKNOWN. There is no body.md, no "
            "parseable XML and no usable PDF text layer -- the shape of a scan "
            "that was never OCR'd, or of a corrupt file. Do NOT record this as "
            "a paper that shares nothing."
        )
        return out
    out["note"] = summarise(out)
    return out


def summarise(found: dict) -> str:
    """One sentence a reader can act on."""
    bits = []
    if found["n_repositories"]:
        where = ", ".join(sorted(found["repositories"]))
        bits.append(f"{found['n_repositories']} code/data link(s) ({where})")
    if found["n_registrations"]:
        ids = ", ".join(v for vs in found["registrations"].values() for v in vs)
        bits.append(f"registration(s): {ids}")
    if not bits:
        return ("No code, data or registration links found in the extracted text. "
                "Absence here is weak evidence -- these often live in a "
                "data-availability statement that extraction may have dropped.")
    s = "This paper points at " + "; ".join(bits) + "."
    if not found["has_availability_statement"]:
        s += (" No data-availability statement was detected, so the links may be "
              "incidental rather than a sharing commitment.")
    s += (" Nothing was fetched. To analyse what they point to, supply it with "
          "--artefact.")
    return s


# ---------------------------------------------------------------------------
# Preregistration
#
# The strongest handle a text-only pass has on OUTCOME SWITCHING: a paper that
# registered a primary outcome and then reports a different one is the classic
# case, and it is invisible to every arithmetic check in this toolkit.
#
# Three states, and the distinction between the last two matters. A paper that
# SAYS it was not preregistered has been candid, and one found in this corpus
# explains why ("This trial was not registered because the data collection
# began..."). A paper that says nothing may or may not have registered. Treating
# silence as absence would be an accusation drawn from the extraction's gaps.
# ---------------------------------------------------------------------------

#: Registries whose presence establishes a prospective registration.
_PREREG_IDS = frozenset({"clinicaltrials", "isrctn", "prospero", "drks"})

_PREREG_TERMS = re.compile(
    r"\bpre-?regist\w+|\bregistered report\b|\bpre-?specified\s+(?:primary|outcome|analys)",
    re.I)

# Domain only. A bare "as predicted" matched "was predicted by the Papini et al.
# model" -- an ordinary sentence, not a registration.
_ASPREDICTED = re.compile(r"aspredicted\.org/\w+", re.I)

_OSF_PREREG = re.compile(
    r"osf\.io/\w+[^.]{0,120}?pre-?regist|pre-?regist[^.]{0,120}?osf\.io/\w+", re.I)

#: An explicit statement that the study was NOT preregistered.
#:
#: WIDENED 2026-08-18. The original three alternatives all required the -ED
#: form, so "we did not preregister our hypotheses" -- an ordinary way to say it
#: -- matched none of them and fell through to the bare-keyword branch, which
#: reported the paper as PREREGISTERED. The verb forms are added here rather
#: than by loosening the -ed patterns, so the match still has to sit next to an
#: explicit negation and cannot fire on "we preregistered".
_EXPLICIT_NONE = re.compile(
    r"\b(?:was|were|is|are)\s+not\s+(?:pre-?)?registered\b|"
    r"\bno\s+pre-?registration\b|"
    r"\bnot\s+pre-?registered\b|"
    r"\b(?:did|do|does|would)\s+not\s+pre-?regist\w*|"
    r"\b(?:has|have|had)\s+not\s+been\s+pre-?regist\w*|"
    r"\bwithout\s+(?:a\s+|any\s+)?pre-?registration\b", re.I)

#: Language indicating a DEPARTURE from the registered plan. Bare "post hoc" is
#: deliberately excluded: post-hoc analysis is ordinary and reporting it is good
#: practice, not evidence of switching.
_DEVIATION = re.compile(
    r"\bdeviat\w+\s+from\s+(?:the\s+)?(?:pre-?registered|registered|planned|protocol)|"
    r"\bdepartures?\s+from\s+(?:the\s+)?(?:pre-?registered|registered|protocol)|"
    r"\bchanges?\s+(?:to|from)\s+the\s+(?:pre-?registered|registered|planned)\s+"
    r"(?:protocol|analys\w+|outcome)|"
    # BOTH orders. Papers write "the secondary analyses ... were not
    # pre-registered" at least as often as "not pre-registered ... analyses",
    # and requiring the second order alone missed every real instance in the
    # corpus -- including a registered trial (NCT02737566) disclosing that its
    # secondary analyses were not, which is the mixed case that matters most.
    r"\banalys\w*\b[^.]{0,90}\b(?:was|were|are|is)\s+not\s+(?:pre-?registered|pre-?specified)|"
    r"\bnot\s+(?:pre-?registered|pre-?specified)\b[^.]{0,80}\banalys|"
    r"\bexploratory\b[^.]{0,40}\bnot\s+pre-?", re.I)

_PROTOCOL = re.compile(r"\b(?:study|trial)\s+protocol\b", re.I)


def _context(pattern: "re.Pattern[str]", text: str, n: int = 2) -> list[str]:
    out = []
    for m in pattern.finditer(text):
        s = max(0, m.start() - 90)
        out.append(re.sub(r"\s+", " ", text[s:m.end() + 110]).strip())
        if len(out) >= n:
            break
    return out


#: Clause boundaries, so a judgement about one mention cannot be made from a
#: neighbouring sentence. Same device as `supplements.mention_context`, added
#: there 2026-08-18 after a flat character window read across a semicolon.
_CLAUSE_EDGE = re.compile(r"[.;]")

#: Cues that a registration identifier belongs to a DIFFERENT study. Not an
#: attempt at exhaustive coverage -- an unrecognised cue leaves the mention
#: reading as this paper's own, which is the pre-existing behaviour, so the
#: list can only improve on it and never make it worse.
_THIRD_PARTY = re.compile(
    r"\b(?:ongoing|forthcoming|planned|future|separate|companion|parent|"
    r"another|other|previous|prior|earlier)\b|"
    r"\bwill\s+(?:address|report|examine|test)\b|"
    r"\b(?:reported|described|conducted|registered)\s+by\b|"
    r"\bet\s+al\b", re.I)

#: A clause DENYING departures is not a discussion of departures.
_NO_DEVIATION = re.compile(
    r"\b(?:no|none|without|not\s+any)\s+(?:\w+\s+){0,2}"
    r"(?:deviat\w+|departures?|changes?)\b|"
    r"\b(?:deviat\w+|departures?)\s+(?:were|was)\s+not\b", re.I)


def _clause_around(text: str, start: int, end: int, window: int = 90) -> str:
    """The clause a match sits in -- bounded by `.` or `;`, not by distance."""
    text = text or ""
    lo, hi = max(0, start - window), min(len(text), end + window)
    left = text[lo:start]
    edges = list(_CLAUSE_EDGE.finditer(left))
    if edges:
        lo += edges[-1].end()
    right = text[end:hi]
    edge = _CLAUSE_EDGE.search(right)
    if edge:
        hi = end + edge.start()
    return " ".join(text[lo:hi].split())


def preregistration(text: str, found: dict | None = None) -> dict:
    """Is this paper preregistered, and does it say it departed from the plan?"""
    text = text or ""
    found = found if found is not None else find(text)

    # NO TEXT MEANS UNKNOWN, NOT "NOT MENTIONED".
    #
    # Every branch below reads `text`, so on an empty string they all come back
    # negative and `status` lands on `not_mentioned` -- a machine-readable claim
    # ABOUT THE PAPER produced by our failure to read it. The prose `note` does
    # hedge, but `status` is the field a renderer or a downstream consumer
    # branches on, and a hedge in prose beside an unqualified enum is how the
    # unqualified one wins.
    #
    # FOUND 2026-08-18 tracing #177: `agent.py` calls this with
    # `paper_text(paper_dir)`, which returns "" for a scan with no OCR layer or
    # a PDF that could not be extracted -- 2 of the first 41 documents in the
    # Zotero sweep. The same shape as `supplements.audit`'s three-valued
    # `missing` and the PubPeer record's null `n_comments`: the absence of an
    # answer must not be spelled the same way as a negative answer.
    if not text.strip():
        return {
            "status": "unknown_no_text",
            "identifiers": {},
            "osf_preregistration": False,
            "aspredicted": [],
            "mentions_protocol": False,
            "deviation_passages": [],
            "note": (
                "NO TEXT COULD BE READ from this paper, so whether it is "
                "preregistered is UNKNOWN. This is not a finding that "
                "preregistration went unmentioned -- it is a fact about this "
                "extraction, and must not be reported as one about the paper."
            ),
        }

    ids = {k: v for k, v in found.get("registrations", {}).items() if k in _PREREG_IDS}
    osf_prereg = bool(_OSF_PREREG.search(text))
    aspredicted = _ASPREDICTED.findall(text)
    terms = bool(_PREREG_TERMS.search(text))
    explicit_none = bool(_EXPLICIT_NONE.search(text))

    has_id = bool(ids) or osf_prereg or bool(aspredicted)

    # AN EXPLICIT DENIAL BEATS THE BARE KEYWORD, and until 2026-08-18 it could
    # not, because `terms` was tested first.
    #
    # `_PREREG_TERMS` matches `pre-?regist\w+`, which fires on the word inside a
    # NEGATED sentence -- and a paper can only deny preregistration by using the
    # word. So `explicitly_not_preregistered` was unreachable in exactly the
    # case it names, and the branch was dead. MEASURED on four sentences, all of
    # which returned `preregistered`:
    #     "No preregistration was performed for this study."
    #     "This study was not preregistered."
    #     "We did not preregister our hypotheses."
    #     "The study was preregistered."          (the only correct one)
    #
    # The direction is worth naming: this made a paper look BETTER than it is,
    # so it is a false exoneration rather than a false accusation. It is still a
    # statement about a paper that contradicts what the paper says, in a
    # document whose whole value is that its statements can be checked.
    #
    # A hard identifier still wins over a denial, and deliberately so: a paper
    # carrying an OSF registration that also says "Study 2 was not
    # preregistered" is genuinely mixed, and the ID is the falsifiable half.
    # THE ID MUST BE THIS PAPER'S. Greg, 2026-08-18: "I do not see why this kind
    # of rudimentary application of regex is being used at all." VERIFIED: "The
    # ongoing confirmatory trial (NCT02737566) will address this question; the
    # present secondary analysis was exploratory." returned `preregistered` on
    # somebody else's registration. The clause around each identifier is now
    # checked for a third-party cue, and an attributed identifier stops being
    # evidence that THIS study was registered.
    id_clauses = [_clause_around(text, m.start(), m.end())
                  for m in re.finditer(r"\b(?:NCT\d{6,}|ISRCTN\d{6,}|"
                                       r"ACTRN\d{6,}|CRD\d{6,})\b", text or "",
                                       re.I)]
    id_is_third_party = bool(id_clauses) and all(
        _THIRD_PARTY.search(c) for c in id_clauses)

    if has_id and not id_is_third_party:
        status = "preregistered"
    elif explicit_none:
        status = "explicitly_not_preregistered"
    elif terms:
        # A KEYWORD IS A LOCATION, NOT A VERDICT, and this branch used to be one.
        # `_PREREG_TERMS` matches `pre-?regist\w+`, which fires inside a negated
        # sentence, a citation of someone else's registered report, and a
        # statement about future work. It cannot tell any of those from a claim
        # about this study, so it no longer asserts one. The passages travel in
        # `mention_passages` for a reader -- or the model, which already makes
        # this judgement per hypothesis with a quoted registration -- to settle.
        status = "mentioned_unverified"
    elif id_is_third_party:
        status = "mentioned_unverified"
    else:
        status = "not_mentioned"

    # A DENIAL OF DEPARTURES IS NOT A DEPARTURE. VERIFIED: "There were no
    # deviations from the registered protocol." produced one deviation passage,
    # so a paper stating it followed its protocol was recorded as discussing
    # departures from it.
    deviations = [d for d in _context(_DEVIATION, text, n=4)
                  if not _NO_DEVIATION.search(str(d))]

    if status == "preregistered":
        where = ", ".join(sorted(ids)) or ("OSF" if osf_prereg else
                                           "AsPredicted" if aspredicted else "stated in text")
        note = f"Preregistration indicated ({where})."
        if not has_id:
            note += (" No registration identifier was found, only the claim -- the "
                     "registration itself was not located and has not been checked.")
        note += (" A registered study can still switch outcomes; comparing the "
                 "registered primary outcome against the reported one is the check "
                 "this enables, and it is not automated here.")
        if deviations:
            note += (f" The paper DOES discuss departures from its plan "
                     f"({len(deviations)} passage(s)) -- read those first.")
        else:
            note += " No discussion of deviations from the plan was found."
    elif status == "explicitly_not_preregistered":
        note = ("The paper states it was NOT preregistered. That is candour, not a "
                "finding: it means the analyses cannot be checked against a prior "
                "plan, so the distinction between confirmatory and exploratory rests "
                "on the authors' account.")
    else:
        note = ("No preregistration is mentioned in the extracted text. This is WEAK "
                "evidence: registration statements often sit in a data-availability "
                "or funding section that extraction may have dropped, and absence "
                "here is not evidence that none exists.")

    # A disclosed departure is informative WHATEVER the registration status. It
    # was previously mentioned only in the `preregistered` branch, so a paper
    # that discloses a deviation without a registration ID we could match had
    # that disclosure silently dropped -- which inverts the point: the paper was
    # being candid and we were hiding it.
    if deviations and status != "preregistered":
        note += (f" The paper nonetheless discusses departures from a plan or "
                 f"unregistered analyses ({len(deviations)} passage(s)); those "
                 "passages are reproduced below and are worth reading.")

    return {
        "status": status,
        "identifiers": ids,
        "osf_preregistration": osf_prereg,
        "aspredicted": aspredicted,
        "mentions_protocol": bool(_PROTOCOL.search(text)),
        "deviation_passages": deviations,
        "note": note,
    }
