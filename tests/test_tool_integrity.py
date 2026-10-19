"""Every tool must say what KIND of claim it makes, and it must be consistent.

Greg, 2026-08-09: "there should be documentation for each tool, showing the user
the minimum number of values required, the types of variables, and whether the
results are absolute (possible vs impossible) or just probabilistic (plausible
vs highly implausible, under certain assumptions)."

The declarations live in `registry.TOOL_INTEGRITY` and are folded into the
specs. This file is the guard that makes an omission a BUILD FAILURE rather
than a silent gap -- the same rule the registry itself was built on: "a registry
makes the whole class unrepresentable". A tool whose epistemic class is
undeclared is worse than undocumented, because the card would then have to
guess, and the guess a reader sees is indistinguishable from a fact.
"""

import pytest

from forensic_metascience_ai_toolkit import registry as R


class TestEveryToolDeclaresItsEvidenceClass:
    def test_no_spec_is_undeclared(self):
        missing = sorted(s.name for s in R.SPECS if not s.evidence)
        assert not missing, (
            f"{len(missing)} tool(s) declare no evidence class: {missing}. "
            "Add an entry to registry.TOOL_INTEGRITY saying whether the verdict is "
            "absolute (possible vs impossible), probabilistic (plausible vs highly "
            "implausible under stated assumptions), or descriptive (no verdict)."
        )

    def test_every_declared_class_is_recognised(self):
        for s in R.SPECS:
            assert s.evidence in R.EVIDENCE_CLASSES, f"{s.name}: {s.evidence!r}"

    def test_the_table_names_no_tool_that_does_not_exist(self):
        """Drift in the other direction: an entry for a renamed or deleted tool
        is dead documentation that still reads as current."""
        orphans = sorted(set(R.TOOL_INTEGRITY) - {s.name for s in R.SPECS})
        assert not orphans, f"TOOL_INTEGRITY names non-existent tools: {orphans}"

    def test_every_tool_states_a_purpose(self):
        missing = sorted(s.name for s in R.SPECS if not s.purpose.strip())
        assert not missing, f"no one-line purpose: {missing}"


class TestEveryToolSaysWhetherItConsumesThePapersNumbers:
    """The declaration behind "NOTHING IN THE TABLES WAS CHECKED".

    That sentence is the strongest thing the report says about its own
    coverage, and it was gated on a counter that could see two tool-name
    shapes -- `*check_table` and `*_batch`. Every other per-cell check was
    invisible to it, so runs that had made a hundred checks on the paper's own
    numbers were told, in bold, that nothing in their tables had been checked.

    An UNDECLARED tool has to fail the build rather than default quietly,
    because a quiet default is what put the wrong sentence in the report.
    """

    def test_no_spec_is_undeclared(self):
        missing = sorted(s.name for s in R.SPECS if s.consumes_table_cells is None)
        assert not missing, (
            f"{len(missing)} tool(s) do not say whether they consume the paper's "
            f"reported numbers: {missing}. Add `consumes_table_cells` to the tool's "
            "registry.TOOL_INTEGRITY entry -- True if its inputs are the paper's own "
            "values (means, SDs, counts, percentages, estimates, intervals, group "
            "sizes, p-values), False if it takes a path, free text, a design "
            "declaration, or a quantity we computed. The coverage counter reads this "
            "set, and a tool missing from it makes the report deny work it did."
        )

    def test_every_tool_check_table_routes_to_is_declared_a_consumer(self):
        """The one part of this that IS derivable, used as a closure check.

        `dispatch.DISPATCH` names the tools a typed cell is routed to. Each of
        those consumes a table cell BY CONSTRUCTION, so a False there would be
        two files that both claim to be the truth contradicting each other.
        """
        from forensic_metascience_ai_toolkit.dispatch import DISPATCH

        routed = {t for tools in DISPATCH.values() for t in tools}
        undeclared = sorted(routed - R.cell_consuming_tools())
        assert not undeclared, (
            f"dispatch routes table cells to {undeclared}, but the registry says "
            "they do not consume table cells"
        )

    def test_the_set_is_asked_for_not_restated(self):
        """`cell_consuming_tools()` is derived from the specs, not a literal."""
        assert R.cell_consuming_tools() == {
            s.name for s in R.SPECS if s.consumes_table_cells}
        assert "check_summation" in R.cell_consuming_tools()
        # An extractor is not a check: it produces the cells, it does not
        # consume them, and counting one would suppress a true denial.
        assert "extract_xml" not in R.cell_consuming_tools()


