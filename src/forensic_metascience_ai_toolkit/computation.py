"""No number reaches a reader without a record of where it came from.

GREG, 2026-08-13: "It should be impossible for an agent to perform computations
and it not be recorded for the sake of the output. That's black box nonsense I
want to avoid."

The rule is stronger than "prefer a tool". A finding that presents a NUMBER must
show, in the artefact, either the tool result that produced it or the method
that did.

BUT AN UNRECORDED NUMBER IS NOT A FABRICATED ONE, and the difference is most of
this module. GREG, 2026-08-13: "I am a little concerned about the idea of
outright discarding findings with no provenance given to their numbers... I
suspect that many of these can be 'rescued' by a search for the actual values.
In this project I haven't seen the model outright fabricate numbers."

MEASURED, and he is right: 320 of the 369 figures in non-tool findings (86.7%)
are found in the paper's own text.

THAT FIGURE WAS 93.2% UNTIL A STRESS TEST FOUND THE MATCHER WRONG, 2026-08-13.
`locate` used plain containment, so `12` counted as "found" in a paper that only
prints `3124` -- and the error ran in the DANGEROUS direction: a figure the
agent produced was rescued as a quotation of a number the paper never printed.
`quotes._contains_bounded` had already solved this exact problem after "n = 42"
verified verbatim against "n = 428"; I reached for `in` instead of the module
that had been bitten. The conclusion survives the correction, which is the point
of stating it: 86.7% is still "nearly always a transcription".

The remaining 49 (13.3%) look DERIVED rather than invented -- 1.56, 3.125,
0.923, values with the shape of an intermediate result. So the defect is
unrecorded TRANSCRIPTION and unrecorded DERIVATION, not fabrication, and
discarding on that basis would throw away real findings to punish a bookkeeping
failure.

So nothing is discarded. The number is LOCATED first, and the finding is
labelled by which case it is:

    transcribed   the figure appears in the paper. It is a quotation, not a
                  computation, and the only thing missing is a locator.
    derived       it does not appear, but a method is stated. Auditable.
    unaccounted   it appears nowhere and no method is given. The rare, serious
                  case -- and even here the finding is reported, not deleted.

WHY THE OLD LABEL COULD NOT SUPPORT THIS. `technique: "manual"` meant "no tool
computed this", and it was doing three unrelated jobs at once.

MEASURED 2026-08-13 over 626 findings, deduplicated by (id, location, claim,
computed) across every findings.json in the checkout -- each run is stored twice,
under `forensic_review_*` and again inside its bundle, so an undeduplicated count
inflates every figure. 159 of the 626 are `manual` (25.4%), and bucketing them by
whether `computed` carries a numeric literal:

    103  (64.8%)  a number was computed unaided
     36  (22.6%)  a note, not a number
     20  (12.6%)  no computation recorded at all

So a third of the label named findings with NO ARITHMETIC IN THEM -- a
data-availability statement that withholds data, a figure legend describing the
wrong protein, three asterisks against a p of .004 -- which the schema was
capping at `suspicious` on the grounds that unaided arithmetic is unsafe. There
was no arithmetic. Those are `logical` warrants, the class the stage-2 prompt
itself calls the most valuable thing it produces, and they were being suppressed
by a label that misdescribed them.

The three cases now have three names, and only two of them concern computation:

    not_computational    no arithmetic exists to guard; not capped for it
    no_tool_exists       arithmetic, no registered tool covers it; capped
    tool_existed_unused  arithmetic a tool could have done; capped, and re-run it

`verify` below enforces the recording rule against whichever case is claimed.
It reports; it does not silently rewrite, because a finding quietly stripped of
its number is as opaque as one that never showed its working.
"""

from __future__ import annotations

import re
from typing import Any

