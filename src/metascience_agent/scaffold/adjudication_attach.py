"""THE WITHDRAWAL-ONLY LICENCE VETO -- round 24's prototype, widened in round 28.

ROUND 28 IN FOUR LINES, BECAUSE IT CHANGES WHAT THIS MODULE IS FOR. Round 24
asked the ATTACHMENT sub-question alone (whose quantity do these words
describe?); rounds 25, 26 and 27 then built two more REGEX guards for the two
sub-questions it does not reach -- polarity (does the passage deny it?) and unit
of observation (whole-numbered per what?). Round 28 measured all three head to
head and they are ONE question: `QUESTIONS[PREMISE]` now asks whether the passage
shows the reported per-subject figure to be a whole number, and on 148 probes
across three fixture families it closes every accusation channel the three
vocabularies close and the 53 they leave open, for one honest licence lost out of
38. The WITHDRAWING ANSWER IS NOW `false` -- see `premise_reading.WITHDRAWN_ON_FALSE`
for the four inverted paid runs that measured why it had to be. Everything below
about POLARITY, CANDIDATES and the GREP RAIL is unchanged and still governs.

WHAT THE PREMISE IS. `premises.granularity_verification` grants a per-subject
step of 1 when a located sentence of the paper states discreteness and this
reader can attribute that statement to the variable under test. GRIM, GRIMMER and
SPRITE all rest on that step. The attribution is decided by a rule over clause
and constituent boundaries (`_discreteness_licence`,
`_discreteness_is_attributable`), and that rule is what three consecutive rounds
have been unable to make right.

WHY THIS IS NOT A FOURTH BOUNDARY RULE, and the argument is round 23's rather
than mine. Round 21 closed coordinators and parentheses; round 22 (`77ec0346`)
made an unresolvable boundary fail closed and closed twenty subordinator, adjunct
and participial phrasings; an independent verifier then found NINETEEN MORE that
survive, every one of them GRIM and SPRITE `impossible` on a card the paper
itself says is graded TO THE NEAREST HALF POINT, with `reasons: []`. Its verdict
-- "closed the INSTANCES, not the CLASS" -- is supported by round 23's own
measurement: eight must-refuse and four must-grant sentences occupy ONE cell of
every feature that function can compute, so no threshold over those features
separates them (`test_scaffold_checks_round23.TestTheFeatureCellIsShared`).

What the rule is attempting is SYNTACTIC ATTACHMENT RESOLUTION. `Rescue
technique was graded to the nearest half point, together with a count of damaged
floats` -- who is counted in whole units? A comma heuristic does not answer that
and a twenty-first one will not either.

AND THE COST SIDE MOVED THE WRONG WAY AT THE SAME TIME. A second, independent
audit put `77ec0346` at **6 of 18 honest variables refused** on ordinary academic
methods prose. The reassuring "zero cost across the pinned fixtures" figure is an
artifact and must not be quoted: `discreteness_boundary: unresolved` occurs 0
times across all 979 pinned inputs, so not one fixture in the repo contains the
shape that rule refuses -- this repo's own
[[a-fixture-that-excludes-the-defect-region]], measured where the defect cannot
occur. So the instrument is failing on BOTH axes at once, which is what says the
next move is structural.

# THE POLARITY ARGUMENT, WHICH IS THE WHOLE OF WHY THIS MAY EXIST

D71 says a model must never LOOSEN a licence, and it is right: a model wrongly
granting a step of 1 manufactures `impossible` on honest data, which is the
cardinal failure this project exists to avoid. THIS IS THE OPPOSITE DIRECTION.

    THE REGEX GRANTS, EXACTLY AS IT DOES TODAY. A MODEL MAY ONLY WITHDRAW.

The model is asked ONE question -- does this passage show that the figure the
paper reports for one subject is a whole number? -- and an answer of "it does
not" takes the licence away. It cannot grant anything and it cannot restore
anything:

  * `discreteness_attachment` is in `premise_reading.REFUSAL_PREMISES`, so
    `premise_reading.index` files a verdict ONLY on its WITHDRAWING answer (the
    branch is `elif rec["withdraws"]:`, and `withdraws` is computed by
    `premise_reading.withdraws`, which for THIS premise is `false`). The keeping
    answer is recorded and moves nothing.
  * AND THE KEEPING ANSWER IS HARMLESS BECAUSE OF `eligible`, which is why the
    direction change did not cost the safety argument: the question is only ever
    put about a variable whose step the free path has ALREADY licensed, so a
    model saying "yes, the passage shows it" agrees with a licence that already
    stood. There is no state in which it hands one out.
  * `granularity_verification` ANDs the verdict into `establishes` and uses it in
    no other expression, so it can only turn a True into a False.
  * the KIND licence is not reachable from here at all, and `eligible` does not
    even ASK about a variable whose kind settles the step.

So a model error costs a CHECK, which is the refusal polarity this architecture
is built around; a model success closes the whole attachment class with no
attachment regex; and the coverage/safety tradeoff dissolves, because a generous
regex is no longer an unsafe regex.

AND A STALE VERDICT IS SAFE FOR THE SAME REASON, which is why there is no
equivalent of `premise_reading._asks_the_declared_premise` here. A reading is a
file on disk that outlives the account it was taken against; a `bound` verdict
therefore has to prove it answered about the range the account NOW declares,
because it could grant one. This one cannot grant anything, so a verdict taken
against a granularity sentence the account has since changed costs a check and
buys nothing. `averaging` is unguarded for the same reason.

THE GREP RAIL IS THE ENFORCEMENT, NOT THIS PARAGRAPH.
`test_scaffold_checks_round24` reads this file's source and asserts that it names
neither of the two licence premises and none of the ceiling's readers, the same
way `test_scaffold_checks_round15` pins D71 on `adjudication.py` -- because a
module that composes questions for a model is exactly where a licence could be
handed to one by accident.

# STAGE 1: THE PASSAGE THE LICENCE ACTUALLY RESTS ON

`adjudication`'s machinery is reused rather than copied -- `_ANY_SENTENCE` for
the enumeration, `_window` for the passage, `_rows_for` for segmentation,
`_finish` for the row shape, `premise_reading.read`'s own `only=` door for the
call, so the artifact on disk is the `premise_reading.json` every other run
writes and `premises.stamp` consumes it through the same door. This is a
different QUESTION, not a different pipeline.

ONE THING DIVERGES AND IT IS DELIBERATE: `relevant_passages`' full candidate set
is NOT used. That net is generous by construction and generosity is protective
for `averaging`, `estimator` and `varying_n`, where the model starts from nothing
and every passage it is shown is another chance to find a refusal the vocabulary
missed. Here the model starts from a licence that has ALREADY been granted, on
ONE identified passage, and every additional passage is an independent chance to
withdraw a licence that passage says nothing about -- the cost `relevant_passages`
names in its own docstring ("a window whose NEIGHBOUR describes a different
variable's averaging can persuade a model to withdraw a step THIS variable is
entitled to"), paid once per extra row. Recall is protective when a model may
only ADD a refusal FROM NOTHING; it is a liability when the model is subtracting
from something. So the candidate is the window around the sentence the free path
licensed -- one question per eligible variable, which is also what keeps the paid
cost near zero.

THE PASSAGE IS A WINDOW AND NOT A BARE SENTENCE, for `adjudication`'s reason: a
definition is often written in the sentence after the thing it defines, and an
anaphoric statement ("Each rating was a whole number.") names nothing at all.
Widening here is safe in the direction that matters, because the question asks
whether ANY of the passage's phrases shows the reported figure to be whole -- so
an extra neighbour can only make a withdrawal LESS likely, never more, and the
failure it buys is a leak left open rather than an honest licence destroyed.
ROUND 28 QUALIFIES THAT IN ONE PLACE AND IT IS WORTH NAMING: limb (b) is about
the TARGET, so a neighbouring sentence saying the target is graded in half points
is a reason to withdraw and not merely a missed reason to keep. The window is
still bounded by the section the paper itself started, and the one honest licence
lost in the round's measurement was not lost this way.

# WHAT IT MEASURED, AND THE ONE THING WORTH CARRYING OUT OF THE ROUND

Sonnet, 2026-09-12, 58 candidates over five arms in one interleaved batch set,
$0.401463: **20 of 20 accusation channels closed, 0 of 38 honest licences wrongly
withdrawn** -- including all ten that `77ec0346` and its predecessors already
refuse, which is what says the coverage half of the exit is available. The arms,
the denominators and the caveats are in `tests/test_scaffold_checks_round24`.

AND THE FIRST DRAFT OF THE QUESTION ALSO SCORED 58 OF 58 WHILE BEING WRONG. Run
through `adjudicate` on ONE paper with TWO candidates it returned two correct
REASONS with both booleans INVERTED: it was answering `PREAMBLE`'s question
("Answer true only if the sentence ... does establish the premise for the stated
target") about the premise that draft's own opening sentence had named for it,
and a big batch's worth of context had been hiding it completely. A BATCH SCORE
IS NOT A MEASUREMENT OF WHAT A RUN WILL DO. Exercise any new question in this set
end to end on one paper before believing its batch score.

AND ROUND 28 IS THAT RULE PAYING FOR ITSELF THREE MORE TIMES. Three wordings of
the WIDENED question, each exercised end to end on one two-candidate paper before
any batch was bought, each returning the correct reason with both booleans
inverted -- including one whose TRUE was a positive four-fact disjunction, and one
run with `PREAMBLE`'s polarity rule neutralised. The cause was neither the wording
nor the preamble: it was the name of the boolean. See
`premise_reading.WITHDRAWN_ON_FALSE`. Round 24's own string, run as a control on
the SAME paper, was not inverted, which is what attributed it to the widening.

# AND IT IS NOT THE DEFAULT

`premise_reading.candidates` is unchanged, `adjudication`'s two nets are
unchanged, `adjudication_n` is unchanged, and `checks` behaves on every existing
paper exactly as it did. This path runs only under `--adjudicate-attachment`.
Nothing in this module loosens the boundary rule `77ec0346` shipped: relaxing
that rule is the coverage half of the exit and a change to the FREE path, which
is a different decision with a different owner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import adjudication as _adj
from . import premise_reading as _reading
from . import premises as _premises

#: The relevance instrument this premise's measurements are a claim about. Bump
#: with a new measurement, never with a rewording -- `adjudication`'s own rule,
#: and for the same reason: a candidate set built by different bytes is a
#: different experiment.
#: ROUND 28 DID NOT MOVE IT, DELIBERATELY. It widened the QUESTION and changed no
#: byte of `eligible` or `candidates`, so the candidate set is the same
#: experiment and its own measurements still stand. What moved is
#: `premise_reading.PROMPT_VERSION`, which is where a reworded question belongs.
RELEVANCE_VERSION = "discreteness-attachment-licensing-window/2026-09-12"

#: The premise name, in one place, because it is the join between this module,
#: `premise_reading.QUESTIONS` and `premises.granularity_verification`.
PREMISE = "discreteness_attachment"


def _fold(raw: Any) -> str:
    """One passage with its whitespace collapsed, which is how `Haystack` hands
    every sentence out. Used only to ask whether one span contains another."""
    return " ".join(str(raw or "").split())


def licensing_record(var: dict, hay: _premises.Haystack, others: list[dict],
                     values: list[dict],
                     passages: "list[str] | tuple[str, ...]" = (),
                     subjects: "frozenset[str]" = frozenset()) -> dict:
    """What the FREE path makes of this variable's per-subject step, today.

    Called with no verdicts of any kind, so it is the state a verdict would be
    moving FROM -- which is the only honest baseline for a veto, and is also what
    makes `eligible` a correctness argument rather than a cost trick.

    `subjects` IS PASSED FOR THE SAME REASON EVERY OTHER ARGUMENT HERE IS: this
    must be the state `stamp` computes, and `stamp` reads the account's declared
    unit of analysis (round 26). Withholding it would make a variable whose
    licence stands on the live path look unlicensed here, and the paid question
    would not be asked about it.
    """
    return _premises.granularity_verification(var, hay, others, values,
                                              passages=passages,
                                              subjects=subjects)


def eligible(account: dict, text: str = "") -> list[tuple[dict, dict]]:
    """`[(variable, its free-path granularity record)]` for every variable whose
    step of 1 is licensed TODAY BY A SENTENCE, and which a verdict could move.

    THREE EXCLUSIONS, ALL OF THEM CORRECTNESS AND NOT ONLY COST:

      * a variable the free path does NOT license (`discreteness_source` is not
        `stated`) has no licence to withdraw. Asking would buy nothing, and --
        the part that matters -- a `true` there must not be reported as a
        withdrawal, because nothing fell. `granularity_verification` enforces
        that separately (`discreteness_licence_withdrawn_by_model` is False
        unless a licence actually stood), so this is belt and braces.
      * a variable whose KIND makes the step necessary keeps it whatever any
        sentence is about: a count of things is a whole number of things. No
        verdict can move it, so none is asked for. This is the one place where
        not asking is strictly better than asking and ignoring the answer -- a
        question whose answer is discarded is a paid line and a reader's
        confusion.
      * a variable the vocabulary has already refused for an AVERAGE is already
        withdrawn, by `discreteness_source` not being `stated`.

    So the vocabulary is the FLOOR here exactly as it is in `adjudication`: a run
    that never makes the paid call keeps every refusal it ever made, and a call
    that fails loses coverage rather than protection.
    """
    hay = _premises.Haystack(text)
    variables = _premises.readable_variables(account)
    values = [v for v in (account.get("values") or [])
              if _premises.well_formed(v) is None]
    by_variable: dict[Any, list[dict]] = {}
    for v in values:
        by_variable.setdefault(v.get("variable_id"), []).append(v)
    subjects = _premises.subject_terms(account)
    out: list[tuple[dict, dict]] = []
    for var in variables:
        mine = by_variable.get(var.get("id")) or []
        rec = licensing_record(var, hay, variables, mine,
                               _premises.table_passages(account, mine), subjects)
        if rec.get("discreteness_source") != _premises.STATED_DISCRETENESS:
            continue
        if rec.get("kind_makes_it_necessary"):
            continue
        if not _fold(rec.get("quote_sentence")):
            continue
        out.append((var, rec))
    return out


def licensing_window(rec: dict, hay: _premises.Haystack,
                     sents: list[tuple[int, str]]) -> str:
    """The passage a model is shown: the licensed sentence, in its section.

    `adjudication._window` BUILDS IT, unchanged -- sentence plus its immediate
    neighbours, bounded by the section the paper itself started, which is how a
    person reads a Methods paragraph. A second definition of "how wide is a
    passage" is the drift this repo keeps paying for.

    THE EMPTY STRING WHERE THE SENTENCE IS NOT IN THE ENUMERATION, which happens
    when the account's granularity quote locates inside a sentence the walker
    splits differently. The caller falls back on the located sentence itself
    rather than dropping the variable: a licence must be ASKABLE about, or the
    veto is gated by exactly the kind of text-matching accident it exists to
    replace.
    """
    want = _fold(rec.get("quote_sentence"))
    for i, (_, sent) in enumerate(sents):
        if _fold(sent) == want:
            return _adj._window(hay, sents, i)
    return ""


def _target(var: dict) -> str:
    """The variable the whole-number words either are or are not about.

    `_variable_target` UNCHANGED, which already appends the account's own
    `derivation` where there is one -- and that is the field round 23 names as
    carrying the separating fact ("a count of unserviceable fenders composes the
    berth condition rating, a count of loose bollards does not compose the quay
    surface grade"). NO BOUND AND NO STEP IS NAMED, and round 28's widening makes
    that more important rather than less: the question now IS about whether the
    paper shows the variable's reported figure to be whole, so a step printed in
    the target would be the answer handed to the model. Putting a number in front
    of a model that must not supply one is how `_bounds_clause` had to be fixed
    twice.
    """
    return _reading._variable_target(var)


def candidates(account: dict, text: str = "") -> list[dict]:
    """STAGE 1: ONE row per variable whose step of 1 rests on a sentence.

    THE SHAPE IS `premise_reading`'s, so `build_prompt`, `read` and `index` read
    a row written here with no change to any of them.

    `_rows_for` CAN STILL MAKE TWO ROWS OF ONE PASSAGE, and the tradeoff is worth
    naming because it is the one place "one question per variable" is not
    literally true. A window longer than `MAX_QUOTE_CHARS` -- three sentences of
    a converter-folded block -- becomes overlapping pieces rather than being
    truncated, which is `_segments`' own measured rule. For a WITHDRAWAL both
    options cost something: two pieces are two independent chances to withdraw,
    and a truncated one hides the half of the passage that would have kept the
    licence. Segmenting at least keeps every word in front of the model
    somewhere, and the overlap is longer than any English sentence, so a
    statement shorter than that is wholly inside at least one piece.
    """
    hay = _premises.Haystack(text)
    sents = hay.sentences_matching(_adj._ANY_SENTENCE)
    captions = _premises._captions(account)
    values = [v for v in (account.get("values") or [])
              if _premises.well_formed(v) is None]
    by_variable: dict[Any, list[dict]] = {}
    for v in values:
        by_variable.setdefault(v.get("variable_id"), []).append(v)
    out: list[dict] = []
    for var, rec in eligible(account, text):
        mine = by_variable.get(var.get("id")) or []
        quote = licensing_window(rec, hay, sents) or _fold(rec.get("quote_sentence"))
        for piece in _adj._rows_for(quote):
            out.append({**piece, "premise": PREMISE, "variable_id": var.get("id"),
                        "value_ids": [], "source": "served_text",
                        "target": _target(var),
                        "context": _reading._printed_context(mine, captions),
                        "relevance_version": RELEVANCE_VERSION})
    return _adj._finish(out, hay)


def adjudicate(account: dict, text: str, out_dir: str | Path, *,
               model: str = _reading.DEFAULT_MODEL, timeout_s: int = 900,
               budget: int | None = _reading.MAX_CANDIDATES_PER_PAPER) -> dict:
    """STAGE 2. Ask the model the attachment question of every licensing passage,
    and return the `premise_reading` record.

    PAID, and cheap by construction: one candidate per variable whose step rests
    on a sentence, which on the corpus papers is a handful, so a paper is one
    batched call and usually a small one. `premise_reading.read` makes it,
    reusing a reply already bought for the identical prompt.

    `budget` IS TAKEN ANYWAY, AND IT IS NOT CEREMONY. "Cheap by construction" is
    a claim about the corpus papers measured, not a bound the code carries: the
    count is one candidate per licensing variable, `_rows_for` can make two of a
    long passage, and neither term is capped. It costs nothing to be governed by
    the same ceiling as the nets that are known to run away.

    ATTACH IT BY SETTING `account["premise_reading"]` to the returned record:
    `premises.stamp` reads that key and `premise_reading.index` files a verdict
    by VARIABLE id, which is where `granularity_verification` looks.
    """
    # THE MEMBERSHIP IS CHECKED RATHER THAN ASSERTED IN PROSE, exactly as
    # `adjudication.candidates_for` and `adjudication_n.adjudicate` check their
    # own. This premise's NAME is the one place the design could be misread --
    # it is asked about the passage a licence rests on -- so the rail that its
    # verdict may only ever ADD a refusal is executed rather than documented.
    if PREMISE not in _reading.REFUSAL_PREMISES:
        raise ValueError(f"{PREMISE!r} is not a refusal premise; this module may only "
                         "ask a question whose verdict can remove a check, and can "
                         "never grant or restore a licence the free path withheld")
    return _reading.read(account, text, out_dir, model=model, timeout_s=timeout_s,
                         budget=budget, only=candidates(account, text))
