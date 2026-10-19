"""adjudicate.apply(): every bound in code, every guard proven able to fire.

The known-positive discipline (LESSONS #4) runs through this file: each
clamp/demotion/drop is tested on a fixture BUILT TO TRIP IT, alongside the
clean case, so a guard that silently stopped guarding fails here.
"""

import json
import re
from pathlib import Path

import jsonschema
import pytest

from forensic_metascience_ai_toolkit import adjudicate as A
from forensic_metascience_ai_toolkit.core import prompts

PAPER = ("The compliance rate was 81.3% of participants. "
         "the same section is shown at 10x and 40x magnification. "
         "A total of 200 were randomized.")


def finding(fid, prov=4, producer="tool_expert", outcome="problem", **kw):
    f = {"finding_id": fid, "slug": fid, "producer": producer,
         "technique": "grim_check", "title": "t" * 10, "description": "d" * 30,
         "location": "Table 2", "outcome": outcome,
         "provisional_severity": prov if outcome == "problem" else None,
         "impossible": False}
    f.update(kw)
    return f


def verdict(fid, action="kept", severity=4, category="none",
            rationale="a sentence long enough to pass the schema", **kw):
    v = {"finding_id": fid, "action": action, "severity": severity,
         "category": category, "rationale": rationale}
    v.update(kw)
    return v


def run(findings, verdicts, paper=None, text=PAPER):
    out = {"verdicts": verdicts,
           "paper": paper or {"verdict": "unresolved", "paper_severity": 4,
                              "confidence": "low", "summary": "s" * 200}}
    return A.apply(findings, out, paper_text=text)


class TestEvidenceQuoteGuard:
    def test_a_fabricated_quote_demotes_the_clear(self):
        f = finding("f_a")
        fs, s = run([f], [verdict("f_a", action="discarded", severity=None,
                                  category="innocent_explanation",
                                  evidence_quote="a sentence the paper never printed")])
        assert f["adjudication"]["action"] == "kept"
        assert f["severity"] == 4 and f["severity_is_provisional"] is True
        assert s["n_demoted_clears"] == 1

    def test_a_located_quote_clears(self):
        f = finding("f_a")
        fs, s = run([f], [verdict("f_a", action="discarded", severity=None,
                                  category="innocent_explanation",
                                  evidence_quote="shown at 10x and 40x magnification")])
        assert f["adjudication"]["action"] == "discarded"
        assert f["severity"] is None
        assert s["n_discarded"] == 1

    def test_typography_folds_before_matching(self):
        f = finding("f_a")
        fs, s = run([f], [verdict("f_a", action="discarded", severity=None,
                                  category="innocent_explanation",
                                  evidence_quote="shown at 10× and 40× magnification")],
                    text="the same section is shown at 10x and 40x magnification.")
        assert f["adjudication"]["action"] == "discarded"

    def test_empty_haystack_is_the_conservative_direction(self):
        f = finding("f_a")
        fs, s = run([f], [verdict("f_a", action="discarded", severity=None,
                                  category="innocent_explanation",
                                  evidence_quote="shown at 10x")], text="")
        assert f["adjudication"]["action"] == "kept"


class TestAClearNeedsARealQuote:
    """The gate's stated purpose is that "a fabricated supporting sentence must
    not clear a finding". `_fold("   ")` is `""`, and `"" in haystack` is True,
    so a whitespace-only `evidence_quote` passed it. So did the word "The".

    `quotes._MIN_FRAGMENT` is 12 and exists for exactly this reason -- "'the'
    or '0.05' appears in every paper, so requiring them found would pass
    anything" -- and was not applied here.

    THIS MAKES CLEARING HARDER, which is the accusatory direction, so it was
    measured before shipping: the archive contains ZERO `innocent_explanation`
    verdicts and zero recorded evidence quotes, so no existing clear is
    affected. A demoted clear keeps the finding at its PROVISIONAL severity --
    already capped by the producer clamps -- and records why.
    """

    PAPER = ("The participants were recruited from a university subject pool. "
             "The mean age was 21.4 years.")

    def _run(self, evidence_quote):
        f = finding("f_a", prov=4)
        run([f], [verdict("f_a", action="discarded", severity=None,
                          category="innocent_explanation",
                          evidence_quote=evidence_quote)],
            text=self.PAPER)
        return f

    @pytest.mark.parametrize("quote", ["   ", "", "The", "the", "0.05", "a b"])
    def test_a_fragment_too_short_to_prove_anything_does_not_clear(self, quote):
        f = self._run(quote)
        assert f["severity"] is not None, "the finding was cleared by a stub"

    def test_a_real_located_sentence_still_clears(self):
        f = self._run("the mean age was 21.4 years")
        assert f["severity"] is None

    def test_a_long_but_fabricated_sentence_still_does_not_clear(self):
        """The pre-existing guard, unchanged: long enough to pass the new
        minimum, and absent from the paper."""
        f = self._run("the authors pre-registered this analysis in advance")
        assert f["severity"] is not None

    def test_the_minimum_is_imported_not_restated(self):
        from forensic_metascience_ai_toolkit.quotes import _MIN_FRAGMENT
        assert _MIN_FRAGMENT == 12


