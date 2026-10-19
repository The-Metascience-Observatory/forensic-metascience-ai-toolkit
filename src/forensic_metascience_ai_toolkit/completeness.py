"""Every checkable thing in a paper must end the run with a LABEL.

GREG, 2026-08-12, on the defect register, calling this the most consequential
item on it:

    "I need you to make a system that makes it so the model CANNOT proceed
     unless all checkable cells are checked and given the appropriate label...
     it shouldn't just be cells in tables, but also checkable content in the
     body of the paper."

WHY THIS IS THE MOST CONSEQUENTIAL THING
-----------------------------------------
Measured over 26 archived runs: 21 of 72 tables ever received a `check_table`
call, and 318 of 2,765 consumable cells -- 11.5% -- provably reached a check.
The other 88.5% are not refusals. They are SILENCE. Nothing in the report says
they exist, so a reader cannot tell a paper we examined from a paper we glanced
at, and "no findings" carries a weight it has not earned.

The existing `census` answers "how many cells COULD have been checked" and it is
an honest denominator -- but it is a SURVEY. It runs after the fact, it reports
a percentage, and nothing anywhere blocks on it. A number nobody acts on is the
shape this repository keeps rediscovering.

WHAT THIS DOES INSTEAD
----------------------
It builds a MANIFEST: one row per checkable item across the whole paper, tables
and prose alike, and demands that every row carry a DISPOSITION by the end of the
run. A disposition is either

    checked      -- a tool ran on it and returned something, or
    refused:<r>  -- it was deliberately not checked, for a reason drawn from a
                    CLOSED VOCABULARY

and nothing else. `OUTSTANDING` -- present in the paper, absent from both lists --
is the state the gate exists to eliminate.

THE REFUSAL VOCABULARY IS CLOSED, and that is the load-bearing half. "Checked
everything I could" is not auditable; "142 items, 39 checked, 103 refused as
`no_applicable_check`, 0 outstanding" is. A closed vocabulary also makes the
refusals COUNTABLE, so the commonest reason becomes the next thing to build --
which is how a coverage figure turns into a work queue instead of an apology.

WHAT IT DOES NOT DO
-------------------
It does not decide whether a check was CORRECT, only that one happened or was
declined with a reason. A gate that tried to judge quality would be a second
reviewer, and this is a completeness instrument.

It also cannot enumerate what the extractor never saw. If a table is an image, or
a supplement is missing, those items are invisible here as they are everywhere
else -- so `n_items` is a floor, and `paper_coverage_is_a_floor` says so in the
output rather than leaving a reader to assume otherwise.
"""
from __future__ import annotations

import re
from pathlib import Path

#: The complete set of reasons an item may go unchecked. Adding one is a
#: deliberate act: it means admitting a new class of thing we do not check, and
#: the count against it becomes the argument for building the check.
REFUSAL_REASONS: dict[str, str] = {
    "no_applicable_check":
        "the item's kind routes to no check in the dispatch table -- a gap in "
        "the toolkit, not a property of the paper",
    "missing_input":
        "a required input (almost always the denominator n) is not available "
        "for this item",
    "undeclared_variable":
        "the cell is `ambiguous` and no variable family was declared, so its "
        "meaning is unknown and no tool may run on it",
    "not_a_statistic":
        "a row or column label, a heading, or prose -- correctly not checked",
    "unreadable":
        "the toolkit could not parse it. OUR defect, and it is counted as ours",
    "covered_by_batch":
        "checked as part of a batch or sweep aimed at the whole table rather "
        "than at this item individually",
    "out_of_scope_by_policy":
        "deliberately excluded by a stated policy, e.g. a figure-derived value "
        "refused by the exact-arithmetic checks",
}

CHECKED = "checked"
OUTSTANDING = "OUTSTANDING"

#: Body-text patterns. Deliberately conservative: each matches a shape that is
#: unambiguously a reported statistic, because a false ENTRY here manufactures an
#: outstanding item the model can never discharge and the gate becomes noise.
#: `·` is a DECIMAL POINT here, not a separator. Lancet house style sets
#: `-0·077` where most journals set `-0.077`, and `International Journal of
#: Stroke` does it 158 times in one paper of the eleven-paper run. Without it
#: this pattern matched only the `077`, so the span handed downstream began
#: mid-number and the estimate was read as 77. `celltypes.repair_unicode` turns
#: the dot into a `.` before anything parses the span; this pattern only has to
#: know where the number STARTS and ENDS.
_NUM = r"[-+]?\d*[.·]?\d+"
BODY_PATTERNS: dict[str, str] = {
    # `\d+` for the df missed WELCH'S CORRECTION, which yields a decimal:
    # `t(243.39) = 2.11` matched nothing, and an unequal-variance t-test is
    # the ordinary case in psychology rather than an exotic one.
    "nhst": rf"\b[tFrzZ]\s*\(\s*\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)?\s*\)\s*=\s*{_NUM}",
    "chi2": rf"(?:χ|chi)\s*2?\s*\(\s*\d+[^)]*\)\s*=\s*{_NUM}",
    "p_value": rf"\bp\s*[<>=]\s*\.?{_NUM}",
    "percentage": rf"{_NUM}\s*%",
    "mean_sd_prose": rf"{_NUM}\s*\(\s*(?:SD|s\.d\.|SE|SEM)\s*[=:]?\s*{_NUM}\s*\)",
    # THE APA COMMA FORM, which is how psychology actually writes it:
    # `M = 4.64, SD = 1.50`. The parenthesised pattern above requires
    # `4.64 (SD = 1.50)` and saw NONE of it. MEASURED on
    # 10.1007--s11031-011-9216-y, a psychology paper: every mean/SD pair in its
    # prose was invisible to the floor -- and a mean with its SD is exactly what
    # GRIM and GRIMMER consume, so the tripwire that exists to say what the
    # model overlooked could not see the paper's principal reported statistics.
    "mean_sd_apa": rf"\bM(?:ean)?\s*[=:]\s*{_NUM}\s*,\s*"
                   rf"(?:SD|S\.?D\.?|SE|SEM)\s*[=:]\s*{_NUM}",
    # `65.2 ± 1.17` -- THE CLINICAL CONVENTION, and the largest single hole this
    # enumerator had. MEASURED over the 305-paper cerebrolysin corpus: 128
    # papers (42%) use it, 5,942 occurrences, and NONE of them were indexed.
    # The floor exists to say what the model overlooked, and on 42% of a
    # clinical corpus it could not see the commonest way a mean and its
    # dispersion are printed.
    #
    # The dispersion after `±` may be an SD, an SE or a half-interval, and this
    # does not decide which -- that is the typer's job and `celltypes` already
    # refuses the cell when the label does not say. Enumerating it is not the
    # same act as checking it, and a value nobody can type is still a value the
    # paper printed.
    #
    # `\x06` is included because ONE corpus paper (75 occurrences) has `±`
    # arriving as a control character from the PDF's font encoding -- the same
    # class of damage as `¼` for `=`, and repaired only between two digits.
    "mean_pm_prose": rf"(?<![\w.]){_NUM}\s*(?:±|\+/-|\+-|\x06)\s*{_NUM}(?![\w.])",
    # A NAMED QUANTITY GIVEN A VALUE. `n = 202`, `partial η² = 0.048`,
    # `MWcombined = 0.69`, `Mfemales = 6.22`. Positive-only -- it adds
    # classifications and removes nothing -- and it recovers the one input GRIM
    # needs most: a sample size stated in prose, which no other pattern here
    # matches.
    #
    # A CLOSED SYMBOL LIST, not a general `identifier = number`. The latter
    # would swallow software versions, table coordinates and anything else that
    # happens to be written with an equals sign; these are the symbols a paper
    # uses for reported quantities. The optional suffix is for the subscripts
    # that survive extraction fused to the symbol.
    "named_equality": (r"\b(?:[nN]|M|SD|SE|SEM|Mdn|R2|R²|η2|η²|OR|RR|HR|MW|"
                       r"alpha|beta|β|α|χ2|χ²)[A-Za-z0-9_]{0,14}\s*[=:]\s*"
                       + _NUM),
    "estimate_ci_prose": rf"{_NUM}\s*\(\s*9[059]\s*%\s*CI[^)]*\)",
    # `95% CI 0.50 to 0.81` -- the UNPARENTHESISED form, which the pattern
    # above cannot see. Both bounds are one item, because an interval is one
    # reported quantity however it is punctuated.
    "ci_to_form": rf"9[059]\s*%\s*CI[\s:,]*{_NUM}\s*(?:to|\u2013|\u2014|-|,)\s*{_NUM}",
    "n_of_total": r"\b\d+\s*(?:out\s+of|of|/)\s*\d+\b",
    # THE DEGREES OF FREEDOM FUSED TO THE SYMBOL, with no parentheses:
    # `F1,37 = 1.19`, `F1,60 = 6.52`, `F1,26 = 0.04`. `nhst` above REQUIRES the
    # parentheses, so this form -- ordinary in print and the usual result of a
    # PDF losing its subscript markup -- matched nothing. MEASURED over the
    # 12-paper corpus: 50 unclassified numerals sit inside one, the single
    # largest recoverable group on the floor.
    "nhst_glued": rf"\b[tFrzZ]\s*\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?\s*"
                  rf"[<>=\u2264\u2265]\s*{_NUM}",
    # AND THE INEQUALITY FORM. `nhst` requires `=`, so `F (1,52) < 0.1` and
    # `F(1,68) < 0.3` -- how a paper reports a test it wants to dismiss -- were
    # invisible. A bound on a statistic is still a reported statistic, and it is
    # the one a reader most wants enumerated, because an unreported exact value
    # is what a completeness gate exists to notice.
    "nhst_bounded": rf"\b[tFrzZ]\s*\(\s*\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)?\s*\)"
                    rf"\s*[<>\u2264\u2265]\s*{_NUM}",
    # A BARE REGRESSION COEFFICIENT. `named_equality`'s symbol list carries
    # `beta` and `β` but not `b`, and psychology writes the unstandardised
    # coefficient as a lone `b`: `b = 0.13, SE b = 0.07, t(84) = 2.00`.
    #
    # DELIBERATELY NOT ADDED TO `named_equality`, whose `[A-Za-z0-9_]{0,14}`
    # suffix would turn a one-letter symbol into a match for `baseline = 3` and
    # every other word beginning with b. This requires `b` to stand alone.
    # AUDITED: all 53 occurrences in the corpus are genuine coefficients, 18
    # read by hand -- `b = -2.43, SE b = 1.87`, `B = .10, x2 = 28.82`.
    # The trailing lookahead excludes ONE KNOWN CORRUPTION rather than a class
    # of values. `10.1371--journal.pone.0069841` loses its minus signs to a CMap
    # fault, so `B = -.012` arrives as `B = 2 .012` -- and without the lookahead
    # this pattern matches `B = 2` and files a mangled minus sign as a reported
    # coefficient. MEASURED: 8 such artifacts on that paper. A legitimate
    # coefficient is never a bare integer trailed by a separate decimal.
    # `glyphs.scan` already finds these sites and `markdown_out` stamps that
    # paper `text_is_clean: false`; this keeps the artifact off the floor too.
    "beta_bare": rf"(?<![A-Za-z0-9_.])[Bb]\s*[=:]\s*{_NUM}(?!\s+\.\d)",
    # THE JAMA EFFECT-AND-INTERVAL FORM: `AOR, 1.71; 95% CI, 1.17-2.49`.
    # `estimate_ci_prose` requires the interval parenthesised immediately after
    # the estimate; this journal family separates them with a semicolon and
    # commas, so neither the estimate nor its bounds were indexed.
    "effect_ci_jama": rf"\b(?:A?[OH]R|ARR|IRR|RR|HR|OR)\s*,\s*{_NUM}\s*;\s*"
                      rf"9[059]\s*%\s*CI\s*,\s*{_NUM}\s*[-\u2013\u2014]\s*{_NUM}",
}


#: A NUMBER THAT IS NOT A RESULT. Each of these was found by reading the first
#: 18 body items this enumerator produced on a real paper, and every one would
#: have become an item the model could never discharge -- which is how a
#: completeness gate turns into noise its reader learns to skip.
#:
#:  - `95% CI` / `90% CIs` -- a confidence LEVEL, not a reported percentage
#:  - `80% power (alpha = .05)` -- a design target, not a result
#:  - `A 2-sided P < .05 was set as the threshold` -- a METHODS declaration of
#:    the significance level, not a p-value anyone computed
#:
#: Matched on the text immediately AROUND the number, because the number itself
#: is identical in both readings; only its neighbourhood distinguishes them.
_NOT_A_RESULT = (
    (r"%", r"^\s*(?:CIs?\b|confidence)"),          # trailing: "95% CI"
    (r"%", r"^\s*power\b"),                        # trailing: "80% power"
    (r"p", r"^\s*(?:was|is)\s+(?:set|used|considered)"),   # "P < .05 was set"
)

