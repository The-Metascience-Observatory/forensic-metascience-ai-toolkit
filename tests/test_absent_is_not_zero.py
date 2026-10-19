"""Absent, zero and unknown are three different facts.

Two places rendered a missing value as a measured one, on surfaces a reader
takes at face value.
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from metascience_agent.bundle import _run_facts


def _wall(meta: dict) -> str:
    rows = _run_facts(pathlib.Path(tempfile.mkdtemp()), meta)
    return next(r["value"] for r in rows if r["fact"] == "Wall time")


class TestWallTime:
    """`parallel._usage_totals` writes `None` rather than `0.0` when nothing was
    timed, and its own comment says why: "0.0 would print a false measurement".
    The renderer's `or 0` reintroduced exactly that -- a run whose total was
    never recorded displayed "Wall time 0 min" beside stage timings summing to
    half an hour."""

    def test_a_recorded_total_is_shown(self):
        assert _wall({"total_wall_seconds": 1800, "stages": {}}) == "30 min"

    def test_an_absent_total_is_not_zero_minutes(self):
        got = _wall({"stages": {"a": {"wall_seconds": 900.0},
                                "b": {"wall_seconds": 885.8}}})
        assert got != "0 min"
        assert "30 min" in got

    def test_an_absent_total_says_where_the_number_came_from(self):
        got = _wall({"stages": {"a": {"wall_seconds": 900.0}}})
        assert "summed from stages" in got

    def test_nothing_timed_says_not_recorded(self):
        """The third state: not absent-and-recoverable, but genuinely
        unknown."""
        assert _wall({"stages": {}}) == "not recorded"
        assert _wall({}) == "not recorded"

    def test_zero_is_still_zero_when_it_was_measured(self):
        """A real 0 must survive -- this fix must not convert a measurement
        into an absence."""
        assert _wall({"total_wall_seconds": 0, "stages": {}}) == "0 min"


class TestTheBenchmarkDenominatorIsVisible:
    """`benchmark` drops cases its own generator could not actually flaw -- a
    transposition that leaves the mean unchanged is undetectable by anyone, so
    counting it would measure the generator rather than the tool. That
    exclusion is right, and it was INVISIBLE: the table printed `9/11` for a
    `--flawed 15` request, so the rate ROSE as the generator got worse."""

    def test_the_benchmark_reports_what_it_excluded(self):
        from metascience_agent.simulation import benchmark
        result = benchmark(n_clean=4, n_flawed_per_kind=15, seed0=1000)
        for kind, s in result["sensitivity"].items():
            assert "undetectable" in s, kind
            assert s["total"] + s["undetectable"] == 15, kind

    def test_the_rate_uses_the_reduced_denominator_deliberately(self):
        from metascience_agent.simulation import benchmark
        result = benchmark(n_clean=4, n_flawed_per_kind=15, seed0=1000)
        for s in result["sensitivity"].values():
            if s["total"]:
                assert s["rate"] == pytest.approx(s["caught"] / s["total"])

    def test_the_renderer_prints_the_excluded_column(self):
        """The data always said how many; the table did not."""
        import inspect
        from metascience_agent import cli
        src = inspect.getsource(cli)
        assert '"not flawed"' in src
        assert "undetectable" in src
