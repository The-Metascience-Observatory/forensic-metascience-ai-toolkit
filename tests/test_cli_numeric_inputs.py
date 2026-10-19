"""CLI parsing must preserve the numbers supplied to forensic checks."""

import pytest
import typer
from typer.testing import CliRunner

from metascience_agent.cli import _floats, _ints, app


@pytest.mark.parametrize("token", ["30.9", "-2.1", "30.000000000000000001",
                                  "nan", "inf", "-inf", "abc"])
def test_sample_sizes_are_never_rounded_or_truncated(token):
    with pytest.raises(typer.BadParameter, match="--ns"):
        _ints(f"20,{token}", "--ns")


def test_integral_spellings_preserve_the_exact_integer():
    assert _ints('[30, "30.0", 3e1, 9007199254740993]', "--ns") == [
        30, 30, 30, 9007199254740993,
    ]


@pytest.mark.parametrize("raw", ["1,,3", ",1,3", "1,3,", '[1,"",3]'])
def test_missing_list_entries_are_not_silently_dropped(raw):
    with pytest.raises(typer.BadParameter, match="--values"):
        _floats(raw, "--values")


def test_an_empty_list_remains_empty_for_the_tool_to_validate():
    assert _floats("[]", "--values") == []


def test_anova_rejects_a_fractional_sample_size_before_computation(monkeypatch):
    from metascience_agent.tools import anova

    def must_not_run(*args, **kwargs):
        pytest.fail("the CLI changed the input and reached the forensic tool")

    monkeypatch.setattr(anova, "recalc_one_way_anova", must_not_run)
    result = CliRunner().invoke(app, [
        "anova", "--means", "1,2", "--sds", "1,1", "--ns", "30.9,30",
    ])
    assert result.exit_code == 2, result.output
    assert "30.9" in result.output and "--ns" in result.output
