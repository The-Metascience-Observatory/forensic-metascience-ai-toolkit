"""What this toolkit has been TESTED on, and what it is not built for.

WHY THIS IS A MODULE AND NOT A SENTENCE IN THE README. Every accuracy statement
this project makes is supposed to name its denominator. The scope of the
evidence base is the same kind of claim: a reader who is handed a forensic
report on a qualitative study has no way to know that nothing resembling their
paper was ever in the corpus that shaped these checks. `disclaimer.py` already
tells them the base rates; this tells them the population those base rates came
from.

-----------------------------------------------------------------------------
THE EVIDENCE BASE, hand-classified 2026-08-11
-----------------------------------------------------------------------------
Source: the 19 distinct papers behind the 37 archived runs in this checkout,
classified by reading the reports (see
`scratchpad/editorial_categories_generalization_fable_2026-08-11.md`, local scratch, not tracked §1). NOT
derived from `paper_metadata.study_design` -- that field exists in the schema
and is empty in all 37 archived records, so any machine count would be zero and
would be reported as though nothing had been tested.

The honest summary is that this is a small, biomedical/psychology corpus of
PRIMARY research, and it is dominated by human RCTs.

-----------------------------------------------------------------------------
WHAT THIS TOOLKIT IS NOT FOR, and the difference between the two cases
-----------------------------------------------------------------------------
NARRATIVE REVIEWS -- not designed for, at all. Almost every number in one is
somebody else's, quoted from a primary paper. The arithmetic checks would run
against values the review's authors did not produce and cannot be responsible
for, so a flag is an accusation pointed at the wrong people. That is the
cardinal failure mode with an extra step, and no amount of care in the checks
prevents it.

META-ANALYSES AND SYSTEMATIC REVIEWS -- a real and worthwhile audit target, and
a DIFFERENT UNDERTAKING from this one (Greg's call, 2026-08-11). Their numbers
ARE their own -- pooled effects, heterogeneity statistics, weights -- but what
makes one sound is search completeness, inclusion-criteria application,
double-extraction, risk-of-bias assessment and publication-bias analysis. None
of that is what the checks here test, and running GRIM against a pooled
standardised mean difference tests nothing anybody cares about. Building it is
a separate project with its own tools; pretending this one covers it would be a
false all-clear on the parts that matter.

The classifier below is CONSERVATIVE and ADVISORY. It fires on a paper's own
self-description in its title or abstract, never on a body mention, because a
primary study citing a meta-analysis is the common case and misreading one as
out of scope would refuse a paper we handle perfectly well. It never blocks a
run: it labels one, and the label goes in front of the reader.
"""

from __future__ import annotations

import re
from typing import Any

#: Design families the archive actually contains, with run counts. Written as
#: data so the report and the README cannot drift apart, and so adding a paper
#: to the corpus means editing one place.
TESTED_ON: tuple[tuple[str, int, str], ...] = (
    ("Human randomised trials and their follow-ups", 12,
     "the bulk of it -- 3-arm rTMS trial, stroke RCTs, a pooled 2-RCT analysis, "
     "a home-visiting follow-up, blinded-control and antibiotics trials"),
    ("Rodent / preclinical neuroscience", 2, "nanoparticle toxicity, ischaemia models"),
    ("Observational multilevel community psychology", 3, "coalition study"),
    ("Complex-survey cross-sectional epidemiology", 2, "veterans / suicidality"),
    ("Social-psychology laboratory experiments", 2, "one of them retracted"),
    ("Cost-effectiveness analysis", 1, "a Markov cost-utility model"),
    ("Retrospective records with latent-class analysis", 1, "inpatient comorbidities"),
    ("Ecological momentary assessment / intensive longitudinal", 4, "mediation model; three of the four are 2026-08-11 re-runs of the same paper -- the warrant-schema run and the clamped re-run are the repeat-run pair"),
    ("A correction notice", 1,
     "not a study at all; the run correctly said so and audited the notice"),
)

