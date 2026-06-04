"""内容分类 API Router。

路径前缀由 app/api/router.py include 时指定（最终为 /api/content-categories）。
所有接口返回统一响应格式：{"code": 0, "message": "success", "data": ...}
"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.schemas.content_category import (
    ContentCategoryCreate,
    ContentCategoryOut,
    ContentCategoryUpdate,
)
from app.services import content_category as content_category_service

router = APIRouter(prefix="/content-categories", tags=["内容分类"])


@router.get("", summary="分页查询内容分类")
def list_content_categories(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    group_name: str | None = Query(None, description="按分组名称模糊搜索"),
    db: Session = Depends(get_db),
) -> dict:
    items, total = content_category_service.list_content_categories(
        db,
        page=page,
        page_size=page_size,
        group_name=group_name,
    )
    data = [
        ContentCategoryOut.model_validate(item).model_dump(mode="json")
        for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("", summary="新增内容分类")
def create_content_category(
    payload: ContentCategoryCreate,
    db: Session = Depends(get_db),
) -> dict:
    category = content_category_service.create_content_category(db, payload)
    return success(ContentCategoryOut.model_validate(category).model_dump(mode="json"))


@router.get("/{category_id}", summary="获取内容分类详情")
def get_content_category(
    category_id: int = Path(..., ge=1, description="内容分类 ID"),
    db: Session = Depends(get_db),
) -> dict:
    category = content_category_service.get_content_category(db, category_id)
    return success(ContentCategoryOut.model_validate(category).model_dump(mode="json"))


@router.put("/{category_id}", summary="更新内容分类")
def update_content_category(
    payload: ContentCategoryUpdate,
    category_id: int = Path(..., ge=1, description="内容分类 ID"),
    db: Session = Depends(get_db),
) -> dict:
    category = content_category_service.update_content_category(
        db, category_id, payload
    )
    return success(ContentCategoryOut.model_validate(category).model_dump(mode="json"))


@router.delete("/{category_id}", summary="删除内容分类")
def delete_content_category(
    category_id: int = Path(..., ge=1, description="内容分类 ID"),
    db: Session = Depends(get_db),
) -> dict:
    content_category_service.delete_content_category(db, category_id)
    return success({"id": category_id})
