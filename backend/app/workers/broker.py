"""通用 Dramatiq broker 配置。"""

from __future__ import annotations

import dramatiq
from dramatiq.brokers.stub import StubBroker

from app.core.config import settings


# 根据配置构建 Dramatiq 消息代理并设为全局实例。
def _build_broker() -> dramatiq.Broker:
    if settings.DRAMATIQ_BROKER == "stub":
        return StubBroker()

    from dramatiq.brokers.redis import RedisBroker

    return RedisBroker(url=settings.REDIS_URL)


broker: dramatiq.Broker = _build_broker()
dramatiq.set_broker(broker)
