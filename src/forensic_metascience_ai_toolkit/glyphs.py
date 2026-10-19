"""Detect extracted text whose characters are corrupt, before it is believed.

MEASURED across 400 papers. These are not typos in the papers; they are broken
`ToUnicode` CMaps in the source PDFs, and no text-layer extractor repairs them
-- pdfplumber emits `(cid:237)` on exactly the glyphs docling renders as
`GLYPH<237>`.

  +/- rendered as `6`      109 papers (35.7%)   `30.7 ( 6 4.0)` is `30.7 (±4.0)`
  `GLYPH<nnn>` unmapped     23 papers (7.5%)    9,510 occurrences
  `/C6`-style names leak    34 papers (11.1%)
  `=` rendered as `1/4`     25 papers (8.2%)    `n ¼ 68` is `n = 68`
  `<` rendered as `,`        6 papers (2.0%)    `p , 0.001` is `p < 0.001`
  space inside a number     40 papers (13.1%)

The worst case found: in one paper the embedded font maps `-` to `2` and `=` to
`5`, so a printed `-5.50 (-10.1, -0.85); P = 0.003` reaches the model as
`2 5.50 ( 2 10.1, 2 0.85); P 5 0.003`. The sign is gone and a digit has been
invented. That is the most dangerous failure this pipeline can have: a wrong
number that looks entirely plausible, on which every downstream check will
compute confidently.

The right response is to refuse to make forensic claims from such text, not to
try to repair it. A repair is a guess about what the paper said, and a guess
about a digit is exactly what we must never do.

ONE EXCEPTION, AND IT IS NOT A GUESS (1.98.0). When the damaged character is
drawn by a SYMBOL font, the PDF still holds the outline the reader sees.
`extraction.glyph_repair` identifies each such glyph by its shape against a
closed set of reference characters, refuses an ambiguous match, and logs every
edit; this scan then runs on the repaired text. Characters it refuses stay
damaged and are still reported here.
"""

from __future__ import annotations

import re
from pathlib import Path

