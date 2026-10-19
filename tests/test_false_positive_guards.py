"""Regression tests for the two highest-risk false-positive paths.

Both bugs fixed here produced *fabrication-grade* output (`severity: impossible`)
from ordinary, innocent reporting conventions. These tests exist to make sure
neither can come back.

Where R is available, the SPRITE cases are cross-checked against `rsprite2`,
the canonical implementation. IMPORTANT: the comparison must pin `m_prec` /
`sd_prec` explicitly -- `rsprite2` otherwise infers precision from the literal
(`4.0` reads as 0 decimals), which silently compares different questions.
"""
import math
import shutil
import subprocess

import pytest

from forensic_metascience_ai_toolkit.tools import debit_test, debit_test_batch, sprite_reconstruct
from forensic_metascience_ai_toolkit.tools.ttest import recalc_within_subjects_t

# Pre/post table from a real reporting pattern: every p reported as a threshold.
PRE, SD_PRE, POST, SD_POST, N = 120.0, 7.2, 105.0, 7.0, 30



# ---------------------------------------------------------------------------
# THE POPULATION-SD CONVENTION MOVED FROM `suspicious` TO `consistent` ON
# 2026-08-10. GREG:
#
#   "regarding the Population-SD convention, I changed my mind and want it
#    applied as well -- it would be inconsistent to do the truncation check but
#    not this."
#
# Every test below keeps its ORIGINAL THESIS, which was never "suspicious" --
# it was "NOT `impossible`, because a reporting convention is not fabrication".
# That thesis is now stated one rung lower, and the assertions say so directly:
# `!= "impossible"` where the point is the ceiling, and `== "consistent"` where
# the point is the exact verdict. The convention is still NAMED
# (`failure_mode`/`outcome` == "sd_convention", `sd_convention` == "population")
# and counted per paper, which is where the signal lives.
# ---------------------------------------------------------------------------

class TestThresholdPPValue:
    """A thresholded p ("p < .05") must never yield `impossible`.

    The recovered correlation is monotonically increasing in t, and a threshold
    p only lower-bounds t. Treating the bound as exact drove r to -15.0 and
    tripped the |r| > 1 == `impossible` branch.
    """

    @pytest.mark.parametrize("p", [0.05, 0.01, 0.001])
    def test_explicit_threshold_flag_is_indeterminate(self, p):
        r = recalc_within_subjects_t(PRE, SD_PRE, POST, SD_POST, N, p, p_is_threshold=True)
        assert r["severity"] == "indeterminate"
        assert r["recovered_correlation_is_lower_bound"] is True
        lo, hi = r["attainable_r_interval"]
        assert lo <= hi
        # The interval must reach into the valid range, which is why we cannot conclude.
        assert hi >= 1.0

    def test_the_r_above_one_branch_obeys_this_class_too(self):
        """The one path that escaped the rule in this class's own docstring.

        With UNEQUAL SDs the recovered lower bound can exceed 1, and that branch
        returned `impossible` -- while the SAME data reported with an EXACT p
        returned `highly_suspicious`. The ladder was inverted: a threshold only
        bounds t, so it is the WEAKER evidence, and it was drawing the STRONGER
        verdict. It also skipped `_valid_r_within_rounding`, so it ignored the
        printed precision of every input.

        Capped rather than merely softened: the recovery assumes a standard
        paired t-test read at a particular tail convention, and an assumed model
        may not reach `impossible` down any branch.
        """
        r = recalc_within_subjects_t(
            mean_pre=10.0, sd_pre=2.0, mean_post=10.2, sd_post=4.0, n=20,
            reported_p="<0.001", decimals_mean=1, decimals_sd=1)
        assert r["severity"] == "highly_suspicious"
        lo, _ = r["attainable_r_interval"]
        assert lo > 1.0, "the arithmetic itself is unchanged"

    def test_the_exact_p_reading_of_the_same_data_is_no_softer(self):
        """The inversion is the defect: stronger evidence must not draw a weaker
        verdict than the bound does."""
        args = dict(mean_pre=10.0, sd_pre=2.0, mean_post=10.2, sd_post=4.0,
                    n=20, decimals_mean=1, decimals_sd=1)
        exact = recalc_within_subjects_t(reported_p="0.0005", decimals_p=4, **args)
        threshold = recalc_within_subjects_t(reported_p="<0.001", **args)
        assert exact["severity"] == threshold["severity"] == "highly_suspicious"

    def test_rounding_still_rescues_the_threshold_branch(self):
        """Equal SDs put r = 1 inside the rounding box, so nothing is
        established and the verdict is a refusal."""
        r = recalc_within_subjects_t(
            mean_pre=10.0, sd_pre=2.0, mean_post=10.2, sd_post=2.0, n=20,
            reported_p="<0.001", decimals_mean=1, decimals_sd=1)
        assert r["severity"] == "indeterminate"

    @pytest.mark.parametrize("p", ["<0.05", "p<.001", "≤0.01", "p < 0.05"])
    def test_threshold_strings_are_auto_detected(self, p):
        r = recalc_within_subjects_t(PRE, SD_PRE, POST, SD_POST, N, p)
        assert r["p_is_threshold"] is True
        assert r["severity"] == "indeterminate"

    # p's chosen to be UNAMBIGUOUSLY exact: a bare 0.05/0.01/0.001 is now
    # refused as an ambiguous reading (see TestAStrippedInequality below), so
    # this case -- the severity CAP on a real exact-p violation -- has to be
    # exercised with values no paper prints as a threshold.
    @pytest.mark.parametrize("p", [0.0007, 0.0005])
    def test_exact_p_violation_never_escalates_to_impossible(self, p):
        """An exact-p |r|>1 is real tension, but convention explains it far more
        often than fabrication does. Cap at highly_suspicious."""
        r = recalc_within_subjects_t(PRE, SD_PRE, POST, SD_POST, N, p)
        assert r["severity"] == "highly_suspicious"
        assert r["severity"] != "impossible"


