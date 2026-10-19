"""The value register: every printed value, what it belongs to, what checks it."""
import pathlib

import pytest

from metascience_agent import values as V
from metascience_agent.tools.celltypes import parse_cells

VARS = [{"id": "v1", "name": "BDI-II", "family": "likert_composite",
         "measurement_level": "interval", "discreteness": "discrete",
         "lower_bound": 0, "upper_bound": 63},
        {"id": "v2", "name": "Responders", "family": "binary",
         "lower_bound": 0, "upper_bound": 1}]


def _register(cells, bindings):
    return V.build_register(
        tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
        bindings=bindings, variables=VARS)


class TestAValueIsTheUnit:
    CELLS = [{"raw": "4.20 (0.21)", "row": 1, "col": 1, "row_label": "BDI-II"},
             {"raw": "12/30 (40.0)", "row": 2, "col": 1, "row_label": "Responders"},
             {"raw": "4.20 (0.35)", "row": 3, "col": 1, "row_label": "BDI-II wk4"}]
    BIND = {"BDI-II": "v1", "Responders": "v2", "BDI-II wk4": "v1"}

    def test_a_cell_becomes_a_group_of_roled_values(self):
        """`4.20 (0.21)` is one printed thing and two values, and the checks
        consume them separately -- GRIM takes the mean, GRIMMER takes both."""
        reg = _register(self.CELLS, self.BIND)
        assert reg["n_groups"] == 3 and reg["n_values"] == 7
        g = next(g for g in reg["groups"] if g["kind"] == "mean_sd")
        assert [v["role"] for v in g["values"]] == ["mean", "sd"]

    def test_ambiguity_is_resolved_by_the_declared_variable(self):
        """A bare row printing `4.20 (0.21)` is `ambiguous` to the parser and
        `mean_sd` once a family is declared. Skipping that step dropped every
        mean/SD cell -- exactly the coverage the declaration is meant to buy."""
        reg = _register(self.CELLS, self.BIND)
        assert sum(1 for g in reg["groups"] if g["kind"] == "mean_sd") == 2

    def test_every_value_carries_its_anchor_and_its_variable(self):
        reg = _register(self.CELLS, self.BIND)
        for g in reg["groups"]:
            for v in g["values"]:
                a = v["anchor"]
                assert a["where"] == "table" and a["row"] is not None
                assert v["variable_id"] in {"v1", "v2"}

    def test_ids_are_derived_from_where_the_value_is_printed(self):
        """Not from list position, so they survive re-extraction -- which is
        what lets a viewer keep a highlight and what makes `same_value` mean
        anything."""
        reg = _register(self.CELLS, self.BIND)
        ids = [v["id"] for g in reg["groups"] for v in g["values"]]
        assert len(ids) == len(set(ids)), "value ids collided"
        assert "val:t1:r1:c1:mean" in ids

    def test_applicable_tools_match_what_check_table_would_actually_run(self):
        """THIS TEST ASSERTED THE WRONG ANSWER until an adversarial review
        caught it. BDI-II is a `likert_composite`, and `check_table` refuses the
        whole granularity family on a composite scored as a mean -- but
        `applicable_tools` read `DISPATCH` alone and reported all three, so the
        register promised checks the pipeline would decline. The test enshrined
        the promise instead of checking it against the pipeline, which is what
        it now does."""
        from metascience_agent.dispatch import check_table
        reg = _register(self.CELLS, self.BIND)
        g = next(g for g in reg["groups"] if g["kind"] == "mean_sd")
        out = check_table(cells=self.CELLS, variables=VARS, bindings=self.BIND)
        # Scoped to THIS cell: other rows of the table run their own checks.
        ran_here = {r["tool"] for r in out["results"]
                    if (r.get("cell") or {}).get("raw") == g["quote"]}
        assert set(g["applicable_tools"]) >= ran_here
        assert g["applicable_tools"] == [], (
            "BDI-II is a composite; the granularity family is refused")
        assert ran_here == set(), "the pipeline agrees: nothing ran here"

    def test_a_non_composite_variable_does_get_the_granularity_family(self):
        """...and the gate is not simply swallowing everything."""
        cells = [{"raw": "4.20 (0.21)", "row": 1, "row_label": "Item score"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
            bindings={"Item score": "v9"},
            variables=[{"id": "v9", "name": "Item score", "family": "likert_item",
                        "lower_bound": 1, "upper_bound": 7}])
        assert set(reg["groups"][0]["applicable_tools"]) == {
            "grim_check", "grimmer_check", "sprite_reconstruct"}

    def test_declined_and_never_considered_are_different_answers(self):
        """`DISPATCH.get` defaulted to `()`, so a pair the dispatcher has
        deliberately declined and one it has never heard of came back
        identically."""
        assert V.applicable_tools("garbage", "unknown") is None
        assert V.applicable_tools("mean_sd", "unknown") == ()


class TestSameValueEdges:
    def test_one_number_printed_twice_is_linked(self):
        cells = [{"raw": "4.20 (0.21)", "row": 1, "col": 1, "row_label": "A"},
                 {"raw": "4.20 (0.35)", "row": 2, "col": 1, "row_label": "B"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
            bindings={"A": "v1", "B": "v1"}, variables=VARS)
        linked = [ids for ids in reg["same_value"].values()]
        assert any(len(ids) == 2 and all(i.endswith(":mean") for i in ids)
                   for ids in linked)

    def test_71_and_71_point_0_are_NOT_the_same_value(self):
        """Different assertions about precision, and precision is what every
        granularity check is testing. Keying on the parsed float would collide
        them -- `str(4.2)` is "4.2" where the paper wrote "4.20"."""
        cells = [{"raw": "101 (71%)", "row": 1, "col": 1, "row_label": "A"},
                 {"raw": "140 (71.0%)", "row": 2, "col": 1, "row_label": "B"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
            bindings={"A": "v2", "B": "v2"}, variables=VARS)
        printed = sorted(v["printed"] for g in reg["groups"]
                         for v in g["values"] if v["role"] == "percentage")
        assert printed == ["71", "71.0"]
        assert reg["same_value"] == {}

    def test_a_count_of_30_is_not_a_denominator_of_30(self):
        """Role must match: they are not the same claim."""
        edges = V.same_value_edges([
            {"values": [{"id": "a", "role": "count", "printed": "30"}]},
            {"values": [{"id": "b", "role": "denominator", "printed": "30"}]},
        ])
        assert edges == {}


class TestProseIsHonestAboutWhatItCannotJoin:
    def test_a_prose_item_is_one_ungrouped_value(self):
        """`_body_items` emits one row per regex match, so `M = 4.20 (SD =
        0.21)` arrives as two unrelated rows -- the information that they belong
        together was lost before this module saw it. Recording them as grouped
        would be a claim we cannot support."""
        groups = V.groups_from_body_items(
            [{"id": "body:10", "where": "body", "offset": 10, "kind": "p_value",
              "raw": "p = .011", "context": "..."}])
        assert groups[0]["grouping"] == "ungrouped_prose"
        assert groups[0]["values"][0]["role"] == "p"

    def test_an_nhst_span_is_parsed_into_its_parts(self):
        """This used to assert `role == "unknown"` -- the `nhst` branch of
        `prose_values` did not exist, so the one prose kind carrying a WHOLE
        test reached the register as a printed string and nothing else.
        MEASURED 2026-08-22: 38 such groups on 10.1007--s00221-011-2544-z and
        not one carried a number."""
        groups = V.groups_from_body_items(
            [{"id": "body:20", "where": "body", "offset": 20, "kind": "nhst",
              "raw": "t(38) = 7.21", "context": "..."}])
        by_role = {v["role"]: v for v in groups[0]["values"]}
        assert by_role["df"]["value"] == 38
        assert by_role["statistic"]["value"] == 7.21
        assert by_role["statistic"]["statistic_kind"] == "t"

    def test_an_f_keeps_its_two_df_apart(self):
        """F(2, 54) and F(54, 2) are different tests, so the denominator gets
        its own role rather than being a second `df` row told apart by order."""
        groups = V.groups_from_body_items(
            [{"id": "body:20", "where": "body", "offset": 20, "kind": "nhst",
              "raw": "F(2, 54) = 51.81", "context": "..."}])
        by_role = {v["role"]: v["value"] for v in groups[0]["values"]}
        assert by_role["df"] == 2 and by_role["df2"] == 54

    def test_a_span_that_still_cannot_be_parsed_is_recorded_not_dropped(self):
        """The honesty rule the old test was really protecting: an unparsed
        statistic is still a statistic the paper printed."""
        groups = V.groups_from_body_items(
            [{"id": "body:20", "where": "body", "offset": 20, "kind": "nhst",
              "raw": "chi-squared was large", "context": "..."}])
        assert groups[0]["values"][0]["role"] == "unknown"
        assert groups[0]["values"][0]["printed"] == "chi-squared was large"

    def test_a_prose_kind_names_the_checks_that_could_run(self):
        """`applicable_tools` was hard-coded `[]` for every body group, and an
        empty list is this module's word for "considered and declined" -- so a
        register that had never looked was reporting a decision. MEASURED: 74
        of 74 groups on 10.1007--s00221-011-2544-z."""
        groups = V.groups_from_body_items(
            [{"id": "body:20", "where": "body", "offset": 20, "kind": "nhst",
              "raw": "t(38) = 7.21", "context": "..."}])
        assert "recalc_stat_to_p" in groups[0]["applicable_tools"]
        assert groups[0]["applicable_tools_known"] is True

    def test_a_deliberate_empty_is_distinguishable_from_never_considered(self):
        """`named_equality` is one labelled number with nothing to check it
        against -- an empty list BY DECISION. A kind the table has never heard
        of gets the same empty list and `applicable_tools_known: False`."""
        known, unknown = V.groups_from_body_items([
            {"id": "b:1", "where": "body", "offset": 1, "kind": "named_equality",
             "raw": "n = 202", "context": "..."},
            {"id": "b:2", "where": "body", "offset": 2, "kind": "a_new_kind",
             "raw": "??", "context": "..."},
        ])
        assert known["applicable_tools"] == [] and known["applicable_tools_known"]
        assert unknown["applicable_tools"] == []
        assert unknown["applicable_tools_known"] is False


class TestTheRegisterDoesNotOverclaim:
    def test_it_says_it_is_a_floor(self):
        reg = _register([{"raw": "4.20 (0.21)", "row": 1, "col": 1,
                          "row_label": "BDI-II"}], {"BDI-II": "v1"})
        assert "LOWER BOUND" in reg["is_a_floor"]

    def test_no_applicable_tool_is_counted_separately_from_a_gap(self):
        """A group with no tool is either a kind no check consumes or a
        variable nobody declared. `census` tells those apart; this count exists
        so the register never reads as a coverage claim it has not earned."""
        reg = _register([{"raw": "4.20 (0.21)", "row": 1, "col": 1,
                          "row_label": "Unbound"}], {})
        assert reg["n_groups_with_no_applicable_tool"] == reg["n_groups"]


class TestColumnIdentityInRealTables:
    """`prepass.paper_tables` carries NO `col`. Measured on
    10.1007--s00702-004-0248-2: 0 of 20 cells had one and 10 of 20 shared a
    `(row, col)` key, every cell in a row collapsing onto `r2:cNone`. This is
    the identity failure the repo has already paid for twice -- in
    `completeness.build_manifest` (94 of 757 items, 12.4%) and in `check_table`,
    where it cost 40% of the row dispositions."""

    CELLS = [{"raw": "4.20 (0.21)", "row": 2, "row_label": "BDI",
              "col_label": "Treatment"},
             {"raw": "4.55 (0.31)", "row": 2, "row_label": "BDI",
              "col_label": "Placebo"}]

    def _reg(self):
        return V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(self.CELLS),
                     "cells": self.CELLS}],
            bindings={"BDI": "v1"}, variables=[{"id": "v1", "family": "continuous"}])

    def test_two_columnless_cells_in_one_row_get_distinct_ids(self):
        reg = self._reg()
        ids = [v["id"] for g in reg["groups"] for v in g["values"]]
        assert len(ids) == 4 and len(set(ids)) == 4, ids

    def test_the_ordinal_counts_every_cell_not_only_the_typed_ones(self):
        """Counting only the cells that yield a group moves the ordinal the
        moment a neighbour's kind changes -- which happens as soon as a variable
        is declared and `_resolve_ambiguous` settles it. An id that shifts
        because a neighbour got typed is not an identity."""
        cells = [{"raw": "not a number", "row": 2, "row_label": "BDI"},
                 {"raw": "4.20 (0.21)", "row": 2, "row_label": "BDI"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
            bindings={"BDI": "v1"}, variables=[{"id": "v1", "family": "continuous"}])
        # The numeric cell is SECOND in its row and must say so.
        assert reg["groups"][0]["anchor"]["ordinal"] == 1

    def test_the_column_label_is_kept_but_is_not_the_key(self):
        """Two columns can carry the same header and some carry none, so the
        label is the better display and the worse identity."""
        reg = self._reg()
        labels = {g["anchor"]["col_label"] for g in reg["groups"]}
        assert labels == {"Treatment", "Placebo"}


class TestIdsSurviveBeingWrittenIntoMarkup:
    def test_a_docling_table_label_is_slugged_in_the_id(self):
        """`prepass` labels a docling table `cref='#/texts/57'` -- quotes, a
        hash and slashes. The hover view addresses values by id from the page,
        so an id has to survive being written into markup."""
        import re
        cells = [{"raw": "4.20 (0.21)", "row": 1, "row_label": "A"}]
        reg = V.build_register(
            tables=[{"name": "cref='#/texts/57'", "parsed": parse_cells(cells),
                     "cells": cells}],
            bindings={"A": "v1"}, variables=[{"id": "v1", "family": "continuous"}])
        g = reg["groups"][0]
        assert not re.search(r"[^A-Za-z0-9_.:\-]", g["id"]), g["id"]
        # ...and the label a reader sees is untouched.
        assert g["anchor"]["table"] == "cref='#/texts/57'"


class TestVerdictsJoinBackOntoValues:
    """The register is only a join if the verdicts reach it. `check_table` is
    handed cells with no table name, so it cannot build a value id -- but it can
    say which cell of which row a verdict belongs to, and `(row_label, ordinal)`
    is unique within a table."""

    # Two columns of one row printing the SAME numerator and denominator, which
    # is ordinary in a trial table and is why the join cannot key on the text.
    CELLS = [{"raw": "12/30 (40.0)", "row": 2, "row_label": "Responders",
              "col_label": "Treatment"},
             {"raw": "12/30 (44.4)", "row": 2, "row_label": "Responders",
              "col_label": "Placebo"}]
    VARS = [{"id": "v1", "name": "Responders", "family": "binary",
             "lower_bound": 0, "upper_bound": 1}]

    def _joined(self):
        from metascience_agent.dispatch import check_table
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(self.CELLS),
                     "cells": self.CELLS}],
            bindings={"Responders": "v1"}, variables=self.VARS)
        out = check_table(cells=self.CELLS, variables=self.VARS,
                          bindings={"Responders": "v1"})
        return V.attach_checks(reg, out["results"], table="t1",
                               consistent=out["consistent_index"])

    def test_every_verdict_finds_its_value(self):
        reg = self._joined()
        assert reg["unjoined_check_cells"] == []
        assert reg["n_checks_attached"] == 4

    def test_the_wrong_cell_and_the_right_one_get_their_own_verdicts(self):
        """12/30 is 40.0. Joining on the printed text would have attached one
        column's verdict to the other's value -- both cells read `12/30`."""
        reg = self._joined()
        by_quote = {g["quote"]: g for g in reg["groups"]}
        assert all(c["passed"] for c in by_quote["12/30 (40.0)"]["checks"])
        assert not any(c["passed"] for c in by_quote["12/30 (44.4)"]["checks"])

    def test_a_value_that_PASSED_is_not_spelled_like_one_nothing_ran_on(self):
        """`consistent_index` carried no cell, so a cleared value and an
        unchecked value were indistinguishable downstream -- an absence read as
        knowledge, in the index whose job is to say what came back clean."""
        reg = self._joined()
        clean = next(g for g in reg["groups"] if g["quote"] == "12/30 (40.0)")
        assert len(clean["checks"]) == 2
        assert {c["severity"] for c in clean["checks"]} == {"consistent"}

    def test_a_check_matching_no_value_is_surfaced_not_swallowed(self):
        """It means the register and the dispatcher disagree about what cells
        exist. A silent zero would read as a clean join."""
        reg = V.build_register(tables=[], body_items=[])
        V.attach_checks(reg, [{"check_id": "x", "tool": "grim_check",
                               "cell": {"row_label": "Ghost", "ordinal": 0}}],
                        table="t1")
        assert reg["unjoined_check_cells"]


