"""Coverage, evidence identity, real process execution and safe resume."""

import asyncio
import csv
import json
import random

import pytest
from openpyxl import Workbook

from copy_paste_detector import detect_paper_duplication, detect_raw_duplication
from copy_paste_detector.batch import output_lock, run_batch
from copy_paste_detector.storage import file_hash


def csv_data(path, seed=7, n=60, duplicate=True):
    rng = random.Random(seed)
    rows = [["participant_id", "mass_mg", "cortisol_nmol"]]
    rows += [
        [i, round(rng.uniform(100, 900), 6), round(rng.uniform(100, 900), 6)]
        for i in range(1, n + 1)
    ]
    if duplicate:
        rows[-2][1:] = rows[5][1:]
    with path.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return rows


def test_wide_excel_full_and_partial_are_distinct(tmp_path):
    rng = random.Random(9)
    path = tmp_path / "wide.xlsx"
    book = Workbook()
    book.active.append(
        ["a", "b"] + [f"constant_{i}" for i in range(98)] + ["mass_mg", "cortisol_nmol"]
    )
    rows = [
        [round(rng.uniform(10, 900), 6) for _ in range(2)]
        + [1] * 98
        + [round(rng.uniform(10, 900), 6) for _ in range(2)]
        for _ in range(30)
    ]
    rows[25][-2:] = rows[4][-2:]
    for row in rows:
        book.active.append(row)
    book.save(path)
    partial = detect_raw_duplication(str(path))
    assert partial["coverage"]["status"] == "partial"
    assert "PARTIAL" in partial["explanation"]
    full = detect_paper_duplication([path])
    assert full["coverage"]["status"] == "complete"
    assert full["n_numeric_cells"] == 30 * 102
    assert any(c["col"] == 101 for g in full["duplicate_groups"] for c in g.get("cells", []))


def test_all_groups_and_coordinates_survive(tmp_path):
    path = tmp_path / "many.csv"
    rows = csv_data(path, n=1000, duplicate=False)
    for i in range(150):
        rows[700 + i][1:] = rows[50 + i][1:]
    with path.open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    r = detect_paper_duplication([path])
    assert r["n_duplicate_groups"] > 100
    assert len(r["duplicate_groups"]) == r["n_duplicate_groups"]
    assert len({g["id"] for g in r["duplicate_groups"]}) == len(r["duplicate_groups"])


