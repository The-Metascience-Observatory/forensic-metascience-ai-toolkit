"""GRIM on every mean and percentage cell, aimed by the harness, not the model.

WHY THIS EXISTS. Measured 2026-10-18 on the dev half of the GRIM ground truth
(`benchmarks/grim/literature_2026-10`, Sonnet, `tools_only`): of 135 printed
values that published critics showed to be GRIM-inconsistent, the tools agent
checked 38 -- and flagged every one it checked. The misses were never tested.
On Shaaban 2012 it checked 7 of roughly 180 percentages and stopped. A check
whose targets can be enumerated from the paper must not depend on which targets
a model chose (`prepass.py` makes the same argument for duplication).

WHAT THE HARNESS CAN AND CANNOT ESTABLISH ON ITS OWN. GRIM needs two premises
per cell, and only one of them is ever readable off the table:

  * n. Printed in the cell (`12/30`), in the column header (`CON (n = 62)`), in
    a header row the publisher put in the body (Cureus), or in the row label.
    `column_ns` / `cell_n` read those. An n printed only in Table 1 or the
    Results prose ("The consultants were 41 ... and 25") has to be DECLARED.
  * the integer premise: that the value is a share of n whole units, or a mean
    of n integer responses. Deterministic only for a printed `n (%)` or
    `k/n (%)` cell, where the count IS the share. A bare `46.3` under "%" can
    be a share of respondents or a mean percentage of something continuous
    (HbA1c, oxygen saturation); a `3.48 (1.2)` can be a single 1-9 item or an
    averaged subscale, which Kelly's PCIT survey shows is the commonest false
    alarm in this whole family. Greg's rule for the family is "guilty until
    proven innocent", so those cells run only on a DECLARATION: a variable
    bound to the row, or a table-level statement that bare numbers are shares.

A TARGET WHOSE PREMISES ARE ABSENT IS SKIPPED AND COUNTED, never run on an
invented premise -- the rule `prepass.py` states for every sweep.

NON-RESPONSE. A column header's n is the group size, and a row can have fewer
observations. `jats.py` records what ignoring that cost: two false accusations
on honest papers from a column n applied to rows with missing data. So a cell
inconsistent at a header or declared n is re-tested at every n within
`dispatch._LONE_DENOM_MAX_GAP` below it, and one that some smaller n explains is
reported as `explained_by_nonresponse`, not as a failure. A denominator printed
in the cell itself leaves nothing to explain.
"""
from __future__ import annotations

import math
import re
from typing import Any

#: Where a cell's n came from. Each verdict names its source so a reader can
#: tell a printed denominator from a header group size from a model's
#: declaration, which are not equally strong.
N_SOURCES = ("cell", "header", "header_row", "row_label", "declared")

#: Sources whose n is a group size rather than this cell's own denominator, so
#: a failure there is re-tested against item non-response.
_GROUP_SIZE_SOURCES = frozenset({"header", "header_row", "row_label", "declared"})

#: Families whose numbers in a table are shares of the units (anatomy names).
_SHARE_FAMILIES = frozenset({"binary", "nominal_category", "ordinal_category",
                             "proportion"})

#: Data types whose MEAN is a mean of integers (`Variable.forensic_kwargs`).
_INTEGER_MEAN_TYPES = frozenset({"likert", "integer", "count"})

#: Kinds that are never a GRIM target.
_SKIP_KINDS = frozenset({"non_numeric", "censored", "reference_category",
                         "median_iqr", "median_range", "estimate_ci"})

_PERCENT_LABEL = re.compile(r"%|\bper\s*cent\b|\bpercent(age)?s?\b", re.I)
_MEAN_LABEL = re.compile(r"\bmeans?\b|^\s*m\s*$|\bavg\b|\baverage\b", re.I)

#: A column of test statistics or p-values. `0.42 (0.52)` under "F-test (P
#: value)" types exactly like a mean (SD), and a table-wide variable declaration
#: would otherwise hand it to GRIM as a mean of the declared item.
_STAT_COLUMN = re.compile(
    r"\b(?:f|t|z|u|h|w)\s*-?\s*(?:test|stat\w*|value)\b|\bp\s*-?\s*values?\b|"
    r"^\s*(?:f|t|z|p|r|r2|\u03c7\s*2|chi.?square\w*)\s*$|\bchi.?square|\bsignificance\b",
    re.I)


def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def table_key(index: int) -> str:
    """The id a declaration uses for the `index`-th table (1-based) of
    `prepass.paper_tables(paper_dir, include_supplements=True)`.

    A position, not a label, because a docling table's label was the stringified
    caption reference (`cref='#/texts/49'`) until 2026-10-18 and still is in
    every older cache, and several labels repeat across supplements."""
    return f"T{index}"


