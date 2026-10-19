"""The recorded Python-vs-R differentials still describe the code we ship.

`benchmarks/r_differential/` holds an exhaustive comparison of our GRIM and
SPRITE against R's `scrutiny` and `rsprite2`. A full run takes about a minute and
needs R, so it is NOT part of the suite. What the suite does instead costs
milliseconds: each result records the SHA-256 of every source file its verdict
depends on, and this test fails when one has changed since the run. Then the
"326,785 agree" in the JSON is a claim about old code, and the fix is to re-run
the differential named in the failure, not to edit the hash.

The 2026-08-26 results had no such record; by 2026-10-18 both grim.py and
sprite.py had changed under them and nothing said so.

`TestQuickDifferential` runs the real R comparison on a small grid. It is
opt-in: RUN_R_DIFFERENTIAL=1.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "benchmarks" / "r_differential"


def _fingerprint():
    spec = importlib.util.spec_from_file_location(
        "r_differential_fingerprint", HERE / "fingerprint.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FP = _fingerprint()

RECORDS = {
    "grim_r_differential": FP.GRIM_SOURCES,
    "sprite_r_differential": FP.SPRITE_SOURCES,
}


def _record(stem: str) -> dict:
    return json.loads((HERE / f"{stem}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("stem", sorted(RECORDS))
class TestRecordMatchesCode:
    def test_is_a_full_run(self, stem):
        assert _record(stem)["quick"] is False, (
            f"{stem}.json holds a --quick smoke run; only a full run is the record")

    def test_covers_every_source(self, stem):
        recorded = set(_record(stem).get("code_sha256") or {})
        missing = set(RECORDS[stem]) - recorded
        assert not missing, (
            f"{stem}.json does not fingerprint {sorted(missing)}; re-run "
            f"benchmarks/r_differential/{stem}.py")

    def test_sources_unchanged_since_run(self, stem):
        rec = _record(stem)
        changed = [rel for rel, sha in rec["code_sha256"].items()
                   if FP.sha256_of(rel) != sha]
        assert not changed, (
            f"{', '.join(changed)} changed since the differential ran "
            f"({rec['generated_at']}), so {stem}.json no longer describes this "
            f"code. Re-run (needs R; about a minute):\n"
            f"    $(metascience python) benchmarks/r_differential/{stem}.py")


def test_grim_agrees_with_scrutiny():
    rec = _record("grim_r_differential")
    assert rec["n_compared"] > 0
    assert rec["n_disagree"] == 0, rec["disagreements"][:5]


def test_sprite_agrees_with_rsprite2_where_the_test_has_power():
    """Only n < 10**m_prec is evidence (rsprite2's own rule). Outside it the
    known disagreements are both engines answering a question neither should."""
    reg = _record("sprite_r_differential")["regions"]["in_power"]
    assert reg["n_compared"] > 0
    assert reg["n_disagree"] == 0


@pytest.mark.r_differential
@pytest.mark.skipif(os.environ.get("RUN_R_DIFFERENTIAL") != "1",
                    reason="runs R; set RUN_R_DIFFERENTIAL=1")
@pytest.mark.parametrize("stem", sorted(RECORDS))
def test_quick_differential(stem, tmp_path):
    out = tmp_path / f"{stem}.json"
    proc = subprocess.run(
        [sys.executable, str(HERE / f"{stem}.py"), "--quick", "--out", str(out)],
        capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert json.loads(out.read_text())["n_compared"] > 0
