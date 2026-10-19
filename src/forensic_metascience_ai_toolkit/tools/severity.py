"""
Shared severity vocabulary for all forensic tools.

Every tool result should carry a `severity` field drawn from SEVERITY_LEVELS
so downstream consumers (CLI rendering, the agent's findings schema, the
eval harness) can rely on a single enum.
"""

from __future__ import annotations

import math
from typing import Optional

IMPOSSIBLE = "impossible"
HIGHLY_SUSPICIOUS = "highly_suspicious"
SUSPICIOUS = "suspicious"
INDETERMINATE = "indeterminate"
CONSISTENT = "consistent"

SEVERITY_LEVELS = (
    IMPOSSIBLE,
    HIGHLY_SUSPICIOUS,
    SUSPICIOUS,
    INDETERMINATE,
    CONSISTENT,
)


# ---------------------------------------------------------------------------
# WHICH SEVERITIES ACCUSE, AND THE TWO ANSWERS TO THAT QUESTION
#
# The name `ACCUSATORY` was defined ELEVEN times across this codebase with zero
# imports between them, and it split into two member sets. The split was not a
# copy error -- it is two genuine concepts wearing one name, and unifying them
# into a single set would have been the wrong fix:
#
#   ACCUSES_AT_ALL   -- does this verdict say anything against the paper?
#                       Used where the question is "should a reader be warned",
#                       "should this be re-checked", "did we drop an accusation".
#   ACCUSATION_GRADE -- is this strong enough to be an accusation we would
#                       DEFEND? Used for pre-registered fire-rate thresholds and
#                       for sensitivity harnesses, where `suspicious` is
#                       deliberately below the bar.
#
# Both live here, built from the named constants, so the two can be told apart
# by name at every call site and neither can drift. `severity9.ACCUSATORY_MIN`
# is the numeric ladder's equivalent of ACCUSATION_GRADE; `secondlook` reads
# that one, and this module is the string vocabulary's authority.
#
# THE DEFECT THIS FIXED: `cli.py` carried the GRADE set under a comment reading
# "Severities that constitute an accusation against a paper" -- the at-all
# meaning -- so `warn_if_assumed` never warned when a `suspicious` verdict
# rested on an assumed data type. Every other module in the codebase agrees
# that `suspicious` accuses; the CLI disagreed with all of them, silently.
ACCUSES_AT_ALL = frozenset({IMPOSSIBLE, HIGHLY_SUSPICIOUS, SUSPICIOUS})

#: The higher bar. DELIBERATE where it is used, and both users say so in their
#: own words: `evaluation/corpus.py` carries it as the pre-registered threshold
#: from PREREGISTRATION.md section 4, beside `ACCUSATORY_SECONDARY` "so neither
#: can be quoted alone"; `simulation.py` reasons explicitly about injected flaws
#: "capped at `suspicious` -- below ACCUSATORY". Do not merge these into
#: ACCUSES_AT_ALL: that would silently move a pre-registered threshold.
ACCUSATION_GRADE = frozenset({IMPOSSIBLE, HIGHLY_SUSPICIOUS})

# Rich markup colors used by the CLI for each severity.
SEVERITY_COLORS = {
    IMPOSSIBLE: "red bold",
    HIGHLY_SUSPICIOUS: "red",
    SUSPICIOUS: "yellow",
    INDETERMINATE: "cyan",
    CONSISTENT: "green",
}

_LEGACY_ALIASES = {
    "high": HIGHLY_SUSPICIOUS,
    "moderate": SUSPICIOUS,
    "low": CONSISTENT,
    "ok": CONSISTENT,
}


def normalize_severity(value: str | None) -> str:
    """Map any legacy/variant severity string onto the canonical enum."""
    if not value:
        return INDETERMINATE
    v = value.strip().lower()
    if v in SEVERITY_LEVELS:
        return v
    return _LEGACY_ALIASES.get(v, INDETERMINATE)


def severity_from_consistency(consistent: bool) -> str:
    """Severity for pure possible/impossible checks (GRIM, GRIMMER, DEBIT...)."""
    return CONSISTENT if consistent else IMPOSSIBLE


def _has_nonfinite(value) -> bool:
    """True if `value` is, or contains, a NaN or an infinity."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return not math.isfinite(value)
    if isinstance(value, (list, tuple)):
        return any(_has_nonfinite(v) for v in value)
    return False


def refuse_if_nonfinite(**named_values) -> Optional[dict]:
    """Refuse (return an `indeterminate` result) if any input is non-finite.

    A reported statistic is never NaN or +/-inf: those arise only from OUR
    failures -- a cell that would not parse, a division by a zero SD, an
    overflow -- so a consistency tool handed one must DECLINE, not manufacture a
    verdict about the paper from it. Without this guard the raw functions did
    exactly the thing this toolkit exists to prevent: `grim_test_percentage`,
    `check_sd_range` and `debit_test` returned `impossible` (a false accusation)
    on a NaN, and `grim_test`/`grimmer_test`/`recalc_chi_squared` raised on the
    int() conversion (a crash that a batch loop or internal caller could swallow
    into a false all-clear).

    The MCP/registry surface is already protected by the measured-value gate in
    `ToolSpec.call`; this closes the SAME hole on the raw functions, which are
    reachable directly (CLI commands, tool-to-tool calls, tests). Refusing a
    non-finite input can never blunt a real detection -- no honest paper reports
    a mean of NaN -- so the guard is safe in both directions.

    Returns None when every value is finite, so callers write:
        guard = refuse_if_nonfinite(mean=mean, n=n)
        if guard is not None:
            return guard
    """
    bad = sorted(k for k, v in named_values.items() if _has_nonfinite(v))
    if not bad:
        return None
    return {
        "consistent": False,
        "severity": INDETERMINATE,
        "applicable": False,
        "error": (
            f"Non-finite input(s): {bad}. A NaN or infinite value is not a "
            "reported statistic -- it comes from a failed extraction or "
            "computation on our side -- so this check declines to judge."
        ),
        "explanation": (
            "Declined: one or more inputs "
            f"({', '.join(bad)}) is NaN or infinite. That is a signal about our "
            "own pipeline, not about the paper, so no consistency verdict is "
            "issued."
        ),
        "methodology": "Non-finite input guard (severity.refuse_if_nonfinite).",
    }
