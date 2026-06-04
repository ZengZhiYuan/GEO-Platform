"""写作任务 CRUD / Service。

同步 SQLAlchemy 2.0 写法；所有查询过滤软删除记录（is_deleted=False）。
记录不存在时抛出 BusinessException，由全局异常处理器统一返回。

核心规则（见 docs/claude-code-dev.md 14.1）：
    创建大任务时，根据 ai_generate_count 在同一事务内创建对应数量的
    article 小任务。本任务暂不接 MQ / AI，仅完成数据落库与状态初始化。

引用完整性在 service 层校验（无 DB 外键）：
    content_category_id -> content_category（必填）
    content_rule_id / title_rule_id -> writing_rule（content_rule 必填）
    image_category_id -> image_category（可选）
    brand_knowledge_id -> 品牌知识库模块尚未实现，暂不校验存在性
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.article import Article
from app.models.content_category import ContentCategory
from app.models.image_category import ImageCategory
from app.models.writing_rule import WritingRule
from app.models.writing_task import WritingTask
from app.schemas.article import ArticleStatus
from app.schemas.writing_task import (
    ArticleResultStatus,
    TaskStatus,
    WritingTaskCreate,
)

# 大任务进入终态后不可再取消
_CANCELLABLE_STATUSES = {
    TaskStatus.DRAFT.value,
    TaskStatus.PENDING.value,
    TaskStatus.RUNNING.value,
}


def _get_active(db: Session, task_id: int) -> WritingTask:
    """按 id 获取未删除的写作任务，不存在则抛业务异常。"""
    stmt = select(WritingTask).where(
        WritingTask.id == task_id,
        WritingTask.is_deleted.is_(False),
    )
    task = db.execute(stmt).scalar_one_or_none()
    if task is None:
        raise BusinessException(message="写作任务不存在", code=40400)
    return task


def _ensure_exists(db: Session, model, entity_id: int, label: str) -> None:
    """校验某个被引用实体存在（未删除），不存在则抛业务异常。"""
    stmt = select(model.id).where(
        model.id == entity_id,
        model.is_deleted.is_(False),
    )
    if db.execute(stmt).scalar_one_or_none() is None:
        raise BusinessException(message=f"{label}不存在", code=40400)


def _validate_refs(db: Session, payload: WritingTaskCreate) -> None:
    """校验写作任务引用的素材 / 指令是否存在。"""
    _ensure_exists(db, ContentCategory, payload.content_category_id, "内容分类")
    _ensure_exists(db, WritingRule, payload.content_rule_id, "内容创作指令")
    if payload.title_rule_id is not None:
        _ensure_exists(db, WritingRule, payload.title_rule_id, "标题创作指令")
    if payload.image_category_id is not None:
        _ensure_exists(db, ImageCategory, payload.image_category_id, "画像图库分类")
    # brand_knowledge 模块尚未实现，暂不校验其存在性


def list_writing_tasks(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    task_name: str | None = None,
    task_status: str | None = None,
) -> tuple[list[WritingTask], int]:
    """分页查询写作任务，支持按 task_name 模糊搜索、task_status 精确筛选。

    返回 (当前页记录列表, 总数)。
    """
    conditions = [WritingTask.is_deleted.is_(False)]
    if task_name:
        conditions.append(WritingTask.task_name.ilike(f"%{task_name.strip()}%"))
    if task_status:
        conditions.append(WritingTask.task_status == task_status)

    total = db.execute(
        select(func.count()).select_from(WritingTask).where(*conditions)
    ).scalar_one()

    stmt = (
        select(WritingTask)
        .where(*conditions)
        .order_by(WritingTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_writing_task(db: Session, task_id: int) -> WritingTask:
    """获取写作任务详情。"""
    return _get_active(db, task_id)


def create_writing_task(db: Session, payload: WritingTaskCreate) -> WritingTask:
    """创建大任务，并按 ai_generate_count 在同一事务内创建对应数量的小任务。

    大任务初始 task_status=pending、article_result_status=generating；
    小任务初始 status=generating。暂不投递 MQ（见 TASK-0401/0402）。
    """
    _validate_refs(db, payload)

    task = WritingTask(
        task_name=payload.task_name,
        content_category_id=payload.content_category_id,
        distill_keywords=payload.distill_keywords,
        image_category_id=payload.image_category_id,
        article_image_count=payload.article_image_count,
        brand_knowledge_id=payload.brand_knowledge_id,
        content_rule_id=payload.content_rule_id,
        title_rule_id=payload.title_rule_id,
        ai_generate_count=payload.ai_generate_count,
        article_result_status=ArticleResultStatus.GENERATING.value,
        task_status=TaskStatus.PENDING.value,
    )
    db.add(task)
    db.flush()  # 取得 task.id 供小任务关联

    for _ in range(payload.ai_generate_count):
        db.add(
            Article(
                writing_task_id=task.id,
                status=ArticleStatus.GENERATING.value,
            )
        )

    db.commit()
    db.refresh(task)
    return task


def cancel_writing_task(db: Session, task_id: int) -> WritingTask:
    """取消写作任务。

    大任务状态置为 cancelled；仍在 generating 的小任务置为 failed 并记录
    错误信息（契约 article status 无独立的 cancelled 态，failed 为可重试终态）。
    已处于终态（completed/failed/cancelled）的任务不可取消。
    """
    task = _get_active(db, task_id)
    if task.task_status not in _CANCELLABLE_STATUSES:
        raise BusinessException(message="当前任务状态不可取消", code=40010)

    task.task_status = TaskStatus.CANCELLED.value

    stmt = select(Article).where(
        Article.writing_task_id == task.id,
        Article.is_deleted.is_(False),
        Article.status == ArticleStatus.GENERATING.value,
    )
    for article in db.execute(stmt).scalars().all():
        article.status = ArticleStatus.FAILED.value
        article.error_message = "任务已取消"

    db.commit()
    db.refresh(task)
    return task


def retry_writing_task(db: Session, task_id: int) -> WritingTask:
    """重试写作任务（占位实现）。

    MQ / AI 尚未接入（见 TASK-0401/0402），此处仅完成状态流转占位：
    将失败的小任务重置为 generating 并清空错误信息，大任务状态回到 pending、
    article_result_status 回到 generating。后续接入 MQ 后在此补充消息投递。
    """
    task = _get_active(db, task_id)

    stmt = select(Article).where(
        Article.writing_task_id == task.id,
        Article.is_deleted.is_(False),
        Article.status == ArticleStatus.FAILED.value,
    )
    for article in db.execute(stmt).scalars().all():
        article.status = ArticleStatus.GENERATING.value
        article.error_message = None

    task.task_status = TaskStatus.PENDING.value
    task.article_result_status = ArticleResultStatus.GENERATING.value

    db.commit()
    db.refresh(task)
    return task
