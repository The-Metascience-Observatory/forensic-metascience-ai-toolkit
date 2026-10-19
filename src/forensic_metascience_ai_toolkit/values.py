"""Every value the paper printed, with what it belongs to and what can check it.

See `docs/VALUE_REGISTER_DESIGN.md`. This module is a JOIN, not a sixth
enumeration: `celltypes` already types table cells, `completeness` already
locates prose statistics, `anatomy` already holds the variables and `dispatch`
already knows which checks apply to a (cell kind, variable family) pair. What
none of them carry is an identity for an individual VALUE, or an edge saying
that a mean and the SD beside it are one reported quantity.

THE UNIT IS A VALUE, NOT A ROW. A table cell reading `4.20 (0.21)` is one
`_body_items`-style row and two values, and the checks consume the two
separately -- GRIM takes the mean, GRIMMER takes both. A register keyed on rows
cannot say that the same `n = 93` appears in twenty groups and is one fact,
which is exactly what deduplication needs to know.

WHAT THIS MODULE DOES NOT DO. It does not become the denominator. The regex
floor in `completeness` stays the independent tripwire it was built to be --
`register.py` sets out why at length, and the short version is that a model
which both enumerates and checks reports full coverage of whatever it happened
to notice. This module builds the finder's side. Comparing it against the floor
is still the floor's job.
"""

from __future__ import annotations

import re
from functools import lru_cache

from .tools import rounding as _rounding
from typing import Any

__all__ = [
    "ROLES", "value_id", "group_id", "applicable_tools", "attach_checks",
    "dedupe_checks", "build_from_paper", "attach_not_run", "coverage",
    "attach_calls_by_value", "binding_candidates",
    "groups_from_cells", "groups_from_body_items", "same_value_edges",
    "build_register",
    "classification_batch",
]

#: The closed vocabulary of what a number IS within its group. Closed because
#: every consumer keys off it: the dispatcher maps role -> tool parameter, the
#: viewer maps role -> label, and dedup compares like with like. A number whose
#: role we cannot name is recorded with role `unknown` rather than dropped --
#: an unnameable value is still a value the paper printed.
ROLES = (
    "mean", "sd", "se", "median", "iqr_low", "iqr_high",
    "count", "denominator", "percentage",
    "estimate", "ci_low", "ci_high",
    "n", "df", "df2", "statistic", "p", "effect_size", "unknown",
)


# ---------------------------------------------------------------------------
# What KIND of thing a value is -- Greg, 2026-08-18:
#
#   > statistics presented in a paper [...] are purely descriptive, and not part
#   > of any inferential test (e.g. mean age of participants). While these values
#   > have the potential to inform the interpretation of the paper's veracity,
#   > they seem distinct enough to handle in a different way.
#
# He is right that they are distinct, and the split was already in the code
# without a name: EVERY key in `dispatch.DISPATCH` is a descriptive form
# (`mean_sd`, `mean_se`, `n_percent`, `count_denominator_percent`,
# `estimate_ci`), and `statcheck` appears nowhere in that module -- the
# inferential checks reach a paper by the prose rail instead. Two rails already
# existed; this names the seam.
#
# CLASSIFY BY WHAT THE VALUE IS, NOT BY WHETHER IT WAS TESTED. The tempting
# reading of "not part of any inferential test" is a property of the paper's
# analysis, not of the number, and it misfiles the exact values our own
# `table1_dispersion` and `csf` tools consume -- those work ON the p-values
# attached to baseline descriptive comparisons. A mean is descriptive whether or
# not anyone ran a t-test on it.
#
# Descriptives are NOT the lesser class here. The whole granularity family --
# GRIM, GRIMMER, SPRITE, DEBIT -- is only defined on them, and an impossible
# descriptive is a stronger finding than a mis-recomputed p: it says the numbers
# could not have come from any data, rather than that one derivation slipped.
#
# `design` is the class that earns its place. It is not "leftovers": it is
# exactly the set of values that GATE other checks rather than being checked
# themselves, which is why `census` has a `missing_inputs` bucket at all and why
# `n` dominates it. Naming the class lets a coverage log say WHY a check never
# ran, in the reader's vocabulary rather than the dispatcher's.
ROLE_CLASSES = ("descriptive", "inferential", "design", "unknown")

_ROLE_CLASS = {
    # summaries of a distribution -- checkable for granularity and dispersion
    "mean": "descriptive",
    "sd": "descriptive",
    "se": "descriptive",
    "median": "descriptive",
    "iqr_low": "descriptive",
    "iqr_high": "descriptive",
    "count": "descriptive",
    "percentage": "descriptive",
    # outputs of a test or model -- checkable by recomputation
    "estimate": "inferential",
    "ci_low": "inferential",
    "ci_high": "inferential",
    "statistic": "inferential",
    "p": "inferential",
    "effect_size": "inferential",
    # structural facts that ENABLE checks. `df` sits here for the same reason
    # `n` does, not because it is uninteresting: it is an input to recomputing a
    # p-value exactly as `n` is an input to GRIM. Their absence is what
    # `census.blocked_on_input` counts.
    "n": "design",
    "denominator": "design",
    "df": "design",
    # The DENOMINATOR df of an F. Its own role rather than a second `df` row,
    # because F(2, 54) and F(54, 2) are different tests and a consumer reading
    # two same-named rows has only their order to tell them apart.
    "df2": "design",
    "unknown": "unknown",
}


def role_class(role: str) -> str:
    """The class of a role: descriptive, inferential, design, or unknown.

    Total over `ROLES` by construction, and the closure is asserted by a test
    rather than trusted -- an unmapped role returns "unknown", which would
    otherwise let a new role silently join the class that means "we could not
    tell", the absence-as-knowledge failure this repository keeps re-finding.
    """
    return _ROLE_CLASS.get(role, "unknown")


#: Which `ParsedCell` attribute supplies which role, per cell kind.
#:
#: MODELLED ON `celltypes.ParsedCell.forensic_kwargs` but NOT identical to it,
#: and an earlier comment here claimed the two "cannot disagree". They already
#: did: `forensic_kwargs` returns `{}` for `mean_se` -- it declines to hand a
#: standard error to a granularity tool -- while this table maps it, because the
#: register records what the paper PRINTED and the other decides what a check
#: may CONSUME. Those are different questions and the tables are allowed to
#: differ; what is not allowed is a claim that they cannot.
_CELL_ROLES: dict[str, tuple[tuple[str, str], ...]] = {
    "mean_sd": (("value", "mean"), ("sd", "sd")),
    "mean_se": (("value", "mean"), ("se", "se")),
    "n_percent": (("count", "count"), ("percent", "percentage")),
    "count_denominator_percent": (("count", "count"),
                                  ("denominator", "denominator"),
                                  ("percent", "percentage")),
    "estimate_ci": (("value", "estimate"), ("low", "ci_low"), ("high", "ci_high")),
    "median_iqr": (("value", "median"), ("low", "iqr_low"), ("high", "iqr_high")),
    "median_range": (("value", "median"), ("low", "iqr_low"), ("high", "iqr_high")),
    "count": (("value", "count"),),
    "numeric": (("value", "unknown"),),
}

#: KINDS WITH NO ROLE MAP STILL PRINT NUMBERS. Six kinds used to fall through
#: `if not roles: continue` and vanish: this module's header promises "every
#: value the paper printed" and its ROLES comment promises that an unnameable
#: value is "recorded with role `unknown` rather than dropped" -- true of prose
#: and false of tables. On 10.1007--s00702-004-0248-2 undeclared, 32 table cells
#: produced 0 values and `coverage()` then reported clean zeros, so a paper
#: whose every table cell was dropped read exactly like a paper with no tables.
#: The absence-as-knowledge failure, inside the module written to prevent it.
#:
#: `ambiguous` is the important one: `47 (60.3)` prints two numbers and the cell
#: simply cannot say which is the count. Recorded with role `unknown`, which is
#: what the register is for -- a value nobody has typed yet is still a value.
_UNTYPED_FALLBACK = (("value", "unknown"),)


#: A column heading that names its cells' role, for the ONE role whose bounds
#: make a mistyping detectable.
#:
#: TWO FORMS, deliberately not one pattern. The BARE form takes no qualifier,
#: so `Sample p` is not claimed; the QUALIFIED form allows up to two leading
#: tokens but then REQUIRES an explicit `value`/`val`, which is what keeps
#: `Sample participants` and `Parity` out. Both are anchored at each end: a
#: heading must BE a p-column, not merely contain a p.
#:
#: The trailing `[a-z]?` is a FOOTNOTE MARKER welded to the label by the
#: extractor -- `P valuec`, `P valued`. It is permitted only after `value`, so
#: `pc` matches nothing. `celltypes._TRAILING_MARKER` refuses the same welded
#: letter after a NUMBER, because `12.3a` could be annum; after the word
#: `value` no unit can attach, so the allowance is safe HERE and must not be
#: pushed down into the numeric matcher.
#: A PREFIX OF "value", because the extractor truncates headers. Measured
#: 2026-08-22: 168 values sit under a column labelled `p-v`, which is
#: `p-value` with the end cut off. Allowing a prefix of that ONE word keeps the
#: rule as tight as it was -- `p-w` still matches nothing -- while covering
#: what docling actually emits.
_VALUE_PREFIX = r"v(?:a(?:l(?:u(?:e)?)?)?)?"
_P_BARE = re.compile(
    rf"(?i)^(?:adj(?:usted)?\.?\s*)?p(?:[\s\-_]*(?:{_VALUE_PREFIX})[a-z]?|s)?$")
_P_QUALIFIED = re.compile(
    rf"(?i)^(?:[a-z0-9.\-]{{1,12}}\s+){{1,2}}p[\s\-_]*(?:{_VALUE_PREFIX})[a-z]?$")


def _header_without_marker(label: str) -> str:
    """Drop a trailing footnote mark from a COLUMN HEADING.

    Superscript letters and the baseline footnote symbols only -- the same two
    sets `celltypes` already defines, imported rather than re-spelled so the
    two cannot drift. A welded ASCII letter is NOT handled here; it is allowed
    by the patterns above only in the one position where it cannot be a unit.
    """
    from .tools.celltypes import _SUP_LETTERS, _FOOTNOTE_SYMBOLS
    return str(label).strip().rstrip(_SUP_LETTERS + _FOOTNOTE_SYMBOLS).strip()


def role_from_column(col_label: str | None, value: float | None) -> str | None:
    """The role the COLUMN HEADING names, or None.

    MEASURED 2026-08-20 over the eleven-paper run: 468 values reached the
    register with role `unknown` under a heading that says `p` or `P value`.
    The cell alone cannot type them -- a bare `.002` is just a number -- and
    the cell parser reads only the cell, so the marker sitting one row up in
    the header was never consulted. Same seam as the stacked header, one layer
    up: information the document prints, dropped at a boundary.

    ONLY THE INNERMOST LEVEL IS CONSULTED. A stacked header arrives joined as
    `Within-Person | p`, and the level nearest the data is the one that names
    the quantity; an outer level names the group it belongs to.

    THE BOUND IS THE GUARD, AND IT FAILS CLOSED. A p-value lies in [0, 1]. A
    number outside that range under a `p` heading is evidence that the column
    is misaligned -- a real and common extraction fault -- and NOT evidence
    that the paper printed an impossible p-value. Such a value keeps role
    `unknown`, so no p-value check can dispatch on it. Typing it would let the
    pipeline manufacture an accusation out of its own reading error, which is
    the worst thing it can do.

    Scoped deliberately to `p`. `mean` (48 values) and `CI` (36) were measured
    too small to be worth the risk, and the CI candidates turned out to be
    `1 [Reference]` cells, which are reference categories rather than
    intervals -- a reminder that a heading names the COLUMN, not every cell in
    it.
    """
    if value is None or not col_label:
        return None
    from .dispatch import HEADER_LEVEL_SEP
    innermost = _header_without_marker(
        str(col_label).split(HEADER_LEVEL_SEP)[-1])
    if not (_P_BARE.match(innermost) or _P_QUALIFIED.match(innermost)):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= v <= 1.0):
        return None
    return "p"

#: ...but a cell with NO number is not a value. It is counted, never invented.
_NO_VALUE_KINDS = frozenset({"non_numeric"})

#: Which `decimals_*` field carries the printed precision of which role. The
#: precision is the value's own property, not the group's: `101 (71%)` prints
#: the count to zero decimals and the percentage to zero, and `4.20 (0.213)`
#: prints its two components to different precisions. Attaching precision to the
#: group would force one of them to be wrong.
_ROLE_DECIMALS = {
    "mean": "decimals_value", "estimate": "decimals_value",
    "count": "decimals_value", "sd": "decimals_sd", "se": "decimals_sd",
    "percentage": "decimals_percent",
    "ci_low": "decimals_interval", "ci_high": "decimals_interval",
}

#: Prose kinds from `completeness.BODY_PATTERNS` whose single span holds one
#: value of a nameable role. The kinds NOT here -- `nhst`, `chi2`,
#: `mean_sd_prose`, `estimate_ci_prose` -- hold several, and splitting them
#: needs a parse rather than a lookup; they are recorded as one `unknown`-role
#: value until that parse exists, which is honest about what we can name.
_BODY_ROLE = {
    "p_value": "p",
    "percentage": "percentage",
    "n_of_total": "count",
}


def value_id(anchor: dict, role: str, component: int | None = None) -> str:
    """A stable id for one printed value.

    Derived from WHERE IT IS PRINTED: the table, the row, and -- in order of
    preference -- the column number, the column header, or the position within
    the row.

    HOW STABLE THAT IS DEPENDS ON WHICH ONE APPLIES, and an earlier version of
    this docstring claimed the strongest case for all of them. A column number
    or a unique header survives a re-extraction that reorders columns. A
    POSITIONAL ORDINAL DOES NOT, and it is the fallback that fires whenever a
    row has neither -- which for cells from `prepass.paper_tables` was
    previously every cell, since none of them carry a `col`. Preferring the
    header narrows that to rows whose columns are unlabelled or share a label.
    """
    # A COMPONENT INDEX WHEN THE CELL HOLDS SEVERAL VALUES OF ONE ROLE. A
    # decomposed cell emits one value per printed literal and their roles are
    # often all `unknown`, so without this every component of `3 (1.4)` would
    # carry the same id and the second would silently overwrite the first --
    # the very loss decomposition exists to stop, one layer down.
    if component is not None:
        return f"val:{_anchor_key(anchor)}:{role}#{component}"
    return f"val:{_anchor_key(anchor)}:{role}"


def group_id(anchor: dict) -> str:
    return f"grp:{_anchor_key(anchor)}"


_ID_SAFE = None  # compiled lazily; see `_slug`


def _slug(text: Any) -> str:
    """A table name safe to put in an id.

    `prepass.paper_tables` labels a docling table `cref='#/texts/57'` -- quotes,
    a hash and slashes, all of which are fine in a dict key and none of which
    are fine in a URL fragment or an HTML `id` attribute. The hover view Greg
    wants addresses values by id from the page, so the id has to survive being
    written into markup. The ORIGINAL label is kept on the anchor for display;
    only the key is slugged.
    """
    global _ID_SAFE
    if _ID_SAFE is None:
        import re
        _ID_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")
    out = _ID_SAFE.sub("-", str(text or "t")).strip("-")
    return out or "t"


def _row_label(value: Any) -> str:
    """One spelling of "this row has no label", on both sides of the join.

    `check_table` stamps `""` (`cell.get("row_label") or ...  or ""`) while the
    register stored `None`, so an UNLABELLED row never joined: its check ran,
    came back consistent, and the verdict was dropped -- after which
    `coverage()` called the group silent and its note claimed "a check neither
    ran nor said why", which was false in both halves.
    """
    return "" if value is None else str(value)


def _anchor_key(anchor: dict) -> str:
    """The identity half of an anchor.

    COLUMN IDENTITY IS AN ORDINAL, NOT `col`. Real tables from
    `prepass.paper_tables` carry NO `col` at all: measured on
    10.1007--s00702-004-0248-2, 0 of 20 cells had one and 10 of 20 shared a
    `(row, col)` key -- every cell in a row collapsing onto `r2:cNone`. This is
    the same identity failure the repo has already paid for twice, in
    `completeness.build_manifest` (94 of 757 items sharing an id, 12.4%) and
    before that in `check_table`, where it cost 40% of the row dispositions.

    So `col` is used when the extractor gives one and a positional ordinal
    within `(table, row)` stands in when it does not. `col_label` is NOT used
    for identity -- it is the better label and the worse key, because two
    columns can carry the same header and some carry none.
    """
    a = anchor or {}
    if a.get("where") == "table":
        # A LABEL ANCHOR, NOT A CELL ANCHOR. A design value is printed in a
        # header or a row label, so it has no row and no column of its own --
        # it GOVERNS cells rather than occupying one. Falling through to the
        # cell path below would key every design value in a table as
        # `t1:rNone:i0` and collapse them all onto one id. The label text is
        # the identity, which is also what makes one printed `(n = 68)` stay
        # one value however many cells it covers.
        if a.get("axis"):
            return (f"{_slug(a.get('table', 't'))}:{a['axis']}:"
                    f"{_slug(a.get('label'))}")
        col = a.get("col")
        # `col_label` FIRST when it is usable: it survives a re-extraction that
        # reorders columns, which the ordinal does not. See `value_id`.
        label = _slug(a.get("col_label")) if a.get("col_label_is_unique") else None
        if col is not None:
            col_key = f"c{col}"
        elif label:
            col_key = f"h{label}"
        else:
            col_key = f"i{a.get('ordinal', 0)}"
        # `row` is rendered as a STRING, and the ordinal dict is keyed on the
        # same string: an extractor emitting `1` for one cell and `"1"` for
        # another gave them one id while counting them as separate rows.
        return f"{_slug(a.get('table', 't'))}:r{a.get('row')}:{col_key}"
    return f"body:{a.get('offset')}"


def applicable_tools(kind: str, data_type: str = "unknown",
                     variable: dict | None = None) -> tuple[str, ...] | None:
    """Every check that WOULD run on a value of this type.

    Returns None when the dispatcher has no entry for this pair at all, and an
    empty tuple when it HAS one and it is empty -- "declined" and "never
    considered" are different answers and were previously spelled the same,
    because `DISPATCH.get` defaulted to `()`.

    THE TWO REFUSALS THAT COME AFTER THE TABLE ARE APPLIED HERE TOO, given a
    variable. `check_table` looks the pair up and then drops tools twice more:
    `_drop_unbounded` removes the ones needing scale bounds the variable does
    not state, and the composite gate refuses the whole granularity family for a
    `likert_composite` scored as a mean. Reading `DISPATCH` alone therefore did
    NOT give "the answer the pipeline would actually give" -- a mean_sd cell on
    a likert_composite was reported as checkable by three tools that
    `check_table` refuses on the same input. The test shipped with this module
    asserted that wrong answer, using BDI-II, a likert_composite.
    """
    # NOT GUARDED. A failure to import the dispatcher is a broken install, not
    # a fact about this cell, and the guard that used to be here returned the
    # same `None` that now means "the dispatcher has no entry for this pair" --
    # a crash rendered as a considered answer. The import is inside the function
    # only to break a cycle at module load; by call time it cannot fail for any
    # reason a caller should absorb.
    from .dispatch import DISPATCH, _drop_unbounded, _is_composite
    if (kind, data_type) not in DISPATCH:
        return None
    tools = tuple(DISPATCH[(kind, data_type)])
    if variable is None or not tools:
        return tools
    if kind == "mean_sd" and _is_composite(variable):
        return ()
    kept, _refused = _drop_unbounded(tools, variable)
    return tuple(kept)


