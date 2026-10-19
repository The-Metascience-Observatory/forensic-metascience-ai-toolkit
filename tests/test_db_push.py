"""db_push: named refusals, replace-within-run SQL, the pending journal.

No live Postgres in CI: the connection is a fake that records every
statement, so the tests pin the SQL SEMANTICS (replace-within-run delete,
the record-distinct upsert gate, identity resolution order, sync_state)
without a server. Live verification against a real Neon URL is a
deployment step, not a unit test.
"""

import json
from pathlib import Path

import pytest

from metascience_agent import db_push as D

# Bound at collection time, BEFORE the autouse `_no_live_findings_db` guard
# replaces the module attribute -- the parser tests need the real function.
_real_dotenv_url = D._dotenv_url


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        self.conn.executed.append((" ".join(sql.split()), params))
        for probe, result in self.conn.script:
            if probe in sql:
                self.conn.last = result
                return
        self.conn.last = None

    def fetchone(self):
        return self.conn.last

    def fetchall(self):
        return []


class FakeConn:
    def __init__(self, script):
        self.script = script      # [(sql substring, fetchone result), ...]
        self.executed = []
        self.last = None

    def cursor(self):
        return FakeCursor(self)

    def transaction(self):
        conn = self

        class _Tx:
            def __enter__(self):
                return conn

            def __exit__(self, *a):
                return False
        return _Tx()

    def close(self):
        pass


def _paper(tmp_path, with_review=None):
    paper = tmp_path / "corpus" / "10.1234--x"
    run = paper / "forensic_review"
    run.mkdir(parents=True)
    doc = {"schema_version": "2.0", "paper_id": "10.1234--x",
           "run_id": "r_" + "a" * 16,
           "paper_metadata": {"doi": "https://doi.org/10.1234/X",
                              "title": "T", "year": 2020},
           "channels": {"tool_expert": {"state": "ran"}},
           "findings": [
               {"finding_id": "f_" + "1" * 16, "producer": "tool_expert",
                "technique": "grim_check", "outcome": "problem",
                "severity": 5, "impossible": True,
                "legacy": {"original_id": "numeric:t1"}},
           ],
           "adjudication": {"ran": True, "verdict": "unresolved"}}
    (run / "findings.v2.json").write_text(json.dumps(doc))
    if with_review is not None:
        (paper / "review.json").write_text(json.dumps(with_review))
    return paper


def _script():
    return [("select id from corpora", (7,)),
            ("select id from papers where corpus_id=%s and dir=%s", (11,)),
            ("insert into runs", (99,))]


