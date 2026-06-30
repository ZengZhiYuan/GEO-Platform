"""采集 QueryTask 与 ProviderBatch 的 Dramatiq Actor。"""

from __future__ import annotations

import asyncio

import dramatiq

from app.geo_monitoring.services import collection as collection_service
from app.worker import broker as _broker  # noqa: F401


# 消费采集队列消息，执行单条 QueryTask 并在需要时重新入队。
@dramatiq.actor(queue_name="collection", max_retries=0)
def collect_query_task(task_id: int) -> None:
    """消费仅含 task_id 的消息，执行单条 QueryTask 采集。"""
    result = asyncio.run(collection_service.execute_query_task(task_id))
    if result.should_retry:
        runtime_settings = collection_service.get_runtime().settings
        delay_seconds = (
            result.retry_delay_seconds or runtime_settings.COLLECTION_RETRY_BASE_SECONDS
        )
        collect_query_task.send_with_options(
            args=(task_id,),
            delay=delay_seconds * 1000,
        )


@dramatiq.actor(queue_name="collection", max_retries=0)
def collect_provider_batch(batch_id: int) -> None:
    """消费 provider batch 消息，合并提交并轮询回填 QueryTask。"""
    result = asyncio.run(collection_service.execute_provider_batch(batch_id))
    if result.should_retry:
        runtime_settings = collection_service.get_runtime().settings
        delay_seconds = (
            result.retry_delay_seconds
            or runtime_settings.COLLECTION_MOLIZHISHU_POLL_DELAY_SECONDS
        )
        collect_provider_batch.send_with_options(
            args=(batch_id,),
            delay=delay_seconds * 1000,
        )
