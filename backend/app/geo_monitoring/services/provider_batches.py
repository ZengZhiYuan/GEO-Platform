"""模力指数 ProviderBatch 规划与 run 级拆批。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings as default_settings
from app.geo_monitoring.models import MonitorRun, ProviderBatch, QueryTask
from app.geo_monitoring.repositories import provider_batches as batch_repo
from app.geo_monitoring.services.platforms import MOLIZHISHU_PLATFORM_MAPPINGS

MAX_PROVIDER_BATCH_SUBTASKS = 100


@dataclass(frozen=True)
class ProviderBatchItem:
    """单条 prompt×platform 子任务，用于拆批与提交映射。"""

    query_task_id: int
    prompt_id: int
    platform_code: str
    prompt_text: str
    molizhishu_platform: str
    mode: str
    screenshot: int


def max_subtasks_per_batch(runtime_settings: Settings | None = None) -> int:
    runtime_settings = runtime_settings or default_settings
    configured = runtime_settings.MOLIZHISHU_PROVIDER_BATCH_MAX_SUBTASKS
    if configured <= 0:
        return MAX_PROVIDER_BATCH_SUBTASKS
    return configured


def provider_batch_enabled(
    collection_source: str,
    *,
    runtime_settings: Settings | None = None,
) -> bool:
    runtime_settings = runtime_settings or default_settings
    if collection_source != "molizhishu":
        return False
    return runtime_settings.MOLIZHISHU_PROVIDER_BATCH_ENABLED


def plan_provider_batch_chunks(
    items: list[ProviderBatchItem],
    *,
    max_subtasks: int | None = None,
    runtime_settings: Settings | None = None,
) -> list[list[ProviderBatchItem]]:
    """按 prompts×platforms 顺序拆批，每批不超过 max_subtasks。"""
    if not items:
        return []
    limit = max_subtasks or max_subtasks_per_batch(runtime_settings)
    return [items[index : index + limit] for index in range(0, len(items), limit)]


def build_submit_indexes(
    items: list[ProviderBatchItem],
) -> tuple[list[str], list[dict[str, Any]], list[tuple[int, int]]]:
    """构建提交 payload 的 prompts/platforms 与各 item 的 (prompt_idx, platform_idx)。

    prompt 索引按本地 prompt_id 区分，避免重复 prompt 文本导致 subTask 数量不一致。
    """
    prompt_order: list[str] = []
    prompt_index_by_id: dict[int, int] = {}
    platform_order: list[dict[str, Any]] = []
    platform_index_by_key: dict[tuple[str, str, int], int] = {}
    item_indexes: list[tuple[int, int]] = []

    for item in items:
        if item.prompt_id not in prompt_index_by_id:
            prompt_index_by_id[item.prompt_id] = len(prompt_order)
            prompt_order.append(item.prompt_text.strip())
        prompt_idx = prompt_index_by_id[item.prompt_id]

        platform_key = (item.molizhishu_platform, item.mode, item.screenshot)
        if platform_key not in platform_index_by_key:
            platform_index_by_key[platform_key] = len(platform_order)
            platform_order.append(
                {
                    "platform": item.molizhishu_platform,
                    "mode": item.mode,
                    "screenshot": item.screenshot,
                }
            )
        platform_idx = platform_index_by_key[platform_key]
        item_indexes.append((prompt_idx, platform_idx))

    return prompt_order, platform_order, item_indexes


def map_subtasks_to_items(
    subtask_list: list[dict[str, Any]],
    items: list[ProviderBatchItem],
    item_indexes: list[tuple[int, int]],
) -> dict[int, str]:
    """将 provider subTaskList 映射为 query_task_id -> subTaskId。"""
    if len(subtask_list) != len(items):
        raise ValueError(
            f"subTaskList size mismatch: expected {len(items)}, got {len(subtask_list)}"
        )

    prompt_order, platform_order, _ = build_submit_indexes(items)
    by_prompt_platform: dict[tuple[str, str], str] = {}
    by_cartesian_index: dict[int, str] = {}

    for index, subtask in enumerate(subtask_list):
        subtask_id = subtask.get("subTaskId")
        if not isinstance(subtask_id, str) or not subtask_id.strip():
            raise ValueError("subTaskList entry missing subTaskId")
        normalized_id = subtask_id.strip()
        by_cartesian_index[index] = normalized_id

        prompt_value = subtask.get("prompt")
        platform_value = subtask.get("platform")
        if isinstance(prompt_value, str) and isinstance(platform_value, str):
            by_prompt_platform[(prompt_value.strip(), platform_value.strip())] = (
                normalized_id
            )

    mapping: dict[int, str] = {}
    num_platforms = len(platform_order)
    for item, (prompt_idx, platform_idx) in zip(items, item_indexes, strict=True):
        platform_code = platform_order[platform_idx]["platform"]
        matched: str | None = None

        prompt_id_value = None
        for subtask in subtask_list:
            if not isinstance(subtask, dict):
                continue
            subtask_prompt_id = subtask.get("promptId")
            if subtask_prompt_id is None:
                subtask_prompt_id = subtask.get("prompt_id")
            subtask_platform = subtask.get("platform")
            subtask_id = subtask.get("subTaskId")
            if (
                subtask_prompt_id is not None
                and str(subtask_prompt_id) == str(item.prompt_id)
                and isinstance(subtask_platform, str)
                and subtask_platform.strip() == platform_code
                and isinstance(subtask_id, str)
                and subtask_id.strip()
            ):
                matched = subtask_id.strip()
                break

        if matched is None:
            prompt_text = prompt_order[prompt_idx]
            matched = by_prompt_platform.get((prompt_text, platform_code))

        if matched is None:
            cartesian_index = prompt_idx * num_platforms + platform_idx
            matched = by_cartesian_index.get(cartesian_index)

        if matched is None:
            raise ValueError(
                f"unable to map subTask for query_task_id={item.query_task_id}"
            )
        mapping[item.query_task_id] = matched
    return mapping


def _resolve_mode(run: MonitorRun, platform_code: str) -> str:
    configured = (run.provider_mode_by_platform or {}).get(platform_code)
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    mapping = MOLIZHISHU_PLATFORM_MAPPINGS.get(platform_code)
    if mapping:
        return str(mapping["default_mode"])
    return "search"


def _resolve_molizhishu_platform(platform_code: str) -> str:
    mapping = MOLIZHISHU_PLATFORM_MAPPINGS.get(platform_code)
    if mapping is None:
        raise ValueError(f"unsupported molizhishu platform_code: {platform_code}")
    return str(mapping["molizhishu_platform"])


def build_batch_items_for_run(db: Session, run: MonitorRun) -> list[ProviderBatchItem]:
    tasks = list(
        db.execute(
            select(QueryTask)
            .where(
                QueryTask.run_id == run.id,
                QueryTask.is_deleted.is_(False),
            )
            .order_by(QueryTask.prompt_id, QueryTask.platform_code, QueryTask.id)
        )
        .scalars()
        .all()
    )
    items: list[ProviderBatchItem] = []
    for task in tasks:
        request_json = task.request_json or {}
        prompt_text = str(request_json.get("prompt_text") or "").strip()
        if not prompt_text:
            raise ValueError(f"query task {task.id} missing prompt_text")
        items.append(
            ProviderBatchItem(
                query_task_id=task.id,
                prompt_id=task.prompt_id,
                platform_code=task.platform_code,
                prompt_text=prompt_text,
                molizhishu_platform=_resolve_molizhishu_platform(task.platform_code),
                mode=_resolve_mode(run, task.platform_code),
                screenshot=run.provider_screenshot,
            )
        )
    return items


def create_provider_batches_for_run(
    db: Session,
    run: MonitorRun,
    *,
    runtime_settings: Settings | None = None,
) -> list[ProviderBatch]:
    """为 molizhishu run 创建 ProviderBatch 并关联 QueryTask。"""
    if not provider_batch_enabled(run.collection_source, runtime_settings=runtime_settings):
        return []

    from app.core.exceptions import BusinessException
    from app.geo_monitoring.adapters.registry import (
        RUNTIME_ADAPTER_MISMATCH_CODE,
        _molizhishu_configured,
    )
    from app.geo_monitoring.services.collection import get_runtime

    resolved_settings = runtime_settings or get_runtime().settings
    if not _molizhishu_configured(resolved_settings):
        raise BusinessException(
            message=(
                "模力指数采集运行时未就绪：请设置 MOLIZHISHU_ENABLED=true 并配置 "
                "MOLIZHISHU_API_TOKEN"
            ),
            code=RUNTIME_ADAPTER_MISMATCH_CODE,
            status_code=409,
        )

    items = build_batch_items_for_run(db, run)
    chunks = plan_provider_batch_chunks(
        items,
        runtime_settings=runtime_settings,
    )
    batches: list[ProviderBatch] = []
    for batch_no, chunk in enumerate(chunks, start=1):
        batch = ProviderBatch(
            run_id=run.id,
            provider_name="molizhishu",
            batch_no=batch_no,
            status="pending",
            total_items=len(chunk),
            completed_items=0,
            failed_items=0,
        )
        batch_repo.add_batch(db, batch)
        db.flush()
        for item in chunk:
            task = db.get(QueryTask, item.query_task_id)
            if task is None:
                continue
            task.provider_batch_id = batch.id
            request_json = dict(task.request_json or {})
            request_json["provider_batch_id"] = batch.id
            request_json["provider_batch_no"] = batch_no
            task.request_json = request_json
        batches.append(batch)
    return batches


def refresh_batch_counters(db: Session, batch: ProviderBatch) -> ProviderBatch:
    """根据关联 QueryTask 终态刷新 batch 计数与状态。"""
    tasks = batch_repo.list_tasks_for_batch(db, batch.id)
    completed = sum(1 for task in tasks if task.status == "success")
    failed = sum(1 for task in tasks if task.status == "failed")
    cancelled = sum(1 for task in tasks if task.status == "cancelled")
    batch.completed_items = completed
    batch.failed_items = failed + cancelled
    terminal = completed + failed + cancelled
    if terminal < batch.total_items:
        if batch.provider_task_id and batch.status in {"pending", "submitted"}:
            batch.status = "processing"
        return batch

    if completed == batch.total_items:
        batch.status = "completed"
    elif completed == 0 and failed + cancelled == batch.total_items:
        batch.status = "failed"
    else:
        batch.status = "partial_completed"
    return batch


def prepare_provider_batch_retry(db: Session, batch: ProviderBatch) -> None:
    """重试单个 batch：保留已成功 QueryTask，重置其余子任务与 batch 提交状态。"""
    tasks = batch_repo.list_tasks_for_batch(db, batch.id)
    for task in tasks:
        if task.status == "success":
            continue
        task.status = "queued"
        task.started_at = None
        task.completed_at = None
        task.finished_at = None
        task.error_code = None
        task.error_message = None
        task.last_error_code = None
        task.last_error_message = None
        task.provider_task_id = None
        task.provider_subtask_id = None
        task.provider_status = None
        task.provider_result_json = None
        task.provider_error_message = None
        request_json = dict(task.request_json or {})
        for key in (
            "molizhishu_task_id",
            "molizhishu_subtask_id",
            "molizhishu_status",
            "molizhishu_poll_count",
        ):
            request_json.pop(key, None)
        task.request_json = request_json

    batch.status = "pending"
    batch.provider_task_id = None
    batch.submitted_at = None
    batch.completed_at = None
    batch.raw_submit_json = None
    batch.raw_status_json = None
    batch.raw_result_json = None
    batch.error_message = None
    refresh_batch_counters(db, batch)


def batch_idempotency_key(run_id: int, batch_no: int) -> str:
    source = f"molizhishu-batch:{run_id}:{batch_no}"
    return sha256(source.encode("utf-8")).hexdigest()
