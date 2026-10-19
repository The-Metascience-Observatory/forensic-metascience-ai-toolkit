"""Quarantine for forensic checks not yet validated on simulated + real data.

Greg's rule (2026-08-09): a check whose ACCUSATORY behaviour is delicate or
ambiguous -- resting on a calibration we have not yet tested against known
ground truth -- must not emit an accusation. It still RUNS and reports its
computed statistics (so it can be validated through the normal path), but any
accusatory verdict is forced down to `indeterminate` and the result is tagged,
until a simulation + real-paper validation lifts the quarantine.

This is the "run but never accuse" mechanism, and it is deliberately one-way:

  * A quarantined check can NEVER be the source of a false accusation -- the
    worst output in this toolkit. An accusatory verdict (`suspicious`,
    `highly_suspicious`, `impossible`) becomes `indeterminate`, a tolerated
    refusal.
  * Its numbers stay visible. `severity_before_quarantine` records exactly what
    it WOULD have said, so a validation run can score the check against known
    ground truth without re-plumbing it, and a reader can see the raw signal.
  * A NON-accusatory verdict (`consistent`, `indeterminate`) is left untouched:
    the concern is over-escalation, not a false all-clear, and quarantine's job
    is only to withhold accusations.

Releasing a check from quarantine is a one-line deletion at its call site once
its false-positive rate is measured on the flawed-paper simulator and a labeled
real-paper set. See `carlisle-family-calibration-decisions_2026-08-09.md`.
"""

from __future__ import annotations

from .severity import (ACCUSES_AT_ALL, INDETERMINATE)

# The verdicts quarantine withholds. Everything softer than `suspicious` is not
# an accusation and passes through unchanged. Shared definition, not a copy.
ACCUSATORY = ACCUSES_AT_ALL


def quarantine(result: dict, reason: str) -> dict:
    """Withhold a delicate check's accusation, preserving its computed numbers.

    If `result["severity"]` is accusatory, records it as
    `severity_before_quarantine`, forces `severity` to `indeterminate`, and adds
    `quarantined = True` and `quarantine_reason = reason`. A non-accusatory
    result is returned untouched. Idempotent and in-place (also returned for
    chaining).
    """
    if result.get("quarantined"):
        return result
    sev = result.get("severity")
    if sev in ACCUSATORY:
        result["severity_before_quarantine"] = sev
        result["severity"] = INDETERMINATE
        result["quarantined"] = True
        result["quarantine_reason"] = reason
    return result
