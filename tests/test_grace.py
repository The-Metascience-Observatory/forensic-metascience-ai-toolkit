"""A discrepancy that was forgiven is still a discrepancy, and it is recorded.

Rounding grace was applied INSIDE each check, so a rescued item returned
`consistent` and its residual was destroyed at source. That threw away the only
property that distinguishes rounding noise from anything else: DIRECTION. No
single cell can show a lean; it is a property of the set, and by the time
anything could aggregate, a rescued item looked identical to one that
reconciled exactly.
"""

import pytest

from metascience_agent import grace as G


def _rescued(reported, nearest, kind="printed_precision"):
    return G.record(strict_ok=False, lenient_ok=True, grace=kind,
                    reported=reported, nearest_consistent=nearest)


class TestARescuedItemIsStillConsistent:
    """The whole design depends on this staying true. If recording a residual
    ever starts raising severities, it has become an accusation machine fed by
    the very allowances that exist to prevent accusations."""

    def test_the_module_never_issues_a_severity(self):
        r = _rescued(1.004, 1.0)
        assert "severity" not in r
        assert G.RESCUE_NEVER_ACCUSES is True

    def test_a_strict_pass_is_not_marked_rescued(self):
        r = G.record(strict_ok=True, lenient_ok=True, reported=1.0, nearest_consistent=1.0)
        assert r["rescued"] is False and r["grace"] is None
        assert r["strict"] == "reconciles"


class TestTheSignIsThePoint:
    def test_residual_sign_survives(self):
        assert _rescued(1.004, 1.0)["direction"] == 1
        assert _rescued(0.996, 1.0)["direction"] == -1

    def test_an_even_split_reads_as_rounding(self):
        recs = [_rescued(1.0 + ((-1) ** i) * 0.004, 1.0) for i in range(40)]
        s = G.summarise(recs)
        assert s["n_rescued"] == 40
        assert s["sign_test_p"] > 0.5
        assert "what rounding alone looks like" in s["reading"]

    def test_a_lean_is_surfaced_with_an_exact_test(self):
        recs = ([_rescued(1.004, 1.0)] * 34) + ([_rescued(0.996, 1.0)] * 3)
        s = G.summarise(recs)
        assert s["n_leaning_high"] == 34 and s["n_leaning_low"] == 3
        assert s["sign_test_p"] < 1e-5
        assert "worth a human's eye" in s["reading"]

    def test_the_sign_test_is_symmetric(self):
        hi = G.summarise(([_rescued(1.004, 1.0)] * 30) + ([_rescued(0.996, 1.0)] * 5))
        lo = G.summarise(([_rescued(0.996, 1.0)] * 30) + ([_rescued(1.004, 1.0)] * 5))
        assert hi["sign_test_p"] == pytest.approx(lo["sign_test_p"])

    def test_a_fair_coin_is_not_flagged(self):
        # 20 of 40 must not read as evidence of anything.
        s = G.summarise([_rescued(1.0 + ((-1) ** i) * 0.004, 1.0) for i in range(40)])
        assert s["sign_test_p"] == pytest.approx(1.0)


class TestTheVocabularyIsClosed:
    def test_an_invented_reason_is_rejected(self):
        with pytest.raises(ValueError, match="closed vocabulary"):
            G.record(strict_ok=False, lenient_ok=True, grace="because_i_said_so")

    def test_every_kind_carries_an_evaluable_sentence(self):
        for kind, why in G.GRACE_KINDS.items():
            assert len(why) > 40, f"{kind} needs a reason a reader can evaluate"

    def test_the_split_by_allowance_is_reported(self):
        recs = [_rescued(1.004, 1.0), _rescued(1.004, 1.0, "one_tailed")]
        assert G.summarise(recs)["by_grace"] == {"printed_precision": 1, "one_tailed": 1}


class TestNothingToReportIsSaidPlainly:
    def test_no_rescues_says_so(self):
        s = G.summarise([G.record(strict_ok=True, lenient_ok=True)])
        assert s["n_rescued"] == 0
        assert "Nothing needed an allowance" in s["reading"]

    def test_missing_residuals_do_not_fabricate_a_lean(self):
        s = G.summarise([G.record(strict_ok=False, lenient_ok=True,
                                  grace="alternative_test")])
        assert s["n_with_direction"] == 0
        assert "no lean can be assessed" in s["reading"]


class TestTheReadingReportsTheMajorityNotThePositiveCount:
    """Written first as "{pos} of {n} lean the same way", which prints
    "0 of 24 lean the same way" when all 24 lean LOW -- the strongest possible
    signal rendered as though it were the absence of one. Caught by reading the
    output, not the code."""

    def test_an_all_low_set_says_24_of_24(self):
        recs = [_rescued(0.996, 1.0)] * 24
        r = G.summarise(recs)["reading"]
        assert "24 of 24 lean low" in r
        assert "0 of 24" not in r

    def test_an_all_high_set_says_24_of_24(self):
        recs = [_rescued(1.004, 1.0)] * 24
        r = G.summarise(recs)["reading"]
        assert "24 of 24 lean high" in r

    def test_both_directions_read_as_equally_strong(self):
        lo = G.summarise([_rescued(0.996, 1.0)] * 24)
        hi = G.summarise([_rescued(1.004, 1.0)] * 24)
        assert lo["sign_test_p"] == hi["sign_test_p"]
        assert "worth a human's eye" in lo["reading"]
        assert "worth a human's eye" in hi["reading"]


class TestGraceIsActuallyConsumed:
    """`grace.py` was written and wired to nothing -- the exact
    built-tested-never-consumed defect this repo keeps finding. A module with
    tests and no caller is not instrumentation, it is a decoration."""

    def test_check_regression_attaches_a_record(self):
        import scipy.stats as st
        from metascience_agent.tools.regression import check_regression
        t = float(st.t.isf(0.0312 / 2, 200))
        r = check_regression(b=round(t * 0.01, 4), se=0.0100, df=200,
                             reported_p=0.031, decimals_b=4, decimals_se=4,
                             decimals_p=3)
        assert "grace" in r, "the check must record what it forgave"
        assert r["grace"]["direction"] in (-1, 0, 1)

    def test_recording_does_not_change_the_verdict(self):
        import scipy.stats as st
        from metascience_agent.tools.regression import check_regression
        t = float(st.t.isf(0.0312 / 2, 200))
        for reported in (0.031, 0.030, 0.032):
            r = check_regression(b=round(t * 0.01, 4), se=0.0100, df=200,
                                 reported_p=reported, decimals_b=4,
                                 decimals_se=4, decimals_p=3)
            assert r["severity"] == "consistent", (reported, r["severity"])
