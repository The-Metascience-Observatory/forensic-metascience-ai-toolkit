"""Paper-folder search on the image (and copy/paste) queue.

The queue pages by filter on the server. A client-only match against the 50
loaded rows would hide every other paper in the corpus. `q` is a substring of
the folder shown in the Paper column; a DOI pasted with a slash still hits
the `--` directory name.
"""
import json

import pytest

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.repository import Repository, matches_paper_folder
from tests.test_workbench_catalog import seed


def _repo(tmp_path):
    c = Catalog(tmp_path / "cache.sqlite3")
    seed(c)
    return c, Repository(c)


def _relabel(c):
    papers = {p["id"]: p for p in c.records("papers")}
    papers[1]["dir"] = "10.1007--s004010050748"
    papers[2]["dir"] = "10.1038--nature12345"
    items = sorted(c.records("component_items"), key=lambda i: i["id"])
    for row in items[:3]:
        row["owner_paper_id"] = 2
        row["record"]["paper"] = {"dir": papers[2]["dir"]}
    items[3]["record"]["kind"] = "cross"
    items[3]["record"]["papers"] = [
        {"dir": papers[1]["dir"]},
        {"dir": papers[2]["dir"]},
    ]
    c.apply_changes(
        [("papers", json.dumps([1]), papers[1]),
         ("papers", json.dumps([2]), papers[2])]
        + [("component_items", json.dumps([row["id"]]), row) for row in items[:4]],
        2)
    return items


@pytest.mark.usefixtures("image_package")
def test_feed_filters_by_paper_folder_before_pagination(tmp_path):
    c, r = _repo(tmp_path)
    try:
        _relabel(c)
        r.refresh("project", "r_old", "image_forensics")
        every = r.feed({"project": "project", "run": "r_old", "verdict": "all"})
        nature = r.feed({"project": "project", "run": "r_old", "verdict": "all",
                         "q": "nature12345"})
        # Three items owned by paper 2, plus the cross-paper item that names it.
        assert nature["pagination"]["total"] == 4
        assert all("nature12345" in " ".join(
            [i["paper"]["dir"], *(p.get("dir") or "" for p in i.get("papers") or [])])
            or i["kind"] == "cross" for i in nature["items"])
        slash = r.feed({"project": "project", "run": "r_old", "verdict": "all",
                        "q": "10.1007/s004010050748"})
        assert slash["pagination"]["total"] == every["pagination"]["total"] - 3
        assert all(i["paper"]["dir"] == "10.1007--s004010050748" or i["kind"] == "cross"
                   for i in slash["items"])
        # Facets NARROW with the folder filter (Dan, 2026-09-15: the dropdown
        # numbers must say how many the current filters would leave). The run
        # SUMMARY does not: `counts` feeds the "N items in this run" line and
        # the "N saved results exist but none match" message, both of which
        # mean the run.
        assert sum(k["count"] for k in nature["kinds"]) < sum(k["count"] for k in every["kinds"])
        assert all(k["count"] <= dict((x["value"], x["count"]) for x in every["kinds"])[k["value"]]
                   for k in nature["kinds"])
        assert nature["counts"]["items"] == every["counts"]["items"]
        # The kind select's own "all"/"cross" options ride the same base.
        assert nature["facet_totals"]["kind"] == nature["pagination"]["total"]
        blank = r.feed({"project": "project", "run": "r_old", "verdict": "all", "q": "  "})
        assert blank["pagination"]["total"] == every["pagination"]["total"]
        none = r.feed({"project": "project", "run": "r_old", "verdict": "all",
                       "q": "no-such-folder"})
        assert none["pagination"]["total"] == 0 and none["items"] == []
    finally:
        c.close()


