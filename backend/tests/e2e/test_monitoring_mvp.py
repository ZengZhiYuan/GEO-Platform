"""Backend MVP end-to-end tests using mock platform and Agent LLM."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest
import respx
from freezegun import freeze_time
from sqlalchemy import func, select

from app.geo_monitoring.models import Answer, MonitorRun, QueryTask
from app.geo_monitoring.schemas import ScheduleCreate
from app.geo_monitoring.services import schedules as schedule_service
from app.scheduler import jobs as scheduler_jobs
from app.worker.actors.analysis import analyze_run
from tests.e2e.conftest import (
    MOCK_QWEN_KEY,
    configure_mock_collection_runtime,
    configure_molizhishu_collection_runtime,
    drain_run_collection_sync,
    register_qwen_success_route,
    seed_molizhishu_platform,
)


@respx.mock
def test_monitoring_mvp_mock_end_to_end(
    client,
    session_factory,
    monkeypatch,
    e2e_project,
    fake_llm,
    tmp_path,
):
    monkeypatch.setenv("REPORT_STORAGE_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    register_qwen_success_route()

    run = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": e2e_project["project_id"],
            "platform_codes": ["qwen"],
            "collection_source": "official",
        },
    ).json()["data"]
    run_id = run["id"]
    assert run["status"] == "collecting"

    drain_run_collection_sync(session_factory, run_id)

    run_detail = client.get(f"/api/geo-monitoring/runs/{run_id}").json()["data"]
    assert run_detail["status"] == "completed"
    assert run_detail["succeeded_tasks"] == 2

    answers = client.get(f"/api/geo-monitoring/runs/{run_id}/answers").json()["data"]
    assert answers["total"] == 2
    answer_detail = client.get(
        f"/api/geo-monitoring/answers/{answers['items'][0]['id']}"
    ).json()["data"]
    assert "目标品牌" in answer_detail["normalized_text"]
    assert answer_detail["citations"] == []
    assert any(item["is_mentioned"] for item in answer_detail["brand_results"])

    analyze_run(run_id)
    analysis = client.get(f"/api/geo-monitoring/runs/{run_id}/analysis").json()["data"]
    assert analysis["analysis_status"] in {"completed", "partial_success"}
    assert len(analysis["platforms"]) == 1
    assert analysis["platforms"][0]["valid_answer_count"] == 2

    executions = client.get(
        f"/api/geo-monitoring/runs/{run_id}/agent-executions"
    ).json()["data"]
    assert executions["total"] >= 1

    trends = client.get(
        f"/api/geo-monitoring/projects/{e2e_project['project_id']}/trends",
        params={"metric_code": "brand_visibility", "platform_code": "qwen"},
    ).json()["data"]
    assert isinstance(trends.get("items", trends), list)

    report_resp = client.post(
        f"/api/geo-monitoring/runs/{run_id}/reports",
        json={"formats": ["md", "html"]},
    ).json()
    assert report_resp["code"] == 0
    report_id = report_resp["data"]["reports"][0]["id"]
    meta = client.get(f"/api/geo-monitoring/reports/{report_id}").json()["data"]
    download = client.get(f"/api/geo-monitoring/reports/{report_id}/download")
    assert download.status_code == 200
    expected_checksum = hashlib.sha256(download.content).hexdigest()
    assert meta["checksum"] == expected_checksum

    with session_factory() as db:
        answer = db.execute(select(Answer).limit(1)).scalar_one()
        raw = answer.raw_response_json
        if raw is not None:
            assert MOCK_QWEN_KEY not in json.dumps(raw)


@freeze_time("2026-06-17 10:00:00")
def test_schedule_fire_is_idempotent_without_duplicate_runs(
    client, session_factory, e2e_project, monkeypatch
):
    configure_molizhishu_collection_runtime(session_factory, monkeypatch)
    seed_molizhishu_platform(session_factory)
    with session_factory() as db:
        schedule = schedule_service.create_schedule(
            db,
            e2e_project["project_id"],
            ScheduleCreate(
                name="e2e-hourly",
                cron_expr="0 * * * *",
                timezone="UTC",
                enabled=True,
            ),
        )
        schedule_id = schedule.id

    planned = datetime(2026, 6, 17, 10, 0, tzinfo=timezone.utc)
    first = scheduler_jobs.execute_schedule_fire(
        schedule_id,
        session_factory=session_factory,
        planned_fire_time=planned,
    )
    second = scheduler_jobs.execute_schedule_fire(
        schedule_id,
        session_factory=session_factory,
        planned_fire_time=planned,
    )
    assert first.id == second.id

    with session_factory() as db:
        count = db.scalar(
            select(func.count())
            .select_from(MonitorRun)
            .where(MonitorRun.triggered_by == schedule_id)
        )
    assert count == 1


@respx.mock
def test_cancel_retry_and_analysis_rerun(
    client,
    session_factory,
    monkeypatch,
    e2e_project,
    fake_llm,
):
    project_id = e2e_project["project_id"]
    configure_mock_collection_runtime(session_factory, monkeypatch)
    register_qwen_success_route()

    run = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "platform_codes": ["qwen"],
            "collection_source": "official",
        },
    ).json()["data"]
    run_id = run["id"]

    with session_factory() as db:
        tasks = list(
            db.execute(
                select(QueryTask)
                .where(QueryTask.run_id == run_id)
                .order_by(QueryTask.id)
            )
            .scalars()
            .all()
        )
        assert len(tasks) == 2
        tasks[0].status = "success"
        tasks[0].completed_at = datetime.now(timezone.utc)
        tasks[0].finished_at = tasks[0].completed_at
        if tasks[1].status == "pending":
            tasks[1].status = "queued"
        db.commit()

    cancelled = client.post(f"/api/geo-monitoring/runs/{run_id}/cancel").json()["data"]
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_tasks"] >= 1

    run2 = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "platform_codes": ["qwen"],
            "collection_source": "official",
        },
    ).json()["data"]
    run2_id = run2["id"]

    with session_factory() as db:
        tasks = list(
            db.execute(select(QueryTask).where(QueryTask.run_id == run2_id).order_by(QueryTask.id))
            .scalars()
            .all()
        )
        for task in tasks:
            task.status = "failed"
            task.error_code = "server_error"
            task.error_message = "mock failure"
            task.completed_at = datetime.now(timezone.utc)
            task.finished_at = task.completed_at
        db.commit()

    retried = client.post(f"/api/geo-monitoring/runs/{run2_id}/retry-failed").json()["data"]
    assert retried["retried_count"] == len(tasks)
    drain_run_collection_sync(session_factory, run2_id)

    analyze_run(run2_id)
    client.get(f"/api/geo-monitoring/runs/{run2_id}/analysis").json()["data"]
    rerun = client.post(f"/api/geo-monitoring/runs/{run2_id}/analyze").json()["data"]
    second = client.get(f"/api/geo-monitoring/runs/{run2_id}/analysis").json()["data"]
    assert rerun["queued"] is True
    assert rerun["analysis_status"] == "pending"
    assert rerun["run_analysis_status"] in {"completed", "partial_success", "skipped"}
    assert second["platforms"]
