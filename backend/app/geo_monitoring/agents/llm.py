"""统一 Agent LLM 客户端封装。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

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


class AgentLLMErrorCategory(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    NETWORK = "network"
    PROVIDER = "provider"
    PARSE = "parse"
    VALIDATION = "validation"


class AgentLLMError(Exception):
    """Agent LLM 调用失败，消息已脱敏。"""

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


@dataclass(frozen=True)
class AgentLLMConfig:
    base_url: str
    api_key: str
    model: str
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

    def __init__(self, *, base_url: str, api_key: str, timeout_seconds: float) -> None:
        self._client = AsyncOpenAI(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            timeout=timeout_seconds,
        )

    async def create_chat_completion(self, **kwargs: Any) -> dict[str, Any]:
        response = await self._client.chat.completions.create(**kwargs)
        return response.model_dump()


class AgentLLMClient:
    """封装结构化输出、重试、解析修复与审计元数据。"""

    def __init__(
        self,
        config: AgentLLMConfig,
        *,
        transport: ChatCompletionsTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or OpenAIChatTransport(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout_seconds=config.timeout_seconds,
        )
        self._secrets = (config.api_key,)

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
            except RateLimitError as exc:
                last_error = exc
                category = AgentLLMErrorCategory.RATE_LIMITED
            except APIConnectionError as exc:
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


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    if max_chars <= 3:
        return "..."[:max_chars], True
    return text[: max_chars - 3] + "...", True


def _extract_content(completion: dict[str, Any]) -> str:
    choices = completion.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _usage_int(usage: dict[str, Any], key: str) -> int | None:
    value = usage.get(key)
    return int(value) if isinstance(value, int) else None


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
