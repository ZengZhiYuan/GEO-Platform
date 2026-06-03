"""画像图库图片 CRUD / Service。

同步 SQLAlchemy 2.0 写法；所有查询过滤软删除记录（is_deleted=False）。
记录不存在时抛出 BusinessException，由全局异常处理器统一返回。

附带维护所属分类的 image_count 统计：新增图片 +1、软删除 -1、
改 category_id 时在新旧分类间迁移计数。category_id 的引用完整性在此层校验。
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.image_asset import ImageAsset
from app.models.image_category import ImageCategory
from app.schemas.image_asset import ImageAssetCreate, ImageAssetUpdate


def _get_active(db: Session, asset_id: int) -> ImageAsset:
    """按 id 获取未删除的图片，不存在则抛业务异常。"""
    stmt = select(ImageAsset).where(
        ImageAsset.id == asset_id,
        ImageAsset.is_deleted.is_(False),
    )
    asset = db.execute(stmt).scalar_one_or_none()
    if asset is None:
        raise BusinessException(message="图片不存在", code=40400)
    return asset


def _get_active_category(db: Session, category_id: int) -> ImageCategory:
    """校验图库分类存在（未删除），不存在则抛业务异常。"""
    stmt = select(ImageCategory).where(
        ImageCategory.id == category_id,
        ImageCategory.is_deleted.is_(False),
    )
    category = db.execute(stmt).scalar_one_or_none()
    if category is None:
        raise BusinessException(message="图库分类不存在", code=40400)
    return category


def list_image_assets(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    category_id: int | None = None,
) -> tuple[list[ImageAsset], int]:
    """分页查询图片，支持按 category_id 精确筛选。

    返回 (当前页记录列表, 总数)。
    """
    conditions = [ImageAsset.is_deleted.is_(False)]
    if category_id is not None:
        conditions.append(ImageAsset.category_id == category_id)

    total = db.execute(
        select(func.count()).select_from(ImageAsset).where(*conditions)
    ).scalar_one()

    stmt = (
        select(ImageAsset)
        .where(*conditions)
        .order_by(ImageAsset.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_image_asset(db: Session, asset_id: int) -> ImageAsset:
    """获取图片详情。"""
    return _get_active(db, asset_id)


def create_image_asset(db: Session, payload: ImageAssetCreate) -> ImageAsset:
    """新增图片。校验所属分类存在，并维护分类 image_count +1。"""
    category = _get_active_category(db, payload.category_id)

    asset = ImageAsset(
        category_id=payload.category_id,
        image_url=payload.image_url,
    )
    db.add(asset)
    category.image_count = category.image_count + 1
    db.commit()
    db.refresh(asset)
    return asset


def update_image_asset(
    db: Session, asset_id: int, payload: ImageAssetUpdate
) -> ImageAsset:
    """编辑图片。仅更新请求中显式提供的字段；改分类时迁移 image_count。"""
    asset = _get_active(db, asset_id)

    data = payload.model_dump(exclude_unset=True)

    new_category_id = data.get("category_id")
    if new_category_id is not None and new_category_id != asset.category_id:
        # 校验新分类存在，并在新旧分类间迁移计数
        new_category = _get_active_category(db, new_category_id)
        old_category = db.execute(
            select(ImageCategory).where(
                ImageCategory.id == asset.category_id,
                ImageCategory.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if old_category is not None:
            old_category.image_count = max(0, old_category.image_count - 1)
        new_category.image_count = new_category.image_count + 1
        asset.category_id = new_category_id

    if data.get("image_url") is not None:
        asset.image_url = data["image_url"]

    db.commit()
    db.refresh(asset)
    return asset


def delete_image_asset(db: Session, asset_id: int) -> None:
    """软删除图片，并维护所属分类 image_count -1。"""
    asset = _get_active(db, asset_id)
    asset.is_deleted = True
    asset.deleted_at = datetime.now()

    category = db.execute(
        select(ImageCategory).where(
            ImageCategory.id == asset.category_id,
            ImageCategory.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if category is not None:
        category.image_count = max(0, category.image_count - 1)

    db.commit()
