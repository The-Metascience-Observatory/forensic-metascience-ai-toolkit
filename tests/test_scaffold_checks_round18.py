"""ROUND 18 -- BOUNDED ADJUDICATION FOR THE VARYING-n REFUSAL PREMISE.

THE PREMISE. `checks._Index.group_n` binds the GROUP's n by position and then
asks whether the paper has said that the number of subjects behind THIS row is
not the group's. Where it has, no denominator survives and the check is refused
`per_row_n_not_captured`. Until now that question was answered by one closed
regex, `premises._N_VARIES`, read from the value's own caption, its table's
footnote, or a governing sentence of the served text.

THE DEFECT CLASS, WHICH IS ROUND 14's AND ROUND 17's ON A THIRD PREMISE: five
ordinary, honest ways of saying that a measure was completed by only some of the
group, none of which `_N_VARIES` matches (`test_every_evasion_really_does_evade
_the_vocabulary`, which is what makes these the same experiment). Item-level
missingness is the commonest honest reason a real paper fails GRIM, so the
sentences the vocabulary misses are exactly the papers it convicts.

THE POLARITY IS WHY THIS MAY BE MODEL-JUDGED AT ALL, and it is the opposite of
the alternative-base ceiling's. A `varying_n` verdict can only ever ADD a
refusal: `premise_reading.index` files one on `establishes: True` alone, and the
gate it reaches returns a refusal with no tool called and no `n` passed. D71's
hazard -- a model `false` REMOVING a candidate denominator so a check runs and
accuses -- is a licence-shaped polarity and is not this. That distinction is
argued in `adjudication_n`'s module docstring and RAILED here, in both
directions: the ceiling stays unnameable from the new module, and an n ROW's
eligibility stays unreachable from any reading.

THE ONE CHANNEL THAT COULD SUPPLY A DENOMINATOR, and the reason
`test_an_n_rows_eligibility_is_not_reachable_from_a_reading` carries its
measurement in its docstring: `group_n` DROPS n rows failing
`n_premise.usable` and only then reads `len({integers}) != 1` as `ambiguous_n`,
so making one of two disagreeing n rows unusable RESOLVES the ambiguity and lets
a check run at a denominator that was refused a moment before. Measured on two n
rows printing 47 and 44: `n_run 0` and no severity becomes `n_run 1` and
`impossible`. Nothing in this round touches `usable`, and that test is what keeps
it that way.

THE MODEL VERDICTS ARE REPLAYED FROM A RECORDED RUN, not called for at test time
-- round 15's rule. `RECORDED_TRUE` is what a real sonnet batch answered about
the exact candidate set `adjudication_n.candidates` builds from these fixtures.

THE MEASUREMENT, STATED SO IT CAN BE ARGUED WITH. Seven arms -- one paper per
evasion, one carrying the three honest controls, and one whose group n IS 44 --
gave 17 deduplicated candidates through the real window path. ONE batched call,
sonnet, 2026-09-12, $0.206806, no problems. **17 of 17 agree with a key written
before the call** (`scratchpad/prereg.json`): all ten defect windows `true`, and
seven `false` -- the table caption, both whole-group controls, the window whose
NEIGHBOUR states another variable's missingness ("the 41-of-47 figure is for a
different variable"), and all three of the number-agrees arm.

THE NUMBER-AGREES ARM IS THE RESULT WORTH KEEPING, because it measures the
design decision rather than the model. Its passage is BYTE-IDENTICAL to the
`returned a usable card` defect; only the TARGET differs, 44 against 47. Asked at
47 the model answered `true`; asked at 44 it answered `false`, reason "passage's
44 matches target's 44". Naming the denominator in the target is what separates
the defect from the honest case, and without it the two are the same question.

ONE FIXTURE IS NOT A CORPUS. This measures whether the wiring carries a verdict
to where it has to reach and whether the model answers these seventeen passages
correctly. It says NOTHING about a real paper's false-refusal rate, and the
`n_run` measurement that would -- both reference accounts, before and after, with
a pre-registered stop condition -- has not been run: neither reference account
survives on this machine.
"""

from __future__ import annotations

import copy
import statistics as st

import pytest

from metascience_agent.scaffold import (adjudication, adjudication_n, checks,
                                        premise_reading as PR, premises)

