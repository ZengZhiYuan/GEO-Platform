"""监测运行与查询任务扇出服务。"""

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import Answer, MonitorRun, QueryTask
from app.geo_monitoring.repositories import platforms as platform_repo
from app.geo_monitoring.repositories import prompts as prompt_repo
from app.geo_monitoring.repositories import runs as run_repo
from app.geo_monitoring.schemas import RunCreate, RunDetailRead
from app.geo_monitoring.services.projects import require_active_project

RUN_TERMINAL_STATUSES = frozenset(
    {"completed", "partial_success", "failed", "cancelled"}
)
CANCELLABLE_TASK_STATUSES = frozenset({"pending", "queued", "running"})


def _new_run_no() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"RUN-{timestamp}-{uuid4().hex[:8].upper()}"


def _resolve_prompt_set(db: Session, project_id: int, prompt_set_id: int | None):
    prompt_set = prompt_repo.resolve_active_prompt_set(
        db, project_id, prompt_set_id
    )
    if prompt_set is None:
        raise BusinessException(message="项目没有可用的激活提示词集", code=40030)
    return prompt_set


def _enabled_prompts(db: Session, prompt_set_id: int):
    prompts = prompt_repo.list_enabled_prompts(db, prompt_set_id)
    if not prompts:
        raise BusinessException(
            message="激活提示词集没有可用提示词",
            code=40901,
            status_code=409,
        )
    return prompts


def _resolve_platforms(db: Session, platform_codes: list[str] | None):
    rows = platform_repo.list_candidates(db, platform_codes)
    by_code = {platform.platform_code: platform for platform in rows}

    if platform_codes is None:
        platforms = sorted(
            (platform for platform in rows if platform.enabled),
            key=lambda item: item.id,
        )
    else:
        platforms = []
        for code in platform_codes:
            platform = by_code.get(code)
            if platform is None or not platform.enabled:
                raise BusinessException(message=f"AI 平台不可用: {code}", code=40031)
            platforms.append(platform)
    if not platforms:
        raise BusinessException(
            message="没有可用的 AI 平台",
            code=40902,
            status_code=409,
        )
    return platforms


def _to_run_detail(run: MonitorRun) -> RunDetailRead:
    total_tasks = run.total_tasks or run.expected_query_count
    finished = run.succeeded_tasks + run.failed_tasks + run.cancelled_tasks
    progress = (
        Decimal(finished) / Decimal(total_tasks)
        if total_tasks > 0
        else Decimal("0")
    )
    return RunDetailRead.model_validate(run).model_copy(
        update={"progress_rate": progress.quantize(Decimal("0.0001"))}
    )


def _count_tasks_by_status(db: Session, run_id: int) -> Counter[str]:
    rows = db.execute(
        select(QueryTask.status, func.count())
        .where(
            QueryTask.run_id == run_id,
            QueryTask.is_deleted.is_(False),
        )
        .group_by(QueryTask.status)
    ).all()
    return Counter({status: count for status, count in rows})


def _count_valid_answers(db: Session, run_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Answer)
            .join(QueryTask, QueryTask.id == Answer.task_id)
            .where(
                QueryTask.run_id == run_id,
                QueryTask.status == "success",
                QueryTask.is_deleted.is_(False),
                Answer.is_deleted.is_(False),
                func.length(func.trim(Answer.normalized_text)) > 0,
            )
        )
        or 0
    )


def _build_error_summary(db: Session, run_id: int) -> str | None:
    rows = db.execute(
        select(QueryTask.error_code, QueryTask.error_message)
        .where(
            QueryTask.run_id == run_id,
            QueryTask.status == "failed",
            QueryTask.is_deleted.is_(False),
        )
        .order_by(QueryTask.id)
    ).all()
    if not rows:
        return None
    parts: list[str] = []
    for error_code, error_message in rows:
        code = error_code or "unknown"
        message = (error_message or "").strip()
        parts.append(f"{code}: {message}" if message else code)
    return "; ".join(parts)


