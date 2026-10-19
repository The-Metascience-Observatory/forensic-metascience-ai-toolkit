"""check_flow_arithmetic: the CONSORT ledger reconciles or it does not.

Exact integer arithmetic, four distinct failure modes never fused, and the
misapplication-guard invariant: a missing/fractional operand REFUSES
(`indeterminate`), it never accuses. `unaccounted_attrition` is capped
`suspicious` -- papers legitimately omit attrition reasons.
"""

from forensic_metascience_ai_toolkit.tools import check_flow_arithmetic


def stages_ok():
    return [
        {"label": "assessed", "n": 240,
         "excluded": [{"reason": "declined", "n": 12},
                      {"reason": "ineligible", "n": 28}]},
        {"label": "randomized", "n": 200,
         "arms": [{"label": "treatment", "n": 100},
                  {"label": "control", "n": 100}],
         "excluded": [{"reason": "lost to follow-up", "n": 5}]},
        {"label": "analyzed", "n": 195},
    ]


class TestReconciles:
    def test_a_clean_cascade_is_consistent(self):
        r = check_flow_arithmetic(stages_ok())
        assert r["severity"] == "consistent"
        assert r["consistent"] is True
        assert r["failures"] == []
        assert r["n_checks"] >= 3

    def test_integral_floats_are_counts(self):
        st = stages_ok()
        st[0]["n"] = 240.0
        assert check_flow_arithmetic(st)["severity"] == "consistent"


class TestHardFailures:
    def test_step_mismatch_is_impossible_with_the_difference(self):
        st = stages_ok()
        st[2]["n"] = 190          # 200 - 5 = 195, not 190
        r = check_flow_arithmetic(st)
        assert r["severity"] == "impossible"
        modes = [f["failure_mode"] for f in r["failures"]]
        assert "step_mismatch" in modes
        f = next(f for f in r["failures"] if f["failure_mode"] == "step_mismatch")
        assert (f["expected"], f["observed"], f["difference"]) == (195, 190, -5)

    def test_arms_that_dont_sum_are_impossible(self):
        st = stages_ok()
        st[1]["arms"][1]["n"] = 95    # 100 + 95 != 200
        r = check_flow_arithmetic(st)
        assert r["severity"] == "impossible"
        assert [f["failure_mode"] for f in r["failures"]] == ["arms_dont_sum"]

    def test_growth_after_randomization_fires_both_modes_unfused(self):
        r = check_flow_arithmetic([{"label": "randomized", "n": 100},
                                   {"label": "analyzed", "n": 104}])
        modes = sorted(f["failure_mode"] for f in r["failures"])
        assert modes == ["analyzed_exceeds_randomized", "step_mismatch"]
        assert r["severity"] == "impossible"

    def test_an_arm_larger_than_randomized_is_caught(self):
        r = check_flow_arithmetic(
            [{"label": "enrolled", "n": 300},
             {"label": "randomized", "n": 100},
             {"label": "analyzed", "n": 100,
              "arms": [{"label": "treatment", "n": 100},
                       {"label": "shadow", "n": 120}]}],
        )
        assert any(f["failure_mode"] == "analyzed_exceeds_randomized"
                   and f["stage"] == "shadow" for f in r["failures"])

    def test_explicit_randomized_label_anchors_the_check(self):
        r = check_flow_arithmetic(
            [{"label": "allocation", "n": 80}, {"label": "final", "n": 90}],
            randomized_label="allocation")
        assert any(f["failure_mode"] == "analyzed_exceeds_randomized"
                   for f in r["failures"])


class TestSoftFailure:
    def test_unexplained_drop_caps_at_suspicious(self):
        r = check_flow_arithmetic([{"label": "randomized", "n": 120},
                                   {"label": "analyzed", "n": 112}])
        assert r["severity"] == "suspicious"
        assert [f["failure_mode"] for f in r["failures"]] == \
            ["unaccounted_attrition"]

    def test_hard_beats_soft_in_the_verdict(self):
        st = stages_ok()
        st[2]["n"] = 190
        st.append({"label": "followed up", "n": 180})   # soft drop after hard
        r = check_flow_arithmetic(st)
        assert r["severity"] == "impossible"
        modes = {f["failure_mode"] for f in r["failures"]}
        assert "step_mismatch" in modes and "unaccounted_attrition" in modes


class TestGuardsRefuse:
    def test_missing_n_refuses(self):
        r = check_flow_arithmetic([{"label": "randomized"}])
        assert r["severity"] == "indeterminate"
        assert r["success"] is False and r["applicable"] is False
        assert "randomized" in r["error"]

    def test_fractional_n_refuses(self):
        r = check_flow_arithmetic([{"label": "randomized", "n": 119.5},
                                   {"label": "analyzed", "n": 100}])
        assert r["severity"] == "indeterminate"

    def test_bool_is_not_a_count(self):
        r = check_flow_arithmetic([{"label": "randomized", "n": True},
                                   {"label": "analyzed", "n": 1}])
        assert r["severity"] == "indeterminate"

    def test_missing_exclusion_n_refuses(self):
        r = check_flow_arithmetic(
            [{"label": "assessed", "n": 240,
              "excluded": [{"reason": "declined"}]},
             {"label": "randomized", "n": 200}])
        assert r["severity"] == "indeterminate"
        assert "declined" in r["error"]

    def test_empty_and_nonlist_refuse(self):
        assert check_flow_arithmetic([])["severity"] == "indeterminate"
        assert check_flow_arithmetic("stages")["severity"] == "indeterminate"

    def test_unknown_randomized_label_refuses(self):
        r = check_flow_arithmetic(stages_ok(), randomized_label="enrolment")
        assert r["severity"] == "indeterminate"
        assert "enrolment" in r["error"]

    def test_single_uncheckable_stage_refuses(self):
        r = check_flow_arithmetic([{"label": "randomized", "n": 100}])
        assert r["severity"] == "indeterminate"

    def test_no_random_stage_notes_the_unrun_check(self):
        r = check_flow_arithmetic([{"label": "enrolled", "n": 100},
                                   {"label": "completed", "n": 100}])
        assert r["severity"] == "consistent"
        assert "randomized_label" in r.get("note", "")