#: Whether each non-tool technique is ALLOWED to carry a number.
#:
#: THE MEMBERSHIP IS NOT DECIDED HERE. `prompts.NON_TOOL_TECHNIQUES` is the
#: spec (its own comment: "the six fixed non-tool technique values, spec
#: section 1.2"), and this file used to keep a hand-written four. The two
#: disagreed on FOUR of seven members, and the disagreement was not cosmetic:
#: `classify` returns "tool" for anything absent from THIS mapping, so
#: `internal_contradiction` and `factual_claim` -- techniques the spec names as
#: NON-tool -- were reported as arithmetic a registered tool performed and the
#: ledger could prove. Seven live rows on the run of 2026-08-29.
#:
#: It was inert until 2026-08-29 only because `secondlook` was itself inert
#: (its severity vocabulary had frozen), so nothing downstream read the answer.
#: Fixing that gate armed this one. Both go in one change, deliberately: a
#: latent wrong answer under a guard that has just been switched on is not a
#: separate problem, it is the same problem one step later.
_MAY_CARRY_A_NUMBER: dict[str, bool] = {
    # A number here CONTRADICTS the claim -- the finding says it computed
    # nothing.
    "not_computational": False,
    # These say the arithmetic happened outside the guards; a number is the
    # whole point, and `did_unaided_arithmetic` reads exactly these two.
    "no_tool_exists": True,
    "tool_existed_unused": True,
    # A claim about what the paper says, or about two of its statements
    # disagreeing. Both may quote figures; neither is arithmetic WE did.
    "factual_claim": True,
    "internal_contradiction": True,
    # Legacy labels. `manual` is v1 and absent from the v2 spec, so it is added
    # here rather than derived; it says nothing usable and is decided by its
    # CONTENTS in `did_unaided_arithmetic`, which is the recorded lesson.
    "legacy_unattributed": True,
    "manual": True,
}

def _non_tool_techniques() -> dict[str, bool]:
    """The spec's membership, with this file's may-carry-a-number flags.

    Derived, so the two cannot drift again. A spec member with no flag here
    defaults to True -- the safe direction: it keeps the technique OUT of the
    "a tool computed this" answer, which is the claim that has to be earned.
    """
    try:
        from .core.prompts import NON_TOOL_TECHNIQUES as _spec
    except Exception:  # noqa: BLE001 -- never fail an import over this
        _spec = ()
    out = {t: _MAY_CARRY_A_NUMBER.get(t, True) for t in _spec}
    # `manual` is v1-only and not in the v2 spec; carried explicitly.
    out.setdefault("manual", _MAY_CARRY_A_NUMBER["manual"])
    return out


NON_TOOL_TECHNIQUES: dict[str, bool] = _non_tool_techniques()

#: Only these mean "a tool did the arithmetic and the ledger can prove it".
LEGACY = "manual"

#: A numeric literal inside a `computed` block. NOT `numerals.NUMERAL`, and the
#: difference is deliberate: that pattern refuses a digit glued to a word, which
#: is right for prose and wrong here. A computed block is a stringified dict
#: whose KEYS carry figures -- `unique_viable_n_for_61pct_within_n_max_19` --
#: and this guard exists to ask whether a figure the agent presented came out of
#: the paper. Dropping the ones spelled inside key names would make it ask a
#: smaller question. MEASURED: switching to the shared tokenizer would have
#: dropped 346 such figures across 116 of the 225 archived computed blocks.
#:
#: THE LEADING MINUS IS THE PART THAT WAS WRONG. `-?\d+` read the separator in
#: `rows 1-8, 9-16, 17-24` as a sign and reported -8, -16 and -24 as figures
#: the finding presented. Those appear nowhere in any paper, so they land in
#: `unlocated` and the finding is stamped `number_derived`: "appear nowhere in
#: the paper ... so the agent produced them. Show the derivation." A verbatim
#: transcription accused of unaudited arithmetic, over a hyphen.
#:
#: 21 such spurious negatives sit in the nine archived papers. None reached that
#: stamp, because those findings are `kind == "tool"` and skip the branch -- so
#: this is a latent defect fixed before it fired, not one caught firing.
#:
#: A minus is a sign only when nothing numeric precedes it. After a digit or a
#: closing bracket it is a range separator, and `1-8` is two numbers.
_NUMBER = re.compile(r"(?<![\d)\]])-\d+(?:\.\d+)?|\d+(?:\.\d+)?")


#: Significant digits below which a figure cannot distinguish a quotation from
#: a coincidence. Three is the same judgement `quotes._MIN_FRAGMENT` makes
#: about short strings, applied to numbers.
_MIN_SIGNIFICANT_DIGITS = 3


