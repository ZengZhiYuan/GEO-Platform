"""腾讯元宝到腾讯混元官方 API 的映射适配器。"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlparse

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


class YuanbaoAdapter:
    """平台代码保持 yuanbao，底层调用腾讯混元官方 API。"""

    code = "yuanbao"

    def __init__(
        self,
        *,
        base_url: str = settings.YUANBAO_BASE_URL,
        timeout_seconds: float = settings.COLLECTION_REQUEST_TIMEOUT_SECONDS,
        raw_response_enabled: bool = settings.COLLECTION_RAW_RESPONSE_ENABLED,
        region: str = "ap-guangzhou",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._raw_response_enabled = raw_response_enabled
        self._region = region

    async def query(
        self,
        request: PlatformQuery,
        *,
        credential: PlatformCredential,
    ) -> PlatformAnswer:
        secret_id, secret_key = _require_tencent_credentials(credential)
        payload = _hunyuan_payload(request)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        headers = _tc3_headers(
            self._base_url,
            body,
            secret_id=secret_id,
            secret_key=secret_key,
            region=self._region,
            request_id=request.request_id,
        )
        started = time.perf_counter()
        response = await _post_hunyuan(
            self._base_url,
            body,
            headers=headers,
            timeout_seconds=self._timeout_seconds,
            secrets=(secret_id, secret_key),
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        _raise_for_error(response, secrets=(secret_id, secret_key))
        data = response.json()
        text = _extract_text(data)
        if not text.strip():
            raise AdapterError(
                "yuanbao/hunyuan returned empty answer",
                category=ErrorCategory.INVALID_REQUEST,
            )
        return PlatformAnswer(
            text=text,
            citations=_extract_citations(data),
            model=request.model,
            usage=_extract_usage(data),
            latency_ms=latency_ms,
            provider_request_id=_provider_request_id(data, response),
            raw_response=data if self._raw_response_enabled else None,
        )


def _require_tencent_credentials(credential: PlatformCredential) -> tuple[str, str]:
    if not credential.secret_id or not credential.secret_key:
        raise AdapterError(
            "yuanbao tencent credentials are required",
            category=ErrorCategory.UNAUTHORIZED,
            secrets=(credential.secret_id or "", credential.secret_key or ""),
        )
    return credential.secret_id, credential.secret_key


def _hunyuan_payload(request: PlatformQuery) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"Role": "system", "Content": request.system_prompt})
    messages.append({"Role": "user", "Content": request.prompt})
    payload: dict[str, Any] = {
        "Model": request.model,
        "Messages": messages,
        "Stream": False,
    }
    if request.temperature is not None:
        payload["Temperature"] = request.temperature
    return payload


def _tc3_headers(
    url: str,
    body: str,
    *,
    secret_id: str,
    secret_key: str,
    region: str,
    request_id: str,
) -> dict[str, str]:
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    timestamp = int(time.time())
    request_date = dt.datetime.fromtimestamp(timestamp, tz=dt.UTC).strftime("%Y-%m-%d")
    service = "hunyuan"
    algorithm = "TC3-HMAC-SHA256"
    signed_headers = "content-type;host"
    hashed_payload = hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request = "\n".join(
        [
            "POST",
            path,
            "",
            f"content-type:application/json\nhost:{host}\n",
            signed_headers,
            hashed_payload,
        ]
    )
    credential_scope = f"{request_date}/{service}/tc3_request"
    string_to_sign = "\n".join(
        [
            algorithm,
            str(timestamp),
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    secret_date = _hmac_sha256(f"TC3{secret_key}".encode("utf-8"), request_date)
    secret_service = _hmac_sha256(secret_date, service)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": "application/json",
        "Host": host,
        "X-TC-Action": "ChatCompletions",
        "X-TC-Version": "2023-09-01",
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Region": region,
        "X-Request-Id": request_id,
    }


def _hmac_sha256(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


async def _post_hunyuan(
    url: str,
    body: str,
    *,
    headers: dict[str, str],
    timeout_seconds: float,
    secrets: tuple[str, str],
) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            return await client.post(url, content=body.encode("utf-8"), headers=headers)
    except httpx.TimeoutException as exc:
        raise AdapterError(
            "yuanbao/hunyuan request timed out",
            category=ErrorCategory.NETWORK_ERROR,
            secrets=secrets,
        ) from exc
    except httpx.RequestError as exc:
        raise AdapterError(
            f"yuanbao/hunyuan request failed: {exc}",
            category=ErrorCategory.NETWORK_ERROR,
            secrets=secrets,
        ) from exc


def _raise_for_error(response: httpx.Response, *, secrets: tuple[str, str]) -> None:
    if response.status_code < 400:
        return
    message = _error_message(response)
    raise AdapterError(
        f"yuanbao/hunyuan request failed: {message}",
        category=classify_http_status(response.status_code, message=message),
        status_code=response.status_code,
        retry_after_seconds=_retry_after_seconds(response),
        secrets=secrets,
    )


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text
    if not isinstance(payload, dict):
        return str(payload)
    wrapped = payload.get("Response")
    if isinstance(wrapped, dict):
        error = wrapped.get("Error")
        if isinstance(error, dict):
            return str(error.get("Message") or error.get("Code") or "provider error")
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "provider error")
    return str(payload)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _response_payload(data: dict[str, Any]) -> dict[str, Any]:
    wrapped = data.get("Response")
    return wrapped if isinstance(wrapped, dict) else data


def _extract_text(data: dict[str, Any]) -> str:
    payload = _response_payload(data)
    choices = payload.get("Choices") or payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("Message") or first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("Content") or message.get("content")
    return content if isinstance(content, str) else ""


def _extract_usage(data: dict[str, Any]) -> dict[str, Any]:
    usage = _response_payload(data).get("Usage") or _response_payload(data).get("usage") or {}
    if not isinstance(usage, dict):
        return {}
    return {
        "prompt_tokens": usage.get("PromptTokens", usage.get("prompt_tokens", 0)),
        "completion_tokens": usage.get("CompletionTokens", usage.get("completion_tokens", 0)),
        "total_tokens": usage.get("TotalTokens", usage.get("total_tokens", 0)),
    }


def _extract_citations(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _response_payload(data)
    citations = payload.get("Citations") or payload.get("citations") or []
    if not isinstance(citations, list):
        return []
    return [item for item in citations if isinstance(item, dict)]


def _provider_request_id(data: dict[str, Any], response: httpx.Response) -> str | None:
    payload = _response_payload(data)
    return payload.get("RequestId") or payload.get("id") or response.headers.get("x-request-id")
