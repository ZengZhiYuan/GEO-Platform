"""数据库连接与会话管理。

提供：
- ``engine``：SQLAlchemy 引擎（基于 ``settings.DATABASE_URL``）。
- ``SessionLocal``：会话工厂。
- ``Base``：所有 ORM 模型的声明式基类（SQLAlchemy 2.0 风格）。
- ``get_db``：FastAPI 依赖，按请求提供并自动关闭会话。

业务模型统一继承 ``app.models.base.BaseModel``（内含公共字段），
其元数据通过 ``Base.metadata`` 供 Alembic 生成迁移。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


# 根据数据库类型构建 SQLAlchemy 引擎连接池参数
def _engine_options() -> dict:
    options = {
        "echo": settings.DB_ECHO,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
        "future": True,
    }
    if make_url(settings.DATABASE_URL).get_backend_name() != "sqlite":
        options.update(
            {
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
            }
        )
    return options


engine = create_engine(settings.DATABASE_URL, **_engine_options())

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


class Base(DeclarativeBase):
    """ORM 声明式基类。所有模型（含 BaseModel）的元数据汇聚于此。"""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供一个数据库会话，请求结束后自动关闭。

    用法::

        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
