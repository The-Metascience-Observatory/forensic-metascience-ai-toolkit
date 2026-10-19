"""Acquisition accounting and denominators must survive missing evidence."""

import asyncio
import json

import pytest
from test_paper_batch import csv_data

from copy_paste_detector.batch import run_batch
from copy_paste_detector.benchmark import matches, score
from copy_paste_detector.datasets import import_local, sample_frame, split_families
from copy_paste_detector.storage import file_hash


def test_local_import_pins_version_and_preserves_missing(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    original = incoming / "original.csv"
    csv_data(original)
    files = [
        {
            "filename": "original.csv",
            "supported": True,
            "digest": file_hash(original),
            "digest_type": "sha-256",
        },
        {
            "filename": "missing.csv",
            "supported": True,
            "digest": "0" * 64,
            "digest_type": "sha-256",
        },
    ]
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "test",
                        "family_id": "paper",
                        "paper_doi": "doi",
                        "datasets": [
                            {"doi": "data-doi", "versions": [{"version_id": "1", "files": files}]}
                        ],
                    }
                ]
            }
        )
    )
    result = import_local(catalog, incoming, tmp_path / "imported")
    assert result == {"papers": 1, "verified_files": 1, "files_requested": 2}
    record = json.loads((tmp_path / "imported/manifest.jsonl").read_text())
    assert len(record["files"]) == 2
    receipts = json.loads((tmp_path / "imported/import_receipt.json").read_text())["files"]
    assert {r["status"] for r in receipts} == {"verified", "missing"}
    original.write_text("wrong version")
    bad = import_local(catalog, incoming, tmp_path / "other")
    assert bad["verified_files"] == 0


def test_sampling_does_not_invent_negatives_or_split_versions(tmp_path):
    rows = [
        {
            "paper_id": str(i),
            "family_id": f"family-{i // 2}",
            "files": [{"filename": "a.csv"}],
            "domain": "biology",
        }
        for i in range(240)
    ]
    frame = tmp_path / "frame.json"
    frame.write_text(json.dumps({"description": "synthetic frame", "papers": rows}))
    sample_frame(frame, tmp_path / "sample.json")
    first = json.loads((tmp_path / "sample.json").read_text())
    sample_frame(frame, tmp_path / "sample2.json")
    assert first == json.loads((tmp_path / "sample2.json").read_text())
    assert len(first["papers"]) == 100
    assert len({r["family_id"] for r in first["papers"]}) == 100
    assert all(r["verification_status"] == "unlabelled" for r in first["papers"])
    partition = split_families(rows)
    assert len(partition) == 120
    assert sum(v == "held_out" for v in partition.values()) == 36
    with pytest.raises(ValueError, match="eligible"):
        sample_frame(frame, tmp_path / "too_many.json", n=121)


def test_matching_requires_actual_labeled_cells():
    group = {"kind": "row_pair", "cells": [{"file": "a.csv", "sheet": "Data", "cell": "B5"}]}
    issue = {"kind": "row_pair", "cells": [{"file": "a.csv", "sheet": "Data", "cell": "B20"}]}
    assert not matches(group, issue)
    issue["cells"][0]["cell"] = "B5"
    assert matches(group, issue)
    issue["cells"] = []
    assert not matches(group, issue)


def test_scorecard_separates_missing_and_unverified(tmp_path):
    data = tmp_path / "a.csv"
    csv_data(data)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"paper_id": "present", "files": [str(data)]}))
    out = tmp_path / "run"
    batch = asyncio.run(run_batch(manifest, out))
    result = json.loads((out / batch["runs"][0]["directory"] / "result.json").read_text())
    group = next(g for g in result["duplicate_groups"] if g["kind"] == "row_pair")
    issue = {
        "id": "issue",
        "kind": "row_pair",
        "verification_status": "verified_duplication",
        "evidence_url": "synthetic:planted",
        "cells": [{k: c[k] for k in ("file", "sheet", "cell")} for c in group["cells"]],
    }
    labels = tmp_path / "labels.jsonl"
    gold = [
        {"paper_id": "present", "source_sha256": {"a.csv": file_hash(data)}, "issues": [issue]},
        {"paper_id": "missing", "source_sha256": {"a.csv": "a" * 64}, "issues": [issue]},
        {
            "paper_id": "unverified",
            "issues": [
                {"id": "reported", "kind": "row_pair", "verification_status": "unresolved_concern"}
            ],
        },
    ]
    labels.write_text("".join(json.dumps(r) + "\n" for r in gold))
    report = score(labels, out / "index.json", tmp_path / "score")
    assert report["candidate_recall_all_verified"] == {
        "numerator": 1,
        "denominator": 2,
        "value": 0.5,
    }
    assert report["candidate_recall_available_supported"]["value"] == 1
    assert report["retained_recall_all_verified"]["numerator"] == 0
    assert report["reviewed_candidate_precision"]["value"] is None
    assert report["specificity_complete_verified_negatives"]["value"] is None
    assert report["papers"][1]["issues"][0]["state"] == "source_unavailable"
    assert report["papers"][2]["issues"][0]["state"] == "unverified"


def test_stale_import_bytes_are_refused(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    path = incoming / "data.csv"
    csv_data(path)
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "test",
                        "family_id": "f",
                        "paper_doi": "p",
                        "datasets": [
                            {
                                "doi": "d",
                                "versions": [
                                    {
                                        "version_id": "1",
                                        "files": [
                                            {
                                                "filename": "data.csv",
                                                "supported": True,
                                                "digest": file_hash(path),
                                                "digest_type": "sha256",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        )
    )
    import_local(catalog, incoming, tmp_path / "out")
    (tmp_path / "out/inputs/test-v1/data.csv").write_text("stale bytes")
    path.unlink()
    with pytest.raises(ValueError, match="Existing import"):
        import_local(catalog, incoming, tmp_path / "out")
