"""Redis 密钥池测试。"""

from __future__ import annotations

import asyncio
import logging

import pytest
from freezegun import freeze_time

from app.geo_monitoring.adapters.errors import (
    AdapterError,
    ErrorCategory,
    NoAvailableCredentialError,
)
from app.geo_monitoring.adapters.key_pool import (
    ApiKeyCredential,
    CredentialKeyPool,
    CredentialState,
)


def _credentials() -> list[ApiKeyCredential]:
    return [
        ApiKeyCredential(platform_code="qwen", api_key="key-alpha"),
        ApiKeyCredential(platform_code="qwen", api_key="key-beta"),
        ApiKeyCredential(platform_code="qwen", api_key="key-gamma"),
    ]


def test_acquire_rotates_credentials_in_stable_order(fake_redis):
    async def _run() -> None:
        pool = CredentialKeyPool(fake_redis, key_prefix="test:cred")
        pool.register_platform_credentials("qwen", _credentials())

        first = await pool.acquire("qwen")
        second = await pool.acquire("qwen")
        third = await pool.acquire("qwen")
        fourth = await pool.acquire("qwen")

        assert first.fingerprint != second.fingerprint
        assert {first.fingerprint, second.fingerprint, third.fingerprint} == {
            item.fingerprint for item in _credentials()
        }
        assert first.fingerprint == fourth.fingerprint

    asyncio.run(_run())


def test_cooling_credential_is_skipped(fake_redis):
    async def _run() -> None:
        pool = CredentialKeyPool(fake_redis, key_prefix="test:cred")
        credentials = _credentials()
        pool.register_platform_credentials("qwen", credentials)

        with freeze_time("2026-06-17 10:00:00"):
            await pool.report_failure(
                credentials[0].fingerprint,
                AdapterError(
                    "rate limited",
                    category=ErrorCategory.RATE_LIMITED,
                    retry_after_seconds=60,
                ),
                platform_code="qwen",
                request_id="req-1",
            )
            selected = await pool.acquire("qwen")
            assert selected.fingerprint != credentials[0].fingerprint

    asyncio.run(_run())


def test_disabled_credential_is_skipped(fake_redis):
    async def _run() -> None:
        pool = CredentialKeyPool(fake_redis, key_prefix="test:cred")
        credentials = _credentials()
        pool.register_platform_credentials("qwen", credentials)

        await pool.report_failure(
            credentials[0].fingerprint,
            AdapterError("unauthorized", category=ErrorCategory.UNAUTHORIZED),
            platform_code="qwen",
            request_id="req-1",
        )
        await pool.report_failure(
            credentials[1].fingerprint,
            AdapterError("forbidden", category=ErrorCategory.UNAUTHORIZED),
            platform_code="qwen",
            request_id="req-2",
        )

        selected = await pool.acquire("qwen")
        assert selected.fingerprint == credentials[2].fingerprint

    asyncio.run(_run())


def test_all_credentials_unavailable_raises(fake_redis):
    async def _run() -> None:
        pool = CredentialKeyPool(fake_redis, key_prefix="test:cred")
        credentials = _credentials()
        pool.register_platform_credentials("qwen", credentials)

        for credential in credentials:
            await pool.report_failure(
                credential.fingerprint,
                AdapterError("unauthorized", category=ErrorCategory.UNAUTHORIZED),
                platform_code="qwen",
                request_id="req-x",
            )

        with pytest.raises(NoAvailableCredentialError):
            await pool.acquire("qwen", request_id="req-final")

    asyncio.run(_run())


def test_redis_state_never_contains_plaintext_secret(fake_redis):
    async def _run() -> None:
        pool = CredentialKeyPool(fake_redis, key_prefix="test:cred")
        credentials = _credentials()
        pool.register_platform_credentials("qwen", credentials)

        await pool.acquire("qwen")

        serialized = str(fake_redis._strings) + str(fake_redis._hashes)
        for credential in credentials:
            assert credential.api_key not in serialized

    asyncio.run(_run())


def test_redis_unavailable_falls_back_to_in_memory_rotation(fake_redis, caplog):
    async def _run() -> None:
        pool = CredentialKeyPool(fake_redis, key_prefix="test:cred")
        pool.register_platform_credentials("qwen", _credentials())

        await pool.acquire("qwen")
        fake_redis.available = False

        with caplog.at_level(logging.WARNING, logger="app.geo_monitoring.adapters"):
            first = await pool.acquire("qwen")
            second = await pool.acquire("qwen")

        assert first.fingerprint != second.fingerprint
        warning_messages = [record.getMessage() for record in caplog.records]
        assert any("redis unavailable" in message.lower() for message in warning_messages)
        assert sum("redis unavailable" in message.lower() for message in warning_messages) == 1

    asyncio.run(_run())


def test_server_error_keeps_credential_available(fake_redis):
    async def _run() -> None:
        pool = CredentialKeyPool(fake_redis, key_prefix="test:cred")
        credentials = _credentials()
        pool.register_platform_credentials("qwen", credentials)

        await pool.report_failure(
            credentials[0].fingerprint,
            AdapterError("upstream failed", category=ErrorCategory.SERVER_ERROR),
            platform_code="qwen",
            request_id="req-1",
        )

        state = pool.get_credential_state("qwen", credentials[0].fingerprint)
        assert state == CredentialState.HEALTHY

    asyncio.run(_run())
