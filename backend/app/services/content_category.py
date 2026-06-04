"""内容分类 CRUD / Service。

同步 SQLAlchemy 2.0 写法；所有查询过滤软删除记录（is_deleted=False）。
记录不存在时抛出 BusinessException，由全局异常处理器统一返回。

article_count 为只读统计字段，不在此处接受写入；后续由写作任务/文章模块维护。
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.content_category import ContentCategory
from app.schemas.content_category import (
    ContentCategoryCreate,
    ContentCategoryUpdate,
)


def _get_active(db: Session, category_id: int) -> ContentCategory:
    """按 id 获取未删除的内容分类，不存在则抛业务异常。"""
    stmt = select(ContentCategory).where(
        ContentCategory.id == category_id,
        ContentCategory.is_deleted.is_(False),
    )
    category = db.execute(stmt).scalar_one_or_none()
    if category is None:
        raise BusinessException(message="内容分类不存在", code=40400)
    return category


def list_content_categories(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    group_name: str | None = None,
) -> tuple[list[ContentCategory], int]:
    """分页查询内容分类，支持按 group_name 模糊搜索。

    返回 (当前页记录列表, 总数)。
    """
    conditions = [ContentCategory.is_deleted.is_(False)]
    if group_name:
        conditions.append(ContentCategory.group_name.ilike(f"%{group_name.strip()}%"))

    total = db.execute(
        select(func.count()).select_from(ContentCategory).where(*conditions)
    ).scalar_one()

    stmt = (
        select(ContentCategory)
        .where(*conditions)
        .order_by(ContentCategory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_content_category(db: Session, category_id: int) -> ContentCategory:
    """获取内容分类详情。"""
    return _get_active(db, category_id)


def create_content_category(
    db: Session, payload: ContentCategoryCreate
) -> ContentCategory:
    """新增内容分类。article_count 由系统默认 0，不接受写入。"""
    category = ContentCategory(group_name=payload.group_name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_content_category(
    db: Session, category_id: int, payload: ContentCategoryUpdate
) -> ContentCategory:
    """编辑内容分类。仅更新请求中显式提供的字段。"""
    category = _get_active(db, category_id)

    data = payload.model_dump(exclude_unset=True)
    if data.get("group_name") is not None:
        category.group_name = data["group_name"]

    db.commit()
    db.refresh(category)
    return category


def delete_content_category(db: Session, category_id: int) -> None:
    """软删除内容分类。"""
    category = _get_active(db, category_id)
    category.is_deleted = True
    category.deleted_at = datetime.now()
    db.commit()
