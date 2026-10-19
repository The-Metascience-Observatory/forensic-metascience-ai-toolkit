"""Proactive Claude Code usage-limit guard for long headless runs.

A batch sweep over a corpus can run for hours and will happily walk into the
5-hour session limit mid-paper. What that produces is worse than a stall: the
`claude` CLI returns an error result, the stage yields no findings, and the
paper is written to `failed.jsonl` having already spent whatever it spent. The
run keeps going and burns the rest of the corpus the same way.

The interactive `/usage` gauge is reachable headlessly: `claude -p "/usage"
--output-format json` returns a `result` text containing lines like:

    Current session: 27% used · resets Jul 26, 11:30pm (America/New_York)
    Current week (all models): 53% used · resets Jul 31, 2:59am (America/New_York)

This module probes that, parses BOTH the 5-hour **session** percentage and the
**weekly** one, and — when either reaches its threshold — PAUSES before the next
model call, polling every `poll_min` minutes until the window resets (the
percentage drops).

The weekly limit needs its own gate because the two windows fail differently. A
session at 95% resets within hours, so pausing is the right response. A week at
99% may not reset for days, and a batch that waits for it is not paused, it is
hung. So the weekly gate STOPS rather than waits, unless a caller explicitly
asks otherwise.

Measured 2026-07-31: a 10-paper batch was launched at session 5% / week 99%.
The session gate waved it through, and it ran for 25 minutes against a quota
that was already spent, completing nothing. Both figures were parsed and logged
at the time; only one of them was acted on.
Probes are interval-gated (each probe itself consumes a little session quota),
so we only actually check every `interval_min`.

It is wired into `agent._run_stage`, so EVERY `claude` invocation the pipeline
makes is guarded automatically (sweep, editorial, and JSON-repair alike).

Codex (`--backend codex`) is guarded by the SAME gates from a different
probe: `codex app-server`'s JSON-RPC `account/rateLimits/read` -- the call
the codex TUI's own status line makes -- returns windows with `usedPercent`,
duration and reset time. Duration identifies the window: primary can be the
week when no five-hour gauge is reported. Same thresholds and fail-open. Grok has
no probe at all and is reported as UNSUPPORTED, which is a different fact
from "the probe broke".

Antigravity (`--backend antigravity`) answers `agy -p /usage --output-format
json` WITHOUT a model turn (free; measured 2026-10-18, agy 1.4.2): quota
groups (Gemini; Claude-and-GPT; Gemini 4 Argon) of buckets with a `window`
(`5h`/`weekly`) and a `remaining_fraction`. Used % is 1 - remaining. Only the
groups the run's model draws on count: a Gemini run must not pause on a spent
Claude bucket. With no model known, every group counts (the cautious reading).

Everything here FAILS OPEN: a probe that times out, crashes, or returns
unparseable text lets the run continue. The guard exists to avoid wasting spend,
and must never itself become the reason a batch stops.

Configuration (all optional):
    METASCIENCE_USAGE_GUARD=0         disable entirely (--no-usage-guard)
    METASCIENCE_USAGE_THRESHOLD=90    pause at/above this session %
    METASCIENCE_USAGE_WEEK_THRESHOLD=97  stop at/above this weekly % (see below)
    METASCIENCE_USAGE_IGNORE_WEEKLY=1 skip the weekly STOP; session pause still runs
                                      (--ignore-weekly-limit). The /usage weekly %
                                      does not include extra usage credits.
    METASCIENCE_USAGE_WEEK_WAIT=0     1 = wait for the weekly window instead of stopping
    METASCIENCE_USAGE_INTERVAL_MIN=25 minimum minutes between probes
    METASCIENCE_USAGE_POLL_MIN=15     minutes to wait between re-checks while paused
    METASCIENCE_USAGE_MAX_WAIT_MIN=0  give up waiting after this long (0 = wait indefinitely)

Manual check:  python -m forensic_metascience_ai_toolkit.usage_guard
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import weakref

from rich.console import Console
from rich.markup import escape as _escape_markup

_SESSION_RE = re.compile(r"Current session:\s*(\d+)\s*%\s*used", re.I)
# Anchored on "(all models)": `/usage` also prints per-model week lines
# ("Current week (Fable): ...") which are not the limit we care about.
_WEEK_RE = re.compile(r"Current week \(all models\):\s*(\d+)\s*%\s*used", re.I)

PROBE_TIMEOUT_SEC = 60.0
#: codex's app-server answers rateLimits in ~1 s once initialised; 25 s is
#: the ceiling measured to cover a cold binary start.
CODEX_PROBE_TIMEOUT_SEC = 25.0
CODEX_PROBE_CLIENT = {"name": "metascience-usage", "title": "metascience usage probe",
                      "version": "0.1"}


class _Unsupported:
    """Sentinel: this backend has no usage probe.

    Distinct from ``(None, None)``, which already means "the probe broke".
    Reusing that pair would make "Grok has no /usage" indistinguishable from
    "the guard is broken" -- the failure this module exists to keep named.
    """

    def __repr__(self) -> str:
        return "UNSUPPORTED"


UNSUPPORTED = _Unsupported()

# Pause at/above this session %. Not lower: the probe interval means usage can
# climb between checks, so the gap below 100% is the headroom that keeps a
# long-running stage from dying mid-sweep.
DEFAULT_THRESHOLD_PCT = 90.0

# Stop at/above this weekly %. Higher than the session threshold because the
# consequence differs: a session gate costs a wait, a weekly gate costs the rest
# of the batch, so it should not fire on headroom that is still usable.
DEFAULT_WEEK_THRESHOLD_PCT = 97.0


class WeeklyLimitReached(RuntimeError):
    """The weekly quota is spent, so the batch stops rather than waits.

    The two windows fail differently and want different responses. A session at
    95% resets within hours: pausing is right, and the work resumes. A week at
    99% may not reset for days, and a batch that waits for it is not paused, it
    is hung -- and it will look, from outside, exactly like a batch that is
    working.

    Raising is also what lets the batch runner record where it stopped, so the
    run is resumable instead of half-finished and unlabelled.

    Override when extra usage credits will cover the spend: the `/usage`
    weekly percentage does not include them. ``--ignore-weekly-limit`` /
    ``METASCIENCE_USAGE_IGNORE_WEEKLY=1`` skips this stop and keeps the
    session pause. ``--no-usage-guard`` / ``METASCIENCE_USAGE_GUARD=0``
    disables the guard entirely.
    """


# Named in the exception so an operator who hits the stop is told how to
# proceed. Extra usage credits are a real Anthropic product; `/usage` still
# reports the included weekly quota at 100%.
WEEKLY_OVERRIDE_HINT = (
    "Re-run with --ignore-weekly-limit if extra usage credits will cover "
    "the spend (the weekly % does not include them), or --no-usage-guard "
    "to disable the usage guard entirely."
)

# Async, not threading: the pipeline runs stages on an event loop and the batch
# runner analyzes several papers concurrently. A blocking sleep here would stall
# the loop, so in-flight subprocesses would stop being drained while we wait.
# Awaiting instead lets papers already mid-analysis finish while no NEW call
# starts. One lock per loop — a process may call asyncio.run() more than once,
# and an asyncio.Lock cannot be reused across loops.
_locks: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_last_probe = 0.0


def _get_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _locks.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _locks[loop] = lock
    return lock


def _envf(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_on(name: str) -> bool:
    """True only for the literal ``1``. Same convention as WEEK_WAIT."""
    return os.environ.get(name, "0") == "1"


def apply_cli_overrides(
    *,
    no_usage_guard: bool = False,
    ignore_weekly_limit: bool = False,
) -> None:
    """Map CLI flags onto the env knobs ``guard()`` reads.

    The guard has no CLI of its own. ``analyze``, ``batch``, and the example
    batch script all call this so a flag that exists on one command cannot
    silently fail to exist on another. False means "leave the env alone",
    never "turn the override off": an operator who exported
    ``METASCIENCE_USAGE_GUARD=0`` must not have it undone by a default flag.
    """
    if no_usage_guard:
        os.environ["METASCIENCE_USAGE_GUARD"] = "0"
        _log("disabled (--no-usage-guard / METASCIENCE_USAGE_GUARD=0)")
    if ignore_weekly_limit:
        os.environ["METASCIENCE_USAGE_IGNORE_WEEKLY"] = "1"
        _log("weekly stop overridden (--ignore-weekly-limit); "
             "session pause still runs")


def _log(msg: str) -> None:
    print(f"  [usage_guard] {msg}", file=sys.stderr, flush=True)


# Separate Console instance (not cli.py's) because this module is imported by
# agent.py and the batch script too, both of which run headlessly with no
# other rich usage -- this must not create a dependency on cli.py importing
# first. `stderr=True` matches `_log`'s channel; rich auto-detects whether
# stderr is a TTY and drops the color codes to plain text when it isn't, so a
# batch run redirected to a log file gets readable text, not raw escapes.
_warn_console = Console(stderr=True, highlight=False)


def _warn(msg: str) -> None:
    """Same channel as `_log`, but for the moments the guard actually
    INTERVENES -- pausing, stopping, waiting, or continuing past an override
    -- rather than routine telemetry (the plain "X% used" probe line stays on
    `_log`). Bold yellow so this can't be mistaken for a hang: the whole
    reason to add this was a batch that looked frozen when it was actually
    stopped on a weekly-quota message an operator scrolled past in
    undifferentiated text. `msg` is escaped because it can carry `%`
    figures assembled at runtime, not a literal safe to feed to rich markup
    as-is."""
    _warn_console.print(
        f"  [bold yellow]⚠  [usage_guard][/bold yellow] {_escape_markup(msg)}")


def _probe_env() -> dict[str, str]:
    """Same env hygiene as the analysis stages: strip CLAUDECODE so a parent
    Claude Code session doesn't bleed into the probe."""
    return {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}