#: Numeric literals in a cell, in the order the paper printed them.
_LITERAL = None


#: How a cell's several numbers are related to each other. NOT a claim about
#: what they MEAN -- that is the role, and the roles of a decomposed cell are
#: usually `unknown`. This is the structure the paper printed, which is certain
#: even when the roles are not, and it is what makes two components RELATED
#: rather than merely adjacent.
#:
#: Deliberately small and deliberately honest: `unclassified` is a real answer,
#: and a survey of many more tables will extend this. Guessing a form we have
#: not seen would put a relationship in the register that nobody observed.
_FORMS: tuple = (
    ("value_with_interval", r"^\s*[^()\[\]]+[([][^)\]]*(?:to|[-–—])[^)\]]*[)\]]\s*$"),
    ("value_with_parenthetical", r"^\s*[^()\[\]]+[([][^)\]]+[)\]]\s*$"),
    ("range", r"^\s*[-+−]?[\d.,·]+\s*(?:to|[-–—])\s*[-+−]?[\d.,·]+\s*$"),
    ("pair_over_slash", r"^\s*[-+−]?[\d.,·]+\s*/\s*[-+−]?[\d.,·]+\s*$"),
)


def cell_form(raw: Any) -> str:
    """The printed relationship between a cell's numbers, or `unclassified`."""
    import re
    text = str(raw or "").strip()
    if len(_literals(text)) < 2:
        return "single" if _literals(text) else "no_number"
    for name, pattern in _FORMS:
        if re.match(pattern, text):
            return name
    return "unclassified"


def _literals(raw: Any) -> list[str]:
    """Every numeric literal in a cell's text, AS PRINTED, left to right."""
    global _LITERAL
    if _LITERAL is None:
        import re
        # Thousands groups and a sign are part of the literal; a trailing dot is
        # sentence punctuation and is not.
        #
        # A SIGN ONLY WHERE A SIGN CAN BE. The hyphen in `1.08-1.9` is an
        # interval separator, and reading it as a minus made `ci_high` come back
        # as "-1.9" -- a literal the paper did not print, which is the very
        # fabrication this function was written to stop. The lookbehind refuses
        # a sign that follows a digit, so `(-0.21)` keeps its minus and
        # `1.08-1.9` does not gain one.
        # THE SAME TWO CONVENTIONS THE OTHER READERS HAD TO LEARN. This was the
        # SEVENTH reader of the middle dot found on 2026-08-20:
        # `_literals("33 (55·9)")` returned `['33', '55', '9']`, splitting one
        # printed number into two literals -- and this function's own job is to
        # report the literals AS PRINTED. U+2212 is admitted as a sign for the
        # same reason it is in `numerals.NUMERAL`.
        _LITERAL = re.compile(
            r"(?<![\d.·])[-+−]?\d{1,3}(?:,\d{3})+(?:[.·]\d+)?(?!\d)"
            r"|(?<![\d.·])[-+−]?\d*[.·]?\d+")
    return _LITERAL.findall(str(raw or ""))


def _as_printed(value: Any, decimals: Any) -> str:
    """A RECONSTRUCTION of the literal, used only when the real one is absent.

    Prefer `_literals` on the cell's own text. This reconstructs from the parsed
    float and a decimals count, and it gets two things wrong that matter:

      - `estimate_ci` records ONE precision for all three numbers,
        `decimals_interval`, which is deliberately the COARSEST of them. Used to
        format, it turns `1.42 (1.08-1.9)` into a ci_low of "1.1" -- a literal
        the paper never printed. `same_value` then links that to a genuine "1.1"
        elsewhere and reports two different numbers as the same one.
      - a thousands separator is lost: `1,234.5` reconstructs as "1234.5".

    Both were found by adversarial review, in the field whose own comment claims
    it holds what the paper printed.
    """
    n = _num(value)
    if n is None:
        return str(value)
    try:
        return f"{n:.{int(decimals)}f}"
    except (TypeError, ValueError):
        return str(value)


