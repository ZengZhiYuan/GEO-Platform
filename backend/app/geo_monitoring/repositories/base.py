"""仓储层通用查询工具。"""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


# 对任意 Select 语句执行分页查询，返回当前页数据与总记录数
def paginate(
    db: Session,
    stmt: Select[Any],
    *,
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    # 去掉排序后统计子查询总数
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.execute(count_stmt).scalar_one()
    # 按页码偏移并限制条数
    items = list(
        db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    )
    return items, total
