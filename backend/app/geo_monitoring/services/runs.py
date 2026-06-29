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
from app.geo_monitoring.services.projects import require_active_project, require_monitoring_not_paused

RUN_TERMINAL_STATUSES = frozenset(
    {"completed", "partial_success", "failed", "cancelled"}
)
CANCELLABLE_TASK_STATUSES = frozenset({"pending", "queued", "running"})


# 读取采集任务最大尝试次数配置
def _collection_max_attempts() -> int:
    from app.geo_monitoring.services.collection import get_runtime

    return get_runtime().settings.COLLECTION_MAX_ATTEMPTS


# 生成带时间戳与随机后缀的运行编号
def _new_run_no() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"RUN-{timestamp}-{uuid4().hex[:8].upper()}"


# 解析指定或项目内 active 提示词集
def _resolve_prompt_set(db: Session, project_id: int, prompt_set_id: int | None):
    prompt_set = prompt_repo.resolve_active_prompt_set(
        db, project_id, prompt_set_id
    )
    if prompt_set is None:
        raise BusinessException(message="项目没有可用的激活提示词集", code=40030)
    return prompt_set


# 加载提示词集中已启用的提示词，空集则拒绝
def _enabled_prompts(db: Session, prompt_set_id: int):
    prompts = prompt_repo.list_enabled_prompts(db, prompt_set_id)
    if not prompts:
        raise BusinessException(
            message="激活提示词集没有可用提示词",
            code=40901,
            status_code=409,
        )
    return prompts


# 判断平台是否属于当前采集源
def _platform_matches_collection_source(platform, collection_source: str) -> bool:
    adapter_type = platform.adapter_type
    if collection_source == "aidso":
        return adapter_type == "aidso"
    if collection_source == "molizhishu":
        return adapter_type == "molizhishu"
    return adapter_type not in {"aidso", "molizhishu"}


# 解析并校验可用的 AI 平台列表
def _resolve_platforms(
    db: Session,
    platform_codes: list[str] | None,
    *,
    collection_source: str = "official",
):
    rows = platform_repo.list_candidates(db, platform_codes)
    by_code = {platform.platform_code: platform for platform in rows}

    if platform_codes is None:
        # 未指定时取全部已启用平台
        platforms = sorted(
            (
                platform
                for platform in rows
                if platform.enabled
                and _platform_matches_collection_source(platform, collection_source)
            ),
            key=lambda item: item.id,
        )
    else:
        # 按请求顺序校验每个平台可用
        platforms = []
        for code in platform_codes:
            platform = by_code.get(code)
            if (
                platform is None
                or not platform.enabled
                or not _platform_matches_collection_source(platform, collection_source)
            ):
                raise BusinessException(message=f"AI 平台不可用: {code}", code=40031)
            platforms.append(platform)
    if not platforms:
        raise BusinessException(
            message="没有可用的 AI 平台",
            code=40902,
            status_code=409,
        )
    return platforms


def _validate_provider_mode_for_resolved_platforms(
    payload: RunCreate, resolved_platform_codes: list[str]
) -> None:
    if not payload.provider_mode_by_platform:
        return
    outside = set(payload.provider_mode_by_platform) - set(resolved_platform_codes)
    if outside:
        raise BusinessException(
            message="provider_mode_by_platform 只能配置本次 platform_codes 内的平台",
            code=422,
        )


def prepare_run_create(db: Session, payload: RunCreate):
    """校验并解析创建运行所需的项目、问题集、提示词与平台，不落库。"""
    project = require_active_project(db, payload.project_id)
    require_monitoring_not_paused(project)
    prompt_set = _resolve_prompt_set(db, project.id, payload.prompt_set_id)
    prompts = _enabled_prompts(db, prompt_set.id)
    platform_codes = payload.platform_codes
    if platform_codes is None and project.default_platform_codes:
        platform_codes = list(project.default_platform_codes)
    platforms = _resolve_platforms(
        db,
        platform_codes,
        collection_source=payload.collection_source.value,
    )
    resolved_platform_codes = [platform.platform_code for platform in platforms]
    _validate_provider_mode_for_resolved_platforms(payload, resolved_platform_codes)
    return project, prompt_set, prompts, platforms, resolved_platform_codes


