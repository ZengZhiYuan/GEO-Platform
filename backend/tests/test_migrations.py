import os
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).parents[1]
VERSIONS_DIR = BACKEND_DIR / "alembic" / "versions"
_OFFLINE_DATABASE_URL = "postgresql+psycopg2://migration:test@localhost/migration_test"


def _run_alembic_sql(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args, "--sql"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "DATABASE_URL": _OFFLINE_DATABASE_URL,
            "APP_ENV": "test",
            "NACOS_ENABLED": "false",
        },
        check=True,
    )
    return result.stdout
COLLECTION_NAME = "20260615_0002-geo_monitoring_0002_collection.py"
ANALYSIS_NAME = "20260615_0003-geo_monitoring_0003_analysis_metrics.py"
SCHEDULE_REPORT_NAME = "20260615_0004-geo_monitoring_0004_schedule_report.py"


def _migration_text() -> str:
    return (VERSIONS_DIR / COLLECTION_NAME).read_text(encoding="utf-8")


def test_collection_revision_extends_monitoring_baseline():
    migration = _migration_text()

    assert 'revision = "geo_monitoring_0002"' in migration
    assert 'down_revision = "geo_monitoring_0001"' in migration


def test_collection_revision_adds_run_and_task_runtime_columns():
    migration = _migration_text()

    for column in {
        "triggered_by",
        "total_tasks",
        "succeeded_tasks",
        "failed_tasks",
        "cancelled_tasks",
        "completed_at",
        "error_summary",
        "attempt_count",
        "max_attempts",
        "queued_at",
        "completed_at",
        "last_error_code",
        "last_error_message",
        "provider_request_id",
    }:
        assert f'"{column}"' in migration


def test_collection_revision_creates_answer_tables():
    migration = _migration_text()

    for table in {
        "geo_answer",
        "geo_answer_citation",
        "geo_answer_brand_result",
    }:
        assert f'"{table}"' in migration

    for column in {
        "task_id",
        "platform_code",
        "prompt_id",
        "raw_text",
        "normalized_text",
        "model_name",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "latency_ms",
        "collected_at",
        "raw_response_json",
        "citation_no",
        "title",
        "url",
        "domain",
        "source_type",
        "quoted_text",
        "brand_id",
        "is_mentioned",
        "mention_count",
        "first_position",
        "sentiment",
        "context_json",
    }:
        assert f'"{column}"' in migration


def test_collection_revision_adds_required_indexes_and_uniques():
    migration = _migration_text()

    for name in {
        "ix_geo_monitor_run_status_completed",
        "ix_geo_query_task_status_queued",
        "ix_geo_answer_platform_collected",
        "ix_geo_answer_citation_domain",
        "ix_geo_answer_brand_result_brand_mentioned",
        "uq_geo_answer_task",
        "uq_geo_answer_citation_answer_no",
        "uq_geo_answer_brand_result_answer_brand",
    }:
        assert f'"{name}"' in migration


def test_collection_downgrade_drops_new_objects_in_reverse_order():
    migration = _migration_text()

    brand_drop = migration.index('op.drop_table("geo_answer_brand_result")')
    citation_drop = migration.index('op.drop_table("geo_answer_citation")')
    answer_drop = migration.index('op.drop_table("geo_answer")')
    run_drop = migration.index('op.drop_column("geo_monitor_run", "triggered_by")')

    assert brand_drop < citation_drop < answer_drop < run_drop
    for table in {
        "geo_answer_brand_result",
        "geo_answer_citation",
        "geo_answer",
    }:
        assert f'op.drop_table("{table}")' in migration


def _analysis_migration_text() -> str:
    return (VERSIONS_DIR / ANALYSIS_NAME).read_text(encoding="utf-8")


def test_analysis_revision_extends_collection_revision():
    migration = _analysis_migration_text()

    assert 'revision = "geo_monitoring_0003"' in migration
    assert 'down_revision = "geo_monitoring_0002"' in migration


def test_analysis_revision_creates_analysis_tables():
    migration = _analysis_migration_text()

    for table in {
        "geo_agent_execution",
        "geo_platform_analysis",
        "geo_metric_snapshot",
        "geo_prompt_competitiveness",
        "geo_source_stat",
    }:
        assert f'"{table}"' in migration

    for column in {
        "run_id",
        "platform_code",
        "agent_code",
        "schema_version",
        "input_snapshot",
        "output_json",
        "model_provider",
        "model_name",
        "prompt_version",
        "prompt_tokens",
        "completion_tokens",
        "error_message",
        "started_at",
        "finished_at",
        "valid_answer_count",
        "data_completeness_rate",
        "brand_mention_count",
        "brand_mention_rate",
        "brand_first_count",
        "brand_first_rate",
        "brand_first_among_mentions_rate",
        "top_competitors",
        "top_sources",
        "prompt_competitiveness_summary",
        "improvement_json",
        "summary_json",
        "project_id",
        "prompt_id",
        "metric_code",
        "numerator",
        "denominator",
        "metric_value",
        "metric_json",
        "snapshot_at",
        "prompt_set_version",
        "is_comparable",
        "completeness_rate",
        "target_mentioned",
        "target_rank",
        "target_first",
        "competitors_json",
        "position_label",
        "competitiveness_score",
        "evidence_json",
        "domain",
        "source_name",
        "source_type",
        "citation_count",
        "brand_related_count",
        "share_rate",
        "rank_no",
    }:
        assert f'"{column}"' in migration