def test_cross_file_refs_and_exclusions(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    rows_a, rows_b = csv_data(a, duplicate=False), csv_data(b, seed=42, duplicate=False)
    rows_b[20][1:] = rows_a[5][1:]
    with b.open("w", newline="") as f:
        csv.writer(f).writerows(rows_b)
    result = detect_paper_duplication([a, b])
    pairs = [g for g in result["duplicate_groups"] if g["kind"] == "row_pair" and g["cross_file"]]
    assert pairs
    assert {r["file"] for r in pairs[0]["cells"]} == {"a.csv", "b.csv"}
    assert all(r["source_sha256"] == file_hash(tmp_path / r["file"]) for r in pairs[0]["cells"])
    excluded = detect_paper_duplication([{"path": a, "exclude_columns": ["mass_mg"]}, b])
    assert not any(
        g["kind"] == "row_pair" and g["cross_file"] for g in excluded["duplicate_groups"]
    )


def test_duplicate_deliveries_not_independent_observations(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    csv_data(a, duplicate=False)
    b.write_bytes(a.read_bytes())
    result = detect_paper_duplication([a, b])
    assert result["coverage"]["file_states"]["duplicate_delivery"] == 1
    assert result["n_row_pairs"] == 0


def test_formula_caches_and_unsupported_inputs(tmp_path):
    path = tmp_path / "formulas.xlsx"
    book = Workbook()
    book.active.append(["id", "measurement"])
    book.active.append([1, "=12.345"])
    book.active.append([2, "=12.345"])
    book.save(path)
    result = detect_paper_duplication([path, tmp_path / "missing.csv", tmp_path / "supp.docx"])
    source = next(s for s in result["sources"] if s["file"] == "formulas.xlsx")
    assert len(source["coverage"]["missing_formula_cache"]) == 2
    assert result["coverage"]["status"] != "complete"
    assert result["coverage"]["file_states"]["unsupported"] == 1
    assert result["coverage"]["file_states"]["failed"] == 1


def test_sequences_do_not_bridge_missing_rows(tmp_path):
    path = tmp_path / "gaps.csv"
    with path.open("w", newline="") as f:
        csv.writer(f).writerows(
            [
                ["id", "value"],
                [1, 123.4567],
                [2, ""],
                [3, 378.9136],
                [4, ""],
                [5, 689.4721],
                [6, ""],
                [7, 123.4567],
                [8, ""],
                [9, 378.9136],
                [10, ""],
                [11, 689.4721],
            ]
        )
    result = detect_paper_duplication([path])
    assert not any(g["kind"] == "column_sequence" for g in result["duplicate_groups"])


def test_ambiguous_headers_stay_positional(tmp_path):
    path = tmp_path / "repeated.csv"
    rng = random.Random(42)
    rows = [["id", "measurement", "measurement", "other"]]
    rows += [[i] + [round(rng.uniform(100, 900), 6) for _ in range(3)] for i in range(30)]
    rows[25][1], rows[25][3] = rows[5][1], rows[5][3]
    with path.open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    result = detect_paper_duplication([path])
    assert any("ambiguous" in c for c in result["caveats"])
    assert result["n_row_pairs"] >= 1


@pytest.mark.parametrize("workers", [1, 2, 4, 8])
def test_real_parallel_batch_resume_and_source_hashes(tmp_path, workers):
    rows = []
    for i in range(8):
        path = tmp_path / f"data{i}.csv"
        csv_data(path, seed=i)
        rows.append({"paper_id": str(i), "files": [str(path)]})
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = tmp_path / "output"
    result = asyncio.run(run_batch(manifest, out, workers=workers))
    assert len(result["runs"]) == 8
    assert all(r["status"] == "completed" for r in result["runs"])
    intervals = []
    for run in result["runs"]:
        folder = out / run["directory"]
        saved = json.loads((folder / "result.json").read_text())
        original = detect_paper_duplication(
            [tmp_path / f"data{run['paper_id']}.csv"], paper_id=run["paper_id"]
        )
        assert saved["duplicate_groups"] == original["duplicate_groups"]
        meta = json.loads((folder / "manifest.json").read_text())
        intervals += [(meta["detector_started_at"], 1), (meta["detector_completed_at"], -1)]
        assert "CP-" in (folder / "review.html").read_text()
    active = peak = 0
    for _, delta in sorted(intervals):
        active += delta
        peak = max(active, peak)
    assert peak == 1 if workers == 1 else peak > 1
    reused = asyncio.run(run_batch(manifest, out, workers=workers, resume=True))
    assert all(r["reused"] for r in reused["runs"])
    # Corrupted saved evidence cannot be reused.
    first = out / reused["runs"][0]["directory"] / "result.json"
    first.write_text("{}")
    again = asyncio.run(run_batch(manifest, out, workers=workers, resume=True))
    assert sum(not r["reused"] for r in again["runs"]) == 1


def test_lock_refuses_concurrent_coordinator(tmp_path):
    with output_lock(tmp_path):
        with pytest.raises(ValueError, match="Another batch"):
            with output_lock(tmp_path):
                pytest.fail("Two writers acquired one output index")


def test_timeout_is_failure_and_can_resume(tmp_path):
    data = tmp_path / "a.csv"
    csv_data(data)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"paper_id": "a", "files": [str(data)]}))
    result = asyncio.run(run_batch(manifest, tmp_path / "out", detector_timeout=0.0001))
    assert result["runs"][0]["status"] == "failed"
    restored = asyncio.run(run_batch(manifest, tmp_path / "out", resume=True))
    assert restored["runs"][0]["status"] == "completed"
    assert not restored["runs"][0]["reused"]


@pytest.mark.parametrize("workers", [1, 2, 4, 8])
def test_cancel_reaps_workers_and_preserves_manifest(tmp_path, workers, monkeypatch):
    data = tmp_path / "a.csv"
    csv_data(data, n=2000)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "".join(json.dumps({"paper_id": str(i), "files": [str(data)]}) + "\n" for i in range(8))
    )
    spawned = []
    started = asyncio.Event()
    real_spawn = asyncio.create_subprocess_exec

    async def observe(*a, **kw):
        proc = await real_spawn(*a, **kw)
        spawned.append(proc)
        started.set()
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", observe)

    async def run():
        task = asyncio.create_task(run_batch(manifest, tmp_path / "out", workers=workers))
        await asyncio.wait_for(started.wait(), 10)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    result = json.loads((tmp_path / "out/index.json").read_text())
    assert any(r["status"] == "cancelled" for r in result["runs"])
    assert spawned and all(p.returncode is not None for p in spawned)
    assert not (tmp_path / "out/.batch.lock").exists()


def test_cross_file_sequences_require_matching_units(tmp_path):
    rng = random.Random(19)
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    values = [round(rng.uniform(100, 900), 6) for _ in range(50)]
    other = [round(rng.uniform(100, 900), 6) for _ in range(50)]
    other[20:25] = values[5:10]
    for path, name, series in ((a, "mass_mg", values), (b, "mass_kg", other)):
        with path.open("w") as handle:
            csv.writer(handle).writerows([[name]] + [[v] for v in series])
    mismatch = detect_paper_duplication([a, b])
    assert not any(g["cross_file"] for g in mismatch["duplicate_groups"])
    b.write_text(b.read_text().replace("mass_kg", "mass_mg"))
    matched = detect_paper_duplication([a, b])
    assert any(
        g["cross_file"] and g["kind"] == "column_sequence" for g in matched["duplicate_groups"]
    )


def test_manifest_checksum_mismatch_cannot_become_negative(tmp_path):
    data = tmp_path / "a.csv"
    csv_data(data)
    result = detect_paper_duplication([{"path": data, "expected_digest": "0" * 64}])
    assert result["coverage"]["status"] == "not_evaluable"
    assert result["sources"][0]["status"] == "checksum_mismatch"
