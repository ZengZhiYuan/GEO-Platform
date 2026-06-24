import pytest
from sqlalchemy import func, select

from app.geo_monitoring.models import (
    AIPlatform,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
)
from app.geo_monitoring.repositories import runs as run_repo
from app.geo_monitoring.schemas import RunCreate
from app.geo_monitoring.services import runs as run_service
from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS


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


def test_create_aidso_run_persists_collection_source(
    client, session_factory, project_id
):
    setup = _active_prompt_setup(client, project_id, prompt_count=1)
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

    response = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "aidso",
            "aidso_thinking_enabled": False,
            "platform_codes": ["aidso_doubao_web"],
        },
    ).json()

    run = response["data"]
    assert response["code"] == 0
    assert run["prompt_set_id"] == setup["prompt_set"]["id"]
    assert run["prompt_set_version"] == "v1"
    assert run["collection_source"] == "aidso"
    assert run["aidso_thinking_enabled"] is False
    assert run["platform_codes"] == ["aidso_doubao_web"]
    assert run["expected_query_count"] == 1


def test_run_defaults_to_active_prompt_set_and_enabled_platforms(
    client, session_factory, project_id
):
    setup = _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={"yuanbao", "deepseek", "kimi"})

    created = client.post(
        "/api/geo-monitoring/runs", json={"project_id": project_id}
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


def test_official_run_rejects_aidso_platform(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    body = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "platform_codes": ["aidso_doubao_web"]},
    ).json()

    assert body["code"] == 40031


def test_aidso_run_rejects_official_platform(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)

    body = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "aidso",
            "platform_codes": ["qwen"],
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
        "/api/geo-monitoring/runs", json={"project_id": project_id}
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
        "/api/geo-monitoring/runs", json={"project_id": project_id}
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
        run_service.create_run(db, RunCreate(project_id=project.id))

    after_runs = db.scalar(select(func.count()).select_from(MonitorRun))
    assert after_runs == before_runs
