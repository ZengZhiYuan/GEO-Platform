"""采集 QueryTask 的 Dramatiq Actor。"""

from __future__ import annotations

import asyncio

import dramatiq

from app.geo_monitoring.services import collection as collection_service
from app.worker import broker as _broker  # noqa: F401


# 消费采集队列消息，执行单条 QueryTask 并在需要时重新入队。
@dramatiq.actor(queue_name="collection", max_retries=0)
def collect_query_task(task_id: int) -> None:
    """消费仅含 task_id 的消息，执行单条 QueryTask 采集。"""
    should_retry = asyncio.run(collection_service.execute_query_task(task_id))
    if should_retry:
        collect_query_task.send(task_id)
