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


MOLIZHISHU_SEED_PLATFORM_CODES = (
    "molizhishu_deepseek_web",
    "molizhishu_deepseek_mobile",
    "molizhishu_doubao_web",
    "molizhishu_doubao_mobile",
    "molizhishu_yuanbao_web",
    "molizhishu_kimi_web",
    "molizhishu_qianwen_web",
    "molizhishu_quark_web",
    "molizhishu_baiduai_web",
    "molizhishu_weibo_zhisou_web",
    "molizhishu_wenxinyiyan_web",
)

RUN_PROVIDER_COLUMNS = (
    "provider_mode_by_platform",
    "provider_screenshot",
    "provider_callback_url",
    "region_code",
)

QUERY_TASK_PROVIDER_COLUMNS = (
    "provider_name",
    "provider_task_id",
    "provider_subtask_id",
    "provider_platform_code",
    "provider_mode",
    "provider_status",
    "provider_result_json",
    "provider_error_message",
)


def _insert_run(connection, *, collection_source: str) -> None:
    project_id = connection.execute(
        text(
            """
            INSERT INTO geo_monitor_project (
                project_name, industry, timezone, status, is_deleted
            )
            VALUES (:name, '文旅', 'Asia/Shanghai', 'active', false)
            RETURNING id
            """
        ),
        {"name": f"collection-source-{collection_source}"},
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
    connection.execute(
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
                collection_source,
                platform_codes,
                is_deleted
            )
            VALUES (
                :run_no,
                :project_id,
                :prompt_set_id,
                'v1',
                'manual',
                'pending',
                'pending',
                'skipped',
                'skipped',
                :collection_source,
                '[]'::jsonb,
                false
            )
            """
        ),
        {
            "run_no": f"run-{collection_source}",
            "project_id": project_id,
            "prompt_set_id": prompt_set_id,
            "collection_source": collection_source,
        },
    )


def _column_names(database_url: str, table_name: str) -> set[str]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :table_name
                    """
                ),
                {"table_name": table_name},
            ).scalars()
            return set(rows)
    finally:
        engine.dispose()


def test_molizhishu_migration_on_postgresql(migrated_head_database):
    database_url = migrated_head_database
    assert current_revision(database_url) == "geo_monitoring_0011"

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            seeded_codes = connection.execute(
                text(
                    """
                    SELECT platform_code
                    FROM geo_ai_platform
                    WHERE platform_code = ANY(:codes)
                    ORDER BY platform_code
                    """
                ),
                {"codes": list(MOLIZHISHU_SEED_PLATFORM_CODES)},
            ).scalars()
            assert list(seeded_codes) == sorted(MOLIZHISHU_SEED_PLATFORM_CODES)
    finally:
        engine.dispose()

    run_columns = _column_names(database_url, "geo_monitor_run")
    task_columns = _column_names(database_url, "geo_query_task")
    assert RUN_PROVIDER_COLUMNS <= run_columns
    assert QUERY_TASK_PROVIDER_COLUMNS <= task_columns

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            _insert_run(connection, collection_source="molizhishu")
            _insert_run(connection, collection_source="aidso")
            with pytest.raises(IntegrityError):
                _insert_run(connection, collection_source="unknown")
    finally:
        engine.dispose()


def test_molizhishu_downgrade_preserves_extra_platform_on_postgresql(
    migration_test_database_url,
):
    database_url = migration_test_database_url
    recreate_migration_test_database(database_url)
    try:
        upgrade_result = run_alembic(database_url, "upgrade", "head")
        assert upgrade_result.returncode == 0, upgrade_result.stderr or upgrade_result.stdout

        engine = create_engine(database_url, pool_pre_ping=True)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO geo_ai_platform (
                            platform_code,
                            platform_name,
                            adapter_type,
                            search_enabled,
                            citation_supported,
                            max_concurrency,
                            timeout_seconds,
                            enabled,
                            extra_config
                        )
                        VALUES (
                            'molizhishu_custom_manual',
                            '手工配置平台',
                            'molizhishu',
                            true,
                            true,
                            2,
                            120,
                            true,
                            '{}'::jsonb
                        )
                        """
                    )
                )
        finally:
            engine.dispose()

        downgrade_result = run_alembic(database_url, "downgrade", "geo_monitoring_0010")
        assert downgrade_result.returncode == 0, (
            downgrade_result.stderr or downgrade_result.stdout
        )

        engine = create_engine(database_url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                remaining_codes = set(
                    connection.execute(
                        text(
                            """
                            SELECT platform_code
                            FROM geo_ai_platform
                            WHERE platform_code LIKE 'molizhishu_%'
                            ORDER BY platform_code
                            """
                        )
                    ).scalars()
                )
                assert remaining_codes == {"molizhishu_custom_manual"}
                for code in MOLIZHISHU_SEED_PLATFORM_CODES:
                    assert code not in remaining_codes
        finally:
            engine.dispose()
    finally:
        recreate_migration_test_database(database_url)
        restore_result = run_alembic(database_url, "upgrade", "head")
        assert restore_result.returncode == 0, restore_result.stderr or restore_result.stdout
