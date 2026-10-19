"""Parallel test entry point, shared with bare pytest via tests/conftest.py.

Workers use one native numerical thread by default. ``--tune`` benchmarks the
full configured suite and saves the fastest measured worker count locally;
``--stack`` runs Python, TypeScript, web tests, isolated browser checks and
lint concurrently. Combine them to tune the complete local stack.

Explicit pytest worker/distribution choices and native thread settings win.
pytest-xdist is a base dependency; if an older install lacks it, execution
stays serial and says so. The runner never installs packages itself.
"""

from __future__ import annotations

import importlib.util
import sys

_XDIST_FLAGS = ("-n", "--numprocesses", "--dist", "-p")


def _xdist_available() -> bool:
    return importlib.util.find_spec("xdist") is not None


_XDIST_MISSING = (
    "pytest-xdist is missing; it is a base dependency, so reinstall the "
    "toolkit (`pip install -e .`)"
)


def _default_worker_count() -> int:
    from .test_performance import default_workers

    return default_workers()


def _user_already_chose_workers(args: list[str]) -> bool:
    return any(
        a in _XDIST_FLAGS or a.startswith(("-n", "--numprocesses=", "--dist=")) for a in args
    )


def apply_default_parallelism(config: object) -> bool:
    """Turn xdist on with this suite's default workers, if the user did not choose.

    Called from ``tests/conftest.py`` around ``pytest_cmdline_main`` -- that
    is the hook where xdist decides whether to spawn workers, so this must
    run *before* xdist's own implementation (a ``pytest_configure`` is too
    late on pytest 8/9). Returns True if it applied the default.

    Preserves explicit worker counts and distribution modes. Without an explicit
    distribution, use file grouping even when the caller supplies ``-n``.
    """
    from .test_performance import configure_native_threads

    configure_native_threads()
    if hasattr(config, "workerinput"):
        return False
    pm = getattr(config, "pluginmanager", None)
    if pm is None or not pm.hasplugin("xdist"):
        return False
    option = getattr(config, "option", None)
    if option is None:
        return False
    if getattr(option, "usepdb", False):
        return False
    changed = False
    if getattr(option, "numprocesses", None) is None:
        option.numprocesses = _default_worker_count()
        changed = True
    if getattr(option, "numprocesses", 0) != 0 and getattr(option, "dist", "no") in (None, "no"):
        option.dist = "loadfile"
        changed = True
    return changed


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    from .test_performance import configure_native_threads

    configure_native_threads()
    stack = "--stack" in args
    if stack:
        args.remove("--stack")
    if "--tune" in args:
        args.remove("--tune")
        if not _xdist_available():
            print(f"Worker tuning requires pytest-xdist: {_XDIST_MISSING}.", file=sys.stderr)
            return 2
        from .test_performance import tune

        return tune(args, stack=stack)
    if stack:
        from .test_stack import main as run_stack

        return run_stack(args)

    parallel_ok = _xdist_available()

    pytest_args: list[str] = []
    if parallel_ok and not _user_already_chose_workers(args):
        pytest_args += ["-n", str(_default_worker_count()), "--dist", "loadfile"]
    elif not parallel_ok:
        print(f"metascience-test: running serially ({_XDIST_MISSING}).", file=sys.stderr)

    pytest_args += args

    # Delegate to pytest's own console entry point in-process rather than
    # shelling out to a second `python -m pytest` -- avoids a platform-
    # dependent subprocess/quoting layer (a real concern for the eventual
    # Windows use of this entry point) and preserves the exit code directly.
    import pytest  # imported lazily so `--help`/install failures don't need it

    return pytest.main(pytest_args)


if __name__ == "__main__":
    raise SystemExit(main())
