"""统一 Agent LLM 客户端测试。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
import pytest
from openai import APITimeoutError, RateLimitError

from app.geo_monitoring.agents.llm import (
    AgentLLMClient,
    AgentLLMConfig,
    AgentLLMError,
    AgentLLMErrorCategory,
    AgentLLMFailure,
    AgentLLMRequest,
    AgentLLMResult,
    create_agent_llm_client,
)
from app.geo_monitoring.agents.schemas import (
    InsightSummaryOutput,
    RecommendationIntentOutput,
    RiskAssessmentOutput,
    SentimentOutput,
)
from app.core.exceptions import BusinessException
from app.geo_monitoring.services.analysis import build_agent_llm_config, run_analysis
from tests.test_config import make_settings


API_KEY = "sk-agent-test-secret"
BASE_URL = "https://agent-llm.test/v1"
MODEL = "agent-model"


def _config(**overrides: Any) -> AgentLLMConfig:
    defaults = {
        "base_url": BASE_URL,
        "api_key": API_KEY,
        "model": MODEL,
        "timeout_seconds": 5.0,
        "max_attempts": 2,
        "max_input_chars": 200,
    }
    defaults.update(overrides)
    return AgentLLMConfig(**defaults)


def _sentiment_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "label": "positive",
        "confidence": 0.92,
        "rationale": "回答整体语气积极。",
    }
    payload.update(overrides)
    return payload


def _completion(content: str, *, usage: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        "id": "chatcmpl-test-1",
        "model": MODEL,
        "choices": [{"message": {"content": content}}],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _timeout_error() -> APITimeoutError:
    request = httpx.Request("POST", f"{BASE_URL}/chat/completions")
    return APITimeoutError(request)


def _rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", f"{BASE_URL}/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limited", response=response, body=None)


class FakeTransport:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def create_chat_completion(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if not self._responses:
            raise RuntimeError("no more fake responses")
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _request(**overrides: Any) -> AgentLLMRequest:
    defaults = {
        "template_key": "classify_sentiment",
        "variables": {"answer_text": "品牌表现不错，值得推荐。"},
        "output_schema": SentimentOutput,
        "agent_code": "classify_sentiment",
        "request_id": "req-agent-1",
    }
    defaults.update(overrides)
    return AgentLLMRequest(**defaults)


def _client(transport: FakeTransport, **config_overrides: Any) -> AgentLLMClient:
    return create_agent_llm_client(_config(**config_overrides), transport=transport)


def test_success_structured_output():
    transport = FakeTransport(
        [_completion(json.dumps(_sentiment_payload(), ensure_ascii=False))]
    )
    client = _client(transport)

    result = asyncio.run(client.generate_structured(_request()))

    assert isinstance(result, AgentLLMResult)
    assert isinstance(result.parsed, SentimentOutput)
    assert result.parsed.label.value == "positive"
    assert result.parsed.confidence == pytest.approx(0.92)
    assert result.prompt_version == "1.0.0"
    assert result.input_metadata["prompt_version"] == "1.0.0"
    assert result.input_metadata["agent_code"] == "classify_sentiment"
    assert result.input_metadata["template_key"] == "classify_sentiment"
    assert result.model == MODEL
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert len(transport.calls) == 1
    assert transport.calls[0]["model"] == MODEL
    assert transport.calls[0]["temperature"] == 0


def test_timeout_retries_then_fails():
    transport = FakeTransport([_timeout_error(), _timeout_error()])
    client = _client(transport)

    with pytest.raises(AgentLLMError) as exc_info:
        asyncio.run(client.generate_structured(_request()))

    assert exc_info.value.category == AgentLLMErrorCategory.TIMEOUT
    assert len(transport.calls) == 2


def test_rate_limit_retry_then_success():
    transport = FakeTransport(
        [
            _rate_limit_error(),
            _completion(json.dumps(_sentiment_payload(), ensure_ascii=False)),
        ]
    )
    client = _client(transport)

    result = asyncio.run(client.generate_structured(_request()))

    assert isinstance(result, AgentLLMResult)
    assert len(transport.calls) == 2


def test_invalid_json_repair_once_success():
    transport = FakeTransport(
        [
            _completion("not-json"),
            _completion(json.dumps(_sentiment_payload(), ensure_ascii=False)),
        ]
    )
    client = _client(transport)

    result = asyncio.run(client.generate_structured(_request()))

    assert isinstance(result, AgentLLMResult)
    assert len(transport.calls) == 2
    assert transport.calls[1]["messages"][-1]["role"] == "user"
    assert "修正" in transport.calls[1]["messages"][-1]["content"]


def test_invalid_json_repair_still_fails():
    transport = FakeTransport(
        [
            _completion("still-not-json"),
            _completion("{bad json"),
        ]
    )
    client = _client(transport)

    result = asyncio.run(client.generate_structured(_request()))

    assert isinstance(result, AgentLLMFailure)
    assert result.repair_attempted is True
    assert result.error_code == "parse_failed"
    assert result.raw_text is not None
    assert result.prompt_version == "1.0.0"
    assert "parse" in result.error_message.lower() or "json" in result.error_message.lower()


def test_missing_fields_repair_once_success():
    transport = FakeTransport(
        [
            _completion(json.dumps({"label": "positive"}, ensure_ascii=False)),
            _completion(json.dumps(_sentiment_payload(), ensure_ascii=False)),
        ]
    )
    client = _client(transport)

    result = asyncio.run(client.generate_structured(_request()))

    assert isinstance(result, AgentLLMResult)
    assert len(transport.calls) == 2


def test_missing_fields_repair_still_fails():
    transport = FakeTransport(
        [
            _completion(json.dumps({"label": "positive"}, ensure_ascii=False)),
            _completion(json.dumps({"label": "positive"}, ensure_ascii=False)),
        ]
    )
    client = _client(transport)

    result = asyncio.run(client.generate_structured(_request()))

    assert isinstance(result, AgentLLMFailure)
    assert result.repair_attempted is True
    assert result.error_code == "validation_failed"


def test_logs_redact_api_key_and_truncates_input(caplog: pytest.LogCaptureFixture):
    long_answer = "A" * 500
    transport = FakeTransport(
        [_completion(json.dumps(_sentiment_payload(), ensure_ascii=False))]
    )
    client = _client(transport, max_input_chars=50)

    with caplog.at_level(logging.INFO, logger="app.geo_monitoring.agents.llm"):
        asyncio.run(
            client.generate_structured(
                _request(variables={"answer_text": long_answer})
            )
        )

    log_text = caplog.text
    assert API_KEY not in log_text
    assert long_answer not in log_text
    assert "truncated" in log_text.lower() or "..." in log_text


def test_input_metadata_records_truncation():
    long_answer = "B" * 300
    transport = FakeTransport(
        [_completion(json.dumps(_sentiment_payload(), ensure_ascii=False))]
    )
    client = _client(transport, max_input_chars=80)

    result = asyncio.run(
        client.generate_structured(_request(variables={"answer_text": long_answer}))
    )

    assert isinstance(result, AgentLLMResult)
    assert result.input_metadata["input_truncated"] is True
    assert result.input_metadata["original_input_chars"] == len(long_answer)


def test_other_output_schemas():
    transport = FakeTransport(
        [
            _completion(
                json.dumps(
                    {
                        "intent": "recommend",
                        "confidence": 0.8,
                        "evidence": "明确推荐目标品牌。",
                    },
                    ensure_ascii=False,
                )
            )
        ]
    )
    client = _client(transport)

    result = asyncio.run(
        client.generate_structured(
            _request(
                template_key="classify_recommendation",
                output_schema=RecommendationIntentOutput,
                agent_code="classify_recommendation",
            )
        )
    )

    assert isinstance(result.parsed, RecommendationIntentOutput)
    assert result.parsed.intent.value == "recommend"


def test_risk_and_insight_schemas():
    transport = FakeTransport(
        [
            _completion(
                json.dumps(
                    {
                        "level": "medium",
                        "topics": ["竞品压制"],
                        "summary": "存在可见度风险。",
                    },
                    ensure_ascii=False,
                )
            ),
            _completion(
                json.dumps(
                    {
                        "platform_summary": "整体表现中等。",
                        "key_gaps": ["首推不足"],
                        "suggestions": [
                            {
                                "priority": "P1",
                                "title": "加强首推",
                                "detail": "优化 Prompt 证据。",
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            ),
        ]
    )
    client = _client(transport)

    risk = asyncio.run(
        client.generate_structured(
            _request(
                template_key="assess_risk",
                variables={"metrics_summary": "mention_rate=0.2"},
                output_schema=RiskAssessmentOutput,
                agent_code="assess_risk",
            )
        )
    )
    insight = asyncio.run(
        client.generate_structured(
            _request(
                template_key="generate_insights",
                variables={"platform_code": "qwen", "metrics_summary": "mention_rate=0.2"},
                output_schema=InsightSummaryOutput,
                agent_code="generate_insights",
            )
        )
    )

    assert isinstance(risk.parsed, RiskAssessmentOutput)
    assert isinstance(insight.parsed, InsightSummaryOutput)
    assert insight.parsed.suggestions[0].priority.value == "P1"


def test_build_agent_llm_config_raises_when_settings_incomplete(tmp_path):
    settings = make_settings(
        REPORT_STORAGE_DIR=str(tmp_path),
        AGENT_LLM_BASE_URL="",
        AGENT_LLM_API_KEY="",
        AGENT_LLM_MODEL="",
    )

    with pytest.raises(BusinessException, match="AGENT_LLM_BASE_URL") as exc_info:
        build_agent_llm_config(settings)

    assert exc_info.value.code == 50301
    assert "test-agent-key" not in exc_info.value.message
    assert "sk-" not in exc_info.value.message


def test_build_agent_llm_config_does_not_leak_api_key_in_error_message(tmp_path):
    settings = make_settings(
        REPORT_STORAGE_DIR=str(tmp_path),
        AGENT_LLM_BASE_URL="https://agent.example.test/v1",
        AGENT_LLM_API_KEY="sk-leaked-should-not-appear",
        AGENT_LLM_MODEL="",
    )

    with pytest.raises(BusinessException, match="AGENT_LLM_MODEL") as exc_info:
        build_agent_llm_config(settings)

    assert "sk-leaked-should-not-appear" not in exc_info.value.message


def test_build_agent_llm_config_returns_explicit_settings(tmp_path):
    settings = make_settings(
        REPORT_STORAGE_DIR=str(tmp_path),
        AGENT_LLM_BASE_URL="https://agent.example.test/v1",
        AGENT_LLM_API_KEY=API_KEY,
        AGENT_LLM_MODEL=MODEL,
        AGENT_LLM_PROVIDER="openai_compatible",
    )

    config = build_agent_llm_config(settings)

    assert config.base_url == "https://agent.example.test/v1"
    assert config.api_key == API_KEY
    assert config.model == MODEL
    assert config.provider == "openai_compatible"


def test_run_analysis_accepts_explicit_fake_llm_client(session_factory, monkeypatch):
    from tests.geo_monitoring.agents.test_graph import FakeLLMClient, _seed_run

    llm = FakeLLMClient()
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))

    with session_factory() as db:
        result = run_analysis(db, seeded["run_id"], llm_client=llm)

    assert result["analysis_status"] in {"completed", "partial_success", "failed", "skipped"}
