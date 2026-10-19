"""render_report_v2: the structural guarantees are the renderer's."""

from forensic_metascience_ai_toolkit.report_v2 import render_report_v2
import pytest


def doc(findings, adj=None, **top):
    d = {"schema_version": "2.0", "paper_id": "10.1234--x", "run_id": "r_1",
         "findings": findings, "unchecked": [],
         "adjudication": adj or {"ran": True, "verdict": "unresolved",
                                 "paper_severity": 4, "confidence": "low",
                                 "summary": "the narrative",
                                 "headline_finding_id": "f_a"}}
    d.update(top)
    return d


def f(fid, sev, action="kept", **kw):
    row = {"finding_id": fid, "producer": "tool_expert",
           "technique": "grim_check", "title": f"title for {fid}",
           "description": f"description for {fid}", "outcome": "problem",
           "severity": sev, "provisional_severity": sev,
           "severity_is_provisional": False, "impossible": False,
           "adjudication": {"action": action, "rationale": "because"}}
    row.update(kw)
    return row


class TestStructure:
    def test_headline_first_and_severity_descending(self):
        md = render_report_v2(doc([f("f_a", 6), f("f_b", 3), f("f_c", 5)]))
        assert md.index("## Headline") < md.index("## Findings")
        a, b, c = (md.index("title for f_a"), md.index("title for f_b"),
                   md.index("title for f_c"))
        assert a < c < b, "findings must order by final severity descending"
        assert "Level 6 — " in md

    def test_discarded_findings_stay_visible(self):
        rows = [f("f_a", 4),
                f("f_x", None, action="discarded",
                  adjudication={"action": "discarded",
                                "category": "misapplication",
                                "rationale": "GRIM on a continuous scale"})]
        md = render_report_v2(doc(rows))
        assert "set aside by the adjudicator" in md
        assert "GRIM on a continuous scale" in md
        assert "title for f_x" in md

    def test_not_checked_section_is_always_present(self):
        md = render_report_v2(doc([f("f_a", 4)]))
        assert "## What we could NOT check" in md
        assert "claim about the record" in md
        md2 = render_report_v2(doc([f("f_a", 4)],
                                   unchecked=[{"location": "Table 3",
                                               "reason": "image-only"}]))
        assert "Table 3: image-only" in md2

    def test_provisional_banner_when_the_adjudicator_did_not_run(self):
        rows = [dict(f("f_a", 4), severity_is_provisional=True,
                     impossible=True, cross_check="not_run")]
        rows[0].pop("adjudication")
        md = render_report_v2(doc(rows, adj={"ran": False,
                                             "skipped_reason": "budget"}))
        assert "SEVERITIES ARE PROVISIONAL" in md
        assert "cross-check not run" in md

    def test_disclaimer_and_channel_absences_render(self):
        md = render_report_v2(
            doc([f("f_a", 4)],
                channels={"image_forensics": {"state": "refused",
                                              "detail": "no rasters"}}),
            run_meta={"analysed_at": "2026-08-21", "llm_backend": "claude"},
            limitations=["the science_agent stage failed"])
        assert "## About this report" in md
        assert "image_forensics" in md and "no rasters" in md
        assert "the science_agent stage failed" in md


