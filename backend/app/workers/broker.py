"""通用 Dramatiq broker 配置。"""

from __future__ import annotations

import dramatiq
from dramatiq.brokers.stub import StubBroker

from app.core.config import settings


def _build_broker() -> dramatiq.Broker:
    if settings.DRAMATIQ_BROKER == "stub":
        return StubBroker()

    from dramatiq.brokers.redis import RedisBroker

    return RedisBroker(url=settings.REDIS_URL)


broker: dramatiq.Broker = _build_broker()
dramatiq.set_broker(broker)
