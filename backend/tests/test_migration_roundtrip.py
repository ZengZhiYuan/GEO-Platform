"""PostgreSQL migration roundtrip and constraint integration tests."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import (
    current_revision,
    default_migration_test_database_url,
    postgres_admin_url,
    postgres_server_reachable,
    recreate_migration_test_database,
    run_alembic,
    table_exists,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def migration_test_database_url():
    database_url = default_migration_test_database_url()
    admin_url = postgres_admin_url(database_url)
    if not postgres_server_reachable(admin_url):
        pytest.skip(
            "PostgreSQL unavailable. Start `docker compose up -d postgres` or set "
            "MIGRATION_TEST_DATABASE_URL to a reachable database."
        )
    recreate_migration_test_database(database_url)
    return database_url


@pytest.fixture(scope="module")
def migrated_head_database(migration_test_database_url):
    upgrade_result = run_alembic(migration_test_database_url, "upgrade", "head")
    assert upgrade_result.returncode == 0, upgrade_result.stderr or upgrade_result.stdout
    return migration_test_database_url


def _seed_project_and_run(connection) -> tuple[int, int]:
    project_id = connection.execute(
        text(
            """
            INSERT INTO geo_monitor_project (
                project_name, industry, timezone, status, is_deleted
            )
            VALUES ('migration-test', '文旅', 'Asia/Shanghai', 'active', false)
            RETURNING id
            """
        )
    ).scalar_one()

    prompt_set_id = connection.execute(
        text(
            """
            INSERT INTO geo_prompt_set (
                project_id, set_name, version_no, status, is_deleted
            )
            VALUES (:project_id, 'default', 'v1', 'active', false)
            RETURNING id
            """
        ),
        {"project_id": project_id},
    ).scalar_one()

    run_id = connection.execute(
        text(
            """
            INSERT INTO geo_monitor_run (
                run_no,
                project_id,
                prompt_set_id,
                prompt_set_version,
                trigger_type,
                status,
                collection_status,
                analysis_status,
                report_status,
                platform_codes,
                is_deleted
            )
            VALUES (
                'migration-test-run',
                :project_id,
                :prompt_set_id,
                'v1',
                'manual',
                'pending',
                'pending',
                'skipped',
                'skipped',
                '[]'::jsonb,
                false
            )
            RETURNING id
            """
        ),
        {"project_id": project_id, "prompt_set_id": prompt_set_id},
    ).scalar_one()
    return project_id, run_id


def test_schedule_report_migration_roundtrip_on_postgresql(
    migration_test_database_url,
):
    database_url = migration_test_database_url

    upgrade_result = run_alembic(database_url, "upgrade", "head")
    assert upgrade_result.returncode == 0, upgrade_result.stderr or upgrade_result.stdout
    assert current_revision(database_url) == "geo_monitoring_0004"
    assert table_exists(database_url, "geo_monitor_schedule")
    assert table_exists(database_url, "geo_report")

    downgrade_result = run_alembic(database_url, "downgrade", "geo_monitoring_0003")
    assert downgrade_result.returncode == 0, (
        downgrade_result.stderr or downgrade_result.stdout
    )
    assert current_revision(database_url) == "geo_monitoring_0003"
    assert not table_exists(database_url, "geo_report")
    assert not table_exists(database_url, "geo_monitor_schedule")

    reupgrade_result = run_alembic(database_url, "upgrade", "head")
    assert reupgrade_result.returncode == 0, (
        reupgrade_result.stderr or reupgrade_result.stdout
    )
    assert current_revision(database_url) == "geo_monitoring_0004"
    assert table_exists(database_url, "geo_report")
    assert table_exists(database_url, "geo_monitor_schedule")


def test_geo_report_rejects_absolute_storage_path_on_postgresql(
    migrated_head_database,
):
    database_url = migrated_head_database
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            project_id, run_id = _seed_project_and_run(connection)
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        """
                        INSERT INTO geo_report (
                            project_id,
                            run_id,
                            status,
                            format,
                            file_name,
                            relative_storage_path,
                            is_deleted
                        )
                        VALUES (
                            :project_id,
                            :run_id,
                            'pending',
                            'md',
                            'report.md',
                            '/tmp/report.md',
                            false
                        )
                        """
                    ),
                    {"project_id": project_id, "run_id": run_id},
                )
    finally:
        engine.dispose()


def test_geo_monitor_schedule_name_unique_per_project_on_postgresql(
    migrated_head_database,
):
    database_url = migrated_head_database
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            project_id = connection.execute(
                text(
                    """
                    INSERT INTO geo_monitor_project (
                        project_name, industry, timezone, status, is_deleted
                    )
                    VALUES ('schedule-unique-test', '文旅', 'Asia/Shanghai', 'active', false)
                    RETURNING id
                    """
                )
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO geo_monitor_schedule (
                        project_id, name, cron_expr, timezone, enabled, is_deleted
                    )
                    VALUES (:project_id, 'daily', '0 9 * * *', 'Asia/Shanghai', true, false)
                    """
                ),
                {"project_id": project_id},
            )
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        """
                        INSERT INTO geo_monitor_schedule (
                            project_id, name, cron_expr, timezone, enabled, is_deleted
                        )
                        VALUES (:project_id, 'daily', '0 10 * * *', 'Asia/Shanghai', true, false)
                        """
                    ),
                    {"project_id": project_id},
                )
    finally:
        engine.dispose()
