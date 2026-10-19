"""The three headline coverage measures, on synthetic accounts.

Nothing here calls a model, and one of the tests proves it by making a
subprocess launch raise. The rest pin the five properties the measures are
worth anything only if they have:

1. the tiers partition their denominator, exactly, and a unit in two tiers or
   in none is a recorded problem rather than a rounding difference;
2. the numbers are a pure function of what is on disk, so a re-render
   reproduces them byte for byte;
3. every total is printed with its split -- a bare total is a test failure,
   because it is a number a reader cannot interrogate;
4. removing the readings moves cells to `unread` and never to `placed`, and a
   change that moves `placed` must move the other tiers by the same amount
   (the `25e2f9f` hazard, measured on the coverage side rather than the
   accusation side);
5. an entry whose `id_check` says the name join DISAGREES with the model's id
   is never counted as placed.
"""

from __future__ import annotations

import copy
import json

import pytest

from forensic_metascience_ai_toolkit.scaffold import coverage

# --------------------------------------------------------------------------
# A tiny paper: four sentences that matter, one article table, one supplement
# table, and one cell of each interesting kind.
# --------------------------------------------------------------------------

TEXT = """## RESULTS

The mean score was 4.01 in the treated group.
Attrition was 12% and the model converged (p = .03).
Earlier work found the same (Smith, 2011).
Analyses report the mean and SD for each arm.

## REFERENCES

Smith J (2011). A paper. J Things 12: 100-110.
"""

_RESULTS_END = TEXT.index("## REFERENCES")


def _at(s: str) -> int:
    return TEXT.index(s)


def _num(printed: str, disposition: str, role: str = "results") -> dict:
    off = _at(printed)
    return {"id": f"num:{off}", "printed": printed, "offset": off, "end": off + len(printed),
            "class": "unclassified", "role": role, "source": "article",
            "context": printed, "disposition": disposition, "value_id": None}


ARTICLE_TABLE = {
    "id": "table:1", "label": "Table 1", "source": "article", "caption": None,
    "n_cells": 5, "n_header_rows": 1, "reconstruction": {"status": "verified"},
    "walker_cells": [
        {"row": 1, "col": 1, "raw": "10.0 (1.0)", "row_label": "Score", "col_label": "Treated"},
        {"row": 1, "col": 2, "raw": "20.0 (2.0)", "row_label": "Score", "col_label": "Control"},
        {"row": 2, "col": 1, "raw": "5", "row_label": "Sites", "col_label": "Treated"},
        {"row": 2, "col": 2, "raw": "7", "row_label": "Sites", "col_label": "Control"},
        {"row": 3, "col": 1, "raw": "not measured", "row_label": "Notes", "col_label": "Treated"},
    ],
}
ARTICLE_TABLE["cells"] = ARTICLE_TABLE["walker_cells"]

SUPPLEMENT_TABLE = {
    "id": "table:2", "label": "Table S1", "source": "supplement", "caption": None,
    "n_cells": 2, "n_header_rows": 1, "reconstruction": {"status": "not_attempted"},
    "walker_cells": [
        {"row": 1, "col": 1, "raw": "3.5", "row_label": "Extra", "col_label": "All"},
        {"row": 1, "col": 2, "raw": "see text", "row_label": "Extra", "col_label": "Note"},
    ],
}
SUPPLEMENT_TABLE["cells"] = SUPPLEMENT_TABLE["walker_cells"]


def _cell_value(vid: str, table: str, row: int, col: int, variable_id, id_check) -> dict:
    return {"id": vid, "statistic": "mean", "printed": "10.0", "numeric": 10.0,
            "variable_id": variable_id, "id_check": id_check, "level_id": None,
            "coordinate": {"study_id": "study:1", "group_id": None, "phase_id": None},
            "source": "table", "quote": "10.0",
            "location": {"kind": "table_cell", "table_id": table, "row": row, "col": col}}


