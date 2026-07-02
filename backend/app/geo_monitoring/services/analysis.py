"""分析域 ORM 映射、持久化与 LangGraph 编排入口。"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column, selectinload

from app.core.config import Settings, settings as default_settings
from app.core.exceptions import BusinessException
from app.geo_monitoring.agents.llm import AgentLLMClient, AgentLLMConfig, create_agent_llm_client
from app.geo_monitoring.models import (
    Answer,
    Brand,
    BrandAlias,
    MonitorProject,
    MonitorRun,
    QueryTask,
)
from app.geo_monitoring.services.competitor_scope import resolve_competitor_brand_ids
from app.geo_monitoring.services.runs import RUN_TERMINAL_STATUSES

if False:  # type checking only
    from app.geo_monitoring.agents.graph import AnalysisState
from app.models.base import BaseModel

JSON_VALUE = JSONB().with_variant(
    __import__("sqlalchemy", fromlist=["JSON"]).JSON(), "sqlite"
)


class AgentExecution(BaseModel):
    __tablename__ = "geo_agent_execution"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'skipped')",
            name="ck_geo_agent_execution_status",
        ),
        Index(
            "uq_geo_agent_execution_run_agent",
            "run_id",
            "agent_code",
            "schema_version",
            text("coalesce(platform_code, '')"),
            unique=True,
        ),
        Index(
            "ix_geo_agent_execution_run_platform_agent",
            "run_id",
            "platform_code",
            "agent_code",
        ),
    )

    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    agent_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    schema_version: Mapped[str] = mapped_column(
        String(20), default="1.0", server_default="1.0", nullable=False
    )
    input_snapshot: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(), nullable=True
    )


class PlatformAnalysis(BaseModel):
    __tablename__ = "geo_platform_analysis"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'partial_success', 'failed')",
            name="ck_geo_platform_analysis_status",
        ),
        UniqueConstraint("run_id", "platform_code", name="uq_geo_platform_analysis"),
    )

    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("geo_ai_platform.platform_code"),
        nullable=False,
    )
    valid_answer_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    data_completeness_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("0"), server_default="0", nullable=False
    )
    brand_mention_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    brand_mention_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("0"), server_default="0", nullable=False
    )
    brand_first_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    brand_first_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("0"), server_default="0", nullable=False
    )
    brand_first_among_mentions_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("0"), server_default="0", nullable=False
    )
    top_competitors: Mapped[list] = mapped_column(
        JSON_VALUE, default=list, server_default=text("'[]'"), nullable=False
    )
    top_sources: Mapped[list] = mapped_column(
        JSON_VALUE, default=list, server_default=text("'[]'"), nullable=False
    )
    prompt_competitiveness_summary: Mapped[list] = mapped_column(
        JSON_VALUE, default=list, server_default=text("'[]'"), nullable=False
    )
    improvement_json: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )


class MetricSnapshot(BaseModel):
    __tablename__ = "geo_metric_snapshot"
    __table_args__ = (
        Index(
            "uq_geo_metric_snapshot_dimension",
            "project_id",
            "run_id",
            "metric_code",
            text("coalesce(platform_code, '')"),
            text("coalesce(prompt_id, -1)"),
            text("coalesce(brand_id, -1)"),
            unique=True,
        ),
        Index(
            "ix_geo_metric_snapshot_trend",
            "project_id",
            "metric_code",
            "platform_code",
            "snapshot_at",
        ),
        Index(
            "ix_geo_metric_snapshot_brand_trend",
            "project_id",
            "brand_id",
            "metric_code",
            "platform_code",
            "snapshot_at",
        ),
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_monitor_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    brand_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("geo_brand.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("geo_prompt.id", ondelete="SET NULL"), nullable=True
    )
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False)
    numerator: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    denominator: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    metric_json: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(),
        server_default=func.now(),
        nullable=False,
    )
    prompt_set_version: Mapped[str] = mapped_column(String(50), nullable=False)
    is_comparable: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    completeness_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("0"), server_default="0", nullable=False
    )


class PromptCompetitiveness(BaseModel):
    __tablename__ = "geo_prompt_competitiveness"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "prompt_id",
            "platform_code",
            name="uq_geo_prompt_competitiveness",
        ),
        Index(
            "ix_geo_prompt_competitiveness_run_prompt",
            "run_id",
            "prompt_id",
        ),
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
    target_mentioned: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    target_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_first: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    competitors_json: Mapped[list] = mapped_column(
        JSON_VALUE, default=list, server_default=text("'[]'"), nullable=False
    )
    position_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
    competitiveness_score: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    evidence_json: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)


class SourceStat(BaseModel):
    __tablename__ = "geo_source_stat"
    __table_args__ = (
        Index(
            "uq_geo_source_stat_run_platform_domain",
            "run_id",
            "domain",
            text("coalesce(platform_code, '')"),
            unique=True,
        ),
        Index(
            "ix_geo_source_stat_run_platform_rank",
            "run_id",
            "platform_code",
            "rank_no",
        ),
    )

    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    citation_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    brand_related_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    share_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("0"), server_default="0", nullable=False
    )
    rank_no: Mapped[int | None] = mapped_column(Integer, nullable=True)


# 递归将 Decimal、datetime 等转为 JSON 可序列化值
def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _json_default(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _json_default(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_default(item) for item in value]
    return value


# 将分析状态字典序列化为 JSON 兼容结构
def serialize_state(state: dict[str, Any]) -> dict[str, Any]:
    return _json_default(dict(state))


# 从应用配置构建 Agent LLM 客户端参数
def build_agent_llm_config(settings: Settings | None = None) -> AgentLLMConfig:
    if settings is None:
        from app.core.config import get_settings

        cfg = get_settings()
    else:
        cfg = settings
    missing: list[str] = []
    if not cfg.AGENT_LLM_BASE_URL.strip():
        missing.append("AGENT_LLM_BASE_URL")
    if not cfg.AGENT_LLM_API_KEY.strip():
        missing.append("AGENT_LLM_API_KEY")
    if not cfg.AGENT_LLM_MODEL.strip():
        missing.append("AGENT_LLM_MODEL")
    if missing:
        raise BusinessException(
            message="Agent LLM 配置不完整，请设置: " + ", ".join(missing),
            code=50301,
            status_code=503,
        )
    return AgentLLMConfig(
        base_url=cfg.AGENT_LLM_BASE_URL.strip(),
        api_key=cfg.AGENT_LLM_API_KEY.strip(),
        model=cfg.AGENT_LLM_MODEL.strip(),
        provider=cfg.AGENT_LLM_PROVIDER,
        timeout_seconds=float(cfg.AGENT_LLM_TIMEOUT_SECONDS),
        max_attempts=cfg.AGENT_LLM_MAX_ATTEMPTS,
    )


# 根据运行 ID 加载分析所需的运行、品牌与成功答案上下文
def load_run_context(db: Session, run_id: int) -> dict[str, Any]:
    # 查询运行记录
    run = db.execute(
        select(MonitorRun).where(
            MonitorRun.id == run_id,
            MonitorRun.is_deleted.is_(False),
        )
    ).scalar_one()

    # 加载所属项目
    project = db.execute(
        select(MonitorProject).where(
            MonitorProject.id == run.project_id,
            MonitorProject.is_deleted.is_(False),
        )
    ).scalar_one()

    # 加载活跃品牌并定位目标品牌
    brands = list(
        db.execute(
            select(Brand).where(
                Brand.project_id == run.project_id,
                Brand.is_deleted.is_(False),
                Brand.status == "active",
            )
        )
        .scalars()
        .all()
    )
    target = next((brand for brand in brands if brand.brand_type == "target"), None)
    if target is None:
        raise ValueError(f"run {run_id} has no active target brand")

    # 加载目标品牌的启用别名
    aliases = list(
        db.execute(
            select(BrandAlias).where(
                BrandAlias.brand_id == target.id,
                BrandAlias.is_deleted.is_(False),
                BrandAlias.enabled.is_(True),
            )
        )
        .scalars()
        .all()
    )

    competitor_ids = [
        brand.id for brand in brands if brand.brand_type == "competitor"
    ]
    brand_names = {brand.id: brand.brand_name for brand in brands}

    # 加载本次运行下成功任务的答案及关联数据
    answers = list(
        db.execute(
            select(Answer)
            .join(QueryTask, QueryTask.id == Answer.task_id)
            .options(
                selectinload(Answer.citations),
                selectinload(Answer.brand_results),
            )
            .where(
                QueryTask.run_id == run_id,
                QueryTask.status == "success",
                QueryTask.is_deleted.is_(False),
                Answer.is_deleted.is_(False),
            )
            .order_by(Answer.id)
        )
        .scalars()
        .all()
    )

    resolved_competitor_ids = resolve_competitor_brand_ids(
        brands=brands,
        target_brand_id=target.id,
        answers=answers,
    )

    return {
        "run": run,
        "project": project,
        "target_brand_id": target.id,
        "target_brand_name": target.brand_name,
        "target_aliases": tuple(alias.alias_name for alias in aliases),
        "competitor_brand_ids": resolved_competitor_ids,
        "configured_competitor_ids": tuple(competitor_ids),
        "brand_names": brand_names,
        "official_domain": project.official_domain or "",
        "platform_codes": tuple(run.platform_codes or ()),
        "prompt_set_version": run.prompt_set_version,
        "answers": answers,
    }


def begin_run_analysis(db: Session, run_id: int) -> MonitorRun:
    """加锁认领运行分析，防止并发重复触发。"""
    run = db.execute(
        select(MonitorRun)
        .where(
            MonitorRun.id == run_id,
            MonitorRun.is_deleted.is_(False),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if run is None:
        raise BusinessException(message="监测运行不存在", code=40400)

    if run.status not in RUN_TERMINAL_STATUSES:
        raise BusinessException(
            message="采集尚未完成，暂不可分析",
            code=40910,
            status_code=409,
        )

    if run.analysis_status == "running":
        raise BusinessException(
            message="分析正在进行中，请勿重复触发",
            code=40911,
            status_code=409,
        )

    run.analysis_status = "running"
    db.commit()
    return run


def run_analysis(
    db: Session,
    run_id: int,
    *,
    llm_client: AgentLLMClient | None = None,
    settings: Settings | None = None,
    include_state: bool = False,
) -> dict[str, Any]:
    """执行 LangGraph 分析流程并返回运行分析状态。"""
    from app.geo_monitoring.agents.graph import build_analysis_graph

    client = llm_client or create_agent_llm_client(build_agent_llm_config(settings))
    graph = build_analysis_graph(db=db, llm_client=client)
    initial_state = {"run_id": run_id}
    # 调用 LangGraph 图完成指标计算与 Agent 编排
    final_state = graph.invoke(initial_state)

    payload: dict[str, Any] = {
        "run_id": run_id,
        "analysis_status": final_state.get("analysis_status", "failed"),
        "skip_reason": final_state.get("skip_reason"),
    }
    if include_state:
        payload["state"] = final_state
    return payload
