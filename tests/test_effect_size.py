"""check_effect_plausibility / cohens_d: refusals, the severity cap, and
benchmark integrity.

This tool judges whether a result is BELIEVABLE rather than whether it is
arithmetically consistent, so a false positive here cannot be dismissed by
re-checking arithmetic -- the cap and the refusals are the whole safety story.
"""

import math

import pytest

from metascience_agent.tools.effect_size import (
    FIELD_BENCHMARKS,
    check_effect_plausibility,
    cohens_d,
)

NAN = float("nan")
INF = float("inf")


class TestNonfiniteRefusal:
    """A NaN/inf is OUR artefact (a failed extraction, a divide-by-zero), never
    the paper's claim. The registry gate protects the MCP surface, but the raw
    function is reachable directly (CLI, tool-to-tool, stage 2) and used to
    return `consistent` for d = NaN -- a false all-clear stated in the grammar
    of a verdict about the paper ("|d| = nan is within the usual range")."""

    def test_nan_d_declines(self):
        r = check_effect_plausibility(d=NAN, field="education")
        assert r["severity"] == "indeterminate"

    def test_inf_d_declines(self):
        # inf used to read `suspicious` -- a claim about the paper from our own
        # overflow.
        r = check_effect_plausibility(d=INF, field="education")
        assert r["severity"] == "indeterminate"

    def test_nan_mean_declines(self):
        assert cohens_d(NAN, 1.0, 10, 0.0, 1.0, 10)["severity"] == "indeterminate"

    def test_inf_sd_declines(self):
        # This used to return d = 0.0 at severity `consistent`: an infinity
        # swallowed into a specific, fabricated effect size of exactly zero.
        r = cohens_d(10.0, INF, 10, 8.0, 1.0, 10)
        assert r["severity"] == "indeterminate"
        assert r.get("d") is None

    def test_nan_group_stat_through_plausibility(self):
        r = check_effect_plausibility(mean1=NAN, sd1=1.0, n1=10,
                                      mean2=0.0, sd2=1.0, n2=10,
                                      field="education")
        assert r["severity"] == "indeterminate"


class TestSeverityCeiling:
    """The card says an effect size can be improbable but never impossible.
    Verify the cap holds by execution on every band of every field, including
    absurd magnitudes, rather than trusting the docstring."""

    def test_never_above_suspicious(self):
        fields = list(FIELD_BENCHMARKS) + ["unknown_field", None]
        for f in fields:
            for d in (-5.0, -1.0, 0.0, 0.3, 0.7, 1.1, 1.9, 2.5, 10.0, 1e6):
                sev = check_effect_plausibility(d=d, field=f)["severity"]
                assert sev in ("consistent", "indeterminate", "suspicious"), \
                    (f, d, sev)


class TestGuards:
    def test_unknown_field_refuses_and_lists_options(self):
        r = check_effect_plausibility(d=0.5, field="astrology")
        assert r["severity"] == "indeterminate"
        assert "social_psychology" in r["explanation"]

    def test_no_field_REPORTS_rather_than_refusing(self):
        """REVERSED 2026-08-16. Greg: "Having the effect size tools have any a
        priori expectations for what constitutes a large effect size is not
        especially helpful... insofar as they are unrealistically large, that is
        something that the human can judge themselves after seeing all the effect
        sizes laid out."

        Omitting `field` is now the ORDINARY case, not a misconfiguration. The
        tool states the value and makes no magnitude claim -- which is not an
        all-clear about the paper, it is a refusal to opine about size."""
        r = check_effect_plausibility(d=2.2)
        assert r["severity"] == "consistent"
        assert "2.200" in r["explanation"] and "not judged" in r["explanation"]
        assert "benchmark" not in r

    def test_reporting_without_a_field_is_not_a_clean_bill(self):
        """`consistent` here means "no magnitude claim", and the explanation has
        to say so or a reader will read silence as endorsement."""
        r = check_effect_plausibility(d=2.2)
        assert "Reported, not judged" in r["explanation"]


