"""Fixture compatibility for the extracted standalone test suite."""
from tests.source_paths import IMAGE_ROOT
import importlib.util as _util
import sys as _sys
from pathlib import Path as _Path
_p = IMAGE_ROOT / "tests/test_copy_move.py"
_spec = _util.spec_from_file_location("_image_fixtures_test_copy_move", _p)
_mod = _util.module_from_spec(_spec)
_sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)
_blot = _mod._blot
_membrane = _mod._membrane
_montage = _mod._montage
