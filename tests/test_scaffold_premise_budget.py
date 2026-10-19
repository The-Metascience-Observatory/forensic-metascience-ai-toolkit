"""The per-paper candidate budget: what it costs, what it cuts, and what it says
it did not ask.

WHY THIS FILE EXISTS SEPARATELY, AND IT IS THE WHOLE POINT OF IT. Before the
budget, nothing in this package bounded a paper's bill. Every cap was PER SCOPE
-- `MAX_REFUSAL_CANDIDATES` bounds one premise of one variable,
`MAX_PER_CALL` bounds one request -- and the number of scopes is set by the
paper, so the product had no ceiling. The existing suite cannot see that, in
either direction: its candidate sets are a handful of hand-built rows, so a
budget of two thousand is invisible to it and so was its absence. A green run of
`test_scaffold_premise_reading.py` is therefore NOT evidence about anything
below, which is exactly why these fixtures are here rather than there.

THE FIXTURE PAPER IS HONEST AND IT IS ITS OWN. "The Kestrel Lane bakery survey"
-- twenty-four bakeries whose opening hours, staff and loaf prices were recorded
-- shares nothing with the Marlow allotment survey or with the six adversarial
papers. Every printed number is the exact summary of the real integer data in
this file, so any verdict worse than `consistent` is a false accusation as a
matter of arithmetic, whichever way a model answers and whichever candidates the
budget happens to cut. That matters more here than usual: the thing under test
CUTS QUESTIONS, and a cut must never be able to buy an accusation.

THE PROSE IS DOING WORK, NOT DECORATION. The budget is measured against the
candidate set the REAL nets build from this text, not against a list of fake
rows, because the defect being fixed is that the real nets multiply scopes
without bound. A test that hand-wrote forty candidates would be measuring the
arithmetic of a slice and would pass whatever the nets do.

THE MODEL BOUNDARY IS MOCKED, as everywhere else in this suite: nothing here
costs anything. What is measured is the wiring -- how many questions are put, how
many are not, and whether the record can tell those two apart.
"""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from metascience_agent.scaffold import (adjudication as A, adjudication_attach as AA,
                                        adjudication_n as AN, checks,
                                        premise_reading as PR, premises, render)
from metascience_agent.scaffold import __main__ as MAIN

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Kestrel Lane bakery survey's real per-bakery data
# --------------------------------------------------------------------------

#: Hours each bakery opens on a Saturday, recorded in whole hours.
HOURS = [6, 8, 5, 9, 7, 6, 10, 8, 7, 5, 9, 6, 8, 7, 6, 11, 8, 5, 7, 9, 6, 8, 7, 10]

#: Counter staff on duty, whole people.
STAFF = [2, 3, 1, 4, 2, 2, 5, 3, 2, 1, 4, 2, 3, 2, 2, 5, 3, 1, 2, 4, 2, 3, 2, 4]

#: Loaves sold before noon, whole loaves.
LOAVES = [48, 72, 31, 96, 57, 44, 118, 80, 63, 29, 101, 46, 77, 59, 41, 132,
          84, 27, 55, 99, 43, 76, 61, 112]

N = len(HOURS)
HOURS_MEAN = f"{st.fmean(HOURS):.2f}"          # 7.42
HOURS_SD = f"{st.stdev(HOURS):.2f}"            # 1.67
STAFF_MEAN = f"{st.fmean(STAFF):.2f}"          # 2.67
LOAVES_MEAN = f"{st.fmean(LOAVES):.2f}"        # 68.79

#: Bakeries opening at or before 06:00, as a count and as a percentage of N.
EARLY = sum(1 for h in HOURS if h <= 6)        # 8
EARLY_PCT = f"{EARLY / N * 100:.1f}"           # 33.3

#: THE PAPER'S OTHER VARIABLES, AND THEY ARE THE POINT OF THE FIXTURE. A paper
#: does not grow a bigger candidate set by having longer sentences; it grows one
#: by REPORTING MORE VARIABLES, because the nets spend a per-scope cap once per
#: variable. So these are real further variables of the same survey, each with
#: its own whole-loaf counts, its own printed mean and its own sentences naming
#: it -- which is what makes the growth measured below the real growth law and
#: not an artefact of padding.
#:
#: The counts are constructed rather than typed out, and the construction is
#: stated so it can be checked: whole loaves, derived from each bakery's own
#: hours and staff. `test_the_fixture_paper_is_honest` asserts every printed
#: mean is the exact mean of the integers beneath it.
BREADS = ["rye", "spelt", "oat", "barley", "wholemeal",
          "sourdough", "cottage", "malthouse", "seeded", "milk"]
BREAD_COUNTS = {name: [(h * (i + 2) + s * 3) % 37 for h, s in zip(HOURS, STAFF)]
                for i, name in enumerate(BREADS)}
BREAD_MEAN = {name: f"{st.fmean(c):.2f}" for name, c in BREAD_COUNTS.items()}
BREAD_SD = {name: f"{st.stdev(c):.2f}" for name, c in BREAD_COUNTS.items()}


