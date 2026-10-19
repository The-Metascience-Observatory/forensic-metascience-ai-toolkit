"""Tests for GRIM-U (Mann-Whitney U / Wilcoxon rank-sum p-value granularity).

Regression pins reproduce the four worked examples in Heathers & Grimes (2026)
and the paper's Table 2 / Table 7 achievable-p values.
"""

import pytest

from metascience_agent.tools.grimu import (
    _achievable,
    _exact_u_counts,
    _p_normal,
    _mu_sigma,
    grimu_check,
    grimu_coexistence,
)


class TestEngine:
    def test_normal_approx_reproduces_table2(self):
        """Paper Table 2 (6v6): normal-approx p at half-integer U."""
        mU, sdU = _mu_sigma(6, 6)
        # U=0.5,1.5,2.5 (no CC) → 0.005074868, 0.008239019, 0.013065227
        assert _p_normal(0.5, mU, sdU, 0.0, False) == pytest.approx(0.005074868, abs=1e-8)
        assert _p_normal(1.5, mU, sdU, 0.0, False) == pytest.approx(0.008239019, abs=1e-8)
        assert _p_normal(2.5, mU, sdU, 0.0, False) == pytest.approx(0.013065227, abs=1e-8)
        # U=0,1 (Table 7) → 0.003947752, 0.006485308
        assert _p_normal(0.0, mU, sdU, 0.0, False) == pytest.approx(0.003947752, abs=1e-8)
        assert _p_normal(1.0, mU, sdU, 0.0, False) == pytest.approx(0.006485308, abs=1e-8)

    def test_exact_counts_sum_and_symmetry(self):
        c = _exact_u_counts(6, 6)
        assert sum(c) == 924  # C(12,6)
        assert c[0] == 1
        assert c == c[::-1]

    def test_wagner_mu_sigma(self):
        mU, sdU = _mu_sigma(9, 18)
        assert mU == 81
        assert sdU == pytest.approx(19.4422, abs=1e-3)

    def test_achievable_gated_for_large_n(self):
        # exact skipped past the 5000-product cap (100*100=10000), but the
        # normal set is still built quickly
        ach = _achievable(100, 100, [0.0], ["normal", "exact"], False)
        assert all(a["method"] == "normal" for a in ach)  # exact gated off
        # small product still includes exact
        ach_small = _achievable(6, 6, [0.0], ["normal", "exact"], False)
        assert any(a["method"] == "exact" for a in ach_small)


class TestWagner:
    """Wagner et al. (2025), 9 vs 18 — all consistent per the paper."""

    def test_operative_time_consistent(self):
        r = grimu_check(9, 18, 0.607)
        assert r["severity"] == "consistent"
        assert r["matched"]

    def test_hospitalization_granularity_miss(self):
        # paper: p=0.678 best-approximated at 0.681, no whole/half U → miss
        r = grimu_check(9, 18, 0.678)
        assert r["severity"] == "suspicious"
        assert not r["matched"]

    def test_hospitalization_corrected_value_consistent(self):
        r = grimu_check(9, 18, 0.681)
        assert r["severity"] == "consistent"


class TestBrouwers:
    """Brouwers et al. (2024), 8 vs 8 — the 0.171/0.172 co-existence case."""

    def test_0172_consistent(self):
        assert grimu_check(8, 8, 0.172)["severity"] == "consistent"

    def test_0171_suspicious(self):
        r = grimu_check(8, 8, 0.171)
        assert r["severity"] == "suspicious"
        assert r["nearest_below"] and r["nearest_above"]

    def test_coexistence_violation(self):
        r = grimu_coexistence(8, 8, [0.171, 0.172])
        assert r["severity"] == "suspicious"
        assert len(r["coexistence_violations"]) == 1
        v = r["coexistence_violations"][0]
        assert v["p_inconsistent"] == 0.171 and v["p_consistent"] == 0.172

    def test_low_p_threshold_reachable(self):
        # 8v8 floor ~0.000155 < 0.001 → "<0.001" is reachable, not impossible
        r = grimu_check(8, 8, "<0.001")
        assert r["severity"] == "consistent"
        assert r["floor_p"] < 0.001


