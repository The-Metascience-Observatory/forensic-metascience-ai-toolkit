import pytest
"""The image-type filter on the queue: counts reported, filter applied, and a
missing derivation read as `untyped` rather than as a class.

The derivation lives in component_item_derived, keyed by item id, because a
sealed run's item record cannot be updated (migration 006) and a model's
classification is not evidence. The repository joins it at read time.
"""
import json

from metascience_agent.workbench.catalog import Catalog
from metascience_agent.workbench.repository import Repository
from tests.test_workbench_catalog import seed


def _repo(tmp_path):
    c = Catalog(tmp_path / "cache.sqlite3")
    seed(c)
    return c, Repository(c)


def _derive(c, item_id, image_type, panel_types, rev):
    row = {"item_id": item_id, "image_type": image_type, "panel_types": panel_types,
           "typer": "learned", "derived_at": "2026-09-14"}
    c.apply_changes([("component_item_derived", json.dumps([item_id]), row)], rev)


@pytest.mark.usefixtures("image_package")
def test_items_without_a_derivation_are_untyped(tmp_path):
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "r_old", "image_forensics")
        out = r.feed({"project": "project", "run": "r_old", "verdict": "all"})
        assert out["image_types"] == [{"value": "untyped", "count": out["counts"]["items"]}]
        assert all(i["image_type"] == "untyped" and i["panel_types"] == {} for i in out["items"])
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_counts_and_filter_follow_the_derivation(tmp_path):
    c, r = _repo(tmp_path)
    try:
        items = sorted(c.records("component_items"), key=lambda i: i["id"])
        _derive(c, items[0]["id"], "Blots", {"u1": "Blots", "u2": "Blots"}, 2)
        _derive(c, items[1]["id"], "mixed", {"u1": "Blots", "u3": "Graphs"}, 3)
        _derive(c, items[2]["id"], "Blots", {"u4": "Blots"}, 4)
        r.refresh("project", "r_old", "image_forensics")
        out = r.feed({"project": "project", "run": "r_old", "verdict": "all"})
        counts = {t["value"]: t["count"] for t in out["image_types"]}
        assert counts["Blots"] == 2 and counts["mixed"] == 1
        assert counts["untyped"] == out["counts"]["items"] - 3

        blots = r.feed({"project": "project", "run": "r_old", "verdict": "all", "image_type": "Blots"})
        assert blots["pagination"]["total"] == 2
        assert {i["image_type"] for i in blots["items"]} == {"Blots"}
        assert blots["items"][0]["panel_types"] in ({"u1": "Blots", "u2": "Blots"}, {"u4": "Blots"})

        # The counts describe the selected run BEFORE the type filter, so a
        # reviewer can see what else exists while narrowed to one class.
        assert blots["image_types"] == out["image_types"]

        none = r.feed({"project": "project", "run": "r_old", "verdict": "all", "image_type": "Microscopy"})
        assert none["pagination"]["total"] == 0 and none["items"] == []
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_all_is_the_absence_of_a_type_filter(tmp_path):
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "r_old", "image_forensics")
        every = r.feed({"project": "project", "run": "r_old", "verdict": "all"})
        explicit = r.feed({"project": "project", "run": "r_old", "verdict": "all", "image_type": "all"})
        assert explicit["pagination"]["total"] == every["pagination"]["total"]
    finally:
        c.close()
