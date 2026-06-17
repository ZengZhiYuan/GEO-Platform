"""Security regression tests for API, reports and logging."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.logging import StructuredJsonFormatter, redact_sensitive_text
from app.core.exceptions import register_exception_handlers
from app.main import create_app


TEST_SECRET = "sk-e2e-test-secret-do-not-leak"


@pytest.fixture
def production_client(session_factory, monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://monitor.example.test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.core.database import get_db
    from app.geo_monitoring.services import collection as collection_service

    app = create_app()
    collection_service.configure_runtime(
        collection_service.build_default_runtime(session_factory=session_factory)
    )

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        collection_service.reset_runtime()
        get_settings.cache_clear()


def test_invalid_pagination_rejected(client, project_id):
    response = client.get(
        "/api/geo-monitoring/runs",
        params={"page": 0, "project_id": project_id},
    ).json()
    assert response["code"] == 422


def test_page_size_upper_bound_enforced(client, project_id):
    response = client.get(
        "/api/geo-monitoring/runs",
        params={"page": 1, "page_size": 1000, "project_id": project_id},
    ).json()
    assert response["code"] == 422


def test_report_download_rejects_unknown_report_id(client):
    response = client.get("/api/geo-monitoring/reports/999999/download")
    if response.status_code == 200:
        assert response.json()["code"] != 0
    else:
        assert response.status_code in {404, 422}


def test_report_create_rejects_invalid_format(client, session_factory, monkeypatch):
    from tests.geo_monitoring.agents.test_graph import FakeLLMClient, _seed_run
    import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401

    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))
    with session_factory() as db:
        from app.geo_monitoring.services.analysis import run_analysis

        run_analysis(db, seeded["run_id"], llm_client=llm)

    response = client.post(
        f"/api/geo-monitoring/runs/{seeded['run_id']}/reports",
        json={"formats": ["exe"]},
    )
    body = response.json()
    assert body["code"] != 0


def test_cors_allows_configured_origin_only(production_client):
    allowed = production_client.options(
        "/api/geo-monitoring/health",
        headers={
            "Origin": "https://monitor.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "https://monitor.example.test"

    blocked = production_client.options(
        "/api/geo-monitoring/health",
        headers={
            "Origin": "https://evil.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert blocked.headers.get("access-control-allow-origin") != "https://evil.example.test"


def test_unhandled_exception_handler_hides_internal_details():
    from fastapi import FastAPI

    app = FastAPI(debug=False)
    register_exception_handlers(app)

    @app.get("/api/_security_probe_fail")
    async def _probe_fail() -> None:
        raise RuntimeError("sensitive internal detail")

    with TestClient(app, raise_server_exceptions=False) as probe_client:
        response = probe_client.get("/api/_security_probe_fail")

    body = response.json()
    assert response.status_code == 500
    assert body["code"] == 500
    assert body["message"] == "服务器内部错误"
    assert "sensitive internal detail" not in response.text
    assert "Traceback" not in response.text


def test_api_responses_do_not_leak_test_secrets(client, project_id, monkeypatch):
    monkeypatch.setenv("QWEN_API_KEYS", TEST_SECRET)
    from app.core.config import get_settings

    get_settings.cache_clear()
    response = client.get(f"/api/geo-monitoring/projects/{project_id}")
    assert TEST_SECRET not in response.text


def test_log_formatter_redacts_secrets_from_fixture_messages():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="failed with %s",
        args=(TEST_SECRET,),
        exc_info=None,
    )
    payload = json.loads(StructuredJsonFormatter().format(record))
    assert TEST_SECRET not in payload["message"]


def test_redact_sensitive_text_covers_bearer_tokens():
    sanitized = redact_sensitive_text(f"auth failed Bearer {TEST_SECRET}")
    assert TEST_SECRET not in sanitized
