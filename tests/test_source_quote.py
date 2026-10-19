"""Every check says WHERE its numbers came from, and we check that it is true.

Greg, 2026-08-09: "I would like all the tools to report the exact quote/context
of the paper from which given values were extracted."

The ledger recorded that grim_check was called with mean=48.90. NOTHING recorded
that 48.90 was the Age row of Table 1. So a reader auditing a finding had to go
and locate the value themselves -- the work this was meant to spare them -- and
an evaluating agent could not distinguish a correctly-read value from a misread
one at all.
"""

import pytest

from metascience_agent import registry as R
from metascience_agent.quotes import normalise, verify_ledger

GRIM = dict(mean=5.19, n=28, decimals=2, data_type="likert")


class TestTheToolSurfaceRecordsTheClaim:
    def test_a_verdict_rendering_tool_accepts_a_source_quote(self):
        assert "source_quote" in R.BY_NAME["grim_check"].schema()
        assert "source_locator" in R.BY_NAME["grim_check"].schema()

    def test_an_extractor_does_not(self):
        """An extractor has no input value to source. Asking anyway would teach
        the model to supply one pro forma -- the same
        teach-the-reader-to-skip-it failure the guard alarm had."""
        assert "source_quote" not in R.BY_NAME["extract_pdf"].schema()

    def test_every_tool_that_renders_a_verdict_has_it(self):
        missing = sorted(
            s.name for s in R.SPECS
            if s.evidence != R.EVIDENCE_DESCRIPTIVE
            and "source_quote" not in {p.name for p in s.params})
        assert not missing, missing

    def test_the_unsourced_set_is_pinned_and_every_member_is_justified(self):
        """The closure assertion -- the one that catches the next gap.

        "Renders a verdict" was the wrong predicate and this file used to encode
        it, which is exactly why the gap below survived: `multiplicity_report` is
        classified descriptive, so the rule above skipped it, while 21 archived
        calls fed it 147 p-values transcribed from across the paper and 9
        findings cite its verdict. The right predicate is whether the tool is
        HANDED VALUES read off the page, and the only durable way to enforce it
        is to pin the exhaustive list of tools that legitimately have none.

        A new tool landing in this set fails here and has to be justified rather
        than silently inheriting an exemption.
        """
        unsourced = {s.name for s in R.SPECS
                     if "source_quote" not in {p.name for p in s.params}}
        assert unsourced == {
            # Handed a FILE PATH; they produce the values, they consume none.
            "extract_pdf", "extract_xml", "extract_html", "extract_supplement",
            "extract_figures", "get_table", "get_supplement_table",
            # Handed a cell grid that an extractor above already produced.
            "parse_cells_typed",
            # Handed CODE, not paper values. The numbers a script computes
            # arrive back as captured output; the sourcing obligation lives on
            # the FINDING that cites them (verbatim quotes for the script's
            # inputs, per rulebook rule 15 / findings_v2.md), because the
            # residual risk is transcription INTO the code -- a per-call
            # source_quote would attest the wrong thing.
            "run_python_script",
            # The SAME grid, re-read under a declared format. It consumes no
            # value transcribed off the page -- the `raw` strings come from the
            # extractor output above, and every number it yields it produces
            # itself. The model's claim here is the DECLARATION, not a quote,
            # and it is already evidenced the right way: `misfits` returns the
            # cells that contradicted it and `n_overrides_automatic` counts the
            # ones whose own row/column labels said otherwise.
            "parse_cells_as_declared",
            # The harness GRIM sweep's table index (1.82.0): handed a PAPER
            # DIRECTORY, it reads the cells itself through
            # `prepass.paper_tables`. (`declare_table` is sourced like any
            # check, and each n it declares from prose carries a `quote`.)
            "list_tables",
            # `required_n` WAS here, on the ground that it was a pure calculator
            # and not callable by either stage. Both halves stopped being true on
            # 2026-08-16: it takes `actual_n` and returns a design comparison, and
            # it carries a source quote like any other check. Removed rather than
            # re-justified -- an exemption whose reason has expired is the kind of
            # thing this exhaustive list exists to surface.
        }, sorted(unsourced)

    def test_the_formerly_unsourced_calculator_is_now_sourced(self):
        """REVERSED 2026-08-16. This test existed to assert that `required_n`
        was unreachable, which was the entire justification for its exemption
        from the source-quote rule. Greg: "make required_n a proper check so the
        model can call it." It now carries `source_quote`, so the exemption and
        the test that guarded it both go."""
        spec = next(s for s in R.SPECS if s.name == "required_n")
        assert "source_quote" in {p.name for p in spec.params}
        assert spec.stages, "and it is offered to at least one stage"


    def test_the_three_descriptive_tools_that_consume_paper_numbers_have_it(self):
        for name in ("multiplicity_report", "r_grim_ground_truth", "r_sprite_ground_truth"):
            assert "source_quote" in R.BY_NAME[name].schema(), name

    def test_the_quote_is_echoed_onto_the_result(self):
        r = R.BY_NAME["grim_check"].call(
            {**GRIM, "source_quote": "M = 5.19 (n = 28)",
             "source_locator": "Results, paragraph 2"})
        assert r["source_quote"] == "M = 5.19 (n = 28)"
        assert r["source_locator"] == "Results, paragraph 2"
        assert r["source_quote_supplied"] is True

    def test_it_never_reaches_the_arithmetic(self):
        """A meta param that leaked into kwargs would be a TypeError on every
        call; worse, a check could start reasoning about the quote."""
        with_quote = R.BY_NAME["grim_check"].call({**GRIM, "source_quote": "x" * 40})
        without = R.BY_NAME["grim_check"].call(dict(GRIM))
        assert with_quote["severity"] == without["severity"]

    def test_absence_is_RECORDED_not_merely_silent(self):
        """A field that is simply missing is indistinguishable from one nobody
        looked for -- which is how the findings' own `quote` went 505 calls
        without anyone noticing it was never verified."""
        r = R.BY_NAME["grim_check"].call(dict(GRIM))
        assert r["source_quote"] is None
        assert r["source_quote_supplied"] is False

    def test_a_blank_quote_counts_as_absent(self):
        r = R.BY_NAME["grim_check"].call({**GRIM, "source_quote": "   "})
        assert r["source_quote_supplied"] is False

    @pytest.mark.parametrize(
        "forged", ["source_quote_verified", "source_verified", "quote_verified"])
    def test_the_model_cannot_certify_its_own_quote(self, forged):
        """The tool surface is the one place a forged verdict could enter
        looking native. A self-assessment written by the party being checked is
        not a check -- the rule that already governs `quote_verified` on
        findings and `reproduction_valid` on commands."""
        r = R.BY_NAME["grim_check"].call({**GRIM, "source_quote": "x" * 40,
                                          forged: "verbatim"})
        assert forged not in r


class TestThePipelineDecidesWhetherTheQuoteIsTrue:
    HAY = {"body": normalise(
        "Participants rated agreement on a 1-7 scale (M = 5.19, n = 28).")}

    def _ledger(self, *quotes):
        return [{"tool": "grim_check", "input": ({"source_quote": q} if q else {})}
                for q in quotes]

    def test_a_real_quote_verifies(self):
        led = self._ledger("rated agreement on a 1-7 scale (M = 5.19, n = 28)")
        verify_ledger(led, self.HAY)
        assert led[0]["source_quote_verified"] == "verbatim"

    def test_an_absent_quote_is_reported_as_OUR_search_failing(self):
        led = self._ledger("a sentence that appears nowhere in this paper")
        verify_ledger(led, self.HAY)
        assert led[0]["source_quote_verified"] == "unverified"

    def test_a_forged_verdict_in_the_ledger_is_stripped_before_judging(self):
        led = [{"tool": "t", "input": {"source_quote": "nowhere at all, truly"},
                "source_quote_verified": "verbatim"}]
        verify_ledger(led, self.HAY)
        assert led[0]["source_quote_verified"] == "unverified"

    def test_an_unreadable_paper_stamps_nothing(self):
        """Marking every call `unverified` because WE could not read the paper
        would report our failure as a fact about their work."""
        led = self._ledger("rated agreement on a 1-7 scale (M = 5.19, n = 28)")
        summary = verify_ledger(led, {})
        assert "source_quote_verified" not in led[0]
        assert summary["checked"] is False

    def test_the_summary_counts_coverage_not_just_verdicts(self):
        """"12 of 140 calls said where their numbers came from" is a fact about
        the review that no single entry reveals."""
        led = self._ledger(
            "rated agreement on a 1-7 scale (M = 5.19, n = 28)", None, None)
        s = verify_ledger(led, self.HAY)
        assert (s["calls"], s["with_quote"], s["without_quote"]) == (3, 1, 2)
        assert s["verbatim"] == 1


class TestTheDenominatorCountsOnlyChecksThatCouldHaveQuoted:
    """A ledger is mostly extraction. Scoring `extract_xml` as an unsourced
    check reports a design decision -- extractors were deliberately never given
    the argument -- as a coverage failure, and dilutes the number until nobody
    watches it."""

    HAY = {"body": normalise("Mean age was 48.9 years (SD 7.1).")}

    def test_an_extractor_is_not_counted_as_an_unsourced_check(self):
        led = [{"tool": "mcp__forensic_metascience__extract_xml", "input": {}},
               {"tool": "Read", "tool_short": "Read", "input": {}},
               {"tool": "mcp__forensic_metascience__grim_check", "input": {}}]
        s = verify_ledger(led, self.HAY)
        assert (s["calls"], s["eligible"], s["without_quote"]) == (3, 1, 1)

    def test_the_mcp_prefix_does_not_hide_a_check_from_the_denominator(self):
        led = [{"tool": "mcp__forensic_metascience__grim_check", "input": {}}]
        assert verify_ledger(led, self.HAY)["eligible"] == 1

    def test_an_unrecognised_tool_that_did_quote_still_counts(self):
        """A renamed or newly added check must not fall silently out of the
        denominator -- that would improve the coverage number by losing work."""
        led = [{"tool": "some_new_check", "input": {"source_quote": "Mean age was 48.9 years"}}]
        s = verify_ledger(led, self.HAY)
        assert (s["eligible"], s["with_quote"], s["verbatim"]) == (1, 1, 1)