class TestJoinDiscipline:
    def test_unknown_ids_drop_and_neighbors_stand_under_shuffle(self):
        a, b = finding("f_a", prov=3), finding("f_b", prov=5)
        vs = [verdict("f_ghost", severity=8, category="manipulation"),
              verdict("f_b", action="downgraded", severity=2,
                      category="chance_expected"),
              verdict("f_a", severity=3)]
        for order in (vs, list(reversed(vs))):
            aa, bb = finding("f_a", prov=3), finding("f_b", prov=5)
            fs, s = run([aa, bb], order)
            assert s["n_unknown_ids"] == 1
            assert bb["severity"] == 2 and aa["severity"] == 3

    def test_readonly_flip_attempts_are_ignored_and_counted(self):
        f = finding("f_a", impossible=False)
        fs, s = run([f], [dict(verdict("f_a"), impossible=True,
                               outcome="pass")])
        assert f["impossible"] is False and f["outcome"] == "problem"
        assert s["n_readonly_flip_attempts"] == 2


class TestDiscardRetains:
    def test_discarded_row_stays_in_the_output(self):
        f = finding("f_a")
        fs, s = run([f], [verdict("f_a", action="discarded", severity=None,
                                  category="misapplication")])
        assert f in fs
        assert f["severity"] is None
        assert f["adjudication"]["action"] == "discarded"


class TestClampBattery:
    def test_non_exempt_upgrade_clamps_to_plus_two(self):
        f = finding("f_a", prov=3)
        fs, _ = run([f], [verdict("f_a", action="upgraded", severity=6,
                                  category="consequence_reassessed")])
        assert f["severity"] == 5
        assert f["adjudication"]["severity_from"] == 6

    def test_merged_pattern_is_exempt_from_plus_two(self):
        f = finding("f_a", prov=4)
        fs, _ = run([f], [verdict("f_a", action="upgraded", severity=7,
                                  category="merged_pattern")])
        assert f["severity"] == 7

    def test_manipulation_is_plus_two_bound(self):
        """v1.14.0: the manipulation 8-gate is gone. `manipulation` is an
        ordinary upgrade category, bound by +2 like `consequence_reassessed`,
        so a provisional 5 asking for 8 lands on 7 -- and the clamp is
        recorded, because a clamp is visible, never silent."""
        f = finding("f_a", prov=5, producer="image_track",
                    quote_verified="verbatim")
        fs, _ = run([f], [verdict("f_a", action="upgraded", severity=8,
                                  category="manipulation")])
        assert f["severity"] == 7
        assert f["adjudication"]["severity_from"] == 8

    def test_eight_needs_no_gate(self):
        """No located quote, no tool, no current-run producer required: the
        only bound on 8 is the +2 movement rule."""
        f = finding("f_a", prov=6, producer="legacy_sweep",
                    computed_by="model_reading", quote_verified="absent")
        fs, _ = run([f], [verdict("f_a", action="upgraded", severity=8,
                                  category="manipulation")])
        assert f["severity"] == 8
        assert "severity_from" not in f["adjudication"]

    def test_adjudicator_may_write_nine_from_provisional_seven(self):
        f = finding("f_a", prov=7)
        fs, s = run([f], [verdict("f_a", action="upgraded", severity=9,
                                  category="consequence_reassessed")])
        assert f["severity"] == 9
        assert "severity_from" not in f["adjudication"]

    def test_a_kept_nine_survives(self):
        """An analyst may now write 9 directly; a kept verdict at 9 is 9."""
        f = finding("f_a", prov=9)
        fs, _ = run([f], [verdict("f_a", severity=9)])
        assert f["severity"] == 9

    def test_merged_pattern_may_reach_nine_from_anywhere(self):
        f = finding("f_a", prov=3)
        fs, _ = run([f], [verdict("f_a", action="upgraded", severity=9,
                                  category="merged_pattern")])
        assert f["severity"] == 9

    def test_ineligible_category_upgrade_reverts_to_provisional(self):
        f = finding("f_a", prov=4)
        fs, _ = run([f], [verdict("f_a", severity=9, category="none")])
        assert f["severity"] == 4
        assert f["adjudication"]["severity_from"] == 9

    def test_no_nine_counter_in_summary(self):
        f = finding("f_a", prov=7)
        fs, s = run([f], [verdict("f_a", action="upgraded", severity=9,
                                  category="consequence_reassessed")])
        assert "n_nine_clamped" not in s

    def test_quarantined_rows_cap_at_three(self):
        f = finding("f_a", prov=3, quarantined=True)
        fs, _ = run([f], [verdict("f_a", action="upgraded", severity=5,
                                  category="consequence_reassessed")])
        assert f["severity"] == 3

    def test_manipulation_below_eight_is_not_exempt(self):
        f = finding("f_a", prov=3, producer="image_track")
        fs, _ = run([f], [verdict("f_a", action="upgraded", severity=6,
                                  category="manipulation")])
        assert f["severity"] == 5


