"""ORM 模型包。

Alembic 通过导入本包来收集所有模型的元数据（``Base.metadata``）。
后续新增业务模型时，需在此处 import，确保 autogenerate 能感知到表结构。
"""

from app.core.database import Base
from app.models.article import Article
from app.models.base import BaseModel
from app.models.content_category import ContentCategory
from app.models.image_asset import ImageAsset
from app.models.image_category import ImageCategory
from app.models.keyword import Keyword
from app.models.title_inspiration import TitleInspiration
from app.models.writing_rule import WritingRule

__all__ = [
    "Article",
    "Base",
    "BaseModel",
    "ContentCategory",
    "ImageAsset",
    "ImageCategory",
    "Keyword",
    "TitleInspiration",
    "WritingRule",
]
