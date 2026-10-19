"""Replaying a finding must not start another workflow or write a file."""

import subprocess
from types import SimpleNamespace

import pytest

from metascience_agent import agent
from metascience_agent.evaluation.deterministic import run_reproduction


@pytest.mark.parametrize("command", [
    "metascience analyze paper.pdf",
    "metascience image-sweep papers",
    "metascience review-write paper.json",
    "metascience fetch-metadata papers",
    "metascience statcheck paper.txt --output results.json",
    "metascience statcheck paper.txt --output=results.json",
    "metascience statcheck paper.txt -oresults.json",
])
def test_runner_refuses_side_effects_without_starting_a_process(monkeypatch, command):
    def must_not_run(*args, **kwargs):
        pytest.fail("reproduction validation attempted a side effect")

    monkeypatch.setattr(subprocess, "run", must_not_run)
    result = run_reproduction(command)
    assert result["ran"] is False
    assert result["valid"] is False
    assert result["agrees"] is None
    assert result["problems"]


def test_malformed_quoting_is_reported_without_raising():
    result = run_reproduction("metascience grim 5.5 30 --note 'oops")
    assert result["ran"] is False and result["valid"] is False
    assert "quot" in " ".join(result["problems"])


def test_calculation_commands_still_execute_and_compare_the_verdict(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="consistent", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    result = run_reproduction("metascience grim 5.5 30", claimed_severity="consistent")
    assert calls == [["metascience", "grim", "5.5", "30"]]
    assert result["executed"] and result["agrees"] and result["valid"]


@pytest.mark.usefixtures("image_package")
def test_the_live_annotator_does_not_offer_an_operational_command(monkeypatch):
    def must_not_run(*args, **kwargs):
        pytest.fail("the annotator attempted an operational command")

    monkeypatch.setattr(agent, "_run_repro_cached", must_not_run)
    row = {"finding_id": "f_test", "outcome": "problem", "severity": 3,
           "reproduction": "metascience image-sweep papers"}
    result = {"findings": {"findings": [row]}, "run_meta": {}}
    summary = agent._annotate_reproductions(result)
    assert row["reproduction_valid"] is False
    assert "not automatically executed" in row["reproduction_problem"]
    assert summary["n_invalid"] == 1
    assert summary["n_ran_ok"] == 0