#: A CONCENTRATION IS NOT A FINDING. "Sections were fixed in 4%
#: paraformaldehyde and washed in 0.9% saline" enrolled 4% and 0.9% as reported
#: statistics the model must check or refuse. In a corpus of 309 neuroscience
#: papers, methods sections are made of these, and each one becomes an
#: outstanding item that can never be discharged.
_REAGENT_AFTER = re.compile(
    r"^\s*(?:w/v|v/v|wt/vol|vol/vol)?\s*"
    r"(?:paraformaldehyde|pfa|formalin|formaldehyde|glutaraldehyde|saline|"
    r"ethanol|methanol|isoflurane|halothane|sucrose|agarose|acrylamide|"
    r"gelatin|bsa|serum|albumin|triton|tween|dmso|edta|sds|nacl|hcl|h2o2|"
    r"co2|o2|oxygen|glucose|agar|milk|goat|donkey|normal\s+\w+\s+serum|"
    r"buffer|solution|acid|saponin|azide)\b", re.I)

#: ANOTHER PAPER'S NUMBER IS NOT THIS PAPER'S RESULT. "Smith et al. reported
#: that 62% of studies failed to replicate" is a claim about the literature,
#: and the floor asserts of every item that it is "present in the paper and the
#: model did not list them" -- so an attributed number is charged to the model
#: as a missed statistic of its own paper.
_ATTRIBUTED_BEFORE = re.compile(
    r"\bet\s+al\.?[^.;]{0,40}$|"
    r"\[\d+(?:\s*[-,]\s*\d+)*\][^.;]{0,40}$|"
    r"\b(?:previously|prior(?:\s+work)?|earlier\s+(?:studies|work|reports?)|"
    r"other\s+(?:studies|authors)|the\s+literature)\b[^.;]{0,40}$", re.I)

#: A THRESHOLD THE STUDY WILL APPLY IS NOT A NUMBER IT OBSERVED. "The
#: intervention will be judged successful if more than 30% of patients respond"
#: is a decision rule, in the same family as the alpha and power cases the
#: original table already excluded.
#: TIGHTENED after measuring. A first version listed expect/criterion/target/
#: threshold as cues, and deleted two REAL results out of a 12-item sample:
#:   "As expected, in non-tg mice approximately 65% of the BrdU+ cells
#:    expressed NeuN"                                    -- "expected"
#:   "These criteria improved by 12-38% in comparison to baseline"
#:                                                       -- "criteria"
#: Those words are ordinary in a results sentence. Only genuine future or
#: conditional modality is a decision rule, so that is all this matches now --
#: dropping a real statistic from the floor is a false all-clear about the
#: register's completeness, which is the error this module exists to prevent.
_HYPOTHETICAL_BEFORE = re.compile(
    r"\b(?:will|would|shall)\s+(?:be\s+|not\s+)?\w+[^.;]{0,40}$|"
    r"\bif\s+(?:more|less|fewer|at\s+least|at\s+most|greater|over|under)\b"
    r"[^.;]{0,40}$", re.I)

#: PEOPLE WHO RAN THE STUDY ARE NOT ITS SAMPLE. "Ratings were made by 3 of 5
#: trained coders" is staffing.
_STAFF_AFTER = re.compile(
    r"^\s*(?:trained\s+|independent\s+|blinded\s+)*"
    r"(?:coders?|raters?|reviewers?|judges?|experimenters?|assessors?|"
    r"observers?|authors?|investigators?|clinicians?)\b", re.I)


def _body_end(text: str) -> int:
    """Offset where the results end, so the bibliography is not enumerated.

    GREG, 2026-08-16: "extract the references separately. That way this kind of
    mistake won't happen." The boundary is therefore computed in ONE place --
    `references.split` -- and this function only asks it where the body stops.
    The first cut put a heading regex here, which worked for the papers that
    print a `## References` heading and silently missed all five PNAS papers,
    which print none and number their entries instead.

    MEASURED before the fix, over the 16 cached docling extractions: 33 of 439
    floor items (7.5%) sat inside a reference list, and for `10.1002--eat.24415`
    it was 20 of 25 -- 80% of that paper's floor was bibliography. Three were
    DOIs read as sample fractions: `10.1037/0022-3514...` enumerates as the
    statistic "1037/0022".

    That is the house failure mode exactly. The floor is what accuses the
    register of being incomplete, so every bibliography artefact in it is our
    enumerator's error charged to the model as a missed statistic.
    """
    from . import references as _refs
    return len(_refs.split(text)["body"])


#: C0 controls, minus the three that are ordinary whitespace. A broken
#: `ToUnicode` CMap leaks the raw glyph INDEX here, and it lands mid-number.
_C0 = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]|/C\d{1,3}\b")

#: The same debris, anchored so it must sit in the number's SIGN POSITION.
_GLYPH_BEFORE = re.compile(
    r"(?:[\x00-\x08\x0b\x0c\x0e-\x1f]|/C\d{1,3})\s?$")


