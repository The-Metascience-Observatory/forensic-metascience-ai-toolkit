"""Which accusations need a second look, decided by code, judged by the model.

GREG, 2026-08-13: "insofar as there are problems related with inadequate sanity
checks on findings that require judgment, couldn't you wire this capability into
the editorial agent?"

Yes -- but not by asking the editorial agent to be more careful. The checks that
catch a bad accusation split cleanly in two, and only one half belongs to a
model:

    DECIDABLE IN CODE      did a tool compute this, or did the model?
                           is the quote actually in the paper?
                           does the severity rest on a bound the paper stated?

    REQUIRES JUDGEMENT     is this discrepancy explained by a reporting
                           convention we do not model? does the paper's own
                           framing make this legitimate?

The first half must not be left to the model, because a model asked to check
itself is the same reasoner that made the claim. The instruction "re-read your
single-cell findings before keeping them" has been in the stage-2 prompt for
weeks and cannot be verified, skipped or counted. This module makes that half a
LIST, attached to the findings stage 2 is already triaging, so it arrives
whether or not anyone remembers to look.

WHY IT IS SCOPED TO ACCUSATIONS, AND WHY IT IS SMALL. Applying every decidable
marker to every finding flags 54.2% of them, and a worklist covering half the
output trains its reader to skip it -- the failure this repository has already
named for its completeness gate. Scoped to findings that ACCUSE the paper and
carry a risk marker, the archive yields:

MEASURED 2026-08-13 over 626 deduplicated archived findings, 256 of them
accusatory:

    64  the model did the arithmetic, no registered tool did
    22  quote not located in the paper
     4  rests on a bound the paper did not state
    --
    80  distinct accusations flagged: 31.2% of accusations, 12.8% of findings
        (72 suspicious, 4 impossible, 4 highly_suspicious)

The first count read 95 while this marker fired on the LABEL `manual`, and 31 of
those 95 were false -- the finding carried no number for a model to have
computed. It is now decided by contents; see `computation.did_unaided_arithmetic`.
Every count above is of the ARCHIVE, which predates the vocabulary split, so
expect them to move on the first run that emits the new techniques.

IT CHANGES NO SEVERITY. It is a worklist, not a verdict. Marking a finding says
"a specific, named thing about the evidence is weak", never "this is wrong" --
and the cardinal rule cuts both ways here: a marker that silently downgraded a
true finding would be as damaging as the false accusation it aims to prevent.
"""

from __future__ import annotations

from typing import Any

# ONE READER FOR THE ROW, not a third local spelling. Two defects in
# `is_accusatory` (the v1 string vocabulary against v2 integers, 2026-08-29;
# reading `severity` on producer rows that carry only `provisional_severity`,
# 2026-09-01) and a third in `worklist` (`f.get("id")` on rows that carry
# `finding_id`, live on 4 of 10 control runs of 2026-09-03/04) were all the same
# mistake: this module restating what a finding row looks like. `finding_view`
# is the single statement of that, and `is_accusatory` IS its function --
# `inspect.getsource(secondlook.is_accusatory)` reads the shared body, which
# takes the threshold from `severity9.ACCUSATORY_MIN` rather than copying it.
from .finding_view import effective_severity, is_accusatory, ref  # noqa: F401
#: The v1 word vocabulary, re-exported (not redefined) for callers and tests
#: that speak it; `finding_view.is_accusatory` is what decides.
from .tools.severity import ACCUSES_AT_ALL as ACCUSATORY  # noqa: F401

#: Each marker names a WEAKNESS IN THE EVIDENCE, decidable without judgement,
#: and says what would settle it. The text is written for the model that has to
#: act on it, not for a log.
MARKERS: dict[str, str] = {
    "model_computed":
        "no registered tool produced this number -- the model did the "
        "arithmetic itself, so it has not been through the guards that make a "
        "severity safe to state. If a tool covers this check, re-run it with "
        "the tool. If none does, say in `triage` what you did to satisfy "
        "yourself the arithmetic is right, or drop the finding to "
        "`indeterminate`.",
    "quote_not_located":
        "the quoted passage could not be found in the paper. Either the values "
        "were transcribed rather than copied, or our extraction differs from "
        "what the model read. Re-read the source span before keeping this.",
    "assumed_bound":
        "the severity rests on a scale bound the paper never stated. A "
        "misspecified bound INVERTS these checks rather than weakening them, "
        "so confirm the range from the paper or cap the finding at "
        "`suspicious`.",
}


