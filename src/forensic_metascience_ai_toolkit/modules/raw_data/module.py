"""Raw data: the copy-paste detector as a child track. See MODULE.md."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from ... import agent as _agent
from ..base import Module, ModuleResult

#: Seconds before the child is killed (`METASCIENCE_RAW_DATA_TIMEOUT`).
DEFAULT_TIMEOUT = 900


def _timeout() -> float:
    try:
        return float(os.environ.get("METASCIENCE_RAW_DATA_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError:
        return float(DEFAULT_TIMEOUT)


async def run_raw_track(paper_dir, timeout_s: float | None = None) -> dict:
    """The child's record: ran / execution_status / detail / output."""
    timeout_s = _timeout() if timeout_s is None else timeout_s
    started = time.monotonic()
    record = {"ran": False, "is_error": False, "execution_status": "failed",
              "detail": "", "output": {}, "wall_seconds": 0.0}
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "forensic_metascience_ai_toolkit.raw_track", str(paper_dir),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        # The child imports copy_paste_detector: from THIS tree, not the .pth.
        env=_agent._build_track_env(), start_new_session=True)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout_s)
    except asyncio.TimeoutError:
        _agent._kill_subprocess_group(proc)
        await proc.wait()
        record.update(is_error=True, detail=f"raw-data track timed out after "
                      f"{timeout_s:.0f} s; the spreadsheets are UNSCREENED")
        return record
    finally:
        record["wall_seconds"] = round(time.monotonic() - started, 2)
    if proc.returncode != 0:
        tail = err.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
        record.update(is_error=True, detail=f"raw-data track crashed "
                      f"(exit {proc.returncode}): {tail[0][:300]}")
        return record
    try:
        output = json.loads(out.decode("utf-8"))
    except ValueError as exc:
        record.update(is_error=True, detail=f"raw-data track output unreadable: {exc}")
        return record
    record["output"] = output
    if not output.get("files"):
        record.update(execution_status="did_not_run",
                      detail="no .csv/.tsv/.xlsx/.xlsm file in the paper "
                             "directory or its supplement folders")
        return record
    result = output.get("result") or {}
    coverage = (result.get("coverage") or {}).get("status") or "unknown"
    record.update(
        ran=True,
        execution_status="completed" if coverage == "complete" else "incomplete",
        detail=(f"{len(output['files'])} file(s), "
                f"{result.get('n_duplicate_groups', 0)} group(s), coverage "
                f"{coverage}"))
    return record


class RawData(Module):
    async def run(self, ctx, needed) -> ModuleResult:
        record = await run_raw_track(ctx.paper_dir)
        limitations = []
        if record["is_error"]:
            limitations.append(record["detail"])
        elif record["execution_status"] == "incomplete":
            limitations.append(
                "the raw-data detector's coverage was PARTIAL ("
                + record["detail"] + "); this is not a complete negative "
                "review of the spreadsheets")
        return ModuleResult(self.name, record=record, limitations=limitations)


MODULE = RawData()
