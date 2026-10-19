"""The one door from the toolkit to the optional image analysis package.

The image analysis system (`metascience_observatory_image_analysis`) is a
separate, privately distributed package that depends on this toolkit. The
toolkit must run without it: every statistical check, both analysts, the
adjudicator, the MCP server and the workbench's statistical views. Host code
reaches the image package ONLY through `load()` (a static test pins this), so
its absence is one named state, `ImagePluginUnavailable`, never a crash at
import time and never an empty result that reads as "no image problems".

`METASCIENCE_BLOCK_IMAGE_PLUGIN=1` makes the package unavailable even when it
is installed, which is how the suite proves the toolkit runs without it.
"""
from __future__ import annotations

import importlib
import importlib.util
import os

PACKAGE = "metascience_observatory_image_analysis"
INSTALL_HINT = ("the image analysis package is not installed; it is distributed "
                "separately (pip install -e ../metascience-observatory-image-analysis)")


class ImagePluginUnavailable(ImportError):
    """The optional image analysis package is absent (or blocked)."""


def blocked() -> bool:
    return os.environ.get("METASCIENCE_BLOCK_IMAGE_PLUGIN", "").strip() not in ("", "0")


def available() -> bool:
    if blocked():
        return False
    try:
        return importlib.util.find_spec(PACKAGE) is not None
    except (ImportError, ValueError):
        return False


def load(name: str = ""):
    """Import `metascience_observatory_image_analysis[.name]`, or raise
    `ImagePluginUnavailable` naming what is missing."""
    if not available():
        raise ImagePluginUnavailable(INSTALL_HINT)
    return importlib.import_module(f"{PACKAGE}.{name}" if name else PACKAGE)


def unavailable_record(what: str = "image analysis") -> dict:
    """The structured refusal a tool or service returns in place of a result."""
    return {"error": f"{what} unavailable: {INSTALL_HINT}",
            "state": "image_plugin_unavailable", "severity": "indeterminate"}