def _significant_digits(number: str) -> int:
    """How many significant digits this literal carries."""
    digits = str(number).lstrip("-+").replace(".", "").lstrip("0")
    return len(digits.rstrip("0")) if "." not in str(number) else len(digits)


def _is_informative(number: str) -> bool:
    """Is this figure specific enough that finding it means something?"""
    return _significant_digits(number) >= _MIN_SIGNIFICANT_DIGITS


def _numbers_in(value: Any) -> list[str]:
    """Every numeric literal in a `computed` block, however nested."""
    if value is None:
        return []
    return _NUMBER.findall(str(value))


def classify(finding: dict) -> str:
    """What kind of computation, if any, does this finding rest on?"""
    if not isinstance(finding, dict):
        return "unknown"
    tech = str(finding.get("technique") or "").strip()
    if tech and tech not in NON_TOOL_TECHNIQUES:
        return "tool"
    return tech or "unstated"


def did_unaided_arithmetic(finding: dict) -> bool:
    """Did a model, rather than a registered tool, produce this finding's numbers?

    Both `tool_existed_unused` and `no_tool_exists` say so outright: the
    arithmetic happened outside the guards, and the only difference between them
    is whether a tool COULD have done it. The risk to a reader is identical, so
    both answer yes here and the remedy is spelled out where the marker is read.

    `manual` -- the legacy label -- says nothing usable, and reading it as though
    it did was the original defect. MEASURED 2026-08-13 over 626 deduplicated
    archived findings: 159 are `manual`, and 56 of them (35.2%) carry NO NUMBER
    AT ALL -- `computed` is `{}` or absent. Treating the label as proof of
    arithmetic flagged 95 accusations where the contents justify 64. So the
    legacy label is decided by its CONTENTS, which is the whole lesson.

    Deciding it by contents also means the guard cannot silently stop guarding
    if a run keeps emitting `manual` after the vocabulary split.
    """
    kind = classify(finding)
    if kind in ("tool_existed_unused", "no_tool_exists"):
        return True
    if kind == LEGACY:
        return bool(_numbers_in((finding or {}).get("computed")))
    return False


def locate(number: str, haystack: str | None) -> bool:
    """Does this figure appear in the paper, in any of its printed forms?

    Uses the same matcher as the quote verifier, so `0.99` and `.99` and `12,345`
    and `12345` are one number here exactly as they are there.
    """
    if not haystack or not str(number).strip():
        return False
    # `_contains_bounded`, NOT `in`. A plain containment test reports `12` as
    # present in a paper that only ever prints `3124`, and here that is the
    # dangerous direction: a figure the agent produced would be "rescued" as a
    # transcription of a number the paper never printed, and reported to the
    # reader as a quotation.
    #
    # CAUGHT BY A STRESS TEST 2026-08-13, and the fix already existed. `quotes`
    # solved this for quote verification after "n = 42" verified verbatim
    # against "the final sample was n = 428"; I reached for `in` instead of the
    # module that had already been bitten.
    try:
        from .quotes import _number_forms, _contains_bounded
        return any(f and _contains_bounded(f, haystack)
                   for f in _number_forms(str(number)))
    except Exception:  # noqa: BLE001
        # Fail CLOSED. The fallback used to be `in`, which is the bug; refusing
        # to locate is a missed rescue, and a missed rescue costs a locator
        # while a false rescue costs the reader a fabricated quotation.
        return False


#: Every distinct way a computation record can fail, and what each one means.
#: THEY ARE COUNTED SEPARATELY BECAUSE THEY ARE NOT THE SAME COMPLAINT. A first
#: cut lumped them into one total and then described the total as "N present a
#: number the artefact cannot account for" -- on the three archived runs it was
#: first run against, all 24 were `legacy_label` and NONE was an unaccounted
#: number. Saying it in one sentence was a false statement about our own work,
#: which is exactly what this module refuses to let a paper get away with.
PROBLEM_CODES: dict[str, str] = {
    "legacy_label": "used `manual`, which cannot say whether arithmetic exists",
    "number_under_not_computational":
        "declared no arithmetic and then presented some",
    "number_derived":
        "presents a figure that is NOT in the paper, so the agent produced it "
        "-- the derivation is what a reader has to be shown",
    "number_transcribed":
        "every figure it presents is in the paper verbatim: a quotation "
        "missing its locator, not a computation (RESCUED)",
    "number_uncheckable_no_paper":
        "presents a figure we could not check, because the paper would not "
        "open (OUR gap)",
    "technique_unstated": "no technique named at all",
}

