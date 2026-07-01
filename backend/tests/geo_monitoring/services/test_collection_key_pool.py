"""CredentialKeyPool wiring tests for collection service."""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import Settings
from app.geo_monitoring.adapters.errors import NoAvailableCredentialError
from app.geo_monitoring.services import collection as collection_service
from app.geo_monitoring.services.platforms import MOLIZHISHU_PLATFORM_MAPPINGS


def test_build_credential_key_pool_wires_redis_when_dramatiq_broker_is_redis(monkeypatch):
    created: list[tuple[str, dict]] = []

    class FakeRedisClient:
        pass

    def fake_from_url(url: str, **kwargs):
        created.append((url, kwargs))
        return FakeRedisClient()

    monkeypatch.setattr("redis.Redis.from_url", fake_from_url)

    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://:secret@redis.example.test:6379/0",
        DRAMATIQ_BROKER="redis",
        NACOS_ENABLED=False,
    )

    pool = collection_service.build_credential_key_pool(settings)

    assert pool._redis is not None
    assert isinstance(pool._redis, FakeRedisClient)
    assert created == [
        (
            "redis://:secret@redis.example.test:6379/0",
            {
                "decode_responses": True,
                "socket_connect_timeout": 2,
                "socket_timeout": 2,
            },
        )
    ]


def test_build_credential_key_pool_skips_redis_when_dramatiq_broker_is_stub(monkeypatch):
    def fail_from_url(*_args, **_kwargs):
        raise AssertionError("Redis.from_url should not be called for stub broker")

    monkeypatch.setattr("redis.Redis.from_url", fail_from_url)

    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="stub",
        NACOS_ENABLED=False,
    )

    pool = collection_service.build_credential_key_pool(settings)

    assert pool._redis is None


def test_build_credential_key_pool_honors_explicit_redis_client_override():
    sentinel = object()
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="redis",
        NACOS_ENABLED=False,
    )

    pool = collection_service.build_credential_key_pool(settings, redis_client=sentinel)

    assert pool._redis is sentinel


def test_build_credential_key_pool_registers_molizhishu_token_for_all_platforms():
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="stub",
        NACOS_ENABLED=False,
        MOLIZHISHU_ENABLED=True,
        MOLIZHISHU_API_TOKEN="molizhishu-token",
    )

    pool = collection_service.build_credential_key_pool(settings, redis_client=None)

    for platform_code in MOLIZHISHU_PLATFORM_MAPPINGS:
        credential = asyncio.run(pool.acquire(platform_code))
        assert credential.api_key == "molizhishu-token"
        assert credential.platform_code == platform_code


def test_build_credential_key_pool_registers_molizhishu_token_for_db_platform_codes():
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="stub",
        NACOS_ENABLED=False,
        MOLIZHISHU_ENABLED=True,
        MOLIZHISHU_API_TOKEN="molizhishu-token",
    )

    pool = collection_service.build_credential_key_pool(
        settings,
        redis_client=None,
        molizhishu_platform_codes=["molizhishu_custom_web"],
    )

    credential = asyncio.run(pool.acquire("molizhishu_custom_web"))
    assert credential.api_key == "molizhishu-token"
    assert credential.platform_code == "molizhishu_custom_web"


def test_build_credential_key_pool_skips_molizhishu_when_disabled_even_with_token():
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="stub",
        NACOS_ENABLED=False,
        MOLIZHISHU_ENABLED=False,
        MOLIZHISHU_API_TOKEN="molizhishu-token",
    )

    pool = collection_service.build_credential_key_pool(settings, redis_client=None)

    with pytest.raises(NoAvailableCredentialError):
        asyncio.run(pool.acquire("molizhishu_doubao_web"))
