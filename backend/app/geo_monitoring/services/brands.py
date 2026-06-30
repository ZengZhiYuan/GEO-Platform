"""品牌与品牌别名服务。"""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import Brand, BrandAlias
from app.geo_monitoring.repositories import brands as brand_repo
from app.geo_monitoring.schemas import (
    BrandAliasCreate,
    BrandAliasUpdate,
    BrandCreate,
    BrandUpdate,
)
from app.geo_monitoring.services.projects import require_active_project
from app.geo_monitoring.services.tenant_access import ensure_project_tenant_access


# 提交数据库变更，唯一约束冲突时转为业务异常
def _commit_unique(db: Session, *, code: int, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessException(message=message, code=code) from exc


# 按 ID 查询品牌，不存在则抛业务异常
def get_brand(db: Session, brand_id: int) -> Brand:
    brand = brand_repo.get_by_id(db, brand_id)
    if brand is None:
        raise BusinessException(message="品牌不存在", code=40400)
    ensure_project_tenant_access(db, brand.project_id)
    return brand


# 校验项目内尚未存在其他目标品牌
def _ensure_target_available(
    db: Session, project_id: int, *, exclude_brand_id: int | None = None
) -> None:
    if (
        brand_repo.find_target_brand_id(
            db, project_id, exclude_brand_id=exclude_brand_id
        )
        is not None
    ):
        raise BusinessException(message="每个项目只能配置一个目标品牌", code=40010)


# 分页列出项目下的品牌
def list_brands(
    db: Session,
    *,
    project_id: int,
    page: int,
    page_size: int,
    brand_name: str | None = None,
    brand_type: str | None = None,
    status: str | None = None,
) -> tuple[list[Brand], int]:
    require_active_project(db, project_id)
    return brand_repo.list_brands(
        db,
        project_id=project_id,
        page=page,
        page_size=page_size,
        brand_name=brand_name,
        brand_type=brand_type,
        status=status,
    )


# 创建品牌并校验名称与目标品牌唯一性
def create_brand(db: Session, project_id: int, payload: BrandCreate) -> Brand:
    require_active_project(db, project_id)
    if payload.brand_type.value == "target":
        _ensure_target_available(db, project_id)
    if (
        brand_repo.find_duplicate_name(db, project_id, payload.brand_name)
        is not None
    ):
        raise BusinessException(message="项目内品牌名称不能重复", code=40012)

    brand = Brand(
        project_id=project_id,
        **{
            key: value.value if isinstance(value, StrEnum) else value
            for key, value in payload.model_dump().items()
        },
    )
    brand_repo.add(db, brand)
    _commit_unique(db, code=40012, message="项目内品牌名称不能重复")
    db.refresh(brand)
    return brand


# 更新品牌字段并校验目标品牌约束
def update_brand(db: Session, brand_id: int, payload: BrandUpdate) -> Brand:
    brand = get_brand(db, brand_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("brand_type") == "target" or getattr(
        data.get("brand_type"), "value", None
    ) == "target":
        _ensure_target_available(db, brand.project_id, exclude_brand_id=brand.id)
    for field, value in data.items():
        setattr(brand, field, value.value if isinstance(value, StrEnum) else value)
    _commit_unique(db, code=40012, message="项目内品牌名称不能重复")
    db.refresh(brand)
    return brand


# 软删除品牌，已被答案引用则拒绝
def delete_brand(db: Session, brand_id: int) -> None:
    brand = get_brand(db, brand_id)
    if brand_repo.has_answer_results(db, brand_id):
        raise BusinessException(
            message="品牌已被监测答案引用，无法删除",
            code=40905,
            status_code=409,
        )
    brand.is_deleted = True
    brand.deleted_at = datetime.now(timezone.utc)
    db.commit()


# 按 ID 查询品牌别名，不存在则抛业务异常
def get_alias(db: Session, alias_id: int) -> BrandAlias:
    alias = brand_repo.get_alias_by_id(db, alias_id)
    if alias is None:
        raise BusinessException(message="品牌别名不存在", code=40400)
    brand = brand_repo.get_by_id(db, alias.brand_id)
    if brand is None:
        raise BusinessException(message="品牌别名不存在", code=40400)
    ensure_project_tenant_access(db, brand.project_id)
    return alias


# 分页列出品牌下的别名
def list_aliases(
    db: Session, *, brand_id: int, page: int, page_size: int
) -> tuple[list[BrandAlias], int]:
    get_brand(db, brand_id)
    return brand_repo.list_aliases(
        db, brand_id=brand_id, page=page, page_size=page_size
    )


# 创建品牌别名并校验同品牌内不重复
def create_alias(
    db: Session, brand_id: int, payload: BrandAliasCreate
) -> BrandAlias:
    get_brand(db, brand_id)
    if (
        brand_repo.find_duplicate_alias(db, brand_id, payload.alias_name)
        is not None
    ):
        raise BusinessException(message="品牌内别名不能重复", code=40011)
    alias = BrandAlias(
        brand_id=brand_id,
        **{
            key: value.value if isinstance(value, StrEnum) else value
            for key, value in payload.model_dump().items()
        },
    )
    brand_repo.add_alias(db, alias)
    _commit_unique(db, code=40011, message="品牌内别名不能重复")
    db.refresh(alias)
    return alias


# 更新品牌别名字段
def update_alias(
    db: Session, alias_id: int, payload: BrandAliasUpdate
) -> BrandAlias:
    alias = get_alias(db, alias_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alias, field, value.value if isinstance(value, StrEnum) else value)
    _commit_unique(db, code=40011, message="品牌内别名不能重复")
    db.refresh(alias)
    return alias


# 软删除品牌别名
def delete_alias(db: Session, alias_id: int) -> None:
    alias = get_alias(db, alias_id)
    alias.is_deleted = True
    alias.deleted_at = datetime.now(timezone.utc)
    db.commit()
