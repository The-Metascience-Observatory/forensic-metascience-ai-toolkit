"""Put the passage a check's numbers came from onto the FINDING that cites them.

WHY THIS EXISTS
---------------
Greg's standing requirement: "every number a check cites must be traceable to a
VERBATIM QUOTE of the source text/cell it came from, surfaced in the findings so
a reader (and an evaluating agent) can see the number in its original context
without opening the PDF."

Three of the four pieces already existed. Every verdict-rendering tool takes
`source_quote`/`source_locator`; `quotes.verify_ledger` adjudicates each claim
against the paper afterwards, because a self-assessment by the party being
checked is not a check; and the viewer shows it per call in Chain of reasoning.

What was missing is the join. The quote lived on the CALL and the accusation
lives on the FINDING, and nothing connected them -- so a reader looking at
"the mean is impossible for this n" still had to go and find the ledger entry
that produced it. A provenance record one indirection away from the claim it
justifies is one nobody follows.

WHY IT REUSES `severity_reconcile`'S JOIN
-----------------------------------------
That join is the same question asked for a different field -- "which validated
call produced this finding?" -- and it took three separate corrections to get
right (family-vs-member technique labels, batch expansion, tools dispatched
inside other tools; see `_TECHNIQUE_TOOLS`). A second copy would drift, and the
two would then disagree about which call a finding came from while confidently
labelling both the severity and the quote. Importing the private helpers is the
lesser evil, and deliberate.

MEASURED, over 377 findings across the 15 archived runs that have both a
findings file and a stage-1 ledger. The archived runs predate the prompt asking
for quotes, so each call was given a synthetic one and the JOIN was measured:

    92 of 377 (24%)   `technique: manual` -- no producing call exists, and
                      these are excluded from the denominator rather than
                      counted as misses (see `annotate`).
    126 of 285 (44%)  joined when every call quotes a DIFFERENT passage, which
                      is the worst case for the unanimity rule below.
    193 of 285 (68%)  joined when calls of the same tool share a passage, which
                      is what a real run looks like: the model quotes the row
                      it read, and two checks on that row quote it identically.

The first version of this join scored 27%. The gap was one bug, found by
measuring rather than by reading: tools taking LIST arguments
(`check_summation`, `detect_duplication`, `multiplicity_report`) contribute no
comparable scalars, so requiring the finding's numbers to appear in the call
excluded them on every occasion -- even when only one call of that tool existed.

THE FAILURE THIS MUST NOT CAUSE
-------------------------------
Attaching the WRONG passage is worse than attaching none. "Here is the text your
number came from", pointing at a different row, is precisely the house failure
pattern -- our join error, published in the grammar of a claim about the paper --
and it is more corrosive than most, because a quote is the thing a reader trusts
INSTEAD of checking. So the bar here is higher than for severity:

  * UNANIMITY IS ON THE QUOTE TEXT, not merely on the tool. Two calls of the
    same tool that match a finding's scalars and carry DIFFERENT passages mean
    we cannot say which row the model meant, and we attach nothing.
  * A quote the verifier could not locate (`stitched`, `unverified`) is carried
    but never presented as "as printed" -- the renderers draw that line, and
    this module preserves the verdict so they can.
  * Nothing is inferred. If no call joins, the finding keeps whatever `quote`
    the model wrote for itself and this module is silent.
"""

from __future__ import annotations


from .severity_reconcile import _candidate_tools, _comparable, _scalars

#: Copied onto the finding, in this order, under `source`.
_FIELDS = ("source_quote", "source_locator",
           "source_quote_verified", "source_quote_source")


