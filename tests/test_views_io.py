"""views.json: who opened the results page, and what a missing record is not.

Every assertion here is about a distinction the yes/no column would otherwise
collapse. A view is not a review; an unreadable file is not an unviewed paper;
and an absent file means nothing was recorded, not that nobody looked.
"""
import json

from forensic_metascience_ai_toolkit.views_io import (
    VIEWS_NAME, empty_views, load_views, merge_view, record_view,
)


def test_an_absent_file_is_not_a_view_and_does_not_raise(tmp_path):
    v = load_views(tmp_path)
    assert v["n_views"] == 0
    assert v["viewers"] == []
    assert v["first_at"] is None
    assert not v.get("unreadable")


def test_the_first_view_stamps_both_ends(tmp_path):
    v = record_view(tmp_path, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
    assert v["n_views"] == 1
    assert v["first_at"] == "2026-08-22T10:00:00Z"
    assert v["last_at"] == "2026-08-22T10:00:00Z"
    assert v["viewers"] == [{"name": "Dan Elton",
                             "first_at": "2026-08-22T10:00:00Z",
                             "last_at": "2026-08-22T10:00:00Z", "n": 1}]
    assert json.loads((tmp_path / VIEWS_NAME).read_text())["n_views"] == 1


def test_a_second_view_moves_last_at_and_never_first_at(tmp_path):
    record_view(tmp_path, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
    v = record_view(tmp_path, viewer="Dan Elton", at="2026-08-22T18:30:00Z")
    assert v["n_views"] == 2
    # When this paper was FIRST opened is the fact a reader wants when the
    # last view was five minutes ago.
    assert v["first_at"] == "2026-08-22T10:00:00Z"
    assert v["last_at"] == "2026-08-22T18:30:00Z"
    assert len(v["viewers"]) == 1
    assert v["viewers"][0]["n"] == 2


def test_a_second_viewer_does_not_evict_the_first(tmp_path):
    record_view(tmp_path, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
    v = record_view(tmp_path, viewer="Other Person",
                    at="2026-08-22T11:00:00Z")
    assert [r["name"] for r in v["viewers"]] == ["Dan Elton", "Other Person"]
    assert v["n_views"] == 2


def test_an_anonymous_viewer_is_null_not_the_word_anonymous(tmp_path):
    # The reviewer chip is a free-text box, so "anonymous" is a name somebody
    # could type. A sentinel that collides with real data is not a sentinel.
    v = record_view(tmp_path, viewer="   ", at="2026-08-22T10:00:00Z")
    assert v["viewers"] == [{"name": None, "first_at": "2026-08-22T10:00:00Z",
                             "last_at": "2026-08-22T10:00:00Z", "n": 1}]
    again = record_view(tmp_path, viewer=None, at="2026-08-22T12:00:00Z")
    assert len(again["viewers"]) == 1
    assert again["viewers"][0]["n"] == 2


def test_a_named_and_an_anonymous_view_are_different_viewers(tmp_path):
    record_view(tmp_path, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
    v = record_view(tmp_path, viewer=None, at="2026-08-22T10:05:00Z")
    assert [r["name"] for r in v["viewers"]] == ["Dan Elton", None]


def test_an_unreadable_file_is_not_an_unviewed_paper(tmp_path):
    (tmp_path / VIEWS_NAME).write_text("{ this is not json")
    loaded = load_views(tmp_path)
    assert loaded["unreadable"] is True
    assert loaded["n_views"] == 0


def test_an_unreadable_file_is_not_overwritten(tmp_path):
    # The view is lost; whatever the truncated file still holds is not.
    (tmp_path / VIEWS_NAME).write_text("{ this is not json")
    out = record_view(tmp_path, viewer="Dan Elton")
    assert out["unreadable"] is True
    assert (tmp_path / VIEWS_NAME).read_text() == "{ this is not json"


def test_the_write_leaves_no_temp_litter(tmp_path):
    record_view(tmp_path, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
    assert {p.name for p in tmp_path.iterdir()} == {VIEWS_NAME, ".views.lock"}


def test_a_hand_written_1_0_record_round_trips(tmp_path):
    # Older/other writers may store only `at` on a viewer row.
    (tmp_path / VIEWS_NAME).write_text(json.dumps({
        "schema_version": "1.0",
        "viewers": [{"name": "Dan Elton", "at": "2026-08-01T09:00:00Z"}]}))
    v = load_views(tmp_path)
    assert v["n_views"] == 1
    assert v["first_at"] == "2026-08-01T09:00:00Z"
    assert v["viewers"][0]["last_at"] == "2026-08-01T09:00:00Z"


def test_unknown_top_level_keys_survive_a_merge(tmp_path):
    # An older workbench round-tripping a newer file must not delete its
    # fields.
    merged = merge_view({"schema_version": "1.0", "future_key": {"a": 1}},
                        viewer="Dan Elton", at="2026-08-22T10:00:00Z")
    assert merged["future_key"] == {"a": 1}


def test_the_empty_document_is_a_document(tmp_path):
    assert empty_views()["schema_version"] == "1.0"
    assert empty_views()["viewers"] == []


def test_the_same_open_recorded_twice_counts_once(tmp_path):
    # A defeated latch in the browser, or a retried POST. One person opening
    # one paper once must not become two views.
    record_view(tmp_path, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
    v = record_view(tmp_path, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
    assert v["n_views"] == 1
    assert v["viewers"][0]["n"] == 1


def test_a_missing_paper_directory_is_refused_not_created(tmp_path):
    # `webapp_index.looks_like_paper` calls any non-empty directory a paper,
    # so conjuring one would invent a paper nobody fetched.
    missing = tmp_path / "10.1234--nope"
    out = record_view(missing, viewer="Dan Elton")
    assert out["recorded"] is False
    assert not missing.exists()


def test_a_name_is_bounded_and_stripped_of_control_characters(tmp_path):
    v = record_view(tmp_path, viewer="Dan\u0000 Elton" + "x" * 500,
                    at="2026-08-22T10:00:00Z")
    name = v["viewers"][0]["name"]
    assert "\u0000" not in name
    assert len(name) <= 120


def test_a_view_does_not_create_a_review_file(tmp_path):
    record_view(tmp_path, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
    assert not (tmp_path / "review.json").exists()


def test_a_view_leaves_an_existing_review_file_byte_identical(tmp_path):
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"schema_version": "2.0",
                                  "paper": {"status": "complete",
                                            "reviewed_by": "Dan Elton"}}))
    before = review.read_bytes()
    record_view(tmp_path, viewer="Someone Else", at="2026-08-22T10:00:00Z")
    assert review.read_bytes() == before