class TestAStrippedInequalityCannotManufactureAFinding:
    """`p<0.05` retyped as `0.05` used to become `highly_suspicious`.

    The tool always handled a DECLARED threshold correctly. What it could not
    see was a caller dropping the "<" on the way in:

        reported_p="<0.05"  -> indeterminate,     r interval [-80.22, 1.013]
        reported_p="0.05"   -> highly_suspicious, r interval [-90.59, -70.90]

    MEASURED: a sweep recorded the second interval for seven paired rows of
    `10.17116--jnevro20181185139`, six of which the paper printed as "p<0.05",
    and that became the review's headline finding against a real paper. It was
    retracted: recomputing the attainable p over every r in [-1, 1] gives
    [2.1e-31, 4.5e-11] for the MMSE row, so "p<0.05" was satisfied with room to
    spare and nothing had been established.

    The rule now: when the p handed in is exactly a conventional alpha, the
    finding must survive BOTH readings or it is not reported.
    """

    #: The six rows the paper printed as "p<0.05", as the sweep passed them.
    ROWS = [
        ("CRP",    14.2, 2.9,    5.5, 1.6),
        ("IL-8",   14.1, 0.5,   11.7, 1.5),
        ("IL-4",    4.7, 1.0,   10.4, 1.34),
        ("IgG",  1147.1, 63.3, 1035.7, 62.5),
        ("MMSE",  27.85, 0.2,  28.95, 0.17),
        ("Mattis", 21.65, 0.25, 23.2, 0.3),
    ]

    @pytest.mark.parametrize("label,m1,s1,m2,s2", ROWS)
    def test_the_retracted_rows_no_longer_accuse(self, label, m1, s1, m2, s2):
        r = recalc_within_subjects_t(m1, s1, m2, s2, 20, 0.05)
        assert r["severity"] == "indeterminate"
        assert r["failure_mode"] == "p_reading_ambiguous"

    @pytest.mark.parametrize("label,m1,s1,m2,s2", ROWS)
    def test_declaring_the_threshold_gives_the_same_answer(self, label, m1, s1, m2, s2):
        """The guard must agree with the honest call, not merely differ from it."""
        assert recalc_within_subjects_t(
            m1, s1, m2, s2, 20, "<0.05")["severity"] == "indeterminate"

    def test_a_finding_robust_to_both_readings_survives(self):
        """The guard refuses ambiguity, not evidence.

        Data extreme enough that even the bound reading keeps the whole
        attainable interval above 1 must still flag, or the fix would trade one
        error for another.
        """
        r = recalc_within_subjects_t(
            mean_pre=50.0, sd_pre=10.0, mean_post=51.0, sd_post=40.0,
            n=50, reported_p=0.001, p_tail="two")
        assert r["severity"] == "highly_suspicious"
        assert r.get("failure_mode") != "p_reading_ambiguous"

    def test_an_unambiguous_exact_p_is_untouched(self):
        r = recalc_within_subjects_t(PRE, SD_PRE, POST, SD_POST, N, 0.0007)
        assert r.get("failure_mode") != "p_reading_ambiguous"
        assert r["severity"] == "highly_suspicious"

    def test_the_refusal_says_how_to_settle_it(self):
        r = recalc_within_subjects_t(27.85, 0.2, 28.95, 0.17, 20, 0.05)
        assert "p_is_threshold=True" in r["explanation"]
        assert r["attainable_r_interval_as_bound"] is not None

    def test_consistent_case_still_consistent(self):
        r = recalc_within_subjects_t(PRE, SD_PRE, POST, SD_POST, N, 1e-6)
        assert r["severity"] == "consistent"
        assert -1 <= r["recovered_correlation"] <= 1

    def test_one_tailed_supported_and_validated(self):
        assert recalc_within_subjects_t(
            PRE, SD_PRE, POST, SD_POST, N, 1e-6, p_tail="one"
        )["severity"] == "consistent"
        assert recalc_within_subjects_t(
            PRE, SD_PRE, POST, SD_POST, N, 0.01, p_tail="sideways"
        )["severity"] == "indeterminate"