def test_analysis_revision_uses_jsonb_and_cascade_foreign_keys():
    migration = _analysis_migration_text()

    assert "JSONB" in migration
    assert 'ondelete="CASCADE"' in migration
    assert 'ForeignKey("geo_monitor_project.id", ondelete="CASCADE")' in migration
    assert 'ForeignKey("geo_monitor_run.id", ondelete="CASCADE")' in migration


def test_analysis_revision_uses_null_safe_unique_indexes():
    migration = _analysis_migration_text()

    assert 'coalesce(platform_code, \'\')' in migration
    assert "coalesce(prompt_id, -1)" in migration
    for name in {
        "uq_geo_agent_execution_run_agent",
        "uq_geo_metric_snapshot_dimension",
        "uq_geo_source_stat_run_platform_domain",
    }:
        assert f'"{name}"' in migration
        assert f'unique=True' in migration


def test_analysis_revision_adds_required_indexes_and_uniques():
    migration = _analysis_migration_text()

    for name in {
        "uq_geo_platform_analysis",
        "uq_geo_prompt_competitiveness",
        "uq_geo_agent_execution_run_agent",
        "uq_geo_metric_snapshot_dimension",
        "uq_geo_source_stat_run_platform_domain",
        "ix_geo_agent_execution_run_platform_agent",
        "ix_geo_metric_snapshot_trend",
        "ix_geo_prompt_competitiveness_run_prompt",
        "ix_geo_source_stat_run_platform_rank",
        "ck_geo_agent_execution_status",
        "ck_geo_platform_analysis_status",
    }:
        assert f'"{name}"' in migration


def test_analysis_downgrade_drops_new_objects_in_reverse_order():
    migration = _analysis_migration_text()

    source_drop = migration.index('op.drop_table("geo_source_stat")')
    prompt_comp_drop = migration.index('op.drop_table("geo_prompt_competitiveness")')
    snapshot_drop = migration.index('op.drop_table("geo_metric_snapshot")')
    platform_drop = migration.index('op.drop_table("geo_platform_analysis")')
    agent_drop = migration.index('op.drop_table("geo_agent_execution")')

    assert (
        source_drop
        < prompt_comp_drop
        < snapshot_drop
        < platform_drop
        < agent_drop
    )
    for table in {
        "geo_source_stat",
        "geo_prompt_competitiveness",
        "geo_metric_snapshot",
        "geo_platform_analysis",
        "geo_agent_execution",
    }:
        assert f'op.drop_table("{table}")' in migration


def _schedule_report_migration_text() -> str:
    return (VERSIONS_DIR / SCHEDULE_REPORT_NAME).read_text(encoding="utf-8")


def test_schedule_report_revision_extends_analysis_revision():
    migration = _schedule_report_migration_text()

    assert 'revision = "geo_monitoring_0004"' in migration
    assert 'down_revision = "geo_monitoring_0003"' in migration


def test_schedule_report_revision_creates_schedule_and_report_tables():
    migration = _schedule_report_migration_text()

    for table in {"geo_monitor_schedule", "geo_report"}:
        assert f'"{table}"' in migration

    for column in {
        "project_id",
        "name",
        "cron_expr",
        "timezone",
        "enabled",
        "next_run_at",
        "last_run_at",
        "misfire_policy",
        "run_id",
        "status",
        "format",
        "file_name",
        "relative_storage_path",
        "file_size",
        "checksum",
        "error_message",
        "completed_at",
    }:
        assert f'"{column}"' in migration


def test_schedule_report_revision_uses_cascade_foreign_keys():
    migration = _schedule_report_migration_text()

    assert 'ForeignKey("geo_monitor_project.id", ondelete="CASCADE")' in migration
    assert 'ForeignKey("geo_monitor_run.id", ondelete="CASCADE")' in migration


def test_schedule_report_revision_adds_required_indexes_and_uniques():
    migration = _schedule_report_migration_text()

    for name in {
        "uq_geo_monitor_schedule_project_name",
        "uq_geo_report_relative_storage_path",
        "ix_geo_monitor_schedule_project_enabled",
        "ix_geo_report_project_run",
        "ck_geo_monitor_schedule_misfire_policy",
        "ck_geo_report_status",
        "ck_geo_report_format",
        "ck_geo_report_relative_storage_path",
    }:
        assert f'"{name}"' in migration


def test_schedule_report_revision_rejects_absolute_storage_paths():
    migration = _schedule_report_migration_text()

    assert "relative_storage_path NOT LIKE '/%'" in migration
    assert "relative_storage_path !~ '^[A-Za-z]:'" in migration


def test_schedule_report_downgrade_drops_new_objects_in_reverse_order():
    migration = _schedule_report_migration_text()

    report_drop = migration.index('op.drop_table("geo_report")')
    schedule_drop = migration.index('op.drop_table("geo_monitor_schedule")')

    assert report_drop < schedule_drop
    for table in {"geo_report", "geo_monitor_schedule"}:
        assert f'op.drop_table("{table}")' in migration


def test_schedule_report_upgrade_sql_creates_tables_from_analysis_revision():
    sql = _run_alembic_sql("upgrade", "geo_monitoring_0003:geo_monitoring_0004")

    assert "CREATE TABLE geo_monitor_schedule" in sql
    assert "CREATE TABLE geo_report" in sql
    assert "ck_geo_report_relative_storage_path" in sql
    assert "uq_geo_monitor_schedule_project_name" in sql
    assert "version_num='geo_monitoring_0004'" in sql


def test_schedule_report_downgrade_sql_reverts_to_analysis_revision():
    sql = _run_alembic_sql("downgrade", "geo_monitoring_0004:geo_monitoring_0003")

    assert "DROP TABLE geo_report" in sql
    assert "DROP TABLE geo_monitor_schedule" in sql
    assert "version_num='geo_monitoring_0003'" in sql
