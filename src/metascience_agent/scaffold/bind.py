"""The deterministic half of extraction: turning pass output into the account.

WHAT IS CODE HERE AND WHAT IS MODEL. The model supplies READINGS -- which column
is which coordinate, which row is which variable, what a cell's form is, where
a prose value sits. Code supplies the NUMBERS: every table value is built from
the walker's cell text by this module, never transcribed by the model; every
prose value's `printed` string must occur inside its quote, and the quote must
occur in the text. Code also does all the bookkeeping -- referential integrity
(`schema.validate_account`), quote verification (`quotes.classify`), the
numeral accounting against `numerals.index`, the gaps, and the completeness
measure -- because bookkeeping is exactly what a model does badly and exactly
what a reader needs to be able to trust.

THE ACCOUNTING IS THE HONESTY MECHANISM. `numerals.index` is exhaustive and
model-free. Every numeral in the analytic text ends this module in exactly one
disposition, and `unaccounted` is one of them. A completeness figure is
`accounted / in_scope` with both numbers printed, and a reader can pull the
`unaccounted` list and see what was missed, with its context. A scaffold that
reported only what it found would be measuring the finder with itself.
"""

from __future__ import annotations

import re
from typing import Any

from .. import quotes as _quotes
from .. import numerals as _numerals
from . import schema as _schema

_NUM = r"[-−+]?\d+(?:[.,]\d+)?"
_MEAN_PM_PAREN = re.compile(rf"^({_NUM})\s*\(\s*±\s*({_NUM})\s*\)$")
_MEAN_PM = re.compile(rf"^({_NUM})\s*±\s*({_NUM})$")
_MEAN_PAREN = re.compile(rf"^({_NUM})\s*\(\s*({_NUM})\s*\)$")
_MEDIAN_IQR = re.compile(rf"^({_NUM})\s*[\(\[]\s*({_NUM})\s*[-–,;]\s*({_NUM})\s*[\)\]]$")
_SINGLE = re.compile(rf"^({_NUM})\s*%?$")
_P_CELL = re.compile(r"^[<>≤≥=]?\s*([-−+]?(?:\d+(?:[.,]\d+)?|[.,]\d+))$")  # a p value is where a leading-dot decimal is standard
from ..composite import _COUNT_PCT, _COUNT_SLASH_PCT  # the one definition of `n (pct%)`
_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-"})


#: WHAT SHAPE A PRINTED LITERAL HAS, closed. Every value carries one, because
#: `numeric` and `decimals` mean different things for each shape and a consumer
#: that cannot tell them apart reads `84,299` as 84.299 -- which is what this
#: module did until 2026-09-08, and it shrinks a rounding interval a
#: thousandfold in the ACCUSING direction.
#:
#:   plain            `1.67`, `-0.5`, `64`      -- a bare number
#:   percent          `85.94%`                  -- a bare number with a % sign
#:   grouped_integer  `84,299`                  -- digit groups under the
#:                                                 document's own convention
#:   range            `6-9`                     -- two numbers, no single value
#:   word             `Twenty-six`              -- spelled out, no digits
#:   qualified        `approximately 84,000`    -- one numeral plus words
#:   other            anything else             -- a list, a formula, empty
PRINTED_FORMS = ("plain", "percent", "grouped_integer", "range", "word",
                 "qualified", "other")

# THE LEADING-DOT FORM IS PLAIN. `.01` is the standard way a paper prints a
# p-value, and refusing it would take `numeric` off 40 cells of ajcp.70049's
# regression tables -- a coverage loss caused by a precision fix, which is the
# wrong trade in both directions.
_PLAIN_RE = re.compile(r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)")
_GROUPED_RE = re.compile(r"[-+]?\d{1,3}(?:,\d{3})+")
_RANGE_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?\s*-\s*[-+]?\d+(?:[.,]\d+)?")
_HAS_DIGIT = re.compile(r"\d")
_HAS_ALPHA = re.compile(r"[^\W\d_]", re.UNICODE)
#: One numeral inside a longer literal. The leading-dot alternative is what
#: makes `< .001` one token rather than the digits `001`.
_ONE_NUMERAL = re.compile(r"\d[\d,]*(?:\.\d+)?|\.\d+")


def decimal_convention(text: str) -> str:
    """`.` or `,` -- which character THIS document uses as its decimal point.

    A comma before exactly three digits is ambiguous in isolation: `84,299` is
    eighty-four thousand in an English paper and 84.299 in a German one, and no
    rule reading that literal alone can tell. The document settles it. A paper
    that prints `1.67 (2.15)` has already used the period as its decimal point,
    so its commas are separators; only a document with comma-decimals and NO
    period-decimals is read the other way.

    FAILS TOWARD THE PERIOD, deliberately -- it is the convention of every paper
    in the working corpus, and the comma reading has to be EARNED by positive
    evidence (a comma before one or two digits, which no thousands separator
    ever produces) rather than assumed from a single ambiguous literal.
    """
    t = text or ""
    n_period = len(re.findall(r"\d\.\d", t))
    n_comma_decimal = len(re.findall(r"\d,\d{1,2}(?!\d)", t))
    return "," if (n_comma_decimal and not n_period) else "."


def read_literal(printed: str, decimal_sep: str = ".") -> dict:
    """`{printed_form, numeric, decimals}` for one printed literal.

    `decimals` is the count of digits after the DECIMAL POINT, never after a
    separator: `84,299` is 0 decimals and `85.94%` is 2. A form that is not a
    single number carries `numeric: None` and `decimals: 0`, so a consumer that
    needs a number has to look at `printed_form` first.
    """
    s = str(printed or "").strip().translate(_DASHES)
    out = {"printed_form": "other", "numeric": None, "decimals": 0}
    if not s:
        return out
    grouped = False
    if decimal_sep == ",":
        # The paper's decimal point is the comma; a period before exactly three
        # digits is then the separator. Normalised into the period convention
        # and read by the same grammar below -- one grammar, not two -- with the
        # fact that a separator WAS removed carried through, so the form still
        # says `grouped_integer` rather than flattening to `plain`.
        if re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})+%?", s):
            s, grouped = s.replace(".", ""), True
        s = s.replace(",", ".")
    body, pct = (s[:-1].strip(), True) if s.endswith("%") else (s, False)
    if _PLAIN_RE.fullmatch(body):
        return {"printed_form": ("grouped_integer" if grouped else
                                 "percent" if pct else "plain"),
                "numeric": float(body),
                "decimals": len(body.split(".")[1]) if "." in body else 0}
    if _GROUPED_RE.fullmatch(body):
        # A separator carries no precision: `84,299` is an integer printed to 0
        # decimal places, and reading its last group as decimals is the defect
        # this function exists to remove.
        return {"printed_form": "grouped_integer",
                "numeric": float(body.replace(",", "")), "decimals": 0}
    if _RANGE_RE.fullmatch(s):
        return {**out, "printed_form": "range"}
    if not _HAS_DIGIT.search(s):
        return {**out, "printed_form": "word" if _HAS_ALPHA.search(s) else "other"}
    tokens = _ONE_NUMERAL.findall(s)
    if len(tokens) == 1:
        # A QUALIFIER REMOVES THE NUMBER, NOT ITS PRECISION. `< .001` is not the
        # value .001 and gets no `numeric`, but the paper did print three
        # decimal places and a consumer sizing a rounding interval needs them.
        # `approximately 84,000` reads its one numeral by the same grammar, so
        # the separator lands at 0 decimals rather than 3.
        #
        # THE RECURSION NEEDS A BASE CASE, AND IT HAD NONE. The inner read is
        # only a narrower reading when the token is SHORTER than what we were
        # handed: `< .001` strips its qualifier, `approximately 84,000` its
        # word. A literal that IS its own only numeral and still matched
        # neither grammar above -- `4,16`, a comma-decimal value read under a
        # paper whose convention is the period, and every `1,2` / `12,345,6`
        # shape like it -- recursed on the identical string until the
        # interpreter gave up, and `RecursionError` out of `premises.
        # printed_integer` took an entire account's sidecar with it: no
        # `checks.json`, no docket, nothing written. Such a literal is simply
        # one this function cannot read, which is what `out` already says.
        inner = tokens[0].rstrip(".,")
        if inner == s:
            return out
        return {**out, "printed_form": "qualified",
                "decimals": read_literal(inner, decimal_sep)["decimals"]}
    return out


def _numeric(printed: str, decimal_sep: str = ".") -> float | None:
    return read_literal(printed, decimal_sep)["numeric"]


def _decimals(printed: str, decimal_sep: str = ".") -> int:
    return read_literal(printed, decimal_sep)["decimals"]


