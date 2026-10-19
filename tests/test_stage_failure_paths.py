"""Two bugs that turned a recoverable stage failure into a total loss.

Both were found on a real run of two papers, and they compounded: the API
rejected `--effort max`, both stages died in ~2s, and then the code that
handles "no report" crashed with UnboundLocalError -- so the traceback
REPLACED the error message that said what had actually gone wrong, and the
report, findings.json and cost record were never written.

The invariant these protect: a failed stage must degrade to an incomplete
report, never to an exception out of `analyze_paper`.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "src" / "metascience_agent" / "agent.py"


class TestEffortDefaultIsAccepted:
    """`max` is rejected by the API when thinking is disabled:

        400 output_config.effort 'max' is not supported when thinking is disabled

    `agent.DEFAULT_EFFORT` was already lowered to "high" for this reason, but
    the CLI and batch runner each hardcoded "max" and passed it explicitly, so
    the constant was overridden on every real invocation and the fix reached
    nobody. One source of truth, asserted here.
    """

    def test_agent_default_is_not_max(self):
        from metascience_agent.agent import DEFAULT_EFFORT

        assert DEFAULT_EFFORT != "max"

    def test_cli_analyze_defaults_to_the_shared_constant(self):
        import inspect

        from metascience_agent.agent import DEFAULT_EFFORT
        from metascience_agent.cli import analyze

        default = inspect.signature(analyze).parameters["effort"].default
        default = getattr(default, "default", default)
        # None since pipelines: "the pipeline file's effort, else the shared
        # constant", resolved in the body -- still one source of truth, never
        # a hardcoded level.
        assert default in (DEFAULT_EFFORT, None)
        if default is None:
            assert "effort = effort or DEFAULT_EFFORT" in inspect.getsource(analyze)

    def test_cli_batch_defaults_to_the_shared_constant(self):
        import inspect

        from metascience_agent.agent import DEFAULT_EFFORT
        from metascience_agent.cli import batch_cmd

        default = inspect.signature(batch_cmd).parameters["effort"].default
        default = getattr(default, "default", default)
        assert default in (DEFAULT_EFFORT, None)
        if default is None:
            assert "effort = effort or DEFAULT_EFFORT" in inspect.getsource(batch_cmd)

    def test_no_entry_point_hardcodes_max(self):
        """Source-level, because a new command would reintroduce it silently."""
        for rel in ("src/metascience_agent/cli.py", "src/metascience_agent/batch.py"):
            text = (ROOT / rel).read_text()
            assert '"--effort", default="max"' not in text, rel
            assert 'typer.Option("max", "--effort"' not in text, rel


