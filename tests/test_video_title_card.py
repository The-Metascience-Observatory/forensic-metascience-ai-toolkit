"""Fixture compatibility for the extracted standalone test suite.

`test_video_title_card.py` moved to metascience-observatory-image-analysis/tests/ on
2026-10-01; host tests still import its helpers from here. Collects no tests.
"""
from tests.source_paths import IMAGE_ROOT
import importlib.util as _util
import sys as _sys
from pathlib import Path as _Path
_dir = IMAGE_ROOT / "tests"
if str(_dir) not in _sys.path:  # its own sibling imports, in a host-only run
    _sys.path.append(str(_dir))
_spec = _util.spec_from_file_location("_image_fixtures_test_video_title_card", _dir / "test_video_title_card.py")
_mod = _util.module_from_spec(_spec)
_sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)
_paper = _mod._paper
_result = _mod._result
_stub_animator = _mod._stub_animator
_Vid = _mod._Vid
