"""`printed_as`: the paper's own label for a variable, verified before it counts.

THE MEASUREMENT (D47). All 78 of ajcp.70049's `unjoined` entries -- the model
asserted a variable id and the name join could not check it -- read one of five
row labels, and every one of the five fails `values.binding_candidates` for a
morphological reason: `Externally funded` against the declared `External funding
indicator`; `Number of EBP at baseline` against `Number of EBPs at baseline
(covariate)`, a plural `s`; `Number of members (in 10's)` against `Coalition size
(count of active members)`.

AND LOOSENING THE MATCHER IS WORSE, MEASURED: crude stemming with the declared
name's parenthetical gloss folded in resolves 29 of the 78 and turns 30 more into
five- and eleven-way ambiguity. So the join is not loosened. Instead the model may
declare the labels the paper PRINTS, and each one counts only after it is found
among the row labels the table extractor read -- the `parallel.py:910` pattern,
where the model's own verdict is popped and re-derived rather than believed.

A hallucinated alias would corroborate a wrong id, which is the whole hazard, so
the tests below attack it from that side: an unprinted alias, an alias two
variables claim, an alias that is another variable's name, and an alias that
disagrees with the model.
"""

from __future__ import annotations

import copy

import pytest

from forensic_metascience_ai_toolkit.scaffold import coverage, interpret, structure

from tests.test_scaffold import P1, P2, TEXT, _doc


def _var(vid: str, name: str, **kw) -> dict:
    return {"id": vid, "name": name, "role": "covariate", "kind": "binary",
            "levels": [], "printed_as": [], "studies_using": [], **kw}


def _table(rows: list[tuple[str, str]]) -> dict:
    """One table whose walker cells carry `rows` as (row_label, cell), and whose
    tidy entries read each row's variable as the segment after the banner."""
    walker = [{"row": i, "col": 1, "raw": raw, "row_label": lab, "col_label": "All"}
              for i, (lab, raw) in enumerate(rows, start=1)]
    cells = [{"row": i, "col": 1, "raw": raw, "row_label": lab, "col_label": "All",
              "entries": [{"variable": lab.split("|")[-1].strip(), "level": None,
                           "group": None, "statistic": "count", "value": raw,
                           "variable_id": None, "level_id": None, "group_id": None}]}
             for i, (lab, raw) in enumerate(rows, start=1)]
    return {"id": "table:1", "label": "Table 1", "source": "article",
            "walker_cells": walker, "cells": cells}


ROWS = [("Covariates | Externally funded", "12"),
        ("Number of coalition members (mean, SD)", "34"),
        ("Constant", "7")]


class TestAnAliasIsCheckedBeforeItCounts:

    def test_a_printed_alias_joins_where_the_name_join_cannot(self):
        variables = [_var("var:external_funding", "External funding indicator",
                          printed_as=["Externally funded"])]
        t = _table(ROWS)
        assert interpret._variable_for("Externally funded", variables) == (None, [])
        got = interpret.bind_entries([t], variables)
        assert got["printed_as"]["entries_joined_by_a_verified_alias"] == 1
        e = t["cells"][0]["entries"][0]
        assert e["variable_id"] == "var:external_funding" and e["id_check"] == "join"

    def test_an_alias_the_tables_do_not_print_joins_nothing_and_is_named(self):
        variables = [_var("var:external_funding", "External funding indicator",
                          printed_as=["Grant supported"])]
        t = _table(ROWS)
        got = interpret.bind_entries([t], variables)
        assert got["printed_as"]["entries_joined_by_a_verified_alias"] == 0
        assert got["printed_as"]["refused"][0]["why"].startswith("no table row label")

    def test_an_alias_two_variables_claim_binds_neither(self):
        variables = [_var("var:a", "A", printed_as=["Externally funded"]),
                     _var("var:b", "B", printed_as=["Externally funded"])]
        t = _table(ROWS)
        got = interpret.bind_entries([t], variables)
        assert got["printed_as"]["entries_joined_by_a_verified_alias"] == 0
        assert "binds neither" in got["printed_as"]["refused"][0]["why"]
        assert t["cells"][0]["entries"][0]["variable_id"] is None

    def test_an_alias_that_is_another_variables_own_name_is_refused(self):
        """Aliasing a variable to a second variable's NAME is a rename, and it
        would move every value of one silently onto the other."""
        variables = [_var("var:a", "Externally funded"),
                     _var("var:b", "Something else", printed_as=["Externally funded"])]
        got = interpret.bind_entries([_table(ROWS)], variables)
        assert "own name" in got["printed_as"]["refused"][0]["why"]

    def test_the_banner_and_the_statistic_form_are_the_only_normalisations(self):
        printed = interpret.row_label_vocabulary([_table(ROWS)])
        for ok in ("Externally funded", "Covariates | Externally funded",
                   "Number of coalition members", "Number of coalition members (mean, SD)"):
            assert interpret.label_forms(ok) & printed, ok
        for no in ("External funding", "funded", "Number of members",
                   "Number of coalition member"):
            assert not (interpret.label_forms(no) & printed), no

    def test_the_name_join_itself_is_not_loosened(self):
        """The measured reason: stemming resolves 29 of 78 and makes 30 more
        ambiguous. `binding_candidates` is untouched, and stays untouched."""
        variables = [_var("var:num_ebps_baseline", "Number of EBPs at baseline (covariate)")]
        assert interpret._variable_for("Number of EBP at baseline", variables) == (None, [])


