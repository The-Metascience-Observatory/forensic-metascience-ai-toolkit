"""A paper's absent supplement must be stated, not silently skipped.

MEASURED on the high-value corpus: 76-83% of papers reference supplementary
material and essentially none of it is on disk. `agent._si_pass_text()` builds
a whole prompt pass for supplementary PDFs -- and returns "" when none is
found, so the pass vanishes without a word. The analysis skips SI in 100% of
runs while most papers point into it.

A verdict computed over the main text of a paper whose sensitivity analyses
live in an absent supplement is a different claim from a verdict over the whole
paper. The reader has to be told which one they are holding.
"""
import pytest

from metascience_agent.supplements import audit, find_references, write_declaration


def _declare(tmp_path, *names, role="supplements"):
    """Say what a file IS. Required since 2026-08-13, and the fixtures changed
    with it.

    Detection used to key on seven filename substrings, so `paper_supplementary
    .pdf` was found and Wiley's `EAT-58-1072-s001.docx` was not -- silently,
    landing in neither the usable nor the unusable list. Greg: "The detection of
    supplements shouldn't be contingent on the file naming... The user (or the
    agent they're interfacing with to use the CLI) should have to provide these,
    and specify."

    Several tests below were passing FOR THE WRONG REASON under the new rule --
    a zero-byte file excluded for being undeclared rather than for being empty
    -- so each declares first and then asserts the thing it is actually about.
    """
    write_declaration(tmp_path, **{role: list(names)})
    return tmp_path


class TestDetection:
    @pytest.mark.parametrize("text,style", [
        ("see eTable 3 in Supplement 1", "eTable / eFigure (JAMA)"),
        ("shown in Table S1", "Table S1 / Fig S1 style"),
        ("Supplementary Table 4 reports", "Supplementary Table/Figure"),
        ("in the Supporting Information", "Supporting Information"),
        ("Additional file 2 contains", "Additional file N (BMC)"),
        ("reported in Appendix B", "Appendix"),
    ])
    def test_each_citation_style(self, text, style):
        assert style in find_references(text)

    def test_case_insensitive(self):
        assert find_references("SUPPLEMENTARY TABLE 1")

    def test_clean_text_finds_nothing(self):
        assert find_references("The mean was 5.5 (SD 1.2) in Table 2.") == {}

    def test_duplicates_are_collapsed(self):
        refs = find_references("Table S1 and table s1 and Table S1 again")
        assert len(refs["Table S1 / Fig S1 style"]) == 1


class TestInlineAppendix:
    """An appendix printed in the paper is not a supplement we lack.

    10.1007--s00702-004-0248-2: "See Appendix for a listing of the members of
    the Cerebrolysin Study Group", and the appendix is right there in the main
    text under a `## Appendix` heading. The gate refused the paper as
    incomplete over material it was holding in its hand.
    """

    INLINE = (
        "See Appendix for a listing of the members of the Study Group.\n\n"
        "The results were significant.\n\n"
        "## Appendix\n\n"
        "The participants were: A. One, Clinic X; B. Two, Clinic Y.\n\n"
        "## References\n"
    )

    def test_inline_appendix_suppresses_the_generic_style(self):
        assert "Appendix" not in find_references(self.INLINE)

    def test_prose_citation_without_inline_section_still_flags(self):
        assert "Appendix" in find_references(
            "Full model details are reported in Appendix B of this article, "
            "which also lists the priors."
        )

    def test_supplementary_appendix_still_flags_despite_inline_one(self):
        refs = find_references(
            self.INLINE + "\nSee the Supplementary Appendix, available at "
            "NEJM.org, for the full protocol.\n"
        )
        assert "Supplementary Table/Figure" in refs

    def test_eappendix_still_flags_despite_inline_one(self):
        refs = find_references(self.INLINE + "\nDetails in eAppendix 2.\n")
        assert "eTable / eFigure (JAMA)" in refs

    def test_audit_and_gate_proceed_on_inline_appendix(self, tmp_path):
        from metascience_agent.supplements import gate
        (tmp_path / "body.md").write_text(self.INLINE)
        a = audit(tmp_path)
        assert a["missing"] is False
        assert a["references_supplement"] is False
        g = gate(tmp_path)
        assert g["proceed"] is True
        assert g["message"] == ""