def _num(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def groups_from_cells(parsed: dict, cells: list[dict] | None = None,
                      table: str = "t1",
                      bindings: dict | None = None,
                      variables: dict | None = None,
                      stats: dict | None = None) -> list[dict]:
    """Value groups for one table, from `celltypes.parse_cells` output.

    `cells` is the RAW input list that was parsed. Two things depend on it, and
    both were wrong without it:

    - `parse_cells` does not carry `row`/`col` through to its output, so an
      anchor built from the parsed cell alone is `rNone:cNone` -- every value in
      the table collides on one id. The dispatcher has the same need and solves
      it the same way, `zip(typed["cells"], cells)`.
    - AMBIGUITY IS RESOLVED BY THE DECLARED VARIABLE, not by the parser. A bare
      "Age" row printing `48.90 (14.46)` is `ambiguous` in isolation and
      `mean_sd` once a family is declared. Skipping that step dropped every
      mean/SD cell in a real table, which is exactly the coverage the
      declaration is supposed to buy.

    `bindings` maps a row label to a variable id, exactly as `check_table` takes
    it, so the register carries the same edge the checks do.
    """
    bindings = bindings or {}
    variables = variables or {}
    try:
        from .dispatch import _resolve_ambiguous
    except Exception:  # noqa: BLE001
        _resolve_ambiguous = None
    typed = parsed.get("cells") or []
    source_cells = list(cells or [])
    out: list[dict] = []
    # Ordinal within (table, row), for the columnless case above.
    ordinals: dict[Any, int] = {}
    skipped_no_value = 0
    no_value_raw: list = []
    # WHICH HEADERS CAN CARRY IDENTITY. An ordinal is list position, so an id
    # built on it moves when a re-extraction reorders a row -- and for cells
    # from `prepass.paper_tables` the ordinal is ALL there is, because none of
    # them carry a `col`. A column header does survive reordering, so it is
    # preferred where it is present and unambiguous. Where two columns of a row
    # share a header, or none has one, the ordinal stands in and the id is
    # position-dependent; `value_id` says so rather than claiming otherwise.
    _labels_per_row: dict[str, list] = {}
    for i, cell in enumerate(typed):
        src = source_cells[i] if i < len(source_cells) else {}
        _labels_per_row.setdefault(str(src.get("row", cell.get("row"))), []).append(
            src.get("col_label") or cell.get("col_label"))
    _unique_label = {
        row: {lab for lab in labs
              if lab and labs.count(lab) == 1}
        for row, labs in _labels_per_row.items()
    }
    for i, cell in enumerate(typed):
        src = source_cells[i] if i < len(source_cells) else {}
        row_label = cell.get("row_label") or src.get("row_label")
        # POSITION IN THE ROW, counted over EVERY cell and not only the ones
        # that yield a group. Counting only the yielders makes the ordinal move
        # when a cell's KIND changes -- which it does the moment a variable is
        # declared and `_resolve_ambiguous` settles a cell that was ambiguous
        # last run. An id that shifts because a neighbour got typed is not an
        # identity.
        _row_no = src.get("row", cell.get("row"))
        _row_key = str(_row_no)          # see `_anchor_key`: `1` and `"1"` are one row
        ordinals[_row_key] = ordinals.get(_row_key, -1) + 1
        vid = bindings.get(row_label)
        var = variables.get(vid)
        if _resolve_ambiguous is not None and var:
            cell = _resolve_ambiguous(cell, var)
        kind = cell.get("kind")
        if kind in _NO_VALUE_KINDS:
            skipped_no_value += 1
            # WHAT IT SAID, kept so `no_value_reasons` can tell the paper's
            # `NA` from a table row the extractor glued into one cell.
            no_value_raw.append(cell.get("raw"))
            continue
        roles = _CELL_ROLES.get(kind) or _UNTYPED_FALLBACK
        row_no = _row_no
        col_no = src.get("col", cell.get("col"))
        _col_label = src.get("col_label") or cell.get("col_label")
        anchor = {"where": "table",
                  # The slugged key is in the id; this is the label a reader
                  # sees, kept verbatim.
                  "table": table,
                  "row": row_no,
                  "col": col_no,
                  "ordinal": ordinals[_row_key],
                  "col_label": _col_label,
                  "col_label_is_unique": _col_label in _unique_label.get(
                      _row_key, set())}
        dtype = _data_type(var)
        # THE PAPER'S OWN LITERALS, in printed order. `_CELL_ROLES` lists roles
        # in that same order for every kind, so the two zip -- and this is the
        # only source that keeps `1.08` as `1.08` and `1,234.5` as `1,234.5`.
        # Used only when the counts agree; a mismatch means the cell holds
        # something this map does not describe, and guessing an alignment would
        # attach one number's literal to another number's role.
        printed_literals = _literals(cell.get("raw"))
        aligned = len(printed_literals) == len(
            [a for a, _r in roles if cell.get(a) is not None])
        lit = iter(printed_literals) if aligned else None
        values = []
        if kind not in _CELL_ROLES:
            # SPLIT, DO NOT COLLAPSE.
            #
            # `_UNTYPED_FALLBACK` is ONE role reading ONE attribute, so a cell
            # the typer could not name kept its first number and dropped the
            # rest: `3 (1.4)` became a single value of 3.0 and the 1.4 was gone.
            # MEASURED 2026-08-20 over the eleven papers: 305 reported cells
            # held fewer values than the numbers they print, losing 339 printed
            # numbers -- silently, because the register still showed a value.
            #
            # DECOMPOSITION IS CERTAIN WHERE ROLE ASSIGNMENT IS NOT, and the two
            # were being conflated. `3 (1.4)` definitely contains two numbers;
            # what is uncertain is only whether they are count/percent, mean/SD
            # or estimate/CI -- and `celltypes` is right to refuse THAT guess.
            # Uncertainty about the roles is not grounds to discard the numbers.
            # Every component is emitted with role `unknown`, which is honest;
            # a missing value is not.
            for i, literal in enumerate(printed_literals):
                parsed, decimals = _num_and_decimals(literal)
                if parsed is None:
                    continue
                # THE COLUMN HEADING GETS THE LAST WORD, where it names a
                # role and the value is in bounds for it. See
                # `role_from_column` for why only `p`, and why out-of-bounds
                # fails closed instead of accusing.
                named = role_from_column(anchor.get("col_label"), parsed)
                role_here = named or "unknown"
                values.append({
                    "id": value_id(anchor, role_here, i),
                    "role": role_here,
                    "role_class": role_class(role_here),
                    "printed": literal,
                    "value": parsed,
                    "decimals": decimals,
                    # WHICH component, and HOW MANY there are. The form on the
                    # group says how they relate; this says which one this is,
                    # so a later typing pass can address them individually.
                    "component": i,
                    "n_components": len(printed_literals),
                    "anchor": dict(anchor),
                    "group": group_id(anchor),
                    "variable_id": vid,
                })
        for attr, role in (() if kind not in _CELL_ROLES else roles):
            parsed_value = cell.get(attr)
            if parsed_value is None:
                continue
            literal = next(lit) if lit is not None else None
            # THE COLUMN HEADING NAMES WHAT THE MAP COULD NOT. `numeric` maps
            # to role `unknown` by design -- a bare `.002` is just a number --
            # and that is the kind 421 of the 468 p-column values arrive as.
            # Only an `unknown` may be overridden: where the map states a role,
            # the cell itself proved it, and a heading does not outrank the
            # cell's own syntax.
            if role == "unknown":
                role = role_from_column(anchor.get("col_label"),
                                        _num(parsed_value)) or role
            # PRECISION IS LOOKED UP AFTER THE ROLE IS SETTLED, and it used to
            # run three statements earlier -- against the role the map gave,
            # before the column heading had corrected it. `_ROLE_DECIMALS` has
            # no `unknown` entry and no `p` entry, so the lookup was
            # `cell.get("")` and returned None for exactly the values the
            # override exists to rescue. Measured at HEAD on
            # `10.1002--eat.24415`: 485 of 1,019 values (47.6%) carried
            # `decimals: null`, of which roles `unknown` 336 and `p` 149.
            decimals = cell.get(_ROLE_DECIMALS.get(role, ""))
            if decimals is None and literal is not None:
                # AND WHERE THE MAP STILL HAS NO ENTRY, COUNT THE LITERAL. The
                # paper printed it; the precision is not a guess, it is a read.
                # This is the one direction that is always safe -- it can only
                # replace "unknown precision", which refuses, with the paper's
                # own, which is the number every rounding window needs.
                decimals = _rounding.decimals_of_text(literal)
            printed = literal if literal is not None else _as_printed(
                parsed_value, decimals)
            values.append({
                "id": value_id(anchor, role),
                "role": role,
                "role_class": role_class(role),
                # AS PRINTED, reconstructed from the parsed value and the
                # precision `celltypes` captured. `str(4.2)` is "4.2" and the
                # paper wrote "4.20"; the two are different assertions about
                # precision, and `same_value` below keys on this field
                # precisely to keep them apart. Stringifying the float would
                # have collided them -- the failure this field exists to avoid.
                "printed": printed,
                "value": _num(parsed_value),
                "decimals": decimals,
                **({} if lit is not None else
                   {"printed_is_reconstructed": True}),
                "anchor": dict(anchor),
                "group": group_id(anchor),
                "variable_id": vid,
            })
        if not values:
            skipped_no_value += 1
            no_value_raw.append(cell.get("raw"))
            continue
        out.append({
            "id": group_id(anchor),
            "kind": kind,
            "variable_id": vid,
            "quote": cell.get("raw"),
            "anchor": dict(anchor),
            "row_label": row_label,
            "values": values,
            "applicable_tools": list(applicable_tools(kind, dtype, var) or ()),
            # `None` means the dispatcher has no entry for this (kind,
            # data_type) at all; `[]` means it has one and declined. Kept apart
            # so a reader can tell "nothing applies here" from "nobody asked".
            "dispatch_considered": applicable_tools(kind, dtype, var) is not None,
            "checks": [],
            **({"typing": "untyped"} if kind not in _CELL_ROLES else {}),
            # THE PRINTED RELATIONSHIP between this cell's numbers. Not a claim
            # about what they mean -- that is the role -- but the structure the
            # paper set, which is certain even when the roles are not.
            "form": cell_form(cell.get("raw")),
            # A BOUND, NOT A POINT VALUE. `<0.001` reaches the register with the
            # bound as its number; without the operator beside it a reader --
            # and any consumer -- would take it for an exact 0.001, which is a
            # precision the paper never claimed.
            **({"censored": cell.get("censored")} if cell.get("censored") else {}),
        })
    if stats is not None:
        # A dropped cell that nothing counts is the defect this fallback exists
        # to close, so the count travels explicitly rather than being inferred
        # from a length difference that multi-value groups make meaningless.
        stats["skipped_no_value"] = stats.get("skipped_no_value", 0) + skipped_no_value
        stats.setdefault("no_value_raw", []).extend(no_value_raw)
    return out


#: The symbol a paper writes before `=` and the role it names. Closed, because
#: `named_equality` matches a closed symbol list in the first place -- and
#: because a symbol nobody mapped must come out `unknown` rather than guessed.
#: `alpha`/`beta` are DESIGN THRESHOLDS, not results, and stay unknown so the
#: floor does not hand a checker a significance level as though it were one.
_SYMBOL_ROLE = {
    "n": "n", "m": "mean", "mdn": "median", "sd": "sd", "se": "se",
    "sem": "se", "or": "estimate", "rr": "estimate", "hr": "estimate",
    "mw": "estimate", "r2": "statistic", "r²": "statistic",
    "χ2": "statistic", "χ²": "statistic", "η2": "effect_size",
    "η²": "effect_size",
}

#: A NUMBER, INCLUDING THE LEADING-DECIMAL FORM. `.0525` is how APA style
#: prints a p-value -- the leading zero is dropped by convention -- and it is
#: everywhere in medical writing. A first version required a digit first, so
#: `P = .0525` matched only `0525` and registered as **525.0**, and `P < .001`
#: registered as **1.0**: a p-value the paper called highly significant,
#: recorded as the least significant value possible. Caught 2026-08-20 by a
#: corpus invariant asserting every p-value lies in [0, 1] -- five of 116 did
#: not.
_PROSE_NUM = re.compile(r"[-+\u2212]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)")

#: An interval, matched WHOLE so the separator cannot be read as a sign.
#: A hyphen only separates when the bound after it is not itself signed;
#: `to`, an en-dash and an em-dash always separate, so `-1.2 to -0.3` keeps
#: both minus signs and `0.182-0.912` keeps neither.
_NUM_SRC = r"[-+\u2212]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)"
_INTERVAL = re.compile(
    rf"(?P<lo>{_NUM_SRC})\s*(?:to|\u2013|\u2014|,\s|-)\s*(?P<hi>{_NUM_SRC})")


def _num_and_decimals(text: str) -> tuple[float | None, int | None]:
    """`(value, decimals)` from one numeric token, or `(None, None)`."""
    # `·` FOLDED HERE TOO -- this is the literal-to-number converter, and a
    # literal it cannot read becomes a value the register does not hold.
    # SAME RULE AS `celltypes.decimal_comma_repair`, read from the one place it
    # is defined: a thousands group cannot start with zero, so `0,561` is a
    # decimal comma. Two spellings of one convention is the defect this file
    # has spent the day finding in other modules.
    from .tools.celltypes import decimal_comma_repair
    t = (decimal_comma_repair(text).replace("\u2212", "-")
         .replace("\u00b7", ".").replace(",", ""))
    try:
        v = float(t)
    except (TypeError, ValueError):
        return None, None
    return v, (len(t.split(".", 1)[1]) if "." in t else 0)


#: `t(28) = 2.10`, `F(2, 54) = 51.81`, `r(51) = -0.167`. Mirrors
#: `completeness.BODY_PATTERNS["nhst"]` -- the same shape, with the parts named
#: so they can be read out rather than only detected.
_NHST_SPAN = re.compile(
    r"\s*(?P<stat>[tFrzZ])\s*\(\s*(?P<df1>\d+(?:\.\d+)?)"
    r"(?:\s*,\s*(?P<df2>\d+(?:\.\d+)?))?\s*\)\s*=\s*"
    r"(?P<value>[-\u2212\u2013]?\d*\.?\d+)"
)


def prose_values(kind: str, raw: str) -> list[dict]:
    """`[{role, value, decimals}]` parsed out of ONE prose span.

    WHY THIS EXISTS. `groups_from_body_items` hard-coded `value: None`, so every
    statistic the floor found in running text reached the register as a printed
    STRING and nothing else. MEASURED over the eleven-paper run: of 2,829 values
    the papers themselves printed, **826 had no number at all, and every one of
    them was body-anchored** -- 275 of 275 `mean_pm_prose`, 165 of 165
    `named_equality`, 116 of 116 `p_value`. Table-anchored values: 2,003 parsed,
    0 unparsed. The split was total. The table path worked and this one had
    never been finished.

    What that cost: on `10.1161--strokeaha.124.049834` all 141 body values were
    valueless, including all 56 p-values, and the five complete
    `WTS=..., df=..., P<...` blocks the paper prints gave statcheck nothing.

    THE NUMBER IS PARSED BY `celltypes.parse_cell`, NOT HERE, wherever that
    reader already understands the form -- `65.2 ± 1.17` is the same quantity
    whether a table cell or a sentence prints it, and two parsers would be two
    answers. This function's own job is the part `parse_cell` cannot do: strip
    the prose label, and use that label to name the role.
    """
    from .tools.celltypes import parse_cell, repair_unicode

    # REPAIR BEFORE PARSING, and only for parsing. The branches below that
    # delegate to `parse_cell` get this for free; the ones that read the text
    # themselves -- `estimate_ci_prose`, `p_value`, `n_of_total` -- did not, so
    # a repair that the table path had applied since forever was absent from
    # half of this function.
    #
    # MEASURED on the eleven-paper run: `International Journal of Stroke` sets
    # decimals as MIDDLE DOTS in Lancet house style, 158 times in one paper, and
    # `-0·077 (95% CI: -7·716 to -2·437)` reached the register as estimate 77,
    # ci_low 716, ci_high -2. Every one of the three numbers wrong, the interval
    # inverted, and `check_estimate_ci` ready to pronounce on it.
    #
    # `raw` is rebound LOCALLY, so the `printed` text the caller records is
    # still what the paper set. The repair stays visible by comparing the two
    # rather than being hidden inside the number.
    raw = repair_unicode((raw or "").strip())[0]
    out: list[dict] = []

    def add(role, text):
        v, dec = _num_and_decimals(text)
        if v is not None:
            out.append({"role": role, "value": v, "decimals": dec})

    if kind == "mean_pm_prose":
        # DELEGATED WHOLE. `parse_cell` already returns `mean_sd` for this, with
        # both decimal counts, and the table path consumes exactly that. The
        # dispersion may be an SD, an SE or a half-interval and neither reader
        # decides which -- the typer refuses when the label does not say, and
        # that refusal is the same one whichever path produced the value.
        c = parse_cell(raw)
        if getattr(c, "kind", None) == "mean_sd" and getattr(c, "value", None) is not None:
            out.append({"role": "mean", "value": c.value,
                        "decimals": getattr(c, "decimals_value", None)})
            if getattr(c, "sd", None) is not None:
                out.append({"role": "sd", "value": c.sd,
                            "decimals": getattr(c, "decimals_sd", None)})
        return out

    if kind == "percentage":
        c = parse_cell(raw)
        if getattr(c, "percent", None) is not None:
            out.append({"role": "percentage", "value": c.percent,
                        "decimals": getattr(c, "decimals_percent", None)})
            return out
        nums = _PROSE_NUM.findall(raw)
        if nums:
            add("percentage", nums[0])
        return out

    if kind == "named_equality":
        m = re.match(r"\s*([A-Za-z\u03b1\u03b2\u03c7\u03b7][A-Za-z0-9_\u00b2\u03b1\u03b2]*)", raw)
        sym = (m.group(1) if m else "").lower()
        # the subscripts that survive extraction fused to the symbol
        role = _SYMBOL_ROLE.get(sym)
        if role is None:
            for k in sorted(_SYMBOL_ROLE, key=len, reverse=True):
                if sym.startswith(k):
                    role = _SYMBOL_ROLE[k]
                    break
        nums = _PROSE_NUM.findall(raw)
        if nums:
            add(role or "unknown", nums[-1])
        return out

    if kind == "p_value":
        # THE COMPARATOR IS KEPT ON THE PRINTED STRING AND OFF THE VALUE. A
        # censored `P < 0.001` is not a p-value of 0.001, and writing one would
        # hand a checker a precision the paper never claimed. The bound is the
        # number; whether it is exact is what `printed` still says.
        nums = _PROSE_NUM.findall(raw)
        if nums:
            add("p", nums[-1])
        return out

    if kind in ("ci_to_form", "estimate_ci_prose"):
        # THE SEPARATOR MUST NOT BECOME A MINUS SIGN. A first version scanned
        # for numbers and took the next two, and `0.548 (95% CI, 0.182-0.912)`
        # came out with `ci_high = -0.912` -- an upper bound below its lower
        # bound, and below the estimate. A checker handed that pair reports an
        # interval the paper never printed, against authors who printed a
        # perfectly ordinary one. Real negative bounds exist (`-1.2 to -0.3`),
        # so the sign cannot simply be stripped: the interval is matched as a
        # whole, with the separator captured, and only a sign that is NOT the
        # separator can reach a bound.
        if kind == "estimate_ci_prose":
            lead = _PROSE_NUM.match(raw.strip())
            if lead:
                add("estimate", lead.group(0))
        m = _INTERVAL.search(raw)
        if m:
            add("ci_low", m.group("lo"))
            add("ci_high", m.group("hi"))
        return out

    if kind == "nhst":
        # THE ONE PROSE KIND THAT CARRIES A WHOLE TEST, AND IT PARSED TO
        # NOTHING. `_body_items`' `nhst` pattern captures `t(28) = 2.10` and
        # `F(2, 54) = 51.81` -- statistic, degrees of freedom and value, the
        # complete input to `recalc_stat_to_p` -- and this function had no
        # branch for it, so every such span reached the register as one
        # `unknown` row with `value: None`.
        #
        # MEASURED 2026-08-22 over a 9-paper psychology batch: 38 `nhst` groups
        # on 10.1007--s00221-011-2544-z, 18 on 10.1177--0956797615569889, 15 on
        # 10.1177--0093854811403123, and not one of them carried a number. The
        # p-values sit in their own `p_value` groups at other offsets, so
        # PAIRING them is still the model's job (see `groups_from_body_items`)
        # -- but the halves being unparsed made even the pairing impossible.
        m = _NHST_SPAN.match(raw)
        if m:
            out.append({"role": "statistic_kind", "value": None,
                        "decimals": None, "text": m.group("stat")})
            add("df", m.group("df1"))
            if m.group("df2"):
                add("df2", m.group("df2"))
            add("statistic", m.group("value"))
            # `statistic_kind` is not a ROLE -- it names WHICH distribution, not
            # a quantity. Carried on the statistic row instead of as a row of
            # its own, so the closed role vocabulary stays closed.
            kindrow = out.pop(0)
            for row in out:
                if row["role"] == "statistic":
                    row["statistic_kind"] = kindrow["text"]
        return out

    if kind == "n_of_total":
        nums = _PROSE_NUM.findall(raw)
        if len(nums) >= 2:
            add("count", nums[0])
            add("denominator", nums[1])
        return out

    return out


def _prose_value_rows(item: dict, anchor: dict, fallback_role: str) -> list[dict]:
    """The value rows for one prose span: parsed where we can, honest where not.

    A span we cannot parse still yields ONE row carrying the printed string and
    `value: None`, exactly as before -- an unparsed statistic is still a
    statistic the paper printed, and dropping it would shrink the floor that
    exists to say what was overlooked.
    """
    raw = item.get("raw")
    parsed = prose_values(str(item.get("kind") or ""), str(raw or ""))
    if not parsed:
        parsed = [{"role": fallback_role, "value": None, "decimals": None}]
    rows = []
    for n, got in enumerate(parsed):
        role = got.get("role") or fallback_role
        # Two values of one role in one span cannot share an id.
        a = dict(anchor) if n == 0 else {**anchor, "offset": f"{anchor.get('offset')}#{n}"}
        row = {
            "id": value_id(a, role),
            "role": role,
            "role_class": role_class(role),
            "printed": raw,
            "value": got.get("value"),
            "decimals": got.get("decimals"),
            "anchor": dict(a),
            "group": group_id(anchor),
            "variable_id": None,
        }
        # WHICH distribution, for a `statistic` row. Not a role -- t, F, r and
        # z are all "the statistic" -- but the dispatcher cannot pick between
        # `recalc_stat_to_p`'s five branches without it, and dropping it here
        # would leave the parse in `prose_values` with no consumer.
        if got.get("statistic_kind"):
            row["statistic_kind"] = got["statistic_kind"]
        rows.append(row)
    return rows


#: Which checks WOULD run on a prose span of each kind. The body counterpart of
#: `dispatch.DISPATCH`, which is keyed on TABLE-CELL kinds and so had nothing to
#: say about anything printed in a sentence.
#:
#: MEASURED 2026-08-22 over a 9-paper psychology batch: `applicable_tools` was
#: hard-coded `[]` for every body group, so `value_register.json` reported
#: `n_groups_with_no_applicable_tool: 74 / 74` on 10.1007--s00221-011-2544-z and
#: an empty list on six of the nine papers. An empty list is this module's word
#: for "the dispatcher considered it and declined" -- see `applicable_tools`,
#: where None and () are deliberately different answers -- so a register that
#: had never looked was reporting a decision.
#:
#: THIS NAMES WHAT COULD RUN, NOT WHAT DID. Nothing here executes a check: an
#: `nhst` span and the `p_value` it belongs with sit in separate groups at
#: separate offsets, and joining them is a parse this pass cannot do (see
#: `groups_from_body_items`). What it makes possible is the honest coverage
#: sentence -- "this printed statistic was never checked" -- which an empty list
#: rendered as "there was nothing to check".
BODY_DISPATCH: dict[str, tuple[str, ...]] = {
    # statistic + df, complete but for the p, which is its own group
    "nhst": ("recalc_stat_to_p", "statcheck"),
    "chi2": ("recalc_stat_to_p", "statcheck"),
    # a p on its own is checkable only against the statistic beside it
    "p_value": ("statcheck",),
    # mean and SD in running text: the granularity family, IF the n and the
    # variable's type can be established -- which is why these are candidates
    # and not a promise.
    "mean_pm_prose": ("grim_check", "grimmer_check", "sprite_reconstruct"),
    "mean_sd_prose": ("grim_check", "grimmer_check", "sprite_reconstruct"),
    "mean_sd_apa": ("grim_check", "grimmer_check", "sprite_reconstruct"),
    "estimate_ci_prose": ("check_estimate_ci",),
    "ci_to_form": ("check_estimate_ci",),
    "n_of_total": ("check_count_percent", "grim_percentage"),
    # A bare percentage with no denominator in the span. `grim_percentage`
    # needs an n the register does not have here; naming it is what makes the
    # missing n reportable rather than invisible.
    "percentage": ("grim_percentage",),
    # DELIBERATELY EMPTY, and that is a different answer from absent. A named
    # equality is `n = 202` or `OR = 1.27` -- one number with a label and no
    # second quantity to check it against.
    "named_equality": (),
    "count": (),
    "numeric": (),
    "ambiguous": (),
}


def body_applicable_tools(kind: str) -> tuple[str, ...] | None:
    """Checks that WOULD run on a prose span of this kind.

    `None` when this table has no entry for the kind at all, matching
    `applicable_tools`' None-vs-() contract: never considered and considered
    then declined are different facts about our coverage.
    """
    return BODY_DISPATCH.get(kind)


def groups_from_body_items(items: list[dict]) -> list[dict]:
    """Value groups for prose statistics, from `completeness._body_items`.

    ONE VALUE PER GROUP, FOR NOW, AND SAID SO. `_body_items` emits one row per
    regex match, so `M = 4.20 (SD = 0.21)` in running text arrives as two
    unrelated rows and this function cannot join them -- the information that
    they belong together was lost before it got here. Grouping prose is the
    model's job (see the design note); this records what the mechanical pass can
    honestly say, which is that each span holds a value and where it sits.
    """
    out: list[dict] = []
    for idx, item in enumerate(items or []):
        # `_body_items` always supplies an offset and its overlap set makes two
        # items at one offset impossible -- but a caller-supplied list need not,
        # and every item without one collided on `grp:body:None`.
        offset = item.get("offset")
        anchor = {"where": "body",
                  "offset": offset if offset is not None else f"i{idx}"}
        role = _BODY_ROLE.get(item.get("kind"), "unknown")
        out.append({
            "id": group_id(anchor),
            "kind": item.get("kind"),
            "variable_id": None,
            "quote": item.get("raw"),
            "context": item.get("context"),
            "anchor": dict(anchor),
            "values": _prose_value_rows(item, anchor, role),
            "applicable_tools": list(
                body_applicable_tools(item.get("kind")) or ()),
            "applicable_tools_known": (
                body_applicable_tools(item.get("kind")) is not None),
            "checks": [],
            # NOT a claim that these values are unrelated -- a claim that this
            # pass cannot tell. The distinction is the whole point.
            "grouping": "ungrouped_prose",
        })
    return out


def _data_type(variable: dict | None) -> str:
    if not variable:
        return "unknown"
    # NOT GUARDED, for the reason given in `applicable_tools`: "unknown" is a
    # real answer about a variable nobody typed, and returning it for a crash
    # would spell a broken install exactly like an undeclared row.
    from .dispatch import _canonical_type
    return _canonical_type(variable)


def same_value_edges(groups: list[dict]) -> dict[str, list[str]]:
    """Values that are the same printed number in the same role.

    COMPUTED, NEVER AUTHORED. Greg's "when the same value is used across
    checks": an `n = 93` printed in twenty groups is ONE fact about the paper,
    and a reader who sees a verdict on it deserves to see the other nineteen
    places it governs.

    Keyed on the printed literal rather than the parsed float, because `71` and
    `71.0` are different assertions about precision even though Python calls
    them equal -- and precision is what every granularity check is testing.
    Role must match too: a count of 30 and a denominator of 30 are not the same
    claim.
    """
    by_key: dict[tuple, list[str]] = {}
    for g in groups:
        for v in g.get("values") or []:
            printed = str(v.get("printed") or "").strip()
            if not printed:
                continue
            by_key.setdefault((printed, v.get("role")), []).append(v["id"])
    return {ids[0]: ids for ids in by_key.values() if len(ids) > 1}


def table_for_cells(register: dict, cells: list[dict] | None) -> str | None:
    """Which table in the register a `check_table` call was run on.

    `check_table` is handed cells with no table name, so a run's ledger records
    verdicts that know their row and their position and NOT which table they
    came from. Attaching them without a table would let a verdict from table 1
    land on table 2's group at the same coordinates -- the same cross-attachment
    that made an honest cell carry another row's accusation, one level up.

    Matched on the multiset of printed cell texts, which is what the call and
    the table demonstrably share. Returns None when no table matches or more
    than one does, and the caller must then leave the verdicts unjoined rather
    than pick: a guessed table is a guessed accusation.
    """
    want = sorted(str((c or {}).get("raw") or "") for c in (cells or []))
    if not want:
        return None
    hits = []
    for name in {(g.get("anchor") or {}).get("table")
                 for g in (register.get("groups") or [])
                 if (g.get("anchor") or {}).get("where") == "table"}:
        have = sorted(str(c) for c in (register.get("_table_cells") or {}).get(name, []))
        if have and have == want:
            hits.append(name)
    return hits[0] if len(hits) == 1 else None


def attach_checks(register: dict, results: list[dict] | None,
                  table: str | None = None,
                  consistent: list[dict] | None = None) -> dict:
    """Join a `check_table` run's verdicts onto the register's groups.

    JOINED ON `(row_label, row, ordinal)`, NOT ON THE PRINTED TEXT. Two columns
    of a row routinely print the same number -- a placebo and a treatment arm
    both reading `12 (40.0)` is ordinary -- and joining on the text would attach
    one arm's verdict to the other's value.

    THE ROW NUMBER IS IN THE KEY, and its absence was a false accusation.
    `(row_label, ordinal)` is NOT unique within a table: clinical tables
    routinely repeat a label -- "Male" under two arms, "Age" at baseline and at
    endpoint -- and without the row number every verdict attached to every group
    in the collision set. An honest cell whose own checks all PASSED came away
    carrying the other row's `suspicious` finding, which is the worst output
    this toolkit can produce. Found by an adversarial review, not by the 25
    tests shipped alongside it, none of which used a repeated label.

    `consistent` is `check_table`'s `consistent_index`, and it matters as much
    as `results`: a group with no attached check reads as UNCHECKED, and a group
    whose checks all passed is checked and clean. Attaching only the findings
    would spell those two identically -- the failure this repo keeps finding.
    """
    by_key: dict[tuple, list[dict]] = {}
    for g in register.get("groups") or []:
        a = g.get("anchor") or {}
        if a.get("where") != "table":
            continue
        if table is not None and a.get("table") != table:
            continue
        by_key.setdefault((_row_label(g.get("row_label")), a.get("row"),
                           a.get("ordinal")), []).append(g)

    def _join(records, passed: bool) -> int:
        n = 0
        for r in records or []:
            cell = r.get("cell") or {}
            key = (_row_label(cell.get("row_label")), cell.get("row"),
                   cell.get("ordinal"))
            for g in by_key.get(key, ()):
                g.setdefault("checks", []).append({
                    "check_id": r.get("check_id"),
                    "tool": r.get("tool"),
                    "severity": r.get("severity") or ("consistent" if passed else None),
                    "passed": passed,
                })
                n += 1
        return n

    joined = _join(results, False) + _join(consistent, True)
    register["n_checks_attached"] = register.get("n_checks_attached", 0) + joined
    # A CHECK THAT MATCHED NO GROUP IS NOT NOTHING. It means the register and
    # the dispatcher disagree about what cells exist, which is worth surfacing
    # rather than swallowing -- a silent zero here would read as a clean join.
    seen = {(_row_label((r.get("cell") or {}).get("row_label")),
             (r.get("cell") or {}).get("row"),
             (r.get("cell") or {}).get("ordinal"))
            for r in list(results or []) + list(consistent or [])}
    register["unjoined_check_cells"] = sorted(
        str(k) for k in seen if k not in by_key)
    return register


def attach_not_run(register: dict, not_run: list[dict] | None,
                   table: str | None = None) -> dict:
    """Record WHY a group with applicable tools has no verdict.

    Without this the register spells three different things the same way: a
    value nothing applies to, a value a check cleared, and a value a check was
    REFUSED on. The third is the one a reader most needs -- measured on
    10.1007--s00702-004-0248-2, all 24 checkable table groups came back with no
    verdict because the column header reads `Placebo (n ¼ 68)`, glyph
    corruption having eaten the `=` so the denominator could not be read.
    Silence there would have looked like a clean table.

    ROW-LEVEL, AND SAID SO. `check_table` records a refusal per (row, tool), not
    per cell, so every group in a row receives the same reason. That is coarser
    than the verdict join above and is marked `granularity: "row"` rather than
    quietly presented as if it were per value.

    The row NUMBER is part of the key, for the reason given in `attach_checks`:
    keying on the label alone stamped row 7's refusal onto row 2's group
    whenever a table repeated a label, and `granularity: "row"` was then itself
    untrue -- it was granularity `row_label`.
    """
    by_row: dict[Any, list[dict]] = {}
    for g in register.get("groups") or []:
        a = g.get("anchor") or {}
        if a.get("where") != "table":
            continue
        if table is not None and a.get("table") != table:
            continue
        by_row.setdefault((_row_label(g.get("row_label")), a.get("row")),
                          []).append(g)

    n = 0
    for entry in not_run or []:
        # `cell` on a not_run entry is the row LABEL, not a cell dict.
        for g in by_row.get((_row_label(entry.get("cell")),
                             entry.get("row")), ()):
            g.setdefault("not_run", []).append({
                "tools": list(entry.get("tools") or []),
                "reason": entry.get("reason"),
                "kind": entry.get("kind"),
                "granularity": "row",
            })
            n += 1
    register["n_refusals_attached"] = register.get("n_refusals_attached", 0) + n
    return register


def call_ledger_balance(register: dict, calls: list[dict]) -> dict:
    """Every tool call ends in exactly one recorded state, and they sum.

    A CONSERVATION LAW, not a statistic. `coverage()` already asserts that a
    GROUP is in exactly one state; this asserts the same of a CALL, and the
    difference is that a call is something we did rather than something the
    paper contains -- so an unbalanced ledger is always our defect.

    WHY IT EXISTS. MEASURED 2026-08-20 over the nine registers of the
    eleven-paper run: `n_checks_attached` was ZERO on every paper, while 27 to
    53 calls each reported no matchable value. The verdicts had been computed
    and saved, and were dropped at a silent parse. Nothing failed. No test went
    red. It was found weeks later by someone probing a register by hand.

    Every defect this session found is a violation of this law -- 826 prose
    values with no number, 265 table cells discarded by XML precedence, 143
    silent groups, the zero attachments. Each was a thing produced and then
    ending in NO state at all. One invariant, checked per run, surfaces them the
    day they appear.

    `accounted` is the assertion. It is FALSE when the states do not sum to the
    number of calls, and a false value is a bug here, never a finding about the
    paper.
    """
    checks = [c for c in (calls or []) if is_check_call(c)]
    unreadable = [c for c in checks if c.get("result_unreadable")]
    # COUNT CALLS, NOT ROWS. `n_checks_attached` counts attached RESULT ROWS,
    # and one `check_table` call carries many, so adding it here counted a
    # single call up to a dozen times. That is where the three NEGATIVE
    # residuals in this law's first measurement came from: not two counters
    # describing the same call, but one counter describing something else
    # entirely. `n_check_table_calls_joined` is the per-call figure;
    # `n_checks_attached` stays in the register as the row count it is.
    joined = int(register.get("n_per_cell_checks_joined") or 0)
    joined += int(register.get("n_check_table_calls_joined") or 0)
    # EVERY RECORDED STATE, NOT TWO OF THEM. `n_per_cell_checks_unmatched` and
    # `n_per_cell_checks_ambiguous` were written to the register on every run
    # and read by nothing -- so 201 calls that HAD an honest recorded state were
    # reported as ending in none. A residual that large hides the real ones.
    unmatched = int(register.get("n_calls_with_no_matchable_value") or 0)
    unmatched += int(register.get("n_check_table_calls_unmatched") or 0)
    unmatched += int(register.get("n_per_cell_checks_unmatched") or 0)
    unmatched += int(register.get("n_per_cell_checks_ambiguous") or 0)
    # UNREADABLE IS A SUBSET OF UNMATCHED, NOT A THIRD BUCKET. A call whose
    # result we could not parse cannot be joined to a value either, so it is
    # already inside `n_unmatched`; adding it again over-counted every paper on
    # the first run of this law. It is reported as a REASON, not a state.
    #
    # THE RESIDUAL IS THE POINT, and it is published rather than folded into a
    # boolean I could tune until it read True. `n_unaccounted` is the number of
    # calls that ended in no recorded state at all.
    unaccounted = len(checks) - (joined + unmatched)
    out = {
        "n_calls": len(checks),
        "n_joined": joined,
        "n_unmatched": unmatched,
        "n_unreadable": len(unreadable),
        "n_unaccounted": unaccounted,
        "accounted": unaccounted == 0,
        "note": ("`n_unaccounted` counts calls that ended in NO recorded state: "
                 "not attached to a value, not counted as unmatchable, not "
                 "marked unreadable. Any number other than zero is a defect in "
                 "this bookkeeping, never a fact about the paper. A negative "
                 "number means two counters are counting the same call."),
    }
    if unreadable:
        import collections
        out["unreadable_because"] = dict(collections.Counter(
            str(c.get("result_unreadable")) for c in unreadable))
    return out


#: Arithmetic that must hold of a set of numbers whatever the paper is about.
#: Each entry is (name, evaluable, holds) -- and the two functions are separate
#: ON PURPOSE. A rule that cannot be evaluated has NOT passed, and collapsing
#: those two into one boolean is how "we could not check this" comes to be
#: spelled the same way as "this is fine".
_INVARIANTS: tuple = (
    ("ci_low_above_ci_high",
     lambda v: v.get("ci_low") is not None and v.get("ci_high") is not None,
     lambda v: v["ci_low"] <= v["ci_high"]),
    ("estimate_outside_its_own_ci",
     lambda v: all(v.get(k) is not None for k in ("ci_low", "ci_high", "estimate")),
     lambda v: v["ci_low"] <= v["estimate"] <= v["ci_high"]),
    ("p_outside_zero_to_one",
     lambda v: v.get("p") is not None,
     lambda v: 0.0 <= v["p"] <= 1.0),
    ("percentage_outside_zero_to_hundred",
     lambda v: v.get("percentage") is not None,
     lambda v: 0.0 <= v["percentage"] <= 100.0),
    ("count_above_n",
     lambda v: v.get("count") is not None and v.get("n") is not None,
     lambda v: v["count"] <= v["n"]),
    ("negative_count",
     lambda v: v.get("count") is not None,
     lambda v: v["count"] >= 0),
    ("negative_dispersion",
     lambda v: v.get("sd") is not None or v.get("se") is not None,
     lambda v: (v.get("sd") is None or v["sd"] >= 0)
               and (v.get("se") is None or v["se"] >= 0)),
    ("n_not_a_whole_number",
     lambda v: v.get("n") is not None,
     lambda v: float(v["n"]) == int(v["n"])),
)

#: How many examples of each violation to carry. The COUNT is always exact; the
#: examples are a sample, because one paper's deposited spreadsheet produced 298
#: of one kind and a register is meant to be readable.
_MAX_INVARIANT_EXAMPLES = 5


#: How far below the stated `n` an explaining denominator may sit before the
#: explanation stops being evidence. NOT A TOLERANCE ON THE ARITHMETIC -- that
#: is exact -- but two bounds read off a measurement, and a cell qualifies on
#: EITHER, because neither works alone.
#:
#: MEASURED, 1,200 random percentages per sample size, asking how often SOME
#: denominator reproduces an arbitrary value by luck:
#:
#:     n      gap<=3    gap<=5%      any            n      gap<=3   gap<=5%    any
#:     17       0.2%      0.2%      0.8%            117      0.3%     0.9%    6.2%
#:     50       0.2%      0.2%      2.0%            201      0.3%     0.8%    9.1%
#:     104      0.2%      0.3%      5.0%            540      0.4%     2.6%   20.4%
#:
#: WHY BOTH. An absolute bound alone forgives a gap of 10 in a sample of 50 --
#: 20% of a trial arm silently missing one variable, which does not happen
#: unremarked. A relative bound alone refuses a gap of ONE in a sample of 17,
#: which is one person and the most ordinary thing in a baseline table. The
#: disjunction admits a handful of people at any size, and a small share at
#: large sizes, and nothing else.
#:
#: THE CASE THAT SET THE ABSOLUTE BOUND, verbatim from the corpus:
#:
#:     | Characteristics            | CblG ( n = 50) | Ctrl ( n = 50) |
#:     | Atrial fibrillation, n (%) | 19 (48)        | 22 (44)        |
#:
#: `22/50 = 44` exactly, so 50 IS that row's denominator -- and `19/50 = 38`
#: against a printed 48. A first version of this rule downgraded it to
#: `indeterminate` because n=40 reproduces 48, and that is a FALSE CLEAR: the
#: paper's own sibling cell rules out the missing-data reading.
_EXPLAINED_WITHIN_OBSERVATIONS = 3
_EXPLAINED_WITHIN_SHARE = 0.05


def _section_key(table: Any, row: Any, col_label: Any) -> str:
    """One key for a cell's position, written once and read once.

    A register is JSON, so the tuple `(table, row, col_label)` cannot be a key.
    The separator is a unit separator rather than a pipe because the
    stacked-header fold JOINS a spanning header to its sub-header with " | " --
    a `col_label` legitimately contains pipes, and keying on one would collide
    two different columns of the same table.
    """
    return f"{table}\x1f{row}\x1f{col_label}"


def check_stated_denominators(register: dict) -> dict:
    """Run the count/percent check wherever the column header states its own n.

    WHY THIS RUNS WITHOUT A MODEL. MEASURED over the eleven-paper run: 125
    checkable values were never checked, and **all 125 had
    `dispatch_considered = True`** -- dispatch offered them and the model did
    not call. Their applicable tools were 99 `grim_percentage`, 99
    `check_count_percent`, 16 `check_sd_or_se`. Meanwhile the checks the model
    DID run on this shape produced 15 false suspicions out of 18, every one
    because it chose the wrong denominator.

    So the same arithmetic is both under-run and mis-fed, and for the subset
    where the column header states its own `n` neither is necessary: the
    denominator is printed in the cell's own column heading, and 149 of 158
    such cells reproduce their printed percentage from it exactly.

    THE DENOMINATOR COMES FROM STRUCTURE, NEVER FROM A GUESS. Only a
    `level="column"` n is used. A stacked header's outer figure covers a group
    of columns -- `PP Population, n = 318` sits above arms of 201 and 117 -- and
    is true without being this column's, so it is declined rather than
    borrowed. That single distinction is the difference between 149 exact
    reproductions and 86.

    A NEAR MISS IS A FACT ABOUT OUR PAIRING, NOT ABOUT THE PAPER, and this
    follows a precedent already in `check_count_percent`: when a count exceeds
    its own denominator that tool returns `indeterminate` and says "the pairing
    is wrong, not the paper". A printed percentage that the stated `n` misses
    but a denominator a few smaller reproduces EXACTLY is the same situation --
    a variable with missing data has its own denominator, and that is the
    single commonest convention in a baseline table. Such a cell is recorded
    `indeterminate` with the explaining denominator named, never `suspicious`.

    What survives as `suspicious` is a cell no denominator at or below the
    stated `n` reproduces. On this corpus that is **zero** cells: the check adds
    coverage without adding one accusation.
    """
    from .tools.count_percent import check_count_percent

    ran = attached = skipped = 0
    by_severity: dict = {}
    reasons: dict = {}

    def _skip(why: str) -> None:
        nonlocal skipped
        skipped += 1
        reasons[why] = reasons.get(why, 0) + 1

    for g in register.get("groups") or []:
        if is_deposited_raw_data(g):
            continue
        vals = {v.get("role"): v for v in (g.get("values") or [])}
        count, pct = vals.get("count"), vals.get("percentage")
        if not (count and pct):
            continue
        if any(c.get("tool") == "check_count_percent" for c in (g.get("checks") or [])):
            _skip("already checked by the model")
            continue
        # A TABLE FOOTNOTE'S `N` IS NOT A DENOMINATOR, AND MUST NEVER BECOME
        # ONE HERE. `footnotes` began reaching the floor in a685211, so a
        # table-level "Note: N = 107" is now one `or` away from this call, and
        # adding it would look like an obvious improvement.
        #
        # It is the opposite. A column header's n has a STATED SCOPE -- the
        # check below accepts it only when `level == "column"` -- while a
        # footnote's scope is unstated. It may govern the table, one panel, one
        # wave, or one column, and nothing in the text says which. Feeding it
        # here would reproduce the mechanism that produced 119 false
        # `suspicious` verdicts on 10.1038--s41537-025-00576-3: a
        # multi-response section whose counts sum ABOVE the stated n, where
        # `explaining_denominator` searches only downward and the near-miss
        # downgrade therefore never fires. A footnote is MORE exposed than a
        # header, not less, because there is no `level` to check.
        anchor_of = g.get("anchor") or {}
        stated = _stated_n(anchor_of.get("col_label"))
        if stated is None:
            _skip("the column header states no n")
            continue
        if stated.get("level") != "column":
            # DECLINED, NOT BORROWED. See the docstring: an outer level covers
            # several columns and is not this column's denominator.
            _skip("the only n in the header covers a grouping of columns")
            continue
        # THE SECTION GETS A VETO OVER THE HEADER, and this is the whole repair.
        #
        # MEASURED 2026-08-27 on `10.1038--s41537-025-00576-3`: this function
        # returned 119 `suspicious` out of 244 checks and ALL 119 WERE FALSE.
        # Every one of them was a row inside a MULTI-RESPONSE section -- a
        # patient appears on several drug rows, so the section's counts sum
        # ABOVE the column total, and `explaining_denominator` searches only
        # DOWNWARD from n (`range(n, count - 1, -1)`) and therefore cannot find
        # a denominator larger than the header's. The near-miss downgrade below
        # never fires, and the paper is accused of arithmetic it got right.
        #
        # `check_table` already had this guard: composite refuses a column
        # whose two denominators disagree, in as many words -- "two sources for
        # one denominator disagree, so neither is used". This path never
        # reached it, because `dispatch` and the register are joined AFTER the
        # run, not before it. So the same predicate is now computed at build
        # time and read here.
        #
        # WHY REFUSE RATHER THAN RE-CHECK against composite's derived n: there
        # is none. Measured on the same paper, of the 134 disputed cells,
        # ZERO carry a derived n -- composite withholds it by design when the
        # sources disagree, and inventing one here would be the guess this
        # module exists to avoid. Refusing costs 134 of 244 checks and buys
        # 119 fewer false accusations, which is the trade the cardinal rule
        # names.
        _sec_key = _section_key(anchor_of.get("table"), anchor_of.get("row"),
                                anchor_of.get("col_label"))
        _why = (register.get("_section_disputed") or {}).get(_sec_key)
        if _why:
            _skip(f"the section and the column header disagree: {_why}")
            continue
        _sec = (register.get("_section_n") or {}).get(_sec_key)
        if _sec and _sec.get("n") and int(_sec["n"]) != int(stated["n"]):
            # Composite VERIFIED this n against the paper's own printed
            # percentages before returning it; the header n is unverified.
            # Prefer the verified one and say so.
            stated = {**stated, "n": int(_sec["n"]),
                      "n_source": _sec.get("n_source"),
                      "instead_of_header_n": int(stated["n"])}
        c_val, p_val = count.get("value"), pct.get("value")
        dec = pct.get("decimals")
        if c_val is None or p_val is None or dec is None:
            _skip("count, percentage or printed decimals unavailable")
            continue
        result = check_count_percent(count=int(c_val), percentage=float(p_val),
                                     n=int(stated["n"]), decimals=int(dec))
        ran += 1
        severity = result.get("severity")
        audit = explaining_denominator(c_val, p_val, stated["n"], dec)
        # A NEAR MISS IS OUR PAIRING, NOT THE PAPER'S ARITHMETIC.
        near = (audit and audit.get("reproduces_printed_value")
                and audit.get("n_missing")
                and (audit["n_missing"] <= _EXPLAINED_WITHIN_OBSERVATIONS
                     or (audit.get("share_below") or 1.0) <= _EXPLAINED_WITHIN_SHARE))
        if severity == "suspicious" and near:
            severity = "indeterminate"
            result = {**result, "severity": severity,
                      "downgraded_from": "suspicious",
                      "downgraded_because": (
                          f"a denominator of {audit['denominator']}, "
                          f"{audit['n_missing']} below the {audit['n_used']} this "
                          f"column's header states, reproduces the printed "
                          f"percentage exactly -- the ordinary signature of a "
                          f"variable with missing data. This says the pairing is "
                          f"wrong, not the paper.")}
        by_severity[severity] = by_severity.get(severity, 0) + 1
        g.setdefault("checks", []).append({
            "check_id": f"stated-denominator:{g.get('id')}",
            "tool": "check_count_percent",
            "severity": severity,
            "passed": severity == "consistent",
            "joined_by": "the column header's own n",
            "ran_without_a_model": True,
            "denominator_audit": audit,
            "result": result,
        })
        attached += 1

    return {"n_ran": ran, "n_attached": attached, "n_skipped": skipped,
            "by_severity": by_severity, "skipped_because": reasons,
            "note": ("Deterministic. The denominator is the one this cell's own "
                     "column header states, never a model's choice and never an "
                     "outer level's. A percentage the stated n misses but a "
                     "denominator a few smaller reproduces exactly is recorded "
                     "`indeterminate`, because that is a fact about our pairing "
                     "rather than about the paper.")}


#: What a paper writes where it HAS no value. Matched whole, case-insensitively:
#: a bare `-` is a marker, `-1.2` is a measurement.
_NO_VALUE_MARKERS = frozenset({
    "na", "n/a", "n.a.", "nd", "n.d.", "nr", "n.r.", "none", "nil",
    "-", "--", "---", "\u2013", "\u2014", ".", "..", "x", "*", "\u00b7",
})


def _looks_like_lost_values(text: str) -> bool:
    """Does this unparsed cell hold MEASUREMENTS, or a label with a number in it?

    "contains a digit" was the first rule and it was wrong: `Obesity at age 12
    y` is a row label, and counting it as a lost value overstates our own
    failure -- the opposite error to the one this split exists to correct, and
    just as much a fact about us reported as a fact about them.

    The glued signature is TWO OR MORE separate numeric tokens
    (`189153851 28668870 10307907`, `<.001 <.001`), or a single token in a cell
    that is mostly digits rather than mostly letters. A label carrying one
    incidental number is neither.
    """
    import re as _re

    if "http" in text or "www." in text:
        return False          # a URL's digits are not measurements
    toks = _re.findall(r"[<>=]?\s*-?\d[\d,.]*", text)
    if not toks:
        return False
    # DIGIT-DOMINANT, for one token or many. Requiring it only of single-token
    # cells let `Obesity at age 12 and 18 y` through on its two numbers, which
    # overstates our loss -- our failure reported as larger than it is, still a
    # fact about us stated wrongly. A collapsed row of measurements carries
    # almost no letters: `81.2 (81.0-81.6) 11.6 (11.3-11.9)` has none.
    letters = sum(ch.isalpha() for ch in text)
    digits = sum(ch.isdigit() for ch in text)
    return digits >= letters


def no_value_reasons(raw_cells) -> dict:
    """Split "produced no value" into the paper's fact and our failure.

    `n_cells_with_no_value` counted both as one number, which states OUR defect
    as a property of the paper -- the confusion this module exists to prevent.

    MEASURED 2026-08-22 over the twelve-paper corpus: of 1,838 such cells,
    **1,182 contain digits** --

        '189153851 28668870 10307907 8421099'          four counts fused
        '81.2 (81.0-81.6) 11.6 (11.3-11.9) 4.0 ...'    estimate+CI fused
        '<.001 <.001'                                   two p-values fused

    -- against 656 that are the paper's own missing-data markers (`NA` 104,
    `X` 126, `-` 29, `--` 20) or text labels. The first kind is docling
    collapsing several table ROWS into one cell, and each holds four to eight
    printed numbers, so the real loss runs to several thousand values.

    THIS RECOVERS NOTHING, AND MUST NOT. A glued cell cannot say which column
    each number belongs to -- that is what makes it glued. Splitting one would
    attach a number to a heading it was never printed under, and a mean paired
    with another column's `n` is exactly how an honest paper gets accused. The
    fix for the loss is upstream, in extraction; the fix for the SILENCE is
    here.
    """

    cells = list(raw_cells or [])
    out = {"n_cells": len(cells), "n_blank": 0, "n_marker": 0,
           "n_unparsed_with_digits": 0, "n_text": 0, "examples": []}
    for c in cells:
        t = str(c if c is not None else "").strip()
        if not t:
            out["n_blank"] += 1
        elif t.lower() in _NO_VALUE_MARKERS:
            out["n_marker"] += 1
        elif _looks_like_lost_values(t):
            out["n_unparsed_with_digits"] += 1
            if len(out["examples"]) < 5:
                out["examples"].append(t[:60])
        else:
            out["n_text"] += 1
    out["note"] = (
        "`n_marker` and `n_text` are the PAPER saying it has no number there. "
        "`n_unparsed_with_digits` is OURS: a cell that prints digits and "
        "yielded no value, which on this corpus is a table row collapsed into "
        "one cell by the extractor. Those numbers are lost, not absent, and "
        "they are NOT parsed here -- a glued cell cannot say which column each "
        "number belongs to, and guessing would attach a value to a heading it "
        "was never printed under."
    )
    return out


def ambiguous_columns(register: dict) -> dict:
    """How many values sit under a column label that another column shares.

    `col_label_is_unique` has been computed for every table cell since the
    stacked-header work, and was consumed in exactly ONE place: `group_id`,
    deciding whether a value's id is keyed by its label or by its ordinal. That
    is a correct use of the fact and not the only one it is needed for.

    WHY, in `jats._header_depth`'s own words: when two columns carry the same
    label, "a mean drawn from one and an `n` from another are indistinguishable
    afterwards, and GRIM on that pair calls an honest paper impossible." The
    register holds the fact that would warn a reader and was dropping it -- the
    house failure of computing something correctly and losing it at the seam.

    MEASURED 2026-08-21 over the eleven-paper corpus: 971 of 1,907
    PDF-supplement groups (50.9%) sit under a non-unique label, against 129 of
    2,523 (5.1%) in main-article tables. Per COLUMN the supplement rate is
    18.6%; the duplicate-labelled columns are the data-dense ones, so per-cell
    exposure is about twice the per-column rate. **Report the per-cell figure**
    -- risk scales with values, not with headings, and quoting the smaller
    number because it is smaller is the habit the MO site audit exists to
    criticise.

    SURFACED, NOT GATED, deliberately. Suppressing checks on these groups would
    trade a POSSIBLE false accusation for a CERTAIN false all-clear, and the
    cardinal rule prefers that trade only when the suppression is proven
    unnecessary. This decides nothing; it lets a reader see what the pairing
    rests on.

    `n_unknown` counts groups carrying no flag at all. Nobody checked is not
    the same as checked-and-unique, and folding the two would report our own
    gap as the paper's cleanliness.
    """
    groups = register.get("groups") or []
    table = [g for g in groups
             if ((g.get("anchor") or {}).get("where")) == "table"]
    amb = 0
    unknown = 0
    tables: dict[str, int] = {}
    for g in table:
        a = g.get("anchor") or {}
        flag = a.get("col_label_is_unique")
        if flag is None:
            unknown += 1
            continue
        if flag is False:
            amb += 1
            key = str(a.get("table") or "?")
            tables[key] = tables.get(key, 0) + 1
    return {
        "n_groups": amb,
        "n_groups_total": len(table),
        "n_unknown": unknown,
        "share": round(amb / len(table), 4) if table else 0.0,
        "tables": dict(sorted(tables.items(), key=lambda kv: -kv[1])),
        "note": (
            "values whose column label is shared with another column of the "
            "same table. Reported, not suppressed: a check on such a value may "
            "be pairing it with a quantity from a different column, which is "
            "how a reading error becomes an accusation. Look at the named "
            "tables before reporting anything drawn from them."
        ),
    }


def check_invariants(register: dict) -> dict:
    """Arithmetic the register's own numbers must satisfy, checked every run.

    WHY AT BUILD TIME rather than in the test suite. One such rule already
    existed -- an interval whose bounds are the wrong way round -- and it is
    what caught the Lancet middle-dot corruption on 2026-08-20. It caught it in
    the TEST SUITE, days after the run that produced it, and only because two
    recovered papers happened to bring 158 middle-dot decimals into a corpus
    that until then contained none. Every run before that was green and wrong.

    This is DETECTION, not prevention, and it is worth having anyway: it fires
    on corrupted numbers whichever of the readers produced them, which is the
    property no per-reader fix has. Measured on its first pass over the eleven
    papers it found three things -- `NNT: 4.2` typed as a sample size, 298
    negative "counts" in a deposited spreadsheet, and a published Cohen's d of
    -0.79 whose own 95% CI is centred on +0.788.

    REPORTS, NEVER REWRITES, and never accuses: a violation says these numbers
    cannot all be right AS WE READ THEM, which is as likely to be our
    extraction as the paper's arithmetic. Deciding which is a human's job and
    the record carries the quote so they can.

    STRATIFIED, because the two populations mean different things. A violation
    among the paper's REPORTED values is either a finding or a parse error and
    someone should look. A violation in a DEPOSITED spreadsheet usually means
    our typer guessed a role for a raw data cell -- the 298 negative counts are
    change scores -- and no check is dispatched there anyway.
    """
    strata = {"reported": [], "deposited": []}
    for g in register.get("groups") or []:
        key = "deposited" if is_deposited_raw_data(g) else "reported"
        strata[key].append(g)

    out: dict = {}
    for stratum, groups in strata.items():
        counts: dict = {}
        examples: dict = {}
        n_eval = 0
        for g in groups:
            vals = {v.get("role"): v.get("value") for v in (g.get("values") or [])
                    if v.get("value") is not None}
            for name, evaluable, holds in _INVARIANTS:
                try:
                    if not evaluable(vals):
                        continue
                    n_eval += 1
                    if holds(vals):
                        continue
                except (TypeError, ValueError, OverflowError):
                    # NOT A PASS. A rule that raised could not be evaluated, and
                    # saying nothing about it is the failure this file is about.
                    counts["could_not_evaluate"] = counts.get("could_not_evaluate", 0) + 1
                    continue
                counts[name] = counts.get(name, 0) + 1
                shown = examples.setdefault(name, [])
                if len(shown) < _MAX_INVARIANT_EXAMPLES:
                    shown.append({"group_id": g.get("id"),
                                  "quote": (g.get("quote") or "")[:120],
                                  "row_label": g.get("row_label"),
                                  "values": vals})
        out[stratum] = {"n_groups": len(groups), "n_rules_evaluated": n_eval,
                        "n_violations": sum(counts.values()),
                        "by_rule": counts, "examples": examples}
    out["note"] = (
        "Arithmetic that must hold whatever the paper is about. A violation "
        "says these numbers cannot all be right AS WE READ THEM -- which is as "
        "likely to be our extraction as the paper's arithmetic, and deciding "
        "which is a human's job. Counts are exact; examples are capped. A rule "
        "that could not be evaluated is reported as such and is NOT a pass.")
    return out


def coverage(register: dict) -> dict:
    """What the register can say about its own completeness.

    FOUR STATES, KEPT APART. A value with no applicable tool, one that was
    checked, one that was refused with a reason, and one that is silent -- the
    last being a gap in this bookkeeping rather than a fact about the paper.
    Collapsing any pair of them is how a coverage number starts flattering.
    """
    tbl = [g for g in (register.get("groups") or [])
           if (g.get("anchor") or {}).get("where") == "table"]
    # ONE GROUP, ONE STATE, by precedence. `n_no_applicable_tool` used to be
    # counted regardless of the others, so an undeclared mean_sd cell -- no
    # applicable tools AND a refusal attached -- landed in two buckets and the
    # four states summed to 2 for 1 group. Any consumer computing a rate over
    # them double-counted.
    checked, refused, no_tool, silent = [], [], [], []
    for g in tbl:
        if g.get("checks"):
            checked.append(g)
        elif g.get("not_run"):
            refused.append(g)
        elif g.get("verdicts_not_attached"):
            # BEFORE the no-applicable-tool branch, on purpose. A verdict WAS
            # computed about a number printed in this cell -- we declined to say
            # which of several identical cells it belonged to. Reporting that as
            # "no applicable tool" states the opposite of what happened, and
            # states it about the one cell we know a tool did look at.
            silent.append(g)
        elif not g.get("applicable_tools"):
            no_tool.append(g)
        else:
            silent.append(g)
    # THE PAPER'S OWN VALUES, SEPARATED FROM THE RAW DATA IT DEPOSITED.
    # MEASURED 2026-08-20 over the nine registers: 16,256 of 19,085 values
    # (85.2%) are supplement spreadsheet cells -- participant row 2's
    # treatment-arm code, a per-subject score, a codebook legend. They are not
    # reported statistics and no check is expected to run on them, but they sat
    # in the same denominator, so CAPTAIN read "1 checked of 6,029" and ESCAS
    # "0 of 4,321". Those ratios are not a coverage story; they are a story
    # about how large a spreadsheet is.
    #
    # Separated rather than dropped. Raw data is exactly what
    # `detect_raw_duplication` consumes, so hiding it would trade one wrong
    # number for another. The distinction is the only thing that was missing --
    # and today it is recoverable ONLY by string-matching a `supp:` prefix on
    # the anchor, because `role_class` has no member for it.
    # WHY A VALUE IS SILENT, WHICH IS NOT ONE REASON BUT TWO. A silent group has
    # an applicable tool, no verdict and no recorded refusal, and the register's
    # own note calls that a gap in this bookkeeping. It is really two facts that
    # want different responses. MEASURED 2026-08-20 over the nine registers:
    # 125 of 141 were never checked -- a fact about the RUN, and the thing to
    # fix by dispatching more -- while 16 had a verdict computed that could not
    # be attached to one cell, because the same `32 (25.4)` is printed in three
    # rows. Reporting one number for both invites fixing the wrong one.
    unattached = [g for g in silent if g.get("verdicts_not_attached")]
    never = [g for g in silent if not g.get("verdicts_not_attached")]

    # WHY NO TOOL APPLIES, WHICH IS ALSO NOT ONE REASON BUT TWO. This bucket is
    # the largest in the register -- 864 of the 1,432 values the papers
    # themselves printed -- and "no applicable tool" reads as "nothing could
    # ever check this". For most of them that is false.
    #
    # MEASURED 2026-08-20 over the eleven papers: 242 are `mean_sd`, a shape
    # that GRIM, GRIMMER and SPRITE consume -- and `DISPATCH[("mean_sd",
    # "unknown")]` is EMPTY on purpose, because those checks are valid only on
    # integer-valued data and running them on a continuous variable manufactures
    # accusations. So the tool is not inapplicable; its precondition is
    # UNDECLARED. Nothing said what kind of variable this is.
    #
    # That distinction is the difference between "this value is unreachable"
    # and "declare the variable and it becomes checkable", which are opposite
    # instructions to whoever reads the coverage figure.
    # NO `try` AROUND THIS IMPORT. The first version wrapped it in a bare
    # `except Exception: return False`, and `lint-inert` flagged it inside the
    # hour: "an exception is discarded and nothing records that it happened, so
    # a caller cannot tell failure from a clean result". Every value would have
    # been reported unreachable if `dispatch` ever failed to import -- absence
    # rendered as knowledge, in the function written to stop exactly that. This
    # module already imports from `dispatch` at four other call sites; if that
    # import can fail, the register has larger problems and should say so.
    from .dispatch import DISPATCH

    def _checkable_once_declared(g) -> bool:
        kind = g.get("kind")
        return any(specs for (k, _t), specs in DISPATCH.items() if k == kind)

    undeclared = [g for g in no_tool if _checkable_once_declared(g)]
    unreachable = [g for g in no_tool if not _checkable_once_declared(g)]

    reported = [g for g in tbl if not is_deposited_raw_data(g)]
    raw = [g for g in tbl if is_deposited_raw_data(g)]
    rep_checked = [g for g in reported if g.get("checks")]

    return {
        "n_table_groups": len(tbl),
        "n_checked": len(checked),
        "n_refused_with_a_reason": len(refused),
        "n_no_applicable_tool": len(no_tool),
        "n_silent": len(silent),
        "no_applicable_tool_because": {
            "a check exists for this shape, but nothing declared the variable's "
            "type, and the check is only valid once it is": len(undeclared),
            "no check applies to this shape at all": len(unreachable),
        },
        "silent_because": {
            "no check was run on this value": len(never),
            "a verdict was computed and could not be attached to one cell":
                len(unattached),
        },
        # STRATIFIED, because one ratio over both populations is misleading in
        # the direction that flatters nobody: it makes a thorough run on a paper
        # with a big supplement look negligent.
        "reported": {
            "n_groups": len(reported),
            "n_checked": len(rep_checked),
            "coverage": (round(len(rep_checked) / len(reported), 4)
                         if reported else None),
        },
        "raw_data": {
            "n_groups": len(raw),
            "n_checked": sum(1 for g in raw if g.get("checks")),
            "note": ("deposited raw data, not statistics the paper reported. "
                     "`detect_raw_duplication` consumes these; the per-cell "
                     "checks are not expected to, and counting them in one "
                     "denominator with the reported values understates coverage "
                     "by however large the spreadsheet happens to be."),
        },
        "states_are_exclusive": (
            len(checked) + len(refused) + len(no_tool) + len(silent) == len(tbl)),
        "note": (
            "`n_silent` is a gap in THIS bookkeeping, not a fact about the "
            "paper: a group with an applicable tool, no verdict and no recorded "
            "refusal means a check neither ran nor said why. Any number above "
            "zero is a bug here, not a finding there."
        ),
    }


#: Which tool argument carries which role. A per-cell call names its numbers by
#: parameter, not by position, so this is the join key when the call cannot say
#: which cell it came from -- which is every per-cell call.
#: Roles the ROLED INDEX understands. Deliberately seven names and no aliases:
#: `present` is keyed by role, so adding `mean1` and `mean2` here would map both
#: to "mean" and one would silently overwrite the other.
_ARG_ROLES = {"mean": "mean", "sd": "sd", "se": "se", "percentage": "percentage",
              "count": "count", "estimate": "estimate", "median": "median"}

#: Arguments carrying a number the paper PRINTED IN THE CELL the group quotes.
#: The text fallback requires every one of these to appear in one group's quote,
#: so a name belongs here only if it is printed where the value is printed.
_PRINTED_ARGS = frozenset({
    "mean", "sd", "se", "median", "count", "percentage", "estimate",
    "reported_value", "reported_proportion", "reported_ratio", "reported_d",
    "effect_size", "statistic", "reported_t", "reported_f", "reported_chi2",
    "b", "ci_low", "ci_high", "numerator", "denominator", "n_reported",
})

#: Arguments carrying a real printed number that is NOT printed in the cell.
#: `n` is the biggest: `check_count_percent(count=42, percentage=33.6, n=125)`
#: is the most common call in the archive, and its `n` lives in the COLUMN
#: HEADER, not in the "42 (33.6)" cell. Requiring it inside the quote is what
#: took joins from 262 to 143 when this list was first written as one flat
#: whitelist. These narrow an otherwise ambiguous match; they never gate one.
_CORROBORATING_ARGS = frozenset({
    "n", "n1", "n2", "actual_n", "df", "df1", "df2", "reported_p",
})

#: EVERYTHING ELSE IS IGNORED, and the whitelist is the point: `decimals`,
#: `alpha`, `tails`, `power`, `null_value`, `scale_min`, `scale_max`,
#: `variable_range_*`, `plausible_sd_max`, `num_samples`, `n_min`, `n_max`,
#: `first_page`, `table_num` are parameters and bounds, not results. A new tool
#: argument is ignored rather than wrongly required -- it fails closed, which
#: costs a join it might have made and never invents one.


def _appears_in(number: Any, text: Any) -> bool:
    """Is this number printed in that cell, in ANY of its printed forms?

    Delegates to `quotes`, which already solved this: a tool call carries the
    float `0.52` while psychology prints `.52`, and `12345` is printed
    `12,345`. Matching the repr alone joined 1 of 58 real calls, and the one it
    joined was matched on a different argument.

    `_contains_bounded`, not `in`: `6.58` must not match inside `16.583`. That
    rule exists in `quotes` because "n = 42" once verified against a paper
    printing only "n = 428".
    """
    if not text:
        return False
    from .quotes import _contains_bounded, _number_forms
    return any(form and _contains_bounded(form, str(text))
               for form in _number_forms(str(number)))


#: Names that are not a check FOR THE VALUE JOIN: they fetch text, read a file,
#: parse a grid, or emit structure. None computed a verdict about a number, so
#: none can be joined to one.
#:
#: DERIVED from `registry.NOT_A_TECHNIQUE` rather than hand-copied, with exactly
#: two adjustments, both stated:
#:
#:   - `Read` and `StructuredOutput` are added. They are not registered tools,
#:     so the registry cannot know about them.
#:   - `check_table` is REMOVED, because the two lists answer different
#:     questions. The registry's asks "can a FINDING name this as the technique
#:     that produced it?" -- `check_table` cannot, being a batch runner, and a
#:     finding names the specific check that fired inside it. This one asks "did
#:     this CALL compute a verdict about a number?" -- `check_table` did, and
#:     its verdicts are attached by a different path.
#:
#: Merging the two outright would drop every `check_table` call out of the
#: conservation law's denominator while its joined and unmatched counts stayed
#: in the sum: a NEGATIVE residual, the law reporting that two counters describe
#: one call when really one end had stopped counting. Same lesson as
#: `computation._NUMBER` -- two lists that look alike are not always one list.
#:
#: ONE TUPLE, READ BY BOTH WALKERS. `call_ledger_balance` used its own copy of
#: this list and read it off `call["name"]`, while the join read
#: `call["tool"] or call["name"]`. MEASURED 2026-08-20: all 819 calls in the
#: nine real runs carry `tool` and NONE carries `name`, so on raw ledger data
#: the balance's filter matched nothing at all while the join's matched
#: everything -- the two ends of one conservation law disagreeing about what
#: they were counting. That is the seam this file exists to close.
@lru_cache(maxsize=1)
def _not_a_check() -> frozenset:
    from .registry import NOT_A_TECHNIQUE
    return (NOT_A_TECHNIQUE - {"check_table"}) | {"Read", "StructuredOutput"}


def is_check_call(call: dict) -> bool:
    """Did this call compute a verdict about a value, or just fetch something?"""
    name = str(call.get("tool") or call.get("name") or "").split("__")[-1]
    return name not in _not_a_check()


def _stated_n(label) -> dict | None:
    """The sample size a column header states, and WHICH LEVEL of it said so.

    `Placebo (N = 540)` and `Cerebrolysin , n = 16` both say what they divided
    by. A stacked header says it twice at different scopes, and THE INNERMOST
    LEVEL GOVERNS THE CELL -- see `dispatch.header_ns`, which does the reading.

    MEASURED, and the difference is not cosmetic. Auditing every count/percent
    cell in the nine registers whose header states an n, reading the OUTERMOST
    level gave 86 reproduced exactly and 72 needing a smaller denominator at a
    median gap of 126 -- which reads like a fabricated table. Reading the
    INNERMOST gives 149 reproduced exactly and 9 at a median gap of 1, the
    ordinary signature of a variable with a missing measurement. Same cells,
    same arithmetic, opposite impression.

    ONE PARSER, IN `dispatch`. This function used to carry its own regex, which
    was a weaker copy: `dispatch._N_IN_LABEL` also reads `n \u00bc 59`, the OCR
    corruption of `n = 59` that a real extractor produces. Two spellings of one
    question is the defect this file keeps finding in other people's code.

    Returns the LEVEL as well as the number because they carry different
    weight. `level="column"` is the denominator for these numbers.
    `level="group"` -- what a p-value column falls back to, having no n of its
    own -- covers several columns, so a consumer can decline to lean on it.
    Returns None when no level states an n; a header that says nothing is not
    evidence of anything.
    """
    from .dispatch import header_ns
    found = header_ns(label)
    return found[0] if found else None


#: The one spelling of "this table came out of a supplementary file".
#: `supplement_anchor` writes it and `is_deposited_raw_data` reads it; a test
#: pins the round trip so the pair cannot drift apart the way the conservation
#: law and the join did earlier today.
SUPPLEMENT_ANCHOR_PREFIX = "supp:"


def supplement_anchor(supplement_file: str | None, label: str) -> str:
    """The anchor name for a table read out of a supplementary file."""
    return f"{SUPPLEMENT_ANCHOR_PREFIX}{supplement_file or '?'}:{label}"


def is_deposited_raw_data(group: dict) -> bool:
    """Is this value a cell of a deposited dataset rather than a reported statistic?

    ONE DEFINITION, read by `coverage` and by the join. `coverage` had this
    nested inside itself, which is how the balance and the join came to disagree
    about what a check call is earlier today -- two copies of a predicate drift,
    and nothing tells you when they have.

    WHY THIS IS NOT A `role_class`. A `role_class` is a property of the ROLE: a
    mean is descriptive wherever it is printed, and a deposited mean is still a
    mean. Where a value came from is PROVENANCE, and folding provenance into the
    role vocabulary would make "descriptive" and "deposited" alternatives when
    they are independent facts.

    WHAT IT DOES NOT DISTINGUISH, stated because the limit is real. A formatted
    supplementary TABLE of statistics carries the same prefix as a spreadsheet
    of per-subject rows, and this one-line test cannot tell them apart.

    THIS DOCSTRING PREVIOUSLY CLAIMED, as a measurement, that the corpus held
    "NOT ONE formatted supplementary statistics table", and concluded that no
    negative example existed to validate a classifier against. THAT CLAIM WAS
    FALSIFIED 2026-08-20 by a fix elsewhere. The tables were always there; they
    were invisible because `supplements_read._finish` read every .docx with a
    ONE-ROW header, so a stacked-header regression table surfaced with six of
    seven columns unlabelled and looked exactly like an unstructured cell dump.
    Repairing that header produced the negative examples the claim denied.

    RE-MEASURED 2026-08-20 over the rebuilt eleven-paper registers: 2,421 of
    4,944 groups (49%) are classified deposited raw data, spanning 37 tables in
    3 papers, and they are `b (SE) | p | beta` multilevel SEM tables, `CFI /
    TLI / RMSEA / SRMR` fit indices, `ARR / IPW ARR / Asy. p-val`, and
    `Weighted % (95% CI)`. Only 15 groups carry the bare-integer row label that
    is this docstring's own signature for a deposit, and the corpus contains no
    .xlsx or .csv at all -- the per-subject files described in the old text came
    from a different corpus and were carried across.

    The behaviour is UNCHANGED pending a methods decision, because the error is
    not symmetric. Calling a statistics table "raw data" loses checking and
    FLATTERS coverage: bad, visible, not accusatory. Calling a per-subject
    deposit "reported statistics" would run per-cell checks against individual
    observations -- GRIM against one participant's score -- which is how a false
    accusation gets manufactured. So a classifier may promote raw -> reported
    only on POSITIVE PROOF (column headings naming statistical quantities),
    never by default, and the switch moves every coverage number the project
    publishes. See `FMT-register-remeasured_2026-08-20.md`.

    That asymmetry is also why the join PREFERS reported cells rather than
    DISCARDING these: preferring costs nothing when the guess would be wrong,
    and discarding would lose a real join to a supplementary table.
    """
    t = str(((group.get("anchor") or {}).get("table")) or "")
    # The second form is the slugged spelling: `_slug` turns the `:` into `-`,
    # so an anchor that has been through it reads `supp-file-...`.
    return t.startswith(SUPPLEMENT_ANCHOR_PREFIX) or "supp-" in t


def _prefer_reported(found: list) -> list:
    """Drop deposited-data cells from a contested match when reported ones remain.

    MEASURED 2026-08-20: 37 of 209 groups stamped "a verdict was computed about
    this and could not be attached" were spreadsheet cells that merely held the
    same integer as a reported statistic. A per-subject data cell is not what a
    `grim` or `count_percent` verdict is about, so when a real reported cell is
    among the candidates the data cells are not rivals for it.

    If EVERY candidate is deposited data the list is returned untouched -- a
    check genuinely aimed at a supplementary table still joins to it. Measured
    effect on the nine registers: joined 298 -> 300, ambiguous 129 -> 127, and
    NOTHING lost, because zero verdicts were attached to a data cell to begin
    with.
    """
    if len(found) < 2:
        return found
    reported = [g for g in found if not is_deposited_raw_data(g)]
    return reported or found


def _round_half_up(x: float, decimals: int) -> float:
    """Round the way a paper rounds, not the way Python does.

    `round(31.25, 1)` is **31.2** in Python: bankers' rounding, half to even.
    Journals round half UP, so 31.25 prints as 31.3. Using the built-in here
    would make the toolkit disagree with a correctly rounded number once every
    ten values whose next digit is a 5 -- and disagreeing with a correct number
    is how a false accusation starts.
    """
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(1).scaleb(-decimals)
    return float(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))


