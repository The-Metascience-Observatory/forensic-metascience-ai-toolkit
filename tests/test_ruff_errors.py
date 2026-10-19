"""`src/` carries no ruff ERROR-class findings.

pyproject.toml selects `E, F, I, N, W` and nothing enforced any of it: there
is no CI and no pre-commit, so on 2026-09-02 `src/` held 867 findings under
its own configuration, 68 of them the class that can hide a defect (49 unused
imports, 10 unused locals, 9 placeholder-less f-strings) -- and one of those
unused locals was a real bug (handoff.py's dropped walker problems). This
pins the ERROR class at zero: syntax errors and every F-rule. Style rules
(E501 line length, import order, naming) are deliberately not gated here.

Offline and fast (~1 s). Skips, loudly, if ruff is not importable in this
interpreter -- a missing linter is not a clean lint.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _ruff(*args: str) -> list[dict]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--output-format", "json", *args],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        pytest.skip(f"ruff could not run: {exc}")
    if proc.returncode not in (0, 1):
        pytest.skip(f"ruff unavailable in this interpreter: {proc.stderr[:200]}")
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:  # pragma: no cover
        pytest.skip("ruff did not return JSON")


def test_src_has_no_error_class_findings():
    findings = _ruff("src/", "--select", "E9,F")
    lines = sorted(f"{f['filename'].replace(str(ROOT) + '/', '')}:{f['location']['row']}: "
                   f"{f['code']} {f['message']}" for f in findings)
    assert not findings, "ruff error-class findings in src/:\n" + "\n".join(lines)