#: Which of the above leave a number's provenance genuinely UNKNOWN.
#:
#: `number_derived` is deliberately absent, and the measurement is why. The
#: first cut tried to decide "is a method recorded?" by looking for prose beside
#: the figure -- 12+ letters in `computed`. MEASURED 2026-08-13 over the 18
#: archived findings that present a figure absent from their paper: it passed
#: 18 and failed 0, because `computed` is a dict and its KEYS are words.
#: `{'fisher_odds_ratio_from_recalc': 1.56}` and `{'difference': 10576}` scored
#: identically, and the first names its derivation while the second does not.
#: A guard that cannot separate those is not a guard (LESSONS.md #4), and one
#: that cannot fire while reading as though it had is worse than none.
#:
#: So the undecidable half is not guessed at. What IS decidable -- did this
#: figure come out of the paper, or out of the agent? -- is decided exactly, and
#: every agent-produced figure is NAMED in the ledger for a reader to check.
#: That is the black-box rule as far as code can honestly take it.
BLOCKING = ("legacy_label", "number_under_not_computational",
            "number_uncheckable_no_paper", "technique_unstated")


def verify(finding: dict, haystack: str | None = None) -> dict:
    """Is this finding's arithmetic auditable? Reports, never rewrites.

    Returns `codes` alongside the prose so a caller can count the failures
    APART -- see `PROBLEM_CODES` for why that is not a nicety.
    """
    kind = classify(finding)

    # NOT A FINDING AT ALL, and it used to be reported as auditable.
    #
    # `classify` returns "unknown" only when the input is not a dict. No branch
    # matched it, so it fell through to the closing return, where `codes` is
    # empty and `auditable` is therefore True: a thing that is not a finding,
    # reported as a finding whose arithmetic checks out.
    #
    # PLACED HERE, BEFORE THE LINE BELOW, because `(finding or {}).get(...)`
    # crashes on a non-empty STRING -- truthy, and no `.get`. Checking after it
    # fixed None and [] and left 'x' raising AttributeError, which testing three
    # input types rather than one is what caught.
    #
    # Latent rather than live: reaching it needs a caller passing a non-dict,
    # itself a bug elsewhere. Fixed anyway, being the same shape as five other
    # defects found the same night -- an absence spelled exactly like a pass.
    if kind == "unknown":
        return {"kind": kind, "auditable": False,
                "problems": ["this is not a finding object, so whether its "
                             "arithmetic is auditable could not be assessed"],
                "codes": ["not_a_finding"],
                "n_numbers": 0, "transcribed": False}

    computed = (finding or {}).get("computed")
    nums = _numbers_in(computed)
    problems: list[str] = []
    codes: list[str] = []
    transcribed = False

    def _fail(code: str, text: str) -> None:
        codes.append(code)
        problems.append(text)

    if kind == "tool":
        return {"kind": kind, "auditable": True, "problems": [], "codes": [],
                "n_numbers": len(nums), "transcribed": False}

    if kind == LEGACY:
        _fail("legacy_label",
              "`manual` does not say whether this finding involves arithmetic "
              "at all, so neither the cap nor the audit can be applied "
              "correctly. Use not_computational / no_tool_exists / "
              "tool_existed_unused.")

    if kind == "not_computational" and nums:
        _fail("number_under_not_computational",
              f"declared `not_computational` and yet presents {len(nums)} "
              "number(s) in `computed`. Either the finding rests on arithmetic "
              "-- in which case say which of no_tool_exists / "
              "tool_existed_unused applies -- or the numbers do not belong here.")

    if kind in ("no_tool_exists", "tool_existed_unused", LEGACY) and nums:
        # THE ONE QUESTION CODE CAN ANSWER: did this figure come out of the
        # paper, or out of the agent? Everything else about a computation
        # record needs judgement, and pretending otherwise built a guard that
        # fired on 2 of 626 archived findings and on 0 of the 18 that actually
        # needed it. MEASURED 2026-08-13: 86.7% of the 369 figures in non-tool
        # findings are in their paper VERBATIM. Greg, 2026-08-13: "I haven't
        # seen the model outright fabricate numbers" -- correct, and the
        # remaining 6.8% are the ones worth a reader's attention.
        if not haystack:
            _fail("number_uncheckable_no_paper",
                  f"presents {len(nums)} figure(s), and the paper could not be "
                  "read to tell a transcription from a computation. This is "
                  "OUR gap, not the finding's.")
        else:
            unlocated = [n for n in nums if not locate(n, haystack)]
            if not unlocated and not any(_is_informative(n) for n in nums):
                # LOCATED, BUT ON NOTHING. `12`, `0.05`, `95`, `2` are printed
                # in essentially every paper -- as a figure number, a table
                # cell, an alpha, a CI level, a count of anything. Finding one
                # is not evidence that this finding QUOTED it.
                #
                # The rescue is all-or-nothing over the finding's numbers, so a
                # single-number finding whose number is small was rescued
                # unconditionally: `{"difference": 12}`, produced by the agent
                # subtracting 40 - 28 unaided, is "rescued" by any `12` in the
                # paper and reported to the reader as a quotation. Withdrawing
                # the demand "Show the derivation" on that basis is the
                # expensive half of the error.
                #
                # Same principle as `quotes._MIN_FRAGMENT`: a string too common
                # to distinguish anything cannot carry a verdict. At least one
                # figure must have three significant digits before the whole
                # finding is called a transcription.
                _fail("number_transcribed_uninformative",
                      f"all {len(nums)} of its figure(s) appear in the paper, "
                      "but none carries enough information to tell a quotation "
                      "from a coincidence -- small round numbers are printed in "
                      "every paper. Treated as a computation. Add "
                      "`source_quote`/`source_locator` to settle it.")
            elif not unlocated:
                transcribed = True
                _fail("number_transcribed",
                      f"every one of its {len(nums)} figure(s) appears in the "
                      "paper verbatim, so this is a TRANSCRIPTION with a "
                      "missing locator, not a computation. Add "
                      "`source_quote`/`source_locator` and it is fully "
                      "auditable.")
            else:
                shown = ", ".join(dict.fromkeys(unlocated[:6]))
                _fail("number_derived",
                      f"{len(unlocated)} of its {len(nums)} figure(s) appear "
                      f"nowhere in the paper -- {shown} -- so the agent "
                      "produced them, with no registered tool to answer for "
                      "the arithmetic. Show the derivation.")

    if kind == "unstated":
        _fail("technique_unstated",
              "names no technique at all, so nothing records what produced this "
              "finding.")

    return {"kind": kind,
            "auditable": not any(c in BLOCKING for c in codes),
            "problems": problems, "codes": codes,
            "n_numbers": len(nums), "transcribed": transcribed}