def explaining_denominator(count, percentage, n, decimals=None):
    """The largest denominator at most `n` that reproduces the printed percentage.

    WHY THIS EXISTS, measured 2026-08-20 on the eleven-paper run. Ten cells were
    flagged `suspicious` by `check_count_percent` or `grim_percentage`. NINE had
    an implied denominator BELOW the `n` the check used, and eight of those
    within 5% of it -- the exact signature of a baseline table where each
    variable has its own denominator because some participants are missing that
    measurement. One case is unambiguous: the column header reads `n = 16`, the
    check used 17, and 5/16 = 31.3 is precisely what the paper printed.

    So most of a run's count/percent flags were not errors in the paper. They
    were the wrong denominator, and they are the cardinal failure -- a false
    accusation against an honest paper -- arriving at scale and in the one
    check that fires most often.

    HOW STRONG IS AN EXPLANATION? MEASURED AGAINST ARBITRARY VALUES, because a
    search that sweeps every denominator at or below `n` will sometimes land on
    one by luck, and an explanation that arrives by luck exonerates nothing.
    1,500 random percentages per sample size, asking how often ANY denominator
    reproduces one, and how often one within `k` of `n` does:

        n        k<=1     k<=3    k<=10       any
        17       0.3%     0.5%     1.0%      1.1%
        104      0.1%     0.2%     0.5%      4.9%
        201      0.1%     0.3%     0.6%      8.3%
        540      0.3%     0.4%     0.9%     22.4%

    THE GAP IS THE WHOLE STATISTIC. Unconstrained, the rate rises with `n` --
    a bigger sample offers more denominators to sweep -- until at n = 540 more
    than a QUARTER of arbitrary values find an "explanation". Constrained to a
    handful of observations it collapses below 1% at every sample size, because
    only a few denominators sit that close and each reproduces only a narrow
    band of percentages.

    So `n_missing` is not a footnote to the verdict, it IS the evidence. A
    denominator one or two below `n` is a participant missing a measurement and
    the reading is near-conclusive. A denominator 60% below is something else --
    on the one paper where it happens it is a STACKED HEADER stating a study
    total of 318 over cells belonging to arms of 201 and 117, which sum to it
    exactly -- and it is innocent too, but for a different reason and on much
    weaker arithmetic evidence. Report both numbers and let the reader see
    which case they are in. "Explained" must never be read as "exonerated".

    NO TOLERANCE, AND NOTHING SUPPRESSED. A threshold ("within 5% is fine")
    would be a number I chose, and it would silently forgive a real error just
    below it. Instead this searches for a denominator that reproduces the
    printed value EXACTLY, and reports it with how many observations would have
    to be missing. `332/539 = 61.6` is checkable by the reader; "within
    tolerance" is not. The verdict is annotated, never overturned: whether one
    missing observation is plausible is a judgement about the paper, and this
    file does not make those.
    """
    try:
        count, percentage, n = float(count), float(percentage), int(n)
    except (TypeError, ValueError):
        return None
    if n <= 0 or count < 0 or count > n:
        return None
    if decimals is None:
        text = repr(percentage)
        decimals = len(text.split(".")[1]) if "." in text else 0
    decimals = max(0, min(int(decimals), 6))
    for d in range(n, max(int(count), 1) - 1, -1):
        if _round_half_up(100.0 * count / d, decimals) == round(percentage, decimals):
            return {"denominator": d, "n_used": n, "n_missing": n - d,
                    # HOW FAR BELOW, AS A SHARE, BECAUSE THE ABSOLUTE NUMBER
                    # CONFLATES TWO DIFFERENT EXPLANATIONS. `n_missing = 1`
                    # against 540 is one participant missing a measurement.
                    # `n_missing = 201` against 318 is not 201 missing people:
                    # it is a STACKED HEADER stating a study total over a cell
                    # that belongs to one arm -- and 201 + 117 = 318 exactly.
                    # Both are real, both are innocent, and they are not the
                    # same fact. A reader given only the absolute number cannot
                    # tell them apart, and the second reads alarming.
                    "share_below": round((n - d) / n, 4),
                    "reproduces_printed_value": True}
    return {"denominator": None, "n_used": n, "n_missing": None,
            "share_below": None, "reproduces_printed_value": False}


