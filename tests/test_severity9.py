"""
Pins for severity9.py, the one 1-9 severity source of truth (findings_v2 R1).

These are deliberately literal: the ladder, the maps and every cap are pinned
by VALUE, so any change here is a conscious act (and, per CHANGELOG.md, a
MINOR bump -- two reviews across a changed ladder are not comparable).
Every clamp guard has a known-positive (LESSONS #4: a guard that cannot fire
reads as though it had passed).
"""

from __future__ import annotations

import inspect
import json
import re

import pytest

from forensic_metascience_ai_toolkit import severity9
from forensic_metascience_ai_toolkit.severity9 import (
    ACCUSATORY_MIN,
    AGENT_CODE_CAP,
    FAST_SCREEN_CAP,
    FIVE_TO_NINE,
    LEVELS,
    MODEL_KNOWLEDGE_CAP,
    MODEL_READING_CAP,
    OUTCOME_FROM_FIVE,
    QUARANTINE_CAP,
    RUBRIC_QUESTION,
    SEVERITY9_COLORS,
    as_json,
    clamp_provisional,
    rubric_markdown,
)

# The tool-layer 5-enum, as literal strings ON PURPOSE: severity9 must not
# import tools/severity.py, and neither may its test route the contract
# through that module -- the strings ARE the shared surface.
FIVE_ENUM = (
    "impossible",
    "highly_suspicious",
    "suspicious",
    "indeterminate",
    "consistent",
)

EXPECTED_SLUGS = {
    1: "trivial",
    2: "minor",
    3: "notable",
    4: "local_flaw",
    5: "conclusions_affected",
    6: "unreliable",
    7: "fatal_error",
    8: "misconduct",
    9: "extreme_misconduct",
}


# ---------------------------------------------------------------------------
# The ladder
# ---------------------------------------------------------------------------


def test_ladder_has_exactly_nine_rungs_keyed_1_to_9():
    assert sorted(LEVELS) == list(range(1, 10))


def test_slugs_are_pinned():
    assert {n: level.slug for n, level in LEVELS.items()} == EXPECTED_SLUGS


def test_correction_outcomes_are_pinned():
    # The spec table in docs/specs/findings_v2.md section 7, verbatim intent.
    assert {n: level.correction_outcome for n, level in LEVELS.items()} == {
        1: "no formal correction",
        2: "erratum if needed",
        3: "localized correction/clarification",
        4: "public correction (corrigendum)",
        5: "corrigendum or partial retraction",
        6: "expression of concern; retraction candidate",
        7: "retraction (honest error)",
        8: "retraction (misconduct)",
        9: "retraction, sanctions",
    }


def test_every_rung_has_a_substantive_label_and_rubric():
    for n, level in LEVELS.items():
        assert level.label.strip(), f"level {n} has an empty label"
        # One real paragraph each, not a placeholder.
        assert len(level.finding_rubric) >= 120, (
            f"level {n} rubric is too short to answer the per-finding "
            f"question: {level.finding_rubric!r}"
        )


def test_every_rung_has_a_table_sized_web_summary():
    # The public ladder page renders this in one cell; the rubric is far too
    # long for that, which is why the two are separate fields.
    for n, level in LEVELS.items():
        assert level.web_summary.strip(), f"level {n} has no web_summary"
        assert len(level.web_summary) <= 90, (
            f"level {n} web_summary is too long for a table cell "
            f"({len(level.web_summary)} chars): {level.web_summary!r}"
        )


def test_boundary_tests_point_at_the_adjacent_rungs():
    """Every rung says how to escalate and de-escalate, and names the right
    neighbour. A boundary pointing at the wrong rung reads as guidance while
    guiding nowhere (LESSONS #4), so the neighbour is checked, not just the
    presence of a line."""
    for n, level in LEVELS.items():
        directions = {}
        for test in level.boundaries:
            m = re.match(r"^(Down|Up) to (\d) if: \S", test)
            assert m, f"level {n} boundary is malformed: {test!r}"
            directions[m.group(1)] = int(m.group(2))
        if n > 1:
            assert directions.get("Down") == n - 1, (
                f"level {n} must de-escalate to {n - 1}, got {directions}"
            )
        else:
            assert "Down" not in directions, "level 1 has nothing below it"
        if n < 9:
            assert directions.get("Up") == n + 1, (
                f"level {n} must escalate to {n + 1}, got {directions}"
            )
        else:
            assert "Up" not in directions, "level 9 has nothing above it"