class TestKhajuria:
    """Khajuria et al. (2024), 6 vs 6 — below-floor impossibilities."""

    def test_p_001_below_floor_impossible(self):
        r = grimu_check(6, 6, 0.001)
        assert r["severity"] == "impossible"
        assert r["below_floor"] is True
        assert r["floor_p"] == pytest.approx(0.00216, abs=1e-4)  # exact-union floor

    def test_threshold_below_floor_impossible(self):
        r = grimu_check(6, 6, "<0.001")
        assert r["severity"] == "impossible"
        assert r["is_threshold"] is True

    def test_p_007_granularity_miss(self):
        # paper: no U gives 0.007 (nearest U=1 → 0.006485)
        r = grimu_check(6, 6, 0.007)
        assert r["severity"] == "suspicious"
        assert not r["matched"]


class TestCoexistenceSeverity:
    """The top-level severity must not hide what per_value already found.

    A consumer that reads only `severity` never opens `per_value`, so any
    collapse here turns a detected impossibility into a clean report.
    """

    def test_two_impossibles_do_not_collapse_to_consistent(self):
        # 5v5 floor is ~0.00794, so both p's are individually below-floor
        # impossible; no pairwise co-existence violation fires (neither value
        # is `suspicious`), which previously left the top level `consistent`.
        assert grimu_check(5, 5, 0.001)["severity"] == "impossible"
        assert grimu_check(5, 5, 0.002)["severity"] == "impossible"
        r = grimu_coexistence(5, 5, [0.001, 0.002])
        assert [pv["severity"] for pv in r["per_value"]] == ["impossible", "impossible"]
        assert r["severity"] == "impossible"
        assert r["coexistence_violations"] == []

    def test_pairwise_verdict_never_downgrades_an_impossibility(self):
        # 8v8: 0.171/0.172 is a genuine co-existence violation (suspicious),
        # but "0.0001" is below the 8v8 floor (~0.000155) and outranks it.
        # (passed as a string so the 4th decimal is honoured -- a bare float
        # carries no printed precision and falls back to 3 dp)
        r = grimu_coexistence(8, 8, [0.171, 0.172, "0.0001"])
        assert r["coexistence_violations"]  # pairwise rule still fires
        assert "impossible" in [pv["severity"] for pv in r["per_value"]]
        assert r["severity"] == "impossible"

    def test_all_consistent_stays_consistent(self):
        r = grimu_coexistence(9, 18, [0.607, 0.681])
        assert [pv["severity"] for pv in r["per_value"]] == ["consistent", "consistent"]
        assert r["severity"] == "consistent"


class TestCoexistenceOneSided:
    """One-sided tables must be scored against the one-sided achievable set."""

    def test_one_sided_propagates_to_each_value(self):
        # 8v8 p=0.086: suspicious two-sided, consistent one-sided. Forcing a
        # one-sided table onto the two-sided set is a false accusation.
        assert grimu_check(8, 8, 0.086)["severity"] == "suspicious"
        assert grimu_check(8, 8, 0.086, one_sided=True)["severity"] == "consistent"

        two = grimu_coexistence(8, 8, [0.086, 0.172])
        assert two["severity"] == "suspicious"
        assert [pv["severity"] for pv in two["per_value"]] == ["suspicious", "consistent"]

        one = grimu_coexistence(8, 8, [0.086, 0.172], one_sided=True)
        assert [pv["severity"] for pv in one["per_value"]] == ["consistent", "consistent"]
        assert one["severity"] == "consistent"

    def test_one_sided_default_matches_grimu_check(self):
        # default is two-sided in both entry points
        assert (grimu_coexistence(8, 8, [0.086, 0.172])["per_value"][0]["severity"]
                == grimu_check(8, 8, 0.086, one_sided=False)["severity"])


