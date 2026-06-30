"""模力指数采集集成测试（Task M13）。

使用 respx mock 模力指数 HTTP，经真实 MolizhishuAdapter 与 CollectionService 验证
1 prompt × 1 platform、pending 续跑、轮询上限、部分失败与取消等行为。
"""

from __future__ import annotations

import json
from typing import Any

import dramatiq
import httpx
import pytest
import respx
from dramatiq.brokers.stub import StubBroker
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.geo_monitoring.adapters.key_pool import ApiKeyCredential, CredentialKeyPool
from app.geo_monitoring.adapters.molizhishu import MolizhishuAdapter
from app.geo_monitoring.adapters.registry import AdapterRegistry
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    AnswerBrandResult,
    AnswerCitation,
    Brand,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.repositories import answers as answer_repo
from app.geo_monitoring.services import collection as collection_service
from app.worker.actors.collection import collect_query_task

BASE_URL = "https://molizhishu.test"
PLATFORM_CODE = "molizhishu_qianwen_web"
MOLIZHISHU_PLATFORM = "qianwen"


def _dispatch_task(task_id: int) -> None:
    pending: list[int] = []

    def defer_send(next_task_id: int) -> None:
        pending.append(next_task_id)

    def defer_send_with_options(*, args=(), kwargs=None, delay=None, **options):
        pending.append(args[0])

    original_send = collect_query_task.send
    original_send_with_options = collect_query_task.send_with_options
    collect_query_task.send = defer_send
    collect_query_task.send_with_options = defer_send_with_options
    try:
        collect_query_task.fn(task_id)
        while pending:
            collect_query_task.fn(pending.pop(0))
    finally:
        collect_query_task.send = original_send
        collect_query_task.send_with_options = original_send_with_options


def _make_runtime(session_factory, tmp_path, *, max_polls: int = 360) -> collection_service.CollectionRuntime:
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="stub",
        NACOS_ENABLED=False,
        REPORT_STORAGE_DIR=str(tmp_path),
        MOLIZHISHU_ENABLED=True,
        MOLIZHISHU_API_TOKEN="molizhishu-token",
        MOLIZHISHU_BASE_URL=BASE_URL,
        COLLECTION_MOLIZHISHU_MAX_POLLS=max_polls,
        COLLECTION_MOLIZHISHU_POLL_DELAY_SECONDS=1,
        COLLECTION_RAW_RESPONSE_ENABLED=True,
    )
    registry = AdapterRegistry()
    registry.register(
        MolizhishuAdapter(
            code=PLATFORM_CODE,
            molizhishu_platform=MOLIZHISHU_PLATFORM,
            default_mode="search",
            base_url=BASE_URL,
            timeout_seconds=0.5,
        )
    )
    key_pool = CredentialKeyPool(None)
    key_pool.register_platform_credentials(
        PLATFORM_CODE,
        [ApiKeyCredential(platform_code=PLATFORM_CODE, api_key="molizhishu-token")],
    )
    runtime = collection_service.CollectionRuntime(
        session_factory=session_factory,
        settings=settings,
        adapter_registry=registry,
        key_pool=key_pool,
        stale_running_seconds=1,
    )
    collection_service.configure_runtime(runtime)
    return runtime


@pytest.fixture
def stub_broker():
    broker = StubBroker()
    broker.emit_after("process_boot")
    dramatiq.set_broker(broker)
    return broker


@pytest.fixture
def molizhishu_collection_env(session_factory, stub_broker, tmp_path):
    runtime = _make_runtime(session_factory, tmp_path)
    try:
        yield runtime
    finally:
        collection_service.reset_runtime()


