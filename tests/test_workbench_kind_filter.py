import pytest
"""Kind facet on the image queue: counts reported, filter applied, and the
counts describe the selected run before other filters — the same contract as
image_types.
"""
import json

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.repository import Repository
from tests.test_workbench_catalog import seed


def _repo(tmp_path):
    c = Catalog(tmp_path / "cache.sqlite3")
    seed(c)
    return c, Repository(c)


@pytest.mark.usefixtures("image_package")
def test_kind_counts_cover_the_selected_run_before_filters(tmp_path):
    c, r = _repo(tmp_path)
    try:
        items = sorted(c.records("component_items"), key=lambda i: i["id"])
        items[0]["record"]["detector_kind"] = "transformed_match"
        items[1]["record"]["detector_kind"] = "transformed_match"
        items[2]["record"]["detector_kind"] = "intra_panel_clone"
        items[2]["record"]["kind"] = "cross"
        c.apply_changes(
            [("component_items", json.dumps([row["id"]]), row) for row in items[:3]], 2)
        r.refresh("project", "r_old", "image_forensics")
        out = r.feed({"project": "project", "run": "r_old", "verdict": "all"})
        counts = {t["value"]: t["count"] for t in out["kinds"]}
        assert counts["transformed_match"] == 2
        assert counts["intra_panel_clone"] == 1
        assert counts["exact"] == out["counts"]["items"] - 3
        assert sum(counts.values()) == out["counts"]["items"]
        assert out["counts"]["cross"] == 1

        narrowed = r.feed({"project": "project", "run": "r_old", "verdict": "all",
                           "kind": "transformed_match"})
        assert narrowed["pagination"]["total"] == 2
        assert {i["detector_kind"] for i in narrowed["items"]} == {"transformed_match"}
        # The counts describe the selected run BEFORE the kind filter, so a
        # reviewer can see what else exists while narrowed to one detector.
        assert narrowed["kinds"] == out["kinds"]
        assert narrowed["counts"]["cross"] == out["counts"]["cross"]
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_uniform_seed_reports_one_kind(tmp_path):
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "r_old", "image_forensics")
        out = r.feed({"project": "project", "run": "r_old", "verdict": "all"})
        assert out["kinds"] == [{"value": "exact", "count": out["counts"]["items"]}]
    finally:
        c.close()
