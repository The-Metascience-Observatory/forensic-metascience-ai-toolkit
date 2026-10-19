"""Who imposes the obligation a finding invokes -- named, rendered, and capped.

THE PROBLEM THIS SOLVES, and it is a generalization problem, not a coverage one.
`prompts/stage2_editorial.md` section 2 listed six review dimensions (data
availability, effect-size plausibility, design validity, feasibility/logistics,
reporting hygiene, consequence tracing) written with one kind of paper in mind.
MEASURED over 23 archived runs / 222 editorial findings
(`scratchpad/editorial_categories_generalization_fable_2026-08-11.md`, local scratch, not tracked):

  * the six account for ~35 of 88 non-tool findings (40%);
  * two of them barely operate as written -- effect-size plausibility fired
    manually ONCE in 23 runs, and design validity's literal wording
    ("between-within vs independent tests, paired data, zero cells") fits ~6;
  * the two largest and most field-general classes the stage actually produces
    -- internal contradiction (~19) and inference overreach (~12) -- are on no
    list at all;
  * on every off-home-turf design the model kept the six labels and silently
    substituted the field-appropriate concern (PSA uncertainty propagation on a
    Markov cost-effectiveness model, covariate overlap on a survey-epidemiology
    paper, construct collinearity on an EMA mediation paper). The words were a
    costume; the model's training did the work.

The conclusion is not "write a longer list". No list enumerates every field's
failure modes, and a longer one fails the same way with more maintenance. What
IS enumerable is the small set of SOURCES from which any legitimate critique of
any paper, in any field, can draw its authority. Four of them:

    paper_commitment  the paper promised this itself -- a guideline it claims,
                      its registration, its prespecified outcomes, its stated
                      thresholds, its data-availability statement. Quote the
                      promise. The strongest warrant there is: the paper cannot
                      object to being held to its own word.

    named_guideline   an external reporting standard (CONSORT, STROBE, ARRIVE,
                      PRISMA, CHEERS, JARS). Name the guideline AND the item,
                      and say whether the paper claims to follow it. If it does,
                      this is really `paper_commitment` and should say so.

    logical           the claim follows from the document or from arithmetic
                      alone -- two passages that cannot both be true, a p-value
                      that cannot come from that test statistic, a total that
                      does not sum. Field-independent by construction, which is
                      why it is the class that generalized when the topic list
                      did not.

    field_norm        a standard WE supply that this paper never accepted.
                      Legitimate and often valuable, but it is our norm, and it
                      is the only class that can hold a paper to something its
                      design never owed.

WHY A FIELD RATHER THAN MORE PROMPT TEXT. The archive contains NO false
accusation from a misapplied category in 222 findings, and the reason is that
the model sources its obligations unprompted -- quoting the CONSORT claim before
invoking CONSORT items, writing "which is an external benchmark I supply, not
one the paper states" before applying ARRIVE to a rodent study, hedging
registration norms by era. Every one of those is model discretion. No prompt
sentence requires it, no schema field records it, and nothing can check it. The
prior memo measured prompt-law leaking at ~1% per run on the severity cap --
small, and always at the top of the ladder, which is where it matters. This
module asks the model only for what its best behaviour already does, and makes
the answer inspectable.

WHAT THE CAP IS AND IS NOT. `field_norm` caps at `suspicious`.

  * It is NOT redundant with `clamp_uncomputed`. That clamp keys on evidence
    grade, so it never touches a finding a tool computed. A `field_norm` finding
    CAN be tool-computed -- `multiplicity_report` will happily compute how many
    claims fail a correction the paper never undertook -- and the computation is
    sound while the obligation is still ours. Capping on the warrant catches
    exactly the case capping on evidence cannot see.
  * It is not a judgement that reviewer-supplied norms are weak. It is that the
    top two rungs read as determinations about the paper, and a norm the paper
    never accepted cannot support one.

FAIL-SAFE DIRECTION. A finding with no warrant, or an unrecognised one, is read
as `field_norm` -- the capped, labelled-as-ours class. That is deliberate: the
unknown case degrades toward the weaker reading, never the stronger. A missing
field must never buy a finding severity it did not earn.
"""

from __future__ import annotations

from typing import Any

#: The closed vocabulary. Order is strongest-warrant-first, which is also the
#: order a reader should prefer: hold a paper to its own word before holding it
#: to a standard it never adopted.
WARRANTS: tuple[str, ...] = (
    "paper_commitment",
    "named_guideline",
    "logical",
    "field_norm",
)

#: One line each, for the codebook and the viewer. Written for the lay reader --
#: this is the field that tells them whether a criticism is the paper's own
#: promise coming back on it or a standard we brought to the table.
WARRANT_MEANING: dict[str, str] = {
    "paper_commitment": (
        "The paper promised this itself -- a guideline it claims to follow, its "
        "registration, its stated outcomes or thresholds. We are holding it to "
        "its own word."
    ),
    "named_guideline": (
        "An external reporting standard (CONSORT, STROBE, ARRIVE, PRISMA, "
        "CHEERS) and a specific item within it, named so you can look it up."
    ),
    "logical": (
        "The paper contradicts itself, or the arithmetic does not work. Nothing "
        "outside the document is needed to see it."
    ),
    "field_norm": (
        "A standard the REVIEWER supplied, which this paper never claimed to "
        "follow. It may still be the right standard -- but it is ours, not "
        "theirs, and findings resting on one are capped."
    ),
}

