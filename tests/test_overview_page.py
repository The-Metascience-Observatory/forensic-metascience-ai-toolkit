"""The Overview page described a paper without saying what the paper claims,
and answered three questions with the wrong data.

- `Code / data availability` read `found["all"]`, which UNIONS repositories and
  registrations, so a ClinicalTrials number landed in the row headed "code or
  data" -- claiming a paper shared code when it had shared none.
- `Sample size justified` could never say `yes`. It was a string match on the
  `unchecked` reason text, which is only ever written when something is
  MISSING, so a paper reporting a power analysis scored the same as one
  reporting nothing.
- `Multiplicity corrected` said `no` when zero tests were extracted, charging
  the paper for our blind spot, and gave one verdict for a whole paper when
  correction applies to a FAMILY.
"""
from pathlib import Path

import pytest

from metascience_agent.bundle import (
    _abstract,
    _abstract_text,
    _missing_supplements,
    _paper_facts,
    _power_statement,
    _practice,
)

def _has_paper_files(d) -> bool:
    """Is this a real paper directory, or a leftover shell?

    `d.exists()` is NOT the question. The corpus was removed from the repo on
    2026-08-09, but a working tree can still hold the DIRECTORY -- run outputs
    and `figures/` are written inside it and survive as untracked files -- while
    the PDF and XML the test actually reads are gone. Gating on the directory
    let the test run against an empty shell and FAIL, which is the same
    absence-read-as-presence mistake the toolkit polices in its own checks,
    appearing here in the harness.

    A suite that is red by default on every machine without the corpus teaches
    people to ignore it, so gate on the artefact rather than the folder.
    """
    return d.is_dir() and (any(d.glob("*.pdf")) or any(d.glob("*.xml")))


CORPUS = Path("tests/fixtures/papers/high_value_pdfs_to_run_on")


def _fact(rows, name):
    return next(r for r in rows if r["fact"] == name)


# --------------------------------------------------------------------------
# Availability: repositories are not registrations
# --------------------------------------------------------------------------

BODY_WITH_BOTH = (
    "Data availability: code is at https://github.com/ofekfink/BMI_Prediction "
    "and the trial is registered as NCT03020186."
)


class TestAvailabilitySplit:
    def test_a_registration_does_not_appear_as_shared_code(self, tmp_path):
        rows = _paper_facts(tmp_path, BODY_WITH_BOTH, tmp_path, {}, [], {}, [])
        assert "NCT03020186" not in _fact(rows, "Code / data availability")["value"]

    def test_the_repository_still_does(self, tmp_path):
        rows = _paper_facts(tmp_path, BODY_WITH_BOTH, tmp_path, {}, [], {}, [])
        assert "github.com/ofekfink" in _fact(rows, "Code / data availability")["value"]

    def test_the_registration_appears_in_its_own_row(self, tmp_path):
        rows = _paper_facts(tmp_path, BODY_WITH_BOTH, tmp_path, {}, [], {}, [])
        assert "NCT03020186" in _fact(rows, "Registry ID")["value"]

    def test_the_practice_row_agrees_with_the_metadata_row(self, tmp_path):
        """The two used to disagree, reading different keys off the same scan."""
        from metascience_agent import artefacts

        rows = _practice({}, [], artefacts.find(BODY_WITH_BOTH), {}, [], 0,
                         tmp_path, BODY_WITH_BOTH)
        shared = next(r for r in rows if r["practice"] == "Data or code shared")
        assert "NCT03020186" not in shared["detail"]

    def test_a_prereg_document_gets_its_own_row(self, tmp_path):
        body = "The plan is registered at https://osf.io/ab3cd and NCT03020186."
        rows = _paper_facts(tmp_path, body, tmp_path, {}, [], {}, [])
        assert "osf.io/ab3cd" in _fact(rows, "Preregistration document")["value"]
        assert "NCT03020186" not in _fact(rows, "Preregistration document")["value"]


# --------------------------------------------------------------------------
# Sample size
# --------------------------------------------------------------------------

