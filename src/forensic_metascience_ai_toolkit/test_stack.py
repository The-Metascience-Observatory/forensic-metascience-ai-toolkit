"""Run independent local checks concurrently, retaining each lane's output."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def node_binary() -> str:
    """Use a supported Node on PATH, or an installed nvm version; never install."""
    explicit = os.environ.get("METASCIENCE_TEST_NODE")
    candidates = [explicit] if explicit else [shutil.which("node")]
    if not explicit:
        candidates += [
            str(p)
            for p in sorted((Path.home() / ".nvm/versions/node").glob("*/bin/node"), reverse=True)
        ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            result = subprocess.run(
                [candidate, "--version"], capture_output=True, text=True, timeout=5
            )
            version = tuple(int(p) for p in result.stdout.strip().lstrip("v").split("."))
            if result.returncode == 0 and version >= (22, 6, 0):
                return candidate
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError(
        "Local web tests require Node >=22.6; set METASCIENCE_TEST_NODE to its executable."
    )


def stack_jobs(root: Path, pytest_args: list[str], node: str) -> list[tuple[str, list[str], Path]]:
    web = root / "webapp"
    jobs = [
        ("python", [sys.executable, "-m", "pytest", *pytest_args], root),
        (
            "typescript",
            [node, "node_modules/typescript/bin/tsc", "--noEmit", "--incremental", "false"],
            web,
        ),
        (
            "lint-inert",
            [sys.executable, "-m", "forensic_metascience_ai_toolkit.cli", "lint-inert", "--certain-only"],
            root,
        ),
    ]
    # These existing scripts require a running server/database and named corpora.
    live_scripts = {
        "browser.mjs",
        "bulkImageReviewBrowser.mjs",
        "imageScreeningStatus.mjs",
        "imageQueueFilters.mjs",
        "infiniteQueueBrowser.mjs",
        "run-history.mjs",
        "workbench.mjs",
        "workbench-browser.mjs",
        "performance.mjs",
    }
    for script in sorted((web / "test").glob("*.mjs")):
        if script.name not in live_scripts:
            jobs.append(
                (
                    f"web-{script.stem}",
                    [node, "--experimental-strip-types", str(script.relative_to(web))],
                    web,
                )
            )
    return jobs


def run_jobs(jobs, log_dir: Path, env=None) -> list[dict]:
    """Start every independent lane; wait for all, even if one fails."""
    log_dir.mkdir(parents=True, exist_ok=True)
    active = []
    results = []
    try:
        for name, command, cwd in jobs:
            output = log_dir / f"{name}.log"
            start = time.monotonic()
            with output.open("w") as log:
                try:
                    process = subprocess.Popen(
                        command,
                        cwd=cwd,
                        env=env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=os.name != "nt",
                    )
                except OSError as exc:
                    log.write(str(exc))
                    results.append(
                        dict(
                            name=name,
                            seconds=time.monotonic() - start,
                            returncode=127,
                            log=str(output),
                        )
                    )
                    continue
            active.append((name, process, start, output))
        while active:
            for entry in active[:]:
                name, process, start, output = entry
                code = process.poll()
                if code is None:
                    continue
                result = dict(
                    name=name,
                    seconds=round(time.monotonic() - start, 3),
                    returncode=code,
                    log=str(output),
                )
                results.append(result)
                print(
                    f"{name}: {'PASS' if code == 0 else 'FAIL'} in {result['seconds']:.2f}s ({output})",
                    flush=True,
                )
                active.remove(entry)
            if active:
                time.sleep(0.05)
    finally:
        # Ctrl-C must not leave the Python workers or a browser running.
        for _, process, _, _ in active:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True
                    )
                else:
                    os.killpg(process.pid, signal.SIGTERM)
        for _, process, _, _ in active:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
    return results


def main(pytest_args: list[str]) -> int:
    root = Path(__file__).resolve().parents[2]
    try:
        node = node_binary()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    env = dict(os.environ)
    env["PATH"] = str(Path(node).parent) + os.pathsep + env.get("PATH", "")
    log_dir = Path(tempfile.mkdtemp(prefix="metascience-test-stack-"))
    print(f"Parallel local stack; logs: {log_dir}", flush=True)
    print("Live database/server browser checks and paid evals remain explicit opt-ins.", flush=True)
    start = time.monotonic()
    results = run_jobs(stack_jobs(root, pytest_args, node), log_dir, env)
    summary = dict(seconds=round(time.monotonic() - start, 3), checks=results)
    (log_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Entire local stack: {summary['seconds']:.2f}s", flush=True)
    return int(any(result["returncode"] != 0 for result in results))