def _truncated_by_a_glyph(text: str, m: "re.Match") -> bool:
    """Did this match stop because a corrupt character interrupted the number?

    THE FAILURE THIS PREVENTS IS A WRONG NUMBER, NOT A MISSING ONE. In
    `10.1166--jnn.2011.5114` the text reads `P < 0\x0605` -- a printed
    `P < 0.05` whose decimal point survived extraction as a raw font glyph
    index. The `p_value` pattern matches up to the control character and stops,
    so the item's `raw` is `P < 0` and the pipeline receives a reported p of
    ZERO. That is impossible, and a check comparing a reported p against a
    computed one can turn it into an accusation against an honest paper.

    Refused rather than repaired, which is `glyphs.py`'s standing rule: the byte
    is a font-specific glyph index and not an encoding. MEASURED, the same
    `\x06` is `±` in three Zotero papers ("mean \x06 SD", 255 occurrences, no
    literal `±` between them) and a DECIMAL POINT in the paper above, which
    carries 471 literal `±`. One byte, two characters, decided by a font we do
    not have. `glyphs.scan` reports the damage and quarantines the paper; this
    only declines to hand a truncated number onward as though it were whole.

    Deliberately narrow: the control character must sit IMMEDIATELY at the end
    of the match or inside it. A corrupt character elsewhere in the sentence
    says nothing about whether THIS number came through intact.
    """
    if _C0.search(m.group(0)):
        return True
    if _C0.match(text[m.end():m.end() + 6]):
        return True
    # AND THE SIGN POSITION IN FRONT OF IT. In `7AP7MG3N`, `\x00` is a minus
    # (`between +0.345 and \x00 0.145`, in a paper with 1052 literal `-` and no
    # unicode `−`) and `\x18` is `~` (`\x18 70 million neurons`). Read without
    # this, a negative value arrives positive and an approximate one arrives
    # exact -- the second is the difference between a number GRIM may test and
    # one it may not.
    # IMMEDIATELY IN FRONT, not merely nearby. MEASURED: `the effect was
    # /C0 0.85 (95% CI /C0 1.2, /C0 0.3)` emitted an `estimate_ci_prose` of
    # 0.85 -- a printed -0.85 with CI [-1.2, -0.3] reaching a check as
    # POSITIVE, with a confidence interval attached -- and `reduced by /C0 43%`
    # emitted `43%` the same way. Both are this file header's named failure: a
    # wrong number that looks plausible, on which every check computes
    # confidently.
    #
    # A FIRST CUT SEARCHED SEVEN CHARACTERS BACK AND OVER-REFUSED. In
    # `10.1007--s00702-003-0025-7` a footnote legend reads `/C3 ¼ p < 0.05` --
    # that is `* = p < 0.05`, where `/C3` is the ASTERISK and the p-value is
    # perfectly intact. A window wide enough to reach past the `=` threw away
    # four undamaged p-values. The glyph has to be the thing standing in the
    # number's sign position, so it must END where the number begins.
    return bool(_GLYPH_BEFORE.search(text[max(0, m.start() - 8):m.start()]))


def _is_result(text: str, m: "re.Match") -> bool:
    """Does this match read as a REPORTED result rather than a design choice?"""
    after = text[m.end():m.end() + 40]
    before = text[max(0, m.start() - 40):m.start()]
    # Wider windows for the judgments that need a clause rather than a token.
    after_wide = text[m.end():m.end() + 60]
    before_wide = text[max(0, m.start() - 120):m.start()]
    for _tok, tail in _NOT_A_RESULT:
        if re.match(tail, after, re.IGNORECASE):
            return False
    if _REAGENT_AFTER.match(after_wide):
        return False
    if _STAFF_AFTER.match(after_wide):
        return False
    if _ATTRIBUTED_BEFORE.search(before_wide):
        return False
    if _HYPOTHETICAL_BEFORE.search(before_wide):
        return False
    # "the 90% CIs from ..." puts CI after a plural; also catch the level named
    # before the number, e.g. "at the 95 % confidence level".
    if re.search(r"\b(?:alpha|α)\s*[=:]\s*$", before, re.IGNORECASE):
        return False
    if re.search(r"\bsignificance\b[^.]{0,30}$", before, re.IGNORECASE):
        return False
    # A DOI is not a sample fraction. `10.1037/0022-3514` reads as "1037 of
    # 22" to a slash pattern, and papers cite DOIs in running text as well as
    # in the reference list, so the cutoff above does not catch all of them.
    if re.search(r"\b10\.$", before):
        return False
    # Nor is any fraction whose numerator exceeds its denominator: "n of total"
    # cannot exceed its total. Five such items were in the corpus, every one a
    # DOI. This costs nothing real -- an impossible fraction is not a statistic
    # the model could have enumerated correctly either.
    frac = re.match(r"^(\d+)\s*/\s*(\d+)$", m.group(0).strip())
    if frac and int(frac.group(1)) > int(frac.group(2)):
        return False
    return True


#: `=` AS OLDER PDFs ENCODED IT. A Type-1 font-encoding artifact, not an OCR
#: guess: `p = 0.038` reaches us as `p ¼ 0.038`. MEASURED over the 305-paper
#: cerebrolysin corpus, 25 papers contain `¼`, and repairing it recovers 30
#: prose statistics (508 -> 538, +5.9%), up to +7 on a single paper -- p-values
#: and whole NHST triples (`F CL ¼ 45.43; DFn ¼ 19; DFd ¼ 80`) that no pattern
#: here could see, so they were missing from the floor AND unreachable by
#: statcheck.
#:
#: CONTEXTUAL, NEVER GLOBAL. `¼` means one quarter, and this only fires between
#: a word or closing bracket and a NUMBER, where it cannot: "improvement in ¼ of
#: patients" is untouched.
#:
#: LENGTH-PRESERVING, which is the load-bearing property. Only the single
#: character is swapped and every surrounding space is kept, so an offset into
#: the repaired text is an offset into the original -- and `raw` and `context`
#: below are sliced from the ORIGINAL. A locator that points at a string the
#: paper does not contain is worse than no locator.
_MOJIBAKE_EQUALS = re.compile(r"(?<=[\w\)\]])(\s*)¼(\s*)(?=[-+.\d])")


#: HTML ENTITIES THAT HIDE AN OPERATOR. docling leaves `&lt;` and `&gt;`
#: undecoded, so `p &lt; .05` never matches a pattern wanting a literal `<`.
#: MEASURED over the 305-paper cerebrolysin corpus: 265 papers (87%) contain an
#: entity, on 3,393 lines, and 1,901 of the hits are `p &lt; <number>` -- every
#: one a p-value invisible to this enumerator AND to statcheck, whose entire
#: job is comparing a reported p against a recomputed one.
#:
#: PADDED TO PRESERVE LENGTH, the same discipline as the mojibake `=` above:
#: `&lt;` becomes `<` followed by three spaces, so every offset into the
#: repaired text is still an offset into the original and `raw`/`context` can
#: be sliced from the source. The patterns all allow `\s*` around an operator,
#: so the padding costs nothing.
_ENTITY = {"&lt;": "<", "&gt;": ">", "&le;": "<", "&ge;": ">", "&amp;": "&"}
_ENTITY_RE = re.compile("|".join(re.escape(k) for k in _ENTITY))


def _repair_entities(text: str) -> str:
    """`text` with operator entities decoded, character-for-character."""
    def _sub(m):
        rep = _ENTITY[m.group(0)]
        return rep + " " * (len(m.group(0)) - len(rep))
    return _ENTITY_RE.sub(_sub, text or "")


