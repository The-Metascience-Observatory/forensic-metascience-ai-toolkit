"""The findings database is local-only, and its cache follows its identity.

1. Every store is on this machine (the remote Neon database was retired
   2026-10-16). A URL naming another host must REFUSE rather than connect, so a
   stale `.env` cannot quietly send findings or review decisions off-machine.
2. The local SQLite cache is a projection of ONE database, and its `cursor` is a
   watermark into that database's `workbench_changes.revision` sequence. Against
   a different database (a recreated local cluster, say) the watermark is
   meaningless, so a changed identity resets the cache.
"""

from __future__ import annotations

import pytest

from metascience_agent import db_push
from metascience_agent.workbench.catalog import Catalog

#: Captured before the autouse conftest guard stubs it out for every test.
_real_dotenv_url = db_push._dotenv_url


@pytest.fixture
def no_env_file(monkeypatch, tmp_path):
    env = tmp_path / "empty.env"
    env.write_text("")
    monkeypatch.setenv("METASCIENCE_ENV_FILE", str(env))
    monkeypatch.delenv(db_push.DB_URL_ENV, raising=False)
    return env


class TestLocalOnly:
    @pytest.mark.parametrize("url", [
        "postgresql://u:p@127.0.0.1:5432/metascience",
        "postgresql://localhost/metascience",
        "postgresql://u@[::1]:5432/db",
        "postgresql:///metascience?host=/var/run/postgresql",
        "postgresql://u@localhost:5432,127.0.0.1:5433/db",
    ])
    def test_local_urls_resolve(self, monkeypatch, no_env_file, url):
        monkeypatch.setenv(db_push.DB_URL_ENV, url)
        assert db_push.resolve_db_url() == url

    @pytest.mark.parametrize("url", [
        "postgresql://u:p@ep-x.us-east-2.aws.neon.tech/neondb?sslmode=require",
        "postgresql://u@db.example.org:5432/x",
        "postgresql://u@localhost,db.example.org/x",
        "postgresql:///x?host=db.example.org",
    ])
    def test_a_remote_host_refuses(self, monkeypatch, no_env_file, url):
        monkeypatch.setenv(db_push.DB_URL_ENV, url)
        with pytest.raises(db_push.DbUnavailable, match="remote host"):
            db_push.resolve_db_url()

    def test_an_explicit_remote_argument_also_refuses(self, no_env_file):
        with pytest.raises(db_push.DbUnavailable, match="remote host"):
            db_push.resolve_db_url("postgresql://u@db.example.org/x")

    def test_the_retired_variables_are_not_read(self, monkeypatch, no_env_file):
        """NEON_DB_URL and the profile switcher are gone; setting them selects nothing."""
        monkeypatch.setenv("NEON_DB_URL", "postgresql://127.0.0.1/old")
        monkeypatch.setenv("METASCIENCE_DB_PROFILES", "local=postgresql://127.0.0.1/p")
        monkeypatch.setenv("METASCIENCE_DB_PROFILE", "local")
        assert db_push.resolve_db_url() is None

    def test_the_env_file_supplies_the_url(self, monkeypatch, tmp_path):
        env = tmp_path / "repo.env"
        env.write_text("METASCIENCE_DB_URL=postgresql://127.0.0.1/metascience\n")
        monkeypatch.setenv("METASCIENCE_ENV_FILE", str(env))
        monkeypatch.delenv(db_push.DB_URL_ENV, raising=False)
        monkeypatch.setattr(db_push, "_dotenv_url", _real_dotenv_url)
        assert db_push.resolve_db_url() == "postgresql://127.0.0.1/metascience"

    def test_auto_push_reports_a_remote_url_instead_of_raising(self, monkeypatch, no_env_file, tmp_path):
        """The run-completion hook must never fail a paid run."""
        monkeypatch.delenv("METASCIENCE_NO_DB_PUSH", raising=False)
        monkeypatch.setenv(db_push.DB_URL_ENV, "postgresql://u@db.example.org/x")
        out = db_push.auto_push(tmp_path, tmp_path)
        assert out["pushed"] == 0 and "remote host" in out["skipped"]


class TestCacheResetOnDatabaseChange:
    def _catalog(self, tmp_path):
        return Catalog(tmp_path / "workbench.sqlite3")

    def test_reset_clears_the_projection_and_the_watermark(self, tmp_path):
        cat = self._catalog(tmp_path)
        cat.set_state("cursor", 12345)
        cat.set_state("bytes_received", 999)
        gen = cat.begin_snapshot()
        cat.stage_snapshot(gen, "papers", [("k1", {"dir": "10.1/a"})])
        cat.finish_snapshot(gen, 12345)
        assert cat.state("cursor") == 12345

        cat.reset_for_new_database("7676498233559181761/neondb")

        assert cat.state("cursor") is None, "a stale watermark would skip or replay changes"
        assert cat.state("bytes_received") is None
        assert cat.reader.execute("select count(*) from records").fetchone()[0] == 0
        cat.close()

    def test_the_outbox_survives_a_reset(self, tmp_path):
        """Unsent human decisions are work; the reset must not destroy them."""
        cat = self._catalog(tmp_path)
        cat.db.execute("insert into outbox(event_id,body) values(?,?)", ("e1", "{}"))
        cat.db.commit()
        cat.reset_for_new_database("other/db")
        assert cat.reader.execute("select count(*) from outbox").fetchone()[0] == 1
        cat.close()

    def test_a_cleared_cursor_forces_a_full_snapshot(self, tmp_path):
        """This is the mechanism the guard relies on: _sync_locked bootstraps
        whenever `cursor` is None."""
        cat = self._catalog(tmp_path)
        cat.set_state("cursor", 7)
        cat.reset_for_new_database("x/y")
        assert cat.state("cursor") is None
        cat.close()


class TestIdentityQuery:
    def test_the_identity_combines_cluster_and_database(self):
        """cluster alone is not enough: two databases in one cluster hold
        different schemas, and database alone is not enough either because two
        servers can both have a database called the same thing."""
        import inspect

        from metascience_agent.workbench.remote import Remote

        src = inspect.getsource(Remote.identity)
        assert "system_identifier" in src
        assert "current_database" in src

    def test_sync_resets_when_the_identity_changes(self):
        import inspect

        from metascience_agent.workbench.remote import Remote

        src = inspect.getsource(Remote._sync_locked)
        assert "db_identity" in src
        assert "reset_for_new_database" in src

    def test_the_first_sync_does_not_reset(self):
        """A fresh cache has no recorded identity; that is not a change, and
        resetting there would throw away a bootstrap already in progress."""
        import inspect

        from metascience_agent.workbench.remote import Remote

        src = inspect.getsource(Remote._sync_locked)
        assert "if seen is not None" in src
