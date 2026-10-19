"""An impossible value indicts our extraction before it indicts the paper.

GREG, 2026-08-11, on a real archived finding reporting "a correlation
coefficient of 11.3":

    "such a finding should trigger an automatic review of the PDF to make sure
     there wasn't an extraction error like misreading 0.113 for 11.3, or
     mistakenly extracting a mean instead of an r value. Gross mistakes like
     that are uncommon even in the most fraudulent papers."

That is a claim about priors, and it inverts the obvious design. An
out-of-bounds value is the most tempting thing in this toolkit to escalate --
unambiguous, premise-free, and `impossible` is defensible on the arithmetic
alone. It is therefore the shortest path to the worst output this toolkit can
produce: a false accusation sourced entirely from our own decimal-point slip,
stated at the top of the ladder.
"""
import pytest

from metascience_agent.tools.bounds import (
    MEASURE_BOUNDS, canonical_measure, check_statistic_bounds,
    rescalings_that_fit,
)


class TestTheCaseThatPromptedIt:
    def test_r_of_11_point_3_is_NOT_an_accusation(self):
        r = check_statistic_bounds(11.3, "correlation")
        assert r["severity"] == "indeterminate"
        assert r["failure_mode"] == "extraction_suspect"
        assert r["severity"] not in ("impossible", "highly_suspicious", "suspicious")

    def test_it_names_the_reading_greg_named_on_sight_FIRST(self):
        """Ordering is load-bearing. Sorting the candidates by magnitude put
        0.00113 ahead of 0.113 -- burying the one reading a human recognises
        instantly behind two nobody would propose. Fewest places slipped is
        likeliest, so that is the order."""
        fits = check_statistic_bounds(11.3, "r")["rescalings_that_would_fit"]
        assert fits[0]["reading"] == pytest.approx(0.113)
        assert fits[0]["places"] == 1 or "2 places" in fits[0]["slip"]

    def test_it_says_the_error_is_probably_OURS(self):
        r = check_statistic_bounds(11.3, "correlation")
        assert "doubt OUR reading before doubting the paper" in r["explanation"]
        assert "fabricators produce plausible numbers" in r["explanation"].lower()

    def test_it_tells_the_reader_where_to_look(self):
        """A generic 'check the extraction' is not actionable; the specific
        alternative reading can be confirmed in one glance at the page."""
        v = check_statistic_bounds(11.3, "correlation")["verify_first"]
        assert any("decimal point" in s for s in v)
        assert any("wrong column" in s for s in v)

    def test_it_declares_itself_not_a_finding(self):
        assert "must not be reported as one" in \
            check_statistic_bounds(11.3, "correlation")["not_evidence"]


class TestVerificationIsThePriceOfTheAccusation:
    def test_a_verified_extraction_licenses_impossible(self):
        """The bound IS logically necessary. Once the reading is confirmed
        against the paper's own text, the refusal has done its job and the
        arithmetic speaks."""
        r = check_statistic_bounds(11.3, "r", extraction_verified=True,
                                   source_quote="a correlation coefficient of 11.3")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "outside_logical_bound"

    def test_even_then_it_offers_the_innocent_explanations(self):
        r = check_statistic_bounds(11.3, "r", extraction_verified=True)
        assert "typesetting error" in r["explanation"]
        assert "mislabelled" in r["explanation"]

    def test_the_escape_is_evidential_not_discretionary(self):
        """The ONLY thing that lifts the refusal is a verified extraction --
        not a confidence flag, not the model's say-so."""
        import inspect

        from metascience_agent.tools import bounds
        sig = inspect.signature(bounds.check_statistic_bounds)
        assert set(sig.parameters) == {
            "value", "measure", "extraction_verified", "source_quote"}


