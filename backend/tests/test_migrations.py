from pathlib import Path


VERSIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"
COLLECTION_NAME = "20260615_0002-geo_monitoring_0002_collection.py"


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
