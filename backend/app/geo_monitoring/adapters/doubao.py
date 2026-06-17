"""豆包官方 API 适配器。"""

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
)


class DoubaoAdapter:
    code = "doubao"

    def __init__(
        self,
        *,
        base_url: str = settings.DOUBAO_BASE_URL,
        timeout_seconds: float = settings.COLLECTION_REQUEST_TIMEOUT_SECONDS,
        raw_response_enabled: bool = settings.COLLECTION_RAW_RESPONSE_ENABLED,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._raw_response_enabled = raw_response_enabled

    async def query(
        self,
        request: PlatformQuery,
        *,
        credential: PlatformCredential,
    ) -> PlatformAnswer:
        api_key = _require_api_key(credential)
        payload = _chat_payload(request)
        started = time.perf_counter()
        response = await _post_chat_completion(
            f"{self._base_url}/chat/completions",
            payload,
            api_key=api_key,
            request_id=request.request_id,
            timeout_seconds=self._timeout_seconds,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        _raise_for_error(response, api_key=api_key)
        data = response.json()
        text = _extract_text(data)
        if not text.strip():
            raise AdapterError("doubao returned empty answer", category=ErrorCategory.INVALID_REQUEST)
        return PlatformAnswer(
            text=text,
            citations=_extract_citations(data),
            model=str(data.get("model") or request.model),
            usage=dict(data.get("usage") or {}),
            latency_ms=latency_ms,
            provider_request_id=str(data.get("id") or response.headers.get("x-request-id") or ""),
            raw_response=data if self._raw_response_enabled else None,
        )


def _require_api_key(credential: PlatformCredential) -> str:
    if not credential.api_key:
        raise AdapterError("doubao api key is required", category=ErrorCategory.UNAUTHORIZED)
    return credential.api_key


def _chat_payload(request: PlatformQuery) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": messages,
        "stream": False,
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    return payload


async def _post_chat_completion(
    url: str,
    payload: dict[str, Any],
    *,
    api_key: str,
    request_id: str,
    timeout_seconds: float,
) -> httpx.Response:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": request_id,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            return await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise AdapterError(
            "doubao request timed out",
            category=ErrorCategory.NETWORK_ERROR,
            secrets=(api_key,),
        ) from exc
    except httpx.RequestError as exc:
        raise AdapterError(
            f"doubao request failed: {exc}",
            category=ErrorCategory.NETWORK_ERROR,
            secrets=(api_key,),
        ) from exc


def _raise_for_error(response: httpx.Response, *, api_key: str) -> None:
    if response.status_code < 400:
        return
    message = _error_message(response)
    raise AdapterError(
        f"doubao request failed: {message}",
        category=classify_http_status(response.status_code, message=message),
        status_code=response.status_code,
        retry_after_seconds=_retry_after_seconds(response),
        secrets=(api_key,),
    )


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "provider error")
    if error:
        return str(error)
    return str(payload)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _extract_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _extract_citations(data: dict[str, Any]) -> list[dict[str, Any]]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return []
    raw_citations = message.get("citations") or message.get("references") or []
    if not isinstance(raw_citations, list):
        return []
    citations: list[dict[str, Any]] = []
    for item in raw_citations:
        if not isinstance(item, dict):
            continue
        citation: dict[str, Any] = {}
        if item.get("title"):
            citation["title"] = item["title"]
        if item.get("url"):
            citation["url"] = item["url"]
        quoted_text = item.get("quoted_text") or item.get("content") or item.get("text")
        if quoted_text:
            citation["quoted_text"] = quoted_text
        if citation:
            citations.append(citation)
    return citations
