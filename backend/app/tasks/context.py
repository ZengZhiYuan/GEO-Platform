"""文章生成上下文拼接（只读，短事务）。

根据 ``article`` 与其所属 ``writing_task``，从各素材 / 指令模块读取并拼接出
``ArticleContext``（纯数据）。该函数只做数据库**读取**，调用方在短事务内执行，
读取完成即关闭会话，随后在无事务状态下调用 AI（见任务要求 16）。

拼接来源（见 dev 文档 11.2）：
- 写作任务 writing_task：task_name / distill_keywords / article_image_count
- 内容分类 content_category：group_name -> category_name
- 写作规范 writing_rule：content_rule_id -> 内容创作指令；title_rule_id -> 标题创作指令
- 画像图库 image_asset：按 image_category_id 取候选配图 URL 列表
- 品牌知识库 brand_knowledge：模块尚未实现，相关字段暂留空（预留接入）
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.content_category import ContentCategory
from app.models.image_asset import ImageAsset
from app.models.writing_rule import WritingRule
from app.models.writing_task import WritingTask
from app.services.ai_generation.base import ArticleContext

# 单篇文章拼接的候选配图上限（避免一次性载入过多图片）
_MAX_IMAGE_CANDIDATES = 20


def _rule_content(db: Session, rule_id: int | None) -> str | None:
    if rule_id is None:
        return None
    stmt = select(WritingRule.instruction_content).where(
        WritingRule.id == rule_id,
        WritingRule.is_deleted.is_(False),
    )
    return db.execute(stmt).scalar_one_or_none()


def _category_name(db: Session, category_id: int) -> str | None:
    stmt = select(ContentCategory.group_name).where(
        ContentCategory.id == category_id,
        ContentCategory.is_deleted.is_(False),
    )
    return db.execute(stmt).scalar_one_or_none()


def _image_urls(db: Session, image_category_id: int | None) -> list[str]:
    if image_category_id is None:
        return []
    stmt = (
        select(ImageAsset.image_url)
        .where(
            ImageAsset.category_id == image_category_id,
            ImageAsset.is_deleted.is_(False),
        )
        .order_by(ImageAsset.id.asc())
        .limit(_MAX_IMAGE_CANDIDATES)
    )
    return list(db.execute(stmt).scalars().all())


def _generation_index(db: Session, task_id: int, article_id: int) -> int:
    """以「同任务内按 id 升序的序号」作为 AI 创作序号（从 1 开始）。

    模型未单列 generation_index 字段，这里按稳定排序推导，仅用于标题等展示。
    """
    stmt = (
        select(Article.id)
        .where(
            Article.writing_task_id == task_id,
            Article.is_deleted.is_(False),
        )
        .order_by(Article.id.asc())
    )
    ids = list(db.execute(stmt).scalars().all())
    try:
        return ids.index(article_id) + 1
    except ValueError:
        return 1


def build_article_context(
    db: Session, article: Article, task: WritingTask
) -> ArticleContext:
    """拼接单篇文章的生成上下文（纯数据，无 DB 句柄外泄）。"""
    return ArticleContext(
        writing_task_id=task.id,
        article_id=article.id,
        generation_index=_generation_index(db, task.id, article.id),
        task_name=task.task_name,
        distill_keywords=task.distill_keywords,
        category_name=_category_name(db, task.content_category_id),
        content_rule_content=_rule_content(db, task.content_rule_id) or "",
        title_rule_content=_rule_content(db, task.title_rule_id),
        article_image_count=task.article_image_count,
        image_urls=_image_urls(db, task.image_category_id),
        # 品牌知识库模块尚未实现，brand_* 字段暂留空
    )
