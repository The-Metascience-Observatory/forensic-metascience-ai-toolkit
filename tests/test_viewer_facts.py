"""The viewer's claims about ITS OWN WORK, which nothing could test until now.

Every function under test was previously a JavaScript expression inside a
Python template string. None was reachable by a test, and all four were
measurably wrong on a real bundle -- which is how a document whose authority
rests on being auditable ended up less scrupulous about itself than about the
paper it reviews.

THE NUMBERS BELOW ARE MEASURED, not invented. `REAL` is the payload of
`tests/fixtures/papers/cerebrolysin_run_2026-08-09/10.1007--s11064-023-03861-8/forensic_review_opus_08_10_2026_bundle`,
re-parsed here so the regressions are pinned against a genuine artefact rather
than a fixture that agrees with the code by construction.
"""
import json
import pathlib
import re

import pytest

from forensic_metascience_ai_toolkit import viewer_facts as VF

BUNDLE = pathlib.Path(__file__).resolve().parents[1] / (
    "tests/fixtures/papers/cerebrolysin_run_2026-08-09/10.1007--s11064-023-03861-8/"
    "forensic_review_opus_08_10_2026_bundle/viewer.html")


def _real():
    if not BUNDLE.exists():
        pytest.skip("archived bundle not present in this checkout")
    m = re.search(r'id="payload"[^>]*>(.*?)</script>',
                  BUNDLE.read_text(errors="ignore"), re.S)
    if not m:
        pytest.skip("bundle carries no embedded payload")
    return json.loads(m.group(1))


class TestSeverityLedger:
    """The Overview printed the WRITE-UP severities under the label 'sweep tool
    verdicts ... passes included', and the table 300px below disagreed."""

    def test_the_two_universes_are_different_on_the_real_bundle(self):
        led = VF.severity_ledger(_real())
        assert led["write_up"]["total"] == 20
        assert led["tool"]["total"] == 24
        assert led["write_up"]["counts"] == {
            "suspicious": 12, "highly_suspicious": 4, "indeterminate": 4}
        assert led["tool"]["counts"] == {
            "highly_suspicious": 8, "suspicious": 11, "consistent": 2,
            "indeterminate": 3}

    def test_the_dropped_passes_are_named(self):
        """Not a neutral rounding. `consistent` is the ONLY category that is good
        news for the authors, and a summary that silently omits it is biased in
        the accusing direction."""
        assert VF.severity_ledger(_real())["consistent_dropped"] == 2

    def test_each_universe_carries_the_population_it_counted(self):
        """The recurring defect was never arithmetic -- each count was right. It
        was a number printed under a description of a different set."""
        led = VF.severity_ledger(_real())
        assert "findings" in led["write_up"]["population"]
        assert "passes included" in led["tool"]["population"]

    def test_the_check_table_copy_agrees_with_the_findings(self):
        """If these ever diverge, two parts of the page count the same thing
        differently and a reader cannot tell which to believe."""
        led = VF.severity_ledger(_real())
        assert led["agree"] is True

    def test_an_empty_payload_returns_zeroes_not_a_crash(self):
        led = VF.severity_ledger({})
        assert led["write_up"]["total"] == 0 and led["tool"]["total"] == 0
        assert VF.severity_ledger(None)["consistent_dropped"] == 0