def _repair_equals(text: str) -> str:
    """`text` with the mojibake `=` restored, character-for-character."""
    return _MOJIBAKE_EQUALS.sub(lambda m: f"{m.group(1)}={m.group(2)}", text or "")


def _body_items(text: str, max_items: int = 400) -> list[dict]:
    """Reported statistics in prose, one manifest row each.

    Overlaps are resolved by keeping the FIRST match at a given offset, so
    `12.3 (95% CI 1.1-2.2)` is one item rather than three. Without that, a
    single sentence generates items the model cannot discharge individually and
    the gate trains its reader to ignore it.

    Matches that read as DESIGN rather than RESULT are dropped -- see
    `_NOT_A_RESULT`. That filter was written after reading the enumerator's own
    first output, where a confidence level, a power target and a stated alpha
    had all been enrolled as checkable claims.
    """
    seen: set[int] = set()
    out: list[dict] = []
    end = _body_end(text)
    # MATCHED against the repaired text, REPORTED from the original. See
    # `_MOJIBAKE_EQUALS`: the repair is length-preserving precisely so these two
    # can be different strings at the same offsets.
    original = text or ""
    # ...and a raw font glyph index only where THIS document proves what it is.
    # `glyphs.proven_repairs` requires a textual anchor (`mean \x06 SD`, the
    # glyph between two words where no digit is at stake) AND the absence of any
    # literal `±`, because a paper that can print the character is not also
    # spelling it as a control code. Unproven documents get no repair and their
    # damaged numbers are refused below rather than guessed at.
    from .glyphs import apply_proven_repairs as _apply_glyphs
    text = _apply_glyphs(_repair_entities(_repair_equals(original)))
    # ...and LaTeX notation rendered as the characters it stands for, for the
    # extractors that return mathematics as markup. GATED on the text actually
    # containing LaTeX, so an ordinary paper with a dollar sign in a cost table
    # is untouched.
    #
    # SAFE GLOBALLY, unlike the glyph repairs above, and the difference is the
    # whole reason both exist: a font glyph index means whatever that font says,
    # while `\pm` means `±` in every document ever written. This is the same
    # class as decoding `&lt;`.
    #
    # MEASURED on 10.1007--s00702-004-0248-2: our floor reads 40 statistics from
    # the text layer, 39 from Mistral and 2 from Mathpix, whose extraction was
    # excellent and whose notation we simply could not see.
    from .latex_text import looks_like_latex as _is_tex, to_unicode as _tex
    if _is_tex(text):
        text = _tex(text)
    for kind, pat in BODY_PATTERNS.items():
        for m in re.finditer(pat, text, re.IGNORECASE):
            if m.start() >= end:
                continue
            if any(o in seen for o in range(m.start(), m.end())):
                continue
            if not _is_result(text, m):
                continue
            if _truncated_by_a_glyph(text, m):
                continue
            seen.update(range(m.start(), m.end()))
            out.append({
                "id": f"body:{m.start()}",
                "where": "body",
                "offset": m.start(),
                "kind": kind,
                # WHAT THE PAPER PRINTED, so a reader searching the PDF for it
                # finds it. `celltypes` keeps `raw` verbatim for the same
                # reason and records the repair beside it rather than in it.
                "raw": original[m.start():m.end()].strip(),
                # A locator a human can search for, which is what makes an
                # outstanding item actionable rather than an accusation of
                # laziness.
                "context": original[max(0, m.start() - 60):m.end() + 60].replace("\n", " "),
                **({"repaired": m.group(0).strip(),
                    "repair": "mojibake '=' restored for matching"}
                   if original[m.start():m.end()] != m.group(0) else {}),
            })
            if len(out) >= max_items:
                return sorted(out, key=lambda x: x["offset"])
    return sorted(out, key=lambda x: x["offset"])


def _supplement_items(base: Path, problems: list[str]) -> list[dict]:
    """PROSE items from every supplementary file, labelled by source.

    Supplement TABLES come from `prepass.paper_tables(include_supplements=True)`,
    which is the single walker for them. This function covers the half that walk
    does not: statistics reported in a supplement's running text.

    Each item's `where` names the file it came from, so a reader can tell a
    number in Supplementary Table S3 from one in Table 3 of the article. Ids are
    namespaced the same way; without that, a cell at row 2 of "Table 1" in a
    supplement would collide with row 2 of "Table 1" in the paper.

    A supplement that cannot be read appends to `problems` and contributes no
    items. That is deliberate and it is the whole point: the count of items must
    never quietly absorb a document we failed to open, because a smaller
    denominator flatters our coverage.
    """
    out: list[dict] = []
    try:
        from . import supplements as _supp
        names = list(_supp.present_files(base) or [])
    except Exception as exc:  # noqa: BLE001
        problems.append(
            f"supplementary files could not be enumerated "
            f"({type(exc).__name__}: {exc}), so NO supplement item is counted "
            "for this paper. That is our failure, not the paper's.")
        return out

    for name in names:
        path = base / name if not Path(name).is_absolute() else Path(name)
        try:
            from .extraction.supplements_read import extract_supplement_full
            doc = extract_supplement_full(path)
        except Exception as exc:  # noqa: BLE001
            problems.append(
                f"supplement {Path(name).name!r} is present but could not be "
                f"read ({type(exc).__name__}: {exc}); its statistics are absent "
                "from this manifest and are NOT counted as checked or refused.")
            continue
        if not isinstance(doc, dict) or doc.get("error"):
            why = (doc or {}).get("error") if isinstance(doc, dict) else "no result"
            problems.append(
                f"supplement {Path(name).name!r} is present but unreadable "
                f"({why}); its statistics are absent from this manifest.")
            continue

        short = Path(name).name
        for it in _body_items(doc.get("text") or ""):
            it = dict(it)
            it["id"] = f"supp:{short}:{it['id']}"
            it["where"] = f"supplement {short} body"
            out.append(it)

    return out