def cell_components(raw: str, statistic_form: str, variable_kind: str | None = None, col_label: str | None = None) -> list[tuple[str, str]]:
    """`[(statistic, printed)]` for one cell under the model's stated form.

    Returns [] when the cell does not parse under that form -- the caller records
    the cell as unparsed rather than guessing a different form, because the form
    is the model's reading and a silent re-reading here would be a second,
    unlogged interpretation.
    """
    text = (raw or "").strip()
    if not text:
        return []
    if statistic_form in ("mean_pm_sem", "mean_pm_sd", "mean_pm_unstated"):
        disp = {"mean_pm_sem": "sem", "mean_pm_sd": "sd",
                "mean_pm_unstated": "dispersion_unstated"}[statistic_form]
        for pat in (_MEAN_PM_PAREN, _MEAN_PM, _MEAN_PAREN):
            m = pat.match(text)
            if m:
                return [("mean", m.group(1)), (disp, m.group(2))]
        m = _SINGLE.match(text)
        if m:
            return [("mean", m.group(1))]
        return []
    if statistic_form == "median_iqr":
        m = _MEDIAN_IQR.match(text)
        if m:
            return [("median", m.group(1)), ("min", m.group(2)), ("max", m.group(3))]
        return []
    # A `p` COLUMN IS A p VALUE WHATEVER THE ROW'S FORM. On ajcp.70049 the
    # regression tables print `Coefficient | M (SD)` beside `Coefficient | p`,
    # and the reading is per ROW (`model_coefficient`, form `other`), so the
    # p cells `.01`, `< .001`, `0` had no parser: 0 of 126 cells landed. The
    # column label is printed evidence the call site already held.
    leaf = re.sub(r"[^a-z]", "", (col_label or "").split("|")[-1].lower()) if col_label else ""
    if leaf in ("p", "pvalue", "adjustedpvalue") or leaf.endswith("pvalue"):
        m = _P_CELL.match(text)
        return [("p_value", m.group(0).replace(" ", ""))] if m else []
    if statistic_form in ("percentage_of_subjects", "count", "single_value"):
        # `38 (59%)` is a count AND a percentage. Reuses composite's regexes --
        # the one definition of that cell shape -- rather than a second copy.
        m = _COUNT_PCT.match(text) or _COUNT_SLASH_PCT.match(text)
        if m:
            return [("count", m.group(1)), ("percentage", m.group(2))]
        m = _SINGLE.match(text)
        if not m:
            return []
        stat = {"percentage_of_subjects": "percentage", "count": "count"}.get(statistic_form)
        if stat is None:
            stat = "percentage" if (variable_kind or "").startswith("percentage") else "other"
        return [(stat, m.group(1))]
    # FORM `other` -- a coefficient with a parenthesised dispersion. `1.01 (0.38)`
    # is an estimate and SOMETHING in parentheses; the paper's header says
    # `M (SD)` over cells that are not means, and the reading declined to say
    # whether it is an SE or an SD. So the second component is named
    # `dispersion_unstated`, never `se` or `sd` -- a derived boundary may narrow
    # a premise, never supply one.
    m = _MEAN_PAREN.match(text)
    if m:
        return [("other", m.group(1)), ("dispersion_unstated", m.group(2))]
    m = _SINGLE.match(text)
    return [("other", m.group(1))] if m else []


# --------------------------------------------------------------------------
# Locating quotes and numerals in the text
# --------------------------------------------------------------------------


def _flex_pattern(quote: str) -> re.Pattern | None:
    """Whitespace- and dash-tolerant literal pattern for `quote`."""
    toks = quote.translate(_DASHES).split()
    if not toks:
        return None
    parts = []
    for tok in toks:
        parts.append("".join(r"[-–—−‐‑]" if c == "-" else re.escape(c) for c in tok))
    return re.compile(r"\s+".join(parts))


def locate(quote: str, text: str) -> tuple[int, int] | None:
    """The span of `quote` in `text`, tolerant of whitespace and dash variants.
    None when it is not a contiguous span of the text."""
    pat = _flex_pattern(quote or "")
    if pat is None:
        return None
    m = pat.search(text)
    return (m.start(), m.end()) if m else None


def _numeral_tokens(printed: str) -> list[str]:
    """The numeric tokens a printed value contains: `6–9` -> [`6`, `9`]."""
    return re.findall(r"\d+(?:[.,]\d+)?", printed or "")


class _Hay:
    """One paper's haystack for `quotes.classify`, built once."""

    def __init__(self, text: str):
        self.hay = {"the paper's text": _quotes.normalise(text)}
        self.folded = _quotes.fold_haystack(self.hay)

    def verify(self, quote: str | None) -> dict:
        return _quotes.classify(quote or "", self.hay, self.folded)


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------


def _norm_label(s: Any) -> str:
    return " ".join(str(s or "").translate(_DASHES).lower().split())


def _coord_for_group(group_id: str | None, doc: dict) -> dict | None:
    """The study/group coordinate a declared group id names, from pass 1's studies
    as carried on the document's caller; None when the id is unknown."""
    if not group_id:
        return None
    for st in doc.get("_studies") or []:
        for g in st.get("groups") or []:
            if g.get("id") == group_id:
                return {"study_id": st.get("id"), "group_id": group_id, "phase_id": None}
    return None


def _caption_group(table: dict, doc: dict) -> dict | None:
    """The one declared group whose printed LABEL the table's caption contains.

    MEASURED on ajcp.70049 (D47). The coordinate reaches a table value by two
    routes -- the model's own `group_id` on the entry, and the pass-3 column map
    -- and pass 3 does not re-read a verified table, so where the model omitted
    the group id there was no fallback at all: all 63 values of Table 4 carry no
    group. Its caption ends `(n = 101 programs in 35 coalitions)` and
    `grp:programs_n101`'s declared label IS the string `n = 101 programs in 35
    coalitions`. Verbatim containment, one hit, no inference.

    A DERIVED BOUNDARY MAY NARROW A PREMISE, NEVER SUPPLY ONE (CLAUDE.md 8d,
    invariant 1) -- and a group id IS a premise, because it is a denominator. So
    the join is refused wherever it would be a choice: two declared groups whose
    labels both sit in one caption bind nothing, which is what happens on this
    paper's Tables 2 and 3, where two groups share the label `n = 64 coalitions`.
    Nothing is lost there -- those values already carry the model's own ids.
    """
    cap = _norm_label(table.get("caption"))
    if not cap:
        return None
    hits = [{"study_id": st.get("id"), "group_id": g.get("id"), "phase_id": None}
            for st in doc.get("_studies") or [] for g in st.get("groups") or []
            if g.get("id") and (lab := _norm_label(g.get("label"))) and lab in cap]
    return hits[0] if len(hits) == 1 else None


#: reconstruct.TIDY_STATISTICS -> schema.STATISTICS. Every tidy kind lands on an
#: account kind; `other` is the honest floor, never a guess.
_TIDY_TO_ACCOUNT = {"n": "n", "count": "count", "percentage": "percentage", "mean": "mean", "sd": "sd",
                    "sem": "sem", "median": "median", "iqr": "iqr", "range": "range",
                    "ci_lower": "ci_lower", "ci_upper": "ci_upper", "coefficient": "coefficient",
                    "se": "se", "test_statistic": "test_statistic", "df": "df", "p": "p_value",
                    "ratio": "ratio", "score": "score", "other": "other"}