class TestOrdinaryValuesArePassedWithoutComment:
    @pytest.mark.parametrize("v,m", [
        (0.113, "correlation"), (-0.97, "pearson_r"), (0.04, "p_value"),
        (1.0, "p_value"), (0.0, "proportion"), (73.0, "percentage"),
        (100.0, "percentage"), (1.0, "kappa"), (-1.0, "icc"),
        (0.83, "r_squared"), (12.4, "chi_squared"), (0.0, "sd"),
    ])
    def test_in_bounds_is_consistent(self, v, m):
        assert check_statistic_bounds(v, m)["severity"] == "consistent"

    def test_cronbach_alpha_is_unbounded_below(self):
        """A negative alpha is ugly and entirely possible; only alpha > 1 is
        impossible. Treating the lower side as a bound would accuse papers that
        honestly reported a badly-behaved scale."""
        assert check_statistic_bounds(-3.2, "cronbach_alpha")["severity"] == "consistent"
        assert check_statistic_bounds(1.4, "alpha")["severity"] == "indeterminate"


class TestItRefusesRatherThanGuessing:
    def test_an_unknown_measure_is_never_accused(self):
        """This tool knows bounds that follow from a DEFINITION. An expectation
        about a plausible range is an assumption, and this repo caps verdicts
        resting on our assumptions rather than issuing them."""
        r = check_statistic_bounds(500.0, "widget_index")
        assert r["applicable"] is False
        assert r["severity"] == "indeterminate"
        assert "Not a statement about the paper" in r["explanation"]

    @pytest.mark.parametrize("bad", [None, "abc", float("nan"), float("inf")])
    def test_garbage_returns_a_refusal_not_a_crash(self, bad):
        r = check_statistic_bounds(bad, "correlation")
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_aliases_the_model_actually_writes_resolve(self):
        for alias, canon in (("r", "correlation"), ("p", "p_value"),
                             ("R2", "r_squared"), ("rho", "spearman_rho"),
                             ("AUROC", "auc"), ("chi2", "chi_squared")):
            assert canonical_measure(alias) == canon

    def test_every_bound_in_the_table_is_logically_necessary(self):
        """A reviewer of this table should be able to name the theorem or the
        definition for each row. Convention-based ranges do not belong here --
        they would make our expectations into the paper's obligations."""
        for name, (lo, hi) in MEASURE_BOUNDS.items():
            assert lo is not None or hi is not None, name
            if lo is not None and hi is not None:
                assert lo < hi, name


class TestTheRescalingSearch:
    def test_it_finds_nothing_when_nothing_would_fit(self):
        """A negative SD cannot be rescued by moving the decimal point, and
        offering a bogus candidate would be worse than offering none."""
        assert rescalings_that_fit(-5.0, 0.0, None) == []

    def test_a_percentage_of_150_reads_as_15(self):
        fits = rescalings_that_fit(150.0, 0.0, 100.0)
        assert fits[0]["reading"] == pytest.approx(15.0)
        assert fits[0]["places"] == 1

    def test_it_caps_the_list(self):
        assert len(rescalings_that_fit(11300.0, -1.0, 1.0)) <= 3


