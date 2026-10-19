"""Shared implementation extracted for independent image analysis."""
from typing import Callable

import asyncio


import json


import os
import sys


import re


import tempfile
import time


from .llm_backend import (
    BackendUnavailable,
    fatal_backend_reason as _fatal_backend_reason,
    MCPUnavailable,
    as_invocation,
    build_invocation,
    make_stream_normalizer,
    mcp_discovery_error,
    mcp_discovery_from_init,
    resolve_backend,
)


class _ImagePreflight:
    """Default stage preflight: the image package's own capability check.

    The toolkit's statistical stages always pass `preflight=` (the statistical
    gate); only image screening relies on this default, so it resolves through
    the plugin door and fails closed when the image package is absent."""

    @staticmethod
    def assert_ready(backend=None):
        from .image_plugin import load
        return load("preflight").assert_ready(backend)


_preflight_module = _ImagePreflight


from . import usage_guard as _usage_guard_module


def _build_env() -> dict[str, str]:
    """Env for the subprocess; strip CLAUDECODE so a parent Claude Code session doesn't bleed in."""
    from .history_runtime import env as history_env
    return {**{k: v for k, v in os.environ.items() if k != "CLAUDECODE"}, **history_env()}


class StageError(RuntimeError):
    """A claude CLI stage failed outright (nonzero exit and no usable output)."""


def _safe_on_progress(on_progress, snapshot: dict) -> None:
    """A broken status line must not cost a paid stage or skip extraction."""
    if on_progress is None:
        return
    try:
        on_progress(snapshot)
    except Exception:  # noqa: BLE001 -- a broken display must not cost a run
        pass


def _kill_subprocess_group(proc) -> None:
    """SIGKILL the process group, falling back to the one pid.

    Grok (and Claude) spawn an MCP server as a child. Killing only the CLI
    leaves that grandchild holding stdout, so `proc.wait()` blocks for the
    grandchild's lifetime -- the forensic-track client already measured this.
    `start_new_session=True` on the Popen is what makes the group ours.
    A fake/test proc with no pid still gets `.kill()`.
    """
    import signal
    pid = getattr(proc, "pid", None)
    if pid:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        proc.kill()
    except (ProcessLookupError, AttributeError):
        pass


#: How often the stage reader looks for new stdout in the child's output file.
#: Only the status line and the stall clock wait on it; nothing is lost by
#: polling, because a file keeps everything the child wrote.
STDOUT_POLL_SECONDS = 0.1


class _FileLineReader:
    """`readline()` over a regular file another process is appending to.

    WHY THE CHILD'S STDOUT IS A FILE AND NOT A PIPE. `claude -p` (2.1.301)
    DROPS whatever it has not yet written when it exits while its stdout pipe
    is full, and still exits 0. MEASURED 2026-10-18: a reader that slept 75 s
    received exactly 65,242 bytes (the pipe's capacity), the last line cut
    mid-JSON, and no `result` event, from a CLI that had exited rc=0 at
    t+15 s. In the v1.83.0 sonnet batch (20 stages sharing one event loop)
    7 of 57 stages lost their stream's tail this way; 10.1007--s40200-021-
    00832-0's tools agent lost its last 100 s, including the accepted
    StructuredOutput call that the CLI's own session log records. A pipe is
    drained only when the event loop gets to this coroutine; a write to a
    regular file completes in the child no matter what the parent is doing.

    End of stream is the child's exit (`exited` done) followed by a read that
    returns nothing -- not an EOF on a descriptor that a grandchild may hold.
    """

    def __init__(self, fh, exited: "asyncio.Future", poll: float = STDOUT_POLL_SECONDS):
        self._fh = fh
        self._exited = exited
        self._poll = poll
        self._buf = bytearray()
        self._eof = False

    async def readline(self) -> bytes:
        while True:
            i = self._buf.find(b"\n")
            if i >= 0:
                line = bytes(self._buf[:i + 1])
                del self._buf[:i + 1]
                return line
            if self._eof:
                # An unterminated last line is returned as it is: the caller
                # counts it as unparsed, which is the evidence of a cut stream.
                line, self._buf = bytes(self._buf), bytearray()
                return line
            # Exit is observed BEFORE the read: the child's writes all happen
            # before its exit, so a read made after seeing the exit sees every
            # byte. Checking after an empty read would race a final write.
            exited = self._exited.done()
            chunk = self._fh.read(1 << 20)
            if chunk:
                self._buf += chunk
                continue
            if exited:
                self._eof = True
                continue
            await asyncio.wait({self._exited}, timeout=self._poll)


def _open_stdout_file():
    """(write handle for the child, read handle for us, path).

    Two handles, two file descriptions: the child's writes must not move our
    read offset. The path is removed when the stage ends."""
    import tempfile
    fd, path = tempfile.mkstemp(prefix="metascience-stage-", suffix=".jsonl")
    os.close(fd)
    try:
        writer = open(path, "wb")
        reader = open(path, "rb")
    except BaseException:
        _close_stdout_file(None, None, path)
        raise
    return writer, reader, path


def _close_stdout_file(writer, reader, path) -> None:
    for fh in (writer, reader):
        try:
            if fh is not None:
                fh.close()
        except OSError:
            pass
    try:
        os.unlink(path)
    except OSError:
        pass


#: How long a forensic-track child gets between SIGTERM and SIGKILL. The image
#: child uses it to seal its own run as failed; 0 restores the old SIGKILL.
TRACK_TERMINATE_GRACE_DEFAULT = 10.0
#: The image child's packaging watchdog (`packaging_timeout`): snapshotting the
#: previous answer, rendering, archiving and publishing. Separate from the
#: detection deadline, which no longer pays for any of it.
IMAGE_PACKAGING_TIMEOUT_DEFAULT = 1800.0


def _signal_group(proc, sig) -> bool:
    """Signal the child's whole process group; False when nothing is left.

    The group id IS the child's pid (`start_new_session=True`), so this still
    reaches worker processes after the child itself has exited and been
    reaped -- `os.getpgid(pid)` cannot, which is how pool workers outlived a
    killed paper.
    """
    pid = getattr(proc, "pid", None)
    if not pid:
        return False
    try:
        os.killpg(pid, sig)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