def _table_values(doc: dict, p3: dict, variables: dict, problems: list[str],
                  decimal_sep: str = ".") -> tuple[list[dict], list[dict]]:
    """Values built from the walker's cells under the model's table readings."""
    values: list[dict] = []
    unparsed: list[dict] = []
    readings = {r["table_id"]: r for r in p3.get("table_readings", [])}
    for t in doc["tables"]:
        reading = readings.get(t["id"])
        recon_ok = (t.get("reconstruction") or {}).get("status") == "verified"
        tnum = t["id"].split(":")[-1]
        # A VERIFIED TABLE NEEDS NO PASS-3 READING: pass 3 is told not to give
        # one, so `reading is None` is the expected state, not a gap. Checked
        # first -- measured on 37679, the no-reading branch below ran first and
        # Table 1's 417 verified entries became 0 values and 189 "unparsed".
        cols = {_norm_label(c["col_label"]): c for c in (reading or {}).get("column_map", [])}
        if not recon_ok:
            if reading is None:
                problems.append(f"{t['id']}: the model gave no reading; its "
                                f"{t['n_cells']} cells are recorded as unparsed")
                unparsed += [{"table_id": t["id"], "raw": c.get("raw"), "row": c.get("row"),
                              "col": c.get("col"), "why": "no table reading"} for c in t["cells"]]
                continue
            rows = {_norm_label(r["row_label"]): r for r in reading.get("row_map", [])}
            missing_cols = [l for l in t["col_labels"] if _norm_label(l) not in cols]
            missing_rows = [l for l in t["row_labels"] if _norm_label(l) not in rows]
            if missing_cols:
                problems.append(f"{t['id']}: {len(missing_cols)} column label(s) not in the "
                                f"reading: {missing_cols[:4]}")
            if missing_rows:
                problems.append(f"{t['id']}: {len(missing_rows)} row label(s) not in the "
                                f"reading: {missing_rows[:4]}")
        if recon_ok:
            # THE TIDY READING IS THE TABLE. Each entry names its variable,
            # level, group and statistic itself; nothing here re-matches a row
            # label by string (that re-matching cost 64 values on the grid
            # form). The column map still supplies the study/group/phase ids
            # for the column; a column the map lacks leaves the coordinate
            # empty, not the value unrecorded.
            cap_coord = _caption_group(t, doc)
            for c in t["cells"]:
                col = cols.get(_norm_label(c.get("col_label"))) or {}
                for k, e in enumerate(c.get("entries") or []):
                    stat = _TIDY_TO_ACCOUNT.get(e.get("statistic"), "other")
                    lit = read_literal(str(e.get("value") or ""), decimal_sep)
                    vid = e.get("variable_id")
                    coord = _coord_for_group(e.get("group_id"), doc)
                    csrc = "declared_group_id" if coord else None
                    if coord is None:
                        coord = {"study_id": col.get("study_id"), "group_id": col.get("group_id"),
                                 "phase_id": col.get("phase_id")}
                        csrc = "column_map" if any(coord.values()) else None
                    # THE CAPTION, LAST AND ONLY WHERE THERE IS NO GROUP. It
                    # cannot overrule a group the model named or the column map
                    # supplied, and it is refused where it would contradict a
                    # study already on the coordinate: a caption naming another
                    # study's arm is a continuation panel misread, and a wrong
                    # group id is a wrong denominator.
                    if cap_coord and not coord.get("group_id") and coord.get(
                            "study_id") in (None, cap_coord["study_id"]):
                        coord = {**coord, "study_id": cap_coord["study_id"],
                                 "group_id": cap_coord["group_id"]}
                        csrc = "caption_join"
                    values.append({
                        "id": f"val:t{tnum}:r{c.get('row')}:c{c.get('col')}:{k}:{stat}",
                        "statistic": stat, "printed": str(e.get("value") or ""),
                        "numeric": lit["numeric"], "decimals": lit["decimals"],
                        "printed_form": lit["printed_form"],
                        "units": (variables.get(vid) or {}).get("units") if vid else None,
                        "variable_id": vid, "variable_as_read": e.get("variable"),
                        # THE ID THE READING WROTE, when the closed vocabulary
                        # refused it: the words are one witness, the id it was
                        # read as is another, and neither is thrown away.
                        "variable_id_as_read": e.get("variable_id_as_read"),
                        "variable_candidates": e.get("variable_candidates") or [],
                        "level_id": e.get("level_id"), "level_as_read": e.get("level"),
                        "group_as_read": e.get("group"),
                        "variable_id_source": e.get("variable_id_source"),
                        "id_check": e.get("id_check"),
                        # AN INFERRED KIND IS CARRIED, NOT TRUSTED: a check that needs
                        # to know a `(y)` is an SD reads this before it runs.
                        "statistic_basis": e.get("statistic_basis"),
                        # WHAT THE MODEL CALLED IT, where `reconstruct._retype`
                        # disagreed with it on the paper's own printed evidence.
                        # Null wherever the reading and the cell agree, so a
                        # non-null value IS the audit record of an override --
                        # the same shape as `variable_id_as_read` above.
                        "statistic_as_read": e.get("statistic_as_read"),
                        "statistic_disputed": bool(e.get("statistic_disputed")),
                        "reference_group_id": e.get("reference_group_id"),
                        "contrast_as_read": e.get("contrast"),
                        "coordinate": coord, "coordinate_source": csrc,
                        "applies_to_all_groups": False, "source": "table",
                        "location": {"kind": "table_cell", "table_id": t["id"], "row": c.get("row"),
                                     "col": c.get("col"), "row_label": c.get("row_label"),
                                     "col_label": c.get("col_label")},
                        "quote": str(c.get("raw") or ""), "quote_verified": "cell",
                        "statistic_form": "tidy_entry", "binding": e.get("binding"),
                    })
            continue
        for c in t["cells"]:
            col = cols.get(_norm_label(c.get("col_label")))
            row = rows.get(_norm_label(c.get("row_label")))
            if col is None or row is None:
                unparsed.append({"table_id": t["id"], "raw": c.get("raw"), "row": c.get("row"),
                                 "col": c.get("col"), "why": "label not in the reading"})
                continue
            vid = row.get("variable_id")
            vkind = (variables.get(vid) or {}).get("kind") if vid else None
            comps = cell_components(str(c.get("raw") or ""), row.get("statistic_form", "other"), vkind,
                                    col_label=c.get("col_label"))
            if not comps:
                unparsed.append({"table_id": t["id"], "raw": c.get("raw"), "row": c.get("row"),
                                 "col": c.get("col"),
                                 "why": f"does not parse as {row.get('statistic_form')}"})
                continue
            for stat, printed in comps:
                lit = read_literal(printed, decimal_sep)
                values.append({
                    "id": f"val:t{tnum}:r{c.get('row')}:c{c.get('col')}:{stat}",
                    "statistic": stat, "printed": printed, "numeric": lit["numeric"],
                    "decimals": lit["decimals"], "printed_form": lit["printed_form"],
                    "units": (variables.get(vid) or {}).get("units") if vid else None,
                    "variable_id": vid,
                    "coordinate": {"study_id": col.get("study_id"),
                                   "group_id": col.get("group_id"),
                                   "phase_id": col.get("phase_id")},
                    "applies_to_all_groups": False,
                    "source": "table",
                    "location": {"kind": "table_cell", "table_id": t["id"],
                                 "row": c.get("row"), "col": c.get("col"),
                                 "row_label": c.get("row_label"),
                                 "col_label": c.get("col_label")},
                    "quote": str(c.get("raw") or ""),
                    "quote_verified": "cell",
                    "statistic_form": row.get("statistic_form"),
                    "dispersion_stated_where": row.get("dispersion_stated_where"),
                })
    return values, unparsed


def _prose_values(rows: list[dict], text: str, hay: _Hay, source: str,
                  problems: list[str], decimal_sep: str = ".") -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for pv in rows:
        vid = pv.get("id") or f"val:prose:{len(out)}"
        if vid in seen:
            vid = f"{vid}:{len(out)}"
        seen.add(vid)
        quote = pv.get("quote") or ""
        span = locate(quote, text)
        verdict = hay.verify(quote)
        printed = str(pv.get("printed") or "")
        in_quote = all(tok in quote.translate(_DASHES) or tok in quote
                       for tok in _numeral_tokens(printed)) if printed else False
        if not in_quote:
            problems.append(f"{vid}: printed value {printed!r} is not inside its quote")
        lit = read_literal(printed, decimal_sep)
        numeric = pv.get("numeric")
        if numeric is None:
            numeric = lit["numeric"]
        out.append({
            "id": vid, "statistic": pv.get("statistic") or "other", "printed": printed,
            "numeric": numeric, "decimals": lit["decimals"],
            "printed_form": lit["printed_form"], "units": pv.get("units"),
            "variable_id": pv.get("variable_id"),
            "coordinate": dict(pv.get("coordinate") or {"study_id": None, "group_id": None,
                                                        "phase_id": None}),
            "applies_to_all_groups": bool(pv.get("applies_to_all_groups")),
            "source": source,
            "location": {"kind": pv.get("location") or "prose",
                         "offset": span[0] if span else None,
                         "end": span[1] if span else None},
            "quote": quote,
            "quote_verified": verdict.get("quote_verified"),
            "printed_in_quote": in_quote,
            "note": pv.get("note"),
        })
    return out


def _verify_quotes(rows: list[dict], text: str, hay: _Hay, field: str = "quote") -> None:
    for r in rows:
        q = r.get(field) or ""
        span = locate(q, text)
        r["quote_verified"] = hay.verify(q).get("quote_verified")
        r["quote_offset"] = span[0] if span else None


