"""What COULD have been checked, so coverage stops being measured against effort.

Every coverage number this pipeline has ever produced used a denominator of what
was attempted. `coverage_summary.stats_checked` is the model's count of what it
noticed; `tables_checked` lists the tables a `check_table` call was made against,
whether or not a single cell inside them ran. On 10.3390--jpm11060545 that read
`["Table 1", "Table 2", "Table 3"]` while 0 of 79 consumable cells received a
cell-level check.

A denominator of effort cannot distinguish a thorough run from a lazy one, and it
cannot show a regression: the prompt's own mandate to call `check_table` once per
table is honoured in a minority of archived runs, and no number anywhere fell
when it stopped being followed.

So this module computes the other denominator. It answers "how many cells in this
paper could a check have been run against", from the cells alone, with no model
in the loop, and it does so by asking the DISPATCHER -- not by restating its
rules, which is how the two drift apart.

Three nested populations, because collapsing them hides which problem you have:

  consumable  the cell kind is one some family routes to a check. The ceiling.
  routable    given the family AS CURRENTLY DECLARED (or undeclared), a check
              applies. A consumable cell that is not routable is waiting on a
              variable declaration.
  runnable    every required input is present too. A routable cell that is not
              runnable is waiting on an input -- overwhelmingly `n`.

`checked / consumable` is the honest coverage figure. The gap between them
decomposes into "needs a declaration", "needs an input", and "never submitted at
all", and those three call for completely different fixes.
"""
from __future__ import annotations

from collections import Counter

from .dispatch import (
    DISPATCH,
    DISPATCHABLE_KINDS,
    NEVER_DISPATCH,
    _build_args,
    _canonical_type,
    _drop_unbounded,
    _resolve_ambiguous,
    _specs,
    _variable_kwargs,
)
from .tools.celltypes import parse_cells

#: Cell kinds that SOME family routes to at least one check. Derived, never
#: listed: a kind whose every row is empty by decision is not consumable, and
#: nobody should have to remember to update a second list.
CONSUMABLE_KINDS = frozenset(
    kind for kind in DISPATCHABLE_KINDS
    if any(DISPATCH.get((kind, dt)) for (k, dt) in DISPATCH if k == kind)
)