class TestDedupBelongsAtTheValueLayer:
    def test_the_same_check_twice_on_one_value_collapses(self):
        reg = {"groups": [{"checks": [
            {"tool": "grim_check", "severity": "consistent", "passed": True},
            {"tool": "grim_check", "severity": "consistent", "passed": True},
            {"tool": "grimmer_check", "severity": "suspicious", "passed": False},
        ]}]}
        V.dedupe_checks(reg)
        assert reg["n_duplicate_checks_removed"] == 1
        assert len(reg["groups"][0]["checks"]) == 2

    def test_identical_checks_on_DIFFERENT_values_both_survive(self):
        """Identical arguments from different printed values are two real
        checks of two real numbers. Deduplicating on the arguments alone -- the
        obvious place -- would delete a real finding."""
        reg = {"groups": [
            {"checks": [{"tool": "grim_check", "severity": "impossible",
                         "passed": False}]},
            {"checks": [{"tool": "grim_check", "severity": "impossible",
                         "passed": False}]},
        ]}
        V.dedupe_checks(reg)
        assert reg["n_duplicate_checks_removed"] == 0
        assert all(len(g["checks"]) == 1 for g in reg["groups"])


class TestAGroupAlwaysAccountsForItself:
    """Without refusals attached the register spells three different things the
    same way: a value nothing applies to, a value a check cleared, and a value a
    check was REFUSED on. The third is the one a reader most needs."""

    def test_a_refused_group_carries_the_reason(self):
        reg = V.build_register(tables=[{"name": "t1", "parsed": {"cells": [
            {"raw": "47 (60.3)", "kind": "n_percent", "count": 47,
             "percent": 60.3, "row_label": "Female"}]},
            "cells": [{"raw": "47 (60.3)", "row": 4, "row_label": "Female"}]}],
            bindings={"Female": "v2"}, variables=VARS)
        V.attach_not_run(reg, [{"cell": "Female", "row": 4, "kind": "n_percent",
                                "tools": ["grim_percentage"],
                                "reason": "needs n and this cell carries none"}],
                         table="t1")
        g = reg["groups"][0]
        assert g["not_run"][0]["reason"].startswith("needs n")
        # Coarser than the verdict join, and marked as such rather than passed
        # off as per-value.
        assert g["not_run"][0]["granularity"] == "row"

    def test_a_refusal_does_not_cross_to_another_row_with_the_same_label(self):
        """Clinical tables repeat labels -- "Male" under two arms, "Age" at
        baseline and endpoint. Keying on the label alone stamped row 7's
        refusal onto row 2's values."""
        cells = [{"raw": "10 (33.3)", "row": 2, "row_label": "Male"},
                 {"raw": "20 (60.0)", "row": 7, "row_label": "Male"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
            bindings={"Male": "v2"}, variables=VARS)
        V.attach_not_run(reg, [{"cell": "Male", "row": 7, "kind": "n_percent",
                                "tools": ["grim_percentage"],
                                "reason": "row seven only"}], table="t1")
        by_row = {g["anchor"]["row"]: g for g in reg["groups"]}
        assert by_row[7].get("not_run")
        assert not by_row[2].get("not_run")

    def test_coverage_keeps_the_four_states_apart(self):
        reg = {"groups": [
            {"anchor": {"where": "table"}, "applicable_tools": ["grim_check"],
             "checks": [{"tool": "grim_check"}]},
            {"anchor": {"where": "table"}, "applicable_tools": ["grim_check"],
             "checks": [], "not_run": [{"reason": "no n"}]},
            {"anchor": {"where": "table"}, "applicable_tools": [], "checks": []},
            {"anchor": {"where": "table"}, "applicable_tools": ["grim_check"],
             "checks": []},
        ]}
        c = V.coverage(reg)
        assert (c["n_checked"], c["n_refused_with_a_reason"],
                c["n_no_applicable_tool"], c["n_silent"]) == (1, 1, 1, 1)

    def test_silence_is_declared_a_bug_here_not_a_finding_there(self):
        c = V.coverage({"groups": [{"anchor": {"where": "table"},
                                    "applicable_tools": ["grim_check"],
                                    "checks": []}]})
        assert c["n_silent"] == 1
        assert "bug here, not a finding there" in c["note"]


class TestTheThreeDefectsAnAdversarialReviewFound:
    """None of these were caught by the 25 tests shipped with the module. Each
    is pinned here by the reviewer's own reproducing case."""

    BINARY = [{"id": "v2", "name": "Male", "family": "binary",
               "lower_bound": 0, "upper_bound": 1}]

    def test_a_verdict_does_not_cross_to_a_row_with_the_same_label(self):
        """HIGH. `(row_label, ordinal)` is not unique within a table. Row 2 is
        honest (10/30 = 33.3); row 7 is not (20/30 = 66.7, printed 60.0). The
        honest row came away carrying the other's `suspicious` finding -- a
        false accusation rendered onto an honest value."""
        from metascience_agent.dispatch import check_table
        cells = [{"raw": "10 (33.3)", "row": 2, "row_label": "Male", "n": 30},
                 {"raw": "20 (60.0)", "row": 7, "row_label": "Male", "n": 30}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
            bindings={"Male": "v2"}, variables=self.BINARY)
        out = check_table(cells=cells, variables=self.BINARY,
                          bindings={"Male": "v2"})
        V.attach_checks(reg, out["results"], table="t1",
                        consistent=out["consistent_index"])
        by_row = {g["anchor"]["row"]: g for g in reg["groups"]}
        assert not [c for c in by_row[2]["checks"] if not c["passed"]], \
            "the honest row was accused"
        assert [c for c in by_row[7]["checks"] if not c["passed"]]
        # 4 verdicts, not 8: each was being attached twice.
        assert reg["n_checks_attached"] == 4

    def test_no_literal_is_ever_fabricated(self):
        """HIGH. `printed` claimed to hold the paper's literal and was
        reconstructed from the parsed float plus a decimals count. For
        `estimate_ci` that count is `decimals_interval`, deliberately the
        COARSEST of the three numbers, so `1.42 (1.08-1.9)` yielded a ci_low of
        "1.1" -- and `same_value` then linked it to a genuine 1.1."""
        cells = [{"raw": "1.42 (1.08-1.9)", "row": 1, "col": 1, "row_label": "OR"},
                 {"raw": "2.0 (1.1-3.6)", "row": 2, "col": 1, "row_label": "OR"},
                 {"raw": "1,234.5 (12.1)", "row": 3, "col": 1, "row_label": "Mass"},
                 {"raw": "-0.21 (0.05)", "row": 4, "col": 1, "row_label": "Beta"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
            bindings={k: "v1" for k in ("OR", "Mass", "Beta")},
            variables=[{"id": "v1", "family": "continuous"}])
        for g in reg["groups"]:
            for v in g["values"]:
                assert v["printed"] in g["quote"], (v["printed"], g["quote"])
        assert reg["same_value"] == {}, "1.08 and 1.1 are different numbers"

    def test_the_interval_hyphen_is_not_a_minus_sign(self):
        """Introduced while fixing the above, caught before it shipped:
        reading the hyphen in `1.08-1.9` as a sign made ci_high `-1.9`, which
        is the same fabrication in a new place. A real minus still survives."""
        assert V._literals("1.42 (1.08-1.9)") == ["1.42", "1.08", "1.9"]
        assert V._literals("-0.21 (0.05)") == ["-0.21", "0.05"]
        assert V._literals("1,234.5 (12.1)") == ["1,234.5", "12.1"]

    def test_a_cell_kind_with_no_role_map_is_recorded_not_dropped(self):
        """HIGH. Six kinds fell through `if not roles: continue`, against the
        module's promise that an unnameable value is recorded with role
        `unknown` rather than dropped -- true of prose, false of tables. A
        paper whose every table cell was dropped read exactly like a paper with
        no tables."""
        cells = [{"raw": "47 (60.3)", "row": 1, "row_label": "A"},   # ambiguous
                 {"raw": "93", "row": 2, "row_label": "B"},          # count
                 {"raw": "0.166", "row": 3, "row_label": "C"},       # numeric
                 {"raw": "Age (years)", "row": 4, "row_label": "D"}]  # no value
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        assert reg["n_groups"] == 3
        assert reg["n_untyped_groups"] >= 1
        # The valueless cell is COUNTED, never invented into a value.
        assert reg["n_cells_with_no_value"] == 1


class TestTheFiveMediumsAndTheLow:
    """The rest of the adversarial review, each pinned by its reproducing case."""

    def test_two_tables_that_slug_alike_do_not_share_ids(self):
        """`cref='#/texts/57'` and `cref-texts-57` both key as
        `cref-texts-57`, and every unnamed table fell back to the literal
        `"t1"` -- colliding with each other and with a real table named `t1`.
        A colliding table name collides every id beneath it."""
        cells = [{"raw": "4.20 (0.21)", "row": 2, "row_label": "BDI",
                  "col_label": "T"}]
        mk = lambda name: {"name": name, "parsed": parse_cells(cells),
                           "cells": cells}
        reg = V.build_register(
            tables=[mk("cref='#/texts/57'"), mk("cref-texts-57"), mk(None), mk(None)],
            bindings={"BDI": "v1"}, variables=[{"id": "v1", "family": "continuous"}])
        ids = [v["id"] for g in reg["groups"] for v in g["values"]]
        # 4 tables x 1 cell x 2 values (mean, sd).
        assert len(ids) == len(set(ids)) == 8

    def test_a_row_number_of_1_and_of_str_1_are_one_row(self):
        """They rendered the same id while the ordinal dict counted them
        separately, so two cells shared `t1:r1:i0`."""
        cells = [{"raw": "4.20 (0.21)", "row": 1, "row_label": "A"},
                 {"raw": "5.10 (0.22)", "row": "1", "row_label": "A"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
            bindings={"A": "v1"}, variables=[{"id": "v1", "family": "continuous"}])
        ids = [g["id"] for g in reg["groups"]]
        assert len(ids) == len(set(ids))

    def test_a_unique_column_header_survives_a_reordering(self):
        """An ordinal is list position, so an id built on it moves when a
        re-extraction reorders a row -- and for cells from
        `prepass.paper_tables` the ordinal was ALL there was."""
        a = {"raw": "4.20 (0.21)", "row": 2, "row_label": "BDI", "col_label": "Treatment"}
        b = {"raw": "4.55 (0.31)", "row": 2, "row_label": "BDI", "col_label": "Placebo"}
        def ids(cells):
            reg = V.build_register(
                tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
                bindings={"BDI": "v1"},
                variables=[{"id": "v1", "family": "continuous"}])
            return {g["anchor"]["col_label"]: g["id"] for g in reg["groups"]}
        assert ids([a, b]) == ids([b, a])

    def test_an_unlabelled_row_still_joins(self):
        """dispatch stamps `""` for a missing label while the register stored
        `None`, so the check RAN, came back consistent, and the verdict was
        dropped -- after which `coverage()` called the group silent and its note
        claimed "a check neither ran nor said why", false in both halves."""
        reg = V.build_register(tables=[{"name": "t1", "parsed": {"cells": [
            {"raw": "4.20 (0.21)", "kind": "mean_sd", "value": 4.2, "sd": 0.21}]},
            "cells": [{"raw": "4.20 (0.21)", "row": 1}]}])
        V.attach_checks(reg, [], table="t1", consistent=[
            {"check_id": "c1", "tool": "grim_check",
             "cell": {"row_label": "", "row": 1, "ordinal": 0}}])
        assert reg["unjoined_check_cells"] == []
        assert reg["groups"][0]["checks"]

    def test_coverage_states_are_actually_exclusive(self):
        """`n_no_applicable_tool` was counted regardless of the others, so an
        undeclared cell with a refusal attached landed in two buckets and the
        four states summed to 2 for 1 group."""
        reg = {"groups": [{"anchor": {"where": "table"}, "applicable_tools": [],
                           "checks": [], "not_run": [{"reason": "no n"}]}]}
        c = V.coverage(reg)
        assert c["states_are_exclusive"] is True
        assert (c["n_checked"] + c["n_refused_with_a_reason"]
                + c["n_no_applicable_tool"] + c["n_silent"]) == c["n_table_groups"]

    def test_the_role_map_is_allowed_to_differ_from_forensic_kwargs(self):
        """The comment claimed they "cannot disagree". They already did:
        `forensic_kwargs` returns {} for `mean_se` while this table maps it,
        because one records what the paper PRINTED and the other decides what a
        check may CONSUME."""
        from metascience_agent.tools.celltypes import ParsedCell
        se_cell = ParsedCell(raw="4.20 (0.21)", kind="mean_se", value=4.2, se=0.21)
        # `forensic_kwargs` declines to hand a standard error to a granularity
        # tool; the register still records both numbers, because the paper
        # printed both.
        assert se_cell.forensic_kwargs() == {}
        assert "mean_se" in V._CELL_ROLES


class TestTheRunActuallyProducesOne:
    """A library nothing calls is not a feature -- the same gap the variable
    gate sat in for three commits. `write_review_outputs` now emits
    `value_register.json` beside the report."""

    PAPER = pathlib.Path("cerebrolysin_papers/10.1007--s00702-004-0248-2")

    def test_a_call_whose_table_cannot_be_identified_is_not_guessed(self):
        """A verdict placed on a guessed table is a guessed accusation."""
        cells = [{"raw": "4.20 (0.21)", "row": 1, "row_label": "A"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        assert V.table_for_cells(reg, [{"raw": "nothing like it"}]) is None

    def test_two_tables_with_identical_cells_are_refused_not_picked(self):
        cells = [{"raw": "4.20 (0.21)", "row": 1, "row_label": "A"}]
        reg = V.build_register(tables=[
            {"name": "t1", "parsed": parse_cells(cells), "cells": cells},
            {"name": "t2", "parsed": parse_cells(cells), "cells": cells}])
        assert V.table_for_cells(reg, cells) is None


class TestTheRealRunFoundTheseFour:
    """A $10.17 run of 10.1007--s11031-011-9216-y made 58 tool calls, 0 of them
    `check_table` and 0 carrying a `variable_id`. Everything below was invisible
    until then."""

    def test_a_per_cell_call_joins_by_the_numbers_it_consumed(self):
        """The model does not use `check_table`, so a register that joins only
        the batch path shows a paper's every check as absent."""
        cells = [{"raw": "6.58 (.52)", "row": 1, "row_label": "Self-eval"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__grimmer_check",
             "input": {"mean": 6.58, "sd": 0.52, "n": 12},
             "result": {"severity": "impossible"}}])
        assert reg["n_per_cell_checks_joined"] == 1
        assert reg["groups"][0]["checks"][0]["severity"] == "impossible"

    def test_APA_leading_dot_still_matches(self):
        """The call carries the float 0.52; psychology prints `.52`. Matching
        the repr alone joined 1 of 58 real calls -- and the one it joined was
        matched on a different argument. `quotes._number_forms` already solved
        this."""
        assert V._appears_in(0.52, "6.58 (.52)")
        assert V._appears_in(0.52, "6.58 (0.52)")

    def test_a_number_does_not_match_inside_a_longer_one(self):
        assert not V._appears_in(6.58, "16.583 (1.2)")

    def test_a_call_with_nothing_joinable_is_not_a_failed_join(self):
        """`extract_xml`, `Read`, `StructuredOutput` and `rivets_anova` (lists,
        not scalars) carry no single value to match. Counting them as unmatched
        put 33 of a run's 58 calls in a bucket labelled failure -- an absence
        and an unasked question spelled identically.

        THREE STATES, NOT TWO. This test once asserted that a FETCH and a
        LIST-ARGUMENT CHECK land in the same bucket. They do not: `extract_xml`
        never computed a verdict about anything, while `statcheck` computed
        real verdicts whose inputs are a block of text rather than the numbers
        it read. Measured over the nine registers, that one bucket held 239
        calls, 96 of them fetches -- so a name promising "a check that found no
        value" was 40% calls that were not checks.
        """
        reg = V.build_register(tables=[], body_items=[])
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__extract_xml", "input": {"xml_path": "p.xml"}},
            {"id": "c2", "name": "mcp__x__statcheck", "input": {"text": "t(28)=3.3"}},
            {"id": "c3", "name": "mcp__x__grimmer_check",
             "input": {"mean": 9.99, "sd": 0.1}, "result": {}}])
        assert reg["n_non_check_calls"] == 1, "a fetch is not a check"
        assert reg["n_calls_with_no_matchable_value"] == 1, "no scalar to join on"
        assert reg["n_per_cell_checks_unmatched"] == 1, "had a value, found no cell"

    def test_the_reason_a_call_did_not_join_is_not_guessed_for_a_new_tool(self):
        """A tool name this file has never seen is a CHECK until shown otherwise.

        The plumbing list is a whitelist of things known not to compute
        verdicts. Guessing the other way -- treating an unrecognised name as
        plumbing -- would quietly drop a real check out of the denominator, and
        a coverage figure that shrinks its own denominator is the house failure
        mode wearing a percentage.
        """
        reg = V.build_register(tables=[], body_items=[])
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__some_check_invented_tomorrow",
             "input": {"whatever": 3}}])
        assert reg["n_non_check_calls"] == 0
        assert reg["n_calls_with_no_matchable_value"] == 1

    def test_two_cells_with_the_same_numbers_are_refused_not_picked(self):
        cells = [{"raw": "6.58 (.52)", "row": 1, "row_label": "A"},
                 {"raw": "6.58 (.52)", "row": 2, "row_label": "B"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__grimmer_check",
             "input": {"mean": 6.58, "sd": 0.52}, "result": {}}])
        assert reg["n_per_cell_checks_ambiguous"] == 1
        assert reg["n_per_cell_checks_joined"] == 0