def markers(finding: dict) -> list[str]:
    """The decidable weaknesses in one finding's evidence. Never a verdict."""
    if not isinstance(finding, dict):
        return []
    if not is_accusatory(finding):
        return []

    inputs = finding.get("inputs")
    inputs = inputs if isinstance(inputs, dict) else {}
    out: list[str] = []

    # CORRECTED 2026-08-13, and this marker was WRONG when first shipped. It
    # fired on the LABEL `technique: "manual"` -- and 35.2% of the archived
    # findings carrying that label contain no arithmetic at all: a
    # data-availability statement, a figure legend naming the wrong protein, an
    # asterisk against the wrong p. Reading a label instead of the contents is
    # entry 1 of LESSONS.md, committed hours earlier, by me.
    #
    # `computation.did_unaided_arithmetic` decides it, and the legacy label is
    # decided by its contents so this guard cannot silently stop guarding on a
    # run that keeps emitting `manual`.
    from . import computation as _comp
    if _comp.did_unaided_arithmetic(finding):
        out.append("model_computed")

    # `absent` WAS MISSING, and it is the verdict that means nothing was found.
    #
    # `quotes.classify` emits five verdicts and this listed three of them, none
    # of which was `absent`. MEASURED on the live ajcp run: 12 of 34 findings
    # carry `absent`, including 2 of the 3 accusatory rows -- so the docket's
    # note asserted that all three "quote a passage located in the paper" while
    # two of them quoted nothing the search could find.
    #
    # `stitched` IS DELIBERATELY NOT HERE, and taking the complement of
    # `viewer_facts.LOCATED_VERDICTS` -- which excludes it -- would be wrong.
    # `stitched` means "not contiguous, but EVERY NUMBER IN IT IS IN THE PAPER";
    # it is 46% of quotes in the module's own corpus, it under-claims by design,
    # and its 22 hand-adjudicated siblings contained NO FABRICATIONS. The
    # evidence a stitched quote rests on IS in the paper, so flagging it would
    # fire this marker on nearly half of all accusations and drown the two
    # verdicts that mean something is genuinely missing. The renderer labels
    # stitched separately, which is where that distinction belongs -- a reader
    # should not go looking for the exact sentence, and that is not the same as
    # the evidence being absent.
    if str(finding.get("quote_verified") or "") in (
            "unverified", "absent", "", "none"):
        out.append("quote_not_located")

    bound = str(inputs.get("bound_source") or "")
    if bound and bound not in ("stated", "None"):
        out.append("assumed_bound")

    return out


def worklist(findings: list[dict]) -> dict[str, Any]:
    """Every accusation with a named weakness, for stage 2 to adjudicate.

    Returned as a structure stage 2 receives alongside the findings themselves,
    so the obligation cannot be met by not noticing it.
    """
    rows, counts = [], {}
    n_accusatory = 0
    # HOW MANY ACCUSATIONS COULD HAVE THEIR BOUNDS CHECKED AT ALL.
    # `assumed_bound` reads `inputs.bound_source`, which is ABSENT on 165 of the
    # 167 findings in this repo's v2 archive -- so the marker is structurally
    # silent on 98.8% of rows, and the clean note nonetheless asserted that
    # every accusation "rests on stated bounds". That is a positive claim made
    # from missing evidence, which is the failure this module exists to catch.
    n_bounds_checkable = 0
    for f in (findings or []):
        if not isinstance(f, dict):
            continue
        if is_accusatory(f):
            n_accusatory += 1
            if str((f.get("inputs") or {}).get("bound_source") or ""):
                n_bounds_checkable += 1
        m = markers(f)
        if not m:
            continue
        for k in m:
            counts[k] = counts.get(k, 0) + 1
        # `ref` and `effective_severity`, NOT `f.get("id")` / `f.get("severity")`.
        # This runs BEFORE `adjudicate.apply`, on rows that carry `finding_id`
        # and `provisional_severity` and neither of the keys it used to read,
        # so the worklist shipped `{"id": null, "severity": null, ...}` and
        # named a weakness in an accusation without saying WHICH accusation.
        # Verified in prompt.adjudicator.md of litvak02/05/06/07 (v1.22.0).
        rows.append({
            "id": ref(f) or None,
            "severity": effective_severity(f),
            "location": f.get("location"),
            "markers": m,
            "what_to_do": [MARKERS[k] for k in m],
        })
    return {
        "n_accusatory": n_accusatory,
        "n_flagged": len(rows),
        "by_marker": counts,
        "items": rows,
        "note": _note(len(rows), n_accusatory, n_bounds_checkable),
    }


def _note(n: int, n_acc: int, n_bounds_checkable: int = 0) -> str:
    if not n_acc:
        return "No finding accuses the paper, so there is nothing to re-check."
    if not n:
        # ONLY WHAT WAS ACTUALLY CHECKED. This used to assert that every
        # accusation "rests on stated bounds" whenever no marker fired -- but
        # `assumed_bound` reads `inputs.bound_source`, absent on 165 of 167
        # archived findings, so on almost every row the clause was inferred
        # from a field nobody had filled in. The real bounds gate is
        # `prepass._bounds_are_stated`, which REFUSES the check rather than
        # annotating it; this marker is coverage recovery, and its silence is
        # not evidence.
        unchecked = n_acc - n_bounds_checkable
        bounds = ("and rest on stated bounds" if not unchecked else
                  f"and none records an assumed bound -- though {unchecked} of "
                  f"them state no bound provenance at all, so that clause is "
                  f"unverified for those")
        return (f"All {n_acc} accusation(s) were computed by a registered tool, "
                f"quote a passage located in the paper, {bounds}. Nothing is "
                "flagged for a second look.")
    return (f"{n} of {n_acc} accusation(s) carry a named weakness in their "
            "evidence. Each is listed with what would settle it. This is a "
            "worklist, not a verdict: none of these is wrong because it is "
            "listed, and a marker you resolve should be recorded in `triage` "
            "like any other triage decision.")
