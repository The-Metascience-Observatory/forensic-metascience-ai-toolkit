"""Portable run output: stdlib only; the detector remains independent."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def save_run(directory, run_id, started_at, source, result, parameters, highlight=None):
    out = Path(directory) / run_id
    out.mkdir(parents=True, exist_ok=False)
    artifacts = {}
    for role, p in (("input", source), ("highlight", highlight)):
        if p and Path(p).is_file():
            dest = out / f"{role}{Path(p).suffix}"
            shutil.copy2(p, dest)
            artifacts[role] = {
                "path": dest.name,
                "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            }
    from . import __version__ as release

    (out / "result.json").write_text(json.dumps(result, indent=2))
    manifest = {
        "schema_version": 1,
        "id": run_id,
        "component": "copy_paste",
        "version": release,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "parameters": parameters,
        "artifacts": artifacts,
        "result": "result.json",
        "result_sha256": hashlib.sha256((out / "result.json").read_bytes()).hexdigest(),
    }
    # Manifest last: incomplete directories are not importable runs.
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return out
