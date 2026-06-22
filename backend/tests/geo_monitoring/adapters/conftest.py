"""Adapter 测试 fixtures。"""

from __future__ import annotations

import time
from typing import Any

import pytest


class FakeRedis:
    """最小 Redis 兼容实现，供密钥池单元测试使用。"""

    def __init__(self) -> None:
        self._strings: dict[str, str] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._expiry: dict[str, float] = {}
        self.available = True

    def _purge_expired(self, key: str) -> None:
        expires_at = self._expiry.get(key)
        if expires_at is not None and expires_at <= time.time():
            self._strings.pop(key, None)
            self._hashes.pop(key, None)
            self._expiry.pop(key, None)

    def incr(self, key: str) -> int:
        if not self.available:
            raise ConnectionError("redis unavailable")
        self._purge_expired(key)
        current = int(self._strings.get(key, "0"))
        current += 1
        self._strings[key] = str(current)
        return current

    def hset(self, name: str, mapping: dict[str, Any] | None = None, **kwargs: Any) -> int:
        if not self.available:
            raise ConnectionError("redis unavailable")
        self._purge_expired(name)
        payload = dict(mapping or {})
        payload.update(kwargs)
        bucket = self._hashes.setdefault(name, {})
        bucket.update({str(k): str(v) for k, v in payload.items()})
        return len(payload)

    def hgetall(self, name: str) -> dict[str, str]:
        if not self.available:
            raise ConnectionError("redis unavailable")
        self._purge_expired(name)
        return dict(self._hashes.get(name, {}))

    def expire(self, name: str, seconds: int) -> bool:
        if not self.available:
            raise ConnectionError("redis unavailable")
        self._expiry[name] = time.time() + seconds
        return True


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()
