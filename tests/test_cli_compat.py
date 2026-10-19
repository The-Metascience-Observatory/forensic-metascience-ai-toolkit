"""The CLI accepts the shape the model actually writes.

MEASURED over every archived review: 341 distinct reproduction commands, of
which only 68 (19%) parsed. 205 of the 360 recorded failures are argument-SHAPE
mismatches -- not wrong numbers, not wrong checks, wrong spelling of the
invocation. The mismatch is systematic: the model writes the MCP tool's
parameter names as long flags with values inline.

After the shim: 215 of 341 parse (63%), 147 newly, and NOTHING that parsed
before stopped parsing.
"""
from pathlib import Path

import click
import pytest
import typer

from metascience_agent.cli import app
from metascience_agent.cli_compat import McpFriendlyGroup, _is_argument, rewrite_args

# The toolkit's own per-tool verbs were retired in 1.95.0 (`metascience tool
# run` is the one command), but the shim still fronts the image package's CLI.
# These stand-ins keep the SHAPES the archive measured -- positionals,
# a renamed option, a path that inline JSON must reach -- so the rules stay
# pinned without depending on commands that no longer exist.
_demo = typer.Typer(cls=McpFriendlyGroup)


@_demo.command("grimmer")
def _grimmer(mean: float, sd: float, n: int):
    """stand-in"""


@_demo.command("grim")
def _grim(mean: float, n: int,
          scale_min: int = typer.Option(1, "--scale-min"),
          scale_max: int = typer.Option(7, "--scale-max")):
    """stand-in"""


@_demo.command("check-ci")
def _check_ci(estimate: float, ci_low: float, ci_high: float,
              measure: str = typer.Option("OR", "--measure")):
    """stand-in"""


@_demo.command("summation")
def _summation(values: str = typer.Option(..., "--values"),
               expected: float = typer.Option(..., "--expected")):
    """stand-in"""


@_demo.command("summation-batch")
def _summation_batch(json_path: Path):
    """stand-in"""


@pytest.fixture(scope="module")
def group():
    return typer.main.get_command(_demo)


def _cmd(group, name):
    return group.get_command(click.Context(group), name)


class TestTheShimIsNotInert:
    """THE BUG THAT ALMOST SHIPPED, and the reason this class exists.

    The first version tested `isinstance(p, click.Argument)`. Typer builds its
    commands against a VENDORED click, so `TyperArgument` is not an instance of
    the `click.Argument` this module imports: the check returned False for
    every parameter of every command and the whole rewrite did nothing. It was
    SILENT, because `rewrite_args` catches everything and returns its input --
    the right failure mode for a shim, and the worst one for noticing the shim
    is dead.

    Caught only by measuring the parse rate before and after and seeing it
    barely move. These tests make the next such regression loud."""

    def test_positional_parameters_are_recognised_at_all(self, group):
        """If this fails, every other test here passes vacuously."""
        cmd = _cmd(group, "grimmer")
        assert [p.name for p in cmd.params if _is_argument(p)] == ["mean", "sd", "n"]

    def test_detection_does_not_depend_on_isinstance(self, group):
        """Pins the actual lesson: `param_type_name` is Click's own parameter
        protocol and survives vendoring; `isinstance` did not.

        RE-PINNED 2026-08-22. The old assertion demanded that TyperArgument
        NOT be an instance of `click.Argument` -- a property of the
        installed typer/click pair, true only where typer vendors click. On
        environments where TyperArgument subclasses the real click.Argument
        (this one), it failed forever as a 'known failure' while the shim
        worked fine. The lesson is about OUR detector, so that is what is
        pinned: it detects positionals, and its source contains no
        isinstance to be defeated by vendoring."""
        import inspect

        from metascience_agent import cli_compat

        cmd = _cmd(group, "grimmer")
        pos = [p for p in cmd.params if _is_argument(p)]
        assert [p.name for p in pos] == ["mean", "sd", "n"]
        # The mechanism, pinned positively (the docstring NARRATES the old
        # isinstance bug, so a source scan for its absence trips on prose):
        # the executable body keys on param_type_name and nothing else.
        body = inspect.getsource(cli_compat._is_argument).rsplit('"""', 1)[1]
        assert "param_type_name" in body
        assert "isinstance" not in body, (
            "the detector must key on param_type_name, which survives "
            "click vendoring; isinstance silently killed the whole shim once"
        )

    def test_a_real_command_is_actually_rewritten(self, group):
        assert rewrite_args(_cmd(group, "grimmer"),
                            ["--mean", "1.67", "--sd", "2.15", "--n", "64"]) \
            == ["1.67", "2.15", "64"]


