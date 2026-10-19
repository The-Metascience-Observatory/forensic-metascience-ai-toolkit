"""Producer boundaries for immutable history; context is task-local, not global."""

from __future__ import annotations

import contextvars
import json
import os
import shutil
from pathlib import Path

from .analysis_runs import (
    Archive,
    digest,
    now,
    project_root,
    provenance,
    read,
)

#: The task-local history context (execution, root, parent run). One object,
#: shared with the image package's run helpers.
CONTEXT = contextvars.ContextVar("analysis_history", default={})






def env():
    context = CONTEXT.get()
    return {
        k: str(v)
        for k, v in {
            "METASCIENCE_EXECUTION_ID": context.get("execution_id")
            or os.environ.get("METASCIENCE_EXECUTION_ID"),
            "METASCIENCE_HISTORY_ROOT": context.get("root")
            or os.environ.get("METASCIENCE_HISTORY_ROOT"),
            "METASCIENCE_PARENT_RUN_ID": context.get("run_id")
            or os.environ.get("METASCIENCE_PARENT_RUN_ID"),
        }.items()
        if v
    }








def record_tool_copy(fn, args):
    """The raw return is archived before the tool ledger can truncate it."""
    context = env()
    paper_s = os.environ.get("METASCIENCE_PAPER_DIR")
    if not paper_s or not context.get("METASCIENCE_EXECUTION_ID"):
        return fn(**args)
    from .analysis_history import capture_copy

    paper = Path(paper_s)
    archive = Archive(context["METASCIENCE_HISTORY_ROOT"])
    run = archive.start(
        context["METASCIENCE_EXECUTION_ID"],
        "copy_paste",
        paper.relative_to(archive.root).as_posix(),
        parent_run_id=context.get("METASCIENCE_PARENT_RUN_ID"),
        provenance=provenance("copy_paste", parameters=args),
    )
    effective = dict(args)
    original_path = args.get("path") or args.get("file_path")
    try:
        captured_path = snapshot_copy_input(archive, run, original_path)
        if captured_path:
            effective["path" if "path" in args else "file_path"] = str(captured_path)
        result = fn(**effective)
    except BaseException as exc:
        archive.seal(run, status="failed", detail=str(exc), completed_at=now())
        raise
    path = captured_path or original_path or result.get("path")
    saved = capture_copy(archive.root, paper, result, path, run=run)
    returned = (
        json.loads(json.dumps(result, default=str).replace(str(captured_path), str(original_path)))
        if captured_path
        else result
    )
    return {**returned, "history_run_id": saved["id"]}


def snapshot_copy_input(archive, run, source):
    if not source or not Path(source).is_file():
        return None
    artifact = archive.object(source)
    run["provenance"]["input_hashes"] = {str(source): artifact["sha256"]}
    destination = archive.base / "work" / run["id"] / Path(source).name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        archive.base / "objects" / artifact["sha256"][:2] / artifact["sha256"], destination
    )
    return destination






def result_archive(result):
    """The archive this run's history lives in: the one chosen when it STARTED.

    `project_root(paper)` is a lookup by marker (`.analysis_runs` or
    `.image_track` in the nearest ancestor), and the image track writes
    `.image_track/` into the paper's parent directory MID-RUN. A second lookup
    at report time therefore resolved to that directory -- a new, empty archive
    -- instead of the one the parent run was recorded in, and
    `archive.run(parent["id"])` raised `unknown or unsealed run` after the
    analysis had been paid for and before any report was written. MEASURED
    2026-10-13: `wound_healing` and `cerebrolysin_flow` (papers with raster
    images, staged as `<dir>/paper` beneath an archive-bearing ancestor) lost
    the whole run on every attempt; the two vector-only papers did not.

    `parallel` pins the root on the result at analysis start
    (`result["history_root"]`). A result without it (one built by hand, or by
    an older caller) falls back to the lookup, which is the old behaviour.
    """
    pinned = result.get("history_root")
    if pinned:
        return Archive(pinned)
    paper = Path(result["paper_path"])
    if paper.is_file():
        paper = paper.parent
    return Archive(project_root(paper))


def prepare_report_revision(result):
    """Enriched output is a revision of the sealed adjudicator response."""
    parent = result.get("run_meta", {}).get("history")
    if not parent:
        return
    archive = result_archive(result)
    saved = archive.run(parent["id"])
    doc = result["findings_v2"]
    # A repeat render is idempotent; the disclaimer is a serialization detail.
    old_doc = {k: v for k, v in (saved.get("document") or {}).items() if k != "disclaimer"}
    if digest(old_doc) == digest({k: v for k, v in doc.items() if k != "disclaimer"}):
        return
    revision = archive.start(
        parent["execution_id"],
        # The parent's own component: a partial pipeline's revision must not
        # be re-filed as the paper's comprehensive review.
        parent.get("component") or "comprehensive",
        parent["paper"],
        revision_of=parent["id"],
        provenance=parent["provenance"],
    )
    revision["component_run_ids"] = [
        r["id"]
        for r in read(archive.base / "index.json", {"runs": {}})["runs"].values()
        if r.get("parent_run_id") == parent["id"]
    ]
    doc["run_id"] = revision["id"]
    result["run_meta"]["run_id"] = revision["id"]
    result["run_meta"]["history"] = revision




def seal_report_outputs(result, output):
    parent = result.get("run_meta", {}).get("history")
    if not parent:
        return
    archive = result_archive(result)
    if not (archive.base / "runs" / f"{parent['id']}.json").exists():
        run = dict(parent, document=read(Path(output) / "findings.v2.json"))
        artifacts = (
            dict(archive.run(parent["revision_of"])["artifacts"])
            if parent.get("revision_of")
            else {}
        )
        for path in sorted(Path(output).rglob("*")):
            if path.is_file():
                aid = "report_" + digest(str(path.relative_to(output)))[:24]
                artifacts[aid] = {
                    **archive.object(path),
                    "role": "report_output",
                    "paper": run["paper"],
                    "relative_path": str(path.relative_to(output)),
                }
        archive.seal(
            run,
            artifacts=artifacts,
            status="incomplete" if result.get("is_error") else "completed",
            completed_at=now(),
        )
    from .history_db import try_sync

    try_sync(archive.root, [parent["id"], *parent.get("component_run_ids", [])])


def __getattr__(name):
    """The image-run helpers (`preserve_image`, `isolated_image_track`,
    `capture_cross`, ...) belong to the image package's own `history_runtime`;
    reached through the plugin door, so they raise `ImagePluginUnavailable`
    by name when it is not installed."""
    if name.startswith("__"):
        raise AttributeError(name)
    from .image_plugin import load
    return getattr(load("history_runtime"), name)