def _printed_arguments(args: dict) -> tuple[list[str], list[str]]:
    """Split a call's numeric arguments into what must be in the cell and what need not.

    Returns printed forms, not floats, because that is what the quote is
    searched for. `bool` is excluded explicitly: `True` is an `int` in Python
    and would be searched for as the number 1.
    """
    required, corroborating = [], []
    for name, value in args.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if name in _PRINTED_ARGS:
            required.append(f"{float(value):g}")
        elif name in _CORROBORATING_ARGS:
            corroborating.append(f"{float(value):g}")
    return required, corroborating


def _two_sample_sides(args: dict) -> list[list[list[str]]]:
    """The per-arm number tiers of a two-sample call, or [] if it is not one.

    A name counts as an arm's only if stripping its trailing 1 or 2 leaves a
    name we already recognise, so `n1` is arm one's N while `ci_low` and
    `df1`-with-no-`df2` are left alone. BOTH arms must be present -- a call
    carrying only `mean1` is a one-armed call with an odd name, not half of a
    comparison, and treating it as half would attach a verdict to a cell that
    was never paired with anything.
    """
    sides = []
    for suffix in ("1", "2"):
        req, cor = [], []
        for name, value in args.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            if not name.endswith(suffix):
                continue
            stem = name[:-1]
            if stem in _PRINTED_ARGS:
                req.append(f"{float(value):g}")
            elif stem in _CORROBORATING_ARGS:
                cor.append(f"{float(value):g}")
        if not req:
            return []
        sides.append([req + cor, req])
    return sides


