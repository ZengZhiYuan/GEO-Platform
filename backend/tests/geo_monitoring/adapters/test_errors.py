"""适配器错误分类与脱敏测试。"""

import logging

import pytest

from app.geo_monitoring.adapters.errors import (
    AdapterError,
    ErrorCategory,
    NoAvailableCredentialError,
    PlatformDisabledError,
    PlatformNotRegisteredError,
    classify_http_status,
    is_retryable,
    log_adapter_event,
    sanitize_message,
)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (429, ErrorCategory.RATE_LIMITED),
        (401, ErrorCategory.UNAUTHORIZED),
        (403, ErrorCategory.UNAUTHORIZED),
        (500, ErrorCategory.SERVER_ERROR),
        (502, ErrorCategory.SERVER_ERROR),
        (400, ErrorCategory.INVALID_REQUEST),
        (422, ErrorCategory.INVALID_REQUEST),
    ],
)
def test_classify_http_status(status_code, expected):
    assert classify_http_status(status_code) == expected


def test_classify_content_safety_by_message():
    assert (
        classify_http_status(
            400,
            message="content safety policy violation",
        )
        == ErrorCategory.CONTENT_SAFETY
    )


def test_classify_molizhishu_message_maps_token_and_balance_errors():
    from app.geo_monitoring.adapters.errors import (
        classify_molizhishu_error,
        classify_molizhishu_message,
    )

    assert classify_molizhishu_message("Token失效") == ErrorCategory.UNAUTHORIZED
    assert classify_molizhishu_message("余额不足") == ErrorCategory.INVALID_REQUEST
    assert classify_molizhishu_error(code=40101, message="鉴权失败") == ErrorCategory.UNAUTHORIZED
    assert classify_molizhishu_error(code=40201, message="账户异常") == ErrorCategory.INVALID_REQUEST
    assert classify_molizhishu_error(code=40001, message="参数错误") == ErrorCategory.INVALID_REQUEST


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        (ErrorCategory.RATE_LIMITED, True),
        (ErrorCategory.SERVER_ERROR, True),
        (ErrorCategory.NETWORK_ERROR, True),
        (ErrorCategory.PENDING, True),
        (ErrorCategory.UNAUTHORIZED, False),
        (ErrorCategory.INVALID_REQUEST, False),
        (ErrorCategory.CONTENT_SAFETY, False),
        (ErrorCategory.CANCELLED, False),
    ],
)
def test_is_retryable(category, expected):
    assert is_retryable(category) is expected


def test_sanitize_message_redacts_known_secrets():
    secret = "sk-live-super-secret-key"
    message = f"request failed with Authorization: Bearer {secret}"
    sanitized = sanitize_message(message, [secret])
    assert secret not in sanitized
    assert "[REDACTED]" in sanitized


def test_adapter_error_does_not_embed_secret_in_str():
    secret = "sk-live-super-secret-key"
    error = AdapterError(
        "provider rejected credential",
        category=ErrorCategory.UNAUTHORIZED,
        secrets=(secret,),
    )
    assert secret not in str(error)


def test_no_available_credential_error_is_adapter_error():
    error = NoAvailableCredentialError(platform_code="qwen", request_id="req-1")
    assert isinstance(error, AdapterError)
    assert error.category == ErrorCategory.UNAUTHORIZED
    assert "qwen" in str(error)
    assert "req-1" in str(error)


def test_platform_disabled_and_not_registered_errors():
    disabled = PlatformDisabledError(platform_code="doubao")
    missing = PlatformNotRegisteredError(platform_code="unknown")
    assert disabled.category == ErrorCategory.INVALID_REQUEST
    assert missing.category == ErrorCategory.INVALID_REQUEST


def test_log_adapter_event_only_logs_safe_fields(caplog):
    secret = "sk-live-super-secret-key"
    with caplog.at_level(logging.INFO, logger="app.geo_monitoring.adapters"):
        log_adapter_event(
            logging.getLogger("app.geo_monitoring.adapters"),
            platform_code="qwen",
            fingerprint="fp1234567890abcd",
            request_id="req-1",
            category=ErrorCategory.RATE_LIMITED,
            message=f"rate limited with key {secret}",
            secrets=(secret,),
        )
    record = caplog.records[-1]
    assert secret not in record.getMessage()
    assert "fp1234567890abcd" in record.getMessage()
    assert "req-1" in record.getMessage()
    assert "rate_limited" in record.getMessage()
