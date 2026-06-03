"""画像图库分类 CRUD / Service。

同步 SQLAlchemy 2.0 写法；所有查询过滤软删除记录（is_deleted=False）。
记录不存在时抛出 BusinessException，由全局异常处理器统一返回。
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.image_category import ImageCategory
from app.schemas.image_category import ImageCategoryCreate, ImageCategoryUpdate


def _get_active(db: Session, category_id: int) -> ImageCategory:
    """按 id 获取未删除的图库分类，不存在则抛业务异常。"""
    stmt = select(ImageCategory).where(
        ImageCategory.id == category_id,
        ImageCategory.is_deleted.is_(False),
    )
    category = db.execute(stmt).scalar_one_or_none()
    if category is None:
        raise BusinessException(message="图库分类不存在", code=40400)
    return category


def list_image_categories(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    category_name: str | None = None,
) -> tuple[list[ImageCategory], int]:
    """分页查询图库分类，支持按 category_name 模糊搜索。

    返回 (当前页记录列表, 总数)。
    """
    conditions = [ImageCategory.is_deleted.is_(False)]
    if category_name:
        conditions.append(
            ImageCategory.category_name.ilike(f"%{category_name.strip()}%")
        )

    total = db.execute(
        select(func.count()).select_from(ImageCategory).where(*conditions)
    ).scalar_one()

    stmt = (
        select(ImageCategory)
        .where(*conditions)
        .order_by(ImageCategory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_image_category(db: Session, category_id: int) -> ImageCategory:
    """获取图库分类详情。"""
    return _get_active(db, category_id)


def create_image_category(
    db: Session, payload: ImageCategoryCreate
) -> ImageCategory:
    """新增图库分类。image_count 初始为 0，由 image_asset 模块维护。"""
    category = ImageCategory(category_name=payload.category_name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_image_category(
    db: Session, category_id: int, payload: ImageCategoryUpdate
) -> ImageCategory:
    """编辑图库分类。仅更新请求中显式提供的字段。"""
    category = _get_active(db, category_id)

    data = payload.model_dump(exclude_unset=True)
    if data.get("category_name") is not None:
        category.category_name = data["category_name"]

    db.commit()
    db.refresh(category)
    return category


def delete_image_category(db: Session, category_id: int) -> None:
    """软删除图库分类。"""
    category = _get_active(db, category_id)
    category.is_deleted = True
    category.deleted_at = datetime.now()
    db.commit()