def test_the_fixture_paper_is_honest():
    assert N == 24 and sum(HOURS) == 178 and sum(STAFF) == 64
    assert sum(LOAVES) == 1651 and EARLY == 8
    assert (HOURS_MEAN, HOURS_SD, STAFF_MEAN) == ("7.42", "1.67", "2.67")
    assert (LOAVES_MEAN, EARLY_PCT) == ("68.79", "33.3")
    # Every printed mean is attainable from whole counts over 24 bakeries, so
    # GRIM on any of them must clear and no cut of this paper's candidate set
    # can turn an honest number into a flagged one.
    for total, printed in ((178, HOURS_MEAN), (64, STAFF_MEAN), (1651, LOAVES_MEAN)):
        assert round(total / N, 2) == float(printed)
    assert round(EARLY / N * 100, 1) == float(EARLY_PCT)
    assert len(BREADS) == 10
    for name, counts in BREAD_COUNTS.items():
        assert len(counts) == N and all(isinstance(c, int) and c >= 0 for c in counts)
        assert round(sum(counts) / N, 2) == float(BREAD_MEAN[name])
    # Ten distinct variables, so ten distinct scopes rather than one repeated.
    assert len({tuple(c) for c in BREAD_COUNTS.values()}) == 10


# --------------------------------------------------------------------------
# The paper
# --------------------------------------------------------------------------

SENTENCES = [
    f"Twenty-four bakeries on and around Kestrel Lane took part in the survey "
    f"(n = {N}).",
    "Saturday opening hours were recorded in whole hours from the shutter log.",
    "Counter staff on duty were counted as whole people at the nine o'clock "
    "changeover.",
    "Loaves sold before noon were counted individually at the till.",
    f"The mean Saturday opening was {HOURS_MEAN} hours (SD {HOURS_SD}).",
    f"Bakeries kept a mean of {STAFF_MEAN} counter staff on the floor.",
    f"A mean of {LOAVES_MEAN} loaves were sold before noon.",
    f"{EARLY_PCT}% of bakeries raised their shutters at or before six o'clock.",
    "All figures reported in this paper are unweighted summaries of the "
    "twenty-four returns.",
    "Table 1 reports the means and percentages described above.",
    "The percentages presented here are shares of the twenty-four bakeries and "
    "of nothing else.",
    "The rates given for early opening were computed over the whole sample.",
    # THE STATED RANGES. Without a bound sentence the checks refuse every mean
    # for `bound_quote_not_located` and the accuses-nobody rail below measures
    # nothing -- a fixture that excludes the region it is meant to defend.
    "Saturday opening can run from 0 to 24 hours.",
    "Counter staff on duty ranged from 0 to 40 people.",
    "Loaves sold before noon could range from 0 to 1000 loaves.",
    "Sales of each named bread ranged from 0 to 500 loaves.",
    # NOT "Estimates of counter staff are simple means and were not adjusted."
    # -- that phrasing matches `premises.estimator_statement` paper-wide and
    # withdraws every mean in the account before any net sees it, which would
    # leave this fixture with nothing to budget. Honest prose, deliberately
    # outside the vocabulary.
    "Counter staff were tallied once at each bakery.",
    "The figures given for loaves sold are arithmetic means of the till counts.",
    "Proportions reported for opening hours were not standardised to any "
    "reference population.",
]

#: THE SENTENCES THAT NAME EACH FURTHER VARIABLE. Three apiece, because one
#: candidate a scope would make the round-robin below untestable -- and because a
#: real paper does say a variable's name more than once.
for _name in BREADS:
    SENTENCES += [
        f"{_name.capitalize()} loaves were counted as whole loaves at the till.",
        f"The mean number of {_name} loaves sold was {BREAD_MEAN[_name]} "
        f"(SD {BREAD_SD[_name]}).",
        f"Figures reported for {_name} loaves are unweighted means over the "
        f"twenty-four bakeries.",
    ]

TEXT = "\n\n".join(SENTENCES) + "\n"

#: The sentences the account's own values quote, by variable.
HOURS_Q = SENTENCES[4]
STAFF_Q = SENTENCES[5]
LOAVES_Q = SENTENCES[6]
EARLY_Q = SENTENCES[7]


def _var(vid, name, kind="continuous", lower=None, upper=None, step=None,
         gquote=None, bquote=None):
    return {"id": vid, "name": name, "label": name, "printed_as": [],
            "kind": kind, "role": None, "units": None,
            "units_source": "not_stated", "derivation": None, "derived_from": [],
            "bounds": {"source": "stated" if lower is not None else "not_stated",
                       "lower": lower, "upper": upper, "quote": bquote},
            "granularity": {"per_subject_step": step, "quote": gquote}}


def _lit(printed):
    return premises.read_plain(printed) or {}


def _prose(vid, statistic, printed, quote, *, variable_id=None):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "prose", "quote": quote,
            "quote_verified": "verbatim", "printed_in_quote": True,
            "location": {"kind": "prose", "offset": TEXT.find(quote),
                         "col_label": None},
            "coordinate": {"study_id": "study:main", "group_id": "grp:all",
                           "phase_id": None}}


def _cell(vid, statistic, printed, *, variable_id=None, col_label="Mean (SD)",
          row=1):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": "table:1", "row": row,
                         "col": 1, "col_label": col_label},
            "coordinate": {"study_id": "study:main", "group_id": "grp:all",
                           "phase_id": None}}


