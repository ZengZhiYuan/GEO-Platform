"""分析查询与看板 API 测试。"""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401
from app.geo_monitoring.models import Brand
from app.geo_monitoring.services.analysis import PlatformAnalysis
from tests.geo_monitoring.agents.test_graph import FakeLLMClient, _seed_run


@pytest.fixture
def analyzed_run(client, session_factory, monkeypatch):
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


def test_manual_analyze_trigger(client, analyzed_run):
    response = client.post(
        f"/api/geo-monitoring/runs/{analyzed_run['run_id']}/analyze"
    )
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["analysis_status"] in {"completed", "partial_success", "skipped"}


def test_get_run_analysis(client, analyzed_run):
    response = client.get(
        f"/api/geo-monitoring/runs/{analyzed_run['run_id']}/analysis"
    )
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["run_id"] == analyzed_run["run_id"]
    assert len(body["data"]["platforms"]) == 1
    platform = body["data"]["platforms"][0]
    assert platform["platform_code"] == "qwen"
    assert platform["valid_answer_count"] == 1
    assert platform["brand_mention_rate"] is not None
    assert platform["brand_top1_mention_rate"] == "1.0000"
    assert platform["brand_top3_mention_rate"] == "1.0000"


def test_get_agent_executions(client, analyzed_run):
    response = client.get(
        f"/api/geo-monitoring/runs/{analyzed_run['run_id']}/agent-executions"
    )
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["total"] >= 1
    assert any(
        item["agent_code"] == "classify_sentiment"
        for item in body["data"]["items"]
    )


