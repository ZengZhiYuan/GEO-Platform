from pathlib import Path


VERSIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"
BASELINE_NAME = "20260615_0001-ai_monitoring_baseline.py"
COLLECTION_NAME = "20260615_0002-geo_monitoring_0002_collection.py"
ANALYSIS_NAME = "20260615_0003-geo_monitoring_0003_analysis_metrics.py"
SCHEDULE_REPORT_NAME = "20260615_0004-geo_monitoring_0004_schedule_report.py"
MONITOR_SETUP_NAME = "20260622_0005-geo_monitoring_0005_monitor_setup.py"
REPORT_PDF_NAME = "20260623_0006-geo_monitoring_0006_report_pdf_format.py"
AIDSO_COLLECTION_SOURCE_NAME = (
    "20260624_0007-geo_monitoring_0007_aidso_collection_source.py"
)
METRIC_SNAPSHOT_BRAND_NAME = (
    "20260625_0008-geo_monitoring_0008_metric_snapshot_brand.py"
)
PROJECT_MONITORING_PAUSED_NAME = (
    "20260626_0009-geo_monitoring_0009_project_monitoring_paused.py"
)
PROJECT_DRAFT_NAME = "20260626_0010-geo_monitoring_0010_project_draft.py"
EXPECTED_MIGRATIONS = [
    BASELINE_NAME,
    COLLECTION_NAME,
    ANALYSIS_NAME,
    SCHEDULE_REPORT_NAME,
    MONITOR_SETUP_NAME,
    REPORT_PDF_NAME,
    AIDSO_COLLECTION_SOURCE_NAME,
    METRIC_SNAPSHOT_BRAND_NAME,
    PROJECT_MONITORING_PAUSED_NAME,
    PROJECT_DRAFT_NAME,
]


def test_alembic_has_monitoring_migrations_in_order():
    versions = sorted(
        path.name
        for path in VERSIONS_DIR.glob("*.py")
        if path.name != "__init__.py"
    )

    assert versions == EXPECTED_MIGRATIONS


def test_baseline_contains_only_monitoring_business_tables():
    migration = (VERSIONS_DIR / BASELINE_NAME).read_text(encoding="utf-8")
    expected_tables = {
        "geo_monitor_project",
        "geo_brand",
        "geo_brand_alias",
        "geo_prompt_set",
        "geo_prompt",
        "geo_ai_platform",
        "geo_monitor_run",
        "geo_query_task",
    }
    forbidden_tables = {
        "keyword_library",
        "title_inspiration",
        "image_asset",
        "writing_rule",
        "writing_task",
        "article",
        "content_category",
    }

    for table in expected_tables:
        assert f'"{table}"' in migration
    for table in forbidden_tables:
        assert table not in migration
    for code in {"doubao", "qwen", "yuanbao", "deepseek", "kimi"}:
        assert f'"{code}"' in migration


def test_baseline_is_a_single_root_revision():
    migration = (VERSIONS_DIR / BASELINE_NAME).read_text(encoding="utf-8")

    assert 'revision = "geo_monitoring_0001"' in migration
    assert "down_revision = None" in migration


def test_project_draft_migration_creates_draft_table():
    migration = (VERSIONS_DIR / PROJECT_DRAFT_NAME).read_text(encoding="utf-8")

    assert 'revision = "geo_monitoring_0010"' in migration
    assert 'down_revision = "geo_monitoring_0009"' in migration
    assert '"geo_project_draft"' in migration
    assert '"draft_key"' in migration
    assert '"current_step"' in migration
    assert '"project_data"' in migration
    assert '"monitor_setup_data"' in migration
    assert '"ix_geo_project_draft_key_updated"' in migration
    assert '"ck_geo_project_draft_current_step"' in migration
    assert 'op.drop_table("geo_project_draft")' in migration
