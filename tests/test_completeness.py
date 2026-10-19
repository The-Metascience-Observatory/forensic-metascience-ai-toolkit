"""Every checkable thing in a paper must end the run with a label.

GREG, 2026-08-12, on the defect register, calling this the most consequential
item on it:

    "I need you to make a system that makes it so the model CANNOT proceed
     unless all checkable cells are checked and given the appropriate label...
     it shouldn't just be cells in tables, but also checkable content in the
     body of the paper."

The measured problem it answers: 21 of 72 tables ever received a check_table
call, and 11.5% of consumable cells provably reached a check. The other 88.5%
are not refusals -- they are SILENCE, and silence is indistinguishable from a
clean pass in the finished report.

Two properties are load-bearing and both are tested here. The refusal vocabulary
must be CLOSED, or "checked everything I could" creeps back in as a free-text
excuse. And the body enumerator must not enrol things that are not results --
a confidence LEVEL, a power target, a stated alpha -- because an item the model
can never discharge turns the gate into noise its reader learns to skip.
"""
import pathlib

import pytest

from metascience_agent import completeness as C

REPO = pathlib.Path(__file__).resolve().parent.parent

#: THE DOCUMENT `TestOnARealPaper` MEASURES, RETARGETED 2026-08-17. It was
#: `10.1001--jamanetworkopen.2023.51752` until `extraction.pdf` became
#: docling-only and CACHE-ONLY. A PDF with no schema-4 docling cache now comes
#: back `unreadable`, and `supplements_read.extract_pdf_tables` is RIGHT to send
#: an unreadable PDF to the OCR seam -- so that paper's three supplementary
#: PDFs, ~90 born-digital pages whose cached extractions predate schema 4, were
#: being rendered and OCR'd at 300 dpi to build one manifest. MEASURED: the
#: class did not finish in 60 minutes; under the pdfplumber reader it took
#: seconds.
#:
#: This paper ships publisher JATS XML and NO supplementary files at all, so its
#: manifest is read from marked-up ground truth end to end and needs no docling
#: cache in any state -- which is what makes it the right fixture for a test
#: about the MANIFEST rather than about PDF extraction. MEASURED 2026-08-17:
#: 968 items (920 table, 48 body, 0 supplement) in 14.2 s, `problems` empty.
#: The thresholds below are unchanged and are cleared by 9.2x and 4.8x.
PAPER = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "10.1038--s41537-025-00576-3"


class TestTheRefusalVocabularyIsClosed:
    def test_a_reason_outside_the_vocabulary_is_REJECTED(self):
        """A free-text refusal is how a closed vocabulary stops being closed.
        The item stays OUTSTANDING rather than being quietly accepted."""
        man = {"items": [{"id": "x", "where": "body", "kind": "p_value",
                          "raw": "P = .04"}]}
        rep = C.disposition_report(man, declared={"x": "seemed fine to me"})
        assert rep["n_outstanding"] == 1
        assert rep["invalid_refusal_reasons"][0]["reason"] == "seemed fine to me"
        assert not rep["complete"]

    def test_a_reason_inside_the_vocabulary_is_accepted(self):
        man = {"items": [{"id": "x", "where": "body", "kind": "p_value",
                          "raw": "P = .04"}]}
        rep = C.disposition_report(man, declared={"x": "no_applicable_check"})
        assert rep["n_outstanding"] == 0
        assert rep["complete"]

    def test_every_reason_carries_a_stated_meaning(self):
        """A vocabulary entry with no explanation is a category nobody can audit."""
        for reason, why in C.REFUSAL_REASONS.items():
            assert why and len(why) > 20, reason

    def test_our_own_failure_is_labelled_as_ours(self):
        """`unreadable` must not read as a property of the paper."""
        assert "OUR defect" in C.REFUSAL_REASONS["unreadable"]


class TestTheGate:
    def test_an_unchecked_unrefused_item_fails_the_gate(self):
        man = {"items": [{"id": "x", "where": "body", "kind": "p_value",
                          "raw": "P = .04"}]}
        g = C.gate(C.disposition_report(man))
        assert g["passed"] is False
        assert "NO disposition" in g["message"]

    def test_the_failure_message_NAMES_the_outstanding_items(self):
        """A gate that says "incomplete" without saying what is missing cannot
        be acted on, and will be ignored."""
        man = {"items": [{"id": "body:12", "where": "body", "kind": "p_value",
                          "raw": "P = .007"}]}
        g = C.gate(C.disposition_report(man))
        assert "body:12" in g["message"] and "P = .007" in g["message"]

    def test_a_fully_disposed_paper_passes(self):
        man = {"items": [{"id": "a", "where": "table T", "kind": "non_numeric",
                          "raw": "Age group", "consumable": False}]}
        rep = C.disposition_report(man)
        assert rep["complete"]
        assert C.gate(rep)["passed"] is True

    def test_enforcement_is_OFF_by_default_and_that_is_deliberate(self):
        """At 11.5% coverage, enforcing today halts every run on its first paper
        and teaches everyone to pass the flag that disables it. The gate is
        introduced RECORDING; the gap it measures is the work queue."""
        man = {"items": [{"id": "x", "where": "body", "kind": "p_value", "raw": "p"}]}
        assert C.gate(C.disposition_report(man))["enforced"] is False
        assert C.gate(C.disposition_report(man), enforce=True)["enforced"] is True