#: Families with ZERO representation. Naming them is the point of the section:
#: an unnamed gap reads as coverage.
NOT_TESTED: tuple[str, ...] = (
    "qualitative and mixed-methods research",
    "bench chemistry, materials science and physics",
    "genomics and other high-throughput -omics",
    "economics, political science and other quantitative social science outside psychology",
    "any field outside biomedicine and psychology (one environmental-journal paper "
    "is itself a clinical rehabilitation study)",
    "single-case and small-N designs",
    "simulation and modelling studies",
)

#: Document kinds this toolkit is not the right instrument for, and why.
OUT_OF_SCOPE: dict[str, dict[str, str]] = {
    "narrative_review": {
        "label": "a narrative review",
        "stance": "not designed for",
        "why": ("Nearly every number in a narrative review is quoted from somebody "
                "else's paper. Checking those numbers tests the papers being "
                "reviewed, not the review, so a flag lands on authors who did not "
                "produce the value. Do not use this output to judge a narrative "
                "review."),
    },
    "systematic_review": {
        "label": "a systematic review",
        "stance": "a separate undertaking",
        "why": ("Auditing a systematic review means auditing its search strategy, "
                "its inclusion criteria and how they were applied, its extraction "
                "procedure and its risk-of-bias assessment. None of that is what "
                "the checks here test. Treat any consistency result below as "
                "narrow bookkeeping about the numbers printed, not as an "
                "assessment of the review."),
    },
    "meta_analysis": {
        "label": "a meta-analysis",
        "stance": "a separate undertaking",
        "why": ("A meta-analysis's own numbers are pooled estimates, weights and "
                "heterogeneity statistics. What makes one sound -- search "
                "completeness, correct effect-size conversion, publication-bias "
                "analysis, the independence of the included samples -- is a "
                "different audit with different tools, and this toolkit does not "
                "perform it. Granularity checks in particular say nothing useful "
                "about a pooled standardised mean difference."),
    },
}

#: LOCATORS, not verdicts. Every pattern below only says "a review design is
#: NAMED here"; whether the paper is claiming that design FOR ITSELF is decided
#: afterwards by `_title_is_self_description` and `_mention_is_self_description`.
#: The split exists because the previous form treated naming and claiming as the
#: same act, and a paper that merely CITES a meta-analysis was reclassified as
#: being one -- which puts a notice at limitations[0] saying this toolkit does
#: not apply to the paper at all.
#:
#: Singular `meta-analysis` only. `meta-analyses` (plural) and bare
#: `meta-analytic` are the forms a title uses when meta-analysis is its SUBJECT
#: MATTER rather than its design -- "Do meta-analyses overestimate treatment
#: effects? A randomised head-to-head trial" is a trial, not a meta-analysis.
#: `meta-analytic` survives only when it modifies a review noun.
_TITLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("meta_analysis", r"\bmeta[-\s]?analysis\b"),
    ("meta_analysis", r"\bmeta[-\s]?analytic\s+(?:review|synthesis|stud(?:y|ies))\b"),
    ("systematic_review", r"\bsystematic\s+review\b"),
    ("systematic_review", r"\bscoping\s+review\b"),
    ("systematic_review", r"\brapid\s+review\b"),
    ("systematic_review", r"\bumbrella\s+review\b"),
    ("narrative_review", r"\bnarrative\s+review\b"),
    ("narrative_review", r"\b(?:a\s+)?(?:critical\s+|brief\s+|mini[-\s])?review\s+(?:of|on)\s+the\s+literature\b"),
    ("narrative_review", r":\s*a\s+review\s*$"),
    ("narrative_review", r"^\s*review\s*:"),
)

