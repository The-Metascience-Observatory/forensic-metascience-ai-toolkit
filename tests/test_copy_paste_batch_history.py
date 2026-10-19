"""Paper-level portable evidence is usable after all live files disappear."""

import asyncio
import csv
import json
import random

import pytest

from copy_paste_detector.batch import run_batch
from copy_paste_detector.storage import atomic_json, file_hash
from forensic_metascience_ai_toolkit.analysis_history import import_copy, sheet
from forensic_metascience_ai_toolkit.analysis_runs import Archive


def test_batch_import_preserves_sources_decisions_and_table_cells(tmp_path):
    paper = tmp_path / "corpus" / "paper"
    paper.mkdir(parents=True)
    rng = random.Random(20260910)
    data = [
        [[i, rng.uniform(100, 900), rng.uniform(100, 900)] for i in range(60)] for _ in range(2)
    ]
    data[1][20][1:] = data[0][5][1:]
    for name, rows in zip(("a.csv", "b.csv"), data):
        with (paper / name).open("w") as handle:
            csv.writer(handle).writerows([["id", "mass_mg", "cortisol_nmol"]] + rows)
    manifest = tmp_path / "input.jsonl"
    manifest.write_text(
        json.dumps({"paper_id": "test", "files": [str(paper / "a.csv"), str(paper / "b.csv")]})
    )
    batch = asyncio.run(run_batch(manifest, tmp_path / "standalone"))
    folder = tmp_path / "standalone" / batch["runs"][0]["directory"]
    raw = json.loads((folder / "result.json").read_text())
    candidate = next(g for g in raw["duplicate_groups"] if g["cross_file"])
    judgment = {
        "status": "completed",
        "decisions": [
            {
                "candidate_id": candidate["id"],
                "decision": "uncertain",
                "reason": "Study context unavailable",
                "citations": [],
            }
        ],
        "receipts": [],
    }
    atomic_json(folder / "adjudication.json", judgment)
    meta = json.loads((folder / "manifest.json").read_text())
    meta["artifacts"]["adjudication.json"]["sha256"] = file_hash(folder / "adjudication.json")
    atomic_json(folder / "manifest.json", meta)
    imported = import_copy(paper.parent, paper, folder)
    item = next(i for i in imported["items"] if i["source_id"] == candidate["id"])
    assert item["copy_judgment"]["decision"] == "uncertain"
    assert {f["name"] for f in item["input_files"]} == {"a.csv", "b.csv"}
    assert item["coverage"]["status"] == "complete"
    archive = Archive(paper.parent)
    for f in item["input_files"]:
        (paper / f["name"]).unlink()
        archived, metadata = archive.artifact(imported["id"], f["path"].rsplit("/", 1)[-1])
        assert metadata["name"].endswith(".csv")
        assert b"cortisol_nmol" in archived.read_bytes()
        refs = [c for c in candidate["cells"] if c["file"] == f["name"]]
        grid = sheet(paper.parent, imported["id"], f["path"].rsplit("/", 1)[-1], highlights=refs)
        assert len(grid["highlights"]) == len(refs)
        for c in refs:
            i = grid["row_numbers"].index(c["row"])
            assert str(c["value"]) in grid["rows"][i]
    assert import_copy(paper.parent, paper, folder)["existing"]
    (folder / "result.json").write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        import_copy(paper.parent, paper, folder)


def test_embedded_copy_version_needs_no_distribution_metadata():
    from copy_paste_detector import __version__
    from forensic_metascience_ai_toolkit.analysis_runs import provenance
    assert provenance('copy_paste')['version'] == __version__


def test_partial_batch_import_is_incomplete_in_workbench(tmp_path):
    paper = tmp_path / 'corpus' / 'paper'
    paper.mkdir(parents=True)
    data = paper / 'data.csv'
    data.write_text('id,mass,cortisol\n1,123.456789,456.789123\n2,678.901234,765.432189\n3,123.456789,456.789123\n')
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(json.dumps({'paper_id': 'partial', 'files': [str(data), str(paper/'missing.csv')]}))
    output = tmp_path / 'batch'
    batch = asyncio.run(run_batch(manifest, output))
    assert batch['runs'][0]['status'] == 'partial'
    saved = import_copy(paper.parent, paper, output / batch['runs'][0]['directory'])
    assert saved['status'] == 'incomplete'
    assert saved['raw_result']['coverage']['status'] == 'partial'