def account(*, n_extra=0):
    """The Kestrel Lane account. `n_extra` is how many of the paper's further
    bread variables it reports -- each one named in the prose above, each with
    its own printed mean, which is how a real paper grows a net's scope count."""
    variables = [
        _var("var:hours", "Saturday opening hours", "count", lower=0, upper=24,
             step=1, gquote=SENTENCES[1], bquote=SENTENCES[12]),
        _var("var:staff", "Counter staff on duty", "count", lower=0, upper=40,
             step=1, gquote=SENTENCES[2], bquote=SENTENCES[13]),
        _var("var:loaves", "Loaves sold before noon", "count", lower=0,
             upper=1000, step=1, gquote=SENTENCES[3], bquote=SENTENCES[14]),
        # THE PERCENTAGE GETS ITS OWN VARIABLE, and this was a real fixture bug
        # worth recording: with `val:early_pct` bound to `var:hours`, a printed
        # 33.3 sat against a declared range of 0-24 and the bridge refused four
        # checks for `bound_contradicted_by_printed_values`. The refusal was
        # correct and the fixture was wrong -- a percentage of bakeries is not a
        # number of hours.
        _var("var:early", "Bakeries opening at or before six", "percentage",
             lower=0, upper=100, step=None, bquote=SENTENCES[10]),
    ]
    values = [
        _prose("val:n", "n", str(N), SENTENCES[0]),
        _cell("val:hours_mean", "mean", HOURS_MEAN, variable_id="var:hours", row=1),
        _cell("val:hours_sd", "sd", HOURS_SD, variable_id="var:hours", row=1),
        _cell("val:staff_mean", "mean", STAFF_MEAN, variable_id="var:staff", row=2),
        _cell("val:loaves_mean", "mean", LOAVES_MEAN, variable_id="var:loaves",
              row=3),
        _prose("val:early_pct", "percentage", EARLY_PCT, EARLY_Q,
               variable_id="var:early"),
    ]
    for i, name in enumerate(BREADS[:n_extra]):
        vid = f"var:{name}"
        variables.append(_var(vid, f"{name.capitalize()} loaves sold", "count",
                              lower=0, upper=500, step=1,
                              bquote=SENTENCES[15],
                              gquote=f"{name.capitalize()} loaves were counted as "
                                     f"whole loaves at the till."))
        values.append(_cell(f"val:{name}_mean", "mean", BREAD_MEAN[name],
                            variable_id=vid, row=4 + i))
        values.append(_cell(f"val:{name}_sd", "sd", BREAD_SD[name],
                            variable_id=vid, row=4 + i))
    return {"paper": {"doi": "10.0000/kestrel",
                      "title": "The Kestrel Lane bakery survey"},
            "studies": [{"id": "study:main", "label": "The Kestrel Lane survey",
                         "design": "prospective_cohort",
                         "groups": [{"id": "grp:all", "label": "All bakeries",
                                     "n": N, "n_source": "text"}]}],
            "variables": variables, "values": values,
            # THE TABLE RECORD IS THE FULL SHAPE `render` READS, not the stub the
            # premise tests get away with: the docket under test is rendered, so
            # the whole page has to build.
            "document": {"tables": [{
                "id": "table:1", "label": "Table 1",
                "caption": "Table 1. Kestrel Lane bakeries.",
                "n_cells": 2 * (3 + n_extra), "n_header_rows": 1,
                "row_labels": [v["label"] for v in variables],
                "col_labels": ["Mean (SD)"], "sections": [], "footnotes": [],
                "source": "table", "page": 1}]}}


def fake_pass(seen, *, cost=0.02, establishes=False):
    """The model boundary, with `run_pass`'s own side effects on disk -- the
    prompt and the parsed output beside each other, which is what the reuse
    guard reads and what the cost accounting reads back."""
    def run_pass(name, prompt, out_dir, **kw):
        seen.append((name, prompt))
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        n = prompt.count("CANDIDATE ")
        data = {"verdicts": [{"candidate": i, "establishes": establishes,
                              "reason": "the sentence does not say so"}
                             for i in range(1, max(1, n) + 1)]}
        (out / f"{name}.prompt.md").write_text(prompt, encoding="utf-8")
        (out / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
        (out / f"{name}.meta.json").write_text(
            json.dumps({"cost_usd": cost, "problems": []}), encoding="utf-8")
        return {"data": data, "problems": [], "meta": {"cost_usd": cost}}
    return run_pass


# --------------------------------------------------------------------------
# 1. THE PROSE REALLY DOES BUILD MORE CANDIDATES THAN A CAP-PER-SCOPE BOUNDS
# --------------------------------------------------------------------------


class TestTheDefectIsReproducedBeforeItIsFixed:
    """Without these, every assertion below is about a set too small to bite."""

    def test_the_estimator_net_grows_linearly_in_the_variable_count(self):
        counts = {k: len(A.candidates_for(account(n_extra=k), TEXT, ("estimator",)))
                  for k in (0, 3, 6, 10)}
        assert counts[0] > PR.MAX_PER_CALL, counts
        # Each further variable the paper reports costs another ~32 candidates,
        # and nothing in the nets bounds the product. This is the corpus growth
        # law reproduced on a fixture: measured on the real served text of
        # jamanetworkopen 37679 and ajcp 70049 it is ~97 a variable, 984 at ten
        # variables and 4,536 at forty-seven.
        per_variable = [(counts[b] - counts[a]) / (b - a)
                        for a, b in ((0, 3), (3, 6), (6, 10))]
        assert all(p >= 25 for p in per_variable), counts
        assert counts[10] - counts[0] >= 300, counts

    def test_no_per_scope_cap_bounds_the_paper(self):
        many = A.candidates_for(account(n_extra=10), TEXT, ("estimator",))
        per_scope: dict = {}
        for c in many:
            per_scope[PR._budget_scope(c)] = per_scope.get(PR._budget_scope(c), 0) + 1
        # Every VARIABLE's scope is inside its own cap ...
        for scope, n in per_scope.items():
            if scope[1] != "None":
                assert n <= PR.MAX_REFUSAL_CANDIDATES, (scope, n)
        # ... and the paper is many times over it, because the number of scopes
        # is set by the paper and nothing multiplied them by a ceiling. That is
        # the arithmetic that made the bill unbounded.
        assert len(many) > PR.MAX_REFUSAL_CANDIDATES * 10, len(many)
        assert len(per_scope) >= 12, per_scope


# --------------------------------------------------------------------------
# 2. THE BUDGET BOUNDS THE BILL
# --------------------------------------------------------------------------


class TestTheBillIsBounded:
    def test_the_calls_stop_at_the_budget(self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen))
        cands = A.candidates_for(account(n_extra=6), TEXT, ("estimator",))
        got = PR.read(account(n_extra=6), TEXT, tmp_path, only=cands, budget=80)
        assert got["n_asked"] == 80
        assert got["n_calls"] == 2 and len(seen) == 2
        # The whole point: the number of paid calls is now a function of the
        # budget and not of the paper.
        assert got["n_calls"] == -(-80 // PR.MAX_PER_CALL)

    def test_a_bigger_paper_does_not_buy_a_bigger_bill(self, tmp_path, monkeypatch):
        small, big = [], []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(small))
        PR.read(account(), TEXT, tmp_path / "a", budget=80,
                only=A.candidates_for(account(), TEXT, ("estimator",)))
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(big))
        PR.read(account(n_extra=6), TEXT, tmp_path / "b", budget=80,
                only=A.candidates_for(account(n_extra=6), TEXT, ("estimator",)))
        assert len(small) == len(big) == 2

    def test_the_projection_rounds_up_to_whole_calls(self):
        assert PR.projected_usd(0) == 0.0
        assert PR.projected_usd(1) == round(PR.USD_PER_FULL_CALL, 2)
        assert PR.projected_usd(PR.MAX_PER_CALL) == round(PR.USD_PER_FULL_CALL, 2)
        # A partly-filled call is billed like a full one, so rounding down is the
        # flattering error and the projection must not make it.
        assert PR.projected_usd(PR.MAX_PER_CALL + 1) == round(2 * PR.USD_PER_FULL_CALL, 2)
        assert PR.projected_usd(PR.MAX_CANDIDATES_PER_PAPER) == 10.0


# --------------------------------------------------------------------------
# 3. IT FAILS CLOSED, AND FAILING CLOSED MEANS SAYING SO
# --------------------------------------------------------------------------


