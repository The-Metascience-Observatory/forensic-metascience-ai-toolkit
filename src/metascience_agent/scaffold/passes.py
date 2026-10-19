"""Running one pass: prompt in, schema-validated JSON out, everything on disk.

Uses the `claude` CLI in print mode with `--json-schema`, the same binary the
rest of the pipeline drives (`llm_backend`), but with EVERY tool disabled: the
paper is inline, there is nothing to fetch, and a model that can reach for a
tool will sometimes read a file instead of the text it was given. The raw CLI
result, the prompt, and the parsed output are all written beside each other so
a run can be audited without re-running it.

A schema violation is REPORTED, not raised: the output is still saved, the
problems ride along, and the caller decides. A CLI failure is raised, because
there is then nothing to save.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from . import schema as _schema

DEFAULT_MODEL = "opus"


class PassFailed(RuntimeError):
    pass


def _claude_binary() -> str:
    exe = shutil.which("claude")
    if not exe:
        raise PassFailed("the `claude` CLI is not on PATH")
    return exe


def run_pass(name: str, prompt: str, out_dir: str | Path, *, model: str = DEFAULT_MODEL,
             timeout_s: int = 3600, retries: int = 1, schema: dict | None = None,
             resume_session: str | None = None, persist_session: bool = False,
             tools: str = "", extra_meta: dict | None = None) -> dict[str, Any]:
    """Run one pass. Returns `{data, problems, meta}`; raises `PassFailed` when
    the CLI produced nothing usable after `retries` further attempts.

    `--tools ""` is what makes the reading stage unable to search: MEASURED
    2026-09-05 on claude CLI 2.1.261, the `system.init` event then lists ZERO
    tools, against 30 by default. The paper is inline and nothing else is
    reachable (the repo's principle, `parallel.py`: default-off has to mean
    unavailable, not merely unmentioned).

    `resume_session` continues an earlier print-mode session so that a later
    prompt is read WITH the earlier context but AFTER it -- the mechanism the
    linear runner uses to serve a paper in order. `persist_session` must be on
    for the first call of such a chain.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sch = schema if schema is not None else _schema.pass_schema(name)
    (out / f"{name}.prompt.md").write_text(prompt, encoding="utf-8")
    (out / f"{name}.schema.json").write_text(json.dumps(sch, indent=1), encoding="utf-8")
    cmd = [_claude_binary(), "-p", "--output-format", "json", "--json-schema",
           json.dumps(sch), "--model", model, "--tools", tools]
    if resume_session:
        cmd += ["--resume", resume_session]
    if not (persist_session or resume_session):
        cmd.append("--no-session-persistence")
    last_err: str | None = None
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, input=prompt, text=True, capture_output=True,
                                  timeout=timeout_s, check=False)
        except subprocess.TimeoutExpired:
            last_err = f"attempt {attempt}: timed out after {timeout_s}s"
            continue
        elapsed = time.time() - t0
        (out / f"{name}.raw.json").write_text(proc.stdout, encoding="utf-8")
        if proc.stderr.strip():
            (out / f"{name}.stderr.txt").write_text(proc.stderr, encoding="utf-8")
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            last_err = (f"attempt {attempt}: CLI output was not JSON ({exc}); "
                        f"exit {proc.returncode}; stderr: {proc.stderr[:400]!r}")
            continue
        data = result.get("structured_output")
        if result.get("is_error") or data is None:
            last_err = (f"attempt {attempt}: no structured output; is_error="
                        f"{result.get('is_error')}; result={str(result.get('result'))[:400]!r}")
            continue
        problems: list[str] = []
        try:
            import jsonschema
            validator = jsonschema.Draft202012Validator(sch)
            for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
                problems.append(f"{'/'.join(str(p) for p in err.path)}: {err.message[:200]}")
        except ImportError:
            problems.append("jsonschema not installed; output not validated")
        meta = {**(extra_meta or {}), "model": model, "attempt": attempt, "elapsed_s": round(elapsed, 1),
                "cost_usd": result.get("total_cost_usd"), "num_turns": result.get("num_turns"),
                "usage": result.get("usage"), "session_id": result.get("session_id"),
                "n_schema_problems": len(problems)}
        (out / f"{name}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False),
                                          encoding="utf-8")
        (out / f"{name}.meta.json").write_text(json.dumps({**meta, "problems": problems}, indent=1),
                                               encoding="utf-8")
        return {"data": data, "problems": problems, "meta": meta}
    raise PassFailed(f"pass {name} failed: {last_err}")


def load_pass(name: str, out_dir: str | Path) -> dict[str, Any] | None:
    """A previously saved pass, or None. Lets a run resume after a later pass failed."""
    p = Path(out_dir) / f"{name}.json"
    if not p.is_file():
        return None
    meta_p = Path(out_dir) / f"{name}.meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.is_file() else {}
    return {"data": json.loads(p.read_text(encoding="utf-8")),
            "problems": meta.get("problems", []), "meta": meta}
