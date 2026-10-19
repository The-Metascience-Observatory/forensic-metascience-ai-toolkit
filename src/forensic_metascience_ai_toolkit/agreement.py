"""Two readings of one page, and where they disagree about a NUMBER.

The architecture this module implements was arrived at twice independently: by
measuring our own corpus, and by a survey of the paid extraction market. Both
land in the same place, and the reasoning is worth keeping because it is not
obvious.

A PDF whose font declares glyphs with no Unicode mapping corrupts its own text
layer. MEASURED here: the same `±` in one paper reaches us as `/C6` from
pdf2mdjson, `\\x06` from docling and `\\x02` from PyMuPDF, and all three report
ZERO literal `±`. Reading rendered pixels instead escapes that entirely -- and
introduces a different failure, because a recogniser hallucinates. MEASURED on
the 22 damaged papers: full-page OCR cleared 988 glyph artefacts to zero and
recovered 14% more statistics, while inventing CJK characters inside numeric
table cells in 6 of them (`1.9 ± 0.1` came back as `1'0干61`).

SO NEITHER READING CAN BE TRUSTED ALONE, AND THAT IS THE POINT. The two fail in
UNRELATED ways: a broken CMap is deterministic and systematic, a recogniser
error is stochastic and local. Where both readings of a page agree on a number,
that number survived two unrelated failure modes. Where they disagree, exactly
one of them is wrong and a human has to look.

This turns a silent corruption into an auditable signal, which is the thing this
repository is for. It does NOT tell you which reading is right -- it cannot, and
claiming otherwise would be the guess the whole toolkit refuses.
"""

from __future__ import annotations

import re
from collections import Counter

def _numbers(text: str) -> Counter:
    """The numbers in this reading, as a multiset.

    THE SIGN IS PART OF THE NUMBER, and this function used to drop it. It
    carried its own pattern -- three alternatives, none of them allowing a
    leading `-` -- so `-1.6` was read as `1.6`. MEASURED over 2,340 real labels
    and cells from the eleven-paper run, 73 of them parsed differently from
    `numerals.NUMERAL`, and every single difference was a negative number read
    as its absolute value.

    That made this comparison BLIND TO THE ONE CORRUPTION IT WOULD BE MOST
    USEFUL FOR. Two readings of a page, one saying `-1.6` and the other `1.6`,
    produced identical multisets and were reported as agreeing -- while the
    documented headline defect of this whole workstream is exactly that: a
    printed effect of `-0.85 (95% CI -1.2, -0.3)` reaching a check as POSITIVE
    0.85, and twenty-one means arriving with the wrong sign in one paper's
    tables. A sign flip inverts a conclusion; there is no error here worth
    catching that matters more.

    So it reads `numerals.tokens` now, which is the hardened pattern plus the
    guard that keeps `COVID-19` from yielding -19.

    Thousands separators and a leading `+` are normalised away before
    comparison, because the two extractors disagree about those for reasons
    that are not about the digits. A leading `-` is never normalised away, for
    reasons that are entirely about the digits.
    """
    from .numerals import tokens
    # `·` FOLDED TO `.` FOR COMPARISON ONLY. Two readings of the same page
    # will both carry the middle dot, but a reading compared against a plain
    # one must not disagree about a typographic mark when the digits match.
    # Same rule as the comma and the leading `+`: normalise what is not about
    # the digits, never the sign, which is.
    # `−` FOLDED TO `-`, WHICH IS A GLYPH AND NOT A SIGN. Two readings of one
    # page can spell the same negative number with different minus characters;
    # that is typography. Dropping the sign is not, and is the defect this
    # function was fixed for hours earlier.
    return Counter(m.group(0).replace(",", "").replace("·", ".")
                   .replace("−", "-").lstrip("+")
                   for m in tokens(text or ""))



