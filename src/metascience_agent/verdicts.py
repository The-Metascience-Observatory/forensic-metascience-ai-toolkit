"""The run-level verdict: what it is called, and what earns it.

WHY THE WORDS CHANGED (Greg, 2026-08-11). `trustworthy | questionable |
untrustworthy` makes a claim about the PAPER. This system does not know whether
a paper is trustworthy. It knows whether the numbers a paper prints reconcile
with each other and with the statistics reported beside them, which is a much
narrower thing and is the only thing any of the checks measure.

The defect is worst at the accusatory end, and that is why all three words moved
rather than only the top one. `untrustworthy` is the single most consequential
string this system can emit, and it asserts exactly what the disclaimer spends
four paragraphs saying we cannot assert. Neutralising `trustworthy` while
leaving `untrustworthy` in place would have fixed the harmless end.

    reconciles          the checkable numbers reconcile
    unresolved          something could not be settled, and it is named
    does_not_reconcile  the paper's own numbers contradict each other, and the
                        contradiction reaches what the paper claims

The vocabulary is the project's own idiom already: the model prose the stage-2
prompt holds up as an example reads "forty-one of the forty-three checkable
values reconcile with the statistics reported alongside them". It is also what
Heathers (2025) defines the field as doing -- evaluating research CONSISTENCY,
not adjudicating trust.

-----------------------------------------------------------------------------
WHAT `reconciles` NOW ALLOWS, AND WHY THAT IS NOT A LOWERING OF THE BAR
-----------------------------------------------------------------------------
A `suspicious` finding no longer disqualifies the top verdict (Greg's decision,
same date). Under the old vocabulary that rule was unavoidable: a paper called
`trustworthy` while carrying a suspicious finding would have been a
contradiction in terms, because the word claimed something about the whole
paper.

Under the new one the rule falls out rather than being an exception. Our ladder
defines `suspicious` as A QUESTION RATHER THAN A DETERMINATION -- the rung that
still reads as "worth asking about" -- and a paper whose arithmetic reconciles
can carry open questions. What still disqualifies is a SURVIVING determination:
an `impossible` or `highly_suspicious` finding, or claims the paper calls
significant that do not survive correction for their own family.

The obligation that comes with it: a `reconciles` verdict carrying suspicious
findings must SAY SO in the same breath. Silently upgrading a paper with three
open questions to the top rung would be the false all-clear, arrived at from a
new direction.
"""

from __future__ import annotations

from typing import Any, Iterable

#: The verdicts, best-reconciling first.
VERDICTS: tuple[str, ...] = ("reconciles", "unresolved", "does_not_reconcile")

#: The words 34 archived reports were written with. Every consumer reads through
#: `canonical()`, because a rename that breaks every bundle already on disk is
#: not a rename, it is a deletion. MEASURED: 27 `questionable`, 5
#: `untrustworthy`, 0 `trustworthy` -- the top rung was never once emitted,
#: which is its own finding and the reason the calibration section exists.
LEGACY: dict[str, str] = {
    "trustworthy": "reconciles",
    "questionable": "unresolved",
    "untrustworthy": "does_not_reconcile",
}

#: One sentence each, for the reader who meets the word cold. Deliberately says
#: what was CHECKED, never what the paper is worth.
MEANING: dict[str, str] = {
    "reconciles": (
        "The numbers this analysis could check reconcile with each other and "
        "with the statistics printed beside them. That is a statement about "
        "arithmetic, not about the quality or the honesty of the work, and open "
        "questions may still be listed below."
    ),
    "unresolved": (
        "Something could not be settled -- an anomaly that does not resolve "
        "either way, an extraction we could not confirm, or a check that could "
        "not run on the claim that matters. What it was is named. It is not a "
        "finding of misconduct, and it is not a negative result: the middle "
        "rung of three means we could not tell, which is a fact about this "
        "analysis and not about the paper."
    ),
    "does_not_reconcile": (
        "The paper's own numbers contradict one another, and the contradiction "
        "reaches a result the paper depends on. This is a statement about the "
        "arithmetic as printed. It is not a finding of misconduct, and the "
        "commonest cause of it is a reporting or transcription error."
    ),
}

#: The severities that are DETERMINATIONS rather than questions. These, and only
#: these, keep a paper off the top rung.
_DISQUALIFYING = ("impossible", "highly_suspicious")

#: The rung that is explicitly a question. Present in the findings, allowed at
#: `reconciles`, and required to be stated when it is.
OPEN_QUESTION = "suspicious"


def canonical(verdict: Any) -> str | None:
    """Map any verdict, old or new, onto the current vocabulary.

    Returns None for a word that is neither -- which a caller must render as
    "unrecognised", never silently coerce to one of the three. A verdict the
    viewer cannot place is a corruption of the single field a reader acts on,
    and guessing at it would hide that.
    """
    v = str(verdict or "").strip().lower()
    if v in VERDICTS:
        return v
    return LEGACY.get(v)


def is_legacy(verdict: Any) -> bool:
    """True for a report written before the rename. Worth showing a reader:
    the words changed, the report did not."""
    return str(verdict or "").strip().lower() in LEGACY


def qualifies_as_reconciles(findings: Iterable[dict] | None,
                            n_claims_lost_to_correction: int | None = 0,
                            principal_claim_checkable: bool = True) -> dict:
    """Does this run's evidence support the top verdict, and what must be said?

    Returns `{"qualifies": bool, "blockers": [...], "open_questions": int,
    "must_state": str}`. `must_state` is the sentence a `reconciles` verdict
    owes the reader when open questions survive -- computed here rather than
    left to the narrative, because the whole risk of relaxing the rule is that
    the questions stop being mentioned.
    """
    rows = [f for f in (findings or []) if isinstance(f, dict)]
    sev = [str(f.get("severity") or "").strip().lower() for f in rows]

    blockers: list[str] = []
    determinations = [s for s in sev if s in _DISQUALIFYING]
    if determinations:
        blockers.append(
            f"{len(determinations)} finding(s) at "
            f"{', '.join(sorted(set(determinations)))} survived triage -- these "
            "are determinations, not questions")
    if n_claims_lost_to_correction:
        blockers.append(
            f"{n_claims_lost_to_correction} claim(s) the paper calls significant "
            "do not survive correction for their own family")
    if not principal_claim_checkable:
        blockers.append(
            "the paper's principal claim was not checkable, so nothing here "
            "reconciles it either way")

    open_q = sum(1 for s in sev if s == OPEN_QUESTION)
    must_state = ""
    if not blockers and open_q:
        must_state = (
            f"The numbers reconcile, and {open_q} question"
            f"{'s' if open_q != 1 else ''} remain{'' if open_q != 1 else 's'} "
            "open. Those are set out below and none of them establishes a "
            "contradiction in the paper's own figures."
        )
    return {"qualifies": not blockers, "blockers": blockers,
            "open_questions": open_q, "must_state": must_state}
