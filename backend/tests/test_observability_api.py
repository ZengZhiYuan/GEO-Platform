"""Health / ready probe API tests."""

from __future__ import annotations


def test_geo_monitoring_health_returns_process_status(client):
    response = client.get("/api/geo-monitoring/health")
    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["status"] == "ok"
    assert body["data"]["env"] == "test"


def test_geo_monitoring_ready_returns_dependency_summary(client, monkeypatch):
    monkeypatch.setattr(
        "app.main.check_readiness",
        lambda: {
            "status": "ready",
            "database": {"ok": True, "target": "sqlite:///:memory:"},
            "redis": {"ok": True, "target": "redis://redis.test:6379/0"},
        },
    )
    response = client.get("/api/geo-monitoring/ready")
    body = response.json()
    assert response.status_code == 200
    assert body["data"]["status"] == "ready"
    assert body["data"]["database"]["ok"] is True
    assert "password" not in response.text


def test_geo_monitoring_ready_returns_503_when_not_ready(client, monkeypatch):
    monkeypatch.setattr(
        "app.main.check_readiness",
        lambda: {
            "status": "not_ready",
            "database": {"ok": False, "target": "postgresql://db.test/app"},
            "redis": {"ok": True, "target": "redis://redis.test:6379/0"},
        },
    )
    response = client.get("/api/geo-monitoring/ready")
    assert response.status_code == 503
    assert response.json()["data"]["status"] == "not_ready"


def test_health_response_includes_request_id_header(client):
    response = client.get(
        "/api/geo-monitoring/health",
        headers={"X-Request-ID": "trace-abc"},
    )
    assert response.headers.get("X-Request-ID") == "trace-abc"
    assert response.headers.get("X-Response-Time-Ms") is not None