def match_declaration(declarations: list[dict] | None, index: int,
                      table: dict) -> dict | None:
    """The declaration for this table: by `table_key`, else by a label that
    names exactly this table. Later declarations replace earlier ones -- the
    model may re-declare after reading a result."""
    found = None
    label = _norm(table.get("label"))
    for d in declarations or []:
        if not isinstance(d, dict):
            continue
        ref = d.get("table")
        if ref is None:
            continue
        if str(ref).strip().upper() == table_key(index) or ref == index:
            found = d
        elif label and _norm(ref) == label and not label.startswith("cref"):
            found = d
    return found


def _col_matches(ref: Any, cell_col: Any, col_label: Any) -> bool:
    if isinstance(ref, int) or (isinstance(ref, str) and ref.strip().isdigit()):
        return cell_col is not None and int(ref) == int(cell_col)
    want = _norm(ref)
    if not want:
        return False
    if want == _norm(col_label):
        return True
    # The innermost level of a stacked header names the column, but a model
    # quoting "Uni. staff" for "Consultant | Uni. staff" means only the column
    # under Consultant if it says so; a bare innermost name matching several
    # columns is ambiguous and `column_ns` refuses it.
    return False


def _header_row_ns(table: dict) -> dict[int, int]:
    """Column n's printed in BODY rows above the first numeric row.

    `jats.py` deliberately never promotes such a row to the header ("that guess
    would rename every value's column"), and that stays true: this only READS
    the n each such cell states, keyed by physical column, and renames nothing.
    Cureus prints `Group 1 (n=70)` in `<tbody>` with no `<thead>`."""
    from .dispatch import header_ns

    by_row: dict[Any, list[dict]] = {}
    for c in table.get("cells") or []:
        by_row.setdefault(c.get("row"), []).append(c)
    out: dict[int, int] = {}
    for row in sorted(r for r in by_row if r is not None):
        cells = by_row[row]
        texts = [str(c.get("raw") or "") for c in cells]
        has_n = {c.get("col"): header_ns(c.get("raw")) for c in cells}
        if any(has_n.values()):
            for col, hits in has_n.items():
                if hits and col is not None:
                    out[int(col)] = hits[0]["n"]
            continue
        # The first row carrying a number that is not an n statement ends the
        # header region.
        if any(re.search(r"\d", t) for t in texts[1:]):
            break
    return out


def column_ns(table: dict, declaration: dict | None = None) -> dict[int, dict]:
    """`{physical col: {"n", "source", "text"} | {"n": None, "why"}}`.

    Header first (innermost level only -- a grouping header's n covers several
    columns), then an n printed in a leading body row, then a declaration. Two
    sources that disagree give NO n, with the disagreement recorded: picking one
    is how the wrong n reaches an accusation."""
    from .dispatch import header_ns

    labels: dict[int, str] = {}
    for c in table.get("cells") or []:
        if c.get("col") is not None and c.get("col_label") is not None:
            labels.setdefault(int(c["col"]), str(c["col_label"]))
    in_body = _header_row_ns(table)
    declared: dict[int, dict] = {}
    for item in (declaration or {}).get("columns") or []:
        if not isinstance(item, dict) or item.get("n") is None:
            continue
        hits = [col for col, lab in labels.items()
                if _col_matches(item.get("col"), col, lab)]
        if len(hits) == 1:
            declared[hits[0]] = item
    out: dict[int, dict] = {}
    for col in sorted(set(labels) | set(in_body) | set(declared)):
        cands: list[tuple[int, str, str]] = []
        column_level = [h for h in header_ns(labels.get(col)) if h["level"] == "column"]
        if column_level:
            cands.append((column_level[0]["n"], "header", labels.get(col, "")))
        if col in in_body:
            cands.append((in_body[col], "header_row", f"n = {in_body[col]}"))
        if col in declared:
            try:
                cands.append((int(declared[col]["n"]), "declared",
                              str(declared[col].get("quote") or "")))
            except (TypeError, ValueError):
                pass
        if not cands:
            continue
        values = {n for n, _, _ in cands}
        if len(values) > 1:
            out[col] = {"n": None, "why": "column n sources disagree: " + "; ".join(
                f"{src} says {n}" for n, src, _ in cands)}
            continue
        n, src, text = cands[0]
        out[col] = {"n": n, "source": src, "text": text,
                    "also": [s for _, s, _ in cands[1:]]}
    return out


