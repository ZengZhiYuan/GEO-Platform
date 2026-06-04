"""文章生成异步任务（TASK-0401 / 0402）。

Dramatiq actor ``generate_article`` 消费单篇文章小任务，按以下分段执行，
确保「不在数据库长事务中调用 AI」（任务要求 16）：

    Phase 1（短事务，只读）：加载 article + writing_task，做幂等/取消判定，
                             拼接 ArticleContext，随后关闭会话。
    Phase 2（无事务）       ：调用 MockAIWriter 生成标题与正文。
    Phase 3（短事务，写）   ：再次校验状态（幂等），回写标题/正文/封面/状态。
    Phase 4（短事务）       ：聚合大任务状态（见 aggregation.refresh_task_status）。

幂等（任务要求 17）：
- article 不存在 / 已软删除          -> 忽略
- 大任务已取消（cancelled）          -> 不写结果；若 article 仍 generating 则置 failed
- article 已是 pending_review/normal/disabled -> 已生成成功，忽略（防重复消费）
- article 为 generating / failed     -> 执行生成（failed 为重试再次进入）

失败重试（任务要求 15）：
- actor ``max_retries`` 启用 Dramatiq 自带重试；
- 仅当重试次数用尽（最后一次）才把 article 置 failed 并记录 error_message，
  中间重试保持 generating，避免状态来回抖动。
"""

from __future__ import annotations

import logging

import dramatiq
from dramatiq.middleware import CurrentMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

# 导入即设置全局 broker（actor 装饰器依赖已设置的 broker）
from app.workers.broker import broker  # noqa: F401

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.article import Article
from app.models.writing_task import WritingTask
from app.schemas.article import ArticleStatus
from app.schemas.writing_task import TaskStatus
from app.services.ai_generation import get_ai_writer
from app.services.ai_generation.base import ArticleContext
from app.tasks.aggregation import refresh_task_status
from app.tasks.context import build_article_context

logger = logging.getLogger("app.tasks")

# Phase 1 判定结果
_SKIP = "skip"
_CANCELLED = "cancelled"
_GENERATE = "generate"

# article 已生成成功（不应被重复消费覆盖）的状态集合
_DONE_STATUSES = {
    ArticleStatus.PENDING_REVIEW.value,
    ArticleStatus.NORMAL.value,
    ArticleStatus.DISABLED.value,
}

_ERROR_MESSAGE_MAXLEN = 2000