class TestItFailsClosedAndSaysSo:
    def _run(self, tmp_path, monkeypatch, budget, *, n_extra=6, establishes=False):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass",
                            fake_pass(seen, establishes=establishes))
        acc = account(n_extra=n_extra)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        return PR.read(acc, TEXT, tmp_path, only=cands, budget=budget), cands, seen

    def test_over_budget_the_run_completes_rather_than_raising(
            self, tmp_path, monkeypatch):
        got, cands, _ = self._run(tmp_path, monkeypatch, 40)
        assert got["n_asked"] == 40 and len(got["verdicts"]) == 40
        assert (tmp_path / "premise_reading.json").is_file()

    def test_it_does_not_truncate_a_call(self, tmp_path, monkeypatch):
        got, _, seen = self._run(tmp_path, monkeypatch, 50)
        # Ten candidates in the second call, not forty asked and thirty answers
        # thrown away: every question put is a question answered.
        assert got["n_calls"] == 2
        assert len(got["verdicts"]) == got["n_asked"] == 50
        assert not [p for p in got["problems"] if "no verdict returned" in p]

    def test_the_record_names_the_state(self, tmp_path, monkeypatch):
        got, cands, _ = self._run(tmp_path, monkeypatch, 40)
        assert got["budget_exhausted"] is True
        assert got["budget"] == 40
        assert got["n_askable"] == len(cands)
        assert got["n_unasked_over_budget"] == len(cands) - 40
        assert got["n_asked"] + got["n_unasked_over_budget"] == got["n_askable"]

    def test_the_record_names_which_premises_and_which_variables(
            self, tmp_path, monkeypatch):
        got, cands, _ = self._run(tmp_path, monkeypatch, 40)
        unasked = got["unasked"]
        assert unasked and all({"premise", "variable_id", "n_unasked"} <= set(r)
                               for r in unasked)
        assert sum(r["n_unasked"] for r in unasked) == got["n_unasked_over_budget"]
        assert {r["premise"] for r in unasked} == {"estimator"}
        # The variables named are variables of this account, not invented ones.
        ids = {v["id"] for v in account(n_extra=6)["variables"]} | {None}
        assert {r["variable_id"] for r in unasked} <= ids

    def test_the_problem_line_states_which_way_the_loss_falls(
            self, tmp_path, monkeypatch):
        got, _, _ = self._run(tmp_path, monkeypatch, 40)
        line = [p for p in got["problems"] if p.startswith("BUDGET EXHAUSTED")]
        assert len(line) == 1
        # A reader who takes one sentence away must take away the dangerous
        # half: these are refusal nets, so an unasked question is a check LEFT
        # RUNNING, never a check that came back clean.
        assert "REFUSAL" in line[0] and "RUNNING" in line[0]

    def test_every_candidate_is_accounted_for_exactly_once(
            self, tmp_path, monkeypatch):
        """The conservation law. A candidate was asked, or was dropped because
        its quote does not locate, or was never asked because the money ran out
        -- and a budget that made rows disappear from the arithmetic would be the
        silent truncation this whole change exists to prevent."""
        for budget in (0, 1, 40, 137, None):
            got, cands, _ = self._run(tmp_path / f"c{budget}", monkeypatch, budget)
            assert (got["n_asked"] + got["n_dropped"]
                    + got["n_unasked_over_budget"]) == got["n_candidates"]
            assert got["n_candidates"] == len(cands) == len(got["candidates"])
            flags = [c["asked"] for c in got["candidates"]]
            assert sum(1 for f in flags if f) == got["n_asked"]

    def test_a_reasked_candidate_does_not_keep_its_old_refusal(
            self, tmp_path, monkeypatch):
        """The same candidate list, two budgets: a row cut by the first and asked
        by the second must not still carry `not_asked_because`."""
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen))
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        PR.read(acc, TEXT, tmp_path / "tight", only=cands, budget=10)
        got = PR.read(acc, TEXT, tmp_path / "wide", only=cands, budget=None)
        assert got["budget_exhausted"] is False
        stale = [c["id"] for c in got["candidates"]
                 if c["asked"] and c.get("not_asked_because")]
        assert not stale, stale

    def test_zero_budget_asks_nothing_and_pays_nothing(self, tmp_path, monkeypatch):
        got, cands, seen = self._run(tmp_path, monkeypatch, 0)
        assert seen == [] and got["n_calls"] == 0 and got["cost_usd"] == 0.0
        assert got["n_asked"] == 0 and got["verdicts"] == []
        assert got["budget_exhausted"] is True
        assert got["n_unasked_over_budget"] == len(cands)
        # Nothing asked is not nothing wrong: a zero-budget run is a run that
        # asked no questions, and the record has to be able to say that rather
        # than look like a paper with no candidates.
        assert got["n_candidates"] == len(cands)


# --------------------------------------------------------------------------
# 4. THE DISTINCTION THE WHOLE THING IS FOR
# --------------------------------------------------------------------------


class TestAskedAndAnsweredNoIsNotTheSameAsNeverAsked:
    """Both end as an absent verdict and both leave the vocabulary standing. If
    the record cannot separate them, a run that ran out of money is
    indistinguishable from one that asked everything and was told no."""

    def test_the_two_are_different_fields(self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen, establishes=False))
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        got = PR.read(acc, TEXT, tmp_path, only=cands, budget=40)
        answered = {v["candidate_id"] for v in got["verdicts"]}
        assert len(answered) == 40
        assert all(v["establishes"] is False for v in got["verdicts"])
        cut = {c["id"] for c in got["candidates"]
               if c.get("not_asked_because") == "budget_exhausted"}
        assert len(cut) == got["n_unasked_over_budget"]
        # Disjoint, exhaustive over the askable set, and separately named.
        assert not (answered & cut)
        assert len(answered | cut) == got["n_askable"]

    def test_every_candidate_says_whether_it_was_asked(self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen))
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        got = PR.read(acc, TEXT, tmp_path, only=cands, budget=40)
        assert all("asked" in c for c in got["candidates"])
        assert sum(1 for c in got["candidates"] if c["asked"]) == got["n_asked"]
        for c in got["candidates"]:
            if not c["asked"]:
                assert c["not_asked_because"] in {"budget_exhausted",
                                                  "quote_not_located"}

    def test_a_budget_cut_is_not_confused_with_an_unlocatable_quote(
            self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen))
        acc = account()
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        # One candidate the served text does not contain: a different fact from
        # a candidate there was no money to ask about, and counted separately.
        ghost = dict(cands[0], id="cand:ghost", quote="The bakers wore blue hats.",
                     quote_located=False, quote_not_located_because="not in text",
                     askable=False)
        got = PR.read(acc, TEXT, tmp_path, only=cands + [ghost], budget=10)
        assert got["n_dropped"] == 1
        assert got["n_unasked_over_budget"] == len(cands) - 10
        by_id = {c["id"]: c for c in got["candidates"]}
        assert by_id["cand:ghost"]["not_asked_because"] == "quote_not_located"


# --------------------------------------------------------------------------
# 5. THE CUT MAY NOT BE A FILTER
# --------------------------------------------------------------------------