def cell_n(cell: dict, columns: dict[int, dict]) -> dict:
    """This cell's n and where it came from, or `{"n": None, "why"}`."""
    from .dispatch import header_ns

    if cell.get("kind") == "count_denominator_percent" and cell.get("denominator"):
        return {"n": int(cell["denominator"]), "source": "cell",
                "text": str(cell.get("raw") or "")}
    col = columns.get(int(cell["col"])) if cell.get("col") is not None else None
    row_hits = header_ns(cell.get("row_label"))
    row = {"n": row_hits[0]["n"], "source": "row_label",
           "text": str(cell.get("row_label"))} if row_hits else None
    if col and col.get("n") is None:
        return {"n": None, "why": col["why"]}
    if col and row and col["n"] != row["n"]:
        # A row-label n beside a column n is usually the row's total across the
        # columns; neither is safely this cell's denominator.
        return {"n": None, "why": (f"the column says n = {col['n']} and the row "
                                   f"label says n = {row['n']}")}
    if col:
        return col
    if row:
        return row
    return {"n": None, "why": "no n printed in the cell, its column header or "
                              "its row label, and none declared"}


def _variable_for(cell: dict, declaration: dict | None,
                  by_id: dict[str, dict]) -> dict | None:
    decl = declaration or {}
    full = str(cell.get("row_label") or "")
    # A stacked row label carries its section ("Demographics | Age"); the model
    # names the row as printed on its own line.
    labels = {_norm(full), _norm(full.split(" | ")[-1])} - {""}
    for item in decl.get("rows") or []:
        if isinstance(item, dict) and _norm(item.get("row")) in labels:
            return by_id.get(str(item.get("variable_id")))
    vid = decl.get("default_variable_id")
    return by_id.get(str(vid)) if vid else None