# (mean, sd, n, expected_outcome) at 2-dp precision, verified against rsprite2.
#
# rsprite2 checks the SAMPLE (Bessel, n-1) convention only, which is its
# default, so its "no solution" verdicts are correct FOR THAT CONVENTION.
# SPRITE now also tries the POPULATION (n) convention before declaring an
# impossibility, because reporting the population SD is a legitimate, common
# choice (numpy's std default) and calling it impossible is a false accusation.
# `(2.0, 0.8, 25)` moved from `no_solution_proven` to `sd_convention` for
# exactly that reason: a real sample exists -- 8x1, 9x2, 8x3, n=25, mean 2.0,
# population SD 0.80 exactly, sum of squares 116 -- so the old expectation was
# pinning a false accusation. The parity case below stays impossible because
# parity (Q must match the total mod 2) holds under BOTH conventions.
SPRITE_CASES = [
    # WAS `no_solution_proven`, AND THAT EXPECTATION WAS A FALSE ACCUSATION.
    # The comment said "parity: needs odd Q, total is even" -- true under the
    # ROUND-HALF window and false under truncation, which admits Q = 546 with
    # S = 120 (both even, parity satisfied). Constructed, 2026-08-27:
    #   [1,1,1,2,3,3, 4 x18, 5,5,6,7,7,7]  n=30, every value inside [1,7]
    #   S = 120, Q = 546, exact mean 4.000000, exact sample SD 1.508596
    # A truncating reporter prints that sample as "4.00, SD 1.50" -- this very
    # row -- and the toolkit called it impossible. An ordinary Likert table.
    (4.0, 1.5, 30, "rounding_convention"),
    (2.0, 0.8, 25, "sd_convention"),       # feasible under the population SD
    (3.5, 1.0, 20, "found"),
    (4.5, 2.0, 40, "found"),
    (3.0, 1.2, 50, "found"),
    (6.0, 1.0, 15, "found"),
]


class TestSpriteOutcomes:
    @pytest.mark.parametrize("mean,sd,n,expected", SPRITE_CASES)
    def test_outcome_matches_expectation(self, mean, sd, n, expected):
        r = sprite_reconstruct(mean, sd, n, scale_min=1, scale_max=7, num_samples=10,
                               decimals_mean=2, decimals_sd=2)
        assert r["outcome"] == expected

    @pytest.mark.parametrize("mean,sd,n,expected", SPRITE_CASES)
    def test_every_return_path_has_severity(self, mean, sd, n, expected):
        """CLAUDE.md invariant: every result dict carries a severity."""
        r = sprite_reconstruct(mean, sd, n, scale_min=1, scale_max=7, num_samples=10,
                               decimals_mean=2, decimals_sd=2)
        assert r.get("severity") in {
            "impossible", "highly_suspicious", "suspicious", "indeterminate", "consistent"
        }

    @pytest.mark.parametrize("mean,sd,n,expected", [c for c in SPRITE_CASES if c[3] == "found"])
    def test_found_distributions_actually_match(self, mean, sd, n, expected):
        import numpy as np
        r = sprite_reconstruct(mean, sd, n, scale_min=1, scale_max=7, num_samples=5,
                               decimals_mean=2, decimals_sd=2)
        for dist in r["example_distributions"]:
            a = np.array(dist)
            assert len(a) == n
            assert round(float(a.mean()), 2) == round(mean, 2)
            assert round(float(a.std(ddof=1)), 2) == round(sd, 2)
            assert a.min() >= 1 and a.max() <= 7

    def test_grim_failure_is_distinguished_from_search_failure(self):
        """A mean that fails GRIM must not be reported as a reconstruction failure."""
        r = sprite_reconstruct(5.51, 1.2, 30, scale_min=1, scale_max=7, num_samples=5,
                               decimals_mean=2, decimals_sd=2)
        assert r["outcome"] == "grim_fail"

    def test_search_exhaustion_is_never_evidence(self):
        """If the search gives up, severity must be indeterminate, not impossible."""
        r = sprite_reconstruct(
            3.5, 1.0, 20, scale_min=1, scale_max=7, num_samples=1, max_iterations=1,
            decimals_mean=2, decimals_sd=2
        )
        if r["outcome"] == "search_exhausted":
            assert r["severity"] == "indeterminate"


