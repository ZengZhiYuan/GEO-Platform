"""豆包官方 API 适配器测试。"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from app.geo_monitoring.adapters.base import PlatformCredential, PlatformQuery
from app.geo_monitoring.adapters.doubao import DoubaoAdapter
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory


BASE_URL = "https://doubao.test/api/v3"


def _query() -> PlatformQuery:
    return PlatformQuery(
        prompt="请总结 GEO 平台",
        system_prompt="你是监测助手",
        model="doubao-pro-32k",
        temperature=0.2,
        request_id="req-doubao-1",
    )


def _credential() -> PlatformCredential:
    return PlatformCredential(
        platform_code="doubao",
        fingerprint="fp-doubao",
        api_key="sk-doubao-test",
    )


def _adapter(*, raw_response_enabled: bool = True) -> DoubaoAdapter:
    return DoubaoAdapter(
        base_url=BASE_URL,
        timeout_seconds=0.1,
        raw_response_enabled=raw_response_enabled,
    )


def _request_json(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def _success_payload(content: str = "豆包回答") -> dict:
    return {
        "id": "doubao-provider-1",
        "model": "doubao-pro-32k",
        "choices": [
            {
                "message": {
                    "content": content,
                    "citations": [
                        {
                            "title": "官方文档",
                            "url": "https://example.com/doubao",
                            "content": "引用原文",
                        }
                    ],
                }
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }


@respx.mock
def test_doubao_maps_success_response_and_citations():
    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_success_payload(),
            headers={"x-request-id": "doubao-provider-1"},
        )
    )

    answer = asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert route.called
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer sk-doubao-test"
    assert request.headers["x-request-id"] == "req-doubao-1"
    payload = _request_json(request)
    assert payload["model"] == "doubao-pro-32k"
    assert payload["messages"] == [
        {"role": "system", "content": "你是监测助手"},
        {"role": "user", "content": "请总结 GEO 平台"},
    ]
    assert answer.text == "豆包回答"
    assert answer.model == "doubao-pro-32k"
    assert answer.usage["total_tokens"] == 15
    assert answer.provider_request_id == "doubao-provider-1"
    assert answer.raw_response == _success_payload()
    assert answer.citations == [
        {
            "title": "官方文档",
            "url": "https://example.com/doubao",
            "quoted_text": "引用原文",
        }
    ]


@respx.mock
def test_doubao_omits_raw_response_when_disabled():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_success_payload())
    )

    answer = asyncio.run(
        _adapter(raw_response_enabled=False).query(_query(), credential=_credential())
    )

    assert answer.raw_response is None


@respx.mock
def test_doubao_maps_timeout_to_network_error():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.NETWORK_ERROR
    assert "sk-doubao-test" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (429, ErrorCategory.RATE_LIMITED),
        (401, ErrorCategory.UNAUTHORIZED),
        (502, ErrorCategory.SERVER_ERROR),
    ],
)
@respx.mock
def test_doubao_maps_http_errors(status_code: int, expected: ErrorCategory):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            status_code,
            json={"error": {"message": "provider rejected request"}},
            headers={"retry-after": "3"},
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == expected
    assert exc_info.value.status_code == status_code
    if status_code == 429:
        assert exc_info.value.retry_after_seconds == 3


@respx.mock
def test_doubao_rejects_empty_answer():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_success_payload(content=""))
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST
