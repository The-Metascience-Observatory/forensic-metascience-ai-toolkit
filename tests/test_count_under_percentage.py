"""A category count printed with its percentage is a COUNT, not the group's n.

THE MEASUREMENT THIS EXISTS FOR. On the reference account of ajcp.70049
(2026-09-13, nine paid calls) the checks bridge enumerated 127 candidates and
ran ZERO of them. `ambiguous_n` was present on 106 and the n premise alone
blocked all 127: seven of Table 1's category counts, plus the `38` of `Use at
least one evidence-based program (n, %)`, were recorded `statistic: "n"`, so
the coordinate `(study:descriptives_table1, grp:coalitions)` offered the eight
competing n-shaped rows `[9, 20, 21, 23, 26, 38, 55, 64]` and `group_n`
correctly declined to pick one. The refusal was the denominator clamp working
on bad input.

Retyping those eight, and changing nothing else, takes the paper from 0 checks
to 12 -- 10 `consistent`, 2 `indeterminate`, no accusation.

THE SUITE TESTS BOTH DIRECTIONS. The rule has to fire on the count/percent form
and has to NOT fire on a bare declaration, on a mean/SD pair, on a
parenthesised number with no percent sign, on a fraction, and on a confidence
level -- and the whole point is that it does all of that without reading a row
label, because three of ajcp's eight cells sit under label stubs (`None`, `1`,
`2 or 3`) that contain no `n` at all.

AND IT RECORDS AN OPEN CHANNEL IT DID NOT CLOSE. `TestTheRetentionRowIsNotMine`
builds the hostile shape -- a flow row whose count/percent cell IS the analysis
n -- and shows the accusation it produces is reachable on UNMODIFIED code the
moment a model types that cell the way the reconstruction prompt asks it to.
The retype makes that state deterministic; it does not create it. Nothing here
asserts the accusation is right.
"""

from __future__ import annotations

import copy

import pytest

from metascience_agent import numerals, sections
from metascience_agent.scaffold import bind, checks, reconstruct

# --------------------------------------------------------------------------
# The rule itself
# --------------------------------------------------------------------------


class TestTheRuleReadsTheCellAndNotTheLabel:
    #: Transcribed from ajcp.70049 Table 1, column `All coalitions`. The header
    #: cell declares the group's n; the eight below it are category counts. The
    #: last three sit under the banner `Level of technical assistance received`
    #: and their row labels are the bare level names, so a rule spelled as a
    #: list of label spellings reaches five of the eight.
    AJCP_TABLE_1 = [
        ("", "n = 64", "64", False),
        ("Use at least one evidence-based program (n, %)", "38 (59%)", "38", True),
        ("Number of evidence-based programs (mean, SD)", "1.67 (2.15)", "1.67", False),
        ("EBP reach (mean, SD)", "223.5 (410.75)", "223.5", False),
        ("Population of service area (mean, SD)", "84,299 (108,353)", "84,299", False),
        ("Pennsylvania (n, %)", "55 (85.94%)", "55", True),
        ("Missouri (n, %)", "9 (14.06%)", "9", True),
        ("Communities That Care (n, %)", "26 (40.63%)", "26", True),
        ("Externally funded (n, %)", "41 (64.06%)", "41", True),
        ("None", "23 (35.94%)", "23", True),
        ("1", "21 (32.81%)", "21", True),
        ("2 or 3", "20 (31.25%)", "20", True),
    ]

    @pytest.mark.parametrize("label,cell,printed,expected", AJCP_TABLE_1)
    def test_the_real_table(self, label, cell, printed, expected):
        assert reconstruct.is_count_of_a_share(cell, printed) is expected, label

    def test_three_of_the_eight_carry_no_n_marker_in_their_label(self):
        """The reason this is not a label lexicon, stated as an assertion.
        `None`, `1` and `2 or 3` inherit their form from a banner three rows
        up, so the cell is the only place the form is written down."""
        bare = [(lab, cell, pr) for lab, cell, pr, exp in self.AJCP_TABLE_1
                if exp and "(n, %)" not in lab]
        assert [lab for lab, _, _ in bare] == ["None", "1", "2 or 3"]
        for lab, cell, pr in bare:
            assert reconstruct.is_count_of_a_share(cell, pr)

    @pytest.mark.parametrize("cell,printed", [
        ("587 / 99.5%", "587"),          # the slash form `celltypes` calls split_n_percent
        ("1 234 (12.0%)", "1234"),       # thin-space thousands, separators removed
        ("64 (100%)", "64"),             # a whole-group count is still a count
    ])
    def test_it_fires(self, cell, printed):
        assert reconstruct.is_count_of_a_share(cell, printed)

    @pytest.mark.parametrize("cell,printed,why", [
        ("n = 64", "64", "a bare declaration is the group's own n"),
        ("64", "64", "a bare integer states no share"),
        ("35 (33)", "35", "no percent sign: `_COUNT_PCT` alone would admit this"),
        ("12 / 30", "12", "a fraction, not a percentage"),
        ("12 (95% CI 3-20)", "12", "95 is a confidence level, not a share of a base"),
        ("38 (59%)", "59%", "this value IS the percentage"),
        ("84,299 (108,353)", "84,299", "a mean beside its SD"),
        ("Analysed 28 (93.3%)", "28", "the construction is not anchored at the cell"),
        ("", "64", "no cell"),
        (None, "64", "no cell at all"),
        ("28 (93.3%)", None, "no value"),
    ])
    def test_it_does_not_fire(self, cell, printed, why):
        assert not reconstruct.is_count_of_a_share(cell, printed), why


class TestTheRetypeKeepsTheModelsWord:
    def _entry(self, **kw):
        base = {"cell": "38 (59%)", "value": "38", "statistic": "n",
                "statistic_basis": "row_label"}
        return reconstruct._retype({**base, **kw})

    def test_it_retypes_and_records_what_was_overruled(self):
        e = self._entry()
        assert e["statistic"] == "count"
        assert e["statistic_as_read"] == "n"
        assert e["statistic_basis"] == "cell_form"

    def test_a_percentage_is_left_alone(self):
        e = self._entry(value="59%", statistic="percentage", statistic_basis="cell_form")
        assert e["statistic"] == "percentage"
        assert "statistic_as_read" not in e

    def test_an_adjudicated_kind_is_not_overruled(self):
        """A second reading of the whole paper, under `review.apply_adjudication`'s
        gates, may know something the cell does not. Declining costs a refusal,
        which is the safe direction."""
        e = self._entry(statistic_basis="adjudicated")
        assert e["statistic"] == "n"

    def test_entries_of_applies_it_on_both_reading_shapes(self):
        cells = {"cells": [{"row_label": "Pennsylvania (n, %)", "cell": "55 (85.94%)",
                            "column_index": 1, "numbers": [
                                {"statistic": "n", "statistic_basis": "row_label", "value": "55"},
                                {"statistic": "percentage", "statistic_basis": "cell_form",
                                 "value": "85.94%"}]}]}
        legacy = {"entries": [{"row_label": "Pennsylvania (n, %)", "cell": "55 (85.94%)",
                               "column_index": 1, "statistic": "n",
                               "statistic_basis": "row_label", "value": "55"}]}
        assert [e["statistic"] for e in reconstruct.entries_of(cells)] == ["count", "percentage"]
        assert [e["statistic"] for e in reconstruct.entries_of(legacy)] == ["count"]


# --------------------------------------------------------------------------
# End to end: a characteristics table whose answer is known by construction
# --------------------------------------------------------------------------

TEXT = """## METHODS

Sixty-four coalitions returned the survey. Wellbeing was rated on a 1-5 scale,
and each coalition gave one whole-number rating on that scale.

## RESULTS

| | All coalitions |
|---|---|
| | n = 64 |
| Pennsylvania (n, %) | 55 (85.94%) |
| Missouri (n, %) | 9 (14.06%) |
| Wellbeing (mean, SD) | 3.83 (0.42) |

## REFERENCES

Smith J (2001). A paper. J Things 12: 100-110.
"""

#: (row label, printed cell, [entries as a MODEL wrote them]). The two category
#: rows are typed `n` because the row label spells the word -- which is exactly
#: what the model did on the real paper.
_ROWS = [
    ("", "n = 64", [{"variable": "All coalitions", "statistic": "n",
                     "statistic_basis": "cell_form", "value": "64", "group_id": "grp:all"}]),
    ("Pennsylvania (n, %)", "55 (85.94%)", [
        {"variable": "State", "level": "Pennsylvania", "variable_id": "var:state",
         "statistic": "n", "statistic_basis": "row_label", "value": "55", "group_id": "grp:all"},
        {"variable": "State", "level": "Pennsylvania", "variable_id": "var:state",
         "statistic": "percentage", "statistic_basis": "cell_form", "value": "85.94%",
         "group_id": "grp:all"}]),
    ("Missouri (n, %)", "9 (14.06%)", [
        {"variable": "State", "level": "Missouri", "variable_id": "var:state",
         "statistic": "n", "statistic_basis": "row_label", "value": "9", "group_id": "grp:all"},
        {"variable": "State", "level": "Missouri", "variable_id": "var:state",
         "statistic": "percentage", "statistic_basis": "cell_form", "value": "14.06%",
         "group_id": "grp:all"}]),
    ("Wellbeing (mean, SD)", "3.83 (0.42)", [
        {"variable": "Wellbeing", "variable_id": "var:wellbeing", "statistic": "mean",
         "statistic_basis": "row_label", "value": "3.83", "group_id": "grp:all"},
        {"variable": "Wellbeing", "variable_id": "var:wellbeing", "statistic": "sd",
         "statistic_basis": "row_label", "value": "0.42", "group_id": "grp:all"}]),
]

SCALE = "Wellbeing was rated on a 1-5 scale"
STEP = "each coalition gave one whole-number rating on that scale"


def _doc(text: str, rows: list, retype: bool) -> dict:
    cells = []
    for ri, (label, raw, entries) in enumerate(rows, start=1):
        es = [dict(e) for e in entries]
        if retype:
            es = [reconstruct._retype({**e, "cell": raw}) for e in es]
        cells.append({"raw": raw, "row": ri, "col": 1, "row_label": label,
                      "col_label": "All coalitions", "entries": es})
    nums = numerals.index(text, tables_available=True)
    back = text.index("## REFERENCES")
    for r in nums:
        r["role"] = "back" if r["offset"] >= back else "results"
    return {"text": text, "original_text": text, "source": {}, "problems": [],
            "font_audit": {}, "repairs": {"n_repairs": 0},
            "sections": sections.map_sections(text),
            "tables": [{"id": "table:1", "label": "Table 1", "caption": None,
                        "n_cells": len(cells), "row_labels": [r[0] for r in rows],
                        "col_labels": ["All coalitions"], "sections": [], "footnotes": [],
                        "n_header_rows": 1, "header_rows": None,
                        "text_span": [text.index("| | All"), back - 2],
                        "cells": cells, "reconstruction": {"status": "verified"}}],
            "figures": [], "supplements_referenced": [], "numerals": nums,
            "numeral_floor": numerals.tally(nums)}


def _p1(group_n: str | None, quote: str) -> dict:
    return {
        "paper": {"title": "T", "authors": ["A"], "journal": None, "year": None,
                  "doi": None, "species_or_population": "coalitions"},
        "background": {"problem": "", "prior_findings": [], "gap": "", "aims": []},
        "subjects": {"population": None, "unit_of_analysis": None, "setting": None,
                     "recruitment": None, "eligibility": None, "species": None,
                     "strain": None, "sex": None, "age": None, "supplier": None,
                     "housing": None, "total_n_stated": True, "quote": quote},
        "statistical_analysis": {"methods_quote": "", "tests_named": [],
                                 "alpha_declared": None, "alpha_quote": None,
                                 "significance_legend": [],
                                 "detailed_statistics_location": None,
                                 "test_to_experiment_mapping_in_main_text": False},
        "phases": [], "procedures": [],
        "studies": [{"id": "study:main", "label": "Main", "aim": "",
                     "section_heading": "RESULTS",
                     "reported_in": [{"kind": "table", "label": "Table 1", "panels": []}],
                     "design_type": "cross_sectional", "design_description": "one occasion",
                     "n_range_printed": None, "n_range_quote": None, "n_scope": "total",
                     "groups": [{"id": "grp:all", "label": "All coalitions",
                                 "description": "", "n_printed": group_n, "n_quote": None}],
                     "phases": [], "outcomes_described": ["wellbeing"],
                     "manipulations_described": [], "result_summary_quotes": [],
                     "interpretation_quotes": [], "procedure_ids": []}],
        "claims": [], "supplements_referenced": [],
    }


def _var(vid, name, kind, bounds, gran):
    return {"id": vid, "name": name, "role": "measured_outcome", "kind": kind,
            "units": None, "units_source": "not_stated", "bounds": bounds,
            "granularity": gran, "derivation": None, "derived_from": [],
            "procedure_id": None, "printed_as": [], "levels": [],
            "studies_using": ["study:main"], "quote": name, "notes": None}


P2 = {"variables": [
    _var("var:wellbeing", "Wellbeing", "integer_score",
         {"lower": 1, "upper": 5, "source": "stated", "quote": SCALE},
         {"per_subject_step": 1, "basis": "whole-number rating", "quote": STEP}),
    _var("var:state", "State", "categorical",
         {"lower": None, "upper": None, "source": "not_stated", "quote": None},
         {"per_subject_step": None, "basis": None, "quote": None})],
    "group_coordinates": [], "phase_coordinates": [], "procedure_parameters": [],
    "outcome_bindings": [], "population_descriptors": []}

P3 = {"table_readings": [{"table_id": "table:1", "caption": None,
                          "n_per_column_stated": True, "n_note": None,
                          "column_map": [{"col_label": "All coalitions",
                                          "study_id": "study:main", "group_id": "grp:all",
                                          "phase_id": None}],
                          "row_map": []}],
      "prose_values": [], "comparisons": [], "figure_panels": []}


def _evaluate(text, rows, p1, retype):
    acct = bind.assemble(_doc(text, rows, retype), p1, P2, P3)
    return acct, checks.evaluate(acct, text)


class TestTheCharacteristicsTable:
    """The ajcp shape, small enough to reason about by hand."""

    P1 = staticmethod(lambda: _p1("64", "Sixty-four coalitions returned the survey"))

    def test_before_the_retype_the_denominator_is_ambiguous(self):
        acct, got = _evaluate(TEXT, _ROWS, self.P1(), retype=False)
        assert sorted(v["printed"] for v in acct["values"]
                      if v["statistic"] == "n") == ["55", "64", "9"]
        assert got["checks"] == []
        assert any(r["reason"] == "ambiguous_n"
                   for ref in got["refused"] for r in ref["reasons"])

    def test_after_the_retype_only_the_declaration_is_an_n(self):
        acct, _ = _evaluate(TEXT, _ROWS, self.P1(), retype=True)
        assert [v["printed"] for v in acct["values"] if v["statistic"] == "n"] == ["64"]
        assert sorted(v["printed"] for v in acct["values"]
                      if v["statistic"] == "count") == ["55", "9"]

    def test_checks_run_and_accuse_nobody(self):
        _, got = _evaluate(TEXT, _ROWS, self.P1(), retype=True)
        assert got["checks"], "the retype unlocked nothing"
        assert not {c["severity"] for c in got["checks"]} - {"consistent", "indeterminate"}, \
            [(c["check_id"], c["severity"]) for c in got["checks"]]

    def test_the_arithmetic_is_the_papers_own(self):
        """55/64 and 9/64 reproduce the printed percentages exactly, which is
        independent confirmation that 64 is the base and the two are counts
        over it. `check_count_percent`'s ceiling is `suspicious`, so this is a
        check that COULD have accused and did not."""
        _, got = _evaluate(TEXT, _ROWS, self.P1(), retype=True)
        cp = [c for c in got["checks"] if c["tool"] == "check_count_percent"]
        assert len(cp) == 2
        for c in cp:
            r = c["result"]
            assert r["n"] == 64 and r["consistent"] is True
            assert abs(r["reported_count"] / 64 * 100 - r["reported_percentage"]) < 0.01

    def test_a_check_can_still_fail_here(self):
        """The fixture is not one that only ever returns `consistent`. The same
        table with a percentage no integer count over 64 produces is caught."""
        rows = copy.deepcopy(_ROWS)
        rows[1][2][1]["value"] = "84.00%"
        text = TEXT.replace("55 (85.94%)", "55 (84.00%)")
        _, got = _evaluate(text, [(a, b.replace("85.94", "84.00"), c) for a, b, c in rows],
                           self.P1(), retype=True)
        bad = [c for c in got["checks"] if c["severity"] not in ("consistent", "indeterminate")]
        assert bad, "a wrong percentage went unnoticed"


# --------------------------------------------------------------------------
# The open channel, recorded and attributed
# --------------------------------------------------------------------------

FLOW_TEXT = """## METHODS

Thirty coalitions were enrolled and twenty-eight were analysed. Wellbeing was
rated on a 1-5 scale, and each coalition gave one whole-number rating on that
scale.

## RESULTS

| | All coalitions |
|---|---|
| Enrolled | 30 |
| Analysed (n, %) | 28 (93.3%) |
| Wellbeing (mean, SD) | 3.29 (0.42) |

## REFERENCES

Smith J (2001). A paper. J Things 12: 100-110.
"""

#: The hostile shape. `28 (93.3%)` IS a count -- the retype is right about it --
#: and it is ALSO the denominator every statistic at this coordinate was
#: computed on. The mean 3.29 is attainable from 28 whole-number ratings under
#: both rounding rules and from 30 under neither.
_FLOW_ROWS = [
    ("Enrolled", "30", [{"variable": "Enrolled", "statistic": "n",
                         "statistic_basis": "row_label", "value": "30",
                         "group_id": "grp:all"}]),
    ("Analysed (n, %)", "28 (93.3%)", [
        {"variable": "Analysed", "statistic": "n", "statistic_basis": "row_label",
         "value": "28", "group_id": "grp:all"},
        {"variable": "Analysed", "statistic": "percentage", "statistic_basis": "cell_form",
         "value": "93.3%", "group_id": "grp:all"}]),
    ("Wellbeing (mean, SD)", "3.29 (0.42)", [
        {"variable": "Wellbeing", "variable_id": "var:wellbeing", "statistic": "mean",
         "statistic_basis": "row_label", "value": "3.29", "group_id": "grp:all"},
        {"variable": "Wellbeing", "variable_id": "var:wellbeing", "statistic": "sd",
         "statistic_basis": "row_label", "value": "0.42", "group_id": "grp:all"}]),
]


def _flow_severities(rows, retype):
    p1 = _p1("30", "Thirty coalitions were enrolled")
    _, got = _evaluate(FLOW_TEXT, rows, p1, retype)
    return {c["check_id"]: c["severity"] for c in got["checks"]}


def _obedient(rows=None):
    """`_FLOW_ROWS` as a model that OBEYS `reconstruct.prompt` writes them -- it
    says in as many words that `38 (59%)` is `(count, percentage)`. This is the
    reading the retype makes deterministic; it does not create it."""
    rows = copy.deepcopy(rows if rows is not None else _FLOW_ROWS)
    rows[1][2][0]["statistic"] = "count"
    return rows


class TestTheRetentionRowIsNotMine:
    """THE DEMONSTRATED FALSE-ACCUSATION CHANNEL, AND THE GATE THAT NOW REFUSES IT.

    A retention row and a category row are the same object arithmetically: both
    print an integer beside a percentage, both reproduce against a base standing
    at the same coordinate, both imply that base as `count / percentage`, and
    both are correctly typed `count`. Nothing in the cell separates them, and
    nothing in the arithmetic does either -- which is why no discriminator built
    out of the numbers survived. What separates them is a RELATION the account
    does not carry: 28 of 30 is the same subjects at a later stage, 38 of 64 is
    a partition by a property.

    THE GATE ASKS THE STRUCTURE INSTEAD (`checks.group_n`,
    `count_at_this_coordinate_may_be_its_n`). A count bound to a declared
    variable or level IS a category count in the account's own vocabulary; where
    none of a coordinate's share-shaped counts is bound, the account cannot say
    what any of these integers counts and the denominator is withdrawn. It only
    ever withdraws.

    NOTHING HERE ASSERTS THAT THE RESIDUAL ACCUSATION IS CORRECT: it is not. A
    suite that pins a false accusation as expected behaviour is a defect this
    repository has already found in itself once (2026-08-29, the truncation
    case). `TestTheResidue` builds the case the gate does NOT close and says so.

    WHY NOT A ROW-LABEL VOCABULARY, measured rather than asserted (2026-09-13,
    393 ClinicalTrials.gov-paired PMC trial reports, 1,250 tables, 1,701
    count/percent rows): `premises._RETAINED` read as a label fires on five rows
    in one table and every one is an education category (`Completed secondary
    school`, `Never attended school`). A pattern narrowed until those stop is
    then silent on all 1,701. Of 111 rows whose label names a study stage, five
    print a count/percent cell and all five are those same false positives, and
    the nearest real instance -- `Complete | 75 (98.7%)` beside means under a
    header `n=76` -- is an honest table a label rule would have cost. The
    prose-join alternative (`premises.analysed_counts` naming an integer that is
    also a count at the coordinate) fires on 3.2% of columns, all coincidental
    collisions on small integers: `Male 7 (43.8%)`, `Cough 2 (4.7%)`.

    THE PREMISE THAT WOULD CLOSE IT PROPERLY is still a STAGE on the flow rows,
    where `phase_n_over_several_phases` and `analysed_n_stated_for_another_stage`
    -- both of which exist -- already refuse.
    """

    def test_the_reading_the_prompt_asks_for_reaches_the_gate_not_a_verdict(self):
        """The shape was reachable on UNMODIFIED code the moment a model typed
        the cell the way the prompt asks: GRIM and SPRITE `impossible` at the
        enrolled 30, on a mean attainable from 28. The gate refuses it."""
        assert _flow_severities(_obedient(), retype=False) == {}

    def test_the_state_that_refuses_is_no_longer_the_one_where_the_model_erred(self):
        """Before the gate, the only protection was a typing ERROR: the flow
        count recorded as an `n` made the coordinate ambiguous, and the
        ambiguity refused. Both readings refuse now, so the protection no longer
        depends on the model being wrong."""
        assert _flow_severities(_FLOW_ROWS, retype=False) == {}
        assert _flow_severities(_FLOW_ROWS, retype=True) == {}

    def test_the_retype_reproduces_the_obedient_reading_and_nothing_worse(self):
        assert _flow_severities(_FLOW_ROWS, retype=True) == \
            _flow_severities(_obedient(), retype=False)

    def test_the_refusal_names_itself_and_the_rows_it_read(self):
        """The docket has to say WHICH integers were not candidates, or the
        reader cannot tell a coordinate whose rivals were typed away from one
        that printed a single n and nothing else."""
        _, got = _evaluate(FLOW_TEXT, _obedient(), _p1("30", "Thirty coalitions were enrolled"),
                           retype=False)
        grim = [r for r in got["refused"] if r["family"] == "grim"]
        assert grim, got["refused"]
        rows = [x for x in grim[0]["reasons"]
                if x["reason"] == "count_at_this_coordinate_may_be_its_n"]
        assert rows, [x["reason"] for x in grim[0]["reasons"]]
        assert "28 are printed here as shares of a base" in rows[0]["detail"], rows[0]
        assert "none is bound to a declared variable or level" in rows[0]["detail"], rows[0]

    def test_a_level_with_no_id_does_not_license_a_value_with_no_level(self):
        """The gate's own false-licence channel, closed before it shipped. A
        declared level carrying no `id` would put `None` in the id set, and a
        value carrying no `level_id` would then test as BOUND -- the least
        identified row in the table licensing the demotion of every other."""
        p2 = copy.deepcopy(P2)
        p2["variables"][1]["levels"] = [{"id": None, "name": "Pennsylvania"}]
        acct = bind.assemble(_doc(FLOW_TEXT, _obedient(), retype=False),
                             _p1("30", "Thirty coalitions were enrolled"), p2, P3)
        got = checks.evaluate(acct, FLOW_TEXT)
        assert got["checks"] == [], got["checks"]


