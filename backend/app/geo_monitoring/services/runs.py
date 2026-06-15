"""监测运行与查询任务扇出服务。"""

from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import (
    AIPlatform,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.schemas import RunCreate
from app.geo_monitoring.services.projects import require_active_project


def _new_run_no() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"RUN-{timestamp}-{uuid4().hex[:8].upper()}"


def _resolve_prompt_set(
    db: Session, project_id: int, prompt_set_id: int | None
) -> PromptSet:
    conditions = [
        PromptSet.project_id == project_id,
        PromptSet.status == "active",
        PromptSet.is_deleted.is_(False),
    ]
    if prompt_set_id is not None:
        conditions.append(PromptSet.id == prompt_set_id)
    prompt_set = db.execute(select(PromptSet).where(*conditions)).scalar_one_or_none()
    if prompt_set is None:
        raise BusinessException(message="项目没有可用的激活提示词集", code=40030)
    return prompt_set


def _enabled_prompts(db: Session, prompt_set_id: int) -> list[Prompt]:
    prompts = list(
        db.execute(
            select(Prompt)
            .where(
                Prompt.prompt_set_id == prompt_set_id,
                Prompt.enabled.is_(True),
                Prompt.is_deleted.is_(False),
            )
            .order_by(Prompt.sort_order, Prompt.id)
        )
        .scalars()
        .all()
    )
    if not prompts:
        raise BusinessException(message="激活提示词集没有可用提示词", code=40032)
    return prompts


def _resolve_platforms(
    db: Session, platform_codes: list[str] | None
) -> list[AIPlatform]:
    conditions = [AIPlatform.is_deleted.is_(False)]
    if platform_codes is not None:
        conditions.append(AIPlatform.platform_code.in_(platform_codes))
    rows = list(db.execute(select(AIPlatform).where(*conditions)).scalars().all())
    by_code = {platform.platform_code: platform for platform in rows}

    if platform_codes is None:
        platforms = sorted(
            (platform for platform in rows if platform.enabled), key=lambda item: item.id
        )
    else:
        platforms = []
        for code in platform_codes:
            platform = by_code.get(code)
            if platform is None or not platform.enabled:
                raise BusinessException(message=f"AI 平台不可用: {code}", code=40031)
            platforms.append(platform)
    if not platforms:
        raise BusinessException(message="没有可用的 AI 平台", code=40031)
    return platforms


def _build_query_tasks(
    db: Session,
    run: MonitorRun,
    prompts: list[Prompt],
    platforms: list[AIPlatform],
) -> None:
    for prompt in prompts:
        for platform in platforms:
            key_source = f"{run.run_no}:{prompt.id}:{platform.platform_code}"
            db.add(
                QueryTask(
                    run_id=run.id,
                    prompt_id=prompt.id,
                    platform_code=platform.platform_code,
                    idempotency_key=sha256(key_source.encode("utf-8")).hexdigest(),
                    status="pending",
                    request_json={
                        "prompt_code": prompt.prompt_code,
                        "prompt_text": prompt.prompt_text,
                        "prompt_type": prompt.prompt_type,
                        "scene_tag": prompt.scene_tag,
                        "contains_brand": prompt.contains_brand,
                        "content_hash": prompt.content_hash,
                        "prompt_set_version": run.prompt_set_version,
                    },
                )
            )


def create_run(db: Session, payload: RunCreate) -> MonitorRun:
    project = require_active_project(db, payload.project_id)
    prompt_set = _resolve_prompt_set(db, project.id, payload.prompt_set_id)
    prompts = _enabled_prompts(db, prompt_set.id)
    platforms = _resolve_platforms(db, payload.platform_codes)
    platform_codes = [platform.platform_code for platform in platforms]
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
        expected_query_count=len(prompts) * len(platforms),
    )
    try:
        db.add(run)
        db.flush()
        _build_query_tasks(db, run, prompts, platforms)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(run)
    return run


def get_run(db: Session, run_id: int) -> MonitorRun:
    run = db.execute(
        select(MonitorRun).where(
            MonitorRun.id == run_id,
            MonitorRun.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if run is None:
        raise BusinessException(message="监测运行不存在", code=40400)
    return run


def list_runs(
    db: Session,
    *,
    page: int,
    page_size: int,
    project_id: int | None = None,
    status: str | None = None,
) -> tuple[list[MonitorRun], int]:
    conditions = [MonitorRun.is_deleted.is_(False)]
    if project_id is not None:
        conditions.append(MonitorRun.project_id == project_id)
    if status:
        conditions.append(MonitorRun.status == status)
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
) -> tuple[list[QueryTask], int]:
    get_run(db, run_id)
    conditions = [QueryTask.run_id == run_id, QueryTask.is_deleted.is_(False)]
    if status:
        conditions.append(QueryTask.status == status)
    if platform_code:
        conditions.append(QueryTask.platform_code == platform_code)
    total = db.execute(
        select(func.count()).select_from(QueryTask).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(QueryTask)
            .where(*conditions)
            .order_by(QueryTask.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total
