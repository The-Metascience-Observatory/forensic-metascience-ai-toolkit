"""Module discovery: every `modules/<name>/MODULE.md` is a module.

Adding a module is adding a folder. The registry reads each folder's
frontmatter into a `ModuleDef` (unknown or missing keys are errors -- a
module that declares itself wrongly must not load as something else) and
imports its `module.py` only when a pipeline uses it. Ordinary subpackages,
never file-path loading: frozen-code snapshots, `sys.modules` aliases and
worker pickling all need real import names.
"""

from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path

import yaml

from .base import KINDS, Module, ModuleDef, ModuleResult

__all__ = ["ModuleDef", "ModuleResult", "Module", "definitions", "load",
           "MODULES_DIR", "ModuleDefinitionError"]

MODULES_DIR = Path(__file__).resolve().parent

_REQUIRED = {"name", "kind", "producer", "label", "order"}
_ALLOWED = _REQUIRED | {"options", "needs", "display", "backend_configurable",
                        "prompt", "description"}


class ModuleDefinitionError(ValueError):
    """A MODULE.md that does not declare a valid module."""


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ModuleDefinitionError(f"{path}: missing YAML frontmatter")
    _, front, _body = text.split("---", 2)
    data = yaml.safe_load(front) or {}
    if not isinstance(data, dict):
        raise ModuleDefinitionError(f"{path}: frontmatter must be a mapping")
    return data


def _parse(path: Path) -> ModuleDef:
    data = _frontmatter(path)
    missing = _REQUIRED - set(data)
    extra = set(data) - _ALLOWED
    if missing or extra:
        raise ModuleDefinitionError(
            f"{path}: missing {sorted(missing)} / unknown {sorted(extra)}")
    if data["name"] != path.parent.name:
        raise ModuleDefinitionError(
            f"{path}: name {data['name']!r} must match its folder "
            f"{path.parent.name!r}")
    if data["kind"] not in KINDS:
        raise ModuleDefinitionError(f"{path}: kind must be one of {KINDS}")
    return ModuleDef(
        name=str(data["name"]), kind=str(data["kind"]),
        producer=data["producer"], label=str(data["label"]),
        options=frozenset(data.get("options") or ()),
        needs=tuple(data.get("needs") or ()),
        display=str(data.get("display") or data["name"]),
        order=int(data["order"]),
        backend_configurable=bool(data.get("backend_configurable", False)),
        prompt=str(data.get("prompt") or ""))


@lru_cache(maxsize=1)
def definitions() -> dict[str, ModuleDef]:
    """Every module's definition, in canonical order."""
    defs = [_parse(p) for p in sorted(MODULES_DIR.glob("*/MODULE.md"))]
    names = {d.name for d in defs}
    for d in defs:
        unknown = set(d.needs) - names
        if unknown:
            raise ModuleDefinitionError(
                f"module {d.name!r} needs unknown module(s) {sorted(unknown)}")
    orders = [d.order for d in defs]
    if len(set(orders)) != len(orders):
        raise ModuleDefinitionError("two modules declare the same `order`")
    return {d.name: d for d in sorted(defs, key=lambda d: d.order)}


def load(name: str) -> Module:
    """The module object for `name` (imports its module.py on first use)."""
    definition = definitions()[name]
    mod = importlib.import_module(f"{__name__}.{name}.module")
    instance = mod.MODULE
    instance.definition = definition
    return instance
