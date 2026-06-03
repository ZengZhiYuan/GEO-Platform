"""标题灵感 CRUD / Service。

同步 SQLAlchemy 2.0 写法；所有查询过滤软删除记录（is_deleted=False）。
记录不存在时抛出 BusinessException，由全局异常处理器统一返回。
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.title_inspiration import TitleInspiration
from app.schemas.title_inspiration import (
    TitleInspirationCreate,
    TitleInspirationUpdate,
)


def _get_active(db: Session, inspiration_id: int) -> TitleInspiration:
    """按 id 获取未删除的标题灵感，不存在则抛业务异常。"""
    stmt = select(TitleInspiration).where(
        TitleInspiration.id == inspiration_id,
        TitleInspiration.is_deleted.is_(False),
    )
    inspiration = db.execute(stmt).scalar_one_or_none()
    if inspiration is None:
        raise BusinessException(message="标题灵感不存在", code=40400)
    return inspiration


def list_title_inspirations(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    main_word: str | None = None,
    collect_status: str | None = None,
) -> tuple[list[TitleInspiration], int]:
    """分页查询标题灵感，支持按 main_word 模糊搜索、collect_status 精确筛选。

    返回 (当前页记录列表, 总数)。
    """
    conditions = [TitleInspiration.is_deleted.is_(False)]
    if main_word:
        conditions.append(TitleInspiration.main_word.ilike(f"%{main_word.strip()}%"))
    if collect_status:
        conditions.append(TitleInspiration.collect_status == collect_status)

    total = db.execute(
        select(func.count()).select_from(TitleInspiration).where(*conditions)
    ).scalar_one()

    stmt = (
        select(TitleInspiration)
        .where(*conditions)
        .order_by(TitleInspiration.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_title_inspiration(db: Session, inspiration_id: int) -> TitleInspiration:
    """获取标题灵感详情。"""
    return _get_active(db, inspiration_id)


def create_title_inspiration(
    db: Session, payload: TitleInspirationCreate
) -> TitleInspiration:
    """新增标题灵感。"""
    inspiration = TitleInspiration(
        main_word=payload.main_word,
        question=payload.question,
        collect_status=payload.collect_status.value,
    )
    db.add(inspiration)
    db.commit()
    db.refresh(inspiration)
    return inspiration


def update_title_inspiration(
    db: Session, inspiration_id: int, payload: TitleInspirationUpdate
) -> TitleInspiration:
    """编辑标题灵感。仅更新请求中显式提供的字段。"""
    inspiration = _get_active(db, inspiration_id)

    data = payload.model_dump(exclude_unset=True)
    if data.get("main_word") is not None:
        inspiration.main_word = data["main_word"]
    if data.get("question") is not None:
        inspiration.question = data["question"]
    if data.get("collect_status") is not None:
        # collect_status 为 StrEnum，统一以字符串值存储
        inspiration.collect_status = str(data["collect_status"])

    db.commit()
    db.refresh(inspiration)
    return inspiration


def delete_title_inspiration(db: Session, inspiration_id: int) -> None:
    """软删除标题灵感。"""
    inspiration = _get_active(db, inspiration_id)
    inspiration.is_deleted = True
    inspiration.deleted_at = datetime.now()
    db.commit()
