"""采集 Actor 与 collection service 测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import dramatiq
import pytest
from dramatiq.brokers.stub import StubBroker
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.geo_monitoring.adapters.base import PlatformAnswer, PlatformCredential, PlatformQuery
from app.geo_monitoring.adapters.aidso import AidsoPendingError
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory
from app.geo_monitoring.adapters.key_pool import ApiKeyCredential, CredentialKeyPool
from app.geo_monitoring.adapters.registry import AdapterRegistry
from app.geo_monitoring.models import (
    AIPlatform,
    AnswerBrandResult,
    AnswerCitation,
    Brand,
    BrandAlias,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.repositories import answers as answer_repo
from app.geo_monitoring.services import collection as collection_service
from app.worker.actors.collection import collect_query_task


def dispatch_task(task_id: int) -> None:
    pending: list[int] = []

    def defer_send(next_task_id: int) -> None:
        pending.append(next_task_id)

    original_send = collect_query_task.send
    collect_query_task.send = defer_send
    try:
        collect_query_task.fn(task_id)
        while pending:
            collect_query_task.fn(pending.pop(0))
    finally:
        collect_query_task.send = original_send


class MockAdapter:
    code = "qwen"

    def __init__(
        self,
        *,
        text: str = "推荐目标品牌和竞品B。",
        citations: list[dict] | None = None,
        fail_with: AdapterError | None = None,
        fail_times: int = 0,
    ) -> None:
        self.text = text
        self.citations = citations or [
            {
                "title": "引用",
                "url": "HTTPS://Example.com/path#frag",
                "source_type": "web",
            }
        ]
        self.fail_with = fail_with
        self.fail_times = fail_times
        self.calls: list[tuple[PlatformQuery, PlatformCredential]] = []

    async def query(
        self,
        request: PlatformQuery,
        *,
        credential: PlatformCredential,
    ) -> PlatformAnswer:
        self.calls.append((request, credential))
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.fail_with or AdapterError(
                "temporary server error",
                category=ErrorCategory.SERVER_ERROR,
            )
        if self.fail_with is not None:
            raise self.fail_with
        return PlatformAnswer(
            text=self.text,
            citations=self.citations,
            model="mock-qwen",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            latency_ms=120,
            provider_request_id="req-1",
            raw_response={"mock": True},
        )


class MockAidsoAdapter:
    code = "aidso_doubao_web"

    def __init__(self) -> None:
        self.calls: list[tuple[PlatformQuery, PlatformCredential]] = []

    async def query(
        self,
        request: PlatformQuery,
        *,
        credential: PlatformCredential,
    ) -> PlatformAnswer:
        self.calls.append((request, credential))
        if "aidso_req_id" not in request.metadata:
            raise AidsoPendingError(
                pending_metadata={
                    "aidso_req_id": "req-db-1",
                    "aidso_task_id": "task-aidso-1",
                    "aidso_platform_name": "DB",
                    "aidso_thinking_enabled": request.metadata.get(
                        "aidso_thinking_enabled"
                    ),
                }
            )
        return PlatformAnswer(
            text="推荐目标品牌。",
            citations=[],
            model="aidso:DB",
            usage={},
            latency_ms=80,
            provider_request_id=request.metadata["aidso_req_id"],
            raw_response={"aidso": True},
        )


def make_test_settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="stub",
        NACOS_ENABLED=False,
        REPORT_STORAGE_DIR=str(tmp_path),
        QWEN_ENABLED=True,
        QWEN_MODEL="qwen-test",
        QWEN_API_KEYS="test-key",
    )


@pytest.fixture
def stub_broker():
    broker = StubBroker()
    broker.emit_after("process_boot")
    dramatiq.set_broker(broker)
    return broker


@pytest.fixture
def collection_env(session_factory, stub_broker, tmp_path):
    settings = make_test_settings(tmp_path)
    adapter = MockAdapter()
    registry = AdapterRegistry()
    registry.register(adapter)
    key_pool = CredentialKeyPool(None)
    key_pool.register_platform_credentials(
        "qwen",
        [ApiKeyCredential(platform_code="qwen", api_key="test-key")],
    )
    runtime = collection_service.CollectionRuntime(
        session_factory=session_factory,
        settings=settings,
        adapter_registry=registry,
        key_pool=key_pool,
        stale_running_seconds=1,
    )
    collection_service.configure_runtime(runtime)
    try:
        yield {
            "runtime": runtime,
            "adapter": adapter,
            "settings": settings,
        }
    finally:
        collection_service.reset_runtime()


def _seed_collection_graph(db: Session) -> dict:
    project = MonitorProject(project_name="采集测试", status="active")
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
    db.add(
        BrandAlias(
            brand_id=target.id,
            alias_name="TB",
            match_mode="exact",
            enabled=True,
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
    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="p1",
        prompt_text="哪个品牌更好？",
    )
    db.add(prompt)
    db.flush()
    db.add(
        AIPlatform(
            platform_code="qwen",
            platform_name="通义千问",
            model_name="qwen-test",
            enabled=True,
        )
    )
    run = MonitorRun(
        run_no="RUN-COLLECT",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        platform_codes=["qwen"],
        total_tasks=1,
        expected_query_count=1,
    )
    db.add(run)
    db.flush()
    task = QueryTask(
        run_id=run.id,
        prompt_id=prompt.id,
        platform_code="qwen",
        idempotency_key="collect-task-1",
        status="pending",
        max_attempts=3,
    )
    db.add(task)
    db.commit()
    return {
        "project_id": project.id,
        "run_id": run.id,
        "task_id": task.id,
        "target_brand_id": target.id,
        "competitor_brand_id": competitor.id,
    }


def test_enqueue_happens_after_commit(collection_env, session_factory, monkeypatch):
    with session_factory() as db:
        seeded = _seed_collection_graph(db)

    observed: list[tuple[int, str]] = []
    original_send = collect_query_task.send

    def spy_send(task_id: int):
        with session_factory() as db:
            task = db.get(QueryTask, task_id)
            observed.append((task_id, task.status))
        return original_send(task_id)

    monkeypatch.setattr(collect_query_task, "send", spy_send)

    enqueued = collection_service.enqueue_run_query_tasks(seeded["run_id"])
    assert enqueued == 1
    assert observed == [(seeded["task_id"], "queued")]


def test_enqueue_accepts_external_db_session(collection_env, session_factory, monkeypatch):
    sends: list[int] = []
    original_send = collect_query_task.send

    def spy_send(task_id: int):
        sends.append(task_id)
        return original_send(task_id)

    monkeypatch.setattr(collect_query_task, "send", spy_send)

    with session_factory() as db:
        seeded = _seed_collection_graph(db)
        count = collection_service.enqueue_run_query_tasks(seeded["run_id"], db=db)
        task = db.get(QueryTask, seeded["task_id"])

    assert count == 1
    assert task.status == "queued"
    assert sends == [seeded["task_id"]]


def test_success_aggregates_run_without_detail_api(collection_env, session_factory):
    with session_factory() as db:
        seeded = _seed_collection_graph(db)
        run = db.get(MonitorRun, seeded["run_id"])
        run.status = "collecting"
        run.collection_status = "running"
        db.commit()

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        run = db.get(MonitorRun, seeded["run_id"])
        assert run.status == "completed"
        assert run.collection_status == "completed"
        assert run.succeeded_tasks == 1
        assert run.valid_answer_count == 1
        assert run.finished_at is not None


def test_terminal_failure_aggregates_run_without_detail_api(collection_env, session_factory):
    adapter = collection_env["adapter"]
    adapter.fail_with = AdapterError(
        "invalid request",
        category=ErrorCategory.INVALID_REQUEST,
    )

    with session_factory() as db:
        seeded = _seed_collection_graph(db)
        run = db.get(MonitorRun, seeded["run_id"])
        run.status = "collecting"
        run.collection_status = "running"
        db.commit()

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        run = db.get(MonitorRun, seeded["run_id"])
        assert run.status == "failed"
        assert run.collection_status == "failed"
        assert run.failed_tasks == 1
        assert run.error_summary is not None


def test_duplicate_message_is_idempotent(collection_env, session_factory):
    with session_factory() as db:
        seeded = _seed_collection_graph(db)

    dispatch_task(seeded["task_id"])
    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        answer = answer_repo.get_by_task_id(db, task.id)
        assert task.status == "success"
        assert answer_repo.count_by_task_id(db, task.id) == 1
        citations = db.query(AnswerCitation).filter(AnswerCitation.answer_id == answer.id).all()
        brand_results = db.query(AnswerBrandResult).filter(
            AnswerBrandResult.answer_id == answer.id
        ).all()
        assert len(citations) == 1
        assert len(brand_results) == 2


def test_retryable_error_requeues_and_recovers(collection_env, session_factory):
    adapter = collection_env["adapter"]
    adapter.fail_times = 1

    with session_factory() as db:
        seeded = _seed_collection_graph(db)

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "success"
        assert task.retry_count == 1
        assert task.attempt_count == 2
        assert len(adapter.calls) == 2


def test_aidso_pending_persists_req_id_and_reuses_on_retry(
    collection_env, session_factory
):
    aidso_adapter = MockAidsoAdapter()
    runtime = collection_env["runtime"]
    runtime.adapter_registry.register(aidso_adapter)
    runtime.key_pool.register_platform_credentials(
        "aidso_doubao_web",
        [ApiKeyCredential(platform_code="aidso_doubao_web", api_key="aidso-token")],
    )

    with session_factory() as db:
        seeded = _seed_collection_graph(db)
        platform = db.query(AIPlatform).filter_by(platform_code="qwen").one()
        platform.platform_code = "aidso_doubao_web"
        platform.platform_name = "豆包 Web 端"
        platform.adapter_type = "aidso"
        platform.model_name = "aidso:DB"
        platform.extra_config = {"aidso_name": "DB"}
        run = db.get(MonitorRun, seeded["run_id"])
        run.collection_source = "aidso"
        run.aidso_thinking_enabled = False
        run.platform_codes = ["aidso_doubao_web"]
        task = db.get(QueryTask, seeded["task_id"])
        task.platform_code = "aidso_doubao_web"
        db.commit()

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "success"
        assert task.request_json["aidso_req_id"] == "req-db-1"
        assert task.request_json["aidso_task_id"] == "task-aidso-1"
        assert task.provider_request_id == "req-db-1"

    assert len(aidso_adapter.calls) == 2
    assert "aidso_req_id" not in aidso_adapter.calls[0][0].metadata
    assert aidso_adapter.calls[0][0].metadata["aidso_thinking_enabled"] is False
    assert aidso_adapter.calls[1][0].metadata["aidso_req_id"] == "req-db-1"
    assert aidso_adapter.calls[1][0].metadata["aidso_thinking_enabled"] is False


def test_non_retryable_error_marks_failed(collection_env, session_factory):
    adapter = collection_env["adapter"]
    adapter.fail_with = AdapterError(
        "invalid request",
        category=ErrorCategory.INVALID_REQUEST,
    )

    with session_factory() as db:
        seeded = _seed_collection_graph(db)

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "failed"
        assert task.error_code == ErrorCategory.INVALID_REQUEST.value
        assert answer_repo.get_by_task_id(db, task.id) is None
        assert len(adapter.calls) == 1


def test_cancelled_run_skips_external_api(collection_env, session_factory):
    adapter = collection_env["adapter"]

    with session_factory() as db:
        seeded = _seed_collection_graph(db)
        run = db.get(MonitorRun, seeded["run_id"])
        run.status = "cancelled"
        db.commit()

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "cancelled"
        assert len(adapter.calls) == 0


def test_cancelled_task_skips_external_api(collection_env, session_factory):
    adapter = collection_env["adapter"]

    with session_factory() as db:
        seeded = _seed_collection_graph(db)
        task = db.get(QueryTask, seeded["task_id"])
        task.status = "cancelled"
        db.commit()

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "cancelled"
        assert len(adapter.calls) == 0


def test_worker_crash_recovery_reclaims_stale_running(collection_env, session_factory):
    adapter = collection_env["adapter"]
    stale = datetime.now(timezone.utc) - timedelta(seconds=30)

    with session_factory() as db:
        seeded = _seed_collection_graph(db)
        task = db.get(QueryTask, seeded["task_id"])
        task.status = "running"
        task.started_at = stale
        task.attempt_count = 1
        db.commit()

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "success"
        assert task.attempt_count == 1
        assert len(adapter.calls) == 1


def test_success_persists_normalized_citations_and_brands(collection_env, session_factory):
    with session_factory() as db:
        seeded = _seed_collection_graph(db)

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        answer = answer_repo.get_by_task_id(db, seeded["task_id"])
        assert answer.normalized_text == "推荐目标品牌和竞品B。"
        citation = db.execute(
            AnswerCitation.__table__.select().where(AnswerCitation.answer_id == answer.id)
        ).mappings().one()
        assert citation["url"] == "https://example.com/path"
        assert citation["domain"] == "example.com"

        brand_results = db.execute(
            AnswerBrandResult.__table__.select().where(
                AnswerBrandResult.answer_id == answer.id
            )
        ).mappings().all()
        mentioned = {
            row["brand_id"]: row["is_mentioned"] for row in brand_results
        }
        assert mentioned[seeded["target_brand_id"]] is True
        assert mentioned[seeded["competitor_brand_id"]] is True


def test_dramatiq_message_carries_only_task_id():
    message = collect_query_task.message(42)
    assert message.args == (42,)
    assert message.kwargs == {}


def test_max_attempts_exhaustion_marks_failed(collection_env, session_factory):
    adapter = collection_env["adapter"]
    adapter.fail_with = AdapterError(
        "server down",
        category=ErrorCategory.SERVER_ERROR,
    )

    with session_factory() as db:
        seeded = _seed_collection_graph(db)
        task = db.get(QueryTask, seeded["task_id"])
        task.max_attempts = 1
        db.commit()

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "failed"
        assert task.attempt_count == 1
        assert len(adapter.calls) == 1