class TestInternalConsistencyNeedsNoBenchmark:
    """The check Greg actually wants: does the effect size a paper PRINTED match
    the one its own means, SDs and ns imply? No comparison class, no opinion
    about what large means -- and it is the shape that catches a mistyped effect
    size, as in Mazar 2023 (printed d = .050 against means implying ~.38)."""

    STATS = dict(mean1=4.44, sd1=1.6, n1=150, mean2=3.83, sd2=1.6, n2=150)

    def test_a_mismatch_is_flagged(self):
        r = check_effect_plausibility(reported_d=0.050, **self.STATS)
        assert r["severity"] == "suspicious"
        assert "One of the two printed values is wrong" in r["explanation"]
        assert r["recomputed_d"] > 0.3

    def test_a_match_is_consistent(self):
        r = check_effect_plausibility(reported_d=0.38, **self.STATS)
        assert r["severity"] == "consistent"

    def test_the_tolerance_follows_the_printed_precision(self):
        """A d given to two decimals cannot be held to more than half a unit in
        its last place; holding it tighter would flag ordinary rounding."""
        loose = check_effect_plausibility(reported_d=0.4, **self.STATS)
        tight = check_effect_plausibility(reported_d=0.380, **self.STATS)
        assert loose["tolerance"] > tight["tolerance"]

    def test_it_needs_no_field_at_all(self):
        r = check_effect_plausibility(reported_d=0.050, **self.STATS)
        assert r.get("field") is None and "benchmark" not in r


class TestEveryEffectSizeCarriesAnInterval:
    """GREG, 2026-08-16, on the anatomy section: "This is the ideal place to
    report estimated effect sizes (and CIs)." A point estimate invites exactly
    the eyeballing the CI exists to replace."""

    def test_cohens_d_returns_a_ci(self):
        r = cohens_d(10.0, 2.0, 30, 12.0, 2.0, 30)
        assert r["ci95_d"] and r["ci95_d"][0] < r["d"] < r["ci95_d"][1]

    def test_a_small_study_gets_an_interval_spanning_zero(self):
        """The whole point: d = -1.0 from six per group is not the same claim as
        d = -1.0 from thirty, and only the interval shows it."""
        small = cohens_d(10.0, 2.0, 6, 12.0, 2.0, 6)
        assert small["ci95_d"][0] < 0 < small["ci95_d"][1]

    def test_the_interval_is_labelled_an_estimate(self):
        r = cohens_d(10.0, 2.0, 30, 12.0, 2.0, 30)
        assert "estimate" in r["ci95_method"]

    def test_small_n_refuses(self):
        assert cohens_d(10.0, 1.0, 1, 8.0, 1.0, 10)["severity"] == "indeterminate"

    def test_negative_sd_refuses(self):
        assert cohens_d(10.0, -1.0, 5, 8.0, 1.0, 5)["severity"] == "indeterminate"

    def test_both_zero_sds_refuse(self):
        assert cohens_d(10.0, 0.0, 5, 8.0, 0.0, 5)["severity"] == "indeterminate"

    def test_missing_group_stats_refuse(self):
        r = check_effect_plausibility(mean1=10.0, sd1=1.0, n1=10,
                                      field="education")
        assert r["severity"] == "indeterminate"


class TestArithmetic:
    def test_cohens_d_hand_checked(self):
        # Pooled SD of (2, 2) at equal n is 2; (10 - 8) / 2 = 1.
        r = cohens_d(10.0, 2.0, 20, 8.0, 2.0, 20)
        assert r["d"] == pytest.approx(1.0)
        assert r["hedges_correction_j"] == pytest.approx(1 - 3 / (4 * 38 - 1))
        assert r["hedges_g"] == pytest.approx(1.0 * (1 - 3 / (4 * 38 - 1)))

    def test_unequal_group_sizes(self):
        # pooled_var = (9*4 + 29*9) / 38 = 297/38; d = 2 / sqrt(297/38)
        r = cohens_d(10.0, 2.0, 10, 8.0, 3.0, 30)
        assert r["d"] == pytest.approx(2.0 / (297.0 / 38.0) ** 0.5)

    def test_confounds_named_in_the_output_not_only_the_card(self):
        """The three ordinary explanations (SEM-as-SD, waitlist comparator,
        units mismatch) must appear in the tool's own explanation, where a
        reader of the finding sees them -- not only in the integrity card."""
        r = check_effect_plausibility(d=3.5, field="psychotherapy")
        assert r["severity"] == "suspicious"
        for word in ("SEM", "waitlist", "units"):
            assert word in r["explanation"], word
        assert "NOT evidence of misconduct" in r["explanation"]


class TestBenchmarkIntegrity:
    def test_social_psychology_p95_matches_its_source(self):
        """Lovakov & Agadullina (2021), Table 1: Cohen's d 95th percentile is
        1.30 (verified against the preprint, osf.io/download/2epc4/). The
        module shipped 1.2, which branded |d| in [1.2, 1.30) as 'at or above
        the field's 95th percentile' -- a mis-citation of our own source in
        the accusing direction."""
        assert FIELD_BENCHMARKS["social_psychology"]["p95"] == pytest.approx(1.30)

    def test_every_benchmark_declares_provenance(self):
        """The module header promises 'EVERY entry names its source'. An entry
        must now also say whether its NUMBERS are traceable to a published
        table ('cited') or are an informal estimate ('uncited_estimate'), so
        an unfalsifiable standard cannot pose as a citation."""
        for name, b in FIELD_BENCHMARKS.items():
            assert b.get("provenance") in ("cited", "uncited_estimate"), name

    def test_uncited_benchmark_is_disclosed_in_the_result(self):
        r = check_effect_plausibility(d=3.5, field="psychotherapy")
        assert r["benchmark_provenance"] == "uncited_estimate"
        assert "benchmark_caveat" in r

    def test_cited_benchmark_carries_no_caveat(self):
        r = check_effect_plausibility(d=0.35, field="social_psychology")
        assert r["benchmark_provenance"] == "cited"
        assert "benchmark_caveat" not in r

    def test_verdicts_unchanged_at_the_pinned_bands(self):
        """Pin current calibration: these are judgement calls that belong to a
        human, so the tests freeze them rather than deciding them."""
        assert check_effect_plausibility(d=0.35, field="social_psychology")["severity"] == "consistent"
        assert check_effect_plausibility(d=3.5, field="psychotherapy")["severity"] == "suspicious"
        assert check_effect_plausibility(d=0.6, field="medicine_rct")["severity"] == "indeterminate"


class TestTheBadBenchmarkIsWithdrawnRatherThanDeleted:
    """#167: `psychology_general` set its median at d = 0.40, taken from the
    Open Science Collaboration (2015) mean original effect of r = .40 -- a
    CORRELATION. As a Cohen's d that is ~0.87, so the row compared reported
    effects against a threshold less than half what its own source implies and
    flagged ordinary psychology effects as large. That is a false-accusation
    source, and the tool's own registry description had said so for days while
    the row stayed live.

    Withdrawn rather than silently deleted: a standard that vanishes is
    indistinguishable from a typo, and the next person re-adds it.
    """

    ARGS = dict(mean1=5.2, sd1=1.1, n1=40, mean2=4.6, sd2=1.2, n2=40)

    def test_the_bad_row_is_gone_from_the_live_table(self):
        from metascience_agent.tools.effect_size import FIELD_BENCHMARKS
        assert "psychology_general" not in FIELD_BENCHMARKS

    def test_naming_it_returns_a_diagnosis_not_unknown_field(self):
        from metascience_agent.tools.effect_size import check_effect_plausibility
        r = check_effect_plausibility(field="psychology_general", **self.ARGS)
        assert r["severity"] == "indeterminate"
        assert r.get("benchmark_withdrawn") == "psychology_general"
        assert "withdrawn" in r["explanation"].lower()
        assert "r = .40" in r["explanation"], "say WHY, or it reads as a typo"

    def test_the_effect_size_is_still_reported(self):
        """A withdrawn benchmark limits the comparison, never the value."""
        from metascience_agent.tools.effect_size import check_effect_plausibility
        r = check_effect_plausibility(field="psychology_general", **self.ARGS)
        assert "d = 0.5" in r["explanation"] and "95% CI" in r["explanation"]

    def test_every_surviving_benchmark_declares_its_provenance(self):
        from metascience_agent.tools.effect_size import FIELD_BENCHMARKS
        for name, row in FIELD_BENCHMARKS.items():
            assert row.get("provenance") in ("cited", "uncited_estimate"), name
            assert row.get("source"), name

    def test_no_benchmark_median_is_below_a_quarter_of_a_sd(self):
        """The withdrawn row's defect in a form that generalises: a median that
        low turns the ordinary into the exceptional. Nothing plausible in these
        literatures sits under d = 0.25."""
        from metascience_agent.tools.effect_size import FIELD_BENCHMARKS
        for name, row in FIELD_BENCHMARKS.items():
            assert row["median"] >= 0.25, f"{name} median {row['median']} will over-flag"
            assert row["median"] < row["p75"] < row["p95"], f"{name} percentiles disordered"


class TestPairedDInterval:
    """d_av = d_z * sqrt(2*(1-r)), and papers reporting d_z rarely report r.

    The discipline is the one `recalc_within_subjects_t` applies to a
    thresholded p: when an input is a bound rather than a value, report the
    attainable range and refuse to pick a point inside it.
    """

    def test_it_returns_d_rm_not_d_av_and_says_so(self):
        """THE TEST THAT WAS MISSING, and the reason the mislabel shipped.

        `dz*sqrt(2(1-r))` is Lakens (2013) eq. 8 -- d_rm. It equals d_av ONLY
        when the pre and post SDs are equal, and the original regression test
        fixed sd1 == sd2, which is precisely that condition. Measured against
        300,000 simulated pairs per cell, the error against true d_av is 0.2%
        at equal SDs, 29.3% at sd2/sd1 = 2, and 44.5% at 3.

        Nothing here can re-run the simulation cheaply, so the guard is on the
        NAMING: the tool must not offer a key called d_av, and must say that
        d_av needs a ratio it does not take.
        """
        from metascience_agent.tools.effect_size import paired_d_interval as P
        out = P(dz=0.89)
        assert not [k for k in out if k.startswith("d_av")], (
            "an output key named d_av names a quantity this tool cannot compute")
        assert "d_rm_low" in out and "d_rm_high" in out
        assert "d_av" in out["note"] and "SD ratio" in out["note"]

    def test_the_registry_card_does_not_state_the_inverse(self):
        """The card asserted 'Unequal SDs make d_av the quantity this returns'
        -- the exact inverse -- and that card is published to the report."""
        from metascience_agent import registry as R
        card = " ".join(R.BY_NAME["paired_d_interval"].assumptions)
        assert "Lakens 2013" in card
        assert "NOT d_av" in card

    def test_the_direction_is_not_inverted(self):
        """d_av SHRINKS as r rises. effectcheck 0.7.7 divides where it should
        multiply and so reports 2.82 where the truth is 0.28."""
        from metascience_agent.tools.effect_size import paired_d_interval as P
        lo = P(dz=0.891, r=0.95)["d_rm"]
        hi = P(dz=0.891, r=0.1)["d_rm"]
        assert lo < hi
        assert abs(lo - 0.891 * math.sqrt(2 * 0.05)) < 1e-9
        assert lo < 0.3 and hi > 1.1

    def test_an_unreported_correlation_yields_an_interval_not_a_point(self):
        from metascience_agent.tools.effect_size import paired_d_interval as P
        r = P(dz=0.89)
        assert r["r_is_reported"] is False
        assert r["d_rm_low"] < r["d_rm_high"]
        assert "d_rm" not in r, "a point estimate must not be offered at all"
        assert r["ratio_high_to_low"] > 3

    def test_a_reported_correlation_determines_it(self):
        from metascience_agent.tools.effect_size import paired_d_interval as P
        r = P(dz=0.89, r=0.5)
        assert r["r_is_reported"] is True
        assert r["d_rm_low"] == r["d_rm_high"] == r["d_rm"]
        assert r["interval_width"] == 0.0

    def test_dz_can_be_derived_from_t_and_n(self):
        from metascience_agent.tools.effect_size import paired_d_interval as P
        assert abs(P(t=6.3, n=50)["dz"] - 6.3 / math.sqrt(50)) < 1e-12

    def test_it_never_accuses(self):
        """Descriptive by evidence class: a wide interval is a fact about the
        reporting, not about the work."""
        from metascience_agent.tools.effect_size import paired_d_interval as P
        for kwargs in ({"dz": 0.89}, {"dz": 5.0}, {"dz": 0.1, "r": 0.99}):
            assert P(**kwargs)["severity"] == "indeterminate"

    @pytest.mark.parametrize("kwargs", [
        {"t": 6.3},                    # n missing
        {},                            # nothing at all
        {"dz": 0.5, "r": 1.0},         # r at the boundary
        {"dz": 0.5, "r": -1.5},        # r out of range
        {"t": 6.3, "n": 1},            # n too small
    ])
    def test_bad_input_is_a_structured_refusal_not_an_exception(self, kwargs):
        from metascience_agent.tools.effect_size import paired_d_interval as P
        out = P(**kwargs)
        assert "error" in out and out["severity"] == "indeterminate"

    def test_it_points_at_the_better_tool_when_one_applies(self):
        from metascience_agent.tools.effect_size import paired_d_interval as P
        assert "recalc_within_subjects_t" in P(dz=0.89)["note"]
