"""The prompt must be on the child's stdin before the child starts waiting.

MEASURED 2026-10-18 (v1.83.0, `metascience batch` on
statcheck_pvalue_errors/working_set, 10 claude + 10 grok workers): both
analysis stages of 10.3389--fpsyg.2011.00199 exited 1 at 0 tokens with
"Warning: no stdin data received in 3s, proceeding without it ... Error:
Input must be provided either through stdin or as a prompt argument when
using --print". `_run_stage` spawned `claude -p` on a PIPE and wrote the
prompt only after `create_subprocess_exec` returned control to it, and with
twenty stages sharing one event loop that took longer than the CLI's 3 s
wait. Reproduced against the real CLI (2.1.301) by blocking the loop 5 s
between spawn and write; a pre-filled file as stdin passed the same delay.

The child below behaves like `claude -p`: it waits a short time for stdin
data and exits 1 if none came. The spawn is wrapped so the loop is blocked
after the child starts, which is what a busy batch does.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import sys
import time

from metascience_agent import runtime
from metascience_agent.llm_backend import CLAUDE, GROK, Invocation

#: Waits CHILD_WAIT seconds for stdin, like the CLI's 3 s, then exits 1.
CHILD_WAIT = 0.5
#: How long the event loop is blocked after the spawn. Longer than CHILD_WAIT.
LOOP_BLOCK = 1.5

_CHILD = f"""
import hashlib, json, select, sys
ready, _, _ = select.select([sys.stdin], [], [], {CHILD_WAIT})
data = sys.stdin.buffer.read() if ready else b""
if not data:
    print("Error: Input must be provided either through stdin", file=sys.stderr)
    sys.exit(1)
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False,
    "result": hashlib.sha256(data).hexdigest() + " " + str(len(data)),
    "total_cost_usd": 0.0, "usage": {{"input_tokens": 1, "output_tokens": 1}}}}))
"""


def _invocation(**kw) -> Invocation:
    base = dict(argv=[sys.executable, "-c", _CHILD], prompt_delivery="stdin",
                workdir=None, env_overlay={}, cleanup=lambda: None,
                backend=CLAUDE, forensic_mcp=False)
    base.update(kw)
    return Invocation(**base)


async def _no_guard(*a, **k):
    return None


def _run(inv, prompt):
    return asyncio.run(runtime._run_stage(
        inv, prompt, preflight=lambda backend: None, guard=_no_guard,
        build_env=lambda: {"PATH": "/usr/bin:/bin"}))


def test_prompt_survives_a_blocked_event_loop(monkeypatch):
    real_exec = asyncio.create_subprocess_exec

    async def spawn_then_block(*a, **kw):
        proc = await real_exec(*a, **kw)
        time.sleep(LOOP_BLOCK)  # another coroutine doing synchronous work
        return proc

    monkeypatch.setattr(runtime.asyncio, "create_subprocess_exec", spawn_then_block)
    # Larger than a 64 KB pipe buffer, so a partial delivery would show too.
    prompt = "paper text " * 30_000
    stage = _run(_invocation(), prompt)
    assert stage["return_code"] == 0, stage
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    assert stage["result"] == f"{digest} {len(prompt.encode())}"


def test_stdin_delivery_hands_the_child_a_prefilled_file(monkeypatch):
    seen = {}

    class _Done(Exception):
        pass

    async def capture(*a, **kw):
        stdin = kw["stdin"]
        seen["is_file"] = isinstance(stdin, io.IOBase)
        seen["content"] = stdin.read() if seen["is_file"] else None
        raise _Done

    monkeypatch.setattr(runtime.asyncio, "create_subprocess_exec", capture)
    try:
        _run(_invocation(), "the prompt")
    except _Done:
        pass
    assert seen == {"is_file": True, "content": b"the prompt"}


def test_prompt_file_delivery_still_gets_a_pipe(monkeypatch, tmp_path):
    """Grok reads `--prompt-file`; its stdin stays a pipe, closed at once."""
    seen = {}

    class _Done(Exception):
        pass

    async def capture(*a, **kw):
        seen["stdin"] = kw["stdin"]
        raise _Done

    monkeypatch.setattr(runtime.asyncio, "create_subprocess_exec", capture)
    path = tmp_path / "prompt.md"
    try:
        _run(_invocation(prompt_delivery="prompt_file", prompt_path=path,
                         backend=GROK), "the prompt")
    except _Done:
        pass
    assert seen["stdin"] is asyncio.subprocess.PIPE
    assert path.read_text() == "the prompt"
