"""关键词库模型。

对应数据表 ``keyword_library``（见 docs/claude-code-dev.md 8.3）。
公共字段（id / created_at / updated_at / 软删除 / 租户等）继承自 BaseModel。
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Keyword(BaseModel):
    """关键词库。管理内容创作主词，统计问题数量，跟踪优化状态。"""

    __tablename__ = "keyword_library"

    # 主词（关键词名称），不能为空
    main_word: Mapped[str] = mapped_column(String(255), nullable=False)
    # 标题灵感中该主词关联的问题数量，由标题灵感模块维护，默认 0
    question_count: Mapped[int] = mapped_column(
        Integer, server_default="0", default=0, nullable=False
    )
    # 优化状态：not_optimized / optimizing / optimized
    optimize_status: Mapped[str] = mapped_column(
        String(32),
        server_default="not_optimized",
        default="not_optimized",
        nullable=False,
    )
