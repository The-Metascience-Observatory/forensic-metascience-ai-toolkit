import pytest
"""Paper-column sort on the image queue.

The queue pages on the server. Sorting only the 50 loaded rows would put
paper B above paper A on page 1 while A still sits on page 3. `sort=paper`
reorders the filtered set before pagination; within one folder the rank
score order is kept.
"""
import json

from metascience_agent.workbench.catalog import Catalog
from metascience_agent.workbench.repository import Repository, paper_column, sort_feed_items
from tests.test_workbench_catalog import seed
from tests.test_workbench_paper_folder_filter import _relabel


def _repo(tmp_path):
    c = Catalog(tmp_path / "cache.sqlite3")
    seed(c)
    return c, Repository(c)


@pytest.mark.usefixtures("image_package")
def test_default_order_is_score_high_to_low(tmp_path):
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "r_old", "image_forensics")
        first = r.feed({"project": "project", "run": "r_old", "verdict": "all"})
        assert first["items"][0]["id"] == "i_122"
        same = r.feed({"project": "project", "run": "r_old", "verdict": "all",
                       "sort": "score", "direction": "desc"})
        assert [i["id"] for i in same["items"]] == [i["id"] for i in first["items"]]
        unknown = r.feed({"project": "project", "run": "r_old", "verdict": "all",
                          "sort": "not-a-column"})
        assert [i["id"] for i in unknown["items"]] == [i["id"] for i in first["items"]]
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_paper_sort_is_the_folder_column_before_pagination(tmp_path):
    c, r = _repo(tmp_path)
    try:
        _relabel(c)
        r.refresh("project", "r_old", "image_forensics")
        every = r.feed({"project": "project", "run": "r_old", "verdict": "all"})
        asc = r.feed({"project": "project", "run": "r_old", "verdict": "all",
                      "sort": "paper", "direction": "asc"})
        desc = r.feed({"project": "project", "run": "r_old", "verdict": "all",
                       "sort": "paper", "direction": "desc"})
        assert asc["pagination"]["total"] == every["pagination"]["total"]
        folders = [paper_column(i) for i in asc["items"]]
        assert folders == sorted(folders, key=str.lower)
        # The first page of A→Z is the 10.1007 folder, not the 10.1038 one.
        assert all(paper_column(i).startswith("10.1007") for i in asc["items"])
        assert paper_column(desc["items"][0]).startswith("10.1038")
        # Within one folder, score high→low is preserved (stable secondary).
        nature = [i for i in desc["items"] if paper_column(i).startswith("10.1038")]
        scores = [float((i.get("rank") or {}).get("score") or 0) for i in nature]
        assert scores == sorted(scores, reverse=True)
        assert desc["kinds"] == every["kinds"]
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_sort_feed_items_unknown_key_is_score():
    rows = [
        {"id": "a", "kind": "within", "paper": {"dir": "z-paper"}, "rank": {"score": 1}},
        {"id": "b", "kind": "within", "paper": {"dir": "a-paper"}, "rank": {"score": 9}},
    ]
    sort_feed_items(rows, "paper", "asc")
    assert [i["id"] for i in rows] == ["b", "a"]
    sort_feed_items(rows, None, None)
    assert [i["id"] for i in rows] == ["b", "a"]
    cross = {"id": "c", "kind": "cross", "paper": {"dir": "z-paper"},
             "papers": [{"dir": "a-paper"}, {"dir": "z-paper"}], "rank": {"score": 5}}
    assert paper_column(cross) == "a-paper ~ z-paper"