class TestTheResidue:
    """WHAT THE GATE DOES NOT CLOSE, built rather than asserted.

    The licence is satisfied by ONE bound category count at the coordinate. A
    flow table that also carries an ordinary characteristics row is therefore
    licensed by that row, and the stale enrolled n is resolved exactly as
    before. That is the commoner real shape, and it is the reason this is a
    NARROWING and not a close.

    THIS TEST DOES NOT SAY THE VERDICT IS RIGHT. It says the state is reachable,
    so that anyone who later claims the flow channel is closed is contradicted
    by the suite rather than by an argument.
    """

    #: `_FLOW_ROWS` with one honest category row added, bound to `var:state`.
    ROWS = _FLOW_ROWS[:2] + [
        ("Pennsylvania (n, %)", "18 (60%)", [
            {"variable": "State", "level": "Pennsylvania", "variable_id": "var:state",
             "statistic": "n", "statistic_basis": "row_label", "value": "18",
             "group_id": "grp:all"},
            {"variable": "State", "level": "Pennsylvania", "variable_id": "var:state",
             "statistic": "percentage", "statistic_basis": "cell_form", "value": "60%",
             "group_id": "grp:all"}]),
    ] + _FLOW_ROWS[2:]

    TEXT = FLOW_TEXT.replace("| Wellbeing (mean, SD) | 3.29 (0.42) |",
                             "| Pennsylvania (n, %) | 18 (60%) |\n"
                             "| Wellbeing (mean, SD) | 3.29 (0.42) |")

    def _run(self):
        """Both count/percent cells demoted -- by the retype here, and by an
        obedient model on unmodified code, which is the same state."""
        return _evaluate(self.TEXT, self.ROWS,
                         _p1("30", "Thirty coalitions were enrolled"), retype=True)

    def test_one_bound_category_row_licenses_the_stale_n(self):
        _, got = self._run()
        sev = {c["check_id"]: c["severity"] for c in got["checks"]}
        assert "impossible" in sev.values(), sev

    def test_and_the_record_still_names_every_rival(self):
        """The verdict is not withheld, so the record is the only thing a reader
        has: both shares named, and exactly one of them explained."""
        _, got = self._run()
        grim = [c for c in got["checks"] if c["tool"] == "grim_check"][0]
        rec = grim["premises"]["n"]
        assert sorted(s["printed"] for s in rec["counts_printed_as_shares_here"]) == ["18", "28"]
        assert len(rec["counts_bound_to_a_declared_category"]) == 1
