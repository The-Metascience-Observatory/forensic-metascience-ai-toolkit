"""`workbench.review_rescope`: recovering decisions stranded in `(unscoped)`.

The hazard this guards is specific. `IMGDUP-N` is POSITIONAL -- an index into
one run's findings list -- so binding a decision to the wrong run attaches a
human's "false positive" to a different finding. That is worse than losing the
decision, so the rule is a provable identity match on the issue key, never a
pick by recency, liveness or count.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.workbench import review_rescope as RR


class FakeCursor:
    """Just enough of a psycopg cursor: canned owners per (paper, key)."""

    def __init__(self, owners):
        self.owners = owners
        self._rows: list = []

    def execute(self, sql, args=()):
        if "component_items" in sql:
            _corpus, paper, like = args
            short = like.lstrip("%:")
            self._rows = self.owners.get((paper, short), [])
        else:  # pragma: no cover - not exercised by the plan path
            self._rows = []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    def __init__(self, owners):
        self._cur = FakeCursor(owners)

    def cursor(self):
        return self._cur


def _review(tmp: Path, paper: str, issues: dict, run="(unscoped)") -> None:
    d = tmp / paper
    d.mkdir(parents=True, exist_ok=True)
    (d / "review.json").write_text(json.dumps({
        "paper": {"status": "unreviewed"},
        "runs": {run: {"issues": issues}},
        "issues": issues if run == "(unscoped)" else {},
        "schema_version": "2.0",
    }))


DECISION = {"decision": "false_positive_other", "reviewer": "A Reviewer",
            "at": "2026-09-08T23:56:31Z"}


def _owner(run_id, run_uid, paper, key, kind="intra_panel_clone", record=None):
    return (run_id, run_uid, f"within:{paper}:{key}",
            record if record is not None else {"detector_kind": kind})


class TestOnlyAProvableMatchIsRebound:
    def test_exactly_one_live_owner_is_rescoped(self, tmp_path):
        _review(tmp_path, "10.x--a", {"image:IMGDUP-11": DECISION})
        conn = FakeConn({("10.x--a", "IMGDUP-11"):
                         [_owner(7, "legacy_run_abc", "10.x--a", "IMGDUP-11")]})
        pl = RR.plan(tmp_path, "corp", conn)
        assert pl["counts"] == {RR.RESCOPED: 1}
        act = pl["actions"][0]
        assert act["run_id"] == 7 and act["run_uid"] == "legacy_run_abc"
        assert act["item_uid"] == "within:10.x--a:IMGDUP-11"
        assert act["detector_kind"] == "intra_panel_clone"

    def test_several_live_owners_is_ambiguous_and_untouched(self, tmp_path):
        """The key no longer identifies a finding. Guessing here is exactly
        the failure mode this module exists to avoid."""
        _review(tmp_path, "10.x--b", {"image:IMGDUP-1": DECISION})
        conn = FakeConn({("10.x--b", "IMGDUP-1"): [
            _owner(1, "ar_one", "10.x--b", "IMGDUP-1"),
            _owner(2, "ar_two", "10.x--b", "IMGDUP-1"),
        ]})
        pl = RR.plan(tmp_path, "corp", conn)
        assert pl["counts"] == {RR.AMBIGUOUS: 1}
        assert pl["actions"][0]["candidates"] == ["ar_one", "ar_two"]
        assert "run_id" not in pl["actions"][0]

    def test_no_live_owner_is_unowned_not_an_error(self, tmp_path):
        """The run was retired and nothing replaced it. Unrecoverable is a
        fact about the data, not a failure of the tool."""
        _review(tmp_path, "10.x--c", {"image:IMGDUP-3": DECISION})
        pl = RR.plan(tmp_path, "corp", FakeConn({}))
        assert pl["counts"] == {RR.UNOWNED: 1}
        assert "run_id" not in pl["actions"][0]

    def test_a_retired_item_record_is_a_tombstone_not_a_candidate(self, tmp_path):
        _review(tmp_path, "10.x--d", {"image:IMGDUP-2": DECISION})
        conn = FakeConn({("10.x--d", "IMGDUP-2"): [
            _owner(3, "ar_dead", "10.x--d", "IMGDUP-2",
                   record={"retired": True, "detector_kind": "transformed_match"}),
        ]})
        assert RR.plan(tmp_path, "corp", conn)["counts"] == {RR.UNOWNED: 1}

    def test_a_decision_already_scoped_is_left_alone(self, tmp_path):
        _review(tmp_path, "10.x--e", {"image:IMGDUP-1": DECISION},
                run="r_already_named")
        pl = RR.plan(tmp_path, "corp", FakeConn({}))
        assert pl["counts"] == {RR.ALREADY: 1}
        assert pl["actions"][0]["run"] == "r_already_named"

    def test_an_entry_with_no_decision_is_not_an_action(self, tmp_path):
        _review(tmp_path, "10.x--f", {"image:IMGDUP-1": {"reviewer": "A", "at": "x"}})
        assert RR.plan(tmp_path, "corp", FakeConn({}))["counts"] == {}


class TestTheRecoveredRowSaysItWasRecovered:
    def test_apply_writes_provenance_so_a_reader_can_tell(self, tmp_path):
        """A recovered decision and one made against a run the reviewer
        actually saw must not look identical in the shared record."""
        _review(tmp_path, "10.x--g", {"image:IMGDUP-11": DECISION})
        conn = FakeConn({("10.x--g", "IMGDUP-11"):
                         [_owner(7, "legacy_run_abc", "10.x--g", "IMGDUP-11")]})
        pl = RR.plan(tmp_path, "corp", conn)
        inserted: list = []

        class RecordingCursor(FakeCursor):
            def execute(self, sql, args=()):
                if sql.lstrip().startswith("insert into reviews"):
                    inserted.append(args)
                    self._rows = []
                elif "from papers p join corpora" in sql:
                    self._rows = [(42,)]
                elif "select decision from reviews" in sql or "from findings" in sql:
                    self._rows = []
                else:
                    super().execute(sql, args)

        class RecordingConn(FakeConn):
            def __init__(self):
                self._cur = RecordingCursor({})

        monkey = RecordingConn()
        import forensic_metascience_ai_toolkit.db_push as dbp
        real = dbp._user_for
        dbp._user_for = lambda cur, name: 2
        try:
            out = RR.apply(pl, monkey)
        finally:
            dbp._user_for = real
        assert out["written"] == 1 and not out["errors"]
        extra = json.loads(inserted[0][6])
        assert extra["rescoped_from"] == "(unscoped)"
        assert extra["matched_item_uid"] == "within:10.x--g:IMGDUP-11"

    def test_apply_ignores_ambiguous_and_unowned(self, tmp_path):
        pl = {"corpus": "corp", "actions": [
            {"outcome": RR.AMBIGUOUS, "paper": "p", "issue_key": "k"},
            {"outcome": RR.UNOWNED, "paper": "p", "issue_key": "k"},
            {"outcome": RR.ALREADY, "paper": "p", "issue_key": "k"},
        ]}
        assert RR.apply(pl, FakeConn({}))["written"] == 0