def _map_collection_status(run_status: str) -> str:
    if run_status == "completed":
        return "completed"
    if run_status == "partial_success":
        return "partial_success"
    if run_status == "failed":
        return "failed"
    if run_status == "cancelled":
        return "cancelled"
    return "running"


def _resolve_natural_terminal_status(counts: Counter[str]) -> str:
    success = counts.get("success", 0)
    failed = counts.get("failed", 0)
    cancelled = counts.get("cancelled", 0)
    if success > 0 and failed == 0 and cancelled == 0:
        return "completed"
    if success == 0 and failed > 0 and cancelled == 0:
        return "failed"
    if success == 0 and failed == 0 and cancelled > 0:
        return "cancelled"
    if success > 0 and failed > 0:
        return "partial_success"
    if success > 0 and cancelled > 0 and failed == 0:
        return "partial_success"
    if success > 0:
        return "partial_success"
    return "failed"


def refresh_run_aggregation(db: Session, run: MonitorRun) -> MonitorRun:
    """根据 QueryTask 终态刷新运行计数与聚合状态。"""
    counts = _count_tasks_by_status(db, run.id)
    success = counts.get("success", 0)
    failed = counts.get("failed", 0)
    cancelled = counts.get("cancelled", 0)
    in_progress = sum(
        counts.get(status, 0) for status in ("pending", "queued", "running")
    )
    total_tasks = run.total_tasks or run.expected_query_count

    run.succeeded_tasks = success
    run.failed_tasks = failed
    run.cancelled_tasks = cancelled
    run.success_query_count = success
    run.failed_query_count = failed
    valid_count = _count_valid_answers(db, run.id)
    run.valid_answer_count = valid_count
    run.data_completeness_rate = (
        (Decimal(valid_count) / Decimal(total_tasks)).quantize(Decimal("0.0001"))
        if total_tasks > 0
        else Decimal("0")
    )
    run.error_summary = _build_error_summary(db, run.id)

    if run.status not in RUN_TERMINAL_STATUSES:
        if in_progress > 0:
            if run.status == "pending":
                run.status = "collecting"
            run.collection_status = "running"
        elif total_tasks > 0 and in_progress == 0:
            now = datetime.now(timezone.utc)
            terminal_status = _resolve_natural_terminal_status(counts)
            run.status = terminal_status
            run.collection_status = _map_collection_status(terminal_status)
            run.completed_at = now
            run.finished_at = now

    db.flush()
    return run


def on_query_task_terminal(db: Session, run_id: int) -> None:
    """QueryTask 进入终态后刷新 Run 计数与聚合状态。"""
    run = run_repo.get_by_id(db, run_id)
    if run is None or run.is_deleted:
        return
    refresh_run_aggregation(db, run)
    db.commit()


def _start_collection(db: Session, run_id: int) -> None:
    from app.geo_monitoring.services import collection as collection_service

    run = get_run(db, run_id)
    now = datetime.now(timezone.utc)
    run.status = "collecting"
    run.collection_status = "running"
    run.started_at = now
    db.commit()
    collection_service.enqueue_run_query_tasks(run_id, db=db)


def create_run(db: Session, payload: RunCreate) -> MonitorRun:
    project = require_active_project(db, payload.project_id)
    prompt_set = _resolve_prompt_set(db, project.id, payload.prompt_set_id)
    prompts = _enabled_prompts(db, prompt_set.id)
    platforms = _resolve_platforms(db, payload.platform_codes)
    platform_codes = [platform.platform_code for platform in platforms]
    task_count = len(prompts) * len(platforms)
    run = MonitorRun(
        run_no=_new_run_no(),
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version=prompt_set.version_no,
        trigger_type="manual",
        status="pending",
        collection_status="pending",
        analysis_status="skipped",
        report_status="skipped",
        platform_codes=platform_codes,
        expected_query_count=task_count,
        total_tasks=task_count,
    )
    try:
        run_repo.add_run(db, run)
        db.flush()
        run_repo.build_query_tasks(db, run, prompts, platforms)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(run)
    _start_collection(db, run.id)
    db.refresh(run)
    return run