BAD = {"suspicious", "highly_suspicious", "impossible"}


# --------------------------------------------------------------------------
# The Ashgate keying bureau shift-log survey -- round 18's own fixture paper
# (shares nothing with rounds 1-17)
# --------------------------------------------------------------------------

#: Copy clarity, scored 0-5 in WHOLE points, returned by 44 of the 47 operators
#: on the roll. The paper is HONEST BY CONSTRUCTION: 121 whole points over 44
#: cards is exactly 2.75, and 2.75 is reachable from NO integer total over 47
#: under either rounding convention -- so binding the enrolled 47 convicts a
#: paper whose arithmetic is exact.
CLARITY = [0] * 4 + [1] * 6 + [2] * 9 + [3] * 10 + [4] * 8 + [5] * 7
ANALYSED, ENROLLED = len(CLARITY), 47
MEAN = f"{st.fmean(CLARITY):.2f}"
SD = f"{st.stdev(CLARITY):.2f}"

assert (ANALYSED, sum(CLARITY), MEAN) == (44, 121, "2.75")
assert not any(round(k / ENROLLED, 2) == float(MEAN) for k in range(ENROLLED * 5 + 1))


# --------------------------------------------------------------------------
# D1 -- FIVE EVASIONS OF THE CLOSED VOCABULARY
# --------------------------------------------------------------------------

#: The sentence that GRANTS the whole-number step, and the roll the group's n is
#: read from. Both ordinary, honest and true.
GRANT = ("Copy clarity was scored in whole points on a 0 to 5 card for every "
         "operator.")
ROLL = "Shift logs were collected from 47 operators at the Ashgate keying bureau."

#: The sentence that WITHDRAWS the group's n, five ways, none of which
#: `premises._N_VARIES` carries. Two name a count against the roll, one spells
#: its count out, one uses the `n =` notation and one says only that complete
#: data were available for some.
EVASIONS = {
    "44 of the 47":
        "Copy clarity was scored for 44 of the 47 operators.",
    "based on 44 logs":
        "The reported copy clarity figure is based on 44 logs.",
    "returned a usable card":
        "Forty-four operators returned a usable copy clarity card.",
    "n = 44":
        "For copy clarity n = 44.",
    "complete data":
        "Complete copy clarity data were available for 44 operators.",
}

#: HONEST CONTROLS. The first says the whole group contributed; the second is
#: about the variable and says nothing about how many; the third is another
#: variable's missingness, which is the contamination case -- it must not
#: withdraw copy clarity's denominator.
WHOLE_GROUP = "All 47 operators returned a usable copy clarity card."
NO_COUNT = "Copy clarity was scored from the printed proof under standard lighting."
OTHER_VARIABLE = "Keying speed was recorded for 41 of the 47 operators."

#: THE NUMBER-AGREES CONTROL, which needs its own account: the same sentence as
#: `returned a usable card`, on a paper whose group n IS 44. The target then
#: names 44, the passage names 44, and the honest answer is `false`.
AGREES = "Forty-four operators returned a usable copy clarity card."


# --------------------------------------------------------------------------
# The account
# --------------------------------------------------------------------------


def var(vid, name, kind, *, lower=None, upper=None, quote=None):
    return {"id": vid, "name": name, "label": name, "printed_as": [],
            "kind": kind, "role": None, "units": None,
            "units_source": "not_stated", "derivation": None, "derived_from": [],
            "bounds": {"source": "stated", "lower": lower, "upper": upper,
                       "quote": quote},
            "granularity": {"per_subject_step": 1, "quote": quote}}


def cell(vid, statistic, printed, *, variable_id=None, col_label="Mean (SD)",
         row=1, col=1, table="table:1"):
    lit = premises.read_plain(printed) or {}
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": table, "row": row,
                         "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:ashgate", "group_id": "grp:operators",
                           "phase_id": None}}