def build_manifest(paper_dir: str | Path, body_text: str | None = None) -> dict:
    """One row per checkable item in the paper: tables first, then prose.

    Deterministic and model-free, deliberately: a manifest the model helped
    write is a manifest the model can shorten.
    """
    from . import census, prepass

    base = Path(paper_dir)
    items: list[dict] = []
    problems: list[str] = []

    # ONE WALKER. `prepass.paper_tables` enumerates article AND supplement
    # tables; keeping a second supplement walk here would rebuild the
    # two-denominators defect that `paper_tables` own docstring warns about.
    tables = prepass.paper_tables(base, include_supplements=True)
    problems += list(getattr(tables, "problems", None) or [])
    for tab in tables:
        label = tab.get("label") or "?"
        is_supp = tab.get("source") == "supplement"
        prefix = "supp:" if is_supp else ""
        where_stem = (f"supplement {tab.get('supplement_file') or '?'} table {label}"
                      if is_supp else f"table {label}")
        seen_in_row: dict[tuple, int] = {}
        for e in census.cell_census(tab.get("cells") or [], table=label):
            raw = (e.get("raw") or "").strip()
            if not raw:
                continue
            # AN ORDINAL, BECAUSE THE ID HAD NO COLUMN IN IT. The key was
            # `cell:{table}:{row}:{raw}`, so a row printing "1 [Reference]" in
            # three columns produced ONE id for three distinct cells. MEASURED
            # on 10.1001--jamanetworkopen.2023.37679: 94 of 757 items (12.4%)
            # shared an id with another item, 32 of the 42 colliding keys inside
            # the article itself. An item that cannot be told apart from another
            # cannot be given its own disposition, which is the whole purpose of
            # this manifest -- and it is the same identity failure that already
            # cost `check_table` 40% of its row dispositions.
            #
            # `cell_census` yields no column, and adding one there would change
            # a function several other callers depend on. The ordinal is
            # positional within (table, row), deterministic for a given
            # extraction, and enough to separate two otherwise identical cells.
            k = (label, e.get("row"))
            seen_in_row[k] = seen_in_row.get(k, -1) + 1
            items.append({
                "id": (f"{prefix}cell:{label}:{e.get('row')}:"
                       f"{seen_in_row[k]}:{raw[:24]}"),
                "where": where_stem,
                "row_label": e.get("row_label"),
                "kind": e.get("kind"),
                "raw": raw,
                "consumable": bool(e.get("consumable")),
                "runnable": bool(e.get("runnable")),
                "missing": e.get("missing"),
                "tools": e.get("tools") or [],
            })

    if body_text is None:
        body_text, body_problem = _read_body(base)
        if body_problem:
            problems.append(body_problem)
    items += _body_items(body_text or "")

    # SUPPLEMENTS ARE PART OF THE PAPER'S CLAIMS AND WERE NOT PART OF ITS
    # ACCOUNTING. `prepass.paper_tables` and `_read_body` both read
    # `glob("*.xml")[0]` -- the main article, and nothing else. Every table and
    # every reported statistic in a supplementary file was therefore absent
    # from this manifest, which is the worst shape a gap can take: those items
    # were not counted as unchecked, they were INVISIBLE, and the denominator
    # they should have enlarged made coverage look better than it was.
    #
    # Supplements are where the detailed tables usually live. MEASURED over
    # this repo: 13 of 78 paper directories carry them, 22 files, 3.1 MB.
    #
    # An unreadable supplement is recorded as a PROBLEM rather than skipped.
    # "Present but unreadable" and "not provided" are different facts about a
    # paper, and silently dropping the first would rebuild the same
    # invisibility one level down.
    items += _supplement_items(base, problems)

    def _n(pred):
        return sum(1 for i in items if pred(i["where"]))

    return {
        "paper": base.name,
        "n_items": len(items),
        "n_table_items": _n(lambda w: w.startswith("table")),
        "n_body_items": _n(lambda w: w == "body"),
        "n_supplement_items": _n(lambda w: w.startswith("supplement ")),
        "n_supplement_table_items": _n(
            lambda w: w.startswith("supplement ") and " table " in w),
        "n_supplement_body_items": _n(
            lambda w: w.startswith("supplement ") and w.endswith(" body")),
        "items": items,
        "problems": problems,
        "paper_coverage_is_a_floor": (
            "This manifest counts only what the extractor could see. An "
            "image-only table, an unfetched supplement or an unread figure "
            "contributes nothing here, so `n_items` is a LOWER BOUND on what the "
            "paper actually contains."
        ),
    }


