"""Immutable, project-local execution/run/item history shared by all producers.

Objects are COPIES, never hard links into mutable paper directories. Manifests
are the commit point; workspaces and orphaned objects are not published runs.
Current publication and human judgments are projections, not edits to history.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .atomicio import atomic_write_text, file_lock

ARCHIVE = ".analysis_runs"
_ID = re.compile(r"[A-Za-z0-9_.-]+\Z")
STATES = {
    "running",
    "completed",
    "failed",
    "refused",
    "cancelled",
    "incomplete",
    "not_requested",
    "unavailable",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(obj):
    # Preserve the exact historical JSON bytes without allocating a second
    # full-size string and byte buffer for large clone evidence payloads.
    checksum = hashlib.sha256()
    encoder = json.JSONEncoder(sort_keys=True, ensure_ascii=False, default=str)
    for chunk in encoder.iterencode(obj):
        checksum.update(chunk.encode())
    return checksum.hexdigest()


def read(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value) or value in {".", "..", "latest"}:
        raise ValueError("invalid archive identity")
    return value


def project_root(paper):
    paper = Path(paper).resolve()
    # An explicit context wins in isolated subprocesses.
    explicit = os.environ.get("METASCIENCE_HISTORY_ROOT")
    if explicit and paper.is_relative_to(Path(explicit).resolve()):
        return Path(explicit).resolve()
    for parent in paper.parents:
        if (parent / ARCHIVE).is_dir() or (parent / ".image_track").is_dir():
            return parent
    return paper.parent


def provenance(component, **extra):
    from .version import __version__, git_state

    version = __version__
    from .image_plugin import available as _image_available
    image_installed = component != "image_forensics" or _image_available()
    if component == "image_forensics":
        # An image run is stamped with the image package's own release; a
        # component sealed `unavailable` without the package says so.
        from .image_plugin import load
        version = load("version").__version__ if image_installed else "not_installed"
    from .integration import metadata_provenance
    host_provenance = metadata_provenance() if metadata_provenance and component not in {"image_forensics", "copy_paste"} else {}
    if component == "copy_paste":
        # The parent wheel embeds this package without a separate distribution.
        # Read the version of the code actually loaded, including editable installs.
        from copy_paste_detector import __version__ as version

    fingerprint = None
    if component == "copy_paste":
        import copy_paste_detector

        folder = Path(copy_paste_detector.__file__).parent
        fingerprint = digest(
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(folder.glob("*.py"))
            }
        )
    elif component == "image_forensics" and image_installed:
        from .image_plugin import load as _image_load
        detector_fingerprint = _image_load("image_forensics.retain").detector_fingerprint

        fingerprint = detector_fingerprint()
    return {"version": version, "code_fingerprint": fingerprint, **git_state(), **host_provenance, **extra}


class Archive:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.base = self.root / ARCHIVE

    def execution(
        self,
        mode,
        *,
        execution_id=None,
        name=None,
        components=None,
        configuration=None,
        started_at=None,
        provenance=None,
        status="running",
        **extra,
    ):
        eid = identifier(execution_id or "e_" + uuid.uuid4().hex)
        path = self.base / "executions" / f"{eid}.json"
        obj = dict(
            id=eid,
            mode=mode,
            name=name or mode,
            requested_components=components or [],
            configuration=configuration or {},
            started_at=started_at,
            status=status,
            provenance=provenance or {},
            **extra,
        )
        if started_at is None and not execution_id:
            obj["started_at"] = now()
        with file_lock(self.base / "catalog.lock"):
            old = read(path)
            if old:
                if old["configuration"] != obj["configuration"] or old["mode"] != mode:
                    raise ValueError("execution configuration changed; create a new execution")
                return old
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(path, json.dumps(obj, indent=2))
        return obj

    def finish_execution(self, eid, status):
        if status not in STATES:
            raise ValueError("invalid execution state")
        path = self.base / "executions" / f"{identifier(eid)}.json"
        with file_lock(self.base / "catalog.lock"):
            obj = read(path)
            if obj is None:
                raise ValueError("unknown execution")
            obj.update(status=status, finished_at=now())
            atomic_write_text(path, json.dumps(obj, indent=2))

    def start(
        self,
        execution,
        component,
        paper,
        *,
        run_id=None,
        parent_run_id=None,
        revision_of=None,
        provenance=None,
        started_at=None,
    ):
        rid = identifier(run_id or "ar_" + uuid.uuid4().hex)
        self._refuse_retired(rid)
        if (self.base / "runs" / f"{rid}.json").exists():
            raise ValueError("cannot restart a sealed run; create a revision")
        obj = dict(
            id=rid,
            execution_id=identifier(execution),
            component=component,
            paper=paper,
            parent_run_id=parent_run_id,
            revision_of=revision_of,
            provenance=provenance or {},
            started_at=started_at or now(),
            status="running",
            schema_version=1,
        )
        path = self.base / "pending" / f"{rid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(obj, indent=2))
        # WHO is running it, beside (never inside) the run record: an unsealed
        # run is otherwise indistinguishable from an abandoned one, and a
        # SIGKILLed producer never seals. `.owner`, not `.json`, so catalog()
        # and feed() -- which glob pending/*.json -- never read it as a run.
        try:
            import socket
            atomic_write_text(owner_path(self.base, rid), json.dumps(
                {"pid": os.getpid(), "host": socket.gethostname(), "started_at": obj["started_at"]}))
        except OSError:
            pass
        return obj

    def reuse(self, execution_id, run_id):
        """Record an explicit reference without copying or relabelling the old run."""
        self.run(run_id)
        path = self.base / "executions" / f"{identifier(execution_id)}.json"
        with file_lock(self.base / "catalog.lock"):
            execution = read(path)
            execution["reused_run_ids"] = sorted(
                set(execution.get("reused_run_ids", [])) | {run_id}
            )
            atomic_write_text(path, json.dumps(execution, indent=2))

    def object(self, source):
        """Store `source` content-addressed; return its sha256, size and name.

        HASH FIRST, then copy only what the store lacks. This used to copy and
        fsync every artifact into a temp file BEFORE asking whether the store
        already held it, so re-archiving a paper whose panels had not changed
        rewrote and fsynced every byte to then delete it -- one paper's
        pre-detection snapshot took 536 s of a 600 s detection budget. A new
        object is still written to a temp file, fsynced and renamed into place,
        so an object that exists under its hash is always complete; the copy
        is a reflink where the filesystem allows (an independent inode, so the
        "copies, never hard links" rule holds). The stat check on either side
        is what proves the hashed bytes and the copied bytes are the same file.
        """
        from .fsclone import clone_or_copy

        source = Path(source)
        before = source.stat()
        h = hashlib.sha256()
        with source.open("rb") as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                h.update(chunk)
        sha = h.hexdigest()

        def unchanged():
            after = source.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError(f"artifact changed while archiving: {source}")
            return after

        dest = self.base / "objects" / sha[:2] / sha
        if dest.is_file():
            after = unchanged()
            return {"sha256": sha, "size": after.st_size, "name": source.name}
        tempdir = self.base / "tmp"
        tempdir.mkdir(parents=True, exist_ok=True)
        temp = tempdir / uuid.uuid4().hex
        try:
            clone_or_copy(source, temp)
            after = unchanged()
            if temp.stat().st_size != after.st_size:
                raise ValueError(f"artifact copy is incomplete: {source}")
            fd = os.open(temp, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                temp.unlink()
            else:
                temp.replace(dest)
            return {"sha256": sha, "size": after.st_size, "name": source.name}
        finally:
            temp.unlink(missing_ok=True)

    def seal(
        self, run, items=(), *, artifacts=None, status="completed", detail="", completed_at=None
    ):
        if status not in STATES - {"running"}:
            raise ValueError("a sealed run needs a terminal state")
        rid = identifier(run["id"])
        obj = {
            **run,
            "status": status,
            "detail": detail,
            "completed_at": completed_at,
            "items": list(items),
            "artifacts": artifacts or {},
        }
        # Callers importing unknown dates pass None; no file mtime masquerades as a run date.
        obj["sealed_digest"] = digest(obj)
        path = self.base / "runs" / f"{rid}.json"
        with file_lock(self.base / "catalog.lock"):
            self._refuse_retired(rid)
            old = read(path)
            if old:
                if old["sealed_digest"] != obj["sealed_digest"]:
                    raise ValueError(f"sealed run {rid} already has different content")
                return old
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(path, json.dumps(obj, indent=1, default=str))
            (self.base / "pending" / f"{rid}.json").unlink(missing_ok=True)
            owner_path(self.base, rid).unlink(missing_ok=True)
            self._index(obj)
        return obj

    def _refuse_retired(self, rid):
        if rid in read(self.base / "retired_runs.json", {}):
            raise ValueError("Image run retired; create a new analysis run")

    def _index(self, obj):
        path = self.base / "index.json"
        idx = read(path, {"runs": {}})
        idx["runs"][obj["id"]] = {k: v for k, v in obj.items() if k not in {"items", "artifacts"}}
        idx["runs"][obj["id"]]["n_items"] = len(obj["items"])
        atomic_write_text(path, json.dumps(idx, indent=1))
        from .integration import published
        published(self.root, obj)

    def rebuild_index(self):
        with file_lock(self.base / "catalog.lock"):
            idx = {"runs": {}}
            for path in sorted((self.base / "runs").glob("*.json")):
                obj = read(path)
                idx["runs"][obj["id"]] = {
                    k: v for k, v in obj.items() if k not in {"items", "artifacts"}
                }
                idx["runs"][obj["id"]]["n_items"] = len(obj["items"])
            atomic_write_text(self.base / "index.json", json.dumps(idx, indent=1))
        return idx

    def run(self, rid):
        obj = read(self.base / "runs" / f"{identifier(rid)}.json")
        if obj is None:
            retired = read(self.base / "retired_runs.json", {}).get(rid)
            if retired:
                return dict(retired, status="unavailable", latest_eligible=False,
                            items=[], artifacts={}, details_retired=True,
                            detail="Image results removed at the user's request; awaiting a new analysis.")
            raise ValueError("unknown or unsealed run")
        if digest({k: v for k, v in obj.items() if k != "sealed_digest"}) != obj["sealed_digest"]:
            raise ValueError("sealed run failed its content digest check")
        return obj

    def artifact(self, rid, aid):
        obj = self.run(rid)
        if obj.get("details_retired"):
            raise FileNotFoundError(obj["detail"])
        artifact = obj["artifacts"].get(identifier(aid))
        if not artifact:
            raise ValueError("artifact not recorded for this run")
        path = self.base / "objects" / artifact["sha256"][:2] / artifact["sha256"]
        if not path.is_file():
            raise FileNotFoundError("archived artifact unavailable")
        return path, artifact

    def _inherited_panel_image(self, run, item_id, uid):
        """Return ``(reference, owner)`` from the nearest exact ancestor."""
        rid = run.get("revision_of") or run.get("parent_run_id")
        seen = set()
        while rid and rid not in seen:
            seen.add(rid)
            try:
                previous = self.run(rid)
            except (ValueError, FileNotFoundError):
                return None, None
            old_item = next(
                (it for it in previous.get("items", []) if it.get("id") == item_id),
                None,
            )
            old_panel = next(
                (
                    panel
                    for panel in (old_item or {}).get("panels", [])
                    if panel.get("uid") == uid
                ),
                None,
            )
            if old_panel and old_panel.get("image"):
                # Prove the manifest and object are still readable before a
                # feed advertises the inherited reference.
                ref = old_panel["image"]
                if str(ref).startswith("__runs/"):
                    try:
                        _, owner, aid = str(ref).split("/")
                        self.artifact(owner, aid)
                    except (ValueError, FileNotFoundError):
                        return None, None
                    return ref, rid
            rid = previous.get("revision_of") or previous.get("parent_run_id")
        return None, None

    def freeze_items(self, run, items, *, sources=None, verified=False,
                     copy_items=True, progress=None):
        """Freeze the media referenced by the actual feed, plus source artifacts.

        sources maps corpus-relative paper ids to producer workspace paths.
        Legacy files have no byte provenance: label these as captured-at-import.
        """
        # Public callers keep copy isolation. Capture owns its freshly loaded
        # item graph and can transfer it, avoiding a second multi-GB graph.
        if copy_items:
            items = copy.deepcopy(items)
        artifacts = {}
        memo = {}
        sources = sources or {}

        def save(paper, rel, role):
            if not rel:
                return None
            if str(rel).startswith(f"__runs/{run['id']}/"):
                return rel
            if str(rel).startswith("__runs/"):
                _, old_rid, aid = str(rel).split("/")
                path, _ = self.artifact(old_rid, aid)
            else:
                base = Path(sources.get(paper, self.root / paper)).resolve()
                path = (base / rel).resolve()
                if not path.is_relative_to(base):
                    return None
            key = (paper, str(rel))
            if key in memo:
                return memo[key]
            if not path.is_file():
                return None
            aid = "a_" + digest(key)[:24]
            record = self.object(path)
            # Object filenames are hashes when reusing a prior run.
            if str(rel).startswith("__runs/"):
                record["name"] = self.artifact(old_rid, str(rel).split("/")[-1])[1]["name"]
            artifacts[aid] = {
                **record,
                "role": role,
                "paper": paper,
                "original_path": str(rel),
                "evidence_source": "producer" if verified else "captured_at_import",
            }
            memo[key] = f"__runs/{run['id']}/{aid}"
            return memo[key]

        for index, item in enumerate(items):
            if progress:
                progress("freezing_items", completed=index, total=len(items), artifacts=len(artifacts))
            item.pop("decision", None)
            item["run_id"] = run["id"]
            item["execution_id"] = run["execution_id"]
            item["provenance"] = run["provenance"]
            item["evidence_source"] = "producer" if verified else "captured_at_import"
            for panel in item.get("panels", []):
                image = save(panel["paper_dir"], panel.get("image"), "panel")
                if not image:
                    image = save(
                        panel["paper_dir"],
                        self._inherited_panel_image(
                            run, item.get("id"), panel.get("uid")
                        )[0],
                        "panel",
                    )
                panel["image"] = image
                document = panel.get("document") or {}
                if str(document.get("path", "")).lower().endswith(".pdf"):
                    archived_doc = save(panel["paper_dir"], document["path"], "source_pdf")
                    if archived_doc:
                        document["path"] = archived_doc
                if not panel["image"]:
                    panel["image_unavailable_reason"] = (
                        "No archived image is available for this panel."
                    )
                else:
                    panel.pop("image_unavailable_reason", None)
            for head in [item.get("paper", {}), *item.get("papers", [])]:
                head["pdf"] = save(head.get("dir", ""), head.get("pdf"), "source_pdf")
            for field in ("exhibit", "video", "input_file", "highlight_file"):
                if item.get(field):
                    item[field] = save(item["paper"]["dir"], item[field], field)
        papers = {p["dir"] for it in items for p in it.get("papers", [])}
        papers.update(sources)
        if run.get("paper"):
            papers.add(run["paper"])
        for paper in papers:
            if progress:
                progress("freezing_sources", artifacts=len(artifacts))
            base = Path(sources.get(paper, self.root / paper))
            for pattern in (
                "image_duplication*.json",
                "metadata.json",
                "*.pdf",
                "*.xml",
                "panels/*.json",
                "panels/review/*.json",
                "panels/text_regions/*.json",
                "panels/text_regions/media/*.png", "panels/text_regions/media/*.npy",
                "figures/figures.json",
            ):
                for path in sorted(base.glob(pattern)):
                    if path.is_file():
                        save(paper, path.relative_to(base).as_posix(), "source")
                        if progress:
                            progress("freezing_sources", artifacts=len(artifacts))
        for index, it in enumerate(items):
            if progress:
                progress("evidence_keys", completed=index, total=len(items), artifacts=len(artifacts))
            it["evidence_key"] = digest(
                {
                    "panels": [
                        {
                            "uid": p.get("uid"),
                            "sha": artifacts.get(str(p.get("image", "")).split("/")[-1], {}).get(
                                "sha256"
                            ),
                        }
                        for p in it.get("panels", [])
                    ],
                    "measurements": it.get("measurements"),
                    "group": it.get("group"),
                }
            )
        return items, artifacts

    def reviews(self):
        path = self.base / "reviews.jsonl"
        out = {}
        if path.exists():
            for line in path.read_text().splitlines():
                rec = json.loads(line)
                out[(rec["run_id"], rec["item"])] = rec
        return out

    def decide(self, rid, item_id, decision, reviewer, note=""):
        from .review_io import IMAGE_DECISIONS

        if decision not in IMAGE_DECISIONS or not reviewer.strip():
            raise ValueError("valid decision and reviewer required")
        run = self.run(rid)
        if not any(it["id"] == item_id for it in run["items"]):
            raise ValueError("item does not belong to this run")
        target = next(it for it in run["items"] if it["id"] == item_id)
        rec = dict(
            evidence_key=target.get("evidence_key"),
            event_id="rv_" + uuid.uuid4().hex,
            run_id=rid,
            item=item_id,
            decision=decision,
            reviewer=reviewer.strip(),
            note=note,
            at=now(),
        )
        with file_lock(self.base / "reviews.lock"):
            with (self.base / "reviews.jsonl").open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        return rec

    def catalog(self, component=None):
        runs = list(read(self.base / "index.json", {"runs": {}})["runs"].values())
        pending = [read(p) for p in (self.base / "pending").glob("*.json")]
        runs += pending
        selected = [r for r in runs if not component or r["component"] == component]
        executions = {p.stem: read(p) for p in (self.base / "executions").glob("*.json")}
        out = []
        for eid, e in executions.items():
            rs = [
                r
                for r in selected
                if r["execution_id"] == eid or r["id"] in e.get("reused_run_ids", [])
            ]
            if not rs and component and component not in e.get("requested_components", []):
                continue
            versions = sorted(
                {str(r.get("provenance", {}).get("version") or "unknown") for r in rs}
            )
            version = ", ".join(versions) or str(
                e.get("provenance", {}).get("version") or "unknown"
            )
            at = e.get("started_at")
            out.append(
                {
                    **e,
                    "version": version,
                    "label": f"v{version} · {at or 'date unknown'} · {e['name']}",
                    "n_runs": len(rs),
                    "n_items": sum(r.get("n_items", 0) for r in rs),
                    "states": {
                        s: sum(r["status"] == s for r in rs)
                        for s in STATES
                        if any(r["status"] == s for r in rs)
                    },
                }
            )
        return sorted(out, key=lambda e: (e.get("started_at") or "", e["id"]), reverse=True)

    def feed(self, selection="latest", component="image_forensics"):
        index = list(read(self.base / "index.json", {"runs": {}})["runs"].values())
        index += [read(p) for p in (self.base / "pending").glob("*.json")]
        runs = [r for r in index if r["component"] == component]
        catalog = self.catalog(component)
        if selection != "latest":
            identifier(selection)
            if selection not in {e["id"] for e in catalog}:
                raise ValueError("unknown execution for this component")
            execution = next(e for e in catalog if e["id"] == selection)
            runs = [
                r
                for r in runs
                if r["execution_id"] == selection or r["id"] in execution.get("reused_run_ids", [])
            ]
        else:
            runs = [r for r in runs if r.get("latest_eligible", True)]
            # Latest ATTEMPT, including failures. Cross-paper analyses are their own scope.
        # A job may retry a paper internally. Show its last attempt once.
        # Copy/paste tools may analyze different input files in the same paper.
        ordered = sorted(
            runs, key=lambda r: (r.get("completed_at") or r.get("started_at") or "", r["id"])
        )
        if component == "copy_paste":
            latest_jobs = {
                r.get("paper"): r.get("parent_run_id") or r["execution_id"] for r in ordered
            }
            if selection == "latest":
                runs = [
                    r
                    for r in ordered
                    if (r.get("parent_run_id") or r["execution_id"]) == latest_jobs[r.get("paper")]
                ]
        else:
            grouped = {}
            families = {r['selection_family']: r['execution_id']
                        for r in ordered if r.get('selection_family')}
            for r in ordered:
                if r.get('selection_family') and r['execution_id'] != families[r['selection_family']]:
                    continue
                key = r.get("scope_key") or r.get("paper") or "cross"
                grouped[key] = r
            runs = list(grouped.values())
        decisions = self.reviews()
        items, notes = [], []
        for meta in runs:
            if meta["status"] == "running":
                notes.append(
                    f"{meta.get('paper') or 'project'}: analysis is unfinished or still running"
                )
                continue
            run = self.run(meta["id"])
            if run["status"] != "completed" or run.get("detail"):
                notes.append(
                    f"{run.get('paper') or 'project'}: {run['status']}. {run.get('detail', '')}"
                )
            for original in run["items"]:
                it = copy.deepcopy(original)
                for panel in it.get("panels", []):
                    if panel.get("image"):
                        continue
                    inherited, owner = self._inherited_panel_image(
                        run, it.get("id"), panel.get("uid")
                    )
                    if inherited:
                        panel["image"] = inherited
                        panel.pop("image_unavailable_reason", None)
                        panel["image_recovery"] = {
                            "method": "exact item id and panel uid in ancestor run",
                            "run_id": owner,
                        }
                it["screening_attempts"] = run.get("screening_attempts", [])
                it["run_status"] = run["status"]
                it["decision"] = decisions.get((run["id"], it["id"]))
                it["prior_decisions"] = [
                    v
                    for (rid, iid), v in decisions.items()
                    if rid != run["id"]
                    and iid == it["id"]
                    and it.get("evidence_key")
                    and v.get("evidence_key") == it["evidence_key"]
                ]
                screen = it.get("screening") or {}
                rejected = (
                    (it.get("decision") or {}).get("decision", "").startswith("false_positive")
                )
                it["publication_status"] = (
                    "cleared"
                    if rejected or it.get("cleared") or screen.get("decision") == "innocuous"
                    else "published"
                    if screen.get("validated")
                    and screen.get("decision") == "issue"
                    and screen.get("confidence") in {"medium", "high"}
                    else "unscreened"
                )
                items.append(it)
        items.sort(key=lambda i: -(i.get("rank") or {}).get("score", 0))
        states = {r["status"] for r in runs}
        empty_reason = None
        if not items:
            empty_reason = (
                "No recorded run for this component. Import saved history or select another run."
                if not runs
                else "This component was not requested in the selected execution."
                if states == {"not_requested"}
                else "The selected attempt failed or was cancelled; see its recorded coverage failure."
                if states & {"failed", "cancelled"}
                else "The selected analysis is unfinished or still running."
                if "running" in states
                else "The run is recorded, but its detailed outputs are unavailable or incomplete."
                if states & {"unavailable", "incomplete"}
                else "The component refused to analyze these inputs; see the recorded reason."
                if "refused" in states
                else "The selected completed runs recorded zero candidates."
            )
        return {
            "project": str(self.root),
            "selection": selection,
            "component": component,
            "runs": catalog,
            "built_at": now(),
            "seconds": 0,
            "items": items,
            "notes": notes,
            "empty_reason": empty_reason,
            "coverage": {
                "runs": len(runs),
                "states": {s: sum(r["status"] == s for r in runs) for s in STATES},
            },
            "counts": {
                "items": len(items),
                "within": sum(i.get("kind") == "within" for i in items),
                "cross": sum(i.get("kind") == "cross" for i in items),
                "unexplained": sum(i["publication_status"] == "published" for i in items),
                "unscreened": sum(i["publication_status"] == "unscreened" for i in items),
                "papers": len({p["dir"] for i in items for p in i.get("papers", [])}),
            },
        }


def owner_path(base, rid):
    """The `pending/<run>.owner` sidecar naming the process running `rid`."""
    return Path(base) / "pending" / f"{identifier(rid)}.owner"


def failure_progress(target):
    """The detector's last progress snapshot inside a producer workspace.

    Kept IN the failure record, because the workspace that holds it is
    reclaimable: before 2026-10-01 a timed-out paper's progress survived
    only inside its leaked workspace.
    """
    out = {}
    for name, rel in (("analysis", "panels/analysis_progress.json"),
                      ("archive", "archive_progress.json")):
        try:
            value = read(Path(target) / rel)
        except (OSError, ValueError):
            value = None
        if value is not None:
            out[name] = value
    return out or None


@contextmanager
def workspace(paper, *, execution_id=None, component="image_forensics", configuration=None,
              on_start=None):
    """Isolated mutable producer workspace; failure records survive cancellation.

    RECLAIMED ON SUCCESS since 2026-09-13. This staging tree used to be removed
    on NO path, so every re-sweep left behind a full copy of every paper it
    touched: 164.7 GB across three corpora when it was finally measured, on one
    of which (`image_discovery_2026-09_batch2`) the staging area was nearly
    twice the size of the corpus it staged. The tree is redundant by the time
    this context exits -- `capture_images` has copied the evidence into the
    content-addressed `objects/` store and the caller has published `panels`
    and `figures` back to the paper directory -- and nothing reads a `work/`
    path afterwards.

    ON FAILURE IT SURVIVES, which is the promise the first line of this
    docstring has always made. A run that never sealed never froze its output
    into `objects/` and never published it, so its tree can be the only copy of
    that work; the `except` path below deliberately does not clean up.
    `METASCIENCE_KEEP_WORKSPACE=1` keeps it on success too, for debugging.

    The copy-in uses copy-on-write clones where the filesystem offers them
    (`fsclone`), which removes the duplicated bytes without weakening the
    isolation: a reflink is an independent inode that merely shares extents
    until written, so this module's "Objects are COPIES, never hard links into
    mutable paper directories" rule still holds. Measured on the corpus disk,
    a 256 MB clone costs 0.0 MB where `shutil.copy2` costs 256.9 MB.
    """
    from .fsclone import clone_or_copy
    from .image_plugin import load as _image_load
    source_directory = _image_load("image_forensics.source_staging").source_directory

    paper = Path(paper).resolve()
    root = project_root(paper)
    archive = Archive(root)
    execution_id = execution_id or os.environ.get("METASCIENCE_EXECUTION_ID")
    if execution_id and read(archive.base / "executions" / f"{identifier(execution_id)}.json"):
        eid = execution_id
    else:
        eid = archive.execution(
            component,
            components=[component],
            configuration=configuration,
            provenance=provenance(component),
        )["id"]
    rel = paper.relative_to(root).as_posix()
    run = archive.start(
        eid, component, rel, provenance=provenance(component, parameters=configuration or {})
    )
    target = archive.base / "work" / run["id"] / paper.name
    target.mkdir(parents=True)
    try:
        if on_start is not None:
            # Before the copy-in: a producer killed while staging still left
            # its run id where its parent can find and seal it.
            on_start(archive, run, target)
        # Copy source and existing extraction inputs. Avoid recursive run/review archives.
        for child in paper.iterdir():
            if child.name.startswith(
                (".", "forensic_review", "image_duplication")
            ) or child.name in {"panels", "figures"}:
                continue
            if child.is_file():
                clone_or_copy(child, target / child.name)
            elif child.is_dir() and source_directory(child.name):
                shutil.copytree(child, target / child.name, copy_function=clone_or_copy)
        yield archive, run, target
    except BaseException as exc:
        if not (archive.base / "runs" / f"{run['id']}.json").exists():
            if "failure_progress" not in run:
                run["failure_progress"] = failure_progress(target)
            archive.seal(
                run,
                status="cancelled"
                if type(exc).__name__ in {"CancelledError", "KeyboardInterrupt"}
                else "failed",
                detail=f"{type(exc).__name__}: {exc}",
                completed_at=now(),
            )
        raise
    else:
        # Success only -- `else` rather than `finally`, so the failure path above
        # keeps its tree. Best-effort: a workspace that cannot be removed is a
        # disk-space problem, never a reason to fail a run whose evidence is
        # already sealed into objects/ and published to the paper directory.
        if not os.environ.get("METASCIENCE_KEEP_WORKSPACE"):
            shutil.rmtree(archive.base / "work" / run["id"], ignore_errors=True)


def capture_images(
    paper, *, archive=None, run=None, source=None, execution_id=None, verified=False
):
    from .image_plugin import load as _image_load
    _within_items = _image_load("image_review")._within_items

    paper = Path(paper).resolve()
    archive = archive or Archive(project_root(paper))
    rel = paper.relative_to(archive.root).as_posix()
    source = Path(source or paper)
    if run is None:
        execution = archive.execution(
            "image_forensics",
            components=["image_forensics"],
            execution_id=execution_id,
            provenance=provenance("image_forensics"),
        )
        run = archive.start(
            execution["id"], "image_forensics", rel, provenance=provenance("image_forensics")
        )
    started = time.monotonic()
    last = [None, 0.0]
    def progress(stage, **counts):
        tick = time.monotonic()
        if stage != last[0] or tick - last[1] >= 5:
            atomic_write_text(source / "archive_progress.json", json.dumps({
                "run_id": run["id"], "pid": os.getpid(), "stage": stage,
                "updated_at": now(), "elapsed_s": tick - started, **counts}))
            last[:] = [stage, tick]
    progress("loading_items")
    if source == paper:
        items = _within_items(paper, False, [], archive.root)
    else:
        items = _within_items(source, True, [])
        for it in items:
            it["id"] = f"within:{rel}:{it['source_id']}"
            for p in [it["paper"], *it["papers"]]:
                p["dir"] = rel
            for p in it["panels"]:
                p["paper_dir"] = rel
            for t in it["targets"]:
                t["paper_dir"] = rel
    # Attach saved screening without replacing the original adjudication.
    ledger = read(archive.root / ".image_track/ai_screening.json", {"items": {}})
    for it in items:
        rec = ledger.get("items", {}).get(it["id"])
        if rec:
            from .image_plugin import load as _image_load
            _m = _image_load("image_forensics.screening")
            input_stamp, policy_for = _m.input_stamp, _m.policy_for

            if (source == paper and rec.get("policy") == policy_for(it)
                    and rec.get("inputs_stamp") == input_stamp(archive.root, it)):
                it["screening"] = rec
    frozen, artifacts = archive.freeze_items(run, items, sources={rel: source}, verified=verified,
                                             copy_items=False, progress=progress)
    st = read(source / "panels/image_track_status.json", {})
    result = read(source / "image_duplication_findings.json")
    # One authority for which outcomes are failures (`code_changed` was
    # missing from the copy that lived here).
    from .image_plugin import load as _image_load
    TRACK_FAILURES = _image_load("image_forensics.retain").TRACK_FAILURES
    failure = st.get("refusal_subtype") in TRACK_FAILURES
    state = (
        "failed"
        if failure or (result or {}).get("error")
        else "incomplete"
        if st.get("truncated_by_budget")
        else "completed"
        if result is not None
        else "refused"
        if st
        else "unavailable"
    )
    progress("sealing", total=len(frozen), artifacts=len(artifacts))
    saved = archive.seal(
        run,
        frozen,
        artifacts=artifacts,
        status=state,
        detail=str(st.get("detail") or ""),
        completed_at=now(),
    )
    progress("completed", total=len(frozen), artifacts=len(artifacts), status=state)
    return saved