def account(*, group_n=ENROLLED, footnotes=()):
    """Copy clarity's mean and SD, a decoy variable beside it, and one n row."""
    return {"paper": {"doi": "10.0000/ashgate",
                      "title": "The Ashgate keying bureau shift-log survey"},
            "studies": [{"id": "study:ashgate", "design": "prospective_cohort",
                         "groups": [{"id": "grp:operators", "label": "All operators",
                                     "n": group_n, "n_source": "text"}]}],
            "variables": [var("var:clarity", "Copy clarity", "ordinal",
                              lower=0, upper=5, quote=GRANT),
                          var("var:speed", "Keying speed", "ordinal",
                              lower=0, upper=5,
                              quote="Keying speed was scored in whole points on a "
                                    "0 to 5 card.")],
            "values": [cell("val:mean", "mean", MEAN, variable_id="var:clarity"),
                       cell("val:sd", "sd", SD, variable_id="var:clarity", col=2),
                       cell("val:n", "n", str(group_n), variable_id="var:clarity",
                            col=3, col_label="n")],
            "document": {"tables": [
                {"id": "table:1",
                 "caption": "Table 1. Copy clarity, Ashgate keying bureau shift logs.",
                 "footnotes": [str(f) for f in footnotes]}]}}


def paper(*sentences):
    """The served text: the roll, the granting sentence, then whatever the case
    adds."""
    return " ".join(("## Methods", ROLL, GRANT) + sentences)


def accusations(got):
    return sorted({(r["check_id"], r["severity"]) for r in got["checks"]
                   if r["severity"] in BAD})


def cands_for(acc, text, variable_id="var:clarity"):
    return [c for c in adjudication_n.candidates(acc, text)
            if c["variable_id"] == variable_id]


def reading(*verdicts, candidates=()):
    cs = list(candidates)
    return {"schema": PR.SCHEMA_VERSION, "prompt_version": PR.PROMPT_VERSION,
            "model": "sonnet", "n_candidates": len(cs), "n_asked": len(cs),
            "n_dropped": 0, "candidates": cs, "verdicts": list(verdicts),
            "problems": [], "cost_usd": 0.0, "n_calls": 1}


def verdicts_for(cs, establishes, reason="recorded"):
    return [{"candidate_id": c["id"], "premise": c["premise"],
             "establishes": bool(establishes(c)), "reason": reason,
             "model": "sonnet", "prompt_version": PR.PROMPT_VERSION}
            for c in cs]


#: WHAT THE PAID BATCH ANSWERED `true` ON, exhaustively: every window carrying
#: one of the five defect passages, asked against a target of 47. Every other
#: candidate came back `false` -- the table caption, the whole-group control, the
#: no-count control, the window carrying ANOTHER variable's missingness as a
#: neighbour, and the number-agrees arm. Written as the passages rather than as
#: candidate ids because a candidate id is an artefact of the ordering and the
#: passage is the thing that was judged.
RECORDED_TRUE = tuple(EVASIONS.values())


def recorded(c):
    """The 2026-09-12 sonnet batch's answer about this candidate.

    THE TARGET IS PART OF THE ADDRESS, NOT ONLY THE PASSAGE, which is this
    round's own measurement rather than an implementation detail: the same
    sentence asked against a target of 47 came back `true` and against a target
    of 44 came back `false`, reason "passage's 44 matches target's 44".
    """
    if f"over the {ANALYSED} subjects" in c["target"]:
        return False
    return any(s in c["quote"] for s in RECORDED_TRUE)


def read_back(acc, text, cs, establishes=recorded, reason="recorded"):
    return checks.evaluate(
        dict(acc, premise_reading=reading(*verdicts_for(cs, establishes, reason),
                                          candidates=cs)), text)


