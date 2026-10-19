"""Live progress reporting during a stage.

A run used to show `Running analysis...` and nothing else for tens of minutes,
so an operator could not tell a healthy sweep from a hung one. `_run_stage` now
takes an `on_progress` callback fed from the stream-json events it already
parses.

The invariant that matters most here is NEGATIVE: the display must never cost a
paid run. A callback that raises, and the presence of the callback at all, must
leave the recorded result byte-identical to a run without one.
"""

import asyncio
import json

import pytest

from forensic_metascience_ai_toolkit import agent
from forensic_metascience_ai_toolkit.cli import _fmt_elapsed, _fmt_tokens, _render_progress


def _events(*, turns=2, tools_per_turn=1, out_per_turn=100):
    """Synthetic stream-json lines: N assistant turns, then a result event."""
    lines = []
    for i in range(turns):
        lines.append({
            "type": "assistant",
            "message": {
                "id": f"msg_{i}",
                "usage": {
                    "input_tokens": 5,
                    "output_tokens": out_per_turn,
                    "cache_creation_input_tokens": 1000,
                    "cache_read_input_tokens": 2000,
                },
                "content": (
                    [{"type": "text", "text": "thinking"}]
                    + [{"type": "tool_use", "name": "grim_test"}] * tools_per_turn
                ),
            },
        })
    lines.append({
        "type": "result",
        "result": "done",
        "total_cost_usd": 1.25,
        "usage": {
            "input_tokens": 11,
            "output_tokens": 999,
            "cache_creation_input_tokens": 2000,
            "cache_read_input_tokens": 4000,
        },
    })
    return b"".join((json.dumps(e) + "\n").encode() for e in lines)


