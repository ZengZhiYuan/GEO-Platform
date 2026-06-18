"""分析触发与查询 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.agents.llm import create_agent_llm_client
from app.geo_monitoring.services.analysis import (
    AgentExecution,
    PlatformAnalysis,
    build_agent_llm_config,
    run_analysis,
)
from app.geo_monitoring.services.runs import RUN_TERMINAL_STATUSES, get_run

router = APIRouter()


# 将平台分析 ORM 行序列化为 API 响应字段
def _platform_analysis_payload(row: PlatformAnalysis) -> dict:
    return {
        "platform_code": row.platform_code,
        "status": row.status,
        "valid_answer_count": row.valid_answer_count,
        "data_completeness_rate": str(row.data_completeness_rate),
        "brand_mention_count": row.brand_mention_count,
        "brand_mention_rate": str(row.brand_mention_rate),
        "brand_first_count": row.brand_first_count,
        "brand_first_rate": str(row.brand_first_rate),
        "brand_first_among_mentions_rate": str(row.brand_first_among_mentions_rate),
        "top_competitors": row.top_competitors,
        "top_sources": row.top_sources,
        "prompt_competitiveness_summary": row.prompt_competitiveness_summary,
        "improvement_json": row.improvement_json,
        "summary_json": row.summary_json,
    }


# 将 Agent 执行审计 ORM 行序列化为 API 响应字段
def _agent_execution_payload(row: AgentExecution) -> dict:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "platform_code": row.platform_code,
        "agent_code": row.agent_code,
        "status": row.status,
        "schema_version": row.schema_version,
        "input_snapshot": row.input_snapshot,
        "output_json": row.output_json,
        "model_name": row.model_name,
        "prompt_version": row.prompt_version,
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


@router.post("/runs/{run_id}/analyze", summary="手工触发或重跑分析")
# 手工触发或重跑指定运行的 Agent 分析
def trigger_run_analysis(
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    run = get_run(db, run_id)
    # 采集未完成时拒绝分析
    if run.status not in RUN_TERMINAL_STATUSES:
        from app.core.exceptions import BusinessException

        raise BusinessException(
            message="采集尚未完成，暂不可分析",
            code=40910,
            status_code=409,
        )

    run.analysis_status = "running"
    db.commit()

    # 同步执行分析流水线
    llm_client = create_agent_llm_client(build_agent_llm_config())
    result = run_analysis(db, run_id, llm_client=llm_client)
    db.refresh(run)
    payload = {
        "run_id": run_id,
        "analysis_status": result["analysis_status"],
        "skip_reason": result.get("skip_reason"),
        "run_analysis_status": run.analysis_status,
    }
    return success(payload)


@router.get("/runs/{run_id}/analysis", summary="获取运行平台指标与洞察")
# 获取运行各平台的确定性指标与 Agent 洞察
def get_run_analysis(
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    run = get_run(db, run_id)
    rows = list(
        db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == run_id,
                PlatformAnalysis.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )
    return success(
        {
            "run_id": run_id,
            "analysis_status": run.analysis_status,
            "platforms": [_platform_analysis_payload(row) for row in rows],
        }
    )


@router.get("/runs/{run_id}/agent-executions", summary="分页查询 Agent 执行审计")
# 分页查询运行的 Agent 执行审计记录
def list_agent_executions(
    run_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    platform_code: str | None = Query(None, max_length=32),
    agent_code: str | None = Query(None, max_length=64),
    db: Session = Depends(get_db),
) -> dict:
    get_run(db, run_id)
    conditions = [
        AgentExecution.run_id == run_id,
        AgentExecution.is_deleted.is_(False),
    ]
    if platform_code:
        conditions.append(AgentExecution.platform_code == platform_code)
    if agent_code:
        conditions.append(AgentExecution.agent_code == agent_code)

    total = db.scalar(select(func.count()).select_from(AgentExecution).where(*conditions)) or 0
    items = list(
        db.execute(
            select(AgentExecution)
            .where(*conditions)
            .order_by(AgentExecution.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    data = [_agent_execution_payload(item) for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)
