"""写作任务（大任务）模型。

对应数据表 ``writing_task``（见 docs/api-contract.md 写作任务）。
组合素材与写作指令，按 ``ai_generate_count`` 拆分为多个 ``article`` 小任务。
公共字段（id / created_at / updated_at / 软删除 / 租户等）继承自 BaseModel。

字段命名以 docs/api-contract.md 为唯一权威源：
    task_name / content_category_id / distill_keywords / image_category_id /
    article_image_count / brand_knowledge_id / content_rule_id / title_rule_id /
    article_result_status / ai_generate_count / task_status

沿用代码库「无 DB 外键」约定：各 *_id 仅为业务引用，引用完整性在 service
层校验；``articles`` 仅为只读 ORM 导航关系（viewonly），不参与写入同步。
"""

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class WritingTask(BaseModel):
    """写作大任务。创建后按 ai_generate_count 拆分为多个 article 小任务。"""

    __tablename__ = "writing_task"

    # 任务名称，不能为空
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 文章分类 ID（引用 content_category），必填，建索引便于后续统计
    content_category_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    # 蒸馏训练词，不能为空
    distill_keywords: Mapped[str] = mapped_column(String(255), nullable=False)
    # 画像图库分类 ID（引用 image_category），可选
    image_category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # 文章配图数量，默认 0
    article_image_count: Mapped[int] = mapped_column(
        Integer, server_default="0", default=0, nullable=False
    )
    # 品牌知识库 ID（引用 brand_knowledge），可选
    brand_knowledge_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # 内容创作指令 ID（引用 writing_rule），必填
    content_rule_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 标题创作指令 ID（引用 writing_rule），可选
    title_rule_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # 文章结果聚合状态，默认 generating，由写作/聚合流程维护
    article_result_status: Mapped[str] = mapped_column(
        String(64), server_default="generating", default="generating", nullable=False
    )
    # AI 创作数量，决定拆分的小任务数量，默认 1
    ai_generate_count: Mapped[int] = mapped_column(
        Integer, server_default="1", default=1, nullable=False
    )
    # 大任务状态，默认 pending（暂未接 MQ）
    task_status: Mapped[str] = mapped_column(
        String(64), server_default="pending", default="pending", nullable=False
    )

    # 只读一对多导航：writing_task.id == article.writing_task_id。
    # 无 DB 外键，使用 foreign() 注解告知 SQLAlchemy 关联列；viewonly 不参与写入。
    articles: Mapped[list["Article"]] = relationship(  # noqa: F821
        "Article",
        primaryjoin="WritingTask.id == foreign(Article.writing_task_id)",
        order_by="Article.id",
        viewonly=True,
    )
