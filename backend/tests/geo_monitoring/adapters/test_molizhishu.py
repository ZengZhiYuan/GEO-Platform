"""模力指数 OpenAPI 适配器测试。"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from app.geo_monitoring.adapters.base import (
    PlatformAdapter,
    PlatformCredential,
    PlatformQuery,
)
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory
from app.geo_monitoring.adapters.molizhishu import MolizhishuPendingError

BASE_URL = "https://molizhishu.test"


def _query(metadata: dict | None = None) -> PlatformQuery:
    return PlatformQuery(
        prompt="100w汽车推荐",
        system_prompt=None,
        model="molizhishu:doubao",
        temperature=None,
        request_id="task-1",
        metadata=metadata or {"provider_mode": "search", "provider_screenshot": 0},
    )


def _credential() -> PlatformCredential:
    return PlatformCredential(
        platform_code="molizhishu_doubao_web",
        fingerprint="fp-molizhishu",
        api_key="molizhishu-token",
    )


def _adapter(*, raw_response_enabled: bool = True):
    from app.geo_monitoring.adapters.molizhishu import MolizhishuAdapter

    return MolizhishuAdapter(
        code="molizhishu_doubao_web",
        molizhishu_platform="doubao",
        default_mode="search",
        base_url=BASE_URL,
        timeout_seconds=0.2,
        raw_response_enabled=raw_response_enabled,
    )


def _submit_payload() -> dict:
    return {
        "success": True,
        "code": 200,
        "message": "ok",
        "data": {
            "taskId": "task-mlz-1",
            "subTaskList": [
                {
                    "subTaskId": "sub-1",
                    "platform": "doubao",
                    "status": "pending",
                }
            ],
        },
    }


def _completed_result_payload() -> dict:
    return {
        "success": True,
        "code": 200,
        "message": "ok",
        "data": {
            "status": "completed",
            "answerContent": "推荐目标品牌。",
            "citationList": [
                {
                    "url": "https://example.com/a",
                    "title": "引用标题",
                    "snippet": "摘要",
                    "siteName": "Example",
                }
            ],
        },
    }


def test_molizhishu_adapter_satisfies_platform_adapter_protocol():
    from app.geo_monitoring.adapters.molizhishu import MolizhishuAdapter

    assert isinstance(_adapter(), PlatformAdapter)
    assert isinstance(MolizhishuAdapter, type)


@respx.mock
def test_molizhishu_submits_then_pending_carries_metadata():
    from app.geo_monitoring.adapters.molizhishu import MolizhishuPendingError

    submit_route = respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    result_route = respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {"status": "processing"},
            },
        )
    )

    with pytest.raises(MolizhishuPendingError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    payload = json.loads(submit_route.calls.last.request.content.decode("utf-8"))
    assert (
        submit_route.calls.last.request.headers["authorization"]
        == "Bearer molizhishu-token"
    )
    assert payload == {
        "prompts": ["100w汽车推荐"],
        "platforms": [
            {"platform": "doubao", "mode": "search", "screenshot": 0},
        ],
    }
    assert result_route.called
    error = exc_info.value
    assert error.category == ErrorCategory.PENDING
    assert error.pending_metadata == {
        "molizhishu_task_id": "task-mlz-1",
        "molizhishu_subtask_id": "sub-1",
        "molizhishu_platform": "doubao",
        "molizhishu_mode": "search",
        "molizhishu_status": "processing",
    }


@respx.mock
def test_molizhishu_reuses_existing_task_and_subtask_without_resubmitting():
    submit_route = respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            500, json={"success": False, "code": 500, "message": "no"}
        )
    )
    result_route = respx.get(f"{BASE_URL}/task/result/task-existing/sub-existing").mock(
        return_value=httpx.Response(200, json=_completed_result_payload())
    )

    answer = asyncio.run(
        _adapter().query(
            _query(
                {
                    "molizhishu_task_id": "task-existing",
                    "molizhishu_subtask_id": "sub-existing",
                    "provider_mode": "search",
                }
            ),
            credential=_credential(),
        )
    )

    assert not submit_route.called
    assert result_route.called
    assert answer.text == "推荐目标品牌。"
    assert answer.provider_request_id == "sub-existing"
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


@respx.mock
def test_molizhishu_completed_returns_answer_and_citations():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(200, json=_completed_result_payload())
    )

    answer = asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert answer.text == "推荐目标品牌。"
    assert answer.model == "molizhishu:doubao"
    assert answer.provider_request_id == "sub-1"
    assert answer.raw_response["submit"]["data"]["taskId"] == "task-mlz-1"
    assert answer.raw_response["result"]["data"]["status"] == "completed"


@respx.mock
def test_molizhishu_uses_reference_list_when_citation_list_empty():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {
                    "status": "completed",
                    "answerContent": "有引用",
                    "citationList": [],
                    "referenceList": [
                        {
                            "url": "https://example.com/ref",
                            "title": "参考标题",
                            "summary": "参考摘要",
                            "site": "RefSite",
                        }
                    ],
                },
            },
        )
    )

    answer = asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert answer.citations == [
        {
            "url": "https://example.com/ref",
            "title": "参考标题",
            "snippet": "参考摘要",
            "quoted_text": "参考摘要",
            "source_type": "web",
            "site_name": "RefSite",
        }
    ]


@respx.mock
def test_molizhishu_http_200_business_failure_is_rejected():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            200,
            json={"success": False, "code": 40001, "message": "参数错误"},
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST


@respx.mock
def test_molizhishu_token_expired_is_unauthorized():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            200,
            json={"success": False, "code": 40101, "message": "Token失效"},
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.UNAUTHORIZED
    assert "molizhishu-token" not in str(exc_info.value)


@respx.mock
def test_molizhishu_insufficient_balance_is_non_retryable():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            200,
            json={"success": False, "code": 40201, "message": "余额不足"},
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST


@respx.mock
def test_molizhishu_non_json_response_is_classified():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, text="not-json")
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category in {
        ErrorCategory.INVALID_REQUEST,
        ErrorCategory.UNKNOWN,
    }
    assert "molizhishu-token" not in str(exc_info.value)


@respx.mock
def test_molizhishu_result_non_json_during_poll_raises_pending_then_completes():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    result_route = respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1")
    call_count = {"n": 0}

    def result_side_effect(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(200, text="not-json")
        return httpx.Response(200, json=_completed_result_payload())

    result_route.mock(side_effect=result_side_effect)

    with pytest.raises(MolizhishuPendingError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.pending_metadata["molizhishu_task_id"] == "task-mlz-1"
    assert exc_info.value.pending_metadata["molizhishu_subtask_id"] == "sub-1"

    answer = asyncio.run(
        _adapter().query(
            _query(
                {
                    "molizhishu_task_id": "task-mlz-1",
                    "molizhishu_subtask_id": "sub-1",
                    "molizhishu_status": "processing",
                    "provider_mode": "search",
                }
            ),
            credential=_credential(),
        )
    )

    assert answer.text == "推荐目标品牌。"
    assert call_count["n"] == 2


@respx.mock
def test_molizhishu_processing_with_answer_content_returns_completed():
    """生产口径：provider status 滞后时，answerContent 非空即视为成功。"""
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {
                    "status": "processing",
                    "answerContent": "推荐目标品牌。",
                    "citationList": [],
                },
            },
        )
    )

    answer = asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert answer.text == "推荐目标品牌。"


@respx.mock
def test_molizhishu_timeout_is_network_error():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        side_effect=httpx.ReadTimeout("timed out")
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.NETWORK_ERROR


@pytest.mark.parametrize("status", ["failed", "error"])
@respx.mock
def test_molizhishu_terminal_failure_status_raises_adapter_error(status: str):
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {
                    "status": status,
                    "errorMessage": f"provider {status}",
                },
            },
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST
    assert f"provider {status}" in str(exc_info.value)
    assert "molizhishu-token" not in str(exc_info.value)


@respx.mock
def test_molizhishu_stopped_maps_to_cancelled():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {
                    "status": "stopped",
                    "errorMessage": "provider stopped",
                },
            },
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.CANCELLED
    assert "provider stopped" in str(exc_info.value)


@respx.mock
def test_molizhishu_token_expired_by_business_code_without_message_hint():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            200,
            json={"success": False, "code": 40101, "message": "鉴权失败"},
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.UNAUTHORIZED


@respx.mock
def test_molizhishu_insufficient_balance_by_business_code_without_message_hint():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            200,
            json={"success": False, "code": 40201, "message": "账户异常"},
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST


@respx.mock
def test_molizhishu_http_401_envelope_uses_unauthorized_category():
    respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(
            401,
            json={"success": False, "code": 40101, "message": "鉴权失败"},
        )
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    assert exc_info.value.category == ErrorCategory.UNAUTHORIZED
    assert exc_info.value.status_code == 401


@respx.mock
def test_molizhishu_reuse_requires_task_id_when_subtask_id_present():
    result_route = respx.get(f"{BASE_URL}/task/result/None/sub-existing").mock(
        return_value=httpx.Response(200, json=_completed_result_payload())
    )

    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(
            _adapter().query(
                _query(
                    {"molizhishu_subtask_id": "sub-existing", "provider_mode": "search"}
                ),
                credential=_credential(),
            )
        )

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST
    assert "missing taskId" in str(exc_info.value)
    assert not result_route.called


@respx.mock
def test_molizhishu_stop_task_calls_put_endpoint():
    stop_route = respx.put(f"{BASE_URL}/task/task-mlz-1/stop").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "code": 200, "message": "ok"},
        )
    )

    asyncio.run(_adapter().stop_task("task-mlz-1", credential=_credential()))

    assert stop_route.called
    request = stop_route.calls[0].request
    assert request.headers["Authorization"] == "Bearer molizhishu-token"


@respx.mock
def test_molizhishu_submit_includes_region_code_when_provided():
    submit_route = respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {"status": "processing"},
            },
        )
    )
    from app.geo_monitoring.adapters.molizhishu import MolizhishuPendingError

    with pytest.raises(MolizhishuPendingError):
        asyncio.run(
            _adapter().query(
                _query({"provider_mode": "search", "region_code": "110000"}),
                credential=_credential(),
            )
        )

    payload = json.loads(submit_route.calls.last.request.content.decode("utf-8"))
    assert payload["regionCode"] == ["110000"]


@respx.mock
def test_molizhishu_submit_omits_region_code_when_not_provided():
    submit_route = respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {"status": "processing"},
            },
        )
    )
    from app.geo_monitoring.adapters.molizhishu import MolizhishuPendingError

    with pytest.raises(MolizhishuPendingError):
        asyncio.run(_adapter().query(_query(), credential=_credential()))

    payload = json.loads(submit_route.calls.last.request.content.decode("utf-8"))
    assert "regionCode" not in payload


@respx.mock
def test_molizhishu_submit_includes_screenshot_when_provided():
    submit_route = respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {"status": "processing"},
            },
        )
    )
    from app.geo_monitoring.adapters.molizhishu import MolizhishuPendingError

    with pytest.raises(MolizhishuPendingError):
        asyncio.run(
            _adapter().query(
                _query({"provider_mode": "search", "provider_screenshot": 2}),
                credential=_credential(),
            )
        )

    payload = json.loads(submit_route.calls.last.request.content.decode("utf-8"))
    assert payload["platforms"][0]["screenshot"] == 2


@respx.mock
def test_molizhishu_rejects_bool_provider_screenshot():
    with pytest.raises(AdapterError) as exc_info:
        asyncio.run(
            _adapter().query(
                _query({"provider_mode": "search", "provider_screenshot": True}),
                credential=_credential(),
            )
        )

    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST


@respx.mock
def test_molizhishu_submit_includes_callback_headers_when_enabled(monkeypatch):
    monkeypatch.setattr(
        "app.geo_monitoring.adapters.molizhishu.settings.MOLIZHISHU_CALLBACK_ENABLED",
        True,
    )
    monkeypatch.setattr(
        "app.geo_monitoring.adapters.molizhishu.settings.MOLIZHISHU_CALLBACK_TOKEN",
        "cb-secret",
    )
    submit_route = respx.post(f"{BASE_URL}/task/batch/shared").mock(
        return_value=httpx.Response(200, json=_submit_payload())
    )
    respx.get(f"{BASE_URL}/task/result/task-mlz-1/sub-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "code": 200,
                "message": "ok",
                "data": {"status": "processing"},
            },
        )
    )
    from app.geo_monitoring.adapters.molizhishu import MolizhishuPendingError

    with pytest.raises(MolizhishuPendingError):
        asyncio.run(
            _adapter().query(
                _query(
                    {
                        "provider_mode": "search",
                        "provider_callback_url": (
                            "https://api.example.com/api/geo-monitoring/"
                            "provider-callbacks/molizhishu?token=must-strip"
                        ),
                    }
                ),
                credential=_credential(),
            )
        )

    payload = json.loads(submit_route.calls.last.request.content.decode("utf-8"))
    assert payload["callbackUrl"] == (
        "https://api.example.com/api/geo-monitoring/provider-callbacks/molizhishu"
    )
    assert payload["callbackHeaders"] == {"X-Callback-Token": "cb-secret"}
    assert "token=" not in payload["callbackUrl"]