class TestTheMechanicalRules:
    def test_a_flag_named_after_a_positional_becomes_that_positional(self, group):
        assert rewrite_args(_cmd(group, "check-ci"),
                            ["--estimate", "0.217", "--ci-low", "0.081",
                             "--ci-high", "0.582", "--measure", "RR"]) \
            == ["0.217", "0.081", "0.582", "--measure", "RR"]

    def test_positionals_come_out_in_declared_order_not_written_order(self, group):
        """The model does not always write them in the CLI's order, and a
        positional in the wrong slot is a wrong answer rather than an error."""
        assert rewrite_args(_cmd(group, "check-ci"),
                            ["--ci-high", "3", "--estimate", "1", "--ci-low", "0"]) \
            == ["1", "0", "3"]

    def test_an_option_addressed_by_its_python_name_is_renamed(self, group):
        """`--expected-sum` is the MCP parameter; the CLI option is
        `--expected`. Same quantity, different spelling."""
        assert rewrite_args(_cmd(group, "summation"),
                            ["--values", "1,2,3", "--expected-sum", "6"]) \
            == ["--values", "1,2,3", "--expected", "6"]

    def test_flag_equals_value_is_handled_too(self, group):
        assert rewrite_args(_cmd(group, "grimmer"),
                            ["--mean=1.67", "--sd=2.15", "--n=64"]) \
            == ["1.67", "2.15", "64"]


class TestItNeverMakesThingsWorse:
    def test_a_command_already_in_cli_shape_is_untouched(self, group):
        args = ["5.5", "30", "--scale-min", "1", "--scale-max", "7"]
        assert rewrite_args(_cmd(group, "grim"), list(args)) == args

    def test_an_unrecognised_flag_is_passed_through_for_click_to_reject(
            self, group):
        """A shim that silently dropped what it did not understand would turn
        a loud failure into a wrong answer, which is strictly worse."""
        out = rewrite_args(_cmd(group, "grim"), ["5.5", "30", "--not-a-flag", "x"])
        assert "--not-a-flag" in out

    def test_it_never_raises(self, group):
        for junk in ([], ["--"], ["--x"], ["--x", "--y"], ["--mean"]):
            rewrite_args(_cmd(group, "grimmer"), list(junk))


class TestInlineJsonBecomesAFileTheCommandCanRead:
    """A command naming `rows.json` reproduces nothing for a reader who does
    not have `rows.json`. Inline data is what makes a batch command
    self-contained, which is the entire purpose of the `reproduction` field."""

    def test_json_for_a_path_positional_is_spilled_to_a_file(self, group, tmp_path):
        import json as _json
        out = rewrite_args(_cmd(group, "summation-batch"),
                           ["--rows", '[{"values":[1,2],"expected_sum":3}]'])
        assert len(out) == 1
        p = Path(out[0])
        assert p.exists()
        assert _json.loads(p.read_text()) == [{"values": [1, 2], "expected_sum": 3}]

    def test_a_plain_path_is_not_spilled(self, group):
        out = rewrite_args(_cmd(group, "summation-batch"), ["--rows", "rows.json"])
        assert out == ["rows.json"]


def test_python_verb_prints_this_interpreter():
    """`PY=$(metascience python)` is the documented way to find the project
    interpreter (AGENTS.md). It must be `sys.executable`, never a shebang read,
    which is `/bin/sh` behind a shell shim."""
    import sys
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, ["python"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == sys.executable