def _seed_molizhishu_run(
    db: Session,
    *,
    prompt_count: int = 1,
    run_status: str = "collecting",
) -> dict:
    project = MonitorProject(project_name="模力指数采集", status="active")
    db.add(project)
    db.flush()
    target = Brand(
        project_id=project.id,
        brand_name="目标品牌",
        brand_type="target",
        status="active",
    )
    competitor = Brand(
        project_id=project.id,
        brand_name="竞品B",
        brand_type="competitor",
        status="active",
    )
    db.add_all([target, competitor])
    db.flush()
    prompt_set = PromptSet(
        project_id=project.id,
        set_name="集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()
    prompts: list[Prompt] = []
    for index in range(prompt_count):
        prompt = Prompt(
            prompt_set_id=prompt_set.id,
            prompt_code=f"p{index + 1}",
            prompt_text=f"问题 {index + 1}：哪个品牌更好？",
        )
        db.add(prompt)
        prompts.append(prompt)
    db.flush()
    db.add(
        AIPlatform(
            platform_code=PLATFORM_CODE,
            platform_name="通义千问",
            model_name="molizhishu:qianwen",
            adapter_type="molizhishu",
            enabled=True,
            extra_config={"molizhishu_platform": MOLIZHISHU_PLATFORM},
        )
    )
    run = MonitorRun(
        run_no=f"RUN-MZ-{project.id}",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version=prompt_set.version_no,
        collection_source="molizhishu",
        provider_mode_by_platform={PLATFORM_CODE: "search"},
        provider_screenshot=0,
        platform_codes=[PLATFORM_CODE],
        status=run_status,
        collection_status="running" if run_status == "collecting" else "pending",
        total_tasks=prompt_count,
        expected_query_count=prompt_count,
    )
    db.add(run)
    db.flush()
    task_ids: list[int] = []
    for prompt in prompts:
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code=PLATFORM_CODE,
            idempotency_key=f"mz-{run.id}-{prompt.id}",
            status="queued",
            max_attempts=3,
        )
        db.add(task)
        db.flush()
        task_ids.append(task.id)
    db.commit()
    return {
        "project_id": project.id,
        "run_id": run.id,
        "task_ids": task_ids,
        "target_brand_id": target.id,
        "competitor_brand_id": competitor.id,
    }


def _submit_payload(*, task_id: str, subtask_id: str) -> dict[str, Any]:
    return {
        "success": True,
        "code": 200,
        "message": "ok",
        "data": {
            "taskId": task_id,
            "subTaskList": [
                {
                    "subTaskId": subtask_id,
                    "platform": MOLIZHISHU_PLATFORM,
                    "status": "pending",
                }
            ],
        },
    }


def _completed_payload(*, answer: str = "推荐目标品牌和竞品B。") -> dict[str, Any]:
    return {
        "success": True,
        "code": 200,
        "message": "ok",
        "data": {
            "status": "completed",
            "answerContent": answer,
            "citationList": [
                {
                    "url": "https://example.com/a",
                    "title": "引用标题",
                    "snippet": "摘要",
                    "siteName": "Example",
                }
            ],
        },
    }


def _mock_submit_and_result(
    *,
    task_id: str = "task-mlz-1",
    subtask_id: str = "sub-1",
    first_status: str = "processing",
    terminal_payload: dict[str, Any] | None = None,
) -> respx.Route:
    submit_route = respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload(task_id=task_id, subtask_id=subtask_id))
    )
    result_route = respx.get(f"{BASE_URL}/task/result/{task_id}/{subtask_id}")
    call_count = {"n": 0}

    def result_side_effect(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1 and first_status != "completed":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "code": 200,
                    "message": "ok",
                    "data": {"status": first_status},
                },
            )
        payload = terminal_payload or _completed_payload()
        return httpx.Response(200, json=payload)

    result_route.mock(side_effect=result_side_effect)
    return submit_route


@respx.mock
def test_one_prompt_one_platform_collects_answer_with_citations(
    molizhishu_collection_env, session_factory
):
    _mock_submit_and_result()
    with session_factory() as db:
        seeded = _seed_molizhishu_run(db)

    _dispatch_task(seeded["task_ids"][0])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_ids"][0])
        run = db.get(MonitorRun, seeded["run_id"])
        answer = answer_repo.get_by_task_id(db, task.id)
        citations = db.query(AnswerCitation).filter(AnswerCitation.answer_id == answer.id).all()
        brand_results = db.query(AnswerBrandResult).filter(
            AnswerBrandResult.answer_id == answer.id
        ).all()

        assert task.status == "success"
        assert task.provider_task_id == "task-mlz-1"
        assert task.provider_subtask_id == "sub-1"
        assert answer.raw_text == "推荐目标品牌和竞品B。"
        assert len(citations) == 1
        assert citations[0].title == "引用标题"
        assert len(brand_results) == 2
        assert run.status == "completed"
        assert run.succeeded_tasks == 1


@respx.mock
def test_pending_poll_resume_reuses_submitted_task(molizhishu_collection_env, session_factory):
    submit_route = _mock_submit_and_result(first_status="processing")
    with session_factory() as db:
        seeded = _seed_molizhishu_run(db)

    _dispatch_task(seeded["task_ids"][0])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_ids"][0])
        assert task.status == "success"
        assert task.request_json["molizhishu_task_id"] == "task-mlz-1"
        assert task.request_json["molizhishu_subtask_id"] == "sub-1"
        assert task.request_json["molizhishu_poll_count"] == 1
        assert task.attempt_count == 1

    assert submit_route.call_count == 1


