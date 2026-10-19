"""Machine-local worker calibration and native thread budgets for test processes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

NATIVE_THREADS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "OPENCV_FOR_THREADS_NUM",
)


def configure_native_threads() -> None:
    # Workers provide parallelism; each worker's BLAS pool must not use every CPU.
    # Explicit user settings win, including for subprocesses launched by tests.
    for name in NATIVE_THREADS:
        os.environ.setdefault(name, "1")


def available_cpus() -> int:
    process_count = getattr(os, "process_cpu_count", os.cpu_count)() or 1
    return max(1, process_count)


def profile_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "metascience/test-workers.json"


def machine_key() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        xdist = version("pytest-xdist")
    except PackageNotFoundError:
        xdist = None
    facts = (
        platform.node(),
        platform.machine(),
        sys.executable,
        sys.version,
        available_cpus(),
        xdist,
        [(name, os.environ.get(name, "1")) for name in NATIVE_THREADS],
    )
    return hashlib.sha256(json.dumps(facts).encode()).hexdigest()


def default_workers() -> int:
    explicit = os.environ.get("METASCIENCE_TEST_WORKERS")
    if explicit:
        try:
            workers = int(explicit)
            if workers > 0:
                return workers
        except ValueError:
            pass
        raise ValueError("METASCIENCE_TEST_WORKERS must be a positive integer")
    try:
        profile = json.loads(profile_path().read_text())
        workers = profile["workers"]
        if (
            profile["machine_key"] == machine_key()
            and type(workers) is int
            and 1 <= workers <= available_cpus()
        ):
            return workers
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # Full CPU availability is the untuned starting point, not a universal optimum.
    return available_cpus()


def save_profile(workers: int, measurements: list[dict], scope: str) -> None:
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(
        machine_key=machine_key(),
        workers=workers,
        measured_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        scope=scope,
        measurements=measurements,
    )
    fd, temporary = tempfile.mkstemp(prefix="test-workers-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(payload, out, indent=2)
            out.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def choose_workers(measurements: list[dict]) -> int:
    if not measurements or any(row["returncode"] for row in measurements):
        raise ValueError("A failed benchmark cannot select a worker count")
    workers = {row["workers"] for row in measurements}
    # Exact ties prefer fewer workers; otherwise optimize elapsed time.
    return min(
        workers,
        key=lambda n: (
            statistics.median(row["seconds"] for row in measurements if row["workers"] == n),
            n,
        ),
    )


def tune(args: list[str], stack: bool = False) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark the full suite sequentially at several worker counts."
    )
    parser.add_argument(
        "--worker-counts",
        default=",".join(
            map(
                str, sorted({min(available_cpus(), n) for n in (4, 6, 8, 12, 16, available_cpus())})
            )
        ),
    )
    parser.add_argument("--tune-repeats", type=int, default=2)
    options = parser.parse_args(args)
    try:
        counts = sorted(set(int(x) for x in options.worker_counts.split(",")))
        if (
            not counts
            or min(counts) < 1
            or max(counts) > available_cpus()
            or options.tune_repeats < 1
        ):
            raise ValueError()
    except ValueError:
        parser.error("Use positive worker counts within available CPUs and at least one repeat.")
    configure_native_threads()
    directory = Path(tempfile.mkdtemp(prefix="metascience-test-tune-"))
    root = Path(__file__).resolve().parents[2]
    measurements = []
    print(f"Benchmark logs: {directory}", flush=True)
    for repeat in range(options.tune_repeats):
        # Reverse alternating rounds to reduce systematic warmup/order bias.
        for workers in counts if repeat % 2 == 0 else counts[::-1]:
            command = [sys.executable, "-m", "metascience_agent.test_runner"]
            if stack:
                command += ["--stack"]
            command += ["-q", "-n", str(workers), "--dist", "loadfile", "--durations=20"]
            output = directory / f"workers-{workers}-round-{repeat + 1}.log"
            start = time.monotonic()
            with output.open("w") as log:
                result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
            row = dict(
                workers=workers,
                seconds=round(time.monotonic() - start, 3),
                returncode=result.returncode,
                log=str(output),
            )
            measurements.append(row)
            (directory / "measurements.json").write_text(json.dumps(measurements, indent=2) + "\n")
            print(
                f"{workers} workers, round {repeat + 1}: {row['seconds']:.2f}s, exit {result.returncode}",
                flush=True,
            )
            if result.returncode:
                print(
                    f"Benchmark failed; existing calibration unchanged. Inspect {output}",
                    file=sys.stderr,
                )
                return result.returncode
    workers = choose_workers(measurements)
    save_profile(workers, measurements, "local-stack" if stack else "python")
    print(f"Fastest measured median: {workers} workers; saved to {profile_path()}", flush=True)
    return 0