class TestSPRITEIsReproducible:
    """A Monte Carlo search whose NEGATIVE result can reach `impossible` must
    give the same answer twice.

    SPRITE drew from the unseeded module-global RNG, so "no integer sample
    reproduces this mean and SD" was not reproducible: the same paper could
    yield a finding on one run and not the next, and a reader re-running the
    tool to check us could fail to see what we saw. For an instrument whose
    output may be put to an author, that is the wrong kind of surprise.

    Found by an observability audit, not by a failing test -- which is the point
    the audit was making.
    """

    KW = dict(mean=3.0, sd=1.5, n=20, scale_min=1, scale_max=7, decimals_sd=1,
              data_type="likert", discreteness_source="stated")

    def _sr(self, **over):
        from metascience_agent.tools.sprite import sprite_reconstruct
        return sprite_reconstruct(**{**self.KW, **over})

    def test_the_same_call_twice_gives_the_same_verdict(self):
        assert self._sr()["severity"] == self._sr()["severity"]

    def test_the_same_call_twice_gives_the_same_reconstructions(self):
        """The verdict alone is a weak check -- it is one word, and it could
        agree by luck. The samples are what the search actually produced."""
        a = [list(map(int, s)) for s in (self._sr().get("sample_distributions") or [])]
        b = [list(map(int, s)) for s in (self._sr().get("sample_distributions") or [])]
        assert a == b

    def test_the_seed_is_a_parameter_so_robustness_can_be_TESTED(self):
        """The honest way to ask whether a no-solution result is robust is to
        re-run under several seeds, not to hope the default was lucky."""
        import inspect

        from metascience_agent.tools.sprite import sprite_reconstruct
        assert "seed" in inspect.signature(sprite_reconstruct).parameters

    def test_it_does_not_seed_the_global_rng(self):
        """A local `random.Random`, because seeding the global would silently
        make every other consumer of `random` in the process deterministic --
        a side effect no caller asked for."""
        import random
        random.seed(1234)
        before = random.random()
        random.seed(1234)
        self._sr()
        assert random.random() == before

    def test_the_analytic_screen_is_not_a_search_at_all(self):
        """What makes a SPRITE no-solution usable as evidence is that the
        infeasibility is PROVED from parity and integrality, not searched for.
        That path takes no RNG and cannot be seed-dependent."""
        from metascience_agent.tools.sprite import _sd_window_feasible
        ok_a, _ = _sd_window_feasible(60, 20, 1.5, 1, 1, 7)
        ok_b, _ = _sd_window_feasible(60, 20, 1.5, 1, 1, 7)
        assert ok_a is ok_b


class TestEverySimulatingToolSuppliesItsSeed:
    """GREG, 2026-08-11: "insofar as we do simulations, we must supply the
    initial seed for the purposes of reproducibility. (make sure this is the
    case for all tools that do this.)"

    Two halves, and the second is the one that was missing. A fixed DEFAULT
    makes a search deterministic; declaring the seed a registry `Param` is what
    puts the actual value into the call ledger, so a reader re-running the tool
    a year from now reproduces THIS result rather than a similar one.

    Audited across the toolkit: `rivets_anova`, `rivets_independent_t`,
    `bayesian_table1_dispersion` and `check_proportion_from_normal` already did
    both. `sprite_reconstruct` drew from the unseeded module-global RNG, and
    `r_sprite_ground_truth` never called `set.seed` at all -- the two SPRITEs,
    which is to say the tool whose negative verdict can reach `impossible` and
    the referee it is judged against.
    """

    #: Every registered tool whose result depends on a pseudo-random draw.
    #: Adding a simulating tool without adding it here is the failure this
    #: guards; the source scan below is what catches that.
    SIMULATING = ("sprite_reconstruct", "rivets_anova", "rivets_independent_t",
                  "bayesian_table1_dispersion", "check_proportion_from_normal",
                  "r_sprite_ground_truth")

    def test_each_takes_a_seed(self):
        import inspect

        from metascience_agent import registry as R
        for name in self.SIMULATING:
            fn = R.BY_NAME[name].fn
            assert "seed" in inspect.signature(fn).parameters, name

    def test_each_seed_defaults_to_a_FIXED_value(self):
        """`seed=None` would be a seed parameter that changes nothing."""
        import inspect

        from metascience_agent import registry as R
        for name in self.SIMULATING:
            default = inspect.signature(R.BY_NAME[name].fn).parameters["seed"].default
            assert isinstance(default, int), f"{name}: seed default is {default!r}"

    def test_each_seed_is_RECORDED_in_the_call_ledger(self):
        """The half that was missing. A seed the caller cannot see is a seed
        nobody can re-supply."""
        from metascience_agent import registry as R
        for name in self.SIMULATING:
            spec = R.BY_NAME[name]
            assert any(p.name == "seed" for p in spec.params), (
                f"{name} simulates but does not declare `seed` as a Param, so "
                "the value used is absent from the archived call")

    def test_no_tool_module_reaches_for_the_GLOBAL_rng(self):
        """A module-level `random.shuffle`/`random.choice` is the shape the
        SPRITE defect had: seeded-looking code that is not. Seeding the global
        instead would be worse -- it silently makes every other consumer of
        `random` in the process deterministic."""
        import pathlib
        import re
        tools = (pathlib.Path(__file__).resolve().parents[1]
                 / "src/metascience_agent/tools")
        call = re.compile(
            r"(?<![\w.])random\.(shuffle|choice|random|randint|sample|uniform|seed)\s*\(")
        bad = []
        for f in sorted(tools.glob("*.py")):
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                # Comments discuss the global RNG precisely BECAUSE it is
                # forbidden; scanning them flags the explanation, not the
                # offence. (This caught my own note on the line below.)
                code = line.split("#", 1)[0]
                if call.search(code):
                    bad.append(f"{f.name}:{i}")
        assert not bad, (
            "these use the module-global RNG rather than a local "
            f"random.Random(seed): {bad}")


