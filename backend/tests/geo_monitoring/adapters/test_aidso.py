"""Aidso OpenAPI 适配器测试。"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from app.geo_monitoring.adapters.aidso import AidsoAdapter, AidsoPendingError
from app.geo_monitoring.adapters.base import PlatformCredential, PlatformQuery
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory

BASE_URL = "https://aidso.test"


def _query(metadata: dict | None = None) -> PlatformQuery:
    return PlatformQuery(
        prompt="100w汽车推荐",
        system_prompt=None,
        model="aidso:DB",
        temperature=None,
        request_id="task-1",
        metadata=metadata or {"aidso_thinking_enabled": False},
    )


def _credential() -> PlatformCredential:
    return PlatformCredential(
        platform_code="aidso_doubao_web",
        fingerprint="fp-aidso",
        api_key="aidso-token",
    )


def _adapter(*, raw_response_enabled: bool = True) -> AidsoAdapter:
    return AidsoAdapter(
        code="aidso_doubao_web",
        aidso_name="DB",
        base_url=BASE_URL,
        timeout_seconds=0.2,
        raw_response_enabled=raw_response_enabled,
    )


def _success_payload() -> dict:
    return {
        "code": 200,
        "data": {
            "prompt": "100w汽车推荐",
            "status": "SUCCESS",
            "result": [
                {"search_word": ""},
                {
                    "quote": json.dumps(
                        [
                            {
                                "url": "https://example.com/a",
                                "title": "引用标题",
                                "snippet": "摘要",
                                "site_name": "Example",
                                "platform": "DP",
                            }
                        ],
                        ensure_ascii=False,
                    )
                },
                {"context": "推荐目标品牌。FINISHED"},
                {"suggestions": ""},
            ],
        },
        "msg": "success",
    }


@respx.mock
def test_aidso_submits_then_polls_success_response():
    commit_route = respx.post(f"{BASE_URL}/open/mt/task_commit").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "reqIds": {"DB": "req-db-1"},
                    "taskId": "task-aidso-1",
                },
                "msg": "ok",
            },
        )
    )
    result_route = respx.get(f"{BASE_URL}/open/mt/get_result").mock(
        return_value=httpx.Response(200, json=_success_payload())
    )

    answer = asyncio.run(_adapter().query(_query(), credential=_credential()))

    payload = json.loads(commit_route.calls.last.request.content.decode("utf-8"))
    assert commit_route.calls.last.request.headers["authorization"] == "aidso-token"
    assert payload == {
        "prompt": "100w汽车推荐",
        "platform": [{"name": "DB", "thinkingEnabled": 0}],
    }
    assert result_route.calls.last.request.url.params["reqId"] == "req-db-1"
    assert answer.text == "推荐目标品牌。FINISHED"
    assert answer.model == "aidso:DB"
    assert answer.usage == {}
    assert answer.provider_request_id == "req-db-1"
    assert answer.citations == [
        {
            "url": "https://example.com/a",
            "title": "引用标题",
            "snippet": "摘要",
            "quoted_text": "摘要",
            "source_type": "web",
            "site_name": "Example",
        }
    ]
    assert answer.raw_response["commit"]["data"]["taskId"] == "task-aidso-1"
    assert answer.raw_response["result"] == _success_payload()


@respx.mock
def test_aidso_reuses_existing_req_id_without_resubmitting():
    commit_route = respx.post(f"{BASE_URL}/open/mt/task_commit").mock(
        return_value=httpx.Response(500, json={"msg": "should not be called"})
    )
    result_route = respx.get(f"{BASE_URL}/open/mt/get_result").mock(
        return_value=httpx.Response(200, json=_success_payload())
    )

    answer = asyncio.run(
        _adapter().query(
            _query({"aidso_req_id": "req-existing", "aidso_thinking_enabled": True}),
            credential=_credential(),
        )
    )

    assert not commit_route.called
    assert result_route.calls.last.request.url.params["reqId"] == "req-existing"
    assert answer.provider_request_id == "req-existing"


@respx.mock
def test_aidso_pending_result_carries_retry_metadata():
    respx.post(f"{BASE_URL}/open/mt/task_commit").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {"reqIds": {"DB": "req-db-1"}, "taskId": "task-aidso-1"},
                "msg": "ok",
            },
        )
    )
    respx.get(f"{BASE_URL}/open/mt/get_result").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {"prompt": "100w汽车推荐", "result": [], "status": "ING"},
                "msg": "success",
            },
        )
    )

    with pytest.raises(AidsoPendingError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    error = exc_info.value
    assert error.category == ErrorCategory.PENDING
    assert error.pending_metadata == {
        "aidso_req_id": "req-db-1",
        "aidso_task_id": "task-aidso-1",
        "aidso_platform_name": "DB",
        "aidso_thinking_enabled": False,
    }


@respx.mock
def test_aidso_errors_do_not_leak_token():
    respx.post(f"{BASE_URL}/open/mt/task_commit").mock(
        return_value=httpx.Response(401, json={"code": 400, "msg": "bad token"})
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.UNAUTHORIZED
    assert "aidso-token" not in str(exc_info.value)