class TestAudit:
    def test_referenced_and_absent_is_missing(self, tmp_path):
        (tmp_path / "body.md").write_text("See Supplementary Table 2.")
        a = audit(tmp_path)
        assert a["missing"] is True
        assert a["references_supplement"] is True

    def test_referenced_and_present_is_not_missing(self, tmp_path):
        (tmp_path / "body.md").write_text("See Supplementary Table 2.")
        (tmp_path / "paper_supplementary.pdf").write_bytes(b"%PDF")
        _declare(tmp_path, "paper_supplementary.pdf")
        a = audit(tmp_path)
        assert a["missing"] is False
        assert "paper_supplementary.pdf" in a["files_present"]

    def test_not_referenced_is_not_missing(self, tmp_path):
        (tmp_path / "body.md").write_text("A plain paper.")
        assert audit(tmp_path)["missing"] is False

    def test_the_main_pdf_is_not_mistaken_for_a_supplement(self, tmp_path):
        (tmp_path / "body.md").write_text("See Supplementary Table 2.")
        (tmp_path / "10.1234--demo.pdf").write_bytes(b"%PDF")
        assert audit(tmp_path)["missing"] is True

    def test_note_says_what_was_not_analysed(self, tmp_path):
        (tmp_path / "body.md").write_text("See eTable 1 in Supplement 1.")
        note = audit(tmp_path)["note"]
        assert "not analysed" in note
        assert "partial" in note.lower()

    def test_missing_directory_does_not_raise(self, tmp_path):
        """It must not raise -- and it must not answer "nothing is missing"
        either. There is no paper here to have read, so the answer is None."""
        a = audit(tmp_path / "nope")
        assert a["missing"] is None
        assert a["text_available"] is False


class TestFailClosedWithoutText:
    """`missing` was `bool(refs) and not have`, and an empty string matches no
    pattern -- so "this paper cites no supplement" and "we could not read a
    word of this paper" came back identical, and the gate passed on both.

    MEASURED before the PDF fallback existed: with only the main PDF in a clean
    directory, `paper_text` returned 0 characters for 7 of 7 PDF-only
    ground-truth papers and the gate PROCEEDED on all 7. `OVERRIDE_WARNING`
    never printed, so nothing in any report said the SI had been absent.
    """

    def test_no_text_at_all_is_unknown_not_absent(self, tmp_path):
        a = audit(tmp_path)
        assert a["missing"] is None
        assert a["references_supplement"] is None

    def test_the_note_says_it_could_not_be_checked(self, tmp_path):
        note = audit(tmp_path)["note"]
        assert "UNKNOWN" in note
        assert "indeterminate" in note

    def test_an_empty_body_file_is_still_unknown(self, tmp_path):
        """An empty extraction is not a paper that says nothing."""
        (tmp_path / "body.md").write_text("   \n")
        assert audit(tmp_path)["missing"] is None

    def test_present_files_still_satisfy_it(self, tmp_path):
        """We hold candidate SI files. Presence is the same evidence the normal
        path accepts, so the gate is satisfied -- but the citation question is
        reported as unanswered rather than answered "no"."""
        (tmp_path / "supplementary.pdf").write_bytes(b"%PDF-1.4 real enough")
        _declare(tmp_path, "supplementary.pdf")
        a = audit(tmp_path)
        assert a["missing"] is False
        assert a["references_supplement"] is None

    def test_a_readable_paper_says_so(self, tmp_path):
        (tmp_path / "body.md").write_text("A plain paper.")
        assert audit(tmp_path)["text_available"] is True

    def test_the_gate_refuses(self, tmp_path):
        from metascience_agent.supplements import gate
        g = gate(tmp_path)
        assert g["proceed"] is False
        assert "could not be read" in g["message"]

    def test_none_is_not_no(self, tmp_path):
        """`not None` is True, so a single falsy test on `missing` would have
        let the unverifiable case straight through -- the same bug one level
        up. This pins that the gate branches on identity, not truthiness."""
        from metascience_agent.supplements import gate
        g = gate(tmp_path)
        assert g["audit"]["missing"] is None
        assert g["proceed"] is False

    def test_no_flag_runs_an_unreadable_paper(self, tmp_path):
        """2026-10-18: an article we cannot read refuses whatever is passed --
        `analyze` used to let `--ok-if-supplementary-missing` through here."""
        from metascience_agent.supplements import gate
        g = gate(tmp_path, allow_incomplete=True)
        assert g["proceed"] is False
        assert "could not be read" in g["message"]