def audit(findings: list[dict], haystack: str | None = None) -> dict:
    """Every finding's computation record, and what is unauditable.

    `haystack` is the paper's own text -- ITS ABSENCE IS NOT A CLEAN RESULT. A
    bare number can only be rescued as a transcription if there is something to
    look it up in, so an audit run without one reports `paper_readable: False`
    and every bare number lands as OUR gap rather than the finding's. That
    distinction is the whole reason this argument exists: 86.7% of the 369
    figures in archived non-tool findings are in their paper verbatim, and a
    rescue that never runs would condemn all of them.

    `n_derived` and `n_transcribed` are the counts to read. A row carrying both
    a blocking code and a ledger code is filed under `unauditable`, so `ledger`
    holds only rows whose remarks are ledger remarks -- on the archive, where
    every finding predates the vocabulary split, that list is empty while
    `n_derived` is not. An empty `ledger` is not a count of zero.
    """
    blocking, ledger, by_kind, by_code = [], [], {}, {}
    n_transcribed = 0
    for f in (findings or []):
        if not isinstance(f, dict):
            continue
        v = verify(f, haystack)
        by_kind[v["kind"]] = by_kind.get(v["kind"], 0) + 1
        if v.get("transcribed"):
            n_transcribed += 1
        for c in v["codes"]:
            by_code[c] = by_code.get(c, 0) + 1
        if not v["problems"]:
            continue
        row = {"id": f.get("id"), "severity": f.get("severity"),
               "kind": v["kind"], "codes": v["codes"],
               "problems": v["problems"], "auditable": v["auditable"],
               "transcribed": bool(v.get("transcribed"))}
        # TWO LISTS, because they are two different things and one list would
        # make the reader treat them alike. `unauditable` is where the
        # provenance is unknown; `ledger` is every figure the agent produced or
        # copied, recorded so it can be checked -- which is the point.
        (blocking if not v["auditable"] else ledger).append(row)
    total = sum(by_kind.values())
    return {
        "n_findings": total,
        "by_kind": by_kind,
        "n_unauditable": len(blocking),
        "unauditable": blocking,
        "n_ledger": len(ledger),
        "ledger": ledger,
        "by_code": by_code,
        "code_meanings": {c: PROBLEM_CODES[c] for c in by_code
                          if c in PROBLEM_CODES},
        "paper_readable": bool(haystack),
        "n_transcribed": n_transcribed,
        "n_derived": by_code.get("number_derived", 0),
        "note": _note(total, by_kind, by_code, bool(haystack)),
    }