class TestUnboundRowsReportTheirCandidates:
    """An unbound row is the largest coverage blocker in the archive -- 275
    cells. Reporting only the count leaves a reader unable to tell "nothing was
    declared for this row" from "several were and they conflict"."""

    VARIABLES = [
        {"id": "v_item", "name": "Self-evaluation (own attractiveness, single item)",
         "family": "likert_item"},
        {"id": "v_comp", "name": "Self-evaluation index, pilot study (mean of three)",
         "family": "likert_composite"},
        {"id": "v_cue", "name": "Similarity cue", "family": "binary"},
    ]

    def test_an_ambiguous_row_is_reported_not_guessed(self):
        """VERBATIM from the fraud ground-truth paper. The two candidates differ
        in FAMILY, and a composite's granularity is 1/(k*n) rather than 1/n --
        binding this row to the wrong one is the documented way to manufacture
        an impossibility out of a correct number."""
        got = V.binding_candidates(["Self-evaluation"], self.VARIABLES)[0]
        assert got["status"] == "ambiguous"
        assert {c["family"] for c in got["candidates"]} == {
            "likert_item", "likert_composite"}
        assert "choosing a verdict" in got["note"]

    def test_a_single_candidate_is_safe_to_bind(self):
        got = V.binding_candidates(["Similarity cue"], self.VARIABLES)[0]
        assert got["status"] == "bound" and got["n_candidates"] == 1

    def test_a_row_with_no_related_variable_says_so(self):
        got = V.binding_candidates(["Haemoglobin"], self.VARIABLES)[0]
        assert got["status"] == "unmatched"
        assert got["candidates"] == []

    def test_nothing_is_ever_bound_automatically(self):
        """Exact-name binding matched 0 of 157 values on the real run, and a
        containment rule matches 0 too -- but for a better reason: the labels
        really are ambiguous. This reports and refuses to choose."""
        import inspect
        src = inspect.getsource(V.binding_candidates)
        assert "NOT A MATCHER" in src
        for row in V.binding_candidates(["Self-evaluation", "Similarity"],
                                        self.VARIABLES):
            assert "variable_id" not in row, "a row must not carry a chosen binding"


