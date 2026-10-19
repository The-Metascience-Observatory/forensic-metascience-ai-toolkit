"""The raw-data detector lives in copy_paste_detector/src, not under src/.

When that root is missing from sys.path the bare project folder at the repo
root is imported as an EMPTY namespace package, and the stock error is
"cannot import name ... (unknown location)", which names nothing a reader can
act on. `metascience_agent.tools`, the first importer, must instead say what to
do. The shadow is reproduced with an attribute-less module in a child
interpreter, so the parent's imported modules are untouched.
"""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "metascience_agent"

_SHADOWED = """
import sys, types
sys.modules["copy_paste_detector"] = types.ModuleType("copy_paste_detector")
try:
    import metascience_agent.tools
except ImportError as exc:
    print(exc)
else:
    print("IMPORTED")
"""


def test_a_shadowed_detector_root_names_the_fix():
    out = subprocess.run([sys.executable, "-c", _SHADOWED], capture_output=True,
                         text=True, timeout=120).stdout
    assert "pip install -e ." in out
    assert "copy_paste_detector/src" in out
    assert "PYTHONPATH" in out


def test_the_real_root_is_the_one_imported():
    import copy_paste_detector

    real = Path(copy_paste_detector.__file__).resolve()
    assert real.parent.parent.name == "src", real
    assert real.parent.parent.parent.name == "copy_paste_detector", real
    assert not (SRC.parent / "copy_paste_detector").exists(), "the src/ symlink is back"
