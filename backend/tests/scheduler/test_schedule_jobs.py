"""APScheduler job 同步与触发测试。"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from apscheduler.schedulers.background import BackgroundScheduler
from freezegun import freeze_time

from app.geo_monitoring.models import MonitorRun
from app.geo_monitoring.schemas import ScheduleCreate
from app.geo_monitoring.services import schedules as schedule_service
from app.scheduler import jobs as scheduler_jobs


def _create_schedule(db, project_id: int, *, enabled: bool = True, **kwargs):
    payload = ScheduleCreate(
        name=kwargs.pop("name", "hourly"),
        cron_expr=kwargs.pop("cron_expr", "0 * * * *"),
        timezone=kwargs.pop("timezone", "UTC"),
        enabled=enabled,
        misfire_policy=kwargs.pop("misfire_policy", "fire_once"),
    )
    return schedule_service.create_schedule(db, project_id, payload)


@freeze_time("2026-06-17 09:00:00")
def test_sync_schedules_registers_enabled_jobs_only(db, session_factory, schedule_setup):
    enabled = _create_schedule(db, schedule_setup["project_id"], name="enabled")
    disabled = _create_schedule(
        db, schedule_setup["project_id"], name="disabled", enabled=False
    )
    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler_jobs.sync_schedules(scheduler, session_factory)
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert scheduler_jobs.build_job_id(enabled.id) in job_ids
    assert scheduler_jobs.build_job_id(disabled.id) not in job_ids


@freeze_time("2026-06-17 09:00:00")
def test_sync_schedules_removes_stale_jobs(db, session_factory, schedule_setup):
    schedule = _create_schedule(db, schedule_setup["project_id"])
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: None,
        trigger="interval",
        seconds=3600,
        id=scheduler_jobs.build_job_id(schedule.id),
    )

    schedule_service.set_schedule_enabled(db, schedule.id, False)

    scheduler_jobs.sync_schedules(scheduler, session_factory)
    assert scheduler.get_job(scheduler_jobs.build_job_id(schedule.id)) is None


@freeze_time("2026-06-17 09:00:00")
def test_execute_schedule_fire_is_idempotent(db, session_factory, schedule_setup):
    schedule = _create_schedule(db, schedule_setup["project_id"])
    planned = datetime(2026, 6, 17, 9, 0, tzinfo=timezone.utc)

    first = scheduler_jobs.execute_schedule_fire(
        schedule.id,
        session_factory=session_factory,
        planned_fire_time=planned,
    )
    second = scheduler_jobs.execute_schedule_fire(
        schedule.id,
        session_factory=session_factory,
        planned_fire_time=planned,
    )

    assert first.id == second.id
    from sqlalchemy import func, select

    with session_factory() as session:
        count = session.scalar(
            select(func.count())
            .select_from(MonitorRun)
            .where(MonitorRun.triggered_by == schedule.id)
        )
    assert count == 1


def test_misfire_kwargs_for_ignore_policy():
    kwargs = scheduler_jobs.build_misfire_kwargs("ignore")
    assert kwargs["coalesce"] is False
    assert kwargs["misfire_grace_time"] == 1


def test_misfire_kwargs_for_fire_once_policy():
    kwargs = scheduler_jobs.build_misfire_kwargs("fire_once")
    assert kwargs["coalesce"] is True
    assert kwargs["max_instances"] == 1