class TestRoleClass:
    """Greg, 2026-08-18, on descriptive statistics that are not part of any
    inferential test: "they seem distinct enough to handle in a different way".
    `role_class` is that handling. These tests pin the two properties that make
    it safe to key consumers off it."""

    def test_every_role_has_a_class(self):
        """TOTALITY. `role_class` falls back to "unknown" for an unmapped role,
        which is the right default for a stray string but the WRONG answer for a
        role we ship: it would file a real, nameable value under "we could not
        tell what this is". A new entry in ROLES must fail here rather than get
        quietly absorbed."""
        unmapped = [r for r in V.ROLES if r not in V._ROLE_CLASS]
        assert unmapped == [], (
            f"roles with no class: {unmapped}. Add them to _ROLE_CLASS -- do "
            f"not let role_class()'s 'unknown' fallback answer for them.")

    def test_classes_are_closed(self):
        assert set(V._ROLE_CLASS.values()) <= set(V.ROLE_CLASSES)

    def test_the_granularity_family_is_descriptive(self):
        """The inputs GRIM/GRIMMER/SPRITE/DEBIT consume are descriptive, and the
        checks that recompute a reported test are inferential. If this ever
        inverts, the coverage log is describing the opposite of what ran."""
        assert V.role_class("mean") == "descriptive"
        assert V.role_class("sd") == "descriptive"
        assert V.role_class("p") == "inferential"
        assert V.role_class("statistic") == "inferential"

    def test_the_blocking_values_are_design(self):
        """`n` is 100% of the missing-input class across the archived runs, and
        `df` gates p-value recomputation the same way. The class exists to name
        what BLOCKS a check, so these three must be in it."""
        assert V.role_class("n") == "design"
        assert V.role_class("denominator") == "design"
        assert V.role_class("df") == "design"

    def test_a_mean_is_descriptive_whether_or_not_it_was_tested(self):
        """The discriminator is what the value IS, not whether the paper ran a
        test on it. Classifying by "was it tested" would misfile the baseline
        comparisons `csf` and `table1_dispersion` exist to consume."""
        assert V.role_class("mean") == V.role_class("median") == "descriptive"

    def test_built_values_carry_their_class(self):
        """A mean/SD row and an n (%) row are both descriptive; the `n` the
        latter is measured against is design. Note the declaration: an
        undeclared `4.20 (0.21)` is `ambiguous`, its values are `unknown`, and
        `unknown` is then the HONEST class -- the point of the fixture is that
        classification follows the parse rather than the digits."""
        reg = _register(TestAValueIsTheUnit.CELLS, TestAValueIsTheUnit.BIND)
        byrole = {v["role"]: v["role_class"]
                  for g in reg["groups"] for v in g["values"]}
        assert byrole["mean"] == byrole["sd"] == "descriptive"
        assert byrole["count"] == byrole["percentage"] == "descriptive"
        assert byrole["denominator"] == "design"

    def test_an_undeclared_cell_is_unknown_not_descriptive(self):
        """The counterpart. Guessing "descriptive" for a cell the parser could
        not type would be the house failure mode -- an absence rendered as
        knowledge."""
        cs = [{"raw": "4.20 (0.21)", "row": 1, "col": 1, "row_label": "Score"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cs), "cells": cs}],
            bindings={}, variables=[])
        vals = [v for g in reg["groups"] for v in g["values"]]
        assert vals, "an undeclared cell must still be indexed, not dropped"
        assert {v["role_class"] for v in vals} == {"unknown"}


class TestDesignValues:
    """The `n` printed in a table's own labels, indexed as a value.

    It gates grim, grimmer, sprite, debit and check_count_percent and is 100% of
    `census.blocked_on_input`, yet `_CELL_ROLES` emits no `n` from any cell kind
    -- so before this it reached the dispatcher as a bare argument parsed out of
    a column header and was never a node the reader could see."""

    CELLS = [
        {"raw": "4.20 (0.21)", "row": 1, "col": 1,
         "row_label": "BDI-II", "col_label": "Placebo (n = 68)"},
        {"raw": "4.40 (0.25)", "row": 2, "col": 1,
         "row_label": "BDI-II wk4", "col_label": "Placebo (n = 68)"},
        {"raw": "3.90 (0.19)", "row": 1, "col": 2,
         "row_label": "BDI-II", "col_label": "Drug (n = 59)"},
    ]

    def _reg(self):
        return V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(self.CELLS),
                     "cells": self.CELLS}],
            bindings={"BDI-II": "v1", "BDI-II wk4": "v1"}, variables=[])

    def test_one_header_is_one_value_however_many_cells_it_governs(self):
        """The failure this avoids: a header over twelve cells becoming twelve
        copies of one number, which is twelve nodes for one piece of ink."""
        reg = self._reg()
        placebo = [d for d in reg["design_values"] if d["value"] == 68]
        assert len(placebo) == 1
        assert len(placebo[0]["anchor"]["occurrences"]) == 2

    def test_two_arms_are_two_values_even_when_the_n_agrees(self):
        cells = [dict(c, col_label=c["col_label"].replace("59", "68"))
                 for c in self.CELLS]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}],
            bindings={}, variables=[])
        assert len({d["id"] for d in reg["design_values"]}) == 2
        assert {d["value"] for d in reg["design_values"]} == {68}

    def test_design_values_are_not_groups(self):
        """A group is something CHECKED; a design value is something CONSUMED.
        Filing these as groups would add permanently-unchecked entries to the
        coverage denominator, so a paper would look less covered the more of its
        structure we successfully read."""
        reg = self._reg()
        assert reg["n_design_values"] == 2
        ids = {v["id"] for g in reg["groups"] for v in g["values"]}
        assert not ids & {d["id"] for d in reg["design_values"]}

    def test_a_group_points_at_the_n_that_permits_its_check(self):
        reg = self._reg()
        g = next(g for g in reg["groups"] if g["anchor"].get("col_label")
                 == "Placebo (n = 68)")
        by_id = {d["id"]: d for d in reg["design_values"]}
        assert g["design_inputs"]
        assert all(by_id[i]["value"] == 68 for i in g["design_inputs"])

    def test_they_carry_the_design_class(self):
        reg = self._reg()
        assert {d["role_class"] for d in reg["design_values"]} == {"design"}
        assert {d["role"] for d in reg["design_values"]} == {"n"}

    def test_a_truncated_header_yields_nothing_rather_than_a_guess(self):
        """Real, from `10.1007--s00702-004-0248-2`: extraction cut a header down
        to `Placebo (n`. There is no n to read, and inventing one from the
        neighbouring column would be a fabricated input to a check that can
        accuse."""
        cells = [{"raw": "4.20 (0.21)", "row": 1, "col": 1,
                  "row_label": "BDI-II", "col_label": "Placebo (n"}]
        assert V.design_values_from_cells(cells, table="t1") == []

    def test_the_thousands_separator_survives_in_printed(self):
        cells = [{"raw": "4.20 (0.21)", "row": 1, "col": 1,
                  "col_label": "Cohort (n = 1,204)"}]
        d = V.design_values_from_cells(cells, table="t1")[0]
        assert d["printed"] == "1,204" and d["value"] == 1204


class TestTheBatchIsAttachedWhereTheAnatomyExists:
    """`classification_batch` was inert: built, tested, and called by nothing.
    It is attached in `agent.py` at the point the register is written, which is
    after the anatomy has been returned -- Greg's ordering constraint, satisfied
    by WHERE it runs rather than by a comment asking for it."""

    def test_the_agent_attaches_it_after_the_anatomy(self):
        """Pins the call site. If the register write moves above the anatomy,
        the batch would be built against no variables and start refusing on
        every paper -- visible as `ready: false` everywhere, but only if
        somebody looked."""
        import re
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src" / "metascience_agent" / "agent.py").read_text()
        assert "classification_batch(register, variables=variables)" in src
        i_vars = src.index('variables = anatomy_obj.get("variables")')
        i_batch = src.index("classification_batch(register")
        assert i_vars < i_batch, "the batch must be built AFTER the anatomy"

    def test_context_is_not_stored_twice(self):
        """The items carry no `context`: it is already on `numerals.rows` under
        the same `id`, and keeping both cost 21% of the artefact to say one
        thing twice."""
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src" / "metascience_agent" / "agent.py").read_text()
        assert 'k != "context"' in src
        assert "context_is_on" in src

    def test_the_batch_joins_back_to_the_numerals_by_id(self):
        """The join the artefact promises has to actually resolve."""
        reg = {"paper": "x", "numerals": {"rows": [
            {"id": "n1", "printed": "4.20", "offset": 10, "end": 14,
             "class": "unclassified", "context": "a mean of 4.20 units",
             "section": "analytic"}]}}
        b = V.classification_batch(reg, variables=[{"id": "v1", "name": "BDI"}])
        assert b["ready"] is True and b["n_items"] == 1
        by_id = {r["id"]: r for r in reg["numerals"]["rows"]}
        assert by_id[b["items"][0]["id"]]["context"] == "a mean of 4.20 units"


class TestOneBindingRuleNotTwo:
    """`agent.py` built `bindings` as an exact name->id dict while
    `binding_candidates` -- which allows containment, and is the rule this
    module documents -- ran afterwards for DISPLAY ONLY. The register was built
    by the weaker rule and the better one only told a reader what had been
    missed.

    MEASURED on 10.1007--s00702-004-0248-2 against its own run's anatomy: exact
    match binds 0 of 16 row labels; containment binds 1 (`Age (years) 1` ->
    `Age`) and leaves 15 unmatched -- `Male`/`Female`/`Left`/`Right` are
    category LEVELS rather than variables, and `CNS 1`/`GCS 1` would need
    initials-guessing. One is the honest ceiling for a rule that does not
    guess."""

    VARS = [{"id": "age", "name": "Age", "family": "continuous",
             "measurement_level": "ratio", "discreteness": "continuous"}]
    CELLS = [{"raw": "65.2 (1.17)", "row": 1, "col": 1,
              "row_label": "Age (years) 1", "col_label": "Arm A"}]

    def test_a_row_label_containing_the_variable_name_binds(self):
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(self.CELLS),
                     "cells": self.CELLS}],
            bindings={"Age (years) 1": "age"}, variables=self.VARS)
        assert reg["n_values_bound_to_a_variable"] > 0

    def test_two_candidates_are_still_refused(self):
        """The documented reason this is not a matcher. On the fraud
        ground-truth paper `Self-evaluation` matches both a `likert_item` and a
        `likert_composite`, and those differ in GRIM's granularity denominator,
        so choosing between them is choosing a verdict."""
        vs = [{"id": "v1", "name": "Self-evaluation (own attractiveness)",
               "family": "likert_item"},
              {"id": "v2", "name": "Self-evaluation index, pilot study",
               "family": "likert_composite"}]
        rows = V.binding_candidates(["Self-evaluation"], vs)
        assert rows[0]["status"] == "ambiguous"
        assert rows[0]["n_candidates"] == 2

    def test_exactly_one_candidate_is_the_only_case_bound(self):
        rows = V.binding_candidates(["Age (years) 1", "Male"], self.VARS)
        by = {r["row_label"]: r["status"] for r in rows}
        assert by["Age (years) 1"] == "bound"
        assert by["Male"] == "unmatched", (
            "a category LEVEL is not a variable, and nothing should pretend it "
            "relates to one")

    def test_the_auto_binding_is_reported(self, tmp_path):
        """A binding nobody can see is a binding nobody can check."""
        d = tmp_path / "10.9999--demo"
        d.mkdir()
        (d / "body.md").write_text("# Body\n\nnothing here\n", encoding="utf-8")
        reg = V.build_from_paper(d, variables=self.VARS)
        assert "auto_bound_rows" in reg
        assert reg["auto_bound_rows"]["n"] == 0
        assert "exactly one variable matches" in reg["auto_bound_rows"]["rule"]


class TestCoverageIsStratified:
    """One ratio over reported statistics AND deposited raw data is a story
    about how large a spreadsheet is, not about coverage.

    MEASURED 2026-08-20 over the nine registers: 16,256 of 19,085 values (85.2%)
    are supplement spreadsheet cells -- a participant's treatment-arm code, a
    per-subject score, a codebook legend. CAPTAIN read "1 checked of 6,029" and
    ESCAS "0 of 4,321". Stratified, the same runs read 1 of 27 and 0 of 69.

    Separated rather than dropped: raw data is exactly what
    `detect_raw_duplication` consumes, so hiding it would trade one wrong number
    for another.
    """

    @staticmethod
    def _reg(reported, raw):
        groups = []
        for i in range(reported):
            groups.append({"anchor": {"where": "table", "table": "Table 1"},
                           "applicable_tools": ["grim_check"],
                           "checks": [{"severity": "consistent"}] if i == 0 else []})
        for i in range(raw):
            groups.append({"anchor": {"where": "table",
                                      "table": "supp:CAPTAIN.xlsx-Sheet1"},
                           "applicable_tools": ["grim_check"], "checks": []})
        return {"groups": groups}

    def test_the_reported_denominator_excludes_raw_data(self):
        from metascience_agent.values import coverage

        c = coverage(self._reg(reported=27, raw=6002))
        assert c["n_table_groups"] == 6029
        assert c["reported"]["n_groups"] == 27
        assert c["raw_data"]["n_groups"] == 6002

    def test_the_reported_rate_is_not_diluted_by_the_spreadsheet(self):
        from metascience_agent.values import coverage

        c = coverage(self._reg(reported=27, raw=6002))
        assert c["reported"]["n_checked"] == 1
        assert c["reported"]["coverage"] == round(1 / 27, 4)

    def test_a_paper_with_no_supplement_is_unchanged(self):
        from metascience_agent.values import coverage

        c = coverage(self._reg(reported=40, raw=0))
        assert c["reported"]["n_groups"] == c["n_table_groups"] == 40
        assert c["raw_data"]["n_groups"] == 0

    def test_raw_data_is_reported_not_hidden(self):
        """`detect_raw_duplication` consumes it. Dropping it would trade one
        wrong number for another."""
        from metascience_agent.values import coverage

        c = coverage(self._reg(reported=5, raw=100))
        assert c["raw_data"]["n_groups"] == 100
        assert "detect_raw_duplication" in c["raw_data"]["note"]

    def test_the_exclusive_states_still_cover_everything(self):
        from metascience_agent.values import coverage

        c = coverage(self._reg(reported=27, raw=6002))
        assert c["states_are_exclusive"] is True


