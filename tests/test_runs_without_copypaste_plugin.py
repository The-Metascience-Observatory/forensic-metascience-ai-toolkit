"""The toolkit runs without the copy-paste detector.

The detector (`copy_paste_detector`) moved to its own repository on
2026-11-06 and is an optional plugin, like the image package. Two checks:

- STATIC: host code reaches the package only through `copypaste_plugin`, so an
  import that would break a detector-less install cannot slip in.
- LIVE: in a fresh interpreter where the package cannot be imported at all,
  every host module imports, the tool stays registered and REFUSES by name,
  the raw_data module reads `unavailable` (not "no duplication"), provenance
  says `not_installed`, and preflight names the missing package.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "forensic_metascience_ai_toolkit"
PACKAGE = "copy_paste_detector"
DOOR = "copypaste_plugin.py"


def test_no_host_module_imports_the_detector():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == DOOR:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level
                     else [])
            offenders += [f"{path.relative_to(SRC)}:{node.lineno} {n}" for n in names
                          if n == PACKAGE or n.startswith(PACKAGE + ".")]
    assert not offenders, (
        "host code must reach the detector through copypaste_plugin.load(), "
        f"so a detector-less install still imports: {offenders}")


_BLOCK = f'''
import sys
class _Block:
    def find_spec(self, name, path=None, target=None):
        if name == "{PACKAGE}" or name.startswith("{PACKAGE}."):
            raise ModuleNotFoundError("blocked: " + name, name=name)
sys.meta_path.insert(0, _Block())
'''


def _run(code: str, tmp_path: Path) -> str:
    env = {**os.environ, "METASCIENCE_BLOCK_COPYPASTE_PLUGIN": "1",
           "PYTHONPATH": os.pathsep.join(filter(None, [str(SRC.parent), os.environ.get("PYTHONPATH", "")]))}
    p = subprocess.run([sys.executable, "-c", _BLOCK + code], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr[-3000:]
    return p.stdout


def test_every_host_module_imports_without_the_detector(tmp_path):
    out = _run('''
import importlib, json, pkgutil
import forensic_metascience_ai_toolkit
failed = []
for m in pkgutil.walk_packages(forensic_metascience_ai_toolkit.__path__, "forensic_metascience_ai_toolkit."):
    if m.name.endswith("__main__"):
        continue
    try:
        importlib.import_module(m.name)
    except SystemExit:
        pass
    except BaseException as exc:
        failed.append(m.name + ": " + type(exc).__name__ + ": " + str(exc)[:200])
print(json.dumps(failed))
''', tmp_path)
    assert json.loads(out.strip().splitlines()[-1]) == []


def test_the_surfaces_refuse_by_name(tmp_path):
    out = _run('''
import asyncio, json
from forensic_metascience_ai_toolkit import copypaste_plugin, modules, registry, preflight
from forensic_metascience_ai_toolkit.analysis_runs import provenance
spec = registry.BY_NAME["detect_raw_duplication"]
refused = spec.fn("data.csv")
module = modules.load("raw_data")
class Ctx:
    paper_dir = "."
result = asyncio.run(module.run(Ctx(), {}))
row = [r for r in preflight.optional_checks() if r[0].startswith("Raw-data duplication")][0]
print(json.dumps({"available": copypaste_plugin.available(), "refused": refused,
                  "record": result.record, "limitations": result.limitations,
                  "version": provenance("copy_paste").get("version"),
                  "preflight": [row[1], row[2]]}))
''', tmp_path)
    got = json.loads(out.strip().splitlines()[-1])
    assert got["available"] is False
    assert got["refused"]["state"] == "copypaste_plugin_unavailable"
    assert got["refused"]["severity"] == "indeterminate"
    assert got["record"]["ran"] is False
    assert got["record"]["execution_status"] == "unavailable"
    assert any("NOT examined" in s for s in got["limitations"])
    assert got["version"] == "not_installed"
    assert got["preflight"][0] is False and "not installed" in got["preflight"][1]
