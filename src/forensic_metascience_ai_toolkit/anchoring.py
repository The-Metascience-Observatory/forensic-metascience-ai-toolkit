"""Where a stage-2 accusation gets its evidence, and what it may claim without one.

THE OBJECT THIS EXISTS FOR. Two runs of the same paper at byte-identical prompt
and schema (Romano, 2026-08-11; `scratchpad/romano_variability_fable_2026-08-11.md`, local scratch, not tracked)
produced one `suspicious` finding that appeared in exactly one of them:

    "Fixed slopes omit a variance component known to bias 1-1-1 multilevel
     indirect effects"
    severity suspicious · confidence medium · warrant field_norm
    stage1_finding_ids: []            <- no sweep ancestor
    no tool call behind it            <- nothing computed
    zero mentions anywhere in the other run's report

An accusation born whole in the editorial pass, resting on a methodological
norm the reviewer supplied, with a 50% chance of existing at all. Under this
project's cardinal rule -- a false accusation against an honest paper is the
worst output there is -- that is the most dangerous shape a finding can have.

WHY THE OBVIOUS RULE IS WRONG, AND THIS ONE IS NARROWER. "Clamp every stage-2
finding with no stage-1 ancestor" was the first proposal. MEASURED over the
archive: 7 of 89 editorial findings are unanchored, 3 of them accusatory. But
reading those three shows they are not one class:

  * `Results text reverses the direction of the lorazepam-hypertension
    association against its own table` -- confidence HIGH, names Table 3's
    Lorazepam row and the Results sentence that contradicts it. A text-vs-table
    contradiction is exactly what this toolkit exists to catch, it is
    checkable by any reader in one glance, and no tool in the kit produces it.
    Clamping this is a pure loss.
  * `Outcome substitution: self-reported ideation presented as evidence...` --
    a construct-validity argument. Interpretive, confidence medium.
  * the fixed-slopes finding above -- `warrant: field_norm`.

The discriminator is already in the schema. `warrant` names WHOSE standard a
finding invokes, and `field_norm` means "a standard WE supply that this paper
never accepted" -- the only class, in `warrants.py`'s own words, "that can hold
a paper to something its design never owed". A finding that is BOTH unanchored
AND resting on our own norm has no paper-side evidence whatsoever: not a sweep
result, not arithmetic, not the paper's own commitment. It is an appeal to
authority. That may be worth SAYING; it is not worth ACCUSING on.

So there are two mechanisms here, deliberately separated:

  ANNOTATE (all findings)  record whether an ancestor exists and say so. The
                           lorazepam finding keeps its severity and gains a
                           visible note that it came from the editorial pass
                           with nothing behind it. Provenance, not punishment.

  CLAMP (one narrow case)  unanchored AND `field_norm` AND accusatory ->
                           `indeterminate`. Fires on exactly ONE of the 89
                           archived findings. Narrow on purpose: the cost of a
                           clamp is a real finding silenced, and the archive
                           says only one object needs it.

This composes with, and does not duplicate, `warrants.clamp_supplied_norms`,
which caps `field_norm` at `suspicious` for every finding regardless of anchor.
This one takes the subset that also has no ancestor down one further rung, to
the tier that means "we could not settle this" -- which is what an unbacked
norm claim honestly is.
"""
from __future__ import annotations

from typing import Any

#: Severities that ACCUSE. Below these a finding reports rather than charges,
#: and an unbacked report is a much smaller problem than an unbacked charge.
from .tools.severity import ACCUSES_AT_ALL as ACCUSATORY  # one definition; see severity.py

#: Where the clamp lands. `indeterminate` is the refusal tier -- "we looked and
#: could not settle it" -- which is the honest description of a norm claim with
#: no evidence behind it. Deliberately NOT `consistent`: we are not asserting
#: the paper is fine, only that we cannot support the charge.
UNANCHORED_CEILING = "indeterminate"

#: The warrant that can be held against a paper that never agreed to it. Kept as
#: a string rather than imported so a rename in `warrants.py` fails loudly in
#: `tests/test_anchoring.py` rather than silently disabling this clamp -- the
#: house failure mode is a guard that stops firing without saying so.
SUPPLIED_WARRANT = "field_norm"

ANCHOR_KINDS = ("sweep_ancestor", "dangling_ancestor", "none")

ANCHOR_MEANING = {
    "sweep_ancestor": (
        "cites at least one stage-1 finding that exists -- the editorial pass "
        "built this on something the sweep actually produced"),
    "dangling_ancestor": (
        "cites stage-1 finding ids that are not in this run's sweep. Treated as "
        "UNANCHORED: a citation that does not resolve is not evidence, and "
        "reading it as one would be the most easily faked anchor of all"),
    "none": (
        "cites no stage-1 finding. The editorial pass raised this from its own "
        "reading of the paper; nothing in the sweep points at it"),
}


