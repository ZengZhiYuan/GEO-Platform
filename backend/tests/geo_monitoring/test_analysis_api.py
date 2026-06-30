"""分析触发 API 测试。"""

from __future__ import annotations

import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401
from app.geo_monitoring.models import MonitorRun
from tests.geo_monitoring.analysis_support import patch_fake_llm_for_analyze
from tests.geo_monitoring.agents.test_graph import FakeLLMClient, _seed_run


def _patch_llm(monkeypatch) -> FakeLLMClient:
    return patch_fake_llm_for_analyze(monkeypatch)


def test_trigger_analysis_rejects_when_already_running(
    client, session_factory, monkeypatch
):
    _patch_llm(monkeypatch)
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))
        run = db.get(MonitorRun, seeded["run_id"])
        run.analysis_status = "running"
        db.commit()
        run_id = seeded["run_id"]

    response = client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == 40911
    assert "分析" in body["message"]


def test_trigger_analysis_allows_rerun_after_completed(
    client, session_factory, monkeypatch
):
    _patch_llm(monkeypatch)
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))
        run_id = seeded["run_id"]

    first = client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")
    assert first.status_code == 200
    first_data = first.json()["data"]
    assert first.json()["code"] == 0
    assert first_data["queued"] is True
    assert first_data["analysis_status"] == "pending"
    assert first_data["run_analysis_status"] == "completed"

    second = client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")
    assert second.status_code == 200
    second_data = second.json()["data"]
    assert second.json()["code"] == 0
    assert second_data["queued"] is True
    assert second_data["run_analysis_status"] == "completed"


def test_trigger_analysis_rejects_when_collection_not_terminal(
    client, session_factory, monkeypatch
):
    _patch_llm(monkeypatch)
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))
        run = db.get(MonitorRun, seeded["run_id"])
        run.status = "collecting"
        run.collection_status = "running"
        db.commit()
        run_id = seeded["run_id"]

    response = client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")

    assert response.status_code == 409
    assert response.json()["code"] == 40910
