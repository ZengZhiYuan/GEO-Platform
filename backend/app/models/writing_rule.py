"""写作规范模型。

对应数据表 ``writing_rule``（见 docs/api-contract.md 写作规范）。
维护不同创作类型的提示词指令内容。
公共字段（id / created_at / updated_at / 软删除 / 租户等）继承自 BaseModel。
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class WritingRule(BaseModel):
    """写作规范。管理提示词指令，按创作类型区分。"""

    __tablename__ = "writing_rule"

    # 规范名称，不能为空
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 创作类型：article_creation / title_creation / traffic_replication
    creation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # 提示词指令内容（长文本），不能为空
    instruction_content: Mapped[str] = mapped_column(Text, nullable=False)
