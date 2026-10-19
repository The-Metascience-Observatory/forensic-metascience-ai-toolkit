"""Every archived call that BECOMES an accusation must be justified by name.

`evaluation/replay.py` re-runs an archived run's tool calls at HEAD and diffs
the verdicts. Once the model has chosen a tool and its arguments, everything
downstream is a pure function of them, so the deterministic half of the pipeline
can be measured against real calls on real papers for free.

WHY THIS IS A TEST AND NOT A COMMAND YOU REMEMBER TO RUN. On 2026-09-01 a commit
added `interval_method` to `check_estimate_ci` and applied it to the midpoint
test. The replay then showed four archived calls going consistent -> suspicious,
and the branch that fired was the RECOVERED-P check 250 lines away, which
reconstructs the standard error as `(ln hi - ln lo) / (2z)` -- the same Wald
assumption. Both branches looked right in isolation and the suite was green.
Reading would not have found it; replaying did.

THE RATCHET IS ONE-DIRECTIONAL AND DELIBERATELY SO. Verdicts moving toward
`consistent` or toward a refusal need no entry here: this codebase's cardinal
rule is that a false accusation is its worst output, so gaining an accusation is
the direction that has to be argued for. Relief is free.

MAINTENANCE. When a change makes a new archived call accusatory, do NOT edit the
count. Work out WHY, decide whether the new verdict is right, and add an entry
with the reason -- or fix the code. The entry is the argument, not the
permission.
"""

from __future__ import annotations

import collections

import pytest

from metascience_agent.evaluation import replay

CORPUS = "tests/fixtures/papers/high_value_pdfs_to_run_on"

#: tool -> (count, why this tool's flips are correct).
#: Keyed by TOOL rather than by call, because `seq` shifts whenever an archived
#: run is re-copied and a per-call key would churn without meaning.
JUSTIFIED: dict[str, tuple[int, str]] = {
    "stalt_check": (
        8,
        "TRUE POSITIVES the old code missed. Each is a paper reporting a "
        "threshold its own recomputed p does not meet -- `p < .001` against a "
        "calculated p of 0.0024, and in one case 0.0177. The arithmetic is not "
        "in doubt and the claim is the paper's own.",
    ),
    "check_estimate_ci": (
        4,
        "The recovered-p check inverts a WALD interval, and these archived "
        "calls declare no `interval_method`. Guarded in 6665ad9: a declared "
        "bootstrap/exact/profile interval now skips the check, and the "
        "undeclared case keeps its severity while naming the innocent reading. "
        "Undeclared behaviour is unchanged BY DESIGN -- two numbers cannot "
        "reveal how an interval was built -- so these four remain and are "
        "expected.",
    ),
}


@pytest.fixture(scope="module")
def flips():
    return replay.classify(replay.replay_corpus(CORPUS))["became_accusatory"]


class TestNoUnjustifiedAccusationAppears:
    def test_every_tool_that_gained_an_accusation_is_justified(self, flips):
        by_tool = collections.Counter(f.get("tool") for f in flips)
        unexplained = sorted(set(by_tool) - set(JUSTIFIED))
        assert not unexplained, (
            "these tools now return an accusation on an archived call where "
            f"they did not before: {unexplained}\n"
            "Work out WHY before adding them here. A new accusation on a real "
            "paper is the direction this codebase treats as its worst failure."
        )

    def test_no_tool_gained_more_than_it_is_allowed(self, flips):
        by_tool = collections.Counter(f.get("tool") for f in flips)
        grew = {t: (n, JUSTIFIED[t][0]) for t, n in by_tool.items()
                if t in JUSTIFIED and n > JUSTIFIED[t][0]}
        assert not grew, (
            f"more archived calls became accusatory than are justified: {grew}\n"
            "Each entry in JUSTIFIED carries a reason; a higher count needs a "
            "reason too, or a fix."
        )

    def test_the_ratchet_is_not_vacuous(self, flips):
        """A ratchet that measures nothing passes forever. This asserts the
        replay actually ran and actually found the known flips."""
        assert len(flips) >= 10, (
            f"only {len(flips)} flips replayed; the corpus or the archive may "
            "not be present, in which case this file is proving nothing")

    def test_every_justification_is_substantive(self):
        for tool, (count, why) in JUSTIFIED.items():
            assert count > 0, tool
            assert len(why) > 60, f"{tool}: give a real reason, not a label"


class TestReliefNeedsNoJustification:
    """The other direction is free, and the asymmetry is the point."""

    def test_relief_is_reported_but_not_gated(self):
        out = replay.classify(replay.replay_corpus(CORPUS))
        assert isinstance(out.get("relieved"), list)
        # No assertion on the count: a fix that relieves more accusations is
        # exactly what this project wants, and must never fail a test.


class TestTheRatchetCanFail:
    """Proven, not assumed. A guard whose failure path is never exercised is
    indistinguishable from one that cannot fire."""

    @staticmethod
    def _unexplained(flips):
        by_tool = collections.Counter(f.get("tool") for f in flips)
        return sorted(set(by_tool) - set(JUSTIFIED))

    @staticmethod
    def _grew(flips):
        by_tool = collections.Counter(f.get("tool") for f in flips)
        return {t: n for t, n in by_tool.items()
                if t in JUSTIFIED and n > JUSTIFIED[t][0]}

    def test_a_new_tool_gaining_an_accusation_is_caught(self):
        planted = [{"tool": "grim_check", "before": {"severity": "consistent"},
                    "after": {"severity": "impossible"}}]
        assert self._unexplained(planted) == ["grim_check"]

    def test_a_justified_tool_gaining_MORE_is_caught(self):
        planted = [{"tool": "stalt_check"}] * (JUSTIFIED["stalt_check"][0] + 1)
        assert self._grew(planted)

    def test_the_expected_shape_passes(self):
        planted = ([{"tool": "stalt_check"}] * JUSTIFIED["stalt_check"][0]
                   + [{"tool": "check_estimate_ci"}]
                   * JUSTIFIED["check_estimate_ci"][0])
        assert not self._unexplained(planted)
        assert not self._grew(planted)

    def test_fewer_flips_than_justified_is_not_a_failure(self):
        """A fix that removes a justified flip must not fail the ratchet --
        only GAINING accusations is gated."""
        assert not self._grew([{"tool": "stalt_check"}])
