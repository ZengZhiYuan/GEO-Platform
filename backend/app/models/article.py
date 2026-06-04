"""文章（小任务）模型。

对应数据表 ``article``（见 docs/api-contract.md 文章清单）。
由写作大任务按 ``ai_generate_count`` 拆分生成，承载单篇文章的生成结果与状态。
公共字段（id / created_at / updated_at / 软删除 / 租户等）继承自 BaseModel。

字段命名以 docs/api-contract.md 为唯一权威源：
    writing_task_id / article_title / cover_image_url / status / content /
    error_message

沿用代码库「无 DB 外键」约定：``writing_task_id`` 仅为业务引用并建索引，
引用完整性在 service 层维护；``writing_task`` 仅为只读 ORM 导航关系。
"""

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Article(BaseModel):
    """小任务文章。隶属于某个写作大任务（writing_task_id）。"""

    __tablename__ = "article"

    # 所属大任务 ID（引用 writing_task），必填，建索引便于按任务查询
    writing_task_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    # 文章标题，生成前为空
    article_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 封面图 URL，生成前为空
    cover_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 文章状态，初始 generating（生成中）
    status: Mapped[str] = mapped_column(
        String(64), server_default="generating", default="generating", nullable=False
    )
    # 正文内容（HTML / 富文本），生成前为空
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 生成失败时的错误信息
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 只读多对一导航：writing_task.id == article.writing_task_id（无 DB 外键）
    writing_task: Mapped["WritingTask"] = relationship(  # noqa: F821
        "WritingTask",
        primaryjoin="WritingTask.id == foreign(Article.writing_task_id)",
        viewonly=True,
    )
