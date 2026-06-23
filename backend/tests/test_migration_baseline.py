from pathlib import Path


VERSIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"
BASELINE_NAME = "20260615_0001-ai_monitoring_baseline.py"
COLLECTION_NAME = "20260615_0002-geo_monitoring_0002_collection.py"
ANALYSIS_NAME = "20260615_0003-geo_monitoring_0003_analysis_metrics.py"
SCHEDULE_REPORT_NAME = "20260615_0004-geo_monitoring_0004_schedule_report.py"
MONITOR_SETUP_NAME = "20260622_0005-geo_monitoring_0005_monitor_setup.py"
REPORT_PDF_NAME = "20260623_0006-geo_monitoring_0006_report_pdf_format.py"
EXPECTED_MIGRATIONS = [
    BASELINE_NAME,
    COLLECTION_NAME,
    ANALYSIS_NAME,
    SCHEDULE_REPORT_NAME,
    MONITOR_SETUP_NAME,
    REPORT_PDF_NAME,
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
