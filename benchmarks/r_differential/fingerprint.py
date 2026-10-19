"""Which source files each differential verified, and their hashes.

A differential result describes the code it ran against and nothing else. The
2026-08-26 results were recorded without saying which code that was, and by
2026-10-18 both `grim.py` and `sprite.py` had changed underneath them while the
JSON still read "326,785 agree" -- a stale number with nothing to show it was
stale (LESSONS: stale numbers). So each result now records the SHA-256 of every
source file its verdict depends on, and `tests/test_r_differential_pin.py`
(free, milliseconds) fails when any of them has changed since the last run.

The lists are the transitive imports inside `tools/` of the function each
script calls. Add a file here when the tool starts importing it.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_TOOLS = "src/forensic_metascience_ai_toolkit/tools"

GRIM_SOURCES = (
    f"{_TOOLS}/grim.py",
    f"{_TOOLS}/rounding.py",
    f"{_TOOLS}/severity.py",
)

# sprite.py imports grim (granularity_ceiling, canonical_data_type) at call time.
SPRITE_SOURCES = (
    f"{_TOOLS}/sprite.py",
    *GRIM_SOURCES,
)


def sha256_of(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def code_sha256(sources: tuple[str, ...]) -> dict[str, str]:
    """{repo-relative path: sha256} for each file, in the order given."""
    return {rel: sha256_of(rel) for rel in sources}
