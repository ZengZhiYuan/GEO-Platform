"""通用模型基类。

定义所有业务表共享的公共字段（见 docs/claude-code-dev.md 8.1）：
主键、创建/更新时间、软删除标记、租户与操作人字段。

业务模型示例::

    class Keyword(BaseModel):
        __tablename__ = "keyword_library"
        main_word: Mapped[str] = mapped_column(String(255), nullable=False)
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BaseModel(Base):
    """抽象基类，提供公共字段，不对应实际数据表。"""

    __abstract__ = True

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), default=False, nullable=False
    )
    tenant_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
