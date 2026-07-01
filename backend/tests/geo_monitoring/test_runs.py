import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.geo_monitoring.models import (
    AIPlatform,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.repositories import runs as run_repo
from app.geo_monitoring.schemas import RunCreate
from app.geo_monitoring.services import collection as collection_service
from app.geo_monitoring.services import runs as run_service
from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS, OFFICIAL_PLATFORMS


def _disabled_except(*enabled_codes: str) -> set[str]:
    enabled = set(enabled_codes)
    return {
        platform["platform_code"]
        for platform in DEFAULT_PLATFORMS
        if platform["platform_code"] not in enabled
    }


def _seed_platforms(session_factory, disabled: set[str] | None = None) -> None:
    disabled = disabled or set()
    with session_factory() as db:
        db.add_all(
            AIPlatform(
                **platform,
                enabled=platform["platform_code"] not in disabled,
            )
            for platform in DEFAULT_PLATFORMS
        )
        db.commit()


def _active_prompt_setup(client, project_id: int, prompt_count: int = 2) -> dict:
    prompt_set = client.post(
        f"/api/geo-monitoring/projects/{project_id}/prompt-sets",
        json={"set_name": "运行提示词", "version_no": "v1"},
    ).json()["data"]
    prompt_ids = []
    for index in range(prompt_count):
        prompt = client.post(
            f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/prompts",
            json={
                "prompt_code": f"prompt_{index + 1}",
                "prompt_text": f"监测问题 {index + 1}",
                "sort_order": index,
            },
        ).json()["data"]
        prompt_ids.append(prompt["id"])
    activated = client.post(
        f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/activate"
    ).json()["data"]
    return {"prompt_set": activated, "prompt_ids": prompt_ids}


def test_create_run_builds_prompt_platform_cartesian_product(
    client, session_factory, project_id
):
    setup = _active_prompt_setup(client, project_id, prompt_count=2)
    _seed_platforms(session_factory)

    response = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "platform_codes": ["qwen", "deepseek", "kimi", "qwen"],
            "collection_source": "official",
        },
    ).json()
    run = response["data"]
    tasks = client.get(
        f"/api/geo-monitoring/runs/{run['id']}/query-tasks"
    ).json()["data"]
    qwen_tasks = client.get(
        f"/api/geo-monitoring/runs/{run['id']}/query-tasks",
        params={"platform_code": "qwen", "status": "queued"},
    ).json()["data"]

    assert response["code"] == 0
    assert run["prompt_set_id"] == setup["prompt_set"]["id"]
    assert run["prompt_set_version"] == "v1"
    assert run["platform_codes"] == ["qwen", "deepseek", "kimi"]
    assert run["expected_query_count"] == 6
    assert run["total_tasks"] == 6
    assert run["analysis_status"] == "skipped"
    assert run["report_status"] == "skipped"
    assert tasks["total"] == 6
    assert qwen_tasks["total"] == 2
    assert {
        (task["prompt_id"], task["platform_code"]) for task in tasks["items"]
    } == {
        (prompt_id, code)
        for prompt_id in setup["prompt_ids"]
        for code in ("qwen", "deepseek", "kimi")
    }


def test_create_run_uses_configured_collection_max_attempts(
    client, session_factory, project_id
):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={"doubao", "deepseek", "kimi", "yuanbao"})
    runtime = collection_service.get_runtime()
    runtime.settings.COLLECTION_MAX_ATTEMPTS = 5

    response = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "platform_codes": ["qwen"],
            "collection_source": "official",
        },
    ).json()

    with session_factory() as db:
        tasks = db.execute(
            select(QueryTask).where(QueryTask.run_id == response["data"]["id"])
        ).scalars().all()

    assert response["code"] == 0
    assert [task.max_attempts for task in tasks] == [5]


