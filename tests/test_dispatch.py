"""One call per table, and refusals that do not depend on anyone remembering.

Measured motivation: the apple-cider run made 58 tool calls, 51 of which were
the same check repeated per cell. Each call is a turn, and each turn re-sends
~16,768 tokens of fixed prefix.

The dispatcher is a ROUTER. Every check goes through
`registry.BY_NAME[tool].call()`, so guards, the exact gate and withheld params
are inherited, never reimplemented.
"""
import pytest

from metascience_agent import registry as R
from metascience_agent.dispatch import COMPOSITE_FAMILIES, check_table


def _t(cells, variables=None, bindings=None, **kw):
    return check_table(cells, variables, bindings, **kw)


LIKERT = {"id": "y", "family": "likert_item", "lower_bound": 1, "upper_bound": 7,
          "confidence": "high"}
CONT = {"id": "a", "family": "continuous", "confidence": "high"}
BINARY = {"id": "s", "family": "binary", "confidence": "high"}
COMPOSITE = {"id": "p", "family": "likert_composite", "lower_bound": 0,
             "upper_bound": 27, "n_items": 9, "confidence": "high"}



# ---------------------------------------------------------------------------
# WHY THREE `impossible` EXPECTATIONS BECAME `suspicious` ON 2026-08-10.
#
# GRIM's granularity branch now caps at `suspicious` unless someone establishes
# that the observations are integer-valued (Greg's "guilty until proven
# innocent" rule for this family -- tools/grim.HARD_DISCRETENESS_SOURCES).
#
# `Variable.discreteness_source()` demands a pipeline-set `provenance_verdict`,
# which the model cannot forge. MEASURED across every archived run: NO variable
# has ever reached `check_table` carrying one, because `agent._annotate_quotes`
# adjudicates quotes AFTER the tool calls. The pre-existing `bounds_are_stated`
# gate (#87) has exactly the same shape and is therefore also absolute on this
# path -- `bound_source` is `assumed` for every table-path call ever made.
#
# So on the CHECK_TABLE path the cap always binds, and these tests say so. That
# is the honest description of what the pipeline currently does; the assertions
# below are the specification, not an accident. Raising the ceiling requires
# verifying variable quotes BEFORE dispatch, which is a separate change.
# ---------------------------------------------------------------------------

class TestDispatch:
    def test_one_call_runs_the_whole_granularity_family(self):
        r = _t([{"raw": "5.51 (1.20)", "row_label": "S", "n": 30}], [LIKERT], {"S": "y"})
        assert set(r["tools_run"]) == {"grim_check", "grimmer_check", "sprite_reconstruct"}
        # 5.51 x 30 = 165.3 -- a real granularity failure, capped because the
        # variable's discreteness is undemonstrated on this path. See the note above.
        assert r["severity"] == "suspicious"
        assert r["n_checks_run"] == 3

    def test_continuous_data_never_reaches_the_granularity_checks(self):
        """The systolic-BP / age-48.90 false accusation, refused by RULE."""
        r = _t([{"raw": "48.90 (14.46)", "row_label": "Age", "n": 49}], [CONT], {"Age": "a"})
        assert "grim_check" not in r["tools_run"]
        assert "grimmer_check" not in r["tools_run"]
        assert "sprite_reconstruct" not in r["tools_run"]

    def test_binary_dispatches_the_percentage_check(self):
        r = _t([{"raw": "142 (71.0)", "row_label": "M", "n": 200}], [BINARY], {"M": "s"})
        assert "grim_percentage" in r["tools_run"]


class TestRefusalsAreMachineGenerated:
    def test_every_refusal_carries_a_reason(self):
        r = _t([{"raw": "3.5 (1.2)", "row_label": "X", "n": 30}])
        assert r["not_run"]
        assert all(x["reason"] for x in r["not_run"])

    def test_ambiguous_cells_run_nothing(self):
        r = _t([{"raw": "3.5 (1.2)", "row_label": "X", "n": 30}])
        assert r["n_checks_run"] == 0
        assert "ambiguous" in r["not_run"][0]["reason"]

    def test_undeclared_variable_runs_nothing_rather_than_defaulting(self):
        """Running on defaults is the top route to a false accusation."""
        r = _t([{"raw": "5.51 (1.20)", "row_label": "S, mean (SD)", "n": 30}])
        assert r["n_checks_run"] == 0
        assert any("not typed" in x["reason"] for x in r["not_run"])