class TestTheJoinTiersItsArguments:
    """A call's numbers are not all printed in the same place.

    MEASURED 2026-08-20 over the nine registers of the eleven-paper run. The
    join read a seven-name whitelist and so filed 181 REAL VERDICTS -- 27
    `absence_of_evidence`, 22 `check_sd_or_se`, 19 `recalc_chi_squared` -- in a
    bucket labelled "nothing to join", because their value is spelled
    `reported_value` or `ci_low` rather than `sd`.

    The obvious fix, one flat whitelist of every printed argument, took joins
    from 262 DOWN to 143. `check_count_percent(count=42, percentage=33.6,
    n=125)` is the most common call in the archive and its `n` is printed in the
    COLUMN HEADER, so requiring it inside the cell's own quote broke the join
    for every one of them. Hence two tiers: what must be in the cell, and what
    merely narrows a tie.
    """

    def _reg(self, cells):
        return V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])

    def test_a_header_n_does_not_have_to_be_inside_the_cell(self):
        reg = self._reg([{"raw": "42 (33.6)", "row": 1, "row_label": "Male"}])
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_count_percent",
             "input": {"count": 42, "percentage": 33.6, "n": 125, "decimals": 1},
             "result": {"severity": "consistent"}}])
        assert reg["n_per_cell_checks_joined"] == 1

    def test_the_narrower_tier_breaks_a_tie_the_broader_one_cannot(self):
        """Two rows print the same estimate; only one prints this CI."""
        reg = self._reg([
            {"raw": "0.55 (0.18-0.91)", "row": 1, "row_label": "A"},
            {"raw": "0.55 (0.30-0.80)", "row": 2, "row_label": "B"}])
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_estimate_ci",
             "input": {"estimate": 0.55, "ci_low": 0.18, "ci_high": 0.91,
                       "null_value": 1, "decimals": 2},
             "result": {"severity": "consistent"}}])
        assert reg["n_per_cell_checks_joined"] == 1
        assert reg["n_per_cell_checks_ambiguous"] == 0

    def test_a_genuine_tie_is_still_refused(self):
        """Narrowing must not become guessing: identical cells stay ambiguous."""
        reg = self._reg([
            {"raw": "0.55 (0.18-0.91)", "row": 1, "row_label": "A"},
            {"raw": "0.55 (0.18-0.91)", "row": 2, "row_label": "B"}])
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_estimate_ci",
             "input": {"estimate": 0.55, "ci_low": 0.18, "ci_high": 0.91},
             "result": {"severity": "consistent"}}])
        assert reg["n_per_cell_checks_joined"] == 0
        assert reg["n_per_cell_checks_ambiguous"] == 1

    def test_a_parameter_is_not_treated_as_a_printed_value(self):
        """`decimals=2` and `null_value=1` are not numbers the paper printed, so
        requiring them in the quote would break every call that carries one."""
        reg = self._reg([{"raw": "6.58 (0.52)", "row": 1, "row_label": "A"}])
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__sprite_reconstruct",
             "input": {"mean": 6.58, "sd": 0.52, "n": 30, "decimals_mean": 2,
                       "scale_min": 1, "scale_max": 7, "num_samples": 1000},
             "result": {"severity": "consistent"}}])
        assert reg["n_per_cell_checks_joined"] == 1


class TestATwoSampleCheckBelongsToBothCells:
    """No single cell holds a two-arm call's six numbers, so the one-quote rule
    can never match one. 24 calls in the nine registers carry a 1/2 pair."""

    def _reg(self):
        cells = [{"raw": "6.6 (0.5)", "row": 1, "row_label": "Treatment"},
                 {"raw": "5.9 (0.6)", "row": 2, "row_label": "Control"}]
        return V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])

    def test_the_verdict_is_attached_to_both_arms(self):
        reg = self._reg()
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_effect_plausibility",
             "input": {"mean1": 6.6, "sd1": 0.5, "n1": 50,
                       "mean2": 5.9, "sd2": 0.6, "n2": 48, "reported_d": 2.4},
             "result": {"severity": "implausible"}}])
        attached = [g for g in reg["groups"] if g.get("checks")]
        assert len(attached) == 2, "the check read both cells"
        assert reg["n_per_cell_checks_joined"] == 1, "one call, counted once"
        assert reg["n_checks_attached_to_two_groups"] == 1
        assert all(c["joined_by"] == "argument values, both arms"
                   for g in attached for c in g["checks"])

    def test_one_arm_alone_is_not_half_a_comparison(self):
        """A call carrying only `mean1` is a one-armed call with an odd name.
        Treating it as half a pair would attach a verdict about a comparison to
        a cell that was never compared with anything."""
        reg = self._reg()
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__odd", "input": {"mean1": 6.6, "sd1": 0.5}}])
        assert reg["n_checks_attached_to_two_groups"] == 0

    def test_a_missing_arm_does_not_attach_the_other_one(self):
        """Arm two is not in this table. Attaching the verdict to arm one alone
        would show a comparison against a cell nobody can see."""
        reg = self._reg()
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_effect_plausibility",
             "input": {"mean1": 6.6, "sd1": 0.5, "mean2": 99.9, "sd2": 88.8},
             "result": {"severity": "implausible"}}])
        assert reg["n_per_cell_checks_joined"] == 0
        assert not any(g.get("checks") for g in reg["groups"])


class TestAnUnreadableResultDoesNotAbortTheJoin:
    """MEASURED 2026-08-20: raw `toolcalls.*.json` stores some results as a bare
    string, and `(call.get("result") or {}).get(...)` raised AttributeError on
    the first one. That does not lose one check -- it aborts the whole join and
    leaves every value in the paper showing no checks at all."""

    def _reg(self):
        cells = [{"raw": "6.58 (0.52)", "row": 1, "row_label": "A"}]
        return V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])

    def test_a_string_result_still_joins(self):
        reg = self._reg()
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__grimmer_check",
             "input": {"mean": 6.58, "sd": 0.52}, "result": "could not parse"}])
        assert reg["n_per_cell_checks_joined"] == 1

    def test_an_unknown_severity_is_not_reported_as_a_failed_check(self):
        """`passed: False` for a severity we could not read is absence rendered
        as knowledge. The viewer already renders an unknown severity as `--`."""
        reg = self._reg()
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__grimmer_check",
             "input": {"mean": 6.58, "sd": 0.52}, "result": "could not parse"}])
        check = reg["groups"][0]["checks"][0]
        assert check["severity"] is None
        assert check["passed"] is None, "unknown is not failed"


class TestTheDenominatorThatWouldMakeItRight:
    """MEASURED 2026-08-20 on the eleven-paper run: of ten cells flagged
    `suspicious` by a count/percent check, NINE had an implied denominator below
    the `n` the check used. That is a baseline table where each variable has its
    own denominator because some participants are missing that measurement --
    not an error in the paper. A false accusation against an honest paper is the
    worst thing this toolkit can produce, and here it was arriving at scale in
    the check that fires most often."""

    def test_it_rounds_the_way_a_journal_rounds(self):
        """`round(31.25, 1)` is 31.2 in Python -- bankers' rounding, half to
        even. Journals round half up, so the paper prints 31.3. The built-in
        would make us disagree with a correctly rounded number."""
        assert V._round_half_up(31.25, 1) == 31.3
        assert V._round_half_up(61.5959, 1) == 61.6
        assert round(31.25, 1) == 31.2, "the trap this exists to avoid"

    def test_the_verbatim_false_positive_from_the_run(self):
        """The column header reads `n = 16`; the check was given 17. 5/16 is
        31.3, exactly what the paper printed, and the flag was ours."""
        got = V.explaining_denominator(count=5, percentage=31.3, n=17, decimals=1)
        assert got["reproduces_printed_value"] is True
        assert got["denominator"] == 16 and got["n_missing"] == 1

    def test_one_missing_observation_explains_a_flagged_cell(self):
        """332/540 is 61.5; the paper printed 61.6; 332/539 is 61.6 exactly."""
        got = V.explaining_denominator(count=332, percentage=61.6, n=540, decimals=1)
        assert got["denominator"] == 539 and got["n_missing"] == 1

    def test_a_discrepancy_no_denominator_explains_is_reported_as_such(self):
        """11/60 is 18.3 and the paper printed 18.2. Every smaller denominator
        gives a LARGER percentage, so nothing at or below n reproduces it. This
        flag survives, and it should."""
        got = V.explaining_denominator(count=11, percentage=18.2, n=60, decimals=1)
        assert got["reproduces_printed_value"] is False
        assert got["denominator"] is None

    def test_nothing_is_suppressed_only_annotated(self):
        """Whether one missing observation is plausible is a judgement about the
        paper. This file records the number and does not make that judgement."""
        cells = [{"raw": "332 (61.6%)", "row": 1, "row_label": "Hypertension"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_count_percent",
             "input": {"count": 332, "percentage": 61.6, "n": 540, "decimals": 1},
             "result": {"severity": "suspicious"}}])
        check = reg["groups"][0]["checks"][0]
        assert check["severity"] == "suspicious", "the verdict is not overturned"
        assert check["denominator_audit"]["denominator"] == 539

    def test_a_check_with_no_denominator_gets_no_audit(self):
        cells = [{"raw": "6.58 (0.52)", "row": 1, "row_label": "A"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__grimmer_check",
             "input": {"mean": 6.58, "sd": 0.52}, "result": {"severity": "consistent"}}])
        assert "denominator_audit" not in reg["groups"][0]["checks"][0]

    def test_a_count_larger_than_n_is_refused_not_answered(self):
        assert V.explaining_denominator(count=50, percentage=10.0, n=40) is None


class TestWhyAValueIsSilent:
    """A silent group has an applicable tool, no verdict and no recorded
    refusal. MEASURED over the nine registers: 125 of 141 were never checked --
    a fact about the RUN -- while 16 had a verdict computed that could not be
    attached, because the same `32 (25.4)` is printed in three different rows.
    One number for both invites fixing the wrong one."""

    def _two_identical_cells(self):
        cells = [{"raw": "32 (25.4)", "row": 1, "row_label": "Atrial fibrillation"},
                 {"raw": "32 (25.4)", "row": 2, "row_label": "Previous aspirin"}]
        return V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])

    def test_a_refused_guess_is_not_reported_as_nobody_looking(self):
        reg = self._two_identical_cells()
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_count_percent",
             "input": {"count": 32, "percentage": 25.4, "n": 126},
             "result": {"severity": "consistent"}}])
        assert reg["n_per_cell_checks_ambiguous"] == 1
        stamped = [g for g in reg["groups"] if g.get("verdicts_not_attached")]
        assert len(stamped) == 2, "both contenders carry the stamp"

    def test_coverage_names_the_two_reasons_apart(self):
        reg = self._two_identical_cells()
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_count_percent",
             "input": {"count": 32, "percentage": 25.4, "n": 126},
             "result": {"severity": "consistent"}}])
        why = V.coverage(reg)["silent_because"]
        assert sum(why.values()) == V.coverage(reg)["n_silent"]
        assert why["a verdict was computed and could not be attached to one cell"] >= 1