class TestAssumptionsAreDeclaredWhereTheyBite:
    def test_a_probabilistic_tool_must_say_what_it_assumes(self):
        """`probabilistic` MEANS "true under assumptions". Declaring the class
        and then listing none states a premise and hides it."""
        bad = sorted(s.name for s in R.SPECS
                     if s.evidence == R.EVIDENCE_PROBABILISTIC and not s.assumptions)
        assert not bad, f"probabilistic with no assumptions declared: {bad}"

    def test_an_absolute_tool_states_the_preconditions_of_its_exactness(self):
        """No tool in this codebase is unconditionally exact: each depends on a
        stated bound, a data type, a printed precision, or a value being printed
        rather than read off a figure. Saying `absolute` without naming the
        precondition invites the reader to over-trust it."""
        bad = sorted(s.name for s in R.SPECS
                     if s.evidence == R.EVIDENCE_ABSOLUTE and not s.assumptions)
        assert not bad, f"absolute with no preconditions declared: {bad}"

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_assumptions_read_as_sentences_not_labels(self, spec):
        """These are shown to a researcher beside a finding, so a bare token
        like `normality` does not tell them what would invalidate it.

        Sentence-ness is tested by length, word count and a full stop -- NOT by
        an initial capital: many of these correctly open with an identifier
        ("n must be the true denominator", "decimals_mean and decimals_sd must
        be the PRINTED precision"), and demanding a capital there would push the
        text away from naming the actual parameter.
        """
        for a in spec.assumptions:
            assert len(a) >= 30, f"{spec.name}: too terse to act on: {a!r}"
            assert len(a.split()) >= 5, f"{spec.name}: not a sentence: {a!r}"
            assert a.rstrip().endswith("."), f"{spec.name}: unterminated: {a!r}"


class TestTheLadderRuleHolds:
    """Only bound-free arithmetic may reach `impossible`. This is the rule the
    codebase enforces case by case; here it is checked as a property."""

    def test_only_absolute_tools_may_reach_impossible(self):
        for s in R.SPECS:
            ceiling = s.severity_ceiling()
            if s.evidence != R.EVIDENCE_ABSOLUTE:
                assert ceiling != "impossible", (
                    f"{s.name} is {s.evidence} but its ceiling is `impossible`"
                )

    def test_a_descriptive_tool_renders_no_verdict(self):
        for s in R.SPECS:
            if s.evidence == R.EVIDENCE_DESCRIPTIVE:
                assert s.severity_ceiling() == "indeterminate", s.name

    def test_an_undeclared_spec_would_have_no_ceiling_at_all(self):
        """The failure mode this replaced: `severity_ceiling` fell open to
        `indeterminate`, so an UNDECLARED tool was indistinguishable from one
        declared `descriptive` -- an undocumented GRIM would have printed "this
        tool cannot accuse" on the very card meant to state its status."""
        from dataclasses import replace
        undeclared = replace(R.BY_NAME["grim_check"], evidence="")
        assert undeclared.severity_ceiling() is None


class TestTheCardIsUsable:
    def test_a_precision_param_counts_toward_the_minimum_input_set(self):
        """`ToolSpec.call` REFUSES a check whose printed precision is missing,
        so a card omitting it tells the reader the opposite of what the tool
        does -- and that refusal is the fix for a measured 41.1% of GRIM rows
        falsely reported `impossible` on a defaulted 2 dp."""
        card = R.BY_NAME["grim_check"].integrity_card()
        names = {p["name"] for p in card["minimum_inputs"]}
        assert "decimals" in names
        assert {"mean", "n"} <= names

    def test_no_input_is_listed_as_both_required_and_optional(self):
        for s in R.SPECS:
            card = s.integrity_card()
            req = {p["name"] for p in card["minimum_inputs"]}
            opt = {p["name"] for p in card["optional_inputs"]}
            assert not (req & opt), f"{s.name}: {req & opt}"

    def test_the_precision_role_is_reachable(self):
        """Every precision param is also a guard, so testing guard first made
        this role unreachable across all 47 specs."""
        card = R.BY_NAME["grim_check"].integrity_card()
        roles = {p["name"]: p["role"] for p in card["minimum_inputs"]}
        assert roles["decimals"] == "precision"

    def test_the_card_explains_the_class_in_words(self):
        for s in R.SPECS:
            card = s.integrity_card()
            assert card["evidence_meaning"], s.name

    def test_the_known_tie_limitation_is_disclosed_to_the_reader(self):
        """grimu_check can brand a scipy/R tie-corrected Mann-Whitney p
        `impossible`. Until that is resolved the card must say so, because the
        alternative is an undisclosed known false-accusation path."""
        text = " ".join(R.BY_NAME["grimu_check"].assumptions).lower()
        assert "tie" in text


class TestTheLadderHoldsAtRUNTIME:
    """The declaration-level ladder test above reads only the TABLE.

    It passed while four tools emitted severities their declared ceiling
    forbids, because nothing drove the code. Every one was also a false
    accusation: `check_regression`, `check_sd_or_se` and `rivets_independent_t`
    each answered a NEGATIVE standard error or SD with `impossible`, and
    `parse_table` -- declared descriptive -- lifted a `suspicious` reconciliation
    verdict to its top level.

    A negative dispersion is never something an analysis produces. It is an en
    dash, or a range separator like "0.4 - 0.9", that OUR parse read as a minus.
    Answering it with the top severity publishes our extraction bug in the
    grammar of an accusation. `recalc_independent_t` had it right all along and
    refuses as `indeterminate`.

    So this class drives the guard and edge inputs and asserts the EMITTED
    severity never exceeds `severity_ceiling()`.
    """

    ORDER = ["consistent", "indeterminate", "suspicious", "highly_suspicious",
             "impossible"]

    #: Inputs that historically reached a top-severity branch early, before any
    #: real arithmetic -- the trivial-precondition guards.
    EDGE_CALLS = [
        ("check_regression", {"b": 1.2, "se": -0.4}),
        ("check_regression", {"b": 1.2, "se": 0.0}),
        ("check_sd_or_se", {"reported_value": -0.2, "n": 30}),
        ("rivets_independent_t", {"mean1": 5.0, "sd1": -1.0, "n1": 20,
                                  "mean2": 6.0, "sd2": 1.0, "n2": 20}),
        ("parse_table", {"source": "| var | v |\n| x | 1.0 (0.5) |",
                         "cross_check": "| var | v |\n| x | 2.0 (0.5) |"}),
        ("check_summation", {"values": [1.0, 2.0], "expected_sum": 99.0}),
        ("check_estimate_ci", {"estimate": 1.5, "ci_low": 2.0, "ci_high": 1.0}),
        ("stalt_check", {"calculated_p": 0.9, "reported_threshold": "<0.001"}),
    ]

    @pytest.mark.parametrize("name,args", EDGE_CALLS,
                             ids=[f"{n}-{i}" for i, (n, _) in enumerate(EDGE_CALLS)])
    def test_the_emitted_severity_respects_the_declared_ceiling(self, name, args):
        spec = R.BY_NAME[name]
        out = spec.call(args)
        emitted = out.get("severity")
        if emitted is None:
            return
        ceiling = spec.severity_ceiling()
        assert ceiling is not None, f"{name} is undeclared"
        assert self.ORDER.index(emitted) <= self.ORDER.index(ceiling), (
            f"{name} emitted {emitted!r} but is declared {spec.evidence!r}, "
            f"whose ceiling is {ceiling!r}"
        )

    @pytest.mark.parametrize("name,args", [
        ("check_regression", {"b": 1.2, "se": -0.4}),
        ("check_sd_or_se", {"reported_value": -0.2, "n": 30}),
        ("rivets_independent_t", {"mean1": 5.0, "sd1": -1.0, "n1": 20,
                                  "mean2": 6.0, "sd2": 1.0, "n2": 20}),
    ])
    def test_a_negative_dispersion_is_refused_not_accused(self, name, args):
        """OUR parse failure must never be reported as their impossibility --
        and the sibling recalc_independent_t already sets the standard."""
        out = R.BY_NAME[name].call(args)
        assert out["severity"] == "indeterminate", name

    def test_the_sibling_that_set_the_standard_still_agrees(self):
        from forensic_metascience_ai_toolkit.tools.ttest import recalc_independent_t
        assert recalc_independent_t(5.0, -1.0, 20, 6.0, 1.0, 20)["severity"] == \
            "indeterminate"


class TestTheCardsReachAReader:
    """49 complete, tested evidence cards that no production surface read.

    Eleventh instance in this repo of build-test-never-consume. The cost is not
    only that readers could not see them: the FIRST thing rendering them
    revealed was that `bayesian_table1_dispersion`'s card had gone stale --
    still describing a percentile bootstrap that had been replaced by an exact
    chi-square null, and still claiming two quarantines that had been released
    the same day. Nobody proof-reads what nobody renders.
    """

    def test_a_glossary_is_rendered_for_the_tools_that_ran(self):
        from forensic_metascience_ai_toolkit.report_render import _render_check_glossary
        md = "\n".join(_render_check_glossary({"tools_run": ["grim_check", "statcheck"]}))
        assert "## What each check does" in md
        assert "`grim_check`" in md and "`statcheck`" in md
        # the three things the card exists to say
        assert "absolute" in md.lower()
        assert "Strongest verdict it may reach" in md
        assert "It assumes:" in md

    def test_a_tool_it_cannot_describe_is_named_not_dropped(self):
        """Silently omitting one would make the glossary look complete."""
        from forensic_metascience_ai_toolkit.report_render import _render_check_glossary
        md = "\n".join(_render_check_glossary({"tools_run": ["grim_check", "no_such_tool"]}))
        assert "no_such_tool" in md
        assert "cannot describe" in md

    def test_no_run_no_glossary(self):
        from forensic_metascience_ai_toolkit.report_render import _render_check_glossary
        assert _render_check_glossary({}) == []
        assert _render_check_glossary({"tools_run": []}) == []

    def test_the_dispersion_card_matches_the_shipped_tool(self):
        """The specific drift that rendering caught. `table1_dispersion` no
        longer uses a bootstrap for its verdict and no longer quarantines, so a
        card saying otherwise misdescribes the check to the reader it is for."""
        import forensic_metascience_ai_toolkit.registry as R
        text = " ".join(R.TOOL_INTEGRITY["bayesian_table1_dispersion"]["assumptions"]).lower()
        assert "exact chi-square null" in text
        assert "quarantined" not in text, "both quarantines were released 2026-08-10"
        assert "the bootstrap resamples" not in text, "the bootstrap no longer drives the verdict"
