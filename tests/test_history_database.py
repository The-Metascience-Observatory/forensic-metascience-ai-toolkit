"""Real PostgreSQL acceptance checks, always isolated in a rolled-back schema.

Set METASCIENCE_HISTORY_TEST_DATABASE_URL explicitly to enable this test.
"""

import json
import os
import uuid
from pathlib import Path

import pytest


def test_postgres_history_constraints_and_idempotence(tmp_path):
    url = os.environ.get("METASCIENCE_HISTORY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("explicit PostgreSQL test connection not configured")
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql
    from metascience_agent.analysis_runs import Archive
    from metascience_agent.history_db import sync, migrate

    class Rollback(Exception):
        pass

    with psycopg.connect(url, connect_timeout=10) as conn:
        try:
            with conn.transaction():
                name = "history_test_" + uuid.uuid4().hex[:12]
                conn.execute(sql.SQL("create schema {}").format(sql.Identifier(name)))
                conn.execute(sql.SQL("set local search_path to {}").format(sql.Identifier(name)))
                conn.execute((Path(__file__).parents[1] / "db/schema.sql").read_text())
                migrate(conn)
                archive = Archive(tmp_path)
                for n in (1, 2):
                    execution = archive.execution(
                        "image_forensics", execution_id=f"e{n}", components=["image_forensics"]
                    )
                    item = {
                        "id": "within:p:IMGDUP-1",
                        "paper": {"dir": "p"},
                        "papers": [{"dir": "p"}],
                        "kind": "within",
                        "panels": [],
                    }
                    archive.seal(
                        {
                            "id": f"r{n}",
                            "execution_id": execution["id"],
                            "component": "image_forensics",
                            "paper": "p",
                            "provenance": {"version": "same"},
                        },
                        [item],
                    )
                archive.decide("r1", "within:p:IMGDUP-1", "true_issue", "Acceptance test")
                assert sync(tmp_path, conn) == {"runs": 2, "items": 2, "reviews": 1}
                assert sync(tmp_path, conn) == {"runs": 0, "items": 0, "reviews": 0}
                before = conn.execute(
                    "select run_uid,history_record from runs order by run_uid"
                ).fetchall()
                with pytest.raises(psycopg.Error, match="sealed"):
                    with conn.transaction():
                        conn.execute("update component_items set record='{}'::jsonb")
                with pytest.raises(psycopg.Error, match="sealed"):
                    with conn.transaction():
                        conn.execute("update runs set sealed_digest='changed' where run_uid='r1'")
                with pytest.raises(psycopg.Error):
                    with conn.transaction():
                        conn.execute(
                            "update reviews set run_id=(select id from runs where run_uid='r2')"
                        )
                for statement in ("update reviews set note='rewritten'", "delete from reviews"):
                    with pytest.raises(psycopg.Error, match="append-only"):
                        with conn.transaction():
                            conn.execute(statement)
                with pytest.raises(psycopg.errors.ForeignKeyViolation):
                    with conn.transaction():
                        conn.execute("""insert into reviews(run_id,paper_id,component_item_pk,
                            issue_key,reviewer_id,decision)
                            select r.id,v.paper_id,v.component_item_pk,v.issue_key,v.reviewer_id,v.decision
                            from reviews v cross join runs r where r.run_uid='r2'""")
                assert (
                    conn.execute(
                        "select run_uid,history_record from runs order by run_uid"
                    ).fetchall()
                    == before
                )
                assert (
                    conn.execute("select count(*) from published_component_items").fetchone()[0]
                    == 0
                )
                # The archive is also consumed by existing report readers/stats.
                # A later compatibility push must keep the same report identity.
                from metascience_agent import db_push
                paper = tmp_path / "p"
                paper.mkdir()
                document = {
                    "schema_version": "2.0", "run_id": "report1",
                    "adjudication": {"ran": True, "verdict": "unresolved"},
                    "findings": [{"finding_id": "f_test", "producer": "tool_expert",
                                  "outcome": "problem", "severity": 5,
                                  "description": "Original saved report finding"}],
                }
                job = archive.execution("comprehensive", components=["comprehensive"])
                archive.seal({"id": "report1", "execution_id": job["id"],
                              "component": "comprehensive", "paper": "p",
                              "document": document, "provenance": {}})
                sync(tmp_path, conn)
                assert conn.execute("select count(*) from findings").fetchone()[0] == 1
                for _ in range(2):
                    assert db_push.push_run(conn, document, {}, paper, tmp_path.name)["run_uid"] == "report1"
                assert conn.execute("select count(*) from runs").fetchone()[0] == 3
                fetched = db_push.fetch_paper_runs(paper, corpus=tmp_path.name, conn=conn)
                assert len(fetched["runs"]) == 1  # Two image runs are not reports.
                assert fetched["runs"][0]["doc"]["findings"] == document["findings"]
                # Local tampering is detected before any database mutation.
                path = archive.base / "runs/r1.json"
                changed = json.loads(path.read_text())
                changed["items"] = []
                path.write_text(json.dumps(changed))
                with pytest.raises(ValueError, match="digest"):
                    sync(tmp_path, conn)
                raise Rollback()
        except Rollback:
            pass


def test_a_null_column_is_an_empty_object_not_a_crash():
    """`runs.meta` and `runs.history_record` are nullable and often NULL.

    MEASURED 2026-09-12 on the local shared database: 3,685 of 24,473 rows
    have no `history_record` and 16,908 no `meta`. Reading `.get` off one
    aborted `push_run` for all 114 papers of the embargoed 2026-09 corpus -- a whole
    corpus of screening judgments stranded, visible only as an AttributeError
    inside a per-paper pending reason.
    """
    from metascience_agent.db_push import _previous_state

    assert _previous_state(None) == ({}, {})
    assert _previous_state((None, None)) == ({}, {})
    assert _previous_state(({"content_digest": "d"}, None)) == ({"content_digest": "d"}, {})
    assert _previous_state((None, '{"document": {"run_id": "r"}}')) == (
        {}, {"document": {"run_id": "r"}})
    # A column holding text that is not JSON is still not a crash.
    assert _previous_state(("not json", "not json")) == ({}, {})


def _partial_document(run_id):
    """A tools_only report as parallel.py seals it under `partial_review`."""
    return {
        "schema_version": "2.0", "run_id": run_id,
        "pipeline": {"name": "tools_only", "complete_review": False,
                     "modules": [{"use": "tools_agent"}]},
        "adjudication": {"ran": False},
        "findings": [{"finding_id": "f_partial", "producer": "tool_expert",
                      "technique": "grim_check", "outcome": "problem",
                      "severity": 4, "provisional_severity": 4,
                      "severity_is_provisional": True,
                      "tool_verdict": {"tool": "grim_check", "severity": "impossible"},
                      "description": "Mean 3.53 is not attainable with n=29"}],
    }


def test_partial_review_findings_are_uploaded_with_their_own_kind():
    """Without a database: the rows the sync sends for a partial run.

    It used to send a `partial_review` run's run row (kind `component`) and
    no findings at all, so the workbench showed an empty run.
    """
    from metascience_agent.history_db import RUN_KINDS, _sync_report_findings

    class Cursor:
        def __init__(self):
            self.sent = []
        def execute(self, sql, params=()):
            self.sent.append((sql, params))
        def fetchall(self):
            return []

    runs = [{"id": "r_part", "component": "partial_review", "paper": "p",
             "document": _partial_document("r_part")},
            {"id": "r_img", "component": "image_forensics", "paper": "p",
             "document": {"findings": [{"finding_id": "never"}]}}]
    cur = Cursor()
    _sync_report_findings(cur, runs, {"r_part": 7, "r_img": 8}, {"p": 3})
    rows = json.loads(cur.sent[-1][1][0])
    assert [(r["run"], r["record"]["finding_id"]) for r in rows] == [(7, "f_partial")]
    assert RUN_KINDS["partial_review"] == "partial_review"
    assert RUN_KINDS["comprehensive"] == "full_review"


def test_postgres_partial_review_findings_reach_the_database(tmp_path):
    url = os.environ.get("METASCIENCE_HISTORY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("explicit PostgreSQL test connection not configured")
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql
    from metascience_agent.analysis_runs import Archive
    from metascience_agent.history_db import sync, migrate

    class Rollback(Exception):
        pass

    with psycopg.connect(url, connect_timeout=10) as conn:
        try:
            with conn.transaction():
                name = "history_test_" + uuid.uuid4().hex[:12]
                conn.execute(sql.SQL("create schema {}").format(sql.Identifier(name)))
                conn.execute(sql.SQL("set local search_path to {}").format(sql.Identifier(name)))
                conn.execute((Path(__file__).parents[1] / "db/schema.sql").read_text())
                migrate(conn)
                archive = Archive(tmp_path)
                job = archive.execution("partial_review", components=["partial_review"])
                archive.seal({"id": "r_part", "execution_id": job["id"],
                              "component": "partial_review", "paper": "p",
                              "document": _partial_document("r_part"), "provenance": {}})
                sync(tmp_path, conn)
                assert conn.execute(
                    "select kind,component from runs where run_uid='r_part'"
                ).fetchone() == ("partial_review", "partial_review")
                assert conn.execute(
                    "select f.finding_id,f.severity_is_provisional,f.tool_verdict->>'tool' "
                    "from findings f join runs r on r.id=f.run_id where r.run_uid='r_part'"
                ).fetchall() == [("f_partial", True, "grim_check")]
                sync(tmp_path, conn)  # idempotent: no conflict, no duplicate
                assert conn.execute("select count(*) from findings").fetchone()[0] == 1
                raise Rollback()
        except Rollback:
            pass
