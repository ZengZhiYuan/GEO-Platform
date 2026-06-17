"""调度 service 单元测试。"""

from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import MonitorRun, MonitorSchedule
from app.geo_monitoring.schemas import ScheduleCreate, ScheduleUpdate
from app.geo_monitoring.services import schedules as schedule_service


def _create_schedule(db, project_id: int, **overrides) -> MonitorSchedule:
    payload = ScheduleCreate(
        name=overrides.pop("name", "daily-run"),
        cron_expr=overrides.pop("cron_expr", "0 9 * * *"),
        timezone=overrides.pop("timezone", "Asia/Shanghai"),
        misfire_policy=overrides.pop("misfire_policy", "fire_once"),
        enabled=overrides.pop("enabled", True),
    )
    return schedule_service.create_schedule(db, project_id, payload)


@freeze_time("2026-06-17 01:00:00")
def test_compute_next_fire_time_uses_schedule_timezone(db, project_id):
    schedule = _create_schedule(
        db,
        project_id,
        cron_expr="0 9 * * *",
        timezone="Asia/Shanghai",
    )

    assert schedule.next_run_at is not None
    next_at = schedule_service.as_utc(schedule.next_run_at)
    assert next_at is not None
    assert next_at.tzinfo is not None
    assert next_at.astimezone(
        schedule_service.get_zoneinfo("Asia/Shanghai")
    ).hour == 9


@freeze_time("2026-03-08 06:30:00")
def test_compute_next_fire_time_handles_dst_gap(db, project_id):
    schedule = _create_schedule(
        db,
        project_id,
        cron_expr="30 2 * * *",
        timezone="America/New_York",
    )

    assert schedule.next_run_at is not None
    next_at = schedule_service.as_utc(schedule.next_run_at)
    assert next_at is not None
    assert next_at > datetime(2026, 3, 8, 6, 30, tzinfo=timezone.utc)


def test_build_idempotency_key_uses_utc_iso(db, project_id):
    planned = datetime(2026, 6, 17, 9, 0, tzinfo=timezone.utc)
    key = schedule_service.build_idempotency_key(42, planned)

    assert key == "schedule:42:2026-06-17T09:00:00+00:00"


@freeze_time("2026-06-17 09:00:00")
def test_fire_schedule_creates_run_with_schedule_trigger(db, schedule_setup):
    schedule = _create_schedule(db, schedule_setup["project_id"])
    planned = datetime(2026, 6, 17, 1, 0, tzinfo=timezone.utc)

    run = schedule_service.fire_schedule(db, schedule.id, planned)

    assert run.trigger_type == "schedule"
    assert run.triggered_by == schedule.id
    assert run.result_json["schedule_idempotency_key"].startswith(
        f"schedule:{schedule.id}:"
    )
    assert run.status == "collecting"


@freeze_time("2026-06-17 09:00:00")
def test_fire_schedule_is_idempotent_for_same_planned_time(db, schedule_setup):
    schedule = _create_schedule(db, schedule_setup["project_id"])
    planned = datetime(2026, 6, 17, 1, 0, tzinfo=timezone.utc)

    first = schedule_service.fire_schedule(db, schedule.id, planned)
    second = schedule_service.fire_schedule(db, schedule.id, planned)

    assert first.id == second.id
    from sqlalchemy import func, select

    count = db.scalar(
        select(func.count())
        .select_from(MonitorRun)
        .where(MonitorRun.triggered_by == schedule.id)
    )
    assert count == 1


@freeze_time("2026-06-17 09:00:00")
def test_fire_schedule_updates_last_and_next_run(db, schedule_setup):
    schedule = _create_schedule(db, schedule_setup["project_id"])
    planned = datetime(2026, 6, 17, 1, 0, tzinfo=timezone.utc)

    schedule_service.fire_schedule(db, schedule.id, planned)
    db.refresh(schedule)

    assert schedule.last_run_at is not None
    assert schedule.next_run_at is not None
    assert schedule.next_run_at > schedule.last_run_at


@freeze_time("2026-06-17 09:00:00")
def test_resolve_missed_fire_time_fire_once_returns_latest_only(db, schedule_setup):
    schedule = _create_schedule(
        db,
        schedule_setup["project_id"],
        cron_expr="0 * * * *",
        misfire_policy="fire_once",
    )
    now = datetime(2026, 6, 17, 9, 0, tzinfo=timezone.utc)
    last_run = datetime(2026, 6, 17, 6, 0, tzinfo=timezone.utc)

    missed = schedule_service.resolve_missed_fire_time(schedule, last_run, now)

    assert missed == datetime(2026, 6, 17, 8, 0, tzinfo=timezone.utc)


@freeze_time("2026-06-17 09:00:00")
def test_resolve_missed_fire_time_ignore_returns_none(db, schedule_setup):
    schedule = _create_schedule(
        db,
        schedule_setup["project_id"],
        cron_expr="0 * * * *",
        misfire_policy="ignore",
    )
    now = datetime(2026, 6, 17, 9, 0, tzinfo=timezone.utc)
    last_run = datetime(2026, 6, 17, 6, 0, tzinfo=timezone.utc)

    assert schedule_service.resolve_missed_fire_time(schedule, last_run, now) is None


def test_create_schedule_rejects_invalid_cron(db, project_id):
    with pytest.raises(BusinessException) as exc:
        schedule_service.create_schedule(
            db,
            project_id,
            ScheduleCreate(name="bad", cron_expr="not-a-cron"),
        )

    assert exc.value.code == 40050


def test_create_schedule_rejects_duplicate_name(db, project_id):
    _create_schedule(db, project_id, name="nightly")

    with pytest.raises(BusinessException) as exc:
        _create_schedule(db, project_id, name="nightly")

    assert exc.value.code == 40904


def test_update_schedule_recomputes_next_run(db, project_id):
    with freeze_time("2026-06-17 01:00:00"):
        schedule = _create_schedule(db, project_id, cron_expr="0 9 * * *")
        previous_next = schedule.next_run_at

    with freeze_time("2026-06-17 02:00:00"):
        updated = schedule_service.update_schedule(
            db,
            schedule.id,
            ScheduleUpdate(cron_expr="0 10 * * *"),
        )

    assert updated.next_run_at != previous_next
    next_at = schedule_service.as_utc(updated.next_run_at)
    assert next_at is not None
    assert (
        next_at.astimezone(schedule_service.get_zoneinfo("Asia/Shanghai")).hour
        == 10
    )


def test_set_schedule_enabled(db, project_id):
    schedule = _create_schedule(db, project_id, enabled=True)

    disabled = schedule_service.set_schedule_enabled(db, schedule.id, False)
    assert disabled.enabled is False

    enabled = schedule_service.set_schedule_enabled(db, schedule.id, True)
    assert enabled.enabled is True