class TestALostDocketIsNotReportedAsCoverage:
    """MEASURED 2026-08-22, `10.1186--s12889-025-24026-y` on grok-4.6.

    The tool agent made 76 forensic calls, then filed a docket with one
    finding, `coverage: {"stats_found": 0, "tools_run": []}`, and no
    `unchecked` entries; the retry was empty too. The published report then
    carried THREE numbers for one quantity -- the adjudicator's summary said
    "Twenty-six table checks were consistent with the printed cells",
    Limitations said "Checks recorded as passing: 0", and Coverage said
    "tools run: none recorded" -- and told the reader "Nothing was recorded as
    uncheckable" on a paper where an entire agent's output had been lost.
    """

    def _doc(self, *, tools_run, checks_passed, filed_passes):
        findings = [
            {"finding_id": f"f_p{i}", "outcome": "pass", "producer": "tool_expert",
             "technique": "check_count_percent", "title": f"pass {i}",
             "description": "d", "severity": None}
            for i in range(filed_passes)
        ] + [
            {"finding_id": "f_x", "outcome": "problem", "producer": "science_error",
             "technique": "internal_contradiction", "severity": 3,
             "title": "Abstract OR disagrees with Table 5",
             "description": "The abstract and the table print different odds ratios."},
        ]
        return {
            "schema_version": "2.0", "paper_id": "10.1186--s12889",
            "run_id": "r_test", "findings": findings,
            "adjudication": {"ran": True, "verdict": "unresolved",
                             "paper_severity": 3, "confidence": "medium",
                             "summary": "s"},
            "coverage": {"stats_found": 0 if not tools_run else 96,
                         "tools_run": list(tools_run)},
            "unchecked": [],
            "checks_tally": {"checks_passed": checks_passed,
                             "of_which_collapsed_by_check_table": checks_passed,
                             "checks_flagged": 5,
                             "checks_total": checks_passed + 5},
            "channels": {},
        }

    def test_the_lost_docket_is_named_in_all_three_places(self):
        md = render_report_v2(self._doc(tools_run=[], checks_passed=26,
                                        filed_passes=0))
        nc = md.split("## What we could NOT check", 1)[1].split("\n## ", 1)[0]
        assert "not a coverage statement" in nc
        # The old sentence may still follow, but it must not stand alone.
        assert nc.index("not a coverage statement") < nc.index(
            "Nothing was recorded as uncheckable")

        lim = md.split("## Limitations", 1)[1].split("\n## ", 1)[0]
        assert "0 filed as findings, 26 on the tool ledger" in lim
        assert "The two counts differ" in lim

        cov = md.split("## Coverage", 1)[1]
        assert "did not survive serialization" in cov
        assert "not because nothing ran" in cov

    def test_a_healthy_report_says_none_of_it(self):
        md = render_report_v2(self._doc(
            tools_run=["extract_xml", "check_table"], checks_passed=12,
            filed_passes=12))
        assert "not a coverage statement" not in md
        assert "did not survive serialization" not in md
        assert "The two counts differ" not in md
        assert "- Checks recorded as passing: 12; undecided: 0." in md


    def test_a_recovered_tool_list_still_says_the_docket_was_lost(self):
        """THE QUIET WAY A GUARD STOPS GUARDING.

        `_coverage_with_ledger_fallback` rebuilds `tools_run` from the
        transcript, so `tools_run` is no longer empty on exactly the papers
        this section exists for. Only the LIST was recovered -- the findings,
        the anatomy and the register are still gone -- so keying the warning on
        emptiness alone would have switched it off the moment the recovery
        landed.
        """
        doc = self._doc(tools_run=[], checks_passed=26, filed_passes=0)
        doc["coverage"] = {"stats_found": 0,
                           "tools_run": ["check_table", "grim_check"],
                           "tools_run_source": "ledger"}
        md = render_report_v2(doc)
        assert "not a coverage statement" in md
        cov = md.split("## Coverage", 1)[1]
        assert "recovered from the tool-call ledger" in cov
        assert "did not survive serialization" in cov
        assert "the findings, anatomy and statistics register" in cov


class TestReportingConventionsAreRendered:
    """Greg, 2026-08-26: a rescued check should still be visible.

    `agent.py` computed both convention rates from the start and `checks_tally`
    carried them into every findings-v2 document. Nothing rendered them, so a
    reader saw the rescued verdict and never the rescue.
    """

    def _doc(self, trunc=0, pop=0, denom=13):
        return {"findings": [], "checks_tally": {
            "checks_total": denom,
            "rounding_convention": {"n_fit_only_under_truncation": trunc,
                                    "n_granularity_checks": denom},
            "sd_convention": {"n_fit_only_under_population_sd": pop,
                              "n_granularity_checks": denom}}}

    def test_a_truncation_rescue_reaches_the_reader(self):
        md = render_report_v2(self._doc(trunc=7))
        assert "## Reporting conventions" in md
        assert "**7 of 13**" in md and "TRUNCATES" in md

    def test_zero_is_printed_rather_than_omitted(self):
        """'0 of 13' says we looked. An absent section says nothing at all,
        and a reader cannot tell those apart."""
        md = render_report_v2(self._doc(trunc=0, pop=0))
        assert "**0 of 13**" in md

    def test_the_section_never_reads_as_an_accusation(self):
        md = render_report_v2(self._doc(trunc=12))
        i = md.find("## Reporting conventions")
        section = md[i:md.find("\n## ", i + 5)]
        assert "NOT findings" in section
        assert "rate is the signal" in section
        assert "house style" in section

    def test_both_conventions_are_named_separately(self):
        """Different innocent explanations lead to different follow-up
        questions, so they may not be folded into one number."""
        md = render_report_v2(self._doc(trunc=3, pop=5))
        assert "**3 of 13**" in md and "**5 of 13**" in md
        assert "TRUNCATES" in md and "POPULATION" in md

    def test_no_denominator_means_no_section_rather_than_a_bare_count(self):
        doc = {"findings": [], "checks_tally": {
            "rounding_convention": {"n_fit_only_under_truncation": 4}}}
        assert "## Reporting conventions" not in render_report_v2(doc)

    def test_a_document_predating_the_tally_is_unaffected(self):
        assert "## Reporting conventions" not in render_report_v2(
            {"findings": [], "checks_tally": {}})