def cell_census(
    cells: list[dict],
    variables: list[dict] | None = None,
    bindings: dict | None = None,
    table: str | None = None,
) -> list[dict]:
    """One record per cell: could a check have run, and if not, what is missing.

    Mirrors `dispatch.check_table`'s routing exactly -- same DISPATCH keys, same
    unbounded drop, same `_build_args` -- but runs no checks and reaches no
    verdict. It is a survey of the work, not the work.
    """
    parsed = parse_cells(cells)
    by_id = {v.get("id"): v for v in (variables or []) if isinstance(v, dict)}
    out: list[dict] = []

    for raw_cell, cell in zip(cells, parsed.get("cells") or []):
        row_label = cell.get("row_label") or raw_cell.get("row_label") or ""
        var = by_id.get((bindings or {}).get(row_label))
        # SAME ORDER AS check_table. `4.20 (1.15)` types `ambiguous` on its own
        # and becomes `mean_sd` once a family is declared, so a census that
        # skips this step undercounts exactly the cells a declaration would
        # unlock -- which is the number this module exists to report.
        cell = _resolve_ambiguous(cell, var)
        kind = cell.get("kind")
        dtype = _canonical_type(var)

        consumable = kind in CONSUMABLE_KINDS
        # An `X (Y)` cell types `ambiguous` with no family declared, and a
        # declaration turns it into `mean_sd`. Such a cell is one declaration
        # away from being checkable, so excluding it from the denominator would
        # hide the single largest thing a declaration buys. Whether a given
        # ambiguous cell is resolvable is decided by ASKING the resolver against
        # each family, not by assuming -- `_resolve_ambiguous` declines some
        # readings outright (an n (%) reading needs an integer count and a
        # percentage in range).
        resolvable_by_declaration = False
        if not consumable and kind == "ambiguous":
            resolvable_by_declaration = any(
                _resolve_ambiguous(dict(cell), {"family": fam}).get("kind")
                in CONSUMABLE_KINDS
                for fam in ("likert_item", "count", "binary", "continuous", "proportion")
            )
            consumable = resolvable_by_declaration

        entry = {
            "table": table,
            "row": raw_cell.get("row"),
            "row_label": row_label,
            "raw": raw_cell.get("raw"),
            "kind": kind,
            "data_type": dtype,
            "consumable": consumable,
            "routable": False,
            "runnable": False,
            "tools": [],
            "missing": [],
        }
        if resolvable_by_declaration:
            entry["missing"] = [
                "a variable declaration: this cell reads as 'X (Y)' and its meaning is "
                "ambiguous until the variable's family says whether Y is an SD, an SE, "
                "a percentage or an interval"
            ]
            out.append(entry)
            continue
        if not consumable:
            entry["missing"] = ["not a checkable cell kind: "
                                + NEVER_DISPATCH.get(kind, str(kind))]
            out.append(entry)
            continue

        tools = DISPATCH.get((kind, dtype)) or ()
        if tools:
            tools, _refused = _drop_unbounded(tools, var)
        if not tools:
            entry["missing"] = (
                ["a variable declaration: this kind is checkable but nothing routes "
                 f"it at data_type={dtype!r}"]
                if dtype == "unknown" else
                [f"no check applies to a {kind} cell on {dtype} data"]
            )
            out.append(entry)
            continue

        entry["routable"] = True
        entry["tools"] = list(tools)

        base = dict(_variable_kwargs(var))
        base.update({k: v for k, v in cell.items()
                     if k in ("value", "sd", "se", "percent", "count", "low", "high")})
        n = raw_cell.get("n") or (var or {}).get("n")
        runnable, missing = [], set()
        for name in tools:
            spec = _specs().get(name)
            if spec is None:
                continue
            if _build_args(spec, cell, base, n) is not None:
                runnable.append(name)
            elif any(p.name == "n" and p.required for p in spec.params) and n is None:
                missing.add("n")
            else:
                missing.add("a required input")
        entry["runnable"] = bool(runnable)
        entry["tools"] = runnable or entry["tools"]
        entry["missing"] = sorted(missing)
        out.append(entry)
    return out


