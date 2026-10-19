"""`metascience db-setup` and the preflight row: a machine either has a
working findings database or has said it does without one.

Offline: every connection here is a fake. The schema steps themselves were
checked against a real server in a throwaway schema (see CHANGELOG 1.94.0);
`tests/test_workbench_remote.py` is the opt-in live test of the migrations.
"""

import pytest
from typer.testing import CliRunner

from forensic_metascience_ai_toolkit import db_push, db_setup as S
from forensic_metascience_ai_toolkit.cli import app


#: Captured at import, before conftest's autouse fixture blinds it: these
#: tests own their .env (test_db_push.py does the same).
_real_dotenv_url = db_push._dotenv_url


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.setenv("METASCIENCE_ENV_FILE", str(path))
    monkeypatch.delenv(db_push.NO_DB_ENV, raising=False)
    monkeypatch.setattr(db_push, "_dotenv_url", _real_dotenv_url)
    return path


class FakeConn:
    def __init__(self, present):
        self.present = set(present)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, query, *a):
        self.executed.append(query)
        name = next((n for n, marker, _ in S.STEPS if marker == query), None)
        value = name in self.present

        class R:
            def fetchone(self_inner):
                return (value,)
        return R()


class TestStatus:
    def test_no_url_is_not_configured_and_never_connects(self, env_file, monkeypatch):
        monkeypatch.setattr(db_push, "_connect", lambda *a, **k: pytest.fail("connected"))
        st = S.status()
        assert st["state"] == "not_configured"
        assert "db-setup" in st["detail"]

    def test_the_off_switch_in_the_env_file_counts(self, env_file):
        env_file.write_text(f"{db_push.NO_DB_ENV}=1\n")
        assert db_push.database_disabled()
        assert S.status()["state"] == "off"

    def test_off_also_stops_the_auto_push(self, env_file, tmp_path):
        env_file.write_text(f"{db_push.NO_DB_ENV}=1\n"
                            f"{db_push.DB_URL_ENV}=postgresql:///x\n")
        out = db_push.auto_push(tmp_path, tmp_path)
        assert out["skipped"].startswith(db_push.NO_DB_ENV)

    def test_remote_url_is_refused(self, env_file):
        env_file.write_text(f"{db_push.DB_URL_ENV}=postgresql://db.example.com/x\n")
        assert S.status()["state"] == "remote_refused"

    @pytest.mark.parametrize("message, state", [
        ('connection failed: FATAL:  database "metascience" does not exist', "no_database"),
        ('FATAL:  role "dan" does not exist', "auth_failed"),
        ("FATAL:  password authentication failed for user \"x\"", "auth_failed"),
        ("connection to server at \"127.0.0.1\", port 5432 failed: Connection refused",
         "server_unreachable"),
        ('connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: '
         "No such file or directory", "server_unreachable"),
    ])
    def test_connection_errors_are_classified(self, env_file, monkeypatch, message, state):
        env_file.write_text(f"{db_push.DB_URL_ENV}=postgresql:///metascience\n")

        def boom(*a, **k):
            raise RuntimeError(message)
        monkeypatch.setattr(db_push, "_connect", boom)
        st = S.status()
        assert st["state"] == state
        assert "db-setup" in st["detail"]

    def test_missing_schema_names_the_steps(self, env_file, monkeypatch):
        env_file.write_text(f"{db_push.DB_URL_ENV}=postgresql:///metascience\n")
        monkeypatch.setattr(db_push, "_connect",
                            lambda *a, **k: FakeConn({"schema", "003_analysis_history"}))
        st = S.status()
        assert st["state"] == "schema_missing"
        assert st["missing"] == ["004_workbench", "005_image_retirement", "006_image_reset"]

    def test_ready(self, env_file, monkeypatch):
        env_file.write_text(f"{db_push.DB_URL_ENV}=postgresql:///metascience\n")
        monkeypatch.setattr(db_push, "_connect",
                            lambda *a, **k: FakeConn({n for n, _, _ in S.STEPS}))
        assert S.status()["state"] == "ready"


