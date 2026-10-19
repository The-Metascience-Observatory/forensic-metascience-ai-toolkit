"""Four places the document was unfair to itself, or unreadable about itself.

None of these is a claim about the paper. Each is a claim about OUR conduct or
OUR coverage, and each was either overstated, contradicted elsewhere in the same
bundle, or buried in noise.
"""
import json

import pytest

from tests.test_bundle import flat, review, section_html  # noqa: F401

from metascience_agent.bundle import collect, render_viewer


class TestTheCoverageCaveatTravelsWithItsNumber:
    """A3. The Coverage page says the figure UNDERSTATES what was done. That
    sentence stayed on the Coverage page while the bare number appeared on the
    landing screen, directly beneath the verdict."""

    def _payload(self, review, checked=0, consumable=525):
        """The bullet reads `report_obj.coverage_summary.checkable`, which is
        where the editorial stage records it -- not `D.coverage`."""
        p = collect(review)
        ro = p.setdefault("report_obj", {})
        ro.setdefault("coverage_summary", {})["checkable"] = {
            "n_consumable": consumable, "cells_checked_via_check_table": checked}
        return p

    def test_the_understatement_is_stated_where_the_number_is(self, review, tmp_path):
        html = flat(section_html(self._payload(review), "overview", tmp_path))
        assert "0 of 525" in html
        assert "UNDERSTATES" in html

    def test_it_says_what_the_number_actually_counts(self, review, tmp_path):
        """"0 of 525" under a verdict reads as "we checked nothing". It counts
        only the batch path; a check called directly on a cell scores zero."""
        html = flat(section_html(self._payload(review), "overview", tmp_path))
        assert "check_table" in html
        assert "called directly on a cell scores nothing here" in html

    def test_knowingly_wrong_in_our_own_disfavour_is_still_wrong(self, review, tmp_path):
        """A shortfall list that OVERSTATES the shortfall fails the same way as
        one that hides it: the reader cannot tell which parts to believe."""
        html = flat(section_html(self._payload(review, checked=12), "overview", tmp_path))
        assert "12 of 525" in html
        assert "rather than flattering it" in html


class TestTheAuditAndTheChainStopContradictingEachOther:
    """A4. Audit says CLEAN; the Chain of reasoning marks rows "unvalidated
    surface". Both true -- those calls emit the output schema and compute no
    statistic -- and the document never said so, leaving a careful reader to
    decide which of our own pages to believe about our own conduct."""

    def _clean_with_unvalidated(self, review, n=3):
        p = collect(review)
        p["calls"] = ([{"seq": i, "tool_short": "StructuredOutput",
                        "surface": "builtin", "validated": False}
                       for i in range(n)]
                      + [{"seq": 99, "tool_short": "grim_check",
                          "surface": "forensic_mcp", "validated": True}])
        # The verdict is driven by the sandbox audit's counters; without them
        # the page correctly says NOT RECORDED and there is no CLEAN to test.
        p["sandbox_audit"] = {"n_unvalidated_total": 0, "n_severe_total": 0,
                              "n_unbacked_findings": 0}
        return p

    def test_a_clean_verdict_explains_the_unvalidated_rows(self, review, tmp_path):
        html = flat(section_html(self._clean_with_unvalidated(review), "audit", tmp_path))
        assert "CLEAN" in html
        assert "Chain of reasoning marks 3 call(s)" in html
        assert "compute no statistic" in html

    def test_the_clean_claim_itself_is_unchanged(self, review, tmp_path):
        """Reconciling must not soften the verdict. The statement was true."""
        html = flat(section_html(self._clean_with_unvalidated(review), "audit", tmp_path))
        assert "No statistic in this report was computed by anything unaudited" in html

    def test_no_sentence_when_there_is_nothing_to_reconcile(self, review, tmp_path):
        p = collect(review)
        p["calls"] = [{"seq": 1, "tool_short": "grim_check", "validated": True}]
        p["sandbox_audit"] = {"n_unvalidated_total": 0, "n_severe_total": 0,
                              "n_unbacked_findings": 0}
        html = flat(section_html(p, "audit", tmp_path))
        assert "Chain of reasoning marks" not in html


class TestTheExcusedGuardsTableIsGrouped:
    """C10. MEASURED on the archived cerebrolysin run: stage 1 listed 11 excused
    rows carrying 3 distinct (tool, guard, reason) triples and stage 2 listed 7
    carrying 2 -- one ~200-character justification printed eleven times to
    contextualise a single genuinely defaulted guard."""

    def _audit(self, review, n=11):
        p = collect(review)
        p["guard_audit"] = {"stage1": {
            "n_excused": n, "supplied_rate": 1.0, "n_supplied": 1,
            "n_defaulted": 0, "n_guard_slots": 1, "defaulted_calls": [],
            "excused_calls": [{"seq": i, "tool": "rivets_independent_t",
                               "guard": "provenance", "default": "printed_text",
                               "why_sound": "The same long justification " * 8}
                              for i in range(n)]}}
        return p

    def test_identical_rows_collapse_to_one(self, review, tmp_path):
        html = flat(section_html(self._audit(review), "audit", tmp_path))
        assert "11&times;" in html or "11×" in html

    def test_the_justification_is_printed_once_not_eleven_times(self, review, tmp_path):
        html = flat(section_html(self._audit(review), "audit", tmp_path))
        assert html.count("The same long justification") <= 8 + 1, (
            "the repeated justification is still being printed per row")

    def test_no_call_is_hidden(self, review, tmp_path):
        """Grouping must not lose the audit trail: every sequence number is
        still printed, in the row's own cell."""
        html = flat(section_html(self._audit(review, n=4), "audit", tmp_path))
        for seq in range(4):
            assert f"#{seq}" in html.replace(", #", " #")

    def test_distinct_reasons_stay_distinct(self, review, tmp_path):
        p = self._audit(review, n=2)
        p["guard_audit"]["stage1"]["excused_calls"][1]["guard"] = "data_type"
        html = flat(section_html(p, "audit", tmp_path))
        assert "provenance" in html and "data_type" in html


