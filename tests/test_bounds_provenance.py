"""Evidence has to be about the thing it licenses.

`Variable.bounds_are_stated()` is what lets GRIM, GRIMMER and SPRITE reach
`impossible` -- the top of the severity ladder, the most damning verdict this
toolkit can issue -- instead of capping at `suspicious`. It asked two questions:
is the model's confidence `high`, and did the pipeline find the model's
`provenance_quote` in the paper.

Both check that the quote is REAL. Neither checked that it is real ABOUT THIS.
And `findings.schema.json` specifies `provenance_quote` as the "verbatim
sentence establishing this TYPING" -- what kind of variable it is -- while
`lower_bound` and `upper_bound` carry no description and no evidence
requirement at all. So a verified sentence about a variable's type was
unlocking `impossible` for a scale range it never mentioned.

MEASURED over the archive. Variables passing the old two-condition test AND
declaring bounds: 26. Quotes that actually contain the declared bounds: 16. Ten
of twenty-six (38%) held an unsound licence. The clearest one:

    lower_bound 1, upper_bound 5, confidence high, verdict verbatim
    provenance_quote: "(2) difficulties resisting eating (M = 2.79, SD = 1.42)"

A real sentence, really in the paper, reporting a mean and an SD, offered as
evidence that the scale runs 1 to 5. It establishes nothing whatever about
bounds.

WHY NOT A SEPARATE `bounds_quote` FIELD. That is the better long-run shape and
it is a schema change, a prompt change and a paid run to populate. This is sound
today at no cost. Coverage falls 26 -> 16 and falls in the correct direction:
every one of the ten removed was licensing the top of the ladder on evidence
that did not support it.
"""
import glob
import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.anatomy import Variable

REPO = Path(__file__).resolve().parents[1]


def _var(quote, lo=1, hi=5, confidence="high", verdict="verbatim"):
    v = Variable(id="v1", name="Mood", lower_bound=lo, upper_bound=hi,
                 provenance_quote=quote, confidence=confidence)
    v.provenance_verdict = verdict
    return v


class TestTheFirstTwoConditionsStillHold:
    """The tightening ADDS a condition; it must not weaken the two that caught
    a model certifying its own invented 1-7 scale."""

    def test_low_confidence_is_still_refused(self):
        assert not _var("scored 1 to 5", confidence="medium").bounds_are_stated()

    def test_an_unverified_quote_is_still_refused(self):
        assert not _var("scored 1 to 5", verdict="unverified").bounds_are_stated()

    def test_a_stitched_quote_is_still_refused(self):
        """`stitched` means WE assembled the sentence and it is not in the
        paper, so it cannot evidence that the authors stated anything."""
        assert not _var("scored 1 to 5", verdict="stitched").bounds_are_stated()

    def test_no_verdict_at_all_is_refused(self):
        assert not _var("scored 1 to 5", verdict=None).bounds_are_stated()

    def test_a_quote_naming_both_bounds_passes_everything(self):
        assert _var("responses ranged from 1 = Not at all to 5 = Extremely"
                    ).bounds_are_stated()


class TestTheQuoteMustMentionTheBounds:
    def test_a_typing_quote_does_not_license_a_range(self):
        """THE MEASURED INSTANCE. Real sentence, real in the paper, and silent
        about the scale."""
        assert not _var("(2) difficulties resisting eating (M = 2.79, SD = 1.42)"
                        ).bounds_are_stated()

    def test_mentioning_only_one_bound_is_not_enough(self):
        """A quote giving the floor says nothing about the ceiling, and the
        ceiling is what an SD-range or SPRITE check leans on."""
        assert not _var("items were scored from 1 upward").bounds_are_stated()

    def test_decimal_forms_of_the_same_number_count(self):
        """Routed through the quote verifier's own matcher, so `5`, `5.0` and
        `5.00` are one number here exactly as they are there."""
        assert _var("anchored at 1.0 and 5.0").bounds_are_stated()

    def test_a_variable_with_no_bounds_is_vacuously_fine(self):
        """`bound_source` only matters to a check handed a range. A variable
        with no range never reaches one, and refusing here would cap checks
        that never used bounds in the first place."""
        v = _var("Age in years at intake", lo=None, hi=None)
        assert v.bounds_are_stated()

    def test_an_empty_quote_cannot_evidence_bounds(self):
        assert not _var("", lo=1, hi=5).bounds_are_stated()

    def test_a_missing_matcher_closes_the_gate_rather_than_opening_it(self, monkeypatch):
        """Fail-safe direction. An import failure must not silently restore the
        permissive behaviour this test file exists to remove."""
        import forensic_metascience_ai_toolkit.quotes as q
        monkeypatch.delattr(q, "_number_forms", raising=False)
        assert not _var("responses ranged from 1 to 5").bounds_are_stated()


class TestTheArchiveReplayed:
    """A ratchet on soundness: the count may rise as the model learns to quote
    the range, but no variable may pass on a quote lacking its bounds."""

    @pytest.fixture(scope="class")
    def variables(self):
        out = []
        for f in sorted(glob.glob(str(
                REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on/*/forensic_review*/findings.json"))):
            try:
                fj = json.loads(Path(f).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out += [d for d in ((fj.get("anatomy") or {}).get("variables") or [])
                    if isinstance(d, dict)]
        if not out:
            pytest.skip("no archived anatomy in this checkout")
        return out

    def _built(self, d):
        v = Variable(id=d.get("id", "v"), name=d.get("name", "v"),
                     lower_bound=d.get("lower_bound"),
                     upper_bound=d.get("upper_bound"),
                     provenance_quote=d.get("provenance_quote"),
                     confidence=d.get("confidence", "low"))
        v.provenance_verdict = d.get("provenance_verdict")
        return v

    def test_the_gate_is_not_simply_shut(self, variables):
        """A gate that always says no is indistinguishable from a broken one --
        `_verify_variable_quote`'s own words. Some variables must still pass."""
        passing = [d for d in variables if self._built(d).bounds_are_stated()
                   and d.get("lower_bound") is not None]
        assert len(passing) >= 10, (
            f"only {len(passing)} archived variables still license stated "
            "bounds; if this fell to zero the tightening went too far")

    def test_nothing_passes_without_its_bounds_in_the_quote(self, variables):
        from forensic_metascience_ai_toolkit.quotes import _number_forms, normalise
        for d in variables:
            v = self._built(d)
            if not (v.bounds_are_stated() and v.lower_bound is not None):
                continue
            hay = normalise(v.provenance_quote or "")
            for bound in (v.lower_bound, v.upper_bound):
                if bound is None:
                    continue
                assert any(f and f in hay for f in _number_forms(str(bound))), (
                    f"`{v.name}` licenses bounds ({v.lower_bound}, "
                    f"{v.upper_bound}) on a quote that does not contain them")

    def test_the_tightening_removed_the_measured_ten(self, variables):
        old = [d for d in variables
               if d.get("confidence") == "high"
               and d.get("provenance_verdict") in ("verbatim", "elided")
               and d.get("lower_bound") is not None
               and d.get("upper_bound") is not None]
        new = [d for d in old if self._built(d).bounds_are_stated()]
        assert len(old) - len(new) >= 5, (
            f"{len(old)} qualified before, {len(new)} after -- the measured "
            "reduction was 26 -> 16, and a much smaller one means the quote "
            "check is not actually being applied")