def _by_source(rows: list[dict]) -> dict[str, int]:
    """`{<source>_<prose|table>: n}` over `rows`, by the one key rule in `numerals`."""
    out: dict[str, int] = {}
    for r in rows:
        k = _numerals.source_key(r)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def account_numerals(doc: dict, values: list[dict], text: str) -> list[dict]:
    """One disposition per numeral outside the back matter, deterministic part.

    Table numerals are matched to table values by printed string within the
    table's own text span; prose numerals are matched to a value whose located
    quote covers them and whose printed tokens include them. Everything else is
    `unaccounted` here, and goes to the residual pass.
    """
    rows = [dict(r) for r in doc["numerals"] if r.get("role") != "back"]
    # TABLE-CELL ROWS HAVE NO BODY OFFSET. `numerals.index_table_cells` enumerates
    # a table's cells into the floor with `offset: None`, because their coordinate
    # is (table, cell), not a byte in the text. They are owned by the table pass
    # and are dispositioned as such up front; every offset-keyed branch below
    # must skip them. This crashed the first JATS run at `<=` on None after three
    # paid passes -- the guard existed in `linear.chunks` and not here.
    for r in rows:
        r["disposition"] = "unaccounted"
    for r in rows:
        if r.get("offset") is None:
            r["disposition"] = "table_cell"
            r["residual_note"] = f"printed in a table cell ({r.get('file') or r.get('table_index')}); owned by the table pass"
        r["value_id"] = None
        if r.get("class") == "citation_year":
            r["disposition"] = "citation_year"

    # Table spans: header numerals are coordinate labels; cell numerals match values.
    for t in doc["tables"]:
        span = t.get("text_span")
        if not span:
            continue
        tv = [v for v in values if v["source"] == "table"
              and v["location"].get("table_id") == t["id"]]
        pool: dict[str, list[str]] = {}
        for v in tv:
            pool.setdefault(v["printed"].replace("−", "-"), []).append(v["id"])
        header_end = span[0]
        # The header rows come first inside the span; find the end of the last
        # header pipe-row by counting `n_header_rows` newlines.
        n_hdr = t.get("n_header_rows") or 0
        pos = span[0]
        for _ in range(n_hdr):
            nl = text.find("\n", pos)
            if nl < 0:
                break
            pos = nl + 1
        header_end = pos
        for r in rows:
            if r.get("offset") is None:
                continue
            if not (span[0] <= r["offset"] < span[1]):
                continue
            if r["offset"] < header_end:
                r["disposition"] = "coordinate_label"
                continue
            key = r["printed"].replace("−", "-")
            ids = pool.get(key)
            if ids:
                r["disposition"] = "value"
                r["value_id"] = ids.pop(0)
            elif key.lstrip("-") in pool or any(key.lstrip("-") == k for k in pool):
                r["disposition"] = "value"
                r["value_id"] = pool[key.lstrip("-")].pop(0) if pool.get(key.lstrip("-")) else None
            else:
                r["disposition"] = "unaccounted"

    # Prose/caption values: a numeral inside a located quote, matching a token.
    for v in values:
        if v["source"] == "table":
            continue
        loc = v.get("location") or {}
        if loc.get("offset") is None:
            continue
        toks = set(_numeral_tokens(v["printed"]))
        for r in rows:
            if r["disposition"] != "unaccounted" or r.get("offset") is None:
                continue
            if loc["offset"] <= r["offset"] < loc["end"] and r["printed"].lstrip("-−+") in toks:
                r["disposition"] = "value"
                r["value_id"] = v["id"]
    return rows


def classify_phase_labels(rows: list[dict], text: str, account: dict) -> int:
    """Class the numerals inside a DECLARED phase label `phase_label`. Returns how many.

    `Wave 1`, `Time 2`, `Year 1` are the paper's names for its own occasions, and
    the numeral in one is a label rather than a measurement: on ajcp.70049 eight
    of them block six statistic-bearing sentences. THE LABEL MUST BE DECLARED --
    this is a join against the structure's own phases, not a word list, so a
    paper that calls its waves something else is unaffected and a paper that
    calls nothing a wave gains nothing.

    Narrow on purpose: the label must carry a letter and a digit and be at least
    four characters, so a phase declared as `1` cannot sweep every `1` in the
    paper. `classify_with` touches only `unclassified` rows, so nothing already
    named is renamed.
    """
    declared = {str(p.get("label") or "") for p in account.get("phases") or []}
    declared |= {str(p.get("label") or "") for s in account.get("studies") or []
                 for p in s.get("phases") or []}
    # THE PAPER PRINTS THE SHORT FORM. ajcp declares `Wave 1 (baseline / Time 1)`
    # and writes `Wave 1` and `Time 1`, so the full label occurs nowhere. The
    # label without its parenthetical, and each segment INSIDE it, are the same
    # declaration written the way the prose writes it -- and each must still pass
    # the letter-and-digit floor below on its own.
    labels: set[str] = set()
    for lab in declared:
        labels.add(lab)
        labels.add(re.sub(r"\([^)]*\)", " ", lab))
        for inner in re.findall(r"\(([^)]*)\)", lab):
            labels.update(re.split(r"\s*[,/;]\s*", inner))
    labels = {" ".join(l.split()) for l in labels}
    spans: list[tuple[int, int]] = []
    named: list[str] = []
    for lab in sorted(labels, key=len, reverse=True):
        if len(lab) < 4 or not any(c.isdigit() for c in lab) or not any(c.isalpha() for c in lab):
            continue
        pos = text.find(lab)
        while pos >= 0:
            spans.append((pos, pos + len(lab)))
            pos = text.find(lab, pos + 1)
        named.append(lab)
    if not spans:
        return 0
    return _numerals.classify_with(rows, spans, "phase_label",
                                   "inside a phase label this paper declares "
                                   f"({', '.join(sorted(named))})")


def apply_residual(rows: list[dict], residual: dict | None, known_value_ids: set[str]
                   ) -> tuple[list[dict], list[str]]:
    """Merge pass-3b dispositions into the accounting rows. Returns problems."""
    problems: list[str] = []
    if not residual:
        return rows, problems
    by_id = {r["id"]: r for r in rows}
    for d in residual.get("dispositions", []):
        r = by_id.get(d.get("numeral_id"))
        if r is None:
            problems.append(f"residual names unknown numeral {d.get('numeral_id')!r}")
            continue
        if r["disposition"] != "unaccounted":
            continue  # code already placed it; the deterministic answer stands
        disp = d.get("disposition") or "unaccounted"
        if disp not in _schema.NUMERAL_DISPOSITIONS:
            problems.append(f"{r['id']}: disposition {disp!r} outside the vocabulary")
            disp = "unaccounted"
        vid = d.get("value_id")
        if disp in ("value", "duplicate_of_value"):
            if vid not in known_value_ids:
                problems.append(f"{r['id']}: names value {vid!r} that does not exist; "
                                "left unaccounted")
                disp, vid = "unaccounted", None
        cands = list(d.get("candidates") or [])
        if disp == "ambiguous" and len(cands) < 2:
            # AMBIGUOUS MEANS TWO OR MORE CANDIDATES. One candidate is a placement
            # the model declined to make; none is an unplaced numeral. Either way
            # the honest state is unplaced, and the reason is kept.
            problems.append(f"{r['id']}: `ambiguous` with {len(cands)} candidate(s); "
                            "left unaccounted")
            disp = "unaccounted"
        r["disposition"] = disp
        r["value_id"] = vid
        r["residual_note"] = d.get("note")
        if disp == "ambiguous":
            r["candidates"] = cands
            r["distinguisher"] = d.get("distinguisher")
    return rows, problems