class TestAFileMustActuallyBeThere:
    """A NAME IS NOT A FILE.

    `present_files` matched on the filename alone, so a zero-byte
    `paper_supplementary.pdf` -- what an interrupted download, a failed `touch`
    or an unpulled git-lfs pointer leaves behind -- satisfied the gate and the
    run proceeded as though the SI had been read. That is the failure the gate
    exists to prevent, arriving through the one door it did not watch.
    """

    def _cites(self, tmp_path):
        (tmp_path / "body.md").write_text("See eTable 3 in Supplement 1.")
        return tmp_path

    def test_a_zero_byte_supplement_does_not_count(self, tmp_path):
        (self._cites(tmp_path) / "supplementary.pdf").write_bytes(b"")
        _declare(tmp_path, "supplementary.pdf")
        a = audit(tmp_path)
        assert a["missing"] is True
        assert a["files_present"] == []

    def test_it_says_why_the_file_was_rejected(self, tmp_path):
        """"We have no supplement" and "we have an empty file named like one"
        send an operator to different places."""
        (self._cites(tmp_path) / "supplementary.pdf").write_bytes(b"")
        _declare(tmp_path, "supplementary.pdf")
        a = audit(tmp_path)
        assert a["files_unusable"][0]["name"] == "supplementary.pdf"
        assert "zero bytes" in a["files_unusable"][0]["reason"]
        assert "zero bytes" in a["note"]

    def test_a_file_that_is_not_its_claimed_format_does_not_count(self, tmp_path):
        """An HTML error page saved as `supplement.pdf` is not a supplement."""
        (self._cites(tmp_path) / "supplement.pdf").write_bytes(b"<!DOCTYPE html>")
        _declare(tmp_path, "supplement.pdf")
        assert audit(tmp_path)["files_present"] == []

    def test_a_real_file_still_counts(self, tmp_path):
        (self._cites(tmp_path) / "supplementary.pdf").write_bytes(b"%PDF-1.4\n...")
        _declare(tmp_path, "supplementary.pdf")
        assert audit(tmp_path)["files_present"] == ["supplementary.pdf"]

    def test_an_empty_placeholder_does_not_count_as_held(self, tmp_path):
        """The gate now warns rather than refuses, but a placeholder must still
        read as MISSING, or the warning (and the report's limitation) vanishes."""
        from metascience_agent.supplements import gate
        (self._cites(tmp_path) / "appendix.pdf").write_bytes(b"")
        _declare(tmp_path, "appendix.pdf")
        g = gate(tmp_path)
        assert g["audit"]["missing"] is True
        assert "WARNING" in g["message"]


class TestSuppliedOnTheCommandLine:
    """`--supplement` is checked like any other file, and is actually swept.

    It used to be neither. `cli._supplement_gate` tested `Path.exists()` and
    then overwrote `files_present`/`missing` itself, so `_unusable_because`
    never ran on a supplied path -- a zero-byte `etable.xlsx` passed the gate
    that refuses the SAME file when it is discovered in the directory. And the
    paths stopped at the gate: `analyze_paper` had no parameter for them, so the
    flag bought a proceed for a file the sweep never opened, while a SECOND
    audit computed inside the run still said the supplement was absent and
    printed OVERRIDE_WARNING into the finished report.
    """

    def _cites(self, tmp_path):
        d = tmp_path / "paper"
        d.mkdir()
        (d / "body.md").write_text("See eTable 3 in Supplement 1.")
        return d

    def test_a_supplied_file_outside_the_directory_satisfies_the_gate(self, tmp_path):
        from metascience_agent.supplements import gate
        d = self._cites(tmp_path)
        si = tmp_path / "elsewhere" / "etable.xlsx"
        si.parent.mkdir()
        si.write_bytes(b"PK\x03\x04rest")
        g = gate(d, extra=[si])
        assert g["proceed"] is True
        assert str(si) in g["audit"]["files_present"]

    def test_a_zero_byte_supplied_file_does_not(self, tmp_path):
        """The gate's own override must not defeat the gate's own defence."""
        from metascience_agent.supplements import gate
        d = self._cites(tmp_path)
        si = tmp_path / "etable.xlsx"
        si.write_bytes(b"")
        g = gate(d, extra=[si])
        assert g["audit"]["missing"] is True
        assert g["audit"]["files_present"] == []
        assert "zero bytes" in g["audit"]["files_unusable"][0]["reason"]

    def test_a_supplied_file_that_is_not_its_claimed_format_does_not(self, tmp_path):
        from metascience_agent.supplements import gate
        d = self._cites(tmp_path)
        si = tmp_path / "etable.pdf"
        si.write_bytes(b"<!DOCTYPE html>")
        assert gate(d, extra=[si])["audit"]["missing"] is True

    def test_a_supplied_file_does_not_make_an_unreadable_paper_readable(self, tmp_path):
        """Two different questions. `--supplement` answers "do we hold the
        supplement" and says nothing about whether we can read the ARTICLE it
        belongs to; a scan that was never OCR'd is not fixed by an attachment."""
        from metascience_agent.supplements import gate
        d = tmp_path / "paper"
        d.mkdir()
        si = tmp_path / "etable.xlsx"
        si.write_bytes(b"PK\x03\x04rest")
        g = gate(d, extra=[si])
        assert g["audit"]["text_available"] is False
        assert g["audit"]["missing"] is None
        assert g["proceed"] is False

