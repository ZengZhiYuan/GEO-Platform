"""腾讯元宝到腾讯混元官方 API 映射适配器测试。"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from app.geo_monitoring.adapters.base import PlatformCredential, PlatformQuery
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory
from app.geo_monitoring.adapters.key_pool import YuanbaoCredential
from app.geo_monitoring.adapters.yuanbao import YuanbaoAdapter


BASE_URL = "https://hunyuan.tencentcloudapi.test"


def _query() -> PlatformQuery:
    return PlatformQuery(
        prompt="请总结 GEO 平台",
        system_prompt="你是监测助手",
        model="hunyuan-turbo",
        temperature=0.4,
        request_id="req-yuanbao-1",
    )


def _credential() -> PlatformCredential:
    return YuanbaoCredential(
        platform_code="yuanbao",
        secret_id="tc-secret-id-test",
        secret_key="tc-secret-key-test",
    ).to_platform_credential()


def _adapter(*, raw_response_enabled: bool = True) -> YuanbaoAdapter:
    return YuanbaoAdapter(
        base_url=BASE_URL,
        timeout_seconds=0.1,
        raw_response_enabled=raw_response_enabled,
        region="ap-guangzhou",
    )


def _request_json(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def _success_payload(content: str = "混元回答") -> dict:
    return {
        "Response": {
            "RequestId": "hunyuan-provider-1",
            "Choices": [
                {
                    "Message": {
                        "Content": content,
                    }
                }
            ],
            "Usage": {
                "PromptTokens": 11,
                "CompletionTokens": 6,
                "TotalTokens": 17,
            },
        }
    }


@respx.mock
def test_yuanbao_calls_hunyuan_with_tencent_credentials():
    route = respx.post(BASE_URL).mock(
        return_value=httpx.Response(200, json=_success_payload())
    )

    answer = asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert route.called
    request = route.calls.last.request
    assert request.headers["x-tc-action"] == "ChatCompletions"
    assert request.headers["x-tc-version"] == "2023-09-01"
    assert request.headers["x-tc-region"] == "ap-guangzhou"
    assert request.headers["x-request-id"] == "req-yuanbao-1"
    assert "TC3-HMAC-SHA256" in request.headers["authorization"]
    assert "tc-secret-key-test" not in request.headers["authorization"]
    payload = _request_json(request)
    assert payload == {
        "Model": "hunyuan-turbo",
        "Messages": [
            {"Role": "system", "Content": "你是监测助手"},
            {"Role": "user", "Content": "请总结 GEO 平台"},
        ],
        "Stream": False,
        "Temperature": 0.4,
    }
    assert answer.text == "混元回答"
    assert answer.model == "hunyuan-turbo"
    assert answer.usage == {
        "prompt_tokens": 11,
        "completion_tokens": 6,
        "total_tokens": 17,
    }
    assert answer.provider_request_id == "hunyuan-provider-1"
    assert answer.raw_response == _success_payload()
    assert answer.citations == []


@respx.mock
def test_yuanbao_can_omit_raw_response():
    respx.post(BASE_URL).mock(return_value=httpx.Response(200, json=_success_payload()))

    answer = asyncio.run(
        _adapter(raw_response_enabled=False).query(_query(), credential=_credential())
    )

    assert answer.raw_response is None


@respx.mock
def test_yuanbao_maps_timeout_to_network_error():
    respx.post(BASE_URL).mock(side_effect=httpx.TimeoutException("timeout"))

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.NETWORK_ERROR
    assert "tc-secret-id-test" not in str(exc_info.value)
    assert "tc-secret-key-test" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (429, ErrorCategory.RATE_LIMITED),
        (401, ErrorCategory.UNAUTHORIZED),
        (500, ErrorCategory.SERVER_ERROR),
    ],
)
@respx.mock
def test_yuanbao_maps_hunyuan_http_errors(status_code: int, expected: ErrorCategory):
    respx.post(BASE_URL).mock(
        return_value=httpx.Response(
            status_code,
            json={
                "Response": {
                    "Error": {
                        "Code": "AuthFailure.SignatureFailure",
                        "Message": "provider rejected request",
                    },
                    "RequestId": "hunyuan-error-1",
                }
            },
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == expected
    assert exc_info.value.status_code == status_code
    assert "tc-secret-key-test" not in str(exc_info.value)


@respx.mock
def test_yuanbao_rejects_empty_answer():
    respx.post(BASE_URL).mock(
        return_value=httpx.Response(200, json=_success_payload(content=""))
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST
