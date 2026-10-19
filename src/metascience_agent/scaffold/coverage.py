"""The three HEADLINE coverage measures, computed without a model.

WHY THESE THREE AND NOT THE NUMERAL FLOOR (Greg, D34, 2026-09-06). The floor is
an INVENTORY: it exists so that digit conservation on a table can be checked and
so that an under-reading pass shows up as a falling share rather than an
unchanged score. It is not the headline denominator, because a paper's numerals
are not the thing a reader wants covered -- its table cells, its statistic-bearing
sentences and its declared variables are. So:

    H1  table cells placed          -- of every walker cell that carries a numeral
    H2  statistic-bearing sentences -- of every sentence with a statistic in it
    H3  declared variables with values

EVERY TOTAL IS PRINTED WITH ITS SPLIT (Greg, 2026-09-06: "whenever you give the
total give the breakdown by source"). A total with no split is a number a reader
cannot interrogate: 56% placed over article and supplement together hides that
the article is at 95% and the supplement at 4%, which is a different fact about
the tool. `headline()` therefore refuses to emit a total without the split beside
it, and the renderer prints them on the same line.

THE TIERS PARTITION THE DENOMINATOR, and that is what makes them honest. A cell
lands in exactly one of `placed`, `read_unbound`, `unparsed`, `unread`; a
sentence in exactly one of `covered`, `partial`, `uncovered`. `check_conservation`
is called on every block and its failures ride out in `problems`, because the
failure mode this guards against is the one measured on `25e2f9f`: a change that
raises `placed` by making cells checkable, while the other tiers fall by a
different amount, has not improved coverage -- it has moved the denominator.

NOTHING HERE CALLS A MODEL and nothing here re-reads the paper. Every number is a
function of `account.json` and `document.json` alone, so a disk-only re-render
reproduces it exactly.
"""

from __future__ import annotations

import bisect
import re
from typing import Any, Iterator

from .. import numerals as _numerals
from . import bind as _bind
from . import codestamp as _codestamp
from . import premises as _premises

#: The states a table cell can be in. They partition the denominator.
#: `non_statistical` is the cell of a table that is a CODEBOOK rather than a
#: result -- see `table_role`. It is a tier and never a subtraction: the cell
#: stays in `cells`, so `share_placed` cannot rise by relabelling a table.
H1_TIERS = ("placed", "read_unbound", "unparsed", "unread", "non_statistical")

#: `placed` SPLIT BY WHAT BACKS THE ID, and both halves are printed on the
#: headline line. A cell is placed when a value built from it carries a declared
#: variable id; whether the name join CORROBORATED that id is a different fact
#: about the same cell, and burying the uncorroborated half inside
#: `read_unbound` said "not placed" about a cell that had been placed by the
#: model and could not be cross-checked. The sub-tiers do not change the outer
#: partition -- they sum to `placed` exactly, and `check_conservation` says so.
H1_PLACED_SUBTIERS = ("placed_corroborated", "placed_model_only")

#: The three states a statistic-bearing sentence can be in.
H2_TIERS = ("covered", "partial", "uncovered")

#: A numeral in one of these DISPOSITIONS is not a statistic, so it neither puts
#: a sentence into the denominator nor counts against its coverage: a citation
#: year is the literature's number, not the paper's, and a table cell is owned by
#: H1 and would otherwise be counted twice.
NOT_A_STATISTIC = ("citation_year", "table_cell")

#: ...and a numeral in one of these CLASSES is not a statistic either, whatever
#: its disposition. THE FLOOR ALREADY KNEW: `(Table 4)` was classed `ordinal`
#: with the reason `follows '(Table'` and then counted anyway, so a sentence
#: reading "none of the practices was associated with EBP fidelity (Table 4)"
#: was uncovered on the strength of the 4. Measured over ajcp.70049's 24
#: not-covered sentences: 9 blocked by a citation year the old classifier missed,
#: 9 by a `(Table N)` already named `ordinal`, 8 by a declared phase label, 4 by
#: factorial notation, 1 by a page number.
#:
#: EVERY MEMBER IS A CLASSIFICATION AND NOT A SUPPRESSION -- the numeral stays in
#: the floor's `n_total` and in `by_class`, and only this measure declines to
#: count it. That distinction is the one measured at +206 rows in CLAUDE.md 8f,
#: and it is why this is a tuple of class names rather than a filter over the
#: index. `scale_anchor` is deliberately NOT here: `1 = sad, 9 = happy` names the
#: ends of a measured scale and a reader may reasonably want it covered.
NOT_A_STATISTIC_CLASSES = ("citation_year", "citation_page", "citation_marker",
                           "ordinal", "placeholder", "phase_label")

#: A numeral the account placed on a value row.
IS_A_VALUE = ("value", "duplicate_of_value")


def _is_a_statistic(row: dict) -> bool:
    return (row.get("disposition") not in NOT_A_STATISTIC
            and (row.get("class") or "unclassified") not in NOT_A_STATISTIC_CLASSES)