def parse_usage(text: str) -> tuple[int | None, int | None]:
    """Extract (session_pct, week_pct) from `/usage` output text."""
    s = _SESSION_RE.search(text or "")
    w = _WEEK_RE.search(text or "")
    return (int(s.group(1)) if s else None, int(w.group(1)) if w else None)


def _pct(value) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def parse_codex_rate_limits(response: dict) -> dict:
    """Reduce an `account/rateLimits/read` JSON-RPC response to one flat dict.

    On 2026-09-09 the live primary window was 10080 minutes, with no secondary
    window. Identify gauges by duration, not position. Historical responses
    without duration retain the old positional interpretation. An explicitly
    unfamiliar duration stays unknown. Prefer the main Codex bucket, never
    a separate Spark bucket. Missing gauges are None, never zero.
    """
    result = (response or {}).get("result") or {}
    rl = (result.get("rateLimitsByLimitId") or {}).get("codex") or result.get("rateLimits") or {}
    pr, se = {}, {}
    for position, window in (("session", rl.get("primary")), ("week", rl.get("secondary"))):
        if not isinstance(window, dict):
            continue
        duration = window.get("windowDurationMins")
        if duration == 300 or (duration is None and position == "session"):
            pr = window
        elif duration == 10080 or (duration is None and position == "week"):
            se = window
    return {
        "session_pct": _pct(pr.get("usedPercent")),
        "session_resets_at": pr.get("resetsAt"),
        "session_window_min": pr.get("windowDurationMins"),
        "week_pct": _pct(se.get("usedPercent")),
        "week_resets_at": se.get("resetsAt"),
        "plan": rl.get("planType"),
        "reached": rl.get("rateLimitReachedType"),
    }