def test_create_molizhishu_run_persists_provider_fields(
    molizhishu_client, session_factory, project_id
):
    setup = _active_prompt_setup(molizhishu_client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    response = molizhishu_client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "molizhishu",
            "provider_mode_by_platform": {
                "molizhishu_doubao_web": "search",
                "molizhishu_kimi_web": "standard",
            },
            "provider_screenshot": 2,
            "region_code": "110000",
            "provider_callback_url": "https://example.com/callback",
            "platform_codes": ["molizhishu_doubao_web", "molizhishu_kimi_web"],
        },
    ).json()

    run = response["data"]
    assert response["code"] == 0
    assert run["prompt_set_id"] == setup["prompt_set"]["id"]
    assert run["prompt_set_version"] == "v1"
    assert run["collection_source"] == "molizhishu"
    assert run["provider_mode_by_platform"] == {
        "molizhishu_doubao_web": "search",
        "molizhishu_kimi_web": "standard",
    }
    assert run["provider_screenshot"] == 2
    assert run["region_code"] == "110000"
    assert run["provider_callback_url"] == "https://example.com/callback"
    assert run["platform_codes"] == ["molizhishu_doubao_web", "molizhishu_kimi_web"]
    assert run["expected_query_count"] == 2


def test_create_run_rejects_aidso_collection_source(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    response = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "aidso",
            "platform_codes": ["aidso_doubao_web"],
        },
    ).json()

    assert response["code"] == 422


def test_create_run_rejects_legacy_aidso_thinking_field(
    client, session_factory, project_id
):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    response = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "molizhishu",
            "platform_codes": ["molizhishu_doubao_web"],
            "aidso_thinking_enabled_by_platform": {"aidso_doubao_web": False},
        },
    ).json()

    assert response["code"] == 422


def test_molizhishu_run_rejected_when_provider_disabled(
    client, session_factory, project_id
):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    response = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "molizhishu",
            "platform_codes": ["molizhishu_doubao_web"],
        },
    ).json()

    assert response["code"] == 40908
    assert "MOLIZHISHU_ENABLED" in response["message"]


def test_official_run_rejected_when_platform_runtime_not_configured(
    client, session_factory, project_id, monkeypatch
):
    from app.core.config import Settings
    from app.geo_monitoring.services import collection as collection_service

    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)
    disabled_runtime = collection_service.build_default_runtime(
        session_factory=session_factory,
        runtime_settings=Settings(
            _env_file=None,
            APP_ENV="test",
            DATABASE_URL="sqlite+pysqlite:///:memory:",
            REDIS_URL="redis://test-redis.invalid:6379/15",
            DRAMATIQ_BROKER="stub",
            NACOS_ENABLED=False,
            REPORT_STORAGE_DIR="data/reports",
            QWEN_ENABLED=False,
            QWEN_API_KEYS="",
            QWEN_MODEL="",
        ),
    )
    monkeypatch.setattr(collection_service, "get_runtime", lambda: disabled_runtime)

    response = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "platform_codes": ["qwen"],
            "collection_source": "official",
        },
    ).json()

    assert response["code"] == 40908
    assert "qwen" in response["message"]


def test_ready_includes_platform_runtime_diagnostics(
    client, session_factory, project_id, monkeypatch
):
    _seed_platforms(session_factory)
    monkeypatch.setattr(
        "app.main.check_readiness",
        lambda: {
            "status": "ready",
            "database": {"ok": True, "target": "sqlite:///:memory:"},
            "redis": {"ok": True, "target": "redis://redis.test:6379/0"},
        },
    )

    def _platform_runtime(_db):
        from app.geo_monitoring.services.collection import platform_runtime_diagnostics

        with session_factory() as db:
            return platform_runtime_diagnostics(db)

    monkeypatch.setattr("app.main.check_platform_runtime_diagnostics", _platform_runtime)
    response = client.get("/api/geo-monitoring/ready")
    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    platform_runtime = body["data"]["platform_runtime"]
    assert "platforms" in platform_runtime
    assert "collection_ready" in platform_runtime
    qwen = next(
        item
        for item in platform_runtime["platforms"]
        if item["platform_code"] == "qwen"
    )
    assert qwen["db_enabled"] is True
    assert qwen["adapter_registered"] is True
    assert qwen["runtime_configured"] is True
    assert qwen["credential_count"] >= 1
    molizhishu = next(
        item
        for item in platform_runtime["platforms"]
        if item["platform_code"] == "molizhishu_doubao_web"
    )
    assert molizhishu["db_enabled"] is True
    assert molizhishu["adapter_registered"] is False
    assert molizhishu["runtime_configured"] is False


