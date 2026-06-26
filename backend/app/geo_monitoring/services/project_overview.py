"""项目概览与删除检查服务。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import (
    AIPlatform,
    Brand,
    BrandAlias,
    MonitorProject,
    MonitorRun,
    MonitorSchedule,
    Prompt,
    PromptSet,
)
from app.geo_monitoring.repositories import projects as project_repo
from app.geo_monitoring.reports.storage import GeoReport
from app.geo_monitoring.schemas import (
    ProjectDeleteCheckRead,
    ProjectOptionRead,
    ProjectOverviewItemRead,
    ProjectOverviewLatestRunRead,
)
from app.geo_monitoring.services.metadata import _resolve_base_platform
from app.geo_monitoring.services.projects import get_project


def _build_platform_base_map(db: Session) -> dict[str, str]:
    platforms = list(
        db.execute(
            select(AIPlatform).where(AIPlatform.is_deleted.is_(False))
        )
        .scalars()
        .all()
    )
    return {
        platform.platform_code: _resolve_base_platform(platform)
        for platform in platforms
    }


def _count_unique_base_platforms(
    platform_codes: list[str],
    base_map: dict[str, str],
) -> int:
    bases = {
        base_map.get(code, code)
        for code in platform_codes
        if code
    }
    return len(bases)


def _load_target_brands(db: Session, project_ids: list[int]) -> dict[int, Brand]:
    if not project_ids:
        return {}
    rows = list(
        db.execute(
            select(Brand).where(
                Brand.project_id.in_(project_ids),
                Brand.brand_type == "target",
                Brand.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )
    return {row.project_id: row for row in rows}


def _load_competitor_counts(db: Session, project_ids: list[int]) -> dict[int, int]:
    if not project_ids:
        return {}
    rows = db.execute(
        select(Brand.project_id, func.count())
        .where(
            Brand.project_id.in_(project_ids),
            Brand.brand_type == "competitor",
            Brand.is_deleted.is_(False),
        )
        .group_by(Brand.project_id)
    ).all()
    return {project_id: count for project_id, count in rows}


def _load_brand_word_counts(
    db: Session,
    target_brands: dict[int, Brand],
) -> dict[int, int]:
    brand_ids = [brand.id for brand in target_brands.values()]
    if not brand_ids:
        return {}
    rows = db.execute(
        select(BrandAlias.brand_id, func.count())
        .where(
            BrandAlias.brand_id.in_(brand_ids),
            BrandAlias.is_deleted.is_(False),
            BrandAlias.enabled.is_(True),
        )
        .group_by(BrandAlias.brand_id)
    ).all()
    alias_counts = {brand_id: count for brand_id, count in rows}
    project_counts: dict[int, int] = {}
    for project_id, brand in target_brands.items():
        project_counts[project_id] = alias_counts.get(brand.id, 0)
    return project_counts


def _load_question_counts(db: Session, project_ids: list[int]) -> dict[int, int]:
    if not project_ids:
        return {}
    active_sets = list(
        db.execute(
            select(PromptSet).where(
                PromptSet.project_id.in_(project_ids),
                PromptSet.status == "active",
                PromptSet.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )
    if not active_sets:
        return {}
    prompt_set_ids = [item.id for item in active_sets]
    rows = db.execute(
        select(Prompt.prompt_set_id, func.count())
        .where(
            Prompt.prompt_set_id.in_(prompt_set_ids),
            Prompt.is_deleted.is_(False),
            Prompt.enabled.is_(True),
        )
        .group_by(Prompt.prompt_set_id)
    ).all()
    counts_by_set = {prompt_set_id: count for prompt_set_id, count in rows}
    project_counts: dict[int, int] = {}
    for prompt_set in active_sets:
        project_counts[prompt_set.project_id] = counts_by_set.get(prompt_set.id, 0)
    return project_counts


def _load_latest_runs(db: Session, project_ids: list[int]) -> dict[int, MonitorRun]:
    if not project_ids:
        return {}
    latest_ids = [
        run_id
        for (run_id,) in db.execute(
            select(func.max(MonitorRun.id))
            .where(
                MonitorRun.project_id.in_(project_ids),
                MonitorRun.is_deleted.is_(False),
            )
            .group_by(MonitorRun.project_id)
        ).all()
        if run_id is not None
    ]
    if not latest_ids:
        return {}
    rows = list(
        db.execute(select(MonitorRun).where(MonitorRun.id.in_(latest_ids)))
        .scalars()
        .all()
    )
    return {run.project_id: run for run in rows}


def list_project_options(db: Session) -> list[ProjectOptionRead]:
    items = project_repo.list_all_projects(db)
    return [
        ProjectOptionRead(
            id=project.id,
            project_name=project.project_name,
            status=project.status,
            monitoring_paused=project.monitoring_paused,
        )
        for project in items
    ]


def list_project_overview(
    db: Session,
    *,
    page: int,
    page_size: int,
    project_name: str | None = None,
    status: str | None = None,
) -> tuple[list[ProjectOverviewItemRead], int]:
    projects, total = project_repo.list_projects(
        db,
        page=page,
        page_size=page_size,
        project_name=project_name,
        status=status,
    )
    if not projects:
        return [], total

    project_ids = [project.id for project in projects]
    base_map = _build_platform_base_map(db)
    target_brands = _load_target_brands(db, project_ids)
    competitor_counts = _load_competitor_counts(db, project_ids)
    brand_word_counts = _load_brand_word_counts(db, target_brands)
    question_counts = _load_question_counts(db, project_ids)
    latest_runs = _load_latest_runs(db, project_ids)

    items: list[ProjectOverviewItemRead] = []
    for project in projects:
        selected_codes = list(project.default_platform_codes or [])
        latest_run = latest_runs.get(project.id)
        target_brand = target_brands.get(project.id)
        items.append(
            ProjectOverviewItemRead(
                id=project.id,
                project_name=project.project_name,
                industry=project.industry,
                status=project.status,
                monitoring_paused=project.monitoring_paused,
                target_brand_name=target_brand.brand_name if target_brand else None,
                brand_word_count=brand_word_counts.get(project.id, 0),
                competitor_count=competitor_counts.get(project.id, 0),
                question_count=question_counts.get(project.id, 0),
                platform_count=_count_unique_base_platforms(selected_codes, base_map),
                endpoint_count=len(selected_codes),
                selected_platform_codes=selected_codes,
                latest_run=(
                    ProjectOverviewLatestRunRead(
                        run_id=latest_run.id,
                        run_no=latest_run.run_no,
                        status=latest_run.status,
                        collection_status=latest_run.collection_status,
                        analysis_status=latest_run.analysis_status,
                        completed_at=latest_run.completed_at,
                    )
                    if latest_run is not None
                    else None
                ),
                updated_at=project.updated_at,
            )
        )
    return items, total


def get_delete_check(db: Session, project_id: int) -> ProjectDeleteCheckRead:
    get_project(db, project_id)
    run_count = db.scalar(
        select(func.count())
        .select_from(MonitorRun)
        .where(
            MonitorRun.project_id == project_id,
            MonitorRun.is_deleted.is_(False),
        )
    ) or 0
    report_count = db.scalar(
        select(func.count())
        .select_from(GeoReport)
        .where(
            GeoReport.project_id == project_id,
            GeoReport.is_deleted.is_(False),
        )
    ) or 0
    schedule_count = db.scalar(
        select(func.count())
        .select_from(MonitorSchedule)
        .where(
            MonitorSchedule.project_id == project_id,
            MonitorSchedule.is_deleted.is_(False),
        )
    ) or 0

    blocking_reasons: list[str] = []
    if run_count > 0:
        blocking_reasons.append(f"项目已有 {run_count} 次监测运行")

    return ProjectDeleteCheckRead(
        project_id=project_id,
        run_count=run_count,
        report_count=report_count,
        schedule_count=schedule_count,
        can_delete=run_count == 0,
        blocking_reasons=blocking_reasons,
    )
