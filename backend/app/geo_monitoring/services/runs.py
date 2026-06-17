"""监测运行与查询任务扇出服务。"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import MonitorRun
from app.geo_monitoring.repositories import platforms as platform_repo
from app.geo_monitoring.repositories import prompts as prompt_repo
from app.geo_monitoring.repositories import runs as run_repo
from app.geo_monitoring.schemas import RunCreate, RunDetailRead
from app.geo_monitoring.services.projects import require_active_project


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
    return run


def get_run(db: Session, run_id: int) -> MonitorRun:
    run = run_repo.get_by_id(db, run_id)
    if run is None:
        raise BusinessException(message="监测运行不存在", code=40400)
    return run


def get_run_detail(db: Session, run_id: int) -> RunDetailRead:
    return _to_run_detail(get_run(db, run_id))


def list_runs(
    db: Session,
    *,
    page: int,
    page_size: int,
    project_id: int | None = None,
    status: str | None = None,
) -> tuple[list[MonitorRun], int]:
    return run_repo.list_runs(
        db,
        page=page,
        page_size=page_size,
        project_id=project_id,
        status=status,
    )


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
