"""Code decides what needs a second look; the model decides whether it survives.

Greg, 2026-08-13: a post-hoc reviewer using this same model reliably catches
these, so the pipeline's own agents should be able to. He is right, and the
difference is not capability -- a reviewer gets a SECOND PASS over work already
written, and stage 2 gets one. This supplies the trigger for that pass.

The split is load-bearing. "Did a tool compute this", "is the quote in the
paper", "did the paper state that bound" are FACTS, and a model asked to check
itself is the same reasoner that made the claim. Whether the finding survives
needs judgement, and stays with the model.

THESE TESTS WERE WRONG WHEN FIRST WRITTEN, in both of the ways this repository
keeps getting wrong, and the corrections are kept visible below rather than
quietly rewritten.

  1. They asserted a finding is `model_computed` because its LABEL said
     `manual`. MEASURED 2026-08-13 over 626 deduplicated archived findings: 159
     carry that label and 56 of them (35.2%) contain no arithmetic at all. The
     label was doing three unrelated jobs; `computation` now splits it, and the
     legacy value is decided by contents.
  2. The fixture set the tool in `inputs.tool`. Production sets `technique` on
     100% of those 626 findings and `inputs.tool` on 5.4% -- so the suite was
     green against a shape the pipeline almost never produces, which is the
     "tested against a shape production never produces" failure by name.
"""

import pytest

from forensic_metascience_ai_toolkit import secondlook as S


def _f(fid, severity, technique="grim_check", quote="verbatim", bound="stated",
       computed=None, **kw):
    """A finding shaped the way the pipeline actually emits one."""
    return {"id": fid, "severity": severity, "location": "T1",
            "technique": technique, "computed": computed,
            "quote_verified": quote,
            "inputs": {"bound_source": bound}, **kw}


class TestOnlyAccusationsAreMarked:
    """An `indeterminate` or `consistent` finding accuses nobody, so a weak
    quote on one costs a reader nothing. Marking them is how a worklist becomes
    noise its reader learns to skip."""

    @pytest.mark.parametrize("sev", ["consistent", "indeterminate"])
    def test_a_non_accusation_is_never_marked(self, sev):
        assert S.markers(_f("a", sev, technique="tool_existed_unused",
                            quote="unverified")) == []

    @pytest.mark.parametrize("sev", ["suspicious", "highly_suspicious", "impossible"])
    def test_every_accusatory_band_is_eligible(self, sev):
        assert S.markers(_f("a", sev, technique="tool_existed_unused")) == \
            ["model_computed"]


class TestEachMarkerIsDecidable:
    def test_model_computed_fires_on_arithmetic_no_tool_guarded(self):
        for tech in ("tool_existed_unused", "no_tool_exists"):
            assert "model_computed" in S.markers(_f("a", "suspicious", technique=tech)), tech
        assert "model_computed" not in S.markers(
            _f("a", "suspicious", technique="grim_check"))

    def test_a_finding_with_no_arithmetic_is_not_accused_of_doing_any(self):
        """THE ORIGINAL BUG. 35.2% of the archive's `manual` findings are
        warrants, not computations -- an asterisk against the wrong p, a figure
        legend naming the wrong protein -- and the label alone cannot tell them
        apart from arithmetic."""
        assert "model_computed" not in S.markers(
            _f("a", "suspicious", technique="not_computational"))
        for empty in (None, {}, ""):
            assert "model_computed" not in S.markers(
                _f("a", "suspicious", technique="manual", computed=empty)), empty

    def test_the_legacy_label_still_fires_when_its_contents_show_arithmetic(self):
        """A guard that stops guarding the moment the vocabulary changes is
        indistinguishable from one that found nothing (LESSONS.md #4). `manual`
        remains legal for archived runs, so it is decided by contents."""
        assert "model_computed" in S.markers(
            _f("a", "suspicious", technique="manual",
               computed={"ratio": 1.56, "n": 40}))

    def test_quote_not_located(self):
        assert "quote_not_located" in S.markers(_f("a", "suspicious", quote="unverified"))
        assert "quote_not_located" in S.markers(_f("a", "suspicious", quote=""))
        for good in ("verbatim", "stitched", "elided"):
            assert "quote_not_located" not in S.markers(_f("a", "suspicious", quote=good))

    def test_assumed_bound(self):
        assert "assumed_bound" in S.markers(_f("a", "impossible", bound="assumed"))
        assert "assumed_bound" not in S.markers(_f("a", "impossible", bound="stated"))

    def test_a_clean_accusation_carries_nothing(self):
        assert S.markers(_f("a", "impossible")) == []


class TestItIsAWorklistNotAVerdict:
    """A marker that silently downgraded a true finding would be as damaging as
    the false accusation it aims to prevent."""

    def test_no_severity_is_changed(self):
        f = _f("a", "impossible", technique="tool_existed_unused")
        before = f["severity"]
        S.worklist([f])
        assert f["severity"] == before
        assert "verdict" not in S.worklist([f])

    def test_every_marker_says_what_would_settle_it(self):
        w = S.worklist([_f("a", "suspicious", technique="tool_existed_unused",
                           quote="unverified")])
        item = w["items"][0]
        assert len(item["what_to_do"]) == len(item["markers"])
        assert all(len(s) > 60 for s in item["what_to_do"])

    def test_the_note_says_it_is_not_a_verdict(self):
        w = S.worklist([_f("a", "suspicious", technique="tool_existed_unused")])
        assert "not a verdict" in w["note"]


class TestTheEmptyAndAbsentCasesAreHonest:
    def test_clean_accusations_say_so_rather_than_going_silent(self):
        w = S.worklist([_f("a", "impossible"), _f("b", "suspicious")])
        assert w["n_flagged"] == 0 and w["n_accusatory"] == 2
        assert "Nothing is flagged" in w["note"]

    def test_no_accusations_at_all_is_distinguished(self):
        w = S.worklist([_f("a", "consistent")])
        assert w["n_accusatory"] == 0
        assert "nothing to re-check" in w["note"]

    def test_junk_input_does_not_raise(self):
        assert S.markers(None) == [] and S.markers("x") == []
        assert S.worklist([None, "x"])["n_flagged"] == 0


