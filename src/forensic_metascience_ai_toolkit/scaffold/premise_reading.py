"""The five text premises, READ BY A MODEL ONCE PER PAPER instead of classified
by a vocabulary that grows forever.

WHY THIS MODULE EXISTS. Six adversarial rounds against the checks bridge
converged on one wall: 6, then 16, then 8 real false-accusation classes, every
one of them a closed regex vocabulary -- bound attribution, discreteness,
estimator type, unit multiplier, correction wording -- defeated by the next
honest phrasing a paper happens to use. There is no bound on how many ways a
paper can say the same thing, so a rule that CLASSIFIES free-form printed
language keeps finding gaps. This is the walker-as-witness pattern one layer up,
and section 8n already measured the alternative on exactly this kind of
judgement: a model reading the actual text beat the rule-based reader 714/714 on
composite tables, and it was the RULE that was wrong five times across five
rounds, never the model.

WHAT IS ASKED, AND WHAT IS NOT. The model is asked ONE closed question per
candidate -- "does this sentence establish this premise FOR this quantity?" --
about a passage THIS MODULE SUPPLIED from the served text. It never supplies the
passage, never supplies a number, and never reaches a premise the pre-filter did
not surface. A wrongly-judged relevance is the new failure mode and it is
bounded by the candidate set; a hallucinated passage is not a failure mode at
all, because there is no channel for one.

THE PROMPT IS THE ONE THAT WAS VALIDATED, and that is not a stylistic
preference. E1 (2026-09-09) replayed the thirty defect classes rounds 6-8 found,
verbatim from the fixtures that found them, through ONE generic prompt template
with no case-specific tuning: **37 of 37 defect cases correct on sonnet**, and
19 of 21 honest controls. `PREAMBLE`, `ITEM`, `TAIL`, `SCHEMA` and the three
question strings below are that template, unchanged. Changing their wording
discards the validation, so a change here is a change to an experiment's
instrument and must be re-measured, not reviewed.

TWO POLARITIES, AND THEY ARE NOT SYMMETRIC. This is the whole safety argument:

  * a LICENCE premise (`bound`, `step`) is what lets a check RUN. The model
    governs it in both directions: a `false` withdraws a licence the vocabulary
    granted (which can only remove a check), and a `true` grants one on a
    located sentence that prints the account's own number (which is the coverage
    this wave buys, and the only direction that carries risk).
  * a REFUSAL premise (`estimator`, `correction`, `averaging`) is what STOPS a
    check. The model may only ever ADD one. A model `false` NEVER removes a
    refusal the vocabulary made, because that would let a check run on a premise
    a rule had already withdrawn -- an accusation created by a model's opinion.

  * and the ALTERNATIVE-BASE / subject-count ceiling (`premises.paper_max_n`,
    `premises.other_bases_that_fit`) IS NOT IN THIS MODULE AT ALL. It is the one
    premise whose dangerous polarity is a model `false`: removing a candidate
    denominator lets `check_count_percent` run and accuse. E1 measured the
    failure directly -- on NC11-37679 (`of whom 241675 were aged 18 years or
    older`) sonnet said the sentence establishes no base and opus said it does --
    so a model verdict there would have removed a real base on the model that is
    cheap enough to run. It stays on the regex path, untouched.

THE VOCABULARIES ARE STILL HERE, DEMOTED. `premises.DISCRETENESS`,
`premises.AVERAGED`, `premises.WEIGHTED_PERCENTAGE`, `premises.NOT_A_SIMPLE_MEAN`
and `premises._CORRECTION_NOTICE` are now CANDIDATE GENERATORS: their job is
recall, which is what a regex is actually good at, and precision is the model's.
They are used loosely and widened here (`_BOUND_CANDIDATE`, `_STEP_CANDIDATE`,
`_ESTIMATOR_CANDIDATE`), because a pre-filter that misses a sentence is a gap the
model cannot close.

AND UNTIL ROUND 10 EVERY QUESTION ASKED HERE WAS ONE THAT COULD ONLY GRANT, which
is a hole in the two-polarity design above rather than a gap in a vocabulary. A
model was shown the sentence saying the reported quantity is an average -- the
pre-filter surfaces it as a `step` candidate -- and the only question put to it
was whether that sentence ESTABLISHES a whole-number step; a `false` withdraws
nothing, so the step granted on a DIFFERENT sentence stood. Measured with a real
sonnet call on an index that is `(observer A + observer B) / 2`: `establishes =
True`, and GRIM `impossible` on an honest paper. The `averaging` premise is the
withdrawing question, asked of the same sentences.

THE OTHER HALF OF THE SAME HOLE WAS A PLACE THE NET DID NOT REACH.
`premises.named_estimator` reads FOUR places for the paper's statement about its
own estimator -- the column band, the caption, the value's own sentence, and a
governing sentence of the paper's -- and `_estimator_candidates` built its blob
from three, so a paper whose Methods sentence the narrow vocabulary misses could
not even be ASKED about: zero candidates in all six of round 10's phrasings.

AND EVERY CANDIDATE SENTENCE IS OFFERED FOR THE VARIABLE, NOT JUST THE STAMPED
ONE. E1's single real miss -- NC7-ajcp, missed on sonnet AND on opus -- was not a
model error: it was a defensible "no" about the one sentence it was given, on a
paper that establishes the same premise in a DIFFERENT sentence about the same
variable. The fix belongs in the pre-filter and is here: every sentence of the
served text that names the variable and carries premise-shaped language becomes
a candidate, the account's own quote first.

AND ROUND 11 FOUND THE PRE-FILTER APPLYING THE LICENCE'S OWN TEST TO A REFUSAL,
which reproduces the vocabulary's blind spot one layer up. "Names the variable at
anchor >= 0.5" is what makes a LICENCE fail closed; used to decide what a model
is ALLOWED TO SEE about a refusal it becomes a filter, and the model cannot
withdraw a premise it is never shown. Two measured consequences, both closed
here: an ANAPHORIC averaging sentence (`The reported figure is the mean of the
pair.`) names nothing, so all six of round 11's phrasings offered ZERO averaging
candidates; and `MAX_TEXT_CANDIDATES`, ordered by POSITION, let four ordinary
introduction sentences take every slot ahead of the Methods sentence that
withdraws the premise. A refusal's pool now admits a sentence the DISCOURSE
resolves to this variable and the table's own caption and footnotes, is ordered
by EVIDENCE rather than by position, and has its own larger budget
(`MAX_REFUSAL_CANDIDATES`) -- all three safe for the same reason: a verdict there
can only ever ADD a refusal.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import passes as _passes
from . import premises as _premises

#: The artifact this module writes, and the version of the QUESTION SET. A run
#: read back against a different prompt version is a run of a different
#: instrument; the field is here so that can be seen rather than assumed.
SCHEMA_VERSION = "premise_reading/1"

#: The E1 experiment this prompt is the instrument of. Bump ONLY with a new
#: measurement: `PREAMBLE`/`ITEM`/`TAIL`/`SCHEMA`/`QUESTIONS` are the tested
#: object, and 37/37 is a claim about these bytes.
#:
#: `-target-bounds` IS A NEW MEASUREMENT AND NOT A REWORDING. The template is
#: unchanged; what changed is what the pre-filter puts in the TARGET slot, which
#: now names the range the account records (`_bounds_clause`). Measured on sonnet
#: in two independently composed batches: the mis-split `respectively` sentence
#: and the abbreviations block both flip from `true` to `false` when the target
#: names the declared range, and the honest control -- the same block, asked
#: about the variable whose range it does state -- stays `true`.
#: `-averaging-integrality` IS A NEW MEASUREMENT AND NOT A REWORDING EITHER, and
#: it is the only question in the set that changed. See `QUESTIONS["averaging"]`:
#: the old string asked whether ANY combination happened, which is broader than
#: the premise it gates, and on the real candidate path -- a window plus the
#: printed context, which is what `adjudication.candidates` builds -- sonnet
#: answered `true` on a MAXIMUM ("the higher of the two inspectors' whole-point
#: cards", even with "the hull score is itself always a whole number" in the same
#: sentence) and on a MINIMUM. Both are integer-preserving, so both were checks
#: withdrawn from an honest paper. Re-measured after the rewording: those flip to
#: `false`, the genuine averaging controls (a mean, a total divided by three, a
#: midpoint) stay `true`, and all eight of round 15's pinned defect passages stay
#: `true`. 2026-09-12, sonnet, $1.14 across six batches.
#: AND IT DID NOT MOVE FOR ROUND 17, WHICH IS A RESULT AND NOT AN OMISSION. That
#: round widened the estimator premise's RECALL (`adjudication`) and proposed
#: rewriting `QUESTIONS["estimator"]` with it, on the argument that a list of
#: adjectives is the same instrument as the vocabulary a model is brought in to
#: replace. The rewrite was written, measured head to head against this string on
#: the real candidate path, and REVERTED: 49 candidates asked under both, and the
#: two wordings agreed on 49 of 49 -- including seven estimators described with
#: NONE of this string's adjectives (a weighting stated as replication, a
#: two-stage mean, an unnamed trim, an unnamed imputation, a model fit, an unnamed
#: post-stratification, a geometric mean) and five honest controls a stricter
#: wording could have over-fired on. 2026-09-12, sonnet, $0.894 for both arms.
#: WHY IT GENERALISES, which is the thing worth keeping: the string is not a bare
#: list. It ends in the ARITHMETIC CONTRAST -- "rather than a plain total divided
#: by the number of subjects in this group" -- and that clause is what the model
#: answers from. Do not re-propose the rewrite without a phrasing that defeats
#: THIS string; bumping this constant discards the reuse of every saved reply for
#: all five premises, and paying that for a measured parity is a bad trade.
#: `-varying-n` IS A NEW QUESTION AND NOT A REWORDING OF AN OLD ONE. Round 18
#: adds a SIXTH premise, `varying_n`, and `QUESTIONS` is part of the named tested
#: object -- so the constant moves. The five existing strings and
#: `PREAMBLE`/`ITEM`/`TAIL`/`SCHEMA` are BYTE-IDENTICAL, so E1's 37/37, round
#: 16's averaging re-measurement and round 17's 74-of-74 parity are all still
#: claims about the bytes they were measured on.
#: AND NO SAVED REPLY IS DISCARDED BY THIS BUMP, which is worth stating because
#: it is easy to assume the opposite: `_reuse` compares the PROMPT'S OWN BYTES
#: (`{name}.prompt.md`) and this constant is not in the prompt, is not in
#: `_passes`' cache key, and is not `reconstruct.PROMPT_VERSION` -- the one
#: CLAUDE.md 8p warns discards every paid reading. A run whose candidate set is
#: unchanged pays nothing.
#: `-target-anchored` IS A REWORDING OF `varying_n` AND IT IS THE ONLY QUESTION
#: THAT MOVED. Round 18 shipped a string with TWO anchors -- the target's number
#: and an unnamed "that whole group" -- and a paper states item-level missingness
#: against its ENROLMENT, so on an account that has correctly bound the ANALYSED
#: n the honest sentence reads as a violation of the second anchor. MEASURED,
#: sonnet, 2026-09-12, the honest arm asked ALONE: **7 of 7 honest phrasings
#: across two fixtures answered `true`** and withdrew the only check those papers
#: had; reworded, 7 of 7 answer `false`. The true positives were re-measured in
#: the same round and did not move: **22 of 22**, round 18's own ten defect
#: windows among them. $1.44 over seven batches, sonnet.
#: THE COMPOSITION IS WHY ROUND 18 DID NOT SEE IT, and it is the methodological
#: half of this result. Asked in a batch that ALSO held the enrolled-target arm,
#: the shipped string answers all seven correctly (36 of 36) -- the contrast does
#: the disambiguation the question should have done. Round 18's own measurement
#: was one such mixed batch. A refusal premise's question must therefore be
#: measured on ONE PAPER'S candidates alone, which is the shape a real run has.
#: `-attachment` IS A SEVENTH PREMISE AND NOT A REWORDING OF ANY OF THE SIX. The
#: six existing strings and `PREAMBLE`/`ITEM`/`TAIL`/`SCHEMA` are BYTE-IDENTICAL,
#: so E1's 37/37, round 16's averaging re-measurement, round 17's 74-of-74 parity
#: and round 20's varying-n result are all still claims about the bytes they were
#: measured on. `QUESTIONS` is part of the named tested object, so the constant
#: moves; no saved reply is discarded, for the reason round 18 states below.
#: WHAT IT IS FOR, because it is the first question in this set that is asked
#: ABOUT A LICENCE. `discreteness_attachment` does not judge a licence premise --
#: it judges whether the passage a licence was ALREADY granted on was talking
#: about the target variable at all, and a `true` takes the licence away. See
#: `QUESTIONS["discreteness_attachment"]` and `adjudication_attach`.
#: `-premise` IS A WIDENING OF `discreteness_attachment` AND IT IS THE ONLY
#: QUESTION THAT MOVED. The other six strings and
#: `PREAMBLE`/`ITEM`/`TAIL`/`SCHEMA` are BYTE-IDENTICAL, so every earlier
#: measurement is still a claim about the bytes it was measured on. Round 24
#: asked the ATTACHMENT sub-question alone (whose quantity do these words
#: describe?) and rounds 25, 26 and 27 then built two more REGEX guards for the
#: two remaining sub-questions -- polarity (does the passage deny it?) and unit
#: of observation (whole-numbered per what?). Round 28 measured all three head to
#: head and the three sub-questions are one question; see
#: `QUESTIONS["discreteness_attachment"]` for the result and its denominators.
PROMPT_VERSION = "e1-discreteness-premise/2026-09-13"

#: E1 ran on sonnet and scored 37/37 on the defect classes. Opus was measured on
#: the two controls sonnet missed and agreed on one of them; neither model reads
#: NC7 as establishing its premise, which is why that case is fixed in the
#: pre-filter instead.
DEFAULT_MODEL = "sonnet"

#: The premise types a model may judge. `base` is deliberately absent; see the
#: module docstring.
PREMISES = ("bound", "step", "estimator", "correction", "averaging", "varying_n",
            "discreteness_attachment")

#: The two whose verdict may GRANT a licence, and the four whose verdict may
#: only ADD a refusal. Named rather than implied, because the asymmetry is the
#: safety argument and a reader has to be able to find it.
#:
#: `varying_n` IS A REFUSAL AND ITS POLARITY IS THE OPPOSITE OF THE CEILING'S,
#: which is the distinction round 18 had to make before it could exist. The
#: ALTERNATIVE-BASE ceiling (`premises.paper_max_n`,
#: `premises.other_bases_that_fit`) is dangerous because a model `false` REMOVES
#: a candidate denominator and lets a check run and accuse. `varying_n` moves the
#: other way: a `true` WITHDRAWS the group's n and refuses the check, and a
#: `false` lifts nothing. The ceiling is still not in this module and still not
#: judged by any model.
#:
#: `discreteness_attachment` IS A REFUSAL, AND THE NAME IS THE ONE PLACE THIS
#: COULD BE MISREAD. It is asked about the passage a GRANULARITY LICENCE rests
#: on, which sounds like the licence side and is not: the question is whose
#: quantity the passage's whole-number words describe, a `true` means "some other
#: quantity" and WITHDRAWS the licence the vocabulary granted, and a `false`
#: leaves the vocabulary exactly where it stood. So the polarity is `averaging`'s
#: -- the model may only ever take a check away -- and D71's rule (a model may
#: never LOOSEN a licence) is obeyed rather than bent: nothing a verdict here can
#: do grants or restores a step of 1 the free path did not already grant. That is
#: pinned literally, by a test that greps `adjudication_attach` and by
#: `TestAVerdictMayOnlyWithdraw` in round 24, not by this paragraph.
LICENCE_PREMISES = frozenset({"bound", "step"})
REFUSAL_PREMISES = frozenset({"estimator", "correction", "averaging", "varying_n",
                              "discreteness_attachment"})

#: THE REFUSAL PREMISES `index` FILES BY VARIABLE ID RATHER THAN BY VALUE ID.
#: `index` spelled the exception as a literal `== "averaging"` while there was
#: one member; a second is exactly the point at which that literal becomes the
#: duplicate-constant drift this repo keeps paying for, so it is named here
#: instead. Both members withdraw a property of the VARIABLE -- a per-subject
#: step of 1 -- which is where `granularity_verification` looks for them;
#: `estimator`, `correction` and `varying_n` withdraw a property of one printed
#: VALUE.
VARIABLE_KEYED_REFUSALS = frozenset({"averaging", "discreteness_attachment"})

#: THE REFUSAL PREMISES WHOSE WITHDRAWING ANSWER IS `false`, AND WHY THERE IS
#: EXACTLY ONE. Five of the six refusal questions are asked about a fact BESIDE
#: the premise -- is this an average, is this an estimator, is this the withdrawn
#: value, does this n differ -- so `establishes: true` reads as "the sentence
#: establishes THAT fact" and filing the refusal on `true` is natural for all of
#: them.
#:
#: `discreteness_attachment` IS NOW ASKED THE PREMISE QUESTION ITSELF (round 28),
#: and that is the one direction in which `establishes` cannot be borrowed: the
#: field is named for the premise, `PREAMBLE` defines `true` as "the sentence
#: does establish the premise for the stated target", and the premise IS the
#: whole-number one. MEASURED, sonnet, 2026-09-13, four consecutive wordings of
#: the widened question through `adjudication_attach.adjudicate` on one
#: two-candidate paper: EVERY ONE returned the correct REASON with the boolean
#: INVERTED -- including a wording whose TRUE was a positive four-fact
#: disjunction rather than a negation, and one run with `PREAMBLE`'s polarity
#: rule neutralised, which rules the preamble out as the cause. Round 24's own
#: string, on the SAME paper, was not inverted. So the model was never reading
#: the question wrong; it was filling a field called `establishes` with whether
#: the premise holds, which is what the field is called. Asked in the natural
#: direction and withdrawn on `false`, the same paper is right on both.
#:
#: THE POLARITY OF THE POWER IS UNCHANGED, WHICH IS THE ONLY THING THAT MATTERED.
#: A verdict may still only ever take a check away: `adjudication_attach.eligible`
#: asks ONLY about a variable the free path has already licensed by a sentence,
#: and `granularity_verification` ANDs the withdrawal in and uses it nowhere
#: else, so a `true` here agrees with a licence that already stood and restores
#: nothing. What moved is which boolean means "withdraw", not what a verdict is
#: allowed to do.
#:
#: AND A CONSUMER THAT READS THE WRONG FIELD FAILS OPEN. A filed row of such a
#: premise carries the model's literal answer in `establishes` (False, where it
#: withdraws) and the decision in `withdraws` (True). Anything that reads
#: `establishes` as "withdraw" therefore sees False, declines to withdraw, and
#: loses a check -- it cannot buy an accusation. Pinned in round 28.
WITHDRAWN_ON_FALSE = frozenset({"discreteness_attachment"})


def withdraws(premise: Any, establishes: Any) -> bool:
    """Does a verdict on `premise` WITHDRAW, given what the model answered?

    ONE DEFINITION, because the alternative is the duplicate constant this repo
    keeps paying for (CLAUDE.md 8j): the filing rule in `index` and every reader
    of a filed row have to agree about which boolean takes the check away.
    """
    return (not establishes) if premise in WITHDRAWN_ON_FALSE else bool(establishes)


# --------------------------------------------------------------------------
# The prompt. BYTE-FOR-BYTE THE ONE E1 MEASURED -- see the module docstring.
# --------------------------------------------------------------------------

PREAMBLE = """You are judging, for each candidate below, whether one sentence taken from a research paper establishes a specific premise about a specific quantity. A statistical consistency check will only run if the premise holds, and a wrong "yes" can make that check falsely accuse an honest paper.

