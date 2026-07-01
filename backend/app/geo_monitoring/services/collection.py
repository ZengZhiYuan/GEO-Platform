"""采集队列编排与 QueryTask 执行服务。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, object_session

from app.core.config import Settings, settings as default_settings
from app.core.database import SessionLocal
from app.geo_monitoring.adapters.base import PlatformAnswer, PlatformQuery
from app.geo_monitoring.adapters.errors import (
    AdapterError,
    ErrorCategory,
    NoAvailableCredentialError,
    is_retryable,
)
from app.geo_monitoring.adapters.key_pool import (
    ApiKeyCredential,
    CredentialKeyPool,
    YuanbaoCredential,
)
from app.geo_monitoring.adapters.registry import (
    AdapterRegistry,
    _aidso_configured,
    _configured,
    _molizhishu_configured,
    build_adapter_registry,
)
from app.geo_monitoring.adapters.molizhishu import MolizhishuPendingError
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    AnswerBrandResult,
    AnswerCitation,
    Brand,
    BrandAlias,
    MonitorRun,
    Prompt,
    ProviderBatch,
    QueryTask,
)
from app.geo_monitoring.repositories import answers as answer_repo
from app.geo_monitoring.repositories import provider_batches as batch_repo
from app.geo_monitoring.services.brand_matcher import (
    build_provider_brand_context,
    match_brands_in_text,
    merge_brand_context_with_provider,
    normalize_answer_text,
)
from app.geo_monitoring.services.platforms import (
    AIDSO_PLATFORM_MAPPINGS,
    MOLIZHISHU_PLATFORM_MAPPINGS,
    serialize_molizhishu_platform_mapping,
)

logger = logging.getLogger(__name__)

TERMINAL_TASK_STATUSES = frozenset({"success", "failed", "cancelled"})
CLAIMABLE_TASK_STATUSES = frozenset({"pending", "queued", "running"})
_KEY_POOL_REDIS_UNSET = object()
_OFFICIAL_API_KEY_PLATFORM_PREFIXES: tuple[tuple[str, str], ...] = (
    ("doubao", "DOUBAO"),
    ("qwen", "QWEN"),
    ("deepseek", "DEEPSEEK"),
    ("kimi", "KIMI"),
)


@dataclass(frozen=True)
class TaskSnapshot:
    task_id: int
    run_id: int
    prompt_id: int
    platform_code: str
    idempotency_key: str
    prompt_text: str
    model_name: str
    project_id: int
    collection_source: str
    provider_mode: str | None
    provider_screenshot: int
    region_code: str | None
    aidso_thinking_enabled: bool
    request_json: dict[str, Any] | None
    reclaim: bool
    provider_callback_url: str | None = None


@dataclass(frozen=True)
class QueryTaskExecutionResult:
    should_retry: bool = False
    retry_delay_seconds: int | None = None


@dataclass(frozen=True)
class ProviderBatchExecutionResult:
    should_retry: bool = False
    retry_delay_seconds: int | None = None


TERMINAL_BATCH_STATUSES = frozenset(
    {"completed", "partial_completed", "failed", "cancelled"}
)


@dataclass(frozen=True)
class MolizhishuCallbackResult:
    outcome: str
    task_id: int | None = None
    message: str | None = None


@dataclass
class CollectionRuntime:
    session_factory: Callable[[], Session]
    settings: Settings
    adapter_registry: AdapterRegistry
    key_pool: CredentialKeyPool
    stale_running_seconds: int | None = None

    # 判定 running 任务是否超时的 stale 阈值
    @property
    def running_stale_after(self) -> timedelta:
        seconds = self.stale_running_seconds
        if seconds is None:
            seconds = self.settings.COLLECTION_REQUEST_TIMEOUT_SECONDS * 2
        return timedelta(seconds=seconds)


_runtime: CollectionRuntime | None = None


# 注入全局采集运行时依赖（测试或自定义配置时使用）
def configure_runtime(runtime: CollectionRuntime) -> None:
    global _runtime
    _runtime = runtime


# 清除全局采集运行时（测试 teardown 使用）
def reset_runtime() -> None:
    global _runtime
    _runtime = None


# 获取全局采集运行时，未配置则构建默认实例
def get_runtime() -> CollectionRuntime:
    global _runtime
    if _runtime is None:
        _runtime = build_default_runtime()
    return _runtime


# 组装默认采集运行时（会话工厂、适配器注册表、密钥池）
def build_default_runtime(
    *,
    session_factory: Callable[[], Session] | None = None,
    runtime_settings: Settings | None = None,
    adapter_registry: AdapterRegistry | None = None,
    key_pool: CredentialKeyPool | None = None,
) -> CollectionRuntime:
    from app.core.config import get_settings

    runtime_settings = runtime_settings or get_settings()
    resolved_session_factory = session_factory or SessionLocal
    molizhishu_mappings = _load_runtime_molizhishu_mappings(resolved_session_factory)
    registry = adapter_registry or build_adapter_registry(
        runtime_settings,
        molizhishu_mappings=molizhishu_mappings,
    )
    pool = key_pool or build_credential_key_pool(
        runtime_settings,
        molizhishu_platform_codes=list(molizhishu_mappings),
    )
    return CollectionRuntime(
        session_factory=resolved_session_factory,
        settings=runtime_settings,
        adapter_registry=registry,
        key_pool=pool,
    )


def _load_runtime_molizhishu_mappings(
    session_factory: Callable[[], Session],
) -> dict:
    from app.geo_monitoring.services.platforms import (
        MOLIZHISHU_PLATFORM_MAPPINGS,
        load_molizhishu_platform_mappings,
    )

    try:
        with session_factory() as db:
            return load_molizhishu_platform_mappings(db, enabled=True)
    except SQLAlchemyError as exc:
        logger.warning("load molizhishu platform mappings from db failed: %s", exc)
        return dict(MOLIZHISHU_PLATFORM_MAPPINGS)


def platform_runtime_diagnostics(db: Session) -> dict[str, Any]:
    """采集运行时各平台 DB / adapter / 凭证脱敏诊断（供 /ready 与脚本复用）。"""
    from app.geo_monitoring.adapters.registry import build_platform_runtime_diagnostics

    runtime = get_runtime()
    platforms = build_platform_runtime_diagnostics(
        db,
        runtime_settings=runtime.settings,
        adapter_registry=runtime.adapter_registry,
        key_pool=runtime.key_pool,
    )
    enabled_in_db = [item for item in platforms if item["db_enabled"]]
    return {
        "collection_ready": all(item["ready_for_collection"] for item in enabled_in_db),
        "platforms": platforms,
    }


# 为跨 worker 凭证协调创建 Redis 客户端；stub broker 测试环境跳过
def _create_key_pool_redis_client(runtime_settings: Settings) -> Any | None:
    if runtime_settings.DRAMATIQ_BROKER == "stub":
        return None
    from redis import Redis

    return Redis.from_url(
        runtime_settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


# 从配置构建各平台 API 密钥池
def build_credential_key_pool(
    runtime_settings: Settings,
    *,
    redis_client: Any | None = _KEY_POOL_REDIS_UNSET,
    molizhishu_platform_codes: list[str] | tuple[str, ...] | None = None,
) -> CredentialKeyPool:
    resolved_redis = (
        _create_key_pool_redis_client(runtime_settings)
        if redis_client is _KEY_POOL_REDIS_UNSET
        else redis_client
    )
    pool = CredentialKeyPool(
        resolved_redis,
        retry_base_seconds=runtime_settings.COLLECTION_RETRY_BASE_SECONDS,
    )
    for platform_code, prefix in _OFFICIAL_API_KEY_PLATFORM_PREFIXES:
        if _configured(runtime_settings, prefix):
            _register_api_keys(
                pool,
                runtime_settings,
                platform_code,
                getattr(runtime_settings, f"{prefix}_API_KEYS"),
            )
    # #region agent log
    import json as _json
    import time as _time
    from pathlib import Path as _Path

    _dbg_payload = {
        "sessionId": "499d7f",
        "hypothesisId": "H1-H5",
        "location": "collection.py:build_credential_key_pool",
        "message": "platform credential registration gate",
        "data": {
            "doubao_enabled": runtime_settings.DOUBAO_ENABLED,
            "qwen_enabled": runtime_settings.QWEN_ENABLED,
            "yuanbao_enabled": runtime_settings.YUANBAO_ENABLED,
            "deepseek_enabled": runtime_settings.DEEPSEEK_ENABLED,
            "kimi_enabled": runtime_settings.KIMI_ENABLED,
            "aidso_enabled": runtime_settings.AIDSO_ENABLED,
            "molizhishu_enabled": runtime_settings.MOLIZHISHU_ENABLED,
            "yuanbao_configured": _configured(runtime_settings, "YUANBAO"),
            "aidso_configured": _aidso_configured(runtime_settings),
            "molizhishu_configured": _molizhishu_configured(runtime_settings),
        },
        "timestamp": int(_time.time() * 1000),
    }
    for _dbg_path in (
        _Path("debug-499d7f.log"),
        _Path(__file__).resolve().parents[4] / "debug-499d7f.log",
    ):
        try:
            with _dbg_path.open("a", encoding="utf-8") as _dbg_f:
                _dbg_f.write(_json.dumps(_dbg_payload) + "\n")
            break
        except OSError:
            continue
    # #endregion
    if _configured(runtime_settings, "YUANBAO"):
        yuanbao_credentials = runtime_settings.parsed_yuanbao_credentials()
        if yuanbao_credentials:
            pool.register_platform_credentials(
                "yuanbao",
                [
                    YuanbaoCredential(
                        platform_code="yuanbao",
                        secret_id=item.secret_id,
                        secret_key=item.secret_key,
                    )
                    for item in yuanbao_credentials
                ],
            )
    if _aidso_configured(runtime_settings):
        aidso_token = runtime_settings.AIDSO_API_TOKEN.strip()
        for platform_code in AIDSO_PLATFORM_MAPPINGS:
            pool.register_platform_credentials(
                platform_code,
                [ApiKeyCredential(platform_code=platform_code, api_key=aidso_token)],
            )
    if _molizhishu_configured(runtime_settings):
        molizhishu_token = runtime_settings.MOLIZHISHU_API_TOKEN.strip()
        platform_codes = molizhishu_platform_codes or tuple(MOLIZHISHU_PLATFORM_MAPPINGS)
        for platform_code in platform_codes:
            pool.register_platform_credentials(
                platform_code,
                [
                    ApiKeyCredential(
                        platform_code=platform_code, api_key=molizhishu_token
                    )
                ],
            )
    return pool


# 将某平台的 API Key 列表注册到密钥池
def _register_api_keys(
    pool: CredentialKeyPool,
    runtime_settings: Settings,
    platform_code: str,
    raw_keys: str,
) -> None:
    keys = runtime_settings.parsed_api_keys(raw_keys)
    if not keys:
        return
    pool.register_platform_credentials(
        platform_code,
        [ApiKeyCredential(platform_code=platform_code, api_key=key) for key in keys],
    )


def _resolve_aidso_thinking_enabled(run: MonitorRun, platform_code: str) -> bool:
    value = (run.aidso_thinking_enabled_by_platform or {}).get(platform_code)
    return value if isinstance(value, bool) else True


def _resolve_provider_mode(run: MonitorRun, platform: AIPlatform) -> str | None:
    platform_code = platform.platform_code
    configured = (run.provider_mode_by_platform or {}).get(platform_code)
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    mapping = (
        serialize_molizhishu_platform_mapping(platform)
        if platform.adapter_type == "molizhishu"
        else None
    )
    if mapping:
        return str(mapping["default_mode"])
    return None


def _task_uses_molizhishu(task: QueryTask) -> bool:
    if task.provider_name == "molizhishu":
        return True
    request_json = task.request_json or {}
    if any(str(key).startswith("molizhishu_") for key in request_json):
        return True
    return task.platform_code.startswith("molizhishu_")


def enqueue_run_query_tasks(run_id: int, *, db: Session | None = None) -> int:
    """运行事务提交后，将 pending 任务标记为 queued 并逐个入队。"""
    runtime = get_runtime()
    owns_session = db is None
    if owns_session:
        db = runtime.session_factory()

    try:
        run = db.execute(
            select(MonitorRun).where(
                MonitorRun.id == run_id,
                MonitorRun.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if run is not None:
            from app.geo_monitoring.services.provider_batches import (
                provider_batch_enabled,
            )

            if provider_batch_enabled(
                run.collection_source,
                runtime_settings=runtime.settings,
            ):
                batches = batch_repo.list_by_run_id(db, run_id)
                if batches:
                    return _enqueue_run_provider_batches(run_id, db=db)
        return _enqueue_individual_query_tasks(run_id, db=db)
    finally:
        if owns_session:
            db.close()


def _enqueue_individual_query_tasks(run_id: int, *, db: Session | None = None) -> int:
    runtime = get_runtime()
    now = datetime.now(timezone.utc)
    task_ids: list[int] = []
    owns_session = db is None
    if owns_session:
        db = runtime.session_factory()

    try:
        tasks = list(
            db.execute(
                select(QueryTask).where(
                    QueryTask.run_id == run_id,
                    QueryTask.status == "pending",
                    QueryTask.is_deleted.is_(False),
                )
            )
            .scalars()
            .all()
        )
        for task in tasks:
            task.status = "queued"
            task.queued_at = now
            task_ids.append(task.id)
        db.commit()
    finally:
        if owns_session:
            db.close()

    from app.worker.actors.collection import collect_query_task

    for task_id in task_ids:
        collect_query_task.send(task_id)
    return len(task_ids)


def _enqueue_run_provider_batches(run_id: int, *, db: Session | None = None) -> int:
    runtime = get_runtime()
    now = datetime.now(timezone.utc)
    batch_ids: list[int] = []
    owns_session = db is None
    if owns_session:
        db = runtime.session_factory()

    try:
        batches = batch_repo.list_by_run_id(db, run_id)
        tasks = list(
            db.execute(
                select(QueryTask).where(
                    QueryTask.run_id == run_id,
                    QueryTask.status == "pending",
                    QueryTask.is_deleted.is_(False),
                )
            )
            .scalars()
            .all()
        )
        for task in tasks:
            task.status = "queued"
            task.queued_at = now
        for batch in batches:
            if batch.status in TERMINAL_BATCH_STATUSES:
                continue
            batch_ids.append(batch.id)
        db.commit()
    finally:
        if owns_session:
            db.close()

    from app.worker.actors.collection import collect_provider_batch

    for batch_id in batch_ids:
        collect_provider_batch.send(batch_id)
    return len(batch_ids)


# QueryTask 终态后回调刷新 Run 聚合状态
def _after_task_terminal(db: Session, run_id: int) -> None:
    from app.geo_monitoring.services.runs import on_query_task_terminal

    on_query_task_terminal(db, run_id)


# 执行单个 QueryTask：认领、调用平台、持久化或处理失败
async def execute_query_task(task_id: int) -> QueryTaskExecutionResult:
    runtime = get_runtime()
    snapshot = _claim_task_for_execution(runtime, task_id)
    if snapshot is None:
        return QueryTaskExecutionResult()

    try:
        platform_answer = await _collect_platform_answer(runtime, snapshot)
    except AdapterError as exc:
        return _handle_adapter_failure(runtime, task_id, exc)
    except Exception as exc:
        return _handle_adapter_failure(
            runtime,
            task_id,
            AdapterError(str(exc), category=ErrorCategory.UNKNOWN),
        )

    _persist_platform_answer(runtime, snapshot, platform_answer, require_running=True)
    return QueryTaskExecutionResult()


async def execute_provider_batch(batch_id: int) -> ProviderBatchExecutionResult:
    """执行 ProviderBatch：合并提交、轮询子任务并回填 QueryTask。"""
    runtime = get_runtime()
    db = runtime.session_factory()
    try:
        batch = batch_repo.get_by_id(db, batch_id)
        if batch is None or batch.status in TERMINAL_BATCH_STATUSES:
            return ProviderBatchExecutionResult()

        run = db.execute(
            select(MonitorRun).where(
                MonitorRun.id == batch.run_id,
                MonitorRun.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if run is None:
            return ProviderBatchExecutionResult()
        if run.status == "cancelled":
            _mark_provider_batch_cancelled(db, batch)
            db.commit()
            _after_task_terminal(db, run.id)
            return ProviderBatchExecutionResult()

        tasks = batch_repo.list_tasks_for_batch(db, batch.id)
        if not tasks:
            batch.status = "completed"
            batch.completed_at = datetime.now(timezone.utc)
            db.commit()
            return ProviderBatchExecutionResult()

        from app.geo_monitoring.services.provider_batches import (
            ProviderBatchItem,
            build_submit_indexes,
            map_subtasks_to_items,
            refresh_batch_counters,
        )

        items = _provider_batch_items_from_tasks(tasks, run)
        credential_platform = tasks[0].platform_code
        credential = await runtime.key_pool.acquire(
            credential_platform,
            request_id=f"provider-batch-{batch.id}",
        )
        api_key = credential.api_key or ""
        settings = runtime.settings

        try:
            if not batch.provider_task_id:
                prompts, platforms, item_indexes = build_submit_indexes(items)
                from app.geo_monitoring.adapters.molizhishu import (
                    extract_molizhishu_subtask_list,
                    submit_molizhishu_shared_batch,
                )

                submit_data = await submit_molizhishu_shared_batch(
                    prompts=prompts,
                    platforms=platforms,
                    api_key=api_key,
                    base_url=settings.MOLIZHISHU_BASE_URL,
                    timeout_seconds=settings.MOLIZHISHU_REQUEST_TIMEOUT_SECONDS,
                    region_code=run.region_code,
                    metadata={"provider_callback_url": run.provider_callback_url},
                )
                payload = submit_data.get("data")
                provider_task_id = (
                    payload.get("taskId")
                    if isinstance(payload, dict)
                    else None
                )
                if not isinstance(provider_task_id, str) or not provider_task_id.strip():
                    raise AdapterError(
                        "molizhishu batch submit missing taskId",
                        category=ErrorCategory.INVALID_REQUEST,
                    )
                subtask_list = extract_molizhishu_subtask_list(submit_data)
                try:
                    mapping = map_subtasks_to_items(subtask_list, items, item_indexes)
                except ValueError as exc:
                    raise AdapterError(
                        str(exc),
                        category=ErrorCategory.INVALID_REQUEST,
                    ) from exc
                now = datetime.now(timezone.utc)
                for task in tasks:
                    if task.status == "success":
                        continue
                    subtask_id = mapping.get(task.id)
                    if subtask_id is None:
                        continue
                    request_json = dict(task.request_json or {})
                    request_json["molizhishu_task_id"] = provider_task_id.strip()
                    request_json["molizhishu_subtask_id"] = subtask_id
                    item = next(
                        (entry for entry in items if entry.query_task_id == task.id),
                        None,
                    )
                    if item is not None:
                        request_json["molizhishu_platform"] = item.molizhishu_platform
                        request_json["molizhishu_mode"] = item.mode
                    task.request_json = request_json
                    task.provider_name = "molizhishu"
                    task.provider_task_id = provider_task_id.strip()
                    task.provider_subtask_id = subtask_id
                    task.status = "running"
                    task.started_at = now
                batch.provider_task_id = provider_task_id.strip()
                batch.status = "submitted"
                batch.submitted_at = now
                batch.raw_submit_json = submit_data
                db.flush()

            from app.geo_monitoring.adapters.molizhishu import (
                extract_molizhishu_task_status_payload,
                get_molizhishu_task_status,
            )

            status_response: dict[str, Any] | None = None
            if batch.provider_task_id:
                status_response = await get_molizhishu_task_status(
                    batch.provider_task_id,
                    api_key=api_key,
                    base_url=settings.MOLIZHISHU_BASE_URL,
                    timeout_seconds=settings.MOLIZHISHU_REQUEST_TIMEOUT_SECONDS,
                )
                provider_main_status = extract_molizhishu_task_status_payload(
                    status_response
                )
                if provider_main_status == "failed":
                    now = datetime.now(timezone.utc)
                    for task in tasks:
                        if task.status == "success":
                            continue
                        _mark_task_failed(
                            db,
                            task,
                            now,
                            error_code=ErrorCategory.INVALID_REQUEST.value,
                            error_message="molizhishu provider batch failed",
                        )
                    batch.status = "failed"
                    batch.error_message = "molizhishu provider batch failed"
                    batch.completed_at = now
                    _record_provider_batch_poll(
                        batch,
                        status_response=status_response,
                    )
                    db.commit()
                    _after_task_terminal(db, run.id)
                    return ProviderBatchExecutionResult()
                if provider_main_status == "stopped":
                    now = datetime.now(timezone.utc)
                    for task in tasks:
                        if task.status in TERMINAL_TASK_STATUSES:
                            continue
                        _mark_task_cancelled(db, task, now)
                    batch.status = "cancelled"
                    batch.completed_at = now
                    _record_provider_batch_poll(
                        batch,
                        status_response=status_response,
                    )
                    db.commit()
                    _after_task_terminal(db, run.id)
                    return ProviderBatchExecutionResult()

            pending_any = False
            subtask_snapshots: list[dict[str, Any]] = []
            for task in tasks:
                if task.status in TERMINAL_TASK_STATUSES:
                    continue
                snapshot = _build_snapshot_for_task(db, runtime, task)
                if snapshot is None:
                    continue
                item = next(
                    (entry for entry in items if entry.query_task_id == task.id),
                    None,
                )
                if item is None:
                    continue
                try:
                    platform_answer = await _fetch_molizhishu_subtask_answer(
                        runtime,
                        snapshot=snapshot,
                        item=item,
                        provider_task_id=batch.provider_task_id or "",
                        api_key=api_key,
                    )
                    _write_platform_answer_to_session(
                        db,
                        snapshot,
                        platform_answer,
                        require_running=False,
                    )
                    subtask_snapshots.append(
                        {
                            "query_task_id": task.id,
                            "subtask_id": task.provider_subtask_id,
                            "status": "success",
                        }
                    )
                except MolizhishuPendingError as exc:
                    pending_any = True
                    subtask_snapshots.append(
                        {
                            "query_task_id": task.id,
                            "subtask_id": task.provider_subtask_id,
                            "status": exc.pending_metadata.get(
                                "molizhishu_status", "pending"
                            ),
                        }
                    )
                except AdapterError as exc:
                    _mark_task_failed(
                        db,
                        task,
                        datetime.now(timezone.utc),
                        error_code=exc.category.value,
                        error_message=exc.sanitized_message(),
                        provider_error_message=getattr(
                            exc, "provider_error_message", None
                        ),
                    )
                    subtask_snapshots.append(
                        {
                            "query_task_id": task.id,
                            "subtask_id": task.provider_subtask_id,
                            "status": "failed",
                            "error": exc.sanitized_message(),
                        }
                    )

            poll_count = 0
            if batch.provider_task_id and (
                status_response is not None or subtask_snapshots
            ):
                poll_count = _record_provider_batch_poll(
                    batch,
                    status_response=status_response,
                    subtask_snapshots=subtask_snapshots or None,
                )

            refresh_batch_counters(db, batch)
            if batch.status in TERMINAL_BATCH_STATUSES:
                batch.completed_at = datetime.now(timezone.utc)
            db.commit()
            _after_task_terminal(db, run.id)

            if pending_any:
                if poll_count >= settings.COLLECTION_MOLIZHISHU_MAX_POLLS:
                    _fail_pending_provider_batch_tasks(db, batch, tasks)
                    refresh_batch_counters(db, batch)
                    batch.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    _after_task_terminal(db, run.id)
                    return ProviderBatchExecutionResult()
                return ProviderBatchExecutionResult(
                    should_retry=True,
                    retry_delay_seconds=settings.COLLECTION_MOLIZHISHU_POLL_DELAY_SECONDS,
                )

            await runtime.key_pool.report_success(
                credential.fingerprint,
                platform_code=credential_platform,
            )
            return ProviderBatchExecutionResult()
        except ValueError as exc:
            await runtime.key_pool.report_failure(
                credential.fingerprint,
                AdapterError(str(exc), category=ErrorCategory.INVALID_REQUEST),
                platform_code=credential_platform,
                request_id=f"provider-batch-{batch.id}",
            )
            now = datetime.now(timezone.utc)
            for task in tasks:
                if task.status == "success":
                    continue
                _mark_task_failed(
                    db,
                    task,
                    now,
                    error_code=ErrorCategory.INVALID_REQUEST.value,
                    error_message=str(exc),
                )
            batch.status = "failed"
            batch.error_message = str(exc)
            batch.completed_at = now
            db.commit()
            _after_task_terminal(db, run.id)
            return ProviderBatchExecutionResult()
        except AdapterError as exc:
            await runtime.key_pool.report_failure(
                credential.fingerprint,
                exc,
                platform_code=credential_platform,
                request_id=f"provider-batch-{batch.id}",
            )
            now = datetime.now(timezone.utc)
            for task in tasks:
                if task.status == "success":
                    continue
                _mark_task_failed(
                    db,
                    task,
                    now,
                    error_code=exc.category.value,
                    error_message=exc.sanitized_message(),
                )
            batch.status = "failed"
            batch.error_message = exc.sanitized_message()
            batch.completed_at = now
            db.commit()
            _after_task_terminal(db, run.id)
            return ProviderBatchExecutionResult()
    finally:
        db.close()


def _provider_batch_items_from_tasks(
    tasks: list[QueryTask],
    run: MonitorRun,
) -> list:
    if not tasks:
        return []

    from app.geo_monitoring.services.provider_batches import (
        ProviderBatchItem,
        _resolve_mode,
        _resolve_molizhishu_platform,
    )
    from app.geo_monitoring.services.platforms import load_molizhishu_platform_mappings

    session = object_session(run) or object_session(tasks[0])
    if session is None:
        raise RuntimeError("provider batch tasks must be attached to a Session")
    mappings = load_molizhishu_platform_mappings(session)

    items: list[ProviderBatchItem] = []
    for task in tasks:
        request_json = task.request_json or {}
        prompt_text = str(request_json.get("prompt_text") or "").strip()
        items.append(
            ProviderBatchItem(
                query_task_id=task.id,
                prompt_id=task.prompt_id,
                platform_code=task.platform_code,
                prompt_text=prompt_text,
                molizhishu_platform=_resolve_molizhishu_platform(
                    task.platform_code, mappings
                ),
                mode=_resolve_mode(run, task.platform_code, mappings),
                screenshot=run.provider_screenshot,
            )
        )
    return items


async def _fetch_molizhishu_subtask_answer(
    runtime: CollectionRuntime,
    *,
    snapshot: TaskSnapshot,
    item,
    provider_task_id: str,
    api_key: str,
) -> PlatformAnswer:
    from app.geo_monitoring.adapters.molizhishu import (
        MolizhishuPendingError,
        get_molizhishu_subtask_result,
        platform_answer_from_molizhishu_result,
    )

    request_json = snapshot.request_json or {}
    last_status = request_json.get("molizhishu_status")
    subtask_id = snapshot.request_json.get("molizhishu_subtask_id") if snapshot.request_json else None
    if not isinstance(subtask_id, str) or not subtask_id.strip():
        subtask_id = None
    if subtask_id is None:
        raise AdapterError(
            "molizhishu batch task missing subTaskId",
            category=ErrorCategory.INVALID_REQUEST,
        )

    result_data = await get_molizhishu_subtask_result(
        provider_task_id,
        subtask_id,
        api_key=api_key,
        base_url=runtime.settings.MOLIZHISHU_BASE_URL,
        timeout_seconds=runtime.settings.MOLIZHISHU_REQUEST_TIMEOUT_SECONDS,
        molizhishu_platform=item.molizhishu_platform,
        mode=item.mode,
        last_status=last_status if isinstance(last_status, str) else None,
    )
    payload = result_data.get("data")
    if not isinstance(payload, dict):
        payload = result_data
    status = payload.get("status")
    status_text = status.strip() if isinstance(status, str) else ""
    text = str(payload.get("answerContent") or "")
    if status_text in {"pending", "assigned", "processing"} and not text.strip():
        raise MolizhishuPendingError(
            pending_metadata={
                "molizhishu_task_id": provider_task_id,
                "molizhishu_subtask_id": subtask_id,
                "molizhishu_platform": item.molizhishu_platform,
                "molizhishu_mode": item.mode,
                "molizhishu_status": status_text or "unknown",
            }
        )
    if status_text == "stopped":
        raise AdapterError(
            f"molizhishu subtask stopped: {payload.get('errorMessage') or ''}",
            category=ErrorCategory.CANCELLED,
        )
    if status_text in {"failed", "error"}:
        raise AdapterError(
            f"molizhishu subtask failed: {payload.get('errorMessage') or ''}",
            category=ErrorCategory.INVALID_REQUEST,
            provider_error_message=str(payload.get("errorMessage") or ""),
        )
    return platform_answer_from_molizhishu_result(
        payload,
        model=snapshot.model_name,
        subtask_id=subtask_id,
        raw_response={"result": result_data},
    )


def _record_provider_batch_poll(
    batch: ProviderBatch,
    *,
    status_response: dict[str, Any] | None = None,
    subtask_snapshots: list[dict[str, Any]] | None = None,
) -> int:
    status_json = dict(batch.raw_status_json or {})
    poll_count = int(status_json.get("poll_count") or 0) + 1
    status_json["poll_count"] = poll_count
    if status_response is not None:
        status_json["last_provider_status"] = status_response
    batch.raw_status_json = status_json
    if subtask_snapshots is not None:
        batch.raw_result_json = {
            "poll_count": poll_count,
            "subtasks": subtask_snapshots,
        }
    return poll_count


def _increment_provider_batch_poll_count(batch: ProviderBatch) -> int:
    return _record_provider_batch_poll(batch)


def _fail_pending_provider_batch_tasks(
    db: Session,
    batch: ProviderBatch,
    tasks: list[QueryTask],
) -> None:
    now = datetime.now(timezone.utc)
    for task in tasks:
        if task.status in TERMINAL_TASK_STATUSES:
            continue
        _mark_task_failed(
            db,
            task,
            now,
            error_code=ErrorCategory.PENDING.value,
            error_message="molizhishu batch poll limit exceeded",
        )
    batch.error_message = "molizhishu batch poll limit exceeded"


def _mark_provider_batch_cancelled(db: Session, batch: ProviderBatch) -> None:
    now = datetime.now(timezone.utc)
    batch.status = "cancelled"
    batch.completed_at = now
    for task in batch_repo.list_tasks_for_batch(db, batch.id):
        if task.status not in TERMINAL_TASK_STATUSES:
            _mark_task_cancelled(db, task, now)


def _refresh_provider_batch_after_task(db: Session, task: QueryTask) -> None:
    if task.provider_batch_id is None:
        return
    from app.geo_monitoring.services.provider_batches import refresh_batch_counters

    batch = batch_repo.get_by_id(db, task.provider_batch_id)
    if batch is None:
        return
    refresh_batch_counters(db, batch)
    if batch.status in TERMINAL_BATCH_STATUSES and batch.completed_at is None:
        batch.completed_at = datetime.now(timezone.utc)
    db.flush()


# 加锁认领 QueryTask 并构建执行快照，不可执行时返回 None
def _claim_task_for_execution(
    runtime: CollectionRuntime,
    task_id: int,
) -> TaskSnapshot | None:
    now = datetime.now(timezone.utc)
    db = runtime.session_factory()
    try:
        task = db.execute(
            select(QueryTask)
            .where(QueryTask.id == task_id, QueryTask.is_deleted.is_(False))
            .with_for_update()
        ).scalar_one_or_none()
        if task is None:
            return None

        if task.status in TERMINAL_TASK_STATUSES:
            return None

        if task.provider_batch_id is not None:
            return None

        run = db.execute(
            select(MonitorRun).where(
                MonitorRun.id == task.run_id,
                MonitorRun.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if run is None:
            return None

        # 运行或任务已取消则标记 cancelled 并刷新聚合
        if run.status == "cancelled" or task.status == "cancelled":
            _mark_task_cancelled(db, task, now)
            run_id = task.run_id
            db.commit()
            _after_task_terminal(db, run_id)
            return None

        if task.status == "running":
            started_at = _as_utc(task.started_at or task.updated_at or now)
            # running 未超时则跳过，避免重复执行
            if now - started_at < runtime.running_stale_after:
                return None
            reclaim = True
        elif task.status in {"pending", "queued"}:
            reclaim = False
        else:
            return None

        # 答案已存在则直接将任务标为 success
        if answer_repo.get_by_task_id(db, task.id) is not None:
            task.status = "success"
            task.completed_at = now
            task.finished_at = now
            run_id = task.run_id
            db.commit()
            _after_task_terminal(db, run_id)
            return None

        prompt = db.execute(
            select(Prompt).where(
                Prompt.id == task.prompt_id,
                Prompt.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        platform = db.execute(
            select(AIPlatform).where(
                AIPlatform.platform_code == task.platform_code,
                AIPlatform.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if prompt is None or platform is None or not platform.enabled:
            # 提示词或平台不可用则标记失败
            _mark_task_failed(
                db,
                task,
                now,
                error_code=ErrorCategory.INVALID_REQUEST.value,
                error_message="prompt or platform unavailable",
            )
            run_id = task.run_id
            db.commit()
            _after_task_terminal(db, run_id)
            return None

        if not reclaim and not _is_provider_pending_poll(task):
            task.attempt_count += 1
        # 更新为 running 并返回执行快照
        task.status = "running"
        task.started_at = now
        task.error_code = None
        task.error_message = None
        db.commit()

        return TaskSnapshot(
            task_id=task.id,
            run_id=task.run_id,
            prompt_id=task.prompt_id,
            platform_code=task.platform_code,
            idempotency_key=task.idempotency_key,
            prompt_text=prompt.prompt_text,
            model_name=_resolve_model(runtime.settings, platform),
            project_id=run.project_id,
            collection_source=run.collection_source,
            provider_mode=_resolve_provider_mode(run, platform),
            provider_screenshot=run.provider_screenshot,
            region_code=run.region_code,
            aidso_thinking_enabled=_resolve_aidso_thinking_enabled(
                run, task.platform_code
            ),
            request_json=task.request_json,
            reclaim=reclaim,
            provider_callback_url=run.provider_callback_url,
        )
    finally:
        db.close()


# 调用平台适配器查询并上报密钥池成功/失败
async def _collect_platform_answer(
    runtime: CollectionRuntime,
    snapshot: TaskSnapshot,
) -> PlatformAnswer:
    adapter = runtime.adapter_registry.get(snapshot.platform_code)
    credential = await runtime.key_pool.acquire(
        snapshot.platform_code,
        request_id=snapshot.idempotency_key,
    )
    request = PlatformQuery(
        prompt=snapshot.prompt_text,
        system_prompt=None,
        model=snapshot.model_name,
        temperature=None,
        request_id=snapshot.idempotency_key,
        metadata=_build_platform_query_metadata(runtime, snapshot),
    )
    try:
        answer = await adapter.query(request, credential=credential)
        await runtime.key_pool.report_success(
            credential.fingerprint,
            platform_code=snapshot.platform_code,
        )
        return answer
    except AdapterError as exc:
        # 失败时通知密钥池以便轮换或退避
        await runtime.key_pool.report_failure(
            credential.fingerprint,
            exc,
            platform_code=snapshot.platform_code,
            request_id=snapshot.idempotency_key,
        )
        raise


# 持久化平台答案、引用、品牌匹配结果并标记任务成功
def _persist_success(
    runtime: CollectionRuntime,
    snapshot: TaskSnapshot,
    platform_answer: PlatformAnswer,
) -> None:
    _persist_platform_answer(
        runtime,
        snapshot,
        platform_answer,
        require_running=True,
    )


def _persist_platform_answer(
    runtime: CollectionRuntime,
    snapshot: TaskSnapshot,
    platform_answer: PlatformAnswer,
    *,
    require_running: bool,
) -> bool:
    """写入答案与引用；返回 True 表示新写入，False 表示重复或跳过。"""
    db = runtime.session_factory()
    try:
        created = _write_platform_answer_to_session(
            db,
            snapshot,
            platform_answer,
            require_running=require_running,
        )
        db.commit()
        task = db.get(QueryTask, snapshot.task_id)
        if task is not None and task.status == "success":
            _after_task_terminal(db, task.run_id)
        return created
    except IntegrityError:
        db.rollback()
        return _recover_duplicate_platform_answer(
            runtime,
            snapshot,
            platform_answer,
            require_running=require_running,
        )
    finally:
        db.close()


def _recover_duplicate_platform_answer(
    runtime: CollectionRuntime,
    snapshot: TaskSnapshot,
    platform_answer: PlatformAnswer,
    *,
    require_running: bool,
) -> bool:
    """唯一约束冲突后按 duplicate 收敛，避免并发写入返回异常。"""
    db = runtime.session_factory()
    try:
        created = _write_platform_answer_to_session(
            db,
            snapshot,
            platform_answer,
            require_running=require_running,
        )
        db.commit()
        task = db.get(QueryTask, snapshot.task_id)
        if task is not None and task.status == "success":
            _after_task_terminal(db, task.run_id)
        return created
    finally:
        db.close()


def _mark_task_success_if_needed(
    db: Session,
    task: QueryTask,
    *,
    platform_answer: PlatformAnswer | None = None,
    snapshot: TaskSnapshot | None = None,
    now: datetime | None = None,
) -> None:
    if task.status == "success":
        return
    now = now or datetime.now(timezone.utc)
    task.status = "success"
    task.completed_at = now
    task.finished_at = now
    if platform_answer is not None:
        task.latency_ms = platform_answer.latency_ms
        task.provider_request_id = platform_answer.provider_request_id
        task.response_http_status = 200
        task.last_error_code = None
        task.last_error_message = None
        if snapshot is not None:
            _apply_provider_task_fields(task, snapshot, platform_answer)


def _write_platform_answer_to_session(
    db: Session,
    snapshot: TaskSnapshot,
    platform_answer: PlatformAnswer,
    *,
    require_running: bool,
) -> bool:
    """在同一 session 内写入答案；返回 True 表示新写入，False 表示重复或跳过。"""
    now = datetime.now(timezone.utc)
    normalized_text = normalize_answer_text(platform_answer.text)
    task = db.get(QueryTask, snapshot.task_id)
    if task is None:
        return False
    if require_running and task.status != "running":
        return False
    if (
        not require_running
        and task.status in TERMINAL_TASK_STATUSES
        and task.status != "success"
    ):
        return False

    existing = answer_repo.get_by_task_id(db, task.id)
    if existing is not None:
        _mark_task_success_if_needed(
            db,
            task,
            platform_answer=platform_answer,
            snapshot=snapshot,
            now=now,
        )
        return False

    answer = Answer(
        task_id=task.id,
        platform_code=snapshot.platform_code,
        prompt_id=snapshot.prompt_id,
        raw_text=platform_answer.text,
        normalized_text=normalized_text,
        model_name=platform_answer.model,
        prompt_tokens=int(platform_answer.usage.get("prompt_tokens") or 0),
        completion_tokens=int(platform_answer.usage.get("completion_tokens") or 0),
        total_tokens=int(platform_answer.usage.get("total_tokens") or 0),
        latency_ms=platform_answer.latency_ms,
        raw_response_json=platform_answer.raw_response,
    )
    answer_repo.add(db, answer)
    db.flush()

    for index, citation in enumerate(platform_answer.citations, start=1):
        normalized_url = normalize_citation_url(citation.get("url"))
        answer_repo.add_citation(
            db,
            AnswerCitation(
                answer_id=answer.id,
                citation_no=index,
                title=citation.get("title"),
                url=normalized_url,
                domain=extract_domain(normalized_url),
                source_type=citation.get("source_type"),
                quoted_text=citation.get("quoted_text") or citation.get("snippet"),
            ),
        )

    brands, aliases_by_brand = _load_project_brands(db, snapshot.project_id)
    provider_brand_context = build_provider_brand_context(
        _extract_molizhishu_result_payload(platform_answer)
    )
    for match in match_brands_in_text(normalized_text, brands, aliases_by_brand):
        answer_repo.add_brand_result(
            db,
            AnswerBrandResult(
                answer_id=answer.id,
                brand_id=match.brand_id,
                is_mentioned=match.is_mentioned,
                mention_count=match.mention_count,
                first_position=match.first_position,
                context_json=merge_brand_context_with_provider(
                    match.context_json,
                    provider_brand_context,
                ),
            ),
        )

    _mark_task_success_if_needed(
        db,
        task,
        platform_answer=platform_answer,
        snapshot=snapshot,
        now=now,
    )
    return True


def _handle_adapter_failure(
    runtime: CollectionRuntime,
    task_id: int,
    error: AdapterError,
) -> QueryTaskExecutionResult:
    """记录失败并在可重试时返回重试决策，由调用方在 asyncio.run 结束后入队。"""
    now = datetime.now(timezone.utc)
    db = runtime.session_factory()
    try:
        task = db.get(QueryTask, task_id)
        if task is None or task.status not in {"running", "queued", "pending"}:
            return QueryTaskExecutionResult()

        task.last_error_code = error.category.value
        task.last_error_message = error.sanitized_message()
        task.error_code = error.category.value
        task.error_message = error.sanitized_message()
        pending_poll_count = _persist_pending_metadata(task, error)

        # 可重试且未达上限则重新入队
        if _should_retry_task(runtime, task, error, pending_poll_count):
            task.status = "queued"
            task.retry_count += 1
            task.started_at = None
            retry_delay_seconds = None
            if (
                error.category == ErrorCategory.PENDING
                and _task_uses_molizhishu(task)
            ):
                retry_delay_seconds = (
                    runtime.settings.COLLECTION_MOLIZHISHU_POLL_DELAY_SECONDS
                )
            db.commit()
            return QueryTaskExecutionResult(
                should_retry=True,
                retry_delay_seconds=retry_delay_seconds,
            )

        if error.category == ErrorCategory.CANCELLED:
            _mark_task_cancelled(db, task, now)
        else:
            _mark_task_failed(
                db,
                task,
                now,
                error_code=error.category.value,
                error_message=error.sanitized_message(),
                provider_error_message=getattr(error, "provider_error_message", None),
            )
        run_id = task.run_id
        db.commit()
        _after_task_terminal(db, run_id)
        return QueryTaskExecutionResult()
    finally:
        db.close()


def _build_platform_query_metadata(
    runtime: CollectionRuntime,
    snapshot: TaskSnapshot,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        **(snapshot.request_json or {}),
        "collection_source": snapshot.collection_source,
    }
    if snapshot.provider_mode is not None:
        metadata["provider_mode"] = snapshot.provider_mode
    metadata["provider_screenshot"] = snapshot.provider_screenshot
    if snapshot.region_code:
        metadata["region_code"] = snapshot.region_code
    if snapshot.provider_callback_url:
        metadata["provider_callback_url"] = snapshot.provider_callback_url
    if (
        snapshot.collection_source == "aidso"
        and snapshot.platform_code in AIDSO_PLATFORM_MAPPINGS
    ):
        metadata["aidso_thinking_enabled"] = snapshot.aidso_thinking_enabled
    return metadata


def _is_provider_pending_poll(task: QueryTask) -> bool:
    if task.last_error_code != ErrorCategory.PENDING.value:
        return False
    request_json = task.request_json or {}
    if task.platform_code in AIDSO_PLATFORM_MAPPINGS:
        return isinstance(request_json.get("aidso_req_id"), str) and bool(
            request_json.get("aidso_req_id", "").strip()
        )
    if _task_uses_molizhishu(task):
        return isinstance(request_json.get("molizhishu_subtask_id"), str) and bool(
            request_json.get("molizhishu_subtask_id", "").strip()
        )
    return False


def _pending_poll_count_key(task: QueryTask) -> str:
    if _task_uses_molizhishu(task):
        return "molizhishu_poll_count"
    return "aidso_poll_count"


def _pending_max_polls(runtime: CollectionRuntime, task: QueryTask) -> int:
    if _task_uses_molizhishu(task):
        return runtime.settings.COLLECTION_MOLIZHISHU_MAX_POLLS
    return runtime.settings.COLLECTION_AIDSO_MAX_POLLS


def _should_retry_task(
    runtime: CollectionRuntime,
    task: QueryTask,
    error: AdapterError,
    pending_poll_count: int | None,
) -> bool:
    if not is_retryable(error.category):
        return False
    if error.category == ErrorCategory.PENDING:
        return (pending_poll_count or 0) < _pending_max_polls(runtime, task)
    return task.attempt_count < task.max_attempts


def _persist_pending_metadata(task: QueryTask, error: AdapterError) -> int | None:
    pending_metadata = getattr(error, "pending_metadata", None)
    if not isinstance(pending_metadata, dict):
        return None
    request_json = dict(task.request_json or {})
    request_json.update(pending_metadata)
    poll_count = None
    if error.category == ErrorCategory.PENDING:
        poll_key = _pending_poll_count_key(task)
        poll_count = int(request_json.get(poll_key) or 0) + 1
        request_json[poll_key] = poll_count
    task.request_json = request_json
    if _task_uses_molizhishu(task):
        subtask_id = pending_metadata.get("molizhishu_subtask_id")
        if isinstance(subtask_id, str) and subtask_id.strip():
            task.provider_request_id = subtask_id.strip()
    else:
        req_id = pending_metadata.get("aidso_req_id")
        if isinstance(req_id, str) and req_id.strip():
            task.provider_request_id = req_id.strip()
    return poll_count


# 将 QueryTask 标记为 failed 并写入错误信息
def _mark_task_failed(
    db: Session,
    task: QueryTask,
    now: datetime,
    *,
    error_code: str,
    error_message: str,
    provider_error_message: str | None = None,
) -> None:
    task.status = "failed"
    task.error_code = error_code
    task.error_message = error_message
    task.last_error_code = error_code
    task.last_error_message = error_message
    if provider_error_message and _task_uses_molizhishu(task):
        task.provider_error_message = provider_error_message
    task.completed_at = now
    task.finished_at = now


def _extract_molizhishu_result_payload(
    platform_answer: PlatformAnswer,
) -> dict[str, Any] | None:
    raw = platform_answer.raw_response
    if not isinstance(raw, dict):
        return None
    result = raw.get("result")
    if not isinstance(result, dict):
        return None
    data = result.get("data")
    return data if isinstance(data, dict) else None


def _apply_provider_task_fields(
    task: QueryTask,
    snapshot: TaskSnapshot,
    platform_answer: PlatformAnswer,
) -> None:
    if snapshot.collection_source != "molizhishu":
        return
    request_json = snapshot.request_json or {}
    task.provider_name = "molizhishu"
    task_id = request_json.get("molizhishu_task_id")
    if isinstance(task_id, str) and task_id.strip():
        task.provider_task_id = task_id.strip()
    subtask_id = platform_answer.provider_request_id or request_json.get(
        "molizhishu_subtask_id"
    )
    if isinstance(subtask_id, str) and subtask_id.strip():
        task.provider_subtask_id = subtask_id.strip()
    platform_code = request_json.get("molizhishu_platform")
    if isinstance(platform_code, str) and platform_code.strip():
        task.provider_platform_code = platform_code.strip()
    mode = snapshot.provider_mode or request_json.get("molizhishu_mode")
    if isinstance(mode, str) and mode.strip():
        task.provider_mode = mode.strip()
    payload = _extract_molizhishu_result_payload(platform_answer)
    if isinstance(payload, dict):
        status = payload.get("status")
        if isinstance(status, str) and status.strip():
            task.provider_status = status.strip()
        task.provider_result_json = payload


def find_query_task_by_molizhishu_ids(
    db: Session,
    *,
    provider_task_id: str,
    provider_subtask_id: str,
) -> QueryTask | None:
    """根据模力指数 taskId/subTaskId 查找本地 QueryTask。"""
    task = db.execute(
        select(QueryTask).where(
            QueryTask.is_deleted.is_(False),
            QueryTask.provider_task_id == provider_task_id,
            QueryTask.provider_subtask_id == provider_subtask_id,
        )
    ).scalar_one_or_none()
    if task is not None:
        return task

    candidates = list(
        db.execute(
            select(QueryTask)
            .join(AIPlatform, QueryTask.platform_code == AIPlatform.platform_code)
            .where(
                QueryTask.is_deleted.is_(False),
                AIPlatform.adapter_type == "molizhishu",
                AIPlatform.is_deleted.is_(False),
                QueryTask.provider_task_id == provider_task_id,
            )
        )
        .scalars()
        .all()
    )
    for candidate in candidates:
        request_json = candidate.request_json or {}
        subtask_id = request_json.get("molizhishu_subtask_id")
        if candidate.provider_subtask_id == provider_subtask_id or (
            isinstance(subtask_id, str) and subtask_id.strip() == provider_subtask_id
        ):
            return candidate

    candidates = list(
        db.execute(
            select(QueryTask)
            .join(AIPlatform, QueryTask.platform_code == AIPlatform.platform_code)
            .where(
                QueryTask.is_deleted.is_(False),
                AIPlatform.adapter_type == "molizhishu",
                AIPlatform.is_deleted.is_(False),
                QueryTask.provider_task_id.is_(None),
                QueryTask.status.notin_(tuple(TERMINAL_TASK_STATUSES)),
            )
        )
        .scalars()
        .all()
    )
    for candidate in candidates:
        request_json = candidate.request_json or {}
        task_id = request_json.get("molizhishu_task_id")
        subtask_id = request_json.get("molizhishu_subtask_id")
        if (
            isinstance(task_id, str)
            and task_id.strip() == provider_task_id
            and isinstance(subtask_id, str)
            and subtask_id.strip() == provider_subtask_id
        ):
            return candidate
    return None


def _build_snapshot_for_task(
    db: Session,
    runtime: CollectionRuntime,
    task: QueryTask,
) -> TaskSnapshot | None:
    run = db.execute(
        select(MonitorRun).where(
            MonitorRun.id == task.run_id,
            MonitorRun.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    prompt = db.execute(
        select(Prompt).where(
            Prompt.id == task.prompt_id,
            Prompt.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    platform = db.execute(
        select(AIPlatform).where(
            AIPlatform.platform_code == task.platform_code,
            AIPlatform.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if run is None or prompt is None or platform is None:
        return None
    return TaskSnapshot(
        task_id=task.id,
        run_id=task.run_id,
        prompt_id=task.prompt_id,
        platform_code=task.platform_code,
        idempotency_key=task.idempotency_key,
        prompt_text=prompt.prompt_text,
        model_name=_resolve_model(runtime.settings, platform),
        project_id=run.project_id,
        collection_source=run.collection_source,
        provider_mode=_resolve_provider_mode(run, platform),
        provider_screenshot=run.provider_screenshot,
        region_code=run.region_code,
        aidso_thinking_enabled=_resolve_aidso_thinking_enabled(run, task.platform_code),
        request_json=task.request_json,
        reclaim=False,
        provider_callback_url=run.provider_callback_url,
    )


def _aggregate_molizhishu_callback_outcomes(
    outcomes: list[MolizhishuCallbackResult],
) -> MolizhishuCallbackResult:
    if not outcomes:
        return MolizhishuCallbackResult(outcome="ignored")
    if any(item.outcome == "processed" for item in outcomes):
        task_id = next(
            item.task_id for item in outcomes if item.outcome == "processed"
        )
        return MolizhishuCallbackResult(outcome="processed", task_id=task_id)
    if any(item.outcome == "failed_task" for item in outcomes):
        task_id = next(
            item.task_id for item in outcomes if item.outcome == "failed_task"
        )
        return MolizhishuCallbackResult(outcome="failed_task", task_id=task_id)
    if all(item.outcome == "duplicate" for item in outcomes):
        return MolizhishuCallbackResult(
            outcome="duplicate",
            task_id=outcomes[0].task_id,
        )
    if all(item.outcome == "ignored" for item in outcomes):
        return MolizhishuCallbackResult(
            outcome="ignored",
            task_id=outcomes[0].task_id,
        )
    return MolizhishuCallbackResult(
        outcome="ignored",
        task_id=outcomes[0].task_id,
        message="batch callback mixed outcomes",
    )


def _dispatch_molizhishu_batch_callback(
    db: Session,
    payload: dict[str, Any],
    *,
    provider_task_id: str,
    subtask_list: list[dict[str, Any]],
) -> MolizhishuCallbackResult:
    """处理 batch 形态 callback：按 subTaskList 逐条复用单任务入库逻辑。"""
    from app.geo_monitoring.services.provider_batches import refresh_batch_counters

    batch = batch_repo.get_by_provider_task_id(db, provider_task_id)
    if batch is not None:
        batch.raw_result_json = {"callback": payload}
        db.flush()

    outcomes: list[MolizhishuCallbackResult] = []
    for subtask_data in subtask_list:
        subtask_id = subtask_data.get("subTaskId")
        if not isinstance(subtask_id, str) or not subtask_id.strip():
            continue
        synthetic_payload = {
            **subtask_data,
            "taskId": provider_task_id,
            "subTaskId": subtask_id.strip(),
        }
        outcomes.append(
            _handle_molizhishu_single_subtask_callback(db, synthetic_payload)
        )

    if batch is not None:
        refresh_batch_counters(db, batch)
        if batch.status in TERMINAL_BATCH_STATUSES and batch.completed_at is None:
            batch.completed_at = datetime.now(timezone.utc)
        db.commit()

    return _aggregate_molizhishu_callback_outcomes(outcomes)


def _handle_molizhishu_single_subtask_callback(
    db: Session,
    payload: dict[str, Any],
) -> MolizhishuCallbackResult:
    """处理单条 subTask callback（供 batch dispatch 与 HTTP 入口复用）。"""
    from app.geo_monitoring.adapters.molizhishu import (
        _PENDING_STATUSES,
        _TERMINAL_FAILURE_STATUSES,
        molizhishu_callback_result_status,
        parse_molizhishu_callback_payload,
        platform_answer_from_molizhishu_result,
    )

    runtime = get_runtime()
    try:
        provider_task_id, provider_subtask_id, result_data = (
            parse_molizhishu_callback_payload(payload)
        )
    except ValueError as exc:
        logger.warning("molizhishu callback invalid payload: %s", exc)
        return MolizhishuCallbackResult(outcome="invalid_payload", message=str(exc))

    task = find_query_task_by_molizhishu_ids(
        db,
        provider_task_id=provider_task_id,
        provider_subtask_id=provider_subtask_id,
    )
    if task is None:
        logger.warning(
            "molizhishu callback task not found task_id=%s subtask_id=%s",
            provider_task_id,
            provider_subtask_id,
        )
        return MolizhishuCallbackResult(outcome="task_not_found")

    locked_task = db.execute(
        select(QueryTask)
        .where(QueryTask.id == task.id, QueryTask.is_deleted.is_(False))
        .with_for_update()
    ).scalar_one_or_none()
    if locked_task is None:
        return MolizhishuCallbackResult(outcome="task_not_found")

    if answer_repo.get_by_task_id(db, locked_task.id) is not None:
        was_success = locked_task.status == "success"
        _mark_task_success_if_needed(db, locked_task)
        db.commit()
        if not was_success:
            _after_task_terminal(db, locked_task.run_id)
        logger.info(
            "molizhishu callback duplicate task_id=%s subtask_id=%s query_task_id=%s",
            provider_task_id,
            provider_subtask_id,
            locked_task.id,
        )
        return MolizhishuCallbackResult(outcome="duplicate", task_id=locked_task.id)

    status = molizhishu_callback_result_status(result_data)
    if status in _PENDING_STATUSES:
        request_json = dict(locked_task.request_json or {})
        request_json.update(
            {
                "molizhishu_task_id": provider_task_id,
                "molizhishu_subtask_id": provider_subtask_id,
                "molizhishu_status": status,
            }
        )
        locked_task.request_json = request_json
        locked_task.provider_task_id = provider_task_id
        locked_task.provider_subtask_id = provider_subtask_id
        locked_task.provider_status = status
        db.commit()
        return MolizhishuCallbackResult(outcome="ignored", task_id=locked_task.id)

    snapshot = _build_snapshot_for_task(db, runtime, locked_task)
    if snapshot is None:
        db.rollback()
        return MolizhishuCallbackResult(
            outcome="task_not_found", task_id=locked_task.id
        )

    if status in _TERMINAL_FAILURE_STATUSES or status == "stopped":
        now = datetime.now(timezone.utc)
        error_message = str(result_data.get("errorMessage") or f"status={status}")
        if status == "stopped":
            _mark_task_cancelled(db, locked_task, now)
        else:
            _mark_task_failed(
                db,
                locked_task,
                now,
                error_code=ErrorCategory.INVALID_REQUEST.value,
                error_message=error_message,
                provider_error_message=error_message,
            )
        locked_task.provider_task_id = provider_task_id
        locked_task.provider_subtask_id = provider_subtask_id
        locked_task.provider_status = status
        locked_task.provider_result_json = result_data
        run_id = locked_task.run_id
        db.commit()
        _refresh_provider_batch_after_task(db, locked_task)
        _after_task_terminal(db, run_id)
        return MolizhishuCallbackResult(outcome="failed_task", task_id=locked_task.id)

    if status != "completed":
        db.commit()
        return MolizhishuCallbackResult(
            outcome="ignored",
            task_id=locked_task.id,
            message=f"unsupported status: {status or 'unknown'}",
        )

    try:
        platform_answer = platform_answer_from_molizhishu_result(
            result_data,
            model=snapshot.model_name,
            subtask_id=provider_subtask_id,
            raw_response={"callback": payload, "result": {"data": result_data}},
        )
    except AdapterError as exc:
        logger.warning(
            "molizhishu callback normalize failed task_id=%s subtask_id=%s message=%s",
            provider_task_id,
            provider_subtask_id,
            exc.sanitized_message(),
        )
        db.rollback()
        return MolizhishuCallbackResult(
            outcome="invalid_payload",
            task_id=locked_task.id,
            message=exc.sanitized_message(),
        )

    request_json = dict(locked_task.request_json or {})
    request_json.update(
        {
            "molizhishu_task_id": provider_task_id,
            "molizhishu_subtask_id": provider_subtask_id,
            "molizhishu_status": status,
        }
    )
    locked_task.request_json = request_json
    locked_task.provider_task_id = provider_task_id
    locked_task.provider_subtask_id = provider_subtask_id

    try:
        created = _write_platform_answer_to_session(
            db,
            snapshot,
            platform_answer,
            require_running=False,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = answer_repo.get_by_task_id(db, task.id)
        if existing is None:
            raise
        locked_task = db.get(QueryTask, task.id)
        if locked_task is not None:
            _mark_task_success_if_needed(
                db,
                locked_task,
                platform_answer=platform_answer,
                snapshot=snapshot,
            )
            db.commit()
        created = False

    _refresh_provider_batch_after_task(db, locked_task)
    _after_task_terminal(db, snapshot.run_id)
    outcome = "processed" if created else "duplicate"
    logger.info(
        "molizhishu callback %s task_id=%s subtask_id=%s query_task_id=%s",
        outcome,
        provider_task_id,
        provider_subtask_id,
        locked_task.id,
    )
    return MolizhishuCallbackResult(outcome=outcome, task_id=locked_task.id)


def handle_molizhishu_callback(
    db: Session,
    payload: dict[str, Any],
) -> MolizhishuCallbackResult:
    """处理模力指数完成回调，与轮询共用归一化与入库逻辑。"""
    from app.geo_monitoring.adapters.molizhishu import (
        try_parse_molizhishu_batch_callback_payload,
    )

    batch_parsed = try_parse_molizhishu_batch_callback_payload(payload)
    if batch_parsed is not None:
        provider_task_id, subtask_list = batch_parsed
        return _dispatch_molizhishu_batch_callback(
            db,
            payload,
            provider_task_id=provider_task_id,
            subtask_list=subtask_list,
        )
    return _handle_molizhishu_single_subtask_callback(db, payload)


# 将 QueryTask 标记为 cancelled
def _mark_task_cancelled(db: Session, task: QueryTask, now: datetime) -> None:
    task.status = "cancelled"
    task.completed_at = now
    task.finished_at = now


async def _stop_single_molizhishu_provider_task(
    run_id: int,
    task_id: str,
    subtask_ids: list[str | None],
    *,
    adapter: Any,
    credential: Any,
    platform_code: str,
    runtime: CollectionRuntime,
) -> bool:
    for subtask_id in subtask_ids:
        logger.info(
            "molizhishu stop requested run_id=%s task_id=%s subtask_id=%s",
            run_id,
            task_id,
            subtask_id,
        )
    try:
        await adapter.stop_task(task_id, credential=credential)
        await runtime.key_pool.report_success(
            credential.fingerprint, platform_code=platform_code
        )
        return True
    except AdapterError as exc:
        await runtime.key_pool.report_failure(
            credential.fingerprint,
            exc,
            platform_code=platform_code,
        )
        logger.warning(
            "molizhishu stop failed run_id=%s task_id=%s category=%s message=%s",
            run_id,
            task_id,
            exc.category.value,
            exc.sanitized_message(),
        )
        return False


async def _stop_molizhishu_provider_tasks_async(
    run_id: int,
    task_subtasks: dict[str, list[str | None]],
) -> int:
    runtime = get_runtime()
    from app.geo_monitoring.adapters.molizhishu import MolizhishuAdapter

    platform_code = None
    adapter = None
    for registered_code in runtime.adapter_registry.registered_codes():
        candidate = runtime.adapter_registry.get(registered_code)
        if isinstance(candidate, MolizhishuAdapter):
            platform_code = registered_code
            adapter = candidate
            break
    if platform_code is None or adapter is None:
        logger.warning(
            "molizhishu stop skipped run_id=%s: adapter unavailable",
            run_id,
        )
        return 0
    try:
        credential = await runtime.key_pool.acquire(platform_code)
    except NoAvailableCredentialError:
        logger.warning(
            "molizhishu stop skipped run_id=%s: no credential available",
            run_id,
        )
        return 0

    results = await asyncio.gather(
        *[
            _stop_single_molizhishu_provider_task(
                run_id,
                task_id,
                subtask_ids,
                adapter=adapter,
                credential=credential,
                platform_code=platform_code,
                runtime=runtime,
            )
            for task_id, subtask_ids in sorted(task_subtasks.items())
        ]
    )
    return sum(1 for succeeded in results if succeeded)


def collect_molizhishu_provider_stop_targets(
    db: Session, run_id: int
) -> dict[str, list[str | None]]:
    """收集取消前需要 provider stop 的唯一 taskId（仅未终态且已有 provider_task_id）。"""
    from app.geo_monitoring.repositories import runs as run_repo

    run = run_repo.get_by_id(db, run_id)
    if run is None or run.collection_source != "molizhishu":
        return {}

    rows = db.execute(
        select(QueryTask.provider_task_id, QueryTask.provider_subtask_id).where(
            QueryTask.run_id == run_id,
            QueryTask.status.in_(CLAIMABLE_TASK_STATUSES),
            QueryTask.provider_task_id.isnot(None),
            QueryTask.is_deleted.is_(False),
        )
    ).all()

    task_subtasks: dict[str, list[str | None]] = {}
    for task_id, subtask_id in rows:
        if not isinstance(task_id, str) or not task_id.strip():
            continue
        normalized_task_id = task_id.strip()
        task_subtasks.setdefault(normalized_task_id, []).append(subtask_id)
    return task_subtasks


def stop_molizhishu_provider_tasks(
    run_id: int, task_subtasks: dict[str, list[str | None]]
) -> int:
    """对已收集的 taskId 并发调用 provider stop（供后台线程与测试使用）。"""
    if not task_subtasks:
        return 0
    if not _molizhishu_configured(get_runtime().settings):
        logger.warning(
            "molizhishu stop skipped run_id=%s: provider not configured",
            run_id,
        )
        return 0
    return asyncio.run(_stop_molizhishu_provider_tasks_async(run_id, task_subtasks))


def schedule_molizhishu_provider_stop(
    run_id: int, task_subtasks: dict[str, list[str | None]]
) -> bool:
    """后台调度 provider stop，不阻塞取消 API。"""
    import threading

    if not task_subtasks:
        return False
    thread = threading.Thread(
        target=stop_molizhishu_provider_tasks,
        args=(run_id, task_subtasks),
        name=f"molizhishu-stop-run-{run_id}",
        daemon=True,
    )
    thread.start()
    return True


def stop_molizhishu_provider_tasks_for_run(db: Session, run_id: int) -> int:
    """同步收集并 stop（保留给脚本或测试；取消 API 应使用 schedule）。"""
    task_subtasks = collect_molizhishu_provider_stop_targets(db, run_id)
    return stop_molizhishu_provider_tasks(run_id, task_subtasks)


# 加载项目活跃品牌及按品牌分组的启用别名
def _load_project_brands(
    db: Session,
    project_id: int,
) -> tuple[list[Brand], dict[int, list[BrandAlias]]]:
    brands = list(
        db.execute(
            select(Brand).where(
                Brand.project_id == project_id,
                Brand.status == "active",
                Brand.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )
    if not brands:
        return [], {}

    brand_ids = [brand.id for brand in brands]
    aliases = list(
        db.execute(
            select(BrandAlias).where(
                BrandAlias.brand_id.in_(brand_ids),
                BrandAlias.enabled.is_(True),
                BrandAlias.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )
    aliases_by_brand: dict[int, list[BrandAlias]] = {
        brand_id: [] for brand_id in brand_ids
    }
    for alias in aliases:
        aliases_by_brand.setdefault(alias.brand_id, []).append(alias)
    return brands, aliases_by_brand


# 解析平台实际使用的模型名（平台配置或环境变量）
def _resolve_model(runtime_settings: Settings, platform: AIPlatform) -> str:
    if platform.model_name:
        return platform.model_name
    prefix = platform.platform_code.upper()
    return str(getattr(runtime_settings, f"{prefix}_MODEL", "") or "")


# 规范化引用 URL（小写 scheme/host、去除默认端口与 fragment）
def normalize_citation_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if port is not None:
        if (parsed.scheme == "http" and port == 80) or (
            parsed.scheme == "https" and port == 443
        ):
            port = None
    netloc = host if port is None else f"{host}:{port}"
    return urlunparse(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path or "",
            parsed.params,
            parsed.query,
            "",
        )
    )


# 从 URL 提取小写域名
def extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).hostname
    return host.lower() if host else None


# 将 datetime 统一转为 UTC  aware
def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
