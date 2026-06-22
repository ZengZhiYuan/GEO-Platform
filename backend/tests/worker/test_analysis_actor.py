"""分析 Actor 测试。"""

from __future__ import annotations

import dramatiq
import pytest
from dramatiq.brokers.stub import StubBroker
from sqlalchemy import select

import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401
from app.core.config import Settings
from app.geo_monitoring.adapters.base import PlatformAnswer, PlatformCredential, PlatformQuery
from app.geo_monitoring.adapters.key_pool import ApiKeyCredential, CredentialKeyPool
from app.geo_monitoring.adapters.registry import AdapterRegistry
from app.geo_monitoring.models import (
    AIPlatform,
    Brand,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.services import collection as collection_service
from app.geo_monitoring.services.analysis import PlatformAnalysis
from app.geo_monitoring.services.runs import on_query_task_terminal
from app.worker.actors.analysis import analyze_run, maybe_enqueue_run_analysis
from app.worker.actors.collection import collect_query_task
from tests.geo_monitoring.agents.test_graph import FakeLLMClient, _seed_run


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

    async def query(
        self,
        request: PlatformQuery,
        *,
        credential: PlatformCredential,
    ) -> PlatformAnswer:
        return PlatformAnswer(
            text="推荐目标品牌，优于竞品B。",
            citations=[
                {
                    "title": "引用",
                    "url": "https://example.com/article",
                    "source_type": "web",
                }
            ],
            model="mock-qwen",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            latency_ms=120,
            provider_request_id="req-1",
            raw_response={"mock": True},
        )


@pytest.fixture
def stub_broker():
    broker = StubBroker()
    broker.emit_after("process_boot")
    dramatiq.set_broker(broker)
    return broker


@pytest.fixture
def collection_env(session_factory, stub_broker, tmp_path, monkeypatch):
    settings = Settings(
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

    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.worker.actors.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    monkeypatch.setattr(
        "app.geo_monitoring.services.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    try:
        yield {"llm": llm, "settings": settings}
    finally:
        collection_service.reset_runtime()


def _seed_collection_run(session_factory) -> dict:
    with session_factory() as db:
        project = MonitorProject(project_name="Actor测试", status="active")
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
            run_no="RUN-ACTOR",
            project_id=project.id,
            prompt_set_id=prompt_set.id,
            prompt_set_version="v1",
            platform_codes=["qwen"],
            status="collecting",
            collection_status="running",
            analysis_status="skipped",
            total_tasks=1,
            expected_query_count=1,
        )
        db.add(run)
        db.flush()
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code="qwen",
            idempotency_key="actor-task-1",
            status="queued",
            max_attempts=3,
        )
        db.add(task)
        db.commit()
        return {"run_id": run.id, "task_id": task.id, "project_id": project.id}


def test_collection_terminal_auto_enqueues_analysis_once(
    collection_env, session_factory, monkeypatch
):
    seeded = _seed_collection_run(session_factory)
    sent: list[int] = []
    original_send = analyze_run.send

    def spy_send(run_id: int):
        sent.append(run_id)
        return original_send(run_id)

    monkeypatch.setattr(analyze_run, "send", spy_send)

    dispatch_task(seeded["task_id"])

    with session_factory() as db:
        run = db.get(MonitorRun, seeded["run_id"])
        assert run.status == "completed"
        assert run.collection_status == "completed"

    assert sent == [seeded["run_id"]]
    assert maybe_enqueue_run_analysis(seeded["run_id"]) is False


def test_analyze_run_persists_platform_analysis(collection_env, session_factory):
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))

    analyze_run.fn(seeded["run_id"])

    with session_factory() as db:
        run = db.get(MonitorRun, seeded["run_id"])
        rows = db.execute(
            select(PlatformAnalysis).where(PlatformAnalysis.run_id == seeded["run_id"])
        ).scalars().all()
        assert run.analysis_status == "completed"
        assert len(rows) == 1
        assert rows[0].platform_code == "qwen"


def test_on_query_task_terminal_triggers_enqueue_when_run_becomes_terminal(
    collection_env, session_factory, monkeypatch
):
    seeded = _seed_collection_run(session_factory)
    sent: list[int] = []

    monkeypatch.setattr(
        "app.worker.actors.analysis.maybe_enqueue_run_analysis",
        lambda run_id, db=None: sent.append(run_id) or True,
    )

    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        task.status = "success"
        db.flush()
        on_query_task_terminal(db, seeded["run_id"])

    assert sent == [seeded["run_id"]]
