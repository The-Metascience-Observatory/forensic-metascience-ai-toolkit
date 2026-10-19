"""Every registered tool is offered to a stage, or declared CLI-only on purpose.

GREG, 2026-08-15, on learning four tools could never be called by the model:
"if reconstruct_2x2 has the potential to be dispositive, I want it... This is the
same test I'd want you to apply to all tools -- if they have the potential to be
useful, I want them."

MEASURED that day, by set difference between the registry and the per-stage tool
surfaces:

    registry                   54
    offered to stage 1         48
    offered to stage 2         35
    OFFERED TO NEITHER          4     check_sd_range, flag_round_n,
                                      reconstruct_2x2, required_n

`registry.py` already says an empty `stages` is legal but "must be a deliberate
choice". One of the four was: `check_sd_range` carried a paragraph explaining
that the blocker had been closed and the remaining question was "left to a
human". The other three carried nothing at all, and were indistinguishable from
it -- which is the whole problem. A deliberate omission and a forgotten one look
identical in the source, so the register of intent has to live somewhere a test
can read.

`reconstruct_2x2` is why this matters rather than being tidy: it rebuilds a 2x2
from two percentages and an N and tests it for integer consistency, which is THE
check for diagnostic-accuracy papers -- the corpus in #162. We would have run
that corpus with its most applicable tool unreachable.
"""
import pytest

from metascience_agent import agent, registry

from metascience_agent.registry import CLI_ONLY


def _offered() -> set[str]:
    s1 = {str(t).split("__")[-1] for t in agent.STAGE1_TOOLS}
    s2 = {str(t).split("__")[-1] for t in agent.STAGE2_TOOLS}
    # The SCIENCE_AGENT role: staged in the registry (a decision this test
    # can read) while agent.py's science stage is wired in Phase 4. Reading
    # the role from the registry rather than an agent.py list keeps the
    # register of intent in one place.
    s3 = set(registry.stage_tools(registry.SCIENCE_AGENT))
    return s1 | s2 | s3


class TestNoToolIsUnreachableByAccident:
    def test_every_registered_tool_is_offered_or_declared_cli_only(self):
        names = {s.name for s in registry.SPECS}
        stranded = sorted(names - _offered() - set(CLI_ONLY))
        assert not stranded, (
            "registered, tested, documented -- and no model can call them: "
            f"{stranded}. Offer them to a stage, or add each to CLI_ONLY with "
            "the reason. Silence is not a decision.")

    def test_cli_only_entries_carry_a_reason(self):
        empty = [k for k, v in CLI_ONLY.items() if not str(v).strip()]
        assert not empty, f"CLI_ONLY entries with no stated reason: {empty}"

    def test_cli_only_names_are_real_tools(self):
        names = {s.name for s in registry.SPECS}
        assert not (set(CLI_ONLY) - names), "CLI_ONLY names a tool that no longer exists"

    def test_cli_only_tools_are_not_on_the_mcp_server(self):
        """The leak this pins: serving CLI-only names over MCP lets a
        sweep LLM launch the image/text tracks mid-run and dump empty
        findings. The tracks import the Python functions; they do not
        need the server."""
        pytest.importorskip("claude_agent_sdk")
        from metascience_agent.tools_mcp import ALL_TOOLS
        leaked = set(CLI_ONLY) & {t.name for t in ALL_TOOLS}
        assert not leaked, f"CLI-only tools served over MCP: {sorted(leaked)}"

    @pytest.mark.parametrize("name", ["reconstruct_2x2", "check_sd_range",
                                      "flag_round_n"])
    def test_the_three_that_were_stranded_are_reachable(self, name):
        """Pinned individually so a bulk refactor cannot quietly re-strand one."""
        assert name in _offered()

    def test_required_n_is_now_offered(self):
        """REVERSED 2026-08-16. It was declared CLI-only the day before, on the
        ground that a model-callable tool returns a verdict and says where its
        inputs came from, and a bare calculator does neither.

        THE ARGUMENT WAS SOUND AND THE DECISION WAS STILL WRONG. On PNAS
        0801268105 the sweep reached for this tool THREE TIMES and was refused,
        on a paper whose reported degrees of freedom imply 68 participants
        against a stated 34. Rather than keep withholding it, the tool was made
        to satisfy the invariant: it now returns a ladder severity, carries a
        source quote, and with `actual_n` compares the design a paper HAD
        against the one its own effect size needs."""
        assert "required_n" in _offered()
        spec = next(s for s in registry.SPECS if s.name == "required_n")
        assert "source_quote" in spec.schema(), "a check says where its inputs came from"
        assert "actual_n" in spec.schema(), "without this it is still only a calculator"


class TestTheHeuristicsCannotAccuse:
    """Offering a tool widens what the model can say. Two of the four are not
    exact checks, so their ceilings are what make them safe to offer."""

    def test_flag_round_n_is_capped_at_suspicious(self):
        s = next(x for x in registry.SPECS if x.name == "flag_round_n")
        assert s.evidence == "probabilistic"
        assert any("suspicious" in a for a in s.assumptions), \
            "a round-N heuristic that can reach `impossible` would accuse every " \
            "study whose recruitment target was a round number"

    def test_required_n_renders_no_verdict(self):
        s = next(x for x in registry.SPECS if x.name == "required_n")
        assert s.evidence == "descriptive"
        assert any("no verdict" in a for a in s.assumptions)
