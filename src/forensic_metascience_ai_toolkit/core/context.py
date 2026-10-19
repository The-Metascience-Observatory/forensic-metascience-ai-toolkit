"""Everything a module may read about the run it is part of.

Built once by `parallel._coordinate_analysis` and handed to every module. A
module reads it; the only things it writes are `system_prompts` (through
`remember`, so the archived prompt is the one that was sent) and its own
`ModuleResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BackendSettings:
    """One module's model backend, resolved."""

    backend: Any                   # llm_backend.Backend
    model: str
    effort: str

    @property
    def name(self) -> str:
        return self.backend.name


@dataclass
class RunContext:
    config: Any                    # pipeline_config.PipelineConfig
    paper_path: str
    paper_dir: Path
    paper_id: str
    src: Any                       # agent._resolve_paper_sources(...)
    text: str
    survey_note: str
    run_slug: str
    run_settings: BackendSettings  # the run-level backend (CLI/API/pipeline)
    verbose: bool = False
    timeout: float | None = None
    on_progress: Any = None
    budget_usd: float | None = None
    toolset: frozenset[str] | None = None   # restricted tools-agent toolset
    system_prompts: dict[str, str] = field(default_factory=dict)

    @property
    def figures(self) -> bool:
        return self.config.figures

    def remember(self, label: str, text: str) -> str:
        self.system_prompts[label] = text
        return text

    def settings_for(self, module: str) -> BackendSettings:
        """A module's backend: its own `backend:` in the pipeline file, else
        the run's. A module-level setting is the most specific statement in
        the file, so it wins over the run-level one (and over a CLI flag,
        which sets the run level). Its model defaults to that backend's
        default, never to another backend's model."""
        spec = self.config.module(module)
        declared = (spec.backend if spec is not None else None) or {}
        if not declared:
            return self.run_settings
        from ..llm_backend import resolve_backend
        be = resolve_backend(declared["name"])
        return BackendSettings(
            backend=be, model=declared.get("model") or be.default_model,
            effort=declared.get("effort") or self.run_settings.effort)
