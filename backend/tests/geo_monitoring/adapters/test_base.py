"""适配器基础契约测试。"""

from dataclasses import asdict

import pytest

from app.geo_monitoring.adapters.base import (
    PlatformAnswer,
    PlatformQuery,
    compute_credential_fingerprint,
)


def test_platform_query_contains_required_fields():
    query = PlatformQuery(
        prompt="问题",
        system_prompt="系统提示",
        model="qwen-max",
        temperature=0.2,
        request_id="req-1",
    )
    assert query.prompt == "问题"
    assert query.system_prompt == "系统提示"
    assert query.model == "qwen-max"
    assert query.temperature == 0.2
    assert query.request_id == "req-1"


def test_platform_answer_contains_required_fields():
    answer = PlatformAnswer(
        text="回答",
        citations=[{"title": "引用", "url": "https://example.com"}],
        model="qwen-max",
        usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        latency_ms=120,
        provider_request_id="provider-1",
        raw_response={"id": "provider-1"},
    )
    payload = asdict(answer)
    assert payload["text"] == "回答"
    assert payload["citations"][0]["url"] == "https://example.com"
    assert payload["usage"]["total_tokens"] == 3
    assert payload["latency_ms"] == 120
    assert payload["provider_request_id"] == "provider-1"
    assert payload["raw_response"]["id"] == "provider-1"


def test_compute_credential_fingerprint_is_stable_and_short():
    first = compute_credential_fingerprint("qwen", "secret-key-1")
    second = compute_credential_fingerprint("qwen", "secret-key-1")
    different = compute_credential_fingerprint("qwen", "secret-key-2")
    assert first == second
    assert first != different
    assert len(first) == 16
    assert "secret-key-1" not in first


def test_compute_credential_fingerprint_scopes_by_platform():
    same_secret = "shared-secret"
    qwen = compute_credential_fingerprint("qwen", same_secret)
    kimi = compute_credential_fingerprint("kimi", same_secret)
    assert qwen != kimi
