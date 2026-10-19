"""Run producer modules by their declared `needs`.

SEMANTICS (docs/specs/modules.md):

* Every producer starts as soon as the modules it `needs` have FINISHED --
  completion, not success. A module receives its needs' results and decides
  for itself what a failed dependency means; a failed dependency never
  silently skips a module.
* Modules that need nothing start together, at once. There are no layer
  barriers: a module waits only for what it names.
* The finaliser is not scheduled here. The core calls it after every
  producer has finished, which is the one barrier in the pipeline.
* Results come back keyed by module name; the core merges them in canonical
  order (`ModuleDef.order`), never completion order, so finding-id suffixes
  and the report do not depend on which model answered first.
* Exceptions: a module that raises is recorded as an `error` on its result
  ONLY if its own code chose to catch it (the analysts do -- one analyst
  failing must not sink the run). Otherwise the exception propagates out of
  `run_producers`, as it always has for the image and text tracks.
* Cancellation and cleanup: every task is registered in `background` before
  anything is awaited, so the caller's existing cleanup cancels and drains
  all of them if the run stops.
"""

from __future__ import annotations

import asyncio

from ..modules import ModuleResult


async def run_producers(ctx, specs, modules, background: list) -> dict[str, ModuleResult]:
    tasks: dict[str, asyncio.Task] = {}

    async def runner(spec):
        needed = {}
        for name in spec.definition.needs:
            if name in tasks:
                needed[name] = await tasks[name]
        return await modules[spec.use].run(ctx, needed)

    for spec in specs:
        tasks[spec.use] = asyncio.create_task(runner(spec), name=f"module:{spec.use}")
    background.extend(tasks.values())
    if not tasks:
        return {}
    done = await asyncio.gather(*tasks.values())
    return dict(zip(tasks, done))
