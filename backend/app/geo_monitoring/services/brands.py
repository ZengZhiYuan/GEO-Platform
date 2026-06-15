"""品牌与品牌别名服务。"""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import Brand, BrandAlias
from app.geo_monitoring.schemas import (
    BrandAliasCreate,
    BrandAliasUpdate,
    BrandCreate,
    BrandUpdate,
)
from app.geo_monitoring.services.projects import require_active_project


def _commit_unique(db: Session, *, code: int, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessException(message=message, code=code) from exc


def get_brand(db: Session, brand_id: int) -> Brand:
    brand = db.execute(
        select(Brand).where(Brand.id == brand_id, Brand.is_deleted.is_(False))
    ).scalar_one_or_none()
    if brand is None:
        raise BusinessException(message="品牌不存在", code=40400)
    return brand


def _ensure_target_available(
    db: Session, project_id: int, *, exclude_brand_id: int | None = None
) -> None:
    conditions = [
        Brand.project_id == project_id,
        Brand.brand_type == "target",
        Brand.is_deleted.is_(False),
    ]
    if exclude_brand_id is not None:
        conditions.append(Brand.id != exclude_brand_id)
    if db.execute(select(Brand.id).where(*conditions)).scalar_one_or_none() is not None:
        raise BusinessException(message="每个项目只能配置一个目标品牌", code=40010)


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
    conditions = [Brand.project_id == project_id, Brand.is_deleted.is_(False)]
    if brand_name:
        conditions.append(Brand.brand_name.ilike(f"%{brand_name.strip()}%"))
    if brand_type:
        conditions.append(Brand.brand_type == brand_type)
    if status:
        conditions.append(Brand.status == status)
    total = db.execute(select(func.count()).select_from(Brand).where(*conditions)).scalar_one()
    items = list(
        db.execute(
            select(Brand)
            .where(*conditions)
            .order_by(Brand.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def create_brand(db: Session, project_id: int, payload: BrandCreate) -> Brand:
    require_active_project(db, project_id)
    if payload.brand_type.value == "target":
        _ensure_target_available(db, project_id)
    duplicate = db.execute(
        select(Brand.id).where(
            Brand.project_id == project_id,
            Brand.brand_name == payload.brand_name,
            Brand.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise BusinessException(message="项目内品牌名称不能重复", code=40012)

    brand = Brand(
        project_id=project_id,
        **{
            key: value.value if isinstance(value, StrEnum) else value
            for key, value in payload.model_dump().items()
        },
    )
    db.add(brand)
    _commit_unique(db, code=40012, message="项目内品牌名称不能重复")
    db.refresh(brand)
    return brand


def update_brand(db: Session, brand_id: int, payload: BrandUpdate) -> Brand:
    brand = get_brand(db, brand_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("brand_type") == "target" or getattr(data.get("brand_type"), "value", None) == "target":
        _ensure_target_available(db, brand.project_id, exclude_brand_id=brand.id)
    for field, value in data.items():
        setattr(brand, field, value.value if isinstance(value, StrEnum) else value)
    _commit_unique(db, code=40012, message="项目内品牌名称不能重复")
    db.refresh(brand)
    return brand


def delete_brand(db: Session, brand_id: int) -> None:
    brand = get_brand(db, brand_id)
    brand.is_deleted = True
    brand.deleted_at = datetime.now(timezone.utc)
    db.commit()


def get_alias(db: Session, alias_id: int) -> BrandAlias:
    alias = db.execute(
        select(BrandAlias).where(
            BrandAlias.id == alias_id,
            BrandAlias.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if alias is None:
        raise BusinessException(message="品牌别名不存在", code=40400)
    return alias


def list_aliases(
    db: Session, *, brand_id: int, page: int, page_size: int
) -> tuple[list[BrandAlias], int]:
    get_brand(db, brand_id)
    conditions = [
        BrandAlias.brand_id == brand_id,
        BrandAlias.is_deleted.is_(False),
    ]
    total = db.execute(
        select(func.count()).select_from(BrandAlias).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(BrandAlias)
            .where(*conditions)
            .order_by(BrandAlias.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def create_alias(
    db: Session, brand_id: int, payload: BrandAliasCreate
) -> BrandAlias:
    get_brand(db, brand_id)
    duplicate = db.execute(
        select(BrandAlias.id).where(
            BrandAlias.brand_id == brand_id,
            BrandAlias.alias_name == payload.alias_name,
            BrandAlias.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise BusinessException(message="品牌内别名不能重复", code=40011)
    alias = BrandAlias(
        brand_id=brand_id,
        **{
            key: value.value if isinstance(value, StrEnum) else value
            for key, value in payload.model_dump().items()
        },
    )
    db.add(alias)
    _commit_unique(db, code=40011, message="品牌内别名不能重复")
    db.refresh(alias)
    return alias


def update_alias(
    db: Session, alias_id: int, payload: BrandAliasUpdate
) -> BrandAlias:
    alias = get_alias(db, alias_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alias, field, value.value if isinstance(value, StrEnum) else value)
    _commit_unique(db, code=40011, message="品牌内别名不能重复")
    db.refresh(alias)
    return alias


def delete_alias(db: Session, alias_id: int) -> None:
    alias = get_alias(db, alias_id)
    alias.is_deleted = True
    alias.deleted_at = datetime.now(timezone.utc)
    db.commit()
