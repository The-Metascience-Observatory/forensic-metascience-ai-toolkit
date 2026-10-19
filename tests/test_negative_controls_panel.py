"""Negative controls for the rest of the check panel.

`test_false_positive_rate.py` measures specificity for `grim_test` and
`grimmer_test`. The toolkit has a dozen more checks and NONE of them had a
negative control -- so their false-positive rate was unmeasured, on a toolkit
whose cardinal rule is that a false accusation is its worst output.

The 2026-09-01 audits found honest-paper accusations in five separate tools: a
percent CHANGE read as a share, a cluster trial read as one unit, a geometric
mean read as arithmetic, a bootstrap CI read as Wald, and a within-subjects d
read as between-groups. Each was found by a human reading code. A generator
finds that class by construction.

WHAT MAKES THESE CONTROLS RATHER THAN FIXTURES: every quantity is COMPUTED from
generated data, never typed. A percentage is `100 * k / n` at the printed
precision; a CI is the actual Wald interval of the generated estimate; a flow's
arms sum to its stage. An accusatory verdict on any of them is a false positive
by definition, with no adjudication needed.
"""

from __future__ import annotations

import pytest

from forensic_metascience_ai_toolkit.simulation import (
    BREAKERS,
    CLEAN_GENERATORS,
    screen_broken,
    screen_clean,
)

ACCUSATORY = ("suspicious", "highly_suspicious", "impossible")
SEEDS = range(2000, 2060)


class TestNoCleanCaseIsAccused:
    """The cardinal metric. There is no acceptable non-zero rate here: every
    input is correct by construction."""

    @pytest.mark.parametrize("tool", sorted(CLEAN_GENERATORS))
    def test_sixty_correct_cases_produce_no_accusation(self, tool):
        bad = []
        for seed in SEEDS:
            r = screen_clean(tool, seed)
            if r["severity"] in ACCUSATORY:
                bad.append(r)
        assert not bad, (
            f"{tool} accused {len(bad)} of {len(list(SEEDS))} "
            f"correct-by-construction cases. First: seed {bad[0]['seed']}, "
            f"inputs {bad[0]['inputs']}, {bad[0]['explanation']}")


class TestTheControlsActuallyReachTheirCheck:
    """A negative control that never reaches its check reports specificity it
    did not test, and looks exactly like a clean sweep.

    This is not hypothetical: `clean_flow`'s first version emitted `excluded`
    entries as PAIRS where the tool wants objects, so `check_flow_arithmetic`
    refused all 60 with "excluded[0] is not an object" and returned
    `indeterminate` every time. Zero false positives, zero information.
    """

    @pytest.mark.parametrize("tool", sorted(CLEAN_GENERATORS))
    def test_a_clean_case_reaches_a_real_verdict(self, tool):
        verdicts = {screen_clean(tool, s)["severity"] for s in list(SEEDS)[:10]}
        assert verdicts <= {"consistent"}, (
            f"{tool} returned {verdicts} on correct input; anything other than "
            "`consistent` means the control is not reaching the check")

    @pytest.mark.parametrize("tool", sorted(BREAKERS))
    def test_a_planted_defect_is_caught(self, tool):
        """The other direction. Together with the test above, this pins that
        the generator produces input the tool both accepts and discriminates
        on."""
        caught = sum(1 for s in SEEDS
                     if screen_broken(tool, s)["severity"] in ACCUSATORY)
        n = len(list(SEEDS))
        assert caught >= 0.9 * n, (
            f"{tool} caught only {caught}/{n} planted defects; either the "
            "breaker is not producing a real defect or the check has stopped "
            "discriminating")


class TestTheGeneratorsAreHonest:
    def test_every_generator_has_a_breaker(self):
        assert set(CLEAN_GENERATORS) == set(BREAKERS)

    def test_a_clean_case_and_its_broken_twin_differ(self):
        """A breaker that changes nothing would make the positive control pass
        for the wrong reason."""
        import random
        for tool, (gen, _) in CLEAN_GENERATORS.items():
            clean = gen(random.Random(2000))
            broken = BREAKERS[tool](gen(random.Random(2000)))
            assert clean != broken, f"{tool}: the breaker changed nothing"

    def test_the_generated_percentage_is_actually_correct(self):
        """Spot-check the construction claim itself rather than trusting it."""
        import random
        from forensic_metascience_ai_toolkit.simulation import clean_count_percent
        for seed in range(2000, 2020):
            kw = clean_count_percent(random.Random(seed))
            assert kw["percentage"] == pytest.approx(
                round(100.0 * kw["count"] / kw["n"], kw["decimals"]))

    def test_the_generated_interval_is_actually_wald(self):
        import math
        import random
        from forensic_metascience_ai_toolkit.simulation import clean_estimate_ci
        for seed in range(2000, 2020):
            kw = clean_estimate_ci(random.Random(seed))
            centre = math.sqrt(kw["ci_low"] * kw["ci_high"])
            assert centre == pytest.approx(kw["estimate"], rel=0.01)
