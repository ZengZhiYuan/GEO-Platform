"""文章 CRUD / Service。

同步 SQLAlchemy 2.0 写法；所有查询过滤软删除记录（is_deleted=False）。
记录不存在时抛出 BusinessException，由全局异常处理器统一返回。

本任务（TASK-0307）范围：分页列表、详情、内容编辑、状态切换。
文章的生成与新增由写作任务/Worker 模块负责，本模块不提供新增接口。
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.article import Article
from app.schemas.article import (
    ArticleStatusUpdate,
    ArticleUpdate,
)


def _get_active(db: Session, article_id: int) -> Article:
    """按 id 获取未删除的文章，不存在则抛业务异常。"""
    stmt = select(Article).where(
        Article.id == article_id,
        Article.is_deleted.is_(False),
    )
    article = db.execute(stmt).scalar_one_or_none()
    if article is None:
        raise BusinessException(message="文章不存在", code=40400)
    return article


def list_articles(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    writing_task_id: int | None = None,
    status: str | None = None,
    article_title: str | None = None,
) -> tuple[list[Article], int]:
    """分页查询文章。

    支持按 writing_task_id 精确筛选、status 精确筛选、article_title 模糊搜索。
    返回 (当前页记录列表, 总数)。
    """
    conditions = [Article.is_deleted.is_(False)]
    if writing_task_id is not None:
        conditions.append(Article.writing_task_id == writing_task_id)
    if status:
        conditions.append(Article.status == status)
    if article_title:
        conditions.append(Article.article_title.ilike(f"%{article_title.strip()}%"))

    total = db.execute(
        select(func.count()).select_from(Article).where(*conditions)
    ).scalar_one()

    stmt = (
        select(Article)
        .where(*conditions)
        .order_by(Article.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_article(db: Session, article_id: int) -> Article:
    """获取文章详情。"""
    return _get_active(db, article_id)


def update_article(
    db: Session, article_id: int, payload: ArticleUpdate
) -> Article:
    """编辑文章。仅更新请求中显式提供的字段（标题 / 封面图 / 正文）。"""
    article = _get_active(db, article_id)

    data = payload.model_dump(exclude_unset=True)
    if "article_title" in data:
        article.article_title = data["article_title"]
    if "cover_image_url" in data:
        article.cover_image_url = data["cover_image_url"]
    if "content" in data:
        article.content = data["content"]

    db.commit()
    db.refresh(article)
    return article


def update_article_status(
    db: Session, article_id: int, payload: ArticleStatusUpdate
) -> Article:
    """切换文章状态。目标态限于 pending_review / normal / disabled / failed。"""
    article = _get_active(db, article_id)
    article.status = payload.status.value
    db.commit()
    db.refresh(article)
    return article