class TestCompositeRefusal:
    """A 9-item composite moves in steps of 1/(items*n), not 1/n.

    `grim_test` has no `items` parameter, so dispatching a composite would use
    the wrong denominator. Verified: mean 12.30, n=42, 9 items returns
    `impossible` from grim_check -- a false accusation the batch form would have
    produced once per composite row.
    """

    def test_composites_are_refused_not_checked(self):
        r = _t([{"raw": "12.30 (4.10)", "row_label": "P", "n": 42}], [COMPOSITE], {"P": "p"})
        assert r["n_checks_run"] == 0
        assert any("composite" in x["reason"] for x in r["not_run"])

    def test_the_underlying_false_positive_is_real(self):
        """Pins WHY the refusal exists, so nobody removes it as over-caution.

        `decimals=2` is the printed precision of the literal this class is about.
        It became a no-default guard on 2026-08-07 -- the old default of 2 was
        wrong in the ACCUSING direction on 41.1% of GRIM rows -- so it now has to
        be stated. Stating it is what keeps this a test of the composite
        denominator rather than of the precision gate.

        The mean is 12.27, not the "12.30" this class was first written around:
        12.30 at n=42 is consistent under the TRUNCATION convention (true mean
        12.3095, floored to 12.30), so GRIM now correctly de-escalates it to
        `suspicious` rather than accusing a truncating reporter. 12.27 is
        impossible under BOTH round-half and truncation (enumerated), so it is
        still the genuine violation this test needs.
        """
        out = R.BY_NAME["grim_check"].call(
            {"mean": 12.27, "n": 42, "scale_min": 0, "scale_max": 27,
             "data_type": "likert", "decimals": 2,
             # Direct call, not the table path: this test is about the
             # ARITHMETIC being a genuine violation, so it stipulates the
             # discreteness premise rather than inheriting the cap.
             "discreteness_source": "stated"})
        assert out["severity"] == "impossible", (
            "if this ever passes, grim_check may have gained `items` and the "
            "composite refusal can be revisited"
        )
        assert "likert_composite" in COMPOSITE_FAMILIES


class TestDeclarationResolvesAmbiguity:
    """A declared family recovers cells that syntax alone must refuse."""

    def test_a_bare_label_is_ambiguous_without_a_declaration(self):
        assert _t([{"raw": "48.90 (14.46)", "row_label": "Age", "n": 49}])["n_checks_run"] == 0

    def test_the_same_cell_resolves_once_the_variable_is_declared(self):
        r = _t([{"raw": "48.90 (14.46)", "row_label": "Age", "n": 49}], [CONT], {"Age": "a"})
        assert r["n_checks_run"] > 0

    def test_resolution_requires_an_explicit_family_never_a_default(self):
        r = _t([{"raw": "48.90 (14.46)", "row_label": "Age", "n": 49}],
               [{"id": "a", "name": "Age"}], {"Age": "a"})
        assert r["n_checks_run"] == 0


class TestInheritsTheRegistryGates:
    def test_measured_provenance_refuses_the_exact_checks(self):
        """Reuses the registry's gate rather than duplicating it."""
        r = _t([{"raw": "5.51 (1.20)", "row_label": "S", "n": 30}], [LIKERT], {"S": "y"},
               provenance="measured_raster")
        severities = {x["severity"] for x in r["results"]}
        assert "impossible" not in severities
        assert r["severity"] in ("indeterminate", "consistent")

    def test_the_dispatcher_never_reseverities_a_result(self):
        r = _t([{"raw": "5.51 (1.20)", "row_label": "S", "n": 30}], [LIKERT], {"S": "y"})
        for rec in r["results"]:
            assert rec["severity"] == rec["result"]["severity"]


class TestOutputShape:
    def test_consistent_results_are_counted_not_repeated(self):
        """Re-inflating the context is the cost this exists to avoid."""
        r = _t([{"raw": "142 (71.0)", "row_label": "M", "n": 200}], [BINARY], {"M": "s"})
        assert r["consistent_index"]
        assert all(x["severity"] != "consistent" for x in r["results"])

    def test_denominator_travels_with_the_result(self):
        r = _t([{"raw": "5.51 (1.20)", "row_label": "S", "n": 30}], [LIKERT], {"S": "y"})
        assert r["n_checks_run"] and "summary_by_severity" in r
        assert "denominator" in r["methodology"].lower()

    def test_empty_table_does_not_crash(self):
        r = _t([])
        assert r["severity"] == "indeterminate" and r["n_checks_run"] == 0


class TestZeroChecksIsNotAnAllClear:
    """`stage1_sweep.md:213` mandates ONE check_table call per table, so this
    single severity is the entire record of the table. The fallback used to be
    "consistent", which turned "we refused every cell" into "we checked and it
    is clean" -- verified: cells n/a, --, NR returned severity 'consistent' with
    n_checks_run 0, n_not_run 3, tools_run []."""

    NOT_NUMBERS = [{"raw": "n/a"}, {"raw": "--"}, {"raw": "NR"}]

    def test_a_table_of_non_numbers_is_indeterminate(self):
        r = _t(self.NOT_NUMBERS, [])
        assert r["n_checks_run"] == 0
        assert r["tools_run"] == []
        assert r["severity"] == "indeterminate"

    def test_the_refusals_are_still_itemised(self):
        r = _t(self.NOT_NUMBERS, [])
        assert r["n_not_run"] == 3

    def test_untyped_cells_that_run_nothing_are_indeterminate_too(self):
        """A parseable cell with no declared variable: nothing dispatches."""
        r = _t([{"raw": "48.90 (14.46)", "row_label": "Age", "n": 49}],
               [{"id": "a", "name": "Age"}], {"Age": "a"})
        assert r["n_checks_run"] == 0
        assert r["severity"] == "indeterminate"

    def test_checks_that_all_pass_are_still_consistent(self):
        """The fix must not turn a real all-clear into a refusal."""
        r = _t([{"raw": "142 (71.0)", "row_label": "M", "n": 200}], [BINARY], {"M": "s"})
        assert r["n_checks_run"] > 0
        assert r["severity"] == "consistent"


class TestTheDispatchKeySpaceIsComplete:
    """A missing key and a deliberate refusal used to be indistinguishable.

    `DISPATCH` refuses anything it has no row for. That makes absence a silent
    decision, and four absences sat next to eight decisions reading identically
    until someone measured the refusals. The worst consequence was an inverted
    incentive: an `estimate_ci` cell with NO declared variable ran the check
    (via the "unknown" row) while the same cell WITH a declared likert variable
    was refused -- declaring more information turned the check off.
    """

    def test_every_kind_crossed_with_every_data_type_has_a_row(self):
        from itertools import product

        from metascience_agent.dispatch import (
            CANONICAL_DATA_TYPES,
            DISPATCH,
            DISPATCHABLE_KINDS,
        )
        expected = set(product(sorted(DISPATCHABLE_KINDS), sorted(CANONICAL_DATA_TYPES)))
        missing = expected - set(DISPATCH)
        extra = set(DISPATCH) - expected
        assert not missing, f"unrouted (kind, data_type) pairs: {sorted(missing)}"
        assert not extra, f"DISPATCH rows outside the declared key space: {sorted(extra)}"

    def test_the_kinds_match_celltypes_minus_the_never_dispatch_set(self):
        from metascience_agent.dispatch import DISPATCHABLE_KINDS, NEVER_DISPATCH
        from metascience_agent.tools.celltypes import CELL_KINDS
        assert DISPATCHABLE_KINDS == set(CELL_KINDS) - set(NEVER_DISPATCH)

    def test_the_data_types_match_what_anatomy_can_actually_produce(self):
        """If a new family maps to a new data_type, this fails before the hole
        can reach a paper."""
        from metascience_agent.anatomy import DISTRIBUTION_FAMILIES, Variable
        from metascience_agent.dispatch import CANONICAL_DATA_TYPES
        produced = {
            Variable(id=f"v{i}", name="x", family=fam).forensic_kwargs()["data_type"]
            for i, fam in enumerate(DISTRIBUTION_FAMILIES)
        }
        assert produced <= CANONICAL_DATA_TYPES, sorted(produced - CANONICAL_DATA_TYPES)

    def test_declaring_a_family_never_removes_a_check_that_unknown_would_run(self):
        """The inverted-incentive regression, stated as a property.

        For every dispatchable kind, a declared family must not run FEWER tools
        than the undeclared case, unless the empty row is a documented decision
        in WHY_NOT.
        """
        from metascience_agent.dispatch import (
            CANONICAL_DATA_TYPES,
            DISPATCH,
            DISPATCHABLE_KINDS,
            WHY_NOT,
        )
        for kind in sorted(DISPATCHABLE_KINDS):
            baseline = DISPATCH[(kind, "unknown")]
            if not baseline:
                continue
            for dtype in sorted(CANONICAL_DATA_TYPES):
                tools = DISPATCH[(kind, dtype)]
                if not tools:
                    assert (kind, dtype) in WHY_NOT, (
                        f"({kind}, {dtype}) runs nothing while ({kind}, unknown) runs "
                        f"{baseline}, and no WHY_NOT entry explains the downgrade"
                    )


class TestARefusalNamesItsOwnDischarge:
    """Every one of the 71 missing-n refusals in the archive was for an n that
    was available, and in the worst case it was inside the refused call's own
    arguments: `col_label: "Cerebrolysin (n = 59)"`, refused for want of the
    number it had just been handed.

    The refusal stays a refusal -- an enrolled n is not always the n behind a
    given row, and GRIM run with too large an n accuses. What changes is that
    the message says what would discharge it, turning a silent loss into a
    one-turn fix.
    """

    CELL = {"raw": "4.20 (1.15)", "row": 0, "row_label": "dFMA total",
            "col_label": "Cerebrolysin (n = 59)"}
    VARS = [{"id": "v1", "name": "dFMA total", "family": "likert_item",
             "lower_bound": 0, "upper_bound": 66}]

    def _run(self, cells):
        from metascience_agent.dispatch import check_table
        return check_table(cells=cells, variables=self.VARS,
                           bindings={"dFMA total": "v1"})

    def test_it_still_refuses(self):
        r = self._run([dict(self.CELL)])
        assert r["n_checks_run"] == 0 and r["n_not_run"] == 3

    def test_the_reason_names_the_number_and_where_it_came_from(self):
        r = self._run([dict(self.CELL)])
        reason = r["not_run"][0]["reason"]
        assert "n = 59" in reason and "col_label" in reason
        assert "Pass n=59" in reason

    def test_it_says_why_it_will_not_use_it_automatically(self):
        reason = self._run([dict(self.CELL)])["not_run"][0]["reason"]
        assert "not used automatically" in reason

    def test_supplying_the_named_n_discharges_it(self):
        r = self._run([dict(self.CELL, n=59)])
        assert r["n_checks_run"] == 3 and r["n_not_run"] == 0

    def test_a_cell_with_no_n_anywhere_says_where_to_look(self):
        cell = dict(self.CELL, col_label="Cerebrolysin")
        reason = self._run([cell])["not_run"][0]["reason"]
        assert "carries none" in reason
        assert "footnote" in reason or "participants" in reason

    def test_a_refusal_for_something_other_than_n_is_unchanged(self):
        from metascience_agent.dispatch import _refusal_reason
        from metascience_agent.registry import BY_NAME
        spec = BY_NAME["check_estimate_ci"]
        assert _refusal_reason(spec, None, {"col_label": "x"}) == (
            "required inputs not present in this cell")

    def test_thousands_grouped_group_sizes_are_read(self):
        from metascience_agent.dispatch import _n_in_labels
        assert _n_in_labels({"col_label": "Total (N = 1,204)"}) == [("col_label", 1204)]
        assert _n_in_labels({"row_label": "Placebo n=51"}) == [("row_label", 51)]


