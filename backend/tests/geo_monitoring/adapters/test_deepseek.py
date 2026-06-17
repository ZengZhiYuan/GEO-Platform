"""DeepSeek 官方 API 适配器测试。"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from app.geo_monitoring.adapters.base import PlatformCredential, PlatformQuery
from app.geo_monitoring.adapters.deepseek import DeepSeekAdapter
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory


BASE_URL = "https://deepseek.test"


def _query() -> PlatformQuery:
    return PlatformQuery(
        prompt="请总结 GEO 平台",
        system_prompt="你是监测助手",
        model="deepseek-chat",
        temperature=0.1,
        request_id="req-deepseek-1",
    )


def _credential() -> PlatformCredential:
    return PlatformCredential(
        platform_code="deepseek",
        fingerprint="fp-deepseek",
        api_key="sk-deepseek-test",
    )


def _adapter() -> DeepSeekAdapter:
    return DeepSeekAdapter(
        base_url=BASE_URL,
        timeout_seconds=0.1,
        raw_response_enabled=True,
    )


def _request_json(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def _success_payload(content: str = "DeepSeek 回答") -> dict:
    return {
        "id": "deepseek-provider-1",
        "model": "deepseek-chat",
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": 8,
            "completion_tokens": 4,
            "total_tokens": 12,
        },
    }


@respx.mock
def test_deepseek_maps_openai_compatible_success_response():
    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_success_payload())
    )

    answer = asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert route.called
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer sk-deepseek-test"
    payload = _request_json(request)
    assert payload["model"] == "deepseek-chat"
    assert payload["temperature"] == 0.1
    assert payload["messages"] == [
        {"role": "system", "content": "你是监测助手"},
        {"role": "user", "content": "请总结 GEO 平台"},
    ]
    assert answer.text == "DeepSeek 回答"
    assert answer.model == "deepseek-chat"
    assert answer.usage["total_tokens"] == 12
    assert answer.provider_request_id == "deepseek-provider-1"
    assert answer.raw_response == _success_payload()
    assert answer.citations == []


@respx.mock
def test_deepseek_maps_timeout_to_network_error():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.NETWORK_ERROR
    assert "sk-deepseek-test" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (429, ErrorCategory.RATE_LIMITED),
        (401, ErrorCategory.UNAUTHORIZED),
        (503, ErrorCategory.SERVER_ERROR),
    ],
)
@respx.mock
def test_deepseek_maps_http_errors(status_code: int, expected: ErrorCategory):
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
def test_deepseek_rejects_empty_choices():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json={**_success_payload(), "choices": []})
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST


@respx.mock
def test_deepseek_rejects_empty_content():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_success_payload(content=""))
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST
