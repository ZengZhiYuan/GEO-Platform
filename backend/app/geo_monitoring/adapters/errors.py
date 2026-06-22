"""平台适配器错误分类与脱敏。"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Iterable


class ErrorCategory(StrEnum):
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    INVALID_REQUEST = "invalid_request"
    CONTENT_SAFETY = "content_safety"
    UNKNOWN = "unknown"


REDACTED = "[REDACTED]"


# 将 HTTP 状态码与错误消息映射为统一错误分类
def classify_http_status(status_code: int, *, message: str = "") -> ErrorCategory:
    normalized = message.lower()
    if "content safety" in normalized or "content policy" in normalized:
        return ErrorCategory.CONTENT_SAFETY
    if status_code == 429:
        return ErrorCategory.RATE_LIMITED
    if status_code in {401, 403}:
        return ErrorCategory.UNAUTHORIZED
    if status_code >= 500:
        return ErrorCategory.SERVER_ERROR
    if status_code >= 400:
        return ErrorCategory.INVALID_REQUEST
    return ErrorCategory.UNKNOWN


# 判断该错误类别是否适合自动重试
def is_retryable(category: ErrorCategory) -> bool:
    return category in {
        ErrorCategory.RATE_LIMITED,
        ErrorCategory.SERVER_ERROR,
        ErrorCategory.NETWORK_ERROR,
    }


# 从错误消息中替换敏感密钥为占位符
def sanitize_message(message: str, secrets: Iterable[str] = ()) -> str:
    sanitized = message
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, REDACTED)
    return sanitized


class AdapterError(Exception):
    """适配器统一异常，消息中不得包含明文密钥。"""

    # 构造带分类与脱敏消息的适配器异常
    def __init__(
        self,
        message: str,
        *,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
        secrets: Iterable[str] = (),
    ) -> None:
        self.category = category
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self._secrets = tuple(secrets)
        super().__init__(sanitize_message(message, self._secrets))

    # 返回已脱敏的异常消息文本
    def sanitized_message(self) -> str:
        return str(self)


class NoAvailableCredentialError(AdapterError):
    # 平台无可用凭证时抛出
    def __init__(self, *, platform_code: str, request_id: str | None = None) -> None:
        suffix = f" request_id={request_id}" if request_id else ""
        super().__init__(
            f"no available credential for platform={platform_code}{suffix}",
            category=ErrorCategory.UNAUTHORIZED,
        )
        self.platform_code = platform_code
        self.request_id = request_id


class PlatformDisabledError(AdapterError):
    # 平台被禁用时抛出
    def __init__(self, *, platform_code: str) -> None:
        super().__init__(
            f"platform disabled: {platform_code}",
            category=ErrorCategory.INVALID_REQUEST,
        )
        self.platform_code = platform_code


class PlatformNotRegisteredError(AdapterError):
    # 平台适配器未注册时抛出
    def __init__(self, *, platform_code: str) -> None:
        super().__init__(
            f"platform adapter not registered: {platform_code}",
            category=ErrorCategory.INVALID_REQUEST,
        )
        self.platform_code = platform_code


# 记录脱敏后的适配器调用/失败事件
def log_adapter_event(
    logger: logging.Logger,
    *,
    platform_code: str,
    fingerprint: str,
    request_id: str | None,
    category: ErrorCategory,
    message: str,
    secrets: Iterable[str] = (),
) -> None:
    logger.info(
        "platform=%s fingerprint=%s request_id=%s category=%s message=%s",
        platform_code,
        fingerprint,
        request_id or "-",
        category.value,
        sanitize_message(message, secrets),
    )