class TestAnAliasFillsAJoinAndNeverOverridesOne:

    def test_where_the_model_gave_an_id_the_alias_is_the_cross_check(self):
        variables = [_var("var:external_funding", "External funding indicator",
                          printed_as=["Externally funded"])]
        t = _table(ROWS)
        t["cells"][0]["entries"][0]["variable_id"] = "var:external_funding"
        interpret.bind_entries([t], variables)
        assert t["cells"][0]["entries"][0]["id_check"] == "agrees"

    def test_an_alias_that_contradicts_the_model_yields_disagrees_not_a_silent_swap(self):
        variables = [_var("var:external_funding", "External funding indicator",
                          printed_as=["Externally funded"]),
                     _var("var:other", "Other thing")]
        t = _table(ROWS)
        t["cells"][0]["entries"][0]["variable_id"] = "var:other"
        interpret.bind_entries([t], variables)
        e = t["cells"][0]["entries"][0]
        assert e["id_check"] == "disagrees" and e["variable_id"] == "var:other"

    def test_a_declared_variable_the_name_join_already_binds_is_not_touched(self):
        variables = [_var("var:members", "Number of coalition members",
                          printed_as=["Externally funded"])]
        t = _table(ROWS)
        interpret.bind_entries([t], variables)
        assert t["cells"][1]["entries"][0]["variable_id"] == "var:members"


class TestAnInterceptIsNotAnUnboundVariable:

    def test_the_constant_row_is_bound_as_an_intercept(self):
        t = _table(ROWS)
        interpret.bind_entries([t], [_var("var:x", "X")])
        assert t["cells"][2]["entries"][0]["binding"] == "intercept"

    @pytest.mark.parametrize("label", ["Constant", "(Constant)", "Intercept", "_cons",
                                       "Covariates | Constant"])
    def test_the_labels_that_are_an_intercept(self, label):
        assert interpret.is_intercept(label)

    @pytest.mark.parametrize("label", ["Constant comparison group", "Constant dose",
                                       "Interception rate", ""])
    def test_a_label_that_only_contains_the_word_is_not_one(self, label):
        assert not interpret.is_intercept(label)

    def test_a_declared_variable_called_constant_still_wins(self):
        t = _table(ROWS)
        interpret.bind_entries([t], [_var("var:constant", "Constant")])
        assert t["cells"][2]["entries"][0]["binding"] == "variable"

    def test_h1_names_the_intercept_instead_of_calling_it_a_failed_join(self):
        acct = {"document": {"tables": [{"id": "table:1", "source": "article",
                                         "caption": None, "walker_cells": [
                                             {"row": 3, "col": 1, "raw": "7",
                                              "row_label": "Constant", "col_label": "All"}]}],
                             "figures": [], "sections": []},
                "variables": [{"id": "var:x", "name": "X", "levels": [], "studies_using": []}],
                "values": [{"id": "val:1", "statistic": "coefficient", "printed": "7",
                            "variable_id": None, "id_check": None, "binding": "intercept",
                            "coordinate": {}, "source": "table",
                            "location": {"kind": "table_cell", "table_id": "table:1",
                                         "row": 3, "col": 1}}],
                "unparsed_cells": [], "accounting": [], "studies": []}
        acct["document"]["tables"][0]["cells"] = acct["document"]["tables"][0]["walker_cells"]
        h1 = coverage.table_cells_placed(acct)
        assert h1["by_tier"]["read_unbound"] == 1
        assert h1["read_unbound_because"] == {"id_check_disagrees": 0,
                                              "regression_intercept": 1,
                                              "no_declared_variable_id": 0}