def _read_body(base: Path) -> tuple[str, str | None]:
    """`(text, problem)`. Never raises, and never hides that it failed.

    Returns the problem ALONGSIDE the text rather than swallowing it. An empty
    string on its own says "this paper has no prose", which is a claim about the
    paper; a failure to read one is a fact about US, and the two must not be
    indistinguishable. This is the defect `paper_text` had -- it returned "" on
    every extraction crash, and four of its five consumers went on to publish a
    clean result on a paper nobody had opened.
    """
    try:
        xmls = sorted(base.glob("*.xml"))
        if xmls:
            from .extraction.jats import extract_xml_text_with_tables
            return (extract_xml_text_with_tables(
                str(xmls[0]), max_chars=400_000).get("text") or ""), None
        md = base / "body.md"
        if md.exists():
            return md.read_text(encoding="utf-8", errors="replace"), None

        # THE ARTICLE PDF, VIA THE DOCLING CACHE. Until 2026-08-15 this read XML
        # or `body.md` and nothing else, so a PDF-ONLY paper -- which is most of
        # them -- returned "" and the prose half of its manifest was empty. The
        # absence was then read downstream as "this paper reports nothing in
        # prose", and it became the headline entry on the defect list: "the
        # completeness manifest is effectively a TABLE manifest".
        #
        # IT WAS A WIRING FAULT ONE LEVEL UP, not a weakness of the enumerator.
        # MEASURED on the three papers run this week:
        #
        #   Ophir 2009  (PDF only)     body chars 0 -> 38,879
        #   Kross 2013  (PDF + docx)   body chars 0 -> 33,527
        #   JAMA .37679 (ships XML)    unchanged -- it already had a source
        #
        # `_body_items` recovers tens of items from that text. It was never
        # handed any. Same shape as `verdicts.py` and `text_provenance` this
        # week: the capability exists and is not connected to its source.
        #
        # CACHE ONLY, never extraction: building a manifest must not block for
        # minutes on a layout model, which is the rule `prepass.paper_tables`
        # already follows. A cold cache returns its reason and names the fix.
        #
        # THE DECLARED ARTICLE ONLY. Reading whichever PDF sorts first would let
        # a supplement's prose enter the manifest as the paper's own body.
        # HTML, BEFORE THE PDF, because the TEXT LADDER PUTS IT THERE and this
        # function is the register's floor -- if the two disagree, the model
        # reads one document and the denominator counts another.
        #
        # THIS WAS LIVE. `jats._derive_paper_text` ranks
        # body_md > xml_publisher > xml_derived > html > pdf; this function had
        # xml > body.md > pdf and NO HTML RUNG AT ALL. So on the five papers
        # upgraded to a PMC full text on 2026-09-06 the model was served the
        # HTML while the floor kept counting numerals in the docling PDF text --
        # the corrupted one, whose dose units are wrong by 1000x. The corpus
        # diff not moving for those papers is what exposed it.
        #
        # `find_html` is shared rather than re-globbed, so the decoy gate
        # applies here too: a Cloudflare challenge page cannot become the
        # denominator any more than it can become the text.
        #
        # A LARGE BUDGET DELIBERATELY. The ladder serves the model a clipped
        # 50,000 characters; the FLOOR must still know how many numerals the
        # paper has, or clipping would improve coverage. `numerals.tally` says
        # `n_total` "cannot be silently incomplete", and a budget is exactly the
        # silent kind of incomplete.
        from .extraction.html import extract_html_text_with_tables, find_html

        html = find_html(base)
        if html is not None:
            try:
                res = extract_html_text_with_tables(html, max_chars=10_000_000)
                htext = "" if res.get("error") else (res.get("text") or "")
            except (OSError, ValueError) as exc:
                return "", (f"the HTML full text ({html.name}) could not be read "
                            f"({type(exc).__name__}: {exc}), so NO prose item is "
                            "enumerated. That is OUR gap, not an absence of "
                            "reported statistics.")
            if htext.strip():
                return htext, None

        from .extraction.docling_tables import cached_text

        article, how = _article_pdf(base)
        if article is not None:
            text, why = cached_text(article)
            if text:
                return text, None
            return "", (f"the article PDF ({article.name}, resolved {how}) has no "
                        f"cached text ({why}), so NO prose item is enumerated. Run "
                        "`metascience extract-tables` on this paper. That is OUR "
                        "gap, not an absence of reported statistics.")
        article_note = how
    except Exception as exc:  # noqa: BLE001 -- reported, never swallowed
        return "", (f"body text could not be read ({type(exc).__name__}: {exc}), "
                    "so NO prose item is enumerated for this paper. That is our "
                    "failure, not an absence of reported statistics.")
    return "", (f"no XML, body.md or article PDF in this directory ({article_note}), "
                "so no prose item is enumerated. The prose half of this manifest "
                "is empty for want of a source, not because the paper has none.")


#: Filenames that POSITIVELY identify a PDF as the article. Used only as the
#: last resort, after a declaration and after the DOI stem, and only when it is
#: the directory's single PDF. An allowlist because the failure direction has to
#: be refusal: `supplements.classify_inputs` returns `undeclared` for anything
#: nobody declared, so a name it does not recognise tells us nothing, and a
#: lone `aaa_supplementary_appendix.pdf` must not become the paper's body.
_ARTICLE_STEMS = frozenset({"paper", "article", "manuscript", "fulltext",
                            "full_text", "full-text", "main", "ms"})


def _article_pdf(base: Path) -> tuple[Path | None, str]:
    """`(path, how)` -- the PDF this directory's ARTICLE lives in, and by whose
    authority we decided that.

    Declaration first, filename convention second. `supplements.classify_inputs`
    reads the operator's `inputs.json`, the article's own supplementary-material
    list and the DOI stem -- the three authorities that do not guess -- and a
    supplement misread as the article would put its prose into the manifest as
    the paper's own.

    `how` IS RETURNED RATHER THAN DISCARDED. The first cut wrote
    `except Exception: pass` and fell through to the stem convention silently,
    so a caller could not tell an article resolved by DECLARATION from one
    guessed by FILENAME, nor either from a declaration that failed to parse.
    `lint-inert` flagged it as the 29th proven-inert finding within the hour --
    the repo's own guard catching, in code written to fix the
    absence-read-as-evidence defect, the absence-read-as-evidence defect.
    """
    try:
        from .supplements import classify_inputs

        for row in (classify_inputs(base).get("files") or []):
            # `name`, NOT `path`. `classify_inputs` emits rows keyed
            # `declared_by / name / role / why` and has no `path` at all, so
            # this branch read `None` for every row and NEVER FIRED. The
            # docstring below says "Declaration first, filename convention
            # second"; in practice declaration was dead and every article was
            # resolved by DOI stem -- including the ones an operator had
            # explicitly declared. `path` is still honoured if a caller supplies
            # it, so this only adds the key that actually exists.
            path = str(row.get("name") or row.get("path") or "")
            if row.get("role") == "article" and path.lower().endswith(".pdf"):
                p = Path(path)
                if not p.is_absolute():
                    p = base / p.name
                if p.is_file():
                    # WHICH AUTHORITY, not merely "declared". `classify_inputs`
                    # resolves an article three ways and stamps `declared_by`:
                    # `operator` (an inputs.json somebody wrote), `doi_stem` (a
                    # filename convention), or the article's own supplement
                    # list. Collapsing them to one word loses exactly the
                    # distinction `test_a_supplement_is_not_read_as_the_article`
                    # asks for -- "the caller must be able to tell a guess from
                    # a declaration" -- and a DOI-stem match IS a guess.
                    by = str(row.get("declared_by") or "unknown authority")
                    return p, f"declared by {by}"
        why = "no PDF carries the `article` role in this directory's declaration"
    except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
        why = (f"the input declaration could not be read "
               f"({type(exc).__name__}: {exc}), so the article was resolved by "
               "filename instead")

    stem = base / f"{base.name}.pdf"
    if stem.is_file():
        return stem, f"by DOI-stem filename ({why})"

    # THE ONLY PDF, when there is exactly one AND its name says it is the
    # article. An ALLOWLIST, not a denylist, and the difference is the whole
    # safety of it: an unrecognised name fails closed.
    #
    # My first cut used "exactly one PDF, therefore no ambiguity" and
    # `test_a_supplement_is_not_read_as_the_article` broke immediately -- a
    # directory holding only `aaa_supplementary_appendix.pdf` would have had a
    # SUPPLEMENT's prose enter the manifest as the paper's own body. The
    # ambiguity was never between two PDFs; it is whether the one PDF is the
    # article at all. `supplements.classify_inputs` cannot settle it either: it
    # returns `undeclared` for every undeclared file rather than guessing.
    #
    # It closes a split between two halves of the same manifest.
    # `prepass._article_pdf_tables` ALREADY falls back this way -- "no file is
    # declared the article, so paper.pdf was read as one" -- so on a directory
    # holding a bare `paper.pdf` the TABLE half read the paper and the PROSE
    # half returned nothing, for the same paper, in the same run. MEASURED:
    # every one of the 217 Zotero and 309 cerebrolysin directories holds 0 or 1
    # PDF, so this is the normal case and not an edge one, and the prose half
    # was empty on all 217.
    #
    # Still refuses when there are several: then the ambiguity is real and a
    # supplement's prose could enter the manifest as the paper's own body.
    pdfs = sorted(base.glob("*.pdf"))
    if len(pdfs) == 1 and pdfs[0].stem.lower() in _ARTICLE_STEMS:
        return pdfs[0], f"the only PDF in the directory, named as the article ({why})"
    if len(pdfs) > 1:
        return None, (f"{len(pdfs)} PDFs and none declared the article ({why}); "
                      "refusing to guess which is the paper. Declare it with "
                      "`metascience inputs`.")
    if pdfs:
        return None, (f"the only PDF here is {pdfs[0].name}, whose name does not "
                      f"identify it as the article ({why}); it may be a "
                      "supplement. Declare it with `metascience inputs`.")
    return None, f"no article PDF found ({why})"