class TestMergeValidation:
    def test_valid_merge_writes_the_inverse(self):
        a, b = finding("f_a", prov=4), finding("f_b", prov=4)
        fs, s = run([a, b], [verdict("f_a", severity=5,
                                     category="merged_pattern"),
                             verdict("f_b", action="merged", severity=None,
                                     category="duplicate", merged_into="f_a")])
        assert b["adjudication"]["merged_into"] == "f_a"
        assert a["adjudication"]["merged_from"] == ["f_b"]
        assert b["severity"] is None and s["n_merged"] == 1

    @pytest.mark.parametrize("target", ["f_ghost", "f_b", "f_c"])
    def test_bad_targets_degrade_to_kept(self, target):
        # ghost, self, and into-discarded are all invalid.
        b = finding("f_b", prov=4)
        c = finding("f_c", prov=4)
        vs = [verdict("f_b", action="merged", severity=None,
                      category="duplicate", merged_into=target),
              verdict("f_c", action="discarded", severity=None,
                      category="misapplication")]
        fs, s = run([b, c], vs)
        assert b["adjudication"]["action"] == "kept"
        assert b["severity"] == 4 and s.get("n_invalid_merges") == 1

    def test_no_merge_chains(self):
        a, b, c = (finding("f_a", prov=4), finding("f_b", prov=4),
                   finding("f_c", prov=4))
        fs, s = run([a, b, c],
                    [verdict("f_a", severity=4),
                     verdict("f_b", action="merged", severity=None,
                             category="duplicate", merged_into="f_a"),
                     verdict("f_c", action="merged", severity=None,
                             category="duplicate", merged_into="f_b")])
        assert c["adjudication"]["action"] == "kept"


class TestSilenceRule:
    def test_unmentioned_rows_keep_provisional(self):
        a, b = finding("f_a", prov=3), finding("f_b", prov=5)
        fs, s = run([a, b], [verdict("f_a", severity=3)])
        assert b["severity"] == 5 and b["severity_is_provisional"] is True
        assert b["adjudication"]["action"] == "kept"

    def test_non_problem_rows_never_gain_a_severity(self):
        p = finding("f_p", outcome="pass")
        fs, _ = run([p], [verdict("f_p", severity=4)])
        assert p["severity"] is None


class TestSkipPaths:
    def test_apply_skip_writes_no_adjudication_objects(self):
        a = finding("f_a", prov=4)
        b = finding("f_b", prov=5, impossible=True)
        fs, s = A.apply_skip([a, b], skipped_reason="budget below floor")
        assert s["ran"] is False and s["skipped_reason"] == "budget below floor"
        for f in (a, b):
            assert "adjudication" not in f
            assert f["severity"] == f["provisional_severity"]
            assert f["severity_is_provisional"] is True

    def test_impossible_rows_get_the_cross_check_stamp(self):
        b = finding("f_b", prov=5, impossible=True)
        a = finding("f_a", prov=4)
        A.apply_skip([a, b], failure="transport died")
        assert b["cross_check"] == "not_run"
        assert "cross_check" not in a