def test_slash_and_dash_doi_spellings_are_the_same_folder():
    item = {"paper": {"dir": "10.1007--s004010050748"}, "papers": [], "panels": []}
    assert matches_paper_folder(item, "s004010050748")
    assert matches_paper_folder(item, "10.1007/s004010050748")
    assert matches_paper_folder(item, "10.1007--s004010050748")
    assert matches_paper_folder(item, "")
    assert matches_paper_folder(item, "  ")
    assert not matches_paper_folder(item, "nature12345")
    cross = {"paper": {"dir": "nested/paper"},
             "papers": [{"dir": "10.1007--s004010050748"}], "panels": []}
    assert matches_paper_folder(cross, "s004010050748")
    panel = {"paper": {"dir": "other"}, "papers": [],
             "panels": [{"paper_dir": "10.1038--nature12345"}]}
    assert matches_paper_folder(panel, "10.1038/nature12345")


@pytest.mark.usefixtures("image_package")
@pytest.mark.parametrize('filters', [
    {'kind': 'cross'}, {'image_type': 'Microscopy'},
    {'lookalike': 'yes'}, {'judgments': []}, {'verdict': 'cleared'},
])
def test_other_filters_do_not_claim_the_paper_folder_is_absent(tmp_path, filters):
    c, repo = _repo(tmp_path)
    try:
        repo.refresh('project', 'r_old', 'image_forensics')
        feed = repo.feed({'project': 'project', 'run': 'r_old', 'verdict': 'all',
                          'q': 'nested/paper', **filters})
        assert feed['pagination']['total'] == 0
        assert '123 saved results match paper folder "nested/paper", but other filters hide them.' in feed['empty_reason']
        assert 'No paper folder matches' not in feed['empty_reason']
        absent = repo.feed({'project': 'project', 'run': 'r_old', 'verdict': 'all',
                            'q': 'no-such-folder'})
        assert 'No saved results in this run selection match paper folder "no-such-folder".' in absent['empty_reason']
        assert 'synchronize' in absent['empty_reason']
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_newly_synchronized_detection_only_paper_appears_in_latest(tmp_path):
    """The embargoed-corpus expansion exists only after its saved run reaches the catalog.

    Null screening/adjudication are real detection-only records, not legacy
    judgments. Both DOI spellings and the user's partial folder must find them.
    An explicitly selected older execution must remain scoped to that execution.
    """
    c, repo = _repo(tmp_path)
    try:
        args = {'project': 'project', 'run': 'latest', 'verdict': 'all',
                'judgments': ['issue', 'unresolved', 'missing'], 'q': '10.1002--dvdy.64'}
        repo.refresh('project', 'latest', 'image_forensics')
        assert repo.feed(args)['pagination']['total'] == 0
        paper = {'id': 3, 'corpus_id': 1, 'dir': '10.1002--dvdy.646'}
        run = {'id': 3, 'run_uid': 'r_expansion', 'paper_id': 3, 'component': 'image_forensics',
               'status': 'complete', 'execution_status': 'completed',
               'analysed_at': '2026-09-19', 'execution_uid': 'e_expansion'}
        item = {'id': 124, 'run_id': 3, 'owner_paper_id': 3, 'item_uid': 'expansion_item',
                'record': {'id': 'expansion_item', 'paper': {'dir': paper['dir']},
                           'kind': 'within', 'detector_kind': 'transformed_match',
                           'screening': None, 'adjudication': None, 'cleared': False}}
        c.apply_changes([('papers', '[3]', paper), ('runs', '[3]', run),
                         ('executions', '["e_expansion"]', {'execution_uid': 'e_expansion',
                          'corpus_id': 1, 'name': 'Expansion', 'status': 'completed'}),
                         ('component_items', '[124]', item)], 2)
        repo.refresh('project', 'latest', 'image_forensics')
        for query in ('10.1002--dvdy.64', '10.1002/dvdy.64', '  DVDY.646  '):
            feed = repo.feed({**args, 'q': query, 'undecided': True})
            assert [i['id'] for i in feed['items']] == ['expansion_item']
            assert feed['latest_info']['newest_run_at'] == '2026-09-19'
            assert feed['judgment_counts'] == {'missing': 1}
            assert feed['empty_reason'] is None
        assert repo.feed({**args, 'judgments': ['legacy']})['pagination']['total'] == 0
        repo.refresh('project', 'r_old', 'image_forensics')
        older = repo.feed({**args, 'run': 'r_old'})
        assert older['pagination']['total'] == 0
        assert 'No saved results in this run selection' in older['empty_reason']
    finally:
        c.close()
