"""Hold what the paper CLAIMED beside what its own numbers show.

The family this belongs to is the one that fires on an ABSENCE or a
contradiction rather than on a miscomputed number: the multiple-comparisons
check, which fires because no correction was applied, is the existing member.
Here the contradiction is between two things the paper itself printed -- a
p-value, and a sentence describing that p-value's result.

WHY THIS CHECK IS DELIBERATELY SMALLER THAN THE IDEA BEHIND IT.

"Spin" is the obvious target and the wrong one to automate. Describing p = .06
as "marginally significant" is a stylistic convention that a large part of the
literature accepts, criticizes openly, and -- crucially -- practices WHILE
PRINTING THE ACTUAL P-VALUE. A paper doing that is being transparent. A tool
that calls it misconduct is not detecting a defect; it is enforcing one field's
house style against another's, and it would fire constantly on honest work.

So this check refuses the literary question entirely and asks only the
arithmetic one: the paper states an alpha, prints an exact p for ONE test, and
describes that test's result, without hedging, as showing the effect exists.
If p > alpha those two printed things contradict each other. That is not a
matter of taste, and it is the only part of the interpretation layer that is
not.

EVERY REFUSAL BELOW IS THERE BECAUSE ITS ABSENCE WOULD MANUFACTURE AN
ACCUSATION:

  no stated alpha        -- defaulting to .05 accuses every paper that
                            pre-registered a stricter or looser threshold. The
                            precedent is `76e9cc3`, which DELETED four
                            precision defaults rather than defaulting them.
  more than one test      -- a hypothesis supported by three of four tests is
                            legitimately described as supported. Reading that
                            sentence against the one failing test invents a
                            contradiction the paper never made.
  a threshold p           -- "p < .05" is not a number to compare; the paper
                            may be reporting exactly what it should.
  any hedge               -- a hedge is the authors telling the reader not to
                            over-read the result. Honest behavior must never
                            be the trigger.
  a corrected alpha       -- if a correction was applied the operative
                            threshold is not the stated alpha, and comparing
                            against the wrong one is our error, not theirs.

CEILING `suspicious`, never `impossible`. An impossibility is a statement about
arithmetic that cannot be; this is a statement about a sentence, and a sentence
can always have a reading we did not think of.
"""

from __future__ import annotations

from typing import Any

METHODOLOGY = (
    "Compares a paper's own description of a single test's result against that "
    "test's printed p-value and the paper's stated alpha. Fires only when an "
    "unhedged claim that an effect was found accompanies p > alpha, with no "
    "multiplicity correction in play. Reports the two quotes so a reader "
    "adjudicates the sentence, not the tool."
)

#: A sentence-level claim can always have a reading we did not anticipate, so
#: this check may never assert impossibility.
CEILING = "suspicious"

CHECK = "claim_vs_printed_p"


def check_claim_vs_result(
    *,
    claim_quote: str,
    asserts: str,
    p_value: float | None,
    alpha: float | None,
    hedged: bool,
    p_is_threshold: bool = False,
    n_tests_claimed: int = 1,
    correction_applied: str | None = None,
    p_quote: str | None = None,
    source_locator: str | None = None,
) -> dict:
    """Does an unhedged claim of an effect sit beside a p above the paper's alpha?

    Args:
        claim_quote: The paper's OWN sentence, verbatim. A paraphrase is our
            reading of their reading and cannot be adjudicated by a reader.
        asserts: What the sentence asserts -- `supported`, `not_supported`,
            `mixed`, or `none`. Only `supported` is checkable here.
        p_value: The EXACT p the paper printed for this test.
        alpha: The threshold the paper STATED. Required; there is no default,
            because assuming .05 accuses every paper that chose otherwise.
        hedged: Whether the sentence softens the claim in any way.
        p_is_threshold: True when the paper printed `p < .05` rather than a
            number. Then there is nothing exact to compare.
        n_tests_claimed: How many tests this one sentence covers. Anything
            above 1 is refused -- see the module docstring.
        correction_applied: A multiplicity correction, if one was applied. Its
            presence means the operative threshold is not `alpha`.

    Returns a severity plus both quotes, so the finding is adjudicated on the
    paper's words rather than on ours.
    """
    out: dict[str, Any] = {
        "check": CHECK,
        "methodology": METHODOLOGY,
        "ceiling": CEILING,
        "claim_quote": claim_quote,
        "p_quote": p_quote,
        "source_locator": source_locator,
        "asserts": asserts,
        "reported_p": p_value,
        "stated_alpha": alpha,
        "hedged": bool(hedged),
    }

    def refuse(why: str) -> dict:
        return {**out, "severity": "indeterminate", "applicable": False,
                "why_not_checked": why}

    if not (claim_quote or "").strip():
        return refuse("no claim sentence was quoted, so there is nothing to "
                      "hold the number against")
    if asserts != "supported":
        return refuse(f"the claim asserts {asserts!r}; only an assertion that "
                      f"the effect WAS found can contradict a p above alpha")
    if hedged:
        return refuse("the sentence is hedged, which is the paper telling the "
                      "reader not to over-read the result -- honest behavior "
                      "is never the trigger")
    if alpha is None:
        return refuse("the paper's alpha was not stated; assuming .05 would "
                      "accuse every paper that chose a different threshold")
    # ORDER MATTERS, AND IT IS NOT COSMETIC. A refusal reason is reported to a
    # reader, and "no p-value was printed" is a criticism OF THE PAPER while
    # "the sentence covers six tests" is a fact about OUR check. When a
    # multi-test sentence resolves to no single test, `p_value` arrives None
    # and the p-value branch fired first -- reporting our own refusal as the
    # authors' omission. MEASURED on ajcp.70049, whose abstract names six
    # tests in one sentence: the sweep blamed the paper for a p it prints in
    # Table 2. Ask about the sentence before asking about the number.
    if n_tests_claimed != 1:
        return refuse(f"the sentence covers {n_tests_claimed} tests; a claim "
                      f"supported by most of several tests is legitimately "
                      f"described as supported")
    if p_value is None:
        return refuse("no p-value was printed for this test")
    if p_is_threshold:
        return refuse("the paper printed a threshold (p < x) rather than an "
                      "exact p, so there is no number to compare")
    if correction_applied and str(correction_applied).lower() not in ("", "none"):
        return refuse(f"a {correction_applied} correction was applied, so the "
                      f"operative threshold is not the stated alpha")

    try:
        p, a = float(p_value), float(alpha)
    except (TypeError, ValueError):
        return refuse("p or alpha is not a number")
    if not (0.0 <= p <= 1.0) or not (0.0 < a < 1.0):
        return refuse("p or alpha is outside the range a probability can take")

    out["exceeds_alpha_by"] = round(p - a, 6)
    if p > a:
        return {
            **out, "severity": "suspicious", "applicable": True,
            "finding": (
                f"The paper states alpha = {a:g} and prints p = {p:g} for this "
                f"test, then describes the result, without hedging, as showing "
                f"the effect. Those two printed statements disagree."),
            "what_would_resolve_it": (
                "A different alpha for this analysis, a correction we did not "
                "see, or a reading of the sentence that does not claim the "
                "effect was found."),
        }
    return {**out, "severity": "consistent", "applicable": True,
            "finding": (f"p = {p:g} is at or below the stated alpha = {a:g}, so "
                        f"the claim and the number agree.")}