class TestTheStatedDenominator:
    """A column header often says what it divided by.

    THIS TEST EXISTS BECAUSE THE REGEX WAS A BACKSPACE. The pattern reached the
    file as `\\x08[nN]...` instead of `\\b[nN]...` -- it parsed, the suite stayed
    green, and `header_confirms_denominator` would simply never have appeared on
    any register. A field that silently never fires is indistinguishable from a
    fact that is never true, which is the failure this whole file is about.
    """

    def test_it_reads_the_forms_that_actually_appear(self):
        assert V._stated_n("Cerebrolysin , n = 16")["n"] == 16
        assert V._stated_n("Placebo (N = 540)")["n"] == 540
        assert V._stated_n("Cerebrolysin, n=104")["n"] == 104
        assert V._stated_n("Total (N = 1,070)")["n"] == 1070

    def test_the_innermost_level_of_a_stacked_header_governs_the_cell(self):
        """VERBATIM from the corpus. 318 describes the pair of columns grouped
        under it; 117 is what THIS column's numbers were divided by. Reading the
        outermost made every count/percent cell on that paper appear to need a
        denominator 120 to 204 below the stated n, which reads like a fabricated
        table. Against 117 the gaps are 1 to 6 -- an ordinary missing
        measurement. Same cells, same arithmetic, opposite impression."""
        got = V._stated_n("PP Population, n = 318 | Cerebrolysin , n = 117")
        assert got == {"n": 117, "level": "column"}

    def test_a_group_level_n_is_reported_as_a_group_level_n(self):
        """The p-value column states no n of its own. The outer figure is true
        and is not this column's, so it is returned LABELLED rather than
        silently promoted to the column's denominator."""
        got = V._stated_n("PP Population, n = 318 | p -Value")
        assert got == {"n": 318, "level": "group"}

    def test_a_single_level_header_is_a_column_level_n(self):
        assert V._stated_n("Placebo (N = 540)")["level"] == "column"

    def test_a_header_that_states_nothing_says_so(self):
        assert V._stated_n("OR (95% CI)") is None
        assert V._stated_n("Male sex, number (%)") is None
        assert V._stated_n(None) is None

    def test_the_word_boundary_is_real(self):
        """Without it, the `n` inside a word would match."""
        assert V._stated_n("Column n = 12")["n"] == 12
        assert V._stated_n("mean = 12") is None

    def test_the_header_confirming_the_denominator_is_recorded(self):
        """VERBATIM from the run: the header states 16, the check was given 17,
        and 5/16 is the 31.3 the paper printed."""
        cells = [{"raw": "5 (31.3)", "row": 1, "row_label": "Undetermined"}]
        reg = V.build_register(tables=[{"name": "t1", "parsed": parse_cells(cells),
                                        "cells": cells}])
        reg["groups"][0].setdefault("anchor", {})["col_label"] = "Cerebrolysin , n = 16"
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_count_percent",
             "input": {"count": 5, "percentage": 31.3, "n": 17, "decimals": 1},
             "result": {"severity": "suspicious"}}])
        audit = reg["groups"][0]["checks"][0]["denominator_audit"]
        assert audit["column_header_states_n"] == 16
        assert audit["header_confirms_denominator"] is True
        assert audit["denominator"] == 16 and audit["n_missing"] == 1


class TestDepositedDataIsNotARivalForAReportedCell:
    """MEASURED 2026-08-20: 37 of 209 groups stamped "a verdict was computed
    about this and could not be attached" were spreadsheet cells that merely
    held the same integer as a reported statistic."""

    def _mixed(self):
        cells = [{"raw": "42 (33.6)", "row": 1, "row_label": "Male"},
                 {"raw": "42 (33.6)", "row": 2, "row_label": "subject 7"}]
        reg = V.build_register(tables=[{"name": "t1", "parsed": parse_cells(cells),
                                        "cells": cells}])
        reg["groups"][1].setdefault("anchor", {})["table"] = "supp:data.xlsx:Sheet1"
        return reg

    def test_the_reported_cell_wins_a_contest_against_a_data_cell(self):
        reg = self._mixed()
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_count_percent",
             "input": {"count": 42, "percentage": 33.6, "n": 125},
             "result": {"severity": "consistent"}}])
        assert reg["n_per_cell_checks_joined"] == 1
        assert reg["groups"][0].get("checks"), "attached to the reported cell"
        assert not reg["groups"][1].get("checks")

    def test_a_check_aimed_at_a_supplement_still_joins_to_it(self):
        """If EVERY candidate is deposited data, none is discarded."""
        cells = [{"raw": "42 (33.6)", "row": 1, "row_label": "Male"}]
        reg = V.build_register(tables=[{"name": "t1", "parsed": parse_cells(cells),
                                        "cells": cells}])
        reg["groups"][0].setdefault("anchor", {})["table"] = "supp:tableS1.xlsx"
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_count_percent",
             "input": {"count": 42, "percentage": 33.6, "n": 125},
             "result": {"severity": "consistent"}}])
        assert reg["n_per_cell_checks_joined"] == 1

    def test_two_data_cells_are_still_refused_not_picked(self):
        reg = self._mixed()
        reg["groups"][0].setdefault("anchor", {})["table"] = "supp:data.xlsx:Sheet1"
        V.attach_calls_by_value(reg, [
            {"id": "c1", "name": "mcp__x__check_count_percent",
             "input": {"count": 42, "percentage": 33.6, "n": 125},
             "result": {"severity": "consistent"}}])
        assert reg["n_per_cell_checks_ambiguous"] == 1


class TestTheSupplementAnchorRoundTrips:
    """`supplement_anchor` writes the fact and `is_deposited_raw_data` reads it.

    They are an encode/decode pair, and an encode/decode pair that nothing pins
    together is how the conservation law and the join came to disagree about
    what a check call is -- one wrote `tool` and the other read `name`, and the
    filter matched nothing on all 819 real calls while the suite stayed green.
    """

    def test_what_the_builder_writes_the_predicate_recognises(self):
        for f, label in (("CAPTAIN_AnalysisData.xlsx", "Sheet1"),
                         ("data.csv", "table S3"),
                         (None, "?")):
            name = V.supplement_anchor(f, label)
            assert V.is_deposited_raw_data({"anchor": {"table": name}}), name

    def test_an_article_table_is_not_deposited_data(self):
        for name in ("Table 4", "t1", "Table 1 :: continued", ""):
            assert not V.is_deposited_raw_data({"anchor": {"table": name}}), name

    def test_a_group_with_no_anchor_is_not_deposited_data(self):
        assert not V.is_deposited_raw_data({})
        assert not V.is_deposited_raw_data({"anchor": None})

    def test_the_slugged_spelling_is_recognised_too(self):
        """`_slug` turns the colon into a dash, so an anchor that has been
        through it reads `supp-file-...` and must still be recognised."""
        assert V.is_deposited_raw_data({"anchor": {"table": "supp-data-xlsx-Sheet1"}})

    def test_provenance_is_not_folded_into_the_role_vocabulary(self):
        """A deposited mean is still a mean. If `raw_data` ever becomes a
        role_class, `descriptive` and `deposited` become alternatives when they
        are independent facts, and every consumer keying off role_class starts
        answering a different question than it asks."""
        assert "raw_data" not in V.ROLE_CLASSES
        assert V.role_class("mean") == "descriptive"


class TestTheGapIsTheEvidence:
    """MEASURED against arbitrary values, 1,500 random percentages per sample
    size. Some denominator at or below `n` reproduces an ARBITRARY percentage
    1.1% of the time at n=17 and **22.4%** of the time at n=540 -- the bigger
    the sample, the more denominators there are to land on by luck. Constrained
    to a handful of observations it collapses below 1% everywhere. So the SIZE
    of the gap is not a footnote to the verdict; it is the evidence."""

    def test_a_near_miss_and_a_far_one_are_told_apart(self):
        near = V.explaining_denominator(332, 61.6, 540, 1)
        assert near["n_missing"] == 1 and near["share_below"] < 0.01

    def test_the_share_is_reported_not_just_the_count(self):
        """`n_missing = 201` against 318 is not 201 missing people. It is a
        stacked header stating a study total over a cell belonging to one arm --
        201 + 117 = 318 exactly. The absolute count reads the same for both."""
        far = V.explaining_denominator(34, 17.2, 318, 1)
        assert far["reproduces_printed_value"] is True
        assert far["n_missing"] > 10
        assert far["share_below"] > 0.3, "a reader must be able to see this is far"

    def test_an_unexplained_cell_carries_no_share(self):
        got = V.explaining_denominator(11, 18.2, 60, 1)
        assert got["reproduces_printed_value"] is False
        assert got["share_below"] is None and got["n_missing"] is None

    def test_the_measured_false_explanation_rate_is_recorded_where_it_is_used(self):
        """The rate is what makes a small gap conclusive and a large one weak.
        If it ever stops being written down, the audit becomes an assertion."""
        import inspect
        src = inspect.getsource(V.explaining_denominator)
        assert "22.4%" in src and "k<=1" in src, (
            "the measured false-explanation rate must stay in the docstring")
        assert "never be read as" in src


class TestOneParserForHeaderSampleSizes:
    """`values._stated_n` used to carry its own regex, a weaker copy of
    `dispatch._N_IN_LABEL`: it could not read `n ¼ 59`, the OCR corruption
    of `n = 59` that a real extractor produces. Two spellings of one question is
    the defect this file keeps finding in other people's code, and it was the
    FOURTH instance found in a single day."""

    def test_the_ocr_corruption_of_the_equals_sign_is_read(self):
        got = V._stated_n("Cerebrolysin (n ¼ 59)")
        assert got == {"n": 59, "level": "column"}

    def test_both_readers_agree_on_a_stacked_header(self):
        from metascience_agent.dispatch import _n_in_labels
        label = "PP Population, n = 318 | Cerebrolysin , n = 117"
        assert V._stated_n(label)["n"] == 117
        assert _n_in_labels({"col_label": label})[0] == ("col_label", 117), (
            "the dispatcher recommends an n to pass; on a stacked header that "
            "used to be the grouping total, which is also the LARGER number -- "
            "and this module's own refusal text warns that a check accuses "
            "when n is too large")

    def test_the_refusal_names_the_wider_groupings_too(self):
        from metascience_agent.dispatch import _refusal_reason
        from metascience_agent.registry import BY_NAME
        reason = _refusal_reason(
            BY_NAME["grim_percentage"], None,
            {"col_label": "PP Population, n = 318 | Cerebrolysin , n = 117"})
        assert "Pass n=117" in reason
        assert "318" in reason and "wider groupings" in reason, (
            "a reader choosing a denominator should see the alternatives, not "
            "be handed one figure as though it were the only candidate")


class TestTwoListsThatLookAlikeAreNotOneList:
    """`values._NOT_A_CHECK` and `registry.NOT_A_TECHNIQUE` overlap and answer
    different questions. This test exists so nobody merges them."""

    def test_check_table_is_not_a_nameable_technique(self):
        """A finding names the specific check that fired, not the batch runner
        that ran it."""
        from metascience_agent.registry import NOT_A_TECHNIQUE, technique_names
        assert "check_table" in NOT_A_TECHNIQUE
        assert "check_table" not in technique_names()

    def test_but_a_check_table_CALL_did_compute_verdicts(self):
        """Merging the two lists would drop every `check_table` call out of the
        conservation law's denominator while its joined and unmatched counts
        stayed in the sum -- a NEGATIVE residual, the law reporting that two
        counters describe the same call when really one end stopped counting."""
        assert V.is_check_call({"tool": "mcp__x__check_table"}) is True

    def test_plumbing_is_neither(self):
        from metascience_agent.registry import NOT_A_TECHNIQUE
        for name in ("extract_pdf", "get_table", "parse_table"):
            assert name in NOT_A_TECHNIQUE
            assert V.is_check_call({"tool": f"mcp__x__{name}"}) is False


class TestEveryRegisteredCheckCanBeNamedAsItsOwnTechnique:
    """MEASURED 2026-08-20: 32 of 58 registered tools could not be named as a
    `technique`, because the enum was a hand-maintained paraphrase of the
    registry -- `count_percent` for `check_count_percent`, `grim` for
    `grim_check`, `sprite` for `sprite_reconstruct`.

    The field's own description says "Use the registry name of the tool that
    actually computed it". A model that follows that instruction is rejected by
    the validator, and the rejection is not partial: stage 1 emits ONE
    structured output, so one unacceptable string discards the whole statistical
    anatomy. It cost the entire stage-1 output on 2 of the 11 papers in the
    cerebrolysin run -- no findings, no value register -- for spelling a tool's
    name the way the registry spells it.
    """

    def _enum(self):
        from metascience_agent.core import prompts
        return set(prompts.findings_schema_v2()["properties"]["findings"]["items"]
                   ["properties"]["technique"]["enum"])

    def test_the_verbatim_rejections_from_the_run_are_now_accepted(self):
        enum = self._enum()
        for name in ("check_count_percent", "detect_duplication",
                     "check_summation_batch", "required_n"):
            assert name in enum, name

    def test_plumbing_is_still_not_a_technique(self):
        enum = self._enum()
        for name in ("extract_pdf", "get_table", "parse_cells_typed"):
            assert name not in enum, name