class TestReproFailuresAreClassified:
    """C11. This shipped 29 rows of raw Typer usage errors -- box-drawing
    characters, truncated mid-word -- to a reader who may be a journal editor.
    It is OUR defect, not a defect in the findings, and printing it raw made it
    look like the toolkit cannot re-run its own arithmetic."""

    def _repro(self, review):
        p = collect(review)
        rm = p.setdefault("run_meta", {})
        rm["reproducibility"] = {
            "n_findings": 3, "n_valid": 0, "n_invalid": 3,
            "problems": [
                "finding[t2_respiration]: exited 2: Usage: metascience rivets-t "
                "[OPTIONS]  Error: Missing argument 'MEAN1'.",
                "finding[t3_paw_latency]: exited 2: Usage: metascience rivets-t "
                "[OPTIONS]  Error: Missing argument 'MEAN1'.",
                "finding[table1_totals]: Error: No such option: --rows",
            ]}
        return p

    def test_the_causes_are_counted(self, review, tmp_path):
        html = flat(section_html(self._repro(review), "run", tmp_path))
        assert "wrong argument shape" in html
        assert "unknown flag name" in html

    def test_findings_are_named(self, review, tmp_path):
        """`finding[0]` and `finding[11]` tell a reader nothing about which
        result they cannot re-run."""
        html = flat(section_html(self._repro(review), "run", tmp_path))
        assert "t2_respiration" in html and "table1_totals" in html

    def test_the_raw_log_is_kept_one_click_away(self, review, tmp_path):
        """An audit trail that has been tidied out of existence is not one."""
        html = flat(section_html(self._repro(review), "run", tmp_path))
        assert "the raw output, verbatim" in html
        assert "Missing argument" in html

    def test_the_framing_sentence_survives(self, review, tmp_path):
        """It was already right: a command can be mistyped and its arithmetic
        still be exactly correct."""
        html = flat(section_html(self._repro(review), "run", tmp_path))
        assert "Nothing here says the FINDING is wrong" in html


class TestTheEmittedJavascriptIsWellFormed:
    """Two defects reached the emitted JS in one edit of this file: a NULL BYTE
    in a string literal (which made `bundle.py` itself unimportable) and a
    double-escaped regex (`/finding\\\\[.../` instead of `/finding\\[.../`),
    which parsed as an unmatched paren and killed every section.

    The node harness caught the second. Nothing caught the first until Python
    refused to import the module. Both are cheap to pin.
    """

    def test_the_source_contains_no_null_bytes(self):
        import pathlib
        import metascience_agent.bundle as B
        raw = pathlib.Path(B.__file__).read_bytes()
        assert b"\x00" not in raw, "a null byte reached bundle.py"

    def test_no_double_escaped_character_class_reaches_the_js(self, review):
        r"""In a raw Python string `\\[` is TWO characters in the emitted JS and
        is never what a regex wants there."""
        html = render_viewer(collect(review))
        assert r"\\[" not in html
        assert r"\\d" not in html


class TestTheShortfallListIsScoped:
    """Wording changes twice failed to stop this section reading as "the
    pipeline had a list of tasks and abandoned it". The reason is structural: a
    limit that BOUNDS what else could be in the paper sat in the same bullet
    list as one that BEARS on a finding printed above it, so a reader could not
    tell which items weakened what they had just read."""

    def _payload(self, review):
        p = collect(review)
        ro = p.setdefault("report_obj", {})
        ro.setdefault("coverage_summary", {}).update(
            {"stats_found": 704, "stats_checked": 37})
        p.setdefault("run_meta", {})["reproducibility"] = {
            "n_findings": 33, "n_invalid": 29, "problems": ["x"]}
        return p

    def test_both_headings_appear(self, review, tmp_path):
        html = flat(section_html(self._payload(review), "overview", tmp_path))
        assert "Bears on the findings above" in html
        assert "Bounds what else could be here" in html

    def test_the_bounds_list_disclaims_weakening_any_finding(self, review, tmp_path):
        """The sentence that does the work: without it the second list still
        reads as a confession."""
        html = flat(section_html(self._payload(review), "overview", tmp_path))
        assert "Nothing in this list weakens a finding above" in html

    def test_coverage_and_reproduction_are_BOUNDS_not_bears(self, review, tmp_path):
        """'37 of 704 statistics' bounds how much was seen; a reproduction
        string that will not run says nothing about whether a finding is right
        -- the page already said so, in the list that implied the opposite."""
        html = flat(section_html(self._payload(review), "overview", tmp_path))
        bounds = html.index("Bounds what else could be here")
        assert html.index("37 of 704", bounds) > bounds
        assert html.index("29 of 33", bounds) > bounds

    def test_an_empty_bears_list_says_so_rather_than_vanishing(self, review, tmp_path):
        """Silence there would read as "we have not thought about it"."""
        p = collect(review)
        html = flat(section_html(p, "overview", tmp_path))
        assert ("Bears on the findings above" in html
                or "Nothing here weakens a specific finding above" in html)