class TestDebitConventions:
    """DEBIT must not call a reporting convention fabrication.

    Reporting the population SD sqrt(p(1-p)) instead of the Bessel-corrected
    sample SD is common and legitimate. Flagging it `impossible` produced 66
    false accusations across a 450-case grid.
    """

    def test_population_convention_is_a_convention_not_an_accusation(self):
        r = debit_test(0.20, 0.40, 30)
        assert r["severity"] != "impossible"       # the original thesis
        assert r["severity"] == "consistent"       # and where it now sits
        assert r["sd_convention"] == "population"
        assert r["consistent_under_population_convention"] is True

    def test_sample_convention_still_consistent(self):
        r = debit_test(0.30, 0.46, 50)
        assert r["severity"] == "consistent"
        assert r["sd_convention"] == "sample"

    def test_genuinely_impossible_still_flagged(self):
        assert debit_test(0.30, 0.30, 50)["severity"] == "impossible"

    def test_no_population_row_is_ever_impossible(self):
        """The core regression: sweep the grid, assert zero false accusations."""
        offenders = []
        for n in (20, 25, 30, 40, 50, 64, 100):
            for k in range(1, n):
                p = k / n
                pop = round(math.sqrt(p * (1 - p)), 2)
                samp = round(math.sqrt(k * (n - k) / (n * (n - 1))), 2)
                if pop == samp:
                    continue
                r = debit_test(round(p, 2), pop, n)
                if r["severity"] == "impossible":
                    offenders.append((round(p, 2), pop, n))
        assert offenders == [], f"population-SD rows flagged impossible: {offenders[:5]}"

    def test_batch_does_not_escalate_on_a_single_row(self):
        """One impossible row in a 3-row table is noise, not a pattern."""
        rows = [
            {"mean": 0.30, "sd": 0.30, "n": 50, "decimals_mean": 2, "decimals_sd": 2},   # impossible
            {"mean": 0.30, "sd": 0.46, "n": 50, "decimals_mean": 2, "decimals_sd": 2},   # consistent
            {"mean": 0.50, "sd": 0.51, "n": 40, "decimals_mean": 2, "decimals_sd": 2},   # consistent
        ]
        assert debit_test_batch(rows)["severity"] == "suspicious"


def _rsprite2_available() -> bool:
    if not shutil.which("Rscript"):
        return False
    out = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("rsprite2", quietly=TRUE))'],
        capture_output=True, text=True,
    )
    return "TRUE" in out.stdout


@pytest.mark.skipif(not _rsprite2_available(), reason="R/rsprite2 not installed")
class TestAgainstRsprite2GroundTruth:
    @pytest.mark.parametrize("mean,sd,n,expected", SPRITE_CASES)
    def test_feasibility_agrees_with_rsprite2(self, mean, sd, n, expected):
        r_code = f"""
        suppressMessages(library(rsprite2))
        p <- tryCatch(set_parameters(mean={mean}, sd={sd}, n_obs={n}, min_val=1, max_val=7,
                                     m_prec=2, sd_prec=2),
                      error=function(e) NULL)
        if (is.null(p)) {{ cat("INFEASIBLE") }} else {{
          d <- tryCatch(find_possible_distribution(p), error=function(e) NULL)
          cat(if (!is.null(d) && !is.null(d$values)) "FEASIBLE" else "NO_SOLUTION")
        }}"""
        out = subprocess.run(["Rscript", "-e", r_code], capture_output=True, text=True)
        r_feasible = "FEASIBLE" in out.stdout and "INFEASIBLE" not in out.stdout
        py_feasible = sprite_reconstruct(
            mean, sd, n, scale_min=1, scale_max=7, num_samples=10,
            decimals_mean=2, decimals_sd=2,
        ).get("success", False)
        assert py_feasible == r_feasible, (
            f"disagreement with rsprite2 on mean={mean} sd={sd} n={n}: "
            f"python={py_feasible} rsprite2={r_feasible} (R said {out.stdout!r})"
        )


