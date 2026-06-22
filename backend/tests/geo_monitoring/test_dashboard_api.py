"""分析查询与看板 API 测试。"""

from __future__ import annotations

import pytest

import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401
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
    assert any(item["metric_code"] == "brand_visibility" for item in summary["metrics"])
    assert any(
        item["metric_code"] == "brand_visibility" and item["platform_code"] == "qwen"
        for item in platform["metrics"]
    )


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

    for platform in data["platforms"]:
        assert platform["collection"]["succeeded_tasks"] == 1
        assert platform["analysis"]["valid_answer_count"] == 1
        assert platform["analysis"]["brand_mention_rate"] == "1.0000"


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