def account() -> dict:
    """One account, with a cell in every H1 tier and a sentence in every H2 tier."""
    return {
        "document": {
            "tables": [copy.deepcopy(ARTICLE_TABLE), copy.deepcopy(SUPPLEMENT_TABLE)],
            "figures": [],
            "sections": [{"role": "results", "start": 0, "end": _RESULTS_END},
                         {"role": "back", "start": _RESULTS_END, "end": len(TEXT)}],
        },
        "variables": [
            {"id": "var:score", "name": "Score", "role": "measured_outcome", "kind": "continuous",
             "levels": [], "studies_using": ["study:1"]},
            {"id": "var:arm", "name": "Arm", "role": "manipulated_factor", "kind": "categorical",
             "levels": [{"id": "lvl:t", "label": "Treated"}, {"id": "lvl:c", "label": "Control"}],
             "studies_using": ["study:1", "study:2"]},
            {"id": "var:unused", "name": "Never measured", "role": "covariate", "kind": "binary",
             "levels": [], "studies_using": ["study:1"]},
        ],
        "values": [
            # placed: a declared id the name join corroborates
            _cell_value("val:1", "table:1", 1, 1, "var:score", "agrees"),
            # read_unbound: the join DISAGREES with the model's id (invariant 5)
            _cell_value("val:2", "table:1", 1, 2, "var:score", "disagrees"),
            # read_unbound: no variable id at all
            _cell_value("val:3", "table:1", 2, 1, None, None),
            # a level-bearing variable with one of its two levels bound
            {"id": "val:4", "statistic": "count", "printed": "4.01", "numeric": 4.01,
             "variable_id": "var:arm", "level_id": "lvl:t",
             "coordinate": {"study_id": "study:1", "group_id": None, "phase_id": None},
             "source": "prose", "quote": "The mean score was 4.01 in the treated group.",
             "location": {"kind": "results", "offset": _at("The mean score"),
                          "end": _at("The mean score") + 45}},
            {"id": "val:5", "statistic": "percentage", "printed": "12", "numeric": 12.0,
             "variable_id": None, "level_id": None,
             "coordinate": {"study_id": None, "group_id": None, "phase_id": None},
             "source": "prose", "quote": "Attrition was 12%",
             "location": {"kind": "results", "offset": _at("Attrition"),
                          "end": _at("Attrition") + 17}},
        ],
        # table:1 r2c2 was read and did not parse; table:2 r1c1 was never read.
        "unparsed_cells": [{"table_id": "table:1", "row": 2, "col": 2, "raw": "7",
                            "why": "does not parse as other"}],
        "accounting": [_num("4.01", "value"), _num("12", "value"), _num(".03", "unaccounted"),
                       _num("2011", "citation_year")],
        "studies": [{"id": "study:1"}, {"id": "study:2"}],
    }


@pytest.fixture()
def acct():
    return account()


@pytest.fixture()
def head(acct):
    return coverage.headline(acct, TEXT)


# --------------------------------------------------------------------------
# Invariant 1: the tiers partition the denominator
# --------------------------------------------------------------------------


