"""Readiness probes for infrastructure dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import Engine, text

from app.core.config import _url_target_summary, settings


def check_database_ready(
    *,
    engine: Engine,
    database_url: str | None = None,
) -> dict[str, Any]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {
        "ok": True,
        "target": _url_target_summary(database_url or settings.DATABASE_URL),
    }


def check_redis_ready(
    *,
    redis_url: str | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    url = redis_url or settings.REDIS_URL
    if client_factory is None:
        from redis import Redis

        client_factory = Redis.from_url

    client = client_factory(url, socket_connect_timeout=2, socket_timeout=2)
    try:
        client.ping()
    finally:
        client.close()

    return {"ok": True, "target": _url_target_summary(url)}


def check_nacos_ready(
    *,
    enabled: bool | None = None,
    server_addresses: str | None = None,
    client_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    is_enabled = settings.NACOS_ENABLED if enabled is None else enabled
    addresses = (
        settings.NACOS_SERVER_ADDRESSES if server_addresses is None else server_addresses
    )
    if not is_enabled:
        return {"ok": True, "enabled": False, "target": None}

    if client_factory is None:
        raise RuntimeError("Nacos readiness requires an explicit client_factory")

    client = client_factory()
    if hasattr(client, "is_ready"):
        client.is_ready()
    return {"ok": True, "enabled": True, "target": addresses}


def check_readiness() -> dict[str, Any]:
    from app.core.database import engine

    database = check_database_ready(engine=engine)
    redis = check_redis_ready()
    return {
        "status": "ready" if database["ok"] and redis["ok"] else "not_ready",
        "database": database,
        "redis": redis,
    }