Rules, applied to every candidate independently:
- Judge ONLY from what the quoted sentence says. Do not use outside knowledge to fill a gap the sentence leaves.
- The sentence may be about a DIFFERENT variable, a different unit or scale, a different quantity, or a different set of people than the one you are asked about. If so, it does not establish the premise for the one you are asked about.
- Do not invent or supply a number. You are judging only whether this sentence is relevant to, and sufficient for, the premise asked about.
- Answer true only if the sentence, read plainly, does establish the premise for the stated target. Otherwise answer false.
- Candidates are independent. Judge each on its own; do not assume they share an answer.

"""

ITEM = """--- CANDIDATE {i}
TARGET: {target}
{context}SENTENCE(S) FROM THE PAPER:
{sentence}

PREMISE QUESTION: {question}
"""

TAIL = """
Reply with JSON only: an object with key "verdicts", an array of {n} objects in
the order the candidates were given, each {{"candidate": <number>, "establishes": true or false, "reason": "<one line, max 25 words>"}}."""

SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate": {"type": "integer"},
                    "establishes": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["candidate", "establishes", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

#: THE QUESTIONS. `bound`, `step` and `correction` are E1's own strings,
#: unchanged; `step` deliberately carries "in the unit and scale the number is
#: PRINTED in", which is how one question covers both the discreteness premise
#: and the unit/scale multiplier premise -- E1 measured that phrasing against the
#: thousands / per-100 / minutes-printed-as-hours cases and it answered all of
#: them.
#:
#: `estimator` WAS THE ONE QUESTION E1 DID NOT MEASURE. ROUND 17 MEASURED IT, AND
#: LEFT IT ALONE. 74 candidate rows on the real candidate path -- a window plus
#: the printed context, which is what `adjudication.estimator_candidates` builds,
#: and NOT a bare sentence, the distinction round 16 proved matters -- and this
#: string was right about 74 of 74, which is 72 distinct rows (two windows were
#: asked in both batches): 40 defect passages `true`, 32 honest controls `false`.
#: The defects cover four phrasings that return three
#: `impossible` verdicts on an honest paper at `ff4d5ae`, a document-level
#: statement, a statement split across two sentences, a footnote-only statement,
#: and seven estimators described with NONE of this string's adjectives. The
#: controls include a bare `Mean (SD)` column with a plain caption, a reported
#: exclusion, a rounding step and the name of the spreadsheet used.
#:
#: THE REWRITE THAT WAS PROPOSED AND REVERTED IS RECORDED IN `PROMPT_VERSION`. Its
#: argument was that a list of adjectives is the same instrument as a vocabulary;
#: the measurement says this string is not read as a list, because it ends in the
#: ARITHMETIC CONTRAST and that is the clause the model answers from.
#:
#: IT WAS ALSO MEASURED ON THE PREMISE NEXT DOOR, which is a risk the wider recall
#: net carries by construction: table furniture is admitted to this premise's
#: candidate set with no aboutness test, so a footnote saying the analysed n
#: differs between measures IS asked this question, and a `true` there would file
#: a true fact under the wrong premise and print the wrong reason in a docket. It
#: answers `false`. That had to be measured rather than guarded in
#: `adjudication`, because D71's grep rail forbids that module from naming the
#: other premise at all.
#:
#: Its polarity is why it was safe to ship unmeasured in the first place: a
#: verdict on it can only ever ADD a refusal, so a wrong answer costs a check and
#: cannot buy an accusation.
#:
#: `averaging` ASKS ABOUT THE ARITHMETIC, NOT ABOUT COMBINATION. The premise it
#: gates is a per-subject STEP OF 1, so the only thing that matters is whether the
#: operation can return a NON-WHOLE number from whole inputs. A mean, a total
#: divided by its count, a weighted blend and a midpoint can; a maximum, a
#: minimum, a first, a last, a mode, a plain total and a plain count cannot -- the
#: maximum of two integers is an integer as a fact about the operation, and no
#: sentence has to say so. The old string asked instead whether the value was "an
#: AVERAGE, midpoint or other combination", which is strictly broader than the
#: premise, and MEASURED (see `PROMPT_VERSION`) it withdrew the step from a
#: maximum and from a minimum on honest fixtures.
#:
#: AND AMBIGUITY RESOLVES TOWARD THE REFUSAL, which is the opposite of the
#: PREAMBLE's general instinct and has to be said in the question because the
#: preamble is shared with the licence premises. A wording that could name either
#: an averaging or a selecting operation ("the central value", "the consensus",
#: "reconciled into one figure") does not ESTABLISH integrality, and this premise
#: can only ever remove a check -- so the unclear case answers `true`. Measured:
#: without that clause sonnet read "the central value of the three judges' cards"
#: as a median of three and dropped one of round 15's eight pinned defects.
QUESTIONS: dict[str, str] = {
    "bound": "Does this sentence state the numeric range (lowest and highest possible "
             "value) of the target variable, as that variable is reported in this paper?",
    "step": "Does this sentence establish that each subject's value of the target "
            "variable, in the unit and scale the number is PRINTED in, is a whole "
            "number (an integer)?",
    "correction": "Does this correction notice say that the target number is the OLD, "
                  "erroneous value the paper is withdrawing (as opposed to the corrected "
                  "value that now stands)?",
    "estimator": "Does this sentence, caption or column heading say that the target "
                 "number is a weighted, standardized, adjusted, pooled, imputed, trimmed "
                 "or otherwise model-estimated quantity, rather than a plain total "
                 "divided by the number of subjects in this group?",
    "averaging": "The check this premise gates can only run if each subject's own value "
                 "of the target variable is a whole number. Does this sentence say that "
                 "each subject's value was arrived at by combining two or more separate "
                 "observations, ratings or measurements of that subject in a way that "
                 "need NOT give back a whole number even when every observation combined "
                 "is itself a whole number? Answer TRUE for an average or mean, a total "
                 "divided by how many observations there are, a weighted blend, a "
                 "midpoint or splitting the difference between two values, and for any "
                 "combining whose operation the sentence leaves unclear or whose wording "
                 "could equally name an averaging one (for example 'the central value', "
                 "'reconciled into one figure', 'the consensus'). Answer FALSE only where "
                 "the operation is named unambiguously AND always returns one of the whole "
                 "numbers combined -- the higher, the lower, the first, the last, the most "
                 "frequent, a plain total, a plain count -- and FALSE where the sentence "
                 "describes no combining of separate observations of the same subject at "
                 "all.",
    # `varying_n` ASKS WHETHER THE NUMBER IN THE TARGET IS THE WRONG DENOMINATOR
    # FOR THIS QUANTITY, and that number is the only anchor it has. Round 18
    # named it in the TARGET -- the move `_bounds_clause` made for `bound`,
    # because the honest case ("Forty-four operators returned a usable clarity
    # card" where the account's n IS 44) and the defect case are the same
    # sentence and only the comparison separates them.
    #
    # AND ROUND 20 FOUND THAT NAMING IT THERE IS NOT ENOUGH IF THE QUESTION ALSO
    # OFFERS A SECOND ANCHOR. Round 18's string asked whether the quantity was
    # computed over "FEWER subjects than that whole group" and then said "Answer
    # TRUE where the passage names a number of subjects for this quantity that
    # differs from the number in the target". A paper states item-level
    # missingness against its ENROLMENT -- `44 of the 47`, `missing for 3 of the
    # 47`, `all but three of the 47` -- so on an account that has correctly bound
    # the ANALYSED 44 the passage is fewer than the roll while being exactly the
    # target, and the enrolled 47 is a number that differs. MEASURED, sonnet,
    # 2026-09-12, seven such phrasings over two fixtures asked alone:
    # 7 of 7 answered `true` and withdrew the only check an honest paper had,
    # six of them reasoning in as many words "fewer than whole group" and the
    # seventh "matching target's smaller subgroup" -- the differs-clause firing
    # after the model had already seen the match.
    #
    # SO THERE IS ONE ANCHOR NOW AND THE TWO-NUMBER CASE IS DECIDED EXPLICITLY.
    # The question asks first for the CONTRIBUTING number -- how many the passage
    # says actually contributed to this quantity -- and states that a larger
    # enrolled total, and a count of who was missing from it, are not that
    # number. A contributing number equal to the target is `false` even when the
    # passage also prints the roll.
    #
    # AND THE DOMINANCE MAY NOT BE READ AS "THE TARGET'S NUMBER APPEARS". That
    # inversion is how this fix would manufacture the accusation it exists to
    # remove: `missing for 3 of the 47` asked at a target of 47 prints the
    # target's own number, and answering `false` there restores GRIM `impossible`
    # on a paper whose arithmetic is exact at 44. Measured in the same round --
    # eight such windows, all `true` under this string, and 22 of 22 true
    # positives held including round 18's own ten defect windows.
    #
    # IT MAY NOT READ A NUMBER OUT, and the last clause still says so. A
    # varying-n passage routinely prints a count, and taking one would SUPPLY a
    # denominator rather than narrow one -- CLAUDE.md 8d invariant 1, which
    # `group_n`'s own `subgroup_stated_in_the_sentence` branch already obeys by
    # refusing rather than re-binding. The clause is now about what the model may
    # REPORT rather than about what it may read, because the round-18 wording
    # ("do not infer or calculate") also forbade the plain reading that three
    # missing from forty-seven leaves the target's forty-four.
    #
    # AND AMBIGUITY RESOLVES TOWARD THE REFUSAL, as it does for `averaging` and
    # for the same reason: this premise can only ever remove a check, so a
    # passage that says some subjects are missing without saying how many is a
    # `true`. The clause has to be in the question because `PREAMBLE` is shared
    # with the licence premises, whose instinct is the opposite.
    "varying_n": "The check this premise gates divides the target quantity by the "
                 "number of subjects stated in the target above. Judge ONE thing: is "
                 "that number the WRONG denominator for this quantity? First work out "
                 "what number of subjects this passage gives for THIS quantity -- how "
                 "many of them it says actually contributed to it. A passage often "
                 "names a larger enrolled, invited or randomised total as well, and may "
                 "say how many of that total were missing; the number that decides this "
                 "question is the one left contributing to this quantity, never the "
                 "larger total and never the count of who was missing. Answer TRUE "
                 "where that contributing number is not the number in the target, "
                 "including where the passage only plainly implies it -- because some "
                 "did not answer this item or complete this measure, because usable or "
                 "complete data were available for only some of them, because the "
                 "quantity is reported for a subgroup, or because some had left the "
                 "study by the time it was measured. Answer TRUE where the passage says "
                 "some subjects are missing from this quantity but leaves the "
                 "contributing number unclear. Answer FALSE where the contributing "
                 "number is the number in the target; it stays FALSE when the passage "
                 "also names a larger total, or says how many were missing from that "
                 "larger total, because the target's number already excludes them and "
                 "the denominator is right. Answer FALSE where the passage plainly says "
                 "the measure was taken for, or the quantity computed over, every "
                 "subject and names no smaller contributing number, and FALSE where it "
                 "says nothing at all about how many subjects contributed. Do not "
                 "propose or report a denominator; your whole answer is the true or "
                 "false.",
    # `discreteness_attachment` ASKS WHICH QUANTITY A WHOLE-NUMBER CLAIM IS
    # ABOUT, which is the one thing three rounds of boundary rules were trying
    # to compute and could not. Rounds 21, 22 and 23 each widened or narrowed a
    # rule over commas, and a fresh adversary found the next phrasings within
    # hours; round 23's own docstring records why, and it is not a missing
    # vocabulary entry. `Rescue technique was graded to the nearest half point,
    # together with a count of damaged floats` -- who is counted in whole units?
    # -- is SYNTACTIC ATTACHMENT RESOLUTION, and a comma heuristic does not solve
    # it. Two populations that must be decided oppositely sit in ONE feature cell
    # of everything `_discreteness_is_attributable` can compute
    # (`test_scaffold_checks_round23.TestTheFeatureCellIsShared`).
    #
    # THE WORDING IS ABOUT ATTACHMENT AND ABOUT NOTHING ELSE, which is the half
    # this repo has twice got wrong in a way that cost real coverage (round 16's
    # averaging string asked whether ANY combination happened; round 18's
    # varying-n string offered a second anchor a paper's enrolment fills). So it
    # does NOT ask whether the variable is discrete -- that would invite the
    # model to re-decide the licence, which is the direction D71 forbids and
    # which a model answering `false` from general knowledge of Likert scales
    # would quietly do. It asks the model to enumerate the passage's whole-number
    # phrases and say, of each, which quantity it describes.
    #
    # THE POLARITY IS THE SAFETY ARGUMENT AND IT IS INVERTED FROM THE GATE'S. A
    # `true` says the whole-number words belong somewhere else, and `index` files
    # it as a REFUSAL, so it can only take the check away. There is no answer to
    # this question that grants anything: a `false` leaves the free path's own
    # licence exactly where it stood, which is why the regex may stay generous.
    #
    # AND AMBIGUITY RESOLVES TOWARD THE REFUSAL, as it does for `averaging` and
    # `varying_n` and for the same reason -- this premise can only ever remove a
    # check. The clause has to be in the question because `PREAMBLE` is shared
    # with the licence premises, whose instinct is the opposite.
    #
    # THE POLARITY HAD TO BE SAID THREE TIMES, AND THE FIRST WORDING WAS MEASURED
    # INVERTING ON A REAL RUN. This question's TRUE is the opposite of the
    # PREAMBLE's -- the preamble says "Answer true only if the sentence, read
    # plainly, does establish the premise for the stated target", and here a TRUE
    # says the sentence establishes it for somebody ELSE. The first wording
    # opened by naming the whole-number premise ("The check this premise gates
    # can only run if each subject's own value ... is a whole number") and put
    # its FALSE clause before its TRUE clause. MEASURED, sonnet, 2026-09-12: in a
    # 58-candidate interleaved batch it answered 58 of 58 correctly, and on the
    # SAME question in a real two-candidate run through `adjudicate` it returned
    # two correct REASONS with both booleans INVERTED -- "the only whole-number
    # language belongs to reed dent score or workload, not warp tension grade"
    # scored `false`, and "plainly describing the target's own per-subject values
    # as integers" scored `true`. It had answered the preamble's question about
    # the premise this string's first sentence had just named for it, which a big
    # batch's worth of context had been covering up.
    #
    # SO THE OPENING NAMES NO PREMISE, THE TRUE CLAUSE COMES FIRST (as it does in
    # every other question in this set), AND THE INVERSION IS FORBIDDEN BY NAME
    # in two places. The consequence of a verdict is deliberately NOT stated: the
    # preamble already tells the model a wrong `true` causes a false accusation,
    # which is backwards here, and correcting it in the question would push
    # toward `true` on a premise whose honest arm is 38 of 58 candidates.
    # RE-MEASURED after the rewrite: see `test_scaffold_checks_round24`.
    "discreteness_attachment":
        "Does this passage show that the figure this paper reports for ONE SUBJECT on "
        "the target variable is a whole number? Answer TRUE only where it does: where "
        "at least one phrase plainly gives the target's own reported per-subject figure "
        "whole numbers, and nothing in the passage moves it off them. A plain statement "
        "that the target was counted, scored, graded, entered or recorded in whole "
        "numbers is such a phrase: it need not use the words 'each subject' or 'per "
        "subject', and it still counts when the same passage also describes a different "
        "quantity's granularity. Answer FALSE in any of these four cases. (a) The "
        "passage's whole-number wording -- an integer, a whole unit or whole point, "
        "counting or tallying in whole units, a fixed number of scale points or "
        "response options, a Likert item -- describes some OTHER quantity, a different "
        "variable, a different measure, a count of something else, a separate "
        "instrument or item, and none of it describes the target. (b) The passage gives "
        "the TARGET a granularity finer than whole numbers -- half points, quarter "
        "points, fractions, decimals -- or says that whole-number recording of the "
        "target was avoided, dropped, abandoned, discontinued, ruled out, replaced, "
        "done without, or found too coarse. (c) The passage's whole-number wording "
        "about the target is attached to a single OBSERVATION of it -- a visit, "
        "occasion, session, rater, item, frame or sitting -- or to a unit smaller than "
        "the one the paper prints, rather than to the one figure the paper reports for "
        "a subject. (d) The whole-number wording could equally describe the target or "
        "another quantity named beside it, so which of them it describes cannot be told "
        "from the passage. Judge only from the words of this passage: do not bring in "
        "anything you know about measures of this kind from outside it, and do not "
        "answer from what is likely to be true of such a variable. Where the passage "
        "leaves it open, answer FALSE.",
}


# --------------------------------------------------------------------------
# The pre-filter: the demoted vocabularies, widened for RECALL
# --------------------------------------------------------------------------

#: BOUND-SHAPED LANGUAGE, loose. It does not have to be right -- a candidate it
#: surfaces is judged, and a candidate it invents costs one line of a prompt.
#: What it must not do is MISS the sentence, so it takes every ordinary way a
#: paper prints a range and does not try to tell a range from a date.
_BOUND_CANDIDATE = re.compile(
    r"\b(?:rang(?:e|es|ed|ing)|scales?|scaled|scor(?:ed|es|ing)|rat(?:ed|ings?)|"
    r"cod(?:ed|ing)|measured|assessed|response\s+options?|answer\s+options?|"
    r"minimum|maximum|lowest|highest|possible|"
    r"likert|dichotom\w+|binary|indicator|point\s+scale)\b"
    r"|\bfrom\s+[-+]?\d"
    r"|\bbetween\s+[-+]?\d"
    r"|[-+]?\d[\d.]*\s*(?:to|-|‐|‑|–|—)\s*[-+]?\d"
    r"|\b\d\s*[/=]\s*\d\b", re.I)

#: GRANULARITY- AND UNIT-SHAPED LANGUAGE, loose. The three vocabularies the
#: current code judges with are UNIONED here rather than restated -- the
#: discreteness words, the averaging veto, and the recorded-in-a-unit phrase --
#: and the scale multipliers a table band prints are added, because "thousands"
#: over a column is exactly the premise the `step` question asks about and no
#: existing vocabulary contains it.
_STEP_CANDIDATE = re.compile(
    "(?:" + _premises.DISCRETENESS.pattern + ")"
    + "|(?:" + _premises.AVERAGED.pattern + ")"
    + "|(?:" + _premises._RECORDED_IN_UNIT.pattern + ")"
    + r"|\b(?:thousands?|hundreds?|millions?|billions?|per\s+\d+|"
      r"percentage\s+points?|expressed\s+in|reported\s+in|given\s+in|"
      r"presented\s+in|shown\s+in\s+units|in\s+units\s+of|"
      r"nearest\s+(?:whole|integer|unit)|to\s+the\s+nearest)\b", re.I)

#: ESTIMATOR-SHAPED LANGUAGE, loose. Wider than `NOT_A_SIMPLE_MEAN` and
#: `WEIGHTED_PERCENTAGE` on purpose: those two are JUDGEMENTS and have to be
#: narrow, and this one is a net.
#:
#: AND A NET MADE OF ADJECTIVES MISSES A SENTENCE THAT NAMES ITS ESTIMATOR AS A
#: NOUN OR AS AN OPERATION. Round 11: `Means are shrunken towards the site mean
#: by an empirical Bayes step.` and `Means were computed with the
#: Horvitz-Thompson estimator for the roll.` carried no adjective in this list,
#: so a paid pass was offered ZERO candidates and could not rescue them even in
#: principle. The two shapes are added rather than the two names: a paper that
#: says WHAT PROCEDURE produced its means has said the premise is gone, whatever
#: the procedure is called.
_ESTIMATOR_CANDIDATE = re.compile(
    r"\b(?:weight(?:s|ed|ing)?|standardi[sz]\w+|adjust(?:ed|ing|ment)|"
    r"least[-\s]squares?|lsmeans?|emms?|lsms?|marginal|trimmed|winsori[sz]\w+|"
    r"truncated|pooled|imputed|imputation|bootstrap\w*|jack[-\s]?knifed?|"
    r"geometric|harmonic|back[-\s]transformed|predicted|fitted|model[-\s]based|"
    r"covariate|two[-\s]stage|multi[-\s]?stage|survey\s+design|propensity|"
    r"post[-\s]?stratif\w+|calibrat\w+|estimator|estimation|shrinkage|"
    r"shrunk\w*|smoothed|penali[sz]ed|regulari[sz]ed)\b"
    r"|\b(?:means?|averages?|estimates?|percentages?|proportions?|rates?)\b"
    r"[^.;\n]{0,60}?\b(?:computed|calculated|derived|obtained|estimated|"
    r"produced|constructed)\s+(?:with|using|from|by|via)\b", re.I)

#: A CORRECTION NOTICE, loose: the existing notice detector, which is already a
#: recall-shaped test. What the vocabulary could not do is decide WHICH of the
#: two numbers a notice names is the withdrawn one, and that is the question.
_CORRECTION_CANDIDATE = _premises._CORRECTION_NOTICE

#: COMBINATION-SHAPED LANGUAGE, loose, for the premise that WITHDRAWS a step.
#:
#: WHY THIS EXISTS, AND IT IS THE STRUCTURAL HALF OF ROUND 10's F4. Under a model
#: `true` on the step, the only guard left on the granted licence is
#: `premises.AVERAGED` -- a closed vocabulary -- and round 10 walked past it four
#: ways on an index that is `(observer A + observer B) / 2`. Widening that regex
#: closes the four; it does not close the class, because the pre-filter's own
#: recall vocabulary decides what the model is ALLOWED TO SEE, and until now
#: every question this module asked was a question that could only GRANT. A model
#: cannot withdraw a premise it is never shown, so the withdrawing question is
#: now asked of the sentences that carry combination language.
#:
#: ITS POLARITY IS WHY SHIPPING IT UNMEASURED IS SAFE, exactly as the module
#: docstring argues for `estimator`: a verdict here can only ever ADD a veto, so
#: a wrong answer costs a check and cannot buy an accusation.
#:
#: ROUND 13 ADDED THE SHAPE, NOT ANOTHER VERB. "Each member's overall
#: promptness figure blends the fourteen branch-level counts recorded for that
#: member into one score" carries none of the words above -- `blends` is the
#: whole claim, and the next honest paper will use a different verb again. The
#: `into one <score>` alternative is verb-agnostic on purpose, matching
#: `premises.AVERAGED`'s own round-13 branch: a wrong candidate costs one
#: prompt line (recall net, not a judgement), so being generic here is the
#: cheap side of the tradeoff.
_AVERAGING_CANDIDATE = re.compile(
    r"\b(?:mean|means|average|averages|averaged|averaging|midpoint|midpoints|"
    r"mid[-\s]points?|halved|halving|combined|combining|composite|aggregate|"
    r"aggregated|aggregating|summed|pooled|index|indices|"
    r"divided\s+by|added\s+together)\b"
    r"|\binto\s+(?:a\s+|one\s+)(?:single\s+)?"
    r"(?:score|figure|value|index|number|measure|total|estimate)s?\b", re.I)

#: A SENTENCE THAT GOVERNS WHAT THE PAPER REPORTS, rather than describing a model
#: somewhere in it. Paired with `_ESTIMATOR_CANDIDATE` so a Methods sentence
#: naming the estimator of the paper's own reported quantities can reach the
#: model. `_estimator_candidates` built its blob from the column band, the
#: caption and (only for a non-table-cell) the value's own quote, so a
#: DOCUMENT-LEVEL statement produced ZERO candidates -- measured 0 in all six of
#: round 10's F5 cases -- and `named_estimator` reads four places while the
#: model's net reached three.
_GOVERNS_REPORTED = re.compile(
    r"\b(?:means?|averages?|estimates?|statistics?|percentages?|prevalences?|"
    r"proportions?|rates?|figures?|values?)\b"
    r"|\b(?:tables?|figures?)\s*[\w.]{0,4}\s*"
    r"(?:reports?|presents?|shows?|gives?|contains?)\b", re.I)

#: How many sentences of the served text may be offered for one premise of one
#: variable. The account's own quote is always first and does not count against
#: it. A cap rather than a filter: the sentences are ordered by position, so the
#: set is deterministic and a paper that says a thing five ways costs no more
#: than one that says it twice.
MAX_TEXT_CANDIDATES = 4

#: THE SAME CAP FOR A REFUSAL PREMISE, AND IT IS BIGGER FOR A STATED REASON.
#:
#: "A cap rather than a filter" IS TRUE ONLY FOR A LICENCE. For a REFUSAL the
#: candidate set is what the model is ALLOWED TO SEE, and a premise it is never
#: shown is a premise it cannot withdraw -- so a cap ordered by POSITION is a
#: filter after all. Round 11 measured it: four ordinary introduction sentences
#: merely containing `adjusted` / `predicted` / `covariate` / `weighted` took
#: every slot, and the Methods sentence that withdraws the premise was never
#: asked about, in both channels. Two things follow, and both are here: a
#: refusal's budget is larger (a wrong verdict there costs a check and cannot
#: buy an accusation, so the only cost of a bigger set is prompt length), and
#: the set is ordered by EVIDENCE rather than by position -- a sentence carrying
#: the narrow shape a judgement would actually use goes first.
#:
#: RAISED AGAIN, WAVE 7D. Ranking-before-cutting already makes 8 survive nine
#: decoys (`TestARefusalCandidateSetIsAFilterUnlessItIsRanked`), because the
#: narrow-vocabulary sentence sorts first regardless of how many decoys precede
#: it in the document. The cap is raised anyway, to `MAX_PER_CALL` -- the point
#: past which a bigger set buys nothing but a second call -- so that no future
#: paper with more than eight genuinely evidence-shaped candidates for one
#: premise of one variable can have the tenth one silently cut before ranking
#: ever sees it. Recall for a refusal is a WINDOW; this is the same rule
#: applied to how many of that window's members reach the model, not only to
#: which one goes first.
MAX_REFUSAL_CANDIDATES = 40

#: How many candidates go in one call. E1 ran twenty in one call and twenty-one
#: in another with no degradation; the cap exists so a large paper cannot
#: overflow the output cap in one request, which is the failure `reconstruct`
#: already met on a twelve-table pass 3.
MAX_PER_CALL = 40

#: WHAT ONE FULL CALL COSTS, MEASURED, and the only number a budget in
#: candidates can be turned into money by.
#:
#: Nine real sonnet calls of the round-19 probe harness
#: (`runs/{a3_filler5_offered,c2_decoys38,d_window_cut,e2_*,e3*}`): a
#: `MAX_PER_CALL`-sized call of 40 candidates cost $0.20096, a 10-candidate call
#: $0.198668, an 8-candidate call $0.148666, a 1-candidate call $0.03554. So the
#: call has a fixed floor of roughly three cents and a full one lands at twenty,
#: which is what makes CANDIDATES divided by `MAX_PER_CALL` the honest unit to
#: price: a partly-filled call costs nearly as much as a full one, so the bill
#: tracks CALLS, and calls track candidates in steps of `MAX_PER_CALL`.
#:
#: IT IS A PRICE, NOT A LIMIT. Nothing reads it to decide anything; it exists so
#: that a budget expressed in candidates can be reported in dollars, and so that
#: a help string quoting a cost quotes one somebody measured.
USD_PER_FULL_CALL = 0.20

#: THE PER-PAPER CANDIDATE BUDGET. The unit is CANDIDATES because CANDIDATES are
#: what the bill counts -- `MAX_PER_CALL` of them per call, `USD_PER_FULL_CALL` a
#: call -- so the default below is `2000 / 40 * $0.20`, fifty calls and ten
#: dollars.
#:
#: WHY THERE HAS TO BE ONE AT ALL, AND THE GROWTH LAW IS MEASURED RATHER THAN
#: FEARED. Every other cap in this package is PER SCOPE:
#: `MAX_REFUSAL_CANDIDATES` bounds one premise of one variable, and
#: `adjudication._estimator_candidates` spends it once per `(variable, kind)` and
#: once per `(paper, kind)`. The NUMBER OF SCOPES is set by the paper, so nothing
#: bounded the product. Stage 1 is free and deterministic, so the product can be
#: counted without paying for it; counted on the REAL served text of two corpus
#: papers (`jats._derive_paper_text`, `xml_publisher` rung) against accounts
#: carrying 10, 25 and 47 variables, the estimator net returns:
#:
#:     jamanetworkopen 37679   10 vars   984    25 vars  2,424   47 vars  4,536
#:     ajcp 70049              10 vars   992    25 vars  2,402   47 vars  4,470
#:
#: which is LINEAR IN THE NUMBER OF VARIABLES at ~97 candidates each, with no
#: term that bounds it -- 114 calls and ~$22.68 at the top row. Those accounts
#: are synthetic in their VARIABLES (every one carrying both a mean and a
#: percentage, which maximises the `(variable, kind)` scopes) and real in
#: everything the net actually reads, so they are an UPPER bound for a given
#: variable count rather than a reproduction of a paid run; the costing pass that
#: prompted this work measured 1,819 candidates / 46 calls / $9.09 for one net on
#: a real 47-variable account of the same paper, and projected $20-30 unbudgeted.
#: Both agree on the part that matters: the number has no ceiling of its own.
#: CLAUDE.md section 8q has carried "what happens if the model runs out of
#: budget" as an unanswered ask; before this constant the answer was that there
#: was no budget to run out of.
#:
#: WHY THE DEFAULT IS A RUNAWAY GUARD AND NOT A COST CONTROL, which is the whole
#: of the safety argument for having a budget at all. Every net that reaches this
#: module is a REFUSAL net: a verdict can remove a check and can never add one.
#: So a candidate that is cut is NOT a saving -- it is a check left RUNNING that
#: the model might have withdrawn, and the cut therefore falls in the one
#: direction that can end in a false accusation. A default low enough to save
#: money on an ordinary paper would open that channel on every paper, which is
#: the trade this project does not make.
#:
#: 2,000 is therefore set ABOVE the largest real-account figure on hand (1,819),
#: so it cuts nothing on any paid run yet measured, and it caps an unbudgeted
#: paper at fifty calls and ten dollars instead of the $20-30 projected above. A
#: paper at the synthetic upper bound (4,536) WOULD be cut by it, and when that
#: happens the run says so in the account, names the premises and variables it
#: never asked about, and states which way the loss falls -- see `_over_budget`.
#: An operator who wants a tighter bill passes a smaller budget and owns that
#: trade knowingly; what is not on offer is spending the money silently or
#: cutting the questions silently.
MAX_CANDIDATES_PER_PAPER = 2000


def projected_usd(n_candidates: int, per_call: int = MAX_PER_CALL) -> float:
    """What `n_candidates` will cost, at the measured price of a call.

    Rounded UP to whole calls, because a partly-filled call is billed like a full
    one (`USD_PER_FULL_CALL`) and a projection that rounds down is the flattering
    error.
    """
    calls = -(-max(0, int(n_candidates)) // max(1, int(per_call)))
    return round(calls * USD_PER_FULL_CALL, 2)


# --------------------------------------------------------------------------
# Candidate generation
# --------------------------------------------------------------------------


def _one_line(raw: Any, limit: int = 240) -> str:
    return " ".join(str(raw or "").split())[:limit]


#: How long a candidate passage may be. A "sentence" longer than this is a
#: conversion artefact -- a whole markdown table folded onto one line -- rather
#: than a sentence, and there is no point asking a model about one.
MAX_QUOTE_CHARS = 700


def _clip(raw: Any, limit: int = MAX_QUOTE_CHARS) -> str:
    """One passage, whitespace collapsed, CUT AT A WORD BOUNDARY.

    CUTTING MID-WORD BREAKS LOCATION, which is the one property a candidate must
    have. `Haystack.locate` refuses a span that begins or ends inside a word, so
    a hard `[:limit]` slice of a long sentence turned three real passages of the
    served text into unlocatable ones and dropped them before the call. A prefix
    that ends where a word ends is still a contiguous span of the document.
    """
    s = " ".join(str(raw or "").split())
    if len(s) <= limit:
        return s
    cut = s.rfind(" ", 0, limit)
    return s[:cut] if cut > 0 else s[:limit]


#: How many `MAX_QUOTE_CHARS` pieces one over-long passage may be cut into
#: before what is left is REPORTED rather than carried. Eight is 5,600
#: characters -- longer than any real sentence and long enough for the folded
#: blocks CLAUDE.md 8l describes -- and the number matters far less than the
#: fact that passing it is stamped on the row rather than happening silently.
MAX_QUOTE_SEGMENTS = 8

#: HOW FAR EACH PIECE REACHES BACK INTO THE ONE BEFORE IT. A cut is a hole:
#: MEASURED (2026-09-12), a statement 600 characters into a folded block landed
#: half in one piece and half in the next and reached a model in neither -- a
#: butt-jointed segmentation trades truncation for straddling and fixes nothing.
#: The pieces therefore overlap by a third of the limit, which is longer than any
#: English sentence, so a statement shorter than that is WHOLLY inside at least
#: one piece wherever the cuts happen to fall.
QUOTE_SEGMENT_OVERLAP = MAX_QUOTE_CHARS // 3


def _segments(raw: Any, limit: int = MAX_QUOTE_CHARS,
              cap: int = MAX_QUOTE_SEGMENTS,
              overlap: int = QUOTE_SEGMENT_OVERLAP) -> tuple[list[str], int]:
    """`([piece, ...], characters not carried)` for one passage.

    `_clip` IS THE RIGHT ANSWER FOR A LICENCE AND THE WRONG ONE FOR A REFUSAL,
    and `MAX_QUOTE_CHARS`' own docstring reasons only from the licence side
    ("there is no point asking a model about one"). For a REFUSAL the passage is
    what the model is ALLOWED TO SEE, so cutting its tail is the same act as
    dropping the candidate -- which `adjudication._finish` explicitly refuses to
    do, and then did by another route.

    MEASURED (2026-09-12): with a converter-folded block ahead of it, a
    withdrawing statement 300 characters in was served, judged `true` and the
    accusation removed; the same statement 900 characters in was cut out of a
    candidate that was still emitted, still `askable`, still batched and still
    paid for, three `false` verdicts came back about text that no longer
    contained it, and `premise_reading.json` recorded nothing. That is
    [[absence-must-be-representable]] at an artifact boundary.

    SO THE PASSAGE IS CUT INTO PIECES RATHER THAN TRUNCATED, each a contiguous
    word-boundary span of the document in its own right, and what does not fit
    in `cap` pieces is RETURNED AS A COUNT so the caller can say so.
    """
    s = " ".join(str(raw or "").split())
    out: list[str] = []
    at = 0
    while at < len(s) and len(out) < cap:
        if len(s) - at <= limit:
            out.append(s[at:])
            at = len(s)
            break
        cut = s.rfind(" ", at, at + limit)
        cut = cut if cut > at else at + limit
        out.append(s[at:cut])
        back = s.find(" ", max(at, cut - overlap))
        at = (back + 1) if 0 <= back < cut else cut
    return (out or [""]), max(len(s) - at, 0)


def _sentences_matching(text: str, rx: "re.Pattern[str]",
                        hay: _premises.Haystack) -> list[tuple[int, str]]:
    """`(offset, sentence)` for every sentence of `text` carrying `rx`.

    THE SENTENCE COMES OUT OF THE DOCUMENT, which is what makes the returned
    quote unforgeable: the model is never asked for a passage, so there is no
    channel by which one can be invented. Whitespace is collapsed by
    `Haystack.sentence`, exactly as it is for every account quote, and the result
    still locates through the fold `quotes.classify` applies.

    ONE DEFINITION, ON THE HAYSTACK: `premises` needs the same enumeration to ask
    its averaging veto of the whole paper, and two copies of "which sentences
    carry this pattern" is the drift this repo keeps paying for.
    """
    return hay.sentences_matching(rx)


def _bounds_clause(bounds: dict) -> str:
    """How the ACCOUNT records this variable's range, in words.

    THE QUESTION HAS TO NAME THE THING IT LICENSES. The target said only which
    variable was meant, so on `The supervisor rated lunchtime enjoyment and
    lunchtime noise on cards running from 0 to 6 and from 0 to 10 respectively`
    the model answered `true` for lunchtime noise -- correctly, about the 0-to-10
    range its own reason named -- and `index` applied that yes to the 0-to-6 the
    account had mis-split onto noise, because `numeral_in` is satisfied by the
    NEIGHBOUR's numerals in the same sentence. MEASURED TWICE on sonnet, in two
    independently composed batches: naming the declared range in the target flips
    both forms of the case to `false` ("Sentence gives noise range as 0-10, not
    the 0-6 the account claims"), while the honest control -- the same
    abbreviations block, asked about the variable whose range it does state --
    stays `true`.

    This is the pre-filter's own wiring, not a change to the prompt template: the
    E1 instrument (`PREAMBLE`/`ITEM`/`TAIL`/`SCHEMA`/`QUESTIONS`) is untouched.
    """
    lower, upper = bounds.get("lower"), bounds.get("upper")
    if lower is not None and upper is not None:
        return f"the account records its range as {lower} to {upper}"
    if lower is not None:
        return f"the account records its lowest possible value as {lower}"
    if upper is not None:
        return f"the account records its highest possible value as {upper}"
    return ""


def _variable_target(var: dict, bounds: dict | None = None) -> str:
    name = _one_line(var.get("name") or var.get("label") or var.get("id"), 120)
    parts = [p for p in (_one_line(var.get("derivation"), 120),
                         _bounds_clause(bounds) if bounds else "") if p]
    return f"the variable {name!r}" + (f" ({'; '.join(parts)})" if parts else "")


def _printed_context(values: list[dict], captions: dict[str, str]) -> str:
    """How this variable's numbers are PRINTED -- the half of the step question
    the sentence cannot answer.

    THE COLUMN BAND AND THE CAPTION ARE THE EVIDENCE FOR THE UNIT, and a table
    cell has no sentence of its own to carry it. `Total steps recorded,
    thousands` over a cell of 143.98 is a paper reporting whole steps in
    thousands, and nothing about the granularity sentence says so.
    """
    bits: list[str] = []
    for v in values[:3]:
        loc = v.get("location") or {}
        band = _one_line(loc.get("col_label"), 80)
        cap = _one_line(captions.get(str(loc.get("table_id") or "")), 160)
        unit = _one_line(v.get("units"), 30)
        piece = f"{v.get('statistic') or 'value'} {str(v.get('printed'))[:24]}"
        if band:
            piece += f" under the column heading {band!r}"
        if unit:
            piece += f" with units {unit!r}"
        if cap:
            piece += f", in a table captioned {cap!r}"
        if not band and not cap and v.get("quote"):
            piece += f", in the sentence {_one_line(v.get('quote'), 200)!r}"
        bits.append(piece)
    if not bits:
        return ""
    return "As printed in the paper: " + "; ".join(bits) + "."


def _bound_candidates(var: dict, mine: list[dict], hay: _premises.Haystack,
                      captions: dict[str, str],
                      sents: list[tuple[int, str]]) -> list[dict]:
    """Candidates for one variable's stated range.

    ONLY WHERE THE ACCOUNT DECLARES A BOUND. The NUMBERS are the account's and
    the model may not supply one, so a variable with no declared bound has
    nothing to establish and is not asked about -- which is also what keeps the
    call small.
    """
    b = _premises.field_dict(var, "bounds")
    if str(b.get("source") or "") not in _premises.BOUND_SOURCE_OF:
        return []
    lower, upper = b.get("lower"), b.get("upper")
    if lower is None and upper is None:
        return []
    ctx = _printed_context(mine, captions)
    # WHAT THIS CANDIDATE ASKED ABOUT, recorded beside the question rather than
    # only rendered into it. `index` admits a bound licence only where the pair
    # asked about is still the pair the account declares, which is the same move
    # the quote already gets one line later: re-derived from the artifact, so a
    # verdict that answered a DIFFERENT question -- an older reading, a changed
    # account -- cannot license this one.
    asked = [lower, upper]
    target = _variable_target(var, b)
    out: list[dict] = []
    quote = b.get("quote")
    if quote and hay.locate(quote)["located"]:
        out.append({"premise": "bound", "variable_id": var.get("id"),
                    "source": "account_quote", "quote": _clip(quote),
                    "asked_bounds": asked, "target": target, "context": ctx})
    picked = 0
    for _, sent in sents:
        if picked >= MAX_TEXT_CANDIDATES:
            break
        if out and sent == out[0]["quote"]:
            continue
        # A BOUND CANDIDATE HAS TO PRINT THE BOUND. The model may not supply a
        # number, so a sentence that does not carry the account's own numeral
        # could never admit anything and is not worth a line of the prompt.
        if not (_premises.numeral_in(sent, lower) or _premises.numeral_in(sent, upper)):
            continue
        if _premises.anchor_score(var, _premises._sentence_words(sent)) < 0.5:
            continue
        out.append({"premise": "bound", "variable_id": var.get("id"),
                    "source": "served_text", "quote": _clip(sent),
                    "asked_bounds": asked, "target": target, "context": ctx})
        picked += 1
    return out


def _step_candidates(var: dict, mine: list[dict], hay: _premises.Haystack,
                     captions: dict[str, str],
                     sents: list[tuple[int, str]]) -> list[dict]:
    """Candidates for one variable's per-subject step of 1.

    ONLY WHERE THE ACCOUNT DECLARES A STEP OF 1, for the same reason
    `_bound_candidates` needs a declared bound: the step is the account's number.
    """
    gran = _premises.field_dict(var, "granularity")
    if gran.get("per_subject_step") != 1:
        return []
    ctx = _printed_context(mine, captions)
    out: list[dict] = []
    quote = gran.get("quote")
    if quote and hay.locate(quote)["located"]:
        out.append({"premise": "step", "variable_id": var.get("id"),
                    "source": "account_quote", "quote": _clip(quote),
                    "target": _variable_target(var), "context": ctx})
    picked = 0
    for _, sent in sents:
        if picked >= MAX_TEXT_CANDIDATES:
            break
        if out and sent == out[0]["quote"]:
            continue
        if _premises.anchor_score(var, _premises._sentence_words(sent)) < 0.5:
            continue
        out.append({"premise": "step", "variable_id": var.get("id"),
                    "source": "served_text", "quote": _clip(sent),
                    "target": _variable_target(var), "context": ctx})
        picked += 1
    return out


def _averaging_candidates(var: dict, mine: list[dict], hay: _premises.Haystack,
                          others: list[dict], captions: dict[str, str],
                          sents: list[tuple[int, str]],
                          passages: list[str] = ()) -> list[dict]:
    """Candidates for "each subject's own value is itself an average".

    THE WITHDRAWING QUESTION, asked of the sentences the granting question is
    already asked of. `_step_candidates` surfaces a sentence and asks whether it
    ESTABLISHES a whole-number step; a `false` there withdraws nothing, so the
    sentence that says the quantity is a mean of two ratings could be shown to
    the model and still license the step. This asks the other question of it.

    ONLY WHERE THE VOCABULARY DID NOT ALREADY REFUSE, the same rule
    `_estimator_candidates` follows and for the same reason: a refusal premise
    can only be ADDED, so a variable `premises.AVERAGED` has already vetoed
    cannot be moved by a verdict and is not worth a line of the prompt. That is
    also what keeps the cost near zero on the papers the vocabulary handles.

    THE POOL IS NOT "SENTENCES THAT NAME THE VARIABLE". That test is the
    LICENCE's, and reusing it here reproduced the vocabulary's own blind spot one
    layer up: an anaphoric averaging sentence (`The reported figure is the mean
    of the pair.`) names nothing, so the model was offered ZERO candidates in all
    six of round 11's phrasings and could not have withdrawn the premise however
    well it read. A sentence that names no declared variable is admitted where
    the DISCOURSE resolves it to this one, and the table's own caption and
    footnotes are admitted as passages, which is where a house-style statement
    of this premise actually sits.
    """
    gran = _premises.field_dict(var, "granularity")
    if gran.get("per_subject_step") != 1:
        return []
    if _premises.averaging_statements(var, hay, others, passages):
        return []
    if _premises.derivation_reports_an_average(var):
        return []
    ctx = _printed_context(mine, captions)
    target = _variable_target(var)
    declared = [var] + [o for o in others
                        if str(o.get("id")) != str(var.get("id"))]
    vid = str(var.get("id"))
    pool: list[tuple[int, int, str, str]] = []
    for off, sent in sents:
        if _premises.anchor_score(var, _premises._sentence_words(sent)) < 0.5:
            if _premises._names_a_declared_variable(sent, declared):
                continue
            if vid not in _premises._antecedent_ids(hay, off, declared):
                continue
        # THE NARROW SHAPE A JUDGEMENT WOULD USE RANKS FIRST. See
        # `MAX_REFUSAL_CANDIDATES`: the cap is a filter for a refusal, so the
        # order has to be evidence and not position.
        rank = 0 if _premises.AVERAGED.search(sent) else 1
        pool.append((rank, off, sent, "served_text"))
    for i, passage in enumerate(passages):
        rank = 0 if _premises.AVERAGED.search(passage) else 1
        pool.append((rank, -len(passages) + i, passage, "printed_context"))
    out: list[dict] = []
    for _, _, quote, source in sorted(pool, key=lambda row: (row[0], row[1])):
        if len(out) >= MAX_REFUSAL_CANDIDATES:
            break
        out.append({"premise": "averaging", "variable_id": var.get("id"),
                    "source": source, "quote": _clip(quote),
                    "target": target, "context": ctx})
    return out


def _estimator_groups(values: list[dict], captions: dict[str, str],
                      statement: str | None,
                      weighting: str | None,
                      furniture: dict[str, str] | None = None,
                      *, gate: bool = True) -> tuple[list[dict], dict[str, list]]:
    """`(one candidate row per column of table furniture, the ids the vocabulary
    left standing)`.

    TWO RECALL NETS, ONE DEFINITION OF WHAT A GROUP IS. The survivor filter, the
    `(band, caption, footnote, own sentence, kind)` grouping and the target
    string it builds are wanted by BOTH the vocabulary-gated generator below and
    by `adjudication.estimator_candidates`, which admits the same furniture with
    no vocabulary test at all. Copying them would be the 44-same-name-groups
    problem this repo already pays for, so the only thing the two callers differ
    by is `gate`.

    `gate` IS THE ONLY DIFFERENCE, AND IT IS RECALL ONLY. With it, a column whose
    furniture carries no `_ESTIMATOR_CANDIDATE` word is not offered; without it,
    every surviving column is. Neither setting can change WHO SURVIVES: the two
    vocabulary judges run before the gate, so a value a rule already refused is
    absent from `survivors` either way and cannot be reached by any verdict.
    """
    groups: dict[tuple, dict] = {}
    survivors: dict[str, list] = {"mean": [], "percentage": []}
    for v in values:
        stat = str(v.get("statistic") or "")
        lit, _ = _premises.literal_of(v)
        is_pct = _premises._is_percentage(v, lit)
        if stat != "mean" and not is_pct:
            continue
        if stat == "mean" and _premises.estimated_mean_reason(v, captions, statement,
                                                               furniture):
            continue
        if is_pct and _premises.weighted_percentage_reason(v, lit, captions, weighting,
                                                            furniture):
            continue
        survivors["percentage" if is_pct else "mean"].append(v.get("id"))
        loc = v.get("location") or {}
        band = _one_line(loc.get("col_label"), 120)
        cap = _one_line(captions.get(str(loc.get("table_id") or "")), 240)
        note = _one_line((furniture or {}).get(str(loc.get("table_id") or "")), 240)
        own = "" if loc.get("kind") == "table_cell" else _one_line(v.get("quote"), 400)
        blob = " ".join(x for x in (band, cap, note, own) if x)
        # A COLUMN WITH NO FURNITURE AT ALL HAS NOTHING TO ASK ABOUT. Under the
        # gate this was implicit -- no text, no match -- and ungated it has to be
        # said, or a table cell with no band and no caption becomes a candidate
        # whose quote is the empty string.
        if not blob:
            continue
        if gate and not _ESTIMATOR_CANDIDATE.search(blob):
            continue
        key = (band, cap, note, own, "percentage" if is_pct else "mean")
        rec = groups.setdefault(key, {
            "premise": "estimator", "variable_id": None, "value_ids": [],
            "source": "printed_context",
            "quote": _clip(" | ".join(x for x in (band, cap, note, own) if x)),
            "band": band, "caption": cap, "kind": "percentage" if is_pct else "mean",
        })
        rec["value_ids"].append(v.get("id"))
    out: list[dict] = []
    for key in sorted(groups, key=lambda k: (str(k[3]), str(k[0]), str(k[1]))):
        rec = groups[key]
        n = len(rec["value_ids"])
        where = []
        if rec["band"]:
            where.append(f"the column heading {rec['band']!r}")
        if rec["caption"]:
            where.append(f"the table caption {rec['caption']!r}")
        rec["target"] = (f"the {n} {rec['kind']} value(s) printed under "
                         + (" and ".join(where) or "this passage"))
        rec["context"] = ""
        out.append(rec)
    return out, survivors


def _estimator_candidates(values: list[dict], captions: dict[str, str],
                          statement: str | None,
                          weighting: str | None,
                          governing: list[tuple[int, str]] = (),
                          furniture: dict[str, str] | None = None) -> list[dict]:
    """Candidates for "this number is not a plain total over n".

    ONLY WHERE THE VOCABULARY DID NOT ALREADY REFUSE. A verdict here can only
    ADD a refusal, so a value the strict regex has already refused cannot be
    changed by one and is not worth asking about. What is left is the recall
    gap: a paper naming its estimator in words `NOT_A_SIMPLE_MEAN` and
    `WEIGHTED_PERCENTAGE` do not carry. `furniture` (table footnotes, by table
    id) is passed to the SAME two vocabulary calls `value_premise` uses, so a
    value already refused through a footnote (wave 7d) is not re-offered here.

    ONE CANDIDATE PER COLUMN, NOT PER CELL. The evidence is the band, the caption
    or a governing sentence -- all of which are shared by every cell under them
    -- so a table of 143 weighted percentages is one question, not 143.

    AND THE FOURTH PLACE WAS NOT IN THE NET. `premises.named_estimator` reads
    five places for the paper's statement about its own estimator -- the band,
    the caption, the table's FOOTNOTES, the value's own sentence, and a
    GOVERNING SENTENCE of the paper's -- and this generator read three (now
    four, with the footnote), so a paper whose Methods sentence the narrow
    `_ESTIMATOR_STATEMENT` misses could not even be ASKED about: measured at
    zero candidates for all six of round 10's F5 phrasings. The served text's
    own governing sentences are now candidates too, one per statistic kind,
    because that statement governs every such value in the paper and not one
    column of it.

    AND THE `_ESTIMATOR_CANDIDATE` GATE IS STILL HERE, WHICH IS THE POINT OF
    KEEPING THIS GENERATOR. Round 17 measured what it costs -- four ordinary
    phrasings of a survey-weighted mean that produce ZERO candidates, so no paid
    pass can rescue them -- and answered it in `adjudication`, ungated, behind
    its own flag. This path is unchanged so the two nets stay comparable.
    """
    out, survivors = _estimator_groups(values, captions, statement, weighting,
                                       furniture)
    seen = {r["quote"] for r in out}
    # ORDERED BY EVIDENCE, NOT BY POSITION. See `MAX_REFUSAL_CANDIDATES`: four
    # ordinary introduction sentences merely CONTAINING `adjusted` or `weighted`
    # took every slot ahead of the Methods sentence that names the estimator, and
    # a premise the model is never shown is a premise it cannot withdraw. A
    # sentence carrying one of the two narrow JUDGING vocabularies goes first.
    ranked = sorted(
        ((0 if (_premises.NOT_A_SIMPLE_MEAN.search(sent)
                or _premises.WEIGHTED_PERCENTAGE.search(sent)
                or _premises._ESTIMATOR_STATEMENT.search(sent)) else 1, off, sent)
         for off, sent in governing),
        key=lambda row: (row[0], row[1]))
    picked = 0
    for _, _, sent in ranked:
        if picked >= MAX_REFUSAL_CANDIDATES:
            break
        quote = _clip(sent)
        if quote in seen or not _GOVERNS_REPORTED.search(sent):
            continue
        seen.add(quote)
        picked += 1
        for kind in ("mean", "percentage"):
            ids = survivors[kind]
            if not ids:
                continue
            out.append({
                "premise": "estimator", "variable_id": None, "value_ids": list(ids),
                "source": "served_text", "quote": quote,
                "band": "", "caption": "", "kind": kind,
                "target": (f"the {len(ids)} {kind} value(s) this paper reports"),
                "context": ""})
    return out


def _correction_candidates(values: list[dict], text: str,
                           hay: _premises.Haystack) -> list[dict]:
    """Candidates for "the paper has withdrawn this number".

    ONLY WHERE THE VOCABULARY DID NOT ALREADY WITHDRAW IT, and only for a number
    the notice actually prints. A correction notice does not withdraw every
    number in a paper, and the numeral test is what keeps that true: the
    candidate is the notice sentence that carries THIS value's printed literal.
    """
    notices = _sentences_matching(text, _CORRECTION_CANDIDATE, hay)
    if not notices:
        return []
    groups: dict[tuple, dict] = {}
    for v in values:
        lit, _ = _premises.literal_of(v)
        if lit is None:
            continue
        if _premises.withdrawn_by_a_correction(v):
            continue
        own = str(v.get("quote") or "")
        for _, sent in notices:
            if not _premises.numeral_in(sent, lit["value"]):
                continue
            key = (sent, lit["value"])
            rec = groups.setdefault(key, {
                "premise": "correction", "variable_id": None, "value_ids": [],
                "source": "served_text",
                "quote": _clip(sent),
                "target": f"the number {str(v.get('printed'))[:24]}",
                "context": "",
            })
            rec["value_ids"].append(v.get("id"))
            break
        else:
            if own and _CORRECTION_CANDIDATE.search(own):
                key = (own, lit["value"])
                rec = groups.setdefault(key, {
                    "premise": "correction", "variable_id": None, "value_ids": [],
                    "source": "account_quote",
                    "quote": _clip(own),
                    "target": f"the number {str(v.get('printed'))[:24]}",
                    "context": "",
                })
                rec["value_ids"].append(v.get("id"))
    return [groups[k] for k in sorted(groups, key=lambda k: (str(k[0]), float(k[1])))]


def candidates(account: dict, text: str = "") -> list[dict]:
    """Every premise this paper offers a model, in a deterministic order.

    THE PRE-FILTER'S JOB IS RECALL AND ITS COST IS ONE PROMPT LINE. Nothing here
    decides anything: a candidate is a QUESTION, and the answer can only move a
    premise within the bounds the module docstring states.
    """
    hay = _premises.Haystack(text)
    variables = _premises.readable_variables(account)
    by_var_id = _premises.variables_by_id(variables)
    values = [v for v in (account.get("values") or []) if _premises.well_formed(v) is None]
    captions = _premises._captions(account)
    #: TABLE FURNITURE (wave 7d), by table id, beside `captions` -- the same
    #: channel `premises.value_premise` reads for the free path, so the model
    #: is not asked about a value the vocabulary already refused via a
    #: footnote, and so a value the vocabulary CANNOT decide from its footnote
    #: alone is still offered.
    furniture = _premises.table_footnotes(account)
    by_variable: dict[Any, list[dict]] = {}
    for v in values:
        by_variable.setdefault(v.get("variable_id"), []).append(v)
    bound_sents = _sentences_matching(text, _BOUND_CANDIDATE, hay)
    step_sents = _sentences_matching(text, _STEP_CANDIDATE, hay)
    averaging_sents = _sentences_matching(text, _AVERAGING_CANDIDATE, hay)
    estimator_sents = _sentences_matching(text, _ESTIMATOR_CANDIDATE, hay)
    out: list[dict] = []
    for var in variables:
        if var.get("id") not in by_var_id:
            continue
        mine = by_variable.get(var.get("id")) or []
        out += _bound_candidates(var, mine, hay, captions, bound_sents)
        out += _step_candidates(var, mine, hay, captions, step_sents)
        out += _averaging_candidates(var, mine, hay, variables, captions,
                                     averaging_sents,
                                     _premises.table_passages(account, mine))
    out += _estimator_candidates(values, captions,
                                 _premises.estimator_statement(text),
                                 _premises.weighting_statement(text),
                                 estimator_sents, furniture)
    out += _correction_candidates(values, text, hay)
    for i, c in enumerate(out, 1):
        c["id"] = f"cand:{i}"
        c["question"] = QUESTIONS[c["premise"]]
        # ONE SHAPE FOR EVERY CANDIDATE. A licence names a variable and a
        # refusal names values; both fields exist on both, so a reader of the
        # artifact never has to know which generator wrote a row.
        c.setdefault("variable_id", None)
        c.setdefault("value_ids", [])
        c.setdefault("asked_bounds", None)
        loc = hay.locate(c["quote"])
        c["quote_located"] = bool(loc["located"])
        c["quote_not_located_because"] = loc["why"]
        # A LICENCE CANDIDATE WHOSE PASSAGE DOES NOT LOCATE IS NOT ASKED ABOUT.
        # It is the same refusal `_annotate_quotes` makes of a model's own
        # quote, one step earlier: a passage we cannot find in the served text
        # cannot license anything, and asking would put an unlocatable sentence
        # in a docket. A REFUSAL candidate is exempt because its evidence is
        # often table furniture -- a column band or a caption, which the
        # document layer holds and the body text does not contain -- and a
        # verdict on it can only ever remove a check.
        c["askable"] = c["quote_located"] or c["premise"] not in LICENCE_PREMISES
    return out


# --------------------------------------------------------------------------
# The call
# --------------------------------------------------------------------------


def build_prompt(cands: list[dict]) -> str:
    """The batched prompt for one call. `PREAMBLE`/`ITEM`/`TAIL` unchanged."""
    parts = [PREAMBLE]
    for i, c in enumerate(cands, 1):
        raw = str(c.get("context") or "").strip()
        ctx = (raw + "\n") if raw else ""
        parts.append(ITEM.format(i=i, target=c["target"], context=ctx,
                                 sentence=c["quote"], question=c["question"]))
    parts.append(TAIL.format(n=len(cands)))
    return "\n".join(parts)


def _reuse(name: str, out: Path, prompt: str) -> dict | None:
    """A saved reply to THIS EXACT PROMPT, or None.

    The comparison is the prompt's own bytes rather than a timestamp or a
    version: a pre-filter that surfaced a different candidate set wrote a
    different prompt, and its old answers address candidates that are no longer
    at those positions.
    """
    saved = _passes.load_pass(name, out)
    if saved is None:
        return None
    p = out / f"{name}.prompt.md"
    try:
        if p.read_text(encoding="utf-8") != prompt:
            return None
    except OSError:
        return None
    meta = dict(saved.get("meta") or {})
    # A REUSED REPLY COSTS NOTHING, and the record has to say so rather than
    # bill the run a second time for a call it did not make.
    meta["cost_usd"] = 0.0
    meta["reused"] = True
    return {**saved, "meta": meta}


def _address(got: list[dict], n: int) -> tuple[dict[int, dict], str]:
    """`({position: verdict}, why the join is not the numbers)` for one reply.

    THE MODEL'S OWN NUMBER IS AN ADDRESS OR IT IS NOTHING, and which of the two
    it is has to be decided for the WHOLE reply rather than row by row. MEASURED
    on jamanetworkopen.2023.37679, the live 12-candidate call: the model answered
    candidates 1-6, skipped 7-11, and answered 12 -- seven objects numbered
    `[1,2,3,4,5,6,12]`. Read positionally that is one mis-addressed verdict and
    FIVE candidates recorded as unanswered when six were; read by its own
    numbers it is exactly what it says, six answers and five genuine gaps.

    So the numbers are used when they can be an addressing: distinct, in range,
    and no more of them than there are candidates. Otherwise position is the
    join, which is what catches the dangerous shape -- a reply whose numbering
    has slipped by one would address every verdict to the wrong candidate, and
    under a positional join every one of them mismatches and is dropped rather
    than silently moving a premise on a quantity nobody asked about.
    """
    nums = [v.get("candidate") for v in got if isinstance(v, dict)]
    usable = (len(got) <= n and all(isinstance(x, int) and 1 <= x <= n for x in nums)
              and len(set(nums)) == len(nums))
    if usable:
        return {int(v["candidate"]): v for v in got if isinstance(v, dict)}, ""
    out: dict[int, dict] = {}
    bad = 0
    for i, v in enumerate(got[:n], 1):
        if not isinstance(v, dict):
            bad += 1
            continue
        if v.get("candidate") not in (None, i):
            bad += 1
            continue
        out[i] = v
    why = (f"the reply's own candidate numbers are not an addressing of the {n} "
           f"candidates asked ({nums[:12]}...), so position is the join and "
           f"{bad} verdict(s) that disagree with their position were dropped"
           if bad or len(got) > n else "")
    return out, why


def _budget_scope(c: Any) -> tuple[str, str]:
    """The unit a per-paper cut may not starve: one premise of one variable."""
    got = c if isinstance(c, dict) else {}
    return (str(got.get("premise")), str(got.get("variable_id")))


def _over_budget(asked: list[dict], budget: int | None) -> tuple[list[dict], list[dict]]:
    """`(asked within budget, never asked)`, cut ROUND-ROBIN ACROSS SCOPES.

    THE CUT MAY NOT BE ORDERED BY POSITION, for the reason
    `MAX_REFUSAL_CANDIDATES` already gives one level down -- "a cap ordered by
    POSITION is a filter after all" -- and `adjudication._stratified` is the same
    argument applied to ranks. Here the stratum is the SCOPE: `asked` arrives
    grouped, every candidate of one variable together, so `asked[:budget]` would
    spend the whole budget on the variables that happen to sort first and ask
    NOTHING about the rest. Round-robin instead, one per scope per turn, so every
    scope loses its weakest candidates before any scope loses all of them. Within
    a scope the order is untouched -- the nets already ranked it by evidence, and
    the strongest passage for each variable is exactly what a truncated budget
    should keep.

    FAILS CLOSED IN THE ONLY SENSE AVAILABLE TO IT, AND THE LIMIT IS WORTH
    STATING. It stops asking rather than truncating a call or raising: nothing
    downstream sees a half-answered chunk, and the run completes. What it CANNOT
    do is make an unasked question safe, because these are refusal nets and an
    unasked refusal leaves a check RUNNING. So the cut is recorded rather than
    absorbed, and `read` puts the count, the scopes and the direction of the loss
    in the record the account carries.

    THE KEPT ROWS COME BACK IN DOCUMENT ORDER, WHICH IS WHAT KEEPS A PAID
    READING PAID. `_reuse` matches a saved reply on the prompt's BYTES, so any
    reshuffle of the candidate list repays for every call in the paper. The
    result is therefore built by FILTERING the input by index and never by
    appending in pick order: the round-robin decides who survives and has no say
    in what order they are asked. `adjudication._stratified` is built the same
    way for the same reason.

    A budget of None, or one no smaller than the set, cuts nothing and returns
    the set unchanged. That guard is a SHORTCUT AND NOT THE ORDER-PRESERVATION
    MECHANISM -- measured: deleting it fails no test, because the filter above
    preserves order on its own.
    """
    n = len(asked)
    if budget is None or budget >= n:
        return list(asked), []
    if budget <= 0:
        return [], list(asked)
    by_scope: dict[tuple[str, str], list[int]] = {}
    for i, c in enumerate(asked):
        by_scope.setdefault(_budget_scope(c), []).append(i)
    keep: set[int] = set()
    order = list(by_scope)
    while order and len(keep) < budget:
        for scope in list(order):
            if len(keep) >= budget:
                break
            queue = by_scope[scope]
            keep.add(queue.pop(0))
            if not queue:
                order.remove(scope)
    return ([c for i, c in enumerate(asked) if i in keep],
            [c for i, c in enumerate(asked) if i not in keep])


def _unasked_summary(over: list[dict]) -> list[dict]:
    """WHICH premises and WHICH variables went unasked, one row per scope.

    A summary rather than the rows themselves: the cut set can be thousands of
    candidates, and what a reader has to be able to do is name the premise and
    the variable whose question was never put -- not re-read the passages that
    were never sent. Every cut candidate also carries `asked: False` and its own
    reason in `candidates`, so nothing here is the only record of anything.
    """
    # THE ORIGINAL ID IS CARRIED, NOT PARSED BACK OUT OF THE KEY. `_budget_scope`
    # stringifies so a scope can be a dict key, and the obvious inverse --
    # reading `"None"` back as `None` -- would rename a variable whose id really
    # is the string "None". Keep what the candidate actually held.
    rows: dict[tuple[str, str], int] = {}
    original: dict[tuple[str, str], Any] = {}
    for c in over:
        scope = _budget_scope(c)
        rows[scope] = rows.get(scope, 0) + 1
        original.setdefault(scope,
                            c.get("variable_id") if isinstance(c, dict) else None)
    return [{"premise": scope[0], "variable_id": original[scope], "n_unasked": n}
            for scope, n in sorted(rows.items())]


def read(account: dict, text: str, out_dir: str | Path, *,
         model: str = DEFAULT_MODEL, timeout_s: int = 900,
         only: list[dict] | None = None,
         budget: int | None = MAX_CANDIDATES_PER_PAPER) -> dict:
    """Run the premise-reading pass and write `premise_reading.json`.

    ONE BATCHED CALL PER PAPER, chunked only at `MAX_PER_CALL`. Per-candidate
    isolation was measured at $0.22 a call on sonnet with no cache reuse between
    `claude -p` invocations, so fifty-eight isolated calls cost $13 where one
    batch costs $0.25 -- and E1 measured that batch composition does not move
    the verdicts (a deliberately interleaved defect/control batch agreed with
    the segregated ones on 19 of 20).

    `budget` IS A CANDIDATE COUNT, BECAUSE CANDIDATES ARE WHAT THE BILL COUNTS.
    All four recall nets reach the model through this one door, so this is where
    a per-paper cost ceiling belongs and the only place it can be enforced once
    for all of them. See `MAX_CANDIDATES_PER_PAPER` for the measured growth law
    and for why the default sits above every real figure on hand. `None` spends
    whatever the nets produce.

    AND IT FAILS CLOSED BY SAYING SO. Over budget, the run stops asking: it does
    not truncate a call, does not raise, and does not report a partial pass as a
    whole one. `budget_exhausted`, `n_unasked_over_budget` and `unasked` go in
    the record, every cut candidate carries `asked: False` with its reason, and a
    `problems` line states which way the loss falls -- an unasked REFUSAL is a
    check left running, not a check that came back clean. The distinction a
    reader needs is "asked and answered no" (a verdict in `verdicts`) versus
    "never asked" (a scope in `unasked`), and after this they are different
    fields rather than the same silence.

    THE COST IS REPORTED TWICE ON PURPOSE. `cost_usd` is what THIS invocation
    spent, with a reused reply costing nothing (`_reuse`); `cost_usd_total` is
    what the reading cost to produce, reused calls included. On a resumed run the
    first is 0.0 and the second is the real price of the artifact, and reporting
    only either one of them is a lie in one of the two directions.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cands = list(only) if only is not None else candidates(account, text)
    for c in cands:
        c.setdefault("askable", c.get("quote_located")
                     or c.get("premise") not in LICENCE_PREMISES)
    askable = [c for c in cands if c.get("askable")]
    dropped = [c for c in cands if not c.get("askable")]
    asked, over = _over_budget(askable, budget)
    for c in asked:
        # THE REASON IS CLEARED AND NOT ONLY THE FLAG. The same candidate list is
        # handed to `read` twice by anything comparing budgets, and a row cut by
        # the first budget would otherwise keep `not_asked_because:
        # budget_exhausted` while `asked` said True -- a row that reads as both.
        c["asked"] = True
        c.pop("not_asked_because", None)
    for c in dropped:
        c["asked"] = False
        c["not_asked_because"] = "quote_not_located"
    for c in over:
        c["asked"] = False
        c["not_asked_because"] = "budget_exhausted"
    rec: dict[str, Any] = {
        "schema": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION, "model": model,
        "n_candidates": len(cands), "n_asked": len(asked), "n_dropped": len(dropped),
        "budget": budget, "n_askable": len(askable),
        "n_unasked_over_budget": len(over), "budget_exhausted": bool(over),
        "unasked": _unasked_summary(over),
        "candidates": cands, "verdicts": [], "problems": [],
        "cost_usd": 0.0, "cost_usd_total": 0.0, "n_calls": 0, "n_calls_reused": 0,
        "projected_usd": projected_usd(len(asked)),
    }
    for c in dropped:
        rec["problems"].append(
            f"{c['id']}: dropped before the call -- its quote does not locate in the "
            f"served text ({c.get('quote_not_located_because')})")
    if over:
        scopes = rec["unasked"]
        variables = {r["variable_id"] for r in scopes}
        rec["problems"].append(
            f"BUDGET EXHAUSTED: {len(over)} of {len(askable)} askable candidate(s) were "
            f"never put to the model, because the per-paper budget is {budget} "
            f"candidate(s) (~${projected_usd(budget)} at {MAX_PER_CALL} a call). "
            f"{len(scopes)} scope(s) are short, over {len(variables)} variable(s) and "
            f"premise(s) {sorted({r['premise'] for r in scopes})}; `unasked` names each "
            f"one. A candidate that was never asked is NOT a premise the model "
            f"declined: every net here is a REFUSAL net, so an unasked candidate leaves "
            f"a check RUNNING that the model might have withdrawn. Raise the budget, or "
            f"read this as reduced coverage rather than as a clean pass.")
    for start in range(0, len(asked), MAX_PER_CALL):
        chunk = asked[start:start + MAX_PER_CALL]
        name = f"premise_reading_{start // MAX_PER_CALL + 1}"
        prompt = build_prompt(chunk)
        # A REPLY ALREADY PAID FOR IS REUSED, AND ONLY AGAINST THE PROMPT THAT
        # BOUGHT IT. The saved prompt is compared byte for byte, because a
        # verdict addresses a SLOT IN THIS CHUNK either way -- by its number or
        # by its position -- and joining last night's answers to this morning's
        # candidate set is the shape that moves a premise on a quantity nobody
        # asked about. A changed pre-filter therefore pays again, which is the
        # honest price of having changed it.
        res = _reuse(name, out, prompt) or _passes.run_pass(
            name, prompt, out, model=model, schema=SCHEMA, timeout_s=timeout_s)
        rec["n_calls"] += 1
        rec["cost_usd"] = round((rec["cost_usd"] or 0)
                                + (res["meta"].get("cost_usd") or 0), 6)
        # WHAT THE ARTIFACT COST TO PRODUCE, WHICH A RESUMED RUN WOULD OTHERWISE
        # LOSE. `_reuse` zeroes `meta["cost_usd"]` so this invocation is not
        # billed twice, and is right to; but the reading is then a file that
        # cannot say what it cost, and "$0.00" beside fifty verdicts reads as a
        # free instrument. The saved meta still carries the price that was paid,
        # so both facts are recorded and neither stands in for the other.
        if res["meta"].get("reused"):
            rec["n_calls_reused"] += 1
        paid = (_passes.load_pass(name, out) or {}).get("meta") or {}
        rec["cost_usd_total"] = round((rec["cost_usd_total"] or 0)
                                      + (paid.get("cost_usd")
                                         or res["meta"].get("cost_usd") or 0), 6)
        rec["problems"] += [f"{name}: {p}" for p in res.get("problems") or []]
        got = list((res.get("data") or {}).get("verdicts") or [])
        by_position, why = _address(got, len(chunk))
        if why:
            rec["problems"].append(f"{name}: {why}")
        for i, c in enumerate(chunk, 1):
            v = by_position.get(i)
            if v is None:
                rec["problems"].append(f"{c['id']}: no verdict returned")
                continue
            rec["verdicts"].append({
                "candidate_id": c["id"], "premise": c["premise"],
                "establishes": bool(v.get("establishes")),
                "reason": _one_line(v.get("reason"), 200),
                "model": model, "prompt_version": PROMPT_VERSION})
    (out / "premise_reading.json").write_text(
        json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    return rec


def load(out_dir: str | Path) -> dict | None:
    """A premise reading already on disk, or None."""
    p = Path(out_dir) / "premise_reading.json"
    if not p.is_file():
        return None
    try:
        got = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return got if isinstance(got, dict) else None


def attach(out_dir: str | Path) -> bool:
    """Write the reading on disk into `account.json` as its `premise_reading`
    block, so a re-check of an existing run consults it.

    THE SAME MOVE `--review` MAKES, for the same reason: the account is what
    every downstream reader loads, and a pass that ran after it was written has
    to reach the readers through it.
    """
    out = Path(out_dir)
    reading = load(out)
    acc = out / "account.json"
    if reading is None or not acc.is_file():
        return False
    account = json.loads(acc.read_text(encoding="utf-8"))
    account["premise_reading"] = reading
    acc.write_text(json.dumps(account, indent=1, ensure_ascii=False), encoding="utf-8")
    return True


# --------------------------------------------------------------------------
# The index a stamp consults
# --------------------------------------------------------------------------


def _rows(block: Any, field: str) -> list:
    """One list off a block that anyone may have written.

    A MALFORMED READING IS LOST COVERAGE, NEVER THE RUN. `premise_reading.json`
    is loaded off disk and `attach()` writes it into `account.json`, so every
    shape a hand-edited or half-written file can have arrives here -- and
    `for x in block.get("verdicts") or []` raises `TypeError` on a scalar, out of
    `premises.stamp`, which is the FIRST statement of `checks.evaluate` and sits
    outside every per-candidate try/except. No checks, no refusals and no
    `checks.json` were written at all. `premises.well_formed` says the same thing
    about values and gives the reason: a field this package iterates has to be
    checked for being iterable, on the TYPE rather than on a list of names.
    """
    got = block.get(field) if isinstance(block, dict) else None
    return got if isinstance(got, list) else []


def _same_number(a: Any, b: Any) -> bool:
    """Are these two the same declared bound? `None` matches only `None`."""
    if a is None or b is None:
        return a is None and b is None
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _asks_the_declared_premise(c: dict, var: dict) -> bool:
    """Did this candidate ask about the premise the account NOW declares?

    THE QUESTION IS RE-DERIVED FROM THE ARTIFACT, exactly as the quote is. A
    `bound` verdict is an answer about ONE range -- the one `_bounds_clause` put
    in its target -- and a reading is a file on disk that outlives the account it
    was taken against. A verdict that answered about a different range is not
    evidence in either direction, so it neither grants the bound nor withdraws
    it; the vocabulary decides, which is where the premise sat before the pass
    ran. Only `bound` carries a number to check: a `step` candidate exists only
    where the declared step is 1, so its question cannot have been about another.
    """
    if str(c.get("premise")) != "bound":
        return True
    asked = c.get("asked_bounds")
    b = _premises.field_dict(var, "bounds")
    return (isinstance(asked, list) and len(asked) == 2
            and _same_number(asked[0], b.get("lower"))
            and _same_number(asked[1], b.get("upper")))


def _by_candidate(reading: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for c in _rows(reading, "candidates"):
        if isinstance(c, dict) and c.get("id"):
            out[str(c["id"])] = c
    return out


def index(reading: Any, hay: _premises.Haystack,
          by_var_id: dict[str, dict]) -> dict:
    """`{bound, step, estimator, correction}` lookups for `premises.stamp`.

    EVERY QUOTE IS RE-LOCATED HERE, against the text the stamp is running on and
    not the text the pass ran on. The reading is an artifact on disk and an
    account is a file anyone can edit; re-locating is what makes a forged block
    cost nothing it could not already have had, because the only passages it can
    ever offer are real sentences of the served document.

    AND A LICENCE STILL HAS TO CARRY ITS OWN NUMBER. A `bound` verdict is
    admitted only for the side whose numeral the located sentence prints
    (`numeral_in`), so a model cannot supply a bound by agreeing with a sentence
    that does not contain one.

    AND IT HAS TO BE AN ANSWER TO THE QUESTION THE ACCOUNT IS ASKING NOW. A bound
    candidate records the pair it asked about (`asked_bounds`); a verdict whose
    candidate asked about a different pair is counted (`n_stale_question`) and
    dropped, in both directions, so the vocabulary decides -- which is where the
    premise sat before the pass ran. See `_asks_the_declared_premise`.
    """
    empty = {"bound": {}, "step": {}, "estimator": {}, "correction": {},
             "averaging": {}, "varying_n": {}, "discreteness_attachment": {},
             "n_verdicts": 0, "n_applied": 0, "n_quote_refused": 0,
             "n_stale_question": 0,
             "prompt_version": None, "model": None}
    if not isinstance(reading, dict):
        return empty
    cands = _by_candidate(reading)
    out = dict(empty)
    out["bound"], out["step"] = {}, {}
    out["estimator"], out["correction"], out["averaging"] = {}, {}, {}
    out["varying_n"], out["discreteness_attachment"] = {}, {}
    out["prompt_version"] = reading.get("prompt_version")
    out["model"] = reading.get("model")
    licences: dict[tuple[str, str], list[dict]] = {}
    for v in _rows(reading, "verdicts"):
        if not isinstance(v, dict):
            continue
        c = cands.get(str(v.get("candidate_id")))
        if c is None or c.get("premise") not in PREMISES:
            continue
        out["n_verdicts"] += 1
        if not _asks_the_declared_premise(c, by_var_id.get(str(c.get("variable_id"))) or {}):
            out["n_stale_question"] += 1
            continue
        quote = str(c.get("quote") or "")
        premise = str(c["premise"])
        located = hay.locate(quote)["located"]
        # THE RE-LOCATION IS REQUIRED WHERE A VERDICT CAN GRANT SOMETHING, AND
        # NOT WHERE IT CAN ONLY TAKE SOMETHING AWAY. A licence rests on the
        # paper having said a thing, so the passage has to be the paper's. A
        # refusal premise's evidence is often TABLE FURNITURE -- a column band
        # or a caption, which the document layer holds and the served body text
        # does not contain -- and a wrong one there costs a check and cannot buy
        # an accusation, so requiring location would only lose coverage.
        if premise in LICENCE_PREMISES and not located:
            out["n_quote_refused"] += 1
            continue
        rec = {"establishes": bool(v.get("establishes")), "quote": quote,
               "reason": str(v.get("reason") or ""), "candidate_id": c.get("id"),
               "source": c.get("source"), "quote_located": located,
               "model": v.get("model"), "prompt_version": v.get("prompt_version")}
        # WHAT THE ANSWER DOES, BESIDE WHAT THE MODEL SAID. `establishes` is the
        # model's literal answer to the question it was asked; `withdraws` is
        # what this layer does with it, and the two differ for exactly the
        # premises in `WITHDRAWN_ON_FALSE`. Both are kept because a reader of a
        # docket has to be able to see the answer AND the decision -- and
        # because a consumer reading the wrong one of them must fail open, which
        # only holds while the literal answer is still there to be read.
        rec["withdraws"] = withdraws(premise, rec["establishes"])
        if premise in LICENCE_PREMISES:
            licences.setdefault((premise, str(c.get("variable_id"))), []).append(rec)
        elif rec["withdraws"]:
            # A REFUSAL PREMISE MOVES ONLY ON THE WITHDRAWING ANSWER, which is
            # `true` for five of the six and `false` for the one asked the
            # premise question itself (`WITHDRAWN_ON_FALSE`). See the module
            # docstring: a model may never remove a refusal a vocabulary made.
            #
            # `averaging` IS KEYED BY VARIABLE, NOT BY VALUE, because the premise
            # it withdraws -- a per-subject step of 1 -- is a property of the
            # variable and is where `granularity_verification` looks for it.
            #
            # `varying_n` IS KEYED BY VALUE, like `estimator` and `correction`,
            # because what it withdraws is THIS value's denominator: `group_n`
            # reads `analysis_n_varies` off the value being checked, and the same
            # variable can be reported at two coordinates whose n rows differ.
            #
            # `discreteness_attachment` IS KEYED BY VARIABLE FOR `averaging`'S OWN
            # REASON and is in the same branch rather than in a second copy of the
            # test: what it withdraws is the per-subject step of 1, which is a
            # property of the variable. See `VARIABLE_KEYED_REFUSALS`.
            if premise in VARIABLE_KEYED_REFUSALS:
                out[premise][str(c.get("variable_id"))] = rec
                out["n_applied"] += 1
                continue
            for vid in _rows(c, "value_ids"):
                out[premise][str(vid)] = rec
                out["n_applied"] += 1
    for (premise, vid), recs in licences.items():
        var = by_var_id.get(vid) or {}
        yes = [r for r in recs if r["establishes"]]
        if premise == "bound":
            b = _premises.field_dict(var, "bounds")
            yes = [r for r in yes
                   if _premises.numeral_in(r["quote"], b.get("lower"))
                   or _premises.numeral_in(r["quote"], b.get("upper"))]
            yes.sort(key=lambda r: -(int(_premises.numeral_in(r["quote"], b.get("lower")))
                                     + int(_premises.numeral_in(r["quote"], b.get("upper")))))
        if yes:
            out[premise][vid] = yes[0]
        else:
            # THE ACCOUNT'S OWN QUOTE IS THE ONE WHOSE REFUSAL IS REPORTED, when
            # it was asked about: it is the sentence the reader will look for.
            own = [r for r in recs if r.get("source") == "account_quote"]
            out[premise][vid] = dict((own or recs)[0], establishes=False)
        out["n_applied"] += 1
    return out
