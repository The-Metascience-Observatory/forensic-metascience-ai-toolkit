"""`preregistration` must not claim a paper is preregistered when it says it is not.

TWO DEFECTS, FOUND 2026-08-18 while tracing #177 (extract_text returns a bare
string, so callers cannot tell an unreadable file from an empty paper).
`agent.py` feeds this function `paper_text(paper_dir)`, which returns "" for a
scan with no OCR layer -- 2 of the first 41 documents in the Zotero sweep.

1. AN EMPTY STRING WAS REPORTED AS `not_mentioned`. Every branch reads `text`,
   so on "" they all come back negative and the status lands on a claim ABOUT
   THE PAPER produced by our failure to read it. The prose `note` did hedge, but
   `status` is what a renderer branches on, and a hedge in prose beside an
   unqualified enum is how the unqualified one wins. Same shape as
   `supplements.audit`'s three-valued `missing`.

2. AN EXPLICIT DENIAL WAS REPORTED AS `preregistered`, which is the worse of the
   two. `_PREREG_TERMS` matches `pre-?regist\\w+`, which fires on the word inside
   a NEGATED sentence -- and a paper can only deny preregistration by using the
   word. Because `terms` was tested before `explicit_none`, the
   `explicitly_not_preregistered` branch was unreachable in exactly the case it
   names. MEASURED: all four of these returned `preregistered`.

       "No preregistration was performed for this study."
       "This study was not preregistered."
       "We did not preregister our hypotheses."
       "The study was preregistered."            (the only correct one)

   The direction is worth naming. This made a paper look BETTER than it is, so
   it is a false EXONERATION rather than a false accusation -- the cardinal rule
   is not engaged. It is still a statement about a paper that contradicts what
   the paper says, in a document whose entire value is that its statements can
   be checked against the source.
"""
import pytest

from metascience_agent.artefacts import preregistration


class TestNoTextIsUnknown:
    def test_empty_is_not_not_mentioned(self):
        assert preregistration("")["status"] == "unknown_no_text"

    def test_whitespace_only_is_also_unknown(self):
        assert preregistration("   \n\t ")["status"] == "unknown_no_text"

    def test_the_note_says_it_is_about_the_extraction(self):
        note = preregistration("")["note"]
        assert "UNKNOWN" in note
        assert "not a finding" in note

    def test_no_identifiers_are_invented(self):
        r = preregistration("")
        assert r["identifiers"] == {} and r["deviation_passages"] == []


class TestAnExplicitDenialWins:
    @pytest.mark.parametrize("text", [
        "No preregistration was performed for this study.",
        "This study was not preregistered.",
        "We did not preregister our hypotheses.",
        "The analyses have not been preregistered.",
        "The study was conducted without preregistration.",
    ])
    def test_denials_are_recorded_as_denials(self, text):
        assert preregistration(text)["status"] == "explicitly_not_preregistered"


class TestAClaimWithoutAnIdentifierIsNotAVerdict:
    """CHANGED 2026-08-18, and the change is the point.

    These three cases asserted `preregistered` earlier the same night, when the
    bare-keyword branch still issued that verdict. Greg then asked why a regex
    was making the judgement at all, and the answer is that it cannot: the same
    pattern fires on "The study was preregistered", on "Future work should be
    preregistered", on a citation of someone else's registered report, and on
    "Neither study was preregistered". It has no way to tell them apart.

    So a keyword with no identifier behind it now reports
    `mentioned_unverified` and carries the passage, and the metadata row reads
    "mentioned, but not verified -- see the passage" rather than "yes".

    THE COST, STATED: a genuinely preregistered study that says so without
    printing an identifier is no longer recorded as preregistered. That is a
    real coverage loss. It is taken deliberately, in the conservative
    direction, because the model already makes this judgement properly per
    hypothesis with a QUOTED registration (modules/tools_agent/prompt.md), and a
    second worse answer rendered as flat metadata was contradicting it -- on 2
    of 22 archived runs, measured.
    """

    @pytest.mark.parametrize("text", [
        "The study was preregistered.",
        "We preregistered the primary outcome.",
        "This is a registered report.",
    ])
    def test_a_bare_claim_is_reported_as_unverified(self, text):
        assert preregistration(text)["status"] == "mentioned_unverified"

    @pytest.mark.parametrize("text", [
        "This trial was registered at ClinicalTrials.gov (NCT02737566).",
        "This study was preregistered on OSF (osf.io/ab12c).",
    ])
    def test_an_identifier_still_yields_the_verdict(self, text):
        """Hard evidence is still evidence. What changed is the branch that had
        none."""
        assert preregistration(text)["status"] == "preregistered"

    def test_an_identifier_belonging_to_another_study_does_not_count(self):
        """VERIFIED before the fix: this returned `preregistered` on somebody
        else's registration."""
        r = preregistration(
            "The ongoing confirmatory trial (NCT02737566) will address this "
            "question; the present secondary analysis was exploratory.")
        assert r["status"] == "mentioned_unverified"


class TestADenialOfDeparturesIsNotADeparture:
    def test_no_deviations_produces_no_deviation_passage(self):
        """VERIFIED before the fix: "There were no deviations from the
        registered protocol." produced one deviation passage, recording a paper
        that followed its protocol as discussing departures from it."""
        r = preregistration(
            "This study was preregistered (osf.io/ab12c). There were no "
            "deviations from the registered protocol.")
        assert r["deviation_passages"] == []

    def test_a_real_departure_is_still_recorded(self):
        r = preregistration(
            "This study was preregistered (osf.io/ab12c). We deviated from the "
            "registered protocol by adding a covariate.")
        assert len(r["deviation_passages"]) >= 1

    def test_a_hard_identifier_outranks_a_partial_denial(self):
        """Deliberate. A paper carrying an OSF registration that also says
        "Study 2 was not preregistered" is genuinely mixed, and the identifier
        is the falsifiable half."""
        r = preregistration(
            "Preregistered at osf.io/ab12c; Study 2 was not preregistered.")
        assert r["status"] == "preregistered"


class TestSilenceIsStillSilence:
    def test_a_paper_that_never_mentions_it(self):
        r = preregistration("We measured reaction time in 40 adults.")
        assert r["status"] == "not_mentioned"

    def test_not_mentioned_and_unknown_are_different_states(self):
        """The whole point of defect 1: these must never collapse."""
        silent = preregistration("We measured reaction time in 40 adults.")
        unread = preregistration("")
        assert silent["status"] != unread["status"]
