"""A progress bar with an ETA, and a plain-text fallback when there isn't one.

A corpus sweep runs for 20-30 minutes with no indication of how much longer.
That is not merely uncomfortable: it is what makes a person kill a run that
was nearly finished, or leave a hung one going for an hour. An ETA is the
difference.

TWO REASONS THIS IS NOT JUST `from tqdm import tqdm`:

  * `tqdm` must stay OPTIONAL. This package's hard dependencies are the ones
    whose absence makes the output WRONG (see `preflight.fatal_checks`); a
    progress bar's absence makes it quieter, which is a different category.
    An install that lacks it degrades to a plain line and keeps working.
  * A bar written to a redirected stdout is noise. A long sweep
    is routinely run with `> log 2>&1`, where tqdm's carriage returns become
    thousands of unreadable lines. When stderr is not a TTY this falls back to
    a periodic one-line report, which is what you actually want in a log.

The ETA is computed from observed throughput rather than assumed to be
uniform: panel harvesting varies by an order of magnitude between a two-figure
clinical paper and a forty-panel micrograph atlas, so a naive
remaining = elapsed / done * left is wrong early and right late. Both are
reported honestly -- the estimate is labelled an estimate.
"""

from __future__ import annotations

import contextvars
import sys
import time
from typing import Any, Iterable, Iterator, Optional


def _fmt(seconds: float) -> str:
    """`1h 04m`, `12m 30s`, `45s` -- never `3847.2 seconds`."""
    if seconds < 0 or seconds != seconds:        # negative or NaN
        return "?"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"


class Progress:
    """Iterate `items`, reporting progress and an ETA.

    Use as a context manager or just iterate it. `note(text)` attaches a
    short label to the current item (the paper being processed), which is the
    thing you actually want on screen when a run stalls.
    """

    def __init__(self, items: Iterable[Any], total: Optional[int] = None,
                 desc: str = "", every_s: float = 15.0,
                 stream=None):
        self.items = items
        if total is None:
            try:
                total = len(items)                # type: ignore[arg-type]
            except TypeError:
                total = None
        self.total = total
        self.desc = desc
        self.every_s = every_s
        self.stream = stream or sys.stderr
        self.n = 0
        self.t0 = time.monotonic()
        self._last = 0.0
        self._label = ""
        self._bar = None
        self._tty = bool(getattr(self.stream, "isatty", lambda: False)())

    # -- the two rendering paths ------------------------------------------
    def _start(self) -> None:
        if not self._tty:
            return
        try:
            from tqdm import tqdm
        except ImportError:
            return                                # plain path; not an error
        self._bar = tqdm(total=self.total, desc=self.desc or None,
                         unit="paper", file=self.stream, dynamic_ncols=True,
                         smoothing=0.3)

    def _line(self, force: bool = False) -> None:
        """The non-TTY path: one line, occasionally, with an ETA."""
        now = time.monotonic()
        if not force and now - self._last < self.every_s:
            return
        self._last = now
        elapsed = now - self.t0
        rate = self.n / elapsed if elapsed > 0 else 0.0
        if self.total and rate > 0:
            eta = _fmt((self.total - self.n) / rate)
            pct = f"{self.n / self.total:.0%}"
            head = f"{self.desc} {self.n}/{self.total} ({pct})"
        else:
            eta = "?"
            head = f"{self.desc} {self.n}"
        print(f"  [{head}]  elapsed {_fmt(elapsed)}  eta ~{eta}"
              f"  {rate * 60:.1f}/min"
              + (f"  {self._label}" if self._label else ""),
              file=self.stream, flush=True)

    # -- api ---------------------------------------------------------------
    def note(self, text: str) -> None:
        """Label the item in flight -- what a stalled run is stuck on."""
        self._label = text
        if self._bar is not None:
            self._bar.set_postfix_str(text[:40], refresh=False)

    def advance(self, label: str = "", n: int = 1) -> None:
        """Count `n` finished items, when the CALLER drives the loop.

        `__iter__` owns both dispatch and counting, which is right for a
        serial pass and impossible for a process pool: the loop that consumes
        results is not the loop that defines the work, and results arrive out
        of order. Use inside `with Progress(...) as bar:` so the bar is still
        started and closed exactly once.
        """
        if label:
            self.note(label)
        self.n += n
        if self._bar is not None:
            self._bar.update(n)
        else:
            self._line()

    def __enter__(self) -> "Progress":
        self._start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __iter__(self) -> Iterator[Any]:
        self._start()
        try:
            for item in self.items:
                yield item
                self.n += 1
                if self._bar is not None:
                    self._bar.update(1)
                else:
                    self._line()
        finally:
            self.close()

    def close(self) -> None:
        if self._bar is not None:
            self._bar.close()
            self._bar = None
        elif self.n:
            self._line(force=True)

    def summary(self) -> str:
        elapsed = time.monotonic() - self.t0
        per = elapsed / self.n if self.n else 0.0
        return (f"{self.n} item(s) in {_fmt(elapsed)} "
                f"({per:.1f}s each, {self.n / elapsed * 60:.1f}/min)"
                if self.n else "nothing processed")


