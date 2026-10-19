"""`--figures` off must mean the figure pass cannot run, not merely go unmentioned.

THE DEFECT, verified end to end on HEAD 3901200 and on the live run of
2026-08-29. `analyze_paper_parallel` took no `figures` argument at all, so the
tool agent's system prompt was assembled with the default and the figure
section was stripped -- and ALL the figure discipline lives in that section: the
instruction to stamp `provenance="measured_raster"`, the error-bar rules, the
figures-array duty. The shipped `system_prompt.tool_agent.md` of that run
contains ZERO occurrences of `measured_raster` and zero of "error bar".

Meanwhile `extract_figures` stayed in the 57-tool allowlist, and the model
called it.

CAPABILITY ON, GUARDS OFF -- strictly worse than either coherent setting, and a
live false-accusation channel. The exact-arithmetic gate (`registry.py`) keys on
a `provenance` parameter that DEFAULTS to `printed_table`, so a value read off a
plot reaches a granularity check as though the paper had printed it. Measured on
the figure-extractor benchmark (Fitzgerald, MIT): the best reader recovers a
mean to ~0.44% and an error bar to ~3.89% (worst 27.7%). GRIM needs error below
half its granularity window, 1/(2n), so a figure read is admissible only when
n x value < ~114 -- and a 1-7 Likert mean at n=30 (126) already fails.

WHY OFF RATHER THAN ON. Making the flag real enforces a decision the CLI already
records -- "OFF BY DECISION: figure-value extraction is not yet reliable, and a
wrong number read off a plot is worse than a stated gap." Removing a tool cannot
manufacture an accusation, and the blindness it restores is a reported gap. The
alternative (serve the discipline and keep the tool) reverses a recorded default
without the validation that decision demanded, and is Greg's and Dan's call.

SIX SURFACES, because five would have left the flag decorative again:
the entry point's parameter, the forward from `analyze_paper`, the system-prompt
section, the tool allowlist, the CLI map, and the producer schema's required
`figures` array.
"""
from __future__ import annotations

import inspect

import pytest

from metascience_agent import parallel as P
from metascience_agent.core import prompts
from metascience_agent import agent as A


class TestTheFlagReachesThePipeline:
    def test_the_parallel_entry_point_accepts_it(self):
        assert "figures" in inspect.signature(P.analyze_paper_parallel).parameters

    def test_analyze_paper_forwards_it(self):
        """It had the parameter and dropped it on the floor at the call."""
        src = inspect.getsource(A.analyze_paper)
        call = src[src.index("analyze_paper_parallel("):]
        assert "figures=figures" in call[:600], call[:600]

    def test_off_is_the_default_on_both(self):
        assert inspect.signature(P.analyze_paper_parallel).parameters["figures"].default is False
        assert inspect.signature(A.analyze_paper).parameters["figures"].default is False


class TestOffMeansUncallable:
    def test_the_tool_leaves_the_allowlist(self):
        on, off = P.tool_agent_tools(True), P.tool_agent_tools(False)
        assert any("extract_figures" in t for t in on)
        assert not any("extract_figures" in t for t in off)
        assert len(off) == len(on) - len(prompts.FIGURE_TOOLS)

    def test_nothing_else_leaves_the_allowlist(self):
        """The off-switch: removing the whole allowlist would also pass the
        assertion above."""
        on, off = set(P.tool_agent_tools(True)), set(P.tool_agent_tools(False))
        removed = on - off
        assert removed == {A._mcp(n) for n in prompts.FIGURE_TOOLS}, removed


class TestOffMeansUninstructedAndUnadvertised:
    def test_the_discipline_is_stripped_when_off_and_present_when_on(self):
        on = prompts.tool_expert_system_prompt(figures=True)
        off = prompts.tool_expert_system_prompt(figures=False)
        assert "measured_raster" in on
        assert "measured_raster" not in off

    def test_the_prompt_stops_naming_it(self):
        """A prompt naming a tool the agent cannot call invites off-list calls.
        (The CLI map that used to name it left the prompt in Phase 3b; the
        prompt body itself must still drop it.)"""
        on = prompts.tool_expert_system_prompt(figures=True)
        off = prompts.tool_expert_system_prompt(figures=False)
        assert "extract_figures" in on
        assert "extract_figures" not in off

    def test_the_tools_that_remain_are_still_named(self):
        off = prompts.tool_expert_system_prompt(figures=False)
        for still_callable in ("`grim_check`", "`statcheck`"):
            assert still_callable in off, still_callable


class TestOffDoesNotDemandAFieldNothingCanFill:
    def test_the_figures_array_is_required_only_when_the_pass_is_on(self):
        assert "figures" in prompts.producer_findings_schema(
            "tool_expert", figures=True)["required"]
        assert "figures" not in prompts.producer_findings_schema(
            "tool_expert", figures=False)["required"]

    def test_the_other_required_keys_are_untouched(self):
        req = prompts.producer_findings_schema("tool_expert", figures=False)["required"]
        for key in ("coverage", "anatomy", "statistics_register"):
            assert key in req, key
