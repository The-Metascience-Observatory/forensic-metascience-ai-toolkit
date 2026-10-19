"""Default the suite to parallel when pytest-xdist is loaded.

``addopts`` cannot carry ``-n``/``--dist``: pytest parses those before
plugins load, and a missing xdist turns every ``pytest`` into
"unrecognized arguments: -n". This hook runs around
``pytest_cmdline_main``, which is where xdist decides whether to spawn
workers, so the same flags are applied only when they will be understood.

``metascience-test`` applies the same defaults itself. This is the path for
bare ``pytest`` / ``python -m pytest``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

#: `METASCIENCE_BLOCK_IMAGE_PLUGIN=1` runs the suite as a toolkit WITHOUT the
#: separately distributed image analysis package: the package cannot be
#: imported at all, and test files that exercise it are not collected (they
#: belong to the image package's suite). What remains must pass.
_BLOCKED = os.environ.get("METASCIENCE_BLOCK_IMAGE_PLUGIN", "").strip() not in ("", "0")
_IMAGE_PACKAGE = "metascience_observatory_image_analysis"


class _BlockImagePackage:
    def find_spec(self, name, path=None, target=None):
        if name == _IMAGE_PACKAGE or name.startswith(_IMAGE_PACKAGE + "."):
            raise ModuleNotFoundError(f"image package blocked: {name}", name=name)
        return None


if _BLOCKED:
    sys.meta_path.insert(0, _BlockImagePackage())


def needs_image_package(path: Path) -> bool:
    """A test file whose MODULE-LEVEL imports reach the image package cannot
    even be collected without it; it belongs to the image package's suite.
    Every other file is collected, so a test that fails for want of the
    package is a failure to fix or mark, never silently dropped."""
    import ast
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, SyntaxError):
        return False
    if "from tests.source_paths import IMAGE_ROOT" in text:
        return True     # e.g. a zero-test stub that loads the image suite's helpers
    for node in tree.body:
        names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level
                 else [])
        if isinstance(node, ast.ImportFrom) and node.module:
            names += [f"{node.module}.{a.name}" for a in node.names]
        for name in names:
            if name == _IMAGE_PACKAGE or name.startswith(_IMAGE_PACKAGE + "."):
                return True
    return False


def pytest_ignore_collect(collection_path, config):
    if _BLOCKED and collection_path.suffix == ".py" and collection_path.name.startswith("test_"):
        return True if needs_image_package(Path(collection_path)) else None
    return None


@pytest.fixture
def image_package():
    """Request this in a test that exercises the image analysis package: it is
    skipped, by name, in a run where the package is absent or blocked."""
    from forensic_metascience_ai_toolkit.image_plugin import available
    if not available():
        pytest.skip("needs the image analysis package (absent or blocked)")


from forensic_metascience_ai_toolkit.test_runner import apply_default_parallelism  # noqa: E402


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_cmdline_main(config: pytest.Config):
    apply_default_parallelism(config)
    yield


@pytest.fixture(autouse=True)
def _no_operator_model_store(monkeypatch, tmp_path_factory):
    """No test may reach the operator's installed panel-detector model.

    `image_forensics.model_store` discovers a model in
    `$XDG_DATA_HOME/metascience-observatory/models/panel_detector`, so on a
    machine where one is installed, a test that clears
    METASCIENCE_PANEL_DETECTOR_ONNX to mean "no model" would still find one --
    which is how a learned-mode refusal test started passing or failing by
    machine the moment discovery shipped. Isolate the SOURCE, the same way the
    findings-database guard below does: point XDG_DATA_HOME at an empty
    directory. A test that wants a model sets the variable or passes a path.
    """
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path_factory.mktemp("xdg")))


@pytest.fixture(autouse=True)
def _no_operator_workbench_cache(monkeypatch, tmp_path_factory):
    """No test may write the operator's workbench caches.

    Every sealed archive notifies `workbench.notifications.published`, which
    writes to `cache_path()` and `image_path()` whenever those files exist.
    The explicit variables win over XDG_DATA_HOME, so the XDG guard above
    only protected the real caches by accident; before it, pytest tmp
    folders reached ~4,200 `roots` rows there (measured 2026-09-26). Point
    both at files that do not exist, so a notification is a no-op. A test
    that wants a cache creates its own `Catalog(tmp_path / ...)`.
    """
    base = tmp_path_factory.mktemp("workbench")
    monkeypatch.setenv("METASCIENCE_WORKBENCH_DB", str(base / "workbench.sqlite3"))
    monkeypatch.setenv("METASCIENCE_IMAGE_REVIEW_DB", str(base / "image-review.sqlite3"))


@pytest.fixture(autouse=True)
def _no_live_findings_db(monkeypatch, tmp_path_factory):
    """The suite must never touch the real findings database.

    `db_push.resolve_db_url` deliberately falls back to the repo's
    gitignored `.env` (wired live 2026-08-21) so the CLI and the webapp's
    spawned Python work without an exported variable -- which means on a
    wired machine every unit test that reaches `auto_push` would otherwise
    resolve the REAL url and push test fixtures into the live findings
    store. Tests that want a URL set one explicitly (monkeypatch.setenv or
    a FakeConn); everything else sees no database at all.
    """
    monkeypatch.delenv("METASCIENCE_DB_URL", raising=False)
    # Isolate the SOURCE, not the readers: every `.env`-backed reader resolves
    # through METASCIENCE_ENV_FILE, so pointing it at a file that does not
    # exist blinds all of them at once -- and a test that wants a .env still
    # overrides this with its own setenv.
    monkeypatch.setenv("METASCIENCE_ENV_FILE",
                       str(tmp_path_factory.mktemp("noenv") / "absent.env"))
    try:
        from forensic_metascience_ai_toolkit import db_push
    except ImportError:
        yield
        return
    monkeypatch.setattr(db_push, "_dotenv_url",
                    lambda env_file=None: None)
    yield


@pytest.fixture(autouse=True)
def _block_unmocked_model_execution(monkeypatch):
    """Offline tests must fail if a refactor disconnects a paid-call mock."""
    import asyncio
    import os
    import shutil
    from pathlib import Path
    if os.environ.get("RUN_EVAL") == "1":
        return
    original = asyncio.create_subprocess_exec
    async def guarded(program, *args, **kwargs):
        name = Path(str(program)).name
        if name in {"codex", "claude", "grok"}:
            resolved = Path(shutil.which(str(program)) or str(program)).resolve()
            if "/tmp/" not in str(resolved):
                raise AssertionError(f"Unmocked model execution in offline test: {name}")
        return await original(program, *args, **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", guarded)


@pytest.fixture(autouse=True)
def _no_operator_text_ocr(monkeypatch):
    """Detector unit tests must not depend on installed OCR or spawn Tesseract.

    OCR localization tests explicitly supply a deterministic adapter. Real OCR
    acceptance is a separate archived-fixture replay, with engine provenance.
    """
    from forensic_metascience_ai_toolkit.image_plugin import available, load
    if not available():
        return None
    text_support = load("image_forensics.text_support")
    original = text_support.capability
    monkeypatch.setattr(text_support, 'capability', lambda: (None, 'offline test'))
    return original


@pytest.fixture(scope="session", autouse=True)
def _session_portable_environment(tmp_path_factory):
    """The function-level fixtures below isolate each TEST; this isolates
    everything that runs before them. Module- and session-scoped fixtures
    (19 files) are built before any function-level autouse fixture, so they
    used to run with the workstation's environment: GPU devices, `enforce`
    text exclusion and the operator's compute cache. MEASURED 2026-10-01:
    `test_copy_move_wiring.py`'s module fixture attached to the PRODUCTION
    GPU broker serving a live author run and queued behind it for minutes."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("METASCIENCE_DEVICE", "cpu")
        for workload in ("CRAFT", "PANEL", "DOCUMENT", "VIDEO"):
            mp.delenv(f"METASCIENCE_{workload}_DEVICE", raising=False)
        mp.setenv("METASCIENCE_COMPUTE_CACHE", str(tmp_path_factory.mktemp("session_compute")))
        mp.setenv("METASCIENCE_TEXT_EXCLUSION", "off")
        mp.setenv("METASCIENCE_FREEZE", "0")
        mp.setenv("METASCIENCE_FROZEN_CODE_DIR", str(tmp_path_factory.mktemp("session_frozen")))
        # The search checkpoints and pair-feature stores live under the XDG
        # CACHE dir; a test once wrote rows into the operator's 27 GB
        # within-clones.sqlite (2026-10-01). Models live under XDG DATA,
        # which stays the operator's so tests that use an installed model can.
        mp.setenv("XDG_CACHE_HOME", str(tmp_path_factory.mktemp("session_xdg_cache")))
        yield