def _gaps(account: dict, doc: dict | None = None) -> list[dict]:
    """Named absences: what a reader or a check would want and the paper does not give.

    One of them is OURS rather than the paper's, and it is here because a reader
    asking "why is this table's typing so poor" has to be able to find the
    answer: a reading of a table was bought and then discarded, and the walker's
    grid was substituted for it (`reconstruct._refuse`).
    """
    gaps: list[dict] = []
    for t in (doc or {}).get("tables") or []:
        sub = ((t.get("reconstruction") or {}).get("substitution")) or {}
        if not sub.get("happened"):
            continue
        gaps.append({"kind": "table_reading_bought_and_discarded", "table_id": t["id"],
                     "label": t.get("label"),
                     "cost_usd": sub.get("reading_cost_usd"),
                     "n_entries_discarded": sub.get("n_entries_discarded"),
                     "detail": "; ".join(sub.get("why") or [])[:300],
                     "reading_kept_at": "; ".join(sub.get("reading_kept_at") or []),
                     "consequence": sub.get("consequence")})
    for s in account["studies"]:
        groups = s.get("groups", [])
        if groups and all(g.get("n_printed") is None for g in groups):
            gaps.append({"kind": "per_group_n_not_stated", "study_id": s["id"],
                         "detail": (f"n printed only as a range {s.get('n_range_printed')!r}"
                                    if s.get("n_range_printed") else "no n printed"),
                         "consequence": "no check needing a per-group n can bind"})
    for v in account["variables"]:
        b = v.get("bounds") or {}
        if v.get("role") in ("measured_outcome", "derived_outcome") and b.get("source") == "not_stated":
            gaps.append({"kind": "bounds_not_stated", "variable_id": v["id"],
                         "consequence": "no bounds-based check may license `impossible`"})
        if v.get("role") in ("measured_outcome", "derived_outcome") and v.get("units_source") == "not_stated":
            gaps.append({"kind": "units_not_stated", "variable_id": v["id"]})
    for c in account["comparisons"]:
        if c.get("test_type_stated") is None:
            gaps.append({"kind": "test_not_named_for_comparison", "comparison_id": c["id"],
                         "detail": c.get("detailed_statistics_elsewhere")})
        if c.get("p_printed") is None and c.get("statistic_printed") is None:
            gaps.append({"kind": "no_test_statistic_or_exact_p_in_main_text",
                         "comparison_id": c["id"],
                         "detail": c.get("detailed_statistics_elsewhere")})
    for t in account.get("table_readings", []):
        if not t.get("n_per_column_stated"):
            gaps.append({"kind": "table_n_not_stated", "table_id": t["table_id"],
                         "consequence": "GRIM / count-percent checks on this table cannot bind"})
        for r in t.get("row_map", []):
            if r.get("statistic_form") == "mean_pm_unstated":
                gaps.append({"kind": "dispersion_kind_not_stated", "table_id": t["table_id"],
                             "row_label": r["row_label"]})
    for s in account.get("supplements_referenced", []):
        # THREE-VALUED, and the middle value is the point. `available` is False
        # only when the directory holds no supplement file at all -- provable,
        # and a real gap. It is None when we hold files but cannot prove which
        # of them "Table S3" names, which is a weaker statement and gets a
        # weaker kind: reporting it as `not_available` beside a docx sitting on
        # disk was a false sentence to a reader. A DENIED mention ("no
        # supplementary material is provided") is not a dependency at all.
        if s.get("denied"):
            continue
        if s.get("available") is False:
            gaps.append({"kind": "supplement_not_available", "label": s["label"],
                         "detail": s.get("referenced_for") or s.get("first_context")})
        elif s.get("available") is None:
            gaps.append({"kind": "supplement_held_but_not_matched_to_label",
                         "label": s["label"], "files_held": s.get("files_held") or [],
                         "detail": s.get("referenced_for") or s.get("first_context")})
    return gaps


def paper_identity(model_paper: dict, front: dict | None, problems: list[str]) -> dict:
    """The paper's bibliographic identity: front matter where the document has
    it, the model's reading otherwise, and the disagreement recorded.

    The first JATS run printed `.  . DOI not stated` for a paper whose
    `<article-meta>` carries title, journal, year and DOI. A deterministic read
    of the document's own front matter beats a model's transcription of it, and
    where the two differ the reader should see both rather than one.
    """
    paper = dict(model_paper or {})
    if not front:
        paper["identity_source"] = "model reading"
        return paper
    paper["identity_source"] = f"front matter ({front.get('source') or 'document'})"
    norm = lambda x: " ".join(str(x or "").split()).lower()
    for k in ("title", "journal", "doi", "year"):
        fv = front.get(k)
        if fv in (None, ""):
            continue
        if k == "year":
            try:
                fv = int(str(fv)[:4])
            except ValueError:
                continue
        mv = paper.get(k)
        if mv not in (None, "") and norm(mv) != norm(fv):
            problems.append(f"paper.{k}: the model read {mv!r}; the front matter says {fv!r}; "
                            "front matter kept")
        paper[k] = fv
    if front.get("author_list"):
        paper["authors"] = list(front["author_list"])
    return paper


def _reported_kind(c: dict) -> str:
    """`reported_in_kind` when the producer wrote one; else read off the label."""
    k = c.get("reported_in_kind")
    if k:
        return str(k)
    s = str(c.get("reported_in") or "").lower()
    for word, kind in (("abstract", "abstract"), ("discussion", "discussion"),
                       ("supp", "supplement"), ("table", "table"), ("fig", "figure"),
                       ("method", "methods")):
        if word in s:
            return kind
    return "results_text"


def demote_restatements(comparisons: list[dict], problems: list[str]) -> tuple[list[dict], list[dict]]:
    """A comparison is a result the paper reports WITH EVIDENCE. One that sits
    in the abstract or discussion and carries no printed statistic, exact p or
    threshold is a restatement of a result reported elsewhere: a CLAIM. It is
    moved to the claims list, marked `demoted_from_comparison`, never dropped.

    MEASURED 2026-09-06 on the first JATS paper: a linear pass filed 15 of its
    24 comparisons this way ("Inclusive leadership was positively associated
    with..." from the Abstract), each with free-text direction prose. A Results
    sentence WITHOUT a printed statistic is kept -- the statistic is usually in
    a table -- and the existing `no_test_statistic_or_exact_p_in_main_text` gap
    records it.
    """
    kept: list[dict] = []
    demoted: list[dict] = []
    for c in comparisons:
        has_evidence = any(c.get(k) not in (None, "") for k in ("statistic_printed", "p_printed", "p_threshold"))
        kind = _reported_kind(c)
        if has_evidence or kind not in ("abstract", "discussion"):
            kept.append(c)
            continue
        demoted.append({
            "id": f"claim:restated:{str(c.get('id') or '').split(':', 1)[-1]}",
            "text": c.get("quote") or "", "location": kind, "kind": "finding",
            "study_ids": [c["study_id"]] if c.get("study_id") else [],
            "hedged": None, "generalizes_beyond_sample": None, "causal": None,
            "demoted_from_comparison": c.get("id"),
            "significance": c.get("significance"), "direction": c.get("direction"),
            "direction_words": c.get("direction_words"),
            "quote_verified": c.get("quote_verified"), "quote_offset": c.get("quote_offset"),
        })
    if demoted:
        problems.append(f"{len(demoted)} comparison(s) restated a result in the abstract/discussion "
                        "with no printed statistic, p or threshold; filed as claims "
                        "(`demoted_from_comparison`), not as comparisons")
    return kept, demoted


# NO BOUNDS ARE DERIVED FROM LEVELS, and this note is the reason it stays that
# way. Proposed and withdrawn 2026-09-06: min/max of a variable's declared
# levels looked like a join on the paper's own structure. On the very paper it
# was written for, `fidelity_parents` lists 6 of its 7 printed levels while its
# stated bounds are 1..7 -- so the derived bound would have been TIGHTER than
# the truth and a mean of 6.5 would have read as impossible. A level list can
# be incomplete; a bound built from it supplies a premise rather than
# narrowing one (section 8d, Rule 1). Bounds come from the paper or not at all.


def template_problems(studies: list[dict], variables: dict,
                      paper_phases: list[dict] | None = None) -> list[str]:
    """Does each study's declared design have the parts that design requires?

    `schema.DESIGN_TEMPLATES` fixes the shape per design type. A `dose_response`
    study with two groups, or a `within_subjects` study with one phase, is either
    a mis-declared design or a missing part; either way a reader should see it
    rather than trust the label.
    """
    out: list[str] = []
    for s in studies:
        t = _schema.DESIGN_TEMPLATES.get(s.get("design_type") or "other")
        if t is None:
            out.append(f"{s['id']}: design_type {s.get('design_type')!r} has no template")
            continue
        if len(s.get("groups", [])) < t["min_groups"]:
            out.append(f"{s['id']}: {s.get('design_type')} needs >= {t['min_groups']} groups, "
                       f"has {len(s.get('groups', []))}")
        # A study that lists no phases of its own runs on the paper-level ones.
        n_phases = len(s.get("phases", [])) or len(paper_phases or [])
        if n_phases < t["min_phases"]:
            out.append(f"{s['id']}: {s.get('design_type')} needs >= {t['min_phases']} phases, "
                       f"has {n_phases}")
        if t["needs_numeric_factor"]:
            fids = {a["variable_id"] for g in s.get("groups", []) for a in g.get("assignments", [])}
            numeric = any(sum(1 for l in (variables.get(f) or {}).get("levels", [])
                              if l.get("value") is not None) >= 3 for f in fids)
            if not numeric:
                out.append(f"{s['id']}: dose_response needs a factor with >= 3 numeric levels "
                           "bound to its groups")
    return out


