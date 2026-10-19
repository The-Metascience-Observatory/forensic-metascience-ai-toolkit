"""One reader for a finding row, whatever shape it arrived in.

THE DEFECT CLASS THIS CLOSES. A module reads a finding-row field under a name,
or with a value vocabulary, that the producing path does not use. Every
consumer had spelled its own answer to "which row is this" and "how severe is
it", and the two sides of each spelling were written months apart, so only one
side moved. Three instances shipped in `secondlook.py` alone in five weeks; the
third -- `"id": f.get("id")` on rows that carry `finding_id` -- put
`{"id": null, "severity": null}` into the adjudicator's worklist on 4 of the 10
clean-control runs of 2026-09-03/04 (`fmt-litvak/original/litvak02,05,06,07`).
The same month: `evaluation/agreement._band` banded all 285 rows of those runs
"clears" (51 accuse), and `viewer_facts.evidence_ledger` reported
`accusatory_without_a_validated_check: 0` on a bundle whose true count was 5.

THE FOUR SHAPES A ROW TAKES, all live today:

    producer row     `parallel.analyze_paper_parallel` BEFORE `adjudicate.apply`
                     (the shape `secondlook.worklist` is handed): `finding_id`,
                     `provisional_severity` (int 1-9 or None), and NO `severity`
                     key at all.
    adjudicated row  `findings.v2.json`: `finding_id`; `severity` int 1-9, or
                     None meaning discarded / merged / pass; `severity_is_provisional`.
    viewer card      `bundle._v2_container`: `id` = the finding_id, `severity`
                     rendered as the STRING "S<n>" (or None), `severity_9` int.
    legacy v1 row    archived `findings.json`: `id`, `severity` one of the
                     five tool words (`tools/severity.py`).

ABSENT AND None ARE DIFFERENT FACTS, and conflating them resurrects cleared
findings. A row with no `severity` key has not been adjudicated, so its
provisional level is the only level it has. A row whose `severity` IS None has
been adjudicated and discarded (adjudicate.py:366/423/432 write exactly that),
and its provisional level is the claim the adjudicator just rejected.

Two ladders, deliberately not translated into one another (findings_v2.md
section 0): the 1-9 ranking accuses at `severity9.ACCUSATORY_MIN` and only on
an `outcome: problem` row; the five-word tool enum accuses per
`tools.severity.ACCUSES_AT_ALL`. This module reads both; it mints neither.
"""

from __future__ import annotations

import re
from typing import Any

from . import severity9
from .tools.severity import ACCUSES_AT_ALL

#: `bundle._v2_container` renders a 1-9 rung as "S<n>" for display. Recognised
#: here so a viewer-side reader gets the same answer as a pipeline-side one.
_CARD_LEVEL = re.compile(r"^S([1-9])$")


def ref(row: Any) -> str:
    """The row's identity, whichever spelling it carries.

    `finding_id` is the v2 content hash and the only join key (findings_v2.md
    section 1: `slug` is "display only; never a join key"). `id` is the v1 key
    and the viewer card's copy of the finding_id. `slug` is last, for a
    producer row that has not yet been through `assign_finding_ids`.
    """
    if not isinstance(row, dict):
        return ""
    for key in ("finding_id", "id", "slug"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def effective_severity(row: Any) -> Any:
    """The severity value this row currently carries, under the absent-vs-None
    rule: the `severity` key when present (None included -- that is a discard),
    else `provisional_severity`. Returned RAW: an int, a v1 word, an "S<n>"
    card string, or None."""
    if not isinstance(row, dict):
        return None
    if "severity" in row:
        return row["severity"]
    return row.get("provisional_severity")


def severity_level(row: Any) -> int | None:
    """The 1-9 rung, or None when the row carries none (v1 words included)."""
    value = effective_severity(row)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 9 else None
    if isinstance(value, str):
        m = _CARD_LEVEL.match(value)
        if m:
            return int(m.group(1))
    return None


def is_accusatory(row: Any) -> bool:
    """Does this row assert something against the paper?

    On the 1-9 ladder the threshold is the ladder's own constant,
    `severity9.ACCUSATORY_MIN`, read from `severity9` rather than copied -- a
    second copy is how the vocabulary drifted before. Outcome is required as
    well as level: a `pass` at level 4 accuses nobody. A v1 row is judged by
    the five-word enum's own authority, `ACCUSES_AT_ALL`.
    """
    if not isinstance(row, dict):
        return False
    level = severity_level(row)
    if level is not None:
        return (str(row.get("outcome") or "") == "problem"
                and level >= severity9.ACCUSATORY_MIN)
    value = effective_severity(row)
    return isinstance(value, str) and value in ACCUSES_AT_ALL
