"""Alembic 迁移运行环境。

- 数据库地址从 ``app.core.config.settings.DATABASE_URL`` 读取。
- 目标元数据为 ``app.models.Base.metadata``；导入 ``app.models`` 包
  以确保所有模型被注册，autogenerate 才能感知表结构。
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings

# 导入公共基类与业务模型，填充 Base.metadata
import app.geo_monitoring.models  # noqa: F401
from app.models import Base

# Alembic 配置对象
config = context.config

# 用应用配置中的 DATABASE_URL 覆盖 alembic.ini 中的占位
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：仅根据 URL 生成 SQL，不实际连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库并执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