class TestMigrationOrder:
    def test_never_goes_back_past_a_later_step(self):
        """006 redefines 005's trigger function; with 006 present and an
        earlier marker missing, the earlier step must still run BEFORE 006,
        never after it."""
        conn = FakeConn({"schema", "003_analysis_history", "004_workbench",
                         "006_image_reset"})
        assert S.missing_steps(conn) == ["005_image_retirement", "006_image_reset"]

    def test_the_sql_files_exist(self):
        assert (S.DB_DIR / "schema.sql").exists()
        for name in ("005_image_retirement.sql", "006_image_reset.sql"):
            assert (S.DB_DIR / "migrations" / name).exists()


class TestEnvFile:
    def test_write_keeps_other_lines_and_replaces_keys(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("# comment\nOTHER=1\nMETASCIENCE_DB_URL=old\nMETASCIENCE_NO_DB_PUSH=1\n")
        S.write_env({"METASCIENCE_DB_URL": "new", "METASCIENCE_NO_DB_PUSH": None}, env)
        assert env.read_text() == "# comment\nOTHER=1\nMETASCIENCE_DB_URL=new\n"


class TestCommand:
    def test_no_database_records_the_choice(self, env_file):
        result = CliRunner().invoke(app, ["db-setup", "--no-database"])
        assert result.exit_code == 0, result.output
        assert f"{db_push.NO_DB_ENV}=1" in env_file.read_text()
        assert S.status()["state"] == "off"

    def test_check_exits_nonzero_when_unsettled(self, env_file):
        result = CliRunner().invoke(app, ["db-setup", "--check"])
        assert result.exit_code == 1
        assert "not_configured" in result.output

    def test_declining_setup_turns_the_notice_off(self, env_file):
        result = CliRunner().invoke(app, ["db-setup"], input="n\n")
        assert result.exit_code == 0, result.output
        assert S.status()["state"] == "off"

    def test_no_postgres_prints_install_steps(self, env_file, monkeypatch):
        monkeypatch.setattr(S, "server_installed", lambda: False)
        result = CliRunner().invoke(app, ["db-setup", "--yes"])
        assert result.exit_code == 1
        assert S.install_instructions()[0] in result.output
        assert db_push.DB_URL_ENV not in (env_file.read_text() if env_file.exists() else "")

    def test_server_down_prints_start_steps(self, env_file, monkeypatch):
        monkeypatch.setattr(S, "server_installed", lambda: True)
        monkeypatch.setattr(S, "server_accepting", lambda url: False)
        result = CliRunner().invoke(app, ["db-setup", "--yes"])
        assert result.exit_code == 1
        assert S.start_instructions()[0] in result.output

    def test_creates_migrates_and_saves_the_url(self, env_file, monkeypatch):
        monkeypatch.setattr(S, "server_installed", lambda: True)
        monkeypatch.setattr(S, "server_accepting", lambda url: True)
        state = {"created": False, "present": set()}

        def connect(url, **k):
            if not state["created"]:
                raise RuntimeError('FATAL:  database "metascience" does not exist')
            return FakeConn(state["present"])
        monkeypatch.setattr(db_push, "_connect", connect)
        monkeypatch.setattr(S, "create_database",
                            lambda url: state.__setitem__("created", True))
        monkeypatch.setattr(S, "apply_steps", lambda conn, names: (
            state["present"].update(names), names)[1])
        result = CliRunner().invoke(app, ["db-setup", "--yes"])
        assert result.exit_code == 0, result.output
        assert f"{db_push.DB_URL_ENV}={S.default_url()}" in env_file.read_text()
        assert S.status()["state"] == "ready"


class TestPreflightRow:
    def test_row_is_present_and_off_passes(self, env_file):
        from forensic_metascience_ai_toolkit.preflight import optional_checks
        env_file.write_text(f"{db_push.NO_DB_ENV}=1\n")
        row = next(r for r in optional_checks() if r[0] == "Findings database")
        assert row[1] is True

    def test_not_configured_does_not_pass(self, env_file):
        from forensic_metascience_ai_toolkit.preflight import database_row
        name, ok, detail = database_row()
        assert not ok and "db-setup" in detail
