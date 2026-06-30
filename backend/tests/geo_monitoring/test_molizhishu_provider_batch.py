"""模力指数 ProviderBatch 正式版能力测试（Task M15）。"""

from __future__ import annotations

import asyncio
import json
from hashlib import sha256

import httpx
import pytest
import respx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.geo_monitoring.adapters.key_pool import ApiKeyCredential, CredentialKeyPool
from app.geo_monitoring.adapters.molizhishu import MolizhishuAdapter
from app.geo_monitoring.adapters.registry import AdapterRegistry
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    Brand,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    ProviderBatch,
    QueryTask,
)
from app.geo_monitoring.repositories import answers as answer_repo
from app.geo_monitoring.repositories import provider_batches as batch_repo
from app.geo_monitoring.services import collection as collection_service
from app.geo_monitoring.services.provider_batches import (
    ProviderBatchItem,
    build_submit_indexes,
    create_provider_batches_for_run,
    map_subtasks_to_items,
    plan_provider_batch_chunks,
    prepare_provider_batch_retry,
    provider_batch_enabled,
    refresh_batch_counters,
)
from app.geo_monitoring.services.platforms import MOLIZHISHU_PLATFORM_MAPPINGS
from app.geo_monitoring.services.runs import refresh_run_aggregation

BASE_URL = "https://molizhishu.test"
PLATFORM_CODES = [
    "molizhishu_qianwen_web",
    "molizhishu_doubao_web",
    "molizhishu_kimi_web",
    "molizhishu_yuanbao_web",
    "molizhishu_deepseek_web",
]


def _make_items(prompt_count: int, platform_count: int) -> list[ProviderBatchItem]:
    items: list[ProviderBatchItem] = []
    task_id = 1
    for prompt_index in range(prompt_count):
        for platform_index in range(platform_count):
            platform_code = PLATFORM_CODES[platform_index]
            mapping = MOLIZHISHU_PLATFORM_MAPPINGS[platform_code]
            items.append(
                ProviderBatchItem(
                    query_task_id=task_id,
                    prompt_id=prompt_index + 1,
                    platform_code=platform_code,
                    prompt_text=f"问题 {prompt_index + 1}",
                    molizhishu_platform=str(mapping["molizhishu_platform"]),
                    mode=str(mapping["default_mode"]),
                    screenshot=0,
                )
            )
            task_id += 1
    return items


def test_plan_50_prompts_5_platforms_splits_into_three_batches():
    items = _make_items(50, 5)
    chunks = plan_provider_batch_chunks(items, max_subtasks=100)
    assert [len(chunk) for chunk in chunks] == [100, 100, 50]
    assert sum(len(chunk) for chunk in chunks) == 250


def test_each_query_task_maps_to_batch_and_subtask_id():
    items = _make_items(2, 2)
    prompts, platforms, item_indexes = build_submit_indexes(items)
    subtask_list = []
    for prompt_idx, platform_idx in item_indexes:
        subtask_list.append(
            {
                "subTaskId": f"sub-{prompt_idx}-{platform_idx}",
                "prompt": prompts[prompt_idx],
                "platform": platforms[platform_idx]["platform"],
            }
        )
    mapping = map_subtasks_to_items(subtask_list, items, item_indexes)
    assert len(mapping) == 4
    assert set(mapping) == {item.query_task_id for item in items}
    assert all(value.startswith("sub-") for value in mapping.values())


