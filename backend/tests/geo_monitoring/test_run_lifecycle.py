"""运行聚合、取消、重试与采集查询 API 生命周期测试。"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    MonitorRun,
    QueryTask,
)
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
    payload: dict = {"project_id": project_id}
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
