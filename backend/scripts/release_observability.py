"""Release acceptance observability helpers (Task O10).

供 ``run_api_full_test.py`` 与手动上线验收复用：配置 preflight、/ready、
Dramatiq 三队列深度、模力指数 ProviderBatch 指标与 Agent LLM 调用统计。
"""

from __future__ import annotations

import statistics
from typing import Any

import httpx

from app.core.config import Settings
from app.geo_monitoring.adapters.registry import build_adapter_registry
from app.geo_monitoring.models import ProviderBatch
from app.geo_monitoring.services.analysis import AgentExecution
from app.geo_monitoring.services.collection import build_credential_key_pool
from app.geo_monitoring.services.platforms import MOLIZHISHU_PLATFORM_MAPPINGS
from smoke_preflight import build_preflight_report

DRAMATIQ_NAMESPACE = "dramatiq"
DRAMATIQ_QUEUE_NAMES = ("collection", "analysis", "report")


def _redis_client_from_url(redis_url: str):
    from redis import Redis

    return Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)


def build_local_preflight_summary(settings: Settings) -> dict[str, Any]:
    """本地配置摘要 + adapter registry + credential count（不访问外部 HTTP）。"""
    registry = build_adapter_registry(settings)
    registered_codes = sorted(registry.registered_codes())
    sample_code = next(iter(MOLIZHISHU_PLATFORM_MAPPINGS), None)
    credential_samples: dict[str, int] = {}
    credential_error: str | None = None
    try:
        key_pool = build_credential_key_pool(settings)
        for code in registered_codes[:8]:
            credential_samples[code] = key_pool.credential_count(code)
        if sample_code and sample_code not in credential_samples:
            credential_samples[sample_code] = key_pool.credential_count(sample_code)
    except ValueError as exc:
        credential_error = str(exc)

    try:
        preflight = build_preflight_report(settings)
    except ValueError as exc:
        preflight = {
            "infrastructure": {
                "app_env": settings.APP_ENV,
                "dramatiq_broker": settings.DRAMATIQ_BROKER,
                "database_target": settings.connection_targets_summary()["database"],
                "redis_target": settings.connection_targets_summary()["redis"],
            },
            "molizhishu": {"enabled": settings.MOLIZHISHU_ENABLED},
            "agent_llm": {"has_api_key": bool(settings.AGENT_LLM_API_KEY.strip())},
            "ready_for_paid_molizhishu": False,
            "blockers": [str(exc)],
        }

    try:
        runtime_summary = settings.runtime_summary()
    except ValueError as exc:
        runtime_summary = {
            "app_env": settings.APP_ENV,
            "error": str(exc),
            "dramatiq_broker": settings.DRAMATIQ_BROKER,
        }

    return {
        "preflight": preflight,
        "runtime_summary": runtime_summary,
        "adapter_registry": {
            "registered_count": len(registered_codes),
            "registered_codes": registered_codes,
            "credential_count_by_platform": credential_samples,
            "credential_error": credential_error,
        },
    }