_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def sentence_accountability(text: str, sections: list[dict], account: dict,
                            roles: tuple[str, ...] = ("abstract", "discussion", "results")) -> dict:
    """Which sentences of the argument-bearing sections are covered by a quote
    the account carries (a claim, a result summary, an interpretation, a
    comparison, a value). Numerals do not cover claims; sentences do. Reported
    as counts, with the uncovered sentences listed, so that whether claim
    coverage needs its own per-sentence pass is a measurement, not a guess."""
    spans: list[tuple[int, int]] = []
    for c in account.get("claims", []):
        if c.get("quote_offset") is not None:
            spans.append((c["quote_offset"], c["quote_offset"] + len(c.get("text") or "")))
    for c in account.get("comparisons", []):
        if c.get("quote_offset") is not None:
            spans.append((c["quote_offset"], c["quote_offset"] + len(c.get("quote") or "")))
    for v in account.get("values", []):
        loc = v.get("location") or {}
        if loc.get("offset") is not None and loc.get("end") is not None:
            spans.append((loc["offset"], loc["end"]))
    for s in account.get("studies", []):
        for q in (s.get("result_summary_quotes") or []) + (s.get("interpretation_quotes") or []):
            sp = locate(q, text)
            if sp:
                spans.append(sp)
    out: dict[str, Any] = {"by_role": {}, "uncovered": []}
    for sec in sections:
        if sec.get("role") not in roles:
            continue
        body = text[sec["start"]:sec["end"]]
        # skip the heading line and pipe-table rows
        pos = sec["start"]
        for sent in _SENTENCE.split(body):
            st = text.find(sent, pos)
            if st < 0:
                continue
            en = st + len(sent)
            pos = en
            stripped = sent.strip()
            if len(stripped) < 25 or stripped.startswith(("#", "|", "<!--")):
                continue
            covered = any(a < en and st < b for a, b in spans)
            d = out["by_role"].setdefault(sec["role"], {"sentences": 0, "covered": 0})
            d["sentences"] += 1
            d["covered"] += covered
            if not covered:
                out["uncovered"].append({"role": sec["role"], "offset": st,
                                         "sentence": " ".join(stripped.split())[:200]})
    total = sum(d["sentences"] for d in out["by_role"].values())
    cov = sum(d["covered"] for d in out["by_role"].values())
    out["sentences"] = total
    out["covered"] = cov
    out["share_covered"] = round(cov / total, 4) if total else None
    return out


def _completeness(account: dict, accounting: list[dict], unparsed: list[dict]) -> dict:
    from . import structure as _structure
    # Idempotent: the same parse `assemble` already stamped, called again here
    # for its summary rather than kept in a second place.
    group_n = _structure.annotate_group_n(account.get("studies") or [])
    values = account["values"]
    in_scope = [r for r in accounting]
    n_scope = len(in_scope)
    by_disp: dict[str, int] = {}
    for r in in_scope:
        by_disp[r["disposition"]] = by_disp.get(r["disposition"], 0) + 1
    by_role: dict[str, dict] = {}
    for r in in_scope:
        d = by_role.setdefault(r.get("role", "?"), {"n": 0, "accounted": 0, "value": 0})
        d["n"] += 1
        d["accounted"] += r["disposition"] != "unaccounted"
        d["value"] += r["disposition"] in ("value", "duplicate_of_value")
    n_acc = sum(1 for r in in_scope if r["disposition"] != "unaccounted")
    n_val = sum(1 for r in in_scope if r["disposition"] in ("value", "duplicate_of_value"))
    # THE THREE BUCKETS (coordinator, 2026-09-05): extracted as a value at a
    # coordinate; explicitly dispositioned as a non-measurement; an unexplained
    # gap. The third is the hard completeness number a model cannot talk past.
    n_amb = sum(1 for r in in_scope if r["disposition"] == "ambiguous")
    buckets = {"placed_as_value": n_val,
               "dispositioned_non_measurement": n_acc - n_val - n_amb,
               "ambiguous_with_candidates": n_amb,
               "unplaced": n_scope - n_acc}

    def share(a: int, b: int) -> float | None:
        return round(a / b, 4) if b else None

    # THE THIRD AXIS IS ONLY AN AXIS WHERE THE DESIGN HAS ONE (D47). Requiring a
    # `phase_id` of every value read ajcp.70049 at 3.4% "full coordinate" while
    # NO study on that paper declares a phase at all -- the number was dominated
    # by an axis that is structurally unavailable, not by a table-reading
    # failure. On the two axes the paper does have, the same values are at 70%.
    # So `full_coordinate` requires study and group, and phase only from a value
    # whose own study declares one; the strict definition is kept beside it,
    # because dropping it would be the opposite error.
    phased = {s.get("id") for s in account.get("studies") or [] if s.get("phases")}
    def _full(v: dict, always_phase: bool) -> bool:
        c = v["coordinate"]
        if not (c.get("study_id") and c.get("group_id")):
            return False
        return bool(c.get("phase_id")) if (always_phase or c.get("study_id") in phased) else True
    coord_full = sum(1 for v in values if _full(v, False))
    coord_full_phase = sum(1 for v in values if _full(v, True))
    coord_sg = sum(1 for v in values if v["coordinate"].get("study_id")
                   and v["coordinate"].get("group_id"))
    coord_source: dict[str, int] = {}
    for v in values:
        k = v.get("coordinate_source") or "none"
        coord_source[k] = coord_source.get(k, 0) + 1
    coord_study = sum(1 for v in values if v["coordinate"].get("study_id"))
    with_var = sum(1 for v in values if v.get("variable_id"))
    qv: dict[str, int] = {}
    for coll in ("values", "comparisons", "claims"):
        for r in account[coll]:
            k = f"{coll}:{r.get('quote_verified')}"
            qv[k] = qv.get(k, 0) + 1
    cmps = account["comparisons"]
    return {
        "three_buckets": buckets,
        "numerals_in_scope": n_scope,
        # ONE FLOOR, THE SPLIT BESIDE THE TOTAL (Greg, 2026-09-06).
        "numerals_by_source": _by_source(in_scope),
        "numerals_in_scope_note": ("every numeric token outside the reference list and "
                                   "back matter (`numerals.index`) plus every cell of a "
                                   "table the text does not inline, article and supplement "
                                   "alike (`numerals.index_table_cells`); one model-free "
                                   "denominator, split by source in `numerals_by_source`"),
        "numerals_accounted": n_acc, "share_accounted": share(n_acc, n_scope),
        "numerals_bound_to_a_value": n_val, "share_bound_to_a_value": share(n_val, n_scope),
        "numerals_unaccounted": by_disp.get("unaccounted", 0),
        "by_disposition": dict(sorted(by_disp.items(), key=lambda kv: -kv[1])),
        "by_role": by_role,
        "values_total": len(values),
        "values_by_source": {s: sum(1 for v in values if v["source"] == s)
                             for s in sorted({v["source"] for v in values})},
        "values_with_variable": with_var, "share_values_with_variable": share(with_var, len(values)),
        "values_with_study": coord_study, "share_values_with_study": share(coord_study, len(values)),
        "values_with_study_and_group": coord_sg,
        "share_values_with_study_and_group": share(coord_sg, len(values)),
        "values_with_full_coordinate": coord_full,
        "share_values_with_full_coordinate": share(coord_full, len(values)),
        "values_with_full_coordinate_incl_phase": coord_full_phase,
        "share_values_with_full_coordinate_incl_phase": share(coord_full_phase, len(values)),
        "studies_declaring_a_phase": sorted(phased),
        "full_coordinate_note": (
            "`values_with_full_coordinate` counts a value carrying a study AND a group, "
            "and a phase ONLY where the value's own study declares one -- a design with "
            "no phases has no third axis to be missing, and requiring it read ajcp.70049 "
            "at 3.4% while none of its seven studies declares a phase at all. "
            "`values_with_full_coordinate_incl_phase` is the strict definition, kept "
            "beside it. `values_by_coordinate_source` says how each coordinate was "
            "reached: `declared_group_id` is the reading's own group id, `column_map` "
            "the pass-3 reading of the column, `caption_join` a declared group whose "
            "printed label the table's caption contains VERBATIM and UNIQUELY."),
        "values_by_coordinate_source": dict(sorted(coord_source.items())),
        "groups_with_a_parsed_n": group_n,
        "table_cells_total": sum(t["n_cells"] for t in account["document"]["tables"]),
        "table_cells_unparsed": len(unparsed),
        "comparisons_total": len(cmps),
        "comparisons_with_test_named": sum(1 for c in cmps if c.get("test_type_stated")),
        "comparisons_with_exact_p": sum(1 for c in cmps if c.get("p_printed")),
        "comparisons_with_threshold_only": sum(1 for c in cmps if c.get("p_threshold") is not None
                                               and not c.get("p_printed")),
        "claims_total": len(account["claims"]),
        "claims_linked_to_a_study": sum(1 for c in account["claims"] if c.get("study_ids")),
        "studies_total": len(account["studies"]),
        "variables_total": len(account["variables"]),
        "quote_verification": qv,
        "gaps_total": len(account["gaps"]),
    }


