"""标题灵感模型。

对应数据表 ``title_inspiration``（见 docs/claude-code-dev.md 8.4）。
公共字段（id / created_at / updated_at / 软删除 / 租户等）继承自 BaseModel。

字段命名以 docs/api-contract.md 为唯一权威源：收录状态字段名为 ``collect_status``。
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TitleInspiration(BaseModel):
    """标题灵感。管理围绕主词的用户提问/选题灵感。"""

    __tablename__ = "title_inspiration"

    # 主词（关键词名称），不能为空
    main_word: Mapped[str] = mapped_column(String(255), nullable=False)
    # 围绕主词的提问/选题问题，不能为空
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # 收录状态：not_included / included
    collect_status: Mapped[str] = mapped_column(
        String(32),
        server_default="not_included",
        default="not_included",
        nullable=False,
    )