class TestTraceability:
    """The most-repeated self-criticism in the document, and it was false."""

    def test_the_three_questions_get_three_answers_on_the_real_bundle(self):
        tr = VF.traceability(_real())
        assert tr["n"] == 20
        assert tr["quotes_located"]["with_quote"] == 20
        assert tr["quotes_located"]["verdicts"] == {"verbatim": 17, "stitched": 3}
        assert tr["quotes_located"]["located_in_paper"] == 17
        assert tr["joined_to_call"]["n"] == 4
        assert tr["anchored"]["n"] == 20

    def test_stitched_does_not_count_as_located(self):
        """WE assembled that sentence and it does not appear in the paper, so it
        evidences nothing about what the authors wrote. Same split
        `anatomy.bounds_are_stated` uses."""
        tr = VF.traceability({"findings": [
            {"quote": "a", "quote_verified": "verbatim"},
            {"quote": "b", "quote_verified": "stitched"},
            {"quote": "c", "quote_verified": "unverified"},
        ]})
        assert tr["quotes_located"]["with_quote"] == 3
        assert tr["quotes_located"]["located_in_paper"] == 1

    def test_the_sentence_leads_with_what_IS_traceable(self):
        """The old sentence -- '12 of 16 tool verdicts cite numbers this bundle
        cannot trace back to a passage of the paper' -- reported the NARROW join
        under the BROAD description, telling a cold reader that three quarters of
        our numbers were untraceable when 17 of 20 were located verbatim."""
        s = VF.traceability_sentence(VF.traceability(_real()))
        assert s.startswith("20 of 20 findings quote a passage")
        assert "17 verbatim" in s
        assert "12 could not be tied" in s

    def test_the_sentence_still_states_the_narrow_failure(self):
        """Correcting an over-claim must not become an under-claim. The join
        genuinely failed on most findings and the sentence must say so."""
        s = VF.traceability_sentence(VF.traceability(_real()))
        assert "could not be tied" in s and "validated check" in s

    def test_the_join_denominator_excludes_HAND_READ_findings(self):
        """The same error this module exists to fix, one level down, and an
        existing test in test_bundle caught me making it.

        A `technique: manual` finding is a value the model read off the paper
        itself; NO PRODUCING CALL EXISTS for it, by construction rather than by
        failure. Counting it among the findings we "could not tie to a validated
        call" reports a design fact as a coverage failure and inflates our own
        stated shortfall -- in the one direction this document must never err.
        """
        tr = VF.traceability(_real())
        assert tr["n"] == 20
        assert tr["joined_to_call"]["of"] == 16
        assert tr["joined_to_call"]["hand_read_excluded"] == 4
        s = VF.traceability_sentence(tr)
        assert "no producing call exists for them" in s

    def test_an_all_hand_read_run_claims_no_shortfall_at_all(self):
        """With nothing joinable, "0 of 0" would invent a failure out of a
        design fact, so the clause is omitted entirely."""
        s = VF.traceability_sentence(VF.traceability({"findings": [
            {"quote": "x", "quote_verified": "verbatim", "technique": "manual"}] * 3}))
        assert "could not be tied" not in s
        assert "3 of 3 findings quote a passage" in s

    def test_stitched_quotes_are_described_not_just_counted(self):
        s = VF.traceability_sentence(VF.traceability(_real()))
        assert "assembled from adjacent text" in s

    def test_no_findings_is_stated_plainly(self):
        assert "nothing to trace" in VF.traceability_sentence(VF.traceability({}))