# ---------------------------------------------------------------------------
# Live one-line stage status (analyze + batch). Separate from Progress above:
# that class is a corpus ETA bar; this is "what is THIS paper doing right now".
# ---------------------------------------------------------------------------

_STAGE_TITLES = {
    "sweep": "stage 1 running",
    "editorial": "stage 2 running",
    "analysis": "analysis running",
    "extracting": "extracting",
    # The parallel pipeline's stages (agent.py stamps `stage_label` into every
    # snapshot; parallel.py labels them). Absent from this map they render as
    # raw slugs.
    "tool_agent": "tools agent",
    "science_agent": "scientific proofreading agent",
    "adjudicator": "adjudicator",
    "image_track": "image track",
    "text_track": "text track",
}


def fmt_elapsed_clock(seconds: float) -> str:
    """`m:ss`, rolling to `h:mm:ss` only past the hour.

    A sweep over a 107-page supplement runs well past 45 minutes, so the hour
    form is reachable in ordinary use rather than a theoretical branch.
    """
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def fmt_tokens(n: int) -> str:
    """Compact token counts: 1234 -> 1.2k, 1_200_000 -> 1.2M."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def live_tool_label(name: str | None) -> str:
    """Short name for the status line: `grim_check`, not the MCP prefix."""
    if not name:
        return "thinking"
    text = str(name)
    if "__" in text:
        return text.rpartition("__")[2] or text
    return text


def render_stage_line(
    snapshot: dict | None,
    elapsed: float | None = None,
    *,
    paper: str | None = None,
    markup: bool = True,
) -> str:
    """One status line: stage, flashing current tool, tokens in/out, elapsed.

    `elapsed` overrides the snapshot's own figure and SHOULD be passed by a
    caller redrawing on a timer. Snapshots only arrive when the CLI emits an
    event, and nothing is emitted during a long tool call or a slow model turn
    -- so a clock read from the snapshot visibly freezes for tens of seconds,
    which is exactly when the operator is wondering whether the run has hung.

    Input tokens are the SUM of the plain, cache-creation and cache-read
    fields. Showing `input_tokens` alone would read as ~0 on a real run --
    measured on one sweep: 20 plain against 607,415 cache-read -- which looks
    like a broken counter rather than a working one.

    No dollar figure: cost arrives only in the CLI's final event, and a run
    spans models that price differently, so anything live would be an estimate
    from a price table this repo would then have to keep current.
    """
    if not snapshot:
        base = "Running analysis..."
        if markup:
            base = f"[bold green]{base}[/bold green]"
        return base if elapsed is None else f"{base} · {fmt_elapsed_clock(elapsed)}"

    raw_stage = snapshot.get("stage") or "analysis"
    title = _STAGE_TITLES.get(raw_stage, str(raw_stage))
    if elapsed is None:
        elapsed = snapshot.get("elapsed", 0) or 0

    # A deterministic track (image/text) has no model and therefore no tokens.
    # Falling through would print `0 in / 0 out`, which reads as a broken
    # counter rather than as "this channel does not have that number" -- the
    # same failure this function's docstring describes for `input_tokens`.
    if snapshot.get("kind") == "track":
        state = str(snapshot.get("state") or "running")
        if markup:
            from rich.markup import escape
            title, state = (f"[bold green]{escape(title)}[/bold green]",
                            f"[bold cyan]{escape(state)}[/bold cyan]")
        return f"{title} : {state} · {fmt_elapsed_clock(elapsed)}"

    tool = live_tool_label(snapshot.get("current_tool"))
    if raw_stage == "extracting" and not snapshot.get("current_tool"):
        tool = "docling"

    inp = (int(snapshot.get("input_tokens", 0) or 0)
           + int(snapshot.get("cache_creation_input_tokens", 0) or 0)
           + int(snapshot.get("cache_read_input_tokens", 0) or 0))
    out = int(snapshot.get("output_tokens", 0) or 0)

    if markup:
        from rich.markup import escape
        title_s = f"[bold green]{escape(title)}[/bold green]"
        tool_s = f"[bold cyan]{escape(tool)}[/bold cyan]"
        paper_s = f"[bold]{escape(paper)}[/bold]  " if paper else ""
    else:
        title_s = title
        tool_s = tool
        paper_s = f"{paper}  " if paper else ""

    # A backend that streams no per-turn usage (codex: the figures arrive
    # only in the final turn.completed) stamps `live_tokens: False`, and the
    # segment is dropped rather than printed as a permanent `0 in / 0 out`
    # -- the same argument as the `kind: "track"` branch above. An absent
    # key keeps the segment: claude and grok stream real counters.
    if snapshot.get("live_tokens") is False:
        return f"{paper_s}{title_s} : {tool_s} · {fmt_elapsed_clock(elapsed)}"

    return (
        f"{paper_s}{title_s} : {tool_s} · "
        f"{fmt_tokens(inp)} in / {fmt_tokens(out)} out · "
        f"{fmt_elapsed_clock(elapsed)}"
    )


class LiveBatchStatus:
    """One status line per in-flight slot, redrawn on a timer.

    TTY: Rich Live on stderr so the current tool, tokens and elapsed sit still
    at the bottom while completion lines print above. Not a TTY: a plain line
    every 15 s -- a redirected log must not fill with carriage returns.

    Two callers, two shapes. `batch.py` keys slots by PAPER and wants the
    key printed and the block gone at the end. `metascience analyze` keys them
    by STAGE (tool agent / science agent / the tracks), where the key is
    already the line's own title -- printing it would read
    `tool_agent  tool agent : ...` -- and where the final states are worth
    keeping on screen. Hence `show_key` and `transient`; both default to the
    batch behaviour, so that caller is untouched.
    """

    def __init__(self, *, live: bool | None = None, periodic_log: bool = True,
                 transient: bool = True, show_key: bool = True):
        if live is None:
            live = bool(getattr(sys.stderr, "isatty", lambda: False)())
        self.live = bool(live)
        self.periodic_log = bool(periodic_log) and not self.live
        self.transient = bool(transient)
        self.show_key = bool(show_key)
        self.slots: dict[str, dict] = {}
        self._live = None

    def start(self) -> None:
        if not self.live:
            return
        from rich.console import Console
        from rich.live import Live

        self._live = Live(
            _BatchView(self),
            console=Console(stderr=True),
            refresh_per_second=4,
            transient=self.transient,
        )
        self._live.start()

    def stop(self) -> None:
        live = self._live
        self._live = None
        if live is not None:
            live.stop()

    def begin(self, paper: str) -> None:
        self.slots[paper] = {"snapshot": None, "t0": time.monotonic()}

    def update(self, key: str, snapshot: dict) -> None:
        slot = self.slots.get(key)
        if slot is None:
            self.begin(key)
            slot = self.slots[key]
        if snapshot.get("done"):
            # Merged, not replaced: a bare `{stage, done}` marker from an LLM
            # stage must not wipe the token counters it last reported, and a
            # track's terminal `state` must survive.
            snapshot = {**(slot.get("snapshot") or {}), **snapshot}
            if self._owns(key, snapshot):
                # STOP THE CLOCK. Slots are kept on screen after they finish
                # (the analyze view is not transient), and a finished stage
                # whose elapsed keeps climbing reads as one that is still
                # working -- which is the whole thing this display exists to
                # tell you.
                slot["t_end"] = time.monotonic()
        elif "t_end" in slot:
            # Work again after a terminal marker: restart the clock rather
            # than leave a live line showing a stopped one.
            slot.pop("t_end", None)
        slot["snapshot"] = snapshot
        if not self.periodic_log:
            return
        # Throttled PER SLOT. One shared window let a single slot's line
        # through every 15 s, so concurrent slots starved each other.
        now = time.monotonic()
        if now - slot.get("last_log", float("-inf")) < 15.0:
            return
        slot["last_log"] = now
        print(render_stage_line(
            snapshot, elapsed=self._elapsed(slot, now),
            paper=key if self.show_key else None, markup=False,
        ), flush=True)

    @staticmethod
    def _owns(key: str, snapshot: dict) -> bool:
        """Is this `done` marker the END of what this line is measuring?

        Only when the line IS that stage. The two callers key their slots
        differently: `metascience analyze` keys by STAGE, so a stage's done
        marker retires its own line; `batch.py` keys by PAPER, and every
        stage of that paper reports into the one line. Stopping a paper's
        clock on a stage-scoped marker is what froze the batch display at
        `0:00` -- the image track refuses in well under a second on a paper
        with no figures, and its done marker then stopped a clock that had
        two live analysts still to run behind it.
        """
        stage = snapshot.get("stage")
        return stage is None or str(stage) == key

    @staticmethod
    def _elapsed(slot: dict, now: float) -> float:
        return (slot.get("t_end") or now) - slot["t0"]

    def end(self, paper: str) -> None:
        self.slots.pop(paper, None)

    def renderable(self):
        from rich.console import Group
        from rich.text import Text

        now = time.monotonic()
        rows = []
        for paper, slot in self.slots.items():
            line = render_stage_line(
                slot.get("snapshot"),
                elapsed=self._elapsed(slot, now),
                paper=paper if self.show_key else None,
                markup=True,
            )
            rows.append(Text.from_markup(line))
        if not rows:
            return Text("waiting for workers...")
        return Group(*rows)

    def __enter__(self) -> "LiveBatchStatus":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()


class _BatchView:
    """Rich re-calls `__rich__` every frame, which is what makes elapsed tick
    during a silent tool call -- a frozen Text would not."""

    def __init__(self, monitor: LiveBatchStatus):
        self.monitor = monitor

    def __rich__(self):
        return self.monitor.renderable()


# Canonical row order inside one paper's block, so a stage does not jump rows
# depending on which one happened to report first.
_STAGE_ORDER = ("extracting", "tool_agent", "science_agent", "image_track",
                "text_track", "adjudicator")

# Grid column titles. The status line's "scientific proofreading agent" is 29
# characters, and at 110 columns it pushed the clock off the right edge.
_GRID_STAGE_TITLES = {**_STAGE_TITLES, "science_agent": "proofreading"}

_STATUS_STYLE = {
    "ok": ("ok", "green"),
    "partial": ("partial", "yellow"),
    "fail": ("FAILED", "bold red"),
    None: ("finishing", "dim"),
}


class BatchGrid(LiveBatchStatus):
    """The `metascience batch` view: a grid with one row per STAGE of every
    paper in flight, under a header that counts the whole corpus.

    The one-line-per-paper view it replaced folded every stage of a paper into
    one line, so with the two analysts and the tracks running concurrently the
    line showed whichever stage reported last and flickered between them --
    the same defect `test_the_two_parallel_analysts_get_a_line_each` fixed for
    `metascience analyze`. Here each stage keeps its own row, tool, tokens and
    clock, and a stage's `done` stops only its own clock.

    Not a TTY: one plain line per (paper, stage) at most every `LOG_EVERY`
    seconds, plus a line when a stage finishes. The throttle is per row, not
    global: a global 15 s window let ONE paper's line through per window, so a
    ten-worker log showed each paper about every two and a half minutes and a
    quiet paper possibly never.
    """

    LOG_EVERY = 15.0
    RECENT = 6

    def __init__(self, *, total: int = 0, live: bool | None = None,
                 periodic_log: bool = True, recent: int | None = None):
        super().__init__(live=live, periodic_log=periodic_log,
                         transient=True, show_key=True)
        self.total = int(total)
        self.started = 0
        self.t_batch = time.monotonic()
        self.counts = {"ok": 0, "partial": 0, "fail": 0, "skip": 0}
        self.finished: list[dict] = []          # newest last
        self.recent = self.RECENT if recent is None else int(recent)

    # -- state -------------------------------------------------------------
    def begin(self, paper: str) -> None:
        self.started += 1
        self.slots[paper] = {"t0": time.monotonic(), "stages": {}}

    def update(self, key: str, snapshot: dict) -> None:
        slot = self.slots.get(key)
        if slot is None:
            self.begin(key)
            slot = self.slots[key]
        stage = str(snapshot.get("stage") or "analysis")
        now = time.monotonic()
        row = slot["stages"].get(stage)
        if row is None:
            row = slot["stages"][stage] = {"snapshot": {}, "t0": now}
        if snapshot.get("done"):
            # Merged, as in LiveBatchStatus: a bare `{stage, done}` marker
            # must not wipe the counters the stage last reported.
            snapshot = {**row["snapshot"], **snapshot}
            row.setdefault("t_end", now)
        else:
            row.pop("t_end", None)
            row.pop("logged_done", None)
        row["snapshot"] = snapshot
        if self.periodic_log:
            self._log(key, row, now)

    def end(self, paper: str) -> None:
        slot = self.slots.pop(paper, None)
        if slot is None:
            return
        self.finished.append({"paper": paper, "status": None,
                              "elapsed": time.monotonic() - slot["t0"]})
        del self.finished[:-max(self.recent, 1) * 4]

    def record(self, paper: str, status: str) -> None:
        """The paper's final status (`ok|partial|fail|skip`), once known.

        A skipped paper never began, so it is counted and gets no row.
        """
        if status in self.counts:
            self.counts[status] += 1
        for item in reversed(self.finished):
            if item["paper"] == paper and item["status"] is None:
                item["status"] = status
                break

    # -- plain-log path ----------------------------------------------------
    def _log(self, paper: str, row: dict, now: float) -> None:
        done = "t_end" in row
        if done:
            if row.get("logged_done"):
                return
            row["logged_done"] = True
        elif now - row.get("last_log", float("-inf")) < self.LOG_EVERY:
            return
        row["last_log"] = now
        line = render_stage_line(row["snapshot"],
                                 elapsed=self._elapsed(row, now),
                                 paper=paper, markup=False)
        print(line + (" · done" if done else ""), flush=True)

    # -- grid path -----------------------------------------------------------
    @staticmethod
    def _stage_key(item):
        stage = item[0]
        return (_STAGE_ORDER.index(stage) if stage in _STAGE_ORDER
                else len(_STAGE_ORDER))

    def _header(self, now: float):
        from rich.text import Text

        c = self.counts
        done = sum(c.values())
        running = len(self.slots)
        queued = max(self.total - done - running, 0)
        head = Text()
        head.append(f"{fmt_elapsed_clock(now - self.t_batch)}  ")
        head.append(f"{done}/{self.total} done", style="bold")
        head.append(f" · {running} running · {queued} queued · ")
        head.append(f"{c['ok']} ok", style="green")
        head.append(" · ")
        head.append(f"{c['partial']} partial", style="yellow")
        head.append(" · ")
        head.append(f"{c['fail']} failed",
                    style="bold red" if c["fail"] else None)
        head.append(f" · {c['skip']} skipped")
        return head

    def _stage_cells(self, stage: str, row: dict, now: float):
        from rich.text import Text

        snap = row["snapshot"] or {}
        done = "t_end" in row
        title = _GRID_STAGE_TITLES.get(stage, stage)
        no_tokens = Text("—", style="dim")
        if snap.get("kind") == "track":
            activity = Text(str(snap.get("state") or "running"),
                            style="dim" if done else "cyan",
                            no_wrap=True, overflow="ellipsis")
            tin = tout = no_tokens
        else:
            if done:
                activity = Text("done", style="green")
            elif stage == "extracting" and not snap.get("current_tool"):
                activity = Text("docling", style="cyan")
            else:
                activity = Text(live_tool_label(snap.get("current_tool")),
                                style="bold cyan", no_wrap=True,
                                overflow="ellipsis")
            if snap.get("live_tokens") is False:
                tin = tout = no_tokens
            else:
                inp = (int(snap.get("input_tokens", 0) or 0)
                       + int(snap.get("cache_creation_input_tokens", 0) or 0)
                       + int(snap.get("cache_read_input_tokens", 0) or 0))
                tin = Text(fmt_tokens(inp))
                tout = Text(fmt_tokens(int(snap.get("output_tokens", 0) or 0)))
        return (Text(title, style="dim" if done else "green"), activity,
                tin, tout,
                Text(fmt_elapsed_clock(self._elapsed(row, now)),
                     style="dim" if done else None))

    def renderable(self):
        from rich import box
        from rich.console import Group
        from rich.table import Table
        from rich.text import Text

        now = time.monotonic()
        recent = self.finished[-self.recent:] if self.recent > 0 else []
        if not self.slots and not recent:
            return Group(self._header(now), Text("waiting for workers..."))

        table = Table(box=box.SIMPLE_HEAD, expand=False, pad_edge=False)
        # Paper and Activity absorb a narrow terminal (ellipsis); the stage
        # and the numbers keep their width, since a clipped clock is the one
        # thing that makes a live run look hung.
        table.add_column("Paper", overflow="ellipsis",
                         max_width=40, ratio=3)
        table.add_column("Stage", no_wrap=True, min_width=12)
        table.add_column("Activity", overflow="ellipsis",
                         max_width=28, ratio=2)
        table.add_column("In", justify="right", no_wrap=True, min_width=6)
        table.add_column("Out", justify="right", no_wrap=True, min_width=6)
        table.add_column("Time", justify="right", no_wrap=True, min_width=7)

        first_block = True
        for paper, slot in self.slots.items():
            if not first_block:
                table.add_section()
            first_block = False
            name = Text(paper, style="bold", no_wrap=True,
                        overflow="ellipsis")
            stages = sorted(slot["stages"].items(), key=self._stage_key)
            if not stages:
                table.add_row(name, Text("starting", style="dim"), "", "", "",
                              Text(fmt_elapsed_clock(now - slot["t0"])))
                continue
            for i, (stage, row) in enumerate(stages):
                table.add_row(name if i == 0 else "",
                              *self._stage_cells(stage, row, now))

        if recent:
            if not first_block:
                table.add_section()
            for item in reversed(recent):
                label, style = _STATUS_STYLE.get(item["status"],
                                                 (str(item["status"]), "dim"))
                table.add_row(Text(item["paper"], style="dim", no_wrap=True,
                                   overflow="ellipsis"),
                              Text(label, style=style), "", "", "",
                              Text(fmt_elapsed_clock(item["elapsed"]),
                                   style="dim"))
        return Group(self._header(now), table)


# ---------------------------------------------------------------------------
# `metascience batch -v` with several workers: every paper's streamed model
# text goes to the one stdout, interleaved and unattributable. Each paper runs
# in its own asyncio task, so a ContextVar set inside that task names the
# paper for everything it prints, however deep in the stack the print is.
# ---------------------------------------------------------------------------

CURRENT_PAPER: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "metascience_current_paper", default=None)


class PaperPrefixedStream:
    """A stdout wrapper that prefixes each line with `[<paper>] `.

    Lines are buffered PER PAPER until their newline, so a paper that prints
    a partial line and then yields cannot have another paper's text spliced
    into the middle of it. Writes made outside any paper's context (the
    batch's own header and summary, executor threads that did not copy the
    context) pass through unchanged.
    """

    def __init__(self, stream):
        self._stream = stream
        self._pending: dict[str, str] = {}

    def write(self, s: str) -> int:
        key = CURRENT_PAPER.get()
        if not key:
            return self._stream.write(s)
        buf = self._pending.pop(key, "") + s
        *lines, rest = buf.split("\n")
        if rest:
            self._pending[key] = rest
        if lines:
            self._stream.write("".join(f"[{key}] {ln}\n" for ln in lines))
        return len(s)

    def flush_paper(self, key: str) -> None:
        """Emit a paper's unterminated last line, e.g. when it finishes."""
        rest = self._pending.pop(key, "")
        if rest:
            self._stream.write(f"[{key}] {rest}\n")

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, name: str):
        return getattr(self._stream, name)


class prefix_stdout_by_paper:
    """Context manager: install `PaperPrefixedStream` on `sys.stdout` while
    `enabled`, and restore (and drain) it on exit."""

    def __init__(self, enabled: bool = True):
        self.enabled = bool(enabled)
        self.stream: PaperPrefixedStream | None = None
        self._saved = None

    def __enter__(self) -> "prefix_stdout_by_paper":
        if self.enabled:
            self._saved = sys.stdout
            self.stream = PaperPrefixedStream(sys.stdout)
            sys.stdout = self.stream
        return self

    def __exit__(self, *exc: Any) -> None:
        if self.stream is not None:
            for key in list(self.stream._pending):
                self.stream.flush_paper(key)
            sys.stdout = self._saved
            self.stream = None