class TestPaperBlock:
    def test_invalid_headline_falls_back_to_worst_kept(self):
        a, b = finding("f_a", prov=3), finding("f_b", prov=6)
        fs, s = run([a, b], [verdict("f_a", severity=3),
                             verdict("f_b", severity=6,
                                     category="consequence_reassessed")],
                    paper={"verdict": "unresolved", "paper_severity": 9,
                           "confidence": "low", "summary": "s" * 200,
                           "headline_finding_id": "f_ghost"})
        assert s["headline_finding_id"] == "f_b"
        assert s["n_headline_fallback"] == 1
        assert s["paper_severity"] == 9   # no ceiling (v1.14.0)

    def test_paper_severity_out_of_range_clamps_to_the_ladder(self):
        a = finding("f_a", prov=3)
        fs, s = run([a], [verdict("f_a", severity=3)],
                    paper={"verdict": "unresolved", "paper_severity": 12,
                           "confidence": "low", "summary": "s" * 200,
                           "headline_finding_id": "f_a"})
        assert s["paper_severity"] == 9

    def test_a_discarded_row_cannot_headline(self):
        a, b = finding("f_a", prov=3), finding("f_b", prov=6)
        fs, s = run([a, b],
                    [verdict("f_a", severity=3),
                     verdict("f_b", action="discarded", severity=None,
                             category="innocent_explanation",
                             evidence_quote="shown at 10x and 40x magnification")],
                    paper={"verdict": "unresolved", "paper_severity": 3,
                           "confidence": "low", "summary": "s" * 200,
                           "headline_finding_id": "f_b"})
        assert s["headline_finding_id"] == "f_a"


class TestDocket:
    def make(self, n, producer="tool_expert", outcome="problem"):
        return [finding(f"f_{producer}_{i:03d}", prov=(i % 5) + 1,
                        producer=producer, outcome=outcome)
                for i in range(n)]

    def test_cap_names_the_remainder(self):
        d = A.build_docket(self.make(121), paper_text="text")
        assert d["n_itemized"] == 120 and d["n_not_adjudicated"] == 1
        assert "DOCKET CAP: 1 row(s) withheld" in d["text"]
        assert "tool_expert/grim_check: 1" in d["text"]

    def test_pass_rows_are_counted_never_itemized(self):
        rows = self.make(2) + self.make(41, outcome="pass")
        d = A.build_docket(rows)
        assert d["n_itemized"] == 2
        assert "grim_check: 41 pass" in d["text"]

    def test_producer_interleave_protects_the_quiet_producer(self):
        rows = self.make(200, "tool_expert") + self.make(4, "science_error")
        d = A.build_docket(rows)
        science = [i for i in d["included_ids"] if "science" in i]
        assert len(science) == 4, "a noisy producer must not evict the quiet one"

    def test_web_unbacked_reaches_the_adjudicator(self):
        """The guard that flags web citations with no ledger web call must
        be READ, not only written: until 2026-08-21 `web_unbacked` was set
        by parallel._rows_from_producer and consumed by nobody (caught by
        the write-only-key ratchet)."""
        rows = self.make(1)
        rows[0]["web_sources"] = [{"url": "https://x", "quote": "q"}]
        rows[0]["web_unbacked"] = True
        d = A.build_docket(rows)
        assert "web_unbacked" in d["text"]
        assert "no web call" in d["text"]

    def test_unsourced_lookup_shape_gets_its_own_sentence(self):
        """MEASURED 2026-08-22 (four-paper grok rematch): all ten
        basis=web_lookup rows carried web_sources: [] beside ledgers full
        of real web calls -- the inverted unbacked shape. The docket must
        say what it means, not reuse the no-ledger-call sentence."""
        rows = self.make(1)
        rows[0]["basis"] = "web_lookup"
        rows[0]["web_unbacked"] = "no_recorded_source"
        d = A.build_docket(rows)
        assert "ZERO web_sources" in d["text"]
        assert "model knowledge" in d["text"]

    def test_the_ledgers_visited_urls_reach_the_docket(self):
        """An unsourced claim beside a list of real fetches is a different
        adjudication question than one beside nothing."""
        rows = self.make(1)
        rows[0]["basis"] = "web_lookup"
        rows[0]["web_unbacked"] = "no_recorded_source"
        rows[0]["ledger_web_context"] = ["https://vectorlabs.com/ba-1400"]
        d = A.build_docket(rows)
        assert "https://vectorlabs.com/ba-1400" in d["text"]

    def test_text_truncation_is_announced(self):
        d = A.build_docket(self.make(1),
                           paper_text="x" * (A.PAPER_TEXT_BUDGET_CHARS + 5))
        assert "text truncated at 40,000" in d["text"]

    def test_absent_text_is_a_statement(self):
        d = A.build_docket(self.make(1), paper_text="")
        assert "NO EXTRACTED TEXT WAS AVAILABLE" in d["text"]

    def test_handoff_notes_reach_the_adjudicator(self):
        """MEASURED 2026-10-16 (10.1371--journal.pone.0042828, sonnet): the
        science agent's handoff that the Table 2 count means "look
        inconsistent with GRIM at n=6" was written and read by nobody --
        the analysts run concurrently and the docket did not carry it."""
        note = {"location": "Table 2 locomotor and rearing means",
                "reason": "Handoff to tools agent: rearing 18.4 looks "
                          "inconsistent with GRIM at n=6."}
        d = A.build_docket(self.make(1), paper_text="t",
                           unchecked={"science_error": [note],
                                      "tool_expert": None})
        assert "## What the analysts did NOT check" in d["text"]
        assert "inconsistent with GRIM at n=6" in d["text"]
        assert '"producer": "science_error"' in d["text"]
        # Before the paper text, which is clipped last.
        assert d["text"].index("did NOT check") < d["text"].index("## Paper text")

    def test_no_unchecked_entries_adds_no_section(self):
        d = A.build_docket(self.make(1), unchecked={"tool_expert": []})
        assert "did NOT check" not in d["text"]

    def test_unchecked_cap_is_announced(self):
        many = [{"location": f"row {i}", "reason": "r" * 200} for i in range(60)]
        d = A.build_docket(self.make(1), unchecked={"tool_expert": many})
        assert "UNCHECKED CAP:" in d["text"]
        assert "of 60 entries not shown" in d["text"]