class _FakeStdin:
    """A fake process needs a stdin, because the prompt goes down it.

    `_run_stage` writes the prompt to stdin and closes the pipe -- `claude -p`
    reads until EOF -- rather than passing it on argv, where a large prompt dies
    at Popen with `OSError: [Errno 7]`. A fake without `stdin` raises
    AttributeError before a single progress event is read. Records what was
    written so a test can assert the prompt reached the process."""

    def __init__(self):
        self.written = b""

    def write(self, data: bytes) -> None:
        self.written += data

    def close(self) -> None:
        pass

    async def drain(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass


class _FakeProc:
    def __init__(self, payload: bytes):
        self.stdout = asyncio.StreamReader()
        self.stdout.feed_data(payload)
        self.stdout.feed_eof()
        self.stderr = asyncio.StreamReader()
        self.stderr.feed_eof()
        self.stdin = _FakeStdin()

    async def wait(self):
        return 0

    def kill(self):  # pragma: no cover - only on timeout paths
        pass


@pytest.fixture(autouse=True)
def _no_env_gates(monkeypatch):
    """The gates are tested elsewhere; keep this file about progress."""
    monkeypatch.setattr(agent, "_assert_ready", lambda *a, **k: None)

    async def _no_guard(*a, **k):
        return None

    monkeypatch.setattr(agent, "usage_guard", _no_guard)


def _run(monkeypatch, payload, **kwargs):
    async def fake_exec(*a, **kw):
        return _FakeProc(payload)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    # `prompt` is a REQUIRED positional in this build: it goes down stdin,
    # never on argv, because a large one dies at Popen with Errno 7. Dan's
    # original call omitted it; supplying one changes nothing this file tests.
    return asyncio.run(
        agent._run_stage(["claude", "-p", "x"], "a prompt", **kwargs))


class TestCallbackIsInvoked:
    def test_snapshots_arrive(self, monkeypatch):
        seen = []
        _run(monkeypatch, _events(turns=3), on_progress=seen.append,
             stage_label="sweep")
        assert seen, "no progress snapshots were emitted"
        assert all(s["stage"] == "sweep" for s in seen)

    def test_counters_are_monotonic(self, monkeypatch):
        seen = []
        _run(monkeypatch, _events(turns=4, tools_per_turn=2),
             on_progress=seen.append)
        for key in ("tool_calls", "output_tokens", "elapsed"):
            values = [s[key] for s in seen]
            assert values == sorted(values), f"{key} went backwards: {values}"

    def test_tool_calls_count_tool_use_blocks_only(self, monkeypatch):
        seen = []
        _run(monkeypatch, _events(turns=3, tools_per_turn=2),
             on_progress=seen.append)
        assert seen[-1]["tool_calls"] == 6      # not 9: text blocks don't count

    def test_current_tool_is_the_last_tool_use_name(self, monkeypatch):
        seen = []
        _run(monkeypatch, _events(turns=2, tools_per_turn=1),
             on_progress=seen.append)
        named = [s.get("current_tool") for s in seen if s.get("current_tool")]
        assert named, "status snapshots must name the tool in flight"
        assert named[-1] == "grim_test"

    def test_repeated_message_id_is_counted_once(self, monkeypatch):
        """The CLI re-emits a turn per content block; usage must not inflate."""
        dup = json.dumps({
            "type": "assistant",
            "message": {"id": "same", "usage": {"output_tokens": 50},
                        "content": [{"type": "text", "text": "a"}]},
        }) + "\n"
        payload = (dup * 3).encode() + json.dumps(
            {"type": "result", "result": "ok", "usage": {}}).encode() + b"\n"
        seen = []
        _run(monkeypatch, payload, on_progress=seen.append)
        assert seen[-1]["output_tokens"] == 50

    def test_elapsed_is_present_and_non_negative(self, monkeypatch):
        seen = []
        _run(monkeypatch, _events(), on_progress=seen.append)
        assert all(s["elapsed"] >= 0 for s in seen)


class TestTheDisplayCannotCostARun:
    """The whole reason the callback is wrapped."""

    def test_a_raising_callback_does_not_fail_the_stage(self, monkeypatch):
        def boom(_):
            raise RuntimeError("display exploded")

        result = _run(monkeypatch, _events(), on_progress=boom)
        assert result["result"] == "done"
        assert result["is_error"] is False

    def test_recorded_totals_ignore_the_live_counters(self, monkeypatch):
        """Live per-turn usage must NOT be added to the returned totals.

        The `result` branch accumulates with `+=`, so summing per-turn usage
        into the same variables would double-count every token and write the
        inflated figure into run_meta.json.
        """
        payload = _events(turns=3)
        without = _run(monkeypatch, payload)
        with_cb = _run(monkeypatch, payload, on_progress=lambda _: None)
        for key in ("input_tokens", "output_tokens",
                    "cache_creation_input_tokens", "cache_read_input_tokens",
                    "cost_usd"):
            assert without[key] == with_cb[key], key
        # And they equal the `result` event alone, not the per-turn sum.
        assert with_cb["output_tokens"] == 999

    def test_omitting_the_callback_changes_nothing(self, monkeypatch):
        result = _run(monkeypatch, _events())
        assert result["result"] == "done"
        assert result["cost_usd"] == 1.25


class TestElapsedFormatting:
    @pytest.mark.parametrize("seconds,expected", [
        (0, "0:00"), (7, "0:07"), (59, "0:59"),
        (60, "1:00"), (90, "1:30"), (2700, "45:00"),
        (3599, "59:59"),                 # last second before the hour form
        (3600, "1:00:00"),               # rollover
        (7503, "2:05:03"),
    ])
    def test_hours_appear_only_past_sixty_minutes(self, seconds, expected):
        assert _fmt_elapsed(seconds) == expected

    def test_negative_is_clamped(self):
        assert _fmt_elapsed(-5) == "0:00"


class TestTheClockTicksBetweenEvents:
    """Elapsed must come from the redraw, not from the snapshot.

    Snapshots arrive only when the CLI emits an event, and nothing is emitted
    during a long tool call. Observed on a real run before this was fixed: nine
    consecutive redraws all printed `2:28` while the spinner kept spinning --
    the display said "possibly hung" during the exact stretch it exists to
    reassure about.
    """

    def test_caller_supplied_elapsed_overrides_a_stale_snapshot(self):
        stale = {"stage": "sweep", "tool_calls": 10, "elapsed": 148.0}
        assert "2:28" in _render_progress(stale)                 # snapshot's own
        assert "3:20" in _render_progress(stale, elapsed=200.0)  # caller's clock
        assert "2:28" not in _render_progress(stale, elapsed=200.0)

    def test_elapsed_advances_while_counters_hold_steady(self):
        """The silent-gap case: same snapshot, later wall clock."""
        snap = {"stage": "sweep", "tool_calls": 10,
                "cache_read_input_tokens": 238_100, "output_tokens": 4,
                "elapsed": 148.0}
        lines = [_render_progress(snap, elapsed=t) for t in (148, 149, 150)]
        assert [l.rsplit("· ", 1)[-1] for l in lines] == ["2:28", "2:29", "2:30"]
        assert all("238.1k in" in l for l in lines)
        assert all("stage 1 running" in l for l in lines)

    def test_the_pre_snapshot_line_also_shows_a_clock(self):
        """Before the first event there is still something moving."""
        assert "0:05" in _render_progress(None, elapsed=5)


class TestRendering:
    def test_no_snapshot_falls_back_to_the_old_text(self):
        assert "Running analysis" in _render_progress(None)

    def test_input_side_tokens_are_summed(self):
        """`input_tokens` alone reads as ~0 on real runs and looks broken."""
        line = _render_progress({
            "stage": "sweep", "tool_calls": 3, "current_tool": "grim_check",
            "input_tokens": 20, "cache_creation_input_tokens": 113921,
            "cache_read_input_tokens": 607415, "output_tokens": 6834,
            "elapsed": 221,
        })
        assert "721.4k in" in line
        assert "6.8k out" in line
        assert "3:41" in line
        assert "stage 1 running" in line
        assert "grim_check" in line

    def test_current_tool_is_cyan_not_blinking(self):
        line = _render_progress(
            {"stage": "sweep", "current_tool": "check_table", "elapsed": 1})
        assert "stage 1 running" in line
        assert "check_table" in line
        assert "cyan" in line
        assert "blink" not in line

    def test_mcp_prefix_is_stripped(self):
        line = _render_progress({
            "stage": "sweep",
            "current_tool": "mcp__forensic_metascience__grim_check",
            "elapsed": 1,
        })
        assert "grim_check" in line
        assert "mcp__" not in line

    def test_editorial_is_stage_2(self):
        line = _render_progress(
            {"stage": "editorial", "current_tool": "Read", "elapsed": 1})
        assert "stage 2 running" in line

    def test_live_tokens_false_drops_the_token_segment(self):
        """Codex streams no per-turn usage (the figures arrive only in the
        final turn.completed), so its counters would print a permanent
        `0 in / 0 out` -- the broken-counter look this module's own docstring
        warns about. The stamp drops the segment instead."""
        line = _render_progress({
            "stage": "tool_agent", "current_tool": "grim_check",
            "elapsed": 61, "live_tokens": False,
            "input_tokens": 0, "output_tokens": 0,
        })
        assert "in /" not in line
        assert "out" not in line
        assert "grim_check" in line
        assert "1:01" in line

    def test_absent_live_tokens_keeps_the_segment(self):
        """Claude and grok stream real counters; only an explicit False
        stamp may drop them."""
        line = _render_progress({
            "stage": "tool_agent", "current_tool": "grim_check",
            "elapsed": 61, "input_tokens": 100, "output_tokens": 5,
        })
        assert "in /" in line and "out" in line


class TestLiveToolName:
    def test_mcp_prefix_and_grok_use_tool_unwrap(self):
        from forensic_metascience_ai_toolkit.agent import _live_tool_name
        assert _live_tool_name({
            "name": "mcp__forensic_metascience__grim_check"}) == "grim_check"
        assert _live_tool_name({
            "name": "use_tool",
            "input": {"tool_name": "forensic_metascience__check_table"},
        }) == "check_table"
        assert _live_tool_name({"name": "Read"}) == "Read"


class TestLiveBatchStatus:
    def test_renderable_names_each_in_flight_paper(self):
        from rich.console import Console
        from forensic_metascience_ai_toolkit.progress import LiveBatchStatus
        mon = LiveBatchStatus(live=False, periodic_log=False)
        mon.begin("paper-a")
        mon.update("paper-a", {
            "stage": "sweep", "current_tool": "grim_check",
            "input_tokens": 10, "output_tokens": 2,
        })
        mon.begin("paper-b")
        mon.update("paper-b", {
            "stage": "editorial", "current_tool": "Read",
            "input_tokens": 5, "output_tokens": 1,
        })
        console = Console(record=True, width=160, color_system=None)
        console.print(mon.renderable())
        text = console.export_text()
        assert "paper-a" in text and "paper-b" in text
        assert "grim_check" in text
        assert "stage 1 running" in text
        assert "stage 2 running" in text

    def test_the_two_parallel_analysts_get_a_line_each(self):
        """The bug this replaced: one cell, so they overwrote each other.

        Both agents run concurrently and both emit snapshots. Keyed by
        `stage`, they occupy separate slots; keyed by nothing, the operator
        watched one line flicker between two unrelated stages.
        """
        from rich.console import Console
        from forensic_metascience_ai_toolkit.progress import LiveBatchStatus
        mon = LiveBatchStatus(live=False, periodic_log=False, show_key=False)
        mon.begin("tool_agent")
        mon.begin("science_agent")
        mon.update("tool_agent", {
            "stage": "tool_agent", "current_tool": "get_table",
            "input_tokens": 10, "output_tokens": 2,
        })
        mon.update("science_agent", {
            "stage": "science_agent", "current_tool": "WebSearch",
            "input_tokens": 5, "output_tokens": 1,
        })
        console = Console(record=True, width=160, color_system=None)
        console.print(mon.renderable())
        lines = [ln for ln in console.export_text().splitlines() if ln.strip()]
        assert len(lines) == 2
        assert "tools agent" in lines[0] and "get_table" in lines[0]
        assert "scientific proofreading agent" in lines[1] and "WebSearch" in lines[1]
        # show_key=False: the slot key is already the line's title, so it must
        # not be printed a second time as a prefix.
        assert "tool_agent" not in lines[0]

    def test_a_track_line_shows_no_token_counters(self):
        """A deterministic track has no model, so `0 in / 0 out` would read as
        a broken counter rather than as "this channel has no such number"."""
        line = _render_progress(
            {"stage": "image_track", "kind": "track", "state": "running"},
            elapsed=83, markup=False)
        assert line == "image track : running \u00b7 1:23"
        assert "in /" not in line and "out" not in line

    def test_a_track_reports_its_terminal_state_by_name(self):
        """"Did not run" and "ran and found nothing" are different facts."""
        for state, expect in [("clean", "clean"),
                              ("3 finding row(s)", "3 finding row(s)"),
                              ("engine_missing", "engine_missing"),
                              ("track_timeout", "track_timeout")]:
            line = _render_progress(
                {"stage": "image_track", "kind": "track", "state": state},
                elapsed=1, markup=False)
            assert expect in line

    def test_a_finished_slot_stops_its_clock(self):
        """A line kept on screen must not keep counting. A finished stage
        whose elapsed climbs reads as one that is still working."""
        import time as _time
        from forensic_metascience_ai_toolkit.progress import LiveBatchStatus
        mon = LiveBatchStatus(live=False, periodic_log=False, show_key=False)
        mon.begin("tool_agent")
        mon.update("tool_agent", {"stage": "tool_agent",
                                  "current_tool": "get_table",
                                  "input_tokens": 10, "output_tokens": 2})
        slot = mon.slots["tool_agent"]
        slot["t0"] -= 100                       # pretend it ran for 1:40
        mon.update("tool_agent", {"stage": "tool_agent", "done": True})
        frozen = mon._elapsed(slot, _time.monotonic())
        later = mon._elapsed(slot, _time.monotonic() + 500)
        assert frozen == later
        # The bare done marker must not wipe what the stage last reported.
        assert slot["snapshot"]["current_tool"] == "get_table"
        assert slot["snapshot"]["input_tokens"] == 10

    def test_a_finished_track_keeps_its_terminal_state(self):
        from rich.console import Console
        from forensic_metascience_ai_toolkit.progress import LiveBatchStatus
        mon = LiveBatchStatus(live=False, periodic_log=False, show_key=False)
        mon.begin("image_track")
        mon.update("image_track", {"stage": "image_track", "kind": "track",
                                   "state": "running"})
        mon.update("image_track", {"stage": "image_track", "kind": "track",
                                   "state": "3 finding row(s)", "done": True})
        console = Console(record=True, width=160, color_system=None)
        console.print(mon.renderable())
        assert "3 finding row(s)" in console.export_text()

    def test_a_paper_keyed_clock_survives_a_stage_finishing(self):
        """The batch view keys one line per PAPER, and every stage of that
        paper reports into it. A stage-scoped `done` must not stop that clock.

        Measured 2026-08-22 on a two-paper sonnet batch: both lines sat at
        `0:00` for the whole run while the token counters climbed past 300k.
        The image track refuses in well under a second on a paper with no
        figures, its done marker froze the paper's clock, and the operator
        lost the one signal that says whether a silent run is still alive.
        """
        import time as _time
        from forensic_metascience_ai_toolkit.progress import LiveBatchStatus
        mon = LiveBatchStatus(live=False, periodic_log=False)
        mon.begin("10.1136--bmjopen-2023-082989")
        for stage, snap in [
            ("image_track", {"stage": "image_track", "kind": "track",
                             "state": "running"}),
            ("image_track", {"stage": "image_track", "kind": "track",
                             "state": "engine_missing", "done": True}),
            ("text_track", {"stage": "text_track", "kind": "track",
                            "state": "clean", "done": True}),
            ("tool_agent", {"stage": "tool_agent", "done": True}),
            ("science_agent", {"stage": "science_agent",
                               "current_tool": "get_table",
                               "input_tokens": 328_600, "output_tokens": 11}),
        ]:
            mon.update("10.1136--bmjopen-2023-082989", snap)
        slot = mon.slots["10.1136--bmjopen-2023-082989"]
        now = _time.monotonic()
        # `approx`, NOT `==`. `_elapsed` is `(t_end or now) - t0`, so this
        # computes ((now+500) - t0) - (now - t0) on monotonic values in the
        # hundreds -- catastrophic cancellation. The exact form failed on 2 of
        # 6 identical runs. The property under test is that advancing `now`
        # advances the clock by the same amount; the last bit of a float is not
        # part of that property, and a suite with an intermittent failure trains
        # everyone to re-run until green.
        assert mon._elapsed(slot, now + 500) - mon._elapsed(slot, now) == pytest.approx(500)

    def test_a_stage_keyed_clock_still_stops_on_a_foreign_done(self):
        """The analyze view keys by stage, so only that stage's own marker
        retires its line -- another stage finishing must not touch it."""
        import time as _time
        from forensic_metascience_ai_toolkit.progress import LiveBatchStatus
        mon = LiveBatchStatus(live=False, periodic_log=False, show_key=False)
        mon.begin("science_agent")
        mon.update("science_agent", {"stage": "science_agent",
                                     "current_tool": "WebSearch"})
        mon.update("science_agent", {"stage": "image_track", "done": True})
        slot = mon.slots["science_agent"]
        now = _time.monotonic()
        # `approx`, NOT `==`. `_elapsed` is `(t_end or now) - t0`, so this
        # computes ((now+500) - t0) - (now - t0) on monotonic values in the
        # hundreds -- catastrophic cancellation. The exact form failed on 2 of
        # 6 identical runs. The property under test is that advancing `now`
        # advances the clock by the same amount; the last bit of a float is not
        # part of that property, and a suite with an intermittent failure trains
        # everyone to re-run until green.
        assert mon._elapsed(slot, now + 500) - mon._elapsed(slot, now) == pytest.approx(500)
        mon.update("science_agent", {"stage": "science_agent", "done": True})
        assert mon._elapsed(slot, now + 500) == mon._elapsed(slot, now + 900)

    def test_transient_defaults_to_the_batch_behaviour(self):
        from forensic_metascience_ai_toolkit.progress import LiveBatchStatus
        assert LiveBatchStatus(live=False).transient is True
        assert LiveBatchStatus(live=False, transient=False).transient is False

    def test_no_dollar_figure_is_shown(self):
        """Cost is not live-computable without a price table; never fake it."""
        line = _render_progress({
            "stage": "sweep", "tool_calls": 1, "output_tokens": 10,
            "elapsed": 5,
        })
        assert "$" not in line

    @pytest.mark.parametrize("n,expected", [
        (0, "0"), (999, "999"), (1000, "1.0k"), (12345, "12.3k"),
        (1_000_000, "1.0M"), (1_250_000, "1.2M"),
    ])
    def test_token_shortening(self, n, expected):
        assert _fmt_tokens(n) == expected


class TestBatchGrid:
    """The `metascience batch` grid: a row per stage of every paper in flight."""

    @staticmethod
    def _text(mon, width=160):
        from rich.console import Console
        console = Console(record=True, width=width, color_system=None)
        console.print(mon.renderable())
        return console.export_text()

    def test_each_stage_of_each_paper_gets_its_own_row(self):
        """The paper-keyed line showed whichever stage reported last."""
        from forensic_metascience_ai_toolkit.progress import BatchGrid
        mon = BatchGrid(total=5, live=False, periodic_log=False)
        mon.begin("paper-a")
        mon.update("paper-a", {"stage": "tool_agent", "current_tool": "grim_check",
                               "input_tokens": 1200, "output_tokens": 30})
        mon.update("paper-a", {"stage": "science_agent", "current_tool": "WebSearch",
                               "input_tokens": 50, "output_tokens": 5})
        mon.begin("paper-b")
        mon.update("paper-b", {"stage": "image_track", "kind": "track",
                               "state": "running"})
        lines = self._text(mon).splitlines()
        row = {ln.split()[0] if ln.strip() else "": ln for ln in lines}
        assert any("paper-a" in ln and "tools agent" in ln and "grim_check" in ln
                   and "1.2k" in ln for ln in lines)
        assert any("proofreading" in ln and "WebSearch" in ln
                   for ln in lines)
        track = [ln for ln in lines if "image track" in ln]
        assert track and "paper-b" in track[0] and "—" in track[0]
        assert "0 in" not in track[0]
        assert row  # rendered something

    def test_a_finished_stage_says_done_and_stops_only_its_clock(self):
        import time as _time
        from forensic_metascience_ai_toolkit.progress import BatchGrid
        mon = BatchGrid(total=1, live=False, periodic_log=False)
        mon.begin("p")
        mon.update("p", {"stage": "tool_agent", "current_tool": "get_table",
                         "input_tokens": 10})
        mon.update("p", {"stage": "science_agent", "current_tool": "Read"})
        mon.update("p", {"stage": "tool_agent", "done": True})
        stages = mon.slots["p"]["stages"]
        now = _time.monotonic()
        assert mon._elapsed(stages["tool_agent"], now + 500) == \
            mon._elapsed(stages["tool_agent"], now)
        assert mon._elapsed(stages["science_agent"], now + 500) - \
            mon._elapsed(stages["science_agent"], now) == pytest.approx(500)
        # The bare done marker keeps the counters it last reported.
        assert stages["tool_agent"]["snapshot"]["input_tokens"] == 10
        tool_row = [ln for ln in self._text(mon).splitlines()
                    if "tools agent" in ln][0]
        assert "done" in tool_row

    def test_header_counts_the_corpus_and_finished_papers_are_listed(self):
        from forensic_metascience_ai_toolkit.progress import BatchGrid
        mon = BatchGrid(total=6, live=False, periodic_log=False)
        mon.record("already-done", "skip")
        for name, status in [("p1", "ok"), ("p2", "partial"), ("p3", "fail")]:
            mon.begin(name)
            mon.update(name, {"stage": "tool_agent", "current_tool": "x"})
            mon.end(name)
            mon.record(name, status)
        mon.begin("p4")
        text = self._text(mon)
        header = text.splitlines()[0]
        assert "4/6 done" in header and "1 running" in header
        assert "1 queued" in header
        assert "1 ok" in header and "1 partial" in header
        assert "1 failed" in header and "1 skipped" in header
        assert "FAILED" in text and "partial" in text
        assert "already-done" not in text      # a skip gets no row
        assert "starting" in text              # p4 has not reported yet

    def test_markup_in_a_paper_name_is_printed_literally(self):
        from forensic_metascience_ai_toolkit.progress import BatchGrid
        mon = BatchGrid(total=1, live=False, periodic_log=False)
        mon.begin("[bold]weird[/bold]")
        assert "[bold]weird[/bold]" in self._text(mon)

    def test_plain_log_is_throttled_per_row_not_globally(self, capsys):
        """A global window let one paper through per 15 s; ten workers then
        showed each paper every ~2.5 minutes, and a quiet one possibly never."""
        from forensic_metascience_ai_toolkit.progress import BatchGrid
        mon = BatchGrid(total=3, live=False, periodic_log=True)
        for p in ("a", "b", "c"):
            mon.begin(p)
            mon.update(p, {"stage": "tool_agent", "current_tool": "grim_check"})
        out = capsys.readouterr().out.splitlines()
        assert [ln.split()[0] for ln in out] == ["a", "b", "c"]
        # Within the window: silent.
        mon.update("a", {"stage": "tool_agent", "current_tool": "statcheck"})
        assert capsys.readouterr().out == ""
        # A stage finishing is always logged, once.
        mon.update("a", {"stage": "tool_agent", "done": True})
        mon.update("a", {"stage": "tool_agent", "done": True})
        done = capsys.readouterr().out.splitlines()
        assert len(done) == 1 and done[0].endswith("· done")

    def test_live_status_slots_are_throttled_independently(self, capsys):
        """Same defect in the `analyze` view, keyed by stage."""
        from forensic_metascience_ai_toolkit.progress import LiveBatchStatus
        mon = LiveBatchStatus(live=False, periodic_log=True, show_key=False)
        mon.update("tool_agent", {"stage": "tool_agent", "current_tool": "a"})
        mon.update("science_agent", {"stage": "science_agent",
                                     "current_tool": "b"})
        assert len(capsys.readouterr().out.splitlines()) == 2


class TestVerbosePrefix:
    def test_each_paper_task_prefixes_its_own_lines(self, capsys):
        import asyncio
        from forensic_metascience_ai_toolkit.progress import (CURRENT_PAPER,
                                                prefix_stdout_by_paper)

        async def paper(name, chunks):
            CURRENT_PAPER.set(name)
            for c in chunks:
                print(c, end="")
                await asyncio.sleep(0)

        async def main():
            with prefix_stdout_by_paper(enabled=True):
                print("batch header")
                # Partial lines interleave across tasks; each must come out
                # whole and attributed.
                await asyncio.gather(paper("A", ["one ", "line\n", "tail"]),
                                     paper("B", ["two ", "lines\nmore\n"]))

        asyncio.run(main())
        out = capsys.readouterr().out.splitlines()
        assert out[0] == "batch header"
        assert sorted(out[1:]) == sorted(["[A] one line", "[A] tail",
                                          "[B] two lines", "[B] more"])

    def test_disabled_leaves_stdout_alone(self):
        import sys
        from forensic_metascience_ai_toolkit.progress import prefix_stdout_by_paper
        before = sys.stdout
        with prefix_stdout_by_paper(enabled=False):
            assert sys.stdout is before
        assert sys.stdout is before
