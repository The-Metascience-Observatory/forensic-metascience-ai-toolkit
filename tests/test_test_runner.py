"""Tests for the cross-platform self-installing parallel test runner.

The contract this module exists to guarantee: `metascience-test` never
hard-fails just because pytest-xdist is missing (it self-installs, or falls
back to serial), uses machine-local measured worker counts on
Mac/Linux/Windows alike, and never double-specifies `-n`/`--dist` when the
caller already chose their own.
"""

import subprocess
import sys
import types

import pytest

from metascience_agent import test_runner


def _install_fake_pytest(monkeypatch, captured):
    """Stub `import pytest` inside test_runner.main() to capture its argv."""

    def fake_pytest_main(args):
        captured["args"] = args
        return 0

    fake_module = types.SimpleNamespace(main=fake_pytest_main)
    monkeypatch.setitem(sys.modules, "pytest", fake_module)


class TestDefaultWorkerCount:
    def test_delegates_to_machine_calibration(self, monkeypatch):
        from metascience_agent import test_performance
        monkeypatch.setattr(test_performance, "default_workers", lambda: 12)
        assert test_runner._default_worker_count() == 12


class TestUserAlreadyChoseWorkers:
    @pytest.mark.parametrize(
        "args",
        [
            ["-n", "4"],
            ["-n4"],
            ["--numprocesses", "auto"],
            ["--dist", "loadscope"],
            ["-p", "no:xdist"],
        ],
    )
    def test_recognised_flags_suppress_the_default(self, args):
        assert test_runner._user_already_chose_workers(args) is True

    def test_unrelated_args_do_not(self):
        assert test_runner._user_already_chose_workers(["-k", "grim", "-q"]) is False

    def test_empty_args_do_not(self):
        assert test_runner._user_already_chose_workers([]) is False


class TestEnsureXdistInstalled:
    def test_already_available_skips_install(self, monkeypatch):
        monkeypatch.setattr(test_runner, "_xdist_available", lambda: True)
        called = []
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: called.append((a, k)))
        assert test_runner._ensure_xdist_installed() is True
        assert called == []

    def test_installs_when_missing_then_reports_true_if_it_worked(self, monkeypatch):
        calls = {"n": 0}

        def fake_available():
            calls["n"] += 1
            return calls["n"] > 1  # missing on first check, present after "install"

        monkeypatch.setattr(test_runner, "_xdist_available", fake_available)
        monkeypatch.setattr(
            test_runner.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0)
        )
        assert test_runner._ensure_xdist_installed() is True

    def test_offline_install_failure_degrades_to_false_not_raise(self, monkeypatch):
        monkeypatch.setattr(test_runner, "_xdist_available", lambda: False)

        def raise_network_error(*a, **k):
            raise subprocess.CalledProcessError(1, a)

        monkeypatch.setattr(test_runner.subprocess, "run", raise_network_error)
        # Must not raise -- a failed install is a "run serially" signal, never fatal.
        assert test_runner._ensure_xdist_installed() is False

    def test_install_timeout_also_degrades_gracefully(self, monkeypatch):
        monkeypatch.setattr(test_runner, "_xdist_available", lambda: False)

        def raise_timeout(*a, **k):
            raise subprocess.TimeoutExpired(cmd="pip", timeout=120)

        monkeypatch.setattr(test_runner.subprocess, "run", raise_timeout)
        assert test_runner._ensure_xdist_installed() is False


