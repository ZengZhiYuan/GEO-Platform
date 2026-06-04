"""内容分类模型。

对应数据表 ``content_category``（见 docs/api-contract.md 内容分类）。
管理文章分组，统计分组下的文章数量。
公共字段（id / created_at / updated_at / 软删除 / 租户等）继承自 BaseModel。

字段命名以 docs/api-contract.md 为唯一权威源：group_name / article_count。
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ContentCategory(BaseModel):
    """内容分类。管理文章分组，统计分组下的文章数量。"""

    __tablename__ = "content_category"

    # 分组名称，不能为空
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 分组下的文章数量，由写作任务/文章模块维护，默认 0
    article_count: Mapped[int] = mapped_column(
        Integer, server_default="0", default=0, nullable=False
    )