@respx.mock
def test_max_poll_limit_marks_task_failed(session_factory, stub_broker, tmp_path):
    _make_runtime(session_factory, tmp_path, max_polls=1)
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            200,
            json=_submit_payload(task_id="task-mlz-1", subtask_id="sub-1"),
        )
    )
    respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {"status": "processing"},
            },
        )
    )
    with session_factory() as db:
        seeded = _seed_molizhishu_run(db)

    _dispatch_task(seeded["task_ids"][0])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_ids"][0])
        assert task.status == "failed"
        assert task.error_code == "pending"
        assert task.request_json["molizhishu_poll_count"] == 1
        assert answer_repo.get_by_task_id(db, task.id) is None


@respx.mock
def test_partial_success_when_one_subtask_fails(molizhishu_collection_env, session_factory):
    submit_state = {"n": 0}

    def submit_side_effect(request: httpx.Request) -> httpx.Response:
        submit_state["n"] += 1
        suffix = submit_state["n"]
        return httpx.Response(
            200,
            json=_submit_payload(task_id=f"task-{suffix}", subtask_id=f"sub-{suffix}"),
        )

    respx.post(f"{BASE_URL}/task/batch/shared").mock(side_effect=submit_side_effect)

    def result_side_effect(request: httpx.Request) -> httpx.Response:
        subtask_id = request.url.path.rsplit("/", 1)[-1]
        if subtask_id == "sub-1":
            return httpx.Response(200, json=_completed_payload(answer="任务一成功。"))
        return httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {
                    "status": "failed",
                    "errorMessage": "provider failed",
                },
            },
        )

    respx.route(url__regex=rf"{BASE_URL}/task/result/task-\d+/sub-\d+").mock(
        side_effect=result_side_effect
    )

    with session_factory() as db:
        seeded = _seed_molizhishu_run(db, prompt_count=2)

    for task_id in seeded["task_ids"]:
        _dispatch_task(task_id)

    with session_factory() as db:
        tasks = [db.get(QueryTask, task_id) for task_id in seeded["task_ids"]]
        run = db.get(MonitorRun, seeded["run_id"])
        statuses = {task.status for task in tasks}
        assert statuses == {"success", "failed"}
        assert run.status == "partial_success"
        assert run.collection_status == "partial_success"
        assert run.succeeded_tasks == 1
        assert run.failed_tasks == 1


@respx.mock
def test_cancelled_task_does_not_call_provider(molizhishu_collection_env, session_factory):
    submit_route = respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            200,
            json=_submit_payload(task_id="task-mlz-1", subtask_id="sub-1"),
        )
    )
    with session_factory() as db:
        seeded = _seed_molizhishu_run(db)
        task = db.get(QueryTask, seeded["task_ids"][0])
        task.status = "cancelled"
        db.commit()

    _dispatch_task(seeded["task_ids"][0])

    assert submit_route.call_count == 0
    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_ids"][0])
        assert task.status == "cancelled"
        assert answer_repo.get_by_task_id(db, task.id) is None


@respx.mock
def test_completed_answer_persists_provider_raw_response(
    molizhishu_collection_env, session_factory
):
    _mock_submit_and_result(first_status="completed")
    with session_factory() as db:
        seeded = _seed_molizhishu_run(db)

    _dispatch_task(seeded["task_ids"][0])

    with session_factory() as db:
        answer = answer_repo.get_by_task_id(db, seeded["task_ids"][0])
        assert answer is not None
        raw = answer.raw_response_json
        assert raw is not None
        assert raw["submit"]["data"]["taskId"] == "task-mlz-1"
        assert raw["result"]["data"]["status"] == "completed"
        assert "molizhishu-token" not in json.dumps(raw)


def test_smoke_script_exits_without_token_from_repo_root_command():
    """按 README 文档命令从仓库根目录执行，无 token 时应提示并退出。"""
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    env = {
        **os.environ,
        "MOLIZHISHU_API_TOKEN": "",
        "PYTHONIOENCODING": "utf-8",
    }
    result = subprocess.run(
        [
            sys.executable,
            "backend/scripts/molizhishu_smoke_test.py",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode != 0
    assert "MOLIZHISHU_API_TOKEN" in (result.stdout + result.stderr)