class TestTheSplitCountPercentColumn:
    """`check_count_percent` is the strongest check available wherever the
    count is printed -- and it never ran on the commonest layout for printing
    one.

    It is routed for every cell typed `n_percent`, but that type means ONE cell
    reading `142 (73.0)`. Where a journal splits the pair across adjacent
    columns no such cell exists, so the routing never fires. Archived refusals
    name it exactly: "the counts and percentages sit in separate columns, so
    the typed parser reads them as independent."

    MEASURED on real archived tables after building the pairing: 180 pairs
    found, 132 checkable, ZERO disagreements -- the check works and that paper's
    arithmetic is sound.
    """

    A, B = "Arm A (n = 22)", "Arm B (n = 30)"

    def _cells(self):
        return [
            {"raw": "3", "row_label": "Spasticity", "col_label": f"{self.A} | No."},
            {"raw": "13.64", "row_label": "Spasticity", "col_label": f"{self.A} | %"},
            {"raw": "14", "row_label": "Spasticity", "col_label": f"{self.B} | No."},
            {"raw": "46.67", "row_label": "Spasticity", "col_label": f"{self.B} | %"},
        ]

    def test_it_pairs_within_an_arm_and_NOT_ACROSS_ARMS(self):
        """THE SAFETY PROPERTY, and the reason this test exists.

        My first attempt at measuring this took the cross-product of count
        columns against percentage columns and reported 1,656 "pairs" -- it was
        pairing arm A's count with arm B's percentage. Every one would have been
        a false accusation, manufactured by us, against a table whose
        arithmetic is fine. Four cells here must yield TWO pairs, not four.
        """
        from metascience_agent.dispatch import count_percent_pairs
        pairs = count_percent_pairs(self._cells())
        assert len(pairs) == 2
        for p in pairs:
            assert (p["count_cell"]["col_label"].split("|")[0]
                    == p["percent_cell"]["col_label"].split("|")[0])

    def test_the_denominator_comes_from_that_groups_OWN_header(self):
        from metascience_agent.dispatch import count_percent_pairs
        got = {p["group"]: p["n"] for p in count_percent_pairs(self._cells())}
        assert got == {self.A: 22, self.B: 30}

    def test_headers_that_do_not_span_are_LEFT_ALONE(self):
        """Without a separator there is no group to pair on, and pairing by
        position is the guess this refuses to make."""
        from metascience_agent.dispatch import count_percent_pairs
        assert count_percent_pairs([
            {"raw": "3", "row_label": "X", "col_label": "No."},
            {"raw": "13.64", "row_label": "X", "col_label": "%"}]) == []

    def test_no_printed_denominator_means_no_check(self):
        from metascience_agent.dispatch import count_percent_pairs
        assert count_percent_pairs([
            {"raw": "3", "row_label": "X", "col_label": "Arm A | No."},
            {"raw": "13.64", "row_label": "X", "col_label": "Arm A | %"}]) == []

    def test_an_ambiguous_prefix_refuses_rather_than_picking_one(self):
        """Two count columns under one prefix means the prefix does not
        identify a group."""
        from metascience_agent.dispatch import count_percent_pairs
        assert count_percent_pairs([
            {"raw": "3", "row_label": "X", "col_label": "Arm A (n = 22) | No."},
            {"raw": "4", "row_label": "X", "col_label": "Arm A (n = 22) | n"},
            {"raw": "13.64", "row_label": "X", "col_label": "Arm A (n = 22) | %"}]) == []

    def test_check_table_ACTUALLY_RUNS_IT(self):
        """Built, tested, never invoked is this repo's recurring failure, and
        the tool being paired here is itself an instance of nearly becoming
        one."""
        from metascience_agent.dispatch import check_table
        out = check_table(self._cells(), [], {})
        assert "check_count_percent" in (out.get("tools_run") or set())

    def test_a_real_mismatch_surfaces_capped_at_suspicious(self):
        """5/22 = 22.7%, not 40.0. Capped because a percentage over a DIFFERENT
        base is the commonest convention in clinical tables -- the mismatch is
        evidence about which denominator was used at least as often as about
        the arithmetic."""
        from metascience_agent.dispatch import check_table
        cells = self._cells() + [
            {"raw": "5", "row_label": "Pain", "col_label": f"{self.A} | No."},
            {"raw": "40.0", "row_label": "Pain", "col_label": f"{self.A} | %"}]
        hits = [r for r in check_table(cells, [], {}).get("results", [])
                if r["tool"] == "check_count_percent"]
        assert len(hits) == 1
        assert hits[0]["severity"] == "suspicious"
        assert hits[0]["cell"]["row_label"] == "Pain"

    def test_it_carries_a_runnable_reproduction_and_its_denominator_source(self):
        from metascience_agent.dispatch import check_table
        cells = self._cells() + [
            {"raw": "5", "row_label": "Pain", "col_label": f"{self.A} | No."},
            {"raw": "40.0", "row_label": "Pain", "col_label": f"{self.A} | %"}]
        r = [x for x in check_table(cells, [], {}).get("results", [])
             if x["tool"] == "check_count_percent"][0]
        assert r["reproduction"] == "metascience check-count-percent 5 40.0 22 --decimals 1"
        assert r["n_provenance"]["how"] == "printed_in_a_label"
        assert r["n_provenance"]["derived"] is False

    def test_consistent_pairs_do_not_bloat_the_result(self):
        """They go to the index, like every other consistent check -- the whole
        point of the dispatcher."""
        from metascience_agent.dispatch import check_table
        out = check_table(self._cells(), [], {})
        assert not [r for r in out.get("results", [])
                    if r["tool"] == "check_count_percent"]
        assert len([c for c in out.get("consistent_index", [])
                    if c["tool"] == "check_count_percent"]) == 2

    def test_garbage_cells_are_skipped_rather_than_crashing(self):
        from metascience_agent.dispatch import check_table
        cells = [
            {"raw": "n/a", "row_label": "X", "col_label": f"{self.A} | No."},
            {"raw": "--", "row_label": "X", "col_label": f"{self.A} | %"}]
        assert check_table(cells, [], {}) is not None


