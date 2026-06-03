"""关键词库 CRUD / Service。

同步 SQLAlchemy 2.0 写法；所有查询过滤软删除记录（is_deleted=False）。
记录不存在时抛出 BusinessException，由全局异常处理器统一返回。
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.keyword import Keyword
from app.schemas.keyword import KeywordCreate, KeywordUpdate


def _get_active(db: Session, keyword_id: int) -> Keyword:
    """按 id 获取未删除的关键词，不存在则抛业务异常。"""
    stmt = select(Keyword).where(
        Keyword.id == keyword_id,
        Keyword.is_deleted.is_(False),
    )
    keyword = db.execute(stmt).scalar_one_or_none()
    if keyword is None:
        raise BusinessException(message="关键词不存在", code=40400)
    return keyword


def list_keywords(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    main_word: str | None = None,
    optimize_status: str | None = None,
) -> tuple[list[Keyword], int]:
    """分页查询关键词，支持按 main_word 模糊搜索、optimize_status 精确筛选。

    返回 (当前页记录列表, 总数)。
    """
    conditions = [Keyword.is_deleted.is_(False)]
    if main_word:
        conditions.append(Keyword.main_word.ilike(f"%{main_word.strip()}%"))
    if optimize_status:
        conditions.append(Keyword.optimize_status == optimize_status)

    total = db.execute(
        select(func.count()).select_from(Keyword).where(*conditions)
    ).scalar_one()

    stmt = (
        select(Keyword)
        .where(*conditions)
        .order_by(Keyword.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_keyword(db: Session, keyword_id: int) -> Keyword:
    """获取关键词详情。"""
    return _get_active(db, keyword_id)


def create_keyword(db: Session, payload: KeywordCreate) -> Keyword:
    """新增关键词。"""
    keyword = Keyword(
        main_word=payload.main_word,
        optimize_status=payload.optimize_status.value,
    )
    db.add(keyword)
    db.commit()
    db.refresh(keyword)
    return keyword


def update_keyword(db: Session, keyword_id: int, payload: KeywordUpdate) -> Keyword:
    """编辑关键词。仅更新请求中显式提供的字段。"""
    keyword = _get_active(db, keyword_id)

    data = payload.model_dump(exclude_unset=True)
    if data.get("main_word") is not None:
        keyword.main_word = data["main_word"]
    if data.get("optimize_status") is not None:
        # optimize_status 为 StrEnum，统一以字符串值存储
        keyword.optimize_status = str(data["optimize_status"])

    db.commit()
    db.refresh(keyword)
    return keyword


def delete_keyword(db: Session, keyword_id: int) -> None:
    """软删除关键词。"""
    keyword = _get_active(db, keyword_id)
    keyword.is_deleted = True
    keyword.deleted_at = datetime.now()
    db.commit()