#: (label, compiled pattern, what it means, whether it corrupts DIGITS).
#: Digit corruption is quarantine-grade on its own; the rest are reported.
_PATTERNS: tuple[tuple[str, "re.Pattern[str]", str, bool], ...] = (
    ("unmapped glyph", re.compile(r"GLYPH<\d+>"),
     "the font has no Unicode mapping for these characters; they are simply lost", False),
    ("raw CID", re.compile(r"\(cid:\d+\)"),
     "same failure seen through a different extractor", False),
    ("glyph name leak", re.compile(r"/C\d{1,3}\b"),
     "PostScript glyph names leaking into the text", False),
    # ...AND THE SAME LEAK STANDING INSIDE A NUMBER, which is a different
    # severity. The pattern above is reported and does not quarantine, which is
    # right for a glyph name in prose. Between two digits it is the `\x06` case
    # wearing the other extractor's spelling: MEASURED, `10.1007--s00702-004-
    # 0248-2` reads `65 /C6 1.17` in pdf2mdjson's `body.md` and `65 \x06 1.17`
    # in docling's cells -- one PDF, one character, two corruptions. Across the
    # 309-paper corpus it sits between numbers 233 times in 12 papers, and it is
    # a lost `±`, so a dispersion looks like a value.
    ("glyph name inside a number", re.compile(
        r"\d\s*/C\d{1,3}\b\s*\d|/C\d{1,3}\b\s*\d"),
     "a PostScript glyph name is standing inside a number or in its sign "
     "position, so an operator or a leading `-` has been lost: a dispersion "
     "reads as a separate value, or a negative effect reads as positive", True),
    # The 6 must stand ALONE between spaces: `30.7 ( 6 4.0)`. Without the
    # whitespace requirement this matched `157 (60.2)`, an ordinary n (%) cell,
    # and fired on 46 papers that were perfectly fine.
    ("plus-minus as digit 6", re.compile(r"\d\s*\(\s+6\s+\d"),
     "`±` is being rendered as the digit 6, so a dispersion looks like a value", True),
    ("equals as one-quarter", re.compile(r"\b[nNpP]\s*¼\s*\d"),
     "`=` is being rendered as `¼`, e.g. `n ¼ 68` for `n = 68`", False),
    ("less-than as comma", re.compile(r"\bp\s*,\s*\.?\d"),
     "`<` is being rendered as `,`, so `p < 0.001` reads as `p , 0.001`", False),
    ("minus as digit 2", re.compile(r"(?<![\d.])2\s+\d+\.\d+\s*\(\s*2\s*\d"),
     "the font maps `-` to `2`: a reported -5.50 reaches us as 2 5.50, with the "
     "sign gone and a digit invented", True),
    # THE SAME DEFECT REPORTED IN PROSE RATHER THAN IN A PARENTHESISED CI. The
    # pattern above was written from the single paper that exposed it, whose
    # corruption read `2 5.50 ( 2 10.1, 2 0.85)`, so it REQUIRES the bracketed
    # interval and misses the identical font failure when a paper reports inline.
    #
    # MEASURED 2026-08-13 on Kross 2013 (PLOS ONE), which prints
    # `B = 2 .006, b = 2 .059, t (73) = 1.04`: TEN statistics with the sign
    # replaced by a digit, ZERO true minus signs anywhere in the text -- and the
    # scan returned "the numbers themselves appear intact" while a paid run made
    # forensic claims from it. LESSONS #7: a guard tested only against the
    # instance that motivated it.
    #
    # ANCHORED ON `=`, with the value shaped `digit whitespace decimal`, which is
    # not a number in any legitimate rendering. The anchor is what stops a
    # flattened table row -- "Age 2 .006", two adjacent cells -- from matching.
    # MEASURED: 9 hits on Kross, 0 on the other 15 docling texts in this
    # checkout, 0 across 331 `body.md` files.
    #
    # IT DOES NOT REPLACE THE PATTERN ABOVE, and the pair was checked against
    # each other's evidence: the old one catches the original paper and not
    # Kross; this one catches Kross and not the original, where the `=` is
    # itself corrupted to a `5` and so cannot serve as an anchor.
    ("operator lost before a decimal", re.compile(r"=\s*\d\s+\.?\d"),
     "a digit stands where an operator was: `B = 2 .006` is `B = -.006` with its "
     "sign replaced, so the value reaches a check with the wrong sign or an "
     "invented leading digit", True),
    # `=` rendered as `5`: `t (10) 5 1.84, p 5 .09`. Anchored to a p/t/F or a
    # closing df parenthesis so it cannot match ordinary prose containing a 5.
    ("equals as digit 5", re.compile(r"\b[pPtF]\s+5\s+\.?\d|\)\s+5\s+\d"),
     "`=` is being rendered as the digit 5, so `p = .09` reads as `p 5 .09` and "
     "the statistic is unreadable", True),

    # A C0 CONTROL CHARACTER STANDING WHERE A CHARACTER BELONGS, between two
    # digits. Same root cause as the rest of this file -- a broken ToUnicode
    # CMap -- but it leaks the raw GLYPH INDEX instead of a name, so none of the
    # patterns above see it.
    #
    # DIGIT-CORRUPTING, and demonstrably so. In `10.1166--jnn.2011.5114` the
    # text reads `P < 0\x0605`, and `completeness._body_items` returns a
    # `p_value` whose raw is `P < 0` -- the pattern matches up to the control
    # character and stops. A reported p < 0.05 reaches the pipeline as a p of
    # ZERO, which is not a missing statistic but a WRONG one, and it is
    # impossible, so any check comparing reported against computed p can turn it
    # into an accusation against an honest paper.
    #
    # NO REPAIR IS ATTEMPTED, AND NONE IS POSSIBLE. The byte is a font-specific
    # glyph index, not an encoding: MEASURED across both corpora, `\x06` is `±`
    # in EPIVI7B3, YLHWMEJ3 and YR8VZZRJ ("mean \x06 SD", 255 occurrences, and
    # not one literal `±` in any of them) and a DECIMAL POINT in
    # 10.1166--jnn.2011.5114, which contains 471 literal `±`. The same byte,
    # two characters, decided by a font we do not have. Mapping it globally
    # would turn `P < 0\x0605` into `P < 0±05` in one paper while fixing
    # another -- inventing a digit, the one thing this file exists to refuse.
    # ...AND IN SIGN POSITION, which is the worse half and the one the first
    # cut of this pattern missed. In `7AP7MG3N` the text reads `between +0.345
    # and \x00 0.145` for a printed `−0.145`: the paper carries 1052 literal
    # `-` and ZERO unicode `−`, so the font maps the minus to glyph 0 and the
    # SIGN IS SIMPLY GONE. The same paper spells `~` as `\x18` -- `\x18 70
    # million neurons`, `\x18 21 hr` -- so an APPROXIMATE value arrives looking
    # exact, which is the difference between a number GRIM may test and one it
    # may not.
    #
    # This file's own header calls a lost minus sign "the most dangerous failure
    # this pipeline can have: a wrong number that looks entirely plausible, on
    # which every downstream check will compute confidently."
    ("control character in a number", re.compile(
        r"\d[\x00-\x08\x0b\x0c\x0e-\x1f]\d"
        r"|\d\s[\x00-\x08\x0b\x0c\x0e-\x1f]\s\d"
        r"|[\x00-\x08\x0b\x0c\x0e-\x1f]\s?\d"),
     "a raw font glyph index is standing inside a number or in its sign "
     "position, so the value is truncated, split, or has lost a leading `-` or "
     "`~`; what it should say is not recoverable from the text", True),
    # NOTE: a "space around the decimal point" pattern was tried and dropped.
    # `1.517 (0. 613-3.753)` is real corruption, but `1991. 19 We` is a
    # reference marker and `10.1186/s13293-020-00299-3 . 49` is a DOI, and the
    # three are structurally identical. It flagged 72 of 121 papers, most of
    # them wrongly. A quarantine signal that fires on half the corpus tells the
    # user nothing, so precision beats coverage here.
)

