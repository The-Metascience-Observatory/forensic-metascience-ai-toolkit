"""Calibration uses real elapsed time, preserves overrides and rejects failures."""

import json
import sys

import pytest

from forensic_metascience_ai_toolkit import test_performance as perf
from forensic_metascience_ai_toolkit import test_stack as stack


@pytest.fixture
def calibration(tmp_path, monkeypatch):
    monkeypatch.setattr(perf, "profile_path", lambda: tmp_path / "workers.json")
    monkeypatch.setattr(perf, "available_cpus", lambda: 20)
    monkeypatch.setattr(perf, "machine_key", lambda: "this-machine")
    monkeypatch.delenv("METASCIENCE_TEST_WORKERS", raising=False)
    return tmp_path / "workers.json"


def test_profile_is_consumed_and_foreign_profile_ignored(calibration):
    assert perf.default_workers() == 20
    perf.save_profile(12, [{"workers": 12, "seconds": 50, "returncode": 0}], "local-stack")
    assert perf.default_workers() == 12
    profile = json.loads(calibration.read_text())
    profile["machine_key"] = "another-machine"
    calibration.write_text(json.dumps(profile))
    assert perf.default_workers() == 20


@pytest.mark.parametrize("contents", ["broken", "[]", "{}", '{"workers": null}'])
def test_invalid_cache_falls_back(calibration, contents):
    calibration.write_text(contents)
    assert perf.default_workers() == 20


def test_explicit_worker_override_wins(calibration, monkeypatch):
    perf.save_profile(12, [], "python")
    monkeypatch.setenv("METASCIENCE_TEST_WORKERS", "8")
    assert perf.default_workers() == 8
    monkeypatch.setenv("METASCIENCE_TEST_WORKERS", "nope")
    with pytest.raises(ValueError, match="positive"):
        perf.default_workers()


def test_selects_fastest_median_instead_of_fastest_outlier():
    rows = [
        dict(workers=n, seconds=s, returncode=0)
        for n, s in [(6, 70), (6, 72), (12, 51), (12, 53), (20, 48), (20, 80)]
    ]
    assert perf.choose_workers(rows) == 12
    with pytest.raises(ValueError, match="failed"):
        perf.choose_workers(rows + [dict(workers=8, seconds=1, returncode=1)])


def test_thread_limits_preserve_explicit_settings(monkeypatch):
    for name in perf.NATIVE_THREADS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MKL_NUM_THREADS", "3")
    perf.configure_native_threads()
    assert perf.os.environ["MKL_NUM_THREADS"] == "3"
    assert perf.os.environ["OPENBLAS_NUM_THREADS"] == "1"


def test_jobs_really_overlap_and_retain_failure_output(tmp_path):
    # Both children must start before either can finish; serial launch would fail.
    script = """
from pathlib import Path
import sys,time
Path(sys.argv[1]).touch()
end=time.monotonic()+5
while not Path(sys.argv[2]).exists() and time.monotonic()<end: time.sleep(.01)
assert Path(sys.argv[2]).exists(), 'sibling never started'
print('both lanes started', flush=True)
sys.exit(int(sys.argv[3]))
"""
    a, b = tmp_path / "a", tmp_path / "b"
    jobs = [
        ("a", [sys.executable, "-c", script, str(a), str(b), "0"], tmp_path),
        ("b", [sys.executable, "-c", script, str(b), str(a), "3"], tmp_path),
    ]
    results = stack.run_jobs(jobs, tmp_path / "logs")
    assert {r["name"]: r["returncode"] for r in results} == {"a": 0, "b": 3}
    assert all(
        "both lanes started" in (tmp_path / "logs" / f"{r['name']}.log").read_text()
        for r in results
    )


def test_stack_includes_both_python_roots_and_no_live_services(tmp_path):
    tests = tmp_path / "webapp/test"
    tests.mkdir(parents=True)
    for name in [
        "smoke",
        "reviewSyncBrowser",
        "newRegression",
        "workbench",
        "browser",
        "run-history",
        "workbench-browser",
        "performance",
        "bulkImageReviewBrowser",
        "imageScreeningStatus",
        "imageQueueFilters",
        "infiniteQueueBrowser",
    ]:
        (tests / f"{name}.mjs").touch()
    jobs = stack.stack_jobs(tmp_path, ["-q"], "node")
    python = next(command for name, command, _ in jobs if name == "python")
    assert python == [sys.executable, "-m", "pytest", "-q"]  # pyproject owns both roots
    assert {name for name, _, _ in jobs} == {
        "python",
        "typescript",
        "lint-inert",
        "web-smoke",
        "web-reviewSyncBrowser",
        "web-newRegression",
    }
    typescript = next(command for name, command, _ in jobs if name == "typescript")
    assert typescript[-2:] == ["--incremental", "false"]


def test_failed_tuning_leaves_existing_profile(calibration, monkeypatch):
    from types import SimpleNamespace

    perf.save_profile(6, [], "python")
    before = calibration.read_bytes()
    monkeypatch.setattr(perf.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    assert perf.tune(["--worker-counts", "6", "--tune-repeats", "1"]) == 1
    assert calibration.read_bytes() == before