# --------------------------------------------------------------------------
# D1 -- THE VOCABULARY CANNOT SEE ANY OF THEM
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_every_evasion_really_does_evade_the_vocabulary(label):
    """THE ASSERTION THAT MAKES THESE THE SAME EXPERIMENT. A regenerated
    sentence the regex happens to catch would be testing nothing, and the
    failure would look exactly like a pass."""
    sentence = EVASIONS[label]
    assert not premises._N_VARIES.search(sentence)
    assert premises.varying_n_statement(paper(sentence)) is None


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_the_old_path_convicts_and_cannot_even_ask(label):
    """BEFORE. The bridge binds the enrolled 47, the checks convict a paper
    whose arithmetic is exact, and NO existing path can offer the model the
    withdrawing sentence: `premise_reading.candidates` has no generator for this
    premise at all."""
    text = paper(EVASIONS[label])
    acc = account()
    assert accusations(checks.evaluate(acc, text)), "the fixture must convict"
    assert "varying_n" not in {c["premise"] for c in PR.candidates(acc, text)}


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_stage_one_surfaces_the_withdrawing_sentence(label):
    """AFTER, STAGE 1. Relevance is free and deterministic, and this is the half
    the defect class is actually about: the sentence reaches a model at all."""
    text = paper(EVASIONS[label])
    got = cands_for(account(), text)
    assert any(EVASIONS[label] in c["quote"] for c in got), [c["quote"] for c in got]


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_a_true_verdict_removes_every_accusation(label):
    """AFTER, STAGE 2 REPLAYED. The recorded reply said `true` on the
    withdrawing passage; the wiring has to carry that to `group_n`, which is
    where the denominator is bound."""
    text = paper(EVASIONS[label])
    acc = account()
    cs = cands_for(acc, text)
    assert any(recorded(c) for c in cs)
    assert accusations(read_back(acc, text, cs)) == []


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_the_refusal_names_the_papers_own_words(label):
    """THE DOCKET GETS THE PAPER'S SENTENCE, not the model's prose. What is
    stamped is the CANDIDATE'S QUOTE -- a passage this pipeline supplied -- and
    `_n_detail` prints its first 120 characters verbatim, so a reader is sent to
    a span of the paper rather than to an assertion about nothing."""
    text = paper(EVASIONS[label])
    acc = account()
    cs = cands_for(acc, text)
    got = read_back(acc, text, cs)
    rows = [r for r in got["refused"] if r["reason"] == "per_row_n_not_captured"]
    assert rows
    mv = next(v for v in premises.stamp(
        dict(acc, premise_reading=reading(*verdicts_for(cs, recorded), candidates=cs)),
        text)["values"] if v["id"] == "val:mean")
    varies = mv["premise"]["analysis_n_varies"]
    assert varies in {c["quote"] for c in cs}
    assert EVASIONS[label] in varies
    assert any(str(varies)[:120] in row["detail"] for r in rows for row in r["reasons"])


# --------------------------------------------------------------------------
# THE HONEST CONTROLS
# --------------------------------------------------------------------------


def test_the_honest_paper_is_not_touched_by_a_false_verdict():
    """A `false` lifts nothing and adds nothing: the run is what it was."""
    text = paper(WHOLE_GROUP, NO_COUNT)
    acc = account()
    cs = cands_for(acc, text)
    assert cs, "the honest paper still offers candidates -- that is the point"
    assert read_back(acc, text, cs, lambda c: False) == checks.evaluate(acc, text)


def test_the_contaminating_neighbour_is_asked_about_the_right_variable():
    """RISK: a window whose NEIGHBOUR describes ANOTHER variable's missingness
    can persuade a model to withdraw a denominator this variable is entitled to.
    Stage 1 cannot prevent that -- a window is a window -- so what is pinned is
    that the question names the variable and the denominator it would move."""
    text = paper(OTHER_VARIABLE, NO_COUNT)
    got = cands_for(account(), text)
    assert got
    for c in got:
        assert "Copy clarity" in c["target"]
        assert f"over the {ENROLLED} subjects" in c["target"]


def test_a_true_on_one_variable_does_not_reach_another():
    """THE FAN-OUT IS THE CANDIDATE'S OWN `value_ids`, which are the values of
    one variable at one denominator. A verdict about copy clarity may not
    withdraw keying speed's denominator."""
    text = paper(EVASIONS["44 of the 47"])
    acc = account()
    cs = adjudication_n.candidates(acc, text)
    assert cs and all(c["variable_id"] == "var:clarity" for c in cs)
    assert all(set(c["value_ids"]) <= {"val:mean"} for c in cs), \
        [c["value_ids"] for c in cs]


# --------------------------------------------------------------------------
# THE RAILS -- the tests that keep the polarity where it is
# --------------------------------------------------------------------------