def summarise(entries: list[dict], n_checked: int | None = None) -> dict:
    """Coverage against the checkable surface, with the gap decomposed.

    `n_checked` is how many cells a run actually submitted to a check. Left None
    when no run is being scored, so the census can be reported on its own as
    "here is the work" before anything is attempted.
    """
    consumable = [e for e in entries if e["consumable"]]
    routable = [e for e in consumable if e["routable"]]
    runnable = [e for e in routable if e["runnable"]]

    blocked_on_declaration = len(consumable) - len(routable)
    blocked_on_input = len(routable) - len(runnable)
    # Tallied over the cells actually blocked on an INPUT. Counting it over
    # every consumable cell folded the declaration message into the input line
    # and reported the same cell under two headings.
    missing = Counter(
        m for e in routable if not e["runnable"] for m in e["missing"]
    )

    out = {
        # NO CELLS AT ALL IS NOT A CENSUS OF ZERO, and until 2026-08-18 the
        # return said nothing to separate them.
        #
        # Every count below comes out 0 for an empty `entries`, and the viewer
        # renders that as an audited census -- "cells extracted from the tables:
        # 0" -- which a reader takes as a fact about the PAPER. It is equally
        # the shape of a paper whose tables were never enumerated, an extraction
        # that failed, or a caller that passed an empty list.
        #
        # `n_cells: 0` is kept (removing it would break every consumer) and
        # `no_cells_examined` is added beside it, so a branch on the difference
        # is possible without reading prose. Same fix as `tables_note` on
        # `extract_text_with_tables`, and the same reason: an observed zero and
        # an unasked question must not be spelled identically.
        "no_cells_examined": not entries,
        "n_cells": len(entries),
        "n_consumable": len(consumable),
        "n_routable": len(routable),
        "n_runnable": len(runnable),
        "blocked_on_declaration": blocked_on_declaration,
        "blocked_on_input": blocked_on_input,
        "by_kind": dict(Counter(e["kind"] for e in consumable)),
        "missing_inputs": dict(missing.most_common()),
    }
    if not entries:
        out["note"] = (
            "NO TABLE CELLS WERE EXAMINED, so every count here is 0 because "
            "there was nothing to count -- not because the paper's tables were "
            "found to hold nothing. Whether this paper has checkable cells is "
            "UNKNOWN from this census alone."
        )
    if n_checked is not None:
        out["n_checked"] = n_checked
        # A RATIO ONLY WHILE BOTH COUNTS DESCRIBE THE SAME POPULATION. The
        # denominator is this census -- the cells in the paper's XML tables.
        # The numerator is what the run submitted, and a run may legitimately
        # submit cells from outside those tables: the s11031 review assembled
        # two of its four "tables" out of means printed in the prose, which the
        # census cannot see. MEASURED there, 2026-08-12: 28 cells checked
        # against 24 surveyed, which as a percentage reads `117%`.
        #
        # A coverage figure over 100% is our accounting failure printed as the
        # paper's number, and capping it at 100% would be the same failure made
        # invisible -- it would assert that every surveyed cell was checked,
        # which is not established and here is not true (16 of the 24 were).
        # So the ratio is withheld and both counts are stated, which is what we
        # actually know. Same rule, one rung up, as `predictor_disagrees`.
        outside = n_checked - len(consumable) if consumable else 0
        if outside > 0:
            out["coverage"] = None
            out["checked_outside_census"] = outside
            out["census_undercounts"] = {
                "n_consumable": len(consumable),
                "n_checked": n_checked,
                "note": (
                    f"{n_checked} distinct cells were checked and this census "
                    f"surveyed {len(consumable)} checkable cells, so at least "
                    f"{outside} of the cells checked came from outside the tables "
                    "it walked -- values read out of the prose and submitted as a "
                    "table, a supplement, or a table only the PDF carries. No "
                    "percentage of one population against the other is stated, and "
                    "this does NOT mean every surveyed cell was checked."),
            }
        else:
            out["coverage"] = (n_checked / len(consumable)) if consumable else None

        # `n_runnable` IS A PREDICTION, AND IT CAN BE WRONG. Everything above is
        # computed statically, by asking whether `_build_args` can assemble a
        # call FROM THE CELL ALONE. `check_table` does not work that way: it
        # takes the denominator from the table's own header and section, so it
        # runs on cells this census has already written off.
        #
        # MEASURED on 10.1002--eat.24415 (2026-08-11): the census predicted
        # `n_runnable: 0` and the run checked 21. Greg read the rendered line
        # "21 of 110 checkable cells were checked" beside "104 are waiting on an
        # input: n" and asked, reasonably, which was true.
        #
        # The old `max(0, ...)` clamped the difference to zero and the
        # disagreement vanished. A predictor that is wrong by 21 cells is a
        # fact about OUR census, and burying it is the house defect: our own
        # limitation, reported as though it were settled. It is now recorded.
        shortfall = len(runnable) - n_checked
        out["never_submitted"] = max(0, shortfall)
        if shortfall < 0:
            out["predictor_disagrees"] = {
                "predicted_runnable": len(runnable),
                "actually_checked": n_checked,
                "note": (
                    f"The static census predicted {len(runnable)} cell(s) could "
                    f"run, and the run checked {n_checked}. The prediction is "
                    "the thing that is wrong: it asks whether a call can be "
                    "built from the cell alone, while `check_table` supplies "
                    "denominators from the table header and section. Read "
                    "`n_checked` as the fact and `n_runnable` as a LOWER BOUND "
                    "on what was possible."),
            }
    return out


