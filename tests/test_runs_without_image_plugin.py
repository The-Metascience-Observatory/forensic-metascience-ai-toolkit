"""The toolkit runs without the image analysis package.

The image system (`metascience_observatory_image_analysis`) is distributed
separately and privately; the toolkit must install and run without it. Two
checks:

- STATIC: host code reaches the package only through `image_plugin`, so an
  import that would break a plugin-less install cannot slip in.
- LIVE: in a fresh interpreter where the package cannot be imported at all,
  every host module imports, the CLI, the tool registry,
  the MCP tool list and a statistical tool work, and an image surface says
  `unavailable` by name rather than reading as "no image problems".
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "metascience_agent"
PACKAGE = "metascience_observatory_image_analysis"

#: The one file allowed to name the package in code. Host modules do not alias
#: the package's: the forwarding aliases for old import paths were deleted on
#: 2026-10-18 (v1.85.0), not kept.
DOOR = "image_plugin.py"


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC).with_suffix("")
    parts = rel.parts[:-1] if rel.name == "__init__" else rel.parts
    return ".".join(parts)


class TestTheOnlyDoorIsImagePlugin:
    def test_no_host_module_imports_the_image_package(self):
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
            "host code must reach the image package through image_plugin.load(), "
            f"so a plugin-less install still imports: {offenders}")

    def test_no_host_module_names_the_package_by_string(self):
        found = set()
        for path in sorted(SRC.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "import_module"
                        and node.args and isinstance(node.args[0], ast.Constant)
                        and str(node.args[0].value).startswith(PACKAGE)):
                    found.add(_module_name(path))
        assert not found, f"host module(s) importing the image package by string: {sorted(found)}"


_BLOCK = f'''
import sys
class _Block:
    def find_spec(self, name, path=None, target=None):
        if name == "{PACKAGE}" or name.startswith("{PACKAGE}."):
            raise ModuleNotFoundError("blocked: " + name, name=name)
sys.meta_path.insert(0, _Block())
'''


def _run(code: str, tmp_path: Path) -> str:
    env = {**os.environ, "METASCIENCE_BLOCK_IMAGE_PLUGIN": "1",
           "PYTHONPATH": os.pathsep.join(filter(None, [str(SRC.parent), os.environ.get("PYTHONPATH", "")]))}
    p = subprocess.run([sys.executable, "-c", _BLOCK + code], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr[-3000:]
    return p.stdout


class TestTheToolkitRunsWithoutThePackage:
    def test_every_non_image_module_imports(self, tmp_path):
        out = _run('''
import importlib, json, pkgutil
import metascience_agent
failed = []
for m in pkgutil.walk_packages(metascience_agent.__path__, "metascience_agent."):
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
        assert json.loads(out) == []

    def test_the_cli_registry_and_a_statistical_tool_work(self, tmp_path):
        out = _run('''
import json
from typer.testing import CliRunner
from metascience_agent.cli import app
from metascience_agent import image_plugin, registry
from metascience_agent.tools_mcp import ALL_TOOLS
r = CliRunner()
help_ = r.invoke(app, ["--help"])
assert help_.exit_code == 0, help_.output
assert "image-gate" not in help_.output and "image-sweep" not in help_.output
assert r.invoke(app, ["pipeline", "list"]).exit_code == 0
listed = r.invoke(app, ["tool", "list"])
assert listed.exit_code == 0 and "grim_check" in listed.output, listed.output
run = r.invoke(app, ["tool", "run", "grim_check", "--json",
                     '{"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert"}'])
assert run.exit_code == 0, run.output
spec = registry.BY_NAME["extract_figures"]
refused = spec.fn(paper_dir=".")
print(json.dumps({"available": image_plugin.available(), "n_specs": len(registry.SPECS),
                  "n_mcp": len(ALL_TOOLS), "refused": refused}))
''', tmp_path)
        got = json.loads(out.strip().splitlines()[-1])
        assert got["available"] is False
        # The registry is the same with or without the package: specs stay
        # registered and refuse by name.
        from metascience_agent import registry
        assert got["n_specs"] == len(registry.SPECS)
        assert got["refused"]["state"] == "image_plugin_unavailable"
        assert got["refused"]["severity"] == "indeterminate"

    def test_an_image_module_reports_unavailable_not_clean(self, tmp_path):
        out = _run('''
import asyncio, json
from metascience_agent import modules
module = modules.load("image_analysis")
class Ctx:
    paper_dir = "."
result = asyncio.run(module.run(Ctx(), {}))
print(json.dumps(result.record))
''', tmp_path)
        record = json.loads(out.strip().splitlines()[-1])
        assert record["ran"] is False and record["execution_status"] == "unavailable"
        assert record["findings"] == []
        assert any("NOT examined" in s for s in record["limitations"])

    def test_preflight_and_the_workbench_service_build(self, tmp_path):
        _run(f'''
from metascience_agent import preflight
rows = preflight.optional_checks()
panel = [r for r in rows if r[0].startswith("Panel duplication")][0]
assert panel[1] is False and "not installed" in panel[2], panel
from metascience_agent.workbench.catalog import Catalog
from metascience_agent.workbench.service import Service
from metascience_agent.image_plugin import ImagePluginUnavailable
svc = Service(Catalog(r"{tmp_path}/wb.sqlite3"), remote=object(), background=False)
try:
    svc.shared_image_queue("feed", {{}})
except ImagePluginUnavailable:
    pass
else:
    raise AssertionError("an image route answered without the image package")
''', tmp_path)