#: LOCATORS for running text. Each requires a verb of CONDUCTING near the design
#: noun -- the construction of a design claim -- but is otherwise loose about
#: what sits between them, because the strictness lives in the judge. The old
#: form hard-coded the whole sentence ("we conducted a meta-analysis") and so
#: missed "We therefore conducted a meta-analysis" while still firing on a bare
#: "random-effects meta-analysis" that named someone else's work.
#:
#: ACCEPTED FALSE NEGATIVE: a purely passive self-description with no first
#: person anywhere in the clause -- "A meta-analysis was conducted according to
#: PRISMA" -- does not fire, because the judge cannot tell it from a sentence
#: about a cited synthesis. Real meta-analyses almost always say so in the
#: TITLE, which is checked separately and unaffected; this is the backstop, and
#: a backstop that stays quiet costs a caveat, while one that fires wrongly
#: tells the reader the toolkit does not apply to a paper it does apply to.
_ABSTRACT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("meta_analysis",
     r"\b(?:conduct|perform|carr(?:y|ied)|undert(?:ook|ake|aken)|report|present|"
     r"pool)\w*\b[^.;?]{0,40}?\bmeta[-\s]?analys[ei]s\b"),
    ("meta_analysis",
     r"\bmeta[-\s]?analys[ei]s\b[^.;?]{0,40}?\b(?:was|were|is|are)\s+"
     r"(?:conducted|performed|carried\s+out|undertaken|reported)\b"),
    ("meta_analysis", r"\bthis\s+meta[-\s]?analysis\b"),
    ("systematic_review",
     r"\b(?:conduct|perform|carr(?:y|ied)|undert(?:ook|ake|aken)|report|present)"
     r"\w*\b[^.;?]{0,40}?\bsystematic\s+review\b"),
    ("systematic_review",
     r"\bsystematic\s+review\b[^.;?]{0,40}?\b(?:was|were|is|are)\s+"
     r"(?:conducted|performed|carried\s+out|undertaken|reported)\b"),
    ("systematic_review", r"\bthis\s+systematic\s+review\b"),
    ("systematic_review", r"\b(?:following|according\s+to|in\s+accordance\s+with)\s+PRISMA\b"),
    ("narrative_review", r"\bthis\s+(?:narrative\s+)?review\s+(?:summari[sz]es|discusses|examines|provides\s+an\s+overview)\b"),
)

#: A meta-analysis is a KIND of systematic review often enough that matching
#: both should report the more specific one.
_PRECEDENCE = ("meta_analysis", "systematic_review", "narrative_review")

#: Clause boundaries, so a verdict about one mention is not read off a
#: neighbouring sentence. Same device as `artefacts._clause_around` and
#: `supplements.mention_context`. `?` is an edge here because a question-form
#: title ("Do meta-analyses overestimate...? A randomised trial") puts the
#: paper's own design in the clause AFTER the question mark.
_CLAUSE_EDGE = re.compile(r"[.;?]")

#: THE JUDGE for a mention in running text. A POSITIVE requirement: the clause
#: must attribute the design to THIS paper. Deliberately not a list of the ways
#: a paper can refer to someone else's work -- a closed list of negations is
#: what failed in `artefacts.preregistration`, because the ways to say "not us"
#: do not enumerate. Requiring the self-reference instead means an unrecognised
#: phrasing FAILS TO FIRE rather than firing wrongly, and that is the direction
#: to fail in: a false fire prints "this toolkit does not apply to this paper"
#: as the first thing a reader sees.
_SELF_ANCHOR = re.compile(
    r"\b(?:we|our|us)\b|"
    r"\bthis\s+(?:study|paper|article|work|review|analysis|synthesis|report|"
    r"meta[-\s]?analysis)\b|"
    r"\bthe\s+(?:present|current)\s+(?:study|paper|article|work|review|"
    r"analysis|meta[-\s]?analysis|synthesis)\b|"
    r"\bhere\s+we\b", re.I)

#: Checked EVEN WHEN a self-anchor is present, because "this review" can be
#: anaphora to a work just cited: "This systematic review by Olds et al.
#: summarised earlier findings; here we report our own cohort." The anchor
#: alone cannot tell self-reference from anaphora; an attribution can.
_ATTRIBUTED_ELSEWHERE = re.compile(
    r"\bet\s+al\b|"
    r"\b(?:previous|prior|earlier|recent|recently|published|existing)\b|"
    r"\b(?:have|has|had)\s+(?:been\s+)?"
    r"(?:reported|shown|found|published|conducted|demonstrated|suggested)\b|"
    r"\b(?:several|numerous|many)\s+(?:\w+\s+){0,2}"
    r"(?:reviews?|meta[-\s]?analyses|studies|trials)\b|"
    r"\b(?:reported|described|conducted|performed)\s+by\b", re.I)