#: THE OTHER DIRECTION OF UNTRUSTWORTHY TEXT. Everything above detects a
#: corrupt TEXT LAYER. These detect a corrupt PIXEL reading -- an OCR engine or
#: vision model that invented characters -- and they belong in the same module
#: because a caller is asking one question: may I compute on this?
#:
#: MEASURED 2026-08-19 on the 22 papers whose numbers the text layer corrupts.
#: Full-page OCR cleared all 988 glyph artefacts and recovered 14% more
#: statistics, and in 6 of the 22 (27%) it invented CJK characters -- inside
#: numeric table cells. A printed `1.9 ± 0.1` came back as `1'0<CJK>61`, and
#: `11 (1 of 9)` as `(6 t 1) 11)`.
#:
#: THIS IS THE MORE DANGEROUS FAILURE OF THE TWO, and that is why it is
#: detected rather than trusted. A corrupt text layer announces itself: it
#: carries `/C6` and `\x06` that the patterns above find. Invented text looks
#: clean, so a check computes on it confidently -- the exact shape of a false
#: accusation against an honest paper.
#:
#: The engine is the cause, not the approach: docling loads `ch_ppocr_mobile`
#: and `PP-OCRv6_*_small`, Chinese-trained mobile models. Setting `lang=["en"]`
#: was accepted and produced BYTE-IDENTICAL output; disabling table structure
#: (the docling #2963 workaround) also changed nothing. Both were tested.
_OCR_HALLUCINATION: tuple[tuple[str, "re.Pattern[str]", str], ...] = (
    ("CJK in a latin document", re.compile("[\u3000-\u9fff\uac00-\ud7af]"),
     "Chinese/Japanese/Korean characters in a document that has none, which is "
     "a recogniser inventing glyphs rather than reading them"),
    ("quote inside a number", re.compile("\\d[\u2019'`]\\d"),
     "a quote mark between two digits, which no printed number contains"),
    ("digits split by a letter", re.compile(r"\(\d+ [a-z] \d+\)"),
     "a lone letter between digits inside brackets, the shape a misread table "
     "cell takes"),
)


def ocr_trust(text: str, *, compare_with: str | None = None) -> dict:
    """Whether a PIXEL reading may be computed on, or must be refused.

    Returns `usable`; see the note on the return value for why not the other
    word.

    `compare_with` is the text-layer reading of the same document, when there is
    one. It is used ONLY to establish that a marker is new: a paper that really
    does contain CJK is not evidence of hallucination, and the text layer is how
    we know which it is. Without it every marker is reported as unverified,
    because absence of a comparison is not absence of a problem.

    MEASURED over the 22 damaged papers: 16 come back clean and are strictly
    better than their text layer; 6 are refused. That is the gate, and it is
    per-document for the same reason the glyph repairs are -- what one paper
    proves says nothing about the next.
    """
    text = text or ""
    found = []
    for label, pat, means in _OCR_HALLUCINATION:
        n_new = len(pat.findall(text))
        if not n_new:
            continue
        n_old = len(pat.findall(compare_with)) if compare_with is not None else None
        if n_old:
            # The document legitimately contains this. Not our invention.
            continue
        found.append({"marker": label, "count": n_new, "means": means,
                      "verified_against_text_layer": compare_with is not None})
    # `usable`, NOT `trustworthy`. That word is a RETIRED VERDICT here --
    # `verdicts.RETIRED` holds ("trustworthy", "questionable", "untrustworthy")
    # because they are accusatory judgements about a PAPER, and
    # `test_verdict_vocabulary` forbids any module from spelling one as a key.
    # My first cut used it and the guard caught it. The rename is also more
    # accurate: this judges OUR reading of the page, never the authors' work.
    return {
        "usable": not found,
        "markers": found,
        "note": ("This reading invented characters and must not be computed on; "
                 "fall back to the text layer, which is corrupt but ANNOUNCES "
                 "that it is." if found else
                 "No invented-character markers. This is not a guarantee of "
                 "accuracy -- it is the absence of the failures we can detect."),
    }