def test_project_dashboard_latest_summary(client, session_factory, analyzed_run):
    response = client.get(
        f"/api/geo-monitoring/projects/{analyzed_run['project_id']}/dashboard"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["project_id"] == analyzed_run["project_id"]
    latest_run = data["latest_run"]
    assert latest_run["run_id"] == analyzed_run["run_id"]
    assert latest_run["platform_codes"] == ["qwen"]
    assert len(data["platforms"]) == 1

    platform = data["platforms"][0]
    assert platform["platform_code"] == "qwen"
    assert platform["platform_name"] == "qwen"
    assert platform["collection"]["succeeded_tasks"] == 1
    assert platform["analysis"]["valid_answer_count"] == 1

    summary = data["summary"]
    assert summary["scope"] == "all"
    assert summary["valid_answer_count"] == 1
    assert summary["brand_mention_rate"] is not None
    assert summary["brand_top1_mention_rate"] == "1.000000"
    assert summary["brand_top3_mention_rate"] == "1.000000"
    assert any(item["metric_code"] == "brand_visibility" for item in summary["metrics"])
    assert any(
        item["metric_code"] == "brand_top1_mention_rate"
        for item in summary["metrics"]
    )
    assert any(
        item["metric_code"] == "brand_top3_mention_rate"
        for item in summary["metrics"]
    )
    assert any(
        item["metric_code"] == "brand_visibility" and item["platform_code"] == "qwen"
        for item in platform["metrics"]
    )
    assert any(
        item["metric_code"] == "brand_top3_mention_rate"
        and item["platform_code"] == "qwen"
        for item in platform["metrics"]
    )


def test_analyze_persists_extended_metric_snapshots(client, session_factory, analyzed_run):
    from app.geo_monitoring.services.analysis import MetricSnapshot

    run_id = analyzed_run["run_id"]
    with session_factory() as db:
        snapshots = list(
            db.execute(
                select(MetricSnapshot).where(
                    MetricSnapshot.run_id == run_id,
                    MetricSnapshot.is_deleted.is_(False),
                )
            )
            .scalars()
            .all()
        )
    codes = {row.metric_code for row in snapshots}
    assert "average_mention_rank" in codes
    assert "share_of_voice" in codes
    assert "brand_top10_mention_rate" in codes
    assert "brand_mention_total_count" in codes
    assert "positive_rate" in codes
    assert "neutral_rate" in codes
    assert "negative_rate" in codes
    brand_snapshots = [row for row in snapshots if row.brand_id is not None]
    assert brand_snapshots
    assert any(
        row.metric_code == "share_of_voice" and row.brand_id is not None
        for row in brand_snapshots
    )


def test_project_dashboard_platform_metrics_exclude_brand_snapshots(
    client, session_factory, analyzed_run
):
    from app.geo_monitoring.services.analysis import MetricSnapshot

    run_id = analyzed_run["run_id"]
    project_id = analyzed_run["project_id"]
    with session_factory() as db:
        brand_snapshots = list(
            db.execute(
                select(MetricSnapshot).where(
                    MetricSnapshot.run_id == run_id,
                    MetricSnapshot.brand_id.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        assert brand_snapshots

    response = client.get(f"/api/geo-monitoring/projects/{project_id}/dashboard")
    body = response.json()
    assert body["code"] == 0
    platform = body["data"]["platforms"][0]
    assert all(item.get("brand_id") is None for item in platform["metrics"])
    metric_codes = {item["metric_code"] for item in platform["metrics"]}
    assert "average_mention_rank" in metric_codes
    assert "brand_mention_rate" not in metric_codes


def test_dashboard_overview_time_filter_share_of_voice_counts_competitors(
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
                Brand.project_id == project_id,
                Brand.brand_type == "competitor",
            )
        ).scalar_one()

    client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    collected_at = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    with session_factory() as db:
        from app.geo_monitoring.models import Answer, AnswerBrandResult

        answer = db.execute(select(Answer)).scalar_one()
        answer.collected_at = collected_at
        target_result = db.execute(
            select(AnswerBrandResult).where(
                AnswerBrandResult.answer_id == answer.id,
                AnswerBrandResult.brand_id == target_id,
            )
        ).scalar_one()
        target_result.is_mentioned = True
        competitor_result = db.execute(
            select(AnswerBrandResult).where(
                AnswerBrandResult.answer_id == answer.id,
                AnswerBrandResult.brand_id == competitor_id,
            )
        ).scalar_one()
        competitor_result.is_mentioned = True
        db.commit()

    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard/overview",
        params={
            "start_at": collected_at.isoformat(),
            "end_at": collected_at.isoformat(),
        },
    )
    assert response.json()["data"]["kpis"]["share_of_voice"] == "0.5000"


@pytest.fixture
def multi_platform_analyzed_run(client, session_factory, monkeypatch):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen", "deepseek"))
    response = client.post(f"/api/geo-monitoring/runs/{seeded['run_id']}/analyze")
    assert response.json()["code"] == 0
    return seeded


def test_project_dashboard_multi_platform_summary_and_breakdown(
    client, multi_platform_analyzed_run
):
    project_id = multi_platform_analyzed_run["project_id"]
    response = client.get(f"/api/geo-monitoring/projects/{project_id}/dashboard")
    body = response.json()
    assert body["code"] == 0
    data = body["data"]

    assert set(data["latest_run"]["platform_codes"]) == {"qwen", "deepseek"}
    assert len(data["platforms"]) == 2
    codes = {item["platform_code"] for item in data["platforms"]}
    assert codes == {"qwen", "deepseek"}

    summary = data["summary"]
    assert summary["valid_answer_count"] == 2
    assert summary["brand_mention_count"] == 2
    assert summary["brand_mention_rate"] == "1.000000"
    assert summary["brand_top1_mention_count"] == 2
    assert summary["brand_top1_mention_rate"] == "1.000000"
    assert summary["brand_top3_mention_count"] == 2
    assert summary["brand_top3_mention_rate"] == "1.000000"

    for platform in data["platforms"]:
        assert platform["collection"]["succeeded_tasks"] == 1
        assert platform["analysis"]["valid_answer_count"] == 1
        assert platform["analysis"]["brand_mention_rate"] == "1.0000"
        assert platform["analysis"]["brand_top1_mention_rate"] == "1.0000"
        assert platform["analysis"]["brand_top3_mention_rate"] == "1.0000"


def test_project_dashboard_filter_by_run_id(client, multi_platform_analyzed_run):
    project_id = multi_platform_analyzed_run["project_id"]
    run_id = multi_platform_analyzed_run["run_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard",
        params={"run_id": run_id},
    )
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["latest_run"]["run_id"] == run_id


def test_project_dashboard_collection_only_run(client, session_factory):
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",), with_valid_answers=True)
    response = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/dashboard"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["latest_run"]["platform_codes"] == ["qwen"]
    assert data["summary"] is None
    platform = data["platforms"][0]
    assert platform["collection"]["succeeded_tasks"] == 1
    assert platform["analysis"] is None
    assert platform["metrics"] == []


def test_project_trends_filter_by_metric_and_platform(client, analyzed_run):
    response = client.get(
        f"/api/geo-monitoring/projects/{analyzed_run['project_id']}/trends",
        params={
            "metric_code": "brand_visibility",
            "platform_code": "qwen",
        },
    )
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["total"] >= 1
    assert body["data"]["items"][0]["metric_code"] == "brand_visibility"
    assert body["data"]["items"][0]["platform_code"] == "qwen"


def test_analyze_rejects_missing_run(client):
    response = client.post("/api/geo-monitoring/runs/999999/analyze")
    assert response.json()["code"] == 40400


def test_dashboard_overview_empty_when_no_runs(client, session_factory):
    from app.geo_monitoring.models import MonitorProject

    with session_factory() as db:
        project = MonitorProject(
            project_name="空大盘项目",
            status="active",
            official_domain="example.com",
        )
        db.add(project)
        db.commit()
        project_id = project.id

    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard/overview"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["project_id"] == project_id
    assert data["run_id"] is None
    assert data["platforms"] == []
    assert data["kpis"]["brand_mention_rate"] is None
    assert data["kpis"]["valid_answer_count"] is None
    assert data["competitor_preview"]["boards"]["mention_rate"] == []
    assert data["source_preview"]["items"] == []
    assert data["recent_questions"]["items"] == []


def test_dashboard_overview_returns_kpis_and_previews(client, analyzed_run):
    project_id = analyzed_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard/overview"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["run_id"] == analyzed_run["run_id"]
    assert data["kpis"]["brand_mention_rate"] is not None
    assert data["kpis"]["brand_top1_mention_rate"] == "1.000000"
    assert data["kpis"]["brand_top3_mention_rate"] == "1.000000"
    assert data["kpis"]["valid_answer_count"] == 1
    assert data["kpis"]["brand_mention_count"] == 1
    assert len(data["platforms"]) == 1
    assert data["platforms"][0]["platform_code"] == "qwen"
    assert data["platforms"][0]["analysis"]["valid_answer_count"] == 1
    assert len(data["competitor_preview"]["boards"]["mention_rate"]) >= 1
    assert len(data["recent_questions"]["items"]) >= 1


def test_dashboard_overview_platform_codes_filter(
    client, multi_platform_analyzed_run
):
    project_id = multi_platform_analyzed_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard/overview",
        params={"platform_codes": ["qwen"]},
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert len(data["platforms"]) == 1
    assert data["platforms"][0]["platform_code"] == "qwen"
    assert data["kpis"]["valid_answer_count"] == 1
    for item in data["recent_questions"]["items"]:
        platform_codes = {row["platform_code"] for row in item["platform_metrics"]}
        assert platform_codes <= {"qwen"}


def test_dashboard_overview_collection_only_run_no_error(client, session_factory):
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",), with_valid_answers=True)
    response = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/dashboard/overview"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["run_id"] == seeded["run_id"]
    assert data["kpis"]["brand_mention_rate"] is None
    assert data["kpis"]["valid_answer_count"] is None
    assert data["platforms"][0]["analysis"] is None
    assert data["competitor_preview"]["boards"]["mention_rate"] == []


def test_dashboard_overview_extended_kpis_match_competitor_analysis_multi_platform(
    client, session_factory, monkeypatch
):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen", "deepseek"))
        target_id = db.execute(
            select(Brand.id).where(
                Brand.project_id == seeded["project_id"],
                Brand.brand_type == "target",
            )
        ).scalar_one()
        competitor_id = db.execute(
            select(Brand.id).where(
                Brand.project_id == seeded["project_id"],
                Brand.brand_type == "competitor",
            )
        ).scalar_one()
        run_id = seeded["run_id"]
        project_id = seeded["project_id"]

    client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    with session_factory() as db:
        qwen_row = db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == run_id,
                PlatformAnalysis.platform_code == "qwen",
            )
        ).scalar_one()
        deepseek_row = db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == run_id,
                PlatformAnalysis.platform_code == "deepseek",
            )
        ).scalar_one()

        qwen_summary = copy.deepcopy(qwen_row.summary_json or {})
        qwen_metrics = dict((qwen_summary.get("metrics") or {}))
        qwen_metrics["brand_metrics"] = [
            {
                "brand_id": target_id,
                "brand_name": "目标品牌",
                "mention_count": 1,
                "mention_conversation_count": 1,
                "mention_rate": {"numerator": 1, "denominator": 11, "rate": "0.0909"},
                "average_mention_rank": "1.0",
                "share_of_voice": "0.0909",
            },
            {
                "brand_id": competitor_id,
                "brand_name": "竞品B",
                "mention_count": 10,
                "mention_conversation_count": 10,
                "mention_rate": {"numerator": 10, "denominator": 11, "rate": "0.9091"},
                "average_mention_rank": "2.0",
                "share_of_voice": "0.9091",
            },
        ]
        qwen_summary["metrics"] = qwen_metrics
        qwen_row.summary_json = qwen_summary

        deepseek_summary = copy.deepcopy(deepseek_row.summary_json or {})
        deepseek_metrics = dict((deepseek_summary.get("metrics") or {}))
        deepseek_metrics["brand_metrics"] = [
            {
                "brand_id": target_id,
                "brand_name": "目标品牌",
                "mention_count": 9,
                "mention_conversation_count": 9,
                "mention_rate": {"numerator": 9, "denominator": 9, "rate": "1.0000"},
                "average_mention_rank": "1.0",
                "share_of_voice": "1.0000",
            },
        ]
        deepseek_summary["metrics"] = deepseek_metrics
        deepseek_row.summary_json = deepseek_summary
        db.commit()

    competitor_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis"
    )
    competitor_body = competitor_response.json()
    assert competitor_body["code"] == 0
    competitor_kpis = competitor_body["data"]["kpis"]
    assert competitor_kpis["share_of_voice"] == "0.5000"

    overview_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard/overview"
    )
    overview_body = overview_response.json()
    assert overview_body["code"] == 0
    overview_kpis = overview_body["data"]["kpis"]
    assert overview_kpis["share_of_voice"] == competitor_kpis["share_of_voice"]
    assert overview_kpis["average_rank"] == competitor_kpis["average_rank"]
    assert overview_kpis["brand_mention_total_count"] == competitor_kpis["mention_count"]