def quotes_from_ledger(ledger: list[dict] | None) -> list[tuple[str, set, dict]]:
    """(tool name, argument scalars, sourcing fields) for every validated call.

    Only validated calls, and only calls that actually supplied a quote. An
    unvalidated call is the model running its own code, and a call with no
    quote has nothing to contribute -- both would otherwise dilute the
    unanimity test below and cost real joins.

    Batch calls are NOT expanded per row here, unlike the severity join. A
    batch carries ONE `source_quote` covering the whole table (the prompt asks
    for the caption or the footnote that says what the cells mean), so
    attributing it to an individual row would claim a precision the argument
    never had.
    """
    out: list[tuple[str, set, dict]] = []
    for call in ledger or []:
        if not isinstance(call, dict) or not call.get("validated"):
            continue
        args = call.get("input")
        if not isinstance(args, dict):
            continue
        quote = args.get("source_quote")
        if not (isinstance(quote, str) and quote.strip()):
            continue
        payload = {"source_quote": " ".join(quote.split())}
        locator = args.get("source_locator")
        if isinstance(locator, str) and locator.strip():
            payload["source_locator"] = locator.strip()
        # From the ENTRY, never from `input`: a verdict inside the arguments
        # would be the model's own, and the party being checked cannot certify
        # itself. `quotes.verify_ledger` writes these onto the entry.
        for key in ("source_quote_verified", "source_quote_source"):
            value = call.get(key)
            if isinstance(value, str) and value.strip():
                payload[key] = value.strip()
        out.append((str(call.get("tool_short") or ""), _scalars(args), payload))
    return out


def _source_for(finding: dict,
                from_ledger: list[tuple[str, set, dict]]) -> dict | None:
    """The sourcing of the call that produced this finding, if it is unambiguous."""
    tools = _candidate_tools(finding.get("technique"))
    if not tools or not from_ledger:
        return None
    candidates = [(args, payload) for name, args, payload in from_ledger
                  if name in tools]
    if not candidates:
        return None
    wanted = _comparable(_scalars(finding.get("inputs")))
    if wanted:
        # A call with NO comparable scalars of its own cannot be discriminated
        # by scalars, so requiring the finding's numbers to appear in it rules
        # it out on every occasion -- including when it is the only call of
        # that tool. This is not hypothetical: `check_summation`,
        # `detect_duplication` and `multiplicity_report` take LISTS, `_scalars`
        # drops lists, and MEASURED over the archived corpus this alone
        # accounted for most of the 101 findings that matched a tool and then
        # failed on scalars. The emptiness is on the CALL side rather than the
        # finding side, but the argument is the one already written into
        # `_tool_severity` for the mirror case: nothing to join on, so let the
        # unanimity rule below decide.
        hits = [p for args, p in candidates
                if not _comparable(args) or wanted <= _comparable(args)]
    else:
        # Nothing comparable to join on. The tool still ran, and if every call
        # of it quoted the SAME passage then that passage is this finding's
        # whichever call produced it. Most findings land here: `inputs` is
        # written for a human and is mostly prose.
        hits = [p for _, p in candidates]
    if not hits:
        # SCALAR MATCHING FAILED ENTIRELY -- try the locator before giving up.
        #
        # `wanted <= _comparable(args)` demands the finding's numbers be a
        # SUBSET of the call's, and a finding that records its own
        # `decimals_mean` or `p_is_threshold` slightly differently from the call
        # fails that test on a technicality while plainly describing the same
        # row. MEASURED on 10.1007--s11064-023-03861-8: all 8
        # rivets_independent_t findings carry full scalars, none is a subset of
        # its call, and every one names its table row in prose that the call's
        # own locator nearly repeats.
        return _disambiguate_by_locator(finding, [p for _, p in candidates])
    # Unanimity ON THE QUOTE. Several calls may match; if they all read from
    # the same passage, that passage is this finding's regardless of which one
    # it was. If they read from different ones, we cannot say which row the
    # model meant, and a guess here would attach one row's evidence to another
    # row's accusation.
    distinct = {p["source_quote"] for p in hits}
    if len(distinct) != 1:
        # THE QUOTES DISAGREE -- SO ASK WHERE EACH CALL SAID IT WAS LOOKING.
        #
        # Refusing is right when we genuinely cannot tell which row the model
        # meant. But often we CAN tell and were discarding the answer: the
        # finding names its location in prose, every call carries a
        # `source_locator` naming its own, and the two are frequently near
        # verbatim. The join keyed on `reported` alone and never looked.
        #
        # MEASURED on 10.1007--s11064-023-03861-8: 8 rivets_independent_t calls,
        # 8 findings, 1 joined. Each finding's `reported` is
        # {"marker": "*", "meaning": "P < 0.05 from control group"} -- a
        # significance marker with nothing numeric to match -- while its
        # location reads "Table 2, Respiration cycle/min, Nerve Lesion 4 wk
        # (12 +/- 9*) vs Control (14 +/- 3)" and the call's locator reads
        # "Table 2, Respiration cycle/min column: Nerve Lesion...".
        #
        # UNIQUENESS IS STILL REQUIRED. A tie refuses exactly as before. This
        # narrows an ambiguous set; it never picks a winner from equals, because
        # attaching one row's evidence to another row's accusation is the false
        # attribution this module exists to prevent.
        return _disambiguate_by_locator(finding, hits)
    # Among calls quoting the same passage, prefer the richest record: one may
    # carry a locator or a located verdict that another omitted, and dropping
    # it would lose information no other call disputes.
    return max(hits, key=lambda p: len(p))


#: Words that appear in almost every locator and so discriminate nothing.
_LOCATOR_STOP = frozenset({
    "table", "column", "row", "figure", "results", "section", "vs", "and",
    "the", "of", "in", "at", "for", "from", "paragraph", "value", "values",
})


def _locator_tokens(text: str) -> set[str]:
    """Content words of a locator, lowercased, minus the boilerplate.

    Numbers are kept AT ANY LENGTH, including single digits. A first version
    dropped tokens shorter than two characters and that discarded the only
    discriminating token in the case this was written for: two calls tied at
    overlap 9 on "Nerve Lesion 4 wk" and "Nerve Lesion 10 wk", the finding said
    "4 wk", and the filter had thrown the 4 away. Short words are still dropped
    -- they are articles, not identifiers.
    """
    import re
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if t not in _LOCATOR_STOP and (len(t) > 1 or t.isdigit())}


def _disambiguate_by_locator(finding: dict, hits: list[dict]) -> dict | None:
    """Pick the one call whose locator matches this finding's location best.

    Returns None unless exactly one candidate scores highest AND shares real
    content with the finding -- a weak best match is still a guess.
    """
    want = _locator_tokens(str(finding.get("location") or ""))
    if len(want) < 2:
        return None
    want_nums = {t for t in want if t.isdigit()}
    scored = []
    for p in hits:
        got = _locator_tokens(str(p.get("source_locator") or ""))
        overlap = want & got

        # NUMBERS DISCRIMINATE; WORDS ARE FURNITURE. Word overlap alone chose
        # the WRONG ROW, verified 2026-08-18: finding at "Table 3, control
        # group, week 4", candidates "Table 3, control group, week 12" (wrong)
        # and "Table 3, wk 4 control" (the true producer). The wrong one won
        # 4-3, because `control`, `group` and `week` are boilerplate shared by
        # every row of that table while the only token that identifies the ROW
        # -- the 4 -- counted exactly as much as the word "the" would have.
        #
        # A locator's numbers are what name the row, column or timepoint. So a
        # candidate carrying a number the finding does NOT name is describing a
        # different place, and is disqualified rather than merely outscored.
        # `week 12` cannot be the producer of a finding about `week 4`.
        #
        # This can refuse a legitimate range ("Table 3, rows 4-8" for a finding
        # about row 4), and that is the safe direction: no attribution beats a
        # confident wrong one, which is rendered to the reader as a bold
        # "Numbers read from".
        got_nums = {t for t in got if t.isdigit()}
        if want_nums and (got_nums - want_nums):
            continue

        # Two shared content words is the floor. One ("table") is a coincidence
        # waiting to happen even after the stop list.
        if len(overlap) >= 2:
            scored.append((len(overlap), p))
    if not scored:
        return None
    best = max(s for s, _ in scored)
    winners = [p for s, p in scored if s == best]
    if len(winners) != 1:
        return None  # a tie is still ambiguous; refuse exactly as before
    out = dict(winners[0])
    out["source_matched_by"] = "locator"
    return out


