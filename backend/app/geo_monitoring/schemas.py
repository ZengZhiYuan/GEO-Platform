"""AI 应用监测请求与响应 Schema。"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


# 去除首尾空白并校验非空字符串。
def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("不能为空")
    return value


# 去除可选字符串首尾空白，空串转为 None。
def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class BrandType(StrEnum):
    TARGET = "target"
    COMPETITOR = "competitor"
    CANDIDATE = "candidate"


class EntityStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class AliasMatchMode(StrEnum):
    EXACT = "exact"
    CONTAINS = "contains"
    CONTEXT = "context"


class PromptSetStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class RunStatus(StrEnum):
    PENDING = "pending"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    REPORTING = "reporting"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueryTaskStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectCreate(BaseModel):
    project_name: str = Field(max_length=100)
    industry: str = Field(default="文旅演艺", max_length=100)
    description: str | None = None
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    official_domain: str | None = Field(default=None, max_length=255)
    report_title: str | None = Field(default=None, max_length=255)
    report_subtitle: str | None = Field(default=None, max_length=500)

    @field_validator("project_name", "industry", "timezone")
    @classmethod
    # 校验并规范化必填字符串字段。
    def strip_required(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator(
        "description",
        "official_domain",
        "report_title",
        "report_subtitle",
    )
    @classmethod
    # 规范化可选字符串字段。
    def strip_optional(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ProjectUpdate(BaseModel):
    project_name: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=100)
    description: str | None = None
    timezone: str | None = Field(default=None, max_length=64)
    status: ProjectStatus | None = None
    official_domain: str | None = Field(default=None, max_length=255)
    report_title: str | None = Field(default=None, max_length=255)
    report_subtitle: str | None = Field(default=None, max_length=500)

    @field_validator("project_name", "industry", "timezone")
    @classmethod
    # 更新时若提供则校验并规范化必填字段。
    def strip_required_when_present(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None

    @field_validator(
        "description",
        "official_domain",
        "report_title",
        "report_subtitle",
    )
    @classmethod
    # 更新时规范化可选字符串字段。
    def strip_optional(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_name: str
    industry: str
    description: str | None
    timezone: str
    status: str
    official_domain: str | None
    report_title: str | None
    report_subtitle: str | None
    created_at: datetime
    updated_at: datetime


class BrandCreate(BaseModel):
    brand_name: str = Field(max_length=255)
    brand_type: BrandType = BrandType.COMPETITOR
    official_domain: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: EntityStatus = EntityStatus.ACTIVE

    @field_validator("brand_name")
    @classmethod
    # 校验并规范化品牌名称。
    def strip_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("official_domain", "description")
    @classmethod
    # 规范化品牌可选字符串字段。
    def strip_optional(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class BrandUpdate(BaseModel):
    brand_name: str | None = Field(default=None, max_length=255)
    brand_type: BrandType | None = None
    official_domain: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: EntityStatus | None = None

    @field_validator("brand_name")
    @classmethod
    # 更新时若提供则校验并规范化品牌名称。
    def strip_name(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None

    @field_validator("official_domain", "description")
    @classmethod
    # 更新时规范化品牌可选字符串字段。
    def strip_optional(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    brand_name: str
    brand_type: str
    official_domain: str | None
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class BrandAliasCreate(BaseModel):
    alias_name: str = Field(max_length=255)
    match_mode: AliasMatchMode = AliasMatchMode.CONTAINS
    is_ambiguous: bool = False
    context_keywords: list[str] = Field(default_factory=list)
    enabled: bool = True

    @field_validator("alias_name")
    @classmethod
    # 校验并规范化别名名称。
    def strip_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("context_keywords")
    @classmethod
    # 去重并去除上下文关键词首尾空白。
    def normalize_keywords(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class BrandAliasUpdate(BaseModel):
    alias_name: str | None = Field(default=None, max_length=255)
    match_mode: AliasMatchMode | None = None
    is_ambiguous: bool | None = None
    context_keywords: list[str] | None = None
    enabled: bool | None = None

    @field_validator("alias_name")
    @classmethod
    # 更新时若提供则校验并规范化别名名称。
    def strip_name(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None

    @field_validator("context_keywords")
    @classmethod
    # 更新时去重并规范化上下文关键词列表。
    def normalize_keywords(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class BrandAliasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand_id: int
    alias_name: str
    match_mode: str
    is_ambiguous: bool
    context_keywords: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class PromptSetCreate(BaseModel):
    set_name: str = Field(max_length=100)
    version_no: str = Field(max_length=50)

    @field_validator("set_name", "version_no")
    @classmethod
    # 校验并规范化 Prompt 集名称与版本号。
    def strip_required(cls, value: str) -> str:
        return _strip_required(value)


class PromptSetUpdate(BaseModel):
    set_name: str | None = Field(default=None, max_length=100)

    @field_validator("set_name")
    @classmethod
    # 更新时若提供则校验并规范化 Prompt 集名称。
    def strip_name(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None


class PromptSetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    set_name: str
    version_no: str
    status: str
    prompt_count: int
    checksum: str | None
    activated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PromptCreate(BaseModel):
    prompt_code: str = Field(max_length=64)
    prompt_text: str
    prompt_type: str = Field(default="generic", max_length=50)
    scene_tag: str | None = Field(default=None, max_length=100)
    contains_brand: bool = False
    enabled: bool = True
    sort_order: int = 0

    @field_validator("prompt_code", "prompt_text", "prompt_type")
    @classmethod
    # 校验并规范化 Prompt 必填字段。
    def strip_required(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("scene_tag")
    @classmethod
    # 规范化 Prompt 场景标签。
    def strip_scene(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class PromptUpdate(BaseModel):
    prompt_code: str | None = Field(default=None, max_length=64)
    prompt_text: str | None = None
    prompt_type: str | None = Field(default=None, max_length=50)
    scene_tag: str | None = Field(default=None, max_length=100)
    contains_brand: bool | None = None
    enabled: bool | None = None
    sort_order: int | None = None

    @field_validator("prompt_code", "prompt_text", "prompt_type")
    @classmethod
    # 更新时若提供则校验并规范化 Prompt 必填字段。
    def strip_required_when_present(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None

    @field_validator("scene_tag")
    @classmethod
    # 更新时规范化 Prompt 场景标签。
    def strip_scene(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class PromptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt_set_id: int
    prompt_code: str
    prompt_text: str
    prompt_type: str
    scene_tag: str | None
    contains_brand: bool
    enabled: bool
    sort_order: int
    content_hash: str | None
    created_at: datetime
    updated_at: datetime


class AIPlatformUpdate(BaseModel):
    platform_name: str | None = Field(default=None, max_length=100)
    adapter_type: str | None = Field(default=None, max_length=50)
    base_url: str | None = Field(default=None, max_length=500)
    model_name: str | None = Field(default=None, max_length=255)
    search_enabled: bool | None = None
    citation_supported: bool | None = None
    max_concurrency: int | None = Field(default=None, gt=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
    enabled: bool | None = None
    extra_config: dict[str, Any] | None = None

    @field_validator("platform_name", "adapter_type")
    @classmethod
    # 更新时若提供则校验并规范化平台名称与适配器类型。
    def strip_required_when_present(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None

    @field_validator("base_url", "model_name")
    @classmethod
    # 更新时规范化平台 URL 与模型名称。
    def strip_optional(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class AIPlatformOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_code: str
    platform_name: str
    adapter_type: str
    base_url: str | None
    model_name: str | None
    search_enabled: bool
    citation_supported: bool
    max_concurrency: int
    timeout_seconds: int
    enabled: bool
    extra_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RunCreate(BaseModel):
    project_id: int = Field(ge=1)
    prompt_set_id: int | None = Field(default=None, ge=1)
    platform_codes: list[str] | None = None

    @field_validator("platform_codes")
    @classmethod
    # 去重并校验平台编码列表非空。
    def normalize_platform_codes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = list(dict.fromkeys(code.strip() for code in value if code.strip()))
        if not normalized:
            raise ValueError("platform_codes 不能为空")
        return normalized


class MonitorRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_no: str
    project_id: int
    prompt_set_id: int
    prompt_set_version: str
    trigger_type: str
    triggered_by: int | None = None
    status: str
    collection_status: str
    analysis_status: str
    report_status: str
    platform_codes: list[str]
    expected_query_count: int
    total_tasks: int = 0
    succeeded_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    success_query_count: int
    failed_query_count: int
    valid_answer_count: int
    data_completeness_rate: Decimal
    result_json: dict | None
    error_message: str | None
    error_summary: str | None = None
    started_at: datetime | None
    completed_at: datetime | None = None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RunDetailRead(MonitorRunOut):
    """运行详情，包含任务计数与进度摘要。"""

    progress_rate: Decimal = Decimal("0")


class QueryTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    prompt_id: int
    platform_code: str
    idempotency_key: str
    status: str
    key_slot: int | None
    retry_count: int
    attempt_count: int = 0
    max_attempts: int = 3
    request_json: dict | None
    response_http_status: int | None
    error_code: str | None
    error_message: str | None
    last_error_code: str | None = None
    last_error_message: str | None = None
    provider_request_id: str | None = None
    latency_ms: int | None
    queued_at: datetime | None = None
    started_at: datetime | None
    completed_at: datetime | None = None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    answer_id: int
    citation_no: int
    title: str | None
    url: str | None
    domain: str | None
    source_type: str | None
    quoted_text: str | None


class BrandResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    answer_id: int
    brand_id: int
    is_mentioned: bool
    mention_count: int
    first_position: int | None
    sentiment: str | None
    context_json: dict[str, Any]


class AnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    platform_code: str
    prompt_id: int
    raw_text: str
    normalized_text: str | None
    model_name: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int | None
    collected_at: datetime
    created_at: datetime
    updated_at: datetime


class AnswerDetailRead(AnswerRead):
    citations: list[CitationRead] = Field(default_factory=list)
    brand_results: list[BrandResultRead] = Field(default_factory=list)


class AnswerCreate(BaseModel):
    task_id: int = Field(ge=1)
    platform_code: str = Field(min_length=1, max_length=32)
    prompt_id: int = Field(ge=1)
    raw_text: str
    normalized_text: str | None = None
    model_name: str | None = Field(default=None, max_length=255)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    raw_response_json: dict[str, Any] | None = None

    @field_validator("raw_text")
    @classmethod
    # 校验并规范化回答原始文本非空。
    def strip_raw_text(cls, value: str) -> str:
        return _strip_required(value)


class MisfirePolicy(StrEnum):
    FIRE_ONCE = "fire_once"
    IGNORE = "ignore"


class ScheduleCreate(BaseModel):
    name: str = Field(max_length=100)
    cron_expr: str = Field(max_length=100)
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    enabled: bool = True
    misfire_policy: MisfirePolicy = MisfirePolicy.FIRE_ONCE

    @field_validator("name", "cron_expr", "timezone")
    @classmethod
    # 校验并规范化调度计划名称、cron 表达式与时区。
    def strip_required(cls, value: str) -> str:
        return _strip_required(value)


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    cron_expr: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=64)
    enabled: bool | None = None
    misfire_policy: MisfirePolicy | None = None

    @field_validator("name", "cron_expr", "timezone")
    @classmethod
    # 更新时若提供则校验并规范化调度字段。
    def strip_optional(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    cron_expr: str
    timezone: str
    enabled: bool
    misfire_policy: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
