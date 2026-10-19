"""A comparable snapshot of what the register currently says.

WHY THIS EXISTS. Greg, 2026-08-21: Dan is landing his own changes, and "the
version he created will not have the kind of coverage as ours... we will need
to use our framework for sanity-checking the results."

Merging Dan's work is, in this codebase's own terms, a fix elsewhere -- and
today produced three separate cases of a measured claim being falsified by one
(`9e8058b`, `1bf77a3`, `2650cd6`). After a merge, every number we have measured
is a claim about the code that produced it, not about the corpus. The only
honest way to tell an improvement from a regression is to have written the
before down first.

WHAT IT MUST NOT DO is pass or fail. A snapshot that renders a verdict invites
tuning the threshold; this one reports numbers and the diff between two of
them, and a human decides which direction is good. `n_ambiguous_columns` going
UP after a merge might mean the reader got worse, or that it started detecting
tables it used to skip -- the tool cannot know and must not pretend.
"""
import json
import pathlib
import pytest

from metascience_agent import corpus_state as CS

CORPUS = pathlib.Path("tests/fixtures/papers/high_value_pdfs_to_run_on")


class TestASnapshotIsComparable:
    def test_it_reports_the_measures_we_actually_argue_from(self):
        snap = CS.snapshot_register({"groups": [], "problems": []})
        for key in ("n_groups", "n_values", "n_ambiguous_columns",
                    "roles", "n_stale_cache_warnings"):
            assert key in snap, f"{key} missing from the snapshot"

    def test_an_empty_register_reports_zeros_not_omissions(self):
        """A missing key would read as 'not measured'; zero is a measurement."""
        snap = CS.snapshot_register({"groups": [], "problems": []})
        assert snap["n_groups"] == 0 and snap["n_values"] == 0

    def test_it_counts_roles_so_a_typing_regression_is_visible(self):
        reg = {"groups": [
            {"anchor": {"where": "table"}, "values": [{"role": "p"},
                                                      {"role": "unknown"}]},
            {"anchor": {"where": "table"}, "values": [{"role": "p"}]},
        ], "problems": []}
        snap = CS.snapshot_register(reg)
        assert snap["roles"]["p"] == 2 and snap["roles"]["unknown"] == 1

    def test_a_stale_cache_warning_is_carried_into_the_snapshot(self):
        reg = {"groups": [], "problems": [
            "x.pdf: cached at schema 4, before header depth was read"]}
        assert CS.snapshot_register(reg)["n_stale_cache_warnings"] == 1


class TestTheDiffRefusesToJudge:
    def test_it_reports_direction_without_calling_it_good_or_bad(self):
        before = {"totals": {"n_groups": 100, "roles": {"p": 10}}}
        after = {"totals": {"n_groups": 120, "roles": {"p": 8}}}
        d = CS.diff(before, after)
        assert d["n_groups"]["before"] == 100
        assert d["n_groups"]["after"] == 120
        assert d["n_groups"]["change"] == 20
        assert "verdict" not in d["n_groups"], (
            "a snapshot reports; a human judges")

    def test_a_key_present_in_one_side_only_is_named_not_dropped(self):
        d = CS.diff({"totals": {"a": 1}}, {"totals": {"b": 2}})
        assert "a" in d and "b" in d
        assert d["a"]["after"] is None and d["b"]["before"] is None

    def test_nothing_changed_is_stated_rather_than_empty(self):
        d = CS.diff({"totals": {"n_groups": 5}}, {"totals": {"n_groups": 5}})
        assert d["n_groups"]["change"] == 0

    def test_it_round_trips_through_json(self):
        """The whole point is comparing across a merge, i.e. across files."""
        snap = CS.snapshot_register({"groups": [], "problems": []})
        assert json.loads(json.dumps(snap)) == snap


@pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus not in this checkout")
class TestOnTheRealCorpus:
    def test_it_snapshots_a_real_paper(self):
        d = CORPUS / "10.1001--jamanetworkopen.2023.37679"
        if not d.is_dir():
            pytest.skip("paper not present")
        snap = CS.snapshot_paper(d)
        assert snap["n_groups"] > 0
        assert snap["n_ambiguous_columns"] >= 0