def get_run(db: Session, run_id: int) -> MonitorRun:
    run = run_repo.get_by_id(db, run_id)
    if run is None:
        raise BusinessException(message="监测运行不存在", code=40400)
    return run


def get_run_detail(db: Session, run_id: int) -> RunDetailRead:
    run = get_run(db, run_id)
    refresh_run_aggregation(db, run)
    db.commit()
    db.refresh(run)
    return _to_run_detail(run)


def list_runs(
    db: Session,
    *,
    page: int,
    page_size: int,
    project_id: int | None = None,
    status: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> tuple[list[MonitorRun], int]:
    conditions = [MonitorRun.is_deleted.is_(False)]
    if project_id is not None:
        conditions.append(MonitorRun.project_id == project_id)
    if status:
        conditions.append(MonitorRun.status == status)
    if created_after is not None:
        conditions.append(MonitorRun.created_at >= created_after)
    if created_before is not None:
        conditions.append(MonitorRun.created_at <= created_before)
    total = db.execute(
        select(func.count()).select_from(MonitorRun).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(MonitorRun)
            .where(*conditions)
            .order_by(MonitorRun.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def list_query_tasks(
    db: Session,
    *,
    run_id: int,
    page: int,
    page_size: int,
    status: str | None = None,
    platform_code: str | None = None,
) -> tuple[list, int]:
    get_run(db, run_id)
    return run_repo.list_query_tasks(
        db,
        run_id=run_id,
        page=page,
        page_size=page_size,
        status=status,
        platform_code=platform_code,
    )


def cancel_run(db: Session, run_id: int) -> MonitorRun:
    run = get_run(db, run_id)
    if run.status in RUN_TERMINAL_STATUSES:
        refresh_run_aggregation(db, run)
        db.commit()
        db.refresh(run)
        return run

    now = datetime.now(timezone.utc)
    tasks = list(
        db.execute(
            select(QueryTask)
            .where(
                QueryTask.run_id == run_id,
                QueryTask.status.in_(CANCELLABLE_TASK_STATUSES),
                QueryTask.is_deleted.is_(False),
            )
            .with_for_update()
        )
        .scalars()
        .all()
    )
    for task in tasks:
        task.status = "cancelled"
        task.completed_at = now
        task.finished_at = now

    run.status = "cancelled"
    run.collection_status = "cancelled"
    run.completed_at = now
    run.finished_at = now
    refresh_run_aggregation(db, run)
    db.commit()
    db.refresh(run)
    return run


def retry_failed_tasks(db: Session, run_id: int) -> tuple[MonitorRun, int]:
    run = get_run(db, run_id)
    if run.status == "cancelled":
        raise BusinessException(message="已取消的运行不可重试", code=40040)

    failed_tasks = list(
        db.execute(
            select(QueryTask)
            .where(
                QueryTask.run_id == run_id,
                QueryTask.status == "failed",
                QueryTask.is_deleted.is_(False),
            )
            .with_for_update()
        )
        .scalars()
        .all()
    )
    if not failed_tasks:
        refresh_run_aggregation(db, run)
        db.commit()
        db.refresh(run)
        return run, 0

    now = datetime.now(timezone.utc)
    for task in failed_tasks:
        task.attempt_count += 1
        task.status = "pending"
        task.error_code = None
        task.error_message = None
        task.last_error_code = None
        task.last_error_message = None
        task.started_at = None
        task.queued_at = None
        task.completed_at = None
        task.finished_at = None

    run.status = "collecting"
    run.collection_status = "running"
    run.completed_at = None
    run.finished_at = None
    run.error_summary = None
    refresh_run_aggregation(db, run)
    db.commit()

    from app.geo_monitoring.services import collection as collection_service

    collection_service.enqueue_run_query_tasks(run_id, db=db)
    db.refresh(run)
    return run, len(failed_tasks)