def annotate(result: dict, ledger: list[dict] | None = None) -> dict:
    """Attach `source` to every sweep finding whose producing call can be named.

    In place, and never raises: this runs after both stages are billed, and no
    provenance annotation is worth losing a paid analysis over.

    Writes a `sourcing` summary into `run_meta` -- how many findings could be
    traced back to a passage. A coverage number that is computed and not
    recorded is a coverage number nobody notices is missing, which is exactly
    how the findings' own `quote` field went 505 calls without being checked.
    """
    findings = result.get("findings")
    rows = (findings or {}).get("findings") if isinstance(findings, dict) else None
    if not isinstance(rows, list):
        return result
    from_ledger = quotes_from_ledger(ledger)
    traced = 0
    joinable = 0
    for finding in rows:
        if not isinstance(finding, dict):
            continue
        # Strip anything quote-shaped the model may have written under this
        # key before deciding it here, for the same reason the ledger verdict
        # is stripped before adjudication.
        finding.pop("source", None)
        # `technique: manual` means the model read the value off the paper
        # itself. There IS no producing call, so counting it as an untraced
        # finding would report a design fact as a coverage failure -- and
        # inventing a call for it would be the worst laundering available
        # here, hand-read text presented as tool-sourced. MEASURED on the
        # archived corpus: 92 of 377 findings (24%) are `manual`.
        if not _candidate_tools(finding.get("technique")):
            continue
        joinable += 1
        payload = _source_for(finding, from_ledger)
        if payload:
            finding["source"] = dict(payload)
            traced += 1
    meta = result.setdefault("run_meta", {})
    if isinstance(meta, dict):
        meta["sourcing"] = {"findings": len(rows),
                            "joinable": joinable,
                            "traced_to_a_passage": traced}
    return result


def annotate_v2(doc: dict, ledger: list[dict] | None = None) -> dict:
    """Attach `source` to every v2 finding whose producing call can be named.

    In place, never raises, and returns the summary for `run_meta.sourcing` --
    the v2 sibling of `annotate`.

    PORTED 2026-09-04, and it was a CONTRACT WITH NO PRODUCER rather than an
    open question. `source` is declared in `findings.v2.schema.json` ("Set by
    the pipeline, not the model", five subfields) AND listed in
    `prompts._NOT_PRODUCER_WRITTEN`, so the design already said the pipeline
    writes it -- and nothing on the parallel path did. Measured before this
    landed: 0 of 80 findings across the four archived parallel runs carried
    it, against every legacy run that did. That is the `sandbox_audit.json`
    case again, and the legacy deletion would have taken the capability
    silently, because `annotate` lives in `write_review_outputs`.

    ONE ADAPTATION FROM V1, AND IT IS THE ONLY ONE THAT EARNED ITS PLACE:
    `_has_real_tool` rather than `_candidate_tools` truthiness. v2 techniques
    include `not_computational`, `internal_contradiction` and `factual_claim`
    -- findings with no producing call BY DEFINITION -- and `_candidate_tools`
    falls back to the technique's own name for an unknown technique, so the v1
    test files those as joinable and then as untraced, reporting a design fact
    as a coverage failure. Measured: 14 / 4 / 5 / 8 findings per archived run
    land in `manual` this way.

    WHAT I BUILT AND THEN DELETED, so it is not re-attempted. v2 findings carry
    no `inputs`, so `_source_for`'s scalar route cannot fire and the whole
    technique family becomes candidates -- which looks like exactly when the
    unanimity rule should refuse. So a first cut narrowed the pool to
    `tool_verdict.tool`, the call `findings_v2.tool_verdict_for` had already
    joined. MEASURED ACROSS ALL FOUR ARCHIVED RUNS IT CHANGED NOTHING: not one
    additional join (18/10/2/2 either way) and not one differing quote.
    `_source_for`'s empty-`wanted` branch already does the right thing here --
    it takes every call of the family and lets unanimity on the QUOTE decide,
    and the family is in practice the joined tool. Shipping the narrowing
    would have been inert machinery carrying a plausible story, which is the
    defect class `LESSONS.md` names as "code built and never consumed".
    """
    from .severity_reconcile import _has_real_tool

    summary = {"findings": 0, "joinable": 0, "traced_to_a_passage": 0,
               "manual": 0, "quotes_available": 0}
    rows = doc.get("findings") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return summary
    from_ledger = quotes_from_ledger(ledger)
    summary["quotes_available"] = len(from_ledger)
    summary["findings"] = len(rows)
    for finding in rows:
        if not isinstance(finding, dict):
            continue
        # Stripped before it is decided here, for the reason the ledger verdict
        # is stripped before adjudication: the party being checked does not get
        # to certify itself.
        finding.pop("source", None)
        if not _has_real_tool(finding.get("technique")):
            summary["manual"] += 1
            continue
        summary["joinable"] += 1
        payload = _source_for(finding, from_ledger)
        if payload:
            finding["source"] = dict(payload)
            summary["traced_to_a_passage"] += 1
    return summary
