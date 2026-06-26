"""竞品分析页面级 API。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.geo_monitoring.services import competitor_analysis as competitor_analysis_service

router = APIRouter()


@router.get(
    "/projects/{project_id}/competitor-analysis",
    summary="竞品分析页面级聚合",
)
def get_competitor_analysis(
    project_id: int = Path(..., ge=1),
    run_id: int | None = Query(None, ge=1, description="指定运行 ID，默认取最近已分析或已终态 run"),
    platform_codes: list[str] | None = Query(None),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    brand_scope: str = Query(
        "top5",
        pattern="^(top5|all)$",
        description="趋势品牌范围；P0 趋势返回空数组，P1 起按此参数裁剪",
    ),
    db: Session = Depends(get_db),
) -> dict:
    data = competitor_analysis_service.get_competitor_analysis(
        db,
        project_id,
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        brand_scope=brand_scope,
    )
    return success(data)