def _unique_group(groups: list, tiers: list[list[str]]) -> tuple[dict | None, bool]:
    """The one group whose quote holds these numbers, trying each tier in turn.

    Returns `(None, True, contenders)` when a tier matched SEVERAL groups and
    none matched exactly one. `contenders` is who they were: a value that a
    verdict was computed about, and could not be attached to, is not the same
    as a value nobody checked, and only the join knows the difference. Ambiguity is not resolved by picking: where two cells carry the
    same numbers -- ordinary when a table repeats a value -- attaching the
    verdict to the wrong one of them is the same false accusation the row-label
    join already produced once.
    """
    contested, contenders = False, []
    for wanted in tiers:
        if not wanted:
            continue
        found = _prefer_reported(
            [g for g in groups
             if all(_appears_in(n, g.get("quote")) for n in wanted)])
        if len(found) == 1:
            return found[0], False, []
        if len(found) > 1:
            contested = True
            # The NARROWEST contested tier, because tiers run narrow-to-wide
            # and the first one to match several is the tightest description of
            # what this verdict could be about.
            contenders = contenders or found
    return None, contested, contenders


def attach_calls_by_value(register: dict, calls: list[dict] | None) -> dict:
    """Join per-cell checks onto the values they consumed, by argument value.

    THE MODEL DOES NOT USE `check_table`. Measured on a real run of
    10.1007--s11031-011-9216-y: 41 tool calls, 0 of them `check_table` and 0
    carrying a `variable_id`, which matches the 1:13.8 ratio across the whole
    archive. A register that only joins `check_table` therefore shows a paper's
    every check as absent, which is worse than showing nothing -- it is the
    absence-as-knowledge failure wearing a coverage number.

    So the join is on the NUMBERS. A `grimmer_check(mean=6.58, sd=0.52)` belongs
    to the value group whose mean is 6.58 and whose sd is 0.52. Matched on the
    parsed values rather than the printed literals, because the call carries
    floats and the group carries what the paper printed.

    A MATCH MUST BE UNIQUE. Where two groups carry the same numbers -- ordinary
    when a table repeats a value -- the call is left unjoined and counted, since
    attaching a verdict to the wrong one of two identical cells is the same
    false accusation the row-label join already produced once.
    """
    index: dict[tuple, list[dict]] = {}
    for g in register.get("groups") or []:
        by_role = {v.get("role"): v.get("value") for v in (g.get("values") or [])}
        for roles in (("mean", "sd"), ("mean", "se"), ("count", "percentage"),
                      ("estimate",), ("mean",), ("median",)):
            key = tuple(by_role.get(r) for r in roles)
            if all(k is not None for k in key):
                index.setdefault((roles, key), []).append(g)

    joined = unmatched = ambiguous = nothing_to_join = two_sided = 0
    non_check = 0
    groups = register.get("groups") or []
    for call in calls or []:
        args = call.get("input") or call.get("args") or {}
        if not isinstance(args, dict):
            continue
        present = {role: args.get(arg) for arg, role in _ARG_ROLES.items()
                   if isinstance(args.get(arg), (int, float))}
        required, corroborating = _printed_arguments(args)
        sides = _two_sample_sides(args)
        if not is_check_call(call):
            # NOT A CHECK AT ALL, so not a failed join and not a check that had
            # nothing to join. `extract_pdf`, `get_table`, `Read` and
            # `StructuredOutput` fetch text and emit structure. Filed with the
            # checks, they were 96 of the 239 calls in a bucket whose name
            # promises a check that found no value.
            non_check += 1
            continue
        if not (present or required or corroborating or sides):
            # NOT A FAILED JOIN. `extract_xml`, `Read`, `StructuredOutput`,
            # `grim_sweep` (which sweeps hypothetical Ns) and `rivets_anova`
            # (which takes lists) carry no printed value to match, so there is
            # nothing here that could have joined. Counting them as unmatched
            # put 34 of a run's 58 calls into a bucket labelled failure -- an
            # absence and an unasked question spelled identically, which is the
            # defect this file exists to avoid committing.
            #
            # WHAT IS LEFT HERE AFTER THE SPLIT ABOVE IS REAL: `statcheck`,
            # `multiplicity_report`, `check_summation_batch`, `grim_sweep` and
            # `bayesian_table1_dispersion` are genuine checks whose arguments
            # are a table, a list or a range rather than the numbers they read,
            # so no scalar exists to match. They are a limit of joining BY
            # VALUE, and naming them is how that limit stays visible.
            nothing_to_join += 1
            continue
        hits: list[dict] = []
        contested = False
        contenders: list[dict] = []
        for roles in (("mean", "sd"), ("mean", "se"), ("count", "percentage"),
                      ("estimate",), ("mean",), ("median",)):
            if not all(r in present for r in roles):
                continue
            found = _prefer_reported(
                index.get((roles, tuple(float(present[r]) for r in roles))) or [])
            if found and len(found) == 1:
                hits = [found[0]]
                break
            if found:
                contested = True
                contenders = found
                break
        if not hits and sides:
            # A TWO-SAMPLE CHECK BELONGS TO BOTH CELLS IT READ.
            # `check_effect_plausibility(mean1=6.6, sd1=.5, n1=50, mean2=5.9,
            # sd2=.6, n2=48)` reads one cell per arm, so no single cell holds
            # all six numbers and the one-quote rule can never match it. 24
            # calls in the archive carry a 1/2 pair. Matching each side on its
            # own numbers and attaching the verdict to both is not a guess: the
            # check really did read both cells, and showing it on either alone
            # would hide half of what it looked at.
            per_side = [_unique_group(groups, tiers) for tiers in sides]
            if all(g is not None for g, _, _ in per_side):
                hits = [g for g, _, _ in per_side]
                two_sided += 1
            elif any(amb for _, amb, _ in per_side):
                contested = True
                contenders = [g for _, _, cs in per_side for g in cs]
        if not hits:
            # FALL BACK TO THE PRINTED TEXT, NARROWEST SET FIRST. A roled match
            # needs the cell to have been TYPED, which needs a declared
            # variable -- and on a real run nothing was declared, so every table
            # cell stayed `ambiguous` with one `unknown` value and 57 of 58
            # calls matched nothing. The numbers are still in the cell's text
            # whether or not anyone typed it.
            #
            # Each tier requires FEWER numbers than the last, so the candidate
            # sets nest: narrowing can only ever turn many into one or none,
            # and widening can only ever turn none into some. Trying the most
            # specific first therefore picks the tightest set that lands on a
            # single cell, and the last tier reproduces the old behaviour
            # exactly, so no join this code used to make can be lost.
            tiers = ([required + corroborating, required] if required
                     else [corroborating])
            tiers.append([f"{float(v):g}" for v in present.values()])
            hit, also_contested, more = _unique_group(groups, tiers)
            if hit is not None:
                hits = [hit]
            contenders = contenders or more
            # `or`, NOT `=`. A contested ROLED match still gets the text tiers,
            # because they can require MORE numbers and so land on one cell
            # where the roled pair could not. But if they also fail, the earlier
            # ambiguity is still the true reason, and overwriting it here would
            # report a cell that could not be found rather than one that could
            # not be told apart from its neighbour.
            contested = contested or also_contested
        if contested and not hits:
            ambiguous += 1
            # STAMP WHO IT COULD HAVE BEEN. Without this the group shows as
            # SILENT -- no check, no reason -- which says nobody looked at this
            # value. Somebody did: a verdict was computed about a number
            # printed here, and we refused to say which of several identical
            # cells it belonged to. MEASURED over the nine registers: 16 of the
            # 141 silent groups are this, and `32 (25.4)` is printed in three
            # different rows of one paper.
            for g in contenders:
                g["verdicts_not_attached"] = g.get("verdicts_not_attached", 0) + 1
            continue
        if not hits:
            unmatched += 1
            continue
        # A RESULT THAT IS NOT A DICT IS UNKNOWN, NOT FAILED. Raw
        # `toolcalls.*.json` stores some results as a bare string, and
        # `(call.get("result") or {}).get(...)` raised AttributeError on the
        # first one -- which does not lose one check, it aborts the whole join
        # and leaves every value in the paper showing no checks at all.
        # `passed` is None rather than False for the same reason: a severity we
        # could not read is not a check that failed, and the viewer already
        # renders an unknown severity as "--".
        result = call.get("result")
        severity = result.get("severity") if isinstance(result, dict) else None
        # THE REGISTER ANNOTATES; IT DOES NOT OVERTURN.
        #
        # A near miss recorded here keeps the severity the CHECK returned, and
        # gets the denominator audit beside it. `check_stated_denominators`
        # records the same shape as `indeterminate`, and the difference is not
        # an inconsistency -- it is AUTHORSHIP. There the register chose the
        # denominator itself, so a near miss is its own pairing error and
        # declining to accuse is its own verdict to make. Here a model computed
        # the verdict, and re-grading someone else's conclusion from evidence
        # they did not have is exactly the judgement this file refuses to make
        # on a paper's behalf.
        #
        # I wrote the downgrade into this path and reverted it: a test written
        # hours earlier -- `nothing is suppressed, only annotated` -- had
        # already settled the question, and the reader is not misled either way
        # because the viewer prints the audit inline beside the severity.
        # WHICH DENOMINATOR WOULD MAKE THE PRINTED NUMBER RIGHT. Recorded on
        # the attachment because this is the only place that holds the call's
        # arguments and the cell together. See `explaining_denominator`.
        denom = None
        if all(k in args for k in ("count", "percentage", "n")):
            denom = explaining_denominator(
                args.get("count"), args.get("percentage"), args.get("n"),
                args.get("decimals"))
        for hit in hits:
            record = {
                "check_id": call.get("id") or call.get("tool_use_id"),
                "tool": str(call.get("tool") or call.get("name") or "").split("__")[-1],
                "severity": severity,
                "passed": (severity == "consistent") if severity is not None else None,
                "joined_by": ("argument values, both arms" if len(hits) > 1
                              else "argument values"),
            }
            if denom is not None:
                audit = dict(denom)
                # THE COLUMN HEADER OFTEN STATES THE DENOMINATOR. When the
                # header's own n is the one that reproduces the printed value
                # and the check used a different one, there is nothing left to
                # judge: the paper said what it divided by, and we divided by
                # something else. That is the whole of the verbatim false
                # positive from the run -- header `n = 16`, check given 17,
                # 5/16 = 31.3 as printed.
                stated = _stated_n((hit.get("anchor") or {}).get("col_label"))
                if stated is not None:
                    audit["column_header_states_n"] = stated["n"]
                    audit["column_header_states_n_at"] = stated["level"]
                    audit["header_confirms_denominator"] = (
                        stated["n"] == audit.get("denominator"))
                record["denominator_audit"] = audit
            hit.setdefault("checks", []).append(record)
        joined += 1
    register["n_per_cell_checks_joined"] = joined
    # Had a value to join on and did not find its cell. THIS is the gap number.
    register["n_per_cell_checks_unmatched"] = unmatched
    # Carried nothing joinable. Not a gap; recorded so the denominator is real.
    register["n_calls_with_no_matchable_value"] = nothing_to_join
    # Of the joined, how many were attached to two cells rather than one.
    register["n_checks_attached_to_two_groups"] = two_sided
    # Never a check. Excluded from the ledger's denominator, not from the sum.
    register["n_non_check_calls"] = non_check
    register["n_per_cell_checks_ambiguous"] = ambiguous
    return register