#: Occurrences below this are treated as incidental rather than systemic.
_NOISE_FLOOR = 3


def scan(text: str) -> dict:
    """Report character-level corruption in extracted text.

    `quarantine` is True when corruption touches DIGITS, because that is the
    case where a check computes confidently on a number the paper never
    printed.
    """
    text = text or ""
    hits: list[dict] = []
    quarantine = False
    for label, pattern, meaning, corrupts_digits in _PATTERNS:
        found = pattern.findall(text)
        if len(found) < _NOISE_FLOOR:
            continue
        examples = []
        for m in pattern.finditer(text):
            s = max(0, m.start() - 25)
            examples.append(re.sub(r"\s+", " ", text[s:m.end() + 25]).strip())
            if len(examples) >= 3:
                break
        hits.append({
            "pattern": label, "count": len(found), "means": meaning,
            "corrupts_digits": corrupts_digits, "examples": examples,
        })
        quarantine = quarantine or corrupts_digits

    if not hits:
        note = "No character-level corruption detected in the extracted text."
    elif quarantine:
        worst = ", ".join(h["pattern"] for h in hits if h["corrupts_digits"])
        note = (
            "The extracted text is CHARACTER-CORRUPT in a way that affects DIGITS "
            f"({worst}). A number that reaches a check wrong -- a lost minus sign, a "
            "`±` read as a 6 -- produces a confident finding about a value the "
            "paper never printed. This is a defect in the source PDF's font "
            "encoding, not in the paper's statistics, and no extractor repairs it. "
            "Forensic claims from this text are not reliable and should be checked "
            "against the PDF by eye."
        )
    else:
        note = (
            "The extracted text contains character-level corruption, but not in the "
            "digits. Symbols and operators may be wrong; the numbers themselves "
            "appear intact."
        )

    return {
        "clean": not hits,
        "quarantine": quarantine,
        "patterns": hits,
        "total_occurrences": sum(h["count"] for h in hits),
        "note": note,
    }


def scan_paper(paper_dir: str | Path) -> dict:
    """Scan a paper directory's extracted text.

    NO TEXT MEANS UNKNOWN, NOT CLEAN. `paper_text` returns "" for three
    different reasons -- the paper is a scan with no OCR layer, the PDF is
    corrupt and extraction raised, or no source file was found -- and all
    three used to be handed to `scan`, which then correctly reported that it
    found no corrupt glyphs in the empty string: `clean: True`.

    MEASURED on a corpus PDF whose every extraction path crashes with
    "Unexpected EOF", this returned "No character-level corruption detected in
    the extracted text." A corruption scanner reporting CLEAN on a file it
    could not read is the purest form of the failure this toolkit exists to
    prevent, and unlike a missed finding it is a POSITIVE claim that can be
    quoted back as reassurance. `supplements.audit` already fails closed on
    the same input; this now matches it.
    """
    from .extraction.jats import paper_text

    paper_dir = Path(paper_dir)
    # Falls back to the XML full text when body.md is absent.
    text = paper_text(paper_dir)
    if not text.strip():
        return {
            "clean": False,
            "quarantine": False,
            "text_available": False,
            "patterns": [],
            "total_occurrences": 0,
            "note": (
                "NO TEXT COULD BE READ from this paper, so whether its "
                "characters are corrupt is UNKNOWN. This is not a clean "
                "result. There is no body.md, no parseable XML and no usable "
                "PDF text layer -- which is what a scan that was never OCR'd "
                "looks like, and also what a corrupt download looks like. The "
                "absence of detected corruption here is a fact about this "
                "extraction and must not be reported as one about the paper."
            ),
        }
    out = scan(text)
    out["text_available"] = True
    return out


