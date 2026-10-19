"""Fixture compatibility for the extracted standalone test suite."""
from tests.source_paths import IMAGE_ROOT
import importlib.util as _util
import sys as _sys
from pathlib import Path as _Path
_p = IMAGE_ROOT / "tests/test_image_analysis.py"
_spec = _util.spec_from_file_location("_image_fixtures_test_image_analysis", _p)
_mod = _util.module_from_spec(_spec)
_sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)
_texture = _mod._texture
_png = _mod._png
_jpeg_roundtrip_png = _mod._jpeg_roundtrip_png
_half = _mod._half
_glyph_png = _mod._glyph_png
_make_pdf = _mod._make_pdf
_two_figs_same_stream = _mod._two_figs_same_stream
_run = _mod._run
_transform_pdf = _mod._transform_pdf
_panel = _mod._panel
_placement = _mod._placement
_repaired_pdf = _mod._repaired_pdf
_montage_gray = _mod._montage_gray
_montage_harvest = _mod._montage_harvest
