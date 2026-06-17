"""AI 应用监测服务配置。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class YuanbaoCredential(BaseModel):
    secret_id: str
    secret_key: str


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


def _parse_comma_separated_keys(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(",")
    seen: set[str] = set()
    parsed: list[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        parsed.append(key)
    return parsed


def _parse_yuanbao_credentials(value: Any) -> list[YuanbaoCredential]:
    if value is None or value == "" or value == "[]":
        return []
    if isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("YUANBAO_CREDENTIALS_JSON must be a JSON array") from exc
    elif isinstance(value, list):
        raw = value
    else:
        raise ValueError("YUANBAO_CREDENTIALS_JSON must be a JSON array")
    if not isinstance(raw, list):
        raise ValueError("YUANBAO_CREDENTIALS_JSON must be a JSON array")
    credentials: list[YuanbaoCredential] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(
                f"YUANBAO_CREDENTIALS_JSON[{index}] must be an object with "
                "secret_id and secret_key"
            )
        secret_id = str(item.get("secret_id", "")).strip()
        secret_key = str(item.get("secret_key", "")).strip()
        if not secret_id or not secret_key:
            raise ValueError(
                f"YUANBAO_CREDENTIALS_JSON[{index}] must include non-empty "
                "secret_id and secret_key"
            )
        credentials.append(
            YuanbaoCredential(secret_id=secret_id, secret_key=secret_key)
        )
    return credentials


def _ensure_report_storage_dir(value: str) -> str:
    path = Path(value)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(f"REPORT_STORAGE_DIR is not creatable: {exc}") from exc
    return value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class Settings(BaseSettings):
    # 同时兼容从项目根目录或 backend/ 目录启动的两种情况
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # 应用
    APP_NAME: str = "ai-application-monitoring"
    APP_ENV: str = "dev"
    DEBUG: bool = Field(default=False, validation_alias=AliasChoices("DEBUG", "APP_DEBUG"))

    # 后端服务
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # 接口前缀
    API_PREFIX: str = "/api"

    # 数据库：本地运行必须从 .env 提供，禁止在代码中硬编码服务器地址。
    DATABASE_URL: str = Field(...)
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True

    # Redis / 异步任务基础设施
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

    # 采集
    COLLECTION_REQUEST_TIMEOUT_SECONDS: int = 60
    COLLECTION_MAX_ATTEMPTS: int = 3
    COLLECTION_RETRY_BASE_SECONDS: int = 2
    COLLECTION_MAX_CONCURRENCY: int = 10
    COLLECTION_RAW_RESPONSE_ENABLED: bool = True

    # 平台适配器
    DOUBAO_ENABLED: bool = False
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL: str = ""
    DOUBAO_API_KEYS: str = ""

    QWEN_ENABLED: bool = False
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = ""
    QWEN_API_KEYS: str = ""

    YUANBAO_ENABLED: bool = False
    YUANBAO_BASE_URL: str = "https://hunyuan.tencentcloudapi.com"
    YUANBAO_MODEL: str = ""
    YUANBAO_CREDENTIALS_JSON: str = "[]"

    DEEPSEEK_ENABLED: bool = False
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = ""
    DEEPSEEK_API_KEYS: str = ""

    KIMI_ENABLED: bool = False
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = ""
    KIMI_API_KEYS: str = ""

    # Agent LLM
    AGENT_LLM_BASE_URL: str = ""
    AGENT_LLM_API_KEY: str = ""
    AGENT_LLM_MODEL: str = ""
    AGENT_LLM_TIMEOUT_SECONDS: int = 90
    AGENT_LLM_MAX_ATTEMPTS: int = 2

    # 调度
    SCHEDULER_ENABLED: bool = False
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"
    SCHEDULER_POLL_SECONDS: int = 30

    # 报告
    REPORT_STORAGE_DIR: str = "./data/reports"
    REPORT_PUBLIC_BASE_URL: str = ""
    REPORT_RETENTION_DAYS: int = 90

    @property
    def APP_DEBUG(self) -> bool:
        return self.DEBUG

    def parsed_api_keys(self, raw_value: str) -> list[str]:
        return _parse_comma_separated_keys(raw_value)

    def parsed_yuanbao_credentials(self) -> list[YuanbaoCredential]:
        return _parse_yuanbao_credentials(self.YUANBAO_CREDENTIALS_JSON)

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return _validate_url_scheme(value, "DATABASE_URL", ("postgresql", "sqlite"))

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        return _validate_url_scheme(value, "REDIS_URL", ("redis", "rediss"))

    @field_validator(
        "DOUBAO_API_KEYS",
        "QWEN_API_KEYS",
        "DEEPSEEK_API_KEYS",
        "KIMI_API_KEYS",
        mode="before",
    )
    @classmethod
    def normalize_api_keys_raw(cls, value: str | list[str] | None) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return ",".join(value)
        return str(value)

    @field_validator("YUANBAO_CREDENTIALS_JSON", mode="before")
    @classmethod
    def normalize_yuanbao_credentials_raw(cls, value: Any) -> str:
        if value is None or value == "":
            return "[]"
        if isinstance(value, str):
            cls._validate_yuanbao_credentials_json_array(value)
            return value
        if isinstance(value, list):
            serialized = json.dumps(value)
            cls._validate_yuanbao_credentials_json_array(serialized)
            return serialized
        raise ValueError("YUANBAO_CREDENTIALS_JSON must be a JSON array")

    @staticmethod
    def _validate_yuanbao_credentials_json_array(value: str) -> None:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("YUANBAO_CREDENTIALS_JSON must be a JSON array") from exc
        if not isinstance(parsed, list):
            raise ValueError("YUANBAO_CREDENTIALS_JSON must be a JSON array")

    @field_validator("NACOS_SERVER_ADDRESSES", "NACOS_NAMESPACE", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None or not isinstance(value, str):
            return value
        return _optional_text(value)

    @field_validator("NACOS_USERNAME", "NACOS_PASSWORD", "NACOS_ACCESS_TOKEN", mode="before")
    @classmethod
    def normalize_optional_secret_text(cls, value: str | None) -> str | None:
        if value is None or not isinstance(value, str):
            return value
        return _optional_text(value)

    @field_validator("NACOS_SERVER_ADDRESSES")
    @classmethod
    def validate_nacos_server_addresses(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_nacos_addresses(value)

    @field_validator("REPORT_STORAGE_DIR")
    @classmethod
    def validate_report_storage_dir(cls, value: str) -> str:
        return _ensure_report_storage_dir(value)

    @field_validator(
        "COLLECTION_REQUEST_TIMEOUT_SECONDS",
        "COLLECTION_MAX_ATTEMPTS",
        "COLLECTION_RETRY_BASE_SECONDS",
        "COLLECTION_MAX_CONCURRENCY",
        "AGENT_LLM_TIMEOUT_SECONDS",
        "AGENT_LLM_MAX_ATTEMPTS",
        "SCHEDULER_POLL_SECONDS",
        "REPORT_RETENTION_DAYS",
    )
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be greater than 0")
        return value

    @field_validator("SCHEDULER_TIMEZONE")
    @classmethod
    def validate_scheduler_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"SCHEDULER_TIMEZONE is invalid: {value}") from exc
        return value

    @model_validator(mode="after")
    def validate_runtime_contract(self) -> Settings:
        if self.NACOS_ENABLED and not self.NACOS_SERVER_ADDRESSES:
            raise ValueError("NACOS_SERVER_ADDRESSES is required when NACOS_ENABLED=true")

        api_key_platforms = (
            ("DOUBAO", self.DOUBAO_ENABLED, self.DOUBAO_MODEL, self.DOUBAO_API_KEYS),
            ("QWEN", self.QWEN_ENABLED, self.QWEN_MODEL, self.QWEN_API_KEYS),
            ("DEEPSEEK", self.DEEPSEEK_ENABLED, self.DEEPSEEK_MODEL, self.DEEPSEEK_API_KEYS),
            ("KIMI", self.KIMI_ENABLED, self.KIMI_MODEL, self.KIMI_API_KEYS),
        )
        for prefix, enabled, model, api_keys_raw in api_key_platforms:
            if not enabled:
                continue
            if not model.strip():
                raise ValueError(f"{prefix}_MODEL is required when {prefix}_ENABLED=true")
            if not self.parsed_api_keys(api_keys_raw):
                raise ValueError(f"{prefix}_API_KEYS is required when {prefix}_ENABLED=true")

        if self.YUANBAO_ENABLED:
            if not self.YUANBAO_MODEL.strip():
                raise ValueError("YUANBAO_MODEL is required when YUANBAO_ENABLED=true")
            try:
                credentials = self.parsed_yuanbao_credentials()
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
            if not credentials:
                raise ValueError(
                    "YUANBAO_CREDENTIALS_JSON is required when YUANBAO_ENABLED=true"
                )

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

    def runtime_summary(self) -> dict[str, Any]:
        return {
            "app_env": self.APP_ENV,
            "debug": self.DEBUG,
            **self.connection_targets_summary(),
            "collection": {
                "request_timeout_seconds": self.COLLECTION_REQUEST_TIMEOUT_SECONDS,
                "max_attempts": self.COLLECTION_MAX_ATTEMPTS,
                "retry_base_seconds": self.COLLECTION_RETRY_BASE_SECONDS,
                "max_concurrency": self.COLLECTION_MAX_CONCURRENCY,
                "raw_response_enabled": self.COLLECTION_RAW_RESPONSE_ENABLED,
            },
            "platforms": {
                "doubao": self._platform_summary(
                    self.DOUBAO_ENABLED,
                    self.DOUBAO_BASE_URL,
                    self.DOUBAO_MODEL,
                    len(self.parsed_api_keys(self.DOUBAO_API_KEYS)),
                ),
                "qwen": self._platform_summary(
                    self.QWEN_ENABLED,
                    self.QWEN_BASE_URL,
                    self.QWEN_MODEL,
                    len(self.parsed_api_keys(self.QWEN_API_KEYS)),
                ),
                "yuanbao": {
                    "enabled": self.YUANBAO_ENABLED,
                    "base_url": self.YUANBAO_BASE_URL,
                    "model": self.YUANBAO_MODEL or None,
                    "credential_count": len(self.parsed_yuanbao_credentials()),
                },
                "deepseek": self._platform_summary(
                    self.DEEPSEEK_ENABLED,
                    self.DEEPSEEK_BASE_URL,
                    self.DEEPSEEK_MODEL,
                    len(self.parsed_api_keys(self.DEEPSEEK_API_KEYS)),
                ),
                "kimi": self._platform_summary(
                    self.KIMI_ENABLED,
                    self.KIMI_BASE_URL,
                    self.KIMI_MODEL,
                    len(self.parsed_api_keys(self.KIMI_API_KEYS)),
                ),
            },
            "agent_llm": {
                "base_url": self.AGENT_LLM_BASE_URL or None,
                "model": self.AGENT_LLM_MODEL or None,
                "timeout_seconds": self.AGENT_LLM_TIMEOUT_SECONDS,
                "max_attempts": self.AGENT_LLM_MAX_ATTEMPTS,
                "has_api_key": bool(self.AGENT_LLM_API_KEY.strip()),
            },
            "scheduler": {
                "enabled": self.SCHEDULER_ENABLED,
                "timezone": self.SCHEDULER_TIMEZONE,
                "poll_seconds": self.SCHEDULER_POLL_SECONDS,
            },
            "report": {
                "storage_dir": self.REPORT_STORAGE_DIR,
                "public_base_url": self.REPORT_PUBLIC_BASE_URL or None,
                "retention_days": self.REPORT_RETENTION_DAYS,
            },
        }

    @staticmethod
    def _platform_summary(
        enabled: bool, base_url: str, model: str, api_key_count: int
    ) -> dict[str, Any]:
        return {
            "enabled": enabled,
            "base_url": base_url,
            "model": model or None,
            "api_key_count": api_key_count,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
