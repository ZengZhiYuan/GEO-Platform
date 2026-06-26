"""LangGraph 分析节点实现。"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol
from sqlalchemy import select
from sqlalchemy.orm import Session

AnalysisState = dict[str, Any]

from app.geo_monitoring.agents.llm import (
    AgentLLMClient,
    AgentLLMFailure,
    AgentLLMRequest,
    AgentLLMResult,
)
from app.geo_monitoring.agents.schemas import (
    SCHEMA_VERSION,
    InsightSummaryOutput,
    RecommendationIntent,
    RecommendationIntentOutput,
    RiskAssessmentOutput,
    SentimentOutput,
)
from app.geo_monitoring.analysis.brands import BrandProfile
from app.geo_monitoring.analysis.dto import (
    AnswerInput,
    BrandMentionInput,
    CitationInput,
    PlatformMetricsOutput,
)
from app.geo_monitoring.analysis.metrics import (
    compute_platform_metrics,
    compute_rate,
    filter_valid_answers,
)
from app.geo_monitoring.models import MonitorRun
from app.geo_monitoring.services.analysis import (
    AgentExecution,
    MetricSnapshot,
    PlatformAnalysis,
    PromptCompetitiveness,
    SourceStat,
    load_run_context,
    serialize_state,
)


class LLMClientProtocol(Protocol):
    # LLM 结构化输出生成接口
    async def generate_structured(
        self, request: AgentLLMRequest
    ) -> AgentLLMResult | AgentLLMFailure:
        ...


# 返回当前 UTC 时间
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# 将 None 的 Decimal 转为零值
def _decimal(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal("0")


# 将 ORM 回答行转换为分析用 AnswerInput DTO
def _answer_input_from_row(answer: Any, task_status: str = "success") -> AnswerInput:
    return AnswerInput(
        answer_id=answer.id,
        prompt_id=answer.prompt_id,
        platform_code=answer.platform_code,
        task_status=task_status,
        normalized_text=answer.normalized_text or "",
        brand_mentions=tuple(
            BrandMentionInput(
                brand_id=result.brand_id,
                is_mentioned=result.is_mentioned,
                mention_count=result.mention_count,
                first_position=result.first_position,
                sentiment=result.sentiment,
            )
            for result in answer.brand_results
        ),
        citations=tuple(
            CitationInput(
                citation_no=citation.citation_no,
                url=citation.url,
                domain=citation.domain,
                title=citation.title,
                source_type=citation.source_type,
            )
            for citation in answer.citations
        ),
        agent_recommendation=None,
    )


# 将 PlatformMetricsOutput 序列化为可写入状态的字典
def _metrics_to_dict(metrics: PlatformMetricsOutput) -> dict[str, Any]:
    return serialize_state({"metrics": metrics})["metrics"]


# 生成供 LLM 阅读的平台指标摘要文本
def _metrics_summary(metrics: PlatformMetricsOutput) -> str:
    visibility = metrics.brand_visibility.rate
    citation = metrics.citation_rate.rate
    recommendation = metrics.recommendation.combined_rate
    return (
        f"valid_answers={metrics.valid_answer_count}; "
        f"brand_visibility={visibility}; "
        f"citation_rate={citation}; "
        f"recommendation_rate={recommendation}; "
        f"competitor_gap={metrics.competitor_advantage_gap}"
    )


# 将 Agent 推荐意图输出映射为布尔值或 None
def _recommendation_bool(output: RecommendationIntentOutput) -> bool | None:
    if output.intent in {RecommendationIntent.STRONG_RECOMMEND, RecommendationIntent.RECOMMEND}:
        return True
    if output.intent == RecommendationIntent.NOT_RECOMMEND:
        return False
    return None


# 从数据库加载监测运行上下文并初始化分析状态
def load_run_data(state: AnalysisState, *, db: Session) -> AnalysisState:
    run_id = state["run_id"]
    context = load_run_context(db, run_id)
    answers = [
        _answer_input_from_row(answer)
        for answer in context["answers"]
    ]
    valid_answers = filter_valid_answers(answers)

    next_state: AnalysisState = {
        "run_id": run_id,
        "project_id": context["run"].project_id,
        "prompt_set_version": context["prompt_set_version"],
        "platform_codes": list(context["platform_codes"]),
        "target_brand_id": context["target_brand_id"],
        "target_brand_name": context["target_brand_name"],
        "target_aliases": list(context["target_aliases"]),
        "competitor_brand_ids": list(context["competitor_brand_ids"]),
        "brand_names": context["brand_names"],
        "official_domain": context["official_domain"],
        "answers": [serialize_state({"answer": answer})["answer"] for answer in answers],
        "valid_answer_count": len(valid_answers),
        "classifications": {},
        "platform_insights": {},
        "platform_failures": {},
        "execution_records": [],
    }

    if not valid_answers:
        next_state["analysis_status"] = "skipped"
        next_state["skip_reason"] = "no_valid_answers"
    return next_state


# 按平台计算确定性指标并写入状态
def calculate_metrics(state: AnalysisState) -> AnalysisState:
    if state.get("analysis_status") == "skipped":
        return {}

    answers = [_deserialize_answer(item) for item in state["answers"]]
    valid_answers = filter_valid_answers(answers)
    brands = tuple(
        BrandProfile(
            brand_id=brand_id,
            brand_name=state["brand_names"][brand_id],
            category="competitor"
            if brand_id in state["competitor_brand_ids"]
            else "target",
        )
        for brand_id in sorted(state["brand_names"])
    )

    platform_metrics: dict[str, dict[str, Any]] = {}
    for platform_code in state["platform_codes"]:
        metrics = compute_platform_metrics(
            answers,
            platform_code=platform_code,
            target_brand_id=state["target_brand_id"],
            target_brand_name=state["target_brand_name"],
            target_aliases=tuple(state["target_aliases"]),
            competitor_brand_ids=tuple(state["competitor_brand_ids"]),
            brand_names=state["brand_names"],
            official_domain=state["official_domain"],
            brands=brands,
        )
        platform_metrics[platform_code] = _metrics_to_dict(metrics)

    return {"platform_metrics": platform_metrics}


# 调用 LLM 对每条有效回答进行情感与推荐意图分类
def classify_answers(state: AnalysisState, *, llm_client: LLMClientProtocol) -> AnalysisState:
    if state.get("analysis_status") == "skipped":
        return {}

    # 异步遍历有效回答，逐条调用分类 Agent
    async def _run() -> tuple[dict[str, Any], dict[str, list[str]], list[dict[str, Any]]]:
        answers = [_deserialize_answer(item) for item in state["answers"]]
        valid_answers = filter_valid_answers(answers)
        answer_updates: dict[int, AnswerInput] = {
            answer.answer_id: answer for answer in answers
        }
        classifications: dict[str, dict[str, Any]] = {}
        platform_failures: dict[str, list[str]] = {}
        execution_records: list[dict[str, Any]] = []

        for answer in valid_answers:
            platform_code = answer.platform_code
            answer_key = str(answer.answer_id)
            platform_failures.setdefault(platform_code, [])
            answer_labels: dict[str, Any] = {}
            current = answer_updates[answer.answer_id]

            for template_key, agent_code, schema, variables in (
                (
                    "classify_sentiment",
                    "classify_sentiment",
                    SentimentOutput,
                    {"answer_text": answer.normalized_text, "platform_code": platform_code},
                ),
                (
                    "classify_recommendation",
                    "classify_recommendation",
                    RecommendationIntentOutput,
                    {"answer_text": answer.normalized_text, "platform_code": platform_code},
                ),
            ):
                request = AgentLLMRequest(
                    template_key=template_key,
                    variables=variables,
                    output_schema=schema,
                    agent_code=agent_code,
                    request_id=f"run-{state['run_id']}-{platform_code}-{answer.answer_id}-{agent_code}",
                )
                result = await llm_client.generate_structured(request)
                record = _execution_record_from_result(
                    run_id=state["run_id"],
                    platform_code=platform_code,
                    agent_code=agent_code,
                    request=request,
                    result=result,
                )
                execution_records.append(record)
                if isinstance(result, AgentLLMFailure):
                    platform_failures[platform_code].append(agent_code)
                    continue
                if agent_code == "classify_sentiment":
                    answer_labels["sentiment"] = result.parsed.model_dump()
                else:
                    answer_labels["recommendation"] = result.parsed.model_dump()
                    current = replace(
                        current,
                        agent_recommendation=_recommendation_bool(result.parsed),
                    )
                    answer_updates[answer.answer_id] = current

            classifications[answer_key] = answer_labels

        updated_answers = [
            serialize_state({"answer": answer_updates[_deserialize_answer(item).answer_id]})[
                "answer"
            ]
            for item in state["answers"]
        ]

        return classifications, platform_failures, execution_records, updated_answers

    classifications, platform_failures, execution_records, updated_answers = asyncio.run(
        _run()
    )

    # 分类完成后用更新后的回答重新计算指标
    metrics_update = calculate_metrics({**state, "answers": updated_answers})
    return {
        "answers": updated_answers,
        "classifications": classifications,
        "platform_failures": platform_failures,
        "execution_records": state.get("execution_records", []) + execution_records,
        **metrics_update,
    }


# 基于平台指标调用 LLM 生成风险评估与改进洞察
def generate_insights(state: AnalysisState, *, llm_client: LLMClientProtocol) -> AnalysisState:
    if state.get("analysis_status") == "skipped":
        return {}

    # 异步逐平台调用风险与洞察 Agent
    async def _run() -> tuple[dict[str, Any], dict[str, list[str]], list[dict[str, Any]]]:
        platform_insights: dict[str, Any] = {}
        platform_failures = dict(state.get("platform_failures") or {})
        execution_records: list[dict[str, Any]] = []

        for platform_code in state["platform_codes"]:
            metrics_dict = (state.get("platform_metrics") or {}).get(platform_code)
            if not metrics_dict:
                continue
            if platform_failures.get(platform_code):
                continue

            metrics = _deserialize_platform_metrics(metrics_dict)
            summary = _metrics_summary(metrics)
            platform_failures.setdefault(platform_code, [])

            for template_key, agent_code, schema in (
                ("assess_risk", "assess_risk", RiskAssessmentOutput),
                ("generate_insights", "generate_insights", InsightSummaryOutput),
            ):
                request = AgentLLMRequest(
                    template_key=template_key,
                    variables={
                        "metrics_summary": summary,
                        "platform_code": platform_code,
                    },
                    output_schema=schema,
                    agent_code=agent_code,
                    request_id=f"run-{state['run_id']}-{platform_code}-{agent_code}",
                )
                result = await llm_client.generate_structured(request)
                execution_records.append(
                    _execution_record_from_result(
                        run_id=state["run_id"],
                        platform_code=platform_code,
                        agent_code=agent_code,
                        request=request,
                        result=result,
                    )
                )
                if isinstance(result, AgentLLMFailure):
                    platform_failures[platform_code].append(agent_code)
                    continue
                if agent_code == "assess_risk":
                    platform_insights.setdefault(platform_code, {})["risk"] = (
                        result.parsed.model_dump()
                    )
                else:
                    platform_insights.setdefault(platform_code, {})["insights"] = (
                        result.parsed.model_dump()
                    )

        return platform_insights, platform_failures, execution_records

    platform_insights, platform_failures, execution_records = asyncio.run(_run())
    return {
        "platform_insights": platform_insights,
        "platform_failures": platform_failures,
        "execution_records": state.get("execution_records", []) + execution_records,
    }


# 将分析结果持久化到数据库并更新运行状态
def persist_results(state: AnalysisState, *, db: Session) -> AnalysisState:
    run_id = state["run_id"]
    now = _utcnow()
    run = db.execute(
        select(MonitorRun).where(MonitorRun.id == run_id)
    ).scalar_one()

    if state.get("analysis_status") == "skipped":
        _upsert_execution(
            db,
            run_id=run_id,
            platform_code=None,
            agent_code="analysis_orchestrator",
            status="skipped",
            error_message=state.get("skip_reason") or "skipped",
            started_at=now,
            finished_at=now,
            input_snapshot={"reason": state.get("skip_reason")},
        )
        run.analysis_status = "skipped"
        db.commit()
        return {"analysis_status": "skipped", "skip_reason": state.get("skip_reason")}

    platform_failures = state.get("platform_failures") or {}
    completed_platforms = 0
    partial_platforms = 0

    for platform_code in state["platform_codes"]:
        metrics_dict = (state.get("platform_metrics") or {}).get(platform_code)
        if not metrics_dict:
            continue
        metrics = _deserialize_platform_metrics(metrics_dict)
        failures = platform_failures.get(platform_code) or []
        if failures:
            status = "partial_success"
            partial_platforms += 1
        else:
            status = "completed"
            completed_platforms += 1

        insights = (state.get("platform_insights") or {}).get(platform_code) or {}
        _upsert_platform_analysis(
            db,
            run_id=run_id,
            platform_code=platform_code,
            metrics=metrics,
            insights=insights,
            status=status,
        )
        _upsert_source_stats(db, run_id=run_id, metrics=metrics)
        _upsert_prompt_competitiveness(db, run_id=run_id, metrics=metrics)
        _upsert_metric_snapshots(
            db,
            run_id=run_id,
            project_id=state["project_id"],
            prompt_set_version=state["prompt_set_version"],
            metrics=metrics,
        )

    for record in state.get("execution_records") or []:
        _upsert_execution(db, **record)

    if partial_platforms and completed_platforms:
        analysis_status = "partial_success"
    elif partial_platforms and not completed_platforms:
        analysis_status = "partial_success"
    else:
        analysis_status = "completed"

    run.analysis_status = analysis_status
    db.commit()
    return {"analysis_status": analysis_status}


# 从状态字典反序列化为 AnswerInput
def _deserialize_answer(payload: dict[str, Any]) -> AnswerInput:
    return AnswerInput(
        answer_id=payload["answer_id"],
        prompt_id=payload["prompt_id"],
        platform_code=payload["platform_code"],
        task_status=payload["task_status"],
        normalized_text=payload["normalized_text"],
        brand_mentions=tuple(
            BrandMentionInput(**mention) for mention in payload.get("brand_mentions", [])
        ),
        citations=tuple(
            CitationInput(**citation) for citation in payload.get("citations", [])
        ),
        agent_recommendation=payload.get("agent_recommendation"),
    )


# 从状态字典反序列化为 PlatformMetricsOutput
def _deserialize_platform_metrics(payload: dict[str, Any]) -> PlatformMetricsOutput:
    from app.geo_monitoring.analysis.dto import (
        BrandMetricsRow,
        CompetitorRow,
        PromptCompetitivenessRow,
        RateMetric,
        RecommendationMetric,
        SourceStatRow,
    )

    # 辅助：反序列化 RateMetric 子结构
    def _rate(data: dict[str, Any]) -> RateMetric:
        return RateMetric(
            numerator=int(data["numerator"]),
            denominator=int(data["denominator"]),
            rate=Decimal(data["rate"]) if data.get("rate") is not None else None,
        )

    recommendation = payload["recommendation"]
    empty_rate = {"numerator": 0, "denominator": 0, "rate": None}
    return PlatformMetricsOutput(
        platform_code=payload["platform_code"],
        valid_answer_count=int(payload["valid_answer_count"]),
        brand_visibility=_rate(payload["brand_visibility"]),
        brand_top1_mention_rate=_rate(payload["brand_top1_mention_rate"]),
        brand_top3_mention_rate=_rate(payload["brand_top3_mention_rate"]),
        brand_top10_mention_rate=_rate(
            payload.get("brand_top10_mention_rate") or empty_rate
        ),
        citation_rate=_rate(payload["citation_rate"]),
        recommendation=RecommendationMetric(
            numerator=int(recommendation["numerator"]),
            denominator=int(recommendation["denominator"]),
            rate=Decimal(recommendation["rate"])
            if recommendation.get("rate") is not None
            else None,
            rule_numerator=int(recommendation["rule_numerator"]),
            rule_rate=Decimal(recommendation["rule_rate"])
            if recommendation.get("rule_rate") is not None
            else None,
            agent_numerator=int(recommendation["agent_numerator"]),
            agent_rate=Decimal(recommendation["agent_rate"])
            if recommendation.get("agent_rate") is not None
            else None,
            combined_numerator=int(recommendation["combined_numerator"]),
            combined_rate=Decimal(recommendation["combined_rate"])
            if recommendation.get("combined_rate") is not None
            else None,
        ),
        source_coverage=_rate(payload["source_coverage"]),
        competitor_advantage_gap=Decimal(payload["competitor_advantage_gap"])
        if payload.get("competitor_advantage_gap") is not None
        else None,
        top_competitors=tuple(
            CompetitorRow(
                brand_id=row["brand_id"],
                brand_name=row["brand_name"],
                mention_answer_count=row["mention_answer_count"],
                visibility_rate=Decimal(row["visibility_rate"])
                if row.get("visibility_rate") is not None
                else None,
            )
            for row in payload.get("top_competitors", [])
        ),
        source_stats=tuple(
            SourceStatRow(
                platform_code=row["platform_code"],
                domain=row["domain"],
                citation_count=row["citation_count"],
                answer_coverage_count=row["answer_coverage_count"],
                share_rate=Decimal(row["share_rate"])
                if row.get("share_rate") is not None
                else None,
                rank_no=row["rank_no"],
            )
            for row in payload.get("source_stats", [])
        ),
        prompt_competitiveness_rows=tuple(
            PromptCompetitivenessRow(
                prompt_id=row["prompt_id"],
                platform_code=row["platform_code"],
                target_rank=row.get("target_rank"),
                target_first=row.get("target_first"),
                competitiveness_score=Decimal(row["competitiveness_score"])
                if row.get("competitiveness_score") is not None
                else None,
                competitors_json=tuple(row.get("competitors_json") or []),
                position_label=row.get("position_label"),
            )
            for row in payload.get("prompt_competitiveness_rows", [])
        ),
        brand_metrics=tuple(
            BrandMetricsRow(
                brand_id=row["brand_id"],
                brand_name=row["brand_name"],
                brand_category=row["brand_category"],
                mention_count=row["mention_count"],
                mention_conversation_count=row["mention_conversation_count"],
                mention_rate=_rate(row["mention_rate"]),
                mention_rate_percent=Decimal(row["mention_rate_percent"])
                if row.get("mention_rate_percent") is not None
                else None,
                average_mention_rank=Decimal(row["average_mention_rank"])
                if row.get("average_mention_rank") is not None
                else None,
                share_of_voice=Decimal(row["share_of_voice"])
                if row.get("share_of_voice") is not None
                else None,
                positive_neutral_sentiment_percent=Decimal(
                    row["positive_neutral_sentiment_percent"]
                )
                if row.get("positive_neutral_sentiment_percent") is not None
                else None,
                brand_score=Decimal(row["brand_score"])
                if row.get("brand_score") is not None
                else None,
                include_in_avg_rank_display=row["include_in_avg_rank_display"],
            )
            for row in payload.get("brand_metrics", [])
        ),
        average_mention_rank=Decimal(payload["average_mention_rank"])
        if payload.get("average_mention_rank") is not None
        else None,
        share_of_voice=Decimal(payload["share_of_voice"])
        if payload.get("share_of_voice") is not None
        else None,
        brand_mention_total_count=int(payload.get("brand_mention_total_count") or 0),
        positive_rate=_rate(payload.get("positive_rate") or empty_rate),
        neutral_rate=_rate(payload.get("neutral_rate") or empty_rate),
        negative_rate=_rate(payload.get("negative_rate") or empty_rate),
    )


# 将 LLM 调用结果转换为 Agent 执行记录字典
def _execution_record_from_result(
    *,
    run_id: int,
    platform_code: str | None,
    agent_code: str,
    request: AgentLLMRequest,
    result: AgentLLMResult | AgentLLMFailure,
) -> dict[str, Any]:
    now = _utcnow()
    if isinstance(result, AgentLLMFailure):
        return {
            "run_id": run_id,
            "platform_code": platform_code,
            "agent_code": agent_code,
            "status": "failed",
            "schema_version": SCHEMA_VERSION,
            "input_snapshot": {
                "template_key": request.template_key,
                "request_id": request.request_id,
                "variables": request.variables,
            },
            "output_json": None,
            "model_name": None,
            "prompt_version": result.prompt_version,
            "prompt_tokens": None,
            "completion_tokens": None,
            "error_message": result.error_message,
            "started_at": now,
            "finished_at": now,
        }

    return {
        "run_id": run_id,
        "platform_code": platform_code,
        "agent_code": agent_code,
        "status": "success",
        "schema_version": SCHEMA_VERSION,
        "input_snapshot": result.input_metadata,
        "output_json": result.parsed.model_dump(),
        "model_name": result.model,
        "prompt_version": result.prompt_version,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "error_message": None,
        "started_at": now,
        "finished_at": now,
    }


# 插入或更新 Agent 执行审计记录（保留历史快照）
def _upsert_execution(db: Session, **fields: Any) -> None:
    existing = db.execute(
        select(AgentExecution).where(
            AgentExecution.run_id == fields["run_id"],
            AgentExecution.agent_code == fields["agent_code"],
            AgentExecution.schema_version == fields.get("schema_version", SCHEMA_VERSION),
            AgentExecution.platform_code.is_(None)
            if fields.get("platform_code") is None
            else AgentExecution.platform_code == fields["platform_code"],
            AgentExecution.is_deleted.is_(False),
        )
    ).scalar_one_or_none()

    if existing is None:
        db.add(AgentExecution(**fields))
        return

    history = list((existing.input_snapshot or {}).get("execution_history") or [])
    history.append(
        {
            "status": existing.status,
            "output_json": existing.output_json,
            "prompt_version": existing.prompt_version,
            "finished_at": existing.finished_at.isoformat()
            if existing.finished_at
            else None,
        }
    )
    merged_snapshot = dict(fields.get("input_snapshot") or {})
    merged_snapshot["execution_history"] = history
    existing.status = fields["status"]
    existing.input_snapshot = merged_snapshot
    existing.output_json = fields.get("output_json")
    existing.model_name = fields.get("model_name")
    existing.prompt_version = fields.get("prompt_version")
    existing.prompt_tokens = fields.get("prompt_tokens")
    existing.completion_tokens = fields.get("completion_tokens")
    existing.error_message = fields.get("error_message")
    existing.started_at = fields.get("started_at")
    existing.finished_at = fields.get("finished_at")


# 插入或更新平台级分析汇总记录
def _upsert_platform_analysis(
    db: Session,
    *,
    run_id: int,
    platform_code: str,
    metrics: PlatformMetricsOutput,
    insights: dict[str, Any],
    status: str,
) -> None:
    existing = db.execute(
        select(PlatformAnalysis).where(
            PlatformAnalysis.run_id == run_id,
            PlatformAnalysis.platform_code == platform_code,
            PlatformAnalysis.is_deleted.is_(False),
        )
    ).scalar_one_or_none()

    target_first_count = metrics.brand_top1_mention_rate.numerator
    brand_first_among_mentions_rate = compute_rate(
        target_first_count,
        metrics.brand_visibility.numerator,
    )
    payload = {
        "run_id": run_id,
        "platform_code": platform_code,
        "valid_answer_count": metrics.valid_answer_count,
        "data_completeness_rate": _decimal(metrics.brand_visibility.rate),
        "brand_mention_count": metrics.brand_visibility.numerator,
        "brand_mention_rate": _decimal(metrics.brand_visibility.rate),
        "brand_first_count": target_first_count,
        "brand_first_rate": _decimal(metrics.brand_top1_mention_rate.rate),
        "brand_first_among_mentions_rate": _decimal(brand_first_among_mentions_rate),
        "top_competitors": serialize_state({"rows": metrics.top_competitors})["rows"],
        "top_sources": serialize_state({"rows": metrics.source_stats})["rows"],
        "prompt_competitiveness_summary": serialize_state(
            {"rows": metrics.prompt_competitiveness_rows}
        )["rows"],
        "improvement_json": insights.get("insights"),
        "summary_json": {
            "risk": insights.get("risk"),
            "metrics": serialize_state({"metrics": metrics})["metrics"],
        },
        "status": status,
    }

    if existing is None:
        db.add(PlatformAnalysis(**payload))
    else:
        for key, value in payload.items():
            setattr(existing, key, value)


# 插入或更新各引用域名的来源统计记录
def _upsert_source_stats(
    db: Session, *, run_id: int, metrics: PlatformMetricsOutput
) -> None:
    for row in metrics.source_stats:
        existing = db.execute(
            select(SourceStat).where(
                SourceStat.run_id == run_id,
                SourceStat.domain == row.domain,
                SourceStat.platform_code == metrics.platform_code,
                SourceStat.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        payload = {
            "run_id": run_id,
            "platform_code": metrics.platform_code,
            "domain": row.domain,
            "source_type": "web",
            "citation_count": row.citation_count,
            "brand_related_count": row.answer_coverage_count,
            "share_rate": _decimal(row.share_rate),
            "rank_no": row.rank_no,
        }
        if existing is None:
            db.add(SourceStat(**payload))
        else:
            for key, value in payload.items():
                setattr(existing, key, value)


# 插入或更新各 Prompt 的竞争力分析记录
def _upsert_prompt_competitiveness(
    db: Session, *, run_id: int, metrics: PlatformMetricsOutput
) -> None:
    for row in metrics.prompt_competitiveness_rows:
        existing = db.execute(
            select(PromptCompetitiveness).where(
                PromptCompetitiveness.run_id == run_id,
                PromptCompetitiveness.prompt_id == row.prompt_id,
                PromptCompetitiveness.platform_code == row.platform_code,
                PromptCompetitiveness.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        payload = {
            "run_id": run_id,
            "prompt_id": row.prompt_id,
            "platform_code": row.platform_code,
            "target_mentioned": row.target_rank is not None,
            "target_rank": row.target_rank,
            "target_first": row.target_first,
            "competitors_json": list(row.competitors_json),
            "position_label": row.position_label,
            "competitiveness_score": row.competitiveness_score,
            "evidence_json": None,
        }
        if existing is None:
            db.add(PromptCompetitiveness(**payload))
        else:
            for key, value in payload.items():
                setattr(existing, key, value)


# 按维度查找指标快照（含软删行，避免唯一索引冲突）
def _find_metric_snapshot_for_upsert(
    db: Session,
    *,
    project_id: int,
    run_id: int,
    metric_code: str,
    platform_code: str,
    prompt_id: int | None,
    brand_id: int | None = None,
) -> MetricSnapshot | None:
    conditions = [
        MetricSnapshot.project_id == project_id,
        MetricSnapshot.run_id == run_id,
        MetricSnapshot.metric_code == metric_code,
        MetricSnapshot.platform_code == platform_code,
    ]
    if prompt_id is None:
        conditions.append(MetricSnapshot.prompt_id.is_(None))
    else:
        conditions.append(MetricSnapshot.prompt_id == prompt_id)
    if brand_id is None:
        conditions.append(MetricSnapshot.brand_id.is_(None))
    else:
        conditions.append(MetricSnapshot.brand_id == brand_id)

    active = db.execute(
        select(MetricSnapshot).where(*conditions, MetricSnapshot.is_deleted.is_(False))
    ).scalar_one_or_none()
    if active is not None:
        return active

    return db.execute(
        select(MetricSnapshot).where(*conditions, MetricSnapshot.is_deleted.is_(True))
    ).scalar_one_or_none()


# 写入或更新单条指标快照
def _save_metric_snapshot(
    db: Session,
    *,
    project_id: int,
    run_id: int,
    platform_code: str,
    prompt_id: int | None,
    metric_code: str,
    payload: dict[str, Any],
    brand_id: int | None = None,
) -> None:
    existing = _find_metric_snapshot_for_upsert(
        db,
        project_id=project_id,
        run_id=run_id,
        metric_code=metric_code,
        platform_code=platform_code,
        prompt_id=prompt_id,
        brand_id=brand_id,
    )
    if existing is None:
        db.add(MetricSnapshot(**payload))
        return

    for key, value in payload.items():
        setattr(existing, key, value)
    existing.is_deleted = False
    existing.deleted_at = None


# 插入或更新平台级与推荐率指标快照
def _upsert_metric_snapshots(
    db: Session,
    *,
    run_id: int,
    project_id: int,
    prompt_set_version: str,
    metrics: PlatformMetricsOutput,
) -> None:
    metric_rows: dict[str, Any] = {
        "brand_visibility": metrics.brand_visibility,
        "brand_top1_mention_rate": metrics.brand_top1_mention_rate,
        "brand_top3_mention_rate": metrics.brand_top3_mention_rate,
        "brand_top10_mention_rate": metrics.brand_top10_mention_rate,
        "citation_rate": metrics.citation_rate,
        "source_coverage": metrics.source_coverage,
        "positive_rate": metrics.positive_rate,
        "neutral_rate": metrics.neutral_rate,
        "negative_rate": metrics.negative_rate,
    }
    scalar_rows: dict[str, Decimal | None | int] = {
        "average_mention_rank": metrics.average_mention_rank,
        "share_of_voice": metrics.share_of_voice,
        "brand_mention_total_count": metrics.brand_mention_total_count,
    }
    for metric_code, metric in metric_rows.items():
        payload = {
            "project_id": project_id,
            "run_id": run_id,
            "platform_code": metrics.platform_code,
            "prompt_id": None,
            "brand_id": None,
            "metric_code": metric_code,
            "numerator": Decimal(metric.numerator),
            "denominator": Decimal(metric.denominator),
            "metric_value": metric.rate,
            "metric_json": serialize_state({"metric": metric})["metric"],
            "prompt_set_version": prompt_set_version,
            "is_comparable": True,
            "completeness_rate": _decimal(metrics.brand_visibility.rate),
        }
        _save_metric_snapshot(
            db,
            project_id=project_id,
            run_id=run_id,
            platform_code=metrics.platform_code,
            prompt_id=None,
            metric_code=metric_code,
            payload=payload,
        )

    for metric_code, value in scalar_rows.items():
        if metric_code == "brand_mention_total_count":
            numerator = Decimal(int(value))
            denominator = Decimal(metrics.valid_answer_count)
            metric_value = numerator
        else:
            numerator = None
            denominator = None
            metric_value = _decimal(value) if value is not None else None
        payload = {
            "project_id": project_id,
            "run_id": run_id,
            "platform_code": metrics.platform_code,
            "prompt_id": None,
            "brand_id": None,
            "metric_code": metric_code,
            "numerator": numerator,
            "denominator": denominator,
            "metric_value": metric_value,
            "metric_json": serialize_state({"metric": value})["metric"],
            "prompt_set_version": prompt_set_version,
            "is_comparable": True,
            "completeness_rate": _decimal(metrics.brand_visibility.rate),
        }
        _save_metric_snapshot(
            db,
            project_id=project_id,
            run_id=run_id,
            platform_code=metrics.platform_code,
            prompt_id=None,
            metric_code=metric_code,
            payload=payload,
        )

    for row in metrics.brand_metrics:
        brand_metric_rows = {
            "brand_mention_rate": row.mention_rate,
            "average_mention_rank": row.average_mention_rank,
            "share_of_voice": row.share_of_voice,
            "brand_mention_total_count": row.mention_count,
        }
        for metric_code, metric in brand_metric_rows.items():
            if metric_code == "brand_mention_total_count":
                payload = {
                    "project_id": project_id,
                    "run_id": run_id,
                    "platform_code": metrics.platform_code,
                    "prompt_id": None,
                    "brand_id": row.brand_id,
                    "metric_code": metric_code,
                    "numerator": Decimal(metric),
                    "denominator": Decimal(metrics.valid_answer_count),
                    "metric_value": Decimal(metric),
                    "metric_json": serialize_state({"metric": metric})["metric"],
                    "prompt_set_version": prompt_set_version,
                    "is_comparable": True,
                    "completeness_rate": _decimal(metrics.brand_visibility.rate),
                }
            elif metric_code == "average_mention_rank":
                payload = {
                    "project_id": project_id,
                    "run_id": run_id,
                    "platform_code": metrics.platform_code,
                    "prompt_id": None,
                    "brand_id": row.brand_id,
                    "metric_code": metric_code,
                    "numerator": None,
                    "denominator": None,
                    "metric_value": metric,
                    "metric_json": serialize_state({"metric": metric})["metric"],
                    "prompt_set_version": prompt_set_version,
                    "is_comparable": True,
                    "completeness_rate": _decimal(metrics.brand_visibility.rate),
                }
            elif metric_code == "share_of_voice":
                payload = {
                    "project_id": project_id,
                    "run_id": run_id,
                    "platform_code": metrics.platform_code,
                    "prompt_id": None,
                    "brand_id": row.brand_id,
                    "metric_code": metric_code,
                    "numerator": None,
                    "denominator": None,
                    "metric_value": metric,
                    "metric_json": serialize_state({"metric": metric})["metric"],
                    "prompt_set_version": prompt_set_version,
                    "is_comparable": True,
                    "completeness_rate": _decimal(metrics.brand_visibility.rate),
                }
            else:
                payload = {
                    "project_id": project_id,
                    "run_id": run_id,
                    "platform_code": metrics.platform_code,
                    "prompt_id": None,
                    "brand_id": row.brand_id,
                    "metric_code": metric_code,
                    "numerator": Decimal(metric.numerator),
                    "denominator": Decimal(metric.denominator),
                    "metric_value": metric.rate,
                    "metric_json": serialize_state({"metric": metric})["metric"],
                    "prompt_set_version": prompt_set_version,
                    "is_comparable": True,
                    "completeness_rate": _decimal(metrics.brand_visibility.rate),
                }
            _save_metric_snapshot(
                db,
                project_id=project_id,
                run_id=run_id,
                platform_code=metrics.platform_code,
                prompt_id=None,
                metric_code=metric_code,
                payload=payload,
                brand_id=row.brand_id,
            )

    recommendation = metrics.recommendation
    payload = {
        "project_id": project_id,
        "run_id": run_id,
        "platform_code": metrics.platform_code,
        "prompt_id": None,
        "brand_id": None,
        "metric_code": "recommendation_combined_rate",
        "numerator": Decimal(recommendation.combined_numerator),
        "denominator": Decimal(recommendation.denominator),
        "metric_value": recommendation.combined_rate,
        "metric_json": serialize_state({"metric": recommendation})["metric"],
        "prompt_set_version": prompt_set_version,
        "is_comparable": True,
        "completeness_rate": _decimal(metrics.brand_visibility.rate),
    }
    _save_metric_snapshot(
        db,
        project_id=project_id,
        run_id=run_id,
        platform_code=metrics.platform_code,
        prompt_id=None,
        metric_code="recommendation_combined_rate",
        payload=payload,
    )