class TestEvidenceGrade:
    """THE PREDICATE MATTERS AND THE OBVIOUS ONE IS WRONG.

    A design review proposed banner-flagging report findings with no
    `stage1_finding_ids`. On the run it cited as motivation that predicate fires
    on 0 of 8. The real structure is a chain, and the dangerous case is a
    finding whose backing sweep findings are themselves `technique: manual`.
    """

    def _sweep(self):
        return {"s1": {"id": "s1", "technique": "rivets_independent_t"},
                "s2": {"id": "s2", "technique": "manual"},
                "s3": {"id": "s3", "technique": "manual"}}

    def test_a_validated_technique_is_computed(self):
        g = VF.evidence_grade({"stage1_finding_ids": ["s1"]}, self._sweep())
        assert g["grade"] == "computed"

    def test_backing_that_is_ALL_manual_is_hand_computed(self):
        g = VF.evidence_grade({"stage1_finding_ids": ["s2", "s3"]}, self._sweep())
        assert g["grade"] == "hand_computed"
        assert "no validated check computed it" in g["headline"]

    def test_one_validated_backing_is_enough_to_be_computed(self):
        """A finding resting on a real check plus a remark is still resting on a
        real check. Grading it down would hide the checks we did run."""
        g = VF.evidence_grade({"stage1_finding_ids": ["s1", "s2"]}, self._sweep())
        assert g["grade"] == "computed"

    def test_no_backing_ids_is_a_reading_not_a_hand_computation(self):
        """Different facts, different sentences. A hand-computed finding has
        arithmetic nobody checked; a reading has no arithmetic at all and
        nothing to re-run. The viewer said one sentence over both."""
        g = VF.evidence_grade({}, self._sweep())
        assert g["grade"] == "reading"
        assert "no arithmetic to re-run" in g["detail"]

    def test_dangling_ids_fall_to_reading_and_are_reported(self):
        """A reference that resolves to nothing is a broken audit trail, and the
        safe reading of a broken trail is that nothing verified sits behind it."""
        g = VF.evidence_grade({"stage1_finding_ids": ["nope"]}, self._sweep())
        assert g["grade"] == "reading"
        assert g["dangling_ids"] == ["nope"]

    @pytest.mark.parametrize("tech", ["manual", "", None, "unknown", "MANUAL"])
    def test_every_non_tool_technique_counts_as_the_model_doing_it(self, tech):
        sweep = {"x": {"id": "x", "technique": tech}}
        assert VF.evidence_grade({"stage1_finding_ids": ["x"]}, sweep)["grade"] \
            == "hand_computed"


class TestEvidenceLedger:
    def test_the_real_bundle_splits_seven_four_one(self):
        led = VF.evidence_ledger(_real())
        assert led["n"] == 12
        assert led["counts"] == {"computed": 7, "hand_computed": 4, "reading": 1}

    def test_the_number_that_actually_matters_is_surfaced(self):
        """Three of the four hand-computed findings on this paper are
        `suspicious`. A finding at that severity resting on unverified
        arithmetic is the shape most likely to become a false accusation, and
        nothing on its card said so."""
        assert VF.evidence_ledger(_real())["accusatory_without_a_validated_check"] == 4

    def test_every_finding_is_graded_none_silently_skipped(self):
        led = VF.evidence_ledger(_real())
        assert len(led["per_finding"]) == led["n"]
        assert all(f["grade"] in VF.EVIDENCE_GRADES for f in led["per_finding"])

    def test_empty_input_is_safe(self):
        assert VF.evidence_ledger({})["n"] == 0
        assert VF.evidence_ledger(None)["counts"]["computed"] == 0


