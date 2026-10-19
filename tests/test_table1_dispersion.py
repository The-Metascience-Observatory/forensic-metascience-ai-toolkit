"""Tests for Bayesian-style Table 1 dispersion."""

import math
import random

import pytest

from metascience_agent.tools.table1_dispersion import (
    table1_dispersion,
    _z_from_p_two_sided,
    _precision_multiplier,
    _row_to_p_value,
)
from metascience_agent.tools.csf import csf_test
import numpy as np


#: Heathers' Fujii 2005 baseline rows (the four continuous ones).
FUJII_ROWS = [
    {"label": "age", "means": [41, 41, 41, 42], "sds": [12]*4, "ns": [30]*4},
    {"label": "height", "means": [161, 161, 163, 162], "sds": [8, 8, 8, 10], "ns": [30]*4},
    {"label": "weight", "means": [57, 58, 59, 59], "sds": [10, 10, 9, 10], "ns": [30]*4},
    {"label": "init_dose", "means": [29, 29, 30, 30], "sds": [4, 5, 5, 5], "ns": [30]*4},
]


#: 18 well-powered rows whose arm means differ by hundredths of an SD, giving
#: per-row p-values of 0.95-0.99. This is under-dispersion strong enough that
#: csf_test's correlation-aware null also calls it a finding, so it is the case
#: that must STILL escalate once every guard is satisfied.
_STRONG_DELTAS = (0.017, 0.035, 0.052, 0.070, 0.028, 0.042)
STRONGLY_UNDER_DISPERSED = [
    {"label": f"v{i}",
     "means": [50.0 + 3 * i, round(50.0 + 3 * i + _STRONG_DELTAS[i % 6], 3)],
     "sds": [10.0, 10.1], "ns": [150, 150]}
    for i in range(18)
]


#: The 12-row table that produced the disagreement this module was hardened for:
#: dispersion returned `highly_suspicious` (tau-hat 7.40, CI [7.08, 7.75]) while
#: csf_test on the very same p-values returned `indeterminate`.
TWELVE_ROW_CLINICAL = [
    {"label": lab, "means": [m, round(m + 0.0178 * sd, prec)],
     "sds": [sd, round(sd * 1.01, 3)], "ns": [100, 100]}
    for lab, m, sd, prec in [
        ("age", 54.1, 10.0, 1), ("height", 168.3, 9.0, 1), ("weight", 78.2, 12.0, 1),
        ("bmi", 27.6, 4.0, 2), ("waist", 95.1, 11.0, 1), ("sbp", 131.2, 15.0, 1),
        ("dbp", 80.4, 9.0, 1), ("hr", 72.1, 11.0, 1), ("glucose", 5.61, 1.10, 2),
        ("chol", 5.21, 1.00, 2), ("hdl", 1.31, 0.30, 3), ("crp", 3.11, 1.50, 2),
    ]
]


class TestHelpers:
    def test_z_from_p_under_null(self):
        # z = Φ⁻¹(1 - p/2). p=1 → z=0; p=0.5 → z≈0.674; p=0.05 → z≈1.96.
        assert _z_from_p_two_sided(1.0) == pytest.approx(0.0, abs=1e-6)
        assert _z_from_p_two_sided(0.5) == pytest.approx(0.6745, abs=1e-3)
        assert _z_from_p_two_sided(0.05) == pytest.approx(1.96, abs=0.01)
        assert _z_from_p_two_sided(0.001) == pytest.approx(3.291, abs=0.01)

    def test_precision_multiplier_under_null(self):
        # If z² ≈ 1 on average, τ̂ ≈ 1.
        z2 = np.array([1.0, 1.0, 1.0])
        assert _precision_multiplier(z2) == pytest.approx(1.0)

    def test_precision_multiplier_under_dispersion(self):
        # mean(z²) = 0.25 → τ̂ = 2.0.
        z2 = np.array([0.25, 0.25, 0.25])
        assert _precision_multiplier(z2) == pytest.approx(2.0)


class TestRowToPValue:
    def test_continuous_row(self):
        p, kind, _ = _row_to_p_value({
            "means": [10, 11, 12], "sds": [2, 2, 2], "ns": [10, 10, 10]
        })
        assert kind == "continuous"
        assert 0.0 <= p <= 1.0

    def test_categorical_row(self):
        p, kind, _ = _row_to_p_value({"counts": [[10, 20], [30, 25]]})
        assert kind == "categorical"
        assert 0.0 <= p <= 1.0

    def test_invalid_row(self):
        with pytest.raises(ValueError):
            _row_to_p_value({"foo": "bar"})


class TestFujii2005:
    """Heathers' Fujii 2005 example is the canonical under-dispersion case.

    Per-row p-values are cited in the intro doc as 0.9842, 0.9875, 0.77,
    0.8335, 0.7251.
    """

    def test_per_row_pvalues_match_intro(self):
        rows = [
            {"label": "age", "means": [41, 41, 41, 42], "sds": [12]*4, "ns": [30]*4},
            {"label": "sex", "counts": [[15, 16, 15, 16], [15, 14, 15, 14]]},
            {"label": "height", "means": [161, 161, 163, 162], "sds": [8, 8, 8, 10], "ns": [30]*4},
            {"label": "weight", "means": [57, 58, 59, 59], "sds": [10, 10, 9, 10], "ns": [30]*4},
            {"label": "init_dose", "means": [29, 29, 30, 30], "sds": [4, 5, 5, 5], "ns": [30]*4},
        ]
        result = table1_dispersion(rows, num_bootstrap=500, seed=0)
        per_row_p = {r["label"]: r["p_value"] for r in result["per_row"] if "p_value" in r}
        assert per_row_p["age"] == pytest.approx(0.9842, abs=1e-3)
        assert per_row_p["sex"] == pytest.approx(0.9875, abs=1e-3)
        assert per_row_p["height"] == pytest.approx(0.77, abs=2e-2)
        assert per_row_p["weight"] == pytest.approx(0.8335, abs=2e-3)
        assert per_row_p["init_dose"] == pytest.approx(0.7251, abs=2e-3)

    def test_fujii_is_refused_not_cleared_under_correlation(self):
        """Fujii is k = 4, worth df = 1.60 once discounted for correlation.

        The history matters. This asserted `highly_suspicious` (over-claiming on
        a bootstrap CI that was not a calibrated null), then `indeterminate` via
        a blanket small-k QUARANTINE (right answer, no reasoning). Under the
        exact chi-square null the arithmetic itself declines: tau-hat = 3.97 but
        the CI is [0.42, 8.01], which does not exclude tau = 1.

        `consistent` would be a FALSE ALL-CLEAR on the canonical fabrication
        case -- and that is exactly what this returned before the
        apparent-signal branch was added. The honest verdict is a refusal: four
        correlated baseline rows can neither convict nor clear.
        """
        result = table1_dispersion(FUJII_ROWS, num_bootstrap=500, seed=0,
                                   design="parallel_rct")
        assert result["severity"] == "indeterminate"
        assert result["precision_multiplier"] > 2.0
        assert result["precision_multiplier_ci"][0] < 1.0, "tau = 1 is not excluded"
        assert "NOT a clean bill of health" in result["explanation"]
        # No longer suppressed downstream -- the refusal comes from the statistics.
        assert result.get("quarantined", False) is False

    def test_fujii_is_a_finding_if_the_rows_are_taken_as_independent(self):
        """The signal is real, and the tool must still say so under the assumption
        that licenses it. This is the pair that makes the refusal above honest
        rather than evasive: it names what would have to be true."""
        result = table1_dispersion(FUJII_ROWS, num_bootstrap=500, seed=0,
                                   design="parallel_rct", correlation=0.0)
        assert result["severity"] == "suspicious"
        assert result["precision_multiplier_ci"][0] > 1.0

    def test_fujii_capped_when_design_unstated(self):
        """The same table, design withheld, must not reach a fabrication verdict."""
        result = table1_dispersion(FUJII_ROWS, num_bootstrap=500, seed=0,
                                   correlation=0.0)
        assert result["severity"] == "suspicious"
        assert "DESIGN was not supplied" in result["explanation"]