def _stage1_ids(result: dict) -> set[str]:
    """Ids the sweep actually emitted, for resolving citations."""
    findings = (result or {}).get("findings")
    if isinstance(findings, dict):
        findings = findings.get("findings")
    out: set[str] = set()
    for f in findings or []:
        if isinstance(f, dict) and f.get("id"):
            out.add(str(f["id"]))
    return out


def anchor_of(finding: dict, known_ids: set[str]) -> dict:
    """Does this editorial finding rest on anything the sweep produced?

    A DANGLING CITATION IS NOT AN ANCHOR. Ids are checked against the sweep's
    actual output rather than merely counted, because the failure this guards
    against is a finding asserting provenance it does not have, and an
    unchecked id list is the cheapest possible way to assert it.
    """
    cited = finding.get("stage1_finding_ids")
    cited = [str(x) for x in cited] if isinstance(cited, list) else []
    resolved = [x for x in cited if x in known_ids]
    if resolved:
        kind = "sweep_ancestor"
    elif cited:
        kind = "dangling_ancestor"
    else:
        kind = "none"
    return {
        "anchored": kind == "sweep_ancestor",
        "kind": kind,
        "cited": cited,
        "resolved": resolved,
        "meaning": ANCHOR_MEANING[kind],
    }


def annotate_anchoring(result: dict) -> dict:
    """Stamp every editorial finding with where its evidence came from.

    Runs on EVERY finding and changes no severity. The clamp below is a separate
    call on a much smaller set: knowing that a finding came from the editorial
    pass unaided is useful to a reader whether or not it is accusatory, and a
    reader who is told is not being protected from anything -- they are being
    given the provenance to judge it themselves.
    """
    summary: dict[str, Any] = {
        "n_findings": 0, "n_anchored": 0, "n_unanchored": 0,
        "n_dangling": 0, "unanchored_accusations": [], "by_kind": {},
    }
    # `report_obj` IS THE KEY PRODUCTION USES. Reading `report` alone is how two
    # previous clamps returned at their first line on every real run while their
    # tests passed on hand-built fixtures. `report` stays as the fallback those
    # fixtures and the archive replay rely on.
    report = result.get("report_obj")
    if not isinstance(report, dict):
        report = result.get("report")
    findings = report.get("findings") if isinstance(report, dict) else None
    if not isinstance(findings, list):
        return summary

    known = _stage1_ids(result)
    for f in findings:
        if not isinstance(f, dict):
            continue
        summary["n_findings"] += 1
        res = anchor_of(f, known)
        f["anchor"] = res["kind"]
        f["anchored"] = res["anchored"]
        summary["by_kind"][res["kind"]] = summary["by_kind"].get(res["kind"], 0) + 1
        if res["anchored"]:
            summary["n_anchored"] += 1
            continue
        summary["n_unanchored"] += 1
        if res["kind"] == "dangling_ancestor":
            summary["n_dangling"] += 1
        if str(f.get("severity") or "") in ACCUSATORY:
            summary["unanchored_accusations"].append({
                "title": str(f.get("title") or "")[:120],
                "severity": f.get("severity"),
                "warrant": f.get("warrant"),
                "kind": res["kind"],
            })
    return summary


def clamp_unanchored_norms(result: dict) -> dict:
    """Cap an accusation that has neither an ancestor nor the paper's assent.

    THE ONLY CASE: no resolvable stage-1 finding behind it, `field_norm` as its
    warrant, and a severity that accuses. Every other unanchored finding keeps
    its severity and carries the annotation instead.

    Writes the same visible `severity_source` block the other clamps write, and
    for the same reason: a severity quietly lowered hides both the correction
    and a model that is systematically over-calling. A reader must be able to
    see that we pulled this one down, and why.
    """
    summary: dict[str, Any] = {
        "n_findings": 0, "n_candidates": 0, "n_clamped": 0, "clamps": [],
    }
    report = result.get("report_obj")
    if not isinstance(report, dict):
        report = result.get("report")
    findings = report.get("findings") if isinstance(report, dict) else None
    if not isinstance(findings, list):
        return summary

    known = _stage1_ids(result)
    for f in findings:
        if not isinstance(f, dict):
            continue
        summary["n_findings"] += 1
        if anchor_of(f, known)["anchored"]:
            continue
        if str(f.get("warrant") or "") != SUPPLIED_WARRANT:
            continue
        summary["n_candidates"] += 1
        original = str(f.get("severity") or "")
        if original not in ACCUSATORY:
            continue
        f["severity"] = UNANCHORED_CEILING
        f["severity_source"] = {
            "original": original,
            "final": UNANCHORED_CEILING,
            "clamped_by": "unanchored_supplied_norm",
            "why": (
                "This finding cites no stage-1 result and rests on a standard "
                "the review supplied rather than one the paper accepted, so "
                "nothing in the paper or the toolkit supports it. It is "
                "reported as unsettled rather than as a problem with the work."
            ),
        }
        summary["n_clamped"] += 1
        summary["clamps"].append({
            "title": str(f.get("title") or "")[:120],
            "from": original, "to": UNANCHORED_CEILING,
        })
    return summary
