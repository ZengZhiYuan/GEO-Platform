"""平台端元数据与基础字典 API。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.geo_monitoring.services import metadata as metadata_service

router = APIRouter()


@router.get("/platform-endpoints", summary="获取平台端元数据分组")
def list_platform_endpoints(
    enabled: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    data = metadata_service.list_platform_endpoints(db, enabled=enabled)
    return success(data)


@router.get("/prompt-types", summary="获取 Prompt 意图类型字典")
def list_prompt_types() -> dict:
    return success(metadata_service.list_prompt_types())


@router.get("/source-types", summary="获取信源类型展示字典")
def list_source_types() -> dict:
    return success(metadata_service.list_source_types())
