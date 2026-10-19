"""The module contract: what a module declares, and what it hands back.

A module is a folder under `modules/` holding `MODULE.md` (YAML frontmatter =
its definition; body = documentation) and `module.py` (its code). The core
reads the definition to validate pipelines and schedule work; it never
imports a specific module by name.

Producer modules implement `async run(ctx, needed) -> ModuleResult`. The
finaliser (the adjudicator) implements `async finalize(ctx, merged, **inputs)`.
See docs/specs/modules.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

KINDS = ("agent", "deterministic", "ai_review", "finalizer")


@dataclass(frozen=True)
class ModuleDef:
    """A module's declaration, read from its MODULE.md frontmatter."""

    name: str
    kind: str                       # agent | deterministic | ai_review | finalizer
    producer: str | None            # STORED producer value; hashed into finding ids
    label: str                      # the history/run_meta stage label
    options: frozenset[str] = frozenset()
    needs: tuple[str, ...] = ()
    display: str = ""
    order: int = 0                  # canonical merge order (finding-id suffixes)
    backend_configurable: bool = False
    prompt: str = ""                # where the agent's system prompt lives today


@dataclass
class ModuleResult:
    """What one producer module returns to the core.

    `stage` is an agent's CLI stage dict (None when the stage did not run or
    failed); `doc` its parsed producer document; `record` a deterministic
    track's record. `limitations` are this module's, merged by the core in
    canonical module order so a report reads the same from run to run.
    """

    name: str
    stage: dict | None = None
    doc: dict | None = None
    record: dict | None = None
    limitations: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class Module:
    """Base class. `definition` is bound by the registry."""

    definition: ModuleDef

    @property
    def name(self) -> str:
        return self.definition.name

    async def run(self, ctx, needed: dict[str, ModuleResult]) -> ModuleResult:
        raise NotImplementedError(f"{self.name} is not a producer module")