# ---------------------------------------------------------------------------
# Maps
# ---------------------------------------------------------------------------


def test_five_to_nine_is_pinned():
    assert FIVE_TO_NINE == {
        "suspicious": 3,
        "highly_suspicious": 4,
        "impossible": 5,
    }


def test_outcome_from_five_is_total_over_the_five_enum():
    assert set(OUTCOME_FROM_FIVE) == set(FIVE_ENUM)
    assert OUTCOME_FROM_FIVE["consistent"] == "pass"
    assert OUTCOME_FROM_FIVE["indeterminate"] == "undecided"
    for value in ("suspicious", "highly_suspicious", "impossible"):
        assert OUTCOME_FROM_FIVE[value] == "problem"


def test_five_to_nine_covers_exactly_the_problem_outcomes():
    # A 5-enum value maps to a rung iff it maps to a problem; pass/undecided
    # rows get null severity, so they must NOT appear in FIVE_TO_NINE.
    problems = {k for k, v in OUTCOME_FROM_FIVE.items() if v == "problem"}
    assert set(FIVE_TO_NINE) == problems


# ---------------------------------------------------------------------------
# Caps: every constant pinned by value
# ---------------------------------------------------------------------------


def test_scalar_caps_are_pinned():
    assert AGENT_CODE_CAP == 4
    assert FAST_SCREEN_CAP == 4
    assert MODEL_KNOWLEDGE_CAP == 3
    assert MODEL_READING_CAP == 3
    assert QUARANTINE_CAP == 3
    assert ACCUSATORY_MIN == 3


def test_no_ceiling_constants_exist():
    """v1.14.0: the ladder has no absolute ceiling. Every role may write any
    rung 1-9; only evidence-CHANNEL caps remain. A reintroduced ceiling
    constant is a regression, not a safety feature, until Dan says otherwise."""
    from forensic_metascience_ai_toolkit import severity9
    for name in ("PIPELINE_MAX", "ADJUDICATOR_MAX_DEFAULT",
                 "ADJUDICATOR_MAX_MANIPULATION", "PROVISIONAL_CAP"):
        assert not hasattr(severity9, name), name


def test_ladder_version_is_three():
    from forensic_metascience_ai_toolkit.severity9 import LADDER_VERSION
    assert LADDER_VERSION == "3"


# ---------------------------------------------------------------------------
# clamp_provisional: a known-positive for EVERY cap, and a known-negative for
# the ceiling that no longer exists
# ---------------------------------------------------------------------------


def test_uncapped_channel_keeps_nine():
    assert clamp_provisional(9) == 9
    assert clamp_provisional(9, computed_by="registry_tool",
                             producer="tool_expert",
                             technique_is_tool=True) == 9
    assert clamp_provisional(9, computed_by="model_reading",
                             producer="science_error") == 9


@pytest.mark.parametrize("kwargs,cap", [
    ({"computed_by": "agent_code"}, AGENT_CODE_CAP),
    ({"computed_by": "model_knowledge"}, MODEL_KNOWLEDGE_CAP),
    ({"computed_by": "model_reading", "technique_is_tool": True},
     MODEL_READING_CAP),
    ({"producer": "fast_screen"}, FAST_SCREEN_CAP),
    ({"quarantined": True}, QUARANTINE_CAP),
])
def test_channel_caps_still_fire_from_nine(kwargs, cap):
    assert clamp_provisional(9, **kwargs) == cap


def test_below_cap_severity_passes_through_unchanged():
    assert clamp_provisional(2, computed_by="agent_code") == 2
    assert clamp_provisional(1, quarantined=True) == 1


