"""画像图库图片模型。

对应数据表 ``image_asset``（见 docs/claude-code-dev.md 图库设计）。
公共字段（id / created_at / updated_at / 软删除 / 租户等）继承自 BaseModel。

字段命名以 docs/api-contract.md 为唯一权威源：category_id / image_url / use_count。
沿用代码库无 DB 外键约定，category_id 为普通索引列，引用完整性在 service 层校验。
"""

from sqlalchemy import BigInteger, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ImageAsset(BaseModel):
    """画像图库图片。管理某分类下的图片素材，统计图片被使用次数。"""

    __tablename__ = "image_asset"

    # 所属图库分类 ID，不能为空
    category_id: Mapped[int] = mapped_column(
        BigInteger, index=True, nullable=False
    )
    # 图片 URL，不能为空
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    # 图片被写作任务使用的次数，由写作/文章模块维护，默认 0
    use_count: Mapped[int] = mapped_column(
        Integer, server_default="0", default=0, nullable=False
    )
