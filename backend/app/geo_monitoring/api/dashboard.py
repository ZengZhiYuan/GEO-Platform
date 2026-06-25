"""项目看板与趋势 API。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.services.analysis import MetricSnapshot
from app.geo_monitoring.services.dashboard import (
    build_dashboard_overview,
    build_project_dashboard,
)
from app.geo_monitoring.services.projects import require_active_project

router = APIRouter()


@router.get("/projects/{project_id}/dashboard", summary="获取项目最新分析汇总")
def get_project_dashboard(
    project_id: int = Path(..., ge=1),
    run_id: int | None = Query(None, ge=1, description="指定运行 ID，默认取最近已分析或已采集运行"),
    db: Session = Depends(get_db),
) -> dict:
    payload = build_project_dashboard(db, project_id, run_id=run_id)
    return success(payload)


@router.get(
    "/projects/{project_id}/dashboard/overview",
    summary="数据大盘页面级总览",
)
def get_project_dashboard_overview(
    project_id: int = Path(..., ge=1),
    run_id: int | None = Query(None, ge=1, description="指定运行 ID，默认取最近已分析或已终态 run"),
    platform_codes: list[str] | None = Query(None),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    payload = build_dashboard_overview(
        db,
        project_id,
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
    )
    return success(payload)


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