class TestArithmeticInvariants:
    """One rule of this kind already existed -- an interval whose bounds are the
    wrong way round -- and it is what caught the Lancet middle-dot corruption.
    It caught it in the TEST SUITE, days after the run that produced it, and
    only because two recovered papers happened to bring 158 middle-dot decimals
    into a corpus that until then had none. Every run before that was green and
    wrong. These now run on every register build."""

    def _reg(self, values, deposited=False):
        reg = {"groups": [{"id": "g1", "quote": "x", "values": [
            {"role": k, "value": v} for k, v in values.items()]}]}
        if deposited:
            reg["groups"][0]["anchor"] = {"table": "supp:data.xlsx:Sheet1"}
        return reg

    def test_an_inverted_interval_is_caught(self):
        got = V.check_invariants(self._reg({"ci_low": 716.0, "ci_high": -2.0}))
        assert got["reported"]["by_rule"]["ci_low_above_ci_high"] == 1

    def test_an_estimate_outside_its_own_interval_is_caught(self):
        """VERBATIM from a 2024 paper: d = -0.79 with a 95% CI of
        (0.416, 1.16), whose midpoint is 0.788."""
        got = V.check_invariants(
            self._reg({"estimate": -0.79, "ci_low": 0.416, "ci_high": 1.16}))
        assert got["reported"]["by_rule"]["estimate_outside_its_own_ci"] == 1

    def test_a_sample_size_that_is_not_a_whole_number_is_caught(self):
        """VERBATIM: `NNT: 4.2` read as a sample size. `n` gates GRIM,
        GRIMMER and count-percent."""
        got = V.check_invariants(self._reg({"n": 4.2}))
        assert got["reported"]["by_rule"]["n_not_a_whole_number"] == 1

    def test_clean_numbers_violate_nothing(self):
        got = V.check_invariants(
            self._reg({"estimate": 0.548, "ci_low": 0.182, "ci_high": 0.912,
                       "count": 42, "n": 125, "percentage": 33.6, "p": 0.03,
                       "sd": 1.2}))
        assert got["reported"]["by_rule"] == {}
        assert got["reported"]["n_rules_evaluated"] > 0, (
            "a register that evaluated NOTHING must not look like one that "
            "evaluated everything and found nothing wrong")

    def test_the_two_strata_are_reported_apart(self):
        """298 negative 'counts' in one paper are deposited change scores, not
        a finding. Mixed into one number they would bury the two real hits."""
        got = V.check_invariants(self._reg({"count": -325.0}, deposited=True))
        assert got["deposited"]["by_rule"]["negative_count"] == 1
        assert got["reported"]["by_rule"] == {}

    def test_a_rule_that_cannot_be_evaluated_is_not_a_pass(self):
        got = V.check_invariants(self._reg({"ci_low": 0.1}))
        assert "ci_low_above_ci_high" not in got["reported"]["by_rule"]
        assert got["reported"]["n_rules_evaluated"] == 0, (
            "one bound alone cannot test bound ordering, and must not be "
            "counted as having tested it")

    def test_examples_are_capped_but_counts_are_exact(self):
        reg = {"groups": [{"id": f"g{i}", "quote": "-325", "values": [
            {"role": "count", "value": -325.0}]} for i in range(40)]}
        got = V.check_invariants(reg)["reported"]
        assert got["by_rule"]["negative_count"] == 40
        assert len(got["examples"]["negative_count"]) == V._MAX_INVARIANT_EXAMPLES


class TestTheArithmeticNobodyRan:
    """MEASURED over the eleven-paper run: 125 checkable values were never
    checked, and **all 125 had `dispatch_considered = True`** -- dispatch
    offered them and the model did not call. Meanwhile the checks the model DID
    run on this shape produced 15 false suspicions out of 18, every one because
    it chose the wrong denominator.

    Where the cell's own column header states its `n`, neither problem needs a
    model: 149 of 158 such cells reproduce their printed percentage from the
    stated n exactly.
    """

    def _reg(self, raw, col_label, deposited=False, checks=None):
        # `n (%)` IN THE ROW LABEL IS WHAT TYPES THE CELL. Without the format
        # annotation `32 (80.0)` is `ambiguous` with a single `unknown` value,
        # and the roles this check reads do not exist. Real baseline tables
        # carry it -- `Male sex, number (%)` -- which is why the check finds
        # 158 such cells in the corpus and none in a fixture that omits it.
        cells = [{"raw": raw, "row": 1, "row_label": "Male sex, n (%)"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        g = reg["groups"][0]
        g.setdefault("anchor", {})["col_label"] = col_label
        if deposited:
            g["anchor"]["table"] = "supp:data.xlsx:Sheet1"
        if checks:
            g["checks"] = checks
        return reg

    def test_a_cell_whose_header_states_its_n_is_checked_with_no_model(self):
        reg = self._reg("32 (80.0)", "Total, n = 40")
        got = V.check_stated_denominators(reg)
        assert got["n_attached"] == 1
        check = reg["groups"][0]["checks"][0]
        assert check["severity"] == "consistent", "32/40 is exactly 80.0"
        assert check["ran_without_a_model"] is True
        assert check["joined_by"] == "the column header's own n"

    def test_a_grouping_level_n_is_declined_not_borrowed(self):
        """`PP Population, n = 318` sits above arms of 201 and 117. It is true
        and it is not this column's denominator. That single distinction is the
        difference between 149 exact reproductions and 86."""
        reg = self._reg("32 (80.0)", "PP Population, n = 318 | p -Value")
        got = V.check_stated_denominators(reg)
        assert got["n_attached"] == 0
        assert got["skipped_because"][
            "the only n in the header covers a grouping of columns"] == 1

    def test_a_near_miss_is_our_pairing_not_the_papers_arithmetic(self):
        """18/117 is 15.4 and the paper prints 15.8; 18/114 is 15.8 exactly.
        A variable with missing data has its own denominator, which is the
        commonest convention in a baseline table -- so this is `indeterminate`
        with the denominator named, never `suspicious`."""
        reg = self._reg("18 (15.8)", "Cerebrolysin, n = 117")
        V.check_stated_denominators(reg)
        check = reg["groups"][0]["checks"][0]
        assert check["severity"] == "indeterminate"
        assert check["result"]["downgraded_from"] == "suspicious"
        assert check["denominator_audit"]["denominator"] == 114
        assert "missing data" in check["result"]["downgraded_because"]

    def test_a_mismatch_no_denominator_explains_still_stands(self):
        """11/60 is 18.3 and the paper prints 18.2. Every smaller denominator
        gives a LARGER percentage, so nothing at or below n reproduces it."""
        reg = self._reg("11 (18.2)", "Arm A, n = 60")
        V.check_stated_denominators(reg)
        check = reg["groups"][0]["checks"][0]
        assert check["severity"] == "suspicious"
        assert check["denominator_audit"]["reproduces_printed_value"] is False

    def test_an_explanation_far_below_n_does_not_excuse_anything(self):
        """VERBATIM from the corpus, and it is why the absolute bound is 3:

            | Characteristics            | CblG ( n = 50) | Ctrl ( n = 50) |
            | Atrial fibrillation, n (%) | 19 (48)        | 22 (44)        |

        `22/50 = 44` exactly, so 50 IS that row's denominator, while
        `19/50 = 38` against a printed 48. A denominator of 40 reproduces 48 --
        and a first version of this rule downgraded the cell on that basis,
        which is a FALSE CLEAR: 20% of an arm missing one variable does not
        happen unremarked, and the paper's own sibling cell rules it out.
        """
        reg = self._reg("19 (48)", "CblG ( n = 50)")
        V.check_stated_denominators(reg)
        check = reg["groups"][0]["checks"][0]
        assert check["severity"] == "suspicious", (
            "a gap of 10 in a sample of 50 is not missing data")
        assert check["denominator_audit"]["n_missing"] == 10

    def test_one_person_missing_is_ordinary_at_any_sample_size(self):
        """A relative bound alone would refuse a gap of ONE in a sample of 17,
        which is one person and the commonest thing in a baseline table."""
        reg = self._reg("3 (18.8)", "Control, n = 17")
        V.check_stated_denominators(reg)
        assert reg["groups"][0]["checks"][0]["severity"] == "indeterminate"

    def test_a_small_share_is_ordinary_at_a_large_sample_size(self):
        """And an absolute bound alone would refuse six people out of 201."""
        reg = self._reg("44 (22.6)", "Arm A, n = 201")
        V.check_stated_denominators(reg)
        assert reg["groups"][0]["checks"][0]["severity"] == "indeterminate"

    def test_deposited_data_is_not_checked(self):
        reg = self._reg("32 (80.0)", "Total, n = 40", deposited=True)
        assert V.check_stated_denominators(reg)["n_attached"] == 0

    def test_a_cell_the_model_already_checked_is_not_checked_twice(self):
        reg = self._reg("32 (80.0)", "Total, n = 40",
                        checks=[{"tool": "check_count_percent", "severity": "consistent"}])
        got = V.check_stated_denominators(reg)
        assert got["n_attached"] == 0
        assert got["skipped_because"]["already checked by the model"] == 1

    def test_a_header_that_states_no_n_is_skipped_with_a_reason(self):
        reg = self._reg("32 (80.0)", "Cerebrolysin")
        got = V.check_stated_denominators(reg)
        assert got["n_attached"] == 0
        assert got["skipped_because"]["the column header states no n"] == 1
        assert got["n_ran"] == 0, "a skip is not a run"


class TestWhyNoToolAppliesIsTwoReasons:
    """`n_no_applicable_tool` is the largest bucket in the register -- 864 of
    the 1,432 values the papers themselves printed -- and the name reads as
    "nothing could ever check this". For most of them that is false.

    MEASURED 2026-08-20: 242 are `mean_sd`, the shape GRIM, GRIMMER and SPRITE
    consume, and `DISPATCH[("mean_sd", "unknown")]` is EMPTY **on purpose** --
    those checks are valid only on integer-valued data and running them on a
    continuous variable manufactures accusations. The tool is not inapplicable;
    its precondition is UNDECLARED.

    "This value is unreachable" and "declare the variable and it becomes
    checkable" are opposite instructions to whoever reads the coverage figure.
    """

    def _reg(self, kind_label, raw):
        cells = [{"raw": raw, "row": 1, "row_label": kind_label}]
        return V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])

    def test_an_undeclared_mean_sd_is_not_reported_as_uncheckable(self):
        cov = V.coverage(self._reg("Age, mean (SD)", "47.4 (17.3)"))
        why = cov["no_applicable_tool_because"]
        declared = [k for k in why if "nothing declared the variable" in k]
        assert declared and why[declared[0]] == 1, (
            "GRIM consumes mean_sd; what is missing is the variable's type")

    def test_the_two_reasons_sum_to_the_bucket(self):
        cov = V.coverage(self._reg("Age, mean (SD)", "47.4 (17.3)"))
        assert sum(cov["no_applicable_tool_because"].values()) == \
            cov["n_no_applicable_tool"]


