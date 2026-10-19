"""Reassurance language the review must never use about the paper.

Rulebook rules 1 and 9: a consistent check is not clearance, and high
baseline similarity is the red flag, never reassurance. The eval caught these
phrases only per fixture (`must_not_say`), after the fact; on 2026-10-13 a
grok review shipped "consistent with randomisation" and nothing in the
pipeline said so. This list is scanned over every finding's title and
description and the adjudicator's summary; a hit is a
`producer_constraint_problems` entry and a report limitation. The text is
never rewritten: the reader sees the phrase and the flag together.
"""

from __future__ import annotations

import re

PATTERNS: tuple[str, ...] = (
    r"consistent with (?:successful )?randomi[sz]ation",
    r"consistent with random (?:allocation|assignment)",
    r"baseline (?:characteristics|values|comparisons|dispersion|similarity)[^.]*\bconsistent\b",
    r"no suspicious uniformity",
    r"groups (?:were|are) well[- ]balanced",
    r"results (?:are|appear) (?:sound|trustworthy)",
    r"no (?:significant|notable) (?:anomalies|inconsistencies) (?:were )?found",
    r"statistics (?:are|were|appear)[^.]*\bconsistent\b and (?:verifiable|reproducible)",
    r"(?:participant|patient|animal) flow[^.\n]{0,60}(?:reconciles|is consistent|is fully accounted for)\b",
)
_COMPILED = tuple(re.compile(p, re.I) for p in PATTERNS)


def scan(findings: list[dict] | None, adjudication: dict | None = None) -> list[dict]:
    """One problem per (row, field) that uses a reassurance phrase."""
    out: list[dict] = []
    for i, f in enumerate(findings or []):
        if not isinstance(f, dict):
            continue
        if (f.get("adjudication") or {}).get("action") in ("discarded", "merged"):
            continue          # not in the report; the reader never sees it
        for field in ("title", "description"):
            text = str(f.get(field) or "")
            for rx in _COMPILED:
                m = rx.search(text)
                if m:
                    out.append({"index": i, "slug": f.get("slug"),
                                "code": "reassurance_language", "field": field,
                                "match": m.group(0),
                                "problem": (f"'{m.group(0)}' reads as clearance of the "
                                            "paper (rulebook rules 1 and 9)")})
                    break
    summary = str((adjudication or {}).get("summary") or "")
    for rx in _COMPILED:
        m = rx.search(summary)
        if m:
            out.append({"index": None, "slug": "adjudication.summary",
                        "code": "reassurance_language", "field": "summary",
                        "match": m.group(0),
                        "problem": (f"'{m.group(0)}' reads as clearance of the "
                                    "paper (rulebook rules 1 and 9)")})
            break
    return out