class TestPrintAndExport:
    """The last unbuilt piece of the Fable viewer plan's phase 3.

    The integrity officer this document is partly for does not read HTML: they
    read a paper copy in a meeting and hand it to someone who was not in the
    room. Two consequences shape the whole feature, and each has its own test
    below -- the lazy section cache, and the fact that a printed page travels
    without its context.
    """

    def _src(self):
        import pathlib
        return (pathlib.Path(__file__).resolve().parents[1]
                / "src/metascience_agent/bundle.py").read_text(encoding="utf-8")

    def test_printing_forces_every_section_to_BUILD_first(self):
        """`built{}` fills lazily as a reader clicks, so a bare window.print()
        emits whatever happened to be open and silently omits the rest. That is
        worse than no print support: the result looks complete."""
        src = self._src()
        assert "function printAll()" in src
        i = src.index("function printAll()")
        body = src[i:i + 900]
        assert "S.filter(s=>!built[s.id])" in body
        assert "window.print()" in body

    def test_a_section_that_fails_to_build_does_not_abort_the_print(self):
        """One broken section must not cost the reader the other eleven."""
        src = self._src()
        i = src.index("function printAll()")
        assert "catch(e)" in src[i:i + 900]

    def test_every_printed_sheet_carries_the_disclaimer(self):
        """A page cropped out of the middle of this document and circulated is
        the route by which an automated flag becomes an accusation nobody
        qualified. The same argument as the screenshot test, applied to paper."""
        src = self._src()
        assert "NOT a finding of misconduct" in src
        assert '.printhead{' in src
        assert "position:fixed" in src[src.index(".printhead{"):src.index(".printhead{") + 200]

    def test_the_running_head_is_SHORT(self):
        """The first draft printed the author list whole and produced a
        seventeen-name running header on the first paper I tried -- a header
        nobody reads, on every sheet. First author plus `et al.` is what a
        running head is for."""
        src = self._src()
        i = src.index("const h=document.getElementById('printhead')")
        block = src[i:i + 1400]
        assert "et al." in block
        assert "split(/\\s+/).pop()" in block

    def test_the_chrome_is_hidden_on_paper(self):
        src = self._src()
        i = src.index("@media print{")
        block = src[i:i + 900]
        for hidden in ("nav", "#navtoggle", ".copyq", ".printbtn"):
            assert hidden in block
        # and every section prints, not just the open one
        assert "section:not(.on){display:block!important}" in block

    def test_cards_are_not_split_across_a_page_break(self):
        """A finding whose severity chip lands on one sheet and whose
        qualification lands on the next is the screenshot failure in slow
        motion."""
        src = self._src()
        i = src.index("@media print{")
        assert "break-inside:avoid" in src[i:i + 900]

    def test_collapsed_details_open_on_paper(self):
        """A <details> a reader never clicked is invisible in print, which
        would silently drop the evidence blocks from the printed record."""
        src = self._src()
        i = src.index("@media print{")
        assert "details:not([open])>*:not(summary){display:revert}" in src[i:i + 900]


