"""统一 Agent LLM 客户端封装。"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from dashscope import Generation
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from app.geo_monitoring.adapters.errors import sanitize_message
from app.geo_monitoring.agents.prompts import (
    REPAIR_PROMPT_VERSION,
    REPAIR_SYSTEM_PROMPT,
    REPAIR_USER_TEMPLATE,
    render_prompt,
)
from app.geo_monitoring.agents.schemas import SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_MAX_INPUT_CHARS = 12_000
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
AGENT_LLM_PROVIDER_OPENAI = "openai_compatible"
AGENT_LLM_PROVIDER_DASHSCOPE = "dashscope"


class AgentLLMErrorCategory(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    NETWORK = "network"
    PROVIDER = "provider"
    PARSE = "parse"
    VALIDATION = "validation"


class AgentLLMError(Exception):
    """Agent LLM 调用失败，消息已脱敏。"""

    # 构造带错误分类与脱敏消息的 Agent LLM 异常
    def __init__(
        self,
        message: str,
        *,
        category: AgentLLMErrorCategory,
        secrets: tuple[str, ...] = (),
    ) -> None:
        self.category = category
        self._secrets = secrets
        super().__init__(sanitize_message(message, self._secrets))


class TransportTimeoutError(Exception):
    """传输层超时，供 AgentLLMClient 重试。"""


class TransportRateLimitError(Exception):
    """传输层限流，供 AgentLLMClient 重试。"""


class TransportNetworkError(Exception):
    """传输层网络/服务端异常，供 AgentLLMClient 重试。"""


@dataclass(frozen=True)
class AgentLLMConfig:
    base_url: str
    api_key: str
    model: str
    provider: str = AGENT_LLM_PROVIDER_OPENAI
    timeout_seconds: float = 90.0
    max_attempts: int = 2
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    temperature: float = 0.0

@dataclass(frozen=True)
class AgentLLMRequest:
    template_key: str
    variables: dict[str, Any]
    output_schema: type[BaseModel]
    agent_code: str
    request_id: str


@dataclass(frozen=True)
class AgentLLMResult:
    parsed: BaseModel
    prompt_version: str
    input_metadata: dict[str, Any]
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    raw_text: str


@dataclass(frozen=True)
class AgentLLMFailure:
    error_code: str
    error_message: str
    prompt_version: str
    input_metadata: dict[str, Any]
    raw_text: str | None
    repair_attempted: bool


@runtime_checkable
class ChatCompletionsTransport(Protocol):
    async def create_chat_completion(self, **kwargs: Any) -> dict[str, Any]:
        ...


class OpenAIChatTransport:
    """OpenAI-compatible SDK 传输层；业务代码通过 AgentLLMClient 间接使用。"""

    # 初始化 OpenAI 兼容异步客户端
    def __init__(self, *, base_url: str, api_key: str, timeout_seconds: float) -> None:
        self._client = AsyncOpenAI(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            timeout=timeout_seconds,
        )

    # 调用 Chat Completions 并返回字典形式响应
    async def create_chat_completion(self, **kwargs: Any) -> dict[str, Any]:
        response = await self._client.chat.completions.create(**kwargs)
        return response.model_dump()


class DashScopeGenerationTransport:
    """DashScope 原生 Generation API 传输层。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url or DEFAULT_DASHSCOPE_BASE_URL

    async def create_chat_completion(self, **kwargs: Any) -> dict[str, Any]:
        model = str(kwargs.get("model") or self._model)
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature", 0.0)

        def _call() -> Any:
            import dashscope

            dashscope.base_http_api_url = self._base_url
            return Generation.call(
                api_key=self._api_key,
                model=model,
                messages=messages,
                result_format="message",
                temperature=temperature,
            )

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(_call),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise TransportTimeoutError(
                f"dashscope request timed out after {self._timeout_seconds}s"
            ) from exc
        except TransportRateLimitError:
            raise
        except TransportNetworkError:
            raise
        except AgentLLMError:
            raise
        except Exception as exc:
            raise _map_dashscope_exception(exc) from exc

        return _dashscope_response_to_completion(response, model=model)


