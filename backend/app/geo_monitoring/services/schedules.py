"""监测调度服务。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import MonitorRun, MonitorSchedule
from app.geo_monitoring.repositories import runs as run_repo
from app.geo_monitoring.schemas import ScheduleCreate, ScheduleUpdate
from app.geo_monitoring.services.projects import require_active_project


def get_zoneinfo(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise BusinessException(message=f"无效时区: {tz_name}", code=40051) from exc


def validate_cron_expr(cron_expr: str) -> str:
    try:
        CronTrigger.from_crontab(cron_expr, timezone=timezone.utc)
    except ValueError as exc:
        raise BusinessException(message=f"无效 cron 表达式: {cron_expr}", code=40050) from exc
    return cron_expr


def build_idempotency_key(schedule_id: int, planned_fire_time: datetime) -> str:
    utc_time = planned_fire_time.astimezone(timezone.utc)
    return f"schedule:{schedule_id}:{utc_time.isoformat()}"


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _ensure_utc(value)


def compute_next_fire_time(
    cron_expr: str,
    tz_name: str,
    *,
    after: datetime | None = None,
) -> datetime:
    validate_cron_expr(cron_expr)
    tz = get_zoneinfo(tz_name)
    reference = _ensure_utc(after or datetime.now(timezone.utc)).astimezone(tz)
    trigger = CronTrigger.from_crontab(cron_expr, timezone=tz)
    next_fire = trigger.get_next_fire_time(None, reference)
    if next_fire is None:
        raise BusinessException(message="无法计算下次运行时间", code=40052)
    if next_fire.tzinfo is None:
        next_fire = next_fire.replace(tzinfo=tz)
    return _ensure_utc(next_fire)


def _iter_cron_fire_times(
    cron_expr: str,
    tz_name: str,
    *,
    start: datetime,
    end: datetime,
) -> list[datetime]:
    tz = get_zoneinfo(tz_name)
    trigger = CronTrigger.from_crontab(cron_expr, timezone=tz)
    local_start = start.astimezone(tz)
    local_end = end.astimezone(tz)
    probe = local_start - timedelta(days=2)
    previous: datetime | None = None
    fire_times: list[datetime] = []
    while True:
        next_fire = trigger.get_next_fire_time(
            previous,
            probe if previous is None else previous + timedelta(seconds=1),
        )
        if next_fire is None or next_fire > local_end:
            break
        if next_fire >= local_start:
            fire_times.append(_ensure_utc(next_fire))
        previous = next_fire
    return fire_times


def align_planned_fire_time(
    schedule: MonitorSchedule, moment: datetime
) -> datetime:
    tz = get_zoneinfo(schedule.timezone)
    local_moment = moment.astimezone(tz)
    trigger = CronTrigger.from_crontab(schedule.cron_expr, timezone=tz)
    probe = local_moment - timedelta(days=2)
    previous: datetime | None = None
    aligned: datetime | None = None
    while True:
        next_fire = trigger.get_next_fire_time(
            previous,
            probe if previous is None else previous + timedelta(seconds=1),
        )
        if next_fire is None or next_fire > local_moment:
            break
        aligned = next_fire
        previous = next_fire
    if aligned is None:
        return _ensure_utc(moment)
    return _ensure_utc(aligned)


def resolve_missed_fire_time(
    schedule: MonitorSchedule,
    last_run_at: datetime | None,
    now: datetime,
) -> datetime | None:
    if schedule.misfire_policy == "ignore":
        return None
    upper_bound = align_planned_fire_time(
        schedule, now - timedelta(seconds=1)
    )
    if last_run_at is not None and last_run_at.astimezone(timezone.utc) >= upper_bound:
        return None
    start = (
        last_run_at.astimezone(timezone.utc) + timedelta(seconds=1)
        if last_run_at is not None
        else upper_bound - timedelta(days=1)
    )
    fire_times = _iter_cron_fire_times(
        schedule.cron_expr,
        schedule.timezone,
        start=start,
        end=upper_bound,
    )
    if not fire_times:
        return None
    return fire_times[-1]


def _find_run_by_idempotency_key(db: Session, key: str) -> MonitorRun | None:
    return db.execute(
        select(MonitorRun).where(
            MonitorRun.is_deleted.is_(False),
            MonitorRun.result_json["schedule_idempotency_key"].as_string() == key,
        )
    ).scalar_one_or_none()


def _try_acquire_schedule_lock(db: Session, idempotency_key: str) -> bool:
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        lock_key = int.from_bytes(
            hashlib.sha256(idempotency_key.encode("utf-8")).digest()[:8],
            "big",
        ) & 0x7FFFFFFFFFFFFFFF
        return bool(
            db.execute(
                text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
                {"lock_key": lock_key},
            ).scalar()
        )
    return True


def get_schedule(db: Session, schedule_id: int) -> MonitorSchedule:
    schedule = db.execute(
        select(MonitorSchedule).where(
            MonitorSchedule.id == schedule_id,
            MonitorSchedule.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if schedule is None:
        raise BusinessException(message="监测调度不存在", code=40400)
    return schedule


def list_schedules(
    db: Session,
    *,
    project_id: int,
    page: int,
    page_size: int,
) -> tuple[list[MonitorSchedule], int]:
    require_active_project(db, project_id)
    conditions = [
        MonitorSchedule.project_id == project_id,
        MonitorSchedule.is_deleted.is_(False),
    ]
    total = db.scalar(
        select(func.count()).select_from(MonitorSchedule).where(*conditions)
    ) or 0
    items = list(
        db.execute(
            select(MonitorSchedule)
            .where(*conditions)
            .order_by(MonitorSchedule.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def create_schedule(
    db: Session, project_id: int, payload: ScheduleCreate
) -> MonitorSchedule:
    require_active_project(db, project_id)
    validate_cron_expr(payload.cron_expr)
    get_zoneinfo(payload.timezone)
    schedule = MonitorSchedule(
        project_id=project_id,
        name=payload.name,
        cron_expr=payload.cron_expr,
        timezone=payload.timezone,
        enabled=payload.enabled,
        misfire_policy=payload.misfire_policy.value,
        next_run_at=compute_next_fire_time(
            payload.cron_expr, payload.timezone
        ),
    )
    db.add(schedule)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessException(
            message="同一项目下调度名称已存在",
            code=40904,
            status_code=409,
        ) from exc
    db.refresh(schedule)
    return schedule


def update_schedule(
    db: Session, schedule_id: int, payload: ScheduleUpdate
) -> MonitorSchedule:
    schedule = get_schedule(db, schedule_id)
    data = payload.model_dump(exclude_unset=True)
    if "misfire_policy" in data and data["misfire_policy"] is not None:
        data["misfire_policy"] = data["misfire_policy"].value
    for field, value in data.items():
        setattr(schedule, field, value)
    if {"cron_expr", "timezone"} & data.keys():
        validate_cron_expr(schedule.cron_expr)
        get_zoneinfo(schedule.timezone)
        schedule.next_run_at = compute_next_fire_time(
            schedule.cron_expr, schedule.timezone
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessException(
            message="同一项目下调度名称已存在",
            code=40904,
            status_code=409,
        ) from exc
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule_id: int) -> None:
    schedule = get_schedule(db, schedule_id)
    now = datetime.now(timezone.utc)
    schedule.is_deleted = True
    schedule.deleted_at = now
    schedule.enabled = False
    db.commit()


def set_schedule_enabled(
    db: Session, schedule_id: int, enabled: bool
) -> MonitorSchedule:
    schedule = get_schedule(db, schedule_id)
    schedule.enabled = enabled
    if enabled:
        schedule.next_run_at = compute_next_fire_time(
            schedule.cron_expr, schedule.timezone
        )
    db.commit()
    db.refresh(schedule)
    return schedule


def _create_scheduled_run(
    db: Session,
    schedule: MonitorSchedule,
    *,
    idempotency_key: str,
    planned_fire_time: datetime,
) -> MonitorRun:
    from app.geo_monitoring.services.runs import (
        _enabled_prompts,
        _new_run_no,
        _resolve_platforms,
        _resolve_prompt_set,
        _start_collection,
    )

    project = require_active_project(db, schedule.project_id)
    prompt_set = _resolve_prompt_set(db, project.id, None)
    prompts = _enabled_prompts(db, prompt_set.id)
    platforms = _resolve_platforms(db, None)
    platform_codes = [platform.platform_code for platform in platforms]
    task_count = len(prompts) * len(platforms)
    run = MonitorRun(
        run_no=_new_run_no(),
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version=prompt_set.version_no,
        trigger_type="schedule",
        triggered_by=schedule.id,
        status="pending",
        collection_status="pending",
        analysis_status="skipped",
        report_status="skipped",
        platform_codes=platform_codes,
        expected_query_count=task_count,
        total_tasks=task_count,
        result_json={
            "schedule_idempotency_key": idempotency_key,
            "planned_fire_time": planned_fire_time.astimezone(timezone.utc).isoformat(),
        },
    )
    run_repo.add_run(db, run)
    db.flush()
    run_repo.build_query_tasks(db, run, prompts, platforms)
    now = datetime.now(timezone.utc)
    schedule.last_run_at = now
    schedule.next_run_at = compute_next_fire_time(
        schedule.cron_expr, schedule.timezone, after=now
    )
    db.commit()
    db.refresh(run)
    _start_collection(db, run.id)
    db.refresh(run)
    return run


def fire_schedule(
    db: Session,
    schedule_id: int,
    planned_fire_time: datetime,
) -> MonitorRun:
    schedule = get_schedule(db, schedule_id)
    if not schedule.enabled:
        raise BusinessException(message="监测调度未启用", code=40053)
    require_active_project(db, schedule.project_id)
    normalized = align_planned_fire_time(schedule, planned_fire_time)
    idempotency_key = build_idempotency_key(schedule.id, normalized)
    existing = _find_run_by_idempotency_key(db, idempotency_key)
    if existing is not None:
        return existing
    if not _try_acquire_schedule_lock(db, idempotency_key):
        existing = _find_run_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing
        raise BusinessException(message="调度触发正在处理中", code=40905, status_code=409)
    existing = _find_run_by_idempotency_key(db, idempotency_key)
    if existing is not None:
        return existing
    return _create_scheduled_run(
        db,
        schedule,
        idempotency_key=idempotency_key,
        planned_fire_time=normalized,
    )


def trigger_schedule_now(db: Session, schedule_id: int) -> MonitorRun:
    schedule = get_schedule(db, schedule_id)
    require_active_project(db, schedule.project_id)
    now = datetime.now(timezone.utc)
    manual_key = f"schedule:{schedule.id}:manual:{now.isoformat()}"
    return _create_scheduled_run(
        db,
        schedule,
        idempotency_key=manual_key,
        planned_fire_time=now,
    )
