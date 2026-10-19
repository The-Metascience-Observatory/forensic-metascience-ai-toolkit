"""Fixture compatibility for the extracted standalone test suite."""
from tests.source_paths import IMAGE_ROOT
import importlib.util as _util
import sys as _sys
from pathlib import Path as _Path
_p = IMAGE_ROOT / "tests/test_panels.py"
_spec = _util.spec_from_file_location("_image_fixtures_test_panels", _p)
_mod = _util.module_from_spec(_spec)
_sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)
_texture = _mod._texture
_png = _mod._png
_make_pdf = _mod._make_pdf
_placements_by_bbox = _mod._placements_by_bbox
_hide_fitz = _mod._hide_fitz