class TestCompositeScoringDecidesTheDenominator:
    """`derivation` was in the schema, in the prompt, rendered to the reader and
    tested -- and `Variable` had no such field, so both loaders dropped it before
    any check could see it. The model was answering a question nothing read.

    It is the field that distinguishes the two opposite composite cases, and
    conflating them cost a real detection: the blanket refusal was written from
    the item-MEAN model and suppressed the SUM case with it.
    """

    CELL = [{"raw": "12.27 (5.10)", "row": 0, "row_label": "PHQ-9 total",
             "col_label": "All (n = 42)", "n": 42}]
    BASE = {"id": "v1", "name": "PHQ-9 total", "family": "likert_composite",
            "n_items": 9, "lower_bound": 0, "upper_bound": 27}

    def _run(self, derivation=None):
        from metascience_agent.dispatch import check_table
        v = dict(self.BASE)
        if derivation:
            v["derivation"] = derivation
        return check_table(cells=self.CELL, variables=[v],
                           bindings={"PHQ-9 total": "v1"})

    def test_variable_keeps_the_field_at_all(self):
        from metascience_agent.anatomy import Variable
        assert Variable(id="v", name="v", derivation="sum_of_items").derivation \
            == "sum_of_items"

    def test_the_loaders_no_longer_drop_it(self):
        """`_as_variable` and `_pick` both filter to dataclass fields, so the
        field's absence WAS the drop."""
        from metascience_agent.dispatch import _as_variable
        assert _as_variable({"id": "v", "family": "likert_composite",
                             "derivation": "sum_of_items"}).derivation == "sum_of_items"

    def test_a_sum_composite_is_checked_at_one_over_n(self):
        """Each subject's total is an integer, so ordinary GRIM is correct and
        needs no `items` parameter. Cross-checked against R: scrutiny::grim
        agrees this value is inconsistent when treated as a sum."""
        r = self._run("sum_of_items")
        assert r["n_checks_run"] == 3 and r["n_not_run"] == 0
        # The DENOMINATOR is what this test is about -- 1/n rather than 1/(k*n)
        # -- and that is unchanged. The ceiling is capped for the reason in the
        # note above; a wrong denominator would return `consistent`, not a
        # lower-severity finding, so the test still discriminates.
        assert r["severity"] == "suspicious"

    def test_the_detection_the_blanket_refusal_was_suppressing(self):
        """Derived independently: mean 12.27 at n=42 has ZERO integer solutions
        at 1/42 and three at 1/378."""
        def sols(mean, n, d=2):
            tol = 0.5 / 10 ** d + 1e-12
            return [k for k in range(int(mean * n) - 3, int(mean * n) + 4)
                    if abs(k / n - mean) <= tol]
        assert sols(12.27, 42) == []
        assert len(sols(12.27, 42 * 9)) == 3

    def test_a_mean_composite_is_still_refused(self):
        """1/(items*n) granularity, and grim_test still has no `items`."""
        r = self._run("mean_of_items")
        assert r["n_checks_run"] == 0
        assert "MEAN of items" in r["not_run"][0]["reason"]

    def test_an_undeclared_composite_is_refused_and_says_what_would_fix_it(self):
        r = self._run(None)
        assert r["n_checks_run"] == 0
        reason = r["not_run"][0]["reason"]
        assert "undeclared" in reason and "derivation" in reason
        assert "sum_of_items" in reason

    def test_the_two_refusals_are_distinguishable(self):
        """A reader must be able to tell 'we cannot check this' from 'nobody has
        told us which kind it is' -- the second is discharged by one word."""
        assert self._run(None)["not_run"][0]["reason"] != \
            self._run("mean_of_items")["not_run"][0]["reason"]


