"""The run dropdown lists one line per event.

A run record is the per-paper answer an execution produced. Listing executions
AND their records showed every sweep twice on a one-paper corpus (Dan,
2026-09-14, on the Stiles thesis: seven events, twelve lines) and N+1 times on
an N-paper one. A record folds into its execution; selecting the execution
already selects its records. Only a record whose execution is not listed
stands on its own -- an older import with no execution row must not vanish.
"""
import json

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.repository import Repository
from tests.test_workbench_catalog import seed


def _repo(tmp_path):
    c = Catalog(tmp_path / "cache.sqlite3")
    seed(c)
    return c, Repository(c)


def test_a_run_record_folds_into_its_execution(tmp_path):
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "latest", "image_forensics")
        rows = r.catalog_runs("project")["runs"]
        ids = [row["id"] for row in rows]
        # Executions only (the seed gives them no start time, so no order).
        assert sorted(ids) == ["e_new", "e_old"], ids
        by_id = {row["id"]: row for row in rows}
        assert "run_ids" not in by_id["e_old"]
        assert "run_ids" not in by_id["e_new"]
        assert by_id["e_old"]["n_runs"] == 1
        assert by_id["e_old"]["components"] == ["image_forensics"]
        assert "· image_forensics" in by_id["e_old"]["label"]
        assert "papers" not in by_id["e_old"]["label"]  # one paper: no count
        # The execution id still resolves to the record it folded.
        assert [x["run_uid"] for x in r.selected_runs("project", "e_old")] == ["r_old"]
    finally:
        c.close()


def test_a_record_without_a_listed_execution_stands_alone(tmp_path):
    c, r = _repo(tmp_path)
    try:
        changes = [("runs", json.dumps([3]), {
            "id": 3, "run_uid": "r_orphan", "paper_id": 2, "component": "image_forensics",
            "status": "complete", "execution_status": "completed",
            "analysed_at": "2026-03-01", "execution_uid": "e_gone"})]
        c.apply_changes(changes, 2)
        r.refresh("project", "latest", "image_forensics")
        rows = r.catalog_runs("project")["runs"]
        ids = [row["id"] for row in rows]
        assert sorted(ids[:2]) == ["e_new", "e_old"] and ids[2] == "r_orphan", ids
        assert rows[-1]["execution_id"] == "e_gone"
        assert "run_ids" not in rows[-1]
    finally:
        c.close()


def test_a_many_paper_execution_says_how_many(tmp_path):
    c, r = _repo(tmp_path)
    try:
        changes = [("runs", json.dumps([4]), {
            "id": 4, "run_uid": "r_old_2", "paper_id": 2, "component": "image_forensics",
            "status": "complete", "execution_status": "completed",
            "analysed_at": "2026-01-01", "execution_uid": "e_old"})]
        c.apply_changes(changes, 2)
        r.refresh("project", "latest", "image_forensics")
        rows = {row["id"]: row for row in r.catalog_runs("project")["runs"]}
        assert "run_ids" not in rows["e_old"]
        assert sorted(x["run_uid"] for x in r.selected_runs("project", "e_old")) == ["r_old", "r_old_2"]
        assert rows["e_old"]["n_runs"] == 2
        assert rows["e_old"]["label"].endswith("· 2 papers")
    finally:
        c.close()