def fetch_api_ready(base_url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """调用 ``/api/geo-monitoring/ready``，返回 HTTP 状态与 data 载荷。"""
    url = f"{base_url.rstrip('/')}/api/geo-monitoring/ready"
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
    body: dict[str, Any] = {}
    if response.headers.get("content-type", "").startswith("application/json"):
        payload = response.json()
        if isinstance(payload, dict):
            body = payload.get("data") or payload
    return {
        "http_status": response.status_code,
        "ready": response.status_code == 200 and body.get("status") == "ready",
        "database_ok": (body.get("database") or {}).get("ok"),
        "redis_ok": (body.get("redis") or {}).get("ok"),
        "platform_runtime": body.get("platform_runtime"),
        "payload": body,
    }


def inspect_worker_queues(redis_url: str, *, dramatiq_broker: str) -> dict[str, Any]:
    """检查 Dramatiq collection / analysis / report 队列深度（Redis LLEN）。"""
    if dramatiq_broker.strip().lower() == "stub":
        return {
            "skipped": True,
            "reason": "DRAMATIQ_BROKER=stub",
            "queues": {name: None for name in DRAMATIQ_QUEUE_NAMES},
        }

    client = _redis_client_from_url(redis_url)
    queues: dict[str, dict[str, int | None]] = {}
    try:
        for name in DRAMATIQ_QUEUE_NAMES:
            pending = client.llen(f"{DRAMATIQ_NAMESPACE}:{name}")
            delayed = client.llen(f"{DRAMATIQ_NAMESPACE}:{name}.DQ")
            queues[name] = {"pending": int(pending), "delayed": int(delayed)}
    finally:
        client.close()

    return {"skipped": False, "queues": queues}


def aggregate_provider_batch_metrics(db) -> dict[str, Any]:
    """聚合模力指数 ProviderBatch：submitted/processing/completed/failed 与 poll_count。"""
    from sqlalchemy import func, select

    rows = db.execute(
        select(ProviderBatch.status, func.count())
        .where(
            ProviderBatch.is_deleted.is_(False),
            ProviderBatch.provider_name == "molizhishu",
        )
        .group_by(ProviderBatch.status)
    ).all()
    by_status = {status: int(count) for status, count in rows}

    poll_rows = db.scalars(
        select(ProviderBatch.raw_status_json).where(
            ProviderBatch.is_deleted.is_(False),
            ProviderBatch.provider_name == "molizhishu",
        )
    ).all()
    poll_counts = [
        int(item.get("poll_count") or 0)
        for item in poll_rows
        if isinstance(item, dict)
    ]

    return {
        "by_status": by_status,
        "submitted": by_status.get("submitted", 0),
        "processing": by_status.get("processing", 0),
        "completed": by_status.get("completed", 0) + by_status.get("partial_completed", 0),
        "failed": by_status.get("failed", 0),
        "poll_count_total": sum(poll_counts),
        "poll_count_max": max(poll_counts) if poll_counts else 0,
    }


def summarize_duration_ms(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "max": None, "avg": None, "p50": None, "p95": None}
    ordered = sorted(values)
    count = len(ordered)
    p50 = ordered[count // 2]
    p95_index = min(count - 1, int(count * 0.95))
    return {
        "count": count,
        "min": round(ordered[0], 2),
        "max": round(ordered[-1], 2),
        "avg": round(statistics.fmean(ordered), 2),
        "p50": round(p50, 2),
        "p95": round(ordered[p95_index], 2),
    }


def aggregate_agent_llm_metrics(db, *, run_id: int | None = None) -> dict[str, Any]:
    """聚合 Agent LLM：调用次数、失败分类、token usage、耗时分布。"""
    from sqlalchemy import select

    conditions = [AgentExecution.is_deleted.is_(False)]
    if run_id is not None:
        conditions.append(AgentExecution.run_id == run_id)

    rows = list(db.scalars(select(AgentExecution).where(*conditions)).all())
    by_status: dict[str, int] = {}
    failure_categories: dict[str, int] = {}
    prompt_tokens_total = 0
    completion_tokens_total = 0
    durations: list[float] = []

    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        if row.prompt_tokens:
            prompt_tokens_total += int(row.prompt_tokens)
        if row.completion_tokens:
            completion_tokens_total += int(row.completion_tokens)
        if row.status == "failed":
            label = (row.error_message or "unknown").strip()[:120] or "unknown"
            failure_categories[label] = failure_categories.get(label, 0) + 1
        if row.started_at and row.finished_at:
            delta_ms = (row.finished_at - row.started_at).total_seconds() * 1000
            durations.append(delta_ms)

    return {
        "call_count": len(rows),
        "by_status": by_status,
        "failure_categories": failure_categories,
        "prompt_tokens_total": prompt_tokens_total,
        "completion_tokens_total": completion_tokens_total,
        "duration_ms": summarize_duration_ms(durations),
    }


def build_release_checklist(
    *,
    settings: Settings,
    base_url: str,
    db_session_factory,
    strict_preflight: bool = False,
) -> dict[str, Any]:
    """组装完整上线验收观测报告（本地 + API + DB + Redis）。"""
    local = build_local_preflight_summary(settings)
    api_ready: dict[str, Any] | None = None
    api_error: str | None = None
    try:
        api_ready = fetch_api_ready(base_url)
    except httpx.HTTPError as exc:
        api_error = str(exc)

    worker_queues: dict[str, Any]
    try:
        worker_queues = inspect_worker_queues(
            settings.REDIS_URL,
            dramatiq_broker=settings.DRAMATIQ_BROKER,
        )
    except Exception as exc:  # noqa: BLE001
        worker_queues = {
            "skipped": True,
            "reason": f"redis queue inspect failed: {exc}",
            "queues": {name: None for name in DRAMATIQ_QUEUE_NAMES},
        }

    warnings: list[str] = list(local["preflight"].get("blockers") or [])
    cred_error = (local.get("adapter_registry") or {}).get("credential_error")
    if cred_error:
        warnings.append(f"凭证池解析失败: {cred_error}")

    provider_batch: dict[str, Any] = {
        "by_status": {},
        "submitted": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0,
        "poll_count_total": 0,
        "poll_count_max": 0,
    }
    agent_llm: dict[str, Any] = {
        "call_count": 0,
        "by_status": {},
        "failure_categories": {},
        "prompt_tokens_total": 0,
        "completion_tokens_total": 0,
        "duration_ms": summarize_duration_ms([]),
    }
    db_error: str | None = None
    try:
        with db_session_factory() as db:
            provider_batch = aggregate_provider_batch_metrics(db)
            agent_llm = aggregate_agent_llm_metrics(db)
    except Exception as exc:  # noqa: BLE001
        db_error = str(exc)
        warnings.append(f"DB 指标聚合失败: {db_error}")

    blockers: list[str] = []
    if api_error:
        blockers.append(f"无法访问 ready 探针: {api_error}")
    elif api_ready and not api_ready.get("ready"):
        blockers.append("API /ready 未返回 ready")
    if strict_preflight and warnings:
        blockers.extend(warnings)

    return {
        "base_url": base_url,
        "local_preflight": local,
        "api_ready": api_ready,
        "api_ready_error": api_error,
        "worker_queues": worker_queues,
        "provider_batch_metrics": provider_batch,
        "agent_llm_metrics": agent_llm,
        "db_metrics_error": db_error,
        "warnings": warnings,
        "blockers": blockers,
        "checklist_ok": not blockers,
    }


def print_release_checklist(report: dict[str, Any]) -> None:
    print("=== Release Checklist / Observability (Task O10) ===")
    print(f"Base URL: {report['base_url']}")
    print("")

    local = report["local_preflight"]
    runtime = local["runtime_summary"]
    adapter = local["adapter_registry"]
    print("[Config Preflight]")
    print(f"  APP_ENV: {runtime.get('app_env')}")
    print(f"  DRAMATIQ_BROKER: {local['preflight']['infrastructure']['dramatiq_broker']}")
    print(f"  adapter_registry.count: {adapter['registered_count']}")
    print(f"  adapter_registry.sample: {', '.join(adapter['registered_codes'][:6])}")
    if adapter["credential_count_by_platform"]:
        sample_cred = next(iter(adapter["credential_count_by_platform"].items()))
        print(f"  credential_count ({sample_cred[0]}): {sample_cred[1]}")
    if adapter.get("credential_error"):
        print(f"  credential_error: {adapter['credential_error']}")
    print("")

    api = report.get("api_ready")
    print("[API Ready]")
    if report.get("api_ready_error"):
        print(f"  error: {report['api_ready_error']}")
    elif api:
        print(f"  http_status: {api['http_status']}")
        print(f"  ready: {api['ready']}")
        print(f"  database_ok: {api['database_ok']}")
        print(f"  redis_ok: {api['redis_ok']}")
        platform_runtime = api.get("platform_runtime") or {}
        enabled = [
            item["platform_code"]
            for item in platform_runtime.get("platforms", [])
            if item.get("db_enabled")
        ]
        if enabled:
            print(f"  db_enabled_platforms: {len(enabled)}")
    print("")

    queues = report["worker_queues"]
    print("[Worker Queues]")
    if queues.get("skipped"):
        print(f"  skipped: {queues.get('reason')}")
    else:
        for name, depth in queues["queues"].items():
            print(f"  {name}: pending={depth['pending']}, delayed={depth['delayed']}")
    print("")

    batch = report["provider_batch_metrics"]
    print("[Molizhishu ProviderBatch]")
    print(
        "  submitted={submitted}, processing={processing}, completed={completed}, "
        "failed={failed}, poll_count_total={poll_count_total}, poll_count_max={poll_count_max}".format(
            **batch
        )
    )
    print("")

    agent = report["agent_llm_metrics"]
    duration = agent["duration_ms"]
    print("[Agent LLM]")
    print(f"  call_count: {agent['call_count']}")
    print(f"  by_status: {agent['by_status']}")
    print(
        "  tokens: prompt={prompt_tokens_total}, completion={completion_tokens_total}".format(
            **agent
        )
    )
    print(
        "  duration_ms: count={count}, avg={avg}, p50={p50}, p95={p95}, max={max}".format(
            **duration
        )
    )
    if agent["failure_categories"]:
        print(f"  failure_categories: {agent['failure_categories']}")
    print("")

    if report["blockers"]:
        print("Blockers:")
        for item in report["blockers"]:
            print(f"  - {item}")
    elif report.get("warnings"):
        print("Preflight warnings (非致命，真实 provider smoke 前需处理):")
        for item in report["warnings"]:
            print(f"  - {item}")
    else:
        print("Checklist OK：配置与 ready 探针通过；队列/指标供发布前人工核对。")


def checklist_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("checklist_ok") else 1
