"""Canonical journal names, one string at a time (spec findings_v2.md §11).

Ported 2026-08-21 from the website repo's `data_ingestor.py`
(`_normalize_journal_key` + `normalize_journal_names`, ~line 1313), reworked
from DataFrame to single string. Mapping data vendored whole at
`data/journal_name_mappings.json` (33,354 abbreviations + 26 variant forms,
counted 2026-08-21).

An unknown journal passes through unchanged — a null `journal_normalized`
would read as "journal unknown" when the truth is "no mapping entry"
(LESSONS #1). Two guards travel with the expansion, ported verbatim because
each fixed a measured false positive on the website corpus:

  - known-full-name guard: a canonical full name is never re-expanded, even
    when its key collides with an abbreviation for a DIFFERENT journal
    ("Social Psychology" is a real journal, not an abbreviation of "Social
    Psychology Quarterly").
  - qualifier-expansion guard: NLM entries that merely append a location
    qualifier or subtitle ("BMJ" -> "BMJ (Clinical research ed.)") are
    refused — the input is already canonical. Truncated-word completions
    still expand ("Death Stud" -> "Death Studies": the word continues, no
    separator).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "journal_name_mappings.json"


def normalize_key(name: str) -> str:
    """Lookup form of a journal name: lowercase, periods stripped, spaces collapsed.

    This is what makes matching case- and period-insensitive; the JSON keys
    are stored already normalized this way.
    """
    s = str(name).lower().replace(".", "").strip()
    return re.sub(r"\s+", " ", s)


@lru_cache(maxsize=1)
def _mappings() -> tuple[dict[str, str], dict[str, str], frozenset[str]]:
    """(abbreviations, variant_forms, known_full_names) from the vendored file.

    A missing or unreadable file degrades to passthrough rather than raising —
    but silently, which is why `mapping_counts` exists:
    `tests/test_journal_names.py` asserts the tables are populated, so an
    empty vendored file fails the suite loudly instead of shipping a
    normalizer that never normalizes (LESSONS #4).
    """
    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}, frozenset()
    if not isinstance(raw, dict):
        return {}, {}, frozenset()
    abbreviations = raw.get("abbreviations")
    variant_forms = raw.get("variant_forms")
    abbreviations = abbreviations if isinstance(abbreviations, dict) else {}
    variant_forms = variant_forms if isinstance(variant_forms, dict) else {}
    known_full = frozenset(
        normalize_key(v)
        for v in list(abbreviations.values()) + list(variant_forms.values())
        if isinstance(v, str)
    )
    return abbreviations, variant_forms, known_full


def mapping_counts() -> dict[str, int]:
    """How many entries each table actually loaded — the known-positive probe."""
    abbreviations, variant_forms, _ = _mappings()
    return {"abbreviations": len(abbreviations),
            "variant_forms": len(variant_forms)}


def normalize(journal: str) -> str:
    """Canonical full name for `journal`, or `journal` itself (passthrough).

    Never returns None or "" for a non-blank input. Blank/non-string input
    is returned as given — the caller decides what an absent journal means.
    """
    if not isinstance(journal, str) or not journal.strip():
        return journal
    original = journal.strip()
    normalized = normalize_key(original)
    abbreviations, variant_forms, known_full = _mappings()

    # Step 1: abbreviation expansion, unless the name is already canonical.
    if normalized not in known_full and normalized in abbreviations:
        expansion = abbreviations[normalized]
        exp_norm = normalize_key(expansion)
        is_qualifier_expansion = (
            exp_norm.startswith(normalized)
            and len(exp_norm) > len(normalized)
            and exp_norm[len(normalized)] in " ;:,("
        )
        if not is_qualifier_expansion:
            return expansion

    # Step 2: variant-form standardization.
    if normalized in variant_forms:
        return variant_forms[normalized]

    # Step 3: HTML entity fix.
    if "&amp;" in original:
        return original.replace("&amp;", "&")

    return original
