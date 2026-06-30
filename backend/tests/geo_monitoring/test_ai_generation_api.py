"""Task P0-2 / O5：AI 生成辅助接口测试。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.geo_monitoring.agents.llm import AgentLLMConfig, create_agent_llm_client
from app.geo_monitoring.schemas import (
    AiBrandWordsGenerateIn,
    AiCompetitorsGenerateIn,
    AiQuestionsGenerateIn,
)
from app.geo_monitoring.services import ai_generation as ai_generation_service
from tests.geo_monitoring.agents.test_llm import FakeTransport, _completion
from tests.test_config import make_settings

_LLM_API_KEY = "sk-agent-test-secret"
_LLM_BASE_URL = "https://agent-llm.test/v1"
_LLM_MODEL = "agent-model"


def _llm_settings(**overrides: Any):
    return make_settings(
        AGENT_LLM_BASE_URL=_LLM_BASE_URL,
        AGENT_LLM_API_KEY=_LLM_API_KEY,
        AGENT_LLM_MODEL=_LLM_MODEL,
        AI_GENERATION_LLM_ENABLED=True,
        AI_GENERATION_TIMEOUT_SECONDS=5,
        AI_GENERATION_MAX_INPUT_CHARS=500,
        **overrides,
    )


def _llm_client(responses: list[Any]):
    config = AgentLLMConfig(
        base_url=_LLM_BASE_URL,
        api_key=_LLM_API_KEY,
        model=_LLM_MODEL,
        timeout_seconds=5.0,
        max_attempts=1,
        max_input_chars=500,
    )
    return create_agent_llm_client(config, transport=FakeTransport(responses))


_SONGCHENG_BASE = {
    "brand_name": "杭州宋城",
    "category": "文旅演艺",
    "region": "杭州",
    "official_domain": "https://www.hzsongcheng.com",
}


def test_brand_words_generate_rejects_empty_brand_name(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/brand-words:generate",
        json={"brand_name": "   "},
    ).json()
    assert response["code"] == 422


def test_brand_words_generate_songcheng_example(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/brand-words:generate",
        json={**_SONGCHENG_BASE, "limit": 10},
    ).json()
    assert response["code"] == 0
    assert response["data"]["generation_method"] == "rule_fallback"
    words = response["data"]["brand_words"]
    assert words[0] == "杭州宋城"
    assert "杭州宋城" in words
    assert "宋城千古情" in words
    assert "宋城" in words
    assert len(words) == len(set(words))
    assert all(word.strip() for word in words)


def test_brand_words_generate_respects_limit_one(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/brand-words:generate",
        json={**_SONGCHENG_BASE, "limit": 1},
    ).json()
    assert response["code"] == 0
    words = response["data"]["brand_words"]
    assert words == ["杭州宋城"]


def test_competitors_generate_songcheng_example(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/competitors:generate",
        json={**_SONGCHENG_BASE, "limit": 5},
    ).json()
    assert response["code"] == 0
    competitors = response["data"]["competitors"]
    names = {item["brand_name"] for item in competitors}
    assert "印象西湖" in names
    assert "只有河南·戏剧幻城" in names
    assert "杭州宋城" not in names
    assert "宋城演艺" not in names
    assert "宋城" not in names
    for item in competitors:
        assert item["brand_name"] in item["competitor_words"]
        assert len(item["competitor_words"]) == len(set(item["competitor_words"]))


def test_questions_generate_songcheng_example(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/questions:generate",
        json={
            **_SONGCHENG_BASE,
            "core_keywords": ["杭州旅游"],
            "competitors": ["印象西湖", "只有河南·戏剧幻城"],
            "limit": 5,
        },
    ).json()
    assert response["code"] == 0
    questions = response["data"]["questions"]
    assert len(questions) == 5
    prompt_types = {item["prompt_type"] for item in questions}
    assert prompt_types == {
        "brand_sentiment",
        "brand_info",
        "category_sentiment",
        "competitor_comparison",
        "category_recommendation",
    }
    assert any("杭州宋城" in item["prompt_text"] for item in questions)
    assert any(item["core_keyword"] == "杭州旅游" for item in questions)


def test_questions_generate_respects_limit(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/questions:generate",
        json={
            "brand_name": "杭州宋城",
            "category": "文旅演艺",
            "core_keywords": ["杭州旅游"],
            "limit": 3,
        },
    ).json()
    assert response["code"] == 0
    assert len(response["data"]["questions"]) == 3


def test_ai_generation_does_not_persist_monitor_setup(client, project_id):
    before = client.get(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup"
    ).json()["data"]
    assert before["brand"] is None

    client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/brand-words:generate",
        json={"brand_name": "杭州宋城", "category": "文旅演艺", "limit": 5},
    )
    client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/competitors:generate",
        json={"brand_name": "杭州宋城", "category": "文旅演艺", "region": "杭州", "limit": 5},
    )
    client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/questions:generate",
        json={
            "brand_name": "杭州宋城",
            "category": "文旅演艺",
            "core_keywords": ["杭州旅游"],
            "limit": 5,
        },
    )

    after = client.get(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup"
    ).json()["data"]
    assert after["brand"] is None
    assert after["competitors"] == []
    assert after["ai_questions"] == []


def test_ai_generation_returns_404_for_missing_project(client):
    response = client.post(
        "/api/geo-monitoring/projects/99999/ai/brand-words:generate",
        json={"brand_name": "杭州宋城"},
    ).json()
    assert response["code"] == 40400


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/geo-monitoring/projects/{project_id}/ai/brand-words:generate",
        "/api/v1/geo-monitoring/projects/{project_id}/ai/competitors:generate",
        "/api/v1/geo-monitoring/projects/{project_id}/ai/questions:generate",
    ],
)
def test_ai_generation_routes_available_on_v1_prefix(client, project_id, path):
    body = {
        "brand_name": "杭州宋城",
        "category": "文旅演艺",
        "region": "杭州",
        "core_keywords": ["杭州旅游"],
        "competitors": ["印象西湖"],
        "limit": 3,
    }
    response = client.post(path.format(project_id=project_id), json=body).json()
    assert response["code"] == 0
    assert response["data"]


_GLOBAL_AI_PATHS = (
    "/api/geo-monitoring/ai/brand-words:generate",
    "/api/geo-monitoring/ai/competitors:generate",
    "/api/geo-monitoring/ai/questions:generate",
)

_GLOBAL_AI_V1_PATHS = (
    "/api/v1/geo-monitoring/ai/brand-words:generate",
    "/api/v1/geo-monitoring/ai/competitors:generate",
    "/api/v1/geo-monitoring/ai/questions:generate",
)

_GLOBAL_AI_BODY = {
    "brand_name": "杭州宋城",
    "category": "文旅演艺",
    "region": "杭州",
    "core_keywords": ["杭州旅游"],
    "competitors": ["印象西湖", "只有河南·戏剧幻城"],
    "limit": 5,
}


def test_global_brand_words_generate_without_project_id(client):
    response = client.post(
        "/api/geo-monitoring/ai/brand-words:generate",
        json={**_SONGCHENG_BASE, "limit": 10},
    ).json()
    assert response["code"] == 0
    words = response["data"]["brand_words"]
    assert words[0] == "杭州宋城"
    assert "宋城千古情" in words


def test_global_competitors_generate_without_project_id(client):
    response = client.post(
        "/api/geo-monitoring/ai/competitors:generate",
        json={**_SONGCHENG_BASE, "limit": 5},
    ).json()
    assert response["code"] == 0
    names = {item["brand_name"] for item in response["data"]["competitors"]}
    assert "印象西湖" in names
    assert "杭州宋城" not in names


def test_global_questions_generate_without_project_id(client):
    response = client.post(
        "/api/geo-monitoring/ai/questions:generate",
        json={
            **_SONGCHENG_BASE,
            "core_keywords": ["杭州旅游"],
            "competitors": ["印象西湖", "只有河南·戏剧幻城"],
            "limit": 5,
        },
    ).json()
    assert response["code"] == 0
    assert len(response["data"]["questions"]) == 5


@pytest.mark.parametrize("path", _GLOBAL_AI_V1_PATHS)
def test_global_ai_generation_routes_available_on_v1_prefix(client, path):
    response = client.post(path, json=_GLOBAL_AI_BODY).json()
    assert response["code"] == 0
    assert response["data"]


def test_global_ai_generation_does_not_create_or_modify_projects(client):
    before_total = client.get("/api/geo-monitoring/projects").json()["data"]["total"]

    for path in _GLOBAL_AI_PATHS:
        response = client.post(path, json=_GLOBAL_AI_BODY).json()
        assert response["code"] == 0

    after_total = client.get("/api/geo-monitoring/projects").json()["data"]["total"]
    assert after_total == before_total


def test_brand_words_llm_success_uses_structured_output():
    payload = AiBrandWordsGenerateIn(
        brand_name="杭州宋城",
        category="文旅演艺",
        limit=5,
    )
    llm_payload = {
        "brand_words": ["杭州宋城", "宋城千古情", "宋城演艺", "千古情", "宋城"],
    }
    client = _llm_client(
        [_completion(json.dumps(llm_payload, ensure_ascii=False))]
    )

    result = ai_generation_service.generate_brand_words(
        payload,
        settings=_llm_settings(),
        llm_client=client,
    )

    assert result["generation_method"] == "llm"
    assert result["brand_words"] == llm_payload["brand_words"]


def test_brand_words_llm_failure_falls_back_to_rules():
    payload = AiBrandWordsGenerateIn(
        brand_name="杭州宋城",
        category="文旅演艺",
        limit=10,
    )
    from openai import APITimeoutError
    import httpx

    request = httpx.Request("POST", f"{_LLM_BASE_URL}/chat/completions")
    client = _llm_client([APITimeoutError(request)])

    result = ai_generation_service.generate_brand_words(
        payload,
        settings=_llm_settings(),
        llm_client=client,
    )

    assert result["generation_method"] == "rule_fallback"
    assert result["brand_words"][0] == "杭州宋城"
    assert "宋城千古情" in result["brand_words"]


def test_brand_words_llm_invalid_output_falls_back_to_rules():
    payload = AiBrandWordsGenerateIn(
        brand_name="杭州宋城",
        category="文旅演艺",
        limit=10,
    )
    client = _llm_client(
        [
            _completion('{"brand_words": "not-a-list"}'),
            _completion('{"brand_words": "still-not-a-list"}'),
        ]
    )

    result = ai_generation_service.generate_brand_words(
        payload,
        settings=_llm_settings(),
        llm_client=client,
    )

    assert result["generation_method"] == "rule_fallback"
    assert "宋城千古情" in result["brand_words"]


def test_ai_generation_llm_error_does_not_leak_api_key(caplog):
    payload = AiBrandWordsGenerateIn(
        brand_name="杭州宋城",
        category="文旅演艺",
        limit=5,
    )
    from openai import APITimeoutError
    import httpx

    request = httpx.Request("POST", f"{_LLM_BASE_URL}/chat/completions")
    client = _llm_client([APITimeoutError(request)])

    with caplog.at_level("WARNING"):
        result = ai_generation_service.generate_brand_words(
            payload,
            settings=_llm_settings(),
            llm_client=client,
        )

    assert result["generation_method"] == "rule_fallback"
    joined = " ".join(record.message for record in caplog.records)
    assert _LLM_API_KEY not in joined
    assert "sk-" not in joined


def test_competitors_llm_success(client, project_id, monkeypatch):
    llm_payload = {
        "competitors": [
            {
                "brand_name": "印象西湖",
                "competitor_words": ["印象西湖", "印象西湖演出"],
                "official_domain": None,
            },
            {
                "brand_name": "只有河南·戏剧幻城",
                "competitor_words": ["只有河南", "戏剧幻城"],
                "official_domain": "https://www.onlyhenan.com",
            },
        ]
    }
    monkeypatch.setattr(
        ai_generation_service,
        "_build_ai_generation_llm_client",
        lambda *args, **kwargs: _llm_client(
            [_completion(json.dumps(llm_payload, ensure_ascii=False))]
        ),
    )
    monkeypatch.setattr(
        ai_generation_service,
        "_get_ai_generation_settings",
        lambda: _llm_settings(),
    )

    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/competitors:generate",
        json={**_SONGCHENG_BASE, "limit": 5},
    ).json()

    assert response["code"] == 0
    assert response["data"]["generation_method"] == "llm"
    names = {item["brand_name"] for item in response["data"]["competitors"]}
    assert names == {"印象西湖", "只有河南·戏剧幻城"}


def test_questions_llm_success(client, project_id, monkeypatch):
    llm_payload = {
        "questions": [
            {
                "prompt_text": "杭州宋城怎么样？",
                "prompt_type": "brand_sentiment",
                "core_keyword": "杭州旅游",
            },
            {
                "prompt_text": "介绍一下杭州宋城。",
                "prompt_type": "brand_info",
                "core_keyword": None,
            },
        ]
    }
    monkeypatch.setattr(
        ai_generation_service,
        "_build_ai_generation_llm_client",
        lambda *args, **kwargs: _llm_client(
            [_completion(json.dumps(llm_payload, ensure_ascii=False))]
        ),
    )
    monkeypatch.setattr(
        ai_generation_service,
        "_get_ai_generation_settings",
        lambda: _llm_settings(),
    )

    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/questions:generate",
        json={
            **_SONGCHENG_BASE,
            "core_keywords": ["杭州旅游"],
            "competitors": ["印象西湖"],
            "limit": 2,
        },
    ).json()

    assert response["code"] == 0
    assert response["data"]["generation_method"] == "llm"
    assert len(response["data"]["questions"]) == 2
    assert response["data"]["questions"][0]["prompt_type"] == "brand_sentiment"