class TestReportPlacement:
    def _obj(self):
        return {
            "headline": {"severity": "suspicious", "statement": "A finding."},
            "verdict": "unresolved", "confidence": "high", "findings": [],
            "not_checked": [], "limitations": [],
            "coverage_summary": {"stats_found": 1, "stats_checked": 1},
        }

class TestStatcheckUnescaping:
    def test_escaped_comparators_are_unescaped(self):
        """MEASURED: 93.8% of p-value inequalities in the corpus arrive as
        `&lt;`. statcheck looks for a literal `<`, so an escaped comparator is
        invisible to it. Unescaping recovers ~45-52% more statistics."""
        from metascience_agent.tools import r_wrappers

        captured = {}

        def fake_statcheck(text, *a, **k):
            captured["text"] = text
            raise ImportError("stop here")

        import sys
        import types
        mod = types.ModuleType("statcheck.st")
        mod.statcheck = fake_statcheck
        pkg = types.ModuleType("statcheck")
        old = sys.modules.get("statcheck"), sys.modules.get("statcheck.st")
        sys.modules["statcheck"], sys.modules["statcheck.st"] = pkg, mod
        try:
            r_wrappers.python_statcheck_text("t(28) = 2.1, p &lt; .05")
        except Exception:
            pass
        finally:
            for k, v in zip(("statcheck", "statcheck.st"), old):
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
        assert "p < .05" in captured.get("text", "")


class TestGate:
    """A missing supplement WARNS and the paper runs (Dan, 2026-10-18).

    The risk the old refusal guarded is real -- a statistic in an absent
    supplement reads as one the authors never reported -- so the warning names
    what is missing and the run records it as a limitation. Refusing threw away
    every check the main text supports.
    """

    def _paper(self, tmp_path, body="See eTable 3 in Supplement 1."):
        (tmp_path / "body.md").write_text(body)
        return tmp_path

    def test_proceeds_with_a_warning(self, tmp_path):
        from metascience_agent.supplements import gate
        g = gate(self._paper(tmp_path))
        assert g["proceed"] is True
        assert g["message"].startswith("WARNING")

    def test_refusal_names_what_is_missing(self, tmp_path):
        from metascience_agent.supplements import gate
        msg = gate(self._paper(tmp_path))["message"]
        assert "eTable 3" in msg

    def test_warning_says_what_it_means_and_how_to_include_it(self, tmp_path):
        from metascience_agent.supplements import gate
        msg = gate(self._paper(tmp_path))["message"]
        assert "not reported" in msg and "limitation" in msg
        assert "--supplement" in msg

    def test_explicit_override_proceeds(self, tmp_path):
        from metascience_agent.supplements import gate
        g = gate(self._paper(tmp_path), allow_incomplete=True)
        assert g["proceed"] is True
        assert "WITHOUT" in g["message"]  # the old flag changes nothing

    def test_complete_paper_proceeds_silently(self, tmp_path):
        from metascience_agent.supplements import gate
        (tmp_path / "body.md").write_text("A plain paper with no supplement.")
        g = gate(tmp_path)
        assert g["proceed"] is True and g["message"] == ""

    def test_present_supplement_proceeds(self, tmp_path):
        from metascience_agent.supplements import gate
        self._paper(tmp_path)
        (tmp_path / "supplementary.pdf").write_bytes(b"%PDF")
        _declare(tmp_path, "supplementary.pdf")
        assert gate(tmp_path)["proceed"] is True


