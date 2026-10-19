"""The run-level verdict vocabulary, and what earns the top rung.

Greg, 2026-08-11: `trustworthy` is too value-laden, and a paper with some
`suspicious` findings should be allowed the top designation once the word stops
claiming something about the paper as a whole.
"""
import glob
import json
from pathlib import Path

import pytest

from metascience_agent import verdicts as V

REPO = Path(__file__).resolve().parents[1]


def _f(sev, **kw):
    d = {"severity": sev}
    d.update(kw)
    return d


class TestTheVocabularyIsAboutArithmeticNotWorth:
    def test_the_three_words(self):
        assert V.VERDICTS == ("reconciles", "unresolved", "does_not_reconcile")

    def test_none_of_them_judges_the_paper(self):
        """The whole reason for the rename. A verdict this system emits may
        describe what its checks found; it may not describe the work."""
        banned = ("trust", "honest", "fraud", "misconduct", "credib", "reliab",
                  "sound", "good", "bad")
        for v in V.VERDICTS:
            for word in banned:
                assert word not in v, f"{v} contains {word!r}"

    def test_every_verdict_has_a_lay_meaning(self):
        for v in V.VERDICTS:
            assert len(V.MEANING[v]) > 80, v

    def test_the_worst_verdict_still_disclaims_misconduct(self):
        """`does_not_reconcile` is the most consequential string this system
        emits. It has to carry its own caveat, because it will be quoted alone."""
        m = V.MEANING["does_not_reconcile"]
        assert "not a finding of misconduct" in m
        assert "reporting or transcription error" in m


class TestLegacyReportsStillRead:
    """34 archived reports use the old words. A rename that breaks every bundle
    on disk is not a rename, it is a deletion."""

    @pytest.mark.parametrize("old,new", [
        ("trustworthy", "reconciles"),
        ("questionable", "unresolved"),
        ("untrustworthy", "does_not_reconcile"),
        ("UNTRUSTWORTHY", "does_not_reconcile"),
        ("  questionable  ", "unresolved"),
    ])
    def test_the_old_words_map_forward(self, old, new):
        assert V.canonical(old) == new

    def test_a_new_word_maps_to_itself(self):
        for v in V.VERDICTS:
            assert V.canonical(v) == v

    def test_an_unrecognised_word_is_none_not_a_guess(self):
        """A verdict the viewer cannot place is a corruption of the one field a
        reader acts on. Coercing it to one of the three would hide that."""
        assert V.canonical("probably fine") is None
        assert V.canonical(None) is None
        assert V.canonical("") is None

    def test_every_archived_verdict_survives_the_mapping(self):
        seen = set()
        for f in glob.glob(str(REPO / "**/report.json"), recursive=True):
            if "scratchpad" in f:
                continue
            try:
                d = json.load(open(f))
            except Exception:  # noqa: BLE001
                continue
            if isinstance(d, dict) and d.get("verdict"):
                seen.add(d["verdict"])
        if not seen:
            pytest.skip("no archived reports in this checkout")
        unmapped = [v for v in seen if V.canonical(v) is None]
        assert not unmapped, f"archived verdicts nothing can render: {unmapped}"


class TestSuspiciousNoLongerDisqualifies:
    """Greg's decision. Under the old vocabulary the rule was unavoidable -- a
    paper called `trustworthy` while carrying a suspicious finding is a
    contradiction in terms. Under the new one it falls out: our ladder defines
    `suspicious` as a question rather than a determination."""

    def test_a_paper_with_only_questions_reconciles(self):
        r = V.qualifies_as_reconciles([_f("suspicious"), _f("suspicious"),
                                       _f("consistent")])
        assert r["qualifies"] is True
        assert r["open_questions"] == 2

    def test_and_it_is_required_to_say_so(self):
        """The whole risk of relaxing the rule is that the questions stop being
        mentioned. The sentence is computed here rather than left to the
        narrative."""
        r = V.qualifies_as_reconciles([_f("suspicious")])
        assert "1 question" in r["must_state"]
        assert "remains open" in r["must_state"]
        assert "none of them establishes a contradiction" in r["must_state"]

    def test_a_clean_paper_owes_no_such_sentence(self):
        r = V.qualifies_as_reconciles([_f("consistent"), _f("indeterminate")])
        assert r["qualifies"] is True and r["must_state"] == ""

    @pytest.mark.parametrize("sev", ["impossible", "highly_suspicious"])
    def test_a_surviving_determination_still_blocks(self, sev):
        """These are determinations, not questions, and they are exactly what
        the top rung must continue to exclude."""
        r = V.qualifies_as_reconciles([_f(sev), _f("consistent")])
        assert r["qualifies"] is False
        assert "determinations, not questions" in " ".join(r["blockers"])

    def test_claims_lost_to_correction_block(self):
        r = V.qualifies_as_reconciles([_f("suspicious")],
                                      n_claims_lost_to_correction=2)
        assert r["qualifies"] is False
        assert "do not survive correction" in " ".join(r["blockers"])

    def test_an_uncheckable_principal_claim_blocks(self):
        """`reconciles` is a statement about checks that RAN. If the main
        result was never checkable, nothing reconciles it either way."""
        r = V.qualifies_as_reconciles([_f("consistent")],
                                      principal_claim_checkable=False)
        assert r["qualifies"] is False
        assert "not checkable" in " ".join(r["blockers"])

    def test_blockers_accumulate_rather_than_short_circuiting(self):
        """A reader deciding what to fix needs all the reasons, not the first."""
        r = V.qualifies_as_reconciles([_f("impossible")],
                                      n_claims_lost_to_correction=1,
                                      principal_claim_checkable=False)
        assert len(r["blockers"]) == 3

    def test_it_survives_junk_input(self):
        r = V.qualifies_as_reconciles([None, "x", {}, _f(None)])
        assert r["qualifies"] is True and r["open_questions"] == 0


