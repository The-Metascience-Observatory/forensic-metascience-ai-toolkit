"""Tests for the pre-call usage guard.

The guard's contract: pause before spending a call when the 5-hour session
window is nearly exhausted, but never become the reason a batch stops. Every
failure path must fail OPEN.
"""

import asyncio

import pytest

from forensic_metascience_ai_toolkit import usage_guard


USAGE_TEXT = (
    "You are currently using your subscription to power your Claude Code usage\n"
    "\n"
    "Current session: 27% used · resets Jul 26, 11:30pm (America/New_York)\n"
    "Current week (all models): 53% used · resets Jul 31, 2:59am (America/New_York)\n"
    "Current week (Fable): 16% used · resets Jul 31, 2:59am (America/New_York)\n"
)


@pytest.fixture(autouse=True)
def clean_guard_state(monkeypatch):
    """Each test starts un-gated, with the guard enabled and its knobs pinned."""
    usage_guard._reset_state_for_tests()
    for var in (
        "METASCIENCE_USAGE_GUARD",
        "METASCIENCE_USAGE_THRESHOLD",
        "METASCIENCE_USAGE_WEEK_THRESHOLD",
        "METASCIENCE_USAGE_WEEK_WAIT",
        "METASCIENCE_USAGE_IGNORE_WEEKLY",
        "METASCIENCE_USAGE_INTERVAL_MIN",
        "METASCIENCE_USAGE_POLL_MIN",
        "METASCIENCE_USAGE_MAX_WAIT_MIN",
    ):
        monkeypatch.delenv(var, raising=False)
    yield
    usage_guard._reset_state_for_tests()


def _fake_probe(readings):
    """Probe stub returning `readings` in order, repeating the last one."""
    calls = []

    async def probe(*_args, **_kwargs):
        calls.append(1)
        idx = min(len(calls) - 1, len(readings) - 1)
        return readings[idx]

    probe.calls = calls
    return probe


@pytest.fixture
def no_real_sleep(monkeypatch):
    """Make the pause instantaneous but record how long it asked for."""
    slept = []
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds, *args, **kwargs):
        slept.append(seconds)
        return await real_sleep(0)

    monkeypatch.setattr(usage_guard.asyncio, "sleep", fake_sleep)
    return slept


# --- parsing -------------------------------------------------------------

def test_parse_usage_reads_session_and_week():
    assert usage_guard.parse_usage(USAGE_TEXT) == (27, 53)


def test_parse_usage_ignores_per_model_week_line():
    """`Current week (Fable): 16%` must not be mistaken for the all-models limit."""
    text = "Current week (Fable): 16% used\nCurrent week (all models): 53% used\n"
    assert usage_guard.parse_usage(text)[1] == 53


def test_parse_usage_on_unrecognized_text():
    assert usage_guard.parse_usage("no gauge here") == (None, None)
    assert usage_guard.parse_usage("") == (None, None)


# --- gating --------------------------------------------------------------