class TestTheAutomaticRefusals:
    """The harness assigns what it can, so the outstanding list holds only items
    that need a human or a model decision. Demanding that someone declare they
    declined to check a row label would bury the items that matter."""

    def _cell(self, **kw):
        base = {"id": "c", "where": "table T", "raw": "x", "consumable": True,
                "runnable": True}
        return {"items": [{**base, **kw}]}

    def test_a_row_label_is_refused_as_not_a_statistic(self):
        rep = C.disposition_report(self._cell(kind="non_numeric"))
        assert rep["by_disposition"]["refused:not_a_statistic"] == 1

    def test_an_ambiguous_cell_asks_for_a_declaration(self):
        rep = C.disposition_report(self._cell(kind="ambiguous"))
        assert rep["by_disposition"]["refused:undeclared_variable"] == 1

    def test_a_kind_with_no_check_is_refused_as_such(self):
        rep = C.disposition_report(self._cell(kind="numeric", consumable=False))
        assert rep["by_disposition"]["refused:no_applicable_check"] == 1

    def test_a_cell_waiting_on_an_n_is_refused_as_missing_input(self):
        rep = C.disposition_report(self._cell(kind="mean_sd", runnable=False))
        assert rep["by_disposition"]["refused:missing_input"] == 1

    def test_a_RUNNABLE_cell_is_left_OUTSTANDING(self):
        """The whole point. A cell every precondition is satisfied for, that
        nothing checked, is the silence this instrument exists to end."""
        rep = C.disposition_report(self._cell(kind="mean_sd"))
        assert rep["n_outstanding"] == 1

    def test_a_body_item_is_NEVER_auto_refused(self):
        """Prose cannot be disposed of by rule -- someone has to decide."""
        man = {"items": [{"id": "b", "where": "body", "kind": "percentage",
                          "raw": "40%"}]}
        assert C.disposition_report(man)["n_outstanding"] == 1


class TestTheBodyEnumeratorDoesNotEnrolNonResults:
    """Found by reading the enumerator's own first output on a real paper: a
    confidence level, a power target and a stated alpha had all been enrolled as
    checkable claims. Each would have been an item the model could never
    discharge."""

    def test_a_confidence_LEVEL_is_not_a_reported_percentage(self):
        got = C._body_items("the 90% CIs from quantile regressions were wide")
        assert not [i for i in got if i["raw"].startswith("90")]

    def test_a_95_percent_CI_label_is_not_enrolled(self):
        got = C._body_items("(ARR, 0.185; 95% CI, 0.046-0.748)")
        assert not [i for i in got if i["raw"].strip() == "95%"]

    def test_a_power_target_is_not_a_result(self):
        got = C._body_items("we had at least 80% power (a = .05) for most outcomes")
        assert not [i for i in got if i["raw"].startswith("80")]

    def test_a_stated_significance_threshold_is_not_a_p_value(self):
        got = C._body_items("A 2-sided P < .05 was set as the threshold for "
                            "significance by logistic regression")
        assert not [i for i in got if "P < .05" in i["raw"]]

    def test_a_REAL_reported_p_is_still_enrolled(self):
        """The filter must not be so eager that it silences results."""
        got = C._body_items("obesity by 81% (ARR, 0.185; 95% CI, 0.046-0.748; "
                            "P < .001). These effects were robust")
        assert [i for i in got if "P < .001" in i["raw"]]

    def test_a_REAL_count_percentage_is_still_enrolled(self):
        got = C._body_items("727 (98%) were unmarried and 631 (85%) lived below")
        assert len([i for i in got if i["kind"] == "percentage"]) == 2

    def test_overlapping_matches_become_one_item(self):
        """`0.185; 95% CI, 0.046-0.748; P < .001` is one claim, not four. Items
        the model cannot discharge individually make the gate unusable."""
        got = C._body_items("(ARR, 0.185; 95% CI, 0.046-0.748; P < .001)")
        assert len(got) <= 2

    def test_every_item_carries_a_locator_a_human_can_search_for(self):
        got = C._body_items("the risk of obesity fell 55% (P = .003) overall")
        assert all(i.get("context") and i.get("offset") is not None for i in got)


@pytest.mark.skipif(not PAPER.exists(), reason="corpus paper absent")
class TestOnARealPaper:
    """The same four properties, measured on a published paper rather than a
    hand-built dict. See `PAPER` for why this is no longer the paper it was.

    NOTHING IT ASSERTS CHANGED. Both halves of the paper are enumerated, the
    count declares itself a floor, every item lands in exactly one of
    checked/refused/outstanding, and recording a check moves a row out of
    outstanding. Only the document underneath moved, to one this suite can read
    without first running an extraction step.
    """

    @pytest.fixture(scope="class")
    def manifest(self):
        man = C.build_manifest(PAPER)
        if man.get("problems"):
            # A manifest built over a document we failed to open measures US,
            # and asserting `n_table_items > 100` against one would record our
            # gap as a property of the paper -- the house failure mode this
            # whole module exists to end. Skip instead, carrying the reason: a
            # cold docling cache names `metascience extract-tables` in its own
            # problem text, so the reader is told what to run.
            pytest.skip("the manifest reports reading gaps, so its counts are "
                        "ours and not the paper's: "
                        + " | ".join(man["problems"])[:400])
        return man

    def test_it_enumerates_both_tables_and_prose(self, manifest):
        assert manifest["n_table_items"] > 100
        assert manifest["n_body_items"] > 10

    def test_it_says_its_count_is_a_floor(self, manifest):
        """An image-only table or an unfetched supplement contributes nothing
        here, and a reader must not take `n_items` for the paper's true total."""
        assert "LOWER BOUND" in manifest["paper_coverage_is_a_floor"]

    def test_the_outstanding_set_is_the_runnable_and_the_prose(self, manifest):
        """With no checks recorded, what remains outstanding should be exactly
        the items a check COULD have run on, plus every prose claim -- not the
        row labels, and not the cells waiting on an n."""
        rep = C.disposition_report(manifest)
        assert rep["n_outstanding"] > 0
        wheres = {r["where"].split()[0] for r in rep["outstanding"]}
        assert wheres <= {"table", "body"}
        assert rep["n_items"] == rep["n_checked"] + rep["n_refused"] + rep["n_outstanding"]

    def test_recording_a_check_removes_it_from_outstanding(self, manifest):
        rep0 = C.disposition_report(manifest)
        first = rep0["outstanding"][0]["id"]
        rep1 = C.disposition_report(manifest, checked_ids={first})
        assert rep1["n_checked"] == 1
        assert rep1["n_outstanding"] == rep0["n_outstanding"] - 1


