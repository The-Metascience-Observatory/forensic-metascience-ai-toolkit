"""Resumable, process-isolated detection and bounded asynchronous AI review."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import socket
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from .grok import SCHEMA, SYSTEM, GrokAdjudicator, packets, subprocess_output
from .readers import DetectionLimits
from .report import render_index, render_report
from .storage import atomic_json, code_hash, digest, file_hash, now, read_jsonl


@contextmanager
def output_lock(root):
    """One coordinator owns an output index; stale same-host locks are recoverable."""
    lock = root / ".batch.lock"
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            try:
                owner = json.loads(lock.read_text())
                if owner["host"] != socket.gethostname():
                    raise ValueError("Output belongs to another host; inspect .batch.lock")
                os.kill(owner["pid"], 0)
            except ProcessLookupError:
                lock.unlink()
                continue
            raise ValueError("Another batch owns this output directory") from None
    else:
        raise ValueError("Could not claim output directory")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(
                {"pid": os.getpid(), "host": socket.gethostname(), "started_at": now()}, handle
            )
        yield
    finally:
        lock.unlink(missing_ok=True)


def load_manifest(path):
    path = Path(path).resolve()
    rows = read_jsonl(path)
    ids = set()
    for row in rows:
        pid = row.get("paper_id")
        if not isinstance(pid, str) or not pid.strip() or pid in ids:
            raise ValueError("Each paper_id must be a unique nonempty string")
        ids.add(pid)
        if not isinstance(row.get("files"), list):
            raise ValueError(f"{pid}: files must be an array")
        files = []
        for value in row["files"]:
            f = dict(value) if isinstance(value, dict) else {"path": value}
            p = Path(f["path"])
            f.setdefault("name", p.as_posix() if not p.is_absolute() else p.name)
            f["path"] = str((path.parent / p).resolve())
            files.append(f)
        row["files"] = files
        row["context_files"] = [
            str((path.parent / Path(p)).resolve()) for p in row.get("context_files", [])
        ]
    return rows


def load_context(row):
    output, failures = [], []
    for path in row.get("context_files", []):
        p = Path(path)
        try:
            if p.suffix.lower() not in {".txt", ".md", ".xml", ".html", ".htm"}:
                raise ValueError("Context must be pre-extracted text, XML or HTML")
            text = p.read_text(encoding="utf-8")
            output.append({"name": p.name, "sha256": file_hash(p), "text": text})
        except (OSError, UnicodeError, ValueError) as exc:
            failures.append({"path": path, "error": str(exc)})
    return output, failures


def reusable(root, row, fingerprint):
    entry = root / "latest" / (digest(row["paper_id"]) + ".json")
    if not entry.exists():
        return None
    latest = json.loads(entry.read_text())
    if latest["fingerprint"] != fingerprint:
        return None
    folder = root / latest["directory"]
    try:
        meta = json.loads((folder / "manifest.json").read_text())
        if meta["status"] != "completed":
            return None
        for artifact in list(meta["artifacts"].values()) + list(meta["source_artifacts"].values()):
            target = (folder / artifact["path"]).resolve()
            if (
                not target.is_relative_to(folder.resolve())
                or file_hash(target) != artifact["sha256"]
            ):
                return None
        return {
            "paper_id": row["paper_id"],
            "status": "completed",
            "reused": True,
            "run_id": meta["id"],
            "directory": latest["directory"],
            "review": (Path(latest["directory"]) / "review.html").as_posix(),
        }
    except (OSError, ValueError, KeyError):
        return None


async def run_batch(
    manifest,
    output,
    *,
    workers=None,
    ai_concurrency=2,
    backend="none",
    model="grok-4.6",
    detector_timeout=300,
    ai_timeout=180,
    max_ai_calls=500,
    retries=2,
    resume=False,
    limits=None,
    max_row_pairs=0,
    grok_binary="grok",
):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    workers = workers if workers is not None else min(4, os.cpu_count() or 1)
    if (
        workers < 1
        or ai_concurrency < 1
        or detector_timeout <= 0
        or backend not in {"none", "grok"}
    ):
        raise ValueError("Invalid workers, timeout or backend")
    rows = load_manifest(manifest)
    limits = limits or DetectionLimits(0, 0, 0)
    configuration = {
        "backend": backend,
        "model": model,
        "limits": asdict(limits),
        "max_row_pairs": max_row_pairs,
        "detector_timeout": detector_timeout,
        "ai_timeout": ai_timeout,
        "retries": retries,
        "max_ai_calls": max_ai_calls,
        "code_sha256": code_hash(),
        "prompt_sha256": digest([SYSTEM, SCHEMA]),
    }
    detector_sem = asyncio.Semaphore(workers)
    grok = (
        GrokAdjudicator(
            concurrency=ai_concurrency,
            max_calls=max_ai_calls,
            timeout=ai_timeout,
            retries=retries,
            model=model,
            binary=grok_binary,
        )
        if backend == "grok"
        else None
    )
    completed = []
    started = now()
    tick = time.monotonic()

    async def one(row):
        contexts, context_failures = load_context(row)
        identities = []
        for f in row["files"]:
            try:
                sha = file_hash(f["path"])
            except OSError:
                sha = None
            identities.append({**{k: v for k, v in f.items() if k != "path"}, "sha256": sha})
        fingerprint = digest(
            [
                configuration,
                row["paper_id"],
                row.get("data_context", "unknown"),
                identities,
                contexts,
                context_failures,
            ]
        )
        if resume:
            previous = reusable(root, row, fingerprint)
            if previous:
                completed.append(previous)
                return
        rid = "cp_" + uuid.uuid4().hex
        folder = root / "runs" / rid
        folder.mkdir(parents=True)
        from . import __version__

        meta = {
            "version": __version__,
            "schema_version": 2,
            "id": rid,
            "component": "copy_paste",
            "paper_id": row["paper_id"],
            "fingerprint": fingerprint,
            "configuration": configuration,
            "started_at": now(),
            "status": "running",
            "source_artifacts": {},
            "artifacts": {},
            "context_failures": context_failures,
        }
        atomic_json(folder / "pending.json", meta)
        result = {
            "severity": "indeterminate",
            "error": "Detection did not complete",
            "coverage": {"status": "not_evaluable"},
        }
        adjudication = {"status": "not_requested", "decisions": [], "receipts": []}
        try:
            files = []
            async with detector_sem:
                for index, (f, identity) in enumerate(zip(row["files"], identities)):
                    if identity["sha256"] is None:
                        files.append(f)
                        continue
                    target = folder / "inputs" / f"{index}{Path(f['path']).suffix.lower()}"
                    target.parent.mkdir(exist_ok=True)
                    shutil.copyfile(f["path"], target)
                    if file_hash(target) != identity["sha256"]:
                        raise ValueError(f"Input changed during capture: {f['name']}")
                    meta["source_artifacts"][f["name"]] = {
                        "path": target.relative_to(folder).as_posix(),
                        "sha256": identity["sha256"],
                    }
                    files.append({**f, "path": str(target)})
                request = {
                    "paper_id": row["paper_id"],
                    "files": files,
                    "data_context": row.get("data_context", "unknown"),
                    "limits": asdict(limits),
                    "max_row_pairs": max_row_pairs,
                    "output": str(folder / "result.json"),
                }
                meta["detector_started_at"] = now()
                env = {
                    **os.environ,
                    "OPENBLAS_NUM_THREADS": "1",
                    "OMP_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1",
                }
                env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
                code, stdout, stderr = await subprocess_output(
                    [sys.executable, "-m", "copy_paste_detector.worker"],
                    stdin=json.dumps(request).encode(),
                    env=env,
                    cwd=folder,
                    timeout=detector_timeout,
                )
                meta.update(detector_completed_at=now(), detector_exit_code=code)
                (folder / "detector.stderr.txt").write_text(stderr)
                if (folder / "result.json").exists():
                    result = json.loads((folder / "result.json").read_text())
                elif code:
                    raise ValueError(f"Detection process exited {code}: {stderr[-500:]}")
            if grok and not result.get("error"):
                jobs = list(packets(result, contexts, context_failures=context_failures))
                # Fixed worker pool: do not create thousands of pending tasks.
                queue = asyncio.Queue()
                for i, packet in enumerate(jobs):
                    queue.put_nowait((i, packet))
                receipts = []

                async def consume():
                    while not queue.empty():
                        i, packet = queue.get_nowait()
                        receipt = await grok.judge(packet, folder / "ai" / str(i))
                        receipts.append({"packet": i, **receipt})

                await asyncio.gather(*(consume() for _ in range(min(ai_concurrency, len(jobs)))))
                receipts.sort(key=lambda r: r["packet"])
                decisions = [d for r in receipts for d in r["decisions"]]
                adjudication = {
                    "status": "completed"
                    if all(r["status"] == "completed" for r in receipts)
                    else "partial",
                    "decisions": decisions,
                    "receipts": receipts,
                }
            meta["status"] = (
                "failed"
                if result.get("error")
                else "partial"
                if result["coverage"]["status"] != "complete" or adjudication["status"] == "partial"
                else "completed"
            )
        except asyncio.CancelledError:
            meta["status"] = "cancelled"
            raise
        except (OSError, ValueError, TimeoutError) as exc:
            meta.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            result.update(
                error=meta["error"], severity="indeterminate", coverage={"status": "not_evaluable"}
            )
        finally:
            meta["completed_at"] = now()
            atomic_json(folder / "result.json", result)
            atomic_json(folder / "adjudication.json", adjudication)
            atomic_json(folder / "contexts.json", contexts)
            render_report(folder, meta, result, adjudication)
            for name in ("result.json", "adjudication.json", "contexts.json", "review.html"):
                meta["artifacts"][name] = {"path": name, "sha256": file_hash(folder / name)}
            for target in sorted((folder / "ai").rglob("*")) if (folder / "ai").exists() else []:
                if target.is_file():
                    name = target.relative_to(folder).as_posix()
                    meta["artifacts"][name] = {"path": name, "sha256": file_hash(target)}
            atomic_json(folder / "manifest.json", meta)
            (folder / "pending.json").unlink(missing_ok=True)
            relative = folder.relative_to(root).as_posix()
            atomic_json(
                root / "latest" / (digest(row["paper_id"]) + ".json"),
                {"directory": relative, "fingerprint": fingerprint},
            )
            completed.append(
                {
                    "paper_id": row["paper_id"],
                    "run_id": rid,
                    "status": meta["status"],
                    "reused": False,
                    "directory": relative,
                    "review": relative + "/review.html",
                }
            )
            atomic_json(
                root / "index.json",
                {"started_at": started, "runs": sorted(completed, key=lambda r: r["paper_id"])},
            )

    with output_lock(root):
        # Bound active paper tasks too; finished detection can overlap AI.
        queue = asyncio.Queue()
        for row in rows:
            queue.put_nowait(row)

        async def consume_papers():
            while not queue.empty():
                await one(queue.get_nowait())

        tasks = [
            asyncio.create_task(consume_papers())
            for _ in range(min(workers + ai_concurrency, len(rows)))
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            summary = {
                "started_at": started,
                "completed_at": now(),
                "papers_requested": len(rows),
                "configuration": configuration,
                "workers": workers,
                "ai_concurrency": ai_concurrency,
                "ai_calls_attempted": grok.calls if grok else 0,
                "wall_seconds": time.monotonic() - tick,
                "runs": sorted(completed, key=lambda r: r["paper_id"]),
            }
            atomic_json(root / "index.json", summary)
            render_index(root, summary["runs"])
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--ai-concurrency", type=int, default=2)
    parser.add_argument("--backend", choices=["none", "grok"], default="none")
    parser.add_argument("--model", default="grok-4.6")
    parser.add_argument("--detector-timeout", type=float, default=300)
    parser.add_argument("--ai-timeout", type=float, default=180)
    parser.add_argument("--max-ai-calls", type=int, default=500)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    for flag in ("max-rows", "max-columns", "max-sheets", "max-row-pairs"):
        parser.add_argument("--" + flag, type=int, default=0, help="0 = unlimited")
    args = vars(parser.parse_args(argv))
    output = args.pop("output_dir")
    manifest = args.pop("manifest")
    try:
        limits = DetectionLimits(*(args.pop(k) for k in ("max_rows", "max_columns", "max_sheets")))
        summary = asyncio.run(run_batch(manifest, output, limits=limits, **args))
        print(json.dumps(summary, indent=2))
        return int(any(r["status"] != "completed" for r in summary["runs"]))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