def test_molizhishu_run_rejects_official_platform(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    body = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "molizhishu",
            "platform_codes": ["qwen"],
        },
    ).json()

    assert body["code"] == 40031


def test_molizhishu_run_rejects_invalid_mode_via_api(
    molizhishu_client, session_factory, project_id
):
    _active_prompt_setup(molizhishu_client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    response = molizhishu_client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "molizhishu",
            "platform_codes": ["molizhishu_doubao_web"],
            "provider_mode_by_platform": {"molizhishu_doubao_web": "reasoning"},
        },
    ).json()

    assert response["code"] == 422


def test_molizhishu_run_rejects_provider_mode_outside_default_platforms(
    molizhishu_client, session_factory, project_id
):
    from app.geo_monitoring.models import MonitorProject

    _active_prompt_setup(molizhishu_client, project_id, prompt_count=1)
    _seed_platforms(session_factory)
    with session_factory() as db:
        project = db.get(MonitorProject, project_id)
        project.default_platform_codes = ["molizhishu_doubao_web"]
        db.commit()

    response = molizhishu_client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "molizhishu",
            "provider_mode_by_platform": {"molizhishu_kimi_web": "search"},
        },
    ).json()

    assert response["code"] == 422
    assert "provider_mode_by_platform" in response["message"]


def test_molizhishu_run_persists_provider_mode_for_default_platforms(
    molizhishu_client, session_factory, project_id
):
    from app.geo_monitoring.models import MonitorProject

    _active_prompt_setup(molizhishu_client, project_id, prompt_count=1)
    _seed_platforms(session_factory)
    with session_factory() as db:
        project = db.get(MonitorProject, project_id)
        project.default_platform_codes = ["molizhishu_doubao_web"]
        db.commit()

    response = molizhishu_client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "molizhishu",
            "provider_mode_by_platform": {"molizhishu_doubao_web": "search"},
        },
    ).json()

    run = response["data"]
    assert response["code"] == 0
    assert run["platform_codes"] == ["molizhishu_doubao_web"]
    assert run["provider_mode_by_platform"] == {"molizhishu_doubao_web": "search"}


def test_molizhishu_run_inherits_provider_mode_from_project_platform_toggles(
    molizhishu_client, session_factory, project_id
):
    from app.geo_monitoring.models import MonitorProject

    _active_prompt_setup(molizhishu_client, project_id, prompt_count=1)
    _seed_platforms(session_factory)
    with session_factory() as db:
        project = db.get(MonitorProject, project_id)
        project.default_platform_codes = ["molizhishu_doubao_web"]
        project.deep_thinking_enabled_by_platform = {"molizhishu_doubao_web": False}
        project.search_enabled_by_platform = {"molizhishu_doubao_web": True}
        db.commit()

    response = molizhishu_client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "molizhishu",
        },
    ).json()

    run = response["data"]
    assert response["code"] == 0
    assert run["platform_codes"] == ["molizhishu_doubao_web"]
    assert run["provider_mode_by_platform"] == {"molizhishu_doubao_web": "search"}


def test_official_run_defaults_to_active_prompt_set_and_enabled_platforms(
    client, session_factory, project_id
):
    setup = _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled=_disabled_except("doubao", "qwen"))

    created = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "collection_source": "official"},
    ).json()["data"]
    listed = client.get(
        "/api/geo-monitoring/runs", params={"project_id": project_id}
    ).json()["data"]
    detail = client.get(
        f"/api/geo-monitoring/runs/{created['id']}"
    ).json()["data"]

    assert created["prompt_set_id"] == setup["prompt_set"]["id"]
    assert created["platform_codes"] == ["doubao", "qwen"]
    assert created["expected_query_count"] == 2
    assert listed["total"] == 1
    assert detail["run_no"].startswith("RUN-")


def test_molizhishu_run_defaults_to_enabled_molizhishu_platforms(
    molizhishu_client, session_factory, project_id
):
    from app.geo_monitoring.services.platforms import MOLIZHISHU_PLATFORMS

    setup = _active_prompt_setup(molizhishu_client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    created = molizhishu_client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id},
    ).json()["data"]

    molizhishu_codes = {
        platform["platform_code"] for platform in MOLIZHISHU_PLATFORMS
    }
    assert created["collection_source"] == "molizhishu"
    assert created["prompt_set_id"] == setup["prompt_set"]["id"]
    assert set(created["platform_codes"]) == molizhishu_codes
    assert created["expected_query_count"] == len(molizhishu_codes)


