"""Typed parsing of clinical/scientific table cells.

WHY THIS EXISTS
---------------
The untyped parser read every `X (Y)` cell as `value=X, sd=Y`. In a clinical
Table 1 the modal cell is `142 (71.0)` — a count and a PERCENTAGE — so the
percentage was handed downstream as a standard deviation. Feeding sd=71.0 to
GRIMMER, SPRITE or the SD-range check manufactures impossibilities out of an
entirely ordinary table.

It also silently dropped every format it did not recognise: `median [IQR]`,
`OR (95% CI)` and `median [range]` produced no cell and no warning, so the
tools were starved of input while the extraction reported success.

Both failure modes are upstream of every technique: misparsing generates false
positives, and silent dropping generates false negatives.

DESIGN RULE
-----------
**When the format is ambiguous, say so — never guess.** A cell whose kind
cannot be established is returned as `ambiguous` with the candidate readings
attached. Downstream tools must refuse to run on it rather than pick one.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from . import rounding as _rounding

# Cell kinds we can act on.
CELL_KINDS = (
    "mean_sd",        # 45.2 (12.1)  |  5.4 ± 1.2
    "n_percent",      # 142 (71.0)
    "count_denominator_percent",  # 12/30 (40.0) -- the denominator is PRINTED
    "median_iqr",     # 27.3 [24.1-31.2]
    "median_range",   # 27.3 (12-45)
    "estimate_ci",    # 1.42 (1.08-1.87)
    "mean_se",        # 45.2 (SE 1.3)
    "numeric",        # 45.2
    "count",          # 142
    "ambiguous",      # X (Y) with no disambiguating signal
    "censored",       # <0.001  |  >=65  -- a BOUND, never a point value
    "reference_category",  # 1 [Reference] -- a 1 BY DEFINITION, never measured
    "non_numeric",    # "n/a", "-", text
)

_NUM = r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d*\.?\d+"

# Row/column-label signals. The label is the STRONGEST disambiguator and is
# checked before any numeric heuristic. NOTE two rules enforced in
# `_label_hints` below, both bought by demonstrated mistypings:
#
#  - Labels that imply TWO DIFFERENT kinds refuse rather than resolve. These
#    patterns used to be first-match-wins, so "Age, mean (SD)" sitting in an
#    "n (%)" column typed the cell a definite n_percent -- the row label said
#    the opposite and nothing recorded the conflict. Mixed headers ("Mean (SD)
#    or n (%)") are common in clinical tables precisely because the format
#    varies BY ROW, which is exactly when a column-level hint must not decide.
#  - Ratio abbreviations are CASE-SENSITIVE and live in a separate list. "OR"
#    is an odds ratio; "or" is the English conjunction, and matching it
#    case-insensitively hinted `estimate_ci` onto rows like "Death or MI" and
#    "8th grade education or less".
_LABEL_PATTERNS: list[tuple[str, str]] = [
    # SQUARE BRACKETS ARE THE SAME ANNOTATION. `n [%]` is standard house style
    # exactly where the outer parentheses are already taken -- `Sex (male,
    # n [%])` -- and requiring literal parens meant a table that avoids
    # nesting got NO count/percent checks at all. MEASURED over the
    # eleven-paper run: 142 cells whose own column header states an n sat
    # untyped as `ambiguous` for this reason, and typing them yields 141
    # `consistent`, 1 near-miss and ZERO new accusations.
    (r"\bn\s*[(\[]\s*%\s*[)\]]|\bno\.?\s*[(\[]\s*%\s*[)\]]|\bcount\s*[(\[]\s*%\s*[)\]]|[(\[]\s*%\s*[)\]]", "n_percent"),
    (r"\bmean\s*\(?\s*(sd|s\.d\.|standard deviation)\s*\)?|\bsd\b|±", "mean_sd"),
    (r"\bmean\s*\(?\s*(se|s\.e\.|standard error|sem)\s*\)?|\bse\b|\bsem\b", "mean_se"),
    (r"\bmedian\b.*\b(iqr|interquartile)\b|\biqr\b|\bq1\s*[-–,]\s*q3\b", "median_iqr"),
    (r"\bmedian\b.*\brange\b|\bmedian\b.*\bmin.*max\b", "median_range"),
    (r"\b(95\s*%\s*ci|99\s*%\s*ci|confidence interval|\bci\b)\b", "estimate_ci"),
    (r"\b(odds ratio|risk ratio|hazard ratio|rate ratio)\b", "estimate_ci"),
    # A P-VALUE COLUMN, AND IT IS HERE TO CREATE A CONFLICT RATHER THAN TO
    # RESOLVE ONE. `p_value` is deliberately NOT one of `CELL_KINDS`: no branch
    # below consumes it, and nothing dispatches on it.
    #
    # What it does is make `_label_hints` return TWO kinds for the modal
    # clinical layout -- an "n (%)" ROW crossed with a "P value" COLUMN -- so
    # `hint` becomes None and the cell falls through to `numeric`. Without it,
    # the row label wins alone and `0.014` types as 1.4%; `grim_test_percentage`
    # then returns `impossible` for that percentage at every sample size, so a
    # correctly reported p-value becomes an accusation. MEASURED: 1,097 corpus
    # cells sit under such a header, and while most are already inert (707
    # numeric, 381 non_numeric, 4 count), the 5 that typed `n_percent` are the
    # only firing family in this module with a GUARANTEED rather than a possible
    # false accusation.
    #
    # Conservative by construction: it matches an explicit p-value spelling, or
    # a label that is nothing but "p". It does NOT match a bare trailing "p",
    # because "group p" and "arm p" are variable names, and a hint invented from
    # one would be the guessing this module exists to refuse.
    (r"\bp[\s.\-]*values?\b|\bp[\s.\-]*val\b|^\s*p\s*$|^\s*sig\.?\s*$", "p_value"),
]

# Matched against the ORIGINAL label text, never the lowercased blob: the case
# is the signal.
_LABEL_PATTERNS_CASED: list[tuple[str, str]] = [
    (r"\b(?:OR|RR|HR|IRR|aOR|aHR|aRR)\b", "estimate_ci"),
]

_INTERVAL_SEP = r"(?:\s*(?:-|–|—|to|,|;)\s*)"

# FOOTNOTE MARKERS. A marker is not part of the value and does not make the
# cell's FORMAT ambiguous -- `45.2 (12.1)ᵃ` under a "Mean (SD)" column is a
# mean and an SD however many footnotes it carries -- but every pattern here is
# a `fullmatch`, so one trailing marker sent the whole cell to `non_numeric`.
# That is this module's OTHER named failure mode: a cell the tools never see,
# reported as coverage we did not have. MEASURED over the 103 XML papers in
# `high_value_pdfs_to_run_on/` (49,777 typed cells): 924 `non_numeric` cells
# parse cleanly once a trailing marker is removed -- 451 `numeric`, 161
# `mean_sd`, 128 `estimate_ci`, 110 `ambiguous`, 45 `mean_se`, 21 `count`,
# 8 `n_percent`. 922 of those 924 are recovered by the rule below; `non_numeric`
# falls 18,620 -> 17,698 across the corpus. The dominant marker is the
# significance star (357 `*`, 228 `**`, 227 `***`), then footnote letters
# and `†` (47).
#
# Two character classes only, and the exclusion is the load-bearing half:
#
#  - Unicode superscript LETTERS. `extraction.jats` raises `<sup>a</sup>` to
#    `ᵃ` rather than welding it on as `a`, and a raised letter after a number
#    can only be a marker. The welded ASCII form is deliberately NOT stripped:
#    `12.3a` could be a unit (`12.3 a` = annum), and guessing is what this
#    module exists not to do. Raising the marker is exactly what buys the
#    disambiguation.
#  - The baseline symbols `* † ‡ § ¶ #`, which jats leaves alone because
#    Unicode has no superscript form for them, and which are never units or
#    exponents. Same set `tableparse._clean_extras` already treats as extras.
#
# Superscript DIGITS and SIGNS (⁰-⁹ ⁺ ⁻ ⁼) are excluded. After a number they
# are the EXPONENT form, and reading `10⁻³` as 10 hands a checking tool a value
# 10,000x too large -- the exact error `jats` renders true exponents as `10^-3`
# to avoid. Measured cost of the exclusion: 2 cells of the 924 (both a trailing
# `⁺` significance marker); measured cost of getting it wrong: unbounded.
_SUP_LETTERS = "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ"
_FOOTNOTE_SYMBOLS = "*†‡§¶#"
_TRAILING_MARKER = re.compile(rf"\s*([{_SUP_LETTERS}{_FOOTNOTE_SYMBOLS}]+)\s*$")

# BASELINE ASCII LETTERS, BUT ONLY AFTER A CLOSING BRACKET.
#
# The exclusion above is right for a BARE number and wrong for a bracketed one.
# `12.3a` is genuinely ambiguous -- the `a` could be annum -- which is why
# welded ASCII is not stripped there and must not start being. But
# `5.38 (1.17)a` carries no such ambiguity: a unit does not attach to the far
# side of a closing bracket. Those letters can only be the significance
# subscripts psychology tables use for "means not sharing a subscript differ at
# P < 0.05".
#
# MEASURED, which is why it earns its own rule: in the SI of
# 10.1073/pnas.1523586113 -- the Kouchaki & Gino paper whose duplicated affect
# rows are on PubPeer -- EVERY ONE of the 153 `mean (SD)` cells in Tables S1
# and S2 carries one, so `census.parse_cells` typed 153 of 153 `non_numeric`.
# A table in which every cell fails to parse is not a table with nothing in it,
# and counting it that way is our failure recorded as the paper's property --
# this codebase's oldest bug, and the one the census exists to end.
#
# Deliberately NOT extended to a letter after a bare digit, and deliberately
# not to `{1.17}` or `<1.17>`. Those are FORMAT questions rather than marker
# questions, and inventing a format is what this module refuses to do.
_BRACKETED_TRAILING_LETTERS = re.compile(
    r"(?<=[)\]}])\s*((?:[a-zA-Z]\s*,?\s*)+)$")


# NON-ASCII CHARACTERS THAT CARRY NUMERIC MEANING.
#
# `_NUM` accepts only ASCII `[-+]`, so a cell typeset with the real MINUS SIGN
# U+2212 matches no pattern in this module and falls out as `non_numeric` --
# silently, because `non_numeric` is the destination for genuine text too. That
# is a cell the checking tools never see, reported as coverage we did not have.
#
# MEASURED over the RAW `<td>`/`<th>`/`<entry>` text of the 99 XML papers in
# `high_value_pdfs_to_run_on/` (58,110 cells) -- raw, because that is what every
# path which does NOT run `jats._normalise` hands to `parse_cell`: the PDF text
# layer, the .docx/.xlsx/.csv supplement readers, and any caller passing a
# string through directly. 2,850 cells carry U+2212, 2,789 an en dash, 162 an
# em dash. Mapping them retypes 1,590 cells that are `non_numeric` today, and
# the digit-group rule below adds 56 more, for 1,646: 727 `ambiguous`,
# 445 `numeric`, 302 `estimate_ci`, 80 `count`, 68 `median_iqr`, 20 `mean_sd`,
# 4 `n_percent`. The 302 estimate-plus-CI cells are the ones that matter most:
# an effect estimate with its interval is the highest-value cell on a clinical
# table, and a negative one was being deleted for its typography. The 727 that become `ambiguous` are not usable either,
# but `ambiguous` SAYS so and carries its candidate readings; `non_numeric`
# says the cell held no number, which was false.
#
# NFKC IS NOT USED, and that is deliberate. It does not fix the actual defect
# (U+2212 is left unchanged by NFKC) and it breaks two things this module
# depends on: `12.3ᵃ` becomes `12.3a`, welding a footnote marker onto the value
# where `_TRAILING_MARKER` can no longer see it, and `10⁻³` becomes `10−3`,
# undoing the exponent rendering `extraction.jats` produces precisely so that a
# value 10,000x too large cannot be read off it. MEASURED: NFKC alters 345 of
# 48,588 parsed corpus cells and CHANGES THE PARSE of 75 of them. An explicit
# map of the characters whose numeric meaning is unambiguous does the whole job
# and touches nothing else.
#
# En and em dash map to `-` only for the arithmetic sign; `_INTERVAL_SEP`
# already reads all three as a range separator, so "1.08–1.87" is unaffected
# either way.
#
# EXOTIC SPACES ARE NOT MAPPED TO AN ASCII SPACE, because that would be a change
# with no effect: every pattern in this module separates its tokens with `\s`,
# and Python's `\s` already matches U+00A0, U+2002, U+2003, U+2007, U+2009 and
# U+202F. MEASURED on the same 58,110 raw corpus cells: mapping them rescues
# exactly the same 1,590 cells as mapping the dashes alone. What an exotic space
# DOES break is a GROUPED NUMBER -- "1 234" is `non_numeric` however the space
# is spelled -- and that is the rule below, the only place the character changes
# an answer (+56 cells, all of them `count`).
_UNICODE_REPAIRS = {
    "−": "-",   # MINUS SIGN
    "–": "-",   # EN DASH
    "—": "-",   # EM DASH
    # FULLWIDTH PARENTHESES. A cell reading `88.89%（32）` is a percentage
    # beside its count, and the typer sees no parenthesis at all, so the count
    # never becomes a value. MEASURED 2026-09-03 across 21 supplement .docx
    # files in three corpora: U+FF08 and U+FF09 occur 83 times each, in 81
    # cells of one file -- the mefatinib protocol supplement, whose phase II
    # adverse-event table contributes ZERO groups to the register as a result.
    # Nothing else full-width occurs anywhere in the corpora; in particular
    # the DIGITS are ordinary ASCII, so a repair aimed at them would fix
    # nothing.
    #
    # RESTORES, NEVER INVENTS -- the section 8d Rule 2 line. A fullwidth
    # parenthesis IS a parenthesis; mapping it to ASCII recovers a character
    # the encoding obscured and asserts nothing the paper did not print. That
    # is why it belongs here beside the dashes and NOT with the guarded
    # repairs below, which have to reason about context.
    "（": "(",  # FULLWIDTH LEFT PARENTHESIS
    "）": ")",  # FULLWIDTH RIGHT PARENTHESIS
}
_UNICODE_RE = re.compile("[" + "".join(re.escape(c) for c in _UNICODE_REPAIRS) + "]")

#: Spaces used as DIGIT-GROUP separators ("226 150 662"), REMOVED rather than
#: mapped. Same rule, same guard and same reason as `jats._DIGIT_GROUP`: the
#: lookahead requires exactly three following digits and no fourth, so a plain
#: space between two separate numbers is left alone and two values are never
#: welded into a third the paper never printed. It is repeated here because the
#: PDF text layer and the .docx/.xlsx/.csv supplement readers never pass through
#: `jats._normalise`.
_DIGIT_GROUP = re.compile(r"(?<=\d)[      ](?=\d\d\d(?!\d))")

#: A MIDDLE DOT BETWEEN TWO DIGITS IS A DECIMAL POINT. Lancet, BMJ and the
#: journals that follow their house style set `4·5` rather than `4.5`, and
#: `International Journal of Stroke` does it 158 times in one paper of the
#: eleven-paper run. Unrepaired, `-0·077 (95% CI: -7·716 to -2·437)` reached the
#: register as estimate 77, ci_low 716, ci_high -2: every one of the three
#: numbers wrong, the interval inverted, and `check_estimate_ci` ready to
#: pronounce on it.
#:
#: GUARDED, NOT GLOBAL, for the same reason as `_DIGIT_GROUP` above and the
#: `¼` repair in `dispatch`. A middle dot is a bullet and a separator
#: elsewhere, and this codebase may not rewrite it on sight. Between two digits,
#: in a scientific paper, it can mean nothing else -- and the alternative is
#: splitting one number into two, which is what was happening.
_DECIMAL_MIDDLE_DOT = re.compile(r"(?<=\d)·(?=\d)")


def repair_unicode(text: str) -> tuple[str, int]:
    """`text` with numerically meaningful non-ASCII characters made ASCII.

    Returns `(repaired, n_changed)`. The count is kept so the repair is
    reported rather than performed silently -- a reader has to be able to see
    that the string the tools parsed is not byte-for-byte what the paper
    printed.
    """
    text = text or ""
    n = (len(_UNICODE_RE.findall(text)) + len(_DIGIT_GROUP.findall(text))
         + len(_DECIMAL_MIDDLE_DOT.findall(text)))
    if not n:
        return text, 0
    return _UNICODE_RE.sub(
        lambda m: _UNICODE_REPAIRS[m.group(0)],
        _DECIMAL_MIDDLE_DOT.sub(".", _DIGIT_GROUP.sub("", text))
    ), n


@dataclass
class ParsedCell:
    raw: str
    kind: str
    value: float | None = None
    # kind-specific companions
    sd: float | None = None
    se: float | None = None
    percent: float | None = None
    count: int | None = None
    #: The n a fraction cell PRINTS for itself, as in `12/30 (40.0)`.
    #:
    #: This is the one cell form where a granularity test needs nothing from the
    #: model. Everywhere else the n has to be inferred -- read off a column
    #: header, carried down from a row above, or asked for -- and every one of
    #: those routes can be wrong in a way that manufactures an impossibility.
    #: Here the paper states it, so `bound_source` is "stated" rather than
    #: "assumed", and rulebook rule 4's cap does not apply.
    denominator: int | None = None
    #: The comparison operator of a CENSORED cell -- `<`, `>`, `<=`, `>=`.
    #: `value` then holds the BOUND, which is not the same assertion as a point
    #: value and must not be consumed as one.
    censored: str | None = None
    low: float | None = None
    high: float | None = None
    # PRINTED precision, captured here because this is the last layer that can
    # see it. `101 (71%)` parses to percent=71.0 -- a float that has already
    # lost the fact that the paper printed "71" to zero decimals. Every
    # granularity test needs the printed precision to size its rounding
    # interval, and assuming one decimal too many shrinks that interval tenfold
    # and manufactures impossibilities out of correctly-reported numbers.
    decimals_value: int | None = None
    decimals_sd: int | None = None
    decimals_percent: int | None = None
    # Coarsest printed precision across the estimate and BOTH interval bounds.
    # A comparison among the three is only known to the coarsest of them, so
    # `1.42 (1.1-1.9)` is a 1 dp comparison however finely the estimate is
    # printed. Kept separate from `decimals_value` because the estimate's own
    # precision is what a granularity test on the estimate alone would need.
    decimals_interval: int | None = None
    # Footnote markers removed to reach the value. RECORDED, never dropped: the
    # marker is a pointer into the table's footnotes, and a footnote is where a
    # paper says "n=38 for this row", "log-transformed" or "per 1,000". A tool
    # that consumed the number without knowing a footnote qualified it would be
    # checking a value the paper did not quite assert.
    markers: list[str] = field(default_factory=list)
    # How many characters had to be repaired before this cell would parse: a
    # Unicode minus or dash mapped to ASCII, or a digit-group space removed.
    # RECORDED for the same reason `markers` is: `raw` holds what the paper
    # printed, so without this count nothing says the parsed string differed
    # from it.
    unicode_repairs: int = 0
    candidates: list[str] = field(default_factory=list)
    warning: str | None = None

    def as_dict(self) -> dict:
        d = {"raw": self.raw, "kind": self.kind, "value": self.value}
        # `denominator` WAS MISSING FROM THIS TUPLE. The field above documents
        # itself as "the one cell form where a granularity test needs nothing
        # from the model" -- and then this method dropped it, so the n every
        # `count_denominator_percent` cell PRINTS never reached a consumer.
        # `forensic_kwargs` returned it and `as_dict` did not, which is why the
        # gap survived: the per-cell path saw the number and the table path,
        # which serialises through here, did not.
        for k in ("sd", "se", "percent", "count", "denominator", "low", "high",
                  "decimals_value", "decimals_sd", "decimals_percent",
                  "decimals_interval"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        # THE OPERATOR TRAVELS WITH THE BOUND, for the same reason `denominator`
        # had to: a field the per-cell path can see and the table path cannot is
        # a field that does not exist for half the pipeline. `p < 0.001` and
        # `p = 0.001` are different assertions, and only this tells them apart.
        if self.censored:
            d["censored"] = self.censored
        if self.markers:
            d["markers"] = self.markers
        if self.unicode_repairs:
            d["unicode_repaired"] = self.unicode_repairs
        if self.candidates:
            d["candidates"] = self.candidates
        if self.warning:
            d["warning"] = self.warning
        return d

    def forensic_kwargs(self) -> dict:
        """What a forensic tool may legitimately be given for this cell.

        An ambiguous or unsupported cell yields NOTHING, so a tool cannot be
        run on a value whose meaning is unknown.
        """
        if self.kind == "mean_sd":
            return {"mean": self.value, "sd": self.sd}
        if self.kind == "n_percent":
            return {"count": self.count, "percentage": self.percent}
        if self.kind == "count_denominator_percent":
            # `n` comes from the cell itself, which is the whole point of typing
            # this form separately. A percentage with no n is not checkable; a
            # percentage whose n we inferred is checkable and occasionally
            # wrong. This one is checkable and right.
            out = {"count": self.count, "n": self.denominator}
            if self.percent is not None:
                out["percentage"] = self.percent
            return out
        if self.kind == "estimate_ci":
            return {"estimate": self.value, "ci_low": self.low, "ci_high": self.high}
        return {}


#: A THOUSANDS GROUP CANNOT START WITH ZERO, so `0,561` is a decimal comma and
#: nothing else. This is the ONE part of the decimal-comma question that needs
#: no document context: `74,874` really is undecidable from the cell alone
#: (74.874 in a Russian journal, 74,874 in an American one), but no convention
#: on earth writes seventy-four thousand as `0,561`.
#:
#: MEASURED 2026-08-20, and these were SILENTLY WRONG rather than missing --
#: the worst class this survey found:
#:
#:     "0,001"  ->  count 1.0      a p-value read as 1
#:     "0,056"  ->  count 56.0
#:     "0,561"  ->  count 561.0
#:     "0,932 ± 0,011"  ->  mean 932.0, sd 11.0   and this goes to GRIM
#:
#: One Russian paper in the corpus carries 58 such numbers -- Mann-Whitney
#: statistics between 0 and 1, every one read as a three-digit integer.
#:
#: The AMBIGUOUS case is deliberately untouched: `74,874` still reads as
#: thousands, because deciding it needs the document's convention and guessing
#: is what produced these four lines.
#: THE REFERENCE CATEGORY OF A REGRESSION TABLE. `1 [Reference]` is the level
#: every other level's odds ratio is expressed against, so its 1 is TRUE BY
#: CONSTRUCTION -- not a measured quantity, and nothing a check can confirm or
#: refute. It has no interval because it cannot have one.
#:
#: MEASURED 2026-08-20: 510 occurrences across the JAMA/psychology stratum,
#: sitting inside odds-ratio rows -- `"Suicide AOR (95% CI)", "1 [Reference]",
#: "2.60 (1.46 to 4.66)", ...` -- and ZERO in the 284-paper cerebrolysin
#: corpus. It is a convention of a literature, not of a journal, which is why
#: it went unseen until the survey widened the frame.
#:
#: Recorded rather than dropped, because the row is real and a reader tracing
#: an odds ratio needs to see what it is relative to.
_REFERENCE_CATEGORY = re.compile(
    r"^\s*(1(?:[.,\u00b7]0+)?)\s*[\[(]\s*ref(?:erence|erent|\.)?\s*[\])]\s*$", re.I)

#: A cell that is only a bound: an operator then a number, nothing else. Bare
#: `p` prefixes (`p < 0.001`) are included because a p-value column prints them.
_CENSORED = re.compile(
    r"^\s*[Pp]?\s*(<=|>=|<|>|\u2264|\u2265)\s*([0-9]*[.,\u00b7]?[0-9]+)\s*$")

_ZERO_COMMA = re.compile(r"(?<![\d,.])0,(\d+)")


#: The genuinely ambiguous form: exactly three digits after the comma and a
#: whole part that could be a thousands group. `74,874` is 74.874 in a Russian
#: journal and seventy-four thousand in an American one, and BOTH conventions
#: are attested in this corpus -- so this one is decidable only from the
#: document, never from the cell.
_AMBIGUOUS_COMMA = re.compile(r"(?<![\d,.])([1-9]\d{0,2}),(\d{3})(?!\d)")

#: How many decisive witnesses a document must show before its ambiguous commas
#: are read as decimals. MEASURED 2026-08-20 over the 309-paper corpus: the 27
#: papers whose table cells carry a `0,nnn` witness carry between 14 and 204 of
#: them, so any small threshold separates them from noise, and three keeps a
#: single stray typo from deciding a document.
_CONVENTION_WITNESSES = 3


def infer_decimal_convention(texts) -> dict:
    """Which character this document uses as its decimal separator.

    DECIDED FROM WITNESSES, NOT FROM LANGUAGE OR PUBLISHER. The only decisive
    evidence is a comma number a thousands reading cannot explain -- `0,561`,
    since no convention writes a thousands group starting with zero. Counting
    those is enough: MEASURED over the corpus, every paper that has BOTH
    witnesses and ambiguous commas has ZERO point-decimals, so the two
    populations do not overlap in practice.

    A citation list is why the witness must be the leading-zero form and
    nothing else. `[7,8]` and `[10,11]` are commas between digits in every
    English paper ever written, and an earlier version of this rule -- "fewer
    than three digits after the comma means decimal" -- would have read them as
    decimals. `[0,056]` is not a thing anybody writes.

    Returns the verdict with its evidence, so the decision is auditable rather
    than asserted: `unknown` when nothing witnesses it, which leaves the
    ambiguous cells exactly as they were.
    """
    witnesses = points = ambiguous = 0
    for t in texts or ():
        t = str(t or "")
        witnesses += len(_ZERO_COMMA.findall(t))
        points += len(re.findall(r"(?<![\d,.])\d+\.\d+", t))
        ambiguous += len(_AMBIGUOUS_COMMA.findall(t))
    comma = witnesses >= _CONVENTION_WITNESSES and witnesses > points
    return {"separator": "comma" if comma else "unknown",
            "n_witnesses": witnesses, "n_point_decimals": points,
            "n_ambiguous": ambiguous,
            "why": (f"{witnesses} number(s) of the form `0,nnn`, which a "
                    f"thousands reading cannot explain, against {points} "
                    f"point-decimal(s)" if comma else
                    f"only {witnesses} decisive witness(es); ambiguous commas "
                    f"are left as they were rather than guessed")}


def decimal_comma_repair(text: str, ambiguous_too: bool = False) -> str:
    """`0,561` -> `0.561`, where a thousands reading is impossible.

    `ambiguous_too` additionally converts `74,874`, and may be set ONLY from a
    document-level verdict -- see `infer_decimal_convention`. Guessing it per
    cell is what read a p-value of 0.001 as 1.
    """
    out = _ZERO_COMMA.sub(lambda m: "0." + m.group(1), str(text or ""))
    if ambiguous_too:
        out = _AMBIGUOUS_COMMA.sub(lambda m: f"{m.group(1)}.{m.group(2)}", out)
    return out


def _f(text: str) -> float | None:
    try:
        return float(decimal_comma_repair(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# Decimal places as PRINTED in the source text -- "71" -> 0, "71.0" -> 1,
# "1,234.56" -> 2, and None when the text is not a parseable number, so callers
# can tell "printed to zero decimals" from "unknown". This parser is where
# printed precision enters the toolkit; the definition lives in `rounding` so
# every check downstream measures it the same way.
_dp = _rounding.decimals_of_text


def _label_hints(*labels: str | None) -> list[str]:
    """Every distinct kind the row/column labels imply, in pattern order."""
    orig = " ".join(str(x) for x in labels if x)
    if not orig.strip():
        return []
    blob = orig.lower()
    kinds: list[str] = []
    for pattern, kind in _LABEL_PATTERNS:
        if kind not in kinds and re.search(pattern, blob, re.IGNORECASE):
            kinds.append(kind)
    for pattern, kind in _LABEL_PATTERNS_CASED:
        if kind not in kinds and re.search(pattern, orig):
            kinds.append(kind)
    return kinds


def label_hint(*labels: str | None) -> str | None:
    """Infer the cell kind from its row/column labels.

    Returns None both when NO pattern matches and when the labels imply
    CONFLICTING kinds -- a "mean (SD)" row inside an "n (%)" column. The two
    cases are deliberately not distinguished here: neither licenses a reading,
    and `parse_cell` reports the conflict as `ambiguous` with the competing
    kinds as candidates.
    """
    hints = _label_hints(*labels)
    return hints[0] if len(hints) == 1 else None


def parse_cell(raw: str, row_label: str | None = None, col_label: str | None = None,
               decimal_comma: bool = False) -> ParsedCell:
    """Classify and parse one table cell.

    Resolution order: non-ASCII numeric characters mapped to ASCII (recorded in
    `unicode_repairs`) -> explicit in-cell syntax -> label hint -> numeric
    heuristics -> retry with a trailing footnote marker stripped (and recorded
    in `markers`) -> `ambiguous` / `non_numeric`.

    `raw` always holds the cell AS PRINTED, before the character repair, so a
    reader can still see the source text.
    """
    text = (raw or "").strip()
    repaired, n_repairs = repair_unicode(text)
    if decimal_comma:
        # ONLY from a document-level verdict -- see `infer_decimal_convention`.
        repaired = decimal_comma_repair(repaired, ambiguous_too=True)
    cell = _parse_cell(repaired, row_label, col_label)
    # `raw` ALWAYS HOLDS THE CELL AS PRINTED, which is this function's own
    # promise and was briefly broken: the restore was conditional on a UNICODE
    # repair having happened, so a separator repair with no unicode repair left
    # `74,874` showing as `74.874` -- the register quoting a string the paper
    # never printed, in the field a reader checks the claim against.
    if n_repairs or repaired != text:
        cell.raw = text
    if n_repairs:
        cell.unicode_repairs = n_repairs
    return cell


def _parse_cell(raw: str, row_label: str | None = None, col_label: str | None = None) -> ParsedCell:
    """`parse_cell` on text whose characters are already ASCII."""
    text = (raw or "").strip()
    if not text:
        return ParsedCell(raw=raw or "", kind="non_numeric")

    # A CENSORED VALUE IS A BOUND, AND IT WAS BEING DROPPED ENTIRELY.
    # `<0.001`, `<.0001`, `>0.99`, `\u22657.0` all returned `non_numeric`, so
    # roughly 93 cells across the surveyed corpus -- most of them p-values --
    # were invisible to every check. The PROSE path has read them since it was
    # written (`values.prose_values` records the bound and lets `printed` carry
    # the qualifier); the cell path never did. One quantity, two answers.
    #
    # `value` holds the bound and `censored` holds the operator, so a consumer
    # can tell `p < 0.001` from `p = 0.001`. Reading the first AS the second
    # hands a checker a precision the paper never claimed -- which is why the
    # operator is a field and not a note in the text.
    m = _REFERENCE_CATEGORY.match(text)
    if m:
        # THE VALUE IS ASSERTED, NOT PARSED, because it is 1 BY DEFINITION --
        # that is the whole meaning of a reference category. Parsing it went
        # wrong immediately: `_f("1,00")` strips the comma as a thousands
        # separator and returns 100.0, so the one cell in the table whose value
        # is certain came out a hundredfold wrong. The printed form still
        # supplies the precision, since `1.00` and `1` assert different
        # precisions even when they assert the same number.
        printed = m.group(1).replace(",", ".").replace("\u00b7", ".")
        return ParsedCell(raw=raw or "", kind="reference_category",
                          value=1.0, decimals_value=_dp(printed))

    m = _CENSORED.match(text)
    if m:
        bound = _f(m.group(2))
        if bound is not None:
            op = m.group(1).replace("\u2264", "<=").replace("\u2265", ">=")
            return ParsedCell(raw=raw or "", kind="censored", value=bound,
                              censored=op,
                              decimals_value=_dp(m.group(2)))

    hints = _label_hints(row_label, col_label)
    hint = hints[0] if len(hints) == 1 else None

    # --- unambiguous in-cell syntax -------------------------------------
    m = re.fullmatch(rf"\s*({_NUM})\s*(?:±|\+/-|\+-)\s*({_NUM})\s*", text)
    if m:
        return ParsedCell(raw=text, kind="mean_se" if hint == "mean_se" else "mean_sd",
                          value=_f(m.group(1)),
                          decimals_value=_dp(m.group(1)), decimals_sd=_dp(m.group(2)),
                          **({"se": _f(m.group(2))} if hint == "mean_se"
                             else {"sd": _f(m.group(2))}))

    # k/n (p) and k/n (p%) and bare k/n -- an explicit fraction, optionally with
    # its percentage. MEASURED 2026-08-09 and again 2026-08-17: `12/30 (40.0)`
    # typed `non_numeric` and was skipped by every downstream check, both before
    # and after that day's parse-layer fixes, so the gap is original rather than
    # introduced. The direction is safe -- coverage lost, never a false
    # accusation -- which is why it waited, but it is a real loss: this cell
    # carries MORE information than `12 (40.0)` does, and it was worth less.
    #
    # THE DATE TRAP is why the bare form is treated differently. `12/30` in a
    # clinical table is a responder count; `12/30` in a date column is the 30th
    # of December. With the percentage present the reading is settled -- a date
    # does not come with a percentage, and 100*12/30 = 40.0 confirms it. Without
    # it, a cell whose two integers would also make a calendar date stays
    # ambiguous rather than being guessed at.
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*(?:[\(\[]\s*([\d.]+)\s*%?\s*[\)\]])?\s*",
                     text)
    if m:
        k, n = int(m.group(1)), int(m.group(2))
        pct_txt = m.group(3)
        if k <= n and n > 0:
            if pct_txt is not None:
                return ParsedCell(
                    raw=text, kind="count_denominator_percent",
                    value=float(k), count=k, denominator=n,
                    percent=_f(pct_txt), decimals_value=0,
                    decimals_percent=_dp(pct_txt))
            could_be_a_date = 1 <= k <= 12 and 1 <= n <= 31
            if not could_be_a_date:
                return ParsedCell(
                    raw=text, kind="count_denominator_percent",
                    value=float(k), count=k, denominator=n, decimals_value=0)
            return ParsedCell(
                raw=text, kind="ambiguous", value=float(k),
                candidates=["count_denominator_percent", "date"],
                warning=(f"'{text}' is either {k} of {n} or a calendar date, "
                         "and nothing in the cell settles it. No forensic tool "
                         "may run on it. A row or column label naming a count, "
                         "a proportion or a date would resolve it."))

    m = re.fullmatch(rf"\s*({_NUM})\s*%\s*", text)
    if m:
        return ParsedCell(raw=text, kind="n_percent", percent=_f(m.group(1)),
                          decimals_percent=_dp(m.group(1)))

    # X (SE 1.3) / X (SD 1.3)
    m = re.fullmatch(rf"\s*({_NUM})\s*[\(\[]\s*(sd|se|sem)\s*[:=]?\s*({_NUM})\s*[\)\]]\s*",
                     text, re.IGNORECASE)
    if m:
        val, tag, comp = _f(m.group(1)), m.group(2).lower(), _f(m.group(3))
        dpv, dpc = _dp(m.group(1)), _dp(m.group(3))
        return (ParsedCell(raw=text, kind="mean_sd", value=val, sd=comp,
                           decimals_value=dpv, decimals_sd=dpc) if tag == "sd"
                else ParsedCell(raw=text, kind="mean_se", value=val, se=comp,
                                decimals_value=dpv, decimals_sd=dpc))

    # X (a-b) or X [a-b]  -> an INTERVAL; never a mean/SD pair
    m = re.fullmatch(rf"\s*({_NUM})\s*[\(\[]\s*({_NUM}){_INTERVAL_SEP}({_NUM})\s*[\)\]]\s*", text)
    if m:
        val, lo, hi = _f(m.group(1)), _f(m.group(2)), _f(m.group(3))
        bracket = "[" in text
        dpv = _dp(m.group(1))
        dpi = _rounding.coarsest_decimals(m.group(1), m.group(2), m.group(3))
        interval_kinds = ("median_iqr", "median_range", "estimate_ci")

        if len(hints) == 1 and hints[0] in interval_kinds:
            # The label is the authority. If the numbers then disagree with the
            # labelled reading (an estimate outside its own labelled CI), that
            # is the CHECKER's legitimate finding about the paper, not ours.
            kind = hints[0]
        elif hints:
            # Labels that conflict, or that contradict the syntax (an "n (%)"
            # label over an interval cell): the reading is not established.
            return ParsedCell(
                raw=text, kind="ambiguous", value=val, decimals_value=dpv,
                candidates=[h for h in hints if h in interval_kinds] or list(interval_kinds),
                warning=(
                    f"'{text}' holds an interval, but the row/column labels imply "
                    f"{', '.join(hints)}. The reading is not established, so no "
                    "forensic tool may run on this cell."
                ),
            )
        else:
            # NO LABEL. The default guess (bracket -> median_iqr, paren ->
            # estimate_ci) may stand only where it cannot accuse. Typed
            # `estimate_ci`, this cell goes to check_estimate_ci, and an
            # ordinary SKEWED median (IQR) -- `5 (3-15)`, the modal way
            # length-of-stay is printed -- came back `suspicious`: "the
            # estimate 5 is not the arithmetic midpoint of [3, 15]". Our
            # guess, reported in the grammar of a claim about the paper. So
            # the guess is kept only when the numbers FIT the guessed reading;
            # a value outside its interval, or off both midpoints, is refused.
            tol = _rounding.half_width(dpi) if dpi is not None else 0.0
            usable = val is not None and lo is not None and hi is not None
            if not (usable and lo - tol <= val <= hi + tol):
                return ParsedCell(
                    raw=text, kind="ambiguous", value=val, decimals_value=dpv,
                    candidates=list(interval_kinds),
                    warning=(
                        f"'{text}': the leading value lies outside the parenthetical "
                        "interval, so it is neither an estimate inside its CI nor a "
                        "median inside its IQR/range. No label disambiguated it, so "
                        "no forensic tool may run on this cell."
                    ),
                )
            if not bracket:
                # Same slack check_estimate_ci itself applies before flagging.
                arith = (lo + hi) / 2
                fits = abs(val - arith) <= max(3 * tol, 0.10 * abs(arith))
                if not fits and lo > 0 and val > 0:
                    geo = math.exp((math.log(lo) + math.log(hi)) / 2)
                    fits = abs(val - geo) <= max(3 * tol, 0.10 * abs(geo))
                if not fits:
                    return ParsedCell(
                        raw=text, kind="ambiguous", value=val, decimals_value=dpv,
                        candidates=list(interval_kinds),
                        warning=(
                            f"'{text}': the value sits at neither the arithmetic nor "
                            "the geometric midpoint of the interval -- the shape of a "
                            "skewed median with its IQR or range, not of an estimate "
                            "with its CI. No label disambiguated it, so no forensic "
                            "tool may run on this cell."
                        ),
                    )
            kind = "median_iqr" if bracket else "estimate_ci"
        return ParsedCell(raw=text, kind=kind, value=val, low=lo, high=hi,
                          decimals_value=dpv, decimals_interval=dpi)

    # X (y%) -> explicit percentage
    m = re.fullmatch(rf"\s*({_NUM})\s*[\(\[]\s*({_NUM})\s*%\s*[\)\]]\s*", text)
    if m:
        v = _f(m.group(1))
        return ParsedCell(raw=text, kind="n_percent", count=int(v) if v is not None and
                          float(v).is_integer() else None, value=v, percent=_f(m.group(2)),
                          decimals_value=_dp(m.group(1)), decimals_percent=_dp(m.group(2)))

    # --- the genuinely ambiguous case: X (Y) ----------------------------
    m = re.fullmatch(rf"\s*({_NUM})\s*[\(\[]\s*({_NUM})\s*[\)\]]\s*", text)
    if m:
        x, y = _f(m.group(1)), _f(m.group(2))
        dpx, dpy = _dp(m.group(1)), _dp(m.group(2))
        # The parenthetical's printed precision is recorded on the AMBIGUOUS
        # returns too, under both names it could take. dispatch resolves an
        # ambiguous cell from a declared variable by copying this dict, and
        # without these the resolved cell fell back to a default `decimals`
        # and the check sized its rounding interval off the wrong precision.
        ambiguous_dp = {"decimals_value": dpx, "decimals_sd": dpy,
                        "decimals_percent": dpy}
        if len(hints) >= 2:
            return ParsedCell(
                raw=text, kind="ambiguous", value=x, candidates=list(hints),
                warning=(
                    f"'{text}': the row and column labels imply conflicting formats "
                    f"({', '.join(hints)}) -- a per-row format inside a mixed column, "
                    "or a mixed header. Refused rather than resolved by precedence; "
                    "no forensic tool may run on this cell."
                ),
                **ambiguous_dp,
            )
        if hint == "n_percent":
            # The label can be right for the COLUMN and wrong for the ROW: the
            # Age row inside an "n (%)" table is mean (SD). An n (%) reading
            # needs an integer count and a percentage in [0, 100]; a cell that
            # fails either is not what the label says it is.
            if (x is None or not float(x).is_integer()
                    or y is None or not 0 <= y <= 100):
                return ParsedCell(
                    raw=text, kind="ambiguous", value=x,
                    candidates=["n_percent", "mean_sd", "estimate_ci"],
                    warning=(
                        f"'{text}' sits under an n (%) label but does not fit that "
                        "reading (the count is not an integer, or the percentage is "
                        "outside [0, 100]) -- the label likely does not govern this "
                        "row. No forensic tool may run on this cell."
                    ),
                    **ambiguous_dp,
                )
            return ParsedCell(raw=text, kind="n_percent",
                              count=int(x), value=x, percent=y,
                              decimals_value=dpx, decimals_percent=dpy)
        if hint in ("mean_sd", "mean_se"):
            return (ParsedCell(raw=text, kind="mean_sd", value=x, sd=y,
                               decimals_value=dpx, decimals_sd=dpy) if hint == "mean_sd"
                    else ParsedCell(raw=text, kind="mean_se", value=x, se=y,
                                    decimals_value=dpx, decimals_sd=dpy))
        if hint in ("median_iqr", "median_range"):
            # A single parenthetical under a median label is the IQR/range
            # WIDTH -- a dispersion. It is NOT a bound: typing it into `low`
            # asserted a quartile the paper never printed, and median kinds'
            # low/high may be harvested as stated bounds for other checks.
            return ParsedCell(
                raw=text, kind=hint, value=x, decimals_value=dpx,
                warning=(
                    f"'{text}': single parenthetical under a median label read as a "
                    "dispersion width; the interval bounds are unknown."
                ),
            )
        if hint == "estimate_ci":
            # The label promises TWO bounds; one number does not fit it. The
            # cell could be an estimate (SE), or an interval split across
            # columns -- either way the labelled reading fails and guessing a
            # replacement is what this module exists not to do.
            return ParsedCell(
                raw=text, kind="ambiguous", value=x,
                candidates=["estimate_ci", "mean_se", "mean_sd"],
                warning=(
                    f"'{text}' sits under an estimate (CI) label but holds a single "
                    "parenthetical value -- possibly an SE, possibly a truncated "
                    "interval. No forensic tool may run on this cell."
                ),
                **ambiguous_dp,
            )

        # No label signal. `X (Y)` with a large integer beside a value in
        # [0, 100] is n (%) more often than mean (SD) -- but "more often" is a
        # guess, and a guessed n_percent DISPATCHES: `154 (23.4)` (a mean
        # cholesterol with its SD) fed grim_percentage, which returns
        # `impossible` for 23.4% at n=180. The likeliest reading leads the
        # candidates so a DECLARED variable can still resolve the cell in
        # dispatch -- resolution from a declaration is the recovery path; a
        # numeric shape is not.
        x_is_count = x is not None and float(x).is_integer() and x >= 0
        y_is_pct_like = y is not None and 0 <= y <= 100
        if x_is_count and y_is_pct_like and x > 100 and y <= 100:
            return ParsedCell(
                raw=text, kind="ambiguous", value=x,
                candidates=["n_percent", "mean_sd", "estimate_ci"],
                warning=(
                    f"'{text}': a large integer beside a value in [0, 100] is most "
                    "often n (%), but no label says so and a mean with its SD fits "
                    "the same shape. Declare the variable's family to resolve it; "
                    "no forensic tool may run on a guessed reading."
                ),
                **ambiguous_dp,
            )
        return ParsedCell(
            raw=text, kind="ambiguous", value=x,
            candidates=["mean_sd", "n_percent", "estimate_ci"],
            warning=(
                f"'{text}' could be mean (SD), n (%), or estimate (CI). No row/column label "
                "disambiguated it, so no forensic tool may run on this cell."
            ),
            **ambiguous_dp,
        )

    # bare number
    m = re.fullmatch(rf"\s*({_NUM})\s*", text)
    if m:
        v = _f(m.group(1))
        dpv = _dp(m.group(1))
        # A PERCENTAGE HAS TO BE IN [0, 100]. The label branch above had no
        # range guard while the paired branch at 498-499 always has, so a bare
        # number under an "n (%)" header became a percentage WHATEVER its value:
        # `parse_cell("576", "Total participants", "No. (%)")` returned
        # `percent=576.0`, and that payload reached two archived runs. The same
        # unguarded branch types a p-value of 0.014 as 1.4%, and
        # `grim_test_percentage` returns `impossible` for it at every n tested.
        #
        # Falling through costs nothing: `count` and `numeric` are both in
        # NEVER_DISPATCH, so a cell refused here was never going to be checked.
        # It only stops being checked under a reading that was false.
        if hint == "n_percent" and v is not None and 0 <= v <= 100:
            return ParsedCell(raw=text, kind="n_percent", percent=v, decimals_percent=dpv)
        if v is not None and float(v).is_integer():
            return ParsedCell(raw=text, kind="count", value=v, count=int(v),
                              decimals_value=dpv)
        return ParsedCell(raw=text, kind="numeric", value=v, decimals_value=dpv)

    # --- last resort: a trailing footnote marker ------------------------
    # Deliberately LAST, after every pattern above has declined. Retrying only
    # on the path that was already going to return `non_numeric` means no cell
    # that types today can be retyped by this branch -- the change can add
    # coverage and cannot move an existing verdict.
    #
    # `raw` keeps the ORIGINAL text including the marker, so the record of what
    # the paper printed survives the strip and a reader can find the footnote.
    m = _TRAILING_MARKER.search(text) or _BRACKETED_TRAILING_LETTERS.search(text)
    if m and text[: m.start()].strip():
        inner = parse_cell(text[: m.start()].strip(), row_label, col_label)
        # A marker alone does not rescue an unreadable cell: `n/a*` is still
        # non-numeric, and reporting it as anything else would be the silent
        # guessing this module refuses. Only a real parse is kept.
        if inner.kind != "non_numeric":
            inner.raw = text
            # One token per RUN of the same character, because the two marker
            # conventions differ: `***` is one marker (a threshold tier -- `*`
            # and `***` mean different p-values and must not both read as "*"),
            # while `ᵃᵇ` is two footnotes. Splitting per run gets both right
            # without interpreting either.
            # Separators are not markers. `1.25 (0.37)b,c` carries TWO
            # footnotes, not three tokens one of which is a comma.
            inner.markers = [g.group(0)
                             for g in re.finditer(r"(.)\1*", m.group(1))
                             if g.group(0).strip(", \t")]
            return inner

    return ParsedCell(raw=text, kind="non_numeric",
                      warning=f"could not parse '{text}' as a numeric cell")


def parse_cells(cells: list[dict], decimal_comma: bool = False) -> dict:
    """Type a list of `{raw, row_label, col_label}` cells and summarise coverage.

    The summary is the honest answer to "how much of this table did we
    actually understand", which the untyped parser could not report because it
    dropped what it could not read.
    """
    parsed, kinds = [], {}
    markers: set[str] = set()
    n_marked = 0
    n_repaired = 0
    for c in cells:
        pc = parse_cell(c.get("raw", ""), c.get("row_label"), c.get("col_label"),
                        decimal_comma=decimal_comma)
        d = pc.as_dict()
        d["row_label"] = c.get("row_label")
        d["col_label"] = c.get("col_label")
        # THE COORDINATES TRAVEL WITH THE CELL. This function used to copy the
        # two LABELS and drop the two INDICES, so the walker emitted a physical
        # position and the register recorded `col: None` on every group -- the
        # third instance today of the same seam defect, where a producer selects
        # a few keys from a larger record and the information dies between two
        # functions that both had it.
        #
        # `col_label` is not an address: on 10.1002--ajcp.70049 Table 2, whose
        # header is three identical `Coefficient` spans, 42 cells share 18
        # distinct `(row_label, col_label)` pairs. `(row, col)` separates all
        # 42, and `data[row - 1][col]` round-trips to `raw`.
        for _k in ("row", "col"):
            if c.get(_k) is not None:
                d[_k] = c[_k]
        parsed.append(d)
        kinds[pc.kind] = kinds.get(pc.kind, 0) + 1
        if pc.markers:
            n_marked += 1
            markers.update(pc.markers)
        if pc.unicode_repairs:
            n_repaired += 1
    n = len(parsed)
    unusable = kinds.get("ambiguous", 0) + kinds.get("non_numeric", 0)
    # ONE aggregate warning, not one per cell. 924 of 49,777 corpus cells carry
    # a marker; per-cell warnings would bury the ambiguity warnings that mean a
    # tool must not run, and the two are not equally urgent.
    marker_warning = (
        f"{n_marked} of {n} cell(s) carried a footnote marker "
        f"({', '.join(sorted(markers))}), stripped to reach the value and recorded in each "
        "cell's `markers`. Read the table footnotes before using them: a marker can restrict "
        "the row's n, name a transformation, or change the units."
    ) if n_marked else None
    # WHAT WAS REPAIRED, AND WHAT IS STILL DISCARDED. One aggregate line, for
    # the same reason the marker warning is aggregated. Both halves are stated:
    # a repair means the parsed string is not byte-for-byte the printed one,
    # and the residue is the honest measure of how much of this table the
    # toolkit still cannot read.
    repair_warning = (
        f"{n_repaired} of {n} cell(s) were typeset with non-ASCII numeric "
        "characters -- a Unicode minus or dash mapped to ASCII, or a "
        "digit-group space removed -- before parsing. Each carries "
        "`unicode_repaired`, and its `raw` is the text as printed. "
        f"{kinds.get('non_numeric', 0)} cell(s) remain non_numeric and "
        f"{kinds.get('ambiguous', 0)} remain ambiguous after the repair -- "
        "those were NOT read, and no tool may run on them."
    ) if n_repaired else None
    # WHAT WE COULD NOT READ, DIAGNOSED RATHER THAN COUNTED. Unconditional, and
    # computed here rather than offered as a separate tool anyone could decline
    # to call: a `non_numeric` count is a number nobody acts on, while "36 cells
    # share the shape `<9.9` and none of them parsed" names an unhandled
    # convention and can be fixed. This module's two worst historical bugs were
    # both a whole table failing one way at a time, and both went unnoticed for
    # exactly as long as the failure was reported per cell.
    from .cellformat import cluster_unparsed
    unparsed = cluster_unparsed(
        [{"raw": p.get("raw"), "kind": p.get("kind"), "col_label": p.get("col_label")}
         for p in parsed])
    return {
        "cells": parsed,
        "n_cells": n,
        "kind_counts": kinds,
        "n_unusable": unusable,
        "n_footnote_marked": n_marked,
        "n_unicode_repaired": n_repaired,
        "coverage": round(1 - unusable / n, 3) if n else 0.0,
        "unparsed": unparsed,
        "warnings": ([p["warning"] for p in parsed if p.get("warning")]
                     + ([marker_warning] if marker_warning else [])
                     + ([repair_warning] if repair_warning else [])
                     + list(unparsed.get("warnings") or [])),
        "severity": "indeterminate",
        "methodology": (
            "Typed cell parsing: each cell classified by in-cell syntax, then row/column "
            "label, then once more with a trailing footnote marker removed and recorded. "
            "Conflicting labels, label-syntax contradictions and unlabelled X (Y) cells "
            "are reported as ambiguous rather than guessed, so no tool runs on a value "
            "of unknown meaning; a declared variable can still resolve them downstream."
        ),
    }
