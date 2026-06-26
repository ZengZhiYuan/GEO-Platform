"""Task P2-3：行业基准接口测试。"""

import pytest

from app.geo_monitoring.schemas import BenchmarkDetailOut, BenchmarkListOut


def test_benchmarks_lists_available_industries(client):
    payload = client.get("/api/geo-monitoring/benchmarks").json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    BenchmarkListOut.model_validate(data)
    assert data["sample_source"] == "static_config"
    industries = {item["industry"] for item in data["industries"]}
    assert "文旅演艺" in industries
    travel = next(item for item in data["industries"] if item["industry"] == "文旅演艺")
    assert travel["metrics"]["mention_rate"] == "0.4500"
    assert travel["metrics"]["top1_rate"] == "0.1800"
    assert travel["market_position_thresholds"]


def test_benchmarks_returns_industry_metrics(client):
    payload = client.get(
        "/api/geo-monitoring/benchmarks",
        params={"industry": "文旅演艺"},
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    BenchmarkDetailOut.model_validate(data)
    assert data["industry"] == "文旅演艺"
    assert data["sample_source"] == "static_config"
    metrics = data["metrics"]
    assert metrics["mention_rate"] == "0.4500"
    assert metrics["average_rank"] == "3.2"
    assert metrics["mention_count"] == 12
    assert metrics["top1_rate"] == "0.1800"
    assert metrics["share_of_voice"] == "0.2500"


def test_benchmarks_unknown_industry_returns_404(client):
    payload = client.get(
        "/api/geo-monitoring/benchmarks",
        params={"industry": "未知行业"},
    ).json()
    assert payload["code"] == 40400


@pytest.mark.parametrize(
    "path",
    [
        "/api/geo-monitoring/benchmarks",
        "/api/v1/geo-monitoring/benchmarks",
    ],
)
def test_benchmarks_available_on_both_prefixes(client, path):
    payload = client.get(path).json()
    assert payload["code"] == 0, payload
    assert payload["data"]["sample_source"] == "static_config"
