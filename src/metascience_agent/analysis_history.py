"""Import, inspect, and serve preserved component runs. Never runs an analysis."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from .analysis_runs import Archive, digest, identifier, now, read


def _legacy_execution(archive, sweep_id, stamp, *, started_at=None, name=None):
    eid = "legacy_" + digest([str(archive.root), sweep_id])[:24]
    return archive.execution(
        "image_forensics",
        execution_id=eid,
        name=name or sweep_id,
        components=["image_forensics"],
        started_at=started_at,
        configuration=stamp.get("flags", {}),
        status="completed",
        provenance={
            "version": (stamp.get("detector") or {}).get("release"),
            "detector_fingerprint": (stamp.get("detector") or {}).get("fingerprint"),
        },
    )


def import_history(root, *, dry_run=False):
    from .webapp_index import iter_paper_dirs
    from .image_plugin import load as _image_load
    _m = _image_load("image_review")
    _within_items, _cross_items, read_ledger = _m._within_items, _m._cross_items, _m.read_ledger

    archive = Archive(root)
    dirs = iter_paper_dirs(archive.root)
    report = {
        "papers_inspected": len(dirs),
        "imported": 0,
        "existing": 0,
        "unavailable": 0,
        "items": 0,
        "errors": [],
        "executions": [],
    }
    executions = {}
    expected = {}
    for path in sorted(archive.root.glob(".image_track/sweeps/*/sweep.json")):
        try:
            meta = read(path)
            sid = meta.get("sweep_id") or path.parent.name
            stamp = meta.get("stamp", {})
            eid = "legacy_" + digest([str(archive.root), sid])[:24]
            executions[sid] = {"id": eid, "stamp": stamp, "started_at": meta.get("started_at")}
            report["executions"].append(
                {"name": sid, "id": eid, "version": stamp.get("detector", {}).get("release")}
            )
            if not dry_run:
                _legacy_execution(archive, sid, stamp, started_at=meta.get("started_at"))
            manifest = path.parent / "manifest.jsonl"
            if manifest.exists():
                # Resume/appended manifests contain several attempts: last paper entry wins.
                for line in manifest.read_text().splitlines():
                    row = json.loads(line)
                    rel = row.get("rel_dir") or row.get("paper")
                    if rel:
                        expected[(eid, rel)] = row
        except Exception as exc:
            report["errors"].append(f"{path}: {type(exc).__name__}: {exc}")
    recovered = set()
    for paper in dirs:
        rel = paper.relative_to(archive.root).as_posix()
        path = paper / "image_duplication_findings.json"
        status = paper / "panels/image_track_status.json"
        if not path.exists() and not status.exists():
            continue
        try:
            result = read(path, {})
            st = read(status, {})
            stamp = (result.get("sweep") or {}) if path.exists() else (st.get("sweep") or {})
            sid = stamp.get("sweep_id") or "legacy-unassigned"
            eid = "legacy_" + digest([str(archive.root), sid])[:24]
            rid = "legacy_run_" + digest([rel, result, st])[:24]
            recovered.add((eid, rel))
            if (archive.base / "runs" / f"{rid}.json").exists():
                report["existing"] += 1
                continue
            if dry_run:
                report["imported"] += 1
                report["items"] += len(result.get("duplicate_groups", []))
                continue
            if sid not in executions:
                _legacy_execution(archive, sid, stamp)
            version = stamp.get("detector", {}).get("release")
            run = {
                "id": rid,
                "execution_id": eid,
                "component": "image_forensics",
                "paper": rel,
                "schema_version": 1,
                "started_at": stamp.get("completed_at"),
                "provenance": {
                    "version": version,
                    "detector_fingerprint": stamp.get("detector", {}).get("fingerprint"),
                    "parameters": stamp.get("flags", {}),
                    "input_digest": stamp.get("inputs_digest"),
                    "imported": True,
                    "original_stamp": stamp,
                },
            }
            items = _within_items(paper, False, [], archive.root) if result else []
            # Preserve old unscoped decisions as context only.
            for item in items:
                if item.get("decision"):
                    item["legacy_decision_context"] = item["decision"]
            frozen, artifacts = archive.freeze_items(run, items)
            state = (
                "completed"
                if path.exists()
                else "refused"
                if st.get("refusal_subtype")
                else "failed"
            )
            archive.seal(
                run,
                frozen,
                artifacts=artifacts,
                status=state,
                completed_at=stamp.get("completed_at"),
                detail="Historical media captured at import; original bytes were not independently verified.",
            )
            report["imported"] += 1
            report["items"] += len(items)
        except Exception as exc:
            report["errors"].append(f"{rel}: {type(exc).__name__}: {exc}")
    for (eid, rel), row in expected.items():
        if (eid, rel) in recovered:
            continue
        rid = "missing_" + digest([eid, rel, row])[:24]
        report["unavailable"] += 1
        if dry_run or (archive.base / "runs" / f"{rid}.json").exists():
            continue
        sw = row.get("stamp") or {}
        run = {
            "id": rid,
            "execution_id": eid,
            "component": "image_forensics",
            "paper": rel,
            "schema_version": 1,
            "started_at": sw.get("completed_at"),
            "provenance": {
                "version": sw.get("detector", {}).get("release"),
                "manifest_record": row,
            },
        }
        archive.seal(
            run,
            status="unavailable",
            completed_at=sw.get("completed_at"),
            detail="The sweep manifest survives, but the corresponding detailed output is unavailable. Newer results were not substituted.",
        )
    if not dry_run:
        try:
            cross = _cross_items(dirs, False, read_ledger(archive.root), [], archive.root)
            if cross:
                eid = "legacy_cross_" + digest(cross)[:24]
                rid = eid + "_run"
                if not (archive.base / "runs" / f"{rid}.json").exists():
                    archive.execution(
                        "image_forensics",
                        execution_id=eid,
                        name="Legacy cross-paper matches",
                        components=["image_forensics"],
                        status="completed",
                    )
                    run = {
                        "id": rid,
                        "execution_id": eid,
                        "component": "image_forensics",
                        "paper": None,
                        "schema_version": 1,
                        "scope_key": "cross",
                        "started_at": None,
                        "provenance": {"version": None},
                    }
                    frozen, artifacts = archive.freeze_items(run, cross)
                    archive.seal(
                        run,
                        frozen,
                        artifacts=artifacts,
                        detail="Historical cross-paper provenance is incomplete.",
                    )
                    report["items"] += len(cross)
                    report["imported"] += 1
        except Exception as exc:
            report["errors"].append(f"cross-paper import: {exc}")
        import_reports(archive, dirs, report)
        import_image_snapshots(archive, dirs, report)
        import_partial_logs(archive, report)
        import_tool_results(archive, dirs, report)
    copy_outputs = []
    for folder in [archive.root, *dirs]:
        for path in folder.glob("*.json"):
            try:
                payload = read(path)
                candidate = payload.get("result", payload) if isinstance(payload, dict) else {}
                if (
                    isinstance(candidate, dict)
                    and "duplicate_groups" in candidate
                    and any(
                        key in candidate
                        for key in ("n_row_pairs", "n_row_pair_groups", "n_rows_implicated")
                    )
                ):
                    copy_outputs.append((folder, path, candidate))
            except (ValueError, OSError):
                continue  # Unrelated JSON is not evidence of a copy/paste run.
    report["copy_outputs_found"] = len(copy_outputs)
    if not dry_run:
        for folder, path, candidate in copy_outputs:
            owner = (
                folder
                if folder in dirs
                else next(
                    (
                        paper
                        for paper in dirs
                        if candidate.get("path")
                        and Path(candidate["path"]).resolve().is_relative_to(paper)
                    ),
                    None,
                )
            )
            if owner is None:
                report["errors"].append(
                    f"{path}: copy/paste output has no recorded paper association; use history-import-copy --paper"
                )
                continue
            try:
                saved = import_copy(archive.root, owner, path)
                report["existing" if saved.get("existing") else "imported"] += 1
            except Exception as exc:
                report["errors"].append(f"{path}: {exc}")
    report["inventory"] = {
        "report_documents": sum(
            len(list(p.glob("forensic_review*/findings.v2.json"))) for p in dirs
        ),
        "screening_history_documents": sum(
            len(list(p.glob(".image_screening_history/**/*.json"))) for p in dirs
        ),
        "tool_ledgers": sum(len(list(p.glob("forensic_review*/toolcalls*.json"))) for p in dirs),
        "partial_log_files": len(list(archive.root.glob(".image_track/*.jsonl"))),
    }
    report["dry_run"] = dry_run
    return report


def import_reports(archive, dirs, report):
    """Full review archives and audit originals retain recorded run IDs and versions."""
    for paper in dirs:
        rel = paper.relative_to(archive.root).as_posix()
        paths = list(paper.glob("forensic_review*/findings.v2.json"))
        paths += list(paper.glob(".image_screening_history/**/findings.v2.json"))
        # Preserved pre-projection documents precede their mutable projections.
        paths.sort(key=lambda p: (".image_screening_history" not in p.parts, str(p)))
        for path in paths:
            try:
                doc = read(path)
                meta = read(path.parent / "run_meta.json", {})
                image_history = (
                    path.parent.name == "forensic_review_image"
                    and ".image_screening_history" in path.parts
                )
                if path.parent.name == "forensic_review_image" and not image_history:
                    continue  # Detailed image candidates are imported above, not duplicated from capped v2.
                original = doc.get("run_id")
                rid = original or "legacy_report_" + digest([rel, doc])[:24]
                revision_of = None
                if (archive.base / "runs" / f"{identifier(rid)}.json").exists():
                    previous = archive.run(rid)
                    previous_doc = previous.get("document")
                    if previous_doc is None and "findings" in previous["artifacts"]:
                        previous_doc = read(archive.artifact(rid, "findings")[0])
                    if previous_doc == doc:
                        continue
                    revision_of = rid
                    rid = f"{rid}_rev_{digest(doc)[:16]}"
                    if (archive.base / "runs" / f"{identifier(rid)}.json").exists():
                        continue
                component = "image_forensics" if image_history else "comprehensive"
                eid = "report_" + digest([rel, rid])[:24]
                archive.execution(
                    component,
                    execution_id=eid,
                    name=path.parent.name
                    + (" preserved screening history" if image_history else ""),
                    components=[component],
                    started_at=meta.get("analysed_at"),
                    status="completed",
                )
                run = {
                    "id": rid,
                    "execution_id": eid,
                    "component": component,
                    "paper": rel,
                    "started_at": meta.get("analysed_at"),
                    "schema_version": 1,
                    "revision_of": revision_of,
                    "document": doc,
                    "provenance": {
                        "version": meta.get("version")
                        or doc.get("legacy", {}).get("pipeline_version"),
                        "original_meta": meta,
                        "imported": True,
                    },
                }
                arts = {"findings": {**archive.object(path), "role": "report", "paper": rel}}
                if (path.parent / "run_meta.json").exists():
                    arts["metadata"] = {
                        **archive.object(path.parent / "run_meta.json"),
                        "role": "metadata",
                        "paper": rel,
                    }
                items = []
                if image_history:
                    run["latest_eligible"] = False
                    for n, finding in enumerate(doc.get("findings", [])):
                        head = {"dir": rel}
                        items.append(
                            {
                                "id": f"within:{rel}:{finding.get('finding_id') or n}",
                                "source_id": finding.get("finding_id"),
                                "run_id": rid,
                                "execution_id": eid,
                                "provenance": run["provenance"],
                                "paper": head,
                                "papers": [head],
                                "kind": "within",
                                "panels": [],
                                "targets": [],
                                "figure_labels": [],
                                "detector_kind": finding.get("technique", "unknown"),
                                "sentence": finding.get("description", ""),
                                "measurements": {},
                                "rank": {"score": 0},
                                "cleared": finding.get("outcome") != "problem",
                                "adjudication": finding.get("adjudication"),
                                "recorded_fields": finding,
                                "evidence_source": "partial_report",
                            }
                        )
                archive.seal(
                    run,
                    items,
                    artifacts=arts,
                    completed_at=meta.get("analysed_at"),
                    detail="Preserved report; historical source media was not retained with this document.",
                )
                report["imported"] += 1
            except Exception as exc:
                report["errors"].append(f"{path}: {exc}")


def import_image_snapshots(archive, dirs, report):
    """Recover retained detector documents without borrowing current panel bytes."""
    import tempfile
    from .image_plugin import load as _image_load
    _within_items = _image_load("image_review")._within_items

    for paper in dirs:
        rel = paper.relative_to(archive.root).as_posix()
        for path in paper.glob(".image_screening_history/**/image_duplication_findings.json"):
            try:
                document = read(path)
                rid = "image_original_" + digest([rel, document])[:24]
                if (archive.base / "runs" / f"{rid}.json").exists():
                    continue
                stamp = document.get("sweep") or {}
                eid = "screening_original_" + digest([stamp, path.parent.name])[:24]
                archive.execution(
                    "image_forensics",
                    execution_id=eid,
                    name="Preserved detector output before screening",
                    components=["image_forensics"],
                    status="incomplete",
                    started_at=stamp.get("completed_at"),
                )
                run = {
                    "id": rid,
                    "execution_id": eid,
                    "component": "image_forensics",
                    "paper": rel,
                    "started_at": stamp.get("completed_at"),
                    "latest_eligible": False,
                    "provenance": {
                        "version": stamp.get("detector", {}).get("release"),
                        "original_stamp": stamp,
                        "imported": True,
                    },
                }
                with tempfile.TemporaryDirectory() as temporary:
                    source = Path(temporary)
                    (source / "image_duplication_findings.json").write_text(json.dumps(document))
                    items = _within_items(source, False, [])
                    for item in items:
                        item["id"] = f"within:{rel}:{item['source_id']}"
                        for head in [item["paper"], *item["papers"]]:
                            head["dir"] = rel
                        for panel in item["panels"]:
                            panel["paper_dir"] = rel
                        for target in item["targets"]:
                            target["paper_dir"] = rel
                    items, artifacts = archive.freeze_items(run, items, sources={rel: source})
                archive.seal(
                    run,
                    items,
                    artifacts=artifacts,
                    status="incomplete",
                    completed_at=stamp.get("completed_at"),
                    detail="Saved detector fields and judgments; historical panel media was not retained with this snapshot.",
                )
                report["imported"] += 1
            except Exception as exc:
                report["errors"].append(f"{path}: {exc}")


def import_partial_logs(archive, report):
    """Old compact detector logs are evidence records, not reconstructed full runs."""
    from .webapp_index import iter_paper_dirs

    names = {}
    for p in iter_paper_dirs(archive.root):
        names.setdefault(p.name, []).append(p.relative_to(archive.root).as_posix())
    for path in sorted(archive.root.glob(".image_track/*.jsonl")):
        rows = {}
        try:
            for line in path.read_text().splitlines():
                row = json.loads(line)
                if isinstance(row.get("groups"), list) and row.get("paper"):
                    rows[str(row["paper"])] = row
            if not rows:
                continue
            eid = "log_" + digest([path.name, rows])[:24]
            archive.execution(
                "image_forensics",
                execution_id=eid,
                name=path.name + " (partial log)",
                components=["image_forensics"],
                status="incomplete",
            )
            for paper, row in rows.items():
                # Logs may use absolute paths; retain the recorded scope safely.
                p = Path(paper)
                if p.is_absolute():
                    if not p.resolve().is_relative_to(archive.root):
                        continue
                    paper = p.resolve().relative_to(archive.root).as_posix()
                if ".." in Path(paper).parts:
                    continue
                matches = names.get(Path(paper).name, [])
                if not (archive.root / paper).is_dir() and len(matches) == 1:
                    paper = matches[0]
                rid = "log_run_" + digest([eid, paper, row])[:24]
                if (archive.base / "runs" / f"{rid}.json").exists():
                    continue
                items = []
                for i, g in enumerate(row["groups"]):
                    if not isinstance(g, dict):
                        continue
                    heads = [{"dir": paper}]
                    items.append(
                        {
                            "id": f"within:{paper}:LOG-{i + 1}",
                            "source_id": f"LOG-{i + 1}",
                            "kind": "within",
                            "paper": heads[0],
                            "papers": heads,
                            "panels": [
                                {
                                    "uid": uid,
                                    "paper_dir": paper,
                                    "image": None,
                                    "placements": [],
                                    "figure_label": None,
                                    "caption": None,
                                    "image_unavailable_reason": "This partial log did not retain verifiable panel images.",
                                }
                                for uid in g.get("panel_ids", [])
                            ],
                            "targets": [],
                            "detector_kind": g.get("kind", "unknown"),
                            "sentence": g.get("sentence", ""),
                            "figure_labels": g.get("figure_labels", []),
                            "measurements": {},
                            "rank": {"score": 0, "reasons": ["partial historical log"]},
                            "cleared": g.get("duplication_evidence") is False,
                            "adjudication": g.get("adjudication"),
                            "recorded_fields": g,
                            "run_id": rid,
                            "execution_id": eid,
                            "provenance": {"version": None},
                            "evidence_source": "partial_log",
                        }
                    )
                run = {
                    "id": rid,
                    "execution_id": eid,
                    "component": "image_forensics",
                    "paper": paper,
                    "started_at": None,
                    "provenance": {"version": None, "original_record": row},
                    "latest_eligible": (archive.root / paper).is_dir(),
                }
                archive.seal(
                    run,
                    items,
                    status="incomplete",
                    detail="Partial detector log; only recorded fields are available. Version, date, and original media were not recorded.",
                )
                report["imported"] += 1
        except Exception as exc:
            report["errors"].append(f"{path}: {exc}")


def import_tool_results(archive, dirs, report):
    for paper in dirs:
        for path in sorted(paper.glob("forensic_review*/toolcalls*.json")):
            try:
                rows = read(path, [])
                if isinstance(rows, dict):
                    rows = rows.get("calls", [])
                for row in rows:
                    if not isinstance(row, dict) or "detect_raw_duplication" not in str(
                        row.get("tool_short") or row.get("tool") or row.get("name")
                    ):
                        continue
                    result = row.get("result")
                    if isinstance(result, str):
                        try:
                            result = json.loads(result)
                        except ValueError:
                            result = {
                                "error": "Saved tool output was truncated or unparseable",
                                "original_text": result,
                            }
                    if not isinstance(result, dict):
                        continue
                    rid = "tool_copy_" + digest([str(path.relative_to(archive.root)), row])[:24]
                    if (archive.base / "runs" / f"{rid}.json").exists():
                        continue
                    meta = read(path.parent / "run_meta.json", {})
                    report_doc = read(path.parent / "findings.v2.json", {})
                    parent_uid = report_doc.get("run_id") or meta.get("run_id")
                    parent = (
                        read(archive.base / "runs" / f"{identifier(parent_uid)}.json")
                        if parent_uid
                        else None
                    )
                    if parent:
                        eid = parent["execution_id"]
                    else:
                        eid = (
                            "tool_import_" + digest(str(path.parent.relative_to(archive.root)))[:24]
                        )
                        archive.execution(
                            "comprehensive",
                            execution_id=eid,
                            name=path.parent.name,
                            components=["copy_paste"],
                            status="completed",
                        )
                    run = {
                        "id": rid,
                        "execution_id": eid,
                        "component": "copy_paste",
                        "paper": paper.relative_to(archive.root).as_posix(),
                        "started_at": meta.get("analysed_at"),
                        "parent_run_id": parent_uid if parent else None,
                        "provenance": {
                            "version": None,
                            "parent_version": meta.get("version"),
                            "tool_record": row,
                            "imported": True,
                        },
                    }
                    capture_copy(
                        archive.root,
                        paper,
                        result,
                        result.get("path"),
                        run=run,
                        completed_at=meta.get("analysed_at"),
                    )
                    report["imported"] += 1
            except Exception as exc:
                report["errors"].append(f"{path}: {exc}")


def copy_items(paper_rel, result, input_name, highlight=None):
    head = {"dir": paper_rel, "title": Path(input_name).name}
    return [
        {
            "id": f"copy:{paper_rel}:{digest([input_name, g])[:24]}",
            "kind": "within",
            "source_id": f"COPY-{i + 1}",
            "paper": head,
            "papers": [head],
            "detector_kind": g.get("kind", "copy_paste"),
            "sentence": g.get("sentence") or result.get("explanation", ""),
            "group": g,
            "result_counts": {
                k: result.get(k)
                for k in (
                    "n_row_pair_groups",
                    "n_row_pairs",
                    "n_rows_implicated",
                    "n_rows_total",
                    "n_duplicate_groups",
                )
            },
            "input_file": input_name,
            "highlight_file": highlight,
            "panels": [],
            "targets": [],
            "figure_labels": [],
            "measurements": {},
            "rank": {"score": g.get("adjusted_score", 0), "reasons": []},
            "cleared": False,
            "adjudication": None,
        }
        for i, g in enumerate(result.get("duplicate_groups", []))
    ]


def capture_copy(
    root,
    paper,
    result,
    input_path,
    *,
    parameters=None,
    execution_id=None,
    parent_run_id=None,
    run=None,
    version=None,
    highlight=None,
    completed_at="now",
):
    archive = Archive(root)
    paper = Path(paper).resolve()
    rel = paper.relative_to(archive.root).as_posix()
    if run is None:
        execution = archive.execution(
            "copy_paste",
            execution_id=execution_id,
            components=["copy_paste"],
            configuration=parameters,
            provenance={"version": version},
        )
        run = archive.start(
            execution["id"],
            "copy_paste",
            rel,
            parent_run_id=parent_run_id,
            provenance={"version": version, "parameters": parameters or {}},
        )
    input_path = Path(input_path).resolve() if input_path else None
    # Archive external standalone inputs explicitly; no arbitrary project-relative traversal.
    aid = "input"
    art = archive.object(input_path) if input_path and input_path.is_file() else None
    items = copy_items(rel, result, str(input_path or "input unavailable"))
    for it in items:
        it.update(
            run_id=run["id"],
            execution_id=run["execution_id"],
            provenance=run["provenance"],
            input_file=f"__runs/{run['id']}/{aid}" if art else None,
            evidence_key=digest([art and art["sha256"], it["group"]]),
            evidence_source="captured_at_import"
            if run["provenance"].get("imported")
            else "producer",
        )
    arts = {aid: {**art, "role": "input_file", "paper": rel}} if art else {}
    if highlight and Path(highlight).exists():
        arts["highlight"] = {**archive.object(highlight), "role": "highlight_file", "paper": rel}
        for it in items:
            it["highlight_file"] = f"__runs/{run['id']}/highlight"
    run["raw_result"] = result
    return archive.seal(
        run,
        items,
        artifacts=arts,
        status="failed" if result.get("error") else "completed" if art else "incomplete",
        detail=str(result.get("error") or ("Input evidence unavailable" if not art else "")),
        completed_at=now() if completed_at == "now" else completed_at,
    )


def import_copy(root, paper, source):
    import hashlib

    source = Path(source).resolve()
    archive = Archive(root)
    meta = read(source / "manifest.json") if source.is_dir() else None
    if meta and meta.get("schema_version") == 2 and meta.get("component") == "copy_paste":
        return _import_copy_batch(root, paper, source, meta)
    if meta:

        def checked(entry):
            path = (source / entry["path"]).resolve()
            if not path.is_relative_to(source):
                raise ValueError("portable artifact escapes its directory")
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("portable artifact hash mismatch")
            return path

        input_path = checked(meta["artifacts"]["input"]) if meta["artifacts"].get("input") else None
        highlight = (
            checked(meta["artifacts"]["highlight"]) if meta["artifacts"].get("highlight") else None
        )
        result_path = (source / meta["result"]).resolve()
        if not result_path.is_relative_to(source):
            raise ValueError("portable result outside run")
        if (
            meta.get("result_sha256")
            and hashlib.sha256(result_path.read_bytes()).hexdigest() != meta["result_sha256"]
        ):
            raise ValueError("portable result hash mismatch")
        result = read(result_path)
        rid = identifier(meta["id"])
    else:
        envelope = read(source)
        result = envelope.get("result", envelope)
        input_path = Path(result["path"]) if result.get("path") else None
        if input_path and not input_path.is_absolute():
            input_path = source.parent / input_path
        highlight = None
        rid = identifier(
            envelope.get("run_id")
            or result.get("run_id")
            or "legacy_copy_" + digest([str(Path(paper).resolve()), result])[:24]
        )
        meta = envelope.get("provenance") or {}
    existing = read(archive.base / "runs" / f"{rid}.json")
    if existing:
        if existing.get("raw_result") != result:
            raise ValueError("import conflicts with a sealed run")
        return {"existing": True, "run_id": rid}
    eid = "copy_import_" + digest(rid)[:24]
    archive.execution(
        "copy_paste",
        execution_id=eid,
        name="Imported copy/paste run",
        components=["copy_paste"],
        started_at=meta.get("started_at"),
        configuration=meta.get("parameters"),
        provenance={"version": meta.get("version")},
        status="completed",
    )
    run = {
        "id": rid,
        "execution_id": eid,
        "component": "copy_paste",
        "paper": Path(paper).resolve().relative_to(archive.root).as_posix(),
        "started_at": meta.get("started_at"),
        "provenance": {
            "version": meta.get("version"),
            "parameters": meta.get("parameters", {}),
            "imported": True,
        },
    }
    return capture_copy(
        root,
        paper,
        result,
        input_path,
        run=run,
        highlight=highlight,
        completed_at=meta.get("completed_at"),
    )


def _import_copy_batch(root, paper, source, meta):
    """Import standalone paper-level runs with every source and AI judgment."""
    import hashlib

    state = "incomplete" if meta["status"] == "partial" else meta["status"]
    source = Path(source).resolve()
    archive = Archive(root)
    rid = identifier(meta["id"])
    verified = {}
    for name, entry in {**meta["artifacts"], **meta["source_artifacts"]}.items():
        path = (source / entry["path"]).resolve()
        if not path.is_relative_to(source) or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("portable artifact path or hash mismatch")
        verified[name] = path
    result = read(verified["result.json"])
    judgment = read(verified["adjudication.json"])
    existing = read(archive.base / "runs" / f"{rid}.json")
    if existing:
        if existing.get("raw_result") != result or existing.get("copy_adjudication") != judgment:
            raise ValueError("import conflicts with a sealed run")
        return {"existing": True, "run_id": rid}
    eid = "copy_import_" + digest(rid)[:24]
    provenance = {**meta.get("configuration", {}), "version": meta.get("version"), "imported": True}
    archive.execution("copy_paste", execution_id=eid, components=["copy_paste"],
                      name="Imported standalone copy/paste batch", configuration=meta.get("configuration"),
                      started_at=meta.get("started_at"), provenance=provenance, status=state)
    rel = Path(paper).resolve().relative_to(archive.root).as_posix()
    run = {"id": rid, "execution_id": eid, "component": "copy_paste", "paper": rel,
           "started_at": meta.get("started_at"), "provenance": provenance,
           "raw_result": result, "copy_adjudication": judgment}
    artifacts, input_files = {}, {}
    for index, (name, path) in enumerate(sorted(verified.items())):
        aid = f"source-{index}"
        artifacts[aid] = {**archive.object(path), "role": "input_file" if name in meta["source_artifacts"] else "review_artifact", "paper": rel}
        input_files[name] = f"__runs/{rid}/{aid}"
    items = copy_items(rel, result, meta["paper_id"])
    decisions = {d["candidate_id"]: d for d in judgment.get("decisions", [])}
    for item in items:
        group = item["group"]
        references = group.get("cells", []) + group.get("cells_a", []) + group.get("cells_b", [])
        names = sorted({r["file"] for r in references if r.get("file")})
        item.update(run_id=rid, execution_id=eid, provenance=provenance,
                    source_id=group["id"], evidence_key=digest(group), evidence_source="captured_at_import",
                    input_file=input_files.get(names[0]) if names else None,
                    input_files=[{"name": n, "path": input_files[n]} for n in names if n in input_files],
                    copy_judgment=decisions.get(group["id"]), coverage=result.get("coverage"),
                    ai_status=judgment.get("status"), review_file=input_files.get("review.html"))
    return archive.seal(run, items, artifacts=artifacts, status=state,
                        detail=str(result.get("error", "")), completed_at=meta.get("completed_at"))


def report_view(paper, selection=None):
    """Serve a preserved report and its own source; never join today's tracks."""
    from .analysis_runs import project_root
    from .review_issues import _v2_issues_from_doc, sort_issues
    from .review_io import load_review

    paper = Path(paper).resolve()
    archive = Archive(project_root(paper))
    rel = paper.relative_to(archive.root).as_posix()
    runs = [
        run_record
        for run_record in read(archive.base / "index.json", {"runs": {}})["runs"].values()
        if run_record.get("component") == "comprehensive" and run_record.get("paper") == rel
    ]
    runs.sort(
        key=lambda run_record: (
            run_record.get("completed_at") or run_record.get("started_at") or "",
            run_record["id"],
        ),
        reverse=True,
    )
    options = [
        {
            "id": run_record["id"],
            "label": f"v{run_record.get('provenance', {}).get('version') or 'unknown'} · {run_record.get('started_at') or 'date unknown'} · {run_record['id']}",
        }
        for run_record in runs
    ]
    chosen_execution = (
        read(archive.base / "executions" / f"{identifier(selection)}.json")
        if selection and selection != "latest"
        else None
    )
    if chosen_execution and not any(metadata["execution_id"] == selection for metadata in runs):
        return {
            "paper_dir": str(paper),
            "latest_run": None,
            "available_runs": [selection, *[metadata["id"] for metadata in runs]],
            "run_options": [
                {"id": selection, "label": chosen_execution["name"] + " · no comprehensive report"},
                *options,
            ],
            "n_runs": len(runs),
            "headline": {},
            "issues": [],
            "review": load_review(paper),
            "bundle": None,
            "source": {
                "kind": "archive",
                "execution_id": selection,
                "database": None,
                "status": "not_requested",
                "detail": "This execution has no comprehensive report for this paper. No other run's findings were substituted.",
            },
            "archived_article": {
                "mode": "none",
                "pdf_relpath": None,
                "warning": "No comprehensive report source in this selection.",
            },
        }
    if not runs:
        return None
    picked = next(
        (
            run_record
            for run_record in runs
            if selection in (run_record["id"], run_record["execution_id"])
        ),
        None,
    )
    if selection and selection != "latest" and picked is None:
        # Legacy directory URLs remain supported by the existing reader.
        if (paper / selection).is_dir():
            return None
        raise ValueError("This report run is not recorded for the selected paper")
    saved = archive.run((picked or runs[0])["id"])
    doc = saved.get("document")
    if doc is None and "findings" in saved["artifacts"]:
        doc = read(archive.artifact(saved["id"], "findings")[0])
    issues, headline, _ = (
        _v2_issues_from_doc(doc, saved["id"], include_tracks=True) if doc else ([], {}, None)
    )
    # Only a source recorded in this manifest can be shown beside old findings.
    pdfs = [
        (aid, a)
        for aid, a in saved["artifacts"].items()
        if a.get("name", "").lower().endswith(".pdf") and a.get("role") in {"source", "source_pdf"}
    ]
    pdfs.sort(key=lambda pair: ("supp" in pair[1]["name"].lower(), pair[1]["name"]))
    pdf = f"__runs/{saved['id']}/{pdfs[0][0]}" if pdfs else None
    components = []
    for metadata in read(archive.base / "index.json", {"runs": {}})["runs"].values():
        if metadata.get("parent_run_id") in {saved["id"], saved.get("revision_of")} - {None}:
            child = archive.run(metadata["id"])
            stage = child.get("stage_output") or {}
            components.append(
                {
                    "run_id": child["id"],
                    "component": child["component"],
                    "status": child["status"],
                    "provenance": child.get("provenance"),
                    "error": stage.get("error") or child.get("detail"),
                }
            )
    return {
        "paper_dir": str(paper),
        "latest_run": saved["id"],
        "available_runs": [run_record["id"] for run_record in runs],
        "run_options": options,
        "n_runs": len(runs),
        "headline": headline,
        "issues": sort_issues(issues),
        "review": load_review(paper),
        "bundle": None,
        "source": {
            "kind": "archive",
            "database": None,
            "run_id": saved["id"],
            "execution_id": saved["execution_id"],
            "status": saved["status"],
            "detail": saved.get("detail"),
            "components": components,
        },
        "archived_article": {
            "mode": "pdf" if pdf else "none",
            "pdf_relpath": pdf,
            "warning": "Preserved report source."
            if pdf
            else "The historical source document is unavailable. Current source files have not been substituted.",
        },
    }