#: A title that ALSO names a primary empirical design is describing the study it
#: reports. The review keyword in such a title is its subject matter.
_PRIMARY_DESIGN = re.compile(
    r"\brandomi[sz]ed\b|\bRCT\b|"
    r"\b(?:double|single|triple)[-\s]blind(?:ed)?\b|"
    r"\bplacebo[-\s]controlled\b|"
    r"\b(?:cohort|case[-\s]control|cross[-\s]sectional|longitudinal)\s+"
    r"stud(?:y|ies)\b|"
    r"\bclinical\s+trial\b|\bpilot\s+stud(?:y|ies)\b", re.I)

#: ...UNLESS the design phrase is what the review is a review OF. "A systematic
#: review and meta-analysis of randomised controlled trials" is a meta-analysis;
#: the trials are its material, not its design. Without this the contradiction
#: rule would suppress the check on most medical meta-analyses, which is the
#: population it exists for.
_REVIEW_MATERIAL = re.compile(
    r"\b(?:of|from|among|across|including|in)\s+(?:the\s+)?$", re.I)


def _clause_around(text: str, start: int, end: int, window: int = 120) -> str:
    """The clause a match sits in -- bounded by `.`, `;` or `?`, not distance."""
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


def _names_its_own_primary_design(title: str) -> str | None:
    """The primary design this TITLE claims for itself, or None.

    A design named as the review's material ("meta-analysis OF randomised
    trials") is not a design claim, so it does not count.
    """
    for m in _PRIMARY_DESIGN.finditer(title or ""):
        before = (title or "")[:m.start()]
        if _REVIEW_MATERIAL.search(before):
            continue
        return m.group(0)
    return None


def _mention_is_self_description(text: str, start: int, end: int) -> bool:
    """Does the clause holding this match claim the design for THIS paper?"""
    clause = _clause_around(text, start, end)
    if not _SELF_ANCHOR.search(clause):
        return False
    return not _ATTRIBUTED_ELSEWHERE.search(clause)


def classify_document(title: str | None = None,
                      text: str | None = None) -> dict[str, Any]:
    """Does this document describe ITSELF as a review or meta-analysis?

    Returns `{"kind": str|None, "confidence": "high"|"medium", "evidence": [...],
    "stance": str, "why": str, "notice": str}`. `kind` None means "nothing said
    it was one", which is not the same as "it is primary research" -- this reads
    two fields, not the paper.

    `text` was called `abstract`, and the patterns were written on the promise
    that they would only ever see one. The sole caller (agent.py) has always
    passed the first 4000 characters of the BODY, which is the abstract plus the
    opening of the introduction -- i.e. precisely where a primary study cites the
    prior literature. Rather than restate a promise the codebase does not keep,
    every mention is now judged in its own clause, which makes the distinction
    between abstract and body text stop mattering.
    """
    hits: list[tuple[str, str, str]] = []   # (kind, where, matched text)
    t = " ".join(str(title or "").split())
    a = " ".join(str(text or "").split())

    # A title names the paper's own design UNLESS the same title also names a
    # primary empirical design it is not the material of -- then the review word
    # is the subject matter.
    own_design = _names_its_own_primary_design(t)
    for kind, pat in _TITLE_PATTERNS:
        m = re.search(pat, t, re.I)
        if m and not own_design:
            hits.append((kind, "title", m.group(0)))

    # Every match in running text must claim the design for THIS paper, in the
    # clause it sits in. `finditer`, not `search`: the first mention of a review
    # is routinely a citation, and stopping there missed the paper's own
    # self-description later in the same passage.
    for kind, pat in _ABSTRACT_PATTERNS:
        for m in re.finditer(pat, a, re.I):
            if _mention_is_self_description(a, m.start(), m.end()):
                hits.append((kind, "abstract", m.group(0)))
                break
    if not hits:
        return {"kind": None, "confidence": None, "evidence": [], "stance": "",
                "why": "", "notice": ""}

    kinds = {h[0] for h in hits}
    kind = next(k for k in _PRECEDENCE if k in kinds)
    # A title match is the paper naming itself. An abstract-only match is weaker.
    confidence = "high" if any(h[1] == "title" for h in hits if h[0] == kind) else "medium"
    spec = OUT_OF_SCOPE[kind]
    notice = (
        f"**This document describes itself as {spec['label']}, which is "
        f"{spec['stance']} for this toolkit.** {spec['why']}"
    )
    return {"kind": kind, "confidence": confidence,
            "evidence": [{"where": w, "matched": m} for k, w, m in hits if k == kind],
            "stance": spec["stance"], "why": spec["why"], "notice": notice}