class TestOverrideWarningWording:
    def test_it_warns_that_findings_may_be_artefacts(self):
        from metascience_agent.supplements import OVERRIDE_WARNING
        assert "not reported" in OVERRIDE_WARNING
        assert "artefact" in OVERRIDE_WARNING

    def test_it_says_the_charge_would_be_unfair_to_authors(self):
        """The failure mode is an accusation against the authors for the
        operator's omission -- the report has to name that."""
        from metascience_agent.supplements import OVERRIDE_WARNING
        assert "unfair" in OVERRIDE_WARNING.lower()

    def test_it_says_the_verdict_is_not_a_verdict_on_the_paper(self):
        from metascience_agent.supplements import OVERRIDE_WARNING
        assert "not a verdict on the paper" in OVERRIDE_WARNING

class TestRetrievalRecordDoesNotSpeakForThePaper:
    """`"status": "none_found"` covers several OPPOSITE facts, and the fetcher
    does not distinguish them. There are FOUR, not two, and the difference
    decides what the operator should do next.

    MEASURED 2026-08-11 on a fresh 15-paper fetch with fetchpdf @11ed2b4 -- the
    papers `supplements.audit()` flags as citing a supplement we do not hold.
    9 obtained a file. Of the 7 `no-bundle` skips behind the other 6:

      * 3 carry Europe PMC's own words, `Article with id PMCnnnn is not open
        access one`. The supplement almost certainly EXISTS. It is a licence
        wall. Retrying is futile; the route is the publisher or a library.
      * 4 are a bare 404 at an address fetchpdf BUILDS from the PMCID
        (`{PMCID}_SupplementaryFiles.zip`) before knowing a bundle exists, and
        still reports as `listed: 1`. That is evidence of ABSENCE, not of our
        failure -- nothing ever claimed the file was there.

    THIS CORRECTS AN EARLIER READING IN THIS FILE, which took `listed: 1` at
    face value and called every one of these "a provider listed a file we then
    failed to fetch". Under the old rule an operator was sent hunting for files
    that do not exist (the speculative case) and told to retry ones that no
    retry can reach (the walled case). Both are our own bookkeeping reported as
    an adverse fact -- the `_page_ink` defect class, pointed at retrieval.
    """

    def _record(self, tmp_path, payload):
        import json
        (tmp_path / "x_supplementary_info.json").write_text(json.dumps(payload))
        return tmp_path

    def test_a_licence_wall_is_not_a_failed_download(self, tmp_path):
        """3 of 7 no-bundle skips. Saying "our retrieval failed" here sends the
        operator to retry something no retry can reach."""
        from metascience_agent.supplements import retrieval_record, retrieval_sentence
        d = self._record(tmp_path, {
            "status": "none_found",
            "providers": [{"name": "europepmc_supplements", "status": "ok", "listed": 1}],
            "files": [],
            "skipped": [{"original_name": "PMC2592987_SupplementaryFiles.zip",
                         "provider": "europepmc_supplements",
                         "url": "https://example.invalid/x", "reason": "no-bundle",
                         "status": None,
                         "detail": "Article with id PMC2592987 is not open access one"}],
        })
        rec = retrieval_record(d)
        assert rec["verdict"] == "not_open_access"
        s = retrieval_sentence(rec)
        assert "licence wall" in s
        assert "retrying will never work" in s.lower()
        assert "not evidence the authors published nothing" in s

    def test_a_constructed_address_returning_404_is_absence_not_our_failure(self, tmp_path):
        """4 of 7. The fetcher names the bundle from the PMCID alone and counts
        it as `listed`; a 404 there says the bundle is not there, not that we
        fumbled a file somebody published."""
        from metascience_agent.supplements import retrieval_record, retrieval_sentence
        d = self._record(tmp_path, {
            "status": "none_found",
            "providers": [{"name": "europepmc_supplements", "status": "ok", "listed": 1}],
            "files": [],
            "skipped": [{"original_name": "PMC1_SupplementaryFiles.zip",
                         "provider": "europepmc_supplements",
                         "url": "https://example.invalid/x", "reason": "no-bundle",
                         "status": 404}],
        })
        rec = retrieval_record(d)
        assert rec["verdict"] == "nothing_published"
        assert len(rec["speculative_addresses"]) == 1
        assert "built from the PMCID alone" in retrieval_sentence(rec)

    def test_a_real_download_failure_is_still_ours(self, tmp_path):
        """The case the old test MEANT to cover, kept: a provider named a
        specific file and the transfer broke."""
        from metascience_agent.supplements import retrieval_record, retrieval_sentence
        d = self._record(tmp_path, {
            "status": "none_found",
            "providers": [{"name": "plos", "status": "ok", "listed": 1}],
            "files": [],
            "skipped": [{"original_name": "pone.0000308.s004.xls", "provider": "plos",
                         "url": "https://example.invalid/s004.xls",
                         "reason": "http-error", "status": 503}],
        })
        rec = retrieval_record(d)
        assert rec["verdict"] == "retrieval_failed"
        s = retrieval_sentence(rec)
        assert "OUR retrieval" in s
        assert "not evidence the authors published none" in s

    def test_nothing_listed_anywhere_is_a_real_negative(self, tmp_path):
        from metascience_agent.supplements import retrieval_record, retrieval_sentence
        d = self._record(tmp_path, {
            "status": "none_found",
            "providers": [{"name": n, "status": "nothing_listed", "listed": 0}
                          for n in ("jats_manifest", "pmc_s3", "zenodo_files")],
            "files": [], "skipped": [],
        })
        rec = retrieval_record(d)
        assert rec["verdict"] == "nothing_published"
        assert "3 providers" in retrieval_sentence(rec)

    def test_no_record_is_a_third_state_not_either_verdict(self, tmp_path):
        from metascience_agent.supplements import retrieval_record
        rec = retrieval_record(tmp_path)
        assert rec["verdict"] == "no_record"
        assert rec["present"] is False

    def test_an_unreadable_record_asserts_nothing(self, tmp_path):
        from metascience_agent.supplements import retrieval_record
        (tmp_path / "x_supplementary_info.json").write_text("{not json")
        assert retrieval_record(tmp_path)["verdict"] == "unreadable_record"

    def test_the_refusal_names_an_action_the_operator_can_take(self, tmp_path):
        """The old refusal told every operator to "supply the files", with no
        hint whether that was even possible. When a provider named a specific
        file and our download broke, the correct action is to RETRY -- and
        passing `--ok-if-supplementary-missing` would throw away a file that exists."""
        from metascience_agent.supplements import gate
        (tmp_path / "body.md").write_text("See Supplementary Table 2.")
        self._record(tmp_path, {
            "status": "none_found",
            "providers": [{"name": "plos", "status": "ok", "listed": 1}],
            "files": [],
            "skipped": [{"original_name": "s004.xls", "provider": "plos",
                         "url": "https://example.invalid/b", "reason": "http-error",
                         "status": 503}],
        })
        g = gate(tmp_path)
        assert g["proceed"] is True
        assert "retry the fetch" in g["message"]
        assert g["retrieval"]["verdict"] == "retrieval_failed"

    def test_the_licence_wall_refusal_does_not_tell_you_to_retry(self, tmp_path):
        """Three of the fresh sample. Retrying a subscription article's bundle
        can only ever fail, and telling an operator to do it wastes their time
        on the one case where a library actually would work."""
        from metascience_agent.supplements import gate
        (tmp_path / "body.md").write_text("See Supplementary Table 2.")
        self._record(tmp_path, {
            "status": "none_found",
            "providers": [{"name": "europepmc_supplements", "status": "ok", "listed": 1}],
            "files": [],
            "skipped": [{"original_name": "PMC1_SupplementaryFiles.zip",
                         "provider": "europepmc_supplements",
                         "url": "https://example.invalid/b", "reason": "no-bundle",
                         "status": None,
                         "detail": "Article with id PMC1 is not open access one"}],
        })
        g = gate(tmp_path)
        assert g["proceed"] is True
        assert g["retrieval"]["verdict"] == "not_open_access"
        assert "retry the fetch" not in g["message"]
        assert "a library" in g["message"]

    def test_the_record_never_decides_whether_the_paper_runs(self, tmp_path):
        """Reading the fetch record improves what the operator is TOLD; it must
        never decide. (Greg's 2026-08-10 refuse-by-default was replaced by Dan's
        warn-and-run, 2026-10-18; the flag no longer changes anything.)"""
        from metascience_agent.supplements import gate
        (tmp_path / "body.md").write_text("See Supplementary Table 2.")
        self._record(tmp_path, {
            "status": "none_found",
            "providers": [{"name": "pmc_s3", "status": "nothing_listed", "listed": 0}],
            "files": [], "skipped": [],
        })
        assert gate(tmp_path)["proceed"] is True
        assert gate(tmp_path, allow_incomplete=True)["proceed"] is True
