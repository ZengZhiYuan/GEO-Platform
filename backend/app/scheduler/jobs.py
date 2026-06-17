"""APScheduler 调度 job 同步与触发。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.geo_monitoring.models import MonitorSchedule
from app.geo_monitoring.services import schedules as schedule_service

if TYPE_CHECKING:
    from apscheduler.schedulers.base import BaseScheduler
    from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

JOB_ID_PREFIX = "monitor_schedule:"


def build_job_id(schedule_id: int) -> str:
    return f"{JOB_ID_PREFIX}{schedule_id}"


def build_misfire_kwargs(misfire_policy: str) -> dict:
    if misfire_policy == "ignore":
        return {
            "coalesce": False,
            "misfire_grace_time": 1,
            "max_instances": 1,
        }
    return {
        "coalesce": True,
        "misfire_grace_time": 3600,
        "max_instances": 1,
    }


def execute_schedule_fire(
    schedule_id: int,
    *,
    session_factory: sessionmaker,
    planned_fire_time: datetime | None = None,
):
    moment = planned_fire_time or datetime.now(timezone.utc)
    with session_factory() as db:
        schedule = schedule_service.get_schedule(db, schedule_id)
        if not schedule.enabled:
            logger.info("skip disabled schedule %s", schedule_id)
            return None
        aligned = schedule_service.align_planned_fire_time(schedule, moment)
        return schedule_service.fire_schedule(db, schedule_id, aligned)


def sync_schedules(
    scheduler: BaseScheduler,
    session_factory: sessionmaker,
) -> None:
    with session_factory() as db:
        enabled_schedules = list(
            db.execute(
                select(MonitorSchedule).where(
                    MonitorSchedule.is_deleted.is_(False),
                    MonitorSchedule.enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )
        enabled_ids = {schedule.id for schedule in enabled_schedules}

    for job in scheduler.get_jobs():
        if not job.id.startswith(JOB_ID_PREFIX):
            continue
        schedule_id = int(job.id.removeprefix(JOB_ID_PREFIX))
        if schedule_id not in enabled_ids:
            scheduler.remove_job(job.id)

    for schedule in enabled_schedules:
        tz = schedule_service.get_zoneinfo(schedule.timezone)
        trigger = CronTrigger.from_crontab(schedule.cron_expr, timezone=tz)
        scheduler.add_job(
            _build_fire_callable(session_factory, schedule.id),
            trigger=trigger,
            id=build_job_id(schedule.id),
            replace_existing=True,
            **build_misfire_kwargs(schedule.misfire_policy),
        )


def _build_fire_callable(
    session_factory: sessionmaker,
    schedule_id: int,
) -> Callable[[], object]:
    def _fire() -> object:
        return execute_schedule_fire(
            schedule_id,
            session_factory=session_factory,
        )

    return _fire
