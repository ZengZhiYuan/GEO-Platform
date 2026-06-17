"""品牌仓储。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import AnswerBrandResult, Brand, BrandAlias


def get_by_id(db: Session, brand_id: int) -> Brand | None:
    return db.execute(
        select(Brand).where(Brand.id == brand_id, Brand.is_deleted.is_(False))
    ).scalar_one_or_none()


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
    conditions = [Brand.project_id == project_id, Brand.is_deleted.is_(False)]
    if brand_name:
        conditions.append(Brand.brand_name.ilike(f"%{brand_name.strip()}%"))
    if brand_type:
        conditions.append(Brand.brand_type == brand_type)
    if status:
        conditions.append(Brand.status == status)
    total = db.execute(
        select(func.count()).select_from(Brand).where(*conditions)
    ).scalar_one()
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


def find_target_brand_id(
    db: Session, project_id: int, *, exclude_brand_id: int | None = None
) -> int | None:
    conditions = [
        Brand.project_id == project_id,
        Brand.brand_type == "target",
        Brand.is_deleted.is_(False),
    ]
    if exclude_brand_id is not None:
        conditions.append(Brand.id != exclude_brand_id)
    return db.execute(select(Brand.id).where(*conditions)).scalar_one_or_none()


def find_duplicate_name(
    db: Session, project_id: int, brand_name: str
) -> int | None:
    return db.execute(
        select(Brand.id).where(
            Brand.project_id == project_id,
            Brand.brand_name == brand_name,
            Brand.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def add(db: Session, brand: Brand) -> None:
    db.add(brand)


def get_alias_by_id(db: Session, alias_id: int) -> BrandAlias | None:
    return db.execute(
        select(BrandAlias).where(
            BrandAlias.id == alias_id,
            BrandAlias.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def list_aliases(
    db: Session, *, brand_id: int, page: int, page_size: int
) -> tuple[list[BrandAlias], int]:
    conditions = [BrandAlias.brand_id == brand_id, BrandAlias.is_deleted.is_(False)]
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


def find_duplicate_alias(
    db: Session, brand_id: int, alias_name: str
) -> int | None:
    return db.execute(
        select(BrandAlias.id).where(
            BrandAlias.brand_id == brand_id,
            BrandAlias.alias_name == alias_name,
            BrandAlias.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def add_alias(db: Session, alias: BrandAlias) -> None:
    db.add(alias)


def has_answer_results(db: Session, brand_id: int) -> bool:
    return (
        db.execute(
            select(AnswerBrandResult.id).where(
                AnswerBrandResult.brand_id == brand_id,
                AnswerBrandResult.is_deleted.is_(False),
            )
        ).first()
        is not None
    )
