"""Detection across the structured supplements of ONE paper."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .constants import _CONTEXTS
from .detector import _detect_segments
from .readers import DetectionLimits, _load_segments
from .storage import file_hash

FORMATS = {".csv", ".tsv", ".xlsx", ".xlsm"}


def detect_paper_duplication(
    files, *, paper_id="paper", data_context="unknown", limits=None, max_row_pairs=0
):
    """Files are paths or {path, name?, sheet?, exclude_columns?} objects.

    Batch defaults scan all rows, columns and sheets. External worker timeouts
    bound resource consumption. Original and corrected versions must be separate
    paper records, never files inside one record.
    """
    if data_context not in _CONTEXTS:
        raise ValueError(f"Unknown data_context: {data_context}")
    if isinstance(max_row_pairs, bool) or not isinstance(max_row_pairs, int) or max_row_pairs < 0:
        raise ValueError("max_row_pairs must be nonnegative")
    limits = limits or DetectionLimits(0, 0, 0)
    entries = [dict(f) if isinstance(f, dict) else {"path": str(f)} for f in files]
    names = [f.get("name", Path(f["path"]).name) for f in entries]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate source names: specify unique relative 'name' values")
    sources, segments, caveats, hashes = [], [], [], {}
    for entry, name in sorted(zip(entries, names), key=lambda pair: pair[1]):
        p = Path(entry["path"])
        source = {"file": name, "path": str(p), "status": "pending"}
        sources.append(source)
        if p.suffix.lower() not in FORMATS:
            source.update(status="unsupported", error=f"Deferred/unsupported format {p.suffix}")
            continue
        try:
            sha = file_hash(p)
            source["sha256"] = sha
            if entry.get("expected_digest"):
                if file_hash(p, entry.get("digest_type", "sha256")) != entry["expected_digest"]:
                    source.update(
                        status="checksum_mismatch",
                        error="Bytes do not match the manifest dataset version",
                    )
                    continue
            if sha in hashes:
                source.update(status="duplicate_delivery", duplicate_of=hashes[sha])
                continue
            notes, coverage = [], {}
            loaded = _load_segments(p, entry.get("sheet"), notes, limits=limits, coverage=coverage)
            source["coverage"] = coverage
            if isinstance(loaded, dict):
                source.update(status="not_evaluable", error=loaded["error"])
                continue
            if not loaded:
                source.update(status="not_evaluable", error="No numeric data rows")
                continue
            hashes[sha] = name
            source["status"] = coverage["status"]
            source["n_numeric_cells"] = sum(s.n_numeric for s in loaded)
            for seg in loaded:
                seg.source = {"file": name, "source_sha256": sha}
                seg.exclude_columns = entry.get("exclude_columns", []) or []
                if isinstance(seg.exclude_columns, str):
                    seg.exclude_columns = [seg.exclude_columns]
                if p.suffix.lower() in {".csv", ".tsv"}:
                    seg.sheet = Path(name).name
                    seg.label = seg.label.replace(p.name, Path(name).name, 1)
                original = seg.label
                seg.label = f"{name} :: {original}"
                duplicates = [
                    n
                    for n, count in Counter(x.strip().lower() for x in seg.col_names if x).items()
                    if count > 1
                ]
                if duplicates:
                    notes.append(
                        f"{original}: ambiguous repeated column headers {duplicates}; row matching stays positional within this table"
                    )
            segments.extend(loaded)
            caveats.extend(f"{name}: {n}" for n in notes)
        except (OSError, ValueError, KeyError, EOFError) as exc:
            source.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        except Exception as exc:
            # Corrupt Office containers can raise reader-specific exceptions.
            source.update(status="failed", error=f"Reader {type(exc).__name__}: {exc}")
    result = _detect_segments(segments, Path(paper_id), caveats, [], data_context, max_row_pairs)
    incomplete = [s for s in sources if s["status"] not in {"complete", "duplicate_delivery"}]
    partial_pairs = any("budget" in c and "exhausted" in c for c in caveats)
    status = (
        "not_evaluable"
        if result.get("error")
        else "partial"
        if incomplete or partial_pairs
        else "complete"
    )
    result.update(
        paper_id=paper_id,
        sources=sources,
        coverage={
            "status": status,
            "files_requested": len(entries),
            "files_analyzed": sum(s["status"] in {"complete", "partial"} for s in sources),
            "file_states": dict(Counter(s["status"] for s in sources)),
            "row_pairs_partial": partial_pairs,
        },
    )
    if status != "complete" and "PARTIAL" not in result.get("explanation", ""):
        result["explanation"] = (
            result.get("explanation", "")
            + f" Coverage is {status.upper()}; this is not a complete negative review."
        )

    # Context is kept separately from exact cells. These are source data, never
    # interpreted as instructions. No issue labels or external judgments enter it.
    result["evidence_tables"] = []
    referenced = {}
    for g in result.get("duplicate_groups", []):
        refs = g.get("cells", []) + g.get("cells_a", []) + g.get("cells_b", [])
        g["cross_file"] = len({r.get("file") for r in refs}) > 1
        for ref in refs:
            referenced.setdefault((ref["file"], ref["segment"]), set()).update(
                range(max(1, ref["row"] - 1), ref["row"] + 2)
            )
    for seg in segments:
        key = (seg.source["file"], seg.label)
        if key in referenced:
            result["evidence_tables"].append(
                {
                    "file": key[0],
                    "segment": key[1],
                    "sheet": seg.sheet,
                    "headers": seg.col_names,
                    "rows": [
                        {"row": n, "values": seg.raw[n]}
                        for n in sorted(referenced[key])
                        if n in seg.raw
                    ],
                }
            )
    return result
