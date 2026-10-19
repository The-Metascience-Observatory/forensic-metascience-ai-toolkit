"""Is the local findings database set up, and if not, set it up.

The database is OPTIONAL. With no `METASCIENCE_DB_URL` every run is files
only (`forensic_review/`, `findings.v2.json`), and nothing is lost but
`db-push`, the review workbench and the auto-push at the end of each run.
What is not acceptable is a machine that never decided: a URL pointing at a
server that is down, a database with no schema, or a typo, all of which make
every finished run land in `db_push_pending.jsonl` without a word.

So there are two answers that end the question, and `status()` reports which
one this machine gave:

  - `ready`: a URL resolves, the server answers, and the schema is current.
  - `off`: `METASCIENCE_NO_DB_PUSH=1` in the environment or the repo `.env`
    (what `metascience db-setup --no-database` writes).

Everything else is a state with a named fix, and `metascience db-setup`
walks through it. `preflight` shows the row; it never blocks a run, because
a run without a database is still a correct run.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from . import db_push

#: The schema and its migrations, in the order they must be applied. Each
#: entry is (name, marker query that is true once it is applied, applier).
#: 006 redefines the trigger function 005 defines, so 005 must never be
#: applied after 006: application starts at the FIRST missing step and runs
#: forward, never back.
DB_DIR = Path(__file__).resolve().parents[2] / "db"

DEFAULT_DB_NAME = "metascience"

STATES = ("ready", "off", "not_configured", "remote_refused", "driver_missing",
          "server_unreachable", "auth_failed", "no_database", "schema_missing",
          "error")


def default_url() -> str:
    """A unix-socket URL on Linux/macOS (peer auth as the login user, no
    password to store); TCP as `postgres` on Windows, which has no socket."""
    if platform.system() == "Windows":
        return f"postgresql://postgres@localhost:5432/{DEFAULT_DB_NAME}"
    return f"postgresql:///{DEFAULT_DB_NAME}"


def _apply_file(conn, path: Path) -> None:
    with conn.transaction():
        conn.execute(path.read_text())


def _apply_history(conn) -> None:
    from .history_db import migrate
    migrate(conn)


def _apply_workbench(conn) -> None:
    from .workbench.remote import migration_sql
    with conn.transaction():
        conn.execute("set local lock_timeout='5s'")
        conn.execute(migration_sql())


def _has_table(name: str) -> str:
    return f"select to_regclass('{name}') is not null"


def _has_column(table: str, column: str) -> str:
    return ("select exists (select 1 from information_schema.columns where "
            f"table_schema = current_schema() and table_name = '{table}' "
            f"and column_name = '{column}')")


STEPS = (
    ("schema", _has_table("corpora"),
     lambda conn: _apply_file(conn, DB_DIR / "schema.sql")),
    ("003_analysis_history", _has_table("executions"), _apply_history),
    ("004_workbench", _has_table("workbench_changes"), _apply_workbench),
    ("005_image_retirement", _has_column("runs", "retired_at"),
     lambda conn: _apply_file(conn, DB_DIR / "migrations" / "005_image_retirement.sql")),
    ("006_image_reset", _has_column("runs", "retirement_reason"),
     lambda conn: _apply_file(conn, DB_DIR / "migrations" / "006_image_reset.sql")),
)


def missing_steps(conn) -> list[str]:
    """Names of the steps still to apply, from the first missing one onward."""
    for i, (_, marker, _) in enumerate(STEPS):
        if not conn.execute(marker).fetchone()[0]:
            return [name for name, _, _ in STEPS[i:]]
    return []


def apply_steps(conn, names: list[str]) -> list[str]:
    applied = []
    for name, _, apply in STEPS:
        if name in names:
            apply(conn)
            applied.append(name)
    return applied


def classify_error(exc: Exception) -> str:
    """Which fix a connection error needs. psycopg puts the server's message
    in str(exc); these are the four that need different instructions."""
    text = str(exc).lower()
    if "does not exist" in text and "database" in text:
        return "no_database"
    if ("password authentication failed" in text or "peer authentication" in text
            or ("role" in text and "does not exist" in text)
            or "no password supplied" in text):
        return "auth_failed"
    if ("connection refused" in text or "could not connect" in text
            or "timeout" in text or "no such file or directory" in text
            or "is the server running" in text):
        return "server_unreachable"
    return "error"


def _redact(url: str) -> str:
    """The URL without its password, for printing."""
    try:
        from psycopg.conninfo import conninfo_to_dict
        parts = conninfo_to_dict(url)
    except Exception:  # noqa: BLE001
        return "<unparseable URL>"
    parts.pop("password", None)
    host = parts.get("host") or "local socket"
    user = parts.get("user") or "login user"
    return f"{parts.get('dbname', '?')} on {host} as {user}"


def status(connect_timeout: int = 3) -> dict:
    """{"state": one of STATES, "detail": str, "url": redacted or None,
    "missing": [step names]}. Connects only when a URL is configured."""
    if db_push.database_disabled():
        return {"state": "off", "url": None, "missing": [],
                "detail": f"turned off ({db_push.NO_DB_ENV}); runs are saved as "
                          "files only"}
    try:
        url = db_push.resolve_db_url()
    except db_push.DbUnavailable as exc:
        return {"state": "remote_refused", "url": None, "missing": [],
                "detail": str(exc)}
    if not url:
        return {"state": "not_configured", "url": None, "missing": [],
                "detail": "no database configured; runs are saved as files only. "
                          "`metascience db-setup` sets one up, or turns this "
                          "notice off"}
    shown = _redact(url)
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return {"state": "driver_missing", "url": shown, "missing": [],
                "detail": "psycopg is not installed (a base dependency): "
                          "reinstall with `pip install -e .`"}
    try:
        with db_push._connect(url, connect_timeout=connect_timeout) as conn:
            missing = missing_steps(conn)
    except Exception as exc:  # noqa: BLE001
        state = classify_error(exc)
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return {"state": state, "url": shown, "missing": [],
                "detail": f"{shown}: {first}. Run `metascience db-setup`"}
    if missing:
        return {"state": "schema_missing", "url": shown, "missing": missing,
                "detail": f"{shown}: schema not applied ({', '.join(missing)}). "
                          "Run `metascience db-setup`"}
    return {"state": "ready", "url": shown, "missing": [],
            "detail": f"{shown}: ready; each finished run is pushed here"}


# ---------------------------------------------------------------- the .env

def write_env(updates: dict[str, str | None], env_file: Path) -> None:
    """Set (or, with None, remove) keys in the `.env`, keeping every other
    line and comment as it was."""
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    out, seen = [], set()
    for line in lines:
        is_setting = "=" in line and not line.lstrip().startswith("#")
        key = line.split("=", 1)[0].strip() if is_setting else None
        if key in updates:
            seen.add(key)
            if updates[key] is not None:
                out.append(f"{key}={updates[key]}")
            continue
        out.append(line)
    for key, value in updates.items():
        if key not in seen and value is not None:
            out.append(f"{key}={value}")
    env_file.write_text("\n".join(out) + "\n")
    try:
        env_file.chmod(0o600)
    except OSError:
        pass


# --------------------------------------------------------- install advice

def install_instructions() -> list[str]:
    system = platform.system()
    if system == "Darwin":
        return ["brew install postgresql@16",
                "brew services start postgresql@16"]
    if system == "Windows":
        return ["winget install PostgreSQL.PostgreSQL.16",
                "(the installer asks for a password for the `postgres` user; put it "
                "in the URL: postgresql://postgres:<password>@localhost:5432/metascience)"]
    if shutil.which("apt-get"):
        return ["sudo apt-get install postgresql",
                "sudo systemctl enable --now postgresql"]
    if shutil.which("dnf"):
        return ["sudo dnf install postgresql-server",
                "sudo postgresql-setup --initdb",
                "sudo systemctl enable --now postgresql"]
    return ["install PostgreSQL 14 or newer from https://www.postgresql.org/download/",
            "and start its server"]


def start_instructions() -> list[str]:
    system = platform.system()
    if system == "Darwin":
        return ["brew services start postgresql@16"]
    if system == "Windows":
        return ["start the postgresql service from Services, or: "
                "net start postgresql-x64-16"]
    return ["sudo systemctl start postgresql"]


def role_instructions() -> list[str]:
    """The login was refused: usually no role for this user yet."""
    if platform.system() in ("Darwin", "Windows"):
        return ["check the user and password in the URL"]
    user = os.environ.get("USER") or "$USER"
    return [f"sudo -u postgres createuser --createdb {user}"]


def create_instructions(url: str) -> list[str]:
    """The role exists but may not create databases: have the server's
    superuser create this one, owned by the user."""
    from psycopg.conninfo import conninfo_to_dict
    parts = conninfo_to_dict(url)
    name = parts.get("dbname") or DEFAULT_DB_NAME
    user = parts.get("user") or os.environ.get("USER") or "$USER"
    if platform.system() == "Windows":
        return [f'psql -U postgres -c "create database {name} owner {user}"']
    return [f"sudo -u postgres createdb -O {user} {name}"]


def server_installed() -> bool:
    return any(shutil.which(cmd) for cmd in ("psql", "pg_isready", "postgres", "pg_ctl"))


def server_accepting(url: str) -> bool | None:
    """True/False from `pg_isready` against the URL's host, None when
    pg_isready is not on PATH (the connection attempt decides then)."""
    exe = shutil.which("pg_isready")
    if not exe:
        return None
    from psycopg.conninfo import conninfo_to_dict
    parts = conninfo_to_dict(url)
    cmd = [exe, "-q"]
    if parts.get("host"):
        cmd += ["-h", parts["host"]]
    if parts.get("port"):
        cmd += ["-p", str(parts["port"])]
    try:
        return subprocess.run(cmd, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return None


def create_database(url: str) -> None:
    """CREATE DATABASE for the URL's dbname, connected to the server's
    `postgres` maintenance database as the same user."""
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    name = conninfo_to_dict(url).get("dbname") or DEFAULT_DB_NAME
    with psycopg.connect(make_conninfo(url, dbname="postgres"),
                         autocommit=True, connect_timeout=10) as conn:
        conn.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