class TestPromptContract:
    def test_the_embedded_example_validates(self):
        md = prompts.prompt_path("adjudication.md").read_text()
        blocks = [json.loads(m.group(1))
                  for m in re.finditer(r"```json\n(.*?)```", md, re.S)]
        assert blocks
        schema = prompts.adjudication_schema()
        for b in blocks:
            jsonschema.validate(b, schema)

    def test_the_assembler_carries_the_ladder_and_rulebook(self):
        text = prompts.adjudication_system_prompt()
        assert "only problem in the paper" in text
        assert "## Severity enum" in text
        assert "Who each rule binds" in text


class TestTheDocketSaysWhereThePaperIs:
    """MEASURED 2026-08-22 over the biomedical batch, from grok's own session
    logs:

        role           sessions  tool calls  failed       reached MCP
        tool_expert          18       1,487  3    ( 0%)   1,238 (83%)
        science_error        15         498  8    ( 2%)     295 (59%)
        ADJUDICATOR          13       1,038  680  (66%)     145 (14%)

    `grep -c "/home/dan" prompt.adjudicator.md` returned 0 on every paper:
    `build_docket` took no paths, so the stage that assigns every final
    severity was asked to verify findings against a paper whose location it
    was never given. `_resolve_paper_sources` already states the rule --
    "every path the model can read is one this function put in the prompt...
    a supplement that is not merged here is a supplement that does not exist
    as far as the review is concerned"."""

    def _rows(self):
        return [{"finding_id": "f_1", "slug": "s", "producer": "tool_expert",
                 "technique": "grim_check", "outcome": "problem",
                 "provisional_severity": 3, "title": "t", "description": "d"}]

    def test_absolute_paths_reach_the_docket(self):
        d = A.build_docket(
            self._rows(),
            sources={"XML full text (extract_xml)": "/abs/p/paper.xml",
                     "main PDF (extract_pdf)": "/abs/p/paper.pdf"})
        assert "/abs/p/paper.xml" in d["text"]
        assert "/abs/p/paper.pdf" in d["text"]

    def test_they_come_before_the_findings(self):
        """The model needs this before it starts reaching for tools; a packet
        that buries it is a packet it will not read in time."""
        d = A.build_docket(self._rows(),
                                    sources={"paper directory": "/abs/p"})
        assert d["text"].index("Where the paper is") < d["text"].index("f_1")

    def test_a_list_of_supplements_is_itemised(self):
        d = A.build_docket(
            self._rows(),
            sources={"supplements": ["/abs/p/s1.docx", "/abs/p/s2.xlsx"]})
        assert "/abs/p/s1.docx" in d["text"] and "/abs/p/s2.xlsx" in d["text"]

    def test_empty_entries_are_dropped_not_printed_as_none(self):
        d = A.build_docket(
            self._rows(),
            sources={"HTML full text": None, "supplements": [],
                     "paper directory": "/abs/p"})
        assert "None" not in d["text"].split("## ")[1]

    def test_no_sources_is_a_named_absence_not_a_silence(self):
        """An adjudicator told nothing must know that is OUR gap, not a licence
        to guess -- the guessing is what cost the 66%."""
        d = A.build_docket(self._rows())
        assert "NOT SUPPLIED" in d["text"]
        assert "Do not guess at filenames" in d["text"]

    def test_the_fetchpdf_trap_is_named_where_the_paths_are(self):
        d = A.build_docket(self._rows(),
                                    sources={"paper directory": "/abs/p"})
        assert "_from_xml.md" in d["text"]
        assert "markdown/body.md" in d["text"]
