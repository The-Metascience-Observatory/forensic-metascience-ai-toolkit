"""Compatibility alias: `metascience_agent` is the toolkit's old import name.

The package was renamed `forensic_metascience_ai_toolkit` in 2.0.0. This shim
keeps old code working: `import metascience_agent.X` returns THE SAME module
object as `forensic_metascience_ai_toolkit.X` (never a second copy, which
would duplicate module-level state such as caches, registries and locks).

Records written before the rename name the old modules, for example
`python -m metascience_agent.mcp_server` in archived transcripts; those still
resolve. New code should import `forensic_metascience_ai_toolkit`.
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
import warnings

_OLD = __name__
_NEW = "forensic_metascience_ai_toolkit"

warnings.warn(
    f"`{_OLD}` was renamed `{_NEW}`; import `{_NEW}` instead.",
    DeprecationWarning,
    stacklevel=2,
)


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, target: str) -> None:
        self._target = target

    def create_module(self, spec):
        return importlib.import_module(self._target)

    def exec_module(self, module) -> None:
        # The real module is already executed; nothing to run twice.
        pass

    # `python -m metascience_agent.X` goes through runpy, which asks the
    # loader for code rather than a module.
    def _real_loader(self):
        return importlib.util.find_spec(self._target).loader

    def get_code(self, fullname):
        return self._real_loader().get_code(self._target)

    def is_package(self, fullname):
        return self._real_loader().is_package(self._target)


class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(_OLD + "."):
            return None
        real = _NEW + fullname[len(_OLD):]
        real_spec = importlib.util.find_spec(real)
        if real_spec is None:
            return None
        # `origin` is what runpy puts in sys.argv[0] for `python -m`.
        spec = importlib.util.spec_from_loader(
            fullname, _AliasLoader(real), origin=real_spec.origin,
            is_package=real_spec.submodule_search_locations is not None)
        if real_spec.submodule_search_locations is not None:
            spec.submodule_search_locations = list(real_spec.submodule_search_locations)
        return spec


if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

# The package itself: same object, so attributes and `__path__` match.
sys.modules[_OLD] = importlib.import_module(_NEW)
