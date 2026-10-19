"""Group a paper's findings for the review list: one tool family, one place.

Dan, 2026-10-18: "if there were 10 GRIM test failures in one table, that
should be a group. And if there's a bunch of GRIM test failures in a page or
several pages of text, that should be a group." The list must not be
overwhelmed by a hundred rows from one table.

The rule, and the only one:

  * same TOOL FAMILY (`tool_specs.family_of`: grim_check and grim_percentage
    are both `grim`), and
  * same PLACE: one table (from the finding's anchors, else a "Table N" in its
    location), or, for a finding with no table, PDF pages within one page of
    the group's range.

Two or more findings make a group; a lone one stays a row. A finding with no
recorded tool or no place is never grouped -- absence is not a shared place.
Decisions stay per finding: a group is a way of listing, never a verdict.

Applied server-side (`workbench.service.paper`) BEFORE pagination, so a
group is never split across pages.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

_TABLE = re.compile(
    r"\b((?:supplementary\s+|suppl\.?\s+|e)?table\s*s?\d+[a-z]?)\b", re.I)


def _norm_table(text: Any) -> str | None:
    s = " ".join(str(text or "").split())
    if not s or s.lower().startswith("cref"):
        return None
    m = _TABLE.search(s)
    return " ".join(m.group(1).lower().split()) if m else s.lower()


def tool_family(issue: dict) -> str | None:
    tool = issue.get("tool")
    if not tool or issue.get("tool_source") in (None, "not_recorded"):
        return None
    try:
        from .tool_specs import family_of
        return family_of().get(str(tool), str(tool))
    except Exception:  # noqa: BLE001
        return str(tool)


def table_of(issue: dict) -> str | None:
    """The one table this finding is about, or None (none, or several)."""
    basis = issue.get("location_basis") or {}
    tables = {t for t in (_norm_table(x) for x in basis.get("tables") or []) if t}
    if len(tables) == 1:
        return tables.pop()
    if tables:
        return None
    m = _TABLE.search(str(issue.get("location") or basis.get("location") or ""))
    return " ".join(m.group(1).lower().split()) if m else None


def pages_of(issue: dict) -> list[int]:
    basis = issue.get("location_basis") or {}
    return sorted({int(p) for p in basis.get("pages") or []
                   if isinstance(p, (int, float)) and not isinstance(p, bool) and p >= 1})


def _sev(issue: dict) -> int:
    v = issue.get("severity_9")
    return v if isinstance(v, int) else 0


def _meta(family: str, unit: str, members: list[dict]) -> dict:
    tools = {m.get("tool") for m in members}
    key = f"{family}|{unit}|" + "|".join(sorted(str(m.get("id")) for m in members))
    return {
        "id": "grp:" + hashlib.sha1(key.encode()).hexdigest()[:12],
        "family": family,
        "tool": tools.pop() if len(tools) == 1 else family,
        "unit": unit,
        "n": len(members),
        "severity_9": max((_sev(m) for m in members), default=0) or None,
        "provisional": any(m.get("severity_is_provisional") for m in members),
    }


def group_issues(issues: list[dict]) -> list[list[dict]]:
    """ENTRIES in list order: each a list of findings, one finding unless grouped.

    Ordered by worst severity, then by first finding id, so a group sits
    where its worst member would. Grouped members carry `group` (`_meta`)."""
    entries: list[list[dict]] = []
    by_table: dict[tuple, list[dict]] = {}
    by_pages: dict[str, list[tuple[int, int, dict]]] = {}
    for issue in issues:
        family = tool_family(issue) if issue.get("kind") == "numeric" else None
        table = table_of(issue) if family else None
        pages = pages_of(issue) if family and not table else []
        if table:
            by_table.setdefault((family, table), []).append(issue)
        elif pages:
            by_pages.setdefault(family, []).append((pages[0], pages[-1], issue))
        else:
            entries.append([issue])
    for (family, table), members in by_table.items():
        if len(members) > 1:
            meta = _meta(family, table[:1].upper() + table[1:], members)
            for m in members:
                m["group"] = meta
        entries.append(members if len(members) > 1 else members[:1])
    for family, items in by_pages.items():
        items.sort(key=lambda x: (x[0], x[1]))
        clusters: list[tuple[int, int, list[dict]]] = []
        for lo, hi, issue in items:
            if clusters and lo <= clusters[-1][1] + 1:
                c = clusters[-1]
                clusters[-1] = (c[0], max(c[1], hi), c[2] + [issue])
            else:
                clusters.append((lo, hi, [issue]))
        for lo, hi, members in clusters:
            if len(members) > 1:
                unit = f"p. {lo}" if lo == hi else f"pp. {lo}–{hi}"
                meta = _meta(family, unit, members)
                for m in members:
                    m["group"] = meta
            entries.append(members)
    for entry in entries:
        entry.sort(key=lambda m: (-_sev(m), str(m.get("id"))))
    entries.sort(key=lambda e: (-max(_sev(m) for m in e), str(e[0].get("id"))))
    return entries
