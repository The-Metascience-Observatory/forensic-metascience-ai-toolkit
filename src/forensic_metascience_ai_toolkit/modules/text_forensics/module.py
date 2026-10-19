"""Text forensics: the tortured-phrases child track. See MODULE.md."""

from __future__ import annotations

from ... import agent as _agent
from ..base import Module, ModuleResult


class TextForensics(Module):
    async def run(self, ctx, needed) -> ModuleResult:
        record = await _agent._run_text_track(ctx.paper_dir,
                                              on_progress=ctx.on_progress)
        return ModuleResult(self.name, record=record)


MODULE = TextForensics()