def test_official_run_defaults_exclude_molizhishu_when_all_platforms_enabled(
    client, session_factory, project_id
):
    setup = _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    created = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "collection_source": "official"},
    ).json()["data"]

    official_codes = {platform["platform_code"] for platform in OFFICIAL_PLATFORMS}
    assert created["prompt_set_id"] == setup["prompt_set"]["id"]
    assert set(created["platform_codes"]) == official_codes
    assert created["expected_query_count"] == len(official_codes)
    assert not any(code.startswith("molizhishu_") for code in created["platform_codes"])


def test_run_rejects_cross_project_prompt_set_and_unavailable_platforms(
    client, session_factory, project_id
):
    setup = _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={"kimi"})
    other_project = client.post(
        "/api/geo-monitoring/projects",
        json={"project_name": "另一个项目"},
    ).json()["data"]

    cross_project = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": other_project["id"],
            "prompt_set_id": setup["prompt_set"]["id"],
        },
    ).json()
    disabled = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "platform_codes": ["kimi"]},
    ).json()
    unknown = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "platform_codes": ["unknown"]},
    ).json()

    assert cross_project["code"] == 40030
    assert disabled["code"] == 40031
    assert unknown["code"] == 40031


def test_molizhishu_run_rejects_aidso_platform(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)
    with session_factory() as db:
        db.add(
            AIPlatform(
                platform_code="aidso_doubao_web",
                platform_name="豆包 Web 端",
                adapter_type="aidso",
                model_name="aidso:DB",
                enabled=True,
                extra_config={"aidso_name": "DB"},
            )
        )
        db.commit()

    body = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "platform_codes": ["aidso_doubao_web"]},
    ).json()

    assert body["code"] == 40031


def test_official_run_rejects_molizhishu_platform(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    body = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "platform_codes": ["molizhishu_doubao_web"],
            "collection_source": "official",
        },
    ).json()

    assert body["code"] == 40031




def test_run_rejects_inactive_project_and_empty_enabled_prompts(
    client, session_factory, project_id
):
    setup = _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)
    client.put(
        f"/api/geo-monitoring/projects/{project_id}",
        json={"status": "disabled"},
    )

    inactive = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "collection_source": "official"},
    ).json()
    client.put(
        f"/api/geo-monitoring/projects/{project_id}",
        json={"status": "active"},
    )
    with session_factory() as db:
        prompt = db.get(Prompt, setup["prompt_ids"][0])
        prompt.enabled = False
        db.commit()
    empty = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "collection_source": "official"},
    ).json()

    assert inactive["code"] == 40001
    assert empty["code"] == 40901


def test_run_creation_rolls_back_when_task_insert_fails(db, monkeypatch):
    project = MonitorProject(project_name="回滚项目", status="active")
    db.add(project)
    db.flush()
    prompt_set = PromptSet(
        project_id=project.id,
        set_name="回滚提示词",
        version_no="v1",
        status="active",
        prompt_count=1,
    )
    db.add(prompt_set)
    db.flush()
    db.add(
        Prompt(
            prompt_set_id=prompt_set.id,
            prompt_code="rollback",
            prompt_text="回滚测试",
            content_hash="a" * 64,
        )
    )
    db.add(AIPlatform(**DEFAULT_PLATFORMS[0]))
    db.commit()
    before_runs = db.scalar(select(func.count()).select_from(MonitorRun))

    def fail_after_run_flush(*args, **kwargs):
        raise RuntimeError("forced fan-out failure")

    monkeypatch.setattr(run_repo, "build_query_tasks", fail_after_run_flush)
    with pytest.raises(RuntimeError, match="forced fan-out failure"):
        run_service.create_run(
            db,
            RunCreate(project_id=project.id, collection_source="official"),
        )

    after_runs = db.scalar(select(func.count()).select_from(MonitorRun))
    assert after_runs == before_runs