def numerals_a_comparison_holds(account: dict, text: str) -> set[str]:
    """The ids of accounting rows a COMPARISON or the declared alpha already holds.

    H2 asks whether the account READ the number, and `IS_A_VALUE` answers it only
    for the value table. A p-threshold does not become a value row -- it becomes a
    field on a comparison -- so on ajcp.70049 five sentences read as uncovered
    while `cmp:funding-reach-in-decision-making-model` quotes one of them
    verbatim and carries `p_threshold: 0.05`. The account had read the number and
    the measure said it had not.

    THE JOIN IS DOUBLE AND BOTH HALVES ARE THE ACCOUNT'S OWN. The numeral must sit
    inside the comparison's LOCATED quote -- located here by `bind.locate`, the
    same matcher that verified it -- and its printed digits must be among the
    numbers that comparison itself carries. A numeral merely near a comparison is
    not credited, so this cannot cover a sentence the account did not read.
    """
    rows = [r for r in (account.get("accounting") or []) if r.get("offset") is not None]
    if not rows or not text:
        return set()
    held: set[str] = set()

    def _num(s: Any) -> float | None:
        try:
            return float(str(s).replace("−", "-").replace(",", "."))
        except ValueError:
            return None

    def _credit(span: tuple[int, int] | None, printed: list[Any]) -> None:
        if not span:
            return
        toks = {m.group(0) for p in printed if p is not None
                for m in _numerals.tokens(str(p))}
        toks |= {t.lstrip("+-−") for t in toks}
        # BY VALUE AS WELL AS BY STRING. The paper prints `p < .05` and the
        # comparison carries `p_threshold: 0.05`; a string comparison called
        # those different numbers and left five ajcp sentences uncovered while
        # the account held every one of them.
        vals = {v for t in toks if (v := _num(t)) is not None}
        for r in rows:
            if not (span[0] <= r["offset"] < span[1]):
                continue
            p = r["printed"].lstrip("+-−")
            if p in toks or (_num(p) is not None and _num(p) in vals):
                held.add(r["id"])

    for c in account.get("comparisons") or []:
        if c.get("quote_verified") not in ("verbatim", "stitched"):
            continue
        _credit(_bind.locate(str(c.get("quote") or ""), text),
                [c.get("p_printed"), c.get("p_threshold"), c.get("statistic_printed"),
                 c.get("df_printed")])
    # THE DECLARED ALPHA, wherever the paper states it. `Test-specific
    # significance levels were assessed at alpha <= .05.` holds one numeral and it
    # is the account's `alpha_declared`, quoted.
    sa = account.get("statistical_analysis") or {}
    alphas = [sa.get("alpha_declared")] + [s.get("alpha") for s in account.get("studies") or []]
    if any(a is not None for a in alphas):
        _credit(_bind.locate(str(sa.get("alpha_quote") or ""), text), alphas)
    return held

#: The `id_check` outcomes that CORROBORATE the variable id an entry carries
#: (`interpret.bind_entries`): `agrees` = the model's id and the name join agree;
#: `join` = the model gave none and the join supplied one. `unjoined` (the model
#: asserted an id the join could not check) and a missing check (the pass-3 row
#: map, which has no join at all) are NOT corroboration, and `disagrees` is the
#: opposite of it. Measured on ajcp: 82 of 222 entries are `unjoined` and one of
#: those is wrong. So a corroborated id and a model-only id are two sub-tiers of
#: `placed` and are printed as two numbers; `disagrees` is not placed at all.
#:
#: IMPORTED, NOT RESTATED. This was a second literal copy of the same two tokens
#: `checks.py` also carried, and `tests/test_scaffold_premises.py` ratchets it:
#: under `scaffold/`, only `premises.py` may assign this name.
CORROBORATED = _premises.CORROBORATED


def _binding_of(value: dict) -> str:
    """The value's stamped binding, or the same rule applied on the spot.

    FOUR-VALUED, AND THE TIERS BELOW ARE A SELECTION FROM IT: `corroborated` is
    the join's own word, `model_only` (no join was possible) and `unchecked`
    (`unjoined`, or a token nobody here has heard of) rest on the model alone,
    and `contradicted` is the join naming a different variable. `bind.assemble`
    stamps before this module runs, so the fallback is for a hand-built account
    -- and it calls the SAME function, which is the point of the wave: one rule,
    one place, and a reader that cannot disagree with the bridge about whether a
    value is corroborated.
    """
    got = (value.get("premise") or {}).get("binding")
    return got if got in _premises.BINDINGS else _premises.binding(value)

#: What makes a sentence statistic-bearing when it carries no in-scope numeral.
#: OURS, not the literature's -- named here so a reader can see what was counted.
#: Each pattern requires an operator, a bracket or a word beside the symbol, so
#: that the English words `or`, `t` and `d` cannot enter the denominator on their
#: own. An over-broad list here can only DEFLATE coverage (a token-only sentence
#: is scored `uncovered`), never flatter it.
STAT_TOKENS: tuple[tuple[str, re.Pattern], ...] = (
    ("p_value", re.compile(r"\bp\s*[-–]?\s*(?:value)?\s*[<>=≤≥]")),
    ("confidence_interval", re.compile(r"\bCIs?\b|\bconfidence interval")),
    ("sd", re.compile(r"\bSDs?\b|\bstandard deviation")),
    ("se", re.compile(r"\bSE\b|\bSEMs?\b|\bstandard error")),
    ("iqr", re.compile(r"\bIQR\b|\binterquartile")),
    ("effect_ratio", re.compile(r"\b(?:a?OR|a?HR|a?RR|ARR|IRR)\s*[=,:(]")),
    ("beta", re.compile(r"\bbetas?\b|β")),
    ("test_statistic", re.compile(r"\b[BFtrdz]\s*\(?[\d, ]*\)?\s*=")),
    ("chi_square", re.compile(r"\bchi[-\s]?squares?\b|χ")),
    ("r_squared", re.compile(r"\bR\s*[²³2]\b|\bR-squared\b")),
    ("sample_size", re.compile(r"\b[nN]\s*=")),
    ("percent", re.compile(r"%")),
)


def _key(table_id: Any, row: Any, col: Any) -> tuple:
    return (table_id, row, col)


def check_conservation(tiers: dict[str, int], denominator: int, what: str) -> list[str]:
    """The tiers must sum to the denominator, exactly. Returns problems.

    THE POINT IS THE FAILURE MESSAGE. A tier sum that is short means something
    landed in no tier; a sum that is long means something landed in two. Both are
    silent in a percentage and loud here.
    """
    total = sum(tiers.values())
    if total != denominator:
        return [f"{what}: the tiers sum to {total} but the denominator is {denominator} "
                f"({'; '.join(f'{k} {v}' for k, v in tiers.items())}); a unit landed in "
                "no tier or in two"]
    return []