def test_the_alternative_base_ceiling_is_not_reachable_from_this_module():
    """D71, KEPT LITERAL FOR THE PREMISE IT IS ACTUALLY ABOUT. The ceiling's
    dangerous direction is a model `false` removing a candidate denominator so a
    check runs and accuses; nothing here may name it.

    THE MODULE DOCSTRING IS EXCLUDED AND THE CODE IS NOT, which is round 17's
    rail rather than round 15's: the docstring has to be able to LIST the
    forbidden names in order to say they are forbidden, and everything after it
    is the part that could reach one."""
    src = adjudication_n.__file__ or ""
    assert src.endswith("adjudication_n.py")
    with open(src, encoding="utf-8") as fh:
        body = fh.read()
    after_module_docstring = body.split('"""', 2)[-1]
    for forbidden in ("paper_max_n", "printed_subject_counts", "_SUBJECT_COUNT",
                      "other_bases_that_fit", "alternative_base"):
        assert forbidden not in after_module_docstring, forbidden


def test_the_round_15_rail_on_the_averaging_module_still_holds_unedited():
    """THE CONFLATION IS NOT RESOLVED BY DELETING SOMEBODY ELSE'S LINE. Rounds
    15 and 17 forbid `_N_VARIES` and `varying_n` from `adjudication.py`, in a
    test named for D71. This round's argument is that the two premises have
    opposite polarities and were bundled under one phrase -- so the work went
    into a module of its own and that rail is asserted here too, unchanged."""
    with open(adjudication.__file__, encoding="utf-8") as fh:
        body = fh.read()
    for forbidden in ("paper_max_n", "_SUBJECT_COUNT", "alternative_base",
                      "_N_VARIES", "varying_n"):
        assert forbidden not in body.split('"""', 2)[-1], forbidden


def two_n_rows():
    """A coordinate whose two n rows disagree: 47 on the roll, 44 in the table.

    `group_n` calls that `ambiguous_n` and refuses, which is correct -- choosing
    between two printed denominators is the guess that layer exists to remove.
    The mean is GRIM-impossible at 47 and reachable at 44, so whichever row is
    dropped decides whether an honest paper is accused.
    """
    acc = account()
    acc["values"].append(cell("val:n2", "n", str(ANALYSED), variable_id="var:clarity",
                              col=4, col_label="n"))
    return acc


def test_the_supply_channel_exists_and_this_fixture_reaches_it():
    """THE POSITIVE CONTROL FOR THE RAIL BELOW, so that it cannot pass by
    testing nothing. Making ONE of two disagreeing n rows unusable RESOLVES the
    ambiguity and turns a refusal into a false accusation on an honest paper:

        both n rows usable        n_run 0   severities {}
        one n row made unusable   n_run 1   severities {'impossible': 1}
    """
    text, acc = paper(), two_n_rows()
    before = checks.evaluate(acc, text)
    assert (before["n_run"], accusations(before)) == (0, [])
    assert "ambiguous_n" in before["refused_by_reason"]
    dropped = copy.deepcopy(acc)
    for v in dropped["values"]:
        if v["id"] == "val:n2":
            v["id_check"] = "contradicted"
    after = checks.evaluate(dropped, text)
    assert after["n_run"] == 1
    assert {s for _, s in accusations(after)} == {"impossible"}