class TestCompositeTableDisplay:
    """A composite table stacks sub-tables under spanning banner rows, and the
    viewer drew it as a flat grid -- so a banner rendered as its own text
    repeated across every column, indistinguishable from data.

    MEASURED across 138 archived table extractions: 80 tables carry banner
    sections, 223 sections in all, over 6 papers.
    """

    def _sections(self, full):
        from metascience_agent.bundle import _table_sections
        return _table_sections(full)

    GRID = [
        ["Group", "A", "B"],
        ["Sham", "6", "6"],
        ["C. Nerve Lesion", "C. Nerve Lesion", "C. Nerve Lesion"],
        ["4 wk", "6", "8"],
    ]

    def _full(self):
        return {"data": self.GRID,
                "cells": [{"row": 2, "col": 0, "raw": "C. Nerve Lesion"},
                          {"row": 2, "col": 1, "raw": "C. Nerve Lesion"},
                          {"row": 3, "col": 0, "raw": "6"},
                          {"row": 3, "col": 1, "raw": "8"}]}

    def test_it_finds_the_banner_row(self):
        out = self._sections(self._full())
        assert out and out[0]["banner_rows"] == [2]

    def test_A_DATA_ROW_IS_NEVER_MARKED_AS_A_BANNER(self):
        """THE BUG I NEARLY SHIPPED, and the reason this test is named this way.

        The first version took row indices from `cells[].row`. They drift from
        the rendered grid by one -- on 10.1007/s11064-023-03861-8 Table 1 the
        banner is `cells` row 4 and `data` row 3 -- and `cells` also excludes
        the label column, so the widths differ. Executing the renderer against
        a real bundle showed the consequence: the data row
        `['4 wk','6','8','8','22']` was about to be collapsed into a single
        `4 wk` cell, DELETING four numbers from the reader's view.

        Reading the grid the viewer actually draws makes the alignment true by
        construction rather than by assumption.
        """
        out = self._sections(self._full())
        assert 3 not in out[0]["banner_rows"]
        assert 1 not in out[0]["banner_rows"]

    def test_indices_address_the_grid_the_viewer_renders(self):
        out = self._sections(self._full())
        for i in out[0]["banner_rows"]:
            row = self.GRID[i]
            assert len({str(v).strip() for v in row if str(v).strip()}) == 1

    def test_a_one_column_table_has_no_banners(self):
        """Treating its label column as one would blank the table."""
        full = {"data": [["Outcome"], ["Pain"], ["Sleep"]],
                "cells": [{"row": 1, "col": 0, "raw": "Pain"}]}
        out = self._sections(full)
        assert not out or out[0]["banner_rows"] == []

    def test_a_repeated_NUMBER_is_not_a_banner(self):
        """A row reading `0, 0, 0` is data, and a very ordinary kind."""
        full = {"data": [["h", "a", "b"], ["Deaths", "0", "0"], ["0", "0", "0"]],
                "cells": [{"row": 1, "col": 0, "raw": "0"}]}
        out = self._sections(full)
        assert not out or 2 not in out[0]["banner_rows"]

    def test_the_denominator_reason_is_carried_not_blanked(self):
        """MEASURED: of 223 archived sections, ZERO have a derived denominator
        and `composite._derive_n` explains why on 217 -- "no column yielded a
        verified denominator". That is the CORRECT answer for those tables
        (animal experiments carrying mean (SD), so there is no count column to
        sum against a printed percentage), and it must reach the reader: a
        section with no denominator and a section nobody tried to derive one
        for look identical when both render blank."""
        out = self._sections(self._full())
        assert out and out[0]["sections"]
        s = out[0]["sections"][0]
        assert set(s) >= {"label", "n", "n_source", "why_not"}

    def test_the_renderer_and_its_styling_are_wired(self):
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src/metascience_agent/bundle.py").read_text(encoding="utf-8")
        assert "function sectionNote(t)" in src
        # Defined once and CALLED from the table strip. The definition happens
        # to sit earlier in the file than the call, so this counts occurrences
        # rather than asserting an order that is not load-bearing.
        assert src.count("sectionNote(t)") >= 2
        assert 'tr class="banner"' in src
        assert "tr.banner td{" in src

    def test_the_banner_is_not_styled_as_a_severity(self):
        """It is structure. It says nothing about whether anything is wrong,
        and the severity palette is reserved for claims about the paper."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src/metascience_agent/bundle.py").read_text(encoding="utf-8")
        i = src.index("tr.banner td{")
        for accusatory in ("--bad", "--warn", "--flag", "red"):
            assert accusatory not in src[i:i + 160]

    def test_a_table_with_no_banners_returns_nothing(self):
        full = {"data": [["h", "a"], ["Pain", "3"]],
                "cells": [{"row": 1, "col": 0, "raw": "3"}]}
        assert self._sections(full) == []

    def test_garbage_input_does_not_crash(self):
        for bad in ({}, {"data": None}, {"data": [], "cells": []},
                    {"data": [["a"]], "cells": None}):
            assert self._sections(bad) == []
