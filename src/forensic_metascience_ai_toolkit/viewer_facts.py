"""The viewer's DERIVED FACTS, computed once in Python instead of in view-time JS.

WHY THIS MODULE EXISTS. Two independent design reviews of the HTML viewer landed
on the same architectural point, and the second stated it as a rule:

    "Presentation in JS; facts in Python."

Every semantic derivation the viewer performs -- classifying a refusal, counting
what traced back to the paper, deciding whether a finding was computed by a
validated check -- is a CLAIM ABOUT OUR OWN WORK, made in a document whose entire
authority is that its claims can be audited. Three of them were being made in
JavaScript inside a template string, where no test could reach them, and all
three were measurably wrong on a real bundle.

MEASURED on `cerebrolysin_run_2026-08-09/10.1007--s11064-023-03861-8` (I
re-parsed the embedded payload rather than taking either review's word):

  * The Overview prints "sweep tool verdicts 20 -- one per check that returned a
    verdict, passes included", then breaks it down HS 4 / S 12 / indet 4. Those
    are the WRITE-UP severities. The tools actually returned HS 8 / S 11 /
    consistent 2 / indet 3 = 24, and the table 300px below says so. The label is
    wrong, the number is the wrong universe, and the only category that is good
    news for the authors -- the two `consistent` verdicts -- is the one the
    summary drops. See `severity_ledger`.

  * The traceability sentence is the most-repeated self-criticism in the
    document and it is false as written. It reports the NARROW join
    (`source.source_quote`, 4 of 20) under the BROAD description ("cite numbers
    this bundle cannot trace back to a passage of the paper"), when 20 of 20
    sweep findings quote a passage and 17 were located verbatim in the paper.
    Worse, three pages answer what looks like one question with three different
    numbers. See `traceability`.

  * "Hand-computed" is a row in a table and a parenthetical at the end of a
    paragraph. On this paper 4 of 12 report findings -- THREE OF THEM
    `suspicious` -- rest entirely on arithmetic the model did itself, with
    nothing on their cards saying so. See `evidence_ledger`.

  * The refusal classifier leaves 9 of 13 rows `unclassified`, which is the
    modal outcome, on a mechanism built specifically to stop the shortfall list
    reading as a task list abandoned. See `classify_refusal`.

THE DISCIPLINE THIS MODULE KEEPS. Every function returns numbers WITH the
population they were counted over, because the recurring defect above is not
arithmetic -- each individual count was right -- it is a number printed under a
description of a different set. A count that cannot say what it counted is how
this document ends up less scrupulous about itself than it is about the paper.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from . import finding_view as _fv

# ---------------------------------------------------------------------------
# Severity: two universes, named
# ---------------------------------------------------------------------------



def _tally(values: Iterable[Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        k = str(v or "unknown")
        out[k] = out.get(k, 0) + 1
    return out


def severity_ledger(payload: dict | None) -> dict:
    """The two DIFFERENT severity universes, each labelled with what it counts.

    They are different on purpose and the viewer already explains the
    difference in a footnote -- "a tool verdict is what a validated check
    computed; a write-up severity is what the review concluded about it" -- and
    then prints one under the other's name.

    `write_up`   one per sweep FINDING. A finding is something the review chose
                 to record, so passes are largely absent by construction.
    `tool`       one per check that RETURNED a verdict, passes included. This is
                 the universe the Overview claimed to be showing.

    `consistent_dropped` is called out explicitly because dropping it is not a
    neutral rounding: it is the only category that is good news for the authors,
    and a summary that omits it is biased in the accusing direction.
    """
    payload = payload or {}
    write_up = _tally(f.get("severity") for f in (payload.get("findings") or [])
                      if isinstance(f, dict))

    tool: dict[str, int] = {}
    from_table = _tally([])
    for row in payload.get("check_table") or []:
        if not isinstance(row, dict):
            continue
        for k, n in (row.get("tool_verdicts") or {}).items():
            tool[str(k)] = tool.get(str(k), 0) + int(n or 0)
        for k, n in (row.get("severities") or {}).items():
            from_table[str(k)] = from_table.get(str(k), 0) + int(n or 0)

    return {
        "write_up": {
            "counts": write_up,
            "total": sum(write_up.values()),
            "population": "sweep findings the review recorded",
            "label": "the write-up recorded",
        },
        "tool": {
            "counts": tool,
            "total": sum(tool.values()),
            "population": "checks that returned a verdict, passes included",
            "label": "the checks returned",
        },
        # The check table's own copy of the write-up severities. If this ever
        # disagrees with `write_up`, two parts of the page are counting the same
        # thing differently and the reader has no way to know which to believe.
        "write_up_from_check_table": {"counts": from_table,
                                      "total": sum(from_table.values())},
        "consistent_dropped": tool.get("consistent", 0),
        "agree": from_table == write_up or not from_table,
    }


# ---------------------------------------------------------------------------
# Traceability: one structure, three questions, three populations
# ---------------------------------------------------------------------------

#: Quote verdicts that mean A READER CAN OPEN THE PAPER AND FIND THE SENTENCE.
#: `stitched` deliberately excluded: we assembled that sentence and it does not
#: appear there, so it evidences nothing about what the authors wrote. Same
#: split `anatomy.bounds_are_stated` uses, and for the same reason.
LOCATED_VERDICTS = ("verbatim", "elided")


def traceability(payload: dict | None) -> dict:
    """What actually traced back to the paper, as THREE separate questions.

    The document currently answers what looks like one question in three places
    with three different numbers (4/16, 12/16, 26/26) and reconciles them
    nowhere. They are not one question. They are:

      quotes_located   Does each sweep finding quote a passage, and did we find
                       that passage in the paper? This is the one a reader means
                       by "can you show me where this came from", and it is the
                       one the page never states.
      joined_to_call   Can that quote be tied to the SPECIFIC validated call that
                       consumed the number? Much narrower, genuinely useful, and
                       currently reported under the sentence above's wording.
      anchored         Does the finding resolve to a place in the source we can
                       jump to?

    Each row carries its own denominator and its own population string, so the
    three cannot be quoted interchangeably again.
    """
    payload = payload or {}
    sweep = [f for f in (payload.get("findings") or []) if isinstance(f, dict)]
    n = len(sweep)

    verdicts = _tally(f.get("quote_verified") for f in sweep if f.get("quote"))
    located = sum(verdicts.get(v, 0) for v in LOCATED_VERDICTS)
    with_quote = sum(1 for f in sweep if f.get("quote"))
    anchored = sum(1 for f in sweep if f.get("_anchor"))

    # THE JOIN DENOMINATOR EXCLUDES HAND-READ FINDINGS, and getting this wrong
    # is the same error this module exists to fix, one level down.
    #
    # A `technique: manual` finding is a value the model read off the paper
    # itself. NO PRODUCING CALL EXISTS FOR IT -- not as a failure, but by
    # construction -- so counting it among the findings we "could not tie to a
    # validated call" reports a design fact as a coverage failure and inflates
    # our own stated shortfall. The viewer's original JS had this exclusion; I
    # dropped it while moving the computation here, and `test_bundle`'s
    # `test_manual_findings_are_not_counted_as_untraceable` caught it.
    # WHAT A TOOL ACTUALLY COMPUTED, NOT WHAT THE TECHNIQUE STRING LOOKS LIKE.
    #
    # `MODEL_TECHNIQUES` froze on the v1 vocabulary, whose catch-all was
    # `manual`. The v2 schema DELETED `manual` and names the non-tool cases
    # explicitly -- `not_computational`, `internal_contradiction`,
    # `absence_of_evidence` -- so the exclusion this module's own docstring says
    # exists to stop us "inflating our own stated shortfall" matched NOTHING.
    #
    # MEASURED on the current ajcp run: 0 of 34 techniques are in
    # `MODEL_TECHNIQUES`, so the viewer told a reader "Of the 34 produced by a
    # validated check..." while `computed_by` says 5 were and 29 are
    # `model_reading`.
    #
    # `computed_by` is the pipeline's own record of whether a registered tool
    # produced the number (`parallel.py` sets it from the tool ledger, not from
    # the model's prose), so it is read first. The technique test remains as
    # the v1 fallback for archived runs, which carry no `computed_by`.
    def _tool_produced(f: dict) -> bool:
        produced = str(f.get("computed_by") or "")
        if produced:
            return produced not in ("model_reading", "model_knowledge")
        return str(f.get("technique") or "").lower() not in MODEL_TECHNIQUES

    joinable = [f for f in sweep if _tool_produced(f)]
    joined = sum(1 for f in joinable if (f.get("source") or {}).get("source_quote"))
    hand_read = len(sweep) - len(joinable)

    return {
        "population": "sweep findings",
        "n": n,
        "quotes_located": {
            "with_quote": with_quote,
            "located_in_paper": located,
            "verdicts": verdicts,
            "of": n,
            "question": "does the finding quote a passage, and is that passage in the paper?",
        },
        "joined_to_call": {
            "n": joined, "of": len(joinable),
            "hand_read_excluded": hand_read,
            "question": ("of the findings a validated check produced, can the "
                         "quote be tied to the specific call that consumed the "
                         "number?"),
            "caveat": ("Narrower than it sounds, and its denominator excludes "
                       "hand-read findings, for which no producing call exists by "
                       "construction. A finding without this join still quotes the "
                       "paper -- the passage shown is the review's rather than the "
                       "call's."),
        },
        "anchored": {
            "n": anchored, "of": n,
            "question": "does the finding resolve to a place we can jump to?",
        },
    }


def traceability_sentence(tr: dict | None) -> str:
    """The corrected sentence, stated positively and with both numbers.

    Replaces "12 of 16 tool verdicts cite numbers this bundle cannot trace back
    to a passage of the paper", which reports the narrow quantity under the
    broad description and tells a cold reader that three quarters of our numbers
    are untraceable when nearly all of them were located verbatim.
    """
    if not tr or not tr.get("n"):
        return "This review recorded no sweep findings, so there is nothing to trace."
    q, j, n = tr["quotes_located"], tr["joined_to_call"], tr["n"]
    verdicts = q["verdicts"]
    parts = []
    if verdicts.get("verbatim"):
        parts.append(f"{verdicts['verbatim']} verbatim")
    if verdicts.get("elided"):
        parts.append(f"{verdicts['elided']} with an internal ellipsis")
    if verdicts.get("stitched"):
        parts.append(f"{verdicts['stitched']} assembled from adjacent text and NOT "
                     "appearing as one sentence in the paper")
    if verdicts.get("unverified"):
        parts.append(f"{verdicts['unverified']} we could not find")
    how = "; ".join(parts) if parts else "none checked"
    out = (f"{q['with_quote']} of {n} findings quote a passage of the paper "
           f"({how}).")
    # The join clause is omitted entirely when nothing was joinable -- a run
    # whose findings were all hand-read has no producing calls to join to, and
    # printing "0 of 0" there would invent a shortfall out of a design fact.
    if j["of"]:
        out += (f" Of the {j['of']} produced by a validated check, {j['of'] - j['n']} "
                f"could not be tied to the specific call that consumed the number, "
                f"so the passage shown is the review's rather than the call's.")
    if j.get("hand_read_excluded"):
        out += (f" {j['hand_read_excluded']} finding"
                f"{'s' if j['hand_read_excluded'] != 1 else ''} the review read off "
                f"the paper by hand {'are' if j['hand_read_excluded'] != 1 else 'is'} "
                "not counted there: no producing call exists for them.")
    return out


# ---------------------------------------------------------------------------
# Evidence class: which grade of arithmetic is a finding actually resting on
# ---------------------------------------------------------------------------

#: A sweep finding carrying one of these as its `technique` was NOT produced by
#: a validated forensic tool -- the model did the arithmetic itself. `manual` is
#: the value the schema uses; the empty cases are folded in because an absent
#: technique is not evidence that a tool ran.
MODEL_TECHNIQUES = frozenset({"manual", "", "none", "unknown"})

#: The three grades, strongest first. They are three because two would conflate
#: the two weak cases, and they fail differently: a hand-computed finding has
#: arithmetic nobody checked, while a reading of the paper has no arithmetic at
#: all and nothing to re-run. The viewer's single "No tool backing" paragraph
#: says one sentence over both.
EVIDENCE_GRADES = ("computed", "hand_computed", "reading")

#: THE SAME FACT, SHORT ENOUGH TO SIT INSIDE THE SEVERITY CHIP.
#:
#: The grade currently renders as a paragraph BELOW the finding title, so a
#: screenshot crop can capture "suspicious" and the claim while missing the
#: qualification entirely -- which fails the viewer's governing test in exactly
#: the band where it matters most. MEASURED across 23 archived runs: 88 of 222
#: findings (40%) are not computed, so this is not an edge case.
#:
#: Vocabulary is deliberately plain and non-euphemistic. "Reviewer reading" says
#: what the thing is and invites the right posture; calling it "qualitative" or
#: "contextual" would dress up the same fact and teach readers to skip it.
GRADE_CHIP = {
    "computed": "computed",
    "hand_computed": "model arithmetic, unverified",
    "reading": "reviewer reading",
}

_GRADE_TEXT = {
    "computed": (
        "Computed by a validated check.",
        "A tool in the audited forensic surface produced this number, and the "
        "call is in the ledger.",
    ),
    "hand_computed": (
        "Hand-computed: the model asserted this arithmetic; no validated check "
        "computed it.",
        "Recompute before relying on it. The reasoning may be right -- but "
        "nothing here verified it, and this is the grade most likely to carry a "
        "plausible-sounding error.",
    ),
    "reading": (
        "This is a reading of the paper, not a computation.",
        "There is no arithmetic to re-run and no tool verdict behind it. Judge "
        "it as you would a colleague's remark about a manuscript.",
    ),
}


def evidence_grade(finding: dict | None, sweep_by_id: dict | None) -> dict:
    """Which of the three grades of evidence one REPORT finding rests on.

    THE PREDICATE MATTERS AND THE OBVIOUS ONE IS WRONG. A design review proposed
    flagging report findings with no `stage1_finding_ids`; measured on the run
    that motivated it, that predicate fires on 0 of 8 findings. The real
    structure is a CHAIN -- report finding -> sweep findings -> the technique
    that produced each -- and the dangerous case is a finding whose backing
    sweep findings are themselves `technique: manual`. It cites evidence; the
    evidence is the model's own arithmetic.

    Measured on the cerebrolysin run: 7 computed, 4 hand-computed, 1 reading.
    Three of the four hand-computed are `suspicious`.
    """
    finding = finding or {}
    sweep_by_id = sweep_by_id or {}

    # A v2 FINDING IS ITS OWN SWEEP FINDING, so there is no chain to walk.
    #
    # The chain above -- report finding -> `stage1_finding_ids` -> sweep
    # findings -> the technique behind each -- is a v1 structure. v2 merged the
    # two stages, so a v2 row carries NO `stage1_finding_ids`, `ids` came out
    # empty, and EVERY finding graded `reading` with the chip "reviewer
    # reading".
    #
    # MEASURED on the current ajcp run: all 34 graded `reading`, including the
    # 5 that `computed_by` records as `registry_tool`. The grade that exists to
    # separate a validated computation from the model's own arithmetic reported
    # the weakest answer for every row, which understates our own evidence in
    # the same breath as it hides the rows that deserve the caution.
    #
    # `computed_by` is the v2 record of the same fact and is set from the TOOL
    # LEDGER, so it maps onto the three grades directly.
    _computed_by = str(finding.get("computed_by") or "")
    if _computed_by:
        grade = ("computed" if _computed_by == "registry_tool"
                 else "hand_computed" if _computed_by == "agent_code"
                 else "reading")
        headline, detail = _GRADE_TEXT[grade]
        return {
            "grade": grade,
            "chip": GRADE_CHIP[grade],
            "headline": headline,
            "detail": detail,
            "backing_ids": [],
            "backing_resolved": 0,
            "techniques": sorted({str(finding.get("technique") or "")} - {""}),
            "dangling_ids": [],
            "graded_from": "computed_by",
        }

    ids = [i for i in (finding.get("stage1_finding_ids") or []) if i]
    backing = [sweep_by_id[i] for i in ids if i in sweep_by_id]

    if not ids:
        grade = "reading"
    elif not backing:
        # Ids that resolve to nothing. NOT silently treated as computed: a
        # dangling reference is a broken audit trail, and the safe reading of a
        # broken trail is that nothing verified is behind it.
        grade = "reading"
    elif all(str(b.get("technique") or "").lower() in MODEL_TECHNIQUES
             for b in backing):
        grade = "hand_computed"
    else:
        grade = "computed"

    headline, detail = _GRADE_TEXT[grade]
    return {
        "grade": grade,
        "chip": GRADE_CHIP[grade],
        "headline": headline,
        "detail": detail,
        "backing_ids": ids,
        "backing_resolved": len(backing),
        "techniques": sorted({str(b.get("technique") or "") for b in backing}),
        "dangling_ids": [i for i in ids if i not in sweep_by_id],
    }


#: What a reader could actually do to settle one finding, keyed on what the
#: finding itself recorded. Ordered most-specific first; the first match wins,
#: because a card ending in five instructions ends in none.
#:
#: PHRASED AS "WHAT WOULD SETTLE THIS", never "what would make us withdraw it".
#: We do not know in advance which way the answer goes, and promising to
#: withdraw is a promise about a conclusion we have not reached.
_SETTLE_RULES: tuple[tuple[str, str], ...] = (
    ("hand_computed",
     "No validated check produced this number -- the arithmetic was asserted "
     "rather than performed. Recompute it before relying on it."),
    ("reading",
     "This is a reading of the paper rather than a computation, so there is "
     "nothing to re-run. Judge it as you would a colleague's remark."),
    ("assumed_n",
     "The exact n behind this row. We tested the denominator printed for the "
     "column, and the n ANALYSED for one outcome is routinely smaller after "
     "exclusions."),
    ("assumed_bounds",
     "The scale range for this measure. We supplied one, and a range violation "
     "against OUR range is a fact about our assumption, not the paper's data."),
    ("assumed_discreteness",
     "Confirmation that this instrument is scored in whole numbers. The "
     "arithmetic here holds only if each subject contributed an integer."),
    ("rounding",
     "One more decimal place on the printed values. The verdict turns on the "
     "rounding interval, which is as wide as the last digit shown."),
    ("quote_unlocated",
     "The printed value, checked against the paper. We could not locate the "
     "passage this number was read from, so our extraction may have misread "
     "the cell."),
    ("supplement",
     "The supplementary material, which we were not able to obtain -- see the "
     "first question for the authors. Some of what follows may already be "
     "answered there."),
)
_SETTLE_TEXT = dict(_SETTLE_RULES)

#: When no rule matches. NEVER SILENCE: a card that ends without saying what
#: would resolve it invites the reader to treat it as settled already, which is
#: the opposite of what every other line on the page is for.
SETTLE_FALLBACK = (
    "The paper's own working for this value -- the exact inputs, and the "
    "software output if one exists. Nothing here establishes that the number is "
    "wrong, only that we could not reproduce it from what is printed."
)


def settle_this(finding: dict | None, backing: list | None,
                grade: str | None = None,
                supplement_missing: bool = False) -> dict:
    """The last block of a finding card: what would resolve it.

    DERIVED HERE, IN PYTHON, at build time. A design review proposed this as "a
    small rule table in JS" and that is the wrong layer for the same reason the
    rest of this module exists: it is a claim about what our own evidence rests
    on, no test can reach it inside a template string, and the two derivations
    that lived there were both wrong on a real bundle.

    Reads only what the finding and its backing checks ALREADY RECORD -- the
    gates this repo spent the last several days building are exactly the list of
    things that could be missing, so the answer is nearly always already on
    disk.
    """
    finding = finding or {}
    backing = [b for b in (backing or []) if isinstance(b, dict)]
    hits: list[str] = []

    if grade in ("hand_computed", "reading"):
        hits.append(grade)

    def _inputs(b):
        v = b.get("inputs")
        return v if isinstance(v, dict) else {}

    if any(_inputs(b).get("bound_source") == "assumed" for b in backing):
        hits.append("assumed_bounds")
    if any(_inputs(b).get("discreteness_source") == "assumed" for b in backing):
        hits.append("assumed_discreteness")
    if any(b.get("denominator_question") or (b.get("n_provenance") or {}).get("derived")
           for b in backing):
        hits.append("assumed_n")
    if any((b.get("computed") or {}).get("rounding_convention")
           or (b.get("computed") or {}).get("failure_mode") == "rounding_convention"
           for b in backing):
        hits.append("rounding")
    if any(b.get("quote") and b.get("quote_verified") not in LOCATED_VERDICTS
           for b in backing):
        hits.append("quote_unlocated")
    if supplement_missing:
        hits.append("supplement")

    ordered = [k for k, _ in _SETTLE_RULES if k in hits]
    return {
        "keys": ordered,
        "text": _SETTLE_TEXT[ordered[0]] if ordered else SETTLE_FALLBACK,
        "also": [_SETTLE_TEXT[k] for k in ordered[1:3]],
        "from_rule": bool(ordered),
    }


def _warrant_of(finding: dict) -> dict:
    """Local import so `warrants` stays a leaf and this module stays importable
    from the tools, which must not pull the report layer in."""
    from .warrants import warrant_of
    return warrant_of(finding)


def evidence_ledger(payload: dict | None) -> dict:
    """`evidence_grade` over every report finding, plus the per-grade counts.

    `accusatory_hand_computed` is surfaced on its own because it is the number
    that matters: a `suspicious` or worse finding resting on unverified
    arithmetic is the shape most likely to become a false accusation, and it is
    currently invisible at card level.
    """
    payload = payload or {}
    # `_fv.ref`, not `f.get("id")`: a v2 row carries `finding_id`. The viewer
    # card happens to copy it into `id` (bundle._v2_container), which is why
    # this worked by accident on the bundle path and not on a raw v2 document.
    sweep_by_id = {_fv.ref(f): f for f in (payload.get("findings") or [])
                   if isinstance(f, dict) and _fv.ref(f)}
    # A v2 document's findings ARE the report findings: v2 merged the sweep and
    # report stages. (This once read `report_obj`, report.json's list, which
    # the parallel path never writes -- so on every v2 run the ledger graded
    # nothing.) `evidence_grade` reads each row's own `computed_by`.
    report = [f for f in (payload.get("findings") or [])
              if isinstance(f, dict)]

    supp_missing = bool((payload.get("supplements") or {}).get("missing"))
    per: list[dict] = []
    counts: dict[str, int] = {g: 0 for g in EVIDENCE_GRADES}
    accusatory = 0
    for f in report:
        g = evidence_grade(f, sweep_by_id)
        counts[g["grade"]] += 1
        # BOTH LADDERS. This compared `str(severity)` against v1 STRINGS, and a
        # v2 severity is an INTEGER -- so `str(4)` is `"4"`, matched nothing,
        # and `accusatory_without_a_validated_check` read 0 on every v2 run.
        #
        # That number is the one this ledger exists to surface: its own
        # docstring calls a `suspicious`-or-worse finding resting on unverified
        # arithmetic "the shape most likely to become a false accusation".
        # MEASURED on the current ajcp run: 3 accusatory findings, 2 of them
        # `model_reading`, reported as 0.
        #
        # AND THE INTEGER BRANCH NEVER RAN EITHER. On the bundle path this
        # function sees `_v2_container`'s cards, whose `severity` is the STRING
        # "S<n>" -- so the fix above matched nothing too, and the count stayed
        # 0 on every v2 bundle. MEASURED on litvak05 (v1.22.0, 2026-09-03):
        # 8 final accusations, 3 by a registry tool, count shown 0; true 5.
        # `finding_view.is_accusatory` reads all four row shapes.
        if g["grade"] != "computed" and _fv.is_accusatory(f):
            accusatory += 1
        backing: list = []
        # The two questions a reader needs are orthogonal and both belong here:
        # WHO COMPUTED IT (evidence grade) and WHOSE STANDARD IT INVOKES
        # (warrant). A finding can be perfectly computed against an obligation
        # the paper never accepted, and nothing above sees that.
        per.append({"title": f.get("title"), "severity": f.get("severity"), **g,
                    "warrant": _warrant_of(f),
                    "settle": settle_this(f, backing, g["grade"], supp_missing)})

    return {
        "population": "report findings",
        "n": len(report),
        "counts": counts,
        "accusatory_without_a_validated_check": accusatory,
        "per_finding": per,
        # WHETHER THIS REPORT SPEAKS THE LANGUAGE AT ALL, which is not the same
        # question as whether a given finding named its warrant. Every run
        # archived before the field existed carries none, and rendering "no
        # warrant named" on all of them would put an apparent defect on 222
        # findings that were written before the requirement -- the exact
        # impression-of-more-errors-than-exist failure the terminology work is
        # about. Silence is the honest rendering for a report that predates the
        # field; the chip is for a report that had the field and left it blank.
        "uses_warrants": any(isinstance(f, dict) and f.get("warrant")
                             for f in report),
    }


# ---------------------------------------------------------------------------
# Refusals: whose limit was it
# ---------------------------------------------------------------------------

#: Ported from the viewer's JS `REFUSAL_KINDS`, WIDENED, and moved here so it is
#: reachable by a test. The JS version was covered by none of this repo's tests
#: and left 9 of 13 rows `unclassified` on a real run -- the modal outcome on the
#: mechanism built specifically to stop the shortfall list reading as a task
#: list abandoned.
#:
#: ORDER IS LOAD-BEARING and is unchanged from the JS. An explicit declaration
#: of inapplicability beats every keyword, because the alternative failure was
#: measured: "detect_duplication across tables -- Not applicable. The paper
#: reports no means with standard deviations anywhere" was filed under "the
#: paper does not report it", turning a check that simply does not apply into an
#: implied deficiency of the publication.
#:
#: The first widening was all in the `na` tiers -- phrasings that plainly declare
#: inapplicability and were missed -- and NOT in `ours`. Ties still resolve
#: against us. Widening the self-blaming bucket to reduce `unclassified` would
#: be flattering the paper at our own expense, which is no more honest than the
#: reverse.
#:
#: THE SECOND WIDENING, and why it was needed. MEASURED across every archived
#: run: 525 distinct refusal reasons, of which 351 -- 67% -- were `unclassified`,
#: and 66 of 70 refusal lists printed "the classifier could not place N of M
#: reasons. Read them rather than the counts." A taxonomy that abstains on two
#: thirds of its input is decoration, and the panel it feeds was reduced to the
#: undifferentiated lump it exists to prevent. After: 34%, and 37 of 70 lists.
#:
#: EVERY PATTERN BELOW WAS DERIVED FROM THE ARCHIVED TEXT, not invented, and
#: every row whose bucket moved was read individually before the change. Three
#: things that measurement changed:
#:
#:   `not provided` was simply absent. The list had `not (present|supplied|
#:   delivered)` and missed the commonest phrasing of all -- 45 rows, every one
#:   a supplement or dataset nobody sent us, all of them sitting in the lump.
#:
#:   "No PDF exists for this paper" was being filed as `paper`. It is `inputs`:
#:   the publication is not deficient, we were handed only the XML. Four rows
#:   moved OFF an implied accusation.
#:
#:   "The paper contains no data figures" is NOT a shortcoming and must not be
#:   filed under "the paper does not report it" -- a paper with no figures is an
#:   ordinary paper. It is `na`, and it is in tier 1 for the same reason the
#:   original `not applicable` rule is: an explicit statement about what the
#:   publication IS beats a keyword about what it lacks.
#:
#: One candidate was measured and DROPPED: `correctly (not reported|omitted)`.
#: Its only match in the whole corpus was a reviewer saying OUR false verdicts
#: were correctly withheld -- nothing to do with the paper. A pattern that fires
#: once, for the wrong reason, on the corpus it was derived from is not evidence.
REFUSAL_KINDS: tuple[tuple[str, str, str], ...] = (
    ("na", "does not apply here",
     r"\bnot applicable\b|\bdeliberately not (?:run|applied)\b|\binapplicab\w+|"
     r"absence is not a (?:reporting )?defect|"
     r"not a (?:reporting )?(?:defect|shortfall|deficiency)\b|"
     r"legitimate reporting choice|"
     r"(?:contains?|presents?|has|carries) no (?:data )?figures?\b|"
     r"\bno data figures\b"),
    ("ours", "our tooling",
     r"no batch form|not run by (this|the) review|returned n_tests = 0|"
     r"our (tool|extraction|harness)|exceeded the harness|no ocr|"
     r"tool (does not|doesn't) (exist|support)|"
     r"not computed by any available tool|no tool (exists|available)|"
     r"\bno (?:validated )?tool\b|\btool defect\b|n_tests\s*=\s*0|"
     r"no items parameter|"
     r"in (?:this|the) (?:kit|toolkit|toolset|suite|validated set)\b|"
     r"exceeds what can be read"),
    ("inputs", "not supplied to us",
     r"not (present|supplied|delivered|provided|in the package)|could not be read|"
     r"not deliverable|supplement(ary)? .*(not|un)(available|readable|supplied)|"
     r"embedded as an image|none (?:are|were) provided|none accompany|"
     r"could not be (?:obtained|retrieved|downloaded)|\bno pdf\b"),
    ("paper", "the paper does not report it",
     r"prints no|reports no|"
     r"no (standard deviation|test statistic|exact p|degrees of freedom|"
     r"dispersion|p-value)|nothing to recompute|appear(s)? nowhere|"
     r"not (printed|reported) (numerically|in the (main )?text)|only as bars|"
     r"no numeric|"
     r"\b(?:states|gives|provides|publishes) no\b|"
     r"\bdeclines to report\b|\bnever (?:states|reports|prints|gives)\b|"
     r"\b(?:are|is|was|were) not reported\b|not reported anywhere|"
     r"\breports? none\b|\bnone (?:are|is) reported\b|"
     r"\bexists? only (?:as|in)\b|\bbare point estimates\b|"
     r"\bno (?:sample size|baseline table|power calculation|effect sizes?)\b|\bcarries none\b|\bneeds a STATED\b|\bthe paper does not give\b|\breported with(?:out)? no\b|\bthis paper reports only\b|\bdo(?:es)? not state which\b|\bnot in the tool registry\b|\bgap in the toolkit\b"),
    ("na", "does not apply here",
     r"not applicable|deliberately|would be meaningless|would manufacture|"
     r"carries none of the meaning|no \(mean, sd\) pairs|there are no |"
     r"correctly not run|not run because|not run,? deliberately|"
     r"has no meaning here|family of one|"
     r"bars? (the|this) (check|family|test)|does not apply|"
     r"no (valid )?(null|comparison) (exists|to test)"),
)
_REFUSAL_RE = tuple((k, label, re.compile(p, re.I)) for k, label, p in REFUSAL_KINDS)

#: What each bucket MEANS, so a count is never printed without its reading.
REFUSAL_MEANING = {
    "na": ("does not apply to this paper's design",
           "Not a shortfall. The check has no meaning here, and declining to run "
           "it is the correct answer."),
    "paper": ("the paper does not report what the check needs",
              "A property of the publication. Where the paper CLAIMS to have used "
              "something it never prints, that is also a question worth putting "
              "to the authors."),
    "inputs": ("the material was not supplied to this review",
               "About our inputs, not about the paper and not about our checks."),
    "ours": ("this toolkit could not do it",
             "The only bucket that is our shortfall."),
    "unclassified": ("not classified",
                     "The reason did not match any rule. Read it below rather "
                     "than trusting a count."),
}

#: Above this share of `unclassified`, the counts are not worth reading and the
#: tally must say so rather than presenting a mostly-empty breakdown as an
#: answer. One third, matching the design review's recommendation.
UNCLASSIFIED_ALARM = 1 / 3


def classify_refusal(reason: str | None) -> dict:
    """Whose limit produced this refusal: theirs, ours, or nobody's."""
    s = str(reason or "")
    for key, label, rx in _REFUSAL_RE:
        if rx.search(s):
            return {"key": key, "label": label}
    # "not classified" was OUR bookkeeping word, printed in a column headed
    # "whose limit". A reader met it as though the row were a defect of unknown
    # kind. It is the opposite: nothing has been established about this row, and
    # the reason beside it is the whole answer. The alarm for us is unchanged --
    # `refusal_tally` still counts these and still fires -- but the LABEL now
    # points the reader at the text instead of announcing a failure.
    return {"key": "unclassified", "label": "see the reason given"}


