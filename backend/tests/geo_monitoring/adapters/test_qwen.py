"""通义千问 OpenAI-compatible 适配器测试。"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from app.geo_monitoring.adapters.base import PlatformCredential, PlatformQuery
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory
from app.geo_monitoring.adapters.qwen import QwenAdapter


BASE_URL = "https://qwen.test/compatible-mode/v1"


def _query() -> PlatformQuery:
    return PlatformQuery(
        prompt="请总结 GEO 平台",
        system_prompt=None,
        model="qwen-max",
        temperature=None,
        request_id="req-qwen-1",
    )


def _credential() -> PlatformCredential:
    return PlatformCredential(
        platform_code="qwen",
        fingerprint="fp-qwen",
        api_key="sk-qwen-test",
    )


def _adapter(*, raw_response_enabled: bool = True) -> QwenAdapter:
    return QwenAdapter(
        base_url=BASE_URL,
        timeout_seconds=0.1,
        raw_response_enabled=raw_response_enabled,
    )


def _request_json(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def _success_payload(content: str = "千问回答") -> dict:
    return {
        "id": "qwen-provider-1",
        "model": "qwen-max",
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 6,
            "total_tokens": 18,
        },
    }


@respx.mock
def test_qwen_maps_openai_compatible_success_response():
    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_success_payload(),
            headers={"x-request-id": "qwen-header-request"},
        )
    )

    answer = asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert route.called
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer sk-qwen-test"
    payload = _request_json(request)
    assert payload == {
        "model": "qwen-max",
        "messages": [{"role": "user", "content": "请总结 GEO 平台"}],
        "stream": False,
    }
    assert answer.text == "千问回答"
    assert answer.model == "qwen-max"
    assert answer.usage == {
        "prompt_tokens": 12,
        "completion_tokens": 6,
        "total_tokens": 18,
    }
    assert answer.provider_request_id == "qwen-provider-1"
    assert answer.raw_response == _success_payload()
    assert answer.citations == []


@respx.mock
def test_qwen_can_omit_raw_response():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_success_payload())
    )

    answer = asyncio.run(
        _adapter(raw_response_enabled=False).query(_query(), credential=_credential())
    )

    assert answer.raw_response is None


@respx.mock
def test_qwen_maps_timeout_to_network_error():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.NETWORK_ERROR
    assert "sk-qwen-test" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (429, ErrorCategory.RATE_LIMITED),
        (401, ErrorCategory.UNAUTHORIZED),
        (500, ErrorCategory.SERVER_ERROR),
    ],
)
@respx.mock
def test_qwen_maps_http_errors(status_code: int, expected: ErrorCategory):
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
def test_qwen_rejects_empty_answer():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_success_payload(content=""))
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST
