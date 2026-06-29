"""采集队列编排与 QueryTask 执行服务。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings as default_settings
from app.core.database import SessionLocal
from app.geo_monitoring.adapters.base import PlatformAnswer, PlatformQuery
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory, is_retryable
from app.geo_monitoring.adapters.key_pool import (
    ApiKeyCredential,
    CredentialKeyPool,
    YuanbaoCredential,
)
from app.geo_monitoring.adapters.registry import (
    AdapterRegistry,
    _molizhishu_configured,
    build_adapter_registry,
)
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    AnswerBrandResult,
    AnswerCitation,
    Brand,
    BrandAlias,
    MonitorRun,
    Prompt,
    QueryTask,
)
from app.geo_monitoring.repositories import answers as answer_repo
from app.geo_monitoring.services.brand_matcher import match_brands_in_text, normalize_answer_text
from app.geo_monitoring.services.platforms import AIDSO_PLATFORM_MAPPINGS, MOLIZHISHU_PLATFORM_MAPPINGS

logger = logging.getLogger(__name__)

TERMINAL_TASK_STATUSES = frozenset({"success", "failed", "cancelled"})
CLAIMABLE_TASK_STATUSES = frozenset({"pending", "queued", "running"})
_KEY_POOL_REDIS_UNSET = object()


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
    aidso_thinking_enabled: bool
    request_json: dict[str, Any] | None
    reclaim: bool


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
    runtime_settings = runtime_settings or default_settings
    registry = adapter_registry or build_adapter_registry(runtime_settings)
    pool = key_pool or build_credential_key_pool(runtime_settings)
    return CollectionRuntime(
        session_factory=session_factory or SessionLocal,
        settings=runtime_settings,
        adapter_registry=registry,
        key_pool=pool,
    )


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
    _register_api_keys(pool, runtime_settings, "doubao", runtime_settings.DOUBAO_API_KEYS)
    _register_api_keys(pool, runtime_settings, "qwen", runtime_settings.QWEN_API_KEYS)
    _register_api_keys(pool, runtime_settings, "deepseek", runtime_settings.DEEPSEEK_API_KEYS)
    _register_api_keys(pool, runtime_settings, "kimi", runtime_settings.KIMI_API_KEYS)
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
    aidso_token = runtime_settings.AIDSO_API_TOKEN.strip()
    if aidso_token:
        for platform_code in AIDSO_PLATFORM_MAPPINGS:
            pool.register_platform_credentials(
                platform_code,
                [ApiKeyCredential(platform_code=platform_code, api_key=aidso_token)],
            )
    molizhishu_token = runtime_settings.MOLIZHISHU_API_TOKEN.strip()
    if _molizhishu_configured(runtime_settings) and molizhishu_token:
        for platform_code in MOLIZHISHU_PLATFORM_MAPPINGS:
            pool.register_platform_credentials(
                platform_code,
                [ApiKeyCredential(platform_code=platform_code, api_key=molizhishu_token)],
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


def enqueue_run_query_tasks(run_id: int, *, db: Session | None = None) -> int:
    """运行事务提交后，将 pending 任务标记为 queued 并逐个入队。"""
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
        # 批量标记 queued 并收集待入队 ID
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


# QueryTask 终态后回调刷新 Run 聚合状态
def _after_task_terminal(db: Session, run_id: int) -> None:
    from app.geo_monitoring.services.runs import on_query_task_terminal

    on_query_task_terminal(db, run_id)


# 执行单个 QueryTask：认领、调用平台、持久化或处理失败
async def execute_query_task(task_id: int) -> bool:
    runtime = get_runtime()
    snapshot = _claim_task_for_execution(runtime, task_id)
    if snapshot is None:
        return False

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

    _persist_success(runtime, snapshot, platform_answer)
    return False


# 加锁认领 QueryTask 并构建执行快照，不可执行时返回 None
def _claim_task_for_execution(
    runtime: CollectionRuntime,
    task_id: int,
) -> TaskSnapshot | None:
    now = datetime.now(timezone.utc)
    db = runtime.session_factory()
    try:
        task = (
            db.execute(
                select(QueryTask)
                .where(QueryTask.id == task_id, QueryTask.is_deleted.is_(False))
                .with_for_update()
            )
            .scalar_one_or_none()
        )
        if task is None:
            return None

        if task.status in TERMINAL_TASK_STATUSES:
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

        if not reclaim and not _is_aidso_pending_poll(task):
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
            aidso_thinking_enabled=_resolve_aidso_thinking_enabled(
                run, task.platform_code
            ),
            request_json=task.request_json,
            reclaim=reclaim,
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
        metadata={
            **(snapshot.request_json or {}),
            "collection_source": snapshot.collection_source,
            "aidso_thinking_enabled": snapshot.aidso_thinking_enabled,
        },
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
    now = datetime.now(timezone.utc)
    normalized_text = normalize_answer_text(platform_answer.text)
    db = runtime.session_factory()
    try:
        task = db.get(QueryTask, snapshot.task_id)
        if task is None or task.status != "running":
            return

        existing = answer_repo.get_by_task_id(db, task.id)
        if existing is not None:
            task.status = "success"
            task.completed_at = now
            task.finished_at = now
            db.commit()
            _after_task_terminal(db, task.run_id)
            return

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

        # 写入引用列表
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

        # 匹配品牌提及并写入结果
        brands, aliases_by_brand = _load_project_brands(db, snapshot.project_id)
        for match in match_brands_in_text(normalized_text, brands, aliases_by_brand):
            answer_repo.add_brand_result(
                db,
                AnswerBrandResult(
                    answer_id=answer.id,
                    brand_id=match.brand_id,
                    is_mentioned=match.is_mentioned,
                    mention_count=match.mention_count,
                    first_position=match.first_position,
                    context_json=match.context_json,
                ),
            )

        task.status = "success"
        task.latency_ms = platform_answer.latency_ms
        task.provider_request_id = platform_answer.provider_request_id
        task.response_http_status = 200
        task.completed_at = now
        task.finished_at = now
        task.last_error_code = None
        task.last_error_message = None
        db.commit()
        _after_task_terminal(db, snapshot.run_id)
    finally:
        db.close()


def _handle_adapter_failure(
    runtime: CollectionRuntime,
    task_id: int,
    error: AdapterError,
) -> bool:
    """记录失败并在可重试时返回 True，由调用方在 asyncio.run 结束后入队。"""
    now = datetime.now(timezone.utc)
    db = runtime.session_factory()
    should_retry = False
    try:
        task = db.get(QueryTask, task_id)
        if task is None or task.status not in {"running", "queued", "pending"}:
            return False

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
            should_retry = True
            db.commit()
            return should_retry

        if error.category == ErrorCategory.CANCELLED:
            _mark_task_cancelled(db, task, now)
        else:
            _mark_task_failed(
                db,
                task,
                now,
                error_code=error.category.value,
                error_message=error.sanitized_message(),
            )
        run_id = task.run_id
        db.commit()
        _after_task_terminal(db, run_id)
        return False
    finally:
        db.close()


def _is_aidso_pending_poll(task: QueryTask) -> bool:
    request_json = task.request_json or {}
    return (
        task.platform_code in AIDSO_PLATFORM_MAPPINGS
        and task.last_error_code == ErrorCategory.PENDING.value
        and isinstance(request_json.get("aidso_req_id"), str)
        and bool(request_json.get("aidso_req_id", "").strip())
    )


def _should_retry_task(
    runtime: CollectionRuntime,
    task: QueryTask,
    error: AdapterError,
    pending_poll_count: int | None,
) -> bool:
    if not is_retryable(error.category):
        return False
    if error.category == ErrorCategory.PENDING:
        return (pending_poll_count or 0) < runtime.settings.COLLECTION_AIDSO_MAX_POLLS
    return task.attempt_count < task.max_attempts


def _persist_pending_metadata(task: QueryTask, error: AdapterError) -> int | None:
    pending_metadata = getattr(error, "pending_metadata", None)
    if not isinstance(pending_metadata, dict):
        return None
    request_json = dict(task.request_json or {})
    request_json.update(pending_metadata)
    poll_count = None
    if error.category == ErrorCategory.PENDING:
        poll_count = int(request_json.get("aidso_poll_count") or 0) + 1
        request_json["aidso_poll_count"] = poll_count
    task.request_json = request_json
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
) -> None:
    task.status = "failed"
    task.error_code = error_code
    task.error_message = error_message
    task.last_error_code = error_code
    task.last_error_message = error_message
    task.completed_at = now
    task.finished_at = now


# 将 QueryTask 标记为 cancelled
def _mark_task_cancelled(db: Session, task: QueryTask, now: datetime) -> None:
    task.status = "cancelled"
    task.completed_at = now
    task.finished_at = now


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
    aliases_by_brand: dict[int, list[BrandAlias]] = {brand_id: [] for brand_id in brand_ids}
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
