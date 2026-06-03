"""ORM 模型包。

Alembic 通过导入本包来收集所有模型的元数据（``Base.metadata``）。
后续新增业务模型时，需在此处 import，确保 autogenerate 能感知到表结构。
"""

from app.core.database import Base
from app.models.base import BaseModel
from app.models.keyword import Keyword

__all__ = ["Base", "BaseModel", "Keyword"]