#: Page furniture that is not the paper's own text. A publisher's download
#: stamp carries an ISSN, a year and a volume, and every extractor reads it
#: identically -- so leaving it in inflates every agreement figure without
#: telling anyone anything about the science.
_FURNITURE = re.compile(
    r"(?i)downloaded from|wiley online library|terms and conditions"
    r"|creative commons|onlinelibrary\.wiley|see the terms")


def analytic_only(text: str) -> str:
    """`text` cut down to the part a forensic check would actually read.

    Three cuts, in order: stop at the bibliography, keep only ANALYTIC sections,
    drop publisher download stamps.

    WHY THIS IS NOT OPTIONAL FOR A COMPARISON. MEASURED over 21 papers with two
    commercial extractions each, the whole-document agreement between Mistral
    and Mathpix is 0.924 and the analytic-only agreement is 0.887. The
    difference is not noise -- it is a reference list. Bibliographies and
    download stamps are plain text that every extractor reads identically, so
    including them adds a large block of guaranteed agreement and flatters
    whichever comparison you are running.

    The retained fraction is close across sources -- measured at 70-93% of each
    document, and within a few points of each other on the same paper -- so this
    is trimming shared furniture rather than trimming one side more than the
    other.
    """
    if not text:
        return ""
    from . import completeness as _c, sections as _s
    body = text[:_c._body_end(text)]
    secs = _s.map_sections(body)
    keep = [body[x["start"]:x["end"]] for x in secs if x["kind"] == _s.ANALYTIC]
    joined = "\n".join(keep) if keep else body
    return "\n".join(l for l in joined.splitlines() if not _FURNITURE.search(l))


def compare(a: str, b: str, *, label_a: str = "a", label_b: str = "b",
            analytic: bool = False) -> dict:
    """Where two readings of one document disagree about numbers.

    Returns counts and the disagreeing literals, as a MULTISET difference: a
    value printed three times in one reading and twice in the other is one
    disagreement, not five. Alignment by position is deliberately not attempted
    -- the two extractors order a page differently (docling serialises tables
    into the text, pdf2mdjson does not), so positional matching would report
    disagreement everywhere the LAYOUT differs rather than where the VALUES do.
    """
    if analytic:
        a, b = analytic_only(a), analytic_only(b)
    na, nb = _numbers(a), _numbers(b)
    only_a, only_b = na - nb, nb - na
    shared = sum((na & nb).values())
    total = sum(na.values()) + sum(nb.values())
    return {
        "label_a": label_a,
        "label_b": label_b,
        "n_numbers_a": sum(na.values()),
        "n_numbers_b": sum(nb.values()),
        "n_agreed": shared,
        "n_only_in_a": sum(only_a.values()),
        "n_only_in_b": sum(only_b.values()),
        # The agreement rate is over the UNION, so a reading that simply finds
        # fewer numbers cannot score well by being quiet.
        "agreement": round(2 * shared / total, 4) if total else None,
        "only_in_a": dict(only_a.most_common(60)),
        "only_in_b": dict(only_b.most_common(60)),
        "note": (
            "A number present in one reading and absent from the other is not "
            "evidence that either is wrong -- it is evidence that ONE of them "
            "is, and which one cannot be decided from the text. Values here "
            "need a human eye on the rendered page. Values that agreed "
            "survived two unrelated failure modes and may be relied on more "
            "than either reading alone would justify."),
    }


def suspect_values(a: str, b: str, *, context: int = 46) -> list[dict]:
    """The disagreeing numbers, each with the context of the reading that has it.

    This is the work list. It exists because a count of disagreements is not
    actionable: a reader needs the sentence to take to the PDF.
    """
    na, nb = _numbers(a), _numbers(b)
    out: list[dict] = []
    for text, other, which in ((a, nb, "a"), (b, na, "b")):
        missing = _numbers(text) - other
        for lit in missing:
            m = re.search(r"(?<![\w.])" + re.escape(lit) + r"(?![\w.])", text or "")
            if m is None:
                continue
            out.append({
                "value": lit,
                "present_in": which,
                "context": (text[max(0, m.start() - context):m.end() + context]
                            .replace("\n", " ")),
            })
    return out
