"""平台适配器注册表。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.adapters.base import PlatformAdapter
from app.geo_monitoring.adapters.errors import PlatformDisabledError, PlatformNotRegisteredError
from app.geo_monitoring.adapters.key_pool import CredentialKeyPool
from app.geo_monitoring.models import AIPlatform
from app.geo_monitoring.repositories import platforms as platform_repo
from app.geo_monitoring.services.platforms import (
    AIDSO_PLATFORM_MAPPINGS,
    MOLIZHISHU_PLATFORM_MAPPINGS,
    MolizhishuPlatformMapping,
    OFFICIAL_PLATFORMS,
)

OFFICIAL_PLATFORM_ENV_PREFIX = {
    item["platform_code"]: item["platform_code"].upper()
    for item in OFFICIAL_PLATFORMS
}
RUNTIME_ADAPTER_MISMATCH_CODE = 40908


class AdapterRegistry:
    # 初始化空的平台适配器注册表
    def __init__(self) -> None:
        self._adapters: dict[str, PlatformAdapter] = {}

    # 注册一个平台适配器实例
    def register(self, adapter: PlatformAdapter) -> None:
        self._adapters[adapter.code] = adapter

    # 按平台代码获取已注册的适配器
    def get(self, platform_code: str) -> PlatformAdapter:
        adapter = self._adapters.get(platform_code)
        if adapter is None:
            raise PlatformNotRegisteredError(platform_code=platform_code)
        return adapter

    # 校验平台已启用后返回对应适配器
    def require_enabled(self, platform_code: str, *, enabled: bool) -> PlatformAdapter:
        if not enabled:
            raise PlatformDisabledError(platform_code=platform_code)
        return self.get(platform_code)

    # 返回所有已注册平台代码的有序元组
    def registered_codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


def build_adapter_registry(
    runtime_settings: Any | None = None,
    *,
    molizhishu_mappings: dict[str, MolizhishuPlatformMapping] | None = None,
) -> AdapterRegistry:
    """按运行配置注册已启用且已配置模型的平台适配器。

    Aidso 仅在 ``AIDSO_ENABLED=true`` 时注册，供历史 pending 任务续跑；
    新建采集应使用 ``official`` 或 ``molizhishu``（见 ``RunCreateCollectionSource``）。
    """

    if runtime_settings is None:
        from app.core.config import settings as runtime_settings

    registry = AdapterRegistry()
    timeout_seconds = runtime_settings.COLLECTION_REQUEST_TIMEOUT_SECONDS
    raw_response_enabled = runtime_settings.COLLECTION_RAW_RESPONSE_ENABLED

    if _configured(runtime_settings, "DOUBAO"):
        from app.geo_monitoring.adapters.doubao import DoubaoAdapter

        registry.register(
            DoubaoAdapter(
                base_url=runtime_settings.DOUBAO_BASE_URL,
                timeout_seconds=timeout_seconds,
                raw_response_enabled=raw_response_enabled,
            )
        )

    if _configured(runtime_settings, "QWEN"):
        from app.geo_monitoring.adapters.qwen import QwenAdapter

        registry.register(
            QwenAdapter(
                base_url=runtime_settings.QWEN_BASE_URL,
                timeout_seconds=timeout_seconds,
                raw_response_enabled=raw_response_enabled,
            )
        )

    if _configured(runtime_settings, "YUANBAO"):
        from app.geo_monitoring.adapters.yuanbao import YuanbaoAdapter

        registry.register(
            YuanbaoAdapter(
                base_url=runtime_settings.YUANBAO_BASE_URL,
                timeout_seconds=timeout_seconds,
                raw_response_enabled=raw_response_enabled,
            )
        )

    if _configured(runtime_settings, "DEEPSEEK"):
        from app.geo_monitoring.adapters.deepseek import DeepSeekAdapter

        registry.register(
            DeepSeekAdapter(
                base_url=runtime_settings.DEEPSEEK_BASE_URL,
                timeout_seconds=timeout_seconds,
                raw_response_enabled=raw_response_enabled,
            )
        )

    if _configured(runtime_settings, "KIMI"):
        from app.geo_monitoring.adapters.kimi import KimiAdapter

        registry.register(
            KimiAdapter(
                base_url=runtime_settings.KIMI_BASE_URL,
                timeout_seconds=timeout_seconds,
                raw_response_enabled=raw_response_enabled,
            )
        )

    if _aidso_configured(runtime_settings):
        from app.geo_monitoring.adapters.aidso import AidsoAdapter
        from app.geo_monitoring.services.platforms import AIDSO_PLATFORM_MAPPINGS

        for code, item in AIDSO_PLATFORM_MAPPINGS.items():
            registry.register(
                AidsoAdapter(
                    code=code,
                    aidso_name=item["aidso_name"],
                    base_url=runtime_settings.AIDSO_BASE_URL,
                    timeout_seconds=timeout_seconds,
                    raw_response_enabled=raw_response_enabled,
                )
            )

    if _molizhishu_configured(runtime_settings):
        from app.geo_monitoring.adapters.molizhishu import MolizhishuAdapter

        mappings = molizhishu_mappings or MOLIZHISHU_PLATFORM_MAPPINGS
        for code, item in mappings.items():
            registry.register(
                MolizhishuAdapter(
                    code=code,
                    molizhishu_platform=str(item["molizhishu_platform"]),
                    default_mode=str(item["default_mode"]),
                    base_url=runtime_settings.MOLIZHISHU_BASE_URL,
                    timeout_seconds=runtime_settings.MOLIZHISHU_REQUEST_TIMEOUT_SECONDS,
                    raw_response_enabled=raw_response_enabled,
                )
            )

    return registry


# 检查某平台是否已启用且具备 URL、模型与凭证配置
def _configured(runtime_settings: Any, prefix: str) -> bool:
    enabled = bool(getattr(runtime_settings, f"{prefix}_ENABLED"))
    base_url = str(getattr(runtime_settings, f"{prefix}_BASE_URL", "")).strip()
    model = str(getattr(runtime_settings, f"{prefix}_MODEL", "")).strip()
    if not enabled or not base_url or not model:
        return False
    if prefix == "YUANBAO":
        return _has_yuanbao_credentials(runtime_settings)
    return _has_api_keys(getattr(runtime_settings, f"{prefix}_API_KEYS", ""))


# 判断配置中是否包含至少一个有效 API Key
def _has_api_keys(raw_value: Any) -> bool:
    if raw_value is None:
        return False
    if isinstance(raw_value, list):
        return any(str(item).strip() for item in raw_value)
    return any(item.strip() for item in str(raw_value).split(","))


def _aidso_configured(runtime_settings: Any) -> bool:
    enabled = bool(getattr(runtime_settings, "AIDSO_ENABLED", False))
    base_url = str(getattr(runtime_settings, "AIDSO_BASE_URL", "")).strip()
    token = str(getattr(runtime_settings, "AIDSO_API_TOKEN", "")).strip()
    return bool(enabled and base_url and token)


def _molizhishu_configured(runtime_settings: Any) -> bool:
    enabled = bool(getattr(runtime_settings, "MOLIZHISHU_ENABLED", False))
    base_url = str(getattr(runtime_settings, "MOLIZHISHU_BASE_URL", "")).strip()
    token = str(getattr(runtime_settings, "MOLIZHISHU_API_TOKEN", "")).strip()
    return bool(enabled and base_url and token)


# 判断配置中是否包含至少一组有效腾讯元宝凭证
def _has_yuanbao_credentials(runtime_settings: Any) -> bool:
    parser = getattr(runtime_settings, "parsed_yuanbao_credentials", None)
    if callable(parser):
        try:
            return bool(parser())
        except ValueError:
            return False

    raw_value = getattr(runtime_settings, "YUANBAO_CREDENTIALS_JSON", "[]")
    if raw_value is None or raw_value == "":
        return False
    if isinstance(raw_value, list):
        return any(_valid_yuanbao_credential(item) for item in raw_value)
    try:
        parsed = json.loads(str(raw_value))
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, list) and any(
        _valid_yuanbao_credential(item) for item in parsed
    )


# 校验单条元宝凭证是否同时包含 secret_id 与 secret_key
def _valid_yuanbao_credential(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    secret_id = str(item.get("secret_id", "")).strip()
    secret_key = str(item.get("secret_key", "")).strip()
    return bool(secret_id and secret_key)


def platform_runtime_configured(
    platform_code: str,
    runtime_settings: Any,
    *,
    adapter_type: str | None = None,
) -> bool:
    """判断平台在运行配置中是否已完整启用（不含 adapter 是否已注册）。"""
    if adapter_type == "molizhishu" or platform_code in MOLIZHISHU_PLATFORM_MAPPINGS:
        return _molizhishu_configured(runtime_settings)
    if adapter_type == "aidso" or platform_code in AIDSO_PLATFORM_MAPPINGS:
        return _aidso_configured(runtime_settings)
    prefix = OFFICIAL_PLATFORM_ENV_PREFIX.get(platform_code)
    if prefix is None:
        return False
    return _configured(runtime_settings, prefix)


def platform_adapter_registered(
    platform_code: str, adapter_registry: AdapterRegistry
) -> bool:
    return platform_code in adapter_registry.registered_codes()


def platform_credential_count(
    platform_code: str,
    *,
    runtime_settings: Any,
    adapter_type: str | None = None,
    key_pool: CredentialKeyPool | None = None,
) -> int:
    if key_pool is not None:
        return key_pool.credential_count(platform_code)
    if adapter_type == "molizhishu" or platform_code in MOLIZHISHU_PLATFORM_MAPPINGS:
        return 1 if _molizhishu_configured(runtime_settings) else 0
    if adapter_type == "aidso" or platform_code in AIDSO_PLATFORM_MAPPINGS:
        token = str(getattr(runtime_settings, "AIDSO_API_TOKEN", "")).strip()
        return 1 if _aidso_configured(runtime_settings) and token else 0
    prefix = OFFICIAL_PLATFORM_ENV_PREFIX.get(platform_code)
    if prefix is None:
        return 0
    if not _configured(runtime_settings, prefix):
        return 0
    if prefix == "YUANBAO":
        return len(runtime_settings.parsed_yuanbao_credentials())
    return len(runtime_settings.parsed_api_keys(getattr(runtime_settings, f"{prefix}_API_KEYS", "")))


def summarize_platform_runtime(
    platform: AIPlatform,
    *,
    runtime_settings: Any,
    adapter_registry: AdapterRegistry,
    key_pool: CredentialKeyPool | None = None,
) -> dict[str, Any]:
    platform_code = platform.platform_code
    runtime_configured = platform_runtime_configured(
        platform_code,
        runtime_settings,
        adapter_type=platform.adapter_type,
    )
    adapter_registered = platform_adapter_registered(platform_code, adapter_registry)
    credential_count = platform_credential_count(
        platform_code,
        runtime_settings=runtime_settings,
        adapter_type=platform.adapter_type,
        key_pool=key_pool,
    )
    return {
        "platform_code": platform_code,
        "db_enabled": platform.enabled,
        "runtime_configured": runtime_configured,
        "credential_count": credential_count,
        "adapter_registered": adapter_registered,
        "ready_for_collection": (
            platform.enabled and runtime_configured and adapter_registered and credential_count > 0
        ),
    }


def build_platform_runtime_diagnostics(
    db: Session,
    *,
    runtime_settings: Any,
    adapter_registry: AdapterRegistry,
    key_pool: CredentialKeyPool | None = None,
) -> list[dict[str, Any]]:
    platforms = platform_repo.list_all_platforms(db)
    return [
        summarize_platform_runtime(
            platform,
            runtime_settings=runtime_settings,
            adapter_registry=adapter_registry,
            key_pool=key_pool,
        )
        for platform in platforms
    ]


def _runtime_mismatch_message(platform_code: str, collection_source: str) -> str:
    if collection_source == "molizhishu":
        return (
            "模力指数采集运行时未就绪：请设置 MOLIZHISHU_ENABLED=true 并配置 "
            "MOLIZHISHU_API_TOKEN"
        )
    prefix = OFFICIAL_PLATFORM_ENV_PREFIX.get(platform_code)
    if prefix:
        if prefix == "YUANBAO":
            return (
                f"AI 平台运行时未配置: {platform_code}（需启用 YUANBAO_ENABLED 并配置 "
                "YUANBAO_MODEL 与 YUANBAO_CREDENTIALS_JSON）"
            )
        return (
            f"AI 平台运行时未配置: {platform_code}（需启用 {prefix}_ENABLED 并配置 "
            f"{prefix}_MODEL 与 {prefix}_API_KEYS）"
        )
    return f"AI 平台运行时未配置: {platform_code}"


def validate_resolved_platforms_runtime(
    platforms: list[AIPlatform],
    *,
    collection_source: str,
    runtime_settings: Any,
    adapter_registry: AdapterRegistry,
    key_pool: CredentialKeyPool | None = None,
) -> None:
    """Run 创建前校验 DB 已选平台与运行时 adapter / 凭证一致。"""
    if collection_source == "molizhishu" and not _molizhishu_configured(runtime_settings):
        raise BusinessException(
            message=_runtime_mismatch_message("molizhishu", collection_source),
            code=RUNTIME_ADAPTER_MISMATCH_CODE,
            status_code=409,
        )

    for platform in platforms:
        platform_code = platform.platform_code
        if not platform_runtime_configured(
            platform_code,
            runtime_settings,
            adapter_type=platform.adapter_type,
        ):
            raise BusinessException(
                message=_runtime_mismatch_message(platform_code, collection_source),
                code=RUNTIME_ADAPTER_MISMATCH_CODE,
                status_code=409,
            )
        if not platform_adapter_registered(platform_code, adapter_registry):
            raise BusinessException(
                message=_runtime_mismatch_message(platform_code, collection_source),
                code=RUNTIME_ADAPTER_MISMATCH_CODE,
                status_code=409,
            )
        if platform_credential_count(
            platform_code,
            runtime_settings=runtime_settings,
            adapter_type=platform.adapter_type,
            key_pool=key_pool,
        ) <= 0:
            raise BusinessException(
                message=_runtime_mismatch_message(platform_code, collection_source),
                code=RUNTIME_ADAPTER_MISMATCH_CODE,
                status_code=409,
            )
