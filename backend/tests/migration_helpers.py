"""PostgreSQL migration integration test helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

BACKEND_DIR = Path(__file__).resolve().parents[1]


def default_migration_test_database_url() -> str:
    explicit = os.environ.get("MIGRATION_TEST_DATABASE_URL", "").strip()
    if explicit:
        return explicit

    user = os.environ.get("POSTGRES_USER", "shipu_geo")
    password = os.environ.get("POSTGRES_PASSWORD", "shipu_geo_password")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("MIGRATION_TEST_POSTGRES_DB", "geo_migration_test")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def postgres_admin_url(database_url: str) -> str:
    url = make_url(database_url)
    database_name = url.database
    if not database_name:
        raise ValueError("migration test database URL must include a database name")
    return str(url.set(database="postgres"))


def postgres_server_reachable(admin_url: str) -> bool:
    try:
        engine = create_engine(admin_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except OperationalError:
        return False


def recreate_migration_test_database(database_url: str) -> None:
    url = make_url(database_url)
    database_name = url.database
    if not database_name:
        raise ValueError("migration test database URL must include a database name")

    engine = create_engine(
        str(url.set(database="postgres")),
        isolation_level="AUTOCOMMIT",
    )
    with engine.connect() as connection:
        connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = :database_name AND pid <> pg_backend_pid()"
            ),
            {"database_name": database_name},
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    engine.dispose()


def run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["APP_ENV"] = "test"
    env["NACOS_ENABLED"] = "false"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def current_revision(database_url: str) -> str:
    result = run_alembic(database_url, "current")
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)

    for line in reversed(result.stdout.splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("INFO"):
            continue
        return stripped.split()[0]
    raise RuntimeError(f"Could not parse alembic current output:\n{result.stdout}")


def table_exists(database_url: str, table_name: str) -> bool:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :table_name"
                ),
                {"table_name": table_name},
            ).scalar()
            return exists is not None
    finally:
        engine.dispose()
