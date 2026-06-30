"""Security regression tests for API, reports and logging."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.logging import StructuredJsonFormatter, redact_sensitive_text
from app.core.exceptions import register_exception_handlers
from app.main import create_app


TEST_SECRET = "sk-e2e-test-secret-do-not-leak"


@pytest.fixture
def production_client(session_factory, monkeypatch):
    monkeypatch.setenv("APP_DEBUG", "false")
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
        "app.geo_monitoring.services.analysis.create_agent_llm_client",
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


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"
MANUAL_SCRIPTS = REPO_ROOT / "backend" / "scripts" / "manual"

_FORBIDDEN_APP_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^\s*JWT\s*=\s*\(", re.MULTILINE), "hardcoded JWT assignment"),
    (re.compile(r"kimi-auth=eyJ"), "hardcoded kimi-auth cookie"),
    (re.compile(r"Bearer eyJ[A-Za-z0-9_-]{20,}"), "hardcoded Bearer JWT token"),
    (re.compile(r"ChatService/Chat"), "Kimi web private protocol manual script"),
)

_FORBIDDEN_MANUAL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^\s*JWT\s*=\s*\(", re.MULTILINE), "hardcoded JWT assignment"),
    (re.compile(r"kimi-auth=eyJ"), "hardcoded kimi-auth cookie"),
    (re.compile(r"Bearer eyJ[A-Za-z0-9_-]{20,}"), "hardcoded Bearer JWT token"),
)


def _collect_pattern_violations(
    root: Path,
    patterns: tuple[tuple[re.Pattern[str], str], ...],
) -> list[str]:
    if not root.exists():
        return []

    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO_ROOT)
        for pattern, label in patterns:
            if pattern.search(text):
                violations.append(f"{rel}: {label}")
    return violations


def test_backend_app_has_no_hardcoded_credentials_or_manual_scripts():
    violations = _collect_pattern_violations(BACKEND_APP, _FORBIDDEN_APP_PATTERNS)
    assert not violations, ";\n".join(violations)


def test_manual_scripts_have_no_hardcoded_web_credentials():
    violations = _collect_pattern_violations(MANUAL_SCRIPTS, _FORBIDDEN_MANUAL_PATTERNS)
    assert not violations, ";\n".join(violations)


def test_backend_app_test_package_is_not_shipped_under_app():
    assert not (BACKEND_APP / "test").exists(), (
        "backend/app/test must be migrated to backend/scripts/manual"
    )


_AUTH_TOKEN_MAP = (
    '[{"token":"tenant-a-token","tenant_id":100,"actor_id":1001},'
    '{"token":"tenant-b-token","tenant_id":200,"actor_id":2001}]'
)


@pytest.fixture
def auth_enabled_client(session_factory, monkeypatch):
    monkeypatch.setenv("APP_DEBUG", "false")
    monkeypatch.setenv("API_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN_MAP_JSON", _AUTH_TOKEN_MAP)
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.core.database import get_db
    from app.geo_monitoring.services import collection as collection_service
    from app.main import create_app

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


def test_api_auth_disabled_allows_anonymous_project_access(client, project_id):
    response = client.get(f"/api/geo-monitoring/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_api_auth_enabled_rejects_missing_bearer(auth_enabled_client):
    response = auth_enabled_client.get("/api/geo-monitoring/projects")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == 401
    assert "Authorization" in body["message"]


def test_api_auth_enabled_accepts_valid_bearer(auth_enabled_client):
    response = auth_enabled_client.get(
        "/api/geo-monitoring/projects",
        headers={"Authorization": "Bearer tenant-a-token"},
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_api_auth_tenant_isolation_hides_other_tenant_project(auth_enabled_client):
    create_a = auth_enabled_client.post(
        "/api/geo-monitoring/projects",
        headers={"Authorization": "Bearer tenant-a-token"},
        json={"project_name": "租户A项目", "industry": "文旅"},
    )
    assert create_a.json()["code"] == 0
    project_id = create_a.json()["data"]["id"]

    forbidden = auth_enabled_client.get(
        f"/api/geo-monitoring/projects/{project_id}",
        headers={"Authorization": "Bearer tenant-b-token"},
    )
    assert forbidden.status_code == 200
    assert forbidden.json()["code"] == 40400

    allowed = auth_enabled_client.get(
        f"/api/geo-monitoring/projects/{project_id}",
        headers={"Authorization": "Bearer tenant-a-token"},
    )
    assert allowed.json()["code"] == 0


def test_api_auth_setup_project_stamps_tenant_and_is_readable(auth_enabled_client):
    response = auth_enabled_client.post(
        "/api/geo-monitoring/projects:setup",
        headers={"Authorization": "Bearer tenant-a-token"},
        json={
            "project": {"project_name": "Setup租户A", "industry": "文旅"},
            "monitor_setup": {
                "brand": {"brand_name": "SetupBrand", "brand_words": ["Setup"]},
            },
            "run_after_create": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    project_id = body["data"]["project"]["id"]

    monitor_setup = auth_enabled_client.get(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup",
        headers={"Authorization": "Bearer tenant-a-token"},
    )
    assert monitor_setup.json()["code"] == 0

    forbidden = auth_enabled_client.get(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup",
        headers={"Authorization": "Bearer tenant-b-token"},
    )
    assert forbidden.json()["code"] == 40400


def test_api_auth_tenant_isolation_hides_sub_resources_by_id(auth_enabled_client):
    create_a = auth_enabled_client.post(
        "/api/geo-monitoring/projects",
        headers={"Authorization": "Bearer tenant-a-token"},
        json={"project_name": "子资源租户A", "industry": "文旅"},
    )
    project_id = create_a.json()["data"]["id"]
    prompt_set = auth_enabled_client.post(
        f"/api/geo-monitoring/projects/{project_id}/prompt-sets",
        headers={"Authorization": "Bearer tenant-a-token"},
        json={"set_name": "租户A集", "version_no": "v-a-1"},
    )
    prompt_set_id = prompt_set.json()["data"]["id"]
    schedule = auth_enabled_client.post(
        f"/api/geo-monitoring/projects/{project_id}/schedules",
        headers={"Authorization": "Bearer tenant-a-token"},
        json={
            "name": "租户A调度",
            "cron_expr": "0 9 * * *",
            "timezone": "Asia/Shanghai",
            "enabled": True,
            "misfire_policy": "fire_once",
        },
    )
    schedule_id = schedule.json()["data"]["id"]
    keyword = auth_enabled_client.post(
        f"/api/geo-monitoring/projects/{project_id}/core-keywords",
        headers={"Authorization": "Bearer tenant-a-token"},
        json={"keyword": "租户A词", "enabled": True},
    )
    keyword_id = keyword.json()["data"]["id"]

    for method, url, json_body in [
        ("GET", f"/api/geo-monitoring/prompt-sets/{prompt_set_id}", None),
        ("GET", f"/api/geo-monitoring/schedules/{schedule_id}", None),
        (
            "PUT",
            f"/api/geo-monitoring/core-keywords/{keyword_id}",
            {"keyword": "租户A词改", "enabled": True},
        ),
    ]:
        response = auth_enabled_client.request(
            method,
            url,
            headers={"Authorization": "Bearer tenant-b-token"},
            json=json_body,
        )
        assert response.json()["code"] == 40400, url


def test_provider_callback_does_not_require_bearer_auth(
    auth_enabled_client,
    monkeypatch,
):
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "MOLIZHISHU_CALLBACK_TOKEN", "callback-secret")

    response = auth_enabled_client.post(
        "/api/geo-monitoring/provider-callbacks/molizhishu",
        json={"taskId": "missing-task"},
        headers={"X-Callback-Token": "callback-secret"},
    )
    assert response.status_code == 200
    assert response.json()["code"] != 401


def test_prod_requires_api_auth_enabled(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DRAMATIQ_BROKER", "redis")
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "prod-key")
    monkeypatch.setenv("AGENT_LLM_MODEL", "prod-model")
    monkeypatch.setenv("API_AUTH_ENABLED", "false")
    monkeypatch.setenv("API_AUTH_TOKEN_MAP_JSON", "[]")
    from app.core.config import Settings

    with pytest.raises(ValueError, match="API_AUTH_ENABLED"):
        Settings(
            DATABASE_URL="postgresql+psycopg2://u:p@localhost:5432/geo",
            REDIS_URL="redis://localhost:6379/0",
        )
