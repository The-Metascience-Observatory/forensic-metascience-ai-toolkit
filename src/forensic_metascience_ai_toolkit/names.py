"""Display names: the ONE alias table from stored identifiers to the names
people read (Phase 5 of the modular refactor).

Stored identifiers never change: the `producer` values `tool_expert` and
`science_error` are hashed into every `finding_id`; the stage labels
`tool_agent` / `science_agent` name files other code reads
(`prompt.tool_agent.md`, `toolcalls.science_agent.json`) and key
`run_meta.stages`; the channel keys key `channels`. Every reader that shows one
of them to a person maps it through `display()`.

Derived from each module's MODULE.md (`name`, `label`, `producer` ->
`display`), so a module's display name is declared once, beside its
definition. The few identifiers that are not a module's (channel keys,
retired labels on archived runs) are listed below.
"""

from __future__ import annotations

from functools import lru_cache

#: Identifiers that are not a module's name, label or producer.
_EXTRA = {
    "tortured_phrases": "Text forensics (tortured phrases)",   # channel key
    "adjudication": "Adjudicator",
    "harness": "Harness sweep (deterministic)",   # producer, not a module
    # Labels of the serial pipeline (deleted v1.27.0), still on archived runs.
    "stage1": "Tools agent (serial sweep)",
    "stage2": "Editorial (serial pipeline)",
    "sweep": "Tools agent (serial sweep)",
}


@lru_cache(maxsize=1)
def display_names() -> dict[str, str]:
    """{stored identifier: display name}. A module's name wins over another
    module's label or producer."""
    from .modules import definitions
    out: dict[str, str] = {}
    defs = list(definitions().values())
    for attr in ("name", "label", "producer"):
        for d in defs:
            key = getattr(d, attr)
            if key and key not in out:
                out[key] = d.display
    for key, value in _EXTRA.items():
        out.setdefault(key, value)
    return out


def display(identifier: str | None) -> str:
    """The display name for a stored identifier; unknown ones pass through."""
    if not identifier:
        return ""
    return display_names().get(str(identifier), str(identifier))
