"""One rounding convention, applied by every member of the granularity family.

`grim_test` has carried a truncation rescue since d584401. `grimmer_test` and
`sprite_reconstruct` did not -- and both CITED Greg's ruling of 2026-08-10 in
their own comments while arguing for the population-SD rescue:

    "it would be inconsistent to do the truncation check but not this."

So the three tools returned different verdicts about one cell. Measured on the
archived run `tests/fixtures/papers/cerebrolysin_run_2026-08-09/10.1016--j.scitotenv.2019.
05.070`: on `59.06 +/- 11.15, n=30`, grim_check said `rounding_convention` while
grimmer_check and sprite_reconstruct both said `impossible`. `granularity_ceiling`
exists to prevent exactly that.

WHAT IT COSTS AND WHAT IT BUYS, both counted 2026-08-27 rather than argued:

    400 honest integer samples, printed the way a TRUNCATING reporter prints them
      falsely accused before:  274 / 400 = 68.5%
      falsely accused after:     0 / 400 =  0.0%

    4,196 printable (mean, SD) pairs that round-half called infeasible
      cleared by truncation alone (the recall cost):  180 = 4.3%

A paper that truncates was having roughly two thirds of its GRIMMER checks called
impossible. That is the largest false-accusation channel measured anywhere in
this toolkit, and closing it costs 4.3% of detections.

NOT AN OFF SWITCH, which is the condition Greg attached on 2026-08-11 -- "I agree
to not do the decimal expansion if it ALWAYS rescues an otherwise impossible
finding." Over the printable SD grid at (n, dp) in {20,30,50,100} x {1,2},
truncation rejects 5.1 / 61.4 / 2.6 / 43.1 / 0 / 25.3 / 0 / 12.3 per cent of the
grid against round-half's 5.1 / 61.9 / 2.6 / 43.1 / 0 / 25.3 / 0 / 12.5. It
rejects what round-half rejects; in the two cells where it rejects nothing,
round-half rejected nothing either.
"""
from __future__ import annotations

import math

import pytest

from metascience_agent.tools import rounding as R
from metascience_agent.tools.grim import grim_test
from metascience_agent.tools.sd_checks import grimmer_test
from metascience_agent.tools.sprite import sprite_reconstruct

#: A real, ordinary Likert sample. Every value inside 1-7, n=30, S=120, Q=546,
#: exact mean 4.000000 and exact sample SD 1.508596. A truncating reporter
#: prints it "4.00, SD 1.50" -- and `tests/test_false_positive_guards.py` used
#: to assert that exact pair was `no_solution_proven`, i.e. proven not to exist.
#: It exists. It is right here.
REAL_SAMPLE = [1, 1, 1, 2, 3, 3] + [4] * 18 + [5, 5, 6, 7, 7, 7]


def _exact(xs):
    n = len(xs)
    m = sum(xs) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def _truncate(v, d):
    return math.floor(v * 10 ** d) / 10 ** d


class TestTheSampleThatDisprovedTheOldExpectation:
    """The fixture is a real sample, not a hand-picked pair of numbers. If the
    arithmetic below ever stops holding, every test in this file is void."""

    def test_it_is_an_ordinary_likert_sample(self):
        assert len(REAL_SAMPLE) == 30
        assert all(1 <= x <= 7 for x in REAL_SAMPLE)
        assert all(float(x).is_integer() for x in REAL_SAMPLE)

    def test_its_exact_statistics_are_what_the_docstring_claims(self):
        m, sd = _exact(REAL_SAMPLE)
        assert sum(REAL_SAMPLE) == 120
        assert sum(x * x for x in REAL_SAMPLE) == 546
        assert m == pytest.approx(4.0, abs=1e-9)
        assert sd == pytest.approx(1.508596, abs=1e-6)

    def test_a_truncating_reporter_prints_the_disputed_pair(self):
        m, sd = _exact(REAL_SAMPLE)
        assert (_truncate(m, 2), _truncate(sd, 2)) == (4.00, 1.50)

    def test_and_a_rounding_reporter_prints_something_else(self):
        """The two conventions genuinely disagree here -- that is the point."""
        m, sd = _exact(REAL_SAMPLE)
        assert (round(m, 2), round(sd, 2)) == (4.00, 1.51)