class TestEveryStage1FindingEndsWithADisposition:
    """The manifest asks it of every checkable ITEM; this asks it of every
    FINDING. MEASURED over 28 archived runs: 24 of 264 accusatory stage-1
    findings are cited by no editorial finding -- 2 at `impossible`, 4 at
    `highly_suspicious` -- and none of their ids appears anywhere in the report
    that dropped them. `report.json` has no channel for a rejected finding at
    all, so an accusation can be withdrawn in silence and a reader cannot tell
    that from an accusation never made."""

    def _f(self, fid, sev):
        return {"id": fid, "severity": sev, "location": "T1"}

    def test_a_dropped_accusation_is_surfaced(self):
        from metascience_agent.completeness import reconcile_findings
        r = reconcile_findings(
            [self._f("a", "impossible"), self._f("b", "consistent")],
            {"findings": [{"stage1_finding_ids": ["b"]}]})
        assert r["n_accusatory_dropped"] == 1
        assert r["accusatory_dropped"][0]["id"] == "a"
        assert r["clean"] is False
        assert "silent retraction" in r["note"]

    def test_dropping_only_consistent_results_is_clean(self):
        from metascience_agent.completeness import reconcile_findings
        r = reconcile_findings(
            [self._f("a", "consistent"), self._f("b", "suspicious")],
            {"findings": [{"stage1_finding_ids": ["b"]}]})
        assert r["n_dropped"] == 1 and r["n_accusatory_dropped"] == 0
        assert r["clean"] is True
        assert "None of the dropped findings was accusatory" in r["note"]

    def test_everything_carried_says_so(self):
        from metascience_agent.completeness import reconcile_findings
        r = reconcile_findings([self._f("a", "suspicious")],
                               {"findings": [{"stage1_finding_ids": ["a"]}]})
        assert r["n_dropped"] == 0 and r["clean"] is True

    def test_no_findings_is_not_an_alarm(self):
        from metascience_agent.completeness import reconcile_findings
        r = reconcile_findings([], {"findings": []})
        assert r["clean"] is True and "nothing to reconcile" in r["note"]

    def test_a_run_with_no_report_is_UNKNOWN_not_zero_carried(self):
        """The correction that produced this test. A first pass read a missing
        report.json as an empty one and scored all 18 findings of that run as
        dropped -- 11 accusatory -- which manufactured a six-item accusation
        against the pipeline out of two absent files. Two archived runs have a
        findings.json and no report.json."""
        from metascience_agent.completeness import reconcile_findings
        r = reconcile_findings([self._f("a", "impossible")], None)
        assert r["reconcilable"] is False
        assert r["n_dropped"] is None and r["n_carried"] is None
        assert r["clean"] is None, "unknown is not clean and is not dirty"
        assert "NOT a count of zero carried" in r["note"]
        r2 = reconcile_findings([self._f("a", "impossible")], {})
        assert r2["reconcilable"] is False

    def test_the_archive_drops_no_impossible_finding(self):
        """MEASURED over the 27 runs that carry both files: `impossible` and
        `highly_suspicious` are dropped 0 times. The strongest claims survive to
        the report, which is what this check was built to find out."""
        import json, pathlib as _p
        from metascience_agent.completeness import reconcile_findings
        root = _p.Path(__file__).resolve().parents[1]
        worst = 0
        seen = 0
        for f in root.glob("**/findings.json"):
            if "_bundle" in str(f) or "scratchpad" in str(f):
                continue
            rp = f.parent / "report.json"
            if not rp.exists():
                continue
            try:
                s1 = (json.loads(f.read_text(encoding="utf-8")) or {}).get("findings") or []
                rpt = json.loads(rp.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            if not s1:
                continue
            seen += 1
            rec = reconcile_findings(s1, rpt)
            worst += sum(1 for d in rec["accusatory_dropped"]
                         if d["severity"] in ("impossible", "highly_suspicious"))
        if seen < 5:
            pytest.skip("archive not in this checkout")
        assert worst == 0, f"{worst} impossible/highly_suspicious findings dropped"


class TestTheTriageChannelIsReadNotJustOffered:
    """The mirror of the `declaration_template` defect. There, a tool OFFERED a
    channel and nothing told the model to use it. Here the stage-2 prompt has
    always INSTRUCTED -- "for every Stage-1 finding you discard or downgrade,
    state why in one line" -- and until 2026-08-13 the report schema had no
    field to put the answer in. Nine properties, none for triage. The reasoning
    could only reach prose, where nothing can count it.

    MEASURED 2026-08-13 over 27 archived runs: 13 of 214 `suspicious` findings
    dropped with no machine-readable reason. `impossible` and
    `highly_suspicious` are dropped 0 times, so this is the middle of the
    ladder, not the top."""

    def _f(self, fid, sev):
        return {"id": fid, "severity": sev, "location": "T1"}

    def test_an_unexplained_accusation_drop_is_not_clean(self):
        from metascience_agent.completeness import reconcile_findings
        r = reconcile_findings([self._f("a", "suspicious")], {"findings": []})
        assert r["n_accusatory_unexplained"] == 1
        assert r["clean"] is False

    def test_a_stated_reason_makes_the_same_drop_clean(self):
        from metascience_agent.completeness import reconcile_findings
        r = reconcile_findings(
            [self._f("a", "suspicious")],
            {"findings": [],
             "triage": [{"stage1_finding_id": "a", "disposition": "discarded",
                         "reason": "GRIM applied to a continuous variable"}]})
        assert r["clean"] is True
        assert r["n_accusatory_unexplained"] == 0
        assert r["n_dropped"] == 1, "explaining a drop does not un-drop it"

    def test_the_reason_travels_with_the_row(self):
        from metascience_agent.completeness import reconcile_findings
        r = reconcile_findings(
            [self._f("a", "impossible")],
            {"findings": [],
             "triage": [{"stage1_finding_id": "a", "disposition": "merged",
                         "reason": "folded into the Table 2 duplication finding"}]})
        row = r["accusatory_dropped"][0]
        assert row["explained"] is True
        assert row["disposition"] == "merged"
        assert "folded into" in row["reason"]

    def test_explaining_a_consistent_drop_is_not_required(self):
        from metascience_agent.completeness import reconcile_findings
        r = reconcile_findings([self._f("a", "consistent")], {"findings": []})
        assert r["clean"] is True, "a consistent result belongs nowhere in a report"


class TestTheProseHalfHasASourceForPDFOnlyPapers:
    """FOUND 2026-08-15, and it was a wiring fault, not a weak enumerator.

    "The completeness manifest is effectively a TABLE manifest" was the headline
    entry on this project's defect list, and the evidence was Ophir 2009: 25 test
    statistics in prose, manifest counting ZERO items.

    The cause was that `_read_body` read publisher XML or `body.md` and nothing
    else. A PDF-only paper -- which is most of them -- returned "" and enumerated
    no prose at all. `_body_items` recovers tens of items from the same paper's
    docling text; it had simply never been handed any.

    MEASURED before and after:

        Ophir 2009  (PDF only)     body chars 0 -> 38,879   prose items 0 -> 30
        Kross 2013  (PDF + docx)   body chars 0 -> 33,527   prose items 0 -> 27
        JAMA .37679 (ships XML)    unchanged -- it always had a source

    The class this belongs to is the one this repository keeps rediscovering: a
    capability that exists and is not connected to its source. Same week as
    `verdicts.py` (no production consumer) and `text_provenance` (wired only to
    the failure path).
    """

    def _dir(self, name):
        import pathlib

        import pytest
        p = pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/papers/high_value_pdfs_to_run_on" / name
        if not p.is_dir():
            pytest.skip(f"{name} not in this checkout")
        return p

    def test_a_pdf_only_paper_now_enumerates_prose(self):
        from metascience_agent.completeness import _read_body, build_manifest
        d = self._dir("10.1073--pnas.0903620106")          # Ophir: PDF, no XML, no body.md
        assert not list(d.glob("*.xml")) and not (d / "body.md").exists(), \
            "this test is only meaningful on a paper with no XML and no body.md"
        text, problem = _read_body(d)
        assert len(text) > 20_000, (len(text), problem)
        body = [i for i in (build_manifest(d).get("items") or []) if i.get("where") == "body"]
        assert len(body) >= 20, f"only {len(body)} prose items from {len(text)} chars"

    def test_publisher_xml_still_wins(self):
        """The PDF is the LAST resort. XML is structured ground truth and must
        not be displaced by a text layer inferred from ink."""
        import pathlib
        from metascience_agent import completeness as C
        d = self._dir("10.1001--jamanetworkopen.2023.37679")
        assert list(d.glob("*.xml")), "fixture assumption"
        called = []
        real = C.cached_text if hasattr(C, "cached_text") else None
        from metascience_agent.extraction import docling_tables as DT
        orig = DT.cached_text
        DT.cached_text = lambda *a, **k: (called.append(a) or ("", "should not be reached"))
        try:
            text, _ = C._read_body(d)
        finally:
            DT.cached_text = orig
        assert text and not called, "XML present, so the docling cache must not be consulted"

    def test_a_cold_cache_names_the_fix_instead_of_returning_silence(self, tmp_path):
        """An empty string on its own reads as "this paper has no prose", which
        is a claim about the paper. A failure to read one is a fact about us."""
        from metascience_agent.completeness import _read_body
        (tmp_path / f"{tmp_path.name}.pdf").write_bytes(b"%PDF-1.4 not really")
        text, problem = _read_body(tmp_path)
        assert text == ""
        assert problem and "extract-tables" in problem
        assert "OUR gap" in problem

    def test_a_supplement_is_not_read_as_the_article(self, tmp_path):
        """Reading whichever PDF sorts first would put a supplement's prose into
        the manifest as the paper's own body. `_article_pdf` resolves by
        declaration, then by the DOI stem -- never by sort order."""
        from metascience_agent.completeness import _article_pdf
        (tmp_path / "aaa_supplementary_appendix.pdf").write_bytes(b"%PDF-1.4")
        got, how = _article_pdf(tmp_path)
        # STILL REFUSED, and now for a reason that names the risk. The message
        # changed when `_article_pdf` gained a sole-PDF fallback: a lone
        # supplement is exactly the case that fallback must not take, so it says
        # so instead of reporting a bare absence.
        assert got is None
        assert "may be a supplement" in how and "aaa_supplementary_appendix" in how
        (tmp_path / f"{tmp_path.name}.pdf").write_bytes(b"%PDF-1.4")
        got, how = _article_pdf(tmp_path)
        assert got is not None and got.name == f"{tmp_path.name}.pdf"
        assert "doi_stem" in how, (
            "the caller must be able to tell a guess from a declaration: a "
            "DOI-stem filename match is a convention, not something an "
            "operator asserted")


class TestTheFloorStopsAtTheBibliography:
    """MEASURED 2026-08-16 over the 16 cached docling extractions: 33 of 439
    floor items (7.5%) sat inside a reference list, and for `10.1002--eat.24415`
    it was 20 of 25 -- 80% of that paper's floor was bibliography.

    Three were DOIs read as sample fractions: `10.1037/0022-3514...` enumerates
    as the "statistic" 1037/0022, a fraction whose numerator exceeds its own
    total. The floor is what accuses the statistics register of being
    incomplete, so each of these was our enumerator's artefact charged to the
    model as a statistic it failed to list -- our failure recorded as the
    paper's property.
    """

    def _body(self, results: str, refs: str) -> str:
        # A body long enough that the heading lands past the 40% mark.
        return f"{'Filler sentence about the method. ' * 40}\n{results}\n\nReferences\n\n{refs}\n"

    def test_a_statistic_in_the_reference_list_is_not_enumerated(self):
        from metascience_agent.completeness import _body_items
        text = self._body(
            "Accuracy differed by group, t(48) = 2.51, p = 0.015.",
            "Gross JJ (1998). Antecedent- and response-focused emotion regulation. "
            "Journal of Personality and Social Psychology, 74(1), 224. 10.1037/0022-3514.74.1.224",
        )
        raws = [i["raw"] for i in _body_items(text)]
        assert any("t(48)" in r.replace(" ", "") for r in raws), "the real result must survive"
        assert not any("1037/0022" in r for r in raws), f"bibliography enumerated: {raws}"

    def test_a_doi_in_running_text_is_not_a_sample_fraction(self):
        """The cutoff cannot catch a DOI cited mid-paragraph, so the DOI context
        and the impossible-fraction rule have to hold on their own."""
        from metascience_agent.completeness import _body_items
        text = "As reported previously (10.1037/0022-3514.74.1.224), the effect held. " * 3
        assert not [i for i in _body_items(text) if "/" in i["raw"]]

    def test_a_fraction_larger_than_its_own_total_is_refused(self):
        from metascience_agent.completeness import _is_result
        import re
        m = re.match(r"^(\d+/\d+)$", "1037/0022")
        assert _is_result("1037/0022", m) is False
        m2 = re.match(r"^(\d+/\d+)$", "22/1037")
        assert _is_result("22/1037", m2) is True, "an ordinary n-of-total must still pass"

    def test_the_cut_never_fires_in_the_front_of_a_document(self):
        """A table of contents listing 'References' must not truncate the paper.
        Cutting early loses real results, which is the worse direction."""
        from metascience_agent.completeness import _body_end
        text = "Contents\n\nReferences\n\n" + ("Body text with results. " * 200)
        assert _body_end(text) == len(text)

    def test_the_heading_must_be_a_heading(self):
        from metascience_agent.completeness import _body_end
        text = ("Filler. " * 100) + "\nWe compared our references to theirs.\n" + ("More. " * 100)
        assert _body_end(text) == len(text), "a sentence mentioning references is not a heading"


class TestANumberInMethodsIsNotAReportedResult:
    """Every body item becomes an OUTSTANDING item -- `_auto_refusals` returns
    None for all of them, so none can be auto-discharged -- and
    `register.floor_check` states the claim outright: "these were located
    mechanically, so they are present in the paper and the model did not list
    them." A false entry is therefore charged to the model as a missed
    statistic of its own paper."""

    NOT_A_RESULT = [
        ("a reagent concentration",
         "Sections were fixed in 4% paraformaldehyde and washed in 0.9% saline."),
        ("another paper's number",
         "Smith et al. reported that 62% of studies failed to replicate."),
        ("staffing, not sample",
         "Ratings were made on a 1 to 7 scale by 3 of 5 trained coders."),
        ("a decision rule the study will apply",
         "The intervention will be judged successful if more than 30% of "
         "patients respond."),
    ]
    IS_A_RESULT = [
        ("a reported percentage", "Response rate was 62% in the treatment arm."),
        ("an NHST", "The interaction was reliable, t(38) = 7.21, p = .011."),
        ("a fraction", "Attrition was 12 of 50 participants."),
        ("a mean and SD", "The mean was 3.45 (SD 1.02) at follow-up."),
        # Both VERBATIM from cerebrolysin_papers. A first version of the
        # hypothetical filter listed `expect` and `criteria` as cues and
        # deleted these two out of a 12-item sample of what it removed.
        ("'As expected' introduces results all the time",
         "As expected, in non-tg mice approximately 65% of the BrdU+ cells "
         "expressed NeuN."),
        ("'criteria' appears in results sentences",
         "These criteria improved by 12-38% in comparison to baseline in the "
         "verum group."),
    ]

    def test_methods_numbers_are_not_enrolled(self):
        from metascience_agent.completeness import _body_items
        fooled = [(n, [i["raw"] for i in _body_items(t)])
                  for n, t in self.NOT_A_RESULT if _body_items(t)]
        assert not fooled, f"enrolled as reported statistics: {fooled}"

    def test_real_results_are_still_enrolled(self):
        from metascience_agent.completeness import _body_items
        missed = [n for n, t in self.IS_A_RESULT if not _body_items(t)]
        assert not missed, f"real statistics dropped from the floor: {missed}"

    def test_the_hypothetical_filter_needs_actual_modality(self):
        """Dropping a real statistic from the floor is a false all-clear about
        the register's completeness -- the error this module exists to
        prevent -- so the filter matches future/conditional modality only."""
        from metascience_agent.completeness import _HYPOTHETICAL_BEFORE
        assert _HYPOTHETICAL_BEFORE.search("will be judged successful if more than ")
        assert not _HYPOTHETICAL_BEFORE.search("As expected, in non-tg mice approximately ")
        assert not _HYPOTHETICAL_BEFORE.search("These criteria improved by ")


class TestTheMojibakeEqualsSign:
    """`p = 0.038` reaches us as `p ¼ 0.038` from older PDFs -- a Type-1
    font-encoding artifact. MEASURED over the 305-paper cerebrolysin corpus: 25
    papers contain `¼`, and repairing it recovers 30 prose statistics (508 ->
    538, +5.9%), up to +7 on one paper. They are p-values and whole NHST triples
    (`F CL ¼ 45.43; DFn ¼ 19; DFd ¼ 80`) that no pattern here could see -- so
    they were absent from the floor AND unreachable by statcheck."""

    def test_a_mojibake_p_value_is_enumerated(self):
        from metascience_agent.completeness import _body_items
        items = _body_items("The effect was reliable (P ¼ 0.038) at follow-up.")
        assert [i["kind"] for i in items] == ["p_value"]

    def test_raw_is_what_the_PAPER_printed_not_the_repair(self):
        """A locator that points at a string the paper does not contain is
        worse than no locator. `celltypes` keeps `raw` verbatim for the same
        reason and records the repair beside it."""
        from metascience_agent.completeness import _body_items
        text = "The effect was reliable (P ¼ 0.038) at follow-up."
        i = _body_items(text)[0]
        assert i["raw"] == "P ¼ 0.038"
        assert i["raw"] in text
        assert i["repaired"] == "P = 0.038"

    def test_offsets_still_point_into_the_original(self):
        from metascience_agent.completeness import _body_items
        text = "Baseline was stable. The effect was reliable (P ¼ 0.038) here."
        i = _body_items(text)[0]
        assert text[i["offset"]:i["offset"] + len(i["raw"])] == i["raw"]

    def test_the_repair_is_length_preserving(self):
        """The load-bearing property: only the single character is swapped and
        every surrounding space is kept, so an offset into the repaired text is
        an offset into the original."""
        from metascience_agent.completeness import _repair_equals
        for s in ("P ¼ 0.038", "n ¼ 68", "F CL ¼ 45.43; DFn ¼ 19", "no quarter here"):
            assert len(_repair_equals(s)) == len(s), s

    def test_one_quarter_is_left_alone(self):
        """`¼` means one quarter. The repair only fires between a word or
        closing bracket and a NUMBER, where it cannot."""
        from metascience_agent.completeness import _repair_equals
        assert _repair_equals("improvement in ¼ of patients") == \
            "improvement in ¼ of patients"
        assert "¼" in _repair_equals("roughly ¼ responded")


class TestTheTwoWaysAPaperPrintsAMeanAndItsDispersion:
    """The enumerator recognised ONE of the three conventions -- `4.17 (SD =
    1.19)` -- and missed both of the ones journals actually use. Found by
    checking exhaustiveness against a real paper rather than by any test."""

    def test_the_APA_comma_form(self):
        """`M = 4.64, SD = 1.50`. Psychology's convention, and the fraud
        ground-truth papers are psychology: 37 pairs in
        10.1007--s11031-011-9216-y alone, every one invisible."""
        from metascience_agent.completeness import _body_items
        items = _body_items("the control condition (M = 6.82, SD = .67) did not")
        assert [i["kind"] for i in items] == ["mean_sd_apa"]

    def test_the_clinical_plus_minus_form(self):
        """`65.2 ± 1.17`. MEASURED over the 305-paper cerebrolysin corpus: 128
        papers (42%) use it, 5,942 occurrences, none indexed. The floor exists
        to say what the model overlooked and could not see the commonest way a
        clinical paper prints a mean."""
        from metascience_agent.completeness import _body_items
        for text in ("mean age was 65.2 ± 1.17 years", "65.2 +/- 1.17"):
            assert [i["kind"] for i in _body_items(text)] == ["mean_pm_prose"], text

    def test_the_parenthesised_form_still_works(self):
        from metascience_agent.completeness import _body_items
        assert [i["kind"] for i in _body_items("scores of 4.17 (SD = 1.19) here")] \
            == ["mean_sd_prose"]

    def test_a_control_character_dispersion_needs_the_document_to_prove_it(self):
        """REVISED 2026-08-19, and the old premise was wrong. This test used to
        assert that `\\x06` is `±` full stop -- "the same damage class as `¼`
        for `=`". It is not a damage class, it is a font-specific GLYPH INDEX,
        and measuring both corpora settled it:

            EPIVI7B3      226 occurrences    0 literal `±`   40 `mean \\x06 SD`
            YR8VZZRJ       23                0                1
            YLHWMEJ3       50                0                0
            jnn.2011.5114  21              471                0

        In the last one `\\x06` is a DECIMAL POINT -- `P < 0\\x0605` is
        `P < 0.05` -- and that paper prints 471 literal `±`, so it cannot also
        be spelling `±` this way. Under the old assumption that sentence yielded
        `p_value` with raw `P < 0`: a reported p of ZERO, which is impossible
        and which any reported-versus-computed check can turn into an accusation
        against an honest paper.

        So a bare snippet proves nothing and is refused; the same text carrying
        the anchor is read. The cost is accepted knowingly: YLHWMEJ3's 50
        dispersions are very probably `±` and go unread, because being nearly
        sure is still a guess about a digit."""
        from metascience_agent.completeness import _body_items
        assert _body_items("the 65 \x06 1.17 group") == []
        proved = "Values are mean \x06 SD. The 65 \x06 1.17 group improved."
        assert "mean_pm_prose" in [i["kind"] for i in _body_items(proved)]

    def test_enumerating_is_not_typing(self):
        """What follows `±` may be an SD, an SE or a half-interval. This does
        not decide which -- that is the typer's job, and a value nobody can
        type is still a value the paper printed."""
        from metascience_agent.completeness import _body_items
        i = _body_items("65.2 ± 1.17")[0]
        assert i["kind"] == "mean_pm_prose"
        assert "sd" not in i["kind"]


class TestOperatorEntitiesHideAPValue:
    """docling leaves `&lt;` undecoded, so `p &lt; .05` never matched a pattern
    wanting a literal `<`. MEASURED over the 305-paper cerebrolysin corpus: 265
    papers (87%) contain an entity on 3,393 lines, and 1,901 hits are
    `p &lt; <number>` -- every one a p-value invisible to this enumerator AND to
    statcheck, whose whole job is comparing a reported p against a recomputed
    one. Repairing them takes the corpus from 12,974 prose statistics to
    15,296."""

    def test_an_entity_hidden_p_value_is_enumerated(self):
        from metascience_agent.completeness import _body_items
        items = _body_items("the effect was reliable (p &lt; .05) overall")
        assert [i["kind"] for i in items] == ["p_value"]

    def test_raw_is_what_the_source_contains(self):
        from metascience_agent.completeness import _body_items
        text = "the effect was reliable (p &lt; .05) overall"
        i = _body_items(text)[0]
        assert i["raw"] == "p &lt; .05"
        assert i["raw"] in text

    def test_the_repair_is_length_preserving(self):
        """Padded, the same discipline as the mojibake `=`: an offset into the
        repaired text stays an offset into the original."""
        from metascience_agent.completeness import _repair_entities
        for s in ("p &lt; .05", "a &gt; b", "x &amp; y", "no entities here"):
            assert len(_repair_entities(s)) == len(s), s

    def test_offsets_still_point_into_the_original(self):
        from metascience_agent.completeness import _body_items
        text = "Baseline held. The effect was reliable (p &lt; .05) overall."
        i = _body_items(text)[0]
        assert text[i["offset"]:i["offset"] + len(i["raw"])] == i["raw"]


class TestANamedQuantityGivenAValue:
    """`n = 202`, `partial η² = 0.048`, `MWcombined = 0.69`. Positive-only: it
    adds classifications and removes nothing. It recovers the one input GRIM
    needs most -- a sample size stated in prose -- which no other pattern here
    matches. +1,745 statistics across the corpus."""

    def _kinds(self, text):
        from metascience_agent.completeness import _body_items
        return [(i["kind"], i["raw"]) for i in _body_items(text)]

    def test_a_prose_sample_size_is_finally_enumerated(self):
        assert self._kinds("participants (N = 45, 30 female)") == [
            ("named_equality", "N = 45")]

    def test_an_effect_size_and_a_fused_subscript(self):
        assert self._kinds("partial η² = 0.048 for")[0][0] == "named_equality"
        assert self._kinds("Mfemales = 6.22 vs")[0][1] == "Mfemales = 6.22"

    def test_a_closed_symbol_list_not_any_identifier(self):
        """A general `identifier = number` would swallow software versions and
        table coordinates."""
        assert self._kinds("version 2 = 3 of the") == []
        assert self._kinds("Table 2 shows") == []

    def test_the_paired_patterns_still_win(self):
        """`M = 6.82, SD = .67` must stay ONE item covering both numbers rather
        than being split by the single-value rule."""
        assert self._kinds("the control (M = 6.82, SD = .67) did") == [
            ("mean_sd_apa", "M = 6.82, SD = .67")]
        assert self._kinds("Age was 65.2 ± 1.17 years")[0][0] == "mean_pm_prose"


class TestThreeGapsTheRulesCatalogueFound:
    def _kinds(self, text):
        from metascience_agent.completeness import _body_items
        return [(i["kind"], i["raw"]) for i in _body_items(text)]

    def test_welch_decimal_degrees_of_freedom(self):
        """The df was `\\d+`, so `t(243.39) = 2.11` matched nothing. An
        unequal-variance t-test is the ordinary case in psychology, not an
        exotic one."""
        assert ("nhst", "t(243.39) = 2.11") in self._kinds("t(243.39) = 2.11, p = .03")

    def test_out_of_is_a_fraction(self):
        assert self._kinds("13 out of 14 responded") == [("n_of_total", "13 out of 14")]

    def test_the_unparenthesised_confidence_interval(self):
        """`95% CI 0.50 to 0.81`. Both bounds are one item, because an interval
        is one reported quantity however it is punctuated."""
        assert self._kinds("95% CI 0.50 to 0.81 overall") == [
            ("ci_to_form", "95% CI 0.50 to 0.81")]

    def test_the_parenthesised_forms_still_match(self):
        assert self._kinds("OR 1.42 (95% CI 1.08-1.9)")[0][0] == "estimate_ci_prose"
        assert self._kinds("F(1, 46) = 6.95")[0][0] == "nhst"


class TestTheRepairBelongsAtTheReader:
    """Greg: "couldn't we just add a preliminary step in which the docling
    extraction had this string replaced with the correct mathematical
    operator?" -- and he was right. Repairing it inside `completeness` fixed the
    FLOOR while leaving the FINDER reading mojibake, which is backwards.

    The markdown path bypassed `_normalise` entirely: XML text got its
    digit-group spaces, true minus and exotic whitespace repaired, while
    `body.md` was read raw. So every docling-extracted paper -- most of them --
    reached the model with damage the XML papers never had."""

    def test_the_reader_decodes_operator_entities(self):
        from metascience_agent.extraction.jats import repair_extraction_damage
        assert repair_extraction_damage("p &lt; .05 and a &gt; b") == "p < .05 and a > b"

    def test_the_reader_repairs_the_mojibake_equals(self):
        from metascience_agent.extraction.jats import repair_extraction_damage
        assert repair_extraction_damage("n ¼ 68 patients") == "n = 68 patients"

    def test_one_quarter_is_still_one_quarter(self):
        from metascience_agent.extraction.jats import repair_extraction_damage
        assert repair_extraction_damage("in ¼ of patients") == "in ¼ of patients"

    def test_it_is_idempotent_so_two_layers_cannot_drift(self):
        """`completeness` keeps its own repair for callers that pass raw text
        directly. Decoding already-decoded text must be a no-op."""
        from metascience_agent.extraction.jats import repair_extraction_damage as R
        once = R("p &lt; .05")
        assert R(once) == once == "p < .05"

    def test_this_is_restoring_the_paper_not_editing_it(self):
        """`&lt;` is not what the paper printed -- the paper printed `<`, and
        the entity is damage the extractor added. That is why the repair belongs
        above every consumer rather than inside one."""
        from metascience_agent.extraction.jats import repair_extraction_damage as R
        assert "&" not in R("p &lt; .05")


class TestASplitDecimalIsOneNumber:
    """docling splits a decimal point off its digits in some PDFs: `0 . 28`.
    An index over that text reports TWO numbers where the paper printed one, so
    the floor counts a value twice. MEASURED across the 211-paper Zotero corpus:
    380 tokens."""

    def test_the_decimal_is_rejoined(self):
        from metascience_agent.extraction.jats import repair_extraction_damage as R
        from metascience_agent import numerals as N
        assert R("a value of 0 . 28 here") == "a value of 0.28 here"
        assert [r["printed"] for r in N.index(R("x 0 . 06 to + 0 . 28"))] == \
            ["0.06", "0.28"]

    def test_a_numbered_list_marker_is_left_alone(self):
        """A SPACE BEFORE THE DOT is required, which is what separates a broken
        decimal from `1. Text`."""
        from metascience_agent.extraction.jats import repair_extraction_damage as R
        assert R("1. Text follows") == "1. Text follows"
        assert R("see 1. 5 above") == "see 1. 5 above"


class TestTheProseHalfNeedsTheSameArticleTheTableHalfUses:
    """`_article_pdf` demanded a DECLARED article; `prepass._article_pdf_tables`
    already fell back to the sole PDF and warned. So on a directory holding a
    bare `paper.pdf` the TABLE half read the paper and the PROSE half returned
    nothing -- same paper, same run.

    MEASURED on the 217-paper Zotero corpus: every directory holds exactly one
    PDF, none declared, so the prose half was empty for ALL of them. With the
    sole-PDF fallback, 211 yield text and `_body_items` finds 11,247 statistics
    that nothing had ever been handed."""

    def test_the_only_pdf_is_the_article(self, tmp_path):
        from metascience_agent.completeness import _article_pdf
        d = tmp_path / "PAPERKEY"
        d.mkdir()
        (d / "paper.pdf").write_bytes(b"%PDF-1.4\n")
        got, how = _article_pdf(d)
        assert got is not None and got.name == "paper.pdf"
        assert "only PDF" in how

    def test_several_pdfs_and_no_declaration_still_refuses(self, tmp_path):
        """Then the ambiguity is real: a supplement's prose would enter the
        manifest as the paper's own body."""
        from metascience_agent.completeness import _article_pdf
        d = tmp_path / "PAPERKEY"
        d.mkdir()
        (d / "paper.pdf").write_bytes(b"%PDF-1.4\n")
        (d / "supplement.pdf").write_bytes(b"%PDF-1.4\n")
        got, how = _article_pdf(d)
        assert got is None
        assert "2 PDFs" in how and "refusing to guess" in how

    def test_no_pdf_at_all_is_still_reported(self, tmp_path):
        from metascience_agent.completeness import _article_pdf
        d = tmp_path / "PAPERKEY"
        d.mkdir()
        got, how = _article_pdf(d)
        assert got is None and "no article PDF found" in how

    def test_a_declaration_still_wins(self, tmp_path):
        """The fallback must not overtake the authority it backs up."""
        import json
        from metascience_agent.completeness import _article_pdf
        d = tmp_path / "PAPERKEY"
        d.mkdir()
        (d / "a.pdf").write_bytes(b"%PDF-1.4\n")
        (d / "b.pdf").write_bytes(b"%PDF-1.4\n")
        (d / "inputs.json").write_text(json.dumps(
            {"article": "b.pdf", "supplements": ["a.pdf"]}))
        got, how = _article_pdf(d)
        assert got is not None and got.name == "b.pdf"
        assert how == "declared by operator", (
            "an operator's inputs.json must be distinguishable from a "
            "filename convention")