def assemble(doc: dict, p1: dict, p2: dict, p3: dict, residual: dict | None = None,
             provenance: dict | None = None, structure: dict | None = None,
             artifact_stamps: dict[str, str | None] | None = None,
             premise_reading: dict | None = None) -> dict:
    """The merged account. Pure: no I/O, no model.

    `structure` is the frozen structural account (`structure.py`) the downstream
    passes selected from, when there is one. Given it, three things happen here
    and nowhere else: artifacts read against a DIFFERENT structure are refused
    outright (`artifact_stamps`); every foreign id a reading or pass 3 emitted is
    nulled, kept as `<field>_as_read` and counted; and the account carries a
    `structure` block saying which version it selected from and whether the
    served document still matches.

    `premise_reading` is the model's reading of the five text premises
    (`premise_reading.py`), when that paid pass has been run for this paper. It
    is attached BEFORE the stamp, because the stamp is what consults it; absent,
    every premise is decided by the vocabularies exactly as before.
    """
    text = doc["text"]
    hay = _Hay(text)
    problems: list[str] = list(doc.get("problems") or [])

    # A VERDICT ABOUT THE MODEL'S OWN QUOTE CANNOT BE AUTHORED BY THE MODEL.
    # `premises.PIPELINE_ONLY` is the scaffold's `anatomy.PIPELINE_ONLY_FIELDS`:
    # the fields the pipeline writes and a pass may not, stripped from every
    # payload before assembly so that a model-supplied `premise` or
    # `bounds.verification` cannot arrive already stamped and fail open.
    from . import premises as _premises_strip
    forged = sum(_premises_strip.strip_pipeline_only(x)
                 for x in (p1, p2, p3, residual) if x)
    if forged:
        problems.append(
            f"{forged} pipeline-only field(s) ({', '.join(sorted(_premises_strip.PIPELINE_ONLY))}) "
            "were present in a pass payload and were stripped: a verdict about whether the "
            "model's own quote is real is not the model's to write")

    from . import structure as _structure
    closed: dict = {}
    if structure is not None:
        # REFUSED BEFORE ANYTHING IS READ. An account assembled from artifacts
        # built on two vocabularies measures the vocabulary change, not the
        # paper; the check therefore runs before the first value is built.
        if artifact_stamps is not None:
            _structure.refuse_mixed_versions(artifact_stamps, _structure.content_sha256(structure))
        closed = _structure.close_vocabulary(_structure.id_sets(structure),
                                             p3, residual or {}, doc.get("tables") or [])
        if closed["unbound_foreign_id"]:
            problems.append(
                f"closed vocabulary: {closed['unbound_foreign_id']} id(s) a reading or pass 3 "
                f"emitted are not in structure v{structure.get('version')} and were nulled "
                f"(kept as `<field>_as_read`): {closed['by_field']}")

    variables = {v["id"]: dict(v) for v in p2.get("variables", [])}
    # Group coordinates and phase coordinates onto the studies.
    gcoords: dict[tuple[str, str], list[dict]] = {}
    for gc in p2.get("group_coordinates", []):
        gcoords.setdefault((gc["study_id"], gc["group_id"]), []).extend(gc.get("assignments", []))
    pcoords: dict[tuple[str, str], dict] = {}
    for pc in p2.get("phase_coordinates", []):
        pcoords[(pc["study_id"], pc["phase_id"])] = {"variable_id": pc["variable_id"],
                                                     "level_id": pc["level_id"]}
    outcomes: dict[str, list[str]] = {}
    for ob in p2.get("outcome_bindings", []):
        outcomes.setdefault(ob["study_id"], []).extend(ob.get("variable_ids", []))
    studies: list[dict] = []
    for s in p1.get("studies", []):
        s2 = dict(s)
        s2["groups"] = [{**g, "assignments": gcoords.get((s["id"], g["id"]), [])}
                        for g in s.get("groups", [])]
        s2["phases"] = [{**p, **pcoords.get((s["id"], p["id"]), {})} for p in s.get("phases", [])]
        s2["outcome_variable_ids"] = outcomes.get(s["id"], [])
        for g in s2["groups"]:
            if not g["assignments"]:
                problems.append(f"{s['id']}/{g['id']}: no factor-level assignment from pass 2")
        studies.append(s2)
    for (sid, gid) in gcoords:
        if not any(st["id"] == sid and any(g["id"] == gid for g in st["groups"]) for st in studies):
            problems.append(f"pass 2 binds unknown group {sid}/{gid}")
    # THE GROUP'S n AS A NUMBER, PARSED FROM WHAT THE PAPER PRINTED. Every
    # declared group on ajcp.70049 has `n_printed: None` while its label IS the
    # string `n = 64 coalitions`, so a header like `Intervention (n = 34)` had
    # nothing to join against.
    _structure.annotate_group_n(studies)

    params_by_proc: dict[str, list[dict]] = {}
    for pp in p2.get("procedure_parameters", []):
        params_by_proc.setdefault(pp["procedure_id"], []).append(pp)
    procedures = [{**p, "parameters": params_by_proc.get(p["id"], [])}
                  for p in p1.get("procedures", [])]

    from . import interpret as _interpret
    doc["_studies"] = p1.get("studies", [])   # for the entries' group ids; not saved
    account_entries = _interpret.bind_entries(doc.get("tables") or [], list(variables.values()))
    # THE DECIMAL POINT IS A PROPERTY OF THE DOCUMENT, read once and applied to
    # every literal in it, so that one paper cannot be read under two grammars.
    decimal_sep = decimal_convention(text)
    table_values, unparsed = _table_values(doc, p3, variables, problems, decimal_sep)
    prose = _prose_values(p3.get("prose_values", []), text, hay, "prose", problems, decimal_sep)
    for v in prose:
        if v["location"]["kind"] in ("figure_caption", "table_caption", "table_footnote"):
            v["source"] = "caption"
    extra = _prose_values((residual or {}).get("new_values", []), text, hay, "residual", problems,
                          decimal_sep)
    values = table_values + prose + extra
    # Procedure parameters are values too: design settings at no group coordinate.
    for pp in p2.get("procedure_parameters", []):
        q = pp.get("quote") or ""
        span = locate(q, text)
        lit = read_literal(str(pp.get("printed") or ""), decimal_sep)
        values.append({
            "id": f"val:param:{pp['procedure_id'].split(':')[-1]}:{re.sub(r'[^a-z0-9]+', '_', pp['name'].lower()).strip('_')}",
            "statistic": "setting", "printed": str(pp.get("printed") or ""),
            "numeric": pp.get("numeric"), "decimals": lit["decimals"],
            "printed_form": lit["printed_form"],
            "units": pp.get("units"), "variable_id": pp.get("variable_id"),
            "coordinate": {"study_id": None, "group_id": None, "phase_id": None},
            "applies_to_all_groups": True, "source": "methods_parameter",
            "location": {"kind": "methods", "offset": span[0] if span else None,
                         "end": span[1] if span else None, "procedure_id": pp["procedure_id"],
                         "name": pp["name"]},
            "quote": q, "quote_verified": hay.verify(q).get("quote_verified"),
        })
    for pdsc in p2.get("population_descriptors", []):
        q = pdsc.get("quote") or ""
        span = locate(q, text)
        lit = read_literal(str(pdsc.get("printed") or ""), decimal_sep)
        values.append({
            "id": f"val:pop:{re.sub(r'[^a-z0-9]+', '_', pdsc['name'].lower()).strip('_')}",
            "statistic": "other", "printed": str(pdsc.get("printed") or ""),
            "numeric": pdsc.get("numeric"), "decimals": lit["decimals"],
            "printed_form": lit["printed_form"],
            "units": pdsc.get("units"), "variable_id": None,
            "coordinate": {"study_id": None, "group_id": None, "phase_id": None},
            "applies_to_all_groups": True, "source": "population",
            "location": {"kind": "methods", "offset": span[0] if span else None,
                         "end": span[1] if span else None, "name": pdsc["name"]},
            "quote": q, "quote_verified": hay.verify(q).get("quote_verified"),
        })
    # De-duplicate ids that collided.
    seen: dict[str, int] = {}
    for v in values:
        if v["id"] in seen:
            seen[v["id"]] += 1
            v["id"] = f"{v['id']}:{seen[v['id']]}"
        else:
            seen[v["id"]] = 0

    comparisons = [dict(c) for c in p3.get("comparisons", [])]
    _verify_quotes(comparisons, text, hay)
    claims = [dict(c) for c in p1.get("claims", [])]
    _verify_quotes(claims, text, hay, field="text")
    comparisons, demoted = demote_restatements(comparisons, problems)
    claims += demoted
    for v in variables.values():
        v["quote_verified"] = hay.verify(v.get("quote")).get("quote_verified")

    doc_slim = {k: v for k, v in doc.items() if k not in ("text", "original_text", "numerals", "_studies")}
    account: dict[str, Any] = {
        "schema_version": _schema.__name__ and "scaffold/0.1",
        "paper": paper_identity(p1.get("paper", {}), doc.get("front"), problems),
        "document": doc_slim,
        # ALWAYS PRESENT, None WHEN THERE IS NO STRUCTURE FILE. An absent key
        # would read to a consumer exactly like a structure it failed to record.
        "structure": None,
        "background": p1.get("background", {}),
        "subjects": p1.get("subjects", {}),
        "statistical_analysis": p1.get("statistical_analysis", {}),
        "procedures": procedures,
        "phases": list(p1.get("phases", []) or []),
        "studies": studies,
        "variables": list(variables.values()),
        "values": values,
        "comparisons": comparisons,
        "claims": claims,
        "figure_panels": p3.get("figure_panels", []),
        "table_readings": p3.get("table_readings", []),
        "supplements_referenced": [
            {**s, "referenced_for": next((r.get("referenced_for") for r in
                                          p1.get("supplements_referenced", [])
                                          if _norm_label(r.get("label")) == _norm_label(s["label"])),
                                         None)}
            for s in doc.get("supplements_referenced", [])],
        "unparsed_cells": unparsed,
        "table_entries": account_entries,
        "gaps": [],
        "accounting": [],
        "completeness": {},
        "problems": problems,
        "provenance": provenance or {},
    }
    # Pages: a reader verifies by page, so every located element carries one.
    from .document import page_at, section_at
    pages = doc.get("pages") or []
    secs = doc.get("sections") or []   # the handle when there are no pages
    for f in doc["figures"]:
        f["page"] = page_at(pages, f.get("start"))
        f["section"] = section_at(secs, f.get("start"))
    for v in values:
        loc = v.get("location") or {}
        if loc.get("kind") == "table_cell":
            t = next((t for t in doc["tables"] if t["id"] == loc.get("table_id")), None)
            v["page"] = t.get("page") if t else None
            v["section"] = (t.get("label") or t.get("id")) if t else None
        else:
            v["page"] = page_at(pages, loc.get("offset"))
            v["section"] = section_at(secs, loc.get("offset"))
    for c in comparisons:
        c["page"] = page_at(pages, c.get("quote_offset"))
        c["section"] = section_at(secs, c.get("quote_offset"))
    for c in claims:
        c["page"] = page_at(pages, c.get("quote_offset"))
        c["section"] = section_at(secs, c.get("quote_offset"))
    for v in variables.values():
        span = locate(v.get("quote") or "", text)
        v["page"] = page_at(pages, span[0] if span else None)
        v["section"] = section_at(secs, span[0] if span else None)
    for s2 in studies:
        for g in s2["groups"]:
            span = locate(g.get("n_quote") or "", text)
            g["n_page"] = page_at(pages, span[0] if span else None)
            g["n_section"] = section_at(secs, span[0] if span else None)
    # STEP 3: banner interpretation as a join on declared levels, beside the
    # model's own row reading. Reported per row and counted; never a verdict.
    if structure is not None:
        account["structure"] = _structure.account_block(structure, doc, closed)
        if account["structure"]["stale_document"]:
            problems.append(
                "stale document: the served text is not the one structure "
                f"v{structure.get('version')} was read from "
                f"({account['structure']['document_sha256'][:12]} then, "
                f"{(doc.get('source') or {}).get('text_sha256', '')[:12]} now); nothing was "
                "re-decomposed and the account says so in section 1")
    # THE ADMISSION DECISION, MADE ONCE AND WRITTEN ON THE ACCOUNT. Six readers
    # of `values` used to decide independently whether a value was safe to use,
    # from the same seven raw fields, and they disagreed. `premises.stamp` is
    # the one decision; every reader downstream is a lookup. It runs here --
    # after values and variables exist, before `_gaps` -- because `_gaps`,
    # `coverage.headline` and the render all read it.
    if premise_reading:
        account["premise_reading"] = premise_reading
    from . import premises as _premises
    _premises.stamp(account, text, inplace=True)
    account["gaps"] = _gaps(account, doc)
    account["template_problems"] = template_problems(studies, variables, account.get("phases"))
    accounting = account_numerals(doc, values, text)
    accounting, more = apply_residual(accounting, residual, {v["id"] for v in values})
    problems += more
    # A CLASSIFICATION, NOT A SUPPRESSION: every row stays, one moves bucket.
    classify_phase_labels(accounting, text, account)
    account["accounting"] = accounting
    account["completeness"] = _completeness(account, accounting, unparsed)
    if provenance and provenance.get("gap_curve"):
        account["completeness"]["gap_curve"] = provenance["gap_curve"]
    account["sentence_accountability"] = sentence_accountability(text, doc.get("sections") or [], account)
    # THE HEADLINE MEASURES, AND THE FLOOR IS NOT ONE OF THEM (D34). Imported
    # here rather than at module level because `coverage` reads this module's
    # sentence splitter and its quote locator -- one definition of each, and the
    # cycle stays unclosed by loading the consumer at its call site.
    from . import coverage as _coverage
    account["headline"] = _coverage.headline(account, text, doc)
    problems += list(account["headline"].get("problems") or [])
    account["completeness"]["sentences_in_argument_sections"] = account["sentence_accountability"]["sentences"]
    account["completeness"]["sentences_covered_by_a_quote"] = account["sentence_accountability"]["covered"]
    account["completeness"]["share_sentences_covered"] = account["sentence_accountability"]["share_covered"]
    account["integrity_problems"] = _schema.validate_account(account)
    # WHICH CODE BUILT THIS ACCOUNT. Not the provenance of the paper -- the
    # provenance of the ARITHMETIC. An account read later is a claim about the
    # code that wrote it, and until this stamp existed it carried no way to fail
    # that claim: the two headline artifacts read in the D47 diagnosis said
    # 65 of 162 where the code in the same tree said 120.
    from . import codestamp as _codestamp
    account["code"] = _codestamp.stamp()
    return account