def test_an_n_rows_eligibility_is_not_reachable_from_a_reading():
    """THE ONE CHANNEL BY WHICH A VERDICT COULD SUPPLY A DENOMINATOR, SHUT.

    `group_n` DROPS rows failing `n_premise.usable` and only then reads
    `len({integers}) != 1` as `ambiguous_n` -- so anything that can make one n
    row unusable can resolve the ambiguity and let a check RUN at a denominator
    that was refused a moment before. The measured consequence is pinned next
    door in `test_the_supply_channel_exists_and_this_fixture_reaches_it`.

    `n_premise` is computed from provenance, binding, disputed and positivity and
    reads `analysis_n_varies` NOWHERE.

    THE READING HERE IS FORGED RATHER THAN BUILT, for two reasons. This net
    builds NO candidate on this account at all -- the dry pre-pass finds no check
    that would run, which is the floor doing its job -- so a test derived from it
    would assert nothing. And the dangerous future edit is precisely someone
    routing this premise at the n ROW instead of at the value being checked, so
    the candidate has to NAME the n rows for the rail to be about anything. A
    `premise_reading` block is also a file anyone can edit, which makes this the
    adversarial shape and not only the hypothetical one.
    """
    text, acc = paper(EVASIONS["44 of the 47"]), two_n_rows()
    every = [v["id"] for v in acc["values"]]
    assert adjudication_n.candidates(acc, text) == []
    cs = [{"premise": adjudication_n.PREMISE, "variable_id": "var:clarity",
           "value_ids": list(every), "source": "served_text",
           "quote": EVASIONS["44 of the 47"], "target": "forged", "context": "",
           "relevance_version": adjudication_n.RELEVANCE_VERSION, "id": "cand:1",
           "question": PR.QUESTIONS["varying_n"], "asked_bounds": None,
           "quote_located": True, "quote_not_located_because": "", "askable": True}]
    plain = premises.stamp(acc, text)
    moved = premises.stamp(
        dict(acc, premise_reading=reading(*verdicts_for(cs, lambda c: True),
                                          candidates=cs)), text)
    rows = {v["id"]: v for v in plain["values"] if v.get("statistic") == "n"}
    assert len(rows) == 2
    for vid, before in rows.items():
        after = next(v for v in moved["values"] if v["id"] == vid)
        # THE VERDICT DID REACH THIS ROW -- it is in `value_ids` -- so the stamp
        # records it. What it may not do is move the row's ELIGIBILITY.
        assert after["premise"]["model_reading"]["varying_n"]["establishes"] is True
        assert after["n_premise"] == before["n_premise"], vid
        assert after["n_premise"]["usable"] is True
    # AND THE CONSEQUENCE, not just the field: the coordinate is still ambiguous
    # and nothing ran, which is where a forged reading has to leave it.
    got = read_back(acc, text, cs, lambda c: True)
    assert got["n_run"] == 0 and accusations(got) == []


def test_forced_true_may_only_lower_the_run_and_never_change_a_denominator():
    """MUTATION CONTROL, ONE DIRECTION. Every verdict forced `true`: the number
    of checks that run may only FALL, no check may gain a worse severity, and
    every check that still runs must carry the `n` it carried with no reading at
    all."""
    for text in [paper(*EVASIONS.values()), paper(WHOLE_GROUP, NO_COUNT),
                 paper(OTHER_VARIABLE), paper()]:
        acc = account()
        base = checks.evaluate(acc, text)
        cs = adjudication_n.candidates(acc, text)
        got = read_back(acc, text, cs, lambda c: True)
        assert got["n_run"] <= base["n_run"], text
        assert not (set(got["by_severity"]) & BAD) - (set(base["by_severity"]) & BAD)
        ns = {r["check_id"]: r["args"].get("n") for r in base["checks"]}
        for r in got["checks"]:
            assert r["args"].get("n") == ns[r["check_id"]], r["check_id"]


def test_forced_false_is_byte_identical_to_no_reading_at_all():
    """MUTATION CONTROL, THE OTHER DIRECTION, and it is the half that proves the
    polarity. A refusal premise's `false` may NEVER remove a refusal the
    vocabulary made, so the whole `checks.evaluate` output must be what it was."""
    for text in [paper(*EVASIONS.values()), paper(WHOLE_GROUP),
                 paper("Sample sizes vary across measures owing to missing responses.")]:
        acc = account()
        cs = adjudication_n.candidates(acc, text)
        assert read_back(acc, text, cs, lambda c: False) == checks.evaluate(acc, text)


def test_a_forged_number_in_the_models_reason_reaches_nothing():
    """NO NUMBER LEAVES THIS PATH. The refusal is stamped from the CANDIDATE'S
    QUOTE -- a span of the served text this pipeline supplied -- so a reason
    claiming a denominator cannot become one, cannot be printed as one, and
    cannot reach a docket."""
    text = paper(EVASIONS["44 of the 47"])
    acc = account()
    cs = cands_for(acc, text)
    forged = "the real n is 44 and the mean is 9.99"
    moved = premises.stamp(
        dict(acc, premise_reading=reading(
            *verdicts_for(cs, lambda c: True, forged), candidates=cs)), text)
    supplied = {c["quote"] for c in cs}
    for v in moved["values"]:
        varies = str((v.get("premise") or {}).get("analysis_n_varies") or "")
        assert forged not in varies
        if varies:
            # A PASSAGE THIS PIPELINE SUPPLIED, AND NOTHING ELSE. Not necessarily
            # a span of the SERVED TEXT: a table's own caption and footnotes are
            # admitted as candidates with no aboutness test, and on a JATS paper
            # the footnote is not in the body at all.
            assert varies in supplied
    got = read_back(acc, text, cs, lambda c: True, forged)
    for r in got["checks"] + got["refused"]:
        assert forged not in repr(r)


