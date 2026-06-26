"""AI 应用监测请求与响应 Schema。"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class CollectionSource(StrEnum):
    OFFICIAL = "official"
    AIDSO = "aidso"


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
    default_platform_codes: list[str] = Field(default_factory=list)
    monitoring_paused: bool = False
    created_at: datetime
    updated_at: datetime


class ProjectOptionRead(BaseModel):
    id: int
    project_name: str
    status: str
    monitoring_paused: bool = False


class ProjectOverviewLatestRunRead(BaseModel):
    run_id: int
    run_no: str
    status: str
    collection_status: str
    analysis_status: str
    completed_at: datetime | None = None


class ProjectOverviewItemRead(BaseModel):
    id: int
    project_name: str
    industry: str
    status: str
    monitoring_paused: bool = False
    target_brand_name: str | None = None
    brand_word_count: int = 0
    competitor_count: int = 0
    question_count: int = 0
    platform_count: int = 0
    endpoint_count: int = 0
    selected_platform_codes: list[str] = Field(default_factory=list)
    latest_run: ProjectOverviewLatestRunRead | None = None
    updated_at: datetime


class ProjectDeleteCheckRead(BaseModel):
    project_id: int
    run_count: int = 0
    report_count: int = 0
    schedule_count: int = 0
    can_delete: bool = True
    blocking_reasons: list[str] = Field(default_factory=list)


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
    core_keyword_id: int | None = Field(default=None, ge=1)
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
    core_keyword_id: int | None = Field(default=None, ge=1)
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
    core_keyword_id: int | None = None
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


class PlatformEndpointOut(BaseModel):
    platform_code: str
    platform_name: str
    base_platform: str
    base_platform_label: str
    endpoint_type: str
    endpoint_label: str
    logo_url: str | None = None
    thinking_mode: str | None = None
    enabled: bool
    adapter_type: str
    search_enabled: bool
    citation_supported: bool


class PlatformEndpointGroupOut(BaseModel):
    base_platform: str
    base_platform_label: str
    endpoints: list[PlatformEndpointOut]


class PlatformEndpointsOut(BaseModel):
    groups: list[PlatformEndpointGroupOut]


class PromptTypeOut(BaseModel):
    code: str
    label: str
    compatible_values: list[str]


class PromptTypesOut(BaseModel):
    items: list[PromptTypeOut]


class SourceTypeOut(BaseModel):
    code: str
    label: str


class SourceTypeStorageMappingOut(BaseModel):
    storage_value: str
    display_code: str
    display_label: str


class SourceTypesOut(BaseModel):
    items: list[SourceTypeOut]
    storage_mappings: list[SourceTypeStorageMappingOut]


class AiBrandWordsGenerateIn(BaseModel):
    brand_name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    official_domain: str | None = Field(default=None, max_length=255)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("brand_name", mode="before")
    @classmethod
    def strip_brand_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("category", "official_domain")
    @classmethod
    def strip_optional_fields(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class AiBrandWordsGenerateOut(BaseModel):
    brand_words: list[str]


class AiCompetitorsGenerateIn(BaseModel):
    brand_name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("brand_name", mode="before")
    @classmethod
    def strip_brand_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("category", "region")
    @classmethod
    def strip_optional_fields(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class AiCompetitorCandidateOut(BaseModel):
    brand_name: str
    competitor_words: list[str]
    official_domain: str | None = None


class AiCompetitorsGenerateOut(BaseModel):
    competitors: list[AiCompetitorCandidateOut]


class AiQuestionsGenerateIn(BaseModel):
    brand_name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    core_keywords: list[str] = Field(default_factory=list, max_length=20)
    competitors: list[str] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("brand_name", mode="before")
    @classmethod
    def strip_brand_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("category", "region")
    @classmethod
    def strip_optional_fields(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("core_keywords", "competitors")
    @classmethod
    def normalize_keyword_lists(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            cleaned = item.strip()
            if not cleaned:
                continue
            if len(cleaned) > 100:
                raise ValueError("单项长度不能超过 100")
            normalized.append(cleaned)
        return list(dict.fromkeys(normalized))


class AiGeneratedQuestionOut(BaseModel):
    prompt_text: str
    prompt_type: str
    core_keyword: str | None = None


class AiQuestionsGenerateOut(BaseModel):
    questions: list[AiGeneratedQuestionOut]


class RunCreate(BaseModel):
    project_id: int = Field(ge=1)
    prompt_set_id: int | None = Field(default=None, ge=1)
    platform_codes: list[str] | None = None
    collection_source: CollectionSource = CollectionSource.OFFICIAL
    aidso_thinking_enabled_by_platform: dict[str, bool] = Field(default_factory=dict)

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

    @field_validator("aidso_thinking_enabled_by_platform")
    @classmethod
    # 按平台码规范化 Aidso 深度思考开关，未配置的平台在采集时默认开启。
    def normalize_aidso_thinking_enabled_by_platform(
        cls, value: dict[str, bool]
    ) -> dict[str, bool]:
        return {code.strip(): enabled for code, enabled in value.items() if code.strip()}

    @model_validator(mode="after")
    def validate_aidso_thinking_enabled_platforms(self) -> "RunCreate":
        if not self.aidso_thinking_enabled_by_platform:
            return self

        from app.geo_monitoring.services.platforms import AIDSO_PLATFORM_MAPPINGS

        configured = set(self.aidso_thinking_enabled_by_platform)
        unknown = configured - set(AIDSO_PLATFORM_MAPPINGS)
        if unknown:
            raise ValueError("aidso_thinking_enabled_by_platform 包含无效 Aidso 平台编码")

        if self.platform_codes is not None:
            outside_request = configured - set(self.platform_codes)
            if outside_request:
                raise ValueError(
                    "aidso_thinking_enabled_by_platform 只能配置本次 platform_codes 内的平台"
                )

        return self


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
    collection_source: str = "official"
    aidso_thinking_enabled_by_platform: dict[str, bool] = Field(default_factory=dict)
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
    prompt_text: str
    prompt_type: str
    reasoning_text: str | None = None
    search_keywords: list[str] = Field(default_factory=list)
    raw_response_safe: dict[str, Any] | None = None
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


class CoreKeywordCreate(BaseModel):
    keyword: str = Field(max_length=100)
    description: str | None = None
    sort_order: int = 0
    enabled: bool = True

    @field_validator("keyword")
    @classmethod
    def strip_keyword(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class CoreKeywordUpdate(BaseModel):
    keyword: str | None = Field(default=None, max_length=100)
    description: str | None = None
    sort_order: int | None = None
    enabled: bool | None = None

    @field_validator("keyword")
    @classmethod
    def strip_keyword(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class CoreKeywordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    keyword: str
    description: str | None
    sort_order: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class PromptLibraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt_code: str
    prompt_text: str
    prompt_type: str
    industry: str | None
    scene_tag: str | None
    default_core_keyword: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class MonitorSetupBrandInput(BaseModel):
    brand_name: str = Field(max_length=255)
    official_domain: str | None = Field(default=None, max_length=255)
    description: str | None = None
    brand_words: list[str] = Field(default_factory=list)

    @field_validator("brand_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("official_domain", "description")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("brand_words")
    @classmethod
    def normalize_words(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class MonitorSetupCompetitorInput(BaseModel):
    brand_name: str = Field(max_length=255)
    competitor_words: list[str] = Field(default_factory=list)

    @field_validator("brand_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("competitor_words")
    @classmethod
    def normalize_words(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class MonitorSetupCoreKeywordInput(BaseModel):
    keyword: str = Field(max_length=100)
    description: str | None = None
    sort_order: int = 0
    enabled: bool = True

    @field_validator("keyword")
    @classmethod
    def strip_keyword(cls, value: str) -> str:
        return _strip_required(value)


class MonitorSetupQuestionInput(BaseModel):
    core_keyword: str | None = Field(default=None, max_length=100)
    prompt_text: str | None = None
    prompt_type: str | None = Field(default=None, max_length=50)
    prompt_code: str | None = Field(default=None, max_length=64)
    library_prompt_code: str | None = Field(default=None, max_length=64)

    @field_validator("core_keyword", "prompt_type", "prompt_code", "library_prompt_code")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class MonitorSetupSave(BaseModel):
    brand: MonitorSetupBrandInput | None = None
    competitors: list[MonitorSetupCompetitorInput] = Field(default_factory=list)
    core_keywords: list[MonitorSetupCoreKeywordInput] = Field(default_factory=list)
    ai_questions: list[MonitorSetupQuestionInput] = Field(default_factory=list)
    selected_platform_codes: list[str] = Field(default_factory=list)
    activate_prompt_set: bool = False

    @field_validator("selected_platform_codes")
    @classmethod
    def normalize_platform_codes(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(code.strip() for code in value if code.strip()))


class ProjectSetupCreate(BaseModel):
    project: ProjectCreate
    monitor_setup: MonitorSetupSave
    run_after_create: bool = False


class ProjectSetupOut(BaseModel):
    project: ProjectOut
    monitor_setup: dict[str, Any]
    run: MonitorRunOut | None = None


class ConversationSentimentSummary(BaseModel):
    positive: int = 0
    neutral: int = 0
    negative: int = 0


class ConversationPlatformMetricsRead(BaseModel):
    platform_code: str
    valid_answer_count: int
    visibility_rate: str | None = None
    mention_count: int
    brand_mention_total_count: int | None = None
    average_rank: str | None = None
    top1_rate: str | None = None
    top3_rate: str | None = None
    top10_rate: str | None = None
    share_of_voice: str | None = None
    positive_rate: str | None = None
    neutral_rate: str | None = None
    negative_rate: str | None = None
    sentiment: ConversationSentimentSummary


class ConversationQuestionRead(BaseModel):
    prompt_id: int
    prompt_text: str
    prompt_type: str
    run_id: int
    valid_answer_count: int
    visibility_rate: str | None = None
    mention_count: int
    brand_mention_total_count: int | None = None
    average_rank: str | None = None
    top1_rate: str | None = None
    top3_rate: str | None = None
    top10_rate: str | None = None
    share_of_voice: str | None = None
    positive_rate: str | None = None
    neutral_rate: str | None = None
    negative_rate: str | None = None
    sentiment: ConversationSentimentSummary
    platform_metrics: list[ConversationPlatformMetricsRead] = Field(default_factory=list)


class ConversationAnswerBrandResultRead(BaseModel):
    brand_id: int
    brand_name: str
    is_mentioned: bool
    mention_count: int
    first_position: int | None = None
    sentiment: str | None = None


class ConversationAnswerRead(BaseModel):
    answer_id: int
    platform_code: str
    prompt_id: int
    prompt_text: str
    prompt_type: str
    raw_text: str
    normalized_text: str | None = None
    collected_at: datetime
    reasoning_text: str | None = None
    search_keywords: list[str] = Field(default_factory=list)
    citations: list[CitationRead] = Field(default_factory=list)
    brand_results: list[ConversationAnswerBrandResultRead] = Field(default_factory=list)


class SourceAnalysisKpiRead(BaseModel):
    citation_count: int
    site_count: int
    article_count: int
    citation_rate: str | None = None


class SourceAnalysisTypeDistributionRead(BaseModel):
    source_type: str
    source_type_label: str
    link_count: int
    citation_rate: str | None = None
    display_value: str


class SourceAnalysisPlatformColumnRead(BaseModel):
    platform_code: str
    has_citation_data: bool


class SourceAnalysisPlatformValueRead(BaseModel):
    platform_code: str
    link_count: int
    citation_rate: str | None = None
    has_citation_data: bool
    display_value: str


class SourceAnalysisSiteRead(BaseModel):
    domain: str
    source_name: str | None = None
    source_type: str
    source_type_label: str
    link_count: int
    citation_rate: str | None = None
    display_value: str
    platform_values: list[SourceAnalysisPlatformValueRead] = Field(default_factory=list)


class SourceAnalysisOut(BaseModel):
    run_id: int | None = None
    metric: str
    has_citation_data: bool
    kpi: SourceAnalysisKpiRead
    type_distribution: list[SourceAnalysisTypeDistributionRead] = Field(default_factory=list)
    platform_columns: list[SourceAnalysisPlatformColumnRead] = Field(default_factory=list)
    sites: PaginatedResponse[SourceAnalysisSiteRead]


class CompetitorAnalysisTargetBrandRead(BaseModel):
    brand_id: int
    brand_name: str


class CompetitorAnalysisKpiRead(BaseModel):
    mention_rate: str | None = None
    mention_count: int
    average_rank: str | None = None
    top1_rate: str | None = None
    share_of_voice: str | None = None


class CompetitorAnalysisBoardRowRead(BaseModel):
    brand_id: int
    brand_name: str
    mention_rate: str | None = None
    mention_count: int
    average_rank: str | None = None
    share_of_voice: str | None = None
    is_target: bool


class CompetitorAnalysisBoardsRead(BaseModel):
    mention_rate: list[CompetitorAnalysisBoardRowRead] = Field(default_factory=list)
    average_rank: list[CompetitorAnalysisBoardRowRead] = Field(default_factory=list)
    mention_count: list[CompetitorAnalysisBoardRowRead] = Field(default_factory=list)


class CompetitorAnalysisTrendsRead(BaseModel):
    days: list[str] = Field(default_factory=list)
    mention_rate: list[Any] = Field(default_factory=list)
    average_rank: list[Any] = Field(default_factory=list)
    mention_count: list[Any] = Field(default_factory=list)


class CompetitorAnalysisOut(BaseModel):
    run_id: int | None = None
    brand_scope: str
    target_brand: CompetitorAnalysisTargetBrandRead
    has_analysis_data: bool
    kpis: CompetitorAnalysisKpiRead
    boards: CompetitorAnalysisBoardsRead
    trends: CompetitorAnalysisTrendsRead


class DashboardOverviewKpiRead(BaseModel):
    brand_mention_rate: str | None = None
    brand_top1_mention_rate: str | None = None
    brand_top3_mention_rate: str | None = None
    brand_top10_mention_rate: str | None = None
    valid_answer_count: int | None = None
    brand_mention_count: int | None = None
    average_rank: str | None = None
    share_of_voice: str | None = None
    brand_mention_total_count: int | None = None
    positive_rate: str | None = None
    neutral_rate: str | None = None
    negative_rate: str | None = None


class DashboardOverviewPlatformRead(BaseModel):
    platform_code: str
    platform_name: str
    analysis: dict[str, Any] | None = None


class DashboardOverviewCompetitorPreviewRead(BaseModel):
    boards: CompetitorAnalysisBoardsRead


class DashboardOverviewSourcePreviewRead(BaseModel):
    items: list[SourceAnalysisSiteRead] = Field(default_factory=list)
    total: int = 0


class DashboardOverviewRecentQuestionsRead(BaseModel):
    items: list[ConversationQuestionRead] = Field(default_factory=list)
    total: int = 0


class DashboardOverviewOut(BaseModel):
    project_id: int
    run_id: int | None = None
    kpis: DashboardOverviewKpiRead
    platforms: list[DashboardOverviewPlatformRead] = Field(default_factory=list)
    competitor_preview: DashboardOverviewCompetitorPreviewRead
    source_preview: DashboardOverviewSourcePreviewRead
    recent_questions: DashboardOverviewRecentQuestionsRead


class ProjectDraftCreate(BaseModel):
    draft_key: str | None = Field(default=None, max_length=128)
    current_step: int = Field(default=1, ge=1, le=3)
    project: dict[str, Any] = Field(default_factory=dict)
    monitor_setup: dict[str, Any] = Field(default_factory=dict)

    @field_validator("draft_key")
    @classmethod
    def strip_draft_key(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ProjectDraftUpdate(BaseModel):
    draft_key: str | None = Field(default=None, max_length=128)
    current_step: int | None = Field(default=None, ge=1, le=3)
    project: dict[str, Any] | None = None
    monitor_setup: dict[str, Any] | None = None

    @field_validator("draft_key")
    @classmethod
    def strip_draft_key(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ProjectDraftOut(BaseModel):
    id: int
    draft_key: str | None
    current_step: int
    project: dict[str, Any] = Field(default_factory=dict)
    monitor_setup: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