async def _terminate_subprocess_group(proc, kill, grace_s: float) -> None:
    """SIGTERM the group, wait up to `grace_s` for the child, then SIGKILL.

    The grace is what lets the image child seal its own run and keep its
    failure record. Whatever remains of the group after the grace is killed
    unconditionally -- a child that exited may have left workers behind.
    """
    import signal
    if grace_s > 0 and getattr(proc, "returncode", None) is None \
            and _signal_group(proc, signal.SIGTERM):
        try:
            await asyncio.wait_for(proc.wait(), timeout=grace_s)
        except (asyncio.TimeoutError, TimeoutError):
            pass
    if getattr(proc, "returncode", None) is None:
        kill(proc)
    _signal_group(proc, signal.SIGKILL)


def _group_gone(proc) -> bool:
    return not _signal_group(proc, 0)


def _read_phase(path) -> str | None:
    try:
        return json.loads(path.read_text()).get("phase")
    except (OSError, ValueError, AttributeError):
        return None


def _live_tool_name(block: dict) -> str:
    """Short name for the live status line from one `tool_use` block.

    After `normalize_event`, a Grok forensic call is already rewritten to
    `mcp__forensic_metascience__grim_check`. Before that rewrite (or for a
    still-wrapped `use_tool`), lift the inner `tool_name`. The status line
    must never show the MCP prefix -- that is plumbing, not what the
    operator is watching for.
    """
    name = str(block.get("name") or "")
    if name == "use_tool":
        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
        raw = inp.get("tool_name") or name
        name = str(raw)
    if "__" in name:
        return name.rpartition("__")[2] or name
    return name


def _stall_seconds() -> float:
    """How long a stage may emit NOTHING before it is treated as dead.

    Separate from the duration timeout on purpose -- see `_watch_for_stall`.
    0 or a bad value disables it, so an operator debugging a slow backend can
    turn it off without also removing the duration cap.
    """
    raw = os.environ.get("METASCIENCE_STAGE_STALL_SECONDS", "")
    try:
        return float(raw) if raw.strip() else STAGE_STALL_SECONDS_DEFAULT
    except ValueError:
        return STAGE_STALL_SECONDS_DEFAULT


STAGE_STALL_SECONDS_DEFAULT = 600.0