#: Short label for a chip in the viewer.
WARRANT_CHIP: dict[str, str] = {
    "paper_commitment": "the paper's own promise",
    "named_guideline": "a named guideline",
    "logical": "logic or arithmetic",
    "field_norm": "a norm we supplied",
}

#: The class whose obligation the paper never accepted, and the rung it stops at.
SUPPLIED_WARRANT = "field_norm"
SUPPLIED_CEILING = "suspicious"

_ABOVE_CEILING = ("impossible", "highly_suspicious")


def warrant_of(finding: Any) -> dict[str, Any]:
    """Resolve one finding's warrant, saying whether we were told or inferred.

    `stated` is False when the field was absent or held a word outside the
    vocabulary. Callers that render must show the difference: "the reviewer
    supplied this norm" and "nobody said where this obligation comes from, so we
    are treating it as ours" are different sentences, and only the first is a
    claim the model actually made.
    """
    if not isinstance(finding, dict):
        return {"warrant": SUPPLIED_WARRANT, "stated": False, "raw": None,
                "chip": WARRANT_CHIP[SUPPLIED_WARRANT],
                "meaning": WARRANT_MEANING[SUPPLIED_WARRANT]}
    raw = finding.get("warrant")
    value = str(raw).strip().lower() if raw is not None else ""
    stated = value in WARRANTS
    resolved = value if stated else SUPPLIED_WARRANT
    return {
        "warrant": resolved,
        "stated": stated,
        "raw": raw,
        "chip": WARRANT_CHIP[resolved],
        "meaning": WARRANT_MEANING[resolved],
    }


def clamp_supplied_norms(result: dict) -> dict:
    """Cap findings resting on a norm we supplied, and say so on the page.

    Same visible `severity_source` block the tool/model reconciler and the
    uncomputed clamp write, for the same reason: a severity quietly lowered
    hides both the correction and a model that is systematically over-calling.
    """
    summary: dict[str, Any] = {
        "n_findings": 0, "n_supplied": 0, "n_inferred": 0,
        "n_clamped": 0, "clamps": [], "by_warrant": {},
    }
    # THE KEY PRODUCTION ACTUALLY USES IS `report_obj`. Read as `report` alone,
    # this returned at the first line on EVERY REAL RUN -- the Romano run of
    # 2026-08-11 has no `uncomputed_severity_clamp` and no `supplied_norm_clamp`
    # in its `run_meta.json` at all, while `severity_reconciliation` (which
    # reads `result["findings"]`) is right there beside them. So the clamp that
    # commit e1fa555 shipped as "the enforced severity cap" enforced nothing,
    # and its tests passed throughout because they hand-build `{"report": ...}`.
    # Tested against a shape production never produces is the same defect as
    # never being called; `lint-inert` should learn this one.
    #
    # `report` is kept as a fallback so those hand-built fixtures, and the
    # archive replay in tests/test_corpus_invariants.py, keep working.
    report = result.get("report_obj")
    if not isinstance(report, dict):
        report = result.get("report")
    findings = report.get("findings") if isinstance(report, dict) else None
    if not isinstance(findings, list):
        return summary

    for f in findings:
        if not isinstance(f, dict):
            continue
        summary["n_findings"] += 1
        res = warrant_of(f)
        w = res["warrant"]
        summary["by_warrant"][w] = summary["by_warrant"].get(w, 0) + 1
        if not res["stated"]:
            summary["n_inferred"] += 1
        if w != SUPPLIED_WARRANT:
            continue
        summary["n_supplied"] += 1
        original = str(f.get("severity") or "")
        if original not in _ABOVE_CEILING:
            continue
        f["severity"] = SUPPLIED_CEILING
        why = ("The finding names no warrant, so it is read as a norm we "
               "supplied") if not res["stated"] else (
              "The obligation this finding invokes is one the reviewer "
              "supplied, not one the paper accepted")
        f["severity_source"] = {
            "tool": None,
            "model": original,
            "final": SUPPLIED_CEILING,
            "direction": "clamped",
            "explained": True,
            "reason": (
                f"Capped at `{SUPPLIED_CEILING}`. The model recorded "
                f"`{original}`. {why}. The two rungs above the cap read as "
                "determinations about the paper, and a standard the paper never "
                "claimed to follow cannot support one. Anchor the obligation to "
                "something the paper itself promised and the cap lifts."
            ),
        }
        summary["n_clamped"] += 1
        who = str(f.get("id") or f.get("title") or "?")[:70]
        summary["clamps"].append(
            f"{who}: {original} -> {SUPPLIED_CEILING} ({w}"
            f"{'' if res['stated'] else ', inferred'})")

    meta = result.setdefault("run_meta", {})
    if isinstance(meta, dict):
        meta["supplied_norm_clamp"] = summary
    return summary