class TestTheTiersPartitionTheDenominator:

    def test_h1_tiers_sum_to_the_cells_that_carry_a_numeral(self, head):
        h1 = head["table_cells_placed"]
        # 4 numeral-bearing article cells + 1 supplement cell; `not measured`
        # and `see text` carry no numeral and are not cells of this denominator.
        assert h1["cells"] == 5
        assert sum(h1["by_tier"].values()) == h1["cells"]
        assert h1["by_tier"] == {"placed": 1, "read_unbound": 2, "unparsed": 1, "unread": 1,
                                 "non_statistical": 0}

    def test_h1_splits_sum_to_the_total_on_every_tier(self, head):
        h1 = head["table_cells_placed"]
        assert sum(d["cells"] for d in h1["splits"].values()) == h1["cells"]
        for tier in coverage.H1_TIERS:
            assert sum(d[tier] for d in h1["splits"].values()) == h1["by_tier"][tier], tier

    def test_h2_tiers_sum_to_the_statistic_bearing_sentences(self, head):
        h2 = head["statistic_sentences"]
        assert sum(h2["by_tier"].values()) == h2["statistic_sentences"]
        assert h2["by_tier"] == {"covered": 1, "partial": 1, "uncovered": 1}

    def test_a_citation_only_sentence_is_not_in_the_denominator(self, head):
        """A citation year is the literature's number, not the paper's. If it
        qualified a sentence it would also, by the same rule, make it `covered`
        for free -- coverage bought from the reference list."""
        h2 = head["statistic_sentences"]
        assert h2["statistic_sentences"] == 3
        assert not any("Earlier work" in u["sentence"] for u in h2["not_covered"])

    def test_a_token_only_sentence_is_uncovered_never_covered(self, head):
        h2 = head["statistic_sentences"]
        assert h2["n_uncovered_with_no_numeral"] == 1
        row = next(u for u in h2["not_covered"] if u["sentence"].startswith("Analyses report"))
        assert row["tier"] == "uncovered" and row["n_statistics"] == 0 and "sd" in row["tokens"]

    def test_a_unit_in_two_tiers_is_a_recorded_problem_not_a_rounding_error(self):
        assert coverage.check_conservation({"placed": 2, "unread": 2}, 3, "H1") != []
        assert coverage.check_conservation({"placed": 2, "unread": 1}, 3, "H1") == []

    def test_a_clean_account_records_no_conservation_problem(self, head):
        assert head["problems"] == []


# --------------------------------------------------------------------------
# Invariant 2: no model, and identical from disk
# --------------------------------------------------------------------------


class TestTheNumbersAreModelFree:

    def test_no_subprocess_is_launched_anywhere_in_the_computation(self, acct, monkeypatch):
        import subprocess

        def _boom(*a, **k):
            raise AssertionError("the headline measures ran a subprocess; they are "
                                 "specified as model-free and must stay that way")

        monkeypatch.setattr(subprocess, "run", _boom)
        monkeypatch.setattr(subprocess, "Popen", _boom)
        coverage.headline(acct, TEXT)

    def test_the_same_account_recomputes_byte_for_byte_from_disk(self, acct, tmp_path):
        first = coverage.headline(acct, TEXT)
        p = tmp_path / "account.json"
        p.write_text(json.dumps(acct, ensure_ascii=False), encoding="utf-8")
        again = coverage.headline(json.loads(p.read_text(encoding="utf-8")), TEXT)
        assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)

    def test_bind_puts_the_headline_on_the_account(self):
        """The measures are worthless if nothing calls them."""
        import inspect

        from forensic_metascience_ai_toolkit.scaffold import bind
        src = inspect.getsource(bind.assemble)
        assert 'account["headline"] = _coverage.headline(' in src


# --------------------------------------------------------------------------
# Invariant 3: a total is never printed without its split
# --------------------------------------------------------------------------


