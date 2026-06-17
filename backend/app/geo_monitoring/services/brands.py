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


def _commit_unique(db: Session, *, code: int, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessException(message=message, code=code) from exc


def get_brand(db: Session, brand_id: int) -> Brand:
    brand = brand_repo.get_by_id(db, brand_id)
    if brand is None:
        raise BusinessException(message="品牌不存在", code=40400)
    return brand


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


def get_alias(db: Session, alias_id: int) -> BrandAlias:
    alias = brand_repo.get_alias_by_id(db, alias_id)
    if alias is None:
        raise BusinessException(message="品牌别名不存在", code=40400)
    return alias


def list_aliases(
    db: Session, *, brand_id: int, page: int, page_size: int
) -> tuple[list[BrandAlias], int]:
    get_brand(db, brand_id)
    return brand_repo.list_aliases(
        db, brand_id=brand_id, page=page, page_size=page_size
    )


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
