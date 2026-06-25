"""信源引用分析页面级 API。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.geo_monitoring.services import source_analysis as source_analysis_service

router = APIRouter()


@router.get(
    "/projects/{project_id}/source-analysis",
    summary="信源引用分析页面级聚合",
)
def get_source_analysis(
    project_id: int = Path(..., ge=1),
    run_id: int | None = Query(None, ge=1, description="指定运行 ID，默认取最近已分析或已终态 run"),
    platform_codes: list[str] | None = Query(None),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    source_type: str | None = Query(None, description="信源展示类型 code，见 GET /source-types"),
    keyword: str | None = Query(None, max_length=200, description="按域名或站点名模糊搜索"),
    metric: str = Query("links", pattern="^(links|rate)$", description="矩阵展示口径：links 或 rate"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    data = source_analysis_service.get_source_analysis(
        db,
        project_id,
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        source_type=source_type,
        keyword=keyword,
        metric=metric,
        page=page,
        page_size=page_size,
    )
    return success(data)