class TestRefusalClassifier:
    """Ported from JS, widened, and reachable by a test for the first time.

    On the real bundle it left 9 of 13 rows `unclassified` -- the modal outcome
    on the mechanism built specifically to stop the shortfall list reading as a
    task list abandoned.
    """

    @pytest.mark.parametrize("reason", [
        # The two misses a design review quoted verbatim from a real run.
        "Correctly inapplicable and not run. Every variable in these tables is a "
        "continuous physiological or biochemical measure.",
        "Cross-table scanning was not run because the tables report different "
        "physical quantities.",
        # And the rest of the widening.
        "This check has no meaning here.",
        "The design bars this check.",
        "Correctly not run: there is no null to test.",
    ])
    def test_the_widened_declarations_are_classified(self, reason):
        assert VF.classify_refusal(reason)["key"] == "na"

    def test_an_explicit_declaration_still_beats_every_keyword(self):
        """ORDER IS LOAD-BEARING and unchanged from the JS. The alternative was
        measured: 'detect_duplication across tables -- Not applicable. The paper
        reports no means with standard deviations anywhere' was filed under 'the
        paper does not report it', turning a check that does not apply into an
        implied deficiency of the publication."""
        r = ("detect_duplication across tables -- Not applicable. The paper "
             "reports no means with standard deviations anywhere.")
        assert VF.classify_refusal(r)["key"] == "na"

    @pytest.mark.parametrize("reason,key", [
        ("The paper prints no test statistic for this comparison.", "paper"),
        ("The supplement was not supplied to this review.", "inputs"),
        ("No OCR engine was available to this run.", "ours"),
        ("Values are embedded as an image.", "inputs"),
    ])
    def test_the_original_buckets_are_unchanged(self, reason, key):
        assert VF.classify_refusal(reason)["key"] == key

    def test_a_tie_between_our_limit_and_the_papers_resolves_against_us(self):
        """THE PROPERTY, not the pattern string.

        This assertion used to pin the `ours` regex to a literal and forbid any
        change to it, on the reasoning that widening the self-blaming bucket
        flatters the paper. The reasoning is right about UNPRINCIPLED widening
        and wrong as a rule: `ours` was later widened on measured evidence --
        every added phrase names a tool this kit does not have ("no tool in the
        suite converts a Pearson r to a p-value"), which is a fact about us, and
        60 archived rows saying exactly that were sitting in `unclassified`.

        A literal-equality test on a regex forbids the improvement without
        checking the thing worth protecting. This is that thing: when a reason
        names BOTH our limit and the paper's, we take the blame.
        """
        both = ("The paper reports no exact p-value, and no tool in this kit "
                "converts a chi-squared statistic plus df to one.")
        assert VF.classify_refusal(both)["key"] == "ours"

    def test_a_paper_only_deficiency_is_never_swept_into_ours(self):
        """The other direction of the same guard: the widening must not have
        made `ours` greedy enough to absorb plain reporting gaps, which would
        hide questions worth putting to the authors."""
        for r in ("The paper prints no standard deviation for any outcome.",
                  "Every efficacy value exists only as a bar in a figure.",
                  "The paper states no power calculation."):
            assert VF.classify_refusal(r)["key"] == "paper"

    def test_a_paper_with_no_figures_is_not_a_paper_with_a_defect(self):
        """MEASURED: 6 archived rows saying "the paper contains no data figures"
        were landing in `paper` -- "the paper does not report it" -- which reads
        as a deficiency. A paper without figures is an ordinary paper."""
        r = ("The paper contains no data figures; the markdown extraction shows "
             "only decorative image placeholders.")
        assert VF.classify_refusal(r)["key"] == "na"

    def test_a_paper_we_were_only_sent_the_XML_of_is_not_deficient(self):
        """MEASURED: 4 archived rows. "No PDF exists for this paper" was filed
        as `paper`, blaming the publication for what we were not sent."""
        r = ("No PDF exists for this paper -- only an XML full text -- so "
             "extract_figures could not be run and no figure was inspected.")
        assert VF.classify_refusal(r)["key"] == "inputs"

    def test_the_commonest_phrasing_of_all_is_not_missed(self):
        """`not provided` was absent from a list that had `not supplied`,
        `not present` and `not delivered`. 45 archived rows -- the single
        largest class in the whole unclassified lump."""
        for r in ("Supplement 2 was not provided.",
                  "None are provided with the article.",
                  "None accompany this article; only the .xml was present."):
            assert VF.classify_refusal(r)["key"] == "inputs"

    def test_an_unmatched_reason_says_so_rather_than_guessing(self):
        assert VF.classify_refusal("Mumble.")["key"] == "unclassified"
        assert VF.classify_refusal(None)["key"] == "unclassified"

    def test_it_measurably_improves_on_the_real_refusal_rows(self):
        """The point of the widening, measured rather than asserted."""
        rows = _real().get("unchecked") or _real().get("not_run") or []
        rows = [r for r in rows if isinstance(r, dict) and r.get("reason")]
        if not rows:
            pytest.skip("this bundle records no refusal reasons under a known key")
        tally = VF.refusal_tally(rows)
        assert tally["counts"].get("unclassified", 0) < tally["n"]


