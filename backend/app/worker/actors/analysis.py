"""分析运行 Dramatiq Actor。"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import dramatiq

from app.core.database import SessionLocal
from app.core.exceptions import BusinessException
from app.geo_monitoring.agents.llm import create_agent_llm_client
from app.geo_monitoring.models import MonitorRun, QueryTask
from app.geo_monitoring.services.analysis import (
    begin_run_analysis,
    build_agent_llm_config,
    run_analysis,
)
from app.geo_monitoring.services.runs import RUN_TERMINAL_STATUSES
from app.worker import broker as _broker  # noqa: F401

logger = logging.getLogger(__name__)

_TASK_IN_PROGRESS = frozenset({"pending", "queued", "running"})

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


# 采集全部结束后幂等地将运行分析任务入队。
def maybe_enqueue_run_analysis(run_id: int, *, db: Session | None = None) -> bool:
    """采集进入终态后自动入队一次分析（幂等）。"""
    owns_session = db is None
    if owns_session:
        db = _open_session()
    try:
        run = db.execute(
            select(MonitorRun).where(
                MonitorRun.id == run_id,
                MonitorRun.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if run is None or run.status not in RUN_TERMINAL_STATUSES:
            return False

        # 仍有进行中的查询任务时不触发分析
        in_progress = (
            db.scalar(
                select(func.count())
                .select_from(QueryTask)
                .where(
                    QueryTask.run_id == run_id,
                    QueryTask.status.in_(_TASK_IN_PROGRESS),
                    QueryTask.is_deleted.is_(False),
                )
            )
            or 0
        )
        if in_progress > 0:
            return False

        if run.analysis_status != "skipped":
            return False

        run.analysis_status = "pending"
        db.commit()

        analyze_run.send(run_id)
        return True
    finally:
        if owns_session:
            db.close()


# 消费分析队列消息，执行 LangGraph 语义分析并更新状态。
@dramatiq.actor(queue_name="analysis", max_retries=0)
def analyze_run(run_id: int) -> None:
    """消费 run_id 消息，执行 LangGraph 分析。"""
    db = _open_session()
    try:
        run = db.execute(
            select(MonitorRun).where(
                MonitorRun.id == run_id,
                MonitorRun.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if run is None:
            return

        try:
            begin_run_analysis(db, run_id)
        except BusinessException as exc:
            if exc.code == 40911:
                logger.info("analysis already running run_id=%s", run_id)
                return
            raise

        try:
            llm_client = create_agent_llm_client(build_agent_llm_config())
        except BusinessException as exc:
            if exc.code == 50301:
                run = db.get(MonitorRun, run_id)
                if run is not None:
                    run.analysis_status = "failed"
                    db.commit()
                logger.warning(
                    "analysis skipped run_id=%s: agent llm not configured",
                    run_id,
                )
                return
            raise

        result = run_analysis(db, run_id, llm_client=llm_client)
        logger.info(
            "analysis finished run_id=%s status=%s skip_reason=%s",
            run_id,
            result.get("analysis_status"),
            result.get("skip_reason"),
        )
    except Exception:
        db.rollback()
        run = db.get(MonitorRun, run_id)
        if run is not None:
            run.analysis_status = "failed"
            db.commit()
        logger.exception("analysis failed run_id=%s", run_id)
        raise
    finally:
        db.close()