class TestEveryTotalIsPrintedWithItsSplit:

    def test_h1_line_carries_the_total_and_every_source(self, head):
        h1 = head["table_cells_placed"]
        md = "\n".join(coverage.render_lines(head))
        assert f"{h1['placed']} of {h1['cells']}" in md
        for name, d in h1["splits"].items():
            assert f"{name.replace('_', ' ')} {d['placed']} of {d['cells']}" in md, name

    def test_h2_line_carries_the_total_and_every_source(self, head):
        h2 = head["statistic_sentences"]
        md = "\n".join(coverage.render_lines(head))
        assert f"{h2['covered']} of {h2['statistic_sentences']}" in md
        for name, d in h2["splits"].items():
            assert f"{name.replace('_', ' ')} {d['covered']} of {d['sentences']}" in md, name

    def test_h3_line_carries_the_total_and_every_role_and_kind(self, head):
        h3 = head["declared_variables"]
        md = "\n".join(coverage.render_lines(head))
        assert f"{h3['with_any_value']} of {h3['variables']}" in md
        for axis in ("by_role", "by_kind"):
            for name, d in h3["splits"][axis].items():
                assert f"{name} {d['with_any_value']} of {d['variables']}" in md, name

    def test_every_computable_block_carries_a_split_and_a_denominator_note(self, head):
        for name, block in head.items():
            if name in coverage.NOT_A_MEASURE or block.get("not_computable"):
                continue
            assert block.get("splits"), name
            assert block.get("note", "").startswith("Denominator:"), name

    def test_a_measure_that_cannot_be_computed_says_why_and_never_prints_zero(self, acct):
        acct["document"]["tables"] = []
        acct["variables"] = []
        head = coverage.headline(acct, None)
        md = "\n".join(coverage.render_lines(head))
        assert head["table_cells_placed"]["not_computable"] == "the document holds no tables"
        assert "not computable: the document holds no tables" in md
        assert "not computable: the account declares no variables" in md
        assert "not computable: the account was loaded without the paper's text" in md
        assert "0 of 0" not in md


# --------------------------------------------------------------------------
# Invariant 4: removing the readings moves cells to `unread`, never to `placed`
# --------------------------------------------------------------------------


class TestRemovingTheReadingsCannotBuyCoverage:

    def test_with_no_readings_every_cell_is_unread(self, acct):
        acct["values"] = [v for v in acct["values"] if v["source"] != "table"]
        acct["unparsed_cells"] = []
        h1 = coverage.headline(acct, TEXT)["table_cells_placed"]
        assert h1["by_tier"] == {"placed": 0, "read_unbound": 0, "unparsed": 0, "unread": 5,
                                 "non_statistical": 0}
        assert sum(h1["by_tier"].values()) == h1["cells"]

    def test_a_move_in_placed_is_matched_exactly_by_the_other_tiers(self, acct):
        """THE `25e2f9f` HAZARD, ON THE COVERAGE SIDE. A change that raises
        `placed` while the other three fall by a different amount has not placed
        anything; it has moved the denominator, and the reader is being shown a
        larger share of a smaller universe."""
        before = coverage.headline(acct, TEXT)["table_cells_placed"]
        stripped = account()
        stripped["values"] = [v for v in stripped["values"] if v["source"] != "table"]
        stripped["unparsed_cells"] = []
        after = coverage.headline(stripped, TEXT)["table_cells_placed"]
        assert before["cells"] == after["cells"]
        rest = lambda h: sum(h["by_tier"][k] for k in coverage.H1_TIERS if k != "placed")
        assert after["by_tier"]["placed"] - before["by_tier"]["placed"] == -(rest(after) - rest(before))

    def test_a_cell_whose_value_is_lost_can_never_become_placed(self, acct):
        placed_before = coverage.headline(acct, TEXT)["table_cells_placed"]["by_tier"]["placed"]
        acct["values"] = [v for v in acct["values"] if v["id"] != "val:1"]
        assert coverage.headline(acct, TEXT)["table_cells_placed"]["by_tier"]["placed"] \
            == placed_before - 1


# --------------------------------------------------------------------------
# Invariant 5: `id_check == disagrees` is never placed
# --------------------------------------------------------------------------