class TestNoToolCallsThisSampleImpossible:
    @pytest.mark.parametrize("mean,sd", [(4.00, 1.50)])
    def test_sprite(self, mean, sd):
        r = sprite_reconstruct(mean=mean, sd=sd, n=30, scale_min=1, scale_max=7,
                               decimals_mean=2, decimals_sd=2,
                               bound_source="stated")
        assert r.get("severity") != "impossible"

    @pytest.mark.parametrize("mean,sd", [(4.00, 1.50)])
    def test_grimmer(self, mean, sd):
        r = grimmer_test(mean=mean, sd=sd, n=30, decimals=2, decimals_sd=2,
                         scale_min=1, scale_max=7, bound_source="stated",
                         discreteness_source="stated")
        assert r.get("severity") != "impossible"


class TestTheThreeToolsAgree:
    """The invariant. Three tools, one cell, one verdict -- which is what
    `granularity_ceiling` was written to guarantee and did not deliver."""

    ARCHIVED = [(17.63, 2.38, 30), (59.06, 11.15, 30)]

    @pytest.mark.parametrize("mean,sd,n", ARCHIVED)
    def test_no_tool_disagrees_about_an_archived_cell(self, mean, sd, n):
        g = grim_test(mean=mean, n=n, decimals=2, data_type="likert",
                      scale_min=1, scale_max=100, bound_source="stated",
                      discreteness_source="stated")
        gr = grimmer_test(mean=mean, sd=sd, n=n, decimals=2, decimals_sd=2,
                          scale_min=1, scale_max=100, bound_source="stated",
                          discreteness_source="stated")
        sp = sprite_reconstruct(mean=mean, sd=sd, n=n, scale_min=1, scale_max=100,
                                decimals_mean=2, decimals_sd=2,
                                bound_source="stated")
        got = {"grim": g.get("severity"), "grimmer": gr.get("severity"),
               "sprite": sp.get("severity")}
        assert len(set(got.values())) == 1, f"the three tools disagree: {got}"

    @pytest.mark.parametrize("mean,sd,n", ARCHIVED)
    def test_and_the_verdict_is_not_an_accusation(self, mean, sd, n):
        """Agreeing on `impossible` would satisfy the test above and be worse
        than disagreeing. Both archived cells are truncation artefacts."""
        sp = sprite_reconstruct(mean=mean, sd=sd, n=n, scale_min=1, scale_max=100,
                                decimals_mean=2, decimals_sd=2,
                                bound_source="stated")
        assert sp.get("severity") == "consistent"


class TestTheWindowItself:
    """`rounding.window` is the one definition the three tools now share."""

    def test_the_two_conventions_are_different_windows(self):
        assert R.window(2.38, 2, "round_half") == (2.375, 2.385)
        lo, hi = R.window(2.38, 2, "truncation")
        assert lo == pytest.approx(2.38) and hi == pytest.approx(2.39)

    def test_neither_window_contains_the_other(self):
        """They OVERLAP on [2.380, 2.385). What matters is the exclusive half:
        2.3850589 -- the archived SD -- is admissible only under truncation."""
        rh = R.window(2.38, 2, "round_half")
        tr = R.window(2.38, 2, "truncation")
        assert not (rh[0] <= tr[0] and tr[1] <= rh[1])
        assert not (tr[0] <= rh[0] and rh[1] <= tr[1])
        assert not (rh[0] <= 2.3850589 < rh[1])
        assert tr[0] <= 2.3850589 < tr[1]

    def test_it_refuses_an_unknown_precision_rather_than_defaulting(self):
        with pytest.raises(TypeError):
            R.window(1.0, None)

    def test_an_unknown_convention_is_an_error_not_a_silent_round_half(self):
        with pytest.raises(ValueError):
            R.window(1.0, 2, "banker")


class TestTheRescueIsNotAnOffSwitch:
    """Greg, 2026-08-11: a rescue that always rescues is not a judgement.
    This is the positive control -- if truncation ever stops rejecting what
    round-half rejects, the rescue has become an off switch and this fails."""

    @pytest.mark.parametrize("n,dp", [(20, 2), (30, 2), (100, 2)])
    def test_truncation_still_rejects_most_of_what_round_half_rejects(self, n, dp):
        from metascience_agent.tools.sprite import _sd_window_feasible
        S = int(n * 3.5)
        grid = [round(x * 10 ** -dp, dp) for x in range(1, int(4 * 10 ** dp))]
        rh = [s for s in grid
              if not _sd_window_feasible(S, n, s, dp, 1, 7,
                                         convention="round_half")[0]]
        both = [s for s in rh
                if not _sd_window_feasible(S, n, s, dp, 1, 7,
                                           convention="truncation")[0]]
        assert rh, "the fixture must sit where the check HAS power"
        assert len(both) / len(rh) > 0.5, (
            f"truncation rescued {100 * (1 - len(both) / len(rh)):.0f}% of "
            f"everything round-half rejected at n={n}, {dp}dp -- that is an "
            f"off switch, not a rescue")
