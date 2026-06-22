"""DashScope Agent LLM 传输层与 provider 开关测试。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from app.geo_monitoring.agents.llm import (
    AgentLLMConfig,
    AgentLLMError,
    AgentLLMErrorCategory,
    DashScopeGenerationTransport,
    OpenAIChatTransport,
    TransportRateLimitError,
    TransportTimeoutError,
    build_agent_llm_transport,
    create_agent_llm_client,
    resolve_dashscope_base_url,
)
from app.geo_monitoring.services.analysis import build_agent_llm_config
from tests.test_config import make_settings


API_KEY = "sk-dashscope-test"
MODEL = "qwen-plus"


def _dashscope_success_response(
    content: str,
    *,
    input_tokens: int = 12,
    output_tokens: int = 8,
) -> SimpleNamespace:
    return SimpleNamespace(
        status_code=200,
        request_id="req-dashscope-1",
        code="",
        message="",
        output={
            "choices": [
                {
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ]
        },
        usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
    )


def _dashscope_error_response(
    *,
    status_code: int = 400,
    code: str = "InvalidParameter",
    message: str = "invalid request",
) -> SimpleNamespace:
    return SimpleNamespace(
        status_code=status_code,
        request_id="req-dashscope-err",
        code=code,
        message=message,
        output=None,
        usage=None,
    )


def test_resolve_dashscope_base_url_defaults_when_empty():
    assert resolve_dashscope_base_url("") == "https://dashscope.aliyuncs.com/api/v1"


def test_resolve_dashscope_base_url_converts_compatible_mode():
    assert (
        resolve_dashscope_base_url("https://dashscope.aliyuncs.com/compatible-mode/v1")
        == "https://dashscope.aliyuncs.com/api/v1"
    )


def test_resolve_dashscope_base_url_keeps_native_api_v1():
    custom = "https://dashscope-us.aliyuncs.com/api/v1"
    assert resolve_dashscope_base_url(custom) == custom


def test_build_agent_llm_transport_openai_compatible_default():
    config = AgentLLMConfig(
        base_url="https://agent-llm.test/v1",
        api_key=API_KEY,
        model=MODEL,
        provider="openai_compatible",
    )

    transport = build_agent_llm_transport(config)

    assert isinstance(transport, OpenAIChatTransport)


def test_build_agent_llm_transport_dashscope():
    config = AgentLLMConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=API_KEY,
        model=MODEL,
        provider="dashscope",
    )

    transport = build_agent_llm_transport(config)

    assert isinstance(transport, DashScopeGenerationTransport)
    assert transport._base_url == "https://dashscope.aliyuncs.com/api/v1"


def test_dashscope_transport_maps_success_response_to_openai_shape():
    transport = DashScopeGenerationTransport(
        api_key=API_KEY,
        model=MODEL,
        timeout_seconds=5.0,
    )
    payload = '{"label":"positive","confidence":0.9,"rationale":"ok"}'

    with patch(
        "app.geo_monitoring.agents.llm.Generation.call",
        return_value=_dashscope_success_response(payload),
    ) as mocked_call:
        result = asyncio.run(
            transport.create_chat_completion(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "user"},
                ],
                temperature=0.0,
            )
        )

    mocked_call.assert_called_once()
    call_kwargs = mocked_call.call_args.kwargs
    assert call_kwargs["api_key"] == API_KEY
    assert call_kwargs["model"] == MODEL
    assert call_kwargs["result_format"] == "message"
    assert call_kwargs["messages"][-1]["content"] == "user"

    assert result["choices"][0]["message"]["content"] == payload
    assert result["usage"]["prompt_tokens"] == 12
    assert result["usage"]["completion_tokens"] == 8
    assert result["model"] == MODEL


def test_dashscope_transport_raises_provider_error_on_invalid_response():
    transport = DashScopeGenerationTransport(
        api_key=API_KEY,
        model=MODEL,
        timeout_seconds=5.0,
    )

    with patch(
        "app.geo_monitoring.agents.llm.Generation.call",
        return_value=_dashscope_error_response(),
    ):
        with pytest.raises(AgentLLMError) as exc_info:
            asyncio.run(
                transport.create_chat_completion(
                    model=MODEL,
                    messages=[{"role": "user", "content": "hi"}],
                )
            )

    assert exc_info.value.category == AgentLLMErrorCategory.PROVIDER


def test_dashscope_transport_rate_limit_is_retryable():
    transport = DashScopeGenerationTransport(
        api_key=API_KEY,
        model=MODEL,
        timeout_seconds=5.0,
    )

    with patch(
        "app.geo_monitoring.agents.llm.Generation.call",
        return_value=_dashscope_error_response(
            status_code=429,
            code="Throttling.RateQuota",
            message="rate limit exceeded",
        ),
    ):
        with pytest.raises(TransportRateLimitError):
            asyncio.run(
                transport.create_chat_completion(
                    model=MODEL,
                    messages=[{"role": "user", "content": "hi"}],
                )
            )


def test_dashscope_transport_timeout_is_retryable():
    transport = DashScopeGenerationTransport(
        api_key=API_KEY,
        model=MODEL,
        timeout_seconds=0.01,
    )

    def slow_call(**_: Any) -> SimpleNamespace:
        import time

        time.sleep(0.05)
        return _dashscope_success_response("late")

    with patch("app.geo_monitoring.agents.llm.Generation.call", side_effect=slow_call):
        with pytest.raises(TransportTimeoutError):
            asyncio.run(
                transport.create_chat_completion(
                    model=MODEL,
                    messages=[{"role": "user", "content": "hi"}],
                )
            )


def test_create_agent_llm_client_selects_dashscope_transport():
    config = AgentLLMConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=API_KEY,
        model=MODEL,
        provider="dashscope",
    )

    client = create_agent_llm_client(config)

    assert isinstance(client._transport, DashScopeGenerationTransport)


def test_build_agent_llm_config_reads_provider_from_settings():
    settings = make_settings(
        AGENT_LLM_PROVIDER="dashscope",
        AGENT_LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1",
        AGENT_LLM_API_KEY=API_KEY,
        AGENT_LLM_MODEL=MODEL,
    )

    config = build_agent_llm_config(settings)

    assert config.provider == "dashscope"
    assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
