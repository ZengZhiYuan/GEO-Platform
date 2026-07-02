from app.core.timestamp_migration import (
    DEFAULT_STORE_TIMEZONE,
    alter_timestamptz_to_timestamp_sql,
    alter_timestamp_to_timestamptz_sql,
)

from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "migrate_timestamptz_to_timestamp.sql"
MIGRATION_PATH = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "20260701_0015-geo_monitoring_0015_timestamp_without_tz.py"
)


def test_default_store_timezone_matches_business_timezone_policy():
    assert DEFAULT_STORE_TIMEZONE == "Asia/Shanghai"


def test_alter_timestamptz_to_timestamp_sql_uses_store_timezone():
    sql = alter_timestamptz_to_timestamp_sql(
        "geo_monitor_project",
        "created_at",
        store_timezone="Asia/Shanghai",
    )
    assert "ALTER TABLE" in sql
    assert '"geo_monitor_project"' in sql
    assert '"created_at"' in sql
    assert "TIMESTAMP WITHOUT TIME ZONE" in sql
    assert "AT TIME ZONE 'Asia/Shanghai'" in sql


def test_alter_timestamp_to_timestamptz_sql_for_downgrade():
    sql = alter_timestamp_to_timestamptz_sql(
        "geo_monitor_project",
        "created_at",
        store_timezone=DEFAULT_STORE_TIMEZONE,
    )
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "AT TIME ZONE 'Asia/Shanghai'" in sql


def test_sql_script_executes_each_alter_independently_with_timeouts():
    sql = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "DO $$" not in sql
    assert "\\gexec" in sql
    assert "lock_timeout" in sql
    assert "statement_timeout" in sql
    assert "udt_name = 'timestamptz'" in sql


def test_sql_script_allows_psql_variable_overrides():
    sql = SCRIPT_PATH.read_text(encoding="utf-8")

    assert ":{?app_timezone}" in sql
    assert ":{?table_prefix}" in sql
    assert ":{?lock_timeout}" in sql


def test_sql_script_defaults_to_business_timezone():
    sql = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "\\set app_timezone Asia/Shanghai" in sql


def test_alembic_timestamp_migration_uses_autocommit_and_lock_timeout():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "autocommit_block" in migration
    assert "lock_timeout" in migration


def test_alembic_timestamp_migration_handles_offline_sql_mode():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "as_sql" in migration
    assert "offline SQL mode" in migration