class TestRandomizedControl:
    """Genuinely randomized data should give τ̂ ≈ 1 and severity 'consistent'."""

    def test_random_data_consistent(self):
        random.seed(42)
        rows = []
        for i in range(15):
            # Two arms drawn from N(50, 5²), n=30 each.
            m1 = random.gauss(50, 5 / math.sqrt(30))
            m2 = random.gauss(50, 5 / math.sqrt(30))
            rows.append({"label": f"v{i}", "means": [m1, m2], "sds": [5, 5], "ns": [30, 30]})
        result = table1_dispersion(rows, num_bootstrap=500, seed=0)
        # τ̂ should be near 1; allow generous tolerance for small-sample noise.
        assert 0.5 < result["precision_multiplier"] < 2.0
        assert result["severity"] in ("consistent", "suspicious")


class TestDesignUnknownCap:
    """Without a stated design, `highly_suspicious` is not available.

    csf_test has applied this cap since it was hardened; this tool escalated
    straight past it on `ci_lo > 2.0`, so the same table could be refused by one
    tool and called fabrication-grade by the other.
    """

    def test_twelve_row_table_is_capped_without_design(self):
        result = table1_dispersion(TWELVE_ROW_CLINICAL, num_bootstrap=500, seed=0)
        assert result["severity"] == "suspicious"
        assert result["precision_multiplier"] > 2.0, "the arithmetic is unchanged"

    def test_the_cap_says_which_designs_would_explain_it(self):
        result = table1_dispersion(TWELVE_ROW_CLINICAL, num_bootstrap=500, seed=0)
        assert "DESIGN was not supplied" in result["explanation"]
        assert "stratified" in result["explanation"].lower()

    def test_a_dependent_design_is_still_refused_outright(self):
        """The gate is separate from the cap and must survive it."""
        result = table1_dispersion(TWELVE_ROW_CLINICAL, num_bootstrap=500, seed=0,
                                   design="stratified")
        assert result["severity"] == "indeterminate"
        assert result["applicable"] is False


class TestDesignRecognitionParity:
    """`design_known` must mean RECOGNISED, not merely non-empty -- the same fix
    csf.py carries. `bool(design_key)` let any string lift the fabrication cap,
    so an honest under-dispersed table described as "observational cohort" or
    with a British spelling was escalated to `highly_suspicious`, while csf_test
    on the same p-values capped it. The two tools now place a design identically.
    """

    def test_an_unrecognized_design_does_not_lift_the_cap(self):
        """A string this module cannot place must keep the cap on: the designs
        that explain baseline uniformity innocently are exactly the ones an
        unrecognised string might be naming."""
        result = table1_dispersion(STRONGLY_UNDER_DISPERSED, num_bootstrap=500,
                                   seed=0, design="observational cohort",
                                   correlation=0.5)
        assert result["severity"] == "suspicious"

    def test_a_quasi_randomised_string_is_capped_not_escalated(self):
        """"quasi" DENIES randomisation, so _resolve_design returns None and the
        cap stays on -- the old `bool(design_key)` read the word 'randomised' in
        it and lifted the ceiling to `highly_suspicious`."""
        result = table1_dispersion(STRONGLY_UNDER_DISPERSED, num_bootstrap=500,
                                   seed=0, design="quasi-randomised",
                                   correlation=0.5)
        assert result["severity"] == "suspicious"

    def test_a_recognized_free_text_independent_design_still_escalates(self):
        """Free text that resolves to a genuine independent design lifts the cap,
        so the tool has not simply been switched off."""
        result = table1_dispersion(STRONGLY_UNDER_DISPERSED, num_bootstrap=500,
                                   seed=0, design="parallel randomized controlled trial",
                                   correlation=0.5)
        assert result["severity"] == "highly_suspicious"

    def test_a_free_text_dependent_design_is_refused_by_the_gate(self):
        """"cluster-randomised trial" exact-matched nothing in DEPENDENT_DESIGNS
        and escaped the gate; _resolve_design substring-matches "cluster" and
        refuses outright, matching csf_test."""
        result = table1_dispersion(STRONGLY_UNDER_DISPERSED, num_bootstrap=500,
                                   seed=0, design="cluster-randomised trial")
        assert result["severity"] == "indeterminate"
        assert result["applicable"] is False


