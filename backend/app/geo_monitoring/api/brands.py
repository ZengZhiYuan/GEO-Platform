"""品牌 API。"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.schemas import (
    BrandAliasCreate,
    BrandAliasOut,
    BrandAliasUpdate,
    BrandCreate,
    BrandOut,
    BrandType,
    BrandUpdate,
    EntityStatus,
)
from app.geo_monitoring.services import brands as brand_service

router = APIRouter()


@router.get("/projects/{project_id}/brands", summary="分页查询项目品牌")
# 分页查询项目下的品牌列表
def list_brands(
    project_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    brand_name: str | None = Query(None),
    brand_type: BrandType | None = Query(None),
    status: EntityStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = brand_service.list_brands(
        db,
        project_id=project_id,
        page=page,
        page_size=page_size,
        brand_name=brand_name,
        brand_type=brand_type.value if brand_type else None,
        status=status.value if status else None,
    )
    data = [BrandOut.model_validate(item).model_dump(mode="json") for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/projects/{project_id}/brands", summary="创建项目品牌")
# 在指定项目下创建品牌
def create_brand(
    payload: BrandCreate,
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    brand = brand_service.create_brand(db, project_id, payload)
    return success(BrandOut.model_validate(brand).model_dump(mode="json"))


@router.get("/brands/{brand_id}", summary="获取品牌")
# 按 ID 获取品牌详情
def get_brand(
    brand_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    brand = brand_service.get_brand(db, brand_id)
    return success(BrandOut.model_validate(brand).model_dump(mode="json"))


@router.put("/brands/{brand_id}", summary="更新品牌")
# 更新品牌信息
def update_brand(
    payload: BrandUpdate,
    brand_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    brand = brand_service.update_brand(db, brand_id, payload)
    return success(BrandOut.model_validate(brand).model_dump(mode="json"))


@router.delete("/brands/{brand_id}", summary="删除品牌")
# 软删除指定品牌
def delete_brand(
    brand_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    brand_service.delete_brand(db, brand_id)
    return success({"id": brand_id})


@router.get("/brands/{brand_id}/aliases", summary="分页查询品牌别名")
# 分页查询品牌下的别名列表
def list_brand_aliases(
    brand_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    items, total = brand_service.list_aliases(
        db, brand_id=brand_id, page=page, page_size=page_size
    )
    data = [
        BrandAliasOut.model_validate(item).model_dump(mode="json") for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.post("/brands/{brand_id}/aliases", summary="创建品牌别名")
# 为品牌创建别名
def create_brand_alias(
    payload: BrandAliasCreate,
    brand_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    alias = brand_service.create_alias(db, brand_id, payload)
    return success(BrandAliasOut.model_validate(alias).model_dump(mode="json"))


@router.put("/brand-aliases/{alias_id}", summary="更新品牌别名")
# 更新品牌别名信息
def update_brand_alias(
    payload: BrandAliasUpdate,
    alias_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    alias = brand_service.update_alias(db, alias_id, payload)
    return success(BrandAliasOut.model_validate(alias).model_dump(mode="json"))


@router.delete("/brand-aliases/{alias_id}", summary="删除品牌别名")
# 软删除指定品牌别名
def delete_brand_alias(
    alias_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> dict:
    brand_service.delete_alias(db, alias_id)
    return success({"id": alias_id})