async def _run_stage(
    cmd,
    prompt: str,
    verbose: bool = False,
    timeout: int | None = None,
    on_progress: "Callable[[dict], None] | None" = None,
    stage_label: str = "",
    *, preflight=None, check_mcp=False, build_env=None, guard=None, kill=None, stall=None,
) -> dict:
    """Run one LLM-CLI invocation and collect its stream-json events.

    `cmd` is an ``Invocation`` (from `_build_claude_cmd`) or a bare argv
    list (existing tests). THE PROMPT GOES DOWN STDIN FOR CLAUDE, NEVER ON
    ARGV; Grok gets it via `--prompt-file` which we write here. Linux caps a
    SINGLE argument at MAX_ARG_STRLEN -- 32 pages, 128 KB -- independently of
    the 2 MB ARG_MAX for the whole vector, so a large prompt fails with
    `OSError: [Errno 7] Argument list too long` at Popen. Measured: a paper
    carrying a 2.1 MB .docx supplement crashed there AFTER a 22-minute
    stage-1 sweep, so the run was paid for and produced nothing.

    Returns a dict with: result (final result string or None), text (joined
    assistant text), messages (all events), cost_usd, input_tokens,
    output_tokens, return_code, is_error, wall_seconds.

    `on_progress`, if given, is called with a snapshot dict as the counters
    change. Cost is deliberately absent from the snapshot: `total_cost_usd`
    arrives only in the final `result` event.
    """
    inv = as_invocation(cmd)
    _assert_ready = preflight or _preflight_module.assert_ready
    _build_env = build_env or globals()["_build_env"]
    usage_guard = guard or _usage_guard_module.guard
    _kill_subprocess_group = kill or globals()["_kill_subprocess_group"]
    _stall_seconds = stall or globals()["_stall_seconds"]
    prompt_stdin = None

    # EVERY EXIT BEFORE THE SPAWN RELEASES THE INVOCATION. A refused
    # preflight, an unreachable MCP server, a weekly-limit stop or a cancel
    # used to leave the invocation behind -- on Grok a sandbox directory
    # per stage (2026-10-18: one per MCPUnavailable paper, prompt.txt
    # still empty). The spawn below cleans up on its own failure, and the
    # stage's `finally` after it.
    try:
        # Refuse to start if a dependency whose absence makes the OUTPUT WRONG is
        # missing. Placed here rather than in the CLI because batch.py
        # calls analyze_paper() directly and would bypass a CLI-level check; this
        # is the one chokepoint every sweep, editorial and repair call passes
        # through. Cached, so the 2-3 calls per paper cost one check.
        #
        # Note this fails CLOSED while the usage guard below fails OPEN, and the
        # asymmetry is the point: a broken /usage probe should never stop a batch
        # (worst case: wasted spend), but a missing statcheck means the run reads a
        # corpus as having no NHST statistics (worst case: confidently wrong output
        # that still looks complete). Override with METASCIENCE_SKIP_PREFLIGHT=1.
        _assert_ready(inv.backend)

        # Free local MCP liveness before the network usage probe -- same ordering
        # argument as preflight-before-usage. Claude: no-op. Grok: doctor. In a
        # worker thread: the probe is a blocking subprocess (up to 90 s, retried
        # with pauses on failure), and run on the loop it would stall every other
        # paper's in-flight stage of a batch for that long.
        if check_mcp:
            await asyncio.to_thread(inv.backend.assert_mcp_live, inv.workdir)

        # Pause the run if the 5-hour session window is nearly spent, BEFORE
        # launching the call. Hitting the limit mid-stage does not stall — it
        # returns an error result, so the paper is charged for a sweep that
        # produced no findings. Interval-gated, fails open, disabled with
        # METASCIENCE_USAGE_GUARD=0, and the weekly STOP is skippable with
        # METASCIENCE_USAGE_IGNORE_WEEKLY=1 (extra usage credits are not in
        # the /usage weekly %). Awaited outside the `started` clock and
        # outside the stage timeout so a pause is not billed to either.
        # The model rides along only when the invocation names one
        # (Antigravity, whose quota buckets are per model family); every
        # other call keeps the one-argument form its test stand-ins accept.
        _model = getattr(inv, "model", None)
        await usage_guard(backend=inv.backend,
                          **({"model": _model} if _model else {}))

        started = time.monotonic()
        env = _build_env()
        env.update(inv.env_overlay)

        if inv.prompt_delivery == "prompt_file":
            if inv.prompt_path is None:
                raise StageError("Grok invocation has prompt_delivery=prompt_file but no prompt_path")
            inv.prompt_path.write_text(prompt, encoding="utf-8")

        # "stdin" delivery (Claude, Codex, OpenRouter): the child's stdin is a
        # FILE that already holds the whole prompt when the child is exec'd, never
        # a pipe we fill afterwards. A pipe is written only once the event loop
        # comes back to this coroutine, and `claude -p` waits 3 s for the first
        # byte and then exits 1 with "Input must be provided either through stdin
        # or as a prompt argument". MEASURED 2026-10-18: with 20 workers on one
        # loop, both stages of 10.3389--fpsyg.2011.00199 died that way at 0
        # tokens; the same failure reproduces with the real CLI by blocking the
        # loop 5 s between spawn and write, and a pre-filled file passes it. An
        # anonymous TemporaryFile also ends at EOF, so no close is needed and
        # nothing is left on disk. Grok: the prompt is already in `--prompt-file`;
        # stdin is a pipe closed at once so a build that ever waited on it cannot
        # hang.
        if inv.prompt_delivery in ("stdin", "stdin_stream_json"):
            prompt_stdin = tempfile.TemporaryFile()
            if inv.prompt_delivery == "stdin_stream_json":
                # Antigravity: `-p` takes its prompt on argv, so the turn goes
                # down stdin as ONE stream-json `user` line (the 128 KB argv
                # limit); EOF after it ends the session once the turn is done.
                prompt_stdin.write((json.dumps(
                    {"event": "user", "message": {"content": prompt}})
                    + "\n").encode())
            else:
                prompt_stdin.write(prompt.encode())
            prompt_stdin.flush()
            prompt_stdin.seek(0)
    except BaseException:
        if prompt_stdin is not None:
            prompt_stdin.close()
        inv.cleanup()
        raise

    # The child's stdout is a regular FILE we tail, never a pipe: a CLI that
    # exits while its pipe is full drops the rest of its stream, `result`
    # event included, and still exits 0 (see `_FileLineReader`).
    stdout_w, stdout_r, stdout_path = _open_stdout_file()
    # Tool-result JSON events can exceed the default 64KB asyncio buffer
    # (stderr is still a pipe, and a test double may hand back a stdout pipe).
    try:
        proc = await asyncio.create_subprocess_exec(
            *inv.argv,
            stdin=prompt_stdin if prompt_stdin is not None else asyncio.subprocess.PIPE,
            stdout=stdout_w,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(inv.workdir) if inv.workdir is not None else None,
            limit=64 * 1024 * 1024,  # 64 MB per line
            start_new_session=True,
        )
    except BaseException:
        _close_stdout_file(stdout_w, stdout_r, stdout_path)
        inv.cleanup()
        raise
    finally:
        # The child holds its own descriptors; ours would only keep the stdout
        # file open for writing after the child is gone, and the prompt file
        # alive for nothing.
        try:
            stdout_w.close()
        except OSError:
            pass
        if prompt_stdin is not None:
            prompt_stdin.close()

    try:
        if proc.stdin is not None:
            proc.stdin.close()
    except Exception:  # noqa: BLE001 -- closing a dead pipe is not a failure
        pass

    analysis_text: list[str] = []
    messages: list[dict] = []
    #: Last few raw stdout lines, for the error path only (see below).
    raw_tail: list[str] = []
    schema_errors: list[str] = []
    cost_usd = 0.0
    # WHETHER ANY RESULT EVENT CARRIED A COST AT ALL. Codex reports tokens
    # only (see `CodexStreamNormalizer`), so its stages sum to 0.0 -- a number
    # that reads as "free" in run_meta and the workbench when it is unknown.
    cost_reported = False
    in_tokens = 0
    out_tokens = 0
    # Cache tokens are NOT part of `input_tokens` -- the API reports them as
    # separate counters, and everything a prompt-cached run actually reads
    # lands in them. MEASURED on the stage-1 sweep of
    # eval/ground_truth/papers/10.3389--fpsyg.2019.02949: input_tokens 22,
    # cache_creation_input_tokens 171,926, cache_read_input_tokens 1,176,684.
    # Recording only `input_tokens` therefore accounted for 22 of ~1.35M input
    # tokens, which is why the token record could never be reconciled against
    # the $4.30 the stage cost.
    cache_creation_tokens = 0
    cache_read_tokens = 0
    final_result: str | None = None
    structured_output = None
    is_error = False
    error_subtype: str | None = None
    stop_reason: str | None = None
    num_turns: int | None = None
    tool_calls = 0
    mcp_discovery: dict | None = None
    mcp_abort: MCPUnavailable | None = None
    # Live-only mirrors of the token counters (see the note in the assistant
    # branch). Never returned; never merged into the recorded totals.
    live_in = 0
    live_out = 0
    live_cache_creation = 0
    live_cache_read = 0
    current_tool: str | None = None

    def _emit_progress() -> None:
        """Hand the caller a counter snapshot. Never lets the display kill a run.

        The same posture as the annotators below: a paid stage must not be lost
        to a formatting bug in something that only draws a status line.
        `elapsed` is included so a caller that redraws on a timer agrees with
        the `wall_seconds` this function ultimately records -- both come from
        the one `started` clock.
        """
        snapshot = {
            "stage": stage_label,
            "tool_calls": tool_calls,
            "current_tool": current_tool,
            "input_tokens": live_in,
            "output_tokens": live_out,
            "cache_creation_input_tokens": live_cache_creation,
            "cache_read_input_tokens": live_cache_read,
            "elapsed": time.monotonic() - started,
        }
        if inv.backend.name == "codex":
            # Codex reports token usage only in the final turn.completed, so
            # the live counters never move; a permanent `0 in / 0 out` reads
            # as a broken counter, not a working one (render_stage_line's own
            # docstring names this failure). The renderer drops the token
            # segment when this is False. NOT keyed on supports_usage_probe:
            # that is about the /usage quota probe, a different fact.
            snapshot["live_tokens"] = False
        _safe_on_progress(on_progress, snapshot)

    # First snapshot before any event, so the status line is not blank while
    # the CLI starts up (MCP handshake, first model turn).
    _emit_progress()

    # A test double hands back a stdout StreamReader of its own; a real child
    # was given the file, so its `proc.stdout` is None.
    exited_future = None
    if proc.stdout is not None:
        stdout_lines = proc.stdout
    else:
        exited_future = asyncio.ensure_future(proc.wait())
        stdout_lines = _FileLineReader(stdout_r, exited_future)

    last_event_at = time.monotonic()
    _STALL_SECONDS = _stall_seconds()

    async def _read_stdout() -> None:
        nonlocal cost_usd, cost_reported, in_tokens, out_tokens, final_result
        nonlocal is_error, error_subtype
        nonlocal cache_creation_tokens, cache_read_tokens, tool_calls
        nonlocal live_in, live_out, live_cache_creation, live_cache_read
        nonlocal structured_output, mcp_discovery, mcp_abort, current_tool
        nonlocal stop_reason, num_turns, schema_errors
        # Assistant turns are re-emitted once per content block, so the same
        # message id can arrive several times; counting its usage each time
        # would inflate the live totals. The final `result` event carries the
        # authoritative figures and is what the returned dict reports -- these
        # per-turn numbers only drive the status line.
        counted_turns: set[str] = set()
        nonlocal last_event_at
        # Claude/Grok: a stateless pass-through to `normalize_event`. Codex:
        # a stateful adapter, because its events map 1-to-N onto the Claude
        # shapes (a completed mcp_tool_call is call+result; the final
        # `result` event is synthesized from state).
        normalizer = make_stream_normalizer(
            inv.backend, expects_schema=inv.expects_schema,
            restore_schema=getattr(inv, "restore_schema", None),
            config_home=getattr(inv, "config_home", None),
            resume_state=getattr(inv, "resume_state", None))
        while True:
            line = await stdout_lines.readline()
            if not line:
                break
            # THE LIVENESS CLOCK. A stage that is working emits stream events
            # continuously; silence is the signal, and it is a different fact
            # from "this stage is taking a long time". See `_STALL_SECONDS`.
            last_event_at = time.monotonic()
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            # A BOUNDED TAIL OF WHAT THE CHILD ACTUALLY SAID. Codex streams
            # its API errors as `{"type":"error"}` lines on STDOUT and exits
            # 1 with an empty stderr; without this the StageError read
            # "exited with code 1. stderr: " and the 400 explaining it (an
            # invalid schema) had to be reproduced by hand. MEASURED
            # 2026-09-02. Five lines, truncated: a diagnostic, not a log.
            raw_tail.append(text[:800])
            del raw_tail[:-5]
            try:
                raw_event = json.loads(text)
            except json.JSONDecodeError:
                # Counted, not just skipped: an unparseable LAST line is a
                # stream cut mid-write, which is how the CLI's dropped tail
                # showed up (see `_FileLineReader`).
                stream_tail[0] += 1
                stream_tail[1] = True
                if verbose:
                    print(f"[non-JSON line] {text[:200]}")
                continue
            stream_tail[1] = False
            if not isinstance(raw_event, dict):
                continue
            for event in normalizer.feed(raw_event):
                messages.append(event)
                etype = event.get("type")
                if etype == "system" and event.get("subtype") == "init":
                    mcp_discovery = mcp_discovery_from_init(
                        event, inv.backend, inv.forensic_mcp)
                    err = mcp_discovery_error(mcp_discovery)
                    if err:
                        mcp_abort = MCPUnavailable(err)
                        try:
                            proc.kill()
                        except ProcessLookupError:
                            pass
                        break
                if etype == "assistant":
                    message = event.get("message") or {}
                    content = message.get("content") or []
                    for block in content:
                        btype = block.get("type")
                        if btype == "text":
                            text_chunk = block.get("text", "")
                            analysis_text.append(text_chunk)
                            if verbose:
                                print(text_chunk)
                        elif btype == "tool_use":
                            tool_calls += 1
                            current_tool = _live_tool_name(block)
                            if verbose:
                                print(f"\n[Using tool: {block.get('name')}]")
                    # Live token counters, for the status line only. They are kept
                    # SEPARATE from in_tokens/out_tokens/cache_* because the
                    # `result` branch below accumulates into those with `+=`:
                    # summing per-turn usage there too would double-count every
                    # token and write the inflated figure to run_meta.json. The
                    # returned totals must come from the `result` event alone.
                    # An id-less event is counted once rather than dropped -- a
                    # missing id should understate nothing.
                    if on_progress is not None:
                        turn_id = message.get("id")
                        if turn_id is None or turn_id not in counted_turns:
                            if turn_id is not None:
                                counted_turns.add(turn_id)
                            turn_usage = message.get("usage") or {}
                            live_in += int(turn_usage.get("input_tokens", 0) or 0)
                            live_out += int(turn_usage.get("output_tokens", 0) or 0)
                            live_cache_creation += int(
                                turn_usage.get("cache_creation_input_tokens", 0) or 0)
                            live_cache_read += int(
                                turn_usage.get("cache_read_input_tokens", 0) or 0)
                        _emit_progress()
                elif etype == "result":
                    result_events[0] += 1
                    final_result = event.get("result")
                    if event.get("structured_output") is not None:
                        structured_output = event.get("structured_output")
                    if event.get("stop_reason") is not None:
                        stop_reason = event.get("stop_reason")
                    if event.get("num_turns") is not None:
                        try:
                            num_turns = int(event.get("num_turns"))
                        except (TypeError, ValueError):
                            num_turns = event.get("num_turns")
                    cost_usd += float(event.get("total_cost_usd", 0) or 0)
                    if event.get("total_cost_usd") is not None:
                        cost_reported = True
                    usage = event.get("usage") or {}
                    in_tokens += int(usage.get("input_tokens", 0) or 0)
                    out_tokens += int(usage.get("output_tokens", 0) or 0)
                    cache_creation_tokens += int(
                        usage.get("cache_creation_input_tokens", 0) or 0)
                    cache_read_tokens += int(usage.get("cache_read_input_tokens", 0) or 0)
                    if event.get("is_error"):
                        is_error = True
                        error_subtype = _error_subtype(event)
                        # WHAT the gate rejected, not just THAT it did. The
                        # subtype alone ("error_max_structured_output_retries")
                        # names a class; the CLI's own `errors` list names the
                        # offending field and value, which is the only thing a
                        # retry can act on. MEASURED 2026-08-22: two grok
                        # adjudications died on `"...placeholder..." is shorter
                        # than 200 characters`, and that sentence was sitting in
                        # this event, discarded, while the retry re-sent an
                        # identical prompt.
                        ev_errors = event.get("errors")
                        if isinstance(ev_errors, list) and ev_errors:
                            schema_errors = [str(e) for e in ev_errors][:5]
                        if verbose:
                            print(f"[ERROR from CLI] subtype={error_subtype}")
                elif inv.backend.name == "codex" and on_progress is not None:
                    # HEARTBEAT. Codex reasons silently between tool calls --
                    # MEASURED on the 2026-09-01 apple_cider run: a healthy
                    # stage went 6.5 minutes with no mapped event -- and its
                    # reasoning/turn events pass through this loop otherwise
                    # untouched. Claude streams assistant deltas continuously,
                    # so this gap class barely exists there. Without a
                    # snapshot per event, the non-TTY 15s logger prints
                    # NOTHING for the whole stretch and a working run reads
                    # as a hung one. This arm also covers `user` tool_result
                    # events, so the label's transition out of a finished
                    # tool is visible.
                    if (event.get("item") or {}).get("type") == "reasoning":
                        current_tool = None      # renders as "thinking"
                    _emit_progress()
                elif inv.backend.name == "antigravity" and on_progress is not None:
                    # The same heartbeat: agy's ACTIVE text deltas pass through
                    # unmapped until their step is DONE, and a tool result is a
                    # `user` event. A long answer must not read as a hung stage.
                    if event.get("type") == "user":
                        current_tool = None
                    _emit_progress()
            if mcp_abort is not None:
                break

    async def _read_stderr() -> bytes:
        assert proc.stderr is not None
        return await proc.stderr.read()

    async def _run_both() -> bytes:
        _, stderr_b = await asyncio.gather(_read_stdout(), _read_stderr())
        return stderr_b

    def _stage_payload(return_code, *, timed_out: bool = False) -> dict:
        return {
            "result": final_result,
            "structured_output": structured_output,
            "text": "\n".join(analysis_text),
            # The prompt AS SENT, carried out so `write_review_outputs` can persist
            # it. Recorded here rather than reconstructed later, because a prompt
            # rebuilt after the fact is a guess about what ran, not a record of it.
            "prompt": prompt,
            "messages": messages,
            "cost_usd": cost_usd,
            "cost_reported": cost_reported,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "cache_creation_input_tokens": cache_creation_tokens,
            "cache_read_input_tokens": cache_read_tokens,
            "return_code": return_code,
            "is_error": True if timed_out else is_error,
            # `error_stalled` vs `error_timeout` are DIFFERENT FACTS and get
            # different responses: running out of clock is a budget decision
            # (raise it, or accept a partial sweep), while a backend that
            # stopped answering is a fault to be counted and reported. Fusing
            # them under one subtype is what made the 2026-08-22 grok stall
            # look like an ordinary slow paper.
            "error_subtype": (
                ("error_stalled" if nonlocal_stalled[0] else "error_timeout")
                if timed_out else error_subtype),
            "stalled_seconds": (
                round(time.monotonic() - last_event_at, 1)
                if timed_out and nonlocal_stalled[0] else None),
            # [] means the CLI reported no per-error detail; it is not the
            # same fact as the stage not having errored (`is_error` says that).
            "schema_errors": list(schema_errors),
            # WHETHER THE CLI'S FINAL `result` EVENT ARRIVED. It is the only
            # event carrying the cost, the token totals and (Claude) the
            # `structured_output`; a stream without one was cut short, and
            # `cost_usd` 0.0 above is then "unknown", not "free".
            "result_event": result_events[0] > 0,
            "stdout_unparsed_lines": stream_tail[0],
            "stdout_ended_mid_line": stream_tail[1],
            "wall_seconds": time.monotonic() - started,
            "llm_backend": inv.backend.name,
            "mcp_discovery": mcp_discovery,
            "current_tool": current_tool,
            "tool_calls": tool_calls,
            "stop_reason": stop_reason,
            "num_turns": num_turns,
            "usage_guard": (
                "unsupported_for_backend"
                if not inv.backend.supports_usage_probe
                else None
            ),
            # True when a turn cap was requested and this backend cannot
            # enforce one (Codex has no --max-turns): the stage ran with
            # wall-clock and the stall watchdog as its only brakes, and
            # that fact must be readable in the record, not silent.
            "max_turns_unsupported": (
                True if getattr(inv, "max_turns_unsupported", False) else None
            ),
            "allowed_tools": list(inv.allowed_tools),
        }

    async def _watch_for_stall() -> None:
        """Raise `asyncio.TimeoutError` when the stream goes quiet.

        ONE NUMBER CANNOT SERVE BOTH QUESTIONS. `timeout` answers "how long may
        a legitimate stage take" -- 1,000 s on the 2026-08-22 batches, and an
        operator who raises it to be safe raises the deadline for a DEAD stage
        by the same amount. This answers "how long before we call it dead",
        which does not scale with the paper.

        MEASURED 2026-08-22, `10.1016--j.ynstr.2021.100304`: the adjudicator
        completed a batch of tool calls at 17:51:33 and its grok session was
        never written to again. The process stayed alive and silent for ~53
        more minutes until it was killed by hand, because `--timeout 60000`
        (16.6 h) was the only clock. At the default 600 s this fires at
        ~18:01, frees the worker, and -- because it takes the SAME path a
        duration timeout takes -- lands the paper as PARTIAL with both
        analysts' findings intact instead of losing the whole run.
        """
        while True:
            await asyncio.sleep(min(_STALL_SECONDS, 30.0))
            if time.monotonic() - last_event_at >= _STALL_SECONDS:
                raise asyncio.TimeoutError

    async def _run_both_watched() -> bytes:
        if _STALL_SECONDS <= 0:
            return await _run_both()
        watcher = asyncio.ensure_future(_watch_for_stall())
        try:
            work = asyncio.ensure_future(_run_both())
            done, _ = await asyncio.wait(
                {work, watcher}, return_when=asyncio.FIRST_COMPLETED)
            if watcher in done:
                work.cancel()
                nonlocal_stalled[0] = True
                watcher.result()          # re-raises the TimeoutError
            return work.result()
        finally:
            watcher.cancel()

    # A one-slot list because `_stage_payload` is defined above this and reads
    # it; a plain `nonlocal` would need the name bound before either closure.
    nonlocal_stalled = [False]
    # [unparseable stdout lines, was the LAST line one of them].
    stream_tail = [0, False]
    result_events = [0]

    try:
        try:
            if timeout is not None:
                stderr_bytes = await asyncio.wait_for(_run_both_watched(),
                                                      timeout=timeout)
            else:
                stderr_bytes = await _run_both_watched()
        except asyncio.TimeoutError:
            # Do NOT re-raise. Raising discarded the in-memory stream --
            # MEASURED 2026-08-20: `10.1016--j.neulet.2017.04.022` sat in
            # failed.jsonl as "timeout after 1800s" with no forensic_review
            # at all, so we could not see whether grok hung on startup, on
            # an MCP tool, or mid-thought. Return the stage as truncated,
            # like a budget stop, so the caller can persist what ran.
            _kill_subprocess_group(proc)
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except (asyncio.TimeoutError, TimeoutError):
                pass
            return _stage_payload(getattr(proc, "returncode", None),
                                  timed_out=True)

        return_code = await proc.wait()
        if mcp_abort is not None:
            raise mcp_abort
        if return_code != 0 and not analysis_text and final_result is None:
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")[:1000]
            # An ACCOUNT-level refusal is not a property of this paper: every
            # paper in the batch would fail identically and retrying cannot fix
            # any of them. Raised as a distinct type so the batch runner stops
            # once instead of producing one traceback per paper and filling the
            # retry queue with papers that were never analysed.
            reason = _fatal_backend_reason(stderr_text)
            if reason:
                raise BackendUnavailable(
                    f"`{inv.backend.binary}` cannot serve requests "
                    f"({reason}). stderr: {stderr_text.strip()[:400]}")
            # THE REASON IS OFTEN ON STDOUT, NOT STDERR. Codex streams its
            # API errors as `{"type":"error"}` JSON lines and exits 1 with
            # an EMPTY stderr, so this message read "exited with code 1.
            # stderr: " and the 400 that explained it (an invalid schema)
            # had to be reproduced by hand. MEASURED 2026-09-02.
            tail = ""
            if not stderr_text.strip() and raw_tail:
                errs = [ln for ln in raw_tail
                        if '"error"' in ln or '"turn.failed"' in ln]
                tail = errs[-1] if errs else raw_tail[-1]
            raise StageError(
                f"`{inv.backend.binary}` CLI exited with code {return_code}. "
                f"stderr: {stderr_text}"
                + (f" | stdout tail: {tail}" if tail else "")
            )

        return _stage_payload(return_code)
    finally:
        # NEVER RMTREE A SANDBOX WHILE A PROCESS STILL HOLDS IT AS CWD.
        #
        # MEASURED 2026-08-22, `10.1016--j.ynstr.2021.100304` on grok: the
        # batch parent was killed while this stage was mid-flight. This
        # `finally` ran `inv.cleanup()` -- which is `shutil.rmtree(run_dir)`
        # -- and nothing killed the child, so the grok CLI was reparented to
        # init (PPID 1) and kept streaming for another 15 minutes against a
        # `(deleted)` cwd, holding its own MCP grandchild. Cost: a runaway
        # spend with nowhere to write, and BOTH analysts' finished work on
        # that paper lost with no `forensic_review*/`, no `batch_costs.jsonl`
        # row, no `partial.jsonl` row -- no record the paper was attempted.
        #
        # The timeout path at the top of this function already does exactly
        # this (`_kill_subprocess_group`, then a bounded wait); the
        # cancellation and exception paths did not, which is the only reason
        # they differed. `_kill_subprocess_group` is safe on an already-dead
        # process -- it swallows ProcessLookupError -- so this is
        # unconditional rather than guarded on a returncode probe that races.
        try:
            # `getattr` and not `proc.returncode`: an object that cannot say
            # whether it is alive must be treated as alive. An extra SIGKILL
            # on a dead pid is a no-op; a skipped one leaks the process, and
            # leaking the process is the whole defect.
            if getattr(proc, "returncode", None) is None:
                _kill_subprocess_group(proc)
        except Exception:  # noqa: BLE001 -- cleanup must not mask the real error
            pass
        if exited_future is not None and not exited_future.done():
            exited_future.cancel()
        _close_stdout_file(None, stdout_r, stdout_path)
        inv.cleanup()


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


