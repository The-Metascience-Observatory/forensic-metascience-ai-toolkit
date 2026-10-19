"""Coordinates: which axes a value must carry, and how a group may reach it.

THREE THINGS, ALL MEASURED ON ajcp.70049 (D47).

(a) The strict full coordinate read 3.4% while NO study on that paper declares a
    phase at all: the number was dominated by an axis that is structurally
    unavailable, not by a table-reading failure. On the two axes the design has,
    the same values are at 70%. So `full_coordinate` asks for a phase only from a
    value whose own study declares one, and the strict definition is printed
    beside it rather than replaced.

(b) A table value reaches a coordinate by two routes -- the model's own group id
    on the entry, and the pass-3 column map -- and pass 3 does not re-read a
    verified table, so where the model omitted the group id there is no fallback
    at all: all 63 values of Table 4 carried none. Its caption ends `(n = 101
    programs in 35 coalitions)` and one declared group's LABEL is that exact
    string. A group id is a DENOMINATOR, so the join binds only on a unique
    verbatim hit -- Tables 2 and 3 name two groups that share a label and bind
    nothing, which costs nothing because their values already carry the model's
    ids.

(c) Every declared group on that paper has `n_printed: None` while its label IS
    `n = 64 coalitions`. The n is parsed, never asked for, and a label carrying
    two of them yields null rather than a choice between them.
"""

from __future__ import annotations

import copy

import pytest

from metascience_agent.scaffold import bind, structure


def _doc_with(tables: list[dict], studies: list[dict]) -> dict:
    return {"tables": tables, "_studies": studies}


STUDIES = [{"id": "study:main", "groups": [
    {"id": "grp:programs_n101", "label": "n = 101 programs in 35 coalitions"},
    {"id": "grp:coalitions_n64", "label": "n = 64 coalitions"},
    {"id": "grp:coalitions_n64_reach", "label": "n = 64 coalitions"},
    {"id": "grp:two", "label": "n = 30 then n = 28"},
    {"id": "grp:printed", "label": "Intervention arm", "n_printed": "34"},
]}]


class TestTheCaptionJoin:

    def test_a_unique_verbatim_hit_binds(self):
        t = {"id": "table:4", "caption": "Associations between leadership and fidelity "
                                         "(n = 101 programs in 35 coalitions)."}
        assert bind._caption_group(t, _doc_with([t], STUDIES)) == {
            "study_id": "study:main", "group_id": "grp:programs_n101", "phase_id": None}

    def test_a_caption_two_declared_groups_answer_binds_nothing(self):
        """The ajcp Tables 2 and 3 case: two groups share the printed label
        `n = 64 coalitions`, so the caption does not say which."""
        t = {"id": "table:2", "caption": "Associations (n = 64 coalitions)."}
        assert bind._caption_group(t, _doc_with([t], STUDIES)) is None

    def test_a_continuation_panel_with_the_same_caption_binds_the_same_group(self):
        cap = "Associations (n = 101 programs in 35 coalitions)."
        a = bind._caption_group({"id": "table:4", "caption": cap}, _doc_with([], STUDIES))
        b = bind._caption_group({"id": "table:5", "caption": cap + " Continued."},
                                _doc_with([], STUDIES))
        assert a == b and a is not None

    def test_no_caption_binds_nothing(self):
        assert bind._caption_group({"id": "table:1", "caption": None},
                                   _doc_with([], STUDIES)) is None

    def test_a_caption_naming_no_declared_group_binds_nothing(self):
        assert bind._caption_group({"id": "table:1", "caption": "Sample characteristics."},
                                   _doc_with([], STUDIES)) is None


def _table(caption, entries_group_id=None, col_map=None) -> tuple[dict, dict]:
    cell = {"row": 1, "col": 1, "raw": "1.23", "row_label": "X", "col_label": "Coefficient",
            "entries": [{"variable": "X", "level": None, "group": None, "statistic": "coefficient",
                         "value": "1.23", "variable_id": None, "level_id": None,
                         "group_id": entries_group_id}]}
    t = {"id": "table:4", "label": "Table 4", "caption": caption, "source": "article",
         "n_cells": 1, "col_labels": ["Coefficient"], "row_labels": ["X"],
         "walker_cells": [cell], "cells": [cell],
         "reconstruction": {"status": "verified"}}
    p3 = {"table_readings": [{"table_id": "table:4", "column_map": col_map or []}]}
    return t, p3


def _values(caption, entries_group_id=None, col_map=None):
    t, p3 = _table(caption, entries_group_id, col_map)
    doc = _doc_with([t], STUDIES)
    vals, _ = bind._table_values(doc, p3, {}, [])
    return vals


