"""Tests for heuristic flags."""

import pytest

from metascience_agent.tools.heuristics import flag_round_n, flag_uninformative_stat


class TestFlagRoundN:
    def test_the_heathers_signature_is_suspicious_not_highly(self):
        """Round Ns are a DESCRIPTIVE prompt, capped at `suspicious`.

        This used to assert `highly_suspicious` for [100,200,300,400] -- but the
        rulebook lists "suspiciously round Ns" as its own example of `suspicious`
        (rule 8: weak signals that escalate only on co-occurrence), and
        required_n gives exactly 100/200/300/400 for a four-study program at
        d=0.4/0.281/0.229/0.198, so an honest program produces this exact list.
        The old expectation was itself the false accusation.
        """
        result = flag_round_n([100, 200, 300, 400])
        assert result["severity"] == "suspicious"
        assert result["all_divisible_by_strong"] is True

    def test_all_multiples_of_50_only_suspicious(self):
        result = flag_round_n([50, 150, 250])  # multiples of 50, not all of 100
        assert result["severity"] == "suspicious"
        assert result["all_divisible_by_moderate"] is True
        assert result["all_divisible_by_strong"] is False

    def test_one_breaks_pattern(self):
        result = flag_round_n([100, 200, 213])
        assert result["severity"] == "consistent"

    def test_realistic_random_ns(self):
        result = flag_round_n([47, 52, 49])
        assert result["severity"] == "consistent"

    def test_a_single_round_n_declines_to_judge(self):
        # A single round total is what recruit-to-target looks like; the old
        # code emitted `suspicious` while its own explanation admitted "weak
        # signal". Too little to distinguish a signature from a design target.
        result = flag_round_n([300])
        assert result["severity"] == "indeterminate"

    def test_an_honest_two_arm_target_is_not_accused(self):
        """[100, 100] is a two-sample t powered at d=0.4 (required_n = 100/arm),
        not a fabrication signature: too few, and not distinct."""
        assert flag_round_n([100, 100])["severity"] == "indeterminate"

    def test_empty(self):
        result = flag_round_n([])
        assert result["severity"] == "indeterminate"

    def test_breakdown_per_n(self):
        result = flag_round_n([100, 250])
        # 100 is divisible by both moduli; 250 is divisible by 50 only.
        b = result["breakdown"]
        assert b[0]["divisible_by_strong"] is True
        assert b[1]["divisible_by_strong"] is False
        assert b[1]["divisible_by_moderate"] is True


class TestFlagRoundNGarbageInputs:
    """A sample size is a positive whole number. Anything else in `ns` is OUR
    extraction artefact, and the old code either crashed on it or -- worse --
    int()-truncated it into a round number and then flagged the roundness it
    had just manufactured."""

    def test_fractional_ns_are_refused_not_rounded_into_a_flag(self):
        # int(100.7) == 100: the old code flagged [100.7, 200.3, 300.1] as
        # "All 3 reported sample sizes are multiples of 100" -- a `suspicious`
        # verdict about values the paper never printed.
        r = flag_round_n([100.7, 200.3, 300.1])
        assert r["severity"] == "indeterminate"

    def test_integral_floats_are_fine(self):
        # JSON numbers can arrive as floats; 100.0 IS the integer 100.
        r = flag_round_n([100.0, 200.0, 300.0])
        assert r["severity"] == "suspicious"

    def test_zero_n_is_refused(self):
        # 0 % 50 == 0, so n=0 counted as "round" and helped flag [0, 50, 100].
        assert flag_round_n([0, 50, 100])["severity"] == "indeterminate"

    def test_negative_ns_are_refused(self):
        # [-100, -200, -300] used to read `suspicious`.
        assert flag_round_n([-100, -200, -300])["severity"] == "indeterminate"

    def test_nan_declines_instead_of_raising(self):
        assert flag_round_n([float("nan")])["severity"] == "indeterminate"

    def test_inf_declines_instead_of_raising(self):
        assert flag_round_n([float("inf")])["severity"] == "indeterminate"

    def test_zero_modulus_declines_instead_of_raising(self):
        r = flag_round_n([100, 200, 300], moderate_modulus=0)
        assert r["severity"] == "indeterminate"

    def test_ceiling_is_suspicious_everywhere(self):
        for ns in ([100, 200, 300], [50, 150, 250], [100], [], [96],
                   [1000, 500, 200], [100, 100]):
            assert flag_round_n(ns)["severity"] in (
                "consistent", "indeterminate", "suspicious"), ns


class TestFlagUninformative:
    """Heathers §"Uninformative statistics" — Cheng 2009 example."""

    def test_three_identical_values_flagged_at_flag_grade_only(self):
        # All three groups reported as 1.60 (0.07), n=30. Reported p=0.687.
        # Even at the exact corner of the truncation box (Heathers' own
        # procedure: means maximally spread, SDs minimal) a one-way ANOVA
        # cannot reach 0.687 -- so the mismatch is real and worth flagging.
        # But Heathers' verdict on this whole category is "not necessarily an
        # error" and "not an error in its own right ... it can be regarded as
        # a flag", and the reported p here is nowhere near significance, so
        # nothing about SIGNIFICANCE is over-claimed: the likeliest cause is a
        # different or adjusted test than a plain one-way ANOVA. This used to
        # read `highly_suspicious` ("the reported significance exceeds what
        # the statistics support" -- about a p of 0.687!). A flag tool's
        # ceiling is `suspicious`; rivets_anova owns the accusation-grade
        # reported-p check.
        result = flag_uninformative_stat(
            means=[1.60, 1.60, 1.60],
            sds=[0.07, 0.07, 0.07],
            ns=[30, 30, 30],
            reported_p=0.687,
            decimals_mean=2, decimals_sd=2,
            num_samples=2000, seed=0,
        )
        assert result["severity"] == "suspicious"
        assert result["reported_p_in_range"] is False
        assert result["reported_p_overclaims"] is True
        # The assumption that licenses the flag must be disclosed in the
        # output a reader sees, not only in the integrity card.
        assert "one-way ANOVA" in result["explanation"]

    def test_clearly_distinct_groups_consistent(self):
        # Three well-separated means, narrow SDs. p should be tiny across the
        # entire truncation interval → not uninformative.
        result = flag_uninformative_stat(
            means=[1.00, 5.00, 9.00],
            sds=[0.10, 0.10, 0.10],
            ns=[30, 30, 30],
            reported_p=1e-50,
            decimals_mean=2, decimals_sd=2,
            num_samples=500, seed=0,
        )
        # The implied p-range is essentially [0, ~0]; not uninformative.
        assert result["severity"] in ("consistent", "highly_suspicious")
        # If reported_p is unrealistically tiny but matches, the function will
        # pass; we just check is_uninformative was computed.
        assert result["is_uninformative"] is not None

    def test_p_range_straddles_threshold(self):
        # Borderline case: small effect, modest n, default decimals → p might
        # straddle 0.05.
        result = flag_uninformative_stat(
            means=[5.00, 5.05, 5.10],
            sds=[0.10, 0.10, 0.10],
            ns=[20, 20, 20],
            decimals_mean=2, decimals_sd=2,
            num_samples=1000, seed=0,
        )
        # Just check the function reports the straddling status sensibly.
        assert "straddles_significance_threshold" in result

    def test_a_threshold_p_below_the_achievable_range_is_not_accused(self):
        """An honest strongly-significant ANOVA reported as 'p < .001' (the agent
        passes the bound 0.001) has an achievable p far below 0.001, so 0.001 is
        LARGER than the achievable maximum -- an under-claim, the conservative
        direction. The old point-in-range test flagged this at fabrication grade
        on every such honest result."""
        r = flag_uninformative_stat(
            means=[1.00, 2.00, 3.00], sds=[0.50, 0.50, 0.50], ns=[20, 20, 20],
            reported_p=0.001, seed=0,
        )
        assert r["severity"] != "highly_suspicious"
        assert r["severity"] == "consistent"

    def test_the_nested_rivets_payload_carries_no_accusation(self):
        """The reported p used to be FORWARDED to rivets_anova, whose own
        two-sided range check branded the honest 'p < .001'-as-bound case
        `highly_suspicious` ("UNREACHABLE") inside `underlying_rivets` --
        while the outer severity said `consistent`. The model reads the whole
        payload, so the retraction and the accusation shipped together."""
        r = flag_uninformative_stat(
            means=[1.00, 2.00, 3.00], sds=[0.50, 0.50, 0.50], ns=[20, 20, 20],
            reported_p=0.001, seed=0,
        )
        ur = r["underlying_rivets"]
        assert ur["severity"] in ("consistent", "indeterminate")
        assert "UNREACHABLE" not in str(ur.get("explanation", ""))

    def test_an_over_claim_below_the_achievable_range_is_still_flagged(self):
        """The reported p is SMALLER than any the printed means/SDs can produce
        (barely-separated means, but p = .001 claimed): a real over-claim of
        significance. Flagged -- at the flag ceiling `suspicious`, with the
        one-way-ANOVA assumption disclosed and rivets_anova named for the
        accusation-grade treatment. (Previously `highly_suspicious`, which is
        a finding, and Heathers is explicit these are flags.)"""
        r = flag_uninformative_stat(
            means=[5.00, 5.05, 5.10], sds=[1.0, 1.0, 1.0], ns=[20, 20, 20],
            reported_p=0.001, decimals_p=3, seed=0,
        )
        assert r["severity"] == "suspicious"
        assert r["reported_p_overclaims"] is True
        assert "rivets_anova" in r["explanation"]

    def test_a_corner_achievable_p_is_not_branded_an_over_claim(self):
        """THE house failure pattern, demonstrated on this tool 2026-08-09:
        means [1.60]*3, sds [0.07]*3, ns [150]*3, reported p = 0.35. At the
        exact corner of the truncation box (means 1.595/1.595/1.605, SDs
        0.065 -- Heathers' own maximise-spread/minimise-SD procedure) a
        one-way ANOVA gives p = 0.307, so 0.35 IS achievable. But the p-range
        came from 3,000 Monte Carlo draws, which never visit the corner
        (sampled minimum 0.366), and the tool declared the reported p
        'SMALLER than any p the printed means/SDs can produce' at
        `highly_suspicious` -- OUR sampling shortfall in the grammar of a
        fabrication claim about the paper. The p-range is now corner-exact:
        F is maximised at a vertex of the means box with all SDs at their
        lower bound, so the achievable minimum is enumerated, not sampled."""
        r = flag_uninformative_stat(
            means=[1.60, 1.60, 1.60], sds=[0.07, 0.07, 0.07],
            ns=[150, 150, 150], reported_p=0.35, seed=0,
        )
        assert r["severity"] != "highly_suspicious"
        assert r["reported_p_overclaims"] is False
        assert r["p_min"] <= 0.35
        assert "SMALLER than any p" not in r["explanation"]

    def test_reported_p_outside_zero_one_is_refused(self):
        """A 'p' of 1.5 is not a p-value -- it is our mis-parse (a percentage,
        a test statistic). The old code compared it anyway and emitted a note
        about the paper."""
        r = flag_uninformative_stat(
            means=[5.00, 5.10, 5.20], sds=[0.30, 0.30, 0.30], ns=[25, 25, 25],
            reported_p=1.5, seed=0,
        )
        assert r["severity"] == "indeterminate"

    def test_reported_p_nan_is_refused(self):
        r = flag_uninformative_stat(
            means=[5.00, 5.10, 5.20], sds=[0.30, 0.30, 0.30], ns=[25, 25, 25],
            reported_p=float("nan"), seed=0,
        )
        assert r["severity"] == "indeterminate"

    def test_ceiling_is_suspicious_on_every_path(self):
        """Heathers: these are FLAGS, never findings. Verified by execution
        across the branches (straddle, wide range, over-claim, under-claim,
        consistent, guards)."""
        cases = [
            dict(means=[1.60, 1.60, 1.60], sds=[0.07, 0.07, 0.07],
                 ns=[30, 30, 30], reported_p=0.687, num_samples=500),
            dict(means=[5.00, 5.05, 5.10], sds=[1.0, 1.0, 1.0],
                 ns=[20, 20, 20], reported_p=0.001, num_samples=500),
            dict(means=[5.00, 5.05, 5.10], sds=[0.10, 0.10, 0.10],
                 ns=[20, 20, 20], num_samples=500),
            dict(means=[1.00, 5.00, 9.00], sds=[0.10, 0.10, 0.10],
                 ns=[30, 30, 30], reported_p=1e-50, num_samples=200),
            dict(means=[1.00, 2.00, 3.00], sds=[0.50, 0.50, 0.50],
                 ns=[20, 20, 20], reported_p=0.001, num_samples=500),
            dict(means=[1.0, 2.0], sds=[1.0, 1.0], ns=[10, 10],
                 num_samples=200),
        ]
        for kw in cases:
            sev = flag_uninformative_stat(seed=0, **kw)["severity"]
            assert sev in ("consistent", "indeterminate", "suspicious"), (kw, sev)

    def test_printed_rounding_of_the_reported_p_is_tolerated(self):
        # A reported p just past the achievable max by less than its own printed
        # half-width must not be flagged.
        base = flag_uninformative_stat(
            means=[5.00, 5.10, 5.20], sds=[0.30, 0.30, 0.30], ns=[25, 25, 25],
            decimals_p=3, seed=0,
        )
        p_max = base["p_max"]
        r = flag_uninformative_stat(
            means=[5.00, 5.10, 5.20], sds=[0.30, 0.30, 0.30], ns=[25, 25, 25],
            reported_p=round(p_max + 0.0004, 3), decimals_p=3, seed=0,
        )
        assert r["severity"] != "highly_suspicious"