class TestAReproductionCommandIsNotOfferedUntilItValidates:
    """`report_render` deleted its own `_render_reproduction` and left the rule
    in a comment: "Anything that reintroduces a command into this renderer has
    to reintroduce that check too." `report_v2` reintroduced the command and
    not the check.

    IT MATTERS BECAUSE MOST COMMANDS DO NOT RUN. Executing all 523 distinct
    reproduction strings in this repo's archive: 60 (11.5%) exited 0, 352
    (67.3%) passed the static check and then exited non-zero. Measured on the
    live ajcp run, only 6 of 24 commands actually run. A command that errors on
    first use reads as a broken tool, and the failure is ours in every case.
    """

    def _line(self, **kw):
        from forensic_metascience_ai_toolkit.report_v2 import _reproduction_line
        return _reproduction_line(kw)

    def test_a_validated_command_is_offered_to_paste(self):
        out = self._line(reproduction="metascience grim --mean 3.2 --n 64",
                         reproduction_valid=True)
        assert out == "Reproduce: `metascience grim --mean 3.2 --n 64`"

    def test_a_failed_command_names_our_failure_not_the_papers(self):
        out = self._line(reproduction="metascience grim {mean}",
                         reproduction_valid=False,
                         reproduction_problem="contains placeholder")
        assert "Reproduce: not available" in out
        assert "the review" in out          # ours, not the paper's
        assert "{mean}" not in out          # never our raw stderr or template

    def test_an_unchecked_command_is_not_called_reproducible(self):
        """The live case: the parallel path recorded no verdict, and the old
        renderer printed the command as though it worked."""
        out = self._line(reproduction="metascience grim --mean 3.2 --n 64")
        assert "UNVERIFIED" in out
        assert not out.startswith("Reproduce:")
        assert "metascience grim --mean 3.2 --n 64" in out

    def test_no_command_produces_no_line(self):
        assert self._line() is None
        assert self._line(reproduction="   ") is None

    def test_it_agrees_with_the_viewer_on_all_three_states(self):
        """A reader of the markdown and a reader of the bundle must be told the
        same thing; `bundle.reproHtml` treats a null verdict as a template and
        a false one as a failure, and only true as paste-ready."""
        paste = self._line(reproduction="metascience x", reproduction_valid=True)
        unver = self._line(reproduction="metascience x")
        failed = self._line(reproduction="metascience x", reproduction_valid=False)
        assert paste.startswith("Reproduce: `")
        assert not unver.startswith("Reproduce: `")
        assert not failed.startswith("Reproduce: `")