def test_the_licence_path_is_untouched():
    """The bound and step candidates `premise_reading` builds are the same rows
    whether or not this module is called, and no licence premise can be asked
    for through it."""
    text = paper(*EVASIONS.values())
    acc = account()
    before = [c for c in PR.candidates(acc, text) if c["premise"] in PR.LICENCE_PREMISES]
    adjudication_n.candidates(acc, text)
    assert [c for c in PR.candidates(acc, text)
            if c["premise"] in PR.LICENCE_PREMISES] == before
    assert adjudication_n.PREMISE in PR.REFUSAL_PREMISES
    assert adjudication_n.PREMISE not in PR.LICENCE_PREMISES


def test_the_averaging_candidate_set_is_byte_identical():
    """ROUND 15's 32 RECORDED VERDICTS JOIN TO CANDIDATES BY QUOTE, so a
    refactor that shifts one window boundary by a sentence would make those
    replays address different passages while every test still passes.
    `relevant_passages` gained a `rank` parameter this round; the default path
    has to be the same rows, as a list and not as a count."""
    text = paper(*EVASIONS.values(), WHOLE_GROUP)
    acc = account()
    hay = premises.Haystack(text)
    variables = premises.readable_variables(acc)
    for v in variables:
        assert (adjudication.relevant_passages(v, hay, variables)
                == adjudication.relevant_passages(
                    v, hay, variables, rank=lambda q: adjudication._rank(q, "averaging")))
    assert adjudication.candidates(acc, text) == adjudication.candidates_for(
        acc, text, ("averaging",))


def test_no_number_leaves_this_path():
    """A candidate carries a passage and a target; a verdict carries a boolean
    and a reason. There is no numeric field in either, so there is no channel for
    one -- which matters more here than for the two shipped nets, because a
    varying-n passage routinely PRINTS a count."""
    for c in adjudication_n.candidates(account(), paper(*EVASIONS.values())):
        assert set(c) == {"premise", "variable_id", "value_ids", "source", "quote",
                          "target", "context", "relevance_version", "id", "question",
                          "asked_bounds", "quote_located", "quote_not_located_because",
                          "askable"}
        assert c["asked_bounds"] is None
        assert c["askable"] is True
        assert c["question"] == PR.QUESTIONS["varying_n"]
        assert c["relevance_version"] == adjudication_n.RELEVANCE_VERSION


# --------------------------------------------------------------------------
# THE FLOOR -- the vocabulary decides first, and the dry pre-pass is the cap
# --------------------------------------------------------------------------


def test_a_paper_the_vocabulary_already_handles_costs_nothing():
    """THE VOCABULARY IS THE FLOOR. A document-level `_N_VARIES` statement
    withdraws every denominator in the paper already, so there is nothing a
    verdict could move and not one candidate is built."""
    text = paper("Sample sizes vary from 44 to 47 across measures owing to "
                 "missing responses.")
    acc = account()
    assert premises.varying_n_statement(text)
    assert accusations(checks.evaluate(acc, text)) == []
    assert adjudication_n.candidates(acc, text) == []


def test_a_footnote_the_vocabulary_reads_costs_nothing_either():
    """The same floor one channel over: a table's own footnote refuses every
    value in it, so the dry pre-pass finds no surviving check and builds no
    candidate."""
    text = paper()
    acc = account(footnotes=["Sample sizes vary across measures owing to item "
                             "non-response."])
    assert accusations(checks.evaluate(acc, text)) == []
    assert adjudication_n.candidates(acc, text) == []


