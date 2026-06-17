"""仓储层通用查询工具。"""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


def paginate(
    db: Session,
    stmt: Select[Any],
    *,
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.execute(count_stmt).scalar_one()
    items = list(
        db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    )
    return items, total
