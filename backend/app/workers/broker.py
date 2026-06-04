"""Dramatiq broker 配置。

技术选型（见 docs/decisions.md 003 + 本任务说明）：
- Broker 采用 **Redis**（不引入 RabbitMQ），与 docs/decisions.md 一致。
- MQ 框架采用 **Dramatiq**（而非 Celery）：Redis 原生、无需独立 result backend、
  API 简洁；且开发/部署含 Windows 环境，Celery 的 prefork 进程池在 Windows 上
  不可用，而 Dramatiq 的多线程 Worker 在 Windows 原生可用，是「当前依赖更简单
  且可跑」的一种。

broker 选择由 ``settings.DRAMATIQ_BROKER`` 决定：
- ``redis``（默认）：连接 ``settings.REDIS_URL``。RedisBroker 初始化为惰性连接，
  仅在真正发送 / 消费消息时才建立连接，因此「导入本模块」不要求 Redis 在线。
- ``stub``：使用内存 StubBroker，供单元测试 / 无 Redis 环境使用。

中间件：启用 Dramatiq 自带 ``Retries``，配合 actor 的 ``max_retries`` 实现
失败重试的基础结构（见任务要求 15）。
"""

from __future__ import annotations

import dramatiq
from dramatiq.brokers.stub import StubBroker
from dramatiq.middleware import CurrentMessage

from app.core.config import settings


def _build_broker() -> dramatiq.Broker:
    if settings.DRAMATIQ_BROKER == "stub":
        return StubBroker()

    # 延迟到此处导入，避免无 redis 依赖的纯 stub 场景报错
    from dramatiq.brokers.redis import RedisBroker

    return RedisBroker(url=settings.REDIS_URL)


broker: dramatiq.Broker = _build_broker()
# 启用 CurrentMessage 中间件：actor 内可读取当前消息的 retries 计数，
# 用于「仅在最后一次重试用尽时标记 article 失败」的精确控制。
broker.add_middleware(CurrentMessage())
dramatiq.set_broker(broker)