class TestSampleSizeJustified:
    def test_a_reported_power_analysis_reads_yes(self, tmp_path):
        body = ("Statistical analysis. Power analyses were designed to detect "
                "a 7-percentage-point difference between the two study arms.")
        rows = _practice({}, [], {}, {}, [], 0, tmp_path, body)
        row = next(r for r in rows if r["practice"] == "Sample size justified")
        assert row["status"] == "yes"
        assert "Power analyses" in row["detail"], "quote the sentence, do not assert"

    def test_a_negated_statement_does_not_read_yes(self):
        """"we were NOT powered to detect" is the opposite claim, and it lives
        in the limitations section of real papers."""
        assert _power_statement(
            "Finally, we were not powered to detect differences in secondary "
            "outcomes between the two groups.") is None

    def test_powerful_and_empowerpharm_do_not_match(self):
        assert _power_statement("novel in finding powerful interactions") is None
        assert _power_statement("consultancy for EmpowerPharm and Janssen") is None

    #: These used `{"missing": [{"name": ...}]}`, a shape `supplements.audit`
    #: NEVER produces -- it returns `missing` three-valued: True (declared and
    #: absent), False (nothing missing), None (paper unreadable, so the
    #: question went unanswered). So the tests passed against a fiction while
    #: every real call returned "" and the accusation branch fired
    #: unconditionally. The first of them contradicted its own name: it passed
    #: `supp={}`, which means the audit did not run, and asserted that reads as
    #: "the material was complete".
    _STATES_NONE = [{"reason": "no power analysis reported; the paper states none"}]

    def test_absence_reads_no_only_when_the_material_was_complete(self, tmp_path):
        """`missing: False` is the ONLY state that licenses "no"."""
        rows = _practice({}, self._STATES_NONE, {}, {"missing": False},
                         [], 0, tmp_path, "")
        assert next(r for r in rows
                    if r["practice"] == "Sample size justified")["status"] == "no"

    def test_a_missing_supplement_turns_that_no_into_unknown(self, tmp_path):
        supp = {"missing": True, "styles": {"Appendix style": ["Appendix S1"]}}
        rows = _practice({}, self._STATES_NONE, {}, supp, [], 0, tmp_path, "")
        row = next(r for r in rows if r["practice"] == "Sample size justified")
        assert row["status"] == "unknown"
        assert "Appendix S1" in row["detail"]

    def test_an_unreadable_paper_is_unknown_not_no(self, tmp_path):
        rows = _practice({}, self._STATES_NONE, {}, {"missing": None},
                         [], 0, tmp_path, "")
        row = next(r for r in rows if r["practice"] == "Sample size justified")
        assert row["status"] == "unknown"
        assert "could not be read" in row["detail"]

    def test_a_crashed_audit_is_unknown_not_no(self, tmp_path):
        """The caller wraps the audit in `except Exception: supp = {}`, so an
        empty dict means OUR failure, and it must not be charged to the paper.
        """
        rows = _practice({}, self._STATES_NONE, {}, {}, [], 0, tmp_path, "")
        row = next(r for r in rows if r["practice"] == "Sample size justified")
        assert row["status"] == "unknown"
        assert "could not be run" in row["detail"]

    def test_the_absence_is_never_blamed_on_the_paper_when_we_cannot_see(self, tmp_path):
        """The sentence this printed: "every declared supplement was supplied,
        so the absence is the paper's" -- for a paper whose supplement we never
        received, and for one we could not open."""
        for supp in ({}, {"missing": None},
                     {"missing": True, "styles": {"S": ["Table S1"]}}):
            rows = _practice({}, self._STATES_NONE, {}, supp, [], 0, tmp_path, "")
            detail = next(r for r in rows
                          if r["practice"] == "Sample size justified")["detail"]
            assert "the absence is the paper's" not in detail, supp

    def test_missing_supplements_speaks_the_audit_s_own_language(self):
        assert _missing_supplements({"missing": False}) == ""
        assert "could not be run" in _missing_supplements({})
        assert "could not be read" in _missing_supplements({"missing": None})
        named = _missing_supplements(
            {"missing": True, "styles": {"Appendix style": ["Appendix S1"]}})
        assert "Appendix S1" in named and "not supplied" in named


# --------------------------------------------------------------------------
# Multiplicity
# --------------------------------------------------------------------------

class TestMultiplicity:
    def test_no_tests_extracted_is_unknown_not_no(self, tmp_path):
        """`no` here charges the paper for OUR blind spot."""
        rows = _practice({"tests": []}, [], {}, {}, [], 0, tmp_path, "")
        row = next(r for r in rows if r["practice"] == "Multiplicity corrected")
        assert row["status"] == "unknown"

    def test_the_verdict_is_reported_per_family(self, tmp_path):
        anatomy = {"tests": [
            {"hypothesis_id": "h1", "correction_applied": "bonferroni"},
            {"hypothesis_id": "h1", "correction_applied": "bonferroni"},
            {"hypothesis_id": "h2", "correction_applied": "none"},
        ]}
        rows = _practice(anatomy, [], {}, {}, [], 0, tmp_path, "")
        row = next(r for r in rows if r["practice"] == "Multiplicity corrected")
        assert "h1 (2/2)" in row["detail"]
        assert "h2 (0/1)" in row["detail"]

    def test_ungrouped_tests_say_so_rather_than_implying_a_judgement(self, tmp_path):
        anatomy = {"tests": [{"correction_applied": "none"}]}
        rows = _practice(anatomy, [], {}, {}, [], 0, tmp_path, "")
        row = next(r for r in rows if r["practice"] == "Multiplicity corrected")
        assert "not grouped into families" in row["detail"]


# --------------------------------------------------------------------------
# Supplements: two questions, not one
# --------------------------------------------------------------------------

class TestSupplementRows:
    def test_supplied_and_cited_are_separate_rows(self, tmp_path):
        rows = _practice({}, [], {}, {"files_present": True}, [], 0, tmp_path, "")
        names = [r["practice"] for r in rows]
        assert "Supplementary material cited by the paper" in names
        assert "Supplementary material supplied to this review" in names

    def test_a_missing_supplement_is_not_charged_to_the_paper(self, tmp_path):
        rows = _practice({}, [], {}, {"missing": ["Appendix S1"]}, [], 0, tmp_path, "")
        supplied = next(r for r in rows
                        if r["practice"] == "Supplementary material supplied to this review")
        assert supplied["status"] == "no"
        assert "not of the publication" in supplied["detail"]