class TestTheCutDoesNotStarveAScope:
    """`MAX_REFUSAL_CANDIDATES`' own docstring: "a cap ordered by POSITION is a
    filter after all". A per-paper budget spent down the list would ask every
    question about the first variables and none about the rest -- and because
    candidates arrive grouped by scope, that is exactly what the obvious
    implementation does."""

    def test_every_scope_is_reached_before_any_scope_is_exhausted(self):
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        scopes = {PR._budget_scope(c) for c in cands}
        assert len(scopes) >= 6, len(scopes)
        kept, cut = PR._over_budget(cands, len(scopes))
        assert len(kept) == len(scopes)
        # One from each: no scope is silent while another is fully asked.
        assert {PR._budget_scope(c) for c in kept} == scopes

    def test_a_positional_cut_would_have_starved_them(self):
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        scopes = {PR._budget_scope(c) for c in cands}
        naive = {PR._budget_scope(c) for c in cands[:len(scopes)]}
        # The reason the round-robin is not ceremony: taking the first N rows
        # reaches only a fraction of the scopes on this paper.
        assert len(naive) < len(scopes)

    def test_each_scope_keeps_its_strongest_candidates_first(self):
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        kept, _ = PR._over_budget(cands, 40)
        for scope in {PR._budget_scope(c) for c in kept}:
            mine_all = [c["id"] for c in cands if PR._budget_scope(c) == scope]
            mine_kept = [c["id"] for c in kept if PR._budget_scope(c) == scope]
            # Within a scope the nets already ranked by evidence; the budget
            # takes a PREFIX of that order and never reshuffles it.
            assert mine_kept == mine_all[:len(mine_kept)]

    def test_the_cut_is_deterministic(self):
        acc = account(n_extra=6)
        a = PR._over_budget(A.candidates_for(acc, TEXT, ("estimator",)), 57)
        b = PR._over_budget(A.candidates_for(acc, TEXT, ("estimator",)), 57)
        assert [c["id"] for c in a[0]] == [c["id"] for c in b[0]]
        assert [c["id"] for c in a[1]] == [c["id"] for c in b[1]]

    def test_a_budget_that_does_not_bite_changes_nothing(self):
        cands = A.candidates_for(account(), TEXT, ("estimator",))
        for budget in (None, len(cands), len(cands) + 1, PR.MAX_CANDIDATES_PER_PAPER):
            kept, cut = PR._over_budget(cands, budget)
            assert cut == [] and [c["id"] for c in kept] == [c["id"] for c in cands]


# --------------------------------------------------------------------------
# 6. THE DEFAULT IS A RUNAWAY GUARD, NOT A ROUTINE CUT
# --------------------------------------------------------------------------


class TestTheDefaultDoesNotCutAnOrdinaryPaper:
    def test_the_default_is_above_the_worst_real_figure_on_hand(self):
        # The costing pass measured 1,819 candidates for one net on a real
        # 47-variable account. A default at or below that would cut a paper we
        # have already paid to run.
        assert PR.MAX_CANDIDATES_PER_PAPER > 1819

    def test_this_paper_is_not_cut_by_the_default(self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen))
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        got = PR.read(acc, TEXT, tmp_path, only=cands)
        assert got["budget_exhausted"] is False
        assert got["n_asked"] == len(cands) and got["unasked"] == []

    def test_an_uncut_run_says_that_an_absent_verdict_was_not_about_money(
            self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen))
        acc = account()
        got = PR.read(acc, TEXT, tmp_path,
                      only=A.candidates_for(acc, TEXT, ("estimator",)))
        acc["premise_reading"] = got
        page = render.render(acc, TEXT)
        assert "was not reached" in page


# --------------------------------------------------------------------------
# 7. THE COST IS REPORTED HONESTLY IN BOTH DIRECTIONS
# --------------------------------------------------------------------------


class TestTheCostIsReportedHonestly:
    def test_a_fresh_run_reports_what_it_spent(self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen, cost=0.2))
        acc = account(n_extra=6)
        got = PR.read(acc, TEXT, tmp_path, budget=80,
                      only=A.candidates_for(acc, TEXT, ("estimator",)))
        assert got["n_calls"] == 2
        assert got["cost_usd"] == 0.4 and got["cost_usd_total"] == 0.4
        assert got["n_calls_reused"] == 0

    def test_a_resumed_run_bills_nothing_again_and_still_says_what_it_cost(
            self, tmp_path, monkeypatch):
        """`_reuse` zeroes the cost so a resumed run is not billed twice, and is
        right to. But the artifact then cannot say what it cost, and "$0.00"
        beside fifty verdicts reads as a free instrument."""
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen, cost=0.2))
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        first = PR.read(acc, TEXT, tmp_path, only=cands, budget=80)
        again = PR.read(acc, TEXT, tmp_path, only=cands, budget=80)
        assert len(seen) == 2, "the second run must make no new call"
        assert first["cost_usd"] == 0.4
        assert again["cost_usd"] == 0.0, "this run spent nothing"
        assert again["cost_usd_total"] == 0.4, "and the reading still cost $0.40"
        assert again["n_calls_reused"] == again["n_calls"] == 2

    def test_introducing_the_budget_does_not_discard_a_paid_reply(
            self, tmp_path, monkeypatch):
        """THE PROPERTY THAT MAKES THE DEFAULT FREE TO ADOPT. `_reuse` matches on
        the prompt's bytes, so any reordering of the candidate list repays for
        every call in the paper. Under budget there is no reordering -- and it is
        worth being exact about why, because the obvious explanation is wrong.

        Two separate things hold. This test exercises the first: under budget
        `_over_budget` returns on its guard clause with the list untouched.
        The second is that even when it DOES cut, the kept rows come back in
        document order, because the result is built by filtering the input by
        index rather than by appending in pick order -- which is what
        `test_each_scope_keeps_its_strongest_candidates_first` pins.

        Measured while writing this: deleting the guard clause fails NOTHING,
        because the filter preserves order on its own. So the guard is a
        shortcut, not the mechanism, and a docstring here first claimed
        otherwise."""
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen, cost=0.2))
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        assert len(cands) < PR.MAX_CANDIDATES_PER_PAPER, "the premise of this test"
        unbudgeted = PR.read(acc, TEXT, tmp_path, only=cands, budget=None)
        assert len(seen) == unbudgeted["n_calls"] > 1
        paid = len(seen)
        again = PR.read(acc, TEXT, tmp_path, only=cands)  # the new default
        assert len(seen) == paid, "the default budget repaid for a cached reply"
        assert again["n_calls_reused"] == again["n_calls"] == paid
        assert again["cost_usd"] == 0.0

    def test_the_projection_is_of_what_was_asked(self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen))
        acc = account(n_extra=6)
        got = PR.read(acc, TEXT, tmp_path, budget=80,
                      only=A.candidates_for(acc, TEXT, ("estimator",)))
        assert got["projected_usd"] == PR.projected_usd(80)