def _auto_refusals(item: dict) -> str | None:
    """The disposition the harness can assign without the model's help.

    Assigning these automatically is what keeps the gate honest rather than
    bureaucratic: a row label is not something a model should have to declare it
    declined to check, and demanding that would bury the items that matter.
    """
    if item["where"] == "body":
        return None
    kind = item.get("kind")
    if kind in ("non_numeric",):
        return "not_a_statistic"
    if kind == "ambiguous":
        return "undeclared_variable"
    if not item.get("consumable"):
        return "no_applicable_check"
    if not item.get("runnable"):
        return "missing_input"
    return None


def disposition_report(manifest: dict, checked_ids: set[str] | None = None,
                       declared: dict[str, str] | None = None) -> dict:
    """Assign every manifest row a disposition, and count what is OUTSTANDING.

    `checked_ids` are items a tool demonstrably ran on. `declared` lets the model
    refuse an item explicitly, with a reason from `REFUSAL_REASONS`; an unknown
    reason is REJECTED rather than accepted, because a free-text refusal is how a
    closed vocabulary stops being closed.
    """
    checked_ids = checked_ids or set()
    declared = declared or {}
    rows, counts, bad_reasons = [], {}, []

    for item in manifest.get("items") or []:
        iid = item["id"]
        if iid in checked_ids:
            disp = CHECKED
        elif iid in declared:
            reason = declared[iid]
            if reason in REFUSAL_REASONS:
                disp = f"refused:{reason}"
            else:
                bad_reasons.append({"id": iid, "reason": reason})
                disp = OUTSTANDING
        else:
            auto = _auto_refusals(item)
            disp = f"refused:{auto}" if auto else OUTSTANDING
        counts[disp] = counts.get(disp, 0) + 1
        rows.append(dict(item, disposition=disp))

    outstanding = [r for r in rows if r["disposition"] == OUTSTANDING]
    n = len(rows)
    return {
        "paper": manifest.get("paper"),
        "n_items": n,
        "n_checked": counts.get(CHECKED, 0),
        "n_refused": sum(v for k, v in counts.items() if k.startswith("refused:")),
        "n_outstanding": len(outstanding),
        "by_disposition": counts,
        "outstanding": outstanding,
        "invalid_refusal_reasons": bad_reasons,
        "complete": not outstanding and not bad_reasons,
        "rows": rows,
    }


def gate(report: dict, enforce: bool = False) -> dict:
    """The verdict, and the sentence the model is shown when it fails.

    ENFORCE DEFAULTS TO FALSE, AND THAT IS A MEASURED DECISION RATHER THAN
    TIMIDITY. Coverage today is 11.5% of consumable cells, so switching
    enforcement on right now halts every run on its first paper. The gate is
    therefore introduced RECORDING first: it measures the gap on real runs, the
    gap drives the work, and enforcement is turned on when the number supports
    it. Shipping it enforcing today would not raise coverage; it would just stop
    the pipeline and teach everyone to pass the flag that disables it.
    """
    if report.get("complete"):
        return {"passed": True, "enforced": enforce,
                "message": (f"All {report['n_items']} checkable item(s) carry a "
                            f"disposition: {report['n_checked']} checked, "
                            f"{report['n_refused']} refused with a stated reason.")}
    lines = [
        f"{report['n_outstanding']} of {report['n_items']} checkable item(s) have "
        "NO disposition. Every item must be either checked or refused with a "
        "reason from the closed vocabulary before this run is complete.",
        "",
        "Outstanding (first 20):",
    ]
    for r in report["outstanding"][:20]:
        lines.append(f"  {r['id']}  [{r.get('kind')}]  {r['raw'][:48]!r}  "
                     f"in {r['where']}")
    if report.get("invalid_refusal_reasons"):
        lines.append("")
        lines.append("Refusals REJECTED for using a reason outside the vocabulary "
                     f"({', '.join(sorted(REFUSAL_REASONS))}):")
        for b in report["invalid_refusal_reasons"][:10]:
            lines.append(f"  {b['id']}: {b['reason']!r}")
    return {"passed": False, "enforced": enforce, "message": "\n".join(lines)}


def render(report: dict) -> str:
    """One screen for a human reader of the report."""
    if not report.get("n_items"):
        return ("No checkable items were enumerated. That is a statement about "
                "our extraction, not about the paper.")
    pct = 100.0 * report["n_checked"] / report["n_items"]
    out = [f"{report['n_items']} checkable item(s) enumerated "
           f"({report['n_checked']} checked, {pct:.1f}%; "
           f"{report['n_refused']} refused; {report['n_outstanding']} outstanding)."]
    reasons = {k.split(":", 1)[1]: v for k, v in report["by_disposition"].items()
               if k.startswith("refused:")}
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        out.append(f"  {n:5d}  refused: {reason} -- {REFUSAL_REASONS.get(reason, '')}")
    if report["n_outstanding"]:
        out.append(f"  {report['n_outstanding']:5d}  OUTSTANDING -- present in the "
                   "paper and neither checked nor refused. These are invisible in "
                   "the findings, and a reader cannot tell them from a clean pass.")
    return "\n".join(out)