class TestUrlResolution:
    """resolve_db_url: explicit > $METASCIENCE_DB_URL > .env, local hosts only.
    The autouse `_no_live_findings_db` guard clears every channel, so each
    test opens exactly the one it is about."""

    def test_explicit_arg_wins(self, monkeypatch):
        monkeypatch.setenv(D.DB_URL_ENV, "postgres://localhost/env")
        assert D.resolve_db_url("postgres://localhost/arg") == "postgres://localhost/arg"

    def test_dotenv_is_the_last_fallback(self, monkeypatch):
        monkeypatch.setattr(D, "_dotenv_url", lambda: "postgres://localhost/dotenv")
        assert D.resolve_db_url() == "postgres://localhost/dotenv"

    def test_dotenv_parser_reads_the_canonical_name_and_strips_quotes(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text('# comment\nOTHER=1\nMETASCIENCE_DB_URL="postgres://canonical"\n')
        assert _real_dotenv_url(env) == "postgres://canonical"
        env.write_text("NEON_DB_URL=postgres://alias\n")
        assert _real_dotenv_url(env) is None, "the retired Neon alias is not read"

    def test_missing_dotenv_is_none(self, tmp_path):
        assert _real_dotenv_url(tmp_path / "absent.env") is None

    def test_the_suite_guard_hides_any_real_url(self):
        """Proves the autouse conftest guard fires: on a live-wired machine
        (a real URL in the repo .env) an unguarded resolve would return it,
        and every unit test reaching auto_push would push into the real
        findings store."""
        assert D.resolve_db_url() is None


class TestRefusals:
    def test_no_url_is_a_named_refusal(self, monkeypatch):
        monkeypatch.delenv(D.DB_URL_ENV, raising=False)
        with pytest.raises(D.DbUnavailable) as e:
            D._connect(None)
        assert D.DB_URL_ENV in str(e.value)

    def test_missing_driver_names_the_extra(self, monkeypatch):
        import sys
        monkeypatch.setitem(sys.modules, "psycopg", None)
        with pytest.raises(D.DbUnavailable) as e:
            D._connect("postgres://localhost/x")
        assert "forensic-metascience-ai-toolkit[db]" in str(e.value)

    def test_connections_autocommit_so_writes_survive_close(self, monkeypatch):
        # Without autocommit push_run's first SELECT opened an implicit
        # transaction, its `transaction()` block became a savepoint, and
        # close() rolled every push back while the CLI reported success.
        import sys
        import types
        calls = []
        fake = types.SimpleNamespace(connect=lambda url, **kw: calls.append(kw))
        monkeypatch.setitem(sys.modules, "psycopg", fake)
        D._connect("postgres://localhost/x")
        D._connect("postgres://localhost/x", connect_timeout=3)
        assert [kw.get("autocommit") for kw in calls] == [True, True]


class TestPushSemantics:
    def test_replace_within_run_and_the_distinct_gate(self, tmp_path):
        paper = _paper(tmp_path)
        conn = FakeConn(_script())
        recs = D.push_paper(paper, conn=conn)
        sql = [s for s, _ in conn.executed]
        assert recs[0]["n_findings"] == 1
        assert any("delete from findings where run_id=%s and finding_id != all"
                   in s for s in sql), "stale rows must be deleted per run"
        assert any("record is distinct from excluded.record" in s
                   for s in sql), "no-op replays must not rewrite records"
        assert any("insert into sync_state" in s for s in sql)
        assert not any("kind='screen'" in s or "'screen'" in str(p)
                       for s, p in conn.executed), \
            "file pushes never touch screen rows"

    def test_doi_is_normalized_before_identity(self, tmp_path):
        paper = _paper(tmp_path)
        conn = FakeConn([              # both identity lookups miss -> insert
            ("select id from corpora", (7,)),
            ("insert into papers", (11,)),
            ("insert into runs", (99,)),
        ])
        D.push_paper(paper, conn=conn)
        inserts = [p for s, p in conn.executed
                   if s.startswith("insert into papers")]
        assert inserts and inserts[0][2] == "10.1234/x", \
            "resolver prefix stripped, lowercased"

    def test_doi_promotion_updates_the_same_row(self, tmp_path):
        paper = _paper(tmp_path)
        # dir lookup misses; doi lookup hits -> the row gains the dir
        conn = FakeConn([
            ("select id from corpora", (7,)),
            ("select id from papers where corpus_id=%s and dir=%s", None),
            ("select id from papers where corpus_id=%s and lower(doi)=%s", (42,)),
            ("update papers set dir=%s", (42,)),
            ("insert into runs", (99,)),
        ])
        D.push_paper(paper, conn=conn)
        sql = [s for s, _ in conn.executed]
        assert any(s.startswith("update papers set dir=%s") for s in sql)
        assert not any(s.startswith("insert into papers") for s in sql)

    def test_orphaned_review_verdicts_are_reported(self, tmp_path):
        paper = _paper(tmp_path, with_review={
            "schema_version": "1.1",
            "issues": {"numeric:t1": {"decision": "false_positive"},
                       "numeric:ghost": {"decision": "correct_minor"}}})
        conn = FakeConn(_script())
        recs = D.push_paper(paper, conn=conn)
        assert recs[0]["review_orphans"] == ["numeric:ghost"]


class TestQueryFindings:
    """The SQL twin of the file-scan findings query. The LIVE drift check
    (60/60 identical rows on cerebrolysin_papers, 2026-08-21) is the real
    equivalence proof; these pin the semantics the SQL must keep."""

    def _sql(self, **kw):
        conn = FakeConn([])
        D.query_findings("my_corpus", conn=conn, **kw)
        assert len(conn.executed) == 1
        return conn.executed[0]

    def test_problem_rows_only_and_discarded_excluded(self):
        sql, params = self._sql()
        assert "f.outcome = 'problem'" in sql
        assert "coalesce(f.adjudication_action, 'kept') <> 'discarded'" in sql
        assert params == ["my_corpus"], "corpus is the only default filter"

    def test_all_runs_not_current_runs(self):
        """The file scan reads every findings.v2.json, so the DB answer must
        cover every run too -- joining through current_runs here would make
        online and offline mode silently disagree."""
        sql, _ = self._sql()
        assert "join runs r on" in sql and "current_runs" not in sql

    def test_filters_are_parameterized_never_interpolated(self):
        sql, params = self._sql(technique="grim_check", journal="Lancet",
                                min_severity=5, year=2020,
                                producer="tool_expert", impossible_only=True)
        assert "Lancet" not in sql and "grim_check" not in sql
        assert params == ["my_corpus", "grim_check", "tool_expert", 5,
                          "%Lancet%", 2020]
        assert "and f.impossible" in sql


class TestBestEffort:
    def test_auto_push_never_raises_and_journals_the_failure(self, tmp_path,
                                                             monkeypatch):
        paper = _paper(tmp_path)
        monkeypatch.setenv(D.DB_URL_ENV, "postgres://localhost/unreachable")

        def boom(url):
            raise ConnectionError("no route to neon")
        monkeypatch.setattr(D, "_connect", boom)
        out = D.auto_push(paper, paper / "forensic_review")
        assert out["pending"] is True
        pending = (paper.parent / D.PENDING_NAME).read_text().splitlines()
        assert len(pending) == 1
        assert "no route to neon" in pending[0]

    def test_auto_push_is_silent_without_the_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv(D.DB_URL_ENV, raising=False)
        assert D.auto_push(_paper(tmp_path), tmp_path) is None

    def test_retry_pending_drains_and_keeps_failures(self, tmp_path,
                                                     monkeypatch):
        paper = _paper(tmp_path)
        root = paper.parent
        D.record_pending(root, paper, "first failure")
        D.record_pending(root, root / "missing_paper", "first failure")
        monkeypatch.setattr(D, "_connect", lambda url: FakeConn(_script()))

        real = D.push_paper

        def selective(p, **kw):
            if "missing_paper" in str(p):
                raise ConnectionError("still down")
            return real(p, **kw)
        monkeypatch.setattr(D, "push_paper", selective)
        rec = D.retry_pending(root, db_url="postgres://localhost/x")
        assert rec == {"retried": 1, "remaining": 1}
        left = (root / D.PENDING_NAME).read_text()
        assert "missing_paper" in left


class TestPushReviews:
    """The reviews table finally gets WRITTEN (until 2026-08-21 only the
    orphan report existed, reading as though verdicts were mirrored)."""

    def _paper(self, tmp_path, entry=None):
        paper = tmp_path / "c" / "10.9--r"
        paper.mkdir(parents=True)
        entry = entry or {"decision": "false_positive", "reviewer": "dan",
                          "at": "2026-08-21T10:00:00Z"}
        (paper / "review.json").write_text(json.dumps({
            "schema_version": "2.0",
            "runs": {"forensic_review_x": {"issues": {"f_" + "9" * 16: entry},
                                           "paper": {}}},
        }))
        return paper

    def test_a_new_verdict_inserts_run_scoped(self, tmp_path):
        conn = FakeConn([
            ("select id from runs where paper_id", (77,)),
            ("select id from users where legacy_name", (5,)),
            ("select id from findings where run_id", (321,)),
        ])
        rec = D.push_reviews(conn, 11, self._paper(tmp_path))
        assert rec["pushed"] == 1 and rec["unmatched"] == []
        ins = [(s, p) for s, p in conn.executed
               if s.startswith("insert into reviews")]
        assert len(ins) == 1
        sql, params = ins[0]
        assert params[0] == 77 and params[1] == 11      # run + paper
        assert params[2] == 321                          # finding_pk joined
        assert params[4] == 5 and params[5] == "false_positive"

    def test_an_unchanged_verdict_inserts_nothing(self, tmp_path):
        conn = FakeConn([
            ("select id from runs where paper_id", (77,)),
            ("select id from users where legacy_name", (5,)),
            ("select decision, submitted_to_pubpeer",
             ("false_positive", False, False, None, None)),
        ])
        rec = D.push_reviews(conn, 11, self._paper(tmp_path))
        assert rec == {"pushed": 0, "unchanged": 1, "unmatched": []}
        assert not any(s.startswith("insert into reviews")
                       for s, _ in conn.executed)

    def test_an_unknown_run_is_reported_never_dropped(self, tmp_path):
        conn = FakeConn([])          # the run-name lookup misses
        rec = D.push_reviews(conn, 11, self._paper(tmp_path))
        assert rec["pushed"] == 0
        assert rec["unmatched"] == ["forensic_review_x:" + "f_" + "9" * 16]

    def test_an_unknown_reviewer_gets_a_legacy_user(self, tmp_path):
        conn = FakeConn([
            ("select id from runs where paper_id", (77,)),
            ("insert into users", (44,)),
        ])
        rec = D.push_reviews(conn, 11, self._paper(tmp_path))
        assert rec["pushed"] == 1
        assert any(s.startswith("insert into users") for s, _ in conn.executed)


class TestMirrorReview:
    def test_never_raises_and_names_the_skip(self, tmp_path, monkeypatch):
        assert D.mirror_review(tmp_path) == {"skipped": "no database URL"}
        monkeypatch.setenv(D.DB_URL_ENV, "postgres://localhost/x")
        monkeypatch.setattr(D, "_connect",
                            lambda url=None, **kwargs: (_ for _ in ()).throw(
                                ConnectionError("down")))
        out = D.mirror_review(tmp_path)
        assert "ConnectionError" in out["error"]


# --- fetch_paper_runs: the READ twin, for a paper with no run on this disk ---

class _ReadCursor:
    """Two-statement fake: the runs join, then the findings fetch."""

    def __init__(self, runs, findings):
        self.runs, self.findings, self.sql = runs, findings, []

    def execute(self, sql, params=None):
        self.sql.append((" ".join(sql.split()), params))
        self._last = self.findings if "from findings" in sql else self.runs

    def fetchall(self):
        return list(self._last)


class _ReadConn:
    def __init__(self, runs, findings):
        self.cur = _ReadCursor(runs, findings)
        self.closed = False

    def cursor(self):
        return self.cur

    def close(self):
        self.closed = True


def _run_row(corpus, pdir, pk, name, sev=3, verdict="does_not_reconcile"):
    return (corpus, pdir, pk, f"r_{pk:016x}", name, "full_review", "complete",
            verdict, sev, "1.12.0", "2026-09-01T12:28:42+00:00", "recorded",
            11.63, {"version": "1.12.0"})


def _meta_paper(tmp_path, doi="10.1002/jfa2.70171"):
    paper = tmp_path / "FMT-reports_derik-flagged_2026-09-01" / "10.1002--jfa2.70171"
    paper.mkdir(parents=True)
    (paper / "metadata.json").write_text(json.dumps({"doi": doi, "title": "T"}))
    return paper


def test_fetch_paper_runs_unavailable_when_no_url_never_raises(tmp_path):
    paper = _meta_paper(tmp_path)
    got = D.fetch_paper_runs(paper)
    assert got["state"] == "unavailable"
    assert got["runs"] == []
    assert "no database URL" in got["detail"]


def test_fetch_paper_runs_miss_is_named_not_empty(tmp_path):
    paper = _meta_paper(tmp_path)
    conn = _ReadConn(runs=[], findings=[])
    got = D.fetch_paper_runs(paper, conn=conn)
    assert got["state"] == "miss"
    assert "10.1002/jfa2.70171" in got["detail"]
    # a caller-owned connection is not closed by the reader
    assert conn.closed is False


def test_fetch_paper_runs_doi_hit_carries_corpus_and_full_records(tmp_path):
    paper = _meta_paper(tmp_path)
    rec = {"finding_id": "f_1", "outcome": "problem", "severity": 3,
           "producer": "tool_expert", "technique": "check_count_percent",
           "title": "Wear-time weeks", "anchors": [{"quote": "q",
                                                    "passage_id": "a"}]}
    conn = _ReadConn(
        runs=[_run_row("fmt-derik-flagged", "10.1002--jfa2.70171", 1837,
                       "forensic_review_opus_v1.12.0")],
        findings=[(1837, rec), (1837, json.dumps({"finding_id": "f_2",
                                                  "outcome": "consistent"})),
                  (1837, "not json")])
    got = D.fetch_paper_runs(paper, conn=conn)
    assert got["state"] == "hit"
    (run,) = got["runs"]
    # the local project folder is NOT the DB corpus name: matched by DOI
    assert run["matched_by"] == "doi"
    assert run["corpus"] == "fmt-derik-flagged"
    assert run["name"] == "forensic_review_opus_v1.12.0"
    doc = run["doc"]
    assert doc["run_id"] == run["run_uid"]
    assert doc["adjudication"] == {"ran": True, "verdict": "does_not_reconcile",
                                   "paper_severity": 3}
    # dict and text jsonb both land; an unparseable row is dropped, not fatal
    assert [f["finding_id"] for f in doc["findings"]] == ["f_1", "f_2"]
    # the query was parameterised on both identities
    sql, params = conn.cur.sql[0]
    assert "lower(p.doi)" in sql and "p.dir" in sql
    assert params == ("FMT-reports_derik-flagged_2026-09-01",
                      "10.1002--jfa2.70171", "10.1002/jfa2.70171",
                      "10.1002/jfa2.70171")
    # and the findings fetch asked for exactly that run
    assert conn.cur.sql[1][1] == ([1837],)


def test_fetch_paper_runs_dir_match_excludes_doi_twins(tmp_path):
    """30 of 646 DOIs sit in two corpora: an exact (corpus, dir) hit must
    not drag another corpus's run into this paper's picker."""
    paper = _meta_paper(tmp_path)
    corpus = paper.parent.name
    conn = _ReadConn(
        runs=[_run_row("grok_run", "10.1002--jfa2.70171", 5, "forensic_review"),
              _run_row(corpus, "10.1002--jfa2.70171", 7, "forensic_review")],
        findings=[])
    got = D.fetch_paper_runs(paper, conn=conn)
    assert [r["matched_by"] for r in got["runs"]] == ["dir"]
    assert got["runs"][0]["corpus"] == corpus
    assert got["runs"][0]["doc"]["findings"] == []


def test_fetch_paper_runs_query_error_is_unavailable(tmp_path):
    paper = _meta_paper(tmp_path)

    class Boom:
        def cursor(self):
            raise RuntimeError("connection reset")

        def close(self):
            pass

    got = D.fetch_paper_runs(paper, conn=Boom())
    assert got["state"] == "unavailable"
    assert "connection reset" in got["detail"]