# 将 MonitorRun 转为含进度率的详情 DTO
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


# 按状态统计某次运行下的 QueryTask 数量
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


# 统计某次运行下非空有效答案数量
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


# 汇总失败任务的错误码与消息为单行摘要
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


# 将运行终态映射为采集阶段状态
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


# 根据各终态任务数量推断运行自然终态
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

    # 同步任务计数与有效答案完整率
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

    # 非终态运行：采集中或全部任务完成后写入终态
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
    previous_status = run.status
    refresh_run_aggregation(db, run)
    db.commit()
    # 运行首次进入终态时尝试入队分析任务
    if run.status in RUN_TERMINAL_STATUSES and previous_status not in RUN_TERMINAL_STATUSES:
        from app.worker.actors.analysis import maybe_enqueue_run_analysis

        maybe_enqueue_run_analysis(run_id, db=db)


# 将运行标记为采集中并入队全部 QueryTask
def _start_collection(db: Session, run_id: int) -> None:
    from app.geo_monitoring.services import collection as collection_service

    run = get_run(db, run_id)
    now = datetime.now(timezone.utc)
    run.status = "collecting"
    run.collection_status = "running"
    run.started_at = now
    db.commit()
    collection_service.enqueue_run_query_tasks(run_id, db=db)


# 创建监测运行、扇出 QueryTask 并启动采集
def create_run(db: Session, payload: RunCreate) -> MonitorRun:
    project, prompt_set, prompts, platforms, platform_codes = prepare_run_create(
        db, payload
    )
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
        collection_source=payload.collection_source.value,
        aidso_thinking_enabled_by_platform={},
        provider_mode_by_platform=payload.provider_mode_by_platform,
        provider_screenshot=payload.provider_screenshot,
        region_code=payload.region_code,
        provider_callback_url=payload.provider_callback_url,
        platform_codes=platform_codes,
        expected_query_count=task_count,
        total_tasks=task_count,
    )
    try:
        run_repo.add_run(db, run)
        db.flush()
        # 按提示词 × 平台组合生成查询子任务
        run_repo.build_query_tasks(
            db,
            run,
            prompts,
            platforms,
            max_attempts=_collection_max_attempts(),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(run)
    _start_collection(db, run.id)
    db.refresh(run)
    return run


# 按 ID 查询监测运行，不存在则抛业务异常
def get_run(db: Session, run_id: int) -> MonitorRun:
    run = run_repo.get_by_id(db, run_id)
    if run is None:
        raise BusinessException(message="监测运行不存在", code=40400)
    return run


# 获取运行详情并刷新最新聚合状态
def get_run_detail(db: Session, run_id: int) -> RunDetailRead:
    run = get_run(db, run_id)
    refresh_run_aggregation(db, run)
    db.commit()
    db.refresh(run)
    return _to_run_detail(run)


# 分页列出监测运行，支持项目与状态筛选
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


# 分页列出某次运行下的 QueryTask
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


# 取消运行并将可取消任务标记为 cancelled
def cancel_run(db: Session, run_id: int) -> MonitorRun:
    run = get_run(db, run_id)
    if run.status in RUN_TERMINAL_STATUSES:
        refresh_run_aggregation(db, run)
        db.commit()
        db.refresh(run)
        return run

    now = datetime.now(timezone.utc)
    # 锁定并取消所有 pending/queued/running 任务
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
    db.flush()
    refresh_run_aggregation(db, run)
    db.commit()
    db.refresh(run)
    return run


# 重置失败任务为 pending 并重新入队采集
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

    # 清空错误信息并将失败任务重置为 pending
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
    db.flush()
    refresh_run_aggregation(db, run)
    db.commit()

    from app.geo_monitoring.services import collection as collection_service

    collection_service.enqueue_run_query_tasks(run_id, db=db)
    db.refresh(run)
    return run, len(failed_tasks)
