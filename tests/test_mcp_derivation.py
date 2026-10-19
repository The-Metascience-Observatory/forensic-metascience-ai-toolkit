"""The MCP layer derived from the registry must match it, tool for tool.

`tools_mcp.py` imports `claude_agent_sdk`, which the unit environment does not
have -- so these tests SKIP by default and run wherever the SDK is installed
(the project venv, and CI).

That skip is itself the point. A mutation to `tools_mcp.py` passed the entire
937-test suite unnoticed, because nothing in it could import the module. The
registry is well covered; the DERIVATION was not covered at all. These tests
close that gap without moving the SDK dependency into the registry, which would
re-create the original problem where the unit suite could not see the specs.
"""

import asyncio
import json

import pytest

from metascience_agent import registry as R

pytest.importorskip("claude_agent_sdk", reason="MCP derivation needs the agent SDK")

from metascience_agent import tools_mcp as M  # noqa: E402

#: Specs a model may be offered. CLI-only tools stay registered and
#: CLI-callable; they must not appear on the MCP server.
MCP_SPECS = [s for s in R.SPECS if s.stages]


def _by_name():
    return {t.name: t for t in M.ALL_TOOLS}


class TestDerivationMatchesRegistry:
    def test_one_tool_per_offered_spec(self):
        assert {t.name for t in M.ALL_TOOLS} == {s.name for s in MCP_SPECS}
        assert set(M.TOOLS_BY_NAME) == {s.name for s in MCP_SPECS}

    def test_cli_only_tools_are_not_served(self):
        leaked = set(R.CLI_ONLY) & {t.name for t in M.ALL_TOOLS}
        assert not leaked, (
            "CLI-only tools are on the MCP server; a sweep LLM can invoke "
            f"them mid-run: {sorted(leaked)}"
        )

    def test_names_are_unique(self):
        names = [t.name for t in M.ALL_TOOLS]
        assert len(set(names)) == len(names)

    @pytest.mark.parametrize("spec", MCP_SPECS, ids=lambda s: s.name)
    def test_description_and_schema_are_carried_through(self, spec):
        built = _by_name()[spec.name]
        assert built.description == spec.description
        assert set(built.input_schema) == set(spec.schema())

    @pytest.mark.parametrize("spec", MCP_SPECS, ids=lambda s: s.name)
    def test_withheld_params_absent_from_the_built_schema(self, spec):
        built = _by_name()[spec.name]
        leaked = spec.withheld() & set(built.input_schema)
        assert not leaked, f"{spec.name} exposes withheld {sorted(leaked)} through MCP"


class TestHandlerDispatch:
    """Each handler must invoke ITS OWN spec.

    The failure this guards is a handler bound to the wrong spec -- every tool
    would appear to work while returning another tool's results, which is
    indistinguishable from correct output in a report.
    """

    def test_each_handler_calls_its_own_spec(self):
        cases = {
            "grim_check": ({"mean": 5.51, "n": 30, "data_type": "likert"}, "grim"),
            "required_n": ({"test_type": "two_sample_t", "effect_size": 0.5}, "n_total"),
            # `measure` is required in practice: without it the null is unknown
            # (1 for a ratio, 0 for a difference) and the tool declines to judge.
            # Omitting it here would exercise the refusal rather than the output
            # shape this test is about.
            "absence_of_evidence": (
                {"ci_low": 0.72, "ci_high": 1.95, "measure": "OR"}, "includes_null"),
            "check_estimate_ci": ({"estimate": 1.42, "ci_low": 1.08, "ci_high": 1.87}, "severity"),
        }
        handlers = {t.name: t.handler for t in M.ALL_TOOLS}
        for name, (args, expected_key) in cases.items():
            payload = asyncio.run(handlers[name](dict(args)))
            body = json.loads(payload["content"][0]["text"])
            direct = R.BY_NAME[name].call(dict(args))
            assert body == json.loads(json.dumps(direct, default=str)), (
                f"{name}'s handler did not produce its own spec's result"
            )
            assert any(expected_key in k for k in body) or expected_key in str(body), (
                f"{name} returned something that is not its own output shape"
            )

    def test_envelope_shape(self):
        handlers = {t.name: t.handler for t in M.ALL_TOOLS}
        out = asyncio.run(handlers["grim_check"]({"mean": 5.51, "n": 30}))
        assert set(out) == {"content"}
        assert out["content"][0]["type"] == "text"
        json.loads(out["content"][0]["text"])   # must be valid JSON

    def test_withheld_param_cannot_be_smuggled_through_the_handler(self):
        """The MCP layer does not validate args against the schema, so a model
        that guesses a withheld name must still be ignored at call time."""
        handlers = {t.name: t.handler for t in M.ALL_TOOLS}
        base = asyncio.run(handlers["csf_test"]({"p_values": [0.93, 0.99, 0.99]}))
        smug = asyncio.run(handlers["csf_test"](
            {"p_values": [0.93, 0.99, 0.99], "rho_grid": (0.0,)}))
        assert base["content"][0]["text"] == smug["content"][0]["text"]
