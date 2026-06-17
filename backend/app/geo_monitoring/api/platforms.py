"""AI 平台 API。"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import AIPlatformOut, AIPlatformUpdate
from app.geo_monitoring.services import platforms as platform_service

router = APIRouter()


@router.get("/platforms", summary="分页查询 AI 平台")
def list_platforms(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    enabled: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = platform_service.list_platforms(
        db, page=page, page_size=page_size, enabled=enabled
    )
    data = [AIPlatformOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.put("/platforms/{platform_code}", summary="更新 AI 平台配置")
def update_platform(
    payload: AIPlatformUpdate,
    platform_code: str = Path(..., min_length=1, max_length=32),
    db: Session = Depends(get_db),
) -> dict:
    platform = platform_service.update_platform(db, platform_code, payload)
    return success(AIPlatformOut.model_validate(platform).model_dump(mode="json"))


@router.get("/platforms/{platform_code}", summary="获取 AI 平台配置")
def get_platform(
    platform_code: str = Path(..., min_length=1, max_length=32),
    db: Session = Depends(get_db),
) -> dict:
    platform = platform_service.get_platform(db, platform_code)
    return success(AIPlatformOut.model_validate(platform).model_dump(mode="json"))