def test_duplicate_prompt_text_keeps_one_prompt_entry_per_prompt_id():
    mapping_spec = MOLIZHISHU_PLATFORM_MAPPINGS[PLATFORM_CODES[0]]
    items = [
        ProviderBatchItem(
            query_task_id=1,
            prompt_id=10,
            platform_code=PLATFORM_CODES[0],
            prompt_text="相同问题",
            molizhishu_platform=str(mapping_spec["molizhishu_platform"]),
            mode="search",
            screenshot=0,
        ),
        ProviderBatchItem(
            query_task_id=2,
            prompt_id=11,
            platform_code=PLATFORM_CODES[0],
            prompt_text="相同问题",
            molizhishu_platform=str(mapping_spec["molizhishu_platform"]),
            mode="search",
            screenshot=0,
        ),
    ]
    prompts, _platforms, item_indexes = build_submit_indexes(items)
    assert len(prompts) == 2
    assert prompts == ["相同问题", "相同问题"]
    assert item_indexes == [(0, 0), (1, 0)]

    subtask_list = [
        {"subTaskId": "sub-a"},
        {"subTaskId": "sub-b"},
    ]
    mapping = map_subtasks_to_items(subtask_list, items, item_indexes)
    assert mapping == {1: "sub-a", 2: "sub-b"}


def _make_runtime(session_factory, tmp_path):
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
        MOLIZHISHU_PROVIDER_BATCH_ENABLED=True,
        COLLECTION_MOLIZHISHU_MAX_POLLS=5,
        COLLECTION_MOLIZHISHU_POLL_DELAY_SECONDS=1,
        COLLECTION_RAW_RESPONSE_ENABLED=True,
    )
    registry = AdapterRegistry()
    key_pool = CredentialKeyPool(None)
    for platform_code in PLATFORM_CODES:
        mapping = MOLIZHISHU_PLATFORM_MAPPINGS[platform_code]
        registry.register(
            MolizhishuAdapter(
                code=platform_code,
                molizhishu_platform=str(mapping["molizhishu_platform"]),
                default_mode=str(mapping["default_mode"]),
                base_url=BASE_URL,
                timeout_seconds=0.5,
            )
        )
        key_pool.register_platform_credentials(
            platform_code,
            [ApiKeyCredential(platform_code=platform_code, api_key="molizhishu-token")],
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
def provider_batch_env(session_factory, tmp_path):
    runtime = _make_runtime(session_factory, tmp_path)
    try:
        yield runtime
    finally:
        collection_service.reset_runtime()


def _seed_large_molizhishu_run(
    db: Session,
    *,
    prompt_count: int,
    platform_codes: list[str],
) -> MonitorRun:
    project = MonitorProject(project_name="ProviderBatch", status="active")
    db.add(project)
    db.flush()
    db.add(
        Brand(
            project_id=project.id,
            brand_name="目标品牌",
            brand_type="target",
            status="active",
        )
    )
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
            prompt_text=f"问题 {index + 1}",
        )
        db.add(prompt)
        prompts.append(prompt)
    db.flush()
    for platform_code in platform_codes:
        mapping = MOLIZHISHU_PLATFORM_MAPPINGS[platform_code]
        db.add(
            AIPlatform(
                platform_code=platform_code,
                platform_name=platform_code,
                model_name=f"molizhishu:{mapping['molizhishu_platform']}",
                adapter_type="molizhishu",
                enabled=True,
                extra_config={"molizhishu_platform": mapping["molizhishu_platform"]},
            )
        )
    task_count = prompt_count * len(platform_codes)
    run = MonitorRun(
        run_no="RUN-PB-1",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version=prompt_set.version_no,
        collection_source="molizhishu",
        provider_mode_by_platform={code: "search" for code in platform_codes},
        provider_screenshot=0,
        platform_codes=platform_codes,
        status="collecting",
        collection_status="running",
        total_tasks=task_count,
        expected_query_count=task_count,
    )
    db.add(run)
    db.flush()
    for prompt in prompts:
        for platform_code in platform_codes:
            key_source = f"{run.run_no}:{prompt.id}:{platform_code}"
            db.add(
                QueryTask(
                    run_id=run.id,
                    prompt_id=prompt.id,
                    platform_code=platform_code,
                    idempotency_key=sha256(key_source.encode("utf-8")).hexdigest(),
                    status="pending",
                    request_json={
                        "prompt_text": prompt.prompt_text,
                        "prompt_code": prompt.prompt_code,
                    },
                )
            )
    db.flush()
    create_provider_batches_for_run(db, run)
    db.commit()
    return run