class TestTheRefusalCarriesItsOwnCure:
    """The commonest refusal in the system had its remedy only in a prompt.

    MEASURED on a real paper: 79 checkable cells, 76 blocked for want of a
    variable declaration, 0 checked. Nothing was missing from the plumbing --
    `variables` and `bindings` arrive in the SAME call and are already guards,
    and the dispatcher refused correctly and said why. What it never returned
    was the FORM, so the cure lived in an instruction the model had to remember,
    and a rule that has to be remembered is one that will sometimes not be.
    """

    def _undeclared(self):
        from metascience_agent.dispatch import check_table
        return check_table([
            {"raw": "48.90 (14.46)", "row_label": "Age", "col_label": "A", "n": 60},
            {"raw": "48.10 (13.02)", "row_label": "Age", "col_label": "B", "n": 58},
            {"raw": "31 (51.7)", "row_label": "Female", "col_label": "A", "n": 60},
        ])

    def test_an_undeclared_table_returns_a_form_not_only_a_complaint(self):
        r = self._undeclared()
        tpl = r["declaration_template"]
        rows = {t["row_label"] for t in tpl}
        assert rows == {"Age", "Female"}
        for t in tpl:
            assert set(t["declare"]) >= {"id", "name", "family", "scale_min",
                                         "scale_max", "bounds_are_stated"}
            assert t["bind"] == {t["row_label"]: "<the id you chose above>"}

    def test_what_it_promises_is_what_the_dispatcher_would_do(self):
        """`would_unlock` is SIMULATED through the real resolver and DISPATCH,
        never written out -- a second copy of the routing table is the thing
        this module exists to avoid."""
        from metascience_agent.dispatch import check_table
        r = self._undeclared()
        age = next(t for t in r["declaration_template"] if t["row_label"] == "Age")
        promised = set(age["would_unlock"]["count"]["runs"])
        assert "grim_check" in promised

        actual = check_table(
            [{"raw": "48.90 (14.46)", "row_label": "Age", "col_label": "A", "n": 60}],
            variables=[{"id": "age", "name": "Age", "family": "count",
                        "scale_min": 0, "scale_max": 100, "bounds_are_stated": True}],
            bindings={"Age": "age"},
        )
        ran = set(actual["tools_run"])
        assert promised & ran, f"promised {sorted(promised)}, ran {sorted(ran)}"

    def test_it_warns_against_declaring_for_coverage(self):
        """`would_unlock` lists more tools for some families than others, so a
        reader optimising for coverage would pick the longest list. On an n(%)
        row, declaring `count` re-reads '31 (51.7)' as mean 31 SD 51.7 and runs
        GRIM on a mean the paper never reported."""
        r = self._undeclared()
        for t in r["declaration_template"]:
            assert "manufactures accusations" in t["caution"]
            assert "never whichever" in t["caution"]

    def test_a_declared_table_needs_no_form(self):
        from metascience_agent.dispatch import check_table
        r = check_table(
            [{"raw": "48.90 (14.46)", "row_label": "Age", "col_label": "A", "n": 60}],
            variables=[{"id": "age", "name": "Age", "family": "count",
                        "scale_min": 0, "scale_max": 100, "bounds_are_stated": True}],
            bindings={"Age": "age"},
        )
        assert r["declaration_template"] == []

    def test_a_family_that_unlocks_nothing_is_not_offered(self):
        """Offering it would invite a declaration that buys the reader nothing."""
        r = self._undeclared()
        for t in r["declaration_template"]:
            for family, detail in t["would_unlock"].items():
                assert detail["runs"], f"{family} offered with no checks"