def test_guard_disabled_by_env_never_probes(monkeypatch):
    monkeypatch.setenv("METASCIENCE_USAGE_GUARD", "0")
    probe = _fake_probe([(99, 99)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)
    asyncio.run(usage_guard.guard())
    assert probe.calls == []


def test_under_threshold_returns_without_sleeping(monkeypatch, no_real_sleep):
    probe = _fake_probe([(27, 53)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)
    asyncio.run(usage_guard.guard())
    assert len(probe.calls) == 1
    assert no_real_sleep == []


def test_over_threshold_waits_until_window_resets(monkeypatch, no_real_sleep):
    monkeypatch.setenv("METASCIENCE_USAGE_THRESHOLD", "80")
    monkeypatch.setenv("METASCIENCE_USAGE_POLL_MIN", "15")
    probe = _fake_probe([(85, 60), (92, 61), (3, 62)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)

    asyncio.run(usage_guard.guard())

    assert len(probe.calls) == 3          # initial + two re-checks
    assert no_real_sleep == [15 * 60, 15 * 60]


def test_probe_failure_fails_open(monkeypatch, no_real_sleep):
    probe = _fake_probe([(None, None)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)
    asyncio.run(usage_guard.guard())
    assert no_real_sleep == []


def test_probe_failure_while_paused_fails_open(monkeypatch, no_real_sleep):
    """If the gauge stops answering mid-pause we resume rather than hang forever."""
    monkeypatch.setenv("METASCIENCE_USAGE_THRESHOLD", "80")
    probe = _fake_probe([(90, 60), (None, None)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)
    asyncio.run(usage_guard.guard())
    assert len(no_real_sleep) == 1


def test_max_wait_gives_up_and_continues(monkeypatch, no_real_sleep):
    monkeypatch.setenv("METASCIENCE_USAGE_THRESHOLD", "80")
    monkeypatch.setenv("METASCIENCE_USAGE_POLL_MIN", "10")
    monkeypatch.setenv("METASCIENCE_USAGE_MAX_WAIT_MIN", "20")
    # Week held BELOW its threshold: this test is about the SESSION gate giving
    # up, and it was written with week=99, which now correctly stops the batch
    # outright and so never reached the code under test.
    probe = _fake_probe([(95, 40)])  # never recovers
    monkeypatch.setattr(usage_guard, "probe_usage", probe)

    asyncio.run(usage_guard.guard())

    assert no_real_sleep == [600, 600]   # stops after 20 minutes, does not hang


class TestWeeklyGate:
    """The two windows fail differently and want different responses.

    MEASURED 2026-07-31: a 10-paper batch was launched at session 5% / week 99%.
    The session gate waved it through and it ran for 25 minutes against a quota
    already spent, completing nothing. Both numbers were parsed and logged at
    the time; only one of them was acted on.
    """

    def test_a_spent_week_stops_the_batch(self, monkeypatch, no_real_sleep):
        monkeypatch.setenv("METASCIENCE_USAGE_WEEK_THRESHOLD", "97")
        monkeypatch.setattr(usage_guard, "probe_usage", _fake_probe([(5, 99)]))
        with pytest.raises(usage_guard.WeeklyLimitReached):
            asyncio.run(usage_guard.guard())

    def test_it_fires_even_when_the_session_is_nearly_empty(self, monkeypatch,
                                                            no_real_sleep):
        """Session 5% is exactly the case that went unnoticed: nothing else in
        the guard had any reason to stop."""
        monkeypatch.setenv("METASCIENCE_USAGE_THRESHOLD", "90")
        monkeypatch.setattr(usage_guard, "probe_usage", _fake_probe([(5, 100)]))
        with pytest.raises(usage_guard.WeeklyLimitReached):
            asyncio.run(usage_guard.guard())

    def test_it_stops_rather_than_waits(self, monkeypatch, no_real_sleep):
        """A week at 99% may not reset for days. A batch waiting on that is
        hung, not paused -- and from outside it looks exactly like one that is
        working."""
        monkeypatch.setattr(usage_guard, "probe_usage", _fake_probe([(5, 99)]))
        with pytest.raises(usage_guard.WeeklyLimitReached):
            asyncio.run(usage_guard.guard())
        assert no_real_sleep == []      # never slept

    def test_waiting_is_available_when_asked_for(self, monkeypatch, no_real_sleep):
        monkeypatch.setenv("METASCIENCE_USAGE_WEEK_WAIT", "1")
        monkeypatch.setenv("METASCIENCE_USAGE_POLL_MIN", "10")
        monkeypatch.setattr(usage_guard, "probe_usage",
                            _fake_probe([(5, 99), (5, 40)]))
        asyncio.run(usage_guard.guard())        # returns, does not raise
        assert no_real_sleep == [600]

    def test_headroom_below_the_threshold_is_left_usable(self, monkeypatch,
                                                         no_real_sleep):
        """Set higher than the session threshold on purpose: a weekly gate costs
        the rest of the batch, so it must not fire on quota still usable."""
        monkeypatch.setattr(usage_guard, "probe_usage", _fake_probe([(5, 96)]))
        asyncio.run(usage_guard.guard())
        assert no_real_sleep == []

    def test_an_unreadable_week_does_not_stop_anything(self, monkeypatch,
                                                       no_real_sleep):
        """The guard is a convenience and must never itself become the reason a
        batch stops."""
        monkeypatch.setattr(usage_guard, "probe_usage", _fake_probe([(5, None)]))
        asyncio.run(usage_guard.guard())

    def test_extra_credits_override_skips_the_weekly_stop(self, monkeypatch,
                                                          no_real_sleep):
        """The /usage weekly % does not include extra usage credits.

        Session 0% / week 100% is the case that fired this stop against a
        paid extra-credits balance: nothing else in the guard had any reason
        to pause, and the weekly gate is what blocked the run.
        """
        monkeypatch.setenv("METASCIENCE_USAGE_IGNORE_WEEKLY", "1")
        monkeypatch.setattr(usage_guard, "probe_usage",
                            _fake_probe([(0, 100)]))
        asyncio.run(usage_guard.guard())        # must not raise
        assert no_real_sleep == []

    def test_extra_credits_override_does_not_disable_session_pause(
            self, monkeypatch, no_real_sleep):
        """Overriding the weekly STOP is not a licence to walk into the
        5-hour session window. Extra credits still sit behind that window."""
        monkeypatch.setenv("METASCIENCE_USAGE_IGNORE_WEEKLY", "1")
        monkeypatch.setenv("METASCIENCE_USAGE_THRESHOLD", "80")
        monkeypatch.setenv("METASCIENCE_USAGE_POLL_MIN", "10")
        probe = _fake_probe([(90, 100), (10, 100)])
        monkeypatch.setattr(usage_guard, "probe_usage", probe)
        asyncio.run(usage_guard.guard())
        assert no_real_sleep == [600]

    def test_extra_credits_override_beats_week_wait(self, monkeypatch,
                                                    no_real_sleep):
        """If credits will cover the spend, waiting for the weekly reset is
        the wrong response even when WEEK_WAIT is on."""
        monkeypatch.setenv("METASCIENCE_USAGE_IGNORE_WEEKLY", "1")
        monkeypatch.setenv("METASCIENCE_USAGE_WEEK_WAIT", "1")
        monkeypatch.setattr(usage_guard, "probe_usage",
                            _fake_probe([(0, 100)]))
        asyncio.run(usage_guard.guard())
        assert no_real_sleep == []

    def test_the_stop_names_the_override(self, monkeypatch, no_real_sleep):
        """An operator who hits this has to be told how to proceed.

        The exception is what they see; a hint that lives only in a log line
        or a docstring reaches nobody.
        """
        monkeypatch.setattr(usage_guard, "probe_usage",
                            _fake_probe([(0, 100)]))
        with pytest.raises(usage_guard.WeeklyLimitReached,
                           match="--ignore-weekly-limit"):
            asyncio.run(usage_guard.guard())


class TestCliOverrides:
    """The flags have to exist on the commands people actually run, and they
    have to write the env knobs the guard reads -- not a second copy of the
    policy that can drift.
    """

    def test_apply_cli_overrides_writes_the_env_the_guard_reads(
            self, monkeypatch, no_real_sleep):
        usage_guard.apply_cli_overrides(
            no_usage_guard=True, ignore_weekly_limit=True)
        assert usage_guard.os.environ["METASCIENCE_USAGE_GUARD"] == "0"
        assert usage_guard.os.environ["METASCIENCE_USAGE_IGNORE_WEEKLY"] == "1"
        probe = _fake_probe([(0, 100)])
        monkeypatch.setattr(usage_guard, "probe_usage", probe)
        asyncio.run(usage_guard.guard())
        assert probe.calls == []            # complete disable: never probed

    def test_apply_cli_overrides_false_does_not_undo_an_exported_env(
            self, monkeypatch):
        monkeypatch.setenv("METASCIENCE_USAGE_GUARD", "0")
        monkeypatch.setenv("METASCIENCE_USAGE_IGNORE_WEEKLY", "1")
        usage_guard.apply_cli_overrides(
            no_usage_guard=False, ignore_weekly_limit=False)
        assert usage_guard.os.environ["METASCIENCE_USAGE_GUARD"] == "0"
        assert usage_guard.os.environ["METASCIENCE_USAGE_IGNORE_WEEKLY"] == "1"

    def test_ignore_weekly_flag_alone_still_probes(self, monkeypatch,
                                                   no_real_sleep):
        usage_guard.apply_cli_overrides(ignore_weekly_limit=True)
        probe = _fake_probe([(0, 100)])
        monkeypatch.setattr(usage_guard, "probe_usage", probe)
        asyncio.run(usage_guard.guard())
        assert probe.calls == [1]

    @staticmethod
    def _flags(command_name: str) -> set[str]:
        """The --flags Click actually accepts, not the wrapped help text.

        Rich truncates long option names with an ellipsis at the default
        terminal width (`--ignore-weekly-li…`), so searching the help
        string for the full flag is a test of the renderer, not of the
        command.
        """
        from typer.main import get_command
        from forensic_metascience_ai_toolkit.cli import app
        cmd = get_command(app).commands[command_name]
        names: set[str] = set()
        for p in cmd.params:
            names.update(p.opts)
            names.update(p.secondary_opts)
        return names

    def test_analyze_declares_both_overrides(self):
        flags = self._flags("analyze")
        assert "--ignore-weekly-limit" in flags
        assert "--no-usage-guard" in flags

    def test_batch_declares_both_overrides(self):
        flags = self._flags("batch")
        assert "--ignore-weekly-limit" in flags
        assert "--no-usage-guard" in flags

    def test_analyze_does_not_file_weekly_limit_as_a_crash(self):
        """WeeklyLimitReached must be caught before the BaseException crash
        record. A quota stop is not an analysis failure, and nothing has
        been spent yet (the guard runs before spawn).
        """
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1]
               / "src" / "forensic_metascience_ai_toolkit" / "cli.py").read_text()
        weekly = src.find("except WeeklyLimitReached")
        crash = src.find("except BaseException")
        assert weekly != -1 and crash != -1 and weekly < crash, (
            "WeeklyLimitReached must be handled before the crash record"
        )


def test_interval_gate_skips_repeat_probes(monkeypatch, no_real_sleep):
    """A probe costs quota, so back-to-back calls must not each probe."""
    monkeypatch.setenv("METASCIENCE_USAGE_INTERVAL_MIN", "25")
    probe = _fake_probe([(27, 53)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)

    async def three_calls():
        await usage_guard.guard()
        await usage_guard.guard()
        await usage_guard.guard()

    asyncio.run(three_calls())
    assert len(probe.calls) == 1


def test_zero_interval_probes_every_call(monkeypatch, no_real_sleep):
    monkeypatch.setenv("METASCIENCE_USAGE_INTERVAL_MIN", "0")
    probe = _fake_probe([(27, 53)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)

    async def two_calls():
        await usage_guard.guard()
        await usage_guard.guard()

    asyncio.run(two_calls())
    assert len(probe.calls) == 2


def test_concurrent_callers_share_one_probe(monkeypatch, no_real_sleep):
    """Batch workers pause together instead of each spending a probe."""
    monkeypatch.setenv("METASCIENCE_USAGE_THRESHOLD", "80")
    probe = _fake_probe([(90, 60), (10, 61)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)

    async def five_workers():
        await asyncio.gather(*(usage_guard.guard() for _ in range(5)))

    asyncio.run(five_workers())
    assert len(probe.calls) == 2   # one worker probed and waited; the rest gated


def test_guard_usable_across_separate_event_loops(monkeypatch, no_real_sleep):
    """asyncio.Lock cannot be reused across loops; the guard must not break when
    a process calls asyncio.run() more than once (CLI, then batch, then eval)."""
    monkeypatch.setenv("METASCIENCE_USAGE_INTERVAL_MIN", "0")
    probe = _fake_probe([(27, 53)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)

    asyncio.run(usage_guard.guard())
    asyncio.run(usage_guard.guard())   # second loop — must not raise
    assert len(probe.calls) == 2


def test_bad_env_values_fall_back_to_defaults(monkeypatch, no_real_sleep):
    monkeypatch.setenv("METASCIENCE_USAGE_THRESHOLD", "not-a-number")
    probe = _fake_probe([(95, 60), (5, 61)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)
    asyncio.run(usage_guard.guard())
    # Default threshold still applied: 95% paused.
    assert len(no_real_sleep) == 1


@pytest.mark.parametrize("session_pct,should_pause", [(89, False), (90, True)])
def test_default_threshold_is_90(monkeypatch, no_real_sleep, session_pct, should_pause):
    """Pin the default: 89% runs, 90% pauses."""
    assert usage_guard.DEFAULT_THRESHOLD_PCT == 90.0
    probe = _fake_probe([(session_pct, 60), (5, 61)])
    monkeypatch.setattr(usage_guard, "probe_usage", probe)
    asyncio.run(usage_guard.guard())
    assert bool(no_real_sleep) is should_pause


# --- probe subprocess ----------------------------------------------------

def test_probe_usage_parses_cli_json(monkeypatch):
    import json

    class FakeProc:
        returncode = 0

        async def communicate(self):
            payload = json.dumps({"result": USAGE_TEXT}).encode()
            return payload, b""

        async def wait(self):
            return 0

        def kill(self):
            pass

    async def fake_exec(*args, **kwargs):
        assert args[:4] == ("claude", "-p", "/usage", "--output-format")
        assert "CLAUDECODE" not in kwargs["env"]
        return FakeProc()

    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setattr(usage_guard.asyncio, "create_subprocess_exec", fake_exec)
    assert asyncio.run(usage_guard.probe_usage()) == (27, 53)


def test_probe_usage_missing_binary_fails_open(monkeypatch):
    async def fake_exec(*args, **kwargs):
        raise FileNotFoundError("claude")

    monkeypatch.setattr(usage_guard.asyncio, "create_subprocess_exec", fake_exec)
    assert asyncio.run(usage_guard.probe_usage()) == (None, None)


def test_probe_usage_garbage_output_fails_open(monkeypatch):
    class FakeProc:
        async def communicate(self):
            return b"not json", b""

        async def wait(self):
            return 0

        def kill(self):
            pass

    async def fake_exec(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr(usage_guard.asyncio, "create_subprocess_exec", fake_exec)
    assert asyncio.run(usage_guard.probe_usage()) == (None, None)


# --- wiring --------------------------------------------------------------

def test_run_stage_guards_before_spawning_claude(monkeypatch):
    """The hook must sit in _run_stage, so sweep, editorial and repair calls are
    all covered by one guard."""
    from forensic_metascience_ai_toolkit import agent

    order = []

    async def fake_guard(*a, **k):
        order.append("guard")

    class FakeProc:
        stdout = None
        stderr = None

        async def wait(self):
            return 0

    async def fake_exec(*args, **kwargs):
        order.append("spawn")
        raise AssertionError("stop here — we only care about call order")

    monkeypatch.setattr(agent, "usage_guard", fake_guard)
    monkeypatch.setattr(agent.asyncio, "create_subprocess_exec", fake_exec)

    with pytest.raises(AssertionError):
        # The prompt is a required argument now: it goes down stdin, never
        # on argv (a single argv entry is capped at 128 KB on Linux).
        asyncio.run(agent._run_stage(["claude", "-p"], "the prompt"))

    assert order == ["guard", "spawn"]


def test_grok_backend_never_spawns_a_usage_probe(monkeypatch):
    """`UNSUPPORTED` is a distinct state from (None, None) fail-open."""
    spawned = []

    async def fake_exec(*args, **kwargs):
        spawned.append(args)
        raise AssertionError("grok has no /usage probe")

    monkeypatch.setattr(usage_guard.asyncio, "create_subprocess_exec", fake_exec)
    from forensic_metascience_ai_toolkit.llm_backend import GROK
    result = asyncio.run(usage_guard.probe_usage(backend=GROK))
    assert result is usage_guard.UNSUPPORTED
    assert spawned == []


# --- codex ---------------------------------------------------------------

CODEX_RATE_LIMITS = {
    "jsonrpc": "2.0", "id": 2,
    "result": {"rateLimits": {
        "planType": "plus", "rateLimitReachedType": None,
        "primary": {"usedPercent": 91.4, "windowDurationMins": 300,
                    "resetsAt": 1756830000},
        "secondary": {"usedPercent": 27, "windowDurationMins": 10080,
                      "resetsAt": 1757200000},
    }},
}


class TestCodexUsageIsGuardedByTheSameGates:
    """`--backend codex` used to be reported `usage_guard:
    unsupported_for_backend` and ran unguarded into its 5-hour window. The
    probe is `codex app-server`'s account/rateLimits/read; the gates, the
    thresholds and the fail-open contract are the Claude ones."""

    def test_parse_reads_both_windows_and_rounds(self):
        parsed = usage_guard.parse_codex_rate_limits(CODEX_RATE_LIMITS)
        assert parsed["session_pct"] == 91
        assert parsed["week_pct"] == 27
        assert parsed["session_window_min"] == 300
        assert parsed["plan"] == "plus"

    def test_a_missing_gauge_is_none_not_zero(self):
        parsed = usage_guard.parse_codex_rate_limits({"result": {"rateLimits": {}}})
        assert parsed["session_pct"] is None and parsed["week_pct"] is None
        assert usage_guard.parse_codex_rate_limits({})["session_pct"] is None

    def test_live_week_only_primary_is_not_a_five_hour_pause(self, monkeypatch, no_real_sleep):
        response = {"result": {"rateLimits": {"primary": {
            "usedPercent": 96, "windowDurationMins": 10080, "resetsAt": 1789474240},
            "secondary": None}}}
        parsed = usage_guard.parse_codex_rate_limits(response)
        assert parsed["session_pct"] is None
        assert parsed["week_pct"] == 96
        assert parsed["week_resets_at"] == 1789474240
        monkeypatch.setattr(usage_guard, "probe_usage", _fake_probe([(None, 96)]))
        asyncio.run(usage_guard.guard(backend="codex"))
        assert no_real_sleep == []

    def test_week_only_primary_still_enforces_weekly_stop(self, monkeypatch, no_real_sleep):
        parsed = usage_guard.parse_codex_rate_limits({"result": {"rateLimits": {
            "primary": {"usedPercent": 97, "windowDurationMins": 10080}}}})
        monkeypatch.setattr(usage_guard, "probe_usage", _fake_probe([
            (parsed["session_pct"], parsed["week_pct"])]))
        with pytest.raises(usage_guard.WeeklyLimitReached):
            asyncio.run(usage_guard.guard(backend="codex"))

    def test_duration_overrides_position_and_main_bucket_overrides_spark(self):
        parsed = usage_guard.parse_codex_rate_limits({"result": {
            "rateLimits": {"primary": {"usedPercent": 1, "windowDurationMins": 300}},
            "rateLimitsByLimitId": {"codex": {
                "primary": {"usedPercent": 96, "windowDurationMins": 10080},
                "secondary": {"usedPercent": 25, "windowDurationMins": 300}},
                "codex_bengalfox": {"primary": {"usedPercent": 0, "windowDurationMins": 300}}}}})
        assert (parsed["session_pct"], parsed["week_pct"]) == (25, 96)

    def test_unknown_duration_is_not_silently_a_session(self):
        parsed = usage_guard.parse_codex_rate_limits({"result": {"rateLimits": {
            "primary": {"usedPercent": 99, "windowDurationMins": 1440}}}})
        assert parsed["session_pct"] is None and parsed["week_pct"] is None

    def test_probe_usage_dispatches_codex_to_the_app_server_probe(self, monkeypatch):
        async def fake_codex(timeout=None):
            return (91, 27)
        monkeypatch.setattr(usage_guard, "probe_codex_usage", fake_codex)
        assert asyncio.run(usage_guard.probe_usage(backend="codex")) == (91, 27)

    def test_grok_is_still_unsupported(self):
        assert asyncio.run(usage_guard.probe_usage(backend="grok")) is usage_guard.UNSUPPORTED

    def test_guard_pauses_codex_at_ninety(self, monkeypatch, no_real_sleep):
        monkeypatch.setenv("METASCIENCE_USAGE_POLL_MIN", "15")
        readings = iter([(91, 27), (94, 27), (3, 27)])

        async def fake_codex(timeout=None):
            return next(readings)
        monkeypatch.setattr(usage_guard, "probe_codex_usage", fake_codex)
        asyncio.run(usage_guard.guard(backend="codex"))
        assert no_real_sleep == [15 * 60, 15 * 60]

    def test_guard_stops_codex_on_a_spent_week(self, monkeypatch, no_real_sleep):
        async def fake_codex(timeout=None):
            return (5, 99)
        monkeypatch.setattr(usage_guard, "probe_codex_usage", fake_codex)
        with pytest.raises(usage_guard.WeeklyLimitReached):
            asyncio.run(usage_guard.guard(backend="codex"))

    def test_no_codex_binary_fails_open(self, monkeypatch):
        async def boom(*a, **k):
            raise FileNotFoundError("codex")
        monkeypatch.setattr(usage_guard.asyncio, "create_subprocess_exec", boom)
        assert asyncio.run(usage_guard.probe_codex_usage()) == (None, None)

    def test_a_server_that_exits_without_answering_fails_open(self, monkeypatch):
        class _Stdin:
            def write(self, b): pass
            async def drain(self): pass

        class _Stdout:
            async def readline(self):
                return b""  # EOF: the server died before answering

        class _Proc:
            stdin, stdout = _Stdin(), _Stdout()
            def kill(self): pass
            async def wait(self): return 0

        async def fake_exec(*a, **k):
            return _Proc()
        monkeypatch.setattr(usage_guard.asyncio, "create_subprocess_exec", fake_exec)
        assert asyncio.run(usage_guard.probe_codex_usage()) == (None, None)

    def test_a_server_that_never_answers_times_out_open(self, monkeypatch):
        class _Stdin:
            def write(self, b): pass
            async def drain(self): pass

        class _Stdout:
            async def readline(self):
                await asyncio.sleep(3600)
                return b""

        class _Proc:
            stdin, stdout = _Stdin(), _Stdout()
            def kill(self): pass
            async def wait(self): return 0

        async def fake_exec(*a, **k):
            return _Proc()
        monkeypatch.setattr(usage_guard.asyncio, "create_subprocess_exec", fake_exec)
        assert asyncio.run(usage_guard.probe_codex_usage(timeout=0.05)) == (None, None)

    def test_the_answer_is_read_off_the_stream_and_the_server_is_killed(self, monkeypatch):
        import json as _json
        lines = [b'{"jsonrpc":"2.0","id":1,"result":{}}\n',
                 b'{"jsonrpc":"2.0","method":"noise","params":{}}\n',
                 b'not json\n',
                 _json.dumps(CODEX_RATE_LIMITS).encode() + b"\n"]
        killed = []

        class _Stdin:
            sent = []
            def write(self, b): self.sent.append(b)
            async def drain(self): pass

        class _Stdout:
            async def readline(self):
                return lines.pop(0) if lines else b""

        class _Proc:
            stdin, stdout = _Stdin(), _Stdout()
            def kill(self): killed.append(1)
            async def wait(self): return 0

        async def fake_exec(*a, **k):
            return _Proc()
        monkeypatch.setattr(usage_guard.asyncio, "create_subprocess_exec", fake_exec)
        assert asyncio.run(usage_guard.probe_codex_usage()) == (91, 27)
        assert killed == [1]
        methods = [_json.loads(b)["method"] for b in _Proc.stdin.sent]
        assert methods == ["initialize", "initialized", "account/rateLimits/read"]
