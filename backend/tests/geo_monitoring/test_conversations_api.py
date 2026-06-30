"""Task P0-3：AI 对话记录问题聚合接口测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
from tests.geo_monitoring.analysis_support import patch_fake_llm_for_analyze
from tests.geo_monitoring.agents.test_graph import FakeLLMClient


def _seed_multi_prompt_run(
    db,
    *,
    platforms: tuple[str, ...] = ("qwen", "deepseek"),
) -> dict[str, Any]:
    project = MonitorProject(
        project_name="对话记录测试",
        status="active",
        official_domain="example.com",
    )
    db.add(project)
    db.flush()

    target = Brand(
        project_id=project.id,
        brand_name="目标品牌",
        brand_type="target",
        status="active",
    )
    db.add(target)
    db.flush()

    prompt_set = PromptSet(
        project_id=project.id,
        set_name="对话集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()

    prompt_a = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="q1",
        prompt_text="哪个文旅品牌更值得推荐？",
        prompt_type="brand_recommendation",
    )
    prompt_b = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="q2",
        prompt_text="杭州有哪些演艺项目？",
        prompt_type="category_explore",
    )
    db.add_all([prompt_a, prompt_b])
    db.flush()

    for code in platforms:
        db.add(
            AIPlatform(
                platform_code=code,
                platform_name=code,
                model_name=f"{code}-model",
                enabled=True,
            )
        )

    run = MonitorRun(
        run_no="RUN-CONV-1",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        platform_codes=list(platforms),
        status="completed",
        collection_status="completed",
        analysis_status="pending",
        total_tasks=len(platforms) * 2,
        expected_query_count=len(platforms) * 2,
        succeeded_tasks=len(platforms) * 2,
        valid_answer_count=len(platforms) * 2,
    )
    db.add(run)
    db.flush()

    now = datetime.now(timezone.utc)
    answer_ids: dict[str, int] = {}
    for prompt in (prompt_a, prompt_b):
        for platform_code in platforms:
            task = QueryTask(
                run_id=run.id,
                prompt_id=prompt.id,
                platform_code=platform_code,
                idempotency_key=f"conv-{run.id}-{prompt.id}-{platform_code}",
                status="success",
                completed_at=now,
                finished_at=now,
            )
            db.add(task)
            db.flush()

            text = f"{platform_code} 推荐目标品牌。"
            answer = Answer(
                task_id=task.id,
                platform_code=platform_code,
                prompt_id=prompt.id,
                raw_text=text,
                normalized_text=text,
                model_name=f"{platform_code}-model",
                collected_at=now,
            )
            db.add(answer)
            db.flush()
            answer_ids[f"{prompt.id}-{platform_code}"] = answer.id

            db.add(
                AnswerBrandResult(
                    answer_id=answer.id,
                    brand_id=target.id,
                    is_mentioned=True,
                    mention_count=1,
                    first_position=0,
                    sentiment="positive",
                )
            )
            if prompt.id == prompt_a.id and platform_code == "qwen":
                db.add(
                    AnswerCitation(
                        answer_id=answer.id,
                        citation_no=1,
                        title="官方介绍",
                        url="https://example.com/intro",
                        domain="example.com",
                        source_type="web",
                    )
                )

    db.commit()
    return {
        "run_id": run.id,
        "project_id": project.id,
        "prompt_a_id": prompt_a.id,
        "prompt_b_id": prompt_b.id,
        "target_brand_id": target.id,
        "platforms": platforms,
        "answer_ids": answer_ids,
    }


@pytest.fixture
def conversation_run(client, session_factory, monkeypatch):
    llm = patch_fake_llm_for_analyze(monkeypatch)
    with session_factory() as db:
        seeded = _seed_multi_prompt_run(db)
    response = client.post(f"/api/geo-monitoring/runs/{seeded['run_id']}/analyze")
    assert response.json()["code"] == 0
    return seeded


def test_conversation_questions_aggregate_by_prompt(client, conversation_run):
    project_id = conversation_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/conversation-questions"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["run_id"] == conversation_run["run_id"]
    assert data["total"] == 2
    assert len(data["items"]) == 2

    prompt_ids = {item["prompt_id"] for item in data["items"]}
    assert prompt_ids == {
        conversation_run["prompt_a_id"],
        conversation_run["prompt_b_id"],
    }

    row = next(
        item
        for item in data["items"]
        if item["prompt_id"] == conversation_run["prompt_a_id"]
    )
    assert row["prompt_text"] == "哪个文旅品牌更值得推荐？"
    assert row["valid_answer_count"] == 2
    assert row["mention_count"] == 2
    assert row["visibility_rate"] == "1.0000"
    assert row["top10_rate"] is not None
    assert row["share_of_voice"] is not None
    assert row["brand_mention_total_count"] == row["mention_count"]
    assert len(row["platform_metrics"]) == 2


def test_conversation_questions_keyword_filter(client, conversation_run):
    project_id = conversation_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/conversation-questions",
        params={"keyword": "杭州"},
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["total"] == 1
    assert data["items"][0]["prompt_id"] == conversation_run["prompt_b_id"]


def test_conversation_questions_platform_codes_filter(client, conversation_run):
    project_id = conversation_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/conversation-questions",
        params={"platform_codes": ["qwen"]},
    )
    body = response.json()
    assert body["code"] == 0
    row = next(
        item
        for item in body["data"]["items"]
        if item["prompt_id"] == conversation_run["prompt_a_id"]
    )
    assert row["valid_answer_count"] == 1
    assert len(row["platform_metrics"]) == 1
    assert row["platform_metrics"][0]["platform_code"] == "qwen"


def test_conversation_question_answers_detail(client, conversation_run):
    project_id = conversation_run["project_id"]
    prompt_id = conversation_run["prompt_a_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/conversation-questions/{prompt_id}/answers"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["prompt_id"] == prompt_id
    assert data["total"] == 2
    assert len(data["items"]) == 2

    qwen_item = next(
        item for item in data["items"] if item["platform_code"] == "qwen"
    )
    assert qwen_item["citations"]
    assert qwen_item["citations"][0]["title"] == "官方介绍"
    assert qwen_item["brand_results"]
    assert qwen_item["brand_results"][0]["brand_name"] == "目标品牌"
    assert qwen_item["reasoning_text"] is None
    assert qwen_item["search_keywords"] == []


def test_conversation_question_answers_empty_citations_and_brands(
    client, session_factory, monkeypatch
):
    llm = patch_fake_llm_for_analyze(monkeypatch)

    with session_factory() as db:
        project = MonitorProject(project_name="空结果测试", status="active")
        db.add(project)
        db.flush()
        db.add(
            Brand(
                project_id=project.id,
                brand_name="目标品牌",
                brand_type="target",
                status="active",
            )
        )
        prompt_set = PromptSet(
            project_id=project.id,
            set_name="空集",
            version_no="v1",
            status="active",
        )
        db.add(prompt_set)
        db.flush()
        prompt = Prompt(
            prompt_set_id=prompt_set.id,
            prompt_code="empty",
            prompt_text="空答案问题",
            prompt_type="generic",
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
            run_no="RUN-EMPTY",
            project_id=project.id,
            prompt_set_id=prompt_set.id,
            prompt_set_version="v1",
            platform_codes=["qwen"],
            status="completed",
            collection_status="completed",
            analysis_status="pending",
            total_tasks=1,
            expected_query_count=1,
            succeeded_tasks=1,
            valid_answer_count=1,
        )
        db.add(run)
        db.flush()
        now = datetime.now(timezone.utc)
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code="qwen",
            idempotency_key=f"empty-{run.id}",
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
                prompt_id=prompt.id,
                raw_text="无品牌提及",
                normalized_text="无品牌提及",
                model_name="qwen-model",
                collected_at=now,
            )
        )
        db.commit()
        project_id = project.id
        prompt_id = prompt.id
        run_id = run.id

    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/conversation-questions/{prompt_id}/answers"
    )
    body = response.json()
    assert body["code"] == 0
    item = body["data"]["items"][0]
    assert item["citations"] == []
    assert item["brand_results"] == []


def _seed_valid_answer_boundary_run(db) -> dict[str, Any]:
    project = MonitorProject(project_name="有效答案边界", status="active")
    db.add(project)
    db.flush()
    target = Brand(
        project_id=project.id,
        brand_name="目标品牌",
        brand_type="target",
        status="active",
    )
    db.add(target)
    db.flush()
    prompt_set = PromptSet(
        project_id=project.id,
        set_name="边界集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()
    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="boundary",
        prompt_text="边界测试问题",
        prompt_type="generic",
    )
    db.add(prompt)
    db.flush()
    for code in ("qwen", "deepseek", "kimi"):
        db.add(
            AIPlatform(
                platform_code=code,
                platform_name=code,
                model_name=f"{code}-model",
                enabled=True,
            )
        )
    run = MonitorRun(
        run_no="RUN-BOUNDARY",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        platform_codes=["qwen", "deepseek", "kimi"],
        status="completed",
        collection_status="completed",
        analysis_status="completed",
        total_tasks=3,
        expected_query_count=3,
        succeeded_tasks=2,
        valid_answer_count=1,
    )
    db.add(run)
    db.flush()
    now = datetime.now(timezone.utc)

    valid_task = QueryTask(
        run_id=run.id,
        prompt_id=prompt.id,
        platform_code="qwen",
        idempotency_key=f"boundary-{run.id}-qwen",
        status="success",
        completed_at=now,
        finished_at=now,
    )
    db.add(valid_task)
    db.flush()
    valid_answer = Answer(
        task_id=valid_task.id,
        platform_code="qwen",
        prompt_id=prompt.id,
        raw_text="推荐目标品牌",
        normalized_text="推荐目标品牌",
        model_name="qwen-model",
        collected_at=now,
    )
    db.add(valid_answer)
    db.flush()
    db.add(
        AnswerBrandResult(
            answer_id=valid_answer.id,
            brand_id=target.id,
            is_mentioned=True,
            mention_count=1,
            first_position=1,
        )
    )

    failed_task = QueryTask(
        run_id=run.id,
        prompt_id=prompt.id,
        platform_code="deepseek",
        idempotency_key=f"boundary-{run.id}-deepseek",
        status="failed",
        completed_at=now,
        finished_at=now,
    )
    db.add(failed_task)
    db.flush()
    db.add(
        Answer(
            task_id=failed_task.id,
            platform_code="deepseek",
            prompt_id=prompt.id,
            raw_text="失败任务不应计入",
            normalized_text="失败任务不应计入",
            model_name="deepseek-model",
            collected_at=now,
        )
    )

    empty_task = QueryTask(
        run_id=run.id,
        prompt_id=prompt.id,
        platform_code="kimi",
        idempotency_key=f"boundary-{run.id}-kimi",
        status="success",
        completed_at=now,
        finished_at=now,
    )
    db.add(empty_task)
    db.flush()
    db.add(
        Answer(
            task_id=empty_task.id,
            platform_code="kimi",
            prompt_id=prompt.id,
            raw_text="   ",
            normalized_text="   ",
            model_name="kimi-model",
            collected_at=now,
        )
    )
    db.commit()
    return {
        "project_id": project.id,
        "run_id": run.id,
        "prompt_id": prompt.id,
    }


def test_conversation_questions_excludes_invalid_answers_from_metrics(
    client, session_factory
):
    with session_factory() as db:
        seeded = _seed_valid_answer_boundary_run(db)

    response = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/conversation-questions",
        params={"run_id": seeded["run_id"]},
    )
    body = response.json()
    assert body["code"] == 0
    row = body["data"]["items"][0]
    assert row["valid_answer_count"] == 1
    assert row["visibility_rate"] == "1.0000"
    assert row["top1_rate"] == "1.0000"
    assert row["top3_rate"] == "1.0000"
    assert row["mention_count"] == 1

    platform_codes = {item["platform_code"] for item in row["platform_metrics"]}
    assert platform_codes == {"qwen", "deepseek", "kimi"}
    qwen_metrics = next(
        item for item in row["platform_metrics"] if item["platform_code"] == "qwen"
    )
    deepseek_metrics = next(
        item for item in row["platform_metrics"] if item["platform_code"] == "deepseek"
    )
    kimi_metrics = next(
        item for item in row["platform_metrics"] if item["platform_code"] == "kimi"
    )
    assert qwen_metrics["valid_answer_count"] == 1
    assert deepseek_metrics["valid_answer_count"] == 0
    assert deepseek_metrics["visibility_rate"] is None
    assert deepseek_metrics["top1_rate"] is None
    assert deepseek_metrics["top3_rate"] is None
    assert kimi_metrics["valid_answer_count"] == 0
    assert kimi_metrics["visibility_rate"] is None


def test_conversation_questions_all_invalid_answers_yield_null_rates(
    client, session_factory
):
    with session_factory() as db:
        project = MonitorProject(project_name="全无有效答案", status="active")
        db.add(project)
        db.flush()
        db.add(
            Brand(
                project_id=project.id,
                brand_name="目标品牌",
                brand_type="target",
                status="active",
            )
        )
        prompt_set = PromptSet(
            project_id=project.id,
            set_name="空有效集",
            version_no="v1",
            status="active",
        )
        db.add(prompt_set)
        db.flush()
        prompt = Prompt(
            prompt_set_id=prompt_set.id,
            prompt_code="none",
            prompt_text="无有效答案问题",
            prompt_type="generic",
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
            run_no="RUN-NONE",
            project_id=project.id,
            prompt_set_id=prompt_set.id,
            prompt_set_version="v1",
            platform_codes=["qwen"],
            status="completed",
            collection_status="completed",
            analysis_status="completed",
            total_tasks=1,
            expected_query_count=1,
            succeeded_tasks=0,
            valid_answer_count=0,
        )
        db.add(run)
        db.flush()
        now = datetime.now(timezone.utc)
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code="qwen",
            idempotency_key=f"none-{run.id}",
            status="failed",
            completed_at=now,
            finished_at=now,
        )
        db.add(task)
        db.flush()
        db.add(
            Answer(
                task_id=task.id,
                platform_code="qwen",
                prompt_id=prompt.id,
                raw_text="失败任务答案",
                normalized_text="失败任务答案",
                model_name="qwen-model",
                collected_at=now,
            )
        )
        db.commit()
        project_id = project.id
        run_id = run.id

    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/conversation-questions",
        params={"run_id": run_id},
    )
    body = response.json()
    assert body["code"] == 0
    row = body["data"]["items"][0]
    assert row["valid_answer_count"] == 0
    assert row["visibility_rate"] is None
    assert row["top1_rate"] is None
    assert row["top3_rate"] is None
    assert row["average_rank"] is None


def test_conversation_questions_deduplicates_platform_codes(client, conversation_run):
    project_id = conversation_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/conversation-questions",
        params={"platform_codes": ["qwen", "qwen"]},
    )
    body = response.json()
    assert body["code"] == 0
    row = next(
        item
        for item in body["data"]["items"]
        if item["prompt_id"] == conversation_run["prompt_a_id"]
    )
    assert len(row["platform_metrics"]) == 1
    assert row["platform_metrics"][0]["platform_code"] == "qwen"


def test_conversation_question_answers_db_pagination(client, conversation_run):
    project_id = conversation_run["project_id"]
    prompt_id = conversation_run["prompt_a_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/conversation-questions/{prompt_id}/answers",
        params={"page": 1, "page_size": 1},
    )
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["total"] == 2
    assert len(body["data"]["items"]) == 1
