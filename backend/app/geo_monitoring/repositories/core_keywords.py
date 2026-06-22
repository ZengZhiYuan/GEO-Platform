"""核心词仓储。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import CoreKeyword


def get_by_id(db: Session, keyword_id: int) -> CoreKeyword | None:
    return db.execute(
        select(CoreKeyword).where(
            CoreKeyword.id == keyword_id,
            CoreKeyword.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def list_keywords(
    db: Session,
    *,
    project_id: int,
    page: int,
    page_size: int,
    enabled: bool | None = None,
) -> tuple[list[CoreKeyword], int]:
    conditions = [
        CoreKeyword.project_id == project_id,
        CoreKeyword.is_deleted.is_(False),
    ]
    if enabled is not None:
        conditions.append(CoreKeyword.enabled.is_(enabled))
    total = db.execute(
        select(func.count()).select_from(CoreKeyword).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(CoreKeyword)
            .where(*conditions)
            .order_by(CoreKeyword.sort_order.asc(), CoreKeyword.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def list_all_for_project(db: Session, project_id: int) -> list[CoreKeyword]:
    return list(
        db.execute(
            select(CoreKeyword)
            .where(
                CoreKeyword.project_id == project_id,
                CoreKeyword.is_deleted.is_(False),
            )
            .order_by(CoreKeyword.sort_order.asc(), CoreKeyword.id.asc())
        )
        .scalars()
        .all()
    )


def find_duplicate(
    db: Session, project_id: int, keyword: str, *, exclude_id: int | None = None
) -> int | None:
    conditions = [
        CoreKeyword.project_id == project_id,
        CoreKeyword.keyword == keyword,
        CoreKeyword.is_deleted.is_(False),
    ]
    if exclude_id is not None:
        conditions.append(CoreKeyword.id != exclude_id)
    return db.execute(select(CoreKeyword.id).where(*conditions)).scalar_one_or_none()


def add(db: Session, keyword: CoreKeyword) -> None:
    db.add(keyword)