_SENT_EDGE = re.compile(r"[.!?]\s+(?=[A-Z(])|\n\n")


def _sentence_around(text: str, offset: int, end: int, pad: int = 400) -> str:
    """The sentence (or table row) containing [offset, end), bounded by `pad`."""
    lo = max(0, offset - pad)
    hi = min(len(text), end + pad)
    before = text[lo:offset]
    after = text[end:hi]
    m = list(_SENT_EDGE.finditer(before))
    start = lo + (m[-1].end() if m else 0)
    m2 = _SENT_EDGE.search(after)
    stop = end + (m2.start() + 1 if m2 else len(after))
    return " ".join(text[start:stop].split())


def residual_rows(accounting: list[dict], limit: int | None = None, text: str | None = None,
                  pages: list[dict] | None = None) -> list[dict]:
    """The numerals still `unaccounted`, in READING ORDER, each with the whole
    sentence it sits in, its section role and its page.

    THIS IS A WORK QUEUE, NOT A RESIDUAL (Greg, 2026-09-05): each row is a
    number the paper printed that has not yet been placed, served back to a
    reader who now holds the scaffold. The question per row is only where it
    belongs -- a far easier task than first-pass extraction -- so the rows carry
    everything needed to answer it and nothing that invites re-reading the paper.
    """
    from .document import page_at
    rows = []
    for r in sorted((r for r in accounting if r["disposition"] == "unaccounted"),
                    key=lambda r: r["offset"]):
        row = {"numeral_id": r["id"], "printed": r["printed"], "role": r.get("role"),
               "context": r.get("context")}
        if text is not None:
            row["sentence"] = _sentence_around(text, r["offset"], r.get("end", r["offset"] + len(r["printed"])))
        if pages:
            row["page"] = page_at(pages, r["offset"])
        rows.append(row)
    return rows[:limit] if limit else rows
