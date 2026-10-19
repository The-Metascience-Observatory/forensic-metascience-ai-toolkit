"""The admission decision, computed once and written on the account.

WHY THIS MODULE EXISTS. Six readers of the account's `values` table
(`applicability`, `coverage`, `review`, `render`, `export`, `checks`) each
decided independently whether a value was safe to use, from the same seven raw
facts (`source`, `quote_verified`, `printed_in_quote`, `id_check`,
`printed_form`, `statistic_disputed`, `location.col_label`). They disagreed:
three different `quote_verified` admission rules lived under `scaffold/` alone,
two different `CORROBORATED` constants, two different quote locators. The newest
reader -- `checks.py`, the first whose output can accuse someone -- reinvented
five of those judgements weakly rather than importing the versions this codebase
already had. Two adversarial rounds then found the same five places again,
because tightening a heuristic (a length threshold, a vocabulary regex, a
column-label string) does not change its kind.

So the judgement is made HERE, once, and stamped on the account:

    value.premise      = {provenance, binding, literal, descriptive, disputed,
                          reasons}
    value.n_premise    = {provenance, binding, positive, source, ...}   (n rows)
    variable.bounds.verification
    variable.granularity.verification

and every reader becomes a LOOKUP. A reader that disagrees with the stamp is now
a visible defect rather than a second opinion nobody can see.

THE STAMP IS THE PIPELINE'S, NEVER THE MODEL'S. `PIPELINE_ONLY` is stripped from
every pass payload before assembly, exactly as `anatomy.PIPELINE_ONLY_FIELDS`
does for `provenance_verdict`, and for the identical reason: a verdict about
whether the model's own quote is real cannot be authored by the model.

WHAT A PREMISE MAY DO. Every rule here can only ever REMOVE a check (CLAUDE.md
8d, invariant 1: a derived boundary may narrow a premise, never supply one). The
three places that look like exceptions are named and bounded: `kind_necessary`
bounds (a count cannot go below zero) and `kind_necessary` discreteness (a count
moves in whole units), each admitted only where the declared kind makes the
premise logically necessary AND the paper's own printed values do not contradict
that kind; and `bounds_verification._shared_scale`, which lifts the attribution
tie only where the OTHER variable the sentence names claims the SAME number on
the same side from the same sentence, so both readings of the ambiguity admit
the same bound and nothing is supplied by choosing between them.

WHAT WAVE 7c ADDED, and each was a measured false accusation on an honest paper:
a granularity sentence that says the reported quantity is a MEAN of whole-point
observations establishes nothing about the average's own step (`AVERAGED`); a
percentage the paper says is weighted or standardised is not the printed count's
own quotient (`WEIGHTED_PERCENTAGE`); a caption naming an ESTIMATION PROCEDURE,
a whole header naming a model or a contrast, and the paper's own sentence about
a table each say the cell is a model output (`_MODEL_TABLE`, `_MODEL_HEADER`,
`table_notes`); and a paper that announces that its analysis n varies by measure
has withdrawn the group's n from every row of it (`varying_n_statement`).

WHAT WAVE 7d ADDED, and each was a measured false accusation on an honest paper:
the UNIT a number is printed in is read at last (`units_of`), because whole
minutes reported in hours and whole grams reported in kilograms were convicted by
every tool that rests on `mean * n` being an integer, while the identical account
in the recorded unit is `consistent`; a table's printed name may be a SUPPLEMENT
label (`Table S1`, `eTable 2`, `Appendix Table 1`), so the paper's own prose can
now withdraw a supplement's regression table as it always could a numbered one
(`_TABLE_LABEL`); a spelled-out number may run past ninety-nine
(`spelled_value`) and a cohort size may be a `count` in a table rather than an
`n` in the text (`CEILING_STATISTICS`), because the ALTERNATIVE-BASE ceiling that
excludes the paper's own base does not withdraw a check, it lets one accuse; the
served text is read for the FOURTH document-level statement it was never read for
-- how many units were analysed here (`analysed_counts`,
`analysis_unit_statement`); and a number the paper's own CORRECTION NOTICE
withdraws is no longer indistinguishable from one it reports
(`withdrawn_by_a_correction`).

WHAT WAVE 7e ADDED, AND IT IS ONE DEFECT WEARING TEN COATS: a guard that asks
its question of the WRONG HALF of the account. Round 7 built four fixtures that
are the same paper twice -- refused when the reading recorded one thing, and
GRIM `impossible` when it recorded another -- so each fix is the same move, of
asking the question where the paper actually answered it.

  * the unit is read from the COLUMN BAND and from the granularity sentence,
    not only from two fields a reading may truthfully leave null
    (`printed_unit`, `recorded_unit`);
  * the averaging veto reads WHOSE average it is, not what the constituents are
    called (`AVERAGED`), and the account's own `derivation` field is read at
    last (`DERIVED_AVERAGE`) -- it said `mean of the three monthly pill counts`
    while a step of 1 reached GRIM;
  * a table's printed name may sit anywhere in its caption's head and may put
    the number first (`S1 Table`, `Additional file 1: Table S1`);
  * a clause boundary is a contrastive conjunction as well as a semicolon
    (`_CLAUSE_BREAK`);
  * a DERIVED quantity whose derivation moves the range may not inherit its
    source's scale (`derived_range_changes`);
  * a numeral in a group's label is asked what it counts before it may
    corroborate a denominator (`numeral_counts_subjects`);
  * a percentage that rounds to zero pins no base, which is the strongest
    evidence there is that the base is not ours (`other_bases_that_fit`);
  * a number the sentence hands to another paper is not this paper's claim
    (`attributed_to_another_study`);
  * the ceiling on the paper's own cohort is read through four adjectives and a
    comma rather than two words (`_SUBJECT_COUNT`), and a wave is whatever the
    paper calls it (`_STAGE_PHRASE`);
  * and the VARIABLE table is finally held to the rule the value table has been
    held to since round 3: an id that cannot be a key is one skip
    (`well_formed_variable`), and two variables may not share one
    (`variables_by_id`).

WHAT THE MODEL-READ PREMISE PASS ADDED, AND IT IS A DIFFERENT KIND OF THING.
Every fix above widened a vocabulary, and six adversarial rounds then defeated
the widened one -- 6, 16 and 8 real false-accusation classes across rounds 6-8,
each a new honest phrasing of something a rule already almost recognised. There
is no bound on how many ways a paper can say a thing, so `scaffold/premise_reading`
demotes five of these vocabularies to CANDIDATE GENERATORS and has a model judge
whether a located sentence establishes the premise it was surfaced for. The
vocabularies keep their old job entirely when no such reading exists, which is
every paper the paid pass has not been run on: `bounds_verification` and
`granularity_verification` take an optional `verdict`, `value_premise` takes two
optional readings, and all four are None on the fallback path.

WHAT ROUND 10 ADDED, AND FOUR OF THE FIVE ARE ONE DEFECT: A GUARD WHOSE
DIRECTION MAKES AN UNDER-READING DANGEROUS. Each of these readers REFUSES when it
sees MORE, so every phrasing it cannot see is a check that RUNS and accuses --
the opposite of the usual failure mode in this module, where a vocabulary that
misses something costs coverage. `stated_ranges` counts the scales a sentence
states and the shared-scale lift fires when it sees one, so a second scale
printed any of seven ordinary ways hid itself and the lift came back
(`scale_claims`); `_CLAUSE_BREAK` carried a semicolon and four conjunctions, so
an em dash, a `--`, an en dash, a colon, a slash, a plain `, and` and a
`, which` relative clause each left two independent clauses as one and gave one
quantity's whole-unit claim to another; `_SUBJECT_COUNT` read a comma and nothing
else, so `1 240 members` put the ALTERNATIVE-BASE ceiling at 240 -- the TAIL of
the number (`_THOUSANDS_SEP`); and `_ESTIMATOR_STATEMENT` could not see
`weighted` inside `reweighted`, could not cross the hyphen of
`inverse-probability weighted`, and carried neither `raked` nor
`post-stratified`. Widening each of these is safe in a way widening a noun list
is not, and the argument is written at each pattern rather than assumed here.

THE FIFTH SURVIVES A PAID READING AND IS STRUCTURAL. Under a model `true` on the
step, `AVERAGED` is the ONLY guard left on the granted licence -- and every
question `premise_reading` asked was one that could only GRANT, so a model could
not withdraw a premise it was never shown. Both halves are fixed: the vocabulary
COUNTS the constituents instead of naming them (`the average of the two
observers`, `the midpoint of the two cards`, `added together and halved`), and
the withdrawing question is now asked as well, with the refusal polarity that
makes a wrong answer cost a check and never buy an accusation.

WHAT ROUND 11 ADDED, AND FIVE OF ITS SEVEN ARE ALSO ONE DEFECT: THE AVERAGING
VETO WAS HELD TO THE ATTRIBUTION RULES A LICENCE IS HELD TO. Those rules exist to
make a licence FAIL CLOSED -- the sentence must positively name the variable, in
the same clause, with no tie -- and a REFUSAL held to them FAILS OPEN. English
uses pronouns, so an averaging sentence names nothing (`The reported figure is
the mean of the pair.`); every separator round 10 added to save a licence also
DETACHED an averaging predicate from its own subject; a TIE in the attribution
heuristic dropped the veto entirely; and the veto was the one refusal that never
read a table's caption or footnote, which is exactly where a house style states
it. All four returned GRIM, GRIMMER and SPRITE `impossible` on an honest
half-point index, and the fix is one rule rather than four: a DEFINITION
(`<NP> is the mean of ...`) belongs to its subject, a PREDICATE ON THE
CONSTITUENTS (`the two cards were averaged`) belongs to whatever the passage is
about, an unattributed sentence is resolved against the DISCOURSE, and a tie no
longer takes a refusal away. See `_averaging_subject`, `_attribution` and
`averaging_statements`.

AND TWO MORE UNDER-READING GUARDS OF THE ROUND-10 SHAPE. `scale_claims` could not
count a scale stated as a POINT COUNT or as `out of 12`, so the shared-scale lift
came back -- closed by reading the scale's POSITION rather than by another list
of phrasings (`scale_sits_between`); and `_ESTIMATOR_STATEMENT` required its noun
BEFORE its copula, which is a constraint on word order and not on meaning, so
`Data are presented as roll-weighted means (SD).` was invisible. `_THOUSANDS_SEP`
is now defined by what a separator is NOT rather than by enumeration.

WHAT A READING MAY AND MAY NOT DO, because the asymmetry is the safety argument:
a LICENCE premise (a stated bound, a step of one) may be granted or withdrawn by
a reading, and every guard that can only remove one still runs beneath it -- the
quote must locate, the bound's own numeral must be in it, an averaging veto still
vetoes, and the paper's own printed values may still contradict it. A REFUSAL
premise (a named estimator, a correction notice, an averaging statement) may only
ever be ADDED by a reading, never removed, because removing one lets a check run
that a rule had already stopped. And the ALTERNATIVE-BASE ceiling (`paper_max_n`,
`other_bases_that_fit`, `_SUBJECT_COUNT`) is not read by a model at all: it is
the one premise whose dangerous polarity is a model saying `no`, and E1 measured
two models disagreeing on exactly that sentence.

WHAT ROUND 13 ADDED, AND THE FIRST IS A NEW SHAPE RATHER THAN ANOTHER ITEM ON AN
OLD LIST. `bounds_verification`'s vocabulary path asked two questions of a
bound's quote -- is it topically ABOUT this variable (`about_this_variable`,
bag-of-words), and does it PRINT the bound's numerals (`numeral_in`) -- and
never asked whether the sentence was making a range claim AT ALL. A fee-waiver
policy note sharing the word "courtesy" with `Courtesy Rating` and counting "0
to 6 first-time offenders" is topically about the right noun and prints both
declared numerals, and licensed a wrong 0-6 ceiling as `stated` -- the HARDEST
evidentiary tier -- against the paper's real 0-10 scale printed in a different
sentence the account did not point at. `granularity_verification` never had
this hole: it has always required the DISCRETENESS vocabulary in the located
clause before granting a step of 1. The bounds premise had no equivalent
content-TYPE gate, only a content-WORDS one, and `SCALE_ASSERTING` closes it the
same way: a bound admitted by the vocabulary path must also sit in a sentence
that reads as stating a range, a scale, a rating, a coding, or a minimum/maximum
-- which can only ever REMOVE a bound (invariant 1) and does not apply to a
model's reading, which has already answered the real question directly.

AND THE SECOND IS THE AVERAGING VETO'S TREADMILL, ONE MORE LAP. `AVERAGED`
still required one of a fixed set of OPERATOR words (mean, average, midpoint,
added together, summed, combined, totalled, divided by, halved) somewhere in
the sentence, and "Each member's overall promptness figure blends the fourteen
branch-level counts recorded for that member into one score" uses none of
them -- the verb `blends` carries the whole claim, and it is invisible to
`premise_reading._AVERAGING_CANDIDATE` too, so a paid pass is never even shown
the sentence. The fix is the shape branch 3 and 4 already point at: a per-
subject possessive (`each member's`, matching branch 3's own anchor, which is
what tells a per-subject average apart from an ordinary group-level total) that
names an explicit count of observations folded `into one score` (or figure,
value, index, number, measure, total, estimate) is an average of them however
the paper's verb names the fold. It is a VETO branch and can only ever cost a
check, never buy an accusation (invariant 1 for a refusal premise, which may
only be added by widening).

WHAT ROUND 21 ADDED, AND IT IS A CHANGE OF QUESTION RATHER THAN A LONGER LIST.
Round 19 closed three instances of one defect -- a discreteness word belonging to
an UNDECLARED quantity licensing a step on this variable -- by narrowing the one
noun-phrase member of the vocabulary, by adding a bare `while` to `_CLAUSE_BREAK`
and by cutting out a parenthetical with an auxiliary-headed subject. SIX more
phrasings of the same defect then returned GRIM `impossible` on an honest
half-point card, on the default path with no flag: the vocabulary's PREDICATE
members after `, and` or a bare `and` (`damaged packets were counted in whole
units`, `mainspring failures were recorded as integers`, `warden workload was
rated on a 7-point scale`) and parentheticals whose finite verb is LEXICAL rather
than one of `_FINITE_AUX`'s nine (`the wardens counted damaged packets in whole
units`). There is no bound on the separators and auxiliaries a paper can write,
and a LICENCE is the polarity where a reader that cannot see one MANUFACTURES an
accusation -- so the licence stopped asking where the clause ends and started
asking WHICH ASSERTION INSIDE IT the discreteness word belongs to. An assertion
carrying a subject of its own is about that subject, which must then be this
variable; one carrying no subject of its own is a predicate on its host clause
and is attributed exactly as before. An undeclared quantity in subject position
now fails BY CONSTRUCTION. `, and` is still not a `_CLAUSE_BREAK` member and does
not need to be: a segment boundary decides only where to look for a subject, so
this repo's canonical known-answer fixture keeps its licence. See
`assertion_segments`, `_assertion_subject` and `_discreteness_licence`; the cost
was measured at zero over eighteen honest phrasings, and the residue -- a
competing assertion with a lexical verb that is not one of the vocabulary's own
-- is pinned in `tests/test_scaffold_checks_round21.py::TestTheResidueIsNamed`.

WHAT ROUND 25 ADDED, AND IT IS THE ONE QUESTION NONE OF THE ABOVE ASKED. Every
round since the fourth asked WHOSE the discreteness claim is -- which clause,
which assertion, which constituent, which quantity. None asked whether the
sentence was MAKING the claim or DENYING it. `DISCRETENESS` is a keyword test,
`counted` matches inside `was not counted`, and a paper that states in its own
words that its measure is NOT recorded in whole units bought
`discreteness_source: stated` and was convicted by GRIM, GRIMMER and SPRITE
together -- eleven phrasings measured on the default path with no flag and no
model. This is the sharpest form the false accusation can take: in rounds 19, 21
and 22 the paper said something TRUE that was mis-attributed, and here the
paper's own disclosure that the premise does not hold is the thing that supplied
it. The guard is a scope rule rather than a NOT-list -- asked per vocabulary
match, backwards only, and only as far as the nearest polarity reset -- so
`... unlike Y, which was not` still licenses the quantity it is about. See
`_NEGATOR`, `_POLARITY_RESET` and `_denial_governing`; the sibling vocabularies
were audited in the same pass and are named in
`tests/test_scaffold_checks_round25.py::TestTheSiblingsAreNamedAndNotTouched`.
"""

from __future__ import annotations

import bisect as _bisect
import re
from typing import Any

from .. import prepass as _prepass
from .. import quotes as _quotes
from .. import sections as _sections
from . import bind as _bind
from . import interpret as _interpret

#: Fields the pipeline writes and the model may not. Stripped from every pass
#: payload before assembly. See `anatomy.PIPELINE_ONLY_FIELDS`, which this
#: mirrors deliberately: one rule, two vocabularies, both named.
PIPELINE_ONLY = frozenset({"premise", "n_premise", "verification"})


def strip_pipeline_only(node: Any) -> int:
    """Remove every `PIPELINE_ONLY` key anywhere in `node`, in place; count them.

    Recursive because a model may write `bounds.verification` as easily as a
    top-level `premise`, and a strip that only looked at the top level would
    leave the forgeable field exactly where the reader looks for it.
    """
    n = 0
    if isinstance(node, dict):
        for key in list(node):
            if key in PIPELINE_ONLY:
                del node[key]
                n += 1
            else:
                n += strip_pipeline_only(node[key])
    elif isinstance(node, list):
        for item in node:
            n += strip_pipeline_only(item)
    return n


# --------------------------------------------------------------------------
# The closed vocabularies -- ONE definition each, and this module owns them
# --------------------------------------------------------------------------

#: `id_check` outcomes that let a value's variable premises be used. AN
#: ALLOWLIST: a value is admitted only by exact membership, case-sensitive and
#: untrimmed, because `interpret` writes exactly these four tokens (`agrees`,
#: `disagrees`, `unjoined`, `join`) or `None` and nothing else can be a
#: corroboration we understand. `coverage.CORROBORATED` IS THIS OBJECT -- it is
#: imported there, not restated, which is what the ratchet in
#: `tests/test_scaffold_premises.py` enforces.
CORROBORATED = frozenset({"agrees", "join"})

#: The `id_check` token that CONTRADICTS the model's id. Named separately
#: because `coverage` counts it as a different tier from "not checked".
CONTRADICTED = "disagrees"

#: `id_check` outcomes that refuse a value for EVERY family. Kept as the NAMED
#: half of the vocabulary so a refusal can say which one it saw; the gate itself
#: is `CORROBORATED`, not this.
UNCORROBORATED = frozenset({"disagrees", "unjoined"})

#: `binding` vocabulary, closed.
BINDINGS = frozenset({"corroborated", "model_only", "contradicted", "unchecked"})

#: `value.source` -> the registry's `provenance`, for a value whose quote
#: verified. Anything not here is refused: a figure-derived value would map to
#: `measured_raster`, which GATE 2 refuses, and wave 5's schema has no field to
#: record one in the first place.
PROVENANCE_OF: dict[str, str] = {
    "table": "printed_table",
    "prose": "printed_text", "caption": "printed_text",
    "methods_parameter": "printed_text", "population": "printed_text",
}

#: `bounds.source` -> the registry's `bound_source`. AN ALLOWLIST, AND THE
#: MEMBERSHIP TEST IS THE GATE. Only `stated` and `definitional` let a number
#: through; `not_stated`, and every value outside this vocabulary, maps to
#: `assumed` AND passes no bound at all. It was a denylist and it failed open:
#: `source: "inferred"` with bounds 1-7 passed both numbers into GRIM, GRIMMER,
#: SPRITE and `check_sd_or_se` under a word that says we invented them.
BOUND_SOURCE_OF: dict[str, str] = {
    "stated": "stated", "definitional": "logically_necessary",
}
ASSUMED_BOUND_SOURCE = "assumed"

#: The `discreteness_source` tokens `tools.grim.HARD_DISCRETENESS_SOURCES`
#: accepts as licensing `impossible`. Named here so the two kinds of licence --
#: the paper's own sentence, and the kind's own logic -- are one vocabulary.
STATED_DISCRETENESS = "stated"
NECESSARY_DISCRETENESS = "logically_necessary"
ASSUMED_DISCRETENESS = "assumed"

#: `variable.kind` -> the bound each side takes BY DEFINITION of that kind. A
#: `definitional` bound is admitted without the paper printing its number only
#: where it is the bound the kind makes necessary: a count cannot go below 0, a
#: percentage of subjects cannot leave 0-100. `percentage_of_reference` is
#: deliberately absent -- a percentage OF a reference value routinely exceeds
#: 100 -- and so is `ordinal`, whose ends are the paper's choice.
NECESSARY_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "count": (0, None),
    "proportion": (0, 1),
    "binary": (0, 1),
    "percentage_of_subjects": (0, 100),
    "percentage_of_observations": (0, 100),
    "percentage_of_time": (0, 100),
}

#: `bounds_verification._side`'s outcomes that ADMIT a bound. `absent` is one
#: because a variable with one side declared is not failing the other; `stated`
#: is the paper's own sentence read by the vocabulary, `kind_necessary` the
#: kind's own logic, and `model_reading` the paper's own sentence read by a model
#: (wave 7c). Named as a set so that adding a way to admit a bound is one edit
#: rather than three string tuples that can drift apart.
_BOUND_ADMITTED = frozenset({"stated", "kind_necessary", "absent", "model_reading"})

#: The kinds whose DECLARED KIND alone makes a per-subject step of 1 logically
#: necessary. A count of things is a whole number of things whatever any
#: sentence says, and a yes/no coding is 0 or 1. NOTHING ELSE IS HERE, and
#: `integer_score` is the reason why: the word `integer` in a kind the MODEL
#: chose is the model's reading, not the paper's, and round 2 built its whole
#: first cluster out of a continuous measurement typed `integer_score`.
DISCRETENESS_NECESSARY_KINDS = frozenset({"count", "binary"})

#: ONE UNIT, EVERY WAY A PAPER SPELLS IT. The map exists so that a unit written
#: `min` on the variable and `minutes` on the value is ONE unit and costs no
#: check; anything not in it is compared on its own stem, so an unknown unit is
#: still compared against itself. It is a SYNONYM table and never a conversion
#: table: nothing here converts 6.77 h into 406 min, because a premise layer may
#: narrow a premise and never supply one (CLAUDE.md 8d, invariant 1).
_UNIT_FORMS: dict[str, str] = {
    "s": "second", "sec": "second", "second": "second",
    "min": "minute", "mins": "minute", "minute": "minute",
    "h": "hour", "hr": "hour", "hrs": "hour", "hour": "hour",
    "d": "day", "day": "day", "wk": "week", "week": "week",
    "mo": "month", "mon": "month", "month": "month",
    "y": "year", "yr": "year", "yrs": "year", "year": "year",
    "g": "gram", "gm": "gram", "gram": "gram", "gramme": "gram",
    "kg": "kilogram", "kilo": "kilogram", "kilogram": "kilogram",
    "mg": "milligram", "milligram": "milligram",
    "lb": "pound", "lbs": "pound", "pound": "pound",
    "mm": "millimetre", "millimetre": "millimetre", "millimeter": "millimetre",
    "cm": "centimetre", "centimetre": "centimetre", "centimeter": "centimetre",
    "m": "metre", "metre": "metre", "meter": "metre",
    "km": "kilometre", "kilometre": "kilometre", "kilometer": "kilometre",
    "ml": "millilitre", "millilitre": "millilitre", "milliliter": "millilitre",
    "l": "litre", "litre": "litre", "liter": "litre",
    "%": "percent", "pct": "percent", "percent": "percent",
    "percentage": "percent",
    "pt": "point", "point": "point", "score": "point",
}

#: The kinds whose values are percentages on a 0-100 scale. `proportion` is NOT
#: one: it is a fraction of one, and `check_count_percent` takes a percentage.
PERCENTAGE_KINDS = frozenset({
    "percentage_of_subjects", "percentage_of_observations",
    "percentage_of_time", "percentage_of_reference",
})

#: The percentage kinds whose BASE IS NOT A COUNT OF SUBJECTS, and so cannot be
#: the group's n. `check_count_percent` divides the printed count by the number
#: of SUBJECTS at the value's coordinate; a percentage of observations, of time,
#: or of a reference value is a percentage of something else, and the account
#: carries no denominator for it. Round 3's case: `31 attended at least ten of
#: the twelve scheduled sessions, and attendance averaged 82.5% of scheduled
#: sessions` -- two honest quantities, paired because they share a coordinate,
#: and 31/40 compared against a percentage of SESSIONS.
#:
#: `percentage_of_subjects` is deliberately absent, and so is every non-percentage
#: kind: demanding a percentage kind would refuse 109 honest cells on
#: jamanetworkopen.37679 alone, where the variable is `Age` (categorical) and the
#: column is the percentage in each band. This is a DENYLIST of kinds that
#: positively contradict the subject denominator, never an allowlist of kinds
#: that permit it.
NON_SUBJECT_PERCENTAGE_KINDS = frozenset({
    "percentage_of_observations", "percentage_of_time", "percentage_of_reference",
})

#: Statistics that are a VALUE OF THE VARIABLE, so that a printed one outside the
#: kind's necessary bounds contradicts the kind. A `count` is not one: a count of
#: 142 subjects sits on a `percentage_of_subjects` variable perfectly honestly.
VALUE_OF_VARIABLE_STATISTICS = frozenset({"mean", "median", "min", "max", "mode",
                                          "percentage"})

#: `value.statistic` words that name an estimate from a FITTED MODEL rather than
#: a description of a measured variable.
ESTIMATE_STATISTICS = frozenset({
    "coefficient", "effect_size", "ratio", "rate", "test_statistic", "score",
    "odds_ratio", "hazard_ratio", "risk_ratio", "slope", "loading",
})

#: The vocabulary in which a paper ESTABLISHES a per-subject step of 1. A
#: granularity quote must use it, because the claim the quote licenses is about
#: GRANULARITY and a sentence that says nothing about granularity establishes
#: nothing about it however true and however well located.
#: THE BARE NOUN `tally` IS NOT IN IT, AND THE VERB IS. `tall(?:y|ied)` matched
#: `tally sheet`, which names the INSTRUMENT a value was transcribed from and
#: says nothing about the granularity of the value: `Pool comfort was transcribed
#: from the observer's tally sheet, which was kept in whole units.` established a
#: per-subject step of 1 on a half-point card off the word `tally` alone -- and
#: it went on doing so after `_CLAUSE_BREAK` had correctly cut the relative
#: clause away, because the clause that SURVIVED was the one carrying the noun.
#: GRIM, GRIMMER and SPRITE `impossible` on an honest paper. The verb forms
#: (`tallied`, `tallying`) are a claim about how the values were made and stay.
DISCRETENESS = re.compile(
    r"\b(?:integers?|whole[\s‐-]+(?:number|numbers|point|points|unit|units|"
    r"event|events)|counts?|counted|counting|discrete|likert|tall(?:ied|ying)|"
    r"number\s+of|response\s+options?|\d+[\s‐-]*point\s+scale)\b", re.I)

#: THE ONE MEMBER OF `DISCRETENESS` THAT NAMES A QUANTITY INSTEAD OF DESCRIBING
#: ONE. Every other member is a PREDICATE or a MODIFIER -- `counted`, `tallied`,
#: `in whole points`, `Likert`, `7-point scale` all say how something was
#: recorded, and whatever the clause is about is what they are about. `number
#: of <X>` is a NOUN-PHRASE HEAD: it names a count of X, and it says nothing
#: about anything that is not X.
#:
#: ROUND 16 D3's FIRST LEAK, and it needs no clause boundary at all to reach a
#: false accusation. `Escapement grade was assigned on a 0 to 12 condition card,
#: and the number of mainspring failures at each overhaul was recorded.` names
#: the grade, carries `number of`, and `, and` is deliberately not a clause break
#: (see `_CLAUSE_BREAK`: adding it splits this repo's own canonical known-answer
#: fixture). So the phrase naming a DIFFERENT, UNDECLARED quantity licensed a
#: whole-number step on the grade and GRIM returned `impossible` on an honest
#: half-point card.
#:
#: THE FIX IS TO ASK THE PHRASE WHAT IT COUNTS, which is a question only this
#: member of the vocabulary can be asked, and to require the answer to be this
#: variable. `The number of falls per week was recorded` still licenses `Falls
#: per week`; it no longer licenses anything else in the sentence.
_NUMBER_OF = re.compile(r"\bnumber\s+of\b", re.I)

#: How many words after `number of` may name what is counted. Four is a noun
#: phrase with its modifiers (`the number of completed home visits`); more than
#: that and the sentence has moved on.
_COUNTED_WORDS = 4


def _discreteness_hits(passage: Any, var: dict):
    """Every vocabulary match in `passage` that could speak for `var`, paired
    with the denial that governs it (`None` where none does).

    ONE WALK, TWO QUESTIONS, because this repo's recurring defect is two
    spellings of one rule written at different times with only one of them moved
    (CLAUDE.md 8j). `discreteness_about` asks whether any match SURVIVES its
    denial; `discreteness_denial` asks which denial took the others away. Both
    read this.
    """
    text = str(passage or "")
    keep = _acronym_words(var)
    mine = {w for form in _name_forms(var) for w in _content(form, keep)}
    for m in DISCRETENESS.finditer(text):
        if _NUMBER_OF.fullmatch(m.group(0)):
            after = _interpret._words(text[m.end():m.end() + 80])[:_COUNTED_WORDS]
            if not (mine & set(_content(after, keep))):
                continue
        yield m, _denial_governing(text, m.start())


def discreteness_about(passage: Any, var: dict) -> bool:
    """Does `passage` state a granularity fact about THIS variable?

    `DISCRETENESS.search` with the one noun-phrase head answered rather than
    merely matched, and every match asked whether the paper was DENYING it. See
    `_NUMBER_OF`, and `_denial_governing` for the scope rule. Everything else in
    the vocabulary is a predicate and is left to the clause and attribution tests
    that already govern it -- both narrowings can only ever REMOVE a licence.

    `_denial_governing` is defined further down, beside the two boundary
    definitions it reuses rather than restates.
    """
    return any(said is None for _, said in _discreteness_hits(passage, var))


def discreteness_denial(passage: Any, var: dict) -> str | None:
    """The denial that took this passage's granularity claim away, or None.

    FOR THE RECORD, NOT FOR THE VERDICT. `discreteness_about` has already
    refused; this says WHICH WORDS did it, so a reader of a refusal can go and
    look at them. A refusal that names nothing is worth less than one that names
    the words it refused on -- the same argument round 22 makes for
    `discreteness_unresolved_constituent`.
    """
    return next((said for _, said in _discreteness_hits(passage, var) if said),
                None)


#: THE VOCABULARY THAT SAYS THE SUMMARISED QUANTITY IS AN AVERAGE OF SEVERAL
#: OBSERVATIONS, and so is NOT the whole-unit quantity the discreteness sentence
#: describes.
#:
#: WHY THIS EXISTS, and it is the sharpest false accusation round 4 found. The
#: gate above is a KEYWORD TEST FOR DISCRETENESS VOCABULARY and it ignores
#: everything else in the same span, so `the child's score is the mean of the
#: two assessors' whole-point ratings` -- a sentence whose only assertion is
#: that the reported quantity is a MEAN -- bought `discreteness_source: stated`
#: and returned GRIM, GRIMMER and SPRITE `impossible` on three ordinary
#: reporting conventions, each verified against real per-subject data:
#:
#:     a mean item score, 20 items rated 1-5   -> step 0.05, printed 3.03 (0.34)
#:     the mean of two whole-point raters 0-10 -> step 0.5,  printed 4.86 (2.13)
#:     the mean of three whole-count trials    -> step 1/3,  printed 6.28 (1.95)
#:
#: The paper's sentence is TRUE in every one of them: the RATINGS are whole
#: points. What it does not say -- and what GRIM needs -- is that the AVERAGE of
#: k of them is. The average of k whole numbers moves in steps of 1/k.
#:
#: IT IS DELIBERATELY NARROW IN TWO WAYS, because `a mean of 3.4 visits` is what
#: EVERY results sentence looks like and vetoing on that would cost the honest
#: papers this whole gate exists to keep. `mean of` must NOT be followed by a
#: numeral (that is a reported summary, not a definition), and it must name the
#: CONSTITUENTS that were averaged. So `attendance averaged 82.5% of scheduled
#: sessions` and `Body mass averaged 78.4 kg` are untouched, and `averaged` on
#: its own is admitted only where it takes an explicit object.
#:
#: A SUM IS NOT AN AVERAGE and is deliberately absent: the sum of k whole
#: numbers is a whole number, so a total score built from whole-point items
#: keeps its step of 1.
#:
#: AND THE NOUN LIST WAS THE WHOLE OF THE GENERAL BRANCH, WHICH IS WHY IT LOST.
#: Round 7 measured it: of twenty-eight nouns a paper actually averages over,
#: TWENTY-ONE evade -- `counts`, `visits`, `nights`, `sessions`, `days`,
#: `reviews`, `scores`, `results` among them -- and `Tablets were counted in
#: whole units, and each patient's adherence index is the mean of her three
#: monthly pill counts` returned GRIM, GRIMMER and SPRITE `impossible` on a
#: step-1/3 index, while the identical sentence saying `pill assessments`
#: refused. A longer list is not the fix; a list is the defect.
#:
#: SO THE SECOND AND THIRD BRANCHES ASK WHOSE AVERAGE IT IS, NOT WHAT WAS
#: AVERAGED. What separates the vetoed within-subject mean from the ordinary
#: group mean is not the constituents' NOUN -- it is that the average is defined
#: PER SUBJECT: `the mean of HER three monthly pill counts`, `EACH PATIENT'S
#: index IS THE MEAN OF ...`. A group mean is never written that way (`the mean
#: of the 28 patients`, `the mean of the children's scores` match neither), so
#: the branches cost nothing on the honest case this gate exists to keep, and
#: they are indifferent to what the constituents are called.
#: AND ROUND 10 DEFEATED THE NOUN LIST AGAIN, FOUR WAYS, on a comfort index that
#: is `(observer A + observer B) / 2` and so moves in HALF points: `the average
#: of the two observers` (the noun is `observers`, which is not one of the
#: eighteen), `the midpoint of the two cards` (the OPERATOR is not `mean` at
#: all), `added together and halved`, and `the arithmetic mean of the pair`. All
#: four returned GRIM `impossible`, on the vocabulary path AND under a real
#: sonnet `true` -- because under a model verdict this regex is the only guard
#: left on a granted step.
#:
#: SO THE FOURTH BRANCH COUNTS THE CONSTITUENTS INSTEAD OF NAMING THEM, which is
#: the same move branches two and three made and is why they have not lost: what
#: separates a per-subject average from a group mean is that the constituents are
#: a SMALL EXPLICIT NUMBER OF THEM (`of the two observers`, `of the pair`, `of
#: three trials`), and a group mean is not written that way. The cardinals are
#: SPELLED deliberately -- `the mean of the 28 patients` is exactly the honest
#: group mean this gate must not touch, and a paper writes its own n in digits.
#:
#: AND HALVING A PAIR IS AN AVERAGE WRITTEN AS ARITHMETIC. `added together and
#: halved` and `divided by two` say the same thing as `the mean of the two`, and
#: a paper that spells out the arithmetic is not making a different claim.
AVERAGED = re.compile(
    r"\b(?:mean|average)s?\s+(?:of|across|over)\s+(?![-+]?[\d.])"
    r"[^.;]{0,40}?\b(?:items?|ratings?|raters?|assessors?|judges?|coders?|"
    r"attempts?|trials?|responses?|administrations?|assessments?|"
    r"measurements?|observations?|readings?|replicates?|questions?|"
    r"indicators?)\b"
    # the average is taken over ONE SUBJECT'S OWN observations
    r"|\b(?:mean|average)s?\s+(?:of|across|over)\s+(?:the\s+|those\s+|all\s+)?"
    r"(?:her|his|its|each\s+[a-z]+(?:'s|’s)|every\s+[a-z]+(?:'s|’s))\b"
    # the reported quantity is DEFINED per subject as an average
    r"|\b(?:each|every)\s+[a-z]+(?:'s|’s)\b[^.;]{0,60}?\b(?:is|was)\s+"
    r"(?:the\s+|a\s+)?(?:mean|average)\s+(?:of|across|over)\b"
    # the constituents are a SMALL EXPLICIT NUMBER of per-subject observations,
    # whatever they are called and whatever the operator is called
    r"|\b(?:mean|average|midpoint|mid[-\s]?point)s?\s+(?:of|across|over|between)"
    r"\s+(?:the\s+|those\s+|all\s+|its\s+|her\s+|his\s+)?"
    r"(?:two|three|four|five|six|seven|eight|nine|ten|pair|couple|both)\b"
    r"|\b(?:was|were|are|is)\s+averaged\b"
    r"|\baverag(?:ed|ing)\s+(?:across|over|within|between)\b"
    r"|\bdivided\s+by\s+the\s+(?:number|total)\b"
    # the arithmetic of an average, spelled out
    r"|\b(?:added\s+together|summed|combined|totalled|totaled)\b[^.;]{0,30}?"
    r"\b(?:halved|averaged|divided\s+by\s+(?:two|2|the\s+number))\b"
    r"|\bdivided\s+by\s+(?:two|2)\b"
    # ROUND 13: THE CONSTITUENTS ARE COMBINED INTO ONE SCORE, WHATEVER VERB
    # DOES IT. "Each member's overall promptness figure blends the fourteen
    # branch-level counts recorded for that member into one score" carries no
    # operator word above at all -- `blends` is the whole claim. Kept to the
    # same per-subject possessive anchor as branch 3 (`each/every <noun>'s`),
    # because that is what tells a per-subject average apart from an ordinary
    # group-level total ("the four subscales were combined into one total
    # score" is usually an honest integer SUM and would be swept up here too;
    # refusing it costs a check rather than buying an accusation, which is the
    # safe side of invariant 1 for a veto that may only be added by widening).
    r"|\b(?:each|every)\s+[a-z]+(?:'s|’s)\b[^.;]{0,80}?\b(?:the\s+)?"
    r"(?:\d+|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"pair|couple|both)\b[^.;]{0,60}?"
    r"\binto\s+(?:a\s+|one\s+)(?:single\s+)?"
    r"(?:score|figure|value|index|number|measure|total|estimate)s?\b", re.I)

#: THE ACCOUNT'S OWN WORDS FOR HOW A VARIABLE IS COMPUTED, when they say it is
#: an AVERAGE of several things.
#:
#: READ BECAUSE IT WAS ALREADY THERE AND NOBODY LOOKED. `variable.derivation`
#: ("the formula in the paper's words, when the variable is computed from
#: others") said `mean of the three monthly pill counts` on the very account
#: whose step of 1 reached GRIM, and no line of `premises` or `checks` read
#: `derivation` or `derived_from`. In a DERIVATION FIELD the word `mean` is
#: unambiguous in a way it is not in prose -- the field describes how THIS
#: variable is built, so it cannot be the group mean of it -- which is why this
#: test can be a word where `AVERAGED` has to be a shape.
DERIVED_AVERAGE = re.compile(
    r"\b(?:mean|means|average|averages|averaged|averaging|midpoint|midpoints)\b"
    r"|\bmid[-\s]points?\b"
    r"|\bdivided\s+by\s+the\s+(?:number|total)\b"
    r"|\bdivided\s+by\s+(?:two|2)\b|\bhalved\b", re.I)

#: A SUM DIVIDED BY THE NUMBER OF ITS OWN TERMS.
#:
#: THE ONE PLACE A WORD LIST IS READING THE WRONG KIND OF INPUT, and round 16
#: found it: `schema.py` asks `variable.derivation` for "the formula in the
#: paper's words", and `DERIVED_AVERAGE` matches only the WORDS. An account that
#: records `Escapement grade = (card A + card B) / 2` -- the field used exactly
#: as the schema asks -- got no veto at all, and it is the ONE evasion in that
#: round with no rescue on any path: stage 1 reads the served text and the table
#: furniture, and no reader anywhere offers a model the derivation field.
#:
#: SO THIS IS NOT ANOTHER SYNONYM, IT IS THE FIELD'S OWN NOTATION. An arithmetic
#: mean written as arithmetic is a parenthesised sum of k terms over the literal
#: k, and the check is COUNTING, not matching: `(a + b) / 2` and `(a + b + c) /
#: 3` are averages, `(a + b) / 4` and `(a + b + c) / 2` are not and are left
#: alone. The prose half of round 16's D1 is NOT addressed here and deliberately
#: -- see `AVERAGED`, and `adjudication`, which already offers all ten of that
#: round's prose phrasings to a model.
_SUM_OVER_K = re.compile(r"\(\s*(?P<sum>[^()]{1,200}?)\s*\)\s*/\s*(?P<k>\d{1,2})\b")


def formula_reports_an_average(derivation: Any) -> str | None:
    """The part of a derivation that DIVIDES A SUM OF k TERMS BY k, or None."""
    text = str(derivation or "")
    for m in _SUM_OVER_K.finditer(text):
        terms = [t for t in m.group("sum").split("+") if t.strip()]
        if len(terms) >= 2 and len(terms) == int(m.group("k")):
            return m.group(0)
    return None


def derivation_reports_an_average(var: Any) -> str | None:
    """This variable's own `derivation`, when it says the variable is an average.

    ONE DEFINITION, AND THERE WERE THREE. `granularity_verification`,
    `premise_reading._averaging_candidates` and `adjudication.already_refused`
    each spelled `DERIVED_AVERAGE.search(str(var.get("derivation") or ""))` by
    hand, so a fourth reading of that field -- the formula one above -- would
    have had to be hand-copied into three places or silently reach only one of
    them. That is this repo's standing failure shape (`import one definition`),
    and the veto it governs is the last guard on a granted step.
    """
    text = str((var or {}).get("derivation") or "") if isinstance(var, dict) else ""
    if DERIVED_AVERAGE.search(text) or formula_reports_an_average(text):
        return text or None
    return None


#: A COLUMN HEADER THAT IS AN ESTIMATE SYMBOL, whole-label only.
#:
#: WHY THIS IS NOT ANOTHER STRING LIST. `prepass.reports_model_output` spells out
#: `hazard ratio`, `risk ratio` and `beta` as WORDS, so `HR (SE)`, `aHR (95% CI)`,
#: `RR (SE)`, `B (SD)` and the Greek letter all walked past it -- and its own
#: `_SE_COLUMN` needs a coefficient symbol immediately beside `(SE)`, so a
#: dispersion printed as `(SD)` or an interval printed as `(95% CI)` walked past
#: that too. The fix is not a longer list of substrings: it is to ask what the
#: WHOLE HEADER IS. A header that consists of an estimate symbol, optionally
#: adjusted/crude/weighted, optionally followed by the parenthetical that names
#: its own uncertainty, is a model output whatever letters the symbol uses. The
#: match is anchored at both ends, so `Mean (SD)` and `All participants` cannot
#: reach it, and a bare `b` -- too short to match safely as a SUBSTRING, which is
#: what `prepass`'s own comment says -- is safe as a WHOLE header.
_ESTIMATE_LABEL = re.compile(
    r"^\s*(?:(?:un)?adjusted|crude|weighted|pooled|standardi[sz]ed|partial|"
    r"standardized|unstandardized)?\s*"
    r"(?:a|adj\.?)?\s*"
    r"(?:b|β|β₁?|beta|est|estimate|coef|coeff|coefficient|hr|or|"
    r"rr|irr|aor|ahr|arr|airr|smd|wmd|md|slope|loading|"
    r"marginal\s+effect)"
    r"\s*(?:\([^)]*\))?\s*$", re.I)

#: AN ESTIMATE REPORTED IN PROSE, where there is no column and no caption to
#: read. `Mood predicted falls (B = 8.57, SE = 3.03, p = .005)` is the ajcp
#: mislabel in its prose form, and the column-and-caption guard is asked a
#: question with no evidence and answers None. A symbol bound to a number by an
#: `=` or a `:` is the paper's own notation for a fitted estimate.
_ESTIMATE_IN_PROSE = re.compile(
    r"(?<![A-Za-z])(?:a|adj\.?\s*)?"
    r"(?:b|β|beta|hr|or|rr|irr|smd|wmd|est|coef|coeff)"
    r"\s*[=:]\s*[-+−]?\d", re.I)

#: A TABLE THAT REPORTS A FITTED MODEL, named by the ESTIMATION PROCEDURE rather
#: than by the shape of the estimate.
#:
#: `prepass._MODEL_OUTPUT_CAPTION` reads three ways of saying it -- `regression`,
#: `associations with/between/of`, `predictors of` -- and round 4 walked past it
#: with the four commonest captions a clinical paper actually prints: `Mixed-
#: effects model for <outcome>`, `Multivariable model, <outcome>`, `Adjusted mean
#: difference in <outcome>` and `ANCOVA for <outcome>, adjusted for baseline`.
#: With any ordinary column header beside them, an honest coefficient 8.57 and
#: its standard error 3.03 reached GRIM as a mean and an SD of a 5-25 whole-point
#: outcome, and 8.57 x 48 = 411.36 is `impossible`.
#:
#: THE QUESTION IT ASKS IS NOT "does this string contain a keyword" BUT "does
#: this caption name a way of ESTIMATING something?" A model is named by its
#: procedure (mixed-effects, ANCOVA, Cox, GEE), by the word `model` itself, or by
#: the contrast it reports (`adjusted mean difference`, `least-squares means`).
#: None of those is how a paper captions a description of its sample.
_MODEL_TABLE = re.compile(
    r"\b(?:mixed[-\s]?effects?|multi[-\s]?level|multivariable|multivariate|"
    r"hierarchical|random[-\s]?effects?|fixed[-\s]?effects?|"
    r"anova|ancova|manova|mancova|"
    r"generali[sz]ed\s+(?:linear|estimating)|glmm?|gee|"
    r"logistic|poisson|negative\s+binomial|cox|proportional\s+hazards|"
    r"propensity|least[-\s]squares?\s+means?|(?:estimated\s+)?marginal\s+means?|"
    r"adjusted\s+(?:mean\s+)?difference|models?)\b", re.I)

#: A WHOLE COLUMN HEADER THAT NAMES A MODEL OR A CONTRAST rather than a measured
#: quantity. Same rule as `_ESTIMATE_LABEL` -- ask what the WHOLE HEADER IS, not
#: whether a substring appears in it -- applied to the headers a regression table
#: carries when it does NOT print an estimate symbol: a bare model number
#: (`(1)`, `Model 2`), the adjustment alone (`Adjusted`, `Crude`), the contrast
#: (`Difference`), or the comparison itself (`Intervention vs control`).
#:
#: A CONTRAST IS NOT A DESCRIPTION OF A MEASURED VARIABLE, which is why it
#: belongs here: `Intervention vs control` holds the difference between two
#: groups, and adjudicating it against the outcome's own scale is the same
#: category error as adjudicating a coefficient against it.
_MODEL_HEADER = re.compile(
    r"^\s*(?:"
    r"\(\s*\d+\s*\)"
    r"|(?:un)?adjusted|crude"
    r"|models?\s*\d*"
    r"|(?:(?:un)?adjusted\s+|crude\s+|between[-\s]group\s+|within[-\s]group\s+"
    r"|absolute\s+|mean\s+)*(?:difference|contrast)s?"
    r"|[^|]{1,40}\bv(?:s\.?|ersus)\b[^|]{1,40}"
    r")\s*(?:\([^)]*\))?\s*$", re.I)

#: The printed name of a table, taken from the FRONT OF ITS OWN CAPTION. The
#: account's `table_id` is an internal handle (`table:4`); what the paper's prose
#: says is `Table 4`, and the caption is where the two are joined.
#:
#: EVERY LABEL A SUPPLEMENT ACTUALLY CARRIES USED TO FAIL IT. The pattern was
#: `^(tables?|tab\.?)\s*([0-9]+[A-Za-z]?)`, so `Table 4`, `Table 4a` and `Tab. 2`
#: joined and `Table S1`, `eTable 2`, `Table A1`, `Supplementary Table 3` and
#: `Appendix Table 1` returned None -- the number is not `[0-9]+`, or the caption
#: does not START with the word `table`. `table_notes` is the ONLY channel by
#: which the paper's own PROSE can say that a table reports a fitted model, and
#: CLAUDE.md 8p makes supplements first-class inputs: a supplement is exactly
#: where a clinical paper puts its regression tables, so the one shape the note
#: channel exists for was the one shape it could not see. MEASURED: the same
#: account under `Table 4.` refuses 4 of 4 candidates (`reports_model_output`),
#: and under each of the five supplement labels ran 4 checks and returned 3
#: accusations -- a coefficient `8.58` and its standard error `3.03` adjudicated
#: as a mean and an SD of a 0-21 whole-point score. Fifteen false accusations
#: from a regex.
#:
#: BOTH HALVES ARE READ BACK OUT AND THE PROSE JOIN IS BUILT FROM WHAT THE
#: CAPTION ITSELF PRINTED, which is what keeps the labels apart: the qualifier
#: (`Supplementary`, `Appendix`, `Online`, the fused `e`) is part of the name, so
#: `Table 1` cannot borrow a sentence about `Table S1` and `eTable 2` cannot
#: borrow one about `Table 2`.
#: AND THE ANCHOR WAS THE NEXT THING TO FAIL. `^` reads a label only where the
#: caption STARTS with the word `table`, and two of the largest publishers do not
#: print it there: PLOS writes `S1 Table. ...` (the number BEFORE the word) and
#: BMC/Springer writes `Additional file 1: Table S1. ...` (the label after a file
#: prefix). Both conventions are in the working corpus (`pone.*`, `s12883-*`),
#: both returned None, and round 7 measured the cost -- six false accusations,
#: `8.58` and `3.03` from a supplement's mixed-effects model adjudicated as a
#: mean and an SD of a 0-21 whole-point score, while `Table 4.` and `Table S1.`
#: refuse 4 of 4.
#:
#: SO THE LABEL IS SEARCHED FOR IN THE CAPTION'S HEAD RATHER THAN MATCHED AT ITS
#: START, and the second alternative reads the number-first form. The head bound
#: is what keeps a caption that CROSS-REFERENCES another table (`... (see Table
#: 2)`) from claiming its name; and if one ever did, the only consequence is a
#: prose note attached to the wrong table, which can only REMOVE checks.
_TABLE_LABEL = re.compile(
    r"(?P<word>(?:(?:supplementary|supplemental|supporting|additional|"
    r"appendix|online|extended(?:\s+data)?|web)\s+)?e?tables?|tab\.?)"
    r"\s*(?P<num>[A-Za-z]{0,2}\s?[0-9]+[A-Za-z]?)\b"
    r"|(?P<pre_num>[A-Za-z]{1,2}\s?[0-9]+[A-Za-z]?)\s+(?P<pre_word>e?tables?)\b",
    re.I)

#: How far into a caption a table's own printed name may sit and still be its
#: name. `Additional file 1: Table S1` puts it at character 19.
_TABLE_LABEL_HEAD = 30

#: A PERCENTAGE THAT IS NOT THE PRINTED COUNT'S OWN QUOTIENT.
#:
#: THE STANDARD COMPLEX-SURVEY CONVENTION, and `check_count_percent` cannot
#: survive it: NHANES, BRFSS, NHIS and every age-standardised prevalence table
#: prints an UNWEIGHTED count beside a WEIGHTED percentage, and the two are not a
#: numerator and its own quotient. Round 4's case is 12 of 48 children with atopy
#: (25.0% unweighted) beside a weighted district prevalence of 31.4%: honest,
#: stated in the column label, in the caption and in Methods, and `suspicious` at
#: every one of them.
#:
#: `premises.other_bases_that_fit` does not rescue it -- a weighted percentage is
#: not a count over ANY integer base -- so the refusal has to read what the paper
#: says about its own estimator. Four places say it: the column band, the
#: caption, the value's own sentence, and a Methods sentence governing the
#: paper's percentages.
WEIGHTED_PERCENTAGE = re.compile(
    r"\b(?:survey[-\s]?|design[-\s]?|sampling[-\s]?)?weight(?:ed|ing)?\s*%"
    r"|\b(?:age|sex|design)?[-\s]?(?:standardi[sz]ed|adjusted)\s*%"
    r"|\b(?:weighted|standardi[sz]ed|adjusted)\s+"
    r"(?:percentage|percentages|percent|prevalence|prevalences|proportion|"
    r"proportions|estimate|estimates)\b"
    r"|\bpercent\w*\b[^.;\n]{0,40}?\b(?:are|were|was|is)\s+(?:\w+\s+){0,2}?"
    r"(?:weighted|standardi[sz]ed|age[-\s]adjusted|design[-\s]adjusted)\b",
    re.I)

#: A REPORTED MEAN THAT IS NOT AN INTEGER TOTAL DIVIDED BY n.
#:
#: GRIM, GRIMMER AND SPRITE ALL REST ON ONE PREMISE -- that the printed mean is
#: `(a sum of n whole-unit observations) / n` -- and a paper that computed a
#: DIFFERENT ESTIMATOR of the same quantity has withdrawn it. Five ordinary ones,
#: every number of them recomputed from a real 34-child integer dataset by the
#: estimator its own sentence names, were adjudicated `impossible`:
#:
#:     a survey-weighted mean            (every complex-survey paper alive)
#:     a mean pooled by Rubin's rules    (after multiple imputation)
#:     an ANCOVA least-squares mean      (adjusted for a covariate)
#:     a 10% trimmed mean
#:     the mean of the two school means  (a two-stage cluster estimate)
#:
#: SAME SHAPE AS `WEIGHTED_PERCENTAGE`, AND THAT IS THE POINT. That guard reads
#: five places for the paper's statement about its own estimator -- the column
#: band, the table's caption, the table's FOOTNOTES (wave 7d), the value's own
#: sentence, and a governing sentence of the paper's -- and
#: `weighted_percentage_reason` returned early unless the value was a
#: PERCENTAGE, so those places were read for one statistic and for nothing
#: else. All five are now read by `named_estimator`, which both guards call
#: with their own vocabulary; only the vocabulary differs.
#:
#: IT IS THE ESTIMATOR THAT IS NAMED, NEVER THE WORD `mean` ALONE. `Mean (SD)`
#: over a plain caption stays checkable -- it is the honest descriptive column
#: this whole family exists for -- and an estimator is recognized by an ADJECTIVE
#: the paper attaches to its own average, by the clause it opens with
#: (`Weighted to ...`, `Adjusted for ...`, `Pooled across ...`), or by the
#: two-stage form (`the mean of the two school means`). It can only ever REMOVE a
#: check (invariant 1).
NOT_A_SIMPLE_MEAN = re.compile(
    # an estimator adjective attached to the paper's own average
    r"\b(?:weighted|standardi[sz]ed|adjusted|least[-\s]squares?|ls|lsmeans?|"
    r"(?:estimated\s+)?marginal|trimmed|winsori[sz]ed|truncated|pooled|imputed|"
    r"bootstrap(?:ped)?|jack[-\s]?knifed?|geometric|harmonic|back[-\s]transformed|"
    r"predicted|fitted|model[-\s]based|covariate[-\s]adjusted)"
    r"\s+(?:mean|average)s?\b"
    # the same adjective attached to the ESTIMATES a table reports
    r"|\b(?:weighted|standardi[sz]ed|adjusted|trimmed|winsori[sz]ed|pooled|imputed|"
    r"bootstrap(?:ped)?)\s+(?:estimates?|values?|figures?)\b"
    # the clause a results sentence opens with
    r"|\bweighted\s+(?:to|for|by|using)\b"
    r"|\badjusted\s+for\b"
    r"|\bpooled\s+(?:across|over|using)\b"
    r"|\bstandardi[sz]ed\s+(?:to|for)\b"
    # the abbreviation a table band prints on its own
    r"|\bEMMs?\b|\bLSMs?\b"
    # a two-stage estimate: the mean OF the group means, not of the observations
    r"|\b(?:mean|average)s?\s+of\s+(?:the\s+)?(?:\w+[-\s]){0,3}?"
    r"(?:means|averages|medians)\b", re.I)

#: THE PAPER'S OWN GOVERNING SENTENCE ABOUT ITS MEANS, the fourth place.
#:
#: NARROWER THAN THE PER-VALUE VOCABULARY ON PURPOSE. This one is matched against
#: the WHOLE served document, so `adjusted for` anywhere in a Methods section
#: would withdraw every mean in the paper. It therefore requires the paper to say
#: it OF ITS MEANS OR ESTIMATES -- `the means below are the least-squares means`,
#: `All percentages and means in Table 2 are weighted to the school-district
#: population` -- which is a statement about what was reported, not a description
#: of a model somewhere in the paper.
#: AND SIX ORDINARY METHODS SENTENCES MISSED IT (round 10), every one of them
#: returning GRIM, GRIMMER and SPRITE `impossible` on an honest register-weighted
#: mean of whole-point cards. Three were the pattern's own machinery failing on
#: ordinary orthography -- `\bweighted` cannot see the word inside `reweighted`,
#: and the `(?:\w+\s+){0,3}?` gap between the noun and its adjective cannot cross
#: the hyphen of `inverse-probability weighted`; two named estimators the list
#: does not carry (`raked`, `post-stratified`) over a noun it does not carry
#: (`summary statistics`); and two said it without an `are`/`were` at all
#: (`Table 1 reports register-calibrated means.`, `Each swimmer contributes ...
#: in proportion to the size of her stratum`).
#:
#: THE ESTIMATOR ADJECTIVE IS NOW ONE FRAGMENT USED IN EVERY BRANCH, because the
#: three branches were three hand-copied lists and they had already drifted.
#: `marginal` IS NOT IN THE LOOSE FRAGMENT, and that is not an oversight: `the
#: differences in means were marginal` is ordinary English about SIZE, and
#: putting the word where the first branch can reach it would withdraw every mean
#: in such a paper. It is admitted only in the two branches whose context is
#: tight enough for it to mean an estimated marginal mean.
#:
#: AND EVERY BRANCH REQUIRED THE NOUN BEFORE THE COPULA, WHICH IS A CONSTRAINT ON
#: WORD ORDER AND NOT ON MEANING. Round 11 measured it: the commonest way a
#: Methods section or a structured abstract says this puts the noun in the
#: PREDICATIVE COMPLEMENT (`Data are presented as roll-weighted means (SD).`,
#: `Values are shown as adjusted means and standard deviations.`) or POSTMODIFIES
#: it (`Table 1 presents means adjusted for plot size.`), and all three returned
#: GRIM, GRIMMER and SPRITE `impossible` on an honest roll-weighted mean. The
#: fragment is now used in BOTH ORDERS around the quantity noun, which is a
#: grammatical widening rather than another list.
_ESTIMATOR_ADJ = (r"(?:[\w]+[-\s])?(?:(?:re|de)?weighted|standardi[sz]ed|"
                  r"adjusted|pooled|trimmed|winsori[sz]ed|imputed|bootstrapped|"
                  r"raked|calibrated|post[-\s]?stratified|least[-\s]squares?|"
                  r"shrunk(?:en)?|smoothed|penali[sz]ed|regulari[sz]ed)")
_ESTIMATOR_ADJ_TIGHT = r"(?:" + _ESTIMATOR_ADJ + r"|marginal)"
#: The quantities a paper reports and this guard is about.
_REPORTED_QUANTITY = (r"(?:means?|averages?|estimates?|statistics?|values?|"
                      r"figures?|percentages?|proportions?|rates?|data)")
_ESTIMATOR_STATEMENT = re.compile(
    r"\b(?:means?|averages?|estimates?|summary\s+statistics?)\b"
    r"[^.;\n]{0,60}?\b(?:are|were|is|was)\s+(?:[\w-]+\s+){0,3}?"
    + _ESTIMATOR_ADJ + r"\b"
    r"|\bthe\s+(?:mean|average)s?\s+(?:below|above|reported|presented|shown)\b"
    r"[^.;\n]{0,40}?\b(?:are|were)\b[^.;\n]{0,40}?\b" + _ESTIMATOR_ADJ_TIGHT + r"\b"
    # the paper says what a TABLE reports, with no copula at all -- in either
    # order, because `presents adjusted means` and `presents means adjusted for
    # plot size` are the same statement
    r"|\b(?:tables?|figures?)\s*[\w.]{0,4}\s*"
    r"(?:reports?|presents?|shows?|gives?|contains?)\b[^.;\n]{0,60}?"
    r"(?:\b" + _ESTIMATOR_ADJ_TIGHT + r"\s+" + _REPORTED_QUANTITY + r"\b"
    r"|\b" + _REPORTED_QUANTITY + r"\s+(?:[\w-]+\s+){0,2}?"
    + _ESTIMATOR_ADJ_TIGHT + r"\b)"
    # THE NOUN IN THE PREDICATIVE COMPLEMENT: `<quantity> are presented as
    # <estimator> <quantity>`, which is where a Methods section puts it
    r"|\b" + _REPORTED_QUANTITY + r"\b[^.;\n]{0,40}?\b(?:are|were|is|was)\s+"
    r"(?:presented|reported|shown|given|expressed|displayed|summari[sz]ed|"
    r"listed|tabulated)\s+as\s+(?:[\w-]+\s+){0,2}?"
    + _ESTIMATOR_ADJ + r"\s+(?:[\w-]+\s+){0,2}?" + _REPORTED_QUANTITY + r"\b"
    # THE PAPER NAMES AN ESTIMATOR. Whatever it is called, a quantity computed
    # with a named estimator is not a total divided by n, and the technical noun
    # never appears in `we averaged the scores`. The quantity list is the
    # narrower one here, because this branch is matched against the WHOLE served
    # document and one segment withdraws every mean in the paper.
    r"|\b(?:means?|averages?|estimates?|percentages?|proportions?|rates?|"
    r"statistics?)\b[^.;\n]{0,60}?"
    r"\b(?:estimator|estimation\s+(?:procedure|method|routine)|shrinkage)\b"
    # a weight described rather than named
    r"|\b(?:means?|averages?|estimates?)\b[^.;\n]{0,60}?"
    r"\bin\s+proportion\s+to\b", re.I)

#: THE PAPER'S OWN STATEMENT THAT ITS ANALYSIS n VARIES BY MEASURE.
#:
#: Item-level missingness is the commonest honest reason a real paper fails GRIM,
#: and papers say so -- `Sample sizes vary from 44 to 48 across measures owing to
#: missing responses` in a table footnote, or the same sentence in Methods. The
#: bridge binds the GROUP's n by position and nothing was reading that sentence,
#: so an honest mean of 46 whole-point scores was adjudicated at n = 48 and came
#: back `impossible` on GRIM, GRIMMER and SPRITE.
#:
#: `checks.BRIDGE_REASONS` already NAMED this gap -- `per_row_n_not_captured`,
#: declared as a premise the scaffold does not capture -- and this is the
#: evidence that makes it reachable: where the paper states the variation, the
#: group's n is not this row's denominator and no other n is available.
_N_VARIES = re.compile(
    r"\b(?:sample\s+sizes?|analytic\s+sample\s+sizes?|ns|n)\b\s*"
    r"(?:var(?:y|ies|ied)|differ(?:s|ed)?|rang(?:e|es|ed))\b"
    r"[^.;\n]{0,60}?\b(?:across|between|among|by|for|per|from)\b"
    r"[^.;\n]{0,60}?\b(?:measures?|outcomes?|variables?|items?|analyses|"
    r"analysis|scales?|questionnaires?|tests?|instruments?|domains?|"
    r"subscales?|endpoints?)\b", re.I)


# --------------------------------------------------------------------------
# The refusal codes this module's judgements produce
# --------------------------------------------------------------------------

#: reason code -> (premise slot, what it means). MERGED INTO `checks.REASONS`,
#: which stays the one closed vocabulary a refusal may draw on. They live here
#: because the JUDGEMENT lives here: the bridge adds no premise judgement of its
#: own after wave 7b, so it may not own the words for one either.
REASONS: dict[str, tuple[str, str]] = {
    "provenance_not_printed": ("provenance", "the value is not a table cell the "
                                             "paper printed nor located prose"),
    "binding_not_corroborated": ("binding", "the variable id the reading asserted "
                                            "disagrees with, or could not be checked "
                                            "against, the name join (`id_check`)"),
    "binding_model_only": ("binding", "the variable id rests on the model's reading "
                                      "alone (`id_check: null`); refused for "
                                      "variable-dependent families in wave 7 (D2)"),
    "reports_model_output": ("applicability", "the column band, the table's own caption, "
                                              "the cell's neighbours or the sentence "
                                              "itself say this is a model output, not a "
                                              "descriptive statistic of a measured "
                                              "variable"),
    "percentage_is_weighted": ("applicability", "the paper says this percentage is "
                                                "weighted, standardised or otherwise adjusted "
                                                "-- in the column band, the caption, the "
                                                "table's footnotes, the sentence itself, or a "
                                                "Methods sentence governing its percentages -- "
                                                "so it is not the printed count's own quotient "
                                                "and no denominator makes the two agree"),
    "mean_is_not_a_simple_average": ("applicability", "the paper names the estimator it used "
                                                      "for this mean -- in the column band, the "
                                                      "table's caption, its footnotes, the "
                                                      "value's own sentence, or a sentence "
                                                      "governing its means -- and it is not an "
                                                      "integer total divided by n, which is the "
                                                      "one premise GRIM, GRIMMER and SPRITE all "
                                                      "rest on"),
    "value_withdrawn_by_a_correction": ("applicability", "the value's own quote is the paper's "
                                                         "OWN CORRECTION NOTICE and this is the "
                                                         "number it withdraws (`premises."
                                                         "withdrawn_by_a_correction`), so it is "
                                                         "printed in the paper and is not one of "
                                                         "the paper's claims; the corrected value "
                                                         "beside it is untouched"),
    "value_attributed_to_another_study": ("applicability", "the value's OWN SENTENCE attributes "
                                                           "this number to another paper "
                                                           "(`reported by <Author>`, `of <Author> "
                                                           "et al.`), so it is printed in this "
                                                           "paper and is not one of its claims; "
                                                           "adjudicating it against THIS study's "
                                                           "n and scale is a category error "
                                                           "(`premises.attributed_to_another_"
                                                           "study`)"),
    "printed_in_another_unit": ("granularity", "the number is printed in a unit other than the "
                                               "one the variable declares (`value.units` against "
                                               "`variable.units`), and a per-subject step "
                                               "established for the RECORDED unit is not the step "
                                               "of the PRINTED number: whole minutes reported in "
                                               "hours move in sixtieths, and `mean * n` -- the "
                                               "one premise GRIM, GRIMMER and SPRITE all rest on "
                                               "-- is an arithmetic claim about the unit printed"),
    "statistic_kind_disputed": ("kind", "the account marks this cell `statistic_disputed`: "
                                        "the same column header and printed form was read "
                                        "as a different kind elsewhere in this paper, and a "
                                        "kind is this check's premise"),
    "printed_not_plain_numeral": ("literal", "the printed literal is not a bare number "
                                             "or percentage under the strict grammar"),
    "percent_sign_on_a_non_percentage": ("literal", "the literal carries a `%` and neither "
                                                    "the value's statistic nor the "
                                                    "variable's kind is a percentage, so "
                                                    "stripping the sign would invent a "
                                                    "number the paper did not print"),
    "step_missing": ("granularity", "the variable declares no per-subject step"),
    "step_not_one": ("granularity", "the per-subject step is not 1 (a mean of k items "
                                    "has granularity 1/(k*n) and these tools have no "
                                    "`items` parameter)"),
    "discreteness_assumed": ("granularity", "the step is 1, the kind does not make it "
                                            "necessary, and no located quote shows the "
                                            "PAPER establishes it; refused in wave 7 (D3)"),
    "discreteness_claim_is_denied":
        ("granularity", "the sentence offered as evidence for a per-subject step of 1 "
                        "DENIES whole-number granularity -- `was not counted in whole "
                        "units`, `never recorded as integers`, `in half points rather "
                        "than whole units` -- and a keyword test for the vocabulary read "
                        "the denial as the claim. A sentence that denies whole-number "
                        "granularity cannot establish it, so the licence is withheld "
                        "(round 25)"),
    "discreteness_claim_is_per_observation":
        ("granularity", "the sentence offered as evidence for a per-subject step of 1 "
                        "makes its whole-number claim PER SOMETHING OTHER THAN THE "
                        "SUBJECT -- `in whole points at each of three visits`, `by each "
                        "of two inspectors`, `as a whole number of quarter grades`. What "
                        "the paper established is that each OBSERVATION is a whole "
                        "number; the value printed for one subject aggregates or "
                        "rescales several of them and does not move in whole units "
                        "(round 26)"),
    "discreteness_assertion_boundary_unresolved":
        ("granularity", "the sentence offered for a per-subject step of 1 carries the "
                        "whole-unit words inside a constituent this reader could not "
                        "attribute -- a subordinate clause, an adjunct, an absolute or "
                        "an appositive, introduced by a comma and headed by nothing it "
                        "can identify. The words may belong to this variable or to a "
                        "quantity beside it, and a boundary that cannot be resolved may "
                        "not SUPPLY the premise it failed to narrow (round 22)"),
    "discreteness_licence_withdrawn_by_a_model":
        ("granularity", "a model was shown the passage the per-subject step of 1 was "
                        "granted on and read it as NOT showing that the figure the "
                        "paper reports for one subject is a whole number -- because its "
                        "whole-number words describe some other quantity, because the "
                        "paper takes whole-number recording away from this variable, or "
                        "because what it makes whole is one observation rather than the "
                        "reported figure -- so the licence the vocabulary granted is "
                        "withdrawn. The model's own words are in the detail. The verdict "
                        "can only ever WITHDRAW: no answer to that question grants or "
                        "restores a step the free path did not already grant (round 24, "
                        "widened in round 28, `adjudication_attach`)"),
    "discreteness_quote_reports_an_average": ("granularity", "the sentence offered as evidence "
                                                             "for a per-subject step of 1 says "
                                                             "the reported quantity is the MEAN "
                                                             "of several observations: the "
                                                             "whole-unit claim is about the "
                                                             "observations that were averaged, "
                                                             "and the average of k of them moves "
                                                             "in steps of 1/k"),
    "derivation_reports_an_average": ("granularity", "the ACCOUNT'S OWN `variable.derivation` "
                                                     "says this variable is COMPUTED as a mean "
                                                     "of several observations, so a per-subject "
                                                     "step of 1 is not its step however whole "
                                                     "the observations that were averaged "
                                                     "(`premises.DERIVED_AVERAGE`)"),
    "bound_stated_for_the_source_quantity": ("bounds", "the account declares this variable "
                                                       "DERIVED from another, and the sentence "
                                                       "offered for its bounds names only the "
                                                       "quantity it is derived FROM: a change "
                                                       "score is not on the level scale, and a "
                                                       "derived variable's name contains its "
                                                       "source's, so a partial name match is "
                                                       "the shape of the mis-attribution rather "
                                                       "than evidence against it"),
    "bounds_not_stated": ("bounds", "the variable's bounds are `not_stated`, and this "
                                    "family's verdict rests entirely on them"),
    "upper_bound_not_stated": ("bounds", "no upper bound is stated, and this family "
                                         "needs both"),
    "lower_bound_not_stated": ("bounds", "no lower bound is stated, and this family "
                                         "needs both"),
    "bound_quote_not_located": ("bounds", "the bound's quote is not a whole-word "
                                          "contiguous span of the served document"),
    "bound_quote_does_not_state_it": ("bounds", "the bound's quote locates, but it does not "
                                                "state this bound OF THIS VARIABLE: the "
                                                "bound's own number is not in the sentence "
                                                "quoted for it, or the sentence is not "
                                                "about this variable"),
    "bound_quote_does_not_assert_a_scale": ("bounds", "the quote is about this variable and "
                                                      "prints the bound's own numeral(s), but "
                                                      "its sentence does not read as stating a "
                                                      "range, a scale, a rating, a coding, or a "
                                                      "minimum/maximum (`premises."
                                                      "SCALE_ASSERTING`) -- it is topically "
                                                      "about the right noun without asserting "
                                                      "the bound"),
    "bound_contradicted_by_printed_values": ("bounds", "the variable's OWN PRINTED VALUES fall "
                                                       "outside the bound offered for it, so "
                                                       "the bound is not the bound of the "
                                                       "quantity those values report -- an item "
                                                       "range read against a total score, a "
                                                       "level scale read against a change "
                                                       "score, or a scale attached to the "
                                                       "wrong variable"),
}


# --------------------------------------------------------------------------
# The literal, read by the bridge's own strict grammar
# --------------------------------------------------------------------------

#: `^[-+]?\d+(\.\d+)?%?$` with the Unicode minus normalised and the `%` stripped
#: before the decimals are counted. A leading-dot decimal (`.001`) is admitted
#: because it is how a paper prints a p-value.
#:
#: DELIBERATELY A SECOND IMPLEMENTATION of what `bind.read_literal` does, and the
#: one place in this package where a second implementation of one rule is wanted
#: rather than tolerated: the account's own reading is the thing being checked,
#: so it cannot also be the checker. The two are compared on every value
#: (`premise.literals.agrees`) and a disagreement is EXPOSED rather than
#: resolved.
_STRICT = re.compile(r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)%?")
_MINUS = str.maketrans({"−": "-", "–": "-", "—": "-",
                        "‐": "-", "‑": "-"})


def read_plain(printed: Any) -> dict | None:
    """`{value, decimals, is_percent}` for a bare numeral, else None.

    None means "not a plain numeral", which is a refusal and never a guess:
    words, qualifiers, ranges and every comma-bearing literal land here, because
    a thousands separator and a decimal comma are undecidable PER VALUE.
    """
    s = str(printed if printed is not None else "").strip().translate(_MINUS)
    if not _STRICT.fullmatch(s):
        return None
    pct = s.endswith("%")
    body = s[:-1] if pct else s
    frac = body.split(".")[1] if "." in body else ""
    return {"value": float(body), "decimals": len(frac), "is_percent": pct}


def is_plain_integer(printed: Any) -> int | None:
    got = read_plain(printed)
    if got is None or got["is_percent"] or got["decimals"]:
        return None
    return int(got["value"]) if float(got["value"]).is_integer() else None


def exact_int(x: Any) -> int | None:
    """`x` as an integer when it IS one exactly, else None. Never truncates and
    never raises: a declared group n arrives as whatever a decomposition or a
    hand edit put there -- `30`, `"29"`, `30.4` or `"twenty-nine"` -- and the
    question asked of it is only ever "does this agree with the printed n?",
    which 30.4 and "twenty-nine" cannot answer."""
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return int(x) if float(x).is_integer() else None
    return is_plain_integer(x)


# --------------------------------------------------------------------------
# What a quote has to be before it can license anything
# --------------------------------------------------------------------------

#: WHERE A SENTENCE OF THE SERVED DOCUMENT ENDS.
#:
#: THE CLOSER LIST WAS ASCII AND THE PAPERS ARE NOT. `[.!?]` followed by
#: whitespace or by a STRAIGHT quote, apostrophe or bracket ended a sentence; a
#: period followed by a CURLY closing quote did not. Publishers set quotation
#: marks as U+201D / U+2019, so a sentence that ends inside a quoted phrase --
#: which is most sentences quoting an item's wording -- ran on into the next one.
#:
#: MEASURED on ajcp.70049, and it cost two real checks. `The means for inclusive
#: decision making and inclusion of community residents were 4.06 and 4.01 on a
#: 1-5 scale.” ` fused with `The number of EBPs reported ranged from 0 to 9.`, so
#: the sentence offered for BOTH variables' bounds stated TWO ranges, the
#: shared-scale lift's own ambiguity guard short-circuited, and each variable
#: lost a genuinely stated bound with the detail "its quote describes <the other
#: one>" -- reciprocally, which is the tell that neither reading was the
#: sentence's.
_SENT_END = re.compile(r"[.!?][\s\"'’”»›)\]]|\n\s*\n")
#: THE SAME PATTERN, AT EVERY POSITION IT CAN MATCH. `_SENT_END.finditer` steps
#: over a terminator that overlaps the one before it (`.\n\n` is one match), while
#: `_SENT_END.search(text, pos)` will find that second one -- so the right-hand
#: boundary of a sentence has to be looked up in a list of ALL match positions,
#: not in the non-overlapping scan. Wrapping the pattern in a lookahead is what
#: makes `finditer` enumerate every start.
_SENT_END_ANY = re.compile(r"(?=(" + _SENT_END.pattern + r"))")
_WORD_CHAR = re.compile(r"[0-9A-Za-zÀ-ɏ]")

#: Words that carry no identity. A variable's name minus these is what has to be
#: found in a sentence for the sentence to be ABOUT that variable.
_GENERIC = frozenset({
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "by",
    "with", "from", "per", "was", "were", "is", "are", "be", "been", "as",
    "that", "this", "these", "those", "it", "its", "each", "any", "all", "no",
    "not", "n", "total", "number", "score", "scores", "value", "values", "mean",
    "means", "median", "rate", "level", "levels", "group", "groups", "study",
    "measure", "measured", "count", "counts", "item", "items", "sd", "se",
})


class Haystack:
    """One paper's text, prepared for every premise question asked of it.

    THE LOCATOR IS THE REPO'S OWN AND THERE IS ONE OF IT. `bind._Hay.verify` is
    `quotes.classify`, which asks "is this ONE CONTIGUOUS SPAN of the paper?" of
    two drawings of the same bytes -- the raw text and the rendering-folded
    text. The plain regex `bind.locate` misses every fold `quotes.py` documents,
    so a quote that IS the paper's own sentence, differing by a ligature space,
    read as not located. Both are used: `classify` decides LOCATED, `locate`
    supplies the SPAN when it can, and a quote that folds but does not regex is
    located with the quote itself standing in for its sentence.
    """

    def __init__(self, text: str = ""):
        self.text = text or ""
        self._hay = _bind._Hay(self.text)
        self._cache: dict[str, dict] = {}
        self._sentences: dict[str, list[tuple[int, str]]] = {}
        self._ends: list[int] | None = None
        self._any_starts: list[int] | None = None
        self._any_ends: list[int] | None = None
        self._spans: dict[tuple[int, int], str] = {}
        self._section_bounds: list[tuple[int, int]] | None = None
        # `_antecedent_ids` is asked the SAME question once per variable at the
        # same offset -- the answer is a property of the offset and the set of
        # declared ids, not of which variable is asking -- and stage 1 asks it of
        # every sentence of the document. Memoised here rather than in the
        # function so the cache dies with the paper it is about.
        self._antecedents: dict[tuple, set[str]] = {}

    # ------------------------------------------------------------------
    # THE SENTENCE BOUNDARIES, COMPUTED ONCE.
    #
    # `sentence()` USED TO RE-SCAN THE DOCUMENT FROM CHARACTER 0 ON EVERY CALL,
    # and it is called once per regex match by every guard that asks its question
    # of the whole paper. MEASURED (round 11) on the shape CLAUDE.md 8l records
    # as the ordinary output of a converter -- a table folded onto one line, with
    # numbers, dashes, colons and slashes and NO terminal punctuation --
    # `premise_reading.candidates` cost 0.12 s at 6.6 kB and 36.88 s at 104 kB,
    # against 0.43 s for ordinary prose of the same length; `Haystack.sentence`
    # was 8,004 calls, 8.7 s of tottime and 30.5 s cumulative, because it re-ran
    # `finditer(text, 0, start)` from zero AND rebuilt the whole 104 kB string
    # each time. A paper plus supplement at 200-400 kB costs minutes per paper
    # before a model is asked anything.
    #
    # The boundaries are a property of the DOCUMENT, so they are found once and
    # looked up by bisection; and the rendered sentence is cached on its own
    # SPAN, which is what collapses the no-punctuation case -- every match there
    # names the same single "sentence" and it is built once rather than 8,004
    # times.
    # ------------------------------------------------------------------

    def _terminators(self) -> tuple[list[int], list[int], list[int]]:
        """`(non-overlapping ends, every start, every end)` of the sentence
        terminators, computed once.

        BOTH SCANS ARE KEPT BECAUSE THE TWO QUESTIONS ARE NOT THE SAME ONE. The
        left edge was found by a NON-OVERLAPPING scan restricted to the text
        before the span, and the right edge by a `search` from the span, which
        may land on a terminator the non-overlapping scan stepped over (`.\\n\\n`
        is one match to the first and two candidate starts to the second). Using
        one list for both would move a boundary the previous code did not move.
        """
        if self._ends is None:
            self._ends = [m.end() for m in _SENT_END.finditer(self.text)]
            starts: list[int] = []
            ends: list[int] = []
            for m in _SENT_END_ANY.finditer(self.text):
                starts.append(m.start())
                ends.append(m.start() + len(m.group(1)))
            self._any_starts, self._any_ends = starts, ends
        return self._ends, self._any_starts or [], self._any_ends or []

    def sentence_bounds(self, span: tuple[int, int]) -> tuple[int, int]:
        """`(left, right)` character offsets of the sentence a span sits in."""
        start, end = span
        ends, any_starts, any_ends = self._terminators()
        i = _bisect.bisect_right(ends, start)
        left = ends[i - 1] if i else 0
        j = _bisect.bisect_left(any_starts, max(end - 1, 0))
        right = any_ends[j] if j < len(any_ends) else len(self.text)
        return left, right

    def section_start(self, offset: int) -> int:
        """Where the section holding `offset` begins.

        THE DOCUMENT'S OWN SECTION MAP, not a second copy of the rule.
        `sections.map_sections` is the module that already knows what a heading
        is (letter-spaced `A B S T R A C T` included) and it reads the text and
        nothing else, so a Haystack can compute it from what it already holds --
        no plumbing, and no chance of two readers disagreeing about where a
        section starts. Memoised because the boundaries are a property of the
        document, like the sentence terminators above.

        A DOCUMENT WITH NO HEADING IS ONE SECTION, which is `map_sections`'s own
        fail-closed rule (an unrecognised structure is analytic, never cut up),
        and here it means a reach bounded only by the document -- the widening
        direction, which is the safe one for a refusal.
        """
        if self._section_bounds is None:
            self._section_bounds = [
                (s["start"], s["end"]) for s in _sections.map_sections(self.text)]
        for start, end in self._section_bounds:
            if start <= offset < end:
                return start
        return 0

    def iter_preceding_sentences(self, offset: int):
        """`(left offset, sentence)` for every sentence BEFORE the one holding
        `offset`, nearest first, lazily.

        ONE WALKER, TWO BUDGETS. `preceding_sentences` counts SENTENCES and
        `_antecedent_ids` counts sentences that NAME something (see
        `_ANAPHORA_REACH`), and the two used to be one loop with the first
        budget baked into it. Yielding the walk instead of a fixed-length list
        is what lets a caller stop on its own evidence without a second copy of
        "step back one sentence" existing anywhere.
        """
        ends, _, _ = self._terminators()
        i = _bisect.bisect_right(ends, offset)
        while i > 0:
            hi = ends[i - 1]
            lo = ends[i - 2] if i >= 2 else 0
            yield lo, " ".join(self.text[lo:hi].split())
            i -= 1

    def preceding_sentences(self, offset: int, limit: int = 6,
                            *, floor: "int | None" = None) -> list[str]:
        """The sentences BEFORE the one holding `offset`, nearest first.

        WHAT IT IS FOR: an averaging statement with an anaphoric subject (`the
        reported figure is the mean of the pair`) names no variable at all, and
        English does not repeat a noun phrase it has just introduced. The
        antecedent is the nearest preceding sentence that does name one. It is
        read ONLY by a refusal (`averaging_statements`), so being wrong about it
        costs a check and cannot buy an accusation.

        `floor` IS A CHARACTER OFFSET THE REACH MAY NOT CROSS, and it WIDENS:
        sentences are taken until `limit` of them have been taken AND the floor
        has been reached, so the window is the LARGER of the two and never the
        smaller. That ordering is the whole point -- this feeds a refusal, whose
        candidate window may only ever grow, because a window that narrows can
        leave a false accusation standing while one that grows can only remove a
        check.
        """
        out: list[str] = []
        for lo, got in self.iter_preceding_sentences(offset):
            if len(out) >= limit and (floor is None or lo < floor):
                break
            if got:
                out.append(got)
        return out

    def sentences_matching(self, rx: "re.Pattern[str]") -> list[tuple[int, str]]:
        """`(offset, sentence)` for every sentence of the document carrying `rx`.

        THE SENTENCE COMES OUT OF THE DOCUMENT, which is what makes it usable as
        evidence: nothing here is supplied by a model or by an account. Memoised
        per pattern because a guard that has to ask its question of the whole
        paper is asked once per variable, and the paper does not change between
        them.
        """
        key = rx.pattern
        got = self._sentences.get(key)
        if got is not None:
            return got
        out: list[tuple[int, str]] = []
        seen: set[str] = set()
        for m in rx.finditer(self.text):
            sent = self.sentence(m.span())
            if not sent or sent in seen:
                continue
            seen.add(sent)
            out.append((m.start(), sent))
        self._sentences[key] = out
        return out

    def locate(self, quote: Any) -> dict:
        """`{located, span, sentence, why}` for one quote.

        THREE CONDITIONS, and each was a measured false accusation:
          1. at least `quotes._MIN_FRAGMENT` characters -- a bounds quote of `a`
             located, licensed `bound_source: stated` against a planted 1-2
             scale, and returned GRIM `impossible` on an honest mean;
          2. a contiguous span, by the repo's own classifier;
          3. WHOLE WORDS at both ends -- `counted as w` is exactly twelve
             characters, locates, and is a fragment of two words, which is how
             round 2 defeated the length floor by one character.
        """
        key = str(quote or "")
        if key in self._cache:
            return self._cache[key]
        out = {"quote": key or None, "located": False, "span": None,
               "sentence": None, "why": ""}
        q = key.strip()
        if len(q) < _quotes._MIN_FRAGMENT:
            out["why"] = (f"shorter than the {_quotes._MIN_FRAGMENT}-character floor "
                          "`quotes._MIN_FRAGMENT` sets")
            self._cache[key] = out
            return out
        verdict = self._hay.verify(q).get("quote_verified")
        span = _bind.locate(q, self.text)
        if verdict != "verbatim" and span is None:
            out["why"] = f"not a contiguous span of the served text (`{verdict}`)"
            self._cache[key] = out
            return out
        if span is not None and not self._whole_words(span):
            out["why"] = "the span begins or ends inside a word"
            self._cache[key] = out
            return out
        out["located"] = True
        out["span"] = list(span) if span else None
        out["sentence"] = self.sentence(span) if span else q
        self._cache[key] = out
        return out

    def _whole_words(self, span: tuple[int, int]) -> bool:
        start, end = span
        before = self.text[start - 1] if start > 0 else " "
        after = self.text[end] if end < len(self.text) else " "
        return not (_WORD_CHAR.match(before) or _WORD_CHAR.match(after))

    def sentence(self, span: tuple[int, int]) -> str:
        """The sentence of the document the span sits in.

        THE SENTENCE, NOT THE QUOTE, IS WHAT THE ATTRIBUTION TEST READS. `was
        scored in whole points` says nothing about which variable was scored;
        the sentence it was cut from -- `Mood was rated on a 1 to 7 point scale
        and was scored in whole points.` -- says Mood. Cutting a fragment out of
        a sentence cannot make the sentence stop being about its subject, and
        reading only the fragment would refuse every honest paper that quotes
        the relevant clause rather than the whole line.
        """
        key = self.sentence_bounds(span)
        got = self._spans.get(key)
        if got is None:
            got = " ".join(self.text[key[0]:key[1]].split())
            self._spans[key] = got
        return got


def _name_forms(var: dict) -> list[list[str]]:
    """Every printed name of one variable, as word sequences.

    `name` is the schema's field; `label` is read too because the account's own
    fixtures and some readings carry the printed label there, and a name we fail
    to recognise weakens both directions of the test at once. The
    statistic-form parenthetical is stripped -- `(count of active members)` is
    the form of the thing, not the name of it -- exactly as `interpret` does
    when it joins a row label to a variable.

    `printed_as` IS READ THROUGH `printed_labels`, WHICH IS THE WHOLE OF ROUND
    12'S DEFECT: `list(var.get("printed_as") or [])` raised
    `TypeError: 'int' object is not iterable` on a scalar, from here, from
    `anchor_score`, from `about_this_variable`, from `bounds_verification` --
    outside every per-candidate try/except in `checks.evaluate` -- and on a bare
    string it raised nothing at all and read one printed label per LETTER.
    """
    out: list[list[str]] = []
    raws = [var.get("name"), var.get("label")] + printed_labels(var)
    for raw in raws:
        for form in {str(raw or ""), _interpret.strip_parens(raw)}:
            ws = _interpret._words(form)
            if ws and ws not in out:
                out.append(ws)
    return out


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


#: A TOKEN THE ACCOUNT ITSELF WRITES IN CAPITALS. Two or more capitals (digits
#: allowed after the first) is how a paper prints an abbreviation, and an
#: abbreviation is a NAME -- `ADL`, `PSS`, `IQ`, `BMI`, `HbA1c` is not one but
#: `HDL` is. The case is read from the RAW declared name, because
#: `interpret._words` lowercases and the distinction is gone by the time
#: `_content` sees a word.
_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]+\b")


def _acronym_words(var: dict) -> frozenset[str]:
    """The stemmed, lowercased tokens this variable's own printed names write in
    CAPITALS.

    WHY THIS EXISTS, MEASURED. `anchor_score` requires at least one matched word
    of four characters or more, and `_content` drops anything shorter than
    three, so `ADL`, `PSS`, `IQ`, `BMI` and `ADLs` scored 0.0 against EVERY
    sentence of their own paper -- a variable a paper names by its abbreviation
    could never be attributed anything, in either direction. That is not a
    coincidence guard doing its job: it is a length rule applied to the one
    class of name that is short BECAUSE it is a name.

    THE LENGTH FLOOR IS NOT WIDENED FOR ORDINARY WORDS, and that is the point.
    `age`, `sex`, `day`, `pre` stay below it, because a three-letter ordinary
    word in a sentence is a coincidence far more often than it is a reference.
    A capitalised token is not: a paper writes `ADL` only when it means ADL.
    """
    raws = [var.get("name"), var.get("label")] + printed_labels(var)
    out: set[str] = set()
    for raw in raws:
        for m in _ACRONYM.finditer(str(raw or "")):
            out.add(_stem(m.group(0).lower()))
    return frozenset(out)


def _content(words: list[str], keep: "frozenset[str] | set[str]" = frozenset(),
             ) -> list[str]:
    return [_stem(w) for w in words
            if w not in _GENERIC and not w.isdigit()
            and (len(w) >= 3 or _stem(w) in keep)]


def anchor_score(var: dict, sentence_words: set[str],
                 *, acronyms: bool = True) -> float:
    """How far a sentence names THIS variable: 1.0 for a whole phrase, else the
    share of the name's content words present.

    THE FULL PHRASE IS RARE AND THE TEST CANNOT REQUIRE IT. `Mood was rated on a
    1 to 7 point scale and was scored in whole points` does not contain the
    string `Mood score`, and it is the paper's own sentence about that variable.
    So a name is matched by its CONTENT words -- its own words minus the ones
    every paper uses -- with at least half of them present and at least one of
    them long enough to be a name rather than a coincidence, OR an abbreviation
    the account itself prints in capitals (see `_acronym_words`).

    `acronyms=False` SCORES THE NAME AS THE LENGTH FLOOR ALONE SCORED IT, which
    is exactly what this function did before the abbreviation relaxation. It is
    not an answer in itself and no caller should reach for it alone: it is one
    of the two readings the comparisons that can take a REFUSAL away combine.
    See `anchor_score_agreed` and `_best_named`.
    """
    keep = _acronym_words(var) if acronyms else frozenset()
    best = 0.0
    for form in _name_forms(var):
        content = _content(form, keep)
        if not content:
            continue
        hit = [w for w in content if w in sentence_words]
        if not any(len(w) >= 4 or w in keep for w in hit):
            continue
        best = max(best, len(hit) / len(content))
    return best


def name_is_anchorable(var: dict) -> bool:
    """Can ANY sentence ever be attributed to this variable?

    A NAME WHOSE EVERY WORD IS GENERIC IS NOT A NAME. `Total count`, `Total
    score`, `Item count` reduce to nothing under `_GENERIC`, so `anchor_score`
    returns 0.0 against every sentence ever written and the whole attribution
    layer is blind to that variable -- permanently, not on this paper.

    THIS IS A PROPERTY OF THE ACCOUNT, NOT OF THE PAPER, which is why it is
    worth naming. Everything that WITHDRAWS a premise resolves its subject
    through `anchor_score`; `granularity_verification`'s kind licence does not.
    So for a variable this returns False on, the licence is granted by a route
    that needs no name while its only veto is withheld by a route that needs
    one. See `averaging_statements`, which is where that asymmetry is closed.
    """
    keep = _acronym_words(var)
    return any(any(len(w) >= 4 or w in keep for w in _content(form, keep))
               for form in _name_forms(var))


def _sentence_words(sentence: str) -> set[str]:
    return {_stem(w) for w in _interpret._words(sentence)}


def _name_positions(sentence: str, var: dict) -> list[int]:
    """Where this variable's own name words are PRINTED in a passage.

    `anchor_score` answers WHETHER a sentence names a variable; this answers
    WHERE, which is the other half of the question a coordinated sentence asks
    (`bounds_verification._shared_scale`). The tokenisation is
    `interpret._words`' own -- runs of letters and digits, lowercased -- so the
    two readers cannot disagree about what a word is.
    """
    keep = _acronym_words(var)
    wanted = {w for form in _name_forms(var) for w in _content(form, keep)}
    if not wanted:
        return []
    return [m.start() for m in re.finditer(r"[a-z0-9]+", str(sentence or "").lower())
            if _stem(m.group(0)) in wanted]


def about_this_variable(var: dict, sentence: str, others: list[dict]) -> dict:
    """Is `sentence` about `var` rather than about something else?

    FAIL-CLOSED IN BOTH DIRECTIONS, and round 2 found it open in both. The old
    test asked only whether the quote named a DIFFERENT declared variable while
    not naming this one, so it was silent when the other variable was undeclared
    (`The number of scheduled sessions was 24 for every participant` licensed a
    step on Weight), and silent again when the variables carried no printed name
    at all (nothing can name 'another' variable when no variable has a name).
    Both cases now refuse: a premise must be POSITIVELY attributed to the
    variable it is offered for.

    A TIE IS NOT AN ATTRIBUTION, AND IT USED TO PASS. The comparison was
    STRICTLY greater, so a sentence that names two variables equally well was
    read as being about whichever one asked. Round 3's case is the shape that
    makes this reachable on real papers: an abbreviations block under a table
    carries no terminal punctuation, so `Haystack.sentence` -- which is right to
    read the whole sentence rather than the fragment -- expands one line into
    the block, and `PSS, Perceived Stress Scale, items rated 0 to 4` is scored
    against a block that also says `BMI, body mass index`. Both variables score
    1.0, the tie passed, and an ordinary BMI of 27.4 (SD 4.6) was adjudicated
    against a 0-4 scale. A tie now names the other variable, which refuses both
    of them: an ambiguity is not evidence for either side, and the rule can only
    ever remove a check.
    """
    words = _sentence_words(sentence)
    mine = anchor_score(var, words)
    other_id, other_best = None, 0.0
    for o in others:
        if o.get("id") == var.get("id"):
            continue
        s = anchor_score(o, words)
        if s > other_best:
            other_id, other_best = str(o.get("id")), s
    names_another = other_id if (other_best > 0 and other_best >= mine) else None
    return {"anchor_score": round(mine, 3), "about_this_variable": mine >= 0.5,
            "names_another_variable": names_another,
            "other_variable_score": round(other_best, 3)}


#: WHERE ONE SENTENCE STOPS BEING ABOUT ONE SUBJECT.
#:
#: THE SEMICOLON, AND THE CONTRASTIVE CONJUNCTIONS, AND NOTHING ELSE. `and` is
#: deliberately absent and the reason is unchanged: `Mood was rated on a 1 to 7
#: point scale and was scored in whole points` is ONE statement about one
#: subject, and splitting it there would refuse the paper's own granularity
#: sentence -- the honest case this whole gate exists to keep.
#:
#: `whereas` / `, while` / `, but` / `, although` / `, though` ARE DIFFERENT, and
#: round 7 measured the difference: `Medicines were counted in whole units,
#: whereas review time was taken from the dispensing log in minutes and seconds`
#: is one clause to a semicolon-only reader, so the discreteness words -- which
#: belong to MEDICINES -- were read as REVIEW TIME's (its name is fully present
#: in the sentence and the other's is half present, so `about_this_variable` says
#: yes and `names_another_variable` says no), and an honest continuous mean of
#: 40.37 minutes came back GRIM `impossible`. The identical words with a
#: semicolon refuse. A contrastive conjunction introduces a clause with its OWN
#: SUBJECT -- that is what the word does -- which is exactly the shape the
#: semicolon rule exists for, written with a comma.
#:
#: AND THE PUNCTUATION HALF WAS ONE MARK LONG. Round 10 measured the rest of it:
#: an em dash, the `--` a PDF conversion prints for one, a spaced en dash, a
#: colon, a spaced slash, a plain `, and`, and a `, which` relative clause each
#: join two independent clauses, and to a semicolon-only reader each left ONE
#: clause -- so `Wall touches were tallied in whole units - pool comfort was
#: recorded to the nearest half point.` gave the WALL TOUCHES' whole-unit claim
#: to POOL COMFORT and returned GRIM, GRIMMER and SPRITE `impossible` on an
#: honest half-point card. The identical sentence with `; ` or `, whereas `
#: refused. Same for the relative clause, where the whole-unit claim belongs to
#: the RECORDING INSTRUMENT (`... from the observer's tally sheet, which was kept
#: in whole units`) and not to the variable at all.
#:
#: THE LIST IS CLOSED IN A WAY A NOUN LIST NEVER IS, which is why widening it
#: here is not the treadmill this module keeps losing on: the marks English uses
#: to join two independent clauses are a handful of characters, not an unbounded
#: vocabulary of phrasings.
#:
#: TWO GUARDS KEEP A RANGE FROM BEING READ AS A CLAUSE BREAK. A dash is only a
#: break when it is SPACED and not flanked by digits (`0 - 6` and `0 – 6` are
#: ranges; `units -- comfort` is two clauses), and a colon is only a break when
#: it is not flanked by digits (`3:1`, `10:30`).
#:
#: `, and` IS STILL ABSENT, AND ROUND 10 MEASURED BOTH SIDES OF THAT. Adding it
#: closes `Wall touches were tallied in whole units, and pool comfort was
#: recorded to the nearest half point.` -- and it also splits `Wellbeing was
#: rated on a 1-7 scale, and each participant gave one whole-number rating on
#: that scale.`, this repo's own canonical known-answer fixture, whose
#: discreteness clause then names no variable and whose step stops being
#: established (five tests, including the demonstrations that GRIM reaches
#: `impossible` AND `consistent`). The two sentences are the same shape --
#: `<subject> <claim>, and <subject> <claim>` -- and what separates them is
#: whether the second subject is the variable or a person, which no boundary
#: rule can see. So the `, and` case is left to the two readers that CAN see it:
#: the account's own `derivation` field, and the model, whose `step` question is
#: asked of exactly that sentence and answers `false` on it.
#:
#: AND SPLITTING MORE FINELY IS NOT FREE. A finer clause makes an ESTABLISHING
#: sentence harder to attribute, which removes a check; it also makes a VETOING
#: sentence harder to attribute, which supplies a licence the paper withdrew.
#: ROUND 11 MEASURED THE SECOND HALF -- every one of the seven separators added
#: above detached `the two cards were averaged` from `Bed health was scored in
#: whole points by each of two stewards`, and GRIM, GRIMMER and SPRITE all
#: returned `impossible` on an honest half-point index. That is now closed in
#: `_averaging_here` rather than by narrowing this list: the veto is no longer
#: clause-scoped in the same way the licence is. See `_averaging_subject`.
#:
#: ROUND 16 D3 -- `while` NEEDED A COMMA AND `whereas` DID NOT, and that was the
#: only difference between a leak and a refusal. The list already carried a bare
#: `\s+(?=whereas\b)` alongside the comma form; `while`/`whilst` had only the
#: comma form, so `Escapement grade was assigned on a 0 to 12 condition card
#: while bushing replacements were tallied in whole units.` was ONE clause, the
#: whole-unit claim about BUSHINGS licensed a step of 1 on the GRADE, and GRIM
#: returned `impossible` on an honest half-point card. The identical sentence
#: with a comma refused. Two spellings of one rule, written at different times,
#: with only one of them moved -- so the two are now the same alternative.
#:
#: AND THE SEPARATORS A CONVERTER PRINTS. A pipe is what the table walker writes
#: between cells and what a converter leaves behind when it folds a row onto one
#: line, so a folded row was one clause and a discreteness word in ANY cell of it
#: reached every variable named in the row. A bullet, a middot, an arrow, an
#: ellipsis, a guillemet and a tab are the same fact in other documents. All are
#: punctuation, which is the class this list is allowed to grow in -- see the
#: paragraph above on why a noun list is not.
_CLAUSE_BREAK = re.compile(
    r";"
    r"|(?<!\d):(?!\d)"
    r"|\s*[—―]\s*"
    r"|(?<!\d)\s+[–\-]{1,2}\s+(?!\d)"
    r"|\s+/\s+"
    r"|\s*[|•·→…»]+\s*"
    r"|\t+"
    r"|,\s+(?=(?:but|although|though|which|who)\b)"
    r"|\s+(?=(?:whereas|while|whilst)\b)", re.I)

#: A PARENTHETICAL THAT CARRIES ITS OWN SUBJECT AND ITS OWN FINITE VERB, which
#: makes it an independent assertion rather than a modifier of the clause it
#: sits in.
#:
#: ROUND 16 D3's THIRD LEAK. `Escapement grade was assigned on a 0 to 12
#: condition card (bushing replacements were counted in whole units).` states
#: the whole-unit fact about BUSHINGS, and a reader that treats the parenthesis
#: as ordinary text reads one clause naming the grade and carrying a
#: discreteness word -- `impossible` on an honest half-point card.
#:
#: THE SUBJECT REQUIREMENT IS WHAT KEEPS THE HONEST CASE, and it is the whole
#: reason this is not simply "break on every bracket". `(scores were recorded in
#: whole points)` and `(all values were rounded)` have a finite verb and NO
#: subject of their own -- every word before the verb is in `_GENERIC` -- so they
#: modify the host clause and stay in it, and the paper keeps its step. `(bushing
#: replacements were counted ...)` names something the host clause does not.
#: The auxiliaries are a closed class of English, like the punctuation above.
_PAREN = re.compile(r"\(\s*(?P<inside>[^()]{1,400}?)\s*\)")
_FINITE_AUX = re.compile(
    r"\b(?:was|were|is|are|had|have|has|be|been|being)\b", re.I)


def _subject_before(span: str, verb: "re.Pattern[str]") -> str | None:
    """The noun phrase `span` asserts about -- the CONTENT words before its
    finite verb -- or None where it has none.

    ONE DEFINITION OF "CARRIES ITS OWN SUBJECT", TWO VERB PROBES, BOTH NAMED.
    `_is_own_assertion` asks it of a parenthetical with the AUXILIARIES alone,
    which is what `_clauses` has always cut on and what round 19 pins; the
    licence side asks it with `_LICENCE_FINITE`, which is wider. Keeping the two
    as one function is deliberate: this repo's recurring defect is two spellings
    of one rule written at different times with only one of them moved
    (CLAUDE.md 8j), and a subject rule is exactly the shape that happens to.
    """
    got = verb.search(span)
    if got is None:
        return None
    head = span[:got.start()]
    return head.strip() if _content(_interpret._words(head)) else None


def _is_own_assertion(inside: str) -> bool:
    """Does this parenthetical carry a subject of its own before a finite verb?"""
    return _subject_before(inside, _FINITE_AUX) is not None


def _clauses(sentence: str) -> list[str]:
    """A sentence's independent clauses.

    A VERB-BEARING PARENTHETICAL IS CUT OUT FIRST, because it is not reachable
    by a split on a separator: its boundary is a matched PAIR of marks, and the
    closing one carries no evidence of what it closes. See `_PAREN`.
    """
    text = str(sentence or "")
    pieces: list[str] = []
    last = 0
    for m in _PAREN.finditer(text):
        if not _is_own_assertion(m.group("inside")):
            continue
        pieces.append(text[last:m.start()])
        pieces.append(m.group("inside"))
        last = m.end()
    pieces.append(text[last:])
    parts = [p.strip() for piece in pieces for p in _CLAUSE_BREAK.split(piece)]
    return [p for p in parts if p] or [sentence]


# --------------------------------------------------------------------------
# WHO THE DISCRETENESS CLAIM IS ABOUT -- the licence's own attribution rule
# --------------------------------------------------------------------------
#
# THE DEFECT THIS CLOSES, AND IT IS A CLASS AND NOT THREE SENTENCES. The licence
# asked TWO questions of the clause it found a discreteness word in -- is the
# clause about this variable (a bag of words over the whole clause), and does it
# name a better-matched DECLARED variable -- and neither can see a whole-unit
# claim made about an UNDECLARED quantity beside it. Measured on an honest
# half-point card, six phrasings returned GRIM `impossible` on the default path
# with no flag:
#
#     ... graded on a card from 0 to 16, and damaged packets were counted in
#         whole units.
#     ... graded on a card from 0 to 16 and damaged packets were tallied in
#         whole units.
#     ... graded on a card from 0 to 16, and mainspring failures were recorded
#         as integers.
#     ... graded on a card from 0 to 16, and steward workload was rated on a
#         7-point scale.
#     ... graded on a card from 0 to 16 (the stewards counted damaged packets in
#         whole units).
#     ... graded on a card from 0 to 16 (each inspector tallied damaged packets
#         in whole units).
#
# The same facts after a SEMICOLON refused, and the same facts about a DECLARED
# rival refused. So the leak is exactly the gap between the two: a quantity the
# paper names and the account does not declare, in a clause the boundary list
# does not cut.
#
# ROUND 19 CLOSED THREE INSTANCES OF IT BY NAME -- `number of`, a bare `while`,
# and a parenthetical with an auxiliary -- and each was one more member of a
# closed list. CLAUDE.md records three separate times that this buys exactly one
# round, and the licence is the DANGEROUS polarity: a boundary this reader cannot
# see MANUFACTURES an accusation, where on the refusal side it only costs a
# check. So the rule changes shape instead of growing.
#
# THE RULE IS POSITIVE EVIDENCE, AND THAT IS THE WHOLE OF IT. A discreteness word
# licenses a step of 1 only where the ASSERTION CARRYING IT is about this
# variable. An assertion that carries a SUBJECT OF ITS OWN is about that
# subject -- which must then be this variable -- and one that carries no subject
# of its own is a predicate on its host clause and is attributed exactly as it is
# today. So an undeclared quantity in subject position fails BY CONSTRUCTION,
# because the test is "the subject is this variable" and never "no OTHER DECLARED
# variable intervenes".
#
# WHAT STILL DEFEATS IT, STATED PLAINLY. A competing assertion whose finite verb
# is LEXICAL and is not itself one of the vocabulary's own verbs -- `..., and
# stewards LOGGED mainspring failures as integers.` -- carries a subject this
# reader cannot find, so it defers to the host clause and licenses. Closing that
# needs a verb lexicon, and the two morphological proxies for one (`-ed`, `-s`)
# both refuse honest sentences: `each inspector MARKED one whole-number grade`
# is the canonical shape this module must keep, and it is `-ed`. That residue is
# left where `_CLAUSE_BREAK` already leaves the `, and` case -- to the account's
# own `derivation` field and to the model, whose `step` question is asked of
# exactly that sentence.

#: THE COORDINATING CONJUNCTIONS, and nothing looser. English joins two
#: independent assertions with a closed handful of words, which is the same
#: argument `_CLAUSE_BREAK` makes for punctuation and is NOT the argument a noun
#: list makes. `for` is deliberately absent: it is overwhelmingly a preposition.
#:
#: THESE ARE NOT CLAUSE BREAKS AND MUST NOT BECOME ONE. `, and` was measured and
#: rejected as a `_CLAUSE_BREAK` member with a stated reason -- it splits this
#: repo's own canonical known-answer fixture, whose discreteness clause then
#: names no variable at all -- and that decision stands. A SEGMENT boundary is a
#: weaker thing: it decides only WHERE TO LOOK FOR A SUBJECT, and a segment with
#: no subject of its own still inherits its clause's attribution. So the
#: canonical fixture keeps its licence (`each participant gave one whole-number
#: rating on that scale` has no auxiliary and no vocabulary verb, so it asserts
#: about nobody and belongs to the clause) while `damaged packets were counted in
#: whole units` does not (it asserts about damaged packets).
_COORDINATOR = re.compile(r",?\s+(?:and|or|but|nor|yet|so)\s+", re.I)

#: THE MEMBERS OF `DISCRETENESS` THAT CAN THEMSELVES HEAD A FINITE PREDICATE.
#: `_FINITE_AUX` finds the subject of `X were counted`; it finds nothing in
#: `the stewards counted X`, where the vocabulary's own word IS the verb. No
#: other member can be one: `integers`, `whole points`, `Likert` and
#: `7-point scale` are nouns and modifiers.
_DISCRETENESS_VERB = r"\b(?:counts?|counted|tall(?:y|ies|ied))\b"

#: The finite-verb probe the LICENCE uses. Wider than `_FINITE_AUX` on purpose,
#: and the direction is the safety argument: a wider probe finds MORE subjects,
#: a found subject must be this variable, so widening here can only ever REMOVE
#: a licence (CLAUDE.md 8d, invariant 1). Widening `_FINITE_AUX` itself would
#: also change `_clauses`, which the averaging VETO walks, and there the same
#: edit would remove a refusal.
_LICENCE_FINITE = re.compile(_FINITE_AUX.pattern + "|" + _DISCRETENESS_VERB, re.I)


def assertion_segments(clause: str) -> list[str]:
    """`clause`, split into the assertions it coordinates.

    TWO BOUNDARIES, BOTH OF THEM PLACES ENGLISH STARTS A NEW ASSERTION WITHOUT
    THE PUNCTUATION `_CLAUSE_BREAK` READS: a parenthesis, and a coordinating
    conjunction that joins two things each carrying a finite verb.

    THE FINITE-VERB TEST ON THE LEFT-HAND SIDE IS WHAT KEEPS A COORDINATED
    SUBJECT WHOLE. `Mood and anxiety were rated in whole points` coordinates two
    NOUNS, not two assertions -- there is no verb before the `and` -- so it stays
    one segment and the sentence keeps its licence for both variables. `Seed
    vigour was graded on a card and damaged packets were tallied in whole units`
    has one on each side and is two.

    EVERY parenthetical is a segment here, including the ones `_clauses` leaves
    inline: `_clauses` cuts only those with an auxiliary-headed subject, because
    cutting is shared with the averaging veto and may not remove a refusal.
    Segmenting is not cutting -- a subject-less parenthetical still inherits its
    clause -- so it is safe to segment on the mark itself.
    """
    text = str(clause or "")
    pieces: list[str] = []
    last = 0
    for m in _PAREN.finditer(text):
        pieces.append(text[last:m.start()])
        pieces.append(m.group("inside"))
        last = m.end()
    pieces.append(text[last:])
    out: list[str] = []
    for piece in pieces:
        start = 0
        for m in _COORDINATOR.finditer(piece):
            # `search(piece, start, m.start())` AND NOT `search(piece[start:...])`:
            # a converter's folded table row is one "sentence" of many thousands
            # of characters with a coordinator every few words, and slicing per
            # match is the quadratic shape round 11 measured at 36.88 s on a
            # 104 kB paper.
            if _LICENCE_FINITE.search(piece, start, m.start()) is None:
                continue
            out.append(piece[start:m.start()])
            start = m.end()
        out.append(piece[start:])
    return [s.strip() for s in out if s.strip()] or [text]


def _assertion_subject(segment: str) -> str | None:
    """The noun phrase a coordinate assertion is ABOUT, or None where it has
    none of its own. See `_subject_before`."""
    return _subject_before(segment, _LICENCE_FINITE)


# --------------------------------------------------------------------------
# ROUND 22 -- INHERITANCE REQUIRES CONTIGUITY, AND AN UNPARSED BOUNDARY FAILS
# CLOSED
# --------------------------------------------------------------------------
#
# THE DEFECT, AND IT IS THE SAME CLASS ARRIVING THROUGH A THIRD DOOR. Round 19
# closed three phrasings by name, round 21 closed the COORDINATORS and the
# PARENTHESES by asking which assertion inside a clause the discreteness word
# belongs to. Neither can see a SUBORDINATE CLAUSE or an ADJUNCT, because
# neither is a coordinator and neither is a bracket -- so `assertion_segments`
# returns the WHOLE SENTENCE as one segment, `_assertion_subject` returns the
# MAIN CLAUSE's subject (which IS the variable under test), and a whole-unit
# word belonging to something else licenses a step of 1. Twenty ordinary
# phrasings were measured against the unchanged tree, every one of them GRIM
# AND SPRITE `impossible` on a card the paper itself says is graded TO THE
# NEAREST HALF POINT:
#
#     ... running from 0 to 20, together with a count of damaged floats.
#     ... running from 0 to 20, because damaged floats were counted in whole units.
#     ... running from 0 to 20, damaged floats being counted in whole units.
#     ... running from 0 to 20, alongside a Likert item on steward workload.
#     ... running from 0 to 20, a measure quite separate from damaged floats,
#         counted in whole units.
#     (and fifteen more: `after`, `since`, `as`, `when`, `where`, `before`,
#      `once`, `whereby`, the bare forms of two of them, `with X counted`,
#      `as well as`, `plus`, `X counted in whole units`, `having counted X`)
#
# THE SAME FACTS AFTER A SEMICOLON REFUSED, AND REFUSE NOW. So this is once
# again exactly the gap between a punctuation this reader cuts on and one it
# does not.
#
# SO THE RULE IS NOT A TWENTY-FIRST SUBORDINATOR. CLAUDE.md records that a
# closed list bought one round three times running, and this premise has now
# paid that price twice. THE ACTUAL DEFECT IS A FAIL-OPEN: where the boundary
# cannot be determined, `_discreteness_licence` falls back on the host clause's
# attribution and GRANTS. That inverts invariant 1 -- a derived boundary may
# NARROW a premise and may never SUPPLY one -- because an unparsed boundary is
# supplying one. The fix is to fail CLOSED there, and the cost is measured
# below rather than asserted.
#
# WHAT MAKES INHERITANCE SOUND, STATED AS THE RULE. `_discreteness_licence`
# grants a segment with no subject of its own the attribution of the clause
# around it, and that is right for a BARE PREDICATE: `was scored in whole
# points` and `(values were recorded in whole units)` have nothing to be about
# except the clause they sit in. It is NOT right for material introduced by a
# comma, because a comma is the mark English uses to start a constituent whose
# head and whose attachment this reader has not identified -- an adjunct, a
# subordinate clause, an absolute, an appositive, a non-restrictive relative.
# So inheritance is available where the discreteness word is CONTIGUOUS with
# the start of its segment, and after a comma only on terms.
#
# THE TWO WAYS A LATER CONSTITUENT STILL EARNS ONE, both of which keep shapes
# that are ordinary methods prose rather than edge cases:
#
#   IT NAMES THIS VARIABLE. `At each watch, lantern polish was recorded in
#   whole points.` puts a leading adverbial before the assertion and the
#   assertion is positively about this variable. That is a POSITIVE
#   attribution, never an inheritance.
#
#   IT NAMES NOTHING AT ALL. `... is scored from 0 to 21, in whole points.` --
#   this repo's own canonical bound-and-granularity sentence -- has no quantity
#   in it once the vocabulary is removed, so it cannot be about a rival, and it
#   modifies the last run that DID name something. See `_run_names_something`,
#   and note that an appositive naming a rival is exactly what that lookback
#   catches.
#
# THE DIRECTION IS THE SAFETY ARGUMENT, AND IT IS CHECKABLE. This test is a
# CONJUNCT added to the ones round 21 already applies: a segment must still be
# about this variable, must still carry the vocabulary, and must still survive
# the subject test. So the change can only ever REMOVE a licence, and removing
# a licence can only ever remove a check. Measured that way over 139 probes on
# four independent fixture papers -- 0 licences granted that were refused
# before, 0 accusations added, 0 check rows added -- and asserted as a property
# in `tests/test_scaffold_checks_round22.py::TestTheNewTestIsTheOnlyThingStandingThere`,
# which removes this conjunct and watches the twenty accusations come back.

#: THE MARK THAT STARTS A CONSTITUENT THIS READER HAS NOT PARSED. It is NOT a
#: `_CLAUSE_BREAK` member and must not become one.
#:
#: MEASURED, because the obvious alternative deserved a number rather than an
#: argument: adding `,\s+` to `_CLAUSE_BREAK` at `6688c9d3` closes nineteen of
#: the twenty-one phrasings, leaves the two BARE subordinators accusing (they
#: have no comma to cut on), and costs the canonical `, and` fixture -- whose
#: discreteness clause then names no variable at all, which is the measured
#: reason `, and` was twice rejected as a member. And a clause break is shared
#: with the averaging VETO, which `_averaging_here` walks: a cut there may
#: remove a REFUSAL, and this module's standing rule is that a boundary may
#: narrow a licence and may never narrow a refusal.
#:
#: So the mark is used here for the opposite purpose -- to say that INHERITANCE
#: is unavailable, which is a refusal and not an attribution, and which touches
#: nothing the veto reads.
_CONSTITUENT = re.compile(r",")


# --------------------------------------------------------------------------
# ROUND 25 -- A SENTENCE THAT DENIES WHOLE-NUMBER GRANULARITY MAY NOT ESTABLISH
# IT
# --------------------------------------------------------------------------
#
# THE DEFECT, AND IT IS THE CHEAPEST ONE THIS PREMISE HAS HAD. Every round since
# the fourth has asked WHOSE the discreteness claim is -- which clause, which
# assertion, which constituent, which quantity. None of them asked whether the
# sentence was making the claim AT ALL or DENYING it. `DISCRETENESS` is a
# keyword test, `counted` matches inside `was not counted`, and a paper that
# states in its own words that its measure is NOT recorded in whole units was
# handed a step of 1 and returned GRIM, GRIMMER and SPRITE `impossible`.
# MEASURED at `ccc8c627`, on the default path, with no flag and no model, on a
# card the paper itself says is graded to the nearest half point. Eleven
# phrasings, and GRIM, GRIMMER and SPRITE all `impossible` on every one:
#
#     ... and was not counted in whole units.
#     ... and not counted in whole units.
#     ... and was not recorded as integers.
#     ... and is not discrete.
#     ... and did not use a Likert item.
#     ... and neither counted nor tallied in whole units.
#     ... and was never a whole number.
#     ... with no integers permitted.
#     ... in half points instead of whole units.
#     ... in half points rather than whole units.
#     ... not in whole units but in half points.
#
# This is the same shape as `SCALE_ASSERTING` in round 13 -- a gate that asked
# what a sentence was ABOUT and never what it SAID -- and the same remedy: a
# conjunct that can only ever REMOVE a licence. There is no argument on the
# other side. A sentence that denies whole-number granularity cannot establish
# whole-number granularity, so nothing honest is lost by refusing to read one as
# if it did.
#
# THE SCOPE RULE, AND IT IS THE WHOLE OF THE DESIGN. A NOT-LIST alone would be
# the wrong instrument twice over: it would withdraw the licence from `no items
# were missing; scores were counted in whole units`, where the denial is about
# something else entirely, and it could not tell `tablets were counted in whole
# units, unlike the diary entries, which were not` (which DOES establish the
# step for tablets) from `tablets were not counted in whole units`. So the
# question is asked PER VOCABULARY MATCH and BACKWARDS, and the denial must be
# shown to GOVERN that match:
#
#   * BACKWARDS ONLY. English negation scopes forward from the negator, so a
#     denial that appears AFTER the whole-unit words is not about them. That one
#     asymmetry is what keeps `..., unlike Y, which was not` licensing X.
#   * AND ONLY AS FAR AS THE NEAREST POLARITY RESET -- a mark that closes a
#     constituent (`_CONSTITUENT`, and the sentence-level marks) or a
#     coordinating conjunction (`_COORDINATOR`). Both definitions are IMPORTED
#     from the two the module already owns rather than restated, which is the
#     drift CLAUDE.md 8j names. `Grades were not averaged and were counted in
#     whole units` keeps its licence because `and` resets; `No items were
#     missing; scores were counted in whole units` keeps it because `;` does.
#   * THE RESET IS INCLUDED IN THE WINDOW, not cut away, because one of the six
#     coordinators IS a negator: `neither counted nor tallied in whole units`
#     would otherwise reset itself clean at `nor`.
#
# WHAT THIS COSTS, MEASURED ON PROSE WRITTEN FOR THE PURPOSE AND NOT ON THE
# PINNED FIXTURES, WHICH CANNOT SEE THIS PREMISE AT ALL. Instrumented, the guard
# is CALLED 6,161 times across the 11,466 pinned tests and FIRES 0 times -- no
# fixture in this repo contains a negated granularity sentence in either
# direction, so a green suite says nothing about this change. (Round 24 recorded
# the same property from the other side: `discreteness_boundary: unresolved`, 0
# occurrences in 979 pinned inputs.) The cost was therefore measured on 46
# honest sentences written for it -- 24 carrying a denial SOMEWHERE ELSE and 22
# carrying none -- A/B against the guard removed:
#
#     38 licences the free path granted at ccc8c627, 0 withdrawn;
#     and on 9 of those 38 the denial sits UPSTREAM of the whole-unit words, so
#     the reset half of the rule is the only thing keeping the licence.
#
# TWO SHAPES ARE WRONG AND ARE NAMED RATHER THAN HIDDEN: a DOUBLE NEGATIVE
# affirms integrality by denying its complement (`could not be recorded in
# anything other than whole units`) and loses its licence, which costs a check;
# and a denial reaching across a parenthetical (`were not, in the end, counted in
# whole units`) keeps its licence, which is the leak this window admits. Both, and
# three more, are in
# `tests/test_scaffold_checks_round25.py::TestWhatThisCostsAndWhatStillLeaks`.
#
# THE DIRECTION IS THE SAFETY ARGUMENT AND IT IS CHECKABLE. This is a conjunct
# on a LICENCE: a match it refuses is a match that does not license, and a
# licence that is not granted cannot accuse anybody. It touches no refusal
# premise -- `AVERAGED`, `_ESTIMATOR_STATEMENT`, `WEIGHTED_PERCENTAGE` and
# `varying_n_statement` are all polarity-blind too, and there the blindness adds
# refusals, which costs checks and never an accusation. Named in the round-25
# test file; deliberately not changed here.

#: THE WORDS THAT DENY. A closed list is the right instrument HERE and the wrong
#: one for a noun vocabulary, and the difference is that English negation is a
#: closed class: a handful of particles, the contracted `-n't`, and the three
#: substitutive phrases that replace one reading with another.
#:
#: `not only` IS NOT ONE, and that is not a softening. `not only X but also Y`
#: ASSERTS X -- it is a focus construction, not a denial -- so treating it as a
#: denial would withdraw a licence from a sentence that grants it.
#:
#: `no` DOES NOT MATCH THE NUMERO ABBREVIATION. `No. of damaged floats was
#: counted in whole units` is a table stub, not a denial, and `No.` is how
#: papers print it.
_NEGATOR = re.compile(
    r"\bnot(?!\s+only\b)\b"
    r"|\b\w+n[’']t\b"
    r"|\b(?:cannot|never|neither|nor|none|without)\b"
    r"|\bno\b(?!\s*[.:])"
    r"|\b(?:instead\s+of|rather\s+than|other\s+than|as\s+opposed\s+to)\b"
    r"|\bfail(?:s|ed|ing)?\s+to\b", re.I)

#: WHERE A DENIAL'S SCOPE ENDS, LOOKING BACK FROM THE WORDS IT WOULD DENY. The
#: two halves are this module's own: `_CONSTITUENT`, the mark that opens a
#: constituent it has not parsed, and `_COORDINATOR`, the closed handful of words
#: English joins two independent assertions with. The sentence-level marks are
#: added because a denial plainly does not cross a full stop or a semicolon.
_POLARITY_RESET = re.compile(
    r"[;:.!?()\[\]{}\"“”«»]|--|[—–]|"
    + _CONSTITUENT.pattern + r"|" + _COORDINATOR.pattern, re.I)

#: How far back a denial may be looked for when no reset intervenes. A BOUND ON
#: COST AND NOT ON MEANING: a converter's folded table row is one "sentence" of
#: many thousands of characters, and an unbounded lookback per vocabulary match
#: is the quadratic shape round 11 measured at 36.88 s on a 104 kB paper. A
#: denial more than this far away with no punctuation and no conjunction between
#: is not English prose.
_DENIAL_LOOKBACK = 400

#: The first token of a truncated lookback, which may be the tail of a word --
#: `piano` cut at `no` would read as a denial. Dropped, so the window starts at a
#: word this reader has actually seen the whole of.
_PART_WORD = re.compile(r"^\S+")


def _denial_governing(text: str, start: int) -> str | None:
    """The denial that governs the vocabulary match beginning at `start`, or
    None.

    See the block comment above for the scope rule. The window runs back from
    the match to the nearest polarity reset, INCLUDING the reset itself.
    """
    lo = start - _DENIAL_LOOKBACK
    head = text[:start] if lo <= 0 else _PART_WORD.sub("", text[lo:start], count=1)
    reset = None
    for reset in _POLARITY_RESET.finditer(head):
        pass
    window = head[reset.start():] if reset is not None else head
    got = _NEGATOR.search(window)
    return got.group(0).strip() if got else None


# ROUND 26 -- WHOLE-NUMBERED PER OBSERVATION IS NOT WHOLE-NUMBERED PER SUBJECT.
#
# THE DEFECT, AND IT IS THE ONE AXIS NO EARLIER ROUND ASKED ABOUT. Round 4 asked
# which CLAUSE, round 21 which ASSERTION, round 22 which CONSTITUENT, round 24
# which QUANTITY, round 25 whether the sentence was AFFIRMING or DENYING. Every
# one of those asks WHOSE the whole-number claim is. None of them asks PER WHAT
# it is made. `Proof legibility was graded in whole points at each of three
# visits` attributes perfectly: it is about the variable under test, it is
# affirmed, its boundaries are clean, and the model asked round 24's question
# answers -- correctly -- that the whole-number words describe the target. What
# the sentence establishes is that each VISIT'S GRADE is a whole number. The
# table prints one number per PRESS RUN, and a run has three visits.
#
# MEASURED ON THE DEFAULT PATH AT `a2878afb`, no flag and no model, on the same
# half-point card round 25 uses: 20 of 22 ordinary phrasings licensed a
# per-subject step of 1, and GRIM, GRIMMER and SPRITE all returned `impossible`
# on every one of the 20.
#
# WHY THIS IS NOT THE AVERAGING PREMISE, AND THE ANSWER DECIDES THE DESIGN.
# `AVERAGED` is a REFUSAL premise asserting a positive fact -- the reported
# quantity IS the mean of several observations -- and it is strong enough to
# withdraw the KIND's licence as well, because the mean of k whole counts is not
# whole. These sentences assert no such thing. `graded in whole points at each of
# three visits` does not say the table reports a mean; the table may report the
# final visit's grade, or the total, either of which IS whole. Putting these
# phrasings into `AVERAGED` would make this layer assert an aggregation the paper
# never stated and take a `count`'s kind licence away on the strength of it --
# supplying a premise rather than narrowing one, which is exactly what CLAUDE.md
# 8d invariant 1 forbids.
#
# WHAT IS TRUE IS WEAKER AND IS AN ABSENCE: the sentence states its granularity
# about individual OBSERVATIONS and says nothing at all about the per-subject
# value. So this belongs where an absence belongs -- the SENTENCE LICENCE fails,
# `discreteness_source` falls back to `assumed`, and the KIND licence is
# untouched, exactly as round 24 leaves it untouched for the same reason (a count
# of things is a whole number of things whatever any adjunct is about).
#
# THE INSTRUMENT IS THE PAPER'S OWN ARITHMETIC, NOT A READING OF ITS NOUNS, and
# that is what keeps the two shipped branches out of the judgement this round
# could not make. `by each of two readers` says there are TWO of them; `as a
# whole number of quarter points` says the unit is a QUARTER of the printed one.
# Neither needs anybody to decide whether a visit is an occasion or a rater is an
# agent. The account's declared units (`subjects.unit_of_analysis` -- "what one n
# counts" -- `subjects.population` and `paper.species_or_population`, three
# fields the schema specifies and no judgement in `premises` or `checks` had ever
# read) are used ONLY as an ESCAPE: `across five press runs` counts subjects, not
# repetitions, so naming one can only KEEP a licence. An account that declares
# none of the three therefore loses coverage and never protection -- which is how
# a NULLABLE schema field is allowed near a premise at all.
#
# TWO BRANCHES, ONE QUESTION -- PER WHAT?
#   A  a CARDINAL over a plural noun that is not the subject and not the measure
#      itself (`by each of two readers`, `on both occasions`, `at all four
#      timepoints`, `by two independent readers`), read after the discreteness
#      vocabulary itself is removed, so `seven response options` and `a 7-point
#      scale` -- which are per-subject claims written with a number -- cannot
#      fire it. The paper has said IN ITS OWN WORDS that there is more than one
#      observation per subject; nothing is inferred about what a visit or a rater
#      IS.
#   B  a SUB-UNIT of the reported measure (`a whole number of quarter points`,
#      `in whole half points`), where the claim is whole in a unit the table does
#      not print. The step is then 1/k of the printed unit, not 1.
#
# AND THE THIRD BRANCH IS NOT SHIPPED, WHICH IS THE MAIN FINDING OF THE ROUND.
# The obvious rule -- a DISTRIBUTIVE QUANTIFIER (`at each visit`, `by every
# reader`, `per sheet`) withdraws unless its restrictor names the subject -- was
# built, measured and REMOVED. It closed eight more accusing phrasings and it
# cannot be made safe, for a reason that is not a tuning problem:
#
#     `each participant gave one whole-number rating on that scale`
#     `each keeper gave one whole-number grade on that card`
#
# are the same sentence. The first is honest and the second is not, and the only
# thing separating them is that a participant is a subject and a keeper is a
# rater -- which no feature of the sentence carries. The account DOES declare the
# answer in principle (`subjects.unit_of_analysis`, `subjects.population`,
# `paper.species_or_population`), and the join against it is not reliable enough
# to rest a licence on: the FIRST sentence above is this repo's own canonical
# known-answer fixture, whose paper declares `species_or_population: "people"`
# and leaves `unit_of_analysis` null, so `participant` misses and GRIM stops
# running on `test_known_impossible_mean_is_impossible`. MEASURED: with that
# branch on, 223 pinned tests fail across 17 files, and the shape it fires on --
# `at every service`, `on each plate`, `at every drill`, `for every plot holder`
# -- is what the honest licensing control of nearly every earlier round is
# written in. A guard that pre-empts those fixtures does not merely cost
# coverage: it makes fifty pinned adjunct cases unable to fail, which is this
# repo's own [[a-fixture-that-excludes-the-defect-region]] arriving from the
# other side.
#
# SO THE BARE DISTRIBUTIVE IS AN ATTACHMENT-SHAPED PROBLEM AND BELONGS WHERE
# ROUND 24 PUT ONE. It needs a model asked a new question -- not `whose quantity
# do these words describe` (which the round-24 veto already asks, and which the
# model answers CORRECTLY on every one of these: the words DO describe the target
# variable) but `PER WHAT is the claim made`. `adjudication_attach`'s machinery
# takes it unchanged -- a withdrawal-only verdict, ANDed into `establishes`,
# filed by `premise_reading.index` on `true` alone -- with a different `PREMISE`
# name and a different question text. Specified here, deliberately not built:
# round 24's own warning is that a batch score is not a measurement of what a run
# will do, and a new question needs its own arms, its own candidate set and its
# own paid measurement.
#
# THE DIRECTION IS THE SAFETY ARGUMENT for what DOES ship. Both branches are
# conjuncts on a LICENCE: each can only fail to license, and a licence not
# granted cannot accuse anybody. So a branch that is too generous costs coverage
# and never safety -- which is why the cost is measured on prose written for it
# rather than argued for here. See `tests/test_scaffold_checks_round26.py`.

#: A SMALL CARDINAL OVER A PLURAL NOUN -- how many of the thing there are per
#: subject, in the paper's own words. Two words of modifier are allowed between
#: (`two independent readers`).
#:
#: `both` IS ONE OF THE CARDINALS AND IS NOT A QUANTIFIER HERE, which is the one
#: place this shape had to be narrowed. English FLOATS `both` over a coordinated
#: subject, where it quantifies two VARIABLES rather than two observations:
#: `Branch health and cut counts were both recorded in whole units` is the repo's
#: own honest coordinated-subject fixture. Requiring a PLURAL NOUN after it is
#: what separates `both readers` and `both occasions` from a `both` floated onto
#: a participle.
#:
#: THE DIGIT FORM IS BOUNDED AT NINE AND THE SPELLED FORM IS NOT, which is
#: `AVERAGED`'s own measured asymmetry from the other side: a paper writes its
#: own n in digits (`each of the 45 press runs`), so a LARGE digit beside a
#: plural noun is the study's own sample and must not be read as a repetition
#: count. A digit that is part of a longer number is not a cardinal at all
#: (`0.5 points`, `14.2`), which is what the lookbehind says.
_COUNTED_PLURAL = re.compile(
    r"\b(?:(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|both)"
    r"|(?<![\d.])[2-9](?![\d.]))\s+"
    r"(?:[A-Za-z][\w-]*\s+){0,2}?(?P<noun>[A-Za-z][\w-]*s)\b", re.I)

#: HOW FAR AFTER THE WHOLE-NUMBER WORDS THE SUB-UNIT MAY SIT, and the direction
#: is the rule. English puts the unit AFTER the quantity word -- `a whole number
#: OF QUARTER POINTS`, `in whole HALF POINTS` -- so a fraction word sitting
#: BEHIND the vocabulary is a different clause's business. Measured: without the
#: direction and the reach, `graded to the nearest half point on a card running
#: from 0 to 16, with chipped prisms counted in whole units` -- round 22's own
#: canonical honest sentence, where the half point belongs to the variable and
#: the whole units to a rival -- fired on the `half point`, which would have made
#: fifty pinned adjunct cases unable to fail.
_SUB_UNIT_REACH = 30

#: A FRACTION OF THE PRINTED UNIT. `quarter` and `half` only, and directly
#: modifying a noun: every other fraction word in English is also an ORDINAL
#: (`the third visit`, `the fifth sheet`) and would fire on ordinary prose, and
#: `half of the sheets` / `a quarter of an hour` are quantities of things rather
#: than units of measure. The plural-with-`of-a` form is unambiguous and is the
#: one place the other fraction words are admitted.
_SUB_UNIT = re.compile(
    r"\b(?:quarters?|halves|half)[\s-]+(?!of\b|the\b|an?\b|its\b|their\b)"
    r"[A-Za-z][\w-]*\b"
    r"|\b(?:halves|thirds|quarters|fifths|sixths|eighths|tenths|twentieths)"
    r"\s+of\s+(?:a|an|one)\b", re.I)

#: WHERE THE QUESTION "PER WHAT?" STOPS LOOKING. An adjunct may sit either side
#: of the words it modifies and may sit behind a comma (`graded in whole points,
#: at each of three visits`), so the plain comma is NOT a reset here -- which is
#: the one place this window is wider than `_POLARITY_RESET`. What does reset is
#: a sentence-level mark or one of the six coordinators, because `counted in
#: whole units, and each reader signed the sheet` is two assertions and the
#: second one's `each` is not about the first.
_PER_SCOPE_RESET = re.compile(
    r"[;:.!?()\[\]{}\"“”«»]|--|[—–]|" + _COORDINATOR.pattern, re.I)

#: HOW FAR EITHER SIDE THE QUESTION LOOKS WHEN NO RESET INTERVENES. `_DENIAL_
#: LOOKBACK`'s reason, in both directions: a converter's folded table row is one
#: "sentence" of many thousands of characters with no punctuation in it, and an
#: unbounded window scanned per vocabulary match is the quadratic shape round 11
#: measured at 36.88 s on a 104 kB paper. An adjunct further away than this, with
#: no punctuation and no conjunction between, is not English prose.
_PER_REACH = 400


def subject_terms(account: dict) -> frozenset[str]:
    """The stemmed content words for WHAT ONE n COUNTS, as the account declares
    it.

    THE FIELD THE SCHEMA ASKS FOR AND NOBODY READ. `subjects.unit_of_analysis`
    is specified as "what one n counts: a mouse, a participant, a coalition, a
    school", `subjects.population` as "who or what the units are, as printed",
    and `paper.species_or_population` is not nullable at all -- so an account
    that passed schema validation carries at least one of the three. Before this
    round `render.py` printed them and no judgement anywhere read them.

    GROUP LABELS ARE DELIBERATELY NOT IN IT. They are the obvious fourth source
    and they are the dangerous one: a longitudinal paper whose groups are
    `Baseline` and `Month 12` would put `visit`-shaped words into the subject
    vocabulary, and a subject term that is really an occasion KEEPS a licence
    this round exists to withdraw. Every source here answers "who is a row",
    which is the question being asked.
    """
    subjects = account.get("subjects")
    subjects = subjects if isinstance(subjects, dict) else {}
    paper = account.get("paper")
    paper = paper if isinstance(paper, dict) else {}
    out: set[str] = set()
    for raw in (subjects.get("unit_of_analysis"), subjects.get("population"),
                paper.get("species_or_population")):
        out.update(_content(_interpret._words(str(raw or ""))))
    return frozenset(out)


def _per_governing(text: str, start: int, end: int, subjects: "frozenset[str]",
                   mine: "frozenset[str]") -> str | None:
    """The words saying WHAT the whole-number claim at `[start, end)` is PER,
    when that is something other than one subject's own reported value.

    `subjects` is `subject_terms(account)` and `mine` is this variable's own name
    words. BOTH ARE ESCAPES AND NEVER TRIGGERS, which is what keeps them off the
    critical path: a cardinal over the subject (`across five press runs`) or over
    the measured thing itself is not a repetition, so naming either can only KEEP
    a licence, and an account that declares nothing loses coverage rather than
    protection. See the block comment above for the two branches and the scope
    rule.
    """
    lo = max(0, start - _PER_REACH)
    head = text[:start] if lo == 0 else _PART_WORD.sub("", text[lo:start], count=1)
    reset = None
    for reset in _PER_SCOPE_RESET.finditer(head):
        pass
    left = (start - len(head)) + (reset.end() if reset is not None else 0)
    tail = _PER_SCOPE_RESET.search(text, end, end + _PER_REACH)
    right = tail.start() if tail is not None else min(len(text), end + _PER_REACH)
    window = text[left:right]
    # THE VOCABULARY IS REMOVED BEFORE THE CARDINAL IS LOOKED FOR, which is
    # `_run_names_something`'s trick and is what keeps `seven response options`
    # and `a 7-point scale`: those numbers are PART of the whole-number claim,
    # not a count of how many times it was made.
    stripped = DISCRETENESS.sub(" ", window)
    for m in _COUNTED_PLURAL.finditer(stripped):
        noun = _stem(m.group("noun").lower())
        if noun in subjects or noun in mine:
            continue
        return " ".join(m.group(0).split())
    got = _SUB_UNIT.search(text, end, min(right, end + _SUB_UNIT_REACH))
    return " ".join(got.group(0).split()) if got else None


def _assertion_spans(text: str) -> list[tuple[int, int]]:
    """`(start, end)` of every coordinate assertion in `text`, in its own
    offsets.

    THE DECOMPOSITION THE LICENCE ALREADY WALKS, WITH THE OFFSETS KEPT.
    `_discreteness_licence` reads `assertion_segments` of each `_clauses` part
    and both return STRIPPED STRINGS, which is all a caller asking "whose is
    this assertion?" needs and not enough for one asking "which assertion is
    this MATCH in?". Located with a forward cursor rather than re-split: two
    spellings of one boundary rule is this repo's recurring defect (CLAUDE.md
    8j) and a splitter is exactly the shape it happens to. Both functions emit
    their pieces in document order, including the parenthetical each lifts out,
    so a cursor that never moves backwards places every one of them.

    A SEGMENT THE CURSOR CANNOT PLACE IS DROPPED, and the caller reads a match
    that lands in no span as the clause's own -- the direction that withdraws.
    """
    spans: list[tuple[int, int]] = []
    cursor = 0
    for clause in _clauses(text):
        for seg in assertion_segments(clause):
            at = text.find(seg, cursor)
            if at < 0:
                continue
            spans.append((at, at + len(seg)))
            cursor = at + len(seg)
    return spans


def _mention_speaks_for_this(text: str, spans: list[tuple[int, int]],
                             pos: int, var: dict) -> bool:
    """Could the vocabulary match at `pos` be a claim about `var`?

    THE QUESTION `_discreteness_licence` ASKS OF A SEGMENT, ASKED OF ONE MATCH,
    and with the polarity a REFUSAL needs rather than the one a licence needs.
    A match sitting in an assertion with no subject of its own INHERITS its
    clause, which is that function's `inherited` and is read here as this
    variable's own; a match whose assertion has a subject speaks for whatever
    that subject names.

    `others` IS DELIBERATELY EMPTY. `_attribution`'s rival list can only ever
    turn a `this` into an `other` -- that is what it is for -- and an `other`
    here REMOVES this veto. A veto must fail open (`_attribution`'s own
    docstring: a tie is `this`, because refusing on an ambiguity can only remove
    a check), so the rival list is not consulted: a claim about a declared rival
    that still anchors on this variable costs a check and cannot buy an
    accusation. It also keeps this question answerable from a sentence alone,
    which is what every caller of `discreteness_is_per` has.
    """
    for start, end in spans:
        if start <= pos < end:
            subject = _assertion_subject(text[start:end])
            if subject is None:
                return True
            return _attribution(var, subject, []) == "this"
    return True


def discreteness_is_per(passage: Any, var: dict, subjects: "frozenset[str]",
                        ) -> str | None:
    """The words that say what this passage's whole-number claim is PER, where
    the claim this variable's own assertion makes is made per something that is
    not the subject. `None` where the passage makes the claim about the value
    the table prints.

    ONE MENTION THIS VARIABLE'S OWN IS ENOUGH, and that is the averaging
    family's policy rather than this premise's own. Round 26 shipped the
    opposite -- `if said and all(said)`, on the argument that a refusal must be
    the passage's LAST WORD on granularity -- and a probe defeated it with an
    ordinary second mention: one more whole-number word anywhere in the located
    sentence, about the CARD, the FORM, the RESPONSE OPTIONS or a rival
    quantity, restored the licence and with it GRIM, GRIMMER and SPRITE
    `impossible` on a card the paper itself grades to the nearest half point.
    FIVE of seven probe sentences. The guard was real and an honest-looking
    second clause disarmed it.

    THE ARGUMENT FOR UNANIMITY RESTED ON A DISTINCTION THIS READER DOES NOT
    HAVE, which is the finding and not a tuning note. Round 26's own pinned
    rescuer and the probe's disarming clause are the same sentence:

        ... by each of two luthiers, and the figure entered in the ledger for
            the instrument is itself recorded in whole units.
        ... at each of three inspections, and the card was printed in whole
            units.

    Both coordinate a second assertion whose subject names something the account
    never declared; one means the REPORTED VALUE is whole and the other means
    the INSTRUMENT is, and nothing in the words separates them. A rule that
    keeps the first keeps the second, and the second manufactures an
    accusation. So a second mention no longer rescues, and the price is written
    down in `tests/test_scaffold_checks_round27.py` rather than argued away: a
    sentence that states the step for an observation AND states it again for
    the reported figure now falls back to `assumed`.

    WHAT IT IS NOT IS A BARE `any`. A whole-number claim made per observation
    about a DIFFERENT quantity -- `..., and damaged frames were counted in whole
    units at each of three inspections` -- says nothing about this variable and
    does not withdraw its licence. That restriction is `_mention_speaks_for_
    this`, and it is why this is a question about the TARGET rather than about
    the sentence.

    ROUND 26'S TEST IS KEPT AS THE FLOOR, so this can only ever withdraw where
    that did: where EVERY surviving match is per something else, the licence
    falls whether or not this reader could attribute any of them.
    """
    mine = frozenset(w for form in _name_forms(var)
                     for w in _content(form, _acronym_words(var)))
    text = str(passage or "")
    spans: list[tuple[int, int]] | None = None
    said: list[str | None] = []
    for m, denied in _discreteness_hits(text, var):
        if denied is not None:
            continue
        governed = _per_governing(text, m.start(), m.end(), subjects, mine)
        said.append(governed)
        if governed is None:
            continue
        # THE SPANS ARE BUILT AT MOST ONCE AND ONLY WHERE A MATCH IS ACTUALLY
        # DISTRIBUTED. A converter's folded table row is one "sentence" of many
        # thousands of characters with a vocabulary match every few words, and
        # re-splitting it per match is the quadratic shape round 11 measured at
        # 36.88 s on a 104 kB paper.
        if spans is None:
            spans = _assertion_spans(text)
        if _mention_speaks_for_this(text, spans, m.start(), var):
            return governed
    if said and all(said):
        return said[0]
    return None


def _one_predication(run: str) -> bool:
    """Does `run` contain at most ONE predication this reader can see?

    THE OTHER WAY ENGLISH STARTS AN ASSERTION WITHOUT PUNCTUATION, and the one
    the comma above cannot see. `... was graded on a card running from 0 to 20
    because damaged floats were counted in whole units.` has no comma, no
    coordinator and no bracket, so it is ONE segment and ONE run -- and it
    carries TWO subjects, each with its own finite verb. `_assertion_subject`
    answers with the FIRST, which is the variable under test, and the
    whole-unit claim of the SECOND licenses a step of 1 on it. Bare `after`
    does the same. Both were measured accusing on the honest half-point card.
    THE SUBORDINATOR IS NOT THE FACT; a second predication is, and a lexicon of
    subordinators is the closed list this rule exists not to be.

    THE TEST USES NOTHING NEW. `_LICENCE_FINITE` finds the finite verbs and the
    existing content/generic split says whether a SUBJECT stands between two of
    them. `Branch health scores were counted in whole units` has two verb
    matches with nothing between them and is one predication; `Batch counts
    were verified before glaze uniformity was recorded in whole points` has
    `verified before glaze uniformity` between them and is two.

    ONLY WHAT COMES BEFORE THE WHOLE-UNIT WORDS IS COUNTED, and that is not a
    softening -- a predication that begins AFTER them cannot own them. `Bench
    tidiness was counted in whole units by the two inspectors who were trained
    together.` is ordinary methods prose whose trailing relative clause has a
    subject of its own, and counting it would refuse an honest sentence for
    words that arrive too late to be the claim. The LAST vocabulary match in the
    run is the cut, not the first: a coincidental earlier match (`Prism counts
    were reconciled before bench tidiness was recorded in whole points`) must
    not shorten the span this walks, or the second predication hides behind it.

    WHAT THIS COSTS IS REAL AND IS RECORDED, not zero: an honest sentence that
    states the granularity in its SECOND predication now refuses, because this
    reader cannot tell it from one that states a rival's granularity there. The
    price of a refusal is a check; the price of the licence is an accusation.
    """
    last = None
    for last in DISCRETENESS.finditer(run):
        pass
    upto = last.start() if last is not None else len(run)
    spans = [m for m in _LICENCE_FINITE.finditer(run) if m.start() <= upto]
    return not any(_content(_interpret._words(run[a.end():b.start()]))
                   for a, b in zip(spans, spans[1:]))


def _run_names_something(run: str, var: dict) -> bool:
    """Does this run NAME a quantity, or does it only MODIFY one?

    THE DISTINCTION THE ROUND WOULD BE WRONG WITHOUT, and this repo's own
    canonical bound-and-granularity sentence is the case: `The Brackenridge
    adherence score is scored from 0 to 21, in whole points.` puts the
    whole-unit words after a comma, in a constituent that names NOTHING -- take
    the vocabulary out and only function words are left. It cannot be about a
    quantity other than the one already named, because it names no quantity at
    all. `, alongside a Likert item on keeper workload` and `, with chipped
    prisms counted in whole units` leave `keeper workload` and `chipped prisms`
    behind, and those are the leak.

    THE VOCABULARY IS REMOVED FIRST, which is the whole trick: `in whole points`
    is entirely vocabulary and `a Likert item on keeper workload` is not. What
    is left is put to the module's existing content/generic split, so a
    reporting participle (`, recorded in whole units`) counts as naming and
    REFUSES. That is conservative and deliberately so -- this reader cannot tell
    a participle from a noun, and the direction it must be wrong in is the one
    that costs a check.
    """
    stripped = DISCRETENESS.sub(" ", str(run or ""))
    return bool(_content(_interpret._words(stripped), _acronym_words(var)))


def _discreteness_is_attributable(var: dict, segment: str,
                                  others: list[dict]) -> tuple[bool, str | None]:
    """Can this reader say whose claim the discreteness word in `segment` is?

    `(yes, the constituent it could not attribute)`. Three conditions, and all
    three are about whether the assertion carrying the whole-unit word was
    DELIMITED rather than about what it says:

      * the run holds a SINGLE PREDICATION, so the subject
        `_assertion_subject` goes on to read is the subject of the assertion the
        whole-unit word is actually in;
      * the run is the segment's FIRST, which is contiguous with the clause the
        caller has already attributed;
      * or the run, or the last run before it that NAMES anything, is about this
        variable. A run that names nothing modifies whatever was last named --
        which is why `..., in whole points.` keeps its licence and
        `..., a measure quite separate from chipped prisms, counted in whole
        units.` does not, though both end in a constituent naming nothing.
    """
    runs = _CONSTITUENT.split(str(segment or ""))
    names = [_run_names_something(r, var) for r in runs]
    unattributed: str | None = None
    for i, run in enumerate(runs):
        if not discreteness_about(run, var):
            continue
        if not _one_predication(run):
            if unattributed is None:
                unattributed = run.strip()
            continue
        if i == 0:
            return True, None
        owner = next((runs[j] for j in range(i, -1, -1) if names[j]), None)
        if owner is None:
            # NOTHING IN THIS SEGMENT NAMES ANYTHING, so there is no rival it
            # could be about and it modifies the clause the caller attributed.
            return True, None
        here = about_this_variable(var, owner, others)
        if here["about_this_variable"] and not here["names_another_variable"]:
            return True, None
        if unattributed is None:
            unattributed = run.strip()
    # THE VOCABULARY MATCH THAT STRADDLES THE MARK. `number of` and what it
    # counts can fall either side of a comma, so the segment carries the
    # vocabulary and no single run does. That is a boundary this reader has not
    # parsed, which is exactly what this function refuses on.
    return False, unattributed or str(segment or "").strip() or None


def _discreteness_licence(
        var: dict, clause: Any,
        others: list[dict]) -> tuple[str | None, str | None, str | None, str | None]:
    """`(the assertion that establishes a step of 1 for `var`, the subject that
    took it away, the constituent whose boundary could not be resolved, how the
    licence was attributed)`.

    THE ATTRIBUTION IS THE LICENCE'S, WHICH IS NOT THE REFUSAL'S. `_attribution`
    reads a TIE as `this` because for a refusal an ambiguity must fail OPEN;
    here it must fail CLOSED, so the subject is put to `about_this_variable`,
    which names the rival on a tie and refuses both. Same asymmetry as
    `granularity_verification`'s own clause test, stated once more where it is
    now decided.

    AND AN UNRESOLVED BOUNDARY IS ITS OWN OUTCOME, not a rival subject. The two
    refusals say different things to an auditor -- `discreteness_belongs_to`
    names a quantity the paper made the claim about, and the third return value
    names words this reader could not attribute to anybody -- so they are
    recorded apart rather than folded into one.
    """
    blocked: str | None = None
    unresolved: str | None = None
    for seg in assertion_segments(clause):
        if not discreteness_about(seg, var):
            continue
        attributable, where = _discreteness_is_attributable(var, seg, others)
        if not attributable:
            if unresolved is None:
                unresolved = where
            continue
        subject = _assertion_subject(seg)
        if subject is None:
            # A PREDICATE WITH NO SUBJECT OF ITS OWN belongs to its host clause,
            # whose attribution the caller has already established -- and which
            # it is CONTIGUOUS with, which the test above has just established.
            return seg, None, None, "inherited"
        here = about_this_variable(var, subject, others)
        if here["about_this_variable"] and not here["names_another_variable"]:
            return seg, None, None, "subject"
        if blocked is None:
            blocked = subject
    return None, blocked, unresolved, None


#: THE NOUN PHRASE A DEFINITIONAL AVERAGING CLAUSE DEFINES, when the clause is
#: written `<NP> is/was the mean of ...` and the averaging match begins at the
#: operator. The subject may not cross a comma, a colon or a semicolon, so it is
#: the nearest noun phrase and never a whole coordinated sentence.
_DEFINITION_HEAD = re.compile(
    r"(?P<subject>[^.;,:]{1,80}?)\s+(?:is|was|are|were)\s+"
    r"(?:the\s+|a\s+|an\s+)?"
    r"(?:arithmetic\s+|simple\s+|unweighted\s+|weighted\s+|overall\s+)?$", re.I)

#: THE SAME, where `AVERAGED` matched the subject too (`each pupil's index is
#: the mean of ...`).
_DEFINITION_IN_MATCH = re.compile(
    r"(?P<subject>[^.;,:]{1,80}?)\s+(?:is|was|are|were)\s+"
    r"(?:the\s+|a\s+|an\s+)?(?:mean|average|midpoint|mid[-\s]?point)\b", re.I)


#: The possessor of a possessive noun phrase, which is the SUBJECT OF THE STUDY
#: and never the quantity: `the child's score`, `each plot's rating`.
_POSSESSOR = re.compile(r"\b[\w-]+(?:'s|’s)\s+", re.I)


def _names_a_quantity(subject: Any) -> bool:
    """Does this noun phrase NAME a quantity, or merely refer to one?

    THE RESIDUAL CASE BETWEEN ROUND 4 AND ROUND 11, and the last one a boundary
    rule can decide. Both of these define something as a mean, in a sentence that
    also names the variable under test:

        ... and the child's score is the mean of the two assessors' ratings.
        ... in whole points; the fidelity index is the mean of four item ratings.

    The first must withdraw the step and the second must not, and what separates
    them is whether the subject NAMES a quantity of its own. `the child's score`
    is a possessive over a word every paper uses -- strip the possessor and
    nothing contentful is left -- so it REFERS to whatever the passage is about.
    `the fidelity index` names something: `fidelity` is not a word this sentence
    could be using for the variable it has already named.
    """
    rest = _POSSESSOR.sub(" ", str(subject or ""))
    return bool(_content(_interpret._words(rest)))


def _averaging_subject(clause: str, hit: "re.Match[str]") -> str | None:
    """The quantity a DEFINITIONAL averaging clause defines, or None where the
    clause is a PREDICATE ON THE CONSTITUENTS rather than a definition.

    THIS IS THE DISTINCTION ROUND 4 AND ROUND 11 BOTH TURN ON, and it is
    grammatical rather than semantic, which is why a boundary rule can make it.
    Two sentences of identical shape:

        Mood was rated ... in whole points; the fidelity index is the mean of
        four item ratings.                      -- the veto must NOT fire
        Bed health was scored in whole points by two stewards; the two cards
        were averaged.                          -- the veto MUST fire

    `<NP> is the mean of <X>` DEFINES its subject: the sentence has named the
    quantity being averaged, and if that quantity is not this variable, this
    variable's step stands. `<NP> was averaged` states an operation on the
    CONSTITUENTS and names no quantity at all, so it belongs to whatever the
    passage is about -- which is how English writes it, and why the second
    sentence's averaging fact is about bed health.

    A subject that NAMES NO QUANTITY (`the child's score`, `it`) is returned as
    None as well: it refers to the passage's own topic rather than introducing a
    quantity of its own, so it is attributed exactly as a predicate is. See
    `_names_a_quantity`.
    """
    got = _DEFINITION_HEAD.search(clause[:hit.start()])
    subject = got.group("subject").strip() if got else None
    if subject is None:
        inside = _DEFINITION_IN_MATCH.match(hit.group(0))
        subject = inside.group("subject").strip() if inside else None
    return subject if (subject and _names_a_quantity(subject)) else None


def anchor_score_agreed(var: dict, sentence_words: set[str]) -> float:
    """The LOWER of the two readings of `anchor_score` -- with the abbreviation
    relaxation and without it.

    THE RELAXATION MAY ONLY EVER ADD A REFUSAL, AND THIS IS HOW THE THREE PLACES
    THAT COULD REMOVE ONE ASK FOR A SCORE. `_acronym_words` exists so that a
    variable a paper calls `ADL` can be attributed its OWN sentence at all -- a
    length floor applied to the one class of name that is short BECAUSE it is a
    name, and that direction is the point of it. Read in the OPPOSITE direction
    -- to take an averaging statement AWAY from another variable and leave its
    step of 1 standing -- a name that could not anchor at all before the
    relaxation must not acquire the power to do that. An abbreviation is also
    the STRONGEST possible rival by construction: it is one content word, so it
    scores 1.0 whenever it appears at all and beats every multi-word name a
    paper prints in full only some of the time.

    MEASURED at `108e9ec6`, on the default path with no flag, against an honest
    paper: seed vigour graded 0-16 in WHOLE points by each of two inspectors and
    reported as the mean of the two cards, so it moves in HALF points and no
    integer total reaches its mean. Beside it a declared `BMI`. The paper's own
    sentence `The vigour and BMI figures were averaged across the two
    inspectors' cards.` scores 0.5 for `Seed vigour` -- the prose says `vigour`
    where the account declares `Seed vigour` -- and, newly, 1.0 for `BMI`. The
    averaging clause was read as BMI's, the step of 1 stood, and GRIM returned
    `impossible`. At `a24add71` BMI scored 0.0 against every sentence and the
    same paper was clean. Two more shapes of the same sentence do it through two
    more comparisons: see `is_anaphoric_averaging` and `_best_named`.

    AND IT IS THE LOWER OF THE TWO, NOT SIMPLY THE OLD ONE, because the
    relaxation does not only RAISE scores. It also enlarges the DENOMINATOR: for
    `IQ test score` the content words are `test` alone without it and `iq, test`
    with it, so a sentence saying `test` scores 1.0 under the old rule and 0.5
    under the new one. Reverting the rival's score to the old rule would
    therefore have manufactured a demotion of its own on a name of that shape.
    A demotion now needs both readings to agree, which is this repo's ordinary
    answer to an ambiguity and can only ever cost a check.

    THE LICENCE SIDE IS DELIBERATELY LEFT ALONE. `about_this_variable` keeps the
    relaxation on both sides, because there a better-named rival sets
    `names_another_variable` and REFUSES the licence: an abbreviation that newly
    anchors can only remove a check on that path.
    """
    if not _acronym_words(var):
        # A NAME WITH NO CAPITALS IN IT READS THE SAME BOTH WAYS, which is most
        # of them, so the second reading is skipped rather than computed.
        return anchor_score(var, sentence_words, acronyms=False)
    return min(anchor_score(var, sentence_words),
               anchor_score(var, sentence_words, acronyms=False))


def _rival_score(var: dict, words: set[str], others: list[dict]) -> float:
    """The best-named OTHER declared variable, scored so that the abbreviation
    relaxation cannot take an averaging statement away. See
    `anchor_score_agreed`."""
    return max((anchor_score_agreed(o, words) for o in others
                if str(o.get("id")) != str(var.get("id"))), default=0.0)


def _attribution(var: dict, passage: Any, others: list[dict]) -> str:
    """`"this" | "other" | "nobody"` -- who a passage is about.

    THE REFUSAL'S POLARITY OF `about_this_variable`, AND IT IS NOT THE LICENCE'S.
    That function sets `names_another_variable` ON A TIE, because for a LICENCE
    an ambiguity is not evidence and must fail closed. `_averaging_here` reused
    it for a REFUSAL, where the same rule fails OPEN: an ordinary Methods
    sentence that defines one variable as an average and mentions a second in the
    same breath (`Bed health is the mean of the two stewards' cards, and steward
    workload was logged at the same visit.`) kept the step of 1, and GRIM,
    GRIMMER and SPRITE all returned `impossible` on honest half-point data
    (round 11 F3, three word orders). A tie is therefore `this` here: refusing on
    an ambiguity can only ever remove a check.

    Only a STRICTLY better-named other variable takes the clause away, which is
    round 4's rule about an averaging clause that is plainly about something
    else, kept.

    AND IT MUST BE BETTER-NAMED ON EVIDENCE BOTH READINGS OF ITS NAME AGREE ON.
    See `_rival_score` and `anchor_score_agreed`: a rival that outscores this
    variable only because the abbreviation relaxation newly lets it anchor does
    not take the clause, so the relaxation can only ever ADD this veto.
    """
    text = str(passage or "")
    here = about_this_variable(var, text, others)
    rival = round(_rival_score(var, _sentence_words(text), others), 3)
    if rival > here["anchor_score"] and rival >= 0.5:
        return "other"
    if here["about_this_variable"]:
        return "this"
    return "nobody"


def _averaging_here(var: dict, passage: Any, others: list[dict], *,
                    unattributed: str = "defer") -> str | None:
    """The averaging statement `passage` makes ABOUT `var`, or None.

    THREE READINGS OF ONE AVERAGING MATCH, IN ORDER, and the order is the whole
    of the rule:

      1. A DEFINITION (`<NP> is the mean of ...`) belongs to ITS SUBJECT. If the
         subject is this variable the step is withdrawn; if it is another
         declared variable it is not; if it names nobody the definition is
         deferred -- a caller with the discourse may resolve it, and one without
         it leaves the premise where it was.
      2. A PREDICATE ON THE CONSTITUENTS (`the two cards were averaged`) names no
         quantity, so it is attributed to the CLAUSE and then, failing that, to
         the WHOLE PASSAGE. That second step is what round 10's wider
         `_CLAUSE_BREAK` broke: seven separators detached the predicate from the
         subject it is about and each returned GRIM `impossible` on an honest
         half-point index.
      3. Failing both, `unattributed` decides. `"defer"` returns None, which is
         where `averaging_statements` picks the sentence up and resolves it
         against the discourse. `"refuse"` withdraws the step anyway, and is what
         a TABLE'S OWN CAPTION OR FOOTNOTE gets: `Each entry is the mean of the
         two stewards' cards.` under a table governs every value in it, and there
         is no sentence for it to be about.

    One definition, because the veto is asked of the granularity sentence, of
    every sentence of the served text, and of the table's own furniture.
    """
    text = str(passage or "")
    for span in _clauses(text):
        for hit in AVERAGED.finditer(span):
            subject = _averaging_subject(span, hit)
            if subject is not None:
                who = _attribution(var, subject, others)
                if who == "this":
                    return hit.group(0).strip()
                if who == "other":
                    continue
            else:
                who = _attribution(var, span, others)
                if who == "this":
                    return hit.group(0).strip()
                if who == "other":
                    continue
                if _attribution(var, text, others) == "this":
                    return hit.group(0).strip()
            if unattributed == "refuse":
                return hit.group(0).strip()
    return None


# --------------------------------------------------------------------------
# Value premises
# --------------------------------------------------------------------------


def provenance(value: dict) -> tuple[str | None, str]:
    """`(registry provenance, why)` for one value.

    A table cell the walker built is `printed_table`; located prose whose own
    printed number sits inside its verified quote is `printed_text`. Everything
    else refuses -- including, by construction, anything a figure would have
    produced, which GATE 2 would refuse anyway.

    `printed_in_quote` IS TESTED FOR TRUTH, NOT FOR `is False`. A reading that
    never wrote the field is not a reading that verified it, and the old test
    admitted exactly that: a prose n whose own number appears nowhere in its
    quote supplied the denominator of every check in the run because the field
    was absent rather than false. The field is only asked of PROSE: a table
    cell's quote is the cell, and `bind` leaves the field null there.
    """
    src = str(value.get("source") or "")
    prov = PROVENANCE_OF.get(src)
    if prov is None:
        return None, f"source `{src or 'none'}`"
    if prov == "printed_table":
        if value.get("quote_verified") != "cell":
            return None, f"a table value whose quote is `{value.get('quote_verified')}`"
        return prov, ""
    if value.get("quote_verified") != "verbatim":
        return None, f"prose quote is `{value.get('quote_verified')}`, not verbatim"
    if not value.get("printed_in_quote"):
        return None, ("the printed number is not inside its own quote"
                      if value.get("printed_in_quote") is False else
                      "the reading did not record whether the printed number is "
                      "inside its own quote")
    return prov, ""


def binding(value: dict) -> str:
    """The `id_check` gate, as a FOUR-VALUED FACT rather than a boolean.

    `corroborated` (the join agrees, or supplied the id), `contradicted` (the
    join names a different variable), `model_only` (`None`: there was no join to
    make), `unchecked` (everything else, including `unjoined` and any token this
    module has never heard of). The split matters because two readers ask
    different questions of it: `checks` admits only `corroborated` and gives
    `model_only` its own reason (D2), while `coverage` counts `model_only` and
    `unchecked` together as `placed_model_only` and only `contradicted` as
    unbound.
    """
    check = value.get("id_check")
    if check is None:
        return "model_only"
    if check in CORROBORATED:
        return "corroborated"
    if check == CONTRADICTED:
        return "contradicted"
    return "unchecked"


def _partners(value: dict, index: dict) -> list[dict]:
    loc = value.get("location") or {}
    if loc.get("kind") == "table_cell":
        key = ("cell", loc.get("table_id"), loc.get("row"), loc.get("col"))
    else:
        c = value.get("coordinate") or {}
        key = ("coord", c.get("study_id"), c.get("group_id"), c.get("phase_id"),
               value.get("variable_id"))
    return [w for w in index.get(key, []) if w.get("id") != value.get("id")]


def table_label_pattern(caption: Any) -> "re.Pattern[str] | None":
    """The regex that finds THIS table's printed name in the paper's prose, or
    None where the caption does not name itself.

    THE JOIN IS BUILT FROM THE CAPTION'S OWN WORDS, never from the account's
    internal handle: `table:4` is ours, `Table 4` is the paper's, and guessing
    one from the other would invent the join rather than read it. The words are
    rejoined with `\\s*` so that a caption printing `Supplementary Table 3` still
    matches prose that breaks the phrase across a line, and the number is matched
    whole (`\\b`) so `Table 1` cannot match `Table 10` or `Table S1`.

    THE ORDER THE CAPTION PRINTED IS THE ORDER THE PROSE PATTERN TAKES. A paper
    that captions `S1 Table` says `S1 Table` in its Results section, not
    `Table S1`, and building the pattern the other way round would join the name
    to a table the paper never printed.
    """
    m = _TABLE_LABEL.search(str(caption or ""))
    if not m or m.start() > _TABLE_LABEL_HEAD:
        return None
    word_first = bool(m.group("word"))
    words = str(m.group("word") if word_first else m.group("pre_word")).split()
    num = re.sub(r"\s+", "", str(m.group("num") if word_first else m.group("pre_num")))
    label = r"\s*".join(re.escape(w) for w in words)
    if word_first:
        return re.compile(r"\b" + label + r"\.?\s*" + re.escape(num) + r"\b", re.I)
    return re.compile(r"\b" + re.escape(num) + r"\s*" + label + r"\b", re.I)


def table_notes(captions: dict[str, str], text: str = "") -> dict[str, str]:
    """Per table, THE PAPER'S OWN SENTENCE saying that table reports a model.

    A CAPTION IS NOT THE ONLY PLACE A PAPER SAYS WHAT A TABLE IS, and round 4's
    sharpest column of the guard matrix is the one where the caption is bare
    (`Table 4.`) and the column carries no label at all -- while the Results
    section says, in the paper's own words, `Table 4 gives the multivariable
    model for week-12 Asthma Control Test score.` The evidence was in the served
    text and nothing looked for it. (CLAUDE.md 8d: "any attempt to understand
    these tables that is not informed by the paper/supplement text will fail.")

    THE JOIN IS THE CAPTION'S OWN FRONT MATTER. The account's `table:4` is an
    internal handle; `Table 4` is what the prose says, and the caption is where
    the paper prints both. A table whose caption does not name itself gets no
    note -- guessing the printed label from an internal id would be inventing
    the join rather than reading it.

    ONE SEGMENT, NOT ONE SENTENCE, so that `Table 4 shows the characteristics;
    the models are in Table 5` cannot borrow the second clause's word for the
    first table. It only ever REMOVES checks (invariant 1).
    """
    out: dict[str, str] = {}
    body = str(text or "")
    if not body:
        return out
    segments = [s for s in re.split(r"(?<=[.;:])\s+|\n", body) if s.strip()]
    for table_id, caption in captions.items():
        rx = table_label_pattern(caption)
        if rx is None:
            continue
        for seg in segments:
            if not rx.search(seg):
                continue
            # THE REPO'S OWN RULE IS ASKED HERE TOO, through its public name and
            # not through a second copy of its pattern: a segment that would
            # count as a model-output CAPTION counts as one when the paper says
            # it in prose instead.
            if _MODEL_TABLE.search(seg) or _prepass.reports_model_output(None, seg):
                out[table_id] = " ".join(seg.split())[:200]
                break
    return out


def model_output_reason(value: dict, var: dict | None, index: dict,
                        captions: dict[str, str],
                        notes: dict[str, str] | None = None) -> str | None:
    """Why this cell is a model output rather than a descriptive statistic, or None.

    EIGHT CHANNELS, IN ORDER, AND THE FIRST IS THE REPO'S OWN. `prepass.
    reports_model_output` is imported and asked first, so nothing it already
    catches can drift; the rest exist because round 2 proved a string-matching
    column rule cannot be patched into completeness. What they read is what the
    estimate IS: the value's own `statistic`, a whole header that is an estimate
    symbol or a model/contrast header, a caption that names an ESTIMATION
    PROCEDURE, the paper's own sentence about this table, a neighbour in the same
    cell that the reading itself typed as an estimate, or -- for a value reported
    in prose, which has no column and no caption at all -- the paper's own
    `B = ... SE = ... p = ...` notation.

    THE VARIABLE'S `role` AND `kind` ARE RECORDED AND NOT USED AS EVIDENCE, and
    the reason is worth stating because they look like they should be: a
    covariate's mean in Table 1 is a DESCRIPTIVE statistic of a covariate, and a
    `continuous` kind says nothing about whether this particular cell holds a
    description or a coefficient. Deciding from them would refuse honest
    descriptive rows by the hundred on any paper with a regression in it.

    IT CAN ONLY EVER REMOVE A CHECK (invariant 1), which is what makes it safe
    to be generous, and every removal is named so the coverage loss cannot be
    silent.
    """
    loc = value.get("location") or {}
    col = loc.get("col_label")
    caption = captions.get(str(loc.get("table_id") or ""))
    why = _prepass.reports_model_output(col, caption)
    if why:
        return why
    if str(value.get("statistic") or "") in ESTIMATE_STATISTICS:
        return (f"the reading typed this value `{value.get('statistic')}` -- an estimate "
                "from a fitted model, not a description of a measured variable")
    label = str(col or "").strip()
    if label and _ESTIMATE_LABEL.match(label):
        return (f"the column is headed {label!r} -- an estimate from a fitted model "
                "beside its own uncertainty, not a descriptive statistic")
    if label and _MODEL_HEADER.match(label):
        return (f"the column is headed {label!r} -- a model number, an adjustment or a "
                "contrast between groups, not a description of a measured variable")
    for where, band in (("caption", caption), ("column", label)):
        m = _MODEL_TABLE.search(str(band or ""))
        if m:
            return (f"the {where} says {m.group(0)!r} -- the table reports an estimation "
                    "procedure, not a description of the sample")
    note = (notes or {}).get(str(loc.get("table_id") or ""))
    if note:
        return (f"the paper's own text says {note!r}, so this table reports a fitted "
                "model rather than a description of the sample")
    for w in _partners(value, index):
        if str(w.get("statistic") or "") in ESTIMATE_STATISTICS:
            return (f"the same cell holds `{w.get('statistic')}` ({w.get('id')}), which "
                    "the reading typed as an estimate from a fitted model")
    if loc.get("kind") != "table_cell":
        quote = str(value.get("quote") or "")
        m = _ESTIMATE_IN_PROSE.search(quote)
        if m:
            return (f"the sentence reports {m.group(0).strip()!r} -- an estimate from a "
                    "fitted model, printed in prose with no column band to read")
    return None


def _governing_statement(rx: "re.Pattern[str]", text: str) -> str | None:
    """The first segment of the served text `rx` matches, tidied for a docket.

    ONE SEGMENT, NOT THE WHOLE DOCUMENT, so that a reader is handed the sentence
    the refusal rests on and can go and read it. Segments are bounded by
    sentence punctuation and by line breaks, which is what a table footnote is.
    """
    for seg in re.split(r"(?<=[.;:])\s+|\n", str(text or "")):
        if seg.strip() and rx.search(seg):
            return " ".join(seg.split())[:200]
    return None


def weighting_statement(text: str) -> str | None:
    """The paper's own sentence saying its percentages are weighted or
    standardised, or None. Computed once per paper (`stamp`)."""
    return _governing_statement(WEIGHTED_PERCENTAGE, text)


def varying_n_statement(text: str) -> str | None:
    """The paper's own sentence saying its analysis n varies by measure, or
    None. Computed once per paper (`stamp`)."""
    return _governing_statement(_N_VARIES, text)


def estimator_statement(text: str) -> str | None:
    """The paper's own sentence saying what estimator its MEANS are, or None.
    Computed once per paper (`stamp`)."""
    return _governing_statement(_ESTIMATOR_STATEMENT, text)


def analysed_counts(text: Any) -> list[dict]:
    """Every number of SUBJECTS the served text says was analysed at a stage.

    THE FOURTH DOCUMENT-LEVEL STATEMENT, and the one that was missing. The stamp
    already reads the whole served text for three -- `weighting_statement`,
    `varying_n_statement`, `estimator_statement` -- and had no reader at all for
    HOW MANY UNITS WERE ANALYSED HERE, so every denominator fact the paper states
    outside a value's own sentence was invisible. `group_n` reads the value's own
    quote (`denominator_stated_in_quote`) and nothing else, and its own docstring
    concedes it never asks whether an n counts the same THING.

    MEASURED: `Twenty-four nurses attended the twelve-week visit.` in Methods,
    with no `n = 24` notation for the reading to key on, left the account holding
    exactly one n -- the enrolled 28, at no phase -- and the follow-up mean
    `7.08` (= 170/24 exactly) was adjudicated against it: GRIM, GRIMMER and
    SPRITE `impossible` on an honest paper. Both controls, where the SAME
    sentence was recorded as an n row, refuse. So the less the reading recorded,
    the more the bridge accused.

    THE VERB LIST IS THE NARROW PART. `enrolled`, `randomised`, `approached` and
    `screened` are deliberately absent: they name the total the group's n already
    is, and reading them would refuse a paper for stating its own sample size.
    What is here is RETENTION and ANALYSIS -- the stages at which the number
    changes.
    """
    out: list[dict] = []
    for seg in re.split(r"(?<=[.;:])\s+|\n", str(text or "")):
        for m in _ANALYSED_AT_A_STAGE.finditer(seg):
            k = _count_of(m.group("count"))
            if k is None or k <= 1:
                continue
            row = {"n": k, "unit": (m.group("noun") or "").lower(),
                   # THE STAGE THIS COUNT IS ABOUT, which is what a value's own
                   # sentence is joined to. A count with no stage joins to
                   # nothing and withdraws nothing.
                   "stages": stage_phrases(seg),
                   "quote": " ".join(seg.split())[:200]}
            if row not in out:
                out.append(row)
    return out


def analysis_unit_statement(text: Any) -> dict | None:
    """The paper's own statement of how many ANALYSIS UNITS its design yields,
    where those units are NOT its subjects -- or None.

    THE n COUNTS SUBJECTS AND THE MEAN AVERAGES OBSERVATIONS. `Each nurse was
    recorded on three consecutive nights, giving 84 nurse-nights of actigraphy.`
    is the whole of the evidence, it sits in Methods, and the mean it governs is
    printed in Results: 257 whole awakenings over 84 nurse-nights is 3.0595 ->
    `3.06`, which at n = 28 is GRIM `impossible`. Moving the same clause INTO the
    value's own sentence defeats the accusation today
    (`denominator_contradicted_by_the_sentence`), which is the shape of the gap:
    the guard reads one sentence and the paper wrote two.

    THE NOUN IS WHAT KEEPS THIS NARROW. A yield clause counting SUBJECTS (`for a
    total of 28 nurses`) says nothing new and is not matched; only a unit that is
    not a subject is -- a hyphenated compound (`nurse-nights`, `patient-years`)
    or one of the observation nouns a repeated-measures design counts. So the
    statement fires on the papers whose unit of analysis is genuinely not the
    person, and on no others.

    WHAT IT COSTS, AND IT IS A REAL COST: where such a statement exists and its
    count is not the n bound at a coordinate, EVERY family refuses at that
    coordinate, including the descriptive rows that are honestly per-subject. The
    account carries no per-value unit of analysis to narrow it with, and the
    alternative -- guessing which values are per-observation -- is the guess this
    layer exists to remove.
    """
    for seg in re.split(r"(?<=[.;:])\s+|\n", str(text or "")):
        m = _ANALYSIS_UNIT_YIELD.search(seg)
        if not m:
            continue
        k = _count_of(m.group("count"))
        if k is None or k <= 1:
            continue
        return {"n": k, "unit": (m.group("noun") or "").lower(),
                "quote": " ".join(seg.split())[:200]}
    return None


def named_estimator(rx: "re.Pattern[str]", value: dict, captions: dict[str, str],
                    statement: str | None = None,
                    furniture: dict[str, str] | None = None) -> tuple[str, str] | None:
    """`(where the paper says it, what it says)` for one value, or None.

    THE FIVE PLACES A PAPER NAMES ITS OWN ESTIMATOR, and they are the same five
    whatever the statistic is: the column band over the cell, the caption of the
    table it sits in, the table's own FOOTNOTES, the sentence the value was read
    out of, and a sentence of the paper's that governs every such value in it.

    THE FOOTNOTE IS THE FOURTH, ADDED IN WAVE 7D (round 12's F3). On a JATS or
    HTML paper it is not in the served body at all -- `extraction/jats.py`
    strips `table-wrap-foot` before the article text reaches the model -- so a
    JAMA/BMJ-style `Means are weighted to the roll.` under the table had no
    channel to reach this function through, and a caption-only reader called an
    honest weighted mean `impossible`.

    EXTRACTED BECAUSE ONE STATISTIC HAD THEM AND THE OTHERS DID NOT.
    `weighted_percentage_reason` read all four and then returned early unless the
    value was a PERCENTAGE, so a survey-weighted MEAN printed in the same table,
    under the same caption, weighted by the same weights, was checked and
    convicted while the percentage beside it was refused. Only the VOCABULARY
    differs between the two callers now; the places do not.
    """
    loc = value.get("location") or {}
    table_id = str(loc.get("table_id") or "")
    band = str(loc.get("col_label") or "")
    caption = captions.get(table_id) or ""
    footnote = (furniture or {}).get(table_id) or ""
    quote = str(value.get("quote") or "") if loc.get("kind") != "table_cell" else ""
    for where, hay in (("column band", band), ("table's caption", caption),
                       ("table's footnotes", footnote),
                       ("value's own sentence", quote)):
        m = rx.search(hay)
        if m:
            return where, m.group(0).strip()
    if statement:
        return "paper", statement
    return None


def estimated_mean_reason(value: dict, captions: dict[str, str],
                          statement: str | None = None,
                          furniture: dict[str, str] | None = None) -> str | None:
    """Why this mean is not an integer total divided by n, or None.

    ONLY A MEAN, and the test is the account's own word for the statistic. The
    SD beside it is left alone deliberately: `check_sd_or_se` asks whether a
    dispersion is plausible for a variable on a stated range, which a weighted
    dispersion still is, and refusing it would remove a value from a family for a
    reason that is not about that family.
    """
    if str(value.get("statistic") or "") != "mean":
        return None
    got = named_estimator(NOT_A_SIMPLE_MEAN, value, captions, statement, furniture)
    if got is None:
        return None
    where, said = got
    if where == "paper":
        return (f"the paper states {said!r}, so its means are not integer totals divided "
                "by n")
    return (f"the {where} says {said!r}, so this mean is not an integer total divided by "
            "the n bound here -- which is the premise GRIM, GRIMMER and SPRITE all assume")


def normalised_unit(unit: Any) -> str | None:
    """One unit's canonical name, or None where nothing is stated.

    A SYNONYM LOOKUP AND A PLURAL STEM, and nothing cleverer: the question asked
    of it is only ever "are these two the SAME unit?", so a unit the map has
    never heard of is compared against itself and two spellings of one unit are
    made equal. Being wrong here can only ever cost a check.
    """
    s = " ".join(str(unit if unit is not None else "").strip().lower().split())
    if not s:
        return None
    if s in _UNIT_FORMS:
        return _UNIT_FORMS[s]
    s = s.rstrip(".")
    if s in _UNIT_FORMS:
        return _UNIT_FORMS[s]
    stem = s[:-1] if len(s) > 1 and s.endswith("s") else s
    return _UNIT_FORMS.get(stem, stem)


#: A UNIT PRINTED OVER A COLUMN: the band's own comma-tail or parenthetical.
#: `Total review time, h`, `Age, y`, `Body mass (kg)`.
_LABEL_UNIT = re.compile(r"[,(]\s*(?P<unit>[A-Za-z%]{1,12})\.?\s*\)?\s*$")

#: THE PAPER'S OWN STATEMENT OF THE UNIT A QUANTITY WAS RECORDED IN, taken from
#: the sentence that establishes the variable's granularity -- which is the
#: sentence the step of 1 is about, and therefore the sentence that says which
#: unit that step is a step of.
_RECORDED_IN_UNIT = re.compile(
    r"\b(?:recorded|measured|counted|reported|expressed|timed|scored|taken|"
    r"logged|collected|captured|noted)\b[^.;\n]{0,40}?\bin\s+"
    r"(?:whole\s+|complete\s+|full\s+|exact\s+)?(?P<unit>[A-Za-z]{1,12})\b", re.I)


def known_unit(raw: Any) -> str | None:
    """`raw` as a canonical unit, ONLY where it is a unit this module knows.

    THE STRICTER READER, AND IT IS USED WHERE THE UNIT IS INFERRED RATHER THAN
    RECORDED. `normalised_unit` compares an unknown token against itself, which
    is right for two fields a reading FILLED IN; it is wrong for a token pulled
    out of a column band or a sentence, where `Mean (SD)` would make `sd` a unit
    and manufacture a mismatch against a real one. An unknown token here is not a
    unit at all.
    """
    s = " ".join(str(raw if raw is not None else "").strip().lower().split())
    s = s.rstrip(".")
    if not s:
        return None
    stem = s[:-1] if len(s) > 1 and s.endswith("s") else s
    return _UNIT_FORMS.get(s) or _UNIT_FORMS.get(stem)


def printed_unit(value: dict | None) -> tuple[str | None, str]:
    """`(the unit this number is PRINTED in, where that was read)`.

    THE COLUMN BAND IS THE SECOND PLACE, and it is where the unit usually is:
    the schema tells a reading to record `units` "as printed. null when the paper
    prints none", so a table whose unit is printed ONCE, over the column
    (`Total review time, h`), truthfully leaves the cell's own `units` null.
    `named_estimator` already reads the band for estimator words; this reads it
    for the unit, and it can only ever produce a refusal.

    A `%` OVER A COLUMN IS THE STATISTIC'S MARK, NOT THE QUANTITY'S UNIT --
    `n (%)` says the column holds counts and percentages -- so it is excluded by
    name rather than left to manufacture a mismatch on every clinical table.
    """
    stated = normalised_unit((value or {}).get("units"))
    if stated is not None:
        return stated, "the value's own `units`"
    label = str(((value or {}).get("location") or {}).get("col_label") or "")
    m = _LABEL_UNIT.search(label)
    got = known_unit(m.group("unit")) if m else None
    if got is not None and got != "percent":
        return got, f"the column band {label!r}"
    return None, ""


def recorded_unit(var: dict | None) -> tuple[str | None, str]:
    """`(the unit this variable was RECORDED in, where that was read)`.

    THE GRANULARITY SENTENCE IS THE SECOND PLACE, and it is the sentence whose
    step is at issue: `Review time was recorded in whole minutes from the
    dispensing system log` establishes a step of one MINUTE, and `mean * n` is an
    arithmetic claim about the unit the number is printed in.
    """
    stated = normalised_unit((var or {}).get("units"))
    if stated is not None:
        return stated, "the variable's own `units`"
    gran = (var or {}).get("granularity")
    quote = gran.get("quote") if isinstance(gran, dict) else None
    m = _RECORDED_IN_UNIT.search(str(quote or ""))
    got = known_unit(m.group("unit")) if m else None
    if got is not None:
        return got, "the granularity sentence"
    return None, ""


def units_of(value: dict, var: dict | None) -> dict:
    """The unit the number is PRINTED in, beside the unit the variable declares.

    THE ONE THING THE SCHEMA CARRIED AND NOTHING READ. `variable.units` and
    `value.units` are both fields of wave 5's schema, both were being filled
    truthfully, and no line of `premises` or `checks` looked at either -- so a
    quantity RECORDED in whole units and REPORTED in a coarser one was convicted
    by every tool that rests on `mean * n` being a whole number:

        11,369 whole minutes over 28 nurses = 406.0357 min = 6.7673 h -> `6.77`
            GRIM `impossible`, GRIMMER `impossible`, SPRITE `impossible`
        1,939,200 whole grams over 28 nurses = 69.2571 kg -> `69.26`
            GRIM `impossible`

    Both papers are honest, and the identical account written in the RECORDED
    unit is `consistent` throughout. The granularity premise is established from
    a sentence about the unit the values were RECORDED in (`counted in whole
    minutes from the actigraph record`) while `mean * n` is an arithmetic claim
    about the unit they are PRINTED in, and minutes reported in hours move in
    sixtieths. Minutes to hours, grams to kilograms, metres to kilometres and
    dollars to thousands are the commonest reporting conventions there are.

    `agree` IS THREE-VALUED, and None is the ordinary case: most accounts state
    no unit on either side, and an absence is not a disagreement. Only two
    KNOWN units that differ withdraw anything.

    AND EACH SIDE HAS TWO SOURCES, BECAUSE REQUIRING THE UNIT TWICE FAILED OPEN.
    Round 7 measured it: the guard closed the defect only for accounts that
    record the unit on BOTH the value and the variable, and both one-sided shapes
    are ordinary truthful readings -- the unit printed once over the column
    (`Total review time, h`) with the cell's own `units` null, or on the value
    with the variable's null. All three shapes returned GRIM `impossible` on
    11,369 whole minutes printed as `6.77` h, and the fully recorded one refused.
    The less the reading recorded, the more the bridge accused.

    So the PRINTED unit falls back to the column band and the RECORDED unit to
    the sentence that established the step, and both fallbacks read only units
    this module knows (`known_unit`), so an unrecognised token is an absence
    rather than a mismatch. Widening either side can only ever REMOVE a check.

    STATED PLAINLY (wave 7d, item 5, per D73/round 4's F5): THIS PREMISE HAS NO
    MODEL CHANNEL AT ALL. `_LABEL_UNIT` is `[,(]\\s*(?P<unit>[A-Za-z%]{1,12})\\.?
    \\s*\\)?\\s*$` -- an ASCII comma or paren introducing the unit at the very
    end of the band -- so a fullwidth paren (`Practice time（h）`), a square
    bracket (`[h]`), a footnote marker after the unit (`(h)*`, `, h†`), or a
    trailing statistic (`(h), mean (SD)`) are each read as NO unit rather than
    as `h`, and the check this function feeds is silently skipped rather than
    wrongly run. That is the SAFE failure mode -- an unrecognised band costs
    coverage, never an accusation -- and it is why this is a documentation
    decision rather than a build one: the gap is a caption/band-PARSING problem
    (a fixed anchor at the string's own end), not a recall-of-evidence problem
    the other four refusal premises in this wave have, so widening it is a
    different, narrower piece of work than anything else in this file. Narrow
    the LICENCE accordingly: a `printed_in_another_unit` refusal is only ever as
    complete as `_LABEL_UNIT`'s own five-and-more bracket forms, and a reader
    relying on it to catch every reporting-convention mismatch should not
    assume it does.
    """
    vu, vu_from = printed_unit(value)
    ru, ru_from = recorded_unit(var)
    return {"value_units": (value or {}).get("units"),
            "variable_units": (var or {}).get("units"),
            "value_unit_normalised": vu, "variable_unit_normalised": ru,
            "value_unit_source": vu_from or None,
            "variable_unit_source": ru_from or None,
            "agree": None if (vu is None or ru is None) else vu == ru}


#: THE PAPER'S OWN NOTICE THAT IT HAS WITHDRAWN A NUMBER.
#:
#: A value quoted INSIDE a correction notice is indistinguishable from a reported
#: one: it is printed in the paper, its quote verifies verbatim, and its
#: provenance is `printed_text`. So the superseded `8.58` of `Correction. In the
#: originally published article the mean index score at wave 1 was given as 8.58;
#: the correct value is 8.54.` reached GRIM and came back `impossible` -- beside
#: the corrected `8.54`, which is `consistent` -- and the finding accused a paper
#: of an error it had already published a correction for. No field on a value and
#: no member of the refusal vocabulary said "the paper has withdrawn this
#: number", which is why the closed vocabulary grows here rather than a heuristic
#: growing somewhere else.
_CORRECTION_NOTICE = re.compile(
    r"\b(?:correction|corrigendum|errat(?:um|a)|"
    r"originally\s+published|as\s+originally\s+(?:printed|published|reported))\b",
    re.I)

#: The number the notice says WAS printed, and the number it says is right. Both
#: are needed: a notice names two values and only one of them is withdrawn, so a
#: rule that refused every number in a correction sentence would take the
#: corrected value with it.
#:
#: AND TWO SENTENCE TEMPLATES WERE NOT THE WAY JOURNALS WRITE CORRECTIONS. Round
#: 7 measured three ordinary wordings that name the old number as the OBJECT of
#: the verb rather than after `as`, and every one of them left the superseded
#: number checked and accused beside the corrected one:
#:
#:     `Table 2 reported a mean of 8.58; this has been corrected to 8.54.`
#:     `The value 8.58 in Table 2 is wrong; it should be 8.54.`
#:     `... the mean adherence score was 8.58 rather than 8.54.`
#:
#: BOTH HALVES GROW TOGETHER, ALWAYS. The third condition of
#: `withdrawn_by_a_correction` -- that the notice does not ALSO name this number
#: as the corrected one -- is what keeps the replacement checkable, so a wording
#: added to the superseded side whose corrected side is not added too would
#: withdraw the paper's own repair.
_CORRECTION_NUMBER = r"[-+]?\d[\d,]*(?:\.\d+)?%?"
_SUPERSEDED_VALUE = re.compile(
    r"\b(?:given|reported|printed|stated|listed|published|misstated|shown|"
    rf"appeared)\s+(?:incorrectly\s+)?as\s+(?P<old>{_CORRECTION_NUMBER})"
    rf"|\bincorrectly\s+(?:gave|read)\s+(?P<old2>{_CORRECTION_NUMBER})"
    # `Table 2 reported a mean of 8.58`
    r"|\b(?:gave|reported|printed|stated|listed|published|showed|shows|gives?|"
    r"carried|contained|had)\s+(?:an?|the)?\s*(?:[a-z-]+\s+){0,3}?of\s+"
    rf"(?P<old3>{_CORRECTION_NUMBER})"
    # `The value 8.58 in Table 2 is wrong`
    rf"|(?P<old4>{_CORRECTION_NUMBER})\b[^.;]{{0,40}}?\b(?:is|was|are|were)\s+"
    r"(?:incorrect|wrong|in\s+error|erroneous|a\s+typographical\s+error|a\s+typo)\b"
    # `8.58 rather than 8.54`
    rf"|(?P<old5>{_CORRECTION_NUMBER})\s+(?:rather\s+than|instead\s+of|and\s+not)"
    r"\s+[-+]?\d", re.I)
_CORRECTED_VALUE = re.compile(
    r"\bcorrect(?:ed)?\s+(?:value|figure|number|result|mean|estimate)?\s*"
    rf"(?:is|was|should\s+(?:be|read))\s+(?P<new>{_CORRECTION_NUMBER})"
    rf"|\bshould\s+(?:read|be|have\s+read)\s+(?P<new2>{_CORRECTION_NUMBER})"
    rf"|\bcorrected\s+to\s+(?P<new3>{_CORRECTION_NUMBER})"
    rf"|{_CORRECTION_NUMBER}\s+(?:rather\s+than|instead\s+of|and\s+not)\s+"
    rf"(?P<new4>{_CORRECTION_NUMBER})", re.I)


def _numbers(rx: "re.Pattern[str]", text: str) -> set[float]:
    out: set[float] = set()
    for m in rx.finditer(text):
        for raw in m.groupdict().values():
            got = read_plain(str(raw or "").replace(",", ""))
            if got is not None:
                out.add(got["value"])
    return out


def withdrawn_by_a_correction(value: dict) -> str | None:
    """The paper's own correction notice that supersedes THIS printed number.

    THREE CONDITIONS, AND THE THIRD IS WHAT KEEPS THE CORRECTED VALUE CHECKABLE:
    the value's own quote is a correction notice, the notice names this number as
    the one it is withdrawing, and it does NOT name it as the corrected one. A
    notice that revises an n rather than a mean (`The sample size was misstated
    as 28 ...; twenty-six nurses were assessed (n = 26)`) therefore withdraws the
    28 and leaves the 26 alone, which is the direction that matters.

    IT READS THE VALUE'S OWN QUOTE AND NOT THE DOCUMENT. A correction notice
    somewhere in a paper does not withdraw every number in it, and a rule that
    read the whole served text would do exactly that.
    """
    quote = str(value.get("quote") or "")
    if not quote or not _CORRECTION_NOTICE.search(quote):
        return None
    lit = read_plain(value.get("printed"))
    if lit is None:
        return None
    old = _numbers(_SUPERSEDED_VALUE, quote)
    if lit["value"] not in old or lit["value"] in _numbers(_CORRECTED_VALUE, quote):
        return None
    return " ".join(quote.split())[:200]


#: THE PAPER HANDING A NUMBER TO SOMEBODY ELSE.
#:
#: A results or discussion sentence routinely carries two papers' numbers -- `Our
#: patients took a mean of 5.39 medicines, more than the 4.70 reported by Chen
#: and colleagues.` -- and both of them are printed in this paper, both verify
#: verbatim inside the quote, and both are `printed_text`. Where the reading
#: records the second as a value at this study's coordinate, ANOTHER STUDY's mean
#: is adjudicated against THIS study's n and scale: measured at GRIM `impossible`
#: on 4.70, beside our own 5.39 `consistent`.
#:
#: THE ONE THING THAT SAVED IT WAS ACCIDENTAL. Where the sentence also prints the
#: other study's sample size, `population_sizes` sees a population larger than the
#: bound n and refuses BOTH values; a citation that does not repeat the n -- the
#: ordinary form -- had no guard at all, while the evidence sat in the value's own
#: quote and was read by nothing.
#:
#: IT IS THE NUMBER THAT IS ATTRIBUTED, NOT THE SENTENCE. Refusing every value in
#: a sentence that cites somebody would take OUR number with theirs, so the phrase
#: has to follow THIS number with no other number in between -- which is what
#: `more than the 4.70 reported by` says and `5.39 medicines, more than the 4.70
#: reported by` does not. NOT case-insensitive, deliberately: the capital that
#: starts a surname is most of the evidence that a person is being named.
#: `in` IS DELIBERATELY NOT A PREPOSITION THE FIRST BRANCH TAKES. `reported in
#: Table 2` is this paper pointing at its own furniture, not at somebody else's
#: paper, and a capital letter cannot tell the two apart. `by` can: `reported by
#: Table 2` is not a sentence anyone writes. The `et al.` branch keeps `in` and
#: `of`, because there the author phrase is what identifies the owner.
_ATTRIBUTION = (
    r"(?:reported|found|observed|obtained|described|published|documented|noted|"
    r"recorded|estimated)\s+by\s+(?:the\s+)?[A-Z]"
    r"|(?:by|of|in|from)\s+[A-Z][A-Za-z'’-]+\s+(?:et\s+al|and\s+colleagues|"
    r"and\s+co-?workers|and\s+co-?authors)"
    r"|in\s+the\s+(?:study|trial|cohort|sample|analysis|series)\s+(?:by|of)\s+[A-Z]")
#: AND A COMPARISON WORD IN THE GAP IS THE BOUNDARY BETWEEN THE TWO PAPERS.
#: `The mean was 5.39, higher THAN in the study by Chen` attributes Chen's
#: number, which the sentence does not print, and OURS is the one beside the
#: phrase; the intervening `than` is what says the phrase belongs to the other
#: side of the comparison. In `more than the 4.70 reported by Chen` the `than`
#: sits BEFORE their number, not between it and the phrase.
_ATTRIBUTED_VALUE = re.compile(
    r"(?<![\d.])(?P<num>[-+]?\d[\d,]*(?:\.\d+)?%?)(?![\d])"
    r"(?:(?!\b(?:than|versus|vs\.?|compared|against)\b)[^\d;]){0,25}?"
    r"\b(?:" + _ATTRIBUTION + r")")


def attributed_to_another_study(value: dict) -> str | None:
    """The phrase in this value's OWN quote that hands THIS number to another
    paper, or None.

    IT READS THE VALUE'S OWN QUOTE AND NOT THE DOCUMENT, for the same reason
    `withdrawn_by_a_correction` does: a citation somewhere in a paper does not
    make every number in it somebody else's.

    AND IT IS A FLOOR RATHER THAN A CEILING, stated so nobody reads it as one.
    The phrase must FOLLOW the number, so `Chen and colleagues reported a mean of
    4.70` is missed: a rule reading backwards would have to decide how far back
    the attribution reaches, and in `Chen reported 4.70; our patients took 5.39`
    the wrong answer takes our own number with theirs. Missing one costs a
    refusal we would have liked; guessing one costs a check we should keep.
    """
    quote = str(value.get("quote") or "")
    lit = read_plain(value.get("printed"))
    if not quote or lit is None:
        return None
    for m in _ATTRIBUTED_VALUE.finditer(quote):
        got = read_plain(str(m.group("num")).replace(",", ""))
        if got is not None and got["value"] == lit["value"]:
            return " ".join(m.group(0).split())[:120]
    return None


def _is_percentage(value: dict, lit: dict | None) -> bool:
    """Is this value a percentage, by the account's own word or the paper's own mark?

    THE VARIABLE'S KIND IS NOT ASKED, and it is the same rule `_percent_allowed`
    keeps: a `count` of 12 sits on a `percentage_of_subjects` variable perfectly
    honestly, and reading the kind here would withdraw the COUNT of a weighted
    pair as well as the percentage -- removing it from every other family for a
    reason that is not about it.
    """
    return (str(value.get("statistic") or "") == "percentage"
            or bool(lit is not None and lit.get("is_percent")))


def weighted_percentage_reason(value: dict, lit: dict | None,
                               captions: dict[str, str],
                               statement: str | None = None,
                               furniture: dict[str, str] | None = None) -> str | None:
    """Why this percentage is not the printed count's own quotient, or None.

    FOUR PLACES A PAPER SAYS IT, and round 4 measured that none of them stopped
    the check: `No. (weighted %)` in the column band, a caption stating that
    percentages are weighted and counts unweighted, the same sentence in Methods,
    `No. (age-standardized %)`, and the prose `the weighted prevalence was
    31.4%`. All five ran and all five accused. A FIFTH -- a table's own
    FOOTNOTE, where this statement is JAMA/BMJ house style -- is round 12's F3.

    ONLY PERCENTAGES, and the test for one is the account's own word or the
    paper's own `%`. A count is left alone: the count is not the estimator the
    weighting changes, and refusing it would remove it from every other family
    for a reason that is not about it.
    """
    if not _is_percentage(value, lit):
        return None
    got = named_estimator(WEIGHTED_PERCENTAGE, value, captions, statement, furniture)
    if got is None:
        return None
    where, said = got
    if where == "paper":
        return (f"the paper states {said!r}, so its percentages are not the printed "
                "counts' own quotients")
    return (f"the {where} says {said!r}, so this percentage is not "
            "the printed count divided by any denominator this account carries")


def literal_of(value: dict) -> tuple[dict | None, str]:
    """The bridge's own reading of one printed literal, and why it refuses.

    THE `%` SIGN IS NOT REQUIRED AND NOT FORBIDDEN ON A PERCENTAGE. `85.94%` and
    `73.0` are both percentages: which of the two a paper prints is a typographic
    choice of the column header's. IT IS FORBIDDEN ON ANYTHING ELSE. A value the
    reading typed `mean`, printed `86.75%`, had the sign stripped and entered
    GRIM as a mean of 86.75 whole-number ratings -- a number the paper does not
    contain, on a scale it does not have.
    """
    got = read_plain(value.get("printed"))
    if got is None:
        return None, repr(str(value.get("printed"))[:40])
    return got, ""


def cross_check(value: dict, got: dict | None) -> dict:
    """What the account said about this literal, beside what the bridge read."""
    return {"value_id": value.get("id"), "printed": value.get("printed"),
            "bridge_value": (got or {}).get("value"),
            "bridge_decimals": (got or {}).get("decimals"),
            "account_numeric": value.get("numeric"),
            "account_decimals": value.get("decimals"),
            "account_printed_form": value.get("printed_form"),
            "agrees": bool(got is not None
                           and value.get("numeric") == got["value"]
                           and value.get("decimals") == got["decimals"])}


def _one_line_quote(raw: Any, limit: int = 200) -> str:
    """One passage, whitespace collapsed, for a record a reader will read."""
    return " ".join(str(raw or "").split())[:limit]


def _percent_allowed(value: dict, var: dict | None) -> bool:
    if str(value.get("statistic") or "") == "percentage":
        return True
    kind = str((var or {}).get("kind") or "")
    return kind in PERCENTAGE_KINDS or kind == "proportion"


def value_premise(value: dict, var: dict | None, index: dict,
                  captions: dict[str, str], *,
                  notes: dict[str, str] | None = None,
                  weighting: str | None = None,
                  n_varies: str | None = None,
                  estimator: str | None = None,
                  read_estimator: dict | None = None,
                  read_correction: dict | None = None,
                  read_varying_n: dict | None = None,
                  furniture: dict[str, str] | None = None) -> dict:
    """Everything a reader needs to decide whether this value may be used.

    THE FOUR DOCUMENT-LEVEL FACTS ARE PASSED IN, NOT RE-READ. `notes` (what the
    paper's prose says each table is), `weighting` (its statement that its
    percentages are weighted), `n_varies` (its statement that the analysis n
    differs by measure) and `estimator` (its statement of what its means are)
    are properties of the PAPER, computed once by `stamp`, so a per-value reader
    cannot arrive at a different answer for two rows of the same table.

    `furniture` IS THE TABLE'S OWN FOOTNOTES, BY TABLE ID (wave 7d, round 12's
    F3): a fifth channel `weighted_percentage_reason`, `estimated_mean_reason`
    and `analysis_n_varies` below now all read, beside the column band, the
    caption, the value's own sentence and a document-wide governing sentence.

    `read_estimator`, `read_correction` AND `read_varying_n` ARE MODEL READINGS
    THAT MAY ONLY ADD A REFUSAL (wave 7c; `varying_n` round 18). All three
    premises REFUSE a value when they hold, so the one dangerous direction is a
    model saying `no` where the vocabulary said `yes` -- that would let a check
    run on a premise a rule had already withdrawn. So `premise_reading.index`
    never hands one a negative verdict, and these three parameters can only ever
    turn a checkable value into a refused one.

    AND `read_varying_n` STOPS HERE. It sets `analysis_n_varies`, which
    `checks._Index.group_n` reads as a terminal refusal of the value being
    checked; it does NOT reach `n_premise`, whose `usable` decides which n ROWS
    are kept. That separation is the whole safety argument of
    `adjudication_n.py`, because dropping one of two disagreeing n rows resolves
    `ambiguous_n` and makes a check RUN at a denominator that was refused --
    measured, and pinned by round 18's
    `test_an_n_rows_eligibility_is_not_reachable_from_a_reading`.
    """
    prov, prov_why = provenance(value)
    bind_state = binding(value)
    lit, lit_why = literal_of(value)
    why_model = model_output_reason(value, var, index, captions, notes)
    why_weighted = weighted_percentage_reason(value, lit, captions, weighting, furniture)
    why_estimator = estimated_mean_reason(value, captions, estimator, furniture)
    why_withdrawn = withdrawn_by_a_correction(value)
    if read_estimator and read_estimator.get("establishes"):
        said = (f"a model read {str(read_estimator.get('quote'))[:120]!r} and says this "
                f"number is not a plain total over the n bound here: "
                f"{str(read_estimator.get('reason'))[:120]!r}")
        if _is_percentage(value, lit):
            why_weighted = why_weighted or said
        elif str(value.get("statistic") or "") == "mean":
            why_estimator = why_estimator or said
    if (read_correction and read_correction.get("establishes")
            and lit is not None and not why_withdrawn):
        why_withdrawn = _one_line_quote(read_correction.get("quote"))
    # THE PAPER'S OWN STATEMENT THAT ITS ANALYSIS n VARIES BY MEASURE, from this
    # value's own table caption, its table's FOOTNOTE, or the served text -- and
    # then, only where all three are silent, from a model reading.
    #
    # THE STAMP IS THE CANDIDATE'S QUOTE AND NEVER THE MODEL'S PROSE. The quote
    # is a verbatim span of the served text that `adjudication_n` supplied, so
    # what reaches `_n_detail` and the docket is the paper's own words; the
    # model's `reason` is recorded in `model_reading` below and is read by
    # nothing that computes.
    loc = value.get("location") or {}
    n_varies_here = (_governing_statement(
        _N_VARIES, captions.get(str(loc.get("table_id") or "")) or "")
        or _governing_statement(
            _N_VARIES, (furniture or {}).get(str(loc.get("table_id") or "")) or "")
        or n_varies)
    if not n_varies_here and read_varying_n and read_varying_n.get("establishes"):
        n_varies_here = _one_line_quote(read_varying_n.get("quote"))
    why_theirs = attributed_to_another_study(value)
    units = units_of(value, var)
    disputed = bool(value.get("statistic_disputed"))
    reasons: list[dict] = []
    if prov is None:
        reasons.append({"reason": "provenance_not_printed", "detail": prov_why})
    if bind_state == "model_only" and value.get("variable_id"):
        reasons.append({"reason": "binding_model_only", "detail": "id_check `null`"})
    elif bind_state in ("contradicted", "unchecked"):
        reasons.append({"reason": "binding_not_corroborated",
                        "detail": f"id_check `{value.get('id_check')}`"})
    if why_model:
        reasons.append({"reason": "reports_model_output", "detail": why_model})
    if why_weighted:
        reasons.append({"reason": "percentage_is_weighted", "detail": why_weighted})
    if why_estimator:
        reasons.append({"reason": "mean_is_not_a_simple_average", "detail": why_estimator})
    if why_withdrawn:
        reasons.append({"reason": "value_withdrawn_by_a_correction",
                        "detail": f"the paper's own notice says {why_withdrawn!r}, and this "
                                  f"is the number it withdraws"
                                  + (f" (read by a model: "
                                     f"{str(read_correction.get('reason'))[:120]!r})"
                                     if read_correction
                                     and read_correction.get("establishes") else "")})
    if why_theirs:
        reasons.append({"reason": "value_attributed_to_another_study",
                        "detail": f"the value's own sentence says {why_theirs!r}, so this "
                                  "number is another paper's and not this one's claim"})
    if units["agree"] is False:
        reasons.append({"reason": "printed_in_another_unit",
                        "detail": f"printed in `{units['value_units']}` on a variable the "
                                  f"account records in `{units['variable_units']}`"})
    if disputed:
        loc = value.get("location") or {}
        reasons.append({"reason": "statistic_kind_disputed",
                        "detail": f"`{value.get('statistic')}` under "
                                  f"`{loc.get('col_label')}` is read as another kind "
                                  "elsewhere in this paper"})
    if lit is None:
        reasons.append({"reason": "printed_not_plain_numeral", "detail": lit_why})
    elif lit["is_percent"] and not _percent_allowed(value, var):
        reasons.append({"reason": "percent_sign_on_a_non_percentage",
                        "detail": f"printed {str(value.get('printed'))[:20]!r} on a "
                                  f"`{value.get('statistic')}` of kind "
                                  f"`{(var or {}).get('kind') or 'none'}`"})
    return {
        "provenance": prov, "provenance_why": prov_why,
        # THE DENOMINATOR THE VALUE'S OWN SENTENCE STATES, where it states one.
        # Only for located prose, because a table cell has no sentence of its
        # own; `group_n` reads it as a CONTRADICTION of a smaller bound n and
        # never as a denominator to use.
        "denominator_stated_in_quote": (population_sizes(value.get("quote"))
                                        if prov == "printed_text" else []),
        # THE STAGE OF THE STUDY THE VALUE'S OWN SENTENCE NAMES. Read here, and
        # only from located prose, so that `group_n` can ask whether a retention
        # count the paper states elsewhere is about THIS value's wave -- and can
        # answer "we do not know" rather than "the enrolled n will do".
        "stages_named_in_quote": (stage_phrases(value.get("quote"))
                                  if prov == "printed_text" else []),
        # THE PAPER'S OWN STATEMENT THAT ITS ANALYSIS n VARIES BY MEASURE, from
        # this value's own table caption, its table's FOOTNOTE, or the served
        # text. `group_n` reads it as a WITHDRAWAL of the group's n and never as
        # a denominator to use: the paper says the number analysed for this row
        # is not the number analysed for the group, and does not say what it is.
        #
        # THE FOOTNOTE WAS NOT READ UNTIL WAVE 7D (round 12's F3): the comment
        # above already said "table footnote/caption" while the code below read
        # only the caption, which is the shape this defect keeps taking -- the
        # prose said what the code did not yet do.
        #
        # AND THE FIFTH CHANNEL IS A MODEL READING (round 18), resolved above:
        # the three vocabulary channels are asked first and a reading is
        # consulted only where all three are silent, so the regex stays the
        # floor and a verdict can only ever add a refusal.
        "analysis_n_varies": n_varies_here,
        "binding": bind_state, "id_check": value.get("id_check"),
        # THE UNIT THE NUMBER IS PRINTED IN, BESIDE THE UNIT THE VARIABLE
        # DECLARES. Recorded on every value, whether they agree or not, because
        # a reader of the record wants to see that the question was asked.
        "units": units,
        "withdrawn_by_a_correction": why_withdrawn,
        # WHAT A MODEL WAS ASKED ABOUT THIS VALUE AND WHAT IT ANSWERED (wave
        # 7c). Recorded whether it fired or not, because a reader weighing a
        # refusal has to be able to see whose reading it rests on.
        "model_reading": {"estimator": read_estimator, "correction": read_correction,
                          "varying_n": read_varying_n}
        if (read_estimator or read_correction or read_varying_n) else None,
        # THE PHRASE THAT HANDS THIS NUMBER TO ANOTHER PAPER, from the value's
        # own sentence. Recorded on every value, whether it fires or not.
        "attributed_to_another_study": why_theirs,
        "literal": lit, "literals": cross_check(value, lit),
        "descriptive": {"col_label": loc.get("col_label"),
                        "caption": captions.get(str(loc.get("table_id") or "")),
                        # RECORDED, NOT USED. See `model_output_reason`: a
                        # covariate's mean in Table 1 is a descriptive statistic.
                        "variable_role": (var or {}).get("role"),
                        "variable_kind": (var or {}).get("kind"),
                        "reports_model_output": why_model,
                        "percentage_is_weighted": why_weighted,
                        "mean_is_not_a_simple_average": why_estimator},
        "disputed": disputed,
        "reasons": reasons,
    }


# --------------------------------------------------------------------------
# The denominator's own premises
# --------------------------------------------------------------------------

def percentage_window(percentage: float, decimals: int) -> tuple[float, float]:
    """The interval a printed percentage asserts, as `check_count_percent` reads it.

    ASYMMETRIC, AND DELIBERATELY THE TOOL'S OWN WINDOW: a full ulp below and a
    half ulp above, because a truncated percentage is always at or below the
    true value. Restating a narrower window here would let the bridge and the
    tool disagree about what the paper printed, which is the two-readers defect
    this package keeps finding.
    """
    ulp = 10.0 ** -int(decimals)
    return percentage - 0.5 * ulp, percentage + ulp


def base_fits(count: Any, percentage: Any, decimals: Any, n: Any) -> bool:
    """Does `n` reproduce the printed percentage from the printed count?"""
    try:
        lo, hi = percentage_window(float(percentage), int(decimals))
        return bool(n) and lo <= 100.0 * float(count) / float(n) <= hi
    except (TypeError, ValueError, ZeroDivisionError):
        return False


#: How many alternative bases are worth naming, and how wide an interval is
#: worth walking. A percentage printed to few decimals admits a wide band of
#: denominators; naming the first few is a fact for the reader, and walking a
#: band of millions is a way to stall a run.
_MAX_ALTERNATIVE_BASES = 5
_MAX_BASE_INTERVAL = 100_000


def other_bases_that_fit(count: Any, percentage: Any, decimals: Any, n: Any,
                         ceiling: Any = None) -> list[int]:
    """The integer denominators OTHER than `n` that reproduce the printed
    percentage from the printed count.

    THIS IS THE PREMISE `check_count_percent` NEVER HAD. The tool compares
    `100 * count / n` against the printed percentage, and the bridge supplies
    `n` from POSITION -- the n rows at this value's coordinate -- with nothing
    testing that this n is THAT percentage's base. The tool's own escape hatch
    is one-sided: `count >= n` returns `indeterminate` because the base must be
    larger, but the commonest case by far is a base that is SMALLER (a subgroup,
    a row percentage, "of those with complete data"), where `count < n` and it
    returns `suspicious` on a table that did nothing wrong.

    So the base is treated as what it is -- a premise -- and the paper's own two
    numbers are the evidence about it. Together the printed count and the
    printed percentage pin the denominator down to an interval. Three cases:

      * `n` is in that interval: the pair agrees and the check runs (and clears).
      * the interval holds NO integer at all: no reading of the base rescues the
        arithmetic, so the disagreement is about the arithmetic and the check
        runs. This is the case the family exists for -- `142 (73.0)` at n = 200
        implies 194.5, and no integer denominator produces 73.0 from 142.
      * the interval holds an integer that is not `n`: the accusation would rest
        entirely on our having chosen `n`, and the paper's own numbers name an
        alternative. Refused, with the alternative in the docket.

    AND AN ALTERNATIVE HAS TO BE A DENOMINATOR THIS PAPER COULD HAVE. `ceiling`
    is the largest number of subjects the account anywhere prints; an integer
    above it is arithmetic, not a base. Without that bound, `26 (0.867%)` -- a
    proportion printed with a `%` sign, which is a hundredfold error and not a
    different base -- was excused by the denominators 2,996 to 3,000 in a paper
    of thirty people.

    Nothing here can add a check: it only ever withdraws one, and only where the
    verdict would have been an accusation (a base that fits is never refused).
    """
    try:
        c = float(count)
        p = float(percentage)
        d = int(decimals)
    except (TypeError, ValueError):
        return []
    if c <= 0:
        # A zero numerator is zero at every denominator, so no denominator is
        # distinguished from any other and the pair says nothing about the base.
        return []
    lo, hi = percentage_window(p, d)
    if hi <= 0:
        return []
    here = exact_int(n)
    top = max([k for k in (here, exact_int(ceiling)) if k is not None] or [0])
    if top <= 0:
        return []
    # A LOWER EDGE AT OR BELOW ZERO DOES NOT MEAN THERE IS NO ALTERNATIVE. It
    # means EVERY denominator from `100 * count / hi` upward reproduces the
    # printed pair -- a percentage that rounds to zero says only "small" -- and
    # returning [] for that said the opposite to the one caller there is, which
    # reads an empty list as "no reading of the base rescues the arithmetic" and
    # RUNS the check. Measured: `1 (0.0)` at a coordinate whose n is 28, in a
    # paper that prints 4,000 patients on its register, came back `suspicious`.
    # The ceiling is what bounds the set, exactly as it does for a finite
    # interval: an integer above it is arithmetic rather than a base this paper
    # could have used, and if the interval starts above the ceiling the pair is
    # unreproducible at any base the paper has, which is the case the family
    # exists for.
    m_lo = 100.0 * c / hi
    m_hi = float(top) if lo <= 0 else 100.0 * c / lo
    if m_lo > top:
        return []
    # A CAP, NOT A BAIL. The walk below stops at `_MAX_ALTERNATIVE_BASES`, so a
    # wide interval costs nothing to enter; what it must not do is return the
    # EMPTY list, which is the word for "no base fits" and would let the check
    # run on the widest evidence there is that the base is not pinned.
    m_hi = min(m_hi, m_lo + _MAX_BASE_INTERVAL)
    out: list[int] = []
    for m in range(max(int(m_lo - 1e-9) + 1, 1), min(int(m_hi + 1e-9), top) + 1):
        if here is not None and m == here:
            continue
        out.append(m)
        if len(out) >= _MAX_ALTERNATIVE_BASES:
            break
    return out


#: A denominator's `source`, closed. `printed` is a row at the value's own
#: coordinate; `study_applies_to_all_groups` is a study-level figure the sentence
#: says applies to every group; `event_count_row` is a lone integer nothing else
#: in the paper corroborates, which may be a count of EVENTS rather than of
#: subjects. `declared_group` IS DECLARED AND NOT REACHED: the bridge never takes
#: a denominator from the structure alone -- the structure only ever CONFIRMS or
#: CONTRADICTS a printed one -- and the member is named so the vocabulary says
#: that rather than leaving it as an absence.
N_SOURCES = frozenset({"printed", "study_applies_to_all_groups", "declared_group",
                       "event_count_row"})


def n_premise(value: dict, premise: dict) -> dict:
    """The premises of a value that serves as a denominator.

    THE n IS AN INPUT AND IS GATED AS ONE. It was not: the n went from the
    account into `args["n"]` having been checked for nothing but its literal, so
    a denominator read off a FIGURE reached an exact GRIM call stamped
    `provenance: printed_table`; an n whose quote never verified did the same;
    and an n row the name join CONTRADICTS supplied every denominator in a run
    while the same row was refused everywhere else.

    NON-POSITIVE IS ITS OWN FACT, and it is the one that cannot be argued with.
    A denominator of 0 or -30 is not a small denominator, it is not a
    denominator; the tools mostly returned `indeterminate` on one, which is luck
    rather than design -- SPRITE returned `suspicious` on n = -30, an accusation
    computed from a number no paper printed.
    """
    n = is_plain_integer(value.get("printed"))
    positive = n is not None and n > 0
    usable = (premise["provenance"] is not None
              and premise["binding"] not in ("contradicted", "unchecked")
              and not premise["disputed"]
              and positive)
    quote = str(value.get("quote") or "")
    return {
        "provenance": premise["provenance"],
        "binding": premise["binding"],
        "disputed": premise["disputed"],
        "integer": n,
        "positive": positive,
        "source": ("study_applies_to_all_groups" if value.get("applies_to_all_groups")
                   and not (value.get("coordinate") or {}).get("group_id")
                   else "printed"),
        # RECORDED, AND NO LONGER A WITNESS. See `n_corroboration`: a paper that
        # prints its EVENT count in the sample-size notation -- `Adverse events
        # were recorded during the trial (n = 18).` -- corroborated itself, and
        # that is precisely the confusion the corroboration test exists to
        # prevent. The fact is still stamped because a reader of the record
        # wants it.
        #
        # THE LOOKAHEAD WAS ALSO WRONG IN THE OTHER DIRECTION. `(?![\d.])`
        # rejected a sentence-final period, so `the enrolled sample was n = 40.`
        # did NOT match while `(n = 18).` did -- the wrong one of the two.
        # A digit may not follow, and a decimal point may not introduce more
        # digits; a full stop is just a full stop.
        "states_n": bool(n is not None
                         and re.search(r"\b[nN]\s*[=:]\s*" + re.escape(str(n))
                                       + r"(?!\d)(?!\.\d)", quote)),
        "usable": usable,
    }


def n_corroboration(rows: list[dict], n: int, group: dict) -> list[dict]:
    """What, BESIDES one row, says this integer is the number of SUBJECTS.

    THE DENOMINATOR IS THE ONE PREMISE EVERY FAMILY TURNS ON, and a lone integer
    at a coordinate is not evidence of it. Round 2's case: the only `statistic:
    n` row at a coordinate printed 57 -- a count of falls among 30 people -- the
    group declared no n of its own, and every check in the run divided by 57.

    THREE WITNESSES, AND THE FOURTH WAS WITHDRAWN IN ROUND 3. It was the row's
    own quote printing `n = <that integer>`, admitted on the argument that the
    notation is the paper's own mark for a sample size. It is not: `Adverse
    events were recorded during the trial (n = 18).` is ordinary published
    prose, and it made an EVENT COUNT the denominator of `9 (30.0%)` of the 30
    intervention participants -- the exact confusion this test exists to
    prevent, walking in through one of its own witnesses. A row cannot
    corroborate itself; that is what the word means.

    IT IS A CORROBORATION TEST AND NEVER A CONTRADICTION TEST. A label that
    prints some OTHER number is not evidence against the n -- `Intervention
    (2 sites)` is a fact about sites -- so nothing here can refuse a denominator
    that another witness supports.

    AND THE LABEL'S NUMERAL HAD TO BE ASKED WHAT IT COUNTS. The witness accepted
    ANY numeral in the group's label as evidence for a lone n, and the commonest
    numeral in a group label is a DURATION: `12-month cohort`, `6-week arm`,
    `2019 cohort`. Round 7's case is a cluster design supplying the matching
    integer honestly -- `Twelve community pharmacies took part (n = 12)` under a
    group labelled `12-month cohort` -- so the two met, the lone n was
    corroborated, and a patient-level mean of 151/30 = 5.03 came back GRIM
    `impossible` at n = 12. The prose form of the same confusion is already
    guarded (`denominator_contradicted_by_the_sentence` reads the value's own
    sentence); a table cell has no sentence, so nothing narrowed it there.
    """
    found: list[dict] = []
    declared = exact_int(group.get("n"))
    if declared is not None and declared == n:
        found.append({"by": "declared_group_n", "detail": group.get("n_source")})
    for field in ("n_printed", "label", "description"):
        if numeral_counts_subjects(group.get(field), n):
            found.append({"by": f"group_{field}", "detail": str(group.get(field))[:60]})
            break
    if len(rows) > 1:
        found.append({"by": "a second row printing the same integer",
                      "detail": ", ".join(str(r.get("id")) for r in rows[1:])})
    return found


#: A POPULATION THE SENTENCE ITSELF REPORTS OVER. `The 240 patients of the
#: intervention clinics attended a mean of 3.4 visits` states its own
#: denominator, in the paper's own words, and it is not the `n = 6` clinics the
#: structure declares for that arm.
#:
#: THE PLURAL NOUN A PAPER COUNTS ITS SUBJECTS IN. Regular plurals end in `s`;
#: the irregular ones a paper actually uses to name PEOPLE do not, and the rule
#: was `[A-Za-z][A-Za-z-]{2,}s` alone -- so `The 21 children who ate a school
#: lunch had a mean score of 11.90` stated no population at all, on a pediatric
#: paper where `children` is the word for the thing being counted. ONE
#: definition, two readers (`_POPULATION` and `_SUBJECT_COUNT`).
_PLURAL_NOUN = (r"(?:[A-Za-z][A-Za-z-]{2,}s|children|men|women|people|mice|"
                r"personnel|staff|offspring)")

#: `one`..`nineteen` and the tens. Papers open a sentence with a number spelled
#: out because a house style forbids a numeral there -- `Thirty-four children
#: were sampled` -- and that is exactly where a paper prints its TOTAL.
_UNITS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9,
}
_TEENS: dict[str, int] = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS: dict[str, int] = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}


#: The multipliers a spelled-out number uses. `million` is deliberately absent:
#: no paper counts its subjects in millions, and a grammar that admits one admits
#: a service-area population as a percentage base.
_SCALES: dict[str, int] = {"hundred": 100, "thousand": 1000}


def _alt(words) -> str:
    return "|".join(sorted(words, key=len, reverse=True))


#: 1..99, 1..999, 1..999,999 -- a GRAMMAR rather than a lookup, and it carries no
#: capture groups so that `_POPULATION` and `_SUBJECT_COUNT` can embed it without
#: renumbering their own.
_SPELLED_99 = (rf"(?:(?:{_alt(_TENS)})(?:[-\s](?:{_alt(_UNITS)}))?"
               rf"|(?:{_alt({**_UNITS, **_TEENS})}))")
_SPELLED_999 = (rf"(?:{_SPELLED_99}[-\s]+hundred(?:[-\s]+and)?"
                rf"(?:[-\s]+{_SPELLED_99})?|{_SPELLED_99})")
_SPELLED = re.compile(
    rf"\b(?:{_SPELLED_999}[-\s]+thousand(?:[-\s]+and)?(?:[-\s]+{_SPELLED_999})?"
    rf"|{_SPELLED_999})\b", re.I)


def read_spelled(text: Any) -> int | None:
    """The integer a number spelled out in words denotes, or None.

    IT USED TO STOP AT NINETY-NINE, and the argument for the bound was that every
    use of this reader can only ever RAISE A CEILING and so REMOVE a check. That
    is true of the reader and FALSE OF THE CONSEQUENCE: the ceiling it raises is
    `paper_max_n`, which bounds what may count as an ALTERNATIVE percentage base,
    and a base the ceiling excludes is not a base named -- it is a check that
    RUNS and accuses. Measured: `Nine of the eligible nurses (8.0%)` in a paper
    whose cohort is printed as `One hundred and twelve nurses` returned
    `suspicious`, because 9/112 = 8.0357% and 112 sat above a ceiling of 99.

    SO IT IS A GRAMMAR NOW, bounded at the thousands, which is where a count of
    subjects stops. Composition is the only thing that changed: the words are the
    same words, and a phrase this grammar cannot parse still returns None.
    """
    s = str(text or "").strip()
    return spelled_value(s) if _SPELLED.fullmatch(s) else None


def spelled_value(text: Any) -> int | None:
    """The value of a spelled-out number, read word by word.

    A PARSER RATHER THAN CAPTURE GROUPS. The old reader pulled three numbered
    groups out of the match, which is why it could not grow past ninety-nine
    without renumbering the two patterns that embed it. Reading the WORDS makes
    the grammar and the arithmetic independent, so `_SPELLED` can be extended
    without touching either caller.
    """
    total, current, seen = 0, 0, False
    for word in re.split(r"[-\s]+", str(text or "").strip().lower()):
        if not word or word == "and":
            continue
        if word in _UNITS or word in _TEENS or word in _TENS:
            current += (_UNITS.get(word) or _TEENS.get(word) or _TENS[word])
        elif word == "hundred":
            current = (current or 1) * 100
        elif word == "thousand":
            total += (current or 1) * 1000
            current = 0
        else:
            return None
        seen = True
    return (total + current) if seen else None


#: A COUNT OF SUBJECTS, as a paper prints one: an integer -- spelled out, grouped
#: by thousands, or bare -- followed by the plural noun it counts.
#:
#: THE ADJECTIVES BETWEEN THE TWO ARE THE PAPER'S CHOICE AND THE BUDGET WAS OURS.
#: The gap allowed at most TWO whole words and no punctuation, so `One hundred
#: and twelve eligible registered community pharmacists` and `One hundred and
#: twelve eligible, registered pharmacists` printed the cohort and were not read,
#: while `One hundred and twelve eligible pharmacists` was. This reader feeds ONE
#: thing -- the ceiling on what may count as an alternative percentage base --
#: and round 6's argument settles the direction: a base the ceiling excludes is
#: not a base named, it is a check that RUNS and accuses. Measured: 9 of the 112
#: screened (`8.0`) came back `suspicious` at the coordinate's n = 28 with three
#: adjectives in the sentence and refused with one. Reading loosely here costs
#: coverage and cannot cost an accusation, which is why the budget is four words
#: and a comma rather than two words and nothing.
#: THE MARKS A PAPER PUTS BETWEEN THOUSANDS. The comma is the only one this
#: repo read, and it is the only one an American journal uses: a space (SI and
#: every European convention, in four different Unicode widths after a PDF
#: conversion), the Swiss apostrophe, and the full stop are all ordinary printed
#: forms of the same number.
#:
#: MEASURED (round 10), and the direction is what makes it urgent rather than
#: cosmetic: on `The club register lists 1 240 members.` the ceiling read 240 --
#: the TAIL of the number, not merely a miss -- so `other_bases_that_fit`
#: returned no alternative at all, which `to_count_percent_kwargs` reads as `no
#: reading of the base rescues the arithmetic`, and an honest `6 members of the
#: register (0.5%)` over a base of 1240 came back `suspicious`. With `1,240` the
#: same paper refuses. Five separator conventions accused.
#:
#: READING THE FULL STOP AS A GROUP MARK IS DELIBERATE AND IS SAFE HERE AND
#: NOWHERE ELSE. `2.500 points` may be two-and-a-half points, and this reader
#: would call it 2500. That is the direction the docstring below states: the only
#: consumer is the CEILING on an alternative percentage base, a higher ceiling
#: can only NAME more alternatives, and naming one only ever REFUSES a check.
#: `read_plain` and `is_plain_integer` -- the readers whose numbers a tool
#: DIVIDES by -- still refuse every separator, for the opposite reason.
#:
#: AND A LIST OF MARKS IS STILL A LIST. Round 11 walked past the enumerated nine
#: with ELEVEN more forms a conversion prints -- U+2002 EN SPACE, U+2003 EM
#: SPACE, U+2005, U+200A HAIR SPACE, U+2060 WORD JOINER, U+200B ZERO WIDTH
#: SPACE, U+FF0C FULLWIDTH COMMA, U+066C ARABIC THOUSANDS SEPARATOR, U+02BC,
#: U+00B7 MIDDLE DOT and fullwidth digits -- reproducing round 10's exact defect
#: in the characters its fix omitted, with `1<EN SPACE>420` read as 420 and an
#: honest `9 (0.6%)` of 1420 returned `suspicious`.
#:
#: SO THE SEPARATOR IS DEFINED BY WHAT IT IS NOT. A thousands mark is ONE
#: character that is neither a digit nor a letter nor a line break, sitting
#: between groups of exactly three digits -- which is a property of the shape and
#: cannot be enumerated past. The apostrophe-like MODIFIER LETTERS (U+02BC and
#: its neighbours) are named explicitly because Unicode classifies them as
#: letters, and the Swiss apostrophe is one of them. Fullwidth digits need no
#: rule at all: Python's `\\d` and `int()` both read them.
_THOUSANDS_SEP = r"(?:[^\w\n\r]|[\u02b9\u02bb\u02bc\u02c8])"
_GROUPED_INT = r"\d{1,3}(?:" + _THOUSANDS_SEP + r"\d{3})+"

_SUBJECT_COUNT = re.compile(
    r"(?<![\w.])(" + _SPELLED.pattern + r"|" + _GROUPED_INT + r"|\d{1,7})"
    r"(?![\d.])\s+(?:[a-z][a-z-]*,?\s+){0,4}?" + _PLURAL_NOUN + r"\b", re.I)

#: A DETERMINER, AN INTEGER AND A PLURAL NOUN, and nothing looser. `of 8000.5
#: steps` is not a population (the integer is bounded against a decimal point on
#: both sides), and a bare `12 sessions` with no determiner is not one either.
#:
#: THE INTEGER MAY BE SPELLED OUT, and it was not read that way. A paper naming
#: its own subgroup at the start of a sentence writes the number in words --
#: `Twenty-nine children (85.3%) were re-interviewed at twelve weeks, and their
#: mean score was 11.45` -- and it states its denominator exactly as plainly as
#: `The 21 children who ate a school lunch` does. A number spelled out is also
#: its own determiner: no paper writes `the twenty-nine children` more often than
#: it writes `Twenty-nine children`, so the leading article is optional there.
_POPULATION = re.compile(
    r"(?:\b(?:among|across|of|for|in|the|these|those|all)\s+"
    r"(?:the|these|those|all)?\s*(?<![\d.])(?P<digits>\d{1,7})(?![\d.])"
    r"|(?<![\w.])(?P<spelled>" + _SPELLED.pattern + r")(?![\d.]))"
    r"\s+(?P<noun>" + _PLURAL_NOUN + r")\b", re.I)

#: NOUNS THAT COUNT TIME, NEVER SUBJECTS. `Twenty-nine children were
#: re-interviewed at twelve weeks` names one population and one duration, and
#: reading the duration as a population puts a number in the docket that is not a
#: denominator at all. The list is closed and short on purpose: every other
#: plural noun stays admitted, because the point of the guard is that a smaller
#: population in the sentence REFUSES rather than supplies, and a spurious member
#: costs nothing but a wrong sentence in the record.
_TIME_UNITS = frozenset({
    "seconds", "minutes", "hours", "days", "weeks", "months", "years",
    "decades", "times",
})

#: THE VERBS A PAPER USES FOR A STAGE AT WHICH ITS NUMBER CHANGED. Retention and
#: analysis only: `enrolled`, `randomised`, `recruited`, `approached` and
#: `screened` are deliberately absent, because they name the total the group's n
#: already is and reading them would refuse a paper for stating its own sample
#: size.
_RETAINED = (r"(?:attend(?:ed)?|complet(?:ed|ing)|return(?:ed)?|remain(?:ed)?|"
             r"reattended|were\s+re[-\s]?(?:assessed|examined|interviewed|tested|"
             r"measured|surveyed)|were\s+(?:reassessed|followed(?:\s+up)?|retained|"
             r"analy[sz]ed|assessed|included|evaluated|available)|"
             r"provided\s+(?:data|complete))")

#: `<integer> <plural noun> ... <retention verb>` -- the paper's own sentence for
#: how many subjects reached a stage. The gap between the noun and the verb is
#: bounded at forty characters so that a later clause of the same sentence cannot
#: supply the verb for an earlier clause's count.
#:
#: A DECIMAL POINT IS NOT A SENTENCE BOUNDARY, and writing the filler as
#: `[^.;\n]` made it one: `Twenty-nine children (85.3%) were re-interviewed at
#: twelve weeks` -- the commonest way there is of printing a retention count --
#: did not match, because the `.` of `85.3` sat between the noun and the verb.
#: That is the one-character evasion round 2 found in the quote-length floor,
#: arriving in a new regex, so the period is admitted only where a digit follows
#: it and the sentence bound otherwise stands.
_ANALYSED_AT_A_STAGE = re.compile(
    r"(?<![\w.])(?P<count>" + _SPELLED.pattern + r"|\d{1,3}(?:,\d{3})+|\d{1,7})"
    r"(?![\d.])\s+(?:[a-z][a-z-]*\s+){0,2}?(?P<noun>" + _PLURAL_NOUN + r")\b"
    r"(?:[^.;\n]|\.(?=\d)){0,40}?\b" + _RETAINED + r"\b", re.I)

#: THE STAGE OF A STUDY, as a paper names one: `baseline`, `follow-up`, `twelve
#: weeks`, `week 12`, `visit 3`, `discharge`.
#:
#: WHY A JOIN IS NEEDED AT ALL, and it is the difference between a guard and a
#: veto. A paper that reports ANY dropout states a retention count somewhere, so
#: withdrawing a phase-less n wherever one exists would refuse the baseline mean
#: of every cohort study ever written -- the honest case, and the one where the
#: enrolled n IS that wave's denominator. What makes the follow-up different is
#: that the retention sentence and the VALUE'S OWN sentence name THE SAME STAGE:
#: `Twenty-four nurses attended the twelve-week visit` beside `At the twelve-week
#: visit the mean index score was 7.08`. Where they name different stages the
#: statement is about some other wave and withdraws nothing.
#:
#: THE LIMIT IS STATED RATHER THAN HIDDEN: a results sentence that names no stage
#: joins to nothing, and that shape keeps its check.
#: AND HALF THE WORDS A PAPER USES FOR A WAVE WERE NOT IN IT. A study that calls
#: its second wave `the second assessment`, `the exit interview` or `endline`
#: named no stage on EITHER side, the join was empty, and the retention count the
#: paper states withdrew nothing: measured at GRIM `impossible` on 170/24 = 7.08
#: at the enrolled n = 28, with the `twelve-week visit` wording of the same paper
#: refusing.
#:
#: WIDENING THIS VOCABULARY IS ONE-DIRECTIONAL, which is why it can be generous.
#: The list feeds a JOIN between two sentences and nothing else; a stage matched
#: more often makes the join non-empty more often, and a non-empty join only ever
#: WITHDRAWS a denominator. Nothing here can supply one.
_STAGE_PHRASE = re.compile(
    r"\b(?:base[-\s]?line|end[-\s]?line|follow[-\s]?up|discharge|end[-\s]?point|"
    r"mid[-\s]?point|mid[-\s]?study|"
    r"post[-\s]?(?:test|intervention|treatment|operative|partum))\b"
    r"|\b(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"final|last|initial|exit|closing|discharge|entry)\s+"
    r"(?:assessment|interview|review|visit|wave|round|session|follow[-\s]?up|"
    r"time[-\s]?point|measurement|survey|phase|examination|appointment|"
    r"questionnaire|contact|screening)s?\b"
    r"|\b(?:\d{1,3}|" + _SPELLED.pattern + r")[-\s]?"
    r"(?:week|month|year|day|hour|visit|session|wave)s?\b"
    r"|\b(?:week|month|year|day|visit|wave|round|phase|time[-\s]?point)[-\s]?"
    r"(?:\d{1,3}|" + _SPELLED.pattern + r")\b", re.I)

#: A UNIT OF ANALYSIS THAT IS NOT A SUBJECT: a hyphenated compound, which is how
#: every repeated-measures design names its own unit (`nurse-nights`,
#: `patient-years`, `person-days`), or one of the nouns a paper counts
#: OBSERVATIONS in.
_ANALYSIS_UNIT_NOUN = (
    r"(?:[a-z][a-z]*[-‐‑][a-z][a-z]*s"
    r"|observations|measurements|readings|recordings|records|assessments|"
    r"administrations|sessions|visits|nights|trials|episodes|samples|specimens|"
    r"images|scans|encounters|admissions|data\s+points)")

#: `giving 84 nurse-nights of actigraphy` -- the yield of a design, stated as a
#: number of units that are not people.
_ANALYSIS_UNIT_YIELD = re.compile(
    r"\b(?:giving|yielding|providing|producing|resulting\s+in|leaving|"
    r"(?:for\s+)?a\s+total\s+of|comprising|contributing)\s+"
    r"(?P<count>" + _SPELLED.pattern + r"|\d{1,3}(?:,\d{3})+|\d{1,7})(?![\d.])"
    r"\s+(?:[a-z][a-z-]*\s+){0,2}?(?P<noun>" + _ANALYSIS_UNIT_NOUN + r")\b", re.I)


def stage_phrases(text: Any) -> list[str]:
    """The stages of the study one sentence names, normalised for comparison.

    A LOOKUP FOR A JOIN, NOT A READING OF A TIMELINE. Nothing here orders the
    stages, decides which came first, or attaches one to a phase id: the only
    question asked is whether two sentences name the SAME stage, and normalising
    `twelve-week`, `twelve weeks` and `Twelve Weeks` to one string is the whole
    of it.
    """
    out: list[str] = []
    for m in _STAGE_PHRASE.finditer(str(text or "")):
        words = re.split(r"[-\s]+", m.group(0).strip().lower())
        key = " ".join(_stem(w) for w in words if w)
        if key and key not in out:
            out.append(key)
    return out


def population_sizes(quote: Any) -> list[int]:
    """The population sizes a sentence states it is reported over."""
    out: list[int] = []
    for m in _POPULATION.finditer(str(quote or "")):
        if (m.group("noun") or "").lower() in _TIME_UNITS:
            continue
        digits, spelled = m.group("digits"), m.group("spelled")
        try:
            k = int(digits) if digits else spelled_value(spelled)
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
        if k is not None and k > 1 and k not in out:
            out.append(k)
    return out


def printed_subject_counts(text: Any) -> list[int]:
    """Every number of things the served text prints as `<integer> <plural noun>`.

    WHAT IT IS FOR, AND IT IS ONLY EVER FOR THAT: the ceiling on what may count
    as an ALTERNATIVE percentage base (`other_bases_that_fit`). A higher ceiling
    can only NAME more alternatives, and naming one only ever REFUSES a check --
    so a reader that is too generous costs coverage and cannot cost an
    accusation, which is why it may read loosely here and nowhere else.

    THE CEILING WAS THE ACCOUNT'S, NOT THE PAPER'S. It was the largest value the
    account held as a `statistic: n` under the STRICT grammar, so a paper that
    spells its total out (`Thirty-four children were sampled`) or prints it with
    a thousands separator (`1,204 patients`) put its own denominator ABOVE its
    own ceiling, and the guard that exists to name the base silently stopped
    firing on exactly the papers whose base is hardest to see.

    WHAT IT COSTS, MEASURED. Reading the text raises the ceiling a long way on a
    paper that prints a population figure: ajcp.70049 goes to 84,000 (its service
    area) and jamanetworkopen.37679 to 315,661. A higher ceiling admits larger
    alternative bases, and an alternative base withdraws a check -- so in
    principle a paper naming a large population buys a wider excuse. On both
    reference accounts it costs NOTHING: the calls that ran before still run (16
    on ajcp, 8 of them `check_count_percent`), because an alternative is only
    ever consulted where the bound n does NOT reproduce the printed percentage,
    and where it does not, the implied denominator is pinned to a narrow interval
    by the paper's own two numbers rather than to anything the ceiling admits.
    """
    out: list[int] = []
    for m in _SUBJECT_COUNT.finditer(str(text or "")):
        k = _count_of(m.group(1))
        if k is not None and k > 1 and k not in out:
            out.append(k)
    return out


def _count_of(raw: Any) -> int | None:
    """The integer a counted quantity is printed as, spelled out or in digits.

    THE SEPARATORS ARE STRIPPED ONLY WHERE THE WHOLE LITERAL IS A GROUPED
    INTEGER, never one character at a time. `int(s.replace(",", "").replace(" ",
    ""))` read `1,240` and `1 240` and nothing else -- a thin space, a
    non-breaking space, the Swiss apostrophe and the European full stop all
    raised -- and the caller was then handed the regex's own tail (`240`) or
    nothing at all. Matching `_GROUPED_INT` first is what makes stripping the
    full stop safe: every group there is exactly three digits, which a decimal
    fraction of one or two places is not.
    """
    s = str(raw or "").strip()
    if _SPELLED.fullmatch(s):
        return spelled_value(s)
    if re.fullmatch(_GROUPED_INT, s):
        return int(re.sub(_THOUSANDS_SEP, "", s))
    try:
        return int(s.replace(",", "").replace(" ", ""))
    except (ValueError, TypeError):
        return None


def printed_integer(printed: Any, decimal_sep: str = ".") -> int | None:
    """The integer a printed literal denotes, in EVERY form a paper prints one.

    DELIBERATELY LOOSER THAN `is_plain_integer`, AND USED ONLY WHERE LOOSER IS
    SAFE. `is_plain_integer` is the gate on a denominator a tool will DIVIDE by,
    and it refuses a comma because a thousands separator and a decimal comma are
    undecidable per value. This reader answers a different question -- how large
    a base could this paper have used -- where being wrong high only removes a
    check.
    """
    got = is_plain_integer(printed)
    if got is not None:
        return got
    lit = _bind.read_literal(str(printed or ""), decimal_sep)
    form, numeric = lit.get("printed_form"), lit.get("numeric")
    if form == "grouped_integer" and numeric is not None and float(numeric).is_integer():
        return int(numeric)
    if form == "word":
        return read_spelled(printed)
    return None


#: The statistics whose printed literal IS A NUMBER OF THINGS THE PAPER COUNTED,
#: and so a denominator this paper could have used.
#:
#: `count` WAS MISSING AND IT IS WHERE A COHORT SIZE ACTUALLY LIVES. The ceiling
#: read `statistic: n` rows and the served text, so a paper that prints its
#: eligible cohort ONLY IN A TABLE -- the ordinary place for a flow table's
#: `Eligible cohort | 112` -- put its own percentage base above its own ceiling
#: and `other_bases_that_fit` returned nothing, which `to_count_percent_kwargs`
#: reads as "no reading of the base rescues the arithmetic". Measured: `Nine of
#: the eligible nurses (8.0%)` (9/112 = 8.0357%) with the ANALYSED n = 28 bound
#: at the coordinate came back `suspicious` on a table that did nothing wrong.
#:
#: A LOOSER CEILING CANNOT ACCUSE ANYBODY. It only ever names more alternatives,
#: and naming one only ever withdraws a check.
CEILING_STATISTICS = frozenset({"n", "count"})


def paper_max_n(values: list[dict], text: str = "") -> int:
    """The largest number of subjects this PAPER prints, in every form it may
    print one in: an account value typed `n` or `count`, and a count of subjects
    in the served text. Zero when it prints none.

    THE DOCUMENT SETTLES THE SEPARATOR, not the literal. `bind.decimal_convention`
    is the repo's one rule for that, and asking it here rather than in the bridge
    keeps the reading of a literal in the module that owns it.

    ONE UNREADABLE LITERAL MAY NOT TAKE THE CEILING WITH IT, and it did. This
    runs inside `checks._Index.__init__`, which is OUTSIDE the bridge's
    per-candidate isolation, so an exception raised while reading one `n` cost
    the whole account its sidecar -- no checks, no refusal docket, nothing. The
    literal that did it (`4,16` under a period-convention paper) is fixed in
    `bind.read_literal`, but the shape of the defect is the one this repo keeps
    meeting, so the read is isolated per value as well: a literal this reader
    falls over on contributes nothing to the ceiling, which can only ever NAME
    FEWER alternative bases and so only ever REMOVE checks.
    """
    sep = _bind.decimal_convention(text or "")
    from_values = []
    for v in values:
        if v.get("statistic") not in CEILING_STATISTICS:
            continue
        try:
            k = printed_integer(v.get("printed"), sep)
        except Exception:
            k = None
        if k is not None:
            from_values.append(k)
    return max(from_values + printed_subject_counts(text) or [0])


def duplicate_ids(values: list[dict]) -> set[str]:
    """The ids more than one value in this account carries.

    AN ID IS A HANDLE AND TWO VALUES MAY NOT SHARE ONE. `_Index.by_id` is
    last-write-wins and `well_formed` asked only that a value HAVE an id, so a
    reading that mints ids from (variable, statistic) -- the natural scheme, and
    one that collides the moment an instrument is reported for two studies, two
    waves or two arms -- produced two candidates that both resolved to the SAME
    record. Measured: an abstract's 1-dp mean and a table's 3-dp SD sharing one
    id gave GRIM the SD as its mean and returned `impossible` on an honest paper,
    while `n_candidates == n_run + n_refused` still balanced exactly.

    THE CHECK CANNOT LIVE IN `well_formed`, which sees one value at a time. It is
    a property of the ACCOUNT, and it refuses every candidate that would touch a
    duplicated id rather than choosing which of the two the id means.
    """
    seen: set[str] = set()
    dupes: set[str] = set()
    for v in values:
        vid = v.get("id") if isinstance(v, dict) else None
        if not isinstance(vid, str):
            continue
        (dupes if vid in seen else seen).add(vid)
    return dupes


# --------------------------------------------------------------------------
# Variable premises
# --------------------------------------------------------------------------


def values_outside(lower: Any, upper: Any, values: list[dict]) -> list[str]:
    """The ids of the printed values of one variable that fall outside `[lower,
    upper]`. Either side may be None, meaning unbounded on that side.

    ONE TEST, TWO CALLERS, AND THE SECOND IS THE POINT. It was written for a
    bound derived from the declared KIND, and it is the same question for a
    bound the PAPER states: does the range offered for this variable contain the
    numbers the paper actually printed on it?
    """
    if lower is None and upper is None:
        return []
    out: list[str] = []
    for v in values:
        if str(v.get("statistic") or "") not in VALUE_OF_VARIABLE_STATISTICS:
            continue
        got = read_plain(v.get("printed"))
        if got is None or got["is_percent"]:
            continue
        x = got["value"]
        try:
            if (lower is not None and x < float(lower)) or \
                    (upper is not None and x > float(upper)):
                out.append(str(v.get("id")))
        except (TypeError, ValueError):
            continue
    return out


def _kind_contradicted(var: dict, values: list[dict]) -> list[str]:
    """The variable's own printed values that fall outside the bounds its
    declared KIND makes necessary.

    A KIND IS THE READING'S ASSERTION, AND A BOUND DERIVED FROM IT IS TOO. That
    is fine where nothing disputes the kind: a count cannot go below zero, and
    every value on the variable agrees. It is not fine where the paper's own
    printed numbers say the kind is wrong -- a mean of 2.40 on a variable the
    reading typed `binary` -- because then the 0-1 ceiling is not a fact about
    the paper, it is a consequence of a mistake, and `check_sd_or_se` adjudicating
    an SD of 1.50 against it accuses an honest paper of the reading's error.
    """
    lo, hi = NECESSARY_BOUNDS.get(str(var.get("kind") or ""), (None, None))
    return values_outside(lo, hi, values)


def _num_forms(value: Any) -> list[str]:
    """The literal forms a paper may print one bound in: `5` and `5.0`, `1.25`."""
    forms: list[str] = []
    if isinstance(value, str) and value.strip():
        forms.append(value.strip())
    try:
        f = float(value)
    except (TypeError, ValueError):
        return forms
    forms += [str(int(f)), f"{f:.1f}"] if f.is_integer() else [repr(f)]
    return forms


def _numeral_pattern(form: str) -> str:
    """One printed form, bounded so it is a numeral of its own.

    ONE DEFINITION OF THAT BOUNDARY, AND THE TRAILING HALF WAS WRONG. `(?![\\d.])`
    reads a FULL STOP as evidence that more of the number follows, so the
    commonest way a paper prints a range -- `rated on a card running from 0 to
    6.` -- did not carry its own upper bound, while the identical sentence with
    one more word after the 6 did. `n_premise.states_n` met the same bug, wrote
    it down ("a full stop is just a full stop") and fixed it in place; the fix
    was never carried to the numeral test every bound and every model
    bound-verdict passes through, so this is now the one place it lives.

    A digit may not follow, and a decimal point may not introduce more digits --
    so the `1` of `1.25` is still not the `1` a bound of 1 needs -- but a
    sentence-final period ends a sentence.
    """
    return r"(?<![\d.])" + re.escape(form) + r"(?!\d)(?!\.\d)"


def numeral_in(quote: Any, value: Any) -> bool:
    """Is `value` printed as a numeral of its own inside `quote`?

    Bounded on both sides against digits and decimal points, so the `5` of
    `1.25` is not the `5` a bound of 5 needs.
    """
    s = str(quote or "").translate(_MINUS)
    return any(re.search(_numeral_pattern(form), s) for form in _num_forms(value))


#: A NUMERIC RANGE AS A PAPER PRINTS ONE. Used to ask how many DIFFERENT scales
#: one sentence states, which is the question `bounds_verification._shared_scale`
#: has to answer and was answering from the account instead. Deliberately loose
#: about what the numbers are: a year range counts, because a sentence that
#: states two spans of numbers is ambiguous about which one belongs to which
#: quantity whatever the numbers mean.
#: AND IT READ FOUR PHRASINGS, WHICH IS WHY ROUND 10 GOT PAST IT SEVEN WAYS. The
#: guard's direction is what makes an under-reading dangerous: seeing FEWER
#: ranges LIFTS the attribution tie, so a second scale printed `from 0 through to
#: 10`, `from 0 up to 10`, `from zero to ten` or `from 0 to as much as 10` left
#: `stated_ranges` reporting one range, the lift returned, and an account that
#: had mis-split the sentence had its neighbour's 0-6 admitted as `stated` --
#: grimmer `suspicious`, sprite `suspicious`, sd_or_se `highly_suspicious` on an
#: honest 0-10 card.
#:
#: SO THE JOIN IS A SHAPE RATHER THAN THREE WORDS, and the endpoints may be
#: spelled out. Reading MORE ranges can only ever refuse the lift, which is why
#: this reader may be generous where the bound reader may not: a year range still
#: counts, and so does an incidental `two to three times`.
#: `zero` IS ADMITTED HERE AND NOWHERE ELSE. `_SPELLED` reads counts of subjects
#: and a paper does not spell out a cohort of none, so `zero` is deliberately
#: absent from `_UNITS`; a SCALE, on the other hand, starts at zero constantly
#: (`a card running from zero to ten`), and reading that as one range rather than
#: none is the whole of the difference between refusing the lift and firing it.
_RANGE_NUMBER = r"(?:[-+]?\d+(?:\.\d+)?|\bzero\b|" + _SPELLED.pattern + r")"
#: The connective between a range's two ends, as a paper writes one: a dash, or a
#: preposition with the optional hedges (`up to`, `through to`, `to as much as`)
#: a paper puts around it.
_RANGE_JOIN = (r"(?:\s*(?:up\s+|down\s+)?(?:to|through|thru|until)\s+"
               r"(?:(?:to|up|as\s+much\s+as|as\s+high\s+as|as\s+low\s+as|"
               r"a\s+maximum\s+of|at\s+most)\s+)?"
               r"|\s*-\s*)")
_STATED_RANGE = re.compile(
    r"(?<![\w.])(" + _RANGE_NUMBER + r")(?![\d.])" + _RANGE_JOIN
    + r"(" + _RANGE_NUMBER + r")(?![\d])"
    r"|\bbetween\s+(" + _RANGE_NUMBER + r")\s+and\s+(" + _RANGE_NUMBER + r")(?![\d])",
    re.I)

#: A BOUND STATED ON ONE SIDE ONLY, which is the other half of "how many scales
#: does this sentence state". `a card whose highest possible value is 10` and
#: `rated up to 10` state a scale as plainly as `0 to 10` does and neither is a
#: range, so a sentence pairing one of them with a range was counted as stating
#: ONE scale and the lift fired.
_BOUND_PHRASE = re.compile(
    r"\b(?P<up>up\s+to|as\s+(?:much|high|many)\s+as|at\s+most|"
    r"no\s+(?:more|higher|greater)\s+than|maximum|highest|greatest|ceiling)\b"
    r"|\b(?P<down>as\s+low\s+as|at\s+least|no\s+(?:fewer|less|lower)\s+than|"
    r"minimum|lowest|smallest|floor|anchored\s+at)\b", re.I)

#: How far past a bound phrase its own number may sit.
_BOUND_PHRASE_REACH = 40


def stated_ranges(sentence: Any) -> list[tuple[float, float]]:
    """Every DISTINCT numeric range this passage states, in order."""
    out: list[tuple[float, float]] = []
    for m in _STATED_RANGE.finditer(str(sentence or "").translate(_MINUS)):
        lo, hi = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        pair = (_range_number(lo), _range_number(hi))
        if pair[0] is None or pair[1] is None or pair in out:
            continue
        out.append(pair)  # type: ignore[arg-type]
    return out


def _range_number(raw: Any) -> float | None:
    """One end of a range, in digits or in words."""
    s = str(raw or "").strip()
    try:
        return float(s)
    except (TypeError, ValueError):
        pass
    if s.lower() == "zero":
        return 0.0
    got = spelled_value(s)
    return None if got is None else float(got)


def scale_claims(sentence: Any) -> list[tuple[float | None, float | None]]:
    """Every DISTINCT SCALE this passage claims, two-sided or one-sided.

    THE QUESTION `bounds_verification._shared_scale` HAS TO ANSWER is whether the
    sentence it is about states ONE scale for the two variables it names, or a
    DIFFERENT scale for each. `stated_ranges` answered a narrower question -- how
    many `X to Y` spans are printed -- and a paper that states its second scale
    as a maximum, or in an abbreviations footnote, or through `the former ... the
    latter`, states two scales that the range reader counts as one.

    A ONE-SIDED CLAIM IS PAIRED WITH ITS OPPOSITE, so a sentence that names both
    ends separately (`whose lowest possible value is 0 and whose highest possible
    value is 10`) is ONE scale and not two; and a one-sided claim whose number is
    already an endpoint of a range in the same sentence is that range restated
    (`from 0 up to 10`), not a second scale.

    OVER-COUNTING ONLY EVER REFUSES THE LIFT, which is the direction that makes a
    loose reader safe here: the lift is the one place a tie in the attribution
    heuristic is allowed to pass, and refusing it returns the variable to the
    ordinary refusal (invariant 1).
    """
    s = str(sentence or "").translate(_MINUS)
    ranges = stated_ranges(s)
    endpoints = {x for pair in ranges for x in pair}
    lower: list[float] = []
    upper: list[float] = []
    for m in _BOUND_PHRASE.finditer(s):
        tail = s[m.end():m.end() + _BOUND_PHRASE_REACH]
        hit = re.search(r"(?<![\w.])(" + _RANGE_NUMBER + r")(?![\d])", tail, re.I)
        if not hit:
            continue
        got = _range_number(hit.group(1))
        if got is None or got in endpoints:
            continue
        (upper if m.group("up") else lower).append(got)
    out: list[tuple[float | None, float | None]] = list(ranges)  # type: ignore[arg-type]
    while lower and upper:
        out.append((lower.pop(0), upper.pop(0)))
    out += [(v, None) for v in lower] + [(None, v) for v in upper]
    seen: set = set()
    uniq: list[tuple[float | None, float | None]] = []
    for claim in out:
        if claim not in seen:
            seen.add(claim)
            uniq.append(claim)
    return uniq


def scale_claim_span(sentence: Any) -> tuple[int, int] | None:
    """Where in this passage its scale claim is PRINTED, or None.

    WHY THE POSITION MATTERS AND THE COUNT DOES NOT SETTLE IT. `_shared_scale`
    asks whether one sentence states ONE scale for the two variables it names,
    and `scale_claims` answers by counting the scales it can READ. Round 11
    stated the second scale four more ways the counter cannot see -- a POINT
    COUNT (`a thirteen-point card`), `out of 12`, `thirteen response options`,
    and a comparison (`a card with almost twice as many points`) -- so the count
    came back to one and the neighbour's 0-7 was admitted as `stated` on a 0-12
    variable, with GRIMMER, SPRITE and `check_sd_or_se` all convicting an honest
    paper.

    A LONGER LIST OF SCALE PHRASINGS IS THE TREADMILL THIS MODULE KEEPS LOSING.
    The position is not: a scale printed BETWEEN the two names modifies the FIRST
    of them (`... shed tidiness on a card running from 0 to 7 and plot
    satisfaction on a thirteen-point card`), and a scale governing a coordinated
    pair is printed AFTER both (`The means for inclusive decision making and
    inclusion of community residents were 4.06 and 4.01 on a 1-5 scale`, the
    ajcp case this lift exists for). The rule never has to SEE the second scale,
    which is exactly why no phrasing of it can defeat the rule.
    """
    s = str(sentence or "").translate(_MINUS)
    spans = [m.span() for m in _STATED_RANGE.finditer(s)]
    for m in _BOUND_PHRASE.finditer(s):
        tail = s[m.end():m.end() + _BOUND_PHRASE_REACH]
        hit = re.search(r"(?<![\w.])(" + _RANGE_NUMBER + r")(?![\d])", tail, re.I)
        if hit:
            spans.append((m.start(), m.end() + hit.end()))
    if not spans:
        return None
    return min(a for a, _ in spans), max(b for _, b in spans)


def scale_sits_between(sentence: Any, mine: dict, other: dict) -> bool:
    """Is this passage's scale claim printed BETWEEN the two variables, with one
    named ONLY before it and the other ONLY after? Then it modifies the nearer
    one and not the pair.

    THE TEST IS ON EVERY MENTION, NOT ON ONE PAIR OF THEM, and the difference is
    measured. ajcp.70049's own sentence -- the case this lift exists for --
    names `inclusive decision making` BEFORE the `1-5` and again after it
    (`corresponding to "agree" to inclusive decision making-related prompts`),
    so a rule satisfied by any one pair of positions refused the lift and cost
    two real `check_sd_or_se` calls on the reference account. A scale that
    modifies the first of two coordinated names has the second one entirely to
    its right; a scale governing the pair does not.

    Being wrong here can only ever REFUSE the shared-scale lift, which returns
    the variable to the ordinary attribution refusal (invariant 1).
    """
    span = scale_claim_span(sentence)
    if span is None:
        return False
    lo, hi = span
    a = _name_positions(sentence, mine)
    b = _name_positions(sentence, other)
    if not a or not b:
        return False
    return (max(a) < lo and min(b) >= hi) or (max(b) < lo and min(a) >= hi)


#: WHAT A NUMERAL IN A GROUP'S LABEL IS COUNTING WHEN IT IS NOT PEOPLE. The
#: commonest by a distance is a DURATION (`12-month cohort`, `6-week arm`), and
#: the second is a YEAR (`2019 cohort`). Both are singular in a label, which is
#: why this is not `_TIME_UNITS` -- that list is plural, because it reads
#: sentences.
_DURATION_NOUN = re.compile(
    r"(?:second|sec|min|minute|hour|hr|day|night|week|fortnight|month|year|yr|"
    r"decade|semester|term)s?\b", re.I)
_YEAR_FORM = re.compile(r"(?:19|20)\d\d")


def numeral_counts_subjects(text: Any, value: Any) -> bool:
    """Is `value` printed in `text` as a COUNT rather than as a duration or a year?

    A CORROBORATION WITNESS HAS TO SAY WHAT IT IS A WITNESS TO. `numeral_in` asks
    only whether the digits are there, and `12-month cohort` has the digits of a
    twelve-pharmacy denominator without being about pharmacies at all. Being
    wrong here can only ever REFUSE a denominator (a corroboration that fails
    costs a check and never buys one), so the reading is deliberately strict.
    """
    s = str(text or "").translate(_MINUS)
    for form in _num_forms(value):
        for m in re.finditer(_numeral_pattern(form), s):
            if _YEAR_FORM.fullmatch(form):
                continue
            tail = s[m.end():m.end() + 24].lstrip("- \t‐‑")
            if _DURATION_NOUN.match(tail):
                continue
            return True
    return False


#: A DERIVATION THAT MOVES THE RANGE. A mean of k items on [a, b] is still on
#: [a, b]; a DIFFERENCE of two of them runs on [-(b-a), +(b-a)], a SUM on
#: [k*a, k*b], and a ratio on neither. Only the second kind may not inherit its
#: source's scale, which is why this is a word list about the DERIVATION and not
#: a rule about derived variables as a class: three of ajcp.70049's own checks
#: rest on a stated scale attached to a variable the account marks derived (`the
#: mean of member responses to four items`), and a rule keyed on derivedness
#: alone would take them.
_RANGE_CHANGING_DERIVATION = re.compile(
    r"\b(?:chang(?:e|es|ed)|difference|differences|delta|gain|loss|decline|"
    r"decrease|increase|reduction|improvement|minus|subtract(?:ed|ing)?|"
    r"sum|summed|total(?:s|led|ed)|aggregate|"
    r"ratio|quotient|product|log|logarithm|z[-\s]?scores?)\b", re.I)


def derived_range_changes(var: dict) -> str | None:
    """The account's own words saying this variable is DERIVED by an operation
    that moves the range, or None.

    BOTH HALVES ARE REQUIRED, and the second is what keeps it narrow: the
    account must mark the variable derived (`derived_from`, `derivation`, or the
    `derived_outcome` role) AND its derivation or its own name must name the
    operation. A variable merely named `Total score` says nothing about being
    computed from anything.
    """
    derived = (bool(var.get("derived_from"))
               or bool(str(var.get("derivation") or "").strip())
               or str(var.get("role") or "") == "derived_outcome")
    if not derived:
        return None
    for raw in (var.get("derivation"), var.get("name"), var.get("label")):
        m = _RANGE_CHANGING_DERIVATION.search(str(raw or ""))
        if m:
            return m.group(0)
    return None


#: WORDS THAT SAY A SENTENCE IS STATING A SCALE, A RANGE, A RATING, A CODING, OR
#: A MINIMUM/MAXIMUM -- rather than merely printing two numbers that happen to
#: sit in a sentence sharing the variable's own name-words.
#:
#: WHY THIS EXISTS (round 13's adversarial probe). `_side`'s vocabulary path
#: admitted a `stated` bound from any sentence that was topically about the
#: variable (`about_this_variable`, bag-of-words content overlap) and happened
#: to print both declared numerals somewhere in it (`numeral_in`) -- with
#: nothing asking whether the sentence was making a RANGE CLAIM at all. `As a
#: courtesy, the front desk waived late fees for 0 to 6 first-time offenders
#: each month` shares the word `courtesy` with `Courtesy Rating` and prints
#: `0` and `6`: `about_this_variable` scored 0.5, `numeral_in` found both, and
#: a wrong 0-6 ceiling reached `check_sd_or_se` as `stated`, the tier that
#: licenses `impossible`/`highly_suspicious` un-downgraded -- while the paper's
#: real scale, `0 to 10`, sat in an entirely different sentence the account did
#: not point at.
#:
#: `granularity_verification` NEVER HAD THIS HOLE: it has always required the
#: DISCRETENESS vocabulary in the same clause before granting a step of 1
#: (`says_step = bool(DISCRETENESS.search(...))`). The bounds premise tested
#: content-WORDS (is this sentence about the right noun?) and never
#: content-TYPE (does it assert a range?), and those are not the same
#: question. This closes it the same way DISCRETENESS does: a gate a sentence
#: must ALSO clear before its printed numerals become a bound.
#:
#: CAN ONLY EVER REMOVE A BOUND (invariant 1). A sentence naming the variable
#: and printing its numerals but using none of these words is refused rather
#: than admitted; every legitimate scale sentence in the working corpus and
#: this suite already uses one of them ("rated ... on a 0 to 10 card", "scored
#: 0-4", "a 1 to 7 point scale", "ranged from 1 to 5", "the minimum ... the
#: maximum", "counted ... from 0 to 7 days", "recorded ... from 0 to 100",
#: "tallied as whole events, from 0 to 20"). `count`/`record`/`measure`/
#: `assess` are admitted because HOW a value was obtained is exactly the
#: sentence a paper states its scale in -- and were measured missing here,
#: costing eight honest checks on three fixtures (rounds 4-6), before the
#: fixed vocabulary below shipped.
#:
#: DOES NOT APPLY TO A MODEL'S READING (`verdict is not None`). There the model
#: has already been asked, and has already answered, the real question -- does
#: this passage establish this bound for this variable -- and a second, cruder
#: proxy for the same question would only narrow a judgement made on the
#: passage's actual content rather than on a fixed word list.
SCALE_ASSERTING = re.compile(
    r"\b(?:rang(?:e|es|ed|ing)|runs?|running|scales?|scaled|"
    r"scor(?:e|es|ed|ing)|"
    r"rat(?:ed|ings?)|cod(?:ed|ing)|"
    r"count(?:ed|ing)?|record(?:ed|ing)?|tall(?:y|ied|ying)|"
    r"measured|assessed|"
    r"likert|dichotom\w+|"
    r"point\s+scale|response\s+options?|answer\s+options?|"
    r"minimum|maximum|lowest|highest|anchored\s+at|floor\s+of|ceiling\s+of)\b",
    re.I)


def bounds_verification(var: dict, hay: Haystack, others: list[dict],
                        values: list[dict], verdict: dict | None = None) -> dict:
    """`variable.bounds.verification` -- which bounds this variable may pass, and
    on whose word.

    A BOUND IS ADMITTED TWO WAYS AND NO OTHER. Either the KIND makes it
    necessary -- a count cannot go below 0, and the paper never prints that
    number because it does not have to -- or the PAPER STATES IT, which means
    its own numeral sits in a sentence that locates in the served document and
    is about this variable. `Participants attended between 1 and 2 supervised
    sessions per week` carries both numerals of a planted 1-2 mood scale and is
    a sentence about session attendance; `1 to 7 point` is twelve characters of
    another variable's scale sentence. Both licensed a scale, and a scale is
    what a range verdict is computed against.

    `verdict` IS THE MODEL'S READING OF THIS PREMISE, when wave 7c's paid pass
    has run for this paper (`premise_reading.index`), and None otherwise -- in
    which case every line below is the code that shipped before it, unchanged.
    Given one, it replaces the ATTRIBUTION heuristic (`about_this_variable`,
    `names_another_variable`, `_shared_scale`) and nothing else: the quote must
    still locate, it must still PRINT the bound's own numeral, a derived
    quantity's bound must still be stated for the derived quantity, and the
    variable's own printed values may still contradict it. A model may say which
    sentence is relevant; it may not supply a number, and it may not overrule
    the paper's own arithmetic.
    """
    b = field_dict(var, "bounds")
    src = str(b.get("source") or "not_stated")
    lower, upper = b.get("lower"), b.get("upper")
    quote = b.get("quote")
    kind = str(var.get("kind") or "")
    need_lo, need_hi = NECESSARY_BOUNDS.get(kind, (None, None))
    contradicted = _kind_contradicted(var, values)
    rec: dict[str, Any] = {
        "declared_source": src, "lower": lower, "upper": upper, "quote": quote,
        "bound_source": BOUND_SOURCE_OF.get(src, ASSUMED_BOUND_SOURCE),
        "kind_necessary": [need_lo, need_hi],
        "kind_contradicted_by": contradicted,
        "lower_passed": None, "upper_passed": None,
        "quote_located": False, "reasons": [],
        # WHAT A MODEL WAS ASKED AND WHAT IT ANSWERED, recorded on every
        # variable a wave-7c pass covered, whichever way it answered. A premise
        # moved by a reading has to say so where the reader looks for it.
        "model_reading": verdict,
    }
    if src not in BOUND_SOURCE_OF or (lower is None and upper is None):
        rec["bound_source"] = ASSUMED_BOUND_SOURCE
        rec["reasons"].append({
            "reason": "bounds_not_stated",
            "detail": f"bounds source `{src}`" if src not in BOUND_SOURCE_OF else ""})
        return rec
    loc = hay.locate(quote)
    about = about_this_variable(var, loc["sentence"] or "", others) if loc["located"] \
        else {"anchor_score": 0.0, "about_this_variable": False,
              "names_another_variable": None, "other_variable_score": 0.0}
    rec.update({"quote_located": loc["located"], "quote_span": loc["span"],
                "quote_sentence": loc["sentence"], "quote_not_located_because": loc["why"],
                "quote_names_another_variable": about["names_another_variable"],
                "quote_about_this_variable": about["about_this_variable"],
                "anchor_score": about["anchor_score"]})

    def _shared_scale(side: str, value: Any) -> str | None:
        """The OTHER variable this sentence names, when it claims the SAME bound
        from the SAME sentence -- else None.

        A TIE IS AN AMBIGUITY ONLY WHERE THE TWO ANSWERS DIFFER. The rule above
        refuses whenever the sentence names another declared variable at least as
        strongly, which is right when one of the two is wrong: round 3's
        abbreviations block scores `body mass index` and `Perceived Stress Scale`
        at 1.0 apiece, and the `0 to 4` on the PSS line was adjudicated against a
        BMI of 27.4. It is NOT right when the sentence states ONE scale for BOTH
        of the variables it names -- `The means for inclusive decision making and
        inclusion of community residents were 4.06 and 4.01 on a 1-5 scale` -- and
        that shape cost two real `check_sd_or_se` calls on ajcp.70049, each
        refused on the ground that its quote describes the OTHER one.

        The test is not a reading of the grammar, which is what a clause split
        would have to be: it is that the two answers AGREE. Where the other
        variable declares the same number on the same side, from a quote that
        locates in the same sentence, attributing the bound to either variable
        admits the same bound, so the ambiguity changes nothing and cannot supply
        anything (invariant 1). Where it declares a different number, or none,
        the refusal stands.

        AND THE WITNESS IS THE SENTENCE, NEVER THE TWO DECLARATIONS ALONE. Round
        9: `The supervisor rated lunchtime enjoyment and lunchtime noise on cards
        running from 0 to 6 and from 0 to 10 respectively` states TWO scales, and
        a reading that mis-splits `respectively` records the neighbour's 0-6 for
        noise. The two declarations then AGREE BY CONSTRUCTION -- because one of
        them was copied from the other -- so the agreement test was satisfied
        exactly when the account was wrong and failed exactly when it was right
        (noise 0-10 disagrees with enjoyment 0-6, and the refusal stood). The
        agreement of two readings is not evidence about the paper.
        `scale_claims` asks the paper instead: a sentence that claims more than
        one scale is ambiguous about which quantity each belongs to, whatever the
        account says, and only a reading of its grammar can settle it -- which is
        the model's job (`premise_reading`), not a vocabulary's. The ajcp case
        this lift exists for states ONE scale (`... were 4.06 and 4.01 on a 1-5
        scale`) and is untouched.

        AND THE COUNT IS OF SCALES, NOT OF PARSEABLE RANGES. Round 10 got past
        the range reader SEVEN ways -- `from 0 through to 10`, `from 0 up to 10`,
        `from zero to ten`, `from 0 to as much as 10`, `whose highest possible
        value is 10`, an abbreviations footnote, and `the former ... the latter`
        -- each of which states a second scale the range reader could not see, so
        the count was one and the lift fired on an account that had mis-split the
        sentence. `scale_claims` reads a one-sided bound as a scale claim too.
        EXACTLY ONE is required rather than at most one: a sentence claiming no
        scale at all is not evidence that two variables share one.

        AND THE COUNT IS NOT THE WHOLE TEST, BECAUSE A SECOND SCALE NEED NOT BE
        COUNTABLE. Round 11 stated it four ways `scale_claims` cannot read -- a
        point count, `out of 12`, a response-option count, and a comparison --
        so the count came back to one and the lift fired on an account that had
        mis-split the sentence. The POSITION settles it without reading the
        second scale at all: a scale printed BETWEEN the two names modifies the
        nearer one, and a scale governing a coordinated pair is printed after
        both. See `scale_sits_between`.
        """
        oid = about.get("names_another_variable")
        if not oid or value is None or not loc["located"]:
            return None
        if len(scale_claims(loc["sentence"] or "")) != 1:
            return None
        for o in others:
            if str(o.get("id")) != str(oid):
                continue
            if scale_sits_between(loc["sentence"] or "", var, o):
                return None
            ob = field_dict(o, "bounds")
            if str(ob.get("source") or "") not in BOUND_SOURCE_OF:
                return None
            try:
                if float(ob.get(side)) != float(value):
                    return None
            except (TypeError, ValueError):
                return None
            oloc = hay.locate(ob.get("quote"))
            return (str(oid) if oloc["located"] and oloc["sentence"] == loc["sentence"]
                    else None)
        return None

    shared: dict[str, str] = {}
    range_changing = derived_range_changes(var)
    rec["derived_range_changes"] = range_changing

    def _side(side: str, value: Any, necessary: Any) -> tuple[Any, str]:
        """`(admitted bound, how)` for one side."""
        if value is None:
            return None, "absent"
        if (src == "definitional" and necessary is not None and not contradicted):
            try:
                if float(value) == float(necessary):
                    return value, "kind_necessary"
            except (TypeError, ValueError):
                pass
        # THE MODEL'S READING REPLACES THE ATTRIBUTION HEURISTIC AND NOTHING
        # ELSE. Every guard that can only REMOVE a bound is still below it: the
        # derived-quantity rule, the numeral test, and (outside this function)
        # the contradiction by the variable's own printed values.
        if verdict is not None:
            if not verdict.get("establishes"):
                return None, "model_reading_refused"
            read_quote = str(verdict.get("quote") or "")
            if range_changing and anchor_score(var, _sentence_words(read_quote)) < 1.0:
                return None, "quote_states_the_source_quantity"
            if not numeral_in(read_quote, value):
                return None, "quote_does_not_print_it"
            return value, "model_reading"
        if not loc["located"]:
            return None, "quote_not_located"
        if not about["about_this_variable"]:
            return None, "quote_not_about_this_variable"
        # A DERIVED QUANTITY'S BOUND MUST BE STATED FOR THE DERIVED QUANTITY.
        #
        # A derived variable is NAMED AFTER WHAT IT IS DERIVED FROM -- `Change in
        # prescribed medicines` shares two of its three content words with
        # `Prescribed medicines ranged from 0 to 25 per patient` -- so the
        # attribution test scores 0.67, passes its own 0.5 threshold, names no
        # other variable (the level variable need not be declared at all), and
        # the LEVEL scale is attributed to the CHANGE. Round 6 closed this shape
        # with `bound_contradicted_by_printed_values`, which sees only the
        # variable's PRINTED values -- and a change score prints a mean and an
        # SD, so a positive mean change with an honest SD sits inside [0, 25] and
        # contradicts nothing. Measured: 24 real whole-number changes, ten of
        # them negative, returned GRIMMER `suspicious` (out_of_range) and SPRITE
        # `suspicious`, the latter asked to rebuild non-negative integers from a
        # quantity that is negative for ten of the twenty-four patients.
        #
        # SO A PARTIAL NAME MATCH IS NOT EVIDENCE HERE. Where the operation moves
        # the range, the sentence must name the WHOLE of the derived variable's
        # name -- the word that separates it from its source is exactly the word
        # a sentence about the source does not have.
        if range_changing and about["anchor_score"] < 1.0:
            return None, "quote_states_the_source_quantity"
        if about["names_another_variable"]:
            with_whom = _shared_scale(side, value)
            if not with_whom:
                return None, "quote_not_about_this_variable"
            shared[side] = with_whom
        if not numeral_in(quote, value):
            return None, "quote_does_not_print_it"
        # THE SENTENCE MUST ASSERT A RANGE, NOT MERELY BE ABOUT THE RIGHT NOUN
        # AND PRINT THE RIGHT DIGITS. See `SCALE_ASSERTING`: round 13's decoy
        # shares the variable's name-words and prints both bound numerals
        # while stating something else entirely (a count of people, not a
        # scale). Can only ever refuse (invariant 1).
        if not SCALE_ASSERTING.search(loc["sentence"] or ""):
            return None, "quote_does_not_assert_a_scale"
        return value, "stated"

    lo_passed, lo_how = _side("lower", lower, need_lo)
    hi_passed, hi_how = _side("upper", upper, need_hi)
    rec["quote_states_a_shared_scale_with"] = shared or None

    # THE BOUND IS ASKED THE QUESTION THE KIND'S BOUND WAS ALREADY ASKED: DOES
    # THIS VARIABLE'S OWN PRINTED VALUES FIT INSIDE IT?
    #
    # `stated` is the HARDEST bound source there is -- it licenses `impossible`
    # at the top of GRIM's ladder -- and until now nothing compared it against a
    # single number the paper printed. Three honest shapes defeat it, and all
    # three satisfy every existing test (the quote is the paper's own, it
    # locates, it is about this variable, and it prints the bound's numerals):
    #
    #   * an ITEM range read against a TOTAL score. `The Perceived Stress Scale
    #     items were each rated from 0 to 4` beside a total-score mean of 18.5
    #     (SD 6.2): GRIM `impossible`, GRIMMER and SPRITE `suspicious`,
    #     `check_sd_or_se` `highly_suspicious`.
    #   * a LEVEL scale read against a CHANGE score. `Mood was rated on a 1 to 7
    #     point scale` beside a mean change of -0.85: a change runs on
    #     [-(max-min), +(max-min)] and the level scale is not its range.
    #   * a scale attributed to the WRONG VARIABLE, which the sentence test can
    #     only narrow and never close.
    #
    # The refusal cannot invent anything -- it only ever withdraws a bound -- so
    # it is invariant-1 safe. WHAT IT COSTS, stated plainly: a paper whose own
    # printed mean lies outside the scale it states for that variable no longer
    # reaches `out_of_range` on that mean. That internal contradiction is a real
    # finding and it is now a NAMED REFUSAL carrying both facts, which is the
    # honest form of it: GRIM's `impossible` says "no integer sample of n can
    # produce this mean", and that is not the claim the evidence supports.
    contradicted_by_printed = values_outside(lo_passed, hi_passed, values)
    if contradicted_by_printed:
        lo_passed, lo_how = None, "contradicted_by_printed_values"
        hi_passed, hi_how = None, "contradicted_by_printed_values"
    rec["bound_contradicted_by_printed_values"] = contradicted_by_printed
    rec.update({"lower_passed": lo_passed, "upper_passed": hi_passed,
                "lower_admitted_by": lo_how, "upper_admitted_by": hi_how,
                "lower_stated_by_quote": lo_how in _BOUND_ADMITTED,
                "upper_stated_by_quote": hi_how in _BOUND_ADMITTED})
    # THE LABEL NAMES HOW THE BOUND WAS ADMITTED, NOT WHAT THE ACCOUNT DECLARED.
    #
    # `bound_source` was `BOUND_SOURCE_OF[declared_source]` and never consulted
    # `lower_admitted_by`, so a variable DECLARING `definitional` whose bound was
    # in fact admitted by reading a sentence -- by the vocabulary, or by a model
    # (wave 7c) -- was passed to GRIM and `check_sd_or_se` as
    # `logically_necessary`, the token meaning the KIND'S OWN LOGIC makes the
    # bound necessary. That is the `basis: "computed"` shape (CLAUDE.md 8e): a
    # true fact about the declaration printed as a stronger claim about the
    # evidence. Both tokens sit in `HARD_BOUNDS`, so nothing about severity
    # moves; what moves is that the record no longer asserts a necessity nobody
    # established.
    admitted = [how for how in (lo_how, hi_how)
                if how in _BOUND_ADMITTED and how != "absent"]
    rec["bound_source"] = (
        ASSUMED_BOUND_SOURCE if not admitted else
        BOUND_SOURCE_OF["definitional"]
        if all(how == "kind_necessary" for how in admitted) else
        BOUND_SOURCE_OF["stated"])
    failed = [(v, how) for v, how in ((lower, lo_how), (upper, hi_how))
              if how not in _BOUND_ADMITTED]
    if failed:
        # NEITHER SIDE IS PASSED WHEN EITHER SIDE FAILS, and the record has to
        # say so rather than carry a number beside the word `assumed`. That
        # combination is the defect the allowlist exists to stop -- a bound
        # reaching `scale_min` under a label saying we invented it -- and it
        # would be true here in the honest case too: the failure refuses every
        # family that reads this variable, so the surviving number could only
        # ever mislead a reader of the record.
        rec["bound_source"] = ASSUMED_BOUND_SOURCE
        rec["lower_passed"], rec["upper_passed"] = None, None
        if contradicted_by_printed:
            rec["reasons"].append({
                "reason": "bound_contradicted_by_printed_values",
                "detail": (f"the bound offered is [{lower}, {upper}] and this variable's "
                           "own printed values fall outside it ("
                           + ", ".join(contradicted_by_printed[:3])
                           + "), so it is not the range of the quantity they report")})
        elif any(how == "quote_states_the_source_quantity" for _, how in failed):
            rec["reasons"].append({
                "reason": "bound_stated_for_the_source_quantity",
                "detail": (f"the account derives this variable ({range_changing!r}) and the "
                           f"sentence offered for its bounds names only part of its name "
                           f"(anchor {about['anchor_score']}): {str(loc['sentence'])[:80]!r}")})
        elif all(how == "quote_not_located" for _, how in failed):
            rec["reasons"].append({
                "reason": "bound_quote_not_located",
                "detail": f"bounds quote {str(quote)[:60]!r}: {loc['why']}"})
        elif any(how == "model_reading_refused" for _, how in failed):
            # THE REASON CODE IS THE EXISTING ONE, DELIBERATELY. Wave 7c changes
            # how a premise is FILLED and not what the bridge does with it, so a
            # refusal it produces has to arrive in the vocabulary
            # `checks.REASONS` already closes over; the model's own words ride in
            # the detail, where a reader can weigh them.
            rec["reasons"].append({
                "reason": "bound_quote_does_not_state_it",
                "detail": (f"a model read the sentence(s) this paper offers for this "
                           f"variable's range and none of them states it: "
                           f"{str((verdict or {}).get('reason'))[:120]!r} "
                           f"({(verdict or {}).get('candidate_id')}, "
                           f"{(verdict or {}).get('model')})")})
        elif any(how == "quote_does_not_assert_a_scale" for _, how in failed):
            rec["reasons"].append({
                "reason": "bound_quote_does_not_assert_a_scale",
                "detail": (f"the quote is about this variable and prints the bound's own "
                           f"numeral(s), but its sentence does not read as stating a range, "
                           f"a scale, a rating, a coding, or a minimum/maximum: "
                           f"{str(loc['sentence'])[:80]!r}")})
        else:
            if about["names_another_variable"]:
                why = f"its quote describes `{about['names_another_variable']}`, not this variable"
            elif not about["about_this_variable"]:
                why = (f"its quote is not about this variable (anchor "
                       f"{about['anchor_score']}): {str(loc['sentence'])[:80]!r}")
            elif contradicted:
                why = ("the kind's own bound is contradicted by this variable's printed "
                       f"values ({', '.join(contradicted[:3])}), and the quote does not "
                       "print the bound")
            else:
                why = ("the quote does not print "
                       + " or ".join(str(v) for v, _ in failed))
            rec["reasons"].append({"reason": "bound_quote_does_not_state_it", "detail": why})
    return rec


#: THE FLOOR OF the reach back to an anaphoric averaging sentence's antecedent,
#: in sentences. The BOUNDARY is the enclosing section -- see
#: `Haystack.section_start` -- and this number now only guarantees that a short
#: section does not reach LESS far than it used to.
#:
#: IT WAS THE BOUNDARY, AND IT WAS A PROXY FOR ONE. The comment it replaces said
#: so outright: "a reach that crosses a whole section would attach a variable's
#: veto to prose about something else. Six is what a Methods paragraph is." The
#: intent was a section, the instrument was a sentence count, and a paper that
#: writes two ordinary sentences more than the guess -- where the sheets went,
#: who collected them -- loses its true antecedent to an arbitrary cutoff while
#: every word of the candidate window is still the same Methods paragraph the
#: constant was named for. The section map (`sections.map_sections`) is the
#: thing itself, it is already built, and it reads the text and nothing else.
#:
#: THE LARGER OF THE TWO, ALWAYS. A refusal's candidate window may only ever
#: grow: a window that narrows can leave a false accusation standing, and one
#: that grows can only cost a check. So a section shorter than six sentences
#: still reaches six, and no antecedent reachable before this change is
#: unreachable after it.
#:
#: AND IT CAN COUNT EVIDENCE RATHER THAN POSITION, FOR A CALLER THAT ASKS.
#: MEASURED (2026-09-12): with the antecedent in `## Methods` and the anaphor
#: under `## Statistical analysis`, the section floor contributes NOTHING --
#: the antecedent is in a different section -- so the reach collapses to a bare
#: six-sentence cut, and stage 1 offered the withdrawing sentence to a model at
#: five ordinary procedural sentences of separation and not at six. One extra
#: sentence about where the sheets went was the whole difference between a
#: model answering `establishes: true` (paid, $0.068350) and an `impossible`
#: standing on an honest paper.
#:
#: `count_naming` SPENDS THE SIX ON SENTENCES THAT NAME A DECLARED VARIABLE, so
#: filler cannot consume an antecedent budget and a heading cannot end the
#: search. It is still a bound: at most six naming sentences' worth of
#: antecedents, however far back they sit.
#:
#: AND IT IS NOT THE DEFAULT, WHICH IS A DECISION AND NOT AN OVERSIGHT.
#: `tests/test_scaffold_checks_round12.py::...::test_the_reach_still_stops_at_
#: the_section_it_is_in` pins the opposite answer for the FREE PATH, with a
#: stated reason -- an Introduction sentence is not a Methods anaphor's subject
#: -- and that path withdraws a check with NO judge downstream of it. Stage 1
#: is the other case: a wrong candidate there costs one line of a prompt and a
#: model decides, so a reach ordered by POSITION is a filter by the same
#: argument `premise_reading.MAX_REFUSAL_CANDIDATES` already makes about a cap.
#: The two consumers therefore differ deliberately. Widening the FREE path to
#: match would overturn round 12 and is Greg's call, not this pass's.
_ANAPHORA_REACH = 6


def _names_a_declared_variable(sentence: str, declared: list[dict],
                               *, agreed: bool = False) -> bool:
    """Does this sentence name ANY declared variable well enough to be about it?

    `agreed` ASKS THE QUESTION SO THAT AN ANSWER CAN ONLY REMOVE AN ACCUSATION.
    See `anchor_score_agreed`: where a YES takes a refusal away, the two
    readings of the name must agree on it.
    """
    words = _sentence_words(sentence)
    score = anchor_score_agreed if agreed else anchor_score
    return any(score(o, words) >= 0.5 for o in declared)


def is_anaphoric_averaging(sentence: str, declared: list[dict]) -> bool:
    """Does this sentence state an averaging fact in a clause that names NO
    declared variable?

    THE UNIT IS THE CLAUSE BECAUSE THE ANAPHOR IS IN THE CLAUSE. English writes
    `<something else> ..., which were averaged` and `<something else> ...; the
    two were averaged` the same way, and in both the averaging predicate has no
    subject of its own -- that is what makes it anaphoric. Asking whether the
    whole SENTENCE names a declared variable answers a different question, and
    answers it wrongly whenever a sentence mentions two things (round 16 D2).

    A YES HERE TAKES THE ANAPHORA RESCUE AWAY, so the name test is the agreed
    one. MEASURED at `108e9ec6` on the same honest half-point paper as
    `anchor_score_agreed`, with the abbreviation moved INTO the averaging clause
    -- `Each plot was visited twice; the two cards were averaged and filed
    beside BMI.` -- the clause newly named a declared variable, stopped being
    anaphoric, never reached `_antecedent_ids`, and GRIM returned `impossible`.
    At `a24add71` BMI named nothing, the clause was anaphoric, the antecedent
    walk found seed vigour and the step was withdrawn.
    """
    return any(not _names_a_declared_variable(part, declared, agreed=True)
               for part in _clauses(sentence) if AVERAGED.search(part))


def _best_named(declared: list[dict], words: set[str],
                *, acronyms: bool = True) -> set[str]:
    """The declared ids this sentence names BEST, or an empty set.

    ONLY THE BEST-NAMED VARIABLE OF A SENTENCE IS KEPT, which is what makes this
    comparison able to take a refusal AWAY rather than merely fail to add one --
    a rival does not join the antecedent set, it takes the sentence outright.
    MEASURED at `108e9ec6` on the same honest half-point paper as
    `anchor_score_agreed`: the one in-reach sentence naming the variable --
    `Vigour and BMI were both entered on the same sheet.` -- scores 0.5 for
    `Seed vigour` and 1.0 for the newly-anchorable `BMI`, so the antecedent set
    became `{var:rival}` alone, the anaphoric `The two cards were averaged for
    each plot.` was attributed to nobody, and GRIM returned `impossible`. At
    `a24add71` the same sentence returned `{var:vigour}` and the step was
    withdrawn.

    SO `_antecedent_ids` TAKES BOTH READINGS AND UNIONS THEM, rather than
    reverting to the old one: an antecedent is a candidate FOR A REFUSAL, so
    adding one can only ever cost a check, and a paper that names its variable
    `ADL` in the antecedent sentence should still be found. Neither reading may
    veto the other.
    """
    scored = [(anchor_score(o, words, acronyms=acronyms), str(o.get("id")))
              for o in declared]
    best = max((s for s, _ in scored), default=0.0)
    return {vid for s, vid in scored if s == best} if best >= 0.5 else set()


def _antecedent_ids(hay: Haystack, offset: int, declared: list[dict],
                    *, count_naming: bool = False) -> set[str]:
    """Every declared variable named by ANY sentence within reach, union -- not
    only the NEAREST one that names one.

    WAVE 7D, round 12's F2: an ordinary Methods sentence about a DIFFERENT
    declared variable, sitting between the true antecedent and the anaphor,
    used to steal the slot outright. `Peal quality was scored in whole points
    ... by each of two judges. Striking accuracy was recorded at the same
    practice. The reported figure is the mean of the pair.` resolved to
    `var:strike` (the nearest name) and never to `var:peal` (the true
    antecedent, two sentences back) -- GRIM `impossible` on an honest paper,
    surviving a real paid reading too, because `_averaging_candidates` uses
    this same function to decide whether the model is even OFFERED the
    sentence. Stopping at the first sentence that names anything is a
    POSITION-ORDERED cut of exactly the kind this wave's redesign removes for a
    refusal premise: recall has to be a WINDOW.

    A TIE NAMES BOTH, deliberately, and this is the same rule extended from one
    sentence to the window: this feeds a REFUSAL, and an ambiguous antecedent
    that withdraws two steps costs two checks, while one that withdraws
    neither leaves a false accusation standing. Two declared variables named by
    two DIFFERENT sentences within reach are exactly as ambiguous as two named
    by the same one -- nothing in the position or the wording says which the
    anaphor meant -- so both are returned rather than whichever happens to sit
    closer to the anaphor.

    AND THE WINDOW IS THE ENCLOSING SECTION, not a sentence count. See
    `_ANAPHORA_REACH`: six sentences was a proxy for a section boundary by its
    own comment's admission, and the section map is the boundary itself. The
    count survives as a FLOOR, so this is purely recall-widening. It does NOT
    resolve an antecedent and a distractor sitting in the SAME section -- that
    needs disambiguation, not a wider window, and the tie rule above is what
    governs it.

    `count_naming` SPENDS THE BUDGET ON EVIDENCE INSTEAD OF ON POSITION, and it
    is off by default. The section floor is no help at all when the antecedent
    is in the PREVIOUS section, which is the ordinary anatomy of a paper --
    `## Methods` says how each judge scored, `## Statistical analysis` says what
    the reported figure was taken to be -- so in that shape the whole reach is
    the bare six and six ordinary procedural sentences put the antecedent out of
    range. Under `count_naming` a sentence that names nothing is stepped over
    for free. WHY IT IS NOT THE DEFAULT: the free path's reach is pinned the
    other way with a reason, and only the stage-1 recall net has a judge
    downstream. See `_ANAPHORA_REACH`.

    AND THE ABBREVIATION RELAXATION MAY ADD AN ANTECEDENT AND MAY NOT REMOVE
    ONE. See `_best_named`: only the best-named variable of each sentence is
    kept, so a rival that newly anchors does not merely join the set -- it takes
    the sentence outright. Both readings of every name are therefore taken, and
    the budget is spent on the ordinary one, so the walk is the same length it
    was and the answer is a superset.
    """
    key = (offset, count_naming, frozenset(str(o.get("id")) for o in declared))
    got = hay._antecedents.get(key)
    if got is not None:
        return set(got)
    out: set[str] = set()
    floor = hay.section_start(offset)
    seen = 0
    for lo, prev in hay.iter_preceding_sentences(offset):
        if seen >= _ANAPHORA_REACH and lo < floor:
            break
        if not prev:
            continue
        if not count_naming:
            seen += 1
        words = _sentence_words(prev)
        named = _best_named(declared, words)
        if named:
            if count_naming:
                seen += 1
            out |= named
        # AND THE PRE-ABBREVIATION READING OF THE SAME SENTENCE, ADDED AND NOT
        # SUBSTITUTED. It spends no budget: `seen` is counted on the ordinary
        # reading alone, so the walk is exactly as long as it was and this can
        # only ever return MORE antecedents than `108e9ec6` did.
        out |= _best_named(declared, words, acronyms=False)
    hay._antecedents[key] = set(out)
    return out


def averaging_statements(var: dict, hay: Haystack, others: list[dict],
                         passages: "list[str] | tuple[str, ...]" = ()) -> list[str]:
    """Every clause of the paper saying THIS variable's reported quantity is an
    average of several per-subject observations.

    A GUARD HAS TO ASK ITS QUESTION WHERE THE PAPER ANSWERED IT. The averaging
    veto read the clauses of ONE sentence -- the one the account happened to
    offer for granularity -- so a paper that says the whole-unit thing in one
    sentence and the averaging thing in the NEXT one defeated it by ordinary
    honest writing: `Vegetable portions on each plate were counted in whole
    portions by the lunchtime supervisor.` establishes a step, and `Each pupil's
    vegetable index is the mean of her three lunchtime plate observations.`
    withdraws it, and only the first was read. Measured (round 9): GRIM
    `impossible` on a step-1/3 index whose mean is exact. `variable.derivation`
    closes the same shape from the account's side and is a FIELD THE ACCOUNT MAY
    LEAVE NULL, which is an honest omission and not evidence of anything.

    AND ENGLISH USES PRONOUNS, WHICH IS THE HALF THAT WAS STILL OPEN. Every
    reader here -- this one, the sentence-local one, and the model's own
    pre-filter -- required the averaging sentence to NAME the variable. A paper
    does not repeat a noun phrase it has just introduced: `Bed health was scored
    in whole points on a 0 to 12 card by each of two stewards. The reported
    figure is the mean of the pair.` Six ordinary phrasings (`the pair`, `this
    index`, `the latter`, `it`, `each plot's score`, `the two were averaged`)
    left the step of 1 standing and returned GRIM, GRIMMER and SPRITE
    `impossible` on an honest half-point index -- and offered a model ZERO
    candidates, so a paid pass could not rescue it either (round 11 F1/F9). A
    sentence that names NO declared variable is resolved against the DISCOURSE:
    the nearest preceding sentence that names one is its subject. Round 4's
    sentence is untouched by construction -- it names Mood, so it is not
    anaphoric and never reaches this path.

    AND THE TABLE'S OWN CAPTION AND FOOTNOTES ARE `passages`. This was the one
    refusal premise that never read them: `model_output_reason`, `table_notes`
    and both `named_estimator` callers read the caption, while the averaging veto
    read the served text and `variable.derivation` and nothing else -- so
    `Values are the mean of two independent ratings.`, the JAMA/BMJ house-style
    footnote that is exactly where a paper says this, withdrew the step in prose
    and withdrew nothing under a table (round 11 F4).

    AND THE ANAPHOR LIVES IN A CLAUSE, NOT IN A SENTENCE (round 16 D2). The
    fallback used to require the whole SENTENCE to name no declared variable, so
    an averaging clause that is anaphoric for THIS variable while the sentence
    names a DIFFERENT one in passing was invisible: `Movements overhauled per
    workshop were logged in the daybook alongside the two cards, which were
    averaged.` gives `which were averaged` to nobody, falls back to the whole
    sentence, finds `Movements overhauled` named there, and hands the clause to
    it -- GRIM `impossible` on the grade the two cards actually belong to. The
    gate now asks of the CLAUSE CARRYING THE AVERAGING STATEMENT, which is where
    the question lives, and a sentence naming nothing declared still has clauses
    naming nothing declared, so nothing reachable before is unreachable now.

    A VARIABLE NO SENTENCE CAN BE ATTRIBUTED TO IS REFUSED RATHER THAN DEFERRED.
    `name_is_anchorable` is False for a name whose every word is generic (`Total
    count`, `Item score`), and for such a variable every branch above returns
    "nobody" on every sentence ever written -- so `defer` means this veto can
    never fire, while `granularity_verification`'s KIND licence needs no name at
    all and fires anyway. That asymmetry was measured as a live false accusation
    (a `count` named `Total count`, its paper stating outright that the printed
    figure is the mean of three observers' tallies, GRIM `impossible`). An
    unnameable variable is in exactly the position a TABLE FOOTNOTE is in --
    there is no sentence for the statement to be about -- so it gets the same
    `refuse` mode, for the same stated reason.

    IT CAN ONLY EVER REMOVE A CHECK, which is why the scan may be loose.
    """
    out: list[str] = []
    declared = [var] + [o for o in others
                        if str(o.get("id")) != str(var.get("id"))]
    vid = str(var.get("id"))
    unattributed = "defer" if name_is_anchorable(var) else "refuse"
    for off, sent in hay.sentences_matching(AVERAGED):
        said = _averaging_here(var, sent, others, unattributed=unattributed)
        if said is None and is_anaphoric_averaging(sent, declared) \
                and vid in _antecedent_ids(hay, off, declared):
            hit = AVERAGED.search(sent)
            said = hit.group(0).strip() if hit else None
        if said and said not in out:
            out.append(said)
    for passage in passages:
        # A CAPTION OR A FOOTNOTE GOVERNS ITS OWN TABLE and has no sentence to be
        # about, so an averaging statement in one that is not plainly about
        # ANOTHER declared variable withdraws the step for every variable printed
        # under it.
        said = _averaging_here(var, passage, others, unattributed="refuse")
        if said and said not in out:
            out.append(said)
    return out


def _table_furniture_by_id(account: dict) -> dict[str, list[str]]:
    """`{table_id: [caption, footnote, footnote, ...]}`, the tolerant read of a
    table record shared by every reader below -- `table_passages`,
    `table_footnotes` and `document_furniture_text` -- so a fourth copy of
    "is this a table, does it have an id, are its footnotes a list" is not
    what a fifth premise type gets when it needs table furniture too (wave 7d,
    item 3: a registry, not a fifth manually-wired call site).
    """
    out: dict[str, list[str]] = {}
    doc = account.get("document")
    tables = doc.get("tables") if isinstance(doc, dict) else doc
    for t in (tables if isinstance(tables, list) else []):
        if not isinstance(t, dict) or not t.get("id"):
            continue
        bits = [str(t.get("caption") or "")]
        notes = t.get("footnotes")
        bits += [str(f) for f in notes] if isinstance(notes, list) else []
        out[str(t["id"])] = [b for b in bits if b.strip()]
    return out


def table_passages(account: dict, values: list[dict]) -> list[str]:
    """The caption and footnotes of every table these values sit in.

    THE FIELD THE PIPELINE ITSELF WRITES AND NOTHING READ. `document.build`
    carries a table's footnotes on the table record and `coverage` reads them;
    `_captions` reads only `caption`, so a premise stated in a lettered footnote
    was in the account and invisible to every judgement.
    """
    by_id = _table_furniture_by_id(account)
    out: list[str] = []
    for v in values:
        loc = v.get("location") or {}
        for passage in by_id.get(str(loc.get("table_id") or ""), []):
            if passage not in out:
                out.append(passage)
    return out


def table_footnotes(account: dict) -> dict[str, str]:
    """`{table_id: joined footnote text}` -- TABLE FURNITURE ALONE, without the
    caption, keyed by table so a per-value reader can add it as a channel of
    its own beside `_captions`.

    ROUND 12'S F3: `named_estimator` read the column band, the caption, the
    value's own sentence and a document-wide governing sentence -- four places
    -- and NONE of them was this one. `value_premise`'s `analysis_n_varies`
    read the caption and the served text and NEITHER was this one either. On a
    JATS-sourced paper the footnote is not in the served body at all
    (`extraction/jats.py` strips `table-wrap-foot` before the text reaches the
    model), so a paper that states its estimator, its weighting or its varying
    analysis n in a table footnote -- exactly where JAMA, BMJ and the Lancet
    house style puts these three statements -- had NO channel by which any of
    the three refusals could ever see it. Round 11 wired this field into the
    ONE refusal that already read it (the averaging veto, via
    `table_passages`); this is the same field reaching the other three.
    """
    out: dict[str, str] = {}
    doc = account.get("document")
    tables = doc.get("tables") if isinstance(doc, dict) else doc
    for t in (tables if isinstance(tables, list) else []):
        if not isinstance(t, dict) or not t.get("id"):
            continue
        notes = t.get("footnotes")
        bits = [str(f) for f in notes] if isinstance(notes, list) else []
        bits = [b for b in bits if b.strip()]
        if bits:
            out[str(t["id"])] = " ".join(bits)
    return out


def document_furniture_text(account: dict) -> str:
    """Every table's caption and footnotes, joined into one blob, for a
    DOCUMENT-WIDE refusal scan.

    THE ALTERNATIVE-BASE CEILING (`paper_max_n`/`printed_subject_counts`) reads
    only the served text, so a paper that prints its eligible cohort or its
    full membership roll ONLY in a table's footnote or caption -- the ordinary
    place for a flow table's own tally -- put its own denominator above its own
    ceiling, the same gap `CEILING_STATISTICS` was added to close from the
    account's n rows. Widening what text is SCANNED cannot loosen how the
    ceiling is USED: `other_bases_that_fit` still requires the paper's own two
    printed numbers to reproduce exactly at the alternative, so a looser
    ceiling only ever NAMES more alternatives, and naming one only ever
    REFUSES a check (`printed_subject_counts`'s own rule, unchanged here).
    """
    by_id = _table_furniture_by_id(account)
    return " ".join(b for bits in by_id.values() for b in bits)


#: THE PREMISE-CHANNEL REGISTRY (wave 7d, item 3). One list of REFUSAL premise
#: types and the CHANNELS each is wired to read a withdrawing statement from,
#: beyond the served body every one of them already scans in full
#: (`_governing_statement`, `averaging_statements`, `printed_subject_counts`).
#:
#: NOT A DISPATCH TABLE. Each channel is still read by its own named function
#: (`table_notes`/`named_estimator` for `caption`; `table_footnotes` for
#: `footnote`; the served text itself for `body`) -- inventing indirection here
#: would trade one hand-wired call site for one hand-wired registry entry,
#: which is the same defect a level up. What this buys is a single place that
#: states what "every channel that could plausibly carry it" MEANS for a
#: refusal premise, so a CONSERVATION TEST can walk the matrix
#: (`tests/test_scaffold_checks_round12.py::TestThePremiseChannelRegistry`)
#: rather than a channel going quiet being something only a fresh adversarial
#: fixture would notice next round -- the exact recurrence CLAUDE.md's
#: [[the-parallel-path-lost-twelve-capabilities]] and [[a-fix-can-repair-its-own-symptom]]
#: both name: a capability wired into ONE call site is a gap at every other
#: one until something makes the ABSENCE visible by construction.
#:
#: `alternative_base` READS THE SAME THREE CHANNELS FOR A DIFFERENT REASON: it
#: is not adjudicated at all (D71/wave 7c's explicit exception -- a model verdict
#: may never loosen it), so widening ITS channels widens only what TEXT a
#: regex may scan, never what MECHANISM decides. See `document_furniture_text`.
REFUSAL_PREMISE_CHANNELS: dict[str, frozenset[str]] = {
    "averaging": frozenset({"body", "caption", "footnote"}),
    "estimator": frozenset({"body", "caption", "footnote"}),
    "weighted_percentage": frozenset({"body", "caption", "footnote"}),
    "varying_n": frozenset({"body", "caption", "footnote"}),
    "alternative_base": frozenset({"body", "caption", "footnote"}),
}


def granularity_verification(var: dict, hay: Haystack, others: list[dict],
                             values: list[dict], verdict: dict | None = None,
                             averaging_verdict: dict | None = None,
                             passages: "list[str] | tuple[str, ...]" = (),
                             attachment_verdict: dict | None = None,
                             subjects: "frozenset[str]" = frozenset()) -> dict:
    """`variable.granularity.verification` -- whether a per-subject step of 1 is
    established, and by what.

    TWO LICENCES, AND THE SECOND IS NEW IN WAVE 7b. The paper's own sentence
    (`stated`), or the declared KIND where the kind makes the step logically
    necessary (`kind_necessary`): a count of things moves in whole things
    whatever any sentence says. The second closes the fragment-matching channel
    from the other side -- no quote is needed at all when the kind settles it --
    and recovers `var:ebp_reach` on ajcp.70049, a `count` whose only granularity
    sentence describes what the variable IS rather than what its step is.

    THE SENTENCE TEST, when there is no kind licence, is three conditions and
    round 2 defeated all three:
      1. the quote locates as a WHOLE-WORD contiguous span (`counted as w` is
         exactly `_MIN_FRAGMENT` characters and is two word fragments);
      2. the discreteness vocabulary and this variable's name are in the SAME
         CLAUSE (`Mood was assessed at each visit; falls were counted as whole
         events` names both and establishes nothing about Mood), and where the
         vocabulary member is the noun-phrase head `number of`, what it counts
         is this variable (`discreteness_about`, round 16 D3);
      3. no other declared variable is named more strongly.
    Each can only remove a check, never supply a premise.

    `verdict` IS THE MODEL'S READING OF THIS PREMISE (wave 7c), and None on
    every path the paid pass has not run, where the code below is unchanged.
    Given one, it replaces the SENTENCE TEST -- the vocabulary, the clause split
    and the attribution -- and it replaces nothing else. The two vetoes still
    veto: a sentence or a derivation saying the reported quantity is an AVERAGE
    withdraws the step whatever a model says, because the average of k whole
    numbers is not whole and no reading of the prose changes that. The KIND's
    own licence is untouched in both directions: a `count` moves in whole things
    as a matter of what a count is, which is a schema fact rather than a
    classification of the paper's prose, and it was never the failure mode.

    `attachment_verdict` IS A MODEL READING OF THE LICENSING PASSAGE (round 24,
    widened in round 28), and None on every path the paid pass has not run, where
    the code below is unchanged. Given one that WITHDRAWS -- meaning the passage
    does not show that the figure the paper reports for one subject is a whole
    number, whether because its whole-number words describe some other quantity,
    because the passage takes whole-number recording away from the target, or
    because what it makes whole is one observation rather than the reported
    figure -- the SENTENCE licence is withdrawn. It is a veto and nothing else,
    which is the whole of why a model is allowed near a licence at all:

      * it is ANDed into `establishes` and appears in no other expression, so it
        can only ever turn a True into a False. No branch below lets a verdict
        make `establishes`, `kind_licenses` or `source` more permissive than they
        were without it, and round 24 asserts that over the full cross-product
        rather than resting on this sentence.
      * the KIND's licence is untouched, deliberately. A `count` moves in whole
        things whatever any sentence is about, so a variable whose kind settles
        it keeps `logically_necessary` -- and `adjudication_attach` does not ask
        about such a variable at all, because no verdict could move it.
      * the two vetoes still veto: an averaging statement withdraws the step
        whether or not a model was asked anything.

    `subjects` IS `subject_terms(account)` -- WHAT ONE n COUNTS (round 26), and
    empty on every path that has no account to read it from, where the
    per-observation branch below simply has no subject to compare a restrictor
    against and so withdraws rather than guessing. A licensing sentence that
    states its whole-number claim PER OBSERVATION -- at each of three visits, by
    each of two readers, as a whole number of quarter points -- has established
    the step for an observation and said nothing about the value the table
    prints, so the SENTENCE licence fails and `discreteness_source` falls back to
    `assumed`. It is a third veto in the averaging family and it reaches the same
    two branches the other two reach, including the model's. THE KIND'S LICENCE
    IS UNTOUCHED, for round 24's reason and not as an oversight: a count of
    things is a whole number of things whatever adjunct the sentence carries, and
    the sentence does not say the reported value is a mean -- it may be the final
    visit's count, or the total. Asserting the aggregation would SUPPLY a premise
    rather than narrow one.
    """
    gran = field_dict(var, "granularity")
    step = gran.get("per_subject_step")
    quote = gran.get("quote")
    kind = str(var.get("kind") or "")
    contradicted = _kind_contradicted(var, values)
    loc = hay.locate(quote)
    sentence = loc["sentence"] or ""
    says_step = discreteness_about(quote, var)
    # AND WHERE IT DOES NOT, WHETHER THAT IS BECAUSE THE PAPER SAID THE OPPOSITE.
    # `quote_states_discreteness: False` covers two facts a reader must be able
    # to tell apart -- a sentence that is silent about granularity, and one that
    # DENIES it. The second is the stronger evidence there is against a step of
    # 1, and folding it into the first would report a paper's own disclosure as
    # an absence ([[absence-must-be-representable]]).
    denied = None if says_step else discreteness_denial(quote, var)
    about = about_this_variable(var, sentence, others) if loc["located"] else \
        {"anchor_score": 0.0, "about_this_variable": False,
         "names_another_variable": None, "other_variable_score": 0.0}
    # THE CLAUSE THAT ESTABLISHES THE STEP, AND THE CLAUSE THAT WITHDRAWS IT.
    #
    # Every clause of the located sentence that is about THIS variable is read
    # twice: for discreteness vocabulary, which is what establishes a step of 1,
    # and for AVERAGING vocabulary, which says the reported quantity is the mean
    # of several observations and so does NOT move in whole units however whole
    # the observations were. A veto anywhere in the sentence beats an
    # establishment anywhere in it -- the paper has said both, and refusing is
    # the only reading that cannot accuse an honest paper (invariant 1).
    clause = None
    averaged = None
    averaged_where = None
    per_observation = None
    per_observation_where = None
    licensed = None
    blocked_by = None
    unattributed = None
    attributed_by = None
    if loc["located"]:
        # THE VETO IS ASKED OF THE WHOLE SENTENCE AND OF ITS CLAUSES; THE
        # ESTABLISHMENT ONLY OF A CLAUSE. See `_averaging_here`: a clause
        # boundary may narrow a licence and may never narrow a refusal.
        averaged = _averaging_here(var, sentence, others)
        if averaged is not None:
            averaged_where = "granularity_quote"
        # AND PER WHAT THE WHOLE-NUMBER CLAIM IS MADE (round 26). Asked of the
        # SENTENCE and not of the clause, because the adjunct that answers it is
        # routinely written behind a comma the clause splitter cuts on; the
        # window inside `_per_governing` is what keeps it from reaching across a
        # coordinated second assertion.
        # ONE MATCH THIS VARIABLE'S OWN IS ENOUGH (round 27), which is the same
        # policy as the line above this loop: a veto anywhere in the sentence
        # beats an establishment anywhere in it. Round 26 required UNANIMITY
        # here, and an ordinary second mention -- `..., and the card was printed
        # in whole units` -- restored the licence on five of seven probes.
        per_observation = discreteness_is_per(sentence, var, subjects)
        if per_observation is not None:
            per_observation_where = "granularity_quote"
        for part in _clauses(sentence):
            here = about_this_variable(var, part, others)
            if not (here["about_this_variable"] and not here["names_another_variable"]):
                continue
            hit = AVERAGED.search(part)
            if not says_step or hit:
                continue
            # AND THE ASSERTION INSIDE THE CLAUSE IS ASKED WHO IT IS ABOUT. A
            # clause naming this variable may coordinate a whole-unit claim
            # about a DIFFERENT, UNDECLARED quantity, which neither the clause's
            # own bag of words nor `names_another_variable` can see. See
            # `_discreteness_licence`.
            said, blocker, unresolved, how = _discreteness_licence(var, part, others)
            if blocked_by is None:
                blocked_by = blocker
            if unattributed is None:
                unattributed = unresolved
            if said is not None and clause is None:
                clause, licensed, about, attributed_by = part, said, here, how
    # AND THE SAME QUESTION IS ASKED OF THE REST OF THE PAPER. The sentence the
    # account offers for granularity is one sentence of many, and the sentence
    # that says the reported quantity is an average is usually a DIFFERENT one.
    # See `averaging_statements`.
    averaged_elsewhere = averaging_statements(var, hay, others)
    if averaged is None and averaged_elsewhere:
        averaged, averaged_where = averaged_elsewhere[0], "served_text"
    # AND OF THE TABLE'S OWN CAPTION AND FOOTNOTES. See `averaging_statements`:
    # this was the one refusal premise that never read the furniture the paper
    # prints its own house-style statement in.
    averaged_in_table = [said for said in
                         (_averaging_here(var, p, others, unattributed="refuse")
                          for p in passages) if said]
    if averaged is None and averaged_in_table:
        averaged, averaged_where = averaged_in_table[0], "table_furniture"
    # AND OF THE PASSAGE A MODEL GRANTED THE STEP ON. Under a verdict the step
    # may be granted by any of the candidate sentences, including one the
    # account never offered, and `establishes = verdict and averaged is None`
    # never re-read the granting quote -- so a `true` on the averaging sentence
    # ITSELF would have licensed a whole-number step. No attribution test is
    # applied here on purpose: the model has just said this passage establishes
    # the step FOR THIS VARIABLE, so a passage that also says the quantity is an
    # average has contradicted the evidence it was granted on.
    if averaged is None and verdict is not None and verdict.get("establishes"):
        hit = AVERAGED.search(str(verdict.get("quote") or ""))
        if hit:
            averaged, averaged_where = hit.group(0).strip(), "granting_quote"
    # AND A MODEL MAY SAY IT WHERE THE VOCABULARY CANNOT SEE IT (round 10). Under
    # a model `true` on the step, `AVERAGED` was the only guard left on the
    # granted licence, and a closed vocabulary is what every round since the
    # sixth has defeated. `premise_reading` now asks the WITHDRAWING question of
    # the sentences that carry combination language, and its polarity is the
    # safety argument: a verdict here can only ever ADD this veto, so a wrong one
    # costs a check and cannot buy an accusation.
    if averaged is None and averaging_verdict is not None \
            and averaging_verdict.get("establishes"):
        averaged = _one_line_quote(averaging_verdict.get("quote"), 120) or "an average"
        averaged_where = "model_reading"
    # AND THE ACCOUNT'S OWN DERIVATION SAYS IT TOO, WITHOUT A SENTENCE. The
    # schema asks for `derivation` -- "the formula in the paper's words, when the
    # variable is computed from others" -- and nothing read it: the account whose
    # step of 1 reached GRIM said, in its own record, `mean of the three monthly
    # pill counts`. It is a stronger witness than the prose, because in that
    # field the word cannot be the GROUP mean of the variable: the field is about
    # how the variable itself is built.
    # AND IT MAY BE WRITTEN AS ARITHMETIC RATHER THAN AS A WORD. The field the
    # schema asks for a FORMULA was being read by a list of nouns; see
    # `formula_reports_an_average`.
    said_derived = derivation_reports_an_average(var)
    derived_average = said_derived[:120] if said_derived else None
    # AND THE KIND'S OWN LICENCE IS WITHDRAWN BY THE SAME SENTENCE. `count` makes
    # a step of 1 necessary because a count of things is a whole number of
    # things -- but the MEAN of three whole counts is not, and a paper that says
    # so in the sentence it offers for that variable has contradicted the kind as
    # surely as a printed 2.40 on a `binary` does.
    kind_licenses = (kind in DISCRETENESS_NECESSARY_KINDS and not contradicted
                     and averaged is None and derived_average is None)
    establishes = (clause is not None and averaged is None
                   and derived_average is None and per_observation is None)
    if verdict is not None:
        # AND THE PAID PATH IS UNTOUCHED BY THE PER-WHAT NARROWING, which is
        # round 25's call taken again rather than a new one. Under a verdict this
        # function replaces the SENTENCE TEST wholesale, and `per_observation` is
        # part of that test: it says the paper's words do not ESTABLISH a
        # per-subject step, which is an absence-of-licence argument and not the
        # arithmetic fact `AVERAGED` carries, so it is not strong enough to
        # overrule a model that was shown the passage and asked. A model
        # answering `true` on `in whole points by each of two keepers` is a model
        # failure of round 24's class, and the veto built for that class is a
        # QUESTION put to a model, never a regex overriding one. Recorded as
        # residue in `tests/test_scaffold_checks_round26.py`, not closed here.
        establishes = (bool(verdict.get("establishes")) and averaged is None
                       and derived_average is None)
        if establishes:
            clause = str(verdict.get("quote") or "") or clause
    # AND A MODEL MAY SAY THE LICENSING PASSAGE WAS TALKING ABOUT SOMETHING ELSE
    # (round 24). This is the ONE line the attachment verdict participates in,
    # and it is an AND: `withdrawn` can only take `establishes` from True to
    # False, never the other way, whichever of the two branches above set it.
    # Recorded before the AND so the record can say a licence WAS withdrawn
    # rather than merely that one was never granted -- an absence and a removal
    # are different facts and a docket that cannot tell them apart is the
    # [[absence-must-be-representable]] failure at an artifact boundary.
    # `withdraws` AND NOT `establishes`, because this is the one premise whose
    # question is asked in the direction where `establishes` means the premise
    # HOLDS (round 28; see `premise_reading.WITHDRAWN_ON_FALSE` for the four
    # inverted runs that measured why it had to be). `index` computes the field
    # through `premise_reading.withdraws`, so the filing rule and this reader
    # cannot drift apart. A row that carries no `withdraws` -- a reading written
    # by an older pipeline -- withdraws nothing, which loses a check and cannot
    # buy an accusation.
    withdrawn = bool(attachment_verdict is not None
                     and attachment_verdict.get("withdraws"))
    withdrawn_a_licence = bool(withdrawn and establishes)
    establishes = establishes and not withdrawn
    source = (STATED_DISCRETENESS if (step == 1 and establishes) else
              NECESSARY_DISCRETENESS if (step == 1 and kind_licenses) else
              ASSUMED_DISCRETENESS)
    rec: dict[str, Any] = {
        "per_subject_step": step, "quote": quote,
        "quote_located": loc["located"],
        "quote_not_located_because": loc["why"],
        "quote_states_discreteness": says_step,
        # THE WORDS THE PAPER DENIED IT WITH, where it did. `None` means the
        # quote was silent about granularity, not that it was read as neutral.
        "discreteness_denied_by": denied,
        "quote_names_another_variable": about["names_another_variable"],
        "quote_about_this_variable": about["about_this_variable"],
        "anchor_score": about["anchor_score"],
        "quote_sentence": loc["sentence"], "clause": clause,
        # WHICH ASSERTION INSIDE THAT CLAUSE CARRIED THE DISCRETENESS WORD, and
        # -- where none of them was this variable's -- whose claim it was
        # instead. A reader of a licence has to be able to go and look at the
        # words that bought it, and a reader of this refusal at the words that
        # took it away.
        "discreteness_assertion": licensed,
        "discreteness_belongs_to": blocked_by,
        # WHETHER THE ASSERTION BOUNDARY WAS RESOLVED AT ALL, which is the one
        # thing a reader of this record could not previously tell. A leaked
        # licence read `discreteness_source: stated`,
        # `establishes_step_of_one: True`, `discreteness_belongs_to: None`,
        # `reasons: []` and a `discreteness_assertion` holding the whole
        # sentence -- which DOES name the variable -- so an auditor reading the
        # premise saw a licence that looked correct. These two fields separate
        # the three outcomes by name:
        #
        #   `subject`     the assertion carrying the whole-unit word has a
        #                 subject of its own and it is this variable
        #   `inherited`   it is a bare predicate CONTIGUOUS with a clause about
        #                 this variable, and takes that clause's attribution
        #   `unresolved`  the whole-unit word sits in a constituent introduced
        #                 by a comma that this reader could not attribute, and
        #                 `discreteness_unresolved_constituent` holds its words
        #
        # `None` on both means the located sentence offered nothing to resolve.
        # Under a model verdict this still describes what the REGEX path found,
        # so `unresolved` beside `establishes_step_of_one: True` says plainly
        # that a model granted what the conservative parse would not.
        "discreteness_boundary": (attributed_by if attributed_by
                                  else "unresolved" if unattributed else None),
        "discreteness_unresolved_constituent": (_one_line_quote(unattributed, 120)
                                                if unattributed else None),
        "quote_reports_an_average": averaged,
        # WHICH PASSAGE SAID SO -- the account's own granularity sentence, some
        # other sentence of the served text, or the passage a model granted the
        # step on. The reader of a refusal has to be able to go and look at it.
        "reports_an_average_in": averaged_where,
        "paper_reports_an_average": (averaged_elsewhere + averaged_in_table) or None,
        "derivation_reports_an_average": derived_average,
        # WHAT THE WHOLE-NUMBER CLAIM WAS MADE PER, where that is not one
        # subject's own reported value, and which passage said so. `None` means
        # the claim was made about the reported value -- an absence of this
        # refusal, not an absence of the question.
        "discreteness_claim_is_per": per_observation,
        "discreteness_claim_is_per_in": per_observation_where,
        "kind": kind, "kind_makes_it_necessary": kind_licenses,
        "kind_contradicted_by": contradicted,
        # WHAT A MODEL WAS ASKED AND WHAT IT ANSWERED, on every variable a
        # wave-7c pass covered, whichever way it answered. BOTH QUESTIONS ARE
        # RECORDED: the one that may grant the step, and the one that may only
        # withdraw it.
        "model_reading": verdict,
        "model_reading_averaging": averaging_verdict,
        # THE THIRD QUESTION, AND THE ONLY ONE ASKED ABOUT A LICENCE THAT WAS
        # ALREADY GRANTED. `discreteness_licence_withdrawn_by_model` is True only
        # where the free path DID license the step and this verdict took it away,
        # so a reader can tell a removal from a licence that never existed, and
        # `model_reading_attachment` carries the verdict that did it.
        #
        # A `false` VERDICT DOES NOT REACH THIS FIELD, and that is
        # `premise_reading.index`'s rule for EVERY refusal premise rather than
        # anything this premise chose: a refusal is filed only on `true`, so a
        # model that was asked and said "these words are about the target" leaves
        # `None` here. It is not lost -- `premise_reading.json` records every
        # verdict either way and `n_verdicts` counts it -- but a reader of the
        # variable's record alone cannot tell "asked and answered no" from "never
        # asked". Recorded rather than fixed: making `index` file negatives would
        # change what `averaging`, `estimator`, `correction` and `varying_n` write
        # too, which is a change to shared machinery and not this round's.
        "model_reading_attachment": attachment_verdict,
        "discreteness_licence_withdrawn_by_model": withdrawn_a_licence,
        "discreteness_source": source,
        "establishes_step_of_one": source != ASSUMED_DISCRETENESS,
        "reasons": [],
    }
    if step is None:
        rec["reasons"].append({"reason": "step_missing", "detail": ""})
        return rec
    if step != 1:
        rec["reasons"].append({"reason": "step_not_one",
                               "detail": f"per-subject step {step}"})
        return rec
    if source == ASSUMED_DISCRETENESS and (averaged is not None
                                           or derived_average is not None):
        if averaged is not None:
            where = {"granularity_quote": "the sentence offered for this variable",
                     "served_text": "a sentence of the paper about this variable",
                     "table_furniture": "the caption or a footnote of the table it "
                                        "is printed in",
                     "granting_quote": "the passage the step was granted on",
                     "model_reading": "a passage a model read for this variable"}.get(
                         str(averaged_where), "the paper")
            rec["reasons"].append({
                "reason": "discreteness_quote_reports_an_average",
                "detail": (f"{where} says {averaged!r}: the "
                           "whole-unit claim is about the observations that were averaged, "
                           "and their average does not move in whole units")})
        if derived_average is not None:
            rec["reasons"].append({
                "reason": "derivation_reports_an_average",
                "detail": (f"the account's own derivation of this variable is "
                           f"{derived_average!r}, and the average of k whole observations "
                           "moves in steps of 1/k")})
        return rec
    # AND THE CLAIM THAT WAS MADE PER SOMETHING ELSE IS NAMED BESIDE THEM, in the
    # same family and for the same reason: the paper stated a granularity, this
    # reader read the words it stated it about, and they are not the words the
    # table prints one of per row. `discreteness_assumed` would say "no located
    # quote shows the PAPER establishes it", which is false about a paper whose
    # quote does establish it -- for a visit, a rater or a quarter point.
    if source == ASSUMED_DISCRETENESS and per_observation is not None:
        # ONE CHANNEL, NAMED RATHER THAN LEFT IMPLICIT. The sibling refusals map
        # several (`reports_an_average_in` has five); this question is asked of
        # the located granularity sentence and of nothing else, because the paid
        # path is deliberately untouched, so `discreteness_claim_is_per_in`
        # carries one value. The field stays -- a reader of a refusal must be
        # able to go and look at the words that took the licence away -- and a
        # second channel added later belongs in this map.
        where = {"granularity_quote": "the sentence offered for this variable"}.get(
            str(per_observation_where), "the paper")
        rec["reasons"].append({
            "reason": "discreteness_claim_is_per_observation",
            "detail": (f"the step is 1 and {where} states whole-number granularity "
                       f"PER {per_observation!r}, not per subject: what the paper "
                       f"established is that each such observation is a whole number, "
                       f"and the value printed for one subject aggregates or rescales "
                       f"several of them")})
        return rec
    # THE WITHDRAWAL IS NAMED, AND IT IS REPORTED AHEAD OF THE TWO REFUSALS
    # BELOW BECAUSE IT IS THE OPERATIVE CAUSE. Both of those say the free path
    # found nothing; here it found something and a model took it away, and a
    # docket reading `discreteness_assumed` ("no located quote shows the PAPER
    # establishes it") would be a false sentence about a paper whose quote this
    # reader DID accept. Emitted only where a licence actually fell -- a `true`
    # on a variable the free path never licensed changes nothing and says so by
    # being absent from here.
    if source == ASSUMED_DISCRETENESS and withdrawn_a_licence:
        rec["reasons"].append({
            "reason": "discreteness_licence_withdrawn_by_a_model",
            # THE DETAIL MAY NOT NAME A CAUSE THE VERDICT DID NOT GIVE. Until
            # round 28 this sentence said the words described "another
            # quantity", which was the only thing the question could then mean;
            # the widened question withdraws for a denial and for a
            # per-observation claim as well, and a docket asserting attachment
            # on either of those would be a false sentence about the paper. The
            # model's own reason is the only account of WHY, so it carries it
            # and this line no longer competes with it.
            "detail": (f"the step is 1 and the paper's own words appeared to establish "
                       f"it, but a model read "
                       f"{_one_line_quote(attachment_verdict.get('quote'), 120)!r} as not "
                       f"showing that the figure reported for one subject is a whole "
                       f"number: "
                       f"{str(attachment_verdict.get('reason'))[:120]!r} "
                       f"({attachment_verdict.get('candidate_id')}, "
                       f"{attachment_verdict.get('model')})")})
        return rec
    # AND THE PAPER'S OWN DENIAL IS NAMED AHEAD OF EVERY OTHER REFUSAL, because
    # it is the only one that is EVIDENCE rather than an absence of evidence.
    # `discreteness_assumed` says "no located quote shows the PAPER establishes
    # it", and that is a false sentence about a paper whose quote says in so many
    # words that the measure is NOT recorded in whole units. A docket that cannot
    # tell a silence from a disclosure has lost the more informative half.
    if source == ASSUMED_DISCRETENESS and denied is not None:
        rec["reasons"].append({
            "reason": "discreteness_claim_is_denied",
            "detail": (f"the step is 1 and the quote offered for it DENIES whole-number "
                       f"granularity ({denied!r} governs the whole-unit words), so the "
                       f"sentence that was read as establishing a step of 1 establishes "
                       f"the opposite")})
        return rec
    # THE REFUSAL IS NAMED, NOT FOLDED INTO THE GENERIC ONE. An auditable
    # refusal is worth more than a silent one, and `discreteness_assumed` --
    # "no located quote shows the PAPER establishes it" -- would be the wrong
    # sentence here: a quote DID state discreteness, in words this reader could
    # not attribute to anybody. Emitted only where nothing else licensed the
    # step, so a variable whose licence came from a different clause, from its
    # kind or from a model still reports whatever that was.
    if source == ASSUMED_DISCRETENESS and unattributed is not None:
        rec["reasons"].append({
            "reason": "discreteness_assertion_boundary_unresolved",
            "detail": (f"the step is 1 and its quote states discreteness inside "
                       f"{_one_line_quote(unattributed, 120)!r}, a constituent this "
                       f"reader cannot attribute: the whole-unit words may belong to "
                       f"this variable or to a quantity beside it, and an unresolved "
                       f"boundary may not supply the premise")})
        return rec
    if source == ASSUMED_DISCRETENESS:
        why = (
            (f"a model read every sentence this paper offers about it and none "
             f"establishes a whole-number step in the unit printed: "
             f"{str(verdict.get('reason'))[:120]!r} ({verdict.get('candidate_id')}, "
             f"{verdict.get('model')})")
            if verdict is not None else
            "no quote for it locates in the served text" if not loc["located"] else
            f"its quote describes `{about['names_another_variable']}`, not this variable"
            if about["names_another_variable"] else
            "its quote locates but states nothing about granularity" if not says_step
            else f"its quote states discreteness of `{blocked_by}`, not of this "
                 f"variable" if blocked_by else
            f"its quote states discreteness but not of this variable "
            f"(anchor {about['anchor_score']})")
        rec["reasons"].append({"reason": "discreteness_assumed",
                               "detail": f"the step is 1 and {why}"})
    return rec


# --------------------------------------------------------------------------
# The stamp
# --------------------------------------------------------------------------


def is_stamped(account: dict) -> bool:
    """Does EVERY readable value in this account carry a premise?

    ALL, NOT ANY. A partially stamped account is the shape that fails open: one
    reader stamps what it touched, the next finds a stamp on the first row and
    concludes the account is done. A value the stamp SKIPS (`well_formed`
    returns a reason) is not evidence either way and does not count against it.
    """
    for v in account.get("values") or []:
        if well_formed(v) is None and not isinstance(v.get("premise"), dict):
            return False
    return True


def _captions(account: dict) -> dict[str, str]:
    """The table's own caption, by table id. `prepass.reports_model_output` reads
    the column band first and the caption second, and on ajcp.70049 the caption
    is what says three of the six tables are regressions.

    THE DOCUMENT IS READ WITH THE SAME TOLERANCE THE VALUES GET. `document`
    arriving as a LIST of tables -- one plausible shape of a hand-built or
    model-authored account -- raised `AttributeError: 'list' object has no
    attribute 'get'` here, which is called from `stamp`, which is outside
    `well_formed`, outside the per-candidate try/except and outside
    `_census_safely`: the paper got no `checks.json` and no docket at all. A
    document we cannot read is a paper with no captions, which costs checks and
    is not a crash.
    """
    out: dict[str, str] = {}
    doc = account.get("document")
    tables = doc.get("tables") if isinstance(doc, dict) else doc
    for t in (tables if isinstance(tables, list) else []):
        if isinstance(t, dict) and t.get("id") and t.get("caption"):
            out[str(t["id"])] = str(t["caption"])
    for t in (account.get("table_readings") or []):
        if isinstance(t, dict) and t.get("table_id") and t.get("caption"):
            out.setdefault(str(t["table_id"]), str(t["caption"]))
    return out


#: The types a value may carry in a field this package uses as part of a
#: DICTIONARY KEY. Everything here is hashable; a list and a dict are not.
_SCALAR_TYPES = (str, int, float, bool)


def is_scalar(x: Any) -> bool:
    """Can `x` be part of an index key?"""
    return x is None or isinstance(x, _SCALAR_TYPES)


def well_formed(value: Any) -> str | None:
    """Why this value cannot be read at all, or None.

    A MALFORMED VALUE IS ONE SKIP, NEVER THE RUN. A `location` that arrived as
    the string `"table_cell"` and a value with no `id` each took the whole
    sidecar with them, because the index and the census are built outside the
    per-candidate try/except.

    THE MEMBERS ARE CHECKED, NOT ONLY THE CONTAINERS, and round 3 is why. This
    function tested that `location` and `coordinate` ARE objects and never what
    was inside them -- while `_cell_index`, `stamp` and the bridge's `_Index`
    build DICTIONARY KEYS out of `location.table_id`, `location.row`,
    `location.col`, `coordinate.study_id`, `coordinate.group_id`,
    `coordinate.phase_id` and `variable_id`. Seven readings of a real shape (a
    list, a dict) raised `TypeError: unhashable type` out of the index, BEFORE
    the per-candidate try/except and before the `value_malformed` docket, so no
    `checks.json` and no `checks.md` were written at all. Every field used as a
    key must therefore be a scalar, and the test is on the TYPE rather than on a
    list of field names, so a field added later cannot reopen the hole.
    """
    if not isinstance(value, dict):
        return "the value is not an object"
    if not isinstance(value.get("id"), str) or not value["id"].strip():
        return "the value carries no id"
    for field in ("location", "coordinate"):
        got = value.get(field)
        if got is not None and not isinstance(got, dict):
            return f"`{field}` is not an object"
        if isinstance(got, dict):
            for key, member in got.items():
                if not is_scalar(member):
                    return (f"`{field}.{key}` is a {type(member).__name__}, and this "
                            "field is used as part of an index key")
    if not is_scalar(value.get("variable_id")):
        return (f"`variable_id` is a {type(value.get('variable_id')).__name__}, and it "
                "is used as part of an index key")
    if value.get("statistic") is not None and not isinstance(value.get("statistic"), str):
        return "`statistic` is not a string"
    return None


def well_formed_variable(var: Any) -> str | None:
    """Why this VARIABLE cannot be read at all, or None.

    THE SAME RULE THE VALUES GET, APPLIED TO THE OTHER TABLE. Round 3 fixed this
    class for values -- "seven readings of a real shape (a list, a dict) raised
    `TypeError: unhashable type` out of the index, BEFORE the per-candidate
    try/except ... so no `checks.json` and no `checks.md` were written at all" --
    and the VARIABLE table was never given the same treatment, although
    `premises.stamp` (`by_var_id`) and `checks._Index.variables` build dictionary
    keys out of `variable.id` in exactly the same way and are called from exactly
    the same place. A variable we cannot key is a value bound to no declared
    variable, which is a refusal (`no_variable`) and not a crash.

    ROUND 12: THE `id` WAS THE ONLY FIELD THIS ASKED ABOUT, AND IT IS NOT THE
    ONLY FIELD READ OUTSIDE THE ISOLATION. `printed_as` is ITERATED by
    `_name_forms` -- reached from `anchor_score`, `about_this_variable` and
    `bounds_verification`, all of them called from `premises.stamp`, which is the
    FIRST statement of `checks.evaluate` -- and a scalar there raised
    `TypeError: 'int' object is not iterable` and took the whole account's
    `checks.json`, `checks.md` and docket with it. The schema declares an array
    of strings; anything else is a variable we cannot read, refused BY NAME in
    `variables_malformed` rather than guessed at. The container is what is tested
    here, because it is the container that is iterated; `printed_labels` is the
    tolerance for every caller that did not come through this gate.
    """
    if not isinstance(var, dict):
        return "the variable is not an object"
    vid = var.get("id")
    if not is_scalar(vid):
        return (f"`id` is a {type(vid).__name__}, and it is used as part of an "
                "index key")
    if not isinstance(vid, str) or not vid.strip():
        return "the variable carries no id"
    printed = var.get("printed_as")
    if printed is not None and not isinstance(printed, list):
        return (f"`printed_as` is a {type(printed).__name__}, and it is read as a "
                "list of printed labels")
    return None


def field_dict(obj: Any, name: str) -> dict:
    """One of an account row's sub-objects, or an empty one.

    ONE READER, BECAUSE TWO OF THEM DISAGREED. `premises.stamp` was hardened
    against a `bounds` that arrived as a list and a `granularity` that arrived as
    a string (`dict(...) if isinstance(...) else {}`) and survives all four
    shapes; `premise_reading.candidates` read the same two fields with
    `var.get("bounds") or {}` and raised `AttributeError` on every one of them --
    so the paid pass died on an account the stamp reads fine. `or {}` is not the
    test it looks like: a non-empty list is truthy and comes straight back.
    """
    got = obj.get(name) if isinstance(obj, dict) else None
    return got if isinstance(got, dict) else {}


def printed_labels(var: Any) -> list:
    """A variable's `printed_as` labels, whatever shape the field arrived in.

    THE FIFTH READING OF THIS CLASS, AND THE FIRST THAT COERCES RATHER THAN
    REFUSING. `well_formed`, `field_dict`, `_captions` and
    `premise_reading._rows` each read one field a hand-built, half-written or
    model-authored account can carry in the wrong shape, and each REFUSES what it
    cannot read: lost coverage, never the run. `printed_as` is read by
    `_name_forms`, and so by `anchor_score`, `about_this_variable` and
    `bounds_verification` -- every one of them called from `premises.stamp`,
    which is the first statement of `checks.evaluate` and sits outside the
    per-candidate try/except. `list(var.get("printed_as") or [])` raised
    `TypeError: 'int' object is not iterable` there, so the paper got no
    `checks.json`, no `checks.md` and no docket at all.

    A BARE STRING IS WHY THIS COERCES INSTEAD OF ONLY GUARDING. `list("Age")`
    raises nothing whatever -- it yields `['A', 'g', 'e']`, one printed label per
    LETTER, which is silently wrong rather than loud, and a one-character label
    is a label that can join to a one-character row banner. A scalar in a field
    the schema declares as an array of strings is one label written without its
    wrapper, so it is read as exactly one label; anything else -- a dict, a set,
    a falsy scalar -- is not a list of labels in any reading, and is read as no
    labels at all.

    THE ACCOUNT BOUNDARY STILL REFUSES IT, AND THAT IS THE PRIMARY FIX.
    `well_formed_variable` rejects a non-list `printed_as` outright, so on the
    live path such a variable is named in `variables_malformed`, its values
    refuse by name, and nothing reaches here. This is the guard for every caller
    that did not come through `readable_variables`.
    """
    got = var.get("printed_as") if isinstance(var, dict) else None
    if isinstance(got, list):
        return list(got)
    return [got] if got and is_scalar(got) else []


def readable_variables(account: Any) -> list[dict]:
    """The variables of an account that can be read AS variables, in order."""
    raw = (account or {}).get("variables") if isinstance(account, dict) else None
    return [v for v in (raw if isinstance(raw, list) else [])
            if well_formed_variable(v) is None]


def variables_by_id(variables: list[dict]) -> dict[str, dict]:
    """`id -> variable`, with EVERY DUPLICATED ID LEFT OUT.

    TWO VARIABLES MAY NOT SHARE ONE ID, and the map was last-write-wins in two
    places at once (`stamp.by_var_id`, `checks._Index.variables`) while
    `duplicate_ids` was only ever asked about VALUES. A slug-from-name reading
    mints `var:daily_dose` for Study A's tablets/day (`count`, step 1) and Study
    B's mg/day (`continuous`), and Study B's honest 41.37 mg mean came back GRIM
    `impossible` with `data_type: count` and `discreteness_source: stated` --
    both premises borrowed from the other variable, which is the value-id defect
    one table over.

    DROPPED RATHER THAN RESOLVED, exactly as a duplicated value id is: choosing
    which of two variables an id means is the guess this layer exists to remove,
    and a value bound to a dropped id refuses by name (`duplicate_variable_id`).
    """
    dupes = duplicate_ids(variables)
    return {v["id"]: v for v in variables
            if isinstance(v.get("id"), str) and v["id"] not in dupes}


def _cell_index(values: list[dict]) -> dict:
    index: dict[Any, list[dict]] = {}
    for v in values:
        loc = v.get("location") or {}
        if loc.get("kind") == "table_cell":
            key = ("cell", loc.get("table_id"), loc.get("row"), loc.get("col"))
        else:
            c = v.get("coordinate") or {}
            key = ("coord", c.get("study_id"), c.get("group_id"), c.get("phase_id"),
                   v.get("variable_id"))
        index.setdefault(key, []).append(v)
    return index


def stamp(account: dict, text: str = "", *, inplace: bool = False) -> dict:
    """Write `premise` / `n_premise` / `verification` onto every value and
    variable, and return the account.

    `inplace=False` COPIES, and the default is not a performance choice. The
    bridge's contract is that it never writes back into the account it was given
    (`checks.py`: "the account is the paper's own description and a verdict is
    not part of it"), and `checks.evaluate` calls this on whatever it is handed.
    The copy is shallow apart from the rows this function writes to, so it costs
    one list of dicts and not a deep copy of the document.
    """
    if not inplace:
        account = dict(account)
        account["values"] = [dict(v) if isinstance(v, dict) else v
                             for v in (account.get("values") or [])]
        account["variables"] = [dict(v) if isinstance(v, dict) else v
                                for v in (account.get("variables") or [])]
        for v in account["variables"]:
            if isinstance(v, dict):
                for field in ("bounds", "granularity"):
                    if isinstance(v.get(field), dict):
                        v[field] = dict(v[field])
    hay = Haystack(text)
    variables = readable_variables(account)
    by_var_id = variables_by_id(variables)
    values = [v for v in (account.get("values") or []) if well_formed(v) is None]
    captions = _captions(account)
    # THE TABLE'S OWN FOOTNOTES, BY TABLE ID -- a channel `named_estimator` and
    # `analysis_n_varies` did not read until wave 7d (round 12's F3), computed
    # once here for the same reason `captions` is: two rows of one table must
    # not disagree about what the paper's own footnote says.
    furniture = table_footnotes(account)
    index = _cell_index(values)
    # THE PAPER'S THREE DOCUMENT-LEVEL FACTS, READ ONCE. Each is a property of
    # the paper rather than of a row, and computing one per value would let two
    # rows of the same table disagree about what the paper says.
    notes = table_notes(captions, text)
    weighting = weighting_statement(text)
    n_varies = varying_n_statement(text)
    estimator = estimator_statement(text)
    # THE MODEL'S READING OF THE FIVE TEXT PREMISES, WHEN THERE IS ONE (wave
    # 7c). Absent -- which is every paper the paid pass has not been run on --
    # `read` is empty and every judgement below is the vocabulary's, unchanged.
    # The consumer is loaded at its call site so the cycle stays unclosed, the
    # way `bind` loads `coverage`.
    read: dict[str, Any] = {}
    if account.get("premise_reading"):
        from . import premise_reading as _reading
        read = _reading.index(account.get("premise_reading"), hay, by_var_id)
    by_variable: dict[Any, list[dict]] = {}
    for v in values:
        by_variable.setdefault(v.get("variable_id"), []).append(v)
    for v in values:
        var = by_var_id.get(v.get("variable_id"))
        vid = str(v.get("id"))
        premise = value_premise(v, var, index, captions, notes=notes,
                                weighting=weighting, n_varies=n_varies,
                                estimator=estimator,
                                read_estimator=(read.get("estimator") or {}).get(vid),
                                read_correction=(read.get("correction") or {}).get(vid),
                                read_varying_n=(read.get("varying_n") or {}).get(vid),
                                furniture=furniture)
        v["premise"] = premise
        if str(v.get("statistic") or "") == "n":
            v["n_premise"] = n_premise(v, premise)
    for var in variables:
        mine = by_variable.get(var.get("id")) or []
        # THE SUB-DICTS ARE REPLACED, NEVER WRITTEN THROUGH, EVEN IN PLACE.
        # `bind.assemble` shallow-copies each pass-2 variable, so `var["bounds"]`
        # is the SAME OBJECT the structure's own `pass2` holds -- and writing a
        # `verification` into it changed `structure.content_sha256` between the
        # account block and the provenance stamp, so a run refused itself with
        # `StructureMismatch`. A stamp may not edit its own input.
        b = dict(field_dict(var, "bounds"))
        g = dict(field_dict(var, "granularity"))
        var["bounds"], var["granularity"] = b, g
        vid = str(var.get("id"))
        b["verification"] = bounds_verification(
            var, hay, variables, mine, (read.get("bound") or {}).get(vid))
        g["verification"] = granularity_verification(
            var, hay, variables, mine, (read.get("step") or {}).get(vid),
            (read.get("averaging") or {}).get(vid),
            table_passages(account, mine),
            (read.get("discreteness_attachment") or {}).get(vid),
            subjects=subject_terms(account))
    if read:
        # WHAT THE READING MOVED, ON THE ACCOUNT, so a reader of `account.json`
        # can see that a paid pass governed some of these premises without
        # walking every variable to find out.
        account["premise_reading_applied"] = {
            k: read.get(k) for k in ("n_verdicts", "n_applied", "n_quote_refused",
                                     "n_stale_question", "prompt_version", "model")}
    return account


def stamped(account: dict, text: str = "") -> dict:
    """The account with premises on it, stamping only if it has none.

    IDEMPOTENT ON PURPOSE. `bind.assemble` stamps, so an account read off disk
    arrives stamped and is not re-read; a hand-built or model-authored account
    (every adversarial fixture) is stamped here, so no reader can fail open by
    finding the field absent.
    """
    if is_stamped(account):
        return account
    return stamp(account, text)
