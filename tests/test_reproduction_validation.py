"""A finding nobody can reproduce is not auditable.

The findings schema REQUIRES a `reproduction` command, but the only check was
that the string is non-empty. In the committed gold run all six were unrunnable:
three contain literal `...` placeholders, three invoke flags that do not exist
(`--percentage`, `--input`) and only fail when actually executed.
"""
import pytest

from metascience_agent.evaluation.deterministic import (
    known_commands,
    run_reproduction,
    validate_reproduction,
)


class TestStaticValidation:
    @pytest.mark.parametrize("cmd", [
        """metascience tool run grim_check --json '{"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert"}'""",
        """metascience tool run grimmer_check --json '{"mean": 4.0, "sd": 1.0, "n": 10, "decimals": 1, "data_type": "likert"}'""",
        """metascience tool run recalc_independent_t --json '{"mean1": 10.0, "sd1": 2.0, "n1": 30, "mean2": 12.0, "sd2": 2.0, "n2": 30, "reported_p": 0.05}'""",
    ])
    def test_runnable_commands_pass(self, cmd):
        assert validate_reproduction(cmd)["valid"] is True

    @pytest.mark.parametrize("cmd,reason", [
        ("metascience grim ... 30", "placeholder"),
        ("metascience recalc-within-subjects-t --baseline-mean ...", "placeholder"),
        ("metascience frobnicate 1 2", "unknown subcommand"),
        ("python -c 'grim(1,2)'", "not metascience"),
        ("N/A -- excluded as a misapplied check", "not metascience"),
        ("", "empty"),
        ("metascience grim <mean> <n>", "placeholder"),
        ("metascience grim 5.51 30", "retired per-tool verb"),
    ])
    def test_unrunnable_commands_are_rejected(self, cmd, reason):
        assert validate_reproduction(cmd)["valid"] is False, f"should reject ({reason}): {cmd!r}"

    def test_known_commands_is_populated(self):
        cmds = known_commands()
        assert {"tool", "analyze", "batch"} <= cmds
        assert not {"grim", "grimmer", "ttest"} & cmds, "per-tool verbs are retired"

    def test_an_archived_verb_reads_as_retired_not_as_unknown(self):
        """Runs before 1.95.0 wrote `metascience grim 5.51 30`. That command
        was right when written; it must not read as a defect in the old run."""
        problems = validate_reproduction("metascience grim 5.51 30")["problems"]
        assert len(problems) == 1
        assert "retired" in problems[0] and "tool run grim_check" in problems[0]
        assert "unknown subcommand" not in problems[0]


class TestExecution:
    """The strong check: actually run it."""

    @pytest.mark.parametrize("cmd", [
        """metascience tool run grim_check --json '{"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert"}'""",
        """metascience tool run grimmer_check --json '{"mean": 4.0, "sd": 1.0, "n": 10, "decimals": 1, "data_type": "likert"}'""",
        """metascience tool run grim_check --json '{"mean": 3.53, "n": 30, "decimals": 2, "data_type": "likert"}'""",
    ])
    def test_real_commands_execute_cleanly(self, cmd):
        r = run_reproduction(cmd)
        assert r["ran"] is True and r["ok"] is True, r.get("problems")

    @pytest.mark.parametrize("cmd", [
        # invented parameter names
        """metascience tool run grim_check --json '{"percentage": 36.6, "n": 120}'""",
        """metascience tool run csf_test --json '{"input": "table1_baseline.json"}'""",
    ])
    def test_invented_arguments_fail_only_on_execution(self, cmd):
        """These pass static checks -- execution is what catches them."""
        assert validate_reproduction(cmd)["valid"] is True
        assert run_reproduction(cmd)["ok"] is False

    def test_a_retired_verb_is_never_executed(self):
        r = run_reproduction("metascience grim 5.51 30")
        assert r["ran"] is False and r["ok"] is False


