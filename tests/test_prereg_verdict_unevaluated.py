"""A pre-registered condition that could not be evaluated is not a passed one.

`corpus.verdict` exists, in its own docstring's words, so "that a bad result
cannot be re-narrated as a mixed one afterwards". It evaluates the
pre-registered failure conditions mechanically, and its all-clear line is the
most consequential sentence this evaluation produces.

MEASURED 2026-08-18. `cluster_bootstrap_ci` returns (nan, nan) when there are
fewer than two CASES to resample -- correct, since one cluster cannot yield an
interval. The E1 check is guarded with `not math.isnan(...)` so it does not
crash; it simply does not fire. Nothing else appended anything, and the function
fell through to:

    "No pre-registered failure condition triggered."

on an endpoint reporting k=3 of n=10 -- a 30% observed false-accusation rate,
half again over the pre-registered 20% ceiling. The RATE was measurable; only
the BOUND was not. The guard turned "we could not test the ceiling" into "the
ceiling was not breached", which is precisely the re-narration this function was
written to make impossible, performed by the function itself.

E4 had the same shape: `if cov is not None and cov < 0.25` skips silently when
coverage is unavailable.

The fix is the same three-valued discipline used by `supplements.audit`'s
`missing`, the PubPeer record's `n_comments`, and `tripwire`'s `not_measured`: an
absent answer gets its own state and is never spelled like a negative one.
"""
import math

import pytest

from metascience_agent.evaluation.corpus import Endpoint, verdict

CLEAN_REST = {"E3_canary_hits": [], "E4_coverage": {"rate": 0.9}}


def _v(e1, **over):
    return verdict({"E1": e1, **CLEAN_REST, **over})


class TestAnUnmeasurableBoundIsNotAPass:
    def test_it_does_not_return_the_bare_all_clear(self):
        lines = _v(Endpoint(name="E1", k=3, n=10, n_cases=1))
        assert lines[0] != "No pre-registered failure condition triggered."

    def test_it_says_the_condition_was_not_tested(self):
        joined = " ".join(_v(Endpoint(name="E1", k=3, n=10, n_cases=1)))
        assert "NOT EVALUATED" in joined
        assert "not tested" in joined

    def test_it_reports_the_observed_rate_that_was_measurable(self):
        """The bound was unmeasurable; the rate was not, and 30% over a 20%
        ceiling is the number a reader most needs to see."""
        joined = " ".join(_v(Endpoint(name="E1", k=3, n=10, n_cases=1)))
        assert "30.0%" in joined and "3/10" in joined

    def test_the_summary_line_refuses_to_reassure(self):
        first = _v(Endpoint(name="E1", k=3, n=10, n_cases=1))[0]
        assert "not a clean result" in first

    def test_it_names_why_the_bootstrap_could_not_run(self):
        joined = " ".join(_v(Endpoint(name="E1", k=3, n=10, n_cases=1)))
        assert "at least two" in joined


class TestGenuineResultsAreUnchanged:
    def test_a_real_clean_run_still_gets_the_plain_all_clear(self):
        e = Endpoint(name="E1", k=0, n=40, n_cases=5, ci=(0.0, 0.08))
        assert _v(e) == ["No pre-registered failure condition triggered."]

    def test_a_real_breach_still_fires(self):
        e = Endpoint(name="E1", k=6, n=20, n_cases=4, ci=(0.1, 0.31))
        assert "NOT DEPLOYABLE" in _v(e)[0]

    def test_an_explicit_upper_bound_is_preferred_over_the_interval(self):
        """`upper_bound` wins when present, so a NaN interval beside a real
        bound must not trip the not-evaluated path."""
        e = Endpoint(name="E1", k=0, n=30, n_cases=1, upper_bound=0.09)
        assert _v(e) == ["No pre-registered failure condition triggered."]


class TestCoverageHasTheSameShape:
    def test_absent_coverage_is_reported_not_skipped(self):
        e = Endpoint(name="E1", k=0, n=40, n_cases=5, ci=(0.0, 0.08))
        joined = " ".join(_v(e, E4_coverage={"rate": None}))
        assert "E4 NOT EVALUATED" in joined

    def test_low_coverage_still_fires(self):
        e = Endpoint(name="E1", k=0, n=40, n_cases=5, ci=(0.0, 0.08))
        joined = " ".join(_v(e, E4_coverage={"rate": 0.10}))
        assert "PARSING RESULT" in joined


class TestTheUnderlyingReturnIsStillHonest:
    def test_cluster_bootstrap_declines_rather_than_inventing(self):
        """The (nan, nan) itself is CORRECT and stays. One cluster cannot
        produce an interval, and a fabricated one would be far worse than a
        missing one -- the defect was never here, it was in the reader."""
        from metascience_agent.evaluation.corpus import cluster_bootstrap_ci
        assert all(math.isnan(x) for x in cluster_bootstrap_ci([]))
        assert all(math.isnan(x) for x in cluster_bootstrap_ci([("a", True)]))
