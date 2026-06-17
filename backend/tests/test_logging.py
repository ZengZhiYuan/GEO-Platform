"""Structured logging unit tests."""

from __future__ import annotations

import json
import logging

import pytest

from app.core.logging import (
    StructuredJsonFormatter,
    configure_logging,
    log_external_api_error,
    log_scheduler_startup,
    log_state_transition,
    log_worker_startup,
    redact_sensitive_text,
)


@pytest.fixture
def log_capture():
    logger = logging.getLogger("test.logging")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    records: list[str] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(StructuredJsonFormatter().format(record))

    handler = _ListHandler()
    logger.addHandler(handler)
    return logger, records


def test_redact_sensitive_text_masks_api_keys():
    text = "Authorization failed for sk-test-secret-key-abcdef"
    sanitized = redact_sensitive_text(text)
    assert "sk-test-secret-key-abcdef" not in sanitized
    assert "[REDACTED]" in sanitized


def test_structured_formatter_includes_required_fields(log_capture):
    logger, records = log_capture
    logger.info(
        "task finished",
        extra={
            "request_id": "req-1",
            "run_id": 9,
            "task_id": 42,
            "platform_code": "qwen",
            "duration_ms": 120,
        },
    )
    payload = json.loads(records[0])
    assert payload["request_id"] == "req-1"
    assert payload["run_id"] == 9
    assert payload["task_id"] == 42
    assert payload["platform_code"] == "qwen"
    assert payload["duration_ms"] == 120


def test_log_state_transition_emits_structured_event(log_capture):
    logger, records = log_capture
    log_state_transition(
        logger,
        entity="MonitorRun",
        entity_id=7,
        from_status="collecting",
        to_status="completed",
        run_id=7,
    )
    payload = json.loads(records[0])
    assert payload["event"] == "state_transition"
    assert payload["from_status"] == "collecting"
    assert payload["to_status"] == "completed"


def test_log_external_api_error_redacts_secrets(log_capture):
    logger, records = log_capture
    log_external_api_error(
        logger,
        platform_code="qwen",
        error_category="unauthorized",
        message="Bearer sk-leaked-token rejected",
        duration_ms=88,
    )
    payload = json.loads(records[0])
    assert payload["event"] == "external_api_error"
    assert payload["platform_code"] == "qwen"
    assert "sk-leaked-token" not in json.dumps(payload)


def test_log_worker_startup_lists_registered_actors(log_capture):
    logger, records = log_capture
    logging.getLogger("app.worker").handlers.clear()
    logging.getLogger("app.worker").addHandler(logger.handlers[0])
    logging.getLogger("app.worker").setLevel(logging.INFO)
    log_worker_startup(["collect_query_task", "analyze_run", "generate_report_task"])
    payload = json.loads(records[0])
    assert payload["event"] == "worker_startup"
    assert payload["registered_actors"] == [
        "analyze_run",
        "collect_query_task",
        "generate_report_task",
    ]


def test_log_scheduler_startup_reports_job_count(log_capture):
    logger, records = log_capture
    logging.getLogger("app.scheduler").handlers.clear()
    logging.getLogger("app.scheduler").addHandler(logger.handlers[0])
    logging.getLogger("app.scheduler").setLevel(logging.INFO)
    log_scheduler_startup(job_count=3, poll_seconds=30, timezone_name="Asia/Shanghai")
    payload = json.loads(records[0])
    assert payload["event"] == "scheduler_startup"
    assert payload["job_count"] == 3


def test_configure_logging_installs_json_formatter():
    configure_logging(level=logging.WARNING)
    root = logging.getLogger()
    assert root.handlers
    assert isinstance(root.handlers[0].formatter, StructuredJsonFormatter)