class TestCorrelationAwareness:
    """Correlated baseline rows must make escalation HARDER, not easier."""

    def test_bootstrap_ci_widens_as_rho_rises(self):
        """The i.i.d. resample did the opposite: correlated rows narrowed it."""
        result = table1_dispersion(TWELVE_ROW_CLINICAL, num_bootstrap=1000, seed=0)
        profile = result["ci_sensitivity_profile"]
        lo_0, hi_0 = profile[0.0]
        lo_7, hi_7 = profile[0.7]
        assert (hi_7 - lo_7) > (hi_0 - lo_0)
        assert lo_7 < lo_0, "a correlation-discounted table cannot have a HIGHER floor"

    def test_effective_rows_discounts_correlated_rows(self):
        result = table1_dispersion(TWELVE_ROW_CLINICAL, num_bootstrap=500, seed=0)
        assert result["effective_rows"] < result["n_valid"]

    def test_independence_only_finding_is_not_escalated(self):
        """Design stated, but the finding evaporates under plausible correlation."""
        result = table1_dispersion(TWELVE_ROW_CLINICAL, num_bootstrap=500, seed=0,
                                   design="parallel_rct")
        assert result["severity"] == "suspicious"
        assert result["csf_cross_check"]["severity"] == "indeterminate"
        assert "correlation-aware" in result["explanation"]

    def test_supplied_correlation_is_used_instead_of_the_grid(self):
        result = table1_dispersion(TWELVE_ROW_CLINICAL, num_bootstrap=500, seed=0,
                                   design="parallel_rct", correlation=0.2)
        assert result["correlation_used"] == 0.2
        assert result["correlation_assumed"] is True

    def test_verdict_rho_matches_csf(self):
        """One calibrated constant, not two drifting ones."""
        from metascience_agent.tools.csf import VERDICT_RHO
        result = table1_dispersion(TWELVE_ROW_CLINICAL, num_bootstrap=200, seed=0)
        assert result["correlation_used"] == VERDICT_RHO
        assert result["correlation_assumed"] is False


class TestNoOppositeEndsOfTheLadder:
    """The two tools answer one question from one set of p-values.

    They may differ by a rung. They may not put the same table at
    `highly_suspicious` and `indeterminate` simultaneously.
    """

    OPPOSITE = {"highly_suspicious", "indeterminate"}

    @pytest.mark.parametrize("design", [None, "parallel_rct", "simple_randomization"])
    @pytest.mark.parametrize("rows,label", [
        (TWELVE_ROW_CLINICAL, "twelve_row_clinical"),
        (FUJII_ROWS, "fujii"),
        (STRONGLY_UNDER_DISPERSED, "strongly_under_dispersed"),
    ])
    def test_tools_agree_within_a_rung(self, rows, label, design):
        d = table1_dispersion(rows, num_bootstrap=500, seed=0, design=design)
        c = csf_test(d["p_values"], design=design)
        pair = {d["severity"], c["severity"]}
        assert pair != self.OPPOSITE, (
            f"{label} (design={design}): dispersion={d['severity']} "
            f"vs csf={c['severity']}"
        )


class TestTheToolStillFires:
    """Hardening must not amount to switching the check off."""

    def test_strong_under_dispersion_escalates_with_design_and_correlation(self):
        result = table1_dispersion(STRONGLY_UNDER_DISPERSED, num_bootstrap=500, seed=0,
                                   design="parallel_rct", correlation=0.5)
        assert result["severity"] == "highly_suspicious"
        assert result["correlation_used"] == 0.5
        # The floor clears 2 after discounting 18 correlated rows, not before.
        assert result["precision_multiplier_ci"][0] > 2.0

    def test_csf_corroborates_that_escalation(self):
        result = table1_dispersion(STRONGLY_UNDER_DISPERSED, num_bootstrap=500, seed=0,
                                   design="parallel_rct", correlation=0.5)
        assert result["csf_cross_check"]["severity"] in ("suspicious", "highly_suspicious")

    def test_the_same_table_is_still_capped_without_a_design(self):
        result = table1_dispersion(STRONGLY_UNDER_DISPERSED, num_bootstrap=500, seed=0,
                                   correlation=0.5)
        assert result["severity"] == "suspicious"


