"""模力指数 provider callback 接口与幂等测试。"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.geo_monitoring.adapters.base import (
    PlatformAnswer,
    PlatformCredential,
    PlatformQuery,
)
from app.geo_monitoring.adapters.molizhishu import (
    MolizhishuPendingError,
    platform_answer_from_molizhishu_result,
)
from app.geo_monitoring.adapters.key_pool import ApiKeyCredential, CredentialKeyPool
from app.geo_monitoring.adapters.registry import AdapterRegistry
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    AnswerCitation,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.repositories import answers as answer_repo
from app.geo_monitoring.services import collection as collection_service
from app.worker.actors.collection import collect_query_task

CALLBACK_PATH = "/api/geo-monitoring/provider-callbacks/molizhishu"
CALLBACK_TOKEN = "test-callback-token"


@pytest.fixture(autouse=True)
def isolate_callback_test_env(monkeypatch):
    monkeypatch.setenv("YUANBAO_ENABLED", "false")
    monkeypatch.setenv("YUANBAO_CREDENTIALS_JSON", "[]")
    monkeypatch.setenv("MOLIZHISHU_CALLBACK_TOKEN", CALLBACK_TOKEN)
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def client(session_factory):
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.core.database import get_db
    from app.geo_monitoring.services import collection as collection_service
    from app.main import app

    test_settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="stub",
        NACOS_ENABLED=False,
        REPORT_STORAGE_DIR="./data/reports",
        YUANBAO_ENABLED=False,
        YUANBAO_CREDENTIALS_JSON="[]",
        MOLIZHISHU_CALLBACK_TOKEN=CALLBACK_TOKEN,
    )
    settings.MOLIZHISHU_CALLBACK_TOKEN = CALLBACK_TOKEN
    collection_service.configure_runtime(
        collection_service.build_default_runtime(
            session_factory=session_factory,
            runtime_settings=test_settings,
        )
    )

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        collection_service.reset_runtime()


def _completed_callback_payload(
    *,
    task_id: str = "task-mz-1",
    subtask_id: str = "subtask-mz-1",
) -> dict:
    return {
        "taskId": task_id,
        "subTaskId": subtask_id,
        "status": "completed",
        "answerContent": "推荐目标品牌。",
        "citationList": [
            {
                "url": "https://example.com/a",
                "title": "引用标题",
                "snippet": "摘要",
                "siteName": "Example",
            }
        ],
    }


def _seed_molizhishu_task(
    db: Session,
    *,
    task_id: str = "task-mz-1",
    subtask_id: str = "subtask-mz-1",
    status: str = "queued",
) -> dict:
    project = MonitorProject(project_name="回调测试", status="active")
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
    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="p1",
        prompt_text="哪个品牌更好？",
    )
    db.add(prompt)
    db.flush()
    db.add(
        AIPlatform(
            platform_code="molizhishu_deepseek_web",
            platform_name="DeepSeek 网页端",
            model_name="molizhishu:deepseek",
            adapter_type="molizhishu",
            enabled=True,
            extra_config={"molizhishu_platform": "deepseek"},
        )
    )
    run = MonitorRun(
        run_no=f"RUN-CB-{project.id}",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version=prompt_set.version_no,
        collection_source="molizhishu",
        platform_codes=["molizhishu_deepseek_web"],
        status="collecting",
        total_tasks=1,
        expected_query_count=1,
        provider_mode_by_platform={"molizhishu_deepseek_web": "reasoning_search"},
    )
    db.add(run)
    db.flush()
    task = QueryTask(
        run_id=run.id,
        prompt_id=prompt.id,
        platform_code="molizhishu_deepseek_web",
        idempotency_key=f"callback-{run.id}-{prompt.id}",
        status=status,
        request_json={
            "molizhishu_task_id": task_id,
            "molizhishu_subtask_id": subtask_id,
            "molizhishu_platform": "deepseek",
            "molizhishu_mode": "reasoning_search",
            "molizhishu_poll_count": 1,
        },
        provider_task_id=task_id,
        provider_subtask_id=subtask_id,
    )
    db.add(task)
    db.commit()
    return {
        "project_id": project.id,
        "run_id": run.id,
        "task_id": task.id,
        "provider_task_id": task_id,
        "provider_subtask_id": subtask_id,
    }


def test_find_query_task_by_molizhishu_ids_legacy_request_json_fallback(session_factory):
    with session_factory() as db:
        seeded = _seed_molizhishu_task(db, status="queued")
        task = db.get(QueryTask, seeded["task_id"])
        task.provider_task_id = None
        task.provider_subtask_id = None
        db.commit()

        matched = collection_service.find_query_task_by_molizhishu_ids(
            db,
            provider_task_id=seeded["provider_task_id"],
            provider_subtask_id=seeded["provider_subtask_id"],
        )

    assert matched is not None
    assert matched.id == seeded["task_id"]


def test_find_query_task_by_molizhishu_ids_supports_custom_db_platform(session_factory):
    with session_factory() as db:
        project = MonitorProject(project_name="自定义回调", status="active")
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
        prompt = Prompt(
            prompt_set_id=prompt_set.id,
            prompt_code="p1",
            prompt_text="问题",
        )
        db.add(prompt)
        db.flush()
        db.add(
            AIPlatform(
                platform_code="molizhishu_custom_web",
                platform_name="自定义模力平台",
                adapter_type="molizhishu",
                model_name="molizhishu:custom_provider",
                enabled=True,
                extra_config={"molizhishu_platform": "custom_provider"},
            )
        )
        run = MonitorRun(
            run_no="RUN-CB-CUSTOM",
            project_id=project.id,
            prompt_set_id=prompt_set.id,
            prompt_set_version=prompt_set.version_no,
            collection_source="molizhishu",
            platform_codes=["molizhishu_custom_web"],
            status="collecting",
            total_tasks=1,
            expected_query_count=1,
        )
        db.add(run)
        db.flush()
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code="molizhishu_custom_web",
            idempotency_key="callback-custom",
            status="queued",
            request_json={
                "molizhishu_task_id": "task-custom-1",
                "molizhishu_subtask_id": "subtask-custom-1",
            },
            provider_task_id=None,
            provider_subtask_id=None,
        )
        db.add(task)
        db.commit()
        task_id = task.id

        matched = collection_service.find_query_task_by_molizhishu_ids(
            db,
            provider_task_id="task-custom-1",
            provider_subtask_id="subtask-custom-1",
        )

    assert matched is not None
    assert matched.id == task_id


class MockMolizhishuAdapter:
    code = "molizhishu_deepseek_web"

    def __init__(self) -> None:
        self.calls: list[tuple[PlatformQuery, PlatformCredential]] = []

    async def query(
        self,
        request: PlatformQuery,
        *,
        credential: PlatformCredential,
    ) -> PlatformAnswer:
        self.calls.append((request, credential))
        if "molizhishu_subtask_id" not in request.metadata:
            raise MolizhishuPendingError(
                pending_metadata={
                    "molizhishu_task_id": "task-mz-1",
                    "molizhishu_subtask_id": "subtask-mz-1",
                    "molizhishu_platform": "deepseek",
                    "molizhishu_mode": "reasoning_search",
                    "molizhishu_status": "processing",
                }
            )
        return PlatformAnswer(
            text="轮询写入的答案。",
            citations=[],
            model="molizhishu:deepseek",
            usage={},
            latency_ms=90,
            provider_request_id=request.metadata["molizhishu_subtask_id"],
            raw_response={"molizhishu": True},
        )


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


def _configure_callback_runtime(session_factory, tmp_path):
    from app.core.config import Settings

    runtime_settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="stub",
        NACOS_ENABLED=False,
        REPORT_STORAGE_DIR=str(tmp_path),
        MOLIZHISHU_CALLBACK_TOKEN=CALLBACK_TOKEN,
    )
    adapter = MockMolizhishuAdapter()
    registry = AdapterRegistry()
    registry.register(adapter)
    key_pool = CredentialKeyPool(None)
    key_pool.register_platform_credentials(
        "molizhishu_deepseek_web",
        [
            ApiKeyCredential(
                platform_code="molizhishu_deepseek_web",
                api_key="molizhishu-token",
            )
        ],
    )
    runtime = collection_service.CollectionRuntime(
        session_factory=session_factory,
        settings=runtime_settings,
        adapter_registry=registry,
        key_pool=key_pool,
        stale_running_seconds=1,
    )
    collection_service.configure_runtime(runtime)
    settings.MOLIZHISHU_CALLBACK_TOKEN = CALLBACK_TOKEN
    return adapter


def test_invalid_callback_token_rejected(client, session_factory, tmp_path):
    _configure_callback_runtime(session_factory, tmp_path)
    with session_factory() as db:
        seeded = _seed_molizhishu_task(db)

    response = client.post(
        CALLBACK_PATH,
        json=_completed_callback_payload(),
        headers={"X-Callback-Token": "wrong-token"},
    )
    assert response.status_code == 401

    with session_factory() as db:
        assert answer_repo.get_by_task_id(db, seeded["task_id"]) is None


def test_completed_callback_writes_answer_and_citations(
    client, session_factory, tmp_path
):
    _configure_callback_runtime(session_factory, tmp_path)
    with session_factory() as db:
        seeded = _seed_molizhishu_task(db)

    response = client.post(
        CALLBACK_PATH,
        json=_completed_callback_payload(),
        headers={"X-Callback-Token": CALLBACK_TOKEN},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["outcome"] == "processed"
    assert body["data"]["task_id"] == seeded["task_id"]

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "success"
        answer = answer_repo.get_by_task_id(db, task.id)
        assert answer is not None
        assert answer.raw_text == "推荐目标品牌。"
        citations = (
            db.query(AnswerCitation).filter(AnswerCitation.answer_id == answer.id).all()
        )
        assert len(citations) == 1
        assert citations[0].title == "引用标题"


def test_duplicate_callback_does_not_duplicate_answer(
    client, session_factory, tmp_path
):
    _configure_callback_runtime(session_factory, tmp_path)
    with session_factory() as db:
        seeded = _seed_molizhishu_task(db)

    headers = {"X-Callback-Token": CALLBACK_TOKEN}
    payload = _completed_callback_payload()
    first = client.post(CALLBACK_PATH, json=payload, headers=headers)
    second = client.post(CALLBACK_PATH, json=payload, headers=headers)
    assert first.json()["data"]["outcome"] == "processed"
    assert second.json()["data"]["outcome"] == "duplicate"

    with session_factory() as db:
        answer = answer_repo.get_by_task_id(db, seeded["task_id"])
        citations = (
            db.query(AnswerCitation).filter(AnswerCitation.answer_id == answer.id).all()
        )
        assert len(citations) == 1


def test_callback_before_poll_converges(client, session_factory, tmp_path):
    adapter = _configure_callback_runtime(session_factory, tmp_path)
    with session_factory() as db:
        seeded = _seed_molizhishu_task(db, status="queued")

    callback = client.post(
        CALLBACK_PATH,
        json=_completed_callback_payload(),
        headers={"X-Callback-Token": CALLBACK_TOKEN},
    )
    assert callback.json()["data"]["outcome"] == "processed"

    _dispatch_task(seeded["task_id"])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        answer = answer_repo.get_by_task_id(db, task.id)
        assert task.status == "success"
        assert answer.raw_text == "推荐目标品牌。"
        citations = (
            db.query(AnswerCitation).filter(AnswerCitation.answer_id == answer.id).all()
        )
        assert len(citations) == 1

    assert len(adapter.calls) == 0


def test_poll_before_callback_converges(client, session_factory, tmp_path):
    adapter = _configure_callback_runtime(session_factory, tmp_path)
    with session_factory() as db:
        seeded = _seed_molizhishu_task(db, status="queued")

    _dispatch_task(seeded["task_id"])

    callback = client.post(
        CALLBACK_PATH,
        json=_completed_callback_payload(),
        headers={"X-Callback-Token": CALLBACK_TOKEN},
    )
    assert callback.json()["data"]["outcome"] == "duplicate"

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        answer = answer_repo.get_by_task_id(db, task.id)
        assert task.status == "success"
        assert answer.raw_text == "轮询写入的答案。"
        citations = (
            db.query(AnswerCitation).filter(AnswerCitation.answer_id == answer.id).all()
        )
        assert len(citations) == 0

    assert len(adapter.calls) == 1


def test_callback_accepts_query_token(client, session_factory, tmp_path):
    _configure_callback_runtime(session_factory, tmp_path)
    with session_factory() as db:
        seeded = _seed_molizhishu_task(db)

    response = client.post(
        f"{CALLBACK_PATH}?token={CALLBACK_TOKEN}",
        json=_completed_callback_payload(),
    )
    assert response.status_code == 200
    assert response.json()["data"]["task_id"] == seeded["task_id"]


def test_callback_registered_on_v1_prefix(client, session_factory, tmp_path):
    _configure_callback_runtime(session_factory, tmp_path)
    with session_factory() as db:
        _seed_molizhishu_task(db)

    response = client.post(
        "/api/v1/geo-monitoring/provider-callbacks/molizhishu",
        json=_completed_callback_payload(),
        headers={"X-Callback-Token": CALLBACK_TOKEN},
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_persist_platform_answer_recovers_unique_violation(
    session_factory, tmp_path, monkeypatch
):
    _configure_callback_runtime(session_factory, tmp_path)
    with session_factory() as db:
        seeded = _seed_molizhishu_task(db, status="running")
        runtime = collection_service.get_runtime()
        task = db.get(QueryTask, seeded["task_id"])
        snapshot = collection_service._build_snapshot_for_task(db, runtime, task)
        assert snapshot is not None

    platform_answer = platform_answer_from_molizhishu_result(
        _completed_callback_payload(),
        model="molizhishu:deepseek",
        subtask_id=seeded["provider_subtask_id"],
    )
    real_write = collection_service._write_platform_answer_to_session
    write_calls = {"count": 0}

    def write_simulate_lost_race(db, *args, **kwargs):
        write_calls["count"] += 1
        if write_calls["count"] == 1:
            with session_factory() as other:
                other.add(
                    Answer(
                        task_id=seeded["task_id"],
                        platform_code=snapshot.platform_code,
                        prompt_id=snapshot.prompt_id,
                        raw_text="并发写入",
                        normalized_text="并发写入",
                        model_name=platform_answer.model,
                    )
                )
                other.commit()
            raise IntegrityError("INSERT", {}, Exception("uq_geo_answer_task"))
        return real_write(db, *args, **kwargs)

    monkeypatch.setattr(
        collection_service,
        "_write_platform_answer_to_session",
        write_simulate_lost_race,
    )

    result = collection_service._persist_platform_answer(
        runtime,
        snapshot,
        platform_answer,
        require_running=False,
    )
    assert result is False

    with session_factory() as db:
        answer = answer_repo.get_by_task_id(db, seeded["task_id"])
        citations = (
            db.query(AnswerCitation).filter(AnswerCitation.answer_id == answer.id).all()
        )
        assert answer is not None
        assert len(citations) == 0


def test_callback_integrity_error_returns_duplicate_not_server_error(
    session_factory, tmp_path, monkeypatch
):
    _configure_callback_runtime(session_factory, tmp_path)
    with session_factory() as db:
        seeded = _seed_molizhishu_task(db, status="queued")

    def write_simulate_lost_race(db, *args, **kwargs):
        with session_factory() as other:
            task = other.get(QueryTask, seeded["task_id"])
            other.add(
                Answer(
                    task_id=seeded["task_id"],
                    platform_code=task.platform_code,
                    prompt_id=task.prompt_id,
                    raw_text="轮询先写入",
                    normalized_text="轮询先写入",
                    model_name="molizhishu:deepseek",
                )
            )
            other.commit()
        raise IntegrityError("INSERT", {}, Exception("uq_geo_answer_task"))

    monkeypatch.setattr(
        collection_service,
        "_write_platform_answer_to_session",
        write_simulate_lost_race,
    )

    with session_factory() as db:
        result = collection_service.handle_molizhishu_callback(
            db,
            _completed_callback_payload(),
        )

    assert result.outcome == "duplicate"

    with session_factory() as db:
        answer = answer_repo.get_by_task_id(db, seeded["task_id"])
        citations = (
            db.query(AnswerCitation).filter(AnswerCitation.answer_id == answer.id).all()
        )
        assert answer is not None
        assert len(citations) == 0
