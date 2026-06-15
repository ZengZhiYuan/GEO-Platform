from importlib.util import find_spec


def test_monitoring_metadata_contains_only_expected_business_tables():
    assert find_spec("app.geo_monitoring.models") is not None

    from app.core.database import Base
    from app.geo_monitoring import models  # noqa: F401

    expected = {
        "geo_monitor_project",
        "geo_brand",
        "geo_brand_alias",
        "geo_prompt_set",
        "geo_prompt",
        "geo_ai_platform",
        "geo_monitor_run",
        "geo_query_task",
    }
    assert expected.issubset(Base.metadata.tables)
    assert "keyword_library" not in Base.metadata.tables
    assert "writing_task" not in Base.metadata.tables
    assert "article" not in Base.metadata.tables


def test_model_table_names_are_stable():
    assert find_spec("app.geo_monitoring.models") is not None

    from app.geo_monitoring.models import (
        AIPlatform,
        Brand,
        BrandAlias,
        MonitorProject,
        MonitorRun,
        Prompt,
        PromptSet,
        QueryTask,
    )

    assert MonitorProject.__tablename__ == "geo_monitor_project"
    assert Brand.__tablename__ == "geo_brand"
    assert BrandAlias.__tablename__ == "geo_brand_alias"
    assert PromptSet.__tablename__ == "geo_prompt_set"
    assert Prompt.__tablename__ == "geo_prompt"
    assert AIPlatform.__tablename__ == "geo_ai_platform"
    assert MonitorRun.__tablename__ == "geo_monitor_run"
    assert QueryTask.__tablename__ == "geo_query_task"


def test_project_and_run_input_validation():
    assert find_spec("app.geo_monitoring.schemas") is not None

    from app.geo_monitoring.schemas import ProjectCreate, RunCreate

    project = ProjectCreate(project_name="  测试项目  ")
    run = RunCreate(
        project_id=1,
        platform_codes=[" qwen ", "deepseek", "qwen"],
    )

    assert project.project_name == "测试项目"
    assert run.platform_codes == ["qwen", "deepseek"]