_DOCUMENT_MARKERS = ("schema_version", "paper_id")


from .track_contracts import _salvage_documents as _salvage_documents


from .track_contracts import _extract_json as _extract_json


def _error_subtype(result_event: dict) -> str | None:
    """What actually went wrong, for a `result` event carrying `is_error`.

    The CLI's `subtype` describes the transport, not the outcome: a hard API
    failure arrives as `subtype="success"` alongside `is_error=True`. Recording
    that verbatim labels a stage that did no work "success", which is how a
    failed run gets mistaken for a committable one -- an eval run that died in
    2.34s on `output_config.effort 'max' is not supported` was written to
    run_meta.json as `error_subtype: "success"`, and the scorecard it produced
    looked like a genuine regression rather than a broken invocation.

    `terminal_reason` ("api_error") is the field that says what happened, so
    prefer it whenever `subtype` would otherwise call a failure a success.
    Real subtypes -- `error_max_budget_usd`, `error_timeout` -- are untouched,
    so `_stage_hit_budget` keeps working.
    """
    subtype = result_event.get("subtype")
    if not subtype or subtype == "success":
        return result_event.get("terminal_reason") or subtype
    return subtype


from .track_contracts import _validate_track_output as _validate_track_output


def _line_prefixer(prefix: str):
    """Return a function that puts `prefix` at the start of every forwarded
    line, including progress bars redrawn with a carriage return, across
    chunk boundaries. An empty prefix forwards text unchanged."""
    import re
    at_start = True

    def write(text: str) -> str:
        nonlocal at_start
        if not prefix:
            return text
        out = []
        for piece in re.split(r"([\r\n])", text):
            if piece in ("\r", "\n"):
                out.append(piece)
                at_start = True
            elif piece:
                if at_start:
                    out.append(prefix)
                    at_start = False
                out.append(piece)
        return "".join(out)
    return write


