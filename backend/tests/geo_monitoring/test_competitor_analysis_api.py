"""Task P0-5：竞品分析页面级接口测试。"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import select

import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    AnswerBrandResult,
    Brand,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.services.analysis import PlatformAnalysis
from tests.geo_monitoring.agents.test_graph import FakeLLMClient, _seed_run


def _seed_run_without_analysis(db) -> dict[str, Any]:
    project = MonitorProject(
        project_name="竞品空数据测试",
        status="active",
        official_domain="example.com",
    )
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
    db.flush()

    prompt_set = PromptSet(
        project_id=project.id,
        set_name="竞品集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()

    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="q1",
        prompt_text="哪个品牌更好？",
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
        run_no="RUN-COMP-EMPTY",
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
        idempotency_key=f"comp-empty-{run.id}",
        status="success",
        completed_at=now,
        finished_at=now,
    )
    db.add(task)
    db.flush()

    answer = Answer(
        task_id=task.id,
        platform_code="qwen",
        prompt_id=prompt.id,
        raw_text="qwen 推荐目标品牌。",
        normalized_text="qwen 推荐目标品牌。",
        model_name="qwen-model",
        collected_at=now,
    )
    db.add(answer)
    db.commit()
    return {"project_id": project.id, "run_id": run.id, "collected_at": now}


@pytest.fixture
def analyzed_competitor_run(client, session_factory, monkeypatch):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))
    response = client.post(f"/api/geo-monitoring/runs/{seeded['run_id']}/analyze")
    assert response.json()["code"] == 0
    return seeded


def test_competitor_analysis_empty_when_no_analysis_data(client, session_factory):
    with session_factory() as db:
        seeded = _seed_run_without_analysis(db)

    response = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/competitor-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["run_id"] == seeded["run_id"]
    assert data["has_analysis_data"] is False
    assert data["boards"]["mention_rate"] == []
    assert data["boards"]["average_rank"] == []
    assert data["boards"]["mention_count"] == []
    assert data["kpis"]["mention_rate"] is None
    assert data["trends"]["days"] == []
    assert data["trends"]["mention_rate"] == []
    assert data["trends"]["average_rank"] == []
    assert data["trends"]["mention_count"] == []


def test_competitor_analysis_empty_when_unanalyzed_run_with_time_filter(
    client, session_factory
):
    with session_factory() as db:
        seeded = _seed_run_without_analysis(db)
        collected_at = seeded["collected_at"]

    response = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/competitor-analysis",
        params={
            "start_at": collected_at.isoformat(),
            "end_at": collected_at.isoformat(),
        },
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["has_analysis_data"] is False
    assert data["boards"]["mention_rate"] == []


def test_competitor_analysis_target_in_kpi_and_boards_when_analyzed(
    client, analyzed_competitor_run
):
    project_id = analyzed_competitor_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["has_analysis_data"] is True
    assert data["target_brand"]["brand_name"] == "目标品牌"
    assert data["kpis"]["mention_rate"] is not None
    assert data["kpis"]["mention_count"] >= 1

    for board_name in ("mention_rate", "average_rank", "mention_count"):
        board = data["boards"][board_name]
        assert board, f"{board_name} board should not be empty"
        target_rows = [row for row in board if row["is_target"]]
        assert len(target_rows) == 1
        assert target_rows[0]["brand_name"] == "目标品牌"


def test_competitor_analysis_excludes_candidate_brand_from_boards(
    client, session_factory, monkeypatch
):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))
        candidate = Brand(
            project_id=seeded["project_id"],
            brand_name="候选品牌",
            brand_type="candidate",
            status="active",
        )
        db.add(candidate)
        db.commit()
        run_id = seeded["run_id"]
        project_id = seeded["project_id"]
        candidate_id = candidate.id

    client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    with session_factory() as db:
        row = db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == run_id,
                PlatformAnalysis.platform_code == "qwen",
            )
        ).scalar_one()
        summary = copy.deepcopy(row.summary_json or {})
        metrics = summary.setdefault("metrics", {})
        metrics["brand_metrics"] = list(metrics.get("brand_metrics") or []) + [
            {
                "brand_id": candidate_id,
                "brand_name": "候选品牌",
                "brand_category": "candidate",
                "mention_count": 99,
                "mention_conversation_count": 9,
                "mention_rate": {
                    "numerator": 9,
                    "denominator": 10,
                    "rate": "0.9000",
                },
                "mention_rate_percent": "90.0000",
                "average_mention_rank": "1.0",
                "share_of_voice": "0.9000",
                "positive_neutral_sentiment_percent": "100.0000",
                "brand_score": "100.0000",
                "include_in_avg_rank_display": True,
            }
        ]
        row.summary_json = summary
        db.commit()

    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    brand_ids = {
        row["brand_id"]
        for board in body["data"]["boards"].values()
        for row in board
    }
    assert candidate_id not in brand_ids


def test_competitor_analysis_mixed_platform_snapshot_fallback(
    client, session_factory, monkeypatch
):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen", "deepseek"))
        competitor_id = db.execute(
            select(Brand.id).where(
                Brand.project_id == seeded["project_id"],
                Brand.brand_type == "competitor",
            )
        ).scalar_one()
        run_id = seeded["run_id"]
        project_id = seeded["project_id"]
        db.commit()

    client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    with session_factory() as db:
        deepseek_row = db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == run_id,
                PlatformAnalysis.platform_code == "deepseek",
            )
        ).scalar_one()
        summary = copy.deepcopy(deepseek_row.summary_json or {})
        metrics = summary.get("metrics") or {}
        metrics = dict(metrics)
        metrics.pop("brand_metrics", None)
        summary["metrics"] = metrics
        deepseek_row.summary_json = summary
        deepseek_row.top_competitors = [
            {
                "brand_id": competitor_id,
                "brand_name": "竞品B",
                "mention_answer_count": 1,
                "visibility_rate": "1.0000",
            }
        ]
        deepseek_row.brand_mention_count = 0
        deepseek_row.valid_answer_count = 1
        db.commit()

    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["has_analysis_data"] is True
    competitor_rows = [
        row
        for board in data["boards"].values()
        for row in board
        if row["brand_id"] == competitor_id
    ]
    assert competitor_rows
    assert any(row["mention_count"] >= 1 for row in competitor_rows)


def test_competitor_analysis_brand_scope_validation(client, analyzed_competitor_run):
    project_id = analyzed_competitor_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis",
        params={"brand_scope": "invalid"},
    )
    body = response.json()
    assert body["code"] == 422


def test_competitor_analysis_top1_rate_follows_time_filter(
    client, session_factory, monkeypatch
):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen", "deepseek"))
        run_id = seeded["run_id"]
        project_id = seeded["project_id"]
        target_id = seeded["target_brand_id"]
        db.commit()

    client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    early = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    late = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)

    with session_factory() as db:
        competitor_id = db.execute(
            select(Brand.id).where(
                Brand.project_id == project_id,
                Brand.brand_type == "competitor",
            )
        ).scalar_one()
        answers = list(db.execute(select(Answer)).scalars().all())
        for answer in answers:
            if answer.platform_code == "qwen":
                answer.collected_at = early
                target_result = (
                    db.query(AnswerBrandResult)
                    .filter(
                        AnswerBrandResult.answer_id == answer.id,
                        AnswerBrandResult.brand_id == target_id,
                    )
                    .one()
                )
                target_result.first_position = 10
                competitor_result = (
                    db.query(AnswerBrandResult)
                    .filter(
                        AnswerBrandResult.answer_id == answer.id,
                        AnswerBrandResult.brand_id == competitor_id,
                    )
                    .one()
                )
                competitor_result.first_position = 30
            else:
                answer.collected_at = late
                target_result = (
                    db.query(AnswerBrandResult)
                    .filter(
                        AnswerBrandResult.answer_id == answer.id,
                        AnswerBrandResult.brand_id == target_id,
                    )
                    .one()
                )
                target_result.first_position = 30
                competitor_result = (
                    db.query(AnswerBrandResult)
                    .filter(
                        AnswerBrandResult.answer_id == answer.id,
                        AnswerBrandResult.brand_id == competitor_id,
                    )
                    .one()
                )
                competitor_result.first_position = 10
        db.commit()

    snapshot_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis"
    )
    assert snapshot_response.json()["data"]["kpis"]["top1_rate"] == "1.0000"

    early_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis",
        params={
            "start_at": early.isoformat(),
            "end_at": early.isoformat(),
        },
    )
    assert early_response.json()["data"]["kpis"]["top1_rate"] == "1.0000"

    late_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis",
        params={
            "start_at": late.isoformat(),
            "end_at": late.isoformat(),
        },
    )
    assert late_response.json()["data"]["kpis"]["top1_rate"] == "0.0000"

    both_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis",
        params={
            "start_at": early.isoformat(),
            "end_at": late.isoformat(),
        },
    )
    assert both_response.json()["data"]["kpis"]["top1_rate"] == "0.5000"


def test_competitor_analysis_top1_rate_uses_relative_rank_not_char_position(
    client, session_factory, monkeypatch
):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))
        run_id = seeded["run_id"]
        project_id = seeded["project_id"]
        target_id = seeded["target_brand_id"]
        competitor_id = db.execute(
            select(Brand.id).where(
                Brand.project_id == seeded["project_id"],
                Brand.brand_type == "competitor",
            )
        ).scalar_one()
        db.commit()

    client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    collected_at = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    with session_factory() as db:
        answer = db.execute(select(Answer).limit(1)).scalar_one()
        answer.collected_at = collected_at
        target_result = (
            db.query(AnswerBrandResult)
            .filter(
                AnswerBrandResult.answer_id == answer.id,
                AnswerBrandResult.brand_id == target_id,
            )
            .one()
        )
        target_result.first_position = 10
        competitor_result = (
            db.query(AnswerBrandResult)
            .filter(
                AnswerBrandResult.answer_id == answer.id,
                AnswerBrandResult.brand_id == competitor_id,
            )
            .one()
        )
        competitor_result.first_position = 30
        db.commit()

    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis",
        params={
            "start_at": collected_at.isoformat(),
            "end_at": collected_at.isoformat(),
        },
    )
    assert response.json()["data"]["kpis"]["top1_rate"] == "1.0000"


def test_competitor_analysis_rejects_start_after_end(client, analyzed_competitor_run):
    project_id = analyzed_competitor_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis",
        params={
            "start_at": "2099-01-02T00:00:00+00:00",
            "end_at": "2099-01-01T00:00:00+00:00",
        },
    )
    body = response.json()
    assert body["code"] == 422


def test_competitor_analysis_brand_scope_top5_and_all(client, analyzed_competitor_run):
    project_id = analyzed_competitor_run["project_id"]
    top5_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis",
        params={"brand_scope": "top5"},
    )
    all_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis",
        params={"brand_scope": "all"},
    )
    assert top5_response.json()["code"] == 0
    assert all_response.json()["code"] == 0
    assert top5_response.json()["data"]["brand_scope"] == "top5"
    assert all_response.json()["data"]["brand_scope"] == "all"


def test_competitor_analysis_trends_empty_not_from_target_trends(
    client, analyzed_competitor_run
):
    project_id = analyzed_competitor_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    trends = body["data"]["trends"]
    assert trends["days"] == []
    assert trends["mention_rate"] == []
    assert trends["average_rank"] == []
    assert trends["mention_count"] == []


def test_competitor_analysis_platform_codes_filter(client, analyzed_competitor_run):
    project_id = analyzed_competitor_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis",
        params={"platform_codes": ["qwen"]},
    )
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["has_analysis_data"] is True


def test_competitor_analysis_run_id_belongs_to_other_project(client, session_factory):
    with session_factory() as db:
        seeded_a = _seed_run_without_analysis(db)
        project_b = MonitorProject(
            project_name="其他项目",
            status="active",
            official_domain="other.com",
        )
        db.add(project_b)
        db.commit()

    response = client.get(
        f"/api/geo-monitoring/projects/{project_b.id}/competitor-analysis",
        params={"run_id": seeded_a["run_id"]},
    )
    body = response.json()
    assert body["code"] == 40400


def test_competitor_analysis_mention_count_from_brand_results(
    client, session_factory, monkeypatch
):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))
        target_id = seeded["target_brand_id"]
        answer = db.execute(select(Answer).limit(1)).scalar_one()
        brand_result = (
            db.query(AnswerBrandResult)
            .filter(
                AnswerBrandResult.answer_id == answer.id,
                AnswerBrandResult.brand_id == target_id,
            )
            .one()
        )
        brand_result.mention_count = 5
        db.commit()

    client.post(f"/api/geo-monitoring/runs/{seeded['run_id']}/analyze")
    response = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/competitor-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["kpis"]["mention_count"] >= 5
