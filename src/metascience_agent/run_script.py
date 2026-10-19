"""Sandboxed code execution for the science-error agent.

The Phase-0 resolution of guardrail 4 (docs/specs/pipeline.md section 10):
the CLI provides no shell sandbox, so code execution is OUR MCP tool and the
sandbox is enforced HERE, identically on every backend. Backend shells stay
denied; this is the only route from a model to running code, and it is
network-off by construction -- paper text is untrusted input, and a shell
with network is an exfiltration vector.

Sandbox ladder, probed once per process:
  bwrap   -- whole filesystem read-only, only the scripts dir writable,
             /tmp a private tmpfs, no network (the full contract)
  unshare -- user+net namespaces: network-off guaranteed, filesystem
             confinement by convention only (recorded as the weaker level)
  neither -- structured refusal, `refusal: "code_disabled"`. Never a shell.

Scripts are persisted BEFORE they run (`NNN_label.py` under
`<paper_dir>/analysis_code/`) -- a finding's `reproduction_kind: "script"`
points at that file, and `write_review_outputs` carries the directory into
the review dir. Every load-bearing number in a finding must come from the
CAPTURED OUTPUT returned here, never from the model's own arithmetic.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PAPER_DIR_ENV = "METASCIENCE_PAPER_DIR"

#: Which RUN these scripts belong to. Set by the pipeline on the same channel
#: as `PAPER_DIR_ENV` -- into the MCP server's environment, never into anything
#: the model can write -- so a second run analysing the same paper directory
#: gets its own scripts directory rather than sharing one.
#:
#: WHY IT HAS TO EXIST. `seq` below is chosen by COUNTING the scripts already
#: on disk, with no reservation. Two concurrent runs both counted 6, both wrote
#: `007_<label>.py`, and the second `write_text` silently replaced the first's
#: code -- under a `007_<label>.d` workdir both sandboxes then executed in.
#: The persisted script is the audit artefact behind every
#: `reproduction_kind: "script"` finding, so that is a finding citing someone
#: else's code. Worse, `parallel.write_parallel_outputs` MOVES this directory
#: into the finishing run's archive, taking the other run's scripts with it.
#:
#: Unset is the normal single-run case and keeps the flat layout exactly as it
#: was, so nothing that reads an archived run has to know about this.
RUN_SLUG_ENV = "METASCIENCE_RUN_SLUG"

SCRIPTS_DIRNAME = "analysis_code"

_MAX_CODE_CHARS = 100_000
_MAX_OUTPUT_CHARS = 40_000
_DEFAULT_TIMEOUT_S = 60
_MAX_TIMEOUT_S = 300

#: Probed once; tests monkeypatch this. None = not yet probed.
_SANDBOX: str | None = None


def _probe_sandbox() -> str:
    """Which isolation this machine can actually enforce. Cached; the probe
    RUNS the mechanism rather than trusting `which` (a bwrap that cannot
    create namespaces on this kernel must not be reported as a sandbox)."""
    global _SANDBOX
    if _SANDBOX is not None:
        return _SANDBOX
    for name, argv in (
        ("bwrap", ["bwrap", "--ro-bind", "/", "/", "--unshare-net", "true"]),
        ("unshare", ["unshare", "-rn", "true"]),
    ):
        if shutil.which(argv[0]) is None:
            continue
        try:
            probe = subprocess.run(argv, capture_output=True, timeout=10)
            if probe.returncode == 0:
                _SANDBOX = name
                return _SANDBOX
        except Exception:
            continue
    _SANDBOX = "none"
    return _SANDBOX


def _slug(label: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", (label or "script")).strip("_.")
    return (s or "script")[:60]


def _clip(text: str) -> tuple[str, bool]:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text, False
    return (text[:_MAX_OUTPUT_CHARS]
            + f"\n...[truncated, {len(text)} chars total]"), True


def _refuse(reason: str, refusal: str) -> dict:
    return {"success": False, "refusal": refusal, "error": reason,
            "sandbox": _probe_sandbox()}


def _sandbox_argv(sandbox: str, scripts_dir: Path, workdir: Path,
                  script: Path) -> list[str]:
    inner = [sys.executable, "-I", str(script)]
    if sandbox == "bwrap":
        return ["bwrap",
                "--ro-bind", "/", "/",
                "--dev", "/dev",
                "--tmpfs", "/tmp",
                "--bind", str(scripts_dir), str(scripts_dir),
                "--unshare-net",
                "--die-with-parent",
                "--chdir", str(workdir),
                *inner]
    # unshare: network isolation only; cwd discipline is convention.
    return ["unshare", "-rn", *inner]


def run_python_script(code: str, label: str = "script",
                      timeout_seconds: int = _DEFAULT_TIMEOUT_S,
                      paper_dir: str | None = None) -> dict:
    """Persist `code`, execute it in the strongest available sandbox, and
    return its captured output. Never raises; never runs unsandboxed."""
    if not isinstance(code, str) or not code.strip():
        return _refuse("`code` is empty", "empty_code")
    if len(code) > _MAX_CODE_CHARS:
        return _refuse(f"`code` exceeds {_MAX_CODE_CHARS} chars", "code_too_large")
    base = paper_dir or os.environ.get(PAPER_DIR_ENV)
    if not base:
        return _refuse(
            f"no paper directory ({PAPER_DIR_ENV} unset) -- scripts must be "
            "persisted somewhere auditable before they run", "no_paper_dir")
    sandbox = _probe_sandbox()
    if sandbox == "none":
        return _refuse(
            "no enforceable network isolation on this machine (neither "
            "bwrap nor unshare user+net namespaces work) -- code execution "
            "is DISABLED rather than run unsandboxed", "code_disabled")

    # Per-run subdirectory when the pipeline named the run; the flat directory
    # otherwise. `write_parallel_outputs` flattens the slug away again when it
    # archives, so an archived run looks the same either way.
    # `_slug` defaults an empty label to "script", so the emptiness test has
    # to come FIRST -- routed through it, an unset variable would have created
    # an `analysis_code/script/` subdirectory on every single-run analysis.
    _raw_slug = (os.environ.get(RUN_SLUG_ENV) or "").strip()
    run_slug = _slug(_raw_slug) if _raw_slug else None
    scripts_dir = Path(base) / SCRIPTS_DIRNAME
    if run_slug:
        scripts_dir = scripts_dir / run_slug
    try:
        scripts_dir.mkdir(parents=True, exist_ok=True)
        seq = 1 + sum(1 for p in scripts_dir.glob("[0-9][0-9][0-9]_*.py"))
        name = f"{seq:03d}_{_slug(label)}"
        script = scripts_dir / f"{name}.py"
        script.write_text(code, encoding="utf-8")
        workdir = scripts_dir / f"{name}.d"
        workdir.mkdir(exist_ok=True)
    except OSError as exc:
        return _refuse(f"could not persist the script: {exc}", "persist_failed")

    timeout = min(max(int(timeout_seconds or _DEFAULT_TIMEOUT_S), 1),
                  _MAX_TIMEOUT_S)
    argv = _sandbox_argv(sandbox, scripts_dir, workdir, script)
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(workdir),
           "PYTHONDONTWRITEBYTECODE": "1"}
    started = time.monotonic()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout, env=env,
                              cwd=str(workdir) if sandbox != "bwrap" else None)
        timed_out = False
        rc: int | None = proc.returncode
        out, err = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out, rc = True, None
        out = (exc.stdout or b"").decode("utf-8", "replace") \
            if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = (exc.stderr or b"").decode("utf-8", "replace") \
            if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    except OSError as exc:
        return _refuse(f"sandbox launch failed: {exc}", "launch_failed")

    stdout, out_trunc = _clip(out)
    stderr, err_trunc = _clip(err)
    return {
        "success": (rc == 0),
        "returncode": rc,
        "timed_out": timed_out,
        "timeout_seconds": timeout,
        "duration_s": round(time.monotonic() - started, 3),
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": out_trunc,
        "stderr_truncated": err_trunc,
        # RELATIVE TO THE ARCHIVE, not to the paper directory. The two agree
        # in the unscoped case (`analysis_code/007_x.py`, byte-identical to
        # what this always returned) and the archive is what a reader of the
        # finished review actually has, since the run slug is flattened away
        # by `write_parallel_outputs`. Reporting the live path would hand a
        # reproduction string naming a directory that no longer exists.
        "script_path": str(Path(SCRIPTS_DIRNAME) / script.name),
        "label": _slug(label),
        "seq": seq,
        "sandbox": sandbox,   # "bwrap" (full) | "unshare" (netns only)
    }
