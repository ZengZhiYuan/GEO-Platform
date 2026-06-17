"""平台适配器基础设施。"""

from app.geo_monitoring.adapters.base import (
    PlatformAdapter,
    PlatformAnswer,
    PlatformCredential,
    PlatformQuery,
    compute_credential_fingerprint,
)
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
from app.geo_monitoring.adapters.key_pool import (
    ApiKeyCredential,
    CredentialKeyPool,
    CredentialState,
    YuanbaoCredential,
)
from app.geo_monitoring.adapters.registry import AdapterRegistry
from app.geo_monitoring.adapters.registry import build_adapter_registry

__all__ = [
    "AdapterError",
    "AdapterRegistry",
    "ApiKeyCredential",
    "CredentialKeyPool",
    "CredentialState",
    "ErrorCategory",
    "NoAvailableCredentialError",
    "PlatformAdapter",
    "PlatformAnswer",
    "PlatformCredential",
    "PlatformDisabledError",
    "PlatformNotRegisteredError",
    "PlatformQuery",
    "YuanbaoCredential",
    "build_adapter_registry",
    "classify_http_status",
    "compute_credential_fingerprint",
    "is_retryable",
    "log_adapter_event",
    "sanitize_message",
]
