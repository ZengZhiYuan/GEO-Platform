"""应用配置。

通过 pydantic-settings 读取环境变量 / .env 文件。
TASK-0002 阶段只声明应用级基础配置；数据库、Redis、AI 等配置
在后续任务（TASK-0101 等）按需补充。.env 中多余的键通过 extra="ignore" 忽略。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 同时兼容从项目根目录或 backend/ 目录启动的两种情况
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    APP_NAME: str = "shipu-geo"
    APP_ENV: str = "local"
    APP_DEBUG: bool = True

    # 后端服务
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # 接口前缀
    API_PREFIX: str = "/api"

    # 数据库（默认值与根目录 .env.example 保持一致）
    DATABASE_URL: str = (
        "postgresql+psycopg2://shipu_geo:shipu_geo_password@localhost:5432/shipu_geo"
    )
    # SQLAlchemy 引擎选项
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True

    # Redis / 异步任务（TASK-0401）
    # Dramatiq broker 地址（Redis）；与 .env.example 的 REDIS_URL 对齐
    REDIS_URL: str = "redis://localhost:6379/0"
    # broker 类型：redis（默认）/ stub（内存，供测试或无 Redis 环境）
    DRAMATIQ_BROKER: str = "redis"
    # 文章生成失败的最大重试次数（Dramatiq actor max_retries）
    ARTICLE_MAX_RETRIES: int = 3

    # AI 生成（第一版 Mock，见 docs/decisions.md 004）
    AI_PROVIDER: str = "mock"
    # MockAIWriter 模拟生成耗时（秒），默认 0 不阻塞
    AI_MOCK_DELAY_SECONDS: float = 0.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
