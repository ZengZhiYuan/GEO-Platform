"""Shared preflight helpers for manual production smoke scripts (Task O4)."""

from __future__ import annotations

import os
from typing import Any

from app.core.config import Settings
from app.geo_monitoring.adapters.registry import (
    _molizhishu_configured,
    build_adapter_registry,
    platform_runtime_configured,
)
from app.geo_monitoring.services.collection import build_credential_key_pool
from app.geo_monitoring.services.platforms import MOLIZHISHU_PLATFORM_MAPPINGS


def mask_secret(value: str, *, visible: int = 4) -> str:
    text = (value or "").strip()
    if not text:
        return "(empty)"
    if len(text) <= visible * 2:
        return "***"
    return f"{text[:visible]}...{text[-visible:]}"


def redact_secrets(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret and secret in redacted:
            redacted = redacted.replace(secret, "***")
    return redacted


def resolve_smoke_auth_headers(settings: Settings) -> dict[str, str]:
    """Build Authorization header for smoke/API scripts when auth is enabled."""
    if not settings.API_AUTH_ENABLED:
        return {}
    token = os.environ.get("API_SMOKE_BEARER_TOKEN", "").strip()
    if not token:
        entries = settings.parsed_api_auth_token_entries()
        if entries:
            token = entries[0].token
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def molizhishu_preflight(settings: Settings) -> dict[str, Any]:
    registry = build_adapter_registry(settings)
    key_pool = build_credential_key_pool(settings)
    sample_code = next(iter(MOLIZHISHU_PLATFORM_MAPPINGS))
    return {
        "enabled": settings.MOLIZHISHU_ENABLED,
        "configured": _molizhishu_configured(settings),
        "has_token": bool(settings.MOLIZHISHU_API_TOKEN.strip()),
        "base_url": settings.MOLIZHISHU_BASE_URL,
        "provider_batch_enabled": settings.MOLIZHISHU_PROVIDER_BATCH_ENABLED,
        "adapter_registered": sample_code in registry.registered_codes(),
        "runtime_configured": platform_runtime_configured(sample_code, settings),
        "credential_count": key_pool.credential_count(sample_code),
        "sample_platform_code": sample_code,
    }


def agent_llm_preflight(settings: Settings) -> dict[str, Any]:
    return {
        "base_url": settings.AGENT_LLM_BASE_URL or None,
        "model": settings.AGENT_LLM_MODEL or None,
        "has_api_key": bool(settings.AGENT_LLM_API_KEY.strip()),
        "provider": settings.AGENT_LLM_PROVIDER,
    }


def infrastructure_preflight(settings: Settings) -> dict[str, Any]:
    return {
        "app_env": settings.APP_ENV,
        "dramatiq_broker": settings.DRAMATIQ_BROKER,
        "database_target": settings.connection_targets_summary()["database"],
        "redis_target": settings.connection_targets_summary()["redis"],
    }


def build_preflight_report(settings: Settings) -> dict[str, Any]:
    molizhishu = molizhishu_preflight(settings)
    agent = agent_llm_preflight(settings)
    infra = infrastructure_preflight(settings)
    blockers: list[str] = []
    if not molizhishu["configured"]:
        blockers.append(
            "模力指数未就绪：需 MOLIZHISHU_ENABLED=true、MOLIZHISHU_API_TOKEN 与 BASE_URL"
        )
    if not agent["has_api_key"] or not agent["model"] or not agent["base_url"]:
        blockers.append("Agent LLM 未完整配置：需 AGENT_LLM_BASE_URL/API_KEY/MODEL")
    if settings.APP_ENV == "prod" and settings.DRAMATIQ_BROKER.strip().lower() != "redis":
        blockers.append("生产环境 DRAMATIQ_BROKER 必须为 redis")
    return {
        "infrastructure": infra,
        "molizhishu": molizhishu,
        "agent_llm": agent,
        "ready_for_paid_molizhishu": not blockers,
        "blockers": blockers,
    }


def print_preflight_report(settings: Settings) -> dict[str, Any]:
    report = build_preflight_report(settings)
    molizhishu = report["molizhishu"]
    agent = report["agent_llm"]
    infra = report["infrastructure"]

    print("=== Production Smoke Preflight (dry-run) ===")
    print("本步骤仅检查配置，不调用模力指数或 Agent 付费接口。")
    print(f"APP_ENV: {infra['app_env']}")
    print(f"DRAMATIQ_BROKER: {infra['dramatiq_broker']}")
    print(f"Database: {infra['database_target']}")
    print(f"Redis: {infra['redis_target']}")
    print("")
    print("[Molizhishu]")
    print(f"  enabled: {molizhishu['enabled']}")
    print(f"  configured: {molizhishu['configured']}")
    print(f"  token: {mask_secret(settings.MOLIZHISHU_API_TOKEN)}")
    print(f"  base_url: {molizhishu['base_url']}")
    print(f"  provider_batch_enabled: {molizhishu['provider_batch_enabled']}")
    print(f"  adapter_registered ({molizhishu['sample_platform_code']}): {molizhishu['adapter_registered']}")
    print(f"  credential_count: {molizhishu['credential_count']}")
    print("")
    print("[Agent LLM]")
    print(f"  base_url: {agent['base_url']}")
    print(f"  model: {agent['model']}")
    print(f"  api_key: {mask_secret(settings.AGENT_LLM_API_KEY)}")
    print(f"  provider: {agent['provider']}")
    if report["blockers"]:
        print("")
        print("Blockers:")
        for item in report["blockers"]:
            print(f"  - {item}")
    else:
        print("")
        print("Preflight OK：可继续 adapter-smoke 或 business-loop（需 --allow-paid-provider）。")
    return report


def ensure_allow_paid_provider(*, allow_paid_provider: bool, action: str) -> None:
    if allow_paid_provider:
        return
    raise SystemExit(
        f"{action} 可能产生模力指数/Agent 费用；请显式添加 --allow-paid-provider 后再执行。"
    )


def preflight_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("ready_for_paid_molizhishu") else 1