def test_agent_code_cap_fires():
    assert clamp_provisional(5, computed_by="agent_code") == 4


def test_model_knowledge_cap_fires():
    # basis="model_knowledge" travels through the evidence-channel slot.
    assert clamp_provisional(5, computed_by="model_knowledge") == 3


def test_other_computed_by_values_do_not_cap():
    assert clamp_provisional(5, computed_by="registry_tool") == 5
    assert clamp_provisional(5, computed_by="model_reading") == 5


def test_fast_screen_cap_fires():
    assert clamp_provisional(5, producer="fast_screen") == 4


def test_other_producers_do_not_cap():
    assert clamp_provisional(5, producer="tool_expert") == 5


def test_quarantine_cap_fires():
    assert clamp_provisional(5, quarantined=True) == 3


def test_caps_compose_by_min():
    # The spec's composition example: quarantined agent_code is
    # min(4, 3) == 3.
    assert clamp_provisional(9, quarantined=True, computed_by="agent_code") == 3
    # fast_screen + model_knowledge: min(4, 3) == 3.
    assert clamp_provisional(
        9, producer="fast_screen", computed_by="model_knowledge") == 3


@pytest.mark.parametrize("bad", [0, 10, -3, "5", 4.0, True, None])
def test_out_of_range_or_non_int_severity_raises(bad):
    with pytest.raises(ValueError):
        clamp_provisional(bad)


# ---------------------------------------------------------------------------
# rubric_markdown
# ---------------------------------------------------------------------------


def test_rubric_contains_the_question_verbatim():
    assert RUBRIC_QUESTION == (
        "If this one finding were confirmed, and it were the only problem "
        "in the paper, what would the journal have to do about it?"
    )
    assert RUBRIC_QUESTION in rubric_markdown()


def test_rubric_contains_all_nine_slugs_and_rungs():
    md = rubric_markdown()
    for n, level in LEVELS.items():
        assert f"`{level.slug}`" in md, f"slug for level {n} missing"
        assert f"Level {n} " in md


def test_rubric_emits_every_boundary_test():
    # The boundaries are the whole point of the rewrite; a rung whose tests
    # never reach the prompt is guidance written for nobody.
    md = rubric_markdown()
    for n, level in LEVELS.items():
        for test in level.boundaries:
            assert f"- {test}" in md, (
                f"level {n} boundary missing from the rendered rubric: "
                f"{test!r}"
            )


def test_rubric_has_no_composition_rules_and_no_ceiling_language():
    """v1.14.0: the composition rules and every "never yours"/"human's call"
    sentence were stripped from the prompts. The ladder and its question
    are the whole instruction."""
    md = rubric_markdown()
    assert "Composition rules" not in md
    assert "rarely exceed 5" not in md
    assert "human's call" not in md
    assert "never assigned by this pipeline" not in md
    assert "never machine-assigned" not in md


# ---------------------------------------------------------------------------
# as_json
# ---------------------------------------------------------------------------


def test_as_json_round_trips():
    payload = as_json()
    assert json.loads(json.dumps(payload)) == payload


def test_as_json_levels_carry_slug_label_and_both_color_variants():
    payload = as_json()
    assert [lv["n"] for lv in payload["levels"]] == list(range(1, 10))
    hex_color = re.compile(r"^#[0-9a-f]{6}$")
    for lv in payload["levels"]:
        assert lv["slug"] == LEVELS[lv["n"]].slug
        assert lv["label"] == LEVELS[lv["n"]].label
        # Both audiences' prose ships: the prompt reads finding_rubric +
        # boundaries, the public page reads web_summary. Dropping either
        # would force a hand-written second copy, which is the failure mode
        # this single source exists to prevent.
        assert lv["web_summary"] == LEVELS[lv["n"]].web_summary
        assert lv["finding_rubric"] == LEVELS[lv["n"]].finding_rubric
        assert lv["boundaries"] == list(LEVELS[lv["n"]].boundaries)
        assert set(lv["colors"]) == {"light", "dark"}, (
            f"level {lv['n']} must ship both theme variants"
        )
        for variant, value in lv["colors"].items():
            assert hex_color.match(value), (
                f"level {lv['n']} {variant} color {value!r} is not #rrggbb"
            )