@pytest.fixture(autouse=True)
def _no_operator_craft(monkeypatch):
    """CRAFT acceptance is explicit; unit tests never load operator weights."""
    monkeypatch.setenv("METASCIENCE_TEXT_EXCLUSION", "off")


@pytest.fixture(autouse=True)
def _portable_compute_reference(monkeypatch, tmp_path):
    """Unit tests cannot inherit a workstation's GPU qualification or overrides."""
    monkeypatch.setenv("METASCIENCE_DEVICE", "cpu")
    monkeypatch.setenv("METASCIENCE_COMPUTE_CACHE", str(tmp_path / "compute"))
    for workload in ("CRAFT", "PANEL", "DOCUMENT", "VIDEO"):
        monkeypatch.delenv(f"METASCIENCE_{workload}_DEVICE", raising=False)


@pytest.fixture(autouse=True)
def _no_frozen_reexec(monkeypatch, tmp_path_factory):
    """A CLI test must not snapshot the package and `execve` the test process.
    The freezing verbs read METASCIENCE_FREEZE=0 as a loud, recorded opt-out;
    `test_frozen_code.py` removes it to exercise the freeze itself. Snapshots
    a test does make go to a temporary root, never the operator's cache."""
    monkeypatch.setenv("METASCIENCE_FREEZE", "0")
    monkeypatch.setenv("METASCIENCE_FROZEN_CODE_DIR", str(tmp_path_factory.mktemp("frozen_code")))
    for name in ("METASCIENCE_FROZEN_CODE", "METASCIENCE_FROZEN_CODE_EXEC"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _no_live_reading_store(monkeypatch, tmp_path_factory):
    """The suite must never read or write the real store of paid readings.

    `reading_store` defaults to `~/.cache/metascience/readings`, which on a
    working machine holds table readings that cost real money. A test that
    drives the reconstruction path with a stubbed model would otherwise deposit
    a fake reading into it under a real key -- and, worse, a later test could
    be served one, which would make the suite's behaviour depend on what this
    machine happens to have bought. Each test gets its own empty store.
    """
    monkeypatch.setenv("METASCIENCE_READING_CACHE",
                       str(tmp_path_factory.mktemp("reading-store")))
    yield
