"""The one door from the toolkit to the optional copy-paste detector.

The raw-data detector (`copy_paste_detector`) is its own repository since
2026-11-06, checked out beside the toolkit as
`../metascience-observatory-copypaste-detector` and installed editable after
it. It imports nothing from the toolkit. The toolkit must run without it:
host code reaches the package ONLY through `load()` (a static test pins
this), so its absence is one named state, `CopyPastePluginUnavailable`, never
a crash at import time and never an empty result that reads as "no
duplicated data". Same shape as `image_plugin`.

`METASCIENCE_BLOCK_COPYPASTE_PLUGIN=1` makes the package unavailable even when
it is installed, which is how the suite proves the toolkit runs without it.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
from pathlib import Path

PACKAGE = "copy_paste_detector"
#: The sibling checkout's folder name, beside the toolkit's repository root.
CHECKOUT = "metascience-observatory-copypaste-detector"
INSTALL_HINT = ("the copy-paste detector is not installed; it is a separate "
                f"repository (pip install -e ../{CHECKOUT})")


class CopyPastePluginUnavailable(ImportError):
    """The optional copy-paste detector package is absent (or blocked)."""


def blocked() -> bool:
    return os.environ.get("METASCIENCE_BLOCK_COPYPASTE_PLUGIN", "").strip() not in ("", "0")


def available() -> bool:
    if blocked():
        return False
    try:
        return importlib.util.find_spec(PACKAGE) is not None
    except (ImportError, ValueError):
        return False


def load(name: str = ""):
    """Import `copy_paste_detector[.name]`, or raise
    `CopyPastePluginUnavailable` naming what is missing."""
    if not available():
        raise CopyPastePluginUnavailable(INSTALL_HINT)
    return importlib.import_module(f"{PACKAGE}.{name}" if name else PACKAGE)


def unavailable_record(what: str = "raw-data duplication check") -> dict:
    """The structured refusal a tool or service returns in place of a result."""
    return {"error": f"{what} unavailable: {INSTALL_HINT}",
            "state": "copypaste_plugin_unavailable", "severity": "indeterminate"}


def sibling_source_root(toolkit_src: Path) -> Path | None:
    """`<toolkit repo>/../metascience-observatory-copypaste-detector/src` when that
    checkout holds the package, else None (then the installed package, if any,
    is what a child imports)."""
    root = Path(toolkit_src).resolve().parent.parent / CHECKOUT / "src"
    return root if (root / PACKAGE / "__init__.py").is_file() else None