def _fmt_reset(epoch) -> str:
    try:
        return time.strftime("%H:%M", time.localtime(float(epoch)))
    except (TypeError, ValueError, OSError, OverflowError):
        return "?"


async def probe_codex_usage(timeout: float = CODEX_PROBE_TIMEOUT_SEC):
    """Return (session_pct, week_pct) from codex's app-server, or (None, None).

    Speaks the app-server's stdio JSON-RPC: `initialize`, the `initialized`
    notification, then `account/rateLimits/read` (id 2), and kills the
    server once that answer arrives. Every failure -- no binary, a hung
    start, malformed lines, no answer before the deadline -- fails OPEN,
    exactly like the Claude probe: the guard must never be why a run stops.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "codex", "app-server",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=_probe_env(),
        )
    except OSError as e:  # `codex` not on PATH -- fail open
        _log(f"codex probe failed to start: {e}")
        return (None, None)

    async def _talk():
        for msg in (
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"clientInfo": dict(CODEX_PROBE_CLIENT)}},
            {"jsonrpc": "2.0", "method": "initialized", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "account/rateLimits/read",
             "params": {}},
        ):
            proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
        await proc.stdin.drain()
        while True:
            line = await proc.stdout.readline()
            if not line:
                return None  # server exited without answering
            try:
                obj = json.loads(line.decode("utf-8", errors="replace"))
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("id") == 2:
                return obj

    try:
        answer = await asyncio.wait_for(_talk(), timeout=timeout)
    except asyncio.TimeoutError:
        _log(f"codex probe timed out after {timeout:.0f}s")
        answer = None
    except Exception as e:  # noqa: BLE001 -- fail open on anything
        _log(f"codex probe failed: {e}")
        answer = None
    finally:
        try:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass  # the server already exited; nothing to reap
        except Exception as e:  # noqa: BLE001 -- cleanup must not mask the reading
            _log(f"codex probe cleanup: {e}")
    if answer is None:
        return (None, None)
    if answer.get("error"):
        _log(f"codex probe refused: {answer['error']}")
        return (None, None)
    parsed = parse_codex_rate_limits(answer)
    if parsed["session_pct"] is not None:
        _log(f"codex 5h window resets {_fmt_reset(parsed['session_resets_at'])}"
             f" (plan {parsed['plan'] or '?'})")
    return (parsed["session_pct"], parsed["week_pct"])


#: `agy -p /usage` returns in well under a second; the ceiling covers a cold
#: binary start and the keyring unlock.
ANTIGRAVITY_PROBE_TIMEOUT_SEC = 45.0


def parse_antigravity_usage(payload: dict, model: str | None = None
                            ) -> tuple[int | None, int | None]:
    """(session_pct, week_pct) USED from agy's `/usage` JSON, or (None, None).

    The worst bucket of each window across the groups `model` draws on. A
    group is matched by its name ("Gemini Models", "Gemini 4 Argon", "Claude
    and GPT models"); an unknown model family counts every group."""
    from .llm_backend import antigravity_model_family
    data = (((payload or {}).get("command") or {}).get("data") or {})
    groups = data.get("groups")
    if not isinstance(groups, list):
        return (None, None)
    family = antigravity_model_family(model)
    argon = "argon" in (model or "").lower()

    def _counts(name: str) -> bool:
        low = name.lower()
        if family is None:
            return True
        if family == "third_party":
            return "claude" in low or "gpt" in low
        if "argon" in low:
            return argon
        return low.startswith("gemini")

    worst: dict[str, int] = {}
    for group in groups:
        if not isinstance(group, dict) or not _counts(str(group.get("name") or "")):
            continue
        for bucket in group.get("buckets") or []:
            if not isinstance(bucket, dict):
                continue
            window = bucket.get("window")
            remaining = bucket.get("remaining_fraction")
            if window not in ("5h", "weekly") or not isinstance(remaining, (int, float)):
                continue
            used = int(round((1.0 - float(remaining)) * 100))
            key = "session" if window == "5h" else "week"
            worst[key] = max(worst.get(key, 0), used)
    return (worst.get("session"), worst.get("week"))


async def probe_antigravity_usage(model: str | None = None,
                                  timeout: float = ANTIGRAVITY_PROBE_TIMEOUT_SEC):
    """(session_pct, week_pct) from `agy -p /usage`, or (None, None).

    Runs under the operator's real HOME (the account, not a sandbox), with
    slash commands enabled -- that is what `/usage` is."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "agy", "-p", "/usage", "--output-format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "AGY_CLI_DISABLE_AUTO_UPDATE": "true"},
        )
    except OSError as e:
        _log(f"agy probe failed to start: {e}")
        return (None, None)
    try:
        out, _err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except (asyncio.TimeoutError, TimeoutError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        _log(f"agy probe timed out after {timeout:.0f}s")
        return (None, None)
    try:
        payload = json.loads(out.decode("utf-8", "replace"))
    except (json.JSONDecodeError, ValueError):
        _log("agy probe returned non-JSON")
        return (None, None)
    if not isinstance(payload, dict) or payload.get("status") != "SUCCESS":
        _log(f"agy probe refused: {str((payload or {}).get('error'))[:200]}")
        return (None, None)
    return parse_antigravity_usage(payload, model)


async def probe_usage(timeout: float = PROBE_TIMEOUT_SEC, backend=None,
                      model: str | None = None):
    """Return (session_pct, week_pct), ``UNSUPPORTED``, or (None, None).

    ``UNSUPPORTED`` means this backend has no probe (Grok). ``(None, None)``
    means the probe broke -- fail open, as before. Claude answers through
    `claude -p "/usage"`; codex through `probe_codex_usage`.
    """
    from .llm_backend import resolve_backend

    be = resolve_backend(backend)
    if not be.supports_usage_probe:
        return UNSUPPORTED
    if be.name == "antigravity":
        return await probe_antigravity_usage(model=model)
    if be.name == "codex":
        return await probe_codex_usage(min(timeout, CODEX_PROBE_TIMEOUT_SEC)
                                       if timeout != PROBE_TIMEOUT_SEC
                                       else CODEX_PROBE_TIMEOUT_SEC)
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", "/usage", "--output-format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_probe_env(),
        )
    except OSError as e:  # `claude` not on PATH — fail open
        _log(f"probe failed to start: {e}")
        return (None, None)
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        _log(f"probe timed out after {timeout:.0f}s")
        return (None, None)
    except Exception as e:  # noqa: BLE001 — fail open on anything
        _log(f"probe failed: {e}")
        return (None, None)
    try:
        text = json.loads(stdout.decode("utf-8", errors="replace")).get("result", "")
    except (json.JSONDecodeError, AttributeError, UnicodeDecodeError) as e:
        _log(f"probe returned unparseable output: {e}")
        return (None, None)
    if not isinstance(text, str):
        return (None, None)
    return parse_usage(text)


async def guard(backend=None, model: str | None = None) -> None:
    """Interval-gated usage check. If the 5-hour session is at/over the threshold,
    wait until it resets (re-checking every poll_min). Safe to await before every
    model call: it only actually probes once per interval. Concurrent callers
    serialize on the lock, so all workers pause together."""
    if os.environ.get("METASCIENCE_USAGE_GUARD", "1") == "0":
        return
    from .llm_backend import resolve_backend
    if not resolve_backend(backend).supports_usage_probe:
        return

    threshold = _envf("METASCIENCE_USAGE_THRESHOLD", DEFAULT_THRESHOLD_PCT)
    week_threshold = _envf("METASCIENCE_USAGE_WEEK_THRESHOLD",
                           DEFAULT_WEEK_THRESHOLD_PCT)
    week_wait = _env_on("METASCIENCE_USAGE_WEEK_WAIT")
    ignore_weekly = _env_on("METASCIENCE_USAGE_IGNORE_WEEKLY")
    interval = _envf("METASCIENCE_USAGE_INTERVAL_MIN", 25) * 60
    poll = max(_envf("METASCIENCE_USAGE_POLL_MIN", 15) * 60, 1.0)
    max_wait = _envf("METASCIENCE_USAGE_MAX_WAIT_MIN", 0) * 60

    global _last_probe
    async with _get_lock():
        now = time.monotonic()
        if _last_probe and now - _last_probe < interval:
            return
        _last_probe = now

        probed = await probe_usage(backend=backend, **({"model": model} if model else {}))
        if probed is UNSUPPORTED:
            return
        sess, week = probed
        if sess is None and week is None:
            return  # fail open
        _log(f"session {sess}% / week {week}% used")

        # Checked BEFORE the session gate. A run at session 5% / week 99% is
        # exactly the case that went unnoticed: the session gate waves it
        # through, and it burns 25 minutes against a quota already spent.
        # Ordering it first also means we never sit in a session pause waiting
        # for a window whose reset cannot help us.
        if week is not None and week >= week_threshold:
            msg = (f"weekly quota at {week}% (>= {week_threshold:.0f}%). "
                   f"Session is at {sess}%, which is why nothing else stopped this.")
            if ignore_weekly:
                # Extra usage credits are not in the /usage weekly %. The
                # session window can still exhaust independently, so that
                # pause is left in place.
                _warn(msg + " Continuing: METASCIENCE_USAGE_IGNORE_WEEKLY=1 "
                            "(the /usage weekly % does not include extra "
                            "usage credits).")
            elif week_wait:
                _warn(msg + " Waiting, as requested by METASCIENCE_USAGE_WEEK_WAIT=1.")
                waited_week = 0.0
                while week is not None and week >= week_threshold:
                    if max_wait and waited_week >= max_wait:
                        _warn(f"weekly still at {week}% after {waited_week / 60:.0f} min "
                              "(max wait reached) — continuing anyway")
                        break
                    await asyncio.sleep(poll)
                    waited_week += poll
                    sess, week = await probe_usage(backend=backend, **({"model": model} if model else {}))
                    _last_probe = time.monotonic()
                    if week is not None:
                        _log(f"re-check: week {week}% used")
            else:
                _warn(msg + " Stopping: the weekly window may not reset for days, "
                            "and a batch waiting on it is hung, not paused. "
                            + WEEKLY_OVERRIDE_HINT +
                            " Set METASCIENCE_USAGE_WEEK_WAIT=1 to wait instead.")
                raise WeeklyLimitReached(f"{msg} {WEEKLY_OVERRIDE_HINT}")

        waited = 0.0
        while sess is not None and sess >= threshold:
            if max_wait and waited >= max_wait:
                _warn(f"still at {sess}% after {waited / 60:.0f} min "
                      f"(max wait reached) — continuing anyway")
                return
            _warn(f"session {sess}% >= {threshold:.0f}% — pausing {poll / 60:.0f} min "
                  f"for window reset (week {week}%)...")
            await asyncio.sleep(poll)
            waited += poll
            sess, week = await probe_usage(backend=backend, **({"model": model} if model else {}))
            _last_probe = time.monotonic()
            if sess is not None:
                _log(f"re-check: session {sess}% used")
        if waited:
            _log(f"resuming after {waited / 60:.0f} min paused "
                 f"(session {sess if sess is not None else '?'}%).")


def _reset_state_for_tests() -> None:
    """Clear the interval gate so a test can force the next call to probe."""
    global _last_probe
    _last_probe = 0.0


if __name__ == "__main__":  # quick manual check: print current usage
    _be = sys.argv[1] if len(sys.argv) > 1 else None
    _r = asyncio.run(probe_usage(backend=_be))
    if _r is UNSUPPORTED:
        print(f"backend {_be}: no usage probe")
    else:
        print(f"backend {_be or 'claude'}: session={_r[0]}% week={_r[1]}%")