# --------------------------------------------------------------------------
# 8. THE READER IS TOLD
# --------------------------------------------------------------------------


class TestTheAccountCarriesTheDocket:
    def _account_with_cut(self, tmp_path, monkeypatch, budget=40):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen))
        acc = account(n_extra=6)
        got = PR.read(acc, TEXT, tmp_path, budget=budget,
                      only=A.candidates_for(acc, TEXT, ("estimator",)))
        acc["premise_reading"] = got
        return acc, got

    def test_the_rendered_account_says_the_budget_ran_out(
            self, tmp_path, monkeypatch):
        acc, got = self._account_with_cut(tmp_path, monkeypatch)
        page = render.render(acc, TEXT)
        assert "THE BUDGET RAN OUT" in page
        assert str(got["n_unasked_over_budget"]) in page
        assert "REFUSAL" in page and "RUNNING" in page

    def test_the_rendered_account_names_the_scopes(self, tmp_path, monkeypatch):
        acc, got = self._account_with_cut(tmp_path, monkeypatch)
        page = render.render(acc, TEXT)
        for row in got["unasked"][:3]:
            if row["variable_id"]:
                assert row["variable_id"] in page

    def test_the_rendered_account_reports_the_cost(self, tmp_path, monkeypatch):
        acc, _ = self._account_with_cut(tmp_path, monkeypatch)
        page = render.render(acc, TEXT)
        assert "15c." in page and "Cost:" in page

    def test_a_reading_written_before_the_budget_existed_still_renders(self):
        """Readings on disk predate this field set, and the docket must not
        invent a budget for one. An artifact that carries no budget is a run we
        cannot say was or was not cut -- which is a third state, and the page
        says nothing rather than reporting a clean sweep."""
        acc = account(n_extra=3)
        acc["premise_reading"] = {
            "schema": PR.SCHEMA_VERSION, "prompt_version": PR.PROMPT_VERSION,
            "model": "sonnet", "n_candidates": 4, "n_asked": 4, "n_dropped": 0,
            "candidates": [], "verdicts": [], "problems": [],
            "cost_usd": 0.05, "n_calls": 1}
        page = render.render(acc, TEXT)
        assert "15c." in page and "Cost: **$0.05**" in page
        assert "THE BUDGET RAN OUT" not in page
        assert "was not reached" not in page

    def test_attach_writes_the_docket_into_the_account_on_disk(
            self, tmp_path, monkeypatch):
        """`premise_reading.attach` is how a reading reaches every downstream
        reader of an existing run, so the budget fields have to survive that
        trip. A docket that exists only in the return value of `read` is a
        docket nobody sees."""
        _, got = self._account_with_cut(tmp_path, monkeypatch)
        (tmp_path / "account.json").write_text(
            json.dumps(account(n_extra=6)), encoding="utf-8")
        assert PR.attach(tmp_path) is True
        on_disk = json.loads((tmp_path / "account.json").read_text())
        block = on_disk["premise_reading"]
        assert block["budget_exhausted"] is True
        assert block["n_unasked_over_budget"] == got["n_unasked_over_budget"]
        assert block["unasked"] == got["unasked"]
        assert render.render(on_disk, TEXT).count("THE BUDGET RAN OUT") == 1


# --------------------------------------------------------------------------
# 9. THE HELP TEXT QUOTES THE UNIT THAT IS BILLED
# --------------------------------------------------------------------------