CAP = "Associations (n = 101 programs in 35 coalitions)."


class TestTheCaptionJoinInTheAccount:

    def test_a_value_with_no_group_gets_the_captions_group_and_says_so(self):
        v = _values(CAP)[0]
        assert v["coordinate"]["group_id"] == "grp:programs_n101"
        assert v["coordinate"]["study_id"] == "study:main"
        assert v["coordinate_source"] == "caption_join"

    def test_it_cannot_overrule_a_group_the_model_named(self):
        v = _values(CAP, entries_group_id="grp:coalitions_n64")[0]
        assert v["coordinate"]["group_id"] == "grp:coalitions_n64"
        assert v["coordinate_source"] == "declared_group_id"

    def test_it_cannot_overrule_the_column_map(self):
        v = _values(CAP, col_map=[{"col_label": "Coefficient", "study_id": "study:main",
                                   "group_id": "grp:coalitions_n64", "phase_id": None}])[0]
        assert v["coordinate"]["group_id"] == "grp:coalitions_n64"
        assert v["coordinate_source"] == "column_map"

    def test_it_is_refused_where_it_would_contradict_the_study_already_there(self):
        """A caption naming another study's arm is a continuation panel misread,
        and a wrong group id is a wrong denominator."""
        v = _values(CAP, col_map=[{"col_label": "Coefficient", "study_id": "study:other",
                                   "group_id": None, "phase_id": None}])[0]
        assert v["coordinate"]["group_id"] is None
        assert v["coordinate_source"] == "column_map"

    def test_an_ambiguous_caption_leaves_the_coordinate_alone(self):
        v = _values("Associations (n = 64 coalitions).")[0]
        assert v["coordinate"]["group_id"] is None and v["coordinate_source"] is None


class TestAGroupsNIsParsedNotAsked:

    @pytest.mark.parametrize("label,expected", [
        ("n = 101 programs in 35 coalitions", 101),
        ("n = 64 coalitions", 64),
        ("Intervention (n=34)", 34),
        ("N = 12", 12),
    ])
    def test_one_n_in_the_label_is_the_n(self, label, expected):
        assert structure.group_n({"label": label}) == (expected, "label")

    @pytest.mark.parametrize("label", ["n = 30 then n = 28", "no n here", "Region n",
                                       "n = 6-9", "n = 12.5", ""])
    def test_anything_else_is_null(self, label):
        assert structure.group_n({"label": label}) == (None, None)

    def test_a_printed_integer_wins_over_the_label(self):
        assert structure.group_n({"label": "n = 64 coalitions", "n_printed": "34"}) \
            == (34, "n_printed")

    def test_a_printed_range_is_not_a_per_group_n(self):
        assert structure.group_n({"label": "Arm A", "n_printed": "6-9"}) == (None, None)

    def test_the_annotation_stamps_every_group_and_counts(self):
        studies = copy.deepcopy(STUDIES)
        got = structure.annotate_group_n(studies)
        assert got["groups"] == 5 and got["with_n"] == 4
        assert got["by_source"] == {"label": 3, "n_printed": 1, "not_stated": 1}
        assert [g["n"] for g in studies[0]["groups"]] == [101, 64, 64, None, 34]


class TestTheThirdAxisIsOnlyAnAxisWhereTheDesignHasOne:

    def _account(self, phases):
        return {"studies": [{"id": "study:main", "phases": phases,
                             "groups": [{"id": "grp:a", "label": "A"}]}],
                "values": [{"id": "val:1", "source": "table", "statistic": "mean",
                            "printed": "1", "quote_verified": "cell",
                            "coordinate": {"study_id": "study:main", "group_id": "grp:a",
                                           "phase_id": None}}],
                "comparisons": [], "claims": [], "gaps": [],
                "document": {"tables": []}, "variables": []}

    def test_with_no_declared_phase_a_study_and_a_group_are_the_whole_coordinate(self):
        c = bind._completeness(self._account([]), [], [])
        assert c["values_with_full_coordinate"] == 1
        assert c["values_with_full_coordinate_incl_phase"] == 0
        assert c["studies_declaring_a_phase"] == []

    def test_with_a_declared_phase_the_phase_is_required_again(self):
        c = bind._completeness(self._account([{"id": "phase:w1"}]), [], [])
        assert c["values_with_full_coordinate"] == 0
        assert c["values_with_full_coordinate_incl_phase"] == 0
        assert c["studies_declaring_a_phase"] == ["study:main"]

    def test_both_definitions_are_printed_with_the_reason(self):
        c = bind._completeness(self._account([]), [], [])
        assert "no third axis to be missing" in c["full_coordinate_note"]
        assert c["values_by_coordinate_source"] == {"none": 1}
