"""模力指数 Business API 适配器。"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import settings
from app.geo_monitoring.adapters.base import (
    PlatformAnswer,
    PlatformCredential,
    PlatformQuery,
)
from app.geo_monitoring.adapters.errors import (
    AdapterError,
    ErrorCategory,
    classify_http_status,
    classify_molizhishu_error,
)

_PENDING_STATUSES = frozenset({"pending", "assigned", "processing"})
_TERMINAL_FAILURE_STATUSES = frozenset({"failed", "error"})


class MolizhishuPendingError(AdapterError):
    """模力指数子任务仍在执行，携带后续轮询所需状态。"""

    def __init__(self, *, pending_metadata: dict[str, Any]) -> None:
        self.pending_metadata = pending_metadata
        super().__init__(
            "molizhishu result is still pending",
            category=ErrorCategory.PENDING,
        )


class MolizhishuAdapter:
    def __init__(
        self,
        *,
        code: str,
        molizhishu_platform: str,
        default_mode: str,
        base_url: str = settings.MOLIZHISHU_BASE_URL,
        timeout_seconds: float = settings.MOLIZHISHU_REQUEST_TIMEOUT_SECONDS,
        raw_response_enabled: bool = settings.COLLECTION_RAW_RESPONSE_ENABLED,
    ) -> None:
        self.code = code
        self._molizhishu_platform = molizhishu_platform
        self._default_mode = default_mode
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._raw_response_enabled = raw_response_enabled

    async def query(
        self,
        request: PlatformQuery,
        *,
        credential: PlatformCredential,
    ) -> PlatformAnswer:
        """调用模力指数 batch/result API 并返回统一答案结构。"""
        api_key = _require_api_key(credential)
        started = time.perf_counter()
        metadata = request.metadata
        mode = _resolve_mode(metadata, self._default_mode)
        screenshot = _resolve_screenshot(metadata)
        region_code = _metadata_text(metadata, "region_code")
        task_id = _metadata_text(metadata, "molizhishu_task_id")
        subtask_id = _metadata_text(metadata, "molizhishu_subtask_id")
        if subtask_id and not task_id:
            raise AdapterError(
                "molizhishu metadata missing taskId for existing subTaskId",
                category=ErrorCategory.INVALID_REQUEST,
                secrets=(api_key,),
            )
        submit_data: dict[str, Any] | None = None

        if not subtask_id:
            submit_data = await self._submit_task(
                request.prompt,
                api_key=api_key,
                mode=mode,
                screenshot=screenshot,
                region_code=region_code,
            )
            task_id = _extract_task_id(submit_data)
            subtask_id = _extract_subtask_id(submit_data)

        result_data = await self._get_result(
            task_id,
            subtask_id,
            api_key=api_key,
        )
        status = _result_status(result_data)
        pending_metadata = {
            "molizhishu_task_id": task_id,
            "molizhishu_subtask_id": subtask_id,
            "molizhishu_platform": self._molizhishu_platform,
            "molizhishu_mode": mode,
            "molizhishu_status": status or "unknown",
        }
        if status in _PENDING_STATUSES:
            raise MolizhishuPendingError(pending_metadata=pending_metadata)
        if status == "stopped":
            error_message = _result_error_message(result_data)
            raise AdapterError(
                f"molizhishu subtask stopped: {error_message}",
                category=ErrorCategory.CANCELLED,
                secrets=(api_key,),
            )
        if status in _TERMINAL_FAILURE_STATUSES:
            error_message = _result_error_message(result_data)
            raise AdapterError(
                f"molizhishu subtask failed: {error_message}",
                category=ErrorCategory.INVALID_REQUEST,
                secrets=(api_key,),
            )
        if status != "completed":
            raise AdapterError(
                f"molizhishu returned unsupported status: {status or 'unknown'}",
                category=ErrorCategory.UNKNOWN,
                secrets=(api_key,),
            )

        text = _extract_answer_content(result_data)
        if not text.strip():
            raise AdapterError(
                "molizhishu returned empty answer",
                category=ErrorCategory.INVALID_REQUEST,
                secrets=(api_key,),
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        raw_response = None
        if self._raw_response_enabled:
            raw_response = {"submit": submit_data, "result": result_data}
        return PlatformAnswer(
            text=text,
            citations=_extract_citations(result_data),
            model=request.model or f"molizhishu:{self._molizhishu_platform}",
            usage={},
            latency_ms=latency_ms,
            provider_request_id=subtask_id,
            raw_response=raw_response,
        )

    async def _submit_task(
        self,
        prompt: str,
        *,
        api_key: str,
        mode: str,
        screenshot: int,
        region_code: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "promptList": [prompt],
            "platformList": [
                {
                    "platform": self._molizhishu_platform,
                    "mode": mode,
                    "screenshot": screenshot,
                }
            ],
        }
        if region_code:
            payload["regionCode"] = [region_code]
        response = await _request(
            "POST",
            f"{self._base_url}/task/batch/shared",
            api_key=api_key,
            timeout_seconds=self._timeout_seconds,
            json_payload=payload,
        )
        data = _json_response(response, api_key=api_key)
        _raise_for_envelope(response, data, api_key=api_key)
        return data

    async def _get_result(
        self,
        task_id: str,
        subtask_id: str,
        *,
        api_key: str,
    ) -> dict[str, Any]:
        response = await _request(
            "GET",
            f"{self._base_url}/task/result/{task_id}/{subtask_id}",
            api_key=api_key,
            timeout_seconds=self._timeout_seconds,
        )
        data = _json_response(response, api_key=api_key)
        _raise_for_envelope(response, data, api_key=api_key)
        return data


def _require_api_key(credential: PlatformCredential) -> str:
    if not credential.api_key:
        raise AdapterError(
            "molizhishu api token is required",
            category=ErrorCategory.UNAUTHORIZED,
        )
    return credential.api_key


async def _request(
    method: str,
    url: str,
    *,
    api_key: str,
    timeout_seconds: float,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            return await client.request(
                method,
                url,
                json=json_payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.TimeoutException as exc:
        raise AdapterError(
            "molizhishu request timed out",
            category=ErrorCategory.NETWORK_ERROR,
            secrets=(api_key,),
        ) from exc
    except httpx.RequestError as exc:
        raise AdapterError(
            f"molizhishu request failed: {exc}",
            category=ErrorCategory.NETWORK_ERROR,
            secrets=(api_key,),
        ) from exc


def _json_response(response: httpx.Response, *, api_key: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise AdapterError(
            "molizhishu returned non-json response",
            category=classify_http_status(response.status_code, message=response.text),
            status_code=response.status_code,
            secrets=(api_key,),
        ) from exc
    return data if isinstance(data, dict) else {"data": data}


def _raise_for_envelope(
    response: httpx.Response,
    data: dict[str, Any],
    *,
    api_key: str,
) -> None:
    message = str(data.get("message") or data.get("msg") or data)
    business_code = data.get("code")
    if response.status_code >= 400:
        category = classify_http_status(response.status_code, message=message)
        if category == ErrorCategory.INVALID_REQUEST:
            category = classify_molizhishu_error(message=message, code=business_code)
        raise AdapterError(
            f"molizhishu request failed: {message}",
            category=category,
            status_code=response.status_code,
            secrets=(api_key,),
        )
    if data.get("success") is True and data.get("code") == 200:
        return
    category = classify_molizhishu_error(message=message, code=business_code)
    raise AdapterError(
        f"molizhishu request failed: {message}",
        category=category,
        status_code=response.status_code,
        secrets=(api_key,),
    )


def _extract_task_id(data: dict[str, Any]) -> str:
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    task_id = payload.get("taskId") if isinstance(payload, dict) else None
    if not isinstance(task_id, str) or not task_id.strip():
        raise AdapterError(
            "molizhishu response missing taskId",
            category=ErrorCategory.INVALID_REQUEST,
        )
    return task_id.strip()


def _extract_subtask_id(data: dict[str, Any]) -> str:
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    subtasks = payload.get("subTaskList") if isinstance(payload, dict) else None
    if not isinstance(subtasks, list) or not subtasks:
        raise AdapterError(
            "molizhishu response missing subTaskList",
            category=ErrorCategory.INVALID_REQUEST,
        )
    first = subtasks[0]
    if not isinstance(first, dict):
        raise AdapterError(
            "molizhishu response missing subTaskId",
            category=ErrorCategory.INVALID_REQUEST,
        )
    subtask_id = first.get("subTaskId")
    if not isinstance(subtask_id, str) or not subtask_id.strip():
        raise AdapterError(
            "molizhishu response missing subTaskId",
            category=ErrorCategory.INVALID_REQUEST,
        )
    return subtask_id.strip()


def _result_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = data.get("data")
    return payload if isinstance(payload, dict) else {}


def _result_status(data: dict[str, Any]) -> str | None:
    status = _result_payload(data).get("status")
    return status if isinstance(status, str) else None


def _result_error_message(data: dict[str, Any]) -> str:
    message = _result_payload(data).get("errorMessage")
    if isinstance(message, str) and message.strip():
        return message.strip()
    status = _result_status(data) or "unknown"
    return f"status={status}"


def _extract_answer_content(data: dict[str, Any]) -> str:
    content = _result_payload(data).get("answerContent")
    return content if isinstance(content, str) else ""


def _extract_citations(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _result_payload(data)
    citations = _map_citation_list(payload.get("citationList"))
    if citations:
        return citations
    return _map_reference_list(payload.get("referenceList"))


def _map_citation_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    citations: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        snippet = item.get("snippet")
        citations.append(
            {
                "url": _text_or_none(item.get("url")),
                "title": _text_or_none(item.get("title")),
                "snippet": _text_or_none(snippet),
                "quoted_text": _text_or_none(snippet),
                "source_type": "web",
                "site_name": _text_or_none(item.get("siteName") or item.get("site")),
            }
        )
    return citations


def _map_reference_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    citations: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        summary = item.get("summary")
        citations.append(
            {
                "url": _text_or_none(item.get("url")),
                "title": _text_or_none(item.get("title")),
                "snippet": _text_or_none(summary),
                "quoted_text": _text_or_none(summary),
                "source_type": "web",
                "site_name": _text_or_none(item.get("site") or item.get("siteName")),
            }
        )
    return citations


def _resolve_mode(metadata: dict[str, Any], default_mode: str) -> str:
    for key in ("provider_mode", "molizhishu_mode"):
        value = _metadata_text(metadata, key)
        if value:
            return value
    return default_mode


def _resolve_screenshot(metadata: dict[str, Any]) -> int:
    value = metadata.get("provider_screenshot")
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _text_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