class TestAQuoteIsNotPrintedAsThePapersWordsUnlessItIs:
    """A `>` blockquote under a finding reads as the paper speaking.

    Corpus census of this repo's v2 archive: 137 findings carry a quote, and 11
    of them are NOT the paper's words -- 7 `stitched`, 4 `unverified`.
    `quotes.classify` had already decided this and already written the sentence
    explaining it; `report_v2` read neither field (`grep quote_verified` in that
    module returned nothing), while the legacy renderer gates on it at
    report_render.py:1194/1206 and the viewer at bundle.py:6687. A reader of the
    markdown was told something a reader of either other surface was not.
    """

    def _lines(self, **f):
        from forensic_metascience_ai_toolkit.report_v2 import _quote_lines
        return _quote_lines(f)

    @pytest.mark.parametrize("verdict", ["verbatim", "elided"])
    def test_a_located_quote_is_printed_bare(self, verdict):
        """`LOCATED_VERDICTS` is the codebase's own definition of located."""
        lines = self._lines(quote="81.3% reported compliance",
                            quote_verified=verdict)
        assert lines == ["> 81.3% reported compliance"]

    @pytest.mark.parametrize("verdict", ["stitched", "unverified", "absent"])
    def test_an_unlocated_quote_is_labelled(self, verdict):
        lines = self._lines(quote="some text", quote_verified=verdict)
        assert lines[0] == "> some text"
        assert any("Not the paper's words" in l for l in lines)

    def test_it_is_labelled_not_suppressed(self):
        """A stitched quote is still the best pointer to where the finding came
        from; dropping it would leave the finding unsupported. What it must not
        do is claim to be a passage a reader can find."""
        lines = self._lines(quote="Operative time 44.8 vs 42.5",
                            quote_verified="stitched")
        assert "> Operative time 44.8 vs 42.5" in lines

    def test_it_reuses_the_pipelines_own_explanation(self):
        problem = ("Every number here appears in the paper, but this exact "
                   "sentence does not.")
        lines = self._lines(quote="x", quote_verified="stitched",
                            quote_problem=problem)
        assert any(problem in l for l in lines)

    def test_a_missing_verdict_is_not_read_as_verified(self):
        """Absent is not the same as located -- the house failure mode."""
        lines = self._lines(quote="some text")
        assert any("no verification was recorded" in l for l in lines)

    def test_no_quote_produces_no_lines(self):
        assert self._lines() == []
        assert self._lines(quote="   ", quote_verified="verbatim") == []


class TestTruncatedStageBanner:
    """A budget-truncated stage must announce itself IN report.md, not only in
    run_meta / the viewer (AGENTS.md: 'A budget-truncated run must announce
    itself'). The serial pipeline's PARTIAL COVERAGE limitation went with it in
    v1.27.0 and nothing replaced it until this banner."""

    @staticmethod
    def _meta(**stages):
        base = {"is_error": False, "error_subtype": "success",
                "truncated_by_budget": False, "truncated_by_timeout": False}
        return {"stages": {k: {**base, **v} for k, v in stages.items()}}

    def test_a_budget_truncated_stage_is_named_near_the_top(self):
        rm = self._meta(
            tool_agent={"is_error": True,
                        "error_subtype": "error_max_budget_usd",
                        "truncated_by_budget": True},
            science_agent={}, adjudicator={})
        md = render_report_v2(doc([f("f_a", 6)]), rm)
        assert "PARTIAL COVERAGE" in md
        assert "Tools agent (ran out of budget)" in md
        assert "Scientific proofreading agent" not in md.split("## Headline")[0]
        assert md.index("PARTIAL COVERAGE") < md.index("## Headline")
        assert md.index("PARTIAL COVERAGE") < md.index("**Verdict:")

    def test_each_truncated_stage_is_named_with_its_cause(self):
        rm = self._meta(tool_agent={"truncated_by_budget": True},
                        science_agent={"truncated_by_timeout": True})
        banner = [l for l in render_report_v2(doc([f("f_a", 4)]), rm).splitlines()
                  if "PARTIAL COVERAGE" in l]
        assert len(banner) == 1
        assert "Tools agent (ran out of budget)" in banner[0]
        assert ("Scientific proofreading agent (was cut off by the time limit)"
                in banner[0])

    def test_no_banner_when_no_stage_was_truncated(self):
        rm = self._meta(tool_agent={}, science_agent={}, adjudicator={})
        assert "PARTIAL COVERAGE" not in render_report_v2(doc([f("f_a", 4)]), rm)
        assert "PARTIAL COVERAGE" not in render_report_v2(doc([f("f_a", 4)]))
        assert "PARTIAL COVERAGE" not in render_report_v2(doc([f("f_a", 4)]),
                                                          {"stages": None})

    def test_ledger_only_attempt_rows_do_not_trigger_it(self):
        """`_add_ledger_only_attempts` rows are billed retries, not stages."""
        rm = self._meta(tool_agent={})
        rm["stages"]["tool_agent_retry"] = {"source": "spend_ledger",
                                            "truncated_by_budget": True}
        assert "PARTIAL COVERAGE" not in render_report_v2(doc([f("f_a", 4)]), rm)
