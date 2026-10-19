"""1.92.0: who files an internal contradiction.

The proofreading agent owns contradictions (it keeps a register of what the
paper commits to and quotes both sides); the tools agent hands them off. When
the run has no proofreading agent, a handoff note reaches no one, so the tools
agent files the one numeric class itself: the same quantity printed with two
values. MEASURED 2026-10-18 (statcheck_pvalue_errors working set, tools_only):
24-25 `not_computational` problem rows per run, against a prompt that said
three different things about them.
"""

from metascience_agent import pipeline_config
from metascience_agent.core import prompts


def _note(pipeline, module="tools_agent"):
    return prompts.run_configuration_note(pipeline_config.load(pipeline), module)


def test_tools_only_hands_the_numeric_class_to_the_tools_agent():
    note = _note("tools_only")
    assert "`internal_contradiction`" in note
    assert "SAME quantity printed with different values" in note
    assert '"said"' in note and '"against"' in note
    # Everything else the proofreading agent owns stays out of scope.
    assert "contradictions in words rather than numbers" in note
    assert "do not describe it as covered" in note


def test_a_complete_review_gets_no_note():
    assert _note("full") == ""


def test_the_adjudicator_never_gets_the_tools_agent_line():
    note = _note("tools_only", module="adjudicator")
    assert "`internal_contradiction`" not in note


def test_the_tools_prompt_hands_contradictions_off_and_keeps_figures():
    body = prompts.tool_expert_body()
    top = body.split("## Tool discipline")[0]
    assert "INTERNAL CONTRADICTION" in top and "handoff note" in top
    assert "FIGURE that disagrees" in top
    # The label no longer advertises cross-reference contradictions or
    # reporting-practice points, and names arithmetic as disqualifying.
    nc = body.split("- **`not_computational`**")[1].split("- **`no_tool_exists`**")[0]
    assert "cross-reference" not in nc and "data-availability" not in nc
    assert "`no_tool_exists`" in nc and "ANY" in nc
    # The one unconditional "never a finding" rule and the label agree.
    assert "hand it off" in nc