class TestRefusalTally:
    def test_it_warns_when_the_classifier_is_mostly_failing(self):
        """A breakdown in which most rows are unclassified LOOKS like an answer
        and is not one."""
        rows = [{"reason": "Mumble."}] * 7 + [{"reason": "Not applicable."}] * 2
        t = VF.refusal_tally(rows)
        assert t["classifier_failing"] is True
        assert "read them rather than the counts" in t["warning"].lower()

    def test_no_warning_when_it_is_working(self):
        rows = [{"reason": "Not applicable."}] * 8 + [{"reason": "Mumble."}]
        t = VF.refusal_tally(rows)
        assert t["classifier_failing"] is False and "warning" not in t

    def test_every_bucket_ships_with_its_meaning(self):
        """A count is never printed without its reading -- 'the paper does not
        report it' and 'this toolkit could not do it' are opposite facts."""
        t = VF.refusal_tally([{"reason": "Not applicable."}])
        assert set(t["meaning"]) >= {"na", "paper", "inputs", "ours", "unclassified"}
        assert "only bucket that is our shortfall" in t["meaning"]["ours"][1]

    def test_empty_rows_do_not_raise_the_alarm(self):
        t = VF.refusal_tally([])
        assert t["n"] == 0 and t["classifier_failing"] is False


