"""适配器 registry 测试。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.geo_monitoring.adapters.base import PlatformAnswer, PlatformQuery
from app.geo_monitoring.adapters.errors import PlatformDisabledError, PlatformNotRegisteredError
from app.geo_monitoring.adapters.registry import AdapterRegistry, build_adapter_registry


class StubAdapter:
    code = "qwen"

    async def query(self, request: PlatformQuery, *, credential: Any) -> PlatformAnswer:
        return PlatformAnswer(
            text="ok",
            citations=[],
            model=request.model,
            usage={},
            latency_ms=1,
            provider_request_id="stub",
            raw_response=None,
        )


def test_registry_returns_registered_adapter():
    registry = AdapterRegistry()
    adapter = StubAdapter()
    registry.register(adapter)
    assert registry.get("qwen") is adapter


def test_registry_raises_for_unknown_platform():
    registry = AdapterRegistry()
    with pytest.raises(PlatformNotRegisteredError):
        registry.get("missing")


def test_registry_raises_for_disabled_platform():
    registry = AdapterRegistry()
    registry.register(StubAdapter())
    with pytest.raises(PlatformDisabledError):
        registry.require_enabled("qwen", enabled=False)


def test_registry_enabled_platform_returns_adapter():
    registry = AdapterRegistry()
    adapter = StubAdapter()
    registry.register(adapter)
    assert registry.require_enabled("qwen", enabled=True) is adapter


def _runtime_settings(**overrides: Any) -> SimpleNamespace:
    defaults = {
        "COLLECTION_REQUEST_TIMEOUT_SECONDS": 60,
        "COLLECTION_RAW_RESPONSE_ENABLED": True,
        "DOUBAO_ENABLED": False,
        "DOUBAO_BASE_URL": "https://doubao.test/api/v3",
        "DOUBAO_MODEL": "",
        "DOUBAO_API_KEYS": "",
        "QWEN_ENABLED": False,
        "QWEN_BASE_URL": "https://qwen.test/compatible-mode/v1",
        "QWEN_MODEL": "",
        "QWEN_API_KEYS": "",
        "YUANBAO_ENABLED": False,
        "YUANBAO_BASE_URL": "https://hunyuan.tencentcloudapi.test",
        "YUANBAO_MODEL": "",
        "YUANBAO_CREDENTIALS_JSON": "[]",
        "DEEPSEEK_ENABLED": False,
        "DEEPSEEK_BASE_URL": "https://deepseek.test",
        "DEEPSEEK_MODEL": "",
        "DEEPSEEK_API_KEYS": "",
        "KIMI_ENABLED": False,
        "KIMI_BASE_URL": "https://kimi.test/v1",
        "KIMI_MODEL": "",
        "KIMI_API_KEYS": "",
        "AIDSO_ENABLED": False,
        "AIDSO_BASE_URL": "https://aidso.test",
        "AIDSO_API_TOKEN": "",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_build_adapter_registry_skips_disabled_and_unconfigured_platforms():
    registry = build_adapter_registry(
        _runtime_settings(
            DOUBAO_ENABLED=True,
            DOUBAO_MODEL="",
            DOUBAO_API_KEYS="doubao-key",
            QWEN_ENABLED=False,
            QWEN_MODEL="qwen-max",
            QWEN_API_KEYS="qwen-key",
        )
    )

    assert registry.registered_codes() == ()


def test_build_adapter_registry_skips_enabled_platforms_without_credentials():
    registry = build_adapter_registry(
        _runtime_settings(
            DOUBAO_ENABLED=True,
            DOUBAO_MODEL="doubao-pro-32k",
            DOUBAO_API_KEYS="",
            YUANBAO_ENABLED=True,
            YUANBAO_MODEL="hunyuan-turbo",
            YUANBAO_CREDENTIALS_JSON="[]",
        )
    )

    assert registry.registered_codes() == ()


@pytest.mark.parametrize(
    "credentials_json",
    [
        [{"secret_id": "sid"}],
        '[{"secret_id": "sid"}]',
        [{}],
    ],
)
def test_build_adapter_registry_skips_malformed_yuanbao_credentials(credentials_json: Any):
    registry = build_adapter_registry(
        _runtime_settings(
            YUANBAO_ENABLED=True,
            YUANBAO_MODEL="hunyuan-turbo",
            YUANBAO_CREDENTIALS_JSON=credentials_json,
        )
    )

    assert registry.registered_codes() == ()


def test_build_adapter_registry_registers_enabled_configured_platforms():
    registry = build_adapter_registry(
        _runtime_settings(
            DOUBAO_ENABLED=True,
            DOUBAO_MODEL="doubao-pro-32k",
            DOUBAO_API_KEYS="doubao-key",
            QWEN_ENABLED=True,
            QWEN_MODEL="qwen-max",
            QWEN_API_KEYS="qwen-key",
            YUANBAO_ENABLED=True,
            YUANBAO_MODEL="hunyuan-turbo",
            YUANBAO_CREDENTIALS_JSON=[
                {"secret_id": "sid", "secret_key": "skey"},
            ],
            DEEPSEEK_ENABLED=True,
            DEEPSEEK_MODEL="deepseek-chat",
            DEEPSEEK_API_KEYS="deepseek-key",
            KIMI_ENABLED=True,
            KIMI_MODEL="moonshot-v1-8k",
            KIMI_API_KEYS="kimi-key",
        )
    )

    assert registry.registered_codes() == (
        "deepseek",
        "doubao",
        "kimi",
        "qwen",
        "yuanbao",
    )


def test_build_adapter_registry_registers_aidso_platforms_when_configured():
    registry = build_adapter_registry(
        _runtime_settings(
            AIDSO_ENABLED=True,
            AIDSO_BASE_URL="https://aidso.test",
            AIDSO_API_TOKEN="aidso-token",
        )
    )

    codes = registry.registered_codes()
    assert "aidso_doubao_web" in codes
    assert "aidso_qwen_app" in codes
