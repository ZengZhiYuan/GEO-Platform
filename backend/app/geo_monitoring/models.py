"""AI 应用监测领域模型。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

JSON_VALUE = JSONB().with_variant(JSON(), "sqlite")


class MonitorProject(BaseModel):
    __tablename__ = "geo_monitor_project"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled', 'archived')",
            name="ck_geo_monitor_project_status",
        ),
        Index("ix_geo_monitor_project_status", "status"),
    )

    project_name: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str] = mapped_column(
        String(100), default="文旅演艺", server_default="文旅演艺", nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Shanghai", server_default="Asia/Shanghai", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )
    official_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Brand(BaseModel):
    __tablename__ = "geo_brand"
    __table_args__ = (
        UniqueConstraint("project_id", "brand_name", name="uq_geo_brand_project_name"),
        CheckConstraint(
            "brand_type IN ('target', 'competitor', 'candidate')",
            name="ck_geo_brand_type",
        ),
        CheckConstraint(
            "status IN ('active', 'disabled')", name="ck_geo_brand_status"
        ),
        Index("ix_geo_brand_project_type", "project_id", "brand_type"),
        Index(
            "uq_geo_brand_one_target_per_project",
            "project_id",
            unique=True,
            postgresql_where=text("brand_type = 'target' AND is_deleted = false"),
            sqlite_where=text("brand_type = 'target' AND is_deleted = 0"),
        ),
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_monitor_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_type: Mapped[str] = mapped_column(
        String(20), default="competitor", server_default="competitor", nullable=False
    )
    official_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )


class BrandAlias(BaseModel):
    __tablename__ = "geo_brand_alias"
    __table_args__ = (
        UniqueConstraint("brand_id", "alias_name", name="uq_geo_brand_alias"),
        CheckConstraint(
            "match_mode IN ('exact', 'contains', 'context')",
            name="ck_geo_brand_alias_match_mode",
        ),
        Index("ix_geo_brand_alias_name", "alias_name"),
    )

    brand_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_brand.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias_name: Mapped[str] = mapped_column(String(255), nullable=False)
    match_mode: Mapped[str] = mapped_column(
        String(20), default="contains", server_default="contains", nullable=False
    )
    is_ambiguous: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    context_keywords: Mapped[list[str]] = mapped_column(
        JSON_VALUE, default=list, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )


class PromptSet(BaseModel):
    __tablename__ = "geo_prompt_set"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "version_no", name="uq_geo_prompt_set_version"
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_geo_prompt_set_status",
        ),
        Index("ix_geo_prompt_set_project_status", "project_id", "status"),
        Index(
            "uq_geo_prompt_set_one_active_per_project",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'active' AND is_deleted = false"),
            sqlite_where=text("status = 'active' AND is_deleted = 0"),
        ),
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_monitor_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    set_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version_no: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", nullable=False
    )
    prompt_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Prompt(BaseModel):
    __tablename__ = "geo_prompt"
    __table_args__ = (
        UniqueConstraint("prompt_set_id", "prompt_code", name="uq_geo_prompt_code"),
        Index(
            "ix_geo_prompt_prompt_set_enabled",
            "prompt_set_id",
            "enabled",
            "sort_order",
        ),
    )

    prompt_set_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_prompt_set.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_code: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_type: Mapped[str] = mapped_column(
        String(50), default="generic", server_default="generic", nullable=False
    )
    scene_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contains_brand: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AIPlatform(BaseModel):
    __tablename__ = "geo_ai_platform"
    __table_args__ = (
        CheckConstraint(
            "max_concurrency > 0", name="ck_geo_ai_platform_max_concurrency"
        ),
        CheckConstraint("timeout_seconds > 0", name="ck_geo_ai_platform_timeout"),
    )

    platform_code: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    platform_name: Mapped[str] = mapped_column(String(100), nullable=False)
    adapter_type: Mapped[str] = mapped_column(
        String(50),
        default="openai_compatible",
        server_default="openai_compatible",
        nullable=False,
    )
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    search_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    citation_supported: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    max_concurrency: Mapped[int] = mapped_column(
        Integer, default=2, server_default="2", nullable=False
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, default=120, server_default="120", nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    extra_config: Mapped[dict] = mapped_column(JSON_VALUE, default=dict, nullable=False)


class MonitorRun(BaseModel):
    __tablename__ = "geo_monitor_run"
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('manual', 'schedule', 'retry')",
            name="ck_geo_monitor_run_trigger_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'collecting', 'analyzing', 'reporting', "
            "'completed', 'partial_success', 'failed', 'cancelled')",
            name="ck_geo_monitor_run_status",
        ),
        CheckConstraint(
            "collection_status IN ('pending', 'running', 'completed', "
            "'partial_success', 'failed', 'cancelled')",
            name="ck_geo_monitor_run_collection_status",
        ),
        CheckConstraint(
            "analysis_status IN ('pending', 'running', 'completed', "
            "'partial_success', 'failed', 'skipped')",
            name="ck_geo_monitor_run_analysis_status",
        ),
        CheckConstraint(
            "report_status IN ('pending', 'running', 'completed', 'failed', 'skipped')",
            name="ck_geo_monitor_run_report_status",
        ),
        Index("ix_geo_monitor_run_project_created", "project_id", "created_at"),
        Index("ix_geo_monitor_run_status", "status", "created_at"),
        Index("ix_geo_monitor_run_status_completed", "status", "completed_at"),
    )

    run_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("geo_monitor_project.id"), nullable=False
    )
    prompt_set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("geo_prompt_set.id"), nullable=False
    )
    prompt_set_version: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual", nullable=False
    )
    triggered_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", server_default="pending", nullable=False
    )
    collection_status: Mapped[str] = mapped_column(
        String(30), default="pending", server_default="pending", nullable=False
    )
    analysis_status: Mapped[str] = mapped_column(
        String(30), default="skipped", server_default="skipped", nullable=False
    )
    report_status: Mapped[str] = mapped_column(
        String(30), default="skipped", server_default="skipped", nullable=False
    )
    platform_codes: Mapped[list[str]] = mapped_column(
        JSON_VALUE, default=list, nullable=False
    )
    expected_query_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    success_query_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    failed_query_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    valid_answer_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    data_completeness_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("0"), server_default="0", nullable=False
    )
    result_json: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_tasks: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    succeeded_tasks: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    failed_tasks: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    cancelled_tasks: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class QueryTask(BaseModel):
    __tablename__ = "geo_query_task"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "prompt_id", "platform_code", name="uq_geo_query_task"
        ),
        CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'success', 'failed', 'cancelled')",
            name="ck_geo_query_task_status",
        ),
        CheckConstraint("retry_count >= 0", name="ck_geo_query_task_retry_count"),
        Index("ix_geo_query_task_run_status", "run_id", "status"),
        Index(
            "ix_geo_query_task_platform_status", "platform_code", "status"
        ),
        Index("ix_geo_query_task_status_queued", "status", "queued_at"),
    )

    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("geo_prompt.id"), nullable=False
    )
    platform_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("geo_ai_platform.platform_code"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    key_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, default=3, server_default="3", nullable=False
    )
    request_json: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    response_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    answer: Mapped["Answer | None"] = relationship(
        "Answer",
        back_populates="task",
        uselist=False,
    )


class Answer(BaseModel):
    __tablename__ = "geo_answer"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_geo_answer_task"),
        Index("ix_geo_answer_platform_collected", "platform_code", "collected_at"),
    )

    task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_query_task.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("geo_ai_platform.platform_code"),
        nullable=False,
    )
    prompt_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_prompt.id"),
        nullable=False,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    raw_response_json: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    task: Mapped[QueryTask] = relationship("QueryTask", back_populates="answer")
    citations: Mapped[list["AnswerCitation"]] = relationship(
        "AnswerCitation",
        back_populates="answer",
        order_by="AnswerCitation.citation_no",
    )
    brand_results: Mapped[list["AnswerBrandResult"]] = relationship(
        "AnswerBrandResult",
        back_populates="answer",
    )


class AnswerCitation(BaseModel):
    __tablename__ = "geo_answer_citation"
    __table_args__ = (
        UniqueConstraint(
            "answer_id", "citation_no", name="uq_geo_answer_citation_answer_no"
        ),
        Index("ix_geo_answer_citation_domain", "domain"),
    )

    answer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_answer.id", ondelete="CASCADE"),
        nullable=False,
    )
    citation_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quoted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[Answer] = relationship("Answer", back_populates="citations")


class AnswerBrandResult(BaseModel):
    __tablename__ = "geo_answer_brand_result"
    __table_args__ = (
        UniqueConstraint(
            "answer_id",
            "brand_id",
            name="uq_geo_answer_brand_result_answer_brand",
        ),
        Index(
            "ix_geo_answer_brand_result_brand_mentioned",
            "brand_id",
            "is_mentioned",
        ),
    )

    answer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_answer.id", ondelete="CASCADE"),
        nullable=False,
    )
    brand_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_brand.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_mentioned: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    mention_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    first_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(30), nullable=True)
    context_json: Mapped[dict] = mapped_column(
        JSON_VALUE, default=dict, server_default=text("'{}'"), nullable=False
    )
    answer: Mapped[Answer] = relationship("Answer", back_populates="brand_results")