class TestTheFactsActuallyReachTheBundle:
    """THE REGRESSION THAT ACTUALLY HAPPENED, and which every other test here
    missed.

    A concurrent agent stashed this working tree mid-edit, and the fifteen lines
    that assemble `payload["facts"]` never reached the commit that claimed to
    wire them. For four commits `D.facts` was undefined on every real bundle --
    the corrected traceability sentence and both severity-ledger rows rendering
    as the EMPTY STRING -- while the suite stayed green, because every test
    above asserts on a rendered fragment built from a payload the test itself
    supplies.

    A viewer test that never calls `collect()` cannot tell "the code is right"
    from "the code is right and unreachable". These do.
    """

    def _collected(self):
        import pathlib

        from forensic_metascience_ai_toolkit.bundle import collect
        review = (pathlib.Path(__file__).resolve().parents[1]
                  / "tests/fixtures/papers/cerebrolysin_run_2026-08-09/10.1007--s11064-023-03861-8"
                  / "forensic_review_opus_08_10_2026")
        if not review.is_dir():
            pytest.skip("archived review not present in this checkout")
        return collect(review)

    def test_collect_emits_the_facts_block(self):
        facts = self._collected().get("facts")
        assert facts, "collect() produced no `facts` -- the viewer reads D.facts"
        assert set(facts) >= {"severity", "traceability",
                              "traceability_sentence", "evidence"}

    def test_the_sentence_is_non_empty_and_is_the_corrected_one(self):
        s = self._collected()["facts"]["traceability_sentence"]
        assert s.startswith("20 of 20 findings quote a passage")

    # RE-MEASURED 2026-10-19 after this run was converted to findings.v2.json
    # and its serial-pipeline files deleted. The tool universe is the tools
    # agent's ledger alone now (15; the editorial ledger's 9 went with
    # toolcalls.stage2.json), and the graded population is the 20 sweep rows,
    # not the 12 report.json findings: 16 name a registered technique, 4 are
    # `manual`.
    def test_the_severity_ledger_carries_both_universes(self):
        sev = self._collected()["facts"]["severity"]
        assert sev["write_up"]["total"] == 20
        assert sev["tool"]["total"] == 15
        assert sev["consistent_dropped"] == 1

    def test_the_evidence_ledger_grades_every_report_finding(self):
        ev = self._collected()["facts"]["evidence"]
        assert ev["counts"] == {"computed": 16, "hand_computed": 0, "reading": 4}
        assert len(ev["per_finding"]) == ev["n"] == 20

    def test_every_graded_finding_carries_a_settle_this(self):
        """Never silent: a card that ends without saying what would resolve it
        invites the reader to treat it as settled already."""
        for f in self._collected()["facts"]["evidence"]["per_finding"]:
            assert f["settle"]["text"], f"no settle-this for {f['title']!r}"

    def test_the_classifier_table_is_shipped_rather_than_restated_in_js(self):
        """Two copies existed and had already DRIFTED -- the JS `na` tier was
        six alternations behind Python's -- so a reason could be bucketed one
        way by this suite and another way by the page the suite covers."""
        shipped = self._collected()["facts"]["refusal_kinds"]
        assert [(k["key"], k["label"], k["re"]) for k in shipped] == list(
            VF.REFUSAL_KINDS)

    def test_the_js_reads_the_shipped_table_and_keeps_a_literal_only_as_fallback(self):
        """A bundle built before the field existed still has to classify, so
        the JS literal stays -- but it must be the FALLBACK, never the source."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src/forensic_metascience_ai_toolkit/bundle.py").read_text(encoding="utf-8")
        i = src.index("const REFUSAL_KINDS=")
        head = src[i:i + 260]
        assert "D.facts" in head and "refusal_kinds" in head
        assert "new RegExp" in head, "must compile the shipped strings, not re-embed literals"


class TestTheFindingIndex:
    """One row per finding, properties never a score.

    Twelve findings, each roughly one screen, no collapse and no way to triage:
    a reader had to scroll the whole page to learn whether anything touched a
    conclusion they must act on.
    """

    def _payload(self, **over):
        base = {
            "findings": [{"id": "s1", "technique": "rivets_independent_t"},
                         {"id": "s2", "technique": "manual"}],
            "report_obj": {"findings": [
                {"title": "B", "severity": "suspicious", "location": "Table 3",
                 "stage1_finding_ids": ["s2"], "reproduction_valid": True,
                 "consequence": {"basis": "asserted", "claims_affected": 2,
                                 "flips_significance": False}},
                {"title": "A", "severity": "impossible", "location": "Table 1",
                 "stage1_finding_ids": ["s1"], "reproduction_valid": False,
                 "consequence": {"basis": "computed", "claims_affected": 1,
                                 "flips_significance": True}},
            ]}}
        base.update(over)
        return base

    def test_it_sorts_by_severity_not_by_input_order(self):
        rows = VF.finding_index(self._payload())
        assert [r["severity"] for r in rows] == ["impossible", "suspicious"]

    def test_the_row_number_stays_the_finding_number(self):
        """Sorting must not renumber: the index links to `#f{n}` and the card
        prints `{n}.`, so a reordered number would point at the wrong card."""
        rows = VF.finding_index(self._payload())
        assert {r["title"]: r["n"] for r in rows} == {"B": 1, "A": 2}

    def test_an_asserted_consequence_is_marked_and_a_computed_one_is_not(self):
        """The one subjective column must not borrow the authority of the
        objective ones beside it."""
        rows = {r["title"]: r for r in VF.finding_index(self._payload())}
        assert rows["B"]["changes_computed"] is False
        assert rows["A"]["changes_computed"] is True

    def test_the_evidence_grade_matches_the_card_banner(self):
        """One computation, so the index and the card cannot disagree about the
        same finding."""
        rows = {r["title"]: r for r in VF.finding_index(self._payload())}
        assert rows["B"]["evidence"] == "hand_computed"
        assert rows["A"]["evidence"] == "computed"

    def test_flips_and_claims_are_both_stated(self):
        rows = {r["title"]: r for r in VF.finding_index(self._payload())}
        assert rows["A"]["changes"] == "a significance decision and 1 stated claim"
        assert rows["B"]["changes"] == "2 stated claims"

    def test_undetermined_and_harmless_are_different_words(self):
        """`None` means we did not determine it; `0` means we determined it
        changes nothing. Rendering both as blank would let an undetermined
        consequence read as a harmless one."""
        p = self._payload()
        p["report_obj"]["findings"][0]["consequence"] = {"basis": "asserted"}
        p["report_obj"]["findings"][1]["consequence"] = {
            "basis": "asserted", "claims_affected": 0, "flips_significance": False}
        rows = {r["title"]: r for r in VF.finding_index(p)}
        assert rows["B"]["changes"] == "not determined"
        assert rows["A"]["changes"] == "nothing the paper states"

    def test_a_missing_consequence_does_not_crash(self):
        p = self._payload()
        del p["report_obj"]["findings"][0]["consequence"]
        assert VF.finding_index(p)[0]["changes"]

    def test_no_report_findings_is_an_empty_index_not_an_error(self):
        assert VF.finding_index({}) == []