class TestBudgetTruncationIsLoud:
    """A sweep killed by the spend cap must never read as a complete review.

    Previously `is_error`/`error_subtype` were parsed and then never branched
    on, so a $1.50 cap produced a hollow findings.json behind a confident
    report. That is a false-NEGATIVE generator that also misstates coverage.
    """

    @staticmethod
    def _stage(**over):
        base = dict(cost_usd=1.0, input_tokens=1, output_tokens=2, wall_seconds=3.0,
                    return_code=0, is_error=False, error_subtype=None)
        base.update(over)
        return base

    def test_stage_meta_records_error_subtype(self):
        from forensic_metascience_ai_toolkit.agent import _stage_meta
        meta = _stage_meta(
            self._stage(is_error=True, return_code=1, error_subtype="error_max_budget_usd"),
            "opus",
        )
        assert meta["error_subtype"] == "error_max_budget_usd"
        assert meta["truncated_by_budget"] is True

    def test_clean_stage_is_not_marked_truncated(self):
        from forensic_metascience_ai_toolkit.agent import _stage_meta
        meta = _stage_meta(self._stage(), "opus")
        assert meta["truncated_by_budget"] is False
        assert meta["truncated_by_timeout"] is False
        assert meta["error_subtype"] is None

    def test_chi_squared_underclaim_p05_is_consistent(self):
        """A paper printing p<.05 (arriving as 0.05) against a tiny computed
        p is an under-claim, not a mismatch."""
        from forensic_metascience_ai_toolkit.tools.chi_squared import recalc_chi_squared
        r = recalc_chi_squared([[20, 5], [8, 30]], reported_p=0.05)
        assert r["severity"] == "consistent"

    def test_f_to_p_underclaim_p05_is_consistent(self):
        from forensic_metascience_ai_toolkit.tools.anova import recalc_f_to_p
        r = recalc_f_to_p(25.0, 2, 40, reported_p=0.05)
        assert r["severity"] == "consistent"

    def test_grimu_conventional_alpha_dual_read(self):
        from forensic_metascience_ai_toolkit.tools.grimu import grimu_check
        as_bound = grimu_check(8, 8, "<0.05")
        assert as_bound["severity"] in {"consistent", "indeterminate"}
        exact = grimu_check(8, 8, "0.05")
        if exact["severity"] in {"impossible", "suspicious"}:
            assert exact.get("failure_mode") == "p_reading_ambiguous" or (
                exact["severity"] == "indeterminate")

    def test_a_wall_clock_kill_is_timeout_not_budget(self):
        from forensic_metascience_ai_toolkit.agent import (
            _stage_hit_budget, _stage_hit_timeout, _stage_meta,
        )
        stage = self._stage(is_error=True, error_subtype="error_timeout",
                            current_tool="extract_pdf", tool_calls=7)
        assert _stage_hit_budget(stage) is False
        assert _stage_hit_timeout(stage) is True
        meta = _stage_meta(stage, "grok-4.6")
        assert meta["truncated_by_timeout"] is True
        assert meta["truncated_by_budget"] is False
        assert meta["current_tool"] == "extract_pdf"
        assert meta["tool_calls"] == 7

    def test_budget_detector_ignores_unrelated_errors(self):
        from forensic_metascience_ai_toolkit.agent import _stage_hit_budget
        assert _stage_hit_budget(self._stage(is_error=True, error_subtype="error_timeout")) is False

    def test_api_failure_is_not_recorded_as_success(self):
        """A stage that died on an API error must not be labelled "success".

        Verbatim from the eval run that broke: `is_error` true, `subtype`
        "success", `terminal_reason` "api_error", 0 tokens, 2.34s. Written out
        as `error_subtype: "success"` it read like a completed stage, so the
        failed scorecard looked committable.
        """
        from forensic_metascience_ai_toolkit.agent import _error_subtype
        assert _error_subtype({
            "is_error": True, "subtype": "success", "terminal_reason": "api_error",
        }) == "api_error"

    def test_real_subtypes_are_preserved(self):
        """The budget/timeout subtypes must survive -- _stage_hit_budget reads them."""
        from forensic_metascience_ai_toolkit.agent import _error_subtype, _stage_hit_budget
        for subtype in ("error_max_budget_usd", "error_timeout"):
            event = {"is_error": True, "subtype": subtype, "terminal_reason": "api_error"}
            assert _error_subtype(event) == subtype
        assert _stage_hit_budget(
            self._stage(is_error=True, error_subtype=_error_subtype(
                {"is_error": True, "subtype": "error_max_budget_usd"}))
        ) is True

    def test_missing_subtype_falls_back_to_terminal_reason(self):
        from forensic_metascience_ai_toolkit.agent import _error_subtype
        assert _error_subtype({"is_error": True, "terminal_reason": "api_error"}) == "api_error"
        assert _error_subtype({"is_error": True}) is None

    def test_repair_call_is_capped(self):
        """The recovery path from a budget stop must itself be capped."""
        import inspect
        from forensic_metascience_ai_toolkit import agent
        src = inspect.getsource(agent._repair_json)
        assert "--max-budget-usd" in src

class TestReportedPrecisionIsHonoured:
    """Precision must come from the reported literal, not a 2-dp default.

    Assuming 2 dp for a mean printed as "1.7" shrinks its rounding interval
    tenfold and rejects totals the paper genuinely permits. Measured false
    `impossible` rates before this fix: 3.24% (2 dp, n>100) and 26.6% (1 dp)
    for SPRITE, 17.1% for GRIMMER.
    """

    def test_real_dataset_is_not_called_impossible(self):
        """Eight 1s and twenty-two 2s, reported as M=1.7, SD=0.4."""
        import numpy as np
        from forensic_metascience_ai_toolkit.tools import grimmer_test
        data = np.array([1] * 8 + [2] * 22)
        assert round(float(data.mean()), 1) == 1.7
        r = sprite_reconstruct(1.7, 0.4, 30, scale_min=1, scale_max=5, num_samples=10)
        assert r["outcome"] != "no_solution_proven", "false accusation on genuine data"
        assert grimmer_test(1.7, 0.4, 30, scale_min=1, scale_max=5)["severity"] != "impossible"

    def test_precision_is_inferred_from_the_literal(self):
        from forensic_metascience_ai_toolkit.tools.sprite import _decimals_of, _grim_consistent_sums
        assert _decimals_of(1.7) == 1 and _decimals_of("1.70") == 2
        # One decimal admits three totals; two decimals admits one.
        assert len(_grim_consistent_sums(1.7, 30, 1)) > len(_grim_consistent_sums(1.70, 30, 2))

    def test_all_admissible_totals_are_tested(self):
        """Infeasibility must hold for EVERY total consistent with the mean."""
        from forensic_metascience_ai_toolkit.tools.sprite import _grim_consistent_sums
        sums = _grim_consistent_sums(1.7, 30, 1)
        assert len(sums) > 1, "multiple totals should be admissible at 1 dp"
        r = sprite_reconstruct(1.7, 0.4, 30, scale_min=1, scale_max=5, num_samples=10)
        assert r.get("success") is True


