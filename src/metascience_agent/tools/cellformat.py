"""Declared cell formats: the model names the format, OUR parser executes it.

WHY THIS EXISTS
---------------
`celltypes.parse_cell` recognises a fixed list of shapes. A table typeset in any
other convention falls out as `non_numeric` -- one cell at a time, silently,
into the same bucket that holds genuine prose. Two named consequences:

  * `5.38 {1.17}` is unreadable. Braces are not in the list. Neither are angle
    brackets, nor `5.38 / 1.17`, nor a dozen other conventions that are perfectly
    ordinary in print. Each one costs a whole table.
  * A table where EVERY cell fails looks exactly like a table with nothing in
    it. That is this codebase's oldest bug -- our failure recorded as the
    paper's property -- and `celltypes` has already been patched twice for one
    instance of it apiece (a trailing footnote marker, a bracketed significance
    subscript).

The obvious fix is to keep adding patterns, and it does not converge: there is
no finite list of ways a journal can print a mean and its SD.

THE OTHER OBVIOUS FIX, AND WHY IT IS REFUSED
--------------------------------------------
Have the model write the regex. It reads the table, sees the convention, emits
a pattern, we run it.

No. A model-written regex is a model-written *statistic*: whatever it captures
becomes the mean we test, and the failure mode is not an exception -- it is a
plausible number, in the right range, checked against GRIM with total
confidence. There is no downstream layer that can catch it, because by the time
the value exists nothing remembers it was invented. This toolkit accuses people
of errors in their published work; the arithmetic it accuses them with cannot
come from generated code.

WHAT THIS MODULE DOES INSTEAD
------------------------------
The model declares a format from a CLOSED VOCABULARY, and code in this file --
written once, tested, reviewed -- does the parsing. The declaration is two enum
choices, not a pattern:

    PAIRING     what the two numbers MEAN      mean_sd, n_percent, estimate_ci...
    DELIMITER   how the second one is WRAPPED  paren, bracket, brace, plusminus...

`mean_sd:brace` parses `5.38 {1.17}`. The model supplied two words from a menu;
every character of the matching is ours. Supporting a convention nobody has seen
yet is one entry in `DELIMITERS`, not a new code path.

THE SAFETY PROPERTY THAT MAKES THIS SHIPPABLE
----------------------------------------------
A declaration is a hypothesis about the table, and a wrong one is dangerous in
the direction this toolkit cares about most: declare `mean_sd` over an `n (%)`
column and every percentage becomes an SD, which is precisely the misparse that
`celltypes` exists to prevent. So a declaration is not obeyed, it is TESTED --
`apply_format` runs the same coherence guards the label path already applies
(an n (%) needs an integer count and a percent in [0, 100]; an estimate must lie
inside its own interval), and a declaration that does not fit its own cells is
REFUSED rather than applied. The fit rate is reported either way, so a
declaration that only half-works cannot pass as one that worked.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from . import rounding as _rounding
from .celltypes import ParsedCell, repair_unicode

# --- the shape abstraction ------------------------------------------------
#
# A cell's SHAPE is the cell with its content removed: every digit run becomes
# `9`, every letter run becomes `A`, everything else is kept verbatim. It is the
# join key for "these 153 cells are all the same format", which is the fact that
# turns 153 silent failures into one loud one.
_DIGIT_RUN = re.compile(r"\d+")
_ALPHA_RUN = re.compile(r"[^\W\d_]+", re.UNICODE)
_WS_RUN = re.compile(r"\s+")

#: Longest shape reported. A shape is a grouping key, and a 400-character key
#: groups nothing -- it is a prose cell wearing a costume.
_SHAPE_MAX = 48


def shape_of(text: str) -> str:
    """The cell with its content removed: `5.38 (1.17)a` -> `9.9 (9.9)A`."""
    s = _ALPHA_RUN.sub("A", _DIGIT_RUN.sub("9", text or ""))
    return _WS_RUN.sub(" ", s).strip()[:_SHAPE_MAX]


#: A shape is NUMERIC-SHAPED when it is made of numbers and punctuation, with at
#: most one short letter run (a unit, a footnote marker, an `SD` tag). Those are
#: cells the paper printed as data and we failed to read: OUR defect.
#:
#: Everything else is prose -- `'Stage 1 hypertension at age 12 y'` is a row
#: label, and `non_numeric` is the CORRECT answer for it. The distinction is the
#: whole point of the split. MEASURED over the 73 XML papers in the repo (8,966
#: non-empty cells): 2,533 type `non_numeric`, but only 421 of them are
#: numeric-shaped. An alarm that did not separate the two would fire on every
#: table in the corpus and mean nothing.
_LETTER_RUN_MAX = 3


def is_numeric_shaped(shape: str) -> bool:
    """Does this shape look like a value we failed to read, rather than prose?"""
    if "9" not in shape:
        return False
    runs = re.findall(r"A+", shape)
    return len(runs) <= 1 and all(len(r) <= _LETTER_RUN_MAX for r in runs)


# --- the closed vocabulary ------------------------------------------------

@dataclass(frozen=True)
class Pairing:
    """What the numbers in a cell MEAN, and what has to be true of them.

    `arity` is how many numbers follow the leading value: an estimate with its
    confidence interval has two, a mean with its SD has one.
    """
    name: str
    arity: int
    description: str


PAIRINGS: dict[str, Pairing] = {
    p.name: p for p in (
        Pairing("mean_sd", 1, "a mean followed by its standard deviation"),
        Pairing("mean_se", 1, "a mean followed by its standard error"),
        Pairing("n_percent", 1, "a count followed by its percentage"),
        Pairing("median_iqr", 2, "a median followed by its interquartile range"),
        Pairing("median_range", 2, "a median followed by its min and max"),
        Pairing("estimate_ci", 2, "an estimate followed by its confidence interval"),
    )
}

#: How the trailing quantity is wrapped. `None` for the closing character means
#: the delimiter opens but does not close (`5.38 ± 1.17`).
#:
#: ADDING A CONVENTION IS ONE ENTRY HERE. That is the point of the split: the
#: reason `5.38 {1.17}` could not be read was never that braces are hard, it was
#: that every format needed its own regex and so the list stopped growing.
DELIMITERS: dict[str, tuple[str, str | None]] = {
    "paren": ("(", ")"),
    "bracket": ("[", "]"),
    "brace": ("{", "}"),
    "angle": ("<", ">"),
    "plusminus": ("±", None),
    "comma": (",", None),
    "semicolon": (";", None),
    "slash": ("/", None),
}

# A BARE SPACE AND A BARE COLON ARE DELIBERATELY NOT DELIMITERS.
#
# Every entry above is a character whose presence means "a second quantity
# follows". A space is not: it is the default separator between everything, so
# `mean_sd:space` would match any two numbers sitting near each other. The
# measured corpus shows what that would actually consume -- cells like
# `'7 : 18 4 : 8'`, which are two table columns welded together by the
# extractor. That is an extraction defect, and giving the model a vocabulary
# entry that reads it as a mean and an SD converts our defect into a number the
# checking tools would treat as the paper's. Same argument for a colon, whose
# real use in a cell is a ratio -- a quantity this vocabulary cannot express,
# and one it must therefore refuse rather than approximate.

#: Separator BETWEEN the two numbers of a 2-arity pairing, inside the delimiter:
#: `1.42 (1.08-1.87)`, `1.42 (1.08 to 1.87)`, `1.42 (1.08, 1.87)`. All three are
#: accepted for every 2-arity format; distinguishing them buys nothing and would
#: multiply the vocabulary by three.
_INNER_SEP = r"(?:\s*(?:-|--|to|,|;)\s*)"

_NUM = r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d*\.?\d+"


def vocabulary() -> dict:
    """The complete set of declarable formats, for the model and for the docs."""
    return {
        "pairings": {k: {"arity": v.arity, "means": v.description}
                     for k, v in PAIRINGS.items()},
        "delimiters": {k: (f"{o}value{c}" if c else f"{o} value")
                       for k, (o, c) in DELIMITERS.items()},
        "syntax": "<pairing>:<delimiter>, e.g. mean_sd:brace for '5.38 {1.17}'",
        "n_formats": len(PAIRINGS) * len(DELIMITERS),
    }


def parse_format(declared: str) -> tuple[Pairing, str]:
    """Split and validate a declared format name.

    Raises `ValueError` naming the vocabulary. A typo must not silently become a
    refusal to parse -- that is indistinguishable from a table we genuinely
    cannot read, which is the failure mode this module was built to end.
    """
    text = str(declared or "").strip().lower()
    if ":" not in text:
        raise ValueError(
            f"'{declared}' is not a format name. Formats are <pairing>:<delimiter>, "
            f"e.g. 'mean_sd:brace'. Pairings: {', '.join(sorted(PAIRINGS))}. "
            f"Delimiters: {', '.join(sorted(DELIMITERS))}."
        )
    pairing, _, delim = text.partition(":")
    if pairing not in PAIRINGS:
        raise ValueError(
            f"unknown pairing '{pairing}'. Choose one of: "
            f"{', '.join(sorted(PAIRINGS))}."
        )
    if delim not in DELIMITERS:
        raise ValueError(
            f"unknown delimiter '{delim}'. Choose one of: "
            f"{', '.join(sorted(DELIMITERS))}."
        )
    return PAIRINGS[pairing], delim


def _pattern(pairing: Pairing, delim: str) -> re.Pattern:
    """The regex for one vocabulary entry. Built HERE, from constants."""
    open_c, close_c = DELIMITERS[delim]
    lead = rf"\s*({_NUM})\s*"
    if pairing.arity == 1:
        body = rf"{re.escape(open_c)}\s*({_NUM})\s*"
    else:
        body = (rf"{re.escape(open_c)}\s*({_NUM}){_INNER_SEP}({_NUM})\s*")
    tail = rf"{re.escape(close_c)}\s*" if close_c else r"\s*"
    return re.compile(lead + body + tail)


#: Built once. The vocabulary is closed, so the pattern set is finite and can be
#: compiled up front -- and compiling it up front is also how a malformed entry
#: becomes an import error rather than a mystery at parse time.
_PATTERNS: dict[tuple[str, str], re.Pattern] = {
    (p, d): _pattern(PAIRINGS[p], d) for p in PAIRINGS for d in DELIMITERS
}


# --- executing a declaration ----------------------------------------------

def _coherent(pairing: Pairing, nums: list[float | None], dpi: int | None) -> str | None:
    """Why this cell does NOT fit the declared reading, or None if it does.

    The declaration is the model's hypothesis and this is the test of it. Same
    guards `celltypes` applies to a LABEL hint, for the same reason: a label and
    a declaration are both external assertions about the cell, and neither is
    evidence about the numbers actually printed in it.
    """
    if any(v is None for v in nums):
        return "a value did not parse as a number"
    lead = nums[0]

    if pairing.name == "n_percent":
        count, pct = lead, nums[1]
        if not float(count).is_integer():
            return f"n (%) needs an integer count; {count:g} is not one"
        if not 0 <= pct <= 100:
            return f"n (%) needs a percentage in [0, 100]; {pct:g} is outside it"
        return None

    if pairing.name in ("mean_sd", "mean_se"):
        # A dispersion cannot be negative. Deliberately the ONLY guard here: a
        # large SD relative to its mean is ordinary in skewed data, and refusing
        # it would reject exactly the tables most worth checking.
        if nums[1] < 0:
            return f"a standard deviation/error cannot be negative; got {nums[1]:g}"
        return None

    # 2-arity: an interval. The bounds must be ordered, and the leading value
    # must lie inside them -- the same containment test `celltypes` uses before
    # it will keep an unlabelled interval reading.
    lo, hi = nums[1], nums[2]
    if lo > hi:
        return f"the interval [{lo:g}, {hi:g}] is inverted"
    tol = _rounding.half_width(dpi) if dpi is not None else 0.0
    if not lo - tol <= lead <= hi + tol:
        return (f"{lead:g} lies outside its own interval [{lo:g}, {hi:g}], so this "
                f"is not {pairing.description}")
    if pairing.name == "estimate_ci":
        # An estimate sits at the middle of its CI; a skewed median does not sit
        # at the middle of its IQR. Getting this backwards is what made
        # check_estimate_ci call an ordinary length-of-stay median `suspicious`.
        arith = (lo + hi) / 2
        fits = abs(lead - arith) <= max(3 * tol, 0.10 * abs(arith) or 1e-9)
        if not fits and lo > 0 and lead > 0:
            geo = math.exp((math.log(lo) + math.log(hi)) / 2)
            fits = abs(lead - geo) <= max(3 * tol, 0.10 * abs(geo))
        if not fits:
            return (f"{lead:g} sits at neither the arithmetic nor the geometric "
                    f"midpoint of [{lo:g}, {hi:g}] -- the shape of a median with "
                    "its IQR, not an estimate with its CI")
    return None


def parse_cell_as(raw: str, declared: str) -> ParsedCell:
    """Parse one cell under a DECLARED format, or refuse and say why.

    Returns a `ParsedCell` of the declared kind on success. On failure the kind
    is `non_numeric` with a warning naming the declaration -- never a guess, and
    never a silent drop.
    """
    pairing, delim = parse_format(declared)
    printed = (raw or "").strip()
    text, n_repairs = repair_unicode(printed)
    pat = _PATTERNS[(pairing.name, delim)]

    m = pat.fullmatch(text)
    # A trailing footnote marker does not change a cell's FORMAT. `celltypes`
    # learned this twice; re-learning it here would reintroduce the bug one
    # module over. Retried only after a clean match has failed, so a cell that
    # parses today cannot be reparsed by this branch.
    markers: list[str] = []
    if not m:
        from .celltypes import _BRACKETED_TRAILING_LETTERS, _TRAILING_MARKER
        mk = _TRAILING_MARKER.search(text) or _BRACKETED_TRAILING_LETTERS.search(text)
        if mk and text[: mk.start()].strip():
            m = pat.fullmatch(text[: mk.start()].strip())
            if m:
                markers = [g.group(0) for g in re.finditer(r"(.)\1*", mk.group(1))
                           if g.group(0).strip(", \t")]
    if not m:
        return ParsedCell(
            raw=printed, kind="non_numeric",
            warning=(f"'{printed}' does not match the declared format "
                     f"'{declared}'. Nothing was read from it."),
        )

    groups = list(m.groups())
    nums = [_num(g) for g in groups]
    dps = [_rounding.decimals_of_text(g) for g in groups]
    dpi = _rounding.coarsest_decimals(*groups) if pairing.arity == 2 else None

    why = _coherent(pairing, nums, dpi)
    if why is not None:
        return ParsedCell(
            raw=printed, kind="non_numeric",
            warning=(f"'{printed}' matches the shape of '{declared}' but not its "
                     f"meaning: {why}. The declaration was refused, not applied."),
        )

    cell = ParsedCell(raw=printed, kind=pairing.name, value=nums[0],
                      decimals_value=dps[0], markers=markers,
                      unicode_repairs=n_repairs)
    if pairing.name == "mean_sd":
        cell.sd, cell.decimals_sd = nums[1], dps[1]
    elif pairing.name == "mean_se":
        cell.se, cell.decimals_sd = nums[1], dps[1]
    elif pairing.name == "n_percent":
        cell.count, cell.percent = int(nums[0]), nums[1]
        cell.decimals_percent = dps[1]
    else:
        cell.low, cell.high = nums[1], nums[2]
        cell.decimals_interval = dpi
    return cell


def _num(text: str | None) -> float | None:
    try:
        return float(str(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


#: A declaration must fit MOST of the cells it is declared over. Below this it
#: is treated as a wrong hypothesis and refused wholesale, because a format that
#: explains half a column is not a format -- it is a coincidence, and applying it
#: would silently hand the tools whichever half happened to match.
#:
#: 0.8 rather than 1.0 because real columns carry legitimate non-values: a `-`
#: for a cell with no data, an `NA`, a header repeated mid-table. Requiring
#: every cell would let one `-` reject a correct declaration over 40 good ones.
MIN_FIT = 0.8


def apply_format(cells: list[dict], declared: str, min_fit: float = MIN_FIT) -> dict:
    """Re-parse `cells` under a declared format, or refuse the declaration.

    `cells` is the same `[{raw, row_label, col_label}]` shape `parse_cells`
    takes. Returns the parsed cells plus the evidence for or against the
    declaration: how many fit, how many were already readable without it, and --
    when it is refused -- the cells that did not fit, so the model can see WHY
    rather than guess again.
    """
    try:
        pairing, delim = parse_format(declared)
    except ValueError as exc:
        return {"applied": False, "declared": declared, "error": str(exc),
                "vocabulary": vocabulary(), "severity": "indeterminate",
                "warnings": [str(exc)]}

    from .celltypes import parse_cell as _auto

    entries, misfits = [], []
    n_fit = n_already = 0
    considered = 0
    for c in cells:
        raw = (c.get("raw") or "").strip()
        if not raw:
            continue
        considered += 1
        pc = parse_cell_as(raw, declared)
        fit = pc.kind != "non_numeric"
        n_fit += fit
        if not fit:
            misfits.append({"raw": raw, "why": pc.warning,
                            "row_label": c.get("row_label"),
                            "col_label": c.get("col_label")})
        # What the automatic parser made of it, so the declaration's VALUE is
        # visible: a declaration that recovers cells already read is worth
        # nothing, and one that OVERRIDES a confident automatic reading is worth
        # scrutiny rather than applause.
        auto = _auto(raw, c.get("row_label"), c.get("col_label"))
        n_already += auto.kind not in ("non_numeric", "ambiguous")
        d = pc.as_dict()
        d["row_label"], d["col_label"] = c.get("row_label"), c.get("col_label")
        d["auto_kind"] = auto.kind
        entries.append(d)

    fit_rate = n_fit / considered if considered else 0.0
    applied = considered > 0 and fit_rate >= min_fit
    n_overridden = sum(1 for e in entries
                       if e["kind"] != "non_numeric"
                       and e["auto_kind"] not in ("non_numeric", "ambiguous")
                       and e["auto_kind"] != e["kind"])

    warnings: list[str] = []
    if not applied:
        warnings.append(
            f"Declaration '{declared}' fits {n_fit} of {considered} cell(s) "
            f"({fit_rate:.0%}), below the {min_fit:.0%} required to apply it. "
            "REFUSED: a format that explains only part of a column is not the "
            "column's format, and applying it would hand the checking tools "
            "whichever cells happened to match. See `misfits` for what did not "
            "fit, then declare a different format or leave the cells unread."
        )
    if n_overridden:
        warnings.append(
            f"{n_overridden} cell(s) were read differently by the automatic "
            f"parser, which typed them from the table's own labels. A declaration "
            "that contradicts the paper's own row/column headers is more likely "
            "wrong than the headers are; confirm against the printed table "
            "before any check runs on these."
        )
    return {
        "applied": applied,
        "declared": declared,
        "pairing": pairing.name,
        "delimiter": delim,
        "n_cells": considered,
        "n_fit": n_fit,
        "fit_rate": round(fit_rate, 3),
        "n_already_readable": n_already,
        "n_recovered": max(0, n_fit - n_already),
        "n_overrides_automatic": n_overridden,
        "cells": entries if applied else [],
        "misfits": misfits[:20],
        "severity": "indeterminate",
        "warnings": warnings,
        "methodology": (
            f"Cells re-parsed under the declared format '{declared}' "
            f"({pairing.description}, second value delimited by {delim}). The "
            "format name comes from a closed vocabulary and the matching is done "
            "by code in `tools/cellformat.py` -- no pattern is generated at run "
            "time. Every match is then tested against the same coherence guards "
            "the label path applies, and the declaration is applied only if it "
            f"fits at least {min_fit:.0%} of the cells."
        ),
    }


# --- the loud signal ------------------------------------------------------

def suggest_formats(raws: list[str], min_fit: float = MIN_FIT) -> list[str]:
    """Which vocabulary entries would parse this group of cells.

    The point of returning candidates rather than one answer: several formats
    genuinely fit `5.38 (1.17)` and the numbers cannot choose between them. The
    model is being asked which one the TABLE says it is -- from its header, its
    caption, its footnotes -- and that is a reading task, which is the half of
    this it should be doing.
    """
    texts = [str(r).strip() for r in raws if str(r or "").strip()]
    if not texts:
        return []
    # Every candidate is tried against every cell, so this is |vocabulary| x |n|
    # parses. A shape cluster is by construction homogeneous -- that is what
    # makes it a cluster -- so a sample settles the question and the full column
    # only costs time. The cap is on the SUGGESTION; `apply_format` still tests
    # the declaration against every cell before it will apply it.
    texts = texts[:60]
    out = []
    for pairing in PAIRINGS:
        for delim in DELIMITERS:
            name = f"{pairing}:{delim}"
            n = sum(parse_cell_as(t, name).kind != "non_numeric" for t in texts)
            if n / len(texts) >= min_fit:
                out.append(name)
    return out


def describe_unparsed(cells: list[dict], max_clusters: int = 12) -> dict:
    """Cluster the cells nothing could read, and say which are OUR failure.

    A table that returns 153 unreadable cells is reported today as 153 separate
    non-events. Grouped by shape it is ONE event -- "153 cells share the format
    `9.9 (9.9)A` and not one of them parsed" -- which is a screaming signal that
    a convention is unhandled, and it is actionable in a way the 153 were not.

    The prose/numeric split is what keeps the signal honest. Most unreadable
    cells are row labels, and `non_numeric` is the right answer for those; only
    the numeric-shaped clusters are cells the paper printed as data and we
    failed to read.
    """
    from .celltypes import parse_cell as _auto

    typed = []
    for c in cells:
        raw = (c.get("raw") or "").strip()
        if raw:
            typed.append(dict(c, raw=raw,
                              kind=_auto(raw, c.get("row_label"),
                                         c.get("col_label")).kind))
    return cluster_unparsed(typed, max_clusters)


def cluster_unparsed(typed: list[dict], max_clusters: int = 12) -> dict:
    """`describe_unparsed` over cells ALREADY typed: `[{raw, kind, ...}]`.

    Split out so `parse_cells` can hand over its own results instead of paying
    for a second parse of the same table -- and, more to the point, so the two
    can never disagree about which cells went unread.
    """
    groups: dict[str, list[dict]] = {}
    n_cells = n_unread = 0
    for c in typed:
        raw = (c.get("raw") or "").strip()
        if not raw:
            continue
        n_cells += 1
        if c.get("kind") != "non_numeric":
            continue
        n_unread += 1
        groups.setdefault(shape_of(raw), []).append(c)

    clusters = []
    for sh, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        numeric = is_numeric_shaped(sh)
        raws = [m.get("raw", "") for m in members]
        clusters.append({
            "shape": sh,
            "n": len(members),
            "numeric_shaped": numeric,
            "examples": raws[:3],
            "columns": sorted({str(m.get("col_label") or "") for m in members
                               if m.get("col_label")})[:4],
            # Candidates only for the clusters that are ours to fix. Suggesting
            # a mean/SD reading for a row label would be the module inviting
            # exactly the misdeclaration its guards exist to refuse.
            "candidate_formats": suggest_formats(raws) if numeric else [],
        })

    numeric_clusters = [c for c in clusters if c["numeric_shaped"]]
    n_numeric = sum(c["n"] for c in numeric_clusters)
    warnings = []
    for c in numeric_clusters[:3]:
        if c["n"] >= 5:
            # Concatenation, NOT `.format`/`%`: a shape string is built from the
            # cell's own punctuation, so the brace format this module exists to
            # support puts a literal `{` in it and any template call raises on
            # the very cells the warning is about.
            sug = (" Declare one of " + ", ".join(c["candidate_formats"][:4])
                   + " to read them." if c["candidate_formats"] else
                   " No format in the vocabulary parses them -- report this rather "
                   "than working around it.")
            warnings.append(
                str(c["n"]) + " cell(s) share the unread format `" + c["shape"]
                + "` (e.g. " + repr(c["examples"][0]) + "). A block of cells that "
                "all fail the same way is an unhandled convention, not an empty "
                "table." + sug
            )
    return {
        "n_cells": n_cells,
        "n_unread": n_unread,
        "n_unread_numeric_shaped": n_numeric,
        "n_unread_prose": n_unread - n_numeric,
        "clusters": clusters[:max_clusters],
        "severity": "indeterminate",
        "warnings": warnings,
        "methodology": (
            "Cells the automatic parser returned as `non_numeric` are grouped by "
            "SHAPE -- the cell with every digit run replaced by 9 and every letter "
            "run by A -- so that cells failing the same way are counted once, as "
            "one unhandled convention. A shape made of numbers and punctuation is "
            "reported as numeric-shaped: those are values the paper printed and "
            "the toolkit could not read, which is our defect. A shape carrying "
            "prose is a row or column label, for which `non_numeric` is correct."
        ),
    }
