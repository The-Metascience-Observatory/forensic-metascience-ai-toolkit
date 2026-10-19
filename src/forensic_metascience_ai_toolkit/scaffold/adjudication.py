"""BOUNDED ADJUDICATION FOR THE REFUSAL PREMISES -- wave 7e's prototype.

TWO PREMISES NOW, BEHIND TWO OPT-IN FLAGS AND NEITHER A DEFAULT: `averaging`
(wave 7e) and `estimator` (round 17). They share stage 1's machinery, stage 2's
call and the whole polarity argument below; what differs is the UNIT relevance is
measured against, which is the only thing `_estimator_candidates` had to solve.

WHY THE SECOND ONE, MEASURED AT `ff4d5ae` AND NOT INFERRED. Four ordinary honest
phrasings of a survey-weighted mean -- "Each swimmer's card counts toward the
reported mean according to her stratum share on the register.", "The reported
averages give every stratum the share it holds on the roll.", "Table 1 gives the
means after the register margins were applied.", "Reported means take account of
the differing selection chances of the swimmers." -- each return GRIM, GRIMMER
AND SPRITE `impossible` on an honest paper AND offer the model ZERO candidates,
so `--read-premises` cannot rescue any of them either. Three of round 10's own
eight pinned statements (`reweighted`, `raked`, `in proportion to`) already evade
`premise_reading._ESTIMATOR_CANDIDATE` and survive only because the JUDGE happens
to carry them; the next phrasing moves both to zero, as those four already do.
That is the averaging premise's D1 shape, reproduced on the estimator premise.

THE ONE MEASUREMENT THIS MODULE IS BUILT AROUND. Across rounds 4, 9, 10, 11, 13
and 14 every averaging defect that reached a false accusation was a RECALL
failure and not a JUDGEMENT failure: wherever a real paid reading actually got
shown the sentence, it answered correctly (round 14's D2, `establishes: True`,
$0.26, three accusations removed). Wherever it did not -- a verb outside the
closed vocabulary, a fact split across two sentences, a statement in a footnote
-- the model was never OFFERED the passage, so no amount of judging could have
rescued it. `premises.AVERAGED` and `premise_reading._AVERAGING_CANDIDATE` are
both closed word lists standing in for a judgement, and a list is the defect.

SO THE TWO STAGES HAVE DIFFERENT JOBS AND DIFFERENT FAILURE DIRECTIONS:

  1. RELEVANCE (`relevant_passages`) -- free, regex-free, recall-only. Is this
     passage plausibly ABOUT how this variable's reported value was arrived at?
     It asks nothing about averaging. A false positive here costs ONE LINE of a
     prompt; a false negative here is the exact failure mode every round above
     traces to. So it is generous by construction: aboutness (`anchor_score`,
     `_attribution`) or anaphoric resolution (`_antecedent_ids`), and nothing
     else.
  2. ADJUDICATION (`adjudicate`) -- a model call, ALWAYS made for whatever
     stage 1 surfaced. The same establish/withdraw question
     `premise_reading.QUESTIONS["averaging"]` already asks, invoked
     automatically for the narrowed set rather than gated behind
     `--read-premises`.

THE PASSAGE IS A WINDOW, NOT A SENTENCE, and that is what closes the split-
sentence and footnote channels. Round 4's F2/F3 and round 13's F9 all split one
fact across two sentences, so no single sentence establishes the premise and
each is judged `false` in isolation even when it IS offered. A relevant sentence
is therefore emitted together with its immediate neighbours inside the same
section (`_SECTION` floor, `Haystack.section_start`), which is how a person
reads a Methods paragraph. Widening what a REFUSAL may be judged on is safe by
construction -- see the polarity argument below -- and it is the only reason
this can be done at all.

THE POLARITY IS THE WHOLE SAFETY ARGUMENT, and it is unchanged from
`premise_reading`'s own. Both premises are in `premise_reading.REFUSAL_PREMISES`:
a verdict on either moves a premise in ONE direction only (`index` applies a
refusal only on `establishes: True`), so the worst a wrong `true` can do is
REMOVE a check from an honest paper, and a wrong `false` leaves the vocabulary's
own judgement exactly where it stood. Nothing here can manufacture an accusation.
`candidates_for` CHECKS that membership rather than trusting this paragraph,
because a composer that takes a premise name by argument is exactly where a
licence could be given to a model by accident.

AND THE VOCABULARY IS THE FLOOR, WHICH IS THE OTHER HALF. Every net below starts
from the values and variables the free path's own judges have ALREADY refused,
and skips them -- so a run that never makes the paid call keeps every refusal it
ever made, and a call that truncates loses coverage rather than protection. The
regexes stay load-bearing; deleting them because "the model does that now" would
re-accuse honest weighted means on every run without the pass.

WHAT THIS DELIBERATELY DOES NOT TOUCH, per D71 and the wave 7e spec:
  * the ALTERNATIVE-BASE CEILING, whose dangerous polarity is a model `false`
    removing a candidate denominator. It is not referenced anywhere in this
    module and a test asserts that by grepping the source.
  * every LICENCE premise (`bound`, `step`) -- a licence being generous is the
    dangerous direction, and this module never widens who is BELIEVED on it;
  * the remaining refusal premise, whose statement is about how many subjects
    were analysed rather than about how a number was computed, and which keeps
    its own vocabulary path untouched. Its passages DO reach the estimator
    question, because table furniture is admitted with no aboutness test -- so
    round 17 MEASURED whether the question answers `false` for them rather than
    guarding it here, because this module may not name that premise at all. It
    does.

AND IT IS NOT THE DEFAULT. `premise_reading.candidates` is unchanged, so an
ordinary run -- with or without `--read-premises` -- behaves exactly as it did.
This path runs only when a caller asks for it (`adjudicate`, or the
`--adjudicate` flag), which is what makes the prototype measurable against the
old one rather than a replacement for it.

NO NUMBER EVER LEAVES THIS PATH. A candidate carries a passage and a target and
comes back a boolean and a reason. Estimator statements routinely name an
external population with a count ("weighted to the guild roll of 240 members"),
and reading that number is the ceiling's job -- which is the one thing a model
may not do here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from . import premise_reading as _reading
from . import premises as _premises

#: The relevance instrument each premise's measurements are a claim about, BY
#: PREMISE, because the two nets are different experiments and a reader of
#: `premise_reading.json` has to be able to tell which one produced a row. Bump an
#: entry with a new measurement, never with a rewording -- the same rule
#: `premise_reading.PROMPT_VERSION` carries, and for the same reason: a candidate
#: set built by different bytes is a different experiment.
RELEVANCE_VERSIONS: dict[str, str] = {
    "averaging": "averaging-relevance-window/2026-09-11",
    "estimator": "estimator-relevance-window/2026-09-12",
}

#: The averaging entry under its old name. Kept because round 15 pins it, and
#: because the averaging prototype's measurement is a claim about this string.
RELEVANCE_VERSION = RELEVANCE_VERSIONS["averaging"]

#: EVERY SENTENCE OF THE DOCUMENT. `Haystack.sentences_matching` is the repo's
#: one sentence enumerator and it takes a pattern, so the enumeration asks for a
#: word character -- which every sentence has and no sentence lacks. Using the
#: haystack's own walker rather than a second splitter is the point: two readers
#: that disagree about where a sentence ends are the drift this repo keeps
#: paying for.
_ANY_SENTENCE = re.compile(r"\w")

#: How many sentences either side of a relevant one go into its window. ONE,
#: and the number is a floor rather than a guess: round 4's F2/F3 and round 13's
#: F9 each split ONE fact across TWO ADJACENT sentences, which is how English
#: writes a definition after the thing it defines. A wider window costs prompt
#: length and can only ever add a refusal, so it is the cheap direction -- but
#: it is not free of a real cost either, and that cost is named in
#: `relevant_passages`: a neighbour about a DIFFERENT variable can persuade a
#: model to withdraw a step this variable is entitled to, which removes a check.
_WINDOW = 1


def _window(hay: _premises.Haystack, sents: list[tuple[int, str]], i: int) -> str:
    """Sentence `i` together with its neighbours inside the same section.

    THE SECTION IS THE BOUNDARY, not a character count -- the same rule
    `premises._antecedent_ids` was given by this wave's own section-boundary
    fix. A Methods sentence and the Results sentence that happens to follow it
    are not one passage, and joining them would offer a model a paragraph the
    paper never wrote.
    """
    floor = hay.section_start(sents[i][0])
    lo = i
    while lo > 0 and i - lo < _WINDOW and sents[lo - 1][0] >= floor:
        lo -= 1
    hi = i
    while hi + 1 < len(sents) and hi - i < _WINDOW \
            and hay.section_start(sents[hi + 1][0]) == floor:
        hi += 1
    return " ".join(s for _, s in sents[lo:hi + 1])


def _is_about(var: dict, sentence: str, others: list[dict], hay: _premises.Haystack,
              offset: int, declared: list[dict]) -> bool:
    """Stage 1's whole judgement: is this sentence about THIS variable?

    TWO WAYS, UNIONED, AND NEITHER MENTIONS AVERAGING. A sentence that names the
    variable (`_attribution` -- which resolves a TIE in this variable's favour,
    because for a refusal an ambiguity must fail OPEN), or a sentence whose
    discourse antecedent is this one (`_antecedent_ids`, the machinery built for
    exactly the anaphoric averaging sentence). Both are borrowed rather than
    reimplemented: a third copy of "is this sentence about this variable" is the
    drift this module exists to stop repeating.

    ATTRIBUTION MAY ONLY ADD A SENTENCE HERE, NEVER SUBTRACT ONE, and that is
    the correction round 16's D2 forced. The second way used to be gated on the
    sentence naming NO declared variable, and the FREE PATH's fallback was gated
    the same way -- so `Movements overhauled per workshop were logged in the
    daybook alongside the two cards, which were averaged.` was invisible to
    BOTH nets at once, and the prototype's stated safety story ("the two stages
    have different failure directions") was false for that shape: it was one
    rule failing twice. The free path keeps a gate, narrowed to the CLAUSE
    carrying the statement (`premises.is_anaphoric_averaging`), because there a
    wrong attribution removes a check with no judge to catch it. Stage 1 keeps
    none, because a wrong candidate here costs ONE LINE OF A PROMPT and the
    model is the judge -- a name-attribution test used to SUBTRACT is a filter,
    which is the one thing a recall-only stage may not contain.

    MEASURED COST (2026-09-12), on a 20-sentence body with 6 declared variables:
    67 candidates before, 93 after -- +39%, bounded above by
    `premise_reading.MAX_REFUSAL_CANDIDATES` per variable, which `_stratified`
    now spends without letting one crowded stratum empty another.

    AND THE ANTECEDENT REACH IS SPENT ON EVIDENCE HERE, `count_naming=True`,
    which the free path does not do. Same argument, one level down: a reach
    ordered by POSITION is a filter for a refusal, and a paper that writes six
    procedural sentences between `## Methods` and `## Statistical analysis` put
    its own antecedent out of range of a model that answers the question
    correctly when shown it. See `premises._ANAPHORA_REACH` for why the free
    path keeps the narrower rule.
    """
    if _premises._attribution(var, sentence, others) == "this":
        return True
    return str(var.get("id")) in _premises._antecedent_ids(
        hay, offset, declared, count_naming=True)


def already_refused(var: dict, hay: _premises.Haystack, others: list[dict],
                    passages: "list[str] | tuple[str, ...]" = ()) -> bool:
    """Has the free path ALREADY withdrawn this variable's step?

    ASKED FIRST, AND IT IS NOT AN OPTIMISATION. A refusal premise can only ever
    be ADDED, so a variable the vocabulary has already vetoed cannot be moved by
    any verdict: asking about it buys nothing and costs a paid line. It is the
    same early-out `premise_reading._averaging_candidates` and
    `_estimator_candidates` both make, and it is what keeps the paid cost of
    this path at zero on every paper the vocabulary already handles.
    """
    gran = _premises.field_dict(var, "granularity")
    if gran.get("per_subject_step") != 1:
        return True
    if _premises.averaging_statements(var, hay, others, passages):
        return True
    return bool(_premises.derivation_reports_an_average(var))


def relevant_passages(var: dict, hay: _premises.Haystack, others: list[dict],
                      passages: "list[str] | tuple[str, ...]" = (),
                      premise: str = "averaging",
                      rank: "Callable[[str], int] | None" = None,
                      ) -> list[tuple[int, str, str]]:
    """STAGE 1. `(rank, passage, source)` for every passage plausibly about how
    this variable's reported value was arrived at.

    NO AVERAGING VOCABULARY IS CONSULTED, and that absence is the design. The
    old net asked "does this sentence contain a combination word AND is it about
    this variable"; six of round 14's evasions and four of round 10's defeated
    the first half with an ordinary English verb the list did not carry
    (`blends`, `midpoint`, `halved`, `the pair`). This asks only the second
    half, and hands the first to the model, which is the reader that can
    actually answer it.

    THE RANK IS EVIDENCE, NOT POSITION, exactly as
    `premise_reading.MAX_REFUSAL_CANDIDATES` requires: a cap ordered by position
    is a FILTER for a refusal, so the passages carrying the narrow shape a
    judgement would use sort first and a paper with more relevant sentences than
    the cap loses its weakest candidates rather than its last ones.

    WHAT IT COSTS WHEN IT IS WRONG, stated plainly because this is the
    prototype's own risk: a window whose NEIGHBOUR describes a different
    variable's averaging can persuade a model to withdraw a step THIS variable
    is entitled to. That removes a check from an honest paper. It cannot add an
    accusation to one -- `premise_reading.index` applies an averaging verdict
    only on `True`, and only ever as a veto -- which is the whole reason a
    recall net this generous is allowed to exist.

    `rank` IS THE ORDERING, AND A CALLER MAY BRING ITS OWN. The loop above it --
    enumerate, ask aboutness, widen to a window, dedupe, admit furniture without
    an aboutness test -- is the same for every refusal premise, and a fourth copy
    of it is the drift this module's docstring exists to stop. What differs per
    premise is only which passages carry the narrow shape a judgement would use,
    so that one function is a parameter. Default `None` means `_rank(quote,
    premise)` and the shipped nets are unchanged.
    """
    scored = rank if rank is not None else (lambda q: _rank(q, premise))
    declared = [var] + [o for o in others
                        if str(o.get("id")) != str(var.get("id"))]
    sents = hay.sentences_matching(_ANY_SENTENCE)
    found: list[tuple[int, int, str, str]] = []
    seen: set[str] = set()
    for i, (off, sent) in enumerate(sents):
        if not _is_about(var, sent, others, hay, off, declared):
            continue
        quote = _window(hay, sents, i)
        if quote in seen:
            continue
        seen.add(quote)
        found.append((scored(quote), len(found), quote, "served_text"))
    for passage in passages:
        quote = " ".join(str(passage or "").split())
        if not quote or quote in seen:
            continue
        seen.add(quote)
        # A CAPTION OR A FOOTNOTE IS ADMITTED WITHOUT AN ABOUTNESS TEST, the
        # same rule `premises.averaging_statements` applies to `passages`: it
        # governs its own table and has no sentence to be about, so there is
        # nothing for aboutness to be measured against.
        found.append((scored(quote), len(found), quote, "printed_context"))
    return [(rank, quote, source)
            for rank, _, quote, source in sorted(found, key=lambda r: (r[0], r[1]))]


#: THE STRICT AND LOOSE VOCABULARIES OF EACH PREMISE, FOR RANKING ONLY. These are
#: the same regexes the free path JUDGES with, borrowed here to ORDER a candidate
#: set and never to filter one -- `premise_reading.MAX_REFUSAL_CANDIDATES` states
#: the rule and round 11 measured what happens when it is broken (four ordinary
#: introduction sentences took every slot ahead of the Methods sentence that
#: withdraws the premise). A passage that matches nothing still reaches the model;
#: it reaches it last.
_STRICT = {
    "averaging": lambda q: bool(_premises.AVERAGED.search(q)),
    "estimator": lambda q: bool(_premises.NOT_A_SIMPLE_MEAN.search(q)
                                or _premises.WEIGHTED_PERCENTAGE.search(q)
                                or _premises._ESTIMATOR_STATEMENT.search(q)),
}
_LOOSE = {
    "averaging": lambda q: bool(_reading._AVERAGING_CANDIDATE.search(q)),
    "estimator": lambda q: bool(_reading._ESTIMATOR_CANDIDATE.search(q)),
}


def _rank(quote: str, premise: str = "averaging") -> int:
    """0 for a passage this premise's strict vocabulary would already read as
    establishing it, 1 for one the loose recall net would, 2 for everything else."""
    if _STRICT[premise](quote):
        return 0
    if _LOOSE[premise](quote):
        return 1
    return 2


def _stratified(rows: list, limit: int, rank_of=lambda r: r[0]) -> list:
    """At most `limit` of `rows`, taken ROUND-ROBIN ACROSS RANKS.

    THE CUT MAY NOT BE ORDERED BY THE INSTRUMENT WHOSE FAILURE THIS MODULE
    EXISTS TO FIX, and before this it was. `_rank` scores a passage 0 or 1 if
    one of the two averaging vocabularies can see it and 2 otherwise, so the
    sentences this module was built to rescue -- the ones NEITHER vocabulary can
    see -- are rank 2 BY CONSTRUCTION, sort last, and are the first thing a cap
    removes. MEASURED (2026-09-12): with 36 vocabulary-matching decoys the
    withdrawing sentence survives; with 38 the candidate set is 40 decoys, the
    withdrawal reaches no model, and a real batched call on that set returned
    zero `true` verdicts while the accusation stood.

    `MAX_REFUSAL_CANDIDATES`' own docstring already states the rule this
    restores -- "a cap ordered by POSITION is a filter after all" -- and a cap
    ordered by VOCABULARY is a filter by the same argument and a worse one,
    because it is ordered by exactly what is known to be blind.

    RANKING STILL ORDERS THE PROMPT: the strongest evidence is still read first,
    and when the whole set fits under the cap nothing changes at all. What
    changes is only who is cut when it does not fit -- every stratum now loses
    its weakest members before any stratum loses all of them.
    """
    by_rank: dict[int, list[int]] = {}
    for i, row in enumerate(rows):
        by_rank.setdefault(rank_of(row), []).append(i)
    keep: set[int] = set()
    order = sorted(by_rank)
    while order and len(keep) < limit:
        for r in list(order):
            if len(keep) >= limit:
                break
            queue = by_rank[r]
            keep.add(queue.pop(0))
            if not queue:
                order.remove(r)
    return [row for i, row in enumerate(rows) if i in keep]


def _rows_for(quote: str) -> list[dict]:
    """One passage as the candidate row(s) that carry ALL of it.

    A REFUSAL CANDIDATE IS NEVER DROPPED AND ITS CONTENTS ARE NEVER DROPPED
    EITHER -- see `premise_reading._segments` for the measurement that separates
    those two sentences. A passage inside `MAX_QUOTE_CHARS` is one row, exactly
    as before; a longer one becomes consecutive rows, each a word-boundary span
    of the document, each stamped with which piece of how many it is, and the
    remainder that did not fit in `MAX_QUOTE_SEGMENTS` pieces is stamped as a
    character count rather than being taken away in silence.
    """
    pieces, dropped = _reading._segments(quote)
    return [{"quote": piece,
             "quote_segment": [i, len(pieces)] if len(pieces) > 1 else None,
             "quote_chars_not_carried": dropped if i == len(pieces) else 0}
            for i, piece in enumerate(pieces, 1)]


def _averaging_candidates(account: dict, text: str = "") -> list[dict]:
    """STAGE 1 FOR `averaging`: one row per passage plausibly about how each
    variable's reported value was arrived at.

    THE SHAPE IS `premise_reading`'s ON PURPOSE. A candidate written here is read
    by `premise_reading.build_prompt`, `read`, and `index` with no change to any
    of them, so the artifact on disk is the same `premise_reading.json` any
    other run writes and `premises.stamp` consumes it through the same door.
    This is a different RECALL NET, not a different pipeline.
    """
    hay = _premises.Haystack(text)
    variables = _premises.readable_variables(account)
    by_var_id = _premises.variables_by_id(variables)
    values = [v for v in (account.get("values") or [])
              if _premises.well_formed(v) is None]
    captions = _premises._captions(account)
    by_variable: dict[Any, list[dict]] = {}
    for v in values:
        by_variable.setdefault(v.get("variable_id"), []).append(v)
    out: list[dict] = []
    for var in variables:
        if var.get("id") not in by_var_id:
            continue
        mine = by_variable.get(var.get("id")) or []
        passages = _premises.table_passages(account, mine)
        if already_refused(var, hay, variables, passages):
            continue
        ctx = _reading._printed_context(mine, captions)
        target = _reading._variable_target(var)
        found = relevant_passages(var, hay, variables, passages)
        kept = _stratified(found, _reading.MAX_REFUSAL_CANDIDATES)
        for rank, quote, source in kept:
            for row in _rows_for(quote):
                row.update({"premise": "averaging", "variable_id": var.get("id"),
                            "source": source, "target": target, "context": ctx,
                            "passages_considered": len(found),
                            "passages_cut": len(found) - len(kept),
                            "relevance_version": RELEVANCE_VERSIONS["averaging"]})
                out.append(row)
    return out


def _governing_windows(hay: _premises.Haystack,
                       sents: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    """`(rank, order, window)` for every passage ABOUT WHAT THE PAPER REPORTS.

    THE ONE CLOSED LIST LEFT IN THIS PREMISE'S RECALL NET, AND THE CLAIM MADE FOR
    IT IS NARROWER THAN "NO VOCABULARY". `premise_reading._GOVERNS_REPORTED`
    enumerates NAMES FOR A REPORTED STATISTIC -- mean, average, estimate,
    percentage, prevalence, proportion, rate, figure, value -- which is a set the
    account's own `statistic` field already closes. It does NOT enumerate WAYS OF
    DESCRIBING AN ESTIMATOR, which is the unbounded set three waves have failed to
    enumerate and the reason this module exists: `reweighted`, `raked` and `in
    proportion to` all evade `_ESTIMATOR_CANDIDATE` today and all match this.

    MEASURED on the four ordinary phrasings that produce three `impossible`
    verdicts and ZERO candidates at `ff4d5ae`: 4 of 4 match this, 0 of 4 match
    either estimator vocabulary. And on four real corpus bodies it costs 14 to 61
    windows a paper against 2 to 12 today, which is one batched call.
    """
    out: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for i, (_, sent) in enumerate(sents):
        if not _reading._GOVERNS_REPORTED.search(sent):
            continue
        quote = _window(hay, sents, i)
        if quote in seen:
            continue
        seen.add(quote)
        out.append((_rank(quote, "estimator"), len(out), quote))
    return out


def _estimator_candidates(account: dict, text: str = "") -> list[dict]:
    """STAGE 1 FOR `estimator`: one row per passage plausibly about how a set of
    the paper's REPORTED NUMBERS was arrived at.

    THE UNIT IS WHAT MOVES, AND IT IS WHY THIS IS NOT A COPY OF THE AVERAGING
    NET. `averaging` is keyed to a VARIABLE (`index` files its verdict by
    variable id, because a per-subject step is a property of the variable);
    `estimator` is keyed to a SET OF VALUES. So relevance asks the same question
    -- is this passage about how these reported numbers were arrived at? -- of
    three different scopes, none of which consults an estimator word list:

      A. THE VARIABLE. `_is_about` verbatim, the same union of attribution and
         anaphoric resolution the averaging net uses, over the variable's own
         surviving mean or percentage values. Narrowest blast radius.
      B. WHAT THE PAPER REPORTS. `_governing_windows`, scoped to every surviving
         value of one statistic kind. This is the channel that carries the
         document-level statement, which is where a paper actually says this.
      C. TABLE FURNITURE, admitted with NO aboutness test -- the column band, the
         caption and the table's footnotes, grouped exactly as the free path
         groups them and with its `_ESTIMATOR_CANDIDATE` gate removed. Same rule
         `relevant_passages` applies to `passages`: furniture governs its own
         table and has no sentence to be about.

    AND EVERY A/B PASSAGE IS A WINDOW, NOT A SENTENCE, which is what closes the
    split-statement channel: "Weights were formed from the register's age and sex
    margins." followed by "Each swimmer's card counts in proportion to hers."
    establishes the premise as a pair and neither half establishes it alone.

    WHO SURVIVES IS THE VOCABULARY'S DECISION AND IS NOT WIDENED HERE. The two
    judges (`premises.estimated_mean_reason`, `premises.weighted_percentage_reason`)
    run inside `premise_reading._estimator_groups` before anything below, so a
    value a rule has already refused is absent from every scope and no verdict can
    reach it. That is what makes the vocabulary the FLOOR: a run without the paid
    pass keeps every refusal it ever made, and this path can only add.

    THE SCOPE IS NAMED IN THE TARGET, and it has to be. A channel-B `true`
    withdraws a check from EVERY mean in the paper, which is the largest single
    lever in the premise layer -- inherited rather than new (a single
    `premises.estimator_statement` regex match does exactly that today), but a
    model answering it should be told how much it is moving.
    """
    hay = _premises.Haystack(text)
    variables = _premises.readable_variables(account)
    values = [v for v in (account.get("values") or [])
              if _premises.well_formed(v) is None]
    captions = _premises._captions(account)
    furniture = _premises.table_footnotes(account)
    rows, survivors = _reading._estimator_groups(
        values, captions, _premises.estimator_statement(text),
        _premises.weighting_statement(text), furniture, gate=False)
    by_id = {str(v.get("id")): v for v in values}
    sents = hay.sentences_matching(_ANY_SENTENCE)
    # `(scope, channel, rank, order, row)`. The scope is what the cap counts,
    # because a cap applied to the whole set would let one crowded table silently
    # cut the paper-level statement -- which is the filter-not-a-cap failure.
    pool: list[tuple[tuple, int, int, int, dict]] = []

    # C -- TABLE FURNITURE, no aboutness test.
    for i, rec in enumerate(rows):
        pool.append((("furniture", rec["kind"]), 0,
                     _rank(rec["quote"], "estimator"), i, dict(rec)))

    # A -- ONE VARIABLE'S OWN REPORTED NUMBERS.
    for var in variables:
        vid = str(var.get("id"))
        found = None
        for kind in ("mean", "percentage"):
            ids = [str(x) for x in survivors[kind]
                   if str((by_id.get(str(x)) or {}).get("variable_id")) == vid]
            if not ids:
                continue
            if found is None:
                found = relevant_passages(var, hay, variables, premise="estimator")
            ctx = _reading._printed_context([by_id[i] for i in ids], captions)
            for order, (rank, quote, source) in enumerate(found):
                pool.append((("variable", vid, kind), 1, rank, order, {
                    "premise": "estimator", "variable_id": var.get("id"),
                    "value_ids": list(ids), "source": source,
                    "quote": quote, "band": "", "caption": "",
                    "kind": kind, "context": ctx,
                    "target": (f"the {len(ids)} {kind} value(s) this paper reports for "
                               + _reading._variable_target(var))}))

    # B -- WHAT THE PAPER REPORTS, paper-wide.
    windows = _governing_windows(hay, sents)
    for kind in ("mean", "percentage"):
        ids = [str(x) for x in survivors[kind]]
        if not ids:
            continue
        for rank, order, quote in windows:
            pool.append((("paper", kind), 2, rank, order, {
                "premise": "estimator", "variable_id": None,
                "value_ids": list(ids), "source": "served_text",
                "quote": quote, "band": "", "caption": "",
                "kind": kind, "context": "",
                "target": f"the {len(ids)} {kind} value(s) this paper reports"}))

    out: list[dict] = []
    # THE SAME FOOTNOTE IS CARRIED BY SEVERAL TABLES AND ONE WINDOW IS REACHED
    # FROM TWO ANCHORS, so without this the model is asked one question five
    # times. Deduplication is on `(passage, target)` and not on the passage
    # alone: the same sentence asked about the paper's means and about its
    # percentages is two different questions with two possible answers.
    said: set[tuple[str, str]] = set()
    by_scope: dict[tuple, list[tuple[int, int, dict]]] = {}
    for i, (scope, channel, rank, order, row) in enumerate(sorted(
            pool, key=lambda r: (r[1], r[0], r[2], r[3]))):
        key = (row["quote"], row["target"])
        if key in said:
            continue
        said.add(key)
        by_scope.setdefault(scope, []).append((rank, i, row))
    # AND THE PER-SCOPE CAP IS SPENT ACROSS RANKS, not down them. See
    # `_stratified`: within one scope the cut was ordered by the same two
    # estimator vocabularies whose blindness is the reason this net exists.
    picked: list[tuple[int, int, dict]] = []
    for rows_of_scope in by_scope.values():
        picked += _stratified(rows_of_scope, _reading.MAX_REFUSAL_CANDIDATES)
    for _, _, row in sorted(picked, key=lambda r: r[1]):
        for piece in _rows_for(row["quote"]):
            out.append({**row, **piece,
                        "relevance_version": RELEVANCE_VERSIONS["estimator"]})
    return out


#: The relevance net of each premise this module can adjudicate. A premise
#: absent from here has none, which is a refusal rather than a fallback: silently
#: adjudicating a premise on the wrong net is how a measurement stops being one.
_NETS = {"averaging": _averaging_candidates, "estimator": _estimator_candidates}

#: The premises `candidates` and `adjudicate` ask about when a caller names none.
#: `averaging` alone, which is what the averaging prototype shipped and what
#: round 15 pins; adding a premise to the DEFAULT would change what an existing
#: flag does, which is the one thing an opt-in prototype may not do.
DEFAULT_PREMISES: tuple[str, ...] = ("averaging",)


def _finish(out: list[dict], hay: _premises.Haystack) -> list[dict]:
    """The shape every candidate carries, whichever net wrote it."""
    for i, c in enumerate(out, 1):
        c["id"] = f"cand:{i}"
        c["question"] = _reading.QUESTIONS[c["premise"]]
        c.setdefault("variable_id", None)
        c.setdefault("value_ids", [])
        c.setdefault("asked_bounds", None)
        loc = hay.locate(c["quote"])
        c["quote_located"] = bool(loc["located"])
        c["quote_not_located_because"] = loc["why"]
        # ALWAYS ASKABLE. Both premises here are refusals, and `premise_reading`'s
        # own rule is that a passage which does not locate is dropped only where a
        # verdict could GRANT something. A window spanning two sentences is
        # exactly the passage that will not locate as one span, and a column band
        # is not in the served body at all -- refusing to ask about either would
        # reintroduce the recall gap this module removes.
        c["askable"] = True
    return out


def candidates(account: dict, text: str = "") -> list[dict]:
    """STAGE 1, for the whole paper, for `DEFAULT_PREMISES`."""
    return candidates_for(account, text)


def candidates_for(account: dict, text: str = "",
                   premises: "tuple[str, ...] | list[str]" = DEFAULT_PREMISES,
                   ) -> list[dict]:
    """STAGE 1 for the named premises, in a deterministic order.

    EVERY PREMISE HERE IS A REFUSAL AND THAT IS CHECKED, not assumed. A licence
    premise being generous is the direction this project has never let a model
    control, and a composer that takes a premise name by argument is exactly
    where that could be given away by accident.
    """
    names = tuple(premises)
    for p in names:
        if p not in _NETS:
            raise ValueError(f"no relevance net for premise {p!r}; "
                             f"have {sorted(_NETS)}")
        if p not in _reading.REFUSAL_PREMISES:
            raise ValueError(f"{p!r} is not a refusal premise; this module may only "
                             "widen what a model is shown about a premise whose "
                             "verdict can remove a check and never add an accusation")
    out: list[dict] = []
    for p in names:
        out += _NETS[p](account, text)
    return _finish(out, _premises.Haystack(text))


def adjudicate(account: dict, text: str, out_dir: str | Path, *,
               model: str = _reading.DEFAULT_MODEL, timeout_s: int = 900,
               premises: "tuple[str, ...] | list[str]" = DEFAULT_PREMISES,
               budget: int | None = _reading.MAX_CANDIDATES_PER_PAPER) -> dict:
    """STAGE 2. Ask the model each named premise's question of every passage
    stage 1 found relevant, and return the `premise_reading` record.

    PAID. One batched call per `premise_reading.MAX_PER_CALL` candidates, reusing
    a reply already bought for the identical prompt -- `premise_reading.read`
    does all of it, and is handed this module's candidate list through its own
    `only=` door. Nothing about the call, the prompt, the schema or the
    verdict-addressing differs from the pass E1 measured; only the candidate set
    does.

    AND `budget` IS WHERE THIS NET'S BILL IS BOUNDED, because this is the net
    that needs it most: `_estimator_candidates` spends `MAX_REFUSAL_CANDIDATES`
    once per `(variable, kind)` scope and the paper sets how many scopes there
    are, so its candidate count is linear in the variable count with no ceiling
    of its own -- measured at ~97 candidates a variable on real corpus text.
    `premise_reading.MAX_CANDIDATES_PER_PAPER` carries the figures and the
    argument for the default.

    ATTACH IT BY SETTING `account["premise_reading"]` to the returned record --
    `premises.stamp` reads that key, and `premise_reading.index` keys an
    `averaging` verdict by variable id (where `granularity_verification` looks
    for one) and an `estimator` verdict by value id (where `value_premise`
    looks).
    """
    return _reading.read(account, text, out_dir, model=model, timeout_s=timeout_s,
                         budget=budget,
                         only=candidates_for(account, text, premises))
