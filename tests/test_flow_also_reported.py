"""A flow stage printed twice is checked against itself (also_reported).

MEASURED 2026-10-14 (cerebrolysin_flow, grok): a cascade built from the
Results (30 -> 21 -> 15) passed, and the review said "the flow reconciles";
the abstract put 16 rats, not 21, at the second operation.
"""

from metascience_agent.tools.flow import check_flow_arithmetic


def _stages(also=None):
    second = {"label": "second operation", "n": 21}
    if also is not None:
        second["also_reported"] = also
    return [{"label": "randomized", "n": 30}, second, {"label": "completed 100 days", "n": 15}]


def test_the_measured_contradiction_is_caught():
    r = check_flow_arithmetic(_stages([{"n": 16, "source": "Abstract"}]))
    assert r["severity"] == "highly_suspicious"
    [f] = [f for f in r["failures"] if f["failure_mode"] == "conflicting_reports"]
    assert (f["expected"], f["observed"]) == (21, 16) and "Abstract" in f["sentence"]


def test_agreeing_printings_add_checks_not_failures():
    r = check_flow_arithmetic(_stages([{"n": 21, "source": "Figure 1"}]))
    assert not any(f["failure_mode"] == "conflicting_reports" for f in r["failures"])


def test_a_pass_says_it_covers_only_the_counts_passed():
    r = check_flow_arithmetic([{"label": "randomized", "n": 30,
                                "arms": [{"label": "a", "n": 15}, {"label": "b", "n": 15}]}])
    assert r["severity"] == "consistent"
    assert "AS PASSED" in r["explanation"] and "also_reported" in r["explanation"]


def test_a_hard_failure_still_wins():
    stages = _stages([{"n": 16, "source": "Abstract"}])
    stages[0]["arms"] = [{"label": "a", "n": 10}, {"label": "b", "n": 10}]   # 20 != 30
    assert check_flow_arithmetic(stages)["severity"] == "impossible"


def test_an_unusable_printing_refuses():
    r = check_flow_arithmetic(_stages([{"n": "about 16", "source": "Abstract"}]))
    assert r["severity"] == "indeterminate"