def dedupe_checks(register: dict) -> dict:
    """Collapse repeated identical checks on ONE value group.

    Measured across the archive: 37 of 745 findings sit in a duplicate group
    (5.0%), 25 of them redundant copies, and one run repeated 9 of its 25.

    DEDUP BELONGS AT THE VALUE LAYER and nowhere else. Identical arguments
    arising from DIFFERENT printed values are two real checks of two real
    numbers; identical arguments arising from the SAME value are one check run
    twice. Only a register that knows which value a check came from can tell
    those apart, which is why deduplicating on the arguments alone -- the
    obvious place -- would delete real findings.
    """
    removed = 0
    for g in register.get("groups") or []:
        seen: set[tuple] = set()
        keep: list[dict] = []
        for c in g.get("checks") or []:
            # `check_id` FIRST. Keying on (tool, severity, passed) alone
            # collapses two REAL verdicts that happen to agree -- which is
            # exactly what a join bug would produce, so the dedup would have
            # hidden the evidence of the bug. A check_id is unique per check the
            # dispatcher ran, so repeating one is the only true duplicate.
            key = c.get("check_id") or (c.get("tool"), c.get("severity"),
                                        c.get("passed"))
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            keep.append(c)
        g["checks"] = keep
    register["n_duplicate_checks_removed"] = removed
    return register


#: Words carried by a row label that say nothing about WHICH variable it is.
#: Deliberately tiny: a stoplist is a place to hide a guess, and every word here
#: is a function word, not a domain term.
_BINDING_STOPWORDS = frozenset({
    "the", "of", "a", "an", "and", "in", "at", "to", "for", "by",
    "is", "are", "was", "were", "with", "on", "or",
})

#: Format markers a paper appends to a row label to say how the cell is
#: printed -- `(n, %)`, `(mean, SD)`, `(median, IQR)`. They describe the CELL,
#: never the variable, so they must not participate in identifying it. Stripped
#: rather than stoplisted, because `n` and `%` are meaningful elsewhere.
_FORMAT_SUFFIX = re.compile(
    r"\((?:\s*(?:n|N|%|mean|median|M|SD|SE|IQR|CI|range|95%\s*CI)\s*[,;/]?\s*)+\)",
    re.I)


def _contains_word(haystack: str, needle: str) -> bool:
    """Is `needle` in `haystack` as WHOLE WORDS, not as a run of characters?

    A bare `in` test binds a row to a variable it shares no word with. MEASURED
    live on the corpus: the row stub `No` matched `Number of comorbid CVD
    diagnoses` -- the `N` and the `o` of "Number of" -- and bound five
    medication rows to a `count` variable; the stub `Other` matched
    `mother-daughter intergenerational closeness`. Six wrong bindings of 112 on
    eight papers, from this one operator.

    `anatomy.py` fixed exactly this class in its assumption matcher and says
    why in the same words ("Word-bounded, not `in`: a bare substring test lets
    a short key like 'icc' match inside an unrelated word"). The binder never
    got the fix; this is that fix, in the second place it was needed.

    The boundary is the same one -- alphanumeric neighbours block a match,
    punctuation and space do not -- so `EBP adherence` still matches inside
    `EBP fidelity (also printed as 'EBP adherence' in Table 1)`.
    """
    if not needle or not haystack:
        return False
    return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])",
                     haystack) is not None


def _content_tokens(text: Any) -> frozenset:
    """The words in a label that could identify a variable, normalised.

    NFKC first, because a publisher's U+2011 NON-BREAKING HYPHEN and an ASCII
    `-` are the same word to a reader and different bytes to a matcher -- one
    of the measured causes of unbound rows on this corpus. Format markers are
    stripped, digits survive as tokens but cannot carry a match on their own
    (see `binding_candidates`), and the stoplist is function words only.
    """
    import unicodedata
    s = unicodedata.normalize("NFKC", str(text or "")).lower()
    s = s.replace("\u2010", "-").replace("\u2011", "-").replace("\u2212", "-")
    s = _FORMAT_SUFFIX.sub(" ", s)
    return frozenset(
        w for w in re.split(r"[^a-z0-9]+", s)
        if w and w not in _BINDING_STOPWORDS)


def binding_candidates(row_labels: Any, variables: Any) -> list[dict]:
    """For each unbound row, which declared variables it COULD be, and why.

    NOT A MATCHER. Automatic binding was tried and is wrong here, and the paper
    that showed it is the fraud ground-truth one: its table row `Self-evaluation`
    matches two declared variables --

        Self-evaluation (own attractiveness, single item)          likert_item
        Self-evaluation index, pilot study (mean of three ...)     likert_composite

    -- and those differ in the one property that decides whether GRIM may run at
    all. A composite scored as a mean has granularity 1/(k*n), not 1/n, and
    binding this row to the wrong one is the documented way to manufacture an
    impossibility out of a correctly reported number. `Similarity` is ambiguous
    the same way, against `Perceived similarity index` and `Similarity cue`.

    Exact-name binding matched 0 of 157 values on that paper, and a containment
    rule would also match 0 -- but for a better reason: the labels really are
    ambiguous, and the ambiguity is the finding. So this reports the candidates
    and refuses to choose. A guessed binding is a guessed variable family, and a
    guessed family is a guessed verdict.

    THE MATCH IS AGAINST THE INNERMOST FOLD SEGMENT, NEVER THE WHOLE LABEL, and
    that one word is the difference between a coverage number and a false
    accusation. `fold_section_bands` writes a row-section band into the label as
    `Band | Stub`, so a containment rule reading the whole string matches the
    BAND'S variable name and hands it to a row that is about something else.

    MEASURED on 10.1002--ajcp.70049: three of thirteen auto-bindings were wrong,
    all three by this mechanism --

        "Level of technical assistance received | Number of coalition members"
                                                 -> v_ta      (true: v_members)
        "State | Communities That Care (n, %)"   -> v_state    (true: v_ctc)
        "State | Externally funded (n, %)"       -> v_state    (true: v_funded)

    -- and the first is not cosmetic. That row is mean 35.78, SD 33.74, n = 64
    coalition MEMBERS. v_ta is `ordinal_category` with declared bounds 0-3, so
    the mis-binding MANUFACTURED a scale ceiling for a variable whose bounds the
    paper never stated, and `dispatch._drop_unbounded` then admitted the two
    bounded checks that the true binding refuses. Run:

        sprite_reconstruct(mean=35.78, sd=33.74, n=64, scale_min=0, scale_max=3)
        -> impossible

    An honest paper, a correctly reported mean. The only thing between it and a
    published accusation was that the model happened to call `grim_check`, which
    passed for the wrong reason (v_members is also discrete).

    FALLING BACK TO THE BAND WHEN THE SEGMENT MATCHES NOTHING WAS CONSIDERED AND
    REJECTED. It looks safe and reintroduces the bug exactly: on this paper the
    declared names are `Follows the Communities That Care model` and `Number of
    active coalition members`, so the innermost segments match nothing and the
    fallback would rebind all three to the band.

    WHAT THIS COSTS, STATED. Five correct bindings go with the three wrong ones
    -- `State | Missouri`, `State | Pennsylvania`, and the three
    `Level of technical assistance received | {None, 1, 2 or 3}` rows, where the
    band really IS the variable and the children really are its levels. The rule
    cannot tell that case from the failing one, because the difference is not in
    the strings: it is whether the children are exhaustive LEVELS of the band
    variable or separate variables under a topic. The register has no
    representation for a level, so this relationship is one we cannot currently
    express -- and losing it is the correct direction until we can. Coverage is
    recoverable; a manufactured family is not.

    The band is still REPORTED on each row (`band_candidates`) so the loss is
    visible rather than silent, and so a model-declared binding -- which reads
    the paper and can tell a level from a variable -- has something to reconcile
    against.
    """
    from .dispatch import HEADER_LEVEL_SEP

    out: list[dict] = []
    vs = [v for v in (variables or []) if isinstance(v, dict) and v.get("id")]

    def _match(text: str) -> list[dict]:
        low = text.strip().lower()
        toks = _content_tokens(text)
        # A LABEL WITH NO WORD IN IT MAY NOT MATCH BY STRING AT ALL. `1`,
        # `2 or 3` and `<= 5` are LEVEL names, not variable names, and a bare
        # numeral is a substring of half the prose in a corpus. MEASURED: the
        # model wrote the variable name "EBP fidelity (also printed as 'EBP
        # adherence' in Table 1)" -- a parenthetical NOTE in an identifier
        # field -- so the row label `1` matched it, because "1" occurs in
        # "Table 1". Both the containment rule and the token rule below
        # inherit that, because the defect is in the KEY, not the matcher.
        # Currently inert (the row is `n_percent`, and the cell-kind gate
        # admits only grim_percentage/check_count_percent regardless of the
        # binding) -- but it is one mean_sd row away from admitting the
        # bounded-scale checks, which is the documented route to a false
        # `impossible`.
        if not any(c.isalpha() for c in "".join(toks)):
            return []
        found = []
        for v in vs:
            name = str(v.get("name") or "")
            nl = name.lower()
            if nl == low:
                why = "the names are identical"
            elif low and _contains_word(nl, low):
                why = "the variable's name contains this row label"
            elif nl and _contains_word(low, nl):
                why = "this row label contains the variable's name"
            elif toks and toks <= _content_tokens(name):
                # EVERY CONTENT WORD OF THE ROW LABEL APPEARS IN THE VARIABLE
                # NAME. Substring containment fails whenever the declared name
                # WRAPS the row label with words on both sides, which is the
                # ordinary way a paper names things: the row `Communities That
                # Care (n, %)` against `Follows the Communities That Care
                # model`, or `Number of coalition members (mean, SD)` against
                # `Number of active coalition members`.
                #
                # MEASURED against a hand-made ground truth for the 16 Table 1
                # rows of 10.1002--ajcp.70049: containment alone scores 3
                # correct / 1 wrong / 12 missed; adding this rule scores 9
                # correct / 1 wrong / 6 missed; adding the no-bare-numeral
                # guard above takes the wrong one to 0. Same safety, three
                # times the coverage.
                #
                # ONE DIRECTION ONLY, deliberately. `row ⊆ variable` says the
                # row names part of the variable. The converse -- `variable ⊆
                # row` -- would let a short declared name match any row that
                # mentions it, and short names are exactly the ones that
                # collide.
                why = "every word of this row label appears in the variable's name"
            else:
                continue
            found.append({"variable_id": v.get("id"), "name": name,
                          "family": v.get("family"), "why": why})
        return found

    for label in sorted({str(r) for r in (row_labels or ()) if r}):
        segments = str(label).split(HEADER_LEVEL_SEP)
        stub = segments[-1]
        band = HEADER_LEVEL_SEP.join(segments[:-1]) if len(segments) > 1 else ""
        cands = _match(stub)
        # NON-BINDING, and it must stay that way: what the band alone would have
        # matched. Reported so a reader can see the relationship the rule
        # refused to use, and so a declared binding has something to disagree
        # with. Nothing downstream may bind from this.
        band_cands = _match(band) if band else []
        row = {
            "row_label": label,
            "matched_against": stub,
            "n_candidates": len(cands),
            "candidates": cands,
            "status": ("unmatched" if not cands
                       else "bound" if len(cands) == 1 else "ambiguous"),
            "note": (
                "No declared variable's name relates to this row label."
                if not cands else
                "One candidate; safe to bind." if len(cands) == 1 else
                "Several candidates, and they may differ in FAMILY -- which "
                "decides which checks may run. Choosing one here would be "
                "choosing a verdict, so none is chosen."
            ),
        }
        if band:
            row["band"] = band
            row["band_candidates"] = band_cands
            if band_cands and not cands:
                row["note"] += (
                    f" The row sits under the band {band!r}, whose own name "
                    f"matches {len(band_cands)} declared variable(s) -- NOT "
                    "used, because a band may name a variable whose children "
                    "are its levels, or a topic whose children are separate "
                    "variables, and the strings cannot tell those apart."
                )
        out.append(row)
    return out


def build_from_paper(paper_dir: Any, variables: list[dict] | None = None,
                    bindings: dict | None = None) -> dict:
    """The register for a paper on disk, from what the pipeline already extracts.

    ONE WALKER, deliberately. `prepass.paper_tables` is the single enumerator of
    article AND supplement tables, and its own docstring warns that a second
    walk is two denominators. This calls it rather than globbing, for the same
    reason `completeness.build_manifest` does.

    `variables` and `bindings` are the model's declarations. Absent them the
    register still builds -- every group carries `variable_id: None`, ambiguous
    cells stay ambiguous, and `applicable_tools` comes back empty. That is not a
    degraded mode to be avoided; it is the honest picture of a paper nobody has
    typed yet, and the gap between the two is what the declaration is worth.
    """
    from pathlib import Path

    from . import completeness, prepass
    from .tools.celltypes import parse_cells

    base = Path(paper_dir)
    base = base if base.is_dir() else base.parent
    tables: list[dict] = []
    problems: list[str] = []
    found = prepass.paper_tables(base, include_supplements=True)
    problems += list(getattr(found, "problems", None) or [])

    # WHICH CHARACTER THIS DOCUMENT USES AS ITS DECIMAL SEPARATOR, decided ONCE
    # from the whole paper before any cell is parsed.
    #
    # `74,874` is 74.874 in a Russian journal and seventy-four thousand in an
    # American one, and both conventions are attested in this corpus, so no
    # per-cell rule can decide it -- guessing thousands is what read a mean of
    # 0.932 as 932 and sent it to GRIM. What CAN decide it is the rest of the
    # paper: a single `0,nnn` anywhere is a comma no thousands reading explains.
    #
    # MEASURED over the 309-paper corpus: 27 papers' table cells carry such a
    # witness, between 14 and 204 of them each, and 196 ambiguous cells sit
    # inside those papers. Every paper having BOTH a witness and an ambiguous
    # comma has ZERO point-decimals, so the two populations do not overlap.
    #
    # Absent a witness the verdict is `unknown` and nothing changes -- the
    # ambiguous cells are left exactly as they were rather than guessed the
    # other way, which is the same refusal the rest of this file makes.
    from .tools.celltypes import infer_decimal_convention
    _all_cells = [str((c or {}).get("raw") or "")
                  for tab in found for c in (tab.get("cells") or [])]
    convention = infer_decimal_convention(_all_cells)
    _comma = convention.get("separator") == "comma"
    if _comma:
        problems.append(
            f"this paper writes decimals with a COMMA ({convention['why']}), so "
            f"{convention['n_ambiguous']} cell(s) of the form `n,nnn` are read "
            f"as decimals rather than as thousands groups")

    for tab in found:
        cells = tab.get("cells") or []
        if not cells:
            continue
        label = str(tab.get("label") or "?")
        if tab.get("source") == "supplement":
            # THE ONE BUILDER. This is where the fact is KNOWN -- `prepass` said
            # the table came out of a supplement -- and everything downstream
            # re-derives it from the string this line writes. Writing it by hand
            # here and reading it by hand there is exactly the encode/decode
            # pair that drifts.
            label = supplement_anchor(tab.get("supplement_file"), label)
        tables.append({"name": label, "cells": cells,
                       "parsed": parse_cells(cells, decimal_comma=_comma)})

    body_items: list[dict] = []
    numeral_index: list[dict] = []
    _stranded_prose = None
    _n_offbody_tables = 0
    try:
        text, _ = completeness._read_body(base)
        if text:
            body_items = completeness._body_items(text)
            # THE FLOOR, UNDER THE FLOOR. `body_items` is a pattern pass and a
            # shape it has not seen is invisible; this is every numeric token,
            # which cannot be. The patterns then classify it rather than being
            # it, so what they miss shows up as `unclassified` instead of as
            # nothing. See `numerals`.
            from . import numerals as _numerals
            numeral_index = _numerals.index(
                text, upto=completeness._body_end(text),
                # Only route a number to the table pass if there IS one.
                tables_available=bool(tables))
            _numerals.classify_with(
                numeral_index,
                [(i["offset"], i["offset"] + len(i["raw"])) for i in body_items],
                evidence="inside a completeness.BODY_PATTERNS match")
            # WHICH SECTION EACH NUMBER SITS IN. Greg, 2026-08-18: "identify
            # those sections and don't include them in the analysis of the
            # extractable values." Stamped here rather than filtered here --
            # the floor stays exhaustive and `classification_batch` is what
            # declines to hand furniture to the model.
            from . import sections as _sections
            secs = _sections.map_sections(text)
            for row in numeral_index:
                row["section"] = _sections.kind_at(secs, row.get("offset") or 0)

            # TABLE CELLS THE BODY DOES NOT HOLD JOIN THE SAME FLOOR (Greg,
            # 2026-09-06: "table values and prose values should be combined
            # floors, but whenever you give the total give the breakdown by
            # source"). Whether a table's numbers are already in `text` is an
            # ACCIDENT OF THE CONVERTER: docling inlines tables as pipe rows,
            # publisher XML and HTML keep them in their own elements. So on
            # the 99 XML-sourced corpus papers every article table cell was
            # in NO denominator -- measured on the 12-paper working corpus
            # before this: `table_cell: 0` of 3,218. Keyed on the one span
            # rule both floors share (`numerals.table_span`), so an inlined
            # table cannot be counted twice. The split is carried by
            # `tally.by_source` and printed beside every total.
            for tab in found:
                cells_ = tab.get("cells") or []
                if not cells_ or _numerals.table_span(text, cells_):
                    continue
                _n_offbody_tables += 1
                origin = str(tab.get("supplement_file") or tab.get("label") or "?")
                src = "supplement" if tab.get("source") == "supplement" else "article"
                cell_rows = _numerals.index_table_cells([tab], origin, src)
                for row in cell_rows:
                    row["section"] = "table"
                numeral_index += cell_rows

            # DOES THE FLOOR'S COMPLETENESS CLAIM ACTUALLY HOLD HERE?
            # `numerals.tally` tells a reader that `n_total` "is the one count
            # here that cannot be silently incomplete", and `register_view`
            # prints that sentence. It rests on the reference cut above
            # removing only references.
            #
            # MEASURED over the 12-paper corpus: SIX papers strand real body
            # prose on the references side, 27 lines in all -- every
            # two-column PNAS paper, because the converter interleaves the
            # bibliography with the running text. On pnas.0801268105 the tail
            # holds `mean age, 25.6 years of age; SD, 3.3` and the whole
            # `Materials. Training task.` section.
            #
            # Recorded rather than repaired: moving the boundary readmits the
            # bibliography, which is the largest source of numerals that are
            # not statistics, and recovering only the prose means deciding line
            # by line which column each belongs to. A claim that does not hold
            # for this document should say so.
            from . import references as _refs
            stranded = _refs.stranded_prose(text)
            if stranded.get("n_lines"):
                # Stashed here, where `text` is in scope, and attached to the
                # register below where `reg` exists.
                _stranded_prose = stranded
                problems.append(
                    f"the numeral floor is INCOMPLETE for this paper: "
                    f"{stranded['n_lines']} line(s) of body prose "
                    f"({stranded['n_chars']} chars) fell on the references side "
                    f"of the split (how={stranded['how']}), so any 'numbers we "
                    f"did not check' denominator built from it is a floor on a "
                    f"floor")
    except Exception as exc:  # noqa: BLE001
        # NOT SILENT. A paper whose body could not be read has NO prose values
        # here, and that is indistinguishable from a paper with none -- the
        # absence-as-knowledge failure this repo keeps finding. Recorded.
        problems.append(f"body text could not be read, so no prose values: {exc}")

    # ONE BINDING RULE, NOT TWO. `agent.py` built `bindings` as an exact
    # name->id dict while `binding_candidates` -- which allows containment and
    # is the rule this module documents -- ran afterwards for DISPLAY ONLY. So
    # the register was built by the weaker rule and the better one only told a
    # reader what had been missed.
    #
    # MEASURED on 10.1007--s00702-004-0248-2 against its own run's anatomy:
    # exact match binds 0 of 16 row labels; the containment rule binds 1
    # (`Age (years) 1` -> `Age`) and leaves 15 unmatched. A modest gain, and it
    # is the honest ceiling for a rule that does not guess.
    #
    # ONLY WHERE THERE IS EXACTLY ONE CANDIDATE, which is the status this
    # module's own note calls "safe to bind". The refusal it documents is about
    # AMBIGUITY: on the fraud ground-truth paper `Self-evaluation` matches both
    # a `likert_item` and a `likert_composite`, and those differ in GRIM's
    # granularity denominator, so choosing between them is choosing a verdict.
    # Two-candidate rows stay unbound here exactly as before.
    bindings = dict(bindings or {})
    _labels = sorted({str(c.get("row_label")) for t in tables
                      for c in (t.get("cells") or [])
                      if isinstance(c, dict) and c.get("row_label")})
    _auto: dict[str, str] = {}
    for _row in binding_candidates(_labels, variables):
        if _row["status"] == "bound" and _row["row_label"] not in bindings:
            _auto[_row["row_label"]] = str(_row["candidates"][0]["variable_id"])
    bindings.update(_auto)

    reg = build_register(tables=tables, body_items=body_items,
                         bindings=bindings, variables=variables)
    reg["paper"] = base.name
    # REPORTED, because a binding nobody can see is a binding nobody can check.
    reg["auto_bound_rows"] = {
        "rule": ("a row label and a variable name where one contains the other, "
                 "and only where exactly one variable matches"),
        "n": len(_auto),
        "rows": _auto,
    }
    reg["n_tables"] = len(tables)
    reg["problems"] = problems
    # WHY EACH UNBOUND ROW IS UNBOUND, with the candidates. An unbound row is
    # the single largest coverage blocker measured across the archive (275
    # cells), and reporting only the count leaves a reader unable to tell "no
    # variable was declared for this" from "several were and they conflict".
    # The second is the common case and the actionable one.
    unbound = sorted({g.get("row_label") for g in reg.get("groups") or []
                      if (g.get("anchor") or {}).get("where") == "table"
                      and not g.get("variable_id") and g.get("row_label")})
    if unbound:
        reg["unbound_rows"] = binding_candidates(unbound, variables)
    if numeral_index:
        from . import numerals as _numerals
        if _stranded_prose:
            reg["numerals_incomplete"] = _stranded_prose
        reg["numerals"] = {
            **_numerals.tally(numeral_index),
            # HOW MANY TABLES WERE ENUMERATED DIRECTLY, so a reader of the
            # split can tell "no table cells" from "every table was inlined".
            "n_offbody_tables": _n_offbody_tables,
            # EVERY ROW, not a summary. Exhaustiveness is the property this
            # layer exists to provide, and an artefact that only counts cannot
            # be checked for it.
            "rows": numeral_index,
        }
    return reg