class TestASectionDenominatorRescuesTheCellsThatCarryNone:
    """MEASURED on 10.1038/s41537-025-00576-3 Table 2, the composite table Greg
    found: 389 cells, `check_table` ran 0 checks and refused all 389 -- 244 of
    them reading "grim_percentage needs n and this cell carries none". The n was
    there the whole time. Within a banner-delimited section the categories are
    exhaustive, so the counts sum to the denominator, and `composite` verifies
    that sum against every percentage the section prints before returning it.
    Same table after wiring: 171 checks run.

    The three properties that keep this from manufacturing accusations are what
    these tests pin -- it is additive, it is restricted to the cells it was
    summed from, and it never reaches `impossible`.
    """

    def _section(self, label, rows, col="Overall"):
        """A banner row, then one `count (percent)` row per category."""
        cells = [{"raw": label, "row": 0, "row_label": label, "col_label": c}
                 for c in (col, "Group B")]
        for i, (name, raw_a, raw_b) in enumerate(rows, start=1):
            cells.append({"raw": raw_a, "row": i, "row_label": name, "col_label": col})
            cells.append({"raw": raw_b, "row": i, "row_label": name, "col_label": "Group B"})
        return cells

    PROP = {"id": "g", "family": "proportion", "confidence": "high"}

    def test_a_cell_with_no_n_is_checked_against_its_sections_own_total(self):
        cells = self._section("Gender", [("Female", "40 (40.00)", "10 (50.00)"),
                                         ("Male", "60 (60.00)", "10 (50.00)")])
        r = _t(cells, [self.PROP], {"Female": "g", "Male": "g"})
        # TWO checks per cell since 2026-08-10: `grim_percentage` and
        # `check_count_percent`. The second is the stronger one wherever the
        # count is printed -- see tests/test_count_percent.py for the false
        # clear it closes -- so 4 cells now run 8 checks.
        assert r["n_checks_run"] == 8
        assert r["n_denominators_derived"] == 8
        used = {c["inputs"]["n"] for c in r["results"]} | {100, 20}
        assert used == {100, 20}, "each column keeps its own denominator"

    def test_a_stated_n_always_wins(self):
        """Purely additive: this can turn a refusal into a check and must never
        change the inputs of a check that would have run anyway."""
        cells = self._section("Gender", [("Female", "40 (40.00)", "10 (50.00)"),
                                         ("Male", "60 (60.00)", "10 (50.00)")])
        for c in cells:
            c["n"] = 3
        r = _t(cells, [self.PROP], {"Female": "g", "Male": "g"})
        assert r["n_denominators_derived"] == 0
        # n = 3 is the point: the derived denominators (100 and 20) both make
        # 40.00% reachable, and only the STATED 3 does not. The verdict proves
        # which number the check was handed.
        assert {c["inputs"]["n"] for c in r["results"]} == {3}
        assert r["severity"] == "impossible"

    def test_a_row_that_contributed_no_count_does_not_receive_the_total(self):
        """THE false-accusation route this closes. A `mean (SD)` row printed
        inside an otherwise categorical section contributed nothing to the sum,
        and its own n may be smaller for missing data. GRIM on the section total
        would be an `impossible` about a denominator that was never its own."""
        cells = self._section("Gender", [("Female", "40 (40.00)", "10 (50.00)"),
                                         ("Male", "60 (60.00)", "10 (50.00)")])
        cells += [{"raw": "5.51 (1.20)", "row": 9, "row_label": "Score",
                   "col_label": "Overall"}]
        likert = {"id": "y", "family": "likert_item", "lower_bound": 1,
                  "upper_bound": 7, "confidence": "high"}
        r = _t(cells, [self.PROP, likert],
               {"Female": "g", "Male": "g", "Score": "y"})
        assert any(c.get("cell") == "Score" for c in r["not_run"]) or any(
            c["cell"]["row_label"] == "Score" for c in r["results"]), \
            "the mean row must still be accounted for"
        assert not any(c.get("n_provenance") for c in r["results"]
                       if (c.get("cell") or {}).get("row_label") == "Score")

    def test_a_derived_denominator_can_never_produce_impossible(self):
        """`impossible` admits no innocent explanation, so this repo reserves it
        for exact arithmetic on values the PAPER PRINTED. A denominator we
        reconstructed is not printed, however well it verifies."""
        from metascience_agent.dispatch import _stamp_derived_n
        rec = {"severity": "impossible"}
        _stamp_derived_n(rec, {"n": 100, "n_source": "x", "section": "S", "column": "c"})
        assert rec["severity"] == "highly_suspicious"
        assert rec["severity_uncapped"] == "impossible"
        assert "NOT printed in the table" in rec["n_provenance"]["note"]

    def test_an_unverifiable_section_yields_nothing_and_says_why(self):
        """A denominator we inferred and could not confirm is worth strictly
        less than no denominator at all."""
        cells = self._section("Gender", [("Female", "40 (40.00)", "10 (50.00)"),
                                         ("Male", "50 (60.00)", "10 (50.00)")])
        r = _t(cells, [self.PROP], {"Female": "g", "Male": "g"})
        why = r["sections"][0]["why_not"]
        assert "Overall" in why
        assert "does not reproduce" in why["Overall"]
        assert not any(c.get("n_provenance") for c in r["results"]
                       if c["inputs"].get("n") == 90)

    def test_sections_are_published_even_when_the_table_has_no_banners(self):
        """The sections are how the table was read. A reader who disagrees with
        a denominator needs the rows it was summed from; a reader whose table
        yielded none needs the stated reason rather than silence."""
        r = _t([{"raw": "5.51 (1.20)", "row_label": "S", "n": 30}],
               [LIKERT], {"S": "y"})
        assert len(r["sections"]) == 1
        assert r["sections"][0]["label"] is None
        assert r["n_denominators_derived"] == 0

    def test_a_malformed_table_degrades_to_the_refusal_we_already_had(self):
        """Never raises. The worst outcome of failing here must be the refusal
        that was there before, not a dead check_table."""
        cells = [{"raw": "40 (40.00)", "row": "a", "row_label": "F", "col_label": "c"},
                 {"raw": "60 (60.00)", "row": 2, "row_label": "M", "col_label": "c"}]
        r = _t(cells, [self.PROP], {"F": "g", "M": "g"})
        assert r["n_denominators_derived"] == 0
        assert "section split failed" in (r["sections"][0]["why_not"] or "")
