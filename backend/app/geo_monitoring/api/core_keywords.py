"""核心词 API。"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import CoreKeywordCreate, CoreKeywordOut, CoreKeywordUpdate
from app.geo_monitoring.services import core_keywords as core_keyword_service

router = APIRouter()


@router.get("/projects/{project_id}/core-keywords", summary="分页查询项目核心词")
def list_core_keywords(
    project_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    enabled: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = core_keyword_service.list_core_keywords(
        db,
        project_id=project_id,
        page=page,
        page_size=page_size,
        enabled=enabled,
    )
    data = [
        CoreKeywordOut.model_validate(item).model_dump(mode="json") for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/projects/{project_id}/core-keywords", summary="创建项目核心词")
def create_core_keyword(
    payload: CoreKeywordCreate,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    keyword = core_keyword_service.create_core_keyword(db, project_id, payload)
    return success(CoreKeywordOut.model_validate(keyword).model_dump(mode="json"))


@router.put("/core-keywords/{keyword_id}", summary="更新核心词")
def update_core_keyword(
    payload: CoreKeywordUpdate,
    keyword_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    keyword = core_keyword_service.update_core_keyword(db, keyword_id, payload)
    return success(CoreKeywordOut.model_validate(keyword).model_dump(mode="json"))


@router.delete("/core-keywords/{keyword_id}", summary="删除核心词")
def delete_core_keyword(
    keyword_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    core_keyword_service.delete_core_keyword(db, keyword_id)
    return success({"id": keyword_id})
