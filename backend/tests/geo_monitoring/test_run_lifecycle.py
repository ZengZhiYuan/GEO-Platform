"""运行聚合、取消、重试与采集查询 API 生命周期测试。"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.services import runs as run_service
from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS


def _enable_molizhishu_runtime(session_factory) -> None:
    import os

    from app.core.config import get_settings
    from app.geo_monitoring.services import collection as collection_service

    os.environ["MOLIZHISHU_ENABLED"] = "true"
    os.environ["MOLIZHISHU_API_TOKEN"] = "test-molizhishu-token"
    get_settings.cache_clear()
    runtime_settings = get_settings()
    collection_service.configure_runtime(
        collection_service.build_default_runtime(
            session_factory=session_factory,
            runtime_settings=runtime_settings,
        )
    )


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
        json={"set_name": "生命周期", "version_no": "v1"},
    ).json()["data"]
    prompt_ids = []
    for index in range(prompt_count):
        prompt = client.post(
            f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/prompts",
            json={
                "prompt_code": f"lc_{index + 1}",
                "prompt_text": f"问题 {index + 1}",
                "sort_order": index,
            },
        ).json()["data"]
        prompt_ids.append(prompt["id"])
    activated = client.post(
        f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/activate"
    ).json()["data"]
    return {"prompt_set": activated, "prompt_ids": prompt_ids}


def _create_run(client, project_id: int, *, platform_codes: list[str] | None = None) -> dict:
    payload: dict = {"project_id": project_id, "collection_source": "official"}
    if platform_codes is not None:
        payload["platform_codes"] = platform_codes
    return client.post("/api/geo-monitoring/runs", json=payload).json()["data"]


def _set_task_statuses(session_factory, run_id: int, statuses: list[str]) -> list[int]:
    with session_factory() as db:
        tasks = list(
            db.execute(
                select(QueryTask)
                .where(QueryTask.run_id == run_id, QueryTask.is_deleted.is_(False))
                .order_by(QueryTask.id)
            )
            .scalars()
            .all()
        )
        assert len(tasks) == len(statuses)
        now = datetime.now(timezone.utc)
        for task, status in zip(tasks, statuses, strict=True):
            task.status = status
            if status == "success":
                task.completed_at = now
                task.finished_at = now
            elif status in {"failed", "cancelled"}:
                task.error_code = "server_error"
                task.error_message = f"{status} task"
                task.completed_at = now
                task.finished_at = now
        db.commit()
        return [task.id for task in tasks]


def test_create_run_auto_enqueues_and_enters_collecting(
    client, session_factory, project_id
):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})

    run = _create_run(client, project_id, platform_codes=["qwen"])
    tasks = client.get(f"/api/geo-monitoring/runs/{run['id']}/tasks").json()["data"]

    assert run["status"] == "collecting"
    assert run["collection_status"] == "running"
    assert run["started_at"] is not None
    assert tasks["total"] == 1
    assert tasks["items"][0]["status"] == "queued"
    assert tasks["items"][0]["queued_at"] is not None


def test_aggregate_run_completed_when_all_tasks_succeed(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=2)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])
    _set_task_statuses(session_factory, run["id"], ["success", "success"])

    detail = client.get(f"/api/geo-monitoring/runs/{run['id']}").json()["data"]
    listed = client.get(
        "/api/geo-monitoring/runs",
        params={"project_id": project_id},
    ).json()["data"]

    assert detail["status"] == "completed"
    assert detail["collection_status"] == "completed"
    assert detail["succeeded_tasks"] == 2
    assert detail["failed_tasks"] == 0
    assert detail["cancelled_tasks"] == 0
    assert detail["progress_rate"] == "1.0000"
    assert detail["finished_at"] is not None
    assert listed["items"][0]["succeeded_tasks"] == 2


def test_aggregate_run_partial_success_when_mixed_outcomes(
    client, session_factory, project_id
):
    _active_prompt_setup(client, project_id, prompt_count=2)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])
    _set_task_statuses(session_factory, run["id"], ["success", "failed"])

    detail = client.get(f"/api/geo-monitoring/runs/{run['id']}").json()["data"]

    assert detail["status"] == "partial_success"
    assert detail["collection_status"] == "partial_success"
    assert detail["succeeded_tasks"] == 1
    assert detail["failed_tasks"] == 1
    assert detail["error_summary"] is not None


def test_aggregate_run_failed_when_all_tasks_failed(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])
    _set_task_statuses(session_factory, run["id"], ["failed"])

    detail = client.get(f"/api/geo-monitoring/runs/{run['id']}").json()["data"]

    assert detail["status"] == "failed"
    assert detail["collection_status"] == "failed"
    assert detail["succeeded_tasks"] == 0
    assert detail["failed_tasks"] == 1


def test_terminal_run_status_does_not_regress(client, session_factory, project_id, db):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])
    _set_task_statuses(session_factory, run["id"], ["success"])
    first = client.get(f"/api/geo-monitoring/runs/{run['id']}").json()["data"]
    assert first["status"] == "completed"

    task = db.execute(
        select(QueryTask).where(QueryTask.run_id == run["id"])
    ).scalar_one()
    task.status = "failed"
    db.commit()

    second = client.get(f"/api/geo-monitoring/runs/{run['id']}").json()["data"]
    assert second["status"] == "completed"


def test_cancel_run_cancels_incomplete_tasks(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=2)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])
    _set_task_statuses(session_factory, run["id"], ["success", "queued"])

    cancelled = client.post(
        f"/api/geo-monitoring/runs/{run['id']}/cancel"
    ).json()["data"]
    tasks = client.get(
        f"/api/geo-monitoring/runs/{run['id']}/tasks"
    ).json()["data"]["items"]

    assert cancelled["status"] == "cancelled"
    assert cancelled["collection_status"] == "cancelled"
    assert cancelled["cancelled_tasks"] == 1
    assert cancelled["succeeded_tasks"] == 1
    statuses = {task["status"] for task in tasks}
    assert statuses == {"success", "cancelled"}


def test_cancel_run_is_idempotent(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])

    first = client.post(f"/api/geo-monitoring/runs/{run['id']}/cancel").json()
    second = client.post(f"/api/geo-monitoring/runs/{run['id']}/cancel").json()

    assert first["code"] == 0
    assert second["code"] == 0
    assert first["data"]["status"] == "cancelled"
    assert second["data"]["status"] == "cancelled"


def test_retry_failed_requeues_only_failed_tasks(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=2)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])
    task_ids = _set_task_statuses(session_factory, run["id"], ["success", "failed"])

    with session_factory() as db:
        failed = db.get(QueryTask, task_ids[1])
        failed.attempt_count = 2
        db.commit()

    retried = client.post(
        f"/api/geo-monitoring/runs/{run['id']}/retry-failed"
    ).json()["data"]
    tasks = client.get(
        f"/api/geo-monitoring/runs/{run['id']}/tasks",
        params={"status": "queued"},
    ).json()["data"]

    assert retried["retried_count"] == 1
    assert retried["status"] == "collecting"
    assert tasks["total"] == 1
    assert tasks["items"][0]["id"] == task_ids[1]
    assert tasks["items"][0]["attempt_count"] == 3


def test_retry_failed_is_idempotent_when_no_failed_tasks(
    client, session_factory, project_id
):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])
    _set_task_statuses(session_factory, run["id"], ["success"])
    client.get(f"/api/geo-monitoring/runs/{run['id']}")

    first = client.post(
        f"/api/geo-monitoring/runs/{run['id']}/retry-failed"
    ).json()["data"]
    second = client.post(
        f"/api/geo-monitoring/runs/{run['id']}/retry-failed"
    ).json()["data"]

    assert first["retried_count"] == 0
    assert second["retried_count"] == 0


def test_retry_failed_rejects_cancelled_run(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])
    client.post(f"/api/geo-monitoring/runs/{run['id']}/cancel")

    response = client.post(
        f"/api/geo-monitoring/runs/{run['id']}/retry-failed"
    ).json()

    assert response["code"] == 40040


def test_list_runs_filters_by_status_and_created_range(
    client, session_factory, project_id, db
):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])
    _set_task_statuses(session_factory, run["id"], ["success"])
    client.get(f"/api/geo-monitoring/runs/{run['id']}")

    now = datetime.now(timezone.utc)
    with session_factory() as session:
        stored = session.get(MonitorRun, run["id"])
        stored.created_at = now - timedelta(days=2)
        session.commit()

    in_range = client.get(
        "/api/geo-monitoring/runs",
        params={
            "project_id": project_id,
            "status": "completed",
            "created_after": (now - timedelta(days=3)).isoformat(),
            "created_before": (now - timedelta(days=1)).isoformat(),
        },
    ).json()["data"]
    out_of_range = client.get(
        "/api/geo-monitoring/runs",
        params={
            "project_id": project_id,
            "created_after": now.isoformat(),
        },
    ).json()["data"]

    assert in_range["total"] == 1
    assert in_range["items"][0]["id"] == run["id"]
    assert out_of_range["total"] == 0


def _seed_molizhishu_run_with_provider_tasks(
    client,
    session_factory,
    project_id: int,
    *,
    statuses: list[str],
    provider_task_ids: list[str | None],
) -> dict:
    from app.geo_monitoring.models import MonitorProject

    _enable_molizhishu_runtime(session_factory)
    _active_prompt_setup(client, project_id, prompt_count=len(statuses))
    _seed_platforms(session_factory)
    with session_factory() as db:
        project = db.get(MonitorProject, project_id)
        project.default_platform_codes = ["molizhishu_doubao_web"]
        db.commit()

    run = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "molizhishu",
            "platform_codes": ["molizhishu_doubao_web"],
        },
    ).json()["data"]

    with session_factory() as db:
        tasks = list(
            db.execute(
                select(QueryTask)
                .where(QueryTask.run_id == run["id"], QueryTask.is_deleted.is_(False))
                .order_by(QueryTask.id)
            )
            .scalars()
            .all()
        )
        assert len(tasks) == len(statuses)
        now = datetime.now(timezone.utc)
        for task, status, provider_task_id in zip(
            tasks, statuses, provider_task_ids, strict=True
        ):
            task.status = status
            if provider_task_id:
                task.provider_task_id = provider_task_id
                task.provider_subtask_id = f"sub-{task.id}"
                task.provider_name = "molizhishu"
            if status == "success":
                task.completed_at = now
                task.finished_at = now
            elif status in {"failed", "cancelled"}:
                task.completed_at = now
                task.finished_at = now
        db.commit()
    return run


def test_cancel_molizhishu_run_schedules_provider_stop_after_local_cancel(
    client, session_factory, project_id, monkeypatch
):
    from app.geo_monitoring.services import collection as collection_service

    run = _seed_molizhishu_run_with_provider_tasks(
        client,
        session_factory,
        project_id,
        statuses=["success", "running"],
        provider_task_ids=[None, "provider-task-1"],
    )
    with session_factory() as db:
        running_task = db.execute(
            select(QueryTask).where(
                QueryTask.run_id == run["id"],
                QueryTask.provider_task_id == "provider-task-1",
            )
        ).scalar_one()
        expected_subtask_id = running_task.provider_subtask_id

    scheduled: list[tuple[int, dict[str, list[str | None]]]] = []
    sync_stop_calls: list[int] = []

    def _record_schedule(run_id: int, targets: dict[str, list[str | None]]) -> bool:
        scheduled.append((run_id, dict(targets)))
        return True

    def _reject_sync_stop(db, run_id: int) -> int:
        sync_stop_calls.append(run_id)
        raise AssertionError("cancel API must not synchronously call provider stop")

    monkeypatch.setattr(
        collection_service,
        "schedule_molizhishu_provider_stop",
        _record_schedule,
    )
    monkeypatch.setattr(
        collection_service,
        "stop_molizhishu_provider_tasks_for_run",
        _reject_sync_stop,
    )

    cancelled = client.post(
        f"/api/geo-monitoring/runs/{run['id']}/cancel"
    ).json()["data"]

    assert sync_stop_calls == []
    assert scheduled == [
        (run["id"], {"provider-task-1": [expected_subtask_id]}),
    ]
    assert cancelled["status"] == "cancelled"
    assert cancelled["succeeded_tasks"] == 1
    assert cancelled["cancelled_tasks"] == 1


def test_cancel_molizhishu_run_preserves_successful_tasks(
    client, session_factory, project_id, monkeypatch
):
    from app.geo_monitoring.services import collection as collection_service

    monkeypatch.setattr(
        collection_service,
        "schedule_molizhishu_provider_stop",
        lambda run_id, targets: False,
    )
    run = _seed_molizhishu_run_with_provider_tasks(
        client,
        session_factory,
        project_id,
        statuses=["success", "queued"],
        provider_task_ids=["provider-task-done", "provider-task-pending"],
    )

    client.post(f"/api/geo-monitoring/runs/{run['id']}/cancel")
    tasks = client.get(
        f"/api/geo-monitoring/runs/{run['id']}/tasks"
    ).json()["data"]["items"]

    statuses = {task["status"] for task in tasks}
    assert statuses == {"success", "cancelled"}


def _seed_molizhishu_run_graph(db, *, task_specs: list[tuple[str, str | None, str | None]]) -> int:
    """task_specs: (status, provider_task_id, provider_subtask_id)"""
    project = MonitorProject(project_name="molizhishu-stop", status="active")
    db.add(project)
    db.flush()
    prompt_set = PromptSet(
        project_id=project.id,
        set_name="stop",
        version_no="v1",
        status="active",
        prompt_count=len(task_specs),
    )
    db.add(prompt_set)
    db.flush()
    prompt_ids: list[int] = []
    for index, _ in enumerate(task_specs):
        prompt = Prompt(
            prompt_set_id=prompt_set.id,
            prompt_code=f"p{index}",
            prompt_text=f"q{index}",
            content_hash=f"{index:064d}",
        )
        db.add(prompt)
        db.flush()
        prompt_ids.append(prompt.id)
    run = MonitorRun(
        run_no="RUN-STOP-TEST",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        trigger_type="manual",
        status="collecting",
        collection_status="running",
        analysis_status="skipped",
        report_status="skipped",
        collection_source="molizhishu",
        platform_codes=["molizhishu_doubao_web"],
        expected_query_count=len(task_specs),
        total_tasks=len(task_specs),
    )
    db.add(run)
    db.flush()
    for index, (status, provider_task_id, provider_subtask_id) in enumerate(task_specs):
        db.add(
            QueryTask(
                run_id=run.id,
                prompt_id=prompt_ids[index],
                platform_code="molizhishu_doubao_web",
                idempotency_key=f"stop-test-{run.id}-{index}",
                status=status,
                provider_task_id=provider_task_id,
                provider_subtask_id=provider_subtask_id,
                provider_name="molizhishu" if provider_task_id else None,
            )
        )
    db.commit()
    return run.id


def test_collect_molizhishu_provider_stop_targets_filters_dedupes_and_skips_blank(
    db,
):
    from app.geo_monitoring.services import collection as collection_service

    run_id = _seed_molizhishu_run_graph(
        db,
        task_specs=[
            ("success", "task-done", "sub-done"),
            ("failed", "task-failed", "sub-failed"),
            ("cancelled", "task-cancelled", "sub-cancelled"),
            ("running", "task-shared", "sub-a"),
            ("queued", "task-shared", "sub-b"),
            ("running", "  ", "sub-blank"),
            ("pending", "task-pending", "sub-pending"),
        ],
    )

    targets = collection_service.collect_molizhishu_provider_stop_targets(db, run_id)

    assert set(targets) == {"task-shared", "task-pending"}
    assert set(targets["task-shared"]) == {"sub-a", "sub-b"}
    assert targets["task-pending"] == ["sub-pending"]


def test_stop_molizhishu_provider_tasks_continues_after_adapter_error(
    session_factory, tmp_path, monkeypatch
):
    import asyncio

    from app.core.config import Settings
    from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory
    from app.geo_monitoring.adapters.key_pool import ApiKeyCredential, CredentialKeyPool
    from app.geo_monitoring.adapters.molizhishu import MolizhishuAdapter
    from app.geo_monitoring.adapters.registry import AdapterRegistry
    from app.geo_monitoring.services import collection as collection_service
    from app.geo_monitoring.services.platforms import MOLIZHISHU_PLATFORM_MAPPINGS

    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="stub",
        NACOS_ENABLED=False,
        REPORT_STORAGE_DIR=str(tmp_path),
        MOLIZHISHU_ENABLED=True,
        MOLIZHISHU_BASE_URL="https://molizhishu.test",
        MOLIZHISHU_API_TOKEN="token",
    )
    registry = AdapterRegistry()
    platform_code = next(iter(MOLIZHISHU_PLATFORM_MAPPINGS))
    mapping = MOLIZHISHU_PLATFORM_MAPPINGS[platform_code]
    registry.register(
        MolizhishuAdapter(
            code=platform_code,
            molizhishu_platform=mapping["molizhishu_platform"],
            default_mode=mapping["default_mode"],
            base_url="https://molizhishu.test",
            timeout_seconds=0.2,
            raw_response_enabled=False,
        )
    )
    key_pool = CredentialKeyPool(None)
    key_pool.register_platform_credentials(
        platform_code,
        [ApiKeyCredential(platform_code=platform_code, api_key="token")],
    )
    collection_service.configure_runtime(
        collection_service.CollectionRuntime(
            session_factory=session_factory,
            settings=settings,
            adapter_registry=registry,
            key_pool=key_pool,
        )
    )

    stop_calls: list[str] = []

    async def fake_stop_task(self, task_id, *, credential):
        stop_calls.append(task_id)
        if task_id == "task-bad":
            raise AdapterError("stop failed", category=ErrorCategory.INVALID_REQUEST)

    monkeypatch.setattr(MolizhishuAdapter, "stop_task", fake_stop_task)
    try:
        stopped = asyncio.run(
            collection_service._stop_molizhishu_provider_tasks_async(
                99,
                {
                    "task-bad": ["sub-bad"],
                    "task-good": ["sub-good"],
                },
            )
        )
    finally:
        collection_service.reset_runtime()

    assert set(stop_calls) == {"task-bad", "task-good"}
    assert stopped == 1


def test_run_answers_and_answer_detail(client, session_factory, project_id, db):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS if p["platform_code"] != "qwen"})
    run = _create_run(client, project_id, platform_codes=["qwen"])
    task_ids = _set_task_statuses(session_factory, run["id"], ["success"])

    with session_factory() as session:
        task = session.get(QueryTask, task_ids[0])
        session.add(
            Answer(
                task_id=task.id,
                platform_code=task.platform_code,
                prompt_id=task.prompt_id,
                raw_text="  有效回答  ",
                normalized_text="有效回答",
            )
        )
        session.commit()

    listed = client.get(
        f"/api/geo-monitoring/runs/{run['id']}/answers"
    ).json()["data"]
    detail = client.get(
        f"/api/geo-monitoring/answers/{listed['items'][0]['id']}"
    ).json()["data"]

    assert listed["total"] == 1
    assert detail["normalized_text"] == "有效回答"
    assert detail["citations"] == []
    assert detail["brand_results"] == []
