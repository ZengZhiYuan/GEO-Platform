"""平台适配器基础契约。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


def compute_credential_fingerprint(platform_code: str, secret_material: str) -> str:
    payload = f"{platform_code}:{secret_material}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


@dataclass(frozen=True)
class PlatformQuery:
    prompt: str
    system_prompt: str | None
    model: str
    temperature: float | None
    request_id: str


@dataclass(frozen=True)
class PlatformAnswer:
    text: str
    citations: list[dict[str, Any]]
    model: str
    usage: dict[str, Any]
    latency_ms: int
    provider_request_id: str | None
    raw_response: dict[str, Any] | None = None


@dataclass(frozen=True)
class PlatformCredential:
    platform_code: str
    fingerprint: str
    api_key: str | None = None
    secret_id: str | None = None
    secret_key: str | None = None

    @property
    def kind(self) -> str:
        if self.secret_id is not None and self.secret_key is not None:
            return "yuanbao"
        return "api_key"


@runtime_checkable
class PlatformAdapter(Protocol):
    code: str

    async def query(
        self,
        request: PlatformQuery,
        *,
        credential: PlatformCredential,
    ) -> PlatformAnswer:
        """调用平台官方 API 并返回统一答案结构。"""
        ...