class TestGrimmerPopulationSdConvention:
    """GRIMMER branded a population-SD report as arithmetically impossible.

    Verified 2026-08-08: real Likert data [1,2,2,3,3,3,4,4,4,4], mean 3.0, whose
    POPULATION SD (numpy std default, Excel STDEVP) is exactly 1.0. GRIMMER
    computed its sum-of-squares window from the sample (Bessel, n-1) convention
    ONLY, so the population report fell outside the window and hit the bound-
    free `sd_granularity` branch -- `severity: impossible`, the strongest
    accusation the tool makes, against a numpy default.

    Same fix DEBIT already carries: try both conventions, and cap the
    population-only case at `suspicious` because a reporting-convention choice
    is not fabrication.
    """

    def test_population_sd_is_not_impossible(self):
        from forensic_metascience_ai_toolkit.tools.sd_checks import grimmer_test
        r = grimmer_test(mean=3.0, sd=1.0, n=10, scale_min=1, scale_max=7,
                         data_type="likert", bound_source="stated")
        assert r["severity"] != "impossible"
        assert r["severity"] == "consistent"
        # STILL NAMED. `consistent` must not mean the convention went unrecorded
        # -- the per-paper rate is built from exactly these fields.
        assert r["failure_mode"] == "sd_convention"
        assert "population" in r["failure_reason"].lower()

    def test_sample_sd_is_still_consistent(self):
        import numpy as np
        from forensic_metascience_ai_toolkit.tools.sd_checks import grimmer_test
        sd = round(float(np.std([1, 2, 2, 3, 3, 3, 4, 4, 4, 4], ddof=1)), 2)
        r = grimmer_test(mean=3.0, sd=sd, n=10, scale_min=1, scale_max=7,
                         data_type="likert", bound_source="stated")
        assert r["severity"] == "consistent"

    def test_a_genuinely_impossible_sd_stays_impossible(self):
        """The fix must not blunt the tool: an SD no convention admits is still
        impossible."""
        from forensic_metascience_ai_toolkit.tools.sd_checks import grimmer_test
        r = grimmer_test(mean=1.0, sd=5.0, n=10, scale_min=1, scale_max=7,
                         data_type="likert", bound_source="stated",
                         discreteness_source="stated")
        assert r["severity"] == "impossible"


class TestSpritePopulationSdConvention:
    """SPRITE proved a population-SD report "impossible" -- the same false
    accusation as GRIMMER, and the two corroborating each other on one cell
    would read to an editor as independent confirmation of fabrication.

    Verified 2026-08-08: [1,2,2,3,3,3,4,4,4,4], mean 3.0, population SD 1.0
    (numpy std default). Q=100 is the real sum of squares and is feasible only
    under the population (n) convention; SPRITE's window used the sample (n-1)
    convention alone -> outcome 'no_solution_proven', severity 'impossible'.
    """

    def test_population_sd_is_not_impossible(self):
        r = sprite_reconstruct(mean=3.0, sd=1.0, n=10, scale_min=1, scale_max=7,
                               data_type="likert", bound_source="stated")
        assert r["severity"] != "impossible"
        assert r["severity"] == "consistent"
        assert r["outcome"] == "sd_convention"
        assert r["sd_convention"] == "population"

    def test_it_agrees_with_grimmer_on_the_same_cell(self):
        """The two must not contradict each other -- corroboration is exactly
        what makes a false accusation persuasive."""
        from forensic_metascience_ai_toolkit.tools.sd_checks import grimmer_test
        args = dict(mean=3.0, sd=1.0, n=10, scale_min=1, scale_max=7,
                    data_type="likert", bound_source="stated")
        assert sprite_reconstruct(**args)["severity"] == "consistent"
        assert grimmer_test(**args)["severity"] == "consistent"

    def test_a_genuinely_impossible_sd_stays_impossible(self):
        r = sprite_reconstruct(mean=1.0, sd=5.0, n=10, scale_min=1, scale_max=7,
                               data_type="likert", bound_source="stated",
                               discreteness_source="stated")
        assert r["severity"] == "impossible"


class TestGrimTruncationConvention:
    """GRIM branded a truncated mean arithmetically impossible.

    Verified 2026-08-08: 16 threes + 14 fours, n=30, exact mean 104/30 =
    3.4666..., printed 3.46 by a reporter that truncates (SPSS's default, and
    one of scrutiny::grim's rounding options). Round-half GRIM rejects it
    (nearest achievable is 3.47) and returned severity 'impossible' -- against a
    real sample whose mean the paper simply floored.

    Same de-escalation as the SD-convention fix: consistent under the standard
    round-half reading -> consistent; consistent only under truncation ->
    suspicious (a reporting choice, not fabrication); neither -> impossible.
    """

    def test_a_truncated_mean_is_not_impossible(self):
        from forensic_metascience_ai_toolkit.tools.grim import grim_test
        r = grim_test(3.46, 30, scale_min=1, scale_max=7, decimals=2,
                      data_type="likert", bound_source="stated")
        # RECALIBRATED 2026-08-10 (Greg): a value rescued purely by the
        # TRUNCATION convention is `consistent`, so it can never enter the
        # findings as an accusation. The fact is carried by the convention
        # field and by the per-paper rate. See `grim.grim_test`.
        assert r["severity"] == "consistent"
        assert r["failure_mode"] == "rounding_convention"
        assert r["failure_mode"] == "rounding_convention"

    def test_the_round_half_neighbour_stays_consistent(self):
        from forensic_metascience_ai_toolkit.tools.grim import grim_test
        r = grim_test(3.47, 30, scale_min=1, scale_max=7, decimals=2,
                      data_type="likert", bound_source="stated")
        assert r["severity"] == "consistent"

    def test_a_mean_impossible_under_both_conventions_stays_impossible(self):
        """3.60 at n=2: exact means are S/2 (..3.0, 3.5, 4.0..). Round-half of
        3.60 lands on none; truncation [3.60, 3.70) contains no S/2 either."""
        from forensic_metascience_ai_toolkit.tools.grim import grim_test
        r = grim_test(3.60, 2, scale_min=1, scale_max=7, decimals=2,
                      data_type="likert", bound_source="stated",
                      discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "granularity"


class TestDebitSdUnitSlip:
    """DEBIT branded a percent-scale SD `impossible` while it guarded the mean.

    Verified 2026-08-08: a paper's "35% (SD 47.7%)" reaches debit_test as
    mean=0.35, sd=47.7 (the model normalised the mean but left the SD in
    percent). 47.7 exceeds the binary SD ceiling 0.5, so DEBIT returned
    `impossible` -- a false accusation from a unit slip. The mean-unit guard
    already treats an out-of-[0,1] mean as misapplication (indeterminate); the
    SD had no equivalent.

    The guard is NARROW on purpose: an impossible binary SD is exactly what
    DEBIT is for. Only the percent slip is reclassified, and its tell is that
    sd/100 equals the binary SD the mean implies. Regnerus 2012 (SD 0.75, mean
    0.01) lacks that tell -- 0.75/100 is nowhere near sqrt(0.01*0.99) -- so it
    stays impossible.
    """

    def test_a_percent_scale_sd_is_a_unit_slip_not_impossible(self):
        r = debit_test(mean=0.35, sd=47.7, n=100, data_type="binary")
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_a_genuinely_impossible_binary_sd_stays_impossible(self):
        """Regnerus 2012 -- the canonical DEBIT detection. Must not be blunted."""
        r = debit_test(mean=0.01, sd=0.75, n=1000, data_type="binary")
        assert r["severity"] == "impossible"

    def test_an_over_range_sd_that_is_not_a_clean_percent_slip_stays_impossible(self):
        r = debit_test(mean=0.30, sd=0.60, n=100, data_type="binary")
        assert r["severity"] == "impossible"


class TestGrimPercentageCannotAccuseOnAnUndeclaredPercentage:
    """A guard whose default is a substantive value is not a guard.

    `grim_percentage`'s `data_type` was flagged `guard=True` and the gate worked
    perfectly whenever it was reached -- 'unknown' and 'continuous' both refuse.
    It could not be reached. The default was 'proportion', so OMITTING the
    declaration handed the check the one value that lets it fire, and the call
    returned `impossible` -- the top of the ladder, reserved for bound-free
    arithmetic -- on the exact case the tool's own description names as the
    false-accusation example, "glucose fell 23.7%".

    Its sibling `grim_check` has always defaulted to 'unknown' and refused on
    the same omission. This is the fifth inert guard found in a week and they
    all look like this: documented, tested in isolation, unreachable from the
    surface that actually gets called.
    """

    @staticmethod
    def _call(**args):
        from forensic_metascience_ai_toolkit.registry import BY_NAME
        return BY_NAME["grim_percentage"].call(dict(args))

    def test_omitting_the_declaration_refuses(self):
        r = self._call(percentage=23.7, n=42)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_a_declared_share_still_fires(self):
        """The fix must not blunt the check -- only the undeclared call refuses."""
        # `decimals=1` is what the literal 23.7 shows. It used to ride on a
        # default of 1, which was right here by luck and wrong wherever a
        # paper printed a whole percentage.
        r = self._call(percentage=23.7, n=42, decimals=1,
                       data_type="proportion")
        assert r["severity"] == "impossible"

    def test_a_declared_continuous_percentage_refuses(self):
        r = self._call(percentage=23.7, n=42, data_type="continuous")
        assert r["applicable"] is False

    def test_it_matches_its_sibling_on_the_same_omission(self):
        """Two GRIM tools disagreeing about what an omitted data_type means is
        how this survived unnoticed."""
        from forensic_metascience_ai_toolkit.registry import BY_NAME
        mean_side = BY_NAME["grim_check"].call({"mean": 5.19, "n": 28, "decimals": 2})
        pct_side = self._call(percentage=23.7, n=42)
        assert mean_side["applicable"] is pct_side["applicable"] is False

    def test_the_default_is_not_a_substantive_value(self):
        """Pins the mechanism, not just the behaviour: if someone restores a
        real default the gate silently stops gating again."""
        from forensic_metascience_ai_toolkit.registry import BY_NAME
        p = next(p for p in BY_NAME["grim_percentage"].params if p.name == "data_type")
        assert p.guard is True
        assert p.default == "unknown"


class TestMcNemarIsADifferentStatistic:
    """A paired 2x2 -- the same subjects measured twice -- is tested with
    McNemar's `(b-c)^2/(b+c)` on the discordant cells, not with a Pearson
    chi-squared of independence. Nothing in the counts tells the two designs
    apart, so a McNemar table handed to `recalc_chi_squared` produced a
    confident mismatch against a paper that had done nothing wrong.

    MEASURED 2026-08-22 on 10.1111--j.2044-835x.2011.02046.x: called with
    `observed=[[11, 6], [6, 0]]` against the paper's McNemar chi2 = 9.09, it
    answered "matches NEITHER convention: Pearson gives 2.8651 and
    Yates-corrected gives 1.3270" and returned `suspicious`. It reached no
    report only because that paper's model chose not to file it.

    The guard does not depend on the caller declaring the design (the GRIM-U
    lesson: model memory is not a guard). McNemar is computed alongside on
    every 2x2 and entered into the same both-conventions matching, so a
    reported statistic that only McNemar explains is reported as explained.
    """

    #: 20 discordant one way, 5 the other: McNemar 9.00, corrected 7.84,
    #: against a Pearson of 27.47 -- far apart enough that no window confuses
    #: them.
    PAIRED = [[30, 20], [5, 45]]

    def test_a_genuine_mcnemar_report_is_not_accused(self):
        from forensic_metascience_ai_toolkit.tools.chi_squared import recalc_chi_squared
        r = recalc_chi_squared(self.PAIRED, reported_chi2=9.0)
        assert r["severity"] == "consistent"
        assert r["chi2_match_convention"] == "mcnemar"
        assert "PAIRED" in r["explanation"]

    def test_the_continuity_corrected_convention_is_tried_too(self):
        """R's `mcnemar.test` applies the correction BY DEFAULT, so a paper
        printing either value is following a mainstream default -- the same
        argument this module already makes for Pearson vs Yates."""
        from forensic_metascience_ai_toolkit.tools.chi_squared import recalc_chi_squared
        r = recalc_chi_squared(self.PAIRED, reported_chi2=7.84)
        assert r["severity"] == "consistent"
        assert r["chi2_match_convention"] == "mcnemar_cc"

    def test_an_independence_table_keeps_its_ordinary_label(self):
        """McNemar is tried LAST, so an ordinary 2x2 is unaffected."""
        from forensic_metascience_ai_toolkit.tools.chi_squared import recalc_chi_squared
        r = recalc_chi_squared(self.PAIRED, reported_chi2=27.47)
        assert r["severity"] == "consistent"
        assert r["chi2_match_convention"] == "pearson"

    def test_a_genuinely_unexplained_value_still_flags(self):
        """The guard must not become a universal excuse."""
        from forensic_metascience_ai_toolkit.tools.chi_squared import recalc_chi_squared
        r = recalc_chi_squared(self.PAIRED, reported_chi2=99.0)
        assert r["severity"] == "suspicious"
        assert r["chi2_match_convention"] is None
        assert "McNemar" in r["explanation"], \
            "a reader must see that the paired reading was considered"

    def test_paired_makes_mcnemar_the_headline(self):
        from forensic_metascience_ai_toolkit.tools.chi_squared import recalc_chi_squared
        r = recalc_chi_squared(self.PAIRED, paired=True)
        assert r["test_type"] == "McNemar"
        assert r["calculated_chi2"] == pytest.approx(9.0)
        assert r["df"] == 1

    def test_no_discordant_pairs_says_so_instead_of_falling_back(self):
        """b + c == 0 makes McNemar undefined. Silently answering with a test
        of independence would be answering a different question."""
        from forensic_metascience_ai_toolkit.tools.chi_squared import recalc_chi_squared
        r = recalc_chi_squared([[30, 0], [0, 45]], paired=True)
        assert "mcnemar_undefined" in r
        assert "calculated_chi2_mcnemar" not in r
