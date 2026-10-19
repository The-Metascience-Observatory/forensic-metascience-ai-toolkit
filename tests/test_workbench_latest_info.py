import pytest
"""The feed must say what "latest" resolved to.

2026-09-14: two newer sweeps of a corpus sat on disk unsynced while the viewer
showed the previous one as current. The header printed `built_at` -- the time
the projection was rebuilt -- which read as fresh. The only on-screen tells were
a version tag on one row and the words "mixed runs". `latest_info` puts the
newest run's OWN date, the number of detector CONFIGURATIONS (code fingerprint
+ flags -- the stamp the sweep resumes on) the per-paper view mixes, and the
newest run's identity into the response, so the selector and header can
state freshness rather than leave it to be inferred.
"""
from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.repository import Repository
from tests.test_workbench_catalog import seed


def _repo(tmp_path):
    c = Catalog(tmp_path / "cache.sqlite3")
    seed(c)
    return c, Repository(c)


@pytest.mark.usefixtures("image_package")
def test_explicit_run_reports_its_own_date_and_execution(tmp_path):
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "r_old", "image_forensics")
        info = r.feed({"project": "project", "run": "r_old"})["latest_info"]
        assert info["newest_run_at"] == "2026-01-01"
        # The seed's run carries no provenance parameters, so it is not a
        # detection stamp and contributes NO configuration -- the same rule
        # that keeps `saved_*` preserve snapshots from counting. A stamped run
        # is asserted in the tests below.
        assert info["configurations_in_view"] == 0
        assert info["papers_in_view"] == 1
        assert info["newest_run"] == {"run_uid": "r_old", "execution_uid": "e_old"}
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_latest_selection_still_carries_the_block_when_nothing_is_eligible(tmp_path):
    """The seed's newest run is FAILED, so `latest` exposes no candidates. The
    freshness block must still be present and well-typed -- an empty feed is
    exactly when a reviewer most needs to know what was (not) selected."""
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "latest", "image_forensics")
        out = r.feed({"project": "project", "run": "latest"})
        info = out["latest_info"]
        assert set(info) == {"newest_run_at", "configurations_in_view", "papers_in_view",
                             "newest_run", "configuration"}
        assert isinstance(info["configurations_in_view"], int)
        assert {o["id"] for o in out["runs"]} >= {"e_old", "e_new"}
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_two_stamps_in_one_view_are_reported_as_mixed(tmp_path):
    """The stale-data signal. Two runs made under different detector code or
    flags, both current for their papers, is exactly the state the viewer sat
    in for a day without saying so."""
    import json
    c, r = _repo(tmp_path)
    try:
        # Two PAPERS, each with one current run, made under different stamps.
        # (The seed's two runs share a paper, and "latest per paper" keeps only
        # the newer -- one run is one configuration, correctly. The mixed state
        # is two papers whose current runs disagree.)
        rows = sorted(c.records("runs"), key=lambda r: r["id"])
        for row, paper_id, fp in zip(rows, (1, 2), ("aaaa", "bbbb")):
            row["paper_id"] = paper_id
            row["history_record"] = {"provenance": {"code_fingerprint": fp,
                                                     "parameters": {"panel_detector": "learned"}}}
            row["execution_status"] = "completed"; row["status"] = "complete"
            c.apply_changes([("runs", json.dumps([row["id"]]), row)], 3)
        r.refresh("project", "latest", "image_forensics")
        info = r.feed({"project": "project", "run": "latest"})["latest_info"]
        assert info["configurations_in_view"] == 2
        assert info["papers_in_view"] == 2
        assert info["configuration"] == {"panel_detector": "learned"}
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_a_preserve_snapshot_without_a_stamp_is_not_a_configuration(tmp_path):
    """`preserve_image` seals a `saved_*` snapshot before every detection; it
    has no detector parameters. On the real corpus 759 of them sat as the
    latest run for their papers and made one sweep read as two
    configurations. A run with no stamp contributes nothing to the count."""
    import json
    c, r = _repo(tmp_path)
    try:
        rows = sorted(c.records("runs"), key=lambda r: r["id"])
        detect, snapshot = rows[0], rows[1]
        detect["paper_id"] = 1
        detect["history_record"] = {"provenance": {"code_fingerprint": "aaaa",
                                                    "parameters": {"panel_detector": "learned"}}}
        snapshot["paper_id"] = 2
        snapshot["history_record"] = {"provenance": {"version": "1.0"}}   # no parameters
        for row in (detect, snapshot):
            row["execution_status"] = "completed"; row["status"] = "complete"
            c.apply_changes([("runs", json.dumps([row["id"]]), row)], 3)
        r.refresh("project", "latest", "image_forensics")
        info = r.feed({"project": "project", "run": "latest"})["latest_info"]
        assert info["papers_in_view"] == 2
        assert info["configurations_in_view"] == 1, "the snapshot must not count"
    finally:
        c.close()
