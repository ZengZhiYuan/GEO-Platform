"""AI 应用监测服务配置。"""

from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _url_target_summary(value: str) -> str:
    parsed = urlparse(value)
    netloc = parsed.hostname or ""
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    path = parsed.path or ""
    return f"{parsed.scheme}://{netloc}{path}"


def _validate_url_scheme(
    value: str, field_name: str, allowed_prefixes: tuple[str, ...]
) -> str:
    parsed = urlparse(value)
    if not parsed.scheme:
        raise ValueError(f"{field_name} must be a valid URL")
    if not any(
        parsed.scheme == prefix or parsed.scheme.startswith(f"{prefix}+")
        for prefix in allowed_prefixes
    ):
        allowed = ", ".join(allowed_prefixes)
        raise ValueError(f"{field_name} scheme must start with one of: {allowed}")
    if parsed.scheme.startswith("sqlite"):
        return value
    if not parsed.hostname:
        raise ValueError(f"{field_name} must include a host")
    return value


def _validate_nacos_addresses(value: str) -> str:
    for address in value.split(","):
        address = address.strip()
        if not address:
            raise ValueError("NACOS_SERVER_ADDRESSES contains an empty address")
        if "://" in address or "/" in address:
            raise ValueError("NACOS_SERVER_ADDRESSES must use host:port entries")
        host, separator, port = address.rpartition(":")
        if not host or separator != ":" or not port.isdigit():
            raise ValueError("NACOS_SERVER_ADDRESSES must use host:port entries")
    return value


class Settings(BaseSettings):
    # 同时兼容从项目根目录或 backend/ 目录启动的两种情况
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    APP_NAME: str = "ai-application-monitoring"
    APP_ENV: str = "local"
    APP_DEBUG: bool = True

    # 后端服务
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # 接口前缀
    API_PREFIX: str = "/api"

    # 数据库：本地运行必须从 .env 提供，禁止在代码中硬编码服务器地址。
    DATABASE_URL: str = Field(...)
    # SQLAlchemy 引擎选项
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True

    # Redis / 异步任务基础设施，供后续采集 Worker 使用。
    REDIS_URL: str = Field(...)
    DRAMATIQ_BROKER: str = "redis"

    # Nacos：默认禁用；本地联调从 .env 显式开启并提供服务地址。
    NACOS_ENABLED: bool = False
    NACOS_SERVER_ADDRESSES: str | None = None
    NACOS_NAMESPACE: str | None = None
    NACOS_GROUP: str = "DEFAULT_GROUP"
    NACOS_USERNAME: str | None = None
    NACOS_PASSWORD: str | None = None
    NACOS_ACCESS_TOKEN: str | None = None
    NACOS_CONFIG_DATA_ID: str | None = None

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return _validate_url_scheme(value, "DATABASE_URL", ("postgresql", "sqlite"))

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        return _validate_url_scheme(value, "REDIS_URL", ("redis", "rediss"))

    @field_validator("NACOS_SERVER_ADDRESSES")
    @classmethod
    def validate_nacos_server_addresses(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        return _validate_nacos_addresses(value)

    @model_validator(mode="after")
    def validate_nacos_enabled(self) -> "Settings":
        if self.NACOS_ENABLED and not self.NACOS_SERVER_ADDRESSES:
            raise ValueError("NACOS_SERVER_ADDRESSES is required when NACOS_ENABLED=true")
        return self

    def connection_targets_summary(self) -> dict[str, Any]:
        return {
            "database": _url_target_summary(self.DATABASE_URL),
            "redis": _url_target_summary(self.REDIS_URL),
            "nacos": {
                "enabled": self.NACOS_ENABLED,
                "servers": self.NACOS_SERVER_ADDRESSES,
                "namespace": self.NACOS_NAMESPACE,
                "group": self.NACOS_GROUP,
                "data_id": self.NACOS_CONFIG_DATA_ID,
            },
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