async def _run_forensic_track(cmd: list[str], timeout_s: float, validate,
                              label: str, unexamined: str,
                              verbose: bool = False,
                              on_progress: "Callable[[dict], None] | None" = None,
                              *, build_env=None, kill=None,
                              detection_complete=None, stream_stderr=False,
                              stderr_prefix: str = "") -> dict:
    """Launch one forensic-track child and reduce it to one stage record.

    NEVER raises. The record mirrors `_stage_meta`'s bookkeeping keys
    (cost/tokens/wall_seconds/return_code/is_error/error_subtype) so
    `run_meta["stages"]` and the batch cost rows absorb it unchanged -- but it
    is NEVER folded into the result-level `is_error`: a broken free track
    must not demote a clean, paid text review to partial.

    `error_subtype` is one of: ran_findings / ran_clean (the track executed),
    the child's structured refusal subtypes (facts about the installation,
    the file, or the paper), track_timeout / track_crashed /
    track_output_invalid (the track itself failed; zero findings injected),
    and, for an image child that announces phases (`detection_complete`),
    packaging_timeout / packaging_failed (the work around detection failed;
    `detection_completed` says whether the detector's answer exists, and
    `failure_record` says which run was sealed, by whom, what became of its
    workspace, and the detector's last progress snapshot).

    A child that must be stopped gets SIGTERM, a grace period
    (METASCIENCE_TRACK_TERMINATE_GRACE_SECONDS, default 10) to seal its own
    run, then SIGKILL for whatever is left of its process group.
    """
    _build_env = build_env or globals()["_build_env"]
    _kill_subprocess_group = kill or globals()["_kill_subprocess_group"]
    t0 = time.monotonic()
    record: dict = {
        "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0,
        "ran": False, "is_error": False, "error_subtype": None,
        "return_code": None, "wall_seconds": 0.0,
        "n_findings_injected": 0, "findings_rows": [], "output": None,
        "detail": "",
    }
    proc = None
    communication = None
    # No token stream: communicate() drains the pipes. Image children can
    # additionally announce phases (see `history_runtime.isolated_image_track`).
    # `kind: "track"` tells the display this channel has no token counters.
    stage = label.replace(" ", "_")
    grace = _track_timeout("METASCIENCE_TRACK_TERMINATE_GRACE_SECONDS",
                           TRACK_TERMINATE_GRACE_DEFAULT)
    phases = None
    if detection_complete is not None:
        from pathlib import Path
        base = Path(detection_complete).parent
        phases = {"complete": Path(detection_complete), "phase": base / "phase.json",
                  "reason": base / "terminate_reason"}

    def _emit(state: str, done: bool = False) -> None:
        _safe_on_progress(on_progress, {
            "stage": stage, "kind": "track", "state": state,
            "elapsed": time.monotonic() - t0, "done": done,
        })

    _emit("running")

    async def _reap(p) -> None:
        # Bounded: if something in the group survived SIGKILL (unkillable
        # D-state), abandon rather than hang the pipeline on its corpse.
        try:
            await asyncio.wait_for(p.wait(), timeout=5)
        except (asyncio.TimeoutError, TimeoutError):
            pass

    async def _stop(p, reason: str) -> None:
        if phases is not None:
            try:
                phases["reason"].write_text(reason)
            except OSError:
                pass
        await _terminate_subprocess_group(p, _kill_subprocess_group, grace)
        await _reap(p)

    async def _recover(reason: str, reclaim: bool = True) -> dict | None:
        """Seal what the stopped image child left unsealed (never raises)."""
        if phases is None:
            return None
        # Only image children announce phases; their recovery is the image package's.
        from .image_plugin import load
        recover_stopped_child = load("history_runtime").recover_stopped_child
        # Grandchildren killed with the group are reaped by init a moment
        # later; reclaim only once none is left using the workspace.
        for _ in range(20):
            if _group_gone(proc):
                break
            await asyncio.sleep(0.1)
        try:
            return await asyncio.to_thread(
                recover_stopped_child, phases["phase"], reason,
                detection_completed=phases["complete"].is_file(),
                group_gone=_group_gone(proc), reclaim=reclaim)
        except Exception as exc:  # noqa: BLE001 -- recorded, not raised
            return {"reason": reason, "errors": [f"{type(exc).__name__}: {exc}"]}

    class _PhaseTimeout(Exception):
        def __init__(self, subtype, phase, seconds):
            self.subtype, self.phase, self.seconds = subtype, phase, seconds

    try:
        child_env = _build_env()
        if phases is not None:
            child_env["METASCIENCE_IMAGE_DETECTION_COMPLETE"] = str(phases["complete"])
            child_env["METASCIENCE_IMAGE_PHASE_FILE"] = str(phases["phase"])
            child_env["METASCIENCE_IMAGE_TERMINATE_REASON"] = str(phases["reason"])
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
            env=child_env,
        )
        try:
            if stream_stderr:
                write = _line_prefixer(stderr_prefix)

                async def drain_progress():
                    tail = bytearray()
                    while chunk := await proc.stderr.read(8192):
                        sys.stderr.write(write(chunk.decode("utf-8", errors="replace")))
                        sys.stderr.flush()
                        tail.extend(chunk)
                        if len(tail) > 65536:
                            del tail[:-65536]
                    return bytes(tail)

                async def communicate_progress():
                    result = await asyncio.gather(proc.stdout.read(), drain_progress())
                    await proc.wait()
                    return result

                communication = asyncio.create_task(communicate_progress())
            else:
                communication = asyncio.create_task(proc.communicate())
            if phases is None:
                try:
                    stdout, stderr = await asyncio.wait_for(communication, timeout=timeout_s)
                except (asyncio.TimeoutError, TimeoutError):
                    raise _PhaseTimeout("track_timeout", None, timeout_s)
            else:
                # ONE CLOCK PER PHASE, each restarted when the child announces
                # the next. Detection gets `timeout_s` and nothing else is
                # billed to it: the snapshot of the previous answer used to
                # run inside it (536 of 600 s on one paper). Before the first
                # announcement the detection clock runs from launch, as it
                # always did; preparing and packaging run under their own
                # named watchdog, and packaging is no longer UNBOUNDED -- a
                # hung render or archive used to hang the whole sweep.
                packaging_s = _track_timeout("METASCIENCE_IMAGE_PACKAGING_TIMEOUT",
                                             IMAGE_PACKAGING_TIMEOUT_DEFAULT)
                current = None
                clock = ("track_timeout", time.monotonic() + timeout_s, timeout_s)
                while not communication.done():
                    phase = "packaging" if phases["complete"].is_file() \
                        else _read_phase(phases["phase"])
                    if phase != current and phase in ("preparing", "detecting", "packaging"):
                        current = phase
                        budget = timeout_s if phase == "detecting" else packaging_s
                        clock = ("track_timeout" if phase == "detecting" else "packaging_timeout",
                                 time.monotonic() + budget, budget)
                        if phase == "packaging":
                            _emit("rendering media and archiving")
                    remaining = clock[1] - time.monotonic()
                    if remaining <= 0:
                        raise _PhaseTimeout(clock[0], current, clock[2])
                    await asyncio.wait({communication}, timeout=min(0.1, remaining))
                stdout, stderr = await communication
        except _PhaseTimeout as stop:
            await _stop(proc, stop.subtype)
            recovery = await _recover(stop.subtype)
            completed = bool(phases and phases["complete"].is_file())
            record.update(is_error=True, error_subtype=stop.subtype, phase=stop.phase,
                          detection_completed=completed, failure_record=recovery)
            if stop.subtype == "packaging_timeout":
                what = ("the completed detection's output was RETAINED in its workspace "
                        "and is unpublished"
                        if completed else "detection never started; " + unexamined)
                record["detail"] = (f"{label} packaging exceeded {stop.seconds:.0f}s "
                                    f"({stop.phase or 'unknown phase'}) and was stopped: {what}"
                                    " -- a timeout is a fact about this run, not the paper.")
            else:
                record["detail"] = (f"{label} exceeded {stop.seconds:.0f}s and was "
                                    f"killed. {unexamined} -- a "
                                    "timeout is a fact about this run, not the paper.")
            if recovery and recovery.get("workspace_action"):
                record["detail"] += f" Run {recovery.get('run_id')}: sealed by " \
                    f"{recovery.get('sealed_by')}; workspace {recovery['workspace_action']}."
            return record
        record["return_code"] = proc.returncode
        if proc.returncode != 0:
            # A crash AFTER the detection checkpoint is a packaging failure:
            # the detector's answer exists (retained in its workspace), so it
            # must not be filed as a detector crash.
            completed = bool(phases and phases["complete"].is_file())
            record.update(
                is_error=True,
                error_subtype="packaging_failed" if completed else "track_crashed",
                detection_completed=completed,
                detail=(f"{label} child exited "
                        f"{proc.returncode}"
                        + (" after detection completed (output retained, unpublished)"
                           if completed else "") + ": "
                        + (stderr or b"").decode(errors="replace")[-2000:]))
            if phases is not None:
                # A crash keeps its workspace for diagnosis (sealed, so
                # `workspace-reclaim` takes it later); only stops reclaim now.
                record["failure_record"] = await _recover(record["error_subtype"],
                                                          reclaim=False)
            return record
        try:
            obj = json.loads((stdout or b"").decode(errors="replace"))
            status, rows = validate(obj)
        except Exception as exc:  # noqa: BLE001 -- any invalid output, one fate
            record.update(
                is_error=True, error_subtype="track_output_invalid",
                detail=(f"child output failed validation ({exc}); ZERO "
                        "findings were injected"))
            return record
        record["output"] = obj
        record["findings_rows"] = rows
        record["ran"] = bool(status.get("ran"))
        if record["ran"]:
            record["error_subtype"] = "ran_findings" if rows else "ran_clean"
        else:
            record["error_subtype"] = status.get("refusal_subtype") or "refused"
        record["detail"] = status.get("detail", "")
        return record
    except Exception as exc:  # noqa: BLE001 -- the client must never raise
        record.update(is_error=True, error_subtype="track_crashed",
                      detail=f"{type(exc).__name__}: {exc}")
        return record
    finally:
        record["wall_seconds"] = round(time.monotonic() - t0, 2)
        if proc is not None and proc.returncode is None:
            try:
                # Cancelled, or an unexpected error: still SIGTERM first so
                # the child seals its run, then make sure nothing is pending.
                await _stop(proc, "cancelled")
                await _recover("cancelled")
            except BaseException as exc:  # noqa: BLE001 -- cleanup, but SAY it failed
                if proc.returncode is None:
                    _kill_subprocess_group(proc)
                record["detail"] = (str(record.get("detail", "")) +
                                    f" [child cleanup failed: "
                                    f"{type(exc).__name__}: {exc} -- the "
                                    f"process may be orphaned]").strip()
        if communication is not None and not communication.done():
            communication.cancel()
            await asyncio.gather(communication, return_exceptions=True)
        subtype = record["error_subtype"]
        rows = len(record["findings_rows"])
        if subtype == "ran_findings":
            _emit(f"{rows} finding row(s)", done=True)
        elif subtype == "ran_clean":
            _emit("clean", done=True)
        else:
            # A refusal, a timeout or a crash. Naming the subtype is the point:
            # "did not run" and "ran and found nothing" are different facts.
            _emit(str(subtype or "no result"), done=True)
        if verbose:
            print(f"[{label}] {record['error_subtype']}: "
                  f"{len(record['findings_rows'])} row(s), "
                  f"{record['wall_seconds']}s")


from .track_contracts import _track_timeout as _track_timeout




DEFAULT_EFFORT = "high"
DEFAULT_MODEL = "opus"


def _build_claude_cmd(system_prompt, allowed_tools, model=DEFAULT_MODEL,
                      json_schema=None, budget_usd=None, effort=DEFAULT_EFFORT,
                      paper_dir=None, denied_tools=None, backend=None,
                      max_turns=None, internet=False, mcp_stage=None, vision=False,
                      run_slug=None):
    """Image model invocation: guarded CLI execution without forensic MCP."""
    if any(t.startswith("mcp__") for t in allowed_tools) or mcp_stage:
        raise ValueError("Image screening does not expose forensic MCP tools")
    return build_invocation(resolve_backend(backend), system_prompt=system_prompt,
                            allowed_tools=allowed_tools, model=model, effort=effort,
                            json_schema=json_schema, budget_usd=budget_usd,
                            paper_dir=paper_dir, denied_tools=denied_tools,
                            max_turns=max_turns, internet=internet, vision=vision,
                            run_slug=run_slug, forensic_mcp=False)