def _get_active_article(db: Session, article_id: int) -> Article | None:
    return db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def _get_active_task(db: Session, task_id: int) -> WritingTask | None:
    return db.execute(
        select(WritingTask).where(
            WritingTask.id == task_id,
            WritingTask.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def _load_phase(
    article_id: int, session_factory
) -> tuple[str, ArticleContext | None, int | None]:
    """Phase 1：加载 + 幂等/取消判定 + 拼接上下文（短事务，只读）。"""
    db: Session = session_factory()
    try:
        article = _get_active_article(db, article_id)
        if article is None:
            logger.info("article %s 不存在或已删除，忽略", article_id)
            return _SKIP, None, None

        task = _get_active_task(db, article.writing_task_id)
        if task is None:
            logger.info("article %s 的大任务不存在或已删除，忽略", article_id)
            return _SKIP, None, None

        if task.task_status == TaskStatus.CANCELLED.value:
            return _CANCELLED, None, task.id

        if article.status in _DONE_STATUSES:
            logger.info("article %s 已生成（%s），忽略重复消费", article_id, article.status)
            return _SKIP, None, task.id

        context = build_article_context(db, article, task)
        return _GENERATE, context, task.id
    finally:
        db.close()


def _save_phase(article_id: int, result, session_factory) -> bool:
    """Phase 3：回写生成结果（短事务，写）。返回是否实际写入。"""
    db: Session = session_factory()
    try:
        article = _get_active_article(db, article_id)
        if article is None:
            return False

        task = _get_active_task(db, article.writing_task_id)
        if task is not None and task.task_status == TaskStatus.CANCELLED.value:
            # 任务已取消：不写结果；若仍卡在 generating 则收敛为 failed
            if article.status == ArticleStatus.GENERATING.value:
                article.status = ArticleStatus.FAILED.value
                article.error_message = "任务已取消"
                db.commit()
            return False

        if article.status in _DONE_STATUSES:
            # 已被其他消费写入，幂等放弃
            return False

        article.article_title = result.title
        article.content = result.content_html
        article.cover_image_url = result.cover_image_url
        article.status = ArticleStatus.PENDING_REVIEW.value
        article.error_message = None
        db.commit()
        return True
    finally:
        db.close()


def _fail_phase(article_id: int, message: str, session_factory) -> None:
    """失败收敛：把 article 置 failed 并记录 error_message（短事务）。"""
    db: Session = session_factory()
    try:
        article = _get_active_article(db, article_id)
        if article is None:
            return
        # 若已生成成功则不覆盖
        if article.status in _DONE_STATUSES:
            return
        article.status = ArticleStatus.FAILED.value
        article.error_message = (message or "生成失败")[:_ERROR_MESSAGE_MAXLEN]
        db.commit()
    finally:
        db.close()


def _cancel_phase(article_id: int, session_factory) -> None:
    """大任务已取消时，把仍 generating 的 article 收敛为 failed。"""
    db: Session = session_factory()
    try:
        article = _get_active_article(db, article_id)
        if article is None:
            return
        if article.status == ArticleStatus.GENERATING.value:
            article.status = ArticleStatus.FAILED.value
            article.error_message = "任务已取消"
            db.commit()
    finally:
        db.close()


def run_generation(article_id: int, *, session_factory=None) -> str:
    """执行单篇文章生成的完整编排（可被 actor 或测试直接调用）。

    ``session_factory`` 默认取模块级 ``SessionLocal``（动态查找，便于测试注入）。
    返回一个简单的结果标识：done / skipped / cancelled。
    生成阶段（Phase 2）若抛错，异常向上抛出，由 actor 决定是否重试 / 收敛。
    """
    if session_factory is None:
        session_factory = SessionLocal

    decision, context, task_id = _load_phase(article_id, session_factory)

    if decision == _SKIP:
        return "skipped"

    if decision == _CANCELLED:
        _cancel_phase(article_id, session_factory)
        if task_id is not None:
            refresh_task_status(task_id, session_factory=session_factory)
        return "cancelled"

    # Phase 2：调用 AI（无 DB 事务）
    writer = get_ai_writer()
    result = writer.generate(context)  # 可能抛出 -> 交由调用方处理

    # Phase 3：回写
    _save_phase(article_id, result, session_factory)

    # Phase 4：聚合大任务状态
    if task_id is not None:
        refresh_task_status(task_id, session_factory=session_factory)
    return "done"


def _retries_left() -> bool:
    """是否还有 Dramatiq 重试次数（用于决定失败时是否收敛为 failed）。"""
    message = CurrentMessage.get_current_message()
    if message is None:
        # 非 Dramatiq 上下文（如直接调用 / 测试）：视为无重试，失败即终态
        return False
    retries = message.options.get("retries", 0) or 0
    return retries < settings.ARTICLE_MAX_RETRIES


@dramatiq.actor(
    max_retries=settings.ARTICLE_MAX_RETRIES,
    min_backoff=1000,
    max_backoff=30000,
)
def generate_article(article_id: int) -> None:
    """Dramatiq actor：消费单篇文章生成小任务。"""
    try:
        run_generation(article_id)
    except Exception as exc:  # noqa: BLE001 - 顶层任务需兜底所有异常
        if _retries_left():
            logger.warning("article %s 生成失败，将重试：%s", article_id, exc)
            raise  # 交由 Dramatiq 重试；article 维持 generating
        logger.error("article %s 生成失败且重试用尽：%s", article_id, exc)
        _fail_phase(article_id, str(exc), SessionLocal)
        # 失败后聚合大任务状态（体现 failed / partial_success）
        task_id = _article_task_id(article_id)
        if task_id is not None:
            refresh_task_status(task_id, session_factory=SessionLocal)
        # 收敛为 failed 后不再向上抛出，避免进入死信


def _article_task_id(article_id: int) -> int | None:
    db: Session = SessionLocal()
    try:
        return db.execute(
            select(Article.writing_task_id).where(Article.id == article_id)
        ).scalar_one_or_none()
    finally:
        db.close()


def enqueue_article_generation(article_id: int) -> None:
    """投递单篇文章生成小任务到 MQ。"""
    generate_article.send(article_id)


def enqueue_articles(article_ids: list[int]) -> None:
    """批量投递文章生成小任务到 MQ。"""
    for article_id in article_ids:
        generate_article.send(article_id)