# --------------------------------------------------------------------------
# Abstract
# --------------------------------------------------------------------------

class TestAbstract:
    def test_the_abstract_heading_is_not_welded_onto_the_first_sentence(self):
        import xml.etree.ElementTree as ET

        el = ET.fromstring(
            "<abstract><title>Abstract</title><p>Obesity is associated with "
            "negative effects on the brain.</p></abstract>")
        assert _abstract_text(el).startswith("Obesity is associated")

    def test_a_structured_abstract_keeps_its_headings_apart(self):
        import xml.etree.ElementTree as ET

        el = ET.fromstring(
            "<abstract><sec><title>Objectives</title><p>To develop a score.</p>"
            "</sec><sec><title>Methods</title><p>We enrolled 200 adults.</p>"
            "</sec></abstract>")
        got = _abstract_text(el)
        assert got == "Objectives: To develop a score. Methods: We enrolled 200 adults."

    def test_a_bare_heading_is_not_an_abstract(self, tmp_path):
        (tmp_path / "abstract.md").write_text("# Abstract\n")
        assert _abstract(tmp_path, tmp_path) == ""

    @pytest.mark.skipif(not _has_paper_files(CORPUS), reason="corpus not present")
    @pytest.mark.parametrize("paper", [
        "10.1002--hbm.26595", "10.1002--mpr.70006", "10.1002--eat.24415"])
    def test_the_real_abstracts_come_back_as_prose(self, paper):
        got = _abstract(CORPUS / paper, CORPUS / paper)
        assert len(got) > 200
        assert not got.lower().startswith("abstract")


# --------------------------------------------------------------------------
# What each check returned
# --------------------------------------------------------------------------

from metascience_agent.bundle import _check_table, _sankey  # noqa: E402

CALLS = [
    {"tool": "grim_sweep", "validated": True},
    {"tool": "grim_sweep", "validated": True},
    {"tool": "statcheck", "validated": True},
    {"tool": "statcheck", "validated": False},   # not a forensic surface
]
SWEEP = [
    {"id": "f1", "technique": "grim", "severity": "suspicious"},
    {"id": "f2", "technique": "grim", "severity": "consistent"},
    {"id": "f3", "technique": "statcheck", "severity": "impossible"},
]
EDITORIAL = [{"stage1_finding_ids": ["f1", "f3"]}]


class TestCheckTable:
    def test_a_check_that_ran_and_found_nothing_still_gets_a_row(self):
        rows = {r["check"]: r for r in _check_table(
            [{"tool": "debit_check", "validated": True}], [], [])}
        assert rows["debit_check"]["calls"] == 1
        assert rows["debit_check"]["findings"] == 0

    def test_unvalidated_calls_are_not_counted(self):
        rows = {r["check"]: r for r in _check_table(CALLS, SWEEP, EDITORIAL)}
        assert rows["statcheck"]["calls"] == 1, "one of the two was unvalidated"

    def test_the_kept_column_says_what_reached_the_report(self):
        rows = {r["check"]: r for r in _check_table(CALLS, SWEEP, EDITORIAL)}
        assert rows["grim_sweep"]["findings"] == 2
        assert rows["grim_sweep"]["kept"] == 1
        assert rows["statcheck"]["kept"] == 1

    def test_a_finding_with_no_matching_call_is_hand_computed(self):
        rows = {r["check"]: r for r in _check_table(
            [], [{"id": "x", "technique": "grim", "severity": "suspicious"}], [])}
        assert rows["hand-computed"]["findings"] == 1


class TestSankeyThirdStage:
    def test_the_flow_is_conserved_through_the_middle_column(self):
        """A severity node receives its findings and passes them on. The old
        renderer summed both directions for a node's height, which is twice its
        real size once a third column exists."""
        s = _sankey(CALLS, SWEEP, EDITORIAL)
        mids = [n["id"] for n in s["nodes"] if n["column"] == 1]
        for node in mids:
            if node == "no finding":
                continue
            into = sum(l["value"] for l in s["links"] if l["target"] == node)
            out = sum(l["value"] for l in s["links"] if l["source"] == node)
            assert into == out, node

    def test_no_finding_terminates_rather_than_flowing_onward(self):
        s = _sankey(CALLS, SWEEP, EDITORIAL)
        assert not [l for l in s["links"] if l["source"] == "no finding"]

    def test_without_an_editorial_stage_there_is_no_third_column(self):
        s = _sankey(CALLS, SWEEP)
        assert max(n["column"] for n in s["nodes"]) == 1

    def test_dropped_findings_are_visible_as_not_reported(self):
        s = _sankey(CALLS, SWEEP, EDITORIAL)
        dropped = sum(l["value"] for l in s["links"] if l["target"] == "not reported")
        assert dropped == 1, "f2 was found and never reported"
