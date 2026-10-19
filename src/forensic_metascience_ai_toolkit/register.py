"""The statistics register: what the model says it found, held to an independent floor.

GREG, 2026-08-15:

    "What if agent 1 extracts all checkable sets of values to its own table
     (or probably tables, plural). That way, the 'table denominator' can be
     the sum of the 'prose table' and the 'tables proper'."

WHY THE MODEL AND NOT A REGEX
-----------------------------
`completeness._body_items` enumerates prose statistics by pattern. MEASURED
2026-08-15 against two independent references:

  * against statcheck's APA-format population, across five papers, its recall is
    60/60 -- PERFECT. The `nhst`, `chi2` and `p_value` patterns are complete.
  * against an independently-designed pattern sweep on Romano, 22 of 24
    candidate spans are UNCOVERED, because four ordinary reporting conventions
    have no pattern at all:

        (M = 2.26, SD = 1.32)     mean and SD both labelled inside the parens
        M = 4.44 (1.57)           mean labelled, SD bare
        β = 0.24                  standardised coefficients
        AOR 0.55 (0.32-0.94)      an estimate and interval without "95% CI"

    `mean_sd_prose` matches only NUMBER-then-paren-then-SD, so it takes
    `4.21 (SD 0.9)` and misses every form above. One Romano sentence carries six
    mean/SD pairs; the enumerator found two items in the entire paper.

The phrasing space is unbounded. Four patterns can be added today and a fifth
convention arrives next month, which is the syntactic-proxy treadmill this
repository has been on all week. Reading a sentence and recognising a reported
statistic is what the model is actually good at.

AND WHY THE MODEL CANNOT BE TRUSTED WITH THE DENOMINATOR
-------------------------------------------------------
THE FINDER SHOULD BE THE MODEL. THE DENOMINATOR MUST BE INDEPENDENT OF THE
FINDER. If the model both enumerates and checks, coverage is
`(what it checked) / (what it decided was checkable)` -- both sides from one
source -- and a model that overlooks thirty statistics reports full coverage of
the ten it found. The metric IMPROVES as the enumeration degrades. That is this
project's signature failure, in the one number a reader acts on.

So the regex set changes job. It stops being the enumerator and becomes the
TRIPWIRE: it is complete on APA-format statistics, so anything it finds and the
register does not list is a hole in the register, detectable for free. A weak
enumerator makes a poor denominator and a perfectly good floor.

THE FLOOR IS CHECKED VALUE BY VALUE, NOT BY COUNT. A register with the same
number of rows as the regex found, listing different statistics, has missed
things; comparing totals would call that agreement.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

__all__ = ["validate", "row_problems", "floor_check", "SOURCES"]

#: Where a statistic was read from. `prose` is the one the floor applies to --
#: table and supplement rows have their own census and are not the regex's job.
SOURCES = ("prose", "table", "supplement", "figure", "abstract")


def _numbers(value: Any) -> list[str]:
    """Every numeric token in a row's reported values, as printed."""
    out: list[str] = []
    if isinstance(value, dict):
        for v in value.values():
            out += _numbers(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            out += _numbers(v)
    elif isinstance(value, (int, float)):
        out.append(repr(value).rstrip("0").rstrip(".") if isinstance(value, float) else str(value))
    elif isinstance(value, str):
        out += re.findall(r"[-+]?\d*\.?\d+", value)
    return [t for t in out if t.strip()]


def row_problems(row: dict) -> list[str]:
    """What is structurally wrong with one register row.

    CHECKABILITY IS A COLUMN, NEVER A FILTER. A statistic no tool can check is a
    row carrying a reason, not an absence -- that is the whole difference between
    a denominator and a self-report.
    """
    p: list[str] = []
    if not isinstance(row, dict):
        return ["row is not an object"]
    if not str(row.get("quote") or "").strip():
        p.append("no quote, so the value cannot be verified against the paper")
    if not _numbers(row.get("values")):
        p.append("no numeric value recorded")
    src = str(row.get("source") or "")
    if src not in SOURCES:
        p.append(f"source {src!r} is not one of {SOURCES}")
    ch = row.get("checkable")
    if not isinstance(ch, dict):
        p.append("no `checkable` block: a row must say which tools apply OR why none does")
    else:
        tools = [t for t in (ch.get("tools") or []) if str(t).strip()]
        reason = str(ch.get("reason") or "").strip()
        if not tools and not reason:
            p.append("`checkable` names no tool and gives no reason for there being none")
    return p


def _verify(row: dict, text: str | None) -> dict:
    """Is this row's quote in the paper, and its values in the quote?

    Two separate questions, reported separately. A quote that is not in the
    paper is a fabrication risk; a value that is not in its own quote is a
    transcription error. Neither drops the row -- both mark it.
    """
    from .computation import locate
    from .quotes import _contains_bounded

    quote = str(row.get("quote") or "").strip()
    nums = _numbers(row.get("values"))
    out: dict[str, Any] = {"quote_located": None, "values_in_quote": None, "problems": []}

    if not text:
        out["problems"].append(
            "no paper text was available, so this row is unverified BY US -- our gap, "
            "not a defect in the row")
        return out

    out["quote_located"] = bool(quote) and _contains_bounded(quote, text)
    if quote and not out["quote_located"]:
        squashed = re.sub(r"\s+", " ", quote)
        out["quote_located"] = bool(re.search(re.escape(squashed).replace(r"\ ", r"\s+"), text))
    if quote and not out["quote_located"]:
        out["problems"].append("the quoted span was not found in the paper text")

    missing = [n for n in nums if not locate(n, quote)]
    out["values_in_quote"] = not missing
    if missing:
        out["problems"].append(
            f"value(s) not present in the row's own quote: {', '.join(missing[:4])}")
    return out


def floor_check(rows: Iterable[dict], floor_items: Iterable[dict],
                text: str | None = None) -> dict:
    """Does the register account for everything the regex enumerator found?

    VALUE BY VALUE. For each floor item, its printed span must appear in some
    register row's quote. A register that lists a different set of the same size
    has missed things, and comparing counts would score that as agreement.

    The floor applies to PROSE rows only. Table and supplement statistics have
    their own cell census; holding the register to a body-text regex for those
    would manufacture a shortfall out of a category mismatch.
    """
    quotes = " \n ".join(str(r.get("quote") or "") for r in rows
                         if str(r.get("source") or "") in ("prose", "abstract"))
    floor = [f for f in floor_items if isinstance(f, dict)]
    unmatched = []
    for f in floor:
        raw = re.sub(r"\s+", " ", str(f.get("raw") or "")).strip()
        if not raw:
            continue
        if re.search(re.escape(raw).replace(r"\ ", r"\s+"), quotes):
            continue
        unmatched.append({"raw": raw, "kind": f.get("kind"), "offset": f.get("offset")})

    ok = not unmatched
    note = ("every statistic the independent enumerator found is accounted for in "
            "the register" if ok else
            f"{len(unmatched)} statistic(s) the independent regex enumerator found do "
            "NOT appear in any register row. The register is incomplete: these were "
            "located mechanically, so they are present in the paper and the model "
            "did not list them.")
    return {"ok": ok, "n_floor": len(floor), "n_unmatched": len(unmatched),
            "unmatched": unmatched[:20], "note": note}


def validate(rows: Iterable[dict] | None, *, text: str | None = None,
             floor_items: Iterable[dict] | None = None,
             provenance: dict | None = None) -> dict:
    """Validate a model-produced register and report what it can be trusted for.

    NOTHING IS DROPPED. A row that fails verification is marked and counted,
    because a register that silently discards its own bad rows is a register
    whose denominator improves every time the model makes a mistake.

    `absent` distinguishes "the model emitted no register" from "the model
    emitted an empty one". The first is our wiring or its refusal; the second is
    a claim about the paper.
    """
    if rows is None:
        return {
            "absent": True, "n_rows": 0, "rows": [],
            "note": ("no statistics register was emitted by this run, so the prose "
                     "denominator falls back to the regex enumerator. That is a gap "
                     "in what we can say about coverage, not a paper with no "
                     "statistics."),
            "floor": floor_check([], floor_items or [], text),
            "provenance": dict(provenance or {}),
        }

    seen: dict[str, int] = {}
    out_rows: list[dict] = []
    for i, row in enumerate(rows):
        r = dict(row) if isinstance(row, dict) else {"malformed": repr(row)[:120]}
        r.setdefault("id", f"reg:{i}")
        r["problems"] = row_problems(row if isinstance(row, dict) else {})
        r["verification"] = _verify(r, text)
        key = re.sub(r"\s+", " ", str(r.get("quote") or "")).strip().lower()[:160]
        if key and key in seen:
            r["duplicate_of"] = out_rows[seen[key]]["id"]
        elif key:
            seen[key] = len(out_rows)
        out_rows.append(r)

    uniq = [r for r in out_rows if not r.get("duplicate_of")]
    checkable = [r for r in uniq
                 if isinstance(r.get("checkable"), dict)
                 and [t for t in (r["checkable"].get("tools") or []) if str(t).strip()]]
    verified = [r for r in uniq
                if r["verification"].get("quote_located")
                and r["verification"].get("values_in_quote")]
    by_source: dict[str, int] = {}
    for r in uniq:
        by_source[str(r.get("source") or "?")] = by_source.get(str(r.get("source") or "?"), 0) + 1

    return {
        "absent": False,
        "rows": out_rows,
        "n_rows": len(out_rows),
        "n_duplicates": len(out_rows) - len(uniq),
        "n_unique": len(uniq),
        "n_checkable": len(checkable),
        "n_verified": len(verified),
        "n_malformed": sum(1 for r in out_rows if r["problems"]),
        "by_source": by_source,
        "floor": floor_check(out_rows, floor_items or [], text),
        # INHERITED, NOT ASSUMED. A register built from pdfplumber text, or from
        # text the glyph scanner has quarantined, carries values that may be
        # wrong in ways no arithmetic can detect -- a lost minus sign reads as an
        # ordinary number. The register must say which text it came from.
        "provenance": dict(provenance or {}),
        "note": ("`n_unique` is the count of statistics THE AGENT LOCATED, not of "
                 "statistics the paper contains. Enumeration recall is unmeasured; "
                 "the floor below is a lower bound on it, not an estimate of it."),
    }
