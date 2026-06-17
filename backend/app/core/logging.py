"""Structured JSON logging for API, worker and scheduler processes."""

from __future__ import annotations

import json
import logging
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
run_id_var: ContextVar[int | None] = ContextVar("run_id", default=None)
task_id_var: ContextVar[int | None] = ContextVar("task_id", default=None)
platform_code_var: ContextVar[str | None] = ContextVar("platform_code", default=None)

STRUCTURED_FIELDS = (
    "request_id",
    "run_id",
    "task_id",
    "platform_code",
    "duration_ms",
    "event",
    "from_status",
    "to_status",
    "error_category",
)

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"(api[_-]?key|secret|password|token)\s*[:=]\s*\S+", re.IGNORECASE),
)


def new_request_id() -> str:
    return uuid4().hex


def redact_sensitive_text(value: str) -> str:
    sanitized = value
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


def bind_log_context(
    *,
    request_id: str | None = None,
    run_id: int | None = None,
    task_id: int | None = None,
    platform_code: str | None = None,
) -> dict[str, Any]:
    tokens: dict[str, Any] = {}
    if request_id is not None:
        tokens["request_id"] = request_id_var.set(request_id)
    if run_id is not None:
        tokens["run_id"] = run_id_var.set(run_id)
    if task_id is not None:
        tokens["task_id"] = task_id_var.set(task_id)
    if platform_code is not None:
        tokens["platform_code"] = platform_code_var.set(platform_code)
    return tokens


def reset_log_context(tokens: dict[str, Any]) -> None:
    if "request_id" in tokens:
        request_id_var.reset(tokens["request_id"])
    if "run_id" in tokens:
        run_id_var.reset(tokens["run_id"])
    if "task_id" in tokens:
        task_id_var.reset(tokens["task_id"])
    if "platform_code" in tokens:
        platform_code_var.reset(tokens["platform_code"])


@contextmanager
def log_context(**kwargs: Any) -> Iterator[None]:
    tokens = bind_log_context(**kwargs)
    try:
        yield
    finally:
        reset_log_context(tokens)


_STANDARD_LOGRECORD_ATTRS = frozenset(
    logging.LogRecord(
        name="",
        level=0,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__
)


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(record.getMessage()),
            "request_id": getattr(record, "request_id", None) or request_id_var.get(),
            "run_id": getattr(record, "run_id", None) or run_id_var.get(),
            "task_id": getattr(record, "task_id", None) or task_id_var.get(),
            "platform_code": getattr(record, "platform_code", None) or platform_code_var.get(),
            "duration_ms": getattr(record, "duration_ms", None),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOGRECORD_ATTRS or key in payload or value is None:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = redact_sensitive_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(*, level: int | str = logging.INFO) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    logging.captureWarnings(True)


def log_state_transition(
    logger: logging.Logger,
    *,
    entity: str,
    entity_id: int | str,
    from_status: str,
    to_status: str,
    **extra: Any,
) -> None:
    logger.info(
        "%s %s transitioned %s -> %s",
        entity,
        entity_id,
        from_status,
        to_status,
        extra={
            "event": "state_transition",
            "from_status": from_status,
            "to_status": to_status,
            **extra,
        },
    )


def log_external_api_error(
    logger: logging.Logger,
    *,
    platform_code: str,
    error_category: str,
    message: str,
    duration_ms: int | None = None,
    **extra: Any,
) -> None:
    logger.warning(
        "external api error platform=%s category=%s",
        platform_code,
        error_category,
        extra={
            "event": "external_api_error",
            "platform_code": platform_code,
            "error_category": error_category,
            "duration_ms": duration_ms,
            "detail": redact_sensitive_text(message),
            **extra,
        },
    )


def log_worker_startup(registered_actors: list[str]) -> None:
    logger = logging.getLogger("app.worker")
    logger.info(
        "worker actors registered",
        extra={
            "event": "worker_startup",
            "registered_actors": sorted(registered_actors),
        },
    )


def log_scheduler_startup(*, job_count: int, poll_seconds: int, timezone_name: str) -> None:
    logger = logging.getLogger("app.scheduler")
    logger.info(
        "scheduler jobs loaded",
        extra={
            "event": "scheduler_startup",
            "job_count": job_count,
            "poll_seconds": poll_seconds,
            "timezone": timezone_name,
        },
    )


@contextmanager
def timed_log(
    logger: logging.Logger,
    message: str,
    **extra: Any,
) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(message, extra={"duration_ms": duration_ms, **extra})
