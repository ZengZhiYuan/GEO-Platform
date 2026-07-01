from importlib.util import find_spec

import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import IntegrityError


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
        "geo_provider_batch",
        "geo_query_task",
        "geo_answer",
        "geo_answer_citation",
        "geo_answer_brand_result",
    }
    assert expected.issubset(Base.metadata.tables)
    assert "keyword_library" not in Base.metadata.tables
    assert "writing_task" not in Base.metadata.tables
    assert "article" not in Base.metadata.tables


def test_model_table_names_are_stable():
    assert find_spec("app.geo_monitoring.models") is not None

    from app.geo_monitoring.models import (
        AIPlatform,
        Answer,
        AnswerBrandResult,
        AnswerCitation,
        Brand,
        BrandAlias,
        MonitorProject,
        MonitorRun,
        Prompt,
        PromptSet,
        ProviderBatch,
        QueryTask,
    )

    assert MonitorProject.__tablename__ == "geo_monitor_project"
    assert Brand.__tablename__ == "geo_brand"
    assert BrandAlias.__tablename__ == "geo_brand_alias"
    assert PromptSet.__tablename__ == "geo_prompt_set"
    assert Prompt.__tablename__ == "geo_prompt"
    assert AIPlatform.__tablename__ == "geo_ai_platform"
    assert MonitorRun.__tablename__ == "geo_monitor_run"
    assert ProviderBatch.__tablename__ == "geo_provider_batch"
    assert QueryTask.__tablename__ == "geo_query_task"
    assert Answer.__tablename__ == "geo_answer"
    assert AnswerCitation.__tablename__ == "geo_answer_citation"
    assert AnswerBrandResult.__tablename__ == "geo_answer_brand_result"


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
    assert run.collection_source == "molizhishu"
    assert run.provider_mode_by_platform == {}
    assert run.provider_screenshot == 0
    assert run.region_code is None
    assert run.provider_callback_url is None


def test_run_create_accepts_molizhishu_collection_source_with_valid_mode():
    from app.geo_monitoring.schemas import RunCreate

    run = RunCreate(
        project_id=1,
        collection_source="molizhishu",
        provider_mode_by_platform={
            " molizhishu_doubao_web ": "search",
            "molizhishu_kimi_web": "standard",
        },
        provider_screenshot=1,
        region_code=" 110000 ",
        provider_callback_url=" https://example.com/callback ",
        platform_codes=["molizhishu_doubao_web", "molizhishu_kimi_web"],
    )

    assert run.collection_source == "molizhishu"
    assert run.provider_mode_by_platform == {
        "molizhishu_doubao_web": "search",
        "molizhishu_kimi_web": "standard",
    }
    assert run.provider_screenshot == 1
    assert run.region_code == "110000"
    assert run.provider_callback_url == "https://example.com/callback"


def test_run_create_rejects_aidso_collection_source():
    from pydantic import ValidationError

    from app.geo_monitoring.schemas import RunCreate

    with pytest.raises(ValidationError):
        RunCreate(
            project_id=1,
            collection_source="aidso",
            platform_codes=["aidso_doubao_web"],
        )


def test_run_create_rejects_legacy_aidso_thinking_field():
    from pydantic import ValidationError

    from app.geo_monitoring.schemas import RunCreate

    with pytest.raises(ValidationError):
        RunCreate(
            project_id=1,
            collection_source="molizhishu",
            platform_codes=["molizhishu_doubao_web"],
            aidso_thinking_enabled_by_platform={"aidso_doubao_web": False},
        )


def test_run_create_rejects_invalid_provider_mode():
    from pydantic import ValidationError

    from app.geo_monitoring.schemas import RunCreate

    with pytest.raises(ValidationError):
        RunCreate(
            project_id=1,
            collection_source="molizhishu",
            platform_codes=["molizhishu_doubao_web"],
            provider_mode_by_platform={"molizhishu_doubao_web": "reasoning"},
        )


def test_run_create_rejects_unknown_provider_mode_platform():
    from pydantic import ValidationError

    from app.geo_monitoring.schemas import RunCreate

    with pytest.raises(ValidationError):
        RunCreate(
            project_id=1,
            collection_source="molizhishu",
            platform_codes=["molizhishu_doubao_web"],
            provider_mode_by_platform={"qwen": "search"},
        )


def test_run_create_rejects_provider_mode_platform_outside_requested_platforms():
    from pydantic import ValidationError

    from app.geo_monitoring.schemas import RunCreate

    with pytest.raises(ValidationError):
        RunCreate(
            project_id=1,
            collection_source="molizhishu",
            platform_codes=["molizhishu_doubao_web"],
            provider_mode_by_platform={"molizhishu_kimi_web": "search"},
        )


def test_run_create_rejects_invalid_provider_screenshot():
    from pydantic import ValidationError

    from app.geo_monitoring.schemas import RunCreate

    with pytest.raises(ValidationError):
        RunCreate(
            project_id=1,
            collection_source="molizhishu",
            platform_codes=["molizhishu_doubao_web"],
            provider_screenshot=3,
        )


def test_run_create_rejects_bool_provider_screenshot():
    from pydantic import ValidationError

    from app.geo_monitoring.schemas import RunCreate

    with pytest.raises(ValidationError):
        RunCreate(
            project_id=1,
            collection_source="molizhishu",
            platform_codes=["molizhishu_doubao_web"],
            provider_screenshot=True,
        )


def test_run_create_applies_molizhishu_default_screenshot_when_omitted(monkeypatch):
    from app.geo_monitoring.schemas import RunCreate

    monkeypatch.setattr("app.core.config.settings.MOLIZHISHU_DEFAULT_SCREENSHOT", 2)

    payload = RunCreate(
        project_id=1,
        collection_source="molizhishu",
        platform_codes=["molizhishu_doubao_web"],
    )

    assert payload.provider_screenshot == 2


def test_run_create_keeps_zero_default_for_official_when_explicit():
    from app.geo_monitoring.schemas import RunCreate

    payload = RunCreate(project_id=1, collection_source="official")

    assert payload.collection_source == "official"
    assert payload.provider_screenshot == 0
    assert "provider_screenshot" not in payload.model_fields_set


def test_run_create_defaults_to_molizhishu_when_omitted(monkeypatch):
    from app.geo_monitoring.schemas import RunCreate

    monkeypatch.setattr("app.core.config.settings.MOLIZHISHU_DEFAULT_SCREENSHOT", 2)

    payload = RunCreate(project_id=1, platform_codes=["molizhishu_doubao_web"])

    assert payload.collection_source == "molizhishu"
    assert payload.provider_screenshot == 2


def test_run_create_rejects_empty_region_code():
    from pydantic import ValidationError

    from app.geo_monitoring.schemas import RunCreate

    with pytest.raises(ValidationError):
        RunCreate(
            project_id=1,
            collection_source="molizhishu",
            platform_codes=["molizhishu_doubao_web"],
            region_code="   ",
        )


def _collection_source_check_sql() -> str:
    from app.geo_monitoring.models import MonitorRun

    for item in MonitorRun.__table_args__:
        if isinstance(item, CheckConstraint) and item.name == "ck_geo_monitor_run_collection_source":
            return str(item.sqltext)
    raise AssertionError("collection_source check constraint not found")


def test_monitor_run_collection_source_check_includes_molizhishu():
    assert "molizhishu" in _collection_source_check_sql()


def test_monitor_run_provider_fields_have_defaults():
    from app.geo_monitoring.models import MonitorRun

    table = MonitorRun.__table__
    assert table.c.provider_mode_by_platform.server_default is not None
    assert table.c.provider_screenshot.server_default is not None
    assert table.c.provider_callback_url.nullable is True
    assert table.c.region_code.nullable is True


def test_query_task_has_provider_tracking_columns():
    from app.geo_monitoring.models import QueryTask

    table = QueryTask.__table__
    for column in {
        "provider_name",
        "provider_task_id",
        "provider_subtask_id",
        "provider_platform_code",
        "provider_mode",
        "provider_status",
        "provider_result_json",
        "provider_error_message",
    }:
        assert column in table.c


def _seed_run(db, *, collection_source: str) -> None:
    from app.geo_monitoring.models import MonitorProject, MonitorRun, PromptSet

    project = MonitorProject(project_name="model-test")
    db.add(project)
    db.flush()
    prompt_set = PromptSet(
        project_id=project.id,
        set_name="default",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()
    db.add(
        MonitorRun(
            run_no=f"run-{collection_source}",
            project_id=project.id,
            prompt_set_id=prompt_set.id,
            prompt_set_version="v1",
            collection_source=collection_source,
            platform_codes=[],
        )
    )
    db.commit()


def test_persist_monitor_run_with_molizhishu_collection_source(db):
    from app.geo_monitoring.models import MonitorRun

    _seed_run(db, collection_source="molizhishu")
    run = db.query(MonitorRun).filter_by(run_no="run-molizhishu").one()
    assert run.collection_source == "molizhishu"
    assert run.provider_mode_by_platform == {}
    assert run.provider_screenshot == 0


def test_persist_monitor_run_with_aidso_collection_source_still_allowed(db):
    from app.geo_monitoring.models import MonitorRun

    _seed_run(db, collection_source="aidso")
    run = db.query(MonitorRun).filter_by(run_no="run-aidso").one()
    assert run.collection_source == "aidso"


def test_persist_monitor_run_rejects_unknown_collection_source(db):
    with pytest.raises(IntegrityError):
        _seed_run(db, collection_source="unknown")