class TestSquareBracketsAreTheSameAnnotation:
    """`n [%]` is standard house style exactly where the outer parentheses are
    already taken -- `Sex (male, n [%])`. Requiring literal parens meant a table
    that avoids nesting got no count/percent typing at all."""

    def _kind(self, label):
        cells = [{"raw": "28 (56)", "row": 1, "row_label": label}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        return reg["groups"][0].get("kind")

    def test_the_bracket_form_types_like_the_paren_form(self):
        assert self._kind("Sex (male, n [%])*") == "n_percent"
        assert self._kind("Male sex, n (%)") == "n_percent"

    def test_a_mean_sd_label_is_unaffected(self):
        assert self._kind("Age, mean (SD)") == "mean_sd"

    def test_an_unannotated_label_still_refuses(self):
        """`28 (56)` alone could be mean (SD), n (%) or estimate (CI). Without a
        label saying which, refusing is correct -- this fix widens the
        annotation, it does not start guessing."""
        assert self._kind("Myocardial infarction") == "ambiguous"


class TestACellIsDecomposedIntoTheValuesItPrints:
    """Greg, 2026-08-20: "splitting the column into two columns, and
    automatically associating the two values (n and percent) in the register of
    values ... another example would be tables with cells containing ranges,
    like '37-42'."

    MEASURED before the change, over 1,963 article table cells in the eleven
    papers: **305 reported cells held fewer values than the numbers they print**,
    losing 339 printed numbers -- silently, because the register still showed a
    value. `_UNTYPED_FALLBACK` was one role reading one attribute, so `3 (1.4)`
    became a single value of 3.0.

    DECOMPOSITION IS CERTAIN WHERE ROLE ASSIGNMENT IS NOT, and the two were
    conflated. `3 (1.4)` definitely contains two numbers; what is uncertain is
    only whether they are count/percent, mean/SD or estimate/CI. Uncertainty
    about the roles is not grounds to discard the numbers.
    """

    def _group(self, raw, label="Myocardial infarction"):
        cells = [{"raw": raw, "row": 1, "row_label": label}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        return reg["groups"][0] if reg["groups"] else None

    def test_an_untyped_cell_keeps_every_number_it_prints(self):
        g = self._group("3 (1.4)")
        assert [(v["role"], v["value"]) for v in g["values"]] == [
            ("unknown", 3.0), ("unknown", 1.4)]

    def test_each_component_gets_its_own_id(self):
        """Without a component index both `unknown`s key to
        `val:{anchor}:unknown` and the second overwrites the first -- the very
        loss decomposition exists to stop, one layer down."""
        g = self._group("3 (1.4)")
        assert len({v["id"] for v in g["values"]}) == 2

    def test_the_component_position_is_recorded(self):
        g = self._group("3 (1.4)")
        assert [v["component"] for v in g["values"]] == [0, 1]
        assert all(v["n_components"] == 2 for v in g["values"])

    def test_a_typed_cell_is_untouched(self):
        """Decomposition is the fallback for cells the typer could not name; it
        must not disturb the ones it could."""
        g = self._group("47.4 (17.3)", label="Age, mean (SD)")
        assert [(v["role"], v["value"]) for v in g["values"]] == [
            ("mean", 47.4), ("sd", 17.3)]
        assert all(v.get("component") is None for v in g["values"])

    def test_the_printed_relationship_is_recorded_not_guessed(self):
        """The form says how the numbers relate -- structure the paper set,
        certain even when the roles are not. `unclassified` is a real answer."""
        assert self._group("3 (1.4)")["form"] == "value_with_parenthetical"
        assert self._group("10 (6–14)", "NIHSS (M, IQR)")["form"] == \
            "value_with_interval"
        assert V.cell_form("37-42") == "range"
        assert V.cell_form("37 to 42") == "range"
        assert V.cell_form("74 / 55") == "pair_over_slash"
        assert V.cell_form("12.3") == "single"
        assert V.cell_form("N/A") == "no_number"
        assert V.cell_form("5.2 +1.1/−0.8") == "unclassified", (
            "a shape we have not surveyed is named unclassified, not guessed")

    def test_a_middle_dot_component_is_read_as_one_number(self):
        g = self._group("33 (55·9)")
        assert [v["value"] for v in g["values"]] == [33.0, 55.9]

    def test_a_cell_with_no_numbers_is_still_not_a_value(self):
        assert self._group("N/A") is None


class TestAThousandsGroupCannotStartWithZero:
    """The worst class a 196-paper cell survey found on 2026-08-20: cells that
    are SILENTLY WRONG rather than missing.

        "0,001"          ->  count 1.0            a p-value read as 1
        "0,056"          ->  count 56.0
        "0,561"          ->  count 561.0
        "0,932 ± 0,011"  ->  mean 932.0, sd 11.0  and this goes to GRIM

    One Russian paper in the corpus carries 58 such numbers -- Mann-Whitney
    statistics between 0 and 1, every one read as a three-digit integer.

    `74,874` really is undecidable from the cell alone: 74.874 in a Russian
    journal, seventy-four thousand in an American one, and both conventions are
    attested in this corpus. But no convention writes a thousands group starting
    with zero, so THIS much needs no document context at all.
    """

    def _cell(self, raw):
        from metascience_agent.tools.celltypes import parse_cell
        return parse_cell(raw)

    def test_the_p_value_read_as_one(self):
        assert self._cell("0,001").value == 0.001

    def test_a_mean_read_as_a_thousandfold_integer(self):
        c = self._cell("0,932 ± 0,011")
        assert (c.value, c.sd) == (0.932, 0.011)

    def test_the_printed_precision_survives(self):
        """`0,561` is printed to three decimals, and GRIM's granularity is a
        function of that count -- reading it as 561 loses the precision as well
        as the value."""
        assert V._num_and_decimals("0,561") == (0.561, 3)

    def test_a_genuine_thousands_group_is_untouched(self):
        assert self._cell("12,345").value == 12345.0
        assert self._cell("1,234.56").value == 1234.56

    def test_the_ambiguous_case_is_deliberately_left_alone(self):
        """`74,874` needs the document's convention, and guessing it is what
        produced the four wrong readings above. Deciding this belongs to
        document-level inference, not to a per-cell rule."""
        assert self._cell("74,874").value == 74874.0

    def test_both_readers_apply_the_same_rule(self):
        """`values._num_and_decimals` reads the rule from the one place it is
        defined rather than carrying a second copy -- the defect this codebase
        found in seven separate number readers today."""
        from metascience_agent.tools.celltypes import decimal_comma_repair
        assert decimal_comma_repair("0,561") == "0.561"
        assert decimal_comma_repair("74,874") == "74,874"
        assert V._num_and_decimals("0,001")[0] == self._cell("0,001").value


class TestTheDocumentDecidesItsOwnSeparator:
    """`74,874` is 74.874 in a Russian journal and seventy-four thousand in an
    American one, and BOTH conventions are attested in this corpus -- so no
    per-cell rule can decide it. Guessing thousands is what read a mean of 0.932
    as 932 and sent it to GRIM.

    What CAN decide it is the rest of the paper: a single `0,nnn` anywhere is a
    comma no thousands reading explains. MEASURED over the 309-paper corpus, 27
    papers' table cells carry such a witness -- between 14 and 204 each -- and
    196 ambiguous cells sit inside them. Every paper having BOTH a witness and
    an ambiguous comma has ZERO point-decimals.
    """

    def _infer(self, texts):
        from metascience_agent.tools.celltypes import infer_decimal_convention
        return infer_decimal_convention(texts)

    def test_witnesses_decide_a_comma_document(self):
        got = self._infer(["0,561", "0,7118", "0,001", "74,874"])
        assert got["separator"] == "comma"
        assert got["n_witnesses"] == 3 and got["n_ambiguous"] == 1

    def test_no_witness_means_no_verdict_not_a_guess(self):
        """An English table keeps its thousands groups, because nothing in it
        witnesses otherwise."""
        got = self._infer(["84,299", "12,345", "1.5", "0.05"])
        assert got["separator"] == "unknown"
        assert "left as they were rather than guessed" in got["why"]

    def test_citation_lists_do_not_witness_anything(self):
        """`[7,8]` and `[10,11]` are commas between digits in every English
        paper ever written. An earlier version of this rule -- fewer than three
        digits means decimal -- would have read them as decimals. `[0,056]` is
        not a thing anybody writes, which is why the witness is the
        leading-zero form and nothing else."""
        assert self._infer(["[7,8]", "[10,11]", "[18,19]"])["separator"] == "unknown"

    def test_one_stray_witness_does_not_decide_a_document(self):
        assert self._infer(["0,5", "84,299", "12,345"])["separator"] == "unknown"

    def test_the_verdict_carries_its_evidence(self):
        got = self._infer(["0,561", "0,7118", "0,001"])
        assert str(got["n_witnesses"]) in got["why"], "auditable, not asserted"

    def test_the_flag_changes_the_reading_and_only_the_reading(self):
        from metascience_agent.tools.celltypes import parse_cell
        assert parse_cell("74,874").value == 74874.0
        assert parse_cell("74,874", decimal_comma=True).value == 74.874

    def test_the_quote_is_still_what_the_paper_printed(self):
        """`raw` always holds the cell as printed -- this function's own
        promise, and the field a reader checks a claim against."""
        from metascience_agent.tools.celltypes import parse_cell
        assert parse_cell("74,874", decimal_comma=True).raw == "74,874"


class TestACensoredValueIsABoundNotAPoint:
    """`<0.001`, `<.0001`, `>0.99`, `≥7.0` all returned `non_numeric`, so about
    93 cells across the surveyed corpus -- most of them p-values -- were
    invisible to every check and absent from the register.

    The PROSE path has read them since it was written: `values.prose_values`
    records the bound and lets `printed` carry the qualifier. The cell path
    never did. One quantity, two answers -- the shape of defect this codebase
    found in seven number readers in a single day.
    """

    def _cell(self, raw):
        from metascience_agent.tools.celltypes import parse_cell
        return parse_cell(raw)

    def test_the_bound_and_its_operator_are_both_read(self):
        c = self._cell("<0.001")
        assert (c.kind, c.value, c.censored) == ("censored", 0.001, "<")

    def test_every_operator_form_that_appears(self):
        assert self._cell("<.0001").value == 0.0001
        assert self._cell(">0.99").censored == ">"
        assert self._cell("≥7.0").censored == ">="
        assert self._cell("≤5").censored == "<="
        assert self._cell("p < 0.001").value == 0.001, "a p-value column prints the p"

    def test_the_printed_precision_survives(self):
        """`<.0001` asserts four decimals. GRIM-family granularity is a
        function of that count."""
        assert self._cell("<.0001").decimals_value == 4

    def test_an_ordinary_number_is_untouched(self):
        c = self._cell("0.05")
        assert c.kind == "numeric" and c.censored is None

    def test_an_operator_with_no_number_is_still_nothing(self):
        assert self._cell("<").kind == "non_numeric"

    def test_no_check_is_offered_on_a_bound(self):
        """`p < 0.001` is not `p = 0.001`, and handing a checker the bound as a
        point value gives it a precision the paper never claimed. The register
        records the value and dispatch declines it."""
        cells = [{"raw": "<0.001", "row": 1, "row_label": "p-value"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        g = reg["groups"][0]
        assert g["censored"] == "<"
        assert g["quote"] == "<0.001", "the quote is what the paper printed"
        assert g["applicable_tools"] == []
        assert [v["value"] for v in g["values"]] == [0.001]

    def test_the_operator_reaches_the_table_path_not_just_the_cell(self):
        """`denominator` was a field the per-cell path could see and the table
        path could not, which is a field that does not exist for half the
        pipeline. This one travels through `as_dict`."""
        from metascience_agent.tools.celltypes import parse_cell
        assert parse_cell("<0.001").as_dict()["censored"] == "<"


class TestTheReferenceCategoryIsAValueByDefinition:
    """`1 [Reference]` is the level every other level's odds ratio is expressed
    against, so its 1 is TRUE BY CONSTRUCTION. It has no interval because it
    cannot have one, and no check can confirm or refute a definition.

    MEASURED 2026-08-20: 510 occurrences across the JAMA/psychology stratum,
    inside odds-ratio rows -- `"Suicide AOR (95% CI)", "1 [Reference]",
    "2.60 (1.46 to 4.66)", ...` -- and **ZERO** in the 284-paper cerebrolysin
    corpus. A convention of a literature rather than of a journal, which is why
    it went unseen until a survey widened the frame.
    """

    def _cell(self, raw):
        from metascience_agent.tools.celltypes import parse_cell
        return parse_cell(raw)

    def test_the_forms_that_actually_appear(self):
        for raw in ("1 [Reference]", "1 (Reference)", "1 [reference]", "1 [Ref]"):
            c = self._cell(raw)
            assert (c.kind, c.value) == ("reference_category", 1.0), raw

    def test_the_value_is_asserted_not_parsed(self):
        """Parsing it went wrong immediately: `_f("1,00")` strips the comma as a
        thousands separator and returns 100.0 -- the one cell in the table whose
        value is certain, a hundredfold wrong."""
        assert self._cell("1,00 [Reference]").value == 1.0
        assert self._cell("1·00 [Reference]").value == 1.0

    def test_the_printed_precision_still_comes_from_the_page(self):
        """`1.00` and `1` assert the same number to different precisions."""
        assert self._cell("1 [Reference]").decimals_value == 0
        assert self._cell("1.00 [Reference]").decimals_value == 2

    def test_a_number_other_than_one_is_not_a_reference_category(self):
        """The definition IS that it is 1. Anything else is a cell we have not
        understood, and guessing would be inventing a category."""
        assert self._cell("2 [Reference]").kind == "non_numeric"

    def test_no_check_is_dispatched_to_a_definition(self):
        cells = [{"raw": "1 [Reference]", "row": 1, "row_label": "Veteran status"}]
        reg = V.build_register(
            tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])
        g = reg["groups"][0]
        assert g["kind"] == "reference_category"
        assert g["applicable_tools"] == []
        assert g["quote"] == "1 [Reference]"

    def test_a_real_estimate_beside_it_is_unaffected(self):
        c = self._cell("2.60 (1.46 to 4.66)")
        assert c.kind == "estimate_ci" and c.value == 2.60