class TestTheAggregatorWasDeletedRatherThanFixed:
    """`check_reproductions` is gone (2026-08-11) and this replaces the test
    that pinned it.

    It had no caller: `deterministic.run_all` never listed it and
    `harness.run_all` is the eval entry point, so its last consumer left with
    the rewrite `tests/test_reproduction_wiring.py` documents. Being dead is
    not why it was deleted -- it had drifted into scoring agreement by not
    checking it. It called `run_reproduction(cmd)` with no `claimed_severity`,
    so `valid` fell back to executability, and it counted the legacy `ok` key,
    which means "exited 0". Every forensic verb exits 0 whichever verdict it
    reaches, so a command whose tool CONTRADICTED its finding was counted valid.

    A tested, importable function that certifies the wrong thing is worse than
    no function, because the next person needing one finds it first. The live
    path is `agent._annotate_reproductions` via `_run_repro_cached`, and
    `TestAgreementNotJustExecutability` below is where that behaviour is pinned.
    """

    def test_it_is_gone(self):
        from metascience_agent.evaluation import deterministic as D
        assert not hasattr(D, "check_reproductions"), (
            "if it is back, it must forward claimed_severity and count `valid`, "
            "not `ok` -- see the note at its former site")

    def test_the_live_path_is_the_one_wired_in(self):
        """Named here so the deletion cannot be read as a loss of coverage."""
        from metascience_agent.agent import _annotate_reproductions
        r = {"findings": {"findings": [
            {"id": "f1", "severity": "consistent",
             "reproduction": """metascience tool run grim_check --json '{"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert"}'"""},
            {"id": "f2", "severity": "consistent",
             "reproduction": "metascience grim ... 30"},
        ]}, "run_meta": {}}
        s = _annotate_reproductions(r)
        assert s["n_findings"] == 2 and s["n_headline"] == 0
        assert s["n_targets"] == 2
        assert s["n_unparseable"] == 1, "the `...` placeholder must be caught"


class TestAgreementNotJustExecutability:
    """Greg, 2026-08-11: `reproduction_valid` certifying EXECUTABILITY was the
    weakest link in the evidence chain, because it is the one place a reader is
    invited to stop checking.

    Every forensic verb in this CLI exits 0 whichever verdict it reaches:

        $ metascience check-bounds 11.3 correlation
        indeterminate  correlation = 11.3          # exit 0

    So a finding claiming `impossible` could carry a green badge whose command,
    executed, said `indeterminate`."""

    def test_the_verdict_is_read_out_of_the_output(self):
        from metascience_agent.evaluation.deterministic import reported_severity
        assert reported_severity("CONSISTENT: Mean 3.14 is possible for n=28") == "consistent"
        assert reported_severity("indeterminate  correlation = 11.3") == "indeterminate"
        assert reported_severity("highly_suspicious  x") == "highly_suspicious"

    def test_prose_further_down_is_not_read_as_the_verdict(self):
        """`consistent` appears in explanations ("...is consistent with...").
        Reading that as the answer would score a disagreement as a pass."""
        from metascience_agent.evaluation.deterministic import reported_severity
        head = "impossible  x = 1\n" + "y " * 200 + "is consistent with the mean"
        assert reported_severity(head) == "impossible"

    def test_an_unreadable_verdict_is_unknown_not_agreement(self):
        from metascience_agent.evaluation.deterministic import reported_severity
        assert reported_severity("something with no ladder word in it") is None

    def test_a_command_that_disagrees_is_no_longer_valid(self):
        """THE LIVE CASE. This command runs, exits 0, and reports
        `indeterminate`. A finding claiming `impossible` from it is not
        reproduced by it."""
        from metascience_agent.evaluation.deterministic import run_reproduction
        r = run_reproduction("""metascience tool run check_statistic_bounds --json '{"value": 11.3, "measure": "correlation"}'""",
                             claimed_severity="impossible")
        if not r.get("ran"):
            pytest.skip(f"CLI unavailable: {r.get('problems')}")
        assert r["executed"] is True, "the command DOES run -- that is the point"
        assert r["reported_severity"] == "indeterminate"
        assert r["agrees"] is False
        assert r["valid"] is False
        assert "DISAGREES" in " ".join(r["problems"])

    def test_a_command_that_agrees_is_valid(self):
        from metascience_agent.evaluation.deterministic import run_reproduction
        r = run_reproduction("""metascience tool run check_statistic_bounds --json '{"value": 11.3, "measure": "correlation"}'""",
                             claimed_severity="indeterminate")
        if not r.get("ran"):
            pytest.skip("CLI unavailable")
        assert r["agrees"] is True and r["valid"] is True

    def test_with_no_claim_it_falls_back_to_executability(self):
        """The fail-safe direction. Nothing was claimed, so nothing can
        disagree, and the old meaning is the honest one."""
        from metascience_agent.evaluation.deterministic import run_reproduction
        r = run_reproduction("""metascience tool run check_statistic_bounds --json '{"value": 11.3, "measure": "correlation"}'""")
        if not r.get("ran"):
            pytest.skip("CLI unavailable")
        assert r["agrees"] is None and r["valid"] is True

    def test_an_unreadable_verdict_does_not_become_a_pass_or_a_failure(self):
        """`None` must not be promoted in either direction: not to agreement,
        which would restore the bug, and not to disagreement, which would
        accuse a finding on the strength of our own parser."""
        from metascience_agent.evaluation.deterministic import run_reproduction
        r = run_reproduction("metascience --help", claimed_severity="impossible")
        if not r.get("ran"):
            pytest.skip("CLI unavailable")
        assert r["agrees"] is None
        assert r["valid"] is True
        assert any("unknown" in p for p in r["problems"])