#: `mean ± SD`, `median ± SEM` -- the glyph sitting between two WORDS, where no
#: digit is at stake and only `±` reads. This is the proof, and it is textual.
_PM_ANCHOR = re.compile(
    r"(?i)\b(?:mean|median|average|sd|sem?|se)\s*\x06\s*(?:sd|sem?|se|mean)\b")


#: The SAME character, leaked by a different extractor. Docling emits the raw
#: glyph index (`\x06`); pdf2mdjson emits the PostScript glyph NAME (`/C6`).
#: MEASURED on `10.1007--s00702-004-0248-2`, whose two extractions of one PDF
#: disagree: `body.md` reads `65 /C6 1.17` and the docling cells read
#: `65 \x06 1.17`.
_NAMED_PM_ANCHOR = re.compile(
    r"(?i)\b(?:mean|median|average|sd|sem?|se)\s*(/C\d{1,3})\b\s*"
    r"(?:sd|sem?|se|mean)\b")


def proven_repairs(text: str) -> dict[str, str]:
    """Character repairs this ONE document proves, or nothing.

    Greg asked whether extraction artefacts could just be replaced with the
    right operator. For entities (`&lt;`) they can, because the mapping is the
    standard's. For a raw control character they CANNOT be replaced globally,
    and this function exists to say exactly when they may be replaced locally.

    MEASURED across both corpora, `\\x06` is TWO different characters:

        EPIVI7B3    226 occurrences   0 literal `±`   40 `mean \\x06 SD`  -> `±`
        YR8VZZRJ     23               0                1                 -> `±`
        YLHWMEJ3     50               0                0                 -> unproven
        jnn.2011.5114 21            471                0                 -> NOT `±`

    It is a font-specific GLYPH INDEX, not an encoding. In
    `10.1166--jnn.2011.5114` it is a DECIMAL POINT -- `P < 0\\x0605` is
    `P < 0.05` -- and that paper prints 471 literal `±`, so it cannot also be
    spelling `±` this way. Mapping the byte globally would repair two papers and
    corrupt a third, inventing digits in the process.

    SO THE EVIDENCE MUST COME FROM THE DOCUMENT ITSELF, and it must be textual:

      1. The document contains `mean \\x06 SD` or a sibling -- the glyph between
         two WORDS, where no digit is at stake and only `±` reads sensibly.
      2. The document contains NO literal `±`. A paper that can print the
         character is not also spelling it as a control code, and this is the
         condition that rules the counterexample out.

    Both, or nothing. `YLHWMEJ3` has 50 occurrences that are very probably `±`
    and no anchor to prove it, so it gets no repair -- a guess about a digit is
    the one thing this module refuses, and being nearly sure is still a guess.

    The repair is LENGTH-PRESERVING (one character for one), so offsets taken
    against the repaired string remain offsets into the original.
    """
    text = text or ""
    if "±" in text:
        # A paper that can print the character is not also encoding it. This is
        # the condition that rules out `10.1166--jnn.2011.5114`, where `\x06`
        # is a DECIMAL POINT and 471 literal `±` prove it cannot be `±`.
        return {}
    out: dict[str, str] = {}
    if "\x06" in text and _PM_ANCHOR.search(text):
        out["\x06"] = "±"
    # The glyph-NAME spelling of the same failure. MEASURED over the 309-paper
    # cerebrolysin corpus, whose `body.md` files come from pdf2mdjson: `/Cn`
    # sits between two numbers 233 times in 12 papers, and 4 of those papers
    # carry a textual anchor ("Values shown mean /C6 SEM", "Values are Mean /C6
    # SD") that proves the glyph -- 141 of the occurrences. The other 8 papers
    # have no anchor and keep their damage, which includes
    # `10.1007--s00702-004-0248-2`.
    for m in _NAMED_PM_ANCHOR.finditer(text):
        token = m.group(1)
        # PADDED TO THE ORIGINAL LENGTH. `/C6` is three characters and `±` is
        # one, and `completeness._body_items` matches on the repaired string
        # while slicing `raw` from the source at the SAME offsets. Trailing
        # spaces are harmless -- every BODY_PATTERN already allows whitespace
        # around an operator -- and a shortened string would silently move every
        # offset after the first repair.
        out[token] = "±" + " " * (len(token) - 1)
    return out


def apply_proven_repairs(text: str) -> str:
    """`text` with only the repairs it proves. See `proven_repairs`."""
    out = text or ""
    for bad, good in proven_repairs(out).items():
        out = out.replace(bad, good)
    return out
