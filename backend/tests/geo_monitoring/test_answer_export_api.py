"""Task P1-3：回答详情扩展与导出接口测试。"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import pytest

import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    AnswerBrandResult,
    AnswerCitation,
    Brand,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from tests.geo_monitoring.agents.test_graph import FakeLLMClient
from tests.geo_monitoring.test_conversations_api import _seed_multi_prompt_run
from tests.geo_monitoring.test_source_analysis_api import _seed_source_analysis_run


def _decode_csv(content: bytes) -> list[list[str]]:
    text = content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def test_answer_detail_includes_prompt_and_metadata(client, session_factory):
    with session_factory() as db:
        project = MonitorProject(project_name="答案扩展", status="active")
        db.add(project)
        db.flush()
        prompt_set = PromptSet(
            project_id=project.id,
            set_name="集",
            version_no="v1",
            status="active",
        )
        db.add(prompt_set)
        db.flush()
        prompt = Prompt(
            prompt_set_id=prompt_set.id,
            prompt_code="q1",
            prompt_text="哪个文旅品牌更值得推荐？",
            prompt_type="brand_recommendation",
        )
        db.add(prompt)
        db.flush()
        db.add(
            AIPlatform(
                platform_code="qwen",
                platform_name="qwen",
                model_name="qwen-model",
                enabled=True,
            )
        )
        run = MonitorRun(
            run_no="RUN-DETAIL",
            project_id=project.id,
            prompt_set_id=prompt_set.id,
            prompt_set_version="v1",
            platform_codes=["qwen"],
            status="completed",
            total_tasks=1,
            expected_query_count=1,
        )
        db.add(run)
        db.flush()
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code="qwen",
            idempotency_key="detail-task",
            status="success",
        )
        db.add(task)
        db.flush()
        answer = Answer(
            task_id=task.id,
            platform_code="qwen",
            prompt_id=prompt.id,
            raw_text="推荐目标品牌。",
            normalized_text="推荐目标品牌。",
            raw_response_json={
                "result": {
                    "data": {
                        "result": [
                            {"search_word": "杭州文旅,宋城"},
                            {"thinking": "比较各品牌优势。"},
                        ]
                    }
                }
            },
        )
        db.add(answer)
        db.flush()
        db.add(
            AnswerCitation(
                answer_id=answer.id,
                citation_no=1,
                title="官方介绍",
                url="https://example.com",
                domain="example.com",
            )
        )
        answer_id = answer.id
        db.commit()

    response = client.get(f"/api/geo-monitoring/answers/{answer_id}")
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["prompt_text"] == "哪个文旅品牌更值得推荐？"
    assert data["prompt_type"] == "brand_recommendation"
    assert data["reasoning_text"] == "比较各品牌优势。"
    assert data["search_keywords"] == ["杭州文旅", "宋城"]
    assert data["raw_response_safe"] is not None
    assert len(data["citations"]) == 1


@pytest.fixture
def conversation_run(client, session_factory, monkeypatch):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_multi_prompt_run(db)
    response = client.post(f"/api/geo-monitoring/runs/{seeded['run_id']}/analyze")
    assert response.json()["code"] == 0
    return seeded


def test_conversation_question_answers_exposes_metadata_from_raw_response(
    client, session_factory, conversation_run, monkeypatch
):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        answer = db.get(Answer, conversation_run["answer_ids"]["1-qwen"])
        answer.raw_response_json = {
            "result": {
                "data": {
                    "result": [
                        {"search_word": "文旅推荐"},
                        {"thinking": "分析用户需求。"},
                    ]
                }
            }
        }
        db.commit()

    project_id = conversation_run["project_id"]
    prompt_id = conversation_run["prompt_a_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/conversation-questions/{prompt_id}/answers"
    )
    body = response.json()
    assert body["code"] == 0
    qwen_item = next(
        item for item in body["data"]["items"] if item["platform_code"] == "qwen"
    )
    assert qwen_item["reasoning_text"] == "分析用户需求。"
    assert qwen_item["search_keywords"] == ["文旅推荐"]


def test_conversation_questions_export_csv(client, conversation_run):
    project_id = conversation_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/conversation-questions/export",
        params={"keyword": "杭州"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = _decode_csv(response.content)
    assert rows[0][0] == "问题ID"
    assert len(rows) == 2
    assert "杭州" in rows[1][1]


@pytest.fixture
def source_analysis_run(client, session_factory):
    with session_factory() as db:
        return _seed_source_analysis_run(db)


def test_source_analysis_export_csv(client, source_analysis_run):
    project_id = source_analysis_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis/export",
        params={"source_type": "official_site"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = _decode_csv(response.content)
    assert rows[0][0] == "域名"
    assert len(rows) >= 2
    assert rows[1][0] == "example.com"


def test_export_conversation_questions_fetches_all_pages(monkeypatch):
    from app.geo_monitoring.services import conversations as conversations_service

    calls: list[int] = []

    def fake_list(*_args, **kwargs):
        page = kwargs["page"]
        calls.append(page)
        if page == 1:
            return {
                "total": 3,
                "items": [
                    {
                        "prompt_id": 1,
                        "prompt_text": "问题1",
                        "prompt_type": "generic",
                        "run_id": 9,
                        "valid_answer_count": 1,
                        "visibility_rate": "1.0000",
                        "mention_count": 1,
                        "average_rank": None,
                        "top1_rate": None,
                        "top3_rate": None,
                        "top10_rate": None,
                        "share_of_voice": None,
                        "positive_rate": None,
                        "neutral_rate": None,
                        "negative_rate": None,
                    },
                    {
                        "prompt_id": 2,
                        "prompt_text": "问题2",
                        "prompt_type": "generic",
                        "run_id": 9,
                        "valid_answer_count": 1,
                        "visibility_rate": "1.0000",
                        "mention_count": 1,
                        "average_rank": None,
                        "top1_rate": None,
                        "top3_rate": None,
                        "top10_rate": None,
                        "share_of_voice": None,
                        "positive_rate": None,
                        "neutral_rate": None,
                        "negative_rate": None,
                    },
                ],
            }
        return {
            "total": 3,
            "items": [
                {
                    "prompt_id": 3,
                    "prompt_text": "问题3",
                    "prompt_type": "generic",
                    "run_id": 9,
                    "valid_answer_count": 1,
                    "visibility_rate": "1.0000",
                    "mention_count": 1,
                    "average_rank": None,
                    "top1_rate": None,
                    "top3_rate": None,
                    "top10_rate": None,
                    "share_of_voice": None,
                    "positive_rate": None,
                    "neutral_rate": None,
                    "negative_rate": None,
                }
            ],
        }

    monkeypatch.setattr(
        conversations_service,
        "list_conversation_questions",
        fake_list,
    )
    headers, rows = conversations_service.export_conversation_questions_rows(
        db=None,
        project_id=1,
    )
    assert headers[0] == "问题ID"
    assert [row[0] for row in rows] == [1, 2, 3]
    assert calls == [1, 2]


def test_export_source_analysis_fetches_all_pages(monkeypatch):
    from app.geo_monitoring.services import source_analysis as source_analysis_service

    calls: list[int] = []

    def fake_get(*_args, **kwargs):
        page = kwargs["page"]
        calls.append(page)
        if page == 1:
            return {
                "platform_columns": [{"platform_code": "qwen", "has_citation_data": True}],
                "sites": {
                    "total": 3,
                    "items": [
                        {
                            "domain": "a.example.com",
                            "source_name": "A",
                            "source_type": "official_site",
                            "source_type_label": "官网",
                            "link_count": 2,
                            "citation_rate": "0.5000",
                            "display_value": "2",
                            "platform_values": [
                                {
                                    "platform_code": "qwen",
                                    "link_count": 2,
                                    "citation_rate": "0.5000",
                                    "has_citation_data": True,
                                    "display_value": "2",
                                }
                            ],
                        },
                        {
                            "domain": "b.example.com",
                            "source_name": "B",
                            "source_type": "official_site",
                            "source_type_label": "官网",
                            "link_count": 1,
                            "citation_rate": "0.2500",
                            "display_value": "1",
                            "platform_values": [
                                {
                                    "platform_code": "qwen",
                                    "link_count": 1,
                                    "citation_rate": "0.2500",
                                    "has_citation_data": True,
                                    "display_value": "1",
                                }
                            ],
                        },
                    ],
                },
            }
        return {
            "platform_columns": [{"platform_code": "qwen", "has_citation_data": True}],
            "sites": {
                "total": 3,
                "items": [
                    {
                        "domain": "c.example.com",
                        "source_name": "C",
                        "source_type": "official_site",
                        "source_type_label": "官网",
                        "link_count": 1,
                        "citation_rate": "0.2500",
                        "display_value": "1",
                        "platform_values": [
                            {
                                "platform_code": "qwen",
                                "link_count": 1,
                                "citation_rate": "0.2500",
                                "has_citation_data": True,
                                "display_value": "1",
                            }
                        ],
                    }
                ],
            },
        }

    monkeypatch.setattr(source_analysis_service, "get_source_analysis", fake_get)
    headers, rows = source_analysis_service.export_source_analysis_rows(
        db=None,
        project_id=1,
    )
    assert headers[0] == "域名"
    assert [row[0] for row in rows] == [
        "a.example.com",
        "b.example.com",
        "c.example.com",
    ]
    assert calls == [1, 2]