def test_create_run_builds_three_provider_batches(db, provider_batch_env):
    run = _seed_large_molizhishu_run(db, prompt_count=50, platform_codes=PLATFORM_CODES)
    batches = batch_repo.list_by_run_id(db, run.id)
    assert [batch.total_items for batch in batches] == [100, 100, 50]
    assert all(batch.provider_name == "molizhishu" for batch in batches)
    tasks = db.query(QueryTask).filter(QueryTask.run_id == run.id).all()
    assert len(tasks) == 250
    assert all(task.provider_batch_id is not None for task in tasks)


def _build_subtask_list(items: list[ProviderBatchItem]) -> list[dict]:
    prompts, platforms, item_indexes = build_submit_indexes(items)
    subtasks: list[dict] = []
    for prompt_idx, platform_idx in item_indexes:
        subtasks.append(
            {
                "subTaskId": f"sub-{prompt_idx}-{platform_idx}",
                "prompt": prompts[prompt_idx],
                "platform": platforms[platform_idx]["platform"],
            }
        )
    return subtasks


@respx.mock
def test_partial_batch_failure_run_enters_partial_success(
    db,
    provider_batch_env,
):
    run = _seed_large_molizhishu_run(db, prompt_count=2, platform_codes=PLATFORM_CODES[:2])
    batches = batch_repo.list_by_run_id(db, run.id)
    assert len(batches) == 1
    batch = batches[0]
    tasks = batch_repo.list_tasks_for_batch(db, batch.id)
    from app.geo_monitoring.services.collection import _provider_batch_items_from_tasks

    items = _provider_batch_items_from_tasks(tasks, run)

    submit_route = respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {
                    "taskId": "task-batch-1",
                    "subTaskList": _build_subtask_list(items),
                },
            },
        )
    )

    def _result_handler(request: httpx.Request) -> httpx.Response:
        subtask_id = request.url.path.rsplit("/", 1)[-1]
        if subtask_id.endswith("0-0"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "code": 200,
                    "message": "ok",
                    "data": {
                        "status": "completed",
                        "answerContent": "成功答案",
                    },
                },
            )
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

    respx.get(url__regex=rf"{BASE_URL}/task/result/task-batch-1/.+").mock(
        side_effect=_result_handler
    )
    respx.get(f"{BASE_URL}/task/status/task-batch-1").mock(
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

    result = asyncio.run(collection_service.execute_provider_batch(batch.id))
    assert result.should_retry is False
    assert submit_route.called

    db.expire_all()
    tasks = batch_repo.list_tasks_for_batch(db, batch.id)
    success_count = sum(1 for task in tasks if task.status == "success")
    failed_count = sum(1 for task in tasks if task.status == "failed")
    assert success_count == 1
    assert failed_count == len(tasks) - 1

    refresh_batch_counters(db, batch)
    db.commit()
    assert batch.status == "partial_completed"

    refresh_run_aggregation(db, run)
    db.commit()
    assert run.status == "partial_success"
    assert batch.raw_status_json is not None
    assert batch.raw_status_json.get("last_provider_status") is not None
    assert batch.raw_result_json is not None
    assert batch.raw_result_json.get("subtasks")


@respx.mock
def test_malformed_subtask_list_marks_batch_failed(db, provider_batch_env):
    run = _seed_large_molizhishu_run(db, prompt_count=1, platform_codes=PLATFORM_CODES[:2])
    batch = batch_repo.list_by_run_id(db, run.id)[0]

    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {
                    "taskId": "task-batch-bad",
                    "subTaskList": [{"subTaskId": "only-one"}],
                },
            },
        )
    )

    result = asyncio.run(collection_service.execute_provider_batch(batch.id))
    assert result.should_retry is False

    db.expire_all()
    batch = db.get(ProviderBatch, batch.id)
    tasks = batch_repo.list_tasks_for_batch(db, batch.id)
    assert batch.status == "failed"
    assert batch.error_message
    assert all(task.status == "failed" for task in tasks)
    refresh_run_aggregation(db, run)
    db.commit()
    assert run.status == "failed"