class TestTheHelpTextIsAboutTheBilledUnit:
    """The estimator net's help quoted GOVERNING WINDOWS (10 to 21 on real corpus
    bodies) where the bill counts CANDIDATES (984 to 4,536 on the same bodies),
    and told an operator to budget one to four calls for something that buys
    twenty-five to a hundred and fourteen."""

    def _flat_help(self):
        """The CLI's own `--help`, with argparse's line wrapping undone.

        FLATTENED ON PURPOSE, and the negative assertions below are the reason.
        argparse wraps help text to the terminal width, so `"one to four batched
        calls" not in raw_help` can pass merely because a newline landed inside
        the phrase -- a test that reports success for the wrong reason, which is
        the exact shape this file exists to avoid. Joining on whitespace makes
        the absence a real absence.
        """
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.suppress(SystemExit):
            MAIN.main(["--help"])
        flat = " ".join(buf.getvalue().split())
        assert len(flat) > 2000, "the help did not render; every assertion below " \
                                 "would be vacuous"
        return flat

    def test_the_flattening_would_catch_the_old_sentence(self):
        # The guard on the guard: prove the negative assertion below can fail.
        flat = " ".join("budget one to four\nbatched calls. Not the".split())
        assert "one to four batched calls" in flat

    def test_the_estimator_help_no_longer_prices_in_windows(self):
        flat = self._flat_help()
        assert "one to four batched calls" not in flat
        assert "14 to 61 governing windows" not in flat

    def test_the_estimator_help_quotes_the_billed_unit_and_a_measured_count(self):
        flat = self._flat_help()
        assert "candidates" in flat.lower()
        assert "4,536" in flat, "the measured candidate count is not quoted"
        assert "$5 to $23" in flat, "the help does not price the net"

    def test_the_budget_flag_is_documented_in_candidates(self):
        flat = self._flat_help()
        assert "--premise-budget" in flat
        assert "CANDIDATES because candidates are what is billed" in flat
        assert "unasked" in flat and "budget_exhausted" in flat

    def test_the_help_does_not_promise_a_behaviour_the_code_lacks(self):
        """The help says 0 asks nothing and a negative number lifts the budget.
        Both are claims about `_over_budget` and the CLI's translation of the
        flag, so both are executed here rather than believed."""
        flat = self._flat_help()
        assert "0 asks nothing at all" in flat
        assert "any NEGATIVE number means no budget" in flat
        cands = A.candidates_for(account(n_extra=6), TEXT, ("estimator",))
        assert PR._over_budget(cands, 0) == ([], cands)
        # The CLI turns a negative flag into the library's `None`, which is the
        # only spelling of "unbudgeted" the library has.
        assert PR._over_budget(cands, None)[1] == []


# --------------------------------------------------------------------------
# 10. AND IT ACCUSES NOBODY, WHICHEVER WAY IT CUTS
# --------------------------------------------------------------------------


class TestNoCutBuysAnAccusation:
    """A budget that could turn an honest paper into a flagged one would be a
    false-accusation channel bought to save money. The nets are refusal nets so
    this should be impossible by construction; it is measured anyway, across the
    whole range of budgets, because "by construction" is what the last several
    rounds of this project kept being wrong about."""

    def test_the_free_path_accuses_nobody(self):
        got = checks.evaluate(account(n_extra=6), TEXT)
        assert got["n_run"] >= 1
        assert not [r for r in got["checks"] if r["severity"] in BAD]

    def test_no_budget_from_nothing_to_everything_accuses_anybody(
            self, tmp_path, monkeypatch):
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        for i, budget in enumerate((0, 1, 17, 40, 80, len(cands), None)):
            seen = []
            monkeypatch.setattr(PR._passes, "run_pass",
                                fake_pass(seen, establishes=True))
            one = account(n_extra=6)
            one["premise_reading"] = PR.read(
                one, TEXT, tmp_path / f"b{i}", only=list(cands), budget=budget)
            got = checks.evaluate(one, TEXT)
            bad = [r for r in got["checks"] if r["severity"] in BAD]
            assert not bad, (budget, bad[:2])

    def test_the_budget_never_creates_a_verdict(self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen, establishes=True))
        acc = account(n_extra=6)
        cands = A.candidates_for(acc, TEXT, ("estimator",))
        got = PR.read(acc, TEXT, tmp_path, only=cands, budget=40)
        # Exactly the questions asked come back answered, and nothing else.
        assert len(got["verdicts"]) == got["n_asked"] == 40
        asked_ids = {c["id"] for c in got["candidates"] if c["asked"]}
        assert {v["candidate_id"] for v in got["verdicts"]} == asked_ids


# --------------------------------------------------------------------------
# 11. EVERY NET IS GOVERNED, NOT JUST THE ONE THAT RAN AWAY
# --------------------------------------------------------------------------


class TestAllFourNetsTakeTheBudget:
    def test_each_entry_point_forwards_it(self, tmp_path, monkeypatch):
        acc = account(n_extra=6)
        for name, fn in (("estimator", lambda **kw: A.adjudicate(
                              acc, TEXT, tmp_path / "a",
                              premises=("estimator",), **kw)),
                         ("varying_n", lambda **kw: AN.adjudicate(
                             acc, TEXT, tmp_path / "n", **kw)),
                         ("attachment", lambda **kw: AA.adjudicate(
                             acc, TEXT, tmp_path / "t", **kw)),
                         ("free", lambda **kw: PR.read(
                             acc, TEXT, tmp_path / "f", **kw))):
            seen = []
            monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen))
            got = fn(budget=5)
            assert got["budget"] == 5, name
            assert got["n_asked"] <= 5, name
            assert len(seen) <= 1, name

    def test_the_default_reaches_every_entry_point(self, tmp_path, monkeypatch):
        acc = account()
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", fake_pass(seen))
        for i, fn in enumerate((lambda d: AN.adjudicate(acc, TEXT, d),
                                lambda d: AA.adjudicate(acc, TEXT, d),
                                lambda d: PR.read(acc, TEXT, d))):
            got = fn(tmp_path / f"d{i}")
            assert got["budget"] == PR.MAX_CANDIDATES_PER_PAPER