class TestNumericPrecisionInference:
    """The number of decimals a paper printed is a fact about the PAPER; a bare
    Python float does not carry it. The old code silently assumed 3 decimals
    for any numeric reported_p, so grimu_check(4, 4, 0.02) was scored as
    "0.020" (interval [0.0195, 0.0205], below the 4v4 floor ~0.0209 ->
    `impossible`) while grimu_check(4, 4, "0.02") was `consistent`. Same
    number, opposite verdicts, and the accusing one rode on OUR default.

    Fix: infer the MINIMUM printed precision from the float's shortest
    round-tripping decimal form (never narrower than anything the paper could
    have printed, so it can only widen the interval -- the lenient direction),
    and refuse floats whose shortest form is float noise.
    """

    def test_float_and_string_spelling_agree(self):
        rf = grimu_check(4, 4, 0.02)
        rs = grimu_check(4, 4, "0.02")
        assert rf["severity"] == rs["severity"] == "consistent"
        assert rf["decimals"] == 2

    def test_float_never_silently_assumes_three_decimals(self):
        # 0.5 prints as one decimal; the old default clamped it to 3.
        r = grimu_check(8, 8, 0.5)
        assert r["decimals"] == 1

    def test_explicit_decimals_still_licenses_the_detection(self):
        # If the caller ASSERTS the paper printed "0.020" (3 dp), the
        # below-floor impossibility is genuine and must survive.
        r = grimu_check(4, 4, 0.02, decimals=3)
        assert r["severity"] == "impossible"
        assert r["below_floor"] is True

    def test_float_noise_precision_is_refused_not_scored(self):
        # 0.1 + 0.2 -> 0.30000000000000004: its shortest decimal form needs 17
        # decimals, which matches no cleanly printed p-value. Refuse visibly.
        r = grimu_check(8, 8, 0.1 + 0.2)
        assert r["severity"] == "indeterminate"
        assert "error" in r
        assert "decimals" in r["error"] or "precision" in r["error"]

    def test_inference_source_is_disclosed(self):
        assert "float" in grimu_check(4, 4, 0.02)["decimals_source"]
        assert grimu_check(4, 4, "0.02")["decimals_source"] == "printed_literal"
        assert grimu_check(4, 4, 0.02, decimals=2)["decimals_source"] == "caller"

    def test_khajuria_float_pin_survives_inference(self):
        # 0.001 round-trips at exactly 3 decimals, so the canonical Khajuria
        # below-floor impossibility is unchanged by the inference change.
        r = grimu_check(6, 6, 0.001)
        assert r["severity"] == "impossible"
        assert r["decimals"] == 3


class TestGuardsAndScaling:
    def test_bad_group_sizes(self):
        assert grimu_check(0, 5, 0.5)["severity"] == "indeterminate"
        assert "error" in grimu_check(0, 5, 0.5)

    def test_p_out_of_range(self):
        assert grimu_check(6, 6, 1.5)["severity"] == "indeterminate"
        assert grimu_check(6, 6, 0.0)["severity"] == "indeterminate"

    def test_unparseable_p(self):
        assert grimu_check(6, 6, "n.s.")["severity"] == "indeterminate"

    def test_large_n_no_false_impossible(self):
        # granularity vanishes; must never flag as impossible/suspicious
        r = grimu_check(200, 200, 0.03)
        assert r["severity"] == "consistent"

    def test_string_and_float_agree(self):
        assert grimu_check(8, 8, 0.172)["severity"] == grimu_check(8, 8, "0.172")["severity"]

    def test_result_is_json_serializable(self):
        import json
        json.dumps(grimu_check(6, 6, 0.007))  # no numpy types leaking
        json.dumps(grimu_coexistence(8, 8, [0.171, 0.172]))
