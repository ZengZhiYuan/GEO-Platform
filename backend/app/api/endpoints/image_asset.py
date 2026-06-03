"""画像图库图片 API Router。

路径前缀由 app/api/router.py include 时指定（最终为 /api/image-assets）。
所有接口返回统一响应格式：{"code": 0, "message": "success", "data": ...}
"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.schemas.image_asset import (
    ImageAssetCreate,
    ImageAssetOut,
    ImageAssetUpdate,
)
from app.services import image_asset as image_asset_service

router = APIRouter(prefix="/image-assets", tags=["画像图库图片"])


@router.get("", summary="分页查询图片")
def list_image_assets(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    category_id: int | None = Query(None, ge=1, description="按图库分类 ID 筛选"),
    db: Session = Depends(get_db),
) -> dict:
    items, total = image_asset_service.list_image_assets(
        db,
        page=page,
        page_size=page_size,
        category_id=category_id,
    )
    data = [
        ImageAssetOut.model_validate(item).model_dump(mode="json")
        for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("", summary="新增图片")
def create_image_asset(
    payload: ImageAssetCreate,
    db: Session = Depends(get_db),
) -> dict:
    asset = image_asset_service.create_image_asset(db, payload)
    return success(ImageAssetOut.model_validate(asset).model_dump(mode="json"))


@router.get("/{asset_id}", summary="获取图片详情")
def get_image_asset(
    asset_id: int = Path(..., ge=1, description="图片 ID"),
    db: Session = Depends(get_db),
) -> dict:
    asset = image_asset_service.get_image_asset(db, asset_id)
    return success(ImageAssetOut.model_validate(asset).model_dump(mode="json"))


@router.put("/{asset_id}", summary="更新图片")
def update_image_asset(
    payload: ImageAssetUpdate,
    asset_id: int = Path(..., ge=1, description="图片 ID"),
    db: Session = Depends(get_db),
) -> dict:
    asset = image_asset_service.update_image_asset(db, asset_id, payload)
    return success(ImageAssetOut.model_validate(asset).model_dump(mode="json"))


@router.delete("/{asset_id}", summary="删除图片")
def delete_image_asset(
    asset_id: int = Path(..., ge=1, description="图片 ID"),
    db: Session = Depends(get_db),
) -> dict:
    image_asset_service.delete_image_asset(db, asset_id)
    return success({"id": asset_id})
