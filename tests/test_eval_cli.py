"""`metascience eval --skip-analysis` must never start the paid pipeline.

The flag exists to say "do not spend money, just rescore what is already on
disk". The harness reads it as "reuse the run IF one exists, otherwise run it"
(`harness.eval_one`: `if skip_analysis and (review_dir / "report.md").exists()`),
so on a fixture with no run it did the exact thing it was passed to prevent,
silently and at full two-stage cost.

MEASURED 2026-08-07 in this repo: 2 of the 3 fixtures (airforce, wound_healing)
have no `benchmarks/paper_reviews/runs/<paper>/forensic_review/report.md`, so the invocation the
README documented -- a bare `metascience eval --skip-analysis` -- would have
launched two full analyses at the measured ~$5/paper on sonnet.

Nothing here spends money: every test either refuses before dispatch or asserts
on argv that is never executed.
"""

import pytest
from typer.testing import CliRunner

from metascience_agent import cli
from metascience_agent.cli import app
from metascience_agent.evaluation import harness

runner = CliRunner()


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A repo root with three fixtures and a run for only one of them."""
    (tmp_path / "benchmarks" / "paper_reviews" / "fixtures").mkdir(parents=True)
    for name in ("apple_cider", "airforce", "wound_healing"):
        (tmp_path / "benchmarks" / "paper_reviews" / "fixtures" / f"{name}.yaml").write_text(
            f"paper: {name}\npdf: nope.pdf\nverdict_expected: untrustworthy\n"
        )
    done = tmp_path / "benchmarks" / "paper_reviews" / "runs" / "apple_cider" / "forensic_review"
    done.mkdir(parents=True)
    (done / "report.md").write_text("# an existing run")
    monkeypatch.setattr(harness, "repo_root", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def no_dispatch(monkeypatch):
    """Capture the argv the CLI would hand the harness, without running it."""
    seen = {}

    def _fake_main(argv):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(harness, "main", _fake_main)
    return seen


class TestSkipAnalysisRefuses:
    def test_refuses_when_a_selected_fixture_has_no_existing_run(
        self, fake_repo, no_dispatch
    ):
        r = runner.invoke(app, ["eval", "--skip-analysis"])
        assert r.exit_code == 2, r.output
        assert "argv" not in no_dispatch, (
            "the harness was dispatched anyway -- it would have run the paid pipeline"
        )
        assert "airforce" in r.output and "wound_healing" in r.output, (
            "the refusal must name which fixtures have nothing to rescore"
        )

    def test_proceeds_when_the_selected_fixture_does_have_a_run(
        self, fake_repo, no_dispatch
    ):
        r = runner.invoke(app, ["eval", "--skip-analysis", "--paper", "apple_cider"])
        assert r.exit_code == 0, r.output
        assert "--skip-analysis" in no_dispatch["argv"]

    def test_refuses_for_a_single_named_fixture_with_no_run(self, fake_repo, no_dispatch):
        r = runner.invoke(app, ["eval", "--skip-analysis", "--paper", "airforce"])
        assert r.exit_code == 2, r.output
        assert "argv" not in no_dispatch

    def test_without_the_flag_nothing_is_prechecked(self, fake_repo, no_dispatch):
        """`metascience eval` alone is documented as costing money; leave it alone."""
        r = runner.invoke(app, ["eval", "--paper", "airforce"])
        assert r.exit_code == 0, r.output
        assert "--skip-analysis" not in no_dispatch["argv"]


class TestModelDefault:
    def test_matches_the_harness_default(self):
        """cli.py said 'opus' where harness.py:216 says 'sonnet', and the CLI always
        forwards --model, so the same fixtures were scored on different models
        depending on the entry point -- and the expensive one always won.
        Measured on a nine-study paper with SI: $4.97 sonnet, $22.01 fable.
        """
        cli_default = next(
            p.default.default
            for name, p in _params(cli.eval_cmd).items()
            if name == "model"
        )
        harness_default = next(
            a.default for a in harness.build_parser()._actions if a.dest == "model"
        )
        assert cli_default == harness_default, (
            f"metascience eval defaults to {cli_default!r} while the harness "
            f"defaults to {harness_default!r}"
        )


def _params(fn):
    import inspect

    return dict(inspect.signature(fn).parameters)


class TestGrokBudgetSkip:
    def test_a_budgetless_backend_drops_the_default_budget(self):
        """Grok raises BudgetUnsupported on any --budget-usd, and `metascience
        eval` defaults one -- so the documented `eval --backend grok` errored
        before spending a cent. The harness now drops the budget for a
        backend that cannot cap spend, loudly."""
        import inspect

        from metascience_agent.evaluation import harness
        src = inspect.getsource(harness)
        assert "supports_budget" in src
        assert "running WITHOUT" in src


class TestTheBudgetDefaultCanActuallyRunTheFixtures:
    """MEASURED 2026-08-22: `metascience eval --paper apple_cider` -- the exact
    command CLAUDE.md prescribes after a prompt change -- could not complete.

        StageError: both analysis agents failed; nothing to adjudicate
          science_agent: `claude` CLI exited with code 1
          tool_agent:    BUDGET-TRUNCATED before emitting findings

    The default was $3.00, the parallel pipeline gives the tool agent 0.40 of
    it, and the archived apple_cider run spent $2.81 on that stage alone. A
    documented command that cannot finish is worse than no command.
    """

    def _default(self, src: str, needle: str) -> float:
        import re
        m = re.search(needle, src)
        assert m, f"could not find the budget default via {needle!r}"
        return float(m.group(1))

    def test_the_cli_and_harness_defaults_agree(self):
        """Two places declare it; they must not drift. Same argument the
        `--model` defaults are already pinned on."""
        import pathlib
        cli = pathlib.Path("src/metascience_agent/cli.py").read_text()
        harness = pathlib.Path(
            "src/metascience_agent/evaluation/harness.py").read_text()
        a = self._default(cli, r'([\d.]+), "--budget-usd"')
        b = self._default(harness, r'"--budget-usd", type=float, default=([\d.]+)')
        assert a == b, f"cli={a} harness={b}"

    def test_the_default_covers_the_most_expensive_archived_fixture(self):
        """$2.81 on the tool agent at a 0.40 split needs $7.01. The number is
        not arbitrary and the test says where it comes from, so a future
        reduction has to argue with the measurement rather than the constant."""
        import pathlib
        from metascience_agent.parallel import TOOL_BUDGET_FRACTION
        harness = pathlib.Path(
            "src/metascience_agent/evaluation/harness.py").read_text()
        default = self._default(
            harness, r'"--budget-usd", type=float, default=([\d.]+)')
        most_expensive_tool_stage = 2.81   # benchmarks/paper_reviews/runs/apple_cider, 2026-08-21
        assert default * TOOL_BUDGET_FRACTION >= most_expensive_tool_stage, (
            f"a ${default} budget caps the tool agent at "
            f"${default * TOOL_BUDGET_FRACTION:.2f}, below the ${most_expensive_tool_stage} "
            "that fixture is measured to need")


class TestLegacyTwoStage:
    """`metascience eval --legacy-two-stage` runs the retiring serial pipeline
    BESIDE the parallel run, never over it.

    Added 2026-09-02. Measured before it existed: `baselines/` held no eval
    data at all (corpus-state snapshots), the only serial-mode recall anywhere
    was apple_cider's git history, and airforce / wound_healing /
    cerebrolysin_flow each had exactly one archived run -- v1.3.0, parallel,
    grok -- so the legacy body's deletion was gated on a comparison nothing
    could produce. The harness hardcoded `mode="parallel"` and one output
    directory, so a serial run would have erased the very run it was to be
    compared against.
    """

    def test_without_the_flag_the_harness_is_not_told_legacy(self, fake_repo, no_dispatch):
        r = runner.invoke(app, ["eval", "--paper", "airforce"])
        assert r.exit_code == 0, r.output
        assert "--legacy-two-stage" not in no_dispatch["argv"]



@pytest.mark.usefixtures("image_package")
def test_image_screen_defaults_to_ten_workers():
    """Dan, 2026-09-14: adjudication always runs ten-wide. The default was 2,
    and the runbook already showed `--workers 10`; a default that contradicts
    the runbook is the one people actually run."""
    import inspect
    from metascience_observatory_image_analysis.cli import image_screen_cmd
    param = inspect.signature(image_screen_cmd).parameters["workers"]
    assert param.default.default == 10


class TestTheJudgeIsFixed:
    """The judge used to follow --backend, so Grok graded Grok. Measured
    2026-10-13: the Grok judge scored a 26-finding review 0.0 with empty
    notes (Sonnet: 0.462). One grader for every backend."""

    def test_default_judge_is_claude_sonnet(self):
        from metascience_agent.evaluation import harness
        assert (harness.JUDGE_BACKEND, harness.JUDGE_MODEL) == ("claude", "sonnet")
        args = harness.build_parser().parse_args(["--backend", "grok"])
        assert args.judge_backend is None and args.judge_model is None   # -> the constants

    def test_eval_one_passes_the_judge_not_the_backend(self, monkeypatch, tmp_path):
        import asyncio
        from metascience_agent.evaluation import harness
        seen = {}

        async def fake_judge(fixture, report_md, findings, model=None, verbose=False,
                             backend=None, effort=None):
            seen.update(model=model, backend=backend, effort=effort)
            return {"recall_weighted": 1.0, "per_finding": [], "judge_notes": "ok",
                    "num_false_positives": 0, "false_positives": []}
        monkeypatch.setattr(harness, "judge_paper", fake_judge)
        run = tmp_path / "runs" / "p" / "forensic_review"
        run.mkdir(parents=True)
        (run / "report.md").write_text("# r")
        (run / "findings.v2.json").write_text('{"schema_version": "2.0", "findings": []}')
        monkeypatch.setattr(harness, "prepare_paper_dir", lambda *a, **k: tmp_path)
        fixture = {"paper": "p", "verdict_expected": "does_not_reconcile",
                   "expected_findings": []}
        sc = asyncio.run(harness.eval_one(fixture, tmp_path / "runs", tmp_path, budget_usd=None,
                                          timeout=None, model=None, skip_analysis=True,
                                          verbose=False, backend="grok"))
        assert seen == {"model": "sonnet", "backend": "claude", "effort": "high"}
        assert sc["backend"] == "grok"
        assert (sc["judge_backend"], sc["judge_model"], sc["judge_effort"]) == (
            "claude", "sonnet", "high")

    def test_a_silent_judge_is_flagged_not_scored_as_zero(self):
        from metascience_agent.evaluation.judge import score_judgement
        fixture = {"key_findings": [{"id": "a", "weight": "major"}]}
        findings = {"findings": [{"technique": "x"}] * 3}
        sc = score_judgement(fixture, {"per_finding": [], "notes": ""}, findings)
        assert sc["judge_degenerate"] is True
        sc = score_judgement(fixture, {"per_finding": [{"id": "a", "covered": False}],
                                       "notes": "missed a"}, findings)
        assert sc["judge_degenerate"] is False


def test_the_judge_sees_every_kept_finding_compactly():
    """The full JSON was cut at 30K characters, so a 60-80 finding review was
    graded on what fitted. The judge now gets the grading fields of every
    kept row, and the cross-route equivalence rule."""
    from metascience_agent.evaluation.judge import _judge_prompt, _judge_view
    rows = [{"finding_id": f"f_{i}", "technique": "grim_check", "title": f"t{i}",
             "description": "d" * 200, "outcome": "problem", "severity": 3,
             "anchors": [{"quote": "x" * 2000}], "inputs": {"mean": 1.0},
             "adjudication": {"action": "kept"}} for i in range(80)]
    rows.append({"finding_id": "f_gone", "title": "discarded",
                 "adjudication": {"action": "discarded"}})
    view = _judge_view({"findings": rows, "adjudication": {"verdict": "does_not_reconcile"}})
    assert len(view["findings"]) == 80 and "anchors" not in view["findings"][0]
    fixture = {"key_findings": [{"id": "a", "weight": "major", "description": "x"}]}
    prompt = _judge_prompt(fixture, "# r", {"findings": rows})
    assert '"f_79"' in prompt and "f_gone" not in prompt
    assert "SAME DEFECT by a different route" in prompt
