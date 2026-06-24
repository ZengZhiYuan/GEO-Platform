"""Aidso OpenAPI collection adapter."""

from __future__ import annotations

from app.core.config import settings
from app.geo_monitoring.adapters.base import (
    PlatformAnswer,
    PlatformCredential,
    PlatformQuery,
)
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory


class AidsoAdapter:
    # 初始化 Aidso 端侧适配器配置
    def __init__(
        self,
        *,
        code: str,
        aidso_name: str,
        base_url: str = settings.AIDSO_BASE_URL,
        timeout_seconds: float = settings.COLLECTION_REQUEST_TIMEOUT_SECONDS,
        raw_response_enabled: bool = settings.COLLECTION_RAW_RESPONSE_ENABLED,
    ) -> None:
        self.code = code
        self._aidso_name = aidso_name
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._raw_response_enabled = raw_response_enabled

    async def query(
        self,
        request: PlatformQuery,
        *,
        credential: PlatformCredential,
    ) -> PlatformAnswer:
        """调用 Aidso OpenAPI 并返回统一答案结构。"""
        raise AdapterError(
            "aidso adapter query is not implemented",
            category=ErrorCategory.INVALID_REQUEST,
        )