class TestMainBuildsCorrectPytestArgs:
    def test_injects_n_and_dist_when_xdist_available_and_user_did_not_choose(
        self, monkeypatch
    ):
        monkeypatch.setattr(test_runner, "_ensure_xdist_installed", lambda: True)
        monkeypatch.setattr(test_runner, "_default_worker_count", lambda: 7)
        captured = {}
        _install_fake_pytest(monkeypatch, captured)

        rc = test_runner.main(["-k", "grim"])
        assert rc == 0
        assert captured["args"][:4] == ["-n", "7", "--dist", "loadfile"]
        assert captured["args"][4:] == ["-k", "grim"]

    def test_does_not_override_an_explicit_n(self, monkeypatch):
        monkeypatch.setattr(test_runner, "_ensure_xdist_installed", lambda: True)
        captured = {}
        _install_fake_pytest(monkeypatch, captured)

        test_runner.main(["-n", "3"])
        assert captured["args"] == ["-n", "3"]

    def test_falls_back_to_plain_args_when_xdist_unavailable(self, monkeypatch):
        monkeypatch.setattr(test_runner, "_ensure_xdist_installed", lambda: False)
        captured = {}
        _install_fake_pytest(monkeypatch, captured)

        test_runner.main(["-k", "grim"])
        assert captured["args"] == ["-k", "grim"]
        assert "-n" not in captured["args"]


def _fake_config(*, xdist=True, numprocesses=None, dist="no",
                 usepdb=False, worker=False):
    """Minimal stand-in for pytest's Config, for apply_default_parallelism."""

    class _PM:
        def hasplugin(self, name):
            return xdist and name == "xdist"

    cfg = types.SimpleNamespace(
        pluginmanager=_PM(),
        option=types.SimpleNamespace(
            numprocesses=numprocesses, dist=dist, usepdb=usepdb,
        ),
    )
    if worker:
        cfg.workerinput = {"workerid": "gw0"}
    return cfg


class TestApplyDefaultParallelism:
    """Bare ``pytest`` has to pick up the same default as ``metascience-test``."""

    def test_applies_n_and_loadfile_when_xdist_is_loaded(self, monkeypatch):
        monkeypatch.setattr(test_runner, "_default_worker_count", lambda: 5)
        cfg = _fake_config()
        assert test_runner.apply_default_parallelism(cfg) is True
        assert cfg.option.numprocesses == 5
        assert cfg.option.dist == "loadfile"

    def test_noop_when_xdist_is_not_loaded(self):
        cfg = _fake_config(xdist=False)
        assert test_runner.apply_default_parallelism(cfg) is False
        assert cfg.option.numprocesses is None
        assert cfg.option.dist == "no"

    def test_does_not_override_an_explicit_n(self):
        cfg = _fake_config(numprocesses=2)
        assert test_runner.apply_default_parallelism(cfg) is True
        assert cfg.option.numprocesses == 2
        assert cfg.option.dist == "loadfile"

    def test_keeps_an_explicit_dist_mode(self, monkeypatch):
        monkeypatch.setattr(test_runner, "_default_worker_count", lambda: 5)
        cfg = _fake_config(dist="loadscope")
        assert test_runner.apply_default_parallelism(cfg) is True
        assert cfg.option.numprocesses == 5
        assert cfg.option.dist == "loadscope"

    def test_noop_on_an_xdist_worker(self):
        cfg = _fake_config(worker=True)
        assert test_runner.apply_default_parallelism(cfg) is False
        assert cfg.option.numprocesses is None

    def test_noop_with_pdb(self):
        cfg = _fake_config(usepdb=True)
        assert test_runner.apply_default_parallelism(cfg) is False
        assert cfg.option.numprocesses is None


def test_explicit_serial_is_preserved():
    cfg = _fake_config(numprocesses=0)
    assert test_runner.apply_default_parallelism(cfg) is False
    assert cfg.option.numprocesses == 0


def test_stack_dispatches_without_nesting_pytest(monkeypatch):
    from metascience_agent import test_stack
    calls = []
    monkeypatch.setattr(test_runner, "_ensure_xdist_installed", lambda: True)
    monkeypatch.setattr(test_stack, "main", lambda args: calls.append(args) or 3)
    assert test_runner.main(["--stack", "-n", "12", "-q"]) == 3
    assert calls == [["-n", "12", "-q"]]
