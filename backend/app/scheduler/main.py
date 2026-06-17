"""独立 APScheduler 进程入口。

启动：
    backend/.venv/Scripts/python.exe -m app.scheduler.main
"""

from __future__ import annotations

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import SessionLocal
from app.scheduler import jobs as scheduler_jobs

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def create_scheduler(session_factory: sessionmaker | None = None) -> BlockingScheduler:
    factory = session_factory or SessionLocal
    scheduler = BlockingScheduler(timezone=settings.SCHEDULER_TIMEZONE)

    def sync_job() -> None:
        scheduler_jobs.sync_schedules(scheduler, factory)

    scheduler.add_job(
        sync_job,
        trigger="interval",
        seconds=settings.SCHEDULER_POLL_SECONDS,
        id="sync_monitor_schedules",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sync_job()
    return scheduler


def main() -> int:
    if not settings.SCHEDULER_ENABLED:
        logger.error("SCHEDULER_ENABLED=false，拒绝启动调度进程")
        return 1

    _configure_logging()
    scheduler = create_scheduler()
    stop_requested = False

    def _handle_stop(signum, frame) -> None:  # noqa: ARG001
        nonlocal stop_requested
        stop_requested = True
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    logger.info(
        "monitor scheduler started (poll=%ss, timezone=%s)",
        settings.SCHEDULER_POLL_SECONDS,
        settings.SCHEDULER_TIMEZONE,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        stop_requested = True
    if stop_requested:
        logger.info("monitor scheduler stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