def summary(root, rid, item_id):
    from .image_plugin import load as _image_load
    summary_figure = _image_load("image_forensics.review_media").summary_figure
    from .image_plugin import load as _image_load
    review_media = _image_load("image_forensics.review_media")

    archive = Archive(root)
    run = archive.run(rid)
    item = next((copy.deepcopy(i) for i in run["items"] if i["id"] == item_id), None)
    if item is None:
        raise ValueError("item not in selected run")
    for p in item.get("panels", []):
        if not p.get("image"):
            raise ValueError("historical panel unavailable")
        _, owner, aid = p["image"].split("/")
        path, _ = archive.artifact(owner, aid)
        p.update(paper_path=str(path.parent), image=path.name)
    evidence = (
        "original bytes unverified; captured at import"
        if item.get("evidence_source") == "captured_at_import"
        else item.get("evidence_source", "historical provenance unknown")
    )
    item["sentence"] = (
        f"Saved result · run {rid} · v{run['provenance'].get('version') or 'unknown'} · {evidence}. "
        + item.get("sentence", "")
    )
    renderer = digest(
        [
            Path(__file__).read_text(),
            Path(review_media.__file__).read_text(),
        ]
    )
    out = archive.base / "derived" / rid / f"summary_{digest(item_id)[:20]}_{renderer}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    result = summary_figure(item, out, corpus_root=archive.root)
    from .atomicio import atomic_write_text

    atomic_write_text(
        out.with_suffix(".json"),
        json.dumps(
            {
                "run_id": rid,
                "item": item_id,
                "source": run["sealed_digest"],
                "renderer": {"code_sha": renderer},
                "artifact": archive.object(out),
            },
            indent=2,
        ),
    )
    return result


