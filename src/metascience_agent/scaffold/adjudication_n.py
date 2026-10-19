"""BOUNDED ADJUDICATION FOR THE VARYING-n REFUSAL PREMISE -- round 18's prototype.

WHAT THE PREMISE IS. `checks._Index.group_n` resolves a denominator by KEY --
the n rows at exactly this value's (study, group, phase) -- and then asks whether
the PAPER has said that this row's analysed n is not the group's. Where it has,
no denominator survives and the check is refused `per_row_n_not_captured`. That
question is currently answered by ONE closed regex, `premises._N_VARIES`, read
from the value's own caption, its table's footnote, or a governing sentence of
the served text.

WHY A SECOND PREMISE GETS THE SAME TREATMENT AS `averaging` AND `estimator`.
Item-level missingness is the commonest honest reason a real paper fails GRIM,
and `_N_VARIES` recognises exactly one way of announcing it -- a sentence
containing an inflection of "sample size" beside "vary/differ/range" beside
"measures/outcomes/items". MEASURED on five ordinary, honest ways of saying the
same thing, none of which is contrived:

    "Copy clarity was scored for 44 of the 47 operators"     _N_VARIES: no
    "based on 44 logs"                                       _N_VARIES: no
    "Forty-four operators returned a usable clarity card"    _N_VARIES: no
    "For copy clarity n = 44"                                _N_VARIES: no
    "Complete clarity data were available for 44 operators"  _N_VARIES: no

Five for five. That is the same D1 shape the averaging premise had in round 14
and the estimator premise had in round 17: a closed word list standing in for a
judgement, and the list is the defect.

AND THE MODEL ANSWERS THEM. ONE batched call through this module's own candidate
path -- seven arms, 17 deduplicated windows, sonnet, 2026-09-12, $0.206806 --
scored **17 of 17 against a key written before the call**: all ten defect windows
`true`, and `false` on the table caption, on both whole-group controls, on the
window whose NEIGHBOUR states another variable's missingness ("the 41-of-47
figure is for a different variable"), and on all three windows of the
number-agrees arm. Pinned in `tests/test_scaffold_checks_round18.py`, which
states what one fixture can and cannot show.

THE NUMBER-AGREES ARM MEASURES THE DESIGN RATHER THAN THE MODEL, and it is why
`_target` names the denominator. Its passage is BYTE-IDENTICAL to one of the five
defects; only the target differs, 44 against 47. Asked at 47 the answer was
`true`; asked at 44, `false` -- "passage's 44 matches target's 44". Without the
number in the target the honest case and the defect are the same question.

    AND THAT ARM WAS NOT ENOUGH, WHICH ROUND 20 MEASURED AND `premise_reading`
    RECORDS IN FULL. Naming the denominator in the target fixes the case where
    the passage PRINTS the analysed count and nothing else; round 18's question
    then offered a SECOND anchor ("fewer subjects than that whole group") that a
    paper's own enrolment fills. On an account that has correctly bound the
    analysed n, seven honest ways of stating item-level missingness against the
    roll -- `44 of the 47`, `missing for 3 of the 47`, `all but three of the 47`
    -- all answered `true` and withdrew the only check those papers had. The
    question is reworded; `_target` is unchanged, because the target was never
    the half that was wrong.

    THE NUMBER-AGREES ARM ALSO EXPLAINS WHY THE ROUND-18 BATCH COULD NOT SEE IT:
    it put the enrolled-target and analysed-target readings of one passage in
    front of the model together, and the contrast did the disambiguation the
    question should have done. Asked alone, as a real run asks, the shipped
    string failed seven for seven. A refusal premise's question is measured on
    ONE paper's candidates from here on.

    THE FREE PATH IS NOT QUITE EMPTY, AND THE ONE PLACE IT REACHES IS RECORDED
    HERE SO NOBODY RE-MEASURES IT. `premises.analysed_counts` already reads
    sentence 3 correctly (`n = 44`, `stages: []`) and `group_n` never asks,
    because its join at `checks.py:1046` is scoped to a value whose n row carries
    no phase AND requires a STAGE intersection. Widening that join is a change to
    the FREE path -- it would move every run, with no model in the loop -- so it
    is not done here: this module is opt-in and paid, and a production default
    change is a different decision with a different owner. It is written up as a
    recommendation instead.

THE TWO STAGES ARE `adjudication`'s, AND STAGE 1 IS LITERALLY ITS CODE.
`relevant_passages` -- enumerate every sentence, keep the ones this variable is
the subject of by attribution or by anaphora, widen each to a window inside its
own section, admit the table's own caption and footnotes with no aboutness test
-- asks nothing about averaging and nothing about denominators. It is imported
rather than copied; only the RANKING differs, and `relevant_passages` takes it as
a parameter for that reason.

# THE SAFETY ARGUMENT, WHICH IS THE WHOLE OF WHY THIS MAY EXIST

THE POLARITY. `varying_n` is in `premise_reading.REFUSAL_PREMISES`, so
`premise_reading.index` files a verdict only on `establishes: True` (the branch
is `elif rec["establishes"]:`). A model `true` ADDS a refusal; a model `false`
lifts nothing and leaves the vocabulary exactly where it stood. The worst a wrong
verdict can do is remove a check from an honest paper.

AND THE GATE IT REACHES IS TERMINAL. `checks.py:1024` reads
`_premise_of(v)["analysis_n_varies"]` and returns `(None, "per_row_n_not_captured",
rec)`. Every caller -- `checks.py:1518/1591/1642/1780` -- does `ref.add(n_reason,
...)` and then `if ref: return ref`. No tool is called, no `n` is passed, and
there is no retry at another coordinate; the alternative-base machinery
(`checks.py:1544`) is gated on `if not ref`, so this refusal short-circuits it
rather than redirecting it.

THERE IS EXACTLY ONE CHANNEL BY WHICH A VERDICT ABOUT n COULD SUPPLY A
DENOMINATOR RATHER THAN WITHDRAW ONE, AND IT IS MEASURED. `group_n` resolves the
denominator from the KEPT n rows (`checks.py:918-961`): rows failing
`n_premise.usable` are DROPPED, and only then is `len({integers}) != 1` read as
`ambiguous_n`. So dropping one of two disagreeing n rows RESOLVES the ambiguity
and makes a check run at a denominator that was refused a moment before. Built
and run -- two n rows printing 47 and 44 at one coordinate, a group declaring 47,
a mean of `0.05` that is GRIM-impossible at 47 and possible at 44:

    both n rows usable          n_run 0   severities {}
    one n row made unusable     n_run 1   severities {'impossible': 1}

A refusal became a false accusation purely by making one n row unusable. That is
the line this module may not cross, and the four rules below are what keep it
shut STRUCTURALLY rather than by promise:

  1. THE VERDICT ATTACHES TO `value_premise`'s `analysis_n_varies` AND TO NOTHING
     ELSE. `premises.n_premise` computes `usable` from `provenance`, `binding`,
     `disputed` and positivity -- it does not read `analysis_n_varies`, and no
     model verdict of any premise reaches any of those four. Pinned by
     `test_an_n_rows_eligibility_is_not_reachable_from_a_reading`.
  2. THE REFUSAL IS STAMPED FROM THE CANDIDATE'S QUOTE -- a verbatim span of the
     served text THIS MODULE supplied -- and never from the model's `reason`
     prose. The reason is recorded in `premise["model_reading"]["varying_n"]`
     for a reader and is read by nothing that computes.
  3. NO NUMBER LEAVES THIS PATH. A candidate carries a passage and a target; a
     verdict carries a boolean and a reason. A varying-n passage routinely names
     a count ("44 of the 47 operators"), and reading one would SUPPLY a
     denominator -- the one thing `group_n`'s own comment (CLAUDE.md 8d,
     invariant 1) forbids. There is no numeric field in either shape.
  4. THE ALTERNATIVE-BASE CEILING IS NOT TOUCHED AND IS NOT NAMEABLE HERE.
     `paper_max_n`, `printed_subject_counts`, `_SUBJECT_COUNT`,
     `other_bases_that_fit` and `alternative_base` appear nowhere below and a
     test greps this file for them. (`premises.population_sizes` IS used, for
     RANKING only: it reads `_POPULATION`, which is not the ceiling's reader, and
     its result orders a list rather than entering one.)

# THE RECORDED DECISION THIS READS AGAINST, STATED RATHER THAN WORKED AROUND

`tests/test_scaffold_checks_round15.py:428` and its round-17 copy forbid
`_N_VARIES` and `varying_n` from `adjudication.py`, in a test named for D71 --
the ALTERNATIVE-BASE CEILING -- and D77's D5 in the decision log likewise bundles
"the n-premise" with that ceiling as things "the project's own D71 rule says must
never be model-loosened".

D71's stated hazard is a model `false` REMOVING a candidate base so that a check
runs and accuses: a LICENCE-shaped polarity, on a premise whose verdict grants
something. `_N_VARIES` is the opposite -- a model `true` ADDS a refusal -- and the
two were bundled under one phrase. THE BUNDLE IS NOT EDITED. Both rails stay
exactly as written and keep passing, because this work is in a module of its own;
this file carries its own rail for the ceiling's five names, and round 18 asserts
the unedited round-15 rail as well. The conflation is written up for a person to
rule on rather than resolved by deleting a line from somebody else's test, and
until it is ruled on this prototype stays behind its own flag and is applied to
nothing.

# AND IT IS NOT THE DEFAULT

`premise_reading.candidates` is unchanged, `adjudication`'s two nets are
unchanged, and `checks` behaves on every existing paper exactly as it did. This
path runs only under `--adjudicate-varying-n`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import adjudication as _adj
from . import checks as _checks
from . import premise_reading as _reading
from . import premises as _premises

#: The relevance instrument this premise's measurements are a claim about. Bump
#: with a new measurement, never with a rewording -- `adjudication`'s own rule,
#: and for the same reason: a candidate set built by different bytes is a
#: different experiment.
RELEVANCE_VERSION = "varying-n-relevance-window/2026-09-12"

#: The premise name, in one place, because it is the join between this module,
#: `premise_reading.QUESTIONS` and `premises.value_premise`.
PREMISE = "varying_n"

#: `n = 44` AND `n: 44`, FOR RANKING ONLY. A passage carrying the notation a
#: paper uses for a sample size is more likely to be the one that withdraws the
#: group's n, so it sorts ahead of a passage that carries none. It is NOT read
#: for its number: see rule 3 above.
_N_NOTATION = re.compile(r"\b[nN]\s*[=:]\s*\d")


def _rank(quote: str) -> int:
    """0 for a passage the strict vocabulary would already read as establishing
    this premise, 1 for one carrying a count of subjects or the `n =` notation,
    2 for everything else.

    RANK IS ORDER AND NEVER A FILTER, which `premise_reading.MAX_REFUSAL_CANDIDATES`
    states and which matters more here than for either shipped net. Of the five
    measured evasions, two carry no count `population_sizes` can read at all, and
    one of those two -- "The reported copy clarity figure is based on 44 logs" --
    ranks 2, the same as a sentence saying nothing about counts. A premise the
    model is never shown is a premise it cannot withdraw, so rank 2 is a
    position and not an exclusion.
    """
    if _premises._N_VARIES.search(quote):
        return 0
    if (_premises.analysed_counts(quote) or _premises.population_sizes(quote)
            or _N_NOTATION.search(quote)):
        return 1
    return 2


def already_refused(text: str) -> bool:
    """Has the free path ALREADY withdrawn every n in this paper?

    ASKED FIRST, AND IT IS NOT AN OPTIMISATION. `premises.varying_n_statement`
    is a DOCUMENT-LEVEL statement: `stamp` passes it to every `value_premise`, so
    a paper that carries one has `analysis_n_varies` set on every value and
    `group_n` refuses everywhere. A refusal premise can only be ADDED, so there
    is nothing any verdict could move, and asking would buy nothing and cost a
    paid line. Per-value refusals the vocabulary made from a caption or a
    footnote are cut by `eligible` below, for the same reason and by
    construction.
    """
    return _premises.varying_n_statement(text) is not None


def eligible(account: dict, text: str = "") -> dict[tuple[Any, int], list[str]]:
    """`{(variable_id, denominator): [primary value ids]}` for every check that
    would RUN on this account as it stands.

    THE DRY PRE-PASS IS THE COST CONTROL AND IT IS ALSO A CORRECTNESS ARGUMENT.
    Unlike `averaging` (which applies only where `per_subject_step == 1`), this
    premise applies to every value at a coordinate carrying an n, which is a much
    larger space. A refusal candidate is worth a prompt line only if a verdict
    would change something, and the test for that is not a guess: run
    `checks.translate` on every candidate and keep the ones that come back with
    arguments rather than a `Refusal`. Nothing is called, nothing is paid for,
    and a value the vocabulary has ALREADY refused -- through the caption, the
    footnote or any other gate -- is absent by construction, which is what makes
    the vocabulary the floor here as it is in `adjudication`.

    AND IT YIELDS THE DENOMINATOR THE CHECK WOULD ACTUALLY USE, which is what
    the target names. Keyed by `(variable, n)` rather than by variable alone: a
    variable reported at two coordinates with two different group sizes is two
    different questions, and one target string cannot honestly name both.
    """
    acc = _premises.stamped(account, text)
    cands, idx = _checks.candidates(acc, text)
    out: dict[tuple[Any, int], list[str]] = {}
    for cand in cands:
        if cand.variable_id is None:
            # NAMED RATHER THAN LEFT AS AN ABSENCE: a value with no variable id
            # cannot be reached by a per-variable candidate, because relevance is
            # measured against a variable. `adjudication`'s averaging net has the
            # same gap. It is a coverage limit, not a safety one.
            continue
        try:
            got = _checks.translate(cand, idx)
        except Exception:  # noqa: BLE001 -- `evaluate` wraps each candidate too
            continue
        if not isinstance(got, tuple):
            continue
        n = ((got[1].get("n") or {}).get("n"))
        if not isinstance(n, int):
            continue
        row = out.setdefault((cand.variable_id, n), [])
        if cand.primary_value_id not in row:
            row.append(cand.primary_value_id)
    return out


def _target(var: dict, n: int) -> str:
    """The variable, and the denominator a `true` would withdraw.

    THE QUESTION HAS TO NAME THE THING IT WITHDRAWS, which is the move
    `premise_reading._bounds_clause` made for the bound premise and which was
    measured there as an improvement. Without the number, "Forty-four operators
    returned a usable clarity card" cannot be told apart from the honest case
    where the group's n IS 44; with it, the model is judging a comparison it can
    actually make. It SUPPLIES nothing: the number named is the account's own
    denominator, already bound at this coordinate, and the verdict can only
    remove it.
    """
    return (_reading._variable_target(var)
            + f", as this paper reports it over the {n} subjects the account "
              "binds to this quantity")


def candidates(account: dict, text: str = "") -> list[dict]:
    """STAGE 1: one row per passage plausibly about how many subjects contributed
    to a quantity whose check would otherwise run.

    THE SHAPE IS `premise_reading`'s, so `build_prompt`, `read` and `index` read
    a row written here with no change to any of them and the artifact on disk is
    the same `premise_reading.json` every other run writes.
    """
    if already_refused(text):
        return []
    hay = _premises.Haystack(text)
    variables = _premises.readable_variables(account)
    by_var_id = _premises.variables_by_id(variables)
    by_id = {str(v.get("id")): v for v in (account.get("values") or [])
             if _premises.well_formed(v) is None}
    captions = _premises._captions(account)
    out: list[dict] = []
    for (vid, n), ids in sorted(eligible(account, text).items(),
                                key=lambda kv: (str(kv[0][0]), kv[0][1])):
        var = by_var_id.get(str(vid))
        if var is None:
            continue
        mine = [by_id[i] for i in ids if i in by_id]
        ctx = _reading._printed_context(mine, captions)
        target = _target(var, n)
        passages = _premises.table_passages(account, mine)
        kept = 0
        for _, quote, source in _adj.relevant_passages(var, hay, variables,
                                                       passages, rank=_rank):
            if kept >= _reading.MAX_REFUSAL_CANDIDATES:
                break
            kept += 1
            out.append({"premise": PREMISE, "variable_id": vid,
                        "value_ids": list(ids), "source": source,
                        "quote": _reading._clip(quote), "target": target,
                        "context": ctx, "relevance_version": RELEVANCE_VERSION})
    return _adj._finish(out, hay)


def adjudicate(account: dict, text: str, out_dir: str | Path, *,
               model: str = _reading.DEFAULT_MODEL, timeout_s: int = 900,
               budget: int | None = _reading.MAX_CANDIDATES_PER_PAPER) -> dict:
    """STAGE 2. Ask the model this premise's question of every passage stage 1
    found relevant, and return the `premise_reading` record.

    `budget` bounds the paper's bill in CANDIDATES, enforced once for every net
    in `premise_reading.read`; this net spends `MAX_REFUSAL_CANDIDATES` per
    `(variable, n)` pair, so it grows with the paper the same way the others do.

    PAID. One batched call per `premise_reading.MAX_PER_CALL` candidates, reusing
    a reply already bought for the identical prompt -- `premise_reading.read`
    does all of it, through its own `only=` door. Nothing about the call, the
    prompt template, the schema or the verdict-addressing differs from the pass
    E1 measured; only the candidate set and the question do.

    ATTACH IT BY SETTING `account["premise_reading"]` to the returned record:
    `premises.stamp` reads that key and `premise_reading.index` files a
    `varying_n` verdict by VALUE id, which is where `value_premise` looks.
    """
    # THE MEMBERSHIP IS CHECKED RATHER THAN ASSERTED IN PROSE, exactly as
    # `adjudication.candidates_for` checks its own: a module that can compose a
    # question for a premise is where a licence could be handed to a model by
    # accident, and this one may only ever add a refusal.
    if PREMISE not in _reading.REFUSAL_PREMISES:
        raise ValueError(f"{PREMISE!r} is not a refusal premise; this module may only "
                         "widen what a model is shown about a premise whose verdict "
                         "can remove a check and never add an accusation")
    return _reading.read(account, text, out_dir, model=model, timeout_s=timeout_s,
                         budget=budget, only=candidates(account, text))
