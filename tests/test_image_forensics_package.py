"""The image track lives in the standalone package; the toolkit keeps no
aliases of its old paths.

Three guarantees, each with the failure that motivated it:

1. `extraction.figures`, the one host module that becomes the package's when
   it is installed, is the SAME object as its canonical module. Tests and
   callers `monkeypatch` or `mock.patch` attributes on module objects; a
   re-export shim would take the patch and the real code would never see it.
2. Every module here imports cleanly when it is the FIRST thing a fresh
   interpreter imports. The child process (`python -m ...image_track`)
   imports the detector before anything else, and on the first real run after
   the move that path raised "cannot import name 'analyze_paper_images' from
   partially initialized module": `image_analysis` imports `tools.quarantine`,
   which ran `tools/__init__`, which eagerly re-imported the half-built
   detector. The whole test suite passed, because every test loads `tools`
   first. Only a fresh interpreter reproduces it, so that is what this test
   uses.
3. The old paths stay gone (`REMOVED`): the forwarding aliases were deleted
   on 2026-10-01 and 2026-10-18 (v1.85.0), and must not quietly come back.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.source_paths import IMAGE_SRC

SRC = Path(__file__).resolve().parent.parent / "src"
#: All three source roots of THIS checkout. `src` alone let a child import
#: the image package from whatever editable install the interpreter has --
#: another checkout's, in a worktree -- so the child ran code this test
#: never wrote.
_ROOT = SRC.parent
CHILD_PATH = os.pathsep.join([*(str(_ROOT / p) for p in ("src", "copy_paste_detector/src")),
                              *([str(IMAGE_SRC.parent)] if IMAGE_SRC else [])])

PAIRS = [
    ("metascience_agent.extraction.figures",
     "metascience_observatory_image_analysis.extraction.figures"),
]

_IMAGE = "metascience_observatory_image_analysis"
#: Modules a fresh interpreter must be able to import first.
FIRST_IMPORTS = ["metascience_agent.extraction.figures",
                 f"{_IMAGE}.extraction.figures",
                 f"{_IMAGE}.image_forensics.image_track",
                 f"{_IMAGE}.image_forensics.pipeline",
                 f"{_IMAGE}.image_forensics.review_media",
                 f"{_IMAGE}.review_workbench.local_images"]

#: Old paths, removed (a sample from 2026-10-01; all of 2026-10-18's).
REMOVED = [
    "metascience_agent.tools.image_analysis",
    "metascience_agent.tools.chrome_mask",
    "metascience_agent.tools.copy_move",
    "metascience_agent.extraction.panels",
    "metascience_agent.image_corpus",
    "metascience_agent.image_review",
    "metascience_agent.review_media",
    "metascience_agent.image_track",
    "metascience_agent.image_forensics",
    "metascience_agent.image_forensics.image_track",
    "metascience_agent.image_forensics.pipeline",
    "metascience_agent.workbench.content_support",
    "metascience_agent.workbench.image_equivalence",
    "metascience_agent.workbench.image_geometry",
    "metascience_agent.workbench.local_image_import",
    "metascience_agent.workbench.local_image_service",
    "metascience_agent.workbench.local_images",
    "metascience_agent.workbench.text_regions",
    "metascience_agent.workbench.thumbnails",
    "metascience_agent.workbench.videos",
    "metascience_agent.highlight_render",
    "metascience_agent.tools.raw_duplication",
    "copy_paste_detector._compat",
]


@pytest.mark.usefixtures("image_package")
@pytest.mark.parametrize("old,new", PAIRS, ids=[o for o, _ in PAIRS])
def test_the_alias_is_the_same_module_object(old, new):
    a = importlib.import_module(old)
    b = importlib.import_module(new)
    assert a is b
    parent, _, leaf = old.rpartition(".")
    assert getattr(importlib.import_module(parent), leaf) is b


def _fresh(code: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": CHILD_PATH}
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, env=env, timeout=120)


@pytest.mark.usefixtures("image_package")
@pytest.mark.parametrize("module", FIRST_IMPORTS)
def test_each_module_imports_first_in_a_fresh_interpreter(module):
    proc = _fresh(f"import {module}")
    assert proc.returncode == 0, proc.stderr[-800:]


@pytest.mark.usefixtures("image_package")
def test_the_package_level_tool_export_still_resolves():
    proc = _fresh(
        "from metascience_agent.tools import analyze_paper_images as a\n"
        "from metascience_observatory_image_analysis.image_forensics.image_analysis import "
        "analyze_paper_images as b\n"
        "assert a is b\n"
        "import metascience_agent.tools as T; assert 'analyze_paper_images' in T.__all__")
    assert proc.returncode == 0, proc.stderr[-800:]


@pytest.mark.usefixtures("image_package")
def test_the_child_runs(tmp_path):
    """The per-paper child, run as `python -m`. A no-PDF directory is the
    cheapest full round trip."""
    env = {**os.environ, "PYTHONPATH": CHILD_PATH}
    proc = subprocess.run([sys.executable, "-m", f"{_IMAGE}.image_forensics.image_track",
                           str(tmp_path), "--json"],
                          capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr[-800:]
    out = json.loads(proc.stdout)
    assert out["status"]["ran"] is False
    assert out["status"]["refusal_subtype"] == "no_pdf"


@pytest.mark.parametrize("module", REMOVED)
def test_removed_alias_paths_stay_removed(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)