#: The archive is LARGER than the classification, and saying so is the point.
#: 36 run records over 19 `paper_id`s, three of which are blinded placeholders.
#: The hand classification below covers the runs whose reports were read
#: (25 runs, 16 identifiable papers); the rest are re-runs and blinded runs of
#: the same material. Quoting 36 against a table that sums to 25 would be the
#: same defect this project keeps catching elsewhere -- a denominator that does
#: not match the thing it is a denominator for.
#: CORRECTED 2026-08-11 from 36 to 34. The 36 counted two bundles I had built
#: into `scratchpad/` earlier the same day -- scratch is not the archive, and
#: this is the denominator-drift defect committed in the very module that
#: exists to state a denominator honestly. Caught by this module's own test.
#: CORRECTED AGAIN 2026-08-11, 37 -> 35, while merging the recalibration
#: branch: the archive holds 35 non-scratchpad `run_meta.json` files and the
#: constant claimed 37. The overstatement survived on its own branch because
#: `test_scope` resolves the archive relative to the checkout, and a checkout
#: living under a `scratchpad/` path filters every run out and SKIPS -- so the
#: assertion only really runs in the primary tree. Same drift, same catch.
ARCHIVE_RUNS = 35
ARCHIVE_PAPER_IDS = 19
CLASSIFIED_PAPERS = 16


def classified_runs() -> int:
    """Runs covered by the hand classification. Derived, never written twice."""
    return sum(c for _, c, _ in TESTED_ON)


def tested_on_sentence() -> str:
    """One line naming the evidence base, for a place that has room for one."""
    return (f"Tested on {ARCHIVE_RUNS} runs over {ARCHIVE_PAPER_IDS} papers "
            f"({classified_runs()} runs over {CLASSIFIED_PAPERS} papers "
            "classified by design), almost all of them primary biomedical or "
            "psychology research and most of them human randomised trials. No "
            "qualitative, bench-science, -omics or non-biomedical paper has ever "
            "been through it.")


def scope_markdown() -> list[str]:
    """The scope statement as markdown lines, for the report's closing section."""
    out = ["## What this has been tested on", "",
           "The checks in this report were built and calibrated against a small "
           "corpus. Naming it is not modesty -- it is the denominator you need "
           "in order to know how much of it to believe for YOUR paper.", "",
           f"The archive holds **{ARCHIVE_RUNS} runs over {ARCHIVE_PAPER_IDS} "
           f"papers** (three of them blinded). Of those, {classified_runs()} "
           f"runs on {CLASSIFIED_PAPERS} identifiable papers have been "
           "classified by design, by reading the reports:", ""]
    for label, n, detail in TESTED_ON:
        out.append(f"- {label} -- {n} run{'s' if n != 1 else ''} ({detail})")
    out += ["", "**Designs with no representation at all.** Nothing resembling "
            "these has ever been through this pipeline, so no claim here about "
            "its accuracy transfers to them:", ""]
    for f in NOT_TESTED:
        out.append(f"- {f}")
    out += ["", "**Document kinds this is not the instrument for:**", ""]
    for spec in OUT_OF_SCOPE.values():
        out.append(f"- **{spec['label'].capitalize()}** -- {spec['stance']}. {spec['why']}")
    out.append("")
    return out