def claim_consistency_report(anatomy, alpha: float | None = None) -> dict:
    """Walk every interpretation against the test it names.

    A SWEEP, not a tool the model chooses to call, for the same reason
    `multiplicity_report` is: the join it needs already exists in the anatomy,
    and a check the model must remember to invoke is a check that silently
    stops running. The model's job here is EXTRACTION -- quote the sentences --
    and the arithmetic is ours.

    `alpha` is the paper's STATED threshold and has no default. Passing None
    makes every claim `indeterminate` with the reason recorded, which is the
    honest output when we do not know what the paper committed to: a sweep that
    invents .05 to stay busy is how a coverage number becomes an accusation.
    """
    interps = list(getattr(anatomy, "interpretations", None) or [])
    tests = {t.id: t for t in (getattr(anatomy, "tests", None) or [])}

    out: dict[str, Any] = {
        "check": CHECK, "alpha": alpha, "methodology": METHODOLOGY,
        "n_interpretations": len(interps), "n_checked": 0,
        "n_refused": 0, "refusals": {}, "results": [], "worst": None,
    }
    if alpha is None:
        out["why"] = ("the paper's alpha was not stated, so no claim can be "
                      "judged against it")

    rank = {"suspicious": 0, "indeterminate": 1, "consistent": 2}
    for it in interps:
        ids = list(getattr(it, "test_ids", None) or [])
        # A sentence naming a test we never extracted is OUR gap, not their
        # error, and must not be reported as one.
        known = [i for i in ids if i in tests]
        test = tests[known[0]] if len(known) == 1 else None

        res = check_claim_vs_result(
            claim_quote=getattr(it, "claim", "") or "",
            asserts=getattr(it, "asserts", "none"),
            p_value=getattr(test, "p_value", None) if test else None,
            alpha=alpha,
            hedged=bool(getattr(it, "hedged", False)),
            p_is_threshold=bool(getattr(test, "p_is_threshold", False)) if test else False,
            n_tests_claimed=len(ids) if ids else 0,
            correction_applied=getattr(test, "correction_applied", None) if test else None,
            p_quote=getattr(test, "provenance_quote", None) if test else None,
            source_locator=getattr(test, "location", None) if test else None,
        )
        res["interpretation_id"] = getattr(it, "id", None)
        res["test_id"] = test.id if test else None
        res["location"] = getattr(it, "location", None)

        if res.get("applicable"):
            out["n_checked"] += 1
        else:
            out["n_refused"] += 1
            why = res.get("why_not_checked", "unknown")
            out["refusals"][why] = out["refusals"].get(why, 0) + 1
        out["results"].append(res)

        sev = res.get("severity")
        if sev in rank and (out["worst"] is None
                            or rank[sev] < rank.get(out["worst"], 9)):
            out["worst"] = sev

    # Recorded so that "nothing to say" stays distinguishable from "never ran",
    # which is the failure mode this codebase keeps re-finding.
    out["n_contradictions"] = sum(
        1 for r in out["results"] if r.get("severity") == "suspicious")
    return out
