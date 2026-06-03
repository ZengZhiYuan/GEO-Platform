"""画像图库分类 API Router。

路径前缀由 app/api/router.py include 时指定（最终为 /api/image-categories）。
所有接口返回统一响应格式：{"code": 0, "message": "success", "data": ...}
"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.schemas.image_category import (
    ImageCategoryCreate,
    ImageCategoryOut,
    ImageCategoryUpdate,
)
from app.services import image_category as image_category_service

router = APIRouter(prefix="/image-categories", tags=["画像图库分类"])


@router.get("", summary="分页查询图库分类")
def list_image_categories(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    category_name: str | None = Query(None, description="按分类名称模糊搜索"),
    db: Session = Depends(get_db),
) -> dict:
    items, total = image_category_service.list_image_categories(
        db,
        page=page,
        page_size=page_size,
        category_name=category_name,
    )
    data = [
        ImageCategoryOut.model_validate(item).model_dump(mode="json")
        for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("", summary="新增图库分类")
def create_image_category(
    payload: ImageCategoryCreate,
    db: Session = Depends(get_db),
) -> dict:
    category = image_category_service.create_image_category(db, payload)
    return success(
        ImageCategoryOut.model_validate(category).model_dump(mode="json")
    )


@router.get("/{category_id}", summary="获取图库分类详情")
def get_image_category(
    category_id: int = Path(..., ge=1, description="图库分类 ID"),
    db: Session = Depends(get_db),
) -> dict:
    category = image_category_service.get_image_category(db, category_id)
    return success(
        ImageCategoryOut.model_validate(category).model_dump(mode="json")
    )


@router.put("/{category_id}", summary="更新图库分类")
def update_image_category(
    payload: ImageCategoryUpdate,
    category_id: int = Path(..., ge=1, description="图库分类 ID"),
    db: Session = Depends(get_db),
) -> dict:
    category = image_category_service.update_image_category(
        db, category_id, payload
    )
    return success(
        ImageCategoryOut.model_validate(category).model_dump(mode="json")
    )


@router.delete("/{category_id}", summary="删除图库分类")
def delete_image_category(
    category_id: int = Path(..., ge=1, description="图库分类 ID"),
    db: Session = Depends(get_db),
) -> dict:
    image_category_service.delete_image_category(db, category_id)
    return success({"id": category_id})