def _share(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


# --------------------------------------------------------------------------
# H1. Table cells placed
# --------------------------------------------------------------------------


#: What a table is FOR. `unknown` is the default and is not a failure: it is a
#: table nothing here has positive evidence about, and it is scored exactly as
#: every table was scored before this test existed.
TABLE_ROLES = ("statistics", "non_statistical", "unknown")

#: The statistic kinds a codebook's numbers take. A rating CODE (`Effective (5)`),
#: a count of qualifying studies, an unclassifiable token -- none of them is a
#: measurement OF anything, and none is a premise any check consumes. A single
#: `mean`, `sd`, `percentage`, `p` or `ci_*` in the reading is enough to make the
#: table statistics, which is what keeps this a positive test on the whole table
#: rather than a judgement about cells.
NON_MEASUREMENT_STATISTICS = frozenset({"score", "count", "other"})

#: Words by which a table's OWN PRINTED FURNITURE says it is a codebook: its
#: caption, its footnotes and the row and column headers the WALKER read, before
#: any model saw the table. Deliberately not the cell text -- a results table may
#: name a registry in a cell -- and deliberately short: each word here names the
#: table's JOB, not its subject.
ROLE_WORDS: tuple[str, ...] = (
    "crosswalk", "cross-walk", "codebook", "code book", "coding scheme",
    "coding frame", "coding rules", "rating scheme", "registry", "registries",
    "clearinghouse", "clearinghouses", "glossary",
)


def _table_furniture(table: dict) -> list[tuple[str, str]]:
    """`(where, text)` for every piece of printed furniture this table carries.

    The row and column labels come from `walker_cells`, never from `cells`: a
    verified reconstruction REPLACES `cells` and refreshes the labels, so the
    labels on a read table are the model's and the labels on the walker's cells
    are the paper's. A role must rest on the paper's.
    """
    out: list[tuple[str, str]] = [("caption", str(table.get("caption") or ""))]
    out += [("footnote", str(f)) for f in table.get("footnotes") or []]
    for c in table.get("walker_cells") or []:
        out.append(("column header", str(c.get("col_label") or "")))
        out.append(("row header", str(c.get("row_label") or "")))
    return [(w, t) for w, t in out if t.strip()]


def table_role(table: dict) -> dict:
    """`{"role", "why"}`: is this table a result, or a codebook?

    THE TEST IS POSITIVE AND IT IS NEVER A SUBTRACTION. ajcp table:6 is the EBP
    rating crosswalk -- `Rating 1 | Rating 2 | Blueprints | NREPP | ...` over
    `Evidence-based (1) | Effective (5) | Model | 4 | ...` -- and its 19
    numeral-bearing cells are rating CODES. Read as a statistics table it is 15
    uncovered cells, which says something false about the account. Read as what
    it is, it is a table whose numbers were never anybody's to place.

    So the cells stay in the denominator and move to their own tier, disclosed
    with the evidence. That is the cheap form of the `25e2f9f` hazard: if this
    test is wrong about a table, a real statistics supplement is MISLABELLED,
    and coverage does not rise for it -- `placed` falls and `cells` does not
    move. A denominator subtraction would have bought coverage for free.

    BOTH CONDITIONS ARE REQUIRED, and each is evidence of a different kind:

      * every statistic the READING found is one of `NON_MEASUREMENT_STATISTICS`,
        and there is at least one. This comes from a reading the walker's own
        digits verified, so it is not the model's unchecked word about the table;
      * the table's OWN PRINTED FURNITURE -- caption, footnotes, or the row and
        column headers the walker read -- names a codebook (`ROLE_WORDS`).

    Anything else is `unknown`, and nothing changes for it.
    """
    rec = table.get("reconstruction") or {}
    ver = rec.get("verification") or {}
    if rec.get("status") != "verified":
        return {"role": "unknown",
                "why": "no verified reading, so what kind of numbers this table holds is unread"}
    by_stat = {k: v for k, v in (ver.get("by_statistic") or {}).items() if v}
    if not by_stat:
        return {"role": "unknown", "why": "the reading found no statistic to judge the table by"}
    measured = sorted(k for k in by_stat if k not in NON_MEASUREMENT_STATISTICS)
    if measured:
        return {"role": "statistics",
                "why": f"the reading found {', '.join(measured)}, which no codebook holds"}
    hit = next(((w, where, text) for where, text in _table_furniture(table)
                for w in ROLE_WORDS if w in text.lower()), None)
    if hit is None:
        return {"role": "unknown",
                "why": (f"every statistic read is one of {', '.join(sorted(by_stat))}, but nothing "
                        "the table prints says it is a codebook")}
    word, where, text = hit
    return {"role": "non_statistical",
            "why": (f"every statistic read is one of {', '.join(sorted(by_stat))}, and the table's "
                    f"own {where} “{' '.join(text.split())[:70]}” names a {word}")}


def _cell_carries_a_numeral(raw: Any) -> bool:
    """ONE READER for what a numeral is: `numerals.tokens`, the same enumerator
    the floor uses, with its word-hyphen guard. A second regex here would be the
    `agreement` defect again -- two readings of one page that disagree because
    one of them forgot the sign."""
    return any(True for _ in _numerals.tokens(str(raw or "")))


def _with_a_numeral(cells: list[dict]) -> list[dict]:
    return [c for c in cells or []
            if not c.get("is_header") and _cell_carries_a_numeral(c.get("raw"))]


def _denominator_cells(table: dict) -> tuple[list[dict], list[dict]]:
    """`(cells to score, the walker's own cells)`, both filtered to those that
    carry a numeral. Header and stub cells are in neither list -- the walker puts
    them in `col_labels`, `row_labels` and the cell's own `stub`.

    A CELL IS SCORED THROUGH `cells`, AND COUNTED AGAINST `walker_cells`, and the
    two are not the same list. `walker_cells` is what the extractor read off the
    markup before any model saw it, and is the authority on HOW MANY cells the
    table has. But a verified reconstruction RE-KEYS the grid -- measured on
    ajcp.70049 Table 2, the two lists hold 42 cells each and agree on only 22
    (row, col) pairs -- and every value's `location` names the reconstruction's
    coordinates. Scoring against the walker's keys therefore filed 64 of 162
    cells as `unread` while their values sat one grid over: a conservation
    failure that looked like a coverage failure. The counts are compared instead,
    and a table whose two cell sets differ in size says so in `problems`.
    """
    return _with_a_numeral(table.get("cells") or table.get("walker_cells") or []), \
        _with_a_numeral(table.get("walker_cells") or [])


def table_cells_placed(account: dict, doc: dict | None = None) -> dict:
    """H1: of every table cell that carries a numeral, how many were placed onto
    a declared variable, article and supplement split."""
    doc = doc if doc is not None else (account.get("document") or {})
    tables = doc.get("tables") or []
    if not tables:
        return {"not_computable": "the document holds no tables"}
    declared = {v["id"] for v in account.get("variables") or [] if v.get("id")}

    values_by_cell: dict[tuple, list[dict]] = {}
    for v in account.get("values") or []:
        loc = v.get("location") or {}
        if loc.get("kind") != "table_cell":
            continue
        values_by_cell.setdefault(_key(loc.get("table_id"), loc.get("row"), loc.get("col")),
                                  []).append(v)
    unparsed_cells: set[tuple] = {
        _key(u.get("table_id"), u.get("row"), u.get("col"))
        for u in account.get("unparsed_cells") or []}

    per_table: list[dict] = []
    totals = {t: 0 for t in H1_TIERS}
    sub_totals = {t: 0 for t in H1_PLACED_SUBTIERS}
    splits: dict[str, dict[str, int]] = {}
    why_unbound = {"id_check_disagrees": 0, "regression_intercept": 0,
                   "no_declared_variable_id": 0}
    seen_cells: set[tuple] = set()
    n_cells_total = 0
    problems: list[str] = []

    for t in tables:
        source = t.get("source") or "article"
        split_key = f"{source}_table"
        cells, walked = _denominator_cells(t)
        if t.get("walker_cells") and len(walked) != len(cells):
            problems.append(
                f"{t.get('id')}: the reading holds {len(cells)} numeral-bearing cell(s) and the "
                f"walker read {len(walked)}; the denominator is the reading's, and the two "
                "should not differ")
        n_cells_total += len(cells)
        tiers = {k: 0 for k in H1_TIERS}
        subs = {k: 0 for k in H1_PLACED_SUBTIERS}
        role = table_role(t)
        for c in cells:
            key = _key(t.get("id"), c.get("row"), c.get("col"))
            seen_cells.add(key)
            vals = values_by_cell.get(key)
            # A CODEBOOK'S NUMBERS WERE NEVER ANYBODY'S TO PLACE, and saying so
            # is not the same as removing them: the cell stays in `cells`, so
            # this tier can only LOWER `share_placed`, never raise it.
            if role["role"] == "non_statistical":
                tiers["non_statistical"] += 1
            elif vals:
                # A DECLARED ID PLACES THE CELL; THE `id_check` SAYS ON WHOSE
                # WORD. `disagrees` is neither: the model's id and the name join
                # name different variables, so nothing here is settled and the
                # cell stays unbound (the `25e2f9f` asymmetry, unchanged).
                # THE BINDING IS READ OFF THE STAMP, not re-derived from
                # `id_check` here. `premises.binding` is four-valued and the
                # tiers are a selection from it: `corroborated` is the join's
                # own word, `model_only` and `unchecked` are the model's alone,
                # and `contradicted` is the join naming a different variable.
                if any(v.get("variable_id") in declared
                       and _binding_of(v) == "corroborated" for v in vals):
                    tiers["placed"] += 1
                    subs["placed_corroborated"] += 1
                elif any(v.get("variable_id") in declared
                         and _binding_of(v) != "contradicted" for v in vals):
                    tiers["placed"] += 1
                    subs["placed_model_only"] += 1
                else:
                    tiers["read_unbound"] += 1
                    if any(_binding_of(v) == "contradicted" for v in vals):
                        why_unbound["id_check_disagrees"] += 1
                    # A REGRESSION INTERCEPT IS NOT A FAILED JOIN. There is no
                    # variable for a model's constant term to be, so counting it
                    # under `no_declared_variable_id` says the account missed
                    # something it did not. It is still not `placed` -- no
                    # declared variable holds it -- and it is still in the
                    # denominator; only the REASON changes.
                    elif all(v.get("binding") == "intercept" for v in vals):
                        why_unbound["regression_intercept"] += 1
                    else:
                        why_unbound["no_declared_variable_id"] += 1
            elif key in unparsed_cells:
                tiers["unparsed"] += 1
            else:
                tiers["unread"] += 1
        per_table.append({"table_id": t.get("id"), "label": t.get("label"),
                          "source": source, "caption": t.get("caption"),
                          "role": role["role"], "role_why": role["why"],
                          "n_cells_with_a_numeral": len(cells),
                          "n_walker_cells_with_a_numeral": len(walked),
                          "reconstruction": (t.get("reconstruction") or {}).get("status"),
                          **tiers, **subs})
        for k, n in tiers.items():
            totals[k] += n
        for k, n in subs.items():
            sub_totals[k] += n
        d = splits.setdefault(split_key, {"cells": 0, **{k: 0 for k in H1_TIERS},
                                          **{k: 0 for k in H1_PLACED_SUBTIERS}})
        d["cells"] += len(cells)
        for k, n in list(tiers.items()) + list(subs.items()):
            d[k] += n

    outside = sum(1 for key in values_by_cell if key not in seen_cells)
    if outside:
        problems.append(f"H1 table cells: {outside} cell(s) carry a table value and are not in "
                        "the denominator; a value was built from a cell nothing counted")
    problems += check_conservation(totals, n_cells_total, "H1 table cells")
    problems += check_conservation(sub_totals, totals["placed"], "H1 placed sub-tiers")
    return {
        "cells": n_cells_total,
        "by_tier": totals,
        "by_placed_subtier": sub_totals,
        "placed": totals["placed"],
        "placed_corroborated": sub_totals["placed_corroborated"],
        "placed_model_only": sub_totals["placed_model_only"],
        "share_placed": _share(totals["placed"], n_cells_total),
        "share_placed_corroborated": _share(sub_totals["placed_corroborated"], n_cells_total),
        "non_statistical": totals["non_statistical"],
        "by_role": {r: {"tables": sum(1 for t in per_table if t["role"] == r),
                        "cells": sum(t["n_cells_with_a_numeral"] for t in per_table
                                     if t["role"] == r)}
                    for r in TABLE_ROLES},
        "splits": splits,
        "split_axis": "source",
        "by_table": per_table,
        "read_unbound_because": why_unbound,
        "n_table_values_at_cells_outside_the_denominator": outside,
        "note": (
            "Denominator: every cell of every table the document holds -- article and "
            "supplement alike -- that carries a numeral by `numerals.tokens`, the "
            "floor's own enumerator; header and stub cells are not cells of this "
            "table. The cells are the reading's, which for a verified table re-keys "
            "the walker's grid; `n_walker_cells_with_a_numeral` is printed per table "
            "beside it and a difference is a recorded problem. A cell is `placed` "
            "when a value was built from it AND that value carries a declared "
            "variable id, split into `placed_corroborated` (the name join checked "
            "the id: `id_check` is `agrees` or `join`) and `placed_model_only` (the "
            "model asserted an id the join could not check); the two sub-tiers sum "
            "to `placed`. `read_unbound` when a value exists but no declared id "
            "does, or the join DISAGREES with the one it carries (the reason is "
            "split in `read_unbound_because`, and `id_check == disagrees` can never "
            "be placed); `unparsed` when the cell is in `unparsed_cells`; `unread` "
            "when no reading produced anything for it; `non_statistical` when the "
            "table is a CODEBOOK rather than a result (`coverage.table_role`: every "
            "statistic its verified reading found is a rating code, a count or an "
            "unclassifiable token, AND the table's own caption, footnote or "
            "walker-read header names a crosswalk, a registry or a coding scheme -- "
            "the reason is printed per table in `role_why`). That tier is a "
            "DISCLOSURE, never a subtraction: its cells stay in this denominator, so "
            "calling a table a codebook can only LOWER `share_placed`. The tiers "
            "partition the denominator."),
        "problems": problems,
    }


# --------------------------------------------------------------------------
# H2. Statistic-bearing sentences covered
# --------------------------------------------------------------------------


def _caption_spans(doc: dict, text: str) -> list[tuple[int, int]]:
    """Where the captions are, so a caption sentence is attributed to captions
    and not to whichever section it happens to sit inside.

    Figure captions carry their own span. A table caption does not -- the table
    record keeps the string and not its position -- so it is located with
    `bind.locate`, the one whitespace- and dash-tolerant matcher, rather than a
    second string search that would disagree with it on a repaired dash.
    """
    spans: list[tuple[int, int]] = []
    for f in doc.get("figures") or []:
        if f.get("start") is not None and f.get("end") is not None:
            spans.append((int(f["start"]), int(f["end"])))
    for t in doc.get("tables") or []:
        cap = t.get("caption")
        if not cap:
            continue
        sp = _bind.locate(str(cap), text)
        if sp:
            spans.append(sp)
    return spans


def sentences(text: str, sections: list[dict],
              exclude_roles: tuple[str, ...] = ("back",)) -> Iterator[tuple[int, int, str, str]]:
    """`(start, end, role, sentence)` for every sentence of every section.

    THE SAME SPLITTER `sentence_accountability` USES (`bind._SENTENCE`), and the
    same structural skips -- a heading line, a pipe-table row, an HTML comment is
    not a sentence. What is NOT carried over is that function's 25-character
    floor: `n = 64.` is a short sentence and a statistic-bearing one, and
    dropping it from a coverage denominator would flatter the result.

    `back` is excluded because the reference list is outside the numeral floor
    too; a denominator that included it would count the bibliography's numbers
    as statistics nobody covered.

    A SECTION'S OWN HEADING LINE IS DROPPED BEFORE SPLITTING, which the
    argument-sentence measure does not do. A section span begins at its heading,
    the splitter breaks on `. ` and a heading has no full stop, so the first
    chunk of every section is `## RESULTS\\n\\nThe mean was ...` -- one chunk,
    starting with `#`, discarded by the skip below along with the sentence glued
    to it. Dropping the heading recovers the first sentence of every section; it
    can only ENLARGE this denominator, never shrink it.
    """
    for sec in sections or []:
        if sec.get("role") in exclude_roles:
            continue
        start, end = sec.get("start"), sec.get("end")
        if start is None or end is None:
            continue
        body = text[start:end]
        off = 0
        while body[off:].lstrip(" \t").startswith("#") and "\n" in body[off:]:
            off += body[off:].index("\n") + 1
        pos = start + off
        for sent in _bind._SENTENCE.split(body[off:]):
            st = text.find(sent, pos)
            if st < 0:
                continue
            en = st + len(sent)
            pos = en
            stripped = sent.strip()
            if not stripped or stripped.startswith(("#", "|", "<!--")):
                continue
            yield st, en, sec.get("role") or "?", stripped


def stat_tokens_in(sentence: str) -> list[str]:
    """Which of `STAT_TOKENS` the sentence carries, named."""
    return [name for name, pat in STAT_TOKENS if pat.search(sentence)]


def statistic_sentences(account: dict, text: str | None, doc: dict | None = None) -> dict:
    """H2: of every sentence that carries a statistic, how many have every one of
    their numerals accounted for as a value.

    STRICTER AND BROADER THAN `sentence_accountability`, and both are kept. That
    one asks whether a sentence of the abstract, results or discussion OVERLAPS
    any quote the account carries, over the argument-bearing sections only. This
    one asks, over EVERY section, whether each statistic in the sentence reached
    a value row. A sentence can pass the first and fail this one, which is the
    whole reason for having two: `argument_sentences` measures whether the
    account read the argument, `statistic_sentences` measures whether it read the
    numbers.
    """
    doc = doc if doc is not None else (account.get("document") or {})
    if text is None:
        return {"not_computable": "the account was loaded without the paper's text, "
                                  "and a sentence cannot be split without it"}
    secs = [s for s in (doc.get("sections") or []) if s.get("start") is not None]
    if not secs:
        return {"not_computable": "the document carries no section spans"}
    rows = [r for r in (account.get("accounting") or []) if r.get("offset") is not None]
    rows.sort(key=lambda r: r["offset"])
    offsets = [r["offset"] for r in rows]
    caps = _caption_spans(doc, text)
    held = numerals_a_comparison_holds(account, text)
    n_held = 0
    by_excluded_class: dict[str, int] = {}

    tiers = {k: 0 for k in H2_TIERS}
    by_role: dict[str, dict[str, int]] = {}
    splits: dict[str, dict[str, int]] = {}
    by_token: dict[str, int] = {}
    n_token_only = 0
    n_qualified = 0
    uncovered: list[dict] = []
    n_sentences_read = 0

    for st, en, role, sent in sentences(text, secs):
        n_sentences_read += 1
        lo = bisect.bisect_left(offsets, st)
        hi = bisect.bisect_left(offsets, en)
        nums = [r for r in rows[lo:hi] if _is_a_statistic(r)]
        for r in rows[lo:hi]:
            if not _is_a_statistic(r) and (cl := r.get("class")) in NOT_A_STATISTIC_CLASSES:
                by_excluded_class[cl] = by_excluded_class.get(cl, 0) + 1
        toks = stat_tokens_in(sent)
        if not nums and not toks:
            continue
        # COUNTED HERE, BEFORE ANY TIER IS CHOSEN. The conservation check is only
        # a check if its denominator is arrived at independently of the tiers; a
        # denominator defined as the sum of the tiers can never disagree with
        # them, and would be a test that passes by construction.
        n_qualified += 1
        # READ IS READ. A p-threshold reaches a comparison rather than a value
        # row, and the declared alpha reaches `statistical_analysis`; both are
        # numbers the account holds with a verified quote, and counting only the
        # value table said otherwise about five sentences of ajcp.70049.
        n_val = sum(1 for r in nums if r.get("disposition") in IS_A_VALUE
                    or r["id"] in held)
        n_held += sum(1 for r in nums if r.get("disposition") not in IS_A_VALUE
                      and r["id"] in held)
        if not nums:
            tier = "uncovered"
            n_token_only += 1
        elif n_val == len(nums):
            tier = "covered"
        elif n_val:
            tier = "partial"
        else:
            tier = "uncovered"
        tiers[tier] += 1
        for name in toks:
            by_token[name] = by_token.get(name, 0) + 1
        d = by_role.setdefault(role, {"sentences": 0, **{k: 0 for k in H2_TIERS}})
        d["sentences"] += 1
        d[tier] += 1
        if role == "supplement":
            key = "supplement_prose"
        elif any(a < en and st < b for a, b in caps):
            key = "caption"
        else:
            key = "article_prose"
        s = splits.setdefault(key, {"sentences": 0, **{k: 0 for k in H2_TIERS}})
        s["sentences"] += 1
        s[tier] += 1
        if tier != "covered":
            uncovered.append({"role": role, "offset": st, "tier": tier,
                              "n_statistics": len(nums), "n_placed": n_val,
                              "tokens": toks,
                              "sentence": " ".join(sent.split())[:200]})

    problems = check_conservation(tiers, n_qualified, "H2 statistic-bearing sentences")
    return {
        "statistic_sentences": n_qualified,
        "sentences_read": n_sentences_read,
        "by_tier": tiers,
        "covered": tiers["covered"],
        "share_covered": _share(tiers["covered"], n_qualified),
        "splits": splits,
        "split_axis": "source",
        "by_role": by_role,
        "by_token": dict(sorted(by_token.items(), key=lambda kv: -kv[1])),
        "n_uncovered_with_no_numeral": n_token_only,
        "n_numerals_held_by_a_comparison_or_the_declared_alpha": n_held,
        "numerals_excluded_by_class": dict(sorted(by_excluded_class.items())),
        "not_covered": uncovered,
        "note": (
            "Denominator: every sentence of every section except the reference list "
            "that carries at least one in-scope numeral which is not a citation year "
            "and not a table cell, and whose FLOOR CLASS is not one of "
            f"{', '.join(NOT_A_STATISTIC_CLASSES)} (the counts are in "
            "`numerals_excluded_by_class`; every one of them is still in the floor's "
            "`n_total`, which this measure does not move), OR one of the statistical "
            "tokens in "
            "`coverage.STAT_TOKENS` (`by_token` names which fired). `covered` means "
            "every such numeral reached a value row OR is held by a comparison or by "
            "the declared alpha, with a verified quote covering it and its own digits "
            "matching that record's; `partial` means some did; "
            "`uncovered` means none did, and that bucket also holds the "
            f"{n_token_only} sentence(s) whose only evidence of a statistic is a "
            "token, which nothing in the account could cover. Citation years and "
            "table-cell numerals neither qualify a sentence nor count against it -- "
            "the first are the literature's numbers and the second are H1's. This is "
            "`statistic_sentences`; the separate `argument_sentences` measure "
            "(`sentence_accountability`) is quote-based and runs over the abstract, "
            "results and discussion only."),
        "problems": problems,
    }


# --------------------------------------------------------------------------
# H3. Declared variables with values
# --------------------------------------------------------------------------


def declared_variables_with_values(account: dict) -> dict:
    """H3: of the variables the account declares, how many carry a value.

    THE THREE NUMERATORS SIT SIDE BY SIDE and none replaces another, because they
    answer different questions: whether the variable was measured at all, whether
    it was measured in every study that declares it, and how much of its declared
    level list carries a value. The last is coverage OF THE DECLARATION and never
    a claim about the paper -- a level list can be incomplete (D21: a variable
    listing 6 of its 7 printed levels), so `2 of 3 levels` says two of the levels
    WE RECORDED carry a value, not that the paper printed three.
    """
    variables = account.get("variables") or []
    if not variables:
        return {"not_computable": "the account declares no variables"}
    values = account.get("values") or []
    by_var: dict[str, list[dict]] = {}
    for v in values:
        vid = v.get("variable_id")
        if vid:
            by_var.setdefault(vid, []).append(v)

    with_any = 0
    per_study_ok = 0
    per_study_denominator = 0
    by_role: dict[str, dict[str, int]] = {}
    by_kind: dict[str, dict[str, int]] = {}
    levels_rows: list[dict] = []
    n_levels = n_levels_with = 0
    missing: list[dict] = []

    for var in variables:
        vid = var.get("id")
        vals = by_var.get(vid) or []
        has = bool(vals)
        with_any += has
        for axis, key in ((by_role, var.get("role") or "?"), (by_kind, var.get("kind") or "?")):
            d = axis.setdefault(key, {"variables": 0, "with_any_value": 0})
            d["variables"] += 1
            d["with_any_value"] += has
        using = [s for s in (var.get("studies_using") or []) if s]
        if using:
            per_study_denominator += 1
            seen = {(v.get("coordinate") or {}).get("study_id") for v in vals}
            if all(s in seen for s in using):
                per_study_ok += 1
        levels = var.get("levels") or []
        if levels:
            bound = {v.get("level_id") for v in vals if v.get("level_id")}
            k = sum(1 for l in levels if l.get("id") in bound)
            n_levels += len(levels)
            n_levels_with += k
            levels_rows.append({"variable_id": vid, "name": var.get("name"),
                                "levels_with_values": k, "levels_declared": len(levels)})
        if not has:
            missing.append({"variable_id": vid, "name": var.get("name"),
                            "role": var.get("role"), "kind": var.get("kind")})

    n_with_var = sum(1 for v in values if v.get("variable_id"))
    return {
        "variables": len(variables),
        "with_any_value": with_any,
        "share_with_any_value": _share(with_any, len(variables)),
        "with_value_in_every_declaring_study": (
            {"variables_naming_a_study": per_study_denominator, "n": per_study_ok,
             "share": _share(per_study_ok, per_study_denominator)}
            if per_study_denominator else
            {"not_computable": "no variable names a study in `studies_using`"}),
        "levels_with_values": (
            {"levels_declared": n_levels, "levels_with_values": n_levels_with,
             "share": _share(n_levels_with, n_levels),
             "level_bearing_variables": len(levels_rows), "by_variable": levels_rows}
            if n_levels else
            {"not_computable": "no variable declares any level"}),
        "splits": {"by_role": by_role, "by_kind": by_kind},
        "split_axis": "role and kind",
        "variables_with_no_value": missing,
        "values_total": len(values),
        "values_with_no_variable": len(values) - n_with_var,
        "share_values_with_no_variable": _share(len(values) - n_with_var, len(values)),
        "note": (
            "Denominator: the variables this account declares (pass 2), split by role "
            "and by kind. `with_any_value` counts a variable with at least one value "
            "bound to it; `with_value_in_every_declaring_study` counts a variable that "
            "has a value at every study its own `studies_using` names; "
            "`levels_with_values` counts declared levels carrying a value and is "
            "coverage OF THE DECLARATION, never a claim that the paper printed only "
            "those levels. The inverse -- values carrying no variable at all -- is "
            "printed beside them."),
        "problems": [],
    }


# --------------------------------------------------------------------------


#: The keys of a headline block that are not measures. `render_lines` and every
#: test that walks the block for a split must skip them by this one name.
NOT_A_MEASURE = ("problems", "code")


def headline(account: dict, text: str | None = None, doc: dict | None = None) -> dict:
    """The three measures, each with its tiers, its split and its denominator note.

    STAMPED WITH THE CODE THAT COMPUTED IT (`codestamp`). The stamp is what lets
    a stored headline FAIL: the two artifacts read in the D47 diagnosis were
    written by an older `coverage.py` and read 65 of 162 where this code reads
    120, and nothing on either file said which code had produced it.
    """
    doc = doc if doc is not None else (account.get("document") or {})
    out = {"table_cells_placed": table_cells_placed(account, doc),
           "statistic_sentences": statistic_sentences(account, text, doc),
           "declared_variables": declared_variables_with_values(account)}
    out["problems"] = [p for block in out.values() if isinstance(block, dict)
                       for p in (block.get("problems") or [])]
    out["code"] = _codestamp.stamp()
    return out


def for_rendering(account: dict, text: str | None = None) -> dict:
    """The headline block a renderer should print: RECOMPUTED from the account.

    A STORED HEADLINE IS NEVER TRUSTED. H1 and H3 are functions of the account
    alone and are recomputed here every time. H2 needs the paper's text, which
    the account does not carry; where the caller has it, it is recomputed too,
    and where it does not, the stored block is used ONLY if its stamp says this
    code wrote it. A stored block from other code is replaced by the reason it
    cannot be printed -- never by its numbers, and never by a zero.
    """
    doc = account.get("document") or {}
    fresh = headline(account, text, doc)
    stored = account.get("headline") or {}
    if text is None and stored:
        block = stored.get("statistic_sentences") or {}
        if _codestamp.is_current(stored.get("code")) and not block.get("not_computable"):
            fresh["statistic_sentences"] = block
        elif not _codestamp.is_current(stored.get("code")):
            fresh["statistic_sentences"] = {
                "not_computable": _codestamp.stale_note(stored.get("code"),
                                                        "the stored H2 block"),
                "stale_code": stored.get("code")}
        fresh["problems"] = [p for k, b in fresh.items()
                             if k not in NOT_A_MEASURE and isinstance(b, dict)
                             for p in (b.get("problems") or [])]
    return fresh


# --------------------------------------------------------------------------
# Rendering: section 0 of `account.md`
# --------------------------------------------------------------------------


#: Which key of a split holds its own denominator, per numerator.
_DEN = {"placed": "cells", "covered": "sentences"}


def _cell(s: Any) -> str:
    """A markdown table cell: a caption or label carrying a pipe would otherwise
    split the row and shift every number one column left."""
    return " ".join(str("" if s is None else s).replace("|", "\\|").split())


def _split_str(splits: dict[str, dict[str, int]], key: str) -> str:
    return ", ".join(f"{name.replace('_', ' ')} {d.get(key, 0)} of {d.get(_DEN[key], 0)}"
                     for name, d in sorted(splits.items())) or "no split available"


#: An account assembled before these measures existed has no `headline` at all.
#: It is rendered as not computable and named as such -- an absent measure is a
#: fact about the run, and printing it as a zero would be the false measurement
#: the `or 0` on wall time already was.
_NO_BLOCK = {"not_computable": "this account carries no headline block; it was "
                               "assembled before the measures existed"}


def render_lines(headline_block: dict) -> list[str]:
    """Section 0. THREE LINES, EACH CARRYING ITS OWN SPLIT -- a total printed
    without its breakdown is the defect this section exists to stop."""
    headline_block = headline_block or {}
    L: list[str] = ["## 0. Headline coverage", ""]
    # A BLOCK THIS CODE DID NOT WRITE PRINTS NO NUMBER. An empty block is a run
    # that never computed the measures and is rendered as not computable below;
    # a POPULATED block whose stamp is not this code is a claim about code the
    # tree does not contain, and printing its share as a share would be the
    # defect the stamp exists to catch.
    if headline_block and not _codestamp.is_current(headline_block.get("code")):
        L.append("**STALE.** " + _codestamp.stale_note(headline_block.get("code"),
                                                       "This headline block"))
        L.append("")
        return L
    L.append("The three measures a reader should judge this account by. Each is computed "
             "from the account and the document alone -- no model, no re-reading of the "
             "paper -- so it recomputes identically from disk. Every total is followed by "
             "its breakdown; the tiers under each measure partition its denominator "
             "exactly, so a number that moves has to come from somewhere.")
    L.append("")

    h1 = headline_block.get("table_cells_placed") or _NO_BLOCK
    if h1.get("not_computable"):
        L.append(f"**H1. Table cells placed:** not computable: {h1['not_computable']}")
    else:
        L.append(f"**H1. Table cells placed: {h1['placed']} of {h1['cells']} "
                 f"({h1['share_placed']})** -- of which corroborated "
                 f"{h1['placed_corroborated']}, model only {h1['placed_model_only']} -- "
                 f"by source: {_split_str(h1['splits'], 'placed')}.")
        L.append("")
        L.append("| tier | n | what it means |")
        L.append("|---|---:|---|")
        for tier, meaning in (
                ("placed", "a value was built from the cell and carries a declared variable id"),
                ("placed_corroborated", "-- and the name join checked that id (`agrees` or `join`)"),
                ("placed_model_only", "-- the model asserted the id and the name join could not check it"),
                ("read_unbound", "a value was built from the cell and carries no declared variable id, "
                                 "or the join disagrees with the one it carries"),
                ("unparsed", "the cell was read and did not parse under the reading's form"),
                ("unread", "no reading produced anything for this cell"),
                ("non_statistical", "the table is a codebook, not a result: its numbers are rating "
                                    "codes and were never anybody's to place (the cell stays in "
                                    "the denominator; the reason is printed per table below)")):
            n = h1["by_tier"].get(tier, h1["by_placed_subtier"].get(tier))
            L.append(f"| {tier} | {n} | {meaning} |")
        L.append("")
        L.append("Read unbound because: " + ", ".join(
            f"{k.replace('_', ' ')} {v}" for k, v in h1["read_unbound_because"].items()) + ".")
        L.append("")
        L.append("Tables by role: " + ", ".join(
            f"{r} {d['tables']} table(s), {d['cells']} cell(s)"
            for r, d in (h1.get("by_role") or {}).items()) + ".")
        L.append("")
        L.append("| table | source | role | cells with a numeral | placed (corroborated + model only) | "
                 "read unbound | unparsed | unread | non statistical |")
        L.append("|---|---|---|---:|---:|---:|---:|---:|---:|")
        for t in h1["by_table"]:
            L.append(f"| {_cell(t['table_id'])} {_cell(t.get('label'))} | {_cell(t['source'])} | "
                     f"{_cell(t.get('role'))} | {t['n_cells_with_a_numeral']} | {t['placed']} "
                     f"({t['placed_corroborated']} + {t['placed_model_only']}) | {t['read_unbound']} | "
                     f"{t['unparsed']} | {t['unread']} | {t.get('non_statistical', 0)} |")
        for t in h1["by_table"]:
            if t.get("role") != "unknown":
                L.append(f"- `{_cell(t['table_id'])}` role **{t['role']}**: {_cell(t.get('role_why'))}")
    L.append("")
    L.append(f"_{h1.get('note', '')}_" if h1.get("note") else "")
    L.append("")

    h2 = headline_block.get("statistic_sentences") or _NO_BLOCK
    if h2.get("not_computable"):
        L.append(f"**H2. Statistic-bearing sentences covered:** not computable: "
                 f"{h2['not_computable']}")
    else:
        L.append(f"**H2. Statistic-bearing sentences covered: {h2['covered']} of "
                 f"{h2['statistic_sentences']} ({h2['share_covered']})** -- by source: "
                 f"{_split_str(h2['splits'], 'covered')}.")
        L.append("")
        L.append(f"Tiers: covered {h2['by_tier']['covered']}, partial "
                 f"{h2['by_tier']['partial']}, uncovered {h2['by_tier']['uncovered']} "
                 f"(of which {h2['n_uncovered_with_no_numeral']} carry a statistical token "
                 f"and no numeral). Sentences read: {h2['sentences_read']}.")
        L.append("")
        L.append("| section role | statistic sentences | covered | partial | uncovered |")
        L.append("|---|---:|---:|---:|---:|")
        for role, d in sorted(h2["by_role"].items()):
            L.append(f"| {_cell(role)} | {d['sentences']} | {d['covered']} | {d['partial']} | "
                     f"{d['uncovered']} |")
    L.append("")
    L.append(f"_{h2.get('note', '')}_" if h2.get("note") else "")
    L.append("")

    h3 = headline_block.get("declared_variables") or _NO_BLOCK
    if h3.get("not_computable"):
        L.append(f"**H3. Declared variables with values:** not computable: "
                 f"{h3['not_computable']}")
    else:
        roles = h3["splits"]["by_role"]
        L.append(f"**H3. Declared variables with values: {h3['with_any_value']} of "
                 f"{h3['variables']} ({h3['share_with_any_value']})** -- by role: "
                 + ", ".join(f"{r} {d['with_any_value']} of {d['variables']}"
                             for r, d in sorted(roles.items())) + ".")
        L.append("")
        L.append("By kind: " + ", ".join(f"{k} {d['with_any_value']} of {d['variables']}"
                                         for k, d in sorted(h3["splits"]["by_kind"].items())) + ".")
        L.append("")
        ev = h3["with_value_in_every_declaring_study"]
        L.append("- With a value in every study its `studies_using` names: "
                 + (f"not computable: {ev['not_computable']}" if ev.get("not_computable")
                    else f"{ev['n']} of {ev['variables_naming_a_study']} ({ev['share']})"))
        lw = h3["levels_with_values"]
        L.append("- Declared levels carrying a value: "
                 + (f"not computable: {lw['not_computable']}" if lw.get("not_computable")
                    else f"{lw['levels_with_values']} of {lw['levels_declared']} "
                         f"({lw['share']}) across {lw['level_bearing_variables']} "
                         "level-bearing variable(s): "
                         + "; ".join(f"{_cell(r['name'])} {r['levels_with_values']} of "
                                     f"{r['levels_declared']}" for r in lw["by_variable"][:12])
                         + (" ..." if len(lw["by_variable"]) > 12 else "")))
        L.append(f"- Values carrying NO variable (the inverse): {h3['values_with_no_variable']} "
                 f"of {h3['values_total']} ({h3['share_values_with_no_variable']})")
    L.append("")
    L.append(f"_{h3.get('note', '')}_" if h3.get("note") else "")
    L.append("")
    for p in headline_block.get("problems") or []:
        L.append(f"- **CONSERVATION FAILURE** {p}")
    if headline_block.get("problems"):
        L.append("")
    return L