class TestTheCacheKeyIncludesTheClaim:
    """Keyed on the command alone, the second finding would inherit the first
    one's agreement verdict -- a fresh instance of the bug the change exists to
    close.

    ASSERTED AS BEHAVIOUR, NOT AS SOURCE TEXT. This test used to match the
    literal `key = (command, claimed_severity)`, so adding `claimed_outcome` --
    which makes the key strictly MORE discriminating, exactly what the test
    protects -- failed it. A test that breaks when its property is strengthened
    is testing the spelling, not the property.
    """

    def _cached(self, monkeypatch, **kw):
        from metascience_agent import agent
        calls = []

        def fake(command, timeout=90, claimed_severity=None,
                 claimed_outcome=None):
            calls.append((command, claimed_severity, claimed_outcome))
            return {"ran": True, "executed": True, "ok": True, "valid": True,
                    "agrees": None, "problems": []}

        monkeypatch.setattr(
            "metascience_agent.evaluation.deterministic.run_reproduction", fake)
        agent._REPRO_RUN_CACHE.clear()
        return agent, calls

    def test_differing_severity_is_a_different_question(self, monkeypatch):
        agent, calls = self._cached(monkeypatch)
        agent._run_repro_cached("metascience grim 5.5 30", claimed_severity=2)
        agent._run_repro_cached("metascience grim 5.5 30", claimed_severity=4)
        assert len(calls) == 2, "the second claim reused the first one's verdict"

    def test_differing_outcome_is_a_different_question(self, monkeypatch):
        agent, calls = self._cached(monkeypatch)
        agent._run_repro_cached("metascience grim 5.5 30", claimed_severity=2,
                                claimed_outcome="problem")
        agent._run_repro_cached("metascience grim 5.5 30", claimed_severity=2,
                                claimed_outcome="pass")
        assert len(calls) == 2, "the outcome is part of the question now"

    def test_the_identical_question_is_still_cached(self, monkeypatch):
        # The cache must still be a cache: this is what stops a re-render
        # paying to execute every command again.
        agent, calls = self._cached(monkeypatch)
        for _ in range(3):
            agent._run_repro_cached("metascience grim 5.5 30",
                                    claimed_severity=2, claimed_outcome="problem")
        assert len(calls) == 1
