"""The account's values as one long-form CSV row each.

WHY A CSV AT ALL. `account.json` is the record and `account.md` is the reading of
it; neither is what a person with a spreadsheet, or a check that wants every
(mean, n) pair for one variable, actually needs. The account is already
normalised -- every value IS a row at a coordinate -- so the long form is a
projection of it and not a second representation.

IT ADDS NOTHING. Every column is a field the account already carries or a
rendering of one (`location`), and the test that matters asserts the row count is
exactly `len(account["values"])`: a row per value, no filtering, no expansion, no
row for anything that is not a value. A file that dropped rows would be a
coverage claim nobody made, and one that added them would be an invention.

EACH ROW CARRIES WHAT WOULD OTHERWISE HAVE TO BE LOOKED UP ELSEWHERE: which
structure version the ids belong to, and which code wrote the file. A CSV
outlives the directory it was written in, and a value id means nothing without
the vocabulary it was drawn from (D43) -- the same reason `account.headline.json`
now carries a code stamp (D47).
"""

from __future__ import annotations

import csv
import io

from . import codestamp as _codestamp

#: Fixed and ordered. A column added in the middle silently shifts every reader.
COLUMNS: tuple[str, ...] = (
    "value_id", "study_id", "group_id", "phase_id", "variable_id", "level_id",
    "statistic", "value", "printed", "units", "source", "location",
    "quote_verified", "coordinate_source", "structure_version", "code_commit",
)


def _location(v: dict) -> str:
    """One cell naming where the value is, in the form its own kind takes.

    A table cell is (table, row, col) -- a byte offset would be meaningless for
    it, and `numerals.index_table_cells` says why: its coordinate is the cell,
    not a position in the text. Prose carries the offset it was located at.
    """
    loc = v.get("location") or {}
    kind = loc.get("kind") or "?"
    if kind == "table_cell":
        return f"{loc.get('table_id')} r{loc.get('row')} c{loc.get('col')}"
    if loc.get("offset") is not None:
        return f"{kind}@{loc.get('offset')}"
    if loc.get("procedure_id"):
        return f"{kind}:{loc['procedure_id']}"
    return kind


def rows(account: dict) -> list[dict]:
    """One dict per value, keyed by `COLUMNS`. Pure: no I/O, no model."""
    st = account.get("structure") or {}
    code = account.get("code") or {}
    version = st.get("version")
    commit = code.get("code_commit") or code.get("sha256")
    out: list[dict] = []
    for v in account.get("values") or []:
        c = v.get("coordinate") or {}
        out.append({
            "value_id": v.get("id"),
            "study_id": c.get("study_id"),
            "group_id": c.get("group_id"),
            "phase_id": c.get("phase_id"),
            "variable_id": v.get("variable_id"),
            "level_id": v.get("level_id"),
            "statistic": v.get("statistic"),
            "value": v.get("numeric"),
            "printed": v.get("printed"),
            "units": v.get("units"),
            "source": v.get("source"),
            "location": _location(v),
            "quote_verified": v.get("quote_verified"),
            "coordinate_source": v.get("coordinate_source"),
            "structure_version": version,
            "code_commit": commit,
        })
    return out


def values_csv(account: dict) -> str:
    """The long form as CSV text. An absent field is an EMPTY cell, never the
    string `None`: a reader cannot tell a literal `None` from a value."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(COLUMNS), lineterminator="\n",
                       extrasaction="raise")
    w.writeheader()
    for r in rows(account):
        w.writerow({k: ("" if r.get(k) is None else r[k]) for k in COLUMNS})
    return buf.getvalue()


def code_stamp_of(account: dict) -> dict:
    """What wrote this account, for a caller that wants to say so."""
    return account.get("code") or _codestamp.stamp()
