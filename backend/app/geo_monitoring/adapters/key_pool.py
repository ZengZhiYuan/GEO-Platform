"""Redis 密钥池与进程内降级。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from app.geo_monitoring.adapters.base import PlatformCredential, compute_credential_fingerprint
from app.geo_monitoring.adapters.errors import (
    AdapterError,
    ErrorCategory,
    NoAvailableCredentialError,
    log_adapter_event,
)

logger = logging.getLogger("app.geo_monitoring.adapters")


class CredentialState(StrEnum):
    HEALTHY = "healthy"
    COOLING = "cooling"
    DISABLED = "disabled"


class RedisClient(Protocol):
    def incr(self, key: str) -> int: ...

    def hset(self, name: str, mapping: dict[str, Any] | None = None, **kwargs: Any) -> int: ...

    def hgetall(self, name: str) -> dict[str, str]: ...

    def expire(self, name: str, seconds: int) -> bool: ...


@dataclass(frozen=True)
class ApiKeyCredential:
    platform_code: str
    api_key: str

    @property
    def fingerprint(self) -> str:
        return compute_credential_fingerprint(self.platform_code, self.api_key)

    def to_platform_credential(self) -> PlatformCredential:
        return PlatformCredential(
            platform_code=self.platform_code,
            fingerprint=self.fingerprint,
            api_key=self.api_key,
        )


@dataclass(frozen=True)
class YuanbaoCredential:
    platform_code: str
    secret_id: str
    secret_key: str

    @property
    def fingerprint(self) -> str:
        material = f"{self.secret_id}:{self.secret_key}"
        return compute_credential_fingerprint(self.platform_code, material)

    def to_platform_credential(self) -> PlatformCredential:
        return PlatformCredential(
            platform_code=self.platform_code,
            fingerprint=self.fingerprint,
            secret_id=self.secret_id,
            secret_key=self.secret_key,
        )


CredentialInput = ApiKeyCredential | YuanbaoCredential | PlatformCredential


class CredentialKeyPool:
    def __init__(
        self,
        redis_client: RedisClient | None,
        *,
        key_prefix: str = "geo:cred",
        retry_base_seconds: int = 2,
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix
        self._retry_base_seconds = retry_base_seconds
        self._credentials: dict[str, tuple[PlatformCredential, ...]] = {}
        self._fallback_cursor: dict[str, int] = {}
        self._fallback_state: dict[tuple[str, str], dict[str, str]] = {}
        self._redis_degraded_logged = False

    def register_platform_credentials(
        self,
        platform_code: str,
        credentials: list[CredentialInput],
    ) -> None:
        normalized: list[PlatformCredential] = []
        for item in credentials:
            if isinstance(item, PlatformCredential):
                normalized.append(item)
            elif isinstance(item, ApiKeyCredential):
                normalized.append(item.to_platform_credential())
            elif isinstance(item, YuanbaoCredential):
                normalized.append(item.to_platform_credential())
            else:
                raise TypeError(f"unsupported credential type: {type(item)!r}")
        self._credentials[platform_code] = tuple(normalized)
        self._sync_redis_metadata(platform_code, normalized)

    async def acquire(
        self,
        platform_code: str,
        *,
        request_id: str | None = None,
    ) -> PlatformCredential:
        credentials = self._credentials.get(platform_code, ())
        if not credentials:
            raise NoAvailableCredentialError(platform_code=platform_code, request_id=request_id)

        try:
            return self._acquire_with_redis(platform_code, credentials, request_id=request_id)
        except Exception as exc:
            self._log_redis_degraded(exc)
            return self._acquire_with_fallback(platform_code, credentials, request_id=request_id)

    async def report_failure(
        self,
        fingerprint: str,
        error: AdapterError,
        *,
        platform_code: str,
        request_id: str | None = None,
    ) -> None:
        log_adapter_event(
            logger,
            platform_code=platform_code,
            fingerprint=fingerprint,
            request_id=request_id,
            category=error.category,
            message=error.sanitized_message(),
        )
        if error.category == ErrorCategory.UNAUTHORIZED:
            self._set_state(platform_code, fingerprint, CredentialState.DISABLED)
            return
        if error.category == ErrorCategory.RATE_LIMITED:
            cooldown = error.retry_after_seconds or self._retry_base_seconds
            self._set_state(
                platform_code,
                fingerprint,
                CredentialState.COOLING,
                cooldown_until=str(time.time() + cooldown),
            )
            return
        if error.category in {ErrorCategory.SERVER_ERROR, ErrorCategory.NETWORK_ERROR}:
            return
        if error.category in {ErrorCategory.INVALID_REQUEST, ErrorCategory.CONTENT_SAFETY}:
            return

    async def report_success(self, fingerprint: str, *, platform_code: str) -> None:
        self._set_state(platform_code, fingerprint, CredentialState.HEALTHY)

    def get_credential_state(self, platform_code: str, fingerprint: str) -> CredentialState:
        state = self._read_state(platform_code, fingerprint)
        status = state.get("status", CredentialState.HEALTHY.value)
        if status == CredentialState.COOLING.value:
            cooldown_until = float(state.get("cooldown_until", "0"))
            if cooldown_until <= time.time():
                return CredentialState.HEALTHY
        return CredentialState(status)

    def _acquire_with_redis(
        self,
        platform_code: str,
        credentials: tuple[PlatformCredential, ...],
        *,
        request_id: str | None,
    ) -> PlatformCredential:
        if self._redis is None:
            raise ConnectionError("redis client is not configured")
        cursor = self._redis.incr(self._cursor_key(platform_code))
        return self._select_from_cursor(
            platform_code,
            credentials,
            start_index=(cursor - 1) % len(credentials),
            request_id=request_id,
        )

    def _acquire_with_fallback(
        self,
        platform_code: str,
        credentials: tuple[PlatformCredential, ...],
        *,
        request_id: str | None,
    ) -> PlatformCredential:
        cursor = self._fallback_cursor.get(platform_code, 0) + 1
        self._fallback_cursor[platform_code] = cursor
        return self._select_from_cursor(
            platform_code,
            credentials,
            start_index=(cursor - 1) % len(credentials),
            request_id=request_id,
            use_fallback=True,
        )

    def _select_from_cursor(
        self,
        platform_code: str,
        credentials: tuple[PlatformCredential, ...],
        *,
        start_index: int,
        request_id: str | None,
        use_fallback: bool = False,
    ) -> PlatformCredential:
        for offset in range(len(credentials)):
            candidate = credentials[(start_index + offset) % len(credentials)]
            state = (
                self._read_fallback_state(platform_code, candidate.fingerprint)
                if use_fallback
                else self._read_state(platform_code, candidate.fingerprint)
            )
            if self._is_selectable(state):
                return candidate
        raise NoAvailableCredentialError(platform_code=platform_code, request_id=request_id)

    def _sync_redis_metadata(
        self,
        platform_code: str,
        credentials: tuple[PlatformCredential, ...] | list[PlatformCredential],
    ) -> None:
        if self._redis is None:
            return
        try:
            for credential in credentials:
                key = self._state_key(platform_code, credential.fingerprint)
                existing = self._redis.hgetall(key)
                if not existing:
                    self._redis.hset(
                        key,
                        mapping={
                            "status": CredentialState.HEALTHY.value,
                            "cooldown_until": "0",
                        },
                    )
        except Exception as exc:
            self._log_redis_degraded(exc)

    def _set_state(
        self,
        platform_code: str,
        fingerprint: str,
        status: CredentialState,
        *,
        cooldown_until: str | None = None,
    ) -> None:
        mapping = {
            "status": status.value,
            "cooldown_until": cooldown_until or "0",
        }
        try:
            if self._redis is not None:
                self._redis.hset(self._state_key(platform_code, fingerprint), mapping=mapping)
        except Exception as exc:
            self._log_redis_degraded(exc)
        self._fallback_state[(platform_code, fingerprint)] = mapping

    def _read_state(self, platform_code: str, fingerprint: str) -> dict[str, str]:
        try:
            if self._redis is not None:
                return self._redis.hgetall(self._state_key(platform_code, fingerprint))
        except Exception as exc:
            self._log_redis_degraded(exc)
        return self._read_fallback_state(platform_code, fingerprint)

    def _read_fallback_state(self, platform_code: str, fingerprint: str) -> dict[str, str]:
        return dict(
            self._fallback_state.get(
                (platform_code, fingerprint),
                {
                    "status": CredentialState.HEALTHY.value,
                    "cooldown_until": "0",
                },
            )
        )

    @staticmethod
    def _is_selectable(state: dict[str, str]) -> bool:
        status = state.get("status", CredentialState.HEALTHY.value)
        if status == CredentialState.DISABLED.value:
            return False
        if status == CredentialState.COOLING.value:
            cooldown_until = float(state.get("cooldown_until", "0"))
            return cooldown_until <= time.time()
        return True

    def _cursor_key(self, platform_code: str) -> str:
        return f"{self._key_prefix}:{platform_code}:cursor"

    def _state_key(self, platform_code: str, fingerprint: str) -> str:
        return f"{self._key_prefix}:{platform_code}:fp:{fingerprint}"

    def _log_redis_degraded(self, exc: Exception) -> None:
        if self._redis_degraded_logged:
            return
        logger.warning("redis unavailable, falling back to in-memory credential rotation: %s", exc)
        self._redis_degraded_logged = True