def classification_batch(register: dict | None,
                         variables: list[dict] | None = None,
                         limit: int | None = None) -> dict:
    """The residue the pattern floor could not name, handed to the model.

    Greg, 2026-08-18, on where the search should start:

        > instead of looking for these patterns, I think that target of the
        > search for values ought to be ALL NUMERIC VALUES. And only after a
        > numeric value is indexed, the model looks at the context in order to
        > classify it as, e.g., a mean.

    `numerals` is the first half of that -- every numeric token, found without a
    model and without a shape rule. This is the second: the tokens no pattern
    claimed, packaged with the context needed to judge them. MEASURED on
    10.1007--s00702-004-0248-2: 319 numerals, 144 unclassified, `share_judged`
    0.55. The residue is the work.

    AND IT COMES AFTER THE ANATOMY, WHICH IS THE WHOLE POINT OF THE ORDERING.
    Greg again, and this is a constraint rather than a preference:

        > this must come AFTER the construction of the statistical anatomy.
        > Since otherwise the model would need to derive the variable
        > characteristics of the printed values in a vacuum.

    So with no declared variables this function does NOT return a smaller batch
    or an empty one. It returns `ready: False` and says why. A batch emitted
    into a vacuum would get answered -- models answer -- and the answers would
    be variable characteristics invented to fit the digits, which is the input
    to a false accusation. Refusing loudly is the only safe failure here.

    IT HANDS OVER, IT DOES NOT DECIDE. Nothing in here guesses a role. The
    `candidates` on each item are variables whose declared name appears in that
    number's own context window; they are REPORTED for the model to choose
    among, never matched, for the same reason `binding_candidates` reports and
    does not bind -- candidates that differ in family differ in which checks may
    run, so choosing between them would be choosing a verdict.

    NOT A DENOMINATOR. `numerals` stays the floor and `completeness` stays the
    tripwire. This is a worklist drawn FROM the floor, and a model that
    classifies every item on it has not thereby covered the paper.
    """
    from . import sections as _sections

    reg = register or {}
    rows = ((reg.get("numerals") or {}).get("rows")) or []
    residue = [r for r in rows if r.get("class") == "unclassified"]
    # FURNITURE IS NOT WORK. A number in the title block is an affiliation
    # superscript and a number in the acknowledgements is a grant id; neither is
    # a reported statistic, and handing them over invites a classification that
    # a check could later act on. Rows carrying no `section` are treated as
    # analytic, so a paper whose structure we could not read loses nothing.
    furniture = [r for r in residue
                 if r.get("section") in (_sections.FRONT_MATTER,
                                         _sections.BACK_MATTER)]
    residue = [r for r in residue if r not in furniture]

    declared = [v for v in (variables or []) if isinstance(v, dict) and v.get("id")]
    out: dict = {
        "paper": reg.get("paper"),
        "n_numerals_total": len(rows),
        "n_residue": len(residue),
        # COUNTED, NOT SILENT. An exclusion nobody can see is a coverage claim.
        "n_excluded_as_furniture": len(furniture),
        # The vocabulary is CLOSED and shipped with the batch, so the model
        # picks from the same list every consumer keys off rather than inventing
        # a synonym that no dispatcher recognises.
        "vocabulary": {"role": list(ROLES), "role_class": list(ROLE_CLASSES)},
        "variables": [{
            "id": v.get("id"),
            "name": v.get("name"),
            "family": v.get("family"),
            "measurement_level": v.get("measurement_level"),
            "discreteness": v.get("discreteness"),
            "lower_bound": v.get("lower_bound"),
            "upper_bound": v.get("upper_bound"),
            "units": v.get("units"),
            "n_items": v.get("n_items"),
            "derivation": v.get("derivation"),
        } for v in declared],
    }

    if not declared:
        out["ready"] = False
        out["not_ready_because"] = (
            "No variable has been declared for this paper, so there is nothing "
            "to classify these numbers AGAINST. Build the statistical anatomy "
            "first: asked in this state the model would have to infer each "
            "value's measurement level, bounds and granularity from the digits "
            "alone, and those inferences are the inputs GRIM, GRIMMER and "
            "SPRITE turn into accusations.")
        out["items"] = []
        return out

    names = [(str(v.get("name") or ""), v.get("id")) for v in declared]
    items = []
    for r in (residue[:limit] if limit else residue):
        ctx = str(r.get("context") or "")
        low = ctx.lower()
        cands = [vid for nm, vid in names if nm and nm.lower() in low]
        items.append({
            "id": r.get("id"),
            "printed": r.get("printed"),
            "offset": r.get("offset"),
            "end": r.get("end"),
            "context": ctx,
            # REPORTED, NEVER MATCHED. See the docstring.
            "candidates": cands,
        })
    out["ready"] = True
    out["items"] = items
    out["n_items"] = len(items)
    # A cap is a coverage claim unless it says so. Silent truncation would read
    # as "this is the whole residue".
    if limit and len(residue) > limit:
        out["truncated"] = {"shown": len(items), "of": len(residue),
                            "note": "limit applied by the caller; the rest are "
                                    "unclassified still and are NOT judged."}
    return out


def design_values_from_cells(cells: list[dict] | None,
                             table: str = "t1") -> list[dict]:
    """The group sizes a table prints in its OWN labels, as indexed values.

    WHY THIS EXISTS. `n` is the value that gates `grim_check`, `grimmer_check`,
    `sprite_reconstruct`, `debit_check` and `check_count_percent`, and it is
    100% of `census.blocked_on_input`. Until this function it was never a value:
    `_CELL_ROLES` emits no `n` from any cell kind, so the dispatcher parsed the
    number straight out of a column header (`Placebo (n = 68)`) and passed it as
    a bare argument. The most consequential number on the page was the one the
    register did not hold -- the hover view could show a mean, show GRIM running
    on it, and offer NO NODE for the n that permitted the check.

    MEASURED over the 305-paper cerebrolysin corpus: 180 papers (59.0%) print an
    `n = ...` somewhere, 1,651 occurrences in all, and 61 papers (20.0%) print
    one inside a table row.

    ONE VALUE PER PRINTED OCCURRENCE, NOT PER CELL. A single `(n = 68)` in a
    column header governs every cell beneath it. Emitting one value per cell
    would put twelve copies of one number in the register and show a reader
    twelve nodes for one piece of ink. Occurrences are keyed on the LABEL TEXT,
    which also survives the columnless cells real extractions produce (measured:
    0 of 20 cells carried a `col` on 10.1007--s00702-004-0248-2), and the
    positions the label governs are kept on the anchor so a viewer can still
    highlight every cell it applies to.

    Two arms both reading `n = 30` stay two values, because `Drug (n = 30)` and
    `Placebo (n = 30)` are two distinct printed claims that happen to agree.

    NOT A GROUP. Groups are things that get CHECKED; a design value is a thing
    that gets CONSUMED. Filing these as groups would add permanently-unchecked
    entries to the coverage denominator and make a paper look less covered the
    more of its structure we successfully read -- an artefact this repository
    has been bitten by before.
    """
    from .dispatch import _N_IN_LABEL

    out: dict[tuple[str, str], dict] = {}
    for cell in cells or []:
        if not isinstance(cell, dict):
            continue
        for axis in ("col_label", "row_label"):
            text = cell.get(axis)
            if not isinstance(text, str):
                continue
            for m in _N_IN_LABEL.finditer(text):
                printed = m.group(1)
                key = (axis, text)
                v = out.get(key)
                if v is None:
                    anchor = {"where": "table", "table": table,
                              "axis": axis, "label": text,
                              "occurrences": []}
                    v = {
                        "id": value_id(anchor, "n"),
                        "role": "n",
                        "role_class": role_class("n"),
                        # The paper's own literal, including any thousands
                        # separator it printed -- `printed` is what the page
                        # says, `value` is what the check consumes.
                        "printed": printed,
                        "value": int(printed.replace(",", "")),
                        "decimals": 0,
                        "anchor": anchor,
                        "group": None,
                        "variable_id": None,
                    }
                    out[key] = v
                pos = {"row": cell.get("row"), "col": cell.get("col")}
                if pos not in v["anchor"]["occurrences"]:
                    v["anchor"]["occurrences"].append(pos)
    return list(out.values())


def build_register(tables: list[dict] | None = None,
                   body_items: list[dict] | None = None,
                   bindings: dict | None = None,
                   variables: list[dict] | None = None) -> dict:
    """The whole register for one paper.

    `tables` is a list of `{"name": str, "parsed": <parse_cells output>}`.
    """
    by_id = {str(v.get("id")): v for v in (variables or []) if isinstance(v, dict)}
    groups: list[dict] = []
    design: list[dict] = []
    stats: dict = {}
    # DISTINCT NAMES, ENFORCED HERE. Two tables can arrive with names that slug
    # to the same key (`cref='#/texts/57'` and `cref-texts-57`), and every
    # unnamed table used to fall back to the same literal `"t1"` -- colliding
    # with each other AND with a real table called `t1`. Colliding table names
    # collide every id beneath them, which poisons `same_value`, the verdict
    # join and any viewer highlight.
    used: dict[str, int] = {}
    from .dispatch import _section_denominators

    table_cells: dict[str, list] = {}
    #: `table|row|col_label` -> the section denominator composite VERIFIED, and
    #: -> why a column's two denominators disagree. See the build loop below.
    section_n: dict[str, dict] = {}
    section_disputed: dict[str, str] = {}
    for idx, t in enumerate(tables or []):
        name = t.get("name") or f"table{idx + 1}"
        key = _slug(name)
        if key in used:
            used[key] += 1
            name = f"{name}#{used[key]}"
        else:
            used[key] = 1
        groups += groups_from_cells(t.get("parsed") or {},
                                    cells=t.get("cells"),
                                    table=name,
                                    bindings=bindings, variables=by_id,
                                    stats=stats)
        table_cells[name] = [str((c or {}).get("raw") or "")
                             for c in (t.get("cells") or [])]
        # THE SECTION'S VETO, RECORDED WHERE THE CELLS ARE STILL IN HAND.
        # `check_stated_denominators` runs later from the register alone, and
        # the register keeps only each cell's printed TEXT (`table_cells`
        # above). So the structural facts it needs -- which rows form a
        # section, and whether that section's counts agree with the column
        # header -- must be recorded here or they are gone. Keyed on the
        # DEDUPLICATED `name`, because that is what the group anchors carry.
        _cells = t.get("cells") or []
        try:
            _sec_n, _sec_pub, _sec_disp = _section_denominators(_cells)
        except Exception:                                    # noqa: BLE001
            _sec_n, _sec_disp = {}, {}          # a bad table must not fail the build
        for _i, _info in (_sec_n or {}).items():
            _c = _cells[_i] if _i < len(_cells) else {}
            section_n[_section_key(name, _c.get("row"),
                                   _c.get("col_label"))] = _info
        for _i, _why in (_sec_disp or {}).items():
            _c = _cells[_i] if _i < len(_cells) else {}
            section_disputed[_section_key(name, _c.get("row"),
                                          _c.get("col_label"))] = _why
        design += design_values_from_cells(t.get("cells"), table=name)
    groups += groups_from_body_items(body_items or [])

    # THE EDGE FROM A CHECKED GROUP TO THE VALUE THAT PERMITTED THE CHECK.
    # Matched on the label text, the same string `design_values_from_cells`
    # keyed on, so a group and its n agree by construction rather than by two
    # parsers happening to concur.
    by_label = {(v["anchor"]["axis"], v["anchor"]["label"]): v["id"]
                for v in design}
    for g in groups:
        a = g.get("anchor") or {}
        want = (("col_label", a.get("col_label")),
                ("row_label", g.get("row_label")))
        g["design_inputs"] = [by_label[k] for k in want if k in by_label]

    values = [v for g in groups for v in (g.get("values") or [])]
    n_bound = sum(1 for v in values if v.get("variable_id"))
    return {
        "n_groups": len(groups),
        "n_values": len(values),
        # COUNTED APART FROM `n_values`. Design values are not candidates for a
        # check, so folding them into the value count would inflate every
        # coverage rate computed against it -- the denominator would grow with
        # each `n` we successfully read while the numerator stood still.
        "n_design_values": len(design),
        "n_groups_with_a_design_input": sum(
            1 for g in groups if g.get("design_inputs")),
        "design_values": design,
        "n_values_bound_to_a_variable": n_bound,
        # A GROUP WITH NO APPLICABLE TOOL IS NOT A GAP IN THE PAPER. It is
        # either a kind no check consumes or a variable nobody declared, and
        # `census` is what tells those two apart. Counted here so the register
        # never reads as a coverage claim it has not earned.
        "n_groups_with_no_applicable_tool": sum(
            1 for g in groups if not g.get("applicable_tools")),
        # Cells that printed no number at all -- a row label, an empty cell.
        # COUNTED, never invented: the register may not manufacture a value for
        # a cell that has none, and may not stay silent about one either.
        "n_cells_with_no_value": stats.get("skipped_no_value", 0),
        # SPLIT BY REASON. One number conflated the paper saying "no
        # value here" with a table row our extractor glued shut. See
        # `no_value_reasons` for the measurement that separated them.
        "no_value_because": no_value_reasons(stats.get("no_value_raw") or []),
        # Groups whose cell kind has no role map, carried with role `unknown`
        # rather than dropped. `47 (60.3)` prints two numbers and cannot say
        # which is the count; a value nobody has typed yet is still a value.
        "n_untyped_groups": sum(1 for g in groups if g.get("typing") == "untyped"),
        # WHOSE COLUMN CANNOT BE TOLD FROM ANOTHER. Computed for every
        # cell since the stacked-header work and, until now, read only by
        # `group_id`. See `ambiguous_columns` for why a reader needs it.
        "ambiguous_columns": ambiguous_columns({"groups": groups}),
        "groups": groups,
        # Printed cell texts per table, so a `check_table` call recorded in a
        # run's ledger -- which does not know its own table -- can be matched
        # back to one. See `table_for_cells`.
        "_table_cells": table_cells,
        # See `_section_key`. Consumed by `check_stated_denominators`, which
        # cannot see a cell.
        "_section_n": section_n,
        "_section_disputed": section_disputed,
        "same_value": same_value_edges(groups),
        "is_a_floor": (
            "Counts only what the extractor could see and the typer could name. "
            "An image-only table, an unfetched supplement and a prose statistic "
            "whose components could not be joined all contribute less here than "
            "they do in the paper, so every count is a LOWER BOUND."
        ),
    }
