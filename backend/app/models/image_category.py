"""画像图库分类模型。

对应数据表 ``image_category``（见 docs/claude-code-dev.md 图库设计）。
公共字段（id / created_at / updated_at / 软删除 / 租户等）继承自 BaseModel。

字段命名以 docs/api-contract.md 为唯一权威源：category_name / image_count。
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ImageCategory(BaseModel):
    """画像图库分类。管理图片素材的分组，统计分组下的图片数量。"""

    __tablename__ = "image_category"

    # 分类名称，不能为空
    category_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 分类下的图片数量，由 image_asset 模块维护，默认 0
    image_count: Mapped[int] = mapped_column(
        Integer, server_default="0", default=0, nullable=False
    )
