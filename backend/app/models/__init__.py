"""ORM 公共基类导出。业务模型由各领域包自行注册。"""

from app.core.database import Base
from app.models.base import BaseModel

__all__ = ["Base", "BaseModel"]
