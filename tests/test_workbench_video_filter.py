import pytest
"""Image-queue feed facets, and the removal of the has-video filter.

Dan, 2026-09-30: new detections no longer render videos automatically, and the
queue's Video yes/no filter was removed. The feed ignores a stale `has_video`
argument (a browser can still hold one in saved filter state) and reports no
`video_counts`; a video that exists is still attached to its item.
"""
import json

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.repository import Repository
from tests.test_workbench_catalog import seed


def _repo(tmp_path):
    c = Catalog(tmp_path / "cache.sqlite3")
    seed(c)
    return c, Repository(c)


def _feed(r, **kw):
    return r.feed({"project": "project", "run": "r_old", "verdict": "all", **kw})


@pytest.mark.usefixtures("image_package")
def test_the_feed_has_no_video_facet_and_ignores_a_stale_argument(tmp_path):
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "r_old", "image_forensics")
        base = _feed(r)
        total = base["counts"]["items"]
        assert "video_counts" not in base
        target = base["items"][0]["id"]
        for item in r.feed_pages[("project", "r_old", "image_forensics")]:
            if item["id"] == target:
                item["video"] = "__runs/ar_test/a_video"
        for stale in ("yes", "no", "all"):
            assert _feed(r, has_video=stale)["pagination"]["total"] == total, stale
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_the_feed_does_not_deep_copy_every_record(tmp_path):
    """The feed's views are SHALLOW copies, and the stored record stays intact.

    MEASURED 2026-09-15 on the embargoed 2026-09 corpus (37,465 items): the deep copy
    was 3.79 s of a 4.94 s cold feed build -- 3.9 million recursive
    `copy.deepcopy` calls over nested panels, measurements and captions that
    nothing on this path writes to. Shallow: 0.73 s.

    This pins BOTH halves. A future edit that starts writing into a nested
    structure from `item_view` would corrupt the projection silently, and the
    mutation check below is what catches it.
    """
    import copy as _copy
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "r_old", "image_forensics")
        rid = next(iter(r.items_by_run))
        raws = r.items_by_run[rid]
        before = [_copy.deepcopy(x["record"]) for x in raws]

        views = [r.item_view(x, "latest", deep=False) for x in raws]
        assert views, "the seed must offer items"
        # Nothing the view writes may reach the stored record.
        for raw, snapshot in zip(raws, before):
            assert raw["record"] == snapshot, "a view write leaked into the projection"
        # ...and the saving is real: nested values are shared, not rebuilt.
        shared = [v for v, raw in zip(views, raws)
                  if raw["record"].get("panels") is not None
                  and v.get("panels") is raw["record"].get("panels")]
        assert shared, "the shallow copy is not actually sharing nested values"

        # The deep path still deep-copies, for callers handed the full record.
        deep = r.item_view(raws[0], "latest", deep=True)
        if raws[0]["record"].get("panels") is not None:
            assert deep.get("panels") is not raws[0]["record"].get("panels")
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_workers_at_one_generation_share_the_projection(tmp_path):
    """The load is paid once per (catalog generation, scope), not per worker.

    The service runs four interactive readers and gives each THREAD its own
    Repository, so every worker used to load the projection itself. MEASURED
    2026-09-15 on the embargoed 2026-09 corpus: 4.4 s per worker, and three sequential
    queue requests hit three cold workers for 7.5-8.6 s apiece with the catalog
    generation provably unchanged between them.

    Sharing is not a semantic change: every worker at one generation reads the
    same read-only tables and computes identical data. What it must NOT share
    is the per-worker page caches, which are written on every read.
    """
    c = Catalog(tmp_path / "cache.sqlite3")
    seed(c)
    try:
        a, b = Repository(c), Repository(c)
        a.refresh("project", "r_old", "image_forensics")
        b.refresh("project", "r_old", "image_forensics")
        for name in ("items", "runs", "papers", "data"):
            assert getattr(a, name) is getattr(b, name), f"{name} is not shared"
        assert a.feed_pages is not b.feed_pages, "page caches must stay per-worker"
        assert a.paper_pages is not b.paper_pages, "page caches must stay per-worker"
        # Both must still answer identically.
        assert (a.feed({"project": "project", "run": "r_old", "verdict": "all"})["counts"]
                == b.feed({"project": "project", "run": "r_old", "verdict": "all"})["counts"])
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_a_new_generation_is_not_served_from_the_old_one(tmp_path):
    """The generation is the cache key, so a write must not be answered with
    stale data -- the failure mode that would make this optimisation a
    correctness bug rather than a speed-up."""
    c = Catalog(tmp_path / "cache.sqlite3")
    seed(c)
    try:
        r = Repository(c)
        r.refresh("project", "r_old", "image_forensics")
        first = r.feed({"project": "project", "run": "r_old", "verdict": "all"})
        before = first["counts"]["items"]
        version_before = r.version
        # A REAL item, found from the feed: a derivation written against an id
        # the seed does not contain would leave the tally unchanged and the
        # test would pass for the wrong reason.
        item_row = next(i for rid in r.items_by_run for i in r.items_by_run[rid])
        item_key = item_row["id"]
        # Any record write bumps the catalog generation.
        c.apply_changes([("component_item_derived", json.dumps([item_key]),
                          {"item_id": item_key, "image_type": "Blots", "panel_types": {},
                           "typer": "learned", "derived_at": "2026-09-15"})], 10 ** 9)
        r.refresh("project", "r_old", "image_forensics")
        assert r.version != version_before, "the generation must move with the write"
        after = r.feed({"project": "project", "run": "r_old", "verdict": "all"})
        assert after["counts"]["items"] == before
        assert any(t["value"] == "Blots" for t in after["image_types"]), (
            "the reload must pick the write up, not serve the previous generation")
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_a_locally_stored_video_is_attached_even_though_the_record_is_sealed(tmp_path):
    """A video rendered AFTER the sweep must still reach the queue.

    Two mechanisms show a reviewer a video and only one reaches the item
    record: the archive capture during the sweep writes `video` onto the
    record, and that record is sealed afterwards (migration 006). Anything
    rendered later -- `image-render-videos`, or the on-demand button -- lands
    in `local_video_jobs`.

    MEASURED 2026-09-15 on the embargoed 2026-09 corpus: 68 videos on disk, 68 named by
    the review manifests, and the queue reported 2, because only 2 had been
    captured during the sweep. Reading the record alone hid the video from
    exactly the items that have one.
    """
    import time as _time
    import hashlib
    from metascience_observatory_image_analysis.review_workbench.videos import digest, snapshot
    c = Catalog(tmp_path / "cache.sqlite3")
    seed(c)
    try:
        r = Repository(c)
        r.refresh("project", "r_old", "image_forensics")
        base = _feed(r)
        target = base["items"][0]["id"]
        run_uid = base["items"][0]["run_id"]
        assert not base["items"][0].get("video"), "the fixture item must start with none"

        content = b'fixture video'
        sha = hashlib.sha256(content).hexdigest()
        media = c.path.parent / 'generated-media/videos/objects'
        media.mkdir(parents=True)
        (media / f'{sha}.mp4').write_bytes(content)
        signature = digest(snapshot(base['items'][0]))
        with c.lock, c.db:
            c.db.executescript("""
create table if not exists local_video_jobs(
 id text primary key, scope text not null, signature text not null,
 renderer text not null, payload text not null, status text not null,
 error text, owner text, lease real, created real not null, updated real not null,
 video_sha text);""")
            c.db.execute(
                "insert into local_video_jobs(id,scope,signature,renderer,payload,status,"
                "created,updated,video_sha) values(?,?,?,?,?,'ready',?,?,?)",
                ("j1", json.dumps([c.state("db_identity"), "project", run_uid, target]),
                 signature, "imported", "{}", _time.time(), _time.time(), sha))

        assert set(r.local_video_items("project")) == {(run_uid, target)}
        after = _feed(r)
        assert [i["id"] for i in after["items"] if i.get("video")] == [target]
        # A ready video in ANOTHER project must not leak into this one.
        with c.lock, c.db:
            c.db.execute(
                "insert into local_video_jobs(id,scope,signature,renderer,payload,status,"
                "created,updated,video_sha) values(?,?,?,?,?,'ready',?,?,?)",
                ("j2", json.dumps([c.state("db_identity"), "other", run_uid, "within:x:IMGDUP-1"]),
                 "sig", "imported", "{}", _time.time(), _time.time(), "1" * 64))
        assert set(r.local_video_items("project")) == {(run_uid, target)}
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_the_lookalike_filter_follows_the_rank_flag(tmp_path):
    """A LOOKALIKE is a MEASURED control failure, and an unmeasured group is not
    one.

    `triage_rank` sets `rank.lookalike` when the unaligned control was measured
    and failed -- the two panels agree about as well unaligned as aligned, so
    the agreement is not specific to the transform -- or when a single channel
    matches a merge containing it across two figures. It moves the sort order
    and never the score.

    The asymmetry is the point, and this test exists to keep it: a group whose
    control was never measured must count as "no", not "yes". Treating absence
    of a measurement as a failure would file a fact about OUR exhibit coverage
    as a fact about the paper -- the mistake `triage_rank`'s own docstring is
    written against.
    """
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "r_old", "image_forensics")
        base = _feed(r)
        total = base["counts"]["items"]
        assert base["lookalike_counts"] == [{"value": "no", "count": total}], (
            "no seeded group has a measured control, so none may be a lookalike")

        target = base["items"][0]["id"]
        for item in r.feed_pages[("project", "r_old", "image_forensics")]:
            if item["id"] == target:
                item["rank"] = {**(item.get("rank") or {}), "lookalike": True}

        tally = {t["value"]: t["count"] for t in _feed(r)["lookalike_counts"]}
        assert tally == {"yes": 1, "no": total - 1}, tally
        only = _feed(r, lookalike="yes")
        assert [i["id"] for i in only["items"]] == [target]
        assert only["pagination"]["total"] == 1
        without = _feed(r, lookalike="no")
        assert target not in {i["id"] for i in without["items"]}
        assert _feed(r, lookalike="all")["pagination"]["total"] == total
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_a_missing_rank_block_is_not_a_lookalike(tmp_path):
    """An item with no rank at all must not be read as flagged."""
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "r_old", "image_forensics")
        _feed(r)  # build the page cache before reaching into it
        for item in r.feed_pages[("project", "r_old", "image_forensics")]:
            item["rank"] = None
        tally = {t["value"]: t["count"] for t in _feed(r)["lookalike_counts"]}
        assert "yes" not in tally, tally
        assert _feed(r, lookalike="yes")["pagination"]["total"] == 0
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_every_dropdown_count_is_faceted_on_the_other_filters(tmp_path):
    """Dan, 2026-09-15: "the numbers in the filter dropdowns should dynamically
    update as other filters are applied."

    A facet's numbers answer "how many would I get if I picked this", given the
    other filters. Two boundaries make that useful rather than confusing:

    * a facet does NOT count its own selection -- otherwise picking "yes" would
      report 0 for "no" and the control could never be un-narrowed;
    * the run SUMMARY (`counts`) stays whole-run, because it feeds the "N items
      in this run" line and the "N saved results exist but none match the
      current filters" message. Both of those mean the run, not the filter.
    """
    c, r = _repo(tmp_path)
    try:
        r.refresh("project", "r_old", "image_forensics")
        base = _feed(r)
        total = base["counts"]["items"]
        page = r.feed_pages[("project", "r_old", "image_forensics")]
        # Two independent facets on disjoint subsets of the run.
        for n, item in enumerate(page):
            item["rank"] = {**(item.get("rank") or {}), "lookalike": n % 2 == 0}
            if n < 10:
                item["image_type"] = "FacetFixture"

        both = _feed(r)
        assert {t["value"]: t["count"] for t in both["image_types"]}["FacetFixture"] == 10
        assert {t["value"]: t["count"] for t in both["lookalike_counts"]}["yes"] == (total + 1) // 2

        # Narrow on image type: the LOOKALIKE counts must shrink to that subset...
        narrowed = _feed(r, image_type="FacetFixture")
        look = {t["value"]: t["count"] for t in narrowed["lookalike_counts"]}
        assert look["yes"] + look["no"] == 10, look
        # ...while the image-type facet keeps reporting its own full base, so the
        # user can widen again.
        assert sum(t["count"] for t in narrowed["image_types"]) == total
        # The run summary is untouched by any of it.
        assert narrowed["counts"]["items"] == total
        # The kind select's own "all" rides the faceted base, not the run.
        assert narrowed["facet_totals"]["kind"] == narrowed["pagination"]["total"] == 10
    finally:
        c.close()