# --------------------------------------------------------------------------
# The gated way to add one
# --------------------------------------------------------------------------

PRINTED = {"externallyfunded", "covariatesexternallyfunded"}


def _edit(**kw) -> dict:
    e = {"op": "add_printed_as", "id": "var:weight", "parent_variable_id": None,
         "label": "Externally funded", "role": None, "kind": None,
         "quote": "Covariates | Externally funded",
         "why": "Tables 2-4 print the covariate under this stub"}
    e.update(kw)
    return e


def _apply(edit, printed=PRINTED):
    st = structure.build(P1, P2, _doc())
    after, audit = structure.apply_structural_adjudication(
        st, {"disagreements": [], "structural_edits": [edit]}, TEXT,
        bound_variable_ids=set(), printed_row_labels=printed)
    return after, audit


class TestAddPrintedAsIsGatedOnWhatTheExtractorRead:

    def test_a_label_and_a_quote_the_extractor_read_are_applied(self):
        after, audit = _apply(_edit())
        assert audit["n_applied"] == 1 and audit["n_skipped"] == 0
        var = next(v for v in after["pass2"]["variables"] if v["id"] == "var:weight")
        assert var["printed_as"] == ["Externally funded"]

    def test_a_label_no_table_prints_is_refused(self):
        _, audit = _apply(_edit(label="Grant supported", quote="Grant supported"))
        assert audit["n_applied"] == 0
        assert "not a table row label" in audit["skipped"][0]["why"]

    def test_a_quote_no_table_prints_is_refused_even_when_the_label_is_printed(self):
        _, audit = _apply(_edit(quote="the paper surely prints it somewhere"))
        assert audit["n_applied"] == 0
        assert "the quote" in audit["skipped"][0]["why"]

    def test_without_the_extractors_labels_every_such_edit_is_refused(self):
        """Not knowing what the tables print is not the same as knowing they
        print this. The fail-closed reading is the only one that cannot invent
        a label."""
        _, audit = _apply(_edit(), printed=None)
        assert audit["n_applied"] == 0
        assert "unknown is not a printing" in audit["skipped"][0]["why"]

    def test_an_undeclared_variable_is_refused(self):
        _, audit = _apply(_edit(id="var:never_declared"))
        assert audit["n_applied"] == 0
        assert "not a declared variable" in audit["skipped"][0]["why"]

    def test_the_same_label_twice_is_refused_the_second_time(self):
        st = structure.build(P1, P2, _doc())
        once, _ = structure.apply_structural_adjudication(
            st, {"disagreements": [], "structural_edits": [_edit()]}, TEXT,
            bound_variable_ids=set(), printed_row_labels=PRINTED)
        _, audit = structure.apply_structural_adjudication(
            once, {"disagreements": [], "structural_edits": [_edit()]}, TEXT,
            bound_variable_ids=set(), printed_row_labels=PRINTED)
        assert audit["n_applied"] == 0
        assert "already a printed label" in audit["skipped"][0]["why"]

    def test_it_adds_no_id_and_the_vocabulary_does_not_move(self):
        st = structure.build(P1, P2, _doc())
        after, _ = _apply(_edit())
        assert structure.id_counts(after) == structure.id_counts(st)

    def test_it_moves_the_content_hash_so_older_artifacts_are_refused(self):
        st = structure.build(P1, P2, _doc())
        after, _ = _apply(_edit())
        assert structure.content_sha256(after) != structure.content_sha256(st)
        assert after["version"] == st["version"] + 1 and after["status"] == "adjudicated"

    def test_the_op_is_in_the_schema_the_adjudicator_is_given(self):
        sch = structure.structure_adjudication_schema()
        ops = sch["properties"]["structural_edits"]["items"]["properties"]["op"]["enum"]
        assert "add_printed_as" in ops
