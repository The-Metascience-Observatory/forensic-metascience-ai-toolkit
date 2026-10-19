"""`absence_of_evidence` must not guess where the null is.

The null is 1 for a ratio measure (OR/RR/HR/IRR) and 0 for a difference.
`is_ratio_measure(None)` is False, so an omitted `measure` used to silently
assume 0.0 -- and every ratio confidence interval has positive bounds. The
odds-ratio interval [0.85, 1.42], a textbook null result, was reported as
"excludes the null" with severity `consistent`.

That is the worst shape a wrong answer can take here: a GREEN verdict, on the
most common result format in the corpus (353 estimate-with-CI triples,
dominated by ratios), from a check the reader believes ran.
"""
import pytest

from metascience_agent.registry import BY_NAME
from metascience_agent.tools.estimates import absence_of_evidence


class TestRefusesWithoutTheNull:
    def test_the_reported_inversion(self):
        """[0.85, 1.42] spans 1. It must never come back `consistent`."""
        r = absence_of_evidence(ci_low=0.85, ci_high=1.42)
        assert r["severity"] == "indeterminate"
        assert r.get("measure_required") is True

    def test_it_says_what_is_missing(self):
        r = absence_of_evidence(ci_low=0.85, ci_high=1.42)
        assert "measure" in r["explanation"]

    def test_with_measure_it_judges(self):
        r = absence_of_evidence(ci_low=0.85, ci_high=1.42, measure="OR")
        assert r["includes_null"] is True
        assert r["severity"] == "indeterminate"     # null included, no SESOI stated

    def test_null_value_is_an_equally_good_answer(self):
        """A caller who knows the null exactly should not need `measure`."""
        r = absence_of_evidence(ci_low=0.85, ci_high=1.42, null_value=1.0)
        assert r.get("measure_required") is not True
        assert r["includes_null"] is True


class TestStillJudgesWhenItCan:
    def test_a_negative_bound_settles_it(self):
        """Ratio measures are strictly positive, so this cannot be a ratio."""
        r = absence_of_evidence(ci_low=-0.2, ci_high=0.5)
        assert r.get("measure_required") is not True
        assert r["includes_null"] is True

    def test_a_ratio_excluding_the_null_is_still_consistent(self):
        """The fix must not be "always refuse"."""
        r = absence_of_evidence(ci_low=1.10, ci_high=1.42, measure="OR")
        assert r["severity"] == "consistent"
        assert r["includes_null"] is False

    def test_reversed_bounds_still_caught_first(self):
        r = absence_of_evidence(ci_low=2.0, ci_high=1.0)
        assert r["severity"] == "indeterminate"
        assert "reversed" in r["explanation"].lower()


class TestRegistryMarksItAGuard:
    def test_measure_is_a_guard(self):
        """Guard status is what makes the audit count a defaulted `measure`."""
        assert "measure" in BY_NAME["absence_of_evidence"].guards()

    def test_description_tells_the_model_to_pass_it(self):
        d = BY_NAME["absence_of_evidence"].description
        assert "ALWAYS PASS `measure`" in d

    def test_the_registry_declares_it(self):
        assert "measure" in {p.name for p in BY_NAME["absence_of_evidence"].params}