def test_dashboard_overview_kpis_follow_time_filter(client, session_factory, monkeypatch):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen", "deepseek"))
        run_id = seeded["run_id"]
        project_id = seeded["project_id"]

    client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    early = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    late = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)

    with session_factory() as db:
        from app.geo_monitoring.models import Answer

        answers = list(db.execute(select(Answer)).scalars().all())
        for answer in answers:
            answer.collected_at = early if answer.platform_code == "qwen" else late
        db.commit()

    full_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard/overview"
    )
    assert full_response.json()["data"]["kpis"]["valid_answer_count"] == 2

    filtered_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard/overview",
        params={
            "start_at": early.isoformat(),
            "end_at": early.isoformat(),
        },
    )
    filtered_data = filtered_response.json()["data"]
    assert filtered_data["kpis"]["valid_answer_count"] == 1
    assert filtered_data["recent_questions"]["items"]
    assert all(
        row["valid_answer_count"] <= 1
        for row in filtered_data["recent_questions"]["items"]
    )


def test_dashboard_overview_time_filter_top_rank_uses_relative_rank(
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

    client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    collected_at = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    with session_factory() as db:
        from app.geo_monitoring.models import Answer, AnswerBrandResult

        answer = db.execute(select(Answer)).scalar_one()
        answer.collected_at = collected_at
        target_result = db.execute(
            select(AnswerBrandResult).where(
                AnswerBrandResult.answer_id == answer.id,
                AnswerBrandResult.brand_id == target_id,
            )
        ).scalar_one()
        target_result.first_position = 20
        target_result.is_mentioned = True
        competitor_result = db.execute(
            select(AnswerBrandResult).where(
                AnswerBrandResult.answer_id == answer.id,
                AnswerBrandResult.brand_id != target_id,
            )
        ).scalar_one()
        competitor_result.is_mentioned = False
        competitor_result.first_position = None
        db.commit()

    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard/overview",
        params={
            "start_at": collected_at.isoformat(),
            "end_at": collected_at.isoformat(),
        },
    )
    kpis = response.json()["data"]["kpis"]
    assert kpis["brand_top1_mention_rate"] == "1.000000"
    assert kpis["brand_top3_mention_rate"] == "1.000000"
    assert kpis["brand_mention_rate"] == "1.000000"


def test_dashboard_overview_time_filter_brand_mention_count_is_conversation_count(
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

    client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    collected_at = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    with session_factory() as db:
        from app.geo_monitoring.models import Answer, AnswerBrandResult

        answer = db.execute(select(Answer)).scalar_one()
        answer.collected_at = collected_at
        target_result = db.execute(
            select(AnswerBrandResult).where(
                AnswerBrandResult.answer_id == answer.id,
                AnswerBrandResult.brand_id == target_id,
            )
        ).scalar_one()
        target_result.mention_count = 5
        db.commit()

    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard/overview",
        params={
            "start_at": collected_at.isoformat(),
            "end_at": collected_at.isoformat(),
        },
    )
    kpis = response.json()["data"]["kpis"]
    assert kpis["brand_mention_count"] == 1
    assert kpis["brand_mention_total_count"] == 5
