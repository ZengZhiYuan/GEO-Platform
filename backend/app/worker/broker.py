"""Dramatiq broker 配置。"""

from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker

from app.core.config import settings


# 根据配置创建 Dramatiq 消息代理（Redis 或内存 Stub）。
def create_broker() -> dramatiq.Broker:
    if settings.DRAMATIQ_BROKER == "stub":
        broker = StubBroker()
        broker.emit_after("process_boot")
        return broker
    return RedisBroker(url=settings.REDIS_URL)


broker = create_broker()
dramatiq.set_broker(broker)