class TestSmallKCalibration:
    """The two quarantined accusation paths, RELEASED 2026-08-10.

    Both were quarantined because the percentile bootstrap CI on tau could not
    work at small k -- it resampled k values from k values, so a few similar z²
    gave a spuriously tight CI. Measured, it accused 35.9% of honest k = 2
    tables and 27.6% at k = 3. `_exact_tau_ci` fixes that at the source rather
    than suppressing it downstream, so the verdicts are allowed through again.

    `test_honest_tables_are_not_accused_at_any_k` is the release evidence and
    must keep passing for the release to remain justified.
    """

    def test_a_small_k_honest_table_is_no_longer_accused(self):
        """The measured honest-world rate at k = 3 was 27.7% accused, 7.3%
        fabrication-grade. Under the exact null it is 0.33% and 0.00%, so the
        blanket small-k quarantine is no longer what is holding this down --
        the calibration is. Genuinely honest rows must come back `consistent`,
        not merely un-accused."""
        rng = random.Random(11)
        rows = []
        for i in range(3):
            sd, base = 10.0, 50.0
            se = sd * math.sqrt(2 / 100)
            rows.append({"label": f"r{i}", "means": [base, base + rng.gauss(0, se)],
                         "sds": [sd, sd], "ns": [100, 100]})
        r = table1_dispersion(rows, num_bootstrap=1, seed=0, design="parallel_rct")
        assert r["severity"] == "consistent"
        assert r.get("quarantined", False) is False

    def test_an_extreme_small_k_table_may_still_accuse(self):
        """Release is not amnesty. Three rows whose arms differ by 0.002 SD each
        -- all three p = 0.9887, about 1e-5 under randomisation -- still reach a
        finding, and csf_test corroborates it on the same p-values. The exact
        null lowers the false-positive rate; it does not switch the check off."""
        rows = [{"means": [50.0, 50.02], "sds": [10.0, 10.0], "ns": [100, 100],
                 "label": f"r{i}"} for i in range(3)]
        r = table1_dispersion(rows, num_bootstrap=1, seed=0, design="parallel_rct")
        assert r["severity"] in ("suspicious", "highly_suspicious")
        assert r["csf_cross_check"]["severity"] in ("suspicious", "highly_suspicious")

    def test_the_statistics_are_always_preserved(self):
        rows = [{"means": [50.0, 50.02], "sds": [10.0, 10.0], "ns": [100, 100],
                 "label": f"r{i}"} for i in range(3)]
        r = table1_dispersion(rows, num_bootstrap=1, seed=0, design="parallel_rct")
        assert r["precision_multiplier"] > 2.0
        assert len(r["precision_multiplier_ci"]) == 2
        assert len(r["p_values"]) == 3
        assert r["ci_method"] == "exact_chi2"

    @pytest.mark.parametrize("k", [2, 3, 5, 12])
    def test_honest_tables_are_not_accused_at_any_k(self, k):
        """THE RELEASE EVIDENCE. Genuinely randomised tables, a stated design
        (the condition under which accusation is easiest), measured end to end
        through the real entry point rather than on synthetic z².

        The bootstrap accused 35.9% of these at k = 2 and 27.6% at k = 3, with
        7.3% fabrication-grade. Full sweep at 600 tables/k measured 0.00-0.33%
        accused and 0.00% fabrication-grade at every k from 2 to 20. This runs a
        smaller n for suite speed and asserts the bound that matters: a
        fabrication-grade accusation against an honest table is the worst output
        this toolkit can produce, and it must not happen at all.
        """
        rng = random.Random(909 + k)
        accused = 0
        n_tables = 120
        for _ in range(n_tables):
            rows = []
            for i in range(k):
                sd = rng.uniform(5, 15)
                base = rng.uniform(20, 80)
                se = sd * math.sqrt(2 / 100)
                rows.append({"label": f"v{i}", "means": [base, base + rng.gauss(0, se)],
                             "sds": [sd, sd], "ns": [100, 100]})
            r = table1_dispersion(rows, num_bootstrap=1, seed=0, design="parallel_rct")
            assert r["severity"] != "highly_suspicious", (
                f"fabrication-grade accusation against an honest k={k} table: "
                f"{r['explanation']}"
            )
            if r["severity"] == "suspicious":
                accused += 1
        assert accused / n_tables < 0.05, (
            f"k={k}: {accused}/{n_tables} honest tables accused; the exact null "
            "measured under 1%, so this is a regression in calibration"
        )

    def test_csf_finding_nothing_now_vetoes_escalation(self):
        """`correlation_veto` caught only csf's `indeterminate`; csf returning
        `consistent` -- a STRONGER no-finding -- did not veto. Closing that used
        to demote Fujii from a pinned true positive, which is why it waited."""
        r = table1_dispersion(FUJII_ROWS, num_bootstrap=1, seed=0,
                              design="parallel_rct", correlation=0.0)
        assert r["csf_cross_check"]["severity"] == "consistent"
        assert r["severity"] == "suspicious", "capped, not fabrication-grade"
        assert "does not reach a robust finding" in r["explanation"]

    def test_a_corroborated_finding_still_accuses(self):
        """Quarantine must not amount to switching the tool off: 18 rows, a
        stated design, and csf_test corroborating still reach fabrication grade."""
        r = table1_dispersion(STRONGLY_UNDER_DISPERSED, num_bootstrap=500, seed=0,
                              design="parallel_rct", correlation=0.5)
        assert r["severity"] == "highly_suspicious"
        assert r.get("quarantined", False) is False

    def test_a_consistent_verdict_passes_through_untouched(self):
        """Quarantine withholds ACCUSATIONS only -- it must never manufacture a
        refusal out of a clean result, which would be a different kind of lie."""
        random.seed(42)
        rows = [{"label": f"v{i}",
                 "means": [random.gauss(50, 5 / math.sqrt(30)),
                           random.gauss(50, 5 / math.sqrt(30))],
                 "sds": [5, 5], "ns": [30, 30]} for i in range(15)]
        r = table1_dispersion(rows, num_bootstrap=500, seed=0)
        assert r["severity"] == "consistent"
        assert r.get("quarantined", False) is False
        assert "severity_before_quarantine" not in r


class TestEdgeCases:
    def test_too_few_rows(self):
        result = table1_dispersion([{"means": [1, 2], "sds": [1, 1], "ns": [10, 10]}])
        assert result["severity"] == "indeterminate"

    def test_empty(self):
        result = table1_dispersion([])
        assert result["severity"] == "indeterminate"

    def test_invalid_row_recorded(self):
        rows = [
            {"means": [1, 2], "sds": [1, 1], "ns": [10, 10]},
            {"means": [1, 2], "sds": [1, 1], "ns": [10, 10]},
            {"foo": "bar"},  # invalid
        ]
        result = table1_dispersion(rows, num_bootstrap=200, seed=0)
        assert result["n_valid"] == 2
        assert len(result["errors"]) == 1



class TestUpperTailSimesGuard:
    """MEASURED FAILURE, 2026-08-21 apple_cider eval: age/weight/height at
    per-row p = 0.93/0.99/0.99 beside eight unremarkable biochemical rows.
    tau_hat = 1.44 with CI [0.20, 2.82], internal csf similarity_p = 0.19 --
    every whole-table statistic diluted the trio, the tool printed
    "consistent with random allocation", and the run published the exact
    reassurance the gold review exists to catch. The upper-tail Simes guard
    (0.057 on this data) withholds the all-clear and names csf_test."""

    APPLE_CIDER_TABLE1 = [
        {
            "label": "Age (years)",
            "means": [
                17.2,
                18.1,
                17.6,
                17.8
            ],
            "sds": [
                5.2,
                5.5,
                5.1,
                5.7
            ],
            "ns": [
                30,
                30,
                30,
                30
            ]
        },
        {
            "label": "Weight (kg)",
            "means": [
                79,
                79.3,
                77.2,
                79.1
            ],
            "sds": [
                27.1,
                28.5,
                27.2,
                28.6
            ],
            "ns": [
                30,
                30,
                30,
                30
            ]
        },
        {
            "label": "Height (cm)",
            "means": [
                157.4,
                158.6,
                157.1,
                156.9
            ],
            "sds": [
                20.1,
                22.2,
                20.8,
                21.4
            ],
            "ns": [
                30,
                30,
                30,
                30
            ]
        },
        {
            "label": "BMI (kg/m2)",
            "means": [
                30.6,
                30.2,
                30,
                30.7
            ],
            "sds": [
                3.1,
                2.8,
                3,
                3.2
            ],
            "ns": [
                30,
                30,
                30,
                30
            ]
        },
        {
            "label": "Waist (cm)",
            "means": [
                85.9,
                84.7,
                85.3,
                84.2
            ],
            "sds": [
                3.8,
                4.4,
                4.8,
                4.3
            ],
            "ns": [
                30,
                30,
                30,
                30
            ]
        },
        {
            "label": "Hip (cm)",
            "means": [
                106.4,
                105.8,
                105.1,
                106.6
            ],
            "sds": [
                3.5,
                3.4,
                3.9,
                3.7
            ],
            "ns": [
                30,
                30,
                30,
                30
            ]
        },
        {
            "label": "BFR (%)",
            "means": [
                29.8,
                28.1,
                30.4,
                29.1
            ],
            "sds": [
                6.7,
                5.5,
                6.3,
                5.8
            ],
            "ns": [
                30,
                30,
                30,
                30
            ]
        },
        {
            "label": "FBS (mg/dL)",
            "means": [
                120.1,
                118.9,
                119.9,
                113.6
            ],
            "sds": [
                10.9,
                13.1,
                7.2,
                12.5
            ],
            "ns": [
                30,
                30,
                30,
                30
            ]
        },
        {
            "label": "TG (mg/dL)",
            "means": [
                170.1,
                167.2,
                165.9,
                168.1
            ],
            "sds": [
                17.9,
                13.2,
                13.8,
                18.2
            ],
            "ns": [
                30,
                30,
                30,
                30
            ]
        },
        {
            "label": "TC (mg/dL)",
            "means": [
                176,
                173.6,
                176.9,
                178.5
            ],
            "sds": [
                13.1,
                16.3,
                11.1,
                11.5
            ],
            "ns": [
                30,
                30,
                30,
                30
            ]
        },
        {
            "label": "Gender",
            "counts": [
                [
                    12,
                    18
                ],
                [
                    10,
                    20
                ],
                [
                    11,
                    19
                ],
                [
                    13,
                    17
                ]
            ]
        }
    ]
    
    def test_the_measured_apple_cider_table_is_not_cleared(self):
        out = table1_dispersion(self.APPLE_CIDER_TABLE1,
                                design="parallel_rct", seed=0)
        assert out["severity"] == "indeterminate"
        assert out["upper_tail_simes_p"] < 0.10
        text = out["explanation"]
        assert "csf_test" in text and "NOT a clean bill of health" in text
        assert "Age (years)" in text and "Height (cm)" in text
        assert "consistent with random allocation" not in text

    def test_an_unremarkable_table_still_clears_without_reassurance(self):
        """Mid-range per-row p-values: verdict stays consistent, and the
        wording never asserts the reassurance rulebook rule 1 bans -- 'does
        not distinguish' is a statement about the test, not the trial."""
        rng = random.Random(7)
        rows = []
        for i in range(9):
            base = 20 + i
            # groups differing by a bit under one pooled SE: p in the broad
            # middle, neither uniform nor dispersed
            rows.append({"label": f"v{i}",
                         "means": [base, base + 0.35 + rng.random() * 0.3],
                         "sds": [2.0, 2.0], "ns": [40, 40]})
        out = table1_dispersion(rows, design="parallel_rct", seed=0)
        assert out["severity"] == "consistent", out["explanation"]
        assert "consistent with random allocation" not in out["explanation"]
        assert "does not distinguish" in out["explanation"]

    def test_the_guard_never_downgrades_an_accusation(self):
        """Uniformly extreme rows reach the tau/K-S branches; the Simes
        guard only replaces , never a firing verdict."""
        rows = [{"label": f"u{i}", "means": [10.0, 10.001],
                 "sds": [3.0, 3.0], "ns": [50, 50]} for i in range(12)]
        out = table1_dispersion(rows, design="parallel_rct", seed=0)
        assert out["severity"] in ("suspicious", "highly_suspicious",
                                   "indeterminate")
        assert out["severity"] != "consistent"