def sheet(root, rid, aid, selected_sheet=None, highlights=None):
    import shutil
    from .finding_files import read_sheet

    archive = Archive(root)
    source, a = archive.artifact(rid, aid)
    named = archive.base / "derived" / rid / aid / Path(a["name"]).name
    named.parent.mkdir(parents=True, exist_ok=True)
    if not named.exists():
        shutil.copyfile(source, named)
    if archive.run(rid).get("component") == "copy_paste" and highlights:
        from copy_paste_detector.review_grid import evidence_grid

        return evidence_grid(named, selected_sheet, highlights)
    return read_sheet(named, selected_sheet, highlights or [])


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=[
            "import",
            "catalog",
            "feed",
            "review",
            "resolve",
            "rebuild",
            "import-copy",
            "summary",
            "sheet",
        ],
    )
    parser.add_argument("root", type=Path)
    parser.add_argument("--run", default="latest")
    parser.add_argument("--component", default="image_forensics")
    parser.add_argument("--item")
    parser.add_argument("--decision")
    parser.add_argument("--reviewer")
    parser.add_argument("--note", default="")
    parser.add_argument("--artifact")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--paper", type=Path)
    parser.add_argument("--sheet")
    parser.add_argument("--highlights", default="[]")
    args = parser.parse_args(argv)
    archive = Archive(args.root)
    try:
        if args.action == "summary":
            result = summary(args.root, args.run, args.item)
        elif args.action == "sheet":
            result = sheet(
                args.root, args.run, args.artifact, args.sheet, json.loads(args.highlights)
            )
        elif args.action == "import":
            result = import_history(args.root, dry_run=args.dry_run)
        elif args.action == "rebuild":
            result = archive.rebuild_index()
        elif args.action == "catalog":
            result = {"runs": archive.catalog(args.component)}
        elif args.action == "feed":
            result = archive.feed(args.run, args.component)
        elif args.action == "review":
            result = archive.decide(args.run, args.item, args.decision, args.reviewer, args.note)
            from .history_db import try_sync

            result["db_mirror"] = [try_sync(args.root, [args.run])]
        elif args.action == "resolve":
            path, artifact = archive.artifact(args.run, args.artifact)
            result = {"path": str(path), **artifact}
        elif args.action == "import-copy":
            result = import_copy(args.root, args.paper, args.file)
        print(json.dumps(result, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