def render(summary: dict) -> str:
    """One paragraph a reader can act on. Silence is not a pass."""
    if not summary.get("n_consumable"):
        return ("Coverage: no table cell in this paper is of a kind any check "
                "consumes, so nothing was checkable. This is a statement about "
                "the tables, not a clean result.")
    lines = []
    if summary.get("census_undercounts"):
        lines.append("Coverage cannot be stated as a fraction on this run. "
                     + summary["census_undercounts"]["note"])
    elif summary.get("coverage") is not None:
        lines.append(
            f"Coverage: {summary['n_checked']} of {summary['n_consumable']} checkable "
            f"cells were checked ({summary['coverage']:.0%})."
        )
    else:
        lines.append(f"{summary['n_consumable']} of {summary['n_cells']} cells are "
                     f"of a checkable kind.")
    # THE OTHER TWO POPULATIONS, IN THE PROSE. `_checkable_coverage` counts
    # batch rows and per-value calls precisely because a report once printed
    # "**NOTHING IN THE TABLES WAS CHECKED.**" on runs that had made 125, 122
    # and 14 cell-consuming calls. The counters were added; this sentence was
    # not, so the denial simply moved from bold text into a percentage.
    #
    # MEASURED 2026-09-03 on the archived parallel runs: apple_cider renders
    # "0 of 168 checkable cells were checked (0%)" beside 47 per-value calls
    # and 39 findings, and airforce "0 of 33" beside 37 calls. Both are true
    # of the `check_table` path and false as a summary of the run.
    #
    # They are NOT summed into the fraction: a batch tool reports rows and a
    # per-value tool reports calls, neither returns census cell ids, and a
    # union of the three would be invented. Saying what the fraction covers,
    # and what else ran, is the honest version.
    other = []
    if summary.get("rows_checked_by_batch_tools"):
        other.append(f"{summary['rows_checked_by_batch_tools']} row(s) through "
                     f"batch tools")
    if summary.get("direct_check_calls"):
        other.append(f"{summary['direct_check_calls']} per-value call(s)")
    if other and summary.get("n_checked") is not None:
        lines.append(
            "That fraction counts the `check_table` path only. This run also "
            "ran " + " and ".join(other) + " against the paper's own numbers. "
            "Those return no census cell ids, so they cannot be added to the "
            "fraction without inventing a union -- but the tables were not "
            "left unchecked.")
    if summary["blocked_on_declaration"]:
        lines.append(f"{summary['blocked_on_declaration']} are waiting on a variable "
                     f"declaration (what kind of quantity is this?).")
    if summary["blocked_on_input"]:
        miss = ", ".join(f"{k} ({v})" for k, v in summary["missing_inputs"].items())
        lines.append(f"{summary['blocked_on_input']} are waiting on an input: {miss}.")
    if summary.get("never_submitted"):
        lines.append(f"{summary['never_submitted']} could have run as they stand and "
                     f"were never submitted to a check.")
    # THE PREDICTOR'S OWN DISAGREEMENT, SAID OUT LOUD. `_summarise` records it
    # and the comment there says "It is now recorded" -- recorded, and read by
    # nothing. `never_submitted` is clamped at zero, so a NEGATIVE shortfall
    # left no trace in the prose at all, and the reader got an arithmetic
    # impossibility instead: "8 of 24 checkable cells were checked. 24 are
    # waiting on a variable declaration" -- 32 out of 24, from a real shipped
    # report.
    #
    # It goes LAST and it names itself as our defect, because a reader who has
    # just been handed numbers that do not add up needs the explanation in the
    # same breath, not in a JSON field beside it.
    if summary.get("predictor_disagrees"):
        d = summary["predictor_disagrees"]
        lines.append(
            f"These counts do not add up, and the fault is ours: the static "
            f"census predicted {d.get('predicted_runnable')} cell(s) could run "
            f"while the run checked {d.get('actually_checked')}. Read the "
            f"checked count as the fact and the census as a LOWER BOUND -- it "
            f"asks whether a call can be built from a cell alone, and "
            f"`check_table` supplies denominators the cell does not carry.")
    return " ".join(lines)
