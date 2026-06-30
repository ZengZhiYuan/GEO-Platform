"""Task P2-3 / O6：高频评价标签聚类接口测试。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
from openai import APITimeoutError

from app.geo_monitoring.agents.llm import AgentLLMConfig, create_agent_llm_client
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.schemas import EvaluationTagsOut
from app.geo_monitoring.services import evaluation_tags as evaluation_tags_service
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
        EVALUATION_TAGS_LLM_ENABLED=True,
        EVALUATION_TAGS_LLM_MIN_ANSWERS=3,
        EVALUATION_TAGS_LLM_TIMEOUT_SECONDS=5,
        **overrides,
    )


def _llm_client(responses: list[Any]):
    config = AgentLLMConfig(
        base_url=_LLM_BASE_URL,
        api_key=_LLM_API_KEY,
        model=_LLM_MODEL,
        timeout_seconds=5.0,
        max_attempts=1,
        max_input_chars=8000,
    )
    return create_agent_llm_client(config, transport=FakeTransport(responses))


def _seed_prompt_with_tagged_answers(db) -> dict[str, Any]:
    project = MonitorProject(
        project_name="评价标签测试",
        industry="文旅演艺",
        status="active",
    )
    db.add(project)
    db.flush()

    prompt_set = PromptSet(
        project_id=project.id,
        set_name="标签集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()

    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="q1",
        prompt_text="宋城演艺怎么样？",
        prompt_type="brand_sentiment",
    )
    db.add(prompt)
    db.flush()

    for code in ("qwen", "deepseek"):
        db.add(
            AIPlatform(
                platform_code=code,
                platform_name=code,
                model_name=f"{code}-model",
                enabled=True,
            )
        )

    run = MonitorRun(
        run_no="RUN-TAGS",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        platform_codes=["qwen", "deepseek"],
        status="completed",
        collection_status="completed",
        analysis_status="completed",
        total_tasks=2,
        expected_query_count=2,
        succeeded_tasks=2,
        valid_answer_count=2,
    )
    db.add(run)
    db.flush()

    now = datetime.now(timezone.utc)
    answer_texts = (
        "宋城演艺演出非常精彩，舞台视觉效果震撼，票价性价比也不错。",
        "交通很方便，演出质量高，适合全家一起观看，沉浸体验很好。",
    )
    for index, (platform_code, text) in enumerate(
        zip(("qwen", "deepseek"), answer_texts, strict=True)
    ):
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code=platform_code,
            idempotency_key=f"tags-{run.id}-{index}",
            status="success",
            completed_at=now,
            finished_at=now,
        )
        db.add(task)
        db.flush()
        db.add(
            Answer(
                task_id=task.id,
                platform_code=platform_code,
                prompt_id=prompt.id,
                raw_text=text,
                normalized_text=text,
                model_name=f"{platform_code}-model",
                collected_at=now,
            )
        )
    db.commit()
    return {"project_id": project.id, "prompt_id": prompt.id, "run_id": run.id}


def _seed_prompt_with_neutral_answers(db, *, answer_count: int = 3) -> dict[str, Any]:
    project = MonitorProject(
        project_name="评价标签 LLM 测试",
        industry="文旅演艺",
        status="active",
    )
    db.add(project)
    db.flush()

    prompt_set = PromptSet(
        project_id=project.id,
        set_name="标签集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()

    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="q-neutral",
        prompt_text="某品牌整体评价如何？",
        prompt_type="brand_sentiment",
    )
    db.add(prompt)
    db.flush()

    platform_codes = ("qwen", "deepseek", "kimi")[:answer_count]
    for code in platform_codes:
        db.add(
            AIPlatform(
                platform_code=code,
                platform_name=code,
                model_name=f"{code}-model",
                enabled=True,
            )
        )

    run = MonitorRun(
        run_no="RUN-TAGS-NEUTRAL",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        platform_codes=list(platform_codes),
        status="completed",
        collection_status="completed",
        analysis_status="completed",
        total_tasks=answer_count,
        expected_query_count=answer_count,
        succeeded_tasks=answer_count,
        valid_answer_count=answer_count,
    )
    db.add(run)
    db.flush()

    now = datetime.now(timezone.utc)
    for index in range(answer_count):
        platform_code = platform_codes[index]
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code=platform_code,
            idempotency_key=f"tags-neutral-{run.id}-{platform_code}",
            status="success",
            completed_at=now,
            finished_at=now,
        )
        db.add(task)
        db.flush()
        db.add(
            Answer(
                task_id=task.id,
                platform_code=platform_code,
                prompt_id=prompt.id,
                raw_text=f"这是第 {index + 1} 条普通用户反馈，没有预置关键词。",
                normalized_text=f"这是第 {index + 1} 条普通用户反馈，没有预置关键词。",
                model_name=f"{platform_code}-model",
                collected_at=now,
            )
        )
    db.commit()
    return {"project_id": project.id, "prompt_id": prompt.id, "run_id": run.id}


def test_evaluation_tags_clusters_rule_based_tags(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    response = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
    )
    payload = response.json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["run_id"] == seeded["run_id"]
    assert data["prompt_id"] == seeded["prompt_id"]
    assert data["cluster_method"] == "rule"
    assert data["answer_count"] == 2
    tags = {item["tag"]: item for item in data["items"]}
    assert "演出质量" in tags
    assert "性价比" in tags
    assert "交通便利" in tags
    assert tags["演出质量"]["count"] >= 2
    assert tags["演出质量"]["share_rate"] is not None


def test_evaluation_tags_respects_limit(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"limit": 2},
    ).json()
    assert payload["code"] == 0, payload
    assert len(payload["data"]["items"]) <= 2


def test_evaluation_tags_unknown_prompt_returns_404(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        "conversation-questions/999999/evaluation-tags",
    ).json()
    assert payload["code"] == 40400


def test_evaluation_tags_platform_codes_filter(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"platform_codes": ["qwen"]},
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["answer_count"] == 1
    tags = {item["tag"] for item in data["items"]}
    assert "演出质量" in tags
    assert "性价比" in tags
    assert "交通便利" not in tags
    EvaluationTagsOut.model_validate(data)


def test_evaluation_tags_run_id_filter(client, session_factory):
    with session_factory() as db:
        seeded = _seed_prompt_with_tagged_answers(db)
        older_run = db.get(MonitorRun, seeded["run_id"])
        older_run.status = "completed"
        older_run.analysis_status = "completed"
        older_run.completed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        newer_run = MonitorRun(
            run_no="RUN-TAGS-NEW",
            project_id=seeded["project_id"],
            prompt_set_id=older_run.prompt_set_id,
            prompt_set_version="v1",
            platform_codes=["qwen"],
            status="completed",
            collection_status="completed",
            analysis_status="completed",
            total_tasks=1,
            expected_query_count=1,
            succeeded_tasks=1,
            valid_answer_count=1,
            completed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        db.add(newer_run)
        db.flush()
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        task = QueryTask(
            run_id=newer_run.id,
            prompt_id=seeded["prompt_id"],
            platform_code="qwen",
            idempotency_key=f"tags-new-{newer_run.id}",
            status="success",
            completed_at=now,
            finished_at=now,
        )
        db.add(task)
        db.flush()
        db.add(
            Answer(
                task_id=task.id,
                platform_code="qwen",
                prompt_id=seeded["prompt_id"],
                raw_text="交通便利，停车方便。",
                normalized_text="交通便利，停车方便。",
                model_name="qwen-model",
                collected_at=now,
            )
        )
        db.commit()
        newer_run_id = newer_run.id

    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"run_id": newer_run_id},
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["run_id"] == newer_run_id
    assert data["answer_count"] == 1
    assert {item["tag"] for item in data["items"]} == {"交通便利"}


def test_evaluation_tags_run_id_belongs_to_other_project(client, session_factory):
    with session_factory() as db:
        seeded = _seed_prompt_with_tagged_answers(db)
        other_project = MonitorProject(
            project_name="其他项目",
            status="active",
        )
        db.add(other_project)
        db.commit()

    payload = client.get(
        f"/api/geo-monitoring/projects/{other_project.id}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"run_id": seeded["run_id"]},
    ).json()
    assert payload["code"] == 40400


def test_evaluation_tags_time_range_filter(client, session_factory):
    with session_factory() as db:
        seeded = _seed_prompt_with_tagged_answers(db)
        answers = db.query(Answer).filter(Answer.prompt_id == seeded["prompt_id"]).all()
        by_platform = {answer.platform_code: answer for answer in answers}
        early_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        late_time = datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc)
        by_platform["qwen"].collected_at = early_time
        by_platform["deepseek"].collected_at = late_time
        db.commit()

    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={
            "start_at": early_time.isoformat(),
            "end_at": (early_time + timedelta(hours=1)).isoformat(),
        },
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["answer_count"] == 1
    assert "交通便利" not in {item["tag"] for item in data["items"]}


def test_evaluation_tags_no_matching_tags_returns_empty_items(client, session_factory):
    with session_factory() as db:
        seeded = _seed_prompt_with_tagged_answers(db)
        for answer in db.query(Answer).filter(Answer.prompt_id == seeded["prompt_id"]):
            answer.raw_text = "没有任何评价关键词的普通回复。"
            answer.normalized_text = answer.raw_text
        db.commit()

    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["answer_count"] == 2
    assert data["items"] == []
    assert data["total"] == 0


def test_evaluation_tags_cluster_method_rule_explicit(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"cluster_method": "rule"},
    ).json()
    assert payload["code"] == 0, payload
    assert payload["data"]["cluster_method"] == "rule"


def test_evaluation_tags_rejects_invalid_cluster_method(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"cluster_method": "semantic"},
    ).json()
    assert payload["code"] == 42200


def test_evaluation_tags_llm_success(client, session_factory, monkeypatch):
    seeded = _seed_prompt_with_neutral_answers(session_factory(), answer_count=3)
    llm_payload = {
        "items": [
            {"tag": "整体满意度", "answer_indexes": [0, 1, 2]},
            {"tag": "服务态度", "answer_indexes": [1]},
        ]
    }
    transport = FakeTransport(
        [_completion(json.dumps(llm_payload, ensure_ascii=False))]
    )
    monkeypatch.setattr(
        evaluation_tags_service,
        "_build_evaluation_tags_llm_client",
        lambda *args, **kwargs: create_agent_llm_client(
            AgentLLMConfig(
                base_url=_LLM_BASE_URL,
                api_key=_LLM_API_KEY,
                model=_LLM_MODEL,
                timeout_seconds=5.0,
                max_attempts=1,
                max_input_chars=8000,
            ),
            transport=transport,
        ),
    )
    monkeypatch.setattr(
        evaluation_tags_service,
        "_get_evaluation_tags_settings",
        lambda settings=None: _llm_settings(),
    )

    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"cluster_method": "llm"},
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["cluster_method"] == "llm"
    tags = {item["tag"]: item for item in data["items"]}
    assert tags["整体满意度"]["count"] == 3
    assert tags["服务态度"]["count"] == 1


def test_evaluation_tags_llm_failure_falls_back_to_rule(client, session_factory, monkeypatch):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    request = httpx.Request("POST", f"{_LLM_BASE_URL}/chat/completions")
    monkeypatch.setattr(
        evaluation_tags_service,
        "_build_evaluation_tags_llm_client",
        lambda *args, **kwargs: _llm_client([APITimeoutError(request)]),
    )
    monkeypatch.setattr(
        evaluation_tags_service,
        "_get_evaluation_tags_settings",
        lambda settings=None: _llm_settings(),
    )

    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"cluster_method": "llm"},
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["cluster_method"] == "rule"
    assert "演出质量" in {item["tag"] for item in data["items"]}


def test_evaluation_tags_auto_prefers_rule_when_rules_match(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"cluster_method": "auto"},
    ).json()
    assert payload["code"] == 0, payload
    assert payload["data"]["cluster_method"] == "rule"
    assert payload["data"]["items"]


def test_evaluation_tags_auto_uses_llm_when_rules_miss_and_sample_enough(
    client, session_factory, monkeypatch
):
    seeded = _seed_prompt_with_neutral_answers(session_factory(), answer_count=3)
    llm_payload = {
        "items": [{"tag": "用户反馈", "answer_indexes": [0, 1, 2]}]
    }
    transport = FakeTransport(
        [_completion(json.dumps(llm_payload, ensure_ascii=False))]
    )
    monkeypatch.setattr(
        evaluation_tags_service,
        "_build_evaluation_tags_llm_client",
        lambda *args, **kwargs: create_agent_llm_client(
            AgentLLMConfig(
                base_url=_LLM_BASE_URL,
                api_key=_LLM_API_KEY,
                model=_LLM_MODEL,
                timeout_seconds=5.0,
                max_attempts=1,
                max_input_chars=8000,
            ),
            transport=transport,
        ),
    )
    monkeypatch.setattr(
        evaluation_tags_service,
        "_get_evaluation_tags_settings",
        lambda settings=None: _llm_settings(),
    )

    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"cluster_method": "auto"},
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["cluster_method"] == "llm"
    assert data["items"][0]["tag"] == "用户反馈"


def test_evaluation_tags_llm_cache_avoids_repeat_requests(
    client, session_factory, monkeypatch
):
    seeded = _seed_prompt_with_neutral_answers(session_factory(), answer_count=3)
    llm_payload = {
        "items": [{"tag": "缓存标签", "answer_indexes": [0, 1, 2]}]
    }
    transport = FakeTransport(
        [_completion(json.dumps(llm_payload, ensure_ascii=False))]
    )
    monkeypatch.setattr(
        evaluation_tags_service,
        "_build_evaluation_tags_llm_client",
        lambda *args, **kwargs: create_agent_llm_client(
            AgentLLMConfig(
                base_url=_LLM_BASE_URL,
                api_key=_LLM_API_KEY,
                model=_LLM_MODEL,
                timeout_seconds=5.0,
                max_attempts=1,
                max_input_chars=8000,
            ),
            transport=transport,
        ),
    )
    monkeypatch.setattr(
        evaluation_tags_service,
        "_get_evaluation_tags_settings",
        lambda settings=None: _llm_settings(),
    )

    path = (
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags"
    )
    first = client.get(path, params={"cluster_method": "llm"}).json()
    second = client.get(path, params={"cluster_method": "llm"}).json()

    assert first["code"] == 0, first
    assert second["code"] == 0, second
    assert first["data"]["cluster_method"] == "llm"
    assert second["data"]["items"] == first["data"]["items"]
    assert len(transport.calls) == 1


def test_evaluation_tags_llm_error_does_not_leak_api_key(
    client, session_factory, monkeypatch, caplog
):
    seeded = _seed_prompt_with_neutral_answers(session_factory(), answer_count=3)
    request = httpx.Request("POST", f"{_LLM_BASE_URL}/chat/completions")
    monkeypatch.setattr(
        evaluation_tags_service,
        "_build_evaluation_tags_llm_client",
        lambda *args, **kwargs: _llm_client([APITimeoutError(request)]),
    )
    monkeypatch.setattr(
        evaluation_tags_service,
        "_get_evaluation_tags_settings",
        lambda settings=None: _llm_settings(),
    )

    with caplog.at_level("WARNING"):
        payload = client.get(
            f"/api/geo-monitoring/projects/{seeded['project_id']}/"
            f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
            params={"cluster_method": "llm"},
        ).json()

    assert payload["code"] == 0, payload
    joined = " ".join(record.message for record in caplog.records)
    assert _LLM_API_KEY not in joined