@respx.mock
def test_provider_batch_poll_records_status_and_result_json(db, provider_batch_env):
    run = _seed_large_molizhishu_run(db, prompt_count=1, platform_codes=PLATFORM_CODES[:1])
    batch = batch_repo.list_by_run_id(db, run.id)[0]
    tasks = batch_repo.list_tasks_for_batch(db, batch.id)
    from app.geo_monitoring.services.collection import _provider_batch_items_from_tasks

    items = _provider_batch_items_from_tasks(tasks, run)

    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {
                    "taskId": "task-batch-poll",
                    "subTaskList": _build_subtask_list(items),
                },
            },
        )
    )
    respx.get(f"{BASE_URL}/task/status/task-batch-poll").mock(
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
    respx.get(url__regex=rf"{BASE_URL}/task/result/task-batch-poll/.+").mock(
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

    result = asyncio.run(collection_service.execute_provider_batch(batch.id))
    assert result.should_retry is True

    db.expire_all()
    batch = db.get(ProviderBatch, batch.id)
    assert batch.raw_status_json["poll_count"] == 1
    assert batch.raw_status_json["last_provider_status"]["data"]["status"] == "processing"
    assert batch.raw_result_json["subtasks"]


def test_collect_provider_batch_actor_schedules_retry_on_pending(
    db, provider_batch_env,
):
    run = _seed_large_molizhishu_run(db, prompt_count=1, platform_codes=PLATFORM_CODES[:1])
    batch = batch_repo.list_by_run_id(db, run.id)[0]
    tasks = batch_repo.list_tasks_for_batch(db, batch.id)
    from app.geo_monitoring.services.collection import _provider_batch_items_from_tasks

    items = _provider_batch_items_from_tasks(tasks, run)

    with respx.mock:
        respx.post(f"{BASE_URL}/task/batch/shared").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "code": 200,
                    "message": "ok",
                    "data": {
                        "taskId": "task-batch-actor",
                        "subTaskList": _build_subtask_list(items),
                    },
                },
            )
        )
        respx.get(f"{BASE_URL}/task/status/task-batch-actor").mock(
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
        respx.get(url__regex=rf"{BASE_URL}/task/result/task-batch-actor/.+").mock(
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

        from app.worker.actors.collection import collect_provider_batch

        delayed: list[tuple] = []
        original = collect_provider_batch.send_with_options

        def capture_send_with_options(*, args=(), kwargs=None, delay=None, **options):
            delayed.append((args, delay))

        collect_provider_batch.send_with_options = capture_send_with_options
        try:
            collect_provider_batch.fn(batch.id)
        finally:
            collect_provider_batch.send_with_options = original

    assert delayed
    assert delayed[0][0][0] == batch.id
    assert delayed[0][1] == 1000


def test_batch_retry_does_not_rewrite_successful_query_task(db, provider_batch_env):
    run = _seed_large_molizhishu_run(db, prompt_count=1, platform_codes=PLATFORM_CODES[:2])
    batch = batch_repo.list_by_run_id(db, run.id)[0]
    tasks = batch_repo.list_tasks_for_batch(db, batch.id)
    success_task = tasks[0]
    failed_task = tasks[1]

    success_task.status = "success"
    success_task.provider_task_id = "old-task"
    success_task.provider_subtask_id = "old-sub-success"
    success_task.request_json = {
        **(success_task.request_json or {}),
        "molizhishu_task_id": "old-task",
        "molizhishu_subtask_id": "old-sub-success",
    }
    db_answer = Answer(
        task_id=success_task.id,
        platform_code=success_task.platform_code,
        prompt_id=success_task.prompt_id,
        raw_text="已有答案",
        normalized_text="已有答案",
    )
    answer_repo.add(db, db_answer)
    failed_task.status = "failed"
    batch.status = "failed"
    batch.provider_task_id = "old-task"
    db.commit()

    prepare_provider_batch_retry(db, batch)
    db.commit()
    db.expire_all()

    success_task = db.get(QueryTask, success_task.id)
    failed_task = db.get(QueryTask, failed_task.id)
    batch = db.get(ProviderBatch, batch.id)

    assert success_task.status == "success"
    assert success_task.provider_subtask_id == "old-sub-success"
    assert answer_repo.get_by_task_id(db, success_task.id) is not None
    assert failed_task.status == "queued"
    assert failed_task.provider_task_id is None
    assert batch.status == "pending"
    assert batch.provider_task_id is None


def test_provider_batch_disabled_for_official_runs():
    assert provider_batch_enabled("official") is False
    assert provider_batch_enabled("molizhishu") is True


def test_create_provider_batches_rejected_when_molizhishu_not_configured(db):
    from app.core.config import Settings
    from app.core.exceptions import BusinessException
    from app.geo_monitoring.adapters.registry import RUNTIME_ADAPTER_MISMATCH_CODE

    project = MonitorProject(project_name="PB guard", status="active")
    db.add(project)
    db.flush()
    prompt_set = PromptSet(
        project_id=project.id,
        set_name="集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()
    run = MonitorRun(
        run_no="RUN-PB-GUARD",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version=prompt_set.version_no,
        collection_source="molizhishu",
        platform_codes=["molizhishu_doubao_web"],
        status="pending",
        collection_status="pending",
        total_tasks=0,
        expected_query_count=0,
    )
    db.add(run)
    db.commit()

    with pytest.raises(BusinessException) as exc_info:
        create_provider_batches_for_run(
            db,
            run,
            runtime_settings=Settings(
                _env_file=None,
                APP_ENV="test",
                DATABASE_URL="sqlite+pysqlite:///:memory:",
                REDIS_URL="redis://test-redis.invalid:6379/15",
                DRAMATIQ_BROKER="stub",
                NACOS_ENABLED=False,
                REPORT_STORAGE_DIR="data/reports",
                MOLIZHISHU_ENABLED=False,
                MOLIZHISHU_API_TOKEN="",
            ),
        )

    assert exc_info.value.code == RUNTIME_ADAPTER_MISMATCH_CODE


def test_batch_callback_processes_subtask_list(db, provider_batch_env):
    run = _seed_large_molizhishu_run(db, prompt_count=1, platform_codes=PLATFORM_CODES[:1])
    batch = batch_repo.list_by_run_id(db, run.id)[0]
    task = batch_repo.list_tasks_for_batch(db, batch.id)[0]
    task.status = "running"
    task.provider_task_id = "task-cb-batch"
    task.provider_subtask_id = "sub-cb-1"
    task.request_json = {
        **(task.request_json or {}),
        "molizhishu_task_id": "task-cb-batch",
        "molizhishu_subtask_id": "sub-cb-1",
        "molizhishu_platform": "qianwen",
        "molizhishu_mode": "search",
    }
    batch.provider_task_id = "task-cb-batch"
    batch.status = "processing"
    db.commit()

    result = collection_service.handle_molizhishu_callback(
        db,
        {
            "taskId": "task-cb-batch",
            "subTaskList": [
                {
                    "subTaskId": "sub-cb-1",
                    "status": "completed",
                    "answerContent": "batch 回调答案",
                }
            ],
        },
    )

    assert result.outcome == "processed"
    db.expire_all()
    batch = db.get(ProviderBatch, batch.id)
    task = db.get(QueryTask, task.id)
    assert batch.raw_result_json is not None
    assert batch.raw_result_json.get("callback") is not None
    assert task.status == "success"
    assert answer_repo.get_by_task_id(db, task.id) is not None
