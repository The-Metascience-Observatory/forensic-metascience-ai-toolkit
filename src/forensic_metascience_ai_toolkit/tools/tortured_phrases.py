"""
Tortured-phrases screen: does this paper's PROSE carry paraphrase-tool or
undisclosed-LLM fingerprints?

Dictionary matching only (the Problematic Paper Screener method): the engine
in `phrasebook.py` reports verbatim matches of a versioned fingerprint
dictionary -- tortured phrases ("counterfeit consciousness" for "artificial
intelligence"), LLM boilerplate ("as an AI language model"), and tortured
acronym expansions. ML alternatives were considered and rejected: the best
published detector (SciBERT masked-token) reaches precision 0.615, which is
triage, not accusation grade. A curated fingerprint hit asserts exactly one
thing -- THE PHRASE APPEARS -- and the inference from appearance to
paraphrasing-tool use is probabilistic, which caps this tool's evidence class.

THE COUNT THAT DRIVES SEVERITY IS k: distinct canonical fingerprints whose
matches survive every guard. Total occurrences are recorded separately and
never thresholded -- one phrase pasted twenty times is ONE substitution event
(the raw-duplication "39% of rows" counting lesson). Guards, each recorded on
the match it suppresses (`suppressed_by`), never silently dropping anything:

  * references section -- a tortured phrase in a CITED title indicts the
    cited paper, not this one (sleuths legitimately cite retracted tortured
    papers). Recorded with `section="references"`, excluded from k.
  * quotation -- `in_quotation` has THREE states: true / false / "unknown"
    (the extracted text carries no quote glyphs at all, so quotation detection
    is blind). Only `true` suppresses; `unknown` is stated, not acted on.
    Single-quote quoting is NOT detected (apostrophes drown it) -- that gap
    belongs to stage 2's rule-14 duty to eyeball the quoted span.
  * metadiscussion -- a paper ABOUT tortured phrases / paper mills quotes its
    specimens; flagging it accuses the fire brigade of arson. Two or more
    distinct lexicon terms => every match context-flagged, excluded from k.
  * LLM-topic context -- post-2023 NLP papers quote "as an AI language model"
    legitimately. Boilerplate severity drops one tier, with a named caveat.
  * ambiguity -- `ambiguity=high` fingerprints (defensible legitimate reading
    in some field) are reported but NEVER count toward k.
  * extraction risk -- a match that exists only under the linebreak-hyphen
    join is marked `extraction_risk`; if a severity threshold is crossed ONLY
    by such matches, the lower tier is kept and the caveat says so.

OCR-derived text never reaches this tool: `paper_text` reads body.md /
publisher XML / HTML / the PDF's own text layer, and no OCR engine feeds any
of those channels. If that ever changes, OCR text must not contribute to k
(the `ocr_table` provenance invariant, ported to prose).

SEVERITY is pre-registered ahead of calibration and hard-capped at
`highly_suspicious` -- awkward language violates no mathematics, so
`impossible` is UNREACHABLE (rulebook rules 3, 9, 11 logic):
  * tortured phrases (incl. dictionary-listed acronym expansions):
    k=1 -> indeterminate (permanently), k=2 -> suspicious,
    k>=3 -> highly_suspicious;
  * LLM boilerplate, `first_person_disclaimer`: one guarded hit ->
    highly_suspicious; other subclasses: 1 distinct -> suspicious,
    >=2 distinct -> highly_suspicious; one tier lower when the paper
    discusses LLMs.

THE RESULT SHIPS QUARANTINED (`tools/quarantine.py`): computed statistics
visible, accusation withheld, the pre-registered grade preserved in
`severity_before_quarantine`. Release is a one-line deletion of the
`quarantine(...)` call plus updating its test, and requires ALL of the
pre-registered gates measured by `examples/calibrate_tortured_phrases.py`
(deleted 2026-10-16 with examples/; recover it from git history):
  * paper-level k>=1 rate <= 2% on the presumed-clean corpus, with EVERY
    fired paper hand-checked;
  * ZERO extraction-artifact and ZERO references-leak matches among the
    hand-checked fires (those are pipeline bugs -- fix, don't tolerate);
  * no `ambiguity=low` fingerprint firing on > 0.5% of clean papers;
  * recall >= 80% at k>=2 on the known-positive (PPS-flagged) set.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from ..phrasebook import (
    Match,
    Phrasebook,
    PhrasebookError,
    context_snippet,
    load_phrasebook,
    scan_text,
    tokenize,
)
from .quarantine import quarantine
from .severity import (
    CONSISTENT,
    HIGHLY_SUSPICIOUS,
    INDETERMINATE,
    SUSPICIOUS,
)

_METHODOLOGY = (
    "Local computation only -- no network, no model. Dictionary fingerprint "
    "matching (case/hyphenation/ligature/plural-folded token match) over the "
    "paper's extracted text; references-section matches recorded but excluded "
    "from severity. A hit asserts the phrase appears -- the inference to "
    "paraphrase-tool or undisclosed-LLM use is probabilistic. Coverage is the "
    "dictionary's (skewed CS/engineering/biomedical): a clean result on an "
    "out-of-field or non-English paper is weak clearance."
)

_QUARANTINE_REASON = (
    "The tortured-phrases screen is newly added: its false-positive classes "
    "(extraction artifacts, quotation, field-legitimate phrasing) have not "
    "been measured on this pipeline's own corpora, so it may not accuse yet. "
    "The pre-registered grade is preserved in severity_before_quarantine; "
    "release gates live in this tool's module docstring, measured by "
    "calibrate_tortured_phrases.py (removed from examples/; in git history)."
)

#: Section heading that starts the bibliography. `paper_text`'s two richest
#: sources (markdown files, XML render) both emit a literal `# References`
#: heading; the PDF text-layer fallback usually has none, and that blindness
#: is announced via the `references_not_delimited` caveat.
_REFS_HEADING = re.compile(
    r"^\s{0,3}#{0,6}\s*(?:references|bibliography|literature\s+cited|"
    r"works\s+cited)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE)

#: >=2 distinct terms => the paper DISCUSSES the phenomenon and quotes its
#: specimens; matches are context-flagged, never counted.
_METADISCUSSION_TERMS = (
    "tortured phrase", "tortured phrases", "paper mill", "paper mills",
    "problematic paper screener", "paraphrasing tool", "paraphrase tool",
    "spinbot", "retraction watch", "research integrity",
    "plagiarism detection", "scientific sleuth",
)

#: >=3 distinct terms => the paper discusses LLMs; boilerplate quotes are
#: plausible, so boilerplate severity drops one tier (named caveat).
_LLM_TOPIC_TERMS = (
    r"chatgpt", r"gpt-[345]", r"\bllms?\b", r"large language model",
    r"language models", r"prompt engineering", r"openai", r"generative ai",
    r"foundation model",
)

#: Opening/closing glyphs that mark quoted material. Straight double quote,
#: curly doubles, guillemets, low-9. Single quotes are deliberately absent.
_QUOTE_GLYPHS = "\"“”«»„"

_RANK = {CONSISTENT: 0, INDETERMINATE: 1, SUSPICIOUS: 2, HIGHLY_SUSPICIOUS: 3}
_BY_RANK = {v: k for k, v in _RANK.items()}


def _max_severity(*sevs: str) -> str:
    return _BY_RANK[max(_RANK[s] for s in sevs)]


def _drop_tier(sev: str) -> str:
    return _BY_RANK[max(0, _RANK[sev] - 1)]


def _phrase_ladder(k: int) -> str:
    if k >= 3:
        return HIGHLY_SUSPICIOUS
    if k == 2:
        return SUSPICIOUS
    if k == 1:
        return INDETERMINATE  # permanently: one hit is a pointer for review
    return CONSISTENT


def _references_cut(text: str) -> Optional[int]:
    """Char offset where the references section begins, or None.

    The LAST heading-like match in the final two-thirds of the text. A
    mid-document heading (before appendices) over-marks the tail, which
    UNDER-counts -- the safe direction, and the caveat says so.
    """
    cut = None
    for m in _REFS_HEADING.finditer(text):
        if m.start() >= len(text) // 3:
            cut = m.start()
    return cut


def _in_quotation(text: str, start: int, end: int,
                  text_has_quotes: bool) -> bool | str:
    """Three states: True / False / "unknown" (no quote glyphs anywhere, so
    the extraction lost them and detection is blind)."""
    if not text_has_quotes:
        return "unknown"
    before = text[max(0, start - 2):start].strip()
    after = text[end:end + 2].strip()
    return bool(before and before[-1] in _QUOTE_GLYPHS
                and after and after[0] in _QUOTE_GLYPHS)


def _acronym_present(text: str, end: int, acronym: str) -> bool:
    """`(<acronym>)` within 15 chars after the matched expansion."""
    if not acronym:
        return False
    window = text[end:end + 15 + len(acronym)]
    return bool(re.search(r"\(\s*" + re.escape(acronym) + r"\s*\)",
                          window, re.IGNORECASE))


def _distinct_terms_present(text_lower: str, terms: tuple[str, ...],
                            regex: bool) -> list[str]:
    found = []
    for term in terms:
        if regex:
            if re.search(term, text_lower):
                found.append(term)
        elif term in text_lower:
            found.append(term)
    return found


def _match_record(m: Match, text: str, cut: Optional[int],
                  text_has_quotes: bool) -> dict[str, Any]:
    fp = m.fingerprint
    section = "references" if cut is not None and m.start >= cut else "body"
    return {
        "family": fp.family,
        "subclass": fp.subclass or None,
        "matched_text": m.matched_text,
        "fingerprint": fp.tortured,
        "expected": fp.expected or None,
        "sources": list(fp.sources),
        "start": m.start,
        "end": m.end,
        "context": context_snippet(text, m.start, m.end),
        "section": section,
        "variant": m.variant,
        "extraction_risk": m.variant == "line_hyphenation",
        "in_quotation": _in_quotation(text, m.start, m.end, text_has_quotes),
        "ambiguity": fp.ambiguity,
        "acronym_present": (_acronym_present(text, m.end, fp.acronym)
                            if fp.family == "tortured_acronym" else None),
        "suppressed_by": None,  # filled by the guard pass
    }


def detect_tortured_phrases(paper_dir: str | None = None,
                            text: str | None = None,
                            data_dir: str | None = None) -> dict[str, Any]:
    """Screen a paper directory (or raw text) for fingerprint matches.

    Exactly one of `paper_dir` / `text`. Refusals carry NO counting keys at
    all (`artefacts.find_in_paper` precedent): an unread paper must not
    impersonate a clean one.
    """
    try:
        book = load_phrasebook(data_dir)
    except PhrasebookError as exc:
        return {
            "success": False,
            "severity": INDETERMINATE,
            "refusal": "dictionary_missing",
            "error": str(exc),
            "explanation": (
                "The fingerprint dictionary could not be loaded, so NOTHING "
                "was screened. This is a property of the installation and "
                "says nothing about the paper."),
            "methodology": _METHODOLOGY,
        }

    text_source: Optional[str] = None
    if text is None:
        if paper_dir is None:
            return _refuse(book, "no_text_source",
                           "neither paper_dir nor text was provided")
        pd = Path(paper_dir)
        if not pd.is_dir():
            return _refuse(book, "no_text_source",
                           f"paper directory not found: {pd}")
        has_candidates = ((pd / "body.md").exists()
                          or any(pd.glob("*.xml")) or any(pd.glob("*.html"))
                          or any(pd.glob("*.pdf")))
        from ..extraction.jats import paper_text_with_source
        text, text_source = paper_text_with_source(pd)
        if not text.strip():
            subtype = "text_unreadable" if has_candidates else "no_text_source"
            return _refuse(
                book, subtype,
                "NO TEXT COULD BE READ from this paper -- no body.md, no "
                "parseable XML/HTML, no usable PDF text layer (the shape of "
                "a scanned, never-OCR'd or corrupt file). Whether its prose "
                "carries fingerprints is UNKNOWN, not clean."
                if has_candidates else
                "the paper directory contains no text-bearing source at all "
                "(no body.md, XML, HTML or PDF); the screen has nothing to "
                "read and nothing is cleared.")
    elif not text.strip():
        return _refuse(book, "text_unreadable", "empty text was provided")

    cut = _references_cut(text)
    text_lower = text.lower()
    body_lower = text_lower if cut is None else text_lower[:cut]
    text_has_quotes = any(g in text for g in _QUOTE_GLYPHS)

    meta_terms = _distinct_terms_present(text_lower, _METADISCUSSION_TERMS,
                                         regex=False)
    metadiscussion = len(meta_terms) >= 2
    llm_terms = _distinct_terms_present(body_lower, _LLM_TOPIC_TERMS,
                                        regex=True)
    discusses_llms = len(llm_terms) >= 3

    records = [_match_record(m, text, cut, text_has_quotes)
               for m in scan_text(text, book)]

    # ---- Guard pass: mark, never drop --------------------------------------
    for r in records:
        if r["section"] == "references":
            r["suppressed_by"] = "references_section"
        elif metadiscussion:
            r["suppressed_by"] = "metadiscussion"
        elif r["in_quotation"] is True:
            r["suppressed_by"] = "quotation"
        elif r["ambiguity"] == "high":
            r["suppressed_by"] = "ambiguous_fingerprint"

    def _guarded(r: dict) -> bool:
        return r["suppressed_by"] is None

    phrase_like = [r for r in records if _guarded(r)
                   and r["family"] in ("tortured_phrase", "tortured_acronym")]
    boiler = [r for r in records if _guarded(r)
              and r["family"] == "llm_boilerplate"]

    k_fps = {r["fingerprint"] for r in phrase_like}
    k = len(k_fps)
    k_solid = len({r["fingerprint"] for r in phrase_like
                   if not r["extraction_risk"]})

    caveats: list[str] = []
    sev_phrases = _phrase_ladder(k)
    if _RANK[sev_phrases] > _RANK[_phrase_ladder(k_solid)]:
        sev_phrases = _phrase_ladder(k_solid)
        caveats.append(
            f"the k={k} severity threshold is crossed only via matches that "
            "span a line-break hyphenation (extraction_risk); severity is "
            f"held at the k={k_solid} tier until a human confirms those "
            "spans against the source document.")

    disclaimers = {r["fingerprint"] for r in boiler
                   if r["subclass"] == "first_person_disclaimer"}
    other_boiler = {r["fingerprint"] for r in boiler
                    if r["subclass"] != "first_person_disclaimer"}
    if disclaimers:
        sev_boiler = HIGHLY_SUSPICIOUS
    elif len(other_boiler) >= 2:
        sev_boiler = HIGHLY_SUSPICIOUS
    elif len(other_boiler) == 1:
        sev_boiler = SUSPICIOUS
    else:
        sev_boiler = CONSISTENT
    if discusses_llms and _RANK[sev_boiler] > _RANK[INDETERMINATE]:
        sev_boiler = _drop_tier(sev_boiler)
        caveats.append(
            "this paper discusses LLMs "
            f"(topic terms: {', '.join(llm_terms)}), so quoted boilerplate "
            "is plausible; the boilerplate severity was dropped one tier and "
            "the authors'-own-voice judgement belongs to a human reader.")

    severity = _max_severity(sev_phrases, sev_boiler)

    if metadiscussion and records:
        caveats.append(
            "this paper appears to DISCUSS tortured phrases / paper mills "
            f"(lexicon terms: {', '.join(meta_terms)}); all matches were "
            "context-flagged and excluded from k -- a paper about the "
            "phenomenon quotes its specimens.")
    if cut is None:
        caveats.append(
            "references_not_delimited: no references heading was found, so "
            "bibliography text was scanned as body; a fingerprint appearing "
            "only in a cited title could inflate the count (it did not "
            "affect zero-match results).")
    if severity == CONSISTENT:
        caveats.append(
            "a null result is coverage-bounded: the dictionary lists KNOWN "
            "fingerprints with a CS/engineering/biomedical skew; absence of "
            "matches is not evidence the text is human-written.")

    n_body = sum(1 for r in records if r["section"] == "body")
    n_refs = len(records) - n_body
    n_body_words = len(tokenize(text if cut is None else text[:cut]))
    per_family: dict[str, dict[str, int]] = {}
    for r in records:
        fam = per_family.setdefault(r["family"],
                                    {"n_matches": 0, "n_distinct": 0})
        fam["n_matches"] += 1
    for fam_name, fam in per_family.items():
        fam["n_distinct"] = len({r["fingerprint"] for r in records
                                 if r["family"] == fam_name})

    strongest = max(per_family, key=lambda f: per_family[f]["n_matches"],
                    default=None) if per_family else None
    if not records:
        explanation = (
            f"No fingerprint matches in {n_body_words} words scanned "
            f"against {book.n_fingerprints} fingerprints "
            f"(dictionary {book.version}).")
    else:
        n_suppressed = sum(1 for r in records if r["suppressed_by"])
        explanation = (
            f"{k} distinct guarded fingerprint(s) across {len(records)} "
            f"match(es) ({n_refs} in references, {n_suppressed} suppressed "
            f"by guards); strongest family: {strongest}.")

    result: dict[str, Any] = {
        "success": True,
        "severity": severity,
        "consistent": severity == CONSISTENT,
        "matches": records,
        # DISTINCT counting keys, never interchanged:
        "n_matches": len(records),
        "n_matches_body": n_body,
        "n_matches_references": n_refs,
        "n_distinct_fingerprints": k,
        "n_distinct_fingerprints_solid": k_solid,
        "per_family": per_family,
        "n_words_scanned": n_body_words,
        "density_per_10k_words": (round(n_body / n_body_words * 10000, 2)
                                  if n_body_words else 0.0),
        "references_delimited": cut is not None,
        # Pre-quarantine grade per ladder (acronym expansions ride the phrase
        # ladder); the text track shapes one findings row per family and needs
        # each family's own grade, not only the max.
        "severity_raw_by_family": {"tortured_phrase": sev_phrases,
                                   "llm_boilerplate": sev_boiler},
        "paper_discusses_llms": discusses_llms,
        "metadiscussion_context": metadiscussion,
        "text_source": text_source,
        "dictionary": book.dictionary_block(),
        "caveats": caveats,
        "explanation": explanation,
        "methodology": _METHODOLOGY,
    }
    return quarantine(result, _QUARANTINE_REASON)


def _refuse(book: Phrasebook, subtype: str, detail: str) -> dict[str, Any]:
    return {
        "success": False,
        "severity": INDETERMINATE,
        "refusal": subtype,
        "error": detail,
        "text_available": False,
        "dictionary": book.dictionary_block(),
        "explanation": detail,
        "methodology": _METHODOLOGY,
    }