class TestADisagreeingIdIsNeverPlaced:

    def test_the_disagreeing_cell_is_read_unbound(self, head):
        h1 = head["table_cells_placed"]
        assert h1["read_unbound_because"]["id_check_disagrees"] == 1
        assert h1["by_tier"]["placed"] == 1

    def test_marking_every_cell_as_disagreeing_places_nothing(self, acct):
        for v in acct["values"]:
            if v["source"] == "table" and v.get("variable_id"):
                v["id_check"] = "disagrees"
        h1 = coverage.headline(acct, TEXT)["table_cells_placed"]
        assert h1["by_tier"]["placed"] == 0
        assert h1["read_unbound_because"]["id_check_disagrees"] == 2

    def test_an_uncorroborated_id_is_placed_as_a_named_sub_tier(self, acct):
        """`unjoined` means the model asserted an id the name join could not
        check -- measured wrong on ajcp at least once. The cell IS placed, on
        the model's word alone, and the headline says how many of the placed
        cells rest on nothing but that."""
        for v in acct["values"]:
            if v["id"] == "val:2":
                v["id_check"] = "unjoined"
        h1 = coverage.headline(acct, TEXT)["table_cells_placed"]
        assert h1["by_tier"]["placed"] == 2
        assert h1["by_placed_subtier"] == {"placed_corroborated": 1, "placed_model_only": 1}
        assert h1["read_unbound_because"] == {"id_check_disagrees": 0,
                                              "regression_intercept": 0,
                                              "no_declared_variable_id": 1}
        md = "\n".join(coverage.render_lines(coverage.headline(acct, TEXT)))
        assert "corroborated 1, model only 1" in md

    def test_the_placed_sub_tiers_sum_to_placed(self, head):
        h1 = head["table_cells_placed"]
        assert sum(h1["by_placed_subtier"].values()) == h1["by_tier"]["placed"]
        assert coverage.check_conservation({"placed_corroborated": 1, "placed_model_only": 1},
                                           3, "H1 placed sub-tiers") != []

    def test_an_id_the_account_does_not_declare_is_not_placed(self, acct):
        for v in acct["values"]:
            if v["id"] == "val:1":
                v["variable_id"] = "var:never_declared"
        h1 = coverage.headline(acct, TEXT)["table_cells_placed"]
        assert h1["by_tier"]["placed"] == 0


# --------------------------------------------------------------------------
# H3, and the inverse it is printed with
# --------------------------------------------------------------------------


class TestDeclaredVariablesWithValues:

    def test_a_variable_with_no_value_is_named_not_just_counted(self, head):
        h3 = head["declared_variables"]
        assert h3["variables"] == 3 and h3["with_any_value"] == 2
        assert [v["variable_id"] for v in h3["variables_with_no_value"]] == ["var:unused"]

    def test_a_variable_missing_from_one_declaring_study_does_not_count(self, head):
        """All three variables name a study. Only `var:score` has a value at
        every study it names: `var:arm` names two and is measured in one, and
        `var:unused` is measured nowhere."""
        ev = head["declared_variables"]["with_value_in_every_declaring_study"]
        assert ev["variables_naming_a_study"] == 3 and ev["n"] == 1

    def test_levels_are_reported_as_k_of_m_of_what_we_declared(self, head):
        lw = head["declared_variables"]["levels_with_values"]
        assert lw["levels_declared"] == 2 and lw["levels_with_values"] == 1
        assert lw["by_variable"] == [{"variable_id": "var:arm", "name": "Arm",
                                      "levels_with_values": 1, "levels_declared": 2}]

    def test_levels_are_not_computable_when_nothing_declares_one(self, acct):
        for v in acct["variables"]:
            v["levels"] = []
        lw = coverage.headline(acct, TEXT)["declared_variables"]["levels_with_values"]
        assert lw == {"not_computable": "no variable declares any level"}

    def test_the_inverse_is_printed_beside_it(self, head):
        h3 = head["declared_variables"]
        assert h3["values_with_no_variable"] == 2 and h3["values_total"] == 5
        assert "Values carrying NO variable" in "\n".join(coverage.render_lines(head))


# --------------------------------------------------------------------------
# The floor is no longer the headline
# --------------------------------------------------------------------------


def test_the_numeral_floor_is_rendered_as_an_inventory_under_its_own_heading():
    from forensic_metascience_ai_toolkit.scaffold import render
    src = render.render.__doc__ or ""
    import inspect
    body = inspect.getsource(render.render)
    assert "## 0. Headline coverage" not in src
    assert "_coverage.render_lines(" in body
    assert "## 14. Inventory: the numeral floor, and the residual" in body
    assert "**This is an INVENTORY, not the headline coverage measure**" in body