def _note(total: int, by_kind: dict, by_code: dict, readable: bool = True) -> str:
    """Say what actually failed, one clause per FAILURE, never one total.

    A single count described as "N present a number the artefact cannot account
    for" was false on the first three runs it met: all 24 were legacy labels and
    none was an unaccounted number.
    """
    if not total:
        return "No findings to audit."
    head = (f"{total} finding(s): {by_kind.get('tool', 0)} computed by a "
            f"registered tool, {by_kind.get('not_computational', 0)} resting "
            "on no arithmetic at all, "
            f"{by_kind.get('no_tool_exists', 0)} on arithmetic no tool covers, "
            f"{by_kind.get('tool_existed_unused', 0)} on arithmetic a tool "
            f"could have done, {by_kind.get(LEGACY, 0)} on the legacy "
            "`manual` label.")
    if not by_code:
        return head + " Every number presented is recorded with its provenance."

    said = []
    if by_code.get("number_derived"):
        said.append(f"{by_code['number_derived']} present a figure that is NOT "
                    "in the paper, so the agent produced it -- each one is "
                    "named, and its derivation is what to check")
    if by_code.get("number_under_not_computational"):
        said.append(f"{by_code['number_under_not_computational']} declare no "
                    "arithmetic and then present some")
    if by_code.get("technique_unstated"):
        said.append(f"{by_code['technique_unstated']} name no technique at all")
    if by_code.get("legacy_label"):
        said.append(f"{by_code['legacy_label']} use the legacy `manual` label, "
                    "which cannot say whether arithmetic is involved -- OUR "
                    "vocabulary gap, not a claim about the finding")
    if by_code.get("number_uncheckable_no_paper"):
        said.append(f"{by_code['number_uncheckable_no_paper']} present a "
                    "figure THE PAPER COULD NOT BE READ to check, so a "
                    "transcription is indistinguishable here from an invention "
                    "-- also our gap")
    if by_code.get("number_transcribed"):
        said.append(f"{by_code['number_transcribed']} present figures that are "
                    "ALL in the paper verbatim, so they are RESCUED as "
                    "quotations missing a locator rather than computations "
                    "missing a method")

    # NOT `.capitalize()`, which lowercases everything after the first
    # character -- it silently flattened "OUR gap", "NOT in the paper" and
    # "THE PAPER COULD NOT BE READ" into unemphasised prose, and the only
    # reason it was caught is a test that read the rendered sentence.
    body = "; ".join(said)
    return (head + " " + body[:1].upper() + body[1:] + ". Nothing here is "
            "deleted: an unrecorded number is not a fabricated one, and the "
            "pattern of what needed rescuing is itself worth reading.")
