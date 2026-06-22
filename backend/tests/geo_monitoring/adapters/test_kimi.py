"""Kimi/Moonshot 官方 API 适配器测试。"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from app.geo_monitoring.adapters.base import PlatformCredential, PlatformQuery
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory
from app.geo_monitoring.adapters.kimi import KimiAdapter


BASE_URL = "https://kimi.test/v1"


def _query() -> PlatformQuery:
    return PlatformQuery(
        prompt="请总结 GEO 平台",
        system_prompt="你是监测助手",
        model="moonshot-v1-8k",
        temperature=0.3,
        request_id="req-kimi-1",
    )


def _credential() -> PlatformCredential:
    return PlatformCredential(
        platform_code="kimi",
        fingerprint="fp-kimi",
        api_key="sk-kimi-test",
    )


def _adapter(*, raw_response_enabled: bool = True) -> KimiAdapter:
    return KimiAdapter(
        base_url=BASE_URL,
        timeout_seconds=0.1,
        raw_response_enabled=raw_response_enabled,
    )


def _request_json(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def _success_payload(content: str = "Kimi 回答") -> dict:
    return {
        "id": "kimi-provider-1",
        "model": "moonshot-v1-8k",
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": 9,
            "completion_tokens": 7,
            "total_tokens": 16,
        },
    }


@respx.mock
def test_kimi_maps_moonshot_success_response():
    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_success_payload(),
            headers={"x-request-id": "kimi-header-request"},
        )
    )

    answer = asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert route.called
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer sk-kimi-test"
    assert request.headers["x-request-id"] == "req-kimi-1"
    payload = _request_json(request)
    assert payload["model"] == "moonshot-v1-8k"
    assert payload["temperature"] == 0.3
    assert answer.text == "Kimi 回答"
    assert answer.model == "moonshot-v1-8k"
    assert answer.usage["total_tokens"] == 16
    assert answer.provider_request_id == "kimi-provider-1"
    assert answer.raw_response == _success_payload()
    assert answer.citations == []


@respx.mock
def test_kimi_can_omit_raw_response():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_success_payload())
    )

    answer = asyncio.run(
        _adapter(raw_response_enabled=False).query(_query(), credential=_credential())
    )

    assert answer.raw_response is None


@respx.mock
def test_kimi_maps_timeout_to_network_error():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.NETWORK_ERROR
    assert "sk-kimi-test" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (429, ErrorCategory.RATE_LIMITED),
        (401, ErrorCategory.UNAUTHORIZED),
        (500, ErrorCategory.SERVER_ERROR),
    ],
)
@respx.mock
def test_kimi_maps_http_errors(status_code: int, expected: ErrorCategory):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            status_code,
            json={"error": {"message": "provider rejected request"}},
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == expected
    assert exc_info.value.status_code == status_code


@respx.mock
def test_kimi_maps_content_safety_refusal():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"message": "content safety policy violation"}},
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.CONTENT_SAFETY


@respx.mock
def test_kimi_rejects_empty_answer():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_success_payload(content=""))
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST
