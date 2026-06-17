"""项目看板与趋势 API。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.models import MonitorRun
from app.geo_monitoring.services.analysis import MetricSnapshot, PlatformAnalysis
from app.geo_monitoring.services.projects import require_active_project

router = APIRouter()


def _run_summary(run: MonitorRun) -> dict:
    return {
        "run_id": run.id,
        "run_no": run.run_no,
        "status": run.status,
        "collection_status": run.collection_status,
        "analysis_status": run.analysis_status,
        "valid_answer_count": run.valid_answer_count,
        "data_completeness_rate": str(run.data_completeness_rate),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _platform_analysis_payload(row: PlatformAnalysis) -> dict:
    return {
        "platform_code": row.platform_code,
        "status": row.status,
        "valid_answer_count": row.valid_answer_count,
        "brand_mention_rate": str(row.brand_mention_rate),
        "brand_first_rate": str(row.brand_first_rate),
        "top_competitors": row.top_competitors,
        "top_sources": row.top_sources,
        "summary_json": row.summary_json,
        "improvement_json": row.improvement_json,
    }


@router.get("/projects/{project_id}/dashboard", summary="获取项目最新分析汇总")
def get_project_dashboard(
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    require_active_project(db, project_id)
    latest_run = db.execute(
        select(MonitorRun)
        .where(
            MonitorRun.project_id == project_id,
            MonitorRun.is_deleted.is_(False),
            MonitorRun.analysis_status.in_(
                {"completed", "partial_success", "skipped", "running", "pending"}
            ),
        )
        .order_by(MonitorRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    platforms: list[dict] = []
    if latest_run is not None:
        rows = list(
            db.execute(
                select(PlatformAnalysis).where(
                    PlatformAnalysis.run_id == latest_run.id,
                    PlatformAnalysis.is_deleted.is_(False),
                )
            )
            .scalars()
            .all()
        )
        platforms = [_platform_analysis_payload(row) for row in rows]

    return success(
        {
            "project_id": project_id,
            "latest_run": _run_summary(latest_run) if latest_run else None,
            "platforms": platforms,
        }
    )


@router.get("/projects/{project_id}/trends", summary="按指标、平台和时间范围查询趋势")
def list_project_trends(
    project_id: int = Path(..., ge=1),
    metric_code: str = Query(..., min_length=1, max_length=100),
    platform_code: str | None = Query(None, max_length=32),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    require_active_project(db, project_id)
    conditions = [
        MetricSnapshot.project_id == project_id,
        MetricSnapshot.metric_code == metric_code,
        MetricSnapshot.is_deleted.is_(False),
    ]
    if platform_code:
        conditions.append(MetricSnapshot.platform_code == platform_code)
    if start_at is not None:
        conditions.append(MetricSnapshot.snapshot_at >= start_at)
    if end_at is not None:
        conditions.append(MetricSnapshot.snapshot_at <= end_at)

    total = db.scalar(select(func.count()).select_from(MetricSnapshot).where(*conditions)) or 0
    items = list(
        db.execute(
            select(MetricSnapshot)
            .where(*conditions)
            .order_by(MetricSnapshot.snapshot_at.desc(), MetricSnapshot.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    data = [
        {
            "run_id": row.run_id,
            "platform_code": row.platform_code,
            "metric_code": row.metric_code,
            "numerator": str(row.numerator) if row.numerator is not None else None,
            "denominator": str(row.denominator) if row.denominator is not None else None,
            "metric_value": str(row.metric_value) if row.metric_value is not None else None,
            "prompt_set_version": row.prompt_set_version,
            "snapshot_at": row.snapshot_at.isoformat(),
            "completeness_rate": str(row.completeness_rate),
        }
        for row in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)