def test_as_json_carries_the_maps_and_every_cap():
    payload = as_json()
    assert payload["five_to_nine"] == FIVE_TO_NINE
    assert payload["outcome_from_five"] == OUTCOME_FROM_FIVE
    assert payload["caps"] == {
        "agent_code": AGENT_CODE_CAP,
        "fast_screen": FAST_SCREEN_CAP,
        "model_knowledge": MODEL_KNOWLEDGE_CAP,
        "model_reading": MODEL_READING_CAP,
        "quarantine": QUARANTINE_CAP,
        "accusatory_min": ACCUSATORY_MIN,
    }


def test_as_json_does_not_share_mutable_state_with_the_module():
    # The codegen must not be able to corrupt the source of truth.
    payload = as_json()
    payload["five_to_nine"]["impossible"] = 9
    payload["caps"]["quarantine"] = 9
    assert FIVE_TO_NINE["impossible"] == 5
    assert QUARANTINE_CAP == 3


def test_hue_break_at_8_is_real():
    # Misconduct is a kind change, not a shade: 8 must not reuse 7's hue.
    assert SEVERITY9_COLORS[7]["light"] != SEVERITY9_COLORS[8]["light"]
    assert SEVERITY9_COLORS[7]["dark"] != SEVERITY9_COLORS[8]["dark"]


# ---------------------------------------------------------------------------
# The layering rule
# ---------------------------------------------------------------------------


def test_severity9_imports_nothing_from_tools_severity():
    # The 5-enum stays tool-layer; the shared surface is strings only.
    source = inspect.getsource(severity9)
    assert "tools.severity" not in source
    assert "from .tools" not in source
    assert "from forensic_metascience_ai_toolkit.tools" not in source


class TestModelReadingIsArithmeticNobodyPerformed:
    """MEASURED 2026-08-22 on 10.1037--0022-3514.94.2.94.2.196. Two findings
    shipped at severity 4 in a `does_not_reconcile` verdict carrying
    `computed_by: model_reading`, `inputs: null`, `computed: null` and no
    tool_verdict, and one of them is a FALSE POSITIVE: `F(1, 142) = 14.06` was
    called twice the F from the means, but the paper states a
    "2 x 2 x (time) mixed-design ANOVA" in the same paragraph, and the
    within-subjects error term at r = 0.47 reproduces the printed F exactly.

    `recalc_anova` itself returned `suspicious` on those numbers. The tool was
    right and the finding did not cite it -- and `_COMPUTED_BY_CAPS` had an
    entry for `agent_code` (4) and `model_knowledge` (3) but none at all for
    the weakest channel of the three."""

    def test_a_tool_technique_asserted_unaided_caps_at_three(self):
        assert clamp_provisional(
            4, computed_by="model_reading", technique_is_tool=True) == 3

    def test_citing_the_tool_restores_the_full_range(self):
        """The cap rewards CITATION, not a guess about which findings are
        correct -- which is what makes it safe to apply without knowing."""
        assert clamp_provisional(
            4, computed_by="registry_tool", technique_is_tool=True) == 4

    def test_a_non_tool_warrant_is_untouched(self):
        """`not_computational` and `internal_contradiction` have no arithmetic
        to cite and reading the page IS their honest channel. A blanket cap
        would demote three legitimate level-4 findings in the same two runs."""
        assert clamp_provisional(
            4, computed_by="model_reading", technique_is_tool=False) == 4

    def test_the_gate_defaults_off(self):
        """`technique_is_tool` is the caller's answer, and a caller that does
        not answer must not have a cap applied on its behalf -- the registry
        lookup lives in findings_v2, not here."""
        assert clamp_provisional(4, computed_by="model_reading") == 4

    def test_it_is_weaker_than_agent_code(self):
        """agent_code at least RAN code that can be re-run; model_reading did
        the sum in its head. The ordering is the whole justification."""
        assert MODEL_READING_CAP < AGENT_CODE_CAP

