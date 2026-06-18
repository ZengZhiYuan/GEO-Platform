"""报告生成 Dramatiq Actor。"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

import dramatiq

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.geo_monitoring.reports.storage import ReportStorage, generate_report_content
from app.worker import broker as _broker  # noqa: F401

logger = logging.getLogger(__name__)

_session_factory: Callable[[], Session] | None = None


# 注入可替换的数据库会话工厂，便于测试。
def configure_session_factory(factory: Callable[[], Session]) -> None:
    global _session_factory
    _session_factory = factory


# 重置会话工厂为默认的 SessionLocal。
def reset_session_factory() -> None:
    global _session_factory
    _session_factory = None


# 打开数据库会话，优先使用已注入的工厂。
def _open_session() -> Session:
    if _session_factory is not None:
        return _session_factory()
    return SessionLocal()


# 定时清理超过保留期且未标记保留的报告文件。
@dramatiq.actor(queue_name="report", max_retries=0)
def cleanup_expired_reports_task() -> int:
    """清理超过保留期且未标记保留的报告文件。"""
    from app.geo_monitoring.reports.storage import purge_expired_reports

    db = _open_session()
    storage = ReportStorage(get_settings().REPORT_STORAGE_DIR)
    try:
        removed = purge_expired_reports(
            db,
            storage,
            retention_days=get_settings().REPORT_RETENTION_DAYS,
        )
        logger.info("purged %s expired reports", removed)
        return removed
    finally:
        db.close()


# 消费报告队列消息，渲染并持久化指定报告内容。
@dramatiq.actor(queue_name="report", max_retries=0)
def generate_report_task(report_id: int) -> None:
    db = _open_session()
    storage = ReportStorage(get_settings().REPORT_STORAGE_DIR)
    try:
        report = generate_report_content(db, report_id, storage=storage)
        logger.info(
            "report generated report_id=%s status=%s size=%s",
            report_id,
            report.status,
            report.file_size,
        )
    except Exception:
        logger.exception("report generation failed report_id=%s", report_id)
        raise
    finally:
        db.close()
