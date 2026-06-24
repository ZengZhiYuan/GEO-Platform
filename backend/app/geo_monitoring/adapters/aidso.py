"""Aidso OpenAPI collection adapter."""

from __future__ import annotations

import json
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
)


class AidsoPendingError(AdapterError):
    """Aidso 结果仍在生成，携带后续轮询所需状态。"""

    def __init__(self, *, pending_metadata: dict[str, Any]) -> None:
        self.pending_metadata = pending_metadata
        super().__init__(
            "aidso result is still pending",
            category=ErrorCategory.PENDING,
        )


class AidsoAdapter:
    # 初始化 Aidso 端侧适配器配置
    def __init__(
        self,
        *,
        code: str,
        aidso_name: str,
        base_url: str = settings.AIDSO_BASE_URL,
        timeout_seconds: float = settings.COLLECTION_REQUEST_TIMEOUT_SECONDS,
        raw_response_enabled: bool = settings.COLLECTION_RAW_RESPONSE_ENABLED,
    ) -> None:
        self.code = code
        self._aidso_name = aidso_name
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._raw_response_enabled = raw_response_enabled

    async def query(
        self,
        request: PlatformQuery,
        *,
        credential: PlatformCredential,
    ) -> PlatformAnswer:
        """调用 Aidso OpenAPI 并返回统一答案结构。"""
        api_key = _require_api_key(credential)
        started = time.perf_counter()
        req_id = _metadata_text(request.metadata, "aidso_req_id")
        task_id = _metadata_text(request.metadata, "aidso_task_id")
        thinking_enabled = bool(request.metadata.get("aidso_thinking_enabled", True))
        commit_data: dict[str, Any] | None = None

        if not req_id:
            commit_data = await self._submit_task(
                request.prompt,
                api_key=api_key,
                thinking_enabled=thinking_enabled,
            )
            req_id = _extract_req_id(commit_data, self._aidso_name)
            task_id = _extract_task_id(commit_data)

        result_data = await self._get_result(req_id, api_key=api_key)
        status = _result_status(result_data)
        pending_metadata = {
            "aidso_req_id": req_id,
            "aidso_task_id": task_id,
            "aidso_platform_name": self._aidso_name,
            "aidso_thinking_enabled": thinking_enabled,
        }
        if status == "ING":
            raise AidsoPendingError(pending_metadata=pending_metadata)
        if status != "SUCCESS":
            raise AdapterError(
                f"aidso returned unsupported status: {status or 'unknown'}",
                category=ErrorCategory.UNKNOWN,
                secrets=(api_key,),
            )

        text = _extract_context(result_data)
        if not text.strip():
            raise AdapterError(
                "aidso returned empty answer",
                category=ErrorCategory.INVALID_REQUEST,
                secrets=(api_key,),
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        raw_response = None
        if self._raw_response_enabled:
            raw_response = {"commit": commit_data, "result": result_data}
        return PlatformAnswer(
            text=text,
            citations=_extract_citations(result_data),
            model=request.model or f"aidso:{self._aidso_name}",
            usage={},
            latency_ms=latency_ms,
            provider_request_id=req_id,
            raw_response=raw_response,
        )

    async def _submit_task(
        self,
        prompt: str,
        *,
        api_key: str,
        thinking_enabled: bool,
    ) -> dict[str, Any]:
        payload = {
            "prompt": prompt,
            "platform": [
                {
                    "name": self._aidso_name,
                    "thinkingEnabled": 1 if thinking_enabled else 0,
                }
            ],
        }
        response = await _request(
            "POST",
            f"{self._base_url}/open/mt/task_commit",
            api_key=api_key,
            timeout_seconds=self._timeout_seconds,
            json_payload=payload,
        )
        data = _json_response(response, api_key=api_key)
        _raise_for_error(response, data, api_key=api_key)
        return data

    async def _get_result(self, req_id: str, *, api_key: str) -> dict[str, Any]:
        response = await _request(
            "GET",
            f"{self._base_url}/open/mt/get_result",
            api_key=api_key,
            timeout_seconds=self._timeout_seconds,
            params={"reqId": req_id},
        )
        data = _json_response(response, api_key=api_key)
        _raise_for_error(response, data, api_key=api_key)
        return data


def _require_api_key(credential: PlatformCredential) -> str:
    if not credential.api_key:
        raise AdapterError(
            "aidso api token is required",
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
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            return await client.request(
                method,
                url,
                json=json_payload,
                params=params,
                headers={
                    "Authorization": api_key,
                    "Content-Type": "application/json",
                },
            )
    except httpx.TimeoutException as exc:
        raise AdapterError(
            "aidso request timed out",
            category=ErrorCategory.NETWORK_ERROR,
            secrets=(api_key,),
        ) from exc
    except httpx.RequestError as exc:
        raise AdapterError(
            f"aidso request failed: {exc}",
            category=ErrorCategory.NETWORK_ERROR,
            secrets=(api_key,),
        ) from exc


def _json_response(response: httpx.Response, *, api_key: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise AdapterError(
            "aidso returned non-json response",
            category=classify_http_status(response.status_code, message=response.text),
            status_code=response.status_code,
            secrets=(api_key,),
        ) from exc
    return data if isinstance(data, dict) else {"data": data}


def _raise_for_error(
    response: httpx.Response,
    data: dict[str, Any],
    *,
    api_key: str,
) -> None:
    code = data.get("code")
    if response.status_code < 400 and code == 200:
        return
    message = str(data.get("msg") or data.get("message") or data)
    category = (
        classify_http_status(response.status_code, message=message)
        if response.status_code >= 400
        else ErrorCategory.INVALID_REQUEST
    )
    raise AdapterError(
        f"aidso request failed: {message}",
        category=category,
        status_code=response.status_code,
        secrets=(api_key,),
    )


def _extract_req_id(data: dict[str, Any], aidso_name: str) -> str:
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    req_ids = payload.get("reqIds") if isinstance(payload, dict) else None
    if not isinstance(req_ids, dict):
        raise AdapterError(
            "aidso response missing reqIds",
            category=ErrorCategory.INVALID_REQUEST,
        )
    req_id = req_ids.get(aidso_name)
    if not isinstance(req_id, str) or not req_id.strip():
        raise AdapterError(
            f"aidso response missing reqId for platform {aidso_name}",
            category=ErrorCategory.INVALID_REQUEST,
        )
    return req_id.strip()


def _extract_task_id(data: dict[str, Any]) -> str | None:
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    task_id = payload.get("taskId") if isinstance(payload, dict) else None
    return task_id if isinstance(task_id, str) and task_id.strip() else None


def _result_status(data: dict[str, Any]) -> str | None:
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    status = payload.get("status") if isinstance(payload, dict) else None
    return status if isinstance(status, str) else None


def _result_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    result = payload.get("result") if isinstance(payload, dict) else []
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


def _extract_context(data: dict[str, Any]) -> str:
    for item in _result_items(data):
        context = item.get("context")
        if isinstance(context, str):
            return context
    return ""


def _extract_citations(data: dict[str, Any]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for item in _result_items(data):
        raw_quote = item.get("quote")
        if raw_quote is None or raw_quote == "":
            continue
        parsed = _parse_quote(raw_quote)
        for quote in parsed:
            url = quote.get("url")
            title = quote.get("title")
            snippet = quote.get("snippet")
            citations.append(
                {
                    "url": url if isinstance(url, str) else None,
                    "title": title if isinstance(title, str) else None,
                    "snippet": snippet if isinstance(snippet, str) else None,
                    "quoted_text": snippet if isinstance(snippet, str) else None,
                    "source_type": "web",
                    "site_name": quote.get("site_name"),
                }
            )
    return citations


def _parse_quote(raw_quote: Any) -> list[dict[str, Any]]:
    if isinstance(raw_quote, str):
        try:
            raw_quote = json.loads(raw_quote)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw_quote, list):
        return []
    return [item for item in raw_quote if isinstance(item, dict)]


def _metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
