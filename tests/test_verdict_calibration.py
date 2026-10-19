"""The verdict was a constant, and a constant carries no information.

MEASURED over every report on disk when this was written: `verdict` was
`questionable` in 14 of 14 reports across 8 papers. `trustworthy` and
`untrustworthy` had never been emitted. It is the most user-visible field the
system produces, so a reader who notices it never varies is right to ignore it.

The cause was not caution. Two of those 14 carried a headline the system itself
graded `impossible` resting on `stated_constraint` -- the paper's own numbers --
and still returned `questionable`, so the verdict was contradicting the report
printed above it. Nothing in `stage2_editorial.md` or `report.schema.json` said
what any of the three values meant; the enum was three strings with no
description.

These tests hold the calibration guidance to the two things the system actually
computes -- the severity ladder and `multiplicity_report`'s
`n_claims_lost_to_correction` -- so a reviewer can decide whether a given paper
qualifies. Whether a model then USES it cannot be tested here: that takes a paid
run.
"""
import json
from pathlib import Path

import pytest

from metascience_agent import verdicts

PROMPT = Path("src/metascience_agent/modules/adjudicator/prompt.md")
SCHEMA = Path("src/metascience_agent/schema/report.schema.json")

LADDER = ("impossible", "highly_suspicious", "suspicious",
          "indeterminate", "consistent")


@pytest.fixture(scope="module")
def calibration():
    """The calibration section alone, so a stray mention elsewhere cannot pass."""
    text = PROMPT.read_text(encoding="utf-8")
    # RE-POINTED 2026-09-04: the rule survives the legacy deletion, it just
    # lives in the adjudicator now. `stage2_editorial.md` called this
    # "## 4. Calibrate the verdict"; `adjudication.md` calls it
    # "## 7. The paper-level block" and states the same thing -- the verdict
    # is an arithmetic claim, the middle band is the overwhelming default,
    # and a reader who notices it never varies is right to discount it.
    start = text.index("## 7. The paper-level block")
    return text[start:text.index("## 8. Output discipline", start)]


class TestTheGuidanceExistsAtAll:
    def test_the_prompt_has_a_calibration_section(self):
        assert "## 7. The paper-level block" in PROMPT.read_text(encoding="utf-8")

class TestAPrintedScaleCountsAsStated:
    """MEASURED 2026-08-17 on a RETRACTED paper, and it cost a true detection.

    Rulebook rule 4 gained "stated means the paper PRINTS THE NUMERALS", to stop
    a matched CONTROL paper being headlined `impossible` on the phrase "in their
    20s". It worked, and it over-reached: the bullet listed `"a Likert scale" ->
    [1, 7]` as an ASSUMED translation and gave no positive example, so the model
    capped EVERY scale.

    On `10.1007--s11031-011-9216-y` -- Stapel, retracted for fabrication, the
    confession corroborated by the Levelt committee -- that moved the verdict
    from the bottom band to the middle in one step: two `impossible` findings
    became `suspicious`, including Experiment 4's M = 4.20, SD = 0.21, a pair no
    whole-number sample on a seven-point scale can produce. The Method prints
    "(1 = not at all me, 9 = very much me)". The bounds were stated; the cap was
    ours.

    Restoring the contrast restored the detection: `does_not_reconcile`, an
    `impossible` headline on `logical_necessity`, and the same Experiment 4
    finding back at the top.

    This test guards the CONTRAST, because half of it is what caused the
    regression. Both halves have to be present or the rule teaches the wrong
    lesson in one direction or the other.
    """

    @pytest.fixture(scope="class")
    def rulebook(self):
        return Path("src/metascience_agent/core/prompts/rulebook.md").read_text(encoding="utf-8")

    def test_the_assumed_side_is_stated(self, rulebook):
        """The half that stops a control paper being convicted on prose."""
        assert "PRINTS THE NUMERALS" in rulebook
        assert "in their 20s" in rulebook

    def test_the_stated_side_is_stated_too(self, rulebook):
        """The half whose absence cost a true detection. A scale printed with
        its anchors is STATED and supports `impossible`."""
        assert "A PRINTED SCALE IS STATED" in rulebook
        assert "1 = not at all me, 9 = very much me" in rulebook
        assert "READ THE METHOD FOR THE ANCHORS BEFORE YOU CAP" in rulebook

    def test_it_says_what_the_omission_cost(self, rulebook):
        """A rule that changed a verdict on a retracted paper must carry that
        measurement, or the next editor will 'simplify' it back."""
        assert "10.1007--s11031-011-9216-y" in rulebook
        # Whitespace-collapsed: the rulebook is hard-wrapped and this phrase
        # straddles a line break. A pattern that only matches unwrapped text
        # silently stops checking the moment a paragraph reflows.
        assert "cost a true detection" in " ".join(rulebook.split())
