"""Task O10：上线验收与观测 helper 测试。"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from app.geo_monitoring.models import MonitorProject, MonitorRun, PromptSet, ProviderBatch
from app.geo_monitoring.services import analysis as analysis_models  # noqa: F401
from app.geo_monitoring.services.analysis import AgentExecution
from release_observability import (
    DRAMATIQ_QUEUE_NAMES,
    aggregate_agent_llm_metrics,
    aggregate_provider_batch_metrics,
    build_local_preflight_summary,
    inspect_worker_queues,
    summarize_duration_ms,
)


def test_build_local_preflight_summary_includes_adapter_registry(monkeypatch):
    monkeypatch.setenv("MOLIZHISHU_ENABLED", "false")
    monkeypatch.setenv("MOLIZHISHU_API_TOKEN", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    summary = build_local_preflight_summary(get_settings())

    assert "runtime_summary" in summary
    assert "adapter_registry" in summary
    assert "registered_count" in summary["adapter_registry"]
    assert isinstance(summary["adapter_registry"]["registered_codes"], list)
    get_settings.cache_clear()


def test_inspect_worker_queues_skips_stub_broker():
    report = inspect_worker_queues("redis://localhost:6379/0", dramatiq_broker="stub")
    assert report["skipped"] is True
    assert report["queues"] == {name: None for name in DRAMATIQ_QUEUE_NAMES}


def test_inspect_worker_queues_reads_redis_depths(monkeypatch):
    client = MagicMock()
    client.llen.side_effect = [3, 1, 0, 0, 2, 0]
    monkeypatch.setattr(
        "release_observability._redis_client_from_url",
        lambda _url: client,
    )

    report = inspect_worker_queues("redis://localhost:6379/0", dramatiq_broker="redis")

    assert report["skipped"] is False
    assert report["queues"]["collection"] == {"pending": 3, "delayed": 1}
    assert report["queues"]["analysis"] == {"pending": 0, "delayed": 0}
    assert report["queues"]["report"] == {"pending": 2, "delayed": 0}
    client.close.assert_called_once()


def test_aggregate_provider_batch_metrics_groups_status_and_poll_count(session_factory):
    with session_factory() as db:
        project = MonitorProject(project_name="O10-batch", status="active")
        db.add(project)
        db.flush()
        prompt_set = PromptSet(
            project_id=project.id,
            set_name="O10",
            version_no="v1",
            status="active",
        )
        db.add(prompt_set)
        db.flush()
        run = MonitorRun(
            run_no="RUN-O10-BATCH",
            project_id=project.id,
            prompt_set_id=prompt_set.id,
            prompt_set_version="v1",
            status="collecting",
            collection_source="molizhishu",
        )
        db.add(run)
        db.flush()
        db.add_all(
            [
                ProviderBatch(
                    run_id=run.id,
                    provider_name="molizhishu",
                    batch_no=1,
                    status="submitted",
                    raw_status_json={"poll_count": 2},
                ),
                ProviderBatch(
                    run_id=run.id,
                    provider_name="molizhishu",
                    batch_no=2,
                    status="processing",
                    raw_status_json={"poll_count": 5},
                ),
                ProviderBatch(
                    run_id=run.id,
                    provider_name="molizhishu",
                    batch_no=3,
                    status="completed",
                    raw_status_json={"poll_count": 1},
                ),
                ProviderBatch(
                    run_id=run.id,
                    provider_name="molizhishu",
                    batch_no=4,
                    status="failed",
                    raw_status_json={"poll_count": 7},
                ),
            ]
        )
        db.commit()

        metrics = aggregate_provider_batch_metrics(db)

    assert metrics["submitted"] == 1
    assert metrics["processing"] == 1
    assert metrics["completed"] == 1
    assert metrics["failed"] == 1
    assert metrics["poll_count_total"] == 15
    assert metrics["poll_count_max"] == 7


def test_aggregate_agent_llm_metrics_counts_tokens_and_failures(session_factory):
    started = datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc)
    finished = started + timedelta(seconds=2)
    with session_factory() as db:
        project = MonitorProject(project_name="O10-agent", status="active")
        db.add(project)
        db.flush()
        prompt_set = PromptSet(
            project_id=project.id,
            set_name="O10-agent",
            version_no="v1",
            status="active",
        )
        db.add(prompt_set)
        db.flush()
        run = MonitorRun(
            run_no="RUN-O10-AGENT",
            project_id=project.id,
            prompt_set_id=prompt_set.id,
            prompt_set_version="v1",
            status="analyzing",
        )
        db.add(run)
        db.flush()
        db.add_all(
            [
                AgentExecution(
                    run_id=run.id,
                    agent_code="classify_sentiment",
                    status="success",
                    prompt_tokens=100,
                    completion_tokens=20,
                    started_at=started,
                    finished_at=finished,
                ),
                AgentExecution(
                    run_id=run.id,
                    agent_code="generate_insights",
                    status="failed",
                    error_message="timeout: upstream LLM",
                    prompt_tokens=50,
                    completion_tokens=0,
                    started_at=started,
                    finished_at=finished,
                ),
            ]
        )
        db.commit()

        metrics = aggregate_agent_llm_metrics(db, run_id=run.id)

    assert metrics["call_count"] == 2
    assert metrics["by_status"]["success"] == 1
    assert metrics["by_status"]["failed"] == 1
    assert metrics["prompt_tokens_total"] == 150
    assert metrics["completion_tokens_total"] == 20
    assert "timeout: upstream LLM" in metrics["failure_categories"]
    assert metrics["duration_ms"]["count"] == 2
    assert metrics["duration_ms"]["max"] == 2000.0


def test_summarize_duration_ms_empty():
    assert summarize_duration_ms([]) == {"count": 0, "min": None, "max": None, "avg": None, "p50": None, "p95": None}


def test_run_api_full_test_script_exposes_release_flags():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "run_api_full_test.py"
    ).read_text(encoding="utf-8")
    for token in (
        "--base-url",
        "--release-checklist-only",
        "release_observability",
        "build_release_checklist",
        "run_release_checklist_phase",
    ):
        assert token in source, f"missing run_api_full_test flag/helper: {token}"