def refusal_tally(rows: Iterable[dict] | None) -> dict:
    """Counts per bucket, plus an honest warning when the classifier is failing.

    The warning is the part that matters. A breakdown in which most rows are
    `unclassified` looks like an answer and is not one, and the mechanism exists
    precisely so the shortfall list does not read as work abandoned.
    """
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    counts: dict[str, int] = {}
    for r in rows:
        k = classify_refusal(r.get("reason"))["key"]
        counts[k] = counts.get(k, 0) + 1

    n = len(rows)
    unclassified = counts.get("unclassified", 0)
    share = (unclassified / n) if n else 0.0
    out = {
        "n": n,
        "counts": counts,
        "unclassified_share": round(share, 4),
        "classifier_failing": bool(n) and share > UNCLASSIFIED_ALARM,
        "order": [k for k in ("na", "paper", "inputs", "ours", "unclassified")
                  if counts.get(k)],
        "meaning": REFUSAL_MEANING,
    }
    # THE SENTENCE A READER SHOULD SEE FIRST, computed here rather than in the
    # page. Greg, 2026-08-11: "it wouldn't do to have the user come away with
    # the impression that there were more errors and omissions than there
    # actually are." A bare count of refusals is exactly that impression -- it
    # reads as a task list abandoned. Only the `ours` bucket is a shortfall of
    # this review; `na` is the check correctly declining, `paper` is a property
    # of the publication, and `inputs` is material nobody sent us. Say the split
    # before showing the list.
    not_ours = sum(counts.get(k, 0) for k in ("na", "paper", "inputs"))
    ours = counts.get("ours", 0)
    if n:
        if not ours:
            reading = (f"{n} check{'s' if n != 1 else ''} did not run. "
                       f"{'None' if n != 1 else 'It'} "
                       "did so because of a limitation of this toolkit -- each "
                       "either does not apply to this paper, needs a number the "
                       "paper does not print, or needed material nobody supplied.")
        elif ours == n:
            reading = (f"All {n} of these are limitations of this toolkit.")
        else:
            reading = (f"{n} checks did not run. {ours} of them because this "
                       f"toolkit could not do it; the other {not_ours + unclassified} "
                       "either do not apply to this paper, need a number the paper "
                       "does not print, or needed material nobody supplied to us.")
    else:
        reading = ""
    out["not_our_shortfall"] = not_ours
    out["our_shortfall"] = ours
    out["reading"] = reading

    if out["classifier_failing"]:
        out["warning"] = (
            f"The classifier could not place {unclassified} of {n} reasons. "
            "Read them rather than the counts."
        )
    return out