def resolve_dashscope_base_url(base_url: str) -> str:
    """将 Agent LLM base_url 规范为 DashScope 原生 API v1 地址。"""
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized or "compatible-mode" in normalized:
        return DEFAULT_DASHSCOPE_BASE_URL
    return normalized


def build_agent_llm_transport(config: AgentLLMConfig) -> ChatCompletionsTransport:
    provider = (config.provider or AGENT_LLM_PROVIDER_OPENAI).strip().lower()
    if provider == AGENT_LLM_PROVIDER_DASHSCOPE:
        return DashScopeGenerationTransport(
            api_key=config.api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            base_url=resolve_dashscope_base_url(config.base_url),
        )
    return OpenAIChatTransport(
        base_url=config.base_url,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
    )


class AgentLLMClient:
    """封装结构化输出、重试、解析修复与审计元数据。"""

    # 初始化 LLM 客户端，可选注入自定义传输层
    def __init__(
        self,
        config: AgentLLMConfig,
        *,
        transport: ChatCompletionsTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or build_agent_llm_transport(config)
        self._secrets = (config.api_key,)
    # 渲染 Prompt、调用 LLM 并解析/修复结构化 JSON 输出
    async def generate_structured(
        self, request: AgentLLMRequest
    ) -> AgentLLMResult | AgentLLMFailure:
        prepared = self._prepare_input(request)
        system_prompt, user_prompt, prompt_version = render_prompt(
            request.template_key,
            prepared["render_variables"],
        )
        input_metadata = self._build_input_metadata(request, prepared, prompt_version)

        self._log_request(
            request=request,
            input_metadata=input_metadata,
            user_prompt=user_prompt,
        )

        completion = await self._call_with_retries(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            request_id=request.request_id,
        )
        raw_text = _extract_content(completion)
        parsed, failure = await self._parse_or_repair(
            raw_text=raw_text,
            output_schema=request.output_schema,
            request_id=request.request_id,
        )
        if failure is not None:
            return AgentLLMFailure(
                error_code=failure["error_code"],
                error_message=failure["error_message"],
                prompt_version=prompt_version,
                input_metadata=input_metadata,
                raw_text=raw_text,
                repair_attempted=failure["repair_attempted"],
            )

        usage = completion.get("usage") or {}
        return AgentLLMResult(
            parsed=parsed,
            prompt_version=prompt_version,
            input_metadata=input_metadata,
            model=str(completion.get("model") or self._config.model),
            prompt_tokens=_usage_int(usage, "prompt_tokens"),
            completion_tokens=_usage_int(usage, "completion_tokens"),
            raw_text=raw_text,
        )

    # 截断过长输入变量并记录截断元数据
    def _prepare_input(self, request: AgentLLMRequest) -> dict[str, Any]:
        render_variables: dict[str, str] = {}
        truncated = False
        original_chars = 0
        for key, value in request.variables.items():
            text = "" if value is None else str(value)
            original_chars += len(text)
            clipped, was_truncated = _truncate_text(text, self._config.max_input_chars)
            render_variables[key] = clipped
            truncated = truncated or was_truncated
        return {
            "render_variables": render_variables,
            "input_truncated": truncated,
            "original_input_chars": original_chars,
        }

    # 构建审计用的输入元数据快照
    def _build_input_metadata(
        self,
        request: AgentLLMRequest,
        prepared: dict[str, Any],
        prompt_version: str,
    ) -> dict[str, Any]:
        return {
            "agent_code": request.agent_code,
            "template_key": request.template_key,
            "prompt_version": prompt_version,
            "schema_version": SCHEMA_VERSION,
            "request_id": request.request_id,
            "input_truncated": prepared["input_truncated"],
            "original_input_chars": prepared["original_input_chars"],
            "max_input_chars": self._config.max_input_chars,
        }

    # 记录脱敏后的 LLM 请求日志
    def _log_request(
        self,
        *,
        request: AgentLLMRequest,
        input_metadata: dict[str, Any],
        user_prompt: str,
    ) -> None:
        preview = _truncate_text(user_prompt, 120)[0]
        logger.info(
            "agent_code=%s request_id=%s prompt_version=%s input_truncated=%s "
            "input_preview=%s",
            request.agent_code,
            request.request_id,
            input_metadata["prompt_version"],
            input_metadata["input_truncated"],
            sanitize_message(preview, self._secrets),
        )

    # 带指数退避重试的 Chat Completions 调用
    async def _call_with_retries(
        self,
        *,
        messages: list[dict[str, str]],
        request_id: str,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        category = AgentLLMErrorCategory.PROVIDER
        for attempt in range(1, self._config.max_attempts + 1):
            try:
                return await self._transport.create_chat_completion(
                    model=self._config.model,
                    messages=messages,
                    temperature=self._config.temperature,
                )
            except APITimeoutError as exc:
                last_error = exc
                category = AgentLLMErrorCategory.TIMEOUT
            except TransportTimeoutError as exc:
                last_error = exc
                category = AgentLLMErrorCategory.TIMEOUT
            except RateLimitError as exc:
                last_error = exc
                category = AgentLLMErrorCategory.RATE_LIMITED
            except TransportRateLimitError as exc:
                last_error = exc
                category = AgentLLMErrorCategory.RATE_LIMITED
            except APIConnectionError as exc:
                last_error = exc
                category = AgentLLMErrorCategory.NETWORK
            except TransportNetworkError as exc:
                last_error = exc
                category = AgentLLMErrorCategory.NETWORK
            except Exception as exc:
                raise AgentLLMError(
                    f"agent llm provider error request_id={request_id}: {exc}",
                    category=AgentLLMErrorCategory.PROVIDER,
                    secrets=self._secrets,
                ) from exc

            logger.warning(
                "agent llm retry request_id=%s attempt=%s category=%s message=%s",
                request_id,
                attempt,
                category.value,
                sanitize_message(str(last_error), self._secrets),
            )
            if attempt >= self._config.max_attempts:
                raise AgentLLMError(
                    f"agent llm failed after {self._config.max_attempts} attempts "
                    f"request_id={request_id}: {last_error}",
                    category=category,
                    secrets=self._secrets,
                ) from last_error
        raise AgentLLMError(
            f"agent llm failed request_id={request_id}",
            category=AgentLLMErrorCategory.PROVIDER,
            secrets=self._secrets,
        )

    # 解析 JSON 输出，失败时尝试 LLM 修复
    async def _parse_or_repair(
        self,
        *,
        raw_text: str,
        output_schema: type[BaseModel],
        request_id: str,
    ) -> tuple[BaseModel | None, dict[str, Any] | None]:
        parsed, error = _parse_structured_output(raw_text, output_schema)
        if parsed is not None:
            return parsed, None

        repair_attempted = True
        repaired = await self._repair(
            raw_text,
            error or "invalid output",
            output_schema,
            request_id,
        )
        if isinstance(repaired, BaseModel):
            return repaired, None

        error_code = (
            "validation_failed"
            if error and "validation" in error.lower()
            else "parse_failed"
        )
        return None, {
            "error_code": error_code,
            "error_message": repaired if isinstance(repaired, str) else error or "structured output parse failed",
            "repair_attempted": repair_attempted,
        }

    # 调用修复 Prompt 让 LLM 修正不符合 Schema 的输出
    async def _repair(
        self,
        raw_text: str,
        validation_errors: str,
        output_schema: type[BaseModel],
        request_id: str,
    ) -> BaseModel | str:
        repair_user = REPAIR_USER_TEMPLATE.format(
            raw_text=_truncate_text(raw_text, self._config.max_input_chars)[0],
            validation_errors=validation_errors,
            schema_hint=json.dumps(output_schema.model_json_schema(), ensure_ascii=False),
        )
        try:
            completion = await self._call_with_retries(
                messages=[
                    {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
                    {"role": "user", "content": repair_user},
                ],
                request_id=f"{request_id}-repair",
            )
        except AgentLLMError as exc:
            return str(exc)

        repaired_text = _extract_content(completion)
        parsed, error = _parse_structured_output(repaired_text, output_schema)
        if parsed is not None:
            logger.info(
                "agent llm repair succeeded request_id=%s repair_prompt_version=%s",
                request_id,
                REPAIR_PROMPT_VERSION,
            )
            return parsed
        return error or "repair failed"


def create_agent_llm_client(
    config: AgentLLMConfig,
    *,
    transport: ChatCompletionsTransport | None = None,
) -> AgentLLMClient:
    """工厂方法：业务代码通过此函数获取客户端，不直接实例化 SDK。"""
    return AgentLLMClient(config, transport=transport)


def _dashscope_response_to_completion(response: Any, *, model: str) -> dict[str, Any]:
    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code != 200:
        _raise_for_dashscope_response(response)

    content = _extract_dashscope_content(response)
    usage = getattr(response, "usage", None) or {}
    prompt_tokens = _dashscope_usage_int(usage, "input_tokens")
    completion_tokens = _dashscope_usage_int(usage, "output_tokens")
    return {
        "model": model,
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


def _extract_dashscope_content(response: Any) -> str:
    output = getattr(response, "output", None)
    if output is None:
        return ""

    if isinstance(output, dict):
        choices = output.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
        text = output.get("text")
        if isinstance(text, str):
            return text
        return ""

    choices = getattr(output, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        if message is not None:
            content = getattr(message, "content", None)
            if isinstance(content, str):
                return content
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content

    text = getattr(output, "text", None)
    return text if isinstance(text, str) else ""


def _dashscope_usage_int(usage: Any, key: str) -> int | None:
    if isinstance(usage, dict):
        value = usage.get(key)
    else:
        value = getattr(usage, key, None)
    return int(value) if isinstance(value, int) else None


def _raise_for_dashscope_response(response: Any) -> None:
    status_code = int(getattr(response, "status_code", 0) or 0)
    code = str(getattr(response, "code", "") or "")
    message = str(getattr(response, "message", "") or "dashscope api error")
    detail = f"dashscope api error status={status_code} code={code}: {message}"

    if status_code == 429 or "Throttling" in code or "RateQuota" in code:
        raise TransportRateLimitError(detail)
    if status_code >= 500:
        raise TransportNetworkError(detail)
    raise AgentLLMError(
        detail,
        category=AgentLLMErrorCategory.PROVIDER,
    )


def _map_dashscope_exception(exc: Exception) -> Exception:
    message = str(exc)
    lowered = message.lower()
    if "timeout" in lowered or "timed out" in lowered:
        return TransportTimeoutError(message)
    if "rate" in lowered and "limit" in lowered:
        return TransportRateLimitError(message)
    if "connection" in lowered or "network" in lowered:
        return TransportNetworkError(message)
    return AgentLLMError(
        f"dashscope transport error: {exc}",
        category=AgentLLMErrorCategory.PROVIDER,
    )


# 截断文本至最大字符数并返回是否已截断
def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    if max_chars <= 3:
        return "..."[:max_chars], True
    return text[: max_chars - 3] + "...", True


# 从 Chat Completions 响应字典中提取文本内容
def _extract_content(completion: dict[str, Any]) -> str:
    choices = completion.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


# 从 usage 字典中安全提取整型 Token 计数
def _usage_int(usage: dict[str, Any], key: str) -> int | None:
    value = usage.get(key)
    return int(value) if isinstance(value, int) else None


# 将 LLM 原始 JSON 文本解析并校验为目标 Pydantic 模型
def _parse_structured_output(
    raw_text: str,
    output_schema: type[BaseModel],
) -> tuple[BaseModel | None, str | None]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return None, f"json decode error: {exc.msg}"

    try:
        return output_schema.model_validate(payload), None
    except ValidationError as exc:
        return None, f"validation error: {exc.errors()}"
