"""Specificity gate: the pipeline must not accuse honest papers.

Every fixture in `benchmarks/paper_reviews/fixtures/` expects `untrustworthy`, so the eval measures
sensitivity only and the FALSE-POSITIVE rate -- the error that actually matters
for an integrity tool -- was previously unmeasurable.

These negative controls are papers whose summary statistics are computed from
real integer samples, i.e. correct by construction. An accusatory severity on
any of them is a false positive by definition. Free, offline, deterministic.
"""
import pytest

from metascience_agent.simulation import (
    FLAW_KINDS,
    benchmark,
    generate_clean_paper,
    generate_flawed_paper,
    screen_paper,
)


class TestSpecificity:
    """The cardinal metric: never accuse an honest paper."""

    @pytest.mark.parametrize("seed", range(1000, 1040))
    def test_clean_paper_is_never_accused(self, seed):
        result = screen_paper(generate_clean_paper(seed))
        assert result["accused"] is False, (
            f"FALSE POSITIVE on a paper with correct statistics: "
            f"{result['accused_rows']} -> {result['per_row']}"
        )

    def test_specificity_is_perfect_across_the_benchmark(self):
        b = benchmark(n_clean=60, n_flawed_per_kind=5)
        assert b["false_positive_papers"] == 0, b["false_positive_detail"]
        assert b["specificity"] == 1.0

    @pytest.mark.parametrize("scale", [(1, 5), (1, 7), (0, 10), (1, 100)])
    def test_specificity_holds_across_scales(self, scale):
        lo, hi = scale
        for seed in range(2000, 2015):
            r = screen_paper(generate_clean_paper(seed, scale_min=lo, scale_max=hi))
            assert r["accused"] is False, f"FP on scale {scale}: {r['accused_rows']}"


class TestSensitivity:
    """Detection must not be zero -- specificity is trivial to achieve alone."""

    @pytest.mark.parametrize("kind", FLAW_KINDS)
    def test_injected_flaws_are_detected_at_all(self, kind):
        runs = [screen_paper(generate_flawed_paper(s, kind=kind)) for s in range(3000, 3015)]
        caught = sum(1 for r in runs if r["accused"])
        assert caught > 0, f"no {kind} flaw was ever detected -- the panel is inert"

    def test_impossible_sd_is_always_caught(self):
        """An SD exceeding what the scale can support is unambiguous."""
        runs = [
            screen_paper(generate_flawed_paper(s, kind="impossible_sd"))
            for s in range(3100, 3112)
        ]
        assert all(r["accused"] for r in runs)


def test_ground_truth_generator_is_self_consistent():
    """The negative controls must actually be truthful, or the gate is vacuous."""
    for seed in range(4000, 4010):
        for row in generate_clean_paper(seed).rows:
            assert row.reported_n == len(row.values)
            assert row.reported_mean == round(row.true_mean, row.decimals)
            assert row.reported_sd == round(row.true_sd, row.decimals)


class TestTheGeneratorInjectsFlawsThatAreActuallyThere:
    """A flaw that changes no printed number is not a flaw.

    Both mean-perturbing kinds used to produce them, and the benchmark counted
    the resulting no-ops as MISSES -- so a generator defect was being published
    as a property of the tools.

    MEASURED over seeds 3000-3099 before the fix:
      * `grim_violation` nudged by 1/(3n) and re-rounded. At n = 80 or 117 that
        is below the rounding resolution, so 23 of 100 "flawed" papers were
        numerically IDENTICAL to their clean twin. The reported sensitivity of
        ~75% was close to 1 minus that rate; corrected, it is 100%.
      * `transposed_digits` was not a transposition -- it copied the second-last
        digit over the last, so 4.61 became 4.66 rather than 4.16.
    """

    def test_a_transposition_actually_transposes(self):
        from metascience_agent.simulation import Row, inject_flaw
        import random
        row = Row(label="r", values=[1], scale_min=1, scale_max=7)
        row.reported_mean, row.reported_sd, row.reported_n = 4.61, 1.0, 30
        inject_flaw(row, "transposed_digits", random.Random(0))
        assert row.reported_mean == 4.16, "4.61 must transpose to 4.16, not 4.66"

    @pytest.mark.parametrize("kind", ["grim_violation", "transposed_digits"])
    def test_an_unchanged_row_is_recorded_as_no_flaw(self, kind):
        """The honest record. At n >= 100 every two-decimal mean is
        GRIM-attainable, so there is no detectable violation to inject, and
        saying so is what lets the benchmark exclude it rather than score it."""
        from metascience_agent.simulation import (generate_clean_paper,
                                                  generate_flawed_paper)
        for seed in range(3000, 3060):
            clean = generate_clean_paper(seed)
            flawed = generate_flawed_paper(seed, kind=kind)
            for c, f in zip(clean.rows, flawed.rows):
                unchanged = (abs(c.reported_mean - f.reported_mean) < 1e-12
                             and abs(c.reported_sd - f.reported_sd) < 1e-12)
                assert not (unchanged and f.flaw), (
                    f"seed {seed}: row {f.label} is unchanged but claims flaw={f.flaw}")

    def test_the_benchmark_excludes_undetectable_flaws_and_says_how_many(self):
        from metascience_agent.simulation import benchmark
        b = benchmark()
        for kind, s in b["sensitivity"].items():
            assert "undetectable" in s, f"{kind} must report what it excluded"
            assert s["total"] + s["undetectable"] == 12, kind
            if s["total"]:
                assert s["rate"] == s["caught"] / s["total"]

    def test_a_hit_requires_the_ACCUSED_row_to_be_the_INJECTED_row(self):
        """Crediting any accused row lets a false positive on a clean row of a
        flawed paper score as a detection -- the one arrangement that makes a
        tool look better the worse it behaves."""
        import inspect
        from metascience_agent import simulation
        src = inspect.getsource(simulation.benchmark)
        assert "flawed_rows &" in src or "flawed_rows.intersection" in src, (
            "benchmark must intersect the injected rows with the accused rows")