def test_a_candidate_is_built_only_where_a_check_would_otherwise_run():
    """THE DRY PRE-PASS IS THE COST CONTROL AND ALSO A CORRECTNESS ARGUMENT: a
    refusal candidate is worth a prompt line only where a verdict would change
    something. With the mean's literal unreadable, every check refuses for a
    reason of its own and no varying-n question is asked."""
    text = paper(*EVASIONS.values())
    acc = account()
    assert adjudication_n.candidates(acc, text)
    broken = copy.deepcopy(acc)
    for v in broken["values"]:
        if v["id"] in ("val:mean", "val:sd"):
            v["printed"] = "approximately " + str(v["printed"])
            v["numeric"] = None
    assert checks.evaluate(broken, text)["n_run"] == 0
    assert adjudication_n.candidates(broken, text) == []


def test_the_target_names_the_denominator_the_check_would_use():
    """`eligible` yields the `n` the check would actually divide by, and the
    target names it. Without the number the honest case and the defect case are
    the same sentence."""
    text = paper(EVASIONS["returned a usable card"])
    for n in (ENROLLED, ANALYSED):
        got = cands_for(account(group_n=n), text)
        assert got
        assert all(f"over the {n} subjects" in c["target"] for c in got)


def test_the_number_agrees_control_is_the_same_passage_at_a_different_target():
    """THE CONTROL THE PAID BATCH NEEDS, AND THE ONE RESULT THAT MEASURES THE
    DESIGN RATHER THAN THE MODEL. `Forty-four operators returned a usable copy
    clarity card` is a DEFECT where the group's n is 47 and HONEST where it is
    44; the passage is byte-identical and nothing but the TARGET separates them.

    REPLAYED: asked at 47 the recorded batch said `true` and the accusation goes;
    asked at 44 it said `false` ("passage's 44 matches target's 44") and the run
    is exactly what it was -- which at 44 is a clean paper with nothing to
    remove."""
    text = paper(AGREES)
    defect, honest = account(group_n=ENROLLED), account(group_n=ANALYSED)
    dc, hc = cands_for(defect, text), cands_for(honest, text)
    assert {c["quote"] for c in dc} == {c["quote"] for c in hc}
    assert {c["target"] for c in dc} != {c["target"] for c in hc}
    assert any(recorded(c) for c in dc) and not any(recorded(c) for c in hc)
    assert accusations(checks.evaluate(defect, text))
    assert accusations(read_back(defect, text, dc)) == []
    assert read_back(honest, text, hc) == checks.evaluate(honest, text)
    assert accusations(checks.evaluate(honest, text)) == []


def test_the_cli_offers_its_own_flag_and_refuses_two_nets_at_once(capsys):
    """ONE FLAG, ONE NET, AND THEY ALL WRITE ONE FILE. `--read-premises`,
    `--adjudicate`, `--adjudicate-varying-n` and (round 24)
    `--adjudicate-attachment` all write `premise_reading.json` by different
    recall nets, so asking for two is refused rather than merged -- a reader of
    that file has to be able to say which net produced a verdict. The flag is its
    own rather than a `--adjudicate` choice because this net lives in a module of
    its own, which is what keeps D71's grep rail on `adjudication.py` passing
    unedited.

    WHAT IS PINNED IS THE REFUSAL, NOT ITS WORDING. Round 24 added a fourth net
    and had to edit the sentence; the assertion is now that the error names every
    flag that reaches the branch, so adding a fifth without naming it fails
    here."""
    import inspect

    from metascience_agent.scaffold import __main__ as M

    with pytest.raises(SystemExit) as exc:
        M.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--adjudicate-varying-n" in out
    src = inspect.getsource(M.main)
    assert "_adjudication_n.adjudicate" in src
    refusal = src.split('ap.error("')[1].split('")')[0]
    for flag in ("--read-premises", "--adjudicate", "--adjudicate-varying-n",
                 "--adjudicate-attachment"):
        assert flag in refusal, flag


def test_the_ranking_orders_and_never_filters():
    """`MAX_REFUSAL_CANDIDATES` is a cap, and for a refusal a cap ordered by
    POSITION is a filter. Two of the five evasions carry no count any reader can
    see, so they rank last -- and must still be asked."""
    text = paper(*EVASIONS.values())
    quotes = [c["quote"] for c in cands_for(account(), text)]
    for sentence in EVASIONS.values():
        assert any(sentence in q for q in quotes), sentence
    assert adjudication_n._rank(EVASIONS["n = 44"]) == 1
    assert adjudication_n._rank(NO_COUNT) == 2