def _decimals(x: Any) -> int | None:
    try:
        return int(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _column_kind(cell: dict, declaration: dict | None) -> str | None:
    for item in (declaration or {}).get("columns") or []:
        if isinstance(item, dict) and item.get("kind") and _col_matches(
                item.get("col"), cell.get("col"), cell.get("col_label")):
            return str(item["kind"])
    return None


def target_of(cell: dict, table: dict, declaration: dict | None,
              by_id: dict[str, dict]) -> dict:
    """What GRIM question this cell poses, or `{"refused": reason}`.

    Returns `{"what": "percent"|"mean", "value", "decimals", "premise", ...}`.
    `premise` says how the integer premise was established: `printed_count`
    (an n (%) cell -- the count is the share), `declared_share` /
    `declared_variable` (a declaration), never a guess."""
    from .dispatch import _resolve_ambiguous, _variable_kwargs

    kind = cell.get("kind")
    if kind in _SKIP_KINDS:
        return {"refused": f"kind {kind} is not a GRIM target", "silent": True}
    col_label = str(cell.get("col_label") or "")
    if _STAT_COLUMN.search(col_label.split(" | ")[-1]) or _STAT_COLUMN.search(col_label):
        return {"refused": "test-statistic or p-value column", "silent": True}
    from .prepass import reports_model_output
    why = reports_model_output(cell.get("col_label"), table.get("caption"))
    if why:
        return {"refused": "model output, not a descriptive statistic: " + why}
    var = _variable_for(cell, declaration, by_id)
    declared_kind = _column_kind(cell, declaration)
    if declared_kind and declared_kind not in ("percent", "mean"):
        return {"refused": f"declared column kind {declared_kind}", "silent": True}

    if kind in ("n_percent", "count_denominator_percent"):
        if cell.get("percent") is None:
            return {"refused": "n (%) cell without a readable percentage"}
        return {"what": "percent", "value": float(cell["percent"]),
                "decimals": _decimals(cell.get("decimals_percent")),
                "count": cell.get("count"), "premise": "printed_count"}

    if kind == "ambiguous" and var:
        cell = _resolve_ambiguous(dict(cell), var)
        kind = cell.get("kind")
        if kind == "n_percent" and cell.get("percent") is not None:
            return {"what": "percent", "value": float(cell["percent"]),
                    "decimals": _decimals(cell.get("decimals_percent"))
                    if cell.get("decimals_percent") is not None
                    else _decimals_of(cell.get("raw"), 1),
                    "count": cell.get("count"), "premise": "declared_variable",
                    "variable_id": var.get("id")}
    if kind == "ambiguous":
        return {"refused": "ambiguous cell (mean (SD) or n (%)?) and no "
                           "variable declared for its row"}

    if kind in ("numeric", "count"):
        value = cell.get("value")
        if value is None:
            return {"refused": "no value"}
        is_share = (bool((declaration or {}).get("percent_of_units"))
                    or declared_kind == "percent"
                    or bool(var and var.get("family") in _SHARE_FAMILIES))
        looks_percent = bool(_PERCENT_LABEL.search(str(cell.get("col_label") or ""))
                             or _PERCENT_LABEL.search(str(cell.get("row_label") or "")))
        if is_share and declared_kind != "mean":
            if not 0.0 <= float(value) <= 100.0:
                return {"refused": f"declared a percentage but {value} is outside 0-100"}
            return {"what": "percent", "value": float(value),
                    "decimals": _decimals(cell.get("decimals_value")) or 0,
                    "premise": "declared_share",
                    "variable_id": (var or {}).get("id")}
        is_mean = declared_kind == "mean" or bool(
            _MEAN_LABEL.search(str(cell.get("col_label") or "")))
        if is_mean and var:
            return _mean_target(float(value), cell.get("decimals_value"), var,
                                _variable_kwargs(var))
        if looks_percent:
            return {"refused": "a bare number under a % label: a share of the "
                               "units or a percentage-valued measurement? Needs "
                               "a declaration"}
        if _PERCENT_LABEL.search(str(table.get("caption") or "")) and 0 <= float(value) <= 100:
            # Counted, not silent: a caption saying "%" over a grid of bare
            # numbers is the Cureus and Shaaban shape, and an uncounted refusal
            # there is a coverage gap nobody sees.
            return {"refused": "a bare number in a table whose caption mentions "
                               "percentages: needs a declaration"}
        if is_mean:
            return {"refused": "a mean with no variable declared for its row"}
        return {"refused": "bare number, not marked as a mean or a percentage",
                "silent": True}

    if kind in ("mean_sd", "mean_se"):
        if not var:
            return {"refused": "a mean with no variable declared for its row"}
        return _mean_target(float(cell["value"]), cell.get("decimals_value"), var,
                            _variable_kwargs(var))
    return {"refused": f"kind {kind} not handled", "silent": True}


def _decimals_of(raw: Any, which: int) -> int | None:
    nums = re.findall(r"\d+(?:\.(\d+))?", str(raw or ""))
    if len(nums) <= which:
        return None
    return len(nums[which] or "")


def _mean_target(value: float, decimals: Any, var: dict, kwargs: dict) -> dict:
    from .dispatch import _composite_reason, _is_composite

    if _is_composite(var) and not kwargs.get("items"):
        return {"refused": _composite_reason(var)}
    dtype = kwargs.get("data_type")
    if dtype not in _INTEGER_MEAN_TYPES:
        return {"refused": f"variable {var.get('id')!r} is {dtype}, not integer-valued"}
    return {"what": "mean", "value": value, "decimals": _decimals(decimals),
            "premise": "declared_variable", "variable_id": var.get("id"),
            "items": int(kwargs.get("items") or 1),
            "data_type": dtype,
            "discreteness_source": kwargs.get("discreteness_source")}


def _consistent(target: dict, n: int) -> tuple[bool, dict]:
    from .tools.grim import grim_test, grim_test_percentage

    if target["what"] == "percent":
        res = grim_test_percentage(target["value"], n, decimals=target["decimals"],
                                   data_type="proportion")
    else:
        res = grim_test(target["value"], n * target.get("items", 1),
                        scale_min=None, scale_max=None,
                        decimals=target["decimals"] if target["decimals"] is not None else 2,
                        data_type=target.get("data_type") or "integer",
                        bound_source="assumed",
                        discreteness_source=target.get("discreteness_source") or "assumed")
    if not res.get("applicable", True) or res.get("error"):
        return True, res
    return bool(res.get("consistent")), res


def _rounds_to(exact: float, printed: float, decimals: int) -> bool:
    """Does `exact` print as `printed` at `decimals`, rounding half either way?"""
    unit = 10.0 ** -decimals
    return abs(exact - printed) <= unit / 2 + 1e-9


def check_cell(target: dict, n_info: dict) -> dict:
    """One verdict: `consistent`, `inconsistent`, `explained_by_nonresponse` or
    `refused`, with the GRIM result and, for a failure, the smaller n's tried."""
    from .dispatch import _LONE_DENOM_MAX_GAP

    n = n_info.get("n")
    if n is None:
        return {"status": "refused", "why": n_info.get("why")}
    if n < 2:
        return {"status": "refused", "why": f"n = {n}"}
    if target.get("decimals") is None:
        return {"status": "refused", "why": "printed precision unknown"}
    ok, res = _consistent(target, n)
    if res.get("error") or not res.get("applicable", True):
        return {"status": "refused", "why": res.get("error") or "not applicable"}
    out = {"status": "consistent" if ok else "inconsistent", "n": n,
           "n_source": n_info.get("source"), "severity": res.get("severity"),
           "failure_mode": res.get("failure_mode")}
    if ok:
        return out
    if res.get("failure_mode") in ("rounding_convention", "no_discriminating_power"):
        # Fails round-half, passes truncation: a house style (SPSS truncates),
        # counted per paper and never filed -- the GRIM tools' own rule. When
        # truncation rescues EVERY failure at this n and precision the tool
        # calls it undecidable (`no_discriminating_power`); same treatment.
        out["status"] = "rounding_only"
        return out
    if target["what"] == "percent" and res.get("passes_under_truncation"):
        out["passes_under_truncation"] = True
    if n_info.get("source") in _GROUP_SIZE_SOURCES:
        lo = max(2, math.ceil(n * (1 - _LONE_DENOM_MAX_GAP)))
        # A PRINTED COUNT STAYS FIXED. Non-response shrinks the denominator,
        # not the count the paper printed: "41 (58%)" at n = 70 is not
        # explained by 40/69, which is a different row. With k printed, only
        # k/m for a smaller m can rescue the percentage.
        count = target.get("count") if target["what"] == "percent" else None
        if isinstance(count, int):
            smaller = [m for m in range(n - 1, max(lo, count) - 1, -1)
                       if _rounds_to(100.0 * count / m, target["value"],
                                     target["decimals"])]
        else:
            smaller = [m for m in range(n - 1, lo - 1, -1)
                       if _consistent(target, m)[0]]
        out["tried_n"] = [lo, n - 1] if lo <= n - 1 else []
        if smaller:
            out["status"] = "explained_by_nonresponse"
            out["consistent_at_n"] = smaller[0]
    out["possible_nearby"] = (res.get("possible_percentages_nearby")
                              or res.get("possible_means_nearby"))
    return out


def sparse_rows(table: dict) -> set:
    """Rows printing fewer than half the numbers a typical row of this table
    prints.

    A PDF row whose values span several subcolumns ("Highest order CS
    performed" on Shaaban 2012: one value per rank, printed across that rank's
    three subcolumns) comes out of docling with each value under the FIRST
    subcolumn. Every value then inherits that subcolumn's n, which is the wrong
    n -- and on that table it produced six GRIM failures on values the paper
    printed correctly. Nothing in the cells says the placement is wrong; the
    row's sparseness against its neighbours is the only signal."""
    counts: dict[Any, int] = {}
    for c in table.get("cells") or []:
        if c.get("row") is None or not re.search(r"\d", str(c.get("raw") or "")):
            continue
        if str(c.get("raw") or "").strip() == str(c.get("row_label") or "").strip():
            continue
        counts[c["row"]] = counts.get(c["row"], 0) + 1
    if len(counts) < 3:
        return set()
    typical = sorted(counts.values())[len(counts) // 2]
    return {r for r, k in counts.items() if k * 2 < typical}


def sweep_grim(tables: list[dict], declarations: list[dict] | None = None,
               variables: list[dict] | None = None,
               paper_text: str | None = None) -> dict:
    """GRIM over every eligible cell of every table, with full coverage counts.

    `tables` is `prepass.paper_tables(paper_dir, include_supplements=True)`;
    each declaration names its table by `table_key` (`T1`, `T2`, ...).

    Counts, never only results: `enumerated` (cells posing a GRIM question or
    refused for a stated reason), `checked`, and `refused` by reason -- so "no
    failure" is distinguishable from "nothing was checkable"."""
    from .prepass import _typed

    out: dict[str, Any] = {
        "tool": "grim_sweep_harness", "n_tables": len(tables or []),
        "enumerated": 0, "checked": 0, "consistent": 0, "inconsistent": 0,
        "explained_by_nonresponse": 0, "rounding_only": 0,
        "refused": {}, "n_by_source": {},
        "premise_by_source": {}, "tables": [], "failures": [],
        # EVERY checked cell, compactly, passes included: a cell that passed
        # is a fact a scorer (benchmarks/grim/score.py) and a reader need, and
        # `failures` alone cannot tell "checked and consistent" from "never
        # reached".
        "checked_cells": [],
    }
    if paper_text:
        from .survey_design import declares_complex_survey
        survey = declares_complex_survey(paper_text)
        if survey:
            # A weighted percentage or mean is not k/n. Refused as a whole and
            # SAID, rather than run and left to accuse a weighted estimate.
            out["refused_whole_paper"] = (
                "the paper declares a complex survey design, so its percentages "
                f"and means are weighted, not k/n: {survey['quote']!r}")
            return out
    by_id = {str(v.get("id")): v for v in (variables or []) if isinstance(v, dict)}

    def bump(key: str, sub: str) -> None:
        out[key][sub] = out[key].get(sub, 0) + 1

    for i, table in enumerate(tables or [], start=1):
        decl = match_declaration(declarations, i, table)
        columns = column_ns(table, decl)
        # Only matters where columns carry DIFFERENT n's: a value under the
        # wrong column of a single-n table still meets its own n.
        sparse = (sparse_rows(table)
                  if len({v.get("n") for v in columns.values()}) > 1 else set())
        row = {"table": table_key(i), "label": table.get("label"),
               "declared": decl is not None, "checked": 0, "inconsistent": 0,
               "explained_by_nonresponse": 0, "rounding_only": 0, "refused": 0,
               "column_n": {str(c): {k: v for k, v in info.items() if k != "also"}
                            for c, info in columns.items()}}
        for cell in _typed(table.get("cells") or []):
            target = target_of(cell, table, decl, by_id)
            if target.get("refused"):
                if not target.get("silent"):
                    out["enumerated"] += 1
                    row["refused"] += 1
                    bump("refused", target["refused"].split(":")[0])
                continue
            out["enumerated"] += 1
            if cell.get("row") in sparse:
                row["refused"] += 1
                bump("refused", "sparse row: its values may sit under the wrong column")
                continue
            n_info = cell_n(cell, columns)
            verdict = check_cell(target, n_info)
            if verdict["status"] == "refused":
                row["refused"] += 1
                bump("refused", str(verdict.get("why")).split(":")[0][:80])
                continue
            out["checked"] += 1
            row["checked"] += 1
            bump("n_by_source", str(verdict.get("n_source")))
            bump("premise_by_source", str(target.get("premise")))
            status = verdict["status"]
            out[status] += 1
            out["checked_cells"].append({
                "table": table_key(i), "row": cell.get("row"), "col": cell.get("col"),
                "raw": cell.get("raw"), "what": target["what"],
                "value": target["value"], "n": verdict.get("n"),
                "n_source": verdict.get("n_source"), "status": status})
            if status == "rounding_only":
                row[status] += 1
            elif status != "consistent":
                row[status] += 1
                out["failures"].append({
                    "table": table_key(i), "label": table.get("label"),
                    "table_num": table.get("table_num"),
                    "source": table.get("source"),
                    "page": table.get("page"), "row": cell.get("row"),
                    "col": cell.get("col"), "row_label": cell.get("row_label"),
                    "col_label": cell.get("col_label"), "raw": cell.get("raw"),
                    "what": target["what"], "value": target["value"],
                    "decimals": target["decimals"], "premise": target["premise"],
                    "variable_id": target.get("variable_id"),
                    "n_text": n_info.get("text"), **verdict})
        out["tables"].append(row)
    return out


# ---------------------------------------------------------------------------
# The model's half: two tools, read back from the ledger after the run.
# ---------------------------------------------------------------------------

#: The tool whose calls carry the declarations (`tool_short` in the ledger).
DECLARE_TOOL = "declare_table"


def list_tables(paper_dir: str) -> dict:
    """Every table the harness will sweep, with the key a declaration uses.

    One entry per table of `prepass.paper_tables(paper_dir,
    include_supplements=True)` -- the same walk the sweep makes, so a key here
    is a key there."""
    from .prepass import paper_tables

    tables = paper_tables(paper_dir, include_supplements=True)
    out = []
    for i, t in enumerate(tables, start=1):
        cells = t.get("cells") or []
        columns = column_ns(t)
        labels: dict[int, str] = {}
        for c in cells:
            if c.get("col") is not None:
                labels.setdefault(int(c["col"]), str(c.get("col_label") or ""))
        rows: list[str] = []
        for c in cells:
            lab = str(c.get("row_label") or "")
            if lab and lab not in rows:
                rows.append(lab)
        out.append({
            "table": table_key(i), "label": t.get("label"),
            "caption": (str(t.get("caption") or "")[:200] or None),
            "page": t.get("page"), "source": t.get("source"),
            "n_cells": len(cells),
            "columns": [{"col": col, "label": lab,
                         **({"n": columns[col].get("n"),
                             "n_source": columns[col].get("source")}
                            if col in columns else {})}
                        for col, lab in sorted(labels.items())],
            "rows": rows[:60],
            **({"rows_truncated": len(rows)} if len(rows) > 60 else {}),
        })
    return {"paper_dir": str(paper_dir), "n_tables": len(out), "tables": out,
            "how_to_declare": (
                "Call declare_table once per table that prints means or "
                "percentages, naming it by `table` (T1, T2, ...). The harness "
                "then runs GRIM on every cell whose premises the declaration "
                "establishes, and files the failures itself.")}


def declare_table(paper_dir: str, table: str, variables: list | None = None,
                  rows: list | None = None, columns: list | None = None,
                  default_variable_id: str | None = None,
                  percent_of_units: bool = False) -> dict:
    """Record what a table's cells ARE, and return the GRIM sweep over it.

    The declaration is the model's job and the enumeration is the harness's:
    every eligible cell of the table is checked from this declaration, and the
    same declaration is read back from the ledger after the run, when the
    harness checks every table again and files the failures. A later call for
    the same table replaces an earlier one."""
    from .prepass import paper_tables

    tables = paper_tables(paper_dir, include_supplements=True)
    decl = {"table": table, "variables": variables or [], "rows": rows or [],
            "columns": columns or [], "default_variable_id": default_variable_id,
            "percent_of_units": bool(percent_of_units)}
    hits = [i for i, t in enumerate(tables, start=1)
            if match_declaration([decl], i, t) is decl]
    if len(hits) != 1:
        return {"severity": "indeterminate", "declared": False,
                "error": (f"table {table!r} names {len(hits)} tables; use the key "
                          "list_tables returns (T1, T2, ...)"),
                "tables": [{"table": table_key(i), "label": t.get("label")}
                           for i, t in enumerate(tables, start=1)]}
    i = hits[0]
    decl["table"] = table_key(i)
    one = [dict(t) if k == i - 1 else {"label": t.get("label"), "cells": []}
           for k, t in enumerate(tables)]
    try:
        from .extraction.jats import paper_text as _paper_text
        text = _paper_text(paper_dir)
    except Exception:  # noqa: BLE001
        text = None
    sweep = sweep_grim(one, [decl], variables, paper_text=text)
    if sweep.get("refused_whole_paper"):
        return {"severity": "indeterminate", "declared": True,
                "table": table_key(i), "refused": sweep["refused_whole_paper"]}
    row = sweep["tables"][i - 1]
    by_id = {str(v.get("id")) for v in variables or [] if isinstance(v, dict)}
    unknown = sorted({str(r.get("variable_id")) for r in rows or []
                      if isinstance(r, dict) and str(r.get("variable_id")) not in by_id}
                     | ({str(default_variable_id)} if default_variable_id
                        and str(default_variable_id) not in by_id else set()))
    fails = [f for f in sweep["failures"]]
    worst = ("highly_suspicious" if any(f["status"] == "inconsistent" for f in fails)
             else "suspicious" if fails else "consistent" if row["checked"]
             else "indeterminate")
    return {
        "severity": worst, "declared": True, "table": table_key(i),
        "label": tables[i - 1].get("label"),
        "checked": row["checked"], "inconsistent": row["inconsistent"],
        "explained_by_nonresponse": row["explained_by_nonresponse"],
        "refused": sweep["refused"], "column_n": row["column_n"],
        "unknown_variable_ids": unknown or None,
        "failures": [{k: f.get(k) for k in (
            "row", "col", "row_label", "col_label", "raw", "what", "value",
            "n", "n_source", "status", "consistent_at_n", "premise")}
            for f in fails],
        "note": ("The harness files every failure listed here as a finding of "
                 "its own after the run, one per table. Do NOT file them again. "
                 "If a failure rests on a wrong declaration (an averaged "
                 "subscale declared as an item, a percentage of something "
                 "continuous declared as a share, the wrong n), call "
                 "declare_table again with the correction; the last call wins."),
    }


def declarations_from_ledger(ledger: list[dict] | None) -> tuple[list[dict], list[dict]]:
    """`(declarations, variables)` from the tools agent's `declare_table` calls,
    in call order (a later declaration of a table replaces an earlier one in
    `match_declaration`; a later variable with the same id replaces it here).
    A call the server answered with an error still declared nothing."""
    decls: list[dict] = []
    variables: dict[str, dict] = {}
    for rec in ledger or []:
        if rec.get("tool_short") != DECLARE_TOOL or rec.get("is_error"):
            continue
        args = rec.get("input")
        if not isinstance(args, dict) or not args.get("table"):
            continue
        for v in args.get("variables") or []:
            if isinstance(v, dict) and v.get("id") is not None:
                variables[str(v["id"])] = v
        decls.append(args)
    return decls, list(variables.values())


def merge_variables(declared: list[dict], anatomy: list[dict] | None) -> list[dict]:
    """The declare_table variables, with the anatomy's VERIFIED fields laid
    over them where the ids agree. `provenance_verdict` is pipeline-written
    (the quote pass), so an anatomy variable carries the verdict a variable
    passed in a tool call cannot."""
    by_id = {str(v.get("id")): dict(v) for v in declared if isinstance(v, dict)}
    for v in anatomy or []:
        if not isinstance(v, dict) or v.get("id") is None:
            continue
        key = str(v["id"])
        if key in by_id:
            for field in ("provenance_verdict",):
                if v.get(field) is not None:
                    by_id[key][field] = v[field]
        else:
            by_id[key] = dict(v)
    return list(by_id.values())


#: Display: what kind of n a verdict rested on.
_N_SOURCE_WORDS = {
    "cell": "printed in the cell", "header": "from the column header",
    "header_row": "from a header row", "row_label": "from the row label",
    "declared": "declared from the paper's text",
}


def finding_rows(sweep: dict | None, paper_id: str) -> list[dict]:
    """findings-v2 rows: ONE per table with a failure, listing every cell.

    Dan, 2026-10-18: the harness's GRIM failures are findings. Severity is
    provisional and bounded: `highly_suspicious` (4) when some cell fails at
    its stated n, `suspicious` (3) when every failure is one that a few
    missing observations would explain. Never `impossible`: the integer
    premise rests on a declaration, and a GRIM `impossible` needs the R
    cross-check besides."""
    from . import findings_v2, severity9

    rows: list[dict] = []
    by_table: dict[str, list[dict]] = {}
    for f in (sweep or {}).get("failures") or []:
        by_table.setdefault(str(f.get("table")), []).append(f)
    for key, fails in by_table.items():
        strict = [f for f in fails if f["status"] == "inconsistent"]
        weak = [f for f in fails if f["status"] == "explained_by_nonresponse"]
        label = fails[0].get("label") or key
        # An old docling cache labels a table by its caption reference.
        shown = (str(label) if not str(label).startswith("cref")
                 else f"the table on page {fails[0].get('page')}")
        checked = next((t["checked"] for t in sweep.get("tables") or []
                        if t.get("table") == key), None)
        worst = "highly_suspicious" if strict else "suspicious"
        lines = []
        for f in (strict + weak)[:12]:
            source = _N_SOURCE_WORDS.get(str(f.get("n_source")), f.get("n_source"))
            nearby = (f", consistent at n = {f['consistent_at_n']}"
                      if f.get("consistent_at_n") else "")
            lines.append(f"{f.get('row_label')} / {f.get('col_label')}: {f.get('raw')} "
                         f"at n = {f.get('n')} ({source}){nearby}")
        what = "percentage" if all(f["what"] == "percent" for f in fails) else (
            "mean" if all(f["what"] == "mean" for f in fails) else "value")
        description = (
            f"The harness GRIM sweep checked {checked} cell(s) of {shown} and found "
            f"{len(strict)} {what}(s) that no whole-number count over the stated n "
            "can produce"
            + (f", and {len(weak)} more that fail at the stated n but would pass "
               "if one or a few participants had not answered" if weak else "")
            + ". " + "; ".join(lines)
            + (f"; and {len(fails) - 12} more" if len(fails) > 12 else "") + ".")
        anchors = [{k: v for k, v in {
                        "kind": "table_cell", "table": str(label), "table_key": key,
                        "table_num": f.get("table_num"), "source": f.get("source"),
                        "row_label": f.get("row_label"),
                        "row": f.get("row"), "col": f.get("col"), "raw": f.get("raw"),
                        "value": f.get("value"), "page": f.get("page"),
                        "cells": [f"r{f.get('row')}c{f.get('col')}"],
                        "role": "said"}.items() if v is not None}
                   for f in strict + weak]
        technique = "grim_percentage" if what == "percentage" else "grim_check"
        rows.append({
            "slug": f"harness_grim_{key.lower()}",
            "producer": "harness",
            "technique": technique,
            "title": findings_v2.clip(
                f"{shown}: {len(strict) or len(weak)} {what}(s) inconsistent with "
                "the stated n (GRIM)", 90),
            "description": findings_v2.clip(description, 700),
            "location": str(label),
            "outcome": "problem",
            "provisional_severity": severity9.FIVE_TO_NINE[worst],
            "severity_is_provisional": True,
            "impossible": False,
            "quarantined": False,
            "computed_by": "deterministic_track",
            # The CHECK that fired, so the finding is tagged with its tool;
            # `producer: harness` says the harness, not a model, aimed it.
            "tool_verdict": {"severity": worst, "tool": technique,
                             "validated": True},
            "inputs": {"table": key, "n_checked": checked,
                       "n_inconsistent": len(strict),
                       "n_explained_by_nonresponse": len(weak),
                       "cells": [{k: f.get(k) for k in (
                           "row", "col", "row_label", "col_label", "raw", "value",
                           "decimals", "what", "n", "n_source", "n_text", "status",
                           "consistent_at_n", "premise", "variable_id")}
                           for f in strict + weak]},
            "anchors": anchors,
            "anchor_problem": ("located by table cell (row, column); the cells are "
                               "listed in `inputs.cells`"),
        })
    findings_v2.assign_finding_ids(rows, paper_id)
    return rows


def coverage_line(sweep: dict | None) -> str | None:
    """One sentence for the report: what the harness GRIM sweep covered."""
    if not sweep:
        return None
    if sweep.get("refused_whole_paper"):
        return "GRIM sweep: not run -- " + sweep["refused_whole_paper"]
    refused = sum((sweep.get("refused") or {}).values())
    top = sorted((sweep.get("refused") or {}).items(), key=lambda x: -x[1])[:3]
    return (f"GRIM sweep: {sweep.get('enumerated', 0)} mean/percentage cell(s) "
            f"enumerated across {sweep.get('n_tables', 0)} table(s); "
            f"{sweep.get('checked', 0)} checked, {sweep.get('inconsistent', 0)} "
            f"inconsistent, {sweep.get('explained_by_nonresponse', 0)} explained "
            f"by possible non-response, {sweep.get('rounding_only', 0)} consistent "
            f"only if the paper truncates; {refused} not checked"
            + (" (" + "; ".join(f"{k}: {v}" for k, v in top) + ")" if top else "")
            + ".")
