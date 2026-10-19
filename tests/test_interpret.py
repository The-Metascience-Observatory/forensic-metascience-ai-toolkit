"""Tidy entries joined to the declared variables and levels (step 3)."""
from metascience_agent.scaffold import interpret as I

VARS = [
    {"id": "var:state", "name": "State", "levels": [{"id": "lvl:pa", "label": "Pennsylvania", "value": None},
                                                    {"id": "lvl:mo", "label": "Missouri", "value": None}]},
    {"id": "var:ta", "name": "Level of technical assistance received",
     "levels": [{"id": "lvl:ta0", "label": "Little to no TA", "value": 0},
                {"id": "lvl:ta1", "label": "Regular noncustomized assistance in groups", "value": 1},
                {"id": "lvl:ta2", "label": "Regular (monthly) one-on-one monitoring", "value": 2},
                {"id": "lvl:ta3", "label": "Regular (monthly) one-on-one capacity building assistance", "value": 3}]},
    {"id": "var:ctc", "name": "Communities That Care (CTC) model indicator", "levels": []},
    {"id": "var:members", "name": "Number of active coalition members", "levels": []},
]


def _table(*entries):
    return [{"id": "table:1", "cells": [{"row": 1, "col": 1, "raw": "x", "entries": list(entries)}]}]


def _e(variable, level, statistic="count", value="1", variable_id=None, level_id=None):
    return {"variable": variable, "level": level, "group": None, "statistic": statistic, "value": value,
            "variable_id": variable_id, "level_id": level_id, "group_id": None}


class TestTheJoin:
    def test_variable_and_level_bind_by_declared_structure(self):
        t = _table(_e("State", "Pennsylvania"), _e("State", "Missouri"))
        s = I.bind_entries(t, VARS)
        es = t[0]["cells"][0]["entries"]
        assert [(e["variable_id"], e["level_id"], e["binding"]) for e in es] == [
            ("var:state", "lvl:pa", "variable_and_level"), ("var:state", "lvl:mo", "variable_and_level")]
        assert s["bound_to_a_variable"] == 2

    def test_a_coded_level_matches_by_value_and_a_merged_one_is_ambiguous(self):
        t = _table(_e("Level of technical assistance received", "1"),
                   _e("Level of technical assistance received", "2 or 3"),
                   _e("Level of technical assistance received", "None"))
        I.bind_entries(t, VARS)
        es = {e["level"]: e for e in t[0]["cells"][0]["entries"]}
        assert es["1"]["level_id"] == "lvl:ta1"
        assert es["2 or 3"]["binding"] == "ambiguous_level" and set(es["2 or 3"]["level_candidates"]) == {"lvl:ta2", "lvl:ta3"}
        assert es["None"]["binding"] == "variable_only_level_unmatched", (
            "the table says None where Methods says 'Little to no TA'; a human's call, not a rule's")

    def test_a_variable_the_paper_names_two_ways_is_left_to_the_candidates(self):
        t = _table(_e("Communities That Care", None), _e("Number of coalition members", None, "mean", "35.78"))
        s = I.bind_entries(t, VARS)
        es = t[0]["cells"][0]["entries"]
        assert es[0]["variable_id"] == "var:ctc" and es[1]["variable_id"] == "var:members"
        assert "verdict" not in s


class TestTheModelsOwnIds:
    def test_a_declared_id_from_the_model_is_the_binding_and_the_join_cross_checks_it(self):
        t = _table(_e("State", "Pennsylvania", variable_id="var:state", level_id="lvl:pa"),
                   _e("State", "Missouri", variable_id="var:ta"),        # model wrong; join says var:state
                   _e("Something odd", None, variable_id="var:nope"))    # id does not exist: ignored
        s = I.bind_entries(t, VARS)
        es = t[0]["cells"][0]["entries"]
        assert (es[0]["variable_id"], es[0]["level_id"], es[0]["variable_id_source"], es[0]["agrees_with_join"]) == \
            ("var:state", "lvl:pa", "model", True)
        assert (es[1]["variable_id"], es[1]["agrees_with_join"], es[1]["id_check"]) == ("var:ta", False, "disagrees"), "recorded, not overruled"
        assert es[0]["id_check"] == "agrees"
        assert es[2]["variable_id"] is None and es[2]["variable_id_source"] is None
        assert s["by_binding"].get("model_id_agrees") == 1 and s["by_binding"].get("model_id_disagrees") == 1
